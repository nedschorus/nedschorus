#!/usr/bin/env python3
"""Is the design written and its form complete, so that only the approval-walk and the cold-read remain?

Usage:
  tool-design-write-design-document-next-step-print.py DESIGN [--repository-root DIR]

The /tool-design-write skill's agent runs this program with its design's path,
does the one step it prints, and runs it again, until it exits 0. The step is
decided from the design file and from
tool-design-write-required-sections-judgment-steps-and-named-files-exist-check.py,
first match wins:
  - DESIGN does not exist: write it;
  - the form check finds something: fix each finding it prints;
  - the form is complete: hand the design to the walk-me-through skill, for the
    decisions only the user can make, and then to the cold-read skill, which
    keep their own order and records.

Exits 0 if the form is complete and the hand-off is printed, 1 if a step of
this skill remains and is printed, 2 if it could not tell (bad invocation, an
unreadable design, or a crash)."""

import argparse
import importlib.util
import sys
from pathlib import Path

PROGRAM = "tool-design-write-design-document-next-step-print"
FORM_CHECKER = (Path(__file__).resolve().parent
                / "tool-design-write-required-sections-judgment-steps-and-named-files-exist-check.py")

EXIT_FORM_COMPLETE = 0
EXIT_STEP_REMAINS = 1
EXIT_COULD_NOT_TELL = 2


def load_form_checker():
    specification = importlib.util.spec_from_file_location("tool_design_write_form_checker", FORM_CHECKER)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def write_step(design):
    return (f"Next step: write the design at {design}, as the section \"How to write the design\" of "
            ".claude/skills/tool-design-write/SKILL.md says; read the code it builds on first.\n"
            "Then run this program again.")


def fix_step(design, findings):
    lines = [f"Next step: fix each finding the form check made in {design}:"]
    for line_number, problem in findings:
        lines.append(f"{design}:{line_number}: {problem}" if line_number else f"{design}: {problem}")
    lines.append("Then run this program again.")
    return "\n".join(lines)


def hand_off_step(design):
    return (f"The form of {design} is complete; the steps of tool-design-write are done.\n"
            "When the design leaves a decision only the user can make, such as a `needs-human-decision` honest exit: "
            "put each such decision to him as one approval-walk item, with your recommendation, through the "
            "walk-me-through skill, and write his answer into the design. Settle every other open decision yourself "
            "and write it into the design.\n"
            "Then give the design the review the cold-read skill requires.\n"
            "After any change to the design, run this program again, so its form is checked again.")


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description=__doc__.splitlines()[0],
        epilog="Exits 0 if the form is complete and the hand-off is printed, 1 if a step of this skill remains "
               "and is printed, 2 if it could not tell.")
    parser.add_argument("design", type=Path, help="the design's Markdown file, written or still to be written")
    parser.add_argument("--repository-root", type=Path, default=None,
                        help="the checkout whose files the design names (default: this program's checkout)")
    arguments = parser.parse_args(argv)
    if arguments.repository_root is not None and not arguments.repository_root.is_dir():
        parser.error(f"--repository-root {arguments.repository_root} is not a directory")
    return arguments


def main(argv=None) -> int:
    arguments = parse_arguments(argv)
    if not arguments.design.exists():
        print(write_step(arguments.design))
        return EXIT_STEP_REMAINS
    form_checker = None
    try:
        form_checker = load_form_checker()
        repository_root = (arguments.repository_root or form_checker.REPOSITORY_ROOT).resolve()
        findings = form_checker.check_design(arguments.design, repository_root, form_checker.load_md_drift_lint())
    except Exception as error:
        if form_checker is not None and isinstance(error, form_checker.CouldNotCheck):
            cause = str(error)
        else:
            cause = f"crashed with {type(error).__name__}: {error}"
        print(f"{PROGRAM}: could not tell the next step for {arguments.design}: {cause}", file=sys.stderr)
        return EXIT_COULD_NOT_TELL
    if findings:
        print(fix_step(arguments.design, findings))
        return EXIT_STEP_REMAINS
    print(hand_off_step(arguments.design))
    return EXIT_FORM_COMPLETE


if __name__ == "__main__":
    sys.exit(main())
