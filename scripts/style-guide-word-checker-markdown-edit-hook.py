#!/usr/bin/env python3
"""Report style-guide word hits in Markdown text just written by Edit or Write.

Use hookSpecificOutput.additionalContext: successful PostToolUse plain stdout reaches only the debug log.
Read cwd from the payload; CLAUDE_PROJECT_DIR can name a different checkout in a forked session.

Edit scans new_string alone, so an enclosing code fence may be invisible to the checker.
Skip walk documents because quoted user wording is not the writer's to change."""

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

MARKDOWN_SUFFIXES = (".md", ".markdown")
SKIPPED_DIRECTORY_PREFIXES = ("docs/walk/",)
HIT_LINES_LISTED_AT_MOST = 20
GIT_TIMEOUT_SECONDS = 10

REPORT_OPENING_LINES = (
    "style-guide-word-checker: the text just written to {path} uses {count} word(s) "
    "from the project's list of words to avoid. Each listed word either carries more "
    "than one meaning in this project, so a reader cannot tell which meaning the writer "
    "intended, or is replaced in this project by another word.",
    "Judge each hit below in its sentence: only the writer knows which meaning was "
    "intended.",
    "Where the word carries one of the project meanings listed, replace the word with "
    "the name given for that meaning.",
    "Where the word has its ordinary English meaning, leave the word as written.",
)
HIT_LINE = '{path}:{line}: "{form}": {names}'
EDIT_HIT_LINE = '{path}, in "{context}": "{form}": {names}'
CONTEXT_WORDS_EACH_SIDE = 4
# \Z excludes the final-newline match allowed by $, which would join context across a line break.
WORDS_BEFORE_PATTERN = re.compile(r"(?:\S+\s+){0,%d}\S*\Z" % CONTEXT_WORDS_EACH_SIDE)
# Bound the backward search: trying every start position is quadratic on long text without whitespace.
CONTEXT_CHARACTERS_BEFORE_HIT = 1000
WORDS_AFTER_PATTERN = re.compile(r"\S*(?:\s+\S+){0,%d}" % CONTEXT_WORDS_EACH_SIDE)
MORE_HITS_LINE = ("{count} more hit(s) in the same text are not listed: reread the rest "
                  "of the text just written for the same words.")


def _load_style_guide_word_checker():
    """Return the checker module loaded by path, or None on failure."""
    try:
        specification = importlib.util.spec_from_file_location(
            "style_guide_word_checker",
            Path(__file__).resolve().with_name("style-guide-word-checker.py"))
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        return module
    except Exception:
        return None


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


def hits_in_edit(checker, root: Path, relative_path: str, tool_input: dict):
    new_string = tool_input.get("new_string")
    if not isinstance(new_string, str) or not new_string.strip():
        return []
    if not git_would_track(root, relative_path):
        return []
    return checker.find_style_guide_word_hits_in_markdown(new_string, checker.APPLIES_TO_FILES)


def words_around(text: str, offset: int, form: str) -> str:
    """Return the hit with bounded neighboring words and collapsed whitespace."""
    before = WORDS_BEFORE_PATTERN.search(
        text[max(0, offset - CONTEXT_CHARACTERS_BEFORE_HIT):offset]).group(0)
    after = WORDS_AFTER_PATTERN.match(text[offset + len(form):]).group(0)
    return " ".join((before + form + after).split())


def hits_in_write(checker, root: Path, relative_path: str, tool_input: dict):
    content = tool_input.get("content")
    if not isinstance(content, str) or not content.strip():
        return []
    committed = run_git(["show", "HEAD:" + relative_path], root)
    if committed.returncode == 0:
        committed_lines = set(line.rstrip() for line in committed.stdout.split("\n"))
    elif git_would_track(root, relative_path):
        committed_lines = set()
    else:
        return []
    new_line_numbers = set(
        index + 1 for index, line in enumerate(content.split("\n"))
        if line.rstrip() not in committed_lines)
    return checker.find_style_guide_word_hits_in_markdown(
        content, checker.APPLIES_TO_FILES, new_line_numbers)


def word_report(relative_path: str, hits, edit_text=None) -> str:
    """Format distinct hits in order, using Edit context or Write line numbers."""
    seen = set()
    distinct_hits = []
    for hit in hits:
        key = (hit.line_number, hit.form)
        if key not in seen:
            seen.add(key)
            distinct_hits.append(hit)
    lines = [line.format(path=relative_path, count=len(distinct_hits))
             for line in REPORT_OPENING_LINES]
    for hit in distinct_hits[:HIT_LINES_LISTED_AT_MOST]:
        if edit_text is None:
            lines.append(HIT_LINE.format(path=relative_path, line=hit.line_number,
                                         form=hit.form, names=hit.entry.names_to_choose_from))
        else:
            lines.append(EDIT_HIT_LINE.format(
                path=relative_path, form=hit.form, names=hit.entry.names_to_choose_from,
                context=words_around(edit_text, hit.offset, hit.form)))
    if len(distinct_hits) > HIT_LINES_LISTED_AT_MOST:
        lines.append(MORE_HITS_LINE.format(
            count=len(distinct_hits) - HIT_LINES_LISTED_AT_MOST))
    return "\n".join(lines)


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
    if relative_path.startswith(SKIPPED_DIRECTORY_PREFIXES):
        return 0

    checker = _load_style_guide_word_checker()
    if checker is None:
        return 0
    if tool_name == "Edit":
        hits = hits_in_edit(checker, root, relative_path, tool_input)
        edit_text = tool_input.get("new_string")
    else:
        hits = hits_in_write(checker, root, relative_path, tool_input)
        edit_text = None
    if not hits:
        return 0

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": word_report(relative_path, hits, edit_text),
    }}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # A word report must not turn a successful write into an apparent tool failure.
        sys.exit(0)
