#!/usr/bin/env python3
"""Tests for markdown-edit-hard-wrapped-paragraph-reminder-hook-nbd.py.

Run: python3 scripts/markdown-edit-hard-wrapped-paragraph-reminder-hook-nbd-test.py
Prints one line per case and exits non-zero if any case fails.

The detector's cases call markdown_has_hard_wrapped_paragraph directly. The
detector needs markdown-it-py; without it the suite fails, naming the command that
installs the pinned file. The shared Markdown parser module's own suite checks
that a missing markdown-it-py is installed; here one case checks that the hook reports a failed install as a non-blocking error. The hook's
cases run the hook as Claude Code does, as a subprocess reading a PostToolUse
payload on stdin, against a throwaway repository under a temporary directory
with a .gitignore that ignores one directory. The join's races and failures that a
subprocess cannot bring about on cue are brought about by calling the hook's functions
in this process, with a holder of the lock, a changed file or a failing os.replace put in
their way.

Every git call, the hook's included, runs with the variables that redirect git
(GIT_DIR and its kin) removed, and the scratch repository is checked to be a
repository at its own path before any case writes to it.
"""

import contextlib
import fcntl
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
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

HOOK_PATH = Path(__file__).with_name("markdown-edit-hard-wrapped-paragraph-reminder-hook-nbd.py")

CLEAN_ENVIRONMENT = {name: value for name, value in os.environ.items()
                     if name not in _git_environment_fixture.GIT_REDIRECTING_ENVIRONMENT_VARIABLES}

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


specification = importlib.util.spec_from_file_location(
    "markdown_edit_hard_wrapped_paragraph_reminder_hook_nbd", str(HOOK_PATH))
hook = importlib.util.module_from_spec(specification)
specification.loader.exec_module(hook)
parser_common = hook.markdown_commonmark_parser_with_tables_common()

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
PARSER_INSTALL_COMMAND = ("python3 -m pip install --user --break-system-packages -r "
                          "nc-systems/general-tools/python-libraries-pinned-requirements.txt, "
                          "run with the python3 that `command -v python3` finds in the shell Claude Code runs hooks from")
check("markdown-it-py is installed, so the reminder works on this machine",
      PARSER_AVAILABLE, f"install it with: {PARSER_INSTALL_COMMAND}")

# The hook's message for a failed install of markdown-it-py.
raised = parser_common.MarkdownParserMissing("pip: network is unreachable")
message = hook.parser_missing_message(raised, "Neds-MacBook-Pro") if raised else ""
check("the failed-install message names the machine, the by-hand install of the pinned file "
      "for this interpreter, and what the install printed",
      "markdown-it-py is missing on Neds-MacBook-Pro and installing it failed" in message
      and f"{sys.executable} -m pip install --user --break-system-packages -r " in message
      and "python-libraries-pinned-requirements.txt" in message
      and message.endswith("quoted as it is: pip: network is unreachable"), message)
message = hook.parser_missing_message(parser_common.MarkdownParserMissing("x"), "ned-box")
check("for ned-box, the by-hand command is the ssh form the user runs from the Mac",
      "run this command in a Terminal on your Mac:" in message
      and f"\nssh nedlern@ned-box '{sys.executable} -m pip install" in message, message)

message = hook.parser_missing_message(parser_common.MarkdownParserMissing("nothing was installed"),
                                      "Neds-MacBook-Pro", (3, 9, 6))
check("below Python 3.11 the message gives no pip command, and says how to put a newer Python "
      "first on the PATH",
      "pip" not in message.split("Then pass on")[0] and "Python 3.9.6" in message
      and "Homebrew" in message and "next run" in message
      and message.endswith("quoted as it is: nothing was installed"), message)

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
# The join, called directly.
# ---------------------------------------------------------------------------

if PARSER_AVAILABLE:
    for case_name, text in BROKEN_CASES:
        ranges = hook.markdown_broken_paragraph_line_ranges(text)
        try:
            joined = hook.text_with_lines_joined(text, hook.soft_line_breaks_to_join(text, ranges))
        except hook.JoinNotMade as refusal:
            check(f"joined or refused: {case_name}", "line breaks the parser can place" in str(refusal),
                  str(refusal))
            continue
        check(f"joined, parsing as the same Markdown and broken no more: {case_name}",
              hook.markdown_structure_with_line_breaks_as_spaces(joined)
              == hook.markdown_structure_with_line_breaks_as_spaces(text)
              and not hook.markdown_has_hard_wrapped_paragraph(joined)
              and joined.count("\n") < text.count("\n"), repr(joined))

    for case_name, text, expected in (
            ("a hard break by two trailing spaces is kept, the soft break after it joined",
             "First line  \nsecond line\nthird line\n", "First line  \nsecond line third line\n"),
            ("a trailing <br> is kept, the soft break after it joined",
             "First<br>\nsecond\nthird\n", "First<br>\nsecond third\n"),
            ("a trailing backslash is kept", "One\\\ntwo\nthree\n", "One\\\ntwo three\n"),
            ("a list item's continuation indentation and a trailing tab and space go",
             "- The first half \t\n    and the second half.\n", "- The first half and the second half.\n"),
            ("front matter stays as it is", "---\ntitle: x\nmore: y\n---\n\nOne\ntwo\n",
             "---\ntitle: x\nmore: y\n---\n\nOne two\n")):
        joined = hook.text_with_lines_joined(
            text, hook.soft_line_breaks_to_join(text, hook.markdown_broken_paragraph_line_ranges(text)))
        check(f"join: {case_name}", joined == expected, repr(joined))

    try:
        hook.soft_line_breaks_to_join("\nAn image ![alt\ntext](x.png) here\nand on.\n", [(1, 4)])
        image_refusal = "no refusal"
    except hook.JoinNotMade as refusal:
        image_refusal = str(refusal)
    check("a paragraph whose image holds a line break is refused, naming its lines and counts",
          image_refusal == "the paragraph on lines 2 to 4 has 2 line ends but 1 line breaks the parser "
          "can place, as when an image or a code span holds a line break", image_refusal)
    two_paragraphs = "A\nB\n\nWhole.\n\nC\nD\nE\n"
    only_second = hook.soft_line_breaks_to_join(two_paragraphs, [(5, 8)])
    check("only the paragraphs in the ranges given are joined", only_second == [5, 6], only_second)
    check("the structure compared keeps a code block's line breaks",
          hook.markdown_structure_with_line_breaks_as_spaces("    a\n    b\n")
          != hook.markdown_structure_with_line_breaks_as_spaces("    a b\n"))
    check("the structure compared keeps the break between two paragraphs",
          hook.markdown_structure_with_line_breaks_as_spaces("a\n\nb\n")
          != hook.markdown_structure_with_line_breaks_as_spaces("a b\n"))
    check("the structure compared ignores where a block sits",
          hook.markdown_structure_with_line_breaks_as_spaces("# H\n\na\nb\n")
          == hook.markdown_structure_with_line_breaks_as_spaces("# H\n\na b\n"))

for case_name, tool_name, tool_input, tool_response, expected in (
        ("a Write's content", "Write", {"content": "x"}, {}, ["x"]),
        ("a Write without content", "Write", {}, {}, []),
        ("an Edit whose tool_response is not an object", "Edit", {}, None, []),
        ("an Edit whose tool_response lacks replaceAll", "Edit", {},
         {"originalFile": "a", "oldString": "a", "newString": "b"}, []),
        ("an Edit whose tool_response lacks newString", "Edit", {},
         {"originalFile": "a", "oldString": "a", "replaceAll": False}, []),
        ("an Edit whose tool_response lacks oldString", "Edit", {},
         {"originalFile": "a", "newString": "b", "replaceAll": False}, []),
        ("an Edit with an empty oldString, which writes newString as the file", "Edit", {},
         {"originalFile": None, "oldString": "", "newString": "new", "replaceAll": False}, ["new"]),
        ("an Edit whose originalFile is missing", "Edit", {},
         {"oldString": "a", "newString": "b", "replaceAll": False}, []),
        ("an Edit replacing the first copy", "Edit", {},
         {"originalFile": "a a", "oldString": "a", "newString": "b", "replaceAll": False}, ["b a"]),
        ("a replace_all Edit", "Edit", {},
         {"originalFile": "a a", "oldString": "a", "newString": "b", "replaceAll": True}, ["b b"]),
        ("an Edit deleting text that ends without a newline, with or without the newline after it",
         "Edit", {}, {"originalFile": "x\ny\nz", "oldString": "y", "newString": "", "replaceAll": False},
         ["x\n\nz", "x\nz"]),
        ("an Edit deleting text that ends in a newline", "Edit", {},
         {"originalFile": "x\ny\nz", "oldString": "y\n", "newString": "", "replaceAll": False}, ["x\nz"]),
        ("an Edit whose oldString is not in originalFile", "Edit", {},
         {"originalFile": "x", "oldString": "y", "newString": "z", "replaceAll": False}, [])):
    got = hook.texts_the_tool_wrote(tool_name, tool_input, tool_response)
    check(f"texts the tool wrote: {case_name}", got == expected, got)

check("the joins are described as the agent reads them",
      hook.joined_lines_description([(1, 2, 1), (5, 7, 4)]) == "lines 1 to 2 into line 1; lines 5 to 7 into line 4")
many_joins = [(3 * n + 1, 3 * n + 2, 2 * n + 1) for n in range(hook.JOINS_DESCRIBED_AT_MOST + 2)]
many_described = hook.joined_lines_description(many_joins)
check("past JOINS_DESCRIBED_AT_MOST joins, only that many are named, then how many more",
      many_described == hook.joined_lines_description(many_joins[:hook.JOINS_DESCRIBED_AT_MOST]) + "; and 2 more"
      and hook.joined_lines_description(many_joins[:hook.JOINS_DESCRIBED_AT_MOST]).count("lines ")
      == hook.JOINS_DESCRIBED_AT_MOST, many_described)


class AddedLineNumbersThatCanOnlyBeLookedUp:
    """Added line numbers a filter may test lines against but not walk through:
    walking them for every broken paragraph costs paragraphs times added lines."""

    def __init__(self, numbers):
        self.numbers = set(numbers)

    def __contains__(self, number):
        return number in self.numbers

    def __iter__(self):
        raise AssertionError("the filter walked through the added lines")


try:
    kept = hook.markdown_broken_paragraph_line_ranges_filter_to_ranges_holding_edit_added_lines(
        [(0, 2), (4, 6), (8, 10)], AddedLineNumbersThatCanOnlyBeLookedUp({5, 10}))
except AssertionError as error:
    kept = str(error)
check("the overlap filter looks each paragraph line up in the added lines, and keeps only "
      "the paragraphs holding one", kept == [(4, 6)], kept)



def added_lines_or_fault(original, old, new, after, replace_all=False):
    response = {"originalFile": original, "oldString": old, "newString": new}
    if replace_all is not None:
        response["replaceAll"] = replace_all
    try:
        return sorted(hook.edit_added_line_numbers(response, after))
    except hook.EditedLinesUnknown as error:
        return f"EditedLinesUnknown: {error}"


check("an Edit with an empty oldString, filling an empty file, counts every line of the file as added",
      added_lines_or_fault("", "", "One.\nTwo.\n", "One.\nTwo.\n") == [0, 1, 2],
      added_lines_or_fault("", "", "One.\nTwo.\n", "One.\nTwo.\n"))
missing_replace_all = added_lines_or_fault("a\n", "a", "b", "b\n", replace_all=None)
check("an Edit payload whose only missing field is replaceAll is a check not made",
      isinstance(missing_replace_all, str) and "replaceAll" in missing_replace_all, missing_replace_all)
consumed = added_lines_or_fault("Drop me.\nThe first half\nand the second half.\n", "Drop me.", "",
                                "The first half\nand the second half.\n")
check("an Edit with an empty newString that also removed the following newline, as Claude Code "
      "2.1.222 and later do, is read, and adds no line", consumed == [], consumed)
kept_newline = added_lines_or_fault("Drop me.\nThe first half\nand the second half.\n", "Drop me.", "",
                                    "\nThe first half\nand the second half.\n")
check("an Edit with an empty newString that left the following newline, as Claude Code 2.1.185 did, "
      "adds only the emptied line", kept_newline == [0], kept_newline)
adjacent = added_lines_or_fault("Filler.\np\np\np\nThe first half\n", "p\n", "",
                                "Filler.\nThe first half\n", replace_all=True)
check("a replace_all Edit deleting adjacent identical lines adds no line, though each deleted "
      "line's span shares a line with the next", adjacent == [], adjacent)
adjacent_inserts = added_lines_or_fault("p\np\nq\n", "p\n", "p\nNEW\n", "p\nNEW\np\nNEW\nq\n",
                                        replace_all=True)
check("a replace_all Edit whose adjacent replacements each add a line counts both added lines",
      adjacent_inserts == [1, 3], adjacent_inserts)

_real_sequence_matcher = hook.difflib.SequenceMatcher


class SequenceMatcherNotToBeCalled:
    def __init__(self, *arguments, **keywords):
        raise AssertionError("the line diff ran on a span past LINE_DIFF_MAXIMUM_LINE_PAIRS")


repeated_old = "\n".join(["x"] * 600)
repeated_new = "\n".join(["x", "z"] * 300)
hook.difflib.SequenceMatcher = SequenceMatcherNotToBeCalled
try:
    bounded = added_lines_or_fault("Top.\n" + repeated_old + "\nEnd.\n", repeated_old, repeated_new,
                                   "Top.\n" + repeated_new + "\nEnd.\n")
except AssertionError as error:
    bounded = str(error)
finally:
    hook.difflib.SequenceMatcher = _real_sequence_matcher
check("a span of 600 repeated lines against 600 is not line-diffed, and its every new line counts "
      "as added", bounded == list(range(1, 601)), bounded if isinstance(bounded, str) else len(bounded))
small = added_lines_or_fault("Top.\nx\nx\nEnd.\n", "x\nx", "x\nz", "Top.\nx\nz\nEnd.\n")
check("a span within LINE_DIFF_MAXIMUM_LINE_PAIRS is line-diffed, so only its changed line counts as added",
      small == [2], small)

# ---------------------------------------------------------------------------
# The hook, run as a subprocess against a scratch repository.
# ---------------------------------------------------------------------------


def git(arguments, cwd):
    """Run a fixture's git step; a step that fails stops the suite, with git's error."""
    result = subprocess.run(["git", *arguments], cwd=str(cwd), capture_output=True,
                            text=True, check=False, env=CLEAN_ENVIRONMENT)
    if result.returncode != 0:
        raise SystemExit(f"ABORT: fixture step git {' '.join(arguments)} in {cwd} "
                         f"exited {result.returncode}: {result.stderr.strip()}")
    return result


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


def leading_tabs_as_two_spaces(text):
    return "\n".join("  " * (len(line) - len(line.lstrip("\t"))) + line.lstrip("\t")
                     for line in text.split("\n"))


def structured_patch(before, after):
    """A structuredPatch in the shape Claude Code 2.1.300 puts in an Edit's
    tool_response: one hunk per changed region with three lines of context,
    newStart counted from 1, each line prefixed " ", "-" or "+", and every leading
    tab turned into two spaces before the diff. The hook does not read it; it is here
    so that each payload carries what a real one carries."""
    import difflib
    old_lines = leading_tabs_as_two_spaces(before).splitlines()
    new_lines = leading_tabs_as_two_spaces(after).splitlines()
    hunks = []
    for group in difflib.SequenceMatcher(None, old_lines, new_lines).get_grouped_opcodes(3):
        lines = []
        for tag, old_start, old_end, new_start, new_end in group:
            if tag == "equal":
                lines += [" " + line for line in old_lines[old_start:old_end]]
                continue
            lines += ["-" + line for line in old_lines[old_start:old_end]]
            lines += ["+" + line for line in new_lines[new_start:new_end]]
        hunks.append({"oldStart": group[0][1] + 1, "oldLines": group[-1][2] - group[0][1],
                      "newStart": group[0][3] + 1, "newLines": group[-1][4] - group[0][3],
                      "lines": lines})
    return hunks


def edit_then_run(cwd, file_path, before, old_string, new_string, replace_all=False,
                  written_new_string=None, line_end="\n"):
    """What the Edit tool leaves behind, then the hook that follows it, with the
    tool_response keys a captured Claude Code 2.1.300 Edit payload carries.
    written_new_string stands for what Claude Code wrote when it differs from the
    new_string the agent typed, as when it writes curly quotes the file used; line_end
    is the file's line end on disk, while originalFile always holds LF, as Claude Code
    hands it over."""
    written = new_string if written_new_string is None else written_new_string
    after = before.replace(old_string, written) if replace_all else before.replace(old_string, written, 1)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(after.replace("\n", line_end).encode("utf-8"))
    payload = payload_for(cwd, "Edit", file_path, {"old_string": old_string, "new_string": new_string,
                                                   "replace_all": replace_all})
    payload["tool_response"] = {"filePath": str(file_path), "oldString": old_string,
                                "newString": new_string, "originalFile": before,
                                "structuredPatch": structured_patch(before, after),
                                "userModified": False, "replaceAll": replace_all}
    return run_hook(payload)


def silent(result):
    return result.returncode == 0 and result.stdout.strip() == "" and result.stderr.strip() == ""


def reported(result, fault_words):
    """A fault: exit 1, no reminder on stdout, one stderr line naming the hook and the fault."""
    lines = result.stderr.splitlines()
    return (result.returncode == 1 and result.stdout == "" and len(lines) == 1
            and lines[0].startswith("markdown-edit-hard-wrapped-paragraph-reminder: ")
            and fault_words in lines[0])


def agent_text(result):
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        return ""
    if not isinstance(parsed, dict):
        return ""
    return parsed.get("hookSpecificOutput", {}).get("additionalContext", "")


def reminder_with_reason(path, reason_start):
    """The start of the reminder whose last line says the hook did not join because of a
    reason starting with reason_start."""
    return (hook.REMINDER_MESSAGE.format(path=path)
            + hook.JOIN_NOT_MADE_LINE.format(reason=reason_start))[:-1]


def gives_reminder_with_reason(result, path, reason_start):
    text = agent_text(result)
    return (result.returncode == 0 and result.stderr == ""
            and text.startswith(reminder_with_reason(path, reason_start)) and text.endswith("."))


def gives_reminder_as_today(result, path):
    return (result.returncode == 0 and result.stderr == ""
            and agent_text(result) == hook.REMINDER_MESSAGE.format(path=path))


BROKEN_TEXT = "# Notes\n\nThe first half of a sentence\nand the second half.\n"
BROKEN_TEXT_JOINED = "# Notes\n\nThe first half of a sentence and the second half.\n"
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
        check("a Write leaving a broken paragraph in an unguarded file gets the lines joined and "
              "one PostToolUse message naming them, exit 0",
              result.returncode == 0 and result.stderr == ""
              and reply.get("hookSpecificOutput", {}).get("hookEventName") == "PostToolUse"
              and text == hook.JOINED_MESSAGE.format(path="docs/broken.md", tool_name="Write",
                                                     joins="lines 3 to 4 into line 3")
              and (checkout / "docs" / "broken.md").read_text(encoding="utf-8") == BROKEN_TEXT_JOINED,
              result.stdout + result.stderr)

        edited_file = checkout / "docs" / "edited.md"
        reminded_prefix = hook.JOINED_MESSAGE.format(path="docs/edited.md", tool_name="Edit", joins="lines ")
        reminded_prefix = reminded_prefix[:reminded_prefix.index("lines ")]
        broken_before = "# Notes\n\nThe first half of a sentence\nand the second part.\n"
        result = edit_then_run(checkout, edited_file, broken_before, "the second part", "the second half")
        check("an Edit that wrote into a broken paragraph gets the reminder",
              agent_text(result).startswith(reminded_prefix), result.stdout + result.stderr)
        result = edit_then_run(checkout, edited_file, broken_before, "The first half of a sentence",
                               "The first part of a sentence")
        check("an Edit of a broken paragraph's first line alone gets the reminder",
              agent_text(result).startswith(reminded_prefix), result.stdout + result.stderr)
        result = edit_then_run(checkout, edited_file, BROKEN_TEXT.replace("# Notes", "# Old"), "# Old", "# Notes")
        check("an Edit that wrote only outside the broken paragraph gets no reminder",
              silent(result), result.stdout + result.stderr)
        result = edit_then_run(checkout, edited_file, "# Old\nThe first half\nand the second half.\n",
                               "# Old\n", "# Heading\n")
        check("an Edit of the heading directly above an untouched broken paragraph gets no reminder",
              silent(result), result.stdout + result.stderr)
        result = edit_then_run(checkout, edited_file, "The first half\nand the second half.\n# Old\n",
                               "# Old", "# Heading")
        check("an Edit of the heading directly below an untouched broken paragraph gets no reminder",
              silent(result), result.stdout + result.stderr)
        result = edit_then_run(checkout, edited_file,
                               "# Title\n\nCats or dogs on one line.\n\nThe first half\nand the second half.\n",
                               "or", "and")
        check("an Edit whose new text also stands in an untouched broken paragraph gets no reminder",
              silent(result), result.stdout + result.stderr)
        result = edit_then_run(checkout, edited_file, "# Notes\n\nThe first half\nand the second half.\n",
                               "# Notes\n\n", "")
        check("an Edit that only deleted lines gets no reminder",
              silent(result), result.stdout + result.stderr)
        result = edit_then_run(checkout, edited_file,
                               "Filler.\np\np\np\nThe first half\nand the second half.\n", "p\n", "",
                               replace_all=True)
        check("a replace_all Edit that only deleted adjacent identical lines above an untouched broken "
              "paragraph gets no reminder", silent(result), result.stdout + result.stderr)
        far_apart = ("A mark on one line.\n\n" + "".join(f"Filler {n} on one line.\n\n" for n in range(8))
                     + "The first mark\nand the second half.\n")
        result = edit_then_run(checkout, edited_file, far_apart, "mark", "Mark", replace_all=True)
        check("a replace_all Edit whose second hunk wrote into a broken paragraph gets the reminder",
              agent_text(result).startswith(reminded_prefix), result.stdout + result.stderr)

        result = edit_then_run(checkout, edited_file, "# Notes\n\nThe first paragraph.\n\nThe second one.\n",
                               "paragraph.\n\nThe second", "paragraph.\nThe second")
        check("an Edit that only deleted the blank line joining two paragraphs into a broken one "
              "gets no reminder", silent(result), result.stdout + result.stderr)
        tab_code_block = "# Notes\n\n\tcode line one\n\tcode line two\n\nOther text.\n"
        result = edit_then_run(checkout, edited_file, tab_code_block, "\tcode line one\n\tcode line two",
                               "  code line one\n  code line two")
        check("an Edit that turned leading tabs into two spaces, making a code block a broken paragraph, "
              "gets the reminder, though its structuredPatch is empty",
              agent_text(result).startswith(reminded_prefix), result.stdout + result.stderr)
        result = edit_then_run(checkout, edited_file, "# Notes\n\nIntro.\n\n\tcode line one\n\tcode line two\n",
                               "Intro.\n\n\tcode line one\n\tcode line two",
                               "Intro, longer.\n\n  code line one\n  code line two")
        check("an Edit whose lines changed only in their leading tabs, beside a line changed in its text, "
              "gets the reminder, though its structuredPatch shows them as context",
              agent_text(result).startswith(reminded_prefix), result.stdout + result.stderr)
        result = edit_then_run(checkout, edited_file, "# Notes\n\nOther text.\n", "# Notes",
                               "# Notes\n\nA new first half\nand a new second half.")
        check("an Edit that wrote a broken paragraph below an unchanged line of its old_string gets the reminder",
              agent_text(result).startswith(reminded_prefix), result.stdout + result.stderr)
        result = edit_then_run(checkout, edited_file, "# Notes\n\nThe first half\nand the second half.\n\nNext.\n",
                               "and the second half.\n\nNext.", "and the second half.\n\nNext, changed.")
        check("an Edit whose new_string repeats an untouched broken paragraph's line as context "
              "gets no reminder", silent(result), result.stdout + result.stderr)
        result = edit_then_run(checkout, edited_file, broken_before, "the second part", "the second half",
                               line_end="\r\n")
        check("an Edit into a broken paragraph of a CRLF file, whose originalFile holds LF, gets the "
              "reminder, saying the hook joins only lines ending in a bare line feed, and the file kept",
              gives_reminder_with_reason(result, "docs/edited.md", "the file holds a carriage return")
              and edited_file.read_bytes() == broken_before.replace("the second part", "the second half")
              .replace("\n", "\r\n").encode("utf-8"), result.stdout + result.stderr)
        result = edit_then_run(checkout, edited_file, "# Notes\n\nThe first half\nand the second half.\n\nNext.\n",
                               "and the second half.\n\nNext.", "and the second half.\n\nNext, changed.",
                               line_end="\r\n")
        check("an Edit of a CRLF file whose new_string repeats an untouched broken paragraph's line "
              "as context gets no reminder", silent(result), result.stdout + result.stderr)
        result = edit_then_run(checkout, edited_file,
                               "# mark\n\nFiller one.\n\nFiller two.\n\nThe mark\nand the second half.\n",
                               "mark", "M\n\nAdded.", replace_all=True)
        check("a replace_all Edit whose replacements add lines, and whose second one wrote into "
              "a broken paragraph, gets the reminder",
              agent_text(result).startswith(reminded_prefix), result.stdout + result.stderr)
        result = edit_then_run(checkout, edited_file,
                               "# Notes\n\nHe said \u201chi\u201d\nand left.\n\nOther text.\n",
                               "Other text.", "Other \"text\".", written_new_string="Other \u201ctext\u201d.")
        check("an Edit Claude Code wrote with curly quotes where new_string had straight ones, "
              "outside the broken paragraph, gets no reminder", silent(result), result.stdout + result.stderr)

        edited_file.write_text(CLEAN_TEXT, encoding="utf-8")
        result = run_hook(payload_for(checkout, "Edit", edited_file,
                                      {"old_string": "x", "new_string": "A whole paragraph",
                                       "replace_all": False}))
        check("an Edit of a file holding no broken paragraph needs no originalFile: silent, exit 0",
              silent(result), result.stdout + result.stderr)

        edited_file.write_text(BROKEN_TEXT, encoding="utf-8")
        result = run_hook(payload_for(checkout, "Edit", edited_file,
                                      {"old_string": "x", "new_string": "the second half",
                                       "replace_all": False}))
        check("an Edit whose payload has no originalFile is reported as a check not made, exit 1",
              result.returncode == 1 and result.stdout == ""
              and "lacks tool_response's originalFile" in result.stderr
              and "the Edit itself succeeded." in result.stderr,
              result.stdout + result.stderr)
        payload = payload_for(checkout, "Edit", edited_file, {"old_string": "x", "new_string": "y"})
        payload["tool_response"] = {"originalFile": BROKEN_TEXT, "oldString": "absent",
                                    "newString": "y", "replaceAll": False}
        result = run_hook(payload)
        check("an Edit whose oldString is not in originalFile is reported as a check not made, exit 1",
              result.returncode == 1 and "does not occur" in result.stderr, result.stdout + result.stderr)
        payload["tool_response"] = {"originalFile": BROKEN_TEXT, "oldString": "# Notes",
                                    "newString": "# Notes\n\nMore", "replaceAll": False}
        result = run_hook(payload)
        check("an Edit whose file on disk lacks the line count its replacements give is reported "
              "as a check not made, exit 1",
              result.returncode == 1 and "line count" in result.stderr, result.stdout + result.stderr)


        # ---- the join, as the hook makes it after a tool call
        several = checkout / "docs" / "several.md"
        result = write_then_run(checkout, several, "A\nB\n\nWhole.\n\nC\n  D\nE\n")
        check("a Write with two broken paragraphs has both joined, each named with its lines before "
              "and after the join",
              agent_text(result) == hook.JOINED_MESSAGE.format(
                  path="docs/several.md", tool_name="Write",
                  joins="lines 1 to 2 into line 1; lines 6 to 8 into line 5")
              and several.read_text(encoding="utf-8") == "A B\n\nWhole.\n\nC D E\n",
              result.stdout + result.stderr)

        untouched = "# Notes\n\nThe untouched first\nand second.\n\nThe edited part\nand the rest.\n"
        result = edit_then_run(checkout, edited_file, untouched, "The edited part", "The edited half")
        check("an Edit gets only the broken paragraph it wrote into joined, the untouched one kept",
              agent_text(result) == hook.JOINED_MESSAGE.format(
                  path="docs/edited.md", tool_name="Edit", joins="lines 6 to 7 into line 6")
              and edited_file.read_text(encoding="utf-8")
              == "# Notes\n\nThe untouched first\nand second.\n\nThe edited half and the rest.\n",
              result.stdout + result.stderr)
        result = edit_then_run(checkout, edited_file, edited_file.read_text(encoding="utf-8"),
                               "The edited half", "The edited whole")
        check("the agent's next Edit, made after reading the joined file again, is judged as any "
              "other: silent, the file as the Edit left it",
              silent(result) and "The edited whole and the rest." in edited_file.read_text(encoding="utf-8"),
              result.stdout + result.stderr)

        result = edit_then_run(checkout, edited_file, "", "", "Made by an Edit\nwith no old_string.\n")
        check("an Edit with an empty old_string, which makes the file, gets its lines joined",
              agent_text(result) == hook.JOINED_MESSAGE.format(
                  path="docs/edited.md", tool_name="Edit", joins="lines 1 to 2 into line 1")
              and edited_file.read_text(encoding="utf-8") == "Made by an Edit with no old_string.\n",
              result.stdout + result.stderr)

        new_file = checkout / "docs" / "new-directory" / "made-by-write.md"
        new_file.parent.mkdir(parents=True)
        new_file.write_text(BROKEN_TEXT, encoding="utf-8")
        new_file.chmod(0o640)
        result = run_hook(payload_for(checkout, "Write", new_file, {"content": BROKEN_TEXT}))
        check("a Write that made a new file in a new directory gets it joined, its permission bits "
              "kept and no temporary file left beside it",
              agent_text(result).startswith(reminded_prefix.replace("docs/edited.md", "docs/new-directory/made-by-write.md"))
              and new_file.read_text(encoding="utf-8") == BROKEN_TEXT_JOINED
              and (new_file.stat().st_mode & 0o777) == 0o640
              and sorted(entry.name for entry in new_file.parent.iterdir()) == ["made-by-write.md"],
              result.stdout + result.stderr)

        several.write_text("A\nB\n", encoding="utf-8")
        payload = payload_for(checkout, "Write", several, {"content": "A\nB\n"})
        first, second = run_hook(payload), run_hook(payload)
        check("the same Write's hook run twice on one file: the first joins it, the second finds "
              "no broken paragraph and is silent, the file left joined",
              agent_text(first) == hook.JOINED_MESSAGE.format(path="docs/several.md", tool_name="Write",
                                                              joins="lines 1 to 2 into line 1")
              and silent(second) and several.read_text(encoding="utf-8") == "A B\n",
              first.stdout + second.stdout)

        concurrent = checkout / "docs" / "concurrent.md"
        concurrent.write_text(BROKEN_TEXT, encoding="utf-8")
        payload_text = json.dumps(payload_for(checkout, "Write", concurrent, {"content": BROKEN_TEXT}))
        runs = [subprocess.Popen([sys.executable, str(HOOK_PATH)], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                 env=CLEAN_ENVIRONMENT) for _ in range(4)]
        outputs = [run.communicate(payload_text) for run in runs]
        texts = [agent_text(subprocess.CompletedProcess([], 0, out, err)) for out, err in outputs]
        joined_runs = [text for text in texts if text == hook.JOINED_MESSAGE.format(
            path="docs/concurrent.md", tool_name="Write", joins="lines 3 to 4 into line 3")]
        # A run that reads the file after the join finds nothing broken and is silent; one that
        # read it before is refused, by the lock and the read again under it.
        refused_runs = [text for text in texts if text == "" or text.startswith(
            hook.REMINDER_MESSAGE.format(path="docs/concurrent.md") + "\nThis hook joins such lines itself")]
        check("four runs of the hook started together on one file: one joins it, the other three are "
              "silent or give the reminder with a reason, and the file is joined once",
              len(joined_runs) == 1 and len(refused_runs) == 3
              and all(run.returncode == 0 and err == "" for run, (out, err) in zip(runs, outputs))
              and concurrent.read_text(encoding="utf-8") == BROKEN_TEXT_JOINED,
              texts)

        for guarded_name in ("CLAUDE.md", "docs/agents/guarded-page.md", "docs/guarded-prompt.md",
                             ".claude/guarded-notes.md", "docs/guarded-design.md"):
            guarded_file = checkout / guarded_name
            result = write_then_run(checkout, guarded_file, BROKEN_TEXT)
            check(f"a Write of {guarded_name}, which the instruction-file guard protects, gets the "
                  f"reminder as today and the file kept",
                  gives_reminder_as_today(result, guarded_name)
                  and guarded_file.read_text(encoding="utf-8") == BROKEN_TEXT,
                  result.stdout + result.stderr)
        check("the reminder names no line number",
              ":3" not in hook.REMINDER_MESSAGE and "line 3" not in hook.REMINDER_MESSAGE)
        for exempt_name in ("docs/drafts/draft-design.md", "docs/agents/queue/queued-prompt.md"):
            exempt_file = checkout / exempt_name
            result = write_then_run(checkout, exempt_file, BROKEN_TEXT)
            check(f"a Write of {exempt_name}, which the instruction-file guard leaves open, gets "
                  f"its lines joined", exempt_file.read_text(encoding="utf-8") == BROKEN_TEXT_JOINED,
                  result.stdout + result.stderr)

        link_target = checkout / "docs" / "link-target.md"
        link_target.write_text(BROKEN_TEXT, encoding="utf-8")
        link = checkout / "docs" / "link.md"
        link.symlink_to(link_target)
        result = run_hook(payload_for(checkout, "Write", link, {"content": BROKEN_TEXT}))
        check("a Write through a symbolic link gets the reminder with its reason, link and target kept",
              gives_reminder_with_reason(result, "docs/link-target.md", "the file is a symbolic link")
              and link.is_symlink() and link_target.read_text(encoding="utf-8") == BROKEN_TEXT,
              result.stdout + result.stderr)

        changed_since = checkout / "docs" / "changed-since.md"
        changed_since.write_text(BROKEN_TEXT + "Added by another program.\n", encoding="utf-8")
        result = run_hook(payload_for(checkout, "Write", changed_since, {"content": BROKEN_TEXT}))
        check("a file changed since the Write wrote it gets the reminder with its reason, the file kept",
              gives_reminder_with_reason(result, "docs/changed-since.md",
                                         "the file on disk is not the text the tool's payload says it wrote")
              and changed_since.read_text(encoding="utf-8") == BROKEN_TEXT + "Added by another program.\n",
              result.stdout + result.stderr)

        no_content = checkout / "docs" / "no-content.md"
        no_content.write_text(BROKEN_TEXT, encoding="utf-8")
        result = run_hook(payload_for(checkout, "Write", no_content, {}))
        check("a Write whose payload lacks its content gets the reminder, saying the hook cannot tell "
              "whether the file changed, the file kept",
              gives_reminder_with_reason(result, "docs/no-content.md",
                                         "the tool's payload does not hold the text the tool wrote")
              and no_content.read_text(encoding="utf-8") == BROKEN_TEXT, result.stdout + result.stderr)

        result = edit_then_run(checkout, edited_file, "# Notes\n\nHe said \u201chi\u201d\nand left.\n",
                               "\u201chi\u201d", "\"hello\"", written_new_string="\u201chello\u201d")
        check("an Edit Claude Code wrote with curly quotes where new_string had straight ones, into "
              "the broken paragraph, gets the reminder with its reason, the file kept",
              gives_reminder_with_reason(result, "docs/edited.md",
                                         "the file on disk is not the text the tool's payload says it wrote")
              and edited_file.read_text(encoding="utf-8") == "# Notes\n\nHe said \u201chello\u201d\nand left.\n",
              result.stdout + result.stderr)

        image_file = checkout / "docs" / "image.md"
        image_text = "An image ![alt\ntext](x.png) here\nand on.\n"
        result = write_then_run(checkout, image_file, image_text)
        check("a paragraph whose image holds a line break gets the reminder with its reason, the file kept",
              gives_reminder_with_reason(result, "docs/image.md", "the paragraph on lines 1 to 3 has 2 line ends")
              and image_file.read_text(encoding="utf-8") == image_text, result.stdout + result.stderr)

        def main_in_process(payload):
            """Run the hook's main in this process, so a test can put a fault in its way."""
            stdout = io.StringIO()
            real_stdin = sys.stdin
            sys.stdin = io.StringIO(json.dumps(payload))
            try:
                with contextlib.redirect_stdout(stdout):
                    exit_code = hook.main()
            finally:
                sys.stdin = real_stdin
            return subprocess.CompletedProcess([], exit_code, stdout.getvalue(), "")

        guard_check_file = checkout / "docs" / "guard-check-fails.md"
        real_guard_loader = hook._load_instruction_file_guard

        def guard_that_will_not_load():
            raise FileNotFoundError("instruction-file-guard.py is gone")

        class GuardWhoseCheckRaises:
            is_protected = staticmethod(lambda file_path: False)
            is_reusable_prompt = staticmethod(lambda file_path: False)

            @staticmethod
            def is_reviewed_document(file_path):
                raise OSError("resolve failed")

        for case_name, loader, reason in (
                ("will not load", guard_that_will_not_load,
                 "it could not tell whether the instruction-file guard protects docs/guard-check-fails.md: "
                 "FileNotFoundError: instruction-file-guard.py is gone"),
                ("raises in a check", lambda: GuardWhoseCheckRaises,
                 "it could not tell whether the instruction-file guard protects docs/guard-check-fails.md: "
                 "OSError: resolve failed")):
            guard_check_file.write_text(BROKEN_TEXT, encoding="utf-8")
            hook._load_instruction_file_guard = loader
            try:
                result = main_in_process(payload_for(checkout, "Write", guard_check_file, {"content": BROKEN_TEXT}))
            finally:
                hook._load_instruction_file_guard = real_guard_loader
            check(f"a guard that {case_name} leaves the file kept and gives the reminder, saying the "
                  f"guard could not be asked",
                  result.returncode == 0 and agent_text(result) == (
                      hook.REMINDER_MESSAGE.format(path="docs/guard-check-fails.md")
                      + hook.JOIN_NOT_MADE_LINE.format(reason=reason))
                  and guard_check_file.read_text(encoding="utf-8") == BROKEN_TEXT, result.stdout)

        def join_refusal(action):
            try:
                action()
            except hook.JoinNotMade as refusal:
                return str(refusal)
            return "no refusal"

        race_file = checkout / "docs" / "race.md"
        race_file.write_text(BROKEN_TEXT, encoding="utf-8")
        real_structure = hook.markdown_structure_with_line_breaks_as_spaces
        hook.markdown_structure_with_line_breaks_as_spaces = lambda text: text.count("\n")
        try:
            refusal = join_refusal(lambda: hook.broken_paragraphs_joined_in_file(
                race_file, BROKEN_TEXT, [(2, 4)], [BROKEN_TEXT]))
        finally:
            hook.markdown_structure_with_line_breaks_as_spaces = real_structure
        check("a join whose text would not parse as the same Markdown is refused, the file kept",
              refusal == "the joined text would not parse as the same Markdown"
              and race_file.read_text(encoding="utf-8") == BROKEN_TEXT, refusal)

        # The agent's own next Edit, or any other program, writing the file after the hook read
        # it and before the hook writes: the hook must not write over that change.
        race_file.write_text("# Notes\n\nWritten by the agent's next Edit.\n", encoding="utf-8")
        refusal = join_refusal(lambda: hook.file_replaced_if_unchanged(race_file, BROKEN_TEXT, BROKEN_TEXT_JOINED))
        check("a file changed between the hook's read and its write is refused, the change kept",
              refusal == "the file changed while the hook was joining its lines"
              and race_file.read_text(encoding="utf-8") == "# Notes\n\nWritten by the agent's next Edit.\n",
              refusal)

        race_file.write_text("# A\n", encoding="utf-8")
        refusal = join_refusal(lambda: hook.file_replaced_if_unchanged(race_file, BROKEN_TEXT, BROKEN_TEXT_JOINED))
        check("a file changed to text that sorts before the text read is refused too, the change kept",
              refusal == "the file changed while the hook was joining its lines"
              and race_file.read_text(encoding="utf-8") == "# A\n", refusal)

        three = checkout / "docs" / "three-joins.md"
        three_text = "A\nB\n\nC\nD\n\nE\nF\nG\n"
        three.write_text(three_text, encoding="utf-8")
        joins = hook.broken_paragraphs_joined_in_file(
            three, three_text, hook.markdown_broken_paragraph_line_ranges(three_text), [three_text])
        check("three joins are each numbered before and after the joins above them",
              joins == [(1, 2, 1), (4, 5, 3), (7, 9, 5)]
              and three.read_text(encoding="utf-8") == "A B\n\nC D\n\nE F G\n", joins)

        race_file.write_text(BROKEN_TEXT, encoding="utf-8")
        real_replace = hook.os.replace

        def failing_replace(source, destination):
            raise PermissionError("replace refused by the test")

        hook.os.replace = failing_replace
        try:
            refusal = join_refusal(lambda: hook.file_replaced_if_unchanged(race_file, BROKEN_TEXT, BROKEN_TEXT_JOINED))
        finally:
            hook.os.replace = real_replace
        check("a write that fails is refused with its error, the file kept and no temporary file left",
              refusal == "writing the joined text failed: PermissionError: replace refused by the test"
              and race_file.read_text(encoding="utf-8") == BROKEN_TEXT
              and not [entry for entry in race_file.parent.iterdir() if entry.name.endswith(".hard-wrap-join")],
              refusal)

        missing_directory_file = checkout / "docs" / "no-such-directory" / "x.md"
        refusal = join_refusal(lambda: hook.file_replaced_if_unchanged(missing_directory_file, "a", "b"))
        check("a directory that cannot be opened for the lock is refused, naming it",
              refusal.startswith(f"the hook could not open {missing_directory_file.parent} to lock it: "), refusal)

        vanished_race_file = checkout / "docs" / "vanished-race.md"
        refusal = join_refusal(lambda: hook.file_replaced_if_unchanged(vanished_race_file, "a", "b"))
        check("a file removed before the hook's write is refused as a failed write",
              refusal.startswith("writing the joined text failed: FileNotFoundError: ")
              and not vanished_race_file.exists(), refusal)

        # Another run of this hook on the same directory: the lock keeps the two apart.
        holder = os.open(race_file.parent, os.O_RDONLY)
        fcntl.flock(holder, fcntl.LOCK_EX)
        real_wait = hook.JOIN_LOCK_WAIT_SECONDS
        hook.JOIN_LOCK_WAIT_SECONDS = 0.3
        started = time.monotonic()
        try:
            refusal = join_refusal(lambda: hook.file_replaced_if_unchanged(race_file, BROKEN_TEXT, BROKEN_TEXT_JOINED))
            waited = time.monotonic() - started
            check("while another run holds the directory's lock past the wait, the join is refused "
                  "after waiting, the file kept",
                  refusal == f"another run of this hook held the lock on {race_file.parent} for over 0.3 seconds"
                  and waited >= 0.3 and race_file.read_text(encoding="utf-8") == BROKEN_TEXT,
                  f"{refusal} after {waited:.2f} s")
            hook.JOIN_LOCK_WAIT_SECONDS = 5.0
            releaser = threading.Timer(0.3, lambda: fcntl.flock(holder, fcntl.LOCK_UN))
            releaser.start()
            started = time.monotonic()
            refusal = join_refusal(lambda: hook.file_replaced_if_unchanged(race_file, BROKEN_TEXT, BROKEN_TEXT_JOINED))
            waited = time.monotonic() - started
            releaser.join()
            check("a lock released within the wait lets the join go ahead once it is free",
                  refusal == "no refusal" and 0.25 <= waited < 4.0
                  and race_file.read_text(encoding="utf-8") == BROKEN_TEXT_JOINED, f"{refusal} after {waited:.2f} s")
        finally:
            hook.JOIN_LOCK_WAIT_SECONDS = real_wait
            os.close(holder)


    result = write_then_run(checkout, checkout / "docs" / "clean.md", CLEAN_TEXT)
    check("a Write leaving no broken paragraph outputs nothing", silent(result),
          result.stdout + result.stderr)

    if PARSER_AVAILABLE:
        result = write_then_run(checkout, checkout / "notes.markdown", BROKEN_TEXT)
        check("a .markdown file is checked too",
              agent_text(result).startswith("markdown-edit-hard-wrapped-paragraph-reminder: the text you just wrote in notes.markdown"),
              result.stdout + result.stderr)

    # A machine without markdown-it-py: a package of that name that fails to
    # import stands in for the missing one. A failed install recorded a minute ago
    # in a scratch home stops the hook from running pip; the hook must report the
    # failed install on stderr with exit 1, a non-blocking error Claude Code shows,
    # and give no reminder.
    blocked_home = tmp / "blocked-home"
    blocked_state = blocked_home / parser_common.INSTALL_STATE_DIRECTORY.relative_to(Path.home())
    blocked_state.mkdir(parents=True)
    (blocked_state / parser_common.python_libraries_pinned_requirements_install_if_missing_then_import_common().INSTALL_FAILURE_FILE_NAME
     ).write_text("pip: blocked by the test", encoding="utf-8")
    blocked_packages = tmp / "blocked-packages"
    (blocked_packages / "markdown_it").mkdir(parents=True)
    (blocked_packages / "markdown_it" / "__init__.py").write_text(
        "raise ImportError('markdown-it-py blocked by the test')\n", encoding="utf-8")
    blocked_file = checkout / "docs" / "blocked.md"
    blocked_file.write_text(BROKEN_TEXT, encoding="utf-8")
    blocked_environment = {**CLEAN_ENVIRONMENT, "PYTHONPATH": str(blocked_packages), "HOME": str(blocked_home)}
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload_for(checkout, "Write", blocked_file, {"content": BROKEN_TEXT})),
        capture_output=True, text=True, check=False, env=blocked_environment)
    check("without markdown-it-py, after a failed install, the hook reports the failure and exits 1",
          result.returncode == 1 and result.stdout.strip() == ""
          and "markdown-it-py is missing on" in result.stderr
          and "pip: blocked by the test" in result.stderr,
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
          and "git check-ignore -q -- notes.md in" in result.stderr
          and "failed (exit 128" in result.stderr
          and "the Write itself succeeded." in result.stderr,
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
          and "git check-ignore -q -- " in result.stderr
          and "could not start git" in result.stderr,
          f"exit {result.returncode}: {result.stdout + result.stderr}")

    # The hook without the shared module it loads its git helpers from.
    hook_without_shared_module = tmp / "hook-without-its-git-helpers" / "scripts" / HOOK_PATH.name
    hook_without_shared_module.parent.mkdir(parents=True)
    shutil.copy(str(HOOK_PATH), str(hook_without_shared_module))
    lone_file = checkout / "docs" / "lone-hook.md"
    lone_file.write_text(BROKEN_TEXT, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(hook_without_shared_module)],
        input=json.dumps(payload_for(checkout, "Write", lone_file, {"content": BROKEN_TEXT})),
        capture_output=True, text=True, check=False, env=CLEAN_ENVIRONMENT)
    check("a shared git-helper module that fails to load is reported on stderr, exit 1",
          reported(result, "FileNotFoundError")
          and "edited-file-path-within-checkout-root-and-git-check-ignore-common.py" in result.stderr,
          f"exit {result.returncode}: {result.stdout + result.stderr}")

    outside_file = tmp / "outside" / "elsewhere.md"
    result = write_then_run(checkout, outside_file, BROKEN_TEXT)
    check("a Markdown file outside the session's checkout is silent", silent(result),
          result.stdout + result.stderr)

    undecodable_file = checkout / "docs" / "latin1.md"
    undecodable_file.write_bytes(b"One line \xe9\nand another.\n")
    result = run_hook(payload_for(checkout, "Write", undecodable_file, {"content": ""}))
    check("a file that is not UTF-8 is silent", silent(result), result.stdout + result.stderr)

    for case_name, payload, fault_words in (
            ("a payload that does not parse as JSON", "{not json", "JSONDecodeError"),
            ("a payload that is a JSON list", "[1, 2]", "JSON, but not an object"),
            ("an empty payload", "", "JSONDecodeError")):
        result = run_hook(payload)
        check(f"{case_name} is reported on stderr, exit 1",
              reported(result, fault_words), result.stdout + result.stderr)

    # A Write payload naming a file that is not there: reading it raises
    # FileNotFoundError, which only the top-level handler catches.
    vanished_file = checkout / "docs" / "vanished.md"
    result = run_hook(payload_for(checkout, "Write", vanished_file, {"content": BROKEN_TEXT}))
    check("a written file that cannot be read is reported on stderr, exit 1",
          reported(result, "FileNotFoundError"), result.stdout + result.stderr)

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
