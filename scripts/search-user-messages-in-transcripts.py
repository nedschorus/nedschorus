#!/usr/bin/env python3
"""Search typed user messages in Claude Code transcripts.

The harness also labels tool results, reminders, and command output as user
turns; exclude those when searching for the user’s own words. A message the
user types while the agent is mid-turn has no user turn: it is a queued_command
attachment whose origin is human."""

import argparse
import glob
import json
import os
import re
import sys
import time

DEFAULT_PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
WRAPPED_BLOCK = re.compile(r"\A\s*<[a-z-]+>.*</[a-z-]+>\s*\Z", re.DOTALL)


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


def read_turns(path):
    """Every turn in one transcript: (index, speaker, text, timestamp)."""
    turns = []
    # After an interrupt the harness re-sends a queued message as a user turn; the same words
    # typed again later are a new message, so only that re-send is dropped.
    queued_text_awaiting_resend = None
    interrupted_since_queued = False
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
            stamp = record.get("timestamp", "")
            if is_interrupt_notice(record):
                interrupted_since_queued = True
                continue
            text = queued_by_user(record)
            if text is not None:
                turns.append((len(turns), "user", text, stamp))
                queued_text_awaiting_resend = text
                interrupted_since_queued = False
                continue
            text = typed_by_user(record)
            if text is not None:
                if interrupted_since_queued and text == queued_text_awaiting_resend:
                    queued_text_awaiting_resend = None
                    continue
                turns.append((len(turns), "user", text, stamp))
                queued_text_awaiting_resend = None
                continue
            text = assistant_text(record)
            if text is not None:
                turns.append((len(turns), "agent", text, stamp))
                queued_text_awaiting_resend = None
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

    for path in paths:
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
    print(
        f"{total_hits} matching user message(s) in {len(paths)} transcript(s); "
        f"{total_user_messages} user message(s) scanned."
    )
    return 0 if total_hits else 1


if __name__ == "__main__":
    sys.exit(main())
