#!/usr/bin/env python3
"""Restart a ned-box agent-seat whose agent-session died without writing a handoff.

Usage, on ned-box:
  nc-systems/handoff/handoff-agent-seat-died-without-session-handoff-restart-watcher.py
      one run: assess every agent-seat and act. Cron runs this once a minute.
  nc-systems/handoff/handoff-agent-seat-died-without-session-handoff-restart-watcher.py --show-notice FILE [--then-attach SEAT]
      what the window it opens on the user's Mac runs: print FILE, wait for
      Enter, then attach to SEAT's tmux session or close.

Each run assesses every agent-seat under ~/agents with the assessment
scripts/recover-crashed-seats.py makes (assess_seat), and:
- notes each agent-seat it finds running;
- restarts, with scripts/recover-crashed-seats.py <seat>, an agent-seat it saw
  running earlier in this boot and has since found crashed (verdict resume or
  ignite: no live supervisor, no waiting handoff, no recorded exit) on two runs
  at least CRASH_CONFIRMATION_SECONDS apart;
- tells the user, without restarting it, about an agent-seat it saw running
  that is now down in a state only he should restart from: a handoff waiting
  that no supervisor acted on, or an exit its supervisor recorded without
  resuming, other than a stop on purpose;
- leaves every other agent-seat alone: a stop on purpose (a clean exit, or a
  dont-restart handoff its supervisor consumed), a refusal, and an agent-seat
  not seen running since the machine booted, which the login restart or the
  user brings back;
- restarts an agent-seat at most once in RESTART_LIMIT_SECONDS; a second crash
  inside that time leaves it down and tells the user.

A crash the watcher has handled stays handled only while the seat stays down:
a restart that succeeded counts as a sighting of the seat running, and a
supervisor poll later than the handled crash shows the seat ran again, so its
next death is watched as a new crash.

Each restart and each failure becomes a notice for the user, shown in a window
the program opens on his Mac with scripts/open-mac-window-from-ned-box.py. A
notice the Mac cannot be reached for stays pending and is tried again on every
run. Every decision is appended to decisions.jsonl in LOG_DIRECTORY; the
notices are kept beside it.

Off ned-box the program refuses: the agents root it reads is ned-box's.

SCHEDULED. The job is declared in
nc-systems/general-tools/scheduled-jobs-on-each-machine.json and installed
with nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py
--install --job handoff-agent-seat-died-without-session-handoff-restart-watcher,
on ned-box only, as the cron line
    * * * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/nc-systems/handoff/handoff-agent-seat-died-without-session-handoff-restart-watcher.py >> /home/nedlern/.claude/handoff-agent-seat-died-without-session-handoff-restart-watcher.log 2>&1
Cron starts it with cron's own short environment, so no agent-session's
variables reach a seat it restarts.

NEDSCHORUS_HANDOFF_AGENT_SEAT_DIED_WITHOUT_SESSION_HANDOFF_RESTART_WATCHER_STATE_DIRECTORY and
NEDSCHORUS_HANDOFF_AGENT_SEAT_DIED_WITHOUT_SESSION_HANDOFF_RESTART_WATCHER_LOG_DIRECTORY override where the
state and the log go: the seams the test suite uses.
"""

import argparse
import fcntl
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROGRAM = "handoff-agent-seat-died-without-session-handoff-restart-watcher"

REPOSITORY = Path(__file__).resolve().parent.parent.parent
RECOVERY_PROGRAM = REPOSITORY / "scripts" / "recover-crashed-seats.py"
LOGIN_RESTART_PROGRAM = REPOSITORY / "scripts" / "restart-live-seats-at-login.py"
MAC_WINDOW_OPENER_PROGRAM = REPOSITORY / "scripts" / "open-mac-window-from-ned-box.py"

LOG_DIRECTORY = Path("/home/nedlern/nedschorus-logs") / PROGRAM
STATE_DIRECTORY = Path("~/.local/state/nedschorus").expanduser()
STATE_DIRECTORY_ENVIRONMENT_VARIABLE = "NEDSCHORUS_HANDOFF_AGENT_SEAT_DIED_WITHOUT_SESSION_HANDOFF_RESTART_WATCHER_STATE_DIRECTORY"
LOG_DIRECTORY_ENVIRONMENT_VARIABLE = "NEDSCHORUS_HANDOFF_AGENT_SEAT_DIED_WITHOUT_SESSION_HANDOFF_RESTART_WATCHER_LOG_DIRECTORY"

CRASHED_VERDICTS = ("resume", "ignite")
RUNNING_VERDICT = "seat-already-running"
WAITING_HANDOFF_VERDICT = "defer-to-boot-ignition"
RECORDED_EXIT_VERDICT = "offer-after-recorded-exit"
# Two sightings a minute apart keep a run from acting on a seat that a launch,
# resupervise-seat.py or the login restart is bringing up at that moment.
CRASH_CONFIRMATION_SECONDS = 50
RESTART_LIMIT_SECONDS = 3600

# Words the user's window runs, for the attach step after a restart.
ATTACH_COMMAND = ("tmux", "-L", "{seat}", "attach", "-t", "{seat}")

RESTARTED_NOTICE_TEMPLATE = (
    "{seat} was restarted at {restarted_at}.\n"
    "Its agent-session stopped at about {died_at} without writing a handoff, so the "
    "crash watcher resumed its last conversation under a new supervisor. {seat} goes on "
    "with the work it was doing; nothing is needed from you.\n"
    "Record: {record}\n"
)

SECOND_CRASH_NOTICE_TEMPLATE = (
    "{seat} is down. Its agent-session stopped again at about {died_at} without writing "
    "a handoff. The crash watcher had restarted it at {earlier_restarted_at}, after it "
    "stopped at about {earlier_died_at}.\n"
    "The watcher restarts an agent-seat at most once an hour, so it left {seat} down: an "
    "agent-seat that stops twice within an hour is likely to stop again.\n"
    "Recommendation: find out why it stopped before you restart it. Its last "
    "conversation is the newest .jsonl file in {transcripts}.\n"
    "To restart it, run in a Terminal on your Mac:\n"
    "  ssh nedlern@ned-box 'cd ~/Projects/nedschorus && python3 scripts/recover-crashed-seats.py {seat}'\n"
    "then open its window with:\n"
    "  launch-claude-ubuntu {seat}\n"
    "Record: {record}\n"
)

RECOVERY_FAILED_NOTICE_TEMPLATE = (
    "{seat} is down: the crash watcher could not restart it. Its agent-session stopped "
    "at about {died_at} without writing a handoff, and "
    "scripts/recover-crashed-seats.py {seat} exited {exit_code}. It said:\n"
    "{recovery_output}\n"
    "The watcher does not try again for this crash. Follow what recover-crashed-seats.py "
    "said above. To retry by hand, run in a Terminal on your Mac:\n"
    "  ssh nedlern@ned-box 'cd ~/Projects/nedschorus && python3 scripts/recover-crashed-seats.py {seat}'\n"
    "then open its window with:\n"
    "  launch-claude-ubuntu {seat}\n"
    "Record: {record}\n"
)

ASSESSMENT_FAILED_NOTICE_TEMPLATE = (
    "The crash watcher could not check {seat}: {error}\n"
    "Until this is fixed the watcher cannot restart {seat} if it crashes. It will not "
    "tell you about this error again. Ask an agent on ned-box to fix it, giving it this "
    "notice.\n"
    "Record: {record}\n"
)

RUN_FAILED_NOTICE_TEMPLATE = (
    "The crash watcher on ned-box failed and is watching no agent-seat: {error}\n"
    "Until this is fixed, an agent-seat that crashes is not restarted. The watcher will "
    "not tell you about this error again. Ask an agent on ned-box to fix it, giving it "
    "this notice.\n"
    "Record: {record}\n"
)

WAITING_HANDOFF_NOTICE_TEMPLATE = (
    "{seat} is down, and the crash watcher did not restart it. Its supervisor stopped "
    "at about {died_at} while a handoff it had not acted on was waiting, so no successor "
    "started. The watcher restarts only an agent-session that crashed; a waiting handoff "
    "is the agent's own request for a successor, so it is left to you.\n"
    "To start {seat}'s successor from that handoff, run in a Terminal on your Mac (it "
    "starts the successor the handoff asks for, and does nothing if {seat} is already "
    "running):\n"
    "  ssh nedlern@ned-box 'cd ~/Projects/nedschorus && python3 scripts/recover-crashed-seats.py {seat}'\n"
    "then open its window with:\n"
    "  launch-claude-ubuntu {seat}\n"
    "Record: {record}\n"
)

RECORDED_EXIT_NOTICE_TEMPLATE = (
    "{seat} is down, and the crash watcher did not restart it. Its agent-session ended "
    "at about {died_at} with {exit_description}, and its supervisor recorded the exit and "
    "stopped instead of resuming it. A supervisor stops like this after several resumes "
    "that added no work, or when it has no terminal to resume on.\n"
    "Recommendation: read the end of its last conversation, the newest .jsonl file in "
    "{transcripts}, before you restart it.\n"
    "To restart it, run in a Terminal on your Mac. It asks \"{question}\"; answer y, and "
    "it {restart_effect}:\n"
    "  ssh -t nedlern@ned-box 'cd ~/Projects/nedschorus && python3 scripts/recover-crashed-seats.py {seat}'\n"
    "then open its window with:\n"
    "  launch-claude-ubuntu {seat}\n"
    "Record: {record}\n"
)

SHOW_NOTICE_ATTACH_PROMPT ="Press Enter to open {seat}'s session in this window."
SHOW_NOTICE_CLOSE_PROMPT = "Press Enter to close this window."


def load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def timestamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_timestamp(text):
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def clock_text(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def read_state(state_path: Path) -> dict:
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"seats": {}, "pending_notices": [], "reported_errors": []}
    state.setdefault("seats", {})
    state.setdefault("pending_notices", [])
    state.setdefault("reported_errors", [])
    return state


def write_state(state_path: Path, state: dict):
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = state_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(state_path)


class Watcher:
    """One run's decisions; every outside effect comes in as a callable, for the tests."""

    def __init__(self, *, state, now, boot_at, log_directory, assess, died_at_about,
                 transcripts_directory, recover, open_window, show_notice_words,
                 stopped_on_purpose=None, recorded_exit_question=None):
        self.state = state
        self.stopped_on_purpose = stopped_on_purpose or (lambda seat, detail: False)
        self.recorded_exit_question = recorded_exit_question or (
            lambda seat, exit_code: f"Restart {seat}? y/n")
        self.now = now
        self.boot_at = boot_at
        self.log_directory = log_directory
        self.assess = assess
        self.died_at_about = died_at_about
        self.transcripts_directory = transcripts_directory
        self.recover = recover
        self.open_window = open_window
        self.show_notice_words = show_notice_words

    @property
    def decisions_path(self) -> Path:
        return self.log_directory / "decisions.jsonl"

    def log(self, seat, decision, **details):
        self.log_directory.mkdir(parents=True, exist_ok=True)
        entry = {"at": timestamp(self.now), "seat": seat, "decision": decision, **details}
        with self.decisions_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, sort_keys=True) + "\n")

    def notice_path(self, seat, kind) -> Path:
        stamp = self.now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return self.log_directory / "notices" / f"{stamp}-{seat}-{kind}.txt"

    def write_notice(self, seat, kind, template, attach_seat=None, **fields) -> dict:
        path = self.notice_path(seat, kind)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(template.format(seat=seat, record=self.decisions_path, **fields),
                        encoding="utf-8")
        notice = {"path": str(path), "attach_seat": attach_seat}
        self.show(notice)
        return notice

    def show(self, notice) -> bool:
        exit_code, output = self.open_window(
            self.show_notice_words(notice["path"], notice.get("attach_seat")))
        if exit_code == 0:
            if notice in self.state["pending_notices"]:
                self.state["pending_notices"].remove(notice)
                self.log(None, "pending notice shown", notice=notice["path"])
            return True
        if notice not in self.state["pending_notices"]:
            # Logged once per notice; later runs retry quietly until the Mac answers.
            self.state["pending_notices"].append(notice)
            self.log(None, "notice not shown: the window on the Mac did not open; "
                     "retried on every run", notice=notice["path"], exit_code=exit_code,
                     opener_output=output)
        return False

    def run(self, seat_names):
        for notice in list(self.state["pending_notices"]):
            self.show(notice)
        for seat in seat_names:
            try:
                verdict, detail = self.assess(seat)
            except Exception as error:  # noqa: BLE001 - any failure here must reach the user
                self.report_assessment_failure(seat, f"{type(error).__name__}: {error}")
                continue
            self.decide(seat, verdict, detail)

    def report_assessment_failure(self, seat, error_text):
        self.log(seat, "could not assess", error=error_text)
        key = f"{seat}: {error_text}"
        if key in self.state["reported_errors"]:
            return
        self.state["reported_errors"].append(key)
        self.write_notice(seat, "assessment-failed", ASSESSMENT_FAILED_NOTICE_TEMPLATE,
                          error=error_text)

    def down_kind(self, seat, verdict, detail):
        """Return "crash" to restart, "for-the-user" to report, or None to leave alone."""
        if verdict in CRASHED_VERDICTS:
            return "crash"
        if verdict == WAITING_HANDOFF_VERDICT:
            return "for-the-user"
        if verdict == RECORDED_EXIT_VERDICT and not self.stopped_on_purpose(seat, detail):
            return "for-the-user"
        return None

    def mark_seen_running(self, record, moment):
        record["last_seen_running_at"] = timestamp(moment)
        for key in ("first_seen_crashed_at", "crash_handled", "handled_death_at"):
            record.pop(key, None)

    def ran_again_since_the_handled_death(self, seat, record) -> bool:
        """A supervisor poll later than the handled death shows the seat ran again."""
        handled = parse_timestamp(record.get("handled_death_at"))
        latest_poll = self.died_at_about(seat)
        if handled is None or latest_poll is None or latest_poll <= handled:
            return False
        self.mark_seen_running(record, latest_poll)
        self.log(seat, "ran again since its last handled crash; watching this one as a new crash",
                 supervisor_last_poll_at=timestamp(latest_poll))
        return True

    def mark_handled(self, seat, record):
        record["crash_handled"] = True
        latest_poll = self.died_at_about(seat)
        if latest_poll is not None:
            record["handled_death_at"] = timestamp(latest_poll)

    def decide(self, seat, verdict, detail):
        record = self.state["seats"].setdefault(seat, {})
        if verdict == RUNNING_VERDICT:
            self.mark_seen_running(record, self.now)
            record.pop("left_alone_verdict", None)
            return
        kind = self.down_kind(seat, verdict, detail)
        if kind is None:
            record.pop("first_seen_crashed_at", None)
            if record.get("left_alone_verdict") != verdict:
                record["left_alone_verdict"] = verdict
                self.log(seat, "left alone: not a crash this watcher restarts or reports",
                         verdict=verdict, detail=str(detail))
            return
        record.pop("left_alone_verdict", None)
        if record.get("crash_handled") and not self.ran_again_since_the_handled_death(seat, record):
            return
        last_seen_running = parse_timestamp(record.get("last_seen_running_at"))
        if last_seen_running is None or last_seen_running < self.boot_at:
            self.mark_handled(seat, record)
            self.log(seat, "left alone: down, but not seen running by this watcher "
                     "since the machine booted; the login restart or the user brings it back",
                     verdict=verdict)
            return
        first_seen_crashed = parse_timestamp(record.get("first_seen_crashed_at"))
        if first_seen_crashed is None:
            record["first_seen_crashed_at"] = timestamp(self.now)
            self.log(seat, "found down; acting if still down on a later run", verdict=verdict)
            return
        if (self.now - first_seen_crashed).total_seconds() < CRASH_CONFIRMATION_SECONDS:
            return
        self.mark_handled(seat, record)
        died_at = self.died_at_about(seat) or last_seen_running
        if kind == "for-the-user":
            self.report_down_for_the_user(seat, verdict, detail, died_at)
            return
        recent = [restart for restart in record.get("restarts", [])
                  if (self.now - parse_timestamp(restart["restarted_at"])).total_seconds()
                  < RESTART_LIMIT_SECONDS]
        if recent:
            earlier = recent[-1]
            self.log(seat, "not restarted: restarted less than an hour ago; user told",
                     died_at_about=timestamp(died_at), earlier_restart=earlier)
            self.write_notice(
                seat, "second-crash", SECOND_CRASH_NOTICE_TEMPLATE,
                died_at=clock_text(died_at),
                earlier_restarted_at=clock_text(parse_timestamp(earlier["restarted_at"])),
                earlier_died_at=clock_text(parse_timestamp(earlier["died_at_about"])),
                transcripts=self.transcripts_directory(seat))
            return
        exit_code, output = self.recover(seat)
        if exit_code == 0 and "ALREADY RUNNING" not in output:
            # Recovery exits 0 only once the seat's supervisor survived its settle: a sighting.
            self.mark_seen_running(record, self.now)
            record.setdefault("restarts", []).append(
                {"restarted_at": timestamp(self.now), "died_at_about": timestamp(died_at)})
            record["restarts"] = record["restarts"][-5:]
            self.log(seat, "restarted", died_at_about=timestamp(died_at),
                     recovery_output=output)
            self.write_notice(seat, "restarted", RESTARTED_NOTICE_TEMPLATE, attach_seat=seat,
                              restarted_at=clock_text(self.now), died_at=clock_text(died_at))
            return
        if exit_code == 0:
            self.mark_seen_running(record, self.now)
            self.log(seat, "not restarted: running again by the time recovery ran",
                     recovery_output=output)
            return
        self.log(seat, "recovery failed; user told", exit_code=exit_code,
                 died_at_about=timestamp(died_at), recovery_output=output)
        self.write_notice(seat, "recovery-failed", RECOVERY_FAILED_NOTICE_TEMPLATE,
                          died_at=clock_text(died_at), exit_code=exit_code,
                          recovery_output=output.strip() or "(nothing)")

    def report_down_for_the_user(self, seat, verdict, detail, died_at):
        if verdict == WAITING_HANDOFF_VERDICT:
            self.log(seat, "not restarted: a handoff waits that no supervisor acted on; user told",
                     died_at_about=timestamp(died_at), detail=str(detail))
            self.write_notice(seat, "waiting-handoff", WAITING_HANDOFF_NOTICE_TEMPLATE,
                              died_at=clock_text(died_at))
            return
        exit_code, recorded_at, session_id = detail[0], parse_timestamp(detail[1]) or died_at, detail[2]
        exit_description = ("an unknown exit code" if exit_code is None
                            else f"exit code {exit_code}")
        self.log(seat, "not restarted: its supervisor recorded an exit without resuming; "
                 "user told", exit_code=exit_code, recorded_at=timestamp(recorded_at))
        self.write_notice(seat, "recorded-exit", RECORDED_EXIT_NOTICE_TEMPLATE,
                          died_at=clock_text(recorded_at), exit_description=exit_description,
                          transcripts=self.transcripts_directory(seat),
                          question=self.recorded_exit_question(seat, exit_code),
                          restart_effect=(f"resumes {seat}'s last conversation" if session_id
                                          else f"starts {seat} as a fresh session"))


def run_command(command, environment=None):
    completed = subprocess.run(command, capture_output=True, text=True, env=environment,
                               check=False)
    return completed.returncode, (completed.stdout + completed.stderr).strip()


def recover_seat_in_clean_environment(seat, environment, run=run_command):
    # launch_seat in recover-crashed-seats.py removes agent-session and tmux variables on
    # both of its launch paths, and cron's environment carries none.
    return run([sys.executable, str(RECOVERY_PROGRAM), seat], environment)


def show_notice(path: str, attach_seat):
    """What the user's window runs: the notice, then the seat's session or nothing."""
    sys.stdout.write(Path(path).read_text(encoding="utf-8"))
    prompt = (SHOW_NOTICE_ATTACH_PROMPT.format(seat=attach_seat) if attach_seat
              else SHOW_NOTICE_CLOSE_PROMPT)
    try:
        input(f"\n{prompt}")
    except EOFError:
        pass
    if attach_seat:
        words = [word.format(seat=attach_seat) for word in ATTACH_COMMAND]
        os.execvp(words[0], words)
    return 0


def run_once(environment) -> int:
    state_directory = Path(environment.get(STATE_DIRECTORY_ENVIRONMENT_VARIABLE)
                           or STATE_DIRECTORY)
    log_directory = Path(environment.get(LOG_DIRECTORY_ENVIRONMENT_VARIABLE) or LOG_DIRECTORY)
    state_directory.mkdir(parents=True, exist_ok=True)
    with (state_directory / f"{PROGRAM}.lock").open("w") as lock_stream:
        try:
            fcntl.flock(lock_stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # A run that is still restarting a seat owns this minute.
            return 0
        try:
            return watch(environment, state_directory, log_directory)
        except Exception as error:  # noqa: BLE001 - a failed run must reach the user, not only cron's log
            report_run_failure(f"{type(error).__name__}: {error}", state_directory,
                               log_directory)
            raise


def report_run_failure(error_text, state_directory: Path, log_directory: Path):
    """Log the failure, and show the user a notice the first time this error is seen.

    The notice waits in the state every run reads, so a later run, failing or
    healthy, shows it once the Mac can be reached.
    """
    now = datetime.now(timezone.utc)
    reported_path = state_directory / f"{PROGRAM}-reported-run-failures.txt"
    reported = (reported_path.read_text(encoding="utf-8").splitlines()
                if reported_path.is_file() else [])
    state_path = state_directory / f"{PROGRAM}-state.json"
    try:
        state = read_state(state_path)
        state_readable = True
    except (OSError, ValueError):
        # The failure may be this file; the notice is then retried by the next failing run.
        state = {"seats": {}, "pending_notices": [], "reported_errors": []}
        state_readable = False
    watcher = Watcher(state=state, now=now, boot_at=now, log_directory=log_directory,
                      assess=None, died_at_about=None, transcripts_directory=None,
                      recover=None, open_window=open_mac_window,
                      show_notice_words=show_notice_words_for_window)
    watcher.log(None, "run failed", error=error_text)
    for notice in list(state["pending_notices"]):
        watcher.show(notice)
    if error_text not in reported:
        watcher.write_notice("watcher", "run-failed", RUN_FAILED_NOTICE_TEMPLATE,
                             error=error_text)
    saved = False
    if state_readable:
        try:
            write_state(state_path, state)
            saved = True
        except OSError as error:
            watcher.log(None, "could not save the watcher's state; a notice the Mac missed is "
                        "retried by the next failing run", error=f"{type(error).__name__}: {error}")
    if error_text not in reported and (saved or not state["pending_notices"]):
        with reported_path.open("a", encoding="utf-8") as stream:
            stream.write(error_text + "\n")


def open_mac_window(words):
    return run_command([sys.executable, str(MAC_WINDOW_OPENER_PROGRAM), *words])


def show_notice_words_for_window(path, attach_seat):
    words = [sys.executable, str(Path(__file__).resolve()), "--show-notice", path]
    return words + (["--then-attach", attach_seat] if attach_seat else [])


def stopped_on_purpose_predicate(supervisor, handoff_directory: Path):
    """Return a test of a recorded exit: a clean exit, or a dont-restart handoff its supervisor consumed."""
    def stopped_on_purpose(seat, detail):
        if detail[0] == 0:
            return True
        handoff_path = supervisor.handoff_file_path(handoff_directory, seat)
        if not handoff_path.is_file():
            return False
        fields = supervisor.parse_handoff_file(handoff_path)
        counter = supervisor.counter_from(fields)
        consumed = supervisor.read_supervisor_state(
            supervisor.supervisor_state_path(handoff_directory, seat)).get("consumed_counter")
        return bool(fields.get("dont-restart")) and counter is not None and counter == consumed
    return stopped_on_purpose


def watch(environment, state_directory: Path, log_directory: Path) -> int:
    login_restart = load_module("restart_live_seats_at_login", LOGIN_RESTART_PROGRAM)
    recovery = login_restart.recovery
    supervisor = login_restart.supervisor
    agents_root = recovery.default_agents_root()
    handoff_directory = recovery.default_handoff_directory()
    projects_root = Path("~/.claude/projects").expanduser()
    state_path = state_directory / f"{PROGRAM}-state.json"
    state = read_state(state_path)

    def assess(seat):
        return recovery.assess_seat(seat, agents_root, handoff_directory, projects_root)

    def died_at_about(seat):
        state_path_of_seat = supervisor.supervisor_state_path(handoff_directory, seat)
        return parse_timestamp(
            supervisor.read_supervisor_state(state_path_of_seat).get("last_poll_at"))

    def transcripts_directory(seat):
        return recovery.harness_project_directory(agents_root / seat, projects_root)

    def recover(seat):
        return recover_seat_in_clean_environment(seat, environment)

    watcher = Watcher(
        state=state, now=datetime.now(timezone.utc), boot_at=login_restart.machine_boot_time(),
        log_directory=log_directory, assess=assess, died_at_about=died_at_about,
        transcripts_directory=transcripts_directory, recover=recover,
        open_window=open_mac_window, show_notice_words=show_notice_words_for_window,
        stopped_on_purpose=stopped_on_purpose_predicate(supervisor, handoff_directory),
        recorded_exit_question=recovery.restart_question_for_a_seat_with_a_recorded_exit)
    try:
        watcher.run(recovery.list_agent_seat_names_with_agent_session_records(
            agents_root, handoff_directory, projects_root))
    finally:
        write_state(state_path, state)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog=PROGRAM, description=__doc__.splitlines()[0])
    parser.add_argument("--show-notice", metavar="FILE")
    parser.add_argument("--then-attach", metavar="SEAT")
    arguments = parser.parse_args(argv)
    if arguments.show_notice:
        return show_notice(arguments.show_notice, arguments.then_attach)
    if arguments.then_attach:
        parser.error("--then-attach needs --show-notice")
    if sys.platform != "linux":
        print(f"{PROGRAM}: refused: this program watches ned-box's agent-seats and runs only "
              "on ned-box, where cron starts it.", file=sys.stderr)
        return 2
    return run_once(dict(os.environ))


if __name__ == "__main__":
    sys.exit(main())
