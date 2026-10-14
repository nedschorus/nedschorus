#!/usr/bin/env python3
"""Tests for claude-code-session-transcript-project-directory-for-agent-seat-common.py.

Run: python3 scripts/claude-code-session-transcript-project-directory-for-agent-seat-common-test.py
Prints one line per case and exits non-zero if any case fails.

The three mangle cases expect hard-coded literal folder names, not ones
derived from the function under test, so a mangling bug cannot be mirrored
into the expectation; their seat paths are rooted at a directory that
exists on no machine, so resolve() passes them through unchanged. The
symlink case builds a real link in a temporary directory, because Claude
Code names the folder after the resolved path the session runs in. That
directory's path is known only at run time, so the case computes its
expected name with its own character test, independent of the function
under test.
"""

import importlib.util
import sys
import tempfile
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "claude_code_session_transcript_project_directory_for_agent_seat_common",
    Path(__file__).with_name("claude-code-session-transcript-project-directory-for-agent-seat-common.py"))
project_directory_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(project_directory_module)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def mangled_name(seat):
    return project_directory_module.project_directory_for_seat(
        Path(seat), Path("/proj")).name


def run_all_cases():
    # Claude Code v2.1.233, probed with a real session: [^a-zA-Z0-9] becomes "-", underscores included.
    check("mangle: underscore becomes dash (hard-coded, harness v2.1.233)",
          mangled_name("/mangle-probe-root/agents/mangle_probe")
          == "-mangle-probe-root-agents-mangle-probe",
          mangled_name("/mangle-probe-root/agents/mangle_probe"))
    check("mangle: plain dashed path (hard-coded)",
          mangled_name("/mangle-probe-root/agents/plain-seat")
          == "-mangle-probe-root-agents-plain-seat",
          mangled_name("/mangle-probe-root/agents/plain-seat"))
    check("mangle: dot becomes dash (hard-coded)",
          mangled_name("/mangle-probe-root/.claude/b")
          == "-mangle-probe-root--claude-b",
          mangled_name("/mangle-probe-root/.claude/b"))
    projects_root = Path("/proj")
    check("the folder sits directly under the projects root",
          project_directory_module.project_directory_for_seat(
              Path("/mangle-probe-root/agents/x"), projects_root).parent == projects_root,
          project_directory_module.project_directory_for_seat(
              Path("/mangle-probe-root/agents/x"), projects_root))

    with tempfile.TemporaryDirectory() as scratch:
        real_seat = Path(scratch).resolve() / "real" / "seat"
        real_seat.mkdir(parents=True)
        linked_seat = Path(scratch) / "link-to-seat"
        linked_seat.symlink_to(real_seat)
        expected = "".join(c if c.isascii() and c.isalnum() else "-" for c in str(real_seat))
        found = project_directory_module.project_directory_for_seat(
            linked_seat, projects_root).name
        check("a seat path reached through a symlink is named after the folder the link points to",
              found == expected and "link-to-seat" not in found, (found, expected))


if __name__ == "__main__":
    run_all_cases()
    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        sys.exit(1)
    print("all cases passed")
