#!/usr/bin/env python3
"""Write an owner file, once, into each existing worktree of this machine's clone that lacks one
and whose owner this program can tell, as WHICH WORKTREES below says, so that
scripts/clean-worktrees.py can judge the worktree. Run this program once on each machine after the git
post-checkout hook scripts/git-client-side-hooks/post-checkout, which writes the owner file of
every new worktree, has landed.

Without --write it prints what it would do and changes nothing. With --write it writes the owner
files, through scripts/worktree-owner-file-read-and-write.py, which never replaces one. --repo
PATH names the clone by any of its checkouts; without it, the program handles the clone that
holds this program.

WHICH WORKTREES. The owner file is worktree-owner.json, the record that
scripts/worktree-owner-file-read-and-write.py describes. The agents root is ~/agents, or
$NEDSCHORUS_AGENTS_ROOT when set on the Mac. The agent-seats are those whose agent-home is a
directory directly under the agents root and that have a handoff-supervisor state file or a
session-handoff file in ~/.claude/handoffs/, as scripts/recover-crashed-seats.py lists them.

Each worktree of the clone with no owner file is handled as follows:

  - Skipped silently: the reference-checkout; each agent-home, <agents root>/<agent-seat>; and
    each merge-lane review checkout directly inside ~/.cache/merge-lane-review-worktrees.
    scripts/clean-worktrees.py removes a review checkout after its pull request has merged or
    closed, so a review checkout needs no owner file.
  - Given no owner file, and named on a line of its own but not listed for the user to keep or
    delete: a Claude Code subagent's worktree, directly inside .claude/worktrees/ of the
    reference-checkout and named agent-a followed by 16 lowercase hex digits, Claude Code's name
    for it, while it is locked with `git worktree lock`, whether or not the lock's claude process
    runs. Its line says what scripts/clean-worktrees.py --remove does with it now: keeps it, and
    why, or unlocks it, and whether it first writes an owner file.
  - Given an owner file naming an agent-seat: an unlocked Claude Code subagent's worktree, when
    the Claude Code transcripts of exactly one agent-seat name its subagent, agent-<id> for the
    directory agent-<id>, as agent_seats_whose_claude_code_transcripts_name_subagent in
    scripts/worktree-owner-file-read-and-write.py says which transcripts those are; that
    agent-seat is the owner.
  - Given an owner file naming an agent-seat: a worktree nested beneath an agent-home, or one
    that is, or lies beneath, a directory directly under the agents root named as an agent-seat's
    name followed by a hyphen and more. When several agent-seats' names fit, the
    owner is the agent-seat with the longest name. Examples: prime-intellect for
    ~/agents/prime-intellect-worktrees/<name>, reboot-test for ~/agents/reboot-test-d2m-wording.
  - Given no owner file, and listed for the user to keep or delete: every worktree the bullets
    above leave out, such as an unlocked Claude Code subagent's worktree whose subagent no
    agent-seat's transcripts name, or several agent-seats' do, restored-<name> inside the
    reference-checkout's .claude/worktrees/, or <agents root>/<name> when no agent-seat's name
    fits <name>.

FOR THE USER. Each worktree listed for the user is named on a line of its own with the facts that
decide whether to keep or delete it. To keep one, lock it with
git worktree lock --reason <why> <worktree>:
scripts/clean-worktrees.py removes a worktree with no owner file once nothing in it has changed for 2 days and it holds no uncommitted or untracked file. The facts are how many uncommitted, untracked or ignored files it holds, how many
commits its HEAD has that its branch's upstream lacks, or origin/main when the branch has no
upstream or the worktree is on a detached HEAD, and whether its branch is merged into origin/main,
as git reads origin/main without fetching, or that it is on a detached HEAD and has no branch. A
fact git cannot read is printed as unknown, with git's error. After the list come the two commands
that delete one such worktree, and its branch when it has one, <repo> being the clone this run
handled:

  scripts/worktree-owner-file-read-and-write.py write --agent-seat <agent-seat> --worktree <worktree>
  scripts/clean-worktrees.py --repo <repo> --remove-worktree-and-force-delete-its-branch <worktree>

The second command keeps a worktree with no owner file, so the first gives it one. <agent-seat> is
any agent-seat the user chooses: the second command copies the worktree's uncommitted and
untracked files to a work-snapshot before removing it, and that agent-seat's next agent-session is
told of the work-snapshot. The work-snapshot keeps no ignored file, so removing the worktree
deletes its ignored files for good.

A worktree whose owner file cannot be read, or cannot be written, is named on a FAILED line,
and the program exits 1 once it has handled every other worktree.

Usage:
  scripts/worktree-owner-file-one-time-backfill-for-existing-worktrees-with-none.py [--write] [--repo PATH]

Exit codes: 0 done, 1 a worktree's owner file could not be read or written, 2 bad invocation or
git could not list the worktrees.
"""

import importlib.util
import shlex
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



def agent_seat_whose_name_begins(directory_name, agent_seats):
    """The longest agent-seat name that is the directory name or begins it before a hyphen, or None."""
    matching = [seat for seat in agent_seats
                if directory_name == seat or directory_name.startswith(seat + "-")]
    return max(matching, key=len) if matching else None


def backfill_action(worktree, locked_reason, main_checkout, agents_root, agent_seats,
                    review_worktrees_directory):
    """Return (action, agent-seat or None, why) for a worktree with no owner file, whose
    `git worktree lock` reason is locked_reason, None when unlocked; action is "skip", "write",
    "subagent" or "for the user"."""
    worktree = worktree.resolve()
    if worktree.parent == review_worktrees_directory.resolve():
        return "skip", None, "a merge-lane review checkout"
    if owner_file.worktree_is_claude_code_subagent_worktree_by_location_and_directory_name(worktree, main_checkout):
        if locked_reason is not None:
            return "subagent", None, "a locked Claude Code subagent's worktree"
        agent_id = worktree.name.removeprefix("agent-")
        seats = owner_file.agent_seats_whose_claude_code_transcripts_name_subagent(agent_id,
                                                                                   agents_root)
        if len(seats) == 1:
            return "write", seats[0], (f"{seats[0]}'s Claude Code transcripts name its subagent "
                                       f"agent-{agent_id}")
        whose = ("no agent-seat's Claude Code transcripts name" if not seats
                 else f"the Claude Code transcripts of {len(seats)} agent-seats, "
                      f"{', '.join(seats)}, name")
        return "for the user", None, (f"it is an unlocked Claude Code subagent's worktree and "
                                      f"{whose} its subagent agent-{agent_id}")
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


def clean_worktrees_remove_of_locked_subagent_worktree_text(worktree, record):
    """What scripts/clean-worktrees.py --remove does now with a locked subagent's worktree."""
    verdict, ended = cleaner.claude_code_subagent_lock_verdict_or_ended_lock(worktree, record)
    if verdict is not None:
        return (f"scripts/clean-worktrees.py --remove keeps it, so nothing needs doing now: "
                f"{verdict.reason}")
    owner = ended.owner_to_write
    first = (f", first giving it an owner file naming the agent-seat {owner['agent_seat']}, whose "
             f"Claude Code transcripts name its subagent" if owner else "")
    return (f"the next scripts/clean-worktrees.py --remove unlocks it{first}, since "
            f"{ended.explanation}, then judges it like any other worktree")


def keep_or_delete_facts_text(repo, worktree, branch):
    """The facts FOR THE USER names beside a worktree listed for the user."""
    discarded, listing_error = cleaner.files_a_removal_discards(worktree)
    changes = (f"uncommitted, untracked or ignored files unknown ({listing_error})"
               if discarded is None
               else f"{len(discarded)} uncommitted, untracked or ignored file(s)")
    base = "origin/main"
    if branch is not None:
        upstream = cleaner.run_git(worktree, "rev-parse", "--abbrev-ref", "--symbolic-full-name",
                                   "HEAD@{upstream}")
        if upstream.returncode == 0:
            base = upstream.stdout.strip()
    ahead = cleaner.run_git(worktree, "rev-list", "--count", f"{base}..HEAD")
    commits = (f"{ahead.stdout.strip()} commit(s) {base} lacks" if ahead.returncode == 0
               else f"how many commits its HEAD has that {base} lacks is unknown (git rev-list exited "
                    f"{ahead.returncode}: {' '.join(ahead.stderr.split()) or 'no error text'})")
    if branch is None:
        merged = "on a detached HEAD, so no branch to merge"
    else:
        on_main, git_error = cleaner.branch_fully_on_origin_main_true_false_or_none_with_git_error(repo, branch)
        merged = (f"whether its branch {branch} is merged into origin/main is unknown ({git_error})"
                  if on_main is None
                  else f"its branch {branch} is {'' if on_main else 'not '}merged into origin/main")
    return f"{changes}; {commits}; {merged}"


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
    for worktree, branch, record in worktrees:
        try:
            if owner_file.worktree_owner_file_read(worktree) is not None:
                continue
        except owner_file.WorktreeOwnerFileError as error:
            print(f"{worktree}: FAILED, its owner file could not be read: {error}")
            failed.append(worktree)
            continue
        action, seat, why = backfill_action(worktree, record.locked_reason, main_checkout,
                                            agents_root, agent_seats, review_worktrees_directory)
        if action == "skip":
            continue
        if action == "subagent":
            print(f"{worktree}: given no owner file, since it is {why}; "
                  f"{clean_worktrees_remove_of_locked_subagent_worktree_text(worktree, record)}")
            continue
        if action == "for the user":
            print(f"{worktree}: given no owner file, since {why}; for the user to keep or delete: "
                  f"{keep_or_delete_facts_text(repo, worktree, branch)}")
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
        print(f"{len(for_the_user)} worktree(s) for the user to keep or delete, owned by no "
              f"agent-seat this program can tell: "
              + ", ".join(str(worktree) for worktree in for_the_user))
        print("To keep one, lock it with `git worktree lock --reason <why> <worktree>`: "
              "scripts/clean-worktrees.py removes a worktree with no owner file once nothing in "
              "it has changed for 2 days and it holds no uncommitted or untracked file.")
        print("To delete one with its branch, give it an owner file naming the agent-seat to be "
              "told of the work-snapshot that keeps its uncommitted files, then remove it:\n"
              f"  scripts/worktree-owner-file-read-and-write.py write --agent-seat <agent-seat> "
              f"--worktree <worktree>\n"
              f"  scripts/clean-worktrees.py --repo {shlex.quote(str(repo))} "
              f"{cleaner.REMOVE_WORKTREE_AND_FORCE_DELETE_ITS_BRANCH_COMMAND_LINE_FLAG} <worktree>")
    if failed:
        print(f"FAILED: the owner files of {len(failed)} worktree(s) could not be read or "
              f"written, as their lines above say: " + ", ".join(str(path) for path in failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
