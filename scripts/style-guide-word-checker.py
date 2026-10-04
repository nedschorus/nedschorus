#!/usr/bin/env python3
"""Find candidate style-guide violations in Markdown; the writer decides which uses need revision.

The word list is the "Words to avoid" table of docs/nedschorus-wiki/nedschorus-style-guide.md,
read at import, so the page agents read and the list this checker flags cannot differ.

Inflections are explicit because generated forms also match unrelated words.
Keep Python 3.9 compatibility for the Mac's /usr/bin/python3."""

import re
from pathlib import Path
from typing import AbstractSet, Dict, List, NamedTuple, Optional, Pattern, Tuple

APPLIES_TO_FILES = "files"
APPLIES_TO_AGENT_MESSAGES = "messages to other agents"
APPLIES_TO_USER_MESSAGES = "messages to the user"
APPLIES_TO_VALUES = (APPLIES_TO_FILES, APPLIES_TO_AGENT_MESSAGES, APPLIES_TO_USER_MESSAGES)


class StyleGuideWordListEntry(NamedTuple):
    word: str
    inflected_forms: Tuple[str, ...]
    exempt_forms: Tuple[str, ...]
    names_to_choose_from: str
    applies_to: Tuple[str, ...]


STYLE_GUIDE_PAGE_PATH = (Path(__file__).resolve().parent.parent
                         / "docs" / "nedschorus-wiki" / "nedschorus-style-guide.md")
WORDS_TO_AVOID_HEADING = "## Words to avoid"
WORDS_TO_AVOID_COLUMNS = ("Word", "Forms flagged", "Forms not flagged", "Write instead",
                          "Applies to")
CODE_SPAN_CONTENT_PATTERN = re.compile(r"`([^`]+)`")
TABLE_SEPARATOR_ROW_PATTERN = re.compile(r"^\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?$")


class StyleGuidePageError(ValueError):
    """The style guide page is missing its word table, or a row of it is malformed."""


def _table_cells(line: str) -> List[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _code_span_forms(cell: str, row: str) -> Tuple[str, ...]:
    forms = tuple(CODE_SPAN_CONTENT_PATTERN.findall(cell))
    if CODE_SPAN_CONTENT_PATTERN.sub("", cell).replace(",", "").strip():
        raise StyleGuidePageError("a forms cell holds text outside code spans: " + row)
    return forms


def parse_words_to_avoid_table(page_text: str) -> Tuple[StyleGuideWordListEntry, ...]:
    """Return the entries of the page's "Words to avoid" table, or raise StyleGuidePageError."""
    lines = page_text.split("\n")
    try:
        heading_index = [line.rstrip() for line in lines].index(WORDS_TO_AVOID_HEADING)
    except ValueError:
        raise StyleGuidePageError("no line reads " + WORDS_TO_AVOID_HEADING)
    # The table runs from its header line to the first blank line or heading. Every
    # line in that run must be a row: GFM renders a row without its leading pipe, so
    # skipping such a line would drop a row the page shows.
    table_lines = []
    for line in lines[heading_index + 1:]:
        line = line.rstrip()
        if line.lstrip().startswith("#"):
            break
        if not line.strip():
            if table_lines:
                break
            continue
        if not table_lines and not line.lstrip().startswith("|"):
            continue
        if not line.lstrip().startswith("|"):
            raise StyleGuidePageError("a table line does not start with |: " + line)
        table_lines.append(line.strip())
    if len(table_lines) < 3 or tuple(_table_cells(table_lines[0])) != WORDS_TO_AVOID_COLUMNS:
        raise StyleGuidePageError("the table under %s must have the columns %s"
                                  % (WORDS_TO_AVOID_HEADING, ", ".join(WORDS_TO_AVOID_COLUMNS)))
    if not TABLE_SEPARATOR_ROW_PATTERN.match(table_lines[1]):
        raise StyleGuidePageError("the table's second line is not its separator row: "
                                  + table_lines[1])
    entries = []
    for row in table_lines[2:]:
        cells = _table_cells(row)
        if len(cells) != len(WORDS_TO_AVOID_COLUMNS):
            raise StyleGuidePageError("a row does not have five cells: " + row)
        word_cell, flagged, not_flagged, names, applies_to_cell = cells
        word = word_cell.strip("`")
        applies_to = tuple(place.strip() for place in applies_to_cell.split(","))
        if not word or not names or not set(applies_to) <= set(APPLIES_TO_VALUES):
            raise StyleGuidePageError("a row is missing its word or names, or names an "
                                      "unknown place to check: " + row)
        inflected_forms = _code_span_forms(flagged, row)
        if word not in inflected_forms:
            raise StyleGuidePageError("a row's word is not among its forms flagged: " + row)
        entries.append(StyleGuideWordListEntry(
            word=word, inflected_forms=inflected_forms,
            exempt_forms=_code_span_forms(not_flagged, row),
            names_to_choose_from=names, applies_to=applies_to))
    return tuple(entries)


# Raises on a missing page or a malformed table, so the hook, which loads this module
# inside a try, prints nothing rather than checking against a partial list.
STYLE_GUIDE_WORD_LIST = parse_words_to_avoid_table(
    STYLE_GUIDE_PAGE_PATH.read_text(encoding="utf-8"))


class StyleGuideWordHit(NamedTuple):
    line_number: int   # 1-based, in the text scanned
    offset: int        # 0-based character offset of the form in the text scanned
    form: str          # Preserve source capitalization for the reported hit.
    entry: StyleGuideWordListEntry


# Accept list markers and indentation before fences; missing an opener would invert later fence tracking.
FENCE_PATTERN = re.compile(r"^[ \t]*(?:(?:[-*+]|\d{1,9}[.)])[ \t]+)?(`{3,}|~{3,})")
BLOCKQUOTE_LINE_PATTERN = re.compile(r"^[ \t]*>")
LIST_ITEM_LINE_PATTERN = re.compile(r"^[ \t]*(?:[-*+]|\d{1,9}[.)])[ \t]")
INDENTED_LINE_PATTERN = re.compile(r"^(?: {4}|[ ]{0,3}\t)")

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
    # Keyed lower-case because a hit is looked up by its lower-cased text; a form written
    # with a capital in the table, such as `PR`, would otherwise raise KeyError at a hit.
    entry_by_form = {}
    for entry in entries:
        for form in entry.inflected_forms:
            entry_by_form[form.lower()] = entry
    forms = sorted({form for entry in entries for form in entry.inflected_forms},
                   key=len, reverse=True)
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
    # A row's forms need not begin with its word (go, went), so the prefilter holds every form.
    words = tuple(sorted({form.lower() for entry in entries for form in entry.inflected_forms}))
    return words, word_pattern, exempt_pattern_by_word, entry_by_form


COMPILED_SCOPES: Dict[str, Tuple[Tuple[str, ...], Pattern, Dict[str, Pattern],
                                 Dict[str, StyleGuideWordListEntry]]] = {
    applies_to: _compile_scope(applies_to) for applies_to in APPLIES_TO_VALUES}
LONGEST_EXEMPT_FORM_LENGTH = max((len(form) for entry in STYLE_GUIDE_WORD_LIST
                                  for form in entry.exempt_forms), default=0)


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
    # An indented code block starts only after a blank line, and a line indented under a
    # list item continues the item rather than starting code, so both are tracked.
    previous_line_blank = True
    inside_indented_code = False
    inside_list = False
    lines = text.split("\n")
    line_start = 0
    for line_index, raw_line in enumerate(lines):
        line = raw_line.rstrip("\r")
        this_line_start = line_start
        line_start += len(raw_line) + 1
        line_blank = not line.strip()
        if open_fence is None and not line_blank:
            indented = INDENTED_LINE_PATTERN.match(line) is not None
            if LIST_ITEM_LINE_PATTERN.match(line):
                inside_list = True
            elif not indented:
                inside_list = False
            inside_indented_code = indented and not inside_list and (
                previous_line_blank or inside_indented_code)
        previous_line_blank = line_blank
        if inside_indented_code and not line_blank:
            open_code_span_run = None
            continue
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
