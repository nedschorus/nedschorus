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
          and "close` and do what it prints." in lines[-1],
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
    "Then move the approval-walk on: to the next item, or after the last item, to the walk-me-through "
    "skill's closing."]


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
              "item 4 of 9: approved; every text the change adds has had a fast read. <accepted>"),
          described(result))


def test_each_answer_is_recorded_as_its_word():
    for flags, first, last in (
            (("--obvious",), "the user answered approved #approved_obvious (",
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
              and minutes.rstrip().endswith(last), described(checked) + described(closed) + minutes)


def test_answer_flags_exclude_each_other_and_option_takes_2_or_3():
    for flags in (("--obvious", "--disapproved"), ("--disapproved", "--option", "2"), ("--option", "4")):
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
                                                         "a fast read. <accepted>"), described(closed))
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
              "item 3 of 9: answer held: item 5 of 9, raised by a fast-read finding, waits for the user's answer. <open>"),
          described(result))


def test_close_without_a_check_fails():
    case = Case()
    result = case.run("close")
    check("close with no answer line in the minutes fails on stderr",
          result.returncode == 1 and result.stdout == "" and result.stderr.startswith(FAILURE_PREFIX + "close: ")
          and "has no line recording an answer that makes a change" in result.stderr,
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
