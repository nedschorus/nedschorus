#!/usr/bin/env python3
"""Tests for nc-systems/handoff/agent-seat-terminal-captures-older-than-seven-days-delete.py: what
is deleted and what is kept, --dry-run, which directories each machine deletes from, and each
failure that is reported while the run goes on. Every directory here is a scratch one.

Run: python3 nc-systems/handoff/tests/agent-seat-terminal-captures-older-than-seven-days-delete-test.py
(exit 0 = all passed)
"""

import contextlib
import importlib.util
import io
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

PROGRAM_PATH = (Path(__file__).resolve().parents[1]
                / "agent-seat-terminal-captures-older-than-seven-days-delete.py")
_spec = importlib.util.spec_from_file_location("terminal_captures_delete", PROGRAM_PATH)
deletion = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(deletion)

failures = []
NOW = 2_000_000_000.0
DAY = 86_400


def check(case_name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {case_name}")
    if not condition:
        failures.append(case_name)
        if detail:
            print(f"      {detail}")


def capture_file(directory: Path, seat: str, name: str, age_days: float) -> Path:
    path = directory / seat / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("captured output\n", encoding="utf-8")
    os.utime(path, (NOW - age_days * DAY, NOW - age_days * DAY))
    return path


def run(arguments):
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        exit_code = deletion.main(arguments, now=NOW)
    return exit_code, printed.getvalue()


with tempfile.TemporaryDirectory() as scratch_name:
    scratch = Path(scratch_name)

    # -- what is deleted and what is kept ---------------------------------------------------------
    store = scratch / "store"
    old = capture_file(store, "MD-skills", "20261020T000000Z-MD-skills-terminal-capture.log", 8)
    # Named for a start long ago but written today: a supervisor still running.
    still_written = capture_file(store, "MD-skills", "20260901T000000Z-MD-skills-terminal-capture.log", 0.1)
    only_old = capture_file(store, "retired-seat", "20261001T000000Z-retired-seat-terminal-capture.log", 30)
    just_inside = capture_file(store, "merge-lane-2", "20261029T000000Z-merge-lane-2-terminal-capture.log", 6.9)
    stray_top_level_file = store / "README.txt"
    stray_top_level_file.write_text("not a capture\n", encoding="utf-8")
    os.utime(stray_top_level_file, (NOW - 40 * DAY, NOW - 40 * DAY))

    exit_code, output = run(["--dry-run", "--captures-directory", str(store)])
    check("--dry-run names each file it would delete, deletes nothing, and exits 0",
          exit_code == 0 and f"would delete {old}\n" in output and f"would delete {only_old}\n" in output
          and old.exists() and only_old.exists() and "would delete 2 capture(s)" in output, output)

    exit_code, output = run(["--captures-directory", str(store)])
    check("a file last written more than seven days ago is deleted and named, exit 0",
          exit_code == 0 and not old.exists() and not only_old.exists()
          and f"deleted {old}\n" in output and f"deleted {only_old}\n" in output
          and "deleted 2 capture(s) older than 7 days from" in output, output)
    check("a file last written within seven days is kept, however old the start time in its name",
          still_written.exists() and just_inside.exists())
    check("an agent-seat directory the run emptied is removed; one still holding a file is kept",
          not (store / "retired-seat").exists() and (store / "MD-skills").is_dir())
    check("a file directly in the captures directory, not in an agent-seat's directory, is left alone",
          stray_top_level_file.exists())

    exit_code, output = run(["--captures-directory", str(scratch / "never-made")])
    check("a captures directory that does not exist is not a failure: exit 0, nothing deleted",
          exit_code == 0 and "deleted 0 capture(s)" in output and "FAILED" not in output, output)

    # -- which directories each machine deletes from ----------------------------------------------
    fake_store = scratch / "fake-log-store" / "agent-session-files-by-machine"
    for machine in ("mac", "ned-box"):
        (fake_store / machine / "agent-seat-terminal-captures").mkdir(parents=True)
    (fake_store / "recovered").mkdir()
    environment_without_override = {
        key: value for key, value in os.environ.items()
        if key != deletion.captures.AGENT_SEAT_TERMINAL_CAPTURES_DESTINATION_ENVIRONMENT_VARIABLE}
    with mock.patch.object(deletion.captures, "LOG_STORE_AGENT_SESSION_FILES_BY_MACHINE_DIRECTORY", fake_store), \
            mock.patch.dict(os.environ, environment_without_override, clear=True):
        on_ned_box = deletion.agent_seat_terminal_captures_directories_this_machine_deletes_old_captures_from_find("ned-box")
        on_the_mac = deletion.agent_seat_terminal_captures_directories_this_machine_deletes_old_captures_from_find("els-MacBook-Pro")
    check("on ned-box a run deletes from every machine's copy in the log-store, the Mac's included, "
          "since the transcript mirror never deletes",
          on_ned_box == [fake_store / "mac" / "agent-seat-terminal-captures",
                         fake_store / "ned-box" / "agent-seat-terminal-captures"], str(on_ned_box))
    check("on the Mac a run deletes from the Mac's own ~/.claude/agent-seat-terminal-captures",
          on_the_mac == [Path.home() / ".claude" / "agent-seat-terminal-captures"], str(on_the_mac))

    # -- failures are named, and the run goes on --------------------------------------------------
    locked_store = scratch / "locked-store"
    undeletable = capture_file(locked_store, "a-locked-seat", "20261001T000000Z-a-locked-seat-terminal-capture.log", 30)
    deletable = capture_file(locked_store, "an-open-seat", "20261001T000000Z-an-open-seat-terminal-capture.log", 30)
    # Sorted first, so the agent-seat directories after it show the run went on past it.
    unlistable_seat = locked_store / "a-0-unlistable-seat"
    unlistable_seat.mkdir()
    (locked_store / "a-locked-seat").chmod(0o555)
    unlistable_seat.chmod(0o000)
    try:
        exit_code, output = run(["--captures-directory", str(locked_store)])
    finally:
        (locked_store / "a-locked-seat").chmod(0o755)
        unlistable_seat.chmod(0o755)
    check("a file that cannot be deleted is a FAILED line naming it, with what to do; the run goes on "
          "with the other files and exits 1",
          exit_code == 1 and f"FAILED: could not delete {undeletable} (" in output
          and deletion.FAILED_PATH_KEPT_UNTIL_A_RUN_CAN_DELETE_IT_LINE in output
          and undeletable.exists() and not deletable.exists() and "; 2 FAILED" in output, output)
    check("an agent-seat directory that cannot be listed is a FAILED line naming it",
          f"FAILED: could not list {unlistable_seat} (" in output, output)

    unlistable_store = scratch / "unlistable-store"
    unlistable_store.mkdir()
    unlistable_store.chmod(0o000)
    try:
        exit_code, output = run(["--captures-directory", str(unlistable_store),
                                 "--captures-directory", str(store)])
    finally:
        unlistable_store.chmod(0o755)
    check("a captures directory that cannot be listed is a FAILED line, the next directory is still "
          "done, exit 1",
          exit_code == 1 and f"FAILED: could not list {unlistable_store} (" in output
          and str(store) in output.splitlines()[-1] and output.splitlines()[-1].endswith("; 1 FAILED"),
          output)

    emptied_store = scratch / "emptied-store"
    capture_file(emptied_store, "a-seat", "20261001T000000Z-a-seat-terminal-capture.log", 30)
    with mock.patch.object(Path, "rmdir", side_effect=OSError("injected: Device or resource busy")):
        exit_code, output = run(["--captures-directory", str(emptied_store)])
    check("an emptied agent-seat directory that cannot be removed is a FAILED line naming it, exit 1",
          exit_code == 1
          and f"FAILED: could not remove the emptied directory {emptied_store / 'a-seat'} (" in output
          and output.splitlines()[-1].endswith("; 1 FAILED"),
          output)

print()
if failures:
    print(f"{len(failures)} case(s) FAILED:")
    for name in failures:
        print(f"  - {name}")
    sys.exit(1)
print("all cases passed")
