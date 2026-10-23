#!/usr/bin/env python3
"""Cases for the program that carries out the user's answer that makes a
change in an open approval-walk: its check step, which fast-reads each `#new`
text of the waiting item that has not had a fast read, and its close step.

Each case runs the program as a subprocess in a scratch checkout this suite
made. cold-read-fast-read.py is replaced by a stand-in this suite writes, so no
case calls a model. The exit code is asserted on every case.
"""

import importlib.util
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
'''

WALK_DOCUMENT = """# A walk

## Item 3 of 9: the opening sentence

The opening sentence changes. It says now:

#old "The page lists poems."

and will say:

#new "The page lists one poem per job an agent does."

- #new “Each row names the mistake it prevents.”

```
#new "inside a fence, not a proposed text"
```

Recommendation: change the sentence.

## Item 4 of 9: no proposal here

Nothing is proposed. Recommendation: leave it.

## Items 6 and 7 of 9: two small corrections

Item 6 of 9 fixes a path.

#new "The path is docs/walk/."

Item 7 of 9 drops a sentence.

#new "Item seven's text."

## Item 5 of 9: a new item a finding raised

#new "A changed decision."
"""


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
        (walk / f"{WALK_NAME}.md").write_text(document)
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
          and "Read each fast-read report named above as had to be run." in lines
          and f"close --cwd {shlex.quote(str(case.checkout.resolve()))}` and do what it prints." in lines[-1],
          described(result))
    check("a #new line inside a fence or in another item is not a proposed text",
          case.calls.read_text() == ("The page lists one poem per job an agent does.\n"
                                     "Each row names the mistake it prevents.\n"),
          repr(case.calls.read_text()))
    minutes = case.minutes.read_text()
    check("check records the answer as approved, and the status lines, in the minutes",
          re.search(r"\nitem 3 of 9: the user answered approved \(\d{4}-\d\d-\d\d \d\d:\d\d\), which makes "
                    r"its change\. Fast reads:\n", minutes) is not None
          and minutes.count("\n- `#new` text ") == 2, minutes)
    log = case.counts_log.read_text().split("\t")
    check("check appends the counts", log[1:] == [WALK_NAME, "item 3 of 9", "texts=2",
                                                   "already_done=0", "had_to_be_run=2\n"], repr(log))
    again = case.run("check")
    check("a text the earlier check fast-read is already done the next time",
          again.returncode == 0 and again.stdout.count("fast read already done") == 2
          and "Read each fast-read report" not in again.stdout, described(again))


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
    case = Case()
    result = case.run("check", "--after-advisor", mode="failed")
    check("after a FAILED fast read on an Aa answer, the rerun command keeps --after-advisor",
          result.returncode == 1 and "close.py check --after-advisor` again" in result.stdout, described(result))


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
    check("a counts log that cannot be written is printed, with exit 2",
          result.returncode == 2 and "The fast-read counts were not logged to " in result.stdout
          and result.stdout.startswith("no proposed text marked"), described(result))


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
            (("--obvious",), "the user answered approved #approved_obvious (",
             "item 4 of 9: approved; every text the change adds has had a fast read. <accepted>"),
            (("--after-advisor",), "the user answered approved #approved_after_advisor (",
             "item 4 of 9: approved; every text the change adds has had a fast read. <accepted>"),
            (("--disapproved",), "the user answered disapproved (",
             "item 4 of 9: disapproved; every text the change adds has had a fast read. <rejected>"),
            (("--option", "2"), "the user answered approved option 2 (",
             "item 4 of 9: approved option 2; every text the change adds has had a fast read. <accepted>"),
            (("--option", "3"), "the user answered approved option 3 (",
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


def test_item_picks_one_of_the_waiting_items():
    case = Case(next_to_present="items 6 and 7 of 9")
    result = case.run("check", "--item", "7")
    check("--item reads only that item's #new lines under a heading shared with another item",
          result.returncode == 0 and case.calls.read_text() == "Item seven's text.\n"
          and "\nitem 7 of 9: the user answered approved (" in case.minutes.read_text(), described(result))
    closed = case.run("close")
    check("close records the one item's answer while the other is still waiting",
          closed.returncode == 0 and closed.stdout.startswith("item 7 of 9's answer is recorded in the minutes")
          and case.minutes.read_text().rstrip().endswith("item 7 of 9: approved; every text the change adds has had "
                                                         "a fast read. <accepted>\n#next_to_present item 6 of 9")
          and closed.stdout.rstrip().endswith("Then present item 6 of 9, which the minutes' `#next_to_present` "
                                              "line now names."), described(closed))
    case = Case(next_to_present="items 6 and 7 of 9")
    result = case.run("check")
    check("without --item, check reads every waiting item",
          result.returncode == 0 and case.calls.read_text() == "The path is docs/walk/.\nItem seven's text.\n",
          described(result))
    case = Case(next_to_present="items 6 and 7 of 9")
    result = case.run("check", "--item", "8", "--disapproved")
    check("--item naming an item that is not waiting fails on stderr, writing nothing",
          result.returncode == 1 and result.stderr.startswith(FAILURE_PREFIX + "check: --item 8 is not among")
          and "give one of 6, 7" in result.stderr and "the user answered" not in case.minutes.read_text(),
          described(result))


def test_item_under_a_shared_heading_with_no_line_of_its_own_reads_the_whole_unit():
    document = WALK_DOCUMENT + "\n## Items 8 and 9 of 9: two rows\n\n#new \"Row eight.\"\n\n#new \"Row nine.\"\n\nNo count per row.\n"
    case = Case(next_to_present="items 8 and 9 of 9", document=document)
    result = case.run("check", "--item", "8")
    check("--item on a shared heading whose items have no count line of their own reads every #new line of it",
          result.returncode == 0 and case.calls.read_text() == "Row eight.\nRow nine.\n", described(result))


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
                           "raised, is waiting, and the minutes record the answer as held for it.")
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


def test_no_open_walk_or_no_item_fails():
    case = Case(next_to_present="none, closed")
    result = case.run("check")
    check("check with no open approval-walk fails on stderr",
          result.returncode == 1 and result.stderr.startswith(FAILURE_PREFIX + "check: ") and "no approval-walk is open" in result.stderr, described(result))
    case = Case(next_to_present="item 8 of 9")
    result = case.run("check")
    check("check on an item the walk-document lacks fails on stderr",
          result.returncode == 1 and result.stderr.startswith(FAILURE_PREFIX + "check: ") and "has no heading for `item 8 of 9`" in result.stderr, described(result))
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
          and re.search(r"\nitem 2 of 5: the user answered deferred \(\d{4}-\d\d-\d\d \d\d:\d\d\), which makes no "
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
    for item in ("3", "4"):
        case.run("check", "--item", item)
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
    case.run("check", "--item", "3")
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


def test_items_shown_together_stay_waiting_until_each_is_answered():
    case = summary_case(next_to_present="items 2, 3 and 4 of 5")
    case.run("check", "--item", "2")
    closed = case.run("close")
    check("answering one of three items shown together leaves the other two named",
          closed.returncode == 0 and marker(case) == "#next_to_present items 3 and 4 of 5"
          and closed.stdout.rstrip().endswith("Then present items 3 and 4 of 5, which the minutes' "
                                              "`#next_to_present` line now names."), described(closed))


def test_a_minutes_line_with_an_unusable_item_range_is_skipped():
    case = summary_case(next_to_present="item 3 of 5",
                        recorded="Items 4 to 2 of 5: approved.\nItem 4 of 5: approved.\n")
    case.run("check")
    closed = case.run("close")
    check("a minutes line naming a backwards range records nothing, and later lines still count",
          closed.returncode == 0 and marker(case) == "#next_to_present item 5 of 5", described(closed))


def test_the_walk_goes_on_after_the_last_of_several_items_answered_together():
    case = Case(next_to_present="items 3 and 6 of 9")
    case.run("check")
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
