#!/usr/bin/env python3
"""Write the owner file of the new worktree that holds the current directory, for
scripts/git-client-side-hooks/post-checkout, which runs this only after `git worktree add`.

Usage: git-client-side-hooks-post-checkout-new-worktree-owner-file-write.py [--help]

The owner file is the one scripts/worktree-owner-file-read-and-write.py writes and
scripts/clean-worktrees.py reads. The owner named:

  - a Claude Code subagent's worktree, one directly inside .claude/worktrees/ of the
    clone's main checkout: the agent-session of the nearest `claude` process among this
    program's parent processes, with the agent-seat GIT_AUTHOR_NAME names;
  - any other worktree: the agent-seat GIT_AUTHOR_NAME names.

It writes no owner file, and prints nothing, when GIT_AUTHOR_NAME names no agent-seat (an
agent-seat being a directory under the agents root that holds a handoff-supervisor state
file or a session-handoff file, as scripts/recover-crashed-seats.py lists them), as for a
worktree a person makes by hand; for that agent-seat's own agent-home, <agents root>/<agent-seat>;
for a merge-lane review checkout, directly inside ~/.cache/merge-lane-review-worktrees, which
the cleaner judges by its pull request and which an owner file would keep from that; for the
clone's main checkout; and when the worktree already has an owner file.

It does not tell a worktree made for a new agent-seat's agent-home from any other: the
launchers make that worktree with GIT_AUTHOR_NAME set to the new agent-seat, which has no
handoff records yet, so it gets none.

When the owner file cannot be written, or a subagent's worktree has no `claude` process
among this program's parents, it prints why on stderr, where the maker of the worktree sees
it, and the worktree is left with no owner file, so the cleaner keeps it until someone writes
one. It always exits 0, because the hook's exit status becomes git's.
"""

import importlib.util
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_module(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


owner_file = load_module("worktree_owner_file_read_and_write",
                         "scripts/worktree-owner-file-read-and-write.py")

CLAUDE_CODE_SUBAGENT_WORKTREES_DIRECTORY = Path(".claude") / "worktrees"

OWNER_FILE_NOT_WRITTEN_MESSAGE = (
    "post-checkout: the owner file of the new worktree {worktree} was not written: {reason}\n"
    "scripts/clean-worktrees.py never removes a worktree with no owner file, so this worktree "
    "stays on disk once its work is done.\n"
    "If you made this worktree for your agent-seat's own work, run "
    "`python3 scripts/worktree-owner-file-read-and-write.py write --agent-seat <your agent-seat> "
    "--worktree {worktree}` once the cause is fixed.\n"
    "If that fails too, tell the agent that dispatched you, or the user if no agent did, what "
    "both messages say.")


def new_worktree_owner(worktree, main_checkout, agent_seat, agent_seats, agents_root,
                       review_worktrees_directory, claude_process_key):
    """Return (owner kind, owner key or None) for the new worktree, or None when it gets no
    owner file. claude_process_key() returns the owner key of the nearest `claude` parent
    process, or None when there is none."""
    worktree = worktree.resolve()
    if worktree == main_checkout.resolve():
        return None
    if worktree.parent == review_worktrees_directory.resolve():
        return None
    if agent_seat not in agent_seats:
        return None
    if worktree.parent == (main_checkout / CLAUDE_CODE_SUBAGENT_WORKTREES_DIRECTORY).resolve():
        key = claude_process_key()
        if key is None:
            raise owner_file.WorktreeOwnerFileError(
                "it is a Claude Code subagent's worktree, but no process named claude is among "
                "the hook's parent processes, so there is no agent-session to name")
        return owner_file.OWNER_AGENT_SESSION, key
    if worktree == (agents_root / agent_seat).resolve():
        return None
    return owner_file.OWNER_AGENT_SEAT, None


def nearest_claude_parent_process_owner_key():
    snapshots = owner_file.load_uncommitted_work_snapshots_module_once()
    process_id = snapshots.claude_owner_process_id(os.getppid())
    return None if process_id is None else snapshots.owner_key_of_process(process_id)


def main():
    if sys.argv[1:] in (["--help"], ["-h"]):
        print(__doc__)
        return 0
    worktree = Path.cwd()
    try:
        # Loaded here, not at import, so a failure to load them is reported like any other.
        recover_crashed_seats = load_module("recover_crashed_seats",
                                            "scripts/recover-crashed-seats.py")
        merge_lane_common = load_module(
            "merge_lane_pull_request_helpers_common_options_paths_and_token",
            "scripts/merge-lane-pull-request-helpers-common-options-paths-and-token.py")
        _, common = owner_file.git_directories(worktree)
        agents_root = recover_crashed_seats.default_agents_root()
        agent_seat = os.environ.get("GIT_AUTHOR_NAME", "")
        owner = new_worktree_owner(
            worktree, common.parent, agent_seat,
            recover_crashed_seats.list_agent_seat_names_with_agent_session_records(
                agents_root, recover_crashed_seats.default_handoff_directory()),
            agents_root, Path.home() / merge_lane_common.REVIEW_WORKTREES_DIRECTORY_UNDER_HOME,
            nearest_claude_parent_process_owner_key)
        if owner is not None:
            owner_file.worktree_owner_file_write(worktree, owner[0], agent_seat, owner[1])
    except owner_file.WorktreeOwnerFileAlreadyExistsError:
        pass
    except Exception as error:
        print(OWNER_FILE_NOT_WRITTEN_MESSAGE.format(
            worktree=worktree, reason=f"{type(error).__name__}: {error}"), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
