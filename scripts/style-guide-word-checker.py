#!/usr/bin/env python3
"""Find candidate style-guide violations in Markdown; the writer decides which uses need revision.

Inflections are explicit because generated forms also match unrelated words.
Keep Python 3.9 compatibility for the Mac's /usr/bin/python3."""

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
    form: str          # Preserve source capitalization for the reported hit.
    entry: StyleGuideWordListEntry


# Accept list markers and indentation before fences; missing an opener would invert later fence tracking.
FENCE_PATTERN = re.compile(r"^[ \t]*(?:(?:[-*+]|\d{1,9}[.)])[ \t]+)?(`{3,}|~{3,})")
BLOCKQUOTE_LINE_PATTERN = re.compile(r"^[ \t]*>")

# Blank with equal-length spaces to preserve offsets; code spans must hide embedded quotes and slashes.
# Mask link targets before slash tokens so adjacent link text remains searchable.
INLINE_CODE_SPAN_PATTERN = re.compile(r"(`+).+?\1")
LINK_TARGET_PATTERN = re.compile(r"\]\([^)]*\)")
# Anchor at token starts to avoid retrying the pattern at every character of long lines.
SLASH_TOKEN_PATTERN = re.compile(r"(?<!\S)\S*/\S*")
DOUBLE_QUOTED_TEXT_PATTERN = re.compile('"[^"\n]*"|\u201c[^\u201d\n]*\u201d')
EXEMPT_TEXT_PATTERNS = (INLINE_CODE_SPAN_PATTERN, LINK_TARGET_PATTERN,
                        SLASH_TOKEN_PATTERN, DOUBLE_QUOTED_TEXT_PATTERN)

FORM_NOT_PRECEDED_BY = r"(?<![\w\-/`$<=@#~])"
FORM_NOT_FOLLOWED_BY = r"(?![\w\-/`>=@#~])(?!\.\w)"


def _either_case_first_letter(text: str) -> str:
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
    forms = sorted(entry_by_form, key=len, reverse=True)
    word_pattern = re.compile(
        FORM_NOT_PRECEDED_BY
        + "(?:" + "|".join(_either_case_first_letter(form) for form in forms) + ")"
        + FORM_NOT_FOLLOWED_BY)
    # Search exemptions near each hit to avoid a costly alternation across every character.
    exempt_pattern_by_word = {
        entry.word: re.compile("|".join(_exempt_form_pattern_text(form)
                                        for form in sorted(entry.exempt_forms, key=len,
                                                           reverse=True)))
        for entry in entries if entry.exempt_forms}
    # Every inflected form begins with its entry's word, so this prefilter cannot discard a hit.
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
    """Return the line with exempt text replaced by equal-length spaces."""
    for pattern in EXEMPT_TEXT_PATTERNS:
        line = pattern.sub(_blank, line)
    return line


def backtick_run_closing(line: str, run: str, start: int = 0) -> Optional[int]:
    """Return the closing offset of a matching-length backtick run, or None."""
    found = re.compile(r"(?<!`)`{%d}(?!`)" % len(run)).search(line, start)
    return None if found is None else found.end()


def code_span_continues_to(lines: List[str], line_index: int, run: str) -> bool:
    """Return whether an open code span closes later in the same paragraph."""
    # An unmatched opener is literal Markdown; blank lines and fences end the paragraph.
    for later in lines[line_index + 1:]:
        later = later.rstrip("\r")
        if not later.strip() or FENCE_PATTERN.match(later):
            return False
        if backtick_run_closing(later, run) is not None:
            return True
    return False


def is_inside_exempt_form(line: str, start: int, end: int, exempt_pattern: Pattern) -> bool:
    window_start = max(0, start - LONGEST_EXEMPT_FORM_LENGTH)
    window_end = end + LONGEST_EXEMPT_FORM_LENGTH
    return any(found.start() <= start and end <= found.end()
               for found in exempt_pattern.finditer(line, window_start, window_end))


def find_style_guide_word_hits_in_markdown(
        text: str, applies_to: str,
        line_numbers: Optional[AbstractSet[int]] = None) -> List[StyleGuideWordHit]:
    """Return applicable hits in source order, optionally restricted to selected lines."""
    # Read all lines for fence and span state even when only selected lines are searched.
    words, word_pattern, exempt_pattern_by_word, entry_by_form = COMPILED_SCOPES[applies_to]
    hits = []
    open_fence = None   # (fence character, fence length) while inside a fenced block
    open_code_span_run = None
    lines = text.split("\n")
    line_start = 0
    for line_index, raw_line in enumerate(lines):
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
        # A backtick fence's info string cannot contain backticks; ```x``` is a code span.
        if fence and not (fence.group(1)[0] == "`" and "`" in line[fence.end():]):
            open_fence = (fence.group(1)[0], len(fence.group(1)))
            open_code_span_run = None
            continue
        # Track multiline code spans on every line so selected-line scans retain the correct context.
        code_until = 0
        if open_code_span_run is not None:
            closing_end = backtick_run_closing(line, open_code_span_run)
            if closing_end is None:
                continue
            code_until = closing_end
            open_code_span_run = None
        code_from = len(line)
        if "`" in line[code_until:]:
            spans_blanked = INLINE_CODE_SPAN_PATTERN.sub(_blank, line[code_until:])
            unmatched = re.search(r"`+", spans_blanked)
            if unmatched is not None and code_span_continues_to(lines, line_index,
                                                                unmatched.group(0)):
                open_code_span_run = unmatched.group(0)
                code_from = code_until + unmatched.start()
        if line_numbers is not None and line_index + 1 not in line_numbers:
            continue
        lowered = line.lower()
        if not any(word in lowered for word in words) or BLOCKQUOTE_LINE_PATTERN.match(line):
            continue
        blanked = blank_exempt_text(" " * code_until + line[code_until:code_from]
                                    + " " * (len(line) - code_from))
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
