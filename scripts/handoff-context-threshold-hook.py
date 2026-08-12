#!/usr/bin/env python3
"""Tell a session to write its handoff once context runs low.

The handoff system's auto-trigger (specification:
docs/cross-project/fast-handoff-design.md). Wire it as a Stop hook in
settings.json; it runs at every turn boundary.

Stop-hook stdin does not carry the context window, so the used share is
computed from the session's own transcript: every assistant record carries
the model and the token usage of the request that produced it. That works
in every session type, headless included — a statusline-relay fallback was
cut 2026-08-12 because its only remaining trigger was a session whose first
turn had not completed, a moment the threshold cannot be crossed. A
supervisor-liveness gate (silent unless --agent's supervisor was alive) was
cut the same day: since self-registration (2026-08-06) a firing with no
supervisor watching starts an adopting one, so silence only ever turned a
dead supervisor into a permanent stall.

When the used share reaches the threshold, the hook emits a system message
telling the agent to run the handoff skill; the supervisor takes over from
there. Below the threshold it stays silent.

It fires ONCE per session: after firing it records the fact in the handoff
directory, so the reminder does not repeat at every subsequent turn while
the agent is composing the handoff.

Threshold: --threshold-used-percentage, default 50.
"""

import argparse
import json
import sys
from pathlib import Path

HANDOFF_DIRECTORY = Path.home() / ".claude" / "handoffs"

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

# The skill carries the whole procedure. A hook message that restated any of it
# would be a second copy going stale on its own schedule, which this one did
# twice in a day: once when boundary judgment was removed, once when the writer
# took over the fields.
HANDOFF_INSTRUCTION = "Run the handoff skill now."


def hook_payload_from_stdin() -> dict:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


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

    Every assistant record carries both the model and the
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
    arguments = parser.parse_args(argv)

    payload = hook_payload_from_stdin()
    session_id = payload.get("session_id", "")
    if not session_id:
        return 0  # no session to reason about; stay silent

    # Every session has a transcript, headless included; before the first
    # assistant turn completes there is nothing to measure and nothing near
    # the threshold either, so None simply stays silent.
    used = context_used_percentage_from_transcript(payload.get("transcript_path", ""))
    if used is None or used < arguments.threshold_used_percentage:
        return 0  # nothing measurable yet, or still plenty of room

    fired_marker = HANDOFF_DIRECTORY / f"{session_id}-handoff-asked"
    if fired_marker.exists():
        return 0  # already asked this session; do not nag every turn

    try:
        fired_marker.write_text(f"{used:.1f}\n", encoding="utf-8")
    except OSError:
        pass

    print(
        HANDOFF_INSTRUCTION,
        file=sys.stderr,
    )
    return 2  # exit 2 surfaces stderr to the agent as a system message


if __name__ == "__main__":
    sys.exit(main())
