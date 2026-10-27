#!/usr/bin/env python3
"""Cases for the program that adds claimed user alerts to the open approval-walk right after its waiting item.

Each case runs the program as a subprocess, with HOME pointed at a scratch directory holding the claimed alerts,
in a scratch checkout holding one approval-walk. Prints one line per case and exits non-zero if any case fails.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().parents[4] / "scripts" / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

HERE = Path(__file__).resolve().parents[1]
PROGRAM = HERE / "walk-me-through-user-alert-insert-after-waiting-item-raise-item-count-and-record-in-walk-minutes.py"
_finder_spec = importlib.util.spec_from_file_location(
    "walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common",
    HERE / "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py")
walk_finder = importlib.util.module_from_spec(_finder_spec)
_finder_spec.loader.exec_module(walk_finder)
WALK = "alerts-test-walk-2026-10-27"
failures = []

WALK_DOCUMENT = """# A walk

The opening, which mentions Item 4 of 9 in passing.

## Item 3 of 9: the opening sentence

Recommendation: change it.

## Item 4 of 9: a filter

A filter would hide old rows.

Recommendation: leave the filter out.

## Items 5 and 6 of 9: two small corrections

Item 5 of 9 fixes a path. Recommendation: fix the path.

**Item 6 of 9** drops a sentence. Recommendation: drop it.

```
## Item 7 of 9: an example heading inside code
```

## Item 9 of 9: summary

Recommendation: close.
"""


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def walk_checkout(root, name, waiting="item 4 of 9", document=WALK_DOCUMENT):
    checkout = root / name / "checkout"
    walk = checkout / "docs" / "walk"
    walk.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(checkout)], check=True)
    (walk / f"{WALK}.md").write_text(document, encoding="utf-8")
    (walk / f"{WALK}-minutes.md").write_text(f"# Minutes\n#next_to_present {waiting}\n", encoding="utf-8")
    home = root / name / "home"
    (home / ".local/state/nedschorus/user-alerts/claimed").mkdir(parents=True)
    return checkout, home


def claimed_alert(home, alert_id, title):
    alert = {"id": alert_id, "written_at": "2026-10-27T12:00:00+00:00", "title": title,
             "alert_text": "merge-lane-2 is down.\n  ssh -t nedlern@ned-box 'recover'", "action": "Restart it."}
    (home / ".local/state/nedschorus/user-alerts/claimed" / f"{alert_id}.json").write_text(
        json.dumps(alert), encoding="utf-8")


def run(checkout, home, *alert_ids):
    return subprocess.run([sys.executable, str(PROGRAM), "--cwd", str(checkout), *alert_ids],
                          capture_output=True, text=True, env={**os.environ, "HOME": str(home)}, check=False)


def files(checkout):
    walk = checkout / "docs" / "walk"
    return ((walk / f"{WALK}.md").read_text(encoding="utf-8"),
            (walk / f"{WALK}-minutes.md").read_text(encoding="utf-8"))


def run_one_alert_cases(root):
    checkout, home = walk_checkout(root, "one")
    claimed_alert(home, "alert-a", "merge-lane-2 is down, and recovery refuses it")
    result = run(checkout, home, "alert-a")
    document, minutes = files(checkout)
    check("one alert is added and the program exits 0", result.returncode == 0, result.stderr)
    lines = document.split("\n")
    added = "## Item 4.1 of 10: merge-lane-2 is down, and recovery refuses it"
    check("the alert becomes item 4.1, right after waiting item 4 and before the next item",
          added in lines and lines.index("## Item 4 of 9: a filter".replace("of 9", "of 10"))
          < lines.index(added) < lines.index("## Items 5 and 6 of 10: two small corrections"), document)
    check("the added item holds the alert's text in a fence and what can be done",
          "```text\nmerge-lane-2 is down.\n  ssh -t nedlern@ned-box 'recover'\n```" in document
          and "What can be done: Restart it." in document, document)
    check("every running count that opens a line outside code is raised to the new item count",
          "## Item 3 of 10:" in document and "Item 5 of 10 fixes" in document
          and "**Item 6 of 10** drops" in document and "## Item 9 of 10: summary" in document, document)
    check("a count inside code, and one mentioned mid-sentence, keep their old item count",
          "## Item 7 of 9: an example heading" in document and "mentions Item 4 of 9 in passing" in document,
          document)
    check("the walk-minutes get the `#user_alert` line and, last, the waiting item with the new item count",
          "#user_alert alert-a\n#next_to_present item 4 of 10\n" in minutes
          and minutes.rstrip("\n").endswith("#next_to_present item 4 of 10"), minutes)
    check("the walk-minutes record the re-planning", "added item 4.1, from the alerts" in minutes, minutes)
    check("the output says what was added and tells the agent to write the case against and recommendation",
          "Added item 4.1 of 10" in result.stdout and "Recommendation:" in result.stdout
          and "now has 10 items" in result.stdout, result.stdout)
    parser = walk_finder.markdown_parser()
    value = walk_finder.open_walk(checkout / "docs" / "walk", parser)[1]
    numbers, total = walk_finder.parse_items(value)
    total, units = walk_finder.waiting_item_units(checkout / "docs/walk" / f"{WALK}.md", value, numbers, total,
                                                  parser)
    order = [number for unit in walk_finder.item_unit_spans(document, parser) if unit[1] == "10"
             for number in unit[0]]
    check("the walk-me-through finder still finds the waiting item, and reads item 4.1 next after it",
          total == "10" and units[0][0] == ["4"] and order == ["3", "4", "4.1", "5", "6", "9"],
          repr((total, units, order)))


def run_several_alert_cases(root):
    checkout, home = walk_checkout(root, "two")
    claimed_alert(home, "alert-a", "first")
    claimed_alert(home, "alert-b", "second")
    result = run(checkout, home, "alert-a", "alert-b")
    document, minutes = files(checkout)
    check("two alerts become items 4.1 and 4.2, in the order given, and the item count rises by two",
          result.returncode == 0 and document.index("## Item 4.1 of 11: first")
          < document.index("## Item 4.2 of 11: second") < document.index("## Items 5 and 6 of 11"),
          result.stderr + document)
    check("each alert gets its own `#user_alert` line",
          "#user_alert alert-a\n#user_alert alert-b\n#next_to_present item 4 of 11" in minutes, minutes)

    existing = WALK_DOCUMENT.replace("## Items 5 and 6", "## Item 4.1 of 9: added earlier\n\n## Items 5 and 6")
    checkout, home = walk_checkout(root, "taken", document=existing)
    claimed_alert(home, "alert-c", "third")
    run(checkout, home, "alert-c")
    document, _ = files(checkout)
    check("an alert takes the lowest number after the waiting item's that no item uses",
          "## Item 4.2 of 10: third" in document and "## Item 4.1 of 10: added earlier" in document, document)

    sub_item = WALK_DOCUMENT.replace("## Items 5 and 6", "## Item 4.1 of 9: a part\n\n## Items 5 and 6")
    checkout, home = walk_checkout(root, "sub-item", waiting="item 4.1 of 9", document=sub_item)
    claimed_alert(home, "alert-d", "fourth")
    run(checkout, home, "alert-d")
    document, minutes = files(checkout)
    check("while item 4.1 waits, the alert becomes item 4.1.1",
          "## Item 4.1.1 of 10: fourth" in document and "#next_to_present item 4.1 of 10" in minutes, document)


def run_refusal_cases(root):
    checkout, home = walk_checkout(root, "closed", waiting="none, closed")
    claimed_alert(home, "alert-a", "first")
    before = files(checkout)
    result = run(checkout, home, "alert-a")
    check("with no approval-walk open, the program exits 1, says to open one with the alerts alone, and "
          "changes nothing",
          result.returncode == 1 and "no approval-walk is open" in result.stderr
          and "#user_alert <id>" in result.stderr and files(checkout) == before, result.stderr)

    checkout, home = walk_checkout(root, "missing")
    before = files(checkout)
    result = run(checkout, home, "alert-gone")
    check("an alert no longer in claimed/ makes the program exit 1, naming it in its refusal, and changes nothing",
          result.returncode == 1 and "the alert alert-gone cannot be read from" in result.stderr
          and "Traceback" not in result.stderr and files(checkout) == before, result.stderr)

    checkout, home = walk_checkout(root, "not-an-object")
    (home / ".local/state/nedschorus/user-alerts/claimed" / "alert-list.json").write_text("[]", encoding="utf-8")
    before = files(checkout)
    result = run(checkout, home, "alert-list")
    check("an alert file that holds no JSON object makes the program exit 1, naming it in its refusal, and "
          "changes nothing",
          result.returncode == 1 and "the alert alert-list cannot be read from" in result.stderr
          and "Traceback" not in result.stderr and files(checkout) == before, result.stderr)

    checkout, home = walk_checkout(root, "unknown-item", waiting="item 8 of 9")
    claimed_alert(home, "alert-a", "first")
    before = files(checkout)
    result = run(checkout, home, "alert-a")
    check("a waiting item the walk-document has no heading for makes the program exit 1 and change nothing",
          result.returncode == 1 and "waiting item cannot be found" in result.stderr and "Item 8 of 9" in result.stderr
          and "Traceback" not in result.stderr and files(checkout) == before, result.stderr)


with tempfile.TemporaryDirectory() as temporary_directory:
    scratch = Path(temporary_directory)
    run_one_alert_cases(scratch)
    run_several_alert_cases(scratch)
    run_refusal_cases(scratch)

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
