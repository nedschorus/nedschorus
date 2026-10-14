#!/usr/bin/env python3
"""Read which agent-seats exist, and in what state, from the files they leave.

One module holds the rules the login restart, recovery and the task viewer
use to read an agent-seat's records, so that a later reader of a different
store replaces them in one place. It reads files only: whether a process is
running, a tmux session is up or a directory is in use stays with the
programs that probe for them.

The handoff-supervisor's own readers (file paths, liveness, state, exit
record, handoff fields) are defined in handoff-supervisor.py, which owns the
file names, and are re-exported here. The supervisor does not load this
module, because this module loads the supervisor.
"""

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

_HANDOFF_DIRECTORY = Path(__file__).resolve().parent
_SCRIPTS_DIRECTORY = _HANDOFF_DIRECTORY.parent.parent / "scripts"

_supervisor_spec = importlib.util.spec_from_file_location(
    "handoff_supervisor", _HANDOFF_DIRECTORY / "handoff-supervisor.py")
supervisor = importlib.util.module_from_spec(_supervisor_spec)
_supervisor_spec.loader.exec_module(supervisor)

_worth_resuming_spec = importlib.util.spec_from_file_location(
    "seat_transcript_worth_resuming",
    _SCRIPTS_DIRECTORY / "seat-transcript-worth-resuming.py")
worth_resuming = importlib.util.module_from_spec(_worth_resuming_spec)
_worth_resuming_spec.loader.exec_module(worth_resuming)

supervisor_state_path = supervisor.supervisor_state_path
supervisor_lock_path = supervisor.supervisor_lock_path
supervisor_state_paths = supervisor.supervisor_state_paths
agent_name_from_supervisor_file = supervisor.agent_name_from_supervisor_file
supervisor_liveness = supervisor.supervisor_liveness
read_supervisor_state = supervisor.read_supervisor_state
agent_exit_record_from_supervisor_state = supervisor.agent_exit_record_from_supervisor_state
handoff_file_path = supervisor.handoff_file_path
parse_handoff_file = supervisor.parse_handoff_file
counter_from = supervisor.counter_from
newest_real_transcript = worth_resuming.newest_real_transcript

# Independent supervisor cycles can differ by a full heartbeat interval.
LIVE_SET_WINDOW_SECONDS = 2 * supervisor.HEARTBEAT_INTERVAL_SECONDS
RUN_LOG_FILE_NAME = "restart-live-seats-at-login-log.txt"
# Boot instants are recomputed from clocks NTP can correct; match within a few seconds.
BOOT_MATCH_TOLERANCE_SECONDS = 5


def describe_gap(gap: timedelta) -> str:
    seconds = gap.total_seconds()
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= size:
            return f"{seconds / size:.0f}{unit}"
    return f"{seconds:.0f}s"


def read_supervisor_heartbeat(state_path: Path, now: datetime):
    """Return (stamp, empty string), or (None, failure reason)."""
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return None, f"not readable as JSON: {error.__class__.__name__}"
    stamped = state.get("last_poll_at") if isinstance(state, dict) else None
    if not stamped:
        return None, "it carries no last_poll_at"
    try:
        stamp = datetime.fromisoformat(stamped)
    except (TypeError, ValueError):
        return None, f"last_poll_at {stamped!r} does not parse"
    if stamp.tzinfo is None:
        return None, f"last_poll_at {stamped!r} carries no timezone"
    # A running supervisor may stamp just after now was sampled.
    if (stamp - now).total_seconds() > LIVE_SET_WINDOW_SECONDS:
        return None, f"last_poll_at {stamped} is in the future"
    return stamp, ""


def read_earlier_run_for_this_boot(handoff_directory: Path, boot_at: datetime):
    """Return (recorded stop, whether an earlier run exists for this boot)."""
    # The first readable line wins: restarted seats overwrite the original heartbeats.
    # A recorded null stop differs from no earlier run; unreadable logs must not block restart.
    try:
        lines = (handoff_directory / RUN_LOG_FILE_NAME).read_text(
            encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None, False
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        recorded_boot = entry.get("boot_at")
        if not isinstance(recorded_boot, str):
            continue
        try:
            boot_of_line = datetime.fromisoformat(recorded_boot)
        except ValueError:
            continue
        if boot_of_line.tzinfo is None:
            continue
        if abs((boot_of_line - boot_at).total_seconds()) > BOOT_MATCH_TOLERANCE_SECONDS:
            continue
        stop_of_line, readable = read_stop_of_run_log_line(entry)
        if not readable:
            continue
        return stop_of_line, True
    return None, False


def read_stop_of_run_log_line(entry: dict):
    """Return (stop, whether the line is readable)."""
    # A null stop is deliberate; a corrupt stop makes the whole line unreadable.
    if "stop_at" not in entry:
        return None, False
    recorded_stop = entry["stop_at"]
    if recorded_stop is None:
        return None, True
    if not isinstance(recorded_stop, str):
        return None, False
    try:
        stop_of_line = datetime.fromisoformat(recorded_stop)
    except ValueError:
        return None, False
    return (None, False) if stop_of_line.tzinfo is None else (stop_of_line, True)


def select_seats_live_at_the_stop(handoff_directory: Path, boot_at: datetime,
                                  now: datetime, recorded_stop=None):
    """Return (anchor, per-seat decisions, whether the anchor is the stop)."""
    if not handoff_directory.is_dir():
        return None, [], False
    readings = []
    for state_path in supervisor_state_paths(handoff_directory):
        seat = agent_name_from_supervisor_file(state_path)
        stamp, problem = read_supervisor_heartbeat(state_path, now)
        written_at = datetime.fromtimestamp(state_path.stat().st_mtime, timezone.utc)
        heartbeat_at = stamp if stamp is not None else written_at
        since_boot = heartbeat_at >= boot_at or written_at >= boot_at
        readings.append((seat, heartbeat_at, written_at, since_boot, problem))

    anchor = recorded_stop if recorded_stop is not None else max(
        (heartbeat_at for _, heartbeat_at, _, _, _ in readings
         if heartbeat_at < boot_at), default=None)
    # Post-boot writes can erase the true stop’s heartbeats; only a recorded stop remains trustworthy.
    restart_already_ran = (recorded_stop is None
                           and any(since_boot for _, _, _, since_boot, _ in readings))
    # Do not persist a degraded anchor as the stop for later runs.
    anchor_is_the_stop = anchor is not None and not restart_already_ran

    decisions = []
    for seat, heartbeat_at, written_at, since_boot, problem in readings:
        stands_in = (f"its heartbeat cannot be read ({problem}), so the file's last "
                     "write stands in for it; ") if problem else ""
        if since_boot:
            last_written = max(heartbeat_at, written_at)
            verdict, reason = "stamped-since-boot", (
                f"written {last_written.isoformat(timespec='seconds')}, since boot: "
                "a supervisor has run for it since then")
        elif (anchor - heartbeat_at).total_seconds() > LIVE_SET_WINDOW_SECONDS:
            verdict, reason = "not-running-at-the-stop", (
                f"last heartbeat {describe_gap(anchor - heartbeat_at)} before the stop")
        elif restart_already_ran:
            verdict, reason = "offer", (
                "the newest heartbeat left from before boot, but seats have been "
                "written since boot, so it may not be the stop: offer restart, "
                "park, or finished")
        else:
            verdict, reason = "restart", (
                f"last heartbeat {describe_gap(anchor - heartbeat_at)} before the "
                f"stop, which was {describe_gap(boot_at - anchor)} before boot")
        decisions.append((seat, verdict, stands_in + reason))
    return anchor, decisions, anchor_is_the_stop


def waiting_handoff_verdict(handoff_directory: Path, name: str, state_path: Path):
    """Return None when no handoff waits, else recovery's (verdict, detail)."""
    handoff_path = handoff_file_path(handoff_directory, name)
    if not handoff_path.is_file():
        return None
    fields = parse_handoff_file(handoff_path)
    counter = counter_from(fields)
    state = read_supervisor_state(state_path)
    consumed = state.get("consumed_counter")
    if counter is None:
        # The supervisor cannot consume a handoff without a valid counter; resuming would discard its request.
        return "refuse", (
            f"a handoff exists at {handoff_path} but its restart-counter is "
            "missing or unreadable, so no supervisor would ever consume it. "
            "Read it: if it is real, fix its restart-counter and relaunch "
            "plain; if it is scrap, delete it and rerun this recovery"
        )
    if consumed is None or counter > consumed:
        dont_restart = fields.get("dont-restart")
        if dont_restart:
            # Leave the handoff unconsumed so a by-hand launch still asks the supervisor’s restart question.
            return "seat-asked-to-be-consulted", (counter, dont_restart)
        return "defer-to-boot-ignition", (
            f"an unconsumed handoff waits (counter {counter}, consumed "
            f"{consumed}) — plain relaunch is correct; the supervisor's "
            "boot-ignition consumes it"
        )
    return None


def seat_of(list_id):
    """Return the seat name from a task list ID, leaving unfamiliar IDs whole."""
    # scripts/seat-shared-file-ship.py's seat_name_from_environment reads the same IDs
    # but returns None for an unfamiliar one; the two are kept apart on purpose.
    name = list_id
    if name.startswith("nedschorus-"):
        name = name[len("nedschorus-"):]
    if name.endswith("-tasks"):
        name = name[: -len("-tasks")]
    return name or list_id
