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

FENCE_OPENING_PATTERN = re.compile(r"^\s*(?:(?:[-*+]|\d{1,9}[.)])\s+)?(`{3,}|~{3,})(.*)$")
LIST_ITEM_PATTERN = re.compile(r"^\s*(?:[-*+]|\d{1,9}[.)])(?:\s|$)")
HEADING_PATTERN = re.compile(r"^ {0,3}#{1,6}(?:\s|$)")
THEMATIC_BREAK_OR_SETEXT_PATTERN = re.compile(r"^ {0,3}(?:(?:[-*_=]\s*){3,}|=+|-+)\s*$")
TABLE_DELIMITER_ROW_PATTERN = re.compile(r"^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*$")
LINK_REFERENCE_DEFINITION_PATTERN = re.compile(r"^ {0,3}\[[^\]]+\]:\s")


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


def is_table_delimiter_row(line: str) -> bool:
    return "-" in line and ("|" in line) and bool(TABLE_DELIMITER_ROW_PATTERN.match(line))


def ends_in_hard_line_break(line: str) -> bool:
    return line.endswith("  ") or line.rstrip(" ").endswith("\\")


def markdown_has_hard_wrapped_paragraph(text: str) -> bool:
    return first_hard_wrapped_paragraph_line_index(text) is not None


def first_hard_wrapped_paragraph_line_index(text: str):
    """Return the 0-based index of the first prose line that continues the paragraph
    or list item on the line before it, or None.

    A prose line is a non-blank line outside front matter, fenced and indented code
    blocks, tables, block quotes and HTML, that is not a heading, list item,
    thematic break, setext underline or link reference definition."""
    lines = text.split("\n")
    index = 0
    if lines and lines[0].rstrip() == "---":
        for closing_index in range(1, len(lines)):
            if lines[closing_index].rstrip() in ("---", "..."):
                index = closing_index + 1
                break

    fence_character = None
    fence_length = 0
    inside_html_comment = False
    inside_table = False
    inside_indented_code = False
    list_open = False
    # What the previous line was, for deciding whether the current line continues it:
    # "blank", "prose", "list item", or "other" (a line no paragraph can continue).
    previous_kind = "blank"
    previous_line = ""

    while index < len(lines):
        line = lines[index].rstrip("\r")
        index += 1
        stripped = line.strip()

        if fence_character is not None:
            if (stripped.startswith(fence_character * fence_length)
                    and set(stripped) == {fence_character}):
                fence_character = None
            previous_kind, previous_line = "other", line
            continue
        if inside_html_comment:
            if "-->" in line:
                inside_html_comment = False
            previous_kind, previous_line = "other", line
            continue
        if not stripped:
            inside_table = False
            previous_kind, previous_line = "blank", line
            continue
        if inside_indented_code:
            if line.startswith(("    ", "\t")):
                previous_kind, previous_line = "other", line
                continue
            inside_indented_code = False
        if inside_table:
            previous_kind, previous_line = "other", line
            continue

        fence_match = FENCE_OPENING_PATTERN.match(line)
        if fence_match and not (fence_match.group(1)[0] == "`" and "`" in fence_match.group(2)):
            fence_character = fence_match.group(1)[0]
            fence_length = len(fence_match.group(1))
            list_open = list_open or bool(LIST_ITEM_PATTERN.match(line))
            previous_kind, previous_line = "other", line
            continue
        if previous_kind == "blank" and not list_open and line.startswith(("    ", "\t")):
            inside_indented_code = True
            previous_kind, previous_line = "other", line
            continue
        if index < len(lines) and is_table_delimiter_row(lines[index]) and "|" in line:
            inside_table = True
            previous_kind, previous_line = "other", line
            continue
        if stripped.startswith("<"):
            if stripped.startswith("<!--") and "-->" not in stripped:
                inside_html_comment = True
            previous_kind, previous_line = "other", line
            continue
        if (stripped.startswith((">", "|")) or HEADING_PATTERN.match(line)
                or THEMATIC_BREAK_OR_SETEXT_PATTERN.match(line)
                or LINK_REFERENCE_DEFINITION_PATTERN.match(line)):
            if not line.startswith((" ", "\t")):
                list_open = False
            previous_kind, previous_line = "other", line
            continue
        if LIST_ITEM_PATTERN.match(line):
            list_open = True
            previous_kind, previous_line = "list item", line
            continue

        if previous_kind in ("prose", "list item") and not ends_in_hard_line_break(previous_line):
            return index - 1
        if not line.startswith((" ", "\t")):
            list_open = False
        previous_kind, previous_line = "prose", line
    return None


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
