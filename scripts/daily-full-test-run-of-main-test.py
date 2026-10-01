#!/usr/bin/env python3
"""Tests for daily-full-test-run-of-main.py.

Run: python3 scripts/daily-full-test-run-of-main-test.py

No case reaches anything real. The clone is a fixture clone of a bare
repository in the same scratch directory, so `git fetch origin` fetches a
local path; the log-store's root and the temporary directory are scratch
directories, passed on every call; the runner is a stand-in, committed to the
fixture's main as scripts/run-all-test-suites.py so the program's own default
finds it in the worktree it makes, which prints lines in the real runner's
shapes and exits as the case tells it; ned-box is played by an ssh first on
PATH that records its arguments and runs the command it was handed here; the
machine's name is set per case; and the moment, the wait and the clock are
passed in, so no case sleeps.

Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import fcntl
import importlib.util
import io
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().with_name("daily-full-test-run-of-main.py")
REPOSITORY_ROOT = SCRIPT_PATH.parent.parent

_spec = importlib.util.spec_from_file_location("daily_full_test_run_of_main", SCRIPT_PATH)
program = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(program)

_shipper_spec = importlib.util.spec_from_file_location(
    "cold_read_record_ship",
    REPOSITORY_ROOT / "nc-systems" / "cold-read" / "cold-read-record-ship.py")
record_shipper = importlib.util.module_from_spec(_shipper_spec)
_shipper_spec.loader.exec_module(record_shipper)

failures = []

# 20:30 on 2026-09-30 in America/Los_Angeles (PDT, UTC-7), which is already
# 2026-10-01 in UTC and 12:30 on 2026-10-01 in Tokyo.
PACIFIC_EVENING_THAT_IS_TOMORROW_IN_UTC = datetime(2026, 10, 1, 3, 30, tzinfo=timezone.utc)

SSH_THAT_RUNS_THE_COMMAND_HERE = 'exec /bin/sh -c "$1"'
SSH_THAT_CANNOT_REACH_NED_BOX = (
    "echo 'ssh: connect to host ned-box port 22: No route to host' >&2\n"
    "echo 'a second line' >&2\nexit 255")

STAND_IN_RUNNER_BEHAVIOUR_FILE_VARIABLE = "DAILY_FULL_TEST_RUN_STAND_IN_RUNNER_BEHAVIOUR_FILE"

# Played for scripts/run-all-test-suites.py. It writes down how it was called
# and what the checkout it was run from is, then prints what the real runner
# prints, in the real runner's shapes: its first line, the line saying how
# inputs are recorded, then the case's lines, and exits as the case says.
# Exit 3 and exit 2 print the real runner's refusals on stderr and nothing on
# stdout. A negative exit is the signal the stand-in kills itself with.
STAND_IN_RUNNER_SOURCE = r'''
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

behaviour = json.loads(Path(os.environ["DAILY_FULL_TEST_RUN_STAND_IN_RUNNER_BEHAVIOUR_FILE"]).read_text())
calls_file = Path(behaviour["calls_file"])
calls = json.loads(calls_file.read_text()) if calls_file.exists() else []
arguments = sys.argv[1:]
log_dir = Path(arguments[arguments.index("--log-dir") + 1])
checkout = Path.cwd()


def git(*git_arguments):
    return subprocess.run(["git", "-C", str(checkout), *git_arguments],
                          capture_output=True, text=True, check=False)


commit = git("rev-parse", "HEAD").stdout.strip()
exit_code = behaviour["exits"][min(len(calls), len(behaviour["exits"]) - 1)]
calls.append({
    "argv": sys.argv,
    "executable": sys.executable,
    "checkout": str(checkout),
    "checkout_top": git("rev-parse", "--show-toplevel").stdout.strip(),
    "commit": commit,
    "head_is_detached": git("symbolic-ref", "-q", "HEAD").returncode != 0,
    "later_file_is_there": (checkout / "a-later-file.txt").is_file(),
    "log_dir_held": sorted(path.name for path in log_dir.iterdir()) if log_dir.is_dir() else None,
})
calls_file.write_text(json.dumps(calls))
if exit_code == 3:
    print("run-all-test-suites: not run — another run holds /a/lock: pid 1, checkout "
          "/a/checkout, started 2026-10-01T03:29:00Z.\nRun this again after that run has "
          "finished.", file=sys.stderr)
    sys.exit(3)
if exit_code == 2:
    print("run-all-test-suites: not run — git lists no *-test.py file in " + str(checkout)
          + ".\nPass --checkout a checkout that has its suites committed or added.",
          file=sys.stderr)
    sys.exit(2)
if exit_code < 0:
    os.kill(os.getpid(), -exit_code)
log_dir.mkdir(parents=True, exist_ok=True)
(log_dir / ("log-of-call-%d.log" % len(calls))).write_text("a suite's output\n")
print("run-all-test-suites: %s at %s (tracked files match that commit); 3 suites listed by "
      "git; Python 3.14.4 (%s); -j 4; logs in %s" % (checkout, commit, sys.executable, log_dir))
print("inputs recorded by python-audit-hook, kept in /a/recordings/directory")
for line in behaviour["lines"]:
    print(line)
sys.exit(exit_code)
'''

SKIPPED_CASE_LINE = ("scripts/b-test.py: SKIP the end-to-end case: tmux is not installed")
PASSING_SUMMARY_LINE = ("SUMMARY: 3 passed, 0 failed, 3 total; 1 cases skipped in 1 suites; "
                        "worktree-of-main at 0123456789ab; Python 3.14.4")
PASSING_RUNNER_LINES = [
    "PASS scripts/a-test.py (0.1s)",
    "PASS scripts/b-test.py (0.2s, 1 skipped)",
    "PASS scripts/c-test.py (0.3s)",
    "",
    "skipped cases:",
    SKIPPED_CASE_LINE,
    PASSING_SUMMARY_LINE,
]
FAIL_LINES = [
    "FAIL scripts/b-test.py exit 1 (0.2s, 1 skipped)",
    "FAIL scripts/c-test.py killed by SIGKILL (0.3s)",
    "FAIL scripts/b-test.py exit 1 — log /a/log/directory/scripts__b-test.py.log",
    "FAIL scripts/c-test.py killed by SIGKILL — log /a/log/directory/scripts__c-test.py.log",
]
FAILING_SUMMARY_LINE = ("SUMMARY: 1 passed, 2 failed, 3 total; 1 cases skipped in 1 suites; "
                        "worktree-of-main at 0123456789ab; Python 3.14.4")
FAILING_RUNNER_LINES = [
    "PASS scripts/a-test.py (0.1s)",
    FAIL_LINES[0],
    FAIL_LINES[1],
    "",
    "2 failed:",
    FAIL_LINES[2],
    FAIL_LINES[3],
    "",
    "skipped cases:",
    SKIPPED_CASE_LINE,
    FAILING_SUMMARY_LINE,
]


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


@contextlib.contextmanager
def local_time_zone(name: str):
    saved = os.environ.get("TZ")
    os.environ["TZ"] = name
    time.tzset()
    try:
        yield
    finally:
        if saved is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = saved
        time.tzset()


def fixture_git(directory: Path, *arguments) -> str:
    """One git command in a fixture directory, with the variables that send
    git into another repository dropped; its stdout. A command that fails
    stops the suite, so no case runs against a repository that was not made."""
    completed = subprocess.run(
        ["git", "-C", str(directory), "-c", "user.name=daily-full-test-run-fixture",
         "-c", "user.email=daily-full-test-run-fixture@example.invalid",
         "-c", "commit.gpgsign=false", *arguments],
        env=program.run_all_test_suites.environment_without_git_redirecting_variables(),
        stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise SystemExit(f"fixture: git {' '.join(arguments)} failed in {directory}: "
                         f"{completed.stderr}")
    return completed.stdout.strip()


class RunResult:
    def __init__(self, code, stdout, stderr, ssh_calls, runner_calls, waits):
        self.code = code
        self.stdout = stdout
        self.stderr = stderr
        self.ssh_calls = ssh_calls
        self.runner_calls = runner_calls
        self.waits = waits

    def __repr__(self):
        return (f"exit {self.code}\nstdout: {self.stdout}\nstderr: {self.stderr}\n"
                f"ssh calls: {self.ssh_calls!r}\nwaits: {self.waits!r}\n"
                f"runner calls: {json.dumps(self.runner_calls, indent=1)}")


class Fixture:
    """A bare repository playing origin, a clone of it that is one commit
    behind origin's main, a scratch log-store root and a scratch temporary
    directory."""

    def __init__(self, root: Path):
        self.root = root
        root.mkdir()
        self.origin = root / "origin.git"
        fixture_git(root, "init", "-q", "--bare", "-b", "main", str(self.origin))
        if not (self.origin / "HEAD").is_file():
            raise SystemExit(f"fixture: no bare repository was made at {self.origin}")
        seed = root / "seed"
        fixture_git(root, "init", "-q", "-b", "main", str(seed))
        if not (seed / ".git").is_dir():
            raise SystemExit(f"fixture: no repository was made at {seed}")
        (seed / "scripts").mkdir()
        (seed / "scripts" / "run-all-test-suites.py").write_text(
            STAND_IN_RUNNER_SOURCE, encoding="utf-8")
        fixture_git(seed, "add", "-A")
        fixture_git(seed, "commit", "-q", "-m", "the stand-in runner")
        fixture_git(seed, "push", "-q", str(self.origin), "main")
        self.clone = root / "clone"
        fixture_git(root, "clone", "-q", str(self.origin), str(self.clone))
        if not (self.clone / ".git").is_dir():
            raise SystemExit(f"fixture: no clone was made at {self.clone}")
        self.commit_the_clone_was_made_at = fixture_git(self.clone, "rev-parse", "HEAD")
        # main moves on after the clone was made, so only a fetch finds it.
        (seed / "a-later-file.txt").write_text("added after the clone was made\n",
                                               encoding="utf-8")
        fixture_git(seed, "add", "-A")
        fixture_git(seed, "commit", "-q", "-m", "main moves on")
        fixture_git(seed, "push", "-q", str(self.origin), "main")
        self.commit_of_main = fixture_git(seed, "rev-parse", "HEAD")
        self.log_store = root / "log-store"
        self.temporary = root / "temporary"
        self.temporary.mkdir()
        self.directory = self.temporary / program.DAILY_FULL_TEST_RUN_DIRECTORY_NAME
        self.worktree = self.directory / program.DAILY_FULL_TEST_RUN_WORKTREE_DIRECTORY_NAME
        self.logs = self.directory / program.DAILY_FULL_TEST_RUN_LOGS_DIRECTORY_NAME
        self.local_copy = (self.directory
                           / program.DAILY_FULL_TEST_RUN_RECORD_LOCAL_COPY_FILE_NAME)
        self.run_count = 0

    def scratch_for_next_run(self):
        self.run_count += 1
        scratch = self.root / f"run-{self.run_count}"
        scratch.mkdir()
        return scratch

    def fake_ssh_directory(self, scratch: Path, ssh_body: str) -> Path:
        directory = scratch / "fake-ssh"
        directory.mkdir()
        fake_ssh = directory / "ssh"
        fake_ssh.write_text(
            '#!/bin/sh\nprintf "%s\\n" "$*" >> "' + str(scratch / "ssh-calls") + '"\n'
            'while [ "$1" = "-o" ]; do shift 2; done\nshift\n' + ssh_body + "\n",
            encoding="utf-8")
        fake_ssh.chmod(0o755)
        return directory

    def arguments(self, clone=None):
        return ["--clone", str(clone or self.clone), "--log-store-root", str(self.log_store),
                "--temporary-directory", str(self.temporary)]

    def run(self, exits=(0,), lines=PASSING_RUNNER_LINES, hostname="ned-box",
            now=PACIFIC_EVENING_THAT_IS_TOMORROW_IN_UTC,
            ssh_body=SSH_THAT_RUNS_THE_COMMAND_HERE, extra_arguments=(), clone=None,
            lock_wait_bound_seconds=None) -> RunResult:
        """main's exit code and output, with the fake ssh's calls, the stand-in
        runner's calls and the waits main asked for. The clock is the sum of
        those waits, so a case takes no time."""
        scratch = self.scratch_for_next_run()
        behaviour_file = scratch / "stand-in-runner-behaviour.json"
        calls_file = scratch / "stand-in-runner-calls.json"
        behaviour_file.write_text(json.dumps(
            {"exits": list(exits), "lines": list(lines), "calls_file": str(calls_file)}),
            encoding="utf-8")
        fake_ssh = self.fake_ssh_directory(scratch, ssh_body)
        waits = []
        clock = [0.0]

        def wait(seconds):
            waits.append(seconds)
            clock[0] += seconds

        saved_bound = program.DAILY_FULL_TEST_RUN_LOCK_WAIT_BOUND_SECONDS
        if lock_wait_bound_seconds is not None:
            program.DAILY_FULL_TEST_RUN_LOCK_WAIT_BOUND_SECONDS = lock_wait_bound_seconds
        saved_gethostname = socket.gethostname
        socket.gethostname = lambda: hostname
        original_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{fake_ssh}{os.pathsep}{original_path}"
        os.environ[STAND_IN_RUNNER_BEHAVIOUR_FILE_VARIABLE] = str(behaviour_file)
        stdout, stderr = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = program.main([*self.arguments(clone), *extra_arguments], now=now,
                                    wait=wait, monotonic=lambda: clock[0])
        finally:
            os.environ["PATH"] = original_path
            os.environ.pop(STAND_IN_RUNNER_BEHAVIOUR_FILE_VARIABLE, None)
            socket.gethostname = saved_gethostname
            program.DAILY_FULL_TEST_RUN_LOCK_WAIT_BOUND_SECONDS = saved_bound
        ssh_calls_file = scratch / "ssh-calls"
        ssh_calls = (ssh_calls_file.read_text(encoding="utf-8").splitlines()
                     if ssh_calls_file.exists() else [])
        runner_calls = json.loads(calls_file.read_text()) if calls_file.exists() else []
        return RunResult(code, stdout.getvalue(), stderr.getvalue(), ssh_calls, runner_calls,
                         waits)

    def record_files(self):
        """Every file under the log-store root, relative to it."""
        return sorted(str(path.relative_to(self.log_store))
                      for path in self.log_store.rglob("*") if path.is_file())

    def record(self, machine: str, date: str = "2026-09-30"):
        path = (self.log_store / program.DAILY_FULL_TEST_RUNS_KIND_DIRECTORY_NAME / machine
                / f"{date}.txt")
        return path.read_text(encoding="utf-8") if path.is_file() else None

    def worktree_is_gone(self, clone=None) -> bool:
        """The worktree's directory is gone, the clone has no worktree but
        itself registered, and no branch but main was made."""
        clone = clone or self.clone
        registered = [line for line in fixture_git(
            clone, "worktree", "list", "--porcelain").splitlines()
            if line.startswith("worktree ")]
        branches = fixture_git(clone, "for-each-ref", "--format=%(refname:short)",
                               "refs/heads").split()
        return not self.worktree.exists() and len(registered) == 1 and branches == ["main"]


def run_cases_on_ned_box(workspace: Path):
    fixture = Fixture(workspace / "on-ned-box")

    # --- A passing run ------------------------------------------------------
    result = fixture.run()
    record = fixture.record("ned-box")
    call = result.runner_calls[0] if result.runner_calls else {}
    check("a passing run exits 0", result.code == 0, repr(result))
    check("on ned-box the record is written locally, with no ssh, as "
          "daily-full-test-runs/ned-box/<date>.txt",
          fixture.record_files() == ["daily-full-test-runs/ned-box/2026-09-30.txt"]
          and result.ssh_calls == [], f"{fixture.record_files()} {result!r}")
    check("a passing run's record holds the SUMMARY line",
          record is not None and PASSING_SUMMARY_LINE in record.splitlines(), repr(record))
    first_line = (f"run-all-test-suites: {fixture.worktree} at {fixture.commit_of_main} "
                  f"(tracked files match that commit); 3 suites listed by git; Python 3.14.4 "
                  f"({sys.executable}); -j 4; logs in {fixture.logs}")
    check("the whole record: this program's line, origin/main's commit, the runner's first "
          "line, the skipped case, the SUMMARY line, the exit code, both counts of seconds "
          "and the logs' directory",
          record == "\n".join([
              "daily-full-test-run-of-main: ned-box, 2026-09-30 in America/Los_Angeles, "
              "started 2026-10-01T03:30:00Z",
              f"origin/main: {fixture.commit_of_main}",
              first_line,
              SKIPPED_CASE_LINE,
              PASSING_SUMMARY_LINE,
              "runner exit code: 0",
              "seconds waiting for the machine's lock: 0",
              "wall-clock seconds: 0",
              f"logs: {fixture.logs} on ned-box",
          ]) + "\n", repr(record))
    check("stdout is the record's citation in the scp form",
          result.stdout == "daily-full-test-run-of-main: record written to nedlern@ned-box:"
          f"{fixture.log_store}/daily-full-test-runs/ned-box/2026-09-30.txt\n", result.stdout)
    check("the runner is run once, by the Python running this program, as the worktree's "
          "scripts/run-all-test-suites.py -j 4 --log-dir <logs>, with no selection option "
          "and no --recorded-inputs-directory",
          len(result.runner_calls) == 1
          and call.get("argv") == [str(fixture.worktree / "scripts" / "run-all-test-suites.py"),
                                   "-j", "4", "--log-dir", str(fixture.logs)]
          and os.path.realpath(call.get("executable", "")) == os.path.realpath(sys.executable),
          repr(result))
    check("the fetch found main's newer commit, and the worktree was a detached worktree at "
          "that commit, not the clone's own checkout",
          fixture.commit_of_main != fixture.commit_the_clone_was_made_at
          and call.get("commit") == fixture.commit_of_main
          and call.get("later_file_is_there") is True
          and call.get("head_is_detached") is True
          and call.get("checkout_top") == str(fixture.worktree)
          and not (fixture.clone / "a-later-file.txt").exists(), repr(result))
    check("the worktree is removed after a passing run, and no branch was made",
          fixture.worktree_is_gone(), fixture_git(fixture.clone, "worktree", "list"))
    check("the record's local copy beside the logs is the record",
          fixture.local_copy.is_file()
          and fixture.local_copy.read_text(encoding="utf-8") == record,
          repr(fixture.local_copy))

    # --- A failing run, the same day -----------------------------------------
    result = fixture.run(exits=(1,), lines=FAILING_RUNNER_LINES)
    record = fixture.record("ned-box")
    record_lines = record.splitlines() if record else []
    check("a failing run exits with the runner's exit code", result.code == 1, repr(result))
    check("a failing run's record holds every FAIL line the runner printed, both the line "
          "printed as a suite finished and the line naming its log",
          [line for line in record_lines if line.startswith("FAIL ")] == FAIL_LINES,
          repr(record))
    check("a failing run's record holds the skipped case, the SUMMARY line and exit code 1",
          SKIPPED_CASE_LINE in record_lines and FAILING_SUMMARY_LINE in record_lines
          and "runner exit code: 1" in record_lines, repr(record))
    check("a PASS line is not kept in the record",
          not any(line.startswith("PASS ") for line in record_lines), repr(record))
    check("the worktree is removed after a failing run", fixture.worktree_is_gone(),
          fixture_git(fixture.clone, "worktree", "list"))
    check("a second run the same day replaces the record: one file, holding the second "
          "run alone",
          fixture.record_files() == ["daily-full-test-runs/ned-box/2026-09-30.txt"]
          and PASSING_SUMMARY_LINE not in record_lines, f"{fixture.record_files()} {record!r}")
    check("each run replaces the logs: the second run's runner found none of the first's, "
          "and the directory holds the second run's alone",
          result.runner_calls[0]["log_dir_held"] is None
          and sorted(path.name for path in fixture.logs.iterdir()) == ["log-of-call-1.log"],
          repr(result))

    # --- Exit 3 is waited out -------------------------------------------------
    result = fixture.run(exits=(3, 3, 0))
    record_lines = (fixture.record("ned-box") or "").splitlines()
    check("while the runner exits 3 the program waits 2 seconds and runs it again",
          result.code == 0 and result.waits == [2, 2] and len(result.runner_calls) == 3,
          repr(result))
    check("the record of a run that waited holds the run that followed and the seconds "
          "waited, and none of the refusals",
          PASSING_SUMMARY_LINE in record_lines and "runner exit code: 0" in record_lines
          and "seconds waiting for the machine's lock: 4" in record_lines
          and "wall-clock seconds: 4" in record_lines
          and not any("another run holds" in line for line in record_lines),
          repr(record_lines))

    result = fixture.run(exits=(3,), lock_wait_bound_seconds=6)
    record_lines = (fixture.record("ned-box") or "").splitlines()
    check("the wait is bounded: with a bound of 6 seconds the runner is run at 0, 2, 4 and 6 "
          "seconds and no more, and the program exits 4",
          result.code == 4 and result.waits == [2, 2, 2] and len(result.runner_calls) == 4,
          repr(result))
    check("the record says the lock was never released, with the runner's last refusal",
          any(line.startswith("not run — the lock was never released: run-all-test-suites "
                              "exited 3 on every attempt for 6 s; its last refusal: "
                              "run-all-test-suites: not run — another run holds /a/lock")
              for line in record_lines)
          and "runner exit code: 3" in record_lines
          and not any(line.startswith("SUMMARY:") for line in record_lines),
          repr(record_lines))
    check("stderr says the lock was never released and what to do",
          "not run — the lock was never released" in result.stderr
          and result.stderr.endswith(
              "\nRun this again after the run holding that lock has finished.\n"),
          result.stderr)
    check("the bound is an hour", program.DAILY_FULL_TEST_RUN_LOCK_WAIT_BOUND_SECONDS == 3600
          and program.DAILY_FULL_TEST_RUN_LOCK_WAIT_SECONDS == 2)
    check("the worktree is removed after the lock was never released",
          fixture.worktree_is_gone(), fixture_git(fixture.clone, "worktree", "list"))

    # --- A runner that could not start, and one that gave no verdict -----------
    result = fixture.run(exits=(2,))
    record_lines = (fixture.record("ned-box") or "").splitlines()
    check("a runner that exits 2 is recorded with its stderr in the SUMMARY line's place, "
          "and the program exits 2",
          result.code == 2 and "runner exit code: 2" in record_lines
          and "the runner printed no SUMMARY: line; its stderr:" in record_lines
          and any(line.startswith("  run-all-test-suites: not run — git lists no")
                  for line in record_lines), f"{result!r}\n{record_lines!r}")
    result = fixture.run(exits=(0,), lines=["PASS scripts/a-test.py (0.1s)"])
    record_lines = (fixture.record("ned-box") or "").splitlines()
    check("a runner that exits 0 with no SUMMARY line gave no verdict: the record says so "
          "and the program exits 4",
          result.code == 4 and "runner exit code: 0" in record_lines
          and "run-all-test-suites exited 0 and printed no SUMMARY: line, which is no "
              "verdict" in record_lines, f"{result!r}\n{record_lines!r}")

    result = fixture.run(exits=(-9,))
    record_lines = (fixture.record("ned-box") or "").splitlines()
    check("a runner killed by a signal gave no verdict either: the record names the "
          "signal and the program exits 4",
          result.code == 4 and "runner exit code: -9" in record_lines
          and "run-all-test-suites was killed by SIGKILL" in record_lines
          and fixture.worktree_is_gone(), f"{result!r}\n{record_lines!r}")

    # --- The seams -------------------------------------------------------------
    recorded_inputs = workspace / "a-recorded-inputs-directory"
    result = fixture.run(extra_arguments=["--recorded-inputs-directory", str(recorded_inputs)])
    check("--recorded-inputs-directory is passed through to the runner",
          result.code == 0 and result.runner_calls[0]["argv"][-2:]
          == ["--recorded-inputs-directory", str(recorded_inputs)]
          and not recorded_inputs.exists(), repr(result))
    stand_in_elsewhere = workspace / "a-stand-in-runner-outside-the-worktree.py"
    stand_in_elsewhere.write_text(STAND_IN_RUNNER_SOURCE, encoding="utf-8")
    result = fixture.run(
        extra_arguments=["--test-suite-runner-program", str(stand_in_elsewhere)])
    check("--test-suite-runner-program is run in place of the worktree's runner, from the "
          "worktree, with the same arguments",
          result.code == 0 and result.runner_calls[0]["argv"]
          == [str(stand_in_elsewhere), "-j", "4", "--log-dir", str(fixture.logs)]
          and result.runner_calls[0]["checkout"] == str(fixture.worktree), repr(result))

    # --- What a killed run left -------------------------------------------------
    # Guarded, so that a program that leaves its own worktree behind fails the
    # cases above and below instead of stopping the suite here.
    if not fixture.worktree.exists():
        fixture_git(fixture.clone, "worktree", "add", "-q", "--detach", str(fixture.worktree),
                    fixture.commit_the_clone_was_made_at)
    (fixture.worktree / "left-by-the-killed-run.txt").write_text("left\n", encoding="utf-8")
    result = fixture.run()
    check("a worktree a killed run left at the path is replaced by one at main's commit",
          result.code == 0 and result.runner_calls[0]["commit"] == fixture.commit_of_main
          and fixture.worktree_is_gone(), repr(result))
    fixture.worktree.mkdir(exist_ok=True)
    (fixture.worktree / "not-a-worktree.txt").write_text("left\n", encoding="utf-8")
    result = fixture.run()
    check("a plain directory left at the worktree's path is replaced too",
          result.code == 0 and result.runner_calls[0]["commit"] == fixture.commit_of_main
          and fixture.worktree_is_gone(), repr(result))

    # --- One daily run at a time -------------------------------------------------
    files_before = {name: fixture.record(name) for name in ("ned-box", "mac")}
    with open(fixture.directory / program.DAILY_FULL_TEST_RUN_LOCK_FILE_NAME, "a") as holder:
        fcntl.flock(holder.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = fixture.run()
    check("while another daily run holds this program's lock, a run exits 6 having run "
          "nothing and written nothing",
          result.code == 6 and result.runner_calls == [] and result.stdout == ""
          and {name: fixture.record(name) for name in ("ned-box", "mac")} == files_before
          and result.stderr == "daily-full-test-run-of-main: not run — another daily full "
          f"test run holds {fixture.directory}/daily-full-test-run-of-main.lock.\n"
          "Run this again after that run has finished.\n", repr(result))
    result = fixture.run()
    check("once that run's lock is released, a run goes ahead", result.code == 0,
          repr(result))

    # --- The record's local copy cannot be written --------------------------------
    record_before = fixture.record("ned-box")
    fixture.local_copy.unlink()
    fixture.local_copy.mkdir()
    result = fixture.run(exits=(1,), lines=FAILING_RUNNER_LINES)
    fixture.local_copy.rmdir()
    check("when the record's local copy cannot be written the program exits 5, leaves the "
          "log-store's record as it was, and says what failed and what to do",
          result.code == 5 and result.stdout == "" and fixture.record("ned-box") == record_before
          and result.stderr.startswith(
              "daily-full-test-run-of-main: the record was not written: its local copy "
              f"{fixture.local_copy} could not be written (IsADirectoryError: ")
          and result.stderr.endswith(
              "\nTell the user what the line above says.\n"
              "Fix what the error names, then run this again.\n")
          and fixture.worktree_is_gone(), repr(result))

    # --- A failed fetch -----------------------------------------------------------
    cut_off = workspace / "a-clone-whose-origin-is-gone"
    fixture_git(workspace, "clone", "-q", str(fixture.origin), str(cut_off))
    fixture_git(cut_off, "remote", "set-url", "origin", str(workspace / "no-such-origin.git"))
    result = fixture.run(clone=cut_off)
    record_lines = (fixture.record("ned-box") or "").splitlines()
    check("a failed fetch stops the run: the runner is not run and the program exits 4",
          result.code == 4 and result.runner_calls == [], repr(result))
    check("a failed fetch is written to the record",
          any(line.startswith(f"not run — git fetch origin failed in {cut_off}: ")
              for line in record_lines)
          and "origin/main: not resolved" in record_lines
          and "runner exit code: none, the runner was not run" in record_lines,
          repr(record_lines))
    check("a failed fetch prints what failed and what to do on stderr, and still cites the "
          "record",
          result.stderr.startswith("daily-full-test-run-of-main: not run — git fetch origin "
                                   f"failed in {cut_off}: ")
          and result.stderr.endswith("\nFix what git reports, then run this again.\n")
          and result.stdout.startswith("daily-full-test-run-of-main: record written to "),
          repr(result))
    check("a failed fetch leaves no worktree", fixture.worktree_is_gone(cut_off),
          fixture_git(cut_off, "worktree", "list"))


def run_cases_on_the_mac(workspace: Path):
    fixture = Fixture(workspace / "on-the-mac")

    # Under Tokyo's zone the machine's own date is 2026-10-01; the record is
    # dated by the Pacific one.
    with local_time_zone("Asia/Tokyo"):
        result = fixture.run(hostname="a-mac-that-is-not-ned-box")
    record = fixture.record("mac")
    check("off ned-box the record is written over ssh to nedlern@ned-box, with the options "
          "the log-store's other writers pass, as daily-full-test-runs/mac/<date>.txt",
          result.code == 0 and record is not None and PASSING_SUMMARY_LINE in record
          and result.ssh_calls == [
              "-o BatchMode=yes -o ConnectTimeout=10 nedlern@ned-box mkdir -p "
              f"{fixture.log_store}/daily-full-test-runs/mac && cat > "
              f"{fixture.log_store}/daily-full-test-runs/mac/2026-09-30.txt"],
          f"{result!r}\n{record!r}")
    check("the record is dated by the Pacific date when the machine's zone is another day",
          fixture.record_files() == ["daily-full-test-runs/mac/2026-09-30.txt"]
          and record.startswith("daily-full-test-run-of-main: mac, 2026-09-30 in "
                                "America/Los_Angeles, started 2026-10-01T03:30:00Z\n"),
          f"{fixture.record_files()} {record!r}")
    check("the citation names ned-box and the mac's directory",
          result.stdout == "daily-full-test-run-of-main: record written to nedlern@ned-box:"
          f"{fixture.log_store}/daily-full-test-runs/mac/2026-09-30.txt\n", result.stdout)

    # --- ned-box cannot be reached ------------------------------------------------
    unreachable = Fixture(workspace / "on-the-mac-with-ned-box-unreachable")
    result = unreachable.run(hostname="a-mac-that-is-not-ned-box",
                             ssh_body=SSH_THAT_CANNOT_REACH_NED_BOX)
    target = f"{unreachable.log_store}/daily-full-test-runs/mac/2026-09-30.txt"
    remedy = ("ssh -o BatchMode=yes -o ConnectTimeout=10 nedlern@ned-box "
              f"'mkdir -p {unreachable.log_store}/daily-full-test-runs/mac && cat > "
              f"{target}' < {unreachable.local_copy}")
    check("when ned-box cannot be reached the program exits 5, cites nothing and writes "
          "nothing into the log-store",
          result.code == 5 and result.stdout == "" and unreachable.record_files() == []
          and len(result.runner_calls) == 1, repr(result))
    check("when ned-box cannot be reached stderr is what failed, then one instruction a "
          "line: tell the user, and the command that writes the record",
          result.stderr == "daily-full-test-run-of-main: the record was not written to "
          f"nedlern@ned-box:{target} (ssh nedlern@ned-box exited 255: ssh: connect to host "
          "ned-box port 22: No route to host).\n"
          "Tell the user what the line above says, and the remedy in the line below.\n"
          "When ned-box answers ssh again, write the record by running on this machine: "
          f"{remedy}\n", result.stderr)
    check("the worktree is removed after a failed record write",
          unreachable.worktree_is_gone(), fixture_git(unreachable.clone, "worktree", "list"))
    local_copy = (unreachable.local_copy.read_text(encoding="utf-8")
                  if unreachable.local_copy.is_file() else None)
    check("the record that could not be written is kept beside the logs",
          local_copy is not None and PASSING_SUMMARY_LINE in local_copy.splitlines(),
          repr(local_copy))
    scratch = unreachable.scratch_for_next_run()
    reachable_again = unreachable.fake_ssh_directory(scratch, SSH_THAT_RUNS_THE_COMMAND_HERE)
    environment = program.run_all_test_suites.environment_without_git_redirecting_variables()
    environment["PATH"] = f"{reachable_again}{os.pathsep}{environment.get('PATH', '')}"
    written_by_hand = subprocess.run(["/bin/sh", "-c", remedy], env=environment,
                                     capture_output=True, text=True, check=False)
    check("the command stderr gives writes that record once ned-box answers",
          written_by_hand.returncode == 0 and unreachable.record("mac") == local_copy,
          f"{written_by_hand.returncode} {written_by_hand.stderr}")


def run_cases_as_a_program(workspace: Path):
    """The program run as cron runs it: its own process, its real clock and
    wait, the moment taken from the machine. ned-box is the fake ssh on either
    machine, so the case holds on both."""
    fixture = Fixture(workspace / "as-a-program")
    scratch = fixture.scratch_for_next_run()
    behaviour_file = scratch / "stand-in-runner-behaviour.json"
    behaviour_file.write_text(json.dumps(
        {"exits": [0], "lines": PASSING_RUNNER_LINES,
         "calls_file": str(scratch / "stand-in-runner-calls.json")}), encoding="utf-8")
    fake_ssh = fixture.fake_ssh_directory(scratch, SSH_THAT_RUNS_THE_COMMAND_HERE)
    environment = program.run_all_test_suites.environment_without_git_redirecting_variables()
    environment["PATH"] = f"{fake_ssh}{os.pathsep}{environment.get('PATH', '')}"
    environment[STAND_IN_RUNNER_BEHAVIOUR_FILE_VARIABLE] = str(behaviour_file)
    completed = subprocess.run([sys.executable, str(SCRIPT_PATH), *fixture.arguments()],
                               env=environment, stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, check=False)
    written = fixture.record_files()
    record = ((fixture.log_store / written[0]).read_text(encoding="utf-8")
              if len(written) == 1 else "")
    check("run as a program it exits 0, writes one record dated today and cites it",
          completed.returncode == 0 and len(written) == 1
          and re.fullmatch(r"daily-full-test-runs/(ned-box|mac)/\d{4}-\d{2}-\d{2}\.txt",
                           written[0]) is not None
          and completed.stdout == "daily-full-test-run-of-main: record written to "
          f"nedlern@ned-box:{fixture.log_store}/{written[0]}\n",
          f"{completed.returncode} {written!r}\n{completed.stdout}\n{completed.stderr}")
    check("that record holds the SUMMARY line and both counts of seconds as whole numbers",
          PASSING_SUMMARY_LINE in record.splitlines()
          and re.search(r"^seconds waiting for the machine's lock: 0$", record, re.M)
          and re.search(r"^wall-clock seconds: \d+$", record, re.M), record)
    check("run as a program it leaves no worktree", fixture.worktree_is_gone(),
          fixture_git(fixture.clone, "worktree", "list"))
    invalid = subprocess.run([sys.executable, str(SCRIPT_PATH), "--no-such-option"],
                             env=environment, stdin=subprocess.DEVNULL,
                             capture_output=True, text=True, check=False)
    check("an option it does not have is a bad invocation, exit 2, and nothing is run",
          invalid.returncode == 2 and fixture.record_files() == written,
          f"{invalid.returncode} {invalid.stderr}")


def run_log_store_readme_cases():
    readme = record_shipper.STORE_README
    kind = program.DAILY_FULL_TEST_RUNS_KIND_DIRECTORY_NAME
    check("the log-store's README lists daily-full-test-runs/ once, naming this program as "
          "its owner",
          kind == "daily-full-test-runs" and readme.count(f"`{kind}/`") == 1
          and f"- `{kind}/` -- " in readme
          and "`scripts/daily-full-test-run-of-main.py`" in readme, readme)


with tempfile.TemporaryDirectory() as temporary_directory:
    # Resolved, because the program resolves the paths it is given and the
    # Mac's temporary directory is reached through a symbolic link.
    workspace_root = Path(temporary_directory).resolve()
    run_cases_on_ned_box(workspace_root)
    run_cases_on_the_mac(workspace_root)
    run_cases_as_a_program(workspace_root)
    run_log_store_readme_cases()

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
