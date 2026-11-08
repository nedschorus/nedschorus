#!/usr/bin/env python3
"""Give each existing worktree of this machine's clone that has no owner file one, once, so that
scripts/clean-worktrees.py can judge it; run it once on each machine after the git post-checkout
hook that writes the owner file of every new worktree has landed.

Without --write it prints what it would do and changes nothing. With --write it writes the owner
files, through scripts/worktree-owner-file-read-and-write.py, which never replaces one.

WHICH WORKTREES. Every worktree of the clone with no owner file, apart from:

  - the reference-checkout, the agent-homes, <agents root>/<agent-seat>, and the merge-lane
    review checkouts directly inside ~/.cache/merge-lane-review-worktrees, which the cleaner
    judges by their pull request: skipped silently;
  - a Claude Code subagent's worktree, directly inside .claude/worktrees/ of the reference-
    checkout and named agent-a followed by 16 lowercase hex digits, Claude Code's name for it:
    given none, and named on a line of its own. While Claude Code's lock is on it,
    scripts/clean-worktrees.py --remove gives it one once the lock's claude process has ended.
    Without the lock, the owner file would have to name the agent-session that dispatched the
    subagent, as the owner key of that agent-session's ended `claude` process, and no record
    kept on the machine holds that process's id and start, so this program cannot write it.

Each other worktree is given the agent-seat whose name begins the name of its directory directly
under the agents root, the longest such name when several do, as prime-intellect for
~/agents/prime-intellect-worktrees/<name> and reboot-test for ~/agents/reboot-test-d2m-wording.
An agent-seat is a directory under the agents root holding handoff records, as
scripts/recover-crashed-seats.py lists them. A worktree outside the agents root, or whose
directory there no agent-seat's name begins, is given none and listed for the user to keep or
delete; so is any other worktree inside .claude/worktrees/, such as restored-<name>.

A worktree whose owner file cannot be read, or cannot be written, is named on a FAILED line,
and the program exits 1 after the others.

Usage:
  scripts/worktree-owner-file-one-time-backfill-for-existing-worktrees-with-none.py [--write] [--repo PATH]

Exit codes: 0 done, 1 a worktree's owner file could not be read or written, 2 bad invocation or
git could not list the worktrees.
"""

import importlib.util
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_module(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cleaner = load_module("clean_worktrees", "scripts/clean-worktrees.py")
owner_file = cleaner.owner_file
recover_crashed_seats = owner_file.recover_crashed_seats_module()

CLAUDE_CODE_SUBAGENT_WORKTREES_DIRECTORY = Path(".claude") / "worktrees"
CLAUDE_CODE_SUBAGENT_WORKTREE_DIRECTORY_NAME = re.compile(r"agent-a[0-9a-f]{16}")


def agent_seat_whose_name_begins(directory_name, agent_seats):
    """The longest agent-seat name that is the directory name or begins it before a hyphen, or None."""
    matching = [seat for seat in agent_seats
                if directory_name == seat or directory_name.startswith(seat + "-")]
    return max(matching, key=len) if matching else None


def backfill_action(worktree, main_checkout, agents_root, agent_seats, review_worktrees_directory):
    """Return (action, agent-seat or None, why) for a worktree with no owner file; action is
    "skip", "write", "subagent" or "for the user"."""
    worktree = worktree.resolve()
    if worktree.parent == review_worktrees_directory.resolve():
        return "skip", None, "a merge-lane review checkout"
    if (worktree.parent == (main_checkout / CLAUDE_CODE_SUBAGENT_WORKTREES_DIRECTORY).resolve()
            and CLAUDE_CODE_SUBAGENT_WORKTREE_DIRECTORY_NAME.fullmatch(worktree.name)):
        return "subagent", None, "a Claude Code subagent's worktree"
    agents_root = agents_root.resolve()
    if worktree.parent == agents_root and worktree.name in agent_seats:
        return "skip", None, "an agent-home"
    try:
        top = worktree.relative_to(agents_root).parts[0]
    except ValueError:
        return "for the user", None, f"it is outside the agents root {agents_root}"
    seat = agent_seat_whose_name_begins(top, agent_seats)
    if seat is None:
        return "for the user", None, f"no agent-seat's name begins {top}"
    return "write", seat, f"{seat}'s name begins {top}"


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments in (["--help"], ["-h"]):
        print(__doc__)
        return 0
    repo = REPO_ROOT
    if "--repo" in arguments:
        position = arguments.index("--repo")
        if position + 1 >= len(arguments):
            print(__doc__, file=sys.stderr)
            return 2
        repo = Path(arguments[position + 1])
        del arguments[position:position + 2]
    write = arguments == ["--write"]
    if arguments not in ([], ["--write"]):
        print(__doc__, file=sys.stderr)
        return 2
    main_checkout = cleaner.main_checkout_of(repo)
    if main_checkout is None:
        print(f"worktree-owner-file backfill: {repo} is not a git repository", file=sys.stderr)
        return 2
    try:
        worktrees = cleaner.list_worktrees(repo, main_checkout)
    except cleaner.git_output.GitCommandFailed as error:
        print(f"worktree-owner-file backfill: git could not list the worktrees: {error}",
              file=sys.stderr)
        return 2
    agents_root = recover_crashed_seats.default_agents_root()
    agent_seats = set(recover_crashed_seats.list_agent_seat_names_with_agent_session_records(
        agents_root, recover_crashed_seats.default_handoff_directory()))
    review_worktrees_directory = (Path.home()
                                  / cleaner.merge_lane_common.REVIEW_WORKTREES_DIRECTORY_UNDER_HOME)
    failed = []
    for_the_user = []
    for worktree, _, _ in worktrees:
        try:
            if owner_file.worktree_owner_file_read(worktree) is not None:
                continue
        except owner_file.WorktreeOwnerFileError as error:
            print(f"{worktree}: FAILED, its owner file could not be read: {error}")
            failed.append(worktree)
            continue
        action, seat, why = backfill_action(worktree, main_checkout, agents_root, agent_seats,
                                            review_worktrees_directory)
        if action == "skip":
            continue
        if action == "subagent":
            print(f"{worktree}: given no owner file, as {why}: scripts/clean-worktrees.py --remove "
                  f"gives it one while Claude Code's lock is on it, once the lock's claude process "
                  f"has ended; without the lock no record holds the ended agent-session's claude "
                  f"process, which the owner file would name")
            continue
        if action == "for the user":
            print(f"{worktree}: given no owner file, since {why}; for the user to keep or delete")
            for_the_user.append(worktree)
            continue
        if not write:
            print(f"{worktree}: --write gives it an owner file naming the agent-seat {seat}, "
                  f"since {why}")
            continue
        try:
            owner_file.worktree_owner_file_write(worktree, owner_file.OWNER_AGENT_SEAT, seat)
        except owner_file.WorktreeOwnerFileError as error:
            print(f"{worktree}: FAILED, its owner file could not be written: {error}")
            failed.append(worktree)
            continue
        print(f"{worktree}: owner file written, naming the agent-seat {seat}, since {why}")
    if for_the_user:
        print(f"{len(for_the_user)} worktree(s) for the user to keep or delete, matching no "
              f"agent-seat: " + ", ".join(str(worktree) for worktree in for_the_user))
    if failed:
        print(f"FAILED: the owner files of {len(failed)} worktree(s) could not be read or "
              f"written, as their lines above say: " + ", ".join(str(path) for path in failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
