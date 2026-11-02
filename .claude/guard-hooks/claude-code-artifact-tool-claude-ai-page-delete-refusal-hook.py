#!/usr/bin/env python3
"""Refuse every Artifact tool call whose action is "delete"; let every other Artifact call through.

Claude Code makes each Artifact delete wait for the user to confirm it, and nothing on
screen tells him a confirmation is waiting, so the agent's turn stops until he notices.
The refusal names the page the call would have deleted, from the call's url, so the
agent can give the user the link to delete it himself on claude.ai.

Only the Artifact tool is read. A payload that is not JSON, not an object, or not an
Artifact call is let through without output, as the other guard hooks do.
"""

# Deferred annotations let the hook load on the Mac's system Python 3.9.
from __future__ import annotations

import json
import sys

NO_LINK_TEXT = "(no link in the call)"

REFUSAL_TEMPLATE = (
    'REFUSED: an Artifact tool call with action "delete". This call was not sent, so nothing '
    "waits for the user. Agents in this project do not delete claude.ai pages, because each "
    "delete waits for the user to confirm it, and the agent's turn would stop until the user "
    "confirmed it.\n"
    "If a step, a session-handoff, a skill or your own plan tells you to delete a claude.ai "
    "page, such as a walk's item page: skip that step and go on.\n"
    "If the user asked you to delete a page or an artifact: give him its link, {link}, and "
    "tell him he can delete it himself on claude.ai."
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
