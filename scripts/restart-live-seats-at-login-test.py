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


def verdicts(handoffs: Path, boot_at=BOOT_AT, now=NOW, recorded_stop=None):
    anchor, decisions, _ = restart.select_seats_live_at_the_stop(
        handoffs, boot_at, now, recorded_stop=recorded_stop)
    return anchor, {seat: (verdict, reason) for seat, verdict, reason in decisions}


def run_log_path(handoffs: Path) -> Path:
    return handoffs / restart.RUN_LOG_FILE_NAME


def run_log_lines(handoffs: Path):
    """The run log's lines, parsed. A line that does not parse fails here:
    every line this program writes is one JSON object."""
    path = run_log_path(handoffs)
    if not path.exists():
        return []
    return [json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_run_log_line(handoffs: Path, text: str):
    """One line into the run log, verbatim — so a case can plant a malformed
    one as well as a good one."""
    handoffs.mkdir(parents=True, exist_ok=True)
    with run_log_path(handoffs).open("a", encoding="utf-8") as stream:
        stream.write(text + "\n")


def run_log_entry(boot_at=BOOT_AT, stop_at=STOP, run_at=NOW, seats=None):
    return json.dumps({
        "run_at": run_at.isoformat(timespec="seconds"),
        "boot_at": boot_at.isoformat(),
        "stop_at": None if stop_at is None else stop_at.isoformat(),
        "seats": seats if seats is not None else {"A": "restart"}})


def run_main(arguments, boot_at=BOOT_AT):
    """main() with this machine's boot time replaced by boot_at (BOOT_AT
    unless a case is exercising the boot instant moving between runs) and its
    clock by NOW; (exit code, stdout, stderr)."""
    printed, errors = io.StringIO(), io.StringIO()
    real_machine_boot_time, real_current_time = restart.machine_boot_time, restart.current_time
    try:
        restart.machine_boot_time = lambda: boot_at
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

    # ---- The run log ----
    #
    # User-ruled 2026-09-11: "sounds like we need a log here ... not a single
    # file". A later run in the same boot cannot re-derive the stop, because
    # the seats that came back have stamped over their heartbeats from before
    # boot. So every run that is not a dry run appends one line — the boot,
    # the stop, the verdict per seat — and a later run in the same boot reads
    # the stop back instead of deriving it. Precedent: the recovery tool's
    # recover-crashed-seats-log.txt, ruled 2026-08-22.

    handoffs = root / "run-log-absent"
    handoffs.mkdir(parents=True, exist_ok=True)
    check("with no run log there is no recorded stop",
          restart.read_recorded_stop_for_boot(handoffs, BOOT_AT) is None,
          restart.read_recorded_stop_for_boot(handoffs, BOOT_AT))

    handoffs = root / "run-log-this-boot"
    write_run_log_line(handoffs, run_log_entry())
    check("a line for this boot gives back the stop it recorded",
          restart.read_recorded_stop_for_boot(handoffs, BOOT_AT) == STOP,
          restart.read_recorded_stop_for_boot(handoffs, BOOT_AT))

    handoffs = root / "run-log-another-boot"
    earlier_boot = BOOT_AT - timedelta(days=2)
    write_run_log_line(handoffs, run_log_entry(
        boot_at=earlier_boot, stop_at=earlier_boot - timedelta(minutes=5)))
    check("a line from an earlier boot is ignored: the stop it holds is not this one's",
          restart.read_recorded_stop_for_boot(handoffs, BOOT_AT) is None,
          restart.read_recorded_stop_for_boot(handoffs, BOOT_AT))

    # The box reads its boot time from `uptime -s`, in local time, so the same
    # boot can be written with a different offset. Boots are matched as
    # instants, not as strings.
    handoffs = root / "run-log-other-offset"
    write_run_log_line(handoffs, run_log_entry(
        boot_at=BOOT_AT.astimezone(timezone(timedelta(hours=-7)))))
    check("the same boot written in another timezone offset is the same boot",
          restart.read_recorded_stop_for_boot(handoffs, BOOT_AT) == STOP,
          restart.read_recorded_stop_for_boot(handoffs, BOOT_AT))

    # Neither machine stores its boot instant: the Mac adjusts kern.boottime
    # when the clock is corrected, and the box computes `uptime -s` as now
    # minus /proc/uptime and prints whole seconds, so a clock step of half a
    # second flips it (measured 2026-09-11, in review). A boot written a
    # second or two apart is the same boot; five seconds is still far below
    # the shortest interval two real boots can be apart.
    handoffs = root / "run-log-boot-drifted-by-a-second"
    write_run_log_line(handoffs, run_log_entry(boot_at=BOOT_AT - timedelta(seconds=1)))
    check("a boot instant that has drifted by a second is still this boot",
          restart.read_recorded_stop_for_boot(handoffs, BOOT_AT) == STOP,
          restart.read_recorded_stop_for_boot(handoffs, BOOT_AT))
    for drift_seconds, is_this_boot in ((5, True), (6, False)):
        handoffs = root / f"run-log-boot-drifted-by-{drift_seconds}"
        write_run_log_line(handoffs, run_log_entry(
            boot_at=BOOT_AT + timedelta(seconds=drift_seconds)))
        read_back = restart.read_recorded_stop_for_boot(handoffs, BOOT_AT)
        check(f"a boot instant {drift_seconds} seconds off "
              f"{'is' if is_this_boot else 'is not'} this boot",
              (read_back == STOP) == is_this_boot, read_back)

    # A log failure never blocks a run: a line that cannot be read is skipped.
    handoffs = root / "run-log-malformed"
    write_run_log_line(handoffs, "not json at all")
    write_run_log_line(handoffs, "[1, 2, 3]")
    write_run_log_line(handoffs, "")
    write_run_log_line(handoffs, json.dumps({"boot_at": "yesterday", "stop_at": "x"}))
    write_run_log_line(handoffs, json.dumps({"boot_at": BOOT_AT.isoformat(),
                                             "stop_at": "never"}))
    write_run_log_line(handoffs, json.dumps({"boot_at": BOOT_AT.isoformat(),
                                             "stop_at": "2026-09-10T22:02:12"}))
    write_run_log_line(handoffs, run_log_entry())
    check("a line that does not parse is skipped, and the good line after it is read",
          restart.read_recorded_stop_for_boot(handoffs, BOOT_AT) == STOP,
          restart.read_recorded_stop_for_boot(handoffs, BOOT_AT))

    handoffs = root / "run-log-no-stop-recorded"
    write_run_log_line(handoffs, run_log_entry(stop_at=None))
    check("a run that found no stop pins nothing for the runs after it",
          restart.read_recorded_stop_for_boot(handoffs, BOOT_AT) is None,
          restart.read_recorded_stop_for_boot(handoffs, BOOT_AT))

    # The first run in a boot saw the least disturbed state, so its stop is the
    # one that counts.
    handoffs = root / "run-log-two-lines"
    write_run_log_line(handoffs, run_log_entry())
    write_run_log_line(handoffs, run_log_entry(stop_at=STOP - timedelta(minutes=40),
                                               run_at=NOW + timedelta(minutes=1)))
    check("the first line recorded in this boot is the one that counts",
          restart.read_recorded_stop_for_boot(handoffs, BOOT_AT) == STOP,
          restart.read_recorded_stop_for_boot(handoffs, BOOT_AT))

    handoffs = root / "run-log-unreadable"
    handoffs.mkdir(parents=True, exist_ok=True)
    run_log_path(handoffs).mkdir()
    check("a run log that cannot be read is no recorded stop, and does not raise",
          restart.read_recorded_stop_for_boot(handoffs, BOOT_AT) is None,
          restart.read_recorded_stop_for_boot(handoffs, BOOT_AT))

    # With the stop read back, the degradation of the 2026-09-11 amendment is
    # not needed: the recorded stop is the stop, whatever the seats that came
    # back have stamped since. Compare the "second-run" case above, which is
    # this same state with no log to read.
    handoffs = root / "run-log-second-run"
    write_state(handoffs, "A", NOW - timedelta(seconds=3))
    write_state(handoffs, "B", NOW - timedelta(seconds=6))
    write_state(handoffs, "Z-died-before-stop", STOP - timedelta(minutes=35))
    anchor, seen = verdicts(handoffs, recorded_stop=STOP)
    check("the stop read back is the anchor, not the newest heartbeat left",
          anchor == STOP, anchor)
    check("with the stop read back, the seat that died before it is not even offered",
          seen["Z-died-before-stop"][0] == "not-running-at-the-stop"
          and seen["A"][0] == "stamped-since-boot",
          seen)

    handoffs = root / "run-log-seat-that-did-not-come-back"
    write_state(handoffs, "A", NOW - timedelta(seconds=3))
    write_state(handoffs, "C-never-came-back", STOP - timedelta(seconds=4))
    anchor, seen = verdicts(handoffs, recorded_stop=STOP)
    check("a seat that did not come back is restarted by the later run",
          seen["C-never-came-back"][0] == "restart", seen)
    anchor, seen = verdicts(handoffs)
    check("with no recorded stop that same seat is only offered",
          seen["C-never-came-back"][0] == "offer", seen)

    handoffs = root / "run-log-old-recorded-stop"
    old_stop = BOOT_AT - timedelta(days=3)
    write_state(handoffs, "mac-prof", old_stop)
    anchor, seen = verdicts(handoffs, recorded_stop=old_stop)
    check("a recorded stop long before boot is still offered, never restarted silently",
          seen["mac-prof"][0] == "offer", seen)

    handoffs = root / "run-log-append"
    write_state(handoffs, "MD-skills", STOP)
    write_state(handoffs, "mac-prof", STOP - timedelta(days=3))
    anchor, decisions, anchor_is_the_stop = restart.select_seats_live_at_the_stop(
        handoffs, BOOT_AT, NOW)
    restart.append_selection_to_run_log(handoffs, BOOT_AT, anchor, anchor_is_the_stop,
                                        decisions, NOW)
    lines = run_log_lines(handoffs)
    check("a run appends exactly one line", len(lines) == 1, lines)
    # A verdict is a decision, not an outcome. Today nothing can be launched,
    # and once build step 4 lands a decided restart can still fail to come up,
    # so the line records what was launched beside what was decided.
    check("a run that cannot launch anything records launched null, not an empty list",
          lines and lines[0]["launched"] is None, lines)
    check("the line carries the run, the boot, the stop, the anchor and the verdicts",
          lines and lines[0]["run_at"] == NOW.isoformat(timespec="seconds")
          and lines[0]["boot_at"] == BOOT_AT.isoformat()
          and lines[0]["stop_at"] == STOP.isoformat()
          and lines[0]["anchor_at"] == STOP.isoformat()
          and lines[0]["seats"] == {"MD-skills": "restart",
                                    "mac-prof": "not-running-at-the-stop"},
          lines)
    restart.append_selection_to_run_log(handoffs, BOOT_AT, anchor, anchor_is_the_stop,
                                        decisions, NOW + timedelta(minutes=2))
    check("a second run appends rather than overwriting: a log, not a single file",
          len(run_log_lines(handoffs)) == 2, run_log_lines(handoffs))
    check("what a run writes reads back as this boot's stop",
          restart.read_recorded_stop_for_boot(handoffs, BOOT_AT) == STOP,
          restart.read_recorded_stop_for_boot(handoffs, BOOT_AT))

    handoffs = root / "run-log-append-no-anchor"
    write_state(handoffs, "running-now", NOW - timedelta(seconds=4))
    anchor, decisions, anchor_is_the_stop = restart.select_seats_live_at_the_stop(
        handoffs, BOOT_AT, NOW)
    restart.append_selection_to_run_log(handoffs, BOOT_AT, anchor, anchor_is_the_stop,
                                        decisions, NOW)
    check("a run that found no stop records it as null, rather than leaving it out",
          run_log_lines(handoffs)[0]["stop_at"] is None
          and run_log_lines(handoffs)[0]["anchor_at"] is None,
          run_log_lines(handoffs))

    # What build step 4 will write, once it can launch: the seats it brought
    # back, recorded beside the verdicts, so a restart that failed to come up
    # is distinguishable from one that was never attempted.
    handoffs = root / "run-log-launched-recorded"
    write_state(handoffs, "came-back", STOP)
    write_state(handoffs, "failed-to-come-up", STOP - timedelta(seconds=2))
    anchor, decisions, anchor_is_the_stop = restart.select_seats_live_at_the_stop(
        handoffs, BOOT_AT, NOW)
    restart.append_selection_to_run_log(handoffs, BOOT_AT, anchor, anchor_is_the_stop,
                                        decisions, NOW, launched=["came-back"])
    line = run_log_lines(handoffs)[0]
    check("a launched seat is recorded, and one decided but not launched is not",
          line["launched"] == ["came-back"]
          and line["seats"]["failed-to-come-up"] == "restart",
          line)

    handoffs = root / "run-log-directory-absent" / "handoffs"
    restart.append_selection_to_run_log(handoffs, BOOT_AT, STOP, True, [], NOW)
    check("the appender creates the handoff directory when it is not there",
          len(run_log_lines(handoffs)) == 1, run_log_lines(handoffs))

    handoffs = root / "run-log-unwritable"
    write_state(handoffs, "MD-skills", STOP)
    run_log_path(handoffs).mkdir()
    complaints = io.StringIO()
    with redirect_stderr(complaints):
        restart.append_selection_to_run_log(handoffs, BOOT_AT, STOP, True, [], NOW)
    check("a log that cannot be written is reported and never raises",
          "could not append" in complaints.getvalue(), complaints.getvalue())

    # The command line. Until the restart step is built, the program reports
    # and records, and says plainly that it launched nothing.
    handoffs = root / "run-log-main"
    write_state(handoffs, "MD-skills", STOP)
    write_state(handoffs, "mac-prof", STOP - timedelta(days=3))
    exit_code, report, errors = run_main(["--handoff-dir", str(handoffs)])
    check("without --dry-run it reports, and says the restart step is not built yet",
          exit_code == 0 and "MD-skills: restart" in report
          and "not built yet" in report and "launched nothing" in report,
          (exit_code, report))
    check("that run appended its one line to the run log",
          len(run_log_lines(handoffs)) == 1, run_log_lines(handoffs))

    handoffs = root / "run-log-dry-run-writes-nothing"
    write_state(handoffs, "MD-skills", STOP)
    exit_code, report, errors = run_main(["--dry-run", "--handoff-dir", str(handoffs)])
    check("--dry-run appends no line: it promises to change nothing",
          exit_code == 0 and run_log_lines(handoffs) == [], run_log_lines(handoffs))

    handoffs = root / "run-log-dry-run-reads-it"
    write_state(handoffs, "A", NOW - timedelta(seconds=3))
    write_state(handoffs, "Z-died-before-stop", STOP - timedelta(minutes=35))
    write_run_log_line(handoffs, run_log_entry())
    exit_code, report, errors = run_main(["--dry-run", "--handoff-dir", str(handoffs)])
    check("--dry-run reads the run log too, and says the stop was read back",
          exit_code == 0 and "Z-died-before-stop: not-running-at-the-stop" in report
          and "read back" in report and len(run_log_lines(handoffs)) == 1,
          report)

    # A run that cannot tell where the stop was must record no stop. This is
    # the 2026-09-10 shape: the machine reboots, the user brings A and B back
    # by hand, and only then does this program run for the first time in the
    # boot. Its derived anchor is Z's heartbeat, 35 minutes before the real
    # stop — the very thing the 2026-09-11 amendment refuses to act on. If it
    # were written down as the stop, the next run would read it back, drop the
    # degradation because a stop was "recorded", and restart Z.
    handoffs = root / "run-log-degraded-first-run"
    write_state(handoffs, "A", NOW - timedelta(seconds=3))
    write_state(handoffs, "B", NOW - timedelta(seconds=6))
    write_state(handoffs, "Z-died-before-stop", STOP - timedelta(minutes=35))
    exit_code, first_report, errors = run_main(["--handoff-dir", str(handoffs)])
    check("a run whose anchor was stamped over offers it, as the amendment rules",
          "Z-died-before-stop: offer" in first_report, first_report)
    check("and records no stop, keeping only the anchor it worked from",
          run_log_lines(handoffs)[0]["stop_at"] is None
          and run_log_lines(handoffs)[0]["anchor_at"]
          == (STOP - timedelta(minutes=35)).isoformat(),
          run_log_lines(handoffs))
    exit_code, second_report, errors = run_main(["--handoff-dir", str(handoffs)])
    check("so the run after it still refuses to restart a seat that died earlier",
          "Z-died-before-stop: offer" in second_report, second_report)

    # The whole point, end to end: run 1 selects and records; the seats it
    # restarts stamp over the evidence; run 2 reads the stop back.
    handoffs = root / "run-log-round-trip"
    write_state(handoffs, "A", STOP)
    write_state(handoffs, "B", STOP - timedelta(seconds=6))
    write_state(handoffs, "Z-died-before-stop", STOP - timedelta(minutes=35))
    exit_code, first_report, errors = run_main(["--handoff-dir", str(handoffs)])
    check("the first run in a boot restarts the seats that were running at the stop",
          "A: restart" in first_report and "B: restart" in first_report
          and "Z-died-before-stop: not-running-at-the-stop" in first_report,
          first_report)
    write_state(handoffs, "A", NOW - timedelta(seconds=3))
    write_state(handoffs, "B", NOW - timedelta(seconds=6))
    exit_code, second_report, errors = run_main(["--handoff-dir", str(handoffs)])
    check("the second run reads the stop back instead of re-deriving it",
          "Z-died-before-stop: not-running-at-the-stop" in second_report
          and "A: stamped-since-boot" in second_report,
          second_report)
    check("and does not claim this boot's restart left no line in the run log",
          "already run" not in second_report, second_report)
    check("each run is one line in the log",
          len(run_log_lines(handoffs)) == 2, run_log_lines(handoffs))

    # The same round trip with the boot instant a second later on run 2, which
    # is what a clock correction after boot produces. Without the tolerance
    # the read-back is silently lost and the seat that did not come back drops
    # from restart to offer — back to the behaviour the ruling moved past.
    handoffs = root / "run-log-round-trip-with-the-boot-drifting"
    write_state(handoffs, "A", STOP)
    write_state(handoffs, "C-never-came-back", STOP - timedelta(seconds=4))
    run_main(["--handoff-dir", str(handoffs)])
    write_state(handoffs, "A", NOW - timedelta(seconds=3))
    exit_code, drifted_report, errors = run_main(["--handoff-dir", str(handoffs)],
                                                 boot_at=BOOT_AT + timedelta(seconds=1))
    check("a run whose boot instant drifted a second still reads the stop back",
          "C-never-came-back: restart" in drifted_report and "read back" in drifted_report,
          drifted_report)

    # Real stamps carry microseconds (handoff-supervisor.py writes
    # datetime.now(timezone.utc).isoformat()), so the stop written down and
    # the stop read back have to agree to the microsecond.
    handoffs = root / "run-log-microsecond-stop"
    precise_stop = STOP + timedelta(microseconds=123456)
    write_state(handoffs, "A", precise_stop)
    write_state(handoffs, "B", precise_stop - timedelta(seconds=6))
    run_main(["--handoff-dir", str(handoffs)])
    check("a stop carrying microseconds is recorded and read back exactly",
          run_log_lines(handoffs)[0]["stop_at"] == precise_stop.isoformat()
          and restart.read_recorded_stop_for_boot(handoffs, BOOT_AT) == precise_stop,
          run_log_lines(handoffs))

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
