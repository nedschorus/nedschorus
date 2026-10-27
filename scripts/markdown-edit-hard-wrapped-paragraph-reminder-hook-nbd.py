#!/usr/bin/env python3
"""Join the lines of each Markdown paragraph an Edit or a Write just broke across lines, or,
where the hook must not or cannot, tell the agent to join them.

Use hookSpecificOutput.additionalContext: successful PostToolUse plain stdout reaches only the debug log.
Read cwd from the payload; CLAUDE_PROJECT_DIR can name a different checkout in a forked session.

The whole file is read from disk after the tool ran, for Edit as for Write, so an
Edit inside a fenced code block is judged with the fence visible. Only a broken
paragraph the tool wrote is handled: for a Write, any in the file; for an Edit, one
whose lines overlap a line the Edit added. The added lines come from a line diff of each
replacement the Edit made in the payload's tool_response.originalFile (see
edit_added_line_numbers): a search for new_string in the file would also find copies the
Edit did not write, and tool_response.structuredPatch is built after leading tabs are
turned into spaces, so it drops a line whose only change is a tab. A broken paragraph
the agent did not touch is left alone: the agent did not write it, and someone may have
broken its lines on purpose. An Edit that only deleted lines adds none and is left alone. An Edit
of a file holding a broken paragraph, whose added lines cannot be found that way,
gets one line on stderr and exit 1, a non-blocking hook error, so the agent is told the
check was not made. An Edit of a file holding no broken paragraph needs no diff to be
judged, so a payload lacking that text there is not reported.

Which lines form a paragraph is decided by markdown-it-py's CommonMark parser, not
by this file: a paragraph, in a list item or at the top level, is broken when its
inline content holds a soft line break. markdown-it-py is pinned in
nc-systems/general-tools/python-libraries-pinned-requirements.txt; when it is
missing, the shared Markdown parser module installs the pinned file through the
shared install module, for the python3 the hooks run. When that install fails, the hook writes to
stderr what failed, what the install printed and the command that installs it
by hand, and exits 1, which Claude Code shows as a non-blocking hook error.

A file holding display math ($$) or a footnote definition ([^label]:) is left alone:
CommonMark reads both as paragraphs, and judging their line breaks needs rules this
hook does not carry, so it stays silent rather than join lines that must stay apart.

The join. The hook decides whether a file is guarded by calling instruction-file-guard.py's
own is_protected, is_reusable_prompt and is_reviewed_document, as
.claude/hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook.py does, so the
three cannot disagree. In a guarded file it never joins: a join there is a change the user
has not approved, so it gives the reminder alone. In any other file it joins each soft line
break of the broken paragraphs the tool wrote: the line before the break loses its trailing
spaces and tabs, the line after loses its indentation, and one space stands between them.
A hard break the author chose (two trailing spaces, a trailing backslash or a trailing <br>)
is kept. It then tells the agent which lines it joined and to read the file again before
its next Edit of it, since Claude Code refuses an Edit made from a read older than the
file. It gives the reminder instead, with the reason it did not join, when any of these
holds; each leaves the file as the tool wrote it:
- the guard's code would not load or raised, so the hook cannot tell whether it is guarded;
- the file is a symbolic link, which the replacement would turn into a plain file;
- the file holds a carriage return, whose line ends the join does not handle;
- the tool's payload lacks the text the tool wrote, so the hook cannot tell whether the
  file changed since;
- the file on disk is not the text the tool's payload says it wrote: something changed
  it since, or, for an Edit, Claude Code wrote curly quotes the agent typed straight, and
  the hook cannot tell which;
- a paragraph's line count and its line breaks do not match, as when an image or a code
  span holds a line break, so the hook cannot tell which line ends to join;
- the joined text does not parse as the same Markdown with only line breaks turned into
  spaces;
- another run of this hook holds the lock on the file's directory for over
  LINE_JOIN_DIRECTORY_LOCK_WAIT_SECONDS;
- the file changed between the hook's read and its write;
- writing the joined text failed.

How the write can fail, and the harm it can do. The hook writes the joined text to a
temporary file beside the target, gives it the target's permission bits, and moves it over
the target with os.replace, holding an flock on the target's directory so two runs of this
hook cannot interleave; just before the move it reads the target again and gives up when it
differs from what it joined. A failed write leaves the target as it was and removes the
temporary file, except when the hook is killed, as by its timeout, between making the
temporary file and the move: then a file named .<name>.<random>.hard-wrap-join is left
beside the target, and git shows it as untracked. The harm: a program other than this hook that writes the target in the
instant between that last read and the move loses its write, since only this hook takes
the lock; the move gives the target a new inode, so a hard link to the old one keeps the
unjoined text, and the file's owner becomes the user the hook runs as; an agent that skips
the re-read has its next Edit of the file refused once by Claude Code; and a hook that runs
beside this one and reads the file may report line numbers from before the join.

A fault, such as stdin that is not a JSON object, a written file that cannot be read
or any exception: one line on stderr naming the hook and the fault, nothing on stdout,
exit 1. Claude Code records a PostToolUse exit 1 as a non-blocking error and keeps the
write; exit 0 would read as "no broken paragraph found". A file that is not UTF-8 is
not a fault: the hook judges only UTF-8 text, and stays silent on other bytes."""

import difflib
import fcntl
import functools
import importlib.util
import json
import os
import re
import shutil
import socket
import sys
import tempfile
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

REMINDER_LINE_SAYING_WHY_BROKEN_PARAGRAPH_LINES_WERE_NOT_JOINED = (
    "\nThis hook joins such lines itself when it safely can; it did not join these, because {reason}.")

MARKDOWN_BROKEN_LINES_JOINED_BY_HOOK_MESSAGE = (
    "markdown-edit-hard-wrapped-paragraph-reminder: the text you just wrote in {path} held "
    "paragraphs or list items broken across lines, and this hook has joined each into one "
    "line, changing only the line breaks and the spaces around them: {joins}.\n"
    "Read {path} again before your next Edit of it: the hook changed the file after your "
    "{tool_name}, so Claude Code refuses an Edit made from your earlier read, and every line "
    "below a joined paragraph has moved up.\n"
    "In every Markdown file you write from now on, write each paragraph, list item and "
    "table row as one line, however long; break lines only where Markdown needs a break."
)

# Long enough for another run of this hook to finish its write, well inside the hook's
# 30-second timeout in .claude/settings.json.
LINE_JOIN_DIRECTORY_LOCK_WAIT_SECONDS = 5.0
JOIN_LOCK_POLL_SECONDS = 0.05
# A Write of a long hard-wrapped document joins thousands of paragraphs; naming them all
# would fill the agent's context.
LINE_JOINS_LISTED_IN_MESSAGE_AT_MOST = 20

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


@functools.cache
def markdown_commonmark_parser_with_tables_common():
    """Return the shared Markdown parser module, loaded by path when first needed."""
    specification = importlib.util.spec_from_file_location(
        "markdown_commonmark_parser_with_tables_common",
        Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
        / "markdown-commonmark-parser-with-tables-common.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def parser_missing_message(error, host=None, python_version=None):
    """Return the stderr text for markdown-it-py missing on this machine and its install failed."""
    host = host or socket.gethostname().split(".")[0]
    install = markdown_commonmark_parser_with_tables_common().python_libraries_pinned_requirements_install_if_missing_then_import_common()
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
    parser = markdown_commonmark_parser_with_tables_common().markdown_parser()
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


class BrokenParagraphLinesNotJoinedError(Exception):
    """Why the hook left a broken paragraph for the agent to join; str() is the reason,
    worded to follow "because"."""


def file_is_guarded_by_instruction_file_guard(file_path: str) -> bool:
    """Whether instruction-file-guard.py refuses an unapproved write to file_path. Raises
    whatever loading the guard or its checks raise."""
    guard = _load_instruction_file_guard_hook_module()
    return (guard.is_protected(file_path) or guard.is_reusable_prompt(file_path)
            or guard.is_reviewed_document(file_path))


def _load_instruction_file_guard_hook_module():
    specification = importlib.util.spec_from_file_location(
        "instruction_file_guard",
        Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "instruction-file-guard.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def compute_file_texts_expected_after_edit_or_write_tool_call(tool_name, tool_input, tool_response) -> list:
    """The texts the file holds if nothing changed it after the tool; empty when the payload
    lacks what they are built from. An Edit with an empty new_string and an old_string not
    ending in a newline may also have removed the newline after it, so both are given."""
    if tool_name == "Write":
        content = tool_input.get("content")
        return [content] if isinstance(content, str) else []
    if not isinstance(tool_response, dict):
        return []
    original = tool_response.get("originalFile")
    old, new = tool_response.get("oldString"), tool_response.get("newString")
    replace_all = tool_response.get("replaceAll")
    if not (isinstance(old, str) and isinstance(new, str) and isinstance(replace_all, bool)):
        return []
    if not old:
        return [new]
    if not isinstance(original, str):
        return []
    removed_texts = [old, old + "\n"] if not new and not old.endswith("\n") else [old]
    return [original.replace(removed, new) if replace_all else original.replace(removed, new, 1)
            for removed in removed_texts if removed in original]


def soft_line_breaks_to_join(text: str, broken_ranges) -> list:
    """The 0-based numbers of the lines, within broken_ranges, whose line break is a soft
    one counts_as_line_break counts, so that the line is to be joined to the next.
    Raises BrokenParagraphLinesNotJoinedError when a paragraph's line breaks cannot be matched to its lines."""
    tokens = markdown_commonmark_parser_with_tables_common().markdown_parser().parse(
        front_matter_blanked(text))
    wanted = set(map(tuple, broken_ranges))
    lines_to_join = []
    for opener, token in zip(tokens, tokens[1:]):
        if not (opener.type == "paragraph_open" and token.type == "inline" and tuple(opener.map) in wanted):
            continue
        start, end = opener.map
        children = token.children or []
        breaks = [child_position for child_position, child in enumerate(children)
                  if child.type in ("softbreak", "hardbreak")]
        if len(breaks) != end - start - 1:
            raise BrokenParagraphLinesNotJoinedError(
                f"the paragraph on lines {start + 1} to {end} has {end - start - 1} line ends but "
                f"{len(breaks)} line breaks the parser can place, as when an image or a code span "
                f"holds a line break")
        lines_to_join += [start + index for index, child_position in enumerate(breaks)
                          if children[child_position].type == "softbreak"
                          and counts_as_line_break(children, child_position)]
    return sorted(lines_to_join)


def text_with_lines_joined(text: str, lines_to_join) -> str:
    """text with each line in lines_to_join joined to the line after it by one space."""
    lines = text.split("\n")
    joined = []
    joining = set(lines_to_join)
    for number, line in enumerate(lines):
        if joined and number - 1 in joining:
            joined[-1] = joined[-1].rstrip(" \t") + " " + line.lstrip(" \t")
        else:
            joined.append(line)
    return "\n".join(joined)


def markdown_structure_with_line_breaks_as_spaces(text: str) -> list:
    """What text parses to, leaving out where each block sits and how whitespace runs
    inside paragraphs and headings are spelled."""
    tokens = markdown_commonmark_parser_with_tables_common().markdown_parser().parse(
        front_matter_blanked(text))
    return [(token.type, token.tag, token.nesting, token.markup, token.info, token.attrs,
             " ".join(token.content.split()) if token.type == "inline" else token.content)
            for token in tokens]


def replace_file_text_if_unchanged_since_read(path: Path, text_read: str, new_text: str) -> None:
    """Replace path's bytes with new_text when path still holds text_read, holding the
    lock on path's directory that every run of this hook takes. Raises BrokenParagraphLinesNotJoinedError, with
    the file left as it was, when the lock is not had in time, when path changed, or when
    the write fails."""
    directory = path.parent
    try:
        directory_descriptor = os.open(directory, os.O_RDONLY)
    except OSError as error:
        raise BrokenParagraphLinesNotJoinedError(f"the hook could not open {directory} to lock it: {error}") from error
    try:
        deadline = time.monotonic() + LINE_JOIN_DIRECTORY_LOCK_WAIT_SECONDS
        while True:
            try:
                fcntl.flock(directory_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise BrokenParagraphLinesNotJoinedError(
                        f"another run of this hook held the lock on {directory} for over "
                        f"{LINE_JOIN_DIRECTORY_LOCK_WAIT_SECONDS:g} seconds") from None
                time.sleep(JOIN_LOCK_POLL_SECONDS)
        _replace_file_text_if_unchanged_since_read_under_lock(path, text_read, new_text)
    finally:
        os.close(directory_descriptor)


def _replace_file_text_if_unchanged_since_read_under_lock(path: Path, text_read: str, new_text: str) -> None:
    temporary_path = None
    try:
        if path.read_bytes() != text_read.encode("utf-8"):
            raise BrokenParagraphLinesNotJoinedError("the file changed while the hook was joining its lines")
        descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.",
                                                      suffix=".hard-wrap-join")
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(new_text.encode("utf-8"))
        shutil.copymode(path, temporary_path)
        os.replace(temporary_path, path)
    except OSError as error:
        raise BrokenParagraphLinesNotJoinedError(f"writing the joined text failed: {type(error).__name__}: {error}") from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def join_broken_markdown_paragraphs_in_file_and_list_joins(path: Path, text: str, broken_ranges, texts_written) -> list:
    """Join the broken paragraphs of broken_ranges in path, which held text when read, and
    return the joins as (first line, last line, joined line), 1-based, the first two
    numbered as before the join and the third as after it. Raises BrokenParagraphLinesNotJoinedError, with the
    file left as it was, for each case the module docstring lists after the guard's."""
    if path.is_symlink():
        raise BrokenParagraphLinesNotJoinedError("the file is a symbolic link, which the hook's write would replace "
                          "with a plain file")
    if "\r" in text:
        raise BrokenParagraphLinesNotJoinedError("the file holds a carriage return, and the hook joins only lines "
                          "that end in a bare line feed")
    if not texts_written:
        raise BrokenParagraphLinesNotJoinedError("the tool's payload does not hold the text the tool wrote, so the hook "
                          "cannot tell whether the file changed since")
    if text not in texts_written:
        raise BrokenParagraphLinesNotJoinedError("the file on disk is not the text the tool's payload says it wrote, "
                          "so it may have changed since")
    lines_to_join = soft_line_breaks_to_join(text, broken_ranges)
    new_text = text_with_lines_joined(text, lines_to_join)
    if markdown_structure_with_line_breaks_as_spaces(new_text) != markdown_structure_with_line_breaks_as_spaces(text):
        raise BrokenParagraphLinesNotJoinedError("the joined text would not parse as the same Markdown")
    replace_file_text_if_unchanged_since_read(path, text, new_text)
    joins = []
    removed_before = 0
    for line in lines_to_join:
        if joins and joins[-1][1] == line + 1:
            joins[-1][1] = line + 2
        else:
            joins.append([line + 1, line + 2, line + 1 - removed_before])
        removed_before += 1
    return [tuple(join) for join in joins]


def describe_which_lines_were_joined(joins) -> str:
    """The joins as the agent reads them: "lines 3 to 4 into line 3; lines 7 to 9 into line 6",
    the first LINE_JOINS_LISTED_IN_MESSAGE_AT_MOST of them, then how many more there were."""
    described = "; ".join(f"lines {first} to {last} into line {joined}"
                          for first, last, joined in joins[:LINE_JOINS_LISTED_IN_MESSAGE_AT_MOST])
    if len(joins) > LINE_JOINS_LISTED_IN_MESSAGE_AT_MOST:
        described += f"; and {len(joins) - LINE_JOINS_LISTED_IN_MESSAGE_AT_MOST} more"
    return described


def main() -> int:
    payload = json.loads(sys.stdin.read())
    if not isinstance(payload, dict):
        raise ValueError("the input on the hook's stdin is JSON, but not an object")
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
    except markdown_commonmark_parser_with_tables_common().MarkdownParserMissing as error:
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

    message = REMINDER_MESSAGE.format(path=relative_path)
    try:
        guarded = file_is_guarded_by_instruction_file_guard(file_path)
    except Exception as error:
        message += REMINDER_LINE_SAYING_WHY_BROKEN_PARAGRAPH_LINES_WERE_NOT_JOINED.format(reason=(
            f"it could not tell whether the instruction-file guard protects {relative_path}: "
            f"{type(error).__name__}: {error}"))
    else:
        if not guarded:
            try:
                joins = join_broken_markdown_paragraphs_in_file_and_list_joins(
                    Path(file_path), text, broken_ranges,
                    compute_file_texts_expected_after_edit_or_write_tool_call(tool_name, tool_input, payload.get("tool_response")))
            except BrokenParagraphLinesNotJoinedError as refusal:
                message += REMINDER_LINE_SAYING_WHY_BROKEN_PARAGRAPH_LINES_WERE_NOT_JOINED.format(reason=refusal)
            else:
                message = MARKDOWN_BROKEN_LINES_JOINED_BY_HOOK_MESSAGE.format(path=relative_path, tool_name=tool_name,
                                                joins=describe_which_lines_were_joined(joins))
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": message,
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
