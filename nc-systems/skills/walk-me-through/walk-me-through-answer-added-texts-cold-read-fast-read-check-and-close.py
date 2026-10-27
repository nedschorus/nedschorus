#!/usr/bin/env python3
"""Carry out the user's A, AO, Aa, D, Z, O2 or O3 answer to the waiting item of an
open approval-walk, or his A, AO or D answer to each part of it: give each text
the answer adds a cold-read-fast-read, then record the answer in the
walk-minutes and set their `#next_to_present` line to the next item.

Usage, from the agent-session's checkout:
  walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py check
      [--obvious | --after-advisor | --disapproved | --deferred | --option N
       | --part-answer N=ANSWER ...]
  walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py close

The answer is an approval, A, unless a flag says otherwise: --obvious for AO,
--after-advisor for Aa, --disapproved for D, --deferred for Z, --option 2 or 3
for O2 or O3, which approve the item's "Option N" paragraph instead of its
recommendation. R, E and O decide nothing, so the program takes no flag for
them. --part-answer, given once for each part of an item that holds parts, as
in `--part-answer 1=A --part-answer 2=D`, gives that part its own answer, A, AO
or D. Z is not taken for a part, and a part number given twice is refused,
writing nothing.

The texts an answer adds are the item's lines that begin with the answer's
mark, `#new` or `#new_if_d`, as CHECK below describes them. A, AO, Aa, O2 and
O3 add the `#new` texts; D adds only the `#new_if_d` texts, the texts of the
alternative that D does instead of the item's recommendation. A line's mark
belongs to the whole item, not to a part, so answers to parts add the `#new`
texts when any part is A or AO, and the `#new_if_d` texts when any part is D.
An answer that adds no marked text gets no fast read, and its status line is
"no proposed text marked".

Every answer but O2 and O3 needs the item's `#case_against` line, the first
line of the item, outside fenced code, whose first word after any list,
quotation or emphasis marker is `#case_against`, followed by a rating: none,
weak, medium, strong or very strong. CHECK writes the rating into the answer
line as a hashtag right after the answer, as in `approved #approved_obvious
#case_against_weak`, so that one search finds every rating beside its answer.
An item with no such line, or one whose line opens with no rating, is refused,
writing nothing; O2 and O3 record the rating when the line is there.

`--not-asked KIND` settles the item without the user, as kind KIND, 1 to 5, of
the walk-me-through skill's list of items that need no answer, after checking
what code can from the item's evidence lines, each opening with its marker:
`#not_asked_touches` lists the files the change edits or deletes;
`#not_asked_test` names the test that fails before a fix and passes after it;
`#not_asked_source` cites the ruling, merged code or command; `#not_asked_unused`
names a thing removed; `#not_asked_rename` gives the old name, then the new one.
Every kind needs a case against rated none or weak. Kind 1, text caught up,
needs touches, a source and a `#new` text; kind 2, a code fix, needs touches
and a test, and every touched file must exist except that test; kind 3, a
removal, needs touches, and each unused name must appear, by `git grep`, in no
file outside the touched ones and docs/walk/, or, with no unused line, every
touched file must be Markdown; kind 4, a rename, needs touches and a rename
line, the new name in a `*glossary*.md` file, and the old name in no file
outside the touched ones and docs/walk/; kind 5, carrying out a ruling, needs a
source; for kinds 1 to 4 every touched file but a kind 2 test must exist. A
failed check is refused, writing nothing, with every problem listed; a `git
grep` that fails is a failure too. Otherwise CHECK fast-reads the `#new` texts as
for A, writes the line `<item>: settled without asking the user, not asked,
kind KIND #case_against_<rating> (...)`, and tells the agent to ask the advisor
and judge what code cannot before running CLOSE, which records the item as
`<accepted>`. The checks cannot tell a case against that names only cost from
another weak one, or a fix that matches its design from one that does not;
the agent judges those.

The open approval-walk and its waiting items are found with
walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py,
beside this program and loaded by path, the module the walk-me-through Stop
hook uses too, so the
`#next_to_present` line and the walk-document's item headings are read exactly
as that hook reads them.

CHECK finds the texts the answer adds: the item's lines whose first word,
after any list or quotation marker, outside fenced code, is a mark the answer adds;
the text is the rest of the line, without one pair of surrounding quotation
marks. For each text it looks for a cold-read-record holding a fast-read.md and
a file under target/ that contains the text, whitespace aside, in the
checkout's cold-read-records/ and in the log-store's. The log-store's
cold-read-records directory is the path in cold-read-record-ship.py's
LOG_STORE_RECORDS_DESTINATION, read on ned-box as it is and on the Mac through
the Mac's mount of ned-box's home. For each text with none, it saves the text to
a scratch file and runs cold-read-fast-read.py --target on that file. Then it
writes the answer line, which names each part's answer in part number order
when --part-answer is given, and one status line per text, naming its mark and
its number, from 1 in the walk-document's order, among the item's texts with
that mark, or "no proposed text
marked", into the walk-minutes, and prints the status lines, the judgement the
agent must make on new reports, and the close step to run. It appends one line
of counts to
walk-me-through-answer-added-texts-cold-read-fast-read-already-done-or-had-to-run-counts-per-check.tsv
beside the log-store's cold-read-records directory. A deferral
changes nothing, so CHECK --deferred runs no fast read, logs no counts, and
writes only the answer line. When the `#next_to_present` line names more than
one item, CHECK refuses, writing nothing, because a run would record its one
answer, or its one set of part answers, for every item that line names; CHECK
then tells the agent to add a `#next_to_present` line naming one of those items
before each check run.

A fast read that prints a line opening FAILED, or exits nonzero, ends CHECK
before the walk-minutes are written: the program prints that line, or a FAILED
line of its own, then says the item stays waiting and tells the agent to ask
the user whether to run check again, and exits 1. A fast read that succeeds but says on stderr that its record was not
shipped, or that its target changed during the read, has that line added to its
status line. An unshipped record, a log-store this machine cannot reach, and a
counts line that cannot be written are each printed after the rest, saying the
minutes record the answer, with exit 2; a changed target alone leaves the exit
code 0, since the report was written.

CLOSE reads the last answer line CHECK wrote. When the `#next_to_present` line
still names that line's items, it records the answer: that it took effect, or,
for answers to parts, a single line for the item naming each part's outcome,
or, for a deferral, that the item moves to just before the summary item, the item
whose heading's point opens with "summary"; an item deferred a second time
leaves the walk and stays open. It then writes a `#next_to_present` line as the
minutes' last line, naming the next item: walking the walk-document's items in
order, a once-deferred item placed just before the summary item, from the item
after the answered one, and round again from the first, the first item the
minutes do not record; `none, closed` when there is none. A minutes line
records the items it opens with, after any date or timestamp, as in `Item 4 of
9:`, `- Item 4, <date>:` or `- <timestamp> Item 4 <rejected>`,
when it says approved, disapproved, accepted, rejected or `<moved on, no
decision>`; one that says deferred instead records a deferral; a word right
after the, a or an, as in "the approved definition", says neither; CHECK's
answer lines record nothing. A line with an outcome tag, `<accepted>`, `<rejected>`,
`<moved on, no decision>` or `<approved as revised>`, records a decision
whatever else it says; one with only `<open>` or `<revised, awaiting ruling>`
records none, and records a deferral when its first word after the items is
deferred; so does a line with no such tag whose first word is deferred. A
`<revised, awaiting ruling>` tag also undoes an earlier line's decision of its
items, and outweighs a deciding tag on its own line; `<open>` does neither.
CLOSE refuses, writing nothing, when a line after the
last answer line already opens with the last answer line's item and a colon, as
every line close writes for an answer does: that answer was closed already, and
no check has run since. When the `#next_to_present` line names other items than
the answer line, a new item a finding raised is waiting: the answer is recorded
as held until the user answers the new item, and the line is written again unchanged as the last line.
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
RECORD_SHIPPER_FILE = REPOSITORY_TOP / "nc-systems" / "cold-read" / "cold-read-record-ship.py"
PATH_CONSTANTS_FILE = (REPOSITORY_TOP / "nc-systems" / "general-tools"
                       / "ned-box-home-directory-and-its-mac-mount-point-path-constants-common.py")
COUNTS_LOG_FILE_NAME = "walk-me-through-answer-added-texts-cold-read-fast-read-already-done-or-had-to-run-counts-per-check.tsv"
RECORDS_DIRECTORY_NAME = "cold-read-records"
PROGRAM = "walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close"

NEW_MARK, NEW_IF_D_MARK = "#new", "#new_if_d"
NEW_LINE = re.compile(r"^\s*(?:(?:[-*+]|\d+[.)]|>)\s+)*(#new(?:_if_d)?)\b[:\s]*(.*)$")
QUOTE_PAIRS = (('"', '"'), ("“", "”"), ("'", "'"))
ANSWER_LINE = re.compile(r"^(?P<item>items? .+?): (?:the user answered|settled without asking the user,) "
                         r"(?P<answered>.+?)(?: #approved_(?:obvious|after_advisor))?(?: #case_against_[a-z_]+)? "
                         r"\([^)]*\), which makes (?:its change\. Fast reads:|no change\.)$", re.I)
CASE_AGAINST_LINE = re.compile(r"^\s*(?:(?:[-*+]|\d+[.)]|>)\s+)*[*_`]*#case_against\b[*_`]*[:\s]*(.*)$")
CASE_AGAINST_RATING = re.compile(r"(very strong|none|weak|medium|strong)\b", re.I)
CASE_AGAINST_HASHTAG = " #case_against_{rating}"
NOT_ASKED_RATINGS = ("none", "weak")
NOT_ASKED_KINDS = (1, 2, 3, 4, 5)
EVIDENCE_LINE = re.compile(r"^\s*(?:(?:[-*+]|\d+[.)]|>)\s+)*[*_`]*(#not_asked_(?:touches|test|source|unused|rename))\b"
                           r"[*_`]*[:\s]*(.*)$")
TOUCHES, TEST, SOURCE, UNUSED, RENAME = (f"#not_asked_{name}" for name in ("touches", "test", "source", "unused",
                                                                        "rename"))
GLOSSARY_FILES = "*glossary*.md"
STATUS_LINE_PREFIX = "- "
OBVIOUS_HASHTAG = " #approved_obvious"
AFTER_ADVISOR_HASHTAG = " #approved_after_advisor"
APPROVED, DISAPPROVED, DEFERRED = "approved", "disapproved", "deferred"
OUTCOMES = {APPROVED: "<accepted>", DISAPPROVED: "<rejected>"}
PART_WORDS = {"A": APPROVED, "AO": APPROVED + OBVIOUS_HASHTAG, "D": DISAPPROVED}
PART_ARGUMENT = re.compile(r"^(\d+)=(ao|a|d)$", re.I)
# ANSWER_LINE's `answered` loses a last part's hashtag, so close reads each part's word on its own.
PART_IN_ANSWER = re.compile(r"\bpart (\d+) ((?:dis)?approved)\b")
PART_ARGUMENT_PROBLEM = ("`{value}` is not a part's answer: give the part's number, `=`, then A, AO or D, as in "
                         "`1=A`; a part takes no Z, so a deferral is given to the whole item with --deferred")
PART_REPEATED = ("nothing written: --part-answer gives {parts} more than one answer.\n"
                 "Run check again giving each part's number once, with the letter the user gave that part.")

NO_PROPOSED_TEXT = "no proposed text marked"
STATUS_ALREADY_DONE = "`{mark}` text {number}, \"{excerpt}\": fast read already done ({record})."
STATUS_HAD_TO_BE_RUN = "`{mark}` text {number}, \"{excerpt}\": fast read had to be run ({record})."
STATUS_FAST_READ_NOTE = " The fast read also said: {note}"
# The fast read reports these on stderr and still exits 0, because its report was written.
FAST_READ_NOTE_MARKERS = ("cold-read-fast-read: record: FAILED", "#cold_read_target_changed_during_run")
CHECK_JUDGEMENT_LINES = (
    "Read the fast-read report of each text above whose status line says \"fast read had to be run\".",
    "If a finding holds and changes how a text is understood but not what the item decides, "
    "apply it to that text's marked line in the walk-document {document}.",
    "If a finding would change what the item decides, write that change as a new item right "
    "after {item} in the walk-document, numbered as the walk-me-through skill's Re-planning section "
    "says, and set the minutes' `#next_to_present` line to the new item; "
    "the close step says when to present it.",
)
CHECK_CLOSE_LINE = "Then run `python3 {program} close --cwd {top}` and do what it prints."
COUNTS_NOT_LOGGED = (
    "The minutes record the answer, but the fast-read counts were not logged to {log}: {error}.",
    "Include this line in your next message to the user, and carry on as the lines above say.",
)
LOG_STORE_UNREACHABLE = ("this machine reaches the log-store at neither {paths}, so its cold-read-records were "
                         "not searched either")
RECORDS_NOT_SHIPPED = (
    "The minutes record the answer, but the fast read of `{mark}` text {number} did not ship its record: {note}",
    "The record stays at {record}; once ned-box can be reached, run `python3 {shipper} {record}`.",
    "Include these lines in your next message to the user, and carry on as the lines above say.",
)
FAST_READ_FAILED_LINES = (
    "The item stays waiting: the minutes do not record the answer.",
    "Tell the user the line above, and ask whether to run `python3 {program} check{flags}` again or "
    "answer the item another way.",
)
CHECK_MINUTES = ("{item}: the user answered {answered}{hashtag}{rating} ({date_and_time}), which makes its change. "
                 "Fast reads:")
CHECK_NOT_ASKED_MINUTES = ("{item}: settled without asking the user, {answered}{rating} ({date_and_time}), which makes "
                           "its change. Fast reads:")
CHECK_DEFERRED_MINUTES = "{item}: the user answered deferred{rating} ({date_and_time}), which makes no change."
CLOSE_TOOK_EFFECT_MINUTES = "{item}: {answered}; every text the change adds has had a fast read. {outcome}"
CLOSE_PARTS_TOOK_EFFECT_MINUTES = "{item}: {parts}; every text the change adds has had a fast read."
CLOSE_DEFERRED_MINUTES = "{item}: deferred; it moves to just before the summary item. <open>"
CLOSE_DEFERRED_AGAIN_MINUTES = "{item}: deferred a second time, so it leaves the walk and stays open. <open>"
CHECK_SEVERAL_WAITING = (
    "nothing written: the `#next_to_present` line in {minutes} names more than one item waiting, {item}, "
    "and one check run records one answer for all of them.\n"
    "For each of those items the user has answered, in the order he gave the answers: add the line "
    "`{one_item_line}`, with that item's number, as the minutes' last line, then run check with the flag for "
    "his answer to it, then close.\n"
    "Present the item that `close` names only after the last of those answers is recorded.\n"
    "If he has not answered some of those items, ask him to answer them.")
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
    "{item}'s answer does not take effect yet: {new_item}, which a fast-read finding raised, waits for the "
    "user's answer, and the minutes record {item}'s answer as held until he answers {new_item}.",
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
MODIFIER_BEFORE = re.compile(r"\b(?:the|a|an)\s+$", re.I)
OUTCOME_TAG = re.compile(r"<([^<>]+)>")
DECIDING_OUTCOMES = {"accepted", "rejected", "moved on, no decision", "approved as revised"}
AWAITING_RULING = "revised, awaiting ruling"
UNDECIDED_OUTCOMES = {"open", AWAITING_RULING}
FIRST_WORD = re.compile(r"^[\s,:;*_.)\-\u2013\u2014]*(\w+)")
SUMMARY_HEADING = re.compile(r"\bof\s+\d+\b[*_\s:.\-\u2013\u2014]*summary\b", re.I)
CLOSE_HELD_NEXT = ("Then present {new_item}, and record the user's answer to it in the minutes as "
                   "the outcome of {item} too.")
CASE_AGAINST_MISSING = (
    "nothing written: {item} in {document} has no `#case_against` line, and every answer records the item's "
    "case-against rating beside it in the minutes, so the ratings can later be compared with the user's answers.\n"
    "Add one line to {item}, just before its recommendation, that opens with `#case_against` and your rating of "
    "its strongest case against, none, weak, medium, strong or very strong, as in "
    "`#case_against weak: the fix costs an hour of fast reads.` or `#case_against none.`; the rating is yours, so "
    "the user need not see the item again for it.\n"
    "Then run `python3 {program} check{flags}` again.\n"
    "From now on, write the `#case_against` line into each item before you show it.")
CASE_AGAINST_UNRATED = (
    "nothing written: the `#case_against` line of {item} in {document}, `{line}`, does not open with a rating, "
    "so no rating can be recorded beside the answer.\n"
    "Change that line so that `#case_against` is followed by one of none, weak, medium, strong or very strong, "
    "as in `#case_against weak: the fix costs an hour of fast reads.`, then run `python3 {program} check{flags}` "
    "again.")
NOT_ASKED_REFUSED = (
    "nothing written: {item} cannot be settled without asking the user as kind {kind}, because:\n{problems}\n"
    "If the item does not fit kind {kind}, or the case against is more than cost, present {item} to the user as "
    "usual, then run check with the flag for his answer, as `--help` lists it.\n"
    "If the item fits and only its evidence lines are missing or wrong, fix them in {document} and run "
    "`python3 {program} check --not-asked {kind}` again.")
NOT_ASKED_RATING_PROBLEM = ("- its `#case_against` line rates the case against {rating}; only an item rated none, "
                            "or weak with a case against that names only cost, settles without the user.")
NOT_ASKED_NO_LINE_PROBLEM = "- it has no `{marker}` line; {why}"
NOT_ASKED_MISSING_PATH_PROBLEM = "- `{marker}` names {path}, which is not in the checkout {top}."
NOT_ASKED_NEW_FILE_PROBLEM = ("- `{marker}` names {path}, which is not in the checkout {top}; a code fix that "
                              "settles without the user adds no file but a test.")
NOT_ASKED_NOT_A_TEST_PROBLEM = "- `{marker}` names {path}, which is not a test file in the checkout {top}."
NOT_ASKED_NO_NEW_TEXT_PROBLEM = "- it has no `#new` line holding the changed text."
NOT_ASKED_STILL_USED_PROBLEM = ("- `{word}`, named on its `{marker}` line, is still named in {files}, which "
                                "its `{touches}` line does not list.")
NOT_ASKED_NOT_MARKDOWN_PROBLEM = ("- it has no `{marker}` line, and `{touches}` names {paths}, which are not "
                                  "Markdown standing instructions; name each thing removed on a `{marker}` line.")
NOT_ASKED_RENAME_SHAPE_PROBLEM = "- its `{marker}` line `{value}` does not give the old name, then the new name."
NOT_ASKED_NOT_IN_GLOSSARY_PROBLEM = "- the new name `{new}` is in no glossary file ({pattern}) in the checkout."
NOT_ASKED_WHY = {
    TOUCHES: "list on it every file the change edits or deletes, separated by spaces.",
    TEST: "name on it the test that fails before the fix and passes after it.",
    SOURCE: "cite on it the ruling, the merged code or the command that shows the fact.",
    RENAME: "give on it the old name, then the new name.",
}
NOT_ASKED_JUDGEMENT_LINES = (
    "{item} is recorded as settled without asking the user, kind {kind}; the program checked only what code can.",
    "Before you run close, ask the advisor whether a later ruling or another open item overtakes {item}, and judge "
    "what the program could not, such as whether the case against names only cost and whether a fix matches its "
    "design.",
    "If the advisor objects, the advisor call fails, or your judgement is against settling, do not run close: "
    "present {item} to the user and run check with the flag for his answer, as `--help` lists it; that writes a new "
    "answer line, and close records only the last one, so this line is then set aside.",
)
GIT_GREP_FAILED = ("`git grep` failed with exit {code} in {top} while checking {item}'s evidence: {error}\n"
                   "Run `python3 {program} check --not-asked {kind}` again once; if it fails the same way, "
                   "present {item} to the user and run check with the flag for his answer, as `--help` lists it.")


class Failure(Exception):
    """A step that cannot go on; its argument is the line to print."""


class FastReadFailed(Exception):
    """A fast read failed; its argument is the FAILED line, printed as it is."""


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_walk_finder():
    return load_module("walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common",
                       WALK_FINDER_FILE)


def reachable_log_store_records(record_shipper=None, ned_box_home=None, mac_mount=None):
    """Return (the log-store's cold-read-records directory as this machine reaches it, or None, and the paths
    tried): the path ned-box names it by, then the same path under the Mac's mount of ned-box's home."""
    if record_shipper is None:
        record_shipper = load_module("cold_read_record_ship", RECORD_SHIPPER_FILE)
        constants = load_module("ned_box_home_directory_and_its_mac_mount_point_path_constants_common",
                                PATH_CONSTANTS_FILE)
        ned_box_home, mac_mount = constants.NED_BOX_HOME, constants.MAC_MOUNT_OF_NED_BOX_HOME
    _, path = record_shipper.split_destination(record_shipper.LOG_STORE_RECORDS_DESTINATION)
    candidates = [Path(str(path))]
    if str(path).startswith(ned_box_home + "/"):
        candidates.append(Path(mac_mount + str(path)[len(ned_box_home):]))
    return next((candidate for candidate in candidates if candidate.is_dir()), None), candidates


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


def item_lines(walk_finder, minutes, value, numbers, total, parser):
    """Return (walk-document path, the lines of the items numbered, outside fenced code), finding the items
    as close does, so check refuses a walk-document close would refuse."""
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    try:
        _, spans = walk_finder.waiting_item_units(document, value, numbers, total, parser)
    except walk_finder.UnusableRange as problem:
        raise Failure(f"the last `#next_to_present` line in {minutes}, `{value}`: {problem}")
    text = document.read_text(encoding="utf-8")
    tokens = parser.parse(text)
    lines, openings = walk_finder.prose_lines(text, parser, tokens), walk_finder.item_opening_lines(text, parser, tokens)
    kept = []
    for unit_numbers, unit_total, _, first, end in spans:
        if len(numbers) == 1 and len(unit_numbers) > 1:
            first, end = walk_finder.approval_walk_item_line_range_within_heading_shared_by_several_items(
                openings, first, end, numbers[0], unit_numbers, unit_total)
        kept += lines[first:end]
    return document, kept


def proposed_texts(lines, marks):
    """Return (mark, text) for each line marked with one of marks, in the lines' order."""
    texts = []
    for line in lines:
        match = NEW_LINE.match(line)
        if not match or match[1] not in marks:
            continue
        text = match[2].strip()
        for opening, closing in QUOTE_PAIRS:
            if len(text) >= 2 and text.startswith(opening) and text.endswith(closing):
                text = text[1:-1].strip()
                break
        if text:
            texts.append((match[1], text))
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
    """Fast-read the text from a scratch file; return (the report's directory, the lines the fast read printed
    on stderr about an unshipped record or a changed target), or raise FastReadFailed."""
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
    notes = [line.strip() for line in result.stderr.split("\n")
             if any(marker in line for marker in FAST_READ_NOTE_MARKERS)]
    return Path(lines[-1]).parent, notes


def excerpt(text):
    return text if len(text) <= 60 else text[:57].rstrip() + "..."


def file_name_part(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def append_to_minutes(minutes, lines):
    existing = minutes.read_text(encoding="utf-8")
    separator = "" if existing.endswith("\n") else "\n"
    with open(minutes, "a", encoding="utf-8") as file:
        file.write(separator + "\n".join(lines) + "\n")


def part_answer(value):
    """Return (part number, A, AO or D) from a --part-answer value such as `2=ao`."""
    match = PART_ARGUMENT.match(value)
    if not match:
        raise argparse.ArgumentTypeError(PART_ARGUMENT_PROBLEM.format(value=value))
    return int(match[1]), match[2].upper()


def answered_word(arguments):
    """The answer as the walk-minutes write it: approved, disapproved, approved option N, or each part's word,
    as in `part 1 approved #approved_obvious, part 2 disapproved`."""
    if arguments.part_answer:
        return ", ".join(f"part {number} {PART_WORDS[letter]}" for number, letter in sorted(arguments.part_answer))
    if arguments.disapproved:
        return DISAPPROVED
    if arguments.deferred:
        return DEFERRED
    if arguments.option is not None:
        return f"{APPROVED} option {arguments.option}"
    if arguments.not_asked is not None:
        return f"not asked, kind {arguments.not_asked}"
    return APPROVED


def marks_the_answer_adds(arguments):
    """The marks of the texts the answer adds: `#new_if_d` for D, `#new` for any other answer, and for
    answers to parts, the marks of the parts' answers."""
    if arguments.part_answer:
        letters = {letter for _, letter in arguments.part_answer}
        return {mark for mark, adds in ((NEW_MARK, letters != {"D"}), (NEW_IF_D_MARK, "D" in letters)) if adds}
    return {NEW_IF_D_MARK} if arguments.disapproved else {NEW_MARK}


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
    if arguments.not_asked is not None:
        flags += f" --not-asked {arguments.not_asked}"
    for number, letter in arguments.part_answer or []:
        flags += f" --part-answer {number}={letter}"
    return flags


def case_against_rating(lines, item, document, arguments):
    """Return the rating on the item's first `#case_against` line, as in `very strong`, or None when the item
    has none and the answer, O2 or O3, does not need one; raise Failure when an answer that needs one finds
    none, or a line that opens with no rating."""
    for line in lines:
        match = CASE_AGAINST_LINE.match(line)
        if not match:
            continue
        rating = CASE_AGAINST_RATING.match(match[1])
        if rating is None:
            raise Failure(CASE_AGAINST_UNRATED.format(item=item, document=document, line=line.strip(),
                                                      program=Path(__file__).resolve(),
                                                      flags=check_flags(arguments)))
        return rating[1].lower()
    if arguments.option is not None:
        return None
    raise Failure(CASE_AGAINST_MISSING.format(item=item, document=document, program=Path(__file__).resolve(),
                                              flags=check_flags(arguments)))


def evidence(lines):
    """Return {marker: [the values of each of the item's lines opening with that `#not_asked_` marker]}."""
    found = collections.defaultdict(list)
    for line in lines:
        match = EVIDENCE_LINE.match(line)
        if match:
            found[match[1]].append(match[2].strip())
    return found


def words(values):
    """The paths or names on evidence lines, without code marks or separating commas."""
    return [word.strip("`,;") for value in values for word in value.split() if word.strip("`,;")]


def files_naming(top, word, item, kind, pathspec=None):
    """Return the checkout files, tracked or untracked, outside the walk directory, that hold word as a word."""
    command = ["git", "-C", str(top), "grep", "--untracked", "-l", "-w", "-F", "-e", word]
    if pathspec:
        command += ["--", pathspec]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode not in (0, 1):
        raise Failure(GIT_GREP_FAILED.format(code=result.returncode, top=top, item=item, kind=kind,
                                             error=result.stderr.strip(), program=Path(__file__).resolve()))
    return {path for path in result.stdout.split("\n") if path and not path.startswith("docs/walk/")}


def not_asked_problems(kind, rating, lines, top, item):
    """Return the lines saying why the item cannot be settled as the kind given, from what code can check."""
    problems = []
    if rating not in NOT_ASKED_RATINGS:
        problems.append(NOT_ASKED_RATING_PROBLEM.format(rating=rating))
    found = evidence(lines)
    needed = {1: (TOUCHES, SOURCE), 2: (TOUCHES, TEST), 3: (TOUCHES,), 4: (TOUCHES, RENAME), 5: (SOURCE,)}[kind]
    for marker in needed:
        if not words(found[marker]):
            problems.append(NOT_ASKED_NO_LINE_PROBLEM.format(marker=marker, why=NOT_ASKED_WHY[marker]))
    touched = words(found[TOUCHES])
    if kind == 1 and not proposed_texts(lines, {NEW_MARK}):
        problems.append(NOT_ASKED_NO_NEW_TEXT_PROBLEM)
    tests = words(found[TEST])
    for path in touched:
        if not (top / path).exists():
            # A code fix may add the test that shows it; any other new file is an addition the user sees.
            if kind == 2 and path in tests:
                continue
            problem = NOT_ASKED_NEW_FILE_PROBLEM if kind == 2 else NOT_ASKED_MISSING_PATH_PROBLEM
            problems.append(problem.format(marker=TOUCHES, path=path, top=top))
    if kind == 2:
        for path in tests:
            if "test" not in Path(path).name or not ((top / path).is_file() or path in touched):
                problems.append(NOT_ASKED_NOT_A_TEST_PROBLEM.format(marker=TEST, path=path, top=top))
    if kind == 3:
        unused = words(found[UNUSED])
        for word in unused:
            others = sorted(files_naming(top, word, item, kind) - set(touched))
            if others:
                problems.append(NOT_ASKED_STILL_USED_PROBLEM.format(word=word, marker=UNUSED, files=", ".join(others),
                                                                   touches=TOUCHES))
        not_markdown = [path for path in touched if not path.endswith(".md")]
        if not unused and not_markdown:
            problems.append(NOT_ASKED_NOT_MARKDOWN_PROBLEM.format(marker=UNUSED, touches=TOUCHES,
                                                                  paths=", ".join(not_markdown)))
    if kind == 4:
        for value in found[RENAME]:
            names = words([value])
            if len(names) != 2:
                problems.append(NOT_ASKED_RENAME_SHAPE_PROBLEM.format(marker=RENAME, value=value))
                continue
            old, new = names
            if not files_naming(top, new, item, kind, GLOSSARY_FILES):
                problems.append(NOT_ASKED_NOT_IN_GLOSSARY_PROBLEM.format(new=new, pattern=GLOSSARY_FILES))
            others = sorted(files_naming(top, old, item, kind) - set(touched))
            if others:
                problems.append(NOT_ASKED_STILL_USED_PROBLEM.format(word=old, marker=RENAME, files=", ".join(others),
                                                                   touches=TOUCHES))
    return problems


def check(arguments):
    part_numbers = [number for number, _ in arguments.part_answer or []]
    repeated = sorted({number for number in part_numbers if part_numbers.count(number) > 1})
    if repeated:
        raise Failure(PART_REPEATED.format(parts=", ".join(f"part {number}" for number in repeated)))
    walk_finder = load_walk_finder()
    top, minutes, value, parser = the_open_walk(walk_finder, arguments.cwd)
    item, numbers, total = waiting_items(walk_finder, value, minutes)
    if numbers[1:]:
        raise Failure(CHECK_SEVERAL_WAITING.format(minutes=minutes, item=item, one_item_line=NEXT_MARKER_LINE.format(
            value=f"item <number>{f' of {total}' if total else ''}")))
    document, lines = item_lines(walk_finder, minutes, value, numbers, total, parser)
    rating = case_against_rating(lines, item, document, arguments)
    rated = CASE_AGAINST_HASHTAG.format(rating=rating.replace(" ", "_")) if rating else ""
    if arguments.deferred:
        now = datetime.datetime.now().astimezone()
        append_to_minutes(minutes, [CHECK_DEFERRED_MINUTES.format(item=item, rating=rated,
                                                                  date_and_time=f"{now:%Y-%m-%d %H:%M}")])
        print(CHECK_CLOSE_LINE.format(program=Path(__file__).resolve(), top=shlex.quote(str(top))))
        return 0
    if arguments.not_asked is not None:
        problems = not_asked_problems(arguments.not_asked, rating, lines, top, item)
        if problems:
            raise Failure(NOT_ASKED_REFUSED.format(item=item, kind=arguments.not_asked, problems="\n".join(problems),
                                                   document=document, program=Path(__file__).resolve()))
    texts = proposed_texts(lines, marks_the_answer_adds(arguments))
    log_store_records, tried = (None, []) if arguments.cold_read_records and arguments.counts_log \
        else reachable_log_store_records()
    record_directories = arguments.cold_read_records or (
        [top / RECORDS_DIRECTORY_NAME] + ([log_store_records] if log_store_records else []))
    walk_name = minutes.name[:-len(walk_finder.MINUTES_SUFFIX)]
    statuses, already_done, had_to_be_run, problems = [], 0, 0, []
    counted = collections.Counter()
    for mark, text in texts:
        counted[mark] += 1
        number = counted[mark]
        record = fast_read_record_holding(text, record_directories)
        if record is not None:
            already_done += 1
            statuses.append(STATUS_ALREADY_DONE.format(mark=mark, number=number, excerpt=excerpt(text),
                                                       record=record))
            continue
        name = f"{walk_name}-{file_name_part(item)}-{file_name_part(mark)}-{number}"
        record, notes = run_fast_read(text, name, arguments.fast_read_program)
        had_to_be_run += 1
        statuses.append(STATUS_HAD_TO_BE_RUN.format(mark=mark, number=number, excerpt=excerpt(text), record=record)
                        + "".join(STATUS_FAST_READ_NOTE.format(note=note) for note in notes))
        for note in notes:
            if note.startswith(FAST_READ_NOTE_MARKERS[0]):
                problems += [line.format(mark=mark, number=number, note=note, record=record,
                                         shipper=RECORD_SHIPPER_FILE)
                             for line in RECORDS_NOT_SHIPPED]
    if not texts:
        statuses.append(NO_PROPOSED_TEXT)
    now = datetime.datetime.now().astimezone()
    answer_minutes = CHECK_NOT_ASKED_MINUTES if arguments.not_asked is not None else CHECK_MINUTES
    append_to_minutes(minutes, [answer_minutes.format(item=item, answered=answered_word(arguments),
                                                      hashtag=answer_hashtag(arguments), rating=rated,
                                                      date_and_time=f"{now:%Y-%m-%d %H:%M}")]
                      + [STATUS_LINE_PREFIX + status for status in statuses])
    output = list(statuses)
    if had_to_be_run:
        output += [line.format(document=document, item=item) for line in CHECK_JUDGEMENT_LINES]
    if arguments.not_asked is not None:
        output += [line.format(item=item, kind=arguments.not_asked) for line in NOT_ASKED_JUDGEMENT_LINES]
    output.append(CHECK_CLOSE_LINE.format(program=Path(__file__).resolve(), top=shlex.quote(str(top))))
    log = arguments.counts_log or (log_store_records.parent / COUNTS_LOG_FILE_NAME if log_store_records else None)
    try:
        if log is None:
            raise OSError(LOG_STORE_UNREACHABLE.format(paths=" or ".join(str(path) for path in tried)))
        with open(log, "a", encoding="utf-8") as file:
            file.write("\t".join([now.isoformat(timespec="seconds"), walk_name, item,
                                  f"texts={len(texts)}", f"already_done={already_done}",
                                  f"had_to_be_run={had_to_be_run}"]) + "\n")
    except OSError as error:
        problems += [line.format(log=log or "the log-store", error=error) for line in COUNTS_NOT_LOGGED]
    print("\n".join(output + problems))
    return 2 if problems else 0


def last_answer(walk_finder, minutes, parser):
    """Return (item, answered, status lines) of the walk-minutes' last answer line, or raise Failure when
    there is none or a close already recorded it."""
    lines = walk_finder.prose_lines(minutes.read_text(encoding="utf-8"), parser)
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
    text = document.read_text(encoding="utf-8") if document.is_file() else ""
    units = walk_finder.item_unit_spans(text, parser) if document.is_file() else None
    try:
        total, _ = walk_finder.waiting_item_units(document, value, numbers, total, parser, units)
    except walk_finder.UnusableRange as problem:
        raise Failure(f"the last `#next_to_present` line in {minutes}, `{value}`: {problem}")
    lines = text.split("\n")
    order, summary = [], None
    for unit_numbers, unit_total, _, first, _ in units:
        if unit_total != total:
            continue
        order += [number for number in unit_numbers if number not in order]
        if unit_numbers and SUMMARY_HEADING.search(lines[first]):
            summary = unit_numbers[0]
    return total, order, summary


def says_outcome(pattern, line):
    """Return whether the line holds a match of pattern that does not follow the, a or an."""
    return any(not MODIFIER_BEFORE.search(line[:match.start()]) for match in pattern.finditer(line))


def minutes_record(walk_finder, minutes_text, parser):
    """Return (the item numbers whose last line that records a decision or its absence decides them, a
    Counter of how many lines defer each item)."""
    decided, deferrals = set(), collections.Counter()
    for line in walk_finder.prose_lines(minutes_text, parser):
        if ANSWER_LINE.match(line):
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
        first_word = first[1].lower() if first else ""
        # An outcome tag or a leading "deferred" says what the line records; only an untagged line is read
        # by its keywords, since a hand-written open line may use "approved" in another sense, and even
        # then a keyword right after the, a or an, as in "the approved definition", is not read. An
        # awaiting-ruling tag undoes an earlier decision and beats a deciding tag on its own line; `<open>`
        # does neither, since real minutes use it after a decision for a side point left open.
        defers = first_word == DEFERRED
        if AWAITING_RULING in outcomes:
            decided.difference_update(items)
        elif outcomes & DECIDING_OUTCOMES:
            decided.update(items)
            defers = False
        elif not (outcomes & UNDECIDED_OUTCOMES or defers):
            if says_outcome(DECIDED, line):
                decided.update(items)
            else:
                defers = says_outcome(DEFERRED_WORD, line)
        if defers:
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
    item, answered, statuses = last_answer(walk_finder, minutes, parser)
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
        parts = PART_IN_ANSWER.findall(answered)
        if parts:
            recorded = CLOSE_PARTS_TOOK_EFFECT_MINUTES.format(item=item, parts=", ".join(
                f"part {number} {word} {OUTCOMES[word]}" for number, word in parts))
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
    answer.add_argument("--disapproved", action="store_true", help="check: the answer was D, disapprove; reads only the `#new_if_d` texts")
    answer.add_argument("--deferred", action="store_true", help="check: the answer was Z, defer")
    answer.add_argument("--option", type=int, choices=(2, 3),
                        help="check: the answer was O2 or O3, approving the item's \"Option N\" paragraph")
    answer.add_argument("--part-answer", type=part_answer, action="append", metavar="N=ANSWER",
                        help="check: part N of the item was answered ANSWER, A, AO or D; give it once for each part")
    answer.add_argument("--not-asked", type=int, choices=NOT_ASKED_KINDS, metavar="KIND",
                        help="check: the user is not asked; settle the item as kind KIND, 1 to 5, of the "
                             "walk-me-through skill's list of items that need no answer, if its evidence lines pass")
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
