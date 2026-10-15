#!/usr/bin/env python3
"""Report style-guide word hits in Markdown text just written by Edit or Write.

Use hookSpecificOutput.additionalContext: successful PostToolUse plain stdout reaches only the debug log.
Read cwd from the payload; CLAUDE_PROJECT_DIR can name a different checkout in a forked session.

Edit scans new_string alone, so an enclosing code fence may be invisible to the checker.
Skip walk documents because quoted user wording is not the writer's to change.

A fault, such as stdin that is not a JSON object, a checker that will not load or a git call that fails:
one line on stderr naming the fault, nothing on stdout, exit 1.
Claude Code records a PostToolUse exit 1 as a non-blocking error and keeps the write; exit 0 would read as "no words found"."""

import importlib.util
import json
import re
import sys
from pathlib import Path

MARKDOWN_SUFFIXES = (".md", ".markdown")
SKIPPED_DIRECTORY_PREFIXES = ("docs/walk/",)
HIT_LINES_LISTED_AT_MOST = 20

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
    """Return the checker module loaded by path; raises when it will not load."""
    specification = importlib.util.spec_from_file_location(
        "style_guide_word_checker",
        Path(__file__).resolve().with_name("style-guide-word-checker.py"))
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _load_edited_file_path_within_checkout_root_and_git_check_ignore():
    """Return the shared checkout and git-tracking helpers, loaded by path; raises when they will not load."""
    specification = importlib.util.spec_from_file_location(
        "edited_file_path_within_checkout_root_and_git_check_ignore_common",
        Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
        / "edited-file-path-within-checkout-root-and-git-check-ignore-common.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def hits_in_edit(checker, checks, root: Path, relative_path: str, tool_input: dict):
    new_string = tool_input.get("new_string")
    if not isinstance(new_string, str) or not new_string.strip():
        return []
    if not checks.git_would_track(root, relative_path):
        return []
    return checker.find_style_guide_word_hits_in_markdown(
        new_string, checker.APPLIES_TO_FILES, text_starts_document=False)


def words_around(text: str, offset: int, form: str) -> str:
    """Return the hit with bounded neighboring words and collapsed whitespace."""
    before = WORDS_BEFORE_PATTERN.search(
        text[max(0, offset - CONTEXT_CHARACTERS_BEFORE_HIT):offset]).group(0)
    after = WORDS_AFTER_PATTERN.match(text[offset + len(form):]).group(0)
    return " ".join((before + form + after).split())


def hits_in_write(checker, checks, root: Path, relative_path: str, tool_input: dict):
    content = tool_input.get("content")
    if not isinstance(content, str) or not content.strip():
        return []
    committed_lines = checks.file_lines_at_head_unless_git_ignores_file(root, relative_path)
    if committed_lines is None:
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
    payload = json.loads(sys.stdin.read())
    if not isinstance(payload, dict):
        raise ValueError(f"the payload Claude Code sent on stdin is a JSON "
                         f"{type(payload).__name__}, not an object")
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
    if relative_path.startswith(SKIPPED_DIRECTORY_PREFIXES):
        return 0

    checker = _load_style_guide_word_checker()
    if tool_name == "Edit":
        hits = hits_in_edit(checker, checks, root, relative_path, tool_input)
        edit_text = tool_input.get("new_string")
    else:
        hits = hits_in_write(checker, checks, root, relative_path, tool_input)
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
    except Exception as error:
        print(f"style-guide-word-checker-markdown-edit-hook: the text just written was not "
              f"checked for style-guide words, because the hook failed; the write itself "
              f"succeeded: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
