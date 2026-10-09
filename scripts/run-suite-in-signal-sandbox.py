#!/usr/bin/env python3
"""Run one test suite inside the signal sandbox, optionally with a hand mutant applied.

Usage:
  python3 scripts/run-suite-in-signal-sandbox.py <suite> [--mutant PATCH]
                                                [--checkout DIR] [--python PY]
                                                [--lock-file PATH]

  <suite>      the suite's path relative to the checkout's top directory,
               such as scripts/run-all-test-suites-test.py, or an absolute
               path inside the checkout
  --mutant     a patch `git apply` can apply in the checkout; the suite runs
               once without it, which must pass, then the patch is applied to
               the files it names, the suite runs again, and those files are
               put back byte for byte with their mode and modification time,
               whatever happens to the suite
  --checkout   the checkout's top directory; default the current directory
  --python     the interpreter for a Python suite; default this one
  --lock-file  default ~/.claude/.run-all-test-suites.lock, the lock
               scripts/run-all-test-suites.py takes

The suite runs exactly as scripts/run-all-test-suites.py runs it: from the
checkout's top directory, stdin closed, without the variables that redirect
git, inside the signal sandbox (`bwrap --unshare-pid` on Linux, `sandbox-exec`
on macOS), with RUN_ALL_TEST_SUITES_INSIDE_SIGNAL_SANDBOX=1, while holding the
machine's test-run lock. Before the suite starts, a check inside the sandbox
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
deletes or renames a file is refused, because putting the files back is then
more than restoring their bytes.

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
  VERDICT: RESTORE FAILED (...)    exit 4   a mutated file could not be put
                                            back; the message names its copy

Run: python3 scripts/run-suite-in-signal-sandbox.py scripts/a-test.py --mutant /tmp/m.patch
"""

import argparse
import ctypes
import importlib.util
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
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
EXIT_RESTORE_FAILED = 4


def load_run_all_test_suites():
    spec = importlib.util.spec_from_file_location(
        "run_all_test_suites", SCRIPTS_DIR / "run-all-test-suites.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_run_all_test_suites()


class NotRun(Exception):
    """Nothing was run; the message says why."""


class RestoreFailed(Exception):
    """A mutated file could not be put back; the message names where its original is kept."""


class Terminated(BaseException):
    """SIGTERM, SIGHUP or SIGINT arrived; raised so the mutated files are still put back."""


@dataclass
class KeptOriginal:
    data: bytes
    mode: int
    times_ns: tuple


def note_later_interruption(signal_number, frame):
    pass


def raise_terminated(signal_number, frame):
    # A second signal must not abort the restore the first one started.
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


def keep_originals(top, paths, keep_dir):
    """Copy each file's bytes into keep_dir and return {path: KeptOriginal}."""
    originals = {}
    for relative in paths:
        target = top / relative
        status = target.stat()
        data = target.read_bytes()
        kept = keep_dir / relative
        kept.parent.mkdir(parents=True, exist_ok=True)
        kept.write_bytes(data)
        originals[relative] = KeptOriginal(data, status.st_mode & 0o7777,
                                           (status.st_atime_ns, status.st_mtime_ns))
    return originals


def restore_originals(top, originals, keep_dir):
    """Write each original back and read it back; raise RestoreFailed naming any that differ."""
    # A signal arriving half-way through would leave some files mutated.
    failed = []
    blocked = signal.pthread_sigmask(signal.SIG_BLOCK, INTERRUPTING_SIGNALS)
    try:
        failed = write_back(top, originals)
    finally:
        try:
            signal.pthread_sigmask(signal.SIG_SETMASK, blocked)
        except (Terminated, KeyboardInterrupt) as interruption:
            if failed:
                raise RestoreFailed(
                    f"{', '.join(failed)}; the original of each is kept under {keep_dir} "
                    f"(the run was also interrupted: {interruption})") from interruption
            raise
    if failed:
        raise RestoreFailed(
            f"{', '.join(failed)}; the original of each is kept under {keep_dir}")


def write_back(top, originals):
    failed = []
    for relative, original in originals.items():
        target = top / relative
        try:
            target.write_bytes(original.data)
            os.chmod(target, original.mode)
            os.utime(target, ns=original.times_ns)
            remove_cached_bytecode(target)
            status = target.stat()
            if target.read_bytes() != original.data:
                failed.append(f"{relative} (read back differs)")
            elif status.st_mode & 0o7777 != original.mode:
                failed.append(f"{relative} (mode {oct(status.st_mode & 0o7777)}, "
                              f"was {oct(original.mode)})")
        except OSError as error:
            failed.append(f"{relative} ({error})")
    return failed


def remove_cached_bytecode(source):
    """Delete the bytecode cached beside a source file the mutant changes.

    A process that does not inherit PYTHONPYCACHEPREFIX, such as a child started
    with `python3 -I`, reads and writes bytecode beside the source. The mutant
    has the original's size, so bytecode written within the same second passes
    Python's size-and-seconds staleness check: the original's would run during
    the mutant run, and the mutant's after the restore.
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
    caches beside them; the restore deletes that bytecode.

    However the suite ends, every process it left is killed before this returns:
    inside a sandbox that this program did not start, nothing else would. On
    macOS, where no process can adopt orphans, the suite runs as the leader of
    a process group of its own, and that group is what is killed.
    """
    platform = sys.platform if platform is None else platform
    by_process_group = platform == "darwin"
    command = [*sandbox_prefix, sys.executable, str(Path(__file__).resolve()),
               INSIDE_CHECK_OPTION, str(proof_file), "--",
               *suite_command(top, suite, interpreter)]
    environment = runner.environment_without_git_redirecting_variables()
    if bytecode_dir is not None:
        environment["PYTHONPYCACHEPREFIX"] = str(bytecode_dir)
    # A proof left by an earlier run must not vouch for this one.
    proof_file.write_text("")
    process = subprocess.Popen(command, cwd=str(top), env=environment,
                               stdin=subprocess.DEVNULL, start_new_session=by_process_group)
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
    if proof_file.read_text().strip() != expected_proof(platform):
        raise NotRun(f"the check inside the sandbox did not confirm the suite would be "
                     f"confined (exit {process.returncode}), so the suite was not started")
    exit_code = process.returncode
    if runner.does_signal_sandbox_report_killed_suite_as_exit_code_128_plus_signal(sandbox_prefix) and \
            128 < exit_code <= 128 + runner.SIGNAL_NUMBER_LIMIT:
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
    return parser.parse_args(argv)


def run(arguments, platform):
    """Return (verdict line, exit code). Raises NotRun or RestoreFailed."""
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

    lock_handle, holder, previous_holder = runner.take_machine_lock(
        Path(arguments.lock_file), top)
    if lock_handle is None:
        return (f"VERDICT: not run (lock held) — {arguments.lock_file} is held by {holder}; "
                f"run again when that run has finished"), EXIT_LOCKED
    try:
        # Taking the lock overwrote the description a killed run left; clean up after it
        # here, as the run of scripts/run-all-test-suites.py that would have read it does.
        runner.remove_traces_the_last_lock_holder_left(previous_holder)
        if platform != "darwin":
            become_child_subreaper()
        with tempfile.TemporaryDirectory(prefix=f"{PROGRAM}-") as work_name:
            work = Path(work_name)
            proof_file = work / "sandbox-proof"
            if patch is None:
                code = run_suite_confined(top, suite, interpreter, sandbox_prefix, proof_file,
                                          platform=platform)
                return verdict(code, mutant=False)
            paths = files_the_patch_changes(top, patch)
            baseline = run_suite_confined(top, suite, interpreter, sandbox_prefix, proof_file,
                                          platform=platform)
            if baseline != 0:
                raise NotRun(f"the suite fails without the mutant ({runner.describe_exit(baseline)}), "
                             f"so a failure with the mutant in would not show the mutant "
                             f"was caught; the mutant was not applied")
            print(f"{PROGRAM}: the suite passes without the mutant", flush=True)
            keep_dir = Path(tempfile.mkdtemp(prefix=f"{PROGRAM}-originals-"))
            originals = keep_originals(top, paths, keep_dir)
            try:
                applied = runner.git(top, "apply", str(patch))
                if applied.returncode != 0:
                    raise NotRun(f"git apply failed: {applied.stderr.strip()}")
                for relative in paths:
                    remove_cached_bytecode(top / relative)
                print(f"{PROGRAM}: mutant applied to {', '.join(paths)}; originals kept "
                      f"under {keep_dir}", flush=True)
                code = run_suite_confined(top, suite, interpreter, sandbox_prefix, proof_file,
                                          bytecode_dir=work / "bytecode", platform=platform)
            finally:
                restore_originals(top, originals, keep_dir)
            print(f"{PROGRAM}: restored {', '.join(paths)} byte for byte", flush=True)
            shutil.rmtree(keep_dir)
            return verdict(code, mutant=True)
    finally:
        lock_handle.close()


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
    if argv[:1] == [INSIDE_CHECK_OPTION]:
        return inside_check_then_exec(argv[1], argv[3:])
    arguments = parse_arguments(argv)
    install_interruption_handlers()
    try:
        line, code = run(arguments, sys.platform if platform is None else platform)
    except NotRun as error:
        line, code = f"VERDICT: not run — {error}", EXIT_NOT_RUN
    except RestoreFailed as error:
        line, code = f"VERDICT: RESTORE FAILED — {error}", EXIT_RESTORE_FAILED
    except (Terminated, KeyboardInterrupt) as interruption:
        line = (f"VERDICT: not run — interrupted ({type(interruption).__name__} "
                f"{interruption}); any mutated file was put back")
        code = EXIT_NOT_RUN
    print(line, flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
