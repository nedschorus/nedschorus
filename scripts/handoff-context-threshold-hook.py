#!/usr/bin/env python3
"""Request a handoff before context runs out.

It fires at a share of the context window, or below that share once it has deferred the
handoff in this session and the work it deferred for has finished.

Stop-hook payloads lack context usage; headless sessions lack a status line.
The transcript supplies usage for both interactive and headless sessions."""

import argparse
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Every Stop hook obeys this rule first: see the module's docstring.
_stop_hooks_stay_silent_rule_specification = importlib.util.spec_from_file_location(
    "claude_code_stop_hooks_stay_silent_while_agent_answers_a_stop_hook_rule_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "claude-code-stop-hooks-stay-silent-while-agent-answers-a-stop-hook-rule-common.py")
stop_hooks_stay_silent_rule = importlib.util.module_from_spec(_stop_hooks_stay_silent_rule_specification)
_stop_hooks_stay_silent_rule_specification.loader.exec_module(stop_hooks_stay_silent_rule)

_transcript_records_specification = importlib.util.spec_from_file_location(
    "claude_code_session_transcript_records_read_backward_common",
    Path(__file__).resolve().with_name("claude-code-session-transcript-records-read-backward-common.py"))
transcript_records = importlib.util.module_from_spec(_transcript_records_specification)
_transcript_records_specification.loader.exec_module(transcript_records)

_interim_recognizer_specification = importlib.util.spec_from_file_location(
    "claude_code_subagent_task_notification_interim_recognizer_common",
    Path(__file__).resolve().with_name(
        "claude-code-subagent-task-notification-interim-recognizer-common.py"))
interim_recognizer = importlib.util.module_from_spec(_interim_recognizer_specification)
_interim_recognizer_specification.loader.exec_module(interim_recognizer)

HANDOFF_DIRECTORY = Path.home() / ".claude" / "handoffs"

# Compaction clears this shared marker because the session id survives.
FIRED_MARKER_SUFFIX = "-handoff-asked"


def fired_marker_path(session_id: str) -> Path:
    # Read HANDOFF_DIRECTORY at call time so tests can redirect marker writes.
    return HANDOFF_DIRECTORY / f"{session_id}{FIRED_MARKER_SUFFIX}"

# Caller-owned reincarnation must not replace the caller's answer with a handoff.
REINCARNATION_OWNED_BY_CALLER_VARIABLE = "NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER"

# Unknown models use the default; a wrong window silently scales the threshold.
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

FIRST_TAIL_READ_BYTES = 256 * 1024

# Messages below follow docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
# Keep the procedure in the skill so hook instructions cannot drift from it.
HANDOFF_INSTRUCTION = (
    "This session has used {share} of its context window, which has "
    "reached the reincarnation threshold. Run the /handoff skill now."
)

HANDOFF_DEFERRED_NOTICE = (
    "Context at {share} — handoff deferred while {running} run, because a "
    "handoff now would stop them.\n"
    "Do not run the /handoff skill now; carry on with your work, and a later "
    "system message will tell you when to run it. That message comes once "
    "every subagent has finished, and every background task has either "
    "finished or run for {wait_minutes:g} minutes since its launch, or once "
    "this session's context reaches the {ceiling:g}% ceiling; a handoff then "
    "stops whatever is still running.\n"
    "Spawn no new subagents and start no new background tasks, because each "
    "one delays the handoff and is stopped if still running at the ceiling."
)

HANDOFF_DEFERRED_UNKNOWN_COUNT_NOTICE = (
    "Context at {share} — handoff deferred: the transcript could not be fully "
    "read, so what is running is unknown, and a handoff now could stop it.\n"
    "Do not run the /handoff skill now; carry on with your work, and a later "
    "system message will tell you when to run it. That message comes once "
    "the hook can read the whole transcript and finds nothing running, or "
    "once this session's context reaches the {ceiling:g}% ceiling; a handoff "
    "then stops whatever is still running.\n"
    "Spawn no new subagents and start no new background tasks, because each "
    "one delays the handoff and is stopped if still running at the ceiling."
)

# Allow a slow cold-read cell plus one retry; the context ceiling still bounds deferral.
DEFAULT_BACKGROUND_TASK_WAIT_MINUTES = 75.0

# Covers a subagent just woken by its own background task, before it has launched or written more.
SUBAGENT_OWN_TRANSCRIPT_RECENT_WRITE_SECONDS = 5 * 60

class TranscriptCouldNotBeFullyRead(Exception):
    """An incomplete scan must not be mistaken for no work in flight."""


SPAWNED_SUBAGENT_STATUS = "async_launched"

# Check a toolUseResult key, not raw text: foreground grep output can contain the launch marker.
BACKGROUND_TASK_LAUNCH_KEY = "backgroundTaskId"

# Completion notifications use these tags across several record types.
TASK_NOTIFICATION_PATTERN = re.compile(r"<task-notification>(.*?)</task-notification>", re.S)
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
    """Return the newest assistant message with usage."""
    # Read backwards to avoid parsing the whole session at every turn boundary.
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
            return None
        window *= 2


def context_used_tokens_and_window_from_transcript(transcript_path: str):
    """Return (used context tokens, context window tokens), or None when unavailable."""
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

    return used_tokens_of(message["usage"]), context_window_for(message.get("model", ""))


def context_used_percentage_from_transcript(transcript_path: str):
    """Return used context as a percentage, or None when unavailable."""
    reading = context_used_tokens_and_window_from_transcript(transcript_path)
    if reading is None:
        return None
    used_tokens, window = reading
    return 100.0 * used_tokens / window


USED_TOKEN_FIELDS = ("input_tokens", "cache_read_input_tokens",
                     "cache_creation_input_tokens")
USAGE_ITERATIONS_FIELD = "iterations"
OWN_PASS_ITERATION_TYPE = "message"


def used_tokens_of(usage: dict) -> int:
    """Return the largest context used by this model's own passes."""
    # Top-level usage sums iterations; advisor passes use a different context and must be excluded.
    iterations = usage.get(USAGE_ITERATIONS_FIELD)
    if isinstance(iterations, list):
        own_passes = [
            sum(entry.get(field, 0) or 0 for field in USED_TOKEN_FIELDS)
            for entry in iterations
            if isinstance(entry, dict)
            and entry.get("type", OWN_PASS_ITERATION_TYPE) == OWN_PASS_ITERATION_TYPE
        ]
        if own_passes:
            return max(own_passes)
    return sum(usage.get(field, 0) or 0 for field in USED_TOKEN_FIELDS)


class WorkInFlight:
    """An empty scan must be falsy; a tuple of two empty lists would still be truthy."""

    def __init__(self, subagent_ids, background_task_ids):
        self.subagent_ids = list(subagent_ids)
        self.background_task_ids = list(background_task_ids)

    def __bool__(self):
        return bool(self.subagent_ids or self.background_task_ids)


def running_phrase(flight: WorkInFlight) -> str:
    """Return counts of the kinds of work in flight."""
    parts = []
    if flight.subagent_ids:
        parts.append(f"{len(flight.subagent_ids)} subagent(s)")
    if flight.background_task_ids:
        parts.append(f"{len(flight.background_task_ids)} background task(s)")
    return " and ".join(parts)


def record_age_seconds(record, now):
    """Return seconds since the record timestamp, or None if unreadable."""
    # Python before 3.11 requires replacing the ISO 8601 trailing Z for fromisoformat.
    stamp = record.get("timestamp") if isinstance(record, dict) else None
    if not isinstance(stamp, str):
        return None
    try:
        launched_at = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if launched_at.tzinfo is None:
        launched_at = launched_at.replace(tzinfo=timezone.utc)
    return (now - launched_at).total_seconds()


def spawned_subagent_ids_in_flight(transcript_path: str) -> list:
    """Return Agent-tool ids the session transcript's notices leave running, excluding
    background Bash tasks."""
    return work_in_flight(transcript_path, background_task_wait_seconds=0,
                          should_read_subagent_own_transcripts=False).subagent_ids


def work_in_flight(transcript_path: str, background_task_wait_seconds: float,
                   now=None, should_read_subagent_own_transcripts=True,
                   should_raise_on_undecodable_bytes=False) -> WorkInFlight:
    """Return running subagents and background tasks in launch order.

    A subagent whose last task-notification is interim counts only while its own transcript
    shows work in flight; should_read_subagent_own_transcripts=False counts it from the notices alone.
    should_raise_on_undecodable_bytes=True raises TranscriptCouldNotBeFullyRead on bytes that are
    not UTF-8 anywhere in the file, instead of reading past them.
    """
    # Scan the whole transcript: a running task may have launched hours before the tail.
    # Unreadable candidates raise; treating an incomplete scan as empty could kill running work.
    path = Path(transcript_path).expanduser() if transcript_path else None
    if path is None or not path.is_file():
        return WorkInFlight([], [])
    if now is None:
        now = datetime.now(timezone.utc)

    spawned_ids = []
    launched_task_ids = []
    launched_task_age = {}
    # The last notification for a task-id decides: an interim one leaves its subagent running.
    last_notification_is_interim = {}
    try:
        decoding_errors = "strict" if should_raise_on_undecodable_bytes else "replace"
        with path.open("r", encoding="utf-8", errors=decoding_errors) as handle:
            for line in handle:
                is_spawn_candidate = SPAWNED_SUBAGENT_STATUS in line
                is_launch_candidate = BACKGROUND_TASK_LAUNCH_KEY in line
                if is_spawn_candidate or is_launch_candidate:
                    try:
                        record = json.loads(line)
                    except (json.JSONDecodeError, UnicodeDecodeError) as problem:
                        raise TranscriptCouldNotBeFullyRead(
                            f"{path}: a spawn or launch record did not parse"
                        ) from problem
                    tool_result = record.get("toolUseResult") if isinstance(record, dict) else None
                    if not isinstance(tool_result, dict):
                        tool_result = {}
                    if is_spawn_candidate and \
                            tool_result.get("status") == SPAWNED_SUBAGENT_STATUS:
                        agent_id = tool_result.get("agentId")
                        if agent_id and agent_id not in spawned_ids:
                            spawned_ids.append(agent_id)
                    if is_launch_candidate:
                        task_id = tool_result.get(BACKGROUND_TASK_LAUNCH_KEY)
                        if task_id and task_id not in launched_task_age:
                            launched_task_ids.append(task_id)
                            launched_task_age[task_id] = record_age_seconds(record, now)
                if "<task-id>" in line:
                    for notification in TASK_NOTIFICATION_PATTERN.findall(line):
                        interim = interim_recognizer.task_notification_is_interim(notification)
                        for task_id in TASK_NOTIFICATION_TASK_ID_PATTERN.findall(notification):
                            last_notification_is_interim[task_id] = interim
    except (OSError, UnicodeDecodeError) as problem:
        raise TranscriptCouldNotBeFullyRead(f"{path}: {problem}") from problem

    finished_ids = {task_id for task_id, interim in last_notification_is_interim.items()
                    if not interim}

    def still_within_wait(task_id):
        age = launched_task_age[task_id]
        return age is None or age <= background_task_wait_seconds

    def subagent_still_in_flight(agent_id):
        if agent_id in finished_ids:
            return False
        # A subagent with no notice yet has not stopped once; only an interim last notice is doubted.
        if agent_id not in last_notification_is_interim or not should_read_subagent_own_transcripts:
            return True
        return subagent_own_transcript_shows_work_in_flight(
            subagent_transcript_path(path, agent_id), background_task_wait_seconds, now)

    return WorkInFlight(
        [agent_id for agent_id in spawned_ids if subagent_still_in_flight(agent_id)],
        [task_id for task_id in launched_task_ids
         if task_id not in finished_ids and still_within_wait(task_id)],
    )


def subagent_transcript_path(session_transcript_path, agent_id) -> Path:
    """Return where Claude Code writes the subagent's own transcript, beside the session's."""
    return Path(session_transcript_path).with_suffix("") / "subagents" / f"agent-{agent_id}.jsonl"


def subagent_own_transcript_shows_work_in_flight(subagent_path: Path,
                                                 background_task_wait_seconds: float,
                                                 now) -> bool:
    """Return True while the subagent's own transcript was written within the recent-write
    window, or shows a background task of its own still within its wait.

    A missing transcript shows neither, so the subagent counts as finished. One that cannot be
    looked up or read, or holds bytes that are not UTF-8, raises TranscriptCouldNotBeFullyRead.
    """
    # Path.is_file() returns False on any failed stat, which would release a subagent whose
    # transcript exists but cannot be reached.
    try:
        subagent_path.stat()
    except FileNotFoundError:
        return False
    except OSError as problem:
        raise TranscriptCouldNotBeFullyRead(f"{subagent_path}: {problem}") from problem
    try:
        for record in transcript_records.records_newest_first(subagent_path):
            age = record_age_seconds(record, now)
            if age is not None:
                if age <= SUBAGENT_OWN_TRANSCRIPT_RECENT_WRITE_SECONDS:
                    return True
                break
    except (OSError, UnicodeDecodeError) as problem:
        raise TranscriptCouldNotBeFullyRead(f"{subagent_path}: {problem}") from problem
    return bool(work_in_flight(str(subagent_path), background_task_wait_seconds, now=now,
                               should_raise_on_undecodable_bytes=True).background_task_ids)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fire the handoff skill when context runs low.")
    parser.add_argument("--threshold-used-percentage", type=float, default=33.0)
    parser.add_argument(
        "--ceiling-used-percentage", type=float, default=65.0,
        help="above this used share the handoff fires even with work in flight",
    )
    parser.add_argument(
        "--background-task-wait-minutes", type=float,
        default=DEFAULT_BACKGROUND_TASK_WAIT_MINUTES,
        help="a background Bash task older than this no longer holds the handoff: "
             "it is presumed stuck or open-ended",
    )
    arguments = parser.parse_args(argv)

    if os.environ.get(REINCARNATION_OWNED_BY_CALLER_VARIABLE):
        return 0

    payload = hook_payload_from_stdin()
    if stop_hooks_stay_silent_rule.stop_hook_stays_silent_while_agent_answers_a_stop_hook(payload):
        return 0
    session_id = payload.get("session_id", "")
    if not session_id:
        return 0

    transcript_path = payload.get("transcript_path", "")
    reading = context_used_tokens_and_window_from_transcript(transcript_path)
    if reading is None:
        return 0
    used_tokens, window = reading
    used = 100.0 * used_tokens / window
    share = f"{used:.0f}%"
    # A compaction can drop the share below the threshold after a deferral; the deferred marker
    # records that the threshold was passed, so the handoff its notice promised still comes.
    if used < arguments.threshold_used_percentage and not (
            HANDOFF_DIRECTORY / f"{session_id}-handoff-deferred").exists():
        return 0

    fired_marker = fired_marker_path(session_id)
    if fired_marker.exists():
        return 0

    # Reincarnation kills in-process work; defer below the ceiling so work can finish.
    if used < arguments.ceiling_used_percentage:
        # An incomplete scan is not an all-clear; defer only as far as the context ceiling.
        try:
            flight = work_in_flight(
                transcript_path, arguments.background_task_wait_minutes * 60)
            count_is_known = True
        except TranscriptCouldNotBeFullyRead:
            flight = None
            count_is_known = False

        if not count_is_known or flight:
            deferred_marker = HANDOFF_DIRECTORY / f"{session_id}-handoff-deferred"
            if deferred_marker.exists():
                return 0  # Repeating the refusal would drive idle sessions into a loop; completion notifications wake them.

            try:
                HANDOFF_DIRECTORY.mkdir(parents=True, exist_ok=True)
                deferred_marker.write_text(f"{used:.1f}\n", encoding="utf-8")
            except OSError:
                pass

            notice = (
                HANDOFF_DEFERRED_NOTICE.format(
                    share=share, running=running_phrase(flight),
                    wait_minutes=arguments.background_task_wait_minutes,
                    ceiling=arguments.ceiling_used_percentage,
                )
                if count_is_known
                else HANDOFF_DEFERRED_UNKNOWN_COUNT_NOTICE.format(
                    share=share, ceiling=arguments.ceiling_used_percentage)
            )
            print(notice, file=sys.stderr)
            return 2  # exit 2 surfaces stderr to the agent as a system message

    try:
        # A failed marker write would repeat the handoff request every turn.
        HANDOFF_DIRECTORY.mkdir(parents=True, exist_ok=True)
        fired_marker.write_text(f"{used:.1f}\n", encoding="utf-8")
    except OSError:
        pass

    print(
        HANDOFF_INSTRUCTION.format(share=share),
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
