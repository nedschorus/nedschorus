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

WHILE A SUBAGENT IS RUNNING THE HANDOFF WAITS (user-ruled 2026-08-27). A
recycle kills the session, and the session's in-process subagents die with
it: on 2026-08-27 a seat dispatched a builder subagent at 20:38, the hook
fired at 50% at 20:43, and the subagent died four minutes into its job. So
at the threshold the hook first asks whether any Agent-tool subagent is
still in flight. While one is, it says so and does NOT fire — and writes no
marker, so the same question is asked again at the next turn boundary. That
is what detects the finish: a subagent's completion notification is itself
a turn, so the first boundary after the last subagent finishes is the one
that fires. The standing ruling that a recycle records its subagents rather
than waiting for them (2026-08-23, [nedschorus#153]) still governs
everything else; this deferral is its one bounded exception, and
--ceiling-used-percentage is the bound. Above the ceiling the handoff fires
whatever is running, because a session deferring to a subagent that never
finishes would run out of context instead of recycling — which is a worse
loss than the one this defers.

IN FLIGHT means spawned and not yet finished, both read from the transcript.
A spawn is a tool result carrying `status: async_launched` and an `agentId`;
a Monitor's tool result carries neither, so monitors are excluded by their
shape rather than by a guess about their ids. A finish is that agent's id
inside the `<task-id>` tag of a task-notification. The notification arrives
in more than one record shape — as a `user` record when the session is idle
enough to be interrupted, as an `attachment` plus `queue-operation` pair
when it is busy — and in the 2026-08-27 transcript six of the fourteen
finished subagents produced no `user` record at all, so the scan matches the
tag wherever in a record it appears rather than keying on one shape.

WHAT THE SCAN COSTS: the whole transcript, read once. The used share comes
from the tail, but a spawn can be hours back, so this read cannot be a tail
read. Measured at roughly 2.5 ms per megabyte: 7 ms on the 3.5 MB transcript of
the session this change came from, and 8.7 ms on the largest transcript
measured, 3.9 MB. It is paid only between the threshold and the fire:
never below the threshold, and never once the marker is written.

TWO WAYS THE SCAN CAN BE WRONG, both bounded by the ceiling. An agent
resumed by SendMessage runs again with no new spawn record, so its earlier
completion still stands and the handoff fires while it works — the behaviour
this project had before this change. A completion the scan misses defers the
handoff no further than the ceiling. A subagent stopped by TaskStop takes
the same path as any other finish and is untested, because no specimen
exists.

Threshold: --threshold-used-percentage, default 50.
Ceiling: --ceiling-used-percentage, default 65.
"""

import argparse
import json
import re
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

# The deferral says the opposite of the instruction above, so it must not read
# like it: the agent is being told to keep working, and told the one thing that
# would extend the wait indefinitely.
HANDOFF_DEFERRED_NOTICE = (
    "Context at {used_percentage:.0f}% — handoff deferred while "
    "{subagent_count} subagent(s) run. Spawn no new subagents; the handoff "
    "fires when they finish."
)

# What a spawned subagent's tool result carries and a Monitor's does not.
SPAWNED_SUBAGENT_STATUS = "async_launched"

# A completion notification names the agent that finished in this tag, in every
# record shape that carries the notification.
TASK_NOTIFICATION_TASK_ID_PATTERN = re.compile(r"<task-id>([^<]+)</task-id>")


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


def spawned_subagent_ids_in_flight(transcript_path: str) -> list:
    """Return the ids of the session's Agent-tool subagents still running.

    A subagent is in flight when the transcript holds its spawn and no
    completion notification naming it. Both halves are read from the whole
    file, not the tail: a spawn can be hours behind the newest record, and a
    session that missed one would kill a subagent it did not know about,
    which is the failure this exists to prevent (2026-08-27).

    The cheap substring test on each line is what keeps the whole-file read
    affordable — a transcript is mostly large tool results, and only the few
    lines that could matter are parsed. Cost and limits are in the module
    docstring.

    A spawn is identified structurally, by `status: async_launched` plus an
    `agentId` in the tool result. Monitors and background shell commands also
    produce task notifications, but their tool results carry no agentId, so
    they never enter the spawned set and their notifications match nothing.

    Order is spawn order, so a caller reporting the ids reports them in the
    order the agent created them.
    """
    path = Path(transcript_path).expanduser() if transcript_path else None
    if path is None or not path.is_file():
        return []

    spawned_ids = []
    finished_ids = set()
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if SPAWNED_SUBAGENT_STATUS in line:
                    try:
                        record = json.loads(line)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        record = None
                    tool_result = record.get("toolUseResult") if isinstance(record, dict) else None
                    if isinstance(tool_result, dict) and \
                            tool_result.get("status") == SPAWNED_SUBAGENT_STATUS:
                        agent_id = tool_result.get("agentId")
                        if agent_id and agent_id not in spawned_ids:
                            spawned_ids.append(agent_id)
                if "<task-id>" in line:
                    finished_ids.update(TASK_NOTIFICATION_TASK_ID_PATTERN.findall(line))
    except OSError:
        return []  # unreadable transcript: nothing known to be running

    return [agent_id for agent_id in spawned_ids if agent_id not in finished_ids]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fire the handoff skill when context runs low.")
    parser.add_argument("--threshold-used-percentage", type=float, default=50.0)
    parser.add_argument(
        "--ceiling-used-percentage", type=float, default=65.0,
        help="above this used share the handoff fires even with subagents in flight",
    )
    arguments = parser.parse_args(argv)

    payload = hook_payload_from_stdin()
    session_id = payload.get("session_id", "")
    if not session_id:
        return 0  # no session to reason about; stay silent

    transcript_path = payload.get("transcript_path", "")
    # Every session has a transcript, headless included; before the first
    # assistant turn completes there is nothing to measure and nothing near
    # the threshold either, so None simply stays silent.
    used = context_used_percentage_from_transcript(transcript_path)
    if used is None or used < arguments.threshold_used_percentage:
        return 0  # nothing measurable yet, or still plenty of room

    fired_marker = HANDOFF_DIRECTORY / f"{session_id}-handoff-asked"
    if fired_marker.exists():
        return 0  # already asked this session; do not nag every turn

    # Below the ceiling, a running subagent postpones the handoff rather than
    # dying with the session (user-ruled 2026-08-27; module docstring).
    if used < arguments.ceiling_used_percentage:
        subagents_in_flight = spawned_subagent_ids_in_flight(transcript_path)
        if subagents_in_flight:
            # Deliberately no marker. The deferral has to be re-decided at
            # every turn boundary, because the boundary that follows the last
            # completion notification is the one that fires.
            print(
                HANDOFF_DEFERRED_NOTICE.format(
                    used_percentage=used, subagent_count=len(subagents_in_flight)
                ),
                file=sys.stderr,
            )
            return 2  # exit 2 surfaces stderr to the agent as a system message

    try:
        # Nothing guarantees the directory exists this early in a session, and a
        # marker that fails to write silently means the hook nags every turn.
        HANDOFF_DIRECTORY.mkdir(parents=True, exist_ok=True)
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
