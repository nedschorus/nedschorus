#!/usr/bin/env python3
"""Tests for restart-live-seats-at-login.py (nedschorus#116), the selection step.

Every case runs against a throwaway handoff directory, with the boot time and
the current time passed in, so no case reads this machine's heartbeats or its
real boot time. The rule under test is the #116 design's
§ Ruled 2026-08-31 — the heartbeat answers "which seats were running", with
its 2026-09-02 amendments, the user's 2026-09-11 answer on state files that
cannot be read, and the 2026-09-11 amendment from the review of 8b15919.

Each state file's modification time is set explicitly, because the selector
reads it (a file written since boot has had a supervisor since boot): a file
left at the real time of the test run would be after BOOT_AT and read as
written since boot.

Run: python3 scripts/restart-live-seats-at-login-test.py
"""

import importlib.util
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("restart-live-seats-at-login.py")

_spec = importlib.util.spec_from_file_location("restart_live_seats_at_login", SCRIPT_PATH)
restart = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(restart)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


# The 2026-09-10 reboot's boot time, as `sysctl -n kern.boottime` reported it.
BOOT_AT = datetime.fromtimestamp(1789103232, timezone.utc)
NOW = BOOT_AT + timedelta(minutes=3)
STOP = BOOT_AT - timedelta(minutes=5)


def write_state(handoffs: Path, seat: str, stamp=None, raw=None, written_at=None):
    """One supervisor state file. stamp is a datetime written as last_poll_at
    the way stamp_heartbeat() writes it; raw replaces the whole file.
    written_at is the file's modification time: by default the stamp, since
    the supervisor writes the file as it stamps. A raw file has no stamp to
    default from, so it must say when it was written."""
    handoffs.mkdir(parents=True, exist_ok=True)
    path = handoffs / f"{seat}-supervisor-state.json"
    if raw is not None:
        path.write_text(raw, encoding="utf-8")
    else:
        path.write_text(json.dumps({
            "consumed_counter": 3, "session_id": f"{seat}-session",
            "generation": 3, "last_poll_at": stamp.isoformat()}, indent=2),
            encoding="utf-8")
    if written_at is None:
        if stamp is None:
            raise ValueError(f"{seat}: a raw state file needs written_at")
        written_at = stamp
    os.utime(path, (written_at.timestamp(), written_at.timestamp()))
    return path


def verdicts(handoffs: Path, boot_at=BOOT_AT, now=NOW):
    anchor, decisions = restart.select_seats_live_at_the_stop(handoffs, boot_at, now)
    return anchor, {seat: (verdict, reason) for seat, verdict, reason in decisions}


def run_main(arguments):
    """main() with this machine's boot time replaced by BOOT_AT and its clock
    by NOW; (exit code, stdout, stderr)."""
    printed, errors = io.StringIO(), io.StringIO()
    real_machine_boot_time, real_current_time = restart.machine_boot_time, restart.current_time
    try:
        restart.machine_boot_time = lambda: BOOT_AT
        restart.current_time = lambda: NOW
        with redirect_stdout(printed), redirect_stderr(errors):
            try:
                exit_code = restart.main(arguments)
            except SystemExit as stop_request:
                exit_code = stop_request.code
    finally:
        restart.machine_boot_time, restart.current_time = real_machine_boot_time, real_current_time
    return exit_code, printed.getvalue(), errors.getvalue()


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)

    check("the live-set window is twice the supervisor's heartbeat interval",
          restart.LIVE_SET_WINDOW_SECONDS
          == 2 * restart.supervisor.HEARTBEAT_INTERVAL_SECONDS == 20,
          restart.LIVE_SET_WINDOW_SECONDS)

    # The 2026-09-01 measurement the rule was ruled on: two live seats stamped
    # 8 seconds apart, and the rest days away. Shifted to stop five minutes
    # before this boot.
    handoffs = root / "measured-2026-09-01"
    write_state(handoffs, "MD-skills", STOP)
    write_state(handoffs, "merge-lane", STOP - timedelta(seconds=8))
    write_state(handoffs, "mac-prof", STOP - timedelta(days=3))
    write_state(handoffs, "git-infra", STOP - timedelta(days=4))
    write_state(handoffs, "fixer1", STOP - timedelta(days=10))
    write_state(handoffs, "repo-hygiene", STOP - timedelta(days=15))
    anchor, seen = verdicts(handoffs)
    check("the anchor is the newest heartbeat before boot",
          anchor == STOP, anchor)
    check("two live seats stamped 8 seconds apart are both restarted",
          seen["MD-skills"][0] == "restart" and seen["merge-lane"][0] == "restart",
          seen)
    check("seats stamped days before the stop are not restarted",
          all(seen[seat][0] == "not-running-at-the-stop"
              for seat in ("mac-prof", "git-infra", "fixer1", "repo-hygiene")),
          seen)
    check("a seat that was not running says how long before the stop it was stamped",
          "3d" in seen["mac-prof"][1], seen["mac-prof"])

    # The window's edges: 20 seconds behind the anchor is in, 21 is out.
    handoffs = root / "window-edges"
    write_state(handoffs, "anchor-seat", STOP)
    write_state(handoffs, "twenty-behind", STOP - timedelta(seconds=20))
    write_state(handoffs, "twenty-one-behind", STOP - timedelta(seconds=21))
    anchor, seen = verdicts(handoffs)
    check("a seat exactly 20 seconds behind the anchor is restarted",
          seen["twenty-behind"][0] == "restart", seen)
    check("a seat 21 seconds behind the anchor is not",
          seen["twenty-one-behind"][0] == "not-running-at-the-stop", seen)

    # Ruled 2026-09-02: an anchor long before boot asks rather than acts.
    handoffs = root / "old-anchor"
    old_stop = BOOT_AT - timedelta(days=3)
    write_state(handoffs, "mac-prof", old_stop)
    write_state(handoffs, "beside-mac-prof", old_stop - timedelta(seconds=5))
    write_state(handoffs, "long-gone", old_stop - timedelta(days=9))
    anchor, seen = verdicts(handoffs)
    check("seats at an anchor more than an hour before boot are offered, not restarted",
          seen["mac-prof"][0] == "offer" and seen["beside-mac-prof"][0] == "offer",
          seen)
    check("the offer names the three outcomes",
          all(word in seen["mac-prof"][1] for word in ("restart", "park", "finished")),
          seen["mac-prof"])
    check("a seat far behind an old anchor is still not running",
          seen["long-gone"][0] == "not-running-at-the-stop", seen)

    # The one-hour bound, pinned on both sides.
    for minutes_before_boot, expected in ((59, "restart"), (60, "restart"), (61, "offer")):
        handoffs = root / f"anchor-{minutes_before_boot}-minutes-before-boot"
        write_state(handoffs, "late-seat", BOOT_AT - timedelta(minutes=minutes_before_boot))
        anchor, seen = verdicts(handoffs)
        check(f"an anchor {minutes_before_boot} minutes before boot: {expected}",
              seen["late-seat"][0] == expected, seen)

    # A heartbeat since boot belongs to a seat that has had a supervisor since
    # boot. It must not be the anchor: if it were, every seat stamped before
    # the stop would fall outside the window.
    handoffs = root / "stamped-since-boot"
    write_state(handoffs, "running-now", NOW - timedelta(seconds=4))
    write_state(handoffs, "was-running", STOP)
    write_state(handoffs, "was-running-too", STOP - timedelta(seconds=9))
    anchor, seen = verdicts(handoffs)
    check("a heartbeat since boot is not the anchor",
          anchor == STOP, anchor)
    check("a seat stamped since boot is reported as such, and not restarted",
          seen["running-now"][0] == "stamped-since-boot", seen)
    # Amended 2026-09-11 (review of 8b15919): once a seat has been written
    # since boot, nothing is restarted silently — the seats that were
    # running at the stop are offered.
    check("with a seat written since boot, the seats running at the stop are offered",
          seen["was-running"][0] == "offer" and seen["was-running-too"][0] == "offer"
          and "since boot" in seen["was-running"][1],
          seen)

    # The review's second run: run 1 restarted A and B, so their heartbeats
    # are since boot, and the newest one left before boot is Z's — a seat
    # whose supervisor died 35 minutes before the stop. Run 1 left Z alone;
    # run 2 must not restart it.
    handoffs = root / "second-run"
    write_state(handoffs, "A", NOW - timedelta(seconds=3))
    write_state(handoffs, "B", NOW - timedelta(seconds=6))
    write_state(handoffs, "Z-died-before-stop", STOP - timedelta(minutes=35))
    anchor, seen = verdicts(handoffs)
    check("a later run never restarts the seat that died before the stop",
          seen["Z-died-before-stop"][0] == "offer"
          and seen["A"][0] == "stamped-since-boot"
          and seen["B"][0] == "stamped-since-boot",
          seen)

    # The launch window: the supervisor rewrites its state file as it starts
    # (handoff-supervisor.py, before the first launch) while it still holds
    # the stamp from before boot. The file's write says a supervisor is
    # running; the stamp still says when the stop was.
    handoffs = root / "launch-window"
    write_state(handoffs, "just-launched", STOP, written_at=NOW - timedelta(seconds=1))
    write_state(handoffs, "not-yet-launched", STOP - timedelta(seconds=4))
    anchor, seen = verdicts(handoffs)
    check("a file rewritten since boot is not restarted, even with a stamp from before boot",
          seen["just-launched"][0] == "stamped-since-boot", seen)
    check("its stamp from before boot still anchors the stop",
          anchor == STOP and seen["not-yet-launched"][0] == "offer", (anchor, seen))

    handoffs = root / "only-since-boot"
    write_state(handoffs, "running-now", NOW - timedelta(seconds=4))
    anchor, seen = verdicts(handoffs)
    check("with every heartbeat since boot there is no anchor and nothing to restart",
          anchor is None and seen["running-now"][0] == "stamped-since-boot",
          (anchor, seen))

    # The user's answer, 2026-09-11, on a state file that cannot be read:
    # "Resume or continue works perfectly 99% of the time, so I'd try that."
    # A reboot in the middle of the supervisor's whole-file write leaves an
    # empty or cut-off file, written at the stop. The file's last write
    # stands in for the heartbeat it cannot give.
    handoffs = root / "unreadable-at-the-stop"
    write_state(handoffs, "anchor-seat", STOP)
    write_state(handoffs, "empty-file", raw="", written_at=STOP)
    write_state(handoffs, "cut-off-mid-write",
                raw='{\n  "consumed_counter": 3,\n  "sess', written_at=STOP)
    write_state(handoffs, "unparseable-stamp",
                raw=json.dumps({"session_id": "x", "last_poll_at": "yesterday"}),
                written_at=STOP)
    write_state(handoffs, "no-stamp", raw=json.dumps({"session_id": "x"}),
                written_at=STOP)
    write_state(handoffs, "naive-stamp",
                raw=json.dumps({"last_poll_at": "2026-09-11T05:02:12"}),
                written_at=STOP)
    write_state(handoffs, "future-stamp", NOW + timedelta(days=2), written_at=STOP)
    anchor, seen = verdicts(handoffs)
    for seat in ("empty-file", "cut-off-mid-write", "unparseable-stamp",
                 "no-stamp", "naive-stamp", "future-stamp"):
        check(f"a state file cut off at the stop is restarted ({seat})",
              seen[seat][0] == "restart" and "cannot be read" in seen[seat][1],
              seen[seat])
    check("the unreadable files do not disturb the anchor",
          anchor == STOP and seen["anchor-seat"][0] == "restart", (anchor, seen))

    # The review's race: a running supervisor truncates and rewrites its file
    # every 10 seconds, so a read can land on an empty file. Its write is
    # since boot, so it belongs to a seat running now.
    handoffs = root / "unreadable-since-boot"
    write_state(handoffs, "anchor-seat", STOP)
    write_state(handoffs, "caught-mid-write", raw="", written_at=NOW)
    anchor, seen = verdicts(handoffs)
    check("an unreadable file written since boot is a seat running now, not a restart",
          seen["caught-mid-write"][0] == "stamped-since-boot", seen)

    # A file damaged long before the stop is judged like any old seat: the
    # user's answer covers a file the stop damaged, not one abandoned weeks
    # earlier (a supervisor that died before its first heartbeat leaves one).
    handoffs = root / "unreadable-long-before"
    write_state(handoffs, "anchor-seat", STOP)
    write_state(handoffs, "abandoned-weeks-ago", raw=json.dumps({"session_id": "x"}),
                written_at=STOP - timedelta(days=21))
    anchor, seen = verdicts(handoffs)
    check("an unreadable file written weeks before the stop is not restarted",
          seen["abandoned-weeks-ago"][0] == "not-running-at-the-stop", seen)

    # A supervisor stamping while this runs lands a moment after `now`: that
    # is a seat running now, not a stamp from the future.
    handoffs = root / "stamp-just-after-now"
    write_state(handoffs, "stamping-now", NOW + timedelta(seconds=5))
    anchor, seen = verdicts(handoffs)
    check("a stamp a few seconds after now is a seat running now, not an unreadable one",
          seen["stamping-now"][0] == "stamped-since-boot"
          and "cannot be read" not in seen["stamping-now"][1],
          seen)

    # A seat with no state file never ran under a supervisor: the supervisor
    # writes the file on its first launch and never deletes it.
    handoffs = root / "no-state-file"
    write_state(handoffs, "supervised-seat", STOP)
    (handoffs / "never-supervised-handoff.md").write_text(
        "# Handoff\nrestart-counter: 1\n", encoding="utf-8")
    anchor, seen = verdicts(handoffs)
    check("only seats with a supervisor state file are considered",
          set(seen) == {"supervised-seat"}, seen)

    anchor, seen = verdicts(root / "does-not-exist")
    check("a handoff directory that does not exist selects nothing",
          anchor is None and seen == {}, (anchor, seen))

    # Boot time, in each machine's own format.
    check("the Mac's kern.boottime is read from its sec field",
          restart.parse_darwin_kern_boottime(
              "{ sec = 1789103232, usec = 162719 } Thu Sep 10 22:07:12 2026\n")
          == BOOT_AT,
          restart.parse_darwin_kern_boottime(
              "{ sec = 1789103232, usec = 162719 } Thu Sep 10 22:07:12 2026\n"))
    box_boot = restart.parse_uptime_since("2026-08-20 02:01:00\n")
    check("the box's uptime -s is read as local time",
          box_boot.tzinfo is not None
          and box_boot == datetime(2026, 8, 20, 2, 1, 0).astimezone(),
          box_boot)

    # The command line. Until the restart step is built, the program only
    # reports, and says so rather than appearing to restart anything.
    exit_code, report, errors = run_main(["--handoff-dir", str(root / "measured-2026-09-01")])
    check("without --dry-run it refuses: the restart step is not built yet",
          exit_code != 0 and "--dry-run" in errors, (exit_code, errors))
    exit_code, report, errors = run_main(["--dry-run", "--handoff-dir",
                                          str(root / "measured-2026-09-01")])
    check("--dry-run reports the boot, the stop, and one line per seat",
          exit_code == 0 and "boot" in report and "MD-skills: restart" in report
          and "mac-prof: not-running-at-the-stop" in report
          and "nothing is launched" in report,
          report)
    exit_code, report, errors = run_main(["--dry-run", "--handoff-dir",
                                          str(root / "second-run")])
    check("--dry-run says when this boot's restart has already run",
          exit_code == 0 and "already run" in report
          and "Z-died-before-stop: offer" in report,
          report)


print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
