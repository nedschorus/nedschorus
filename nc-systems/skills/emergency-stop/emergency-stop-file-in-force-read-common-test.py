#!/usr/bin/env python3
"""Tests for emergency-stop-file-in-force-read-common.py: which stop file is in
force, what counts as a lift line, and the folder on each machine.

Every case builds its own folder under a temporary directory; none touches the
log-store. Run: python3 nc-systems/skills/emergency-stop/emergency-stop-file-in-force-read-common-test.py
Prints one line per case and exits non-zero if any case fails."""

import importlib.util
import os
import sys
import tempfile
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "emergency_stop_file_in_force_read_common", Path(__file__).with_name("emergency-stop-file-in-force-read-common.py"))
common = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(common)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def main():
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        folder = root / "emergency-stop"

        state = common.read_state(folder)
        check("missing folder under a reachable log-store: no stop", isinstance(state, common.NoStop), state)

        state = common.read_state(root / "gone" / "emergency-stop")
        check("missing log-store: folder unreachable", isinstance(state, common.FolderUnreachable), state)

        folder.mkdir()
        (folder / "2026-10-30T01-00-00Z-repair-brief.md").write_text("brief\n")
        (folder / "notes.md").write_text("x\n")
        state = common.read_state(folder)
        check("only non-stop files: no stop", isinstance(state, common.NoStop), state)

        older = folder / "2026-10-29T01-00-00Z.md"
        older.write_text("started\n#emergency_stop_lifted ok\n")
        newer = folder / "2026-10-30T01-00-00Z.md"
        newer.write_text("started\ncoordinating agent-seat: reboot-test\nwords: \"#emergency_stop_lifted\" quoted\n")
        state = common.read_state(folder)
        check("newest without a lift line is in force, brief ignored",
              isinstance(state, common.InForce) and state.path == newer, state)
        check("a lift tag inside a quote does not lift", isinstance(state, common.InForce), state)
        check("coordinating agent-seat read from the file",
              common.coordinating_agent_seat(state.text) == "reboot-test", state.text)
        check("last coordinating line wins",
              common.coordinating_agent_seat("coordinating agent-seat: a\ncoordinating agent-seat: b\n") == "b")

        newer.write_text(newer.read_text() + "#emergency_stop_lifted the user said lift it\n\n")
        state = common.read_state(folder)
        check("lift line as the last line lifts", isinstance(state, common.Lifted)
              and state.lift_line == "#emergency_stop_lifted the user said lift it", state)

        newer.write_bytes(b"\xff\xfe broken")
        state = common.read_state(folder)
        check("undecodable newest file is unreadable", isinstance(state, common.Unreadable), state)

        if os.geteuid() != 0:
            newer.write_text("started\n")
            folder.chmod(0o000)
            try:
                state = common.read_state(folder)
                check("folder that cannot be listed: unreachable", isinstance(state, common.FolderUnreachable), state)
            finally:
                folder.chmod(0o755)

    check("override variable wins",
          common.emergency_stop_folder({"NEDSCHORUS_EMERGENCY_STOP_FOLDER": "/x"}, "linux") == Path("/x"))
    check("ned-box folder", common.emergency_stop_folder({}, "linux")
          == Path("/home/nedlern/nedschorus-logs/emergency-stop"))
    check("Mac folder through the mount", common.emergency_stop_folder({}, "darwin")
          == Path("/Volumes/nedhome/nedschorus-logs/emergency-stop"))
    print(f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
