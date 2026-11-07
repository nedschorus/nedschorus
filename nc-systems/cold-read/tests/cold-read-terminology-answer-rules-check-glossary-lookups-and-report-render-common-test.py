#!/usr/bin/env python3
"""Tests for cold-read-terminology-answer-rules-check-glossary-lookups-and-report-render-common.py.

One valid answer about one small document is the base. Each rule case
changes one field of a copy and checks that the answer is rejected with that
rule's words, and that the base still passes, so a rule that stopped firing,
or one that fired on a valid answer, fails here. The lookup and report cases
read what the runner adds to the base.

Run: python3 nc-systems/cold-read/tests/cold-read-terminology-answer-rules-check-glossary-lookups-and-report-render-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import copy
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

SYSTEM_DIRECTORY = Path(__file__).resolve().parent.parent
REPO_ROOT = SYSTEM_DIRECTORY.parent.parent
SCHEMA = json.loads((REPO_ROOT / ".claude" / "skills" / "cold-read" / "prompts"
                     / "terminology-answer-schema.json").read_text(encoding="utf-8"))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


terminology = load(
    "cold_read_terminology_answer_rules_check_glossary_lookups_and_report_render_common",
    SYSTEM_DIRECTORY / "cold-read-terminology-answer-rules-check-glossary-lookups-and-report-render-common.py")
glossary_reader = load(
    "glossary_entries_of_project_and_system_glossaries_read_common",
    REPO_ROOT / "nc-systems" / "general-tools"
    / "glossary-entries-of-project-and-system-glossaries-read-common.py")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


GLOSSARY_TEXT = """# Glossary

- **agent-seat** — a named, long-lived agent identity.
- **cold-read-cell** — one fresh-agent reviewing one cold-read-target.
- **code-prompt-code (aka CPC)** — a program whose code does every step that needs no judgment.
- **code-based-test**, **prompt-based-test** — a test of code, or of a prompt.
- **obvious-error** — a mistake in prose.
- **obvious-error-fix** — replacing an obvious-error.
- **/cold-read** — a skill.
"""
ENTRIES = glossary_reader.glossary_entries_in_text(GLOSSARY_TEXT, "docs/glossary.md")
GLOSSARY = terminology.Glossary.of(ENTRIES)

DOCUMENT = """# A small design

The worker takes a slot from the queue. A slot here also means a time window.
An agent-seat is a long-lived agent, as this design defines it.
Each cold-read-cell bumps the counter.
"""


def base_answer():
    return {
        "document_kind": "a design for agents to build from",
        "key_terms": ["slot", "agent-seat", "worker"],
        "flags": [
            {"term": "bumps", "passage": "Each cold-read-cell bumps the counter.",
             "clashes_with": "\"increment\"", "clashes_with_location": "standard_vocabulary",
             "second_definition": "", "meaning_compared": "same",
             "restatement": "adds one to a number", "tests_failed": [1],
             "fixes": [{"fix": "b", "words": "increments", "uses": []}]},
            {"term": "slot", "passage": "The worker takes a slot from the queue.",
             "clashes_with": "", "clashes_with_location": "", "second_definition": "",
             "meaning_compared": "", "restatement": "a queue entry, or a time window",
             "tests_failed": [3],
             "fixes": [{"fix": "c", "words": "queue entry",
                        "uses": ["The worker takes a slot from the queue."]},
                       {"fix": "d", "words": "time-window-share",
                        "uses": ["A slot here also means a time window."]}]},
            {"term": "agent-seat", "passage": "An agent-seat is a long-lived agent",
             "clashes_with": "", "clashes_with_location": "",
             "second_definition": "An agent-seat is a long-lived agent, as this design defines it.",
             "meaning_compared": "", "restatement": "a named agent that lasts",
             "tests_failed": [], "fixes": []},
        ],
        "proposed_definitions": [{"project_term": "time-window-share",
                                  "definition": "the share of time a worker gets."}],
        "terms_kept": ["worker", "queue"],
    }


def problems_of(answer):
    return terminology.terminology_answer_problems(answer, SCHEMA, DOCUMENT, GLOSSARY)


check("the base answer keeps the schema and every rule", problems_of(base_answer()) == [],
      problems_of(base_answer()))


def rejects(case_name, change, expected):
    answer = base_answer()
    change(answer)
    problems = problems_of(answer)
    check(case_name, any(expected in problem for problem in problems), problems)


def flag(answer, index):
    return answer["flags"][index]


# --- The schema, then each row of the rules page's table --------------------
rejects("a field the schema requires is missing",
        lambda a: a.pop("terms_kept"), "the answer has no terms_kept")
rejects("a test number outside the schema's enum",
        lambda a: flag(a, 0).update(tests_failed=[6]), "is not one of 1, 2, 3, 4, 5")
rejects("meaning_compared filled without test (1)",
        lambda a: flag(a, 1).update(meaning_compared="wider"), "meaning_compared is 'wider'")
rejects("meaning_compared empty with test (1)",
        lambda a: flag(a, 0).update(meaning_compared=""), "meaning_compared is ''")
rejects("a test (3) flag with one fix",
        lambda a: flag(a, 1)["fixes"].pop(), "needs one fix per meaning")
rejects("a test (3) fix with no uses",
        lambda a: flag(a, 1)["fixes"][0].update(uses=[]), "needs one fix per meaning")
rejects("a flag failing no test that carries a fix",
        lambda a: flag(a, 2).update(fixes=[{"fix": "a", "words": "agent-seat", "uses": []}]),
        "fails no test, so its fixes must be empty")
rejects("a flag failing one test with two fixes",
        lambda a: flag(a, 0)["fixes"].append({"fix": "b", "words": "adds", "uses": []}),
        "needs exactly one fix with empty uses")
rejects("a single fix that lists uses",
        lambda a: flag(a, 0)["fixes"][0].update(uses=["bumps the counter"]),
        "needs exactly one fix with empty uses")
rejects("a use of a test (3) term in no fix's uses",
        lambda a: flag(a, 1)["fixes"][1].update(uses=["a time window"]),
        "line 3 of the frozen-copy lies inside the uses of 0 fixes")
rejects("a use of a test (3) term in two fixes' uses",
        lambda a: flag(a, 1)["fixes"][1]["uses"].append("The worker takes a slot"),
        "lies inside the uses of 2 fixes")
rejects("test (1) with no clashing term",
        lambda a: flag(a, 0).update(clashes_with="", clashes_with_location=""),
        "must name the term it clashes with")
rejects("an empty clashes_with with a location",
        lambda a: flag(a, 1).update(clashes_with_location="standard_vocabulary"),
        "clashes_with_location must be empty too")
rejects("a flag that fails no test and quotes no second definition",
        lambda a: flag(a, 2).update(second_definition=""),
        "fails no test and quotes no second definition")
rejects("a second definition of a term no glossary lists",
        lambda a: (flag(a, 2).update(term="long-lived agent",
                                     passage="An agent-seat is a long-lived agent"),
                   a["key_terms"].append("long-lived agent")),
        "no glossary lists the term")
rejects("an empty restatement", lambda a: flag(a, 0).update(restatement=" "),
        "flag 1's restatement is empty")
rejects("an empty key-term", lambda a: a["key_terms"].append(""), "key_terms[4] is empty")
rejects("an empty use", lambda a: flag(a, 1)["fixes"][0]["uses"].append("  "), "use 2 is empty")
rejects("an empty definition",
        lambda a: a["proposed_definitions"][0].update(definition=""), "definition is empty")
rejects("document_kind on two lines",
        lambda a: a.update(document_kind="a design\nfor agents"), "holds a line break")
rejects("a test number twice", lambda a: flag(a, 0).update(tests_failed=[1, 1]),
        "lists a test number twice")
rejects("a fix (d) with no proposed definition",
        lambda a: a["proposed_definitions"].clear(), "has no entry in proposed_definitions")
rejects("a proposed definition no fix (d) proposes",
        lambda a: a["proposed_definitions"].append(
            {"project_term": "spare-term", "definition": "unused."}),
        "which no fix (d) proposes")
rejects("a flagged term that is also kept",
        lambda a: a["terms_kept"].append("Slot"), "is also in terms_kept")
rejects("a key-term the document does not hold",
        lambda a: a["key_terms"].append("gadget"), "key-term 'gadget' does not occur")
rejects("a restatement that uses the term",
        lambda a: flag(a, 1).update(restatement="a Slot in the queue"), "uses 'slot'")
rejects("a restatement that uses one of the six words",
        lambda a: flag(a, 0).update(restatement="a kind of adding"), "uses 'kind'")
rejects("a flagged term outside quotation marks in document_kind",
        lambda a: a.update(document_kind="a design about each slot"),
        "document_kind uses the flagged term 'slot'")
rejects("a flagged term outside quotation marks in a question",
        lambda a: flag(a, 0).update(fixes=[{"fix": "question", "words": "Which slot?",
                                            "uses": []}]),
        "flag 1's question uses the flagged term 'slot'")
rejects("a fix (a) naming no glossary term",
        lambda a: flag(a, 0).update(fixes=[{"fix": "a", "words": "incrementer", "uses": []}]),
        "fix (a) 'incrementer' is in no glossary")
rejects("a fix (d) without a hyphen",
        lambda a: (flag(a, 1)["fixes"][1].update(words="timeshare"),
                   a["proposed_definitions"][0].update(project_term="timeshare")),
        "must be hyphenated and in no glossary")
rejects("a fix (d) a glossary already lists",
        lambda a: (flag(a, 1)["fixes"][1].update(words="cold-read-cell"),
                   a["proposed_definitions"][0].update(project_term="cold-read-cell")),
        "must be hyphenated and in no glossary")
rejects("a passage without the term",
        lambda a: flag(a, 0).update(passage="the counter."), "passage does not contain the term")
rejects("a passage not in the document",
        lambda a: flag(a, 0).update(passage="Each cell bumps a counter."),
        "its passage is not in the frozen-copy word for word")
rejects("a second definition not in the document",
        lambda a: flag(a, 2).update(second_definition="An agent-seat is an agent."),
        "its second_definition is not in the frozen-copy")

answer = base_answer()
answer["flags"][0]["passage"] = "Each   cold-read-cell\nbumps the counter."
check("a quotation matches across a different run of whitespace", problems_of(answer) == [],
      problems_of(answer))
answer = base_answer()
answer["flags"][1]["restatement"] = 'not the "slot" of a calendar, but a queue entry'
check("a flagged term inside quotation marks in a restatement still fails the restatement rule",
      any("uses 'slot'" in problem for problem in problems_of(answer)), problems_of(answer))
answer = base_answer()
answer["flags"][0]["fixes"] = [{"fix": "question", "words": 'Is "slot" a queue entry?',
                                "uses": []}]
check("a flagged term inside quotation marks in a question is allowed",
      problems_of(answer) == [], problems_of(answer))
answer = base_answer()
answer["flags"][0]["fixes"] = [{"fix": "a", "words": "Agent seats", "uses": []}]
check("a fix (a) is a glossary term whatever its case, hyphen or plural",
      problems_of(answer) == [], problems_of(answer))
for words in ("the agent-seat", "An agent-seat", '"a cold-read-cell"', "`the cold-read-cell`"):
    answer = base_answer()
    answer["flags"][0]["fixes"] = [{"fix": "a", "words": words, "uses": []}]
    check(f"a fix (a) written {words!r} is a glossary term", problems_of(answer) == [],
          problems_of(answer))
rejects("a fix (a) of two glossary terms joined by 'or' is in no glossary",
        lambda a: flag(a, 0).update(fixes=[{"fix": "a", "words": "agent-seat or cold-read-cell",
                                            "uses": []}]),
        "is in no glossary")
rejects("a leading article does not excuse a fix (a) naming no glossary term",
        lambda a: flag(a, 0).update(fixes=[{"fix": "a", "words": "the incrementer", "uses": []}]),
        "fix (a) 'the incrementer' is in no glossary")

unchecked_schema = copy.deepcopy(SCHEMA)
unchecked_schema["properties"]["document_kind"]["pattern"] = "."
problems = terminology.terminology_answer_problems(base_answer(), unchecked_schema, DOCUMENT,
                                                   GLOSSARY)
check("a schema keyword the check does not enforce rejects every answer",
      len(problems) == 1 and "document_kind: pattern" in problems[0], problems)

try:
    terminology.terminology_report_from_answer(
        dict(base_answer(), document_kind=""), SCHEMA, DOCUMENT, ENTRIES)
    raised = None
except terminology.TerminologyAnswerRejected as rejected:
    raised = rejected
check("terminology_report_from_answer raises TerminologyAnswerRejected listing the problems",
      raised is not None and raised.problems == ["document_kind is empty"],
      raised and raised.problems)

# --- The lookups ------------------------------------------------------------
looked_up = terminology.terminology_answer_with_runner_lookups(base_answer(), DOCUMENT, GLOSSARY)
by_term = {flag["term"]: flag for flag in looked_up["flags"]}
check("flags are sorted by where each term first appears",
      [flag["term"] for flag in looked_up["flags"]] == ["slot", "agent-seat", "bumps"],
      [flag["term"] for flag in looked_up["flags"]])
check("a term defined twice gets the glossary's entry, word for word",
      by_term["agent-seat"]["glossary_entry"]
      == "- **agent-seat** — a named, long-lived agent identity."
      and by_term["agent-seat"]["glossary_entry_path"] == "docs/glossary.md",
      by_term["agent-seat"])
check("a term defined twice that fails no test gets fix (a), the glossary's spelling",
      by_term["agent-seat"]["fixes"] == [{"fix": "a", "words": "agent-seat", "uses": []}],
      by_term["agent-seat"]["fixes"])
check("a standard_vocabulary location stays when no list holds the term",
      by_term["bumps"]["clashes_with_location"] == "standard_vocabulary", by_term["bumps"])
check("the key-terms no glossary lists are listed",
      looked_up["key_terms_no_glossary_lists"] == ["slot", "worker"],
      looked_up["key_terms_no_glossary_lists"])
check("the lookups leave the model's answer unchanged",
      base_answer() == base_answer() and "found_by_runner" not in base_answer()["flags"][0])

answer = base_answer()
answer["flags"][0]["clashes_with"] = "cold-read-cell"
check("a clashing term a glossary lists is located in the glossary, over standard_vocabulary",
      terminology.terminology_answer_with_runner_lookups(answer, DOCUMENT, GLOSSARY)
      ["flags"][2]["clashes_with_location"] == "glossary")
answer["flags"][0]["clashes_with"] = "\"counter\""
check("a clashing term the document holds is located in the document, over standard_vocabulary",
      terminology.terminology_answer_with_runner_lookups(answer, DOCUMENT, GLOSSARY)
      ["flags"][2]["clashes_with_location"] == "document")

variant_document = (
    "The agent seat runs. Agent seats rest. Each Cold-Read-Cell reads; agent-seats too.\n"
    "An Agent-seat starts a sentence. `agent seat` in code, and [x](agent%20seat) too.\n"
    "An obvious error fix, a cpc, and nc-systems/code based test.\n"
    "The /cold-read skill.\n")
found = terminology.glossary_terms_written_differently(variant_document, GLOSSARY)
check("Part 5 finds a glossary term written with a space, a case or a plural, once per term",
      [(entry.term, written) for entry, written, _ in found]
      == [("agent-seat", "agent seat"), ("cold-read-cell", "Cold-Read-Cell"),
          ("obvious-error-fix", "obvious error fix"), ("CPC", "cpc"),
          ("code-based-test", "code based test")],
      [(entry.term, written) for entry, written, _ in found])

flagged_variant = {
    "document_kind": "notes", "key_terms": [], "terms_kept": [], "proposed_definitions": [],
    "flags": [{"term": "agent seat", "passage": "The agent seat runs.", "clashes_with": "",
               "clashes_with_location": "", "second_definition": "", "meaning_compared": "",
               "restatement": "a lasting named agent", "tests_failed": [2],
               "fixes": [{"fix": "c", "words": "worker", "uses": []}]}]}
looked_up = terminology.terminology_answer_with_runner_lookups(
    flagged_variant, variant_document, GLOSSARY)
merged = [flag for flag in looked_up["flags"] if flag["term"] == "agent seat"]
check("Part 5 adds test (5) and fix (a) to the model's flag of that term, not a second flag",
      len(merged) == 1 and merged[0]["tests_failed"] == [2, 5]
      and merged[0]["fixes"][-1] == {"fix": "a", "words": "agent-seat", "uses": []}
      and not merged[0]["found_by_runner"], merged)
added = [flag for flag in looked_up["flags"] if flag["found_by_runner"]]
check("Part 5 adds a test (5) flag with fix (a) for a term the model did not flag",
      [flag["term"] for flag in added] == ["Cold-Read-Cell", "obvious error fix", "cpc",
                                           "code based test"]
      and added[0]["fixes"] == [{"fix": "a", "words": "cold-read-cell", "uses": []}]
      and added[0]["clashes_with_location"] == "glossary"
      and "Cold-Read-Cell" in added[0]["passage"], added)

long_line = ("word " * 60) + "the agent seat runs " + ("tail " * 60)
cut = terminology.line_around(long_line, long_line.index("agent seat"))
check("a passage the runner quotes from a long line is cut at whitespace, not inside a word",
      "agent seat" in cut and set(cut.split()) <= {"word", "the", "agent", "seat", "runs", "tail"}
      and long_line.find(cut) != -1, cut)
odd_line = ("x" * 7 + " ") * 40 + "the agent seat runs" + (" y" + "y" * 6) * 40
cut = terminology.line_around(odd_line, odd_line.index("agent seat"))
check("a passage cut at whitespace keeps whole words at both ends",
      cut.split()[0] == "x" * 7 and cut.split()[-1] == "y" * 7, cut)

# --- The report ---------------------------------------------------------------
report = terminology.terminology_report_from_answer(base_answer(), SCHEMA, DOCUMENT, ENTRIES)
check("the report opens with the document's kind",
      report.startswith("# Terminology report\n\nDocument: a design for agents to build from\n"),
      report[:200])
check("each flag is numbered with its test numbers, in document order",
      '1. "slot", first on line 3; tests failed: (3)' in report
      and '2. "agent-seat", first on line 4; tests failed: none' in report
      and '3. "bumps", first on line 5; tests failed: (1)' in report, report)
check("a test (3) fix names its uses",
      'Fix (c): queue entry; for the uses "The worker takes a slot from the queue."' in report,
      report)
check("a term defined twice shows both definitions",
      'Defined twice: the document says "An agent-seat is a long-lived agent, as this design '
      'defines it."; drop it for the glossary\'s entry, in docs/glossary.md: - **agent-seat** — '
      'a named, long-lived agent identity.' in report, report)
check("the clashing term says where it is from",
      'Clashes with: "increment", from standard software vocabulary' in report, report)
check("the proposed definitions and the missing key-terms have their sections",
      "- **time-window-share** — the share of time a worker gets." in report
      and '## Key-terms no glossary lists' in report and '- "worker"' in report, report)
check("the terms kept are listed on one line",
      'terms listed and kept: "worker", "queue"' in report, report)
check("the report closes with the counts line",
      report.rstrip().splitlines()[-1]
      == "Counts: 3 key-terms, 2 of them in no glossary; 3 flagged terms; test (1): 1, "
         "test (2): 0, test (3): 1, test (4): 0, test (5): 0; 1 proposed definitions; "
         "2 terms kept.", report.rstrip().splitlines()[-1])
empty = {"document_kind": "notes", "key_terms": [], "flags": [], "proposed_definitions": [],
         "terms_kept": []}
empty_report = terminology.terminology_report_from_answer(empty, SCHEMA, "notes\n", ENTRIES)
check("an answer with no flag says so",
      "No term flagged." in empty_report and "terms listed and kept: none" in empty_report,
      empty_report)

# --- The glossary reader --------------------------------------------------------
terms = [entry.term for entry in ENTRIES]
check("an entry's aka alias and each bold name of a shared entry are terms; definitions are not",
      terms == ["agent-seat", "cold-read-cell", "code-prompt-code", "CPC", "code-based-test",
                "prompt-based-test", "obvious-error", "obvious-error-fix", "/cold-read"],
      terms)
check("glossary_terms keeps the first bold name of each entry",
      glossary_reader.glossary_terms(GLOSSARY_TEXT)
      == {"agent-seat", "cold-read-cell", "code-prompt-code (aka CPC)", "code-based-test",
          "obvious-error", "obvious-error-fix", "/cold-read"},
      glossary_reader.glossary_terms(GLOSSARY_TEXT))
real_entries = glossary_reader.glossary_entries_of_checkout(REPO_ROOT)
check("the checkout's glossaries are read, the project glossary and a system glossary included",
      {"docs/nedschorus-wiki/nedschorus-glossary.md", "nc-systems/handoff/handoff-system-glossary.md"}
      <= {entry.glossary_path for entry in real_entries}
      and any(entry.term == "agent-seat" for entry in real_entries))
check("the system glossaries are the paths the project glossary names above its entries",
      glossary_reader.system_glossary_paths_named_on_project_glossary(
          "Lists `a/one-glossary.md`, [two](../../b/two-glossary.md) and "
          "docs/nedschorus-wiki/nedschorus-glossary.md.\n\n- **x** — see c/three-glossary.md\n")
      == ["a/one-glossary.md", "b/two-glossary.md"])
with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)
    try:
        glossary_reader.glossary_entries_of_checkout(scratch)
        unreadable = None
    except glossary_reader.GlossaryFilesUnreadable as error:
        unreadable = error
    check("a checkout without the project glossary raises GlossaryFilesUnreadable",
          unreadable is not None and "could not read the project glossary" in str(unreadable),
          str(unreadable))
    page = scratch / "docs" / "nedschorus-wiki" / "nedschorus-glossary.md"
    page.parent.mkdir(parents=True)
    page.write_text("Also `x/gone-glossary.md`.\n\n- **a** — b\n", encoding="utf-8")
    try:
        glossary_reader.glossary_entries_of_checkout(scratch)
        unreadable = None
    except glossary_reader.GlossaryFilesUnreadable as error:
        unreadable = error
    check("a system glossary the project glossary names but the checkout lacks raises",
          unreadable is not None and "x/gone-glossary.md, a system glossary" in str(unreadable),
          str(unreadable))

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
