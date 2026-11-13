#!/usr/bin/env python3
"""Tests for agent-seat-worktrees-and-branches-with-no-pull-request-first-prompt-list.py.

Each case builds a scratch origin and clone, commits under chosen author
names, and lists for one agent-seat. A gh first on PATH prints the pull
requests in FAKE_GH_PULL_REQUESTS, or fails with FAKE_GH_EXIT_CODE, so no run
reaches GitHub.

Run: python3 nc-systems/handoff/tests/agent-seat-worktrees-and-branches-with-no-pull-request-first-prompt-list-test.py
"""

import atexit
import contextlib
import importlib.util
import io
import json
import os
import shlex
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
# Every printed command these tests run writes its removals here, never to the log-store.
REMOVALS_LOG = SCRATCH / "removals-log.txt"
os.environ[cleaner.REMOVED_WORKTREES_AND_DELETED_BRANCHES_LOG_FILE_OVERRIDE_VARIABLE] = str(REMOVALS_LOG)

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


def worktree_order(main):
    """The worktree paths in the order git lists them, which is the order the list reads them."""
    return [Path(line[len("worktree "):]).resolve()
            for line in git(main, "worktree", "list", "--porcelain").splitlines()
            if line.startswith("worktree ")]


def owned_worktree_listed_after(main, prefix, earlier, record):
    """Add owned worktrees until git lists one after earlier, so a loop that stopped at earlier
    would miss it; return that one."""
    for number in range(20):
        path = owned_worktree(main, f"{prefix}-{number}", record)
        order = worktree_order(main)
        if order.index(path) > order.index(earlier):
            return path
    raise RuntimeError(f"git never listed a worktree after {earlier}")


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
    # Sorts before "main", so a test of the name against main by order would show.
    branch_with_commit(main, "a-early-work", "seat-a")
    branch_with_commit(main, "seat-b-work", "seat-b")
    branch_with_commit(main, "nobody-work", "unconfigured-agent")
    branch_with_commit(main, "by-head-name", "seat-a")
    by_commit_tip = branch_with_commit(main, "by-head-commit", "seat-a")
    pushed_tip = branch_with_commit(main, "pushed-work", "seat-a")
    git(main, "push", "-q", "origin", "pushed-work")
    git(main, "branch", "landed", "origin/main")
    branch_with_commit(main, "checked-out", "seat-a")
    git(main, "worktree", "add", "-q", str(main.parent / "holder"), "checked-out")
    git(main, "worktree", "add", "-q", "--detach", str(main.parent / "detached"), "origin/main")
    (main / "main-only.txt").write_text("unpushed\n")
    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "unpushed main commit", author="seat-a")
    git(main, "checkout", "-q", "--detach")
    set_pull_requests([
        {"number": 7, "state": "OPEN", "headRefName": "by-head-name", "headRefOid": "0" * 40},
        {"number": 8, "state": "CLOSED", "headRefName": "renamed-on-github",
         "headRefOid": by_commit_tip},
    ])
    text, failed = listing.list_text_and_failure(main, "seat-a")
    check(not failed, "a full listing reports no failure", text)
    check("branch seat-a-work; main lacks the changes of its 1 commit(s)" in text and "not on origin" in text,
          "a branch whose tip this agent-seat wrote, with no pull request, is listed", text)
    check("seat-b-work" not in text, "another agent-seat's branch is not listed", text)
    check("nobody-work" not in text, "a branch whose tip author is no agent-seat is not listed", text)
    check("by-head-name" not in text, "a branch that is a pull request's head branch is not listed")
    check("by-head-commit" not in text,
          "a branch whose tip is a pull request's head commit is not listed", text)
    check(f"branch pushed-work; main lacks the changes of its 1 commit(s), the newest {pushed_tip[:12]} of " in text
          and "on origin at the same commit" in text, "a pushed branch says it is on origin", text)
    check('"work on seat-a-work"; not on origin' in text,
          "a branch entry gives its newest commit's subject", text)
    check("landed" not in text, "a branch with nothing beyond origin/main is not listed")
    check("checked-out" not in text, "a branch a worktree has checked out is not listed as a branch")
    check("branch main;" not in text, "main is never listed, even with commits origin/main lacks", text)
    check("branch a-early-work;" in text, "a branch whose name sorts before main is listed", text)
    check("more; list them all with:" not in text, "a list within the limit has no line for more")
    check("branches with no pull request: 3:" in text and listing.INSTRUCTIONS in text,
          "the branch section counts its entries and the steps follow", text)
    command_line = next((line for line in text.splitlines()
                         if line.startswith("- branch seat-a-work;")), "")
    command = command_line.split("; delete with: ", 1)[-1]
    check(command.endswith(f"--repo {main} --force-delete-branch seat-a-work"),
          "each branch entry ends with the command that deletes it", command_line)
    deleted = subprocess.run(shlex.split(command), capture_output=True, text=True)
    check(deleted.returncode == 0 and git(main, "branch", "--list", "seat-a-work") == "",
          "the command printed beside a branch deletes it", deleted.stdout + deleted.stderr)
    logged = REMOVALS_LOG.read_text(encoding="utf-8") if REMOVALS_LOG.exists() else ""
    check("deleted-branch\tbranch=seat-a-work" in logged,
          "the branch deletion is logged to the test's own log of removals, not the log-store",
          logged or "no log")
    check(listing.list_text_and_failure(main, "seat-c") == ("", False),
          "an agent-seat with nothing to list gets no paragraph")
    os.environ["FAKE_GH_EXIT_CODE"] = "3"
    try:
        nothing = listing.list_text_and_failure(main, "seat-c")
    finally:
        os.environ.pop("FAKE_GH_EXIT_CODE")
    check(nothing == ("", False), "gh is not asked when nothing could be listed", nothing)
    branch_with_commit(main, "seat-d-reviewed", "seat-d")
    set_pull_requests([{"number": 9, "state": "MERGED", "headRefName": "seat-d-reviewed",
                        "headRefOid": "0" * 40}])
    check(listing.list_text_and_failure(main, "seat-d") == ("", False),
          "an agent-seat whose only branch has a pull request gets no paragraph")


def test_pushed_text():
    check(listing.pushed_text("b", "1", {"b": "2"}) == "on origin at a different commit"
          and listing.pushed_text("b", "2", {"b": "1"}) == "on origin at a different commit",
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
    # Named to sort after the others, so a skip test that compared paths by order would show.
    home = owned_worktree(main, "zz-agent-home", {"owner_kind": "agent-seat", "agent_seat": "seat-a"})
    after_home = owned_worktree(main, "zzz-after-home", {"owner_kind": "agent-seat",
                                                          "agent_seat": "seat-a"})
    stopped_head = git(stopped, "rev-parse", "HEAD")
    set_pull_requests([{"number": 12, "state": "OPEN", "headRefName": "seat-owned",
                        "headRefOid": "0" * 40},
                       {"number": 13, "state": "CLOSED", "headRefName": "renamed",
                        "headRefOid": stopped_head}])
    text, failed = listing.list_text_and_failure(main, "seat-a", skip_worktree=home)
    check(not failed, "a worktree listing reports no failure", text)
    check(str(seat_owned) not in text,
          "a worktree whose pull request is open is left out: merge-lane-2 reviews it", text)
    reopened = owned_worktree(main, "reopened", {"owner_kind": "agent-seat", "agent_seat": "seat-a"})
    set_pull_requests([{"number": 20, "state": "OPEN", "headRefName": "reopened",
                        "headRefOid": "0" * 40},
                       {"number": 21, "state": "CLOSED", "headRefName": "reopened",
                        "headRefOid": "0" * 40}])
    older_open, _ = listing.list_text_and_failure(main, "seat-a", skip_worktree=home)
    check(str(reopened) not in older_open,
          "a worktree with an older open pull request beside a newer closed one is left out",
          older_open)
    git(main, "worktree", "remove", str(reopened))
    set_pull_requests([{"number": 12, "state": "OPEN", "headRefName": "seat-owned",
                        "headRefOid": "0" * 40},
                       {"number": 13, "state": "CLOSED", "headRefName": "renamed",
                        "headRefOid": stopped_head}])
    check(f"worktree {stopped}; branch stopped-session; pull request #13 (closed)" in text,
          "a worktree of a stopped agent-session is listed, its pull request found by head commit",
          text)
    check(str(other) not in text, "another agent-seat's worktree is not listed")
    check(str(home) not in text, "the directory the agent-session starts in is not listed")
    check(str(after_home) in text,
          "the worktrees git lists after the skipped directory are still listed", text)
    check("worktrees: 2:" in text, "the worktree section counts its entries", text)
    command_line = next((line for line in text.splitlines()
                         if line.startswith(f"- worktree {stopped};")), "")
    command = command_line.split("; delete with: ", 1)[-1]
    check(command.endswith(f"--repo {main} --remove-worktree-and-force-delete-its-branch {stopped}"),
          "each worktree entry ends with the command that removes it", command_line)
    removed = subprocess.run(shlex.split(command), capture_output=True, text=True)
    check(removed.returncode == 0 and not stopped.exists()
          and git(main, "branch", "--list", "stopped-session") == "",
          "the command printed beside a worktree removes it and deletes its branch",
          removed.stdout + removed.stderr)
    git(main, "worktree", "add", "-q", "-b", "stopped-session", str(stopped), "origin/main")
    (Path(git(stopped, "rev-parse", "--absolute-git-dir")) / owner_file.WORKTREE_OWNER_FILE_NAME
     ).write_text(json.dumps({"owner_kind": "agent-session", "agent_seat": "seat-a",
                              "owner_key": dead_owner_key()}) + "\n")
    after_stopped = owned_worktree_listed_after(main, "zz-after-stopped", stopped,
                                                {"owner_kind": "agent-seat", "agent_seat": "seat-a"})
    saved = owner_file.worktree_owner_running_state
    owner_file.worktree_owner_running_state = lambda record, *rest: (owner_file.RUNNING, "runs")
    try:
        running_text = listing.first_prompt_text(main, "seat-a", skip_worktree=home)
    finally:
        owner_file.worktree_owner_running_state = saved
    check(str(stopped) not in running_text and str(after_stopped) in running_text,
          "a worktree whose owning agent-session still runs is not listed", running_text)
    (Path(git(other, "rev-parse", "--absolute-git-dir")) / owner_file.WORKTREE_OWNER_FILE_NAME
     ).write_text("not json")
    check(listing.list_text_and_failure(main, "seat-b") == ("", False),
          "a worktree whose owner file cannot be read is not listed")
    after_unreadable = owned_worktree_listed_after(main, "zz-after-unreadable", other,
                                                   {"owner_kind": "agent-seat", "agent_seat": "seat-b"})
    check(str(after_unreadable) in listing.first_prompt_text(main, "seat-b"),
          "an unreadable owner file does not stop the worktrees after it from being listed")


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
    only_branch = new_clone()
    branch_with_commit(only_branch, "seat-a-work", "seat-a")
    os.environ["FAKE_GH_EXIT_CODE"] = "3"
    try:
        text, failed = listing.list_text_and_failure(only_branch, "seat-a")
    finally:
        os.environ.pop("FAKE_GH_EXIT_CODE")
    check(failed and "could not be listed" in text and listing.INSTRUCTIONS not in text,
          "with nothing listed, the steps for listed entries are left out", text)


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
    check(raised is not None and "exited 128" in raised and "fatal" in raised,
          "a failing git command raises ListingFailed, with git's error text", raised)
    set_pull_requests([])
    branch_with_commit(main, "seat-a-work", "seat-a")
    output = io.StringIO()
    with redirect_stdout(output):
        exit_code = listing.main(["list", "--agent-seat", "seat-a", "--repo", str(main)])
    check(exit_code == 0 and "seat-a-work" in output.getvalue(),
          "the list command exits 0 when the whole list was built", exit_code)
    for arguments, why in ((["list", "--repo", str(main)], "without --agent-seat"),
                           ([], "without a command")):
        try:
            with redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                listing.main(arguments)
            code = None
        except SystemExit as stop:
            code = stop.code
        check(code == 2, f"the list command refuses to run {why}", code)
    script = subprocess.run([sys.executable, str(MODULE_PATH), "list", "--agent-seat", "seat-a",
                             "--repo", str(main)], capture_output=True, text=True)
    check(script.returncode == 0 and "seat-a-work" in script.stdout,
          "run as a program, it prints the list", (script.returncode, script.stderr[-300:]))


def test_more_than_the_limit():
    main = new_clone()
    set_pull_requests([])
    for number in range(listing.ENTRIES_AT_MOST):
        branch_with_commit(main, f"many-{number:02d}", "seat-a")
    text = listing.first_prompt_text(main, "seat-a")
    check(f"branches with no pull request: {listing.ENTRIES_AT_MOST}:" in text
          and "more; list them all with:" not in text,
          "exactly the limit of entries are all listed, with no line for more", text[-400:])
    branch_with_commit(main, f"many-{listing.ENTRIES_AT_MOST:02d}", "seat-a")
    text = listing.first_prompt_text(main, "seat-a")
    check("- and 1 more; list them all with:" in text, "one entry past the limit is counted",
          text[-400:])
    branch_with_commit(main, f"many-{listing.ENTRIES_AT_MOST + 1:02d}", "seat-a")
    text = listing.first_prompt_text(main, "seat-a")
    check(f"branches with no pull request: {listing.ENTRIES_AT_MOST + 2}:" in text
          and "- and 2 more; list them all with:" in text,
          "entries past the limit are counted, with the list command", text[-400:])
    output = io.StringIO()
    with redirect_stdout(output):
        exit_code = listing.main(["list", "--agent-seat", "seat-a", "--repo", str(main)])
    printed = output.getvalue()
    missing = [number for number in range(listing.ENTRIES_AT_MOST + 2)
               if f"branch many-{number:02d};" not in printed]
    check(exit_code == 0 and not missing and "more; list them all with:" not in printed,
          "the list command the first prompt names prints every entry past the limit",
          (exit_code, missing))


def test_more_worktrees_than_the_limit():
    main = new_clone()
    set_pull_requests([])
    count = listing.ENTRIES_AT_MOST + 2
    for number in range(count):
        owned_worktree(main, f"wt-{number:02d}", {"owner_kind": "agent-seat", "agent_seat": "seat-a"})
    text = listing.first_prompt_text(main, "seat-a")
    shown = [line for line in text.splitlines() if line.startswith("- worktree ")]
    check(f"worktrees: {count}:" in text and len(shown) == listing.ENTRIES_AT_MOST
          and "- and 2 more; list them all with:" in text,
          "worktrees past the limit are counted, with the list command", text[:600])
    output = io.StringIO()
    with redirect_stdout(output):
        exit_code = listing.main(["list", "--agent-seat", "seat-a", "--repo", str(main)])
    printed = output.getvalue()
    listed = [line for line in printed.splitlines() if line.startswith("- worktree ")]
    check(exit_code == 0 and len(listed) == count and "more; list them all with:" not in printed,
          "the list command prints every worktree past the limit", (exit_code, len(listed)))


def cherry_picked_branch(main, branch, author):
    """A branch of author's whose one commit is also on origin/main as a cherry-picked copy."""
    tip = branch_with_commit(main, branch, author)
    git(main, "checkout", "-q", "-B", "landing", "origin/main")
    # A commit of main's own first, so the copy cannot come out with the branch commit's hash.
    (main / "landing.txt").write_text("landing\n")
    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "landing")
    git(main, "cherry-pick", tip)
    git(main, "push", "-q", "origin", "HEAD:main")
    git(main, "fetch", "-q", "origin")
    git(main, "checkout", "-q", "--detach")
    git(main, "branch", "-D", "landing")
    return tip


def test_cherry_picked_copies_deleted():
    main = new_clone()
    set_pull_requests([])
    tip = cherry_picked_branch(main, "seat-a-copied", "seat-a")
    branch_with_commit(main, "seat-a-unique", "seat-a")
    listed, failed = listing.list_text_and_failure(main, "seat-a")
    check(not failed and "branch seat-a-copied;" in listed
          and git(main, "branch", "--list", "seat-a-copied") != "",
          "the list command deletes nothing: a cherry-picked copy is listed", listed)
    text = listing.first_prompt_text(main, "seat-a")
    restore = shlex.join(["git", "-C", str(main), "branch", "seat-a-copied", tip])
    check("branch seat-a-copied;" not in text and git(main, "branch", "--list", "seat-a-copied") == ""
          and f"- deleted branch seat-a-copied, whose every commit is on origin/main as a "
              f"cherry-picked copy; restore it with: {restore}" in text,
          "the first prompt deletes a branch whose every commit is a copy on origin/main, and "
          "names it with the command that restores it", text)
    check("branch seat-a-unique;" in text,
          "a branch with a commit origin/main lacks is still listed", text)
    restored = subprocess.run(shlex.split(restore), capture_output=True, text=True)
    check(restored.returncode == 0 and git(main, "rev-parse", "seat-a-copied") == tip,
          "the restore command brings the branch back at its tip", restored.stderr)
    saved = cleaner.run_git

    def refuse_branch_deletion(repo, *arguments, **keywords):
        if arguments[:2] == ("branch", "-D"):
            return subprocess.CompletedProcess(arguments, 1, "", "error: stand-in refusal")
        return saved(repo, *arguments, **keywords)

    cleaner.run_git = refuse_branch_deletion
    try:
        text = listing.first_prompt_text(main, "seat-a")
    finally:
        cleaner.run_git = saved
    check("branch seat-a-copied;" in text and "`git branch -D` exited 1: error: stand-in refusal"
          in text and git(main, "branch", "--list", "seat-a-copied") != "",
          "a branch whose deletion fails is listed, with why", text)


def test_merge_commit_branch_not_deleted():
    main = new_clone()
    set_pull_requests([])
    tip = cherry_picked_branch(main, "seat-a-merged", "seat-a")
    path = main.parent / "tmp-merge"
    git(main, "worktree", "add", "-q", str(path), "seat-a-merged")
    # origin/main~1, not origin/main: merging the copy in would hide it from `git cherry`.
    git(path, "merge", "-q", "--no-ff", "-m", "merge landing", "origin/main~1", author="seat-a")
    # An edit made inside the merge commit, as a hand resolution of a conflict is: work that
    # origin/main lacks and that `git cherry` never shows.
    (path / "tracked.txt").write_text("resolved by hand\n")
    git(path, "commit", "-q", "-a", "--amend", "--no-edit", author="seat-a")
    merged_tip = git(path, "rev-parse", "HEAD")
    git(main, "worktree", "remove", str(path))
    check(merged_tip != tip and git(main, "cherry", "origin/main", merged_tip).startswith("-")
          and "+" not in git(main, "cherry", "origin/main", merged_tip),
          "the scratch branch's only commit not on origin/main that `git cherry` sees is a copy",
          git(main, "cherry", "-v", "origin/main", merged_tip))
    text = listing.first_prompt_text(main, "seat-a")
    check("branch seat-a-merged;" in text and git(main, "branch", "--list", "seat-a-merged") != "",
          "a branch with a merge commit origin/main lacks is listed, not deleted", text)


def test_deletion_reported_when_a_later_git_call_fails():
    main = new_clone()
    set_pull_requests([])
    tip = cherry_picked_branch(main, "seat-a-copied", "seat-a")
    branch_with_commit(main, "seat-a-zz-unique", "seat-a")
    saved = cleaner.run_git

    def fail_after_deleting(repo, *arguments, **keywords):
        if arguments[:1] == ("log",):
            return subprocess.CompletedProcess(arguments, 128, "", "fatal: stand-in failure")
        return saved(repo, *arguments, **keywords)

    cleaner.run_git = fail_after_deleting
    try:
        text, failed = listing.list_text_and_failure(main, "seat-a",
                                                     delete_cherry_picked_copies=True)
    finally:
        cleaner.run_git = saved
    restore = shlex.join(["git", "-C", str(main), "branch", "seat-a-copied", tip])
    check(failed and git(main, "branch", "--list", "seat-a-copied") == ""
          and "could not be listed (ListingFailed" in text
          and f"restore it with: {restore}" in text,
          "a deletion is still reported, with its restore command, when a later git call fails",
          text)


def test_supervisor_puts_leftovers_before_the_next_step_without_a_conversation_tail():
    fixture_spec = importlib.util.spec_from_file_location(
        "handoff_supervisor_test_fixture_without_tail",
        SYSTEM_DIRECTORY / "tests" / "handoff-supervisor-test-fixture.py")
    fixture = importlib.util.module_from_spec(fixture_spec)
    fixture_spec.loader.exec_module(fixture)
    supervisor = fixture.supervisor
    counts = SCRATCH / "seat-y-leftovers-prompt-listing-counts.json"
    prompt = supervisor.IgnitionPlanWithoutConversationTail("Do the next thing.").compose(
        "launch-time-git-sync: test")
    branches = "This agent-seat's branches with no pull request: 1:\n- branch b1; main lacks the changes of its 1 commit(s)"
    launched = supervisor.launch_prompt_with_leftovers_before_the_next_step(
        prompt, ("", branches), counts)
    check(launched.index("branch b1;") < launched.index("Do the next thing.")
          and launched.endswith(f"{supervisor.NEXT_STEP_HEADING}Do the next thing."),
          "a prompt with no conversation-tail gets the leftovers before its next step", launched)
    no_step = supervisor.IgnitionPlanWithoutConversationTail("").compose("")
    check(supervisor.NEXT_STEP_HEADING not in no_step,
          "a prompt with no conversation-tail and no next step has no next-step heading", no_step)


def test_supervisor_puts_leftovers_before_the_next_step():
    fixture_spec = importlib.util.spec_from_file_location(
        "handoff_supervisor_test_fixture_leftovers",
        SYSTEM_DIRECTORY / "tests" / "handoff-supervisor-test-fixture.py")
    fixture = importlib.util.module_from_spec(fixture_spec)
    fixture_spec.loader.exec_module(fixture)
    supervisor = fixture.supervisor
    counts = SCRATCH / "seat-x-leftovers-prompt-listing-counts.json"
    prompt = f"Opening.{supervisor.NEXT_STEP_HEADING}Do the next thing."
    branches = "This agent-seat's branches with no pull request: 1:\n- branch b1; main lacks the changes of its 1 commit(s)\nSteps."
    snapshots = "Leftover work-snapshots: 1:\n- refs/work-snapshots/k/w: worktree /x (is gone); more"
    first = supervisor.launch_prompt_with_leftovers_before_the_next_step(
        prompt, (snapshots, branches), counts)
    check(first.startswith("Opening.\n\n" + supervisor.LEFTOVERS_BEFORE_THE_NEXT_STEP_SENTENCE)
          and first.endswith(f"Steps.{supervisor.NEXT_STEP_HEADING}Do the next thing."),
          "the leftovers go between the opening and the next step", first)
    check("- (listed in 1 first prompt(s)) branch b1;" in first
          and "- (listed in 1 first prompt(s)) refs/work-snapshots/k/w: worktree" in first,
          "each leftover entry opens with how many first prompts have listed it", first)
    second = supervisor.launch_prompt_with_leftovers_before_the_next_step(
        prompt, ("", branches), counts)
    check("- (listed in 2 first prompt(s)) branch b1;" in second
          and json.loads(counts.read_text()) == {"branch b1": 2},
          "a leftover listed again counts up, and one no longer listed is dropped", second)
    check(supervisor.launch_prompt_with_leftovers_before_the_next_step(prompt, ("", ""), counts)
          == prompt, "with no leftovers the prompt is unchanged")
    no_next_step = supervisor.launch_prompt_with_leftovers_before_the_next_step(
        "Resume.", ("", branches), counts)
    check(no_next_step.startswith("Resume.\n\n" + supervisor.LEFTOVERS_BEFORE_THE_NEXT_STEP_SENTENCE),
          "a prompt with no next step gets the leftovers after it", no_next_step)
    counts.write_text("not json")
    broken = supervisor.launch_prompt_with_leftovers_before_the_next_step(
        prompt, ("", branches), counts)
    check("- branch b1;" in broken and "could not be counted" in broken and "JSONDecodeError" in broken,
          "an unreadable counts file is stated, and the entries are still listed", broken)


def test_supervisor_puts_deleted_branches_above_the_leftovers_and_forgets_counts_when_none():
    fixture_spec = importlib.util.spec_from_file_location(
        "handoff_supervisor_test_fixture_deleted_and_counts",
        SYSTEM_DIRECTORY / "tests" / "handoff-supervisor-test-fixture.py")
    fixture = importlib.util.module_from_spec(fixture_spec)
    fixture_spec.loader.exec_module(fixture)
    supervisor = fixture.supervisor
    counts = SCRATCH / "seat-w-leftovers-prompt-listing-counts.json"
    prompt = f"Opening.{supervisor.NEXT_STEP_HEADING}Do the next thing."
    deleted = "\n".join(listing.deleted_section(["deleted branch d1, whose every commit is a copy"]))
    branches = ("This agent-seat's branches with no pull request: 1:\n- branch b1; main lacks the changes of its 1 commit(s)\nSteps.\n"
                + deleted)
    both = supervisor.launch_prompt_with_leftovers_before_the_next_step(prompt, ("", branches), counts)
    check(both.startswith("Opening.\n\n" + listing.ALREADY_DELETED_HEADING_START)
          and both.index("- deleted branch d1,")
          < both.index(supervisor.LEFTOVERS_BEFORE_THE_NEXT_STEP_SENTENCE)
          < both.index("- (listed in 1 first prompt(s)) branch b1;")
          and both.endswith(f"Steps.{supervisor.NEXT_STEP_HEADING}Do the next thing."),
          "the deleted branches go above the leftovers' opening sentence", both)
    only_deleted = supervisor.launch_prompt_with_leftovers_before_the_next_step(
        prompt, ("", deleted), counts)
    check(only_deleted == f"Opening.\n\n{deleted}{supervisor.NEXT_STEP_HEADING}Do the next thing."
          and not counts.exists(),
          "with only deleted branches, no leftovers sentence is shown and the counts file is deleted",
          only_deleted)
    again = supervisor.launch_prompt_with_leftovers_before_the_next_step(prompt, ("", branches), counts)
    check("- (listed in 1 first prompt(s)) branch b1;" in again,
          "a leftover listed after a launch that listed none starts its count again", again)
    quoting = ("This agent-seat's branches with no pull request: 2:\n"
               f"- branch b2; main lacks the changes of its 1 commit(s), the newest \"Move the {listing.ALREADY_DELETED_HEADING_START} "
               "heading\"\n- branch b3; main lacks the changes of its 1 commit(s)\nSteps.\n" + deleted)
    quoted = supervisor.launch_prompt_with_leftovers_before_the_next_step(prompt, ("", quoting), counts)
    check("- (listed in 1 first prompt(s)) branch b2;" in quoted
          and "- (listed in 1 first prompt(s)) branch b3;" in quoted
          and quoted.index("- deleted branch d1,")
          < quoted.index(supervisor.LEFTOVERS_BEFORE_THE_NEXT_STEP_SENTENCE),
          "a commit subject quoting the deleted branches' heading does not start the deleted block",
          quoted)
    counts.unlink()
    counts.mkdir()
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        unchanged = supervisor.launch_prompt_with_leftovers_before_the_next_step(prompt, ("", ""), counts)
    check(unchanged == prompt and "could not delete" in stderr.getvalue()
          and str(counts) in stderr.getvalue(),
          "a counts file that cannot be deleted is reported on the console", stderr.getvalue())
    counts.rmdir()


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
        supervisor.first_prompt_from_launch_command_marked_not_typed_by_the_user("Founding prompt.")
        + "\n\n" + supervisor.LEFTOVERS_BEFORE_THE_NEXT_STEP_SENTENCE
        + "\n\nThis agent-seat's branches with no pull request: 1:\n"
        "- (listed in 1 first prompt(s)) branch seat-five-work;")
          and supervisor.leftover_prompt_listing_counts_path(handoffs, "seat-five").exists(),
          "a launch's prompt with no next step carries the leftovers after it, counted",
          launched[:1] and launched[0][:400])


def task_list(agent_seat, tasks):
    """Write tasks, {id: (status, metadata or None) or raw text}, as the agent-seat's task list."""
    # Path.home(), not HOME: the handoff-supervisor case loads a module that moves HOME.
    directory = Path.home() / ".claude" / "tasks" / f"nedschorus-{agent_seat}-tasks"
    shutil.rmtree(directory, ignore_errors=True)
    directory.mkdir(parents=True)
    for task_id, task in tasks.items():
        if isinstance(task, str):
            (directory / f"{task_id}.json").write_text(task, encoding="utf-8")
            continue
        status, metadata = task
        record = {"id": task_id, "subject": f"task {task_id}", "description": "", "status": status,
                  "blocks": [], "blockedBy": []}
        if metadata is not None:
            record["metadata"] = metadata
        (directory / f"{task_id}.json").write_text(json.dumps(record), encoding="utf-8")
    return directory


def test_open_tasks_hold_entries():
    main = new_clone()
    set_pull_requests([])
    held_worktree = owned_worktree(main, "seat-t-held-tree", {"owner_kind": "agent-seat",
                                                              "agent_seat": "seat-t"})
    by_branch_worktree = owned_worktree(main, "seat-t-tree-by-branch",
                                        {"owner_kind": "agent-seat", "agent_seat": "seat-t"})
    free_worktree = owned_worktree(main, "seat-t-free-tree", {"owner_kind": "agent-seat",
                                                              "agent_seat": "seat-t"})
    for branch in ("seat-t-held-1", "seat-t-held-2", "seat-t-done", "seat-t-free"):
        branch_with_commit(main, branch, "seat-t")
    copied_tip = cherry_picked_branch(main, "seat-t-held-copy", "seat-t")
    task_list("seat-t", {
        "135": ("in_progress", {"branches": [str(held_worktree), "seat-t-held-1"]}),
        "9": ("pending", {"branches": ["seat-t-held-2", "seat-t-tree-by-branch"],
                          "prerequisites": [{"pr_merged": 1}]}),
        "20": ("pending", {"branches": ["seat-t-held-copy"]}),
        "40": ("completed", {"branches": ["seat-t-done", str(free_worktree)]}),
        "41": ("pending", None),
    })
    text = listing.first_prompt_text(main, "seat-t")
    check("This agent-seat also has 2 worktrees and 3 branches that open tasks hold "
          "(tasks 9, 20, 135); they are not listed." in text,
          "the entries open tasks hold are counted in one line naming the tasks in number order",
          text)
    check(str(held_worktree) not in text and str(by_branch_worktree) not in text,
          "a worktree an open task names by its path or by its branch is left out", text)
    check("seat-t-held-1" not in text and "seat-t-held-2" not in text,
          "a branch an open task names is left out", text)
    check("seat-t-held-copy" not in text
          and git(main, "rev-parse", "seat-t-held-copy") == copied_tip,
          "a branch an open task holds is not deleted as a cherry-picked copy", text)
    check(f"worktree {free_worktree};" in text and "branch seat-t-done;" in text
          and "branch seat-t-free;" in text,
          "an entry only a completed task names, or none, is listed", text)
    check("worktrees: 1:" in text and "branches with no pull request: 2:" in text
          and listing.INSTRUCTIONS in text,
          "the sections count only the entries listed", text)
    check("could not be read" not in text, "a readable task list says nothing of reading", text)


def test_open_task_names_a_worktree_by_a_path_written_differently():
    main = new_clone()
    set_pull_requests([])
    record = {"owner_kind": "agent-seat", "agent_seat": "seat-w"}
    by_dots = owned_worktree(main, "seat-w-by-dots", record)
    by_slash = owned_worktree(main, "seat-w-by-slash", record)
    by_link = owned_worktree(main, "seat-w-by-link", record)
    link = SCRATCH / f"link-to-{main.parent.name}"
    link.symlink_to(main.parent)
    task_list("seat-w", {"5": ("pending", {"branches": [
        str(by_dots.parent / "absent" / ".." / by_dots.name),
        str(by_slash) + "/",
        str(link / by_link.name),
    ]})})
    text = listing.first_prompt_text(main, "seat-w")
    check(all(str(path) not in text for path in (by_dots, by_slash, by_link))
          and "This agent-seat also has 3 worktrees" in text,
          "a worktree an open task names by a path with .., a trailing slash or a symlink is left out",
          text)


def test_hidden_line_counts():
    check(listing.hidden_line([]) == "", "nothing hidden prints no line")
    check(listing.hidden_line([("branch", {"5"})])
          == "This agent-seat also has 1 branch that open tasks hold (task 5); they are not listed.",
          "a category whose count is zero is left out, and one entry is singular")
    check(listing.hidden_line([("worktree", {"3"}), ("worktree", {"3", "x"})])
          == "This agent-seat also has 2 worktrees that open tasks hold (tasks 3, x); "
             "they are not listed.",
          "task ids are listed once each, numbers before other ids")


def test_everything_held():
    main = new_clone()
    set_pull_requests([])
    branch_with_commit(main, "seat-u-only", "seat-u")
    task_list("seat-u", {"7": ("pending", {"branches": ["seat-u-only"]})})
    text, failed = listing.list_text_and_failure(main, "seat-u")
    check(not failed and text == "This agent-seat also has 1 branch that open tasks hold "
          "(task 7); they are not listed.",
          "when open tasks hold every entry, only their line is printed", text)


def test_unreadable_task_list_hides_nothing():
    main = new_clone()
    set_pull_requests([])
    branch_with_commit(main, "seat-v-held", "seat-v")
    branch_with_commit(main, "seat-v-other", "seat-v")
    directory = task_list("seat-v", {"1": "{not json", "2": ("pending", {"branches": "seat-v-held"}),
                                     "3": ("pending", {"branches": ["seat-v-other"]})})
    text, failed = listing.list_text_and_failure(main, "seat-v")
    check(not failed and "branch seat-v-held;" in text,
          "an entry no readable task holds is listed", text)
    check("(task 3)" in text and "branch seat-v-other;" not in text,
          "a readable task still holds its entry", text)
    check(text.count("could not be read in full") == 1 and str(directory / "1.json") in text
          and str(directory / "2.json") in text,
          "the list says once that the task list could not be read, naming each file", text)
    directory.chmod(0)
    try:
        text, failed = listing.list_text_and_failure(main, "seat-v")
    finally:
        directory.chmod(0o755)
    check(not failed and "branch seat-v-other;" in text and "branch seat-v-held;" in text
          and f"task list could not be read in full (PermissionError: no permission to read "
              f"{directory})" in text,
          "a task list directory that cannot be read hides nothing and says so", text)
    saved = listing.due_task_raise_hook_module
    listing.due_task_raise_hook_module = lambda: (_ for _ in ()).throw(OSError("stand-in"))
    try:
        text, failed = listing.list_text_and_failure(main, "seat-v")
    finally:
        listing.due_task_raise_hook_module = saved
    check(not failed and "branch seat-v-other;" in text
          and "task list could not be read in full (OSError: stand-in)" in text,
          "a task list reader that fails hides nothing and says so", text)


for case in (test_branches, test_pushed_text, test_worktrees, test_gh_failure,
             test_other_failure_and_outside, test_more_than_the_limit,
             test_more_worktrees_than_the_limit, test_cherry_picked_copies_deleted,
             test_merge_commit_branch_not_deleted,
             test_deletion_reported_when_a_later_git_call_fails,
             test_supervisor_puts_leftovers_before_the_next_step,
             test_supervisor_puts_deleted_branches_above_the_leftovers_and_forgets_counts_when_none,
             test_supervisor_puts_leftovers_before_the_next_step_without_a_conversation_tail,
             test_supervisor_appends_the_list, test_open_tasks_hold_entries,
             test_open_task_names_a_worktree_by_a_path_written_differently,
             test_hidden_line_counts, test_everything_held,
             test_unreadable_task_list_hides_nothing):
    print(f"-- {case.__name__}")
    case()
    os.environ.pop("FAKE_GH_PULL_REQUESTS", None)

print(f"{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
