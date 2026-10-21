#!/usr/bin/env python3
"""Find the open approval-walk and its waiting items: the walk-minutes' last
`#next_to_present` line, and the units of the walk-document that hold the
items it names. The walk-me-through Stop hook, the short-answer
UserPromptSubmit hook and the check program load this module by path, so all
three read the walk files the same way.

THE OPEN APPROVAL-WALK. The walk-me-through skill keeps a `#next_to_present`
line in each walk's docs/walk/<name>-minutes.md. The marker is found anywhere
outside code, the last one in a minutes file counts, and one inside a code
span is a quotation; a value inside a code span is read without its
backticks, and a colon after the hashtag is read as the old form's colon was.
The old marker `Next to present:` is read too, so that a caller can migrate
it. A value is `none` or `closed` for a closed walk, or opens with a running
count, `item N`, `item 4.1`, `items 5 and 6`, `items 10 to 12`, with or
without `of M`. Among the minutes files in docs/walk/, the open approval-walk
is the most recently modified one whose value is not closed.

ITEMS IN THE WALK-DOCUMENT. An item starts at its running count, `Item N of
M`, `Items 5 and 6 of M`, `Items 10 to 12 of M` or `Items 12 to 12.3 of M`,
on a heading or on a paragraph opening with `**`, as markdown-it-py reads the
document, and runs to the next running count. A heading that names several
items is one unit, and so are the paragraphs under it that open with the
count of one of its items. A heading that says `revised` right after its
count replaces the earlier units it names. A running count that names no
item still ends the unit before it.

Agent-facing messages follow
docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
"""
import importlib.util
import os
import re
from pathlib import Path

REPOSITORY_TOP = Path(__file__).resolve().parents[3]
SUITE_RUNNER_FILE = REPOSITORY_TOP / "scripts" / "run-all-test-suites.py"
GIT_MODULE_FILE = (REPOSITORY_TOP / "nc-systems" / "general-tools"
                   / "git-machine-readable-output-runner-and-parser-common.py")
MARKDOWN_PARSER_MODULE_FILE = (REPOSITORY_TOP / "nc-systems" / "general-tools"
                               / "markdown-commonmark-parser-with-tables-common.py")
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
NOT_A_FORM_PROBLEM = (
    "does not open with an item in one of the forms `item N of M`, `item N.K of M`, "
    "`items N and P of M` or `items N to P of M`")


class UnusableRange(ValueError):
    """A running count names no item, or the walk-document does not hold the items one names; its
    argument says why."""


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


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
    return load_module("markdown_commonmark_parser_with_tables_common",
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


def item_unit_spans(document_text, parser):
    """Return [(item numbers, M, problem, first line, end line)] for each running count that starts an item.

    The lines are 0-based; a unit runs from its first line up to, not including, its end
    line, which is where the next running count starts, or the document's line count.

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
        starts.append((numbers, match[2], problem, revised, token.map[0]))
    ends = [start[4] for start in starts[1:]] + [len(lines)]
    return [(numbers, total, problem, first, ends[index])
            for index, (numbers, total, problem, _, first) in enumerate(starts)
            if not (numbers and any(revised and later_total == total and set(numbers) <= set(later_numbers)
                                    for later_numbers, later_total, _, revised, _ in starts[index + 1:]))]


def approval_walk_item_line_range_within_heading_shared_by_several_items(lines, number, numbers, total):
    """Return (first, end) of the lines, of a unit naming several items, that belong to item number: from
    the line holding its running count up to the next such line of another of the unit's items, or every
    line when no line holds its count."""
    starts = {other: index for index, line in enumerate(lines) for other in numbers
              if re.search(rf"\bItem {re.escape(other)} of {total}\b", line)}
    if number not in starts:
        return 0, len(lines)
    later = [index for other, index in starts.items() if index > starts[number]]
    return starts[number], min(later) if later else len(lines)


def waiting_item_units(document, value, numbers, total, parser):
    """Return (M, the units of item_unit_spans that hold the waiting items) for the item numbers and
    total M that parse_items read from the `#next_to_present` value, M None when it gives none.

    Raise UnusableRange, saying what is wrong, when the walk-document does not exist, when M is None
    and the walk-document's headings give no total or more than one, or when a waiting item has no
    heading, or more than one that is not a revision."""
    if not document.is_file():
        raise UnusableRange(f"its walk-document {document} does not exist.")
    all_units = item_unit_spans(document.read_text(encoding="utf-8"), parser)
    if total is None:
        totals = {unit[1] for unit in all_units}
        if not totals:
            raise UnusableRange(
                f"its walk-document {document} has no heading with a running count, such "
                f"as `## Item 3 of 9: <the point>`, so the hook cannot find the item the "
                f"minutes name: give each item's heading its count `Item N of M`.")
        if len(totals) > 1:
            listed = ", ".join(f"`of {each}`" for each in sorted(totals, key=int))
            raise UnusableRange(
                f"its minutes' last `#next_to_present` line, `{value}`, gives no `of M`, "
                f"and the walk-document's headings give more than one total ({listed}), "
                f"so the line must say which: write it as `item N of M`, with M the total "
                f"of the heading meant.")
        total = totals.pop()
    units = [unit for unit in all_units if unit[1] == total and set(unit[0]) & set(numbers)]
    missing = [number for number in numbers if not any(number in unit[0] for unit in units)]
    if missing:
        named = ", ".join(f"`Item {number} of {total}`" for number in missing)
        unreadable = [unit[2] for unit in all_units if unit[1] == total and unit[2]]
        raise UnusableRange(
            f"its walk-document has no heading {named}, which the minutes name"
            + "".join(f"; {each}" for each in unreadable) + ".")
    repeated = [number for number in numbers if sum(number in unit[0] for unit in units) > 1]
    if repeated:
        named = ", ".join(f"`Item {number} of {total}`" for number in repeated)
        raise UnusableRange(
            f"its walk-document has more than one heading for {named}, so the hook cannot tell "
            f"which one the minutes name.")
    return total, units
