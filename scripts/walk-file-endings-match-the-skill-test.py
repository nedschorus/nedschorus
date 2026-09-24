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
SKILL_FILE = REPO_ROOT / ".claude" / "skills" / "walk-me-through" / "SKILL.md"
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


skill_text = SKILL_FILE.read_text()
# A role suffix as the skill writes it: "-draft", "" for the walk text itself.
skill_suffixes = {match.group(1) or "" for match in SKILL_ENDING.finditer(skill_text)}
check("the skill names the walk files' endings",
      len(skill_suffixes) >= 4,
      f"found only {sorted(skill_suffixes)} in {SKILL_FILE.name}; the pattern "
      f"this test reads is <name>-<role>.md")

fast_read = load("cold-read-fast-read.py", "nc-systems/cold-read")
for constant_name in ("WALK_DRAFT_SUFFIX", "WALK_SUGGESTIONS_SUFFIX"):
    ending = getattr(fast_read, constant_name)
    check(f"cold-read-fast-read.py {constant_name} is an ending the skill names",
          ending.removesuffix(".md") in skill_suffixes,
          f"builds {ending!r}, which {SKILL_FILE.name} does not name; the "
          f"skill decides the endings, so change the skill first or follow it")

shipper = load("walk-files-ship.py")
unnamed = [suffix for suffix, _role in shipper.WALK_FILE_ROLES
           if suffix not in skill_suffixes]
check("every walk-files-ship.py role suffix is one the skill names",
      not unnamed,
      f"ships {unnamed}, which {SKILL_FILE.name} does not name")

# The two programs must also agree with each other, or a walk draft's
# suggestions file lands where the shipper will not look for it.
check("the fast read's suggestions ending is the shipper's suggestions role",
      fast_read.WALK_SUGGESTIONS_SUFFIX.removesuffix(".md")
      in {suffix for suffix, _role in shipper.WALK_FILE_ROLES},
      f"the fast read writes {fast_read.WALK_SUGGESTIONS_SUFFIX!r} but the "
      f"shipper's roles are "
      f"{[suffix for suffix, _role in shipper.WALK_FILE_ROLES]}")

print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
