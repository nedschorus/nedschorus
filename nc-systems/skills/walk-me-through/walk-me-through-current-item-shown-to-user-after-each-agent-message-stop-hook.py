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

THE OPEN APPROVAL-WALK. The walk-me-through skill keeps a `Next to present:`
line in each walk's docs/walk/<name>-minutes.md; agents write it at a line's
start, in a bullet, or mid-sentence, so the marker is found anywhere outside
code, and the last one in a minutes file counts. Its value is `none` or
`closed` for a closed walk, or opens with a running count, `item N`,
`item 4.1`, `items 5 and 6`, `items 10 to 12`, with or without `of M`, and
anything after the count, such as `(awaiting answer), then item 24`, is
ignored. Among the minutes files in docs/walk/ at the top of the checkout
named by the payload's cwd, the open approval-walk is the most recently
modified one whose value is not closed. Minutes with no such line, as every
walk before the line existed, are not open walks.

ITEMS IN THE WALK-DOCUMENT. An item starts at its running count, `Item N of
M`, `Items 5 and 6 of M` or `Items 10 to 12 of M`, on a heading or on a
paragraph opening with `**`, as markdown-it-py reads the document, so a count
inside code starts nothing; it runs to the next running count, so headings
inside an item, such as an original and a proposed section, stay in it. A
heading that names several items is one unit. When the minutes' value has no
`of M`, the walk-document's own total is used, if its headings carry only one.

WHAT IS SHOWN is the text of the units the minutes name, taken from the
walk-document in the walk-document's order, without heading marks, bold marks
and separator lines, which Claude Code would show as written, followed by
ANSWERS_LINE. Code spans and code blocks are shown as written: a `#` or `**`
there is part of the code. So an
agent that rewords an item edits the walk-document first, or the user is shown
the old text.

SILENT when stop_hook_active is set (the agent is already continuing because
of a Stop hook), when the agent-session is a headless `claude -p` child (its
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
NEXT_MARKER = re.compile(r"Next to present:[*_`\s]*([^\n]*)", re.I)
CLOSED_VALUE = re.compile(r"^(?:none|closed)\b", re.I)
NUMBER = r"\d+(?:\.\d+)*"
NUMBER_JOINER = r"\s*(?:,|&|\band\b|\bto\b|-|\u2013)\s*"
# A running count: `item 2`, `item 4.1`, `items 5 and 6`, `items 5, 6 and 7`, `items 10 to 12`, `items 10-12`.
NUMBER_LIST = rf"{NUMBER}(?:{NUMBER_JOINER}{NUMBER})*(?![\d.]\d)"
VALUE_COUNT = re.compile(rf"^items?\s+({NUMBER_LIST})(?:\s+of\s+(\d+)\b)?", re.I)
HEADING_COUNT = re.compile(rf"^[*_\s]*items?\s+({NUMBER_LIST})\s+of\s+(\d+)\b", re.I)
NUMBER_OR_JOINER = re.compile(rf"{NUMBER}|\bto\b|-|\u2013", re.I)
# A record from one of these starts a turn even when Claude Code marks it isMeta.
TURN_STARTING_ORIGIN_KINDS = ("human", "peer", "coordinator", "task-notification")

ANSWERS_LINE = "Answer Y to approve, N to decline, D to defer, or R to repeat the item."
UNUSABLE_OPENING_TEMPLATE = (
    "approval-walk current-item check: the open approval-walk {walk} could not "
    "be checked: {problem}"
)
UNUSABLE_INSTRUCTIONS = (
    "If the approval-walk has closed, change the `Next to present:` line in "
    "{minutes} to `Next to present: none, closed.` and end the turn.",
    "Otherwise, correct that line so that it names the items the user has yet to "
    "answer by their headings in the walk-document {document}, as `Next to "
    "present: item 3 of 9.`, `item 4.1 of 9.`, `items 5 and 6 of 9.` or `items 10 to 12 of 54.`; change a "
    "heading in the walk-document only when the heading itself is misnumbered.",
    "Then end the turn: this hook shows the user the items the line names.",
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


def markdown_parser():
    return load_module("markdown_edit_hard_wrapped_paragraph_reminder_hook",
                       MARKDOWN_PARSER_MODULE_FILE).markdown_parser()


def code_line_numbers(tokens):
    lines = set()
    for token in tokens:
        if token.map is not None and token.type in ("fence", "code_block"):
            lines.update(range(*token.map))
    return lines


def without_code_spans(line):
    return CODE_SPAN.sub(" ", line)


def next_to_present(minutes_text, parser):
    """Return the value after the minutes' last `Next to present:` outside code, or None."""
    code_lines = code_line_numbers(parser.parse(minutes_text))
    values = []
    for number, line in enumerate(minutes_text.split("\n")):
        if number not in code_lines:
            values += NEXT_MARKER.findall(without_code_spans(line))
    return values[-1].strip() if values else None


def is_closed(value):
    return bool(CLOSED_VALUE.match(value))


def expand_numbers(number_list):
    """Return the item numbers a list such as `5, 6 and 7` or `10 to 12` names, or None."""
    pieces = NUMBER_OR_JOINER.findall(number_list)
    numbers, index = [], 0
    while index < len(pieces):
        if index + 2 < len(pieces) and pieces[index + 1].lower() in ("to", "-", "\u2013"):
            first, last = pieces[index], pieces[index + 2]
            first_head, _, first_tail = first.rpartition(".")
            last_head, _, last_tail = last.rpartition(".")
            if first_head != last_head or int(first_tail) > int(last_tail):
                return None
            prefix = first_head + "." if first_head else ""
            numbers += [prefix + str(n) for n in range(int(first_tail), int(last_tail) + 1)]
            index += 3
        elif pieces[index].lower() in ("to", "-", "\u2013"):
            return None
        else:
            numbers.append(pieces[index])
            index += 1
    return numbers or None


def parse_items(value):
    """Return (item numbers, M or None) from a value such as `items 10 to 12 of 54.`, or None."""
    match = VALUE_COUNT.match(value)
    if not match:
        return None
    numbers = expand_numbers(match[1])
    return (numbers, match[2]) if numbers else None


def open_walk(walk_directory, parser):
    """Return (minutes path, value) for the open approval-walk, or None."""
    candidates = []
    for minutes in walk_directory.glob("*" + MINUTES_SUFFIX):
        value = next_to_present(minutes.read_text(encoding="utf-8"), parser)
        if value is None or is_closed(value):
            continue
        candidates.append((minutes.stat().st_mtime, minutes, value))
    if not candidates:
        return None
    _, minutes, value = max(candidates, key=lambda candidate: candidate[0])
    return minutes, value


def item_units(document_text, parser):
    """Return [(item numbers, M, text)] for each running count that starts an item.

    A count starts an item on a heading, or on a paragraph opening with `**`.
    """
    lines = document_text.split("\n")
    starts = []
    tokens = parser.parse(document_text)
    for index, token in enumerate(tokens):
        if token.map is None or token.type not in ("heading_open", "paragraph_open"):
            continue
        first_line = token.map[0]
        if token.type == "paragraph_open" and not lines[first_line].lstrip().startswith("**"):
            continue
        content = tokens[index + 1].content.split("\n")[0] if index + 1 < len(tokens) else ""
        match = HEADING_COUNT.match(content)
        numbers = expand_numbers(match[1]) if match else None
        if numbers:
            starts.append((first_line, numbers, match[2]))
    units = []
    for index, (first_line, numbers, total) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(lines)
        units.append((numbers, total, "\n".join(lines[first_line:end])))
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


def block(opening, instructions, **values):
    lines = [opening.format(**values)] + [line.format(**values) for line in instructions]
    return json.dumps({"decision": "block", "reason": "\n".join(lines)}, ensure_ascii=False)


def run(stdin_text, environment):
    """Return the text to print, or None."""
    payload = json.loads(stdin_text)
    rule = load_module("claude_code_stop_hooks_stay_silent_while_agent_answers_a_stop_hook_rule_common",
                       STOP_HOOKS_STAY_SILENT_RULE_FILE)
    if rule.stop_hook_stays_silent_while_agent_answers_a_stop_hook(payload):
        return None
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
    reply = last_reply_text(Path(transcript_path).expanduser())
    if not reply.strip():
        return None
    minutes, value = walk
    name = minutes.name[:-len(MINUTES_SUFFIX)]
    document = minutes.with_name(name + ".md")
    values = {"walk": name, "minutes": minutes, "document": document, "value": value}
    parsed = parse_items(value)
    if parsed is None:
        return block(UNUSABLE_OPENING_TEMPLATE, UNUSABLE_INSTRUCTIONS, problem=(
            f"its minutes' last `Next to present:` line, `{value}`, does not open "
            f"with an item in one of the forms `item N of M`, `item N.K of M`, "
            f"`items N and P of M` or `items N to P of M`."), **values)
    numbers, total = parsed
    if not document.is_file():
        return block(UNUSABLE_OPENING_TEMPLATE, UNUSABLE_INSTRUCTIONS, problem=(
            f"its walk-document {document} does not exist."), **values)
    all_units = item_units(document.read_text(encoding="utf-8"), parser)
    if total is None:
        totals = {unit_total for _, unit_total, _ in all_units}
        if len(totals) != 1:
            return block(UNUSABLE_OPENING_TEMPLATE, UNUSABLE_INSTRUCTIONS, problem=(
                f"its minutes' last `Next to present:` line, `{value}`, gives no `of M`, "
                f"and the walk-document's headings give more than one total, so the line "
                f"must say which: write it as `item N of M`, with M the total of the "
                f"heading meant."), **values)
        total = totals.pop()
    units = [unit for unit in all_units if unit[1] == total and set(unit[0]) & set(numbers)]
    missing = [number for number in numbers if not any(number in unit[0] for unit in units)]
    if missing:
        named = ", ".join(f"`Item {number} of {total}`" for number in missing)
        return block(UNUSABLE_OPENING_TEMPLATE, UNUSABLE_INSTRUCTIONS, problem=(
            f"its walk-document has no heading {named}, which the minutes name."), **values)
    shown = without_heading_and_bold_marks(
        "\n".join(unit_text.strip("\n") for _, _, unit_text in units), parser)
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
