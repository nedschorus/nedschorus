#!/usr/bin/env python3
"""Cases for the one-time conversion of open approval-walks' walk-minutes to
the reading in which only the walk check program's own lines count. Each case
writes its own walk-minutes in a scratch directory and runs the script as a
subprocess, except the cases that load it to replace the check program's
reading or the default glob.
"""
import collections
import contextlib
import importlib.util
import io
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = (Path(__file__).resolve().parents[1]
          / "walk-me-through-open-walk-minutes-hand-written-decision-lines-to-program-lines-one-time-conversion-nbd.py")
CHECK_PROGRAM = Path(__file__).resolve().parents[1] / "walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py"
ROOT = Path(tempfile.mkdtemp(prefix="walk-minutes-conversion-test-")).resolve()
failures = []

MINUTES = """# Minutes

Item 1 of 9: approved. <accepted>
Item 2 of 9: disapproved, the filter is added.
item 3 of 9: moved on, no decision: the question went to another walk. <moved on, no decision>
Item 4 of 9: deferred until the redraft is read.
item 5 of 9: deferred; it moves to just before the summary item. <open>
Items 5 and 6 of 9 rulings: a subagent applies them. 5 deferred; 6 D.
item 6 of 9: approved; every text the change adds has had a fast read. <accepted>
Items 7 to 8 of 9 revised at the advisor call (7 reframed as the cold read he approved today).
#next_to_present item 7 of 12
"""


def check(case_name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {case_name}" + ("" if condition else f": {detail}"))
    if not condition:
        failures.append(case_name)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def minutes_file(name, text=MINUTES):
    path = ROOT / name / "docs" / "walk" / "w-minutes.md"
    path.parent.mkdir(parents=True)
    path.write_text(text)
    return path


def run(*arguments):
    return subprocess.run([sys.executable, str(SCRIPT), *arguments], capture_output=True, text=True)


def described(result):
    return f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}"


EXPECTED_LINES = [
    'item 1 of 12: already decided by the hand-written minutes line 3, "Item 1 of 9: approved. <accepted>"; the walk '
    'does not come back to it. <accepted>',
    'item 2 of 12: already decided by the hand-written minutes line 4, "Item 2 of 9: disapproved, the filter is '
    'added."; the walk does not come back to it. <rejected>',
    'item 3 of 12: moved on, no decision: the hand-written minutes line 5, "item 3 of 9: moved on, no decision: the '
    'question went to another walk. <moved on, no decision>"; the walk does not come back to it. '
    '<moved on, no decision>',
    "item 4 of 12: deferred; it moves to just before the summary item. <open>",
    "item 5 of 12: deferred a second time, so it leaves the walk and stays open. <open>",
    'item 7 of 12: already decided by the hand-written minutes line 10, "Items 7 to 8 of 9 revised at the advisor call '
    '(7 reframed as the cold read he approved today)."; the walk does not come back to it. <accepted>',
    'item 8 of 12: already decided by the hand-written minutes line 10, "Items 7 to 8 of 9 revised at the advisor call '
    '(7 reframed as the cold read he approved today)."; the walk does not come back to it. <accepted>',
]


def appended(path):
    return [line[len("  append: "):] for line in path.read_text().split("\n") if line.startswith("  append: ")]


def test_a_dry_run_proposes_each_line_the_old_reading_counted_and_changes_nothing():
    path = minutes_file("dry")
    result = run("--minutes", str(path))
    proposed = [line[len("  append: "):] for line in result.stdout.split("\n") if line.startswith("  append: ")]
    check("the dry run proposes, in line order, a ruled, rejected, moved-on, first and second deferral line, and "
          "one line per item of a note the old reading misread, and nothing for a deferral of a decided item",
          result.returncode == 0 and proposed == EXPECTED_LINES
          and result.stdout.startswith(f"== {path}: 7 lines to append\n")
          and path.read_text() == MINUTES, described(result))


def test_a_held_answer_whose_new_item_is_decided_takes_that_items_outcome():
    for outcome in ("<accepted>", "<rejected>"):
        word = "approved" if outcome == "<accepted>" else "disapproved"
        text = ("# Minutes\n\nitem 6 of 29: answer held: item 6.1 of 30, raised by a fast-read finding, waits for the "
                f"user's answer. <open>\nitem 6.1 of 30: {word}; every text the change adds has had a fast read. "
                f"{outcome}\nitem 2 of 29: answer held: item 2.1 of 30, raised by a fast-read finding, waits for the "
                "user's answer. <open>\n#next_to_present item 7 of 30\n")
        path = minutes_file(f"held-{word}", text)
        result = run("--minutes", str(path))
        proposed = [line[len("  append: "):] for line in result.stdout.split("\n") if line.startswith("  append: ")]
        check(f"a held item whose new item is {word} is proposed already decided, {outcome}, and one whose new item "
              "is not decided gets nothing",
              result.returncode == 0 and proposed == [
                  "item 6 of 30: already decided by the user's answer to item 6.1 of 30, which the hand-written "
                  "minutes line 3, \"item 6 of 29: answer held: item 6.1 of 30, raised by a fast-read finding, waits "
                  "for the user's an...\" held its answer for; the walk does not come back to it. "
                  f"{outcome}"], described(result))


def test_a_skipped_line_proposes_nothing():
    path = minutes_file("skip")
    result = run("--minutes", str(path), "--skip", f"{path}:10", "--skip", f"{path}:8")
    proposed = [line[len("  append: "):] for line in result.stdout.split("\n") if line.startswith("  append: ")]
    check("--skip drops the proposals of the note on items 7 and 8, and of the hand-written deferral of item 5",
          result.returncode == 0 and proposed == EXPECTED_LINES[:4], described(result))


def test_a_line_judged_a_move_on_is_proposed_as_one():
    path = minutes_file("moved-on")
    result = run("--minutes", str(path), "--as-moved-on", f"{path}:3")
    proposed = [line[len("  append: "):] for line in result.stdout.split("\n") if line.startswith("  append: ")]
    check("--as-moved-on proposes the moved-on line for the items of the line it names, and leaves the others",
          result.returncode == 0 and proposed[0] == (
              'item 1 of 12: moved on, no decision: the hand-written minutes line 3, "Item 1 of 9: approved. '
              '<accepted>"; the walk does not come back to it. <moved on, no decision>')
          and proposed[1:] == EXPECTED_LINES[1:], described(result))


def test_write_appends_the_lines_and_the_marker_and_the_check_program_then_reads_them():
    path = minutes_file("write")
    result = run("--minutes", str(path), "--skip", f"{path}:10", "--write")
    check_program = load(CHECK_PROGRAM, "check_program")
    finder = check_program.load_walk_finder()
    decided, deferrals = check_program.minutes_record(finder, path.read_text(), finder.markdown_parser())
    check("--write appends the proposed lines and the converted marker below every earlier line, changing none",
          result.returncode == 0
          and path.read_text() == MINUTES + "\n".join(EXPECTED_LINES[:5])
          + "\n#walk_minutes_hand_written_lines_converted\n", described(result) + path.read_text())
    check("after --write, the check program reads the converted decisions and deferrals",
          decided == {"1", "2", "3", "6"} and dict(deferrals) == {"4": 1, "5": 2}, repr((decided, deferrals)))
    before = path.read_text()
    again = run("--minutes", str(path), "--write")
    check("a second run leaves a converted file alone",
          again.returncode == 0 and "converted already" in again.stdout and path.read_text() == before,
          described(again))


def test_a_write_the_check_program_does_not_then_read_is_reported_as_failed():
    path = minutes_file("unread")
    script = load(SCRIPT, "conversion")
    check_program = load(CHECK_PROGRAM, "check_program_blind")
    check_program.minutes_record = lambda *_: (set(), collections.Counter())
    script.load_walk_me_through_check_program_module = lambda: check_program
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        status = script.main(["--minutes", str(path), "--write"])
    check("an item the new reading still does not count after --write is a FAILED line and exit 1",
          status == 1 and "FAILED: " in output.getvalue() and "item 1 reads as less decided" in output.getvalue(),
          output.getvalue())


def test_only_open_walks_are_read_by_default():
    open_walk = minutes_file("seats/open", "# M\n\n#next_to_present item 2 of 3\n")
    minutes_file("seats/closed", "# M\n\n#next_to_present item 2 of 3\n#next_to_present none, closed\n")
    minutes_file("seats/unmarked", "# M\n\nItem 1 of 3: approved.\n")
    script = load(SCRIPT, "conversion_glob")
    check_program = script.load_walk_me_through_check_program_module()
    finder = check_program.load_walk_finder()
    found = script.walk_minutes_files_of_open_approval_walks(finder, finder.markdown_parser(), str(ROOT / "seats" / "*" / "docs" / "walk" / "*-minutes.md"))
    check("the default reads a walk whose last marker names an item, not a closed walk or one with no marker",
          found == [open_walk], repr(found))


def test_an_unreadable_minutes_file_fails_and_others_still_run():
    path = minutes_file("readable")
    result = run("--minutes", str(ROOT / "missing-minutes.md"), "--minutes", str(path))
    check("a minutes file that cannot be read is a FAILED line and exit 1, and the next file is still read",
          result.returncode == 1 and result.stdout.startswith(f"FAILED: {ROOT / 'missing-minutes.md'} could not be read")
          and f"== {path}: 7 lines to append" in result.stdout, described(result))
    script = load(SCRIPT, "conversion_unreadable_glob")

    def unreadable(*_):
        raise PermissionError("permission denied")
    script.walk_minutes_files_of_open_approval_walks = unreadable
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        status = script.main([])
    check("walk-minutes the default glob cannot read are a FAILED line and exit 1",
          status == 1 and output.getvalue().startswith("FAILED: the walk-minutes under "), output.getvalue())


def test_a_skip_that_is_not_path_and_line_is_refused_as_usage():
    result = run("--skip", "no-line-number")
    check("--skip without :LINE is refused as usage", result.returncode == 2 and "is not PATH:LINE" in result.stderr,
          described(result))


def main():
    try:
        for name, function in sorted(globals().items()):
            if name.startswith("test_") and callable(function):
                function()
    finally:
        shutil.rmtree(ROOT, ignore_errors=True)
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
