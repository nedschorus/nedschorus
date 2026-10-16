#!/usr/bin/env python3
"""Stop hook: while an approval-walk is open, show the user the current item
in full after each message the agent writes to him, with the answers he can give.

Wired as a Stop hook in .claude/settings.json. The user answers the item at the
end of what he reads, so the item is shown there by code rather than left to
the agent to repeat. A turn that wrote nothing to the user, such as a silent
turn after a background-task notice, shows nothing.

THE TURN starts at the last user-type record in the transcript that is
neither only tool results nor an injection inside the turn: the user's
message, another agent-seat's message, a parent's message to its subagent,
a background-task notice, or a local command. An injection is a record
marked isMeta with no such origin, such as a loaded skill's text or a system
reminder. Claude Code marks another agent-seat's message isMeta too, so the
origin decides first. The item is shown only when an assistant message after
the turn's start holds text.

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
hook blocks with the line to add instead of showing an item. Its value is `none` or
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
only the latest revision is shown. A running count that names no item, such
as a range that runs backwards, still ends the item before it, so that item is
not shown with the next one's text; when the minutes name an item such a
heading was meant to hold, or name an item that two headings carry when
neither is a revision, the hook blocks naming the heading. When the minutes' value has no `of M`, the walk-document's
own total is used, if its headings carry only one.

WHAT IS SHOWN is the text of the units the minutes name, taken from the
walk-document in the walk-document's order, without heading marks, bold marks
and separator lines, which Claude Code would show as written, followed by
ANSWERS_LINE. Code spans and code blocks are shown as written: a `#` or `**`
there is part of the code. So an
agent that rewords an item edits the walk-document first, or the user is shown
the old text.

WHILE THE AGENT ANSWERS A STOP HOOK (stop_hook_active set), the item notice
is still shown, under the one exemption in the Stop-hook silence rule's module,
because it does not keep the agent going; a block on unusable minutes is not
printed then. The hook then installs nothing, so a missing markdown-it-py is a
fault there, which the Stop before it in the same turn, which installs it, has
already met. SILENT when the agent-session is a headless `claude -p` child (its
last words are its caller's answer), when the transcript is missing, when the
turn's last reply is empty, when the cwd is not in a git checkout, and when no
approval-walk is open.

OUTPUT: {"systemMessage": <the item and ANSWERS_LINE>}, which Claude Code
shows the user and which does not keep the agent going. When the open walk's
minutes line or walk-document cannot be used, there is no item to show, so the
hook prints {"decision": "block", "reason": <message>} instead, which keeps
the agent going with the message as its next instruction. ON A
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
# The hard-wrap hook already installs the pinned markdown-it-py when it is missing; its parser is reused.
MARKDOWN_PARSER_MODULE_FILE = REPOSITORY_TOP / "scripts" / "markdown-edit-hard-wrapped-paragraph-reminder-hook.py"
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
REVISED = re.compile(r"\brevised\b", re.I)
NUMBER_OR_JOINER = re.compile(rf"{NUMBER}|\bto\b|-|\u2013", re.I)
# A record from one of these starts a turn even when Claude Code marks it isMeta.
TURN_STARTING_ORIGIN_KINDS = ("human", "peer", "coordinator", "task-notification")

ANSWERS_LINE = "Answer Y to approve, N to decline, D to defer, R to repeat the item, or E to have it explained."
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
    "Then end the turn: this hook shows the user the items the line names.",
)
OLD_MARKER_PROBLEM = (
    "the newest marker line in its minutes {minutes} is the old form `Next to present:`, "
    "and the hook reads the current item only from a `#next_to_present` line.")
OLD_MARKER_INSTRUCTIONS = (
    "Add this line at the end of {minutes}, below every earlier marker line, and leave "
    "the old lines as they are: {new_line}",
    "Then end the turn: this hook shows the user the items the new line names.",
)


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def last_reply_text(transcript_path):
    """Return the text of the last assistant message of the transcript's last turn."""
    records = []
    with open(transcript_path, encoding="utf-8") as transcript:
        for line in transcript:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict):
                records.append(record)
    start = 0
    for index in range(len(records) - 1, -1, -1):
        record = records[index]
        if record.get("type") != "user":
            continue
        content = record.get("message", {}).get("content")
        if (isinstance(content, list) and content
                and all(isinstance(block, dict) and block.get("type") == "tool_result"
                        for block in content)):
            continue
        origin_kind = (record.get("origin") or {}).get("kind")
        if record.get("isMeta") and origin_kind not in TURN_STARTING_ORIGIN_KINDS:
            continue
        start = index + 1
        break
    texts_by_message = {}
    last_text_message_id = None
    for record in records[start:]:
        if record.get("type") != "assistant":
            continue
        message = record.get("message", {})
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                message_id = message.get("id") or id(record)
                texts_by_message.setdefault(message_id, []).append(block.get("text", ""))
                last_text_message_id = message_id
    return "\n".join(texts_by_message.get(last_text_message_id, []))


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


def markdown_parser(may_install):
    """Return the parser; raise ImportError when markdown-it-py is missing and may_install is false."""
    module = load_module("markdown_edit_hard_wrapped_paragraph_reminder_hook", MARKDOWN_PARSER_MODULE_FILE)
    if may_install:
        return module.markdown_parser()
    return module.import_markdown_it()("commonmark").enable("table")


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
    """Return [(item numbers, M, text, problem)] for each running count that starts an item.

    A count starts an item on a heading, or on a paragraph opening with `**`, except a
    paragraph whose items the count heading above it already names, with no other count
    between them, which stays in that heading's unit. A count that names no item still
    ends the unit before it; its unit has no numbers, and problem names the heading and
    says why. problem is None for every other unit. A unit is left out when a later
    heading whose text says `revised` names all of its items.
    """
    lines = document_text.split("\n")
    starts = []
    group = None
    tokens = parser.parse(document_text)
    for index, token in enumerate(tokens):
        if token.map is None or token.type not in ("heading_open", "paragraph_open"):
            continue
        first_line = token.map[0]
        if token.type == "paragraph_open" and not lines[first_line].lstrip().startswith("**"):
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
        elif group and set(numbers) <= group[0] and match[2] == group[1]:
            continue
        else:
            group = None
        revised = bool(REVISED.search(content[match.end():]))
        starts.append((first_line, numbers, match[2], problem, revised))
    units = []
    for index, (first_line, numbers, total, problem, _) in enumerate(starts):
        if numbers and any(revised and later_total == total and set(numbers) <= set(later_numbers)
                           for _, later_numbers, later_total, _, revised in starts[index + 1:]):
            continue
        end = starts[index + 1][0] if index + 1 < len(starts) else len(lines)
        units.append((numbers, total, "\n".join(lines[first_line:end]), problem))
    return units


def without_bold_marks_outside_code_spans(line):
    pieces, end = [], 0
    for span in CODE_SPAN.finditer(line):
        pieces += [line[end:span.start()].replace("**", ""), span[0]]
        end = span.end()
    return "".join(pieces + [line[end:].replace("**", "")])


def without_heading_and_bold_marks(text, parser):
    """Return text without heading marks, bold marks and separator lines, code left as written."""
    lines = text.split("\n")
    code_lines, heading_lines, separator_lines = set(), set(), set()
    for token in parser.parse(text):
        if token.map is None:
            continue
        span = range(*token.map)
        if token.type in ("fence", "code_block"):
            code_lines.update(span)
        elif token.type == "heading_open" and token.markup.startswith("#"):
            heading_lines.update(span)
        elif token.type == "hr":
            separator_lines.update(span)
    shown = []
    for number, line in enumerate(lines):
        if number in code_lines:
            shown.append(line)
            continue
        if number in separator_lines:
            line = ""
        elif number in heading_lines:
            line = re.sub(r"^[ \t]{0,3}#{1,6}(?:[ \t]+|$)", "", line)
        shown.append(without_bold_marks_outside_code_spans(line))
    return "\n".join(shown).strip("\n")


def block_output(opening, instructions, **values):
    lines = [opening.format(**values)] + [line.format(**values) for line in instructions]
    return json.dumps({"decision": "block", "reason": "\n".join(lines)}, ensure_ascii=False)


def run(stdin_text, environment):
    """Return the text to print, or None."""
    payload = json.loads(stdin_text)
    rule = load_module("claude_code_stop_hooks_stay_silent_while_agent_answers_a_stop_hook_rule_common",
                       STOP_HOOKS_STAY_SILENT_RULE_FILE)
    # The item notice is the rule's one exemption; a block on unusable minutes stays silent.
    output = output_for(payload, environment,
                        rule.stop_hook_stays_silent_while_agent_answers_a_stop_hook(payload))
    if not rule.stop_hook_output_may_be_printed_while_agent_answers_a_stop_hook(payload, output):
        return None
    return output


def output_for(payload, environment, answering_a_stop_hook):
    """The item notice, a block naming why there is no item to show, or None.

    While the agent answers a Stop hook, nothing is installed, because only a notice may be
    printed then and computing it may write no state.
    """
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
    parser = markdown_parser(may_install=not answering_a_stop_hook)
    walk = open_walk(top / WALK_DIRECTORY, parser)
    if walk is None:
        return None
    reply = last_reply_text(Path(transcript_path).expanduser())
    if not reply.strip():
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
        unreadable = [unit[3] for unit in all_units if unit[1] == total and unit[3]]
        return block(UNUSABLE_OPENING_TEMPLATE, UNUSABLE_INSTRUCTIONS, problem=(
            f"its walk-document has no heading {named}, which the minutes name"
            + "".join(f"; {each}" for each in unreadable) + "."))
    repeated = [number for number in numbers if sum(number in unit[0] for unit in units) > 1]
    if repeated:
        named = ", ".join(f"`Item {number} of {total}`" for number in repeated)
        return block(UNUSABLE_OPENING_TEMPLATE, UNUSABLE_INSTRUCTIONS, problem=(
            f"its walk-document has more than one heading for {named}, so the hook cannot tell "
            f"which one the minutes name: the heading that is misnumbered needs its own number, and "
            f"a heading that revises an earlier one says `(revised)` after its count."))
    shown = without_heading_and_bold_marks(
        "\n".join(unit[2].strip("\n") for unit in units), parser)
    return json.dumps({"systemMessage": shown + "\n\n" + ANSWERS_LINE}, ensure_ascii=False)


def main():
    try:
        output = run(sys.stdin.read(), os.environ)
    except Exception as error:
        print(f"walk-me-through-current-item-shown-to-user-after-each-agent-message-stop-hook: the hook "
              f"failed, so the user was not shown the approval-walk's current item; the agent "
              f"need not act: {error!r}", file=sys.stderr)
        return 1
    if output is not None:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
