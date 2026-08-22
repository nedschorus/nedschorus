#!/usr/bin/env python3
"""Block writes to backup state — Timeshift on the box, Time Machine on the Mac
(user-walked 2026-08-14, nedschorus#45; override lane removed 2026-08-17).

Wired as a PreToolUse hook on Edit, Write, and NotebookEdit, alongside
instruction-file-guard.py. Separate from that guard on purpose: the two are
different CLASSES of protection, not two calibrations of one (user-ruled
2026-08-17). Instruction files are approval-gated writes — agents legitimately
edit them, through the user's walk, and that guard carries a marker lane for
exactly that. Backup state is not agent-writable at all: no approval, no
marker, no exception. The earlier in-conversation override lane
(.backup-write-approved) was removed by that ruling — a mechanism cannot
verify whose words a marker holds or when approval was given, and a backup an
agent can modify under any lane is not a backup. A backup configuration
change that is genuinely needed is the user's to make at his own keyboard.

Recovering a file never touches this guard. Snapshots are ordinary readable
directory trees: copy the file out. Reading is unrestricted by design, because
the point of the rule is that agents can restore things without being able to
break the thing they restore from.

Two machines, so two shapes of path. On the box, Timeshift keeps snapshots
under its backup mount and its configuration in /etc/timeshift. On the Mac,
Time Machine uses Backups.backupdb directories, .sparsebundle disk images,
and the /Volumes/.timemachine automount tree. Note that /Volumes/nedhome is
the Mac's mount of the BOX'S home directory and is deliberately NOT protected
here — it is ordinary working space that happens to be remote.

Like its sibling, this is a tool-call block and cannot see a write made
through a shell command. It stops the careless path; the rule binds agents
either way.
"""

import json
import sys
from pathlib import Path

# Exact directory prefixes whose contents are backup state.
PROTECTED_PREFIXES = (
    "/mnt/backup",          # Timeshift's backup drive on ned-box
    "/etc/timeshift",       # Timeshift's configuration
    "/Volumes/.timemachine",  # Time Machine's automount tree on the Mac
)

# Path components that mark backup state wherever it is mounted, because a Time
# Machine volume's mount point is named by the user and cannot be listed here.
PROTECTED_COMPONENT_NAMES = ("Backups.backupdb",)
PROTECTED_COMPONENT_SUFFIXES = (".sparsebundle",)

DENY_MESSAGE = (
    "Refusing to modify {path}: it is backup state (Timeshift snapshots or configuration "
    "on ned-box, or Time Machine state on the Mac), and backup state is never an agent's "
    "to write — there is no approval lane for this, in this or any conversation "
    "(user-ruled 2026-08-17). If you are trying to RECOVER a file, nothing here is in "
    "your way: snapshots are ordinary readable directories, so copy the file out of the "
    "snapshot tree instead of writing anything. If backup configuration genuinely needs "
    "changing, that is the user's to do at his own keyboard — tell him what needs "
    "changing and why, and stop."
)


def is_protected(file_path: str) -> bool:
    try:
        path = Path(file_path).resolve()
    except (OSError, RuntimeError):
        path = Path(file_path)

    # macOS mounts /etc as a symlink to /private/etc, so resolving can carry a
    # protected path OUT of its listed prefix; match the unresolved text too.
    for text in (str(Path(file_path)), str(path)):
        for prefix in PROTECTED_PREFIXES:
            if text == prefix or text.startswith(prefix + "/"):
                return True

    for part in path.parts:
        if part in PROTECTED_COMPONENT_NAMES:
            return True
        if part.endswith(PROTECTED_COMPONENT_SUFFIXES):
            return True
    return False


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0
    tool_input = payload.get("tool_input") or {}
    # NotebookEdit carries its target in notebook_path where Edit and Write use
    # file_path. This guard is registered on NotebookEdit, so reading only
    # file_path left a notebook write into backup state unguarded (PR #86's
    # review).
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not file_path or not is_protected(file_path):
        return 0

    print(DENY_MESSAGE.format(path=file_path), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
