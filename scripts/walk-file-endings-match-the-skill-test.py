#!/usr/bin/env python3
"""The walk-me-through skill names the walk files' endings, and this test
keeps the two programs that build those names agreeing with it.

A walk's files are `<name>-draft.md`, `<name>-suggestions.md`, `<name>.md`,
`<name>-minutes.md` and, for a walk on a cold-read-full-run,
`<name>-dispositions.md`. `.claude/skills/walk-me-through/SKILL.md` is where
that list is decided, and two programs carry a copy in code:
nc-systems/cold-read/cold-read-fast-read.py, which puts a walk draft's report beside it as
the suggestions file, and scripts/walk-files-ship.py, which ships all five to
the log-store.

Prose cannot import a constant, so the skill cannot be the single definition
the way a module can. The tie-break is this test instead: the skill's text
governs, and a program whose ending is not in that text fails here (user-ruled
2026-09-19, walk file-naming-and-location-standards-cold-read-findings, item
4). It is deliberately one-directional -- the skill may name an ending no
program builds yet, but no program may build one the skill does not name.

Run: python3 scripts/walk-file-endings-match-the-skill-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
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
        "WALK_FILE_ROLES in scripts/walk-files-ship.py back to what it was, or remove a role your "
        "change added.",
        ASK_THE_USER_TO_CHANGE_THE_SKILL_FIRST,
        RULE_FAILURE_LINES.FAILURE_MAY_COME_FROM_MAIN_NOT_YOUR_CHANGE_REPORT_IT_CLOSING_LINE])


def suggestions_ending_disagrees_failure_detail(written, roles):
    return "\n".join([
        f"the fast read writes {written!r} but the shipper's roles are {roles}, so "
        f"scripts/walk-files-ship.py would not ship a walk's suggestions file to the log-store.",
        "Set back whichever of the two your change altered: WALK_SUGGESTIONS_SUFFIX in "
        "nc-systems/cold-read/cold-read-fast-read.py, which ends in .md, or the suggestions role "
        "in WALK_FILE_ROLES in scripts/walk-files-ship.py, which does not; without its .md, the "
        "first must equal the second.",
        RULE_FAILURE_LINES.FAILURE_MAY_COME_FROM_MAIN_NOT_YOUR_CHANGE_REPORT_IT_CLOSING_LINE])


skill_text = SKILL_FILE.read_text()
# A role suffix as the skill writes it: "-draft", "" for the walk text itself.
skill_suffixes = {match.group(1) or "" for match in SKILL_ENDING.finditer(skill_text)}
check("the skill names the walk files' endings",
      len(skill_suffixes) >= 4, too_few_skill_endings_failure_detail(skill_suffixes))

fast_read = load("cold-read-fast-read.py", "nc-systems/cold-read")
for constant_name in ("WALK_DRAFT_SUFFIX", "WALK_SUGGESTIONS_SUFFIX"):
    ending = getattr(fast_read, constant_name)
    check(f"cold-read-fast-read.py {constant_name} is an ending the skill names",
          ending.removesuffix(".md") in skill_suffixes,
          fast_read_ending_unnamed_failure_detail(constant_name, ending))

shipper = load("walk-files-ship.py")
unnamed = [suffix for suffix, _role in shipper.WALK_FILE_ROLES
           if suffix not in skill_suffixes]
check("every walk-files-ship.py role suffix is one the skill names",
      not unnamed, shipper_role_unnamed_failure_detail(unnamed))

# The two programs must also agree with each other, or a walk draft's
# suggestions file lands where the shipper will not look for it.
shipper_roles = [suffix for suffix, _role in shipper.WALK_FILE_ROLES]
check("the fast read's suggestions ending is the shipper's suggestions role",
      fast_read.WALK_SUGGESTIONS_SUFFIX.removesuffix(".md") in set(shipper_roles),
      suggestions_ending_disagrees_failure_detail(fast_read.WALK_SUGGESTIONS_SUFFIX, shipper_roles))

# Each failure above, made to print from a planted input rather than the real files.
check("too few endings in the skill fails with the rule, the fix, the guarded-file line and the "
      "line for a rule main broke",
      too_few_skill_endings_failure_detail(set()).split("\n") == [
          "found only [] in .claude/skills/walk-me-through/SKILL.md, which decides the endings of "
          "an approval-walk's files; this suite reads them from names written as <name>.md and "
          "<name>-<ending>.md, and needs at least four.",
          "If your change rewrote those names in the skill, write them again as <name>.md and "
          "<name>-<ending>.md.",
          RULE_FAILURE_LINES.guarded_file_fix_failure_message_line_pointing_to_approval_page_and_guard_refusal(".claude/skills/walk-me-through/SKILL.md"),
          RULE_FAILURE_LINES.FAILURE_MAY_COME_FROM_MAIN_NOT_YOUR_CHANGE_REPORT_IT_CLOSING_LINE],
      too_few_skill_endings_failure_detail(set()))
check("a fast-read ending the skill does not name fails with one fix per cause",
      fast_read_ending_unnamed_failure_detail("WALK_SUGGESTIONS_SUFFIX", "-review.md").split("\n") == [
          "builds '-review.md', which .claude/skills/walk-me-through/SKILL.md does not name; the "
          "skill decides the endings of an approval-walk's files.",
          "If the new ending was not meant to change the skill, set WALK_SUGGESTIONS_SUFFIX in "
          "nc-systems/cold-read/cold-read-fast-read.py back to the ending it had.",
          "If the new ending is meant to stay, the skill must name it first: ask the user to "
          "approve that change to .claude/skills/walk-me-through/SKILL.md, which the "
          "instruction-file guard protects.",
          RULE_FAILURE_LINES.FAILURE_MAY_COME_FROM_MAIN_NOT_YOUR_CHANGE_REPORT_IT_CLOSING_LINE],
      fast_read_ending_unnamed_failure_detail("WALK_SUGGESTIONS_SUFFIX", "-review.md"))
check("a shipper role the skill does not name fails with one fix per cause",
      shipper_role_unnamed_failure_detail(["-notes"]).split("\n") == [
          "ships ['-notes'], which .claude/skills/walk-me-through/SKILL.md does not name; the "
          "skill decides the endings of an approval-walk's files.",
          "If the new or changed ending was not meant to change the skill, set that role in "
          "WALK_FILE_ROLES in scripts/walk-files-ship.py back to what it was, or remove a role "
          "your change added.",
          "If the new ending is meant to stay, the skill must name it first: ask the user to "
          "approve that change to .claude/skills/walk-me-through/SKILL.md, which the "
          "instruction-file guard protects.",
          RULE_FAILURE_LINES.FAILURE_MAY_COME_FROM_MAIN_NOT_YOUR_CHANGE_REPORT_IT_CLOSING_LINE],
      shipper_role_unnamed_failure_detail(["-notes"]))
check("a suggestions ending the shipper does not ship fails saying what is lost and which to set back",
      suggestions_ending_disagrees_failure_detail(
          "-suggestions.md", ["-draft", "-suggestion", ""]).split("\n") == [
          "the fast read writes '-suggestions.md' but the shipper's roles are "
          "['-draft', '-suggestion', ''], so scripts/walk-files-ship.py would not ship a walk's "
          "suggestions file to the log-store.",
          "Set back whichever of the two your change altered: WALK_SUGGESTIONS_SUFFIX in "
          "nc-systems/cold-read/cold-read-fast-read.py, which ends in .md, or the suggestions role "
          "in WALK_FILE_ROLES in scripts/walk-files-ship.py, which does not; without its .md, the "
          "first must equal the second.",
          RULE_FAILURE_LINES.FAILURE_MAY_COME_FROM_MAIN_NOT_YOUR_CHANGE_REPORT_IT_CLOSING_LINE],
      suggestions_ending_disagrees_failure_detail("-suggestions.md", ["-draft", "-suggestion", ""]))

print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
