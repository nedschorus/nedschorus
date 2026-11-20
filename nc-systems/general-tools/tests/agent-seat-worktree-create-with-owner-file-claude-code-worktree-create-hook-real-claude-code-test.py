#!/usr/bin/env python3
"""The trial of nc-systems/general-tools/agent-seat-worktree-create-with-owner-file-claude-code-worktree-create-hook.py
against the installed Claude Code.

A headless `claude -p` on haiku, given the hook as its only WorktreeCreate hook, in a scratch
clone with a local bare origin, starts one subagent with isolation "worktree". The suite
checks that the hook made the subagent's worktree with its owner file, naming claude's
agent-session, which has stopped once claude has exited, that `git worktree
list` never shows a worktree locked while claude runs, and that the worktree is still there,
unlocked, once claude has exited. A later Claude Code that locks or removes such a worktree
fails it. It needs the real HOME, where claude is logged in, and an agent-seat of this machine
for GIT_AUTHOR_NAME, so scripts/run-all-test-suites.py runs it outside any sandbox. It spends
one short haiku agent-session, and removes the Claude Code project directory claude made for
the scratch clone. When claude names a cause outside this repository, such as its usage limit
or being logged out, the trial's cases are not judged: the suite prints the cause as its last
line and exits run-all-test-suites.py's NC_TEST_SUITE_EXIT_CODE_FOR_NOT_RUN_BECAUSE_A_CAUSE_OUTSIDE_THIS_REPOSITORY_STOPPED_ITS_CASES,
unless another case failed.

Run: python3 nc-systems/general-tools/tests/agent-seat-worktree-create-with-owner-file-claude-code-worktree-create-hook-real-claude-code-test.py
Prints one line per case and exits 1 if any case fails.
"""

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK = REPO_ROOT / "nc-systems" / "general-tools" / "agent-seat-worktree-create-with-owner-file-claude-code-worktree-create-hook.py"
CLAUDE_RUN_TIMEOUT_SECONDS = 600
LOCK_POLL_SECONDS = 0.2
SUBAGENT_WORKTREE_DIRECTORY_NAME = re.compile(r"worktree-agent-a[0-9a-f]{16}")
CLAUDE_MODEL = "haiku"
# `git worktree add` itself holds this lock while it checks the files out, and drops it when the add ends.
GIT_WORKTREE_ADD_OWN_LOCK_LINE = "locked initializing"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_git_environment_fixture = load_module("git_redirecting_environment_removal_test_fixture",
                                       REPO_ROOT / "scripts" / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()
owner_file = load_module("worktree_owner_file_read_and_write", REPO_ROOT / "scripts" / "worktree-owner-file-read-and-write.py")
recover_crashed_seats = load_module("recover_crashed_seats", REPO_ROOT / "scripts" / "recover-crashed-seats.py")
headless = load_module(
    "claude_code_headless_run_command_line_prefix_with_no_connectors_and_explicit_permission_mode_common",
    REPO_ROOT / "nc-systems" / "general-tools"
    / "claude-code-headless-run-command-line-prefix-with-no-connectors-and-explicit-permission-mode-common.py")
test_suite_runner = load_module("run_all_test_suites", REPO_ROOT / "scripts" / "run-all-test-suites.py")
claude_cell = load_module("cold_read_claude_cell", REPO_ROOT / "nc-systems" / "cold-read" / "cold-read-claude-cell.py")
transcripts = load_module("claude_code_session_transcript_lookup_and_text_search_common",
                          REPO_ROOT / "scripts" / "claude-code-session-transcript-lookup-and-text-search-common.py")

failures = []
stopped_by_an_outside_cause = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def git(cwd, *arguments):
    return subprocess.run(["git", *arguments], cwd=cwd, capture_output=True, text=True, check=True).stdout


def worktree_records(clone):
    """{path: the porcelain lines of its record} from git worktree list."""
    records = {}
    for block in git(clone, "worktree", "list", "--porcelain").strip().split("\n\n"):
        lines = block.splitlines()
        records[lines[0].removeprefix("worktree ")] = lines[1:]
    return records


def lock_lines_not_git_worktree_adds_own(lines):
    """The `locked` lines of a worktree record, leaving out the lock git worktree add holds while it runs."""
    return [line for line in lines if line.startswith("locked") and line != GIT_WORKTREE_ADD_OWN_LOCK_LINE]


def test_git_worktree_adds_own_lock_is_not_counted_as_a_lock():
    check("git worktree add's own `locked initializing` is not counted as a lock",
          lock_lines_not_git_worktree_adds_own(["HEAD 0123", "detached", "locked initializing"]) == [])
    check("any other lock reason, and a lock with no reason, is counted",
          lock_lines_not_git_worktree_adds_own(["HEAD 0123", "locked claude agent agent-a1 (pid 7)"])
          == ["locked claude agent agent-a1 (pid 7)"]
          and lock_lines_not_git_worktree_adds_own(["locked"]) == ["locked"])


def claude_outside_cause_or_none(returncode, stdout, stderr):
    """"<cause class> — <claude's words>" when claude exited nonzero naming a cause outside this
    repository, such as its usage limit or being logged out, else None."""
    if returncode == 0:
        return None
    cause_class, detail = claude_cell.common.classify_failed_attempt(
        stdout=stdout, stderr=stderr, exit_code=returncode,
        recognised_texts=claude_cell.recognised_failure_texts_for_model(CLAUDE_MODEL))
    return (f"{cause_class} — {detail}" if cause_class in claude_cell.common.USER_CLEARABLE_CAUSE_CLASSES
            else None)


def test_claude_outside_cause_is_told_from_a_failure():
    weekly_limit = "You've hit your weekly limit · resets Nov 16, 8pm (America/Los_Angeles)\n"
    check("claude's weekly limit, exit 1, is an outside cause naming the limit and its reset",
          claude_outside_cause_or_none(1, weekly_limit, "")
          == "account-limit — weekly limit · resets Nov 16, 8pm (America/Los_Angeles)",
          repr(claude_outside_cause_or_none(1, weekly_limit, "")))
    check("claude logged out, exit 1, is an outside cause",
          claude_outside_cause_or_none(1, "", "Not logged in · Please run /login\n")
          == "logged-out — Not logged in · Please run /login")
    check("claude's exit 1 with any other output is not an outside cause",
          claude_outside_cause_or_none(1, "Error: the hook failed\n", "") is None)
    check("claude's exit 0 is not an outside cause, whatever it printed",
          claude_outside_cause_or_none(0, weekly_limit, "") is None)


def agent_seat_of_this_machine():
    """GIT_AUTHOR_NAME when it names an agent-seat of this machine, else the first agent-seat, else None."""
    seats = recover_crashed_seats.list_agent_seat_names_with_agent_session_records(
        recover_crashed_seats.default_agents_root(), recover_crashed_seats.default_handoff_directory())
    name = os.environ.get("GIT_AUTHOR_NAME", "")
    return name if name in seats else (seats[0] if seats else None)


def test_trial_against_the_installed_claude_code():
    seat = agent_seat_of_this_machine()
    if seat is None:
        check("this machine has an agent-seat to name GIT_AUTHOR_NAME for the trial", False,
              "scripts/recover-crashed-seats.py lists none")
        return
    # Cron's PATH does not hold ~/.local/bin, where claude is installed.
    claude = shutil.which(headless.CLAUDE_CODE_PROGRAM) or str(Path.home() / ".local" / "bin" / "claude")
    root = Path(os.path.realpath(tempfile.mkdtemp(prefix="worktree-create-hook-trial-")))
    origin, clone = root / "origin.git", root / "clone"
    project_directory = transcripts.project_directory_for_seat(clone, Path.home() / ".claude" / "projects")
    try:
        git(root, "init", "--quiet", "--bare", "--initial-branch=main", str(origin))
        clone.mkdir()
        git(clone, "init", "--quiet", "--initial-branch=main")
        git(clone, "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "commit", "--quiet",
            "--allow-empty", "-m", "base")
        git(clone, "remote", "add", "origin", str(origin))
        git(clone, "push", "--quiet", "origin", "main")
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(("GIT_", "CLAUDE_CODE_"))}
        environment["GIT_AUTHOR_NAME"] = seat
        settings = {"hooks": {"WorktreeCreate": [{"hooks": [
            {"type": "command", "command": f"{sys.executable} {HOOK}"}]}]}}
        command = headless.claude_code_headless_run_command_line_prefix_build(
            "acceptEdits", program=claude, caller_claude_code_session_settings=settings) + [
            ('Call the Agent tool once, with subagent_type "general-purpose", isolation "worktree", and the '
             'prompt "Run the Bash command: sleep 15; pwd. Reply with its output only." Then reply with the '
             "subagent's reply and nothing else."),
            "--model", "haiku", "--allowedTools", "Agent", "Bash"]
        locked_records, stop = [], threading.Event()

        def watch_for_locks():
            while not stop.wait(LOCK_POLL_SECONDS):
                try:
                    records = worktree_records(clone)
                except subprocess.CalledProcessError:
                    continue
                locked_records.extend((path, lines) for path, lines in records.items()
                                      if lock_lines_not_git_worktree_adds_own(lines))

        watcher = threading.Thread(target=watch_for_locks)
        watcher.start()
        outside_cause = None
        try:
            completed = subprocess.run(command, cwd=clone, env=environment, stdin=subprocess.DEVNULL,
                                       capture_output=True, text=True, timeout=CLAUDE_RUN_TIMEOUT_SECONDS,
                                       check=False)
            claude_stdout = completed.stdout
            outcome = f"exit {completed.returncode}, stdout {claude_stdout[-800:]!r}, stderr {completed.stderr[-800:]!r}"
            ran = completed.returncode == 0
            outside_cause = claude_outside_cause_or_none(completed.returncode, completed.stdout, completed.stderr)
        except subprocess.TimeoutExpired:
            claude_stdout, outcome, ran = "", f"claude did not finish within {CLAUDE_RUN_TIMEOUT_SECONDS} s", False
        except OSError as error:
            claude_stdout, outcome, ran = "", f"{claude} could not start: {error}", False
        finally:
            stop.set()
            watcher.join()
        if outside_cause is not None:
            stopped_by_an_outside_cause.append(outside_cause)
            return
        check("claude -p with the hook as its WorktreeCreate hook runs its subagent and exits 0", ran, outcome)
        made = [Path(path) for path in worktree_records(clone)
                if Path(path).parent == clone / ".claude" / "worktrees"
                and SUBAGENT_WORKTREE_DIRECTORY_NAME.fullmatch(Path(path).name)]
        check("the hook made exactly one worktree, worktree-agent-a<16 hex digits>, for the subagent",
              len(made) == 1, f"{list(worktree_records(clone))}; {outcome}")
        if len(made) == 1:
            check("the subagent ran in the hook's worktree", str(made[0]) in claude_stdout, outcome)
            owner = owner_file.worktree_owner_file_read(made[0])
            check("the hook's worktree has the owner file naming claude's agent-session and the agent-seat, "
                  "an agent-session that has stopped once claude has exited",
                  owner is not None and owner["owner_kind"] == owner_file.OWNER_AGENT_SESSION
                  and owner["agent_seat"] == seat
                  and owner_file.worktree_owner_running_state(owner)[0] == owner_file.STOPPED, str(owner))
            check("Claude Code leaves the hook's worktree in place once claude has exited",
                  made[0].is_dir() and str(made[0]) in worktree_records(clone), "")
        check("Claude Code never locked a worktree while claude ran, nor after",
              not locked_records and not any(lock_lines_not_git_worktree_adds_own(lines)
                                             for lines in worktree_records(clone).values()),
              f"locked records seen: {locked_records[:3]}")
    finally:
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(project_directory, ignore_errors=True)


test_git_worktree_adds_own_lock_is_not_counted_as_a_lock()
test_claude_outside_cause_is_told_from_a_failure()
test_trial_against_the_installed_claude_code()
if failures:
    print(f"FAILED: {len(failures)} failed")
    sys.exit(1)
if stopped_by_an_outside_cause:
    print(f"NOT RUN: the trial against the installed Claude Code; claude stopped: {stopped_by_an_outside_cause[0]}")
    sys.exit(test_suite_runner.NC_TEST_SUITE_EXIT_CODE_FOR_NOT_RUN_BECAUSE_A_CAUSE_OUTSIDE_THIS_REPOSITORY_STOPPED_ITS_CASES)
print("PASSED: 0 failed")
sys.exit(0)
