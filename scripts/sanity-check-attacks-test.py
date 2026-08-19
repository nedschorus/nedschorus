#!/usr/bin/env python3
"""Tests for sanity-check-attacks.py's worktree write detector.

The detector's only value is being trustworthy about whether a codex cell
wrote to the worktree, and every hole in it is silent by construction. Each
case below builds a scratch repository, snapshots it, simulates a cell write,
and asserts the write is named. The three holes under test were found
reviewing PRs #98 and #102:

  - a file already dirty before the run, rewritten by a cell (label
    comparison misses it; content hashes catch it)
  - a wholly-untracked directory, which porcelain collapses to one entry, so
    anything a cell writes under it is invisible without -uall
  - a non-ASCII pathname, which git C-quotes without -z, producing a path
    that matches nothing on disk and fingerprints as "absent" on both sides

Run: python3 scripts/sanity-check-attacks-test.py
"""

import importlib.util
import pathlib
import shutil
import subprocess
import sys
import tempfile

RUNNER_SCRIPT = pathlib.Path(__file__).with_name("sanity-check-attacks.py")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def load_runner():
    spec = importlib.util.spec_from_file_location("sanity_check_attacks", RUNNER_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(repo, *arguments):
    completed = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)}: {completed.stderr.strip()}")
    return completed.stdout


def new_repo(root):
    git(root, "init", "-q")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "test")
    (root / "tracked.md").write_text("original\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "initial")
    return root


def main():
    runner = load_runner()
    snapshot = runner.worktree_snapshot
    strays = getattr(runner, "stray_paths", None)
    if strays is None:
        def strays(baseline, now):
            return sorted(path for path in set(now) | set(baseline)
                          if now.get(path) != baseline.get(path))

    # Case 1: a file already dirty before the run, rewritten by a cell.
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        (repo / "tracked.md").write_text("dirty before the run\n", encoding="utf-8")
        baseline = snapshot(repo)
        (repo / "tracked.md").write_text("a cell wrote this\n", encoding="utf-8")
        found = strays(baseline, snapshot(repo))
        check("already-dirty file rewritten by a cell is detected",
              "tracked.md" in found, f"stray list was {found}")

    # Case 2: a file written under a directory that was already untracked.
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        (repo / "untracked-dir").mkdir()
        (repo / "untracked-dir" / "already-here.md").write_text("x\n", encoding="utf-8")
        baseline = snapshot(repo)
        (repo / "untracked-dir" / "cell-wrote-this.md").write_text("y\n", encoding="utf-8")
        found = strays(baseline, snapshot(repo))
        check("file written under an already-untracked directory is detected",
              "untracked-dir/cell-wrote-this.md" in found, f"stray list was {found}")

    # Case 3: a non-ASCII pathname, which git C-quotes unless -z is used.
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        unicode_name = "dirty-ünicode.md"
        (repo / unicode_name).write_text("original\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "add unicode file")
        (repo / unicode_name).write_text("dirty before the run\n", encoding="utf-8")
        baseline = snapshot(repo)
        (repo / unicode_name).write_text("a cell wrote this\n", encoding="utf-8")
        found = strays(baseline, snapshot(repo))
        check("rewrite of a non-ASCII pathname is detected",
              unicode_name in found,
              f"stray list was {found}; baseline was {baseline}")

    # Case 4: a quiet run reports nothing.
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        (repo / "untracked-dir").mkdir()
        (repo / "untracked-dir" / "already-here.md").write_text("x\n", encoding="utf-8")
        baseline = snapshot(repo)
        found = strays(baseline, snapshot(repo))
        check("a run that writes nothing produces no stray", found == [],
              f"stray list was {found}")

    # Case 5: a staged rename must not desynchronize the field walk. Under -z
    # the origin path is its own field, so a parser expecting " -> " consumes
    # one field too few and mistakes the origin path for the next entry.
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        (repo / "zz-last.md").write_text("tail\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "add tail file")
        git(repo, "mv", "tracked.md", "renamed.md")
        baseline = snapshot(repo)
        (repo / "zz-last.md").write_text("a cell wrote this\n", encoding="utf-8")
        found = strays(baseline, snapshot(repo))
        check("a write after a staged rename is still detected",
              "zz-last.md" in found, f"stray list was {found}; baseline was {baseline}")

    print()
    if failures:
        print(f"{len(failures)} failing case(s): {', '.join(failures)}")
        return 1
    print("all cases pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
