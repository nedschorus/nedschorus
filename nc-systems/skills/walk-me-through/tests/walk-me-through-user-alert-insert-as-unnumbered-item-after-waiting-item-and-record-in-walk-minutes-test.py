#!/usr/bin/env python3
"""Cases for the program that adds claimed user alerts to the open approval-walk right after its waiting item.

Each case runs the program as a subprocess, with HOME pointed at a scratch directory holding the claimed alerts,
in a scratch checkout holding one approval-walk, except the heading_title case, which calls that function
in-process because a title it would prefix differently ends in the same refusal either way. Prints one line per case and exits non-zero if any case fails.
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
PROGRAM = HERE / "walk-me-through-user-alert-insert-as-unnumbered-item-after-waiting-item-and-record-in-walk-minutes.py"
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
    _, minutes_before = files(checkout)
    result = run(checkout, home, "alert-a")
    document, minutes = files(checkout)
    check("one alert is added and the program exits 0", result.returncode == 0, result.stderr)
    lines = document.split("\n")
    added = "## merge-lane-2 is down, and recovery refuses it"
    check("the alert becomes an unnumbered `## <title>` item, right after waiting item 4 and before the next item",
          added in lines and lines.index("## Item 4 of 9: a filter")
          < lines.index(added) < lines.index("## Items 5 and 6 of 9: two small corrections"), document)
    check("the added item holds the alert's text in a fence and what can be done",
          "```text\nmerge-lane-2 is down.\n  ssh -t nedlern@ned-box 'recover'\n```" in document
          and "What can be done: Restart it." in document, document)
    check("no other heading or running count changes",
          document.replace("\n" + "\n".join(lines[lines.index(added) - 1:lines.index(
              "## Items 5 and 6 of 9: two small corrections") - 1]), "", 1) == WALK_DOCUMENT
          and "of 10" not in document, document)
    check("the walk-minutes get the re-planning line and the `#user_alert` line, and no new `#next_to_present` line",
          minutes.startswith(minutes_before) and "#user_alert alert-a\n" in minutes
          and "added 1 unnumbered item(s) right after item 4" in minutes
          and minutes.count("#next_to_present") == 1, minutes)
    check("the output says what was added and tells the agent to write the case against and recommendation",
          "Added the unnumbered item `## merge-lane-2 is down, and recovery refuses it`" in result.stdout
          and "Recommendation:" in result.stdout and "`#case_against <rating>:" in result.stdout
          and "`#case_against none.`" in result.stdout, result.stdout)
    check("an alert title that reads as no item heading keeps its words, with no prefix",
          "User alert: " not in document, document)
    parser = walk_finder.markdown_parser()
    value = walk_finder.open_walk(checkout / "docs" / "walk", parser)[1]
    numbers, total = walk_finder.parse_items(value)
    total, units = walk_finder.waiting_item_units(checkout / "docs/walk" / f"{WALK}.md", value, numbers, total,
                                                  parser)
    all_units = walk_finder.item_unit_spans(document, parser)
    count_before = walk_finder.approval_walk_item_total_shown_and_waiting_counted_from_walk_document(walk_finder.item_unit_spans(WALK_DOCUMENT, parser))
    check("the walk-me-through finder still finds waiting item 4, reads the added item as unnumbered, and counts "
          "it in M",
          units[0][0] == ["4"] and sum(map(walk_finder.approval_walk_unit_is_unnumbered_item, all_units)) == 1
          and int(walk_finder.approval_walk_item_total_shown_and_waiting_counted_from_walk_document(all_units)) == int(count_before) + 1,
          repr((units, all_units)))


def run_several_alert_cases(root):
    checkout, home = walk_checkout(root, "two")
    claimed_alert(home, "alert-a", "first")
    claimed_alert(home, "alert-b", "second")
    result = run(checkout, home, "alert-a", "alert-b")
    document, minutes = files(checkout)
    check("two alerts become two unnumbered items, in the order given, right after waiting item 4",
          result.returncode == 0 and document.index("## Item 4 of 9: a filter") < document.index("## first")
          < document.index("## second") < document.index("## Items 5 and 6 of 9"),
          result.stderr + document)
    check("each alert gets its own `#user_alert` line",
          "#user_alert alert-a\n#user_alert alert-b\n" in minutes, minutes)

    for name, title in (("numbered-title", "Item 3 of 9: reboot"), ("label-title", "Item 3 reboot"),
                        ("withdrawn-title", "Withdrawn backups on the Mac")):
        checkout, home = walk_checkout(root, name)
        claimed_alert(home, "alert-c", title)
        result = run(checkout, home, "alert-c")
        document, minutes = files(checkout)
        units = walk_finder.item_unit_spans(document, walk_finder.markdown_parser())
        check(f"an alert titled {title!r} becomes the unnumbered item `## User alert: {title}`, not a refusal",
              result.returncode == 0 and f"\n## User alert: {title}\n" in document
              and sum(map(walk_finder.approval_walk_unit_is_unnumbered_item, units)) == 1
              and f"`## User alert: {title}`" in result.stdout and f"`User alert: {title}`." in minutes,
              result.stderr + document)

    sub_item = WALK_DOCUMENT.replace("## Items 5 and 6", "### Item 4.1 of 9: a part\n\n## Items 5 and 6")
    checkout, home = walk_checkout(root, "sub-item", waiting="item 4.1 of 9", document=sub_item)
    claimed_alert(home, "alert-d", "fourth")
    result = run(checkout, home, "alert-d")
    document, _ = files(checkout)
    check("while sub-step 4.1 waits, the alert becomes an unnumbered item right after it",
          result.returncode == 0
          and document.index("### Item 4.1 of 9: a part") < document.index("## fourth")
          < document.index("## Items 5 and 6 of 9"), result.stderr + document)

    parts = ("# A walk\n\n## Part 1\n\n### Item 1 of 2: one\n\nRecommendation: go.\n\n"
             "### Item 2 of 2: two\n\nRecommendation: stop.\n")
    checkout, home = walk_checkout(root, "parts", waiting="item 1 of 2", document=parts)
    claimed_alert(home, "alert-e", "fifth")
    before = files(checkout)
    result = run(checkout, home, "alert-e")
    check("a walk-document whose items sit under `##` part headings makes the program exit 1, say to add the "
          "alert by hand, and change nothing",
          result.returncode == 1 and "`##` part headings" in result.stderr and "alert-e" in result.stderr
          and "Traceback" not in result.stderr and files(checkout) == before, result.stderr)


def run_marker_in_title_cases(root):
    for number, title in enumerate(("pause it with #approval_walk_paused", "close it: #next_to_present none",
                                    "quote `#next_to_present none` first", "two lines,\n#next_to_present none")):
        checkout, home = walk_checkout(root, f"marker-{number}")
        claimed_alert(home, "alert-m", title)
        result = run(checkout, home, "alert-m")
        _, minutes = files(checkout)
        parser = walk_finder.markdown_parser()
        found = walk_finder.open_walk(checkout / "docs" / "walk", parser)
        check(f"a marker in the alert title {title!r} is written to the walk-minutes as a quotation, so the walk "
              "stays open on its waiting item",
              result.returncode == 0 and found is not None and found[1] == "item 4 of 9"
              and walk_finder.text_wrapped_as_markdown_code_span(title) in minutes,
              f"{result.stderr} {found!r} {minutes}")


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
    check("an unreadable alert given alone gets no command to run again, and is told to the user while its file "
          "exists", "Run again" not in result.stderr
          and "still exists, it holds no readable alert: tell the user its path" in result.stderr, result.stderr)

    checkout, home = walk_checkout(root, "missing-among-others")
    claimed_alert(home, "alert-a", "first")
    claimed_alert(home, "alert-z", "second")
    result = run(checkout, home, "alert-a", "alert-gone", "alert-z")
    check("an unreadable alert's refusal gives the whole command to run again with the other ids, leaving it out",
          result.returncode == 1
          and f"leaving out alert-gone: python3 {PROGRAM.resolve()} --cwd {checkout} alert-a alert-z\n"
          in result.stderr, result.stderr)

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
          result.returncode == 1 and "waiting item cannot be found" in result.stderr
          and "has no heading `Item 8`, which the minutes name" in result.stderr
          and "Traceback" not in result.stderr and files(checkout) == before, result.stderr)
    check("an unfound waiting item's refusal names the whole command to run again, with the same alert ids",
          f"then run again: python3 {PROGRAM.resolve()} --cwd {checkout} alert-a" in result.stderr, result.stderr)
    # The program names the walk files under git's checkout top, which resolves a temporary directory's symlink.
    walk = checkout.resolve() / "docs" / "walk"
    check("an unfound waiting item's refusal names the walk-minutes and the walk-document to fix",
          f"walk-minutes {walk / f'{WALK}-minutes.md'}" in result.stderr
          and f"walk-document {walk / f'{WALK}.md'}" in result.stderr, result.stderr)

    checkout, home = walk_checkout(root, "two-unclosed")
    claimed_alert(home, "alert-a", "first")
    walk = checkout / "docs" / "walk"
    (walk / "second-walk.md").write_text(WALK_DOCUMENT, encoding="utf-8")
    (walk / "second-walk-minutes.md").write_text("# Minutes\n#next_to_present item 4 of 9\n", encoding="utf-8")
    before = files(checkout) + ((walk / "second-walk.md").read_text(encoding="utf-8"),
                                (walk / "second-walk-minutes.md").read_text(encoding="utf-8"))
    result = run(checkout, home, "alert-a")
    after = files(checkout) + ((walk / "second-walk.md").read_text(encoding="utf-8"),
                               (walk / "second-walk-minutes.md").read_text(encoding="utf-8"))
    resolved = checkout.resolve() / "docs" / "walk"
    check("with two unclosed approval-walks, the program exits 1 without a traceback, names both walk-minutes and "
          "the command to run again, and changes nothing",
          result.returncode == 1 and "Traceback" not in result.stderr
          and "more than one approval-walk is open or paused" in result.stderr
          and str(resolved / f"{WALK}-minutes.md") in result.stderr
          and str(resolved / "second-walk-minutes.md") in result.stderr
          and f"Then run again: python3 {PROGRAM.resolve()} --cwd {checkout} alert-a" in result.stderr
          and after == before, result.stderr)


def run_repeated_id_and_title_spanning_two_headings_cases(root):
    checkout, home = walk_checkout(root, "unreadable-given-twice")
    claimed_alert(home, "alert-a", "first")
    result = run(checkout, home, "alert-gone", "alert-a", "alert-gone")
    check("an unreadable alert id given twice is left out both times from the command to run again",
          result.returncode == 1
          and f"leaving out alert-gone: python3 {PROGRAM.resolve()} --cwd {checkout} alert-a\n" in result.stderr,
          result.stderr)

    program_spec = importlib.util.spec_from_file_location("user_alert_insert", PROGRAM)
    program = importlib.util.module_from_spec(program_spec)
    program_spec.loader.exec_module(program)
    title = program.heading_title("first\n## second", walk_finder, walk_finder.markdown_parser())
    check("a title whose `##` heading would be two unnumbered items, not one, gets the prefix",
          title == "User alert: first\n## second", repr(title))

with tempfile.TemporaryDirectory() as temporary_directory:
    scratch = Path(temporary_directory)
    run_one_alert_cases(scratch)
    run_several_alert_cases(scratch)
    run_marker_in_title_cases(scratch)
    run_refusal_cases(scratch)
    run_repeated_id_and_title_spanning_two_headings_cases(scratch)

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
