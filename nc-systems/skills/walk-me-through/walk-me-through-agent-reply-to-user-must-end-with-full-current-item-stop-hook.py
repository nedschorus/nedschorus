#!/usr/bin/env python3
"""Stop hook: while an approval-walk is open, send the agent back when its
last message to the user does not end with the current item in full.

Wired as a Stop hook in .claude/settings.json. The walk-me-through skill tells
the agent to end every message it writes during an approval-walk with the
current item in full; this hook is the check on that rule. The skill's other
half, writing nothing when an automated event gives the user nothing new,
cannot be checked here: a turn that wrote nothing has nothing to check.

THE TURN starts at the last user-type record in the transcript that is not
only tool results: the user's message, another agent-seat's message, a
background-task notice, or a local command. The reply checked is the text of
the last assistant message after it; a turn whose assistant messages hold no
text, such as a silent turn after a background-task notice, is not checked.

THE OPEN APPROVAL-WALK. The walk-me-through skill keeps one line in each
walk's docs/walk/<name>-minutes.md reading `Next to present: item N of M.`,
`item 4.1 of 9`, `items 5 and 6 of 9`, or `none, closed.`; the last such line
in a minutes file is the one that counts. Among the minutes files in
docs/walk/ at the top of the checkout named by the payload's cwd, the open
approval-walk is the most recently modified one whose line names items.
Minutes with no such line, as every walk before the line existed, are not
open walks.

ITEMS IN THE WALK-DOCUMENT. The hook reads only what the skill fixes: each
item starts with its running count, `Item N of M` or, for items shown
together, `Items 5 and 6 of M`, on a heading line (one starting `#` or `**`),
and an item's recommendation is the letter after `Recommendation:`. An item
runs from its running-count line to the next running-count line, so headings
inside an item, such as an original and a proposed section, stay in it. A
heading that names several items is one unit, shown together.

THE CHECK, after Markdown emphasis, code marks, link targets and heading
marks are removed and case and whitespace are folded. Each unit the minutes
name owns the stretch of the reply from the last mention of its first item's
running count to the next unit's, or to the end of the reply for the last
unit:
  - every unit's running count appears in the reply, in the walk-document's
    order;
  - each stretch carries the unit's recommendation letters in the
    walk-document's order, so one item's letter does not pass for another's;
  - each stretch is at least MINIMUM_SHARE_OF_ITEM_WORDS of the unit's words
    in the walk-document, so a one-line summary does not pass;
  - the reply ends with the last unit: after its last recommendation, no more
    than the words the walk-document has there plus WORDS_ALLOWED_AFTER_ITEM
    follow (a question such as "Y, N or D?" or the case for the
    recommendation); a unit with no recommendation, such as a first
    sub-step, may run to (1 + MINIMUM_SHARE_OF_ITEM_WORDS) times its words
    plus WORDS_ALLOWED_AFTER_ITEM.

SILENT when stop_hook_active is set (the agent is already continuing because
of a Stop hook), when the agent-session is a headless `claude -p` child (its
last words are its caller's answer), when the transcript is missing, when the
turn's last reply is empty, when the cwd is not in a git checkout, and when no
approval-walk is open.

OUTPUT when the reply falls short, or when the open walk's minutes line or
walk-document cannot be used: {"decision": "block", "reason": <message>},
which keeps the agent going with the message as its next instruction. ON A
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
WALK_DIRECTORY = Path("docs") / "walk"
MINUTES_SUFFIX = "-minutes.md"
NEXT_LINE = re.compile(r"^\s*Next to present:\s*(.*?)\s*$", re.M)
CLOSED_VALUE = re.compile(r"^none\b", re.I)
ITEMS_VALUE = re.compile(r"^items?\s+(.+?)\s+of\s+(\d+)\.?$", re.I)
ITEM_NUMBER = re.compile(r"\d+(?:\.\d+)*")
# A running count: `item 2 of 9`, `item 4.1 of 9`, `items 5 and 6 of 9`, `items 5, 6 and 7 of 9`.
RUNNING_COUNT = r"items?\s+(\d+(?:\.\d+)*(?:\s*(?:,|and|&)\s*\d+(?:\.\d+)*)*)\s+of\s+{total}\b"
RECOMMENDATION = re.compile(r"recommendation:\s*\**\s*([A-Za-z])\b", re.I)
MINIMUM_SHARE_OF_ITEM_WORDS = 0.5
WORDS_ALLOWED_AFTER_ITEM = 80

BLOCK_OPENING_TEMPLATE = (
    "approval-walk current-item check: your message to the user does not end "
    "with the current item of the open approval-walk {walk}, whose minutes name "
    "the current item as `Next to present: {value}` ({reason}). The user answers "
    "the item at the end of your message, and should not have to scroll back to "
    "find it."
)
BLOCK_INSTRUCTIONS = (
    "If the approval-walk has closed, change that line in {minutes} to `Next to "
    "present: none, closed.` and end the turn without repeating the item.",
    "If the line names an item other than the one the user has yet to answer, "
    "correct the line in {minutes} first, then send the item it names.",
    "Otherwise, send the user one more message that holds only {items} in full, "
    "with its recommendation, as the walk-document {document} has it.",
)
UNUSABLE_OPENING_TEMPLATE = (
    "approval-walk current-item check: the open approval-walk {walk} could not "
    "be checked: {problem}"
)
UNUSABLE_INSTRUCTIONS = (
    "If the approval-walk has closed, change the `Next to present:` line in "
    "{minutes} to `Next to present: none, closed.` and end the turn.",
    "Otherwise, correct that line so that it names the items the user has yet to "
    "answer by their headings in the walk-document {document}, as `Next to "
    "present: item 3 of 9.`, `item 4.1 of 9.` or `items 5 and 6 of 9.`; change a "
    "heading in the walk-document only when the heading itself is misnumbered.",
    "Then send the user one more message that holds only the items the line "
    "names, in full, with their recommendations.",
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


def normalized(text):
    text = re.sub(r"\[([^\]\n]*)\]\([^)\n]*\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"[*_`]", "", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def word_count(text):
    return len(text.split())


def next_to_present(minutes_text):
    """Return the value of the minutes' last `Next to present:` line, or None."""
    values = NEXT_LINE.findall(minutes_text)
    return values[-1] if values else None


def parse_items(value):
    """Return (item numbers, M) from a line value such as `items 5 and 6 of 9.`, or None."""
    match = ITEMS_VALUE.match(value.strip().strip("`").strip())
    if not match:
        return None
    numbers = ITEM_NUMBER.findall(match[1])
    if not numbers:
        return None
    return numbers, match[2]


def open_walk(walk_directory):
    """Return (minutes path, line value) for the open approval-walk, or None."""
    candidates = []
    for minutes in walk_directory.glob("*" + MINUTES_SUFFIX):
        value = next_to_present(minutes.read_text(encoding="utf-8"))
        if value is None or CLOSED_VALUE.match(value.strip("`").strip()):
            continue
        candidates.append((minutes.stat().st_mtime, minutes, value))
    if not candidates:
        return None
    _, minutes, value = max(candidates, key=lambda candidate: candidate[0])
    return minutes, value


def item_units(document_text, total):
    """Return [(item numbers, text)] for each running-count heading in the walk-document."""
    heading = re.compile(r"^[ \t]*(?:#{1,6}[ \t]+|\*\*)[ \t]*(?:\*\*)?[ \t]*"
                         + RUNNING_COUNT.format(total=re.escape(total)), re.I | re.M)
    starts = list(heading.finditer(document_text))
    units = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(document_text)
        units.append((ITEM_NUMBER.findall(match[1]), document_text[match.start():end]))
    return units


def running_count_label(numbers, total):
    if len(numbers) == 1:
        return f"Item {numbers[0]} of {total}"
    return f"Items {', '.join(numbers[:-1])} and {numbers[-1]} of {total}"


def is_in_order_within(wanted, found):
    remaining = iter(found)
    return all(any(letter == candidate for candidate in remaining) for letter in wanted)


def shortfall(reply, units, total):
    """Return why the reply does not end with the named units, or None when it does."""
    text = normalized(reply)
    mentions = [(match.start(), set(ITEM_NUMBER.findall(match[1])))
                for match in re.finditer(RUNNING_COUNT.format(total=re.escape(total)), text)]
    starts = []
    limit = len(text) + 1
    for numbers, _ in reversed(units):
        # From the unit's first item, so a later item's line inside the unit
        # does not cut the earlier items out of its stretch.
        earlier = [position for position, named in mentions
                   if position < limit and numbers[0] in named]
        if not earlier:
            return f"the message does not contain `{running_count_label(numbers, total)}`"
        limit = earlier[-1]
        starts.append(limit)
    starts.reverse()
    for index, (numbers, unit_text) in enumerate(units):
        end = starts[index + 1] if index + 1 < len(units) else len(text)
        stretch = text[starts[index]:end]
        unit = normalized(unit_text)
        label = running_count_label(numbers, total)
        wanted = [letter.lower() for letter in RECOMMENDATION.findall(unit)]
        found = [letter.lower() for letter in RECOMMENDATION.findall(stretch)]
        if not is_in_order_within(wanted, found):
            letters = ", ".join(f"`Recommendation: {letter.upper()}`" for letter in wanted)
            return f"the message's `{label}` does not carry {letters} as the walk-document has it"
        if word_count(stretch) < MINIMUM_SHARE_OF_ITEM_WORDS * word_count(unit):
            return (f"`{label}` runs {word_count(stretch)} words in the message and "
                    f"{word_count(unit)} in the walk-document, so the message gives a "
                    f"summary, not the item")
    last_unit = normalized(units[-1][1])
    last_stretch = text[starts[-1]:]
    unit_recommendations = list(RECOMMENDATION.finditer(last_unit))
    if unit_recommendations:
        allowed = (word_count(last_unit[unit_recommendations[-1].end():])
                   + WORDS_ALLOWED_AFTER_ITEM)
        following = word_count(last_stretch[list(RECOMMENDATION.finditer(last_stretch))[-1].end():])
    else:
        allowed = ((1 + MINIMUM_SHARE_OF_ITEM_WORDS) * word_count(last_unit)
                   + WORDS_ALLOWED_AFTER_ITEM)
        following = word_count(last_stretch)
    if following > allowed:
        return f"{following} words follow the item, so the message does not end with it"
    return None


def block(opening, instructions, **values):
    lines = [opening.format(**values)] + [line.format(**values) for line in instructions]
    return json.dumps({"decision": "block", "reason": "\n".join(lines)}, ensure_ascii=False)


def run(stdin_text, environment):
    """Return the text to print, or None."""
    payload = json.loads(stdin_text)
    if payload.get("stop_hook_active"):
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
    walk = open_walk(top / WALK_DIRECTORY)
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
            f"its minutes' last `Next to present:` line, `{value}`, names no "
            f"item in the form `item N of M` or `items N and P of M`."), **values)
    numbers, total = parsed
    if not document.is_file():
        return block(UNUSABLE_OPENING_TEMPLATE, UNUSABLE_INSTRUCTIONS, problem=(
            f"its walk-document {document} does not exist."), **values)
    units = [unit for unit in item_units(document.read_text(encoding="utf-8"), total)
             if set(unit[0]) & set(numbers)]
    missing = [number for number in numbers if not any(number in unit[0] for unit in units)]
    if missing:
        named = ", ".join(f"`Item {number} of {total}`" for number in missing)
        return block(UNUSABLE_OPENING_TEMPLATE, UNUSABLE_INSTRUCTIONS, problem=(
            f"its walk-document has no heading {named}, which the minutes name."), **values)
    reason = shortfall(reply, units, total)
    if reason is None:
        return None
    items = " and ".join(running_count_label(unit[0], total) for unit in units)
    return block(BLOCK_OPENING_TEMPLATE, BLOCK_INSTRUCTIONS, reason=reason, items=items, **values)


def main():
    try:
        output = run(sys.stdin.read(), os.environ)
    except Exception as error:
        print(f"walk-me-through-agent-reply-to-user-must-end-with-full-current-item-stop-hook: the hook "
              f"failed, so it did not check that the message ends with the approval-walk's "
              f"current item; the agent need not act: {error!r}", file=sys.stderr)
        return 1
    if output is not None:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
