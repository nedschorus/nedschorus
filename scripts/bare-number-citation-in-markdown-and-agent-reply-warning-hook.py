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
around the reference, or a bracket that starts no link, names nothing. Emphasis
markers may stand on either side of the separator, so a bold label such as
`**GHI <n>:** [title](url)` names its item. A quoted name that names a
reference is not scanned itself, so a task subject that mentions another item
is not reported; a bare reference after the name still is.

A LINK TITLE is checked for a Markdown link outside code whose target is
https://github.com/nedschorus/nedschorus/pull/<n> or .../issues/<n>, not a
comment or a review in it, and whose text has at least
TITLE_ATTEMPT_WORDS_AT_LEAST words; shorter text, such as "this PR" or
"PR <number>", is no attempt at a title, and a URL is one word. The text and
the title GitHub reports are compared after surrounding quotes and whitespace
are stripped, runs of whitespace are made one space, Markdown backslash escapes
are undone and case is ignored; text that matches only with backticks removed
from both still matches. Link text may put an ID prefix before the title,
such as `PR <n>, "<title>"`: PR, GHI or issue and a number, or `#` and a
number, then a comma, colon, dash or space. The prefix is accepted only when
its number is the URL's; when the number differs, the link is noted, and the
note says the number is wrong. All titles come from one `gh api graphql` call per
run, with a timeout of GH_TIMEOUT_SECONDS, because the hook runs on every
prompt. When gh fails, times out, is not installed, or reports any error other
than an item that does not exist, titles are not checked and the note says so
in one line; nothing else changes. A number GitHub has no item for is not
reported.

OUTPUT is a note, never a refusal and never a blocked prompt:
hookSpecificOutput.additionalContext with the hook's event name, listing up to
HIT_LINES_LISTED_AT_MOST hits. The UserPromptSubmit half stays silent in a
headless `claude -p` child, told apart as agent-seat-due-task-raise-hook.py
does, where the prompt comes from a program, not from a reader of the reply.

ONE NOTE PER REPLY. A reply is the assistant message Claude Code assembles
from transcript records sharing one message id. The UserPromptSubmit half
keeps, per agent-session, a record in the temporary directory of the last
reply it noted, and does not note that reply again: a task notification or a
message from another session submits a prompt with no reply in between. A
reply with no message id is always noted, so no two replies can share a key.
The bare-number part of the note is sent in full once per agent-session, and
again after each compaction, which may drop it from the agent's context; after
that its instructions shrink to one line, and the hits are listed as before.
The link-title part is always sent in full. A record that cannot be read or
written leaves the note as it would be without the record and adds a line
saying so. A reply with nothing to note reports no record failure: no note is
lost, and the next reply that has a note reports the failure.
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
import tempfile
from pathlib import Path

MARKDOWN_SUFFIXES = (".md", ".markdown")
HIT_LINES_LISTED_AT_MOST = 10
GH_TIMEOUT_SECONDS = 5
GITHUB_REPOSITORY_OWNER = "nedschorus"
GITHUB_REPOSITORY_NAME = "nedschorus"
TITLE_ATTEMPT_WORDS_AT_LEAST = 3
EXCERPT_CHARACTERS_EACH_SIDE = 40
REINCARNATION_OWNED_BY_CALLER_VARIABLE = "NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER"
SESSION_ATTENDED_VARIABLE = "CLAUDE_CODE_SESSION_ATTENDED"
SESSION_UNATTENDED_VALUE = "0"
SESSION_ID_SAFE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
NOTE_RECORD_DIRECTORY_NAME = "bare-number-citation-in-markdown-and-agent-reply-warning-hook-state"

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
EMPHASIS_MARKER = r"(?:\*\*|__|\*|_)?"
NAME_SEPARATOR_PATTERN = re.compile(
    r"[ \t]*" + EMPHASIS_MARKER + r"[ \t]*[,:\u2014\u2013-]?[ \t]*" + EMPHASIS_MARKER + r"[ \t]*")
STRAIGHT_QUOTED_NAME_PATTERN = re.compile(r"\"[^\"\n]+\"")
CURLY_QUOTED_NAME_PATTERN = re.compile(r"\u201c[^\u201d\n]+\u201d")
LINK_TEXT_AND_TARGET_PATTERN = re.compile(
    r"\[(?P<text>(?:[^\[\]\n]|\[[^\[\]\n]*\])*)\]\((?P<target>(?:[^()\s]|\([^()\s]*\))*)")
REPOSITORY_ITEM_URL_PATTERN = re.compile(
    r"^<?https://github\.com/" + GITHUB_REPOSITORY_OWNER + "/" + GITHUB_REPOSITORY_NAME
    + r"/(?:pull|issues)/(?P<number>\d+)"
    # A link to a comment or a review, a review comment on the files tab
    # (#r<id>) included, cites that comment, not the item's title.
    + r"(?![^#]*#(?:issuecomment-|pullrequestreview-|discussion_r|r\d))(?:[/?#]\S*)?>?$",
    re.IGNORECASE)
MARKDOWN_BACKSLASH_ESCAPE_PATTERN = re.compile(r"\\([!-/:-@\[-`{-~])")
ID_PREFIX_BEFORE_TITLE_PATTERN = re.compile(
    r"^\s*(?:(?:PR|GHI|issue)\s+#?|#)(?P<number>\d+)\s*(?:[,:\u2013\u2014-]\s*|\s)(?P<title>.+)$",
    re.IGNORECASE | re.DOTALL)
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
# After the full note has been sent once in the agent-session, and since the last compaction.
PREVIOUS_REPLY_SHORT_OPENING_LINES = (
    PREVIOUS_REPLY_OPENING_LINES[0],
    "Cite each one by its ID-type and its name, as this hook's earlier note in this agent-session "
    "said. In your next reply, cite in full each one listed below that you mention again.",
)
NOTE_RECORD_FAILED_LINE = (
    "bare-number-citation-in-markdown-and-agent-reply-warning-hook: its record of the replies it "
    "has noted, {record}, could not be {action} ({reason}), so this note may be sent again for the "
    "same reply, and in full. Nothing needs doing about the record.")
MARKDOWN_TITLE_OPENING_LINES = (
    "bare-number-citation-in-markdown-and-agent-reply-warning-hook: the text just written to {path} links {count} pull "
    "request(s) or GitHub issue(s) under link text that is not the title GitHub reports, or "
    "whose number is not the link's. A reader "
    "takes link text written as a title to be the linked item's title, so a different title points "
    "the reader at the wrong item.",
    "For each link listed below whose text was meant as the item's title, change the text to "
    "the title shown, keeping any ID prefix such as PR <number>.",
    "For each link whose text describes the item in your own words instead, leave the text as written.",
)
PREVIOUS_REPLY_TITLE_OPENING_LINES = (
    "bare-number-citation-in-markdown-and-agent-reply-warning-hook: your previous reply to the user linked {count} pull "
    "request(s) or GitHub issue(s) under link text that is not the title GitHub reports, or "
    "whose number is not the link's. A reader "
    "takes link text written as a title to be the linked item's title, so a different title points "
    "the reader at the wrong item.",
    "This note asks for no correction now. If a later reply of yours mentions an item listed below "
    "whose link text was meant as its title, cite the item under the title shown, keeping any ID "
    "prefix such as PR <number>.",
    "For a link whose text described the item in your own words instead, nothing needs doing.",
)
WRONG_NUMBER_LINE_OPENING_INSTRUCTION = (
    "For each link listed below whose line ends by saying the number in the link text is not the "
    "link's number, ")
# Present only when the title lines are, so the two never contradict.
WRONG_NUMBER_TITLE_LINES_OVERRIDE_INSTRUCTION = "the two instruction lines above do not apply to that link: "
# Present only when the title lines, which already say it, are left out.
NO_CORRECTION_NOW_INSTRUCTION = "This note asks for no correction now. "
MARKDOWN_WRONG_NUMBER_LINE = (
    WRONG_NUMBER_LINE_OPENING_INSTRUCTION + "{override}the URL may be the part that is wrong, so "
    "do not change the link text to fit the URL. Decide from the text around the link which item "
    "was meant, and point the link's URL at that item. Then, if the link text was meant as a "
    "title, write the link text as that item's ID prefix and title, such as PR <number>, "
    "\"<title>\" or GHI <number>: <title>; gh issue view <that item's number> --json title --jq "
    ".title prints the title, for a pull request too. If the link text was your own words, keep "
    "the words, and make the number in them that item's number.")
PREVIOUS_REPLY_WRONG_NUMBER_LINE = (
    "{no_correction}" + WRONG_NUMBER_LINE_OPENING_INSTRUCTION + "{override}the URL may be the "
    "part that is wrong, so do not change the link text to fit the URL. If a later reply of yours "
    "cites the item again, first decide from your earlier reply which item was meant, and point "
    "the link's URL at that item. Then, if the link text was meant as a title, write the link "
    "text as that item's ID prefix and title, such as PR <number>, \"<title>\" or GHI <number>: "
    "<title>; gh issue view <that item's number> --json title --jq .title prints the title, for a "
    "pull request too. If the link text was your own words, keep the words, and make the number "
    "in them that item's number.")
TITLES_NOT_CHECKED_LINE = (
    "bare-number-citation-in-markdown-and-agent-reply-warning-hook: the text of {count} link(s) to pull "
    "requests or GitHub issues was not checked against their titles on GitHub, because gh could not "
    "report the titles: {reason}. Nothing needs doing; the check runs again next time.")
WRITE_TITLE_HIT_LINE = '{path}:{line}: "{text}" links {url}; the title on GitHub is "{title}"{number_note}'
EXCERPT_TITLE_HIT_LINE = '"{text}" links {url}; the title on GitHub is "{title}"{number_note}'
WRONG_NUMBER_NOTE_TEMPLATE = "; the number {prefix_number} in the link text is not the link's number {number}"
WRITE_HIT_LINE = '{path}:{line}: "{reference}" in "{excerpt}"'
EXCERPT_HIT_LINE = '"{reference}" in "{excerpt}"'
MORE_TITLE_HITS_LINE = ("{count} more not listed: reread the rest of the same text for links to "
                        "pull requests or GitHub issues under text that is not their title, or "
                        "whose number is not the link's.")
MORE_HITS_LINE = ("{count} more not listed: reread the rest of the same text for "
                  "numbers cited the same way.")


class LinkTitleMismatch:
    def __init__(self, line_number, text, url, title, number, prefix_number=None):
        self.line_number = line_number
        self.text = text
        self.url = url
        self.title = title
        self.number = number
        # The number of an ID prefix in the text when it is not the URL's, else None.
        self.prefix_number = prefix_number


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


def name_follows(line: str, masked_line: str, start: int, end: int):
    """Where the name ends when the reference at line[start:end] is followed
    at once by its name, a complete quoted name or a complete Markdown link;
    else None. A straight quote after an odd number of straight quotes closes
    a quotation, so it names nothing; the quotes are counted in masked_line,
    so a quote inside a code span does not count."""
    position = NAME_SEPARATOR_PATTERN.match(line, end).end()
    for name_pattern in (MARKDOWN_LINK_PATTERN, CURLY_QUOTED_NAME_PATTERN):
        name = name_pattern.match(line, position)
        if name:
            return name.end()
    if masked_line.count('"', 0, start) % 2 != 0:
        return None
    name = STRAIGHT_QUOTED_NAME_PATTERN.match(line, position)
    return name.end() if name else None


def bare_references_in(text: str, line_numbers_to_report=None):
    """Every bare reference in text, in reading order, numbering lines from 1.
    With line_numbers_to_report, only hits on those lines."""
    original_lines = text.split("\n")
    found = []
    for index, line in enumerate(scannable_lines(text)):
        line_number = index + 1
        if line_numbers_to_report is not None and line_number not in line_numbers_to_report:
            continue
        # The finditer below scans the line as it was, so a name already
        # accepted is skipped by position, not by changing the line.
        name_end = -1
        for match in BARE_REFERENCE_PATTERN.finditer(line):
            if match.start() < name_end:
                continue
            accepted_name_end = name_follows(original_lines[index], line, match.start(), match.end())
            if accepted_name_end is not None:
                name_end = accepted_name_end
                continue
            found.append(BareReference(
                line_number, match.group(0),
                excerpt_around(original_lines[index], match.start(), match.end())))
    return found


def unquoted_and_unescaped(text: str) -> str:
    text = " ".join(text.split())
    for opening, closing in SURROUNDING_QUOTE_PAIRS:
        if len(text) >= 2 and text.startswith(opening) and text.endswith(closing):
            text = text[1:-1].strip()
            break
    return MARKDOWN_BACKSLASH_ESCAPE_PATTERN.sub(r"\1", text)


def comparable_title(text: str) -> str:
    return unquoted_and_unescaped(text).casefold()


def titles_match(link_text: str, title: str) -> bool:
    link_text, title = comparable_title(link_text), comparable_title(title)
    return link_text == title or link_text.replace("`", "") == title.replace("`", "")


def link_title_mismatch(line_number, link_text, url, number, title):
    """A LinkTitleMismatch, or None when the text is the title, with or
    without an ID prefix carrying the URL's number."""
    if titles_match(link_text, title):
        return None
    prefixed = ID_PREFIX_BEFORE_TITLE_PATTERN.match(unquoted_and_unescaped(link_text))
    if prefixed is None:
        return LinkTitleMismatch(line_number, link_text, url, title, number)
    prefix_number = int(prefixed.group("number"))
    if prefix_number == number and titles_match(prefixed.group("title"), title):
        return None
    return LinkTitleMismatch(line_number, link_text, url, title, number,
                             prefix_number if prefix_number != number else None)


def is_title_attempt(link_text: str) -> bool:
    words = link_text.split()
    return len(words) >= TITLE_ATTEMPT_WORDS_AT_LEAST


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
            # Matched in the masked line, so a bracket inside a code span in the
            # text cannot stop the match; an image's match starts at its "!",
            # where this pattern does not match.
            # An escaped bracket, \[text\](url), starts no link.
            if match.start() > 0 and line[match.start() - 1] == "\\":
                continue
            parts = LINK_TEXT_AND_TARGET_PATTERN.match(line, match.start())
            if parts is None:
                continue
            link_text = original_lines[index][parts.start("text"):parts.end("text")]
            target = original_lines[index][parts.start("target"):parts.end("target")]
            url_match = REPOSITORY_ITEM_URL_PATTERN.match(target)
            if url_match is None or not is_title_attempt(link_text):
                continue
            links.append((line_number, link_text, target.strip("<>"),
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
    detail = (completed.stderr.strip() or completed.stdout.strip()
              or f"exit {completed.returncode}").splitlines()[0]
    try:
        answer = json.loads(completed.stdout)
        repository = answer["data"]["repository"]
        errors = answer.get("errors") or []
    except (ValueError, KeyError, TypeError):
        raise GithubTitlesUnavailable(f"gh api graphql failed: {detail}")
    # A number with no item makes gh exit 1 with a NOT_FOUND error, while the
    # other titles still arrive; any other error means a title may be missing.
    if (not isinstance(repository, dict) or not isinstance(errors, list)
            or any(not isinstance(error, dict) or error.get("type") != "NOT_FOUND"
                   for error in errors)
            or (completed.returncode != 0 and not errors)):
        raise GithubTitlesUnavailable(f"gh api graphql failed: {detail}")
    titles = {}
    for number in set(numbers):
        item = repository.get(f"n{number}")
        titles[number] = item.get("title") if isinstance(item, dict) else None
    return titles


def link_title_mismatches_in(text: str, line_numbers_to_report=None):
    """Return (mismatches, reason titles were not checked or None, links found)."""
    links = repository_item_links_in(text, line_numbers_to_report)
    if not links:
        return [], None, 0
    try:
        titles = github_titles([number for _, _, _, number in links])
    except GithubTitlesUnavailable as error:
        return [], str(error), len(links)
    mismatches = [
        mismatch for mismatch in (
            link_title_mismatch(line_number, link_text, url, number, titles[number])
            for line_number, link_text, url, number in links
            if titles.get(number) is not None)
        if mismatch is not None]
    return mismatches, None, len(links)


def wrong_number_line_text(template, title_lines_shown):
    return template.format(
        override=WRONG_NUMBER_TITLE_LINES_OVERRIDE_INSTRUCTION if title_lines_shown else "",
        no_correction="" if title_lines_shown else NO_CORRECTION_NOW_INSTRUCTION)


def title_note_lines(opening_lines, wrong_number_line, checked, path=None,
                     with_line_numbers=False):
    mismatches, reason, link_count = checked
    if reason is not None:
        return [TITLES_NOT_CHECKED_LINE.format(count=link_count, reason=reason)]
    if not mismatches:
        return []
    listed = mismatches[:HIT_LINES_LISTED_AT_MOST]
    # opening_lines[0] says what was found; the rest instruct about titles, and
    # are left out when every link, listed or not, has a wrong number, whose own
    # line replaces them.
    title_lines_shown = not all(mismatch.prefix_number is not None for mismatch in mismatches)
    if not title_lines_shown:
        opening_lines = opening_lines[:1]
    lines = [line.format(path=path, count=len(mismatches)) for line in opening_lines]
    if any(mismatch.prefix_number is not None for mismatch in listed):
        lines.append(wrong_number_line_text(wrong_number_line, title_lines_shown))
    for mismatch in listed:
        hit_line = WRITE_TITLE_HIT_LINE if with_line_numbers else EXCERPT_TITLE_HIT_LINE
        number_note = "" if mismatch.prefix_number is None else WRONG_NUMBER_NOTE_TEMPLATE.format(
            prefix_number=mismatch.prefix_number, number=mismatch.number)
        lines.append(hit_line.format(path=path, line=mismatch.line_number, text=mismatch.text,
                                     url=mismatch.url, title=mismatch.title,
                                     number_note=number_note))
    if len(mismatches) > HIT_LINES_LISTED_AT_MOST:
        lines.append(MORE_TITLE_HITS_LINE.format(count=len(mismatches) - HIT_LINES_LISTED_AT_MOST))
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

def _load_edited_file_path_within_checkout_root_and_git_check_ignore():
    """Return the shared checkout and git-tracking helpers, loaded by path; raises when they will not load."""
    specification = importlib.util.spec_from_file_location(
        "edited_file_path_within_checkout_root_and_git_check_ignore_common",
        Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
        / "edited-file-path-within-checkout-root-and-git-check-ignore-common.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


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
    checks = _load_edited_file_path_within_checkout_root_and_git_check_ignore()
    located = checks.checkout_relative_path(file_path, Path(working_directory))
    if located is None:
        return None
    root, relative_path = located

    if tool_name == "Edit":
        new_string = tool_input.get("new_string")
        if not isinstance(new_string, str) or not new_string.strip():
            return None
        if not checks.git_would_track(root, relative_path):
            return None
        references = bare_references_in(new_string)
        checked = link_title_mismatches_in(new_string)
        with_line_numbers = False
    else:
        content = tool_input.get("content")
        if not isinstance(content, str) or not content.strip():
            return None
        committed_lines = checks.file_lines_at_head_unless_git_ignores_file(root, relative_path)
        if committed_lines is None:
            return None
        new_line_numbers = set(
            index + 1 for index, line in enumerate(content.split("\n"))
            if line.rstrip() not in committed_lines)
        references = bare_references_in(content, new_line_numbers)
        checked = link_title_mismatches_in(content, new_line_numbers)
        with_line_numbers = True
    sections = title_note_lines(MARKDOWN_TITLE_OPENING_LINES, MARKDOWN_WRONG_NUMBER_LINE, checked,
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


def transcript_records(transcript_path: Path):
    records = []
    with open(transcript_path, encoding="utf-8") as transcript:
        for line in transcript:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict):
                records.append(record)
    return records


def compaction_count(records) -> int:
    return sum(1 for record in records
               if record.get("type") == "system" and record.get("subtype") == "compact_boundary")


def previous_reply(records, is_turn_start):
    """(the text of the agent's last message in the transcript's last turn,
    that message's id or None), which, while the prompt being submitted is not
    yet written, is the previous turn."""
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
                # A record with no id is a message of its own; its id(), a key
                # for this call only, is never returned as the message's id.
                message_id = message.get("id") or id(record)
                texts_by_message.setdefault(message_id, []).append(block.get("text", ""))
                last_text_message_id = message_id
    reply = "\n".join(texts_by_message.get(last_text_message_id, []))
    return reply, (last_text_message_id if isinstance(last_text_message_id, str) else None)


def note_record_path_for(session_id):
    """The agent-session's record of the replies noted, or None when the
    payload names no session this hook can use as a file name."""
    if not isinstance(session_id, str) or not SESSION_ID_SAFE_PATTERN.match(session_id):
        return None
    return Path(tempfile.gettempdir()) / NOTE_RECORD_DIRECTORY_NAME / f"{session_id}.json"


def note_record_read(record_path):
    """(record, None) or ({}, the reason it could not be read); a record not
    yet written is empty."""
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, None
    except (OSError, ValueError) as error:
        return {}, f"{type(error).__name__}: {error}"
    if not isinstance(record, dict):
        return {}, "it holds JSON, but not an object"
    return record, None


def note_record_write(record_path, record):
    """None, or the reason the record could not be written."""
    try:
        record_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = record_path.with_name(record_path.name + ".tmp")
        temporary.write_text(json.dumps(record), encoding="utf-8")
        os.replace(temporary, record_path)
    except OSError as error:
        return f"{type(error).__name__}: {error}"
    return None


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
    records = transcript_records(transcript_file)
    reply, message_id = previous_reply(records, _load_absence_claim_hook().is_human_or_parent_message)
    if not reply.strip():
        return None
    record_path = note_record_path_for(payload.get("session_id"))
    record, read_failure = note_record_read(record_path) if record_path else ({}, None)
    if message_id is not None and record.get("noted_message_id") == message_id:
        return None
    references = bare_references_in(reply)
    sections = title_note_lines(PREVIOUS_REPLY_TITLE_OPENING_LINES, PREVIOUS_REPLY_WRONG_NUMBER_LINE,
                                link_title_mismatches_in(reply))
    if not references and not sections:
        return None
    compactions = compaction_count(records)
    full_note_sent = record.get("full_note_sent_after_compactions") == compactions
    failures = []
    if record_path is not None:
        if references:
            record["full_note_sent_after_compactions"] = compactions
        record["noted_message_id"] = message_id
        if read_failure is not None:
            failures.append(NOTE_RECORD_FAILED_LINE.format(record=record_path, action="read",
                                                           reason=read_failure))
        write_failure = note_record_write(record_path, record)
        if write_failure is not None:
            # A record that cannot be written counts as no record: the full note is sent.
            full_note_sent = False
            failures.append(NOTE_RECORD_FAILED_LINE.format(record=record_path, action="written",
                                                           reason=write_failure))
    if references:
        sections.insert(0, note_text(
            PREVIOUS_REPLY_SHORT_OPENING_LINES if full_note_sent else PREVIOUS_REPLY_OPENING_LINES,
            references))
    return hook_output("UserPromptSubmit", "\n".join(sections + failures))


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
        print(f"bare-number-citation-in-markdown-and-agent-reply-warning-hook: "
              f"no check was made: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
