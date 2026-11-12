#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/test-scratch-directory-whose-earlier-killed-runs-leftovers-are-removed-first-common.py.

A run killed with SIGKILL leaves its scratch directory; the next run of the
same test removes it once it has been unchanged long enough, and keeps every
directory it must not touch.

Run: python3 nc-systems/general-tools/tests/test-scratch-directory-whose-earlier-killed-runs-leftovers-are-removed-first-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = (REPOSITORY_ROOT / "nc-systems" / "general-tools"
               / "test-scratch-directory-whose-earlier-killed-runs-leftovers-are-removed-first-common.py")
_spec = importlib.util.spec_from_file_location(
    "test_scratch_directory_whose_earlier_killed_runs_leftovers_are_removed_first_common", MODULE_PATH)
common = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(common)

PREFIX = "scratch-directory-common-test-"
LATER = time.time() + common.LEFT_BY_A_KILLED_RUN_AFTER_UNCHANGED_SECONDS + 60
failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


# A run that makes its scratch directory, writes in it, and is killed before its finally can run.
KILLED_RUN = f"""
import importlib.util, os, signal, shutil, sys
spec = importlib.util.spec_from_file_location("common", {str(MODULE_PATH)!r})
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
root = common.scratch_directory_after_removing_ones_killed_runs_left({PREFIX!r}, temp_dir=sys.argv[1])
try:
    (root / "case-1").mkdir()
    (root / "case-1" / "file").write_text("x")
    print(root, flush=True)
    os.kill(os.getpid(), signal.SIGKILL)
finally:
    shutil.rmtree(root, ignore_errors=True)
"""

temp_dir = Path(tempfile.mkdtemp(prefix="scratch-directory-common-test-parent-")).resolve()
try:
    run = subprocess.run([sys.executable, "-c", KILLED_RUN, str(temp_dir)],
                         capture_output=True, text=True, timeout=60, check=False)
    left = Path(run.stdout.strip())
    check("a run killed with SIGKILL leaves its scratch directory behind",
          run.returncode == -signal.SIGKILL and left.is_dir(),
          (run.returncode, run.stdout, run.stderr))

    removed, kept = common.remove_scratch_directories_killed_runs_left(PREFIX, temp_dir=temp_dir)
    check("the next run keeps a directory changed within the last hours, which a running run may own",
          left.is_dir() and removed == [] and kept == [], (removed, kept))

    other_name = temp_dir / "another-test-abcdefgh"
    other_name.mkdir()
    longer_name = temp_dir / f"{PREFIX}abcdefgh-not-mkdtemp"
    longer_name.mkdir()
    target_of_link = temp_dir / "target-of-link"
    target_of_link.mkdir()
    link = temp_dir / f"{PREFIX}linklink"
    link.symlink_to(target_of_link)
    removed, kept = common.remove_scratch_directories_killed_runs_left(PREFIX, temp_dir=temp_dir, now=LATER)
    check("once unchanged long enough, the killed run's directory is removed",
          not left.exists() and removed == [left], (removed, kept))
    check("a directory of another prefix, a longer name and a link are kept, and none is reported",
          other_name.is_dir() and longer_name.is_dir() and link.is_symlink() and target_of_link.is_dir()
          and kept == [],
          (sorted(path.name for path in temp_dir.iterdir()), kept))

    stuck = temp_dir / f"{PREFIX}stuck123"
    (stuck / "inner").mkdir(parents=True)
    (stuck / "inner" / "file").write_text("x")
    long_ago = time.time() - common.LEFT_BY_A_KILLED_RUN_AFTER_UNCHANGED_SECONDS - 60
    after_stuck = temp_dir / f"{PREFIX}zzzzzzzz"
    after_stuck.mkdir()
    for path in (stuck / "inner" / "file", stuck / "inner", stuck, after_stuck):
        os.utime(path, (long_ago, long_ago))
    os.chmod(stuck / "inner", 0o500)
    try:
        removed, kept = common.remove_scratch_directories_killed_runs_left(PREFIX, temp_dir=temp_dir)
        check("a directory that cannot be removed is kept and named, with the reason",
              stuck.is_dir() and [path for path, _reason in kept] == [stuck]
              and "Permission denied" in kept[0][1],
              kept)
        check("the directories after one that cannot be removed are still removed",
              not after_stuck.exists() and removed == [after_stuck], removed)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            fresh = common.scratch_directory_after_removing_ones_killed_runs_left(PREFIX, temp_dir=temp_dir)
        check("the run that could not remove it still gets its scratch directory",
              fresh.is_dir() and fresh.name.startswith(PREFIX), fresh)
        check("the run that could not remove it says so on standard error",
              str(stuck) in stderr.getvalue() and "goes on" in stderr.getvalue(), stderr.getvalue())
    finally:
        os.chmod(stuck / "inner", 0o700)
    shutil.rmtree(stuck)

    old_top_fresh_inside = temp_dir / f"{PREFIX}freshins"
    old_top_fresh_inside.mkdir()
    (old_top_fresh_inside / "file").write_text("x")
    os.utime(old_top_fresh_inside, (long_ago, long_ago))
    removed, kept = common.remove_scratch_directories_killed_runs_left(PREFIX, temp_dir=temp_dir)
    check("a directory whose own time is old but which holds a file changed lately is kept",
          old_top_fresh_inside.is_dir() and removed == [] and kept == [], (removed, kept))
    shutil.rmtree(old_top_fresh_inside)

    other_owners = temp_dir / f"{PREFIX}otherown"
    other_owners.mkdir()
    os.utime(other_owners, (long_ago, long_ago))
    real_getuid = os.getuid
    common.os.getuid = lambda: real_getuid() + 1
    try:
        removed, kept = common.remove_scratch_directories_killed_runs_left(PREFIX, temp_dir=temp_dir)
    finally:
        common.os.getuid = real_getuid
    check("a directory of another account is kept",
          other_owners.is_dir() and removed == [] and kept == [], (removed, kept))
    other_owners.rmdir()

    fallback_temp_dir = temp_dir / "fallback-temp-dir"
    fallback_temp_dir.mkdir()
    left_in_tmp = temp_dir / f"{PREFIX}intmp123"
    left_in_fallback = fallback_temp_dir / f"{PREFIX}infallbk"
    for path in (left_in_tmp, left_in_fallback):
        path.mkdir()
        os.utime(path, (long_ago, long_ago))
    real_tmp = common.TMP
    common.tempfile = type("TempfileStandIn", (), {"gettempdir": staticmethod(lambda: str(fallback_temp_dir))})
    common.TMP = temp_dir
    try:
        removed, kept = common.remove_scratch_directories_killed_runs_left(PREFIX)
    finally:
        common.tempfile, common.TMP = tempfile, real_tmp
    check("given no temp directory, a sweep whose system temp directory fell back from /tmp sweeps /tmp too",
          sorted(removed) == sorted([left_in_tmp, left_in_fallback]) and kept == [], (removed, kept))
    shutil.rmtree(fallback_temp_dir)

    vanishing = temp_dir / f"{PREFIX}aaaaaaaa"
    staying = temp_dir / f"{PREFIX}bbbbbbbb"
    for path in (vanishing, staying):
        path.mkdir()
        os.utime(path, (long_ago, long_ago))
    real_rmtree = common.shutil.rmtree

    def rmtree_as_if_another_run_removed_it_first(path):
        real_rmtree(path)
        if Path(path) == vanishing:
            raise FileNotFoundError(2, "No such file or directory", str(path))
    common.shutil = type("ShutilStandIn", (), {"rmtree": staticmethod(rmtree_as_if_another_run_removed_it_first)})
    try:
        removed, kept = common.remove_scratch_directories_killed_runs_left(PREFIX, temp_dir=temp_dir)
    finally:
        common.shutil = shutil
    check("a directory another run removed first is neither counted nor reported, and the next is still removed",
          kept == [] and removed == [staying] and not staying.exists(), (removed, kept))

    # Literal ages, not ones derived from the module's constant, so a change to the three hours fails here.
    unchanged_under_three_hours = temp_dir / f"{PREFIX}under3hr"
    unchanged_over_three_hours = temp_dir / f"{PREFIX}over3hrs"
    now = time.time()
    for path, age in ((unchanged_under_three_hours, 10700), (unchanged_over_three_hours, 10900)):
        path.mkdir()
        os.utime(path, (now - age, now - age))
    removed, kept = common.remove_scratch_directories_killed_runs_left(PREFIX, temp_dir=temp_dir, now=now)
    check("a directory unchanged for 10700 seconds is kept and one unchanged for 10900 seconds is removed",
          unchanged_under_three_hours.is_dir() and not unchanged_over_three_hours.exists()
          and removed == [unchanged_over_three_hours] and kept == [], (removed, kept))
finally:
    shutil.rmtree(temp_dir, ignore_errors=True)

sys.exit(1 if failures else 0)
