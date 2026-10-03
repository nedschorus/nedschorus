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
passed in, so no case run inside this process sleeps. The wait passed in
raises once the program has waited past its own bound, and a case is failed
by whatever leaves the program's main, so a program that waits for ever fails
a case instead of hanging the suite.

The cases that stop a daily run by its process ID use real processes: the
program is started as cron starts it, its stand-in runner waits for a file
this suite writes, and every wait this suite makes for another process ends
at WAIT_FOR_ANOTHER_PROCESS_BOUND_SECONDS. The stand-in runner and the
process it starts end by themselves at their own bound, so a suite that is
itself killed leaves no process behind for longer than that.

Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import errno
import fcntl
import importlib.util
import io
import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
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

# How long this suite waits for another process to do what a case waits for,
# and how long the stand-in runner and the process it starts wait to be
# released before they end by themselves.
WAIT_FOR_ANOTHER_PROCESS_BOUND_SECONDS = 20
STAND_IN_PROCESS_OWN_BOUND_SECONDS = 60

FILE_LEFT_IN_THE_WORKTREE_BY_THE_WAITING_RUNNER = "left-by-the-runner-that-is-still-running.txt"

# Played for scripts/run-all-test-suites.py. It writes down how it was called
# and what the checkout it was run from is, then prints what the real runner
# prints, in the real runner's shapes: its first line, the line saying how
# inputs are recorded, then the case's lines, and exits as the case says.
# Exit 3 and exit 2 print the real runner's refusals on stderr and nothing on
# stdout. A negative exit is the signal the stand-in kills itself with.
#
# Every call also writes down whether the daily run's lock was free, tried
# with a descriptor of the stand-in's own. Three more behaviours, each asked
# for by a key of the behaviour file:
#   leaves_a_directory_its_owner_may_not_write_to: leaves in the checkout a
#     directory at mode 555 holding one file.
#   removes_the_git_file_of_the_checkout: removes the checkout's .git file, so
#     that `git worktree remove` refuses before it drops the registration.
#   waits_until_released: leaves a file in the checkout, starts a process the
#     way the real runner starts a suite (subprocess, its output to a log
#     file), writes both process IDs to started_file, then waits for
#     released_file and exits printing nothing. The process it started waits
#     for process_released_file and then writes process_acknowledgment_file.
STAND_IN_RUNNER_SOURCE = r'''
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

behaviour = json.loads(Path(os.environ["DAILY_FULL_TEST_RUN_STAND_IN_RUNNER_BEHAVIOUR_FILE"]).read_text())
calls_file = Path(behaviour["calls_file"])
calls = json.loads(calls_file.read_text()) if calls_file.exists() else []
arguments = sys.argv[1:]
log_dir = Path(arguments[arguments.index("--log-dir") + 1])
checkout = Path.cwd()


def daily_run_lock_is_free():
    with open(log_dir.parent / "daily-full-test-run-of-main.lock", "a") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        return True


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
    "daily_run_lock_was_free": daily_run_lock_is_free(),
})
calls_file.write_text(json.dumps(calls))
if behaviour.get("leaves_a_directory_its_owner_may_not_write_to"):
    left = checkout / "a-directory-its-owner-may-not-write-to"
    left.mkdir()
    (left / "a-file.txt").write_text("left\n")
    left.chmod(0o555)
if behaviour.get("removes_the_git_file_of_the_checkout"):
    (checkout / ".git").unlink()
waiting = behaviour.get("waits_until_released")
if waiting:
    (checkout / "left-by-the-runner-that-is-still-running.txt").write_text("left\n")
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(log_dir / "the-process-the-runner-started.log", "wb") as log:
        started = subprocess.Popen(
            [sys.executable, "-c",
             "import sys, time\n"
             "from pathlib import Path\n"
             "ends = time.monotonic() + float(sys.argv[3])\n"
             "while not Path(sys.argv[1]).exists() and time.monotonic() < ends:\n"
             "    time.sleep(0.02)\n"
             "if Path(sys.argv[1]).exists():\n"
             "    Path(sys.argv[2]).write_text('running when released')\n",
             waiting["process_released_file"], waiting["process_acknowledgment_file"],
             str(waiting["own_bound_seconds"])],
            cwd=str(checkout), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
    started_file = Path(waiting["started_file"])
    not_yet = started_file.with_name(started_file.name + ".being-written")
    not_yet.write_text(json.dumps({"runner_pid": os.getpid(), "process_pid": started.pid}))
    os.replace(not_yet, started_file)
    ends = time.monotonic() + waiting["own_bound_seconds"]
    while not Path(waiting["released_file"]).exists() and time.monotonic() < ends:
        time.sleep(0.02)
    os._exit(0)
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


class StandInWaitRaised(Exception):
    """Raised by the wait a case passes the program: at once when the case
    says so, and otherwise once the program has waited past its own bound."""


class RunResult:
    def __init__(self, code, stdout, stderr, ssh_calls, runner_calls, waits, raised=None):
        # None when main did not return, and `raised` is what left it.
        self.code = code
        self.raised = raised
        self.stdout = stdout
        self.stderr = stderr
        self.ssh_calls = ssh_calls
        self.runner_calls = runner_calls
        self.waits = waits

    def __repr__(self):
        return (f"exit {self.code}\nraised: {self.raised!r}\n"
                f"stdout: {self.stdout}\nstderr: {self.stderr}\n"
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
        self.lock_file = self.directory / program.DAILY_FULL_TEST_RUN_LOCK_FILE_NAME
        self.run_count = 0

    def local_copy(self, date: str = "2026-09-30") -> Path:
        return self.directory / f"daily-full-test-run-record-{date}.txt"

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
            lock_wait_bound_seconds=None, wait_raises_at_once=False,
            stand_in_runner_behaviour=None, chmod_is_refused=False) -> RunResult:
        """main's exit code and output, with the fake ssh's calls, the stand-in
        runner's calls and the waits main asked for. The clock is the sum of
        those waits, so a case takes no time. Whatever leaves main is kept as
        the result's `raised`, with no exit code, so it fails the case's check
        and the suite goes on. With `chmod_is_refused`, every os.chmod made
        in this process while main runs raises PermissionError, which stands
        for a directory whose mode the program may not change."""
        scratch = self.scratch_for_next_run()
        behaviour_file = scratch / "stand-in-runner-behaviour.json"
        calls_file = scratch / "stand-in-runner-calls.json"
        behaviour_file.write_text(json.dumps(
            {"exits": list(exits), "lines": list(lines), "calls_file": str(calls_file),
             **(stand_in_runner_behaviour or {})}),
            encoding="utf-8")
        fake_ssh = self.fake_ssh_directory(scratch, ssh_body)
        waits = []
        clock = [0.0]

        def wait(seconds):
            waits.append(seconds)
            clock[0] += seconds
            if wait_raises_at_once:
                raise StandInWaitRaised("the case told the wait to raise")
            # The program's last attempt starts at the first moment at or
            # past its bound, which is less than one wait past the bound.
            if clock[0] > (program.DAILY_FULL_TEST_RUN_LOCK_WAIT_BOUND_SECONDS
                           + program.DAILY_FULL_TEST_RUN_LOCK_WAIT_SECONDS):
                raise StandInWaitRaised(
                    f"the program asked to wait at {clock[0]:.0f} s, past its bound of "
                    f"{program.DAILY_FULL_TEST_RUN_LOCK_WAIT_BOUND_SECONDS} s")

        saved_bound = program.DAILY_FULL_TEST_RUN_LOCK_WAIT_BOUND_SECONDS
        if lock_wait_bound_seconds is not None:
            program.DAILY_FULL_TEST_RUN_LOCK_WAIT_BOUND_SECONDS = lock_wait_bound_seconds
        saved_chmod = os.chmod

        def refused_chmod(path, *_arguments, **_keywords):
            raise PermissionError(errno.EPERM, "Operation not permitted", str(path))

        saved_gethostname = socket.gethostname
        socket.gethostname = lambda: hostname
        original_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{fake_ssh}{os.pathsep}{original_path}"
        os.environ[STAND_IN_RUNNER_BEHAVIOUR_FILE_VARIABLE] = str(behaviour_file)
        stdout, stderr = io.StringIO(), io.StringIO()
        code, raised = None, None
        try:
            if chmod_is_refused:
                os.chmod = refused_chmod
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = program.main([*self.arguments(clone), *extra_arguments], now=now,
                                    wait=wait, monotonic=lambda: clock[0])
        except Exception as error:  # every one fails the case that reads the result
            raised = error
        finally:
            os.environ["PATH"] = original_path
            os.environ.pop(STAND_IN_RUNNER_BEHAVIOUR_FILE_VARIABLE, None)
            socket.gethostname = saved_gethostname
            program.DAILY_FULL_TEST_RUN_LOCK_WAIT_BOUND_SECONDS = saved_bound
            os.chmod = saved_chmod
        ssh_calls_file = scratch / "ssh-calls"
        ssh_calls = (ssh_calls_file.read_text(encoding="utf-8").splitlines()
                     if ssh_calls_file.exists() else [])
        runner_calls = json.loads(calls_file.read_text()) if calls_file.exists() else []
        return RunResult(code, stdout.getvalue(), stderr.getvalue(), ssh_calls, runner_calls,
                         waits, raised)

    def environment_of_a_run_as_a_program(self, behaviour: dict):
        """(the environment the program is started in as its own process, the
        file the stand-in runner writes its calls to). ned-box is the fake ssh
        on either machine."""
        scratch = self.scratch_for_next_run()
        calls_file = scratch / "stand-in-runner-calls.json"
        behaviour_file = scratch / "stand-in-runner-behaviour.json"
        behaviour_file.write_text(json.dumps({**behaviour, "calls_file": str(calls_file)}),
                                  encoding="utf-8")
        fake_ssh = self.fake_ssh_directory(scratch, SSH_THAT_RUNS_THE_COMMAND_HERE)
        environment = (
            program.run_all_test_suites.environment_without_git_redirecting_variables())
        environment["PATH"] = f"{fake_ssh}{os.pathsep}{environment.get('PATH', '')}"
        environment[STAND_IN_RUNNER_BEHAVIOUR_FILE_VARIABLE] = str(behaviour_file)
        return environment, calls_file

    def worktree_is_registered(self) -> bool:
        return f"worktree {self.worktree}" in fixture_git(
            self.clone, "worktree", "list", "--porcelain").splitlines()

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


def command_printed_on_stderr_after(stderr: str, opening: str) -> str:
    """The command a line of stderr gives after `opening`, as printed; empty
    when no line has it, which no shell runs as anything."""
    for line in stderr.splitlines():
        if opening in line:
            return line.split(opening, 1)[1]
    return ""


def make_directory_writable_and_remove_it(directory: Path):
    """Remove what a case left at the worktree's path, so that a program that
    did not remove it fails that case alone."""
    if directory.is_dir():
        subprocess.run(["chmod", "-R", "u+rwx", str(directory)], check=False)
        subprocess.run(["rm", "-rf", str(directory)], check=False)


def wait_for_another_process_until(condition, gave_up=lambda: False):
    """condition()'s first true value, or None once
    WAIT_FOR_ANOTHER_PROCESS_BOUND_SECONDS have passed or gave_up() is true."""
    ends = time.monotonic() + WAIT_FOR_ANOTHER_PROCESS_BOUND_SECONDS
    while time.monotonic() < ends:
        value = condition()
        if value:
            return value
        if gave_up():
            return None
        time.sleep(0.02)
    return None


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
          "scripts/run-all-test-suites.py --log-dir <logs>, with no selection option, no -j "
          "and no --recorded-inputs-directory",
          len(result.runner_calls) == 1
          and call.get("argv") == [str(fixture.worktree / "scripts" / "run-all-test-suites.py"),
                                   "--log-dir", str(fixture.logs)]
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
    check("the record's local copy beside the logs, named by the record's date, is the "
          "record",
          fixture.local_copy("2026-09-30").is_file()
          and fixture.local_copy("2026-09-30").read_text(encoding="utf-8") == record,
          repr(sorted(path.name for path in fixture.directory.iterdir())))
    check("this program's lock is held while the runner runs: a second lock on the lock "
          "file, tried from inside the runner, is refused",
          call.get("daily_run_lock_was_free") is False, repr(result))

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
          len(result.runner_calls) == 1 and result.runner_calls[0]["log_dir_held"] is None
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

    # --- The runner step raises ------------------------------------------------------
    result = fixture.run(exits=(3,), wait_raises_at_once=True)
    check("when the runner step raises, what it raised leaves main and the worktree and "
          "its registration are removed all the same",
          isinstance(result.raised, StandInWaitRaised) and result.code is None
          and len(result.runner_calls) == 1 and result.waits == [2]
          and fixture.worktree_is_gone(),
          f"{result!r}\n{fixture_git(fixture.clone, 'worktree', 'list')}")

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
          == [str(stand_in_elsewhere), "--log-dir", str(fixture.logs)]
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

    # --- What git could not delete -----------------------------------------------------
    result = fixture.run(
        stand_in_runner_behaviour={"leaves_a_directory_its_owner_may_not_write_to": True})
    record_lines = (fixture.record("ned-box") or "").splitlines()
    check("a worktree the run left a directory in that its owner may not write to is "
          "removed by this program, registration and all, and the run's verdict stands",
          result.code == 0 and fixture.worktree_is_gone() and result.stderr == ""
          and PASSING_SUMMARY_LINE in record_lines
          and not any("was not removed" in line for line in record_lines),
          f"{result!r}\n{record_lines!r}")
    make_directory_writable_and_remove_it(fixture.worktree)

    # The program's own os.chmod is refused, which stands for a directory
    # whose mode it may not change, so the refusal is printed in the state the
    # remedy has to work in: once with the registration already dropped by
    # git, once with git still holding it.
    for registration, behaviour in (
            ("after git dropped the registration",
             {"leaves_a_directory_its_owner_may_not_write_to": True}),
            ("while git still has the registration",
             {"leaves_a_directory_its_owner_may_not_write_to": True,
              "removes_the_git_file_of_the_checkout": True})):
        result = fixture.run(stand_in_runner_behaviour=behaviour, chmod_is_refused=True)
        record_lines = (fixture.record("ned-box") or "").splitlines()
        remedy = (f"chmod -R u+rwx {fixture.worktree} && rm -rf {fixture.worktree} && "
                  f"git -C {fixture.clone} worktree prune")
        registered = fixture.worktree_is_registered()
        check(f"a worktree that was not removed, {registration}: the program exits 4, the "
              "record says the worktree was not removed, and stderr is what failed and the "
              "command that removes it",
              result.code == 4 and fixture.worktree.is_dir()
              and registered == (registration == "while git still has the registration")
              and any(line.startswith(f"the worktree {fixture.worktree} was not removed: ")
                      for line in record_lines)
              and PASSING_SUMMARY_LINE in record_lines
              and result.stderr.startswith("daily-full-test-run-of-main: the worktree "
                                           f"{fixture.worktree} was not removed: ")
              and result.stderr.endswith(f"\nRemove it with: {remedy}\n")
              and result.stderr.count("\n") == 2,
              f"registered: {registered}\n{result!r}\n{record_lines!r}")
        removed_by_hand = subprocess.run(
            ["/bin/sh", "-c", command_printed_on_stderr_after(result.stderr, "Remove it with: ")],
            env=program.run_all_test_suites.environment_without_git_redirecting_variables(),
            stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)
        check(f"the command stderr gives, run as written {registration}, removes the "
              "worktree's directory and leaves no registration",
              removed_by_hand.returncode == 0 and fixture.worktree_is_gone(),
              f"{removed_by_hand.returncode} {removed_by_hand.stderr}\n"
              f"{fixture_git(fixture.clone, 'worktree', 'list')}")
        make_directory_writable_and_remove_it(fixture.worktree)
        fixture_git(fixture.clone, "worktree", "prune")
        result = fixture.run()
        check(f"the next run goes ahead once that command has been run {registration}",
              result.code == 0 and fixture.worktree_is_gone(), repr(result))

    # --- git worktree add fails ----------------------------------------------------------
    fixture.worktree.write_text("a regular file where the worktree goes\n", encoding="utf-8")
    result = fixture.run()
    fixture.worktree.unlink()
    record_lines = (fixture.record("ned-box") or "").splitlines()
    what_failed = (f"not run — git worktree add --detach {fixture.worktree} "
                   f"{fixture.commit_of_main} failed in {fixture.clone}: fatal: "
                   f"'{fixture.worktree}' already exists")
    check("when git worktree add fails the record holds git's error line, not the progress "
          "line git writes before it, and the runner is not run",
          result.code == 4 and result.runner_calls == [] and what_failed in record_lines
          and not any("Preparing worktree" in line for line in record_lines),
          f"{result!r}\n{record_lines!r}")
    check("when git worktree add fails stderr is what failed, with git's error line, and "
          "what to do",
          result.stderr == f"daily-full-test-run-of-main: {what_failed}\n"
          "Fix what git reports, then run this again.\n", result.stderr)
    error_line = getattr(program, "first_fatal_or_error_stderr_line_or_no_detail", None)
    check("the error line of a failed git worktree add is the first line opening `error:` "
          "or `fatal:`; of one that wrote neither, its first line; of one that wrote "
          "nothing, `no detail`",
          error_line is not None
          and error_line("Preparing worktree (detached HEAD 0123456)\nerror: one\n"
                         "fatal: two\n") == "error: one"
          and error_line("a line\nanother\n") == "a line"
          and error_line("\n") == "no detail")

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
    fixture.local_copy("2026-09-30").unlink(missing_ok=True)
    fixture.local_copy("2026-09-30").mkdir()
    result = fixture.run(exits=(1,), lines=FAILING_RUNNER_LINES)
    fixture.local_copy("2026-09-30").rmdir()
    check("when the record's local copy cannot be written the program exits 5, leaves the "
          "log-store's record as it was, and says what failed and what to do",
          result.code == 5 and result.stdout == "" and fixture.record("ned-box") == record_before
          and result.stderr.startswith(
              "daily-full-test-run-of-main: the record was not written: its local copy "
              f"{fixture.local_copy('2026-09-30')} could not be written "
              "(IsADirectoryError: ")
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
              f"{target}' < {unreachable.local_copy('2026-09-30')}")
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
    local_copy = (unreachable.local_copy("2026-09-30").read_text(encoding="utf-8")
                  if unreachable.local_copy("2026-09-30").is_file() else None)
    check("the record that could not be written is kept beside the logs",
          local_copy is not None and PASSING_SUMMARY_LINE in local_copy.splitlines(),
          repr(local_copy))

    # The next day's run cannot reach ned-box either, and fails two suites.
    # Both days' commands are run only after it, each as stderr gave it.
    remedy_of_the_first_day = command_printed_on_stderr_after(
        result.stderr, "write the record by running on this machine: ")
    result = unreachable.run(hostname="a-mac-that-is-not-ned-box", exits=(1,),
                             lines=FAILING_RUNNER_LINES,
                             now=PACIFIC_EVENING_THAT_IS_TOMORROW_IN_UTC + timedelta(days=1),
                             ssh_body=SSH_THAT_CANNOT_REACH_NED_BOX)
    remedy_of_the_next_day = command_printed_on_stderr_after(
        result.stderr, "write the record by running on this machine: ")
    next_day_local_copy = (
        unreachable.local_copy("2026-10-01").read_text(encoding="utf-8")
        if unreachable.local_copy("2026-10-01").is_file() else None)
    check("the next day's run that cannot reach ned-box either exits 5, keeps its own "
          "record beside the logs and leaves the first day's as it was",
          result.code == 5 and unreachable.record_files() == []
          and next_day_local_copy is not None
          and FAILING_SUMMARY_LINE in next_day_local_copy.splitlines()
          and next_day_local_copy.startswith(
              "daily-full-test-run-of-main: mac, 2026-10-01 in America/Los_Angeles, ")
          and unreachable.local_copy("2026-09-30").is_file()
          and unreachable.local_copy("2026-09-30").read_text(encoding="utf-8") == local_copy,
          f"{result!r}\n{next_day_local_copy!r}")
    scratch = unreachable.scratch_for_next_run()
    reachable_again = unreachable.fake_ssh_directory(scratch, SSH_THAT_RUNS_THE_COMMAND_HERE)
    environment = program.run_all_test_suites.environment_without_git_redirecting_variables()
    environment["PATH"] = f"{reachable_again}{os.pathsep}{environment.get('PATH', '')}"
    written_by_hand = subprocess.run(["/bin/sh", "-c", remedy_of_the_first_day],
                                     env=environment, capture_output=True, text=True,
                                     check=False)
    check("the command the first day's stderr gave, run after the next day's run, writes "
          "the first day's record under the first day's name, and nothing else",
          remedy_of_the_first_day == remedy and written_by_hand.returncode == 0
          and local_copy is not None and unreachable.record("mac", "2026-09-30") == local_copy
          and local_copy.startswith(
              "daily-full-test-run-of-main: mac, 2026-09-30 in America/Los_Angeles, ")
          and unreachable.record_files() == ["daily-full-test-runs/mac/2026-09-30.txt"],
          f"{remedy_of_the_first_day!r}\n{written_by_hand.returncode} "
          f"{written_by_hand.stderr}\n{unreachable.record('mac', '2026-09-30')!r}")
    written_by_hand = subprocess.run(["/bin/sh", "-c", remedy_of_the_next_day],
                                     env=environment, capture_output=True, text=True,
                                     check=False)
    check("the command the next day's stderr gave writes the next day's record under the "
          "next day's name, and leaves the first day's as it was",
          written_by_hand.returncode == 0 and next_day_local_copy is not None
          and unreachable.record("mac", "2026-10-01") == next_day_local_copy
          and unreachable.record("mac", "2026-09-30") == local_copy
          and unreachable.record_files() == ["daily-full-test-runs/mac/2026-09-30.txt",
                                             "daily-full-test-runs/mac/2026-10-01.txt"],
          f"{remedy_of_the_next_day!r}\n{written_by_hand.returncode} "
          f"{written_by_hand.stderr}\n{unreachable.record('mac', '2026-10-01')!r}")


def run_cases_as_a_program(workspace: Path):
    """The program run as cron runs it: its own process, its real clock and
    wait, the moment taken from the machine. ned-box is the fake ssh on either
    machine, so the case holds on both."""
    fixture = Fixture(workspace / "as-a-program")
    environment, _ = fixture.environment_of_a_run_as_a_program(
        {"exits": [0], "lines": PASSING_RUNNER_LINES})
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


def run_cases_of_a_runner_that_outlives_the_program(workspace: Path):
    """Real processes: a daily run is stopped by its process ID while its
    runner runs, and the runner, which tests in the worktree, still holds the
    daily run's lock; a process the runner started does not."""
    fixture = Fixture(workspace / "a-runner-that-outlives-the-program")
    files = fixture.scratch_for_next_run()
    started_file = files / "started.json"
    released_file = files / "released"
    process_released_file = files / "process-released"
    process_acknowledgment_file = files / "process-acknowledgment"
    left_in_the_worktree = fixture.worktree / FILE_LEFT_IN_THE_WORKTREE_BY_THE_WAITING_RUNNER
    refusal = ("daily-full-test-run-of-main: not run — another daily full test run holds "
               f"{fixture.lock_file}.\nRun this again after that run has finished.\n")

    def daily_run_as_a_program():
        """(the finished run, the calls its stand-in runner wrote down)."""
        environment, calls_file = fixture.environment_of_a_run_as_a_program(
            {"exits": [0], "lines": PASSING_RUNNER_LINES})
        completed = subprocess.run([sys.executable, str(SCRIPT_PATH), *fixture.arguments()],
                                   env=environment, stdin=subprocess.DEVNULL,
                                   capture_output=True, text=True, check=False)
        return completed, json.loads(calls_file.read_text()) if calls_file.exists() else []

    def lock_can_be_taken():
        with open(fixture.lock_file, "a") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return False
            return True

    def refused_and_worktree_untouched(completed, calls):
        return (completed.returncode == 6 and calls == [] and completed.stdout == ""
                and completed.stderr == refusal and left_in_the_worktree.is_file()
                and fixture.worktree_is_registered() and fixture.record_files() == [])

    environment, _ = fixture.environment_of_a_run_as_a_program({
        "exits": [0], "lines": PASSING_RUNNER_LINES,
        "waits_until_released": {
            "started_file": str(started_file), "released_file": str(released_file),
            "process_released_file": str(process_released_file),
            "process_acknowledgment_file": str(process_acknowledgment_file),
            "own_bound_seconds": STAND_IN_PROCESS_OWN_BOUND_SECONDS}})
    first = subprocess.Popen([sys.executable, str(SCRIPT_PATH), *fixture.arguments()],
                             env=environment, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        started = wait_for_another_process_until(lambda: started_file.is_file() and json.loads(
            started_file.read_text()), gave_up=lambda: first.poll() is not None)
        check("a daily run started as a program is in its runner, which has started a "
              "process of its own and left a file in the worktree",
              started is not None and first.poll() is None and left_in_the_worktree.is_file(),
              f"started: {started!r}; the daily run's exit: {first.poll()!r}")

        completed, calls = daily_run_as_a_program()
        check("while a daily run is in its runner, a second daily run exits 6, runs nothing "
              "and leaves the worktree alone",
              refused_and_worktree_untouched(completed, calls),
              f"{completed.returncode}\n{completed.stdout}\n{completed.stderr}\n{calls!r}")

        if first.poll() is None:
            os.kill(first.pid, signal.SIGKILL)
        first.wait()
        runner_is_running = False
        if started:
            try:
                os.kill(started["runner_pid"], 0)
                runner_is_running = not released_file.exists()
            except OSError:
                pass
        check("the daily run is stopped with SIGKILL by its process ID, and its runner is "
              "still running",
              first.returncode == -signal.SIGKILL and runner_is_running,
              f"{first.returncode} {started!r}")
        completed, calls = daily_run_as_a_program()
        check("after a daily run is stopped by its process ID, while the runner it started "
              "is still running, a second daily run exits 6, runs nothing and leaves the "
              "worktree alone",
              refused_and_worktree_untouched(completed, calls),
              f"{completed.returncode}\n{completed.stdout}\n{completed.stderr}\n{calls!r}")

        released_file.write_text("", encoding="utf-8")
        lock_was_released = wait_for_another_process_until(lock_can_be_taken)
        completed, calls = daily_run_as_a_program()
        process_released_file.write_text("", encoding="utf-8")
        acknowledged = wait_for_another_process_until(process_acknowledgment_file.is_file)
        check("once that runner has exited the lock is free and a daily run goes ahead, "
              "replacing the worktree the stopped run left, though the process the runner "
              "started is still running",
              lock_was_released is True and completed.returncode == 0 and len(calls) == 1
              and calls[0]["commit"] == fixture.commit_of_main
              and fixture.worktree_is_gone() and acknowledged is True,
              f"lock released: {lock_was_released!r}; acknowledged: {acknowledged!r}\n"
              f"{completed.returncode}\n{completed.stdout}\n{completed.stderr}\n{calls!r}")
    finally:
        # Whatever a failed case left running ends here: the daily run by its
        # process ID, the stand-in runner and its process by their files.
        released_file.write_text("", encoding="utf-8")
        process_released_file.write_text("", encoding="utf-8")
        if first.poll() is None:
            first.kill()
            first.wait()


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
    run_cases_of_a_runner_that_outlives_the_program(workspace_root)
    run_log_store_readme_cases()

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
