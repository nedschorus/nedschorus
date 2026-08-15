#!/usr/bin/env python3
"""Tests for backup-health-check.py.

Run: python3 scripts/backup-health-check-test.py
Prints one line per case and exits non-zero if any case fails.

Every case builds a fake Timeshift layout in a temporary directory and points
the checker at it with the three environment overrides, so nothing here reads or
touches the real backup drive.

Note the mount check: the checker uses os.path.ismount, and a temporary
directory is never a mount point. So the "drive gone" state is the natural
default here, and the healthy cases have to override is_mounted — which they do
by running the checker with a stub injected ahead of it on the import path.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("backup-health-check.py")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def build_layout(root: Path, log_age_seconds=None, snapshot_age_seconds=None,
                 snapshot_tags="hourly"):
    """Create log and snapshot directories aged as requested. None means absent.

    Cleared first: cases share one temporary root, and a leftover log from the
    previous case would make an "absent" state look present.
    """
    log_directory = root / "log"
    snapshot_directory = root / "snapshots"
    shutil.rmtree(log_directory, ignore_errors=True)
    shutil.rmtree(snapshot_directory, ignore_errors=True)
    log_directory.mkdir()
    snapshot_directory.mkdir()

    if log_age_seconds is not None:
        log_file = log_directory / "2026-08-14_12-00-01_backup.log"
        log_file.write_text("ran\n", encoding="utf-8")
        stamp = time.time() - log_age_seconds
        os.utime(log_file, (stamp, stamp))

    if snapshot_age_seconds is not None:
        created = int(time.time() - snapshot_age_seconds)
        entry = snapshot_directory / "2026-08-14_12-00-01"
        entry.mkdir(exist_ok=True)
        (entry / "info.json").write_text(
            json.dumps({"created": str(created), "tags": snapshot_tags}), encoding="utf-8")

    return log_directory, snapshot_directory


def run_check(root: Path, mounted: bool, status_line=True):
    log_directory, snapshot_directory = root / "log", root / "snapshots"
    environment = dict(
        os.environ,
        NEDSCHORUS_BACKUP_MOUNT=str(root / "mount"),
        NEDSCHORUS_TIMESHIFT_LOG_DIRECTORY=str(log_directory),
        NEDSCHORUS_TIMESHIFT_SNAPSHOT_DIRECTORY=str(snapshot_directory),
    )
    (root / "mount").mkdir(exist_ok=True)

    # A temporary directory is never a real mount point, so a healthy case needs
    # os.path.ismount stubbed. Doing it through a sitecustomize module keeps the
    # checker itself free of test-only switches.
    if mounted:
        (root / "sitecustomize.py").write_text(
            "import os.path\nos.path.ismount = lambda path: True\n", encoding="utf-8")
        environment["PYTHONPATH"] = str(root)

    command = [sys.executable, str(SCRIPT_PATH)]
    if status_line:
        command.append("--status-line")
    return subprocess.run(command, capture_output=True, text=True, check=False,
                          env=environment)


with tempfile.TemporaryDirectory() as temporary_directory:
    root = Path(temporary_directory)

    # Healthy: mounted, ran recently, recent scheduled snapshot.
    build_layout(root, log_age_seconds=300, snapshot_age_seconds=1800)
    result = run_check(root, mounted=True)
    check("healthy prints nothing in status-line mode", result.stdout.strip() == "",
          repr(result.stdout))
    check("healthy exits 0", result.returncode == 0, str(result.returncode))

    result = run_check(root, mounted=True, status_line=False)
    check("healthy says so in full mode", "Backups healthy" in result.stdout, result.stdout)

    # Drive absent outranks everything else.
    result = run_check(root, mounted=False)
    check("an absent drive is reported", "BACKUP DRIVE GONE" in result.stdout, result.stdout)
    check("an absent drive exits 1", result.returncode == 1)

    # Scheduler dead: no run for four hours, though snapshots on disk look fine.
    build_layout(root, log_age_seconds=4 * 3600, snapshot_age_seconds=1800)
    result = run_check(root, mounted=True)
    check("a dead scheduler is reported as STALLED", "BACKUP STALLED" in result.stdout,
          result.stdout)
    check("STALLED carries the age", "4h00m" in result.stdout, result.stdout)

    # Running but not producing: fresh log, stale snapshot.
    build_layout(root, log_age_seconds=300, snapshot_age_seconds=6 * 3600)
    result = run_check(root, mounted=True)
    check("running-but-failing is reported as FAILING", "BACKUP FAILING" in result.stdout,
          result.stdout)
    check("FAILING carries the age", "6h00m" in result.stdout, result.stdout)

    # The distinction that motivated the design: an on-demand snapshot is not
    # evidence that the schedule works, so it must not mask a stalled schedule.
    build_layout(root, log_age_seconds=300, snapshot_age_seconds=60,
                 snapshot_tags="ondemand")
    result = run_check(root, mounted=True)
    check("a fresh on-demand-only snapshot does not count as scheduled",
          "BACKUP FAILING" in result.stdout, result.stdout)

    # ...but one that also carries a scheduled tag does, which is the real
    # 2026-08-14 case where an on-demand snapshot took the H, W and M tags.
    build_layout(root, log_age_seconds=300, snapshot_age_seconds=60,
                 snapshot_tags="ondemand hourly weekly monthly")
    result = run_check(root, mounted=True)
    check("an on-demand snapshot tagged hourly does count", result.stdout.strip() == "",
          result.stdout)

    # Nothing has ever run here.
    build_layout(root, log_age_seconds=None, snapshot_age_seconds=None)
    result = run_check(root, mounted=True)
    check("a machine that never ran Timeshift is reported", "BACKUP STALLED" in result.stdout,
          result.stdout)
    check("never-run says 'never' rather than an age", "never" in result.stdout, result.stdout)

# Age formatting is the part the user reads under stress, so pin it directly.
# Loaded by path because the script's filename is hyphenated and not importable.
specification = importlib.util.spec_from_file_location("backup_health_check", SCRIPT_PATH)
module = importlib.util.module_from_spec(specification)
specification.loader.exec_module(module)

check("format_age minutes", module.format_age(47 * 60) == "47m", module.format_age(47 * 60))
check("format_age hours and minutes", module.format_age(4 * 3600 + 12 * 60) == "4h12m",
      module.format_age(4 * 3600 + 12 * 60))
check("format_age pads minutes", module.format_age(4 * 3600 + 5 * 60) == "4h05m",
      module.format_age(4 * 3600 + 5 * 60))
check("format_age days", module.format_age(3 * 86400 + 4 * 3600) == "3d4h",
      module.format_age(3 * 86400 + 4 * 3600))

if failures:
    print(f"\n{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("\nall cases passed")
