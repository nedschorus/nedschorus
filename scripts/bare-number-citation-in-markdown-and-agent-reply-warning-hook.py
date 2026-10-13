#!/usr/bin/env python3
"""Note each pull request, GitHub issue or task cited by a bare number, and
each link to one of this repository's pull requests or GitHub issues whose
text is not that item's title, in Markdown just written by Edit or Write, or
in the agent's previous reply.

One program, two hook events, told apart by the payload's hook_event_name:

  PostToolUse on Edit and Write of a .md or .markdown file: scan the text just
      written, as style-guide-word-checker-markdown-edit-hook.py does. Edit
      scans new_string alone. Write scans only the lines HEAD does not already
      hold, so an edit to a file whose old bare numbers are kept on purpose
      (agent-only files such as those under scripts/ and .claude/hooks/) is
      not reported for text it did not write. A file outside the session's
      checkout, or one git ignores, is not scanned.
  UserPromptSubmit: when the user sends a message, scan the agent's reply
      to the previous turn, read from transcript_path, and hand the note to
      the agent with the user's message. A Stop hook would have to start a
      turn of its own to deliver the note; this costs no turn. The prompt
      being submitted is not yet in the transcript when the hook runs, so
      the transcript's last turn is the previous one. A transcript file that
      does not exist yet, at a session's first prompt, means no previous
      reply. Which records start a turn is decided by
      is_human_or_parent_message() from absence-claim-locator-reminder-hook.py,
      so the two hooks agree on what a turn is.

A BARE REFERENCE is an ID-type word followed by a number (PR, pull request,
issue, GHI or task, any case, optionally plural, optionally with `#`), or a
`#` followed by 2 to 5 digits that does not follow `&` or a word character,
which keeps an HTML entity and a URL's fragment out. A plain number never
matches. Not scanned: fenced code blocks, a block quote's included, inline
code spans, a whole Markdown link `[text](target "title")` (its text included:
a link is already a citation that can be opened), a bare URL, and a line a
program reads: one that starts with `supports-issues:` or `issue-marker:`, or
is, whole, one of ghi-info's reply lines, which ghi-info-ask.py parses
(`verdict: related #<n>,#<m>`, `read #<n>, #<m>`). A fence opened inside a
block quote closes where the block quote ends. A skipped span is blanked to a
barrier character no match can cross, so `PR [title](url) 2 hours` is not read
as "PR 2". A reference followed at once by its name, a complete quoted name or
a complete Markdown link, as the project's citation form for a task gives it
(task #<number>, "<subject>"), is not reported; a quote that closes a quotation
around the reference, or a bracket that starts no link, names nothing.

A LINK TITLE is checked for a Markdown link outside code whose target is
https://github.com/nedschorus/nedschorus/pull/<n> or .../issues/<n> and whose
text has at least TITLE_ATTEMPT_WORDS_AT_LEAST words and is not a URL; shorter
text, such as "this PR" or "PR 1256", is no attempt at a title. The text and
the title GitHub reports are compared after surrounding quotes and whitespace
are stripped, runs of whitespace are made one space, Markdown backslash escapes
are undone and case is ignored; text that matches only with backticks removed
from both still matches. All titles come from one `gh api graphql` call per
run, with a timeout of GH_TIMEOUT_SECONDS, because the hook runs on every
prompt. When gh fails, times out or is not installed, titles are not checked
and the note says so in one line; nothing else changes. A number GitHub has no
item for is not reported.

OUTPUT is a note, never a refusal and never a blocked prompt:
hookSpecificOutput.additionalContext with the hook's event name, listing up to
HIT_LINES_LISTED_AT_MOST hits. The UserPromptSubmit half stays silent in a
headless `claude -p` child, told apart as agent-seat-due-task-raise-hook.py
does, where the prompt comes from a program, not from a reader of the reply.
Nothing found: nothing printed, exit 0. A fault: one line naming it on stderr,
nothing on stdout, exit 1. Claude Code records a hook's exit 1 as a
non-blocking error and keeps the write and the prompt; stderr after exit 0 is
recorded nowhere, so a fault reported that way would read as "no bare numbers".
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

MARKDOWN_SUFFIXES = (".md", ".markdown")
HIT_LINES_LISTED_AT_MOST = 10
GIT_TIMEOUT_SECONDS = 10
GH_TIMEOUT_SECONDS = 5
GITHUB_REPOSITORY_OWNER = "nedschorus"
GITHUB_REPOSITORY_NAME = "nedschorus"
TITLE_ATTEMPT_WORDS_AT_LEAST = 3
EXCERPT_CHARACTERS_EACH_SIDE = 40
REINCARNATION_OWNED_BY_CALLER_VARIABLE = "NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER"
SESSION_ATTENDED_VARIABLE = "CLAUDE_CODE_SESSION_ATTENDED"
SESSION_UNATTENDED_VALUE = "0"

ID_TYPE_WORD_FOLLOWED_BY_NUMBER = (
    r"\b(?:PRs?|pull\s+requests?|issues?|GHIs?|tasks?)(?:\s+#?|\s*#)\d+(?!\w)")
HASH_FOLLOWED_BY_TWO_TO_FIVE_DIGITS = r"(?<![&\w])#\d{2,5}(?![\w])"
# One alternation, so an ID-type word with `#` and digits is one hit, not also a second hit for the `#` and digits alone.
BARE_REFERENCE_PATTERN = re.compile(
    ID_TYPE_WORD_FOLLOWED_BY_NUMBER + "|" + HASH_FOLLOWED_BY_TWO_TO_FIVE_DIGITS,
    re.IGNORECASE)
FENCE_PATTERN = re.compile(r"^\s*(?:>\s?)*\s*(?:[-*+]\s+|\d+[.)]\s+)?(`{3,}|~{3,})")
ISSUE_NUMBER_LIST = r"#\d+(?:[ \t]*,[ \t]*#\d+)*"
# ghi-info tags each closed issue in a reading list with "(closed <date>)" after its number.
READING_LIST_ENTRY = r"#\d+(?:[ \t]*\(closed[ \t]+\d{4}-\d{2}-\d{2}\))?"
READING_LIST = READING_LIST_ENTRY + r"(?:[ \t]*,[ \t]*" + READING_LIST_ENTRY + r")*"
# ghi-info's two reply shapes count only as whole lines, so a sentence that starts "Read #<n> before ..." is still read.
PROGRAM_READ_LINE_PATTERN = re.compile(
    r"^\s*(?:(?:supports-issues|issue-marker):"
    r"|verdict:[ \t]*(?:(?:too-similar|related)[ \t]*" + ISSUE_NUMBER_LIST + r"|unrelated)[ \t]*$"
    r"|read[ \t]+" + READING_LIST + r"[ \t]*\.?[ \t]*$)",
    re.IGNORECASE)
BLOCK_QUOTE_LINE_PATTERN = re.compile(r"^\s*>")
INLINE_CODE_PATTERN = re.compile(r"(`+)(?:(?!\1).)+?\1")
# Link text may hold one level of brackets, a target one level of parentheses, and a title any of the three quotings.
MARKDOWN_LINK_PATTERN = re.compile(
    r"!?\[(?:[^\[\]\n]|\[[^\[\]\n]*\])*\]\((?:[^()\s]|\([^()\s]*\))*"
    r"(?:\s+(?:\"[^\"\n]*\"|'[^'\n]*'|\([^()\n]*\)))?\s*\)")
# A double quote ends a URL, so a quoted URL's closing double quote stays in the line and is counted; an apostrophe is legal inside a URL.
BARE_URL_PATTERN = re.compile(r"<?\b[a-z][a-z0-9+.-]*://[^\s>\"]+>?", re.IGNORECASE)
# What may stand between a reference and its name.
NAME_SEPARATOR_PATTERN = re.compile(r"[ \t]*[,:\u2014\u2013-]?[ \t]*")
STRAIGHT_QUOTED_NAME_PATTERN = re.compile(r"\"[^\"\n]+\"")
CURLY_QUOTED_NAME_PATTERN = re.compile(r"\u201c[^\u201d\n]+\u201d")
LINK_TEXT_AND_TARGET_PATTERN = re.compile(
    r"\[(?P<text>(?:[^\[\]\n]|\[[^\[\]\n]*\])*)\]\((?P<target>(?:[^()\s]|\([^()\s]*\))*)")
REPOSITORY_ITEM_URL_PATTERN = re.compile(
    r"^<?https://github\.com/" + GITHUB_REPOSITORY_OWNER + "/" + GITHUB_REPOSITORY_NAME
    + r"/(?:pull|issues)/(?P<number>\d+)(?:[/?#]\S*)?>?$", re.IGNORECASE)
MARKDOWN_BACKSLASH_ESCAPE_PATTERN = re.compile(r"\\([!-/:-@\[-`{-~])")
SURROUNDING_QUOTE_PAIRS = (('"', '"'), ("'", "'"), ("\u201c", "\u201d"), ("\u2018", "\u2019"))
# Not whitespace and not a word character, so no match can run across a skipped span.
MASK_BARRIER_CHARACTER = "\x00"

MARKDOWN_OPENING_LINES = (
    "bare-number-citation-in-markdown-and-agent-reply-warning-hook: the text just written to {path} cites {count} pull "
    "request(s), GitHub issue(s) or task(s) by a bare number. A number alone tells a "
    "reader almost nothing; a title and a link are what a reader can read and open.",
    "Cite each one by its ID-type and its name, as a clickable link where it can be "
    "opened: PR [title](url), not a bare number.",
    "Look a title and link up with: gh pr view <number> --json title,url, or "
    "gh issue view <number> --json title,url. A task has no link: cite it by its "
    "ID-type and its subject in quotes, task #<number>, \"<subject>\"; read its "
    "subject from your task list, with TaskGet on the task's ID.",
    "Where the text shows the bare form as an example of what not to write, such "
    "as 'not PR #<number>', leave it as written.",
)
PREVIOUS_REPLY_OPENING_LINES = (
    "bare-number-citation-in-markdown-and-agent-reply-warning-hook: your previous reply to the user cited {count} pull "
    "request(s), GitHub issue(s) or task(s) by a bare number. A number alone tells a "
    "reader almost nothing; a title and a link are what a reader can read and open.",
    "From now on, cite each one by its ID-type and its name, as a clickable link where "
    "it can be opened: PR [title](url), not a bare number. In your next reply, cite in "
    "full each one listed below that you mention again.",
    "Look a title and link up with: gh pr view <number> --json title,url, or "
    "gh issue view <number> --json title,url. A task has no link: cite it by its "
    "ID-type and its subject in quotes, task #<number>, \"<subject>\"; read its "
    "subject from your task list, with TaskGet on the task's ID.",
    "Where your previous reply showed the bare form as an example of what not to write, "
    "such as 'not PR #<number>', nothing needs doing.",
)
MARKDOWN_TITLE_OPENING_LINES = (
    "bare-number-citation-in-markdown-and-agent-reply-warning-hook: the text just written to {path} links {count} pull "
    "request(s) or GitHub issue(s) under link text that is not the title GitHub reports. A reader "
    "takes link text to name what the link opens, so a wrong title points the reader at the wrong item.",
    "For each link listed below whose text was meant as the item's title, change the text to "
    "the title shown.",
    "For each link whose text describes the item in your own words instead, leave the text as written.",
)
PREVIOUS_REPLY_TITLE_OPENING_LINES = (
    "bare-number-citation-in-markdown-and-agent-reply-warning-hook: your previous reply to the user linked {count} pull "
    "request(s) or GitHub issue(s) under link text that is not the title GitHub reports. A reader "
    "takes link text to name what the link opens, so a wrong title points the reader at the wrong item.",
    "If your next reply mentions an item listed below whose link text was meant as its title, "
    "cite the item under the title shown.",
    "For a link whose text described the item in your own words instead, nothing needs doing.",
)
TITLES_NOT_CHECKED_LINE = (
    "bare-number-citation-in-markdown-and-agent-reply-warning-hook: link titles were not checked, "
    "because gh could not report them: {reason}. Nothing needs doing; the check runs again next time.")
WRITE_TITLE_HIT_LINE = '{path}:{line}: "{text}" links {url}; its title is "{title}"'
EXCERPT_TITLE_HIT_LINE = '"{text}" links {url}; its title is "{title}"'
WRITE_HIT_LINE = '{path}:{line}: "{reference}" in "{excerpt}"'
EXCERPT_HIT_LINE = '"{reference}" in "{excerpt}"'
MORE_HITS_LINE = ("{count} more not listed: reread the rest of the same text for "
                  "numbers cited the same way.")


class LinkTitleMismatch:
    def __init__(self, line_number, text, url, title):
        self.line_number = line_number
        self.text = text
        self.url = url
        self.title = title


class GithubTitlesUnavailable(Exception):
    """gh could not report the titles; the message says why."""


class BareReference:
    def __init__(self, line_number, reference, excerpt):
        self.line_number = line_number
        self.reference = reference
        self.excerpt = excerpt


def _blank(match):
    return MASK_BARRIER_CHARACTER * len(match.group(0))


def scannable_lines(text: str, keep_links=False):
    """Return the lines of text with every skipped part blanked to
    MASK_BARRIER_CHARACTER, or a skipped line emptied, so line numbers and
    columns still point into the original text. With keep_links, Markdown
    links and bare URLs are left in place."""
    lines = []
    fence = None
    fence_inside_block_quote = False
    for line in text.split("\n"):
        fence_match = FENCE_PATTERN.match(line)
        if fence is not None and fence_inside_block_quote and not BLOCK_QUOTE_LINE_PATTERN.match(line):
            fence = None
        if fence is not None:
            if (fence_match and fence_match.group(1)[0] == fence[0]
                    and len(fence_match.group(1)) >= len(fence)):
                fence = None
            lines.append("")
            continue
        if fence_match:
            fence = fence_match.group(1)
            fence_inside_block_quote = bool(BLOCK_QUOTE_LINE_PATTERN.match(line))
            lines.append("")
            continue
        if PROGRAM_READ_LINE_PATTERN.match(line):
            lines.append("")
            continue
        line = INLINE_CODE_PATTERN.sub(_blank, line)
        if not keep_links:
            line = MARKDOWN_LINK_PATTERN.sub(_blank, line)
            line = BARE_URL_PATTERN.sub(_blank, line)
        lines.append(line)
    return lines


def excerpt_around(line: str, start: int, end: int) -> str:
    before = line[max(0, start - EXCERPT_CHARACTERS_EACH_SIDE):start]
    after = line[end:end + EXCERPT_CHARACTERS_EACH_SIDE]
    excerpt = " ".join((before + line[start:end] + after).split())
    if start > EXCERPT_CHARACTERS_EACH_SIDE:
        excerpt = "..." + excerpt
    if end + EXCERPT_CHARACTERS_EACH_SIDE < len(line):
        excerpt += "..."
    return excerpt


def name_follows(line: str, masked_line: str, start: int, end: int) -> bool:
    """Whether the reference at line[start:end] is followed at once by its
    name: a complete quoted name or a complete Markdown link. A straight quote
    after an odd number of straight quotes closes a quotation, so it names
    nothing; the quotes are counted in masked_line, so a quote inside a code
    span does not count."""
    position = NAME_SEPARATOR_PATTERN.match(line, end).end()
    if MARKDOWN_LINK_PATTERN.match(line, position):
        return True
    if CURLY_QUOTED_NAME_PATTERN.match(line, position):
        return True
    return (masked_line.count('"', 0, start) % 2 == 0
            and STRAIGHT_QUOTED_NAME_PATTERN.match(line, position) is not None)


def bare_references_in(text: str, line_numbers_to_report=None):
    """Every bare reference in text, in reading order, numbering lines from 1.
    With line_numbers_to_report, only hits on those lines."""
    original_lines = text.split("\n")
    found = []
    for index, line in enumerate(scannable_lines(text)):
        line_number = index + 1
        if line_numbers_to_report is not None and line_number not in line_numbers_to_report:
            continue
        for match in BARE_REFERENCE_PATTERN.finditer(line):
            if name_follows(original_lines[index], line, match.start(), match.end()):
                continue
            found.append(BareReference(
                line_number, match.group(0),
                excerpt_around(original_lines[index], match.start(), match.end())))
    return found


def comparable_title(text: str) -> str:
    text = " ".join(text.split())
    for opening, closing in SURROUNDING_QUOTE_PAIRS:
        if len(text) >= 2 and text.startswith(opening) and text.endswith(closing):
            text = text[1:-1].strip()
            break
    return MARKDOWN_BACKSLASH_ESCAPE_PATTERN.sub(r"\1", text).casefold()


def titles_match(link_text: str, title: str) -> bool:
    link_text, title = comparable_title(link_text), comparable_title(title)
    return link_text == title or link_text.replace("`", "") == title.replace("`", "")


def is_title_attempt(link_text: str) -> bool:
    words = link_text.split()
    return (len(words) >= TITLE_ATTEMPT_WORDS_AT_LEAST
            and not BARE_URL_PATTERN.fullmatch(link_text.strip()))


def repository_item_links_in(text: str, line_numbers_to_report=None):
    """(line number, link text, URL, item number) for each link outside code
    to one of this repository's pull requests or issues whose text is an
    attempt at the item's title."""
    original_lines = text.split("\n")
    links = []
    for index, line in enumerate(scannable_lines(text, keep_links=True)):
        line_number = index + 1
        if line_numbers_to_report is not None and line_number not in line_numbers_to_report:
            continue
        for match in MARKDOWN_LINK_PATTERN.finditer(line):
            # An image's match starts at its "!", where this pattern does not match.
            parts = LINK_TEXT_AND_TARGET_PATTERN.match(
                original_lines[index], match.start())
            if parts is None:
                continue
            url_match = REPOSITORY_ITEM_URL_PATTERN.match(parts.group("target"))
            if url_match is None or not is_title_attempt(parts.group("text")):
                continue
            links.append((line_number, parts.group("text"), parts.group("target").strip("<>"),
                          int(url_match.group("number"))))
    return links


def github_titles(numbers, timeout_seconds=GH_TIMEOUT_SECONDS):
    """Map each number to its pull request's or issue's title, by one gh call;
    a number with no item maps to None. Raises GithubTitlesUnavailable."""
    fields = " ".join(
        f"n{number}: issueOrPullRequest(number: {number}) "
        "{ ... on Issue { title } ... on PullRequest { title } }"
        for number in sorted(set(numbers)))
    query = (f'query {{ repository(owner: "{GITHUB_REPOSITORY_OWNER}", '
             f'name: "{GITHUB_REPOSITORY_NAME}") {{ {fields} }} }}')
    try:
        completed = subprocess.run(
            ["gh", "api", "graphql", "-f", f"query={query}"], capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired:
        raise GithubTitlesUnavailable(f"gh did not answer within {timeout_seconds} seconds")
    except OSError as error:
        raise GithubTitlesUnavailable(f"gh could not be run: {error}")
    # A number with no item makes gh exit 1, but the other titles still arrive in data.
    try:
        repository = json.loads(completed.stdout)["data"]["repository"]
    except (ValueError, KeyError, TypeError):
        repository = None
    if not isinstance(repository, dict):
        detail = (completed.stderr.strip() or completed.stdout.strip()
                  or f"exit {completed.returncode}").splitlines()[0]
        raise GithubTitlesUnavailable(f"gh api graphql failed: {detail}")
    titles = {}
    for number in set(numbers):
        item = repository.get(f"n{number}")
        titles[number] = item.get("title") if isinstance(item, dict) else None
    return titles


def link_title_mismatches_in(text: str, line_numbers_to_report=None):
    """Return (mismatches, reason titles were not checked or None)."""
    links = repository_item_links_in(text, line_numbers_to_report)
    if not links:
        return [], None
    try:
        titles = github_titles([number for _, _, _, number in links])
    except GithubTitlesUnavailable as error:
        return [], str(error)
    mismatches = [
        LinkTitleMismatch(line_number, link_text, url, titles[number])
        for line_number, link_text, url, number in links
        if titles.get(number) is not None and not titles_match(link_text, titles[number])]
    return mismatches, None


def title_note_lines(opening_lines, mismatches, reason, path=None, with_line_numbers=False):
    if reason is not None:
        return [TITLES_NOT_CHECKED_LINE.format(reason=reason)]
    if not mismatches:
        return []
    lines = [line.format(path=path, count=len(mismatches)) for line in opening_lines]
    for mismatch in mismatches[:HIT_LINES_LISTED_AT_MOST]:
        hit_line = WRITE_TITLE_HIT_LINE if with_line_numbers else EXCERPT_TITLE_HIT_LINE
        lines.append(hit_line.format(path=path, line=mismatch.line_number, text=mismatch.text,
                                     url=mismatch.url, title=mismatch.title))
    if len(mismatches) > HIT_LINES_LISTED_AT_MOST:
        lines.append(MORE_HITS_LINE.format(count=len(mismatches) - HIT_LINES_LISTED_AT_MOST))
    return lines


def note_text(opening_lines, references, path=None, with_line_numbers=False) -> str:
    lines = [line.format(path=path, count=len(references)) for line in opening_lines]
    for reference in references[:HIT_LINES_LISTED_AT_MOST]:
        if with_line_numbers:
            lines.append(WRITE_HIT_LINE.format(
                path=path, line=reference.line_number,
                reference=reference.reference, excerpt=reference.excerpt))
        else:
            lines.append(EXCERPT_HIT_LINE.format(
                reference=reference.reference, excerpt=reference.excerpt))
    if len(references) > HIT_LINES_LISTED_AT_MOST:
        lines.append(MORE_HITS_LINE.format(count=len(references) - HIT_LINES_LISTED_AT_MOST))
    return "\n".join(lines)


def hook_output(event_name: str, text: str) -> str:
    return json.dumps({"hookSpecificOutput": {
        "hookEventName": event_name, "additionalContext": text}}, ensure_ascii=False)


# --- PostToolUse: the Markdown file just written ---------------------------

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


def markdown_edit_note(payload: dict):
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if tool_name not in ("Edit", "Write") or not isinstance(tool_input, dict):
        return None
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path.lower().endswith(MARKDOWN_SUFFIXES):
        return None
    working_directory = payload.get("cwd")
    if not isinstance(working_directory, str) or not Path(working_directory).is_dir():
        return None
    located = checkout_relative_path(file_path, Path(working_directory))
    if located is None:
        return None
    root, relative_path = located

    if tool_name == "Edit":
        new_string = tool_input.get("new_string")
        if not isinstance(new_string, str) or not new_string.strip():
            return None
        if not git_would_track(root, relative_path):
            return None
        references = bare_references_in(new_string)
        mismatches, reason = link_title_mismatches_in(new_string)
        with_line_numbers = False
    else:
        content = tool_input.get("content")
        if not isinstance(content, str) or not content.strip():
            return None
        committed = run_git(["show", "HEAD:" + relative_path], root)
        if committed.returncode == 0:
            committed_lines = set(line.rstrip() for line in committed.stdout.split("\n"))
        elif git_would_track(root, relative_path):
            committed_lines = set()
        else:
            return None
        new_line_numbers = set(
            index + 1 for index, line in enumerate(content.split("\n"))
            if line.rstrip() not in committed_lines)
        references = bare_references_in(content, new_line_numbers)
        mismatches, reason = link_title_mismatches_in(content, new_line_numbers)
        with_line_numbers = True
    sections = title_note_lines(MARKDOWN_TITLE_OPENING_LINES, mismatches, reason,
                                relative_path, with_line_numbers)
    if references:
        sections.insert(0, note_text(
            MARKDOWN_OPENING_LINES, references, relative_path, with_line_numbers))
    if not sections:
        return None
    return hook_output("PostToolUse", "\n".join(sections))


# --- UserPromptSubmit: the agent's previous reply -----------------------------

def _load_absence_claim_hook():
    specification = importlib.util.spec_from_file_location(
        "absence_claim_locator_reminder_hook",
        Path(__file__).resolve().with_name("absence-claim-locator-reminder-hook.py"))
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def previous_reply(transcript_path: Path, is_turn_start) -> str:
    """The text of the agent's last message in the transcript's last turn,
    which, while the prompt being submitted is not yet written, is the
    previous turn."""
    records = []
    with open(transcript_path, encoding="utf-8") as transcript:
        for line in transcript:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict):
                records.append(record)
    starts = [index for index, record in enumerate(records) if is_turn_start(record)]
    turn = records[starts[-1] + 1:] if starts else records
    last_text_message_id = None
    texts_by_message = {}
    for record in turn:
        if record.get("type") != "assistant":
            continue
        message = record.get("message", {})
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                message_id = message.get("id") or id(record)
                texts_by_message.setdefault(message_id, []).append(block.get("text", ""))
                last_text_message_id = message_id
    return "\n".join(texts_by_message.get(last_text_message_id, []))


def previous_reply_note(payload: dict, environment):
    if (environment.get(REINCARNATION_OWNED_BY_CALLER_VARIABLE)
            or environment.get(SESSION_ATTENDED_VARIABLE) == SESSION_UNATTENDED_VALUE):
        return None
    transcript_path = payload.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path:
        return None
    transcript_file = Path(transcript_path).expanduser()
    if not transcript_file.exists():
        return None
    reply = previous_reply(transcript_file, _load_absence_claim_hook().is_human_or_parent_message)
    if not reply.strip():
        return None
    references = bare_references_in(reply)
    mismatches, reason = link_title_mismatches_in(reply)
    sections = title_note_lines(PREVIOUS_REPLY_TITLE_OPENING_LINES, mismatches, reason)
    if references:
        sections.insert(0, note_text(PREVIOUS_REPLY_OPENING_LINES, references))
    if not sections:
        return None
    return hook_output("UserPromptSubmit", "\n".join(sections))


def run(stdin_text: str, environment):
    """Return the text to print, or None."""
    payload = json.loads(stdin_text or "{}")
    if not isinstance(payload, dict):
        return None
    event_name = payload.get("hook_event_name")
    if event_name == "PostToolUse":
        return markdown_edit_note(payload)
    if event_name == "UserPromptSubmit":
        return previous_reply_note(payload, environment)
    return None


def main() -> int:
    try:
        output = run(sys.stdin.read(), os.environ)
        if output is not None:
            print(output)
    except Exception as error:
        try:
            print(f"bare-number-citation-in-markdown-and-agent-reply-warning-hook: "
                  f"no check was made: {type(error).__name__}: {error}", file=sys.stderr)
        except Exception:
            pass
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
