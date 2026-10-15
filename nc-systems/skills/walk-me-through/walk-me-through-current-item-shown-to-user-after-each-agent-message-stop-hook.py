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

THE OPEN APPROVAL-WALK. The walk-me-through skill keeps one line in each
walk's docs/walk/<name>-minutes.md reading `Next to present: item N of M.`,
`item 4.1 of 9`, `items 5 and 6 of 9`, or `none, closed.`; the last such line
in a minutes file is the one that counts. Among the minutes files in
docs/walk/ at the top of the checkout named by the payload's cwd, the open
approval-walk is the most recently modified one whose line names items.
Minutes with no such line, as every walk before the line existed, are not
open walks.

ITEMS IN THE WALK-DOCUMENT. An item starts at its running count, `Item N of
M` or, for items shown together, `Items 5 and 6 of M`, on a heading line
(one starting `#` or `**`), and runs to the next running count, so headings
inside an item, such as an original and a proposed section, stay in it. A
heading that names several items is one unit.

WHAT IS SHOWN is the text of the units the minutes name, taken from the
walk-document in the walk-document's order, without heading marks, bold marks
and separator lines, which Claude Code would show as written, followed by
ANSWERS_LINE. So an
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
WALK_DIRECTORY = Path("docs") / "walk"
MINUTES_SUFFIX = "-minutes.md"
NEXT_LINE = re.compile(r"^\s*Next to present:\s*(.*?)\s*$", re.M)
CLOSED_VALUE = re.compile(r"^none\b", re.I)
ITEMS_VALUE = re.compile(r"^items?\s+(.+?)\s+of\s+(\d+)\.?$", re.I)
ITEM_NUMBER = re.compile(r"\d+(?:\.\d+)*")
# A running count: `item 2 of 9`, `item 4.1 of 9`, `items 5 and 6 of 9`, `items 5, 6 and 7 of 9`.
RUNNING_COUNT = r"items?\s+(\d+(?:\.\d+)*(?:\s*(?:,|and|&)\s*\d+(?:\.\d+)*)*)\s+of\s+{total}\b"
# A record from one of these starts a turn even when Claude Code marks it isMeta.
TURN_STARTING_ORIGIN_KINDS = ("human", "peer", "coordinator", "task-notification")

ANSWERS_LINE = "Answer Y, N, D to defer, or R to repeat the item."
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


def without_heading_and_bold_marks(text):
    text = re.sub(r"^[ \t]{0,3}#{1,6}[ \t]+", "", text, flags=re.M)
    text = re.sub(r"^[ \t]*(?:[-*_][ \t]*){3,}$", "", text, flags=re.M)
    return text.replace("**", "").strip("\n")


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
    shown = without_heading_and_bold_marks("\n".join(unit_text.strip("\n") for _, unit_text in units))
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
