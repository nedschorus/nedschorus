#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/markdown-file-standard-rules-for-the-markdown-file-kind-at-a-path-print.py.

The program must pick the right section of the Markdown file standard for each kind of path,
print the common part alone and exit 1 for a path no section covers, and exit 2 when the
standard is missing, lacks a heading, or the program is called wrongly. The real standard
must hold every heading the program's constants name.

Run: python3 nc-systems/general-tools/tests/markdown-file-standard-rules-for-the-markdown-file-kind-at-a-path-print-test.py
Prints one line per case and a verdict line, and exits 1 if any case fails.
"""

import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PROGRAM_PATH = Path(os.environ.get(
    "MARKDOWN_FILE_STANDARD_RULES_FOR_THE_MARKDOWN_FILE_KIND_AT_A_PATH_PRINT_PROGRAM_PATH",
    REPOSITORY_ROOT / "nc-systems" / "general-tools"
    / "markdown-file-standard-rules-for-the-markdown-file-kind-at-a-path-print.py"))
_spec = importlib.util.spec_from_file_location(
    "markdown_file_standard_rules_for_the_markdown_file_kind_at_a_path_print", PROGRAM_PATH)
program = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(program)

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


def run(argv, standard_path=program.MARKDOWN_FILE_STANDARD_PATH):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = program.main(argv, standard_path)
    return code, out.getvalue(), err.getvalue()


# Each kind's paths, including the ones a wider pattern also matches.
expected_kinds = {
    "/home/nedlern/.claude/handoffs/merge-lane-2-next-step-20261117-133829.md": "Handoff next-step files",
    "/Volumes/nedhome/.claude/handoffs/reboot-test-next-step-20261117-105148.md": "Handoff next-step files",
    "/home/nedlern/agents/merge-lane-2/CLAUDE.local.md": "Seat-briefs",
    "CLAUDE.local.md": "Seat-briefs",
    "docs/nedschorus-wiki/nedschorus-glossary.md": "The project glossary",
    "/home/nedlern/agents/x-wt/docs/nedschorus-wiki/nedschorus-glossary.md": "The project glossary",
    "docs/issues/46-ghi-guide-agent-design.md": "Designs",
    "docs/issues/queue/topic-branch-creation-script-design.md": "Designs",
    "nc-systems/handoff/handoff-design.md": "Designs",
    "docs/nedschorus-wiki/nedschorus-style-guide.md": "Wiki pages",
    "docs/nedschorus-wiki/queue/nedschorus-markdown-file-standard-common-part-and-one-section-per-kind.md": "Wiki pages",
    "docs/nedschorus-wiki/nedschorus-handoff-architecture-overview.md": "Wiki pages",
    "/Volumes/nedhome/Projects/nedschorus/docs/nedschorus-wiki/nedschorus-agent-seat-model.md": "Wiki pages",
    "docs/issues/1080-type-definitions-for-the-project-s-kinds-of.md": "GHI-MDs",
    "docs/issues/queue/the-signal-sandbox-test-fails.md": "GHI-MDs",
}
for path, kind in expected_kinds.items():
    got = program.kind_section_heading_for_path(path)
    check(f"{path} is covered by {kind}", got == kind, got)

# Paths no section covers.
for path in [
    "README.md",
    "docs/issues/README.md",
    "docs/issues/queue/x-test-design.md",
    "docs/issues/46-ghi-guide-agent-test-design.md",
    "nc-systems/handoff/handoff-contract.md",
    "nc-systems/handoff/handoff-system-glossary.md",
    "docs/nedschorus-wiki/nedschorus-handoff-architecture-overview-proposed-improvements-or-changes-overview-write-claim-check-by-fresh-agent-2026-11-04.md",
    "docs/walk/walk-me-through-skill-refactor-approval-walk-2026-11-02.md",
    "notes-CLAUDE.local.md.bak",
]:
    got = program.kind_section_heading_for_path(path)
    check(f"no section covers {path}", got is None, got)

# The real standard holds every heading the constants name.
real_sections = program.markdown_file_standard_sections()
for heading in [program.COMMON_PART_HEADING] + [h for h, _ in program.KIND_SECTION_HEADING_AND_PATH_PATTERNS]:
    check(f"the standard has the heading ## {heading}", heading in real_sections, sorted(real_sections))

# A covered path prints the common part, then its section, and nothing of other sections.
code, out, err = run(["docs/issues/46-ghi-guide-agent-design.md"])
check("a covered path exits 0", code == 0, (code, err))
check("a covered path prints the common part first", out.startswith("## Common part\n"), out[:80])
check("a covered path prints its section", "\n## Designs\n" in out, out[-200:])
check("a covered path prints no other section", "## GHI-MDs" not in out and "## Seat-briefs" not in out, out)
check("a covered path prints nothing on stderr", err == "", err)

# A path no section covers: the common part alone, a message on stderr, exit 1.
code, out, err = run(["README.md"])
check("an uncovered path exits 1", code == 1, code)
check("an uncovered path prints the common part alone",
      out.startswith("## Common part\n") and "\n## " not in out, out)
check("an uncovered path says no section covers it", "no section of the standard covers README.md" in err, err)

with tempfile.TemporaryDirectory() as scratch:
    # A standard that cannot be read: exit 2, nothing on stdout.
    code, out, err = run(["README.md"], Path(scratch) / "missing.md")
    check("a standard that cannot be read exits 2", code == 2, code)
    check("a standard that cannot be read prints nothing on stdout", out == "", out)
    check("a standard that cannot be read is named on stderr", "cannot read" in err and "missing.md" in err, err)

    # A standard missing a heading the constants name: exit 2, naming the heading.
    partial = Path(scratch) / "partial.md"
    partial.write_text(
        "# Standard\n\n## Common part\n\ncommon\n\n```\n## Designs\n```\n\n"
        + "".join(f"## {h}\n\nbody\n\n" for h, _ in program.KIND_SECTION_HEADING_AND_PATH_PATTERNS
                  if h != "Designs"),
        encoding="utf-8")
    code, out, err = run(["nc-systems/handoff/handoff-design.md"], partial)
    check("a standard missing a heading exits 2", code == 2, code)
    check("a heading inside a code fence does not count", '"## Designs"' in err, err)

# Called wrongly, and asked for help, as a separate process.
for argv, expected_code in [([], 2), (["a.md", "b.md"], 2), (["--help"], 0)]:
    result = subprocess.run([sys.executable, str(PROGRAM_PATH), *argv], capture_output=True, text=True)
    check(f"argv {argv} exits {expected_code}", result.returncode == expected_code,
          (result.returncode, result.stderr))
    if expected_code == 2:
        check(f"argv {argv} prints its usage on stderr", "Usage:" in result.stderr, result.stderr)
    else:
        check("--help prints the help on stdout", "Exits 0 if" in result.stdout, result.stdout)

print(f"VERDICT: {'FAIL' if failures else 'PASS'} ({failures} failed)")
sys.exit(1 if failures else 0)
