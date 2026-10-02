#!/usr/bin/env python3
"""The project's list of words to avoid, and the scanner that finds them in markdown.

THE DESIGN is GHI [A project style guide: words to avoid, a mechanical
checker, and a check on unbacked promises](https://github.com/nedschorus/nedschorus/issues/14),
item 2, whose text is docs/issues/14-review-the-legacy-system-s-bad-phrase-list.md.
This file is the "script holding the list": ONE list for the whole project,
read by every place the checker runs. The first place is the PostToolUse hook
scripts/style-guide-word-checker-markdown-edit-hook.py, which loads this file
by path. Later checkers, on a message to another agent and on a message to the
user, import the same list and pick their entries by APPLIES_TO_* value, so
adding a place needs no change to an entry's shape.

WHY A PROGRAM AND NOT A PAGE ALONE. A word list kept only as text did not hold
in the legacy system: under heavy context a model falls back to its training
priors. The one class that system checked at the moment of action is the class
that held, so the list is checked when the words are written.

THE CHECKER FLAGS AND THE WRITER JUDGES. No model rewrites a flagged word, and
this file chooses no replacement. Only the writer knows which meaning was
intended: bare "head" is a head commit or `HEAD`, and a program, or a model
without the session's context, would guess. A script also cannot tell an
ordinary English use from a project use, so every hit is a candidate that the
writer keeps or rewrites.

WHAT AN ENTRY CARRIES (StyleGuideWordListEntry):
  word                  the word as the list names it
  inflected_forms       every form matched, the word itself included. Each
                        form matches with its first letter in either case
                        ("Seat", "seat") and never in capitals, so `HEAD` and
                        an all-capitals heading are never hits.
  exempt_forms          the compounds and forms the project already names. A
                        form lying inside one of its own entry's exempt forms
                        is not a hit. An exempt form holding a capital letter
                        matches exactly as written ("HEAD"); any other matches
                        with its first letter in either case ("Head commit").
  names_to_choose_from  the text handed to the writer: the name for each
                        project meaning, or the word to write instead
  applies_to            where the entry is checked: APPLIES_TO_FILES,
                        APPLIES_TO_AGENT_MESSAGES, APPLIES_TO_USER_MESSAGES

WHY THE PRONOUN ENTRIES SKIP FILES. CLAUDE.md's pronoun bullet governs writing
to the user or to another agent. A file checker flagging every "it" in every
document would apply the rule outside its scope, and the hits on the other
words would be lost among them. So "it", "its", "they", "this" and "that"
carry only the two message values.

WHAT IS NOT CHECKED, because it is code or quoted text, and the writer cannot
or should not reword either:
  - fenced code blocks (``` or ~~~), inline code spans in backticks, and
    blockquote lines (a line opening with ">")
  - text inside double quotes, straight or curly, on one line: a quotation, or
    a word named rather than used, as in: write "merge" for "land"
  - link targets, and every whitespace-free token holding "/": paths and URLs,
    which covers /home/, docs/drafts/ and docs/walk/
  - a form joined by a hyphen to anything, so every hyphenated compound:
    agent-seat, frozen-head, -draft, /walk-me-through and compounds nobody has
    listed; also a form touching "$", "<", ">", "=", "@", "#", "~" or a
    backtick, and a form followed by a file extension ("seat.md")
  - each entry's exempt_forms

Inflections are listed by hand rather than generated, because the generated
forms are noisy: "heading" would match in nearly every markdown file this
project has, and is not a use of "head".

Every pattern is compiled once, at import. Standard library only, and no
syntax newer than Python 3.9, the /usr/bin/python3 of the user's Mac.
"""

import re
from typing import AbstractSet, Dict, List, NamedTuple, Optional, Pattern, Tuple

APPLIES_TO_FILES = "files"
APPLIES_TO_AGENT_MESSAGES = "agent messages"
APPLIES_TO_USER_MESSAGES = "user messages"
APPLIES_TO_VALUES = (APPLIES_TO_FILES, APPLIES_TO_AGENT_MESSAGES, APPLIES_TO_USER_MESSAGES)

APPLIES_TO_EVERY_PLACE = APPLIES_TO_VALUES
APPLIES_TO_MESSAGES_ONLY = (APPLIES_TO_AGENT_MESSAGES, APPLIES_TO_USER_MESSAGES)


class StyleGuideWordListEntry(NamedTuple):
    word: str
    inflected_forms: Tuple[str, ...]
    exempt_forms: Tuple[str, ...]
    names_to_choose_from: str
    applies_to: Tuple[str, ...]


PRONOUN_NAMES_TO_CHOOSE_FROM = (
    "write the noun the pronoun stands for, unless the noun is in the same sentence "
    "and no other noun there could be meant")

# The names for each meaning are the ones item 1 of the design's GHI-MD gives,
# word for word.
STYLE_GUIDE_WORD_LIST = (
    StyleGuideWordListEntry(
        word="land",
        inflected_forms=("land", "lands", "landed", "landing"),
        exempt_forms=(),
        names_to_choose_from=(
            'write "merge", "merges", "merged" or "merging", matching the form written'),
        applies_to=APPLIES_TO_EVERY_PLACE),
    StyleGuideWordListEntry(
        word="home",
        inflected_forms=("home", "homes"),
        exempt_forms=("agent-home", "/home/"),
        names_to_choose_from=(
            "agent-home for the directory an agent-seat works in; canonical location "
            "for the one place a document or fact is kept"),
        applies_to=APPLIES_TO_EVERY_PLACE),
    StyleGuideWordListEntry(
        word="draft",
        inflected_forms=("draft", "drafts"),
        exempt_forms=("-draft", "docs/drafts/"),
        names_to_choose_from=(
            '-draft for the filename suffix; "pending approval" for text that waits for '
            "the user's approval; \"the `draft` label\" for the GitHub label; "
            "`docs/drafts/` for the directory"),
        applies_to=APPLIES_TO_EVERY_PLACE),
    StyleGuideWordListEntry(
        word="walk",
        inflected_forms=("walk", "walks", "walked", "walking"),
        exempt_forms=("approval-walk", "approved-by-walk", "walk-document", "walk-minutes",
                      "/walk-me-through", "docs/walk/"),
        names_to_choose_from=(
            "approval-walk for the event; walk-document for the file "
            "`docs/walk/<name>.md`; approved-by-walk for the result; \"put to the user "
            'in an approval-walk" for the act'),
        applies_to=APPLIES_TO_EVERY_PLACE),
    StyleGuideWordListEntry(
        word="seat",
        inflected_forms=("seat", "seats", "seated"),
        exempt_forms=("agent-seat", "seat-branch", "seat-brief", "reincarnate-seat",
                      "retire-seat"),
        names_to_choose_from=(
            "agent-seat for the identity; agent-session for one running conversation; "
            "\"the agent-seat's name\" for the name of an agent-seat; working directory "
            "for where an agent-session works; cold-read-cell for one reviewer in a "
            "cold-read-full-run"),
        applies_to=APPLIES_TO_EVERY_PLACE),
    StyleGuideWordListEntry(
        word="head",
        inflected_forms=("head", "heads"),
        exempt_forms=("head commit", "frozen-head", "HEAD"),
        names_to_choose_from=(
            "head commit for a pull request's newest commit; frozen-head for a head "
            "commit once pushed; `HEAD`, in capitals, for what a Git checkout has "
            "checked out"),
        applies_to=APPLIES_TO_EVERY_PLACE),
    StyleGuideWordListEntry(
        word="drain",
        inflected_forms=("drain", "drains", "drained", "draining"),
        exempt_forms=("queue-drain",),
        names_to_choose_from=(
            'queue-drain for the procedure that empties a queue; "is promoted to" for '
            "an item that leaves a queue for its destination"),
        applies_to=APPLIES_TO_EVERY_PLACE),
    StyleGuideWordListEntry(
        word="it", inflected_forms=("it",), exempt_forms=(),
        names_to_choose_from=PRONOUN_NAMES_TO_CHOOSE_FROM,
        applies_to=APPLIES_TO_MESSAGES_ONLY),
    StyleGuideWordListEntry(
        word="its", inflected_forms=("its",), exempt_forms=(),
        names_to_choose_from=PRONOUN_NAMES_TO_CHOOSE_FROM,
        applies_to=APPLIES_TO_MESSAGES_ONLY),
    StyleGuideWordListEntry(
        word="they", inflected_forms=("they",), exempt_forms=(),
        names_to_choose_from=PRONOUN_NAMES_TO_CHOOSE_FROM,
        applies_to=APPLIES_TO_MESSAGES_ONLY),
    StyleGuideWordListEntry(
        word="this", inflected_forms=("this",), exempt_forms=(),
        names_to_choose_from=PRONOUN_NAMES_TO_CHOOSE_FROM,
        applies_to=APPLIES_TO_MESSAGES_ONLY),
    StyleGuideWordListEntry(
        word="that", inflected_forms=("that",), exempt_forms=(),
        names_to_choose_from='where "that" is used as a pronoun, ' + PRONOUN_NAMES_TO_CHOOSE_FROM,
        applies_to=APPLIES_TO_MESSAGES_ONLY),
)


class StyleGuideWordHit(NamedTuple):
    line_number: int   # 1-based, in the text scanned
    offset: int        # 0-based character offset of the form in the text scanned
    form: str          # the form as written
    entry: StyleGuideWordListEntry


# A fence opens with three or more backticks or tildes. Leading whitespace of
# any width is accepted, because a fence inside a list item is indented.
FENCE_PATTERN = re.compile(r"^[ \t]*(`{3,}|~{3,})")
BLOCKQUOTE_LINE_PATTERN = re.compile(r"^[ \t]*>")

# Applied in this order; each blanks what it matches with spaces of equal
# length, so an offset in the blanked line is the same offset in the line.
# Code spans go first, because a code span may hold quotes, brackets and
# slashes. Link targets go before slash tokens, because the link text and its
# target share one whitespace-free token: "seat](https://...)".
INLINE_CODE_SPAN_PATTERN = re.compile(r"(`+).+?\1")
LINK_TARGET_PATTERN = re.compile(r"\]\([^)]*\)")
# Anchored to the start of a token: unanchored, the pattern retries at every
# character of a long line, and a 120 KB design took 40 ms.
SLASH_TOKEN_PATTERN = re.compile(r"(?<!\S)\S*/\S*")
DOUBLE_QUOTED_TEXT_PATTERN = re.compile('"[^"\n]*"|\u201c[^\u201d\n]*\u201d')
EXEMPT_TEXT_PATTERNS = (INLINE_CODE_SPAN_PATTERN, LINK_TARGET_PATTERN,
                        SLASH_TOKEN_PATTERN, DOUBLE_QUOTED_TEXT_PATTERN)

FORM_NOT_PRECEDED_BY = r"(?<![\w\-/`$<=@#~])"
FORM_NOT_FOLLOWED_BY = r"(?![\w\-/`>=@#~])(?!\.\w)"


def _either_case_first_letter(text: str) -> str:
    """"seat" -> "[Ss]eat": the form at a sentence's start is the same form."""
    first = text[0]
    if first.isalpha() and first.islower():
        return "[%s%s]%s" % (first.upper(), first, re.escape(text[1:]))
    return re.escape(text)


def _exempt_form_pattern_text(form: str) -> str:
    if any(character.isupper() for character in form):
        return re.escape(form)
    return _either_case_first_letter(form)


def _compile_scope(applies_to: str):
    entries = [entry for entry in STYLE_GUIDE_WORD_LIST if applies_to in entry.applies_to]
    entry_by_form = {}
    for entry in entries:
        for form in entry.inflected_forms:
            entry_by_form[form] = entry
    # Longest first, so "landed" is tried before "land".
    forms = sorted(entry_by_form, key=len, reverse=True)
    word_pattern = re.compile(
        FORM_NOT_PRECEDED_BY
        + "(?:" + "|".join(_either_case_first_letter(form) for form in forms) + ")"
        + FORM_NOT_FOLLOWED_BY)
    # An entry's exempt forms are looked for only around a hit on that entry,
    # not across the whole line: one alternation tried at every character of
    # every line cost more than the rest of the scan together.
    exempt_pattern_by_word = {
        entry.word: re.compile("|".join(_exempt_form_pattern_text(form)
                                        for form in sorted(entry.exempt_forms, key=len,
                                                           reverse=True)))
        for entry in entries if entry.exempt_forms}
    # Every form begins with its entry's word, so a line whose lowered text
    # holds none of the words holds no hit, and is passed over unblanked.
    words = tuple(entry.word for entry in entries)
    return words, word_pattern, exempt_pattern_by_word, entry_by_form


COMPILED_SCOPES: Dict[str, Tuple[Tuple[str, ...], Pattern, Dict[str, Pattern],
                                 Dict[str, StyleGuideWordListEntry]]] = {
    applies_to: _compile_scope(applies_to) for applies_to in APPLIES_TO_VALUES}
LONGEST_EXEMPT_FORM_LENGTH = max(len(form) for entry in STYLE_GUIDE_WORD_LIST
                                 for form in entry.exempt_forms)


def _blank(match) -> str:
    return " " * (match.end() - match.start())


def blank_exempt_text(line: str) -> str:
    """The line with code spans, link targets, paths and quotations replaced by
    spaces, offsets unchanged."""
    for pattern in EXEMPT_TEXT_PATTERNS:
        line = pattern.sub(_blank, line)
    return line


def is_inside_exempt_form(line: str, start: int, end: int, exempt_pattern: Pattern) -> bool:
    """Whether the form at line[start:end] lies inside one of its entry's
    exempt forms. Only a window around the form is searched: an exempt form
    holding the form begins no earlier than its own length before the form."""
    window_start = max(0, start - LONGEST_EXEMPT_FORM_LENGTH)
    window_end = end + LONGEST_EXEMPT_FORM_LENGTH
    return any(found.start() <= start and end <= found.end()
               for found in exempt_pattern.finditer(line, window_start, window_end))


def find_style_guide_word_hits_in_markdown(
        text: str, applies_to: str,
        line_numbers: Optional[AbstractSet[int]] = None) -> List[StyleGuideWordHit]:
    """Every hit in the text, for the entries that apply to `applies_to`, in
    the order the hits occur. Fenced code blocks and blockquote lines are
    skipped whole; a fence still open at the end of the text runs to the end.

    `line_numbers`, when given, limits the hits to those 1-based lines. Every
    line is still read for the fences, because whether a line is code depends
    on the lines before it; only the named lines are searched for words.
    """
    words, word_pattern, exempt_pattern_by_word, entry_by_form = COMPILED_SCOPES[applies_to]
    hits = []
    open_fence = None   # (fence character, fence length) while inside a fenced block
    line_start = 0
    for line_index, raw_line in enumerate(text.split("\n")):
        line = raw_line.rstrip("\r")
        this_line_start = line_start
        line_start += len(raw_line) + 1
        fence = FENCE_PATTERN.match(line)
        if open_fence is not None:
            if (fence and fence.group(1)[0] == open_fence[0]
                    and len(fence.group(1)) >= open_fence[1]
                    and not line[fence.end():].strip()):
                open_fence = None
            continue
        # ```x``` on one line is a code span, not a fence: a backtick fence's
        # info string may not hold a backtick.
        if fence and not (fence.group(1)[0] == "`" and "`" in line[fence.end():]):
            open_fence = (fence.group(1)[0], len(fence.group(1)))
            continue
        if line_numbers is not None and line_index + 1 not in line_numbers:
            continue
        lowered = line.lower()
        if not any(word in lowered for word in words) or BLOCKQUOTE_LINE_PATTERN.match(line):
            continue
        blanked = blank_exempt_text(line)
        for match in word_pattern.finditer(blanked):
            form = match.group(0)
            entry = entry_by_form[form.lower()]
            exempt_pattern = exempt_pattern_by_word.get(entry.word)
            if exempt_pattern is not None and is_inside_exempt_form(
                    blanked, match.start(), match.end(), exempt_pattern):
                continue
            hits.append(StyleGuideWordHit(
                line_number=line_index + 1,
                offset=this_line_start + match.start(),
                form=form,
                entry=entry))
    return hits
