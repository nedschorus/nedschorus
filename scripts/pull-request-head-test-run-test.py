#!/usr/bin/env python3
"""Tests for pull-request-head-test-run.py.

Run: python3 scripts/pull-request-head-test-run-test.py

No case reaches anything real. The checkout under test is a fixture clone of
a bare repository in the same scratch directory, one commit ahead of the
commit it left main at, with main moved on since; the log-store's root and the
temporary directory are scratch directories, passed on every call; the runner
is a stand-in, committed to the fixture's main as
scripts/run-all-test-suites.py and run from a second clone that plays main's,
which prints lines in the real runner's shapes and exits as the case tells
it; ned-box is played by an ssh first on PATH that records its arguments and
runs the command it was handed here; the machine's name is set per case; and
the moment, the wait and the clock are passed in, so no case sleeps.
Each run a fixture makes reads a process number of its own, as each real run
has one. The far side of an ssh whose client has died is played by the command
run with stderr a pipe whose reader is gone, and a preferred encoding that is
not UTF-8 by a `locale` the program is handed for one run. Two writers at once
are played by holding the first writer's input while the second writes; a
write the test log takes part of, by the shell's limit on the size of a file. The one case that passes no
--test-suite-runner-program replaces the function that runs the runner, so
the real runner beside the program is named and never started. The wait
passed in counts its calls and stops a case that waits more often than any
case's bound allows, so a wait that lost its bound fails its case and does
not hang the suite.

Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import types
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().with_name("pull-request-head-test-run.py")
REPOSITORY_ROOT = SCRIPT_PATH.parent.parent

_spec = importlib.util.spec_from_file_location("pull_request_head_test_run", SCRIPT_PATH)
program = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(program)

_shipper_spec = importlib.util.spec_from_file_location(
    "cold_read_record_ship",
    REPOSITORY_ROOT / "nc-systems" / "cold-read" / "cold-read-record-ship.py")
record_shipper = importlib.util.module_from_spec(_shipper_spec)
_shipper_spec.loader.exec_module(record_shipper)

daily = program.daily_full_test_run_of_main

failures = []

THE_MOMENT = datetime(2026, 10, 1, 3, 30, tzinfo=timezone.utc)
AN_EARLIER_MOMENT = datetime(2026, 10, 1, 3, 0, tzinfo=timezone.utc)
A_LATER_MOMENT = datetime(2026, 10, 1, 4, 0, tzinfo=timezone.utc)

# No case asks for more waits than this: the longest, a bound of 6 seconds at
# 2 seconds a wait, asks for 3. A run that waits more often has lost its
# bound, and is stopped here so that its case fails.
MOST_WAITS_A_CASE_ASKS_FOR = 10
WAITED_MORE_OFTEN_THAN_ANY_CASE_ASKS_FOR = "waited more often than any case asks for"


class WaitedMoreOftenThanAnyCaseAsksFor(Exception):
    pass

SSH_THAT_RUNS_THE_COMMAND_HERE = 'exec /bin/sh -c "$1"'
# The far side of an ssh whose client died while the far side was still
# reading: the command gets the first bytes of the record, or none, and then
# an end of input like any other.
SSH_THAT_HANDS_OVER_300_BYTES = 'head -c 300 | /bin/sh -c "$1"'
SSH_THAT_HANDS_OVER_NOTHING = '/bin/sh -c "$1" < /dev/null'
# An ssh whose client died after the far side had finished: the command runs
# to its end here, and the exit status that comes back is the client's own.
SSH_THAT_RUNS_THE_COMMAND_HERE_AND_THEN_FAILS = (
    '/bin/sh -c "$1"\necho "ssh: the connection was lost" >&2\nexit 255')
SSH_THAT_CANNOT_REACH_NED_BOX = (
    "echo 'ssh: connect to host ned-box port 22: No route to host' >&2\n"
    "echo 'a second line' >&2\nexit 255")

STAND_IN_RUNNER_BEHAVIOUR_FILE_VARIABLE = (
    "PULL_REQUEST_HEAD_TEST_RUN_STAND_IN_RUNNER_BEHAVIOUR_FILE")

# Played for scripts/run-all-test-suites.py. It writes down how it was called,
# where it was run from and what the checkout it was handed is at, then prints
# what the real runner prints, in the real runner's shapes: its first line,
# the line saying how inputs are recorded, then the case's lines, and exits as
# the case says. Exit 3 and exit 2 print the real runner's refusals on stderr
# and nothing on stdout. A negative exit is the signal the stand-in kills
# itself with. Like the real runner it reads the checkout's commit and whether
# a tracked file differs once, for its first line. A run that gets past the
# lock can then change the checkout, as a seat working in the checkout would
# while the suites run: the behaviour file's `files_written_in_the_checkout`
# and `git_commands_run_in_the_checkout`. Three more keys make a runner the
# real one is not: `lines_printed_before_the_first_line`;
# `characters_of_the_commit_named_in_the_first_line`, for a first line that
# names the commit by the start of its hash; and
# `signal_that_kills_the_runner_after_its_last_line`.
STAND_IN_RUNNER_SOURCE = r'''
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

behaviour = json.loads(Path(os.environ[
    "PULL_REQUEST_HEAD_TEST_RUN_STAND_IN_RUNNER_BEHAVIOUR_FILE"]).read_text())
calls_file = Path(behaviour["calls_file"])
calls = json.loads(calls_file.read_text()) if calls_file.exists() else []
arguments = sys.argv[1:]
log_dir = Path(arguments[arguments.index("--log-dir") + 1])
checkout = Path(arguments[arguments.index("--checkout") + 1])
since = arguments[arguments.index("--only-suites-whose-recorded-inputs-changed-since") + 1]
commit = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"],
                        capture_output=True, text=True, check=False).stdout.strip()
changed = subprocess.run(["git", "-C", str(checkout), "status", "--porcelain",
                          "--untracked-files=no"],
                         capture_output=True, text=True, check=False).stdout.strip()
state = ("tracked files differ from that commit" if changed
         else "tracked files match that commit")
exit_code = behaviour["exits"][min(len(calls), len(behaviour["exits"]) - 1)]
calls.append({
    "argv": sys.argv,
    "executable": sys.executable,
    "run_from": str(Path.cwd()),
    "commit": commit,
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
for path, text in behaviour.get("files_written_in_the_checkout", {}).items():
    (checkout / path).write_text(text)
for git_arguments in behaviour.get("git_commands_run_in_the_checkout", []):
    subprocess.run(["git", "-C", str(checkout), *git_arguments], capture_output=True,
                   text=True, check=True)
log_dir.mkdir(parents=True, exist_ok=True)
(log_dir / ("log-of-call-%d.log" % len(calls))).write_text("a suite's output\n")
for line in behaviour.get("lines_printed_before_the_first_line", []):
    print(line)
print("run-all-test-suites: %s at %s (%s); 3 suites listed by "
      "git; 2 selected by inputs changed since %s; Python 3.14.4 (%s); -j 4; logs in %s"
      % (checkout,
         commit[:behaviour.get("characters_of_the_commit_named_in_the_first_line", 40)],
         state, since[:12], sys.executable, log_dir))
print("inputs recorded by python-audit-hook, kept in /a/recordings/directory")
for line in behaviour["lines"]:
    print(line)
if behaviour.get("signal_that_kills_the_runner_after_its_last_line"):
    sys.stdout.flush()
    os.kill(os.getpid(), behaviour["signal_that_kills_the_runner_after_its_last_line"])
sys.exit(exit_code)
'''

INPUTS_RECORDED_LINE = "inputs recorded by python-audit-hook, kept in /a/recordings/directory"
SELECTION_LINES = [
    "SELECTED scripts/a-test.py: it reads scripts/a.py, which differs",
    "SELECTED scripts/b-test.py: the suite itself differs",
    "NOT SELECTED scripts/c-test.py: none of the 4 files it read differs since 0123456789ab",
]
SKIPPED_CASE_LINE = "scripts/b-test.py: SKIP the end-to-end case: tmux is not installed"
PASSING_SUMMARY_LINE = ("SUMMARY: 2 passed, 0 failed, 2 total; 1 cases skipped in 1 suites; "
                        "head at 0123456789ab; Python 3.14.4; 1 suites not selected, their "
                        "recorded inputs unchanged since 0123456789ab")
PASSING_RUNNER_LINES = [
    *SELECTION_LINES,
    "PASS scripts/a-test.py (0.1s)",
    "PASS scripts/b-test.py (0.2s, 1 skipped)",
    "",
    "skipped cases:",
    SKIPPED_CASE_LINE,
    PASSING_SUMMARY_LINE,
]
FAILING_SUMMARY_LINE = ("SUMMARY: 1 passed, 1 failed, 2 total; 1 cases skipped in 1 suites; "
                        "head at 0123456789ab; Python 3.14.4; 1 suites not selected, their "
                        "recorded inputs unchanged since 0123456789ab")
FAILING_RUNNER_LINES = [
    *SELECTION_LINES,
    "PASS scripts/a-test.py (0.1s)",
    "FAIL scripts/b-test.py exit 1 (0.2s, 1 skipped)",
    "",
    "1 failed:",
    "FAIL scripts/b-test.py exit 1 — log /a/log/directory/scripts__b-test.py.log",
    "",
    "skipped cases:",
    SKIPPED_CASE_LINE,
    FAILING_SUMMARY_LINE,
]

THE_REFERENCE_CLONES_RUNNER = object()

A_RECORDS_FIRST_LINE = re.compile(
    r"pull-request-head-test-run: (ned-box|mac), started "
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z, a record of (\d+) lines")


def records_of_a_test_log(text: str):
    """The records a test log holds, in the order they were written, read the
    way the program's docstring tells a reader to: a first line says how many
    lines its record has, and the line after those is the next record's first
    line. None when the text does not read that way: a line that should be a
    first line is not one, a record is shorter than its count, or a record's
    last line is not the line that gives the program's exit code."""
    if text and not text.endswith("\n"):
        return None
    # A line ends at a line feed and nowhere else.
    lines = text.split("\n")[:-1]
    records = []
    at = 0
    while at < len(lines):
        first_line = A_RECORDS_FIRST_LINE.fullmatch(lines[at])
        if first_line is None:
            return None
        count = int(first_line.group(2))
        record = lines[at:at + count]
        if (len(record) != count
                or re.fullmatch(r"pull-request-head-test-run exit code: \d+",
                                record[-1]) is None):
            return None
        records.append("".join(line + "\n" for line in record))
        at += count
    return records


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def fixture_git(directory: Path, *arguments) -> str:
    """One git command in a fixture directory, with the variables that send
    git into another repository dropped; its stdout. A command that fails
    stops the suite, so no case runs against a repository that was not made."""
    completed = subprocess.run(
        ["git", "-C", str(directory), "-c", "user.name=pull-request-head-test-run-fixture",
         "-c", "user.email=pull-request-head-test-run-fixture@example.invalid",
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
    """A bare repository playing origin; a clone of it left at main's first
    commit, which plays main's clone and holds the stand-in runner; a second
    clone, the checkout under test, on a branch one commit ahead of that first
    commit, which has fetched a main that moved on; a scratch log-store root
    and a scratch temporary directory."""

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
        self.reference = self.clone_of_origin("reference")
        self.runner = self.reference / "scripts" / "run-all-test-suites.py"
        self.merge_base = fixture_git(self.reference, "rev-parse", "HEAD")
        self.checkout = self.clone_of_origin("head")
        fixture_git(self.checkout, "checkout", "-q", "-b", "a-topic-branch")
        (self.checkout / "a-change.txt").write_text("the change\n", encoding="utf-8")
        fixture_git(self.checkout, "add", "-A")
        fixture_git(self.checkout, "commit", "-q", "-m", "the pull request's change")
        self.head = fixture_git(self.checkout, "rev-parse", "HEAD")
        # main moves on, and the checkout's clone fetches it, so the merge base
        # is neither the head nor main's tip.
        (seed / "a-later-file.txt").write_text("added to main later\n", encoding="utf-8")
        fixture_git(seed, "add", "-A")
        fixture_git(seed, "commit", "-q", "-m", "main moves on")
        fixture_git(seed, "push", "-q", str(self.origin), "main")
        self.commit_of_main = fixture_git(seed, "rev-parse", "HEAD")
        fixture_git(self.checkout, "fetch", "-q", "origin")
        self.log_store = root / "log-store"
        self.temporary = root / "temporary"
        self.temporary.mkdir()
        self.run_count = 0
        # Each run reads a process number of its own: see the module docstring.
        self.process_number_of_the_newest_run = os.getpid()
        # How many runs printed each citation, by the path under the log-store.
        self.runs_that_cited = {}

    def clone_of_origin(self, name: str) -> Path:
        clone = self.root / name
        fixture_git(self.root, "clone", "-q", str(self.origin), str(clone))
        if not (clone / ".git").is_dir():
            raise SystemExit(f"fixture: no clone was made at {clone}")
        return clone

    def run_directory(self, head=None, moment=THE_MOMENT) -> Path:
        """The directory the newest run, made at the moment, keeps its logs
        and the record's local copy in."""
        return (self.temporary / program.PULL_REQUEST_HEAD_TEST_RUN_DIRECTORY_NAME
                / f"{head or self.head}-{moment:%Y%m%dT%H%M%SZ}-"
                  f"{self.process_number_of_the_newest_run}")

    def logs(self, head=None) -> Path:
        return self.run_directory(head) / program.PULL_REQUEST_HEAD_TEST_RUN_LOGS_DIRECTORY_NAME

    def local_copy(self, head=None, moment=THE_MOMENT) -> Path:
        return (self.run_directory(head, moment)
                / program.PULL_REQUEST_HEAD_TEST_RUN_RECORD_LOCAL_COPY_FILE_NAME)

    def write_command(self, machine: str, record: str):
        """The shell command a run of the head adds the record with, which is
        also the command its refusal prints for a failed write. No path of a
        fixture needs quoting, and the program the command holds has no
        single quote, as run_cases_of_what_the_write_command_holds says. The
        count is the record's UTF-8 length: where this suite runs the
        preferred encoding is UTF-8, and run_cases_of_the_two_byte_counts
        tells the two counts apart."""
        return (f"exec python3 -c '{program.PULL_REQUEST_HEAD_TEST_LOG_APPEND_PROGRAM}' "
                f"{self.log_store}/pull-request-head-test-runs/{machine}/{self.head}.txt "
                f"{len(record.encode('utf-8'))}")

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

    def arguments(self, checkout=None, runner_program=THE_REFERENCE_CLONES_RUNNER):
        arguments = ["--checkout", str(checkout or self.checkout),
                     "--log-store-root", str(self.log_store),
                     "--temporary-directory", str(self.temporary)]
        if runner_program is THE_REFERENCE_CLONES_RUNNER:
            runner_program = self.runner
        if runner_program is not None:
            arguments += ["--test-suite-runner-program", str(runner_program)]
        return arguments

    def run(self, exits=(0,), lines=PASSING_RUNNER_LINES, hostname="ned-box",
            ssh_body=SSH_THAT_RUNS_THE_COMMAND_HERE, extra_arguments=(), checkout=None,
            runner_program=THE_REFERENCE_CLONES_RUNNER,
            lock_wait_bound_seconds=None, during_each_wait=None,
            runner_changes_the_checkout=None, moment=THE_MOMENT,
            started_in=None, stand_in_runner_behaviour=None) -> RunResult:
        """main's exit code and output, with the fake ssh's calls, the stand-in
        runner's calls and the waits main asked for. The clock is the sum of
        those waits, so a case takes no time. during_each_wait is called in
        each wait, to change the checkout while the program waits for the
        lock; runner_changes_the_checkout is what the stand-in runner does to
        the checkout once it is past the lock; stand_in_runner_behaviour is
        any other key of the stand-in runner's behaviour file. The run reads
        a process number no other run of this fixture has read, which names
        the run's directory. A run that waits more often than any case asks
        for is stopped, and its exit code is
        WAITED_MORE_OFTEN_THAN_ANY_CASE_ASKS_FOR."""
        scratch = self.scratch_for_next_run()
        process_number = os.getpid() + self.run_count
        self.process_number_of_the_newest_run = process_number
        behaviour_file = scratch / "stand-in-runner-behaviour.json"
        calls_file = scratch / "stand-in-runner-calls.json"
        behaviour_file.write_text(json.dumps(
            {"exits": list(exits), "lines": list(lines), "calls_file": str(calls_file),
             **(runner_changes_the_checkout or {}),
             **(stand_in_runner_behaviour or {})}),
            encoding="utf-8")
        fake_ssh = self.fake_ssh_directory(scratch, ssh_body)
        waits = []
        clock = [0.0]

        def wait(seconds):
            waits.append(seconds)
            if len(waits) > MOST_WAITS_A_CASE_ASKS_FOR:
                raise WaitedMoreOftenThanAnyCaseAsksFor()
            clock[0] += seconds
            if during_each_wait is not None:
                during_each_wait()

        saved_bound = daily.DAILY_FULL_TEST_RUN_LOCK_WAIT_BOUND_SECONDS
        if lock_wait_bound_seconds is not None:
            daily.DAILY_FULL_TEST_RUN_LOCK_WAIT_BOUND_SECONDS = lock_wait_bound_seconds
        saved_gethostname = socket.gethostname
        socket.gethostname = lambda: hostname
        saved_getpid = os.getpid
        os.getpid = lambda: process_number
        original_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{fake_ssh}{os.pathsep}{original_path}"
        os.environ[STAND_IN_RUNNER_BEHAVIOUR_FILE_VARIABLE] = str(behaviour_file)
        stdout, stderr = io.StringIO(), io.StringIO()
        directory_before = os.getcwd()
        if started_in is not None:
            os.chdir(started_in)
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                try:
                    code = program.main(
                        [*self.arguments(checkout, runner_program), *extra_arguments],
                        now=moment, wait=wait, monotonic=lambda: clock[0])
                except WaitedMoreOftenThanAnyCaseAsksFor:
                    code = WAITED_MORE_OFTEN_THAN_ANY_CASE_ASKS_FOR
        finally:
            os.chdir(directory_before)
            os.environ["PATH"] = original_path
            os.environ.pop(STAND_IN_RUNNER_BEHAVIOUR_FILE_VARIABLE, None)
            os.getpid = saved_getpid
            socket.gethostname = saved_gethostname
            daily.DAILY_FULL_TEST_RUN_LOCK_WAIT_BOUND_SECONDS = saved_bound
        ssh_calls_file = scratch / "ssh-calls"
        ssh_calls = (ssh_calls_file.read_text(encoding="utf-8").splitlines()
                     if ssh_calls_file.exists() else [])
        runner_calls = json.loads(calls_file.read_text()) if calls_file.exists() else []
        cited = re.search(rf"^pull-request-head-test-run: record written to nedlern@ned-box:"
                          rf"{re.escape(str(self.log_store))}/(.+)$", stdout.getvalue(), re.M)
        if cited is not None:
            self.runs_that_cited[cited.group(1)] = (
                self.runs_that_cited.get(cited.group(1), 0) + 1)
        return RunResult(code, stdout.getvalue(), stderr.getvalue(), ssh_calls, runner_calls,
                         waits)

    def record_files(self):
        """Every file under the log-store root, relative to it."""
        return sorted(str(path.relative_to(self.log_store))
                      for path in self.log_store.rglob("*") if path.is_file())

    def test_log(self, machine: str, head=None):
        """The whole text of the head's test log on the machine, or None
        when there is none."""
        path = (self.log_store / program.PULL_REQUEST_HEAD_TEST_RUNS_KIND_DIRECTORY_NAME
                / machine / f"{head or self.head}.txt")
        return path.read_text(encoding="utf-8") if path.is_file() else None

    def records(self, machine: str, head=None):
        """The records in the head's test log on the machine, in the order
        they were written: none when there is no test log, and None when the
        test log does not read record by record."""
        test_log = self.test_log(machine, head)
        return [] if test_log is None else records_of_a_test_log(test_log)

    def record(self, machine: str, head=None):
        """The record written last to the head's test log on the machine,
        or None when the test log holds none or does not read record by
        record."""
        records = self.records(machine, head)
        return records[-1] if records else None

    def runner_first_line(self, since=None) -> str:
        return (f"run-all-test-suites: {self.checkout} at {self.head} (tracked files match "
                f"that commit); 3 suites listed by git; 2 selected by inputs changed since "
                f"{(since or self.merge_base)[:12]}; Python 3.14.4 ({sys.executable}); "
                f"-j 4; logs in {self.logs()}")


def run_cases_on_ned_box(workspace: Path):
    fixture = Fixture(workspace / "on-ned-box")
    record_path = f"pull-request-head-test-runs/ned-box/{fixture.head}.txt"
    citation_line = ("pull-request-head-test-run: record written to nedlern@ned-box:"
                     f"{fixture.log_store}/{record_path}\n")

    # --- A passing run ------------------------------------------------------
    result = fixture.run()
    record = fixture.record("ned-box")
    call = result.runner_calls[0] if result.runner_calls else {}
    check("a passing run exits 0", result.code == 0, repr(result))
    check("on ned-box the record is written locally, with no ssh, as "
          "pull-request-head-test-runs/ned-box/<the head's full hash>.txt",
          fixture.record_files() == [record_path] and len(fixture.head) == 40
          and result.ssh_calls == [], f"{fixture.record_files()} {result!r}")
    check("the whole record: this program's line, which counts the record's lines, the "
          "head, the commit the selection started from, the runner and its commit, the "
          "runner's whole output, the exit code, both counts of seconds and the logs' "
          "directory",
          record == "\n".join([
              "pull-request-head-test-run: ned-box, started 2026-10-01T03:30:00Z, a record "
              f"of {12 + len(PASSING_RUNNER_LINES)} lines",
              f'head: commit {fixture.head} ("the pull request\'s change")',
              f'selecting since: commit {fixture.merge_base} ("the stand-in runner"), the '
              "merge base of the head and refs/remotes/origin/main",
              f'runner: {fixture.runner}, from commit {fixture.merge_base} ("the stand-in '
              'runner")',
              f"the runner's output, {2 + len(PASSING_RUNNER_LINES)} lines:",
              fixture.runner_first_line(),
              INPUTS_RECORDED_LINE,
              *PASSING_RUNNER_LINES,
              "runner exit code: 0",
              "seconds waiting for the machine's lock: 0",
              "wall-clock seconds: 0",
              f"logs: {fixture.logs()} on ned-box",
              "pull-request-head-test-run exit code: 0",
          ]) + "\n", repr(record))
    check("a passing run's record closes with this program's own exit code, 0",
          record is not None
          and record.splitlines()[-1] == "pull-request-head-test-run exit code: 0",
          repr(record))
    check("the record says of every suite whether it was selected and why, and of every "
          "suite run whether it passed",
          record is not None and all(line in record.splitlines() for line in SELECTION_LINES)
          and "PASS scripts/a-test.py (0.1s)" in record.splitlines(), repr(record))
    check("stdout is the runner's SUMMARY line, then the record's citation in the scp form",
          result.stdout == PASSING_SUMMARY_LINE + "\n" + citation_line, result.stdout)
    check("the runner is run once, by the Python running this program, from the checkout, "
          "as <runner> --checkout <checkout> "
          "--only-suites-whose-recorded-inputs-changed-since <since> --log-dir <logs>, "
          "with no -j and no --recorded-inputs-directory",
          len(result.runner_calls) == 1
          and call.get("argv") == [
              str(fixture.runner), "--checkout", str(fixture.checkout),
              "--only-suites-whose-recorded-inputs-changed-since", fixture.merge_base,
              "--log-dir", str(fixture.logs())]
          and call.get("run_from") == str(fixture.checkout)
          and os.path.realpath(call.get("executable", "")) == os.path.realpath(sys.executable),
          repr(result))
    check("the selection starts from the merge base, which is neither the head nor the "
          "tip of the main the clone has fetched",
          len({fixture.merge_base, fixture.head, fixture.commit_of_main}) == 3
          and fixture_git(fixture.checkout, "rev-parse", "refs/remotes/origin/main")
          == fixture.commit_of_main
          and call.get("argv", [None] * 5)[4] == fixture.merge_base, repr(result))
    check("the checkout is left on its branch at the head with no tracked file changed",
          fixture_git(fixture.checkout, "rev-parse", "HEAD") == fixture.head
          and fixture_git(fixture.checkout, "symbolic-ref", "--short", "HEAD")
          == "a-topic-branch"
          and fixture_git(fixture.checkout, "status", "--porcelain",
                          "--untracked-files=no") == "")
    check("the record's local copy beside the logs is the record",
          fixture.local_copy().is_file()
          and fixture.local_copy().read_text(encoding="utf-8") == record,
          repr(fixture.local_copy()))
    check("the first run of a head makes the test log, which is that run's record and "
          "nothing more",
          record is not None and fixture.test_log("ned-box") == record,
          repr(fixture.test_log("ned-box")))
    record_of_the_passing_run = record

    # --- A failing run of the same head --------------------------------------
    result = fixture.run(exits=(1,), lines=FAILING_RUNNER_LINES)
    record = fixture.record("ned-box")
    record_lines = record.splitlines() if record else []
    check("a failing run exits with the runner's exit code", result.code == 1, repr(result))
    heading = f"the runner's output, {2 + len(FAILING_RUNNER_LINES)} lines:"
    output_starts = record_lines.index(heading) + 1 if heading in record_lines else 0
    check("a failing run's record holds every line the runner printed, in the runner's "
          "order, the passing suite's line among them, and exit code 1",
          record_lines[output_starts:output_starts + 2 + len(FAILING_RUNNER_LINES)]
          == [fixture.runner_first_line(), INPUTS_RECORDED_LINE, *FAILING_RUNNER_LINES]
          and "runner exit code: 1" in record_lines, repr(record))
    check("a failing run's record closes with this program's own exit code, 1",
          record_lines[-1:] == ["pull-request-head-test-run exit code: 1"], repr(record))
    check("a failing run prints the runner's SUMMARY line and the citation",
          result.stdout == FAILING_SUMMARY_LINE + "\n" + citation_line, result.stdout)
    check("a second run of the same head on the same machine adds its record to the end "
          "of the same file: one file, the first run's record still there byte for byte "
          "and first, the second run's record after it, and nothing more",
          fixture.record_files() == [record_path] and record is not None
          and record_of_the_passing_run is not None
          and fixture.test_log("ned-box") == record_of_the_passing_run + record
          and fixture.records("ned-box") == [record_of_the_passing_run, record]
          and PASSING_SUMMARY_LINE not in record_lines,
          f"{fixture.record_files()} {fixture.test_log('ned-box')!r}")
    record_of_the_failing_run = record

    # --- The two ways a later run used to replace an earlier result ---------------
    # A run told to select from the head itself selects no suite and passes.
    nothing_selected = [
        "NOT SELECTED scripts/a-test.py: none of the 4 files it read differs since "
        f"{fixture.head[:12]}",
        "SUMMARY: 0 passed, 0 failed, 0 total; 0 cases skipped in 0 suites; head at "
        f"{fixture.head[:12]}; Python 3.14.4; 3 suites not selected, their recorded inputs "
        f"unchanged since {fixture.head[:12]}"]
    result = fixture.run(lines=nothing_selected, extra_arguments=["--since", fixture.head])
    records = fixture.records("ned-box") or []
    check("after a run that failed a suite, a run of the same head that selects no suite "
          "exits 0 and adds its record: the failing run's record is still in the test log "
          "byte for byte, with its FAIL line and its exit code 1",
          result.code == 0 and len(records) == 3
          and records[:2] == [record_of_the_passing_run, record_of_the_failing_run]
          and "FAIL scripts/b-test.py exit 1 (0.2s, 1 skipped)"
              in records[1].splitlines()
          and records[1].splitlines()[-1] == "pull-request-head-test-run exit code: 1"
          and nothing_selected[1] in records[2].splitlines()
          and records[2].splitlines()[-1] == "pull-request-head-test-run exit code: 0",
          f"{result!r}\n{fixture.test_log('ned-box')!r}")
    result = fixture.run(exits=(2,))
    records_after = fixture.records("ned-box") or []
    check("a run whose runner could not start adds a record that says so, and every "
          "earlier record is still in the test log byte for byte",
          result.code == 2 and len(records_after) == 4 and records_after[:3] == records
          and "runner exit code: 2" in records_after[3].splitlines(),
          f"{result!r}\n{fixture.test_log('ned-box')!r}")

    # --- --since ---------------------------------------------------------------
    result = fixture.run(extra_arguments=["--since", fixture.commit_of_main[:12]])
    record_lines = (fixture.record("ned-box") or "").splitlines()
    check("--since is resolved to its full hash and is the commit the selection starts "
          "from, in place of the merge base",
          result.code == 0 and result.runner_calls[0]["argv"][4] == fixture.commit_of_main
          and f'selecting since: commit {fixture.commit_of_main} ("main moves on"), given as '
              "--since" in record_lines, f"{result!r}\n{record_lines!r}")
    result = fixture.run(extra_arguments=["--since", "no-such-commit"])
    record_lines = (fixture.record("ned-box") or "").splitlines()
    check("a --since git cannot resolve is a failed step: the runner is not run, the record "
          "says so, and the program exits 4",
          result.code == 4 and result.runner_calls == []
          and f"not run — git cannot resolve --since no-such-commit to a commit in "
              f"{fixture.checkout}" in record_lines
          and "selecting since: not resolved" in record_lines
          and "runner exit code: none, the runner was not run" in record_lines
          and result.stderr.endswith(
              "\nPass --since a commit this checkout has, then run this again.\n")
          and result.stdout == citation_line, f"{result!r}\n{record_lines!r}")
    check("the record of a run whose runner was not run closes with this program's own "
          "exit code, 4",
          result.code == 4
          and record_lines[-1:] == ["pull-request-head-test-run exit code: 4"],
          repr(record_lines))

    # --- A checkout that does not hold the head's files ------------------------
    test_log_before = fixture.test_log("ned-box")
    (fixture.checkout / "a-change.txt").write_text("changed after the commit\n",
                                                   encoding="utf-8")
    result = fixture.run()
    check("a checkout with a tracked file that differs from its commit is refused: exit 2, "
          "the runner is not run, no record is written, and stderr is what differs and "
          "what to pass",
          result.code == 2 and result.runner_calls == [] and result.stdout == ""
          and fixture.record_files() == [record_path]
          and fixture.test_log("ned-box") == test_log_before
          and result.stderr == "pull-request-head-test-run: not run — a tracked file in "
          f"{fixture.checkout} differs from its commit {fixture.head}: a-change.txt\n"
          "Pass --checkout a checkout whose tracked files match the commit to test, such as "
          "a detached worktree at that commit.\n", repr(result))
    fixture_git(fixture.checkout, "add", "a-change.txt")
    result = fixture.run()
    check("a change that is staged and nothing more is refused the same way",
          result.code == 2 and result.runner_calls == [] and result.stdout == ""
          and fixture.test_log("ned-box") == test_log_before
          and result.stderr.startswith(
              "pull-request-head-test-run: not run — a tracked file in "
              f"{fixture.checkout} differs from its commit {fixture.head}: a-change.txt\n"),
          repr(result))
    fixture_git(fixture.checkout, "reset", "-q", "--hard", fixture.head)
    (fixture.checkout / "a-file-added-to-the-index.txt").write_text("new\n", encoding="utf-8")
    fixture_git(fixture.checkout, "add", "a-file-added-to-the-index.txt")
    result = fixture.run()
    check("a new file that is staged is refused the same way",
          result.code == 2 and result.runner_calls == []
          and fixture.test_log("ned-box") == test_log_before
          and result.stderr.startswith(
              "pull-request-head-test-run: not run — a tracked file in "
              f"{fixture.checkout} differs from its commit {fixture.head}: "
              "a-file-added-to-the-index.txt\n"), repr(result))
    fixture_git(fixture.checkout, "reset", "-q", "--hard", fixture.head)
    (fixture.checkout / "an-untracked-file.txt").write_text("not tracked\n", encoding="utf-8")
    result = fixture.run()
    (fixture.checkout / "an-untracked-file.txt").unlink()
    check("an untracked file is no tracked file that differs: the run goes ahead",
          result.code == 0 and len(result.runner_calls) == 1, repr(result))
    not_a_checkout = workspace / "a-directory-that-is-no-checkout"
    not_a_checkout.mkdir()
    test_log_before = fixture.test_log("ned-box")
    result = fixture.run(checkout=not_a_checkout)
    check("a directory with no commit is refused: exit 2, nothing run, nothing written",
          result.code == 2 and result.runner_calls == [] and result.stdout == ""
          and fixture.record_files() == [record_path]
          and fixture.test_log("ned-box") == test_log_before
          and result.stderr == "pull-request-head-test-run: not run — git cannot resolve "
          f"HEAD to a commit in {not_a_checkout}.\n"
          "Pass --checkout the top directory of a checkout at the commit to test.\n",
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
    check("the record says the lock was never released, with the runner's last refusal, "
          "and holds no runner output",
          any(line.startswith("not run — the lock was never released: run-all-test-suites "
                              "exited 3 on every attempt for 6 s; its last refusal: "
                              "run-all-test-suites: not run — another run holds /a/lock")
              for line in record_lines)
          and "runner exit code: 3" in record_lines
          and not any(line.startswith(("SUMMARY:", "the runner's output"))
                      for line in record_lines)
          and record_lines[-1:] == ["pull-request-head-test-run exit code: 4"],
          repr(record_lines))
    check("stderr says the lock was never released and what to do, and stdout is the "
          "citation alone",
          "not run — the lock was never released" in result.stderr
          and result.stderr.endswith(
              "\nRun this again after the run holding that lock has finished.\n")
          and result.stdout == citation_line, repr(result))
    check("the wait and its bound are the daily run's: 2 seconds, for up to an hour",
          daily.DAILY_FULL_TEST_RUN_LOCK_WAIT_BOUND_SECONDS == 3600
          and daily.DAILY_FULL_TEST_RUN_LOCK_WAIT_SECONDS == 2)

    # The daily run's function hands its runner the lock a caller passes it.
    # This program takes no lock, so its runner is handed no descriptor.
    runs_of_the_runner = []
    subprocess_run = subprocess.run

    def subprocess_run_that_writes_down_each_run_of_the_runner(command, *positional,
                                                               **keywords):
        if list(command[:2]) == [sys.executable, str(fixture.runner)]:
            runs_of_the_runner.append(keywords)
        return subprocess_run(command, *positional, **keywords)

    subprocess.run = subprocess_run_that_writes_down_each_run_of_the_runner
    try:
        result = fixture.run()
    finally:
        subprocess.run = subprocess_run
    check("the daily run's function starts the runner with no descriptor to hold, since "
          "this program takes no lock",
          result.code == 0 and len(result.runner_calls) == 1 and len(runs_of_the_runner) == 1
          and tuple(runs_of_the_runner[0].get("pass_fds", ())) == (),
          f"{runs_of_the_runner!r}\n{result!r}")

    # --- The checkout changes after the first comparison -------------------------
    def put_the_checkout_back():
        fixture_git(fixture.checkout, "checkout", "-q", "-f", "a-topic-branch")
        fixture_git(fixture.checkout, "reset", "-q", "--hard", fixture.head)

    def change_a_tracked_file():
        (fixture.checkout / "a-change.txt").write_text("changed during the run\n",
                                                       encoding="utf-8")

    def move_head():
        fixture_git(fixture.checkout, "checkout", "-q", "--detach", fixture.commit_of_main)

    def no_verdict_line(record_lines):
        lines = [line for line in record_lines
                 if line.startswith(f"no verdict on commit {fixture.head} — ")]
        return lines[0] if len(lines) == 1 else ""

    first_line_does_not_say = (f"the runner's first line does not say it tested "
                               f"{fixture.head} with tracked files matching that commit")
    file_differs_after = (f"after the run a tracked file in {fixture.checkout} differs from "
                          f"its commit: a-change.txt")
    head_is_after = (f"after the run HEAD of {fixture.checkout} is commit "
                     f'{fixture.commit_of_main} ("main moves on")')
    run_again = ("\nRun this again on a checkout that nothing else changes while the run "
                 "lasts, such as a detached worktree at the commit to test.\n")

    result = fixture.run(exits=(3, 0), during_each_wait=change_a_tracked_file)
    put_the_checkout_back()
    record_lines = (fixture.record("ned-box") or "").splitlines()
    differing_first_line = fixture.runner_first_line().replace(
        "(tracked files match that commit)", "(tracked files differ from that commit)")
    check("a tracked file changed during the wait on the lock: the runner's passing run is "
          "no verdict on the head, and the program exits 4",
          result.code == 4 and len(result.runner_calls) == 2 and result.waits == [2]
          and "runner exit code: 0" in record_lines, repr(result))
    check("the record of that run, which holds the runner's passing SUMMARY line and the "
          "runner's exit code 0, closes with this program's own exit code, 4",
          PASSING_SUMMARY_LINE in record_lines and "runner exit code: 0" in record_lines
          and record_lines[-1:] == ["pull-request-head-test-run exit code: 4"],
          repr(record_lines))
    check("the record of that run says what differed, by the runner's account and by the "
          "comparison after the run, and quotes the runner's first line",
          no_verdict_line(record_lines)
          == f"no verdict on commit {fixture.head} — {first_line_does_not_say}; "
             f"{file_differs_after}; the runner's first line: {differing_first_line}",
          repr(record_lines))
    check("stdout of that run is the citation alone, with no SUMMARY line to read as a "
          "pass, and stderr is what differed, then what to do",
          result.stdout == citation_line
          and result.stderr.startswith("pull-request-head-test-run: no verdict on commit ")
          and result.stderr.endswith(run_again), repr(result))

    result = fixture.run(exits=(3, 0), during_each_wait=move_head)
    put_the_checkout_back()
    record_lines = (fixture.record("ned-box") or "").splitlines()
    first_line_of_the_other_commit = fixture.runner_first_line().replace(
        f" at {fixture.head} ", f" at {fixture.commit_of_main} ")
    check("HEAD moved during the wait on the lock: no verdict on the head, exit 4, the "
          "record names the commit HEAD moved to and quotes the runner's first line, and "
          "stdout is the citation alone",
          result.code == 4 and result.stdout == citation_line
          and "runner exit code: 0" in record_lines
          and no_verdict_line(record_lines)
          == f"no verdict on commit {fixture.head} — {first_line_does_not_say}; "
             f"{head_is_after}; the runner's first line: {first_line_of_the_other_commit}",
          f"{result!r}\n{record_lines!r}")

    result = fixture.run(exits=(3, 1), lines=FAILING_RUNNER_LINES,
                         during_each_wait=change_a_tracked_file)
    put_the_checkout_back()
    check("a failing run of a checkout that changed during the wait is no verdict on the "
          "head either: exit 4, not the runner's 1",
          result.code == 4 and result.stdout == citation_line
          and no_verdict_line((fixture.record("ned-box") or "").splitlines()) != "",
          repr(result))

    result = fixture.run(runner_changes_the_checkout={
        "files_written_in_the_checkout": {"a-change.txt": "changed during the run\n"}})
    put_the_checkout_back()
    record_lines = (fixture.record("ned-box") or "").splitlines()
    check("a tracked file changed while the suites run, after the runner's first line said "
          "the files match: the comparison after the run finds it, exit 4",
          result.code == 4 and result.stdout == citation_line
          and no_verdict_line(record_lines)
          == f"no verdict on commit {fixture.head} — {file_differs_after}; the runner's "
             f"first line: {fixture.runner_first_line()}", f"{result!r}\n{record_lines!r}")

    result = fixture.run(runner_changes_the_checkout={
        "git_commands_run_in_the_checkout": [
            ["checkout", "-q", "--detach", fixture.commit_of_main]]})
    put_the_checkout_back()
    record_lines = (fixture.record("ned-box") or "").splitlines()
    check("HEAD moved while the suites run: the comparison after the run finds it, exit 4",
          result.code == 4 and result.stdout == citation_line
          and no_verdict_line(record_lines)
          == f"no verdict on commit {fixture.head} — {head_is_after}; the runner's first "
             f"line: {fixture.runner_first_line()}", f"{result!r}\n{record_lines!r}")

    result = fixture.run(exits=(3, 0), during_each_wait=change_a_tracked_file,
                         runner_changes_the_checkout={
                             "git_commands_run_in_the_checkout": [
                                 ["checkout", "--", "a-change.txt"]]})
    put_the_checkout_back()
    record_lines = (fixture.record("ned-box") or "").splitlines()
    # This run's logs are in a directory of this run's own.
    differing_first_line = fixture.runner_first_line().replace(
        "(tracked files match that commit)", "(tracked files differ from that commit)")
    check("a tracked file changed during the wait and put back before the runner exits: "
          "the runner's first line alone tells it, exit 4",
          result.code == 4 and result.stdout == citation_line
          and no_verdict_line(record_lines)
          == f"no verdict on commit {fixture.head} — {first_line_does_not_say}; the "
             f"runner's first line: {differing_first_line}", f"{result!r}\n{record_lines!r}")
    check("the words this program looks for in the runner's first line are the real "
          "runner's for a checkout whose tracked files match its commit",
          program.run_all_test_suites.commit_and_state(fixture.checkout)
          == (fixture.head, program.RUNNER_STATE_WHEN_TRACKED_FILES_MATCH),
          repr(program.run_all_test_suites.commit_and_state(fixture.checkout)))

    # --- A first line this program cannot read as naming the head ----------------
    a_line_before = "a line the runner prints before its first line"
    result = fixture.run(stand_in_runner_behaviour={
        "lines_printed_before_the_first_line": [a_line_before]})
    record_lines = (fixture.record("ned-box") or "").splitlines()
    check("a runner that prints a line before the line naming the head: the line read is "
          "the first the runner printed, so the passing run is no verdict on the head, "
          "exit 4, though its second line names the head with its tracked files matching",
          result.code == 4 and result.stdout == citation_line
          and len(result.runner_calls) == 1
          and record_lines.count(fixture.runner_first_line()) == 1
          and PASSING_SUMMARY_LINE in record_lines and "runner exit code: 0" in record_lines
          and record_lines[-1:] == ["pull-request-head-test-run exit code: 4"]
          and no_verdict_line(record_lines)
          == f"no verdict on commit {fixture.head} — {first_line_does_not_say}; the "
             f"runner's first line: {a_line_before}", f"{result!r}\n{record_lines!r}")
    result = fixture.run(stand_in_runner_behaviour={
        "characters_of_the_commit_named_in_the_first_line": 12})
    record_lines = (fixture.record("ned-box") or "").splitlines()
    first_line_naming_12_characters = fixture.runner_first_line().replace(
        f" at {fixture.head} ", f" at {fixture.head[:12]} ")
    check("a runner whose first line names the head by the first 12 characters of its "
          "hash: the full hash is what this program reads, so the passing run is no "
          "verdict on the head, exit 4",
          result.code == 4 and result.stdout == citation_line
          and len(result.runner_calls) == 1
          and first_line_naming_12_characters != fixture.runner_first_line()
          and first_line_naming_12_characters in record_lines
          and PASSING_SUMMARY_LINE in record_lines and "runner exit code: 0" in record_lines
          and record_lines[-1:] == ["pull-request-head-test-run exit code: 4"]
          and no_verdict_line(record_lines)
          == f"no verdict on commit {fixture.head} — {first_line_does_not_say}; the "
             f"runner's first line: {first_line_naming_12_characters}",
          f"{result!r}\n{record_lines!r}")

    result = fixture.run()
    check("after those runs a run of the checkout put back at the head passes again and "
          "adds its record",
          result.code == 0 and result.stdout == PASSING_SUMMARY_LINE + "\n" + citation_line
          and no_verdict_line((fixture.record("ned-box") or "").splitlines()) == "",
          repr(result))

    # --- A runner that could not start, and one that gave no verdict -----------
    result = fixture.run(exits=(2,))
    record_lines = (fixture.record("ned-box") or "").splitlines()
    check("a runner that exits 2 is recorded with no output and its stderr, and the "
          "program exits 2",
          result.code == 2 and "runner exit code: 2" in record_lines
          and "the runner's output, 0 lines:" in record_lines
          and "the runner printed no SUMMARY: line; its stderr:" in record_lines
          and any(line.startswith("  run-all-test-suites: not run — git lists no")
                  for line in record_lines)
          and result.stdout == citation_line, f"{result!r}\n{record_lines!r}")
    check("the record of a runner that exits 2 closes with this program's own exit code, "
          "2, the runner's",
          record_lines[-1:] == ["pull-request-head-test-run exit code: 2"],
          repr(record_lines))
    result = fixture.run(exits=(0,), lines=["PASS scripts/a-test.py (0.1s)"])
    record_lines = (fixture.record("ned-box") or "").splitlines()
    check("a runner that exits 0 with no SUMMARY line gave no verdict: the record says so "
          "and the program exits 4",
          result.code == 4 and "runner exit code: 0" in record_lines
          and "run-all-test-suites exited 0 and printed no SUMMARY: line, which is no "
              "verdict" in record_lines, f"{result!r}\n{record_lines!r}")
    check("the record of a runner that exits 0 with no SUMMARY line, which holds the "
          "runner's exit code 0, closes with this program's own exit code, 4",
          "runner exit code: 0" in record_lines
          and record_lines[-1:] == ["pull-request-head-test-run exit code: 4"],
          repr(record_lines))
    result = fixture.run(exits=(-9,))
    record_lines = (fixture.record("ned-box") or "").splitlines()
    check("a runner killed by a signal gave no verdict either: the record names the "
          "signal and the program exits 4",
          result.code == 4 and "runner exit code: -9" in record_lines
          and "run-all-test-suites was killed by SIGKILL" in record_lines
          and record_lines[-1:] == ["pull-request-head-test-run exit code: 4"],
          f"{result!r}\n{record_lines!r}")
    result = fixture.run(stand_in_runner_behaviour={
        "signal_that_kills_the_runner_after_its_last_line": 15})
    record_lines = (fixture.record("ned-box") or "").splitlines()
    check("a runner killed by a signal after it printed a passing SUMMARY line gave no "
          "verdict: exit 4, and the record, which holds that SUMMARY line and the runner's "
          "exit code -15, closes with this program's own exit code, 4",
          result.code == 4 and len(result.runner_calls) == 1
          and PASSING_SUMMARY_LINE in record_lines
          and "runner exit code: -15" in record_lines
          and "run-all-test-suites was killed by SIGTERM" in record_lines
          and record_lines[-1:] == ["pull-request-head-test-run exit code: 4"],
          f"{result!r}\n{record_lines!r}")

    # --- The seams, and the runner beside the program ---------------------------
    recorded_inputs = workspace / "a-recorded-inputs-directory"
    result = fixture.run(extra_arguments=["--recorded-inputs-directory", str(recorded_inputs)])
    check("--recorded-inputs-directory is passed through to the runner",
          result.code == 0 and result.runner_calls[0]["argv"][-2:]
          == ["--recorded-inputs-directory", str(recorded_inputs)]
          and not recorded_inputs.exists(), repr(result))
    commands_run = []

    def runner_that_is_not_started(command, run_from, wait, monotonic, lock_handle=None):
        commands_run.append((command, run_from))
        return (subprocess.CompletedProcess(
            command, 0, stdout=f"{fixture.runner_first_line()}\n{PASSING_SUMMARY_LINE}\n",
            stderr=""), 0, False)

    saved_function = daily.run_test_suite_runner_waiting_for_the_machine_lock
    daily.run_test_suite_runner_waiting_for_the_machine_lock = runner_that_is_not_started
    try:
        result = fixture.run(runner_program=None)
    finally:
        daily.run_test_suite_runner_waiting_for_the_machine_lock = saved_function
    record_lines = (fixture.record("ned-box") or "").splitlines()
    runner_beside_the_program = SCRIPT_PATH.with_name("run-all-test-suites.py")
    check("with no --test-suite-runner-program the runner is the "
          "scripts/run-all-test-suites.py beside this program, not the checkout's, run from "
          "the checkout, and the record names it",
          result.code == 0 and len(commands_run) == 1
          and commands_run[0][0][1] == str(runner_beside_the_program)
          and runner_beside_the_program.is_file()
          and commands_run[0][0][2:4] == ["--checkout", str(fixture.checkout)]
          and commands_run[0][1] == fixture.checkout
          and any(line.startswith(f"runner: {runner_beside_the_program}, ")
                  for line in record_lines), f"{commands_run!r}\n{result!r}")

    result = fixture.run(runner_program=Path("scripts") / "run-all-test-suites.py",
                         started_in=fixture.reference)
    record_lines = (fixture.record("ned-box") or "").splitlines()
    check("a relative --test-suite-runner-program is taken from the directory the program "
          "is started in: that runner runs, not the checkout's file of the same relative "
          "path, and the record names the runner that ran",
          result.code == 0 and len(result.runner_calls) == 1
          and (fixture.checkout / "scripts" / "run-all-test-suites.py").is_file()
          and result.runner_calls[0]["argv"][0] == str(fixture.runner)
          and any(line.startswith(f"runner: {fixture.runner}, from commit "
                                  f"{fixture.merge_base} ") for line in record_lines),
          f"{result!r}\n{record_lines!r}")

    # --- A head with no merge base to start from --------------------------------
    cut_off = fixture.clone_of_origin("a-clone-that-has-no-origin-main")
    fixture_git(cut_off, "update-ref", "-d", "refs/remotes/origin/main")
    result = fixture.run(checkout=cut_off)
    other_record_path = f"pull-request-head-test-runs/ned-box/{fixture.commit_of_main}.txt"
    record_lines = (fixture.record("ned-box", fixture.commit_of_main) or "").splitlines()
    check("with no --since and no merge base the runner is not run, and the program exits 4",
          result.code == 4 and result.runner_calls == [], repr(result))
    check("that failed step is written to the record of that checkout's head, beside the "
          "other head's record",
          fixture.record_files() == sorted([record_path, other_record_path])
          and any(line.startswith(f"not run — git finds no merge base of "
                                  f"{fixture.commit_of_main} and refs/remotes/origin/main in "
                                  f"{cut_off}: ") for line in record_lines)
          and "selecting since: not resolved" in record_lines
          and "runner exit code: none, the runner was not run" in record_lines,
          f"{fixture.record_files()}\n{record_lines!r}")
    check("that failed step prints what failed and what to do on stderr, and still cites "
          "the record",
          result.stderr.startswith("pull-request-head-test-run: not run — git finds no "
                                   "merge base of ")
          and result.stderr.endswith(
              "\nPass --since the commit the selection starts from, then run this again.\n")
          and result.stdout == "pull-request-head-test-run: record written to "
          f"nedlern@ned-box:{fixture.log_store}/{other_record_path}\n", repr(result))

    # --- A runner that prints lines in a record's own shapes ------------------------
    a_line_that_reads_as_a_first_line = (
        "pull-request-head-test-run: ned-box, started 2026-10-01T03:30:00Z, a record of 3 "
        "lines")
    quoting_result = fixture.run(lines=[
        *SELECTION_LINES, "PASS scripts/a-test.py (0.1s)",
        a_line_that_reads_as_a_first_line, "pull-request-head-test-run exit code: 1",
        PASSING_SUMMARY_LINE])
    fixture.run(exits=(1,), lines=FAILING_RUNNER_LINES)

    # --- Every run above that wrote a record is in the test log ---------------------
    records = fixture.records("ned-box")
    check("the head's test log reads record by record from its first line to its last: "
          "each record's first line counts that record's lines, each record closes with "
          "this program's exit code, and there is one record for each run above that "
          "cited the head's test log",
          records is not None and len(records) == fixture.runs_that_cited.get(record_path)
          and len(records) > 20
          and records[:2] == [record_of_the_passing_run, record_of_the_failing_run],
          f"{None if records is None else len(records)} "
          f"{fixture.runs_that_cited.get(record_path)}")
    check("a line the runner printed that reads as a record's first line is quoted in its "
          "record and starts no record: the count in the first line is what a reader goes "
          "by",
          quoting_result.code == 0 and records is not None
          and sum(a_line_that_reads_as_a_first_line in record.splitlines()[1:]
                  for record in records) == 1
          and not any(record.splitlines()[0] == a_line_that_reads_as_a_first_line
                      for record in records),
          f"{quoting_result!r}")

    # --- The record's local copy cannot be written --------------------------------
    test_log_before = fixture.test_log("ned-box")
    # The next run's directory, where its local copy would go, is named by the
    # next process number this fixture hands out.
    in_the_way = (fixture.temporary / program.PULL_REQUEST_HEAD_TEST_RUN_DIRECTORY_NAME
                  / f"{fixture.head}-{THE_MOMENT:%Y%m%dT%H%M%SZ}-"
                    f"{os.getpid() + fixture.run_count + 1}"
                  / program.PULL_REQUEST_HEAD_TEST_RUN_RECORD_LOCAL_COPY_FILE_NAME)
    in_the_way.mkdir(parents=True)
    result = fixture.run(exits=(1,), lines=FAILING_RUNNER_LINES)
    in_the_way.rmdir()
    check("when the record's local copy cannot be written the program exits 5, leaves the "
          "log-store's test log as it was, and says what failed and what to do",
          result.code == 5 and result.stdout == ""
          and fixture.local_copy() == in_the_way
          and fixture.test_log("ned-box") == test_log_before
          and result.stderr.startswith(
              "pull-request-head-test-run: the record was not written: its local copy "
              f"{fixture.local_copy()} could not be written (IsADirectoryError: ")
          and result.stderr.endswith(
              "\nTell the user what the line above says.\n"
              "Fix what the error names, then run this again.\n"), repr(result))


def run_cases_of_a_subject_that_holds_line_boundaries_that_are_no_line_feed(workspace: Path):
    """The count in a record's first line is of the lines a line feed ends,
    which is how the program's docstring tells a reader to count.
    `str.splitlines` also ends a line at a form feed, at U+0085, at U+2028
    and at five more characters, so a count taken with it is too high for a
    record that holds one of them inside a line. A line the runner printed
    never does: the program splits the runner's output with
    `str.splitlines`, and each piece is a line of the record. The head's
    commit subject can, because git gives the subject whole and the record
    quotes it in one line. So the head here is one commit further on than
    the fixture's, with a subject that holds three of those characters."""
    fixture = Fixture(workspace / "a-subject-that-holds-line-boundaries")
    subject = ("a subject that holds a form feed \x0c, the next-line character \x85 and a "
               "line separator \u2028 before its last words")
    (fixture.checkout / "a-second-change.txt").write_text("a second change\n",
                                                          encoding="utf-8")
    fixture_git(fixture.checkout, "add", "-A")
    fixture_git(fixture.checkout, "commit", "-q", "-m", subject)
    fixture.head = fixture_git(fixture.checkout, "rev-parse", "HEAD")
    subject_git_gives = fixture_git(fixture.checkout, "log", "-1", "--format=%s")
    check("the fixture is that case: git gives the head's subject whole, no line feed is "
          "in it, and `str.splitlines` splits it in four",
          subject_git_gives == subject and "\n" not in subject
          and len(subject.splitlines()) == 4, repr(subject_git_gives))
    passing = fixture.run()
    failing = fixture.run(exits=(1,), lines=FAILING_RUNNER_LINES)
    test_log = fixture.test_log("ned-box") or ""
    records = fixture.records("ned-box")
    head_line = f'head: commit {fixture.head} ("{subject}")'
    check("for a head whose subject holds a form feed, U+0085 and U+2028, a record's first "
          "line counts the lines a line feed ends, the line that quotes the subject being "
          "one of them: the test log of two runs of that head reads record by record, "
          "each record's count is the number of its line feeds, and each quotes the "
          "subject whole in one line",
          passing.code == 0 and failing.code == 1
          and records is not None and len(records) == 2
          and "".join(records) == test_log
          and all(record.split("\n")[1] == head_line for record in records)
          and all(int(A_RECORDS_FIRST_LINE.fullmatch(record.split("\n")[0]).group(2))
                  == record.count("\n") for record in records),
          f"{passing!r}\n{failing!r}\n{test_log!r}")


def run_cases_on_the_mac(workspace: Path):
    fixture = Fixture(workspace / "on-the-mac")
    record_path = f"pull-request-head-test-runs/mac/{fixture.head}.txt"

    result = fixture.run(hostname="a-mac-that-is-not-ned-box")
    record = fixture.record("mac")
    check("off ned-box the record is written over ssh to nedlern@ned-box, with the options "
          "the log-store's other writers pass, as "
          "pull-request-head-test-runs/mac/<the head's full hash>.txt",
          result.code == 0 and record is not None and PASSING_SUMMARY_LINE in record
          and fixture.record_files() == [record_path]
          and result.ssh_calls == [
              "-o BatchMode=yes -o ConnectTimeout=10 nedlern@ned-box "
              + fixture.write_command("mac", record)], f"{result!r}\n{record!r}")
    check("the write leaves the test log alone in its directory",
          fixture.record_files() == [record_path], repr(fixture.record_files()))
    check("the Mac's record names the mac, in its first line and beside the logs",
          record is not None and record.startswith(
              "pull-request-head-test-run: mac, started 2026-10-01T03:30:00Z, a record of ")
          and record.endswith(f"logs: {fixture.logs()} on mac\n"
                              "pull-request-head-test-run exit code: 0\n"), repr(record))
    check("the citation names ned-box and the mac's directory",
          result.stdout == PASSING_SUMMARY_LINE + "\npull-request-head-test-run: record "
          f"written to nedlern@ned-box:{fixture.log_store}/{record_path}\n", result.stdout)
    result = fixture.run(hostname="ned-box")
    check("a run of the same head on ned-box leaves the Mac's test log as it was and makes "
          "its own",
          result.code == 0 and fixture.test_log("mac") == record
          and fixture.record_files() == sorted([
              record_path, f"pull-request-head-test-runs/ned-box/{fixture.head}.txt"]),
          f"{fixture.record_files()} {result!r}")

    # --- ned-box cannot be reached ------------------------------------------------
    unreachable = Fixture(workspace / "on-the-mac-with-ned-box-unreachable")
    result = unreachable.run(hostname="a-mac-that-is-not-ned-box",
                             ssh_body=SSH_THAT_CANNOT_REACH_NED_BOX)
    target = (f"{unreachable.log_store}/pull-request-head-test-runs/mac/"
              f"{unreachable.head}.txt")
    local_copy = (unreachable.local_copy().read_text(encoding="utf-8")
                  if unreachable.local_copy().is_file() else None)
    remedy = ("ssh -o BatchMode=yes -o ConnectTimeout=10 nedlern@ned-box "
              + shlex.quote(unreachable.write_command("mac", local_copy or ""))
              + f" < {unreachable.local_copy()}")
    check("when ned-box cannot be reached the program exits 5, cites nothing and writes "
          "nothing into the log-store",
          result.code == 5 and result.stdout == "" and unreachable.record_files() == []
          and len(result.runner_calls) == 1, repr(result))
    check("when ned-box cannot be reached stderr is what failed, then one instruction a "
          "line: tell the user, and the command that writes the record, which is the "
          "command the program ran",
          result.stderr == "pull-request-head-test-run: the record was not written to "
          f"nedlern@ned-box:{target} (ssh nedlern@ned-box exited 255: ssh: connect to host "
          "ned-box port 22: No route to host).\n"
          "Tell the user what the line above says, and the remedy in the line below.\n"
          "When ned-box answers ssh again, write the record by running on this machine: "
          f"{remedy}\n"
          and result.stderr.count("\n") == 3 and len(result.ssh_calls) == 1
          and shlex.quote(result.ssh_calls[0].partition("nedlern@ned-box ")[2]) in remedy,
          result.stderr)
    check("the record that could not be written is kept beside the logs",
          local_copy is not None and PASSING_SUMMARY_LINE in local_copy.splitlines(),
          repr(local_copy))
    check("that record closes with the exit code the run would have exited with, 0, "
          "while the program, its record not written, exits 5",
          result.code == 5 and local_copy is not None
          and local_copy.splitlines()[-1:] == ["pull-request-head-test-run exit code: 0"],
          f"{result.code} {local_copy!r}")
    # The command as stderr printed it is what the cases below run.
    remedy_as_printed = result.stderr.rstrip("\n").rpartition(
        "by running on this machine: ")[2]
    scratch = unreachable.scratch_for_next_run()
    reachable_again = unreachable.fake_ssh_directory(scratch, SSH_THAT_RUNS_THE_COMMAND_HERE)
    environment = program.run_all_test_suites.environment_without_git_redirecting_variables()
    environment["PATH"] = f"{reachable_again}{os.pathsep}{environment.get('PATH', '')}"
    written_by_hand = subprocess.run(["/bin/sh", "-c", remedy_as_printed], env=environment,
                                     capture_output=True, text=True, check=False)
    check("the command stderr gives writes that record once ned-box answers: exit 0, "
          "nothing said, and the test log is that record",
          written_by_hand.returncode == 0 and local_copy is not None
          and unreachable.test_log("mac") == local_copy
          and written_by_hand.stdout == "" and written_by_hand.stderr == "",
          f"{written_by_hand.returncode} {written_by_hand.stdout} {written_by_hand.stderr}")

    # --- That command, run for the first time when the test log holds other runs' ---
    # --- records: of an earlier run, of a later run, of a run of the same second ----
    for state, moment_of_the_other_run in (
            ("an earlier run", AN_EARLIER_MOMENT), ("a later run", A_LATER_MOMENT),
            ("a run started in the same second", THE_MOMENT)):
        other = Fixture(workspace / f"on-the-mac-with-the-record-of-{state.replace(' ', '-')}")
        not_written = other.run(hostname="a-mac-that-is-not-ned-box",
                                ssh_body=SSH_THAT_CANNOT_REACH_NED_BOX)
        remedy_of_the_run = not_written.stderr.rstrip("\n").rpartition(
            "by running on this machine: ")[2]
        record_the_run_kept = (other.local_copy().read_text(encoding="utf-8")
                               if other.local_copy().is_file() else "")
        the_other_run = other.run(hostname="a-mac-that-is-not-ned-box", exits=(1,),
                                  lines=FAILING_RUNNER_LINES, moment=moment_of_the_other_run)
        record_of_the_other_run = other.record("mac")
        scratch = other.scratch_for_next_run()
        reachable_again = other.fake_ssh_directory(scratch, SSH_THAT_RUNS_THE_COMMAND_HERE)
        environment = (
            program.run_all_test_suites.environment_without_git_redirecting_variables())
        environment["PATH"] = f"{reachable_again}{os.pathsep}{environment.get('PATH', '')}"
        written_by_hand = subprocess.run(["/bin/sh", "-c", remedy_of_the_run],
                                         env=environment, capture_output=True, text=True,
                                         check=False)
        check(f"a passing run whose record was not written, then a failing run of the same "
              f"head, {state} by its started moment, whose record was: the first run's "
              f"remedy, run as printed after that, exits 0 and adds the first run's record "
              f"after the other's; the other run's record is still there byte for byte, and "
              f"each record's first line gives the moment its own run started",
              not_written.code == 5 and the_other_run.code == 1
              and record_of_the_other_run is not None and record_the_run_kept != ""
              and written_by_hand.returncode == 0 and written_by_hand.stdout == ""
              and written_by_hand.stderr == ""
              and other.test_log("mac") == record_of_the_other_run + record_the_run_kept
              and other.records("mac") == [record_of_the_other_run, record_the_run_kept]
              and record_of_the_other_run.startswith(
                  "pull-request-head-test-run: mac, started "
                  f"{moment_of_the_other_run:%Y-%m-%dT%H:%M:%SZ}, a record of ")
              and record_the_run_kept.startswith(
                  "pull-request-head-test-run: mac, started 2026-10-01T03:30:00Z, a record "
                  "of ")
              and FAILING_SUMMARY_LINE in record_of_the_other_run.splitlines()
              and PASSING_SUMMARY_LINE in record_the_run_kept.splitlines()
              and other.record_files() == [f"pull-request-head-test-runs/mac/{other.head}.txt"],
              f"{not_written!r}\n{the_other_run!r}\n{written_by_hand.returncode} "
              f"{written_by_hand.stdout} {written_by_hand.stderr}\n{other.test_log('mac')!r}")


def run_cases_of_a_record_cut_short_on_the_way(workspace: Path):
    fixture = Fixture(workspace / "on-the-mac-with-a-record-cut-short")
    record_path = f"pull-request-head-test-runs/mac/{fixture.head}.txt"
    earlier = fixture.run(hostname="a-mac-that-is-not-ned-box", moment=AN_EARLIER_MOMENT)
    record_of_the_earlier_run = fixture.record("mac")
    for handed_over, ssh_body in (("the first 300 bytes", SSH_THAT_HANDS_OVER_300_BYTES),
                                  ("nothing", SSH_THAT_HANDS_OVER_NOTHING)):
        result = fixture.run(hostname="a-mac-that-is-not-ned-box", exits=(1,),
                             lines=FAILING_RUNNER_LINES, ssh_body=ssh_body)
        local_copy = (fixture.local_copy().read_text(encoding="utf-8")
                      if fixture.local_copy().is_file() else "")
        check(f"when {handed_over} of the record reaches the far side before the input "
              f"ends, the program exits 5 and says the record was not written, the test "
              f"log is left byte for byte, the earlier run's whole record and nothing "
              f"more, and no other file is left",
              earlier.code == 0 and record_of_the_earlier_run is not None
              and len(local_copy.encode("utf-8")) > 300
              and result.code == 5 and result.stdout == ""
              and fixture.test_log("mac") == record_of_the_earlier_run
              and fixture.record_files() == [record_path]
              and result.stderr.startswith(
                  "pull-request-head-test-run: the record was not written to "
                  f"nedlern@ned-box:{fixture.log_store}/{record_path} (ssh nedlern@ned-box "
                  f"exited 1: pull-request-head-test-run: not written: "
                  f"{len(local_copy.encode('utf-8'))} bytes of the record were sent and "
                  f"another count arrived.).\n"), f"{result!r}\n{fixture.record_files()}")
    remedy_as_printed = result.stderr.rstrip("\n").rpartition(
        "by running on this machine: ")[2]
    scratch = fixture.scratch_for_next_run()
    reachable = fixture.fake_ssh_directory(scratch, SSH_THAT_RUNS_THE_COMMAND_HERE)
    environment = program.run_all_test_suites.environment_without_git_redirecting_variables()
    environment["PATH"] = f"{reachable}{os.pathsep}{environment.get('PATH', '')}"
    cut_short = subprocess.run(
        ["/bin/sh", "-c", remedy_as_printed.rpartition(" < ")[0]], env=environment,
        input=local_copy[:300], capture_output=True, text=True, check=False)
    check("the remedy printed for that run, handed the first 300 bytes of its record, "
          "adds nothing, exits 1, leaves the test log byte for byte and no other file, and "
          "says what arrived and what to do",
          cut_short.returncode == 1 and record_of_the_earlier_run is not None
          and fixture.test_log("mac") == record_of_the_earlier_run
          and fixture.record_files() == [record_path]
          and cut_short.stdout == ""
          and cut_short.stderr == "pull-request-head-test-run: not written: "
          f"{len(local_copy.encode('utf-8'))} bytes of the record were sent and another "
          "count arrived.\nRun this command again.\n",
          f"{cut_short.returncode} {cut_short.stderr}")
    written_by_hand = subprocess.run(["/bin/sh", "-c", remedy_as_printed], env=environment,
                                     capture_output=True, text=True, check=False)
    check("the remedy, run as printed once the far side gets the whole record, adds that "
          "run's whole record after the earlier run's, which is still there byte for byte",
          written_by_hand.returncode == 0 and record_of_the_earlier_run is not None
          and fixture.test_log("mac") == record_of_the_earlier_run + local_copy
          and FAILING_SUMMARY_LINE in local_copy.splitlines()
          and fixture.record_files() == [record_path],
          f"{written_by_hand.returncode} {written_by_hand.stderr}")
    # --- The far side added the record, and the client died before the exit
    # status came back: the program says the record was not written, and the
    # record is in the test log.
    added = Fixture(workspace / "on-the-mac-with-a-client-that-died-after-the-record-was-added")
    record_path = f"pull-request-head-test-runs/mac/{added.head}.txt"
    result = added.run(hostname="a-mac-that-is-not-ned-box",
                       ssh_body=SSH_THAT_RUNS_THE_COMMAND_HERE_AND_THEN_FAILS)
    local_copy = (added.local_copy().read_text(encoding="utf-8")
                  if added.local_copy().is_file() else "")
    remedy_as_printed = result.stderr.rstrip("\n").rpartition(
        "by running on this machine: ")[2]
    scratch = added.scratch_for_next_run()
    reachable = added.fake_ssh_directory(scratch, SSH_THAT_RUNS_THE_COMMAND_HERE)
    environment = program.run_all_test_suites.environment_without_git_redirecting_variables()
    environment["PATH"] = f"{reachable}{os.pathsep}{environment.get('PATH', '')}"
    written_by_hand = subprocess.run(["/bin/sh", "-c", remedy_as_printed], env=environment,
                                     capture_output=True, text=True, check=False)
    check("when the far side added the record and the ssh client then failed, the "
          "program exits 5 and says the record was not written, with the run's whole "
          "record in the test log; the remedy, run as printed, appends the record again, "
          "exits 0, leaves no other file, and says nothing: the test log holds the "
          "record twice",
          result.code == 5 and local_copy != ""
          and result.stderr.startswith(
              "pull-request-head-test-run: the record was not written to "
              f"nedlern@ned-box:{added.log_store}/{record_path} (ssh nedlern@ned-box "
              f"exited 255: ssh: the connection was lost).\n")
          and written_by_hand.returncode == 0 and added.test_log("mac") == local_copy * 2
          and added.record_files() == [record_path]
          and written_by_hand.stderr == ""
          and written_by_hand.stdout == "",
          f"{result!r}\n{written_by_hand.returncode} {written_by_hand.stdout} "
          f"{written_by_hand.stderr}")

    # --- On ned-box, where the command runs locally: an error of the command's own
    in_the_way = Fixture(workspace / "on-ned-box-with-a-file-where-a-directory-should-be")
    record_path = f"pull-request-head-test-runs/ned-box/{in_the_way.head}.txt"
    (in_the_way.log_store / "pull-request-head-test-runs").mkdir(parents=True)
    a_file = in_the_way.log_store / "pull-request-head-test-runs" / "ned-box"
    a_file.write_text("a file where the machine's directory should be\n", encoding="utf-8")
    result = in_the_way.run()
    local_copy = (in_the_way.local_copy().read_text(encoding="utf-8")
                  if in_the_way.local_copy().is_file() else "")
    stderr_lines = result.stderr.splitlines()
    check("on ned-box, when the test log's directory cannot be made, here because a file "
          "has its name, the program exits 5 and its refusal quotes the one line the "
          "command said, which names the error, then the command to run once the cause is "
          "fixed",
          result.code == 5 and result.stdout == "" and result.ssh_calls == []
          and len(stderr_lines) == 3
          and stderr_lines[0].startswith(
              "pull-request-head-test-run: the record was not written to "
              f"nedlern@ned-box:{in_the_way.log_store}/{record_path} (/bin/sh exited 1: "
              "pull-request-head-test-run: not written: FileExistsError: ")
          and stderr_lines[1] == ("Tell the user what the line above says, and the remedy "
                                  "in the line below.")
          and stderr_lines[2] == (
              "When the cause is fixed, write the record by running on this machine: "
              f"/bin/sh -c {shlex.quote(in_the_way.write_command('ned-box', local_copy))} "
              f"< {in_the_way.local_copy()}"), repr(result))
    a_file.unlink()
    written_by_hand = subprocess.run(
        ["/bin/sh", "-c", (stderr_lines[2:] or [""])[0].rpartition(
            "by running on this machine: ")[2]],
        capture_output=True, text=True, check=False)
    check("that command, run as printed once the file is out of the way, makes the "
          "directory and the test log and writes the record: exit 0",
          written_by_hand.returncode == 0 and local_copy != ""
          and in_the_way.test_log("ned-box") == local_copy
          and in_the_way.record_files() == [record_path],
          f"{written_by_hand.returncode} {written_by_hand.stderr}")


def run_cases_of_a_record_the_test_log_takes_part_of(workspace: Path):
    """A test log the size limit lets take only part of the record, through
    main as a run on the Mac calls it: the remedy is the repair by hand, never
    an append of the whole record behind the partial one."""
    probe = workspace / "file-size-limit-probe"
    subprocess.run(["/bin/sh", "-c", 'ulimit -f 1; head -c 8192 /dev/zero > "$1"', "sh",
                    str(probe)], capture_output=True, check=False)
    limit = probe.stat().st_size
    fixture = Fixture(workspace / "on-the-mac-with-a-test-log-that-takes-part-of-the-record")
    record_path = f"pull-request-head-test-runs/mac/{fixture.head}.txt"
    test_log = fixture.log_store / record_path
    test_log.parent.mkdir(parents=True)
    earlier = "x" * (limit - 2) + "\n"
    test_log.write_text(earlier, encoding="utf-8")
    result = fixture.run(hostname="a-mac-that-is-not-ned-box",
                         ssh_body='ulimit -f 1; exec /bin/sh -c "$1"')
    citation = f"nedlern@ned-box:{fixture.log_store}/{record_path}"
    stderr_lines = result.stderr.splitlines()
    check("when the test log takes only part of the record, the program exits 5, says a "
          "partial record now ends the test log, and gives the repair by hand before any "
          "append, never the append alone",
          result.code == 5 and len(stderr_lines) == 4
          and stderr_lines[0].startswith(
              f"pull-request-head-test-run: the record was not written to {citation} "
              f"(ssh nedlern@ned-box exited 1: pull-request-head-test-run: not written: "
              f"the test log took only part of the record.): a partial record now ends "
              f"that test log")
          and stderr_lines[2] == f"Remove the partial record from the end of {citation} by hand."
          and stderr_lines[3].startswith(
              "Once it is removed, write the record by running on this machine: ")
          and "When ned-box answers ssh again" not in result.stderr
          and (fixture.test_log("mac") or "").startswith(earlier)
          and len(earlier) < len(fixture.test_log("mac"))
          < len(earlier) + len(fixture.local_copy().read_text(encoding="utf-8")),
          f"limit {limit} {result!r}")


def run_cases_of_the_write_command_under_each_shell(workspace: Path):
    """The command that adds a record to a test log, run by itself under
    /bin/sh and under bash and dash where the machine has them: ned-box's
    /bin/sh is dash and its ssh hands a command to bash, and the Mac's /bin/sh
    is bash. The log-store root's name holds a space and a single quote, so
    the path the command is given needs quoting under each."""
    first = "the first run's whole record\nwith a second line — and its last\n"
    second = "the second run's whole record, which is longer\nline two\nline three\n"
    for shell in ("/bin/sh", "/bin/bash", "/bin/dash"):
        if not Path(shell).is_file():
            print(f"SKIP  the write command under {shell}: this machine has no {shell}")
            continue
        root = workspace / f"a root with a space and a ' quote under {Path(shell).name}"
        test_log = root / "pull-request-head-test-runs" / "ned-box" / "a-head.txt"

        def command_for(text_sent, file_name="a-head.txt"):
            return program.write_record_command(
                str(root), "ned-box", file_name, len(text_sent.encode("utf-8")))

        def write(text_sent, handed_over=None, file_name="a-head.txt", before=""):
            return subprocess.run(
                [shell, "-c", before + command_for(text_sent, file_name)],
                input=(text_sent if handed_over is None else handed_over).encode("utf-8"),
                capture_output=True, check=False)

        def files_left():
            return sorted(os.listdir(test_log.parent)) if test_log.parent.is_dir() else None

        def run_with_no_reader_on(stream, command, handed_over):
            """The command run with stdout or stderr a pipe whose reader is
            gone, as on the far side of an ssh whose client has died."""
            read_end, write_end = os.pipe()
            os.close(read_end)
            try:
                return subprocess.run([shell, "-c", command],
                                      input=handed_over.encode("utf-8"),
                                      **{"stdout": subprocess.DEVNULL,
                                         "stderr": subprocess.DEVNULL, stream: write_end},
                                      check=False)
            finally:
                os.close(write_end)

        written = write(first)
        check(f"under {shell}, in a log-store whose root's name holds a space and a single "
              f"quote, a whole record is written to a test log that is not there yet: exit "
              f"0, nothing said, the test log the record byte for byte, and no other file",
              written.returncode == 0 and written.stdout == b"" and written.stderr == b""
              and test_log.is_file() and test_log.read_bytes() == first.encode("utf-8")
              and files_left() == ["a-head.txt"],
              f"{written.returncode} {written.stdout!r} {written.stderr!r} {files_left()}")
        for handed_over_name, handed_over in (("half the record", second[:20]),
                                              ("nothing", ""),
                                              ("the record and a line more",
                                               second + "a line more\n")):
            cut_short = write(second, handed_over)
            check(f"under {shell}, {handed_over_name} handed over before the input ends: "
                  f"exit 1, the test log left byte for byte, no other file, nothing on "
                  f"stdout, and stderr what arrived and what to do",
                  cut_short.returncode == 1 and test_log.read_bytes() == first.encode("utf-8")
                  and files_left() == ["a-head.txt"] and cut_short.stdout == b""
                  and cut_short.stderr.decode("utf-8") == "pull-request-head-test-run: not "
                  f"written: {len(second.encode('utf-8'))} bytes of the record were sent "
                  "and another count arrived.\nRun this command again.\n",
                  f"{cut_short.returncode} {cut_short.stderr!r} {files_left()}")
            cut_short = run_with_no_reader_on("stderr", command_for(second), handed_over)
            check(f"under {shell}, {handed_over_name} handed over before the input ends, "
                  f"with no reader on stderr, as when the ssh client has died: not exit 0, "
                  f"the test log left byte for byte, and no other file",
                  cut_short.returncode != 0
                  and test_log.read_bytes() == first.encode("utf-8")
                  and files_left() == ["a-head.txt"],
                  f"{cut_short.returncode} {files_left()}")
        with open(test_log, "rb") as reader_of_the_test_log:
            added = write(second)
            read_after_the_write = reader_of_the_test_log.read()
        check(f"under {shell} a second whole record is added to the end of the test log the "
              f"first is in, not put in a new file: exit 0, nothing said, the first record "
              f"still there byte for byte and first, a reader that opened the test log "
              f"before the write reads both records, and no other file",
              added.returncode == 0 and added.stdout == b"" and added.stderr == b""
              and test_log.read_bytes() == (first + second).encode("utf-8")
              and read_after_the_write == (first + second).encode("utf-8")
              and files_left() == ["a-head.txt"],
              f"{added.returncode} {added.stderr!r} {read_after_the_write!r}")
        # A write the test log takes part of. Under a limit of one block on
        # the size of a file, 512 bytes or 1024 by the shell, a test log of
        # fewer bytes takes the start of a record of 4096 and no more.
        short = write(first, file_name="another-head.txt")
        another_test_log = test_log.with_name("another-head.txt")
        of_4096_bytes = "x" * 4095 + "\n"
        taken_in_part = write(of_4096_bytes, file_name="another-head.txt",
                              before="ulimit -f 1; ")
        check(f"under {shell} a short append exits 1, leaves the partial record in the "
              f"test log, says nothing on stdout, and reports the failure and manual repair",
              short.returncode == 0 and taken_in_part.returncode == 1
              and len(first.encode("utf-8")) < another_test_log.stat().st_size
              < len((first + of_4096_bytes).encode("utf-8"))
              and (first + of_4096_bytes).encode("utf-8").startswith(
                  another_test_log.read_bytes())
              and taken_in_part.stdout == b""
              and taken_in_part.stderr.decode("utf-8") == "pull-request-head-test-run: not "
              "written: the test log took only part of the record.\n"
              "Before appending another record, repair the partial record in the test log "
              "by hand.\n",
              f"{short.returncode} {taken_in_part.returncode} {taken_in_part.stderr!r} "
              f"{len(another_test_log.read_bytes())}")


def run_cases_of_what_the_write_command_holds():
    command = program.write_record_command("/a/log-store/root", "ned-box", "a-head.txt", 2354)
    held = program.PULL_REQUEST_HEAD_TEST_LOG_APPEND_PROGRAM
    check("the command that writes the record holds ASCII characters alone when the path "
          "it is given does: the program hands it to a process as an argument, and a "
          "filesystem encoding with no such character would stop the run",
          command.isascii(),
          repr(sorted({character for character in command if not character.isascii()})))
    check("the command is one line, as the refusal that prints it is, and is `exec python3 "
          "-c`, the program in one pair of single quotes, the test log's path and the "
          "count: the program holds no single quote and no line break",
          "'" not in held and "\n" not in held
          and command == f"exec python3 -c '{held}' /a/log-store/root/"
                         f"pull-request-head-test-runs/ned-box/a-head.txt 2354", command)


def run_cases_of_the_two_byte_counts(workspace: Path):
    """The count in the command the program runs is of the bytes the program
    sends, which the preferred encoding makes; the count in the remedy it
    prints is of the local copy's bytes, which are UTF-8. Where this suite
    runs the preferred encoding is UTF-8 and the two counts are one number.
    So the program is told here, for one run, that the preferred encoding is
    UTF-16, which makes of every text another number of bytes than UTF-8
    does. The stand-in ssh still gets the bytes this machine's encoding makes,
    fewer than that count, so the write is refused as cut short and the
    remedy is printed."""
    fixture = Fixture(workspace / "on-the-mac-told-another-preferred-encoding")
    record_path = f"pull-request-head-test-runs/mac/{fixture.head}.txt"
    locale_of_the_program = program.locale
    program.locale = types.SimpleNamespace(
        getpreferredencoding=lambda do_setlocale=True: "utf-16-le")
    try:
        result = fixture.run(hostname="a-mac-that-is-not-ned-box")
    finally:
        program.locale = locale_of_the_program
    local_copy = (fixture.local_copy().read_text(encoding="utf-8")
                  if fixture.local_copy().is_file() else "")
    as_utf_16 = len(local_copy.encode("utf-16-le"))
    as_utf_8 = len(local_copy.encode("utf-8"))
    remedy_as_printed = result.stderr.rstrip("\n").rpartition(
        "by running on this machine: ")[2]
    # The count is the command's last word.
    count_the_program_ran_with = re.findall(r"\.txt (\d+)$", (result.ssh_calls or [""])[0])
    count_in_the_remedy = re.findall(r"\.txt (\d+)' < ", remedy_as_printed)
    check("told that the preferred encoding is UTF-16, the program gives the command it "
          "runs the count of the record's UTF-16 bytes, the bytes it would send, and the "
          "remedy it prints the count of the local copy's UTF-8 bytes",
          result.code == 5 and local_copy != "" and as_utf_16 != as_utf_8
          and len(result.ssh_calls) == 1
          and count_the_program_ran_with == [str(as_utf_16)]
          and count_in_the_remedy == [str(as_utf_8)]
          and f"not written: {as_utf_16} bytes of the record were sent and another count "
              f"arrived." in result.stderr
          and fixture.record_files() == [],
          f"{result!r}\n{as_utf_16} {as_utf_8}")
    scratch = fixture.scratch_for_next_run()
    reachable = fixture.fake_ssh_directory(scratch, SSH_THAT_RUNS_THE_COMMAND_HERE)
    environment = program.run_all_test_suites.environment_without_git_redirecting_variables()
    environment["PATH"] = f"{reachable}{os.pathsep}{environment.get('PATH', '')}"
    written_by_hand = subprocess.run(["/bin/sh", "-c", remedy_as_printed], env=environment,
                                     capture_output=True, text=True, check=False)
    check("that remedy, run as printed, writes the local copy whole: its count is the "
          "count of the bytes it is fed",
          written_by_hand.returncode == 0 and local_copy != ""
          and fixture.test_log("mac") == local_copy
          and fixture.record_files() == [record_path],
          f"{written_by_hand.returncode} {written_by_hand.stderr}")


def run_cases_of_two_writers_at_once(workspace: Path):
    """The command that writes a record, run twice at once on one test log:
    the first writer has been handed half its record when the second is
    handed all of its own."""
    root = workspace / "two-writers-at-once"
    of_the_first = "the first writer's first half\nthe first writer's second half\n"
    of_the_second = "the second writer's whole record\n"
    first = program.write_record_command(
        str(root), "ned-box", "a-head.txt", len(of_the_first))
    second = program.write_record_command(
        str(root), "ned-box", "a-head.txt", len(of_the_second))
    test_log = root / "pull-request-head-test-runs" / "ned-box" / "a-head.txt"
    writer = subprocess.Popen(["/bin/sh", "-c", first], stdin=subprocess.PIPE, text=True,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        writer.stdin.write("the first writer's first half\n")
        writer.stdin.flush()
        other = subprocess.run(["/bin/sh", "-c", second], capture_output=True, text=True,
                               input=of_the_second, check=False)
        after_the_second = (test_log.read_text(encoding="utf-8") if test_log.is_file()
                            else None)
        files_after_the_second = (sorted(os.listdir(test_log.parent))
                                  if test_log.parent.is_dir() else None)
        writer.stdin.write("the first writer's second half\n")
        writer.stdin.close()
        code_of_the_first = writer.wait(timeout=20)
    finally:
        if writer.poll() is None:
            writer.kill()
            writer.wait()
    check("a second writer that writes its whole record while the first has been handed "
          "half of its own: exit 0, the test log is the second writer's record and nothing "
          "more, and no other file is beside it: no part of a record still on its way is "
          "in the log-store",
          other.returncode == 0 and after_the_second == of_the_second
          and files_after_the_second == ["a-head.txt"],
          f"{other.returncode} {other.stderr} {after_the_second!r} {files_after_the_second}")
    files_left = sorted(os.listdir(test_log.parent)) if test_log.parent.is_dir() else None
    check("the first writer, finishing last, adds its own whole record after the second "
          "writer's, which is still there byte for byte, and leaves no other file",
          code_of_the_first == 0 and test_log.is_file()
          and test_log.read_text(encoding="utf-8") == of_the_second + of_the_first
          and files_left == ["a-head.txt"], f"{code_of_the_first} {files_left}")


def run_cases_as_a_program(workspace: Path):
    """The program run as a reviewer runs it: its own process, its real clock
    and wait, the moment taken from the machine. ned-box is the fake ssh on
    either machine, so the case holds on both."""
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
    check("run as a program it exits 0, writes one record named by the head's hash, and "
          "prints the SUMMARY line and the citation",
          completed.returncode == 0 and len(written) == 1
          and re.fullmatch(rf"pull-request-head-test-runs/(ned-box|mac)/{fixture.head}\.txt",
                           written[0]) is not None
          and completed.stdout == PASSING_SUMMARY_LINE + "\npull-request-head-test-run: "
          f"record written to nedlern@ned-box:{fixture.log_store}/{written[0]}\n",
          f"{completed.returncode} {written!r}\n{completed.stdout}\n{completed.stderr}")
    check("that record holds the SUMMARY line, both counts of seconds as whole numbers, "
          "and a logs directory named by the head, a UTC moment and the process",
          PASSING_SUMMARY_LINE in record.splitlines()
          and re.search(r"^seconds waiting for the machine's lock: 0$", record, re.M)
          and re.search(r"^wall-clock seconds: \d+$", record, re.M)
          and re.search(rf"^logs: {re.escape(str(fixture.temporary))}/"
                        rf"nedschorus-pull-request-head-test-run/{fixture.head}-"
                        r"\d{8}T\d{6}Z-\d+/logs on (ned-box|mac)$", record, re.M), record)
    invalid = subprocess.run([sys.executable, str(SCRIPT_PATH), "--no-such-option"],
                             env=environment, stdin=subprocess.DEVNULL,
                             capture_output=True, text=True, check=False)
    check("an option it does not have is a bad invocation, exit 2, and nothing is run",
          invalid.returncode == 2 and fixture.record_files() == written,
          f"{invalid.returncode} {invalid.stderr}")

    # --- An exception nothing catches ----------------------------------------------
    stopped_by_an_error = ("pull-request-head-test-run: not finished — the error above "
                           "stopped this program, and this run gives no verdict.\n"
                           "Tell the user what the error above says.\n")
    a_file = scratch / "a-file-where-the-temporary-directory-should-be"
    a_file.write_text("not a directory\n", encoding="utf-8")
    stopped = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--checkout", str(fixture.checkout),
         "--log-store-root", str(fixture.log_store), "--temporary-directory", str(a_file),
         "--test-suite-runner-program", str(fixture.runner)],
        env=environment, stdin=subprocess.DEVNULL, capture_output=True, text=True,
        check=False)
    check("an exception nothing catches, here a temporary directory that is a file, exits "
          "7, not Python's 1 that reads as a failed suite: the traceback on stderr, then "
          "what the exit means and what to do, nothing on stdout, and no record written",
          stopped.returncode == 7 and stopped.stdout == ""
          and stopped.stderr.startswith("Traceback (most recent call last):\n")
          and "NotADirectoryError" in stopped.stderr
          and stopped.stderr.endswith(stopped_by_an_error)
          and fixture.record_files() == written,
          f"{stopped.returncode}\n{stopped.stdout}\n{stopped.stderr}")
    copies = scratch / "copies" / "scripts"
    copies.mkdir(parents=True)
    shutil.copy(SCRIPT_PATH, copies / SCRIPT_PATH.name)
    (copies / "daily-full-test-run-of-main.py").write_text(
        'raise RuntimeError("a module that does not load")\n', encoding="utf-8")
    not_loaded = subprocess.run(
        [sys.executable, str(copies / SCRIPT_PATH.name), *fixture.arguments()],
        env=environment, stdin=subprocess.DEVNULL, capture_output=True, text=True,
        check=False)
    check("a module this program loads that does not load exits 7 the same way",
          not_loaded.returncode == 7 and not_loaded.stdout == ""
          and "RuntimeError: a module that does not load" in not_loaded.stderr
          and not_loaded.stderr.endswith(stopped_by_an_error)
          and fixture.record_files() == written,
          f"{not_loaded.returncode}\n{not_loaded.stdout}\n{not_loaded.stderr}")


def run_log_store_readme_cases():
    readme = record_shipper.STORE_README
    kind = program.PULL_REQUEST_HEAD_TEST_RUNS_KIND_DIRECTORY_NAME
    check("the log-store's README lists pull-request-head-test-runs/ once, naming this "
          "program as its owner",
          kind == "pull-request-head-test-runs" and readme.count(f"`{kind}/`") == 1
          and f"- `{kind}/` -- " in readme
          and "`scripts/pull-request-head-test-run.py`" in readme, readme)


with tempfile.TemporaryDirectory() as temporary_directory:
    # Resolved, because the program resolves the paths it is given and the
    # Mac's temporary directory is reached through a symbolic link.
    workspace_root = Path(temporary_directory).resolve()
    run_cases_on_ned_box(workspace_root)
    run_cases_of_a_subject_that_holds_line_boundaries_that_are_no_line_feed(workspace_root)
    run_cases_on_the_mac(workspace_root)
    run_cases_of_a_record_cut_short_on_the_way(workspace_root)
    run_cases_of_a_record_the_test_log_takes_part_of(workspace_root)
    run_cases_of_the_write_command_under_each_shell(workspace_root)
    run_cases_of_what_the_write_command_holds()
    run_cases_of_the_two_byte_counts(workspace_root)
    run_cases_of_two_writers_at_once(workspace_root)
    run_cases_as_a_program(workspace_root)
    run_log_store_readme_cases()

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
