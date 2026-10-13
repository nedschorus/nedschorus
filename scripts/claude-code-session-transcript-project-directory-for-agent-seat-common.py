#!/usr/bin/env python3
"""Find the folder under ~/.claude/projects/ where Claude Code keeps an agent-seat's session transcripts."""

import re


def project_directory_for_seat(seat_path, projects_root):
    """Return the harness project directory for the seat."""
    # The harness replaces every non-ASCII-alphanumeric character, including underscores, with a dash.
    mangled = re.sub(r"[^a-zA-Z0-9]", "-", str(seat_path.resolve()))
    return projects_root / mangled
