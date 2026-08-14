#!/usr/bin/env python3
"""Report whether this machine's backups are actually running (user-walked 2026-08-14).

Timeshift fails silently. If the drive unmounts, cron breaks, or the disk dies,
nothing announces it — snapshots simply stop, and the loss surfaces when a
restore is attempted. This check makes that visible in the status line, which is
where the user already looks.

Read-only by construction: it stats directories and reads two small JSON files.
CLAUDE.md forbids agents writing backup state, and a health check that could
corrupt what it measures would be a poor advertisement for the rule.

WHY THE LOG DIRECTORY AND NOT JUST SNAPSHOT AGE. Timeshift is time-driven, not
content-driven: `--check` means "create a snapshot if one is scheduled", so it
never skips because nothing changed — it skips because the level is not yet due.
A manual snapshot therefore resets the hourly clock, and a perfectly healthy
machine can go nearly two hours with no new hourly snapshot. Observed 2026-08-14:
an on-demand snapshot at 11:35 took the H, W and M tags, so the 12:00 run
correctly created nothing. Snapshot age alone would have cried wolf.

Timeshift writes a log for EVERY run, including runs that create nothing and runs
that fail, so the log directory answers "did the scheduler fire" while snapshot
age answers "did the run succeed". Checking both separates a dead scheduler from
a scheduler that is alive but failing — different problems, different fixes.

Usage:
  python3 scripts/backup-health-check.py                 full diagnosis, always prints
  python3 scripts/backup-health-check.py --status-line   one terse line, SILENT when healthy

Exit code is 0 when healthy and 1 when any check fails, so a caller can branch on
it without parsing the text.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Overridable so the test can build a fake layout in a temporary directory.
BACKUP_MOUNT = Path(os.environ.get("NEDSCHORUS_BACKUP_MOUNT", "/mnt/backup"))
TIMESHIFT_LOG_DIRECTORY = Path(
    os.environ.get("NEDSCHORUS_TIMESHIFT_LOG_DIRECTORY", "/var/log/timeshift"))
TIMESHIFT_SNAPSHOT_DIRECTORY = Path(
    os.environ.get("NEDSCHORUS_TIMESHIFT_SNAPSHOT_DIRECTORY",
                   "/mnt/backup/timeshift/snapshots"))

# Hourly snapshots run at :00. Ninety minutes is one interval plus half again,
# so a single late or slow run does not raise an alarm but a stopped scheduler
# does within two cycles.
MAXIMUM_LOG_AGE_SECONDS = 90 * 60

# Three hours exceeds the hourly interval by enough to absorb the legitimate
# skip described above, where a manual snapshot has taken the H tag.
MAXIMUM_SNAPSHOT_AGE_SECONDS = 3 * 60 * 60


def format_age(seconds: float) -> str:
    """Compact and unambiguous: 47m, 4h12m, 3d4h."""
    seconds = max(0, int(seconds))
    minutes, hours = seconds // 60, seconds // 3600
    if hours < 1:
        return f"{minutes}m"
    if hours < 24:
        return f"{hours}h{minutes - hours * 60:02d}m"
    days = hours // 24
    return f"{days}d{hours - days * 24}h"


def is_mounted(path: Path) -> bool:
    """A separate device is mounted there, rather than an empty stand-in directory.

    os.path.ismount is the right test: when the drive is absent, /mnt/backup
    still exists as an ordinary directory on the root filesystem, so existence
    proves nothing.
    """
    try:
        return os.path.ismount(path)
    except OSError:
        return False


def newest_run_log_age(log_directory: Path):
    """Seconds since Timeshift last ran at all, or None if it has never run here."""
    try:
        stamps = [entry.stat().st_mtime for entry in log_directory.iterdir()
                  if entry.is_file()]
    except OSError:
        return None
    if not stamps:
        return None
    return time.time() - max(stamps)


def newest_scheduled_snapshot_age(snapshot_directory: Path):
    """Seconds since the newest *scheduled* snapshot, or None if there is none.

    On-demand snapshots are excluded unless they also carry a scheduled tag,
    because a person taking one by hand says nothing about whether the schedule
    is working — which is the entire question here. Directory names sort
    chronologically, so the newest scheduled snapshot is usually the first or
    second entry examined.
    """
    try:
        entries = sorted((entry for entry in snapshot_directory.iterdir()
                          if entry.is_dir()), reverse=True)
    except OSError:
        return None
    for entry in entries:
        try:
            info = json.loads((entry / "info.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        tags = str(info.get("tags", "")).split()
        if not any(tag in ("hourly", "daily", "weekly", "monthly") for tag in tags):
            continue
        try:
            created = float(info.get("created", 0))
        except (TypeError, ValueError):
            continue
        if created:
            return time.time() - created
    return None


def diagnose():
    """Return (headline, detail_lines). headline is None when everything is healthy."""
    detail = []

    if not is_mounted(BACKUP_MOUNT):
        detail.append(f"{BACKUP_MOUNT} is not a mount point — the backup drive is absent.")
        snapshot_age = newest_scheduled_snapshot_age(TIMESHIFT_SNAPSHOT_DIRECTORY)
        age_text = format_age(snapshot_age) if snapshot_age is not None else "unknown"
        detail.append(f"Last scheduled snapshot: {age_text} ago.")
        detail.append("Check the drive's connection, then remount it.")
        return f"BACKUP DRIVE GONE {age_text}", detail

    log_age = newest_run_log_age(TIMESHIFT_LOG_DIRECTORY)
    if log_age is None or log_age > MAXIMUM_LOG_AGE_SECONDS:
        age_text = format_age(log_age) if log_age is not None else "never"
        detail.append(f"Timeshift last ran {age_text} ago; it should run hourly.")
        detail.append("The scheduler is not firing. Check /etc/cron.d/timeshift-hourly "
                      "and whether cron is running.")
        return f"BACKUP STALLED {age_text}", detail

    snapshot_age = newest_scheduled_snapshot_age(TIMESHIFT_SNAPSHOT_DIRECTORY)
    if snapshot_age is None or snapshot_age > MAXIMUM_SNAPSHOT_AGE_SECONDS:
        age_text = format_age(snapshot_age) if snapshot_age is not None else "never"
        detail.append(f"Timeshift is running (last run {format_age(log_age)} ago) but the "
                      f"newest scheduled snapshot is {age_text} old.")
        detail.append(f"Runs are failing rather than not happening. Read the newest log in "
                      f"{TIMESHIFT_LOG_DIRECTORY} for the reason.")
        return f"BACKUP FAILING {age_text}", detail

    detail.append(f"Drive mounted at {BACKUP_MOUNT}.")
    detail.append(f"Timeshift last ran {format_age(log_age)} ago.")
    detail.append(f"Newest scheduled snapshot {format_age(snapshot_age)} ago.")
    return None, detail


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--status-line", action="store_true",
                        help="print one terse line, and nothing at all when healthy")
    arguments = parser.parse_args()

    headline, detail = diagnose()

    if arguments.status_line:
        if headline:
            print(f"⚠ {headline}")
        return 1 if headline else 0

    if headline:
        print(f"⚠ {headline}")
    else:
        print("Backups healthy.")
    for line in detail:
        print(f"  {line}")
    return 1 if headline else 0


if __name__ == "__main__":
    sys.exit(main())
