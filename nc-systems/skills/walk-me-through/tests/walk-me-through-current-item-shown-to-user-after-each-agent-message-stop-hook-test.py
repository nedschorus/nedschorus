#!/usr/bin/env python3
"""Cases for the Stop hook that, during an open approval-walk, shows the user
the current item in full after each message the agent writes to him.

Each case runs the hook as a subprocess, its real stdin-to-stdout path, in a
scratch checkout this suite made, with a transcript this suite wrote. The exit
code is asserted on every case: the hook exits 0 unless it hit a fault, which
it names on stderr with exit 1.
"""

import importlib.util
import json
import os
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

HOOK_SCRIPT = (Path(__file__).resolve().parents[1]
               / "walk-me-through-current-item-shown-to-user-after-each-agent-message-stop-hook.py")
SUITE_ROOT = Path(tempfile.mkdtemp(prefix="approval-walk-current-item-hook-test-"))
failures = []

WALK_DOCUMENT = """# A walk: approval-walk

This approval-walk settles two questions about the poem page. It has 9 items.

## Item 2 of 9: where the poem page lives

The poem page goes in the wiki, next to the glossary and the style guide, so that agents find it where they already look for project terms. Its name is checked against the [naming page](file:///x/naming.md) before the file is created.

**The strongest case for N:** a page in the wiki is one more document agents must be told to read. **Recommendation: Y.**

---

## Item 4.1 of 9: how a poem row reads

One row per job an agent is about to do, written "to do X, use Y", with one example call and the mistake it prevents, so an agent reading the row can act on it without opening anything else. SUB_STEP_EXTRA

## Item 5 of 9: the hook

A hook checks each written file for narrow patterns and names the row to use when one matches. The first patterns:

- a Markdown fence literal;
- `ps` called to find a process.

Recommendation: Y.

## Item 6 of 9: the reviewer

A cheap reviewer checks each code pull request against the page. Recommendation: N.

## Items 7 and 8 of 9: two small corrections

Item 7 of 9 fixes a misspelt path in the page's first row. Recommendation: Y.

Item 8 of 9 drops a repeated sentence from the page's last row. Recommendation: Y.

## Item 9 of 9: the page's opening section

The opening section is rewritten.
Item 1 of 9 put the page in the wiki, so the opening says so. The original section:

### What the page is

The page lists poems.

The proposed section:

### What the page is

The page lists the components an agent uses before writing its own, one row per job, grouped by the job the agent is about to start.

The strongest case for N: the old opening is shorter. Recommendation: Y.
"""
SUB_STEP_EXTRA = " ".join(["Each row also names the default component where two could do the job."] * 8)
WALK_DOCUMENT = WALK_DOCUMENT.replace("SUB_STEP_EXTRA", SUB_STEP_EXTRA)

ITEM_2_REPLY = """Recorded your answer to item 1.

**Item 2 of 9: where the poem page lives**

The poem page goes in the wiki, next to the glossary and the style guide, so that agents find it where they already look for project terms. Its name is checked against the naming page before the file is created.

**The strongest case for N:** a page in the wiki is one more document agents must be told to read. **Recommendation: Y.**"""


def section(start, end=None):
    """The walk-document's text from one running-count heading to another."""
    return WALK_DOCUMENT[WALK_DOCUMENT.index(start):
                         WALK_DOCUMENT.index(end) if end else len(WALK_DOCUMENT)]


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


class Case:
    """One case's own checkout, walk files and transcript."""

    counter = 0

    def __init__(self, with_walk_directory=True, in_git=True):
        Case.counter += 1
        self.root = SUITE_ROOT / f"case-{Case.counter}"
        self.checkout = self.root / "checkout"
        self.checkout.mkdir(parents=True)
        if in_git:
            subprocess.run(["git", "init", "-q", str(self.checkout)], check=True)
        self.walk = self.checkout / "docs" / "walk"
        if with_walk_directory:
            self.walk.mkdir(parents=True)
        self.transcript = self.root / "transcript.jsonl"

    def walk_files(self, name="poem-page-2026-10-12", minutes="", document=WALK_DOCUMENT,
                   modified=1_000_000):
        if document is not None:
            (self.walk / f"{name}.md").write_text(document)
        minutes_path = self.walk / f"{name}-minutes.md"
        minutes_path.write_text(f"# Minutes\n\n{minutes}\n")
        os.utime(minutes_path, (modified, modified))
        return minutes_path

    def reply(self, *texts):
        records = [{"type": "user", "message": {"role": "user", "content": "y"}}]
        for index, text in enumerate(texts):
            content = ([{"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}]
                       if text is None else [{"type": "text", "text": text}])
            records.append({"type": "assistant",
                            "message": {"id": f"message-{index}", "content": content}})
        self.transcript.write_text("".join(json.dumps(record) + "\n" for record in records))

    def run(self, stop_hook_active=False, environment_extra=None, stdin_text=None):
        payload = {"hook_event_name": "Stop", "session_id": "test-session",
                   "transcript_path": str(self.transcript), "cwd": str(self.checkout),
                   "stop_hook_active": stop_hook_active}
        environment = {name: value for name, value in os.environ.items()
                       if name not in ("NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER",
                                       "CLAUDE_CODE_SESSION_ATTENDED")}
        environment.update(environment_extra or {})
        return subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            input=json.dumps(payload) if stdin_text is None else stdin_text,
            capture_output=True, text=True, env=environment, cwd=self.checkout)


def blocked_reason(result):
    if result.returncode != 0 or not result.stdout.strip():
        return None
    output = json.loads(result.stdout)
    return output["reason"] if output.get("decision") == "block" else None


def check_silent(case_name, result):
    check(case_name, result.returncode == 0 and result.stdout == "",
          f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")


ANSWERS_LINE = "Answer Y, N, D to defer, or R to repeat the item."


def check_shown(case_name, result, *units):
    """The hook shows the user the units' walk-document text, then the answers.

    Heading and bold marks are left out, because Claude Code shows them as written.
    """
    text = "\n".join(unit.strip("\n") for unit in units)
    text = "\n".join(line[line.index(" ") + 1:] if line.startswith("#") else line
                     for line in text.splitlines())
    text = "\n".join(line for line in text.splitlines() if line.strip() != "---")
    wanted = text.replace("**", "").strip("\n") + "\n\n" + ANSWERS_LINE
    output = json.loads(result.stdout) if result.returncode == 0 and result.stdout.strip() else {}
    check(case_name, output == {"systemMessage": wanted},
          f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")


def check_blocked(case_name, result, *phrases):
    reason = blocked_reason(result)
    check(case_name, reason is not None and all(phrase in reason for phrase in phrases),
          f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")


def test_shows_current_item_whatever_the_reply_says():
    case = Case()
    case.walk_files(minutes="Next to present: item 2 of 9.")
    item = section("## Item 2 of 9", "## Item 4.1 of 9")
    for case_name, reply in (
            ("a reply that already holds the item is followed by the item", ITEM_2_REPLY),
            ("a one-line summary of the item is followed by the item",
             "The background job finished. Waiting on item 2 of 9; Recommendation: Y."),
            ("a reply that never mentions the item is followed by the item",
             "The background job finished and its report is in the log-store.")):
        case.reply(reply)
        check_shown(case_name, case.run(), item)
    shown = json.loads(case.run().stdout)["systemMessage"]
    check("the item is shown from its heading's words, without Markdown marks",
          shown.startswith("Item 2 of 9: where the poem page lives\n") and "**" not in shown
          and shown.endswith("Recommendation: Y.\n\n" + ANSWERS_LINE), repr(shown))


def test_items_shown_together():
    case = Case()
    case.walk_files(minutes="Next to present: items 5 and 6 of 9.")
    case.reply("Recorded.")
    check_shown("items shown together are both shown, in the walk-document's order", case.run(),
                section("## Item 5 of 9", "## Item 6 of 9"),
                section("## Item 6 of 9", "## Items 7 and 8 of 9"))


def test_items_under_one_heading():
    case = Case()
    case.walk_files(minutes="Next to present: items 7 and 8 of 9.")
    case.reply("Recorded.")
    check_shown("items under one heading are shown whole", case.run(),
                section("## Items 7 and 8 of 9", "## Item 9 of 9"))


def test_part_without_recommendation():
    case = Case()
    case.walk_files(minutes="Next to present: item 4.1 of 9.")
    case.reply("Recorded.")
    check_shown("a part is shown alone, without the next part", case.run(),
                section("## Item 4.1 of 9", "## Item 5 of 9"))


def test_item_holding_original_and_proposed_sections():
    case = Case()
    case.walk_files(minutes="Next to present: item 9 of 9.")
    case.reply("Recorded.")
    check_shown("an item holding its own headings is shown whole", case.run(),
                section("## Item 9 of 9"))


def turn_records(*middle):
    """A turn opened by the user and answered in text, then the given records."""
    return ([{"type": "user", "message": {"role": "user", "content": "what is PR 1188?"}},
             {"type": "assistant", "message": {"id": "m1", "content": [
                 {"type": "text", "text": "PR 1188 changes the hook."}]}}]
            + list(middle))


TOOL_CALL = {"type": "assistant", "message": {"id": "m2", "content": [
    {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}]}}
TOOL_RESULT = {"type": "user", "message": {"role": "user", "content": [
    {"type": "tool_result", "tool_use_id": "t", "content": "ok"}]}}
NOTICE = {"type": "user", "origin": {"kind": "task-notification"},
          "message": {"role": "user", "content": [
              {"type": "text", "text": "<task-notification>done</task-notification>"}]}}
PEER_MESSAGE = {"type": "user", "isMeta": True, "origin": {"kind": "peer"},
                "message": {"role": "user", "content": [
                    {"type": "text", "text": "Another Claude session sent a message: hello"}]}}
# A loaded skill's text, as scripts/absence-claim-locator-reminder-hook-test.py records it.
SKILL_LOADED = {"type": "user", "isMeta": True, "message": {"role": "user", "content": [
    {"type": "text", "text": "Base directory for this skill: /x\n\n# walk-me-through"}]}}
LATER_TEXT = {"type": "assistant", "message": {"id": "m3", "content": [
    {"type": "text", "text": "The background job finished."}]}}


def test_where_the_turn_starts():
    case = Case()
    case.walk_files(minutes="Next to present: item 2 of 9.")
    item = section("## Item 2 of 9", "## Item 4.1 of 9")
    for case_name, records, shown in (
            ("a turn that wrote to the user, then made tool calls, shows the item",
             turn_records(TOOL_CALL, TOOL_RESULT), True),
            ("a skill loaded inside the turn does not start a new turn",
             turn_records(TOOL_CALL, TOOL_RESULT, SKILL_LOADED, TOOL_CALL, TOOL_RESULT), True),
            ("a silent turn after a background-task notice shows nothing",
             turn_records(NOTICE, TOOL_CALL, TOOL_RESULT), False),
            ("a silent turn after another agent-seat's message shows nothing",
             turn_records(PEER_MESSAGE, TOOL_CALL), False),
            ("a turn after a notice that wrote to the user shows the item",
             turn_records(NOTICE, TOOL_CALL, TOOL_RESULT, LATER_TEXT), True)):
        case.transcript.write_text("".join(json.dumps(record) + "\n" for record in records))
        if shown:
            check_shown(case_name, case.run(), item)
        else:
            check_silent(case_name, case.run())


def test_unparseable_line():
    case = Case()
    case.walk_files(minutes="Next to present: the poem question.")
    case.reply(ITEM_2_REPLY)
    check_blocked("a Next to present: line naming no item is sent back to be corrected",
                  case.run(), "could not be checked", "the poem question",
                  "Then end the turn: this hook shows the user the items the line names.")


def test_missing_walk_document():
    case = Case()
    case.walk_files(minutes="Next to present: item 2 of 9.", document=None)
    case.reply(ITEM_2_REPLY)
    check_blocked("a missing walk-document is named", case.run(), "does not exist")


def test_missing_heading():
    case = Case()
    case.walk_files(minutes="Next to present: item 3 of 9.")
    case.reply(ITEM_2_REPLY)
    check_blocked("a heading the walk-document lacks is named", case.run(),
                  "no heading `Item 3 of 9`")


def test_closed_and_last_line_wins():
    case = Case()
    case.walk_files(minutes="Next to present: item 2 of 9.\n\nNext to present: none, closed.")
    case.reply("All done.")
    check_silent("a walk whose last line is none, closed. is not open", case.run())
    case = Case()
    case.walk_files(minutes="Next to present: none, closed.\n\nNext to present: item 2 of 9.")
    case.reply("All done.")
    check_shown("a reopened walk's last line counts", case.run(),
                section("## Item 2 of 9", "## Item 4.1 of 9"))


def test_minutes_without_line_are_not_open():
    case = Case()
    case.walk_files(minutes="## Item 1 of 9 — Y")
    case.reply("Anything at all.")
    check_silent("minutes without a Next to present: line are not an open walk", case.run())


def test_newest_open_walk_is_checked():
    case = Case()
    case.walk_files(name="older-walk", minutes="Next to present: item 5 of 9.", modified=1_000)
    case.walk_files(name="newer-walk", minutes="Next to present: item 2 of 9.", modified=2_000)
    case.reply("Recorded.")
    check_shown("the most recently modified open walk's item is the one shown", case.run(),
                section("## Item 2 of 9", "## Item 4.1 of 9"))


def test_silent_cases():
    case = Case()
    case.walk_files(minutes="Next to present: item 2 of 9.")
    case.reply("No item here.")
    check_silent("stop_hook_active keeps the hook silent", case.run(stop_hook_active=True))
    check_silent("a headless child is shown nothing",
                 case.run(environment_extra={"CLAUDE_CODE_SESSION_ATTENDED": "0"}))
    case.reply(None)
    check_silent("a turn that wrote nothing to the user shows nothing", case.run())
    without_walk = Case(with_walk_directory=False)
    without_walk.reply("No item here.")
    check_silent("a checkout without docs/walk shows nothing", without_walk.run())
    outside = Case(in_git=False)
    outside.reply("No item here.")
    check_silent("a cwd outside any checkout shows nothing", outside.run())


def test_faults_are_reported():
    case = Case()
    result = case.run(stdin_text="not json")
    check("input that is not JSON exits 1 and names the fault on stderr",
          result.returncode == 1 and "the hook failed" in result.stderr and result.stdout == "",
          f"exit {result.returncode}, stderr {result.stderr!r}")
    case = Case()
    minutes = case.walk_files(minutes="Next to present: item 2 of 9.")
    case.reply(ITEM_2_REPLY)
    minutes.write_bytes(b"Next to present: \xff\xfe item 2 of 9.\n")
    result = case.run()
    check("minutes that cannot be read exit 1 and name the fault on stderr",
          result.returncode == 1 and "UnicodeDecodeError" in result.stderr,
          f"exit {result.returncode}, stderr {result.stderr!r}")


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
