#!/usr/bin/env python3
"""Print the status line, and relay the context percentage to a side file.

The handoff system's auto-trigger, half one (specification:
docs/cross-project/fast-handoff-design.md). The status line is the only
harness surface that receives `context_window.remaining_percentage`; a Stop
hook's stdin does not carry it. So this script does two jobs at once: it
prints the status line the user sees, and it writes the percentage where
handoff-context-threshold-hook.py can read it.

Wire it as the statusLine command in settings.json. The harness pipes one
JSON object on stdin at every refresh.

The relay file lives beside the session's other machine-local state:
  ~/.claude/handoffs/<session-id>-context.json

A malformed or unexpected payload never breaks the status line: the script
prints what it can and exits 0, because a broken status line is worse than
a missed relay, and the next refresh is a second away.
"""

import json
import sys
from pathlib import Path

RELAY_DIRECTORY = Path.home() / ".claude" / "handoffs"


def relay_path_for(session_id: str) -> Path:
    return RELAY_DIRECTORY / f"{session_id}-context.json"


def status_line_text(payload: dict) -> str:
    """Compose the visible status line: directory, model, context left."""
    working_directory = payload.get("workspace", {}).get("current_dir") or payload.get("cwd", "")
    model = payload.get("model", {}).get("display_name", "")
    remaining = payload.get("context_window", {}).get("remaining_percentage")

    parts = []
    if working_directory:
        parts.append(Path(working_directory).name)
    if model:
        parts.append(model)
    if isinstance(remaining, (int, float)):
        parts.append(f"context {remaining:.0f}% left")
    return " | ".join(parts)


def write_relay(payload: dict) -> None:
    """Record the context percentage for the Stop hook to read."""
    session_id = payload.get("session_id")
    remaining = payload.get("context_window", {}).get("remaining_percentage")
    if not session_id or not isinstance(remaining, (int, float)):
        return

    RELAY_DIRECTORY.mkdir(parents=True, exist_ok=True)
    relay_path_for(session_id).write_text(
        json.dumps({"session_id": session_id, "remaining_percentage": remaining}),
        encoding="utf-8",
    )


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            payload = {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = {}

    try:
        write_relay(payload)
    except OSError:
        pass  # a failed relay must never cost the user their status line

    print(status_line_text(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
