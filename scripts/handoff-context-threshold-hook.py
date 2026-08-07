#!/usr/bin/env python3
"""Tell a session to write its handoff once context runs low.

The handoff system's auto-trigger, half two (specification:
docs/cross-project/fast-handoff-design.md). Wire it as a Stop hook in
settings.json; it runs at every turn boundary.

Stop-hook stdin does not carry the context window, so the used share is
computed from the session's own transcript: every assistant record carries
the model and the token usage of the request that produced it. That works
for headless sessions too, which never run a status line. The relay file
written by handoff-statusline-context-relay.py is the fallback for a session
whose first turn has not completed yet.

When the used share reaches the threshold, the hook emits a system message
telling the agent to run the handoff skill; the supervisor takes over from
there. Below the threshold it stays silent.

It fires ONCE per session: after firing it records the fact beside the relay
file, so the reminder does not repeat at every subsequent turn while the
agent is composing the handoff.

Threshold: --threshold-used-percentage, default 50.
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

RELAY_DIRECTORY = Path.home() / ".claude" / "handoffs"

# Context window per model, so a percentage can be computed from the transcript
# alone — the status line is an interactive-only surface, and headless sessions
# never run it. Prefix-matched against the model id each assistant record
# carries. A model absent from this table falls back to the default; the table
# is worth re-checking when a new model ships, since a wrong window silently
# scales the threshold rather than failing.
CONTEXT_WINDOW_TOKENS_BY_MODEL_PREFIX = {
    "claude-fable-5": 1_000_000,
    "claude-mythos-5": 1_000_000,
    "claude-opus-5": 1_000_000,
    "claude-opus-4": 1_000_000,
    "claude-sonnet-5": 1_000_000,
    "claude-sonnet-4-6": 1_000_000,
    "claude-haiku-4-5": 200_000,
}
DEFAULT_CONTEXT_WINDOW_TOKENS = 200_000

# How much of the transcript's tail to read when looking for the newest
# assistant record. Sized to clear a few large tool-result records; the read
# doubles from here when that is not enough.
FIRST_TAIL_READ_BYTES = 256 * 1024

_supervisor_spec = importlib.util.spec_from_file_location(
    "handoff_supervisor", Path(__file__).with_name("handoff-supervisor.py")
)
supervisor = importlib.util.module_from_spec(_supervisor_spec)
_supervisor_spec.loader.exec_module(supervisor)

HANDOFF_INSTRUCTION = (
    "Context is {used:.0f}% used, at or past the {threshold:.0f}% recycle threshold. "
    "Run the handoff skill now: write next-step, and write the "
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


def hook_payload_from_stdin() -> dict:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def context_used_percentage(session_id: str):
    """Return the session's used-context share, or None if unreported."""
    relay = read_json_file(RELAY_DIRECTORY / f"{session_id}-context.json")
    if not relay:
        return None
    remaining = relay.get("remaining_percentage")
    if not isinstance(remaining, (int, float)):
        return None
    return 100.0 - remaining


def context_window_for(model: str) -> int:
    """Return the model's context window in tokens."""
    for prefix, window in CONTEXT_WINDOW_TOKENS_BY_MODEL_PREFIX.items():
        if model.startswith(prefix):
            return window
    return DEFAULT_CONTEXT_WINDOW_TOKENS


def newest_assistant_message(path: Path):
    """Return the newest assistant record's message, reading from the end.

    Only the last request's usage matters, so the file is read backwards in
    chunks rather than parsed front to back — a transcript grows all session,
    and this hook runs at every turn boundary. The window doubles until the
    record is found or the whole file has been read, so a run of oversized
    tool-result records cannot hide it.
    """
    file_size = path.stat().st_size
    window = FIRST_TAIL_READ_BYTES

    while True:
        with path.open("rb") as handle:
            start = max(0, file_size - window)
            handle.seek(start)
            chunk = handle.read()

        lines = chunk.split(b"\n")
        if start > 0:
            lines = lines[1:]  # the first line is a fragment of an earlier record

        for raw_line in reversed(lines):
            if not raw_line.strip():
                continue
            try:
                record = json.loads(raw_line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if record.get("type") != "assistant":
                continue
            message = record.get("message", {})
            if message.get("usage"):
                return message

        if start == 0:
            return None  # whole file read, no assistant record with usage
        window *= 2


def context_used_percentage_from_transcript(transcript_path: str):
    """Return the session's used-context share, read from its transcript.

    The path for headless sessions, which never run a status line and so never
    produce a relay file. Every assistant record carries both the model and the
    usage of the request that produced it; the newest record's input plus
    cached tokens is what the model last had in front of it, and the model id
    gives the window to divide by.
    """
    if not transcript_path:
        return None
    path = Path(transcript_path).expanduser()
    if not path.is_file():
        return None

    try:
        message = newest_assistant_message(path)
    except OSError:
        return None
    if message is None:
        return None

    usage = message["usage"]
    used_tokens = sum(
        usage.get(field, 0) or 0
        for field in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
    )
    return 100.0 * used_tokens / context_window_for(message.get("model", ""))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fire the handoff skill when context runs low.")
    parser.add_argument("--threshold-used-percentage", type=float, default=50.0)
    parser.add_argument(
        "--agent", default="",
        help="agent name; when given, the hook stays silent unless that agent's supervisor is alive",
    )
    arguments = parser.parse_args(argv)

    payload = hook_payload_from_stdin()
    session_id = payload.get("session_id", "")
    if not session_id:
        return 0  # no session to reason about; stay silent

    # The transcript is the primary source: every session has one, headless
    # included. The relay file is the fallback for the case the transcript
    # cannot answer — a session whose first turn has not completed yet.
    used = context_used_percentage_from_transcript(payload.get("transcript_path", ""))
    if used is None:
        used = context_used_percentage(session_id)
    if used is None or used < arguments.threshold_used_percentage:
        return 0  # nothing measurable yet, or still plenty of room

    if arguments.agent and not supervisor.supervisor_liveness(
        RELAY_DIRECTORY / f"{arguments.agent}-supervisor-state.json"
    )[0]:
        return 0  # nobody is watching; asking for a handoff would hang the session

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
