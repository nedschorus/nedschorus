#!/usr/bin/env python3
"""Tests for nc-systems/handoff/agent-seat-state-records-reader.py, the one
module the login restart, recovery and the task viewer use to read an
agent-seat's records.

Those programs' suites reach this module through their own code. These cases
pin its functions directly, on records written into a temporary handoff
directory: heartbeats, the login restart's run log, the live set at the stop,
a waiting session-handoff, and task list names.

Run: python3 nc-systems/handoff/tests/agent-seat-state-records-reader-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HANDOFF_DIRECTORY = Path(__file__).resolve().parents[1]
MODULE_PATH = Path(os.environ.get(
    "AGENT_SEAT_STATE_RECORDS_READER_MODULE_PATH",
    HANDOFF_DIRECTORY / "agent-seat-state-records-reader.py"))
_spec = importlib.util.spec_from_file_location("agent_seat_state_records_reader", MODULE_PATH)
reader = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reader)

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


BOOT = datetime(2026, 10, 13, 12, 0, 0, tzinfo=timezone.utc)
NOW = BOOT + timedelta(minutes=5)
WINDOW = reader.LIVE_SET_WINDOW_SECONDS


def write_state(directory, seat, last_poll_at, written_at, raw=None):
    path = reader.supervisor_state_path(directory, seat)
    text = raw if raw is not None else json.dumps(
        {"consumed_counter": None, "last_poll_at": last_poll_at})
    path.write_text(text, encoding="utf-8")
    os.utime(path, (written_at.timestamp(), written_at.timestamp()))
    return path


def verdicts(decisions):
    return {seat: verdict for seat, verdict, _ in decisions}


with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)

    # The re-exports are the supervisor's and the transcript selector's own.
    check("re-exports: the supervisor's readers and the transcript selector are passed through",
          reader.supervisor_state_path is reader.supervisor.supervisor_state_path
          and reader.parse_handoff_file is reader.supervisor.parse_handoff_file
          and reader.newest_real_transcript is reader.worth_resuming.newest_real_transcript)
    check("the live-set window is two supervisor heartbeats",
          WINDOW == 2 * reader.supervisor.HEARTBEAT_INTERVAL_SECONDS, WINDOW)

    # describe_gap
    for seconds, expected in ((59, "59s"), (60, "1m"), (120, "2m"), (3600, "1h"),
                              (3 * 3600, "3h"), (86400, "1d"), (2 * 86400, "2d")):
        got = reader.describe_gap(timedelta(seconds=seconds))
        check(f"describe_gap: {seconds}s reads {expected}", got == expected, got)

    # read_supervisor_heartbeat
    def heartbeat(name, text):
        path = scratch / f"{name}-heartbeat.json"
        if text is not None:
            path.write_text(text, encoding="utf-8")
        return reader.read_supervisor_heartbeat(path, NOW)

    stamp = NOW - timedelta(seconds=30)
    check("heartbeat: a stamped state file gives its stamp",
          heartbeat("good", json.dumps({"last_poll_at": stamp.isoformat()})) == (stamp, ""))
    for name, text, words in (
            ("missing", None, "not readable as JSON: FileNotFoundError"),
            ("not-json", "{nope", "not readable as JSON: JSONDecodeError"),
            ("a-list", "[1, 2]", "carries no last_poll_at"),
            ("no-key", json.dumps({"consumed_counter": 3}), "carries no last_poll_at"),
            ("empty-stamp", json.dumps({"last_poll_at": ""}), "carries no last_poll_at"),
            ("garbage", json.dumps({"last_poll_at": "yesterday"}), "does not parse"),
            ("a-number", json.dumps({"last_poll_at": 12345}), "does not parse"),
            ("naive", json.dumps({"last_poll_at": "2026-10-13T11:00:00"}),
             "carries no timezone"),
            ("future", json.dumps({"last_poll_at": (NOW + timedelta(
                seconds=WINDOW + 1)).isoformat()}), "is in the future")):
        result = heartbeat(name, text)
        check(f"heartbeat: {name} is refused with its reason",
              result[0] is None and words in result[1], result)
    near_future = NOW + timedelta(seconds=WINDOW - 1)
    check("heartbeat: a stamp just after now, within the window, is accepted",
          heartbeat("near", json.dumps({"last_poll_at": near_future.isoformat()}))
          == (near_future, ""))
    undecodable = scratch / "undecodable-heartbeat.json"
    undecodable.write_bytes(b'{"last_poll_at": "\xff"}')
    result = reader.read_supervisor_heartbeat(undecodable, NOW)
    check("heartbeat: a state file that is not UTF-8 is refused, not raised",
          result[0] is None and "UnicodeDecodeError" in result[1], result)

    # read_stop_of_run_log_line
    stop = BOOT - timedelta(minutes=10)
    for entry, expected, case in (
            ({}, (None, False), "no stop_at"),
            ({"stop_at": None}, (None, True), "a recorded null stop"),
            ({"stop_at": 5}, (None, False), "a stop that is not text"),
            ({"stop_at": "soon"}, (None, False), "a stop that does not parse"),
            ({"stop_at": "2026-10-13T11:50:00"}, (None, False), "a stop with no timezone"),
            ({"stop_at": stop.isoformat()}, (stop, True), "a readable stop")):
        got = reader.read_stop_of_run_log_line(entry)
        check(f"run-log stop: {case}", got == expected, got)

    # read_earlier_run_for_this_boot
    logs = scratch / "run-logs"
    logs.mkdir()
    check("earlier run: no run log means no earlier run",
          reader.read_earlier_run_for_this_boot(logs, BOOT) == (None, False))
    log = logs / reader.RUN_LOG_FILE_NAME
    lines = [
        "not json",
        json.dumps(["a", "list"]),
        json.dumps({"stop_at": stop.isoformat()}),
        json.dumps({"boot_at": 7, "stop_at": stop.isoformat()}),
        json.dumps({"boot_at": "not a time", "stop_at": stop.isoformat()}),
        json.dumps({"boot_at": "2026-10-13T12:00:00", "stop_at": stop.isoformat()}),
        json.dumps({"boot_at": (BOOT - timedelta(seconds=reader.BOOT_MATCH_TOLERANCE_SECONDS
                                                    + 1)).isoformat(),
                    "stop_at": (stop - timedelta(hours=1)).isoformat()}),
        json.dumps({"boot_at": BOOT.isoformat(), "stop_at": "corrupt"}),
        json.dumps({"boot_at": (BOOT + timedelta(seconds=reader.BOOT_MATCH_TOLERANCE_SECONDS
                                                    - 1)).isoformat(),
                    "stop_at": stop.isoformat()}),
        json.dumps({"boot_at": BOOT.isoformat(), "stop_at": None}),
    ]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    got = reader.read_earlier_run_for_this_boot(logs, BOOT)
    check("earlier run: skips unreadable lines and other boots; the first readable line "
          "for this boot, within the tolerance, wins", got == (stop, True), got)
    log.write_text(json.dumps({"boot_at": BOOT.isoformat(), "stop_at": None}) + "\n",
                   encoding="utf-8")
    check("earlier run: a recorded null stop is an earlier run with no stop",
          reader.read_earlier_run_for_this_boot(logs, BOOT) == (None, True))
    log.write_bytes(b"\xff\xfe\n")
    check("earlier run: a run log that is not UTF-8 does not block the restart",
          reader.read_earlier_run_for_this_boot(logs, BOOT) == (None, False))

    # select_seats_live_at_the_stop
    check("live set: no handoff directory gives no anchor and no decisions",
          reader.select_seats_live_at_the_stop(scratch / "absent", BOOT, NOW)
          == (None, [], False))

    plain = scratch / "plain-stop"
    plain.mkdir()
    last = BOOT - timedelta(seconds=100)
    write_state(plain, "at-the-stop", last.isoformat(), last)
    edge = last - timedelta(seconds=WINDOW)
    write_state(plain, "window-edge", edge.isoformat(), edge)
    early = last - timedelta(seconds=WINDOW + 1)
    write_state(plain, "just-outside", early.isoformat(), early)
    write_state(plain, "unreadable", None, last - timedelta(seconds=5), raw="{broken")
    anchor, decisions, anchor_is_the_stop = reader.select_seats_live_at_the_stop(
        plain, BOOT, NOW)
    check("live set: the anchor is the newest heartbeat before boot, and is the stop",
          anchor == last and anchor_is_the_stop is True, (anchor, anchor_is_the_stop))
    check("live set: seats within the window restart; a seat one second outside does not",
          verdicts(decisions) == {"at-the-stop": "restart", "window-edge": "restart",
                                  "just-outside": "not-running-at-the-stop",
                                  "unreadable": "restart"}, verdicts(decisions))
    reasons = {seat: reason for seat, _, reason in decisions}
    check("live set: an unreadable heartbeat says the file's write time stands in for it",
          reasons["unreadable"].startswith("its heartbeat cannot be read (")
          and "stands in for it" in reasons["unreadable"], reasons["unreadable"])
    check("live set: a restart reason says how long before the stop and before boot",
          "before the stop, which was 2m before boot" in reasons["at-the-stop"],
          reasons["at-the-stop"])

    rerun = scratch / "restart-already-ran"
    rerun.mkdir()
    write_state(rerun, "before-boot", last.isoformat(), last)
    since = BOOT + timedelta(seconds=50)
    write_state(rerun, "since-boot", since.isoformat(), since)
    write_state(rerun, "written-since-boot", last.isoformat(), BOOT + timedelta(seconds=1))
    anchor, decisions, anchor_is_the_stop = reader.select_seats_live_at_the_stop(
        rerun, BOOT, NOW)
    check("live set: once a seat is written since boot, the anchor is not trusted as the stop",
          anchor == last and anchor_is_the_stop is False, (anchor, anchor_is_the_stop))
    check("live set: a seat stamped or written since boot is left alone; one from before "
          "boot is offered, not restarted",
          verdicts(decisions) == {"before-boot": "offer", "since-boot": "stamped-since-boot",
                                  "written-since-boot": "stamped-since-boot"},
          verdicts(decisions))

    recorded = BOOT - timedelta(seconds=200)
    anchor, decisions, anchor_is_the_stop = reader.select_seats_live_at_the_stop(
        rerun, BOOT, NOW, recorded_stop=recorded)
    check("live set: a recorded stop is the anchor and is trusted though seats ran since boot",
          anchor == recorded and anchor_is_the_stop is True, (anchor, anchor_is_the_stop))
    check("live set: under a recorded stop, a seat from before boot within the window restarts",
          verdicts(decisions)["before-boot"] == "restart", verdicts(decisions))

    # waiting_handoff_verdict
    handoffs = scratch / "handoffs"
    handoffs.mkdir()
    state = reader.supervisor_state_path(handoffs, "seat")

    def handoff(text, consumed="absent"):
        reader.handoff_file_path(handoffs, "seat").write_text(text, encoding="utf-8")
        if consumed == "absent":
            state.unlink(missing_ok=True)
        else:
            state.write_text(json.dumps({"consumed_counter": consumed}), encoding="utf-8")
        return reader.waiting_handoff_verdict(handoffs, "seat", state)

    check("waiting handoff: none written means none waits",
          reader.waiting_handoff_verdict(handoffs, "seat", state) is None)
    got = handoff("next-step: carry on\n")
    check("waiting handoff: one with no restart-counter is refused, with the fix",
          got is not None and got[0] == "refuse" and "restart-counter" in got[1], got)
    got = handoff("restart-counter: three\n")
    check("waiting handoff: an unreadable restart-counter is refused",
          got is not None and got[0] == "refuse", got)
    got = handoff("restart-counter: 3\n")
    check("waiting handoff: with no state file, the handoff waits for boot-ignition",
          got is not None and got[0] == "defer-to-boot-ignition" and "counter 3" in got[1], got)
    got = handoff("restart-counter: 3\n", consumed=2)
    check("waiting handoff: a counter above the consumed one waits",
          got is not None and got[0] == "defer-to-boot-ignition", got)
    check("waiting handoff: a counter equal to the consumed one is spent",
          handoff("restart-counter: 3\n", consumed=3) is None)
    check("waiting handoff: a counter below the consumed one is spent",
          handoff("restart-counter: 3\n", consumed=5) is None)
    got = handoff("restart-counter: 4\ndont-restart: user asked for a pause\n", consumed=3)
    check("waiting handoff: a dont-restart handoff asks to be consulted, with its counter "
          "and reason", got == ("seat-asked-to-be-consulted", (4, "user asked for a pause")),
          got)
    check("waiting handoff: a spent dont-restart handoff no longer waits",
          handoff("restart-counter: 4\ndont-restart: pause\n", consumed=4) is None)

    # seat_of
    for list_id, expected in (("nedschorus-reboot-test-tasks", "reboot-test"),
                              ("nedschorus-merge-lane-2", "merge-lane-2"),
                              ("merge-lane-2-tasks", "merge-lane-2"),
                              ("some-other-list", "some-other-list"),
                              ("nedschorus--tasks", "nedschorus--tasks")):
        got = reader.seat_of(list_id)
        check(f"seat_of: {list_id} names {expected}", got == expected, got)

print(f"{failures} failure(s)" if failures else "all cases pass")
sys.exit(1 if failures else 0)
