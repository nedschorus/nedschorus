#!/usr/bin/env python3
"""Tests for restart-live-seats-at-login.py (nedschorus#116), the selection step.

Every case runs against a throwaway handoff directory, with the boot time and
the current time passed in, so no case reads this machine's heartbeats or its
real boot time. The rule under test is the #116 design's
§ Ruled 2026-08-31 — the heartbeat answers "which seats were running", with
its 2026-09-02 amendments and the user's 2026-09-11 answer on state files that
cannot be read.

Run: python3 scripts/restart-live-seats-at-login-test.py
"""

import importlib.util
import io
import json
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


def write_state(handoffs: Path, seat: str, stamp=None, raw=None):
    """One supervisor state file. stamp is a datetime written as last_poll_at
    the way stamp_heartbeat() writes it; raw replaces the whole file."""
    handoffs.mkdir(parents=True, exist_ok=True)
    path = handoffs / f"{seat}-supervisor-state.json"
    if raw is not None:
        path.write_text(raw, encoding="utf-8")
    else:
        path.write_text(json.dumps({
            "consumed_counter": 3, "session_id": f"{seat}-session",
            "generation": 3, "last_poll_at": stamp.isoformat()}, indent=2),
            encoding="utf-8")
    return path


def verdicts(handoffs: Path, boot_at=BOOT_AT, now=NOW):
    anchor, decisions = restart.select_seats_live_at_the_stop(handoffs, boot_at, now)
    return anchor, {seat: (verdict, reason) for seat, verdict, reason in decisions}


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
    stop = BOOT_AT - timedelta(minutes=5)
    write_state(handoffs, "MD-skills", stop)
    write_state(handoffs, "merge-lane", stop - timedelta(seconds=8))
    write_state(handoffs, "mac-prof", stop - timedelta(days=3))
    write_state(handoffs, "git-infra", stop - timedelta(days=4))
    write_state(handoffs, "fixer1", stop - timedelta(days=10))
    write_state(handoffs, "repo-hygiene", stop - timedelta(days=15))
    anchor, seen = verdicts(handoffs)
    check("the anchor is the newest stamp before boot",
          anchor == stop, anchor)
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
    write_state(handoffs, "anchor-seat", stop)
    write_state(handoffs, "twenty-behind", stop - timedelta(seconds=20))
    write_state(handoffs, "twenty-one-behind", stop - timedelta(seconds=21))
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

    handoffs = root / "anchor-just-inside-the-hour"
    write_state(handoffs, "late-seat", BOOT_AT - timedelta(minutes=59))
    anchor, seen = verdicts(handoffs)
    check("an anchor 59 minutes before boot restarts",
          seen["late-seat"][0] == "restart", seen)

    # A stamp since boot belongs to a seat running now — recovered by hand, or
    # started by this program on an earlier run. It must not be the anchor:
    # if it were, every seat stamped before the stop would fall outside the
    # window and nothing would be restarted.
    handoffs = root / "stamped-since-boot"
    write_state(handoffs, "running-now", NOW - timedelta(seconds=4))
    write_state(handoffs, "was-running", stop)
    write_state(handoffs, "was-running-too", stop - timedelta(seconds=9))
    anchor, seen = verdicts(handoffs)
    check("a stamp since boot is not the anchor",
          anchor == stop, anchor)
    check("a seat stamped since boot is reported as running, and not restarted",
          seen["running-now"][0] == "running-since-boot", seen)
    check("the seats running at the stop are still restarted beside it",
          seen["was-running"][0] == "restart" and seen["was-running-too"][0] == "restart",
          seen)

    handoffs = root / "only-since-boot"
    write_state(handoffs, "running-now", NOW - timedelta(seconds=4))
    anchor, seen = verdicts(handoffs)
    check("with every stamp since boot there is no anchor and nothing to restart",
          anchor is None and seen["running-now"][0] == "running-since-boot",
          (anchor, seen))

    # The user's answer, 2026-09-11, on a state file that cannot be read:
    # "Resume or continue works perfectly 99% of the time, so I'd try that."
    # A reboot in the middle of the supervisor's whole-file write leaves an
    # empty or cut-off file.
    handoffs = root / "unreadable"
    write_state(handoffs, "anchor-seat", stop)
    write_state(handoffs, "empty-file", raw="")
    write_state(handoffs, "cut-off-mid-write", raw='{\n  "consumed_counter": 3,\n  "sess')
    write_state(handoffs, "unparseable-stamp",
                raw=json.dumps({"session_id": "x", "last_poll_at": "yesterday"}))
    write_state(handoffs, "no-stamp", raw=json.dumps({"session_id": "x"}))
    write_state(handoffs, "future-stamp", NOW + timedelta(days=2))
    anchor, seen = verdicts(handoffs)
    for seat in ("empty-file", "cut-off-mid-write", "unparseable-stamp",
                 "no-stamp", "future-stamp"):
        check(f"a state file whose heartbeat cannot be read is restarted ({seat})",
              seen[seat][0] == "restart" and "cannot be read" in seen[seat][1],
              seen[seat])
    check("an unreadable state file does not disturb the anchor",
          anchor == stop and seen["anchor-seat"][0] == "restart", (anchor, seen))

    # A seat with no state file never ran under a supervisor: the supervisor
    # writes the file on its first launch and never deletes it.
    handoffs = root / "no-state-file"
    write_state(handoffs, "supervised-seat", stop)
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
    handoffs = root / "command-line"
    write_state(handoffs, "MD-skills", stop)
    write_state(handoffs, "mac-prof", stop - timedelta(days=3))
    printed, errors = io.StringIO(), io.StringIO()
    with redirect_stdout(printed), redirect_stderr(errors):
        try:
            exit_code = restart.main(["--handoff-dir", str(handoffs)])
        except SystemExit as stop_request:
            exit_code = stop_request.code
    check("without --dry-run it refuses: the restart step is not built yet",
          exit_code != 0 and "--dry-run" in errors.getvalue(),
          (exit_code, errors.getvalue()))
    printed = io.StringIO()
    real_machine_boot_time = restart.machine_boot_time
    try:
        restart.machine_boot_time = lambda: BOOT_AT
        with redirect_stdout(printed):
            exit_code = restart.main(["--dry-run", "--handoff-dir", str(handoffs)])
    finally:
        restart.machine_boot_time = real_machine_boot_time
    report = printed.getvalue()
    check("--dry-run reports the boot, the anchor, and one line per seat",
          exit_code == 0 and "boot" in report and "MD-skills: restart" in report
          and "mac-prof: not-running-at-the-stop" in report
          and "nothing is launched" in report,
          report)


print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
