#!/usr/bin/env python3
"""One-time conversion of the open approval-walks' walk-minutes to the reading in
which only a line the walk check program's close step writes decides or defers
an item.

Until that change, walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py
also read hand-written minutes lines: a line naming items recorded a decision
when it carried a deciding outcome tag or said approved, disapproved, accepted
or rejected, other than right after the, a or an, and a deferral when it said
deferred. This script runs that old reading and the program's new one on each
walk-minutes file, and for every item the old reading counts as decided, or as
deferred more often, than the new one does, names the hand-written line
responsible and the line in the program's own format that would make the new
reading count it the same way:
- a decision becomes the close step's already-decided line, citing the hand-written
  line by its number and its opening words, with `<rejected>` when that line
  carries `<rejected>` or opens with disapproved or rejected, and `<accepted>`
  otherwise; one that carries `<moved on, no decision>` becomes the close step's
  moved-on line instead;
- a deferral becomes the close step's deferral line, or its second-deferral line
  when the item already has a deferral; a deferral of an item either reading
  counts as decided is left alone, since the walk never names a decided item;
- an item whose answer the close step held for a new item, which neither
  reading counts as decided once that new item is decided, since the old close
  left recording it to the agent, becomes the close step's already-decided line
  citing the new item's answer, `<rejected>` when the close line deciding the
  new item carries `<rejected>` and `<accepted>` otherwise.
It also prints, as NOTE lines, each item the new reading counts as decided that
the old one did not, since a hand-written `<revised, awaiting ruling>` line no
longer undoes a decision; it proposes nothing for those.

Usage:
  walk-me-through-open-walk-minutes-hand-written-decision-lines-to-program-lines-one-time-conversion-nbd.py
      [--minutes PATH ...] [--skip PATH:LINE ...] [--as-moved-on PATH:LINE ...] [--write]

By default it reads every /home/nedlern/agents/*/docs/walk/*-minutes.md on
ned-box whose last `#next_to_present` line, as the walk-me-through Stop hook
reads it, names an item rather than `none, closed`. A walk-minutes file with no
`#next_to_present` line has no open walk and is left alone. --minutes names the
files instead. --skip PATH:LINE drops the proposals that come from line LINE,
counted from 1, of PATH, for a line a reader has judged not to be a decision or a
deferral, such as a note that only mentions an earlier deferral. --as-moved-on
PATH:LINE proposes the moved-on line instead of the already-decided one for the
items line LINE of PATH decides, for a line a reader has judged to record that
the walk moved on from an item with no decision.

It is a dry run unless --write is given: it prints each proposal and changes
nothing. With --write it appends the proposed lines to each file, below
everything already there, then a `#walk_minutes_hand_written_lines_converted`
line, which makes any later run leave the file alone; it changes no other line.
It then reads the file again and prints FAILED for each item the new reading
counts as less decided, or less often deferred, than the old reading counted it
before the write, other than through a skipped line.

It does not handle: a minutes file whose walk-document is gone, since the line
it writes names the item with the walk's count from the `#next_to_present` line
alone; or an item whose old reading came from a line that both decides and
names other items, beyond writing one line per item. It can fail by proposing a
line for a hand-written note the old reading misread, such as a note that says
an item was approved in an earlier walk; that is why it is a dry run first and
why --skip exists. A wrong appended line is undone by deleting it. It writes
only to the walk-minutes it names, and only with --write.

Exit 0 when every file was read and, with --write, every item now reads alike;
exit 1, after a FAILED line, otherwise.
"""
import argparse
import collections
import glob
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECK_PROGRAM_FILE = HERE / "walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py"
DEFAULT_MINUTES = "/home/nedlern/agents/*/docs/walk/*-minutes.md"
EXCERPT_LENGTH = 100

# The old reading, as the check program had it before only its own lines counted.
RECORDED_ITEMS = re.compile(r"^\s*(?:(?:[-*+]|\d+[.)]|>)\s+)*[*_]*(items?\s+[^:(]*)", re.I)
DATE = re.compile(r"\d{4}-\d\d-\d\d(?:[T ]\d\d:\d\d(?::\d\d(?:\.\d+)?)?(?:Z|[+-]\d\d:?\d\d)?)?")
DECIDED = re.compile(r"\b(?:dis)?approved\b|\baccepted\b|\brejected\b|<moved on, no decision>", re.I)
DEFERRED_WORD = re.compile(r"\bdeferred\b", re.I)
MODIFIER_BEFORE = re.compile(r"\b(?:the|a|an)\s+$", re.I)
OUTCOME_TAG = re.compile(r"<([^<>]+)>")
DECIDING_OUTCOMES = {"accepted", "rejected", "moved on, no decision", "approved as revised"}
AWAITING_RULING = "revised, awaiting ruling"
UNDECIDED_OUTCOMES = {"open", AWAITING_RULING}
FIRST_WORD = re.compile(r"^[\s,:;*_.)\-\u2013\u2014]*(\w+)")
REJECTING_FIRST_WORDS = {"disapproved", "rejected"}
MOVED_ON_TAG = "moved on, no decision"
# Appended after the converted lines: the appended deferral lines carry no citation, so without it a second run
# would read each hand-written deferral as unconverted and defer its item again.
CONVERTED_MARKER = "#walk_minutes_hand_written_lines_converted"
# The close step's held-answer line: the old close told the agent to record the new item's answer as the held
# item's by hand, in a form neither reading reads.
HELD_ANSWER = re.compile(r"^(items?\s[^:]*): answer held: (items?\s.+?), raised by a fast-read finding", re.I)


def load_walk_me_through_check_program_module():
    spec = importlib.util.spec_from_file_location("walk_check_program", CHECK_PROGRAM_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def says_outcome(pattern, line):
    return any(not MODIFIER_BEFORE.search(line[:match.start()]) for match in pattern.finditer(line))


def old_reading(program, walk_finder, text, parser):
    """Return (item -> (line index, line) of the last line that left it decided, item -> [(line index, line)] of
    each line that deferred it), as the old reading counted them."""
    decided_by, deferred_by = {}, collections.defaultdict(list)
    for index, line in enumerate(walk_finder.prose_lines(text, parser)):
        if program.ANSWER_LINE.match(line):
            continue
        dated = DATE.sub("", line)
        match = RECORDED_ITEMS.match(dated)
        if not match:
            continue
        try:
            items, _ = walk_finder.parse_items(match[1].strip())
        except walk_finder.UnusableRange:
            continue
        outcomes = {tag.strip().lower() for tag in OUTCOME_TAG.findall(line)}
        first = FIRST_WORD.match(dated[match.end():])
        defers = bool(first) and first[1].lower() == "deferred"
        if AWAITING_RULING in outcomes:
            for item in items:
                decided_by.pop(item, None)
        elif outcomes & DECIDING_OUTCOMES:
            decided_by.update((item, (index, line)) for item in items)
            defers = False
        elif not (outcomes & UNDECIDED_OUTCOMES or defers):
            if says_outcome(DECIDED, line):
                decided_by.update((item, (index, line)) for item in items)
            else:
                defers = says_outcome(DEFERRED_WORD, line)
        if defers:
            for item in items:
                deferred_by[item].append((index, line))
    return decided_by, deferred_by


def excerpt(line):
    line = " ".join(line.split())
    return line if len(line) <= EXCERPT_LENGTH else line[:EXCERPT_LENGTH - 3].rstrip() + "..."


def citation(index, line):
    return f"the hand-written minutes line {index + 1}, \"{excerpt(line)}\""


def proposed_line(program, item_text, index, line, moved_on=False):
    """The close-step line that records, in the new reading, the decision the old reading read in line."""
    if moved_on or MOVED_ON_TAG in {tag.strip().lower() for tag in OUTCOME_TAG.findall(line)}:
        return program.CLOSE_MOVED_ON_MINUTES.format(item=item_text, reason=citation(index, line))
    match = RECORDED_ITEMS.match(DATE.sub("", line))
    first = FIRST_WORD.match(DATE.sub("", line)[match.end():]) if match else None
    rejected = "<rejected>" in line.lower() or bool(first) and first[1].lower() in REJECTING_FIRST_WORDS
    return program.CLOSE_ALREADY_DECIDED_MINUTES.format(
        item=item_text, ruling=citation(index, line),
        outcome=program.OUTCOMES[program.DISAPPROVED if rejected else program.APPROVED])


def new_items_rejected(program, walk_finder, parser, text, new_items):
    """Return whether the last line the close step wrote deciding any of new_items carries `<rejected>`."""
    last = None
    for line in walk_finder.prose_lines(text, parser):
        match = program.PROGRAM_LINE_ITEMS.match(line)
        if not match or not any(pattern.match(line[match.end():]) for pattern in program.DECIDING_LINES):
            continue
        try:
            items, _ = walk_finder.parse_items(match[1])
        except walk_finder.UnusableRange:
            continue
        if set(items) & set(new_items):
            last = line
    return last is not None and "<rejected>" in last


def walk_total(walk_finder, text, parser):
    marker = walk_finder.next_to_present(text, parser)
    if marker is None:
        return None
    try:
        return walk_finder.parse_items(marker[0])[1]
    except walk_finder.UnusableRange:
        return None


def expected_reading(program, walk_finder, parser, text, skipped_lines):
    """Return (items decided, Counter of deferrals) as the old reading reads text, without the skipped lines."""
    decided_by, deferred_by = old_reading(program, walk_finder, text, parser)
    decided = {item for item, (index, _) in decided_by.items() if index + 1 not in skipped_lines}
    deferrals = collections.Counter({item: sum(index + 1 not in skipped_lines for index, _ in sources)
                                     for item, sources in deferred_by.items() if item not in decided})
    return decided, deferrals


def unconverted(program, walk_finder, parser, text, expected):
    """Return the items whose new reading of text falls short of the expected reading."""
    decided, deferrals = expected
    new_decided, new_deferrals = program.minutes_record(walk_finder, text, parser)
    return sorted((decided - new_decided) | {item for item in deferrals
                                             if item not in new_decided and new_deferrals[item] < deferrals[item]})


def proposals(program, walk_finder, parser, text, skipped_lines, moved_on_lines=frozenset()):
    """Return ([(line index, line, item, proposed line)], [NOTE text]) for one walk-minutes file's text."""
    decided_by, deferred_by = old_reading(program, walk_finder, text, parser)
    decided_by = {item: source for item, source in decided_by.items() if source[0] + 1 not in skipped_lines}
    new_decided, new_deferrals = program.minutes_record(walk_finder, text, parser)
    total = walk_total(walk_finder, text, parser)
    found, notes = [], []

    def item_text(item):
        return f"item {item} of {total}" if total else f"item {item}"

    for item, (index, line) in sorted(decided_by.items(), key=lambda pair: pair[1][0]):
        if item in new_decided:
            continue
        found.append((index, line, item, proposed_line(program, item_text(item), index, line,
                                                       moved_on=index + 1 in moved_on_lines)))
    for item, sources in deferred_by.items():
        # A deferral of an item that is decided changes nothing: the walk never names a decided item.
        if item in decided_by or item in new_decided:
            continue
        missing = len(sources) - new_deferrals[item]
        recorded = new_deferrals[item]
        for index, line in sources:
            if missing <= 0:
                break
            if program.PROGRAM_LINE_ITEMS.match(line) and any(
                    pattern.match(line[program.PROGRAM_LINE_ITEMS.match(line).end():])
                    for pattern in program.DEFERRING_LINES):
                continue
            missing -= 1
            if index + 1 in skipped_lines:
                continue
            template = program.CLOSE_DEFERRED_AGAIN_MINUTES if recorded else program.CLOSE_DEFERRED_MINUTES
            recorded += 1
            found.append((index, line, item, template.format(item=item_text(item))))
    proposed_items = {item for _, _, item, _ in found}
    for index, line in enumerate(walk_finder.prose_lines(text, parser)):
        held = HELD_ANSWER.match(line)
        if not held or index + 1 in skipped_lines:
            continue
        try:
            held_items, _ = walk_finder.parse_items(held[1])
            new_items, _ = walk_finder.parse_items(held[2])
        except walk_finder.UnusableRange:
            continue
        if not set(new_items) <= new_decided:
            continue
        outcome = program.OUTCOMES[program.DISAPPROVED if new_items_rejected(program, walk_finder, parser, text,
                                                                              new_items) else program.APPROVED]
        for item in held_items:
            if item in new_decided or item in proposed_items or item in decided_by:
                continue
            proposed_items.add(item)
            found.append((index, line, item, program.CLOSE_ALREADY_DECIDED_MINUTES.format(
                item=item_text(item), outcome=outcome,
                ruling=f"the user's answer to {held[2]}, which {citation(index, line)} held its answer for")))
    for item in sorted(new_decided - set(decided_by)):
        notes.append(f"NOTE: item {item} reads as decided now but not in the old reading, which a later "
                     f"`<revised, awaiting ruling>` line or an unread close line explains; nothing is proposed.")
    found.sort(key=lambda proposal: proposal[0])
    return found, notes


def walk_minutes_files_of_open_approval_walks(walk_finder, parser, pattern):
    paths = []
    for path in sorted(glob.glob(pattern)):
        marker = walk_finder.next_to_present(Path(path).read_text(encoding="utf-8"), parser)
        if marker is not None and not walk_finder.is_closed(marker[0]):
            paths.append(Path(path))
    return paths


def skip_argument(value):
    path, _, line = value.rpartition(":")
    if not path or not line.isdigit():
        raise argparse.ArgumentTypeError(f"`{value}` is not PATH:LINE, as in `/home/x/docs/walk/w-minutes.md:107`")
    return Path(path).resolve(), int(line)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--minutes", type=Path, action="append",
                        help="a walk-minutes file to convert, instead of every open walk's on ned-box; repeatable")
    parser.add_argument("--skip", type=skip_argument, action="append", default=[], metavar="PATH:LINE",
                        help="propose nothing from line LINE of PATH; repeatable")
    parser.add_argument("--as-moved-on", type=skip_argument, action="append", default=[], metavar="PATH:LINE",
                        help="propose a moved-on line, not an already-decided one, for line LINE of PATH; repeatable")
    parser.add_argument("--write", action="store_true", help="append the proposed lines; without it, a dry run")
    arguments = parser.parse_args(argv)
    program = load_walk_me_through_check_program_module()
    walk_finder = program.load_walk_finder()
    markdown = walk_finder.markdown_parser()
    skips, moved_on = collections.defaultdict(set), collections.defaultdict(set)
    for path, line in arguments.skip:
        skips[path].add(line)
    for path, line in arguments.as_moved_on:
        moved_on[path].add(line)
    try:
        paths = arguments.minutes or walk_minutes_files_of_open_approval_walks(walk_finder, markdown, DEFAULT_MINUTES)
    except OSError as error:
        print(f"FAILED: the walk-minutes under {DEFAULT_MINUTES} could not be read: {error}")
        return 1
    failed = False
    for minutes in paths:
        try:
            text = minutes.read_text(encoding="utf-8")
        except OSError as error:
            print(f"FAILED: {minutes} could not be read: {error}")
            failed = True
            continue
        if any(line.strip().startswith(CONVERTED_MARKER) for line in text.split("\n")):
            print(f"== {minutes}: converted already, by the `{CONVERTED_MARKER}` line it holds; nothing to do")
            continue
        skipped = skips[minutes.resolve()]
        found, notes = proposals(program, walk_finder, markdown, text, skipped, moved_on[minutes.resolve()])
        print(f"== {minutes}: {len(found)} line{'' if len(found) == 1 else 's'} to append")
        for index, line, item, proposed in found:
            print(f"line {index + 1}, item {item}: {excerpt(line)}\n  append: {proposed}")
        for note in notes:
            print(note)
        if arguments.write and found:
            expected = expected_reading(program, walk_finder, markdown, text, skipped)
            program.append_to_minutes(minutes, [proposed for _, _, _, proposed in found] + [CONVERTED_MARKER])
            for item in unconverted(program, walk_finder, markdown, minutes.read_text(encoding="utf-8"), expected):
                print(f"FAILED: {minutes}: after the write, item {item} reads as less decided or less deferred than "
                      f"the old reading read it; delete the lines this run appended and report it.")
                failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
