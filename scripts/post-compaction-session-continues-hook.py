#!/usr/bin/env python3
"""Restore a compacted session's dialog tail and tell the session to continue.

SessionStart stdout injects context, not a new turn. Exit 2 prevents startup,
so failures must not block the session."""

import importlib.util
import json
import pathlib
import sys

EXTRACT_SCRIPT = "handoff-extract-conversation.py"
THRESHOLD_SCRIPT = "handoff-context-threshold-hook.py"

# Load siblings inside main's guard so import failures cannot suppress the continue instruction.
_LOADED_SIBLINGS = {}


def sibling_module(file_name, module_name):
    """Return a cached sibling module, or None if loading fails."""
    if module_name not in _LOADED_SIBLINGS:
        _LOADED_SIBLINGS[module_name] = None
        try:
            spec = importlib.util.spec_from_file_location(
                module_name, pathlib.Path(__file__).with_name(file_name))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            _LOADED_SIBLINGS[module_name] = module
        except Exception:
            pass
    return _LOADED_SIBLINGS[module_name]

PROGRAM = "post-compaction-session-continues-hook"

COMPACTION_SOURCE = "compact"

CONTINUE_INSTRUCTION_LINES = (
    "This session was just compacted. Continue the work that was underway;"
    " do not wait to be prompted.",
    "Re-verify any in-flight state before trusting it: the tail below is what"
    " the transcript held, not a guarantee that the work is still where it"
    " left off.",
    "If the tail below is empty or says nothing about current work, say so and"
    " ask what to work on.",
)

TAIL_HEADING = "Recovered tail of this session's own dialog, oldest first:"

# The extractor walks back to a user turn without a ceiling; cap injection to preserve freed context.
MAXIMUM_INJECTED_TAIL_WORDS = 3000


def hook_payload_from_stdin() -> dict:
    """Return the stdin payload, or {} if unusable."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def start_source(payload: dict) -> str:
    # SessionStart uses source; session_start_reason is a fallback only.
    for key in ("source", "session_start_reason"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def clear_fired_marker(session_id: str) -> bool:
    """Remove the marker and return whether removal succeeded."""
    # Compaction keeps the session id; leaving the marker would prevent future handoffs.
    if not session_id:
        return False
    threshold = sibling_module(THRESHOLD_SCRIPT, "handoff_context_threshold_hook")
    if threshold is None:
        return False
    try:
        marker = threshold.fired_marker_path(session_id)
        marker.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def recovered_tail(transcript_path_text: str) -> str:
    """Return the transcript tail, or "" if unavailable."""
    # Compaction rewrites the transcript; an unreadable tail must not suppress the continue instruction.
    if not transcript_path_text:
        return ""
    extract = sibling_module(EXTRACT_SCRIPT, "handoff_extract_conversation")
    if extract is None:
        return ""
    try:
        transcript_path = pathlib.Path(transcript_path_text)
        if not transcript_path.is_file():
            return ""
        turns, _skip_counts = extract.read_dialog_turns(transcript_path)
    except Exception:
        return ""
    if not turns:
        return ""
    try:
        selected, _start_index = extract.select_tail_clearing_floor(turns)
        selected = turns_within_injected_tail_ceiling(selected)
        # Rendering failures must cost only the tail, not the continue instruction.
        return render_turns(selected)
    except Exception:
        return ""


def turn_words(turn) -> int:
    return len((turn.get("text") or "").split())


def turns_within_injected_tail_ceiling(
        turns, maximum_words: int = MAXIMUM_INJECTED_TAIL_WORDS):
    """Return the newest contiguous run of whole turns that fits the ceiling."""
    # Skip oversized final turns so a long document does not hide all earlier dialog.
    # Keep turns whole to avoid silently injecting partial sentences.
    end = len(turns)
    while end > 0 and turn_words(turns[end - 1]) > maximum_words:
        end -= 1

    start = end
    remaining = maximum_words
    while start > 0:
        words = turn_words(turns[start - 1])
        if words > remaining:
            break
        remaining -= words
        start -= 1

    return turns[start:end]


def render_turns(turns) -> str:
    """Render the injected dialog tail, oldest first."""
    blocks = []
    for turn in turns:
        voice = "User" if turn.get("voice") == "user" else "Agent"
        text = (turn.get("text") or "").strip()
        if not text:
            continue
        blocks.append("## {}\n\n{}".format(voice, text))
    return "\n\n".join(blocks)


def injected_context(tail: str) -> str:
    """Return continuation instructions with the recovered tail."""
    lines = list(CONTINUE_INSTRUCTION_LINES)
    if tail:
        lines.append(TAIL_HEADING)
        lines.append(tail)
    return "\n\n".join(lines)


def emit(context_text: str) -> None:
    """Print a SessionStart context payload."""
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context_text,
        }
    }
    print(json.dumps(payload, ensure_ascii=False))


def main(argv=None) -> int:
    try:
        payload = hook_payload_from_stdin()
        if start_source(payload) != COMPACTION_SOURCE:
            return 0
        session_id = payload.get("session_id")
        clear_fired_marker(session_id if isinstance(session_id, str) else "")
        transcript_path_text = payload.get("transcript_path")
        tail = recovered_tail(
            transcript_path_text if isinstance(transcript_path_text, str) else ""
        )
        emit(injected_context(tail))
    except Exception:
        # A hook failure must not prevent session startup.
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
