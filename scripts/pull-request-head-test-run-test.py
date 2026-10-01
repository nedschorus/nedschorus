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
started.

Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
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
THE_MOMENT_IN_A_DIRECTORY_NAME = "20261001T033000Z"

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
# itself with.
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
log_dir.mkdir(parents=True, exist_ok=True)
(log_dir / ("log-of-call-%d.log" % len(calls))).write_text("a suite's output\n")
print("run-all-test-suites: %s at %s (tracked files match that commit); 3 suites listed by "
      "git; 2 selected by inputs changed since %s; Python 3.14.4 (%s); -j 4; logs in %s"
      % (checkout, commit, since[:12], sys.executable, log_dir))
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

    def run_directory(self, head=None) -> Path:
        """The directory a run made at THE_MOMENT by this process keeps its
        logs and the record's local copy in."""
        return (self.temporary / program.PULL_REQUEST_HEAD_TEST_RUN_DIRECTORY_NAME
                / f"{head or self.head}-{THE_MOMENT_IN_A_DIRECTORY_NAME}-{os.getpid()}")

    def logs(self, head=None) -> Path:
        return self.run_directory(head) / program.PULL_REQUEST_HEAD_TEST_RUN_LOGS_DIRECTORY_NAME

    def local_copy(self, head=None) -> Path:
        return (self.run_directory(head)
                / program.PULL_REQUEST_HEAD_TEST_RUN_RECORD_LOCAL_COPY_FILE_NAME)

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

        saved_bound = daily.DAILY_FULL_TEST_RUN_LOCK_WAIT_BOUND_SECONDS
        if lock_wait_bound_seconds is not None:
            daily.DAILY_FULL_TEST_RUN_LOCK_WAIT_BOUND_SECONDS = lock_wait_bound_seconds
        saved_gethostname = socket.gethostname
        socket.gethostname = lambda: hostname
        original_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{fake_ssh}{os.pathsep}{original_path}"
        os.environ[STAND_IN_RUNNER_BEHAVIOUR_FILE_VARIABLE] = str(behaviour_file)
        stdout, stderr = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = program.main(
                    [*self.arguments(checkout, runner_program), *extra_arguments],
                    now=THE_MOMENT, wait=wait, monotonic=lambda: clock[0])
        finally:
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
    fixture_git(fixture.checkout, "checkout", "-q", "--", "a-change.txt")
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

    def runner_that_is_not_started(command, run_from, wait, monotonic):
        commands_run.append((command, run_from))
        return (subprocess.CompletedProcess(command, 0, stdout=PASSING_SUMMARY_LINE + "\n",
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
              "-o BatchMode=yes -o ConnectTimeout=10 nedlern@ned-box mkdir -p "
              f"{fixture.log_store}/pull-request-head-test-runs/mac && cat > "
              f"{fixture.log_store}/{record_path}"], f"{result!r}\n{record!r}")
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
              f"'mkdir -p {unreachable.log_store}/pull-request-head-test-runs/mac && cat > "
              f"{target}' < {unreachable.local_copy()}")
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
    run_cases_as_a_program(workspace_root)
    run_log_store_readme_cases()

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
