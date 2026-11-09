#!/usr/bin/env python3
"""The first prompt's list of an agent-seat's worktrees and of its branches with no pull request.

nc-systems/handoff/handoff-supervisor.py puts this list in the first prompt
of every agent-session it starts, before the next step, so that work an
earlier agent-session left behind is carried on or deleted instead of
forgotten. Building the list is code; whether to keep or delete each listed
entry is the agent-session's judgment. The first prompt's list also deletes,
without asking, the branches that the section WHAT IT DELETES below describes.

WHAT IS LISTED.
- A worktree, when its owner file (scripts/worktree-owner-file-read-and-write.py)
  names this agent-seat. Three such worktrees are left out: the directory the
  agent-session starts in; a worktree whose owning agent-session's `claude`
  process still runs; and a worktree with any open pull request, which
  merge-lane-2 reviews.
  A worktree with no owner file, or one that cannot be read, is not listed;
  scripts/clean-worktrees.py reports those in its daily count line.
- A local branch, when no worktree has it checked out, its tip commit is not
  on origin/main, the tip commit's author name is this agent-seat's name (the
  launchers set GIT_AUTHOR_NAME to it), and no pull request of any state has
  the branch as its head branch or the tip commit as its head commit. A
  branch whose tip author is no agent-seat, such as the user or
  unconfigured-agent, is in no agent-seat's list; the cleaner's count line
  counts it among the branches with no pull request.

WHAT AN OPEN TASK HOLDS IS LEFT OUT. A task on the agent-seat's task list,
~/.claude/tasks/nedschorus-<agent-seat>-tasks/, read with the due-task hook's
reader (scripts/agent-seat-due-task-raise-hook.py), may name in the
`branches` list of its metadata the branch names and worktree paths it holds.
An entry is left out when an open task (status pending or in_progress) names
it: a branch by its name, a worktree by its path or by the branch it has
checked out. A branch left out is never deleted as a cherry-picked copy, since
its task still names it. In place of the entries left out the list prints one
line counting them and naming their tasks. A task file that cannot be read,
or whose `branches` is not a list of strings, hides nothing, and the list
says once that the task list could not be read in full; so does a task list
directory that cannot be read.

Each branch entry gives how many commits origin/main lacks and the newest
one's subject. Beside each entry the list prints the command that deletes it:
scripts/clean-worktrees.py --remove-worktree-and-force-delete-its-branch for a
worktree, which ships the worktree's walks and records first, or
scripts/clean-worktrees.py --force-delete-branch for a branch. Both commands still refuse a worktree or
branch whose pull request is open, so one opened after the list was built is
kept.

origin/main is read as it is on disk: the handoff-supervisor fetches just
before it builds the prompt.

WHAT IT DELETES. Only the first prompt's list, never the list command, deletes
a branch it would list whose every commit is already on origin/main as a
cherry-picked copy (`git cherry origin/main <branch>` prints no `+` line, and
the branch has no merge commit origin/main lacks, since `git cherry` leaves
merge commits out): no work is lost, and the list names the branch with the `git branch <name>
<sha>` command that restores it, under a line that opens with the heading
"Already deleted, needing nothing from you:", which the handoff-supervisor
puts above the leftovers' opening sentence. A branch whose deletion fails is listed as
before, with why.

HOW IT CAN FAIL. When gh cannot list pull requests, worktrees are listed with
their pull request state unknown and the branch list is replaced by a line
saying why, with the command below; any other failure replaces the whole list
with a line saying why, with the same command, so a failure is never read as
an empty list; a branch deleted before the failure is still named below that
line, with the command that restores it.

Usage:
  agent-seat-worktrees-and-branches-with-no-pull-request-first-prompt-list.py
      list --agent-seat NAME [--repo PATH] [--skip-worktree PATH]
      prints the whole list, every entry, or nothing when there is nothing
      to list; exit 0, 1 when part of it could not be built. The first
      prompt shows at most ENTRIES_AT_MOST entries of each kind and points
      to this command for the rest.
"""

import argparse
import importlib.util
import os
import shlex
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve()
REPO_ROOT = MODULE_PATH.parent.parent.parent
CLEAN_WORKTREES_PATH = REPO_ROOT / "scripts" / "clean-worktrees.py"
DUE_TASK_RAISE_HOOK_PATH = REPO_ROOT / "scripts" / "agent-seat-due-task-raise-hook.py"
TASK_HELD_BRANCHES_METADATA_KEY = "branches"

ALREADY_DELETED_HEADING_START = "Already deleted, needing nothing from you:"
ENTRIES_AT_MOST = 20
# Every agent-session's first prompt waits on this listing, which took about 13 s for 2,239 pull
# requests; 60 s leaves room for the count to grow before a slow gh is cut off.
PULL_REQUEST_LISTING_TIMEOUT_SECONDS = 60
MAIN_BRANCH = "main"
ORIGIN_MAIN = "origin/main"

_clean_worktrees = None
_due_task_raise_hook = None


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


def due_task_raise_hook_module():
    """scripts/agent-seat-due-task-raise-hook.py as a module, loaded on first use, for its task
    list reader."""
    global _due_task_raise_hook
    if _due_task_raise_hook is None:
        spec = importlib.util.spec_from_file_location("agent_seat_due_task_raise_hook",
                                                      DUE_TASK_RAISE_HOOK_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _due_task_raise_hook = module
    return _due_task_raise_hook


class TasksHolding:
    """What the open tasks' `branches` fields name, {name or resolved path: {task id}}, and
    what in the task list could not be read."""

    def __init__(self, held=None, unreadable=None):
        self.held = held or {}
        self.unreadable = unreadable or []

    def holders(self, *names):
        """The ids of the open tasks whose `branches` field names any of names."""
        ids = set()
        for name in names:
            if name:
                ids.update(self.held.get(str(name), ()))
        return ids


def tasks_holding(agent_seat, task_list_directory=None):
    """Read the `branches` fields of the open tasks in task_list_directory, by default the
    agent-seat's own task list. Never raises: a list that cannot be read hides nothing and is
    reported in the result."""
    directory = task_list_directory
    unreadable = []
    held = {}
    try:
        hook = due_task_raise_hook_module()
        if directory is None:
            directory = Path.home() / hook.TASKS_ROOT_UNDER_HOME / f"nedschorus-{agent_seat}-tasks"
        directory = Path(directory)
        # read_tasks globs, and a glob of a directory it may not read finds nothing, silently.
        if directory.exists() and not os.access(directory, os.R_OK | os.X_OK):
            raise PermissionError(f"no permission to read {directory}")
        tasks = hook.read_tasks(directory, unreadable)
    except Exception as error:
        return TasksHolding(unreadable=[f"{type(error).__name__}: {error}"])
    for task_id, task in tasks.items():
        if task.get("status") not in hook.OPEN_TASK_STATUSES:
            continue
        metadata = task.get("metadata")
        names = metadata.get(TASK_HELD_BRANCHES_METADATA_KEY) if isinstance(metadata, dict) else None
        if names is None:
            continue
        if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
            unreadable.append(directory / f"{task_id}.json")
            continue
        for name in names:
            held.setdefault(name, set()).add(task_id)
            if os.path.isabs(name):
                held.setdefault(str(Path(name).resolve()), set()).add(task_id)
    return TasksHolding(held, [str(path) for path in unreadable])


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
        by_head_branch = cleaner.list_all_pull_requests_grouped_by_head_branch(
            repo, PULL_REQUEST_LISTING_TIMEOUT_SECONDS)
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


def owned_worktrees(repo, agent_seat, skip_worktree):
    """Return (path, branch or None, head commit) of each worktree this agent-seat's owner file
    names, other than skip_worktree and those whose owning agent-session still runs."""
    cleaner = clean_worktrees_module()
    owner_file = cleaner.owner_file
    main_checkout = cleaner.main_checkout_of(repo)
    if main_checkout is None:
        raise ListingFailed(f"git cannot find the primary checkout of {repo}")
    skipped = Path(skip_worktree).resolve() if skip_worktree else None
    worktrees = []
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
        worktrees.append((worktree, branch, record.head or ""))
    return worktrees


def delete_command_text(repo, flag, value):
    """The scripts/clean-worktrees.py command that removes one worktree or deletes one branch."""
    return shlex.join(["python3", str(CLEAN_WORKTREES_PATH), "--repo", str(repo), flag, str(value)])


def has_open_pull_request(branch, tip, by_head_branch):
    """Whether any pull request, not only the newest, is open with the branch or the tip as its
    head: scripts/clean-worktrees.py keeps the worktree then, so its delete command refuses."""
    if by_head_branch is None:
        return False
    return clean_worktrees_module().open_pull_request_of(by_head_branch, branch, tip) is not None


def worktree_entry(repo, worktree, branch, tip, by_head_branch, by_head_commit):
    if by_head_branch is None:
        pull_request_text = "pull request state unknown"
    else:
        pull_request = pull_request_for(branch, tip, by_head_branch, by_head_commit)
        pull_request_text = (clean_worktrees_module().pull_request_text(pull_request)
                             if pull_request else "no pull request")
    command = delete_command_text(
        repo, clean_worktrees_module().REMOVE_WORKTREE_AND_FORCE_DELETE_ITS_BRANCH_COMMAND_LINE_FLAG,
        worktree)
    return (f"worktree {worktree}; branch {branch or 'none (detached HEAD)'}; {pull_request_text}; "
            f"delete with: {command}")


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


def authored_branches(repo, agent_seat):
    """Return (branch, tip, date) of each local branch no worktree has checked out whose tip is
    not on origin/main and was written by this agent-seat."""
    attached = checked_out_branches(repo)
    branches = []
    # lstrip=2, not :short, which reads heads/<name> when a tag has the branch's name.
    for line in git_lines(repo, "for-each-ref", f"--no-merged={ORIGIN_MAIN}",
                          "--format=%(refname:lstrip=2)%00%(objectname)%00%(authorname)"
                          "%00%(authordate:short)", "refs/heads/"):
        branch, tip, author, date = line.split("\0")
        if branch != MAIN_BRANCH and branch not in attached and author == agent_seat:
            branches.append((branch, tip, date))
    return branches


def every_commit_is_a_cherry_picked_copy_on_origin_main(repo, tip):
    """Whether origin/main holds a copy of every commit the tip has that origin/main lacks.
    `git cherry` leaves out merge commits, whose conflict resolutions may be work origin/main
    lacks, so a tip with a merge commit origin/main lacks never counts as copied."""
    if git_lines(repo, "rev-list", "--merges", f"{ORIGIN_MAIN}..{tip}"):
        return False
    marks = [line.split(" ", 1)[0] for line in git_lines(repo, "cherry", ORIGIN_MAIN, tip)]
    return bool(marks) and "+" not in marks


def deleted_branch_entry(repo, branch, tip):
    restore = shlex.join(["git", "-C", str(repo), "branch", branch, tip])
    return (f"deleted branch {branch}, whose every commit is on origin/main as a cherry-picked "
            f"copy; restore it with: {restore}")


def branch_entries(repo, branches, by_head_branch, by_head_commit, deleted,
                   delete_cherry_picked_copies=False, holding=None, hidden=None):
    """Return the entry text of each branch that no pull request has as its head. The entry text
    of each such branch deleted because origin/main holds a copy of its every commit is appended
    to deleted, the caller's list, at once, so that the deletion and its restore command are
    still reported when a later git call raises. Each branch an open task holds, as holding
    reads it, is neither listed nor deleted: its holders are appended to hidden, the caller's
    list."""
    origin_tips = origin_branch_tips(repo)
    entries = []
    for branch, tip, date in branches:
        if pull_request_for(branch, tip, by_head_branch, by_head_commit) is not None:
            continue
        holders = holding.holders(branch) if holding is not None else set()
        if holders:
            hidden.append(("branch", holders))
            continue
        deletion_failure = ""
        if delete_cherry_picked_copies and every_commit_is_a_cherry_picked_copy_on_origin_main(
                repo, tip):
            result = clean_worktrees_module().run_git(repo, "branch", "-D", branch)
            if not result.returncode:
                deleted.append(deleted_branch_entry(repo, branch, tip))
                continue
            deletion_failure = (f"; every commit is on origin/main as a cherry-picked copy, but "
                                f"`git branch -D` exited {result.returncode}: "
                                f"{' '.join(result.stderr.split())[:200] or 'no error text'}")
        count = git_lines(repo, "rev-list", "--count", f"{ORIGIN_MAIN}..{tip}")[0]
        subject = git_lines(repo, "log", "-1", "--format=%s", tip)[0]
        command = delete_command_text(
            repo, clean_worktrees_module().FORCE_DELETE_BRANCH_FLAG, branch)
        entries.append(f"branch {branch}; {count} commit(s) not on origin/main, the newest "
                       f"{tip[:12]} of {date}, \"{subject}\"; "
                       f"{pushed_text(branch, tip, origin_tips)}{deletion_failure}; "
                       f"delete with: {command}")
    return entries


INSTRUCTIONS = """\
Each is listed because it belongs to this agent-seat: a worktree because its owner file names this agent-seat, a branch because this agent-seat wrote its newest commit not on origin/main and no pull request has it as its head. An earlier agent-session left each one. Decide for each whether you will carry it on. To carry one on, work on it, or say in your session-handoff which agent-seat will. To delete one, run the command printed beside it, which keeps a worktree whose pull request is open; for a branch marked "not on origin", read `git log origin/main..<branch>` first. If the command prints a line opening FAILED or exits nonzero, keep that item, tell the user what it printed, and go on with the others. Tell the user in your next message which worktrees and branches you kept and which you deleted."""


def section(heading, entries, agent_seat, entries_at_most):
    lines = [heading]
    shown = entries if entries_at_most is None else entries[:entries_at_most]
    lines.extend(f"- {entry}" for entry in shown)
    rest = len(entries) - len(shown)
    if rest > 0:
        lines.append(f"- and {rest} more; list them all with: {list_command_text(agent_seat)}")
    return lines


def counted(count, singular, plural):
    return f"{count} {singular if count == 1 else plural}"


def task_id_sort_key(task_id):
    return (0, int(task_id), "") if task_id.isdigit() else (1, 0, task_id)


def hidden_line(hidden):
    """The one line that stands for the entries open tasks hold; "" when none is hidden."""
    if not hidden:
        return ""
    worktrees = sum(1 for kind, _ in hidden if kind == "worktree")
    branches = len(hidden) - worktrees
    parts = []
    if worktrees:
        parts.append(counted(worktrees, "worktree", "worktrees"))
    if branches:
        parts.append(counted(branches, "branch", "branches"))
    task_ids = sorted(set().union(*(holders for _, holders in hidden)), key=task_id_sort_key)
    tasks = f"{'task' if len(task_ids) == 1 else 'tasks'} {', '.join(task_ids)}"
    return (f"This agent-seat also has {' and '.join(parts)} that open tasks hold ({tasks}); "
            f"they are not listed.")


def unreadable_task_list_line(holding):
    if holding is None or not holding.unreadable:
        return ""
    return (f"This agent-seat's task list could not be read in full "
            f"({'; '.join(holding.unreadable)}), so an entry one of its tasks holds may be "
            f"listed above.")


def deleted_section(deleted):
    if not deleted:
        return []
    return ([f"{ALREADY_DELETED_HEADING_START} this agent-seat's branches whose every "
             f"commit is on origin/main, so no work is lost: {len(deleted)}:"]
            + [f"- {entry}" for entry in deleted])


def list_text_and_failure(repo, agent_seat, skip_worktree=None, entries_at_most=None,
                          delete_cherry_picked_copies=False, task_list_directory=None):
    """Return (the list's text, or "" when there is nothing to list; whether part failed).
    entries_at_most caps the entries shown of each kind; None shows every entry.
    delete_cherry_picked_copies deletes, instead of listing, each branch whose every commit is
    on origin/main as a cherry-picked copy. task_list_directory is the agent-seat's task list,
    whose open tasks' entries are left out; None reads the agent-seat's own."""
    cleaner = None
    deleted = []
    hidden = []
    holding = None
    try:
        cleaner = clean_worktrees_module()
        inside = cleaner.git_output.run_git_unless_outside_a_repository(
            repo, ["rev-parse", "--git-dir"])
        if inside is None:
            # Worktrees and branches live in a clone; a directory outside any has none.
            return "", False
        owned = owned_worktrees(repo, agent_seat, skip_worktree)
        authored = authored_branches(repo, agent_seat)
        if not owned and not authored:
            # gh is asked only when something could be listed: it takes seconds at every launch.
            return "", False
        holding = tasks_holding(agent_seat, task_list_directory)
        by_head_branch, by_head_commit, pull_request_failure = pull_requests_or_failure(repo)
        worktrees = []
        for worktree, branch, tip in owned:
            if has_open_pull_request(branch, tip, by_head_branch):
                continue
            holders = holding.holders(worktree, Path(worktree).resolve(), branch)
            if holders:
                hidden.append(("worktree", holders))
                continue
            worktrees.append(worktree_entry(repo, worktree, branch, tip, by_head_branch,
                                            by_head_commit))
        branches = ([] if pull_request_failure else
                    branch_entries(repo, authored, by_head_branch, by_head_commit, deleted,
                                   delete_cherry_picked_copies, holding, hidden))
    except Exception as error:
        failure = (f"This agent-seat's worktrees and branches with no pull request could not be "
                   f"listed ({type(error).__name__}: {error}). Work an earlier agent-session left "
                   f"may be waiting; list it with: {list_command_text(agent_seat)}")
        return "\n".join([failure] + deleted_section(deleted)), True
    if not worktrees and not branches and not deleted and not pull_request_failure \
            and not hidden:
        return "", False
    lines = []
    if worktrees:
        lines += section(f"This agent-seat's worktrees: {len(worktrees)}:", worktrees, agent_seat,
                         entries_at_most)
    if pull_request_failure:
        lines.append(f"This agent-seat's branches with no pull request could not be listed, "
                     f"because gh could not list the pull requests ({pull_request_failure}); "
                     f"list them with: {list_command_text(agent_seat)}")
    elif branches:
        lines += section(f"This agent-seat's branches with no pull request: {len(branches)}:",
                         branches, agent_seat, entries_at_most)
    if worktrees or branches:
        lines.append(INSTRUCTIONS)
    lines += [line for line in (hidden_line(hidden), unreadable_task_list_line(holding)) if line]
    lines += deleted_section(deleted)
    return "\n".join(lines), bool(pull_request_failure)


def first_prompt_text(repo, agent_seat, skip_worktree=None):
    """The first prompt's paragraph on this agent-seat's worktrees and branches with no pull
    request; empty when there are none. A failure is stated, never left as an empty list."""
    return list_text_and_failure(repo, agent_seat, skip_worktree, ENTRIES_AT_MOST,
                                 delete_cherry_picked_copies=True)[0]


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
