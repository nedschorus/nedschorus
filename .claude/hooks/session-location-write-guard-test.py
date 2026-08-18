#!/usr/bin/env python3
"""Tests for session-location-write-guard.py.

Run: python3 .claude/hooks/session-location-write-guard-test.py
Prints one line per case and exits non-zero if any case fails. Cases run
against throwaway repositories mirroring the fleet layout: a clone whose main
worktree is the reference copy, with linked worktrees as seats. As with the
sibling guards' suites, $CLAUDE_PROJECT_DIR is pointed at a decoy throughout
to prove the guard never consults it.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("session-location-write-guard.py")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run_hook(session_cwd: Path, file_path: str, decoy: Path, notebook: bool = False):
    key = "notebook_path" if notebook else "file_path"
    payload = json.dumps({"cwd": str(session_cwd), "tool_input": {key: file_path}})
    environment = dict(os.environ, CLAUDE_PROJECT_DIR=str(decoy))
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)], input=payload,
        capture_output=True, text=True, check=False, env=environment,
    )


def git(arguments, cwd: Path):
    return subprocess.run(["git", *arguments], cwd=str(cwd),
                          capture_output=True, text=True, check=False)


with tempfile.TemporaryDirectory() as temporary_directory:
    tmp = Path(temporary_directory)
    decoy = tmp / "decoy"
    decoy.mkdir()

    # The reference copy: a repository's main worktree, parked on main.
    reference = tmp / "reference-clone"
    reference.mkdir()
    git(["init", "-q", "-b", "main"], reference)
    git(["config", "user.email", "t@example.invalid"], reference)
    git(["config", "user.name", "location test"], reference)
    (reference / "file.txt").write_text("content\n", encoding="utf-8")
    git(["add", "file.txt"], reference)
    git(["commit", "-q", "-m", "first"], reference)

    # A seat: a linked worktree on its own branch.
    seat = tmp / "seat-worktree"
    git(["worktree", "add", "-q", "-b", "seat", str(seat), "main"], reference)

    # A detached seat.
    detached = tmp / "detached-worktree"
    git(["worktree", "add", "-q", "--detach", str(detached), "main"], reference)

    result = run_hook(seat, str(seat / "notes.md"), decoy)
    check("a branch seat writes freely into its own checkout", result.returncode == 0,
          result.stderr)

    result = run_hook(detached, str(detached / "notes.md"), decoy)
    check("a detached session's write into its checkout is blocked", result.returncode == 2,
          str(result.returncode))
    check("the detached refusal teaches the branch fix", "git switch -c" in result.stderr,
          result.stderr)

    result = run_hook(detached, str(tmp / "outside-any-repo.md"), decoy)
    check("a detached session may still write outside its checkout", result.returncode == 0,
          result.stderr)

    result = run_hook(reference, str(reference / "docs.md"), decoy)
    check("a session seated in the reference checkout is blocked", result.returncode == 2,
          str(result.returncode))
    check("the reference refusal names the marker", ".location-write-approved" in result.stderr,
          result.stderr)

    result = run_hook(reference, str(reference / "book.ipynb"), decoy, notebook=True)
    check("NotebookEdit's notebook_path is judged too", result.returncode == 2,
          str(result.returncode))

    result = run_hook(reference, str(seat / "other.md"), decoy)
    check("a reference-seated write into ANOTHER tree is not this guard's business",
          result.returncode == 0, result.stderr)

    # The exception lane: one approved write per marker, own marker file.
    marker = reference / ".location-write-approved"
    marker.write_text("user approved: the merge lane's conflict resolution\n", encoding="utf-8")
    result = run_hook(reference, str(reference / "file.txt"), decoy)
    check("an approved write in the reference passes once", result.returncode == 0,
          result.stderr)
    check("the marker is consumed by the pass", not marker.exists())
    result = run_hook(reference, str(reference / "file.txt"), decoy)
    check("the next write is blocked again", result.returncode == 2)

    marker.write_text("   \n", encoding="utf-8")
    result = run_hook(reference, str(reference / "file.txt"), decoy)
    check("an empty marker approves nothing", result.returncode == 2)
    marker.unlink()

    # The instruction-file guard's marker must not carry over to this guard.
    (reference / ".walk-approved").write_text("approved\n", encoding="utf-8")
    result = run_hook(reference, str(reference / "file.txt"), decoy)
    check("a .walk-approved marker does not authorize a location write",
          result.returncode == 2)

    # The landing side (user-walked 2026-08-17): a write from a seat into the
    # reference checkout is refused; other trees stay out of scope.
    result = run_hook(seat, str(reference / "landed-from-seat.md"), decoy)
    check("a seat's write landing in the reference is blocked", result.returncode == 2,
          str(result.returncode))
    check("the cross refusal says the session is seated elsewhere",
          "seated elsewhere" in result.stderr, result.stderr)
    result = run_hook(seat, str(reference / "brand" / "new" / "dir" / "note.md"), decoy)
    check("a write creating new directories in the reference is still judged",
          result.returncode == 2, str(result.returncode))
    seat_marker = seat / ".location-write-approved"
    seat_marker.write_text("user approved: the merge lane's cross-tree fix\n", encoding="utf-8")
    result = run_hook(seat, str(reference / "landed-from-seat.md"), decoy)
    check("the cross block honours a marker in the SESSION'S own tree",
          result.returncode == 0, result.stderr)
    check("the cross marker is consumed", not seat_marker.exists())

    # A second seat's tree is deliberately out of scope: no recorded incident.
    other_seat = tmp / "other-seat-worktree"
    git(["worktree", "add", "-q", "-b", "other-seat", str(other_seat), "main"], reference)
    result = run_hook(seat, str(other_seat / "note.md"), decoy)
    check("a write into another SEAT'S tree is not blocked (recorded-unbuilt class)",
          result.returncode == 0, result.stderr)

    # A standalone clone is its own workspace, never "the reference" —
    # verdict pinned per the #88 review's standalone-clone finding.
    lone = tmp / "standalone-clone"
    git(["clone", "-q", str(reference), str(lone)], tmp)
    result = run_hook(lone, str(lone / "notes.md"), decoy)
    check("a session seated in a standalone clone writes freely",
          result.returncode == 0, result.stderr)
    result = run_hook(seat, str(lone / "notes.md"), decoy)
    check("a write landing in a standalone clone is not blocked",
          result.returncode == 0, result.stderr)

    nowhere = tmp / "not-a-checkout"
    nowhere.mkdir()
    result = run_hook(nowhere, str(nowhere / "anything.md"), decoy)
    check("a session outside any checkout passes", result.returncode == 0, result.stderr)
    result = run_hook(nowhere, str(reference / "from-nowhere.md"), decoy)
    check("a no-checkout session's write landing in the reference is still blocked",
          result.returncode == 2, str(result.returncode))

    result = run_hook(seat, "", decoy)
    check("a payload without a target passes", result.returncode == 0)

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
