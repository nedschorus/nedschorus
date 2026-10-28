#!/usr/bin/env python3
"""Cases for the program that carries out the user's answer that makes a
change in an open approval-walk: its check step, which fast-reads each text
the answer adds to the waiting item, `#new` or `#new_if_d`, that has not had a
fast read, and its close step.

Each case runs the program as a subprocess in a scratch checkout this suite
made. cold-read-fast-read.py is replaced by a stand-in this suite writes, so no
case calls a model. The exit code is asserted on every case.
"""

import contextlib
import importlib.util
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Before anything runs git: a GIT_DIR or similar variable inherited from the
# caller would otherwise send this suite's `git init` into another repository.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().parents[4] / "scripts"
    / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

PROGRAM = (Path(__file__).resolve().parents[1]
           / "walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py")
SUITE_ROOT = Path(tempfile.mkdtemp(prefix="answer-added-texts-fast-read-check-test-")).resolve()
WALK_NAME = "poem-page-2026-10-12"
FAILURE_PREFIX = "walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close "
failures = []

# Behaves as cold-read-fast-read.py does on the records route: writes a
# cold-read-record with fast-read.md and target/, prints the report's path.
STAND_IN = r'''
import os, sys
from pathlib import Path
target = Path(sys.argv[sys.argv.index("--target") + 1])
with open(os.environ["STAND_IN_CALLS"], "a") as calls:
    calls.write(target.read_text())
mode = os.environ.get("STAND_IN_MODE", "")
if mode == "failed":
    print("FAILED: the stand-in cold-read-cell failed twice")
    sys.exit(1)
if mode == "silent-exit":
    sys.exit(3)
record = Path(os.environ["STAND_IN_RECORDS"]) / (target.stem + "-2026-10-17")
(record / "target").mkdir(parents=True)
(record / "target" / target.name).write_text(target.read_text())
(record / "fast-read.md").write_text("findings\n")
print(record / "fast-read.md")
if mode == "path-then-exit":
    sys.exit(4)
if mode == "target-changed":
    sys.stderr.write("cold-read-fast-read: #cold_read_target_changed_during_run: the target changed while it was read.\n")
if mode == "record-not-shipped":
    sys.stderr.write("cold-read-fast-read: record: FAILED: ned-box could not be reached (ssh exit 255); "
                     "the record stays on disk.\n")
'''

WALK_DOCUMENT = """# A walk

## Item 3 of 9: the opening sentence

The opening sentence changes. It says now:

#old "The page lists poems."

and will say:

#new "The page lists one poem per job an agent does."

If the sentence stays, a note follows it:

#new_if_d "A note says why the sentence stays."

- #new “Each row names the mistake it prevents.”

```
#new "inside a fence, not a proposed text"
```

#case_against weak: the page grows by one line.

Recommendation: change the sentence.

## Item 4 of 9: no proposal here

#case_against none.

Nothing is proposed. Recommendation: leave it.

## Items 6 and 7 of 9: two small corrections

Item 6 of 9 fixes a path.

#new "The path is docs/walk/."

#case_against none.

Item 7 of 9 drops a sentence.

#new "Item seven's text."

#case_against none.

## Item 5 of 9: a new item a finding raised

#new "A changed decision."

**#case_against very strong:** it undoes a ruling.
"""


# Every answer but O2 and O3 needs the item's `#case_against` line. Cases about something else use documents
# written without one; rated() gives each item opening in such a document a `#case_against none.` line.
ITEM_OPENING = re.compile(r"^(?:#+\s*)?\**Items? [\d.]+(?: (?:and|to) [\d.]+)* of \d+\b.*$", re.M)


def rated(document):
    if "#case_against" in document:
        return document
    return ITEM_OPENING.sub(lambda opening: opening[0] + "\n\n#case_against none.\n", document)


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


class Case:
    """One case's own checkout, walk files, record directories and stand-in."""

    counter = 0

    def __init__(self, next_to_present="item 3 of 9", document=WALK_DOCUMENT):
        Case.counter += 1
        self.root = SUITE_ROOT / f"case-{Case.counter}"
        self.checkout = self.root / "checkout"
        self.checkout.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.checkout)], check=True)
        walk = self.checkout / "docs" / "walk"
        walk.mkdir(parents=True)
        (walk / f"{WALK_NAME}.md").write_text(rated(document))
        self.minutes = walk / f"{WALK_NAME}-minutes.md"
        self.minutes.write_text(f"# Minutes\n\nItem 2 of 9: the user: y. <accepted>\n#next_to_present {next_to_present}\n")
        self.records = self.root / "log-store-cold-read-records"
        self.records.mkdir()
        self.counts_log = self.root / "counts.tsv"
        self.calls = self.root / "stand-in-calls.txt"
        self.calls.write_text("")
        self.stand_in = self.root / "cold-read-fast-read-stand-in.py"
        self.stand_in.write_text(STAND_IN)

    def record_holding(self, text):
        record = self.records / "earlier-read-2026-10-15"
        (record / "target" / "docs" / "walk").mkdir(parents=True)
        (record / "target" / "docs" / "walk" / "item.md").write_text(f"Item 3 of 9\n\n#new \"{text}\"\n")
        (record / "fast-read.md").write_text("findings\n")
        return record

    def run(self, step, *flags, mode="", counts_log=None):
        environment = dict(os.environ, STAND_IN_MODE=mode, STAND_IN_CALLS=str(self.calls),
                           STAND_IN_RECORDS=str(self.records))
        return subprocess.run(
            [sys.executable, str(PROGRAM), step, *flags, "--cwd", str(self.checkout),
             "--cold-read-records", str(self.records), "--fast-read-program", str(self.stand_in),
             "--counts-log", str(counts_log or self.counts_log)],
            capture_output=True, text=True, env=environment, cwd=self.checkout)


def described(result):
    return f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}"


def test_missing_fast_reads_are_run_and_reported():
    case = Case()
    result = case.run("check")
    lines = result.stdout.rstrip("\n").split("\n")
    check("check runs a fast read for each #new text with none, and says so",
          result.returncode == 0
          and lines[0].startswith('`#new` text 1, "The page lists one poem per job an agent does.": '
                                  "fast read had to be run (")
          and lines[1].startswith('`#new` text 2, "Each row names the mistake it prevents.": '
                                  "fast read had to be run (")
          and 'Read the fast-read report of each text above whose status line says "fast read had to be run".' in lines
          and f"close --cwd {shlex.quote(str(case.checkout.resolve()))}` and do what it prints." in lines[-1],
          described(result))
    check("a #new line inside a fence or in another item is not a proposed text",
          case.calls.read_text() == ("The page lists one poem per job an agent does.\n"
                                     "Each row names the mistake it prevents.\n"),
          repr(case.calls.read_text()))
    minutes = case.minutes.read_text()
    check("check records the answer as approved, and the status lines, in the minutes",
          re.search(r"\nitem 3 of 9: the user answered approved #case_against_weak \(\d{4}-\d\d-\d\d \d\d:\d\d\), which makes "
                    r"its change\. Fast reads:\n", minutes) is not None
          and minutes.count("\n- `#new` text ") == 2, minutes)
    log = case.counts_log.read_text().split("\t")
    check("check appends the counts", log[1:] == [WALK_NAME, "item 3 of 9", "texts=2",
                                                   "already_done=0", "had_to_be_run=2\n"], repr(log))
    again = case.run("check")
    check("a text the earlier check fast-read is already done the next time",
          again.returncode == 0 and again.stdout.count("fast read already done") == 2
          and "Read each fast-read report" not in again.stdout, described(again))


NEW_TEXTS = "The page lists one poem per job an agent does.\nEach row names the mistake it prevents.\n"
NEW_IF_D_TEXT = "A note says why the sentence stays.\n"


def test_each_answer_fast_reads_only_the_texts_it_adds():
    for flags, read in ((("--obvious",), NEW_TEXTS), (("--after-advisor",), NEW_TEXTS),
                        (("--option", "2"), NEW_TEXTS), (("--option", "3"), NEW_TEXTS),
                        (("--disapproved",), NEW_IF_D_TEXT),
                        (("--part-answer", "1=AO"), NEW_TEXTS),
                        (("--part-answer", "1=D", "--part-answer", "2=D"), NEW_IF_D_TEXT),
                        (("--part-answer", "1=A", "--part-answer", "2=D"),
                         "The page lists one poem per job an agent does.\n" + NEW_IF_D_TEXT
                         + "Each row names the mistake it prevents.\n")):
        case = Case()
        result = case.run("check", *flags)
        check(f"check {' '.join(flags)} fast-reads only the texts that answer adds",
              result.returncode == 0 and case.calls.read_text() == read,
              described(result) + repr(case.calls.read_text()))
    case = Case()
    result = case.run("check", "--disapproved")
    lines = result.stdout.split("\n")
    check("on D the status line names the `#new_if_d` mark and its scratch file, and the counts hold the one text",
          lines[0].startswith('`#new_if_d` text 1, "A note says why the sentence stays.": fast read had to be run (')
          and f"{WALK_NAME}-item-3-of-9-new-if-d-1-2026-10-17)." in lines[0]
          and "\n- `#new_if_d` text 1, " in case.minutes.read_text()
          and "texts=1\talready_done=0\thad_to_be_run=1" in case.counts_log.read_text(), described(result))
    case = Case()
    result = case.run("check", "--part-answer", "1=A", "--part-answer", "2=D")
    check("each mark's texts are numbered on their own, in the walk-document's order",
          [line.split(",")[0] for line in result.stdout.split("\n")[:3]]
          == ["`#new` text 1", "`#new_if_d` text 1", "`#new` text 2"], described(result))
    case = Case(next_to_present="item 5 of 9")
    result = case.run("check", "--disapproved")
    check("D on an item with no `#new_if_d` line runs no fast read",
          result.returncode == 0 and result.stdout.split("\n")[0] == "no proposed text marked"
          and case.calls.read_text() == "", described(result))
    case = Case()
    result = case.run("check", "--disapproved", mode="record-not-shipped")
    check("an unshipped record of a `#new_if_d` text names that mark",
          result.returncode == 2 and "the fast read of `#new_if_d` text 1 did not ship its record" in result.stdout,
          described(result))


def test_a_fast_read_already_done_is_not_run_again():
    case = Case()
    record = case.record_holding("The page lists one poem\n per job an agent does.")
    result = case.run("check")
    check("a record whose target holds the text, whitespace aside, counts as done",
          result.returncode == 0
          and f'"The page lists one poem per job an agent does.": fast read already done ({record}).'
          in result.stdout
          and case.calls.read_text() == "Each row names the mistake it prevents.\n",
          described(result))


def test_no_proposed_text():
    case = Case(next_to_present="item 4 of 9")
    result = case.run("check")
    check("an item with no #new line says so and needs no judgement",
          result.returncode == 0 and result.stdout.split("\n")[0] == "no proposed text marked"
          and "Read each" not in result.stdout and case.calls.read_text() == "",
          described(result))
    check("the counts of an item with no #new line are logged as zero",
          "texts=0\talready_done=0\thad_to_be_run=0" in case.counts_log.read_text(),
          case.counts_log.read_text())


def test_a_failed_fast_read_stops_the_check():
    case = Case()
    before = case.minutes.read_text()
    result = case.run("check", "--obvious", mode="failed")
    check("a FAILED fast read is printed as it is, with exit 1",
          result.returncode == 1
          and result.stdout.split("\n")[0] == "FAILED: the stand-in cold-read-cell failed twice"
          and "The item stays waiting" in result.stdout
          and "close.py check --obvious` again" in result.stdout, described(result))
    check("after a FAILED fast read the minutes do not record the answer", case.minutes.read_text() == before,
          case.minutes.read_text())
    for flags in (("--after-advisor",), ("--disapproved",), ("--option", "2"), ("--part-answer", "1=A", "--part-answer", "2=D")):
        case = Case()
        result = case.run("check", *flags, mode="failed")
        check(f"after a FAILED fast read, the rerun command keeps {' '.join(flags)}",
              result.returncode == 1 and f"close.py check {' '.join(flags)}` again" in result.stdout,
              described(result))


def test_a_fast_read_that_exits_nonzero_without_a_line_is_a_failure():
    case = Case()
    result = case.run("check", mode="silent-exit")
    check("a fast read that exits nonzero and prints nothing is reported as FAILED",
          result.returncode == 1 and result.stdout.startswith("FAILED: ") and "exited 3" in result.stdout,
          described(result))


def test_a_fast_read_that_names_a_report_but_exits_nonzero_is_a_failure():
    case = Case()
    before = case.minutes.read_text()
    result = case.run("check", mode="path-then-exit")
    check("a fast read that names a report but exits nonzero is reported as FAILED, and the minutes stay as they were",
          result.returncode == 1 and result.stdout.startswith("FAILED: ") and "exited 4" in result.stdout
          and case.minutes.read_text() == before, described(result))


def test_counts_that_cannot_be_logged_are_reported():
    case = Case(next_to_present="item 4 of 9")
    result = case.run("check", counts_log=case.root / "no-such-directory" / "counts.tsv")
    check("a counts log that cannot be written is printed, saying the minutes record the answer, with exit 2",
          result.returncode == 2
          and "The minutes record the answer, but the fast-read counts were not logged to " in result.stdout
          and result.stdout.startswith("no proposed text marked")
          and "item 4 of 9: the user answered approved #case_against_none (" in case.minutes.read_text(), described(result))


def test_a_fast_read_whose_record_was_not_shipped_is_reported():
    case = Case()
    result = case.run("check", mode="record-not-shipped")
    note = ("cold-read-fast-read: record: FAILED: ned-box could not be reached (ssh exit 255); the record stays "
            "on disk.")
    check("a fast read that exits 0 but did not ship its record has its line in the status line, in the minutes, "
          "and in what to do, with exit 2",
          result.returncode == 2
          and result.stdout.split("\n")[0].endswith(f"The fast read also said: {note}")
          and "The minutes record the answer, but the fast read of `#new` text 1 did not ship its record: "
              f"{note}" in result.stdout
          and "cold-read-record-ship.py " in result.stdout
          and case.minutes.read_text().count(f"The fast read also said: {note}") == 2, described(result))


def load_program():
    spec = importlib.util.spec_from_file_location("check_and_close", PROGRAM)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_log_store_is_found_on_ned_box_or_through_the_macs_mount():
    program = load_program()
    root = SUITE_ROOT / "log-store-lookup"

    class Shipper:
        LOG_STORE_RECORDS_DESTINATION = f"nedlern@ned-box:{root}/box-home/nedschorus-logs/cold-read-records"

        @staticmethod
        def split_destination(destination):
            host, _, path = destination.partition(":")
            return host, Path(path)

    on_box, on_mac = root / "box-home" / "nedschorus-logs" / "cold-read-records", \
        root / "mac-mount" / "nedschorus-logs" / "cold-read-records"
    found, tried = program.reachable_log_store_records(Shipper, str(root / "box-home"), str(root / "mac-mount"))
    check("with neither path a directory, the log-store is not found, and both paths are named as tried",
          found is None and tried == [on_box, on_mac], repr((found, tried)))
    on_mac.mkdir(parents=True)
    found, _ = program.reachable_log_store_records(Shipper, str(root / "box-home"), str(root / "mac-mount"))
    check("on the Mac, the log-store is found through the mount of ned-box's home", found == on_mac, repr(found))
    on_box.mkdir(parents=True)
    found, _ = program.reachable_log_store_records(Shipper, str(root / "box-home"), str(root / "mac-mount"))
    check("on ned-box, the log-store is found at its own path", found == on_box, repr(found))
    found, tried = program.reachable_log_store_records()
    check("by default the path comes from cold-read-record-ship.py's LOG_STORE_RECORDS_DESTINATION",
          tried[0] == Path("/home/nedlern/nedschorus-logs/cold-read-records")
          and tried[1] == Path("/Volumes/nedhome/nedschorus-logs/cold-read-records"), repr(tried))


def test_a_capitalised_marker_is_read_and_closed():
    case = Case(next_to_present="Item 4 of 9")
    case.run("check")
    closed = case.run("close")
    check("a `#next_to_present Item 4 of 9` line, capital I, is checked and closed",
          closed.returncode == 0 and "Item 4 of 9: approved; every text the change adds" in case.minutes.read_text(),
          described(closed) + case.minutes.read_text())


TOOK_EFFECT_NEXT = [
    "If the change needs nothing more from the user, such as a text he has not yet seen, start it as the "
    "walk-me-through skill's sentence on ready work says; if it edits a file that work you dispatched "
    "earlier is still editing, start it when that earlier work finishes.",
    "Then present item 6 of 9, which the minutes' `#next_to_present` line now names."]


def test_close_records_that_the_answer_took_effect():
    case = Case(next_to_present="item 4 of 9")
    case.run("check")
    result = case.run("close")
    check("close records an approval that took effect, repeats the status lines, and says to start ready work",
          result.returncode == 0
          and result.stdout.rstrip("\n").split("\n") == [
              "item 4 of 9's answer is recorded in the minutes, and its change may now be made.",
              "Your next message must include these lines, as they are:",
              "no proposed text marked"] + TOOK_EFFECT_NEXT
          and case.minutes.read_text().rstrip().endswith(
              "item 4 of 9: approved; every text the change adds has had a fast read. <accepted>\n"
              "#next_to_present item 6 of 9"),
          described(result))


def test_each_answer_is_recorded_as_its_word():
    for flags, first, last in (
            (("--obvious",), "the user answered approved #approved_obvious #case_against_none (",
             "item 4 of 9: approved; every text the change adds has had a fast read. <accepted>"),
            (("--after-advisor",), "the user answered approved #approved_after_advisor #case_against_none (",
             "item 4 of 9: approved; every text the change adds has had a fast read. <accepted>"),
            (("--disapproved",), "the user answered disapproved #case_against_none (",
             "item 4 of 9: disapproved; every text the change adds has had a fast read. <rejected>"),
            (("--option", "2"), "the user answered approved option 2 #case_against_none (",
             "item 4 of 9: approved option 2; every text the change adds has had a fast read. <accepted>"),
            (("--option", "3"), "the user answered approved option 3 #case_against_none (",
             "item 4 of 9: approved option 3; every text the change adds has had a fast read. <accepted>")):
        case = Case(next_to_present="item 4 of 9")
        checked = case.run("check", *flags)
        closed = case.run("close")
        minutes = case.minutes.read_text()
        check(f"check {' '.join(flags)} writes \"{first}\" and close writes the matching outcome",
              checked.returncode == 0 and closed.returncode == 0 and f"\nitem 4 of 9: {first}" in minutes
              and minutes.rstrip().endswith(last + "\n#next_to_present item 6 of 9"), described(checked) + described(closed) + minutes)


def test_answer_flags_exclude_each_other_and_option_takes_2_or_3():
    for flags in (("--obvious", "--disapproved"), ("--disapproved", "--option", "2"), ("--option", "4"),
                  ("--after-advisor", "--obvious"), ("--after-advisor", "--disapproved"),
                  ("--after-advisor", "--deferred"), ("--after-advisor", "--option", "2")):
        case = Case(next_to_present="item 4 of 9")
        result = case.run("check", *flags)
        check(f"check {' '.join(flags)} is refused as usage, writing nothing",
              result.returncode == 2 and "usage:" in result.stderr and "the user answered" not in case.minutes.read_text(),
              described(result))


def test_a_waiting_item_under_a_heading_shared_with_another_reads_only_its_own_lines():
    case = Case(next_to_present="item 7 of 9")
    result = case.run("check")
    check("check reads only the waiting item's #new lines under a heading shared with another item",
          result.returncode == 0 and case.calls.read_text() == "Item seven's text.\n"
          and "\nitem 7 of 9: the user answered approved #case_against_none (" in case.minutes.read_text(), described(result))


def test_check_refuses_when_more_than_one_item_waits():
    for flags in ((), ("--disapproved",), ("--deferred",)):
        case = Case(next_to_present="items 6 and 7 of 9")
        before = case.minutes.read_text()
        result = case.run("check", *flags)
        check(f"check {' '.join(flags) or 'with no flag'} refuses on stderr, writing nothing and running no fast read, "
              "when more than one item waits",
              result.returncode == 1
              and result.stderr.startswith(FAILURE_PREFIX + "check: nothing written: ")
              and "names more than one item waiting, items 6 and 7 of 9," in result.stderr
              and ("add the line `#next_to_present item <number> of 9`, with that item's number, as the minutes' "
                   "last line, then run check") in result.stderr
              and case.minutes.read_text() == before and case.calls.read_text() == ""
              and not case.counts_log.exists(), described(result))


def test_item_under_a_shared_heading_with_no_line_of_its_own_reads_the_whole_unit():
    document = WALK_DOCUMENT + "\n## Items 8 and 9 of 9: two rows\n\n#new \"Row eight.\"\n\n#new \"Row nine.\"\n\n#case_against none.\n\nNo count per row.\n"
    case = Case(next_to_present="item 8 of 9", document=document)
    result = case.run("check")
    check("a waiting item on a shared heading whose items have no count line of their own reads every #new line of it",
          result.returncode == 0 and case.calls.read_text() == "Row eight.\nRow nine.\n", described(result))


def test_bold_openings_with_no_total_or_in_a_list_item_bound_an_item_under_a_shared_heading():
    for shape, six, seven in (("a top-level paragraph with no `of M`", "**Item 6: the path.**", "**Item 7: the sentence.**"),
                              ("a top-level list item", "- **Item 6, the path.**", "- **Item 7, the sentence.**")):
        document = WALK_DOCUMENT.replace("Item 6 of 9 fixes a path.", six).replace("Item 7 of 9 drops a sentence.", seven)
        case = Case(next_to_present="item 6 of 9", document=document)
        result = case.run("check")
        check(f"under a shared heading, an item opening with a bold count in {shape} ends the item before it, "
              "so check fast-reads only the waiting item's #new text",
              result.returncode == 0 and case.calls.read_text() == "The path is docs/walk/.\n", described(result))


def test_a_mention_of_the_next_item_inside_an_items_part_does_not_end_it_under_a_shared_heading():
    document = WALK_DOCUMENT.replace(
        "#new \"The path is docs/walk/.\"",
        "Item 7 depends on item 6.\n\n#new \"The path is docs/walk/.\"\n\n**Item 7** of 8 said the same.\n\n"
        "#new \"A second path.\"\n\n**Item 7.2** shows the rewrite.\n\n#new \"A third path.\"")
    case = Case(next_to_present="item 6 of 9", document=document)
    result = case.run("check")
    check("under a shared heading, a line that only mentions item 7 inside item 6's part does not end it, "
          "so check fast-reads every #new text of item 6",
          result.returncode == 0
          and case.calls.read_text() == "The path is docs/walk/.\nA second path.\nA third path.\n",
          described(result))


CODE_SHOWING_ANOTHER_ITEMS_COUNT = {
    "a backtick fence": "```\nItem 7 of 9: an example\n```\n",
    "a tilde fence": "~~~\nItem 7 of 9: an example\n~~~\n",
    "an indented code block": "    Item 7 of 9: an example\n",
    "a fence in a list item": "- for example:\n\n  ```\n  **Item 7 of 9**: an example\n  ```\n",
    "an HTML comment": "<!-- A drafter's note.\nItem 7 of 9 was split from this item.\n-->\n",
    "a quotation": "> Item 7 of 9: the user's earlier wording\n",
    "a list item": "Related:\n\n- Item 7 of 9, which follows\n",
    "a quoted heading": "> ## Item 7 of 9: quoted\n",
}


def test_a_count_line_inside_code_is_not_an_items_start():
    for shape, code in CODE_SHOWING_ANOTHER_ITEMS_COUNT.items():
        document = WALK_DOCUMENT.replace("Item 6 of 9 fixes a path.\n\n", f"Item 6 of 9 fixes a path.\n\n{code}\n")
        case = Case(next_to_present="item 6 of 9", document=document)
        result = case.run("check")
        check(f"a line opening with another item's count inside {shape} does not end the waiting item's lines, "
              "so its later #new text is fast-read",
              result.returncode == 0 and case.calls.read_text() == "The path is docs/walk/.\n", described(result))


def test_only_the_units_own_openings_of_its_total_bound_an_item_under_a_shared_heading():
    document = (WALK_DOCUMENT
                .replace("Nothing is proposed. Recommendation: leave it.\n",
                         "Nothing is proposed. Recommendation: leave it.\n\nItem 7 of 9 comes later.\n\n#new \"Item four's text.\"\n")
                .replace("Item 6 of 9 fixes a path.\n\n", "")
                .replace("Item 7 of 9 drops a sentence.\n\n", "Item 7 of 9 drops a sentence.\n\nItem 6 of 8 is another walk's.\n\n")
                .replace("#new \"A changed decision.\"\n", "#new \"A changed decision.\"\n\nItem 6 of 9 was split out.\n"))
    case = Case(next_to_present="item 7 of 9", document=document)
    result = case.run("check")
    check("an item under a shared heading starts at its own opening in the unit, not at one before the unit, and "
          "ends at the unit's end, not at an opening after it, nor at one of another total",
          result.returncode == 0 and case.calls.read_text() == "Item seven's text.\n", described(result))


def test_an_item_with_no_opening_of_its_own_reads_to_the_units_last_line():
    document = WALK_DOCUMENT.replace(
        "## Item 5 of 9: a new item a finding raised",
        "## Items 8 and 9 of 9: two rows\n\n#new \"Row eight.\"\n#new \"Row nine.\"\n#case_against none.\n## Item 5 of 9: a new item a finding raised")
    case = Case(next_to_present="item 9 of 9", document=document)
    result = case.run("check")
    check("an item under a shared heading with no opening of its own reads the unit up to its last line",
          result.returncode == 0 and case.calls.read_text() == "Row eight.\nRow nine.\n", described(result))


def test_an_html_block_that_is_not_a_comment_is_read():
    document = WALK_DOCUMENT.replace("Nothing is proposed. Recommendation: leave it.\n",
                                     "<div>\n#new \"Shown in a div.\"\n</div>\n\nRecommendation: leave it.\n")
    case = Case(next_to_present="item 4 of 9", document=document)
    result = case.run("check")
    check("a `#new` line in an HTML block that is not a comment shows on the page, so it is a proposed text",
          result.returncode == 0 and case.calls.read_text() == "Shown in a div.\n", described(result))


def test_lines_inside_code_in_the_minutes_record_nothing():
    case = summary_case(next_to_present="item 2 of 5",
                        recorded="Item 1 of 5: approved. <accepted>\n```\nItem 3 of 5: approved. <accepted>\n```\n")
    case.run("check")
    closed = case.run("close")
    check("an outcome tag inside a fence in the minutes decides nothing, so the item it names comes next",
          closed.returncode == 0 and marker(case) == "#next_to_present item 3 of 5",
          described(closed) + case.minutes.read_text())
    case = Case(next_to_present="item 4 of 9")
    case.run("check")
    with case.minutes.open("a") as minutes:
        minutes.write("```\nitem 5 of 9: the user answered disapproved (2026-10-23 10:00), which makes no change.\n```\n")
    closed = case.run("close")
    check("an answer line inside a fence in the minutes is not the last answer, so close records the real one",
          closed.returncode == 0 and closed.stdout.startswith("item 4 of 9's answer is recorded in the minutes")
          and marker(case) == "#next_to_present item 6 of 9", described(closed))


def test_a_marker_inside_code_in_the_minutes_is_not_the_last_marker():
    case = Case(next_to_present="item 4 of 9")
    with case.minutes.open("a") as minutes:
        minutes.write("```\n#next_to_present item 3 of 9\n```\n")
    result = case.run("check")
    check("a `#next_to_present` line inside a fence after the real one is not read, so check answers the real item",
          result.returncode == 0 and case.calls.read_text() == ""
          and "\nitem 4 of 9: the user answered approved #case_against_none (" in case.minutes.read_text(), described(result))


def test_a_deciding_tag_on_a_line_opening_deferred_records_no_deferral():
    program = load_program()
    walk_finder = program.load_walk_finder()
    parser = walk_finder.markdown_parser()
    decided, deferrals = program.minutes_record(
        walk_finder, "Item 2 of 5: deferred, then approved. <accepted>\n", parser)
    check("a line that opens with deferred but carries <accepted> decides its item and records no deferral",
          decided == {"2"} and not deferrals, repr((decided, deferrals)))


def test_lines_inside_an_html_comment_in_the_minutes_record_nothing():
    case = summary_case(next_to_present="item 2 of 5",
                        recorded="Item 1 of 5: approved. <accepted>\n<!-- A note, not presented:\n"
                                 "Item 3 of 5: approved in an earlier walk. <accepted>\n-->\n")
    case.run("check")
    closed = case.run("close")
    check("an outcome tag inside an HTML comment in the minutes decides nothing, so the item it names comes next",
          closed.returncode == 0 and marker(case) == "#next_to_present item 3 of 5",
          described(closed) + case.minutes.read_text())
    case = Case(next_to_present="item 4 of 9")
    with case.minutes.open("a") as minutes:
        minutes.write("<!-- an older marker:\n#next_to_present item 3 of 9\n-->\n")
    result = case.run("check")
    check("a `#next_to_present` line inside an HTML comment is not read, so check answers the real item",
          result.returncode == 0 and "\nitem 4 of 9: the user answered approved #case_against_none (" in case.minutes.read_text(),
          described(result))


def test_how_a_minutes_line_without_a_deciding_tag_is_read():
    program = load_program()
    walk_finder = program.load_walk_finder()
    parser = walk_finder.markdown_parser()
    for line, expected, case_name in (
            ("Item 2 of 5: the user deferred it until Friday.\n", (set(), {"2": 1}),
             "an untagged line with deferred later in it records a deferral"),
            ("Item 2 of 5: the approved wording waits. <open>\n", (set(), {}),
             "an `<open>` line holding a deciding word records no decision"),
            ("Item 2 of 5: the user approved it.\n", ({"2"}, {}),
             "an untagged line holding a deciding word records a decision"),
            ("Items 3 to 4 of 5: respelled; item 3 cites the approved definition.\n", (set(), {}),
             "an untagged line whose only deciding word follows `the` records no decision"),
            ("Item 2 of 5: an Accepted text and a rejected one, The approved one too.\n", (set(), {}),
             "deciding words after `an`, `a` and `the` record no decision, whatever their case"),
            ("Items 3 to 4 of 5: each approved.\n", ({"3", "4"}, {}),
             "a deciding word after `each`, standing as a pronoun, records a decision"),
            ("Item 2 of 5: this approved.\n", ({"2"}, {}),
             "a deciding word after `this`, standing as a pronoun, records a decision"),
            ("Item 2 of 5: the approved text stays, and the user approved it.\n", ({"2"}, {}),
             "an untagged line with one deciding word after `the` and one not records a decision"),
            ("Item 2 of 5: the change waits for the deferred migration.\n", (set(), {}),
             "an untagged line whose only `deferred` follows `the` records no deferral")):
        decided, deferrals = program.minutes_record(walk_finder, line, parser)
        check(case_name, (decided, dict(deferrals)) == expected, repr((decided, deferrals)))


def test_status_lines_end_at_the_first_line_that_is_not_one():
    program = load_program()
    walk_finder = program.load_walk_finder()
    case = Case(next_to_present="item 4 of 9")
    case.minutes.write_text("# Minutes\n\nitem 4 of 9: the user answered approved (2026-10-23 10:00), which makes its "
                            "change. Fast reads:\n- the status line\nA note.\n- a later bullet\n"
                            "#next_to_present item 4 of 9\n")
    _, _, statuses = program.last_answer(walk_finder, case.minutes, walk_finder.markdown_parser())
    check("the answer's status lines stop at the first line that is not a status line",
          statuses == ["the status line"], repr(statuses))


def test_a_deferred_line_awaiting_a_ruling_records_a_deferral():
    case = summary_case(next_to_present="item 2 of 5",
                        recorded="Item 1 of 5: approved. <accepted>\n"
                                 "Item 2 of 5: deferred until the redraft is read. <revised, awaiting ruling>\n"
                                 "Item 3 of 5: approved. <accepted>\nItem 4 of 5: approved. <accepted>\n"
                                 "Item 5 of 5: approved. <accepted>\n")
    case.run("check", "--deferred")
    closed = case.run("close")
    check("a `<revised, awaiting ruling>` line whose first word is deferred counts as a deferral, so the next "
          "deferral is the second",
          closed.returncode == 0 and closed.stdout.startswith("item 2 of 5 is deferred a second time")
          and marker(case) == "#next_to_present none, closed", described(closed) + case.minutes.read_text())


def test_close_holds_the_answer_for_a_waiting_new_item():
    case = Case()
    case.run("check")
    with open(case.minutes, "a") as minutes:
        minutes.write("#next_to_present item 5 of 9\n")
    result = case.run("close")
    lines = result.stdout.rstrip("\n").split("\n")
    check("close holds the answer while a new item is waiting",
          result.returncode == 0
          and lines[0] == ("item 3 of 9's answer does not take effect yet: item 5 of 9, which a fast-read finding "
                           "raised, waits for the user's answer, and the minutes record item 3 of 9's answer as held "
                           "until he answers item 5 of 9.")
          and sum("fast read had to be run" in line for line in lines) == 2
          and lines[-1] == ("Then present item 5 of 9, and record the user's answer to it in the minutes as "
                            "the outcome of item 3 of 9 too.")
          and case.minutes.read_text().rstrip().endswith(
              "item 3 of 9: answer held: item 5 of 9, raised by a fast-read finding, waits for the user's answer. <open>\n"
              "#next_to_present item 5 of 9"),
          described(result))


def test_close_without_a_check_fails():
    case = Case()
    result = case.run("close")
    check("close with no answer line in the minutes fails on stderr",
          result.returncode == 1 and result.stdout == "" and result.stderr.startswith(FAILURE_PREFIX + "close: ")
          and "has no line recording the user's answer" in result.stderr,
          described(result))


def test_close_after_a_failed_check_refuses_to_reread_a_closed_answer():
    case = Case(next_to_present="item 4 of 9")
    case.run("check")
    case.run("close")
    before = case.minutes.read_bytes()
    failed_check = case.run("check", "--item", "6")
    result = case.run("close")
    check("close after a check that failed refuses, writing nothing, instead of holding the closed answer",
          failed_check.returncode == 2
          and result.returncode == 1 and result.stdout == "" and result.stderr.startswith(FAILURE_PREFIX + "close: ")
          and "item 4 of 9, is already recorded by an earlier close" in result.stderr
          and "\nRun `python3 " in result.stderr
          and case.minutes.read_bytes() == before,
          described(result))


def test_close_run_twice_refuses_the_second_time():
    case = Case()
    case.run("check")
    with open(case.minutes, "a") as minutes:
        minutes.write("#next_to_present item 5 of 9\n")
    case.run("close")
    before = case.minutes.read_bytes()
    result = case.run("close")
    check("a second close of a held answer refuses, writing nothing",
          result.returncode == 1 and "is already recorded by an earlier close" in result.stderr
          and case.minutes.read_bytes() == before,
          described(result))


def test_no_open_walk_or_no_item_fails():
    case = Case(next_to_present="none, closed")
    result = case.run("check")
    check("check with no open approval-walk fails on stderr",
          result.returncode == 1 and result.stderr.startswith(FAILURE_PREFIX + "check: ") and "no approval-walk is open" in result.stderr, described(result))
    case = Case(next_to_present="item 8 of 9")
    result = case.run("check")
    check("check on an item the walk-document lacks fails on stderr",
          result.returncode == 1 and result.stderr.startswith(FAILURE_PREFIX + "check: ") and "has no heading `Item 8 of 9`, which the minutes name" in result.stderr, described(result))
    case = Case(next_to_present="items 6 to 4 of 9")
    result = case.run("check")
    check("check on a backwards range fails on stderr",
          result.returncode == 1 and result.stderr.startswith(FAILURE_PREFIX + "check: ") and "runs backwards" in result.stderr, described(result))


SUMMARY_DOCUMENT = """# A walk with a summary

## Item 1 of 5: one

#new "Text one."

## Item 2 of 5: two

Recommendation: leave it.

## Item 3 of 5: three

Recommendation: leave it.

## Item 4 of 5: four

Recommendation: leave it.

## Item 5 of 5: summary

The walk in short.
"""


def summary_case(next_to_present="item 2 of 5", recorded=""):
    case = Case(next_to_present=next_to_present, document=SUMMARY_DOCUMENT)
    case.minutes.write_text(f"# Minutes\n\n{recorded}#next_to_present {next_to_present}\n")
    return case


def marker(case):
    return case.minutes.read_text().rstrip("\n").split("\n")[-1]


def test_a_deferral_is_recorded_and_the_item_comes_back_before_the_summary_item():
    case = summary_case(next_to_present="item 2 of 5", recorded="- Item 1, 2026-10-20: approved. <accepted>\n")
    checked = case.run("check", "--deferred")
    check("check --deferred runs no fast read, logs no counts, and writes the no-change answer line",
          checked.returncode == 0 and case.calls.read_text() == "" and not case.counts_log.exists()
          and re.search(r"\nitem 2 of 5: the user answered deferred #case_against_none \(\d{4}-\d\d-\d\d \d\d:\d\d\), which makes no "
                        r"change\.\n$", case.minutes.read_text()) is not None
          and checked.stdout.rstrip().endswith(f"close --cwd {shlex.quote(str(case.checkout.resolve()))}` and do what "
                                               "it prints."), described(checked))
    closed = case.run("close")
    check("close records a deferral as open and names the item after it",
          closed.returncode == 0
          and closed.stdout.split("\n")[0] == ("item 2 of 5 is deferred, and the minutes record it; it comes back "
                                              "just before the summary item.")
          and "item 2 of 5: deferred; it moves to just before the summary item. <open>\n" in case.minutes.read_text()
          and marker(case) == "#next_to_present item 3 of 5", described(closed) + case.minutes.read_text())
    for _ in range(2):
        case.run("check")
        case.run("close")
    check("a deferred item is named again just before the summary item",
          marker(case) == "#next_to_present item 2 of 5", case.minutes.read_text())
    case.run("check")
    closed = case.run("close")
    check("once the deferred item is decided, the summary item is next",
          closed.returncode == 0 and marker(case) == "#next_to_present item 5 of 5", described(closed))
    case.run("check")
    closed = case.run("close")
    check("when the minutes record every item, the marker reads `none, closed` and close says to close the walk",
          closed.returncode == 0 and marker(case) == "#next_to_present none, closed"
          and closed.stdout.rstrip().split("\n")[-1] == (
              "No item is left to present, and the minutes' `#next_to_present` line now reads `none, closed`: "
              "go on to the walk-me-through skill's closing."), described(closed))


def test_an_item_deferred_a_second_time_leaves_the_walk():
    case = summary_case(next_to_present="item 2 of 5",
                        recorded="item 2 of 5: deferred; it moves to just before the summary item. <open>\n"
                                 "Item 1 of 5: approved.\nItem 4 of 5: approved.\nItem 5 of 5: approved.\n")
    case.run("check", "--deferred")
    closed = case.run("close")
    check("a second deferral is recorded as open, the agent is told to keep it as a task, and it is not named again",
          closed.returncode == 0
          and closed.stdout.split("\n")[:2] == [
              "item 2 of 5 is deferred a second time, so the minutes record it as open and it leaves the walk.",
              "Add it to your task list if it is not already a task."]
          and "item 2 of 5: deferred a second time, so it leaves the walk and stays open. <open>\n"
          in case.minutes.read_text()
          and marker(case) == "#next_to_present item 3 of 5", described(closed) + case.minutes.read_text())
    case.run("check")
    case.run("close")
    check("once every other item is recorded, the twice-deferred item is not named and the walk closes",
          marker(case) == "#next_to_present none, closed", case.minutes.read_text())


def test_an_answer_that_changes_nothing_is_recorded():
    case = summary_case(next_to_present="item 3 of 5")
    case.run("check", "--disapproved")
    closed = case.run("close")
    check("a D on an item that adds no text is recorded as decided, and the walk goes on",
          closed.returncode == 0 and "item 3 of 5: disapproved; every text the change adds has had a fast read. "
          "<rejected>\n" in case.minutes.read_text() and marker(case) == "#next_to_present item 4 of 5",
          described(closed))


def test_the_marker_is_written_as_the_last_line_and_skips_recorded_items():
    case = summary_case(next_to_present="item 2 of 5",
                        recorded="Item 3 (three): \"yes\" (user-ruled 2026-10-22) <accepted> approved.\n")
    with open(case.minutes, "a") as minutes:
        minutes.write("A note written after the marker.\n")
    case.run("check")
    closed = case.run("close")
    check("close writes the marker as the minutes' last line, below a note written after the old marker",
          closed.returncode == 0 and marker(case) == "#next_to_present item 4 of 5", case.minutes.read_text())
    case = summary_case(next_to_present="item 4 of 5",
                        recorded="Item 2, 2026-10-21: approved.\n- **Item 5 of 5**: the user: \"ok\". <accepted>\n")
    case.run("check")
    case.run("close")
    check("after the last item the minutes do not record, the walk goes round to the first one they do not",
          marker(case) == "#next_to_present item 1 of 5", case.minutes.read_text())
    case = summary_case(next_to_present="item 4 of 5",
                        recorded="- 2026-10-21T21:23:41Z Item 1 <rejected> (D): the user: \"no\".\n"
                                 "- 2026-10-22 00:40 Item 2 <accepted> (A).\n- Item 5, 2026-10-21: approved.\n")
    case.run("check")
    case.run("close")
    check("a minutes line that opens with a timestamp records its item",
          marker(case) == "#next_to_present item 3 of 5", case.minutes.read_text())


STRAY_TOTALS_DOCUMENT = """# A walk re-planned from 10 and 18 items to 16

## Item 7 of 10: from an older count

## Item 9 of 18: from another older count

## Item 1 of 16: one

## Item 2 of 16: the summary table

## Item 3 of 16: three

## Item 4 of 16: four

## Item 5 of 16: summary

## Item 6 of 16: an appendix
"""


def test_the_summary_item_and_the_walks_total_pick_the_order():
    case = Case(next_to_present="item 3 of 16", document=STRAY_TOTALS_DOCUMENT)
    case.minutes.write_text("# Minutes\n\n#next_to_present item 3 of 16\n")
    case.run("check", "--deferred")
    case.run("close")
    case.run("check")
    case.run("close")
    check("a deferred item comes back before the heading whose point is summary, not before a later item or one "
          "that only mentions a summary", marker(case) == "#next_to_present item 3 of 16", case.minutes.read_text())
    case = Case(next_to_present="item 6 of 16", document=STRAY_TOTALS_DOCUMENT)
    case.minutes.write_text("# Minutes\n\n" + "".join(f"Item {n} of 16: approved.\n" for n in range(1, 6))
                            + "#next_to_present item 6 of 16\n")
    case.run("check")
    closed = case.run("close")
    check("items under another running count's total are not walked",
          closed.returncode == 0 and marker(case) == "#next_to_present none, closed", case.minutes.read_text())


def test_a_deferred_last_item_hands_on_to_the_first_unrecorded_item():
    case = Case(next_to_present="item 5 of 9")
    case.run("check", "--deferred")
    closed = case.run("close")
    check("deferring the walk-document's last item, with no summary item, names the first item not recorded",
          closed.returncode == 0 and marker(case) == "#next_to_present item 3 of 9", case.minutes.read_text())


def test_an_outcome_tag_decides_whether_a_line_records_a_decision():
    case = summary_case(next_to_present="item 3 of 5",
                        recorded="Item 2 of 5: deferred until the approved migration finishes. <open>\n"
                                 "- Item 1, a proposal: <accepted>. A side direction, <open> until scoped.\n"
                                 "Item 4 of 5: the user asked again; approved wording waits. <revised, awaiting ruling>\n")
    case.run("check")
    closed = case.run("close")
    check("an open line naming 'approved' is not a decision, a line with <accepted> is, whatever <open> follows",
          closed.returncode == 0 and marker(case) == "#next_to_present item 4 of 5", case.minutes.read_text())
    case.run("check")
    case.run("close")
    check("an item deferred in a hand-written open line comes back before the summary item",
          marker(case) == "#next_to_present item 2 of 5", case.minutes.read_text())
    case.run("check")
    case.run("close")
    case.run("check")
    case.run("close")
    check("an item whose line has <accepted> and then an <open> side note stays decided, so the walk closes "
          "after the summary item", marker(case) == "#next_to_present none, closed", case.minutes.read_text())
    case = summary_case(next_to_present="item 3 of 5", recorded="Item 2 of 5: deferred, approved wording to come.\n")
    case.run("check")
    case.run("close")
    case.run("check")
    case.run("close")
    check("an untagged line whose first word is deferred records a deferral, not a decision",
          marker(case) == "#next_to_present item 2 of 5", case.minutes.read_text())


DOTTED_PART_DOCUMENT = """# A walk with a part added after a re-plan

## Item 1 of 6: one

## Item 2 of 6: two

## Item 2.1 of 6: a part the user raised

## Item 3 of 6: three

## Item 4 of 6: four

## Item 5 of 6: summary
"""


def test_a_note_naming_later_items_with_approved_as_a_modifier_does_not_skip_them():
    case = Case(next_to_present="item 2.1 of 6", document=DOTTED_PART_DOCUMENT)
    case.minutes.write_text("# Minutes\n\nItem 1 of 6: approved. <accepted>\n"
                            "Items 2 to 4: respelled after item 1; item 2 cites the approved definition.\n"
                            "Item 2 of 6: approved. <accepted>\n#next_to_present item 2.1 of 6\n")
    case.run("check")
    closed = case.run("close")
    check("after a dotted part is approved, a note naming later items whose `approved` follows `the` leaves them "
          "unrecorded, so the item after the part comes next, not the summary item",
          closed.returncode == 0 and marker(case) == "#next_to_present item 3 of 6",
          described(closed) + case.minutes.read_text())


def test_a_minutes_line_with_an_unusable_item_range_is_skipped():
    case = summary_case(next_to_present="item 3 of 5",
                        recorded="Items 4 to 2 of 5: approved.\nItem 4 of 5: approved.\n")
    case.run("check")
    closed = case.run("close")
    check("a minutes line naming a backwards range records nothing, and later lines still count",
          closed.returncode == 0 and marker(case) == "#next_to_present item 5 of 5", described(closed))


def test_answers_to_items_shown_together_are_recorded_as_the_refusal_says():
    for order in (((5, "--disapproved"), (6, None)), ((6, None), (5, "--disapproved"))):
        case = Case(next_to_present="items 5 and 6 of 9")
        refused = case.run("check", "--disapproved")
        results = []
        for number, flag in order:
            with case.minutes.open("a") as minutes:
                minutes.write(f"#next_to_present item {number} of 9\n")
            results += [case.run("check", *([flag] if flag else [])), case.run("close")]
        text = case.minutes.read_text()
        check(f"after check refuses two items waiting, one `#next_to_present` line per item records each answer, "
              f"in the order {[number for number, _ in order]}",
              refused.returncode == 1 and all(result.returncode == 0 for result in results)
              and "item 5 of 9: disapproved; every text the change adds has had a fast read. <rejected>" in text
              and "item 6 of 9: approved; every text the change adds has had a fast read. <accepted>" in text,
              described(results[-1]))


def test_the_walk_goes_on_after_the_last_of_several_items_answered_together():
    case = Case(next_to_present="items 3 and 6 of 9")
    with case.minutes.open("a") as minutes:
        minutes.write("items 3 and 6 of 9: the user answered approved (2026-10-23 10:00), which makes its change. "
                      "Fast reads:\n- no proposed text marked\n")
    closed = case.run("close")
    check("after items answered together, the walk starts after the last of them in the walk-document",
          closed.returncode == 0 and marker(case) == "#next_to_present item 7 of 9", described(closed))


def test_close_without_its_walk_document_fails():
    case = summary_case(next_to_present="item 2 of 5")
    case.run("check")
    (case.checkout / "docs" / "walk" / f"{WALK_NAME}.md").unlink()
    before = case.minutes.read_text()
    closed = case.run("close")
    check("close fails on stderr, writing nothing, when the walk-document is gone",
          closed.returncode == 1 and closed.stderr.startswith(FAILURE_PREFIX + "close: ")
          and "does not exist" in closed.stderr and case.minutes.read_text() == before, described(closed))


def test_repeat_explain_and_other_options_have_no_flag():
    case = summary_case(next_to_present="item 2 of 5")
    for flag in ("--repeat", "--explain", "--other-options"):
        result = case.run("check", flag)
        check(f"check {flag} is refused as usage, since R, E and O decide nothing",
              result.returncode == 2 and "the user answered" not in case.minutes.read_text(), described(result))


def test_a_changed_target_is_noted_but_does_not_fail_the_check():
    case = Case()
    result = case.run("check", mode="target-changed")
    check("a fast read whose target changed has its line in the status line, with exit 0",
          result.returncode == 0
          and result.stdout.split("\n")[0].endswith(
              "The fast read also said: cold-read-fast-read: #cold_read_target_changed_during_run: the target changed "
              "while it was read.")
          and "did not ship its record" not in result.stdout, described(result))


def test_a_log_store_this_machine_cannot_reach_is_reported():
    case = Case(next_to_present="item 4 of 9")
    program = load_program()
    unreachable = [Path("/nowhere/box/cold-read-records"), Path("/nowhere/mac/cold-read-records")]
    program.reachable_log_store_records = lambda: (None, unreachable)
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        status = program.main(["check", "--cwd", str(case.checkout), "--cold-read-records", str(case.records),
                               "--fast-read-program", str(case.stand_in)])
    check("with no counts log given and no log-store reachable, check says so and that the minutes record the "
          "answer, with exit 2",
          status == 2
          and "the fast-read counts were not logged to the log-store: this machine reaches the log-store at "
              "neither /nowhere/box/cold-read-records or /nowhere/mac/cold-read-records" in output.getvalue()
          and "item 4 of 9: the user answered approved #case_against_none (" in case.minutes.read_text(),
          f"status {status}, output {output.getvalue()!r}")


SHARED_HEADING_CROSS_REFERENCE_DOCUMENT = """# A walk

## Item 4 of 9: four

Recommendation: do four.

## Items 5 and 6 of 9: grouped

**Item 5 of 9**: the label wording.

#new "Label text five."

Recommendation: adopt label text five.

**Item 6 of 9**: the button wording.

#new "Button text six."

Recommendation: use the same style as Item 5 of 9.

## Item 7 of 9: seven

Recommendation: do seven.
"""


def test_a_mention_of_an_item_inside_another_is_not_its_start():
    case = Case(next_to_present="item 5 of 9", document=SHARED_HEADING_CROSS_REFERENCE_DOCUMENT)
    result = case.run("check")
    check("item 5's text is fast-read, not item 6's, though item 6 mentions `Item 5 of 9`",
          result.returncode == 0 and case.calls.read_text() == "Label text five.\n", described(result))
    case = Case(next_to_present="item 6 of 9", document=SHARED_HEADING_CROSS_REFERENCE_DOCUMENT)
    result = case.run("check")
    check("item 6's own text is fast-read", result.returncode == 0 and case.calls.read_text() == "Button text six.\n",
          described(result))
    document = SHARED_HEADING_CROSS_REFERENCE_DOCUMENT.replace(
        "Recommendation: use the same style as Item 5 of 9.", "Item 5 of 9 sets the style this follows.")
    case = Case(next_to_present="item 5 of 9", document=document)
    result = case.run("check")
    check("a later line of another item that opens with `Item 5 of 9` does not move item 5's start",
          result.returncode == 0 and case.calls.read_text() == "Label text five.\n", described(result))
    document = SHARED_HEADING_CROSS_REFERENCE_DOCUMENT.replace(
        "**Item 5 of 9**: the label wording.\n", "**Item 5 of 9**: the label wording.\n\nThe button in Item 6 of 9 "
        "reuses this label.\n")
    case = Case(next_to_present="item 5 of 9", document=document)
    result = case.run("check")
    check("a mention of `Item 6 of 9` inside item 5, before item 6 starts, does not end item 5 there",
          result.returncode == 0 and case.calls.read_text() == "Label text five.\n", described(result))
    document = SHARED_HEADING_CROSS_REFERENCE_DOCUMENT.replace(
        "**Item 5 of 9**: the label wording.\n", "**Item 5 of 9**: the label wording.\n\nItems 6 and 7 of 9 follow "
        "this label.\n")
    case = Case(next_to_present="item 5 of 9", document=document)
    result = case.run("check")
    check("a line inside item 5 that opens with a count of several items starts none of them",
          result.returncode == 0 and case.calls.read_text() == "Label text five.\n", described(result))


THREE_ITEM_DOCUMENT = """# A walk

## Item 1 of 3: one

Recommendation: do one.

## Item 2 of 3: two

Recommendation: do two.

## Item 3 of 3: summary

Recommendation: close.
"""


def test_a_later_awaiting_ruling_undoes_an_earlier_decision():
    for recorded in ("Item 2 of 3: approved. <accepted>\n"
                     "Item 2 of 3: the user asked for a change; redrafted. <revised, awaiting ruling>\n",
                     "Item 2 of 3: redrafted after discussion <revised, awaiting ruling>; item 3 <moved on, no "
                     "decision>.\n"):
        case = Case(next_to_present="item 1 of 3", document=THREE_ITEM_DOCUMENT)
        case.minutes.write_text(f"# Minutes\n\n{recorded}#next_to_present item 1 of 3\n")
        case.run("check")
        closed = case.run("close")
        check(f"after {recorded.splitlines()[-1][:60]!r}, close names item 2, which awaits a ruling",
              closed.returncode == 0 and marker(case) == "#next_to_present item 2 of 3",
              described(closed) + case.minutes.read_text())
    case = Case(next_to_present="item 1 of 3", document=THREE_ITEM_DOCUMENT)
    case.minutes.write_text("# Minutes\n\nItem 2 of 3: approved. <accepted> A side point stays <open>.\n"
                            "#next_to_present item 1 of 3\n")
    case.run("check")
    closed = case.run("close")
    check("`<open>` after a decision on its line, for a side point, leaves the item decided",
          closed.returncode == 0 and marker(case) == "#next_to_present item 3 of 3",
          described(closed) + case.minutes.read_text())


FOUR_ITEM_DOCUMENT = """# A walk

## Item 1 of 4: one

## Item 2 of 4: two

## Item 3 of 4: three

## Item 4 of 4: summary
"""


def test_an_item_the_walk_document_keeps_is_named_next_whatever_the_minutes_say_of_its_removal():
    case = Case(next_to_present="item 1 of 4", document=FOUR_ITEM_DOCUMENT)
    case.minutes.write_text("# Minutes\n\n#removed_from_approval_walk item 2 of 4\n#next_to_present item 1 of 4\n")
    case.run("check")
    closed = case.run("close")
    check("an item is removed from the approval-walk only by deleting its section from the walk-document",
          closed.returncode == 0 and marker(case) == "#next_to_present item 2 of 4",
          described(closed) + case.minutes.read_text())


def test_check_refuses_a_walk_document_close_would_refuse_before_any_fast_read():
    for document, next_to_present, reason in (
            ("# W\n\n## Item 2 of 3: two\n\n#new \"First.\"\n\n## Item 2 of 3: again\n\n#new \"Second.\"\n\n"
             "## Item 3 of 3: summary\n", "item 2 of 3", "more than one heading for `Item 2 of 3`"),
            ("# W\n\n## Item 1 of 3: one\n\n## Item 2 of 3: old\n\n#new \"Old.\"\n\n## Item 2 of 4: new\n\n"
             "#new \"New.\"\n", "item 2", "more than one total")):
        case = Case(next_to_present=next_to_present, document=document)
        before = case.minutes.read_text()
        result = case.run("check")
        check(f"check refuses, running no fast read and writing nothing, when the walk-document has {reason}",
              result.returncode == 1 and reason in result.stderr and case.calls.read_text() == ""
              and case.minutes.read_text() == before, described(result))


def test_each_parts_answer_is_recorded_and_close_records_each_parts_outcome():
    for flags, answered, recorded in (
            (("--part-answer", "2=d", "--part-answer", "1=AO"), "part 1 approved #approved_obvious, part 2 disapproved",
             "part 1 approved <accepted>, part 2 disapproved <rejected>"),
            (("--part-answer", "1=D", "--part-answer", "2=ao", "--part-answer", "3=a"),
             "part 1 disapproved, part 2 approved #approved_obvious, part 3 approved",
             "part 1 disapproved <rejected>, part 2 approved <accepted>, part 3 approved <accepted>"),
            (("--part-answer", "1=D", "--part-answer", "2=AO"), "part 1 disapproved, part 2 approved #approved_obvious",
             "part 1 disapproved <rejected>, part 2 approved <accepted>")):
        case = Case(next_to_present="item 4 of 9")
        checked = case.run("check", *flags)
        minutes = case.minutes.read_text()
        check(f"check {' '.join(flags)} writes each part's answer as its word, in part number order",
              checked.returncode == 0 and re.search(
                  rf"\nitem 4 of 9: the user answered {re.escape(answered)} #case_against_none \(\d{{4}}-\d\d-\d\d \d\d:\d\d\), "
                  r"which makes its change\. Fast reads:\n- no proposed text marked\n$", minutes) is not None,
              described(checked) + minutes)
        closed = case.run("close")
        check(f"close after check {' '.join(flags)} records each part's outcome on one line, the last part's "
              "included, and moves on to the next item",
              closed.returncode == 0
              and closed.stdout.rstrip("\n").split("\n") == [
                  "item 4 of 9's answer is recorded in the minutes, and its change may now be made.",
                  "Your next message must include these lines, as they are:",
                  "no proposed text marked"] + TOOK_EFFECT_NEXT
              and case.minutes.read_text().rstrip().endswith(
                  f"item 4 of 9: {recorded}; every text the change adds has had a fast read.\n"
                  "#next_to_present item 6 of 9"), described(closed) + case.minutes.read_text())


def test_a_part_given_more_than_one_answer_is_refused_writing_nothing():
    for flags, named in ((("--part-answer", "1=A", "--part-answer", "2=D", "--part-answer", "1=D"), "part 1"),
                         (("--part-answer", "2=A", "--part-answer", "1=A", "--part-answer", "2=A", "--part-answer", "1=D"), "part 1, part 2")):
        case = Case()
        before = case.minutes.read_text()
        result = case.run("check", *flags)
        check(f"check {' '.join(flags)} is refused on stderr, writing nothing and running no fast read",
              result.returncode == 1
              and result.stderr == (FAILURE_PREFIX + f"check: nothing written: --part-answer gives {named} more than one "
                                    "answer.\nRun check again giving each part's number once, with the letter the "
                                    "user gave that part.\n")
              and case.minutes.read_text() == before and case.calls.read_text() == ""
              and not case.counts_log.exists(), described(result))


def test_a_part_answer_other_than_a_ao_or_d_or_combined_with_another_answer_flag_is_refused_as_usage():
    for flags in (("--part-answer", "1=Z"), ("--part-answer", "1=Aa"), ("--part-answer", "x=A"), ("--part-answer", "1A"), ("--part-answer", "1=A2")):
        case = Case(next_to_present="item 4 of 9")
        result = case.run("check", *flags)
        check(f"check {' '.join(flags)} is refused as usage, saying what a part's answer is, writing nothing",
              result.returncode == 2 and "usage:" in result.stderr
              and f"argument --part-answer: `{flags[1]}` is not a part's answer: give the part's number, `=`, then A, AO or "
                  "D" in result.stderr
              and "the user answered" not in case.minutes.read_text(), described(result))
    for flags in (("--part-answer", "1=A", "--obvious"), ("--deferred", "--part-answer", "1=A"), ("--part-answer", "1=A", "--option", "2")):
        case = Case(next_to_present="item 4 of 9")
        result = case.run("check", *flags)
        check(f"check {' '.join(flags)} is refused as usage, writing nothing",
              result.returncode == 2 and "not allowed with argument" in result.stderr
              and "the user answered" not in case.minutes.read_text(), described(result))


def test_an_item_with_no_case_against_line_is_refused_writing_nothing():
    document = WALK_DOCUMENT.replace("#case_against weak: the page grows by one line.\n\n", "")
    for flags in ((), ("--obvious",), ("--disapproved",), ("--deferred",), ("--part-answer", "1=A")):
        case = Case(document=document)
        before = case.minutes.read_text()
        result = case.run("check", *flags)
        check(f"check {' '.join(flags) or '(A)'} on an item with no `#case_against` line is refused, writing nothing",
              result.returncode == 1 and "item 3 of 9" in result.stderr and "has no `#case_against` line" in result.stderr
              and f"check{''.join(' ' + flag for flag in flags)}` again." in result.stderr
              and case.minutes.read_text() == before and case.calls.read_text() == "", described(result))
    for flags in (("--option", "2"), ("--option", "3")):
        case = Case(document=document)
        result = case.run("check", *flags)
        check(f"check {' '.join(flags)} needs no `#case_against` line and records no rating",
              result.returncode == 0 and f"the user answered approved option {flags[1]} (" in case.minutes.read_text(),
              described(result))


def test_a_case_against_line_with_no_rating_is_refused_writing_nothing():
    case = Case(document=WALK_DOCUMENT.replace("#case_against weak:", "#case_against fairly weak:"))
    before = case.minutes.read_text()
    result = case.run("check")
    check("a `#case_against` line that opens with no rating is refused, quoting the line, writing nothing",
          result.returncode == 1 and "`#case_against fairly weak: the page grows by one line.`, does not open with a "
          "rating" in result.stderr and case.minutes.read_text() == before, described(result))


def test_the_rating_is_written_beside_every_answer_and_close_still_reads_it():
    case = Case(next_to_present="item 5 of 9")
    result = case.run("check", "--disapproved")
    check("a bold `#case_against very strong:` line is read, and its rating written as one hashtag word",
          result.returncode == 0 and "the user answered disapproved #case_against_very_strong (" in case.minutes.read_text(),
          described(result))
    closed = case.run("close")
    check("close reads an answer line that carries a rating, and records the answer's outcome",
          closed.returncode == 0 and "\nitem 5 of 9: disapproved; every text the change adds has had a fast read. "
          "<rejected>\n" in case.minutes.read_text(), described(closed))


# Items written as an agent drafts one to settle without the user: each kind with the evidence lines it needs.
NOT_ASKED_DOCUMENT = """# A walk

## Item 1 of 7: the page's path, caught up with the merged code

#old "The poems are in pages/."

#new "The poems are in docs/poems/."

#not_asked_touches docs/poems/index.md

#not_asked_source commit abc1234 moved the poems.

#case_against none.

Recommendation: change the sentence.

## Item 2 of 7: the line counter counts the last line

#not_asked_touches tools/counter.py tools/counter-test.py

#not_asked_test tools/counter-test.py

#case_against weak: the fix costs a few lines of code.

Recommendation: fix the counter.

## Item 3 of 7: drop the old reader

#not_asked_touches tools/old_reader.py tools/main.py

#not_asked_unused old_reader

#case_against none.

Recommendation: remove it.

## Item 4 of 7: rename poem-list to poem-index

#not_asked_touches docs/poems/index.md

#not_asked_rename poem-list poem-index

#case_against none.

Recommendation: rename it.

## Item 5 of 7: file the GHI the user asked for

#not_asked_source the user, 2026-10-20: "make a GHI for the counter."

#case_against none.

Recommendation: file it.

## Item 6 of 7: a new rule

#new "Every poem has a date."

#case_against strong: it adds a rule nobody asked for.

Recommendation: add the rule.

## Item 7 of 7: summary

#case_against none.

Nothing to decide.
"""


def not_asked_case(next_to_present, files=None):
    case = Case(next_to_present=next_to_present, document=NOT_ASKED_DOCUMENT)
    defaults = {"docs/poems/index.md": "The poems: poem-list.\n", "tools/counter.py": "count = 0\n",
                "tools/counter-test.py": "import counter\n", "tools/old_reader.py": "def old_reader(): pass\n",
                "tools/main.py": "from old_reader import old_reader\n",
                "docs/poems-glossary.md": "- **poem-index** — the page that lists every poem.\n"}
    for path, text in {**defaults, **(files or {})}.items():
        if text is None:
            continue
        (case.checkout / path).parent.mkdir(parents=True, exist_ok=True)
        (case.checkout / path).write_text(text)
    return case


def test_each_kind_with_its_evidence_settles_without_the_user_and_close_records_it_accepted():
    for kind in (1, 2, 3, 4, 5):
        case = not_asked_case(f"item {kind} of 7")
        result = case.run("check", "--not-asked", str(kind))
        minutes = case.minutes.read_text()
        check(f"kind {kind} with its evidence is settled: the minutes say not asked, its kind and its rating",
              result.returncode == 0
              and re.search(rf"\nitem {kind} of 7: settled without asking the user, not asked, kind {kind} "
                            rf"#case_against_(?:none|weak) \(\d{{4}}-\d\d-\d\d \d\d:\d\d\), which makes its change\. "
                            r"Fast reads:\n", minutes) is not None
              and f"Before you run close, ask the advisor whether a later ruling or another open item overtakes item "
                  f"{kind} of 7" in result.stdout, described(result) + minutes)
        closed = case.run("close")
        check(f"close records the settled kind {kind} item as accepted, with not asked and its kind, and moves on",
              closed.returncode == 0
              and f"\nitem {kind} of 7: not asked, kind {kind}; every text the change adds has had a fast read. "
                  f"<accepted>\n" in case.minutes.read_text()
              and int(re.search(r"#next_to_present item (\d+) of 7$", case.minutes.read_text().rstrip())[1]) > kind,
              described(closed))
    case = not_asked_case("item 1 of 7")
    case.run("check", "--not-asked", "1")
    check("a settled item's `#new` texts get their fast read as an approval's do",
          case.calls.read_text() == "The poems are in docs/poems/.\n", repr(case.calls.read_text()))


def refused(case, kind, *problems):
    before = case.minutes.read_text()
    result = case.run("check", "--not-asked", str(kind))
    return (result.returncode == 1 and f"cannot be settled without asking the user as kind {kind}, because:"
            in result.stderr and all(problem in result.stderr for problem in problems)
            and case.minutes.read_text() == before and case.calls.read_text() == "", described(result))


def test_a_case_against_rated_above_weak_is_never_settled():
    check("an item rated strong is refused, whatever its kind",
          *refused(not_asked_case("item 6 of 7"), 1, "rates the case against strong",
                   "it has no `#not_asked_touches` line", "it has no `#not_asked_source` line"))


def test_each_kind_refuses_without_the_evidence_code_can_check():
    check("kind 2 is refused when the item names no test",
          *refused(not_asked_case("item 1 of 7"), 2, "it has no `#not_asked_test` line"))
    check("kind 4 is refused when the item gives no rename",
          *refused(not_asked_case("item 1 of 7"), 4, "it has no `#not_asked_rename` line"))
    check("kind 1 is refused when the item has no `#new` text",
          *refused(not_asked_case("item 5 of 7"), 1, "it has no `#new` line"))
    check("a touched file that is not in the checkout is refused",
          *refused(not_asked_case("item 1 of 7", {"docs/poems/index.md": None}), 1,
                   "`#not_asked_touches` names docs/poems/index.md, which is not in the checkout"))
    check("kind 2 is refused when it touches a new file that is not its test",
          *refused(not_asked_case("item 2 of 7", {"tools/counter.py": None}), 2,
                   "names tools/counter.py, which is not in the checkout",
                   "adds no file but a test"))
    case = not_asked_case("item 2 of 7", {"tools/counter-test.py": None})
    result = case.run("check", "--not-asked", "2")
    check("kind 2 may add the test that shows its fix", result.returncode == 0, described(result))
    case = not_asked_case("item 5 of 7")
    (case.checkout / "docs" / "walk" / f"{WALK_NAME}.md").write_text(NOT_ASKED_DOCUMENT.replace(
        '#not_asked_source the user, 2026-10-20: "make a GHI for the counter."',
        '#not_asked_source the user, 2026-10-20: "make a GHI for the counter."\n\n'
        '#not_asked_touches docs/issues/counter.md'))
    result = case.run("check", "--not-asked", "5")
    check("kind 5 may touch a file the ruling it carries out creates", result.returncode == 0, described(result))
    document = NOT_ASKED_DOCUMENT.replace("#not_asked_test tools/counter-test.py", "#not_asked_test tools/counter.py")
    case = not_asked_case("item 2 of 7")
    (case.checkout / "docs" / "walk" / f"{WALK_NAME}.md").write_text(document)
    check("kind 2 is refused when its named test is not a test file",
          *refused(case, 2, "`#not_asked_test` names tools/counter.py, which is not a test file"))


def test_a_removal_is_refused_while_an_untouched_file_still_names_what_it_removes():
    check("kind 3 is refused when a file the item does not touch still names the removed thing",
          *refused(not_asked_case("item 3 of 7", {"tools/other.py": "old_reader()\n"}), 3,
                   "`old_reader`, named on its `#not_asked_unused` line, is still named in tools/other.py"))
    check("kind 3 is refused when an untouched file names the removed thing in another spelling",
          *refused(not_asked_case("item 3 of 7", {"docs/tools.md": "Run `old-reader.py`.\n"}), 3,
                   "`old_reader`, named on its `#not_asked_unused` line, is still named in docs/tools.md"))
    for spelling in ("OLD_READER_PATH = 1", "use_old_reader_cache()", "Old_Reader()"):
        check(f"kind 3 is refused when an untouched file holds the removed name in another case or inside a longer "
              f"name: {spelling}",
              *refused(not_asked_case("item 3 of 7", {"tools/other.py": f"{spelling}\n"}), 3,
                       "`old_reader`, named on its `#not_asked_unused` line, is still named in tools/other.py"))
    check("kind 3 with no unused line is refused when it touches a file that is not Markdown",
          *refused(not_asked_case("item 2 of 7"), 3, "it has no `#not_asked_unused` line, and `#not_asked_touches` "
                                                     "names tools/counter.py, tools/counter-test.py"))
    case = not_asked_case("item 1 of 7")
    result = case.run("check", "--not-asked", "3")
    check("kind 3 with no unused line settles history removed from Markdown", result.returncode == 0,
          described(result))


def test_a_rename_is_refused_unless_a_glossary_lists_the_new_name_and_no_untouched_file_keeps_the_old():
    check("kind 4 is refused when no glossary file lists the new name",
          *refused(not_asked_case("item 4 of 7", {"docs/poems-glossary.md": "- **other** — something else.\n"}), 4,
                   "the new name `poem-index` is the term of no entry"))
    check("kind 4 is refused when a glossary only mentions the new name, as in an example, outside an entry's term",
          *refused(not_asked_case("item 4 of 7", {"docs/poems-glossary.md": "- **other** — not poem-index.\n"}), 4,
                   "the new name `poem-index` is the term of no entry"))
    check("kind 4 is refused when the entry is in a file whose name only holds the word glossary, not a glossary",
          *refused(not_asked_case("item 4 of 7", {"docs/poems-glossary.md": None,
                                                  "docs/how-to-name-glossary-terms.md": "- **poem-index** — bad.\n"}),
                   4, "the new name `poem-index` is the term of no entry"))
    check("kind 4 is refused when a file the item does not touch still holds the old name",
          *refused(not_asked_case("item 4 of 7", {"docs/about.md": "See poem-list.\n"}), 4,
                   "`poem-list`, named on its `#not_asked_rename` line, is still named in docs/about.md"))
    for spelling in ("POEM_LIST = 1", "poem_list_path = 1", "class PoemList: pass", "poemList = 1"):
        check(f"kind 4 is refused when an untouched file holds the old name spelled as code spells it: {spelling}",
              *refused(not_asked_case("item 4 of 7", {"tools/poems.py": f"{spelling}\n"}), 4,
                       "`poem-list`, named on its `#not_asked_rename` line, is still named in tools/poems.py"))
    case = not_asked_case("item 4 of 7")
    document = NOT_ASKED_DOCUMENT.replace("#not_asked_rename poem-list poem-index", "#not_asked_rename poem-list")
    (case.checkout / "docs" / "walk" / f"{WALK_NAME}.md").write_text(document)
    check("kind 4 is refused when its rename line gives one name", *refused(case, 4, "does not give the old name, then "
                                                                                      "the new name"))


def test_a_git_grep_that_fails_is_reported_and_writes_nothing():
    case = not_asked_case("item 3 of 7")
    stub = case.root / "stub-bin"
    stub.mkdir()
    real_git = shutil.which("git")
    (stub / "git").write_text(f"#!/bin/sh\nfor argument in \"$@\"; do [ \"$argument\" = grep ] && "
                              f"{{ echo 'fatal: stub grep failure' >&2; exit 128; }}; done\nexec {real_git} \"$@\"\n")
    (stub / "git").chmod(0o755)
    before = case.minutes.read_text()
    environment = dict(os.environ, PATH=f"{stub}:{os.environ['PATH']}", STAND_IN_CALLS=str(case.calls),
                       STAND_IN_RECORDS=str(case.records))
    result = subprocess.run([sys.executable, str(PROGRAM), "check", "--not-asked", "3", "--cwd", str(case.checkout),
                             "--cold-read-records", str(case.records), "--fast-read-program", str(case.stand_in),
                             "--counts-log", str(case.counts_log)],
                            capture_output=True, text=True, env=environment, cwd=case.checkout)
    check("a `git grep` that exits with neither 0 nor 1 fails the check, naming the error, writing nothing",
          result.returncode == 1 and "`git grep` failed with exit 128" in result.stderr
          and "fatal: stub grep failure" in result.stderr and case.minutes.read_text() == before, described(result))


def main():
    try:
        for name, function in sorted(globals().items()):
            if name.startswith("test_") and callable(function):
                function()
    finally:
        shutil.rmtree(SUITE_ROOT, ignore_errors=True)
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
