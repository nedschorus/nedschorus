#!/usr/bin/env python3
"""Remind the agent to keep Markdown paragraphs on one line, after an Edit or
Write leaves a Markdown file holding a paragraph broken across lines.

Use hookSpecificOutput.additionalContext: successful PostToolUse plain stdout reaches only the debug log.
Read cwd from the payload; CLAUDE_PROJECT_DIR can name a different checkout in a forked session.

The whole file is read from disk after the tool ran, for Edit as for Write, so an
Edit inside a fenced code block is judged with the fence visible.
The reminder carries no line numbers: the agent is to rejoin every broken
paragraph in the file, and to write later Markdown files the same way.

Which lines form a paragraph is decided by markdown-it-py's CommonMark parser, not
by this file: a paragraph, in a list item or at the top level, is broken when its
inline content holds a soft line break. Without markdown-it-py installed, the hook
writes one line to stderr and exits 1, which Claude Code shows as a non-blocking
hook error, so a machine lacking the package is told the reminder is off there."""

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

# Front matter opens on the file's first line and closes on a line holding --- or ...
FRONT_MATTER_DELIMITER = "---"
FRONT_MATTER_CLOSERS = ("---", "...")
# Display math opens on a line starting with $$ that does not close on that line,
# such as $$ alone or $$\begin{aligned}, and closes on a later line ending in $$.
# CommonMark has no math, so without blanking these lines the parser reads display
# math as a paragraph.
DISPLAY_MATH_OPENER_PATTERN = re.compile(r"^ {0,3}\$\$")
DISPLAY_MATH_CLOSER_PATTERN = re.compile(r"\$\$[ \t]*$")
# A footnote definition, [^label]: text, is its own block to GitHub and Obsidian,
# although CommonMark reads consecutive definitions as one paragraph.
FOOTNOTE_DEFINITION_PATTERN = re.compile(r"^ {0,3}\[\^[^\]]+\]:")
# An inline <br> at a line's end is a hard break the author chose, like two trailing spaces.
LINE_END_BREAK_TAG_PATTERN = re.compile(r"^<br\s*/?>$", re.IGNORECASE)
# Blocks whose lines are never prose: the math and footnote passes leave them alone.
VERBATIM_BLOCK_TOKEN_TYPES = ("fence", "code_block", "html_block")
PARSER_MISSING_MESSAGE = (
    "markdown-edit-hard-wrapped-paragraph-reminder: markdown-it-py is not installed, "
    "so the hard-wrap reminder is off on this machine.")


class MarkdownParserMissing(Exception):
    """markdown-it-py cannot be imported."""

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


def markdown_parser():
    try:
        from markdown_it import MarkdownIt
    except ImportError as error:
        raise MarkdownParserMissing(str(error)) from error
    return MarkdownIt("commonmark").enable("table")


def verbatim_line_indexes(parser, text: str) -> set:
    """Return the indexes of lines inside fenced code, indented code and HTML blocks."""
    indexes = set()
    for token in parser.parse(text):
        if token.type in VERBATIM_BLOCK_TOKEN_TYPES and token.map:
            indexes.update(range(token.map[0], token.map[1]))
    return indexes


def lines_hidden_from_the_parser(parser, text: str) -> str:
    """Return text with front matter, display math and footnote definitions
    blanked, line count kept, so the parser's line numbers still name lines of
    the file. Math and footnote markers inside code or HTML blocks are left
    alone, so a $$ in a fenced example pairs with nothing."""
    lines = text.split("\n")
    if lines and lines[0].rstrip("\r").rstrip() == FRONT_MATTER_DELIMITER:
        for closing_index in range(1, len(lines)):
            if lines[closing_index].rstrip("\r").rstrip() in FRONT_MATTER_CLOSERS:
                for index in range(closing_index + 1):
                    lines[index] = ""
                break
    verbatim = verbatim_line_indexes(parser, "\n".join(lines))
    index = 0
    while index < len(lines):
        line = lines[index].rstrip("\r")
        if index in verbatim:
            index += 1
            continue
        if DISPLAY_MATH_OPENER_PATTERN.match(line) and not opener_closes_on_its_own_line(line):
            for closing_index in range(index + 1, len(lines)):
                if closing_index in verbatim:
                    continue
                if DISPLAY_MATH_CLOSER_PATTERN.search(lines[closing_index].rstrip("\r")):
                    for blanked in range(index, closing_index + 1):
                        lines[blanked] = ""
                    index = closing_index
                    break
            # An opener with no closer blanks nothing: the rest of the file stays visible.
        elif FOOTNOTE_DEFINITION_PATTERN.match(line):
            lines[index] = ""
            # A footnote's indented continuation lines belong to the footnote.
            while (index + 1 < len(lines) and index + 1 not in verbatim
                   and lines[index + 1][:1] in (" ", "\t") and lines[index + 1].strip()):
                index += 1
                lines[index] = ""
        index += 1
    return "\n".join(lines)


def opener_closes_on_its_own_line(line: str) -> bool:
    """True for $$x$$: a line that opens and closes display math holds no block."""
    after_opener = line.lstrip()[2:].rstrip()
    return len(after_opener) >= 2 and after_opener.endswith("$$")


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


def markdown_has_hard_wrapped_paragraph(text: str) -> bool:
    """True when a paragraph holds a soft line break the author did not choose.

    A paragraph is what the CommonMark parser calls one, at the top level or in a
    list item. A paragraph inside a block quote is left alone: a quote often keeps
    the line breaks of the text it quotes. Hard breaks, two trailing spaces, a
    trailing backslash or a trailing <br>, are breaks the author chose.
    Raises MarkdownParserMissing when markdown-it-py cannot be imported."""
    parser = markdown_parser()
    tokens = parser.parse(lines_hidden_from_the_parser(parser, text))
    block_quote_depth = 0
    for position, token in enumerate(tokens):
        if token.type == "blockquote_open":
            block_quote_depth += 1
        elif token.type == "blockquote_close":
            block_quote_depth -= 1
        elif (token.type == "inline" and block_quote_depth == 0
                and position > 0 and tokens[position - 1].type == "paragraph_open"):
            children = token.children or []
            for child_position, child in enumerate(children):
                if child.type == "softbreak" and counts_as_line_break(children, child_position):
                    return True
    return False

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
    try:
        broken = markdown_has_hard_wrapped_paragraph(text)
    except MarkdownParserMissing:
        print(PARSER_MISSING_MESSAGE, file=sys.stderr)
        return 1
    if not broken:
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
