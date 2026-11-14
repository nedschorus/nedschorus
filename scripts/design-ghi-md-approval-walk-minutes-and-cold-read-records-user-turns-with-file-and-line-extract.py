#!/usr/bin/env python3
"""Find every design GHI-MD, the walk-minutes and cold-read-records about it, and the lines in them where
the user speaks; print each such line as one JSON object per line, for an agent to judge.

Usage:
  scripts/design-ghi-md-approval-walk-minutes-and-cold-read-records-user-turns-with-file-and-line-extract.py
      [--repository-checkout DIR] [--log-store DIR] [--agents-directory DIR]

  --repository-checkout  default the checkout this file is in; its docs/issues/*.md are read as they stand
                         in the working tree, and its git history gives each design's past file names
  --log-store            default /home/nedlern/nedschorus-logs; its walk/*-minutes.md and
                         cold-read-records/*/ are read
  --agents-directory     default /home/nedlern/agents; its */docs/walk/*-minutes.md are read when the
                         log-store holds no walk-minutes of the same name

A design is a file docs/issues/*.md with a line `kind: design`, as `grep -l '^kind: design'
docs/issues/*.md` finds it; its number is the number its name starts with.

A cold-read-record is about a design when the record's name starts with `<number>-`, or a file under its
target/ has a name the design's file had at some commit (`git log --follow`).

A walk-minutes file is about a design, for the reason printed as walk_minutes_match, when its name, without
`-minutes.md`, is the name of a cold-read-record about the design (record-name), because a cold-read
approval-walk is named after its cold-read-record; when its name starts with `<number>-` or `ghi-<number>-`
(number-prefix); or when its text cites `issues/<number>`, `GHI <number>` or one of the design's past file
names (cites). Many approval-walks carry items on several designs, so a cites match is the whole file's, and
the reading agent tells which of its lines are about the design.

A user turn is a line of a walk-minutes file, or of a cold-read-record's cold-read-triage.md or triage.md,
that USER_TURN_LINE matches. Every such line is printed, with no filter on what it says: which lines are
questions or rulings about a design is the reading agent's judgment. A line in a cold-read-triage.md
usually cites a ruling given in an approval-walk, so its walk-minutes are where the user spoke.

Each printed object has: design (its path), design_number, source_kind (walk-minutes or
cold-read-triage), walk_minutes_match (as above; "" for a cold-read-triage), source (the file's path), line
(1-based), heading (the nearest Markdown heading above the line, or ""), and text (the line). A count per design goes to stderr at the end.

Exit codes: 0 done; 2 a directory argument does not exist. A failing git command stops it with git's
error and a nonzero exit.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_LOG_STORE = Path("/home/nedlern/nedschorus-logs")
DEFAULT_AGENTS_DIRECTORY = Path("/home/nedlern/agents")
DESIGN_KIND_LINE = re.compile(r"^kind: design", re.MULTILINE)
# Old walk-minutes quote him as `The user, <date>: "..."` or `Item 4 answer in full: "..."`; newer ones carry
# the line walk-me-through's check program writes, `item 3 of 16: the user answered approved ... in his words
# "..."`; cold-read-triage.md cites `user-ruled <date>` or `the user ruled "..."`.
USER_TURN_LINE = re.compile(
    r"\bthe user\b|\buser-ruled\b|\bin his words\b|\banswer in full\b|\bhe (?:said|asked|answered|ruled)\b",
    re.IGNORECASE)
HEADING_LINE = re.compile(r"^#{1,6} ")
TRIAGE_FILE_NAMES = ("cold-read-triage.md", "triage.md")


def designs_in(checkout):
    """(number, path relative to the checkout) for each design GHI-MD, sorted by number."""
    found = []
    for path in sorted((checkout / "docs" / "issues").glob("*.md")):
        number = re.match(r"^(\d+)-", path.name)
        if number and DESIGN_KIND_LINE.search(path.read_text(encoding="utf-8")):
            found.append((int(number.group(1)), str(path.relative_to(checkout))))
    return sorted(found)


def past_file_names(checkout, relative):
    """Every name the file has had, its current one included, from git's rename tracking."""
    logged = subprocess.run(["git", "-C", str(checkout), "log", "--follow", "--name-only", "--format=",
                             "--", relative], capture_output=True, text=True, check=True).stdout
    return {Path(line).name for line in logged.splitlines() if line.strip()} | {Path(relative).name}


def cold_read_records_in(records_root):
    """{record name: set of the file names under its target/}."""
    records = {}
    for record in sorted(records_root.iterdir()):
        if record.is_dir():
            target = record / "target"
            records[record.name] = ({p.name for p in target.rglob("*") if p.is_file()}
                                    if target.is_dir() else set())
    return records


def walk_minutes_in(log_store, agents_directory):
    """{walk-minutes file name: (path, text)}, the log-store's copy where it holds one."""
    paths = {}
    for path in sorted(agents_directory.glob("*/docs/walk/*-minutes.md")):
        paths[path.name] = path
    for path in sorted((log_store / "walk").glob("*-minutes.md")):
        paths[path.name] = path
    return {name: (path, path.read_text(encoding="utf-8", errors="replace")) for name, path in paths.items()}


def starts_with_number(name, number):
    return re.match(rf"^(?:ghi-)?{number}-", name) is not None


def text_cites(text, number, names):
    return (re.search(rf"(?:issues/|\bGHI[- ]){number}(?!\d)", text) is not None
            or any(name in text for name in names))


def walk_minutes_match(name, text, number, names, own_records):
    if name[:-len("-minutes.md")] in own_records:
        return "record-name"
    if starts_with_number(name, number):
        return "number-prefix"
    if text_cites(text, number, names):
        return "cites"
    return None


def user_turns(path):
    """(line number, nearest heading, line) for each line USER_TURN_LINE matches."""
    heading = ""
    for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if HEADING_LINE.match(line):
            heading = line.lstrip("#").strip()
        if USER_TURN_LINE.search(line):
            yield number, heading, line


def extract(checkout, log_store, agents_directory, out, err):
    records = cold_read_records_in(log_store / "cold-read-records")
    minutes = walk_minutes_in(log_store, agents_directory)
    for number, design in designs_in(checkout):
        names = past_file_names(checkout, design)
        own_records = [name for name, files in records.items()
                       if name.startswith(f"{number}-") or files & names]
        own_minutes = []
        for name, (path, text) in minutes.items():
            match = walk_minutes_match(name, text, number, names, own_records)
            if match:
                own_minutes.append((path, match))
        sources = [("walk-minutes", path, match) for path, match in own_minutes]
        for record in own_records:
            for triage_name in TRIAGE_FILE_NAMES:
                triage = log_store / "cold-read-records" / record / triage_name
                if triage.is_file():
                    sources.append(("cold-read-triage", triage, ""))
        count = 0
        for kind, path, match in sources:
            for line_number, heading, text in user_turns(path):
                out.write(json.dumps({"design": design, "design_number": number, "source_kind": kind,
                                      "walk_minutes_match": match, "source": str(path), "line": line_number, "heading": heading,
                                      "text": text}, ensure_ascii=False) + "\n")
                count += 1
        err.write(f"{design}: {len(own_minutes)} walk-minutes, {len(own_records)} cold-read-records, "
                  f"{count} user turns\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repository-checkout", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--log-store", type=Path, default=DEFAULT_LOG_STORE)
    parser.add_argument("--agents-directory", type=Path, default=DEFAULT_AGENTS_DIRECTORY)
    arguments = parser.parse_args(argv)
    for name in ("repository_checkout", "log_store", "agents_directory"):
        if not getattr(arguments, name).is_dir():
            sys.stderr.write(f"--{name.replace('_', '-')} {getattr(arguments, name)} is not a directory.\n"
                             "Give a directory that exists, or leave the option out for its default.\n")
            return 2
    extract(arguments.repository_checkout, arguments.log_store, arguments.agents_directory,
            sys.stdout, sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
