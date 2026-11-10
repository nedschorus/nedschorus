#!/usr/bin/env python3
"""Make a git worktree for the calling agent-seat and write its owner file at once.

Agents make worktrees with it; programs that make and remove their own worktrees keep
doing so.

Usage:
  agent-seat-worktree-create-with-owner-file.py <branch> [--base <commit>]
  agent-seat-worktree-create-with-owner-file.py --detach <directory name> <commit>

Run it from any checkout of the clone. The worktree is made at
<reference-checkout>/.claude/worktrees/<branch>, or <directory name> with --detach, where
the reference-checkout is the parent of the directory `git rev-parse --git-common-dir`
prints. A branch name holding `/` makes nested directories there.

  - <branch> is a branch of this clone: the worktree checks it out.
  - Otherwise it runs `git fetch origin` first, so origin/main and origin/<branch> are
    current, and stops with exit 1 when the fetch fails.
  - <branch> exists only as origin/<branch>: the worktree checks out a new local <branch>
    tracking it, as a fix-round of a pull request pushed from another clone needs.
  - <branch> exists nowhere: the worktree checks out a new <branch> cut from --base, by
    default origin/main. --base with an existing branch is refused.
  - --detach: the worktree stands on a detached HEAD at <commit>, with no branch; nothing
    is fetched.

The owner file, scripts/worktree-owner-file-read-and-write.py's, names the agent-seat
GIT_AUTHOR_NAME names, which must be an agent-seat as scripts/recover-crashed-seats.py lists
them. `git worktree add` runs with core.hooksPath emptied, so the post-checkout hook writes
no owner file of its own and this program is its one writer.

Prints the worktree's path, alone, on stdout, so `cd "$(python3 <this program> <branch>)"`
works; every other line goes to stderr.

How it can fail. When writing the owner file fails, it removes the worktree with
`git worktree remove --force`, leaves a branch it made, and exits 1. When that removal fails
too, the worktree stays with no owner file, which scripts/clean-worktrees.py never removes,
and the message names it. A `git worktree add` that fails leaves what git leaves, which can be
a new branch with no worktree. Nothing it makes is cleaned up when the program is killed
between the add and the owner file.

Exit codes: 0 made; 1 git or the owner file failed; 2 bad invocation, or refused before
anything was made.

The messages follow
docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
"""

import importlib.util
import os
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROGRAM_PATH = Path(__file__).resolve()

AGENT_SEAT_WORKTREES_DIRECTORY = Path(".claude") / "worktrees"
DEFAULT_BASE = "origin/main"
EXIT_MADE, EXIT_FAILED, EXIT_REFUSED = 0, 1, 2
# A directory that holds no hooks, so `git worktree add` runs no post-checkout hook.
NO_HOOKS_DIRECTORY = os.devnull

USAGE = (
    "usage: agent-seat-worktree-create-with-owner-file.py <branch> [--base <commit>]\n"
    "       agent-seat-worktree-create-with-owner-file.py --detach <directory name> <commit>")


def load_module(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


owner_file = load_module("worktree_owner_file_read_and_write",
                         "scripts/worktree-owner-file-read-and-write.py")

NOT_AN_AGENT_SEAT_MESSAGE = (
    "agent-seat-worktree-create-with-owner-file: REFUSED: GIT_AUTHOR_NAME is {name!r}, which "
    "names no agent-seat under {agents_root}, so there is no agent-seat to name in the new "
    "worktree's owner file; nothing was made.\n"
    "If you are an agent-session of an agent-seat, run this from that agent-session's shell, "
    "where the launcher set GIT_AUTHOR_NAME to the agent-seat's name, or prefix the command "
    "with GIT_AUTHOR_NAME=<your agent-seat's name>.\n"
    "If you are not an agent-session of an agent-seat, tell the user, or, if you are a "
    "subagent, the agent that dispatched you, that you cannot make a worktree without an "
    "agent-seat to own it.")

BASE_WITH_EXISTING_BRANCH_MESSAGE = (
    "agent-seat-worktree-create-with-owner-file: REFUSED: branch {branch} already exists "
    "({where}), so --base {base} cannot be its start; nothing was made.\n"
    "If you want a worktree on the existing branch, run the same command without --base.\n"
    "If you want a new branch, choose a name no branch has.")

PATH_EXISTS_MESSAGE = (
    "agent-seat-worktree-create-with-owner-file: REFUSED: {path} already exists, so no "
    "worktree can be made there; nothing was made.\n"
    "If it is a worktree on the branch you want, work in it: run `git -C {path} status`.\n"
    "Otherwise choose another {what}.")

GIT_FAILED_MESSAGE = (
    "agent-seat-worktree-create-with-owner-file: FAILED: `{command}` exited {code}: {stderr}\n"
    "If git's message names a cause you can fix, such as a branch checked out in another "
    "worktree (`git worktree list` names it) or a commit this clone lacks (`git fetch origin` "
    "fetches it), fix it and run this program again once.\n"
    "If it fails again, tell the user, or, if you are a subagent, the agent that dispatched "
    "you, which command failed, quoting both FAILED lines.")

OWNER_FILE_FAILED_MESSAGE = (
    "agent-seat-worktree-create-with-owner-file: FAILED: the owner file of the new worktree "
    "{path} could not be written: {error}\n"
    "This program removed that worktree again, because scripts/clean-worktrees.py never "
    "removes a worktree with no owner file.{branch_kept}\n"
    "Fix the cause the FAILED line names, then run the same command again once{rerun_note}.\n"
    "If it fails again, tell the user, or, if you are a subagent, the agent that dispatched "
    "you, quoting both FAILED lines.")
BRANCH_KEPT_SENTENCE = (
    " The branch {branch} it made is kept, with no commit of its own; a rerun checks it out.")
RERUN_WITHOUT_BASE_NOTE = ", without --base, since the branch now exists"

REMOVAL_FAILED_MESSAGE = (
    "agent-seat-worktree-create-with-owner-file: FAILED: the owner file of the new worktree "
    "{path} could not be written: {error}\n"
    "Removing that worktree failed too: {removal_error}\n"
    "The worktree is still there with no owner file, and scripts/clean-worktrees.py never "
    "removes a worktree with no owner file.\n"
    "If it holds nothing of yours, remove it with `git worktree remove --force {path}`.\n"
    "Then tell the user, or, if you are a subagent, the agent that dispatched you, quoting "
    "both FAILED lines.")


class GitFailed(Exception):
    def __init__(self, command, completed):
        super().__init__(GIT_FAILED_MESSAGE.format(
            command=shlex.join(command), code=completed.returncode,
            stderr=completed.stderr.strip() or "(git printed nothing)"))


def git(*arguments, check=True):
    command = ["git", *arguments]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if check and completed.returncode != 0:
        raise GitFailed(command, completed)
    return completed


def ref_exists(ref):
    return git("rev-parse", "--verify", "--quiet", ref, check=False).returncode == 0


def calling_agent_seat():
    """(GIT_AUTHOR_NAME, whether it names an agent-seat, the agents root it was looked for in)."""
    recover_crashed_seats = load_module("recover_crashed_seats", "scripts/recover-crashed-seats.py")
    agents_root = recover_crashed_seats.default_agents_root()
    name = os.environ.get("GIT_AUTHOR_NAME", "")
    seats = recover_crashed_seats.list_agent_seat_names_with_agent_session_records(
        agents_root, recover_crashed_seats.default_handoff_directory())
    return name, name in seats, agents_root


def reference_checkout():
    common = git("rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
    return Path(common).resolve().parent


def parse_arguments(arguments):
    """(branch, base, detach directory name, commit), or a usage error as a string."""
    if arguments[:1] == ["--detach"]:
        if len(arguments) != 3 or arguments[1].startswith("-") or arguments[2].startswith("-"):
            return "--detach takes a directory name and a commit"
        name = Path(arguments[1])
        if name.is_absolute() or ".." in name.parts or not name.parts:
            return f"the directory name {arguments[1]!r} must be a relative path with no '..'"
        return None, None, arguments[1], arguments[2]
    base = None
    if "--base" in arguments:
        position = arguments.index("--base")
        if position + 1 >= len(arguments):
            return "--base needs a commit"
        base = arguments[position + 1]
        arguments = arguments[:position] + arguments[position + 2:]
    if len(arguments) != 1 or arguments[0].startswith("-"):
        return "give one branch name"
    if git("check-ref-format", "--branch", arguments[0], check=False).returncode != 0:
        return f"{arguments[0]!r} is not a valid branch name"
    return arguments[0], base, None, None


def worktree_add_command(path, branch, base, commit):
    """The `git worktree add` arguments, and the branch this run makes or None."""
    add = ["-c", f"core.hooksPath={NO_HOOKS_DIRECTORY}", "worktree", "add", "--quiet"]
    if branch is None:
        return [*add, "--detach", str(path), commit], None
    for ref, where in ((f"refs/heads/{branch}", "in this clone"),
                       (f"refs/remotes/origin/{branch}", "on origin")):
        if where == "on origin":
            git("fetch", "--quiet", "origin")
        if ref_exists(ref):
            if base is not None:
                return BASE_WITH_EXISTING_BRANCH_MESSAGE.format(
                    branch=branch, where=where, base=base), None
            if where == "in this clone":
                return [*add, str(path), branch], None
            return [*add, "--track", "-b", branch, str(path), f"origin/{branch}"], branch
    return [*add, "-b", branch, str(path), base or DEFAULT_BASE], branch


def owner_file_write_or_remove_worktree(path, agent_seat, made_branch, base):
    """Write the owner file; when that fails, remove the worktree. Return the exit code."""
    try:
        owner_file.worktree_owner_file_write(path, owner_file.OWNER_AGENT_SEAT, agent_seat)
        return EXIT_MADE
    except Exception as error:
        error_text = f"{type(error).__name__}: {error}"
    removal = git("worktree", "remove", "--force", str(path), check=False)
    if removal.returncode != 0:
        print(REMOVAL_FAILED_MESSAGE.format(
            path=path, error=error_text,
            removal_error=removal.stderr.strip() or f"exit {removal.returncode}"),
            file=sys.stderr)
        return EXIT_FAILED
    print(OWNER_FILE_FAILED_MESSAGE.format(
        path=path, error=error_text,
        branch_kept=BRANCH_KEPT_SENTENCE.format(branch=made_branch) if made_branch else "",
        rerun_note=RERUN_WITHOUT_BASE_NOTE if made_branch and base else ""), file=sys.stderr)
    return EXIT_FAILED


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments in (["--help"], ["-h"]):
        print(__doc__)
        return EXIT_MADE
    try:
        parsed = parse_arguments(arguments)
        if isinstance(parsed, str):
            print(f"agent-seat-worktree-create-with-owner-file: {parsed}\n{USAGE}", file=sys.stderr)
            return EXIT_REFUSED
        branch, base, directory_name, commit = parsed
        agent_seat, is_agent_seat, agents_root = calling_agent_seat()
        if not is_agent_seat:
            print(NOT_AN_AGENT_SEAT_MESSAGE.format(name=agent_seat, agents_root=agents_root),
                  file=sys.stderr)
            return EXIT_REFUSED
        path = reference_checkout() / AGENT_SEAT_WORKTREES_DIRECTORY / (branch or directory_name)
        if path.exists() or path.is_symlink():
            print(PATH_EXISTS_MESSAGE.format(
                path=path, what="branch name" if branch else "directory name"), file=sys.stderr)
            return EXIT_REFUSED
        command, made_branch = worktree_add_command(path, branch, base, commit)
        if isinstance(command, str):
            print(command, file=sys.stderr)
            return EXIT_REFUSED
        git(*command)
    except GitFailed as error:
        print(error, file=sys.stderr)
        return EXIT_FAILED
    code = owner_file_write_or_remove_worktree(path, agent_seat, made_branch, base)
    if code == EXIT_MADE:
        print(path)
    return code


if __name__ == "__main__":
    sys.exit(main())
