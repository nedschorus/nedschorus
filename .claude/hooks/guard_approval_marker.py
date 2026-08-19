#!/usr/bin/env python3
"""The approval-marker lane shared by the write guards in this directory.

Extracted 2026-08-19 from the review of PR #91, which found the same marker
code copied into more than one guard. One copy means one place to fix when
the contract changes, and one place a reader has to understand to know what
an approval marker does.

THE CONTRACT. A guard refuses a write and names a marker file. The session
writes the user's quoted approval words into that file at the root of its own
checkout and resubmits. The next guarded call finds the marker, spends it, and
passes. One marker approves exactly one call: the marker is deleted by the
call it approves, so an approval cannot be replayed, and a marker left behind
by accident cannot silently authorize a later write. An empty marker is not an
approval — the audit value is the quoted words, so a file with nothing in it
is treated as absent rather than as consent.

Each guard keeps its OWN marker filename. That is deliberate and is not
something to consolidate here: an instruction-file approval and a
location-write approval must never be able to consume each other, because they
are approvals of different things. This module shares the mechanism, not the
identity.

KNOWN COST, recorded rather than fixed (PR #91's review, and unqueued as of
this extraction). The guards run as separate PreToolUse hooks, in sequence,
and each decides alone. A single write that trips two guards therefore needs
two markers — and if the first guard passes on its marker while a later guard
still refuses the call, the first marker has been spent on a write that never
happened. The session must then write it again. Nothing here can see whether a
later guard will refuse, so a guard cannot know whether spending is safe;
fixing it means changing when consumption happens, which is a design decision
about the lane rather than a defect in this code. `marker_would_pass()` exists
so a caller can ask without spending, and so a test can pin the cost.
"""

from pathlib import Path


def read_marker_approval(marker_path: Path):
    """The approval words held in the marker, or None when there is no approval.

    None covers every way a marker can fail to be one: absent, unreadable, or
    present but empty. Callers must not distinguish those cases in what they
    tell the session — an unreadable marker and a missing one both mean the
    write is not approved.
    """
    try:
        content = marker_path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, OSError):
        return None
    return content or None


def marker_would_pass(marker_path: Path) -> bool:
    """Whether a marker would approve a call, WITHOUT spending it.

    For callers that need to know the answer before deciding to consume, and
    for tests pinning that a marker outside the session's own checkout stays
    inert.
    """
    return read_marker_approval(marker_path) is not None


def consume_approval_marker(marker_path: Path) -> bool:
    """Spend one marker: True when it approved this call, False when there was
    none to spend.

    Deleting on the approving call is the whole point of the lane — see this
    module's docstring for why one approval covers exactly one write.
    """
    if read_marker_approval(marker_path) is None:
        return False
    try:
        marker_path.unlink(missing_ok=True)
    except OSError:
        # The approval was real and the guard should honour it. A marker that
        # cannot be deleted is a worse problem than one spent twice, and
        # refusing the write here would punish the session for a filesystem
        # fault it did not cause and cannot fix.
        pass
    return True
