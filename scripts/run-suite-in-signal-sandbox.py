#!/usr/bin/env python3
"""Run one test suite inside the signal sandbox, optionally with a hand mutant applied.

Usage:
  python3 scripts/run-suite-in-signal-sandbox.py <suite> [--mutant PATCH]
                                                [--checkout DIR] [--python PY]
                                                [--lock-file PATH]
                                                [--wait-for-lock-seconds N]

  <suite>      the suite's path relative to the checkout's top directory,
               such as scripts/run-all-test-suites-test.py, or an absolute
               path inside the checkout
  --mutant     a patch `git apply` can apply in the checkout. The checkout is
               never changed: the program makes a git worktree of it whose
               directory name ends in -mutation-testing-worktree, copies the checkout's
               tracked and untracked files into it as they are now, runs the
               suite there once without the patch, which must pass, then
               applies the patch there and runs the suite again, and removes
               the worktree, whatever happens to the suite. The pre-push hook
               refuses a push from a directory whose name ends in
               -mutation-testing-worktree, so a mutant cannot be pushed from it either
  --checkout   the checkout's top directory; default the current directory
  --python     the interpreter for a Python suite; default this one
  --lock-file  default ~/.claude/.run-all-test-suites.lock. On macOS, the lock
               scripts/run-all-test-suites.py takes there. On Linux no lock is
               taken: the files beside it hold the run records and the admission
               shared with scripts/run-all-test-suites.py
  --wait-for-lock-seconds
               on macOS, how long to wait for that lock, in the kernel's queue as
               `flock -w` waits, before refusing; default 3600, and 0 refuses
               at once. On Linux it is accepted and has no effect

The suite runs exactly as scripts/run-all-test-suites.py runs it: from the
checkout's top directory, stdin closed, without the variables that redirect
git, inside the signal sandbox (`bwrap --unshare-pid` on Linux, `sandbox-exec`
on macOS), with RUN_ALL_TEST_SUITES_INSIDE_SIGNAL_SANDBOX=1; on Linux in a test
sandbox of its own once admission lets it start, at low priority and in a cgroup
scope of its own, whose CPU seconds and peak memory it prints, and on macOS while
holding the machine's test-run lock. Before the suite starts, a check inside the sandbox
proves it is confined: on Linux, that process 1 there is bwrap; on macOS, that
a signal to a process outside the sandbox is refused. If the check fails, the
suite is not run. This program never runs a suite unconfined: without the
sandbox, on a platform other than Linux and macOS, or for a suite listed in
SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX, it refuses. Started inside a sandbox
already, it runs the suite there, after the same check. When the suite ends or
the run is interrupted, it kills every process the suite left behind: on Linux
every descendant, as the end of the sandbox's PID namespace does otherwise; on
macOS every process still in the suite's process group, since macOS keeps no
link from a process whose parent has exited back to that parent, so a leftover
process that moved to another process group and outlived its parent is not found.

The patch may only change files that already exist; a patch that creates,
deletes or renames a file is refused.

The last line printed is the verdict:
  VERDICT: suite passed            exit 0
  VERDICT: suite failed (...)      exit 1
  VERDICT: mutant killed (...)     exit 0   the suite passed without the mutant
                                            and failed with it in
  VERDICT: mutant survived         exit 1   the suite passed with the mutant in
  VERDICT: not run (...)           exit 2   nothing was run, the run could not
                                            be trusted, or the suite failed
                                            without the mutant
  VERDICT: not run (lock held)     exit 3   another test run holds the lock

Run: python3 scripts/run-suite-in-signal-sandbox.py scripts/a-test.py --mutant /tmp/m.patch
"""

import argparse
import contextlib
import ctypes
import importlib.util
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

PROGRAM = "run-suite-in-signal-sandbox"
SCRIPTS_DIR = Path(__file__).resolve().parent
INSIDE_CHECK_OPTION = "--inside-signal-sandbox-check-pid-one-then-exec"
PID_ONE_COMMAND_FILE = Path("/proc/1/comm")
PID_ONE_PROOF = "process 1 is bwrap"
OUTSIDE_SIGNAL_REFUSED_PROOF = "a signal to a process outside the sandbox was refused"
INTERRUPTING_SIGNALS = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)
PR_SET_CHILD_SUBREAPER = 36

EXIT_PASSED_OR_KILLED = 0
EXIT_FAILED_OR_SURVIVED = 1
EXIT_NOT_RUN = 2
EXIT_LOCKED = 3
# The end of the name of every copy a mutant runs in. The pre-push hook refuses a push from a
# directory or of a branch whose name ends in it.
MUTATION_TESTING_WORKTREE_LABEL = "-mutation-testing-worktree"


def load_run_all_test_suites():
    spec = importlib.util.spec_from_file_location(
        "run_all_test_suites", SCRIPTS_DIR / "run-all-test-suites.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Loaded here, so tests can reach it; a failure is kept for main(), which turns it into a verdict.
try:
    runner = load_run_all_test_suites()
    runner_load_failure = None
except Exception as error:
    runner, runner_load_failure = None, error


class NotRun(Exception):
    """Nothing was run; the message says why."""


class Terminated(BaseException):
    """SIGTERM, SIGHUP or SIGINT arrived; raised so the mutation-testing worktree is still removed."""


def note_later_interruption(signal_number, frame):
    pass


def raise_terminated(signal_number, frame):
    # A second signal must not abort the cleanup the first one started.
    for interrupting in INTERRUPTING_SIGNALS:
        signal.signal(interrupting, note_later_interruption)
    raise Terminated(signal.Signals(signal_number).name)


def install_interruption_handlers():
    for interrupting in INTERRUPTING_SIGNALS:
        signal.signal(interrupting, raise_terminated)


def pid_one_is_bwrap(command_file=None):
    command_file = PID_ONE_COMMAND_FILE if command_file is None else command_file
    try:
        return command_file.read_text().strip() == "bwrap"
    except OSError:
        return False


def outside_signal_refusal_failure(environment=None, kill=os.kill):
    """Return None when a signal to the process outside the sandbox is refused, else why not.

    The process is the one named by the outside-process variable, which the
    program that started the sandbox sets to its own process id.
    """
    environment = os.environ if environment is None else environment
    variable = runner.SIGNAL_SANDBOX_TRIAL_SIGNAL_TARGET_PROCESS_VARIABLE
    try:
        outside = int(environment[variable])
    except (KeyError, ValueError):
        return f"{variable} does not name a process here, so there is nothing to signal"
    if outside <= 1:
        return f"{variable} is {outside}, which is not a process this program started"
    try:
        kill(outside, runner.SIGNAL_SANDBOX_MACOS_PROBE_SIGNAL)
    except PermissionError:
        return None
    except OSError as error:
        return f"the trial signal to process {outside} failed with {error}, not a refusal"
    return f"a trial signal to process {outside}, outside the sandbox, was let through"


def inside_check_then_exec(proof_file, command, platform=None):
    """Inside the sandbox: write the proof and start the suite, or refuse without starting it."""
    platform = sys.platform if platform is None else platform
    if platform == "darwin":
        why_not = outside_signal_refusal_failure()
        if why_not is not None:
            print(f"{PROGRAM}: the suite was not started — {why_not}, so a signal "
                  f"from the suite could reach processes outside its sandbox.",
                  file=sys.stderr)
            return EXIT_NOT_RUN
        proof = OUTSIDE_SIGNAL_REFUSED_PROOF
    elif not pid_one_is_bwrap():
        print(f"{PROGRAM}: the suite was not started — process 1 here is not bwrap, "
              f"so the suite would not be in a PID namespace of its own.", file=sys.stderr)
        return EXIT_NOT_RUN
    else:
        proof = PID_ONE_PROOF
    if os.environ.get(runner.SIGNAL_SANDBOX_INSIDE_VARIABLE) != "1":
        print(f"{PROGRAM}: the suite was not started — "
              f"{runner.SIGNAL_SANDBOX_INSIDE_VARIABLE} is not 1 here.", file=sys.stderr)
        return EXIT_NOT_RUN
    Path(proof_file).write_text(proof + "\n")
    os.execvp(command[0], command)


def expected_proof(platform):
    return OUTSIDE_SIGNAL_REFUSED_PROOF if platform == "darwin" else PID_ONE_PROOF


def files_the_patch_changes(top, patch):
    """Return the paths the patch modifies, or raise NotRun when it cannot be applied as it is."""
    check = runner.git(top, "apply", "--check", str(patch))
    if check.returncode != 0:
        raise NotRun(f"the mutant does not apply in {top}: {check.stderr.strip()}")
    summary = runner.git(top, "apply", "--summary", str(patch))
    if summary.returncode != 0:
        raise NotRun(f"git apply --summary failed: {summary.stderr.strip()}")
    if summary.stdout.strip():
        raise NotRun(f"the mutant creates, deletes, renames or changes the mode of a file, "
                     f"and only edits to existing files are put back: {summary.stdout.strip()}")
    numstat = runner.git(top, "apply", "--numstat", "-z", str(patch))
    if numstat.returncode != 0:
        raise NotRun(f"git apply --numstat failed: {numstat.stderr.strip()}")
    paths = [record.split("\t", 2)[2] for record in numstat.stdout.split("\0") if record]
    if not paths:
        raise NotRun("the mutant changes no file")
    return paths


def mutation_testing_worktree_make(top, work):
    """Return a new git worktree of top's HEAD, in work, whose directory name ends in the label."""
    copy = work / f"{top.name}{MUTATION_TESTING_WORKTREE_LABEL}"
    added = runner.git(top, "worktree", "add", "--quiet", "--detach", str(copy), "HEAD")
    if added.returncode != 0:
        raise NotRun(f"the mutation-testing worktree {copy} could not be made: {added.stderr.strip()}")
    return copy


def mutation_testing_worktree_fill(top, copy):
    """Make copy hold top's files as they are now.

    Tracked files, with their uncommitted edits, and untracked files that are not ignored are
    copied. A file of HEAD that top no longer has, whether deleted, staged for deletion or
    renamed, is deleted in the copy.
    """
    listed = runner.git(top, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if listed.returncode != 0:
        raise NotRun(f"git ls-files failed in {top}: {listed.stderr.strip()}")
    for relative in sorted(set(path for path in listed.stdout.split("\0") if path)):
        source, target = top / relative, copy / relative
        if source.is_symlink() or source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink() or target.exists():
                target.unlink()
            shutil.copy2(source, target, follow_symlinks=False)
    of_head = runner.git(copy, "ls-files", "-z")
    if of_head.returncode != 0:
        raise NotRun(f"git ls-files failed in {copy}: {of_head.stderr.strip()}")
    for relative in (path for path in of_head.stdout.split("\0") if path):
        target = copy / relative
        if not os.path.lexists(top / relative) and (target.is_symlink() or target.is_file()):
            target.unlink()


def mutation_testing_worktree_remove(top, copy):
    """Remove the mutation-testing worktree and its worktree record; return why it could not be, or None."""
    removed = runner.git(top, "worktree", "remove", "--force", str(copy))
    if removed.returncode != 0:
        return (f"the mutation-testing worktree {copy} could not be removed "
                f"({removed.stderr.strip()}). Remove it with: git -C {top} worktree remove "
                f"--force {copy} (or, once that directory is gone, git -C {top} worktree prune)")
    return None


def remove_cached_bytecode(source):
    """Delete the bytecode cached beside a source file the mutant changes.

    A process that does not inherit PYTHONPYCACHEPREFIX, such as a child started
    with `python3 -I`, reads and writes bytecode beside the source. The mutant
    has the original's size, so bytecode written within the same second passes
    Python's size-and-seconds staleness check: the original's, cached by the run
    without the mutant in the same copy, would run during the mutant run.
    """
    if source.suffix != ".py":
        return
    for cached in (source.parent / "__pycache__").glob(f"{source.stem}.*.pyc"):
        cached.unlink(missing_ok=True)


def suite_command(top, suite, interpreter):
    if runner.is_shell_test_suite(suite):
        return ["sh", suite]
    return [interpreter, "-u", suite]


def become_child_subreaper():
    """Make orphaned descendants of this process its children, so they can all be found."""
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) != 0:
        raise NotRun(f"prctl(PR_SET_CHILD_SUBREAPER) failed: "
                     f"{os.strerror(ctypes.get_errno())}")


def children_of(parent_pid):
    """Return {pid: state} of the processes whose parent is parent_pid."""
    children = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text()
        except OSError:
            continue
        # The command name in parentheses may hold spaces; the fields after it do not.
        fields = stat[stat.rindex(")") + 2:].split()
        if int(fields[1]) == parent_pid:
            children[int(entry.name)] = fields[0]
    return children


def stop_descendants():
    """SIGKILL and reap every process descended from this one, orphans included.

    Only direct children are signalled: an unreaped child's process id cannot be
    reused, so no other process is hit. A killed child's own children become
    children of this process, the subreaper, and are killed in the next round.
    """
    for _ in range(1000):
        children = children_of(os.getpid())
        if not children:
            return
        for pid, state in children.items():
            if state != "Z":
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        for pid in children:
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass
    raise NotRun("processes the suite started could not all be stopped")


def wait_without_reaping(process):
    """Wait for the process to exit but leave it a zombie, so its process group id stays its own."""
    while True:
        try:
            os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOWAIT)
            return
        except ChildProcessError:
            return
        except InterruptedError:
            continue


def process_group_members_other_than_leader(group_id, run=subprocess.run):
    """Return the ids of processes in the group other than its leader, from macOS's pgrep -g."""
    try:
        listed = run(["pgrep", "-g", str(group_id)], stdin=subprocess.DEVNULL,
                     capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise NotRun(f"pgrep -g {group_id} could not run ({error}), so whether the suite "
                     f"left processes behind is unknown") from error
    # pgrep exits 1 when nothing matched and 0 when something did.
    if listed.returncode not in (0, 1):
        raise NotRun(f"pgrep -g {group_id} exited {listed.returncode}: "
                     f"{listed.stderr.strip()}, so whether the suite left processes "
                     f"behind is unknown")
    return [int(word) for word in listed.stdout.split() if int(word) != group_id]


def stop_process_group_then_reap(process, members_other_than_leader=None):
    """SIGKILL every process left in the suite's process group, then reap its leader.

    The leader is not yet reaped, so its process id, which is the group's id,
    cannot have passed to another process: the signal reaches only the suite's group.
    macOS refuses a signal to a group whose only member is a zombie with EPERM,
    so PermissionError means nothing is left only when the group holds no other process.
    """
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError as error:
        members_other_than_leader = (members_other_than_leader
                                     or process_group_members_other_than_leader)
        left = members_other_than_leader(process.pid)
        if left:
            process.wait()
            raise NotRun(f"processes {', '.join(map(str, left))}, left in the suite's process "
                         f"group, could not be stopped: {error}") from error
    process.wait()


def run_suite_confined(top, suite, interpreter, sandbox_prefix, proof_file, bytecode_dir=None,
                       platform=None):
    """Run the suite inside the sandbox; return its exit code, or raise NotRun if unproven.

    With bytecode_dir, Python started with this environment reads and writes
    bytecode only there, so a mutant run neither runs nor caches bytecode beside
    the sources. A child that drops the environment, such as `python3 -I`, still
    caches beside them, in the mutation-testing worktree, which is removed after the run.

    However the suite ends, every process it left is killed before this returns:
    inside a sandbox that this program did not start, nothing else would. On
    macOS, where no process can adopt orphans, the suite runs as the leader of
    a process group of its own, and that group is what is killed.
    """
    platform = sys.platform if platform is None else platform
    by_process_group = platform == "darwin"
    # A proof left by an earlier run must not vouch for this one.
    proof_file.write_text("")
    environment = runner.launch_environment_for_a_test_suite_with_git_redirecting_agent_session_attendance_and_credential_variables_removed()
    # The proof is read after the sandbox ends, and the bytecode is the suite's own, so
    # both are written for real; nothing else outside the checkout is.
    writable = [proof_file]
    if bytecode_dir is not None:
        bytecode_dir.mkdir(parents=True, exist_ok=True)
        writable.append(bytecode_dir)
        environment["PYTHONPYCACHEPREFIX"] = str(bytecode_dir)
    # The test sandbox is built from Linux's /proc and bwrap, so not on another platform.
    if platform.startswith("linux"):
        sandbox_prefix = runner.command_prefix_starting_one_suite_in_its_test_sandbox(
            sandbox_prefix, top, writable, suite,
            read_only_paths=runner.paths_one_suite_launch_needs_shown_read_only_in_test_sandbox(
                [sys.executable, interpreter], [Path(__file__).resolve()], checkout=top))
    command = [*sandbox_prefix,
               sys.executable, str(Path(__file__).resolve()),
               INSIDE_CHECK_OPTION, str(proof_file), "--",
               *suite_command(top, suite, interpreter)]
    statistics = None
    in_test_sandbox = platform.startswith("linux") and \
        runner.does_signal_sandbox_report_killed_suite_as_exit_code_128_plus_signal(sandbox_prefix)
    if in_test_sandbox:
        # At low priority and in a cgroup scope of its own, as the runner's suites run.
        resource_prefix = ["nice", "-n", str(runner.TEST_SUITE_NICE_INCREMENT)]
        cgroup_unavailable_because = runner.why_test_suites_cannot_run_in_cgroup_scopes_on_this_machine_or_none()
        if cgroup_unavailable_because is None:
            statistics = tempfile.TemporaryFile()
            resource_prefix = [*runner.command_prefix_running_one_suite_in_its_cgroup_scope(
                statistics.fileno(), in_bwrap=True), *resource_prefix]
        else:
            print(f"{PROGRAM}: the suite runs without a cgroup scope, so its CPU seconds and "
                  f"peak memory are not measured: {cgroup_unavailable_because}", flush=True)
        command = [*resource_prefix, *command]
    process = subprocess.Popen(command, cwd=str(top), env=environment,
                               stdin=subprocess.DEVNULL, start_new_session=by_process_group,
                               pass_fds=(statistics.fileno(),) if statistics is not None else ())
    if by_process_group:
        try:
            wait_without_reaping(process)
        finally:
            stop_process_group_then_reap(process)
    else:
        try:
            process.wait()
        finally:
            if process.returncode is None:
                process.kill()
                process.wait()
            stop_descendants()
    if statistics is not None:
        with statistics:
            statistics.seek(0)
            cpu_seconds, peak_memory, missing = \
                runner.cpu_seconds_and_peak_memory_from_suite_cgroup_statistics(
                    statistics.read().decode("utf-8", "replace"))
        print(f"{PROGRAM}: " + (missing if missing else
                                f"the suite used {cpu_seconds:.1f} CPU seconds, peak memory "
                                f"{peak_memory / 10**6:.0f} MB"), flush=True)
    try:
        proof = runner.read_text_without_following_symlinks(proof_file)
    except OSError:
        proof = ""
    if proof.strip() != expected_proof(platform):
        raise NotRun(f"the check inside the sandbox did not confirm the suite would be "
                     f"confined (exit {process.returncode}), so the suite was not started")
    exit_code = process.returncode
    if in_test_sandbox and 128 < exit_code <= 128 + runner.SIGNAL_NUMBER_LIMIT:
        exit_code = -(exit_code - 128)
    return exit_code


def verdict(code, mutant):
    """Return (line, exit code) for the suite's exit code."""
    described = runner.describe_exit(code)
    if mutant:
        if code == 0:
            return "VERDICT: mutant survived — the suite passed with the mutant in", \
                EXIT_FAILED_OR_SURVIVED
        return f"VERDICT: mutant killed — the suite failed: {described}", EXIT_PASSED_OR_KILLED
    if code == 0:
        return "VERDICT: suite passed", EXIT_PASSED_OR_KILLED
    return f"VERDICT: suite failed — {described}", EXIT_FAILED_OR_SURVIVED


def parse_arguments(argv):
    parser = argparse.ArgumentParser(prog=PROGRAM, description=__doc__.splitlines()[0])
    parser.add_argument("suite")
    parser.add_argument("--mutant")
    parser.add_argument("--checkout", default=".")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--lock-file", default=str(runner.DEFAULT_LOCK_FILE))
    parser.add_argument("--wait-for-lock-seconds", type=float,
                        default=runner.MACHINE_LOCK_WAIT_SECONDS_SUGGESTED)
    arguments = parser.parse_args(argv)
    if arguments.wait_for_lock_seconds < 0:
        parser.error("--wait-for-lock-seconds takes a number of seconds of at least 0")
    return arguments


def run(arguments, platform):
    """Return (verdict line, exit code). Raises NotRun."""
    try:
        top = runner.checkout_top_directory(arguments.checkout)
        interpreter, _ = runner.interpreter_and_version(arguments.python)
    except runner.CouldNotRun as error:
        raise NotRun(str(error).split("\n")[0]) from error
    suite = suite_relative_to_top(arguments.suite, top)
    if not (top / suite).is_file():
        raise NotRun(f"{suite} is not a file in {top}; pass the suite's path relative to "
                     f"the checkout's top directory")
    if suite in runner.SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX:
        raise NotRun(f"{suite} cannot run inside the signal sandbox: "
                     f"{runner.SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX[suite]}")
    patch = Path(arguments.mutant).resolve() if arguments.mutant else None
    if patch is not None and not patch.is_file():
        raise NotRun(f"the mutant {arguments.mutant} is not a file")
    if not (platform.startswith("linux") or platform == "darwin"):
        raise NotRun(f"{platform} has no signal sandbox; this program runs only on Linux "
                     f"and macOS")
    if platform == "darwin" and not hasattr(os, "waitid"):
        raise NotRun("this Python has no os.waitid, which stopping the suite's leftover "
                     "processes on macOS needs; run it with Python 3.13 or later")
    try:
        sandbox_prefix, unconfined_because = runner.signal_sandbox(platform=platform)
    except runner.SignalSandboxCouldNotStart as error:
        raise NotRun(f"the signal sandbox could not start: {error}") from error
    if unconfined_because:
        raise NotRun(f"no signal sandbox: {unconfined_because}")

    # In its own test sandbox the suite shares no machine state with other runs, so no
    # machine lock is taken; admission decides when it starts, as for the runner's suites.
    in_test_sandbox = platform.startswith("linux") and \
        runner.does_signal_sandbox_report_killed_suite_as_exit_code_128_plus_signal(sandbox_prefix)
    lock_handle = None
    previous_holder = ""
    if in_test_sandbox:
        psutil, _ = runner.psutil_imported_or_why_not()
        if psutil is None:
            raise NotRun(f"{sys.executable} cannot import psutil, which reads the machine's "
                         f"CPU use and memory before the suite starts; install the pinned "
                         f"libraries with `python3 nc-systems/general-tools/"
                         f"python-libraries-pinned-requirements-check-and-install.py`, "
                         f"then run this again")
    else:
        if arguments.wait_for_lock_seconds > 0:
            # A caller waiting under a timeout of its own sees why nothing has happened yet.
            print(f"{PROGRAM}: waiting up to {arguments.wait_for_lock_seconds:g} s for "
                  f"{arguments.lock_file}", flush=True)
        lock_handle, holder, previous_holder = runner.take_machine_lock(
            Path(arguments.lock_file), top, arguments.wait_for_lock_seconds)
        if lock_handle is None:
            waited = (f"after waiting {arguments.wait_for_lock_seconds:g} s "
                      if arguments.wait_for_lock_seconds > 0 else "")
            return (f"VERDICT: not run (lock held) — {arguments.lock_file} is still held "
                    f"{waited}by {holder}; if you started this program under flock on that "
                    f"lock, that flock is the holder, so run this program without flock, since "
                    f"it waits for the lock itself; otherwise, tell the user which process "
                    f"holds the lock"), EXIT_LOCKED
    readings = None
    try:
        # Clean up after earlier runs here, as scripts/run-all-test-suites.py does.
        if lock_handle is None:
            with runner.lock_held_while_cleaning_up_after_earlier_runs(Path(arguments.lock_file)):
                runner.clean_up_after_earlier_runs(Path(arguments.lock_file), previous_holder,
                                                   platform)
        else:
            runner.clean_up_after_earlier_runs(Path(arguments.lock_file), previous_holder,
                                               platform)
        admitted = contextlib.nullcontext(0.0)
        if in_test_sandbox:
            readings = runner.TestSuiteAdmissionMachineCpuAndMemoryReadingsSampler(psutil)
            readings.start()
            try:
                admission = runner.MachineWideTestSuiteAdmission(
                    runner.test_suite_admission_directory_for_lock_file(arguments.lock_file), readings,
                    lambda line: print(f"{PROGRAM}: {line}", flush=True))
            except runner.MachineWideTestSuiteAdmissionCouldNotDecide as error:
                raise NotRun(f"admission could not start: {error}") from error
            admitted = admission.admitted(suite)
        with admitted:
            return run_admitted_suite(top, suite, interpreter, sandbox_prefix, patch, platform)
    except runner.MachineWideTestSuiteAdmissionCouldNotDecide as error:
        raise NotRun(f"admission failed: {error}") from error
    finally:
        if readings is not None:
            readings.stop()
        if lock_handle is not None:
            lock_handle.close()


def run_admitted_suite(top, suite, interpreter, sandbox_prefix, patch, platform):
    """Run the suite, with the mutant when patch is given; return (verdict line, exit code)."""
    if platform != "darwin":
        become_child_subreaper()
    with tempfile.TemporaryDirectory(prefix=f"{PROGRAM}-") as work_name:
        work = Path(work_name)
        proof_file = work / "sandbox-proof"
        if patch is None:
            code = run_suite_confined(top, suite, interpreter, sandbox_prefix, proof_file,
                                      platform=platform)
            return verdict(code, mutant=False)
        copy = mutation_testing_worktree_make(top, work)
        outcome = None
        # Removal is armed before the copy is filled, so a failure or a signal while filling
        # does not leave the worktree registered.
        try:
            mutation_testing_worktree_fill(top, copy)
            paths = files_the_patch_changes(copy, patch)
            baseline = run_suite_confined(copy, suite, interpreter, sandbox_prefix,
                                          proof_file, platform=platform)
            if baseline != 0:
                raise NotRun(f"the suite fails without the mutant "
                             f"({runner.describe_exit(baseline)}), so a failure with the "
                             f"mutant in would not show the mutant was caught; the mutant "
                             f"was not applied")
            print(f"{PROGRAM}: the suite passes without the mutant", flush=True)
            applied = runner.git(copy, "apply", str(patch))
            if applied.returncode != 0:
                raise NotRun(f"git apply failed: {applied.stderr.strip()}")
            for relative in paths:
                remove_cached_bytecode(copy / relative)
            print(f"{PROGRAM}: mutant applied to {', '.join(paths)} in the mutation-testing "
                  f"worktree {copy}; {top} is not changed", flush=True)
            code = run_suite_confined(copy, suite, interpreter, sandbox_prefix, proof_file,
                                      bytecode_dir=work / "bytecode", platform=platform)
            outcome = verdict(code, mutant=True)
        finally:
            not_removed = mutation_testing_worktree_remove(top, copy)
            if not_removed is not None:
                # A worktree left behind is a failure, whatever the run found.
                found = (outcome[0].removeprefix("VERDICT: ") if outcome
                         else sys.exc_info()[1])
                raise NotRun(f"{not_removed}, then run this again. The run itself ended with: "
                             f"{found}; it counts as not run, because it left the worktree "
                             f"behind.")
        return outcome


def suite_relative_to_top(given, top):
    """Return the suite's path relative to top, normalized, so `./` spellings match lists."""
    path = Path(given)
    if path.is_absolute():
        try:
            path = path.resolve().relative_to(top)
        except ValueError as error:
            raise NotRun(f"{given} is not inside the checkout {top}") from error
    normalized = os.path.normpath(path.as_posix())
    if normalized == ".." or normalized.startswith("../"):
        raise NotRun(f"{given} is not inside the checkout {top}")
    return normalized


def main(argv=None, platform=None):
    argv = sys.argv[1:] if argv is None else argv
    if runner_load_failure is not None:
        print(f"VERDICT: not run — scripts/run-all-test-suites.py, which this program uses, could "
              f"not be loaded: {type(runner_load_failure).__name__}: {runner_load_failure}",
              flush=True)
        return EXIT_NOT_RUN
    if argv[:1] == [INSIDE_CHECK_OPTION]:
        return inside_check_then_exec(argv[1], argv[3:])
    try:
        arguments = parse_arguments(argv)
    except SystemExit as exit_request:
        if exit_request.code in (0, None):
            raise
        # argparse has printed what was wrong; the verdict line still ends the output.
        print("VERDICT: not run — the arguments could not be read; see the error above",
              flush=True)
        return EXIT_NOT_RUN
    install_interruption_handlers()
    try:
        line, code = run(arguments, sys.platform if platform is None else platform)
    except NotRun as error:
        line, code = f"VERDICT: not run — {error}", EXIT_NOT_RUN
    except OSError as error:
        # A failure of the machine, such as a full disk while the worktree is filled.
        line = (f"VERDICT: not run — {type(error).__name__}: {error}; run this again once "
                f"that is put right")
        code = EXIT_NOT_RUN
    except (Terminated, KeyboardInterrupt) as interruption:
        line = (f"VERDICT: not run — interrupted ({type(interruption).__name__} "
                f"{interruption}); the checkout was not changed")
        code = EXIT_NOT_RUN
    except Exception as error:
        # Any other failure is the program's, not the suite's: exit 1 would read as a survivor.
        traceback.print_exc()
        line = (f"VERDICT: not run — this program failed: {type(error).__name__}: {error}; "
                f"the traceback is printed above")
        code = EXIT_NOT_RUN
    print(line, flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
