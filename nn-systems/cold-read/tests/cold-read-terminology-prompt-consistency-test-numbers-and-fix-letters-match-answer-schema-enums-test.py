#!/usr/bin/env python3
"""The terminology prompt's numbered tests and lettered fixes match its answer schema.

`.claude/skills/cold-read/prompts/terminology-prompt.md` lists the tests a term
can fail, as lines opening (1) to (5), and the fixes, as lines opening (a) to
(d). `.claude/skills/cold-read/prompts/terminology-answer-schema.json` lists
the same numbers as the enum of `tests_failed` and the same letters, plus
"question", as the enum of a fix's `fix`, and its descriptions name the ranges
as "tests (1) to (5)" and "fixes (a) to (d)". The model answers from both
files, so a test or fix added to one and not the other leaves it a choice it
cannot make, or an answer the schema refuses.

The mismatch cases at the end run the same comparison on altered copies of
the two files, and fail if the comparison stops seeing a difference.

Run: python3 nc-systems/cold-read/tests/cold-read-terminology-prompt-consistency-test-numbers-and-fix-letters-match-answer-schema-enums-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPTS_DIR = REPO_ROOT / ".claude" / "skills" / "cold-read" / "prompts"
PROMPT_FILE = PROMPTS_DIR / "terminology-prompt.md"
SCHEMA_FILE = PROMPTS_DIR / "terminology-answer-schema.json"
_rule_failure_lines_spec = importlib.util.spec_from_file_location(
    "rule_enforcing_nc_test_suite_failure_message_closing_lines_text_common",
    REPO_ROOT / "nc-systems" / "general-tools"
    / "rule-enforcing-nc-test-suite-failure-message-closing-lines-text-common.py")
RULE_FAILURE_LINES = importlib.util.module_from_spec(_rule_failure_lines_spec)
_rule_failure_lines_spec.loader.exec_module(RULE_FAILURE_LINES)

# The fix the model gives when it asks the author instead; the prompt names it
# in prose, not as a lettered line.
QUESTION_FIX = "question"

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def prompt_tests_and_fixes(prompt_text):
    """The prompt's test numbers and fix letters, in the order its lines give them."""
    tests = [int(number) for number in re.findall(r"^\((\d+)\) ", prompt_text, re.MULTILINE)]
    fixes = re.findall(r"^\(([a-z])\) ", prompt_text, re.MULTILINE)
    return tests, fixes


def schema_tests_and_fixes(schema):
    """The schema's test-number enum, fix-letter enum and the two descriptions that name their ranges."""
    flag = schema["properties"]["flags"]["items"]["properties"]
    tests_failed = flag["tests_failed"]
    fix = flag["fixes"]["items"]["properties"]["fix"]
    return (tests_failed["items"]["enum"], [letter for letter in fix["enum"] if letter != QUESTION_FIX],
            tests_failed["description"], fix["description"])


def differences(prompt_text, schema):
    """Each way the prompt's tests and fixes differ from the schema's lists, as a sentence."""
    prompt_tests, prompt_fixes = prompt_tests_and_fixes(prompt_text)
    schema_tests, schema_fixes, tests_description, fix_description = schema_tests_and_fixes(schema)
    found = []
    if prompt_tests != schema_tests:
        found.append(f"the prompt's tests are {prompt_tests}, but the schema's tests_failed enum is "
                     f"{schema_tests}")
    if prompt_fixes != schema_fixes:
        found.append(f"the prompt's fixes are {prompt_fixes}, but the schema's fix enum, without "
                     f"{QUESTION_FIX!r}, is {schema_fixes}")
    if prompt_tests:
        tests_range = f"tests ({prompt_tests[0]}) to ({prompt_tests[-1]})"
        if tests_range not in tests_description:
            found.append(f"the schema's tests_failed description does not say {tests_range!r}: "
                         f"{tests_description!r}")
    if prompt_fixes:
        fixes_range = f"fixes ({prompt_fixes[0]}) to ({prompt_fixes[-1]})"
        if fixes_range not in fix_description:
            found.append(f"the schema's fix description does not say {fixes_range!r}: "
                         f"{fix_description!r}")
    if not prompt_tests or not prompt_fixes:
        found.append("the prompt has no line opening with a test number such as (1) or no line "
                     "opening with a fix letter such as (a), so nothing could be compared")
    return found


def failure_detail(found):
    return "\n".join(
        ["", *("  " + line for line in found),
         f"  Make {PROMPT_FILE.relative_to(REPO_ROOT)} and {SCHEMA_FILE.relative_to(REPO_ROOT)} "
         "list the same tests and fixes.",
         "  " + RULE_FAILURE_LINES.guarded_file_fix_failure_message_line_pointing_to_approval_page_and_guard_refusal(
             str(PROMPTS_DIR.relative_to(REPO_ROOT)) + "/"),
         "  " + RULE_FAILURE_LINES.FAILURE_MAY_COME_FROM_MAIN_NOT_YOUR_CHANGE_REPORT_IT_CLOSING_LINE])


prompt_text = PROMPT_FILE.read_text(encoding="utf-8")
schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))

found = differences(prompt_text, schema)
check("the prompt's tests (1) to (5) and fixes (a) to (d) match the schema's lists",
      not found, failure_detail(found))


def schema_copy(change):
    copy = json.loads(json.dumps(schema))
    change(copy["properties"]["flags"]["items"]["properties"])
    return copy


def drop_fix_d(flag):
    flag["fixes"]["items"]["properties"]["fix"]["enum"].remove("d")


def add_test_6(flag):
    flag["tests_failed"]["items"]["enum"].append(6)


def change_tests_range(flag):
    flag["tests_failed"]["description"] = flag["tests_failed"]["description"].replace(
        "tests (1) to (5)", "tests (1) to (4)")


MISMATCH_CASES = [
    ("a test (6) added to the prompt alone",
     prompt_text.replace("\n(5) ", "\n(6) is new;\n(5) ", 1), schema),
    ("test (5) removed from the prompt alone",
     re.sub(r"^\(5\) .*\n", "", prompt_text, count=1, flags=re.MULTILINE), schema),
    ("a fix (e) added to the prompt alone",
     prompt_text.replace("\n(d) ", "\n(e) is new;\n(d) ", 1), schema),
    ("fix d removed from the schema alone", prompt_text, schema_copy(drop_fix_d)),
    ("a test 6 added to the schema alone", prompt_text, schema_copy(add_test_6)),
    ("the schema's tests_failed description naming another range", prompt_text,
     schema_copy(change_tests_range)),
    ("a prompt with no numbered or lettered lines", "no lists here", schema),
]
for case_name, case_prompt, case_schema in MISMATCH_CASES:
    check(f"mismatch case, {case_name}, is reported", differences(case_prompt, case_schema),
          "the comparison found no difference")

sys.exit(1 if failures else 0)
