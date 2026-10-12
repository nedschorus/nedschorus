#!/usr/bin/env python3
"""Tests for handoff-agent-seat-died-without-session-handoff-restart-watcher.py.

Run: python3 nc-systems/handoff/tests/handoff-agent-seat-died-without-session-handoff-restart-watcher-test.py

No case restarts an agent-seat or opens a window on the Mac. The decision cases
drive the program's Watcher with a scripted assessment and recorded stand-ins
for the recovery and the window opener; the log goes to a fixture directory;
the moment is passed in. The command-line cases run the program with its state
and log directories pointed at fixture directories.

Prints one line per case and exits non-zero if any case fails.
"""

import fcntl
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

SYSTEM_DIRECTORY = Path(__file__).resolve().parent.parent
SCRIPT_PATH = SYSTEM_DIRECTORY / "handoff-agent-seat-died-without-session-handoff-restart-watcher.py"
REPOSITORY = SYSTEM_DIRECTORY.parent.parent

_spec = importlib.util.spec_from_file_location("handoff_agent_seat_died_without_session_handoff_restart_watcher",
                                               SCRIPT_PATH)
watcher_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(watcher_module)

_forced_spec = importlib.util.spec_from_file_location(
    "mac_window_opened_for_ned_box_forced_command",
    REPOSITORY / "scripts" / "mac-window-opened-for-ned-box-forced-command.py")
forced_command = importlib.util.module_from_spec(_forced_spec)
_forced_spec.loader.exec_module(forced_command)

_recovery_spec = importlib.util.spec_from_file_location(
    "recover_crashed_seats", REPOSITORY / "scripts" / "recover-crashed-seats.py")
recovery_module = importlib.util.module_from_spec(_recovery_spec)
_recovery_spec.loader.exec_module(recovery_module)

failures = []

BOOT = datetime(2026, 10, 12, 0, 0, tzinfo=timezone.utc)
SEEN_RUNNING = datetime(2026, 10, 12, 3, 0, tzinfo=timezone.utc)
# The supervisor's last_poll_at carries microseconds (stamp_heartbeat writes
# datetime.now(timezone.utc).isoformat()), so the fixture's must too.
DIED_AT = datetime(2026, 10, 12, 3, 14, 18, 437512, tzinfo=timezone.utc)


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


class Harness:
    """A Watcher's outside world: verdicts to hand out, and every call recorded."""

    def __init__(self, log_directory, recovery_result=(0, "merge-lane-2: relaunched resuming x"),
                 window_exit_codes=None):
        self.log_directory = log_directory
        self.state = watcher_module.read_state(log_directory / "no-state-yet.json")
        self.verdicts = {}
        self.assessment_errors = {}
        self.recovery_result = recovery_result
        self.window_exit_codes = list(window_exit_codes or [])
        self.recoveries = []
        self.windows = []
        self.died_at = DIED_AT
        # A launch that does not come up polls before it dies: its heartbeat moves.
        self.died_at_after_recovery = None
        self.on_purpose = False

    def assess(self, seat):
        if seat in self.assessment_errors:
            raise self.assessment_errors[seat]
        return self.verdicts[seat]

    def recover(self, seat):
        self.recoveries.append(seat)
        if self.died_at_after_recovery is not None:
            self.died_at = self.died_at_after_recovery
        return self.recovery_result

    def open_window(self, words):
        self.windows.append(words)
        exit_code = self.window_exit_codes.pop(0) if self.window_exit_codes else 0
        return exit_code, "" if exit_code == 0 else "the Mac cannot be reached"

    def run(self, now, seats=("merge-lane-2",)):
        watcher = watcher_module.Watcher(
            state=self.state, now=now, boot_at=BOOT, log_directory=self.log_directory,
            assess=self.assess, died_at_about=lambda seat: self.died_at,
            transcripts_directory=lambda seat: Path(f"/home/nedlern/.claude/projects/-{seat}"),
            recover=self.recover, open_window=self.open_window,
            show_notice_words=lambda path: ["/usr/bin/python3", str(SCRIPT_PATH),
                                            "--show-notice", path],
            stopped_on_purpose=lambda seat, detail: self.on_purpose,
            recorded_exit_question=recovery_module.restart_question_for_a_seat_with_a_recorded_exit)
        watcher.run(list(seats))

    def decisions(self):
        path = self.log_directory / "decisions.jsonl"
        if not path.is_file():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def notices(self):
        directory = self.log_directory / "notices"
        return sorted(directory.iterdir()) if directory.is_dir() else []


def crash_after_running(harness, seat="merge-lane-2", start=SEEN_RUNNING):
    """Seen running, then crashed on two runs a minute apart; returns the second run's moment."""
    harness.verdicts[seat] = ("seat-already-running", "supervisor alive")
    harness.run(start, seats=(seat,))
    harness.verdicts[seat] = ("resume", ("session-id", "found"))
    harness.run(start + timedelta(minutes=15), seats=(seat,))
    confirmed = start + timedelta(minutes=16)
    harness.run(confirmed, seats=(seat,))
    return confirmed


def run_decision_cases(root: Path):
    harness = Harness(root / "restarted")
    crash_after_running(harness)
    check("a seat seen running, then crashed on two runs a minute apart, is restarted once",
          harness.recoveries == ["merge-lane-2"], repr(harness.recoveries))
    check("a restart the watcher carried out shows the user no notice",
          harness.notices() == [], repr(harness.notices()))
    check("a restart opens a window on the Mac attached straight to the seat's session",
          harness.windows == [["tmux", "-L", "merge-lane-2", "attach", "-t", "merge-lane-2"]],
          repr(harness.windows))
    check("the restart is logged with the recovery's output",
          any(entry["decision"] == "restarted" and "relaunched" in entry["recovery_output"]
              for entry in harness.decisions()), repr(harness.decisions()))
    harness.run(SEEN_RUNNING + timedelta(minutes=17))
    check("a crash already restarted is not restarted again while the seat stays down",
          harness.recoveries == ["merge-lane-2"], repr(harness.recoveries))

    harness = Harness(root / "first-sighting")
    harness.verdicts["merge-lane-2"] = ("seat-already-running", "")
    harness.run(SEEN_RUNNING)
    harness.verdicts["merge-lane-2"] = ("resume", ("session-id", "found"))
    harness.run(SEEN_RUNNING + timedelta(minutes=1))
    check("a seat found crashed on one run only is not restarted yet",
          harness.recoveries == [] and any(
              entry["decision"].startswith("found down") for entry in harness.decisions()),
          repr(harness.decisions()))
    harness.run(SEEN_RUNNING + timedelta(minutes=1, seconds=20))
    check("a second sighting sooner than the confirmation time does not restart it",
          harness.recoveries == [], repr(harness.recoveries))
    harness.verdicts["merge-lane-2"] = ("seat-already-running", "")
    harness.run(SEEN_RUNNING + timedelta(minutes=2))
    harness.verdicts["merge-lane-2"] = ("resume", ("session-id", "found"))
    harness.run(SEEN_RUNNING + timedelta(minutes=3))
    check("a seat seen running again between two crashed sightings starts its confirmation over",
          harness.recoveries == [], repr(harness.recoveries))

    for verdict in ("seat-asked-to-be-consulted", "offer-after-recorded-exit", "refuse",
                    "ask-to-close-the-leftover-idle-shell"):
        harness = Harness(root / f"left-alone-{verdict}")
        harness.on_purpose = True
        harness.verdicts["merge-lane-2"] = ("seat-already-running", "")
        harness.run(SEEN_RUNNING)
        harness.verdicts["merge-lane-2"] = (
            verdict, (0, "2026-10-12T03:05:00+00:00", "s") if verdict == "offer-after-recorded-exit"
            else "detail")
        for minutes in (5, 6, 7):
            harness.run(SEEN_RUNNING + timedelta(minutes=minutes))
        left_alone = [entry for entry in harness.decisions()
                      if entry["decision"].startswith("left alone")]
        check(f"a seat whose verdict is {verdict}, stopped on purpose, is left alone, logged once",
              harness.recoveries == [] and harness.windows == [] and len(left_alone) == 1,
              repr(harness.decisions()))

    harness = Harness(root / "not-seen-since-boot")
    harness.state["seats"]["merge-lane-2"] = {
        "last_seen_running_at": watcher_module.timestamp(BOOT - timedelta(hours=1))}
    harness.verdicts["merge-lane-2"] = ("resume", ("session-id", "found"))
    harness.run(BOOT + timedelta(minutes=3))
    harness.run(BOOT + timedelta(minutes=4))
    check("a seat last seen running before the machine booted is left to the login restart",
          harness.recoveries == [] and any(
              "since the machine booted" in entry["decision"] for entry in harness.decisions()),
          repr(harness.decisions()))

    harness = Harness(root / "never-seen")
    harness.verdicts["ghi-info"] = ("resume", ("session-id", "found"))
    harness.run(SEEN_RUNNING, seats=("ghi-info",))
    harness.run(SEEN_RUNNING + timedelta(minutes=2), seats=("ghi-info",))
    check("a seat this watcher never saw running is not restarted",
          harness.recoveries == [], repr(harness.recoveries))

    harness = Harness(root / "second-crash")
    first_restart = crash_after_running(harness)
    crash_after_running(harness, start=first_restart + timedelta(minutes=5))
    second_crash_notices = [path for path in harness.notices() if "second-crash" in path.name]
    text = second_crash_notices[0].read_text(encoding="utf-8") if second_crash_notices else ""
    check("a second crash within the hour is not restarted",
          harness.recoveries == ["merge-lane-2"], repr(harness.recoveries))
    check("the second-crash notice gives both crashes, the earlier restart and the command",
          "merge-lane-2 is down" in text and "had restarted it at 2026-10-12 03:16 UTC" in text
          and "python3 scripts/recover-crashed-seats.py merge-lane-2" in text
          and f"  {watcher_module.MAC_LAUNCHER} merge-lane-2\n" in text, text)
    check("the second-crash notice names the transcripts by their path on the Mac",
          "/Volumes/nedhome/.claude/projects/-merge-lane-2" in text, text)
    check("the second-crash window shows the notice and does not attach",
          harness.windows[-1][-2] == "--show-notice" and "attach" not in harness.windows[-1],
          repr(harness.windows[-1]))
    check("a notice gives the record's path on the Mac and on ned-box",
          f"(on ned-box: {root / 'second-crash' / 'decisions.jsonl'})" in text, text)

    harness = Harness(root / "after-the-hour")
    first_restart = crash_after_running(harness)
    crash_after_running(harness, start=first_restart + timedelta(hours=1, minutes=5))
    check("a crash more than an hour after the last restart is restarted",
          harness.recoveries == ["merge-lane-2", "merge-lane-2"], repr(harness.recoveries))

    harness = Harness(root / "recovery-failed",
                      recovery_result=(1, "merge-lane-2: REFUSED — the durable checkout is missing"))
    crash_after_running(harness)
    failed = [path for path in harness.notices() if "recovery-failed" in path.name]
    text = failed[0].read_text(encoding="utf-8") if failed else ""
    check("a failed recovery reaches the user with its exit code and its words",
          "exited 1" in text and "REFUSED — the durable checkout is missing" in text
          and "launch-claude-ubuntu merge-lane-2" in text, text)
    check("the failed-recovery notice gives the next step when recovery only says why it refused",
          "If it says only why recovery refused, ask an agent on ned-box" in text, text)

    harness = Harness(root / "recovery-failed-last-line",
                      recovery_result=(1, "merge-lane-2: checking the seat\n"
                                          "merge-lane-2: REFUSED — the seat directory is in use\n\n"))
    crash_after_running(harness)
    failed = [path for path in harness.notices() if "recovery-failed" in path.name]
    text = failed[0].read_text(encoding="utf-8") if failed else ""
    check("the failed-recovery notice quotes recovery's last line, not its earlier ones",
          "Its last line was:\n  merge-lane-2: REFUSED — the seat directory is in use\n" in text
          and "checking the seat" not in text, text)
    harness = Harness(root / "recovery-failed-silent", recovery_result=(1, ""))
    crash_after_running(harness)
    failed = [path for path in harness.notices() if "recovery-failed" in path.name]
    text = failed[0].read_text(encoding="utf-8") if failed else ""
    check("a recovery that printed nothing is said to have printed nothing",
          "Its last line was:\n  (it printed nothing)\n" in text, text)
    check("a failed recovery is logged",
          any(entry["decision"].startswith("recovery failed") for entry in harness.decisions()),
          repr(harness.decisions()))
    harness.run(SEEN_RUNNING + timedelta(minutes=17))
    check("a failed recovery is not retried every minute",
          harness.recoveries == ["merge-lane-2"], repr(harness.recoveries))

    harness = Harness(root / "already-running",
                      recovery_result=(0, "merge-lane-2: ALREADY RUNNING — a supervisor is watching"))
    crash_after_running(harness)
    check("a seat already running again when recovery runs gets no notice and no restart record",
          harness.notices() == []
          and not harness.state["seats"]["merge-lane-2"].get("recovery_attempts"),
          repr(harness.state))

    harness = Harness(root / "mac-unreachable", window_exit_codes=[1, 1])
    crash_after_running(harness)
    check("a restarted seat's window the Mac cannot be reached for stays pending, "
          "and is not turned into a notice",
          harness.state["pending_notices"] == [{"attach_seat": "merge-lane-2"}]
          and harness.notices() == [], repr(harness.state["pending_notices"]))
    harness.verdicts["merge-lane-2"] = ("seat-already-running", "restarted")
    harness.run(SEEN_RUNNING + timedelta(minutes=17))
    unopened = [entry for entry in harness.decisions()
                if entry["decision"].startswith("window not opened")]
    check("the unreachable Mac is logged once, not on every retry",
          len(unopened) == 1 and len(harness.windows) == 2, repr(harness.decisions()))
    harness.run(SEEN_RUNNING + timedelta(minutes=18))
    check("a pending window is opened once the Mac answers, and leaves the pending list",
          harness.state["pending_notices"] == [] and len(harness.windows) == 3
          and harness.windows[-1][:2] == ["tmux", "-L"]
          and any(entry["decision"] == "pending window shown" for entry in harness.decisions()),
          repr(harness.state["pending_notices"]))

    harness = Harness(root / "mac-unreachable-for-a-notice",
                      recovery_result=(1, "merge-lane-2: REFUSED — the durable checkout is missing"),
                      window_exit_codes=[1])
    crash_after_running(harness)
    pending = harness.state["pending_notices"]
    check("a notice the Mac cannot be reached for stays pending",
          len(pending) == 1 and "recovery-failed" in pending[0].get("path", ""), repr(pending))
    harness.run(SEEN_RUNNING + timedelta(minutes=17))
    check("a pending notice is shown once the Mac answers",
          harness.state["pending_notices"] == []
          and harness.windows[-1][-2] == "--show-notice", repr(harness.windows))

    harness = Harness(root / "assessment-failed")
    harness.assessment_errors["merge-lane-2"] = OSError("Permission denied: '/home/nedlern/agents'")
    harness.run(SEEN_RUNNING)
    harness.run(SEEN_RUNNING + timedelta(minutes=1))
    failed = [path for path in harness.notices() if "assessment-failed" in path.name]
    text = failed[0].read_text(encoding="utf-8") if failed else ""
    check("an assessment that raises reaches the user once, with the error",
          len(failed) == 1 and "Permission denied" in text, repr(harness.notices()))
    check("an assessment that raises is logged on every run",
          len([entry for entry in harness.decisions()
               if entry["decision"] == "could not assess"]) == 2, repr(harness.decisions()))
    harness.assessment_errors.clear()
    harness.verdicts["merge-lane-2"] = ("seat-already-running", "")
    harness.run(SEEN_RUNNING + timedelta(minutes=2))
    check("one seat's failed assessment does not stop the others",
          "merge-lane-2" in harness.state["seats"], repr(harness.state))


def run_handled_crash_cases(root: Path):
    harness = Harness(root / "dies-again-after-restart")
    restarted_at = crash_after_running(harness)
    for minutes in range(2, 10):
        harness.run(restarted_at + timedelta(minutes=minutes))
    second = [path for path in harness.notices() if "second-crash" in path.name]
    check("a seat that dies again after a restart, before a run sees it running, "
          "reaches the user as a second crash",
          harness.recoveries == ["merge-lane-2"] and len(second) == 1,
          repr((harness.recoveries, harness.notices())))
    check("a restart that succeeded counts as a sighting of the seat running",
          harness.state["seats"]["merge-lane-2"]["last_seen_running_at"]
          == watcher_module.timestamp(restarted_at), repr(harness.state["seats"]))

    harness = Harness(root / "already-running-sighting",
                      recovery_result=(0, "merge-lane-2: ALREADY RUNNING — a supervisor is watching"))
    confirmed = crash_after_running(harness)
    record = harness.state["seats"]["merge-lane-2"]
    check("a seat already running when recovery runs counts as a sighting",
          record.get("last_seen_running_at") == watcher_module.timestamp(confirmed)
          and not record.get("crash_handled"), repr(record))

    harness = Harness(root / "restarted-by-hand-then-died",
                      recovery_result=(1, "merge-lane-2: LAUNCH FAILED (exit 1)"))
    failed_at = crash_after_running(harness)
    harness.recovery_result = (0, "merge-lane-2: relaunched resuming x")
    harness.died_at = failed_at + timedelta(minutes=3, microseconds=250001)
    for minutes in (4, 5, 6):
        harness.run(failed_at + timedelta(minutes=minutes))
    second = [path for path in harness.notices() if "second-crash" in path.name]
    text = second[0].read_text(encoding="utf-8") if second else ""
    check("a seat restarted by hand after a failed attempt, which dies within the hour, "
          "is watched as a new crash and reaches the user, not restarted",
          harness.recoveries == ["merge-lane-2"] and len(second) == 1
          and any(entry["decision"].startswith("ran again since")
                  for entry in harness.decisions()), repr(harness.decisions()))
    check("that second-crash notice says the earlier attempt failed",
          "had tried to restart it at 2026-10-12 03:16 UTC" in text
          and "recovery reported that attempt as failed; merge-lane-2 then ran again, "
              "either because that attempt came up late or because it was started by hand or "
              "by another program" in text, text)
    harness.died_at = failed_at + timedelta(hours=1, minutes=10, microseconds=1)
    for minutes in (71, 72, 73):
        harness.run(failed_at + timedelta(minutes=minutes))
    check("a seat restarted by hand that dies more than an hour after the failed attempt "
          "is restarted",
          harness.recoveries == ["merge-lane-2", "merge-lane-2"], repr(harness.recoveries))

    harness = Harness(root / "handled-and-still-down")
    harness.recovery_result = (1, "merge-lane-2: LAUNCH FAILED (exit 1)")
    failed_at = crash_after_running(harness)
    for minutes in range(1, 6):
        harness.run(failed_at + timedelta(minutes=minutes))
    check("a handled crash with no later supervisor poll is not acted on again",
          harness.recoveries == ["merge-lane-2"] and len(harness.notices()) == 1,
          repr((harness.recoveries, harness.notices())))


def run_handled_death_key_cases(root: Path):
    """The one rule for a handled death: the supervisor's last poll, at full precision."""
    harness = Harness(root / "microsecond-poll-recovery-failed",
                      recovery_result=(1, "merge-lane-2: LAUNCH FAILED (exit 1)"))
    failed_at = crash_after_running(harness)
    for minutes in range(1, 21):
        harness.run(failed_at + timedelta(minutes=minutes))
    check("a failed recovery under a poll with microseconds is attempted once and told once "
          "in twenty runs",
          harness.recoveries == ["merge-lane-2"] and len(harness.notices()) == 1,
          repr((harness.recoveries, harness.notices())))
    record = harness.state["seats"]["merge-lane-2"]
    check("the handled poll is stored at the supervisor's own precision",
          record.get("handled_at_supervisor_last_poll") == DIED_AT.isoformat(), repr(record))

    for verdict, detail in (("defer-to-boot-ignition", "an unconsumed handoff waits"),
                            ("offer-after-recorded-exit", (1, "2026-10-12T03:14:20+00:00", "s"))):
        harness = Harness(root / f"microsecond-poll-{verdict}")
        harness.verdicts["merge-lane-2"] = ("seat-already-running", "")
        harness.run(SEEN_RUNNING)
        harness.verdicts["merge-lane-2"] = (verdict, detail)
        for minutes in range(15, 35):
            harness.run(SEEN_RUNNING + timedelta(minutes=minutes))
        check(f"a seat down with verdict {verdict} under a poll with microseconds is told once "
              "in twenty runs",
              len(harness.notices()) == 1 and harness.recoveries == [], repr(harness.notices()))

    harness = Harness(root / "startup-crash-loop",
                      recovery_result=(1, "merge-lane-2: LAUNCHED BUT DID NOT COME UP — the "
                                          "supervisor exited during the settle"))
    harness.died_at_after_recovery = DIED_AT + timedelta(minutes=2, microseconds=125)
    failed_at = crash_after_running(harness)
    for minutes in range(1, 31):
        harness.run(failed_at + timedelta(minutes=minutes))
    attempts = harness.state["seats"]["merge-lane-2"].get("recovery_attempts", [])
    check("a launch that did not come up, whose supervisor polled before it died, is not "
          "relaunched every two minutes",
          harness.recoveries == ["merge-lane-2"] and len(harness.notices()) == 1,
          repr((harness.recoveries, harness.notices())))
    check("the failed attempt is recorded and counts against the hourly limit",
          [attempt["outcome"] for attempt in attempts] == ["failed"]
          and harness.state["seats"]["merge-lane-2"].get("handled_at_supervisor_last_poll")
          == harness.died_at_after_recovery.isoformat(), repr(harness.state["seats"]))

    harness = Harness(root / "second-crash-never-ran-again")
    first_restart = crash_after_running(harness)
    harness.died_at = first_restart + timedelta(minutes=2, microseconds=660000)
    for minutes in range(3, 90):
        harness.run(first_restart + timedelta(minutes=minutes))
    second = [path for path in harness.notices() if "second-crash" in path.name]
    check("a second crash left down is told once, and the seat that never ran again is not "
          "restarted once the hour has passed",
          harness.recoveries == ["merge-lane-2"] and len(second) == 1,
          repr((harness.recoveries, harness.notices())))


def run_down_for_the_user_cases(root: Path):
    harness = Harness(root / "waiting-handoff")
    harness.verdicts["merge-lane-2"] = ("seat-already-running", "")
    harness.run(SEEN_RUNNING)
    harness.verdicts["merge-lane-2"] = ("defer-to-boot-ignition", "an unconsumed handoff waits")
    for minutes in (5, 6, 7, 8):
        harness.run(SEEN_RUNNING + timedelta(minutes=minutes))
    notices = [path for path in harness.notices() if "waiting-handoff" in path.name]
    text = notices[0].read_text(encoding="utf-8") if notices else ""
    check("a seat down with a waiting handoff is not restarted, and the user is told once",
          harness.recoveries == [] and len(notices) == 1, repr(harness.notices()))
    check("the waiting-handoff notice names the seat, the state and the one command, by the "
          "launcher's path on the Mac",
          "merge-lane-2 is down" in text and "a handoff it had not acted on was waiting" in text
          and f"  {watcher_module.MAC_LAUNCHER} merge-lane-2\n" in text
          and "recover-crashed-seats.py" not in text and "left to you" not in text, text)

    harness = Harness(root / "recorded-exit")
    harness.verdicts["merge-lane-2"] = ("seat-already-running", "")
    harness.run(SEEN_RUNNING)
    harness.verdicts["merge-lane-2"] = ("offer-after-recorded-exit",
                                        (1, "2026-10-12T03:04:00+00:00", "session"))
    for minutes in (5, 6, 7, 8):
        harness.run(SEEN_RUNNING + timedelta(minutes=minutes))
    notices = [path for path in harness.notices() if "recorded-exit" in path.name]
    text = notices[0].read_text(encoding="utf-8") if notices else ""
    check("a seat whose supervisor recorded an exit without resuming is not restarted, "
          "and the user is told once",
          harness.recoveries == [] and len(notices) == 1, repr(harness.notices()))
    check("the recorded-exit notice gives the exit code, the time and the ssh -t command",
          "exit code 1" in text and "2026-10-12 03:04 UTC" in text
          and "ssh -t nedlern@ned-box" in text
          and 'It asks "merge-lane-2 stopped with exit code 1. Restart it? y/n"; answer y, '
              "and it resumes merge-lane-2's last conversation" in text, text)
    check("the recorded-exit notice says what answering n does",
          "answer n, and it starts nothing and prints the commands to bring merge-lane-2 "
          "back by hand later" in text, text)


def run_stopped_on_purpose_cases(root: Path):
    """The real predicate watch() builds, on fixture handoff and supervisor files."""
    agents_root = root / "purpose-agents"
    handoff_directory = root / "purpose-handoffs"
    for directory in (agents_root / "seat-a", handoff_directory):
        directory.mkdir(parents=True, exist_ok=True)
    login_restart = watcher_module.load_module(
        "restart_live_seats_at_login_for_tests", watcher_module.LOGIN_RESTART_PROGRAM)
    supervisor = login_restart.supervisor
    predicate = watcher_module.stopped_on_purpose_predicate(supervisor, handoff_directory)
    check("a clean exit is a stop on purpose", predicate("seat-a", (0, "t", None)))
    check("an exit with an error code and no handoff is not a stop on purpose",
          not predicate("seat-a", (1, "t", None)))
    state_path = supervisor.supervisor_state_path(handoff_directory, "seat-a")
    supervisor.handoff_file_path(handoff_directory, "seat-a").write_text(
        "restart-counter: 7\ndont-restart: the user asked to be consulted before a relaunch\n"
        "next-step: stop\n", encoding="utf-8")
    supervisor.record_agent_exit_in_supervisor_state(
        state_path, {"consumed_counter": 7}, None,
        reason=supervisor.AGENT_EXIT_REASON_STOPPED_AT_A_DONT_RESTART_HANDOFF)
    check("an exit its supervisor recorded as a stop at a dont-restart handoff is a stop on "
          "purpose", predicate("seat-a", (None, "t", None)))
    # The user answered y: the handoff stays on disk, consumed, and its successor later
    # failed and used up its resumes, so the supervisor recorded that exit with no reason.
    supervisor.record_agent_exit_in_supervisor_state(state_path, {"consumed_counter": 7}, -15)
    check("a later failure of the successor of a dont-restart handoff answered y is not a "
          "stop on purpose, though the consumed handoff is still on disk",
          not predicate("seat-a", (-15, "t", None)))


def run_path_on_the_mac_cases():
    check("a ned-box home path is given in the form the Mac mounts",
          watcher_module.path_on_the_mac(
              "/home/nedlern/nedschorus-logs/x/decisions.jsonl")
          == "/Volumes/nedhome/nedschorus-logs/x/decisions.jsonl")
    check("a path outside ned-box's home is left as it is",
          watcher_module.path_on_the_mac("/tmp/x/decisions.jsonl") == "/tmp/x/decisions.jsonl")
    check("a path that only starts with the same letters as the home is left as it is",
          watcher_module.path_on_the_mac("/home/nedlernx/y") == "/home/nedlernx/y")
    harness = Harness(Path("/nonexistent-never-written"))
    harness.log_directory = None
    watcher = watcher_module.Watcher(
        state=harness.state, now=SEEN_RUNNING, boot_at=BOOT,
        log_directory=Path("/home/nedlern/nedschorus-logs") / watcher_module.PROGRAM,
        assess=None, died_at_about=None, transcripts_directory=None, recover=None,
        open_window=None, show_notice_words=None)
    check("the record a notice names is the Mac's form of the log-store path",
          watcher_module.path_on_the_mac(watcher.decisions_path).startswith(
              "/Volumes/nedhome/nedschorus-logs/"), str(watcher.decisions_path))


def run_environment_cases():
    environment = {"PATH": "/usr/bin:/bin", "HOME": "/home/nedlern", "GH_TOKEN": "token",
                   "TMUX": "/tmp/tmux-1000/fleet-restart-at-login,1,0", "TMUX_PANE": "%0",
                   "CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "4095854c",
                   "CLAUDE_CODE_CHILD_SESSION": "1",
                   "CLAUDE_CODE_MESSAGING_SOCKET": "/run/user/1000/cc-socks/1.sock"}
    calls = []
    watcher_module.recover_seat_in_clean_environment(
        "merge-lane-2", environment,
        run=lambda command, passed: calls.append((command, passed)) or (0, ""))
    command, passed = calls[0] if calls else ([], {})
    check("the recovery is recover-crashed-seats.py <seat>",
          command[1:] == [str(watcher_module.RECOVERY_PROGRAM), "merge-lane-2"], repr(calls))
    check("the recovery gets the watcher's environment, which launch_seat cleans before a seat starts",
          passed == environment, repr(passed))


def run_window_words_cases(root: Path):
    notice = (watcher_module.LOG_DIRECTORY / "notices"
              / "20261012T031600Z-merge-lane-2-recovery-failed.txt")
    notice_words = ["/usr/bin/python3",
                    "/home/nedlern/Projects/nedschorus/nc-systems/handoff/"
                    "handoff-agent-seat-died-without-session-handoff-restart-watcher.py",
                    "--show-notice", str(notice)]
    built_words = watcher_module.show_notice_words_for_window(str(notice))
    check("the notice window's words are the interpreter, this program, --show-notice and the notice",
          built_words[2:] == notice_words[2:] and len(built_words) == len(notice_words),
          repr(built_words))
    attach_words = [word.format(seat="merge-lane-2") for word in watcher_module.ATTACH_COMMAND]
    for name, words in (("a notice window", notice_words), ("a restarted seat's window", attach_words)):
        request = " ".join([forced_command.REQUEST_VERB, *words])
        try:
            received = forced_command.window_command_words(request)
            refused = None
        except forced_command.RequestRefused as error:
            received, refused = None, str(error)
        check(f"the Mac's forced command accepts the words of {name}",
              received == words, refused or repr(received))


def run_command_line_cases(root: Path):
    notice = root / "notice.txt"
    notice.write_text("merge-lane-2 is down: the crash watcher could not restart it.\n",
                      encoding="utf-8")
    # The words a notice window runs, built as the watcher builds them, so a flag the
    # parser does not accept fails here rather than in a window on the Mac.
    completed = subprocess.run(
        watcher_module.show_notice_words_for_window(str(notice)),
        stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)
    check("a notice window's words print the notice and the close prompt, and exit 0",
          completed.returncode == 0 and "merge-lane-2 is down" in completed.stdout
          and watcher_module.SHOW_NOTICE_CLOSE_PROMPT in completed.stdout,
          f"{completed.returncode} {completed.stdout!r} {completed.stderr!r}")

    state_directory = root / "locked-state"
    state_directory.mkdir()
    environment = {watcher_module.STATE_DIRECTORY_ENVIRONMENT_VARIABLE: str(state_directory),
                   watcher_module.LOG_DIRECTORY_ENVIRONMENT_VARIABLE: str(root / "locked-log")}
    watched = []
    real_watch = watcher_module.watch
    # A stand-in, so a broken lock reaches no real agent-seat and no window on the Mac.
    watcher_module.watch = lambda *arguments: watched.append(arguments) or 0
    try:
        with (state_directory / f"{watcher_module.PROGRAM}.lock").open("w") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            exit_code = watcher_module.run_once(environment)
    finally:
        watcher_module.watch = real_watch
    check("a run that finds another run holding the lock does nothing and exits 0",
          exit_code == 0 and watched == [], repr(watched))

    run_run_failure_cases(root)

    real_platform, real_run_once = sys.platform, watcher_module.run_once
    ran = []
    # A stand-in, so a broken platform check reaches no real agent-seat and no window on the Mac.
    watcher_module.run_once = lambda environment: ran.append(environment) or 0
    try:
        sys.platform = "darwin"
        exit_code = watcher_module.main([])
    finally:
        sys.platform, watcher_module.run_once = real_platform, real_run_once
    check("off ned-box the watcher refuses with exit 2, and runs nothing",
          exit_code == 2 and ran == [], f"exit {exit_code}, runs started: {len(ran)}")


def run_run_failure_cases(root: Path):
    """A run that fails before it can assess any seat: the login restart's module is missing."""
    environment = {watcher_module.STATE_DIRECTORY_ENVIRONMENT_VARIABLE: str(root / "failed-state"),
                   watcher_module.LOG_DIRECTORY_ENVIRONMENT_VARIABLE: str(root / "failed-log")}
    windows = []
    window_exit_codes = [1]
    real_program, real_opener = watcher_module.LOGIN_RESTART_PROGRAM, watcher_module.open_mac_window
    watcher_module.LOGIN_RESTART_PROGRAM = root / "no-such-login-restart.py"
    watcher_module.open_mac_window = lambda words: (
        windows.append(words) or ((window_exit_codes.pop(0), "unreachable") if window_exit_codes
                                  else (0, "")))
    raised = []
    try:
        for _ in range(3):
            try:
                watcher_module.run_once(environment)
            except Exception as error:  # noqa: BLE001 - the case checks that it propagates
                raised.append(error)
    finally:
        watcher_module.LOGIN_RESTART_PROGRAM, watcher_module.open_mac_window = real_program, real_opener
    notices = sorted((root / "failed-log" / "notices").glob("*run-failed.txt"))
    text = notices[-1].read_text(encoding="utf-8") if notices else ""
    check("a failed run still fails, so cron's log keeps the traceback",
          len(raised) == 3, repr(raised))
    check("a failed run tells the user the watcher is watching no agent-seat, with the error",
          "watching no agent-seat" in text and "no-such-login-restart.py" in text, text)
    check("a failed run's notice is retried while the Mac cannot be reached, then shown once",
          len(windows) == 2, repr(windows))

    environment = {watcher_module.STATE_DIRECTORY_ENVIRONMENT_VARIABLE: str(root / "healed-state"),
                   watcher_module.LOG_DIRECTORY_ENVIRONMENT_VARIABLE: str(root / "healed-log")}
    window_exit_codes = [1]
    windows.clear()
    watcher_module.LOGIN_RESTART_PROGRAM = root / "no-such-login-restart.py"
    watcher_module.open_mac_window = lambda words: (
        windows.append(words) or ((window_exit_codes.pop(0), "unreachable") if window_exit_codes
                                  else (0, "")))
    try:
        try:
            watcher_module.run_once(environment)
        except Exception:  # noqa: BLE001 - the failing run is the setup
            pass
    finally:
        watcher_module.LOGIN_RESTART_PROGRAM, watcher_module.open_mac_window = real_program, real_opener
    state_path = root / "healed-state" / f"{watcher_module.PROGRAM}-state.json"
    saved = watcher_module.read_state(state_path)
    check("a failed run's notice the Mac missed waits in the state every run reads",
          len(saved["pending_notices"]) == 1, repr(saved))
    healthy_windows = []
    watcher = watcher_module.Watcher(
        state=saved, now=SEEN_RUNNING, boot_at=BOOT, log_directory=root / "healed-log",
        assess=None, died_at_about=lambda seat: None, transcripts_directory=None,
        recover=None, open_window=lambda words: healthy_windows.append(words) or (0, ""),
        show_notice_words=lambda path: ["--show-notice", path])
    watcher.run([])
    check("a healthy run shows the failed run's notice and clears it",
          len(healthy_windows) == 1 and saved["pending_notices"] == []
          and "run-failed" in healthy_windows[0][-1], repr(healthy_windows))


def run_report_run_failure_state_cases(root: Path):
    """report_run_failure when the state it would queue a notice in cannot be read or saved."""
    real_opener = watcher_module.open_mac_window
    windows = []
    watcher_module.open_mac_window = lambda words: windows.append(words) or (1, "unreachable")
    try:
        corrupt = root / "corrupt-state"
        corrupt.mkdir()
        (corrupt / f"{watcher_module.PROGRAM}-state.json").write_text("{not json", encoding="utf-8")
        raised = None
        try:
            watcher_module.report_run_failure("ValueError: bad state", corrupt, root / "corrupt-log")
        except Exception as error:  # noqa: BLE001 - the case checks that nothing escapes
            raised = error
        reported = corrupt / f"{watcher_module.PROGRAM}-reported-run-failures.txt"
        check("an unreadable state still lets a failed run write its notice and try the Mac",
              raised is None and len(windows) == 1
              and list((root / "corrupt-log" / "notices").glob("*run-failed.txt")),
              repr((raised, windows)))
        check("with an unreadable state, a notice the Mac missed is left for the next failing run",
              not reported.exists(), reported.read_text(encoding="utf-8") if reported.exists() else "")

        locked = root / "unsavable-state"
        locked.mkdir()
        (locked / f"{watcher_module.PROGRAM}-state.json").write_text("{}", encoding="utf-8")
        locked.chmod(0o555)
        raised = None
        try:
            watcher_module.report_run_failure("OSError: disk", locked, root / "unsavable-log")
        except Exception as error:  # noqa: BLE001 - the case checks that nothing escapes
            raised = error
        finally:
            locked.chmod(0o755)
        decisions = (root / "unsavable-log" / "decisions.jsonl").read_text(encoding="utf-8")
        check("a state that cannot be saved is logged, and the error is not marked as reported",
              raised is None and "could not save the watcher's state" in decisions
              and not (locked / f"{watcher_module.PROGRAM}-reported-run-failures.txt").exists(),
              repr(raised))
    finally:
        watcher_module.open_mac_window = real_opener


def run_state_cases(root: Path):
    state_path = root / "state" / "watcher-state.json"
    state = watcher_module.read_state(state_path)
    state["seats"]["merge-lane-2"] = {"last_seen_running_at": "2026-10-12T03:00:00+00:00"}
    watcher_module.write_state(state_path, state)
    check("the state written is the state read back",
          watcher_module.read_state(state_path) == state, state_path.read_text(encoding="utf-8"))


with tempfile.TemporaryDirectory() as temporary_directory:
    run_decision_cases(Path(temporary_directory))
    run_handled_crash_cases(Path(temporary_directory))
    run_handled_death_key_cases(Path(temporary_directory))
    run_down_for_the_user_cases(Path(temporary_directory))
    run_stopped_on_purpose_cases(Path(temporary_directory))
    run_path_on_the_mac_cases()
    run_environment_cases()
    run_window_words_cases(Path(temporary_directory))
    run_command_line_cases(Path(temporary_directory))
    run_report_run_failure_state_cases(Path(temporary_directory))
    run_state_cases(Path(temporary_directory))

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
