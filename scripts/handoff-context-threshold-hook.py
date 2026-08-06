#!/usr/bin/env python3
"""Tell a session to write its handoff once context runs low.

The handoff system's auto-trigger, half two (specification:
docs/cross-project/fast-handoff-design.md). Wire it as a Stop hook in
settings.json; it runs at every turn boundary.

Stop-hook stdin does not carry the context window, so this reads the
percentage that handoff-statusline-context-relay.py wrote for this session.
When the used share reaches the threshold, the hook emits a system message
telling the agent to run the handoff skill; the supervisor takes over from
there. Below the threshold it stays silent.

It fires ONCE per session: after firing it records the fact beside the relay
file, so the reminder does not repeat at every subsequent turn while the
agent is composing the handoff.

Threshold: --threshold-used-percentage, default 50.
"""

import argparse
import json
import sys
from pathlib import Path

RELAY_DIRECTORY = Path.home() / ".claude" / "handoffs"

HANDOFF_INSTRUCTION = (
    "Context is {used:.0f}% used, at or past the {threshold:.0f}% recycle threshold. "
    "Run the handoff skill now: pick the boundary, write next-step, and write the "
    "handoff file with restart-counter incremented. Finish the sentence you are on "
    "first — nothing is lost, and the supervisor relaunches you with the dialog."
)


def read_json_file(path: Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None


def session_id_from_stdin() -> str:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return ""
    return payload.get("session_id", "") if isinstance(payload, dict) else ""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fire the handoff skill when context runs low.")
    parser.add_argument("--threshold-used-percentage", type=float, default=50.0)
    arguments = parser.parse_args(argv)

    session_id = session_id_from_stdin()
    if not session_id:
        return 0  # no session to reason about; stay silent

    relay = read_json_file(RELAY_DIRECTORY / f"{session_id}-context.json")
    if not relay:
        return 0  # the status line has not reported yet

    remaining = relay.get("remaining_percentage")
    if not isinstance(remaining, (int, float)):
        return 0

    used = 100.0 - remaining
    if used < arguments.threshold_used_percentage:
        return 0

    fired_marker = RELAY_DIRECTORY / f"{session_id}-handoff-asked"
    if fired_marker.exists():
        return 0  # already asked this session; do not nag every turn

    try:
        fired_marker.write_text(f"{used:.1f}\n", encoding="utf-8")
    except OSError:
        pass

    print(
        HANDOFF_INSTRUCTION.format(used=used, threshold=arguments.threshold_used_percentage),
        file=sys.stderr,
    )
    return 2  # exit 2 surfaces stderr to the agent as a system message


if __name__ == "__main__":
    sys.exit(main())
