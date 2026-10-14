#!/usr/bin/env python3
"""Share one-use approval markers between write guards.

Each guard needs its own filename so approval for one kind of write cannot approve another.
Sequential hooks can spend a marker before a later hook refuses; the approving hook cannot see that refusal."""

from pathlib import Path


def read_marker_approval(marker_path: Path):
    """Return nonempty approval words, or None for an absent, unreadable, or empty marker."""
    # Approval is evidenced by quoted user words; an empty marker is not consent.
    try:
        content = marker_path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, OSError):
        return None
    return content or None


def marker_would_pass(marker_path: Path) -> bool:
    """Return whether the marker approves a call, without consuming the marker."""
    return read_marker_approval(marker_path) is not None


def consume_approval_marker(marker_path: Path) -> bool:
    """Consume a marker and return whether approval was present."""
    if read_marker_approval(marker_path) is None:
        return False
    try:
        marker_path.unlink(missing_ok=True)
    except OSError:
        # Honor valid approval even if deletion fails; filesystem failure does not revoke consent.
        pass
    return True
