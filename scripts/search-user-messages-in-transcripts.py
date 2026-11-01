#!/usr/bin/env python3
"""Search typed user messages in Claude Code transcripts.

The harness also labels tool results, reminders, and command output as user
turns; exclude those when searching for the user’s own words. A message the
user types while the agent is mid-turn has no user turn: it is a queued_command
attachment whose origin is human.

A user turn that Claude Code marks with an origin other than human, or as meta,
is not his: such turns carry other agents' messages, hook feedback and delivery
notices. Neither is a turn of a `claude -p` agent-session, whose entrypoint is
sdk-cli and whose prompts a program wrote, nor the summary Claude Code writes
when it compacts a conversation, nor the opening prompt the handoff-supervisor
gives a successor agent-session. Turns written before Claude Code recorded an
origin are read by their text alone."""

import argparse
import glob
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

_claude_code_session_transcript_lookup_and_text_search_common_spec = importlib.util.spec_from_file_location(
    "claude_code_session_transcript_lookup_and_text_search_common",
    Path(__file__).resolve().parent / "claude-code-session-transcript-lookup-and-text-search-common.py")
claude_code_session_transcript_lookup_and_text_search_common = importlib.util.module_from_spec(_claude_code_session_transcript_lookup_and_text_search_common_spec)
_claude_code_session_transcript_lookup_and_text_search_common_spec.loader.exec_module(claude_code_session_transcript_lookup_and_text_search_common)

DEFAULT_PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
WRAPPED_BLOCK = re.compile(r"\A\s*<[a-z-]+>.*</[a-z-]+>\s*\Z", re.DOTALL)
PROGRAM_PROMPT_ENTRYPOINT = "sdk-cli"
COMPACTION_SUMMARY_OPENING = "This session is being continued from a previous conversation"
# Copies of scripts/recover-crashed-seats.py's constants; its test keeps them equal.
REINCARNATION_OPENER_MARKER = "the dialog from the session you are continuing"
REINCARNATION_OPENER_PATTERN = re.compile(
    r"Read .+? — (?:it is )?" + re.escape(REINCARNATION_OPENER_MARKER))
IGNITION_WITHOUT_CONVERSATION_TAIL_MARKER = "the previous session's conversation-tail is unavailable"
# The launch prompts of handoff-supervisor.py and recover-crashed-seats.py reach the transcript with
# human origin; the test feeds each program's own prompt through written_by_a_program.
LAUNCH_PROMPT_MARKERS = (
    "This session was resumed by crash recovery (nedschorus#120)",
    "This seat's supervisor recorded the exit of its last session",
    "This session was launched by nc-systems/handoff/handoff-supervisor.py",
    "this next-step and the repository are your whole context",
)
CONVERSATION_TAIL_IGNITION_PATTERN = re.compile(r"Read .+? — it is the dialog from this seat's last recorded session")


def written_by_a_program(record, text):
    """Whether a user turn's text came from Claude Code, a hook or a program rather than the user."""
    if record.get("isMeta") or record.get("entrypoint") == PROGRAM_PROMPT_ENTRYPOINT:
        return True
    origin = record.get("origin")
    if "origin" in record and (not isinstance(origin, dict) or origin.get("kind") != "human"):
        return True
    return (text.startswith(COMPACTION_SUMMARY_OPENING)
            or REINCARNATION_OPENER_PATTERN.match(text) is not None
            or CONVERSATION_TAIL_IGNITION_PATTERN.match(text) is not None
            or IGNITION_WITHOUT_CONVERSATION_TAIL_MARKER in text
            or any(marker in text for marker in LAUNCH_PROMPT_MARKERS))


def typed_by_user(record):
    """The record's text if the user typed it, else None."""
    if record.get("type") != "user":
        return None
    content = record.get("message", {}).get("content")
    if not isinstance(content, str):
        return None
    text = content.strip()
    if not text:
        return None
    if WRAPPED_BLOCK.match(text):
        return None
    if text.startswith("Caveat:"):
        return None
    if written_by_a_program(record, text):
        return None
    return text


def queued_by_user(record):
    """The text of a message the user typed while the agent was mid-turn, else None."""
    # The same attachment shape also carries peer and task messages; only origin.kind tells them apart.
    if record.get("type") != "attachment":
        return None
    attachment = record.get("attachment")
    if not isinstance(attachment, dict) or attachment.get("type") != "queued_command":
        return None
    origin = attachment.get("origin")
    if not isinstance(origin, dict) or origin.get("kind") != "human":
        return None
    prompt = attachment.get("prompt")
    if not isinstance(prompt, str):
        return None
    return prompt.strip() or None


def is_interrupt_notice(record):
    """Whether the record is the harness's note that the user interrupted the agent."""
    if record.get("type") != "user":
        return False
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        texts = [content]
    elif isinstance(content, list):
        texts = [block.get("text", "") for block in content
                 if isinstance(block, dict) and block.get("type") == "text"]
    else:
        return False
    return any(isinstance(text, str) and text.lstrip().startswith("[Request interrupted")
               for text in texts)


def assistant_text(record):
    """An assistant turn's prose, joined, or None."""
    if record.get("type") != "assistant":
        return None
    content = record.get("message", {}).get("content")
    if isinstance(content, str):
        return content.strip() or None
    if not isinstance(content, list):
        return None
    parts = [
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    joined = "\n".join(p for p in parts if p).strip()
    return joined or None


class TurnReader:
    """Reads one transcript's records in order and returns each turn of the user's or the agent's.

    Its state is a dict of plain values, so a reader that stops part way through a
    transcript can save the state and resume at the next record."""

    def __init__(self, state=None):
        state = state or {}
        # After an interrupt the harness re-sends a queued message as a user turn; the same words
        # typed again later are a new message, so only that re-send is dropped.
        self.queued_text_awaiting_resend = state.get("queued_text_awaiting_resend")
        self.interrupted_since_queued = bool(state.get("interrupted_since_queued"))

    def state(self):
        return {"queued_text_awaiting_resend": self.queued_text_awaiting_resend,
                "interrupted_since_queued": self.interrupted_since_queued}

    def turn(self, record):
        """("user" or "agent", text) for a record that is a turn, else None."""
        if is_interrupt_notice(record):
            self.interrupted_since_queued = True
            return None
        text = queued_by_user(record)
        if text is not None:
            self.queued_text_awaiting_resend = text
            self.interrupted_since_queued = False
            return ("user", text)
        text = typed_by_user(record)
        if text is not None:
            if self.interrupted_since_queued and text == self.queued_text_awaiting_resend:
                self.queued_text_awaiting_resend = None
                return None
            self.queued_text_awaiting_resend = None
            return ("user", text)
        text = assistant_text(record)
        if text is not None:
            self.queued_text_awaiting_resend = None
            return ("agent", text)
        return None


def read_turns(path):
    """Every turn in one transcript: (index, speaker, text, timestamp)."""
    turns = []
    reader = TurnReader()
    with open(path, "r", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            turn = reader.turn(record)
            if turn is not None:
                turns.append((len(turns), turn[0], turn[1], record.get("timestamp", "")))
    return turns


def transcripts(projects_dir, seats, since_hours):
    paths = sorted(glob.glob(os.path.join(projects_dir, "*", "*.jsonl")))
    if seats:
        paths = [
            p for p in paths
            if any(s in os.path.basename(os.path.dirname(p)) for s in seats)
        ]
    if since_hours is not None:
        floor = time.time() - since_hours * 3600
        paths = [p for p in paths if os.path.getmtime(p) >= floor]
    return paths


def claude_code_session_transcript_paths_prefilter_on_raw_json(projects_dir, paths, patterns, all_terms):
    """Return (the paths whose raw JSON holds a pattern's text, a note on what was not prefiltered, or "").

    Every path is kept when a pattern is not plain text, or the search fails, so a prefilter
    never drops a transcript that holds a match."""
    prefilters = [claude_code_session_transcript_lookup_and_text_search_common.claude_code_session_transcript_raw_json_ripgrep_prefilter_pattern_from_search_text_or_none_when_not_plain_text(pattern)
                  for pattern in patterns]
    if not paths:
        return paths, ""
    if None in prefilters:
        return paths, (f"every transcript was read, because ripgrep might not find the pattern "
                       f"{patterns[prefilters.index(None)]!r} wherever Python would")
    groups = [[prefilter] for prefilter in prefilters] if all_terms else [prefilters]
    kept = {os.path.normpath(path) for path in paths}
    for group in groups:
        found, problems = claude_code_session_transcript_lookup_and_text_search_common.claude_code_session_transcripts_matching_any_pattern_ignoring_case(
            [projects_dir], group, include_subagents=False)
        if problems:
            return paths, (f"every transcript was read, because the search that picks the transcripts to read "
                           f"failed: {problems[0]}")
        kept &= {os.path.normpath(path) for path in found}
    return [path for path in paths if os.path.normpath(path) in kept], ""


def main():
    parser = argparse.ArgumentParser(
        description="Search only the user's own typed messages in Claude Code transcripts.",
    )
    parser.add_argument("patterns", nargs="*", metavar="PATTERN")
    parser.add_argument("--projects-dir", default=DEFAULT_PROJECTS_DIR)
    parser.add_argument("--seat", action="append", default=[], metavar="SUBSTRING")
    parser.add_argument("--since-hours", type=float, default=None)
    parser.add_argument("--context", type=int, default=0, metavar="N")
    parser.add_argument("--all-terms", action="store_true")
    parser.add_argument("--list-seats", action="store_true")
    args = parser.parse_args()

    paths = transcripts(args.projects_dir, args.seat, args.since_hours)

    if args.list_seats:
        seen = {}
        for path in paths:
            seat = os.path.basename(os.path.dirname(path))
            seen[seat] = seen.get(seat, 0) + 1
        for seat in sorted(seen):
            print(f"{seen[seat]:4d}  {seat}")
        return 0

    if not args.patterns:
        parser.error("give at least one PATTERN, or --list-seats")

    try:
        regexes = [re.compile(p, re.IGNORECASE) for p in args.patterns]
    except re.error as exc:
        print(f"bad pattern: {exc}", file=sys.stderr)
        return 2

    def matches(text):
        hits = [r for r in regexes if r.search(text)]
        if args.all_terms:
            return len(hits) == len(regexes)
        return bool(hits)

    total_user_messages = 0
    total_hits = 0
    read, note = claude_code_session_transcript_paths_prefilter_on_raw_json(args.projects_dir, paths, args.patterns, args.all_terms)
    if note:
        print(note, file=sys.stderr)

    for path in read:
        turns = read_turns(path)
        user_turns = [t for t in turns if t[1] == "user"]
        total_user_messages += len(user_turns)
        hits = [t for t in user_turns if matches(t[2])]
        if not hits:
            continue
        seat = os.path.basename(os.path.dirname(path))
        for index, _, text, stamp in hits:
            total_hits += 1
            print("=" * 72)
            print(f"{seat}  {os.path.basename(path)}  {stamp}")
            if args.context:
                low = max(0, index - args.context)
                for near in turns[low:index]:
                    print(f"  [{near[1]}] {near[2][:400]}")
            print(f"USER: {text}")
            if args.context:
                for near in turns[index + 1:index + 1 + args.context]:
                    print(f"  [{near[1]}] {near[2][:400]}")

    print("=" * 72)
    skipped = len(paths) - len(read)
    print(
        f"{total_hits} matching user message(s) found among {len(paths)} transcript(s)"
        + (f"; ripgrep found none of the search pattern(s) in {skipped} of them, so only the other "
           f"{len(read)} {'was' if len(read) == 1 else 'were'} opened" if skipped else "")
        + f"; {total_user_messages} user message(s) read in the transcript(s) opened."
    )
    return 0 if total_hits else 1


if __name__ == "__main__":
    sys.exit(main())
