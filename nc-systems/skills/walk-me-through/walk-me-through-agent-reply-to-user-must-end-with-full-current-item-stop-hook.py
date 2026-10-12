#!/usr/bin/env python3
"""Stop hook: while an approval-walk is open, send the agent back when its
last message to the user does not end with the current item in full.

Wired as a Stop hook in .claude/settings.json. The walk-me-through skill tells
the agent to end every message it writes during an approval-walk with the
current item in full; this hook is the check on that rule. The skill's other
half, writing nothing when an automated event gives the user nothing new,
cannot be checked here: a turn that wrote nothing has nothing to check. The
transcript reader does not count a background-task notice as the start of a
turn, so after such a notice the reply checked is the agent's last reply
since the user's last message, which this hook saw when that turn ended.

THE OPEN APPROVAL-WALK. The walk-me-through skill keeps one line in each
walk's docs/walk/<name>-minutes.md reading `Next to present: item N of M.`,
`item 4.1 of 9`, `items 5 and 6 of 9`, or `none, closed.`; the last such line
in a minutes file is the one that counts. Among the minutes files in
docs/walk/ at the top of the checkout named by the payload's cwd, the open
approval-walk is the most recently modified one whose line names items.
Minutes with no such line, as every walk before the line existed, are not
open walks.

THE CHECK, for the last reply of the turn (read as
scripts/absence-claim-locator-reminder-hook.py reads it), after Markdown
emphasis, code marks, link targets and heading marks are removed and case and
whitespace are folded:
  - every named item's `Item N of M` appears in the reply;
  - the reply's text from the first named item to its end is at least
    MINIMUM_SHARE_OF_ITEM_WORDS of the named items' words in the walk-document,
    so a one-line summary does not pass;
  - after each named item's heading, the reply carries `Recommendation:` and
    the walk-document's letter, when the walk-document's section has one;
  - after the last named item's recommendation, or its heading when it has
    none, at most WORDS_ALLOWED_AFTER_ITEM words follow (a question such as
    "Y, N or D?" or the case for the recommendation).

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
TRANSCRIPT_READER_FILE = REPOSITORY_TOP / "scripts" / "absence-claim-locator-reminder-hook.py"
SUITE_RUNNER_FILE = REPOSITORY_TOP / "scripts" / "run-all-test-suites.py"
GIT_MODULE_FILE = (REPOSITORY_TOP / "nc-systems" / "general-tools"
                   / "git-machine-readable-output-runner-and-parser-common.py")
WALK_DIRECTORY = Path("docs") / "walk"
MINUTES_SUFFIX = "-minutes.md"
NEXT_LINE = re.compile(r"^\s*Next to present:\s*(.*?)\s*$", re.M)
CLOSED_VALUE = re.compile(r"^none\b", re.I)
ITEMS_VALUE = re.compile(r"^items?\s+(.+?)\s+of\s+(\d+)\.?$", re.I)
ITEM_NUMBER = re.compile(r"\d+(?:\.\d+)*")
RECOMMENDATION = re.compile(r"recommendation:\s*\**\s*([A-Za-z])\b", re.I)
MINIMUM_SHARE_OF_ITEM_WORDS = 0.5
WORDS_ALLOWED_AFTER_ITEM = 80

BLOCK_OPENING = (
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
UNUSABLE_OPENING = (
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
    """Read the turn's last reply with the absence-claim hook's reader."""
    reader = load_module("absence_claim_locator_reminder_hook", TRANSCRIPT_READER_FILE)
    reply, _ = reader.read_turn(transcript_path)
    return reply


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


def item_sections(document_text, numbers, total):
    """Return {number: section text} for each named item found in the walk-document."""
    headings = list(re.finditer(r"^#{1,6}\s.*$", document_text, re.M))
    sections = {}
    for index, heading in enumerate(headings):
        for number in numbers:
            pattern = rf"^#{{1,6}}\s+item\s+{re.escape(number)}\s+of\s+{total}\b"
            if re.match(pattern, heading.group(), re.I):
                end = headings[index + 1].start() if index + 1 < len(headings) else len(document_text)
                sections[number] = document_text[heading.start():end]
    return sections


def shortfall(reply, numbers, total, sections):
    """Return why the reply does not end with the named items, or None when it does."""
    text = normalized(reply)
    first_position = None
    end_of_items = 0
    for number in numbers:
        marker = f"item {number} of {total}"
        position = text.find(marker, end_of_items)
        if position < 0:
            position = text.find(marker)
        if position < 0:
            return f"the message does not contain `Item {number} of {total}`"
        if first_position is None or position < first_position:
            first_position = position
        end_of_items = max(end_of_items, position + len(marker))
        wanted = RECOMMENDATION.search(normalized(sections[number]))
        if wanted:
            found = None
            for match in RECOMMENDATION.finditer(text, position):
                if match[1].lower() == wanted[1].lower():
                    found = match
            if found is None:
                return (f"the message has no `Recommendation: {wanted[1].upper()}` "
                        f"after `Item {number} of {total}`")
            end_of_items = max(end_of_items, found.end())
    item_words = sum(word_count(normalized(sections[number])) for number in numbers)
    shown_words = word_count(text[first_position:])
    if shown_words < MINIMUM_SHARE_OF_ITEM_WORDS * item_words:
        return (f"the item runs {shown_words} words in the message and {item_words} "
                f"in the walk-document, so the message gives a summary, not the item")
    words_after = word_count(text[end_of_items:])
    if words_after > WORDS_ALLOWED_AFTER_ITEM:
        return f"{words_after} words follow the item, so the message does not end with it"
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
        return block(UNUSABLE_OPENING, UNUSABLE_INSTRUCTIONS, problem=(
            f"its minutes' last `Next to present:` line, `{value}`, names no "
            f"item in the form `item N of M` or `items N and P of M`."), **values)
    numbers, total = parsed
    if not document.is_file():
        return block(UNUSABLE_OPENING, UNUSABLE_INSTRUCTIONS, problem=(
            f"its walk-document {document} does not exist."), **values)
    sections = item_sections(document.read_text(encoding="utf-8"), numbers, total)
    missing = [number for number in numbers if number not in sections]
    if missing:
        named = ", ".join(f"`Item {number} of {total}`" for number in missing)
        return block(UNUSABLE_OPENING, UNUSABLE_INSTRUCTIONS, problem=(
            f"its walk-document has no heading {named}, which the minutes name."), **values)
    reason = shortfall(reply, numbers, total, sections)
    if reason is None:
        return None
    items = " and ".join(f"Item {number} of {total}" for number in numbers)
    return block(BLOCK_OPENING, BLOCK_INSTRUCTIONS, reason=reason, items=items, **values)


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
