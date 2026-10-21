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
"Recorded.", and it still names the item. It is checked only when it holds
text.

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
import re
import sys
from pathlib import Path

REPOSITORY_TOP = Path(__file__).resolve().parents[3]
SUITE_RUNNER_FILE = REPOSITORY_TOP / "scripts" / "run-all-test-suites.py"
GIT_MODULE_FILE = (REPOSITORY_TOP / "nc-systems" / "general-tools"
                   / "git-machine-readable-output-runner-and-parser-common.py")
STOP_HOOKS_STAY_SILENT_RULE_FILE = (
    REPOSITORY_TOP / "nc-systems" / "general-tools"
    / "claude-code-stop-hooks-stay-silent-while-agent-answers-a-stop-hook-rule-common.py")
MARKDOWN_PARSER_MODULE_FILE = (REPOSITORY_TOP / "nc-systems" / "general-tools"
                               / "markdown-commonmark-parser-install-if-missing-common.py")
CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`).+?(?<!`)\1(?!`)")
WALK_DIRECTORY = Path("docs") / "walk"
MINUTES_SUFFIX = "-minutes.md"
# Group 1 is set only for the hashtag; the old form is read so that open walks it marks are migrated.
# The value runs to the line's end or the next marker, so two markers on a line are read as two.
NEXT_MARKER = re.compile(
    r"(?:(#next_to_present)\b|Next to present:)[*_`\s:]*((?:(?!#next_to_present\b|Next to present:)[^\n])*)",
    re.I)
CLOSED_VALUE = re.compile(r"^(?:none|closed)\b", re.I)
NUMBER = r"\d+(?:\.\d+)*"
NUMBER_JOINER = r"\s*(?:,|&|\band\b|\bto\b|-|\u2013)\s*"
# A running count: `item 2`, `item 4.1`, `items 5 and 6`, `items 5, 6 and 7`, `items 10 to 12`, `items 10-12`.
NUMBER_LIST = rf"{NUMBER}(?:{NUMBER_JOINER}{NUMBER})*(?![\d.]\d)"
VALUE_COUNT = re.compile(rf"^items?\s+({NUMBER_LIST})(?:\s+of\s+(\d+)\b)?", re.I)
HEADING_COUNT = re.compile(rf"^[*_\s]*items?\s+({NUMBER_LIST})\s+of\s+(\d+)\b", re.I)
REPLY_COUNT = re.compile(rf"\bitems?\s+({NUMBER_LIST})\s+of\s+(\d+)\b", re.I)
# Only right after the count, as in `(revised)` or `, revised:`, so a title that uses the word drops nothing.
REVISED = re.compile(r"^[*_\s(,:;.\-\u2013\u2014]*revised\b", re.I)
NUMBER_OR_JOINER = re.compile(rf"{NUMBER}|\bto\b|-|\u2013", re.I)
# A record from one of these starts a turn even when Claude Code marks it isMeta.
TURN_STARTING_ORIGIN_KINDS = ("human", "peer", "coordinator", "task-notification")
USER_TURN_ORIGIN = "human"

UNUSABLE_OPENING_TEMPLATE = (
    "approval-walk current-item check: the open approval-walk {walk} could not "
    "be checked: {problem}"
)
NOT_A_FORM_PROBLEM = (
    "does not open with an item in one of the forms `item N of M`, `item N.K of M`, "
    "`items N and P of M` or `items N to P of M`")


class UnusableRange(ValueError):
    """A running count names no item; its argument says why."""


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
    "If his answer moved the approval-walk on, first set the `#next_to_present` line in "
    "{minutes} to the items now waiting, then name those.",
    "If he ended or abandoned the approval-walk, add the line `#next_to_present none, closed` "
    "at the end of {minutes} instead of naming the item, and end the turn.",
)
OLD_MARKER_INSTRUCTIONS = (
    "Add this line at the end of {minutes}, below every earlier marker line, and leave "
    "the old lines as they are: {new_line}",
    "Then name in your reply the items the new line names, showing them in full if the user has "
    "not yet seen them, and end the turn.",
)


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def transcript_records(transcript_path):
    records = []
    with open(transcript_path, encoding="utf-8") as transcript:
        for line in transcript:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict):
                records.append(record)
    return records


def turn_start(records):
    """Return the index of the record that starts the transcript's last turn, or None."""
    for index in range(len(records) - 1, -1, -1):
        record = records[index]
        # A compaction's summary is a user record without isMeta, but Claude Code writes it, not
        # a prompt, so it opens no turn.
        if record.get("type") != "user" or record.get("isCompactSummary"):
            continue
        content = record.get("message", {}).get("content")
        if (isinstance(content, list) and content
                and all(isinstance(block, dict) and block.get("type") == "tool_result"
                        for block in content)):
            continue
        origin_kind = (record.get("origin") or {}).get("kind")
        if record.get("isMeta") and origin_kind not in TURN_STARTING_ORIGIN_KINDS:
            continue
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


def checkout_top(directory):
    """Return the top of directory's checkout, or None outside one."""
    runner = load_module("run_all_test_suites", SUITE_RUNNER_FILE)
    git = load_module("git_machine_readable_output_runner_and_parser_common", GIT_MODULE_FILE)
    environment = {name: value for name, value in os.environ.items()
                   if name not in runner.GIT_REDIRECTING_ENVIRONMENT_VARIABLES}
    output = git.run_git_unless_outside_a_repository(
        directory, ["rev-parse", "--show-toplevel"], environment=environment)
    if output is None:
        return None
    return Path(os.fsdecode(output).rstrip("\n"))


def markdown_parser():
    return load_module("markdown_commonmark_parser_install_if_missing_common",
                       MARKDOWN_PARSER_MODULE_FILE).markdown_parser()


def code_line_numbers(tokens):
    lines = set()
    for token in tokens:
        if token.map is not None and token.type in ("fence", "code_block"):
            lines.update(range(*token.map))
    return lines


def next_to_present(minutes_text, parser):
    """Return (value, whether the marker is the old form) for the minutes' last marker outside code, or None."""
    code_lines = code_line_numbers(parser.parse(minutes_text))
    markers = []
    for number, line in enumerate(minutes_text.split("\n")):
        if number in code_lines:
            continue
        spans = [span.span() for span in CODE_SPAN.finditer(line)]
        for marker in NEXT_MARKER.finditer(line):
            if not any(start <= marker.start() < end for start, end in spans):
                markers.append((marker[1], marker[2].replace("`", "").strip()))
    if not markers:
        return None
    hashtag, value = markers[-1]
    return value, not hashtag


def is_closed(value):
    return bool(CLOSED_VALUE.match(value))


def expand_numbers(number_list):
    """Return the item numbers a list such as `5, 6 and 7` or `10 to 12` names.

    Raise UnusableRange, saying what is wrong, for a range that runs backwards, one whose
    ends belong to different items, or a joiner such as `to` with no range around it.
    """
    pieces = NUMBER_OR_JOINER.findall(number_list)
    numbers, index = [], 0
    while index < len(pieces):
        if index + 2 < len(pieces) and pieces[index + 1].lower() in ("to", "-", "\u2013"):
            first, last = pieces[index], pieces[index + 2]
            first_head, _, first_tail = first.rpartition(".")
            last_head, _, last_tail = last.rpartition(".")
            if not first_head and last_head == first:
                # `12 to 12.3`: item 12 and its parts up to 12.3.
                numbers += [first] + [f"{first}.{n}" for n in range(1, int(last_tail) + 1)]
                index += 3
                continue
            if first_head != last_head:
                raise UnusableRange(
                    f"its range `{first} to {last}` runs between parts of different items; "
                    f"a range runs within one item's parts, such as `items 12.1 to 12.3`, "
                    f"between whole items, such as `items 10 to 12`, or from an item to "
                    f"one of its parts, such as `items 12 to 12.3`")
            if int(first_tail) > int(last_tail):
                raise UnusableRange(
                    f"its range `{first} to {last}` runs backwards; a range runs from the "
                    f"lower number to the higher, such as `items {last} to {first}`")
            prefix = first_head + "." if first_head else ""
            numbers += [prefix + str(n) for n in range(int(first_tail), int(last_tail) + 1)]
            index += 3
        elif pieces[index].lower() in ("to", "-", "\u2013"):
            raise UnusableRange(NOT_A_FORM_PROBLEM)
        else:
            numbers.append(pieces[index])
            index += 1
    return numbers


def parse_items(value):
    """Return (item numbers, M or None) from a value such as `items 10 to 12 of 54.`.

    Raise UnusableRange, saying what is wrong, when the value names no item that way.
    """
    match = VALUE_COUNT.match(value)
    if not match:
        raise UnusableRange(NOT_A_FORM_PROBLEM)
    return expand_numbers(match[1]), match[2]


def open_walk(walk_directory, parser):
    """Return (minutes path, value, whether the marker is the old form) for the open approval-walk, or None."""
    candidates = []
    for minutes in walk_directory.glob("*" + MINUTES_SUFFIX):
        marker = next_to_present(minutes.read_text(encoding="utf-8"), parser)
        if marker is None or is_closed(marker[0]):
            continue
        candidates.append((minutes.stat().st_mtime, minutes, marker))
    if not candidates:
        return None
    _, minutes, (value, old_form) = max(candidates, key=lambda candidate: candidate[0])
    return minutes, value, old_form


def item_units(document_text, parser):
    """Return [(item numbers, M, problem)] for each running count that starts an item.

    A count starts an item on a heading, or on a paragraph opening with `**`, except a
    paragraph whose items the count heading above it already names, with no other count
    between them, which stays in that heading's unit. A count that names no item still
    ends the unit before it; its unit has no numbers, and problem names the heading and
    says why. problem is None for every other unit. A unit is left out when a later
    heading that says `revised` right after its count names all of its items.
    """
    lines = document_text.split("\n")
    starts = []
    group = None
    tokens = parser.parse(document_text)
    for index, token in enumerate(tokens):
        if token.map is None or token.type not in ("heading_open", "paragraph_open"):
            continue
        if token.type == "paragraph_open" and not lines[token.map[0]].lstrip().startswith("**"):
            continue
        content = tokens[index + 1].content.split("\n")[0] if index + 1 < len(tokens) else ""
        match = HEADING_COUNT.match(content)
        if not match:
            continue
        try:
            numbers, problem = expand_numbers(match[1]), None
        except UnusableRange as error:
            numbers, problem = [], f"its walk-document's heading `{content.strip()}` names no item: {error}"
        if token.type == "heading_open":
            group = (set(numbers), match[2])
        elif group and numbers and set(numbers) <= group[0] and match[2] == group[1]:
            continue
        else:
            group = None
        revised = bool(REVISED.match(content[match.end():]))
        starts.append((numbers, match[2], problem, revised))
    return [(numbers, total, problem) for index, (numbers, total, problem, _) in enumerate(starts)
            if not (numbers and any(revised and later_total == total and set(numbers) <= set(later_numbers)
                                    for later_numbers, later_total, _, revised in starts[index + 1:]))]


def items_named_in(reply, total):
    """Return the item numbers the reply's running counts with total M name."""
    named = set()
    for match in REPLY_COUNT.finditer(reply):
        if match[2] != total:
            continue
        try:
            named.update(expand_numbers(match[1]))
        except UnusableRange:
            continue
    return named


def block_output(opening, instructions, **values):
    lines = [opening.format(**values)] + [line.format(**values) for line in instructions]
    return json.dumps({"decision": "block", "reason": "\n".join(lines)}, ensure_ascii=False)


def run(stdin_text, environment):
    """Return the text to print, or None."""
    payload = json.loads(stdin_text)
    rule = load_module("claude_code_stop_hooks_stay_silent_while_agent_answers_a_stop_hook_rule_common",
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
    top = checkout_top(Path(payload["cwd"]))
    if top is None or not (top / WALK_DIRECTORY).is_dir():
        return None
    parser = markdown_parser()
    walk = open_walk(top / WALK_DIRECTORY, parser)
    if walk is None:
        return None
    records = transcript_records(Path(transcript_path).expanduser())
    reply = turn_reply_text(records)
    if not turn_answers_user(records) or not reply.strip():
        return None
    minutes, value, old_form = walk
    name = minutes.name[:-len(MINUTES_SUFFIX)]
    document = minutes.with_name(name + ".md")
    values = {"walk": name, "minutes": minutes, "document": document, "value": value}

    def block(opening, instructions, **more):
        return block_output(opening, instructions, **more, **values)

    if old_form:
        new_line = "#next_to_present " + value.rstrip(". ")
        return block(UNUSABLE_OPENING_TEMPLATE, OLD_MARKER_INSTRUCTIONS,
                     problem=OLD_MARKER_PROBLEM.format(minutes=minutes), new_line=new_line)
    try:
        numbers, total = parse_items(value)
    except UnusableRange as problem:
        return block(UNUSABLE_OPENING_TEMPLATE, UNUSABLE_INSTRUCTIONS, problem=(
            f"its minutes' last `#next_to_present` line, `{value}`, {problem}."))
    if not document.is_file():
        return block(UNUSABLE_OPENING_TEMPLATE, UNUSABLE_INSTRUCTIONS, problem=(
            f"its walk-document {document} does not exist."))
    all_units = item_units(document.read_text(encoding="utf-8"), parser)
    if total is None:
        totals = {unit[1] for unit in all_units}
        if not totals:
            return block(UNUSABLE_OPENING_TEMPLATE, UNUSABLE_INSTRUCTIONS, problem=(
                f"its walk-document {document} has no heading with a running count, such "
                f"as `## Item 3 of 9: <the point>`, so the hook cannot find the item the "
                f"minutes name: give each item's heading its count `Item N of M`."))
        if len(totals) > 1:
            listed = ", ".join(f"`of {each}`" for each in sorted(totals, key=int))
            return block(UNUSABLE_OPENING_TEMPLATE, UNUSABLE_INSTRUCTIONS, problem=(
                f"its minutes' last `#next_to_present` line, `{value}`, gives no `of M`, "
                f"and the walk-document's headings give more than one total ({listed}), "
                f"so the line must say which: write it as `item N of M`, with M the total "
                f"of the heading meant."))
        total = totals.pop()
    units = [unit for unit in all_units if unit[1] == total and set(unit[0]) & set(numbers)]
    missing = [number for number in numbers if not any(number in unit[0] for unit in units)]
    if missing:
        named = ", ".join(f"`Item {number} of {total}`" for number in missing)
        unreadable = [unit[2] for unit in all_units if unit[1] == total and unit[2]]
        return block(UNUSABLE_OPENING_TEMPLATE, UNUSABLE_INSTRUCTIONS, problem=(
            f"its walk-document has no heading {named}, which the minutes name"
            + "".join(f"; {each}" for each in unreadable) + "."))
    repeated = [number for number in numbers if sum(number in unit[0] for unit in units) > 1]
    if repeated:
        named = ", ".join(f"`Item {number} of {total}`" for number in repeated)
        return block(UNUSABLE_OPENING_TEMPLATE, UNUSABLE_INSTRUCTIONS, problem=(
            f"its walk-document has more than one heading for {named}, so the hook cannot tell "
            f"which one the minutes name."))
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
