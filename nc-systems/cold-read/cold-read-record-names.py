#!/usr/bin/env python3
"""Define shared cold-read-record names and paths."""

import datetime
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
# Records are temporary checkout logs for shipping to ned-box; never commit them.
RECORDS_DIR = REPO_ROOT / "cold-read-records"
FROZEN_TARGET_DIRECTORY_NAME = "target"


def frozen_target_path(
    target: pathlib.Path, record_dir: pathlib.Path,
) -> pathlib.Path:
    """Return the frozen path under record_dir/target, preserving repository or outside absolute structure."""
    # Resolve symlinks before making paths relative so /tmp and /private/tmp identify the same target.
    resolved = target.resolve()
    try:
        relative = resolved.relative_to(REPO_ROOT)
    except ValueError:
        relative = pathlib.Path(*resolved.parts[1:])
    return record_dir / FROZEN_TARGET_DIRECTORY_NAME / relative


def record_name_for_target(target: pathlib.Path) -> str:
    """Return the target stem, qualifying SKILL with its parent directory name."""
    if target.stem == "SKILL" and target.parent.name:
        return f"SKILL-{target.parent.name}"
    return target.stem


def record_directory_name_for_target(
    target: pathlib.Path, now: datetime.datetime,
) -> str:
    return f"{record_name_for_target(target)}-{now.strftime('%Y-%m-%d')}"


def fresh_record_directory(base: pathlib.Path) -> pathlib.Path:
    """Return an unused base or numbered suffix without creating the directory."""
    # Each read needs its own directory so a same-day rerun cannot overwrite earlier reports.
    record_directory = base
    suffix = 2
    while record_directory.exists():
        record_directory = base.with_name(f"{base.name}-{suffix}")
        suffix += 1
    return record_directory
