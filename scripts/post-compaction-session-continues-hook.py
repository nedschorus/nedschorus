#!/usr/bin/env python3
"""A compacted session is handed its own tail back and told to continue.

WHY, measured rather than assumed. Compaction replaces a session's context
with a summary and then STOPS: the agent sits idle until a human types. On
2026-09-20 the merge-lane seat crossed its handoff threshold at 22:30:33Z and
65% at 22:35:27Z with ZERO turn boundaries until 23:20:45Z -- one fifty-minute
agentic turn -- so the threshold hook, which is a Stop hook and can only run at
a turn boundary, did not fire until 97.2%. Compaction then kept the session id.

Two things follow from the id being kept, and this hook answers both:

1. The session stops. The user ruled the fix on 2026-09-20: "the post-compact
   hook can read the last 1000 words of the scrubbed jsonl and then be told to
   continue (usually I think it just stops)." The one channel this hook is
   documented to have is its stdout, which the hooks reference says Claude Code
   "adds ... as context that Claude can see and act on" -- context, not a turn.
   So "continue" is phrased INSIDE the injected context rather than asked for
   through a restart mechanism. Precise about what is documented and what is
   not, because the two get confused here (checked 2026-09-22 against
   https://code.claude.com/docs/en/hooks): the reference distinguishes `manual`
   from `auto` compaction as a trigger and says nothing about what the session
   does after either, so the stall above is this fleet's measurement, not a
   documented behaviour; and `initialUserMessage`, which gets cited as a way to
   make a session act, is not in that reference at all, so nothing here rests
   on it.

2. Reincarnation is quietly retired. The fired marker is named for the session
   and is once-per-session, so a kept id means the marker still stands and the
   threshold hook will never ask again. A seat that compacts repeatedly would
   hand off never. Clearing the marker here re-arms it.

THE CONTRACT, MEASURED ON CLAUDE CODE 2.1.277, 2026-09-20. A throwaway hook
whose whole body was `cat > <file>`, wired with no matcher and run under
`claude --settings <probe>`, captured the payload for an ordinary start and
again after a real `/compact` driven under tmux:

    {"session_id": ..., "transcript_path": ..., "cwd": ...,
     "hook_event_name": "SessionStart", "source": "startup" | "compact",
     "model": ..., "scratchpad_dir": ..., "prompt_id": ...}

The field is `source`. There is NO `session_start_reason` key, contrary to the
contract this build started from -- which is why it is read first here and the
other name only as a fallback, rather than the other way round. `matcher` was
measured in both directions on the same version: "startup" fired on a startup,
"compact" did not, so the settings entry's `"matcher": "compact"` filters and
this hook is not reached on an ordinary start.

EXIT 2 PREVENTS THE SESSION FROM STARTING, so nothing here may exit 2 under
any condition -- a bug that did would brick the seat it is meant to rescue.
Every path returns 0, the same reason scripts/checkout-freshness-catch-up.py
does, and every read is wrapped: the transcript is being read moments after
the harness rewrote it, so a partial final record is ordinary. That is also
why the sibling scripts are loaded inside main()'s guard rather than at
import -- module scope is the one place the guard cannot reach. MEASURED
2026-09-20 on the module-scope form this replaced: with the extractor absent
the hook exited 1 on a traceback and emitted NOTHING, so the optional half of
the job took down the essential half. The session still started, exit 1 being
harmless where exit 2 is not, but it was never told to continue.

THE TAIL IS RECORD-AWARE, and not built here. A byte tail of the transcript
does not give 1000 words of conversation: the predecessor session was 2,580
records of which 97 individually exceeded the whole budget, the largest about
95,000 words, and those giant records cluster around heavy tool work -- which
is exactly when compaction fires. scripts/handoff-extract-conversation.py
already walks records backwards, drops harness-injected records and their
short acknowledgements, and selects a tail clearing a word floor; this hook
imports that rather than carrying a second classifier that would drift from
it. Dropping tool results is also what makes the tail scrubbed: a token value
could only appear in a result that echoed one.

THE TAIL HAS A CEILING AS WELL AS A FLOOR, and the ceiling belongs to this
hook alone. The extractor's floor is right for the handoff FILE, which a
person reads on disk and can skim; it is wrong for an injection into a context
window, which is the one resource a compaction just spent itself to free.
MAXIMUM_INJECTED_TAIL_WORDS below carries the measurement and the arithmetic.
scripts/handoff-extract-conversation.py is deliberately left alone: its other
callers write files, not context.

The injected text is instruction and nothing else (user-ruled 2026-09-18). Its
reasons are here, where maintainers read them.
"""

import importlib.util
import json
import pathlib
import sys

EXTRACT_SCRIPT = "handoff-extract-conversation.py"
THRESHOLD_SCRIPT = "handoff-context-threshold-hook.py"

# Siblings are loaded at CALL time, inside main()'s guard, never at import.
# Module scope is the one place that guard cannot reach, and a sibling that
# has been renamed or moved must cost this hook its TAIL, not its CONTINUE
# INSTRUCTION. Renames happen here -- PR "main-gatekeeper moves whole into
# nc-systems/main-gatekeeper/: code, tests, design, record" moved a whole
# program, PR "Wiki pages carry the nedschorus- prefix" renamed four pages --
# so this is a named behaviour, not a hypothetical.
_LOADED_SIBLINGS = {}


def sibling_module(file_name, module_name):
    """Return a sibling script loaded as a module, or None if it will not load.

    The result is cached per process, the None included, so a sibling that is
    missing is answered the same way every time it is asked for in one run.
    """
    if module_name not in _LOADED_SIBLINGS:
        _LOADED_SIBLINGS[module_name] = None
        try:
            spec = importlib.util.spec_from_file_location(
                module_name, pathlib.Path(__file__).with_name(file_name))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            _LOADED_SIBLINGS[module_name] = module
        except Exception:
            pass  # a missing or broken sibling costs the tail, never the start
    return _LOADED_SIBLINGS[module_name]

PROGRAM = "post-compaction-session-continues-hook"

# The one `source` value this hook acts on. Every other value returns 0 in
# silence, so a mis-wired settings entry with no matcher costs nothing.
COMPACTION_SOURCE = "compact"

# Instruction, one line each, with the condition each applies under.
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

# The ceiling on the dialog this hook injects, in words. The extractor's floor
# underneath it is MINIMUM_DIALOG_WORDS = 1000: it selects a tail clearing 1000
# words and then walks back to the nearest earlier USER turn, and NOTHING
# bounds that second walk. MEASURED at the commit this one sits on, HOME
# redirected to a temporary directory: a transcript of one user prompt followed
# by 300 agent turns injected 40,062 words, 271 KiB -- roughly 50,000 tokens
# handed straight back to a session that had just compacted to free context.
# That shape is not exotic, it is the shape that CAUSES a compaction: a long
# agentic stretch with no user turn in it. The same transcript with user turns
# interleaved injected 1,088 words, which is the floor rule working as intended.
#
# 3000 is three times the floor: a tail always clears its 1000 words and keeps
# 2000 more as headroom for the walk back to a user prompt, while the whole
# injection stays near 4,000 tokens -- a fiftieth of a 200k window, and a
# thirteenth of what the measurement above hands back. The floor's own note
# records which way the asymmetry runs: a starved session re-reads the
# transcript it is pointed at once, a fat one taxes every compaction.
MAXIMUM_INJECTED_TAIL_WORDS = 3000


def hook_payload_from_stdin() -> dict:
    """Return the hook's stdin payload, or {} if it is unusable."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def start_source(payload: dict) -> str:
    """Return the payload's start reason.

    `source` is the measured field name on 2.1.277; `session_start_reason` is
    read only if it is absent, because a renamed field would otherwise make
    this hook silently never fire -- the failure this project most dislikes.
    """
    for key in ("source", "session_start_reason"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def clear_fired_marker(session_id: str) -> bool:
    """Delete this session's fired handoff marker; True if one was removed.

    A compaction keeps the session id, so without this the marker written
    before the compaction would stand for the life of the session and the
    threshold hook would never ask for a handoff again.
    """
    if not session_id:
        return False
    threshold = sibling_module(THRESHOLD_SCRIPT, "handoff_context_threshold_hook")
    if threshold is None:
        return False  # the module that names the marker is gone; nothing to do
    try:
        marker = threshold.fired_marker_path(session_id)
        marker.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def recovered_tail(transcript_path_text: str) -> str:
    """Return the record-aware tail of the transcript, or "" if unavailable.

    Never raises. The transcript is read moments after the harness rewrote it
    for the compaction, so an unreadable or half-written file is ordinary and
    silence is the right answer -- the continue instruction is the fix for the
    stall, and it is emitted whether or not a tail was recovered.
    """
    if not transcript_path_text:
        return ""
    extract = sibling_module(EXTRACT_SCRIPT, "handoff_extract_conversation")
    if extract is None:
        return ""  # no extractor, so no tail; the continue instruction stands
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
        # Inside the try, not after it: the docstring promises never to raise,
        # and a raise here costs the CONTINUE INSTRUCTION, not just the tail --
        # main()'s handler would return 0 having emitted nothing. Unreachable
        # with today's extractor, which always yields {"voice", "text"} dicts,
        # and the extractor is a separate program with other callers.
        return render_turns(selected)
    except Exception:
        return ""


def turn_words(turn) -> int:
    """Return one turn's word count, counted the way the extractor counts."""
    return len((turn.get("text") or "").split())


def turns_within_injected_tail_ceiling(
        turns, maximum_words: int = MAXIMUM_INJECTED_TAIL_WORDS):
    """Return the widest contiguous run of whole turns that fits the ceiling.

    The run ends at the newest turn that fits the ceiling on its own, and is
    filled backwards -- newest first, because the work a continuing session
    resumes is the work it did last. Whole turns only: a turn cut in half
    would hand the session half a sentence and no way to tell it was cut.

    A turn wider than the whole ceiling can never fit, so the fill steps over
    it and takes the dialog behind it, which is what the record-aware tail
    exists to do -- stopping there would leave a session whose last act was
    writing a long document inline with no tail at all, the very answer a
    byte tail would have given. A run of them leaves the tail empty, and an
    empty tail is a case the injected instructions already name.
    """
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
    """Render dialog turns as the injected tail, oldest first."""
    blocks = []
    for turn in turns:
        voice = "User" if turn.get("voice") == "user" else "Agent"
        text = (turn.get("text") or "").strip()
        if not text:
            continue
        blocks.append("## {}\n\n{}".format(voice, text))
    return "\n\n".join(blocks)


def injected_context(tail: str) -> str:
    """Return the text handed to the restarted session."""
    lines = list(CONTINUE_INSTRUCTION_LINES)
    if tail:
        lines.append(TAIL_HEADING)
        lines.append(tail)
    return "\n\n".join(lines)


def emit(context_text: str) -> None:
    """Print the SessionStart payload that adds context to the agent."""
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context_text,
        }
    }
    # ensure_ascii=False: the dialog carries em dashes, and a — in an
    # injected line is a character the reader has to decode.
    print(json.dumps(payload, ensure_ascii=False))


def main(argv=None) -> int:
    """Always return 0. Exit 2 would stop the session starting at all."""
    try:
        payload = hook_payload_from_stdin()
        if start_source(payload) != COMPACTION_SOURCE:
            return 0  # an ordinary start, a resume, a clear or a fork
        session_id = payload.get("session_id")
        clear_fired_marker(session_id if isinstance(session_id, str) else "")
        transcript_path_text = payload.get("transcript_path")
        tail = recovered_tail(
            transcript_path_text if isinstance(transcript_path_text, str) else ""
        )
        emit(injected_context(tail))
    except Exception:
        # Nothing this hook can hit is worth costing the seat its start.
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
