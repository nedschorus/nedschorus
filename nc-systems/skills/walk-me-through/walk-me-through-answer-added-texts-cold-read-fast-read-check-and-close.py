#!/usr/bin/env python3
"""Carry out the user's A, AO, Aa, D, Z, O2 or O3 answer to the waiting item of an
open approval-walk: give each text the answered item adds, its `#new` lines, a
cold-read-fast-read, then record the answer in the walk-minutes and set their
`#next_to_present` line to the next item.

Usage, from the agent-session's checkout:
  walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py check
      [--obvious | --after-advisor | --disapproved | --deferred | --option N]
  walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py close

The answer is an approval, A, unless a flag says otherwise: --obvious for AO,
--after-advisor for Aa, --disapproved for D, --deferred for Z, --option 2 or 3
for O2 or O3, which approve the item's "Option N" paragraph instead of its
recommendation. R, E and O decide nothing, so the program takes no flag for
them.

The open approval-walk and its waiting items are found with WALK_FINDER_FILE,
loaded by path, the module the walk-me-through Stop hook uses too, so the
`#next_to_present` line and the walk-document's item headings are read exactly
as that hook reads them.

CHECK finds the texts the change adds: the item's `#new` lines, a line whose
first word is `#new`, after any list or quotation marker, outside fenced code;
the text is the rest of the line, without one pair of surrounding quotation
marks. For each text it looks for a cold-read-record holding a fast-read.md and
a file under target/ that contains the text, whitespace aside, in the
checkout's cold-read-records/ and in the log-store's. For each text with none,
it saves the text to a scratch file and runs cold-read-fast-read.py --target on
that file. Then it writes the answer line and one status line per text, or "no
proposed text marked", into the walk-minutes, and prints the status lines, the
judgement the agent must make on new reports, and the close step to run. It
appends one line of counts to the log-store's COUNTS_LOG_FILE_NAME. A deferral
changes nothing, so CHECK --deferred runs no fast read, logs no counts, and
writes only the answer line. When the `#next_to_present` line names more than
one item, CHECK refuses, writing nothing, because one run records one answer
for every item it names.

A fast read that prints a line opening FAILED, or exits nonzero, ends CHECK
before the walk-minutes are written: the program prints that line, or a FAILED
line of its own, with FAST_READ_FAILED_LINES, and exits 1; the item stays
waiting. A counts line that cannot be written is printed as such after the
rest, with exit 2.

CLOSE reads the last answer line CHECK wrote. When the `#next_to_present` line
still names that line's items, it records the answer: that it took effect, or,
for a deferral, that the item moves to just before the summary item, the item
whose heading's point opens with "summary"; an item deferred a second time
leaves the walk and stays open. It then writes a `#next_to_present` line as the
minutes' last line, naming the next item: walking the walk-document's items in
order, a once-deferred item placed just before the summary item, from the item
after the answered one, and round again from the first, the first item the
minutes do not record; `none, closed` when there is none. A minutes line
records the items it opens with, after any date or timestamp, as in `Item 4 of
9:`, `- Item 4, <date>:` or `- <timestamp> Item 4 <rejected>`,
when it says approved, disapproved, accepted, rejected or `<moved on, no
decision>`; one that says deferred instead records a deferral; CHECK's answer
lines record nothing. CLOSE refuses, writing nothing, when a line after the
last answer line already opens with its item, because no check has run since
that answer was closed. When the `#next_to_present` line names other items than
the answer line, a new item a finding raised is waiting: the answer is recorded
as held for it, and the line is written again unchanged as the last line.
Either way it prints the lines the agent's next message must include, the
status lines among them.

No open approval-walk, or an item the walk-minutes or the walk-document do not
let the program find, is a failure: one line on stderr, exit 1.

Agent-facing messages follow
docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
"""
import argparse
import collections
import datetime
import importlib.util
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOSITORY_TOP = HERE.parents[2]
WALK_FINDER_FILE = HERE / "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py"
FAST_READ_PROGRAM = REPOSITORY_TOP / "nc-systems" / "cold-read" / "cold-read-fast-read.py"
LOG_STORE = Path("/home/nedlern/nedschorus-logs")
COUNTS_LOG_FILE_NAME = "walk-me-through-answer-added-texts-cold-read-fast-read-already-done-or-had-to-run-counts-per-check.tsv"
RECORDS_DIRECTORY_NAME = "cold-read-records"
PROGRAM = "walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close"

NEW_LINE = re.compile(r"^\s*(?:(?:[-*+]|\d+[.)]|>)\s+)*#new\b[:\s]*(.*)$")
QUOTE_PAIRS = (('"', '"'), ("“", "”"), ("'", "'"))
ANSWER_LINE = re.compile(r"^(?P<item>items? .+?): the user answered (?P<answered>.+?)"
                         r"(?: #approved_(?:obvious|after_advisor))? \([^)]*\), "
                         r"which makes (?:its change\. Fast reads:|no change\.)$")
STATUS_LINE_PREFIX = "- "
OBVIOUS_HASHTAG = " #approved_obvious"
AFTER_ADVISOR_HASHTAG = " #approved_after_advisor"
APPROVED, DISAPPROVED, DEFERRED = "approved", "disapproved", "deferred"
OUTCOMES = {APPROVED: "<accepted>", DISAPPROVED: "<rejected>"}

NO_PROPOSED_TEXT = "no proposed text marked"
STATUS_ALREADY_DONE = "`#new` text {number}, \"{excerpt}\": fast read already done ({record})."
STATUS_HAD_TO_BE_RUN = "`#new` text {number}, \"{excerpt}\": fast read had to be run ({record})."
CHECK_JUDGEMENT_LINES = (
    "Read each fast-read report named above as had to be run.",
    "If a finding holds and changes how a text is understood but not what the item decides, "
    "apply it to that text's `#new` line in the walk-document {document}.",
    "If a finding would change what the item decides, write that change as a new item right "
    "after {item} in the walk-document, numbered as the walk-me-through skill's Re-planning section "
    "says, and set the minutes' `#next_to_present` line to the new item; "
    "the close step says when to present it.",
)
CHECK_CLOSE_LINE = "Then run `python3 {program} close --cwd {top}` and do what it prints."
COUNTS_NOT_LOGGED = (
    "The fast-read counts were not logged to {log}: {error}.",
    "Include this line in your next message to the user, and carry on as the lines above say.",
)
FAST_READ_FAILED_LINES = (
    "The item stays waiting: the minutes do not record the answer.",
    "Tell the user the line above, and ask whether to run `python3 {program} check{flags}` again or "
    "answer the item another way.",
)
CHECK_MINUTES = "{item}: the user answered {answered}{hashtag} ({date_and_time}), which makes its change. Fast reads:"
CHECK_DEFERRED_MINUTES = "{item}: the user answered deferred ({date_and_time}), which makes no change."
CLOSE_TOOK_EFFECT_MINUTES = "{item}: {answered}; every text the change adds has had a fast read. {outcome}"
CLOSE_DEFERRED_MINUTES = "{item}: deferred; it moves to just before the summary item. <open>"
CLOSE_DEFERRED_AGAIN_MINUTES = "{item}: deferred a second time, so it leaves the walk and stays open. <open>"
CHECK_SEVERAL_WAITING = (
    "nothing written: the `#next_to_present` line in {minutes} names more than one item waiting, {item}, "
    "and one check run records one answer for all of them.\n"
    "Ask the user to answer those items one at a time, and run check for each answer as it comes.")
CLOSE_ALREADY_RECORDED = (
    "nothing written: the last answer line in {minutes}, for {item}, is already recorded by an earlier close, "
    "so no check has run since then.\n"
    "Run `python3 {program} check` first, with the flag for the user's answer as `--help` lists it, then close.\n"
    "If check failed, fix what it printed before running close.")
CLOSE_HELD_MINUTES = "{item}: answer held: {new_item}, raised by a fast-read finding, waits for the user's answer. <open>"
CLOSE_TOOK_EFFECT_LINES = (
    "{item}'s answer is recorded in the minutes, and its change may now be made.",
    "Your next message must include these lines, as they are:",
)
CLOSE_DEFERRED_LINES = (
    "{item} is deferred, and the minutes record it; it comes back just before the summary item.",
    "Your next message must include these lines, as they are:",
)
CLOSE_DEFERRED_AGAIN_LINES = (
    "{item} is deferred a second time, so the minutes record it as open and it leaves the walk.",
    "Add it to your task list if it is not already a task.",
    "Your next message must include these lines, as they are:",
)
CLOSE_HELD_LINES = (
    "{item}'s answer does not take effect yet: {new_item}, which a fast-read finding raised, is waiting, "
    "and the minutes record the answer as held for it.",
    "Your next message must include these lines, as they are:",
)
CLOSE_TOOK_EFFECT_NEXT = (
    "If the change needs nothing more from the user, such as a text he has not yet seen, start it as the "
    "walk-me-through skill's sentence on ready work says; if it edits a file that work you dispatched "
    "earlier is still editing, start it when that earlier work finishes.",
)
CLOSE_NEXT_ITEM = "Then present {next_item}, which the minutes' `#next_to_present` line now names."
CLOSE_NO_NEXT_ITEM = ("No item is left to present, and the minutes' `#next_to_present` line now reads "
                      "`none, closed`: go on to the walk-me-through skill's closing.")
NEXT_MARKER_LINE = "#next_to_present {value}"
CLOSED_MARKER_VALUE = "none, closed"
RECORDED_ITEMS = re.compile(r"^\s*(?:(?:[-*+]|\d+[.)]|>)\s+)*[*_]*(items?\s+[^:(]*)", re.I)
DATE = re.compile(r"\d{4}-\d\d-\d\d(?:[T ]\d\d:\d\d(?::\d\d(?:\.\d+)?)?(?:Z|[+-]\d\d:?\d\d)?)?")
DECIDED = re.compile(r"\b(?:dis)?approved\b|\baccepted\b|\brejected\b|<moved on, no decision>", re.I)
DEFERRED_WORD = re.compile(r"\bdeferred\b", re.I)
SUMMARY_HEADING = re.compile(r"\bof\s+\d+\b[*_\s:.\-\u2013\u2014]*summary\b", re.I)
CLOSE_HELD_NEXT = ("Then present {new_item}, and record the user's answer to it in the minutes as "
                   "the outcome of {item} too.")


class Failure(Exception):
    """A step that cannot go on; its argument is the line to print."""


class FastReadFailed(Exception):
    """A fast read failed; its argument is the FAILED line, printed as it is."""


def load_walk_finder():
    spec = importlib.util.spec_from_file_location(
        "walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common", WALK_FINDER_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def the_open_walk(walk_finder, cwd):
    """Return (checkout top, minutes path, #next_to_present value, parser)."""
    top = walk_finder.checkout_top(Path(cwd))
    if top is None:
        raise Failure(f"{cwd} is not in a git checkout, so no approval-walk can be open there.")
    parser = walk_finder.markdown_parser()
    walk_directory = top / walk_finder.WALK_DIRECTORY
    walk = walk_finder.open_walk(walk_directory, parser) if walk_directory.is_dir() else None
    if walk is None:
        raise Failure(f"no approval-walk is open in {walk_directory}.")
    minutes, value, _ = walk
    return top, minutes, value, parser


def waiting_items(walk_finder, value, minutes):
    """Return (running count such as `item 4.1 of 6`, item numbers, M or None) of the `#next_to_present` value."""
    match = walk_finder.VALUE_COUNT.match(value)
    if not match:
        raise Failure(f"the last `#next_to_present` line in {minutes}, `{value}`, names no item.")
    try:
        numbers, total = walk_finder.parse_items(value)
    except walk_finder.UnusableRange as problem:
        raise Failure(f"the last `#next_to_present` line in {minutes}, `{value}`, {problem}.")
    return match[0], numbers, total


def item_lines(walk_finder, minutes, numbers, total, count, parser):
    """Return (walk-document path, the lines of the items numbered, outside fenced code)."""
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    if not document.is_file():
        raise Failure(f"the walk-document {document} does not exist.")
    text = document.read_text(encoding="utf-8")
    spans = [unit for unit in walk_finder.item_unit_spans(text, parser)
             if set(unit[0]) & set(numbers) and (total is None or unit[1] == total)]
    if not spans:
        raise Failure(f"the walk-document {document} has no heading for `{count}`.")
    code = walk_finder.code_line_numbers(parser.parse(text))
    lines = text.split("\n")
    kept = []
    for unit_numbers, unit_total, _, first, end in spans:
        if len(numbers) == 1 and len(unit_numbers) > 1:
            own_first, own_end = walk_finder.approval_walk_item_line_range_within_heading_shared_by_several_items(
                lines[first:end], numbers[0], unit_numbers, unit_total)
            first, end = first + own_first, first + own_end
        kept += [lines[number] for number in range(first, end) if number not in code]
    return document, kept


def proposed_texts(lines):
    texts = []
    for line in lines:
        match = NEW_LINE.match(line)
        if not match:
            continue
        text = match[1].strip()
        for opening, closing in QUOTE_PAIRS:
            if len(text) >= 2 and text.startswith(opening) and text.endswith(closing):
                text = text[1:-1].strip()
                break
        if text:
            texts.append(text)
    return texts


def squeezed(text):
    return " ".join(text.split())


def fast_read_record_holding(text, record_directories):
    """Return the cold-read-record directory whose fast read read the text, or None."""
    wanted = squeezed(text)
    for directory in record_directories:
        if not directory.is_dir():
            continue
        for record in sorted(directory.iterdir()):
            if not (record / "fast-read.md").is_file() or not (record / "target").is_dir():
                continue
            for target in (record / "target").rglob("*"):
                if target.is_file() and wanted in squeezed(target.read_text(encoding="utf-8", errors="replace")):
                    return record
    return None


def run_fast_read(text, name, fast_read_program):
    """Fast-read the text from a scratch file; return the report's directory, or raise FastReadFailed."""
    scratch = Path(tempfile.mkdtemp(prefix=PROGRAM + "-"))
    target = scratch / f"{name}.md"
    target.write_text(text + "\n", encoding="utf-8")
    result = subprocess.run([sys.executable, str(fast_read_program), "--target", str(target)],
                            capture_output=True, text=True)
    lines = result.stdout.strip().split("\n")
    failed = [line for line in lines if line.startswith("FAILED")]
    if failed:
        raise FastReadFailed(failed[0])
    if result.returncode != 0 or not lines[-1]:
        raise FastReadFailed(f"FAILED: {fast_read_program} --target {target} exited {result.returncode} "
                             f"without naming a report; its stderr: {result.stderr.strip()[-500:]}")
    return Path(lines[-1]).parent


def excerpt(text):
    return text if len(text) <= 60 else text[:57].rstrip() + "..."


def file_name_part(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def append_to_minutes(minutes, lines):
    existing = minutes.read_text(encoding="utf-8")
    separator = "" if existing.endswith("\n") else "\n"
    with open(minutes, "a", encoding="utf-8") as file:
        file.write(separator + "\n".join(lines) + "\n")


def answered_word(arguments):
    """The answer as the walk-minutes write it: approved, disapproved, or approved option N."""
    if arguments.disapproved:
        return DISAPPROVED
    if arguments.deferred:
        return DEFERRED
    if arguments.option is not None:
        return f"{APPROVED} option {arguments.option}"
    return APPROVED


def answer_hashtag(arguments):
    """The hashtag the walk-minutes write right after an AO or Aa approval, or nothing."""
    if arguments.obvious:
        return OBVIOUS_HASHTAG
    if arguments.after_advisor:
        return AFTER_ADVISOR_HASHTAG
    return ""


def check_flags(arguments):
    """The flags this check step was run with, to repeat in the command it tells the agent to rerun."""
    flags = ""
    if arguments.obvious:
        flags += " --obvious"
    if arguments.after_advisor:
        flags += " --after-advisor"
    if arguments.disapproved:
        flags += " --disapproved"
    if arguments.deferred:
        flags += " --deferred"
    if arguments.option is not None:
        flags += f" --option {arguments.option}"
    return flags


def check(arguments):
    walk_finder = load_walk_finder()
    top, minutes, value, parser = the_open_walk(walk_finder, arguments.cwd)
    item, numbers, total = waiting_items(walk_finder, value, minutes)
    if numbers[1:]:
        raise Failure(CHECK_SEVERAL_WAITING.format(minutes=minutes, item=item))
    document, lines = item_lines(walk_finder, minutes, numbers, total, item, parser)
    if arguments.deferred:
        now = datetime.datetime.now().astimezone()
        append_to_minutes(minutes, [CHECK_DEFERRED_MINUTES.format(item=item, date_and_time=f"{now:%Y-%m-%d %H:%M}")])
        print(CHECK_CLOSE_LINE.format(program=Path(__file__).resolve(), top=shlex.quote(str(top))))
        return 0
    texts = proposed_texts(lines)
    record_directories = arguments.cold_read_records or [top / RECORDS_DIRECTORY_NAME,
                                                         LOG_STORE / RECORDS_DIRECTORY_NAME]
    walk_name = minutes.name[:-len(walk_finder.MINUTES_SUFFIX)]
    statuses, already_done, had_to_be_run = [], 0, 0
    for number, text in enumerate(texts, 1):
        record = fast_read_record_holding(text, record_directories)
        if record is not None:
            already_done += 1
            statuses.append(STATUS_ALREADY_DONE.format(number=number, excerpt=excerpt(text), record=record))
            continue
        name = f"{walk_name}-{file_name_part(item)}-new-{number}"
        record = run_fast_read(text, name, arguments.fast_read_program)
        had_to_be_run += 1
        statuses.append(STATUS_HAD_TO_BE_RUN.format(number=number, excerpt=excerpt(text), record=record))
    if not texts:
        statuses.append(NO_PROPOSED_TEXT)
    now = datetime.datetime.now().astimezone()
    append_to_minutes(minutes, [CHECK_MINUTES.format(item=item, answered=answered_word(arguments),
                                                     hashtag=answer_hashtag(arguments),
                                                     date_and_time=f"{now:%Y-%m-%d %H:%M}")]
                      + [STATUS_LINE_PREFIX + status for status in statuses])
    output = list(statuses)
    if had_to_be_run:
        output += [line.format(document=document, item=item) for line in CHECK_JUDGEMENT_LINES]
    output.append(CHECK_CLOSE_LINE.format(program=Path(__file__).resolve(), top=shlex.quote(str(top))))
    log = arguments.counts_log or LOG_STORE / COUNTS_LOG_FILE_NAME
    try:
        with open(log, "a", encoding="utf-8") as file:
            file.write("\t".join([now.isoformat(timespec="seconds"), walk_name, item,
                                  f"texts={len(texts)}", f"already_done={already_done}",
                                  f"had_to_be_run={had_to_be_run}"]) + "\n")
    except OSError as error:
        output += [line.format(log=log, error=error) for line in COUNTS_NOT_LOGGED]
        print("\n".join(output))
        return 2
    print("\n".join(output))
    return 0


def last_answer(minutes):
    """Return (item, answered, status lines) of the walk-minutes' last answer line, or raise Failure when
    there is none or a close already recorded it."""
    lines = minutes.read_text(encoding="utf-8").split("\n")
    for index in range(len(lines) - 1, -1, -1):
        match = ANSWER_LINE.match(lines[index])
        if match:
            statuses = []
            for line in lines[index + 1:]:
                if not line.startswith(STATUS_LINE_PREFIX):
                    break
                statuses.append(line[len(STATUS_LINE_PREFIX):])
            # Every line close writes for an answer opens with its item; without this, a close after a
            # check that failed reads the earlier, already closed answer as one held for a new item.
            if any(line.startswith(match["item"] + ": ") for line in lines[index + 1:]):
                raise Failure(CLOSE_ALREADY_RECORDED.format(minutes=minutes, item=match["item"],
                                                            program=Path(__file__).resolve()))
            return match["item"], match["answered"], statuses
    raise Failure(f"{minutes} has no line recording the user's answer; run "
                  f"`python3 {Path(__file__).resolve()} check` first, with the flag for the user's answer as "
                  f"`--help` lists it.")


def walk_document_items(walk_finder, minutes, value, numbers, total, parser):
    """Return (M, the walk-document's item numbers of total M in order, the summary item's number or None)."""
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    try:
        total, _ = walk_finder.waiting_item_units(document, value, numbers, total, parser)
    except walk_finder.UnusableRange as problem:
        raise Failure(f"the last `#next_to_present` line in {minutes}, `{value}`: {problem}")
    text = document.read_text(encoding="utf-8")
    lines = text.split("\n")
    order, summary = [], None
    for unit_numbers, unit_total, _, first, _ in walk_finder.item_unit_spans(text, parser):
        if unit_total != total:
            continue
        order += [number for number in unit_numbers if number not in order]
        if unit_numbers and SUMMARY_HEADING.search(lines[first]):
            summary = unit_numbers[0]
    return total, order, summary


def minutes_record(walk_finder, minutes_text, parser):
    """Return (the item numbers a minutes line decides, a Counter of how many lines defer each item)."""
    code = walk_finder.code_line_numbers(parser.parse(minutes_text))
    decided, deferrals = set(), collections.Counter()
    for number, line in enumerate(minutes_text.split("\n")):
        if number in code or ANSWER_LINE.match(line):
            continue
        match = RECORDED_ITEMS.match(DATE.sub("", line))
        if not match:
            continue
        try:
            items, _ = walk_finder.parse_items(match[1].strip())
        except walk_finder.UnusableRange:
            continue
        if DECIDED.search(line):
            decided.update(items)
        elif DEFERRED_WORD.search(line):
            for item in items:
                deferrals[item] += 1
    return decided, deferrals


def next_item(order, summary, answered_numbers, waiting_numbers, decided, deferrals):
    """Return the item numbers the `#next_to_present` line must name next, or [] when the minutes record
    every item.

    Items shown with the answered one that the minutes do not record yet stay waiting. Otherwise the walk
    goes through the walk-document's items in order, an item deferred once and not decided moved to just
    before the summary item, or to the end when there is none, and names the first item the minutes do
    not record. It starts at the last answered item, or, when that item was just deferred, at the first
    item after it in the walk-document that is not deferred, and goes round once.
    """
    recorded = {item for item in order if item in decided or deferrals[item] > 1}
    still_waiting = [item for item in waiting_numbers if item not in recorded and item not in answered_numbers]
    if still_waiting:
        return still_waiting
    waiting_deferred = [item for item in order if item not in recorded and item in deferrals]
    in_place = [item for item in order if item not in waiting_deferred]
    cut = in_place.index(summary) if summary in in_place else len(in_place)
    walk = in_place[:cut] + waiting_deferred + in_place[cut:]
    answered = [index for index, item in enumerate(order) if item in answered_numbers]
    anchors = [item for item in order[answered[-1]:] if item in in_place] if answered else []
    start = walk.index(anchors[0]) if anchors else 0
    return [item for item in walk[start:] + walk[:start] if item not in recorded][:1]


def close(arguments):
    walk_finder = load_walk_finder()
    _, minutes, value, parser = the_open_walk(walk_finder, arguments.cwd)
    item, answered, statuses = last_answer(minutes)
    waiting, waiting_numbers, total = waiting_items(walk_finder, value, minutes)
    try:
        answered_numbers, _ = walk_finder.parse_items(item)
    except walk_finder.UnusableRange as problem:
        raise Failure(f"the last answer line in {minutes}, `{item}`, {problem}.")
    if not set(answered_numbers) <= set(waiting_numbers):
        append_to_minutes(minutes, [CLOSE_HELD_MINUTES.format(item=item, new_item=waiting),
                                    NEXT_MARKER_LINE.format(value=value)])
        output = ([line.format(item=item, new_item=waiting) for line in CLOSE_HELD_LINES] + statuses
                  + [CLOSE_HELD_NEXT.format(item=item, new_item=waiting)])
        print("\n".join(output))
        return 0
    total, order, summary = walk_document_items(walk_finder, minutes, value, waiting_numbers, total, parser)
    if answered == DEFERRED:
        _, deferrals = minutes_record(walk_finder, minutes.read_text(encoding="utf-8"), parser)
        again = any(deferrals[number] for number in answered_numbers)
        recorded = (CLOSE_DEFERRED_AGAIN_MINUTES if again else CLOSE_DEFERRED_MINUTES).format(item=item)
        lines = CLOSE_DEFERRED_AGAIN_LINES if again else CLOSE_DEFERRED_LINES
        output = [line.format(item=item) for line in lines] + statuses
    else:
        outcome = OUTCOMES[DISAPPROVED if answered == DISAPPROVED else APPROVED]
        recorded = CLOSE_TOOK_EFFECT_MINUTES.format(item=item, answered=answered, outcome=outcome)
        output = ([line.format(item=item) for line in CLOSE_TOOK_EFFECT_LINES] + statuses
                  + list(CLOSE_TOOK_EFFECT_NEXT))
    append_to_minutes(minutes, [recorded])
    decided, deferrals = minutes_record(walk_finder, minutes.read_text(encoding="utf-8"), parser)
    numbers = next_item(order, summary, answered_numbers, waiting_numbers, decided, deferrals)
    named = f"item{'s' if numbers[1:] else ''} {' and '.join(numbers)} of {total}"
    append_to_minutes(minutes, [NEXT_MARKER_LINE.format(value=named if numbers else CLOSED_MARKER_VALUE)])
    output.append(CLOSE_NEXT_ITEM.format(next_item=named) if numbers else CLOSE_NO_NEXT_ITEM)
    print("\n".join(output))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("step", choices=("check", "close"))
    answer = parser.add_mutually_exclusive_group()
    answer.add_argument("--obvious", action="store_true", help="check: the answer was AO, approve as obvious")
    answer.add_argument("--after-advisor", action="store_true",
                        help="check: the answer was Aa, approve after an advisor check")
    answer.add_argument("--disapproved", action="store_true", help="check: the answer was D, disapprove")
    answer.add_argument("--deferred", action="store_true", help="check: the answer was Z, defer")
    answer.add_argument("--option", type=int, choices=(2, 3),
                        help="check: the answer was O2 or O3, approving the item's \"Option N\" paragraph")
    parser.add_argument("--cwd", default=os.getcwd(), help="a directory in the walk's checkout")
    parser.add_argument("--cold-read-records", type=Path, action="append",
                        help="a cold-read-records directory to search instead of the defaults; repeatable")
    parser.add_argument("--fast-read-program", type=Path, default=FAST_READ_PROGRAM)
    parser.add_argument("--counts-log", type=Path)
    arguments = parser.parse_args(argv)
    try:
        return check(arguments) if arguments.step == "check" else close(arguments)
    except Failure as failure:
        print(f"{PROGRAM} {arguments.step}: {failure.args[0]}", file=sys.stderr)
        return 1
    except FastReadFailed as failure:
        print("\n".join([failure.args[0]] + [line.format(program=Path(__file__).resolve(),
                                                          flags=check_flags(arguments))
                                              for line in FAST_READ_FAILED_LINES]))
        return 1


if __name__ == "__main__":
    sys.exit(main())
