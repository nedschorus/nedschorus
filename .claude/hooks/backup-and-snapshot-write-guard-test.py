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


def run_hook(project_directory: Path, file_path: str):
    payload = json.dumps({"tool_input": {"file_path": file_path}})
    environment = dict(os.environ, CLAUDE_PROJECT_DIR=str(project_directory))
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)], input=payload,
        capture_output=True, text=True, check=False, env=environment,
    )


with tempfile.TemporaryDirectory() as temporary_directory:
    workspace = Path(temporary_directory)

    # The box: Timeshift's snapshots and its configuration.
    result = run_hook(workspace, "/mnt/backup/timeshift/snapshots/2026-08-14_11-00-01/x.txt")
    check("writing inside a Timeshift snapshot is blocked", result.returncode == 2,
          str(result.returncode))
    check("the refusal demands permission in this conversation",
          "in this conversation, now" in result.stderr, result.stderr)
    check("the refusal rejects prior approval as sufficient",
          "prior approval" in result.stderr, result.stderr)
    check("the refusal points recovery at copying out instead",
          "copy the file out" in result.stderr, result.stderr)
    check("the refusal names its own marker, not the instruction-file one",
          ".backup-write-approved" in result.stderr and ".walk-approved" not in result.stderr,
          result.stderr)

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

    # The override: fresh, single-use, and its own marker.
    marker = workspace / ".backup-write-approved"
    marker.write_text("he said: go ahead and change the retention\n", encoding="utf-8")
    result = run_hook(workspace, "/etc/timeshift/timeshift.json")
    check("a populated marker lets one write through", result.returncode == 0,
          f"rc={result.returncode} {result.stderr}")
    check("the marker is consumed by the call it approves", not marker.exists())

    result = run_hook(workspace, "/etc/timeshift/timeshift.json")
    check("the next write is blocked again", result.returncode == 2)

    marker.write_text("   \n", encoding="utf-8")
    result = run_hook(workspace, "/etc/timeshift/timeshift.json")
    check("an empty marker does not approve anything", result.returncode == 2)

    # The instruction-file guard's marker must not authorise a backup write.
    (workspace / ".walk-approved").write_text("approved\n", encoding="utf-8")
    result = run_hook(workspace, "/mnt/backup/timeshift/x")
    check("an instruction-file approval does not carry to backups", result.returncode == 2)

if failures:
    print(f"\n{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("\nall cases passed")
