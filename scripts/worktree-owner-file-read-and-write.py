#!/usr/bin/env python3
"""Write, read and judge a worktree's owner file, which tells scripts/clean-worktrees.py
who owns a git worktree and so when the worktree's work is done.

THE FILE. `worktree-owner.json`, in the worktree's own git directory, the one
`git rev-parse --absolute-git-dir` prints inside the worktree, such as
<clone>/.git/worktrees/<name>/worktree-owner.json. There `git status` never
lists it, no commit can carry it, and `git worktree remove` deletes it with
the worktree. It holds one JSON object:

  {"owner_kind": "agent-seat", "agent_seat": "<name>"}
  {"owner_kind": "agent-session", "agent_seat": "<name>", "owner_key": "<key>"}

An agent-seat owns the worktree its agent-sessions work in, and counts as
running while its handoff-supervisor runs: the process whose id is in
~/.claude/handoffs/<name>-supervisor.lock runs handoff-supervisor.py with
--agent <name>. A session-handoff keeps the supervisor, so a handoff changes
nothing. An agent-session owns the worktree of a subagent it dispatched, and
counts as running while its `claude` process runs; owner_key names that
process as nc-systems/handoff/uncommitted-work-snapshots.py names a
work-snapshot's owner (boot id, process id and start time on Linux; process id
and start time on macOS). agent_seat is the agent-seat whose agent-sessions
are told about the worktree; the launchers set GIT_AUTHOR_NAME to it.

WHO WRITES IT. The program that makes a worktree, through
worktree_owner_file_write or the `write` command below. A subagent's worktree
is made by Claude Code, which locks it while the subagent runs with the reason
"claude agent agent-<id> (pid N start M)", N being the dispatching
agent-session's `claude` process, and unlocks it when the subagent finishes;
scripts/uncommitted-work-snapshot-hook.py writes the agent-session's owner
file after the subagent's Edit, Write, NotebookEdit or Bash calls there,
while that lock still names the process; a subagent that makes none of those
calls there leaves its worktree with no owner file. A worktree with no owner file is
never removed by the cleaner.

It refuses to write into the reference-checkout, whose git directory is the
clone's common one, and over an existing owner file.

Usage:
  worktree-owner-file-read-and-write.py write --agent-seat NAME [--worktree PATH]
  worktree-owner-file-read-and-write.py write --agent-session [--worktree PATH]
      --agent-session names the nearest `claude` process among this program's
      parent processes, and the agent-seat GIT_AUTHOR_NAME names
  worktree-owner-file-read-and-write.py show [--worktree PATH]
      prints the owner file and whether its owner runs
  PATH defaults to the worktree holding the current directory.

Exit codes: 0 written or shown, 1 the file could not be written or read, or a
worktree already has one, 2 bad invocation.
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

WORKTREE_OWNER_FILE_NAME = "worktree-owner.json"
OWNER_AGENT_SEAT = "agent-seat"
OWNER_AGENT_SESSION = "agent-session"

RUNNING = "running"
STOPPED = "stopped"
UNKNOWN = "unknown"

# Claude Code's lock reason on a subagent's worktree while the subagent runs.
CLAUDE_CODE_SUBAGENT_WORKTREE_LOCK_REASON = re.compile(
    r"^claude agent agent-[0-9A-Za-z]+ \(pid (\d+) start \d+\)$")

AGENT_SEAT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

HANDOFF_DIRECTORY = Path.home() / ".claude" / "handoffs"

WORKTREE_OWNER_FILE_COMMAND_FAILED_NEXT_STEP_LINES = (
    "If the line above says the owner file already exists, the worktree already has its owner, "
    "and nothing needs doing.\n"
    "Otherwise fix the cause the line above names, then run this command again once.\n"
    "If it fails the same way again, tell whoever asked for the worktree what the line above says: "
    "scripts/clean-worktrees.py never removes a worktree that has no owner file, so it stays on "
    "disk until someone removes it with git worktree remove.")

_work_snapshots = None
_handoff_supervisor = None


class WorktreeOwnerFileError(Exception):
    """The owner file could not be written or read, or holds something other than an owner."""


class WorktreeOwnerFileAlreadyExistsError(WorktreeOwnerFileError):
    """The worktree already has an owner file, which a write never replaces."""


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_uncommitted_work_snapshots_module_once():
    global _work_snapshots
    if _work_snapshots is None:
        _work_snapshots = load_module(
            "uncommitted_work_snapshots",
            REPO_ROOT / "nc-systems" / "handoff" / "uncommitted-work-snapshots.py")
    return _work_snapshots


def handoff_supervisor_module():
    """Loaded only to judge an agent-seat owner: the supervisor loads many modules of its own."""
    global _handoff_supervisor
    if _handoff_supervisor is None:
        _handoff_supervisor = load_module(
            "handoff_supervisor", REPO_ROOT / "nc-systems" / "handoff" / "handoff-supervisor.py")
    return _handoff_supervisor


def git_directories(worktree):
    """Return (the worktree's own git directory, the clone's common one); raise when git cannot say."""
    result = subprocess.run(
        ["git", "-C", str(worktree), "rev-parse", "--absolute-git-dir",
         "--path-format=absolute", "--git-common-dir"],
        capture_output=True, text=True, check=False)
    lines = result.stdout.splitlines()
    if result.returncode != 0 or len(lines) != 2:
        raise WorktreeOwnerFileError(
            f"git rev-parse in {worktree} could not name its git directory: "
            f"{result.stderr.strip() or f'exit {result.returncode}'}")
    return Path(lines[0]).resolve(), Path(lines[1]).resolve()


def worktree_owner_file_path_find(worktree):
    own, common = git_directories(worktree)
    if own == common:
        raise WorktreeOwnerFileError(
            f"{worktree} is the clone's main checkout, the reference-checkout, which has no owner")
    return own / WORKTREE_OWNER_FILE_NAME


def worktree_owner_file_record_validate_and_build(owner_kind, agent_seat, owner_key=None):
    """The owner file's object, or raise WorktreeOwnerFileError when a field is wrong."""
    if not isinstance(agent_seat, str) or not AGENT_SEAT_NAME.match(agent_seat):
        raise WorktreeOwnerFileError(f"agent_seat {agent_seat!r} is not an agent-seat's name")
    if owner_kind == OWNER_AGENT_SEAT and owner_key is None:
        return {"owner_kind": owner_kind, "agent_seat": agent_seat}
    if owner_kind == OWNER_AGENT_SESSION and isinstance(owner_key, str) and owner_key:
        return {"owner_kind": owner_kind, "agent_seat": agent_seat, "owner_key": owner_key}
    raise WorktreeOwnerFileError(
        f"owner_kind {owner_kind!r} with owner_key {owner_key!r} is neither an agent-seat "
        f"without an owner_key nor an agent-session with one")


def worktree_owner_file_write(worktree, owner_kind, agent_seat, owner_key=None):
    """Write the owner file into a worktree that has none; return its path.

    Raise WorktreeOwnerFileError when the worktree already has one, is the
    reference-checkout, or the file cannot be written.
    """
    record = worktree_owner_file_record_validate_and_build(owner_kind, agent_seat, owner_key)
    path = worktree_owner_file_path_find(worktree)
    try:
        # Written beside its final place and linked there, so no reader sees half a file and an
        # existing owner file is never replaced.
        with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=".worktree-owner-",
                                         delete=False, encoding="utf-8") as scratch:
            scratch.write(json.dumps(record) + "\n")
        try:
            os.link(scratch.name, path)
        finally:
            os.unlink(scratch.name)
    except FileExistsError:
        raise WorktreeOwnerFileAlreadyExistsError(f"{path} already exists") from None
    except OSError as error:
        raise WorktreeOwnerFileError(f"{path} could not be written: {error}") from None
    return path


def worktree_owner_file_read(worktree):
    """Return the owner file's object, or None when the worktree has none.

    Raise WorktreeOwnerFileError when it cannot be read or is not an owner file.
    """
    path = worktree_owner_file_path_find(worktree)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as error:
        raise WorktreeOwnerFileError(f"{path} could not be read: {error}") from None
    try:
        record = json.loads(text)
    except json.JSONDecodeError as error:
        raise WorktreeOwnerFileError(f"{path} is not JSON: {error}") from None
    if not isinstance(record, dict) or set(record) - {"owner_kind", "agent_seat", "owner_key"}:
        raise WorktreeOwnerFileError(f"{path} does not hold an owner: {text.strip()[:200]}")
    try:
        return worktree_owner_file_record_validate_and_build(record.get("owner_kind"), record.get("agent_seat"), record.get("owner_key"))
    except WorktreeOwnerFileError as error:
        raise WorktreeOwnerFileError(f"{path}: {error}") from None


def agent_seat_handoff_supervisor_running_state_check(agent_seat, handoff_directory=None):
    """Return (state, explanation): whether the agent-seat's handoff-supervisor runs."""
    supervisor = handoff_supervisor_module()
    lock_path = supervisor.supervisor_lock_path(handoff_directory or HANDOFF_DIRECTORY, agent_seat)
    try:
        text = lock_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return STOPPED, f"no handoff-supervisor runs for {agent_seat}: no lock at {lock_path}"
    except OSError as error:
        return UNKNOWN, f"the handoff-supervisor lock {lock_path} could not be read: {error}"
    try:
        process_id = int(text)
    except ValueError:
        return UNKNOWN, f"the handoff-supervisor lock {lock_path} holds {text[:40]!r}, not a process id"
    running, explanation = supervisor.process_is_supervisor_for_agent(
        process_id, agent_seat, lock_path=lock_path)
    return (RUNNING if running else STOPPED), explanation


def agent_session_running_state(owner_key):
    """Return (state, explanation): whether the agent-session's `claude` process runs."""
    snapshots = load_uncommitted_work_snapshots_module_once()
    try:
        alive = snapshots.owner_process_is_alive(owner_key)
    except Exception as error:
        return UNKNOWN, (f"whether the agent-session {owner_key} runs could not be read: "
                         f"{type(error).__name__}: {error}")
    if alive:
        return RUNNING, f"the agent-session's claude process ({owner_key}) runs"
    return STOPPED, f"the agent-session's claude process ({owner_key}) has stopped"


def worktree_owner_running_state(record, handoff_directory=None):
    """Return (state, explanation) for an owner file's object: RUNNING, STOPPED or UNKNOWN."""
    if record["owner_kind"] == OWNER_AGENT_SEAT:
        return agent_seat_handoff_supervisor_running_state_check(record["agent_seat"], handoff_directory)
    return agent_session_running_state(record["owner_key"])


def claude_code_subagent_worktree_lock_reason_dispatching_process_id_parse(lock_reason):
    """The dispatching `claude` process's id in Claude Code's lock reason, or None for any other."""
    match = CLAUDE_CODE_SUBAGENT_WORKTREE_LOCK_REASON.match((lock_reason or "").strip())
    return int(match.group(1)) if match else None


def worktree_lock_reason_read(worktree):
    """The worktree's `git worktree lock` reason, "" for a lock with none, or None when unlocked."""
    own, _ = git_directories(worktree)
    try:
        return (own / "locked").read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise WorktreeOwnerFileError(f"{own / 'locked'} could not be read: {error}") from None


def worktree_of_current_directory():
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                            capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise WorktreeOwnerFileError(
            f"the current directory is in no git worktree: {result.stderr.strip()}")
    return Path(result.stdout.strip())


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments in (["--help"], ["-h"]):
        print(__doc__)
        return 0
    worktree = None
    if "--worktree" in arguments:
        position = arguments.index("--worktree")
        if position + 1 >= len(arguments):
            print("worktree-owner-file-read-and-write: --worktree needs a path", file=sys.stderr)
            return 2
        worktree = Path(arguments[position + 1])
        del arguments[position:position + 2]
    try:
        if arguments == ["show"]:
            worktree = worktree or worktree_of_current_directory()
            record = worktree_owner_file_read(worktree)
            if record is None:
                print(f"{worktree}: no owner file at {worktree_owner_file_path_find(worktree)}")
                return 0
            state, explanation = worktree_owner_running_state(record)
            print(f"{worktree}: {json.dumps(record)} — {state}: {explanation}")
            return 0
        if len(arguments) == 3 and arguments[:2] == ["write", "--agent-seat"]:
            worktree = worktree or worktree_of_current_directory()
            path = worktree_owner_file_write(worktree, OWNER_AGENT_SEAT, arguments[2])
        elif arguments == ["write", "--agent-session"]:
            worktree = worktree or worktree_of_current_directory()
            snapshots = load_uncommitted_work_snapshots_module_once()
            process_id = snapshots.claude_owner_process_id(os.getppid())
            if process_id is None:
                raise WorktreeOwnerFileError(
                    "no process named claude is among this program's parent processes, "
                    "so there is no agent-session to name")
            agent_seat = os.environ.get(snapshots.AGENT_SEAT_ENVIRONMENT_VARIABLE, "")
            path = worktree_owner_file_write(worktree, OWNER_AGENT_SESSION, agent_seat,
                                             snapshots.owner_key_of_process(process_id))
        else:
            print(__doc__, file=sys.stderr)
            return 2
    except WorktreeOwnerFileError as error:
        print(f"worktree-owner-file-read-and-write: FAILED: {error}", file=sys.stderr)
        print(WORKTREE_OWNER_FILE_COMMAND_FAILED_NEXT_STEP_LINES, file=sys.stderr)
        return 1
    print(f"{worktree}: owner file written at {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
