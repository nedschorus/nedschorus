#!/usr/bin/env python3
"""Tests for markdown-edit-hard-wrapped-paragraph-reminder-hook.py.

Run: python3 scripts/markdown-edit-hard-wrapped-paragraph-reminder-hook-test.py
Prints one line per case and exits non-zero if any case fails.

The detector's cases call markdown_has_hard_wrapped_paragraph directly. The hook's
cases run the hook as Claude Code does, as a subprocess reading a PostToolUse
payload on stdin, against a throwaway repository under a temporary directory
with a .gitignore that ignores one directory.

Every git call, the hook's included, runs with the variables that redirect git
(GIT_DIR and its kin) removed, and the scratch repository is checked to be a
repository at its own path before any case writes to it.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Before anything runs git: a run started with GIT_DIR set must still build this
# suite's scratch repository where the suite says.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

HOOK_PATH = Path(__file__).with_name("markdown-edit-hard-wrapped-paragraph-reminder-hook.py")

GIT_REDIRECTING_VARIABLES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                             "GIT_OBJECT_DIRECTORY", "GIT_COMMON_DIR",
                             "GIT_ALTERNATE_OBJECT_DIRECTORIES")
CLEAN_ENVIRONMENT = {name: value for name, value in os.environ.items()
                     if name not in GIT_REDIRECTING_VARIABLES}

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


specification = importlib.util.spec_from_file_location(
    "markdown_edit_hard_wrapped_paragraph_reminder_hook", str(HOOK_PATH))
hook = importlib.util.module_from_spec(specification)
specification.loader.exec_module(hook)

# ---------------------------------------------------------------------------
# The detector, called directly.
# ---------------------------------------------------------------------------

BROKEN_CASES = (
    ("a prose paragraph broken across two lines",
     "# Title\n\nThe first half of a sentence\nand the second half.\n"),
    ("a list item continued onto an indented next line",
     "- The first half of an item\n  and the second half.\n"),
    ("a list item continued onto an unindented next line",
     "1. The first half of an item\nand the second half.\n"),
    ("a broken paragraph after a closed code fence",
     "```\ncode\n```\n\nOne line\nand another.\n"),
    ("a broken paragraph after front matter",
     "---\ntitle: x\n---\n\nOne line\nand another.\n"),
    ("a line ending in an escaped backslash is not a hard break",
     "One line ending in a backslash \\\\\nand another.\n"),
    ("a line ending in a backslash and one space is not a hard break",
     "One line ending in a backslash \\ \nand another.\n"),
    ("a list closed by an unindented paragraph that is itself broken",
     "- item\n\nParagraph one\ncontinued here.\n"),
    ("a broken list-item paragraph after a fence opened on a list-item line",
     "1. ```py\n   x = 1\n   ```\n\n    The item's paragraph, first half\n    and its second half.\n"),
    ("a backtick in a fence's info string makes no fence",
     "```a`b\nline one\nline two\n"),
)
for case_name, text in BROKEN_CASES:
    check(f"fires: {case_name}", hook.markdown_has_hard_wrapped_paragraph(text) is True)

CLEAN_CASES = (
    ("one-line paragraphs separated by blank lines",
     "# Title\n\nA whole paragraph on one line.\n\nAnother whole paragraph.\n"),
    ("a list of one-line items, nested items included",
     "Intro paragraph.\n\n- first item\n- second item\n  - nested item\n1. numbered\n2) numbered\n"),
    ("a table, with and without outer pipes",
     "| a | b |\n|---|---|\n| 1 | 2 |\n\na | b\n--|--\n1 | 2\n"),
    ("a fenced code block with backticks, tildes and a list-item fence",
     "```sh\nline one\nline two\n```\n\n~~~\nx\ny\n~~~\n\n- step\n  ```\n  a\n  b\n  ```\n"),
    ("a fence indented four spaces inside a list item",
     "1. step\n\n    ```toml\n    [tool]\n    key = 1\n    ```\n"),
    ("front matter of several lines",
     "---\ntitle: x\ndescription: y\n---\n\nOne paragraph.\n"),
    ("headings directly followed by a paragraph line",
     "# Title\nOne paragraph.\n## Section\nAnother paragraph.\n"),
    ("a setext heading", "Title\n=====\n\nSubtitle\n--------\n"),
    ("block quote lines", "> quoted first line\n> quoted second line\n"),
    ("HTML lines and a comment over several lines",
     "<details>\n<summary>x</summary>\n</details>\n\n<!-- a comment\nover lines\n-->\n"),
    ("an indented code block of three lines after a blank line",
     "Intro paragraph.\n\n    code line one\n    code line two\n    code line three\n"),
    ("an indented code block inside a list item",
     "- item\n\n      code1\n      code2\n      code3\n"),
    ("an indented code block right after a heading",
     "# H\n    code1\n    code2\n    code3\n"),
    ("an indented code block after a list closed by a one-line paragraph",
     "- item\n\nA closing paragraph.\n\n    code1\n    code2\n    code3\n"),
    ("text lines inside a multi-line HTML block",
     "<div>\nfirst text line\nsecond text line\n</div>\n\n<details>\nhidden first\nhidden second\n</details>\n"),
    ("a pre block with a blank line inside",
     "<pre>\nline one\n\nline two\nline three\n</pre>\n"),
    ("a link reference definition with a title on later lines",
     "[a]: https://example.com\n'a title\nover two lines'\n"),
    ("lazy continuation lines of a block quote",
     "> First line\nsecond line\nthird line\n"),
    ("a setext heading of several lines",
     "A heading\ncontinued\n---\n\nAnother heading\nover lines\n===\n"),
    ("a hard line break with two trailing spaces or a backslash",
     "First line  \nsecond line\n\nThird line\\\nfourth line\n"),
    ("link reference definitions", "[a]: https://example.com\n[b]: https://example.org\n"),
)
for case_name, text in CLEAN_CASES:
    check(f"silent: {case_name}", hook.markdown_has_hard_wrapped_paragraph(text) is False)

# ---------------------------------------------------------------------------
# The hook, run as a subprocess against a scratch repository.
# ---------------------------------------------------------------------------


def git(arguments, cwd):
    return subprocess.run(["git", *arguments], cwd=str(cwd), capture_output=True,
                          text=True, check=False, env=CLEAN_ENVIRONMENT)


def run_hook(payload):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run([sys.executable, str(HOOK_PATH)], input=text,
                          capture_output=True, text=True, check=False, env=CLEAN_ENVIRONMENT)


def payload_for(cwd, tool_name, file_path, tool_input_extra):
    tool_input = {"file_path": str(file_path), **tool_input_extra}
    return {"session_id": "markdown-edit-hard-wrapped-paragraph-reminder-test-session",
            "transcript_path": "/dev/null", "cwd": str(cwd),
            "permission_mode": "acceptEdits", "hook_event_name": "PostToolUse",
            "tool_name": tool_name, "tool_input": tool_input, "tool_response": {}}


def write_then_run(cwd, file_path, content):
    """What the Write tool leaves behind, then the hook that follows it."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return run_hook(payload_for(cwd, "Write", file_path, {"content": content}))


def silent(result):
    return result.returncode == 0 and result.stdout.strip() == "" and result.stderr.strip() == ""


def agent_text(result):
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        return ""
    if not isinstance(parsed, dict):
        return ""
    return parsed.get("hookSpecificOutput", {}).get("additionalContext", "")


BROKEN_TEXT = "# Notes\n\nThe first half of a sentence\nand the second half.\n"
CLEAN_TEXT = "# Notes\n\nA whole paragraph on one line.\n"

with tempfile.TemporaryDirectory() as temporary_directory:
    tmp = Path(temporary_directory)
    checkout = tmp / "checkout"
    checkout.mkdir()
    git(["init", "-q", "-b", "main"], checkout)
    toplevel = git(["rev-parse", "--show-toplevel"], checkout).stdout.strip()
    if not toplevel or Path(toplevel).resolve() != checkout.resolve():
        print(f"ABORT: the scratch repository is not a repository at {checkout} "
              f"(git answered {toplevel!r}); no case was run against the hook")
        sys.exit(1)
    (checkout / ".gitignore").write_text("ignored-notes/\n", encoding="utf-8")

    result = write_then_run(checkout, checkout / "docs" / "broken.md", BROKEN_TEXT)
    reply = json.loads(result.stdout) if result.stdout.strip() else {}
    text = agent_text(result)
    check("a Write leaving a broken paragraph gets one PostToolUse reminder, exit 0",
          result.returncode == 0 and result.stderr == ""
          and reply.get("hookSpecificOutput", {}).get("hookEventName") == "PostToolUse"
          and text.startswith("markdown-edit-hard-wrapped-paragraph-reminder: docs/broken.md holds")
          and "every Markdown file you write from now on" in text,
          result.stdout + result.stderr)
    check("the reminder names no line number",
          ":3" not in text and "line 3" not in text, text)

    edited_file = checkout / "docs" / "edited.md"
    edited_file.write_text(BROKEN_TEXT, encoding="utf-8")
    result = run_hook(payload_for(checkout, "Edit", edited_file,
                                  {"old_string": "x", "new_string": "Notes",
                                   "replace_all": False}))
    check("an Edit is judged on the whole file on disk, not its new_string",
          agent_text(result).startswith("markdown-edit-hard-wrapped-paragraph-reminder: docs/edited.md"),
          result.stdout + result.stderr)

    result = write_then_run(checkout, checkout / "docs" / "clean.md", CLEAN_TEXT)
    check("a Write leaving no broken paragraph outputs nothing", silent(result),
          result.stdout + result.stderr)

    result = write_then_run(checkout, checkout / "notes.markdown", BROKEN_TEXT)
    check("a .markdown file is checked too",
          agent_text(result).startswith("markdown-edit-hard-wrapped-paragraph-reminder: notes.markdown"),
          result.stdout + result.stderr)

    result = write_then_run(checkout, checkout / "scripts" / "tool.txt",
                            "The first half of a sentence\nand the second half.\n")
    check("a non-Markdown file is silent", silent(result), result.stdout + result.stderr)

    result = write_then_run(checkout, checkout / "ignored-notes" / "scratch.md", BROKEN_TEXT)
    check("a git-ignored Markdown file is silent", silent(result),
          result.stdout + result.stderr)

    outside_file = tmp / "outside" / "elsewhere.md"
    result = write_then_run(checkout, outside_file, BROKEN_TEXT)
    check("a Markdown file outside the session's checkout is silent", silent(result),
          result.stdout + result.stderr)

    undecodable_file = checkout / "docs" / "latin1.md"
    undecodable_file.write_bytes(b"One line \xe9\nand another.\n")
    result = run_hook(payload_for(checkout, "Write", undecodable_file, {"content": ""}))
    check("a file that is not UTF-8 is silent", silent(result), result.stdout + result.stderr)

    result = run_hook("{not json")
    check("a payload that does not parse as JSON is silent", silent(result),
          result.stdout + result.stderr)

    result = run_hook("[1, 2]")
    check("a payload that is not a JSON object is silent", silent(result),
          result.stdout + result.stderr)

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
