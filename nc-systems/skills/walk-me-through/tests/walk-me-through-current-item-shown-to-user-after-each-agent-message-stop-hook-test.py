#!/usr/bin/env python3
"""Cases for the Stop hook that, during an open approval-walk, blocks the
agent's stop when its reply to the user does not name the waiting item.

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
SUITE_ROOT = Path(tempfile.mkdtemp(prefix="approval-walk-current-item-hook-test-")).resolve()
failures = []

WALK_DOCUMENT = """# A walk: approval-walk

This approval-walk settles two questions about the poem page. It has 9 items.

## Item 2 of 9: where the poem page lives

The poem page goes in the wiki, next to the glossary and the style guide, so that agents find it where they already look for project terms. Its name is checked against the [naming page](file:///x/naming.md) before the file is created.

**The strongest case for N:** a page in the wiki is one more document agents must be told to read. **Recommendation: Y.**

---

## Item 4.1 of 9: how a poem row reads

One row per job an agent is about to do, written "to do X, use Y", with one example call and the mistake it prevents, so an agent reading the row can act on it without opening anything else.

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

ITEM_2_REPLY = """Recorded your answer to item 1.

**Item 2 of 9: where the poem page lives**

The poem page goes in the wiki, next to the glossary and the style guide, so that agents find it where they already look for project terms. Its name is checked against the naming page before the file is created.

**The strongest case for N:** a page in the wiki is one more document agents must be told to read. **Recommendation: Y.**"""


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


def check_reminded(case_name, result, *phrases):
    """The hook sends the agent back to name the waiting item its reply left out."""
    check_blocked(case_name, result, "does not name", "waiting for his answer", *phrases)


def check_blocked(case_name, result, *phrases):
    reason = blocked_reason(result)
    check(case_name, reason is not None and all(phrase in reason for phrase in phrases),
          f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")


def test_a_reply_naming_the_waiting_item_passes_and_one_leaving_it_out_is_sent_back():
    case = Case()
    case.walk_files(minutes="#next_to_present item 2 of 9.")
    for case_name, reply in (
            ("a reply showing the item in full passes", ITEM_2_REPLY),
            ("a reply ending with a line naming the item passes",
             "The background job finished.\n\nItem 2 of 9 is waiting for your answer."),
            ("a reply naming the item in lower case mid-sentence passes",
             "Recorded. Waiting on item 2 of 9; Recommendation: Y."),
            ("a reply naming the item in a heading passes", "## Item 2 of 9: where the poem page lives\n\nText."),
            ("a reply naming the item in a range passes", "Items 1 to 3 of 9 are waiting.")):
        case.reply(reply)
        check_silent(case_name, case.run())
    for case_name, reply in (
            ("a reply that never mentions the item is sent back",
             "The background job finished and its report is in the log-store."),
            ("a reply naming the item without its total is sent back", "Answer item 2: Y or N."),
            ("a reply naming the item with another total is sent back", "Item 2 of 90 is waiting."),
            ("a reply naming another item is sent back", "Item 5 of 9 is waiting for your answer."),
            ("a reply naming the item's part is sent back", "Item 2.1 of 9 is waiting."),
            ("a word ending in `item` is not a running count", "Lineitem 2 of 9 is fixed."),
            ("a reply naming the item in a backwards range is sent back", "Items 3 to 1 of 9 are waiting.")):
        case.reply(reply)
        check_reminded(case_name, case.run(), "`Item 2 of 9`",
                       "`Item 2 of 9 is waiting for your answer.`")
    case.reply("Nothing here.")
    reason = blocked_reason(case.run()) or ""
    check("the reminder names the walk, its walk-document and its minutes",
          "poem-page-2026-10-12" in reason and str(case.walk / "poem-page-2026-10-12.md") in reason
          and str(case.walk / "poem-page-2026-10-12-minutes.md") in reason, reason)


def test_every_text_of_the_turn_counts():
    case = Case()
    case.walk_files(minutes="#next_to_present item 2 of 9.")
    case.reply(ITEM_2_REPLY, None, "Recorded.")
    check_silent("a turn that shows the item, makes a tool call and ends with a short line passes", case.run())
    case.reply("Recorded.", None, "Item 2 of 9 is waiting for your answer.")
    check_silent("a turn naming the item in its last text passes", case.run())
    shown_before_answer = [USER_PROMPT, {"type": "assistant", "message": {"id": "m1", "content": [
        {"type": "text", "text": ITEM_2_REPLY}]}}, TOOL_CALL, USER_ANSWER_WHILE_WORKING, TOOL_RESULT,
        {"type": "assistant", "message": {"id": "m4", "content": [{"type": "text", "text": "Recorded."}]}}]
    case.transcript.write_text("".join(json.dumps(record) + "\n" for record in shown_before_answer))
    check_reminded("an item named before the user typed into the turn does not count after it", case.run())
    shown_in_earlier_turn = [USER_PROMPT, {"type": "assistant", "message": {"id": "m1", "content": [
        {"type": "text", "text": ITEM_2_REPLY}]}}, USER_PROMPT,
        {"type": "assistant", "message": {"id": "m2", "content": [{"type": "text", "text": "Recorded."}]}}]
    case.transcript.write_text("".join(json.dumps(record) + "\n" for record in shown_in_earlier_turn))
    check_reminded("an item named in an earlier turn does not count in the next one", case.run())


# The two records Claude Code writes when it compacts a conversation, in the shape of a real
# transcript: the summary is a user record that is not isMeta, and its content is a string.
COMPACT_BOUNDARY = {"type": "system", "subtype": "compact_boundary", "content": "Conversation compacted",
                    "isMeta": False, "level": "info", "parentUuid": None,
                    "compactMetadata": {"trigger": "auto", "preTokens": 276544}}
COMPACT_SUMMARY = {"type": "user", "isCompactSummary": True, "isVisibleInTranscriptOnly": True,
                   "promptId": "p1", "turnPosition": {"promptIndex": 1, "turnIndex": 76},
                   "message": {"role": "user", "content":
                               "This session is being continued from a previous conversation that ran out "
                               "of context. The summary below covers the earlier portion of the conversation."}}


def test_a_compaction_does_not_start_a_turn():
    case = Case()
    case.walk_files(minutes="#next_to_present item 2 of 9.")
    recorded = {"type": "assistant", "message": {"id": "m4", "content": [{"type": "text", "text": "Recorded."}]}}
    shown = {"type": "assistant", "message": {"id": "m1", "content": [{"type": "text", "text": ITEM_2_REPLY}]}}
    compacted_mid_turn = [USER_PROMPT, shown, TOOL_CALL, TOOL_RESULT, COMPACT_BOUNDARY, COMPACT_SUMMARY, recorded]
    case.transcript.write_text("".join(json.dumps(record) + "\n" for record in compacted_mid_turn))
    check_silent("an item shown before a compaction in the same turn still counts", case.run())
    compacted_between_turns = [USER_PROMPT, shown, COMPACT_BOUNDARY, COMPACT_SUMMARY, USER_PROMPT, recorded]
    case.transcript.write_text("".join(json.dumps(record) + "\n" for record in compacted_between_turns))
    check_reminded("an item shown in the turn before a compaction does not count in the turn after it",
                   case.run())


def test_an_ended_walk_is_closed_by_the_line_the_reminder_gives():
    case = Case()
    minutes = case.walk_files(minutes="#next_to_present item 2 of 9.")
    case.reply("We are stopping this walk.")
    reason = blocked_reason(case.run()) or ""
    closing_line = "#next_to_present none, closed"
    check("the reminder tells the agent how to close an ended or abandoned walk",
          f"If he ended or abandoned the approval-walk, add the line `{closing_line}` at the end of {minutes}"
          in reason, reason)
    minutes.write_text(minutes.read_text() + "\n" + closing_line + "\n")
    check_silent("minutes ending with the reminder's closing line are not an open walk", case.run())


def test_items_waiting_together():
    case = Case()
    case.walk_files(minutes="#next_to_present items 5 and 6 of 9.")
    case.reply("Recorded.")
    check_reminded("a reply naming neither of two waiting items is sent back with both", case.run(),
                   "`Item 5 of 9` and `Item 6 of 9`", "`Items 5 and 6 of 9 are waiting for your answer.`")
    case.reply("Item 5 of 9: the hook. Text.")
    check_reminded("a reply naming one of two waiting items is sent back with the other", case.run(),
                   "does not name `Item 6 of 9`,")
    for case_name, reply in (
            ("a reply naming both waiting items together passes", "Items 5 and 6 of 9 are waiting."),
            ("a reply naming both waiting items apart passes", "Item 5 of 9: one.\n\nItem 6 of 9: two.")):
        case.reply(reply)
        check_silent(case_name, case.run())


def test_items_under_one_heading():
    case = Case()
    case.walk_files(minutes="#next_to_present items 7 and 8 of 9.")
    case.reply("Recorded.")
    check_reminded("a reply naming neither item under one heading is sent back", case.run())


def test_part_without_recommendation():
    case = Case()
    case.walk_files(minutes="#next_to_present item 4.1 of 9.")
    case.reply("Recorded.")
    check_reminded("a reply leaving out a waiting part is sent back", case.run())


def test_item_holding_original_and_proposed_sections():
    case = Case()
    case.walk_files(minutes="#next_to_present item 9 of 9.")
    case.reply("Recorded.")
    check_reminded("a reply leaving out an item that holds its own headings is sent back", case.run())


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
    for case_name, records, checked in (
            ("a turn that wrote to the user, then made tool calls, is checked",
             turn_records(TOOL_CALL, TOOL_RESULT), True),
            ("a skill loaded inside the turn does not start a new turn",
             turn_records(TOOL_CALL, TOOL_RESULT, SKILL_LOADED, TOOL_CALL, TOOL_RESULT), True),
            ("a silent turn after a background-task notice is not checked",
             turn_records(NOTICE, TOOL_CALL, TOOL_RESULT), False),
            ("a silent turn after another agent-seat's message is not checked",
             turn_records(PEER_MESSAGE, TOOL_CALL), False),
            ("a turn after a notice that wrote text is not checked, because it does not answer the user",
             turn_records(NOTICE, TOOL_CALL, TOOL_RESULT, LATER_TEXT), False)):
        case.transcript.write_text("".join(json.dumps(record) + "\n" for record in records))
        if checked:
            check_reminded(case_name, case.run())
        else:
            check_silent(case_name, case.run())


def opening_prompt(turn_origin, text, **fields):
    """A turn's opening prompt as Claude Code records it, with its turnOrigin."""
    return {"type": "user", "turnOrigin": turn_origin, **fields,
            "message": {"role": "user", "content": [{"type": "text", "text": text}]}}


USER_PROMPT = opening_prompt("human", "what is PR 1188?", origin={"kind": "human"}, promptSource="typed")
PEER_PROMPT = opening_prompt("peer", "Another Claude session sent a message: PR 1188 merged.",
                             origin={"kind": "peer"}, isMeta=True, promptSource="system")
NOTICE_PROMPT = opening_prompt("task_notification", "<task-notification>done</task-notification>",
                               origin={"kind": "task-notification"}, promptSource="system")
SCHEDULED_PROMPT = opening_prompt("scheduled", "Hourly stall check.", isMeta=True, promptSource="system")


def typed_while_working(kind, prompt):
    """A prompt delivered into a running turn, in the form Claude Code writes it: no turnOrigin."""
    return {"type": "attachment", "attachment": {
        "type": "queued_command", "prompt": prompt, "commandMode": "prompt", "origin": {"kind": kind},
        **({"humanTurn": True} if kind == "human" else {})}}


PEER_MESSAGE_WHILE_WORKING = typed_while_working("peer", "Another Claude session sent a message: hi")
USER_ANSWER_WHILE_WORKING = typed_while_working("human", "Y")
REPLY_TEXT = {"type": "assistant", "message": {"id": "m9", "content": [
    {"type": "text", "text": "PR 1188 merged; nothing waits on you."}]}}


def test_only_a_turn_that_answers_the_user_is_checked():
    for case_name, records, checked in (
            ("a turn opened by the user's own prompt is checked",
             [PEER_PROMPT, REPLY_TEXT, USER_PROMPT, REPLY_TEXT], True),
            ("a queued prompt of the user's is checked",
             [opening_prompt("human", "and 5?", origin={"kind": "human"}, promptSource="queued"), REPLY_TEXT],
             True),
            ("a turn opened by another agent-seat's message is not checked",
             [USER_PROMPT, REPLY_TEXT, PEER_PROMPT, REPLY_TEXT], False),
            ("a turn opened by a background-task notice is not checked",
             [USER_PROMPT, REPLY_TEXT, NOTICE_PROMPT, REPLY_TEXT], False),
            ("a turn opened by a scheduled prompt is not checked",
             [USER_PROMPT, REPLY_TEXT, SCHEDULED_PROMPT, TOOL_CALL, TOOL_RESULT, REPLY_TEXT], False),
            ("a message that arrives while the agent answers the user leaves the turn the user's",
             [USER_PROMPT, TOOL_CALL, TOOL_RESULT, PEER_MESSAGE_WHILE_WORKING, REPLY_TEXT], True),
            ("the user's answer typed into a turn another agent-seat's message opened is checked",
             [USER_PROMPT, REPLY_TEXT, PEER_PROMPT, TOOL_CALL, USER_ANSWER_WHILE_WORKING, TOOL_RESULT, REPLY_TEXT],
             True),
            ("the user's answer typed into a turn a background-task notice opened is checked",
             [NOTICE_PROMPT, USER_ANSWER_WHILE_WORKING, REPLY_TEXT], True),
            ("the user's answer typed into a turn a scheduled prompt opened is checked",
             [SCHEDULED_PROMPT, TOOL_CALL, USER_ANSWER_WHILE_WORKING, TOOL_RESULT, REPLY_TEXT], True),
            ("another agent-seat's message typed into a turn another agent-seat's message opened is not checked",
             [USER_PROMPT, REPLY_TEXT, PEER_PROMPT, TOOL_CALL, PEER_MESSAGE_WHILE_WORKING, TOOL_RESULT, REPLY_TEXT],
             False),
            ("the user's answer typed into an earlier turn does not make a later agent-started turn his",
             [PEER_PROMPT, USER_ANSWER_WHILE_WORKING, REPLY_TEXT, NOTICE_PROMPT, REPLY_TEXT], False)):
        case = Case()
        case.walk_files(minutes="#next_to_present item 2 of 9.")
        case.transcript.write_text("".join(json.dumps(record) + "\n" for record in records))
        if checked:
            check_reminded(case_name, case.run())
        else:
            check_silent(case_name, case.run())
    without_turn_origin = {"type": "user", "origin": {"kind": "human"},
                           "message": {"role": "user", "content": "what is PR 1188?"}}
    for case_name, records, checked in (
            ("without turnOrigin, a prompt whose origin is the user's is checked",
             [without_turn_origin, REPLY_TEXT], True),
            ("without turnOrigin, a prompt with another origin is not checked",
             [dict(without_turn_origin, origin={"kind": "coordinator"}), REPLY_TEXT], False),
            ("a transcript with no prompt at all is not checked", [REPLY_TEXT], False),
            ("without turnOrigin, the user's answer typed into another origin's turn is checked",
             [dict(without_turn_origin, origin={"kind": "coordinator"}), USER_ANSWER_WHILE_WORKING, REPLY_TEXT],
             True),
            ("without turnOrigin, an answer typed into another origin's turn before it starts does not count",
             [USER_ANSWER_WHILE_WORKING, dict(without_turn_origin, origin={"kind": "coordinator"}), REPLY_TEXT],
             False),
            ("with no prompt at all, the user's answer typed while working is checked",
             [USER_ANSWER_WHILE_WORKING, REPLY_TEXT], True)):
        case = Case()
        case.walk_files(minutes="#next_to_present item 2 of 9.")
        case.transcript.write_text("".join(json.dumps(record) + "\n" for record in records))
        if checked:
            check_reminded(case_name, case.run())
        else:
            check_silent(case_name, case.run())
    case = Case()
    case.walk_files(minutes="#next_to_present item 12 to 10 of 9.")
    case.transcript.write_text("".join(json.dumps(record) + "\n"
                                       for record in (USER_PROMPT, REPLY_TEXT, PEER_PROMPT, REPLY_TEXT)))
    check_silent("unusable minutes do not block a turn that does not answer the user", case.run())
    case.transcript.write_text("".join(json.dumps(record) + "\n" for record in (PEER_PROMPT, REPLY_TEXT, USER_PROMPT, REPLY_TEXT)))
    check_blocked("unusable minutes block a turn that answers the user", case.run(), "runs backwards")


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


def test_range_headings_and_values():
    for case_name, minutes in (
            ("an item before a range heading ends at the range heading",
             "#next_to_present item 9 of 54."),
            ("minutes naming a range find the range heading",
             "#next_to_present items 10 to 12 of 54."),
            ("minutes listing the range's items find the same heading",
             "#next_to_present items 10, 11 and 12 of 54."),
            ("a dashed range is read as a range",
             "#next_to_present items 10-12 of 54."),
            ("one item inside a range heading is found under it",
             "#next_to_present item 11 of 54."),
            ("a running count inside a code fence starts no item",
             "#next_to_present item 12.1 of 54.")):
        case = Case()
        case.walk_files(minutes=minutes, document=RANGE_WALK_DOCUMENT)
        case.reply("Recorded.")
        check_reminded(case_name, case.run())
    case = Case()
    case.walk_files(minutes="#next_to_present items 12.1 to 12.2 of 54.", document=RANGE_WALK_DOCUMENT)
    case.reply("Recorded.")
    check_reminded("a dotted range finds its parts", case.run())
    backwards_document = ("# A walk\n\n## Item 9 of 54: first\n\nText.\n\n"
                          "## Items 12 to 10 of 54: backwards\n\nMore.\n\n"
                          "## Item 13 of 54: last\n\nEnd.\n")
    case = Case()
    case.walk_files(minutes="#next_to_present item 9 of 54.", document=backwards_document)
    case.reply("Recorded.")
    check_reminded("a heading whose range runs backwards still ends the item before it", case.run())
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
            ("minutes naming an item and its parts find the heading that groups them",
             "#next_to_present items 12 to 12.2 of 54."),
            ("minutes naming one part find the heading that groups the item and its parts",
             "#next_to_present item 12.1 of 54."),
            ("minutes naming the item alone find the heading that groups it with its parts",
             "#next_to_present item 12 of 54.")):
        case = Case()
        case.walk_files(minutes=minutes, document=item_and_parts)
        case.reply("Recorded.")
        check_reminded(case_name, case.run())
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


def test_grouped_heading_paragraphs_and_kept_revisions_are_found():
    for case_name, minutes in (
            ("minutes naming a grouped heading find it",
             "#next_to_present items 10 and 11 of 12."),
            ("minutes naming every item of a grouped heading without a total find the group",
             "#next_to_present items 10 to 11.")):
        case = Case()
        case.walk_files(minutes=minutes, document=GROUPED_WALK_DOCUMENT)
        case.reply("Recorded.")
        check_reminded(case_name, case.run())
    for case_name, minutes in (
            ("minutes naming one item of a grouped heading find that item",
             "#next_to_present item 11 of 12."),
            ("minutes naming a grouped item without a total find that item",
             "#next_to_present item 10.")):
        case = Case()
        case.walk_files(minutes=minutes, document=GROUPED_WALK_DOCUMENT)
        case.reply("Recorded.")
        check_reminded(case_name, case.run())
    case = Case()
    case.walk_files(minutes="#next_to_present item 11 of 12.",
                    document=GROUPED_WALK_DOCUMENT.replace(
                        "## Item 12 of 12: after\n\nAfter.",
                        "## Item 12 of 12: after\n\n**Item 11 of 12: misplaced.** Text.\n\nAfter."))
    case.reply("Recorded.")
    check_blocked("a bold paragraph naming an item its heading does not name still starts an item",
                  case.run(), "more than one heading for `Item 11 of 12`")
    for case_name, minutes in (
            ("minutes naming an item kept beside its revision find only the revision",
             "#next_to_present item 27 of 72."),
            ("minutes naming a revised item without a total find only the revision",
             "#next_to_present item 27.")):
        case = Case()
        case.walk_files(minutes=minutes, document=REVISED_WALK_DOCUMENT)
        case.reply("Recorded.")
        check_reminded(case_name, case.run())
    case = Case()
    case.walk_files(minutes="#next_to_present item 26 of 72.", document=REVISED_WALK_DOCUMENT)
    case.reply("Recorded.")
    check_reminded("an item before a kept original still ends at the original", case.run())
    case = Case()
    case.walk_files(minutes="#next_to_present item 10 of 13.",
                    document=GROUPED_WALK_DOCUMENT.replace(
                        "**Item 11 of 12: drop", "**Item 10 of 13: another count.** Text.\n\n**Item 11 of 12: drop"))
    case.reply("Recorded.")
    check_reminded("a bold paragraph with another total under a grouped heading starts its own item", case.run())
    case = Case()
    case.walk_files(minutes="#next_to_present item 27 of 72.",
                    document=REVISED_WALK_DOCUMENT.replace("## Item 27 of 72 (revised)", "## Item 27 of 76 (revised)"))
    case.reply("Recorded.")
    check_reminded("a revision under another total leaves the original in force", case.run())
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
                  "more than one heading for `Item 27 of 72`")
    case = Case()
    case.walk_files(minutes="#next_to_present item 27 of 72.",
                    document=REVISED_WALK_DOCUMENT.replace("## Item 27 of 72 (revised): keeping code and design in step",
                                                           "## Item 27 of 72: what the revised rule changes"))
    case.reply("Recorded.")
    check_blocked("`revised` elsewhere in a heading's title does not make it a revision", case.run(),
                  "more than one heading for `Item 27 of 72`")
    case = Case()
    case.walk_files(minutes="#next_to_present item 27 of 72.",
                    document=REVISED_WALK_DOCUMENT.replace("## Item 27 of 72 (revised): keeping",
                                                           "## Item 27 of 72, revised: keeping"))
    case.reply("Recorded.")
    check_reminded("a heading saying `, revised:` after its count is a revision", case.run())
    partial = ("# A walk\n\n## Items 5 and 6 of 9: two\n\nBoth. Recommendation: Y.\n\n"
               "## Item 5 of 9 (revised): five again\n\nFive. Recommendation: Y.\n")
    case = Case()
    case.walk_files(minutes="#next_to_present item 6 of 9.", document=partial)
    case.reply("Recorded.")
    check_reminded("a revision of one item of a grouped heading leaves the group in force for the other item", case.run())
    case = Case()
    case.walk_files(minutes="#next_to_present item 5 of 9.", document=partial)
    case.reply("Recorded.")
    check_blocked("a revision of one item of a grouped heading leaves that item under two headings",
                  case.run(), "more than one heading for `Item 5 of 9`")
    case = Case()
    case.walk_files(minutes="#next_to_present item 27 of 72.",
                    document=REVISED_WALK_DOCUMENT.replace("## Item 27 of 72 (revised): keeping",
                                                           "## **Item 27 of 72** (revised): keeping"))
    case.reply("Recorded.")
    check_reminded("a heading whose bold closes before `(revised)` is a revision", case.run())
    for case_name, document in (
            ("minutes naming a grouped item whose paragraph is not bold find the group",
             "# A walk\n\n## Items 5 and 6 of 9: two\n\n**Item 5 of 9: five.** Five.\n\n"
             "Item 6 of 9: six. Six.\n\n## Item 7 of 9: seven\n\nSeven.\n"),
            ("minutes naming a grouped item with no paragraph of its own find the group",
             "# A walk\n\n## Items 5 and 6 of 9: two\n\n**Item 5 of 9: five.** Five.\n\n"
             "Both together. Recommendation: Y.\n\n## Item 7 of 9: seven\n\nSeven.\n")):
        case = Case()
        case.walk_files(minutes="#next_to_present item 6 of 9.", document=document)
        case.reply("Recorded.")
        check_reminded(case_name, case.run())
    case = Case()
    case.walk_files(minutes="#next_to_present item 10 of 54.",
                    document=("# A walk\n\n## Item 9 of 54: nine\n\nNine.\n\n"
                              "**Items 12 to 10 of 54: backwards.** Bad text.\n\n## Item 11 of 54: eleven\n\nEleven.\n"))
    case.reply("Recorded.")
    check_blocked("a bold count that names no item under a heading is its own start and named in the block",
                  case.run(), "Items 12 to 10 of 54: backwards.** Bad text.` names no item: its range `12 to 10` runs backwards")
    case.walk_files(minutes="#next_to_present item 9 of 54.",
                    document=("# A walk\n\n## Item 9 of 54: nine\n\nNine.\n\n"
                              "**Items 12 to 10 of 54: backwards.** Bad text.\n\n## Item 11 of 54: eleven\n\nEleven.\n"))
    check_reminded("a bold count that names no item still ends the item before it", case.run())


def test_where_the_minutes_line_sits():
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
        check_reminded(case_name, case.run())
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
    check_reminded("only the heading with the minutes' total is checked", case.run())


def test_unparseable_line():
    case = Case()
    case.walk_files(minutes="#next_to_present the poem question.")
    case.reply(ITEM_2_REPLY)
    check_blocked("a #next_to_present line naming no item is sent back to be corrected",
                  case.run(), "could not be checked", "the poem question",
                  "Then name in your reply the items the line names")


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
    check_reminded("a reopened walk's last line counts", case.run())


def test_minutes_without_line_are_not_open():
    case = Case()
    case.walk_files(minutes="## Item 1 of 9 — Y")
    case.reply("Anything at all.")
    check_silent("minutes without a #next_to_present line are not an open walk", case.run())


def test_old_marker_is_migrated():
    case = Case()
    minutes = case.walk_files(minutes="Next to present: item 2 of 9.")
    case.reply("Recorded.")
    result = case.run()
    check_blocked("an open walk marked only with the old form is told the line to add", result,
                  "is the old form `Next to present:`", f"at the end of {minutes}",
                  "leave the old lines as they are: #next_to_present item 2 of 9\n",
                  "Then name in your reply the items the new line names")
    check("the old form's block shows no item", "where the poem page lives" not in result.stdout,
          result.stdout)
    case = Case()
    case.walk_files(minutes="#next_to_present item 9 of 9.\n\nNext to present: item 2 of 9.")
    case.reply("Recorded.")
    check_blocked("a hashtag walk whose newest marker is the old form is told the line to add", case.run(),
                  "leave the old lines as they are: #next_to_present item 2 of 9\n")
    case = Case()
    case.walk_files(minutes="#next_to_present item 2 of 9\n\nNext to present: item 5 of 9.")
    case.reply("Recorded.")
    check_blocked("an old-form line below a hashtag line is the newest marker and is migrated",
                  case.run(), "#next_to_present item 5 of 9")
    case = Case()
    case.walk_files(minutes="Next to present: item 5 of 9.\n\n#next_to_present item 2 of 9")
    case.reply("Recorded.")
    check_reminded("a hashtag line below an old-form line counts", case.run())
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
    check_reminded("the most recently modified open walk's item is the one checked", case.run())


def test_silent_cases():
    case = Case()
    case.walk_files(minutes="#next_to_present item 2 of 9.")
    case.reply("No item here.")
    check_silent("while the agent answers a Stop hook, a reply leaving out the item is not sent back",
                 case.run(stop_hook_active=True))
    unusable = Case()
    unusable.walk_files(minutes="#next_to_present item 12 to 10 of 9.")
    unusable.reply("No item here.")
    check_blocked("unusable minutes block when the agent is not answering a Stop hook", unusable.run())
    check_silent("while the agent answers a Stop hook, a block on unusable minutes is not printed",
                 unusable.run(stop_hook_active=True))
    check_silent("a headless child is not checked",
                 case.run(environment_extra={"CLAUDE_CODE_SESSION_ATTENDED": "0"}))
    case.reply(None)
    check_silent("a turn that wrote nothing to the user is not checked", case.run())
    without_walk = Case(with_walk_directory=False)
    without_walk.reply("No item here.")
    check_silent("a checkout without docs/walk is not checked", without_walk.run())
    outside = Case(in_git=False)
    outside.reply("No item here.")
    check_silent("a cwd outside any checkout is not checked", outside.run())


def test_nothing_is_read_or_installed_while_the_agent_answers_a_stop_hook():
    case = Case()
    case.walk_files(minutes="#next_to_present item 2 of 9.")
    case.reply("No item here.")
    shadow = case.root / "shadow"
    (shadow / "markdown_it").mkdir(parents=True)
    (shadow / "markdown_it" / "__init__.py").write_text(
        'raise ImportError("markdown-it-py hidden by this case")\n')
    home = case.root / "home"
    home.mkdir()
    result = case.run(stop_hook_active=True,
                      environment_extra={"PYTHONPATH": str(shadow), "PYTHONDONTWRITEBYTECODE": "1",
                                         # A hook that wrongly installs writes its install state here.
                                         "HOME": str(home)})
    check("while the agent answers a Stop hook, the hook stops before loading the parser or writing state",
          result.returncode == 0 and result.stdout == "" and result.stderr == ""
          and not any(home.iterdir()),
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
    case = Case()
    case.walk_files(minutes="#next_to_present item 2 of 9.")
    case.transcript.write_bytes(b'{"type": "user", "message": {"content": "\xff\xfe"}}\n')
    result = case.run()
    check("a transcript that cannot be read exits 1 and names the fault on stderr",
          result.returncode == 1 and "UnicodeDecodeError" in result.stderr and result.stdout == "",
          f"exit {result.returncode}, stderr {result.stderr!r}")
    case = Case()
    case.walk_files(minutes="#next_to_present none, closed.")
    case.transcript.write_bytes(b'{"type": "user", "message": {"content": "\xff\xfe"}}\n')
    result = case.run()
    check("with no open walk, the transcript is not read, so a transcript that cannot be read is no fault",
          result.returncode == 0 and result.stdout == "" and result.stderr == "",
          f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")


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
