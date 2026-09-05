#!/usr/bin/env python3
"""Search only the user's own typed messages across Claude Code session transcripts.

A transcript is JSONL; one object per line. A line the user typed has
type == "user" and a plain string in message.content. Every other "user" line is
harness material -- tool results (message.content is a list of tool_result
blocks), injected reminders, command output -- and is skipped, which is what
makes this different from grepping the file.

Two further exclusions, because both wear the user's label:
  * a string body that is entirely a <...> block, such as
    <command-message>, <local-command-stdout> or <system-reminder>;
  * a body opening with "Caveat:", the local-command banner.

Usage:
  search-user-messages-in-transcripts.py PATTERN [PATTERN ...]
      [--projects-dir DIR] [--seat SUBSTRING] [--since-hours N]
      [--context N] [--all-terms] [--list-seats]

Every PATTERN is a case-insensitive regular expression. A message matches when
any pattern matches, or, with --all-terms, when all of them do.

  --seat        keep only project directories whose name contains SUBSTRING;
                repeatable. The directory is the checkout path with the
                separators replaced by hyphens, so --seat reboot-test finds
                -Users-el-agents-reboot-test.
  --since-hours consider only transcripts modified in the last N hours.
  --context     also print the N messages on each side of a hit, from either
                speaker, so a bare "y" can be read.
  --list-seats  print the project directories that pass the filters and stop.

Exit status is 0 when at least one message matched, 1 when none did, 2 on a
usage error.
"""

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
            text = typed_by_user(record)
            if text is not None:
                turns.append((len(turns), "user", text, stamp))
                continue
            text = assistant_text(record)
            if text is not None:
                turns.append((len(turns), "agent", text, stamp))
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
