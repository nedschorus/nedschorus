#!/usr/bin/env python3
"""Tests for backup-and-snapshot-write-guard.py.

Run: python3 .claude/hooks/backup-and-snapshot-write-guard-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("backup-and-snapshot-write-guard.py")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run_hook(session_cwd: Path, file_path: str, path_field: str = "file_path"):
    """path_field selects which tool_input key carries the target: Edit and
    Write use file_path, NotebookEdit uses notebook_path."""
    payload = json.dumps({"cwd": str(session_cwd), "tool_input": {path_field: file_path}})
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)], input=payload,
        capture_output=True, text=True, check=False, env=dict(os.environ),
    )


with tempfile.TemporaryDirectory() as temporary_directory:
    workspace = Path(temporary_directory)

    # The box: Timeshift's snapshots and its configuration.
    result = run_hook(workspace, "/mnt/backup/timeshift/snapshots/2026-08-14_11-00-01/x.txt")
    check("writing inside a Timeshift snapshot is blocked", result.returncode == 2,
          str(result.returncode))
    check("the refusal says backup state is never an agent's to write",
          "never an agent's to write" in result.stderr, result.stderr)
    check("the refusal offers no approval lane",
          "no approval lane" in result.stderr, result.stderr)
    check("the refusal points recovery at copying out instead",
          "copy the file out" in result.stderr, result.stderr)
    check("the refusal names no override marker",
          ".backup-write-approved" not in result.stderr
          and ".walk-approved" not in result.stderr,
          result.stderr)
    check("the refusal routes a real change to the user's own keyboard",
          "his own keyboard" in result.stderr, result.stderr)

    result = run_hook(workspace, "/etc/timeshift/timeshift.json")
    check("editing Timeshift configuration is blocked", result.returncode == 2)

    # The Mac: Time Machine's three shapes, including volumes named by the user.
    result = run_hook(workspace, "/Volumes/SomeDisk/Backups.backupdb/mac/2026-08-14/f.txt")
    check("a Time Machine backupdb on any volume is blocked", result.returncode == 2)

    result = run_hook(workspace, "/Volumes/SomeDisk/el.sparsebundle/token")
    check("a Time Machine sparsebundle is blocked", result.returncode == 2)

    result = run_hook(workspace, "/Volumes/.timemachine/host/snap/file.txt")
    check("the Time Machine automount tree is blocked", result.returncode == 2)

    # Paths that merely look adjacent must stay writable.
    result = run_hook(workspace, "/Volumes/nedhome/Projects/nedschorus/docs/x.md")
    check("the Mac's mount of the box's home is NOT blocked", result.returncode == 0,
          f"rc={result.returncode} {result.stderr}")

    result = run_hook(workspace, str(workspace / "backup-notes.md"))
    check("an ordinary file whose name contains 'backup' is NOT blocked",
          result.returncode == 0, f"rc={result.returncode} {result.stderr}")

    result = run_hook(workspace, str(workspace / "mnt" / "backup" / "x"))
    check("a relative lookalike outside the real prefix is NOT blocked",
          result.returncode == 0, f"rc={result.returncode} {result.stderr}")

    # The override lane is gone (user-ruled 2026-08-17). A marker left over
    # from before the removal must neither authorize a write nor be touched.
    legacy_marker = workspace / ".backup-write-approved"
    legacy_marker.write_text("he said: go ahead and change the retention\n", encoding="utf-8")
    result = run_hook(workspace, "/etc/timeshift/timeshift.json")
    check("a populated legacy marker does not let a write through", result.returncode == 2,
          f"rc={result.returncode}")
    check("the legacy marker is left untouched, not consumed", legacy_marker.exists())

    # The instruction-file guard's marker must not authorise a backup write.
    (workspace / ".walk-approved").write_text("approved\n", encoding="utf-8")
    result = run_hook(workspace, "/mnt/backup/timeshift/x")
    check("an instruction-file approval does not carry to backups", result.returncode == 2)

    # --- NotebookEdit carries its target in notebook_path (PR #86's review) ---
    # This guard is registered on NotebookEdit, so reading only file_path left
    # a notebook write into backup state entirely unguarded.
    result = run_hook(workspace, "/mnt/backup/timeshift/snapshot/notes.ipynb",
                      path_field="notebook_path")
    check("a notebook write into Timeshift's backup drive is blocked",
          result.returncode == 2, result.stderr)
    result = run_hook(workspace, "/Volumes/TM/Backups.backupdb/mac/notes.ipynb",
                      path_field="notebook_path")
    check("a notebook write into a Time Machine store is blocked",
          result.returncode == 2, result.stderr)
    result = run_hook(workspace, str(workspace / "ordinary.ipynb"),
                      path_field="notebook_path")
    check("an ordinary notebook still passes through notebook_path",
          result.returncode == 0, result.stderr)

if failures:
    print(f"\n{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("\nall cases passed")
