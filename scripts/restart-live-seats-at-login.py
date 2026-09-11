#!/usr/bin/env python3
"""restart-live-seats-at-login — at login, bring back the seats that were
running when this machine stopped (nedschorus#116).

Built in the order the #116 design lays out (§ The build, in order). This
first piece is the selection alone: which seats were running at the stop,
read from their supervisors' heartbeats. It launches nothing yet — until the
restart step lands, a run selects, records its line in the run log, and says
plainly that it launched nothing.

The rule, from docs/issues/116-fleet-survives-machine-restart-design.md
§ Ruled 2026-08-31 and its amendments:

  - Every supervisor stamps last_poll_at into
    ~/.claude/handoffs/<seat>-supervisor-state.json every
    HEARTBEAT_INTERVAL_SECONDS while it runs. Nothing else writes that file
    (every write is handoff-supervisor.py's write_supervisor_state; checked
    2026-09-11), so the file's modification time is a supervisor's last
    write too.
  - A seat's heartbeat is its last_poll_at. When that cannot be read —
    empty, cut off, no stamp, a stamp that does not parse, or one in the
    future — the file's last write stands in for it. A reboot in the middle
    of the supervisor's whole-file write leaves a file cut off at the stop,
    and the user's answer for that file (2026-09-11) was to try the resume:
    "Resume or continue works perfectly 99% of the time, so I'd try that."
    A file damaged long before the stop is judged like any old seat.
  - The anchor is the newest heartbeat before this boot; it approximates the
    moment the machine stopped.
  - A seat whose heartbeat or file was written since boot has had a
    supervisor since boot — recovered by hand, started by an earlier run of
    this program, or caught mid-write while it runs now. It is neither the
    anchor nor restarted.
  - Anchor within an hour before boot: the seats whose heartbeats are within
    LIVE_SET_WINDOW_SECONDS of it were running at the stop, and are
    restarted.
  - Anchor longer before boot: either nothing was running when the machine
    stopped, or it sat off a long time. Nothing is started silently; those
    seats are offered — restart, park, or finished.
  - Amended 2026-09-11 (review of 8b15919): once any seat has been written
    since boot, this boot's restart has already run, by hand or by this
    program. The seats that were running at the stop have stamped over
    their heartbeats from before boot, so the newest one left is no longer
    the stop, and anchoring on it would restart a seat that died earlier.
    So then nothing is restarted silently; the selection is offered.
  - A seat with no state file is not considered: the supervisor writes the
    file on its first launch and never deletes it, so a seat without one
    never ran under a supervisor.
  - Ruled 2026-09-11 (the user, on the amendment above: "sounds like we need
    a log here ... not a single file"): every run that is not a dry run
    appends one line to the run log beside the state files — the run, the
    boot, the stop, and the verdict per seat. A later run in the same boot
    reads the stop back from it instead of deriving it, and then the
    amendment above does not apply: the recorded stop is the stop whatever
    the restarted seats have stamped over since, so a seat that did not come
    back is restarted rather than merely offered. Lines are matched by boot.
    A line that cannot be read is skipped and a log that cannot be written is
    reported, because the record must never block the restart.

Usage:
  restart-live-seats-at-login.py [--dry-run] [--handoff-dir DIR]
"""

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_supervisor_spec = importlib.util.spec_from_file_location(
    "handoff_supervisor", Path(__file__).with_name("handoff-supervisor.py")
)
supervisor = importlib.util.module_from_spec(_supervisor_spec)
_supervisor_spec.loader.exec_module(supervisor)

# Ruled 2026-09-02: twice the heartbeat interval, not one. Supervisors stamp
# on independent cycles, so a live seat can trail the newest stamp by a full
# interval through timing alone; the two live seats of the 2026-09-01
# measurement were stamped 8 seconds apart.
LIVE_SET_WINDOW_SECONDS = 2 * supervisor.HEARTBEAT_INTERVAL_SECONDS
# Ruled 2026-09-02: an anchor within this long before boot means seats were
# running when the machine stopped; an older one asks rather than acts.
RECENT_ANCHOR_BEFORE_BOOT_SECONDS = 3600
SUPERVISOR_STATE_FILE_SUFFIX = "-supervisor-state.json"
# One JSON object per line, appended, never rewritten (user-ruled 2026-09-11:
# "a log ... not a single file"). It lives beside the state files, as
# recover-crashed-seats-log.txt does.
RUN_LOG_FILE_NAME = "restart-live-seats-at-login-log.txt"


def parse_darwin_kern_boottime(text: str) -> datetime:
    """`sysctl -n kern.boottime` on the Mac:
    "{ sec = 1789103232, usec = 162719 } Thu Sep 10 22:07:12 2026"."""
    match = re.search(r"\bsec = (\d+)", text)
    if match is None:
        raise ValueError(f"no sec field in kern.boottime output: {text!r}")
    return datetime.fromtimestamp(int(match.group(1)), timezone.utc)


def parse_uptime_since(text: str) -> datetime:
    """`uptime -s` on the box: local time, "2026-08-20 02:01:00"."""
    return datetime.strptime(text.strip(), "%Y-%m-%d %H:%M:%S").astimezone()


def machine_boot_time() -> datetime:
    """This machine's boot time — the reference the anchor is validated
    against (the design: previous shutdown time is not available on either
    machine, measured 2026-09-02)."""
    if sys.platform == "darwin":
        command, parse = ["sysctl", "-n", "kern.boottime"], parse_darwin_kern_boottime
    else:
        command, parse = ["uptime", "-s"], parse_uptime_since
    completed = subprocess.run(command, capture_output=True, text=True, check=True)
    return parse(completed.stdout)


def current_time() -> datetime:
    return datetime.now(timezone.utc)


def describe_gap(gap: timedelta) -> str:
    seconds = gap.total_seconds()
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= size:
            return f"{seconds / size:.0f}{unit}"
    return f"{seconds:.0f}s"


def read_supervisor_heartbeat(state_path: Path, now: datetime):
    """(stamp, "") when the state file carries a usable last_poll_at, else
    (None, why it cannot be read)."""
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
    # A supervisor stamping while this runs lands a moment after `now`; that
    # is a seat running now, not a stamp from the future.
    if (stamp - now).total_seconds() > LIVE_SET_WINDOW_SECONDS:
        return None, f"last_poll_at {stamped} is in the future"
    return stamp, ""


def read_recorded_stop_for_boot(handoff_directory: Path, boot_at: datetime):
    """The stop an earlier run in THIS boot recorded, or None.

    The evidence of when the machine stopped is the heartbeats from before
    boot, and the seats a first run brings back stamp over their own within
    ten seconds. So the first run writes the stop down and every later run in
    the same boot reads it back here (user-ruled 2026-09-11).

    Boots are matched as instants, not as strings: the box reads its boot
    time from `uptime -s` in local time, so the same boot can be written with
    a different offset. The first line recorded for this boot wins — it saw
    the least disturbed state. A line that cannot be read is skipped, and a
    log that cannot be read at all is simply no recorded stop: the record
    must never block the restart.
    """
    try:
        lines = (handoff_directory / RUN_LOG_FILE_NAME).read_text(
            encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        recorded_boot, recorded_stop = entry.get("boot_at"), entry.get("stop_at")
        if not isinstance(recorded_boot, str) or not isinstance(recorded_stop, str):
            continue
        try:
            boot_of_line = datetime.fromisoformat(recorded_boot)
            stop_of_line = datetime.fromisoformat(recorded_stop)
        except ValueError:
            continue
        if boot_of_line.tzinfo is None or stop_of_line.tzinfo is None:
            continue
        if boot_of_line == boot_at:
            return stop_of_line
    return None


def append_selection_to_run_log(handoff_directory: Path, boot_at: datetime,
                                anchor, anchor_is_the_stop: bool, decisions,
                                run_at: datetime):
    """One line per run, appended: the run, the boot, the stop, the anchor it
    worked from, and the verdict per seat.

    User-ruled 2026-09-11, a log and not a single overwritten file, so that
    the runs of one boot can be read in order afterwards. Dry runs do not
    write it: --dry-run promises to change nothing. A write that fails is
    reported and nothing more — a machine that has just booted needs its
    seats back more than it needs the record (the same rule as the recovery
    tool's append_to_recovery_log).

    A run that could not tell where the stop was — its derived anchor already
    stamped over by seats brought back earlier in this boot — records
    stop_at null, and keeps what it did work from in anchor_at. Otherwise the
    next run would read that degraded anchor back as the stop, drop the
    degradation because the stop was "recorded", and restart a seat that died
    before the real stop: the defect #318's review blocked, returning by the
    back door.
    """
    log_path = handoff_directory / RUN_LOG_FILE_NAME
    entry = {
        "run_at": run_at.isoformat(timespec="seconds"),
        "boot_at": boot_at.isoformat(),
        "stop_at": anchor.isoformat() if anchor_is_the_stop else None,
        "anchor_at": None if anchor is None else anchor.isoformat(),
        "seats": {seat: verdict for seat, verdict, _ in decisions},
    }
    try:
        handoff_directory.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry) + "\n")
    except OSError as error:
        print(f"restart-live-seats-at-login: could not append to {log_path}: {error}",
              file=sys.stderr)


def select_seats_live_at_the_stop(handoff_directory: Path, boot_at: datetime,
                                  now: datetime, recorded_stop=None):
    """(anchor, decisions, anchor_is_the_stop).

    The anchor is recorded_stop when an earlier run in this boot wrote one
    down, else the newest heartbeat before boot, or None. decisions is one
    (seat, verdict, reason) per supervisor state file; the verdicts are
    restart, offer, not-running-at-the-stop and stamped-since-boot.
    anchor_is_the_stop says whether the anchor can be written down as the
    moment the machine stopped — see append_selection_to_run_log."""
    if not handoff_directory.is_dir():
        return None, [], False
    readings = []
    for state_path in sorted(handoff_directory.glob(f"*{SUPERVISOR_STATE_FILE_SUFFIX}")):
        seat = state_path.name[:-len(SUPERVISOR_STATE_FILE_SUFFIX)]
        stamp, problem = read_supervisor_heartbeat(state_path, now)
        written_at = datetime.fromtimestamp(state_path.stat().st_mtime, timezone.utc)
        heartbeat_at = stamp if stamp is not None else written_at
        since_boot = heartbeat_at >= boot_at or written_at >= boot_at
        readings.append((seat, heartbeat_at, written_at, since_boot, problem))

    anchor = recorded_stop if recorded_stop is not None else max(
        (heartbeat_at for _, heartbeat_at, _, _, _ in readings
         if heartbeat_at < boot_at), default=None)
    anchor_is_recent = (anchor is not None
                        and (boot_at - anchor).total_seconds()
                        <= RECENT_ANCHOR_BEFORE_BOOT_SECONDS)
    # The 2026-09-11 amendment degrades a restart to an offer once any seat
    # has been written since boot, because the anchor derived then may no
    # longer be the stop. A stop read back from the run log is not derived,
    # so there is nothing to degrade: a seat still stamped at the recorded
    # stop is one that did not come back, and it is restarted.
    restart_already_ran = (recorded_stop is None
                           and any(since_boot for _, _, _, since_boot, _ in readings))
    # The same condition, read the other way: a derived anchor that seats
    # brought back since boot may have stamped over is not the stop, and must
    # not be recorded as one.
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
        elif not anchor_is_recent:
            verdict, reason = "offer", (
                f"running at a stop {describe_gap(boot_at - anchor)} before boot, "
                "too long to restart silently: offer restart, park, or finished")
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Select, from supervisor heartbeats, the seats that were "
                    "running when this machine stopped.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="report the selection and change nothing at all, "
                             "the run log included")
    parser.add_argument("--handoff-dir", type=Path,
                        default=Path("~/.claude/handoffs").expanduser(),
                        help="where the supervisor state files and the run log live")
    arguments = parser.parse_args(argv)

    boot_at, now = machine_boot_time(), current_time()
    log_path = arguments.handoff_dir / RUN_LOG_FILE_NAME
    recorded_stop = read_recorded_stop_for_boot(arguments.handoff_dir, boot_at)
    anchor, decisions, anchor_is_the_stop = select_seats_live_at_the_stop(
        arguments.handoff_dir, boot_at, now, recorded_stop=recorded_stop)
    if not arguments.dry_run:
        append_selection_to_run_log(arguments.handoff_dir, boot_at, anchor,
                                    anchor_is_the_stop, decisions, now)

    print("restart-live-seats-at-login: "
          + ("dry run, the selection only; nothing is launched and nothing is recorded"
             if arguments.dry_run else "the selection"))
    print(f"  boot {boot_at.isoformat(timespec='seconds')}")
    if anchor is None:
        print("  no heartbeat before boot: no supervisor was running when the machine stopped")
    elif recorded_stop is not None:
        print(f"  the stop: {anchor.isoformat(timespec='seconds')}, "
              f"{describe_gap(boot_at - anchor)} before boot, read back from "
              f"{log_path} — an earlier run in this boot recorded it")
    else:
        print(f"  the stop: newest heartbeat before boot "
              f"{anchor.isoformat(timespec='seconds')}, "
              f"{describe_gap(boot_at - anchor)} before boot")
    if recorded_stop is None and any(verdict == "stamped-since-boot"
                                     for _, verdict, _ in decisions):
        print("  seats have been written since boot: this boot's restart has already "
              "run and left no line in the run log, so nothing is restarted silently "
              "and no stop is recorded for the runs after this one")
    for seat, verdict, reason in decisions:
        print(f"  {seat}: {verdict} — {reason}")
    if not arguments.dry_run:
        print(f"  recorded in {log_path}; the restart step (nedschorus#116, build "
              "step 4) is not built yet, so this run launched nothing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
