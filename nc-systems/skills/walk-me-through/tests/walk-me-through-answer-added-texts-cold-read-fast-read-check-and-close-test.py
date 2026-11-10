#!/usr/bin/env python3
"""Cases for the program that carries out the user's answer that makes a
change in an open approval-walk: its check step, which fast-reads each text
the answer adds to the waiting item, `#new` or `#new_if_d`, that has not had a
fast read, and its close step.

Most cases run the program as a subprocess in a scratch checkout this suite
made; the rest load it into this process, in a forked child where a signal
must end the process. cold-read-fast-read.py is replaced by a stand-in this suite writes, so no
case calls a model, except one case that runs a copy of the real
cold-read-fast-read.py with stub models, to show the check reads that
program's own output. The exit code is asserted on every case.
"""

import contextlib
import datetime
import importlib.util
import io
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import types
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
_cold_read_scratch_fixture_spec = importlib.util.spec_from_file_location(
    "cold_read_scratch_repository_test_fixture",
    Path(__file__).resolve().parents[3] / "cold-read" / "tests"
    / "cold-read-scratch-repository-test-fixture.py")
cold_read_scratch_fixture = importlib.util.module_from_spec(_cold_read_scratch_fixture_spec)
_cold_read_scratch_fixture_spec.loader.exec_module(cold_read_scratch_fixture)
_scratch_directory_common_spec = importlib.util.spec_from_file_location(
    "test_scratch_directory_whose_earlier_killed_runs_leftovers_are_removed_first_common",
    Path(__file__).resolve().parents[3] / "general-tools"
    / "test-scratch-directory-whose-earlier-killed-runs-leftovers-are-removed-first-common.py")
_scratch_directory_common = importlib.util.module_from_spec(_scratch_directory_common_spec)
_scratch_directory_common_spec.loader.exec_module(_scratch_directory_common)
SUITE_ROOT = _scratch_directory_common.scratch_directory_after_removing_ones_killed_runs_left(
    "answer-added-texts-fast-read-check-test-")
WALK_NAME = "poem-page-2026-10-12"
FAILURE_PREFIX = "walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close "
failures = []

# Behaves as cold-read-fast-read.py does on the records route: writes a
# cold-read-record with cold-read-fast-read.md and target/, prints the report's path.
STAND_IN = r'''
import os, signal, sys, time
from pathlib import Path
target = Path(sys.argv[sys.argv.index("--target") + 1])
with open(os.environ["STAND_IN_CALLS"], "a") as calls:
    calls.write(target.read_text())
mode = os.environ.get("STAND_IN_MODE", "")
if mode == "slow":
    time.sleep(3)  # A read ahead still running when the item it reads comes up.
if mode.startswith("stopped-unremovable "):
    (target.parent / "locked").mkdir()
    (target.parent / "locked" / "file").write_text("x")
    (target.parent / "locked").chmod(0o500)
if mode.startswith("signalled-then-reports "):
    os.kill(os.getppid(), getattr(signal, mode.split()[1]))
if mode.startswith("stopped"):
    os.kill(os.getppid(), getattr(signal, mode.split()[1]))
    time.sleep(2)  # The check is stopped while it waits for this fast read.
    sys.exit(0)
if mode == "failed":
    print("FAILED: the stand-in cold-read-cell failed twice")
    sys.exit(1)
if mode == "silent-exit":
    sys.exit(3)
record = Path(os.environ["STAND_IN_RECORDS"]) / (target.stem + "-2026-10-17")
(record / "target").mkdir(parents=True, exist_ok=True)
(record / "target" / target.name).write_text(target.read_text())
(record / "cold-read-fast-read.md").write_text("findings\n")
print(record / "cold-read-fast-read.md")
if mode == "path-then-exit":
    sys.exit(4)
if mode == "path-then-exit-1":
    sys.exit(1)
if mode == "target-changed":
    sys.stderr.write("cold-read-fast-read: #cold_read_target_changed_during_run: the target changed while it was read.\n")
if mode in ("record-not-shipped", "record-not-shipped-then-exit-4", "record-not-shipped-then-killed"):
    sys.stderr.write("cold-read-fast-read: record: FAILED: ned-box could not be reached (ssh exit 255); "
                     "the record stays on disk.\n")
    sys.stdout.flush()
    sys.stderr.flush()
    if mode == "record-not-shipped-then-killed":
        import signal
        os.kill(os.getpid(), signal.SIGTERM)
    sys.exit(4 if mode == "record-not-shipped-then-exit-4" else 1)
if mode == "record-refused":
    sys.stderr.write("cold-read-fast-read: record: REFUSED: already in the store with different content.\n")
    sys.exit(1)
'''

# Behaves as gh does for the close step's two calls: `pr list` prints GH_STAND_IN_PULL_REQUESTS, `[]` by default;
# `pr comment` succeeds unless its number is in GH_STAND_IN_COMMENT_FAILS. Each call is appended to GH_STAND_IN_CALLS.
GH_STAND_IN = r'''
import json, os, sys, time
with open(os.environ["GH_STAND_IN_CALLS"], "a") as calls:
    calls.write(json.dumps(sys.argv[1:]) + "\n")
mode = os.environ.get("GH_STAND_IN_MODE", "")
if sys.argv[1:3] == ["pr", "list"]:
    if mode == "list-fails":
        sys.stderr.write("HTTP 502: Bad Gateway\n")
        sys.exit(1)
    if mode == "list-fails-silently":
        sys.exit(1)
    if mode == "list-killed":
        import signal
        os.kill(os.getpid(), signal.SIGTERM)
    if mode == "list-hangs":
        time.sleep(5)
    print("not json" if mode == "list-not-json" else os.environ.get("GH_STAND_IN_PULL_REQUESTS", "[]"))
elif sys.argv[1:3] == ["pr", "comment"] and sys.argv[3] in os.environ.get("GH_STAND_IN_COMMENT_FAILS", "").split():
    sys.stderr.write("GraphQL: Could not add comment\n")
    sys.exit(1)
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
A fenced line that names the `#new` mark inside a sentence.
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


# Every answer but O2, O3 and --moved-on-no-decision needs the item's `#case_against` line. Cases about something else use documents
# written without one; rated() gives each item opening in such a document a `#case_against none.` line.
# The walk-document holds five of the walk's items, numbered 3 to 7 under `of 9`; close counts M from the items it
# holds, so the `#next_to_present` lines close writes say `of 5`.
WALK_DOCUMENT_COUNTED_M = "5"
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

    def __init__(self, next_to_present="item 3 of 9", document=WALK_DOCUMENT, temporary_directory_name="tmp"):
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
        self.temporary_directory = self.root / temporary_directory_name
        self.temporary_directory.mkdir()
        self.gh = self.root / "gh-stand-in.py"
        self.gh.write_text(f"#!{sys.executable}\n" + GH_STAND_IN)
        self.gh.chmod(0o755)
        self.gh_calls = self.root / "gh-stand-in-calls.jsonl"
        self.gh_calls.write_text("")

    def gh_comments(self):
        """[(pull request number, body)] of each comment the gh stand-in was asked to post, in order."""
        calls = [json.loads(line) for line in self.gh_calls.read_text().splitlines()]
        return [(call[2], call[4]) for call in calls if call[:2] == ["pr", "comment"]]

    def reads(self):
        """The walk's directory of item cold-read-fast-read outcomes, keyed by a hash of each text read."""
        return self.checkout / "docs" / "walk" / f"{WALK_NAME}-item-cold-read-fast-read-review-status-per-text-hash"

    def wait_for_reads_ahead(self):
        """Wait until every read-ahead worker this case started has ended, so none writes after the case."""
        for started in self.reads().glob("*-started.json") if self.reads().is_dir() else []:
            pid = json.loads(started.read_text())["pid"]
            while True:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.05)

    def left_in_temporary_directory(self):
        return sorted(path.name for path in self.temporary_directory.iterdir())

    def record_holding(self, text, report_name="cold-read-fast-read.md", name=f"{WALK_NAME}-item-3-of-9-2026-10-15"):
        record = self.records / name
        (record / "target" / "docs" / "walk").mkdir(parents=True)
        (record / "target" / "docs" / "walk" / "item.md").write_text(f"Item 3 of 9\n\n#new \"{text}\"\n")
        (record / report_name).write_text("findings\n")
        return record

    def run(self, step, *flags, mode="", counts_log=None, fast_read_program=None, environment=None,
            ignored_signal=None, reply="a", wait_for_reads_ahead=True):
        """Run the program; a check gets `--user-reply-as-typed reply` unless reply is None or the flags
        hold --not-asked or a reply of their own. Unless told not to, wait for the reads ahead it started."""
        result = self.run_only(step, *flags, mode=mode, counts_log=counts_log, fast_read_program=fast_read_program,
                               environment=environment, ignored_signal=ignored_signal, reply=reply)
        if wait_for_reads_ahead:
            self.wait_for_reads_ahead()
        return result

    def run_only(self, step, *flags, mode, counts_log, fast_read_program, environment, ignored_signal, reply):
        if step == "check" and reply is not None and not {"--not-asked", "--already-decided", "--moved-on", "--user-reply-as-typed"} & set(flags):
            flags = (*flags, "--user-reply-as-typed", reply)
        environment = dict(environment or os.environ, STAND_IN_MODE=mode, STAND_IN_CALLS=str(self.calls),
                           STAND_IN_RECORDS=str(self.records), TMPDIR=str(self.temporary_directory),
                           GH_STAND_IN_CALLS=str(self.gh_calls))

        def stop_signal_dispositions():
            # Set explicitly: a child left to inherit would get SIG_IGN when this suite runs under nohup.
            for number in (signal.SIGTERM, signal.SIGHUP):
                signal.signal(number, signal.SIG_IGN if number == ignored_signal else signal.SIG_DFL)

        return subprocess.run(
            [sys.executable, str(PROGRAM), step, *flags, "--cwd", str(self.checkout),
             "--cold-read-records", str(self.records),
             "--fast-read-program", str(fast_read_program or self.stand_in),
             "--counts-log", str(counts_log or self.counts_log), "--gh-program", str(self.gh)],
            capture_output=True, text=True, env=environment, cwd=self.checkout,
            preexec_fn=stop_signal_dispositions)


def case_paths(case):
    """The flags Case.run adds, for running a command the program printed against this case."""
    return ["--cwd", str(case.checkout), "--cold-read-records", str(case.records),
            "--fast-read-program", str(case.stand_in), "--counts-log", str(case.counts_log)]


def outside_paths(text, case):
    """text with this checkout's and the case's paths removed, so that a word the program must not print
    is not found in a directory name, such as a worktree named for a flag. The case's temporary directory
    goes first: it lies inside case.root, and its own name can hold the word."""
    for path in (case.temporary_directory, case.root, Path(__file__).resolve().parents[4]):
        text = text.replace(str(path), "")
    return text


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
    check("a fenced line naming `#new` inside a sentence, or a #new line in another item, is not a proposed text",
          case.calls.read_text() == ("The page lists one poem per job an agent does.\n"
                                     "Each row names the mistake it prevents.\n"),
          repr(case.calls.read_text()))
    minutes = case.minutes.read_text()
    check("check records the answer as approved, and the status lines, in the minutes",
          re.search(r"\nitem 3 of 9: the user answered approved #case_against_weak \(\d{4}-\d\d-\d\d \d\d:\d\d\) in his words \"a\", which makes "
                    r"its change\. Fast reads:\n", minutes) is not None
          and minutes.count("\n- `#new` text ") == 2, minutes)
    log = case.counts_log.read_text().split("\t")
    check("check appends the counts", log[1:] == [WALK_NAME, "item 3 of 9", "texts=2",
                                                   "already_done=0", "had_to_be_run=2\n"], repr(log))
    again = case.run("check")
    check("a text the earlier check fast-read is already done the next time",
          again.returncode == 0 and again.stdout.count("fast read already done") == 2
          and "Read each fast-read report" not in again.stdout, described(again))
    check("check removes the scratch directory of each cold-read-fast-read it ran",
          not case.left_in_temporary_directory(), case.left_in_temporary_directory())


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


def test_another_walks_record_holding_the_text_is_not_opened():
    case = Case()
    for name in ("earlier-read-2026-10-15", f"{WALK_NAME}0-item-3-of-9-2026-10-15"):
        case.record_holding("The page lists one poem\n per job an agent does.", name=name)
    result = case.run("check")
    check("a record whose name does not start with the walk's name and a hyphen is not searched, so its text is "
          "fast-read again",
          result.returncode == 0
          and '"The page lists one poem per job an agent does.": fast read had to be run' in result.stdout
          and "The page lists one poem per job an agent does." in case.calls.read_text(),
          described(result))


def test_a_fast_read_already_done_before_the_cold_read_prefix_is_not_run_again():
    case = Case()
    record = case.record_holding("The page lists one poem\n per job an agent does.", report_name="fast-read.md")
    result = case.run("check")
    check("a record written before the cold-read- prefix, holding fast-read.md, counts as done",
          result.returncode == 0
          and f'"The page lists one poem per job an agent does.": fast read already done ({record}).'
          in result.stdout,
          described(result))


def test_a_record_holding_no_report_is_not_a_fast_read_done():
    case = Case()
    case.record_holding("The page lists one poem\n per job an agent does.", report_name="notes-of-a-read.md")
    result = case.run("check")
    check("a record whose target holds the text but which holds no report under either name is not done",
          "The page lists one poem per job an agent does.\": fast read already done" not in result.stdout,
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


def marks_document(body):
    """A walk-document whose item 3 holds body from its line 5 on."""
    return f"# A walk\n\n## Item 3 of 9: the opening sentence\n\n{body}\n#case_against weak: the page grows.\n\nRecommendation: change it.\n"


UNREADABLE_MARK_CASES = (
    ("a mark with no text", "#new\n\nThe sentence stays.\n",
     ["- line 5: `#new` has no text after it on its line."]),
    ("a mark with an empty quotation", '#new ""\n',
     ["- line 5: `#new` has no text after it on its line."]),
    ("a `#new_if_d` mark with no text, on an A answer", "#new_if_d\n\n> A note\n> says why.\n\nThe end.\n",
     ["- line 5: `#new_if_d` has no text after it on its line. The mark's line with its text joined onto it: "
      "#new_if_d A note says why."]),
    ("a mark with no text above a fenced block", "#new\n\n```\nThe page lists\none poem.\n```\n",
     ["- line 5: `#new` has no text after it on its line. The mark's line with its text joined onto it: "
      "#new The page lists one poem."]),
    ("a mark with no text whose text runs on right below it", '#new\n"The page lists\none poem."\n',
     ["- line 5: `#new` has no text after it on its line. The mark's line with its text joined onto it: "
      '#new "The page lists one poem."']),
    ("a mark inside fenced code", 'Before.\n\n```\n#new "The page lists\none poem."\n```\n',
     ["- line 8: `#new` is inside fenced or indented code, where no mark's text is read. The mark's line with its text joined onto "
      'it: #new "The page lists one poem."']),
    ("a mark inside indented code", 'Before.\n\n    #new "The page lists one poem."\n',
     ["- line 7: `#new` is inside fenced or indented code, where no mark's text is read. The mark's line with its text joined onto "
      'it: #new "The page lists one poem."']),
    ("a mark whose text runs onto the lines below it", '#new "The page lists\none poem\nper job."\n',
     ["- line 5: the text of `#new` runs onto lines 6 to 7 right below it, where it is not read. The mark's line "
      'with its text joined onto it: #new "The page lists one poem per job."']),
    ("a mark in a quotation whose text runs onto the line below it", '> #new "The page lists\n> one poem."\n',
     ["- line 5: the text of `#new` runs onto line 6 right below it, where it is not read. The mark's line with "
      'its text joined onto it: #new "The page lists one poem."']),
    ("two marks, each listed", '#new\n\n#new "The page lists\none poem."\n',
     ["- line 5: `#new` has no text after it on its line.",
      "- line 7: the text of `#new` runs onto line 8 right below it, where it is not read. The mark's line with "
      'its text joined onto it: #new "The page lists one poem."']),
    ("a mark whose text runs onto prose, with another mark right below that",
     '#new "The page lists\none poem."\n#new "Row two."\n',
     ["- line 5: the text of `#new` runs onto line 6 right below it, where it is not read. The mark's line with "
      'its text joined onto it: #new "The page lists one poem."']),
    ("a mark whose text runs onto a line that opens with a hashtag in a code span",
     '#new "Use\n`#new` to mark proposed text."\n',
     ["- line 5: the text of `#new` runs onto line 6 right below it, where it is not read. The mark's line with "
      'its text joined onto it: #new "Use `#new` to mark proposed text."']),
    ("a mark whose text runs onto a line that opens with a hashtag this program does not read",
     '#new "The rule asks for\n#root_cause lines in each description."\n',
     ["- line 5: the text of `#new` runs onto line 6 right below it, where it is not read. The mark's line with "
      'its text joined onto it: #new "The rule asks for #root_cause lines in each description."']),
)


def test_a_mark_whose_text_would_not_be_read_whole_is_refused_by_check_writing_nothing():
    for name, body, problem_lines in UNREADABLE_MARK_CASES:
        case = Case(document=marks_document(body))
        before = case.minutes.read_text()
        result = case.run("check", "--obvious")
        lines = result.stderr.rstrip("\n").split("\n")
        check(f"check refuses {name}, listing each mark by its line, and writes nothing",
              result.returncode == 1 and result.stdout == ""
              and lines[0].startswith(FAILURE_PREFIX + "check: nothing written: item 3 of 9 in the walk-document ")
              and [line for line in lines if line.startswith("- line ")] == problem_lines
              and f"Then run `python3 {PROGRAM} check --obvious --user-reply-as-typed a` again." in lines
              and "Fix the marks from the last listed to the first, so that the line numbers above stay right." in lines
              and case.minutes.read_text() == before and case.calls.read_text() == ""
              and not case.counts_log.exists(), described(result))


def test_a_mark_whose_text_would_not_be_read_whole_is_refused_for_every_answer_that_adds_texts():
    for flags in (("--disapproved",), ("--already-decided", "ruling of 2026-10-01"), ("--not-asked", "5")):
        case = Case(document=marks_document("#new_if_d\n"))
        before = case.minutes.read_text()
        result = case.run("check", *flags)
        check(f"check {flags[0]} refuses an item with a mark that has no text, writing nothing",
              result.returncode == 1 and "- line 5: `#new_if_d` has no text after it on its line." in result.stderr
              and case.minutes.read_text() == before, described(result))
    for flags in (("--deferred",), ("--moved-on-no-decision",), ("--moved-on", "no decision needed")):
        case = Case(document=marks_document("#new\n"))
        result = case.run("check", *flags)
        check(f"check {flags[0]}, which adds no text, records the answer to an item with a mark that has no text",
              result.returncode == 0 and "item 3 of 9: " in case.minutes.read_text(), described(result))


def test_marks_whose_texts_are_read_whole_are_not_refused():
    body = ('- #new "Row one."\n- #new "Row two."\n\n> #new "A quoted row."\n\n'
            '<!--\n#new\n-->\n\n```\nExample: #new "a fenced example"\n```\n\n#new "The last row."\n```\ncode right below\n```\n')
    case = Case(document=marks_document(body))
    result = case.run("check")
    check("marks in list items one under another, in a quotation, in an HTML comment, not opening a fenced line, or "
          "right above a fence "
          "are not refused, and each text is read",
          result.returncode == 0
          and case.calls.read_text() == "Row one.\nRow two.\nA quoted row.\nThe last row.\n", described(result))
    case = Case(document=marks_document('#new "Row one."\n#new_if_d "Row two."\n#new "Row three."\n'
                                        '**#case_against none.**\n'))
    result = case.run("check")
    check("marks one under another with no blank line or list marker between them, and a marker line right below "
          "the last, are not refused, and each mark's line is read on its own",
          result.returncode == 0 and case.calls.read_text() == "Row one.\nRow three.\n", described(result))
    case = Case(document=marks_document('#new "Row one."\n`#case_against weak`: the fix costs an hour.\n'))
    result = case.run("check")
    check("a mark with a backticked `#case_against` line right below it is not refused, and its own line is read",
          result.returncode == 0 and case.calls.read_text() == "Row one.\n", described(result))
    for body, read in (("#new > Keep the old logs.\n", "> Keep the old logs.\n"), ("#new >\n", ">\n")):
        case = Case(document=marks_document(body))
        result = case.run("check")
        check(f"a mark whose text opens with `>` keeps the `>` in the text it reads: {body!r}",
              result.returncode == 0 and case.calls.read_text() == read, described(result))


def test_the_waiting_item_read_step_refuses_a_mark_whose_text_would_not_be_read_whole():
    case = Case(document=marks_document('#new "The page lists\none poem."\n'))
    result = case.run(WAITING_ITEM_READ_STEP_NAME)
    command = (f"python3 {PROGRAM} {WAITING_ITEM_READ_STEP_NAME} --after-fixes-reread-only-when-facts-change "
               f"--cwd {shlex.quote(str(case.checkout.resolve()))}")
    check("the waiting-item read step refuses a mark whose text runs on, before any read, and names itself to rerun",
          result.returncode == 1
          and "- line 5: the text of `#new` runs onto line 6 right below it, where it is not read." in result.stderr
          and f"Then run `{command}` again." in result.stderr
          and case.calls.read_text() == "" and not case.reads().exists(), described(result))
    document = case.checkout / "docs" / "walk" / f"{WALK_NAME}.md"
    document.write_text(document.read_text().replace('#new "The page lists\none poem."', '#new "The page lists one poem."'))
    again = case.run(*shlex.split(command)[2:-2])
    check("after the mark's text is joined onto its line, the command the refusal gave reads the item",
          again.returncode == 0 and "its cold-read-fast-read, of its text as it stands, had to be run now"
          in again.stdout, described(again))


def test_a_failed_fast_read_stops_the_check():
    case = Case()
    before = case.minutes.read_text()
    result = case.run("check", "--obvious", mode="failed")
    check("a FAILED fast read is printed as it is, with exit 1",
          result.returncode == 1
          and result.stdout.split("\n")[0] == "FAILED: the stand-in cold-read-cell failed twice"
          and "The item stays waiting" in result.stdout
          and "close.py check --obvious --user-reply-as-typed a` again" in result.stdout, described(result))
    check("after a FAILED fast read the minutes do not record the answer", case.minutes.read_text() == before,
          case.minutes.read_text())
    check("after a FAILED fast read the scratch directory is removed",
          not case.left_in_temporary_directory(), case.left_in_temporary_directory())
    for flags in (("--after-advisor",), ("--disapproved",), ("--option", "2"), ("--part-answer", "1=A", "--part-answer", "2=D")):
        case = Case()
        result = case.run("check", *flags, mode="failed")
        check(f"after a FAILED fast read, the rerun command keeps {' '.join(flags)}",
              result.returncode == 1 and f"close.py check {' '.join(flags)} --user-reply-as-typed a` again" in result.stdout,
              described(result))


def test_a_fast_read_that_exits_nonzero_without_a_line_is_a_failure():
    case = Case()
    result = case.run("check", mode="silent-exit")
    check("a fast read that exits nonzero and prints nothing is reported as FAILED",
          result.returncode == 1 and result.stdout.startswith("FAILED: ") and "exited 3" in result.stdout,
          described(result))
    check("after a fast read that exits nonzero the scratch directory is removed",
          not case.left_in_temporary_directory(), case.left_in_temporary_directory())


def test_a_check_stopped_by_sigterm_or_sighup_removes_its_scratch_directory_and_ends_as_the_signal_does():
    for number in (signal.SIGTERM, signal.SIGHUP):
        case = Case()
        before = case.minutes.read_text()
        result = case.run("check", mode=f"stopped {number.name}")
        check(f"a {number.name} during a cold-read-fast-read ends the check as {number.name} does, and the minutes "
              f"stay as they were",
              result.returncode == -number and case.minutes.read_text() == before, described(result))
        check(f"a {number.name} during a cold-read-fast-read removes the scratch directory",
              not case.left_in_temporary_directory(), case.left_in_temporary_directory())


def test_a_check_started_with_a_stop_signal_ignored_keeps_ignoring_it():
    for number in (signal.SIGTERM, signal.SIGHUP):
        case = Case()
        result = case.run("check", mode=f"signalled-then-reports {number.name}", ignored_signal=number)
        check(f"a check started with {number.name} ignored, as under nohup, is not ended by a {number.name} during "
              f"its cold-read-fast-read, and records the answer",
              result.returncode == 0 and "the user answered approved" in case.minutes.read_text()
              and not case.left_in_temporary_directory(), described(result))


def test_a_scratch_directory_a_stop_signal_cannot_remove_is_reported_with_the_command_that_removes_it():
    for number in (signal.SIGTERM, signal.SIGHUP):
        # A space in the path shows the command quotes the directory; the word "flag" in it shows the
        # check below for that word ignores paths.
        case = Case(temporary_directory_name="scratch flag root")
        result = case.run("check", mode=f"stopped-unremovable {number.name}")
        left = [case.temporary_directory / name for name in case.left_in_temporary_directory()]
        command = re.search(r"Run `(.+?)`", result.stderr)
        check(f"a scratch directory a {number.name} cannot remove is named, with the command that removes it, "
              f"and the check still ends as {number.name} does",
              result.returncode == -number and len(left) == 1 and command is not None
              and f"a {number.name} stopped this check step" in result.stderr
              and f"the scratch directory {left[0]}, which held the text" in result.stderr
              and f"Then run the same `python3 {shlex.quote(str(PROGRAM))} check` command again, with the same "
                  f"answer" in result.stderr,
              described(result))
        check(f"the {number.name} message names no answer's flags, and gives a reason for the removal that "
              f"holds wherever TMPDIR points",
              "flag" not in outside_paths(result.stderr, case) and "/tmp has a quota" not in result.stderr
              and "the disk it is on can fill" in result.stderr,
              described(result))
        removal = subprocess.run(["sh", "-c", command.group(1) if command else "false"], capture_output=True,
                                 text=True)
        check(f"the command the {number.name} message gives, run as printed, removes the scratch directory it "
              f"left unremovable",
              removal.returncode == 0 and not case.left_in_temporary_directory(),
              f"exit {removal.returncode}, stderr {removal.stderr!r}, left {case.left_in_temporary_directory()}")
        for directory in left:
            if (directory / "locked").exists():
                (directory / "locked").chmod(0o700)  # Else the suite's own removal leaves it behind.


def test_a_fast_read_that_raises_partway_leaves_no_scratch_directory_and_restores_the_stop_signal_handlers():
    program = load_program()
    case = Case()

    def raising_run(*_, **__):
        raise RuntimeError("raised partway, while the fast read ran")

    program.subprocess = types.SimpleNamespace(run=raising_run)
    before_handlers = [signal.getsignal(number) for number in (signal.SIGTERM, signal.SIGHUP)]
    saved_tempdir, tempfile.tempdir = tempfile.tempdir, str(case.temporary_directory)
    try:
        program.run_fast_read("A text.", "a-name", case.stand_in)
        raised = None
    except RuntimeError as error:
        raised = error
    finally:
        tempfile.tempdir = saved_tempdir
    check("a fast read that raises partway leaves no scratch directory, and the error reaches the caller",
          raised is not None and not case.left_in_temporary_directory(),
          f"raised {raised!r}; left {case.left_in_temporary_directory()}")
    after_handlers = [signal.getsignal(number) for number in (signal.SIGTERM, signal.SIGHUP)]
    check("run_fast_read puts back the SIGTERM and SIGHUP handlers its caller had",
          all(after is before for after, before in zip(after_handlers, before_handlers)), after_handlers)


def test_a_stop_signal_right_after_the_scratch_directory_is_made_removes_it():
    """The signal cannot be timed into that window from outside, so a stand-in mkdtemp sends it to its own
    process right after making the directory, in a forked child, since the signal ends that process."""
    program = load_program()
    case = Case()

    def mkdtemp_then_stopped(**keywords):
        directory = tempfile.mkdtemp(dir=case.temporary_directory, **keywords)
        os.kill(os.getpid(), signal.SIGTERM)
        return directory

    child = os.fork()
    if child == 0:
        try:
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
            program.tempfile = types.SimpleNamespace(mkdtemp=mkdtemp_then_stopped)
            with program.scratch_directory_removed_on_every_exit():
                pass
        finally:
            os._exit(0)
    _, status = os.waitpid(child, 0)
    check("a SIGTERM right after the scratch directory is made, before it is registered for removal, removes it "
          "and ends the process as SIGTERM does",
          os.WIFSIGNALED(status) and os.WTERMSIG(status) == signal.SIGTERM
          and not case.left_in_temporary_directory(), f"status {status}, left {case.left_in_temporary_directory()}")


def test_the_check_command_a_stop_signal_message_gives_quotes_the_programs_path():
    """The program's real path holds no character a shell splits on, so a forked child gives the loaded program a
    path with a space, and a removal that fails, then sends itself SIGTERM."""
    program = load_program()
    program.__file__ = str(SUITE_ROOT / "a checkout" / PROGRAM.name)
    case = Case()

    def rmtree_failing(_):
        raise OSError("Permission denied")

    read_end, write_end = os.pipe()
    child = os.fork()
    if child == 0:
        try:
            os.dup2(write_end, 2)
            tempfile.tempdir = str(case.temporary_directory)
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
            program.shutil = types.SimpleNamespace(rmtree=rmtree_failing)
            with program.scratch_directory_removed_on_every_exit():
                os.kill(os.getpid(), signal.SIGTERM)
        finally:
            os._exit(0)
    os.close(write_end)
    with os.fdopen(read_end) as stderr:
        message = stderr.read()
    os.waitpid(child, 0)
    check("the check command a stop signal's message gives names the program's path quoted for the shell",
          f"Then run the same `python3 {shlex.quote(program.__file__)} check` command again" in message, message)


def test_a_scratch_directory_that_cannot_be_made_leaves_the_stop_signals_unblocked_and_their_handlers_restored():
    program = load_program()

    def mkdtemp_failing(**_):
        raise OSError("Disk quota exceeded")

    program.tempfile = types.SimpleNamespace(mkdtemp=mkdtemp_failing)
    before_handlers = [signal.getsignal(number) for number in (signal.SIGTERM, signal.SIGHUP)]
    try:
        with program.scratch_directory_removed_on_every_exit():
            pass
        raised = None
    except OSError as error:
        raised = error
    blocked = signal.pthread_sigmask(signal.SIG_BLOCK, [])
    after_handlers = [signal.getsignal(number) for number in (signal.SIGTERM, signal.SIGHUP)]
    check("a scratch directory that cannot be made raises to the caller, leaves SIGTERM and SIGHUP unblocked, and "
          "puts back the handlers its caller had",
          raised is not None and signal.SIGTERM not in blocked and signal.SIGHUP not in blocked
          and all(after is before for after, before in zip(after_handlers, before_handlers)),
          f"raised {raised!r}, blocked {blocked}, handlers {after_handlers}")


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


def test_a_fast_read_that_names_a_report_and_exits_1_without_a_record_line_is_a_failure():
    case = Case()
    before = case.minutes.read_text()
    result = case.run("check", mode="path-then-exit-1")
    check("a fast read that names a report and exits 1 with no record line on stderr is reported as FAILED",
          result.returncode == 1 and result.stdout.startswith("FAILED: ") and "exited 1" in result.stdout
          and case.minutes.read_text() == before, described(result))


def test_a_record_line_does_not_excuse_an_exit_other_than_1():
    for mode, exit_code in (("record-not-shipped-then-exit-4", 4), ("record-not-shipped-then-killed", -15)):
        case = Case()
        before = case.minutes.read_text()
        result = case.run("check", mode=mode)
        check(f"a fast read that did not ship its record but exits {exit_code} is reported as FAILED",
              result.returncode == 1 and result.stdout.startswith("FAILED: ")
              and f"exited {exit_code} " in result.stdout
              and "its stderr: cold-read-fast-read: record: FAILED: ned-box could not be reached" in result.stdout
              and case.minutes.read_text() == before, described(result))


def test_a_fast_read_whose_record_was_refused_is_used_and_reported():
    case = Case()
    result = case.run("check", mode="record-refused")
    note = "cold-read-fast-read: record: REFUSED: already in the store with different content."
    check("a fast read that exits 1 because the store refused its record is used, and the refusal reported, "
          "with exit 2",
          result.returncode == 2
          and result.stdout.split("\n")[0].endswith(f"The fast read also said: {note}")
          and "did not ship its record: " + note in result.stdout
          and "with a -2 suffix" in result.stdout
          and "the user answered approved" in case.minutes.read_text(), described(result))


def test_the_real_fast_read_whose_record_did_not_ship_is_used():
    case = Case()
    fast_read_program, environment = (
        cold_read_scratch_fixture.cold_read_fast_read_scratch_repository_whose_stub_agy_answers_in_chat(
            case.root, "nobody@no-such-host.invalid:/tmp/no-store"))
    result = case.run("check", fast_read_program=fast_read_program, environment=environment)
    records = fast_read_program.parents[2] / "cold-read-records"
    check("the real fast read, exiting 1 because its record could not reach the log-store, is used: the item's "
          "answer is recorded, each status line names its report, and the record line is reported, with exit 2",
          result.returncode == 2
          and result.stdout.count(f"fast read had to be run ({records}/") == 2
          and result.stdout.count("did not ship its record: cold-read-fast-read: record: FAILED: ") == 2
          and "the user answered approved" in case.minutes.read_text()
          and len(list(records.glob("*/cold-read-fast-read.md"))) == 2, described(result))


def test_a_fast_read_whose_record_was_not_shipped_is_reported():
    case = Case()
    result = case.run("check", mode="record-not-shipped")
    note = ("cold-read-fast-read: record: FAILED: ned-box could not be reached (ssh exit 255); the record stays "
            "on disk.")
    check("a fast read that exits 1 because it did not ship its record is used, and has its line in the status "
          "line, in the minutes, and in what to do, with exit 2",
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


def read_next_item_line(case, item):
    """The last line close prints when it names the next item."""
    return (f"Then run `python3 {PROGRAM} approval-walk-waiting-item-cold-read-fast-read --cwd {shlex.quote(str(case.checkout.resolve()))}`, "
            f"which gives {item}, the item the minutes' `#next_to_present` line now names, its cold-read-fast-read, "
            "and do what it prints before you present it.")


def took_effect_next(case):
    return [
        "If the change needs nothing more from the user, such as a text he has not yet seen, start it as the "
        "walk-me-through skill's sentence on ready work says; if it edits a file that work you dispatched "
        "earlier is still editing, start it when that earlier work finishes.",
        read_next_item_line(case, f"item 6 of {WALK_DOCUMENT_COUNTED_M}")]


def test_close_records_that_the_answer_took_effect():
    case = Case(next_to_present="item 4 of 9")
    case.run("check")
    result = case.run("close")
    check("close records an approval that took effect, repeats the status lines, and says to start ready work",
          result.returncode == 0
          and result.stdout.rstrip("\n").split("\n") == [
              "item 4 of 9's answer is recorded in the minutes, and its change may now be made.",
              "Your next message must include these lines, as they are:",
              "no proposed text marked"] + took_effect_next(case)
          and case.minutes.read_text().rstrip().endswith(
              "item 4 of 9: approved; every text the change adds has had a fast read. <accepted>\n"
              f"#next_to_present item 6 of {WALK_DOCUMENT_COUNTED_M}"),
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
              and minutes.rstrip().endswith(last + f"\n#next_to_present item 6 of {WALK_DOCUMENT_COUNTED_M}"), described(checked) + described(closed) + minutes)


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


def test_a_withdrawn_version_below_the_item_adds_no_text():
    document = WALK_DOCUMENT.replace(
        "## Item 4 of 9: no proposal here\n",
        "#### Withdrawn version 1 of item 3\n\n#new \"The first draft's sentence.\"\n\n"
        "Recommendation: keep the first draft.\n\n## Item 4 of 9: no proposal here\n")
    case = Case(document=document)
    result = case.run("check")
    check("a #new line under a Withdrawn heading below the waiting item is not one of its proposed texts",
          result.returncode == 0 and case.calls.read_text() == NEW_TEXTS, described(result))


def test_a_withdrawn_version_under_a_shared_heading_ends_only_its_own_item():
    document = WALK_DOCUMENT.replace(
        "Item 7 of 9 drops a sentence.\n",
        "#### Withdrawn version 1 of item 6\n\n#new \"The path was docs/.\"\n\nItem 7 of 9 drops a sentence.\n")
    for number, texts in (("6", "The path is docs/walk/.\n"), ("7", "Item seven's text.\n")):
        case = Case(next_to_present=f"item {number} of 9", document=document)
        result = case.run("check")
        check(f"under a shared heading, a Withdrawn version of item 6 ends only item 6, so item {number} reads its own "
              "#new lines and not the withdrawn one",
              result.returncode == 0 and case.calls.read_text() == texts, described(result))


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
                        recorded=approved_line("item 1 of 5") + "```\n" + approved_line("item 3 of 5") + "```\n")
    case.run("check")
    closed = case.run("close")
    check("a line close writes, inside a fence in the minutes, decides nothing, so the item it names comes next",
          closed.returncode == 0 and marker(case) == "#next_to_present item 3 of 5",
          described(closed) + case.minutes.read_text())
    case = Case(next_to_present="item 4 of 9")
    case.run("check")
    with case.minutes.open("a") as minutes:
        minutes.write("```\nitem 5 of 9: the user answered disapproved (2026-10-23 10:00), which makes no change.\n```\n")
    closed = case.run("close")
    check("an answer line inside a fence in the minutes is not the last answer, so close records the real one",
          closed.returncode == 0 and closed.stdout.startswith("item 4 of 9's answer is recorded in the minutes")
          and marker(case) == f"#next_to_present item 6 of {WALK_DOCUMENT_COUNTED_M}", described(closed))


def test_a_marker_inside_code_in_the_minutes_is_not_the_last_marker():
    case = Case(next_to_present="item 4 of 9")
    with case.minutes.open("a") as minutes:
        minutes.write("```\n#next_to_present item 3 of 9\n```\n")
    result = case.run("check")
    check("a `#next_to_present` line inside a fence after the real one is not read, so check answers the real item",
          result.returncode == 0 and case.calls.read_text() == ""
          and "\nitem 4 of 9: the user answered approved #case_against_none (" in case.minutes.read_text(), described(result))


def test_lines_inside_an_html_comment_in_the_minutes_record_nothing():
    case = summary_case(next_to_present="item 2 of 5",
                        recorded=approved_line("item 1 of 5") + "<!-- A note, not presented:\n"
                                 + approved_line("item 3 of 5") + "-->\n")
    case.run("check")
    closed = case.run("close")
    check("a line close writes, inside an HTML comment in the minutes, decides nothing, so the item it names "
          "comes next",
          closed.returncode == 0 and marker(case) == "#next_to_present item 3 of 5",
          described(closed) + case.minutes.read_text())
    case = Case(next_to_present="item 4 of 9")
    with case.minutes.open("a") as minutes:
        minutes.write("<!-- an older marker:\n#next_to_present item 3 of 9\n-->\n")
    result = case.run("check")
    check("a `#next_to_present` line inside an HTML comment is not read, so check answers the real item",
          result.returncode == 0 and "\nitem 4 of 9: the user answered approved #case_against_none (" in case.minutes.read_text(),
          described(result))


def test_only_a_line_the_program_writes_records_a_decision_or_a_deferral():
    program = load_program()
    walk_finder = program.load_walk_finder()
    parser = walk_finder.markdown_parser()
    for line, expected, case_name in (
            ("Item 2 of 5: approved. <accepted>\n", (set(), {}),
             "a hand-written line whose first word is approved, with <accepted>, records nothing"),
            ("Item 2 of 5: deferred until Friday.\n", (set(), {}),
             "a hand-written line whose first word is deferred records nothing"),
            ("- 2026-10-22 00:40 Item 2 <rejected> (D).\n", (set(), {}),
             "a hand-written line with a timestamp and <rejected> records nothing"),
            ("item 6 of 29: approved without asking: already decided by the user's ruling recorded in GHI 783's "
             "GHI-MD; no case against; not asked. <accepted>\n", (set(), {}),
             "a hand-written approved-without-asking line records nothing"),
            ("item 5.1 of 29: moved on, no decision: the question went to another walk. <moved on, no decision>\n",
             (set(), {}), "a hand-written moved-on line records nothing"),
            ("item 2 of 5: the user answered approved (2026-10-23 10:00), which makes its change. Fast reads:\n",
             (set(), {}), "check's answer line records nothing"),
            ("item 2 of 5: answer held: item 2.1 of 5, raised by a fast-read finding, waits for the user's answer. "
             "<open>\n", (set(), {}), "close's held-answer line records nothing"),
            ("item 2 of 5: approved; every text the change adds has had a fast read. <accepted>\n", ({"2"}, {}),
             "close's line for an approval that took effect decides its item"),
            ("items 3 to 4 of 5: disapproved; every text the change adds has had a fast read. <rejected>\n",
             ({"3", "4"}, {}), "close's line for a disapproval decides every item it names"),
            ("item 2 of 5: part 1 approved <accepted>, part 2 disapproved <rejected>; every text the change adds "
             "has had a fast read.\n", ({"2"}, {}), "close's line for answers to parts decides its item"),
            ("item 2 of 5: deferred; it moves to just before the summary item. <open>\n", (set(), {"2": 1}),
             "close's line for a deferral defers its item once"),
            ("item 2 of 5: deferred a second time, so it leaves the walk and stays open. <open>\n",
             (set(), {"2": 1}), "close's line for a second deferral defers its item once more"),
            ("item 2 of 5: already decided by walk x, item 3; the walk does not come back to it. <rejected>\n",
             ({"2"}, {}), "close's line for an item an earlier user-ruling decides decides it"),
            ("item 2 of 5: moved on, no decision: it went to walk y; the walk does not come back to it. "
             "<moved on, no decision>\n", ({"2"}, {}), "close's line for an item moved on from decides it"),
            ("item 2 of 5: not asked, kind 1; every text the change adds has had a fast read. <accepted>\n",
             ({"2"}, {}), "the line close writes for an item settled under PR 2042's --not-asked decides it"),
            ("item 2 of 5: settled without asking the user, moved on, no decision: x (2026-10-29 10:00), which "
             "makes no change.\n", (set(), {}), "check's answer line for a move on records nothing"),
            ("Items 4 to 2 of 5: approved; every text the change adds has had a fast read. <accepted>\n",
             (set(), {}), "a close-form line naming a backwards range records nothing"),
            ("item 3 of 9: deferred; it moves to just before the summary item. <open> later he approved it\n",
             (set(), {}), "close's deferral line with words after its end records nothing"),
            ("item 3 of 9: part 1 approved <accepted>; every text the change adds has had a fast read.(later revised)\n",
             (set(), {}), "close's parts line with words after its end records nothing"),
            ("item 3 of 9: moved on; the item asked for no decision. <moved on, no decision> but he asked again\n",
             (set(), {}), "close's moved-on line with words after its end records nothing"),
            ("item 3 of 9: revised; every text the change adds has had a fast read. Awaiting his ruling.\n",
             (set(), {}), "a line in close's took-effect form with an answer and an outcome close never writes "
                          "records nothing"),
            ("item 3 of 9: approved; every text the change adds has had a fast read. <open>\n",
             (set(), {}), "close's took-effect form with an outcome close never writes records nothing"),
            ("item 3 of 9: part 1 revised, part 2 approved <accepted>; every text the change adds has had a fast "
             "read.\n", (set(), {}), "close's parts form with a part word close never writes records nothing"),
            ("item 3 of 9: already decided by walk x, item 3; the walk does not come back to it. <awaiting>\n",
             (set(), {}), "close's already-decided form with an outcome close never writes records nothing"),
            ("item 3 of 9: approved option 2; every text the change adds has had a fast read. <accepted>\n",
             ({"3"}, {}), "close's line for an option approval decides its item"),
            ("item 3 of 9: approved option 9; every text the change adds has had a fast read. <accepted>\n",
             (set(), {}), "close's took-effect form with an option --option never accepts records nothing"),
            ("item 3 of 9: not asked, kind 6; every text the change adds has had a fast read. <accepted>\n",
             ({"3"}, {}), "the line close writes for an item settled as kind 6 decides it"),
            ("item 3 of 9: not asked, kind 7; every text the change adds has had a fast read. <accepted>\n",
             (set(), {}), "close's took-effect form with a kind --not-asked never accepts records nothing"),
            ("item 3 of 9: part 1 approved <rejected>; every text the change adds has had a fast read.\n",
             (set(), {}), "close's parts form pairing a part's answer with the other answer's outcome records "
                          "nothing"),
            ("item 3 of 9: part 1 disapproved <rejected>, part 2 approved <accepted>; every text the change adds "
             "has had a fast read.\n", ({"3"}, {}), "close's parts line with each answer's own outcome decides "
                                                   "its item")):
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
          and lines[-1] == (f"Then run `python3 {PROGRAM} approval-walk-waiting-item-cold-read-fast-read --cwd "
                            f"{shlex.quote(str(case.checkout.resolve()))}`, which gives item 5 of 9 its "
                            "cold-read-fast-read, do what it prints, and present item 5 of 9. When the close step records the user's approval or disapproval "
                            "of item 5 of 9, it records the same outcome for item 3 of 9; after a deferral, a move on "
                            "or answers to parts, item 3 of 9 stays waiting and the walk comes back to it.")
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
    failed_check = case.run("check", "--option", "5")
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
          result.returncode == 1 and result.stderr.startswith(FAILURE_PREFIX + "check: ") and "no approval-walk is open" in result.stderr
          and "paused" not in outside_paths(result.stderr, case), described(result))
    case = Case(next_to_present="item 4 of 9")
    with open(case.minutes, "a") as minutes:
        minutes.write("#approval_walk_paused the user's stop order\n")
    before = case.minutes.read_bytes()
    result = case.run("check")
    check("check on a paused approval-walk fails, writing nothing, and names its minutes and the line that resumes it",
          result.returncode == 1 and f"minutes are {case.minutes} is paused" in result.stderr
          and "\n#next_to_present item 4 of 9\n" in result.stderr and "no approval-walk is open" not in result.stderr
          and case.minutes.read_bytes() == before, described(result))
    case = Case(next_to_present="item 2 of 9 #approval_walk_paused the user's stop order")
    result = case.run("check")
    check("check on a walk paused on its marker's own line prints a resume line without the pause",
          result.returncode == 1 and "\n#next_to_present item 2 of 9\n" in result.stderr, described(result))
    printed_resume_line = next((line for line in result.stderr.splitlines() if line.startswith("#next_to_present")), "")
    with open(case.minutes, "a") as minutes:
        minutes.write(printed_resume_line + "\n")
    result = case.run("check")
    check("appending the printed resume line resumes the walk",
          printed_resume_line and "is paused" not in result.stderr, described(result))
    case = Case(next_to_present="item 8 of 9")
    result = case.run("check")
    check("check on an item the walk-document lacks fails on stderr",
          result.returncode == 1 and result.stderr.startswith(FAILURE_PREFIX + "check: ") and "has no heading `Item 8`, which the minutes name" in result.stderr, described(result))
    case = Case(next_to_present="items 6 to 4 of 9")
    result = case.run("check")
    check("check on a backwards range fails on stderr",
          result.returncode == 1 and result.stderr.startswith(FAILURE_PREFIX + "check: ") and "runs backwards" in result.stderr, described(result))


def test_two_unclosed_approval_walks_are_refused_naming_both_and_writing_nothing():
    for second_marker, kind in (("item 5 of 9", "open"), ("item 5 of 9\n#approval_walk_paused stop order", "paused")):
        case = Case()
        second = case.minutes.with_name("an-older-walk-minutes.md")
        second.write_text(f"# Minutes\n\n#next_to_present {second_marker}\n")
        # The older modification time is the one the program used to pass over; no walk is guessed now.
        os.utime(second, (1_000, 1_000))
        before = {path: path.read_bytes() for path in (case.minutes, second)}
        for step in ("check", "close", "approval-walk-waiting-item-cold-read-fast-read"):
            result = case.run(step)
            check(f"{step} with a second, {kind} approval-walk fails, naming both walk-minutes, and writes nothing",
                  result.returncode == 1 and result.stderr.startswith(FAILURE_PREFIX + step + ": nothing written: ")
                  and f"  {case.minutes}\n" in result.stderr and f"  {second}\n" in result.stderr
                  and "#next_to_present none, closed" in result.stderr
                  and {path: path.read_bytes() for path in before} == before
                  and case.calls.read_text() == "", described(result))
    case = Case()
    case.minutes.with_name("a-closed-walk-minutes.md").write_text("#next_to_present none, closed.\n")
    result = case.run("check")
    check("a closed approval-walk beside the open one is not counted",
          "more than one approval-walk" not in result.stderr and result.returncode == 0, described(result))


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


def approved_line(item):
    """The line close writes for an approval of item that took effect."""
    return f"{item}: approved; every text the change adds has had a fast read. <accepted>\n"


UNDO_COMMITTED_CHANGE_LINE = ("If a commit on your branch already makes the change this item asks about, undo that "
                              "change in a new commit before the pull request, and say in the task that it was undone.")


def test_a_deferral_is_recorded_and_the_item_comes_back_before_the_summary_item():
    case = summary_case(next_to_present="item 2 of 5", recorded=approved_line("item 1 of 5"))
    checked = case.run("check", "--deferred")
    check("check --deferred runs no fast read, logs no counts, and writes the no-change answer line",
          checked.returncode == 0 and case.calls.read_text() == "" and not case.counts_log.exists()
          and re.search(r"\nitem 2 of 5: the user answered deferred #case_against_none \(\d{4}-\d\d-\d\d \d\d:\d\d\) in his words \"a\", which makes no "
                        r"change\.\n$", case.minutes.read_text()) is not None
          and checked.stdout.rstrip().endswith(f"close --cwd {shlex.quote(str(case.checkout.resolve()))}` and do what "
                                               "it prints."), described(checked))
    closed = case.run("close")
    check("close records a deferral as open and names the item after it, with no line about undoing a committed change",
          closed.returncode == 0
          and closed.stdout.split("\n")[0] == ("item 2 of 5 is deferred, and the minutes record it; it comes back "
                                              "just before the summary item.")
          and UNDO_COMMITTED_CHANGE_LINE not in closed.stdout
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
                                 + "".join(approved_line(f"item {n} of 5") for n in (1, 4, 5)))
    case.run("check", "--deferred")
    closed = case.run("close")
    check("a second deferral is recorded as open, the agent is told to keep it as a task and to undo any change already committed for it, and it is not named again",
          closed.returncode == 0
          and closed.stdout.split("\n")[:3] == [
              "item 2 of 5 is deferred a second time, so the minutes record it as open and it leaves the walk.",
              "Add it to your task list if it is not already a task.",
              UNDO_COMMITTED_CHANGE_LINE]
          and "item 2 of 5: deferred a second time, so it leaves the walk and stays open. <open>\n"
          in case.minutes.read_text()
          and marker(case) == "#next_to_present item 3 of 5", described(closed) + case.minutes.read_text())
    case.run("check")
    case.run("close")
    check("once every other item is recorded, the twice-deferred item is not named and the walk closes",
          marker(case) == "#next_to_present none, closed", case.minutes.read_text())


DEFERRED_NOTE = "(deferred: moved to just before the summary item)"


def walk_document(case):
    return (case.checkout / "docs" / "walk" / f"{WALK_NAME}.md").read_text()


def test_a_deferral_notes_it_in_the_items_heading_once():
    case = summary_case(next_to_present="item 2 of 5", recorded=approved_line("item 1 of 5"))
    before = walk_document(case)
    case.run("check", "--deferred")
    closed = case.run("close")
    check("close on a deferral puts the note right after the item's count in its heading and changes nothing else",
          closed.returncode == 0 and "not given the note" not in closed.stdout
          and walk_document(case) == before.replace("## Item 2 of 5: two", f"## Item 2 of 5 {DEFERRED_NOTE}: two"),
          described(closed) + walk_document(case))
    for _ in range(2):
        case.run("check")
        case.run("close")
    case.run("check", "--deferred")
    closed = case.run("close")
    check("a second deferral drops the item from the walk, takes the note out of its heading, and goes on to the "
          "summary item",
          closed.returncode == 0 and walk_document(case) == before
          and marker(case) == "#next_to_present item 5 of 5", described(closed) + walk_document(case))


def test_an_answer_to_a_deferred_item_takes_the_note_out_of_its_heading():
    case = summary_case(next_to_present="item 2 of 5", recorded=approved_line("item 1 of 5"))
    before = walk_document(case)
    case.run("check", "--deferred")
    case.run("close")
    for _ in range(2):
        case.run("check")
        case.run("close")
    case.run("check")
    closed = case.run("close")
    check("approving an item that was deferred once takes the note out of its heading again",
          closed.returncode == 0 and walk_document(case) == before
          and marker(case) == "#next_to_present item 5 of 5", described(closed) + walk_document(case))


def test_a_deferred_item_decided_through_a_held_answer_loses_the_note_in_its_heading():
    case = summary_case(next_to_present="item 2 of 5", recorded=approved_line("item 1 of 5"))
    before = walk_document(case)
    case.run("check", "--deferred")
    case.run("close")
    with open(case.minutes, "a") as minutes:
        minutes.write("item 2 of 5: answer held: item 3 of 5, raised by a fast-read finding, waits for the user's "
                      "answer. <open>\n#next_to_present item 3 of 5\n")
    case.run("check")
    closed = case.run("close")
    check("an item deferred once, then decided with the item its answer was held for, loses the note in its heading",
          closed.returncode == 0 and "item 2 of 5, whose answer was held for item 3 of 5" in closed.stdout
          and walk_document(case) == before, described(closed) + walk_document(case))


def test_a_deferral_in_a_walk_with_no_summary_item_gives_the_heading_no_note():
    case = Case(next_to_present="item 3 of 9")
    before = walk_document(case)
    case.run("check", "--deferred")
    closed = case.run("close")
    check("a deferred item of a walk with no summary item goes to the end, so its heading gets no note",
          closed.returncode == 0 and walk_document(case) == before and "not given the note" not in closed.stdout,
          described(closed) + walk_document(case))


def test_a_deferral_under_a_heading_naming_other_items_too_leaves_the_heading_alone_and_says_so():
    document = SUMMARY_DOCUMENT.replace("## Item 2 of 5: two\n\nRecommendation: leave it.\n\n## Item 3 of 5: three",
                                        "## Items 2 and 3 of 5: two and three\n\n**Item 2:** two.\n\n"
                                        "#case_against none.\n\nRecommendation: leave it.\n\n**Item 3:** three.")
    case = Case(next_to_present="item 2 of 5", document=document)
    before = walk_document(case)
    case.run("check", "--deferred")
    closed = case.run("close")
    check("close on a deferral of one item of a shared heading writes no note and says the heading is left as it is",
          closed.returncode == 0 and walk_document(case) == before
          and f"names other items too, so it is not given the note {DEFERRED_NOTE}." in closed.stdout,
          described(closed))


def test_a_deferral_notes_only_the_heading_with_the_walks_current_count():
    document = SUMMARY_DOCUMENT.replace("## Item 1 of 5: one", "## Item 2 of 4: two, as an earlier plan had it\n\n"
                                        "## Item 1 of 5: one")
    case = Case(next_to_present="item 2 of 5", document=document)
    before = walk_document(case)
    case.run("check", "--deferred")
    closed = case.run("close")
    check("close on a deferral notes the item's heading of the walk's count M, not an older heading of another M",
          closed.returncode == 0
          and walk_document(case) == before.replace("## Item 2 of 5: two", f"## Item 2 of 5 {DEFERRED_NOTE}: two"),
          described(closed) + walk_document(case))


def test_a_summary_heading_carrying_the_deferred_note_is_still_the_summary_item():
    document = SUMMARY_DOCUMENT.replace("## Item 5 of 5: summary", f"## Item 5 of 5 {DEFERRED_NOTE}: summary")
    case = Case(next_to_present="item 4 of 5", document=document)
    case.minutes.write_text("# Minutes\n\n" + approved_line("item 1 of 5")
                            + "item 2 of 5: deferred; it moves to just before the summary item. <open>\n"
                            + approved_line("item 3 of 5") + "#next_to_present item 4 of 5\n")
    case.run("check")
    closed = case.run("close")
    check("the deferred item comes back before a summary item whose heading carries the note",
          closed.returncode == 0 and marker(case) == "#next_to_present item 2 of 5",
          described(closed) + case.minutes.read_text())


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
                        recorded=approved_line("item 3 of 5"))
    with open(case.minutes, "a") as minutes:
        minutes.write("A note written after the marker.\n")
    case.run("check")
    closed = case.run("close")
    check("close writes the marker as the minutes' last line, below a note written after the old marker",
          closed.returncode == 0 and marker(case) == "#next_to_present item 4 of 5", case.minutes.read_text())
    case = summary_case(next_to_present="item 4 of 5",
                        recorded=approved_line("item 2 of 5") + approved_line("item 5 of 5"))
    case.run("check")
    case.run("close")
    check("after the last item the minutes do not record, the walk goes round to the first one they do not",
          marker(case) == "#next_to_present item 1 of 5", case.minutes.read_text())


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


def test_the_summary_item_picks_the_order_and_headings_of_another_m_are_walked():
    case = Case(next_to_present="item 3 of 16", document=STRAY_TOTALS_DOCUMENT)
    case.minutes.write_text("# Minutes\n\n#next_to_present item 3 of 16\n")
    case.run("check", "--deferred")
    case.run("close")
    case.run("check")
    case.run("close")
    check("a deferred item comes back before the heading whose point is summary, not before a later item or one "
          "that only mentions a summary", marker(case) == "#next_to_present item 3 of 8", case.minutes.read_text())
    case = Case(next_to_present="item 6 of 16", document=STRAY_TOTALS_DOCUMENT)
    case.minutes.write_text("# Minutes\n\n" + "".join(approved_line(f"item {n} of 16") for n in range(1, 6))
                            + "#next_to_present item 6 of 16\n")
    case.run("check")
    closed = case.run("close")
    check("headings whose `of M` is not the minutes' are walked like any other, and M counts them",
          closed.returncode == 0 and marker(case) == "#next_to_present item 7 of 8", case.minutes.read_text())


FIX_NEXT_LINE = "#approval_walk_item_in_category_fix_next"
UNNUMBERED_ITEMS_DOCUMENT = """# A walk whose waiting items have only titles

## Introduction

Not an item: it comes before the first running count.

## Item 1 of 4: one

#case_against none.

Recommendation: approve.

## two

#approval_walk_item_in_category_fix_next

#case_against none.

Recommendation: approve.

## three

#approval_walk_item_in_category_fix_next

#case_against none.

Recommendation: approve.

## Summary

#case_against none.

The walk in short.
"""


def test_an_unnumbered_item_is_numbered_when_it_is_shown_and_nothing_else_is_renumbered():
    case = Case(next_to_present="item 1 of 4", document=UNNUMBERED_ITEMS_DOCUMENT)
    case.run("check")
    closed = case.run("close")
    check("close numbers the next unnumbered item one more than the highest whole number, writing the number and the "
          "counted M into its heading and the `#next_to_present` line",
          closed.returncode == 0 and marker(case) == "#next_to_present item 2 of 4"
          and "\n## Item 2 of 4: two\n" in walk_document(case) and "\n## three\n" in walk_document(case)
          and "\n## Introduction\n" in walk_document(case)
          and "which gives item 2 of 4, the item" in closed.stdout, described(closed) + walk_document(case))
    document = walk_document(case).replace("## three", f"## a case the walk missed\n\n"
        f"{FIX_NEXT_LINE}\n\n#case_against none.\n\n## three")
    (case.checkout / "docs" / "walk" / f"{WALK_NAME}.md").write_text(document)
    case.run("check")
    closed = case.run("close")
    check("an item added after the current one is numbered 3 when shown, M counts it, and the earlier headings keep "
          "their `of 4`",
          closed.returncode == 0 and marker(case) == "#next_to_present item 3 of 5"
          and "\n## Item 3 of 5: a case the walk missed\n" in walk_document(case)
          and "\n## Item 1 of 4: one\n" in walk_document(case) and "\n## Item 2 of 4: two\n" in walk_document(case),
          described(closed) + walk_document(case))
    case.run("check")
    case.run("close")
    check("the item that was waiting next is numbered after the added one",
          marker(case) == "#next_to_present item 4 of 5" and "\n## Item 4 of 5: three\n" in walk_document(case),
          walk_document(case))


def test_an_unnumbered_summary_heading_is_the_summary_item():
    case = Case(next_to_present="item 1 of 4", document=UNNUMBERED_ITEMS_DOCUMENT)
    case.run("check")
    case.run("close")
    case.run("check", "--deferred")
    case.run("close")
    case.run("check")
    closed = case.run("close")
    check("a heading `## Summary` with no number is the summary item, so a deferred item comes back before it is "
          "numbered",
          closed.returncode == 0 and marker(case) == "#next_to_present item 2 of 4"
          and "\n## Summary\n" in walk_document(case), described(closed) + walk_document(case))


def test_an_unnumbered_item_skips_a_number_a_waiting_item_already_holds():
    document = SUMMARY_DOCUMENT.replace("## Item 2 of 5: two", f"## a case the walk missed\n\n"
        f"{FIX_NEXT_LINE}\n\n## Item 2 of 5: two")
    case = summary_case(next_to_present="item 1 of 5")
    (case.checkout / "docs" / "walk" / f"{WALK_NAME}.md").write_text(rated(document))
    case.run("check")
    closed = case.run("close")
    check("in an open walk whose waiting items carry numbers, an added item is numbered past the highest of them, "
          "so no number is used twice",
          closed.returncode == 0 and marker(case) == "#next_to_present item 6 of 6"
          and "\n## Item 6 of 6: a case the walk missed\n" in walk_document(case), described(closed) + walk_document(case))


GROUPED_SUB_STEPS_DOCUMENT = """# A walk whose item 3 is grouped under a heading of its own, as older walks were

## Item 1 of 16: one

#case_against none.

## Item 3: corrections that make the design match the code

### Item 3.1 of 16: the first correction

#case_against none.

### Item 3.2 of 16: the second correction

#case_against none.
"""


def test_a_heading_that_opens_with_an_item_label_and_no_m_is_not_an_unnumbered_item():
    case = Case(next_to_present="item 3.1 of 16", document=GROUPED_SUB_STEPS_DOCUMENT)
    case.minutes.write_text("# Minutes\n\n" + approved_line("item 1 of 16") + "#next_to_present item 3.1 of 16\n")
    before = walk_document(case)
    case.run("check")
    closed = case.run("close")
    check("a `## Item 3: ...` heading that groups sub-steps is not numbered, and the walk goes on to item 3.2",
          closed.returncode == 0 and marker(case) == "#next_to_present item 3.2 of 2" and walk_document(case) == before,
          described(closed) + walk_document(case))


PART_HEADINGS_OVER_ITEMS_DOCUMENT = """# A walk with `##` part headings over `###` items

## Part 1: conflicts

### Item 1 of 3: one

#case_against none.

## Part 2: names

### Item 2 of 3: two

#case_against none.

### Item 3 of 3: three

#case_against none.
"""


def test_a_part_heading_over_items_one_level_down_is_not_an_unnumbered_item():
    case = Case(next_to_present="item 1 of 3", document=PART_HEADINGS_OVER_ITEMS_DOCUMENT)
    before = walk_document(case)
    case.run("check")
    closed = case.run("close")
    check("in a walk-document whose items are `###` headings, a `## Part 2` heading is not numbered as an item, "
          "and the walk goes on to item 2",
          closed.returncode == 0 and marker(case) == "#next_to_present item 2 of 3" and walk_document(case) == before,
          described(closed) + walk_document(case))


DOTTED_SUB_STEP_HEADINGS_ONE_LEVEL_DOWN_DOCUMENT = """# A walk with `###` sub-steps under `##` items

## Item 1 of 3: one

### Item 1.1 of 3

No decision here.

### Item 1.2 of 3

#case_against none.

## a case the walk missed

#approval_walk_item_in_category_fix_next

#case_against none.

## Item 2 of 3: two

#case_against none.
"""


def test_dotted_sub_step_headings_one_level_down_do_not_stop_an_added_item_being_numbered():
    case = Case(next_to_present="item 1.2 of 3", document=DOTTED_SUB_STEP_HEADINGS_ONE_LEVEL_DOWN_DOCUMENT)
    case.run("check")
    closed = case.run("close")
    check("`### Item 1.1 of 3` sub-steps under `##` items do not stop the `##` item added after them from being numbered "
          "and shown next",
          closed.returncode == 0 and marker(case) == "#next_to_present item 3 of 3"
          and "\n## Item 3 of 3: a case the walk missed\n" in walk_document(case),
          described(closed) + walk_document(case))


SUB_STEPS_THEN_ITEMS_WAITING_ON_THEIR_ITEM_DOCUMENT = """# A walk whose item 2 is shown as sub-steps, with added items waiting on item 2

## Item 1 of 2: one

#case_against none.

## Item 2 of 2: The restore task finds its commit

### Item 2.1 of 2: why

No decision here.

### Item 2.2 of 2: the new sentences

#case_against none.

## Nothing reports a renamed constant

#approval_walk_item_in_category_file_an_improvement_feature_or_change
#approval_walk_item_waits_on The restore task finds its commit

#case_against none.

## What this walk decided

#approval_walk_item_in_category_file_an_improvement_feature_or_change
#approval_walk_item_waits_on The restore task finds its commit
#approval_walk_item_waits_on Nothing reports a renamed constant

The walk in short.
"""


def test_an_item_whose_sub_steps_are_all_decided_is_not_named_again_and_the_items_waiting_on_it_are_numbered():
    case = Case(next_to_present="item 2.2 of 2", document=SUB_STEPS_THEN_ITEMS_WAITING_ON_THEIR_ITEM_DOCUMENT)
    case.minutes.write_text("# Minutes\n\n" + approved_line("item 1 of 2")
                            + "item 2.1 of 2: moved on; the item asked for no decision. <moved on, no decision>\n"
                            + "#next_to_present item 2.2 of 2\n")
    case.run("check")
    closed = case.run("close")
    check("once its last sub-step is decided, item 2 is not named again, and the item waiting on it is numbered and "
          "named next",
          closed.returncode == 0 and marker(case) == "#next_to_present item 3 of 4"
          and "\n## Item 3 of 4: Nothing reports a renamed constant\n" in walk_document(case),
          described(closed) + case.minutes.read_text() + walk_document(case))
    case.run("check")
    closed = case.run("close")
    check("the item that waits on items 2 and 3 is numbered and named once both are decided",
          closed.returncode == 0 and marker(case) == "#next_to_present item 4 of 4"
          and "\n## Item 4 of 4: What this walk decided\n" in walk_document(case),
          described(closed) + case.minutes.read_text() + walk_document(case))
    case.run("check", "--moved-on-no-decision", reply="next")
    closed = case.run("close")
    check("with every item and sub-step decided, close closes the walk",
          closed.returncode == 0 and marker(case) == "#next_to_present none, closed",
          described(closed) + case.minutes.read_text())


def test_close_hold_answer_numbers_a_new_item_that_waits_on_the_item_whose_last_sub_step_it_holds():
    case = Case(next_to_present="item 2.2 of 2", document=SUB_STEPS_THEN_ITEMS_WAITING_ON_THEIR_ITEM_DOCUMENT)
    case.minutes.write_text("# Minutes\n\n" + approved_line("item 1 of 2")
                            + "item 2.1 of 2: moved on; the item asked for no decision. <moved on, no decision>\n"
                            + "#next_to_present item 2.2 of 2\n")
    case.run("check")
    closed = case.run("close", "--hold-answer-until-new-item-answered")
    check("close --hold-answer-until-new-item-answered numbers a new item that waits on item 2, whose other sub-steps "
          "the minutes decide and whose last sub-step's answer it holds",
          closed.returncode == 0 and marker(case) == "#next_to_present item 3 of 4"
          and "\n## Item 3 of 4: Nothing reports a renamed constant\n" in walk_document(case),
          described(closed) + walk_document(case))


def test_close_numbers_the_new_item_a_finding_raised_and_holds_the_answer():
    case = Case(next_to_present="item 1 of 4", document=UNNUMBERED_ITEMS_DOCUMENT)
    case.run("check")
    document = walk_document(case).replace("## two", f"## the change a finding raised\n\n"
        f"{FIX_NEXT_LINE}\n\n#case_against none.\n\n## two")
    (case.checkout / "docs" / "walk" / f"{WALK_NAME}.md").write_text(document)
    closed = case.run("close", "--hold-answer-until-new-item-answered")
    check("close --hold-answer-until-new-item-answered numbers the item right after the answered one and holds the answer for it",
          closed.returncode == 0 and marker(case) == "#next_to_present item 2 of 5"
          and "\n## Item 2 of 5: the change a finding raised\n" in walk_document(case) and "\n## two\n" in walk_document(case)
          and "item 1 of 4: answer held: item 2 of 5, raised by a fast-read finding" in case.minutes.read_text()
          and closed.stdout.startswith("item 1 of 4's answer does not take effect yet: item 2 of 5"),
          described(closed) + walk_document(case))


def test_close_hold_answer_refuses_when_no_new_item_follows_the_answered_one():
    case = Case(next_to_present="item 1 of 4", document=UNNUMBERED_ITEMS_DOCUMENT.replace("## two", "## Item 2 of 4: two"))
    case.run("check")
    minutes, document = case.minutes.read_text(), walk_document(case)
    closed = case.run("close", "--hold-answer-until-new-item-answered")
    check("close --hold-answer-until-new-item-answered refuses, writing nothing, when the heading after the answered item has a "
          "number",
          closed.returncode == 1 and closed.stdout == ""
          and closed.stderr.startswith(FAILURE_PREFIX + "close: nothing written: close was given "
                                       "--hold-answer-until-new-item-answered, but in ")
          and "is `## Item 2 of 4: two`, not a new item's heading" in closed.stderr
          and case.minutes.read_text() == minutes and walk_document(case) == document, described(closed))
    case = Case(next_to_present="item 4 of 5", document=SUMMARY_DOCUMENT.replace("## Item 5 of 5: summary\n\nThe walk in short.\n", ""))
    case.run("check")
    closed = case.run("close", "--hold-answer-until-new-item-answered")
    check("close --hold-answer-until-new-item-answered refuses when the answered item is the walk-document's last",
          closed.returncode == 1 and "is none, since it is the last item" in closed.stderr, described(closed))
    case = Case(next_to_present="item 1 of 4", document=UNNUMBERED_ITEMS_DOCUMENT)
    case.run("check")
    document = walk_document(case).replace("## Item 1 of 4: one", "## Item 9 of 9: one")
    (case.checkout / "docs" / "walk" / f"{WALK_NAME}.md").write_text(document)
    minutes = case.minutes.read_text()
    closed = case.run("close", "--hold-answer-until-new-item-answered")
    check("close --hold-answer-until-new-item-answered refuses, writing nothing, when the walk-document no longer has "
          "a heading for the answered item",
          closed.returncode == 1 and closed.stdout == ""
          and "the last `#next_to_present` line in " in closed.stderr
          and "has no heading `Item 1`" in closed.stderr
          and case.minutes.read_text() == minutes and walk_document(case) == document, described(closed))


def test_close_hold_answer_refuses_a_new_item_it_cannot_place_before_numbering_it():
    for name, new_item, expected in (
            ("has no category line, and the refusal's command keeps the hold flag",
             "## the change a finding raised\n\n#case_against none.\n\n",
             " close --hold-answer-until-new-item-answered --cwd "),
            ("waits on an item not yet shown",
             f"## the change a finding raised\n\n{FIX_NEXT_LINE}\n\n#approval_walk_item_waits_on two\n\n"
             "#case_against none.\n\n", "waits on `## two`, which the user has not ruled on yet"),
            ("waits on a numbered item the user has not answered",
             f"## the change a finding raised\n\n{FIX_NEXT_LINE}\n\n#approval_walk_item_waits_on three\n\n"
             "#case_against none.\n\n", "waits on item 3, which the user has not ruled on yet"),
            ("waits on the summary item",
             f"## the change a finding raised\n\n{FIX_NEXT_LINE}\n\n#approval_walk_item_waits_on summary\n\n"
             "#case_against none.\n\n", "waits on `## Summary`, which the user has not ruled on yet")):
        case = Case(next_to_present="item 1 of 4",
                    document=UNNUMBERED_ITEMS_DOCUMENT.replace("## three", "## Item 3 of 4: three"))
        case.run("check")
        document = walk_document(case).replace("## two", new_item + "## two", 1)
        (case.checkout / "docs" / "walk" / f"{WALK_NAME}.md").write_text(document)
        minutes = case.minutes.read_text()
        closed = case.run("close", "--hold-answer-until-new-item-answered")
        check(f"close --hold-answer-until-new-item-answered refuses, writing nothing to the walk-document or the "
              f"minutes, when the new item {name}",
              closed.returncode == 1 and expected in closed.stderr and "nothing written" in closed.stderr
              and "Traceback" not in closed.stderr and walk_document(case) == document
              and case.minutes.read_text() == minutes, described(closed) + walk_document(case))


def test_a_deferred_last_item_hands_on_to_the_first_unrecorded_item():
    case = Case(next_to_present="item 5 of 9")
    case.run("check", "--deferred")
    closed = case.run("close")
    check("deferring the walk-document's last item, with no summary item, names the first item not recorded",
          closed.returncode == 0 and marker(case) == f"#next_to_present item 3 of {WALK_DOCUMENT_COUNTED_M}",
          case.minutes.read_text())


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
    case.minutes.write_text("# Minutes\n\n" + approved_line("item 1 of 6")
                            + "Items 2 to 4: respelled after item 1; item 2 cites the approved definition.\n"
                            + approved_line("item 2 of 6") + "#next_to_present item 2.1 of 6\n")
    case.run("check")
    closed = case.run("close")
    check("after a dotted part is approved, a note naming later items whose `approved` follows `the` leaves them "
          "unrecorded, so the item after the part comes next, not the summary item",
          closed.returncode == 0 and marker(case) == "#next_to_present item 3 of 5",
          described(closed) + case.minutes.read_text())


# Item 5.2.2, once deferred, sits just before the summary item, as the walk-runner moves a deferred item. Its
# headings say `of 24`; close counts M as 3, the whole numbers 5, 6 and 7, as it does for every dotted walk below.
SUB_ITEMS_DOCUMENT = """# A walk whose item 5.2 has sub-items

## Item 5.2 of 24: keep find-missing-file, and build find-info

Recommendation: approve.

## Item 5.2.1 of 24: approve the cold read's corrections as a group

## Item 5.2.3 of 24: change the rule

## Item 5.2.4 of 24: moving an agent-seat between machines is in scope

## Item 6 of 24: an issue's title follows its first heading

## Item 5.2.2 of 24: a deferred session-handoff can wait forever

## Item 7 of 24: Summary
"""


def test_a_note_on_unanswered_sub_items_does_not_skip_them_or_count_as_a_second_deferral():
    case = Case(next_to_present="item 5.2 of 24", document=SUB_ITEMS_DOCUMENT)
    case.minutes.write_text(
        "# Minutes\n\n#next_to_present item 5.2 of 24\n"
        "Items 5.2.1-5.2.3 revised at the advisor call (5.2.1 reframed as the cold read he approved today; 5.2.2 "
        "notes the sanity-check cites it; 5.2.3 recommendation back to keeping the section).\n"
        "#next_to_present item 5.2 of 24\n")
    case.run("check")
    closed = case.run("close")
    check("after item 5.2 is approved, a note on its unanswered sub-items that says `he approved` inside a "
          "parenthesis leaves them unrecorded, so the first sub-item comes next",
          closed.returncode == 0 and marker(case) == "#next_to_present item 5.2.1 of 3",
          described(closed) + case.minutes.read_text())
    case = Case(next_to_present="item 6 of 24", document=SUB_ITEMS_DOCUMENT)
    case.minutes.write_text(
        "# Minutes\n\n"
        + "".join(f"item {n} of 24: approved; every text the change adds has had a fast read. <accepted>\n"
                  for n in ("5.2", "5.2.1"))
        + "item 5.2.2 of 24: deferred; it moves to just before the summary item. <open>\n"
        + "".join(f"item {n} of 24: approved; every text the change adds has had a fast read. <accepted>\n"
                  for n in ("5.2.3", "5.2.4"))
        + "Items 5.2.1-5.2.12 rulings: a subagent applies them to branch handoff-design-full-cold-read-revisions-"
          "topic-branch (rebased on main), with the new handoff-system glossary and the overview update, as one PR "
          "(task #150). 5.2.2 and 5.2.5 deferred; 5.2.6 D.\n"
        "#next_to_present item 6 of 24\n")
    case.run("check")
    closed = case.run("close")
    check("a note on several items that says one of them was deferred is not a second deferral of it, so the "
          "once-deferred item is named before the summary item instead of leaving the walk",
          closed.returncode == 0 and marker(case) == "#next_to_present item 5.2.2 of 3",
          described(closed) + case.minutes.read_text())


NESTED_PARTS_DOCUMENT = """# A walk whose item 2 gained parts and a part of a part

## Item 1 of 18: one

## Item 2 of 18: two

## Item 2.1 of 18: a part

## Item 2.1.1 of 18: a part of a part

## Item 2.2 of 18: a second part

## Item 2.3 of 18: a third part

## Item 2.4 of 18: a fourth part

## Item 18 of 18: summary
"""


def test_a_note_that_adds_parts_and_says_approved_or_deferred_in_another_sense_does_not_skip_them():
    # Each note is a real walk-minutes line that made close skip the part it names.
    for answered, recorded, note, expected in (
            ("2", ["1"],
             "Items 2.1 (step 2: the agent may give a rewrite another cold-read-full-run, guided by the research's "
             "pattern) and 2.2 (GHI 1064 counts the rewrite as a change; the loop deferred) added to the "
             "walk-document after item 2, with the advisor's fixes and fast reads. M stays 18.\n", "2.1"),
            ("2.1", ["1", "2"],
             "Item 2.1.1 of 18 (approve the sort's 60 designs) added after item 2.1, 2026-10-27: the sort item 2 "
             "approved finished; summary at /home/nedlern/fast-read-runs/ghi-md-design-sort/summary.md. Two fast "
             "reads applied. M stays 18.\n", "2.1.1"),
            ("2.2", ["1", "2", "2.1", "2.1.1"],
             "Items 2.3 (add Gemini Argon at high as a seventh cold-read-cell; Luna stays) and 2.4 (keep Fable's "
             "defect-hunt cell at max) added after item 2.2: the Fable-xhigh and Argon rerun approved in walk "
             "cold-read-cells-fable-at-xhigh-gemini-argon-at-high-and-gpt-luna-removal-2026-10-26 finished.\n",
             "2.3")):
        case = Case(next_to_present=f"item {answered} of 18", document=NESTED_PARTS_DOCUMENT)
        case.minutes.write_text("# Minutes\n\n" + "".join(approved_line(f"item {number} of 18") for number in recorded)
                                + note + f"#next_to_present item {answered} of 18\n")
        case.run("check")
        closed = case.run("close")
        check(f"after item {answered} is approved, a note adding item {expected} that says approved or deferred in "
              f"another sense leaves it unrecorded, so close names item {expected} next",
              closed.returncode == 0 and marker(case) == f"#next_to_present item {expected} of 3",
              described(closed) + case.minutes.read_text())


def test_a_minutes_line_with_an_unusable_item_range_is_skipped():
    case = summary_case(next_to_present="item 3 of 5",
                        recorded=approved_line("items 4 to 2 of 5") + approved_line("item 4 of 5"))
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
          closed.returncode == 0 and marker(case) == f"#next_to_present item 7 of {WALK_DOCUMENT_COUNTED_M}",
          described(closed))


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
        status = program.main(["check", "--user-reply-as-typed", "a", "--cwd", str(case.checkout), "--cold-read-records", str(case.records),
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


def test_a_hand_written_awaiting_ruling_line_does_not_undo_a_decision_close_wrote():
    case = Case(next_to_present="item 1 of 3", document=THREE_ITEM_DOCUMENT)
    case.minutes.write_text("# Minutes\n\n" + approved_line("item 2 of 3")
                            + "Item 2 of 3: the user asked for a change; redrafted. <revised, awaiting ruling>\n"
                            "#next_to_present item 1 of 3\n")
    case.run("check")
    closed = case.run("close")
    check("a hand-written <revised, awaiting ruling> line after close decided item 2 leaves it decided",
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


TWO_HEADINGS_FOR_ITEM_2_OF_DIFFERENT_M = (
    "# W\n\n## Item 1 of 3: one\n\n## Item 2 of 3: old\n\n#new \"Old.\"\n\n## Item 2 of 4: new\n\n#new \"New.\"\n")


def test_the_markers_m_picks_between_two_headings_for_one_item():
    case = Case(next_to_present="item 2 of 4", document=TWO_HEADINGS_FOR_ITEM_2_OF_DIFFERENT_M)
    result = case.run("check")
    check("of two headings for item 2 with different M, the `#next_to_present` line's M picks the one check reads",
          result.returncode == 0 and case.calls.read_text() == "New.\n", described(result))


def test_check_refuses_a_walk_document_close_would_refuse_before_any_fast_read():
    for document, next_to_present, reason in (
            ("# W\n\n## Item 2 of 3: two\n\n#new \"First.\"\n\n## Item 2 of 3: again\n\n#new \"Second.\"\n\n"
             "## Item 3 of 3: summary\n", "item 2 of 3", "more than one heading for `Item 2`"),
            (TWO_HEADINGS_FOR_ITEM_2_OF_DIFFERENT_M, "item 2", "more than one heading for `Item 2`")):
        case = Case(next_to_present=next_to_present, document=document)
        before = case.minutes.read_text()
        result = case.run("check")
        check(f"check refuses, running no fast read and writing nothing, when the walk-document has {reason}",
              result.returncode == 1 and reason in result.stderr and case.calls.read_text() == ""
              and case.minutes.read_text() == before, described(result))


def test_following_the_repeated_heading_refusal_clears_it_whichever_heading_is_meant():
    first, second = "## Item 2 of 3: first", "## Item 2 of 3: second"
    layout = ("# W\n\n## Item 1 of 3: one\n\n{first}\n\n#new \"First.\"\n\n{second}\n\n#new \"Second.\"\n\n"
              "## Item 3 of 3: summary\n")
    refused = Case(next_to_present="item 2 of 3", document=layout.format(first=first, second=second)).run("check")
    check("the repeated-heading refusal offers `revised` only for the last of the headings",
          refused.returncode == 1 and "only when the heading you mean comes after every other heading for that item" in refused.stderr,
          described(refused))
    for meant, first_heading, second_heading, read in (
            ("the first, the second withdrawn", first, "## Withdrawn: Item 2 of 3: second", "First.\n"),
            ("the second, the first withdrawn", "## Withdrawn: Item 2 of 3: first", second, "Second.\n"),
            ("the second, marked revised", first, "## Item 2 of 3 revised: second", "Second.\n")):
        case = Case(next_to_present="item 2 of 3",
                    document=layout.format(first=first_heading, second=second_heading))
        result = case.run("check")
        check(f"an agent that means {meant} and does as the refusal says is not refused again",
              result.returncode == 0 and case.calls.read_text() == read, described(result))


def test_following_the_repeated_heading_refusal_clears_it_when_two_headings_share_a_total_and_one_does_not():
    layout = ("# W\n\n## Item 1 of 10: one\n\n{a}\n\n#new \"A.\"\n\n{b}\n\n#new \"B.\"\n\n"
              "## Item 2 of 10: c\n\n#new \"C.\"\n")
    a, b = "## Item 2 of 9: a", "## Item 2 of 9: b"
    refused = Case(next_to_present="item 2 of 9", document=layout.format(a=a, b=b)).run("check")
    check("the `of M` in the minutes does not pick between two headings that share it, and the refusal says so",
          refused.returncode == 1 and "if no other of those headings gives the same total as the heading you mean"
          in refused.stderr, described(refused))
    for meant, next_to_present, first, second, read in (
            ("the one `of 10` heading, named by its total", "item 2 of 10", a, b, "C.\n"),
            ("an `of 9` heading, the other withdrawn", "item 2 of 9", a, "## Withdrawn: Item 2 of 9: b", "A.\n")):
        case = Case(next_to_present=next_to_present, document=layout.format(a=first, b=second))
        result = case.run("check")
        check(f"an agent that means {meant} and does as the refusal says is not refused again",
              result.returncode == 0 and case.calls.read_text() == read, described(result))


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
                  rf"\nitem 4 of 9: the user answered {re.escape(answered)} #case_against_none \(\d{{4}}-\d\d-\d\d \d\d:\d\d\) in his "
                  r"words \"a\", which makes its change\. Fast reads:\n- no proposed text marked\n$", minutes) is not None,
              described(checked) + minutes)
        closed = case.run("close")
        check(f"close after check {' '.join(flags)} records each part's outcome on one line, the last part's "
              "included, and moves on to the next item",
              closed.returncode == 0
              and closed.stdout.rstrip("\n").split("\n") == [
                  "item 4 of 9's answer is recorded in the minutes, and its change may now be made.",
                  "Your next message must include these lines, as they are:",
                  "no proposed text marked"] + took_effect_next(case)
              and case.minutes.read_text().rstrip().endswith(
                  f"item 4 of 9: {recorded}; every text the change adds has had a fast read.\n"
                  f"#next_to_present item 6 of {WALK_DOCUMENT_COUNTED_M}"), described(closed) + case.minutes.read_text())


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
              and f"check{''.join(' ' + flag for flag in flags)} --user-reply-as-typed a` again." in result.stderr
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


RATED_NONE_DOCUMENT = """# A walk

## Item 1 of 3: print the poem count after the list

#not_asked_touches tools/counter.py

#case_against none.

Recommendation: print it.

## Item 2 of 3: a new option for the counter

#not_asked_touches tools/counter.py

#case_against weak: the option costs a few lines of code.

Recommendation: add it.

## Item 3 of 3: summary

#case_against none.

Nothing to decide.
"""


def rated_none_case(next_to_present="item 1 of 3", touches=None):
    document = RATED_NONE_DOCUMENT
    if touches is not None:
        document = document.replace("#not_asked_touches tools/counter.py\n\n#case_against none.",
                                    f"{touches}#case_against none.", 1)
    case = Case(next_to_present=next_to_present, document=document)
    (case.checkout / "tools").mkdir()
    (case.checkout / "tools" / "counter.py").write_text("count = 0\n")
    return case


def test_an_item_of_no_kind_rated_none_settles_without_the_user_and_close_records_it_accepted():
    case = rated_none_case()
    result = case.run("check", "--not-asked", "none")
    minutes = case.minutes.read_text()
    check("an item of no kind rated none is settled: the minutes say not asked, case against none, and its rating",
          result.returncode == 0
          and re.search(r"\nitem 1 of 3: settled without asking the user, not asked, case against none "
                        r"#case_against_none \(\d{4}-\d\d-\d\d \d\d:\d\d\), which makes its change\. Fast reads:\n",
                        minutes) is not None
          and "item 1 of 3 is recorded as settled without asking the user, case against none;" in result.stdout
          and "Before you run close, ask the advisor whether a later ruling or another open item overtakes item 1 of 3"
              in result.stdout, described(result) + minutes)
    closed = case.run("close")
    check("close records the item settled as rated none as accepted, and moves on",
          closed.returncode == 0
          and "\nitem 1 of 3: not asked, case against none; every text the change adds has had a fast read. "
              "<accepted>\n" in case.minutes.read_text()
          and int(re.search(r"#next_to_present item (\d+) of 3$", case.minutes.read_text().rstrip())[1]) > 1,
          described(closed))
    case = rated_none_case()
    result = case.run("check", "--not-asked", "NONE")
    check("`--not-asked` reads none in any case", result.returncode == 0, described(result))


def refused_as_rated_none(case, *problems):
    before = case.minutes.read_text()
    result = case.run("check", "--not-asked", "none")
    return (result.returncode == 1 and "cannot be settled without asking the user as case against none, because:"
            in result.stderr and all(problem in result.stderr for problem in problems)
            and "check --not-asked none` again" in result.stderr
            and case.minutes.read_text() == before and case.calls.read_text() == "", described(result))


def test_an_item_of_no_kind_settles_only_when_rated_none_and_touching_no_guarded_file():
    check("an item of no kind rated weak is refused",
          *refused_as_rated_none(rated_none_case("item 2 of 3"), "rates the case against weak; an item of none of "
                                 "the kinds settles without the user only when its case against is rated none"))
    check("an item of no kind with no touches line is refused",
          *refused_as_rated_none(rated_none_case(touches=""), "it has no `#not_asked_touches` line"))
    for word in ("CLAUDE.md:12", "tools/counter.py.", "tools/missing.py"):
        check(f"an item of no kind whose touches line names {word}, no path in the checkout, is refused",
              *refused_as_rated_none(rated_none_case(touches=f"#not_asked_touches {word}\n\n"),
                                     f"`#not_asked_touches` names {word}, which is not in the checkout"))
    for path in ("CLAUDE.md", ".claude/skills/poems/SKILL.md", "docs/nedschorus-wiki/poems.md",
                 "docs/poems-instructions.md"):
        check(f"an item of no kind that touches {path}, which the instruction-file guard protects, is refused",
              *refused_as_rated_none(rated_none_case(touches=f"#not_asked_touches tools/counter.py {path}\n\n"),
                                     f"`#not_asked_touches` names {path}, which the instruction-file guard protects"))


def test_an_item_of_no_kind_with_an_empty_touches_line_settles_as_a_change_that_touches_no_file():
    case = rated_none_case(touches="#not_asked_touches\n\n")
    result = case.run("check", "--not-asked", "none")
    check("an item of no kind rated none whose touches line is empty, such as one that recommends doing nothing, "
          "is settled", result.returncode == 0
          and "item 1 of 3 is recorded as settled without asking the user, case against none;" in result.stdout,
          described(result))


def test_a_not_asked_value_other_than_a_kind_or_none_is_refused_as_usage():
    for value in ("7", "0", "weak"):
        case = rated_none_case()
        result = case.run("check", "--not-asked", value)
        check(f"`--not-asked {value}` is refused as usage, writing nothing",
              result.returncode == 2 and f"`{value}` is not a kind: give 1, 2, 3, 4, 5, 6 or none" in result.stderr
              and case.minutes.read_text().rstrip().endswith("#next_to_present item 1 of 3"), described(result))


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


def not_asked_case_with_line(next_to_present, old_line, new_line, files=None):
    case = not_asked_case(next_to_present, files)
    (case.checkout / "docs" / "walk" / f"{WALK_NAME}.md").write_text(NOT_ASKED_DOCUMENT.replace(old_line, new_line))
    return case


def test_a_name_holding_a_digit_or_of_one_word_is_found_in_any_case_and_inside_a_longer_name():
    for name, spelling in (("utf8_locale", "utf8_locale_name = 1"), ("utf8_locale", "UTF8_LOCALE = 1"),
                           ("sha256_of", "sha256_of_file_or_empty()"), ("cold-read-v2", "COLD_READ_V2 = 1"),
                           ("utf8_locale", "UTF_8_LOCALE = 1"), ("utf8_locale", "see utf-8-locale"),
                           ("sha256_of", "sha_256_of(x)"),
                           ("reader", "Reader()"), ("reader", "reader_path = 1")):
        case = not_asked_case_with_line("item 3 of 7", "#not_asked_unused old_reader", f"#not_asked_unused {name}",
                                        {"tools/other.py": f"{spelling}\n"})
        check(f"kind 3 is refused when an untouched file holds the removed name {name} as {spelling}",
              *refused(case, 3, f"`{name}`, named on its `#not_asked_unused` line, is still named in tools/other.py"))
    case = not_asked_case_with_line("item 3 of 7", "#not_asked_unused old_reader", "#not_asked_unused utf8_locale")
    result = case.run("check", "--not-asked", "3")
    check("kind 3 settles a removed name holding a digit that no untouched file holds", result.returncode == 0,
          described(result))


def test_underscore_emphasis_around_a_marker_is_read():
    case = not_asked_case_with_line("item 2 of 7", "#not_asked_test tools/counter-test.py\n\n#case_against weak:",
                                    "__#not_asked_test__ tools/counter-test.py\n\n__#case_against__ weak:")
    result = case.run("check", "--not-asked", "2")
    check("`__#case_against__ weak:` and `__#not_asked_test__` are read as their markers",
          result.returncode == 0 and "kind 2 #case_against_weak (" in case.minutes.read_text(), described(result))
    case = not_asked_case_with_line("item 2 of 7", "#case_against weak:", "_#case_against_ weak:")
    result = case.run("check", "--not-asked", "2")
    check("`_#case_against_ weak:` is read as the marker", result.returncode == 0, described(result))
    case = not_asked_case_with_line("item 2 of 7", "#case_against weak:", "#case_against_weak:")
    result = case.run("check", "--not-asked", "2")
    check("`#case_against_weak:`, a hashtag the minutes write, is not read as the marker",
          result.returncode == 1 and "has no `#case_against` line" in result.stderr, described(result))


def test_a_rename_to_a_name_with_spaces_or_to_a_glossary_term_with_an_alias_settles():
    case = not_asked_case_with_line("item 4 of 7", "#not_asked_rename poem-list poem-index",
                                    "#not_asked_rename `poem-list` `poem index page`",
                                    {"docs/poems-glossary.md": "- **poem index page** — the page that lists poems.\n"})
    result = case.run("check", "--not-asked", "4")
    check("kind 4 settles a rename to a name of two or more words, each name in backquotes", result.returncode == 0,
          described(result))
    case = not_asked_case_with_line("item 4 of 7", "#not_asked_rename poem-list poem-index",
                                    "#not_asked_rename `poem list` poem-index", {"docs/about.md": "See PoemList.\n"})
    check("kind 4 is refused when an untouched file holds an old name of two words in another spelling",
          *refused(case, 4, "`poem list`, named on its `#not_asked_rename` line, is still named in docs/about.md"))
    case = not_asked_case("item 4 of 7", {"docs/poems-glossary.md": "- **poem-index (aka PI)** — the poems page.\n"})
    result = case.run("check", "--not-asked", "4")
    check("kind 4 settles when the new name's glossary entry gives an alias after it", result.returncode == 0,
          described(result))
    check("kind 4 is refused when the glossary's term only starts with the new name",
          *refused(not_asked_case("item 4 of 7", {"docs/poems-glossary.md": "- **poem-index-two** — another.\n"}), 4,
                   "the new name `poem-index` is the term of no entry"))
    check("kind 4 is refused when the glossary's term gives the new name with a parenthetical that is not an alias",
          *refused(not_asked_case("item 4 of 7", {"docs/poems-glossary.md": "- **poem-index (v2)** — another.\n"}), 4,
                   "the new name `poem-index` is the term of no entry"))


RENAME_LINE = "#not_asked_rename poem-list poem-index"


def kind_6_case(evidence, files=None, touches=None):
    """Item 4 of the fixture made a kind 6 item: its rename line replaced by the evidence lines given."""
    case = not_asked_case_with_line("item 4 of 7", RENAME_LINE, evidence, files)
    if touches is not None:
        document = (case.checkout / "docs" / "walk" / f"{WALK_NAME}.md").read_text()
        (case.checkout / "docs" / "walk" / f"{WALK_NAME}.md").write_text(
            document.replace("#not_asked_touches docs/poems/index.md", f"#not_asked_touches {touches}".rstrip()))
    return case


def test_a_glossary_term_put_in_or_a_marker_no_program_reads_settles_as_kind_6_and_close_records_it():
    for evidence, files in (("#not_asked_glossary_term poem-index", None),
                            ("#not_asked_glossary_term `poem index page`",
                             {"docs/poems-glossary.md": "- **poem index page** — the page that lists poems.\n"}),
                            ("#not_asked_hashtag_marker #poem_date", {"docs/about.md": "Mark a dated poem #poem_date.\n"}),
                            ("#not_asked_hashtag_marker #poem_date", {"tools/poems.py": "TAG = '#poem_date_old'\n"}),
                            ("#not_asked_hashtag_marker #poem_date-note", {"tools/poems.py": "TAG = '#poem_date-old'\n"}),
                            ("#not_asked_glossary_term poem-index\n\n#not_asked_hashtag_marker #poem_date", None)):
        case = kind_6_case(evidence, files)
        result = case.run("check", "--not-asked", "6")
        check(f"kind 6 settles with {evidence!r} and files {files}",
              result.returncode == 0 and "settled without asking the user, not asked, kind 6 " in case.minutes.read_text(),
              described(result))
    case = kind_6_case("#not_asked_glossary_term poem-index")
    case.run("check", "--not-asked", "6")
    closed = case.run("close")
    check("close records a settled kind 6 item as accepted",
          closed.returncode == 0 and "\nitem 4 of 7: not asked, kind 6; every text the change adds has had a fast read. "
                                     "<accepted>\n" in case.minutes.read_text(), described(closed))


def test_kind_6_is_refused_unless_markdown_prose_outside_a_glossary_gets_a_listed_term_or_an_unread_marker():
    check("kind 6 is refused when the item names neither a term nor a marker",
          *refused(kind_6_case(""), 6, "it has neither a `#not_asked_glossary_term` line nor a `#not_asked_hashtag_marker` line"))
    check("kind 6 is refused when the item lists no file it touches",
          *refused(kind_6_case("#not_asked_glossary_term poem-index", touches=""), 6, "it has no `#not_asked_touches` line"))
    check("kind 6 is refused when it touches a file that is not Markdown",
          *refused(kind_6_case("#not_asked_glossary_term poem-index", touches="tools/main.py"), 6,
                   "`#not_asked_touches` names tools/main.py, which is not Markdown prose outside a glossary"))
    check("kind 6 is refused when it touches a glossary",
          *refused(kind_6_case("#not_asked_glossary_term poem-index", touches="docs/poems-glossary.md"), 6,
                   "`#not_asked_touches` names docs/poems-glossary.md, which is not Markdown prose outside a glossary"))
    check("kind 6 is refused when it touches a file not in the checkout",
          *refused(kind_6_case("#not_asked_glossary_term poem-index", touches="docs/missing.md"), 6,
                   "`#not_asked_touches` names docs/missing.md, which is not in the checkout"))
    check("kind 6 is refused when no glossary lists its term as an entry's term",
          *refused(kind_6_case("#not_asked_glossary_term poem-index",
                               {"docs/poems-glossary.md": "- **other** — not poem-index.\n"}), 6,
                   "the term `poem-index` is the term of no entry"))
    for reader in ("tools/poems.py", ".claude/settings.json", "tools/poems-test.py"):
        check(f"kind 6 is refused when the marker is in {reader}, which a program runs or reads",
              *refused(kind_6_case("#not_asked_hashtag_marker #poem_date", {reader: 'if "#poem_date" in line: pass\n'}), 6,
                       f"the marker `#poem_date` is in {reader}, which are not Markdown"))
    for marker, code, why in (
            ("#POEM_DATE", 'if "#poem_date" in line: pass\n', "in another letter case"),
            ("#poem_date-note", 'PAUSE = re.compile(r"#poem_date\\b")\n', "through a pattern that ends at its `-`"),
            ("#case_poem_strong", 'RATING = re.compile(r"#case_poem_[a-z_]+")\n', "through a pattern for a family of markers")):
        check(f"kind 6 is refused when a program reads the marker {why}",
              *refused(kind_6_case(f"#not_asked_hashtag_marker {marker}", {"tools/poems.py": code}), 6,
                       f"the marker `{marker}` is in tools/poems.py, which are not Markdown"))
    check("kind 6 refuses a marker holding a character other than letters, digits, `_` and `-`, searching nothing",
          *refused(kind_6_case("#not_asked_hashtag_marker #poem(date"), 6,
                   "`#poem(date` on its `#not_asked_hashtag_marker` line is not a hashtag marker"))
    check("kind 6 is refused when its marker line holds no hashtag marker",
          *refused(kind_6_case("#not_asked_hashtag_marker poem_date"), 6,
                   "`poem_date` on its `#not_asked_hashtag_marker` line is not a hashtag marker"))
    check("kind 6 refuses a marker line holding a regular expression's brackets as no hashtag marker, searching nothing",
          *refused(kind_6_case("#not_asked_hashtag_marker (poem"), 6,
                   "`(poem` on its `#not_asked_hashtag_marker` line is not a hashtag marker"))
    check("kind 6 is refused when its case against is rated above weak",
          *refused(kind_6_case("#not_asked_glossary_term poem-index\n\n#case_against medium: misread meaning."), 6,
                   "rates the case against medium"))


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


def test_an_item_an_earlier_ruling_decides_is_fast_read_recorded_and_not_shown():
    case = Case(next_to_present="item 3 of 9")
    checked = case.run("check", "--already-decided", "walk x's minutes, item 3 (2026-10-20)")
    check("check --already-decided fast-reads the `#new` texts, as A does, and writes a not-asked answer line",
          checked.returncode == 0 and case.calls.read_text() == NEW_TEXTS
          and re.search(r"\nitem 3 of 9: settled without asking the user, already decided by walk x's minutes, item 3 "
                        r"\(2026-10-20\) #case_against_weak \(\d{4}-\d\d-\d\d \d\d:\d\d\), which makes its change\. Fast reads:\n",
                        case.minutes.read_text()) is not None, described(checked))
    closed = case.run("close")
    lines = closed.stdout.rstrip("\n").split("\n")
    check("close records the item as already decided and accepted, tells the agent to list it, and moves on",
          closed.returncode == 0
          and "\nitem 3 of 9: already decided by walk x's minutes, item 3 (2026-10-20); the walk does not come back to "
              "it. <accepted>\n" in case.minutes.read_text()
          and lines[:3] == ["item 3 of 9 is recorded in the minutes as settled without being shown to the user.",
                            "List it, with its number, in one line of your next message to the user.",
                            "Its change may now be made; the fast reads of the texts it adds:"]
          and sum("fast read had to be run" in line for line in lines) == 2
          and marker(case) == f"#next_to_present item 4 of {WALK_DOCUMENT_COUNTED_M}",
          described(closed) + case.minutes.read_text())


def test_an_item_the_walk_moves_on_from_is_recorded_without_a_fast_read_and_not_shown():
    case = summary_case(next_to_present="item 1 of 5")
    checked = case.run("check", "--moved-on", "the question went to walk y")
    check("check --moved-on runs no fast read, logs no counts, and writes a no-change answer line",
          checked.returncode == 0 and case.calls.read_text() == "" and not case.counts_log.exists()
          and re.search(r"\nitem 1 of 5: settled without asking the user, moved on, no decision: the question went "
                        r"to walk y #case_against_none \(\d{4}-\d\d-\d\d \d\d:\d\d\), which makes no change\.\n$",
                        case.minutes.read_text()) is not None, described(checked))
    closed = case.run("close")
    check("close records the move on, tells the agent to list it, and names the next item",
          closed.returncode == 0
          and "\nitem 1 of 5: moved on, no decision: the question went to walk y; the walk does not come back to it. "
              "<moved on, no decision>\n" in case.minutes.read_text()
          and closed.stdout.rstrip("\n").split("\n") == [
              "item 1 of 5 is recorded in the minutes as settled without being shown to the user.",
              "List it, with its number, in one line of your next message to the user.",
              read_next_item_line(case, "item 2 of 5")]
          and marker(case) == "#next_to_present item 2 of 5", described(closed) + case.minutes.read_text())


def test_an_item_not_shown_needs_no_case_against_line():
    document = WALK_DOCUMENT.replace("#case_against weak: the page grows by one line.\n\n", "")
    for flags in (("--already-decided", "walk x, item 3"), ("--moved-on", "it went to walk y")):
        case = Case(document=document)
        checked = case.run("check", *flags)
        check(f"check {flags[0]} on an item with no `#case_against` line records the answer with no rating",
              checked.returncode == 0 and f"settled without asking the user, " in case.minutes.read_text()
              and "#case_against_" not in case.minutes.read_text(), described(checked))


def test_closing_the_new_item_records_its_outcome_for_the_held_item():
    for flags, outcome, expected_next in (((), "<accepted>", f"item 4 of {WALK_DOCUMENT_COUNTED_M}"),
                                          (("--disapproved",), "<rejected>", f"item 4 of {WALK_DOCUMENT_COUNTED_M}"),
                                          (("--deferred",), None, f"item 3 of {WALK_DOCUMENT_COUNTED_M}")):
        case = Case()
        with open(case.minutes, "a") as minutes:
            minutes.write("item 4 of 9: answer held: item 7 of 9, raised by a fast-read finding, waits for the user's "
                          "answer. <open>\n#next_to_present item 3 of 9\n")
        case.run("check")
        with open(case.minutes, "a") as minutes:
            minutes.write("#next_to_present item 5 of 9\n")
        case.run("close")
        case.run("check", *flags)
        closed = case.run("close")
        held_line = ("item 3 of 9: already decided by the user's answer to item 5 of 9, for which its answer was "
                     f"held; the walk does not come back to it. {outcome}")
        if outcome:
            check(f"closing the new item {outcome} records that outcome for the item held for it, not for one held for "
                  "another item, says so, and the walk goes on past both",
                  closed.returncode == 0 and held_line in case.minutes.read_text()
                  and "item 4 of 9: already decided" not in case.minutes.read_text()
                  and "item 3 of 9, whose answer was held for item 5 of 9, is recorded with item 5 of 9's outcome."
                  in closed.stdout and marker(case) == f"#next_to_present {expected_next}",
                  described(closed) + case.minutes.read_text())
        else:
            check("deferring the new item leaves the held item waiting, so the walk names it next",
                  closed.returncode == 0 and "already decided by the user's answer" not in case.minutes.read_text()
                  and marker(case) == f"#next_to_present {expected_next}", described(closed) + case.minutes.read_text())


def test_closing_the_new_item_records_its_outcome_for_every_item_in_a_chain_of_held_items():
    case = Case()
    with open(case.minutes, "a") as minutes:
        minutes.write("item 4 of 9: answer held: item 3 of 9, raised by a fast-read finding, waits for the user's "
                      "answer. <open>\n#next_to_present item 3 of 9\n")
    case.run("check")
    with open(case.minutes, "a") as minutes:
        minutes.write("#next_to_present item 5 of 9\n")
    case.run("close")
    case.run("check")
    closed = case.run("close")
    text = case.minutes.read_text()
    check("closing item 5, for which item 3 was held, for which item 4 was held, records item 5's outcome for item 3 "
          "and for item 4, each citing the item it was held for, and the walk goes on past all three",
          closed.returncode == 0
          and "item 3 of 9: already decided by the user's answer to item 5 of 9, for which its answer was held; the "
          "walk does not come back to it. <accepted>" in text
          and "item 4 of 9: already decided by the user's answer to item 3 of 9, for which its answer was held; the "
          "walk does not come back to it. <accepted>" in text
          and "item 4 of 9, whose answer was held for item 5 of 9, is recorded with item 5 of 9's outcome."
          in closed.stdout and marker(case) == f"#next_to_present item 6 of {WALK_DOCUMENT_COUNTED_M}",
          described(closed) + text)


def test_the_check_rerun_a_failed_fast_read_names_repeats_the_already_decided_citation():
    case = Case()
    result = case.run("check", "--already-decided", "walk x's minutes, item 3", mode="failed")
    check("a failed fast read under --already-decided tells the agent to rerun check with the citation quoted",
          result.returncode == 1 and "check --already-decided 'walk x'\"'\"'s minutes, item 3'` again" in result.stdout,
          described(result))


SUMMARY_FIRST_DOCUMENT = """# A walk

## Item 1 of 3: summary

The walk asks two things. Say next.

## Item 2 of 3: already recorded in the fixture's minutes

#case_against none.

Recommendation: keep it.

## Item 3 of 3: the opening sentence

#case_against none.

Recommendation: change the sentence.
"""


def test_a_navigation_word_alone_is_refused_as_an_answer_writing_nothing():
    for reply in ("next", "Next.", "N", "continue", "go!", "  NEXT  "):
        for flags in ((), ("--obvious",), ("--after-advisor",), ("--disapproved",), ("--deferred",),
                      ("--option", "2"), ("--part-answer", "1=A")):
            case = Case(next_to_present="item 4 of 9")
            before = case.minutes.read_text()
            result = case.run("check", *flags, reply=reply)
            check(f"check {' '.join(flags)} on the reply {reply!r}, a navigation word alone, is refused, writing "
                  "nothing, and names the moved-on command",
                  result.returncode == 1 and case.minutes.read_text() == before
                  and "is a navigation word alone, which does not approve, disapprove or defer item 4 of 9"
                      in result.stderr
                  and f"check --moved-on-no-decision --user-reply-as-typed {shlex.quote(' '.join(reply.split()))}`"
                      in result.stderr
                  and case.calls.read_text() == "", described(result))


def test_a_navigation_word_inside_a_longer_reply_is_an_answer():
    case = Case(next_to_present="item 4 of 9")
    result = case.run("check", reply="a, next")
    check("a reply that holds a navigation word and more, `a, next`, is recorded as its answer",
          result.returncode == 0 and 'item 4 of 9: the user answered approved #case_against_none ('
          in case.minutes.read_text() and ') in his words "a, next", which makes its change. Fast reads:'
          in case.minutes.read_text(), described(result) + case.minutes.read_text())


def test_moving_on_from_an_item_that_asks_no_decision_records_it_and_presents_the_next():
    case = Case(next_to_present="item 1 of 3", document=SUMMARY_FIRST_DOCUMENT)
    # Only a line close writes decides an item, so item 2's record is close's line, not the fixture's hand-written one.
    case.minutes.write_text("# Minutes\n\nitem 2 of 3: approved; every text the change adds has had a fast read. "
                            "<accepted>\n#next_to_present item 1 of 3\n")
    checked = case.run("check", "--moved-on-no-decision", reply="next")
    closed = case.run("close")
    minutes = case.minutes.read_text()
    check("check --moved-on-no-decision on an item with no case against writes the no-change line with his "
          "words, runs no fast read, and close records <moved on, no decision> and names the next item",
          checked.returncode == 0 and closed.returncode == 0 and case.calls.read_text() == ""
          and re.search(r'\nitem 1 of 3: the user answered moved on, no decision \(\d{4}-\d\d-\d\d \d\d:\d\d\) '
                        r'in his words "next", which makes no change\.\n', minutes)
          and minutes.rstrip().endswith("item 1 of 3: moved on; the item asked for no decision. "
                                        "<moved on, no decision>\n#next_to_present item 3 of 3")
          and closed.stdout.split("\n")[0] == "item 1 of 3 asked for no decision, and the minutes record that the "
                                              "user moved on from it.",
          described(checked) + described(closed) + minutes)


def test_the_users_reply_is_written_beside_his_answer_and_close_still_reads_the_answer():
    reply = 'a trivial - a bit longer\n doesn\'t matter (see #2: "x"), which makes no change.'
    written = 'a trivial - a bit longer doesn\'t matter (see #2: "x"), which makes no change.'
    for flags, word, outcome in (((), "approved", "approved; every text the change adds has had a fast read. "
                                                 "<accepted>"),
                                 (("--obvious",), "approved #approved_obvious",
                                  "approved; every text the change adds has had a fast read. <accepted>"),
                                 (("--deferred",), "deferred",
                                  "deferred; it moves to just before the summary item. <open>")):
        case = Case(next_to_present="item 4 of 9")
        checked = case.run("check", *flags, reply=reply)
        closed = case.run("close")
        minutes = case.minutes.read_text()
        check(f"check {' '.join(flags)} writes the user's reply, its whitespace squeezed, after the date, and "
              "close reads the answer line as before",
              checked.returncode == 0 and closed.returncode == 0
              and re.search(rf'\nitem 4 of 9: the user answered {re.escape(word)} #case_against_none '
                            rf'\(\d{{4}}-\d\d-\d\d \d\d:\d\d\) in his words "{re.escape(written)}", which makes ', minutes)
              and f"\nitem 4 of 9: {outcome}\n" in minutes, described(checked) + described(closed) + minutes)


def test_a_check_without_the_users_reply_is_refused_writing_nothing():
    case = Case(next_to_present="item 4 of 9")
    before = case.minutes.read_text()
    for reply in (None, "  \n "):
        result = case.run("check", "--obvious", reply=reply)
        check(f"check --obvious with the reply {reply!r} is refused, writing nothing, and says how to give it",
              result.returncode == 1 and case.minutes.read_text() == before
              and "check was given no --user-reply-as-typed" in result.stderr
              and "check --obvious --user-reply-as-typed <his reply>`" in result.stderr, described(result))


# Each answer flag that takes a reply, with the values it is given. --not-asked, --already-decided and --moved-on
# take no reply, so no refusal that asks for one repeats them.
ANSWER_FLAGS_TAKING_A_REPLY = {"--obvious": (), "--after-advisor": (), "--disapproved": (), "--deferred": (),
                               "--moved-on-no-decision": (), "--option": ("2",), "--part-answer": ("1=A",)}


def test_every_answer_flag_is_covered_by_the_rerun_command_cases():
    usage = subprocess.run([sys.executable, str(PROGRAM), "--help"], capture_output=True, text=True)
    group = re.search(r"\[(--obvious[^\]]*)\]", " ".join(usage.stdout.split()))
    flags = set(re.findall(r"--[\w-]+", group[1])) if group else set()
    check("the rerun command cases cover every answer flag of check's --help",
          usage.returncode == 0 and flags == {*ANSWER_FLAGS_TAKING_A_REPLY, "--not-asked", "--already-decided", "--moved-on"},
          f"--help answer flags {sorted(flags)}, {described(usage)}")


def test_the_rerun_command_a_refusal_prints_keeps_the_answer_flag():
    unrated = WALK_DOCUMENT.replace("#case_against weak:", "#case_against fairly weak:")
    for flag, values in ANSWER_FLAGS_TAKING_A_REPLY.items():
        flags = " ".join((flag, *values))
        case = Case()
        result = case.run("check", flag, *values, reply=None)
        check(f"check {flags} with no reply is refused with a rerun command that keeps {flag}",
              result.returncode == 1 and f"check {flags} --user-reply-as-typed <his reply>`" in result.stderr,
              described(result))
        case = Case(document=unrated)
        result = case.run("check", flag, *values)
        check(f"check {flags} on a `#case_against` line with no rating is refused with a rerun command that keeps "
              f"{flag}", result.returncode == 1 and f"check {flags} --user-reply-as-typed a` again." in result.stderr,
              described(result))
    case = Case(document=unrated)
    result = case.run("check", "--moved-on", "the item was withdrawn")
    check("check --moved-on on a `#case_against` line with no rating is refused with a rerun command that keeps "
          "--moved-on and its reason",
          result.returncode == 1 and "check --moved-on 'the item was withdrawn'` again." in result.stderr,
          described(result))


def test_a_reply_given_with_not_asked_is_refused_writing_nothing():
    case = Case(next_to_present="item 4 of 9")
    before = case.minutes.read_text()
    result = case.run("check", "--not-asked", "5", "--user-reply-as-typed", "a")
    check("check --not-asked with --user-reply-as-typed is refused, writing nothing",
          result.returncode == 1 and case.minutes.read_text() == before
          and "--user-reply-as-typed was given with --not-asked" in result.stderr, described(result))


def test_a_reply_given_with_already_decided_or_moved_on_is_refused_writing_nothing():
    for flag, value in (("--already-decided", "walk x's minutes, item 3"), ("--moved-on", "the item was withdrawn")):
        case = Case(next_to_present="item 4 of 9")
        before = case.minutes.read_text()
        result = case.run("check", flag, value, "--user-reply-as-typed", "a")
        check(f"check {flag} with --user-reply-as-typed is refused, writing nothing",
              result.returncode == 1 and case.minutes.read_text() == before
              and f"--user-reply-as-typed was given with {flag}" in result.stderr, described(result))


WAITING_ITEM_READ = "approval-walk-waiting-item-cold-read-fast-read"
AFTER_FIXES = "--after-fixes-reread-only-when-facts-change"


def item_read_case(next_to_present="item 2 of 5", recorded=""):
    """A summary walk whose item 1 is decided, so close of item 2 names item 3 and reads item 4 ahead."""
    return summary_case(next_to_present=next_to_present, recorded=recorded or approved_line("item 1 of 5"))


def times_read(case, heading):
    """How many cold-read-fast-reads the stand-in ran on a text holding the heading."""
    return case.calls.read_text().count(heading)


def answered_and_closed(case, mode=""):
    case.run("check")
    return case.run("close", mode=mode, wait_for_reads_ahead=mode != "slow")


def next_item_waiting(case, answered, waiting):
    """Record answered as decided and waiting as next, as a check and close would."""
    with open(case.minutes, "a") as minutes:
        minutes.write(approved_line(answered) + f"#next_to_present {waiting}\n")


def test_close_reads_the_item_after_the_next_one_ahead_and_the_read_step_uses_it():
    case = item_read_case()
    closed = answered_and_closed(case)
    check("close names the read step for the next item and starts the read of the item after it",
          closed.returncode == 0
          and closed.stdout.rstrip("\n").split("\n")[-1] == read_next_item_line(case, "item 3 of 5")
          and times_read(case, "## Item 4 of 5: four") == 1 and times_read(case, "## Item 3 of 5") == 0,
          described(closed) + case.calls.read_text())
    first = case.run(WAITING_ITEM_READ)
    lines = first.stdout.rstrip("\n").split("\n")
    check("the read step runs a read of a waiting item that no read ahead covered, and says so",
          first.returncode == 0
          and lines[0].startswith("item 3 of 5: its cold-read-fast-read, of its text as it stands, had to be run now: ")
          and lines[0].endswith("/cold-read-fast-read.md") and times_read(case, "## Item 3 of 5: three") == 1
          and lines[-1] == "Then present item 3 of 5."
          and f"{WAITING_ITEM_READ} {AFTER_FIXES} --cwd" in lines[2], described(first))
    answered_and_closed(case)
    ahead = case.run(WAITING_ITEM_READ)
    check("the read step hands over the read ahead of an unchanged item without reading it again",
          ahead.returncode == 0
          and ahead.stdout.startswith("item 4 of 5: its cold-read-fast-read, of its text as it stands, was read ahead "
                                      "while the item before it was shown: ")
          and times_read(case, "## Item 4 of 5: four") == 1, described(ahead))
    again = case.run(WAITING_ITEM_READ)
    check("a second read step on the same text runs no read",
          again.returncode == 0 and times_read(case, "## Item 4 of 5: four") == 1, described(again))


def test_an_unnumbered_item_is_read_ahead_as_close_will_number_it():
    case = Case(next_to_present="item 1 of 4", document=UNNUMBERED_ITEMS_DOCUMENT)
    closed = answered_and_closed(case)
    check("close reads the unnumbered item after the next one ahead, its heading as close will number it",
          closed.returncode == 0 and times_read(case, "## Item 3 of 4: three") == 1
          and "\n## three\n" in walk_document(case), described(closed) + case.calls.read_text())
    case.run(WAITING_ITEM_READ)
    answered_and_closed(case)
    ahead = case.run(WAITING_ITEM_READ)
    check("once close numbers that item, the read step hands over its read ahead without reading it again",
          ahead.returncode == 0
          and ahead.stdout.startswith("item 3 of 4: its cold-read-fast-read, of its text as it stands, was read ahead")
          and times_read(case, "## Item 3 of 4: three") == 1, described(ahead) + case.calls.read_text())


def test_the_read_step_waits_for_a_read_ahead_still_running():
    case = item_read_case()
    answered_and_closed(case, mode="slow")
    next_item_waiting(case, "item 3 of 5", "item 4 of 5")
    no_outcome_yet = not any(case.reads().glob("*-outcome.json"))
    result = case.run(WAITING_ITEM_READ)
    check("the read step waits for the read ahead that is still running and uses it",
          no_outcome_yet and result.returncode == 0
          and "was read ahead while the item before it was shown" in result.stdout
          and times_read(case, "## Item 4 of 5: four") == 1, described(result))


def test_an_item_changed_after_its_read_ahead_started_is_read_again():
    case = item_read_case()
    answered_and_closed(case)
    document = case.checkout / "docs" / "walk" / f"{WALK_NAME}.md"
    document.write_text(document.read_text().replace("## Item 4 of 5: four", "## Item 4 of 5: four, revised"))
    next_item_waiting(case, "item 3 of 5", "item 4 of 5")
    result = case.run(WAITING_ITEM_READ)
    check("an item whose text changed after its read ahead started is read again as it stands",
          result.returncode == 0 and "had to be run now: " in result.stdout
          and times_read(case, "## Item 4 of 5: four, revised") == 1, described(result))


def test_a_read_ahead_that_failed_or_ended_without_an_outcome_is_run_again():
    case = item_read_case()
    answered_and_closed(case, mode="failed")
    next_item_waiting(case, "item 3 of 5", "item 4 of 5")
    result = case.run(WAITING_ITEM_READ)
    check("a read ahead that failed is run again before the item is shown, naming the failure",
          result.returncode == 0
          and result.stdout.startswith("item 4 of 5: its cold-read-fast-read, of its text as it stands, had to be run "
                                       "now, because the read started ahead of it failed: FAILED: the stand-in "
                                       "cold-read-cell failed twice: ")
          and times_read(case, "## Item 4 of 5: four") == 2, described(result))
    case = item_read_case()
    answered_and_closed(case)
    for outcome in case.reads().glob("*-outcome.json"):
        outcome.unlink()  # As a worker killed before it wrote its outcome leaves the directory.
    next_item_waiting(case, "item 3 of 5", "item 4 of 5")
    result = case.run(WAITING_ITEM_READ)
    check("a read ahead whose worker ended without an outcome is run again, naming its log",
          result.returncode == 0
          and "because the read started ahead of it ended without writing its outcome; its output is in " in result.stdout
          and times_read(case, "## Item 4 of 5: four") == 2, described(result))


def test_a_failed_read_ahead_is_not_started_again_by_later_read_steps():
    case = item_read_case()
    answered_and_closed(case, mode="failed")
    case.run(WAITING_ITEM_READ)
    case.run(WAITING_ITEM_READ, AFTER_FIXES)
    check("read steps for the item before a failed read ahead do not start that read ahead again",
          times_read(case, "## Item 4 of 5: four") == 1, case.calls.read_text())


def test_a_read_ahead_that_cannot_find_its_item_never_stops_close_or_the_read_step():
    case = item_read_case()
    document = case.checkout / "docs" / "walk" / f"{WALK_NAME}.md"
    document.write_text(document.read_text().replace("## Item 5 of 5", "## Item 4 of 5: four again\n\n## Item 5 of 5"))
    closed = answered_and_closed(case)
    lines = closed.stdout.rstrip("\n").split("\n")
    not_started = ("No cold-read-fast-read could be started ahead for the item after item 3 of 5; this needs nothing "
                   "from you now, since when that item waits its read step reads it or reports the problem again. "
                   "The problem: the item after item 3 of 5, `item 4 of 5`: ")
    check("close whose read ahead cannot find its item names the next item, saying in one line why no read ahead started",
          closed.returncode == 0 and lines[-1] == read_next_item_line(case, "item 3 of 5")
          and lines[-2].startswith(not_started) and closed.stdout.count(not_started) == 1
          and marker(case) == "#next_to_present item 3 of 5" and times_read(case, "## Item") == 0, described(closed))
    read = case.run(WAITING_ITEM_READ)
    check("the read step reads its own item when the read ahead of the item after it cannot find that item",
          read.returncode == 0 and read.stdout.startswith(not_started)
          and "item 3 of 5: its cold-read-fast-read, of its text as it stands, had to be run now: " in read.stdout
          and times_read(case, "## Item 3 of 5: three") == 1, described(read))


def test_a_read_that_fails_in_the_read_step_says_not_to_present_the_item():
    case = item_read_case()
    answered_and_closed(case)
    result = case.run(WAITING_ITEM_READ, mode="failed")
    lines = result.stdout.rstrip("\n").split("\n")
    check("a failed read of the waiting item exits 1 and says not to present it, with the command to run again",
          result.returncode == 1 and lines[0] == "FAILED: the stand-in cold-read-cell failed twice"
          and lines[1].startswith("item 3 of 5 has had no cold-read-fast-read of its text as it stands, so do not "
                                  "present it yet")
          and lines[2] == (f"Run `python3 {PROGRAM} {WAITING_ITEM_READ} --cwd "
                           f"{shlex.quote(str(case.checkout.resolve()))}` again once."), described(result))
    retried = case.run(WAITING_ITEM_READ)
    check("the read step after a failed read reads the item, naming no read ahead",
          retried.returncode == 0 and "had to be run now: " in retried.stdout
          and "started ahead" not in retried.stdout, described(retried))


def test_the_last_item_and_a_closed_walk_start_no_read_ahead():
    recorded = "".join(approved_line(f"item {number} of 5") for number in (1, 2, 3))
    case = summary_case(next_to_present="item 4 of 5", recorded=recorded)
    answered_and_closed(case)
    check("close of the item before the last starts no read ahead, since no item comes after the last",
          case.calls.read_text() == "" and not case.reads().exists(), case.calls.read_text())
    case.run(WAITING_ITEM_READ)
    case.run("check", "--moved-on-no-decision", "--user-reply-as-typed", "next")
    closed = case.run("close")
    check("close that closes the walk starts no read",
          closed.returncode == 0
          and closed.stdout.rstrip("\n").endswith("go on to the walk-me-through skill's closing.")
          and times_read(case, "## Item") == 1, described(closed) + case.calls.read_text())


def after_fixes_case(old, new):
    """A case whose item 3 was read, then changed from old to new in the walk-document."""
    case = item_read_case()
    answered_and_closed(case)
    case.run(WAITING_ITEM_READ)
    document = case.checkout / "docs" / "walk" / f"{WALK_NAME}.md"
    text = document.read_text()
    if old not in text:
        raise AssertionError(f"{old!r} is not in the walk-document")
    document.write_text(text.replace(old, new))
    return case, case.run(WAITING_ITEM_READ, AFTER_FIXES)


ITEM_3_HEADING = "## Item 3 of 5: three\n"


def test_a_fix_that_touches_no_fact_is_not_read_again():
    case, result = after_fixes_case(ITEM_3_HEADING, ITEM_3_HEADING + "\nThis item, e.g. this one, asks little.\n")
    check(f"{AFTER_FIXES} after a wording fix runs no read and says to present the item",
          result.returncode == 0
          and result.stdout.startswith("item 3 of 5: no new cold-read-fast-read: your changes since its last one (")
          and result.stdout.rstrip("\n").split("\n")[-1] == "Present item 3 of 5."
          and times_read(case, ITEM_3_HEADING) == 1, described(result))
    second = case.run(WAITING_ITEM_READ, AFTER_FIXES)
    check(f"a second {AFTER_FIXES} compares with the text last read, not the text it let pass",
          second.returncode == 0 and "no new cold-read-fast-read" in second.stdout, described(second))


def test_a_fix_is_compared_with_the_items_own_read_not_a_newer_read_of_another_item():
    case = item_read_case()
    answered_and_closed(case)
    case.run(WAITING_ITEM_READ)
    for path in case.reads().glob("*-outcome.json"):
        outcome = json.loads(path.read_text())
        if outcome["item"] == "item 4 of 5":
            path.write_text(json.dumps(dict(outcome, finished=time.time() + 3600)))
    document = case.checkout / "docs" / "walk" / f"{WALK_NAME}.md"
    document.write_text(document.read_text().replace(ITEM_3_HEADING, ITEM_3_HEADING + "\nThis item asks little.\n"))
    result = case.run(WAITING_ITEM_READ, AFTER_FIXES)
    check(f"{AFTER_FIXES} after a wording fix runs no read though another item's read finished later",
          result.returncode == 0 and "no new cold-read-fast-read" in result.stdout
          and times_read(case, ITEM_3_HEADING) == 1, described(result))


def test_a_fix_that_changes_only_the_spacing_inside_a_code_span_is_read_again():
    case = item_read_case()
    document = case.checkout / "docs" / "walk" / f"{WALK_NAME}.md"
    document.write_text(document.read_text().replace(ITEM_3_HEADING, ITEM_3_HEADING + "\nIt edits `poem list`.\n"))
    answered_and_closed(case)
    case.run(WAITING_ITEM_READ)
    document.write_text(document.read_text().replace("`poem list`", "`poem  list`"))
    result = case.run(WAITING_ITEM_READ, AFTER_FIXES)
    check(f"{AFTER_FIXES} after a fix that changes only the spacing inside a code span reads the item again",
          result.returncode == 0 and "had to be run now, because your changes since" in result.stdout
          and times_read(case, ITEM_3_HEADING) == 2, described(result))


def test_a_fix_that_touches_a_fact_is_read_again():
    added = ITEM_3_HEADING + "\n{}\n"
    for name, old, new, fact in (
            ("a number", ITEM_3_HEADING, added.format("It costs 4 hours."), "4"),
            ("a backquoted name", ITEM_3_HEADING, added.format("It edits `poem list`."), "`poem list`"),
            ("a backquoted name after a parenthesis", ITEM_3_HEADING, added.format("It edits (`poems`)."),
             "(`poems`)."),
            ("an autolink with no //", ITEM_3_HEADING, added.format("Write to <mailto:poems@localhost>."),
             "<mailto:poems@localhost>"),
            ("a file name by its extension", ITEM_3_HEADING, added.format("It edits poems.yaml."), "poems.yaml."),
            ("a link", ITEM_3_HEADING, added.format("See [the page](../poems)."),
             "[the page](../poems)"),
            ("the recommendation", "#case_against none.\n\n\nRecommendation: leave it.\n\n## Item 4",
             "#case_against none.\n\n\nRecommendation: drop it.\n\n## Item 4", '"Recommendation: drop it."'),
            ("the alternative", "#case_against none.\n\n\nRecommendation: leave it.\n\n## Item 4",
             "#case_against none.\n\n\nThe alternative: drop it. Recommendation: leave it.\n\n## Item 4",
             '"The alternative: drop it. Recommendation'),
            ("the case against", ITEM_3_HEADING + "\n#case_against none.", ITEM_3_HEADING + "\n#case_against weak.",
             '"#case_against weak."')):
        case, result = after_fixes_case(old, new)
        first = result.stdout.split("\n")[0]
        check(f"{AFTER_FIXES} after a fix that changes {name} reads the item again and names the fact",
              result.returncode == 0
              and "had to be run now, because your changes since its last cold-read-fast-read (" in first
              and fact in first.split(") touch ", 1)[-1]
              and times_read(case, ITEM_3_HEADING) == 2, described(result))


def test_a_file_or_path_git_lists_counts_as_a_fact_and_git_failing_counts_every_change():
    program = load_program()
    top = SUITE_ROOT / "facts-git"
    (top / "scripts").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(top)], check=True)
    (top / "scripts" / "poem-index").write_text("x")
    subprocess.run(["git", "-C", str(top), "add", "scripts/poem-index"], check=True)
    named = program.approval_walk_item_before_and_after_fixes_compare_for_changed_fact_words_needing_another_cold_read_fast_read("It runs a tool.", "It runs poem-index.", top)
    check("a changed word git ls-files lists, by path, directory or file name, is a fact",
          named == ["poem-index."]
          and program.approval_walk_item_before_and_after_fixes_compare_for_changed_fact_words_needing_another_cold_read_fast_read("Look in a place.", "Look in scripts/.", top) == ["scripts/."]
          and program.approval_walk_item_before_and_after_fixes_compare_for_changed_fact_words_needing_another_cold_read_fast_read("It runs a tool.", "It runs a script.", top) == []
          and program.approval_walk_item_before_and_after_fixes_compare_for_changed_fact_words_needing_another_cold_read_fast_read(
              "It reads <the item>.", "It reads <the item> [advisor].", top) == [], repr(named))
    not_a_checkout = SUITE_ROOT / "facts-no-git"
    not_a_checkout.mkdir()
    facts = program.approval_walk_item_before_and_after_fixes_compare_for_changed_fact_words_needing_another_cold_read_fast_read("It runs a tool.", "It runs a script.", not_a_checkout)
    check("when git ls-files fails, every changed word counts, so the item is read again",
          len(facts) == 1 and facts[0].startswith("every changed word, since `git ls-files` failed in "), repr(facts))
    check("an unchanged text touches no fact even when git ls-files fails",
          program.approval_walk_item_before_and_after_fixes_compare_for_changed_fact_words_needing_another_cold_read_fast_read("It runs a tool.", "It runs a tool.", not_a_checkout) == [], "")



CATEGORY_TAG = "#approval_walk_item_in_category_"
WAITING_ITEM_READ_STEP_NAME = "approval-walk-waiting-item-cold-read-fast-read"


def unshown_item(title, *lines):
    """An unnumbered walk-document item headed `## title`, with lines under it, rated and recommended."""
    return "\n\n".join([f"## {title}", *lines, "#case_against none.", "Recommendation: approve."]) + "\n\n"


def ordered_walk(*items):
    """A walk-document whose item 1 is shown, then items, then an unnumbered summary item."""
    return ("# A walk in which code picks the order\n\n## Item 1 of 9: one\n\n#case_against none.\n\n"
            "Recommendation: approve.\n\n" + "".join(items) + "## Summary\n\nThe walk in short.\n")


def titles_shown_in_turn(case, answers=None):
    """Approve each waiting item in turn, or answer it with the check flags answers gives for the k-th close, and
    return the title of the item close names next each time, until it names the summary item or close fails."""
    shown = []
    for turn in range(12):
        case.run("check", *(answers or {}).get(turn, ()))
        closed = case.run("close")
        if closed.returncode != 0:
            return shown + [f"close failed: {closed.stderr}"]
        named = re.search(r"#next_to_present item ([\d.]+) of", marker(case))
        if not named:
            return shown
        heading = re.search(rf"^## Item {re.escape(named[1])} of \d+(?: \(deferred[^)]*\))?: (.*)$",
                            walk_document(case), re.M)
        shown.append(heading[1] if heading else f"no heading for item {named[1]}")
        if shown[-1] == "Summary":
            return shown
    return shown


def test_unshown_items_are_shown_by_category_then_first_entered_day_then_walk_document_order():
    case = Case(next_to_present="item 1 of 9", document=ordered_walk(
        unshown_item("maintenance", f"{CATEGORY_TAG}fix_during_maintenance"),
        unshown_item("an improvement", f"{CATEGORY_TAG}file_an_improvement_feature_or_change"),
        unshown_item("next, entered later", f"{CATEGORY_TAG}fix_next", "#approval_walk_item_first_entered 2026-11-04"),
        unshown_item("next, entered first", f"- **{CATEGORY_TAG}fix_next**",
                     "#approval_walk_item_first_entered 2026-10-30"),
        unshown_item("must fix, entered later", f"{CATEGORY_TAG}must_fix_now",
                     "#approval_walk_item_first_entered 2026-11-02"),
        unshown_item("must fix, same day, written first", f"{CATEGORY_TAG}must_fix_now",
                     "#approval_walk_item_first_entered 2026-11-01"),
        unshown_item("must fix, same day, written second", f"{CATEGORY_TAG}must_fix_now",
                     "#approval_walk_item_first_entered 2026-11-01")))
    shown = titles_shown_in_turn(case)
    check("unshown items come by category, must fix now first and file an improvement last, then by the day each "
          "first entered a walk, then in walk-document order, and the summary item stays last",
          shown == ["must fix, same day, written first", "must fix, same day, written second",
                    "must fix, entered later", "next, entered first", "next, entered later", "maintenance",
                    "an improvement", "Summary"], f"{shown}\n{walk_document(case)}")
    check("each item is numbered in the order it is shown, so no number is skipped or used twice",
          sorted(int(number) for number in re.findall(r"^## Item (\d+) of", walk_document(case), re.M))
          == list(range(1, 10)), walk_document(case))


def test_an_item_comes_after_the_items_it_waits_on_and_an_item_that_unblocks_another_comes_as_early():
    case = Case(next_to_present="item 1 of 9", document=ordered_walk(
        unshown_item("next", f"{CATEGORY_TAG}fix_next"),
        unshown_item("urgent but blocked", f"{CATEGORY_TAG}must_fix_now",
                     "#approval_walk_item_waits_on ## Item 9 of 9: The  Prerequisite"),
        unshown_item("the prerequisite", f"{CATEGORY_TAG}fix_during_maintenance")))
    shown = titles_shown_in_turn(case)
    check("an item comes after the item it waits on, named by its heading in any case, count or spacing, and an item waited on comes as "
          "early as the item waiting on it would, so a maintenance item that unblocks a must-fix-now item comes "
          "before a fix-next item",
          shown == ["the prerequisite", "urgent but blocked", "next", "Summary"], f"{shown}\n{walk_document(case)}")


def test_an_unshown_item_waiting_on_a_deferred_item_comes_after_it():
    case = Case(next_to_present="item 1 of 9", document=ordered_walk(
        unshown_item("two", f"{CATEGORY_TAG}must_fix_now"),
        unshown_item("three", f"{CATEGORY_TAG}must_fix_now", "#approval_walk_item_waits_on two"),
        unshown_item("four", f"{CATEGORY_TAG}fix_next")))
    shown = titles_shown_in_turn(case, answers={1: ("--deferred",)})
    check("an item waiting on a shown item the user deferred is passed over until that item is decided, and the "
          "shown item keeps its number",
          shown == ["two", "four", "two", "three", "Summary"]
          and re.search(r"^## Item 2 of \d+: two$", walk_document(case), re.M) is not None,
          f"{shown}\n{walk_document(case)}")


def numbered_item(number, title):
    """A numbered walk-document item `## Item number of 9: title`, not yet answered."""
    return f"## Item {number} of 9: {title}\n\n#case_against none.\n\nRecommendation: approve.\n\n"


def test_repeated_closes_keep_the_unshown_items_together_and_numbered_items_in_order():
    case = Case(next_to_present="item 1 of 9", document=ordered_walk(
        unshown_item("next", f"{CATEGORY_TAG}fix_next"), numbered_item(3, "three"),
        unshown_item("urgent", f"{CATEGORY_TAG}must_fix_now"), numbered_item(4, "four")))
    shown = titles_shown_in_turn(case)
    check("once an unshown item is shown, the other unshown items come next, and numbered items keep their order, "
          "even when a numbered item stands between unshown ones in the walk-document",
          shown == ["urgent", "next", "three", "four", "Summary"], f"{shown}\n{walk_document(case)}")
    case = Case(next_to_present="item 1 of 9", document=ordered_walk(
        numbered_item(2, "two"), unshown_item("first", f"{CATEGORY_TAG}must_fix_now"), numbered_item(3, "three"),
        unshown_item("second", f"{CATEGORY_TAG}must_fix_now")))
    shown = titles_shown_in_turn(case)
    check("a numbered item that stands between two unshown items in the walk-document comes after both",
          shown == ["two", "first", "second", "three", "Summary"], f"{shown}\n{walk_document(case)}")


def test_an_item_can_wait_on_an_item_whose_title_ends_in_inline_code():
    case = Case(next_to_present="item 1 of 9", document=ordered_walk(
        unshown_item("the waiting one", f"{CATEGORY_TAG}must_fix_now",
                     "#approval_walk_item_waits_on run `close`"),
        unshown_item("run `close`", f"{CATEGORY_TAG}fix_next")))
    shown = titles_shown_in_turn(case)
    check("a waits-on line naming a title that ends in inline code finds that item, and the item waiting comes after",
          shown == ["run `close`", "the waiting one", "Summary"], f"{shown}\n{walk_document(case)}")


def test_a_category_tag_in_underscore_emphasis_is_read_without_the_closing_underscores():
    for tag in (f"_{CATEGORY_TAG}must_fix_now_", f"__{CATEGORY_TAG}must_fix_now__"):
        case = Case(next_to_present="item 1 of 9", document=ordered_walk(
            unshown_item("later", f"{CATEGORY_TAG}fix_next"), unshown_item("emphasised", tag)))
        shown = titles_shown_in_turn(case)
        check(f"the category tag in `{tag}` is read as must_fix_now, not refused with the emphasis's underscores",
              shown == ["emphasised", "later", "Summary"], f"{shown}\n{walk_document(case)}")


def test_gathering_unshown_items_keeps_a_numbered_item_written_as_a_bold_paragraph():
    """The last unshown item ends the file with no blank line after it, and gathering moves it just above a
    numbered item written as a `**Item N of M: ...**` paragraph."""
    document = ("# A walk in which code picks the order\n\n## Item 1 of 9: one\n\n#case_against none.\n\n"
                "Recommendation: approve.\n\n" + unshown_item("urgent", f"{CATEGORY_TAG}must_fix_now")
                + "**Item 2 of 9: two**\n\n#case_against none.\n\nRecommendation: approve.\n\n"
                + unshown_item("later", f"{CATEGORY_TAG}fix_next").rstrip("\n"))
    case = Case(next_to_present="item 1 of 9", document=document)
    case.run("check")
    closed = case.run("close")
    text = walk_document(case)
    check("close shows urgent as a new number and keeps item 2, written as a bold paragraph, as an item of its own",
          closed.returncode == 0 and text.count("**Item 2 of 9: two**") == 1
          and re.search(r"^## Item 3 of \d+: urgent$", text, re.M) is not None
          and re.search(r"Recommendation: approve\.\n\n\*\*Item 2 of 9: two\*\*", text) is not None,
          f"exit {closed.returncode}, stderr {closed.stderr!r}\n{text}")


def test_gathering_puts_an_unshown_item_standing_above_answered_items_after_the_last_answered_one():
    document = ("# A walk in which code picks the order\n\n" + numbered_item(1, "one")
                + unshown_item("above", f"{CATEGORY_TAG}must_fix_now") + numbered_item(2, "two")
                + numbered_item(3, "three") + "## Summary\n\nThe walk in short.\n")
    case = Case(next_to_present="item 2 of 9", document=document)
    shown = titles_shown_in_turn(case)
    text = walk_document(case)
    check("an unshown item that stands above the answered items is shown after them, and moved below the last "
          "answered one, so items stand in the order they were shown",
          shown[:2] == ["three", "above"] and re.search(r"^## Item 4 of \d+: above$", text, re.M) is not None
          and text.index("## Item 2 of 9: two") < text.index("## Item 3 of 9: three") < text.index(": above\n"),
          f"{shown}\n{text}")


def test_gathering_places_unshown_items_after_the_answered_items_heading_the_minutes_total_picks():
    """A walk-document renumbered before numbers were never reused keeps two headings for item 2, `of 3` and `of 4`,
    as md-skills-seat-open-decisions-2026-10-13.md does for its items 22 to 27; the minutes' `of 3` picks the
    first, so gathering must not move the unshown item past item 3 to below the other heading."""
    document = ("# A walk in which code picks the order\n\n"
                "## Item 1 of 3: one\n\n#case_against none.\n\nRecommendation: approve.\n\n"
                "## Item 2 of 3: two\n\n#case_against none.\n\nRecommendation: approve.\n\n"
                + unshown_item("added", f"{CATEGORY_TAG}must_fix_now")
                + "## Item 3 of 3: three\n\n#case_against none.\n\nRecommendation: approve.\n\n"
                "## Item 2 of 4: two, as an earlier count had it\n\n#case_against none.\n\nRecommendation: approve.\n\n"
                "## Summary\n\nThe walk in short.\n")
    case = Case(next_to_present="item 2 of 3", document=document)
    shown = titles_shown_in_turn(case)
    check("with two headings for the answered item, gathering keeps the unshown item after the heading the minutes' "
          "total picks, so item 3 is shown before the summary item",
          shown == ["added", "three", "Summary"], f"{shown}\n{walk_document(case)}")


def test_close_hold_answer_numbers_a_new_item_that_waits_on_a_decided_or_the_answered_item():
    """The hold path refuses a new item waiting on a numbered item still to come; one waiting on an item the minutes
    already decide, or on the item whose answer it holds, has nothing to wait for and is numbered."""
    for name, waits_on in (("an item the minutes already decide", "one"), ("the item whose answer it holds", "two")):
        case = Case(next_to_present="item 2 of 4",
                    document=UNNUMBERED_ITEMS_DOCUMENT.replace("## two", "## Item 2 of 4: two"))
        case.minutes.write_text(case.minutes.read_text().replace(
            "#next_to_present item 2 of 4", "item 1 of 4: approved; every text the change adds has had a fast read. "
                                            "<accepted>\n#next_to_present item 2 of 4"))
        case.run("check")
        document = walk_document(case).replace("## three", f"## the change a finding raised\n\n{FIX_NEXT_LINE}\n\n"
                                               f"#approval_walk_item_waits_on {waits_on}\n\n#case_against none.\n\n"
                                               "## three", 1)
        (case.checkout / "docs" / "walk" / f"{WALK_NAME}.md").write_text(document)
        closed = case.run("close", "--hold-answer-until-new-item-answered")
        check(f"close --hold-answer-until-new-item-answered numbers a new item that waits on {name}",
              closed.returncode == 0 and marker(case).startswith("#next_to_present item 3 of ")
              and re.search(r"^## Item 3 of \d+: the change a finding raised$", walk_document(case), re.M) is not None,
              described(closed) + walk_document(case))


def test_close_writes_no_walk_document_when_gathering_would_lose_an_item():
    """Gathering keeps blank lines at its joins, so it cannot lose an item; a stand-in walk finder that reads one
    item fewer after gathering is put into the program, run in this process."""
    case = Case(next_to_present="item 1 of 9", document=ordered_walk(
        unshown_item("next", f"{CATEGORY_TAG}fix_next"), numbered_item(3, "three"),
        unshown_item("urgent", f"{CATEGORY_TAG}must_fix_now")))
    case.run("check")
    program = load_program()
    original = program.unshown_items_gathered_behind_chosen

    def gathered_with_an_item_lost(walk_finder, *rest):
        class Finder:
            def __getattr__(self, name):
                return getattr(walk_finder, name)

            def item_unit_spans(self, text, parser):
                return walk_finder.item_unit_spans(text, parser)[:-1]
        return original(Finder(), *rest)

    program.unshown_items_gathered_behind_chosen = gathered_with_an_item_lost
    markers = case.minutes.read_text().count("#next_to_present")
    errors = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
        exit_code = program.main(["close", *case_paths(case)])
    text = walk_document(case)
    check("close exits 1, names the defect, neither moves nor numbers an item and adds no `#next_to_present` line "
          "when gathering would lose an item",
          exit_code == 1 and "would have left fewer items than it found" in errors.getvalue()
          and text.index("## next") < text.index("## Item 3 of 9: three") < text.index("## urgent")
          and case.minutes.read_text().count("#next_to_present") == markers,
          f"exit {exit_code}, stderr {errors.getvalue()!r}\n{text}")


def test_close_writes_nothing_when_the_stamped_walk_document_no_longer_places():
    """The first-entered stamp is written so that it cannot make a document unplaceable, so a stand-in stamp that
    does so is put into the program, run in this process."""
    case = Case(next_to_present="item 1 of 9", document=ordered_walk(unshown_item("two", f"{CATEGORY_TAG}fix_next")))
    case.run("check")
    document, minutes = walk_document(case), case.minutes.read_text()
    program = load_program()
    program.unshown_items_first_entered_stamped = lambda walk_finder, text, *_: text.replace(
        f"{CATEGORY_TAG}fix_next", f"{CATEGORY_TAG}fix_next {CATEGORY_TAG}must_fix_now")
    errors = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
        exit_code = program.main(["close", *case_paths(case)])
    check("close exits 1 and leaves the walk-document and the minutes as they were when the stamped walk-document "
          "cannot be placed",
          exit_code == 1 and "more than one category tag" in errors.getvalue()
          and walk_document(case) == document and case.minutes.read_text() == minutes,
          f"exit {exit_code}, stderr {errors.getvalue()!r}\n{walk_document(case)}")


def test_close_writes_the_first_entered_day_once_into_each_unshown_item_that_has_none():
    case = Case(next_to_present="item 1 of 9", document=ordered_walk(
        unshown_item("two", f"{CATEGORY_TAG}fix_next"),
        unshown_item("three", f"{CATEGORY_TAG}fix_next", "#approval_walk_item_first_entered 2026-10-01")))
    before = datetime.date.today().isoformat()
    case.run("check")
    closed = case.run("close")
    days = {before, datetime.date.today().isoformat()}
    document = walk_document(case)
    check("close writes `#approval_walk_item_first_entered <today>` under the heading of an unshown item with no "
          "such line, leaves an item's own date alone, and shows the item first entered earlier first",
          closed.returncode == 0
          and any(f"## two\n\n#approval_walk_item_first_entered {day}\n\n{CATEGORY_TAG}fix_next" in document
                  for day in days)
          and document.count("#approval_walk_item_first_entered") == 2
          and "#approval_walk_item_first_entered 2026-10-01" in document
          and marker(case) == "#next_to_present item 2 of 4" and "\n## Item 2 of 4: three\n" in document,
          described(closed) + document)
    case.run("check")
    case.run("close")
    check("a later close writes no second date", walk_document(case).count("#approval_walk_item_first_entered") == 2,
          walk_document(case))


def test_the_first_entered_line_close_writes_keeps_indented_code_under_the_heading_out_of_its_paragraph():
    code = f"    {CATEGORY_TAG}must_fix_now"
    case = Case(next_to_present="item 1 of 9", document=ordered_walk(
        f"## three\n{code}\n\n{CATEGORY_TAG}fix_next\n\n#case_against none.\n\nRecommendation: approve.\n\n"))
    case.run("check")
    closed = case.run("close")
    document = walk_document(case)
    check("close leaves a blank line after the first-entered line it writes above indented code, so the code's "
          "category tag is not read as the item's second one, and the item is shown",
          closed.returncode == 0 and "Traceback" not in closed.stderr
          and re.search(rf"#approval_walk_item_first_entered \S+\n\n{re.escape(code)}\n", document) is not None
          and marker(case) == "#next_to_present item 2 of 3", described(closed) + document)


def refused_walk_order(name, *items, expected):
    case = Case(next_to_present="item 1 of 9", document=ordered_walk(*items))
    case.run("check")
    document, minutes = walk_document(case), case.minutes.read_text()
    closed = case.run("close")
    check(f"close refuses, writing nothing, {name}",
          closed.returncode == 1 and expected in closed.stderr and "nothing written" in closed.stderr
          and "`#approval_walk_item_in_category_must_fix_now`" in closed.stderr and " close --cwd " in closed.stderr
          and "Traceback" not in closed.stderr
          and walk_document(case) == document and case.minutes.read_text() == minutes, described(closed))


def test_close_refuses_an_unshown_item_it_cannot_place():
    refused_walk_order("when an unshown item has no category line", unshown_item("two"),
                       expected="the item `## two` in ")
    refused_walk_order("when an unshown item names its category only inside its prose",
                       unshown_item("two", f"The tag `{CATEGORY_TAG}fix_next` is not on a line of its own."),
                       expected="has no `#approval_walk_item_in_category_<category>` line")
    refused_walk_order("when an unshown item has two category lines",
                       unshown_item("two", f"{CATEGORY_TAG}fix_next", f"{CATEGORY_TAG}must_fix_now"),
                       expected="more than one category tag: `#approval_walk_item_in_category_fix_next`, "
                                "`#approval_walk_item_in_category_must_fix_now`")
    refused_walk_order("when an unshown item has two category tags on one line",
                       unshown_item("two", f"{CATEGORY_TAG}fix_next {CATEGORY_TAG}fix_next"),
                       expected="more than one category tag")
    refused_walk_order("when an unshown item's category tag is not one of the four",
                       unshown_item("two", f"{CATEGORY_TAG}soon"),
                       expected="the category tag `#approval_walk_item_in_category_soon`, which is not one of the four")
    refused_walk_order("when an unshown item waits on a title no item heading has",
                       unshown_item("two", f"{CATEGORY_TAG}fix_next", "#approval_walk_item_waits_on tree"),
                       expected="waits on `tree`, which is the title of no other item heading")
    refused_walk_order("when an unshown item waits on itself",
                       unshown_item("two", f"{CATEGORY_TAG}fix_next", "#approval_walk_item_waits_on two"),
                       expected="waits on `two`, which is the title of no other item heading")
    refused_walk_order("when unshown items wait on each other in a circle",
                       unshown_item("two", f"{CATEGORY_TAG}fix_next", "#approval_walk_item_waits_on four"),
                       unshown_item("three", f"{CATEGORY_TAG}fix_next", "#approval_walk_item_waits_on two"),
                       unshown_item("four", f"{CATEGORY_TAG}fix_next", "#approval_walk_item_waits_on three"),
                       expected="the items `## two`, `## three`, `## four` in ")
    refused_walk_order("when an unshown item's first-entered date is not written YYYY-MM-DD",
                       unshown_item("two", f"{CATEGORY_TAG}fix_next", "#approval_walk_item_first_entered 4 Nov"),
                       expected="the line `#approval_walk_item_first_entered 4 Nov`, whose date is not a date")


def test_the_read_step_refuses_an_unshown_item_it_cannot_place_and_close_goes_on_once_it_is_tagged():
    case = Case(next_to_present="item 1 of 9", document=ordered_walk(unshown_item("two")))
    read = case.run(WAITING_ITEM_READ_STEP_NAME)
    check("the waiting item's read step refuses while an unshown item has no category, so the agent tags it before "
          "the user answers",
          read.returncode == 1 and "has no `#approval_walk_item_in_category_<category>` line" in read.stderr
          and f" {WAITING_ITEM_READ_STEP_NAME} --cwd " in read.stderr, described(read))
    document = walk_document(case).replace(
        "## two\n", f"## two\n\n{CATEGORY_TAG}file_an_improvement_feature_or_change\n")
    (case.checkout / "docs" / "walk" / f"{WALK_NAME}.md").write_text(document)
    case.run("check")
    closed = case.run("close")
    check("once the item is tagged as the refusal says, close shows it",
          closed.returncode == 0 and marker(case) == "#next_to_present item 2 of 3", described(closed))


def held_pull_requests(*held):
    """A `gh pr list --json number,reviews` output: one pull request per (number, [review bodies])."""
    return json.dumps([{"number": number, "reviews": [{"body": body} for body in bodies]} for number, bodies in held])


def gh_environment(pull_requests="[]", mode="", comment_fails=""):
    return dict(os.environ, GH_STAND_IN_PULL_REQUESTS=pull_requests, GH_STAND_IN_MODE=mode,
                GH_STAND_IN_COMMENT_FAILS=comment_fails)


HELD_ON_ITEM_4 = f"#held_on_ruling {WALK_NAME} item 4"


def test_close_posts_the_ruling_on_each_open_pull_request_held_on_the_answered_item_and_on_no_other():
    pull_requests = held_pull_requests(
        (101, [f"Held.\n\n  {HELD_ON_ITEM_4}  \n\nIf he approves that item, this pull request merges."]),
        (102, ["Looks fine.", None, HELD_ON_ITEM_4]),
        (103, [f"#held_on_ruling {WALK_NAME} item 44"]),
        (104, ["#held_on_ruling another-walk-2026-10-30 item 4"]),
        (105, [f"Merge-lane-2 writes `{HELD_ON_ITEM_4}` in its review."]),
        (106, []))
    for flags, word in (((), "approved"), (("--option", "2"), "approved"), (("--disapproved",), "disapproved"),
                        (("--deferred",), "deferred"), (("--moved-on-no-decision",), "moved_on"),
                        (("--part-answer", "1=A", "--part-answer", "2=D"), "part_answers"),
                        (("--already-decided", "walk x, item 3"), "approved"),
                        (("--moved-on", "it went to walk y"), "moved_on")):
        case = Case(next_to_present="item 4 of 9")
        case.run("check", *flags)
        closed = case.run("close", environment=gh_environment(pull_requests))
        body = f"#ruling_given {WALK_NAME} item 4 {word}"
        check(f"close after check {' '.join(flags) or '(approved)'} posts `{body}` on the two pull "
              "requests whose review holds item 4's line on a line of its own, and on none held on another item or "
              "walk, or quoting the line inside a sentence",
              closed.returncode == 0 and case.gh_comments() == [("101", body), ("102", body)]
              and closed.stdout.rstrip("\n").split("\n")[-2:] == [
                  f"The ruling on item 4 is posted as `{body}` on pull request {number}, held on it."
                  for number in (101, 102)],
              described(closed) + repr(case.gh_comments()))


def test_close_posts_the_ruling_for_each_item_an_answer_names():
    # check refuses an answer to two items at once, so the answer line one close reads for both is written here.
    case = Case(next_to_present="items 6 and 7 of 9")
    with open(case.minutes, "a") as minutes:
        minutes.write("items 6 and 7 of 9: the user answered approved #case_against_none (2026-11-05 10:00) in his "
                      "words \"a\", which makes its change. Fast reads:\n- no proposed text marked\n")
    closed = case.run("close", environment=gh_environment(held_pull_requests(
        (201, [f"#held_on_ruling {WALK_NAME} item 7"]), (202, [f"#held_on_ruling {WALK_NAME} item 6"]))))
    check("an answer to items 6 and 7 posts on the pull request held on each the ruling naming that item, so the "
          "two comments tell the items apart",
          closed.returncode == 0
          and case.gh_comments() == [("202", f"#ruling_given {WALK_NAME} item 6 approved"),
                                     ("201", f"#ruling_given {WALK_NAME} item 7 approved")],
          described(closed) + repr(case.gh_comments()))


def test_a_held_answer_posts_no_ruling_until_the_new_item_decides_it():
    pull_requests = held_pull_requests((301, [f"#held_on_ruling {WALK_NAME} item 3"]),
                                       (302, [f"#held_on_ruling {WALK_NAME} item 5"]))
    case = Case()
    case.run("check")
    with open(case.minutes, "a") as minutes:
        minutes.write("#next_to_present item 5 of 9\n")
    held = case.run("close", environment=gh_environment(pull_requests))
    check("a close that holds the answer for a new item asks gh nothing, since no ruling is given yet",
          held.returncode == 0 and case.gh_calls.read_text() == "", described(held))
    case.run("check", "--disapproved")
    closed = case.run("close", environment=gh_environment(pull_requests))
    comments = case.gh_comments()
    check("closing the new item posts its ruling on the pull request held on it and on the one held on the item "
          "whose answer was held for it",
          closed.returncode == 0
          and comments == [("302", f"#ruling_given {WALK_NAME} item 5 disapproved"),
                           ("301", f"#ruling_given {WALK_NAME} item 3 disapproved")],
          described(closed) + repr(comments))


def test_a_lookup_that_fails_leaves_the_answer_recorded_and_prints_the_commands_to_post_it_by_hand():
    for flags, mode, error in (
            ((), "list-fails", "exited 1: HTTP 502: Bad Gateway."),
            ((), "list-not-json", "printed what is not a list of pull requests with their reviews: "),
            (("--gh-timeout", "0.5"), "list-hangs", "did not end within 0.5 seconds.")):
        case = Case(next_to_present="item 4 of 9")
        case.run("check")
        closed = case.run("close", *flags, environment=gh_environment(mode=mode))
        lines = closed.stdout.rstrip("\n").split("\n")
        top = shlex.quote(str(case.checkout.resolve()))
        check(f"a `gh pr list` that {mode.split('-', 1)[1].replace('-', ' ')} leaves the answer and the next item "
              "in the minutes, prints what failed with the commands that list the held pull requests and post the "
              "ruling, posts nothing, and exits 2",
              closed.returncode == 2
              and "item 4 of 9: approved; every text the change adds has had a fast read. <accepted>"
              in case.minutes.read_text()
              and marker(case) == f"#next_to_present item 6 of {WALK_DOCUMENT_COUNTED_M}"
              and lines[-3].startswith("The minutes record the answer to item 4, but the open pull requests "
                                       "merge-lane-2 holds until that item is answered could not be looked up, so none "
                                       f"of them carries the ruling: `gh pr list` {error}")
              and lines[-2].startswith(f"Run `cd {top} && gh pr list --state open --limit 1000 --json number,reviews "
                                       "--jq ")
              and f'. == "{HELD_ON_ITEM_4}"' in lines[-2]
              and f"run `cd {top} && gh pr comment <number> --body '#ruling_given {WALK_NAME} item 4 approved'`"
              in lines[-2]
              and lines[-1].startswith("If that fails too, tell the user: \"merge-lane-2 was not told that item 4 of "
                                       f"{WALK_NAME} is approved,")
              and case.gh_comments() == [],
              described(closed))


def test_the_by_hand_lookup_command_lists_exactly_the_pull_requests_held_on_the_item():
    case = Case(next_to_present="item 4 of 9")
    case.run("check")
    closed = case.run("close", environment=gh_environment(mode="list-fails"))
    command = re.search(r"--jq ('[^']*')", closed.stdout)
    jq = shlex.split(command.group(1))[0] if command else ""
    program = shutil.which("jq")
    if not program:
        print("SKIP  the by-hand lookup's filter is run only where jq is installed")
        return
    listed = subprocess.run([program, "-r", jq], capture_output=True, text=True, input=held_pull_requests(
        (101, [f"x\n  {HELD_ON_ITEM_4} \ny"]), (103, [f"#held_on_ruling {WALK_NAME} item 44"]), (106, [])))
    check("the --jq filter the lookup failure prints picks the pull request whose review holds item 4's line, "
          "and not one held on item 44",
          listed.returncode == 0 and listed.stdout.split() == ["101"], described(listed) + jq)


def test_a_lookup_that_prints_json_of_another_shape_or_fails_silently_is_reported():
    for pull_requests, mode, error in (
            ('{"number": 1}', "", "printed what is not a list of pull requests with their reviews: TypeError("),
            ('[{"number": 1}]', "", "printed what is not a list of pull requests with their reviews: KeyError("),
            ("[]", "list-fails-silently", "exited 1: it printed nothing on stderr."),
            ("[]", "list-killed", "exited -15: it printed nothing on stderr.")):
        case = Case(next_to_present="item 4 of 9")
        case.run("check")
        closed = case.run("close", environment=gh_environment(pull_requests, mode=mode))
        check(f"a `gh pr list` that prints {pull_requests} in mode {mode or 'none'} is reported as the lookup failing",
              closed.returncode == 2 and f"`gh pr list` {error}" in closed.stdout, described(closed))


def test_a_gh_that_cannot_be_run_leaves_the_answer_recorded_and_exits_2():
    case = Case(next_to_present="item 4 of 9")
    case.run("check")
    case.gh.unlink()
    closed = case.run("close")
    check("a gh program that cannot be run is reported as the lookup failing, and the answer stays recorded",
          closed.returncode == 2 and "`gh pr list` could not be run: " in closed.stdout
          and "item 4 of 9: approved; every text the change adds" in case.minutes.read_text(), described(closed))


def test_a_comment_that_fails_is_reported_with_its_command_and_the_others_are_still_posted():
    case = Case(next_to_present="item 4 of 9")
    case.run("check")
    closed = case.run("close", environment=gh_environment(
        held_pull_requests((401, [HELD_ON_ITEM_4]), (402, [HELD_ON_ITEM_4])), comment_fails="401"))
    lines = closed.stdout.rstrip("\n").split("\n")
    top = shlex.quote(str(case.checkout.resolve()))
    body = case.gh_comments()[0][1] if case.gh_comments() else ""
    check("a comment gh fails to post is reported with the command that posts it, the next pull request still "
          "gets its comment, the answer stays recorded, and close exits 2",
          closed.returncode == 2 and [number for number, _ in case.gh_comments()] == ["401", "402"]
          and lines[-4:] == [
              "The minutes record the answer to item 4, but pull request 401, which merge-lane-2 holds until that "
              "item is answered, did not get the ruling's comment: `gh pr comment` exited 1: GraphQL: Could not add "
              "comment.",
              f"Run `cd {top} && gh pr comment 401 --body {shlex.quote(body)}` once, because merge-lane-2 releases or "
              "answers the hold only when it reads that comment.",
              f"If that fails too, tell the user: \"merge-lane-2 was not told that item 4 of {WALK_NAME} is approved, "
              "so pull request 401 stays held; gh failed.\" A subagent passes this to the agent that dispatched it.",
              f"The ruling on item 4 is posted as `#ruling_given {WALK_NAME} item 4 approved` on pull request 402, "
              "held on it."]
          and "item 4 of 9: approved; every text the change adds" in case.minutes.read_text(),
          described(closed))



def stopped_by_sigterm(*_):
    raise SystemExit(1)  # So main()'s finally removes the suite's scratch directory.


def main():
    signal.signal(signal.SIGTERM, stopped_by_sigterm)
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
