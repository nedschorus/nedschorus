#!/usr/bin/env python3
"""Remind the agent to keep Markdown paragraphs on one line, after an Edit or
Write leaves a Markdown file holding a paragraph broken across lines.

Use hookSpecificOutput.additionalContext: successful PostToolUse plain stdout reaches only the debug log.
Read cwd from the payload; CLAUDE_PROJECT_DIR can name a different checkout in a forked session.

The whole file is read from disk after the tool ran, for Edit as for Write, so an
Edit inside a fenced code block is judged with the fence visible.
The reminder carries no line numbers: the agent is to rejoin every broken
paragraph in the file, and to write later Markdown files the same way."""

import json
import re
import subprocess
import sys
from pathlib import Path

MARKDOWN_SUFFIXES = (".md", ".markdown")
GIT_TIMEOUT_SECONDS = 10

REMINDER_MESSAGE = (
    "markdown-edit-hard-wrapped-paragraph-reminder: {path} holds a paragraph or list item broken "
    "across lines. A line break inside a paragraph, list item or table row is extra "
    "whitespace to a reader whose editor wraps lines to the screen's width, and makes "
    "the text hard to edit.\n"
    "In {path}, join the lines of each broken paragraph and list item into one line.\n"
    "In every Markdown file you write from now on, write each paragraph, list item and "
    "table row as one line, however long; break lines only where Markdown needs a break."
)

# A fence may sit inside block quotes and may open on a list-item line.
FENCE_OPENING_PATTERN = re.compile(r"^[ >]*(?:(?:[-*+]|\d{1,9}[.)])[ \t]+)?(`{3,}|~{3,})(.*)$")
FENCE_LINE_PREFIX_PATTERN = re.compile(r"^[ >]*")
ORDERED_LIST_MARKER_PATTERN = re.compile(r"^\d{1,9}[.)]")
ATX_HEADING_PATTERN = re.compile(r"^#{1,6}(?:\s|$)")
SETEXT_UNDERLINE_PATTERN = re.compile(r"^ {0,3}(?:=+|-+)\s*$")
PROSE_FIRST_CHARACTER_PATTERN = re.compile(r"^[\w\"'(\u201c\u2018<]")
# CommonMark HTML block starts: a line opening one of these is HTML, not prose.
HTML_BLOCK_SPECIAL_START_PATTERN = re.compile(r"^<(?:!--|\?|![A-Za-z]|!\[CDATA\[)")
HTML_BLOCK_TAG_NAMES = frozenset("""
    address article aside base basefont blockquote body caption center col colgroup dd
    details dialog dir div dl dt fieldset figcaption figure footer form frame frameset
    h1 h2 h3 h4 h5 h6 head header hr html iframe legend li link main menu menuitem nav
    noframes ol optgroup option p param pre script section search source style summary
    table tbody td textarea tfoot th thead title tr track ul
""".split())
HTML_BLOCK_TAG_START_PATTERN = re.compile(r"^</?([A-Za-z][A-Za-z0-9-]*)(?=[\s/>]|$)")
# A complete open or closing tag standing alone on its line also starts an HTML block.
HTML_LONE_TAG_LINE_PATTERN = re.compile(
    r"^(?:<[A-Za-z][A-Za-z0-9-]*(?:\s+[A-Za-z_:][\w.:-]*(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s\"'=<>`]+))?)*\s*/?>"
    r"|</[A-Za-z][A-Za-z0-9-]*\s*>)\s*$")

def run_git(arguments, working_directory: Path):
    return subprocess.run(["git", *arguments], cwd=str(working_directory),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=GIT_TIMEOUT_SECONDS, check=False)


def enclosing_checkout_root(directory: Path):
    """Return the nearest checkout root at or above directory, or None."""
    for candidate in (directory, *directory.parents):
        git_marker = candidate / ".git"
        try:
            if git_marker.is_file() or (git_marker / "HEAD").is_file():
                return candidate
        except OSError:
            continue
    return None


def checkout_relative_path(file_path: str, working_directory: Path):
    """Return (checkout root, Git-relative path), or None outside the session checkout."""
    # Resolve both paths so macOS /tmp and /private/tmp compare equal.
    try:
        root = enclosing_checkout_root(working_directory.resolve())
        if root is None:
            return None
        return root, Path(file_path).resolve().relative_to(root).as_posix()
    except (ValueError, OSError, RuntimeError):
        return None


def git_would_track(root: Path, relative_path: str) -> bool:
    # check-ignore exits 0 for ignored, 1 for trackable, and 128 for failure; tracked files are never ignored.
    return run_git(["check-ignore", "-q", "--", relative_path], root).returncode == 1


def ends_in_hard_line_break(line: str) -> bool:
    # A backslash makes a hard break only when it is itself unescaped: a line
    # ending "a\\\\" ends in an escaped backslash, and "a\\ " is no break at all.
    if line.endswith("  ") or line.rstrip().lower().endswith(("<br>", "<br/>", "<br />")):
        return True
    return (len(line) - len(line.rstrip("\\"))) % 2 == 1


def starts_html_block(line: str) -> bool:
    if HTML_BLOCK_SPECIAL_START_PATTERN.match(line) or HTML_LONE_TAG_LINE_PATTERN.match(line):
        return True
    tag_match = HTML_BLOCK_TAG_START_PATTERN.match(line)
    return bool(tag_match) and tag_match.group(1).lower() in HTML_BLOCK_TAG_NAMES


def is_plain_prose(line: str) -> bool:
    """True for a line that can only be paragraph text: unindented, starting with a
    word character, a quotation mark, a parenthesis, or a "<" that opens no HTML
    block, and holding no table pipe."""
    if not PROSE_FIRST_CHARACTER_PATTERN.match(line) or "|" in line:
        return False
    if ORDERED_LIST_MARKER_PATTERN.match(line):
        return False
    if line.startswith("<"):
        return not starts_html_block(line)
    return True


def markdown_has_hard_wrapped_paragraph(text: str) -> bool:
    return first_hard_wrapped_paragraph_line_index(text) is not None


def first_hard_wrapped_paragraph_line_index(text: str):
    """Return the 0-based index of the first line that continues a paragraph begun
    on the line before it, or None.

    Only plain paragraphs count: a run of plain-prose lines (see is_plain_prose)
    that begins after a blank line, an ATX heading, a closed fence, front matter
    or the file's start. A run begun anywhere else continues some other block,
    such as a block quote, list item, HTML block or link reference definition, and
    is left alone; so is a run that a setext underline turns into a heading.
    List items wrapped onto an indented line are not detected, by choice: a missed
    reminder costs little, while a false one tells the agent to join lines that
    must stay apart."""
    lines = [line.rstrip("\r") for line in text.split("\n")]
    index = 0
    if lines and lines[0].rstrip() == "---":
        for closing_index in range(1, len(lines)):
            if lines[closing_index].rstrip() in ("---", "..."):
                index = closing_index + 1
                break

    fence_character = None
    fence_length = 0
    run_start = None
    # Whether a paragraph may begin on the current line.
    paragraph_may_begin = True

    def broken_line_in_run(run_end: int, terminating_line: str):
        if run_start is None or run_end - run_start < 2:
            return None
        if SETEXT_UNDERLINE_PATTERN.match(terminating_line):
            return None
        for line_index in range(run_start, run_end - 1):
            if not ends_in_hard_line_break(lines[line_index]):
                return line_index + 1
        return None

    while index < len(lines):
        line = lines[index]
        if fence_character is not None:
            body = FENCE_LINE_PREFIX_PATTERN.sub("", line).rstrip()
            if body.startswith(fence_character * fence_length) and set(body) == {fence_character}:
                fence_character = None
                paragraph_may_begin = True
            index += 1
            continue

        if is_plain_prose(line):
            if run_start is None and paragraph_may_begin:
                run_start = index
            paragraph_may_begin = False
            index += 1
            continue

        found = broken_line_in_run(index, line)
        if found is not None:
            return found
        run_start = None

        fence_match = FENCE_OPENING_PATTERN.match(line)
        if fence_match and not (fence_match.group(1)[0] == "`" and "`" in fence_match.group(2)):
            fence_character = fence_match.group(1)[0]
            fence_length = len(fence_match.group(1))
            paragraph_may_begin = False
        else:
            paragraph_may_begin = not line.strip() or bool(ATX_HEADING_PATTERN.match(line))
        index += 1
    return broken_line_in_run(len(lines), "")

def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0
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

    located = checkout_relative_path(file_path, Path(working_directory))
    if located is None:
        return 0
    root, relative_path = located
    if not git_would_track(root, relative_path):
        return 0
    try:
        text = Path(file_path).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return 0
    if not markdown_has_hard_wrapped_paragraph(text):
        return 0

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": REMINDER_MESSAGE.format(path=relative_path),
    }}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # A reminder must not turn a successful write into an apparent tool failure.
        sys.exit(0)
