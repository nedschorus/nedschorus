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
the moment, the wait and the clock are passed in, so no case sleeps. The one
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
# and `git_commands_run_in_the_checkout`.
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
print("run-all-test-suites: %s at %s (%s); 3 suites listed by "
      "git; 2 selected by inputs changed since %s; Python 3.14.4 (%s); -j 4; logs in %s"
      % (checkout, commit, state, since[:12], sys.executable, log_dir))
print("inputs recorded by python-audit-hook, kept in /a/recordings/directory")
for line in behaviour["lines"]:
    print(line)
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

    def write_command(self, machine: str, moment=THE_MOMENT, keeps_a_later_record=False):
        """The shell command a run of the head made at the moment by this
        process writes its record with; with keeps_a_later_record, the form
        its remedy is printed in. No path of a fixture needs quoting."""
        directory = f"{self.log_store}/pull-request-head-test-runs/{machine}"
        record = f"{directory}/{self.head}.txt"
        partial = (f"{directory}/.{self.head}.txt.{moment:%Y%m%dT%H%M%SZ}-{os.getpid()}"
                   f".partial")
        keeps = ""
        if keeps_a_later_record:
            keeps = (f"if [ -e {record} ] && [ \"$(sed -n '1s/^.*, started //p' {record})\" "
                     f"\\> {moment:%Y-%m-%dT%H:%M:%SZ} ]; then echo "
                     f"'pull-request-head-test-run: not written — the record there is of a "
                     f"run that started later.' >&2; echo 'Leave that record as it is.' "
                     f">&2; exit 1; fi && ")
        return (f"mkdir -p {directory} && {keeps}cat > {partial} && mv -f {partial} {record} "
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
            started_in=None) -> RunResult:
        """main's exit code and output, with the fake ssh's calls, the stand-in
        runner's calls and the waits main asked for. The clock is the sum of
        those waits, so a case takes no time. during_each_wait is called in
        each wait, to change the checkout while the program waits for the
        lock; runner_changes_the_checkout is what the stand-in runner does to
        the checkout once it is past the lock. A run that waits more often
        than any case asks for is stopped, and its exit code is
        WAITED_MORE_OFTEN_THAN_ANY_CASE_ASKS_FOR."""
        scratch = self.scratch_for_next_run()
        behaviour_file = scratch / "stand-in-runner-behaviour.json"
        calls_file = scratch / "stand-in-runner-calls.json"
        behaviour_file.write_text(json.dumps(
            {"exits": list(exits), "lines": list(lines), "calls_file": str(calls_file),
             **(runner_changes_the_checkout or {})}),
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
          ]) + "\n", repr(record))
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
                      for line in record_lines), repr(record_lines))
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
          and "run-all-test-suites was killed by SIGKILL" in record_lines,
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
              + fixture.write_command("mac")], f"{result!r}\n{record!r}")
    check("the command that writes the record writes under a name of the run's own in the "
          "record's directory and renames that file over the record, and leaves no other "
          "file",
          f"cat > {fixture.log_store}/pull-request-head-test-runs/mac/.{fixture.head}.txt."
          f"{THE_MOMENT:%Y%m%dT%H%M%SZ}-{os.getpid()}.partial && mv -f "
          in fixture.write_command("mac")
          and f"cat > {fixture.log_store}/{record_path}" not in fixture.write_command("mac")
          and fixture.record_files() == [record_path], fixture.write_command("mac"))
    check("the Mac's record names the mac, in its first line and beside the logs",
          record is not None and record.startswith(
              "pull-request-head-test-run: mac, started 2026-10-01T03:30:00Z\n")
          and record.endswith(f"logs: {fixture.logs()} on mac\n"), repr(record))
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
    remedy = ("ssh -o BatchMode=yes -o ConnectTimeout=10 nedlern@ned-box "
              + shlex.quote(unreachable.write_command("mac", keeps_a_later_record=True))
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
    local_copy = (unreachable.local_copy().read_text(encoding="utf-8")
                  if unreachable.local_copy().is_file() else None)
    check("the record that could not be written is kept beside the logs",
          local_copy is not None and PASSING_SUMMARY_LINE in local_copy.splitlines(),
          repr(local_copy))
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
          and written_by_hand.stderr == "pull-request-head-test-run: not written — the "
          "record there is of a run that started later.\nLeave that record as it is.\n",
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
    first = program.write_record_command(str(root), "ned-box", "a-head.txt", "the-first-run")
    second = program.write_record_command(str(root), "ned-box", "a-head.txt",
                                          "the-second-run")
    record = root / "pull-request-head-test-runs" / "ned-box" / "a-head.txt"
    partial_of_the_first = record.with_name(".a-head.txt.the-first-run.partial")
    writer = subprocess.Popen(["/bin/sh", "-c", first], stdin=subprocess.PIPE, text=True,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    check("a record half written is not at the record's path: the writer holds it under a "
          "name of its own in the record's directory",
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
    run_cases_of_two_writers_at_once(workspace_root)
    run_cases_as_a_program(workspace_root)
    run_log_store_readme_cases()

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
