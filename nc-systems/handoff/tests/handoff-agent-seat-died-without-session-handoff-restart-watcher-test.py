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

failures = []

BOOT = datetime(2026, 10, 12, 0, 0, tzinfo=timezone.utc)
SEEN_RUNNING = datetime(2026, 10, 12, 3, 0, tzinfo=timezone.utc)
DIED_AT = datetime(2026, 10, 12, 3, 14, 18, tzinfo=timezone.utc)


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

    def assess(self, seat):
        if seat in self.assessment_errors:
            raise self.assessment_errors[seat]
        return self.verdicts[seat]

    def recover(self, seat):
        self.recoveries.append(seat)
        return self.recovery_result

    def open_window(self, words):
        self.windows.append(words)
        exit_code = self.window_exit_codes.pop(0) if self.window_exit_codes else 0
        return exit_code, "" if exit_code == 0 else "the Mac cannot be reached"

    def run(self, now, seats=("merge-lane-2",)):
        watcher = watcher_module.Watcher(
            state=self.state, now=now, boot_at=BOOT, log_directory=self.log_directory,
            assess=self.assess, died_at_about=lambda seat: DIED_AT,
            transcripts_directory=lambda seat: Path(f"/home/nedlern/.claude/projects/-{seat}"),
            recover=self.recover, open_window=self.open_window,
            show_notice_words=lambda path, seat: (
                ["/usr/bin/python3", str(SCRIPT_PATH), "--show-notice", path]
                + (["--then-attach", seat] if seat else [])))
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
    notices = harness.notices()
    notice_text = notices[0].read_text(encoding="utf-8") if notices else ""
    check("a seat seen running, then crashed on two runs a minute apart, is restarted once",
          harness.recoveries == ["merge-lane-2"], repr(harness.recoveries))
    check("the restart notice names the seat, both times and the record",
          len(notices) == 1 and "merge-lane-2 was restarted at 2026-10-12 03:16 UTC" in notice_text
          and "stopped at about 2026-10-12 03:14 UTC" in notice_text
          and str(root / "restarted" / "decisions.jsonl") in notice_text, notice_text)
    check("the restart window shows the notice and then attaches to the seat",
          len(harness.windows) == 1 and harness.windows[0][-2:] == ["--then-attach", "merge-lane-2"],
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
              entry["decision"].startswith("found crashed") for entry in harness.decisions()),
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

    for verdict in ("defer-to-boot-ignition", "seat-asked-to-be-consulted",
                    "offer-after-recorded-exit", "refuse",
                    "ask-to-close-the-leftover-idle-shell"):
        harness = Harness(root / f"left-alone-{verdict}")
        harness.verdicts["merge-lane-2"] = ("seat-already-running", "")
        harness.run(SEEN_RUNNING)
        harness.verdicts["merge-lane-2"] = (verdict, "detail")
        for minutes in (5, 6, 7):
            harness.run(SEEN_RUNNING + timedelta(minutes=minutes))
        left_alone = [entry for entry in harness.decisions()
                      if entry["decision"].startswith("left alone")]
        check(f"a seat whose verdict is {verdict} is left alone, logged once",
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
          and "launch-claude-ubuntu merge-lane-2" in text, text)
    check("the second-crash window shows the notice and does not attach",
          "--then-attach" not in harness.windows[-1], repr(harness.windows[-1]))

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
          and not harness.state["seats"]["merge-lane-2"].get("restarts"),
          repr(harness.state))

    harness = Harness(root / "mac-unreachable", window_exit_codes=[1, 1])
    crash_after_running(harness)
    check("a notice the Mac cannot be reached for stays pending",
          len(harness.state["pending_notices"]) == 1, repr(harness.state["pending_notices"]))
    harness.run(SEEN_RUNNING + timedelta(minutes=17))
    unshown = [entry for entry in harness.decisions()
               if entry["decision"].startswith("notice not shown")]
    check("the unreachable Mac is logged once, not on every retry",
          len(unshown) == 1 and len(harness.windows) == 2, repr(harness.decisions()))
    harness.run(SEEN_RUNNING + timedelta(minutes=18))
    check("a pending notice is shown once the Mac answers, and leaves the pending list",
          harness.state["pending_notices"] == [] and len(harness.windows) == 3
          and any(entry["decision"] == "pending notice shown" for entry in harness.decisions()),
          repr(harness.state["pending_notices"]))

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
    check("the recovery gets no TMUX, TMUX_PANE, CLAUDECODE or CLAUDE_CODE_* identity variable",
          not any(name in passed for name in ("TMUX", "TMUX_PANE", "CLAUDECODE",
                                               "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_CHILD_SESSION",
                                               "CLAUDE_CODE_MESSAGING_SOCKET")), repr(passed))
    check("the recovery keeps PATH, HOME and GH_TOKEN",
          all(passed.get(name) == environment[name] for name in ("PATH", "HOME", "GH_TOKEN")),
          repr(passed))


def run_window_words_cases(root: Path):
    notice = (watcher_module.LOG_DIRECTORY / "notices"
              / "20261012T031600Z-merge-lane-2-restarted.txt")
    words = ["/usr/bin/python3",
             "/home/nedlern/Projects/nedschorus/nc-systems/handoff/"
             "handoff-agent-seat-died-without-session-handoff-restart-watcher.py",
             "--show-notice", str(notice), "--then-attach", "merge-lane-2"]
    request = " ".join([forced_command.REQUEST_VERB, *words])
    try:
        received = forced_command.window_command_words(request)
        refused = None
    except forced_command.RequestRefused as error:
        received, refused = None, str(error)
    check("the Mac's forced command accepts the window words the watcher sends",
          received == words, refused or repr(received))


def run_command_line_cases(root: Path):
    notice = root / "notice.txt"
    notice.write_text("merge-lane-2 was restarted at 2026-10-12 03:16 UTC.\n", encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--show-notice", str(notice)],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)
    check("--show-notice prints the notice and the close prompt, and exits 0",
          completed.returncode == 0 and "merge-lane-2 was restarted" in completed.stdout
          and watcher_module.SHOW_NOTICE_CLOSE_PROMPT in completed.stdout,
          f"{completed.returncode} {completed.stdout!r} {completed.stderr!r}")

    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--then-attach", "merge-lane-2"],
        capture_output=True, text=True, check=False)
    check("--then-attach without --show-notice is a usage error",
          completed.returncode == 2 and "--then-attach needs --show-notice" in completed.stderr,
          completed.stderr)

    state_directory = root / "locked-state"
    state_directory.mkdir()
    environment = {watcher_module.STATE_DIRECTORY_ENVIRONMENT_VARIABLE: str(state_directory),
                   watcher_module.LOG_DIRECTORY_ENVIRONMENT_VARIABLE: str(root / "locked-log")}
    with (state_directory / f"{watcher_module.PROGRAM}.lock").open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        exit_code = watcher_module.run_once(environment)
    check("a run that finds another run holding the lock does nothing and exits 0",
          exit_code == 0
          and not (state_directory / f"{watcher_module.PROGRAM}-state.json").exists(),
          repr(list(state_directory.iterdir())))

    run_run_failure_cases(root)

    real_platform = sys.platform
    try:
        sys.platform = "darwin"
        exit_code = watcher_module.main([])
    finally:
        sys.platform = real_platform
    check("off ned-box the watcher refuses with exit 2", exit_code == 2, repr(exit_code))


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


def run_state_cases(root: Path):
    state_path = root / "state" / "watcher-state.json"
    state = watcher_module.read_state(state_path)
    state["seats"]["merge-lane-2"] = {"last_seen_running_at": "2026-10-12T03:00:00+00:00"}
    watcher_module.write_state(state_path, state)
    check("the state written is the state read back",
          watcher_module.read_state(state_path) == state, state_path.read_text(encoding="utf-8"))


with tempfile.TemporaryDirectory() as temporary_directory:
    run_decision_cases(Path(temporary_directory))
    run_environment_cases()
    run_window_words_cases(Path(temporary_directory))
    run_command_line_cases(Path(temporary_directory))
    run_state_cases(Path(temporary_directory))

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
