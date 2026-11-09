#!/usr/bin/env python3
"""Make a test's scratch directory in the system temp directory, first removing the ones killed runs left.

A test that removes its scratch directory in a `finally` or a `with` block
cannot do so when it is killed with SIGKILL, which is what a caller's timeout
does to a test run directly rather than under scripts/run-all-test-suites.py,
such as an agent's shell command that runs past its time limit, and each kill
leaves a directory that can hold thousands of files in a /tmp of limited inodes.
So each run, before making its own directory, removes the ones earlier
runs of the same test left: a directory of this account whose name is the
test's prefix followed by mkdtemp's eight-character suffix, and under which
nothing has changed for LEFT_BY_A_KILLED_RUN_AFTER_UNCHANGED_SECONDS, longer
than any run of a test lasts, so a directory another run still writes in is kept.
Given no temp directory, it sweeps /tmp as well as the system temp directory,
because Python falls back to /var/tmp when /tmp has no free inodes, which is
when the leftovers in /tmp most need removing.

It does not remove a directory named otherwise, such as one a killed run of a
test that does not use this module left, nor one an earlier run on another
machine left. A directory it cannot read or remove is kept and named on
standard error, with the reason, and the run goes on in a new scratch
directory without failing: the failure costs only disk space, which the test's
next run tries again to recover.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "test_scratch_directory_whose_earlier_killed_runs_leftovers_are_removed_first_common", <path>)
"""

import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

LEFT_BY_A_KILLED_RUN_AFTER_UNCHANGED_SECONDS = 3 * 60 * 60
MKDTEMP_SUFFIX_SHAPE = r"[a-z0-9_]{8}"
TMP = Path("/tmp")


def newest_modification_time_in_tree(directory):
    """The newest modification time of the directory and everything under it."""
    newest = directory.lstat().st_mtime

    def fail(error):
        raise error
    for parent, subdirectories, files in os.walk(directory, onerror=fail):
        for name in subdirectories + files:
            newest = max(newest, (Path(parent) / name).lstat().st_mtime)
    return newest


def remove_scratch_directories_killed_runs_left(prefix, temp_dir=None, now=None,
                                                unchanged_seconds=LEFT_BY_A_KILLED_RUN_AFTER_UNCHANGED_SECONDS):
    """Remove each directory named prefix + mkdtemp's suffix, of this account, unchanged for
    unchanged_seconds, in temp_dir, or else in the system temp directory and /tmp;
    return (removed, kept), kept being (path, reason) for each one that could not be
    read or removed."""
    if temp_dir is None:
        temp_dirs = list(dict.fromkeys(path for path in (Path(tempfile.gettempdir()), TMP) if path.is_dir()))
    else:
        temp_dirs = [Path(temp_dir)]
    now = time.time() if now is None else now
    shape = re.compile(re.escape(prefix) + MKDTEMP_SUFFIX_SHAPE)
    removed, kept = [], []
    candidates = [directory for parent in temp_dirs
                  for directory in sorted(parent.glob(f"{glob_escape(prefix)}*"))]
    for directory in candidates:
        try:
            if (not shape.fullmatch(directory.name) or directory.is_symlink()
                    or not directory.is_dir() or directory.lstat().st_uid != os.getuid()):
                continue
            if now - newest_modification_time_in_tree(directory) < unchanged_seconds:
                continue
            shutil.rmtree(directory)
        except FileNotFoundError:
            continue
        except OSError as error:
            kept.append((directory, str(error)))
            continue
        removed.append(directory)
    return removed, kept


def glob_escape(text):
    return re.sub(r"([*?\[])", r"[\1]", text)


def scratch_directory_after_removing_ones_killed_runs_left(prefix, temp_dir=None):
    """Remove what killed runs of this test left, then make and return a new scratch directory."""
    _removed, kept = remove_scratch_directories_killed_runs_left(prefix, temp_dir=temp_dir)
    for directory, reason in kept:
        print(f"{prefix}: could not remove {directory}, which an earlier killed run of this test "
              f"left ({reason}). This notice is for information only and needs no action: the failed "
              f"removal does not fail the test, whose result depends only on its own checks. The test goes "
              f"on in a new scratch directory, and the test's next run tries again to remove the leftover "
              f"directory.", file=sys.stderr)
    return Path(tempfile.mkdtemp(prefix=prefix, dir=temp_dir)).resolve()
