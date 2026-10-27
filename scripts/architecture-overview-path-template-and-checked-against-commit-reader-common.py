#!/usr/bin/env python3
"""Where a system's architecture overview lives, and the commit its last line names.

docs/nedschorus-wiki/nedschorus-how-to-write-an-architecture-overview.md defines
both; programs that find an overview or read its **Checked against:** line
import them from here, so a change to the page is made in one place in code.
"""
import re

PATH_TEMPLATE = "docs/nedschorus-wiki/nedschorus-{system}-architecture-overview.md"

CHECKED_AGAINST_PREFIX = "**Checked against:** commit ["

CHECKED_AGAINST_LINE_TEMPLATE = (
    CHECKED_AGAINST_PREFIX
    + "{commit}](https://github.com/nedschorus/nedschorus/commit/{commit})")

_CHECKED_AGAINST_COMMIT = re.compile(
    re.escape(CHECKED_AGAINST_PREFIX) + r"([0-9a-f]{7,40})\]")


def checked_against_commit(text: str):
    """Return the commit the overview's last non-blank line names, or None."""
    # Only the last line counts: the page makes it the overview's one commit, and a quoted example elsewhere must not.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    named = _CHECKED_AGAINST_COMMIT.match(lines[-1])
    return named.group(1) if named else None
