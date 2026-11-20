#!/usr/bin/env python3
"""Turn the terminology reviewer's JSON answer into its report.

The cold-read-cells call terminology_report_from_answer with the answer the
agent-binary returned, the schema the model was given
(.claude/skills/cold-read/prompts/terminology-answer-schema.json), the text
of the frozen-copy and the entries of every glossary. It:

1. checks the answer against the schema, and raises TerminologyAnswerRejected
   listing every break when it fails; then checks it against every rule of
   nc-systems/cold-read/cold-read-terminology-answer-rules-the-runner-validates-beyond-the-schema.md,
   one function per row of that page's table, each break tied to the flag it
   is about or to the answer as a whole, and raises TerminologyAnswerRejected
   only when more than half the flags break a rule;
2. makes the lookups that page's last section lists: the glossary entry of a
   term defined twice, the key-terms no glossary lists, where each flagged
   term first appears, clashes_with_location, the fix of a term defined twice
   that fails no test, and the glossary terms the document writes with a
   different case, hyphen or plural (test (5), one flag per term);
3. renders the report a reader triages: the document's kind, the rule breaks
   of the answer as a whole, one numbered item per flag with its test numbers
   and a "runner check failed: " line per rule it breaks, the proposed definitions, the
   key-terms missing from the glossaries, the terms kept, and a closing
   counts line.

Matching a term in text treats a hyphen as part of a word, so "agent seat"
is not found inside "agent-seat-model", and ignores case and runs of
whitespace. A glossary lookup also ignores the difference between a hyphen
and a space, and a plural "s" or "es" on the last word; a fix (a)'s lookup
also ignores a leading "the", "a" or "an". A passage the runner quotes for a
flag it adds is cut at whitespace, never inside a word. The document's code
spans, fenced code blocks, URLs and link targets are not scanned for
glossary terms written differently; skills (`/name`) and filename suffixes
(`-name`) are never looked for. A quotation in the answer must be in the
frozen-copy word for word, whitespace aside, so a quotation that drops
Markdown markup such as ** or backticks is rejected.

It does not handle a schema keyword json-schema-keyword-subset-answer-check-common.py
does not check: such a schema raises TerminologyAnswerRejected before any
answer is read.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "cold_read_terminology_answer_rules_check_glossary_lookups_and_report_render_common", <path>)
"""

import copy
import importlib.util
import re
import typing
from pathlib import Path

_json_schema_check_spec = importlib.util.spec_from_file_location(
    "json_schema_keyword_subset_answer_check_common",
    Path(__file__).resolve().parents[1] / "general-tools"
    / "json-schema-keyword-subset-answer-check-common.py")
json_schema_check = importlib.util.module_from_spec(_json_schema_check_spec)
_json_schema_check_spec.loader.exec_module(json_schema_check)

RULES_PAGE = ("nc-systems/cold-read/"
              "cold-read-terminology-answer-rules-the-runner-validates-beyond-the-schema.md")
TESTS = (1, 2, 3, 4, 5)
WORDS_A_RESTATEMENT_AVOIDS = ("kind", "type", "category", "sort", "class", "form")
QUOTED_SPAN_PATTERN = re.compile(r'"[^"]*"|“[^”]*”')
SURROUNDING_QUOTES = "\"'`“”‘’"
# A fix (a) written in a sentence, as "the cold-read-target", still names a glossary term.
LEADING_ARTICLE_PATTERN = re.compile(r"^(?:the|an|a)\s+", re.I)
RULE_BREAK_MARK = "runner check failed: "
LOCATION_GLOSSARY = "glossary"
LOCATION_DOCUMENT = "document"
LOCATION_STANDARD_VOCABULARY = "standard_vocabulary"
FIX_GLOSSARY_NAME = "a"
FIX_NEW_PROJECT_TERM = "d"
FIX_QUESTION = "question"
DIFFERENTLY_WRITTEN_GLOSSARY_TERM_TEST = 5
# Blanked before the scan for glossary terms written differently, keeping offsets.
NOT_PROSE_PATTERNS = (
    re.compile(r"```.*?```", re.S),
    re.compile(r"`[^`\n]*`"),
    re.compile(r"\]\([^)\s]*\)"),
    re.compile(r"https?://\S+"),
    re.compile(r"<!--.*?-->", re.S),
)
PASSAGE_CONTEXT_CHARACTERS = 200


class TerminologyAnswerRejected(Exception):
    """The answer breaks the schema or a rule; problems lists each break."""

    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = problems


class Glossary(typing.NamedTuple):
    """Glossary entries indexed by the spelling key glossary_spelling_key makes."""

    entries_by_key: dict

    @classmethod
    def of(cls, entries):
        by_key = {}
        for entry in entries:
            by_key.setdefault(glossary_spelling_key(entry.term), entry)
        return cls(by_key)

    def entry_for(self, written):
        """The entry whose term is written, ignoring case, hyphen against space and a plural ending; or None."""
        key = glossary_spelling_key(unquoted(written))
        for candidate in (key, key[:-2] if key.endswith("es") else None,
                          key[:-1] if key.endswith("s") else None):
            if candidate and candidate in self.entries_by_key:
                return self.entries_by_key[candidate]
        return None

    def terms(self):
        return [entry.term for entry in self.entries_by_key.values()]


def unquoted(text):
    return text.strip().strip(SURROUNDING_QUOTES).strip()


def glossary_spelling_key(text):
    return " ".join(re.split(r"[-\s]+", text.casefold())).strip()


def term_pattern(term, plural=False):
    """Matches term as whole words, a hyphen counting as part of a word, any case and whitespace."""
    words = [re.escape(word) for word in unquoted(term).split()]
    ending = r"(?:es|s)?" if plural else ""
    return re.compile(r"(?<![\w-])" + r"\s+".join(words) + ending + r"(?![\w-])", re.I)


def quotation_pattern(quotation):
    """Matches quotation word for word, any run of whitespace standing for any other."""
    return re.compile(r"\s+".join(re.escape(word) for word in quotation.split()))


def found_in(quotation, text):
    return bool(quotation.split()) and quotation_pattern(quotation).search(text) is not None


def spans_of(quotation, text):
    return [match.span() for match in quotation_pattern(quotation).finditer(text)]


def contains_term(text, term):
    return bool(unquoted(term).split()) and term_pattern(term).search(text) is not None


# --- The rules: one function per row of the rules page's table -------------
#
# Each rule returns RuleBreak entries: `flag` is the 1-based number of the flag
# the break is about, or None for a break of the answer as a whole.

class RuleBreak(typing.NamedTuple):
    flag: typing.Optional[int]
    message: str


def meaning_compared_only_for_test_1(answer, document, glossary):
    return [RuleBreak(index, f"meaning_compared is {flag['meaning_compared']!r}, but it is "
                             f"filled exactly when tests_failed has 1")
            for index, flag in enumerate(answer["flags"], 1)
            if (flag["meaning_compared"] != "") != (1 in flag["tests_failed"])]


def fix_count_matches_tests(answer, document, glossary):
    breaks = []
    for index, flag in enumerate(answer["flags"], 1):
        fixes = flag["fixes"]
        if 3 in flag["tests_failed"]:
            if len(fixes) < 2 or not all(fix["uses"] for fix in fixes):
                breaks.append(RuleBreak(index, f"it fails test (3), so it needs one fix per "
                                               f"meaning, at least two, each naming its uses; "
                                               f"it has {len(fixes)}"))
        elif not flag["tests_failed"]:
            if fixes:
                breaks.append(RuleBreak(index, "it fails no test, so its fixes must be empty; "
                                               "the runner adds its fix"))
        elif len(fixes) != 1 or fixes[0]["uses"]:
            breaks.append(RuleBreak(index, f"it needs exactly one fix with empty uses; it has "
                                           f"{len(fixes)}"))
    return breaks


def every_use_of_a_test_3_term_takes_one_fix(answer, document, glossary):
    breaks = []
    for index, flag in enumerate(answer["flags"], 1):
        if 3 not in flag["tests_failed"]:
            continue
        fix_spans = [[span for use in fix["uses"] for span in spans_of(use, document)]
                     for fix in flag["fixes"]]
        for occurrence in term_pattern(flag["term"]).finditer(document):
            start, end = occurrence.span()
            covering = sum(any(left <= start and end <= right for left, right in spans)
                           for spans in fix_spans)
            if covering != 1:
                line = document.count("\n", 0, start) + 1
                breaks.append(RuleBreak(index, f"its use on line {line} of the frozen-copy lies "
                                               f"inside the uses of {covering} fixes, not one"))
    return breaks


def test_1_or_2_names_the_clashing_term(answer, document, glossary):
    breaks = []
    for index, flag in enumerate(answer["flags"], 1):
        if {1, 2} & set(flag["tests_failed"]) and not flag["clashes_with"].strip():
            breaks.append(RuleBreak(index, "it fails test (1) or (2), so clashes_with must name "
                                           "the term it clashes with"))
        if not flag["clashes_with"].strip() and flag["clashes_with_location"] != "":
            breaks.append(RuleBreak(index, "clashes_with is empty, so clashes_with_location "
                                           "must be empty too"))
    return breaks


def flag_fails_a_test_or_quotes_a_second_definition(answer, document, glossary):
    return [RuleBreak(index, "it fails no test and quotes no second definition")
            for index, flag in enumerate(answer["flags"], 1)
            if not flag["tests_failed"] and not flag["second_definition"].strip()]


def term_defined_twice_is_a_glossary_term(answer, document, glossary):
    return [RuleBreak(index, "it quotes a second definition, but no glossary lists the term")
            for index, flag in enumerate(answer["flags"], 1)
            if flag["second_definition"].strip() and glossary.entry_for(flag["term"]) is None]


def strings_carry_content(answer, document, glossary):
    named = [(None, "document_kind", answer["document_kind"])]
    named += [(None, f"key_terms[{index}]", term)
              for index, term in enumerate(answer["key_terms"], 1)]
    named += [(None, f"terms_kept[{index}]", term)
              for index, term in enumerate(answer["terms_kept"], 1)]
    for index, flag in enumerate(answer["flags"], 1):
        named += [(index, f"its {field}", flag[field])
                  for field in ("term", "passage", "restatement")]
        for fix_index, fix in enumerate(flag["fixes"], 1):
            named.append((index, f"its fix {fix_index}'s words", fix["words"]))
            named += [(index, f"its fix {fix_index}'s use {use_index}", use)
                      for use_index, use in enumerate(fix["uses"], 1)]
    for index, proposal in enumerate(answer["proposed_definitions"], 1):
        named += [(None, f"proposed definition {index}'s {field}", proposal[field])
                  for field in ("project_term", "definition")]
    return [RuleBreak(flag, f"{where} is empty") for flag, where, value in named
            if not value.strip()]


def document_kind_is_one_line(answer, document, glossary):
    kind = answer["document_kind"]
    if "\n" in kind or "\r" in kind:
        return [RuleBreak(None, "document_kind holds a line break; it is one line")]
    return []


def test_number_once_per_flag(answer, document, glossary):
    return [RuleBreak(index, "it lists a test number twice in tests_failed")
            for index, flag in enumerate(answer["flags"], 1)
            if len(set(flag["tests_failed"])) != len(flag["tests_failed"])]


def proposed_terms_match_fixes_d(answer, document, glossary):
    proposed = {proposal["project_term"].strip() for proposal in answer["proposed_definitions"]}
    breaks = []
    proposing = set()
    for index, flag in enumerate(answer["flags"], 1):
        for fix in flag["fixes"]:
            if fix["fix"] == FIX_NEW_PROJECT_TERM:
                proposing.add(fix["words"].strip())
                if fix["words"].strip() not in proposed:
                    breaks.append(RuleBreak(index, f"fix (d) {fix['words']!r} has no entry in "
                                                   f"proposed_definitions"))
    breaks += [RuleBreak(None, f"proposed_definitions has {term!r}, which no fix (d) proposes")
               for term in sorted(proposed - proposing)]
    return breaks


def term_is_flagged_or_kept(answer, document, glossary):
    kept = {term.strip().casefold() for term in answer["terms_kept"]}
    return [RuleBreak(index, "it is also in terms_kept")
            for index, flag in enumerate(answer["flags"], 1)
            if flag["term"].strip().casefold() in kept]


def key_terms_are_the_documents_words(answer, document, glossary):
    return [RuleBreak(None, f"key-term {term!r} does not occur in the frozen-copy")
            for term in answer["key_terms"] if term.strip() and not contains_term(document, term)]


def restatement_avoids_the_term_and_six_words(answer, document, glossary):
    breaks = []
    for index, flag in enumerate(answer["flags"], 1):
        avoided = [flag["term"], *WORDS_A_RESTATEMENT_AVOIDS]
        used = [word for word in avoided if contains_term(flag["restatement"], word)]
        if used:
            breaks.append(RuleBreak(index, f"its restatement uses "
                                           f"{', '.join(repr(word) for word in used)}"))
    return breaks


def strings_avoid_flagged_terms_outside_quotation_marks(answer, document, glossary):
    terms = [flag["term"] for flag in answer["flags"]]
    named = [(None, "document_kind", answer["document_kind"])]
    for index, flag in enumerate(answer["flags"], 1):
        named.append((index, "its restatement", flag["restatement"]))
        named += [(index, "its question", fix["words"])
                  for fix in flag["fixes"] if fix["fix"] == FIX_QUESTION]
    named += [(None, f"proposed definition {index}", proposal["definition"])
              for index, proposal in enumerate(answer["proposed_definitions"], 1)]
    breaks = []
    for flag, where, value in named:
        outside = QUOTED_SPAN_PATTERN.sub(" ", value)
        breaks += [RuleBreak(flag, f"{where} uses the flagged term {term!r} outside quotation "
                                   f"marks")
                   for term in terms if contains_term(outside, term)]
    return breaks


def fix_a_is_listed_and_fix_d_is_new(answer, document, glossary):
    breaks = []
    for index, flag in enumerate(answer["flags"], 1):
        for fix in flag["fixes"]:
            listed = glossary.entry_for(fix["words"]) is not None
            if fix["fix"] == FIX_GLOSSARY_NAME and not listed and glossary.entry_for(
                    LEADING_ARTICLE_PATTERN.sub("", unquoted(fix["words"]))) is None:
                breaks.append(RuleBreak(index, f"fix (a) {fix['words']!r} is in no glossary"))
            if fix["fix"] == FIX_NEW_PROJECT_TERM and ("-" not in fix["words"] or listed):
                breaks.append(RuleBreak(index, f"fix (d) {fix['words']!r} must be hyphenated "
                                               f"and in no glossary"))
    return breaks


def passage_uses_the_term(answer, document, glossary):
    return [RuleBreak(index, "its passage does not contain the term")
            for index, flag in enumerate(answer["flags"], 1)
            if flag["term"].strip() and not contains_term(flag["passage"], flag["term"])]


def quotations_are_in_the_document(answer, document, glossary):
    breaks = []
    for index, flag in enumerate(answer["flags"], 1):
        quotations = [("passage", flag["passage"])]
        if flag["second_definition"].strip():
            quotations.append(("second_definition", flag["second_definition"]))
        quotations += [(f"fix {fix_index}'s use {use_index}", use)
                       for fix_index, fix in enumerate(flag["fixes"], 1)
                       for use_index, use in enumerate(fix["uses"], 1)]
        breaks += [RuleBreak(index, f"its {where} is not in the frozen-copy word for word")
                   for where, quotation in quotations
                   if quotation.strip() and not found_in(quotation, document)]
    return breaks


RULE_CHECKS = (
    meaning_compared_only_for_test_1,
    fix_count_matches_tests,
    every_use_of_a_test_3_term_takes_one_fix,
    test_1_or_2_names_the_clashing_term,
    flag_fails_a_test_or_quotes_a_second_definition,
    term_defined_twice_is_a_glossary_term,
    strings_carry_content,
    document_kind_is_one_line,
    test_number_once_per_flag,
    proposed_terms_match_fixes_d,
    term_is_flagged_or_kept,
    key_terms_are_the_documents_words,
    restatement_avoids_the_term_and_six_words,
    strings_avoid_flagged_terms_outside_quotation_marks,
    fix_a_is_listed_and_fix_d_is_new,
    passage_uses_the_term,
    quotations_are_in_the_document,
)


def schema_problems(answer, schema):
    """Every way the answer breaks the schema; empty when it keeps it."""
    not_checked = json_schema_check.schema_keywords_and_types_the_answer_check_does_not_enforce(schema)
    if not_checked:
        return [f"the answer schema uses keywords or types the answer check does not enforce: "
                f"{'; '.join(not_checked)}"]
    return json_schema_check.answer_problems(answer, schema)


def rule_breaks(answer, document, glossary):
    """Every RuleBreak of a schema-valid answer, in rule order."""
    return [found for rule in RULE_CHECKS for found in rule(answer, document, glossary)]


def described(answer, found):
    if found.flag is None:
        return found.message
    return f"flag {found.flag} {answer['flags'][found.flag - 1]['term']!r}: {found.message}"


def terminology_answer_problems(answer, schema, document, glossary):
    """Every way the answer breaks the schema or a rule, each a line; empty when it keeps all."""
    problems = schema_problems(answer, schema)
    if problems:
        return problems
    return [described(answer, found) for found in rule_breaks(answer, document, glossary)]


def too_many_flags_break_a_rule(answer, breaks):
    """True when more than half the flags break a rule: the answer is then rejected."""
    broken = {found.flag for found in breaks if found.flag is not None}
    return 2 * len(broken) > len(answer["flags"])


# --- The lookups ------------------------------------------------------------

def first_occurrence(term, document):
    match = term_pattern(term, plural=True).search(document)
    return match.start() if match else len(document)


def clashes_with_location_looked_up(clashes_with, document, glossary):
    if not clashes_with.strip():
        return ""
    if glossary.entry_for(clashes_with) is not None:
        return LOCATION_GLOSSARY
    if contains_term(document, clashes_with):
        return LOCATION_DOCUMENT
    return LOCATION_STANDARD_VOCABULARY


def prose_only(document):
    """The document with code, URLs, link targets and comments blanked, offsets kept."""
    for pattern in NOT_PROSE_PATTERNS:
        document = pattern.sub(lambda match: re.sub(r"[^\n]", " ", match.group(0)), document)
    return document


def spelled_as_the_glossary_spells_it(written, term):
    if written in (term, term + "s", term + "es"):
        return True
    return term[:1].islower() and written[:1].isupper() and spelled_as_the_glossary_spells_it(
        written[:1].lower() + written[1:], term)


def glossary_terms_written_differently(document, glossary):
    """[(glossary entry, first different spelling, its offset)], in document order."""
    prose = prose_only(document)
    matches = []
    for term in glossary.terms():
        if term.startswith(("/", "-")):
            continue
        words = [re.escape(word) for word in re.split(r"[-\s]+", term) if word]
        if not words:
            continue
        pattern = re.compile(r"(?<![\w-])" + r"[-\s]+".join(words) + r"(?:es|s)?(?![\w-])", re.I)
        matches += [(match.start(), match.end(), term, match.group(0))
                    for match in pattern.finditer(prose)]
    found = {}
    for start, end, term, written in matches:
        inside_a_longer_term = any(other_start <= start and end <= other_end
                                   and (other_end - other_start) > (end - start)
                                   for other_start, other_end, _, _ in matches)
        if (inside_a_longer_term or spelled_as_the_glossary_spells_it(written, term)
                or term in found):
            continue
        found[term] = (glossary.entry_for(term), written, start)
    return sorted(found.values(), key=lambda item: item[2])


def line_around(document, offset):
    start = document.rfind("\n", 0, offset) + 1
    end = document.find("\n", offset)
    line = document[start:end if end != -1 else len(document)]
    if len(line) <= PASSAGE_CONTEXT_CHARACTERS:
        return line.strip()
    left = max(0, offset - start - PASSAGE_CONTEXT_CHARACTERS // 2)
    right = left + PASSAGE_CONTEXT_CHARACTERS
    while left > 0 and not line[left - 1].isspace():
        left -= 1
    while right < len(line) and not line[right].isspace():
        right += 1
    return line[left:right].strip()


def glossary_fix(entry):
    return {"fix": FIX_GLOSSARY_NAME, "words": entry.term, "uses": []}


def terminology_answer_with_runner_lookups(answer, document, glossary, breaks=()):
    """The answer with every lookup of the rules page's last section made, and each
    RuleBreak in breaks kept with its flag, or with the answer when it names none."""
    looked_up = copy.deepcopy(answer)
    looked_up["rule_breaks"] = [found.message for found in breaks if found.flag is None]
    for index, flag in enumerate(looked_up["flags"], 1):
        flag["rule_breaks"] = [found.message for found in breaks if found.flag == index]
    for flag in looked_up["flags"]:
        flag["found_by_runner"] = False
        flag["clashes_with_location"] = clashes_with_location_looked_up(
            flag["clashes_with"], document, glossary)
        entry = glossary.entry_for(flag["term"]) if flag["second_definition"].strip() else None
        flag["glossary_entry"] = entry.entry_line if entry else ""
        flag["glossary_entry_path"] = entry.glossary_path if entry else ""
        if entry and not flag["tests_failed"]:
            flag["fixes"] = [glossary_fix(entry)]
    for entry, written, offset in glossary_terms_written_differently(document, glossary):
        flagged = next((flag for flag in looked_up["flags"]
                        if glossary.entry_for(flag["term"]) == entry
                        or flag["term"].strip() == written), None)
        if flagged is not None:
            if DIFFERENTLY_WRITTEN_GLOSSARY_TERM_TEST not in flagged["tests_failed"]:
                flagged["tests_failed"].append(DIFFERENTLY_WRITTEN_GLOSSARY_TERM_TEST)
            if glossary_fix(entry) not in flagged["fixes"]:
                flagged["fixes"].append(glossary_fix(entry))
            continue
        looked_up["flags"].append({
            "term": written, "passage": line_around(document, offset),
            "clashes_with": entry.term, "clashes_with_location": LOCATION_GLOSSARY,
            "second_definition": "", "meaning_compared": "", "restatement": "",
            "tests_failed": [DIFFERENTLY_WRITTEN_GLOSSARY_TERM_TEST],
            "fixes": [glossary_fix(entry)], "found_by_runner": True,
            "glossary_entry": "", "glossary_entry_path": "", "rule_breaks": []})
    for flag in looked_up["flags"]:
        flag["first_offset"] = first_occurrence(flag["term"], document)
        flag["tests_failed"].sort()
    looked_up["flags"].sort(key=lambda flag: flag["first_offset"])
    looked_up["key_terms_no_glossary_lists"] = [
        term for term in answer["key_terms"] if glossary.entry_for(term) is None]
    return looked_up


# --- The report ---------------------------------------------------------------

LOCATION_WORDS = {LOCATION_GLOSSARY: "a glossary", LOCATION_DOCUMENT: "the document",
                  LOCATION_STANDARD_VOCABULARY: "standard software vocabulary"}


def quoted(text):
    return f'"{text}"'


def rendered_fix(fix):
    if fix["fix"] == FIX_QUESTION:
        line = f"Question for the author: {fix['words']}"
    else:
        line = f"Fix ({fix['fix']}): {fix['words']}"
    if fix["uses"]:
        line += "; for the uses " + "; ".join(quoted(use) for use in fix["uses"])
    return line


def rendered_flag(number, flag, document):
    tests = ", ".join(f"({test})" for test in flag["tests_failed"]) or "none"
    line = document.count("\n", 0, flag["first_offset"]) + 1
    lines = [f"{number}. {quoted(flag['term'])}, first on line {line}; tests failed: {tests}"]
    lines += [f"   - {RULE_BREAK_MARK}{message}" for message in flag["rule_breaks"]]
    if flag["found_by_runner"]:
        lines.append("   - Found by the runner: a glossary term written with a different case, "
                     "hyphen or plural.")
    lines.append(f"   - Passage: {quoted(flag['passage'])}")
    if flag["clashes_with"].strip():
        lines.append(f"   - Clashes with: {flag['clashes_with']}, from "
                     f"{LOCATION_WORDS[flag['clashes_with_location']]}")
    if flag["meaning_compared"]:
        lines.append(f"   - Its meaning compared with that term: {flag['meaning_compared']}")
    if flag["second_definition"].strip():
        lines.append(f"   - Defined twice: the document says {quoted(flag['second_definition'])}; "
                     f"drop it for the glossary's entry, in {flag['glossary_entry_path']}: "
                     f"{flag['glossary_entry']}")
    if flag["restatement"].strip():
        lines.append(f"   - Restatement: {flag['restatement']}")
    lines += [f"   - {rendered_fix(fix)}" for fix in flag["fixes"]]
    return lines


def counts_line(looked_up):
    per_test = ", ".join(
        f"test ({test}): {sum(test in flag['tests_failed'] for flag in looked_up['flags'])}"
        for test in TESTS)
    return (f"Counts: {len(looked_up['key_terms'])} key-terms, "
            f"{len(looked_up['key_terms_no_glossary_lists'])} of them in no glossary; "
            f"{len(looked_up['flags'])} flagged terms, "
            f"{sum(bool(flag['rule_breaks']) for flag in looked_up['flags'])} of them marked "
            f"by a failed runner check; {per_test}; "
            f"{len(looked_up['proposed_definitions'])} proposed definitions; "
            f"{len(looked_up['terms_kept'])} terms kept.")


def terminology_report(looked_up, document):
    lines = ["# Terminology report", "", f"Document: {looked_up['document_kind']}", ""]
    if looked_up["rule_breaks"]:
        lines += ["Failed runner checks on the answer as a whole:", ""]
        lines += [f"- {RULE_BREAK_MARK}{message}" for message in looked_up["rule_breaks"]]
        lines.append("")
    lines += ["## Flagged terms", ""]
    if looked_up["flags"]:
        for number, flag in enumerate(looked_up["flags"], 1):
            lines += rendered_flag(number, flag, document)
    else:
        lines.append("No term flagged.")
    lines += ["", "## Proposed definitions", ""]
    lines += ([f"- **{proposal['project_term']}** — {proposal['definition']}"
               for proposal in looked_up["proposed_definitions"]] or ["None."])
    lines += ["", "## Key-terms no glossary lists", "",
              "Each is a candidate for the user to add to a glossary; it needs no flag.", ""]
    lines += ([f"- {quoted(term)}" for term in looked_up["key_terms_no_glossary_lists"]]
              or ["None."])
    lines += ["", "terms listed and kept: "
              + (", ".join(quoted(term) for term in looked_up["terms_kept"]) or "none"),
              "", counts_line(looked_up)]
    return "\n".join(lines) + "\n"


def terminology_report_from_answer(answer, schema, document, glossary_entries):
    """The rendered report, each rule break marked on its flag or on the answer; raises
    TerminologyAnswerRejected when the answer breaks the schema, or when more than half
    its flags break a rule."""
    glossary = Glossary.of(glossary_entries)
    problems = schema_problems(answer, schema)
    if problems:
        raise TerminologyAnswerRejected(problems)
    breaks = rule_breaks(answer, document, glossary)
    if too_many_flags_break_a_rule(answer, breaks):
        broken = len({found.flag for found in breaks if found.flag is not None})
        raise TerminologyAnswerRejected(
            [f"{broken} of its {len(answer['flags'])} flags break a rule, more than half"]
            + [described(answer, found) for found in breaks])
    return terminology_report(
        terminology_answer_with_runner_lookups(answer, document, glossary, breaks), document)
