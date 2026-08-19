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


def run_hook(session_cwd: Path, file_path: str, decoy: Path, notebook: bool = False,
             path_prefix: Path = None, process_cwd: Path = None):
    """Invoke the guard.

    path_prefix puts a directory first on PATH, so a stub git can drive states
    a real git will not produce on demand. process_cwd runs the hook from
    somewhere other than the session's directory, which is how a relative
    target proves it is judged against the session and not against the hook.
    """
    key = "notebook_path" if notebook else "file_path"
    payload = json.dumps({"cwd": str(session_cwd), "tool_input": {key: file_path}})
    environment = dict(os.environ, CLAUDE_PROJECT_DIR=str(decoy))
    if path_prefix is not None:
        environment["PATH"] = f"{path_prefix}{os.pathsep}{environment.get('PATH', '')}"
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)], input=payload,
        capture_output=True, text=True, check=False, env=environment,
        cwd=str(process_cwd) if process_cwd is not None else None,
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

    # ------------------------------------------------------------------
    # PR #88's review: the two HEAD states the old reading got wrong
    # ------------------------------------------------------------------
    # A repository created by `git init` with nothing committed. The old
    # reading called this detached, because `rev-parse --abbrev-ref HEAD`
    # prints "HEAD" there while exiting 128, and the exit status was ignored.
    unborn = tmp / "unborn-repository"
    unborn.mkdir()
    git(["init", "-q", "-b", "main"], unborn)
    result = run_hook(unborn, str(unborn / "first.md"), decoy)
    check("an unborn repository is not reported as detached HEAD",
          "detached HEAD" not in result.stderr, result.stderr)
    check("the unborn refusal says the repository has no commits yet",
          "no commits yet" in result.stderr, result.stderr)
    check("the unborn refusal names the branch HEAD points at",
          "main" in result.stderr, result.stderr)

    # A healthy seat whose HEAD lookups fail. The old reading treated ANY
    # failure of its one git command as detached, so a transient fault refused
    # a seat that was on a perfectly good branch and told it to fix a state it
    # was not in. A stub git fails exactly the two HEAD questions and delegates
    # everything else, so the repository still resolves.
    import shutil as _shutil
    real_git = _shutil.which("git")
    stub_directory = tmp / "stub-git"
    stub_directory.mkdir()
    stub_git = stub_directory / "git"
    stub_git.write_text(
        "#!/bin/sh\n"
        'case "$1" in\n'
        "  symbolic-ref) exit 128 ;;\n"
        "esac\n"
        'if [ "$1" = "rev-parse" ] && [ "$2" = "--verify" ]; then exit 128; fi\n'
        # --abbrev-ref is what the OLD reading used. Breaking only the new
        # commands would let the pre-fix guard pass this case for the wrong
        # reason; the realistic fault is a git that cannot answer about HEAD
        # at all, while --show-toplevel still resolves the repository.
        'if [ "$1" = "rev-parse" ] && [ "$2" = "--abbrev-ref" ]; then exit 128; fi\n'
        f'exec {real_git} "$@"\n',
        encoding="utf-8")
    stub_git.chmod(0o755)
    # With no marker present the old reading's refusal is visible directly.
    result = run_hook(seat, str(seat / "notes.md"), decoy, path_prefix=stub_directory)
    check("an unreadable HEAD does not refuse a healthy seat as detached",
          result.returncode == 0, result.stderr)
    check("an unreadable HEAD does not claim the seat is on a detached HEAD",
          "detached HEAD" not in result.stderr, result.stderr)
    # And with one present, the old reading spent it to let the write through —
    # the seat paid an approval for a state it was never in.
    stub_marker = seat / ".location-write-approved"
    stub_marker.write_text("an approval that must not be spent here\n", encoding="utf-8")
    result = run_hook(seat, str(seat / "notes.md"), decoy, path_prefix=stub_directory)
    check("an unreadable HEAD does not spend the seat's marker", stub_marker.exists())
    stub_marker.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # PR #91's review: the .git asymmetry, and marker inertness
    # ------------------------------------------------------------------
    # git will not answer --show-toplevel from inside a .git directory, so the
    # reference checkout's own machinery resolved to no owner and passed, while
    # an ordinary file one level up was refused. .git/hooks/ is executable code.
    result = run_hook(seat, str(reference / ".git" / "hooks" / "pre-commit"), decoy)
    check("a seat's write into the reference's .git/hooks is blocked",
          result.returncode == 2, str(result.returncode))
    result = run_hook(seat, str(reference / ".git" / "config"), decoy)
    check("a seat's write into the reference's .git/config is blocked",
          result.returncode == 2, str(result.returncode))
    result = run_hook(seat, str(seat / ".git"), decoy)
    check("a seat's write to its OWN .git is not this guard's business",
          result.returncode == 0, result.stderr)

    # The detached refusal must teach marker creation by shell, because such a
    # session cannot write the marker with the tool this guard blocks.
    result = run_hook(detached, str(detached / "notes.md"), decoy)
    check("the detached refusal says to create the marker with a shell command",
          "printf" in result.stderr or "echo" in result.stderr, result.stderr)

    # A marker sitting at the TARGET's root must stay inert and unspent for a
    # normally-seated session: without this, an implementation that wrongly
    # honoured the target's marker would still pass every other case here.
    target_side_marker = reference / ".location-write-approved"
    target_side_marker.write_text("an approval lying in the target tree\n", encoding="utf-8")
    result = run_hook(seat, str(reference / "still-blocked.md"), decoy)
    check("a marker at the TARGET's root does not approve a cross write",
          result.returncode == 2, str(result.returncode))
    check("a marker at the TARGET's root is left unspent", target_side_marker.exists())
    target_side_marker.unlink()

    # ------------------------------------------------------------------
    # PR #88's review: the remaining test gaps
    # ------------------------------------------------------------------
    # A relative target is judged against the SESSION's directory. The hook runs
    # from somewhere else entirely, so a guard resolving against its own cwd
    # would reach the wrong tree.
    result = run_hook(reference, "docs-relative.md", decoy, process_cwd=tmp)
    check("a relative target is judged against the session's directory",
          result.returncode == 2, str(result.returncode))
    result = run_hook(seat, "notes-relative.md", decoy, process_cwd=reference)
    check("a relative target does not inherit the hook process's directory",
          result.returncode == 0, result.stderr)

    # A session seated in a SUBDIRECTORY of its checkout is still that checkout.
    reference_subdirectory = reference / "nested" / "deeper"
    reference_subdirectory.mkdir(parents=True)
    result = run_hook(reference_subdirectory, str(reference / "from-subdir.md"), decoy)
    check("a session in a subdirectory of the reference is still seated there",
          result.returncode == 2, str(result.returncode))
    seat_subdirectory = seat / "nested"
    seat_subdirectory.mkdir()
    result = run_hook(seat_subdirectory, str(seat / "ok.md"), decoy)
    check("a session in a subdirectory of a seat writes freely",
          result.returncode == 0, result.stderr)

    # An explicitly symlinked path must be judged by where it LANDS.
    symlink_to_reference = tmp / "link-to-reference"
    symlink_to_reference.symlink_to(reference, target_is_directory=True)
    result = run_hook(seat, str(symlink_to_reference / "through-a-link.md"), decoy)
    check("a write reaching the reference through a symlink is blocked",
          result.returncode == 2, str(result.returncode))

    # The allowed side of NotebookEdit: the field is read, not merely blocked.
    result = run_hook(seat, str(seat / "analysis.ipynb"), decoy, notebook=True)
    check("a seat's own notebook write passes through notebook_path",
          result.returncode == 0, result.stderr)

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
