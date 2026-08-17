#!/usr/bin/env python3
"""Extract the two-voice dialog from a Claude Code session transcript.

The handoff system's dialog carrier (specification:
docs/cross-project/fast-handoff-design.md). A retiring session names a
boundary; the supervisor runs this after killing that session, and the
extracted markdown becomes the successor's context.

By default it carries the tail of the conversation: enough turns to clear a
word floor, extended back to the nearest user prompt so the extract opens on
a clean turn. Nobody chooses a boundary — the retiring agent has no judgment
to exercise here, and the header states how many earlier turns were left in
the transcript, so a successor whose work reaches further back knows to go
read them.

Two overrides exist for manual use:
  --boundary-quote "<first line of a user prompt>"
      Start at a named prompt instead of the floor-sized tail.
  --last-turns N
      Carry exactly N final turns, ignoring the floor.

Locating the transcript, in order: --transcript-path when given; otherwise
the session id keyed against the project directory derived from --cd (or
the current working directory); otherwise a search for <session-id>.jsonl
across every project directory. Latest-by-modification-time is never used:
a second session in the same worktree makes that a race.

Kept verbatim: user prompts and assistant display text. Dropped: tool
calls and their results, thinking blocks, system and harness records,
subagent turns (isSidechain), and harness-injected pseudo-prompts with the
short agent acknowledgements that answer them — none of which the successor
needs and all of which are large.

Alongside the extraction, when it leaves turns behind, the complete filtered
dialog is written as a sibling file: the tail is the successor's working set,
the companion is the conversation's history without the raw transcript's tool
dumps.

Exit codes: 0 extraction written, 2 bad invocation, 3 transcript not
found, 4 transcript unusable (empty, unparseable, or boundary not found).
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECTS_ROOT = Path.home() / ".claude" / "projects"

# One transcript record above this size is a pathological tool dump, not
# dialog. Skipping it by size keeps a single oversized line from defeating
# the whole extraction.
MAXIMUM_RECORD_BYTES = 4 * 1024 * 1024

# How much dialog the successor receives (trimmed from 2500 after live
# restarts showed the longer tail unused, then from 1600 to 1000 when the
# injected-record filter below made every counted word a real one — ruled
# 2026-08-17: the 2026-08-17 merge-lane restart succeeded on 341 real words,
# so 1000 carries ~3x that with margin. The asymmetry favors lean: a starved
# successor reads the companion dialog or transcript it is pointed at once; a
# fat tail taxes every restart). This number, plus those pointers and the
# left-behind count in the header, is what replaced asking the retiring agent
# to judge a boundary.
MINIMUM_DIALOG_WORDS = 1000


# Harness-injected user records open with one of these. The list is the
# 2026-08-17 census of 341 transcripts across both machines and every project
# (script: handoff-census-user-record-shapes.py, kept beside this one): of all
# user-record words the old filter kept, 59% were injected, task-notifications
# alone 860 records — displacing exactly the dialog the tail exists to carry.
# <bash-input> is deliberately absent: those are commands the user personally
# typed via the "!" prefix.
INJECTED_TEXT_PREFIXES = (
    "<task-notification>",
    "<command-message>",
    "<command-name>",
    "<local-command-stdout>",
    "<local-command-stderr>",
    "<bash-stdout>",
    "<bash-stderr>",
    "<system-reminder>",
    "[Request interrupted",
)

# An assistant turn at most this many words, immediately after an injected
# record, is a routine acknowledgement of it ("Routine — … On watch.") and
# falls with it. A longer reaction is real dialog and survives: length is the
# only signal that distinguishes the watcher's one-line acks from an urgent
# analysis a successor genuinely needs.
MAXIMUM_ACKNOWLEDGEMENT_WORDS = 60


class TranscriptProblem(Exception):
    """The transcript cannot be used for extraction."""


def project_directory_for_working_directory(working_directory: Path) -> Path:
    """Return the ~/.claude/projects directory holding a worktree's sessions.

    The harness mangles the absolute path by replacing every character that
    is not alphanumeric, a dash, or an underscore with a dash.
    """
    mangled = "".join(
        character if (character.isalnum() or character in "-_") else "-"
        for character in str(working_directory)
    )
    return PROJECTS_ROOT / mangled


def find_transcript_path(session_id: str, working_directory: Path) -> Path:
    """Locate a session's JSONL by id: keyed lookup first, then a search."""
    keyed_path = project_directory_for_working_directory(working_directory) / f"{session_id}.jsonl"
    if keyed_path.is_file():
        return keyed_path

    matches = sorted(PROJECTS_ROOT.glob(f"*/{session_id}.jsonl"))
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise TranscriptProblem(
            f"no transcript for session {session_id}: looked at {keyed_path} "
            f"and searched {PROJECTS_ROOT}/*/"
        )
    raise TranscriptProblem(
        f"session {session_id} appears in several project directories: "
        + ", ".join(str(match) for match in matches)
    )


def read_dialog_turns(transcript_path: Path):
    """Return (turns, skip_counts) for one transcript.

    A turn is {"voice": "user"|"assistant", "text": str}. Malformed and
    oversized records are skipped and counted rather than raising: a
    transcript is being read while its writer may still be exiting, so the
    final record can be a partial write.
    """
    turns = []
    skip_counts = {
        "malformed": 0, "oversized": 0, "partial_final_record": 0,
        "injected": 0, "acknowledgement": 0,
    }
    # True while the latest dropped record was harness-injected: the very next
    # assistant turn, if short, is its acknowledgement and falls with it.
    following_injected_record = False

    with transcript_path.open("rb") as handle:
        raw_lines = handle.readlines()

    for index, raw_line in enumerate(raw_lines):
        is_final_line = index == len(raw_lines) - 1

        if len(raw_line) > MAXIMUM_RECORD_BYTES:
            skip_counts["oversized"] += 1
            continue

        stripped = raw_line.strip()
        if not stripped:
            continue

        try:
            record = json.loads(stripped)
        except (json.JSONDecodeError, UnicodeDecodeError):
            # An unterminated final line is a partial write, not corruption.
            if is_final_line and not stripped.endswith(b"}"):
                skip_counts["partial_final_record"] += 1
            else:
                skip_counts["malformed"] += 1
            continue

        turn = dialog_turn_from_record(record)
        if turn is None:
            # Harness/state records (system, queue-operation, attachment) sit
            # between a notification and its acknowledgement without breaking
            # the pair. A tool-bearing record does break it: the agent moved
            # on to real work, so its next text is a report the successor
            # needs, not the notification's ack (review finding, 2026-08-17 —
            # a short real conclusion after intervening tool work was being
            # dropped unrecoverably).
            if record_shows_tool_activity(record):
                following_injected_record = False
            continue

        if turn["voice"] == "user":
            if turn["text"].startswith(INJECTED_TEXT_PREFIXES):
                skip_counts["injected"] += 1
                following_injected_record = True
            else:
                turns.append(turn)
                following_injected_record = False
            continue

        if (following_injected_record
                and len(turn["text"].split()) <= MAXIMUM_ACKNOWLEDGEMENT_WORDS):
            skip_counts["acknowledgement"] += 1
        else:
            turns.append(turn)
        following_injected_record = False

    return turns, skip_counts


def record_shows_tool_activity(record) -> bool:
    """True for a record carrying tool calls or results (not a subagent's)."""
    if not isinstance(record, dict) or record.get("isSidechain"):
        return False
    content = record.get("message", {}).get("content")
    return isinstance(content, list) and any(
        isinstance(block, dict) and block.get("type") in ("tool_use", "tool_result")
        for block in content
    )


def joined_text_blocks(content) -> str:
    """Join the text blocks of a content list, dropping every other block.

    Tool calls, tool results, and thinking blocks all live in these lists;
    only text blocks are dialog.
    """
    if not isinstance(content, list):
        return ""
    return "\n".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


def dialog_turn_from_record(record):
    """Return a dialog turn for a transcript record, or None to drop it."""
    if not isinstance(record, dict):
        return None
    if record.get("isSidechain"):
        return None  # subagent conversation, not this session's dialog
    if record.get("type") == "user" and record.get("isMeta"):
        return None  # harness-injected, not typed by the user

    record_type = record.get("type")
    if record_type not in ("user", "assistant"):
        return None  # system, attachment, queue-operation, harness state

    content = record.get("message", {}).get("content")
    if record_type == "user" and isinstance(content, str):
        text = content.strip()
    else:
        text = joined_text_blocks(content).strip()

    return {"voice": record_type, "text": text} if text else None


def first_line_of(text: str) -> str:
    return text.splitlines()[0].strip() if text.splitlines() else ""


def word_count(turns) -> int:
    return sum(len(turn["text"].split()) for turn in turns)


def select_tail_clearing_floor(turns, minimum_words: int = MINIMUM_DIALOG_WORDS):
    """Return the tail of the conversation that clears the word floor.

    Walks back from the end until the selection clears the floor, then keeps
    walking to the nearest earlier user prompt so the extract opens on a
    prompt rather than mid-exchange. Short trailing assistant turns are
    trimmed first: the extraction runs after the retiring session was killed,
    so its last turns are routinely fragments announcing the handoff
    ("Writing the successor's first-action prompt:"). Only short turns fall —
    a substantive final answer is real dialog and survives. Returns
    (selected_turns, start_index).
    """
    end = len(turns)
    while (end > 0 and turns[end - 1]["voice"] == "assistant"
           and len(turns[end - 1]["text"].split()) <= MAXIMUM_ACKNOWLEDGEMENT_WORDS):
        end -= 1
    if end == 0:
        end = len(turns)  # nothing but short assistant turns: keep what exists

    index = end
    while index > 0 and word_count(turns[index:end]) < minimum_words:
        index -= 1

    while index > 0 and turns[index]["voice"] != "user":
        index -= 1

    return turns[index:end], index


def widen_to_minimum_words(turns, boundary_index: int, minimum_words: int) -> int:
    """Walk a boundary backwards to earlier user prompts until it clears the floor.

    Returns the widened index. A boundary already clearing the floor, or one
    with no earlier user prompt to reach, is returned unchanged.
    """
    index = boundary_index
    while word_count(turns[index:]) < minimum_words:
        earlier = [
            candidate
            for candidate in range(index - 1, -1, -1)
            if turns[candidate]["voice"] == "user"
        ]
        if not earlier:
            return 0 if index > 0 else index
        index = earlier[0]
    return index


def select_turns_from_boundary(turns, boundary_quote: str, minimum_words: int = MINIMUM_DIALOG_WORDS):
    """Return the turns from the boundary-quoted user prompt to the end.

    The selection is widened backwards when it falls under the word floor, so
    a too-tight boundary cannot strand the successor.
    """
    wanted = boundary_quote.strip()
    for index, turn in enumerate(turns):
        if turn["voice"] != "user":
            continue
        if first_line_of(turn["text"]) == wanted or turn["text"].strip().startswith(wanted):
            widened = widen_to_minimum_words(turns, index, minimum_words)
            return turns[widened:], widened, index
    raise TranscriptProblem(
        f"boundary quote not found among {sum(1 for t in turns if t['voice'] == 'user')} "
        f"user prompts: {wanted!r}"
    )


@dataclass
class ExtractionReport:
    """What the extraction did, for the successor's header."""

    session_id: str
    transcript_path: Path
    boundary_note: str
    turns_left_behind: int
    total_turns: int
    skip_counts: dict
    companion_path: Path = None


def render_pointers(report: ExtractionReport) -> list:
    lines = []
    if report.companion_path:
        lines.append(
            f"Earlier dialog, complete and noise-free: {report.companion_path}."
        )
    lines.append(
        f"The full transcript is at {report.transcript_path} — every tool call "
        "and result, and the retiring agent's thinking, where the reasoning "
        "behind a decision often lives."
    )
    return lines


def render_extraction(turns, report: ExtractionReport) -> str:
    lines = [
        f"# Session dialog — {report.session_id}",
        "",
        f"Boundary: {report.boundary_note}",
        f"Turns carried: {len(turns)} of {report.total_turns} "
        f"({word_count(turns)} words). Turn counts are dialog only — "
        f"harness-injected records and their acknowledgements are filtered out.",
    ]

    if report.turns_left_behind:
        lines.append(
            f"Earlier in this session, and NOT below: {report.turns_left_behind} turns."
        )
    trimmed_at_end = report.total_turns - report.turns_left_behind - len(turns)
    if trimmed_at_end > 0:
        lines.append(
            f"Trimmed from the end: {trimmed_at_end} short agent turn(s) — "
            f"fragments from the session's last moments before the handoff."
        )

    skipped = ", ".join(f"{count} {name}" for name, count in report.skip_counts.items() if count)
    if skipped:
        lines.append(f"Records skipped while reading: {skipped}.")

    lines += ["", "---", ""]

    for turn in turns:
        speaker = "User" if turn["voice"] == "user" else "Agent"
        lines += [f"## {speaker}", "", turn["text"], ""]

    lines += ["---", "", "Need more than this?"]
    lines += render_pointers(report)
    lines.append("")
    return "\n".join(lines)


def render_companion(turns, report: ExtractionReport) -> str:
    """The complete filtered dialog: every real turn, none of the noise."""
    lines = [
        f"# Complete session dialog — {report.session_id}",
        "",
        f"All {len(turns)} dialog turns ({word_count(turns)} words), "
        f"harness-injected records and their acknowledgements filtered out.",
        f"Tool calls, results, and the agent's thinking are only in the full "
        f"transcript: {report.transcript_path}",
        "",
        "---",
        "",
    ]
    for turn in turns:
        speaker = "User" if turn["voice"] == "user" else "Agent"
        lines += [f"## {speaker}", "", turn["text"], ""]
    return "\n".join(lines)


def resolve_transcript_path(arguments) -> Path:
    """Return the transcript to read: an explicit path, or an id-keyed lookup."""
    if arguments.transcript_path:
        transcript_path = Path(arguments.transcript_path).expanduser()
        if not transcript_path.is_file():
            raise TranscriptProblem(f"no transcript at {transcript_path}")
        return transcript_path
    return find_transcript_path(
        arguments.session_id, Path(arguments.cd).expanduser().resolve()
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract two-voice dialog from a Claude Code session transcript.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--session-id", help="session whose transcript to extract")
    parser.add_argument("--transcript-path", help="explicit JSONL path, bypassing lookup")
    parser.add_argument("--cd", default=".", help="worktree whose project directory holds the session (default: cwd)")
    boundary_group = parser.add_mutually_exclusive_group()
    boundary_group.add_argument("--boundary-quote", help="override: start at this user prompt")
    boundary_group.add_argument("--last-turns", type=int, help="override: carry exactly N final turns")
    parser.add_argument(
        "--minimum-words", type=int, default=MINIMUM_DIALOG_WORDS,
        help=f"dialog the default tail must clear (default {MINIMUM_DIALOG_WORDS})",
    )
    parser.add_argument("--output", help="write here instead of stdout")
    arguments = parser.parse_args(argv)

    if not arguments.session_id and not arguments.transcript_path:
        parser.error("one of --session-id or --transcript-path is required")
    if arguments.last_turns is not None and arguments.last_turns < 1:
        parser.error("--last-turns must be at least 1")
    if arguments.minimum_words < 1:
        # A floor of zero used to crash the tail walk with an IndexError
        # rather than refusing (review finding, 2026-08-17).
        parser.error("--minimum-words must be at least 1")

    try:
        transcript_path = resolve_transcript_path(arguments)
    except TranscriptProblem as problem:
        print(f"handoff-extract-conversation: {problem}", file=sys.stderr)
        return 3

    session_id = arguments.session_id or transcript_path.stem

    try:
        turns, skip_counts = read_dialog_turns(transcript_path)
        if not turns:
            raise TranscriptProblem(
                f"{transcript_path} yielded no dialog turns "
                f"(skipped: {skip_counts}) — refusing to write an empty extraction"
            )

        if arguments.boundary_quote:
            selected, start_index, quoted_index = select_turns_from_boundary(
                turns, arguments.boundary_quote, arguments.minimum_words
            )
            boundary_note = (
                f"the prompt quoted as {arguments.boundary_quote.strip()!r} "
                f"(turn {quoted_index + 1})"
            )
            if start_index < quoted_index:
                boundary_note += (
                    f", widened back to turn {start_index + 1} to clear the "
                    f"{arguments.minimum_words}-word floor"
                )
        elif arguments.last_turns:
            start_index = max(0, len(turns) - arguments.last_turns)
            selected = turns[start_index:]
            boundary_note = f"final {len(selected)} turns (explicit turn count)"
        else:
            selected, start_index = select_tail_clearing_floor(turns, arguments.minimum_words)
            boundary_note = (
                f"the tail of the conversation clearing {arguments.minimum_words} words, "
                f"opening at the user prompt on turn {start_index + 1}"
            )
    except TranscriptProblem as problem:
        print(f"handoff-extract-conversation: {problem}", file=sys.stderr)
        return 4

    report = ExtractionReport(
        session_id=session_id,
        transcript_path=transcript_path,
        boundary_note=boundary_note,
        turns_left_behind=start_index,
        total_turns=len(turns),
        skip_counts=skip_counts,
    )

    if arguments.output:
        output_path = Path(arguments.output).expanduser()
        if len(selected) < len(turns):
            report.companion_path = output_path.with_name(
                f"{output_path.stem}-complete{output_path.suffix}"
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(render_extraction(selected, report), encoding="utf-8")
        print(f"wrote {len(selected)} turns to {output_path}", file=sys.stderr)
        if report.companion_path:
            report.companion_path.write_text(
                render_companion(turns, report), encoding="utf-8")
            print(f"wrote all {len(turns)} turns to {report.companion_path}", file=sys.stderr)
    else:
        sys.stdout.write(render_extraction(selected, report))

    return 0


if __name__ == "__main__":
    sys.exit(main())
