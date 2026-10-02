#!/usr/bin/env python3
"""Select seat transcripts worth resuming.

Shared by recovery and the handoff supervisor to avoid circular imports and
keep their definitions of an empty successor aligned."""

import json
from pathlib import Path

FIRST_PROMPT_AFTER_RECORDED_EXIT_MARKER = "as it does when a session is stopped on purpose"
# A machinery-written opener can precede real work; reject only when work is also absent.
EMPTY_SUCCESSOR_MARKERS = (
    "No handoff exists yet",
    "crash recovery, nedschorus#120",
    "resumed by crash recovery",
    FIRST_PROMPT_AFTER_RECORDED_EXIT_MARKER,
)
SUBSTANTIVE_ASSISTANT_TURNS_MINIMUM = 2
# Large transcripts can hold real work even when the opener matches a successor marker.
EMPTY_SUCCESSOR_MAX_BYTES = 100_000
# The harness uses this model for error notices and filler, neither of which is work.
SYNTHETIC_ASSISTANT_MODEL = "<synthetic>"


def first_user_turn_text(transcript_path: Path) -> str:
    """Return the first non-meta user text, or "" if unreadable."""
    try:
        with transcript_path.open(encoding="utf-8", errors="replace") as stream:
            for line in stream:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("type") != "user" or record.get("isMeta"):
                    continue
                content = (record.get("message") or {}).get("content")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    return json.dumps(content)
                return ""
    except OSError:
        pass
    return ""


def substantive_turn_count(transcript_path: Path) -> int:
    """Count assistant turns with text or tool use, excluding harness messages."""
    # Replacing invalid UTF-8 preserves the death-path exit record when a transcript ends mid-character.
    count = 0
    try:
        with transcript_path.open(encoding="utf-8", errors="replace") as stream:
            for line in stream:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("type") != "assistant":
                    continue
                message = record.get("message") or {}
                if message.get("model") == SYNTHETIC_ASSISTANT_MODEL:
                    continue
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    count += 1
                elif isinstance(content, list) and any(
                        x.get("type") == "tool_use"
                        or (x.get("type") == "text" and x.get("text", "").strip())
                        for x in content if isinstance(x, dict)):
                    count += 1
    except OSError:
        pass
    return count


def newest_real_transcript(project_directory: Path):
    """Return (session id, path) for the newest real transcript, or (None, reason)."""
    if not project_directory.is_dir():
        return None, f"no harness project directory at {project_directory}"
    # UUID order is not chronological; modification time identifies the session last worked in.
    candidates = sorted(
        project_directory.glob("*.jsonl"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return None, f"no transcripts under {project_directory}"
    for transcript in candidates:
        if transcript.stat().st_size <= EMPTY_SUCCESSOR_MAX_BYTES:
            first_turn = first_user_turn_text(transcript)
            if not first_turn.strip():
                continue
            if (any(marker in first_turn for marker in EMPTY_SUCCESSOR_MARKERS)
                    and substantive_turn_count(transcript)
                        < SUBSTANTIVE_ASSISTANT_TURNS_MINIMUM):
                continue
        return transcript.stem, transcript
    return None, ("every transcript is an empty-successor session; nothing "
                  "worth resuming")
