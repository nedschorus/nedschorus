#!/usr/bin/env python3
"""Extract the two-voice dialog from a Claude Code session transcript.

The handoff system's dialog carrier (specification:
docs/cross-project/fast-handoff-design.md). A retiring session names a
boundary; the supervisor runs this after killing that session, and the
extracted markdown becomes the successor's context.

Two modes:
  --boundary-quote "<first line of a user prompt>"
      Recycling mode. Copies every dialog turn from the matching user
      prompt to the end of the transcript.
  --last-turns N
      Recovery mode for a session that died without writing a handoff.
      Copies the final N dialog turns.

Locating the transcript, in order: --transcript-path when given; otherwise
the session id keyed against the project directory derived from --cd (or
the current working directory); otherwise a search for <session-id>.jsonl
across every project directory. Latest-by-modification-time is never used:
a second session in the same worktree makes that a race.

Kept verbatim: user prompts and assistant display text. Dropped: tool
calls and their results, thinking blocks, system and harness records,
queued notifications, and subagent turns (isSidechain), none of which the
successor needs and all of which are large.

Exit codes: 0 extraction written, 2 bad invocation, 3 transcript not
found, 4 transcript unusable (empty, unparseable, or boundary not found).
"""

import argparse
import json
import sys
from pathlib import Path

PROJECTS_ROOT = Path.home() / ".claude" / "projects"

# One transcript record above this size is a pathological tool dump, not
# dialog. Skipping it by size keeps a single oversized line from defeating
# the whole extraction.
MAXIMUM_RECORD_BYTES = 4 * 1024 * 1024


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
    skip_counts = {"malformed": 0, "oversized": 0, "partial_final_record": 0}

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
        if turn is not None:
            turns.append(turn)

    return turns, skip_counts


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


def select_turns_from_boundary(turns, boundary_quote: str):
    """Return the turns from the boundary-quoted user prompt to the end."""
    wanted = boundary_quote.strip()
    for index, turn in enumerate(turns):
        if turn["voice"] != "user":
            continue
        if first_line_of(turn["text"]) == wanted or turn["text"].strip().startswith(wanted):
            return turns[index:], index
    raise TranscriptProblem(
        f"boundary quote not found among {sum(1 for t in turns if t['voice'] == 'user')} "
        f"user prompts: {wanted!r}"
    )


def render_extraction(turns, transcript_path: Path, session_id: str, skip_counts, boundary_note: str) -> str:
    lines = [
        f"# Session dialog — {session_id}",
        "",
        f"Boundary: {boundary_note}",
        f"Turns carried: {len(turns)}",
    ]

    skipped = ", ".join(f"{count} {name}" for name, count in skip_counts.items() if count)
    if skipped:
        lines.append(f"Records skipped while reading: {skipped}.")

    lines += ["", "---", ""]

    for turn in turns:
        speaker = "User" if turn["voice"] == "user" else "Agent"
        lines += [f"## {speaker}", "", turn["text"], ""]

    lines += [
        "---",
        "",
        f"Need more than this? The full transcript, including tool calls and results, is at {transcript_path}.",
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract two-voice dialog from a Claude Code session transcript.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--session-id", help="session whose transcript to extract")
    parser.add_argument("--transcript-path", help="explicit JSONL path, bypassing lookup")
    parser.add_argument("--cd", default=".", help="worktree whose project directory holds the session (default: cwd)")
    boundary_group = parser.add_mutually_exclusive_group(required=True)
    boundary_group.add_argument("--boundary-quote", help="first line of the user prompt to start from")
    boundary_group.add_argument("--last-turns", type=int, help="carry only the final N dialog turns")
    parser.add_argument("--output", help="write here instead of stdout")
    arguments = parser.parse_args(argv)

    if not arguments.session_id and not arguments.transcript_path:
        parser.error("one of --session-id or --transcript-path is required")
    if arguments.last_turns is not None and arguments.last_turns < 1:
        parser.error("--last-turns must be at least 1")

    try:
        if arguments.transcript_path:
            transcript_path = Path(arguments.transcript_path).expanduser()
            if not transcript_path.is_file():
                raise TranscriptProblem(f"no transcript at {transcript_path}")
        else:
            transcript_path = find_transcript_path(
                arguments.session_id, Path(arguments.cd).expanduser().resolve()
            )
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
            selected, boundary_index = select_turns_from_boundary(turns, arguments.boundary_quote)
            boundary_note = (
                f"user prompt {boundary_index + 1} of {len(turns)}, "
                f"quoted as {arguments.boundary_quote.strip()!r}"
            )
        else:
            selected = turns[-arguments.last_turns:]
            boundary_note = f"final {len(selected)} turns (recovery mode)"
    except TranscriptProblem as problem:
        print(f"handoff-extract-conversation: {problem}", file=sys.stderr)
        return 4

    extraction = render_extraction(selected, transcript_path, session_id, skip_counts, boundary_note)

    if arguments.output:
        output_path = Path(arguments.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(extraction, encoding="utf-8")
        print(f"wrote {len(selected)} turns to {output_path}", file=sys.stderr)
    else:
        sys.stdout.write(extraction)

    return 0


if __name__ == "__main__":
    sys.exit(main())
