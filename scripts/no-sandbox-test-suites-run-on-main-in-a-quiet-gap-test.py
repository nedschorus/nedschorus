#!/usr/bin/env python3
"""Tests for scripts/no-sandbox-test-suites-run-on-main-in-a-quiet-gap.py.

Each case runs the program's main() in this process against a scratch origin
repository and its clone, with a stand-in runner, given by
--test-suite-runner-program, that records its arguments and prints and exits
as the case asks. The scratch origin holds its own scripts/run-all-test-suites.py
naming two no-sandbox suites, which the program reads from the worktree it makes.
No case runs a real suite, writes the real state file or the real log-store.

Run: python3 scripts/no-sandbox-test-suites-run-on-main-in-a-quiet-gap-test.py
(exit 0 = all passed)
"""

import contextlib
import fcntl
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Before anything runs git: a run started with GIT_DIR set must still build this suite's
# scratch repositories where the suite says.
_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name("git-redirecting-environment-removal-test-fixture.py"))
_fixture = importlib.util.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(_fixture)
_fixture.remove_git_redirecting_environment_variables_from_this_process()

PROGRAM_PATH = Path(__file__).resolve().with_name("no-sandbox-test-suites-run-on-main-in-a-quiet-gap.py")
spec = importlib.util.spec_from_file_location("quiet_gap", PROGRAM_PATH)
program = importlib.util.module_from_spec(spec)
spec.loader.exec_module(program)
runner = program.runner_module()

failures = []


def check(name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {name}")
    if not condition:
        failures.append(name)
        if detail:
            print(f"      {detail!r}"[:1500])


GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false",
       "-c", "core.hooksPath=/dev/null"]

STAND_IN_RUNNER = '''import json, os, sys, time
with open(os.environ["QUIET_GAP_TEST_CALLS"], "a") as calls:
    calls.write(json.dumps(sys.argv[1:]) + "\\n")
with open(os.environ["QUIET_GAP_TEST_CALLS"] + ".xdg", "w") as seen:
    seen.write(os.environ.get("XDG_RUNTIME_DIR", "unset"))
log_dir = sys.argv[sys.argv.index("--log-dir") + 1]
os.makedirs(log_dir, exist_ok=True)
mode = os.environ.get("QUIET_GAP_TEST_RUNNER", "pass")
if mode == "sleep":
    time.sleep(60)
if mode == "ignore-sigterm-then-sleep":
    import signal
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    print("started", flush=True)
    time.sleep(60)
if mode == "fail-with-missing-log":
    print("FAIL outside-a-test.py exit 1 — log /no/such/log.txt")
    print("SUMMARY: 1 passed, 1 failed, 2 total")
    sys.exit(1)
if mode == "fail-before-closing-list":
    print("FAIL outside-a-test.py exit 1 (1.0s)")
    sys.exit(1)
if mode == "fail":
    log = os.path.join(log_dir, "outside-a-test.py.log")
    with open(log, "w") as written:
        written.write("the suite's own output\\n")
    # The runner's real output: a progress line without a log, then the closing list's line.
    print("FAIL outside-a-test.py exit 1 (1.0s)")
    print(f"FAIL outside-a-test.py exit 1 — log {log}")
    print("SUMMARY: 1 passed, 1 failed, 2 total")
    sys.exit(1)
if mode == "refuse":
    print("run-all-test-suites: not run — a refusal for the test", file=sys.stderr)
    sys.exit(2)
print("SUMMARY: 2 passed, 0 failed, 2 total")
'''

RUNNER_LISTS = ('SUITES_RUN_WITHOUT_ANY_SANDBOX = {"outside-a-test.py": "x", '
                '"outside-b-test.py": "y"}\n'
                "SUITES_GIVEN_A_COPY_ON_WRITE_OVERLAY_OF_THE_REPOSITORY_GIT_DIRECTORY = {}\n"
                "SUITES_WHOSE_TEST_SANDBOX_SHARES_THE_MACHINE_NETWORK = {}\n")


def git(directory, *arguments):
    return subprocess.run([*GIT, "-C", str(directory), *arguments], capture_output=True,
                          text=True, check=True).stdout.strip()


class Scratch:
    def __init__(self, root):
        self.root = root
        self.origin = root / "origin"
        self.origin.mkdir()
        git(self.origin, "init", "-q", "-b", "main")
        (self.origin / "scripts").mkdir()
        (self.origin / "scripts" / "run-all-test-suites.py").write_text(RUNNER_LISTS)
        for name in ("outside-a-test.py", "outside-b-test.py"):
            (self.origin / name).write_text("print('ok')\n")
        git(self.origin, "add", "-A")
        git(self.origin, "commit", "-q", "-m", "start")
        self.clone = root / "clone"
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.clone)], check=True)
        self.state_file = root / "state" / "quiet-gap.json"
        self.log_store = root / "log-store"
        self.temporary = root / "tmp"
        self.temporary.mkdir()
        self.runner_lock = root / "runner" / "run.lock"
        self.stand_in = root / "stand-in-runner.py"
        self.stand_in.write_text(STAND_IN_RUNNER)
        self.calls = root / "calls.jsonl"
        os.environ["QUIET_GAP_TEST_CALLS"] = str(self.calls)

    def commit_on_origin(self, message):
        (self.origin / "changes.txt").write_text(message + "\n")
        git(self.origin, "add", "-A")
        git(self.origin, "commit", "-q", "-m", message)
        return git(self.origin, "rev-parse", "HEAD")

    def merge_on_origin(self, number):
        git(self.origin, "checkout", "-q", "-b", f"topic-{number}")
        self.commit_on_origin(f"topic {number}")
        git(self.origin, "checkout", "-q", "main")
        git(self.origin, "merge", "-q", "--no-ff", "-m",
            f"Merge pull request #{number} from nedschorus/topic-{number}", f"topic-{number}")
        return git(self.origin, "rev-parse", "HEAD")

    def arguments(self, *extra):
        return ["--clone", str(self.clone), "--state-file", str(self.state_file),
                "--log-store-root", str(self.log_store),
                "--temporary-directory", str(self.temporary),
                "--runner-lock-file", str(self.runner_lock),
                "--test-suite-runner-program", str(self.stand_in), *extra]

    def run(self, mode="pass", *extra):
        os.environ["QUIET_GAP_TEST_RUNNER"] = mode
        self.calls.write_text("")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = program.main(self.arguments(*extra))
        calls = [json.loads(line) for line in self.calls.read_text().splitlines() if line]
        return code, out.getvalue() + err.getvalue(), calls

    def state(self):
        return json.loads(self.state_file.read_text())

    def notice(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            program.main(self.arguments("--print-merge-gate-notice-of-last-failed-or-stopped-run"))
        return out.getvalue()


@contextlib.contextmanager
def constants(**values):
    saved = {name: getattr(program, name) for name in values}
    for name, value in values.items():
        setattr(program, name, value)
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(program, name, value)


def held(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    return handle


with tempfile.TemporaryDirectory() as directory:
    s = Scratch(Path(directory))
    first_commit = git(s.origin, "rev-parse", "HEAD")

    # --- Its own lock, and the no-sandbox suites' lock ---------------------------
    own = held(Path(f"{s.state_file}.lock"))
    code, printed, calls = s.run()
    own.close()
    check("when another run holds the program's own lock, it exits 0 and runs nothing",
          code == 0 and calls == [] and not s.state_file.exists(), (code, printed))

    no_sandbox_lock = held(runner.test_suite_admission_directory_for_lock_file(s.runner_lock)
                           / runner.SUITES_RUN_WITHOUT_ANY_SANDBOX_LOCK_FILE_NAME)
    code, printed, calls = s.run()
    no_sandbox_lock.close()
    check("when a no-sandbox suite holds the suites' lock, ned-box is not quiet: exit 0, no run",
          code == 0 and calls == [] and "not quiet" in printed, (code, printed))

    # --- A first run that passes ------------------------------------------------
    code, printed, calls = s.run()
    state = s.state() if s.state_file.exists() else {}
    check("a first run runs the worktree's no-sandbox suites by name, with no selection, and "
          "a pass makes its commit the passing commit",
          code == 0 and len(calls) == 1
          and calls[0][calls[0].index("--only-suites-named") + 1:] == [
              "outside-a-test.py", "outside-b-test.py"]
          and "--only-suites-whose-recorded-inputs-changed-since" not in calls[0]
          and state.get("passing_commit") == first_commit
          and state["last_run"]["result"] == "passed", (code, printed, calls, state))
    records = sorted(s.log_store.glob("no-sandbox-test-suites-runs/*/*Z.txt"))
    check("the run writes its record in the log-store, naming the commit and the result",
          len(records) == 1 and first_commit in records[0].read_text()
          and "result: passed" in records[0].read_text(), records)
    check("the run removes its worktree", not (s.temporary / program.PROGRAM /
                                               "worktree-of-main").exists())

    code, printed, calls = s.run()
    check("at the same commit after a pass, no run is due", code == 0 and calls == []
          and "no run due" in printed, (code, printed))

    # No nc-test-sandbox has /run/user/<uid>/bus, so the daily run's helper is handed a
    # machine where the bus is there, or is not.
    real_module_loaded_by_path = program.module_loaded_by_path
    FAKE_UID = 4242

    def daily_run_module_on_a_machine_whose_user_bus(bus_exists):
        def loaded(name, path):
            daily = real_module_loaded_by_path(name, path)
            real_helper = daily.environment_with_user_runtime_directory_when_the_user_session_bus_exists
            daily.environment_with_user_runtime_directory_when_the_user_session_bus_exists = (
                lambda environment: real_helper(
                    environment, platform="linux", uid=FAKE_UID,
                    path_exists=lambda path: bus_exists and path == f"/run/user/{FAKE_UID}/bus"))
            return daily
        return loaded

    saved_xdg = os.environ.pop("XDG_RUNTIME_DIR", None)
    try:
        s.commit_on_origin("cron starts the program without the user's session bus")
        with constants(module_loaded_by_path=daily_run_module_on_a_machine_whose_user_bus(True)):
            code, printed, calls = s.run()
        seen = Path(f"{s.calls}.xdg").read_text()
        check("started without XDG_RUNTIME_DIR, as under cron, on a machine with the user's "
              "session bus, the runner is given XDG_RUNTIME_DIR=/run/user/<uid>",
              code == 0 and len(calls) == 1 and seen == f"/run/user/{FAKE_UID}",
              (code, printed, seen))
        s.commit_on_origin("a machine with no user session bus")
        with constants(module_loaded_by_path=daily_run_module_on_a_machine_whose_user_bus(False)):
            code, printed, calls = s.run()
        seen = Path(f"{s.calls}.xdg").read_text()
        check("on a machine with no user session bus, the runner is given no XDG_RUNTIME_DIR",
              code == 0 and len(calls) == 1 and seen == "unset", (code, printed, seen))
    finally:
        if saved_xdg is not None:
            os.environ["XDG_RUNTIME_DIR"] = saved_xdg
    first_commit = s.state()["passing_commit"]

    # --- main moves, and the run fails -------------------------------------------
    merged = s.merge_on_origin(41)
    code, printed, calls = s.run("fail")
    state = s.state()
    check("when main moves, the run compares with the passing commit",
          len(calls) == 1 and calls[0][calls[0].index(
              "--only-suites-whose-recorded-inputs-changed-since") + 1] == first_commit, calls)
    check("a failing suite makes a failed run, keeps the passing commit, and copies the "
          "suite's log beside the record",
          code == 0 and state["last_run"]["result"] == "failed"
          and state["passing_commit"] == first_commit
          and [entry["suite"] for entry in state["last_run"]["failing_suites"]]
          == ["outside-a-test.py"]
          and Path(state["last_run"]["failing_suites"][0]["log"]).read_text()
          == "the suite's own output\n", (code, printed, state))

    notice = s.notice()
    check("the merge gate's notice names the failing suite, its log, the range and the pull "
          "request merged in it, and how to record the follow-up",
          "outside-a-test.py" in notice and f"{first_commit[:12]}..{merged[:12]}" in notice
          and "#41" in notice and "--record-follow-up-request-sent" in notice, notice)

    code, printed, calls = s.run("fail")
    check("a failure is not tried again within the hour", calls == [] and code == 0,
          (code, printed))
    with constants(RETRY_FAILED_RUN_AFTER_SECONDS=-1):
        code, printed, calls = s.run("fail")
    check("a failure is tried again once the hour has passed", len(calls) == 1, (code, printed))

    log_mark, fail_prefix = runner.SUITE_LINE_LOG_MARK, runner.FAILED_SUITE_LINE_PREFIX
    check("a closing-list line before the suite's progress line keeps the closing list's log",
          program.failing_suites_and_logs(
              f"{fail_prefix}outside-a-test.py exit 1{log_mark}/logs/outside-a-test.py.log\n"
              f"{fail_prefix}outside-a-test.py exit 1 (1.0s)\n", fail_prefix, log_mark)
          == [("outside-a-test.py", "/logs/outside-a-test.py.log")])

    # --- Following a failure up ---------------------------------------------------
    own = held(Path(f"{s.state_file}.lock"))
    before = s.state_file.read_text()
    code, printed, _ = s.run("pass", "--record-follow-up-request-sent")
    own.close()
    check("--record-follow-up-request-sent refuses while a run holds the program's lock, and "
          "leaves the state file as that run will write it",
          code == program.EXIT_REFUSED and "Run again in 10 minutes" in printed
          and s.state_file.read_text() == before, (code, printed))
    code, printed, _ = s.run("pass", "--record-follow-up-request-sent")
    check("--record-follow-up-request-sent writes the time into the failed last run",
          code == 0 and s.state()["last_run"]["follow_up_request_sent"], (code, printed))
    notice = s.notice()
    check("after the follow-up the notice is one line naming when it was sent",
          len(notice.strip().splitlines()) == 1 and "already has a follow-up request" in notice,
          notice)

    # --- A stopped runner ---------------------------------------------------------
    s.merge_on_origin(42)
    code, printed, calls = s.run("refuse")
    state = s.state()
    check("a runner that exits 2 makes a stopped run with its refusal, exit 4",
          code == program.EXIT_RUN_STOPPED_BY_A_FAILED_STEP and state["last_run"]["result"] == "stopped"
          and "a refusal for the test" in state["last_run"]["reason"], (code, printed, state))
    code, printed, calls = s.run()
    check("after a stop, a run is due at the same commit, and its pass moves the passing commit",
          len(calls) == 1 and code == 0 and s.state()["passing_commit"] == git(
              s.origin, "rev-parse", "HEAD"), (code, printed))
    check("after a passing run the merge gate's notice is empty", s.notice() == "")

    s.merge_on_origin(43)
    began = time.monotonic()
    with constants(RUNNER_TIMEOUT_SECONDS=1, RUNNER_STOP_GRACE_SECONDS=5):
        code, printed, calls = s.run("sleep")
    took = time.monotonic() - began
    state = s.state()
    check("a runner past its time limit is stopped by SIGTERM within the grace, and the run "
          "recorded as stopped",
          code == program.EXIT_RUN_STOPPED_BY_A_FAILED_STEP and state["last_run"]["result"] == "stopped"
          and "ran past" in state["last_run"]["reason"] and took < 30, (code, printed, state, took))
    began = time.monotonic()
    with constants(RUNNER_TIMEOUT_SECONDS=2, RUNNER_STOP_GRACE_SECONDS=1):
        code, printed, calls = s.run("ignore-sigterm-then-sleep")
    took = time.monotonic() - began
    check("a runner that ignores SIGTERM is killed after the grace, and the run recorded as "
          "stopped", code == program.EXIT_RUN_STOPPED_BY_A_FAILED_STEP and s.state()["last_run"]["result"] == "stopped"
          and took < 30, (code, printed, took))

    s.merge_on_origin(44)
    code, printed, calls = s.run("fail-with-missing-log")
    failing = s.state()["last_run"]["failing_suites"]
    check("a failing suite's log that cannot be copied is named as not copied, and the run "
          "still recorded as failed",
          code == 0 and s.state()["last_run"]["result"] == "failed"
          and failing[0]["log"].startswith("not copied from /no/such/log.txt"), (code, failing))
    s.merge_on_origin(45)
    code, printed, calls = s.run("fail-before-closing-list")
    failing = s.state()["last_run"]["failing_suites"]
    check("a runner that exits 1 before its closing list still has its failing suite "
          "recorded, once, with no log, and the notice names it",
          code == 0 and s.state()["last_run"]["result"] == "failed"
          and [entry["suite"] for entry in failing] == ["outside-a-test.py"]
          and failing[0]["log"].startswith("none:") and "outside-a-test.py" in s.notice(),
          (code, failing))
    state = s.state()
    state["last_run"]["ended"] = "not a time"
    s.state_file.write_text(json.dumps(state))
    code, printed, calls = s.run()
    check("a failed run whose end cannot be read is tried again", len(calls) == 1
          and "cannot be read" in printed, (code, printed))

    state = s.state()
    state["last_run"].update(result="failed", compared_with="0" * 40)
    s.state_file.write_text(json.dumps(state))
    notice = s.notice()
    check("the notice says when the merged pull requests cannot be read",
          "the merged pull requests could not be read" in notice, notice)

    # --- The state file -----------------------------------------------------------
    s.state_file.write_text("{not json")
    notice = s.notice()
    check("the notice says when the state file cannot be read",
          "cannot be read" in notice, notice)
    code, printed, calls = s.run()
    check("an unreadable state file counts as empty: the run happens, with no passing commit",
          code == 0 and len(calls) == 1
          and "--only-suites-whose-recorded-inputs-changed-since" not in calls[0]
          and s.state()["last_run"]["result"] == "passed", (code, printed, calls))
    s.state_file.write_text("{not json")
    code, printed, _ = s.run("pass", "--record-follow-up-request-sent")
    check("--record-follow-up-request-sent refuses an unreadable state file",
          code == program.EXIT_REFUSED and "not JSON" in printed, (code, printed))
    s.run()
    code, printed, _ = s.run("pass", "--record-follow-up-request-sent")
    check("--record-follow-up-request-sent refuses when the last run passed",
          code == program.EXIT_REFUSED and "no follow-up request is owed" in printed,
          (code, printed))

    # --- Steps that fail ---------------------------------------------------------------
    s.commit_on_origin("a leftover worktree")
    leftover = s.temporary / program.PROGRAM / "worktree-of-main"
    git(s.clone, "fetch", "-q", "origin")
    git(s.clone, "worktree", "add", "-q", "--detach", str(leftover), "origin/main")
    (leftover / "left-by-a-killed-run.txt").write_text("x\n")
    code, printed, calls = s.run()
    check("a worktree a killed run left is removed first, and the run goes on",
          code == 0 and len(calls) == 1 and not leftover.exists(), (code, printed))

    s.commit_on_origin("the log-store cannot be written")
    real_log_store = s.log_store
    s.log_store = s.root / "a-file-not-a-log-store"
    s.log_store.write_text("x\n")
    code, printed, calls = s.run()
    s.log_store = real_log_store
    state = s.state()
    check("a record that cannot be written to the log-store stops the run, exit 4, recorded",
          code == program.EXIT_RUN_STOPPED_BY_A_FAILED_STEP and state["last_run"]["result"] == "stopped"
          and "could not be written to the log-store" in state["last_run"]["reason"],
          (code, printed, state))

    (s.origin / "scripts" / "run-all-test-suites.py").write_bytes(b"\xff\xfe not UTF-8\n")
    git(s.origin, "add", "-A")
    git(s.origin, "commit", "-q", "-m", "an unreadable runner")
    code, printed, calls = s.run()
    state = s.state()
    check("a runner whose suite lists cannot be read stops the run, exit 4, recorded",
          code == program.EXIT_RUN_STOPPED_BY_A_FAILED_STEP and calls == []
          and "the no-sandbox suites could not be read" in state["last_run"]["reason"],
          (code, printed, state))
    (s.origin / "scripts" / "run-all-test-suites.py").write_text(RUNNER_LISTS)
    git(s.origin, "add", "-A")
    git(s.origin, "commit", "-q", "-m", "the runner restored")

    real_add = program.git

    def worktree_add_fails(clone, *arguments, **options):
        if arguments[:2] == ("worktree", "add"):
            return subprocess.CompletedProcess(arguments, 128, "", "fatal: injected failure")
        return real_add(clone, *arguments, **options)

    with constants(git=worktree_add_fails):
        code, printed, calls = s.run()
    state = s.state()
    head = git(s.origin, "rev-parse", "HEAD")
    check("a worktree that cannot be made stops the run, exit 4, recorded with git's error",
          code == program.EXIT_RUN_STOPPED_BY_A_FAILED_STEP and calls == []
          and f"the worktree of {head[:12]} could not be made: fatal: injected failure"
          == state["last_run"]["reason"], (code, printed, state))

    def rev_parse_fails(clone, *arguments, **options):
        if arguments[:1] == ("rev-parse",):
            return subprocess.CompletedProcess(arguments, 128, "", "fatal: no such ref")
        return real_add(clone, *arguments, **options)

    with constants(git=rev_parse_fails):
        code, printed, calls = s.run()
    check("an origin/main that cannot be resolved stops the run, exit 4, recorded",
          code == program.EXIT_RUN_STOPPED_BY_A_FAILED_STEP and calls == []
          and "origin/main could not be resolved: fatal: no such ref"
          in s.state()["last_run"]["reason"], (code, printed))
    code, printed, _ = s.run("pass", "--record-follow-up-request-sent")
    check("--record-follow-up-request-sent after a run stopped before main was resolved records "
          "the follow-up and says so, with no commit",
          code == 0 and "recorded for the run at no commit" in printed
          and s.state()["last_run"]["follow_up_request_sent"], (code, printed))

    with constants(GIT_FETCH_TIMEOUT_SECONDS=0.001):
        code, printed, calls = s.run()
    check("a fetch past its time limit stops the run, exit 4, naming the git command",
          code == program.EXIT_RUN_STOPPED_BY_A_FAILED_STEP and calls == []
          and "git fetch ran past" in s.state()["last_run"]["reason"], (code, printed))

    real_state_file = s.state_file
    s.state_file = s.root / "a-directory-not-a-state-file"
    s.state_file.mkdir()
    code, printed, calls = s.run()
    check("a state file that cannot be written stops the run with exit 4 and says so",
          code == program.EXIT_RUN_STOPPED_BY_A_FAILED_STEP and "could not be written" in printed, (code, printed))
    s.state_file = s.root / "a-file" / "state.json"
    (s.root / "a-file").write_text("x\n")
    code, printed, calls = s.run()
    check("a lock that cannot be taken stops the program with exit 4 and says why",
          code == program.EXIT_RUN_STOPPED_BY_A_FAILED_STEP and "could not be taken" in printed and calls == [],
          (code, printed))
    code, printed, _ = s.run("pass", "--record-follow-up-request-sent")
    s.state_file = real_state_file
    check("--record-follow-up-request-sent refuses, exit 2, when its lock file cannot be opened, "
          "and says why",
          code == program.EXIT_REFUSED and "the lock file" in printed
          and "could not be opened" in printed, (code, printed))

    # --- A failed fetch -----------------------------------------------------------
    s.commit_on_origin("after the fetch fails")
    git(s.clone, "remote", "set-url", "origin", str(s.root / "no-such-origin"))
    code, printed, calls = s.run()
    state = s.state()
    check("a failed fetch exits 4 and records a stopped run with the reason",
          code == program.EXIT_RUN_STOPPED_BY_A_FAILED_STEP and calls == []
          and state["last_run"]["result"] == "stopped"
          and "git fetch origin failed" in state["last_run"]["reason"], (code, printed, state))
    s.state_file.unlink()
    check("with no state file the notice is empty", s.notice() == "")
    real_state_file = s.state_file
    s.state_file = s.root / "another-directory-not-a-state-file"
    s.state_file.mkdir()
    code, printed, calls = s.run()
    s.state_file = real_state_file
    check("when the fetch fails and the state file cannot be written either, both are said",
          code == program.EXIT_RUN_STOPPED_BY_A_FAILED_STEP and "git fetch origin failed" in printed
          and "could not be written either" in printed, (code, printed))

print(f"{len(failures)} failed" if failures else "all cases passed")
sys.exit(1 if failures else 0)
