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
the moment, the wait and the clock are passed in, so no case sleeps, and a
case of two runs started in one second gives the second run a process number
of its own, as two real runs have. The far side of an ssh whose client has
died is played by the command run with stderr a pipe whose reader is gone, and
a preferred encoding that is not UTF-8 by a `locale` the program is handed for
one run. A writer that was killed part way is played by a file named with a
process number no process has, and two writers of one run at once by holding
the first writer's input while the second starts. The one
case that passes no --test-suite-runner-program replaces the function that
runs the runner, so the real runner beside the program is named and never
started. The wait passed in counts its calls and stops a case that waits more
often than any case's bound allows, so a wait that lost its bound fails its
case and does not hang the suite.

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
import time
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
# Above every process number either machine gives out: Linux stops at 2^22,
# macOS at 99998. `kill -0` of it fails, as of a writer that no longer runs.
A_PROCESS_NUMBER_NO_PROCESS_HAS = 999999999
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

    def clone_of_origin(self, name: str) -> Path:
        clone = self.root / name
        fixture_git(self.root, "clone", "-q", str(self.origin), str(clone))
        if not (clone / ".git").is_dir():
            raise SystemExit(f"fixture: no clone was made at {clone}")
        return clone

    def run_directory(self, head=None, moment=THE_MOMENT) -> Path:
        """The directory a run made at the moment by this process keeps its
        logs and the record's local copy in."""
        return (self.temporary / program.PULL_REQUEST_HEAD_TEST_RUN_DIRECTORY_NAME
                / f"{head or self.head}-{moment:%Y%m%dT%H%M%SZ}-{os.getpid()}")

    def logs(self, head=None) -> Path:
        return self.run_directory(head) / program.PULL_REQUEST_HEAD_TEST_RUN_LOGS_DIRECTORY_NAME

    def local_copy(self, head=None, moment=THE_MOMENT) -> Path:
        return (self.run_directory(head, moment)
                / program.PULL_REQUEST_HEAD_TEST_RUN_RECORD_LOCAL_COPY_FILE_NAME)

    def write_command(self, machine: str, record: str, moment=THE_MOMENT,
                      keeps_a_record_that_started_no_earlier=False):
        """The shell command a run of the head made at the moment by this
        process writes the record with; with
        keeps_a_record_that_started_no_earlier, the form its remedy is printed
        in. No path of a fixture needs quoting. The count is the record's
        UTF-8 length in both forms: where this suite runs the preferred
        encoding is UTF-8, and run_cases_of_the_two_byte_counts tells the two
        counts apart. `$$` stands in the text as the program wrote it: the
        shell that runs the command makes its own process number of it."""
        bytes_sent = len(record.encode("utf-8"))
        directory = f"{self.log_store}/pull-request-head-test-runs/{machine}"
        record_path = f"{directory}/{self.head}.txt"
        files_of_the_run = (f"{directory}/.{self.head}.txt.{moment:%Y%m%dT%H%M%SZ}-"
                            f"{os.getpid()}")
        partial = '"$partial"'
        sweeps = ""
        keeps = ""
        if keeps_a_record_that_started_no_earlier:
            sweeps = (f"{{ for left in {files_of_the_run}.*.partial; do "
                      f"writer=${{left%.partial}}; kill -0 \"${{writer##*.}}\" 2>/dev/null "
                      f"|| rm -f \"$left\"; done; }} && ")
            keeps = (f"if [ -e {record_path} ] && "
                     f"! [ \"$(sed -n '1s/^.*, started //p' {record_path})\" "
                     f"\\< {moment:%Y-%m-%dT%H:%M:%SZ} ]; then "
                     f"if cmp -s {partial} {record_path}; then "
                     f"rm -f {partial}; echo 'pull-request-head-test-run: already written: "
                     f"the record there is the whole record of this run, byte for byte.'; "
                     f"echo 'Tell the user the record is written.'; exit 0; fi; "
                     f"rm -f {partial}; echo "
                     f"'pull-request-head-test-run: not written: the record there is of a "
                     f"run that started in the same second or later.' >&2; echo 'Leave that "
                     f"record as it is.' >&2; exit 1; fi && ")
        return (f"partial={files_of_the_run}.$$.partial && mkdir -p {directory} && "
                f"{sweeps}cat > {partial} && "
                f"{{ [ \"$(wc -c < {partial})\" -eq {bytes_sent} ] || {{ rm -f {partial}; echo "
                f"'pull-request-head-test-run: not written: {bytes_sent} bytes of the "
                f"record were sent and another count arrived.' >&2; echo 'Run this command "
                f"again.' >&2; false; }}; }} && {keeps}mv -f {partial} {record_path} "
                f"|| {{ rm -f {partial}; exit 1; }}")

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
            started_in=None, stand_in_runner_behaviour=None,
            process_number=None) -> RunResult:
        """main's exit code and output, with the fake ssh's calls, the stand-in
        runner's calls and the waits main asked for. The clock is the sum of
        those waits, so a case takes no time. during_each_wait is called in
        each wait, to change the checkout while the program waits for the
        lock; runner_changes_the_checkout is what the stand-in runner does to
        the checkout once it is past the lock; stand_in_runner_behaviour is
        any other key of the stand-in runner's behaviour file. process_number
        is the process number the run reads as its own, for a run played as
        another process's: the run's directory and the file it writes its
        record to are named by it. A run that waits more often than any case
        asks for is stopped, and its exit code is
        WAITED_MORE_OFTEN_THAN_ANY_CASE_ASKS_FOR."""
        scratch = self.scratch_for_next_run()
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
        if process_number is not None:
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
        return RunResult(code, stdout.getvalue(), stderr.getvalue(), ssh_calls, runner_calls,
                         waits)

    def record_files(self):
        """Every file under the log-store root, relative to it."""
        return sorted(str(path.relative_to(self.log_store))
                      for path in self.log_store.rglob("*") if path.is_file())

    def record(self, machine: str, head=None):
        path = (self.log_store / program.PULL_REQUEST_HEAD_TEST_RUNS_KIND_DIRECTORY_NAME
                / machine / f"{head or self.head}.txt")
        return path.read_text(encoding="utf-8") if path.is_file() else None

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
    check("the whole record: this program's line, the head, the commit the selection "
          "started from, the runner and its commit, the runner's whole output, the exit "
          "code, both counts of seconds and the logs' directory",
          record == "\n".join([
              "pull-request-head-test-run: ned-box, started 2026-10-01T03:30:00Z",
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
          "--only-suites-whose-recorded-inputs-changed-since <since> -j 4 --log-dir <logs>, "
          "with no --recorded-inputs-directory",
          len(result.runner_calls) == 1
          and call.get("argv") == [
              str(fixture.runner), "--checkout", str(fixture.checkout),
              "--only-suites-whose-recorded-inputs-changed-since", fixture.merge_base,
              "-j", "4", "--log-dir", str(fixture.logs())]
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
    check("a second run of the same head on the same machine replaces the record: one "
          "file, holding the second run alone",
          fixture.record_files() == [record_path]
          and PASSING_SUMMARY_LINE not in record_lines, f"{fixture.record_files()} {record!r}")

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
    record_before = fixture.record("ned-box")
    (fixture.checkout / "a-change.txt").write_text("changed after the commit\n",
                                                   encoding="utf-8")
    result = fixture.run()
    check("a checkout with a tracked file that differs from its commit is refused: exit 2, "
          "the runner is not run, no record is written, and stderr is what differs and "
          "what to pass",
          result.code == 2 and result.runner_calls == [] and result.stdout == ""
          and fixture.record_files() == [record_path]
          and fixture.record("ned-box") == record_before
          and result.stderr == "pull-request-head-test-run: not run — a tracked file in "
          f"{fixture.checkout} differs from its commit {fixture.head}: a-change.txt\n"
          "Pass --checkout a checkout whose tracked files match the commit to test, such as "
          "a detached worktree at that commit.\n", repr(result))
    fixture_git(fixture.checkout, "add", "a-change.txt")
    result = fixture.run()
    check("a change that is staged and nothing more is refused the same way",
          result.code == 2 and result.runner_calls == [] and result.stdout == ""
          and fixture.record("ned-box") == record_before
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
          and fixture.record("ned-box") == record_before
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
    result = fixture.run(checkout=not_a_checkout)
    check("a directory with no commit is refused: exit 2, nothing run, nothing written",
          result.code == 2 and result.runner_calls == [] and result.stdout == ""
          and fixture.record_files() == [record_path]
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
          "replaces the record",
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

    # --- The record's local copy cannot be written --------------------------------
    record_before = fixture.record("ned-box")
    fixture.local_copy().unlink()
    fixture.local_copy().mkdir()
    result = fixture.run(exits=(1,), lines=FAILING_RUNNER_LINES)
    fixture.local_copy().rmdir()
    check("when the record's local copy cannot be written the program exits 5, leaves the "
          "log-store's record as it was, and says what failed and what to do",
          result.code == 5 and result.stdout == "" and fixture.record("ned-box") == record_before
          and result.stderr.startswith(
              "pull-request-head-test-run: the record was not written: its local copy "
              f"{fixture.local_copy()} could not be written (IsADirectoryError: ")
          and result.stderr.endswith(
              "\nTell the user what the line above says.\n"
              "Fix what the error names, then run this again.\n"), repr(result))


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
    check("the write leaves the record alone in its directory",
          fixture.record_files() == [record_path], repr(fixture.record_files()))
    check("the Mac's record names the mac, in its first line and beside the logs",
          record is not None and record.startswith(
              "pull-request-head-test-run: mac, started 2026-10-01T03:30:00Z\n")
          and record.endswith(f"logs: {fixture.logs()} on mac\n"
                              "pull-request-head-test-run exit code: 0\n"), repr(record))
    check("the citation names ned-box and the mac's directory",
          result.stdout == PASSING_SUMMARY_LINE + "\npull-request-head-test-run: record "
          f"written to nedlern@ned-box:{fixture.log_store}/{record_path}\n", result.stdout)
    result = fixture.run(hostname="ned-box")
    check("a run of the same head on ned-box leaves the Mac's record and adds its own",
          result.code == 0 and fixture.record("mac") == record
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
              + shlex.quote(unreachable.write_command(
                  "mac", local_copy or "", keeps_a_record_that_started_no_earlier=True))
              + f" < {unreachable.local_copy()}")
    check("when ned-box cannot be reached the program exits 5, cites nothing and writes "
          "nothing into the log-store",
          result.code == 5 and result.stdout == "" and unreachable.record_files() == []
          and len(result.runner_calls) == 1, repr(result))
    check("when ned-box cannot be reached stderr is what failed, then one instruction a "
          "line: tell the user, and the command that writes the record",
          result.stderr == "pull-request-head-test-run: the record was not written to "
          f"nedlern@ned-box:{target} (ssh nedlern@ned-box exited 255: ssh: connect to host "
          "ned-box port 22: No route to host).\n"
          "Tell the user what the line above says, and the remedy in the line below.\n"
          "When ned-box answers ssh again, write the record by running on this machine: "
          f"{remedy}\n", result.stderr)
    check("the record that could not be written is kept beside the logs",
          local_copy is not None and PASSING_SUMMARY_LINE in local_copy.splitlines(),
          repr(local_copy))
    check("that record closes with the exit code the run would have exited with, 0, "
          "while the program, its record not written, exits 5",
          result.code == 5 and local_copy is not None
          and local_copy.splitlines()[-1:] == ["pull-request-head-test-run exit code: 0"],
          f"{result.code} {local_copy!r}")
    # The command as stderr printed it is what the two cases below run.
    remedy_as_printed = result.stderr.rstrip("\n").rpartition(
        "by running on this machine: ")[2]
    scratch = unreachable.scratch_for_next_run()
    reachable_again = unreachable.fake_ssh_directory(scratch, SSH_THAT_RUNS_THE_COMMAND_HERE)
    environment = program.run_all_test_suites.environment_without_git_redirecting_variables()
    environment["PATH"] = f"{reachable_again}{os.pathsep}{environment.get('PATH', '')}"
    written_by_hand = subprocess.run(["/bin/sh", "-c", remedy_as_printed], env=environment,
                                     capture_output=True, text=True, check=False)
    check("the command stderr gives writes that record once ned-box answers",
          written_by_hand.returncode == 0 and unreachable.record("mac") == local_copy,
          f"{written_by_hand.returncode} {written_by_hand.stderr}")

    # --- That command, run after a later run of the same head wrote its record ----
    later = unreachable.run(hostname="a-mac-that-is-not-ned-box", exits=(1,),
                            lines=FAILING_RUNNER_LINES, moment=A_LATER_MOMENT)
    record_of_the_later_run = unreachable.record("mac")
    written_by_hand = subprocess.run(["/bin/sh", "-c", remedy_as_printed], env=environment,
                                     capture_output=True, text=True, check=False)
    check("run after a later run of the same head has written its record, that command "
          "writes nothing, exits 1, and says to leave the record as it is",
          later.code == 1 and record_of_the_later_run is not None
          and record_of_the_later_run.startswith(
              "pull-request-head-test-run: mac, started 2026-10-01T04:00:00Z\n")
          and FAILING_SUMMARY_LINE in record_of_the_later_run.splitlines()
          and written_by_hand.returncode == 1
          and unreachable.record("mac") == record_of_the_later_run
          and unreachable.record_files()
          == [f"pull-request-head-test-runs/mac/{unreachable.head}.txt"]
          and written_by_hand.stderr == "pull-request-head-test-run: not written: the "
          "record there is of a run that started in the same second or later.\n"
          "Leave that record as it is.\n",
          f"{later!r}\n{written_by_hand.returncode} {written_by_hand.stderr}")

    earlier = Fixture(workspace / "on-the-mac-with-an-earlier-record")
    first = earlier.run(hostname="a-mac-that-is-not-ned-box", moment=AN_EARLIER_MOMENT)
    record_of_the_earlier_run = earlier.record("mac")
    second = earlier.run(hostname="a-mac-that-is-not-ned-box", exits=(1,),
                         lines=FAILING_RUNNER_LINES,
                         ssh_body=SSH_THAT_CANNOT_REACH_NED_BOX)
    remedy_of_the_second_run = second.stderr.rstrip("\n").rpartition(
        "by running on this machine: ")[2]
    scratch = earlier.scratch_for_next_run()
    reachable_again = earlier.fake_ssh_directory(scratch, SSH_THAT_RUNS_THE_COMMAND_HERE)
    environment = program.run_all_test_suites.environment_without_git_redirecting_variables()
    environment["PATH"] = f"{reachable_again}{os.pathsep}{environment.get('PATH', '')}"
    written_by_hand = subprocess.run(["/bin/sh", "-c", remedy_of_the_second_run],
                                     env=environment, capture_output=True, text=True,
                                     check=False)
    check("run when the record there is of an earlier run, that command replaces the "
          "earlier run's record with its own run's",
          first.code == 0 and second.code == 5
          and record_of_the_earlier_run is not None
          and record_of_the_earlier_run.startswith(
              "pull-request-head-test-run: mac, started 2026-10-01T03:00:00Z\n")
          and written_by_hand.returncode == 0
          and earlier.local_copy().is_file()
          and earlier.record("mac") == earlier.local_copy().read_text(encoding="utf-8")
          and FAILING_SUMMARY_LINE in (earlier.record("mac") or "").splitlines(),
          f"{first!r}\n{second!r}\n{written_by_hand.returncode} {written_by_hand.stderr}")

    # --- That command, run after a run started in the same second wrote its record -
    tie = Fixture(workspace / "on-the-mac-with-two-runs-started-in-one-second")
    first = tie.run(hostname="a-mac-that-is-not-ned-box",
                    ssh_body=SSH_THAT_CANNOT_REACH_NED_BOX)
    remedy_of_the_first_run = first.stderr.rstrip("\n").rpartition(
        "by running on this machine: ")[2]
    record_the_first_run_kept = (tie.local_copy().read_text(encoding="utf-8")
                                 if tie.local_copy().is_file() else "")
    second = tie.run(hostname="a-mac-that-is-not-ned-box", exits=(1,),
                     lines=FAILING_RUNNER_LINES, process_number=os.getpid() + 1)
    record_of_the_second_run = tie.record("mac")
    scratch = tie.scratch_for_next_run()
    reachable_again = tie.fake_ssh_directory(scratch, SSH_THAT_RUNS_THE_COMMAND_HERE)
    environment = program.run_all_test_suites.environment_without_git_redirecting_variables()
    environment["PATH"] = f"{reachable_again}{os.pathsep}{environment.get('PATH', '')}"
    written_by_hand = subprocess.run(["/bin/sh", "-c", remedy_of_the_first_run],
                                     env=environment, capture_output=True, text=True,
                                     check=False)
    check("two runs of one head started in the same second, the first passing with its "
          "record not written, the second failing with its record written: both records "
          "spell the same started moment, and the first run's record is still beside its "
          "logs",
          first.code == 5 and second.code == 1 and record_of_the_second_run is not None
          and record_the_first_run_kept.splitlines()[:1]
          == record_of_the_second_run.splitlines()[:1]
          == ["pull-request-head-test-run: mac, started 2026-10-01T03:30:00Z"]
          and PASSING_SUMMARY_LINE in record_the_first_run_kept.splitlines()
          and FAILING_SUMMARY_LINE in record_of_the_second_run.splitlines()
          and tie.local_copy().is_file()
          and tie.local_copy().read_text(encoding="utf-8") == record_the_first_run_kept,
          f"{first!r}\n{second!r}")
    check("the first run's remedy, run as printed after that, writes nothing, exits 1, "
          "and says to leave the record as it is: the failing run's record is not replaced "
          "by the passing run's",
          written_by_hand.returncode == 1
          and tie.record("mac") == record_of_the_second_run
          and record_of_the_second_run is not None
          and tie.record_files() == [f"pull-request-head-test-runs/mac/{tie.head}.txt"]
          and written_by_hand.stderr == "pull-request-head-test-run: not written: the "
          "record there is of a run that started in the same second or later.\n"
          "Leave that record as it is.\n",
          f"{written_by_hand.returncode} {written_by_hand.stderr}\n{tie.record('mac')!r}")


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
              f"ends, the program exits 5 and says the record was not written, the earlier "
              f"run's whole record is left byte for byte, and no other file is left",
              earlier.code == 0 and record_of_the_earlier_run is not None
              and len(local_copy.encode("utf-8")) > 300
              and result.code == 5 and result.stdout == ""
              and fixture.record("mac") == record_of_the_earlier_run
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
          "writes nothing, exits 1, leaves the earlier run's whole record byte for byte "
          "and no other file, and says what arrived and what to do",
          cut_short.returncode == 1 and record_of_the_earlier_run is not None
          and fixture.record("mac") == record_of_the_earlier_run
          and fixture.record_files() == [record_path]
          and cut_short.stderr == "pull-request-head-test-run: not written: "
          f"{len(local_copy.encode('utf-8'))} bytes of the record were sent and another "
          "count arrived.\nRun this command again.\n",
          f"{cut_short.returncode} {cut_short.stderr}")
    written_by_hand = subprocess.run(["/bin/sh", "-c", remedy_as_printed], env=environment,
                                     capture_output=True, text=True, check=False)
    check("the remedy, run as printed once the far side gets the whole record, writes "
          "that run's whole record over the earlier run's",
          written_by_hand.returncode == 0 and fixture.record("mac") == local_copy
          and FAILING_SUMMARY_LINE in local_copy.splitlines()
          and fixture.record_files() == [record_path],
          f"{written_by_hand.returncode} {written_by_hand.stderr}")
    run_a_second_time = subprocess.run(["/bin/sh", "-c", remedy_as_printed], env=environment,
                                       capture_output=True, text=True, check=False)
    check("the remedy, run a second time, finds its own run's whole record there: it "
          "writes nothing, exits 0, leaves no other file, and says the record is written",
          run_a_second_time.returncode == 0 and fixture.record("mac") == local_copy
          and fixture.record_files() == [record_path]
          and run_a_second_time.stderr == ""
          and run_a_second_time.stdout == "pull-request-head-test-run: already written: "
          "the record there is the whole record of this run, byte for byte.\n"
          "Tell the user the record is written.\n",
          f"{run_a_second_time.returncode} {run_a_second_time.stdout} "
          f"{run_a_second_time.stderr}")

    # --- The far side renamed the record, and the client died before the exit
    # status came back: the program says the record was not written, and the
    # record is in place.
    renamed = Fixture(workspace / "on-the-mac-with-a-client-that-died-after-the-rename")
    record_path = f"pull-request-head-test-runs/mac/{renamed.head}.txt"
    result = renamed.run(hostname="a-mac-that-is-not-ned-box",
                         ssh_body=SSH_THAT_RUNS_THE_COMMAND_HERE_AND_THEN_FAILS)
    local_copy = (renamed.local_copy().read_text(encoding="utf-8")
                  if renamed.local_copy().is_file() else "")
    remedy_as_printed = result.stderr.rstrip("\n").rpartition(
        "by running on this machine: ")[2]
    scratch = renamed.scratch_for_next_run()
    reachable = renamed.fake_ssh_directory(scratch, SSH_THAT_RUNS_THE_COMMAND_HERE)
    environment = program.run_all_test_suites.environment_without_git_redirecting_variables()
    environment["PATH"] = f"{reachable}{os.pathsep}{environment.get('PATH', '')}"
    written_by_hand = subprocess.run(["/bin/sh", "-c", remedy_as_printed], env=environment,
                                     capture_output=True, text=True, check=False)
    check("when the far side renamed the record and the ssh client then failed, the "
          "program exits 5 and says the record was not written, with the run's whole "
          "record in place; the remedy, run as printed, writes nothing, exits 0, leaves no "
          "other file, and says the record is written",
          result.code == 5 and local_copy != ""
          and result.stderr.startswith(
              "pull-request-head-test-run: the record was not written to "
              f"nedlern@ned-box:{renamed.log_store}/{record_path} (ssh nedlern@ned-box "
              f"exited 255: ssh: the connection was lost).\n")
          and written_by_hand.returncode == 0 and renamed.record("mac") == local_copy
          and renamed.record_files() == [record_path]
          and written_by_hand.stderr == ""
          and written_by_hand.stdout == "pull-request-head-test-run: already written: the "
          "record there is the whole record of this run, byte for byte.\n"
          "Tell the user the record is written.\n",
          f"{result!r}\n{written_by_hand.returncode} {written_by_hand.stdout} "
          f"{written_by_hand.stderr}")


def run_cases_of_the_write_command_under_each_shell(workspace: Path):
    """The command that writes the record, run by itself under /bin/sh and
    under bash and dash where the machine has them: ned-box's /bin/sh is
    dash, the Mac's is bash, and `wc -c` pads its count on the Mac."""
    earlier = "the earlier run's whole record\nwith a second line — and its last\n"
    later = "the later run's whole record, which is longer\nline two\nline three\n"
    for shell in ("/bin/sh", "/bin/bash", "/bin/dash"):
        if not Path(shell).is_file():
            print(f"SKIP  the write command under {shell}: this machine has no {shell}")
            continue
        root = workspace / f"the-write-command-under-{Path(shell).name}"
        record = root / "pull-request-head-test-runs" / "ned-box" / "a-head.txt"

        def write(text_sent, handed_over, run_name):
            command = program.write_record_command(
                str(root), "ned-box", "a-head.txt", run_name, len(text_sent.encode("utf-8")))
            return subprocess.run([shell, "-c", command], input=handed_over.encode("utf-8"),
                                  capture_output=True, check=False)

        def files_left():
            return sorted(os.listdir(record.parent)) if record.parent.is_dir() else None

        def run_with_no_reader_on(stream, command, handed_over):
            """The command run with stdout or stderr a pipe whose reader is
            gone, as on the far side of an ssh whose client has died: the
            shell's first write there kills the shell."""
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

        def run_with_no_reader_on_stderr(command, handed_over):
            return run_with_no_reader_on("stderr", command, handed_over)

        first = write(earlier, earlier, "the-earlier-run")
        check(f"under {shell} a whole record is written: exit 0, the record byte for byte, "
              f"and no other file",
              first.returncode == 0 and record.is_file()
              and record.read_bytes() == earlier.encode("utf-8")
              and files_left() == ["a-head.txt"], f"{first.returncode} {first.stderr!r}")
        for handed_over_name, handed_over in (("half the record", later[:20]),
                                              ("nothing", ""),
                                              ("the record and a line more",
                                               later + "a line more\n")):
            cut_short = write(later, handed_over, "the-later-run")
            check(f"under {shell}, {handed_over_name} handed over before the input ends: "
                  f"exit 1, the earlier whole record left byte for byte, the file the "
                  f"command wrote to removed, and stderr what arrived and what to do",
                  cut_short.returncode == 1 and record.is_file()
                  and record.read_bytes() == earlier.encode("utf-8")
                  and files_left() == ["a-head.txt"]
                  and cut_short.stderr.decode("utf-8") == "pull-request-head-test-run: not "
                  f"written: {len(later.encode('utf-8'))} bytes of the record were sent "
                  "and another count arrived.\nRun this command again.\n",
                  f"{cut_short.returncode} {cut_short.stderr!r} {files_left()}")
            cut_short = run_with_no_reader_on_stderr(
                program.write_record_command(
                    str(root), "ned-box", "a-head.txt", "the-later-run",
                    len(later.encode("utf-8"))), handed_over)
            check(f"under {shell}, {handed_over_name} handed over before the input ends, "
                  f"with no reader on stderr, as when the ssh client has died: not exit 0, "
                  f"the earlier whole record left byte for byte, and the file the command "
                  f"wrote to removed",
                  cut_short.returncode != 0 and record.is_file()
                  and record.read_bytes() == earlier.encode("utf-8")
                  and files_left() == ["a-head.txt"],
                  f"{cut_short.returncode} {files_left()}")
        # The count is right and the rename fails: the one state in which the
        # command's last part, and nothing before it, removes the file the
        # command wrote to. `mv` is played by a program that exits 1.
        a_mv_that_fails = workspace / f"a-mv-that-fails-under-{Path(shell).name}"
        a_mv_that_fails.mkdir()
        (a_mv_that_fails / "mv").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        (a_mv_that_fails / "mv").chmod(0o755)
        not_renamed = subprocess.run(
            [shell, "-c", program.write_record_command(
                str(root), "ned-box", "a-head.txt", "the-later-run",
                len(later.encode("utf-8")))],
            env={**os.environ,
                 "PATH": f"{a_mv_that_fails}{os.pathsep}{os.environ.get('PATH', '')}"},
            input=later.encode("utf-8"), capture_output=True, check=False)
        check(f"under {shell}, a whole record handed over and the rename failing: exit 1, "
              f"the earlier whole record left byte for byte, and the file the command wrote "
              f"to removed",
              not_renamed.returncode == 1 and record.is_file()
              and record.read_bytes() == earlier.encode("utf-8")
              and files_left() == ["a-head.txt"],
              f"{not_renamed.returncode} {not_renamed.stderr!r} {files_left()}")
        with open(record, "rb") as reader_of_the_earlier_record:
            replaced = write(later, later, "the-later-run")
            read_after_the_write = reader_of_the_earlier_record.read()
        check(f"under {shell} a later whole record replaces the earlier one by a rename: a "
              f"reader that opened the earlier record before the write still reads the "
              f"earlier record whole, and the record's path holds the later record",
              replaced.returncode == 0 and read_after_the_write == earlier.encode("utf-8")
              and record.read_bytes() == later.encode("utf-8")
              and files_left() == ["a-head.txt"],
              f"{replaced.returncode} {replaced.stderr!r} {read_after_the_write!r}")

        # The form the remedy is printed in, which first reads the started
        # moment of the record it finds.
        record_there = ("pull-request-head-test-run: ned-box, started 2026-10-01T03:30:00Z\n"
                        "the record there\n")
        of_the_remedy = ("pull-request-head-test-run: ned-box, started 2026-10-01T03:30:01Z\n"
                         "the whole record the remedy is handed\n")
        of_a_later_run = ("pull-request-head-test-run: ned-box, started 2026-10-01T03:30:02Z\n"
                          "a later run's whole record\n")

        def remedy_command(started):
            return program.write_record_command(
                str(root), "ned-box", "a-head.txt", "the-run-of-the-remedy",
                len(of_the_remedy.encode("utf-8")),
                unless_the_record_there_started_no_earlier_than=started)

        def remedy(started, there):
            record.write_bytes(there.encode("utf-8"))
            return subprocess.run([shell, "-c", remedy_command(started)],
                                  input=of_the_remedy.encode("utf-8"),
                                  capture_output=True, check=False)

        for which, started in (("the same second", "2026-10-01T03:30:00Z"),
                               ("a second later", "2026-10-01T03:29:59Z")):
            refused = remedy(started, record_there)
            check(f"under {shell} the remedy of a run started at {started}, when the record "
                  f"there is of a run started {which}, at 2026-10-01T03:30:00Z: exit 1, "
                  f"the record there left byte for byte, no other file, and stderr to "
                  f"leave the record as it is",
                  refused.returncode == 1
                  and record.read_bytes() == record_there.encode("utf-8")
                  and files_left() == ["a-head.txt"]
                  and refused.stderr.decode("utf-8") == "pull-request-head-test-run: not "
                  "written: the record there is of a run that started in the same second "
                  "or later.\nLeave that record as it is.\n",
                  f"{refused.returncode} {refused.stderr!r} {files_left()}")
        for which, there in (
                ("of a run started a second earlier, at 2026-10-01T03:30:00Z", record_there),
                ("an empty file", ""),
                ("a file whose first line gives no started moment",
                 "a first line with no moment\n")):
            written = remedy("2026-10-01T03:30:01Z", there)
            check(f"under {shell} the remedy of a run started at 2026-10-01T03:30:01Z, when "
                  f"the record there is {which}: exit 0, the record replaced by the "
                  f"remedy's whole record, and no other file",
                  written.returncode == 0
                  and record.read_bytes() == of_the_remedy.encode("utf-8")
                  and files_left() == ["a-head.txt"],
                  f"{written.returncode} {written.stderr!r} {files_left()}")
        already_written = ("pull-request-head-test-run: already written: the record there "
                           "is the whole record of this run, byte for byte.\n"
                           "Tell the user the record is written.\n")
        record.unlink()
        written_by_the_run = write(of_the_remedy, of_the_remedy, "the-run-of-the-remedy")
        the_remedy_after_it = subprocess.run(
            [shell, "-c", remedy_command("2026-10-01T03:30:01Z")],
            input=of_the_remedy.encode("utf-8"), capture_output=True, check=False)
        check(f"under {shell} the remedy of a run whose own write had put its whole record "
              f"in place: exit 0, the record there left byte for byte, no other file, "
              f"nothing on stderr, and stdout that the record is written",
              written_by_the_run.returncode == 0 and the_remedy_after_it.returncode == 0
              and record.read_bytes() == of_the_remedy.encode("utf-8")
              and files_left() == ["a-head.txt"]
              and the_remedy_after_it.stderr == b""
              and the_remedy_after_it.stdout.decode("utf-8") == already_written,
              f"{the_remedy_after_it.returncode} {the_remedy_after_it.stdout!r} "
              f"{the_remedy_after_it.stderr!r} {files_left()}")
        the_remedy_once = remedy("2026-10-01T03:30:01Z", record_there)
        the_remedy_again = subprocess.run(
            [shell, "-c", remedy_command("2026-10-01T03:30:01Z")],
            input=of_the_remedy.encode("utf-8"), capture_output=True, check=False)
        check(f"under {shell} the remedy run a second time, after its first run replaced an "
              f"earlier run's record: exit 0, the record there left byte for byte, no other "
              f"file, nothing on stderr, and stdout that the record is written",
              the_remedy_once.returncode == 0 and the_remedy_once.stdout == b""
              and the_remedy_again.returncode == 0
              and record.read_bytes() == of_the_remedy.encode("utf-8")
              and files_left() == ["a-head.txt"]
              and the_remedy_again.stderr == b""
              and the_remedy_again.stdout.decode("utf-8") == already_written,
              f"{the_remedy_again.returncode} {the_remedy_again.stdout!r} "
              f"{the_remedy_again.stderr!r} {files_left()}")
        for handed_over_name, handed_over in (("half its record", of_the_remedy[:20]),
                                              ("nothing", "")):
            record.write_bytes(record_there.encode("utf-8"))
            cut_short = run_with_no_reader_on_stderr(
                remedy_command("2026-10-01T03:30:01Z"), handed_over)
            check(f"under {shell} the remedy of a run started at 2026-10-01T03:30:01Z, handed "
                  f"{handed_over_name} with no reader on stderr, when the record there is of "
                  f"a run started a second earlier: not exit 0, the record there left byte "
                  f"for byte, and the file the command wrote to removed",
                  cut_short.returncode != 0
                  and record.read_bytes() == record_there.encode("utf-8")
                  and files_left() == ["a-head.txt"],
                  f"{cut_short.returncode} {files_left()}")
        record.write_bytes(record_there.encode("utf-8"))
        refused = run_with_no_reader_on_stderr(
            remedy_command("2026-10-01T03:30:00Z"), of_the_remedy)
        check(f"under {shell} the remedy of a run started in the same second as the record "
              f"there, handed its whole record with no reader on stderr: not exit 0, the "
              f"record there left byte for byte, and the file the command wrote to removed",
              refused.returncode != 0
              and record.read_bytes() == record_there.encode("utf-8")
              and files_left() == ["a-head.txt"],
              f"{refused.returncode} {files_left()}")
        record.write_bytes(of_the_remedy.encode("utf-8"))
        told_nobody = run_with_no_reader_on(
            "stdout", remedy_command("2026-10-01T03:30:01Z"), of_the_remedy)
        check(f"under {shell} the remedy of a run whose whole record is in place, with no "
              f"reader on stdout: not exit 0, the record there left byte for byte, and the "
              f"file the command wrote to removed before the command says anything",
              told_nobody.returncode != 0
              and record.read_bytes() == of_the_remedy.encode("utf-8")
              and files_left() == ["a-head.txt"],
              f"{told_nobody.returncode} {files_left()}")
        record.write_bytes(b"")
        fed_nothing = subprocess.run(
            [shell, "-c", remedy_command("2026-10-01T03:30:01Z")], input=b"",
            capture_output=True, check=False)
        check(f"under {shell} the remedy handed nothing, when an empty file is at the "
              f"record's path: exit 1 on the count, the empty file left, no other file, "
              f"nothing on stdout, and stderr what arrived and what to do: the count is "
              f"taken before the record there is looked at, so two empty files are not read "
              f"as the record already written",
              fed_nothing.returncode == 1 and record.read_bytes() == b""
              and files_left() == ["a-head.txt"] and fed_nothing.stdout == b""
              and fed_nothing.stderr.decode("utf-8") == "pull-request-head-test-run: not "
              f"written: {len(of_the_remedy.encode('utf-8'))} bytes of the record were sent "
              "and another count arrived.\nRun this command again.\n",
              f"{fed_nothing.returncode} {fed_nothing.stdout!r} {fed_nothing.stderr!r} "
              f"{files_left()}")
        record.write_bytes(of_a_later_run.encode("utf-8"))
        cut_short_beside_a_later_record = subprocess.run(
            [shell, "-c", remedy_command("2026-10-01T03:30:01Z")],
            input=of_the_remedy[:20].encode("utf-8"), capture_output=True, check=False)
        check(f"under {shell} the remedy handed half its record, when the record there is "
              f"of a later run: exit 1, the record there left byte for byte, no other file, "
              f"and stderr what arrived and what to do, not to leave the record there: the "
              f"count is taken before the record there is looked at",
              cut_short_beside_a_later_record.returncode == 1
              and record.read_bytes() == of_a_later_run.encode("utf-8")
              and files_left() == ["a-head.txt"]
              and cut_short_beside_a_later_record.stdout == b""
              and cut_short_beside_a_later_record.stderr.decode("utf-8")
              == "pull-request-head-test-run: not "
              f"written: {len(of_the_remedy.encode('utf-8'))} bytes of the record were sent "
              "and another count arrived.\nRun this command again.\n",
              f"{cut_short_beside_a_later_record.returncode} "
              f"{cut_short_beside_a_later_record.stderr!r} {files_left()}")
        # Two copies of one remedy at once: the other copy puts the run's
        # record in place after this copy has taken its record and before it
        # reads the record there. The other copy's rename is played by a `sed`
        # first on PATH that puts the record in place and then runs the real
        # `sed`: the command's first look at the record there is its `sed`.
        record.write_bytes(record_there.encode("utf-8"))
        the_other_copy_renames = workspace / f"a-sed-under-{Path(shell).name}"
        the_other_copy_renames.mkdir()
        record_of_the_other_copy = the_other_copy_renames / "the-record-of-the-run"
        record_of_the_other_copy.write_bytes(of_the_remedy.encode("utf-8"))
        (the_other_copy_renames / "sed").write_text(
            "#!/bin/sh\n"
            f"cp {shlex.quote(str(record_of_the_other_copy))} {shlex.quote(str(record))}\n"
            f"exec {shlex.quote(shutil.which('sed'))} \"$@\"\n", encoding="utf-8")
        (the_other_copy_renames / "sed").chmod(0o755)
        beside_the_other_copy = subprocess.run(
            [shell, "-c", remedy_command("2026-10-01T03:30:01Z")],
            env={**os.environ, "PATH": f"{the_other_copy_renames}{os.pathsep}"
                                       f"{os.environ.get('PATH', '')}"},
            input=of_the_remedy.encode("utf-8"), capture_output=True, check=False)
        check(f"under {shell} the remedy, when another copy of it puts the run's whole "
              f"record in place after this copy has taken its record and before this copy "
              f"reads the record there: exit 0, the record there left byte for byte, no "
              f"other file, nothing on stderr, and stdout that the record is written",
              beside_the_other_copy.returncode == 0
              and record.read_bytes() == of_the_remedy.encode("utf-8")
              and files_left() == ["a-head.txt"]
              and beside_the_other_copy.stderr == b""
              and beside_the_other_copy.stdout.decode("utf-8") == already_written,
              f"{beside_the_other_copy.returncode} {beside_the_other_copy.stdout!r} "
              f"{beside_the_other_copy.stderr!r} {files_left()}")
        record.unlink()
        with_no_record_there = subprocess.run(
            [shell, "-c", remedy_command("2026-10-01T03:30:01Z")],
            input=of_the_remedy.encode("utf-8"), capture_output=True, check=False)
        check(f"under {shell} the remedy when no record is there: exit 0, the remedy's whole "
              f"record written, no other file, and nothing on stdout or stderr",
              with_no_record_there.returncode == 0 and record.is_file()
              and record.read_bytes() == of_the_remedy.encode("utf-8")
              and files_left() == ["a-head.txt"]
              and with_no_record_there.stdout == b"" and with_no_record_there.stderr == b"",
              f"{with_no_record_there.returncode} {with_no_record_there.stdout!r} "
              f"{with_no_record_there.stderr!r} {files_left()}")

        # What a writer killed part way left. The root's name needs quoting.
        quoted_root = workspace / f"a root with a space and a ' quote under {Path(shell).name}"
        quoted_record = quoted_root / "pull-request-head-test-runs" / "ned-box" / "a-head.txt"
        quoted_record.parent.mkdir(parents=True)

        def files_left_under_the_quoted_root():
            return sorted(os.listdir(quoted_record.parent))

        def remedy_under_the_quoted_root(handed_over):
            return subprocess.run(
                [shell, "-c", program.write_record_command(
                    str(quoted_root), "ned-box", "a-head.txt", "the-run-of-the-remedy",
                    len(of_the_remedy.encode("utf-8")),
                    unless_the_record_there_started_no_earlier_than="2026-10-01T03:30:01Z")],
                input=handed_over.encode("utf-8"), capture_output=True, check=False)

        left_by_a_writer_that_no_longer_runs = quoted_record.with_name(
            f".a-head.txt.the-run-of-the-remedy.{A_PROCESS_NUMBER_NO_PROCESS_HAS}.partial")
        of_a_writer_that_still_runs = quoted_record.with_name(
            f".a-head.txt.the-run-of-the-remedy.{os.getpid()}.partial")
        left_by_a_writer_of_another_run = quoted_record.with_name(
            f".a-head.txt.another-run.{A_PROCESS_NUMBER_NO_PROCESS_HAS}.partial")
        for left in (left_by_a_writer_that_no_longer_runs, of_a_writer_that_still_runs,
                     left_by_a_writer_of_another_run):
            left.write_bytes(b"part of a record\n")
        quoted_record.write_bytes(record_there.encode("utf-8"))
        swept = remedy_under_the_quoted_root(of_the_remedy)
        check(f"under {shell}, in a log-store whose root's name holds a space and a single "
              f"quote, the remedy removes the file a writer of its run left whose shell no "
              f"longer runs, leaves the file of a writer of its run whose process still runs "
              f"and the file a writer of another run left, and writes its whole record: "
              f"exit 0",
              swept.returncode == 0 and swept.stderr == b""
              and quoted_record.read_bytes() == of_the_remedy.encode("utf-8")
              and files_left_under_the_quoted_root() == sorted(
                  [left_by_a_writer_of_another_run.name, of_a_writer_that_still_runs.name,
                   "a-head.txt"])
              and of_a_writer_that_still_runs.read_bytes() == b"part of a record\n"
              and left_by_a_writer_of_another_run.read_bytes() == b"part of a record\n",
              f"{swept.returncode} {swept.stderr!r} {files_left_under_the_quoted_root()}")
        # Gone already where the command removed more than its own run's dead
        # writers' files: the case above has said so.
        of_a_writer_that_still_runs.unlink(missing_ok=True)
        left_by_a_writer_of_another_run.unlink(missing_ok=True)
        left_by_a_writer_that_no_longer_runs.write_bytes(b"part of a record\n")
        quoted_record.write_bytes(record_there.encode("utf-8"))
        cut_short = remedy_under_the_quoted_root(of_the_remedy[:20])
        check(f"under {shell}, in that log-store, the remedy handed half its record: exit 1, "
              f"the record there left byte for byte, and no other file left: neither the "
              f"file the command wrote to nor the file a writer that no longer runs left",
              cut_short.returncode == 1
              and quoted_record.read_bytes() == record_there.encode("utf-8")
              and files_left_under_the_quoted_root() == ["a-head.txt"]
              and cut_short.stderr.decode("utf-8") == "pull-request-head-test-run: not "
              f"written: {len(of_the_remedy.encode('utf-8'))} bytes of the record were sent "
              "and another count arrived.\nRun this command again.\n",
              f"{cut_short.returncode} {cut_short.stderr!r} "
              f"{files_left_under_the_quoted_root()}")


def run_cases_of_what_the_write_command_holds():
    for form, started in (("the program runs", None),
                          ("the remedy is printed in", "2026-10-01T03:30:00Z")):
        command = program.write_record_command(
            "/a/log-store/root", "ned-box", "a-head.txt", "a-run", 2354, started)
        check(f"the command that writes the record, in the form {form}, holds ASCII "
              f"characters alone when the paths it is given do: the program hands it to a "
              f"process as an argument, and a filesystem encoding with no such character "
              f"would stop the run",
              command.isascii(),
              repr(sorted({character for character in command if not character.isascii()})))


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
    count_in_a_command = re.compile(r" -eq (\d+) \]")
    check("told that the preferred encoding is UTF-16, the program gives the command it "
          "runs the count of the record's UTF-16 bytes, the bytes it would send, and the "
          "remedy it prints the count of the local copy's UTF-8 bytes",
          result.code == 5 and local_copy != "" and as_utf_16 != as_utf_8
          and len(result.ssh_calls) == 1
          and count_in_a_command.findall(result.ssh_calls[0]) == [str(as_utf_16)]
          and count_in_a_command.findall(remedy_as_printed) == [str(as_utf_8)]
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
          and fixture.record("mac") == local_copy
          and fixture.record_files() == [record_path],
          f"{written_by_hand.returncode} {written_by_hand.stderr}")


def wait_for_another_process_until(condition) -> bool:
    """Whether the condition came true within 10 seconds, asked 20 times a
    second."""
    for _ in range(200):
        if condition():
            return True
        time.sleep(0.05)
    return condition()


def run_cases_of_two_writers_at_once(workspace: Path):
    """The command that writes the record, run twice at once on one record:
    the first writer is held half way through its record while the second
    writes all of its own."""
    root = workspace / "two-writers-at-once"
    first = program.write_record_command(
        str(root), "ned-box", "a-head.txt", "the-first-run",
        len("the first writer's first half\nthe first writer's second half\n"))
    second = program.write_record_command(
        str(root), "ned-box", "a-head.txt", "the-second-run",
        len("the second writer's whole record\n"))
    record = root / "pull-request-head-test-runs" / "ned-box" / "a-head.txt"
    writer = subprocess.Popen(["/bin/sh", "-c", first], stdin=subprocess.PIPE, text=True,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # The shell that runs the command is the process started here.
    partial_of_the_first = record.with_name(f".a-head.txt.the-first-run.{writer.pid}.partial")
    try:
        writer.stdin.write("the first writer's first half\n")
        writer.stdin.flush()
        half_is_written = wait_for_another_process_until(
            lambda: partial_of_the_first.is_file() and partial_of_the_first.read_text(
                encoding="utf-8") == "the first writer's first half\n")
        record_exists_at_the_half = record.exists()
        other = subprocess.run(["/bin/sh", "-c", second], capture_output=True, text=True,
                               input="the second writer's whole record\n", check=False)
        record_after_the_second = (record.read_text(encoding="utf-8") if record.is_file()
                                   else None)
        writer.stdin.write("the first writer's second half\n")
        writer.stdin.close()
        code_of_the_first = writer.wait(timeout=20)
    finally:
        if writer.poll() is None:
            writer.kill()
            writer.wait()
    check("a record half written is not at the record's path: the writer holds it in the "
          "record's directory, under a name of its own that carries the run's name and the "
          "process number of the shell that runs the command",
          half_is_written and not record_exists_at_the_half,
          f"{half_is_written} {record_exists_at_the_half}")
    check("a second writer that writes its whole record while the first is half way leaves "
          "its own whole record",
          other.returncode == 0
          and record_after_the_second == "the second writer's whole record\n",
          f"{other.returncode} {other.stderr} {record_after_the_second!r}")
    files_left = sorted(os.listdir(record.parent)) if record.parent.is_dir() else None
    check("the first writer, finishing last, leaves its own whole record and no other file",
          code_of_the_first == 0 and record.is_file()
          and record.read_text(encoding="utf-8")
          == "the first writer's first half\nthe first writer's second half\n"
          and files_left == ["a-head.txt"], f"{code_of_the_first} {files_left}")


def run_cases_of_two_writers_of_one_run(workspace: Path):
    """One run can have two writers at once: its own write command still
    running on the far side after the client died, or a copy of its remedy,
    and its remedy started meanwhile. The first writer is fed half the run's
    record and held; the remedy is started and held before it is fed
    anything; the first writer is then fed the rest, and the remedy the whole
    record once the first writer has ended. No step waits on a clock for its
    outcome: each waits for a file to say the step before it has happened.
    The log-store root's name holds spaces and a single quote, so every part
    of the command is run on paths that need quoting."""
    started = "2026-10-01T03:30:01Z"
    record_of_the_run = (
        f"pull-request-head-test-run: ned-box, started {started}\n"
        + "".join(f"line {number} of the run's own record\n" for number in range(2, 40)))
    first_half = record_of_the_run[:len(record_of_the_run) // 2]
    the_rest = record_of_the_run[len(first_half):]
    of_an_earlier_run = ("pull-request-head-test-run: ned-box, started 2026-10-01T03:30:00Z\n"
                         "an earlier run's whole record\n")
    of_a_later_run = ("pull-request-head-test-run: ned-box, started 2026-10-01T03:30:02Z\n"
                      "a later run's whole record\n")
    already_written = ("pull-request-head-test-run: already written: the record there is "
                       "the whole record of this run, byte for byte.\n"
                       "Tell the user the record is written.\n")
    not_written = ("pull-request-head-test-run: not written: the record there is of a run "
                   "that started in the same second or later.\nLeave that record as it is.\n")
    count = 0
    for shell in ("/bin/sh", "/bin/bash", "/bin/dash"):
        if not Path(shell).is_file():
            print(f"SKIP  two writers of one run under {shell}: this machine has no {shell}")
            continue
        for state, there_before in (("no record there", None),
                                    ("an earlier run's record there", of_an_earlier_run),
                                    ("a later run's record there", of_a_later_run)):
            for first_writer, the_first_is_the_remedy in (
                    ("the run's own write command", False),
                    ("a copy of the run's remedy", True)):
                count += 1
                root = workspace / f"two writers of one run's record, {count}"
                record = root / "pull-request-head-test-runs" / "ned-box" / "a-head.txt"
                record.parent.mkdir(parents=True)
                if there_before is not None:
                    record.write_bytes(there_before.encode("utf-8"))
                write_command = program.write_record_command(
                    str(root), "ned-box", "a-head.txt", "the-run",
                    len(record_of_the_run.encode("utf-8")))
                remedy_command = program.write_record_command(
                    str(root), "ned-box", "a-head.txt", "the-run",
                    len(record_of_the_run.encode("utf-8")),
                    unless_the_record_there_started_no_earlier_than=started)

                def files_being_written():
                    return sorted(name for name in os.listdir(record.parent)
                                  if name.endswith(".partial"))

                def one_holds(content: bytes) -> bool:
                    return any((record.parent / name).read_bytes() == content
                               for name in files_being_written())

                first = subprocess.Popen(
                    [shell, "-c", remedy_command if the_first_is_the_remedy
                     else write_command],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                remedy = None
                try:
                    first.stdin.write(first_half.encode("utf-8"))
                    first.stdin.flush()
                    the_first_is_half_way = wait_for_another_process_until(
                        lambda: one_holds(first_half.encode("utf-8")))
                    remedy = subprocess.Popen(
                        [shell, "-c", remedy_command], stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    # The remedy has started once the file it writes to is
                    # there and empty.
                    the_remedy_has_started = wait_for_another_process_until(
                        lambda: one_holds(b""))
                    while_both_are_held = files_being_written()
                    first.stdin.write(the_rest.encode("utf-8"))
                    first.stdin.close()
                    code_of_the_first = first.wait(timeout=20)
                    after_the_first = record.read_bytes() if record.is_file() else None
                    stdout_of_the_remedy, stderr_of_the_remedy = remedy.communicate(
                        record_of_the_run.encode("utf-8"), timeout=20)
                    after_the_remedy = record.read_bytes() if record.is_file() else None
                finally:
                    for process in (first, remedy):
                        if process is not None and process.poll() is None:
                            process.kill()
                            process.wait()
                    for stream in (first.stdout, first.stderr):
                        stream.close()
                files_left = sorted(os.listdir(record.parent))
                each_wrote_to_a_file_of_its_own = (
                    the_first_is_half_way and the_remedy_has_started
                    and while_both_are_held == sorted(
                        f".a-head.txt.the-run.{process.pid}.partial"
                        for process in (first, remedy)))
                detail = (f"{the_first_is_half_way} {the_remedy_has_started} "
                          f"{while_both_are_held} {code_of_the_first} "
                          f"{(after_the_first or b'').count(bytes(1))} NUL bytes of "
                          f"{len(after_the_first or b'')} {remedy.returncode} "
                          f"{stdout_of_the_remedy!r} {stderr_of_the_remedy!r} {files_left}")
                if the_first_is_the_remedy and there_before is of_a_later_run:
                    check(f"under {shell}, {state}: {first_writer} is held half way through "
                          f"the run's record when the run's remedy starts, and each writes "
                          f"to a file of its own in the record's directory; the first, fed "
                          f"the rest, is refused and leaves the later run's record byte for "
                          f"byte; the remedy, fed its record after that, is refused too; no "
                          f"other file is left",
                          each_wrote_to_a_file_of_its_own and code_of_the_first == 1
                          and after_the_first == there_before.encode("utf-8")
                          and remedy.returncode == 1 and stdout_of_the_remedy == b""
                          and stderr_of_the_remedy.decode("utf-8") == not_written
                          and after_the_remedy == there_before.encode("utf-8")
                          and files_left == ["a-head.txt"], detail)
                else:
                    check(f"under {shell}, {state}: {first_writer} is held half way through "
                          f"the run's record when the run's remedy starts, and each writes "
                          f"to a file of its own in the record's directory; the first, fed "
                          f"the rest, exits 0 and leaves the run's whole record, with no "
                          f"part of it emptied; the remedy, fed its record after that, says "
                          f"the record is written and exits 0; no other file is left",
                          each_wrote_to_a_file_of_its_own and code_of_the_first == 0
                          and after_the_first == record_of_the_run.encode("utf-8")
                          and remedy.returncode == 0 and stderr_of_the_remedy == b""
                          and stdout_of_the_remedy.decode("utf-8") == already_written
                          and after_the_remedy == record_of_the_run.encode("utf-8")
                          and files_left == ["a-head.txt"], detail)


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
    run_cases_on_the_mac(workspace_root)
    run_cases_of_a_record_cut_short_on_the_way(workspace_root)
    run_cases_of_the_write_command_under_each_shell(workspace_root)
    run_cases_of_what_the_write_command_holds()
    run_cases_of_the_two_byte_counts(workspace_root)
    run_cases_of_two_writers_at_once(workspace_root)
    run_cases_of_two_writers_of_one_run(workspace_root)
    run_cases_as_a_program(workspace_root)
    run_log_store_readme_cases()

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
