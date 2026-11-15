#!/usr/bin/env python3
"""Is a tool design's form complete: every required section, at least one judgment step, and every named file existing or marked #created_by_the_build?

Usage:
  tool-design-write-required-sections-judgment-steps-and-named-files-exist-check.py DESIGN [--repository-root DIR]

Checks one design written with the /tool-design-write skill:
  - each heading in REQUIRED_SECTION_HEADINGS is present, at any level from ##
    down, outside fenced code blocks;
  - the section "The judgment steps" holds at least one list item;
  - each item of the section "Files" starts with a backticked repository path;
    an item carrying #created_by_the_build names a file that does not exist yet, and an
    item without it names a file that does;
  - each backticked repository path in the design exists, or is the path of a
    #created_by_the_build item of "Files". Which backticked text counts as a path, and
    which lines are skipped, is scripts/md-drift-lint.py's rule, so a design
    this program passes has no "path does not exist" finding from that lint
    other than its #created_by_the_build paths.

Prints one finding per line, "<design>:<line>: <problem>" or "<design>: <problem>",
each with what to do, then one summary line.
Exits 0 if the form is complete, 1 if a finding is printed, 2 if the design could
not be checked (bad invocation, a missing or unreadable file, or a crash)."""

import argparse
import importlib.util
import re
import sys
from pathlib import Path

PROGRAM = "tool-design-write-required-sections-judgment-steps-and-named-files-exist-check"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MD_DRIFT_LINT = REPOSITORY_ROOT / "scripts" / "md-drift-lint.py"

EXIT_FORM_COMPLETE = 0
EXIT_FINDINGS = 1
EXIT_COULD_NOT_CHECK = 2

JUDGMENT_STEPS_HEADING = "The judgment steps"
FILES_HEADING = "Files"
CREATED_BY_THE_BUILD_HASHTAG = "#created_by_the_build"
REQUIRED_SECTION_HEADINGS = (
    "Problem",
    "Goals and non-goals",
    "What exists today",
    "The design",
    JUDGMENT_STEPS_HEADING,
    "Failure behaviour",
    "Alternatives considered",
    "Tests",
    FILES_HEADING,
    "Deferred-decisions",
)

HEADING = re.compile(r"^(#{2,6})\s+(.*?)\s*#*\s*$")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\S")
FIRST_BACKTICK_SPAN = re.compile(r"`([^`\n]+)`")
LINT_MISSING_PATH_PREFIX = "path does not exist: "


class CouldNotCheck(Exception):
    """The design cannot be checked; the message says why and what to do."""


def load_md_drift_lint():
    specification = importlib.util.spec_from_file_location("md_drift_lint", MD_DRIFT_LINT)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def read_design_lines(design: Path) -> list:
    try:
        return design.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        raise CouldNotCheck(f"{design} does not exist; pass the path of the design to check")
    except UnicodeDecodeError as error:
        raise CouldNotCheck(f"{design} is not UTF-8 text ({error}); a design is a Markdown file")
    except OSError as error:
        raise CouldNotCheck(f"{design} could not be read ({error})")


def sections(numbered_lines):
    """Return {heading text: [(line number, line), ...]} for each heading, the
    lines running to the next heading of the same or a higher level."""
    found = {}
    open_sections = []
    for line_number, line in numbered_lines:
        heading = HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            open_sections = [(open_level, name) for open_level, name in open_sections
                             if open_level < level]
            name = heading.group(2)
            found.setdefault(name, [(line_number, line)])
            open_sections.append((level, name))
            continue
        for _, name in open_sections:
            found[name].append((line_number, line))
    return found


def list_items(section_lines):
    return [(line_number, line) for line_number, line in section_lines[1:]
            if LIST_ITEM.match(line)]


def files_section_findings(files_lines, design, repository_root, lint):
    """Return the findings on the Files items, and the paths they mark #created_by_the_build."""
    created_by_the_build_paths = set()
    findings = []
    for line_number, line in list_items(files_lines):
        span = FIRST_BACKTICK_SPAN.search(line)
        if span is None:
            findings.append((line_number, "this Files item names no file; start the item with the "
                             "file's repository path in backticks"))
            continue
        path = lint.without_line_suffix(span.group(1).strip()).lstrip("/")
        exists = lint.resolve(path, design, repository_root) is not None
        if CREATED_BY_THE_BUILD_HASHTAG in line:
            created_by_the_build_paths.add(path)
            if exists:
                findings.append((line_number, f"{path} is marked {CREATED_BY_THE_BUILD_HASHTAG} but already exists; "
                                 f"remove {CREATED_BY_THE_BUILD_HASHTAG} when the build changes that file, or name the "
                                 "new file the build creates"))
        elif not exists:
            findings.append((line_number, f"{path} does not exist; add {CREATED_BY_THE_BUILD_HASHTAG} to this item "
                             "when the build creates it, otherwise correct the path"))
    return findings, created_by_the_build_paths


def check_design(design: Path, repository_root: Path, lint) -> list:
    """Return the findings, each a (line number or None, problem)."""
    lines = read_design_lines(design)
    numbered_lines = list(lint.lines_outside_fenced_code_blocks(lines))
    found_sections = sections(numbered_lines)
    findings = []
    for heading in REQUIRED_SECTION_HEADINGS:
        if heading not in found_sections:
            findings.append((None, f'section "{heading}" is missing; add a heading "{heading}" '
                             "at any level from ## down, written as .claude/skills/tool-design-write/SKILL.md says"))
    if JUDGMENT_STEPS_HEADING in found_sections:
        judgment_lines = found_sections[JUDGMENT_STEPS_HEADING]
        if not list_items(judgment_lines):
            findings.append((judgment_lines[0][0], f'section "{JUDGMENT_STEPS_HEADING}" lists no step; '
                             "list each step that needs judgment as a list item"))
    created_by_the_build_paths = set()
    if FILES_HEADING in found_sections:
        files_findings, created_by_the_build_paths = files_section_findings(
            found_sections[FILES_HEADING], design, repository_root, lint)
        findings.extend(files_findings)
    skipped_markers = lint.HISTORY_MARKERS + lint.FOREIGN_ROOT_MARKERS
    for line_number, line in numbered_lines:
        if any(marker in line for marker in skipped_markers):
            continue
        for problem in lint.check_backtick_paths(line, design, repository_root):
            if not problem.startswith(LINT_MISSING_PATH_PREFIX):
                continue
            word = problem[len(LINT_MISSING_PATH_PREFIX):]
            if lint.without_line_suffix(word).lstrip("/") in created_by_the_build_paths:
                continue
            findings.append((line_number, f"{word} does not exist; list it in the Files section with "
                             f"{CREATED_BY_THE_BUILD_HASHTAG} when the build creates it, otherwise correct the path"))
    return sorted(set(findings), key=lambda finding: (finding[0] or 0, finding[1]))


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description=__doc__.splitlines()[0],
        epilog="Required section headings: " + "; ".join(REQUIRED_SECTION_HEADINGS) + ". "
               "Exits 0 if the form is complete, 1 if a finding is printed, "
               "2 if the design could not be checked.")
    parser.add_argument("design", type=Path, help="the design's Markdown file")
    parser.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT,
                        help="the checkout whose files the design names (default: this program's checkout)")
    arguments = parser.parse_args(argv)
    if not arguments.repository_root.is_dir():
        parser.error(f"--repository-root {arguments.repository_root} is not a directory")
    return arguments


def main(argv=None) -> int:
    arguments = parse_arguments(argv)
    try:
        lint = load_md_drift_lint()
        findings = check_design(arguments.design, arguments.repository_root.resolve(), lint)
    except CouldNotCheck as error:
        print(f"{PROGRAM}: could not check: {error}", file=sys.stderr)
        return EXIT_COULD_NOT_CHECK
    except Exception as error:
        print(f"{PROGRAM}: could not check {arguments.design}: crashed with "
              f"{type(error).__name__}: {error}", file=sys.stderr)
        return EXIT_COULD_NOT_CHECK
    for line_number, problem in findings:
        where = f"{arguments.design}:{line_number}" if line_number else f"{arguments.design}"
        print(f"{where}: {problem}")
    if findings:
        print(f"{PROGRAM}: {len(findings)} finding(s); fix each, then run this program again")
        return EXIT_FINDINGS
    print(f"{PROGRAM}: the form of {arguments.design} is complete")
    return EXIT_FORM_COMPLETE


if __name__ == "__main__":
    sys.exit(main())
