#!/usr/bin/env python3
"""Tests for tool-design-write-design-document-next-step-print.py: each step it can print, and each way it exits 2,
is caused here at least once.

Every case writes its design and its repository files under a temporary directory.
Run: python3 nn-systems/skills/tool-design-write/tests/tool-design-write-design-document-next-step-print-test.py
Prints one line per case and exits 0 if every case passes, 1 if one fails."""

import contextlib
import importlib.util
import io
import subprocess
import sys
import tempfile
from pathlib import Path

TESTS = Path(__file__).resolve().parent
NEXT_STEP = TESTS.parent / "tool-design-write-design-document-next-step-print.py"


def load(path, name):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


next_step = load(NEXT_STEP, "tool_design_write_next_step")
# The form checker's own test holds a complete design; reusing it keeps the two tests on one design.
checker_test = load(TESTS / "tool-design-write-required-sections-judgment-steps-and-named-files-exist-check-test.py",
                    "tool_design_write_check_test")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run(root, design, *extra_arguments):
    completed = subprocess.run(
        [sys.executable, str(NEXT_STEP), str(design), "--repository-root", str(root), *extra_arguments],
        capture_output=True, text=True)
    return completed.returncode, completed.stdout, completed.stderr


def main():
    with tempfile.TemporaryDirectory() as scratch_name:
        scratch = Path(scratch_name)

        root = checker_test.fresh_repository(scratch, "unwritten")
        code, out, err = run(root, root / "docs" / "widget-counter-design.md")
        check("design not yet written: exit 1, the step is to write it",
              code == 1 and "Next step: write the design" in out, f"{code} {out!r} {err!r}")

        root = checker_test.fresh_repository(scratch, "findings")
        design = root / "design.md"
        design.write_text(checker_test.COMPLETE_DESIGN.replace("## Tests\n", "## Not Tests\n"))
        code, out, err = run(root, design)
        check("form check finds something: exit 1, the step is to fix the findings it prints",
              code == 1 and "Next step: fix each finding" in out and 'section "Tests" is missing' in out,
              f"{code} {out!r} {err!r}")

        root = checker_test.fresh_repository(scratch, "complete")
        design = root / "design.md"
        design.write_text(checker_test.COMPLETE_DESIGN)
        code, out, err = run(root, design)
        check("form complete: exit 0, the hand-off to walk-me-through and the cold-read skill",
              code == 0 and "walk-me-through" in out and "cold-read skill" in out, f"{code} {out!r} {err!r}")

        root = checker_test.fresh_repository(scratch, "unreadable")
        design = root / "design.md"
        design.write_bytes(b"\xff\xfe## Problem\n")
        code, out, err = run(root, design)
        check("design the form check cannot read: exit 2, its reason printed",
              code == 2 and "is not UTF-8" in err, f"{code} {err!r}")

        code, out, err = run(root, design, "--repository-root", str(root / "absent"))
        check("--repository-root that is not a directory: exit 2", code == 2 and "is not a directory" in err,
              f"{code} {err!r}")

        completed = subprocess.run([sys.executable, str(NEXT_STEP), "--help"], capture_output=True, text=True)
        check("--help states the exit codes", completed.returncode == 0 and "Exits 0" in completed.stdout,
              f"{completed.returncode} {completed.stdout!r}")

        # A crash inside the form check cannot be caused through the command line, so it is injected.
        root = checker_test.fresh_repository(scratch, "crash")
        design = root / "design.md"
        design.write_text(checker_test.COMPLETE_DESIGN)
        real_loader = next_step.load_form_checker

        def crashing_loader():
            raise RuntimeError("injected crash")

        next_step.load_form_checker = crashing_loader
        error_output = io.StringIO()
        try:
            with contextlib.redirect_stderr(error_output), contextlib.redirect_stdout(io.StringIO()):
                code = next_step.main([str(design), "--repository-root", str(root)])
        finally:
            next_step.load_form_checker = real_loader
        check("a crash: exit 2, cause printed",
              code == 2 and "crashed with RuntimeError: injected crash" in error_output.getvalue(),
              f"{code} {error_output.getvalue()!r}")

    print(f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
