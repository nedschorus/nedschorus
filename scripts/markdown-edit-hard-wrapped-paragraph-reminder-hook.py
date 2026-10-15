#!/usr/bin/env python3
"""Remind the agent to keep Markdown paragraphs on one line, after an Edit or
Write leaves a Markdown file holding a paragraph broken across lines.

Use hookSpecificOutput.additionalContext: successful PostToolUse plain stdout reaches only the debug log.
Read cwd from the payload; CLAUDE_PROJECT_DIR can name a different checkout in a forked session.

The whole file is read from disk after the tool ran, for Edit as for Write, so an
Edit inside a fenced code block is judged with the fence visible. Only a broken
paragraph the tool wrote is reported: for a Write, any in the file; for an Edit, one
whose lines overlap a line the Edit added. The added lines come from a line diff of each
replacement the Edit made in the payload's tool_response.originalFile (see
edit_added_line_numbers): a search for new_string in the file would also find copies the
Edit did not write, and tool_response.structuredPatch is built after leading tabs are
turned into spaces, so it drops a line whose only change is a tab. A broken paragraph
the agent did not touch is left alone, because in a file the instruction-file guard
protects, rejoining it would need the user's approval for whitespace. An Edit that only deleted lines adds none and gets no reminder. An Edit
of a file holding a broken paragraph, whose added lines cannot be found that way,
gets one line on stderr and exit 1, a non-blocking hook error, so the agent is told the
check was not made. An Edit of a file holding no broken paragraph needs no diff to be
judged, so a payload lacking that text there is not reported.
The reminder carries no line numbers: the agent is to rejoin each broken
paragraph it wrote, and to write later Markdown files the same way.

Which lines form a paragraph is decided by markdown-it-py's CommonMark parser, not
by this file: a paragraph, in a list item or at the top level, is broken when its
inline content holds a soft line break. markdown-it-py is pinned in
nc-systems/general-tools/python-libraries-pinned-requirements.txt; when it is
missing, the hook installs the pinned file through the shared install module,
for the python3 the hooks run. When that install fails, the hook writes to
stderr what failed, what the install printed and the command that installs it
by hand, and exits 1, which Claude Code shows as a non-blocking hook error.

A file holding display math ($$) or a footnote definition ([^label]:) gets no
reminder at all: CommonMark reads both as paragraphs, and judging their line
breaks needs rules this hook does not carry, so it stays silent rather than tell
an agent to join lines that must stay apart.

A fault, such as stdin that is not a JSON object, a written file that cannot be read
or any exception: one line on stderr naming the hook and the fault, nothing on stdout,
exit 1. Claude Code records a PostToolUse exit 1 as a non-blocking error and keeps the
write; exit 0 would read as "no broken paragraph found". A file that is not UTF-8 is
not a fault: the hook judges only UTF-8 text, and stays silent on other bytes."""

import difflib
import functools
import importlib.util
import json
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

MARKDOWN_SUFFIXES = (".md", ".markdown")

REMINDER_MESSAGE = (
    "markdown-edit-hard-wrapped-paragraph-reminder: the text you just wrote in {path} holds a "
    "paragraph or list item broken across lines. A line break inside a paragraph, list item "
    "or table row is extra whitespace to a reader whose editor wraps lines to the screen's "
    "width, and makes the text hard to edit.\n"
    "In {path}, join the lines of each broken paragraph and list item you wrote into one "
    "line; leave the paragraphs you did not touch as they are.\n"
    "In every Markdown file you write from now on, write each paragraph, list item and "
    "table row as one line, however long; break lines only where Markdown needs a break."
)

# Front matter opens on the file's first line and closes on a line holding --- or ...
FRONT_MATTER_DELIMITER = "---"
FRONT_MATTER_CLOSERS = ("---", "...")
# A line whose text, past indentation and list or quote markers, starts with $$
# or a footnote label makes the whole file one this hook stays silent on.
LINE_PREFIX_MARKERS_PATTERN = re.compile(r"^(?:[ \t>]*(?:[-*+]|\d{1,9}[.)])(?=[ \t]))*[ \t>]*")
UNJUDGED_BLOCK_START_PATTERN = re.compile(r"\$\$|\[\^[^\]]+\]:")
# An inline <br> at a line's end is a hard break the author chose, like two trailing spaces.
LINE_END_BREAK_TAG_PATTERN = re.compile(r"^<br\s*/?>$", re.IGNORECASE)
PARSER_MISSING_MESSAGE = (
    "markdown-edit-hard-wrapped-paragraph-reminder: markdown-it-py is missing on {host} and "
    "installing it failed, so the paragraphs you just wrote were not checked for hard wraps.\n"
    "Go on with your task, and write each paragraph and list item as one line, however long.\n"
    "Tell the user, or, if you are a subagent, the agent that dispatched you, in these words: "
    "\"markdown-it-py is missing on {host} and could not be installed, so the hard-wrap reminder "
    "is off there. To install it by hand, run this command {where}:\" Then give the install "
    "command on a line of its own:\n"
    "{command}\n"
    "Then pass on what the install printed, quoted as it is: {install_output}")
PARSER_MISSING_BELOW_MINIMUM_PYTHON_MESSAGE = (
    "markdown-edit-hard-wrapped-paragraph-reminder: markdown-it-py is missing on {host} and "
    "installing it failed, so the paragraphs you just wrote were not checked for hard wraps.\n"
    "Go on with your task, and write each paragraph and list item as one line, however long.\n"
    "Tell the user, or, if you are a subagent, the agent that dispatched you, in these words: "
    "\"markdown-it-py is missing on {host} and could not be installed, so the hard-wrap reminder "
    "is off there. {instruction}\" "
    "Then pass on what the install printed, quoted as it is: {install_output}")
# PostToolUse hooks run under a 30-second timeout; a cached wheel installs in about a second.
INSTALL_TIMEOUT_SECONDS = 8
INSTALL_STATE_DIRECTORY = Path.home() / ".cache" / "nedschorus-markdown-edit-hard-wrapped-paragraph-reminder"


class MarkdownParserMissing(Exception):
    """markdown-it-py cannot be imported, and installing it failed; install_output says how."""

    def __init__(self, install_output):
        super().__init__(install_output)
        self.install_output = install_output


@functools.lru_cache(maxsize=None)
def python_libraries_pinned_requirements_install_if_missing_then_import_common():
    """Return the shared install module, loaded by path when first needed."""
    specification = importlib.util.spec_from_file_location(
        "python_libraries_pinned_requirements_install_if_missing_then_import_common",
        Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
        / "python-libraries-pinned-requirements-install-if-missing-then-import-common.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def import_markdown_it():
    """Return the MarkdownIt class, raising ImportError when markdown-it-py is missing."""
    from markdown_it import MarkdownIt
    return MarkdownIt


def _install_pinned_python_libraries(runner=subprocess.run):
    return python_libraries_pinned_requirements_install_if_missing_then_import_common().pinned_requirements_pip_install(
        INSTALL_TIMEOUT_SECONDS, runner)


def parser_missing_message(error, host=None, python_version=None):
    """Return the stderr text for markdown-it-py missing on this machine and its install failed."""
    host = host or socket.gethostname().split(".")[0]
    install = python_libraries_pinned_requirements_install_if_missing_then_import_common()
    where, command = install.pinned_requirements_by_hand_install_command(
        host, python_version=python_version)
    if command is None:
        return PARSER_MISSING_BELOW_MINIMUM_PYTHON_MESSAGE.format(
            host=host, instruction=install.python_below_minimum_version_instruction(host, python_version),
            install_output=error.install_output)
    return PARSER_MISSING_MESSAGE.format(host=host, where=where, command=command,
                                         install_output=error.install_output)


def _load_edited_file_path_within_checkout_root_and_git_check_ignore():
    """Return the shared checkout and git-tracking helpers, loaded by path; raises when they will not load."""
    specification = importlib.util.spec_from_file_location(
        "edited_file_path_within_checkout_root_and_git_check_ignore_common",
        Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
        / "edited-file-path-within-checkout-root-and-git-check-ignore-common.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def markdown_parser(importer=import_markdown_it, installer=_install_pinned_python_libraries, clock=time.time):
    """Return a CommonMark parser with tables, installing markdown-it-py when it is missing.

    markdown-it-py and mdurl are written only in Python, so once their half-imported modules
    are dropped, this process imports the installed copy and never needs a new process.

    Raises MarkdownParserMissing when markdown-it-py is missing and installing it failed.
    """
    try:
        markdown_it_class = importer()
    except ImportError:
        install = python_libraries_pinned_requirements_install_if_missing_then_import_common()
        try:
            markdown_it_class = install.python_libraries_pinned_requirements_install_if_missing_then_import(
                importer, installer, clock, lambda: False, INSTALL_STATE_DIRECTORY, ("markdown_it", "mdurl"))
        except install.PythonLibrariesPinnedRequirementsInstallOrImportFailed as error:
            raise MarkdownParserMissing(error.install_output) from error
    return markdown_it_class("commonmark").enable("table")


def front_matter_blanked(text: str) -> str:
    """Return text with front matter blanked, line count kept."""
    lines = text.split("\n")
    if lines and lines[0].rstrip("\r").rstrip() == FRONT_MATTER_DELIMITER:
        for closing_index in range(1, len(lines)):
            if lines[closing_index].rstrip("\r").rstrip() in FRONT_MATTER_CLOSERS:
                for index in range(closing_index + 1):
                    lines[index] = ""
                break
    return "\n".join(lines)


def holds_math_or_footnote_definition(text: str) -> bool:
    for line in text.split("\n"):
        after_markers = line[LINE_PREFIX_MARKERS_PATTERN.match(line).end():]
        if UNJUDGED_BLOCK_START_PATTERN.match(after_markers):
            return True
    return False


def counts_as_line_break(children, position: int) -> bool:
    """A soft break counts unless the inline token before it, past any
    whitespace-only text, is a <br> tag."""
    previous_position = position - 1
    while (previous_position >= 0 and children[previous_position].type == "text"
           and not children[previous_position].content.strip()):
        previous_position -= 1
    if previous_position >= 0:
        previous = children[previous_position]
        if previous.type == "html_inline" and LINE_END_BREAK_TAG_PATTERN.match(previous.content.strip()):
            return False
    return True


def markdown_broken_paragraph_line_ranges(text: str) -> list:
    """The [start, end) line ranges of the paragraphs holding a soft line break
    the author did not choose.

    A paragraph is what the CommonMark parser calls one, at the top level or in a
    list item. A paragraph inside a block quote is left alone: a quote often keeps
    the line breaks of the text it quotes. Hard breaks, two trailing spaces, a
    trailing backslash or a trailing <br>, are breaks the author chose. A file
    holding display math or a footnote definition is never reported.
    Raises MarkdownParserMissing when markdown-it-py is missing and installing it failed."""
    parser = markdown_parser()
    if holds_math_or_footnote_definition(text):
        return []
    tokens = parser.parse(front_matter_blanked(text))
    ranges = []
    block_quote_depth = 0
    for position, token in enumerate(tokens):
        if token.type == "blockquote_open":
            block_quote_depth += 1
        elif token.type == "blockquote_close":
            block_quote_depth -= 1
        elif (token.type == "inline" and block_quote_depth == 0
                and position > 0 and tokens[position - 1].type == "paragraph_open"):
            children = token.children or []
            if any(child.type == "softbreak" and counts_as_line_break(children, child_position)
                   for child_position, child in enumerate(children)):
                ranges.append(tuple(tokens[position - 1].map))
    return ranges


# SequenceMatcher without autojunk can take cubic time on spans of repeated lines: 800 lines
# against 800 took about 5 s on ned-box, past which a span's every new line counts as added.
LINE_DIFF_MAXIMUM_LINE_PAIRS = 250_000


class EditedLinesUnknown(Exception):
    pass


def edit_added_line_numbers(tool_response, text_after: str) -> set:
    """The 0-based line numbers, in text_after, of the lines the Edit added.

    Each replacement of oldString by newString in tool_response.originalFile is found
    where str.replace finds it, and the lines it spans before and after the Edit are
    line-diffed; a line the diff marks inserted or replaced is added. Diffing only these
    spans keeps a replace_all Edit linear in the file's length, and leaves out lines
    new_string repeats from old_string as context. The spans are placed by line counts,
    not by rebuilding the file: Claude Code hands over originalFile with CRLF line ends
    turned into LF, and newString as typed when the Edit matched straight quotes to curly
    ones but wrote curly ones. Raise EditedLinesUnknown when the payload lacks the text
    this needs, or when text_after's line count is not the one the replacements give."""
    if not isinstance(tool_response, dict):
        raise EditedLinesUnknown("the Edit's payload carries no tool_response object")
    original = tool_response.get("originalFile")
    old, new = tool_response.get("oldString"), tool_response.get("newString")
    replace_all = tool_response.get("replaceAll")
    if not (isinstance(original, str) and isinstance(old, str) and isinstance(new, str)
            and isinstance(replace_all, bool)):
        raise EditedLinesUnknown("the Edit's payload lacks tool_response's originalFile, oldString, "
                                 "newString or replaceAll")
    after_lines = text_after.replace("\r\n", "\n").split("\n")
    if not old:
        return set(range(len(after_lines)))
    before_lines = original.split("\n")
    # Claude Code removes an empty Edit's following newline too when old ends without one,
    # so the line count says which of the two texts it removed.
    for removed in ([old, old + "\n"] if not new and not old.endswith("\n") else [old]):
        replacements = original.count(removed) if replace_all else min(original.count(removed), 1)
        line_shift = new.count("\n") - removed.count("\n")
        if replacements and len(after_lines) == len(before_lines) + replacements * line_shift:
            return _lines_replacements_added(original, before_lines, after_lines, removed, new, replace_all)
    if not original.count(old):
        raise EditedLinesUnknown("tool_response.oldString does not occur in tool_response.originalFile")
    raise EditedLinesUnknown("the file as read does not have the line count the Edit's "
                             "replacements in tool_response.originalFile give")


def _lines_replacements_added(original, before_lines, after_lines, old, new, replace_all) -> set:
    """The after-Edit line numbers the replacements of old by new added. Replacements whose
    line spans share a line are diffed as one span, since diffing each alone would match one
    shared line against the other replacement's lines."""
    old_line_breaks, new_line_breaks = old.count("\n"), new.count("\n")
    spans = []
    offset = original.find(old)
    line, counted_to, replaced = 0, 0, 0
    while offset >= 0:
        line += original.count("\n", counted_to, offset)
        counted_to = offset
        new_line = line + replaced * (new_line_breaks - old_line_breaks)
        span = [line, line + old_line_breaks + 1, new_line, new_line + new_line_breaks + 1]
        if spans and line < spans[-1][1]:
            spans[-1][1], spans[-1][3] = span[1], span[3]
        else:
            spans.append(span)
        replaced += 1
        if not replace_all:
            break
        offset = original.find(old, offset + len(old))
    added = set()
    for before_start, before_end, after_start, after_end in spans:
        before_span, after_span = before_lines[before_start:before_end], after_lines[after_start:after_end]
        if len(before_span) * len(after_span) > LINE_DIFF_MAXIMUM_LINE_PAIRS:
            added.update(range(after_start, after_end))
            continue
        matcher = difflib.SequenceMatcher(None, before_span, after_span, autojunk=False)
        for tag, _, _, start, end in matcher.get_opcodes():
            if tag in ("replace", "insert"):
                added.update(range(after_start + start, after_start + end))
    return added


def markdown_broken_paragraph_line_ranges_filter_to_ranges_holding_edit_added_lines(broken_ranges, added_line_numbers) -> list:
    """The [start, end) ranges among broken_ranges that hold a line of added_line_numbers.
    The ranges do not overlap, so looking each of their lines up costs one pass over the file."""
    return [(start, end) for start, end in broken_ranges
            if any(line in added_line_numbers for line in range(start, end))]


def markdown_has_hard_wrapped_paragraph(text: str) -> bool:
    """True when the file holds a paragraph markdown_broken_paragraph_line_ranges reports.
    Raises MarkdownParserMissing when markdown-it-py is missing and installing it failed."""
    return bool(markdown_broken_paragraph_line_ranges(text))

def main() -> int:
    payload = json.loads(sys.stdin.read())
    if not isinstance(payload, dict):
        raise ValueError(f"the input on the hook's stdin is a JSON {type(payload).__name__}, not an object")
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if tool_name not in ("Edit", "Write") or not isinstance(tool_input, dict):
        return 0
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path.lower().endswith(MARKDOWN_SUFFIXES):
        return 0
    working_directory = payload.get("cwd")
    if not isinstance(working_directory, str) or not Path(working_directory).is_dir():
        return 0

    checks = _load_edited_file_path_within_checkout_root_and_git_check_ignore()
    located = checks.checkout_relative_path(file_path, Path(working_directory))
    if located is None:
        return 0
    root, relative_path = located
    try:
        trackable = checks.git_would_track(root, relative_path)
    except checks.GitCommandFailed as error:
        print(f"markdown-edit-hard-wrapped-paragraph-reminder: {error}, so no reminder check was made; "
              f"the {tool_name} itself succeeded.", file=sys.stderr)
        return 1
    if not trackable:
        return 0
    try:
        text = Path(file_path).read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return 0
    try:
        broken_ranges = markdown_broken_paragraph_line_ranges(text)
    except MarkdownParserMissing as error:
        print(parser_missing_message(error), file=sys.stderr)
        return 1
    if tool_name == "Edit" and broken_ranges:
        try:
            added = edit_added_line_numbers(payload.get("tool_response"), text)
        except EditedLinesUnknown as error:
            print(f"markdown-edit-hard-wrapped-paragraph-reminder: {error}, so no reminder check was made; "
                  f"the Edit itself succeeded.", file=sys.stderr)
            return 1
        broken_ranges = markdown_broken_paragraph_line_ranges_filter_to_ranges_holding_edit_added_lines(broken_ranges, added)
    if not broken_ranges:
        return 0

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": REMINDER_MESSAGE.format(path=relative_path),
    }}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"markdown-edit-hard-wrapped-paragraph-reminder: the text just written was not "
              f"checked for hard-wrapped paragraphs, because the hook failed; the write itself "
              f"succeeded: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
