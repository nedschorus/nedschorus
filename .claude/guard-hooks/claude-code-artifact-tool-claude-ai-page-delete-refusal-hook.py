#!/usr/bin/env python3
"""Refuse every Artifact tool call whose action is "delete"; let every other Artifact call through.

Claude Code shows the confirmation prompt for an Artifact delete only in its terminal UI,
so in the desktop app or over Remote Control the user never sees it and the turn blocks
indefinitely. A hook cannot tell which UI the user is on, so it refuses the action
everywhere. The refusal names the artifact the call would have deleted, from the call's
url, so the agent can give the user the link to delete it himself on claude.ai.

Only the Artifact tool is read. A payload that is not JSON, not an object, or not an
Artifact call is let through without output, as the other guard hooks do.
"""

# Deferred annotations let the hook load on the Mac's system Python 3.9.
from __future__ import annotations

import json
import sys

NO_LINK_TEXT = "(no link in the call)"

REFUSAL_TEMPLATE = (
    'REFUSED: Artifact tool call with action "delete", blocked by a PreToolUse hook. Claude '
    "Code shows the confirmation prompt for this action only in its terminal UI, so in the "
    "desktop app or over Remote Control the user never sees it and the turn blocks "
    "indefinitely. A hook cannot tell which UI the user is on, so it blocks the action "
    "everywhere. The call was not sent; nothing is pending.\n"
    "If a step, skill, session-handoff or plan says to delete an artifact: skip that step "
    "and continue.\n"
    "If the user asked for the delete: give him the artifact URL, {link}, so he can delete "
    "it on claude.ai, then continue."
)


def refusal_for_tool_input(tool_input):
    """Return the refusal for a delete, or None for any other Artifact call."""
    if not isinstance(tool_input, dict) or tool_input.get("action") != "delete":
        return None
    url = tool_input.get("url")
    link = url if isinstance(url, str) and url.strip() else NO_LINK_TEXT
    return REFUSAL_TEMPLATE.format(link=link)


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))


def main(stdin=sys.stdin) -> int:
    try:
        payload = json.load(stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != "Artifact":
        return 0
    refusal = refusal_for_tool_input(payload.get("tool_input"))
    if refusal:
        deny(refusal)
    return 0


if __name__ == "__main__":
    sys.exit(main())
