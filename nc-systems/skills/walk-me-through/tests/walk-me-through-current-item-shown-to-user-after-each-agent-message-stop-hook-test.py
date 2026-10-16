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


ANSWERS_LINE = "Answer Y to approve, N to decline, D to defer, R to repeat the item, or E to have it explained."


def without_bold_marks_outside_code_spans(line):
    """The line's `**` left out, except inside `code` spans; the fixtures' spans use one backtick."""
    pieces = line.split("`")
    return "`".join(piece if index % 2 else piece.replace("**", "")
                    for index, piece in enumerate(pieces))


def check_shown(case_name, result, *units, wanted_text=None):
    """The hook shows the user the units' walk-document text, then the answers.

    Heading and bold marks and separator lines are left out, because Claude Code shows
    them as written; lines inside a ``` fence and text inside a `code` span stay as written.
    wanted_text, when given, is the shown text itself, for fixtures the rule above cannot derive.
    """
    if wanted_text is None:
        shown_lines, in_fence = [], False
        for line in "\n".join(unit.strip("\n") for unit in units).splitlines():
            if line.startswith("```"):
                in_fence = not in_fence
                shown_lines.append(line)
            elif in_fence:
                shown_lines.append(line)
            elif line.strip() != "---":
                line = line[line.index(" ") + 1:] if line.startswith("#") else line
                shown_lines.append(without_bold_marks_outside_code_spans(line))
        wanted_text = "\n".join(shown_lines).strip("\n")
    wanted = wanted_text + "\n\n" + ANSWERS_LINE
    output = json.loads(result.stdout) if result.returncode == 0 and result.stdout.strip() else {}
    check(case_name, output == {"systemMessage": wanted},
          f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")


def check_blocked(case_name, result, *phrases):
    reason = blocked_reason(result)
    check(case_name, reason is not None and all(phrase in reason for phrase in phrases),
          f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")


def test_shows_current_item_whatever_the_reply_says():
    case = Case()
    case.walk_files(minutes="#next_to_present item 2 of 9.")
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


CODE_WALK_DOCUMENT = """# A walk with code

## Item 1 of 2: the log-store path

The search reads `/home/nedlern/**` and **every** record under it. The steps:

```bash
# list the walks
ls docs/walk/**/*-minutes.md
```

The settings file opens:

```yaml
---
name: x
```

    ## an indented **code** line stays

**Recommendation: Y.**

---

## Item 2 of 2: done

Nothing.
"""
CODE_ITEM_SHOWN = """Item 1 of 2: the log-store path

The search reads `/home/nedlern/**` and every record under it. The steps:

```bash
# list the walks
ls docs/walk/**/*-minutes.md
```

The settings file opens:

```yaml
---
name: x
```

    ## an indented **code** line stays

Recommendation: Y."""


def test_code_is_shown_as_written():
    case = Case()
    case.walk_files(minutes="#next_to_present item 1 of 2.", document=CODE_WALK_DOCUMENT)
    case.reply("Recorded.")
    result = case.run()
    check_shown("marks inside code spans, fenced blocks and indented code are shown as written",
                result, wanted_text=CODE_ITEM_SHOWN)
    shown = json.loads(result.stdout)["systemMessage"] if result.returncode == 0 and result.stdout else ""
    check("a code span keeps its **", "`/home/nedlern/**`" in shown, repr(shown))
    check("a fenced bash comment keeps its #", "\n# list the walks\n" in shown, repr(shown))
    check("an indented code line keeps its ## and **", "    ## an indented **code** line stays" in shown,
          repr(shown))
    check("a fenced line keeps its **", "ls docs/walk/**/*-minutes.md" in shown, repr(shown))
    check("a fenced yaml --- line is kept", "```yaml\n---\nname: x" in shown, repr(shown))
    check("bold marks outside code are still left out", "and every record" in shown, repr(shown))


def test_items_shown_together():
    case = Case()
    case.walk_files(minutes="#next_to_present items 5 and 6 of 9.")
    case.reply("Recorded.")
    check_shown("items shown together are both shown, in the walk-document's order", case.run(),
                section("## Item 5 of 9", "## Item 6 of 9"),
                section("## Item 6 of 9", "## Items 7 and 8 of 9"))


def test_items_under_one_heading():
    case = Case()
    case.walk_files(minutes="#next_to_present items 7 and 8 of 9.")
    case.reply("Recorded.")
    check_shown("items under one heading are shown whole", case.run(),
                section("## Items 7 and 8 of 9", "## Item 9 of 9"))


def test_part_without_recommendation():
    case = Case()
    case.walk_files(minutes="#next_to_present item 4.1 of 9.")
    case.reply("Recorded.")
    check_shown("a part is shown alone, without the next part", case.run(),
                section("## Item 4.1 of 9", "## Item 5 of 9"))


def test_item_holding_original_and_proposed_sections():
    case = Case()
    case.walk_files(minutes="#next_to_present item 9 of 9.")
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
    case.walk_files(minutes="#next_to_present item 2 of 9.")
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


RANGE_WALK_DOCUMENT = """# A walk with ranges

## Item 9 of 54: nine

Nine text. Recommendation: Y.

## Items 10 to 12 of 54: three small cuts

Item 10 of 54 cuts a word. Item 11 of 54 cuts a line. Item 12 of 54 cuts a path. Recommendation: Y.

## Item 12.1 of 54: a part

Part one. The steps:

```text
## Item 13 of 54: inside a fence, not a heading
```

## Item 12.2 of 54: another part

Part two. Recommendation: Y.

## Item 13 of 54: last

Last. Recommendation: Y.
"""


def range_section(start, end=None):
    text = RANGE_WALK_DOCUMENT
    return text[text.index(start):text.index(end) if end else len(text)]


def test_range_headings_and_values():
    for case_name, minutes, start, end in (
            ("an item before a range heading ends at the range heading",
             "#next_to_present item 9 of 54.", "## Item 9 of 54", "## Items 10 to 12 of 54"),
            ("minutes naming a range show the range heading's unit",
             "#next_to_present items 10 to 12 of 54.", "## Items 10 to 12 of 54", "## Item 12.1 of 54"),
            ("minutes listing the range's items show the same unit",
             "#next_to_present items 10, 11 and 12 of 54.", "## Items 10 to 12 of 54", "## Item 12.1 of 54"),
            ("a dashed range is read as a range",
             "#next_to_present items 10-12 of 54.", "## Items 10 to 12 of 54", "## Item 12.1 of 54"),
            ("one item inside a range heading shows the range's unit",
             "#next_to_present item 11 of 54.", "## Items 10 to 12 of 54", "## Item 12.1 of 54"),
            ("a running count inside a code fence starts no item",
             "#next_to_present item 12.1 of 54.", "## Item 12.1 of 54", "## Item 12.2 of 54")):
        case = Case()
        case.walk_files(minutes=minutes, document=RANGE_WALK_DOCUMENT)
        case.reply("Recorded.")
        check_shown(case_name, case.run(), range_section(start, end))
    case = Case()
    case.walk_files(minutes="#next_to_present items 12.1 to 12.2 of 54.", document=RANGE_WALK_DOCUMENT)
    case.reply("Recorded.")
    check_shown("a dotted range shows its parts", case.run(),
                range_section("## Item 12.1 of 54", "## Item 12.2 of 54"),
                range_section("## Item 12.2 of 54", "## Item 13 of 54: last"))
    backwards_document = ("# A walk\n\n## Item 9 of 54: first\n\nText.\n\n"
                          "## Items 12 to 10 of 54: backwards\n\nMore.\n\n"
                          "## Item 13 of 54: last\n\nEnd.\n")
    case = Case()
    case.walk_files(minutes="#next_to_present item 9 of 54.", document=backwards_document)
    case.reply("Recorded.")
    check_shown("a heading whose range runs backwards still ends the item before it", case.run(),
                wanted_text="Item 9 of 54: first\n\nText.")
    case = Case()
    case.walk_files(minutes="#next_to_present item 10 of 54.", document=backwards_document)
    case.reply("Recorded.")
    check_blocked("minutes naming an item of a heading whose range runs backwards are told that heading",
                  case.run(), "no heading `Item 10 of 54`",
                  "heading `Items 12 to 10 of 54: backwards` names no item", "`12 to 10` runs backwards")
    item_and_parts = ("# A walk\n\n## Item 11 of 54: before\n\nBefore.\n\n"
                      "## Items 12 to 12.2 of 54: an item and its inserted questions\n\nTogether.\n\n"
                      "## Item 13 of 54: after\n\nAfter.\n")
    for case_name, minutes in (
            ("minutes naming an item and its parts show the heading that groups them",
             "#next_to_present items 12 to 12.2 of 54."),
            ("minutes naming one part show the heading that groups the item and its parts",
             "#next_to_present item 12.1 of 54."),
            ("minutes naming the item alone show the heading that groups it with its parts",
             "#next_to_present item 12 of 54.")):
        case = Case()
        case.walk_files(minutes=minutes, document=item_and_parts)
        case.reply("Recorded.")
        check_shown(case_name, case.run(),
                    wanted_text="Items 12 to 12.2 of 54: an item and its inserted questions\n\nTogether.")
    case = Case()
    case.walk_files(minutes="#next_to_present item 5 of 9.",
                    document=WALK_DOCUMENT + "\n## Item 5 of 9: a misnumbered copy\n\nText.\n")
    case.reply("Recorded.")
    check_blocked("minutes naming an item two headings carry are told the heading is misnumbered",
                  case.run(), "more than one heading for `Item 5 of 9`", "misnumbered")
    case = Case()
    case.walk_files(minutes="#next_to_present items 12 to 10 of 54.", document=RANGE_WALK_DOCUMENT)
    case.reply("Recorded.")
    check_blocked("a backwards range is sent back as backwards", case.run(), "items 12 to 10 of 54",
                  "`12 to 10` runs backwards", "`items 10 to 12`")
    for case_name, minutes, phrases in (
            ("a backwards range after a listed item is sent back as backwards, not cut to the item",
             "#next_to_present items 9, 12 to 10 of 54.", ("`12 to 10` runs backwards",)),
            ("a range across parts of different items is sent back as crossing items",
             "#next_to_present items 12.1 to 13 of 54.",
             ("`12.1 to 13` runs between parts of different items",)),
            ("a dotted range across items is sent back as crossing items",
             "#next_to_present items 4.9 to 5.1 of 9.",
             ("`4.9 to 5.1` runs between parts of different items",)),
            ("a chained range is sent back as a line naming no item",
             "#next_to_present items 10 to 11 to 12 of 54.", ("does not open with an item",))):
        case = Case()
        case.walk_files(minutes=minutes, document=RANGE_WALK_DOCUMENT)
        case.reply("Recorded.")
        result = case.run()
        check_blocked(case_name, result, *phrases)
        if "does not open with an item" not in phrases:
            check(case_name + ", and not told it is in no form",
                  "does not open with an item" not in (blocked_reason(result) or ""), result.stdout)


GROUPED_WALK_DOCUMENT = """# A walk with grouped items

## Item 9 of 12: before

Before. Recommendation: Y.

## Items 10 and 11 of 12: two small changes

**Item 10 of 12: the hook's message carries the diff.** Proposed: a diff. Recommendation: Y.

**Item 11 of 12: drop the timed test.** Proposed: a benchmark. Recommendation: Y.

## Item 12 of 12: after

After. Recommendation: Y.
"""

REVISED_WALK_DOCUMENT = """# A walk with a kept original

## Item 26 of 72: before

Before. Recommendation: Y.

## Item 27 of 72: keeping the design true

The original. Recommendation: Y.

## Item 27 of 72 (revised): keeping code and design in step

The revision. Recommendation: Y.

## Item 28 of 72: after

After. Recommendation: Y.
"""


def test_grouped_heading_paragraphs_and_kept_revisions_are_shown():
    whole_group = ("Items 10 and 11 of 12: two small changes\n\n"
                   "Item 10 of 12: the hook's message carries the diff. Proposed: a diff. Recommendation: Y.\n\n"
                   "Item 11 of 12: drop the timed test. Proposed: a benchmark. Recommendation: Y.")
    for case_name, minutes in (
            ("minutes naming a grouped heading show it with its items' bold paragraphs",
             "#next_to_present items 10 and 11 of 12."),
            ("minutes naming one item of a grouped heading show the whole group",
             "#next_to_present item 11 of 12."),
            ("minutes naming a grouped item without a total show the whole group",
             "#next_to_present item 10.")):
        case = Case()
        case.walk_files(minutes=minutes, document=GROUPED_WALK_DOCUMENT)
        case.reply("Recorded.")
        check_shown(case_name, case.run(), wanted_text=whole_group)
    case = Case()
    case.walk_files(minutes="#next_to_present item 11 of 12.",
                    document=GROUPED_WALK_DOCUMENT.replace(
                        "## Item 12 of 12: after\n\nAfter.",
                        "## Item 12 of 12: after\n\n**Item 11 of 12: misplaced.** Text.\n\nAfter."))
    case.reply("Recorded.")
    check_blocked("a bold paragraph naming an item its heading does not name still starts an item",
                  case.run(), "more than one heading for `Item 11 of 12`")
    for case_name, minutes in (
            ("minutes naming an item kept beside its revision show only the revision",
             "#next_to_present item 27 of 72."),
            ("minutes naming a revised item without a total show only the revision",
             "#next_to_present item 27.")):
        case = Case()
        case.walk_files(minutes=minutes, document=REVISED_WALK_DOCUMENT)
        case.reply("Recorded.")
        check_shown(case_name, case.run(),
                    wanted_text="Item 27 of 72 (revised): keeping code and design in step\n\n"
                                "The revision. Recommendation: Y.")
    case = Case()
    case.walk_files(minutes="#next_to_present item 26 of 72.", document=REVISED_WALK_DOCUMENT)
    case.reply("Recorded.")
    check_shown("an item before a kept original still ends at the original", case.run(),
                wanted_text="Item 26 of 72: before\n\nBefore. Recommendation: Y.")
    case = Case()
    case.walk_files(minutes="#next_to_present item 10 of 13.",
                    document=GROUPED_WALK_DOCUMENT.replace(
                        "**Item 11 of 12: drop", "**Item 10 of 13: another count.** Text.\n\n**Item 11 of 12: drop"))
    case.reply("Recorded.")
    check_shown("a bold paragraph with another total under a grouped heading starts its own item", case.run(),
                wanted_text="Item 10 of 13: another count. Text.")
    case = Case()
    case.walk_files(minutes="#next_to_present item 27 of 72.",
                    document=REVISED_WALK_DOCUMENT.replace("## Item 27 of 72 (revised)", "## Item 27 of 76 (revised)"))
    case.reply("Recorded.")
    check_shown("a revision under another total leaves the original shown", case.run(),
                wanted_text="Item 27 of 72: keeping the design true\n\nThe original. Recommendation: Y.")
    case = Case()
    case.walk_files(minutes="#next_to_present item 10 of 54.",
                    document=("# A walk\n\n## Item 9 of 54: first\n\nText.\n\n"
                              "## Items 12 to 10 of 54: backwards\n\nMore.\n\n"
                              "## Item 13 of 54 (revised): last\n\nEnd.\n"))
    case.reply("Recorded.")
    check_blocked("a later revision leaves a heading that names no item named in the block", case.run(),
                  "heading `Items 12 to 10 of 54: backwards` names no item")
    case = Case()
    case.walk_files(minutes="#next_to_present item 27 of 72.",
                    document=REVISED_WALK_DOCUMENT.replace("## Item 27 of 72 (revised)", "## Item 27 of 72"))
    case.reply("Recorded.")
    check_blocked("two headings for one item, neither a revision, still block", case.run(),
                  "more than one heading for `Item 27 of 72`", "misnumbered", "`(revised)`")


def test_where_the_minutes_line_sits():
    item_2 = section("## Item 2 of 9", "## Item 4.1 of 9")
    for case_name, minutes in (
            ("a line inside a bullet counts", "- #next_to_present item 2 of 9."),
            ("a bold marker counts", "**#next_to_present** item 2 of 9"),
            ("a line without `of M` uses the walk-document's total", "#next_to_present item 2."),
            ("words after the running count are ignored",
             "#next_to_present item 2 (awaiting answer), then item 5, then item 6."),
            ("a comma and a note after the count are ignored",
             "#next_to_present item 2 of 9, the poem page (item 1 was dropped)."),
            ("a value inside a code span is read without its backticks", "#next_to_present `item 2 of 9.`"),
            ("of two markers on one line, the second counts",
             "#next_to_present item 5 of 9. Then #next_to_present item 2 of 9."),
            ("a colon after the hashtag is read as the old form's colon was", "#next_to_present: item 2 of 9."),
            ("a marker inside a code span or a fence is not the last line",
             "#next_to_present item 2 of 9.\n\nThe hook asks for `#next_to_present item 5 of 9.`\n\n"
             "```\n#next_to_present item 6 of 9.\n```")):
        case = Case()
        case.walk_files(minutes=minutes)
        case.reply("Recorded.")
        check_shown(case_name, case.run(), item_2)
    for case_name, minutes in (
            ("a walk closed mid-sentence is not open",
             "#next_to_present item 2 of 9.\n\nSwept into another walk; #next_to_present none, closed."),
            ("a walk closed with `closed` alone is not open", "#next_to_present closed."),
            ("a walk closed with a colon after the hashtag is not open",
             "#next_to_present item 2 of 9.\n\n#next_to_present: none, closed."),
            ("a walk closed after a stale marker on the same line is not open",
             "#next_to_present item 2 of 9. Swept; #next_to_present none, closed."),
            ("a closed value inside a code span is read", "#next_to_present item 2 of 9.\n\n"
             "Next to present: `none, closed.`")):
        case = Case()
        case.walk_files(minutes=minutes)
        case.reply("Recorded.")
        check_silent(case_name, case.run())
    case = Case()
    case.walk_files(minutes="#next_to_present item 2.",
                    document=WALK_DOCUMENT + "\n## Item 2 of 10: a re-planned copy\n\nText.\n")
    case.reply("Recorded.")
    check_blocked("a line without `of M` over headings with two totals is sent back", case.run(),
                  "gives no `of M`", "more than one total (`of 9`, `of 10`)")
    case = Case()
    case.walk_files(minutes="#next_to_present item 2.",
                    document="# A walk\n\n## The poem page\n\nText.\n\n## The summary\n\nText.\n")
    case.reply("Recorded.")
    result = case.run()
    check_blocked("a line without `of M` over headings with no running count is told the headings "
                  "lack counts", result, "has no heading with a running count", "`Item N of M`",
                  "lacks its running count `of M`")
    check("a walk-document with no counted heading is not told it has more than one total",
          "more than one total" not in (blocked_reason(result) or ""), result.stdout)
    case = Case()
    case.walk_files(minutes="#next_to_present item 2 of 9.",
                    document=WALK_DOCUMENT + "\n## Item 2 of 10: a re-planned copy\n\nText.\n")
    case.reply("Recorded.")
    check_shown("only the heading with the minutes' total is shown", case.run(), item_2)


def test_unparseable_line():
    case = Case()
    case.walk_files(minutes="#next_to_present the poem question.")
    case.reply(ITEM_2_REPLY)
    check_blocked("a #next_to_present line naming no item is sent back to be corrected",
                  case.run(), "could not be checked", "the poem question",
                  "Then end the turn: this hook shows the user the items the line names.")


def test_missing_walk_document():
    case = Case()
    case.walk_files(minutes="#next_to_present item 2 of 9.", document=None)
    case.reply(ITEM_2_REPLY)
    check_blocked("a missing walk-document is named", case.run(), "does not exist")


def test_missing_heading():
    case = Case()
    case.walk_files(minutes="#next_to_present item 3 of 9.")
    case.reply(ITEM_2_REPLY)
    check_blocked("a heading the walk-document lacks is named", case.run(),
                  "no heading `Item 3 of 9`")


def test_closed_and_last_line_wins():
    case = Case()
    case.walk_files(minutes="#next_to_present item 2 of 9.\n\n#next_to_present none, closed.")
    case.reply("All done.")
    check_silent("a walk whose last line is none, closed. is not open", case.run())
    case = Case()
    case.walk_files(minutes="#next_to_present none, closed.\n\n#next_to_present item 2 of 9.")
    case.reply("All done.")
    check_shown("a reopened walk's last line counts", case.run(),
                section("## Item 2 of 9", "## Item 4.1 of 9"))


def test_minutes_without_line_are_not_open():
    case = Case()
    case.walk_files(minutes="## Item 1 of 9 — Y")
    case.reply("Anything at all.")
    check_silent("minutes without a #next_to_present line are not an open walk", case.run())


def test_old_marker_is_migrated():
    item_2 = section("## Item 2 of 9", "## Item 4.1 of 9")
    case = Case()
    minutes = case.walk_files(minutes="Next to present: item 2 of 9.")
    case.reply("Recorded.")
    result = case.run()
    check_blocked("an open walk marked only with the old form is told the line to add", result,
                  "is the old form `Next to present:`", f"at the end of {minutes}",
                  "leave the old lines as they are: #next_to_present item 2 of 9\n",
                  "Then end the turn: this hook shows the user the items the new line names.")
    check("the old form's block shows no item", "where the poem page lives" not in result.stdout,
          result.stdout)
    case = Case()
    case.walk_files(minutes="#next_to_present item 2 of 9\n\nNext to present: item 5 of 9.")
    case.reply("Recorded.")
    check_blocked("an old-form line below a hashtag line is the newest marker and is migrated",
                  case.run(), "#next_to_present item 5 of 9")
    case = Case()
    case.walk_files(minutes="Next to present: item 5 of 9.\n\n#next_to_present item 2 of 9")
    case.reply("Recorded.")
    check_shown("a hashtag line below an old-form line counts", case.run(), item_2)
    case = Case()
    case.walk_files(minutes="Next to present: `item 2 of 9.`")
    case.reply("Recorded.")
    check_blocked("an old-form value inside a code span is carried whole into the line to add",
                  case.run(), "leave the old lines as they are: #next_to_present item 2 of 9\n")
    case = Case()
    case.walk_files(minutes="Next to present: item 2 of 9.\n\nNext to present: none, closed.")
    case.reply("All done.")
    check_silent("a walk closed with the old form is not open", case.run())
    case = Case()
    case.walk_files(minutes="Next to present: item 2 of 9.")
    case.reply("Recorded.")
    check_silent("while the agent answers a Stop hook, the old form's block is not printed",
                 case.run(stop_hook_active=True))


def test_newest_open_walk_is_checked():
    case = Case()
    case.walk_files(name="older-walk", minutes="#next_to_present item 5 of 9.", modified=1_000)
    case.walk_files(name="newer-walk", minutes="#next_to_present item 2 of 9.", modified=2_000)
    case.reply("Recorded.")
    check_shown("the most recently modified open walk's item is the one shown", case.run(),
                section("## Item 2 of 9", "## Item 4.1 of 9"))


def test_silent_cases():
    case = Case()
    case.walk_files(minutes="#next_to_present item 2 of 9.")
    case.reply("No item here.")
    check_shown("while the agent answers a Stop hook, the item notice is still shown",
                case.run(stop_hook_active=True), section("## Item 2 of 9", "## Item 4.1 of 9"))
    unusable = Case()
    unusable.walk_files(minutes="#next_to_present item 12 to 10 of 9.")
    unusable.reply("No item here.")
    check_blocked("unusable minutes block when the agent is not answering a Stop hook", unusable.run())
    check_silent("while the agent answers a Stop hook, a block on unusable minutes is not printed",
                 unusable.run(stop_hook_active=True))
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


def test_nothing_is_installed_while_the_agent_answers_a_stop_hook():
    case = Case()
    case.walk_files(minutes="#next_to_present item 2 of 9.")
    case.reply("No item here.")
    shadow = case.root / "shadow"
    (shadow / "markdown_it").mkdir(parents=True)
    (shadow / "markdown_it" / "__init__.py").write_text(
        'raise ImportError("markdown-it-py hidden by this case")\n')
    result = case.run(stop_hook_active=True,
                      environment_extra={"PYTHONPATH": str(shadow), "PYTHONDONTWRITEBYTECODE": "1",
                                         # A hook that wrongly installs writes its install state here.
                                         "HOME": str(case.root)})
    check("while the agent answers a Stop hook, a missing markdown-it-py is a fault, not an install",
          result.returncode == 1 and "markdown-it-py hidden by this case" in result.stderr
          and "MarkdownParserMissing" not in result.stderr and result.stdout == "",
          f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")


def test_faults_are_reported():
    case = Case()
    result = case.run(stdin_text="not json")
    check("input that is not JSON exits 1 and names the fault on stderr",
          result.returncode == 1 and "the hook failed" in result.stderr and result.stdout == "",
          f"exit {result.returncode}, stderr {result.stderr!r}")
    case = Case()
    minutes = case.walk_files(minutes="#next_to_present item 2 of 9.")
    case.reply(ITEM_2_REPLY)
    minutes.write_bytes(b"#next_to_present \xff\xfe item 2 of 9.\n")
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
