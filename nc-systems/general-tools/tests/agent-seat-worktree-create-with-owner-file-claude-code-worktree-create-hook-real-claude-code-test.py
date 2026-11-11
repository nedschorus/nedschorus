#!/usr/bin/env python3
"""The trial of nc-systems/general-tools/agent-seat-worktree-create-with-owner-file-claude-code-worktree-create-hook.py
against the installed Claude Code.

A headless `claude -p` on haiku, given the hook as its only WorktreeCreate hook, in a scratch
clone with a local bare origin, starts one subagent with isolation "worktree". The suite
checks that the hook made the subagent's worktree with its owner file, that `git worktree
list` never shows a worktree locked while claude runs, and that the worktree is still there,
unlocked, once claude has exited. A later Claude Code that locks or removes such a worktree
fails it. It needs the real HOME, where claude is logged in, and an agent-seat of this machine
for GIT_AUTHOR_NAME, so scripts/run-all-test-suites.py runs it outside any sandbox. It spends
one short haiku agent-session, and removes the Claude Code project directory claude made for
the scratch clone.

Run: python3 nc-systems/general-tools/tests/agent-seat-worktree-create-with-owner-file-claude-code-worktree-create-hook-real-claude-code-test.py
Prints one line per case and exits non-zero if any case fails.
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
transcripts = load_module("claude_code_session_transcript_lookup_and_text_search_common",
                          REPO_ROOT / "scripts" / "claude-code-session-transcript-lookup-and-text-search-common.py")

failures = []


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
    if shutil.which(headless.CLAUDE_CODE_PROGRAM) is None:
        check("claude is on PATH for the trial", False, "it is not")
        return
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
            "acceptEdits", caller_claude_code_session_settings=settings) + [
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
                                      if any(line.startswith("locked") for line in lines))

        watcher = threading.Thread(target=watch_for_locks)
        watcher.start()
        try:
            completed = subprocess.run(command, cwd=clone, env=environment, stdin=subprocess.DEVNULL,
                                       capture_output=True, text=True, timeout=CLAUDE_RUN_TIMEOUT_SECONDS,
                                       check=False)
            claude_stdout = completed.stdout
            outcome = f"exit {completed.returncode}, stdout {claude_stdout[-800:]!r}, stderr {completed.stderr[-800:]!r}"
            ran = completed.returncode == 0
        except subprocess.TimeoutExpired:
            claude_stdout, outcome, ran = "", f"claude did not finish within {CLAUDE_RUN_TIMEOUT_SECONDS} s", False
        finally:
            stop.set()
            watcher.join()
        check("claude -p with the hook as its WorktreeCreate hook runs its subagent and exits 0", ran, outcome)
        made = [Path(path) for path in worktree_records(clone)
                if Path(path).parent == clone / ".claude" / "worktrees"
                and SUBAGENT_WORKTREE_DIRECTORY_NAME.fullmatch(Path(path).name)]
        check("the hook made exactly one worktree, worktree-agent-a<16 hex digits>, for the subagent",
              len(made) == 1, f"{list(worktree_records(clone))}; {outcome}")
        if len(made) == 1:
            check("the subagent ran in the hook's worktree", str(made[0]) in claude_stdout, outcome)
            check("the hook's worktree has the owner file naming the agent-seat",
                  owner_file.worktree_owner_file_read(made[0]) == {"owner_kind": owner_file.OWNER_AGENT_SEAT,
                                                                    "agent_seat": seat}, "")
            check("Claude Code leaves the hook's worktree in place once claude has exited",
                  made[0].is_dir() and str(made[0]) in worktree_records(clone), "")
        check("Claude Code never locked a worktree while claude ran, nor after",
              not locked_records and not any(line.startswith("locked") for lines in worktree_records(clone).values()
                                             for line in lines),
              f"locked records seen: {locked_records[:3]}")
    finally:
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(project_directory, ignore_errors=True)


test_trial_against_the_installed_claude_code()
print(f"FAILED: {len(failures)} failed" if failures else "PASSED: 0 failed")
sys.exit(1 if failures else 0)
