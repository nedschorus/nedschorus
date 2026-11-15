#!/usr/bin/env python3
"""Tests for tool-design-write-required-sections-judgment-steps-and-named-files-exist-check.py:
each finding it reports and each way it exits 2 is caused here at least once.

Every case writes its design and its repository files under a temporary directory.
Run: python3 nc-systems/skills/tool-design-write/tests/tool-design-write-required-sections-judgment-steps-and-named-files-exist-check-test.py
Prints one line per case and exits 0 if every case passes, 1 if one fails."""

import contextlib
import importlib.util
import io
import subprocess
import sys
import tempfile
from pathlib import Path

CHECKER = (Path(__file__).resolve().parent.parent
           / "tool-design-write-required-sections-judgment-steps-and-named-files-exist-check.py")

_specification = importlib.util.spec_from_file_location("tool_design_write_check", CHECKER)
checker = importlib.util.module_from_spec(_specification)
_specification.loader.exec_module(checker)

COMPLETE_DESIGN = """---
kind: design
---
# A widget counter

## Problem

Counting widgets by hand loses counts.

## Goals and non-goals

- Count widgets.

## What exists today

`scripts/widget-list.py` lists widgets.

## The design

`scripts/widget-counter.py` reads the list and prints the count.

### The judgment steps

1. Deciding whether an odd widget counts, by a fresh-agent.

## Failure behaviour

A missing list exits 2.

## Alternatives considered

Counting by hand.

## Tests

`scripts/widget-counter-test.py` causes each failure.

## Files

- `scripts/widget-counter.py` #created_by_the_build
- `scripts/widget-counter-test.py` #created_by_the_build
- `scripts/widget-list.py`, gains a `--count` flag.

## Deferred-decisions

None.

```
## Problem
`scripts/not-a-real-file.py` inside a fence is not checked.
```
"""

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def fresh_repository(scratch: Path, name: str) -> Path:
    root = scratch / name
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "widget-list.py").write_text("print('widgets')\n")
    return root


def run_checker(root: Path, design_text=None, design_bytes=None, extra_arguments=()):
    design = root / "docs" / "widget-counter-design.md"
    design.parent.mkdir(parents=True, exist_ok=True)
    if design_bytes is not None:
        design.write_bytes(design_bytes)
    elif design_text is not None:
        design.write_text(design_text)
    completed = subprocess.run(
        [sys.executable, str(CHECKER), str(design), "--repository-root", str(root), *extra_arguments],
        capture_output=True, text=True)
    return completed.returncode, completed.stdout, completed.stderr


def main():
    with tempfile.TemporaryDirectory() as scratch_name:
        scratch = Path(scratch_name)

        code, out, err = run_checker(fresh_repository(scratch, "complete"), COMPLETE_DESIGN)
        check("complete design, with a judgment step under ###, #created_by_the_build paths and a fenced block: exit 0",
              code == 0 and "is complete" in out, f"{code} {out!r} {err!r}")

        for heading in checker.REQUIRED_SECTION_HEADINGS:
            marker = "#### " if heading == checker.JUDGMENT_STEPS_HEADING else "## "
            text = COMPLETE_DESIGN.replace(f"{'### ' if heading == checker.JUDGMENT_STEPS_HEADING else '## '}{heading}\n",
                                           f"{marker}Not {heading}\n", 1)
            code, out, err = run_checker(fresh_repository(scratch, f"missing-{len(heading)}-{heading[:4]}"), text)
            check(f'missing section "{heading}": exit 1, named',
                  code == 1 and f'section "{heading}" is missing' in out, f"{code} {out!r} {err!r}")

        text = COMPLETE_DESIGN.replace("1. Deciding whether an odd widget counts, by a fresh-agent.\n",
                                       "Each step is code.\n")
        code, out, err = run_checker(fresh_repository(scratch, "no-judgment-step"), text)
        check("judgment steps section with no list item: exit 1",
              code == 1 and 'section "The judgment steps" lists no step' in out, f"{code} {out!r} {err!r}")

        text = COMPLETE_DESIGN.replace("- `scripts/widget-counter-test.py` #created_by_the_build\n", "")
        code, out, err = run_checker(fresh_repository(scratch, "unmarked-new-path"), text)
        check("a named path that does not exist and is not a #created_by_the_build item: exit 1",
              code == 1 and "scripts/widget-counter-test.py does not exist; list it in the Files section" in out,
              f"{code} {out!r} {err!r}")

        text = COMPLETE_DESIGN.replace("- `scripts/widget-list.py`, gains", "- `scripts/widget-list.py` #created_by_the_build, gains")
        code, out, err = run_checker(fresh_repository(scratch, "new-file-exists"), text)
        check("a #created_by_the_build item whose file exists: exit 1",
              code == 1 and "scripts/widget-list.py is marked #created_by_the_build but already exists" in out,
              f"{code} {out!r} {err!r}")

        text = COMPLETE_DESIGN.replace("- `scripts/widget-list.py`, gains", "- `scripts/widget-lister.py`, gains")
        code, out, err = run_checker(fresh_repository(scratch, "files-item-missing"), text)
        check("a Files item without #created_by_the_build whose file does not exist: exit 1",
              code == 1 and "scripts/widget-lister.py does not exist; add #created_by_the_build to this item" in out,
              f"{code} {out!r} {err!r}")

        text = COMPLETE_DESIGN.replace("## Deferred-decisions", "- the widget store\n\n## Deferred-decisions")
        code, out, err = run_checker(fresh_repository(scratch, "files-item-no-path"), text)
        check("a Files item that names no file: exit 1",
              code == 1 and "this Files item names no file" in out, f"{code} {out!r} {err!r}")

        root = fresh_repository(scratch, "missing-design")
        completed = subprocess.run(
            [sys.executable, str(CHECKER), str(root / "no-such-design.md"), "--repository-root", str(root)],
            capture_output=True, text=True)
        check("missing design file: exit 2",
              completed.returncode == 2 and "does not exist" in completed.stderr,
              f"{completed.returncode} {completed.stderr!r}")

        code, out, err = run_checker(fresh_repository(scratch, "undecodable"), design_bytes=b"\xff\xfe## Problem\n")
        check("design that is not UTF-8: exit 2", code == 2 and "is not UTF-8" in err, f"{code} {err!r}")

        directory_design = fresh_repository(scratch, "directory-design")
        (directory_design / "docs" / "widget-counter-design.md").mkdir(parents=True)
        code, out, err = run_checker(directory_design)
        check("design path that cannot be read: exit 2", code == 2 and "could not be read" in err, f"{code} {err!r}")

        root = fresh_repository(scratch, "bad-root")
        code, out, err = run_checker(root, COMPLETE_DESIGN, extra_arguments=("--repository-root", str(root / "absent")))
        check("--repository-root that is not a directory: exit 2",
              code == 2 and "is not a directory" in err, f"{code} {err!r}")

        completed = subprocess.run([sys.executable, str(CHECKER)], capture_output=True, text=True)
        check("no design named: exit 2", completed.returncode == 2 and "usage:" in completed.stderr,
              f"{completed.returncode} {completed.stderr!r}")

        completed = subprocess.run([sys.executable, str(CHECKER), "--help"], capture_output=True, text=True)
        check("--help states the required headings and the exit codes",
              completed.returncode == 0 and "Exits 0" in completed.stdout
              and "Alternatives considered" in completed.stdout,
              f"{completed.returncode} {completed.stdout!r}")

        # A crash inside the check cannot be caused through the command line, so it is injected.
        root = fresh_repository(scratch, "crash")
        design = root / "design.md"
        design.write_text(COMPLETE_DESIGN)
        real_loader = checker.load_md_drift_lint

        def crashing_loader():
            raise RuntimeError("injected crash")

        checker.load_md_drift_lint = crashing_loader
        error_output = io.StringIO()
        try:
            with contextlib.redirect_stderr(error_output), contextlib.redirect_stdout(io.StringIO()):
                code = checker.main([str(design), "--repository-root", str(root)])
        finally:
            checker.load_md_drift_lint = real_loader
        check("a crash inside the check: exit 2, cause printed",
              code == 2 and "crashed with RuntimeError: injected crash" in error_output.getvalue(),
              f"{code} {error_output.getvalue()!r}")

    print(f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
