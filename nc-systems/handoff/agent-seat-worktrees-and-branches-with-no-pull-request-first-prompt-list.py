#!/usr/bin/env python3
"""The first prompt's list of an agent-seat's worktrees and of its branches with no pull request.

nc-systems/handoff/handoff-supervisor.py appends this list to the first prompt
of every agent-session it starts, so that work an earlier agent-session left
behind is carried on or deleted instead of forgotten. Building the list is
code; whether to keep or delete each entry is the agent-session's judgment.

WHAT IS LISTED.
- A worktree, when its owner file (scripts/worktree-owner-file-read-and-write.py)
  names this agent-seat, other than the directory the agent-session starts in
  and a worktree whose owning agent-session's `claude` process still runs.
  A worktree with no owner file, or one that cannot be read, is not listed;
  scripts/clean-worktrees.py reports those in its daily count line.
- A local branch, when no worktree has it checked out, its tip commit is not
  on origin/main, the tip commit's author name is this agent-seat's name (the
  launchers set GIT_AUTHOR_NAME to it), and no pull request of any state has
  the branch as its head branch or the tip commit as its head commit. A
  branch whose tip author is no agent-seat, such as the user or
  unconfigured-agent, is in no agent-seat's list; the cleaner's count line
  counts it among the branches with no pull request.

origin/main is read as it is on disk: the handoff-supervisor fetches just
before it builds the prompt.

HOW IT CAN FAIL. When gh cannot list pull requests, worktrees are listed with
their pull request state unknown and the branch list is replaced by a line
saying why, with the command below; any other failure replaces the whole list
with a line saying why, with the same command, so a failure is never read as
an empty list. It reads only; it deletes nothing.

Usage:
  agent-seat-worktrees-and-branches-with-no-pull-request-first-prompt-list.py
      list --agent-seat NAME [--repo PATH] [--skip-worktree PATH]
      prints the list, or nothing when there is nothing to list; exit 0,
      1 when part of it could not be built
"""

import argparse
import importlib.util
import os
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve()
REPO_ROOT = MODULE_PATH.parent.parent.parent
CLEAN_WORKTREES_PATH = REPO_ROOT / "scripts" / "clean-worktrees.py"

ENTRIES_AT_MOST = 20
MAIN_BRANCH = "main"
ORIGIN_MAIN = "origin/main"

_clean_worktrees = None


def clean_worktrees_module():
    """scripts/clean-worktrees.py as a module, loaded on first use, for its worktree, owner-file
    and pull request listing."""
    global _clean_worktrees
    if _clean_worktrees is None:
        spec = importlib.util.spec_from_file_location("clean_worktrees", CLEAN_WORKTREES_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _clean_worktrees = module
    return _clean_worktrees


class ListingFailed(Exception):
    """A git command the list needs failed."""


def git_lines(repo, *arguments):
    result = clean_worktrees_module().run_git(repo, *arguments)
    if result.returncode != 0:
        raise ListingFailed(f"`git {' '.join(arguments)}` exited {result.returncode}: "
                            f"{' '.join(result.stderr.split())[:200] or 'no error text'}")
    return result.stdout.splitlines()


def list_command_text(agent_seat):
    return f"python3 {MODULE_PATH} list --agent-seat {agent_seat}"


def pull_requests_or_failure(repo):
    """Return ({head branch: [pull request]}, {head commit: pull request}, None), or
    (None, None, why gh could not list them)."""
    cleaner = clean_worktrees_module()
    try:
        by_head_branch = cleaner.list_all_pull_requests_grouped_by_head_branch(repo)
    except cleaner.PullRequestListingFailed as error:
        return None, None, str(error)
    by_head_commit = {pull_request["headRefOid"]: pull_request
                      for pull_requests in by_head_branch.values()
                      for pull_request in pull_requests}
    return by_head_branch, by_head_commit, None


def pull_request_for(branch, tip, by_head_branch, by_head_commit):
    """The newest pull request whose head branch is the branch, else one whose head commit is
    the tip, else None."""
    candidates = by_head_branch.get(branch, []) if branch else []
    if candidates:
        return max(candidates, key=lambda pull_request: pull_request["number"])
    return by_head_commit.get(tip)


def owned_worktree_entries(repo, agent_seat, skip_worktree, by_head_branch, by_head_commit):
    """Return the entry text of each worktree this agent-seat's owner file names."""
    cleaner = clean_worktrees_module()
    owner_file = cleaner.owner_file
    main_checkout = cleaner.main_checkout_of(repo)
    if main_checkout is None:
        raise ListingFailed(f"git cannot find the primary checkout of {repo}")
    skipped = Path(skip_worktree).resolve() if skip_worktree else None
    entries = []
    for worktree, branch, record in cleaner.list_worktrees(repo, main_checkout):
        if skipped is not None and worktree.resolve() == skipped:
            continue
        try:
            owner = owner_file.worktree_owner_file_read(worktree)
        except owner_file.WorktreeOwnerFileError:
            continue
        if owner is None or owner.get("agent_seat") != agent_seat:
            continue
        if owner["owner_kind"] == owner_file.OWNER_AGENT_SESSION:
            state, _ = owner_file.worktree_owner_running_state(owner)
            if state == owner_file.RUNNING:
                continue
        tip = record.head or ""
        if by_head_branch is None:
            pull_request_text = "pull request state unknown"
        else:
            pull_request = pull_request_for(branch, tip, by_head_branch, by_head_commit)
            pull_request_text = (cleaner.pull_request_text(pull_request) if pull_request
                                 else "no pull request")
        entries.append(f"worktree {worktree}; branch {branch or 'none (detached HEAD)'}; "
                       f"{pull_request_text}")
    return entries


def checked_out_branches(repo):
    cleaner = clean_worktrees_module()
    listing = cleaner.git_output.run_git(repo, ["worktree", "list", "--porcelain", "-z"])
    return {record.branch[len("refs/heads/"):]
            for record in cleaner.git_output.worktree_records(listing)
            if record.branch is not None and record.branch.startswith("refs/heads/")}


def origin_branch_tips(repo):
    tips = {}
    for line in git_lines(repo, "for-each-ref", "--format=%(refname:lstrip=3)%00%(objectname)",
                          "refs/remotes/origin/"):
        name, _, tip = line.partition("\0")
        tips[name] = tip
    return tips


def pushed_text(branch, tip, origin_tips):
    if branch not in origin_tips:
        return "not on origin"
    if origin_tips[branch] == tip:
        return "on origin at the same commit"
    return "on origin at a different commit"


def owned_branch_entries(repo, agent_seat, by_head_branch, by_head_commit):
    """Return the entry text of each branch with no pull request whose tip this agent-seat wrote."""
    attached = checked_out_branches(repo)
    origin_tips = origin_branch_tips(repo)
    entries = []
    # lstrip=2, not :short, which reads heads/<name> when a tag has the branch's name.
    for line in git_lines(repo, "for-each-ref", f"--no-merged={ORIGIN_MAIN}",
                          "--format=%(refname:lstrip=2)%00%(objectname)%00%(authorname)"
                          "%00%(authordate:short)", "refs/heads/"):
        branch, tip, author, date = line.split("\0")
        if branch == MAIN_BRANCH or branch in attached or author != agent_seat:
            continue
        if pull_request_for(branch, tip, by_head_branch, by_head_commit) is not None:
            continue
        count = git_lines(repo, "rev-list", "--count", f"{ORIGIN_MAIN}..{tip}")[0]
        entries.append(f"branch {branch}; {count} commit(s) not on origin/main, the newest "
                       f"{tip[:12]} of {date}; {pushed_text(branch, tip, origin_tips)}")
    return entries


INSTRUCTIONS = """\
Each is listed because it belongs to this agent-seat: a worktree because its owner file names this agent-seat, a branch because this agent-seat wrote its newest commit not on origin/main and no pull request has it as its head. An earlier agent-session left each one. Before your other work, decide for each whether you will carry it on:
- If you will, carry it on, or say in your session-handoff who will.
- A worktree whose branch has an open pull request is still in use: keep it; scripts/clean-worktrees.py removes it after the pull request closes.
- If you will not, read what it holds first: `git -C <worktree> status` and `git log origin/main..<branch>`. Then remove a worktree with `git worktree remove <worktree>` and delete a branch with `git branch -D <branch>`. A branch "not on origin" loses its commits when deleted.
Tell the user in your next message which you kept and which you removed."""


def section(heading, entries, agent_seat):
    lines = [heading]
    lines.extend(f"- {entry}" for entry in entries[:ENTRIES_AT_MOST])
    rest = len(entries) - ENTRIES_AT_MOST
    if rest > 0:
        lines.append(f"- and {rest} more; list them all with: {list_command_text(agent_seat)}")
    return lines


def list_text_and_failure(repo, agent_seat, skip_worktree=None):
    """Return (the list's text, or "" when there is nothing to list; whether part failed)."""
    cleaner = None
    try:
        cleaner = clean_worktrees_module()
        inside = cleaner.git_output.run_git_unless_outside_a_repository(
            repo, ["rev-parse", "--git-dir"])
        if inside is None:
            # Worktrees and branches live in a clone; a directory outside any has none.
            return "", False
        by_head_branch, by_head_commit, pull_request_failure = pull_requests_or_failure(repo)
        worktrees = owned_worktree_entries(repo, agent_seat, skip_worktree,
                                           by_head_branch, by_head_commit)
        branches = ([] if pull_request_failure else
                    owned_branch_entries(repo, agent_seat, by_head_branch, by_head_commit))
    except Exception as error:
        return (f"This agent-seat's worktrees and branches with no pull request could not be "
                f"listed ({type(error).__name__}: {error}). Work an earlier agent-session left "
                f"may be waiting; list it with: {list_command_text(agent_seat)}"), True
    if not worktrees and not branches and not pull_request_failure:
        return "", False
    lines = []
    if worktrees:
        lines += section(f"This agent-seat's worktrees: {len(worktrees)}:", worktrees, agent_seat)
    if pull_request_failure:
        lines.append(f"This agent-seat's branches with no pull request could not be listed, "
                     f"because gh could not list the pull requests ({pull_request_failure}); "
                     f"list them with: {list_command_text(agent_seat)}")
    elif branches:
        lines += section(f"This agent-seat's branches with no pull request: {len(branches)}:",
                         branches, agent_seat)
    if worktrees or branches:
        lines.append(INSTRUCTIONS)
    return "\n".join(lines), bool(pull_request_failure)


def first_prompt_text(repo, agent_seat, skip_worktree=None):
    """The first prompt's paragraph on this agent-seat's worktrees and branches with no pull
    request; empty when there are none. A failure is stated, never left as an empty list."""
    return list_text_and_failure(repo, agent_seat, skip_worktree)[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list")
    listing.add_argument("--agent-seat", required=True)
    listing.add_argument("--repo", default=os.getcwd())
    listing.add_argument("--skip-worktree")
    arguments = parser.parse_args(argv)
    text, failed = list_text_and_failure(arguments.repo, arguments.agent_seat,
                                         arguments.skip_worktree)
    if text:
        print(text)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
