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
import importlib.util
import os
import pathlib
import signal
import subprocess
import sys
import tempfile

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
# Runs long enough for the case to terminate the program while the mutant is in.
TERMINATES_THE_PROGRAM_SUITE_SOURCE = (
    "import time\n"
    "print('suite started', flush=True)\n"
    "time.sleep(60)\n")


def scratch_checkout(scratch):
    repository = scratch / "repo"
    repository.mkdir()
    (repository / "doubling.py").write_bytes(MODULE_SOURCE.encode())
    (repository / "doubling-test.py").write_text(SUITE_SOURCE)
    (repository / "pid-one-test.py").write_text(PID_ONE_SUITE_SOURCE)
    (repository / "terminates-test.py").write_text(TERMINATES_THE_PROGRAM_SUITE_SOURCE)
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
    if not program.pid_one_is_bwrap():
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

# --- Refusals that run nothing ------------------------------------------------

with tempfile.TemporaryDirectory() as scratch_name:
    scratch = pathlib.Path(scratch_name)
    repository = scratch_checkout(scratch)
    def main_with_nothing_run(platform, sandbox=None):
        """Run main in this process with the suite run replaced; return (exit, output, runs)."""
        ran = []
        original_run, original_sandbox = program.run_suite_confined, program.runner.signal_sandbox
        program.run_suite_confined = lambda *arguments, **options: ran.append(arguments) or 0
        if sandbox is not None:
            program.runner.signal_sandbox = lambda platform=None: sandbox
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                code = program.main(["doubling-test.py", "--checkout", str(repository),
                                     "--lock-file", str(scratch / "run.lock")], platform=platform)
        finally:
            program.run_suite_confined = original_run
            program.runner.signal_sandbox = original_sandbox
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
            signal.signal(signal.SIGHUP, signal.SIG_DFL)
        return code, output.getvalue(), ran

    code, output, ran = main_with_nothing_run("darwin")
    check("on a platform other than Linux, nothing runs and the exit is 2",
          code == program.EXIT_NOT_RUN and ran == [] and "only on Linux" in output,
          (code, output, ran))
    code, output, ran = main_with_nothing_run(
        "linux", sandbox=((), "bwrap is not on PATH (Ubuntu: sudo apt install bubblewrap)"))
    check("on Linux without bwrap, the suite is not run unconfined: exit 2 naming bwrap",
          code == program.EXIT_NOT_RUN and ran == [] and "bwrap is not on PATH" in output,
          (code, output, ran))

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
    marker_suite.unlink()

    outside_suite = next(iter(program.runner.SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX))
    (repository / outside_suite).parent.mkdir(parents=True, exist_ok=True)
    (repository / outside_suite).write_text("print('ran')\n")
    completed, last = run_program(scratch, repository, outside_suite)
    check("a suite listed to run outside the sandbox is refused, exit 2",
          completed.returncode == 2 and "cannot run inside the signal sandbox" in last,
          (completed.returncode, last))

    completed, last = run_program(scratch, repository, "no-such-test.py")
    check("a suite that is not a file is refused, exit 2",
          completed.returncode == 2 and last.startswith("VERDICT: not run"), last)

    completed, last = run_program(scratch, repository, "doubling-test.py", "--mutant",
                                  str(scratch / "no-such.patch"))
    check("a mutant that is not a file is refused, exit 2",
          completed.returncode == 2 and "not a file" in last, last)

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

        # --- Restore failure is reported, not hidden --------------------------
        keep = scratch / "keep"
        keep.mkdir()
        (repository / "doubling.py").write_text("mutated\n")
        original_write_back = program.write_back
        program.write_back = lambda top, originals: ["doubling.py (read back differs)"]
        try:
            program.restore_originals(repository, {"doubling.py": MODULE_SOURCE.encode()}, keep)
        except program.RestoreFailed as error:
            check("a file that does not read back as its original is RestoreFailed naming "
                  "the file and where its original is kept",
                  "doubling.py" in str(error) and str(keep) in str(error), str(error))
        else:
            check("a file that does not read back as its original is RestoreFailed naming "
                  "the file and where its original is kept", False, "no exception")
        finally:
            program.write_back = original_write_back
        failed = program.write_back(repository, {"doubling.py": MODULE_SOURCE.encode()})
        check("write_back puts the bytes back and reports nothing when they read back",
              failed == [] and unchanged(repository), failed)
        failed = program.write_back(repository, {"no-dir/x.py": b"x"})
        check("write_back reports a file it cannot write", failed and "no-dir/x.py" in failed[0],
              failed)
        original_read_bytes = pathlib.Path.read_bytes
        pathlib.Path.read_bytes = lambda self: b"something else"
        try:
            failed = program.write_back(repository, {"doubling.py": MODULE_SOURCE.encode()})
        finally:
            pathlib.Path.read_bytes = original_read_bytes
        check("write_back reports a file that does not read back as written",
              failed == ["doubling.py (read back differs)"], failed)

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
            program.restore_originals(repository, {"doubling.py": MODULE_SOURCE.encode()}, keep)
            terminated = False
        except program.Terminated:
            terminated = True
        finally:
            program.write_back = original_write_back
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
        check("a SIGTERM that arrives during the restore takes effect only after every file "
              "is written", terminated and written == ["all files"], (terminated, written))

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

print()
print(f"{cases_run} cases run")
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
