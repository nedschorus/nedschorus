#!/usr/bin/env python3
"""Block tool writes to Timeshift and Time Machine backup state.

Backup state has no approval override: agents must be able to restore files
without modifying the source. /Volumes/nedhome is ordinary remote working
space, not backup state. Shell writes are outside this tool-call guard."""

import json
import sys
from pathlib import Path

PROTECTED_PREFIXES = (
    "/mnt/backup",
    "/etc/timeshift",
    "/Volumes/.timemachine",
)

# Time Machine mount names are user-selected, so match backup components anywhere in the path.
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

    # macOS resolves /etc to /private/etc; match unresolved paths too so prefixes remain protected.
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
    # NotebookEdit uses notebook_path rather than file_path.
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not file_path or not is_protected(file_path):
        return 0

    print(DENY_MESSAGE.format(path=file_path), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
