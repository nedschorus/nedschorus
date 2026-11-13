#!/usr/bin/env python3
"""Tests for architecture-overview-path-template-and-checked-against-commit-reader-common.py.

Run: python3 scripts/architecture-overview-path-template-and-checked-against-commit-reader-common-test.py
"""

import importlib.util
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
PAGE_PATH = (REPOSITORY_ROOT / "docs" / "nedschorus-wiki"
             / "nedschorus-how-to-write-an-architecture-overview.md")

_spec = importlib.util.spec_from_file_location(
    "architecture_overview_path_template_and_checked_against_commit_reader", Path(__file__).with_name("architecture-overview-path-template-and-checked-against-commit-reader-common.py"))
architecture_overview_path_template_and_checked_against_commit_reader = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(architecture_overview_path_template_and_checked_against_commit_reader)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


FULL = "0123456789abcdef0123456789abcdef01234567"
OTHER = "fedcba9876543210fedcba9876543210fedcba98"
line = architecture_overview_path_template_and_checked_against_commit_reader.CHECKED_AGAINST_LINE_TEMPLATE.format(commit=FULL)
read = architecture_overview_path_template_and_checked_against_commit_reader.checked_against_commit

check("the line the template writes names its commit in the brackets and the link",
      line == f"**Checked against:** commit [{FULL}]"
              f"(https://github.com/nedschorus/nedschorus/commit/{FULL})", line)
check("an overview ending in the line gives its commit",
      read(f"# The widget\n\nIt widgets.\n\n{line}\n") == FULL)
check("blank lines after the last line do not hide it",
      read(f"# The widget\n\n{line}\n\n\n") == FULL)
check("an overview without the line gives None",
      read("# The widget\n\nIt widgets.\n") is None)
check("an empty file gives None", read("") is None)
check("the line counts only as the last line: a commit named earlier is not the one checked",
      read(f"# The widget\n\n{line}\n\nA paragraph written after it.\n") is None)
check("of two such lines, the last names the commit",
      read(f"# The widget\n\n{architecture_overview_path_template_and_checked_against_commit_reader.CHECKED_AGAINST_LINE_TEMPLATE.format(commit=OTHER)}"
           f"\n\n{line}\n") == FULL)
check("the line an overview had before the page does not count",
      read(f"# The widget\n\n**Pinned to what landed:** commit [{FULL[:7]}]"
           f"(https://github.com/nedschorus/nedschorus/commit/{FULL}) on 2026-09-28 — it.\n")
      is None)

# A tree with a hyphenated system holding a subsystem, a hyphenated subsystem, and a plain system.
directories = {"nc-systems/general-tools", "nc-systems/general-tools/scheduled",
               "nc-systems/skills", "nc-systems/skills/walk-me-through", "nc-systems/handoff"}
level = lambda path: architecture_overview_path_template_and_checked_against_commit_reader.architecture_overview_level_and_described_code_directory_from_path(
    path, directories.__contains__)
wiki = "docs/nedschorus-wiki/"
check("the project overview has no code directory of its own, and needs no nc-systems/project",
      level(wiki + "nedschorus-project-architecture-overview.md") == ("project", None))
check("a system's overview describes nc-systems/<system>",
      level(wiki + "nedschorus-handoff-architecture-overview.md") == ("system", "nc-systems/handoff"))
check("a hyphenated system's overview is read as the system, not as a subsystem",
      level(wiki + "nedschorus-general-tools-architecture-overview.md") == ("system", "nc-systems/general-tools"))
check("a subsystem's overview describes nc-systems/<system>/<subsystem>, the subsystem name holding hyphens",
      level(wiki + "nedschorus-skills-walk-me-through-architecture-overview.md")
      == ("subsystem", "nc-systems/skills/walk-me-through"))
check("a subsystem of a hyphenated system is found",
      level(wiki + "nedschorus-general-tools-scheduled-architecture-overview.md")
      == ("subsystem", "nc-systems/general-tools/scheduled"))
check("a name with no directory behind it is not an overview",
      level(wiki + "nedschorus-skills-gone-architecture-overview.md") is None)
check("the how-to page itself is not an overview",
      level(wiki + "nedschorus-how-to-write-an-architecture-overview.md") is None)
check("a proposed-improvements file beside an overview is not an overview",
      level(wiki + "nedschorus-handoff-architecture-overview-proposed-improvements-or-changes-x.md") is None)
check("a path elsewhere is not an overview",
      level("docs/nedschorus-handoff-architecture-overview.md") is None)

# The page is where the path and the line are defined; this module must say the same.
page = PAGE_PATH.read_text(encoding="utf-8")
check("the page names the overview path this module builds",
      architecture_overview_path_template_and_checked_against_commit_reader.SYSTEM_ARCHITECTURE_OVERVIEW_PATH_TEMPLATE.replace("{system}", "<system>") in page,
      architecture_overview_path_template_and_checked_against_commit_reader.SYSTEM_ARCHITECTURE_OVERVIEW_PATH_TEMPLATE)
check("the page names the project overview's path",
      architecture_overview_path_template_and_checked_against_commit_reader.PROJECT_ARCHITECTURE_OVERVIEW_PATH in page,
      architecture_overview_path_template_and_checked_against_commit_reader.PROJECT_ARCHITECTURE_OVERVIEW_PATH)
check("the page names the subsystem overview path this module builds",
      architecture_overview_path_template_and_checked_against_commit_reader.SUBSYSTEM_ARCHITECTURE_OVERVIEW_PATH_TEMPLATE.replace(
          "{system}", "<system>").replace("{subsystem}", "<subsystem>") in page,
      architecture_overview_path_template_and_checked_against_commit_reader.SUBSYSTEM_ARCHITECTURE_OVERVIEW_PATH_TEMPLATE)
check("the page spells the last line this module reads",
      architecture_overview_path_template_and_checked_against_commit_reader.CHECKED_AGAINST_LINE_TEMPLATE.replace(
          "{commit}", "<full commit id>") in page,
      architecture_overview_path_template_and_checked_against_commit_reader.CHECKED_AGAINST_LINE_TEMPLATE)

if failures:
    print(f"\n{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("\nall cases passed")
