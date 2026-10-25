#!/usr/bin/env python3
"""Stop hook: while an approval-walk is open, block the agent's stop when its
reply to the user does not name the item waiting for his answer.

Wired as a Stop hook in .claude/settings.json. The agent shows each item in
full in its own message; a hook notice showing the item again was printed by
the Claude Mac app as one "Stop says:" line per line of text, which the user
took for a broken hook. A reply that names the waiting item by its running
count, `Item N of M`, anywhere in its text passes: the item shown in full
opens with its count, and any other reply can end with a line such as
"Item 4 of 9 is waiting for your answer." A turn that wrote nothing to the
user, such as a silent turn after a background-task notice, is not checked.

ONLY A TURN THAT ANSWERS THE USER is checked or blocks: a turn started by
his own prompt, typed, queued or a slash command. A turn started by another
agent-seat's message, a background-task notice, a coordinator's message or a
scheduled prompt shows and blocks nothing, so a walk left open while the agent
does other work is not sent back over every report, and the minutes,
which change only when he answers, are not checked then. Claude Code records
on each turn's opening prompt a `turnOrigin`, `human` for his own; the last
user record carrying one names the current turn's origin, because a message
that arrives while the agent works carries none. A prompt he types while the
agent works on a turn something else started is delivered into that turn as
an `attachment` of type `queued_command` whose origin kind is `human`; the
agent answers him in that turn, so it answers the user too. A transcript with
no `turnOrigin`, from a Claude Code that did not write it, is read by the
turn's start below: its `origin` kind is `human`, or it has none.

THE TURN starts at the last user-type record in the transcript that is
neither only tool results nor an injection inside the turn: the user's
message, another agent-seat's message, a parent's message to its subagent,
a background-task notice, or a local command. An injection is a record
marked isMeta with no such origin, such as a loaded skill's text or a system
reminder. Claude Code marks another agent-seat's message isMeta too, so the
origin decides first.

THE REPLY is the text of every assistant message after the turn's start, or
after the last prompt the user typed into the turn, if that comes later: a
turn may show the item, make tool calls, and end with a short line such as
"Recorded.", and it still names the item. The reply also holds the payload's
`last_assistant_message`, the turn's final message, because Claude Code can
start the Stop hook before it has written that message to the transcript. It
is checked only when it holds text.

THE OPEN APPROVAL-WALK. The walk-me-through skill keeps a `#next_to_present`
line in each walk's docs/walk/<name>-minutes.md; agents write it at a line's
start, in a bullet, or mid-sentence, so the marker is found anywhere outside
code, and the last one in a minutes file counts, also when two share a line.
A marker inside a code span is a quotation, not a marker; a value inside one,
as in ``#next_to_present `item 3 of 9` ``, is read without its backticks, and a
colon after the hashtag, `#next_to_present: none`, is read as the old form's
colon was. Minutes written before the
hashtag carry the old marker `Next to present:`; the last marker of either
form counts, and when it is the old form on a walk that is not closed, the
hook blocks with the line to add instead of checking the reply. Its value is `none` or
`closed` for a closed walk, or opens with a running count, `item N`,
`item 4.1`, `items 5 and 6`, `items 10 to 12`, with or without `of M`, and
anything after the count, such as `(awaiting answer), then item 24`, is
ignored. Among the minutes files in docs/walk/ at the top of the checkout
named by the payload's cwd, the open approval-walk is the most recently
modified one whose value is not closed. Minutes with no such line, as every
walk before the line existed, are not open walks.

ITEMS IN THE WALK-DOCUMENT. An item starts at its running count, `Item N of
M`, `Items 5 and 6 of M`, `Items 10 to 12 of M` or `Items 12 to 12.3 of M`
(item 12 and its parts 12.1 to 12.3), on a heading or on a paragraph opening
with `**`, as markdown-it-py reads the document, so a count inside code starts
nothing; it runs to the next running count, so headings inside an item, such
as an original and a proposed section, stay in it. A heading that names
several items is one unit, and so are the paragraphs under it that open with
the count of one of its items, such as `**Item 10 of 12: ...**` under `##
Items 10 and 11 of 12`. A heading that keeps an earlier item beside its
revision says `revised` after its count, as in `## Item 27 of 72 (revised)`;
only the latest revision counts. A running count that names no item, such
as a range that runs backwards, still ends the item before it; when the
minutes name an item such a heading was meant to hold, or name an item that
two headings carry when neither is a revision, the hook blocks naming the
heading. When the minutes' value has no `of M`, the walk-document's own total
is used, if its headings carry only one.

THE REPLY NAMES AN ITEM when it holds a running count with the walk's
total that covers it, in any of the forms above: `Item 11 of 12`, or
`Items 10 and 11 of 12` for both. A count with another total, such as `item
2 of 90` for item 2 of 9, names nothing.

SILENT while the agent answers a Stop hook (stop_hook_active set), as the
Stop-hook silence rule's module requires, when the agent-session is a
headless `claude -p` child (its last words are its caller's answer), when the
transcript is missing, when the turn wrote no text to the user, when the cwd is
not in a git checkout, when no approval-walk is open, and when the reply
names every item the minutes name.

OUTPUT: {"decision": "block", "reason": <message>}, which keeps the agent
going with the message as its next instruction: when the reply leaves out a
waiting item, or when the open walk's minutes line or walk-document cannot be
used, so the waiting item is unknown. ON A
FAULT, such as input that is not JSON or a file it cannot read, the hook
prints one line naming it on stderr and exits 1: Claude Code records a Stop
hook's exit 1 as a non-blocking error and still ends the turn.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

WALK_FINDER_FILE = (Path(__file__).resolve().parent
                    / "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py")
_walk_finder_spec = importlib.util.spec_from_file_location(
    "walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common", WALK_FINDER_FILE)
walk_finder = importlib.util.module_from_spec(_walk_finder_spec)
_walk_finder_spec.loader.exec_module(walk_finder)
STOP_HOOKS_STAY_SILENT_RULE_FILE = (
    walk_finder.REPOSITORY_TOP / "nc-systems" / "general-tools"
    / "claude-code-stop-hooks-stay-silent-while-agent-answers-a-stop-hook-rule-common.py")
TRANSCRIPT_READER_FILE = (walk_finder.REPOSITORY_TOP / "scripts"
                          / "claude-code-session-transcript-records-read-backward-common.py")
# A record from one of these starts a turn even when Claude Code marks it isMeta.
TURN_STARTING_ORIGIN_KINDS = ("human", "peer", "coordinator", "task-notification")
USER_TURN_ORIGIN = "human"

UNUSABLE_OPENING_TEMPLATE = (
    "approval-walk current-item check: the open approval-walk {walk} could not "
    "be checked: {problem}"
)
UNUSABLE_INSTRUCTIONS = (
    "If the approval-walk has closed, add the line `#next_to_present none, closed` "
    "at the end of {minutes} and end the turn.",
    "Otherwise, add a line at the end of {minutes} that names the items the user has "
    "yet to answer by their headings in the walk-document {document}, as "
    "`#next_to_present item 3 of 9`, `item 4.1 of 9`, `items 5 and 6 of 9` or `items 10 to 12 of 54`; "
    "change a heading in the walk-document only when the heading itself is misnumbered or "
    "lacks its running count `of M`.",
    "Then name in your reply the items the line names, showing them in full if the user has not "
    "yet seen them, and end the turn.",
)
OLD_MARKER_PROBLEM = (
    "the newest marker line in its minutes {minutes} is the old form `Next to present:`, "
    "and the hook reads the current item only from a `#next_to_present` line.")
REPLY_LEAVES_OUT_OPENING_TEMPLATE = (
    "approval-walk current-item check: your reply to the user does not name {named}, which "
    "the open approval-walk {walk} has waiting for his answer, so he cannot tell which item "
    "his next answer goes to.")
REPLY_LEAVES_OUT_INSTRUCTIONS = (
    "If he has not yet seen the item, or asked to see it again, show it in full, word for word "
    "as the walk-document {document} has it, starting with its running count, as in "
    "`Item 4 of 9: <the point>`.",
    "Otherwise, end your reply with one line naming it, as in `{example} {verb} waiting for "
    "your answer.`",
    "If his answer moved the approval-walk on, first run `python3 nc-systems/skills/walk-me-through/"
    "walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py check`, adding the "
    "flag --help lists for his answer, if it lists one; when check passes, run the close command "
    "it prints. Together they set the `#next_to_present` line in {minutes} to the item now "
    "waiting, so do not set that line by hand; then name the item now waiting. When check fails, "
    "do what it printed instead.",
    "If he ended or abandoned the approval-walk, add the line `#next_to_present none, closed` "
    "at the end of {minutes} instead of naming the item, and end the turn.",
)
OLD_MARKER_INSTRUCTIONS = (
    "Add this line at the end of {minutes}, below every earlier marker line, and leave "
    "the old lines as they are: {new_line}",
    "Then name in your reply the items the new line names, showing them in full if the user has "
    "not yet seen them, and end the turn.",
)


def transcript_records(transcript_path):
    """The records from the newest one that opens a turn, and the newest one holding a
    `turnOrigin`, to the transcript's end: all that turn_reply_text and turn_answers_user read."""
    reader = walk_finder.load_module("claude_code_session_transcript_records_read_backward_common",
                         TRANSCRIPT_READER_FILE)
    return reader.records_from_newest_boundary_to_end(transcript_path, is_turn_start, lambda record: "turnOrigin" in record)


def is_turn_start(record):
    # A compaction's summary is a user record without isMeta, but Claude Code writes it, not
    # a prompt, so it opens no turn.
    if record.get("type") != "user" or record.get("isCompactSummary"):
        return False
    content = record.get("message", {}).get("content")
    if (isinstance(content, list) and content
            and all(isinstance(block, dict) and block.get("type") == "tool_result"
                    for block in content)):
        return False
    origin_kind = (record.get("origin") or {}).get("kind")
    return not (record.get("isMeta") and origin_kind not in TURN_STARTING_ORIGIN_KINDS)


def turn_start(records):
    """Return the index of the record that starts the transcript's last turn, or None."""
    for index in range(len(records) - 1, -1, -1):
        if is_turn_start(records[index]):
            return index
    return None


def typed_while_working(record):
    """Whether the record is a prompt of the user's delivered into a running turn.

    Of the attachments Claude Code writes, only a delivered prompt, a `queued_command`, carries an origin.
    """
    attachment = record.get("attachment")
    return isinstance(attachment, dict) and (attachment.get("origin") or {}).get("kind") == USER_TURN_ORIGIN


def turn_answers_user(records):
    """Whether the transcript's last turn was started by the user's own prompt, or took one while it ran."""
    for index in range(len(records) - 1, -1, -1):
        if "turnOrigin" in records[index]:
            opened_by_user = records[index]["turnOrigin"] == USER_TURN_ORIGIN
            break
    else:
        index = turn_start(records)
        if index is None:
            return any(typed_while_working(record) for record in records)
        origin = records[index].get("origin")
        opened_by_user = origin is None or origin.get("kind") == USER_TURN_ORIGIN
    return opened_by_user or any(typed_while_working(record) for record in records[index + 1:])


def turn_reply_text(records):
    """Return the text of every assistant message since the last turn's start, or since the
    last prompt the user typed into that turn, if later."""
    start = turn_start(records)
    start = 0 if start is None else start + 1
    for index in range(len(records) - 1, start - 1, -1):
        if typed_while_working(records[index]):
            start = index + 1
            break
    texts = []
    for record in records[start:]:
        if record.get("type") != "assistant":
            continue
        message = record.get("message", {})
        content = message.get("content")
        if not isinstance(content, list):
            continue
        texts.extend(block.get("text", "") for block in content
                     if isinstance(block, dict) and block.get("type") == "text")
    return "\n".join(texts)


def items_named_in(reply, total):
    """Return the item numbers the reply's running counts with total M name."""
    named = set()
    for match in walk_finder.REPLY_COUNT.finditer(reply):
        if match[2] != total:
            continue
        try:
            named.update(walk_finder.expand_numbers(match[1]))
        except walk_finder.UnusableRange:
            continue
    return named


def block_output(opening, instructions, **values):
    lines = [opening.format(**values)] + [line.format(**values) for line in instructions]
    return json.dumps({"decision": "block", "reason": "\n".join(lines)}, ensure_ascii=False)


def run(stdin_text, environment):
    """Return the text to print, or None."""
    payload = json.loads(stdin_text)
    rule = walk_finder.load_module("claude_code_stop_hooks_stay_silent_while_agent_answers_a_stop_hook_rule_common",
                       STOP_HOOKS_STAY_SILENT_RULE_FILE)
    if rule.stop_hook_stays_silent_while_agent_answers_a_stop_hook(payload):
        return None
    return output_for(payload, environment)


def output_for(payload, environment):
    """A block naming the waiting items the reply leaves out, or why they are unknown; or None."""
    if (environment.get("NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER")
            or environment.get("CLAUDE_CODE_SESSION_ATTENDED") == "0"):
        return None
    transcript_path = payload.get("transcript_path")
    if not transcript_path or not Path(transcript_path).expanduser().is_file():
        return None
    if not payload.get("cwd"):
        return None
    top = walk_finder.checkout_top(Path(payload["cwd"]))
    if top is None or not (top / walk_finder.WALK_DIRECTORY).is_dir():
        return None
    parser = walk_finder.markdown_parser()
    walk = walk_finder.open_walk(top / walk_finder.WALK_DIRECTORY, parser)
    if walk is None:
        return None
    records = transcript_records(Path(transcript_path).expanduser())
    reply = turn_reply_text(records) + "\n" + (payload.get("last_assistant_message") or "")
    if not turn_answers_user(records) or not reply.strip():
        return None
    minutes, value, old_form = walk
    name = minutes.name[:-len(walk_finder.MINUTES_SUFFIX)]
    document = minutes.with_name(name + ".md")
    values = {"walk": name, "minutes": minutes, "document": document, "value": value}

    def block(opening, instructions, **more):
        return block_output(opening, instructions, **more, **values)

    if old_form:
        new_line = "#next_to_present " + value.rstrip(". ")
        return block(UNUSABLE_OPENING_TEMPLATE, OLD_MARKER_INSTRUCTIONS,
                     problem=OLD_MARKER_PROBLEM.format(minutes=minutes), new_line=new_line)
    try:
        numbers, total = walk_finder.parse_items(value)
    except walk_finder.UnusableRange as problem:
        return block(UNUSABLE_OPENING_TEMPLATE, UNUSABLE_INSTRUCTIONS, problem=(
            f"its minutes' last `#next_to_present` line, `{value}`, {problem}."))
    try:
        total, _ = walk_finder.waiting_item_units(document, value, numbers, total, parser)
    except walk_finder.UnusableRange as problem:
        return block(UNUSABLE_OPENING_TEMPLATE, UNUSABLE_INSTRUCTIONS, problem=str(problem))
    named_in_reply = items_named_in(reply, total)
    left_out = [number for number in numbers if number not in named_in_reply]
    if not left_out:
        return None
    example = (f"Item {numbers[0]} of {total}" if len(numbers) == 1
               else f"Items {', '.join(numbers[:-1])} and {numbers[-1]} of {total}")
    return block(REPLY_LEAVES_OUT_OPENING_TEMPLATE, REPLY_LEAVES_OUT_INSTRUCTIONS,
                 named=" and ".join(f"`Item {number} of {total}`" for number in left_out),
                 example=example, verb="is" if len(numbers) == 1 else "are")


def main():
    try:
        output = run(sys.stdin.read(), os.environ)
    except Exception as error:
        print(f"walk-me-through-current-item-shown-to-user-after-each-agent-message-stop-hook: "
              f"the hook failed, so it did not check that the reply names the approval-walk's "
              f"waiting item; the agent need not act: {error!r}", file=sys.stderr)
        return 1
    if output is not None:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
