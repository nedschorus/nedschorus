#!/usr/bin/env python3
"""Tests for agent-seat-worktrees-and-branches-with-no-pull-request-first-prompt-list.py.

Each case builds a scratch origin and clone, commits under chosen author
names, and lists for one agent-seat. A gh first on PATH prints the pull
requests in FAKE_GH_PULL_REQUESTS, or fails with FAKE_GH_EXIT_CODE, so no run
reaches GitHub.

Run: python3 nc-systems/handoff/tests/agent-seat-worktrees-and-branches-with-no-pull-request-first-prompt-list-test.py
"""

import atexit
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

SYSTEM_DIRECTORY = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = SYSTEM_DIRECTORY.parent.parent
MODULE_PATH = SYSTEM_DIRECTORY / "agent-seat-worktrees-and-branches-with-no-pull-request-first-prompt-list.py"

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    REPOSITORY_ROOT / "scripts" / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

SCRATCH = Path(tempfile.mkdtemp(prefix="agent-seat-worktrees-and-branches-list-test-"))
atexit.register(shutil.rmtree, SCRATCH, ignore_errors=True)
HOME = SCRATCH / "home"
HOME.mkdir()
GLOBAL_CONFIG = SCRATCH / "gitconfig"
GLOBAL_CONFIG.write_text("[user]\n\tname = list test\n\temail = test@nedschorus.invalid\n"
                         "[init]\n\tdefaultBranch = main\n[advice]\n\tdetachedHead = false\n")
os.environ.update(HOME=str(HOME), GIT_CONFIG_GLOBAL=str(GLOBAL_CONFIG), GIT_CONFIG_NOSYSTEM="1")
for variable in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL",
                 "FAKE_GH_PULL_REQUESTS", "FAKE_GH_EXIT_CODE"):
    os.environ.pop(variable, None)

FAKE_GH_DIRECTORY = SCRATCH / "fake-gh"
FAKE_GH_DIRECTORY.mkdir()
(FAKE_GH_DIRECTORY / "gh").write_text(
    "#!/bin/sh\n"
    'if [ -n "$FAKE_GH_EXIT_CODE" ]; then echo "gh: stand-in listing failure" >&2; '
    'exit "$FAKE_GH_EXIT_CODE"; fi\n'
    'printf "%s\\n" "${FAKE_GH_PULL_REQUESTS:-[]}"\n', encoding="utf-8")
(FAKE_GH_DIRECTORY / "gh").chmod(0o755)
os.environ["PATH"] = f"{FAKE_GH_DIRECTORY}{os.pathsep}{os.environ.get('PATH', '')}"

_spec = importlib.util.spec_from_file_location("listing", MODULE_PATH)
listing = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(listing)
cleaner = listing.clean_worktrees_module()
owner_file = cleaner.owner_file

failures = []


def check(condition, description, detail=""):
    print(("ok   " if condition else "FAIL ") + description)
    if not condition:
        failures.append(description)
        if detail:
            print(f"     {detail!r}"[:2000])


def git(directory, *arguments, author=None):
    environment = dict(os.environ)
    if author:
        environment.update(GIT_AUTHOR_NAME=author, GIT_AUTHOR_EMAIL=f"{author}@nedschorus.invalid")
    result = subprocess.run(["git", "-C", str(directory), *arguments], capture_output=True,
                            text=True, env=environment)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)} in {directory}: {result.stderr}")
    return result.stdout.strip()


clone_count = [0]


def new_clone():
    clone_count[0] += 1
    base = SCRATCH / f"clone-{clone_count[0]}"
    origin = base / "origin.git"
    git(SCRATCH, "init", "-q", "--bare", str(origin))
    main = base / "main"
    git(SCRATCH, "clone", "-q", str(origin), str(main))
    (main / "tracked.txt").write_text("one\n")
    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "first")
    git(main, "push", "-q", "origin", "main")
    return main


def branch_with_commit(main, branch, author, start="origin/main"):
    """A branch from start, with one commit by author, left checked out nowhere."""
    git(main, "branch", branch, start)
    path = main.parent / f"tmp-{branch}"
    git(main, "worktree", "add", "-q", str(path), branch)
    (path / f"{branch}.txt").write_text(branch + "\n")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", f"work on {branch}", author=author)
    tip = git(path, "rev-parse", "HEAD")
    git(main, "worktree", "remove", str(path))
    return tip


def owned_worktree(main, name, record):
    path = main.parent / name
    git(main, "worktree", "add", "-q", "-b", name, str(path), "origin/main")
    git_directory = Path(git(path, "rev-parse", "--absolute-git-dir"))
    (git_directory / owner_file.WORKTREE_OWNER_FILE_NAME).write_text(json.dumps(record) + "\n")
    return path.resolve()


def set_pull_requests(pull_requests):
    os.environ["FAKE_GH_PULL_REQUESTS"] = json.dumps(pull_requests)


def dead_owner_key():
    if sys.platform.startswith("linux"):
        return "0" * 32 + "-1-1"
    return "999999-1"


def test_branches():
    main = new_clone()
    set_pull_requests([])
    branch_with_commit(main, "seat-a-work", "seat-a")
    branch_with_commit(main, "seat-b-work", "seat-b")
    branch_with_commit(main, "nobody-work", "unconfigured-agent")
    branch_with_commit(main, "by-head-name", "seat-a")
    by_commit_tip = branch_with_commit(main, "by-head-commit", "seat-a")
    pushed_tip = branch_with_commit(main, "pushed-work", "seat-a")
    git(main, "push", "-q", "origin", "pushed-work")
    git(main, "branch", "landed", "origin/main")
    branch_with_commit(main, "checked-out", "seat-a")
    git(main, "worktree", "add", "-q", str(main.parent / "holder"), "checked-out")
    set_pull_requests([
        {"number": 7, "state": "OPEN", "headRefName": "by-head-name", "headRefOid": "0" * 40},
        {"number": 8, "state": "CLOSED", "headRefName": "renamed-on-github",
         "headRefOid": by_commit_tip},
    ])
    text, failed = listing.list_text_and_failure(main, "seat-a")
    check(not failed, "a full listing reports no failure", text)
    check("branch seat-a-work; 1 commit(s) not on origin/main" in text and "not on origin" in text,
          "a branch whose tip this agent-seat wrote, with no pull request, is listed", text)
    check("seat-b-work" not in text, "another agent-seat's branch is not listed", text)
    check("nobody-work" not in text, "a branch whose tip author is no agent-seat is not listed", text)
    check("by-head-name" not in text, "a branch that is a pull request's head branch is not listed")
    check("by-head-commit" not in text,
          "a branch whose tip is a pull request's head commit is not listed", text)
    check(f"branch pushed-work; 1 commit(s) not on origin/main, the newest {pushed_tip[:12]}" in text
          and "on origin at the same commit" in text, "a pushed branch says it is on origin", text)
    check("landed" not in text, "a branch with nothing beyond origin/main is not listed")
    check("checked-out" not in text, "a branch a worktree has checked out is not listed as a branch")
    check("branches with no pull request: 2:" in text and "git branch -D <branch>" in text,
          "the branch section counts its entries and the steps follow", text)
    check(listing.list_text_and_failure(main, "seat-c") == ("", False),
          "an agent-seat with nothing to list gets no paragraph")
    os.environ["FAKE_GH_EXIT_CODE"] = "3"
    try:
        nothing = listing.list_text_and_failure(main, "seat-c")
    finally:
        os.environ.pop("FAKE_GH_EXIT_CODE")
    check(nothing == ("", False), "gh is not asked when nothing could be listed", nothing)


def test_pushed_text():
    check(listing.pushed_text("b", "1", {"b": "2"}) == "on origin at a different commit",
          "a branch on origin at another commit says so")
    check(listing.pushed_text("b", "1", {}) == "not on origin", "an unpushed branch says so")


def test_worktrees():
    main = new_clone()
    set_pull_requests([])
    seat_owned = owned_worktree(main, "seat-owned", {"owner_kind": "agent-seat", "agent_seat": "seat-a"})
    other = owned_worktree(main, "other-owned", {"owner_kind": "agent-seat", "agent_seat": "seat-b"})
    stopped = owned_worktree(main, "stopped-session", {"owner_kind": "agent-session",
                                                        "agent_seat": "seat-a",
                                                        "owner_key": dead_owner_key()})
    home = owned_worktree(main, "agent-home", {"owner_kind": "agent-seat", "agent_seat": "seat-a"})
    set_pull_requests([{"number": 12, "state": "OPEN", "headRefName": "seat-owned",
                        "headRefOid": "0" * 40}])
    text, failed = listing.list_text_and_failure(main, "seat-a", skip_worktree=home)
    check(not failed, "a worktree listing reports no failure", text)
    check(f"worktree {seat_owned}; branch seat-owned; pull request #12 (open)" in text,
          "a worktree whose owner file names this agent-seat is listed with its pull request", text)
    check(f"worktree {stopped}; branch stopped-session; no pull request" in text,
          "a worktree of a stopped agent-session of this agent-seat is listed", text)
    check(str(other) not in text, "another agent-seat's worktree is not listed")
    check(str(home) not in text, "the directory the agent-session starts in is not listed")
    check("worktrees: 2:" in text, "the worktree section counts its entries", text)
    saved = owner_file.worktree_owner_running_state
    owner_file.worktree_owner_running_state = lambda record, *rest: (owner_file.RUNNING, "runs")
    try:
        running_text = listing.first_prompt_text(main, "seat-a", skip_worktree=home)
    finally:
        owner_file.worktree_owner_running_state = saved
    check(str(stopped) not in running_text and str(seat_owned) in running_text,
          "a worktree whose owning agent-session still runs is not listed", running_text)
    (Path(git(other, "rev-parse", "--absolute-git-dir")) / owner_file.WORKTREE_OWNER_FILE_NAME
     ).write_text("not json")
    check(listing.list_text_and_failure(main, "seat-b") == ("", False),
          "a worktree whose owner file cannot be read is not listed")


def test_gh_failure():
    main = new_clone()
    owned = owned_worktree(main, "seat-owned", {"owner_kind": "agent-seat", "agent_seat": "seat-a"})
    branch_with_commit(main, "seat-a-work", "seat-a")
    os.environ["FAKE_GH_EXIT_CODE"] = "3"
    try:
        text, failed = listing.list_text_and_failure(main, "seat-a")
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = listing.main(["list", "--agent-seat", "seat-a", "--repo", str(main)])
    finally:
        os.environ.pop("FAKE_GH_EXIT_CODE")
    check(failed and exit_code == 1, "a gh failure is reported as a failure", (failed, exit_code))
    check(f"worktree {owned}; branch seat-owned; pull request state unknown" in text,
          "worktrees are still listed, with their pull request state unknown", text)
    check("branches with no pull request could not be listed" in text and "stand-in listing failure"
          in text and "list --agent-seat seat-a" in text and "seat-a-work" not in text,
          "the branch list is replaced by why, with the list command", text)
    check(output.getvalue().strip() == text, "the list command prints the same text")


def test_other_failure_and_outside():
    main = new_clone()
    saved = listing.owned_worktrees

    def fails(*arguments):
        raise listing.ListingFailed("`git worktree list` exited 128: broken")

    listing.owned_worktrees = fails
    try:
        text, failed = listing.list_text_and_failure(main, "seat-a")
    finally:
        listing.owned_worktrees = saved
    check(failed and "could not be listed (ListingFailed" in text and "broken" in text
          and "list --agent-seat seat-a" in text,
          "any other failure is stated, with the list command, not left as an empty list", text)
    outside = SCRATCH / "not-a-repository"
    outside.mkdir()
    check(listing.list_text_and_failure(outside, "seat-a") == ("", False),
          "a directory outside any clone has nothing to list")
    try:
        listing.git_lines(main, "rev-parse", "--verify", "no-such-branch")
        raised = None
    except listing.ListingFailed as error:
        raised = str(error)
    check(raised is not None and "exited 128" in raised, "a failing git command raises ListingFailed",
          raised)


def test_more_than_the_limit():
    main = new_clone()
    set_pull_requests([])
    for number in range(listing.ENTRIES_AT_MOST + 2):
        branch_with_commit(main, f"many-{number:02d}", "seat-a")
    text = listing.first_prompt_text(main, "seat-a")
    check(f"branches with no pull request: {listing.ENTRIES_AT_MOST + 2}:" in text
          and "- and 2 more; list them all with:" in text,
          "entries past the limit are counted, with the list command", text[-400:])


def test_supervisor_appends_the_list():
    fixture_spec = importlib.util.spec_from_file_location(
        "handoff_supervisor_test_fixture", SYSTEM_DIRECTORY / "tests" / "handoff-supervisor-test-fixture.py")
    fixture = importlib.util.module_from_spec(fixture_spec)
    fixture_spec.loader.exec_module(fixture)
    supervisor = fixture.supervisor
    main = new_clone()
    set_pull_requests([])
    branch_with_commit(main, "seat-five-work", "seat-five")
    output = io.StringIO()
    with redirect_stdout(output):
        text = supervisor.agent_seat_worktrees_and_branches_text("seat-five", main)
    check(text.startswith("This agent-seat's branches with no pull request: 1:")
          and "handoff-supervisor: This agent-seat's branches" in output.getvalue(),
          "the handoff-supervisor builds the list and prints its first line", text[:200])
    handoffs = SCRATCH / "handoffs-supervisor"
    handoffs.mkdir()
    launched = []
    supervisor.launch_agent_session = (
        lambda command, session_id, working_directory, prompt, **keywords:
        launched.append(prompt) or (_ for _ in ()).throw(StopIteration()))
    supervisor.launch_time_git_sync = lambda working_directory: "launch-time-git-sync: test"
    settings = supervisor.SupervisorSettings(
        agent="seat-five", working_directory=main, handoff_directory=handoffs,
        agent_command="claude", first_prompt="Founding prompt.",
        first_prompt_wins_over_crashed_transcript=True, agent_update_timeout_seconds=0)
    with redirect_stdout(io.StringIO()):
        try:
            supervisor.supervise_sessions(settings)
        except StopIteration:
            pass
    check(launched and launched[0].startswith(
        "Founding prompt.\n\nThis agent-seat's branches with no pull request: 1:"),
          "every launch's prompt carries the list after the prompt", launched[:1] and launched[0][:200])


for case in (test_branches, test_pushed_text, test_worktrees, test_gh_failure,
             test_other_failure_and_outside, test_more_than_the_limit,
             test_supervisor_appends_the_list):
    print(f"-- {case.__name__}")
    case()
    os.environ.pop("FAKE_GH_PULL_REQUESTS", None)

print(f"{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
