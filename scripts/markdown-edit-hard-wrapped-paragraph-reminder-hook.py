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
hook error, so a machine lacking the package is told the reminder is off there.
Install it with the python3 the hooks run, the one `command -v python3` finds in
the shell Claude Code runs hooks from:
python3 -m pip install --user --break-system-packages markdown-it-py

A file holding display math ($$) or a footnote definition ([^label]:) gets no
reminder at all: CommonMark reads both as paragraphs, and judging their line
breaks needs rules this hook does not carry, so it stays silent rather than tell
an agent to join lines that must stay apart."""

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
# A line whose text, past indentation and list or quote markers, starts with $$
# or a footnote label makes the whole file one this hook stays silent on.
LINE_PREFIX_MARKERS_PATTERN = re.compile(r"^(?:[ \t>]*(?:[-*+]|\d{1,9}[.)])(?=[ \t]))*[ \t>]*")
UNJUDGED_BLOCK_START_PATTERN = re.compile(r"\$\$|\[\^[^\]]+\]:")
# An inline <br> at a line's end is a hard break the author chose, like two trailing spaces.
LINE_END_BREAK_TAG_PATTERN = re.compile(r"^<br\s*/?>$", re.IGNORECASE)
PARSER_MISSING_MESSAGE = (
    "markdown-edit-hard-wrapped-paragraph-reminder: markdown-it-py is not installed, "
    "so the hard-wrap reminder is off on this machine.")


class MarkdownParserMissing(Exception):
    """markdown-it-py cannot be imported."""


class GitIgnoreCheckFailed(Exception):
    """git check-ignore could not say whether the file is ignored."""

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
    """Return whether git would track relative_path; raise GitIgnoreCheckFailed when git cannot say."""
    # check-ignore exits 0 for ignored, 1 for trackable, and 128 for failure; tracked files are never ignored.
    try:
        completed = run_git(["check-ignore", "-q", "--", relative_path], root)
    except (OSError, subprocess.SubprocessError) as error:
        raise GitIgnoreCheckFailed(f"git check-ignore could not run: {error}") from error
    if completed.returncode == 1:
        return True
    if completed.returncode == 0:
        return False
    detail = completed.stderr.strip().splitlines()
    raise GitIgnoreCheckFailed(
        f"git check-ignore exited {completed.returncode}" + (f": {detail[0]}" if detail else ""))


def markdown_parser():
    try:
        from markdown_it import MarkdownIt
    except ImportError as error:
        raise MarkdownParserMissing(str(error)) from error
    return MarkdownIt("commonmark").enable("table")


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


def markdown_has_hard_wrapped_paragraph(text: str) -> bool:
    """True when a paragraph holds a soft line break the author did not choose.

    A paragraph is what the CommonMark parser calls one, at the top level or in a
    list item. A paragraph inside a block quote is left alone: a quote often keeps
    the line breaks of the text it quotes. Hard breaks, two trailing spaces, a
    trailing backslash or a trailing <br>, are breaks the author chose. A file
    holding display math or a footnote definition is never reported.
    Raises MarkdownParserMissing when markdown-it-py cannot be imported."""
    parser = markdown_parser()
    if holds_math_or_footnote_definition(text):
        return False
    tokens = parser.parse(front_matter_blanked(text))
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
    try:
        trackable = git_would_track(root, relative_path)
    except GitIgnoreCheckFailed as error:
        print(f"markdown-edit-hard-wrapped-paragraph-reminder: {error}, so no reminder check was made.",
              file=sys.stderr)
        return 1
    if not trackable:
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
