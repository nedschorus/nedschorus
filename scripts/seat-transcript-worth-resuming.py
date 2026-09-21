#!/usr/bin/env python3
"""Which of a seat's transcripts is worth resuming — defined once.

Two programs need this judgement. scripts/recover-crashed-seats.py has always
needed it: it picks the transcript a crashed seat is resumed from.
scripts/handoff-supervisor.py needs it since issue 242's change 5, so that a
by-hand `launch-claude-mac <seat>` resumes a crashed seat instead of minting an
empty session.

It is a module and nothing else, because neither program can own it. The
dependency between them runs one way — recover-crashed-seats.py loads
handoff-supervisor.py with spec_from_file_location at its module level — and a
supervisor that loaded the recovery tool back would execute that module body a
second time as an orphan copy. Putting the judgement in the supervisor instead
would be worse in a quieter way: EMPTY_SUCCESSOR_MARKERS mixes literals the two
programs own separately, and `scripts/recover-crashed-seats-test.py`'s F8 group
asserts the supervisor-owned ones against handoff-supervisor.py's own source --
an assertion that means nothing once the thing asserted and the thing asserted
against are the same file. The convention here — importlib for a module whose
filename has hyphens — is scripts/cold-read-cell-common.py's, and the
precedent for a module that exists only to stop two programs drifting is
scripts/cold-read-record-names.py.

It is imported, never run. A program loads it:

    _worth_resuming_spec = importlib.util.spec_from_file_location(
        "seat_transcript_worth_resuming",
        Path(__file__).with_name("seat-transcript-worth-resuming.py"))
    worth_resuming = importlib.util.module_from_spec(_worth_resuming_spec)
    _worth_resuming_spec.loader.exec_module(worth_resuming)

recover-crashed-seats.py re-exports every name below at its own module level,
so `recovery.EMPTY_SUCCESSOR_MARKERS` and the rest keep working for the
eighteen references in its test suite.
"""

import json
from pathlib import Path

# The phrase every first prompt after a recorded exit carries
# (write_first_prompt_after_recorded_exit in recover-crashed-seats.py), and so
# its marker.
FIRST_PROMPT_AFTER_RECORDED_EXIT_MARKER = "as it does when a session is stopped on purpose"
# First-turn shapes of sessions this machinery itself composes — the
# supervisor's no-handoff prompt and the recovery tool's own ignition and
# resume prompts. A marker alone writes nothing off: a first-ever session
# legitimately opens with the no-handoff prompt and then works (observed
# live 2026-08-22), and an ignited successor can crash mid-work — both must
# be resumed, not skipped for an older parent. What marks a failed successor
# is a marker AND no work: substantive_turn_count() below measures work, and
# the gate applies to every marker uniformly (round 4 finding 1 — markers
# were measured skipping real work on size alone). The supervisor-owned
# literals are asserted against the supervisor's actual source in
# recover-crashed-seats-test.py's F8 group, so a wording change there fails
# loudly.
EMPTY_SUCCESSOR_MARKERS = (
    "No handoff exists yet",            # handoff-supervisor's default first prompt
    "crash recovery, nedschorus#120",   # recovery's ignition (initial agent instructions)
    "resumed by crash recovery",        # the resume prompt of recovery AND of the supervisor
    FIRST_PROMPT_AFTER_RECORDED_EXIT_MARKER,  # recovery's prompts after a recorded exit
)
SUBSTANTIVE_ASSISTANT_TURNS_MINIMUM = 2
# The size guard: a seat's first-ever session legitimately starts with the
# no-handoff prompt and can then do real work (observed live 2026-08-22 —
# fixer1's 1880KB genuine session began exactly so, and a marker-only filter
# wrongly wrote it off). The crash-day empty successors were a few KB. A
# transcript too small to hold real work is also skipped when its first
# user turn is missing or unreadable — a 0-byte or no-user-turn file is
# not the seat's real work either (finding 3's second shape).
EMPTY_SUCCESSOR_MAX_BYTES = 100_000
# The model name the harness writes on assistant turns it authors itself --
# API error notices (a session limit, "Not logged in", 529 Overloaded,
# "Prompt is too long") and the "No response requested." filler that a
# resume of an interrupted session appends. None of them is work. Measured
# 2026-09-11 across forty days of this Mac's transcripts: every such record
# is text-only.
SYNTHETIC_ASSISTANT_MODEL = "<synthetic>"


def first_user_turn_text(transcript_path: Path) -> str:
    """The first non-meta user turn's text, or "" when none is readable."""
    try:
        with transcript_path.open(encoding="utf-8") as stream:
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
    """Assistant turns carrying text or tool use — the working measure of
    "this session did something". A failed successor dies at or before its
    first reply; a crashed-but-working one replied or called tools after the
    opener. Tool calls count because a terse tool-heavy stint is an ordinary
    seat shape (PR #131 review round 3, finding 2: text-only counting wrote
    off a successor whose work was 12 tool calls and one reply). The
    harness's own turns are not counted (SYNTHETIC_ASSISTANT_MODEL): on
    2026-09-10 a session-limit notice was a successor's only "reply"."""
    count = 0
    try:
        with transcript_path.open(encoding="utf-8") as stream:
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
    """(session_id, transcript_path) of the newest transcript that is not an
    empty-successor session, or (None, reason).
    """
    if not project_directory.is_dir():
        return None, f"no harness project directory at {project_directory}"
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
                continue  # small with no readable user turn: not real work
            if (any(marker in first_turn for marker in EMPTY_SUCCESSOR_MARKERS)
                    and substantive_turn_count(transcript)
                        < SUBSTANTIVE_ASSISTANT_TURNS_MINIMUM):
                continue  # machinery-composed opener and no work: failed successor
        return transcript.stem, transcript
    return None, ("every transcript is an empty-successor session; nothing "
                  "worth resuming")
