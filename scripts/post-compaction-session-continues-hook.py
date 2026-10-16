#!/usr/bin/env python3
"""Restore a compacted session's dialog tail and tell the session to continue.

SessionStart stdout injects context, not a new turn. Claude Code reads that
stdout only on exit 0, so a fault that costs only part of the job, the dialog
tail or the clearing of the threshold hook's fired marker, keeps exit 0 and
the continue instruction, and names the fault in a line of the injected text.

A fault that costs the whole job, such as stdin that is not a JSON object or
any exception main() does not expect: one line on stderr naming the hook and
the fault, nothing on stdout, exit 1. Claude Code records a SessionStart exit 1
as a non-blocking error and the session starts; exit 2 is never used."""

import importlib.util
import json
import pathlib
import sys

EXTRACT_SCRIPT = "handoff-extract-conversation.py"
THRESHOLD_SCRIPT = "handoff-context-threshold-hook.py"

# Load siblings inside main's guard so import failures cannot suppress the continue instruction.
_LOADED_SIBLINGS = {}


def sibling_module(file_name, module_name):
    """Return a cached sibling module; raise the load's error each time a failed one is asked for."""
    if module_name not in _LOADED_SIBLINGS:
        try:
            spec = importlib.util.spec_from_file_location(
                module_name, pathlib.Path(__file__).with_name(file_name))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            _LOADED_SIBLINGS[module_name] = module
        except Exception as error:
            _LOADED_SIBLINGS[module_name] = error
    loaded = _LOADED_SIBLINGS[module_name]
    if isinstance(loaded, Exception):
        raise loaded
    return loaded

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

FAULT_LINE = PROGRAM + ": {what} failed, so {cost}: {error}"
MARKER_NOT_CLEARED_COST = ("the handoff threshold hook's fired marker for this session"
                           " was not cleared and that hook will not ask for a handoff again"
                           " in this session")
# The marker's path is defined only in the threshold hook, so without it the line names the session.
MARKER_PATH_UNKNOWN_INSTRUCTION = (
    "Tell the user that the fired marker for session {session_id} was not deleted. Its path"
    " cannot be named here, because only " + THRESHOLD_SCRIPT + " defines it and {reason}."
    " The marker is safe to delete by hand.")
MARKER_PATH_NOT_CLEARED_INSTRUCTION = ("Tell the user that {path} was not deleted; it is safe to"
                                       " delete by hand.")
TAIL_NOT_RECOVERED_COST = "no tail of this session's dialog is given below"

# The extractor walks back to a user turn without a ceiling; cap injection to preserve freed context.
MAXIMUM_INJECTED_TAIL_WORDS = 3000


def hook_payload_from_stdin() -> dict:
    """Return the stdin payload; raise when it is not a JSON object."""
    payload = json.loads(sys.stdin.read())
    if not isinstance(payload, dict):
        raise ValueError("the input on the hook's stdin is JSON, but not an object")
    return payload


def start_source(payload: dict) -> str:
    # SessionStart uses source; session_start_reason is a fallback only.
    for key in ("source", "session_start_reason"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def fault_line(what: str, cost: str, error: Exception) -> str:
    return FAULT_LINE.format(what=what, cost=cost, error=f"{type(error).__name__}: {error}")


def clear_fired_marker(session_id: str) -> str:
    """Remove the marker; return "" when it is gone or was never there, else a fault line."""
    # Compaction keeps the session id; leaving the marker would prevent future handoffs.
    if not session_id:
        return ""
    try:
        threshold = sibling_module(THRESHOLD_SCRIPT, "handoff_context_threshold_hook")
    except Exception as error:
        return (fault_line(f"loading {THRESHOLD_SCRIPT}", MARKER_NOT_CLEARED_COST, error)
                + "\n" + MARKER_PATH_UNKNOWN_INSTRUCTION.format(
                    session_id=session_id, reason="that file could not be loaded"))
    marker = None
    try:
        marker = threshold.fired_marker_path(session_id)
        marker.unlink()
    except FileNotFoundError:
        return ""
    except Exception as error:
        instruction = (
            MARKER_PATH_UNKNOWN_INSTRUCTION.format(
                session_id=session_id, reason="its fired_marker_path() failed")
            if marker is None else MARKER_PATH_NOT_CLEARED_INSTRUCTION.format(path=marker))
        return (fault_line("clearing the fired marker", MARKER_NOT_CLEARED_COST, error)
                + "\n" + instruction)
    return ""


def recovered_tail(transcript_path_text: str):
    """Return (transcript tail, fault line); the tail is "" when there is none, and
    the fault line is "" unless reading or rendering the tail failed."""
    # Compaction rewrites the transcript; an unreadable tail must not suppress the continue instruction.
    if not transcript_path_text:
        return "", ""
    try:
        extract = sibling_module(EXTRACT_SCRIPT, "handoff_extract_conversation")
        transcript_path = pathlib.Path(transcript_path_text)
        if not transcript_path.is_file():
            return "", ""
        turns, _skip_counts = extract.read_dialog_turns(transcript_path)
        if not turns:
            return "", ""
        selected, _start_index = extract.select_tail_clearing_floor(turns)
        selected = turns_within_injected_tail_ceiling(selected)
        return render_turns(selected), ""
    except Exception as error:
        return "", fault_line("recovering the dialog tail", TAIL_NOT_RECOVERED_COST, error)


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


def injected_context(tail: str, fault_lines=()) -> str:
    """Return continuation instructions, any fault lines, and the recovered tail."""
    lines = list(CONTINUE_INSTRUCTION_LINES)
    lines.extend(line for line in fault_lines if line)
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
        marker_fault = clear_fired_marker(session_id if isinstance(session_id, str) else "")
        transcript_path_text = payload.get("transcript_path")
        tail, tail_fault = recovered_tail(
            transcript_path_text if isinstance(transcript_path_text, str) else ""
        )
        emit(injected_context(tail, (marker_fault, tail_fault)))
    except Exception as error:
        print(f"{PROGRAM}: the session was not told to continue after compaction, because "
              f"the hook failed; the session starts as usual: {type(error).__name__}: {error}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
