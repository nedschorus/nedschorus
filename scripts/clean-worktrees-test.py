#!/usr/bin/env python3
"""Tests for clean-worktrees.py.

Builds a scratch repository with an origin remote and one worktree per
classification — done, dirty, ignored-files-only, unlanded, occupied, and
outside the managed area — then asserts the report names each correctly and
that --remove reaps exactly the done one.

The vacancy check's unusable-answer cases cannot be produced by a real lsof
on a healthy machine, so they run the reaper with a stub lsof first on PATH.
Those cases guard the reaper's central promise — ambiguity keeps, never
reaps — which a worktree holding someone's uncommitted work depends on.

Run: python3 scripts/clean-worktrees-test.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CLEAN_SCRIPT = Path(__file__).with_name("clean-worktrees.py")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def git(repo, *arguments):
    completed = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)}: {completed.stderr.strip()}")
    return completed.stdout


def run_clean(repo, *flags):
    return subprocess.run(
        [sys.executable, str(CLEAN_SCRIPT), "--repo", str(repo), *flags],
        capture_output=True, text=True, check=False,
    )


def run_clean_with_stub_lsof(repo, stub_directory, stub_body):
    """Run the reaper with a fake lsof first on PATH.

    A real lsof exits 0 on both fleet machines even while printing warnings,
    so the failure paths it is supposed to have — nonzero exit, empty
    listing — have no natural trigger to test against. The stub supplies one.
    """
    stub_directory.mkdir(parents=True, exist_ok=True)
    stub = stub_directory / "lsof"
    stub.write_text(stub_body, encoding="utf-8")
    stub.chmod(0o755)
    environment = dict(os.environ)
    environment["PATH"] = f"{stub_directory}{os.pathsep}{environment.get('PATH', '')}"
    return subprocess.run(
        [sys.executable, str(CLEAN_SCRIPT), "--repo", str(repo)],
        capture_output=True, text=True, check=False, env=environment,
    )


with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)
    checkout = scratch / "checkout"
    origin = scratch / "origin.git"

    # A checkout whose origin/main exists, so the landed check has its anchor.
    checkout.mkdir()
    git(checkout, "init", "-b", "main")
    git(checkout, "config", "user.email", "test@test.invalid")
    git(checkout, "config", "user.name", "clean-worktrees test")
    (checkout / "README.md").write_text("# scratch\n", encoding="utf-8")
    (checkout / ".gitignore").write_text(
        "scratch-state/\n.DS_Store\n__pycache__/\n", encoding="utf-8")
    git(checkout, "add", "-A")
    git(checkout, "commit", "-m", "seed")
    subprocess.run(["git", "init", "--bare", str(origin)],
                   capture_output=True, check=True)
    git(checkout, "remote", "add", "origin", str(origin))
    git(checkout, "push", "-u", "origin", "main")

    managed = checkout / ".claude" / "worktrees"
    managed.mkdir(parents=True)

    def add_worktree(name, where=None):
        path = (where or managed) / name
        git(checkout, "worktree", "add", "-b", f"{name}-branch", str(path), "origin/main")
        return path

    done_wt = add_worktree("done-wt")
    # Regenerable junk must not keep an otherwise-done worktree.
    (done_wt / ".DS_Store").write_text("junk", encoding="utf-8")
    (done_wt / "__pycache__").mkdir()
    (done_wt / "__pycache__" / "a.pyc").write_text("junk", encoding="utf-8")
    dirty_wt = add_worktree("dirty-wt")
    (dirty_wt / "uncommitted.txt").write_text("scratch\n", encoding="utf-8")
    ignored_wt = add_worktree("ignored-wt")
    (ignored_wt / "scratch-state").mkdir()
    (ignored_wt / "scratch-state" / "ledger.md").write_text("state\n", encoding="utf-8")
    unlanded_wt = add_worktree("unlanded-wt")
    (unlanded_wt / "new.txt").write_text("work\n", encoding="utf-8")
    git(unlanded_wt, "add", "-A")
    git(unlanded_wt, "commit", "-m", "unlanded work")
    outside_wt = add_worktree("outside-wt", where=scratch)

    occupant = None
    occupied_wt = None
    if shutil.which("lsof"):
        occupied_wt = add_worktree("occupied-wt")
        occupant = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(120)"],
            cwd=str(occupied_wt),
        )
    else:
        print("SKIP  occupied cases: lsof is not installed on this machine")

    try:
        # --- The report classifies every worktree ---------------------------
        report = run_clean(checkout).stdout
        check("a clean, landed, vacant worktree reports done",
              "done-wt: done" in report, report)
        check("uncommitted files keep a worktree",
              "dirty-wt: kept" in report and "file(s)" in report, report)
        check("ignored files alone keep a worktree",
              "ignored-wt: kept" in report, report)
        check("unlanded commits keep a worktree",
              "unlanded-wt: kept" in report and "not on origin/main" in report, report)
        check("a worktree outside the managed area is kept",
              "outside-wt: kept" in report and "outside the managed area" in report,
              report)
        if occupied_wt is not None:
            check("a live process keeps a worktree",
                  "occupied-wt: kept" in report and "live process" in report, report)
        check("no dead-registration line while every directory exists",
              "git worktree prune" not in report, report)

        # --- Anchoring: a copy run from inside a worktree sees the same repo -
        from_inside = run_clean(dirty_wt).stdout
        check("run from inside a worktree, classifications are unchanged",
              "done-wt: done" in from_inside and "dirty-wt: kept" in from_inside
              and "outside-wt: kept" in from_inside, from_inside)

        # --- --only-done prints done worktrees and nothing else -------------
        only_done = run_clean(checkout, "--only-done").stdout
        check("--only-done names the done worktree and its removal command",
              "done-wt" in only_done and "--remove" in only_done, only_done)
        check("--only-done stays silent about kept worktrees",
              "dirty-wt" not in only_done and "unlanded-wt" not in only_done,
              only_done)

        # --- An untrustworthy vacancy answer keeps, and says so honestly ----
        # Each case below reaps done-wt against the pre-fix implementation,
        # which read lsof's stdout and never its exit status: no path matched,
        # so it reported vacant and --remove would have deleted the worktree.
        stub_home = scratch / "stub-lsof"

        failed_lsof = run_clean_with_stub_lsof(
            checkout, stub_home / "nonzero", "#!/bin/sh\nexit 1\n").stdout
        check("an lsof that exits nonzero keeps the worktree",
              "done-wt: kept" in failed_lsof, failed_lsof)
        check("a failed vacancy check is reported as untrusted, not as occupancy",
              "done-wt: kept" in failed_lsof
              and "vacancy" in failed_lsof
              and "live process is rooted inside it" not in failed_lsof,
              failed_lsof)

        empty_lsof = run_clean_with_stub_lsof(
            checkout, stub_home / "empty", "#!/bin/sh\nexit 0\n").stdout
        check("an lsof reporting no working directories at all keeps the worktree",
              "done-wt: kept" in empty_lsof and "no working directories" in empty_lsof,
              empty_lsof)

        # The converse, so failing closed does not become ignoring the answer:
        # a listing that names the worktree is occupancy even if lsof exited
        # nonzero, which is the everyday partial-permissions case.
        matching_lsof = run_clean_with_stub_lsof(
            checkout, stub_home / "match",
            f"#!/bin/sh\necho 'n{done_wt.resolve()}'\nexit 1\n").stdout
        check("a path match counts as occupancy even when lsof exits nonzero",
              "done-wt: kept" in matching_lsof
              and "live process is rooted inside it" in matching_lsof,
              matching_lsof)

        # --- Dead registrations are named, with the prune command ------------
        # A worktree registered under a temp directory leaves a dead entry
        # when the temp area clears (R25, ruled 2026-08-18). Simulate the
        # clearing: delete the directory behind git's back, so the
        # registration outlives it.
        dead_wt = add_worktree("dead-registration-wt", where=scratch)
        shutil.rmtree(dead_wt)
        dead_report = run_clean(checkout).stdout
        dead_line = next((line for line in dead_report.splitlines()
                          if "git worktree prune" in line), "")
        check("a dead registration is named with the prune command",
              "dead-registration-wt" in dead_line, dead_report)
        # dead_line must be non-empty here, or this check would pass against
        # an empty haystack — asserting absence in a line that never printed.
        check("living worktrees are not named on the dead-registration line",
              dead_line != "" and "done-wt" not in dead_line
              and "dirty-wt" not in dead_line, dead_report)
        dead_only_done = run_clean(checkout, "--only-done").stdout
        check("--only-done carries the dead-registration line (the launchers' boot mode)",
              "dead-registration-wt" in dead_only_done
              and "git worktree prune" in dead_only_done, dead_only_done)

        # --- --remove reaps exactly the done worktree ------------------------
        removal = run_clean(checkout, "--remove")
        check("--remove removes the done worktree",
              not done_wt.exists() and "done-wt: removed" in removal.stdout,
              removal.stdout)
        branches = git(checkout, "branch", "--list", "done-wt-branch")
        check("--remove deletes the reaped worktree's merged branch",
              branches.strip() == "", branches)
        check("--remove keeps every not-done worktree",
              dirty_wt.exists() and ignored_wt.exists() and unlanded_wt.exists()
              and outside_wt.exists()
              and (occupied_wt is None or occupied_wt.exists()),
              removal.stdout)
        check("--remove exits 0 when nothing failed", removal.returncode == 0,
              str(removal.returncode))
        check("--remove reports the dead registration too",
              "dead-registration-wt" in removal.stdout
              and "git worktree prune" in removal.stdout, removal.stdout)
        still_listed = git(checkout, "worktree", "list", "--porcelain")
        check("the dead registration survives --remove — the prune stays deliberate",
              "dead-registration-wt" in still_listed, still_listed)
    finally:
        if occupant is not None:
            occupant.kill()
            occupant.wait()

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
