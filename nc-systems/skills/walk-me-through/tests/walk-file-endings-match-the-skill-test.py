#!/usr/bin/env python3
"""The walk-me-through skill names the walk files' endings, and this test
keeps the two programs that build those names agreeing with it.

A walk's files are `<name>-draft.md`, `<name>-cold-read-fast-read.md`, `<name>.md`,
`<name>-minutes.md` and, for a walk on a cold-read-full-run,
`<name>-dispositions.md`. `.claude/skills/walk-me-through/SKILL.md` is where
that list is decided, and two programs carry a copy in code:
nc-systems/cold-read/cold-read-fast-read.py, which puts a walk draft's report beside it,
and nc-systems/skills/walk-me-through/walk-files-ship.py, which ships all five to the log-store. The
shipper also ships an earlier walk's report under the ending the skill named
before, `<name>-suggestions.md`; that one ending is held to the shipper's
own constant here instead of to the skill.

Prose cannot import a constant, so the skill cannot be the single definition
the way a module can. The tie-break is this test instead: the skill's text
governs, and a program whose ending is not in that text fails here (user-ruled
2026-09-19, walk file-naming-and-location-standards-cold-read-findings, item
4). It is deliberately one-directional -- the skill may name an ending no
program builds yet, but no program may build one the skill does not name.

Run: python3 nc-systems/skills/walk-me-through/tests/walk-file-endings-match-the-skill-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SKILL_FILE_RELATIVE_PATH = ".claude/skills/walk-me-through/SKILL.md"
SKILL_FILE = REPO_ROOT / SKILL_FILE_RELATIVE_PATH
_rule_failure_lines_spec = importlib.util.spec_from_file_location(
    "rule_enforcing_nc_test_suite_failure_message_closing_lines_text_common",
    REPO_ROOT / "nc-systems" / "general-tools"
    / "rule-enforcing-nc-test-suite-failure-message-closing-lines-text-common.py")
RULE_FAILURE_LINES = importlib.util.module_from_spec(_rule_failure_lines_spec)
_rule_failure_lines_spec.loader.exec_module(RULE_FAILURE_LINES)
# Every `<name>-something.md` and `<name>.md` the skill writes. The skill
# spells the stem `<name>`, which is what makes an ending findable in prose.
# The role itself may be several hyphenated words: the project's naming rule
# pushes new names that way, so `<name>-fast-read.md` has to read as one
# ending rather than not read at all (reviewer of PR 546, non-blocking; the
# first version stopped at a single word and refused a multi-part role as
# unnamed, which is the opposite of what this test promises).
SKILL_ENDING = re.compile(r"<name>(-[a-z]+(?:-[a-z]+)*)?\.md")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def load(script_name, directory="scripts"):
    """Import a script whose filename has hyphens, the project's convention."""
    path = REPO_ROOT / directory / script_name
    spec = importlib.util.spec_from_file_location(
        script_name.replace("-", "_").removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SKILL_DECIDES_THE_ENDINGS = (
    f"{SKILL_FILE_RELATIVE_PATH} does not name; the skill decides the endings of an "
    f"approval-walk's files.")
ASK_THE_USER_TO_CHANGE_THE_SKILL_FIRST = (
    f"If the new ending is meant to stay, the skill must name it first: ask the user to approve "
    f"that change to {SKILL_FILE_RELATIVE_PATH}, which the instruction-file guard protects.")


def too_few_skill_endings_failure_detail(suffixes):
    return "\n".join([
        f"found only {sorted(suffixes)} in {SKILL_FILE_RELATIVE_PATH}, which decides the endings "
        f"of an approval-walk's files; this suite reads them from names written as <name>.md and "
        f"<name>-<ending>.md, and needs at least four.",
        "If your change rewrote those names in the skill, write them again as <name>.md and "
        "<name>-<ending>.md.",
        RULE_FAILURE_LINES.guarded_file_fix_failure_message_line_pointing_to_approval_page_and_guard_refusal(SKILL_FILE_RELATIVE_PATH),
        RULE_FAILURE_LINES.FAILURE_MAY_COME_FROM_MAIN_NOT_YOUR_CHANGE_REPORT_IT_CLOSING_LINE])


def fast_read_ending_unnamed_failure_detail(constant_name, ending):
    return "\n".join([
        f"builds {ending!r}, which {SKILL_DECIDES_THE_ENDINGS}",
        f"If the new ending was not meant to change the skill, set {constant_name} in "
        f"nc-systems/cold-read/cold-read-fast-read.py back to the ending it had.",
        ASK_THE_USER_TO_CHANGE_THE_SKILL_FIRST,
        RULE_FAILURE_LINES.FAILURE_MAY_COME_FROM_MAIN_NOT_YOUR_CHANGE_REPORT_IT_CLOSING_LINE])


def shipper_role_unnamed_failure_detail(unnamed):
    return "\n".join([
        f"ships {unnamed}, which {SKILL_DECIDES_THE_ENDINGS}",
        "If the new or changed ending was not meant to change the skill, set that role in "
        "WALK_FILE_ROLES in nc-systems/skills/walk-me-through/walk-files-ship.py back to what it was, or remove a role your "
        "change added.",
        ASK_THE_USER_TO_CHANGE_THE_SKILL_FIRST,
        RULE_FAILURE_LINES.FAILURE_MAY_COME_FROM_MAIN_NOT_YOUR_CHANGE_REPORT_IT_CLOSING_LINE])


def suggestions_ending_disagrees_failure_detail(written, roles):
    return "\n".join([
        f"the fast read writes {written!r} but the shipper's roles are {roles}, so "
        f"nc-systems/skills/walk-me-through/walk-files-ship.py would not ship a walk's cold-read-fast-read report to the log-store.",
        "Set back whichever of the two your change altered: WALK_SUGGESTIONS_SUFFIX in "
        "nc-systems/cold-read/cold-read-fast-read.py, which ends in .md, or the cold-read-fast-read report role "
        "in WALK_FILE_ROLES in nc-systems/skills/walk-me-through/walk-files-ship.py, which does not; without its .md, the "
        "first must equal the second.",
        RULE_FAILURE_LINES.FAILURE_MAY_COME_FROM_MAIN_NOT_YOUR_CHANGE_REPORT_IT_CLOSING_LINE])


def skill_suffixes_in(skill_text):
    """Each role suffix the skill writes: "-draft", "" for the walk text itself."""
    return {match.group(1) or "" for match in SKILL_ENDING.finditer(skill_text)}


SKILL_NAMES_ENDINGS_CASE = "the skill names the walk files' endings"
SHIPPER_ROLES_NAMED_CASE = "every walk-files-ship.py role suffix is one the skill names"
FAST_READ_REPORT_SHIPPED_CASE = "the fast read's report ending is the shipper's cold-read-fast-read report role"


def fast_read_ending_named_case(constant_name):
    return f"cold-read-fast-read.py {constant_name} is an ending the skill names"


def walk_file_endings_cases(skill_text, fast_read_endings, walk_file_roles):
    """Every case holding the two programs' endings to the skill, as (case
    name, passed, detail) triples, given the skill's text, the fast read's
    (constant name, ending) pairs and the shipper's WALK_FILE_ROLES; a planted
    input prints the messages the real files would."""
    skill_suffixes = skill_suffixes_in(skill_text)
    cases = [(SKILL_NAMES_ENDINGS_CASE, len(skill_suffixes) >= 4,
              too_few_skill_endings_failure_detail(skill_suffixes))]
    for constant_name, ending in fast_read_endings:
        cases.append((fast_read_ending_named_case(constant_name),
                      ending.removesuffix(".md") in skill_suffixes,
                      fast_read_ending_unnamed_failure_detail(constant_name, ending)))
    unnamed = [suffix for suffix, _role in walk_file_roles if suffix not in skill_suffixes]
    cases.append((SHIPPER_ROLES_NAMED_CASE, not unnamed,
                  shipper_role_unnamed_failure_detail(unnamed)))
    # The two programs must also agree with each other, or a walk draft's
    # report lands where the shipper will not look for it.
    shipper_roles = [suffix for suffix, _role in walk_file_roles]
    written = dict(fast_read_endings)["WALK_SUGGESTIONS_SUFFIX"]
    cases.append((FAST_READ_REPORT_SHIPPED_CASE,
                  written.removesuffix(".md") in set(shipper_roles),
                  suggestions_ending_disagrees_failure_detail(written, shipper_roles)))
    return cases


def case_outcome(cases, case_name):
    return next((passed, detail) for name, passed, detail in cases if name == case_name)


fast_read = load("cold-read-fast-read.py", "nc-systems/cold-read")
shipper = load("walk-files-ship.py", "nc-systems/skills/walk-me-through")
for case_name, passed, detail in walk_file_endings_cases(
        SKILL_FILE.read_text(),
        [(constant_name, getattr(fast_read, constant_name))
         for constant_name in ("WALK_DRAFT_SUFFIX", "WALK_SUGGESTIONS_SUFFIX")],
        shipper.WALK_FILE_ROLES):
    check(case_name, passed, detail)

shipped_beyond_the_skill = [suffix for suffix, _role in shipper.APPROVAL_WALK_FILE_SUFFIX_AND_ROLE_PAIRS_SHIPPED_INCLUDING_EARLIER_WALKS_SUGGESTIONS_SUFFIX
                            if (suffix, _role) not in shipper.WALK_FILE_ROLES]
check("the shipper ships one ending beyond the skill's roles, an earlier walk's -suggestions report",
      shipped_beyond_the_skill == ["-suggestions"]
      == [shipper.APPROVAL_WALK_COLD_READ_FAST_READ_REPORT_FILE_SUFFIX_IN_WALKS_STARTED_BEFORE_ITS_RENAME],
      f"APPROVAL_WALK_FILE_SUFFIX_AND_ROLE_PAIRS_SHIPPED_INCLUDING_EARLIER_WALKS_SUGGESTIONS_SUFFIX in nc-systems/skills/walk-me-through/walk-files-ship.py adds {shipped_beyond_the_skill} "
      f"to WALK_FILE_ROLES; only '-suggestions', the ending of an earlier walk's report, may be "
      f"shipped without the skill naming it.\n"
      f"Put any other role in WALK_FILE_ROLES, where the checks above hold it to the skill.\n"
      + RULE_FAILURE_LINES.FAILURE_MAY_COME_FROM_MAIN_NOT_YOUR_CHANGE_REPORT_IT_CLOSING_LINE)

# Each failure above, made to print from a planted input rather than the real files.
PLANTED_SKILL_TEXT = "<name>-draft.md, <name>-cold-read-fast-read.md, <name>.md and <name>-minutes.md"
PLANTED_FAST_READ_ENDINGS = [("WALK_DRAFT_SUFFIX", "-draft.md"),
                             ("WALK_SUGGESTIONS_SUFFIX", "-cold-read-fast-read.md")]
PLANTED_WALK_FILE_ROLES = [("-draft", "draft"), ("-cold-read-fast-read", "report"),
                           ("", "walk"), ("-minutes", "minutes")]
check("the planted input passes every case, or the planted failures below prove nothing",
      all(passed for _name, passed, _detail in walk_file_endings_cases(
          PLANTED_SKILL_TEXT, PLANTED_FAST_READ_ENDINGS, PLANTED_WALK_FILE_ROLES)),
      walk_file_endings_cases(PLANTED_SKILL_TEXT, PLANTED_FAST_READ_ENDINGS, PLANTED_WALK_FILE_ROLES))

too_few_passed, too_few_detail = case_outcome(
    walk_file_endings_cases("", PLANTED_FAST_READ_ENDINGS, PLANTED_WALK_FILE_ROLES),
    SKILL_NAMES_ENDINGS_CASE)
check("too few endings in the skill fails with the rule, the fix, the guarded-file line and the "
      "line for a rule main broke",
      not too_few_passed and too_few_detail.split("\n") == [
          "found only [] in .claude/skills/walk-me-through/SKILL.md, which decides the endings of "
          "an approval-walk's files; this suite reads them from names written as <name>.md and "
          "<name>-<ending>.md, and needs at least four.",
          "If your change rewrote those names in the skill, write them again as <name>.md and "
          "<name>-<ending>.md.",
          RULE_FAILURE_LINES.guarded_file_fix_failure_message_line_pointing_to_approval_page_and_guard_refusal(".claude/skills/walk-me-through/SKILL.md"),
          RULE_FAILURE_LINES.FAILURE_MAY_COME_FROM_MAIN_NOT_YOUR_CHANGE_REPORT_IT_CLOSING_LINE],
      too_few_detail)

unnamed_ending_passed, unnamed_ending_detail = case_outcome(
    walk_file_endings_cases(
        PLANTED_SKILL_TEXT,
        [("WALK_DRAFT_SUFFIX", "-draft.md"), ("WALK_SUGGESTIONS_SUFFIX", "-review.md")],
        PLANTED_WALK_FILE_ROLES),
    fast_read_ending_named_case("WALK_SUGGESTIONS_SUFFIX"))
check("a fast-read ending the skill does not name fails with one fix per cause",
      not unnamed_ending_passed and unnamed_ending_detail.split("\n") == [
          "builds '-review.md', which .claude/skills/walk-me-through/SKILL.md does not name; the "
          "skill decides the endings of an approval-walk's files.",
          "If the new ending was not meant to change the skill, set WALK_SUGGESTIONS_SUFFIX in "
          "nc-systems/cold-read/cold-read-fast-read.py back to the ending it had.",
          "If the new ending is meant to stay, the skill must name it first: ask the user to "
          "approve that change to .claude/skills/walk-me-through/SKILL.md, which the "
          "instruction-file guard protects.",
          RULE_FAILURE_LINES.FAILURE_MAY_COME_FROM_MAIN_NOT_YOUR_CHANGE_REPORT_IT_CLOSING_LINE],
      unnamed_ending_detail)

unnamed_role_passed, unnamed_role_detail = case_outcome(
    walk_file_endings_cases(PLANTED_SKILL_TEXT, PLANTED_FAST_READ_ENDINGS,
                            PLANTED_WALK_FILE_ROLES + [("-notes", "notes")]),
    SHIPPER_ROLES_NAMED_CASE)
check("a shipper role the skill does not name fails with one fix per cause",
      not unnamed_role_passed and unnamed_role_detail.split("\n") == [
          "ships ['-notes'], which .claude/skills/walk-me-through/SKILL.md does not name; the "
          "skill decides the endings of an approval-walk's files.",
          "If the new or changed ending was not meant to change the skill, set that role in "
          "WALK_FILE_ROLES in nc-systems/skills/walk-me-through/walk-files-ship.py back to what it was, or remove a role "
          "your change added.",
          "If the new ending is meant to stay, the skill must name it first: ask the user to "
          "approve that change to .claude/skills/walk-me-through/SKILL.md, which the "
          "instruction-file guard protects.",
          RULE_FAILURE_LINES.FAILURE_MAY_COME_FROM_MAIN_NOT_YOUR_CHANGE_REPORT_IT_CLOSING_LINE],
      unnamed_role_detail)

unshipped_passed, unshipped_detail = case_outcome(
    walk_file_endings_cases(
        PLANTED_SKILL_TEXT + " <name>-suggestions.md <name>-suggestion.md",
        [("WALK_DRAFT_SUFFIX", "-draft.md"), ("WALK_SUGGESTIONS_SUFFIX", "-suggestions.md")],
        [("-draft", "draft"), ("-suggestion", "report"), ("", "walk")]),
    FAST_READ_REPORT_SHIPPED_CASE)
check("a suggestions ending the shipper does not ship fails saying what is lost and which to set back",
      not unshipped_passed and unshipped_detail.split("\n") == [
          "the fast read writes '-suggestions.md' but the shipper's roles are "
          "['-draft', '-suggestion', ''], so nc-systems/skills/walk-me-through/walk-files-ship.py would not ship a walk's "
          "cold-read-fast-read report to the log-store.",
          "Set back whichever of the two your change altered: WALK_SUGGESTIONS_SUFFIX in "
          "nc-systems/cold-read/cold-read-fast-read.py, which ends in .md, or the cold-read-fast-read report role "
          "in WALK_FILE_ROLES in nc-systems/skills/walk-me-through/walk-files-ship.py, which does not; without its .md, the "
          "first must equal the second.",
          RULE_FAILURE_LINES.FAILURE_MAY_COME_FROM_MAIN_NOT_YOUR_CHANGE_REPORT_IT_CLOSING_LINE],
      unshipped_detail)

print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
