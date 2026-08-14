#!/usr/bin/env python3
"""Block writes to backup state — Timeshift on the box, Time Machine on the Mac
(user-walked 2026-08-14, nedschorus#45).

Wired as a PreToolUse hook on Edit, Write, and NotebookEdit, alongside
instruction-file-guard.py. Separate from that guard on purpose: the two protect
different things and, more importantly, grant different overrides.

The instruction-file guard's override is self-serve — an agent that believes the
user already approved a change may quote his words into .walk-approved and pass.
That is right for instruction files, where the audit value is the visible quote.
It is wrong for backups. A backup an agent can modify is not a backup, and the
failure mode is silent: a snapshot deleted to "free space" or a retention count
lowered to "clean up" destroys history that nothing else holds, and nobody
notices until a restore is attempted. So this guard's override requires approval
obtained in the CURRENT conversation, written to its own marker file, and the
refusal message says so — prior approval, a standing arrangement, or a plausible
inference from the task does not count.

Recovering a file never needs this override. Snapshots are ordinary readable
directory trees: copy the file out. Reading is unrestricted by design, because
the point of the rule is that agents can restore things without being able to
break the thing they restore from.

Two machines, so two shapes of path. On the box, Timeshift keeps snapshots under
its backup mount and its configuration in /etc/timeshift. On the Mac, Time
Machine uses Backups.backupdb directories, .sparsebundle disk images, and the
/Volumes/.timemachine automount tree. Note that /Volumes/nedhome is the Mac's
mount of the BOX'S home directory and is deliberately NOT protected here — it is
ordinary working space that happens to be remote.

Like its sibling, this is a tool-call block and cannot see a write made through a
shell command. It stops the careless path; the rule in CLAUDE.md covers the rest.
"""

import json
import os
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

APPROVAL_MARKER_NAME = ".backup-write-approved"

DENY_MESSAGE = (
    "Refusing to modify {path}: it is backup state (Timeshift snapshots on ned-box, or Time "
    "Machine on the Mac), and agents read backups but never write them. Stop here and ask the "
    "user. Do NOT proceed on prior approval, a standing arrangement, or an inference from your "
    "task — he must give permission for this specific change, in this conversation, now. If you "
    "are trying to RECOVER a file, no permission is needed and this guard is not in your way: "
    "snapshots are ordinary readable directories, so copy the file out of the snapshot tree "
    "instead of writing anything. If he does grant permission for a real change to backup "
    "configuration, quote his exact words into {marker} at the repository root and resubmit — "
    "the marker is consumed by the one call it approves."
)


def project_root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()


def is_protected(file_path: str) -> bool:
    try:
        path = Path(file_path).resolve()
    except (OSError, RuntimeError):
        path = Path(file_path)

    text = str(path)
    for prefix in PROTECTED_PREFIXES:
        if text == prefix or text.startswith(prefix + "/"):
            return True

    for part in path.parts:
        if part in PROTECTED_COMPONENT_NAMES:
            return True
        if part.endswith(PROTECTED_COMPONENT_SUFFIXES):
            return True
    return False


def consume_approval_marker(marker_path: Path) -> bool:
    """One approved change passes; the marker is spent by the call it approves."""
    try:
        content = marker_path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, OSError):
        return False
    if not content:
        return False
    marker_path.unlink(missing_ok=True)
    return True


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0
    file_path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not file_path or not is_protected(file_path):
        return 0

    marker_path = project_root() / APPROVAL_MARKER_NAME
    if consume_approval_marker(marker_path):
        return 0

    print(DENY_MESSAGE.format(path=file_path, marker=APPROVAL_MARKER_NAME), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
