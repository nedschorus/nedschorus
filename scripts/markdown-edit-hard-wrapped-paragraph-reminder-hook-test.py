#!/usr/bin/env python3
"""Tests for markdown-edit-hard-wrapped-paragraph-reminder-hook.py.

Run: python3 scripts/markdown-edit-hard-wrapped-paragraph-reminder-hook-test.py
Prints one line per case and exits non-zero if any case fails.

The detector's cases call markdown_has_hard_wrapped_paragraph directly. The
detector needs markdown-it-py; without it the suite fails, naming the command that
installs the package, and one case checks that the hook reports the missing
package as a non-blocking error when the package fails to import. The hook's
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
    ("a broken paragraph directly after an ATX heading",
     "# Title\nThe first half\nand the second half.\n"),
    ("a broken paragraph at the start of the file",
     "The first half\nand the second half.\n"),
    ("a broken paragraph after a closed code fence",
     "```\ncode\n```\nOne line\nand another.\n"),
    ("a broken paragraph after front matter",
     "---\ntitle: x\n---\n\nOne line\nand another.\n"),
    ("a line ending in an escaped backslash is not a hard break",
     "One line ending in a backslash \\\\\nand another.\n"),
    ("a line ending in a backslash and one space is not a hard break",
     "One line ending in a backslash \\ \nand another.\n"),
    ("a list closed by an unindented paragraph that is itself broken",
     "- item\n\nParagraph one\ncontinued here.\n"),
    ("a backtick in a fence's info string makes no fence",
     "```a`b\n\nline one\nline two\n"),
    ("a line opening with a tag that starts no HTML block is prose (finding: <seat>)",
     "Para first half\n<seat> is named here\nthird line\n"),
    ("a broken paragraph that a fence follows, the fence holding ---",
     "One line\nand another.\n```\n---\n```\n"),
    ("a broken paragraph followed by a heading whose next line is ---",
     "First line\nsecond line\n# Heading\n---\n"),
    ("a paragraph line starting with a digit that is no list marker",
     "2026 was the year\nof the move.\n"),
    ("a paragraph line starting with a quotation mark",
     "\"Quoted opening,\" he said,\nand went on.\n"),
    ("a closing fence inside a block quote closes the fence",
     "> ```\n> code\n> ```\n\nOne line\nand another.\n"),
    ("a third paragraph line after a hard break",
     "First line  \nsecond line\nthird line\n"),
    ("a broken paragraph at the end of a file with no final newline",
     "One line\nand another."),
    ("a broken paragraph after a pre block that opens and closes on one line",
     "<pre></pre>\nOne line\nand another.\n"),
    ("a broken paragraph after a closed HTML comment",
     "<!--\nx\n-->\nOne line\nand another.\n"),
    ("a broken paragraph after a ___ thematic break",
     "___\nOne line\nand another.\n"),
    ("a broken paragraph after a _ _ _ thematic break",
     "_ _ _\nOne line\nand another.\n"),
    ("a broken paragraph that an HTML comment interrupts",
     "One line\nand another.\n<!-- note -->\n"),
    ("a broken paragraph after an HTML block ends at its blank line",
     "<div>\n<!-- note -->\n\nOne line\nand another.\n"),
    ("a fence line indented by a tab inside a fence does not close it, so the fence closes later",
     "```\n\t```\ncode\n```\nOne line\nand another.\n"),
    # Cases the parser reads as wrapped paragraphs although an earlier hand
    # detector stayed silent on them: CommonMark makes each one a paragraph.
    ("a list item wrapped onto an indented line",
     "- The first half of an item\n  and the second half.\n"),
    ("a list item continued onto an unindented line",
     "1. The first half of an item\nand the second half.\n"),
    ("unindented lines after a fence opened on a list-item line leave the list item",
     "1. ```py\nx = 1\ny = 2\n   ```\n"),
    ("a blank line ends a block quote, so the lines after it are a paragraph",
     "> ```\n\nline a\nline b\n> ```\n"),
    ("lines after a blank leave a list item whose fence they were meant for",
     "1. ```py\n\nx = 1\ny = 2\n```\n"),
    ("emphasis on two lines is one paragraph",
     "*emphasised*\n**bold**\n"),
    ("two image lines are one paragraph",
     "![image](x.png)\n![other](y.png)\n"),
    ("pipe lines with no delimiter row are a paragraph, not a table",
     "a | b\nc | d\n"),
    # This round's findings and notes.
    ("a fence opened on a ten-item list line closes at four spaces (round 6, item 1)",
     "10. ```sh\n    x\n    ```\n\nPara a\npara b\n"),
    ("a fence opened on a nested list-item line closes (round 6, item 1)",
     "- outer\n  - ```sh\n    x\n    ```\n\nPara a\npara b\n"),
    ("a fence opened on a list line with a wide marker gap closes (round 6, item 1)",
     "-   ```\n    x\n    ```\n\nPara a\npara b\n"),
    # A $ or a footnote reference is not display math or a footnote definition.
    ("a dollar amount mid-paragraph", "One line costs $5\nand another.\n"),
    ("a line starting with one $ is not display math",
     "$ git status prints the branch\nand the files it changed.\n"),
    ("$$ in the middle of a line", "One line costs $$ more\nand another.\n"),
    ("a footnote reference, not a definition", "See the note[^a] here\nand more.\n"),
    ("a footnote label with no colon", "[^a] is a label\nand more.\n"),
)
try:
    import markdown_it  # noqa: F401
    PARSER_AVAILABLE = True
except ImportError:
    PARSER_AVAILABLE = False
PARSER_INSTALL_COMMAND = ("python3 -m pip install --user --break-system-packages markdown-it-py, "
                          "run with the python3 that `command -v python3` finds in the shell Claude Code runs hooks from")
check("markdown-it-py is installed, so the reminder works on this machine",
      PARSER_AVAILABLE, f"install it with: {PARSER_INSTALL_COMMAND}")

if PARSER_AVAILABLE:
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
    ("a fence line with an info string does not close an open fence",
     "```\n```py\nline one\nline two\n```\n"),
    ("front matter closed by ... is skipped",
     "---\ntitle: x\n\nkey: a\nkey: b\n...\n"),
    ("a fence longer than three closes only on a fence as long",
     "````\n```\nline one\nline two\n````\n"),
    ("a fence closed by the other fence character stays open",
     "~~~\n```\nline one\nline two\n~~~\n"),
    ("front matter of several lines",
     "---\ntitle: x\ndescription: y\n---\n\nOne paragraph.\n"),
    ("headings directly followed by a paragraph line",
     "# Title\nOne paragraph.\n## Section\nAnother paragraph.\n"),
    ("a setext heading", "Title\n=====\n\nSubtitle\n--------\n"),
    ("a setext heading of several lines",
     "A heading\ncontinued\n---\n\nAnother heading\nover lines\n===\n"),
    ("block quote lines", "> quoted first line\n> quoted second line\n"),
    ("lazy continuation lines of a block quote",
     "> First line\nsecond line\nthird line\n"),
    ("HTML lines and a comment over several lines",
     "<details>\n<summary>x</summary>\n</details>\n\n<!-- a comment\nover lines\n-->\n"),
    ("text lines inside a multi-line HTML block",
     "<div>\nfirst text line\nsecond text line\n</div>\n\n<details>\nhidden first\nhidden second\n</details>\n"),
    ("a lone custom tag line opens an HTML block",
     "<my-widget>\nfirst text line\nsecond text line\n"),
    ("an indented code block of three lines after a blank line",
     "Intro paragraph.\n\n    code line one\n    code line two\n    code line three\n"),
    ("an indented code block inside a list item",
     "- item\n\n      code1\n      code2\n      code3\n"),
    ("an indented code block right after a heading",
     "# H\n    code1\n    code2\n    code3\n"),
    ("an indented code block after a list closed by a fence (finding 4)",
     "- item\n```\nx\n```\n\n    code1\n    code2\n"),
    ("a fence right after a block quote line (findings 2 and 6)",
     "> quote\n~~~\n\ncode1\ncode2\n~~~\n"),
    ("a fence right after a link reference definition (finding 7)",
     "[a]: https://example.com\n~~~\n\ncode1\ncode2\n~~~\n"),
    ("a fence after a one-line pre block (finding 8)",
     "<pre></pre>\n~~~\ncode1\ncode2\n~~~\n"),
    ("a fence after an autolink line (finding 8)",
     "<https://example.com>\n~~~\ncode1\ncode2\n~~~\n"),
    ("a fence inside a block quote",
     "> ~~~\n> PR one\n> PR two\n> ~~~\n"),
    ("a link reference definition with a title on later lines",
     "[a]: https://example.com\n'a title\nover two lines'\n"),
    ("a hard line break with two trailing spaces, a backslash or <br>",
     "First line  \nsecond line\n\nThird line\\\nfourth line\n\nFifth<br>\nsixth\n"),
    ("link reference definitions", "[a]: https://example.com\n[b]: https://example.org\n"),
    ("a pre block with a blank line inside",
     "<pre>\nline one\n\nline two\nline three\n</pre>\n"),
    ("a pre block whose first inner line is blank",
     "<pre>\n\nfirst line\nsecond line\n</pre>\n"),
    ("an HTML comment with a blank line inside",
     "<!--\nfirst\n\nsecond line\nthird line\n-->\n"),
    ("a script block with a blank line inside",
     "<script>\nvar a\n\nvar b\nvar c\n</script>\n"),
    ("display math between $$ lines with a blank line inside",
     "$$\nx = 1\n\ny = 2\nz = 3\n$$\n"),
    ("a one-line paragraph either side of a ___ thematic break",
     "First paragraph.\n___\nSecond paragraph.\n"),
    ("a line opening a p tag starts an HTML block",
     "<p>Para one\nline two\n"),
    ("a quoted fence line inside an ordinary fence does not close it",
     "```\n> ```\nline one\nline two\n```\n"),
    ("a fence line in an indented code block opens no fence",
     "Intro.\n\n    ```\n    x\n\n```\nfirst code line\nsecond code line\n```\n"),
    ("text after a one-line comment inside a div block (Codex finding 1)",
     "<div>\n<!-- note -->\nfirst text line\nsecond text line\n</div>\n"),
    ("text after a ___ inside a div block",
     "<div>\n___\nfirst text line\nsecond text line\n</div>\n"),
    ("a tab-indented fence line inside a fence does not close it (Codex finding 2)",
     "```\n\t```\nfirst code line\nsecond code line\n```\n"),
    ("a fence line indented four spaces inside a fence does not close it",
     "```\n    ```\nfirst code line\nsecond code line\n```\n"),
    ("a line holding $$ among other text does not close display math",
     "$$\na $$ b\n\nfirst math line\nsecond math line\n$$\n"),
    ("display math whose closing $$ line is indented by spaces",
     "$$\nfirst math line\n\nsecond math line\nthird math line\n  $$\n"),
    ("display math closed by a line ending in $$, nothing after it",
     "$$\n\\begin{aligned}\nx = 1\ny = 2\n\\end{aligned}$$\n"),
    ("a paragraph inside a block quote is left alone",
     "> quoted first line\nquoted second line\n"),
    ("a <br> at a line's end is a hard break",
     "First<br>\nsecond\n"),
    ("a fence after a <br> line that cannot interrupt a paragraph (round 6, item 3)",
     "Intro.  \n<br>\n```text\n\nalpha\nbeta\n```\n"),
    ("an HTML block whose start is indented by two spaces (round 6 note)",
     "  <div>\nfirst text line\nsecond text line\n</div>\n"),
    ("a later top-level fence opener after a list-item fence (round 6, item 2)",
     "10. ```sh\n    x\n    ```\n\n```\nfirst code line\nsecond code line\n```\n"),
    # Round 7.
    ("consecutive footnote definitions, as in a Sources section (round 7, item 1)",
     "## Sources\n\n[^google-canonical]: [Google Search Central: How to specify a canonical URL]"
     "(https://developers.google.com/search/docs/crawling)\n"
     "[^substack-domain]: [Substack: Set up a custom domain](https://support.substack.com/hc/en-us/articles/1)\n"),
    ("a footnote definition with an indented continuation line (round 7, item 1)",
     "[^a]: A footnote with spaces in it\n    and its indented continuation.\n"),
    ("a footnote definition with two continuation lines indented two spaces",
     "[^a]: A footnote with spaces in it\n  and one continuation\n  and another.\n"),
    ("a $$ inside an HTML block does not close display math opened before it",
     "$$\n<div>\n$$\n</div>\n\nline a\nline b\n$$\n"),
    ("a $$ inside a fenced example does not pair with a later math opener (round 7, item 4)",
     "```markdown\n$$\n```\n\n$$\nx = 1\n$$\n\n```\nfirst code line\nsecond code line\n```\n"),
    # Round 8: a file holding display math or a footnote definition gets no
    # reminder at all; these were broken cases while the hook judged them.
    ("a line starting $$ that does not hold $$ alone opens no math block",
     "$$ x = y + z\n\nOne line\nand another.\n"),
    ("a line holding $$x$$ and more text opens no math block",
     "$$x$$ inline-ish\n\nOne line\nand another.\n"),
    ("a broken paragraph after display math closed by $$ alone",
     "$$\nx = 1\n$$\n\nOne line\nand another.\n"),
    ("display math closed by a line ending in $$ (round 6 note)",
     "$$\n\\begin{aligned}\nx\n\\end{aligned}$$\n\nOne line\nand another.\n"),
    ("a lone $$ with no closer hides nothing",
     "$$\nx = 1\n\nOne line\nand another.\n"),
    ("a broken paragraph after display math opened by $$\\begin{aligned} (round 7 question)",
     "$$\\begin{aligned}\nx\n\\end{aligned}$$\n\nOne line\nand another.\n"),
    ("a broken paragraph after footnote definitions",
     "[^a]: A footnote with spaces\n\nOne line\nand another.\n"),
    ("a one-line $$x$$ opens no math block, so it hides nothing up to a later $$",
     "$$x$$\n\nOne line\nand another.\n\n$$\n"),
    ("display math indented in a list item (round 7, item 1)",
     "10. item\n\n    $$\n    x = 1\n    y = 2\n    $$\n\nOne line\nand another.\n"),
    ("display math opened inside a block quote",
     "> $$\n> x\n\nOne line\nand another.\n"),
    ("a table row without outer pipes that starts with a footnote label (round 7, item 3)",
     "| a | b |\n|---|---|\n[^a]: note | A\nc | d\n\nOne line\nand another.\n"),
    ("display math opened on a numbered list-item line, its other lines unmarked",
     "10. $$\n    x = 1\n\nOne line\nand another.\n"),
    ("display math opened on a list-item line",
     "- $$\n  x\n  $$\n\nOne line\nand another.\n"),
    ("a <br> then a tab at a line's end is a hard break (round 7, item 5)",
     "First<br>\t\nsecond\n"),
    ("display math opened by $$\\begin{aligned} and closed by a line ending in $$ (round 7 question)",
     "$$\\begin{aligned}\nx = 1\ny = 2\n\\end{aligned}$$\n"),
)
if PARSER_AVAILABLE:
    for case_name, text in CLEAN_CASES:
        check(f"silent: {case_name}", hook.markdown_has_hard_wrapped_paragraph(text) is False)

    large_text = ("One whole paragraph on one line.\n\n" * 50000)
    import time as _time
    _started = _time.monotonic()
    hook.markdown_has_hard_wrapped_paragraph(large_text)
    check("a 1.6 MB file is judged in under five seconds",
          _time.monotonic() - _started < 5.0)
else:
    print("the detector's cases were not run: markdown-it-py is missing")

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

    if PARSER_AVAILABLE:
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

    if PARSER_AVAILABLE:
        result = write_then_run(checkout, checkout / "notes.markdown", BROKEN_TEXT)
        check("a .markdown file is checked too",
              agent_text(result).startswith("markdown-edit-hard-wrapped-paragraph-reminder: notes.markdown"),
              result.stdout + result.stderr)

    # A machine without markdown-it-py: a package of that name that fails to
    # import stands in for the missing one, and the hook must say so on stderr
    # with exit 1, a non-blocking error Claude Code shows, and give no reminder.
    blocked_packages = tmp / "blocked-packages"
    (blocked_packages / "markdown_it").mkdir(parents=True)
    (blocked_packages / "markdown_it" / "__init__.py").write_text(
        "raise ImportError('markdown-it-py blocked by the test')\n", encoding="utf-8")
    blocked_file = checkout / "docs" / "blocked.md"
    blocked_file.write_text(BROKEN_TEXT, encoding="utf-8")
    blocked_environment = {**CLEAN_ENVIRONMENT, "PYTHONPATH": str(blocked_packages)}
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload_for(checkout, "Write", blocked_file, {"content": BROKEN_TEXT})),
        capture_output=True, text=True, check=False, env=blocked_environment)
    check("without markdown-it-py the hook reports the missing package and exits 1",
          result.returncode == 1 and result.stdout.strip() == ""
          and "markdown-it-py is not installed" in result.stderr,
          f"exit {result.returncode}: {result.stdout + result.stderr}")

    result = write_then_run(checkout, checkout / "scripts" / "tool.txt",
                            "The first half of a sentence\nand the second half.\n")
    check("a non-Markdown file is silent", silent(result), result.stdout + result.stderr)

    result = write_then_run(checkout, checkout / "ignored-notes" / "scratch.md", BROKEN_TEXT)
    check("a git-ignored Markdown file is silent", silent(result),
          result.stdout + result.stderr)

    # git cannot answer: a .git file pointing nowhere makes check-ignore exit 128.
    broken_checkout = tmp / "broken-checkout"
    broken_checkout.mkdir()
    (broken_checkout / ".git").write_text("gitdir: " + str(tmp / "no-such-git-directory") + "\n",
                                          encoding="utf-8")
    result = write_then_run(broken_checkout, broken_checkout / "notes.md", BROKEN_TEXT)
    check("when git check-ignore exits 128 the hook reports git's failure and exits 1",
          result.returncode == 1 and result.stdout.strip() == ""
          and "git check-ignore exited 128" in result.stderr,
          f"exit {result.returncode}: {result.stdout + result.stderr}")

    # git missing from PATH: the hook runs by absolute path, so only git is absent.
    missing_git_file = checkout / "docs" / "missing-git.md"
    missing_git_file.write_text(BROKEN_TEXT, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload_for(checkout, "Write", missing_git_file, {"content": BROKEN_TEXT})),
        capture_output=True, text=True, check=False,
        env={**CLEAN_ENVIRONMENT, "PATH": str(tmp / "empty-path-directory")})
    check("when git is missing the hook reports it and exits 1",
          result.returncode == 1 and result.stdout.strip() == ""
          and "git check-ignore could not run" in result.stderr,
          f"exit {result.returncode}: {result.stdout + result.stderr}")

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
