#!/usr/bin/env python3
"""Tests for scripts/run-suite-in-signal-sandbox.py.

Each case runs the program on a scratch checkout holding a tiny suite and the
module it tests, with a lock file of its own, so no case touches this checkout
or the machine's test-run lock. Run by scripts/run-all-test-suites.py, this
file is already inside the signal sandbox and the program runs its suites
there; run directly on Linux with bwrap, the program starts bwrap itself.

Run: python3 scripts/run-suite-in-signal-sandbox-test.py   (exit 0 = all passed)
"""

import contextlib
import fcntl
import io
import json
import importlib.util
import marshal
import py_compile
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import time

# Before anything runs git, so the scratch repository is built where this suite says.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    pathlib.Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
PROGRAM_PATH = SCRIPTS_DIR / "run-suite-in-signal-sandbox.py"

failures = []
cases_run = 0


def check(case_name, condition, detail=""):
    global cases_run
    cases_run += 1
    print(f"{'ok' if condition else 'FAIL'}: {case_name}")
    if not condition:
        failures.append(case_name)
        if detail:
            print(f"      {detail!r}"[:1500])


spec = importlib.util.spec_from_file_location("run_suite_in_signal_sandbox", PROGRAM_PATH)
program = importlib.util.module_from_spec(spec)
spec.loader.exec_module(program)

MODULE_SOURCE = "def double(number):\n    return number * 2\n\n\ndef unused():\n    return 1\n"
SUITE_SOURCE = (
    "import sys\n"
    "sys.path.insert(0, '.')\n"
    "import doubling\n"
    "if doubling.double(3) != 6:\n"
    "    print('FAIL: double(3)')\n"
    "    sys.exit(1)\n"
    "print('all cases passed')\n")
PID_ONE_SUITE_SOURCE = (
    "import pathlib, os\n"
    "print('pid one:', pathlib.Path('/proc/1/comm').read_text().strip())\n"
    "print('inside variable:', os.environ.get('RUN_ALL_TEST_SUITES_INSIDE_SIGNAL_SANDBOX'))\n")
# Passes at once without the mutant; with it, runs long enough for the case to
# terminate the program while the mutant is in.
TERMINATES_THE_PROGRAM_SUITE_SOURCE = (
    "import sys, time\n"
    "sys.path.insert(0, '.')\n"
    "import doubling\n"
    "if doubling.unused() == 1:\n"
    "    sys.exit(0)\n"
    "print('suite started', flush=True)\n"
    "time.sleep(60)\n")
# A child started with -I drops PYTHONPYCACHEPREFIX and caches bytecode beside the source.
CHILD_DROPS_ENVIRONMENT_SUITE_SOURCE = (
    "import subprocess, sys\n"
    "answer = subprocess.run([sys.executable, '-I', '-c', "
    "'import sys; sys.path.insert(0, \".\"); import doubling; print(doubling.unused())'], "
    "capture_output=True, text=True).stdout.strip()\n"
    "if answer != '1':\n"
    "    print('FAIL: unused() answered', answer)\n"
    "    sys.exit(1)\n")
FAILS_WITHOUT_ANY_MUTANT_SUITE_SOURCE = "import missing_dependency_module\n"


def scratch_checkout(scratch):
    repository = scratch / "repo"
    repository.mkdir()
    (repository / "doubling.py").write_bytes(MODULE_SOURCE.encode())
    (repository / "doubling-test.py").write_text(SUITE_SOURCE)
    (repository / "pid-one-test.py").write_text(PID_ONE_SUITE_SOURCE)
    (repository / "terminates-test.py").write_text(TERMINATES_THE_PROGRAM_SUITE_SOURCE)
    (repository / "child-drops-environment-test.py").write_text(
        CHILD_DROPS_ENVIRONMENT_SUITE_SOURCE)
    (repository / "fails-without-mutant-test.py").write_text(
        FAILS_WITHOUT_ANY_MUTANT_SUITE_SOURCE)
    (repository / "fails-test.sh").write_text("echo failing; exit 7\n")
    (repository / ".gitignore").write_text("__pycache__/\n")
    for git_arguments in (["init", "-q"], ["add", "-A"],
                          ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "a"]):
        subprocess.run(["git", "-C", str(repository), *git_arguments],
                       capture_output=True, check=True)
    return repository


def patch_file(scratch, repository, name, old, new, path="doubling.py"):
    """A patch made by editing the file, diffing, and putting the file back."""
    target = repository / path
    original = target.read_bytes()
    target.write_bytes(original.replace(old.encode(), new.encode()))
    diff = subprocess.run(["git", "-C", str(repository), "diff"], capture_output=True,
                          check=True).stdout
    target.write_bytes(original)
    patch = scratch / name
    patch.write_bytes(diff)
    return patch


def run_program(scratch, repository, *arguments, environment=None):
    completed = subprocess.run(
        [sys.executable, str(PROGRAM_PATH), *arguments, "--checkout", str(repository),
         "--lock-file", str(scratch / "run.lock")],
        capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120, check=False,
        env=environment)
    lines = completed.stdout.strip().splitlines()
    return completed, (lines[-1] if lines else "")


def unchanged(repository):
    return (repository / "doubling.py").read_bytes() == MODULE_SOURCE.encode() and \
        subprocess.run(["git", "-C", str(repository), "status", "--porcelain"],
                       capture_output=True, text=True, check=True).stdout == ""


def kept(repository, data, path="doubling.py"):
    """A KeptOriginal of data with the file's current mode and times."""
    status = (repository / path).stat()
    return program.KeptOriginal(data, status.st_mode & 0o7777,
                                (status.st_atime_ns, status.st_mtime_ns))


def cached_bytecode_of_mutant(repository):
    """Return the cached bytecode files beside doubling.py whose unused() returns 2."""
    found = []
    for cached in (repository / "__pycache__").glob("doubling.*.pyc"):
        code = marshal.loads(cached.read_bytes()[16:])
        for constant in code.co_consts:
            if getattr(constant, "co_name", None) == "unused" and 2 in constant.co_consts:
                found.append(cached.name)
    return found


def bwrap_usable():
    if os.environ.get("RUN_ALL_TEST_SUITES_INSIDE_SIGNAL_SANDBOX"):
        return program.pid_one_is_bwrap()
    try:
        prefix, why = program.runner.signal_sandbox()
    except program.runner.SignalSandboxCouldNotStart:
        return False
    return bool(prefix)


# --- Verdicts, without running anything ---------------------------------------

check("a passing suite without a mutant is 'suite passed', exit 0",
      program.verdict(0, mutant=False) == ("VERDICT: suite passed", 0))
line, code = program.verdict(3, mutant=False)
check("a failing suite without a mutant is 'suite failed' naming the exit, exit 1",
      line.startswith("VERDICT: suite failed") and "exit 3" in line and code == 1, line)
line, code = program.verdict(0, mutant=True)
check("a suite that passes with the mutant in is 'mutant survived', exit 1",
      line.startswith("VERDICT: mutant survived") and code == 1, line)
line, code = program.verdict(-signal.SIGTERM, mutant=True)
check("a suite killed by a signal with the mutant in is 'mutant killed' naming the signal, exit 0",
      line.startswith("VERDICT: mutant killed") and "SIGTERM" in line and code == 0, line)

# --- Process 1 check ----------------------------------------------------------

with tempfile.TemporaryDirectory() as scratch_name:
    scratch = pathlib.Path(scratch_name)
    (scratch / "bwrap-comm").write_text("bwrap\n")
    (scratch / "init-comm").write_text("systemd\n")
    check("process 1 named bwrap passes the check",
          program.pid_one_is_bwrap(scratch / "bwrap-comm"))
    check("process 1 named anything else fails the check",
          not program.pid_one_is_bwrap(scratch / "init-comm"))
    check("an unreadable process 1 fails the check",
          not program.pid_one_is_bwrap(scratch / "missing"))

    # The inside check, run outside any sandbox, must refuse and leave the proof empty.
    if not sys.platform.startswith("linux"):
        print("SKIP  the inside check's process-1 refusals: they read /proc/1/comm, "
              "which only Linux has")
    elif not program.pid_one_is_bwrap():
        proof = scratch / "proof"
        proof.write_text("")
        ran_marker = scratch / "ran"
        completed = subprocess.run(
            [sys.executable, str(PROGRAM_PATH), program.INSIDE_CHECK_OPTION, str(proof), "--",
             "touch", str(ran_marker)], capture_output=True, text=True, check=False)
        check("outside a sandbox, the inside check refuses: no proof, the command not started",
              completed.returncode == program.EXIT_NOT_RUN and proof.read_text() == ""
              and not ran_marker.exists() and "not bwrap" in completed.stderr,
              (completed.returncode, completed.stderr))
    else:
        environment = {name: value for name, value in os.environ.items()
                       if name != "RUN_ALL_TEST_SUITES_INSIDE_SIGNAL_SANDBOX"}
        proof = scratch / "proof"
        proof.write_text("")
        ran_marker = scratch / "ran"
        completed = subprocess.run(
            [sys.executable, str(PROGRAM_PATH), program.INSIDE_CHECK_OPTION, str(proof), "--",
             "touch", str(ran_marker)], capture_output=True, text=True, check=False,
            env=environment)
        check("without the inside variable, the inside check refuses: no proof, not started",
              completed.returncode == program.EXIT_NOT_RUN and proof.read_text() == ""
              and not ran_marker.exists(), (completed.returncode, completed.stderr))

    def inside_check_in_child(proof, marker, platform, setup="", environment=None):
        """Run the inside check for `platform` in a child, because a passing check execs."""
        proof.write_text("")
        return subprocess.run(
            [sys.executable, "-c",
             "import importlib.util, pathlib, sys\n"
             f"spec = importlib.util.spec_from_file_location('p', {str(PROGRAM_PATH)!r})\n"
             "program = importlib.util.module_from_spec(spec)\n"
             "spec.loader.exec_module(program)\n"
             + setup +
             f"sys.exit(program.inside_check_then_exec(sys.argv[1], sys.argv[2:], "
             f"platform={platform!r}))\n",
             str(proof), "touch", str(marker)],
            capture_output=True, text=True, check=False,
            env={**os.environ, "RUN_ALL_TEST_SUITES_INSIDE_SIGNAL_SANDBOX": "1",
                 **(environment or {})})

    # Process 1 not bwrap and the inside variable leaked in: the suite must not start.
    leaked_marker = scratch / "ran-with-leaked-variable"
    completed = inside_check_in_child(
        scratch / "proof-leaked", leaked_marker, "linux",
        setup=f"program.PID_ONE_COMMAND_FILE = pathlib.Path({str(scratch / 'init-comm')!r})\n")
    check("with the inside variable leaked in but process 1 not bwrap, the inside check "
          "refuses: no proof, the command not started",
          completed.returncode == program.EXIT_NOT_RUN
          and (scratch / "proof-leaked").read_text() == "" and not leaked_marker.exists()
          and "not bwrap" in completed.stderr, (completed.returncode, completed.stderr))

    # The macOS check, run without any sandbox: its signal to the outside process, this
    # file, gets through (SIGWINCH, which this file ignores), so the suite must not start.
    unconfined_marker = scratch / "ran-unconfined-on-macos-check"
    completed = inside_check_in_child(
        scratch / "proof-macos-unconfined", unconfined_marker, "darwin",
        environment={program.runner.SIGNAL_SANDBOX_TRIAL_SIGNAL_TARGET_PROCESS_VARIABLE: str(os.getpid())})
    check("the macOS inside check, unconfined, refuses: its signal out was let through, "
          "no proof, the command not started",
          completed.returncode == program.EXIT_NOT_RUN
          and (scratch / "proof-macos-unconfined").read_text() == ""
          and not unconfined_marker.exists() and "was let through" in completed.stderr,
          (completed.returncode, completed.stderr))
    # The same check with the signal refused, as inside sandbox-exec: proof, then the command.
    confined_marker = scratch / "ran-confined-on-macos-check"
    completed = inside_check_in_child(
        scratch / "proof-macos-confined", confined_marker, "darwin",
        setup="program.outside_signal_refusal_failure = lambda: None\n")
    check("the macOS inside check, its signal out refused, writes its proof and starts the "
          "command",
          completed.returncode == 0 and confined_marker.exists()
          and (scratch / "proof-macos-confined").read_text().strip()
          == program.OUTSIDE_SIGNAL_REFUSED_PROOF, (completed.returncode, completed.stderr))
    check("the proof a run expects is the process-1 proof on Linux and the refused-signal "
          "proof on macOS",
          program.expected_proof("linux") == program.PID_ONE_PROOF
          and program.expected_proof("darwin") == program.OUTSIDE_SIGNAL_REFUSED_PROOF)

    variable = program.runner.SIGNAL_SANDBOX_TRIAL_SIGNAL_TARGET_PROCESS_VARIABLE
    signalled = []

    def refusing_kill(pid, number):
        signalled.append((pid, number))
        raise PermissionError(1, "Operation not permitted")

    def lookup_failing_kill(pid, number):
        raise ProcessLookupError(3, "No such process")

    check("the macOS check passes when its signal to the outside process is refused, "
          "and sends that process SIGWINCH",
          program.outside_signal_refusal_failure({variable: "4242"}, kill=refusing_kill) is None
          and signalled == [(4242, signal.SIGWINCH)], signalled)
    for case_name, environment, kill, expected in (
            ("the macOS check fails when the signal is let through",
             {variable: "4242"}, lambda pid, number: None, "was let through"),
            ("the macOS check fails when the outside process is gone: that is not a refusal",
             {variable: "4242"}, lookup_failing_kill, "not a refusal"),
            ("the macOS check fails when no outside process is named",
             {}, refusing_kill, "does not name a process"),
            ("the macOS check fails when the outside process named is process 1",
             {variable: "1"}, refusing_kill, "not a process this program started")):
        why_not = program.outside_signal_refusal_failure(environment, kill=kill)
        check(case_name, why_not is not None and expected in why_not, why_not)

# --- Stopping a suite's leftovers by process group, as on macOS -------------------

def process_alive(pid):
    try:
        state = pathlib.Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (OSError, IndexError):
        return False
    return state != "Z"


if not sys.platform.startswith("linux"):
    print("SKIP  the process-group stop case: it checks that the leftover is gone through "
          "/proc, which only Linux has")
else:
    with tempfile.TemporaryDirectory() as scratch_name:
        leftover_file = pathlib.Path(scratch_name) / "leftover-pid"
        # The leader starts a sleeper in its own process group, records it, and exits 5.
        leader = subprocess.Popen(
            [sys.executable, "-c",
             "import subprocess, sys\n"
             "sleeper = subprocess.Popen(['sleep', '60'])\n"
             f"open({str(leftover_file)!r}, 'w').write(str(sleeper.pid))\n"
             "sys.exit(5)\n"],
            start_new_session=True, stdin=subprocess.DEVNULL)
        try:
            program.wait_without_reaping(leader)
            leader_unreaped = leader.returncode is None
            leftover = int(leftover_file.read_text())
            leftover_alive_before = process_alive(leftover)
            program.stop_process_group_then_reap(leader)
            deadline = time.monotonic() + 5
            while process_alive(leftover) and time.monotonic() < deadline:
                time.sleep(0.05)
            check("after the suite's leader exits, it is left unreaped until its process "
                  "group is stopped, then the leftover in the group is killed and the leader's "
                  "own exit is kept",
                  leader_unreaped and leftover_alive_before and not process_alive(leftover)
                  and leader.returncode == 5,
                  (leader_unreaped, leftover_alive_before, leader.returncode))
        finally:
            if leader.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(leader.pid, signal.SIGKILL)
                leader.wait()

class FakeLeader:
    """Stands in for the suite's unreaped leader: records whether it was reaped."""
    pid = 4242

    def __init__(self):
        self.reaped = False

    def wait(self):
        self.reaped = True


def killpg_refused_as_on_macos(group_id, number):
    raise PermissionError(1, "Operation not permitted")


original_killpg = program.os.killpg
program.os.killpg = killpg_refused_as_on_macos
try:
    leader = FakeLeader()
    try:
        program.stop_process_group_then_reap(leader, members_other_than_leader=lambda group: [])
        raised = None
    except Exception as error:  # noqa: BLE001 - any escape is the failure checked here
        raised = error
    check("when macOS refuses the group signal because only the zombie leader is left, "
          "nothing is reported and the leader is reaped",
          raised is None and leader.reaped, repr(raised))
    leader = FakeLeader()
    try:
        program.stop_process_group_then_reap(leader, members_other_than_leader=lambda group: [977])
        error_text = None
    except program.NotRun as error:
        error_text = str(error)
    check("when the group signal is refused while another process is still in the group, "
          "the run is NotRun naming it, and the leader is still reaped",
          error_text is not None and "977" in error_text and leader.reaped, error_text)
finally:
    program.os.killpg = original_killpg


def pgrep_answering(returncode, stdout, stderr=""):
    def run(command, **keywords):
        return subprocess.CompletedProcess(command, returncode, stdout, stderr)
    return run


check("pgrep -g listing only the leader means no other process is in the group",
      program.process_group_members_other_than_leader(
          4242, run=pgrep_answering(0, "4242\n")) == [])
check("pgrep -g exiting 1 with nothing listed means no other process is in the group",
      program.process_group_members_other_than_leader(4242, run=pgrep_answering(1, "")) == [])
check("pgrep -g listing another process returns it",
      program.process_group_members_other_than_leader(
          4242, run=pgrep_answering(0, "4242\n977\n")) == [977])
try:
    program.process_group_members_other_than_leader(4242, run=pgrep_answering(2, "", "bad"))
    pgrep_failure_refused = False
except program.NotRun:
    pgrep_failure_refused = True
check("a pgrep that fails is reported, not read as an empty group", pgrep_failure_refused)

# run_suite_confined on macOS must stop leftovers by process group, never through /proc.
with tempfile.TemporaryDirectory() as scratch_name:
    scratch = pathlib.Path(scratch_name)
    (scratch / "quiet-test.py").write_text("pass\n")
    stops = []
    original_group_stop = program.stop_process_group_then_reap
    original_descendants_stop = program.stop_descendants
    program.stop_process_group_then_reap = lambda process: (stops.append("group"),
                                                            process.wait())
    program.stop_descendants = lambda: stops.append("descendants")
    try:
        for platform_name in ("darwin", "linux"):
            stops.clear()
            try:
                program.run_suite_confined(
                    scratch, "quiet-test.py", sys.executable,
                    ("env", "RUN_ALL_TEST_SUITES_INSIDE_SIGNAL_SANDBOX="), scratch / "proof",
                    platform=platform_name)
            except program.NotRun:
                pass
            expected = ["group"] if platform_name == "darwin" else ["descendants"]
            check(f"run_suite_confined on {platform_name} stops leftovers by "
                  f"{expected[0]}", stops == expected, stops)
    finally:
        program.stop_process_group_then_reap = original_group_stop
        program.stop_descendants = original_descendants_stop

# --- Interruption handling ------------------------------------------------------

program.install_interruption_handlers()
try:
    try:
        os.kill(os.getpid(), signal.SIGTERM)
        first_raised = False
    except program.Terminated:
        first_raised = True
    try:
        os.kill(os.getpid(), signal.SIGTERM)
        os.kill(os.getpid(), signal.SIGHUP)
        second_raised = False
    except program.Terminated:
        second_raised = True
finally:
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    signal.signal(signal.SIGHUP, signal.SIG_DFL)
    signal.signal(signal.SIGINT, signal.default_int_handler)
check("the first SIGTERM raises Terminated and a later one does not, so it cannot abort "
      "the restore the first one started", first_raised and not second_raised,
      (first_raised, second_raised))

# --- Suite paths ----------------------------------------------------------------

with tempfile.TemporaryDirectory() as scratch_name:
    top = pathlib.Path(scratch_name).resolve()
    check("a ./ spelling of a suite is normalized to its path from the top",
          program.suite_relative_to_top("./scripts/a-test.py", top) == "scripts/a-test.py")
    check("an absolute path inside the checkout becomes its path from the top",
          program.suite_relative_to_top(str(top / "scripts" / "a-test.py"), top)
          == "scripts/a-test.py")
    for outside in ("../a-test.py", "/elsewhere/a-test.py"):
        try:
            program.suite_relative_to_top(outside, top)
            refused = False
        except program.NotRun:
            refused = True
        check(f"a suite path outside the checkout is refused: {outside}", refused)

# --- Refusals that run nothing ------------------------------------------------

with tempfile.TemporaryDirectory() as scratch_name:
    scratch = pathlib.Path(scratch_name)
    repository = scratch_checkout(scratch)
    def main_with_nothing_run(platform, sandbox=None, mutant=None, sandbox_function=None):
        """Run main in this process with the suite run replaced; return (exit, output, runs).

        Each run is recorded as (top, suite, interpreter, prefix, proof, platform).
        """
        ran = []
        original_run, original_sandbox = program.run_suite_confined, program.runner.signal_sandbox
        original_become_subreaper = program.become_child_subreaper

        def record_run(top, suite, interpreter, prefix, proof, bytecode_dir=None, platform=None):
            ran.append((top, suite, interpreter, prefix, proof, platform))
            return 0

        def become_child_subreaper_as_on_this_platform():
            subreaper_calls.append(platform)
            if platform == "darwin":
                raise AttributeError("macOS's libc has no prctl")

        program.run_suite_confined = record_run
        program.become_child_subreaper = become_child_subreaper_as_on_this_platform
        if sandbox is not None:
            program.runner.signal_sandbox = lambda platform=None: sandbox
        if sandbox_function is not None:
            program.runner.signal_sandbox = sandbox_function
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                code = program.main(["doubling-test.py", "--checkout", str(repository),
                                     "--lock-file", str(scratch / "run.lock")]
                                    + (["--mutant", mutant] if mutant else []),
                                    platform=platform)
        finally:
            program.run_suite_confined = original_run
            program.runner.signal_sandbox = original_sandbox
            program.become_child_subreaper = original_become_subreaper
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
            signal.signal(signal.SIGHUP, signal.SIG_DFL)
            signal.signal(signal.SIGINT, signal.default_int_handler)
        return code, output.getvalue(), ran

    subreaper_calls = []
    code, output, ran = main_with_nothing_run("freebsd14")
    check("on a platform other than Linux and macOS, nothing runs and the exit is 2",
          code == program.EXIT_NOT_RUN and ran == [] and "only on Linux and macOS" in output,
          (code, output, ran))
    macos_prefix = ("/usr/bin/sandbox-exec", "-p", program.runner.SIGNAL_SANDBOX_MACOS_PROFILE)
    code, output, ran = main_with_nothing_run("darwin", sandbox=(macos_prefix, None))
    check("on macOS with the sandbox, the suite runs under the sandbox-exec prefix, "
          "told it is on macOS",
          code == program.EXIT_PASSED_OR_KILLED and len(ran) == 1
          and ran[0][3] == macos_prefix and ran[0][5] == "darwin",
          (code, output, ran))
    check("on macOS, the program never tries to become the child subreaper, which "
          "needs Linux's prctl", "darwin" not in subreaper_calls, subreaper_calls)
    code, output, ran = main_with_nothing_run("darwin", sandbox=((), None))
    check("on macOS inside a sandbox already, no second sandbox-exec is started: the suite "
          "runs with no prefix, and the inside check still proves the inherited sandbox",
          code == program.EXIT_PASSED_OR_KILLED and len(ran) == 1 and ran[0][3] == ()
          and ran[0][5] == "darwin", (code, output, ran))
    bwrap_prefix = ("/usr/bin/bwrap",)
    code, output, ran = main_with_nothing_run("linux", sandbox=(bwrap_prefix, None))
    check("on Linux, the program becomes the child subreaper before the suite runs",
          code == program.EXIT_PASSED_OR_KILLED and "linux" in subreaper_calls,
          (code, output, subreaper_calls))

    def sandbox_exec_missing(platform=None):
        raise program.runner.SignalSandboxCouldNotStart("/usr/bin/sandbox-exec is not on this Mac")

    code, output, ran = main_with_nothing_run("darwin", sandbox_function=sandbox_exec_missing)
    check("on macOS without sandbox-exec, the suite is not run unconfined: exit 2 naming it",
          code == program.EXIT_NOT_RUN and ran == []
          and "/usr/bin/sandbox-exec is not on this Mac" in output, (code, output, ran))
    code, output, ran = main_with_nothing_run(
        "linux", sandbox=((), "bwrap is not on PATH (Ubuntu: sudo apt install bubblewrap)"))
    check("on Linux without bwrap, the suite is not run unconfined: exit 2 naming bwrap",
          code == program.EXIT_NOT_RUN and ran == [] and "bwrap is not on PATH" in output,
          (code, output, ran))

    if not sys.platform.startswith("linux"):
        print("SKIP  the cases that run the inside check through run_suite_confined: "
              "it stops the suite's leftover processes through /proc, which only Linux has")
    else:
        # A sandbox in which the inside check refuses: the suite must not start, and the
        # program must not report the suite's verdict.
        proof = scratch / "proof"
        proof.write_text("")
        marker_suite = repository / "marks-test.py"
        ran_marker = scratch / "marker-suite-ran"
        marker_suite.write_text(f"open({str(ran_marker)!r}, 'w').write('ran')\n")
        try:
            program.run_suite_confined(repository, "marks-test.py", sys.executable,
                                       ("env", "RUN_ALL_TEST_SUITES_INSIDE_SIGNAL_SANDBOX="), proof)
        except program.NotRun as error:
            check("when the check inside the sandbox refuses, the run is NotRun and the suite "
                  "never starts", not ran_marker.exists() and "did not confirm" in str(error),
                  str(error))
        else:
            check("when the check inside the sandbox refuses, the run is NotRun and the suite "
                  "never starts", False, "no exception")
        proof.write_text(program.PID_ONE_PROOF + "\n")
        try:
            program.run_suite_confined(repository, "marks-test.py", sys.executable,
                                       ("env", "RUN_ALL_TEST_SUITES_INSIDE_SIGNAL_SANDBOX="), proof)
            stale_proof_refused = False
        except program.NotRun:
            stale_proof_refused = True
        check("a proof an earlier run left does not vouch for a run whose check refuses",
              stale_proof_refused and not ran_marker.exists())
        marker_suite.unlink()

    outside_suite = next(iter(program.runner.SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX))
    (repository / outside_suite).parent.mkdir(parents=True, exist_ok=True)
    (repository / outside_suite).write_text("print('ran')\n")
    completed, last = run_program(scratch, repository, outside_suite)
    check("a suite listed to run outside the sandbox is refused, exit 2",
          completed.returncode == 2 and "cannot run inside the signal sandbox" in last,
          (completed.returncode, last))
    completed, last = run_program(scratch, repository, "./" + outside_suite)
    check("a suite listed to run outside the sandbox is refused when spelled with ./, exit 2",
          completed.returncode == 2 and "cannot run inside the signal sandbox" in last,
          (completed.returncode, last))

    completed, last = run_program(scratch, repository, "no-such-test.py")
    check("a suite that is not a file is refused, exit 2",
          completed.returncode == 2 and last.startswith("VERDICT: not run"), last)

    completed, last = run_program(scratch, repository, "doubling-test.py", "--mutant",
                                  str(scratch / "no-such.patch"))
    check("a mutant that is not a file is refused, exit 2",
          completed.returncode == 2 and "not a file" in last, last)

    code, output, ran = main_with_nothing_run("darwin", mutant=str(scratch / "no-such.patch"))
    check("on a platform other than Linux, a bad argument is named before the platform",
          code == program.EXIT_NOT_RUN and ran == [] and "not a file" in output,
          (code, output, ran))

if not sys.platform.startswith("linux") or not bwrap_usable():
    print("SKIP  the cases that run a suite: no usable bwrap here")
else:
    # --- Runs without a mutant ------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        scratch = pathlib.Path(scratch_name)
        repository = scratch_checkout(scratch)

        completed, last = run_program(scratch, repository, "doubling-test.py")
        check("a passing suite is 'suite passed', exit 0, its output shown",
              completed.returncode == 0 and last == "VERDICT: suite passed"
              and "all cases passed" in completed.stdout, (completed.returncode, completed.stdout))

        completed, last = run_program(scratch, repository, "fails-test.sh")
        check("a failing shell suite is 'suite failed' with its exit code, exit 1",
              completed.returncode == 1 and last.startswith("VERDICT: suite failed")
              and "exit 7" in last and "failing" in completed.stdout,
              (completed.returncode, completed.stdout))

        completed, last = run_program(scratch, repository, "pid-one-test.py")
        check("the suite runs with process 1 bwrap and the inside variable set to 1",
              completed.returncode == 0 and "pid one: bwrap" in completed.stdout
              and "inside variable: 1" in completed.stdout, completed.stdout)

        # --- Mutants ---------------------------------------------------------
        # The suite has run once, so bytecode of the original sits in __pycache__ with the
        # mutant's size; the mutant must still be what runs, and the original afterwards.
        killing = patch_file(scratch, repository, "kills.patch", "number * 2", "number * 3")
        completed, last = run_program(scratch, repository, "doubling-test.py",
                                      "--mutant", str(killing))
        check("a mutant the suite catches is 'mutant killed', exit 0",
              completed.returncode == 0 and last.startswith("VERDICT: mutant killed")
              and "FAIL: double(3)" in completed.stdout, (completed.returncode, completed.stdout))
        check("after a killed mutant, the mutated file is back byte for byte",
              unchanged(repository), (repository / "doubling.py").read_text())

        surviving = patch_file(scratch, repository, "survives.patch", "return 1", "return 2")
        completed, last = run_program(scratch, repository, "doubling-test.py",
                                      "--mutant", str(surviving))
        check("a mutant the suite misses is 'mutant survived', exit 1",
              completed.returncode == 1 and last.startswith("VERDICT: mutant survived"),
              (completed.returncode, completed.stdout))
        check("after a surviving mutant, the mutated file is back byte for byte",
              unchanged(repository), (repository / "doubling.py").read_text())

        # A suite that fails without the mutant cannot show that the mutant was caught.
        completed, last = run_program(scratch, repository, "fails-without-mutant-test.py",
                                      "--mutant", str(surviving))
        check("a suite that fails without the mutant is 'not run', exit 2, the mutant not applied",
              completed.returncode == 2 and "fails without the mutant" in last
              and "mutant applied" not in completed.stdout and unchanged(repository),
              (completed.returncode, completed.stdout))

        # A child that drops the environment reads and writes bytecode beside the source.
        # Bytecode of the original written in the mutant's second would run during the
        # mutant run; an unchecked hash-based .pyc stands in for it, since Python runs one
        # whatever the source holds.
        py_compile.compile(str(repository / "doubling.py"),
                           cfile=str(repository / "__pycache__" /
                                     f"doubling.{sys.implementation.cache_tag}.pyc"),
                           invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
        completed, last = run_program(scratch, repository, "child-drops-environment-test.py",
                                      "--mutant", str(surviving))
        fresh_import = subprocess.run(
            [sys.executable, "-I", "-c",
             "import sys; sys.path.insert(0, '.'); import doubling; print(doubling.unused())"],
            cwd=str(repository), capture_output=True, text=True, check=False)
        check("after a mutant run whose suite's child cached bytecode beside the source, no "
              "bytecode of the mutant is left and a fresh import runs the original",
              completed.returncode == 0 and last.startswith("VERDICT: mutant killed")
              and cached_bytecode_of_mutant(repository) == []
              and fresh_import.stdout.strip() == "1" and unchanged(repository),
              (completed.returncode, completed.stdout, cached_bytecode_of_mutant(repository),
               fresh_import.stdout))
        # With the original's write long past, the child caches the mutant's bytecode.
        os.utime(repository / "doubling.py", ns=(1_000_000_000_000_000_000,
                                                 1_000_000_000_000_000_000))
        completed, last = run_program(scratch, repository, "child-drops-environment-test.py",
                                      "--mutant", str(surviving))
        check("after a mutant run whose suite's child cached the mutant's bytecode beside the "
              "source, that bytecode is deleted",
              completed.returncode == 0 and last.startswith("VERDICT: mutant killed")
              and cached_bytecode_of_mutant(repository) == [] and unchanged(repository),
              (completed.returncode, completed.stdout, cached_bytecode_of_mutant(repository)))

        # Mode and modification time come back with the bytes.
        os.chmod(repository / "doubling.py", 0o600)
        os.utime(repository / "doubling.py", ns=(1_000_000_000_000_000_000,
                                                 1_000_000_000_000_000_000))
        completed, last = run_program(scratch, repository, "doubling-test.py",
                                      "--mutant", str(killing))
        status = (repository / "doubling.py").stat()
        check("after a mutant run, the file's mode and modification time are back too",
              completed.returncode == 0 and status.st_mode & 0o7777 == 0o600
              and status.st_mtime_ns == 1_000_000_000_000_000_000 and unchanged(repository),
              (completed.returncode, oct(status.st_mode), status.st_mtime_ns))
        os.chmod(repository / "doubling.py", 0o644)

        # A mutant whose file has uncommitted edits: those edits come back too.
        edited = MODULE_SOURCE + "# uncommitted edit\n"
        (repository / "doubling.py").write_text(edited)
        completed, last = run_program(scratch, repository, "doubling-test.py",
                                      "--mutant", str(killing))
        check("a mutant applies over uncommitted edits and the edits are back afterwards",
              completed.returncode == 0 and last.startswith("VERDICT: mutant killed")
              and (repository / "doubling.py").read_text() == edited,
              (completed.returncode, completed.stdout))
        (repository / "doubling.py").write_bytes(MODULE_SOURCE.encode())

        stale = patch_file(scratch, repository, "stale.patch", "number * 2", "number * 3")
        (repository / "doubling.py").write_text("def double(number):\n    return number + number\n")
        completed, last = run_program(scratch, repository, "doubling-test.py",
                                      "--mutant", str(stale))
        check("a mutant that does not apply is refused, exit 2, and the suite does not run",
              completed.returncode == 2 and "does not apply" in last
              and "all cases passed" not in completed.stdout,
              (completed.returncode, completed.stdout))
        (repository / "doubling.py").write_bytes(MODULE_SOURCE.encode())

        new_file_patch = scratch / "new-file.patch"
        (repository / "added.py").write_text("x = 1\n")
        subprocess.run(["git", "-C", str(repository), "add", "-N", "added.py"], check=True)
        new_file_patch.write_bytes(subprocess.run(
            ["git", "-C", str(repository), "diff"], capture_output=True, check=True).stdout)
        subprocess.run(["git", "-C", str(repository), "rm", "-q", "--cached", "added.py"],
                       check=True)
        (repository / "added.py").unlink()
        completed, last = run_program(scratch, repository, "doubling-test.py",
                                      "--mutant", str(new_file_patch))
        check("a mutant that creates a file is refused, exit 2, nothing created",
              completed.returncode == 2 and "creates, deletes" in last
              and not (repository / "added.py").exists(), (completed.returncode, last))

        # --- The program is terminated while the mutant is in -----------------
        terminating = patch_file(scratch, repository, "terminating.patch", "return 1",
                                 "return 5")
        process = subprocess.Popen(
            [sys.executable, str(PROGRAM_PATH), "terminates-test.py", "--mutant",
             str(terminating), "--checkout", str(repository),
             "--lock-file", str(scratch / "run.lock")],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            stdin=subprocess.DEVNULL)
        seen = []
        for output_line in process.stdout:
            seen.append(output_line)
            if "suite started" in output_line:
                process.send_signal(signal.SIGTERM)
                break
        stdout, stderr = process.communicate(timeout=120)
        stdout = "".join(seen) + stdout
        last = stdout.strip().splitlines()[-1] if stdout.strip() else ""
        check("terminated with the mutant in, the program puts the file back and says not run",
              process.returncode == 2 and "interrupted" in last and unchanged(repository),
              (process.returncode, stdout, stderr, (repository / "doubling.py").read_text()))

        # --- An interrupted run leaves no process of the suite running ---------
        heartbeat = scratch / "heartbeat"
        (repository / "heartbeat-child.py").write_text(
            "import sys, time\n"
            "while True:\n"
            "    with open(sys.argv[1], 'w') as beat:\n"
            "        beat.write(repr(time.time()))\n"
            "    time.sleep(0.1)\n")
        (repository / "spawns-test.py").write_text(
            "import os, subprocess, sys, time\n"
            f"heartbeat = {str(heartbeat)!r}\n"
            "subprocess.Popen([sys.executable, 'heartbeat-child.py', heartbeat],\n"
            "                 start_new_session=True)\n"
            "while not os.path.exists(heartbeat):\n"
            "    time.sleep(0.05)\n"
            "print('suite started', flush=True)\n"
            "time.sleep(60)\n")
        process = subprocess.Popen(
            [sys.executable, str(PROGRAM_PATH), "spawns-test.py", "--checkout", str(repository),
             "--lock-file", str(scratch / "run.lock")],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            stdin=subprocess.DEVNULL)
        for output_line in process.stdout:
            if "suite started" in output_line:
                process.send_signal(signal.SIGTERM)
                break
        try:
            # A process left running keeps the output pipe open, and this waits for it.
            process.communicate(timeout=30)
            exited = True
        except subprocess.TimeoutExpired:
            process.kill()
            exited = False
        time.sleep(0.5)
        beat_after_exit = heartbeat.read_text()
        time.sleep(1.0)
        check("terminated, the program leaves no process the suite started running, even one "
              "in a session of its own", exited and heartbeat.read_text() == beat_after_exit
              and process.returncode == 2, (exited, process.returncode, beat_after_exit))
        (repository / "spawns-test.py").unlink()
        (repository / "heartbeat-child.py").unlink()

        # --- Restore failure is reported, not hidden --------------------------
        keep = scratch / "keep"
        keep.mkdir()
        (repository / "doubling.py").write_text("mutated\n")
        original_write_back = program.write_back
        program.write_back = lambda top, originals: ["doubling.py (read back differs)"]
        try:
            program.restore_originals(repository, {"doubling.py": kept(repository, MODULE_SOURCE.encode())}, keep)
        except program.RestoreFailed as error:
            check("a file that does not read back as its original is RestoreFailed naming "
                  "the file and where its original is kept",
                  "doubling.py" in str(error) and str(keep) in str(error), str(error))
        else:
            check("a file that does not read back as its original is RestoreFailed naming "
                  "the file and where its original is kept", False, "no exception")
        finally:
            program.write_back = original_write_back
        failed = program.write_back(repository,
                                    {"doubling.py": kept(repository, MODULE_SOURCE.encode())})
        check("write_back puts the bytes back and reports nothing when they read back",
              failed == [] and unchanged(repository), failed)
        failed = program.write_back(repository, {"no-dir/x.py": program.KeptOriginal(
            b"x", 0o644, (0, 0))})
        check("write_back reports a file it cannot write", failed and "no-dir/x.py" in failed[0],
              failed)
        original_read_bytes = pathlib.Path.read_bytes
        doubling_kept = kept(repository, MODULE_SOURCE.encode())
        pathlib.Path.read_bytes = lambda self: b"something else"
        try:
            failed = program.write_back(repository, {"doubling.py": doubling_kept})
        finally:
            pathlib.Path.read_bytes = original_read_bytes
        check("write_back reports a file that does not read back as written",
              failed == ["doubling.py (read back differs)"], failed)

        original_chmod = program.os.chmod
        program.os.chmod = lambda *arguments, **options: None
        try:
            failed = program.write_back(repository, {"doubling.py": program.KeptOriginal(
                MODULE_SOURCE.encode(), 0o600, (0, 0))})
        finally:
            program.os.chmod = original_chmod
        check("write_back reports a file whose mode does not read back as the original's",
              len(failed) == 1 and "doubling.py (mode" in failed[0], failed)

        # SIGTERM during the restore waits until every file is written.
        written = []

        def write_back_terminated_half_way(top, originals):
            os.kill(os.getpid(), signal.SIGTERM)
            written.append("all files")
            return []

        original_write_back = program.write_back
        program.write_back = write_back_terminated_half_way
        signal.signal(signal.SIGTERM, program.raise_terminated)
        try:
            program.restore_originals(repository,
                                      {"doubling.py": kept(repository, MODULE_SOURCE.encode())},
                                      keep)
            terminated = False
        except program.Terminated:
            terminated = True
        finally:
            program.write_back = original_write_back
            for restored in program.INTERRUPTING_SIGNALS:
                signal.signal(restored, signal.SIG_DFL)
            signal.signal(signal.SIGINT, signal.default_int_handler)
        check("a SIGTERM that arrives during the restore takes effect only after every file "
              "is written", terminated and written == ["all files"], (terminated, written))

        # A restore that fails while a SIGTERM is pending is reported as a failed restore.
        def write_back_fails_and_terminated(top, originals):
            os.kill(os.getpid(), signal.SIGTERM)
            return ["doubling.py (read back differs)"]

        program.write_back = write_back_fails_and_terminated
        signal.signal(signal.SIGTERM, program.raise_terminated)
        try:
            program.restore_originals(repository,
                                      {"doubling.py": kept(repository, MODULE_SOURCE.encode())},
                                      keep)
            outcome = "no exception"
        except program.RestoreFailed as error:
            outcome = f"RestoreFailed: {error}"
        except program.Terminated as error:
            outcome = f"Terminated: {error}"
        finally:
            program.write_back = original_write_back
            for restored in program.INTERRUPTING_SIGNALS:
                signal.signal(restored, signal.SIG_DFL)
            signal.signal(signal.SIGINT, signal.default_int_handler)
        check("a restore that fails while a SIGTERM is pending is RestoreFailed, not an "
              "interruption", outcome.startswith("RestoreFailed") and "doubling.py" in outcome
              and "SIGTERM" in outcome, outcome)

        # --- The lock ---------------------------------------------------------
        lock_path = scratch / "run.lock"
        with open(lock_path, "a+") as holder:
            fcntl.flock(holder.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            holder.truncate(0)
            holder.write("pid 1, checkout elsewhere, started then\n")
            holder.flush()
            completed, last = run_program(scratch, repository, "doubling-test.py",
                                          "--mutant", str(killing))
        check("while another run holds the lock, nothing runs, nothing is mutated, exit 3",
              completed.returncode == 3 and "lock held" in last and "checkout elsewhere" in last
              and "all cases passed" not in completed.stdout and unchanged(repository),
              (completed.returncode, completed.stdout))

        # A killed run of scripts/run-all-test-suites.py left traces; its run record
        # shows nothing of it still runs, so this program removes them as that runner would.
        left_trace = scratch / "killed-run-logs" / "recorded-inputs" / "a-test.py.strace"
        left_trace.mkdir(parents=True)
        lock_path.write_text(f"pid 1, checkout elsewhere, started then, logs in "
                             f"{scratch / 'killed-run-logs'}\n")
        # Started to sleep, so its start ticks are read while it still runs.
        ended = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        ended_ticks = program.runner.process_start_ticks(ended.pid)
        ended.terminate()
        ended.wait()
        runs = program.runner.run_records_directory_for_lock_file(lock_path)
        runs.mkdir(parents=True, exist_ok=True)
        (runs / f"{ended.pid}-{ended_ticks}.json").write_text(json.dumps({
            "runner": {"pid": ended.pid, "start_ticks": ended_ticks},
            "log_dir": str(scratch / "killed-run-logs"), "log_dir_is_temporary": False,
            "started": "then", "finished": None, "suite_processes": []}))
        completed, last = run_program(scratch, repository, "doubling-test.py")
        check("the strace directories a killed run left are removed once its record shows "
              "it ended",
              completed.returncode == 0 and not left_trace.exists(),
              (completed.returncode, last, left_trace.exists()))

print()
print(f"{cases_run} cases run")
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
