#!/usr/bin/env python3
"""restart-live-seats-at-login — at login, bring back the seats that were
running when this machine stopped (nedschorus#116).

Built in the order the #116 design lays out (§ The build, in order). The
selection first: which seats were running at the stop, read from their
supervisors' heartbeats. Then the restart step (build step 4): each seat the
selection decided to restart is handed to recover-crashed-seats.py, one
subprocess per seat, which relaunches it under a supervisor — on the Mac in
its own iTerm window (--open-iterm-window-per-seat, build step 3) — and waits
for it to come up. A run records its line in the run log, with the seats that
came up beside the verdicts, and exits nonzero when a seat it decided to
restart did not come back. A seat the selection only offers is not launched:
the run says how to bring it back by hand. Parking a seat that could not be
brought back, and asking about it in a window, is nedschorus#242 change 3 and
is not built; until then the failed seat is reported and left down.

On the Mac this program is run at login by a LaunchAgent, installed by
install-restart-live-seats-at-login-launch-agent.py, and it has a second job
there (the #116 design's window role; user-ruled 2026-09-14, box seats are
not reconnected by hand): every login has lost the Mac's windows onto the
box's seats, though the seats themselves run on. So on the Mac, after its
own seats, a run asks the box over ssh which seats are alive and opens an
iTerm window onto each, running launch-claude-ubuntu, which attaches. When
the box does not answer — it may be rebooting too — the run retries for a
bounded time and then reports the box's windows as missing, with the by-hand
command, rather than opening nothing quietly. On the box this job does not
exist: the box has no display.

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
    back is restarted rather than merely offered. Lines are matched to this
    boot within a few seconds, because each machine recomputes its boot
    instant from a clock NTP may have stepped since. Each line records what
    came up as well as what was decided — a decided restart can fail to come
    up — so a decision is never read as an outcome.
    A line that cannot be read is skipped and a log that cannot be written is
    reported, because the record must never block the restart.

Usage:
  restart-live-seats-at-login.py [--dry-run] [--handoff-dir DIR]
"""

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

_supervisor_spec = importlib.util.spec_from_file_location(
    "handoff_supervisor", Path(__file__).with_name("handoff-supervisor.py")
)
supervisor = importlib.util.module_from_spec(_supervisor_spec)
_supervisor_spec.loader.exec_module(supervisor)

# The recovery tool is what launches a seat (build step 4 runs step 3): this
# program runs it as a subprocess, one per seat, and reads its report. The
# import is for the report markers only — a report carrying one of them is a
# seat that did not come back — so the two programs agree on what a failure
# looks like without this one parsing free text.
RECOVERY_TOOL_PATH = Path(__file__).with_name("recover-crashed-seats.py")
_recovery_spec = importlib.util.spec_from_file_location(
    "recover_crashed_seats", RECOVERY_TOOL_PATH)
recovery = importlib.util.module_from_spec(_recovery_spec)
_recovery_spec.loader.exec_module(recovery)

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
# A run log line is matched to this boot within a few seconds rather than
# exactly, because neither machine stores its boot instant — both recompute it
# from a realtime clock that NTP may have corrected since (measured
# 2026-09-11, in review). The Mac adjusts kern.boottime when the clock is
# corrected: the same boot read sec=1789103232 usec=162719 in the morning and
# usec=223179 that evening. The box computes `uptime -s` as now minus
# /proc/uptime and prints whole seconds (procps-ng 4.0.4, NTP active), so a
# clock step of half a second flips the second it prints — and a step right
# after boot is exactly when this program runs. Five seconds is far below the
# shortest interval two real boots can be apart, shutdown and POST included,
# so the tolerance cannot reach a different boot.
BOOT_MATCH_TOLERANCE_SECONDS = 5


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


def read_earlier_run_for_this_boot(handoff_directory: Path, boot_at: datetime):
    """(the stop an earlier run in THIS boot recorded, whether there was one).

    Two answers rather than one, because they come apart: a run that could not
    tell where the stop was records a line carrying no stop, so "no recorded
    stop" and "no earlier run" are different states. The selection only needs
    the first; the report needs both, or it says this boot's restart "left no
    line in the run log" about a boot whose log holds exactly that line (found
    in review of bbb66d4, where the verdicts were right and only the sentence
    was false).

    The evidence of when the machine stopped is the heartbeats from before
    boot, and the seats a first run brings back stamp over their own within
    ten seconds. So the first run writes the stop down and every later run in
    the same boot reads it back here (user-ruled 2026-09-11).

    Boots are matched as instants, not as strings: the box reads its boot
    time from `uptime -s` in local time, so the same boot can be written with
    a different offset. They are matched within BOOT_MATCH_TOLERANCE_SECONDS
    rather than exactly, because each machine recomputes the instant from a
    clock that may have been corrected since. The first line recorded for this
    boot wins outright — it saw the least disturbed state, and it settles the
    stop even when it carries none. A line that cannot be read is skipped and
    is not evidence of anything, and a log that cannot be read at all is
    simply no earlier run: the record must never block the restart.
    """
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
    """(the stop this line carries, whether the line could be read at all).

    A null stop is deliberate — a run that could not tell where the stop was
    records exactly that — so it reads fine and carries None. A stop that is
    present but corrupt is a line nobody wrote on purpose: it reads as
    unreadable, and the caller skips the whole line rather than taking its
    silence for a deliberate one.
    """
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


def append_selection_to_run_log(handoff_directory: Path, boot_at: datetime,
                                anchor, anchor_is_the_stop: bool, decisions,
                                run_at: datetime, launched=None, box_windows=None):
    """One line per run, appended: the run, the boot, the stop, the anchor it
    worked from, the verdict per seat, and what was actually launched.

    A verdict is what the run decided, not what happened, and the two are not
    the same thing: a decided restart can fail to come up. So `launched`
    records the outcome beside the decision — the seats that came up, an
    empty list when the run launched and none came back or had nothing to
    launch, and null only when the caller did not launch at all. A cold
    reader can then tell a seat that was never launched from one whose
    launch failed, which a verdict alone cannot say.

    User-ruled 2026-09-11, a log and not a single overwritten file, so that
    the runs of one boot can be read in order afterwards. Dry runs do not
    write it: --dry-run promises to change nothing. A write that fails is
    reported and nothing more — a machine that has just booted needs its
    seats back more than it needs the record (the same rule as the recovery
    tool's append_to_recovery_log). It returns whether it wrote, so the
    report can say what actually happened rather than announcing a record
    that is not there.

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
        "launched": None if launched is None else sorted(launched),
        # The window role's outcome (the Mac only): null when it was not
        # attempted, else whether the box answered and the seats a window
        # was opened onto, so a later reader can tell "no live box seats"
        # from "the box never answered".
        "box_windows": None if box_windows is None or not box_windows.get("attempted")
        else {"answered": box_windows["answered"],
              "opened": sorted(box_windows["opened"])},
    }
    try:
        handoff_directory.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry) + "\n")
    except OSError as error:
        print(f"restart-live-seats-at-login: could not append to {log_path}: {error}",
              file=sys.stderr)
        return False
    return True


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


# The window role's pieces, all beside this program: the launcher that attaches
# a window to a box seat (and reconnects when the box drops), and the opener,
# the only sanctioned way to open an iTerm window running a command.
BOX_LAUNCHER_PATH = Path(__file__).with_name("launch-claude-ubuntu")
WINDOW_OPENER_PATH = Path(__file__).with_name("open-iterm-window-running-command")
# ssh reaches the box the way launch-claude-ubuntu does. Under the LaunchAgent
# there is no terminal, so ssh must never wait on a prompt: BatchMode.
BOX_QUERY_SSH_OPTIONS = ("-o", "BatchMode=yes", "-o", "ConnectTimeout=10")
# When both machines rebooted, the box may still be coming up while the Mac
# logs in; a connection-level failure (ssh exit 255) is retried this long
# before the windows are reported missing. Any other failure is not retried:
# the box answered, and the answer is what the report says.
BOX_QUERY_DEADLINE_SECONDS = 150.0
BOX_QUERY_RETRY_SECONDS = 5.0
# One name per line: every session on every per-seat tmux server (and the
# default server, where seats launched before per-seat servers live), kept
# only when a seat home of that name exists — fleet-anchor, the box's tmux
# keep-alive session, has none. A seat's after-exit shell keeps its session
# name and counts: that is where the user typed exit, and the window belongs
# there. The listing is the one launch-claude-ubuntu's usage() prints.
LIST_LIVE_BOX_SEATS_REMOTE_COMMAND = (
    'for seat_socket_path in "${TMUX_TMPDIR:-/tmp}/tmux-$(id -u)"/*; do '
    '[ -S "$seat_socket_path" ] || continue; '
    'tmux -S "$seat_socket_path" list-sessions -F "#{session_name}" 2>/dev/null; '
    'done | sort -u | while read -r seat_name; do '
    '[ -d "${NEDSCHORUS_AGENTS_ROOT:-$HOME/agents}/$seat_name" ] && echo "$seat_name"; '
    'done; true'
)


def agent_box() -> str:
    """The ssh destination for the box, as launch-claude-ubuntu resolves it."""
    return os.environ.get("NEDSCHORUS_AGENT_BOX", "ned")


def box_seat_query_command(box: str = None) -> list:
    return ["ssh", *BOX_QUERY_SSH_OPTIONS, box or agent_box(), LIST_LIVE_BOX_SEATS_REMOTE_COMMAND]


def ask_the_box_which_seats_are_alive(run=subprocess.run, deadline_seconds=BOX_QUERY_DEADLINE_SECONDS,
                                      retry_seconds=BOX_QUERY_RETRY_SECONDS, sleep=time.sleep,
                                      monotonic=time.monotonic):
    """(seats, detail): the live seat names the box reported, or None with why
    not. ssh exit 255 — the box down, not up yet, unreachable — is retried
    until the deadline; any other nonzero exit is the box's own answer and
    is returned at once. A run that cannot start ssh at all is a failure of
    the same kind as an answer, reported, not retried."""
    started = monotonic()
    attempts = 0
    while True:
        attempts += 1
        try:
            finished = run(box_seat_query_command(), stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True)
        except OSError as error:
            return None, f"could not run ssh: {error}"
        if finished.returncode == 0:
            return sorted({line.strip() for line in finished.stdout.splitlines()
                           if line.strip()}), f"answered on attempt {attempts}"
        if finished.returncode != 255:
            return None, (f"the box answered with exit {finished.returncode}: "
                          f"{finished.stderr.strip()}")
        if monotonic() - started >= deadline_seconds:
            return None, (f"unreachable for {int(deadline_seconds)}s over {attempts} "
                          f"attempt(s) (ssh exit 255: {finished.stderr.strip()})")
        sleep(retry_seconds)


def window_command_for_box_seat(seat: str) -> list:
    """The opener, the launcher by absolute path, the seat: two plain words
    after the opener, so its multi-argument form is safe."""
    return [str(WINDOW_OPENER_PATH), str(BOX_LAUNCHER_PATH), seat]


def open_windows_onto_box_seats(seats, run=subprocess.run):
    """(opened, reports): the seats a window was opened onto, and one
    (seat, opened, detail) per attempt. One seat's failure leaves the rest
    to be tried."""
    opened, reports = [], []
    for seat in seats:
        try:
            finished = run(window_command_for_box_seat(seat), stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True)
        except OSError as error:
            reports.append((seat, False, f"could not run the opener: {error}"))
            continue
        detail = (finished.stdout.strip() or finished.stderr.strip())
        if finished.returncode == 0:
            opened.append(seat)
            reports.append((seat, True, detail))
        else:
            reports.append((seat, False, f"opener exit {finished.returncode}: {detail}"))
    return opened, reports


def restore_box_windows(dry_run: bool, platform: str = sys.platform, run=subprocess.run,
                        sleep=time.sleep, monotonic=time.monotonic):
    """The window role, on the Mac only. Returns a dict: attempted (False on
    the box, and nothing else is set), answered (whether the box reported),
    detail (how the query went), seats (what it reported), opened (the
    seats a window was opened onto), reports (per window). A dry run asks
    the box once — a read — and opens nothing."""
    if platform != "darwin":
        return {"attempted": False}
    seats, detail = ask_the_box_which_seats_are_alive(
        run=run, deadline_seconds=0 if dry_run else BOX_QUERY_DEADLINE_SECONDS,
        sleep=sleep, monotonic=monotonic)
    outcome = {"attempted": True, "answered": seats is not None, "detail": detail,
               "seats": seats, "opened": [], "reports": []}
    if seats and not dry_run:
        outcome["opened"], outcome["reports"] = open_windows_onto_box_seats(seats, run=run)
    return outcome


def recovery_command_for_seat(seat: str, handoff_directory: Path,
                              platform: str = sys.platform) -> list:
    """The recovery tool's command line for one seat, as this program runs
    it. On the Mac the seat is born attached in its own iTerm window (build
    step 3): the recovery tool itself refuses that flag anywhere else, so it
    is passed only on darwin. The handoff directory is passed through so a
    run against a test directory recovers against that directory too; the
    agents root is not, because this program has no argument for it — both
    programs resolve ${NEDSCHORUS_AGENTS_ROOT:-~/agents} the same way."""
    command = [sys.executable, str(RECOVERY_TOOL_PATH), seat,
               "--handoff-dir", str(handoff_directory)]
    if platform == "darwin":
        command.append("--open-iterm-window-per-seat")
    return command


def seat_came_up(exit_code, report: str) -> bool:
    """Whether one recovery run brought its seat back. The recovery tool
    exits nonzero when every seat it was given failed — one seat, so this
    seat — and marks each failed report; either says the seat is down."""
    return exit_code == 0 and not any(
        marker in report for marker in recovery.SEAT_NOT_RECOVERED_REPORT_MARKERS)


def launch_seats_decided_restart(decisions, handoff_directory: Path,
                                 run=subprocess.run, platform: str = sys.platform):
    """Run the recovery tool for every seat whose verdict is restart, in the
    order decided, and return (launched, reports): the seats that came up,
    and one (seat, came_up, report) per attempt. Each seat is its own
    subprocess, so one seat's failure — a refusal, a launch that failed, a
    seat that never came up — leaves the seats after it to be tried. The
    recovery tool's stdout is its report, one line per seat; stderr is
    passed through to this program's stderr. A recovery tool that cannot be
    run at all is a failure of every seat, reported per seat so the run log
    and the report still say which seats are down."""
    launched, reports = [], []
    for seat, verdict, _ in decisions:
        if verdict != "restart":
            continue
        command = recovery_command_for_seat(seat, handoff_directory, platform)
        try:
            finished = run(command, stdout=subprocess.PIPE, text=True)
        except OSError as error:
            reports.append((seat, False, f"could not run {command[1]}: {error}"))
            continue
        report = finished.stdout.strip()
        if not report:
            # An argparse refusal prints usage to stderr and nothing to
            # stdout; the exit code is then the only thing to record.
            report = f"(no report; exit {finished.returncode}, see stderr)"
        came_up = seat_came_up(finished.returncode, report)
        if came_up:
            launched.append(seat)
        reports.append((seat, came_up, report))
    return launched, reports


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Bring back the seats that were running when this machine "
                    "stopped, selected from their supervisors' heartbeats.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="report the selection and what would be launched, and "
                             "change nothing at all, the run log included")
    parser.add_argument("--handoff-dir", type=Path,
                        default=Path("~/.claude/handoffs").expanduser(),
                        help="where the supervisor state files and the run log live")
    arguments = parser.parse_args(argv)

    boot_at, now = machine_boot_time(), current_time()
    log_path = arguments.handoff_dir / RUN_LOG_FILE_NAME
    recorded_stop, an_earlier_run_ran = read_earlier_run_for_this_boot(
        arguments.handoff_dir, boot_at)
    anchor, decisions, anchor_is_the_stop = select_seats_live_at_the_stop(
        arguments.handoff_dir, boot_at, now, recorded_stop=recorded_stop)
    # Launch first, record after: the line records what came up, and a run
    # killed mid-launch then leaves no line, which the next run reads as
    # "already run, offer everything" — the direction that starts nothing
    # twice. Dry runs launch nothing and record nothing.
    if arguments.dry_run:
        launched, reports = None, []
    else:
        launched, reports = launch_seats_decided_restart(decisions, arguments.handoff_dir)
    # Then the windows onto the box's seats: every login has lost them,
    # whatever the verdicts above, so this runs on every Mac run.
    box_windows = restore_box_windows(arguments.dry_run)
    recorded = None if arguments.dry_run else append_selection_to_run_log(
        arguments.handoff_dir, boot_at, anchor, anchor_is_the_stop, decisions, now,
        launched=launched, box_windows=box_windows)

    print("restart-live-seats-at-login: "
          + ("dry run, the selection only; nothing is launched and nothing is recorded"
             if arguments.dry_run else "the selection, and what came of it"))
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
        # Three states, not two: no line for this boot at all, or a line from
        # a run that could not tell where the stop was either. Saying "left no
        # line" about the second is false, and the log is what an investigator
        # reads (found in review of bbb66d4).
        print("  seats have been written since boot: this boot's restart has already run "
              + (f"and an earlier run recorded no stop in {log_path}"
                 if an_earlier_run_ran else "and left no line in the run log")
              + ", so nothing is restarted silently and no stop is recorded for "
                "the runs after this one")
    outcome_by_seat = {seat: (came_up, report) for seat, came_up, report in reports}
    for seat, verdict, reason in decisions:
        print(f"  {seat}: {verdict} — {reason}")
        if verdict == "restart" and arguments.dry_run:
            print("    would run: " + " ".join(
                recovery_command_for_seat(seat, arguments.handoff_dir)))
        elif verdict == "restart":
            came_up, report = outcome_by_seat[seat]
            print(f"    {'came up' if came_up else 'DID NOT COME BACK'}: {report}")
        elif verdict == "offer":
            # The command this run would have used, so the hint names the
            # same handoff directory the run did (PR #354 review, finding 2).
            print("    not launched; to bring it back by hand: " + " ".join(
                recovery_command_for_seat(seat, arguments.handoff_dir)[1:]))
    windows_not_opened = []
    if box_windows["attempted"]:
        box = agent_box()
        if not box_windows["answered"]:
            print(f"  box {box}: did not answer ({box_windows['detail']}) — its windows are "
                  f"missing; when it is back, one window per seat by hand: "
                  f"{BOX_LAUNCHER_PATH} <seat>")
        elif not box_windows["seats"]:
            print(f"  box {box}: no live seats, so no windows to open")
        elif arguments.dry_run:
            print(f"  box {box}: would open a window onto each live seat: "
                  + ", ".join(box_windows["seats"]))
        else:
            for seat, opened, detail in box_windows["reports"]:
                if opened:
                    print(f"  box {box}: window opened onto {seat} ({detail})")
                else:
                    windows_not_opened.append(seat)
                    print(f"  box {box}: NO WINDOW onto {seat} — {detail}; by hand: "
                          f"{BOX_LAUNCHER_PATH} {seat}")
    did_not_come_back = [seat for seat, came_up, _ in reports if not came_up]
    if recorded is True:
        print(f"  recorded in {log_path}")
    elif recorded is False:
        print(f"  could not append this run to {log_path} (the reason is on stderr), "
              "so the runs after it in this boot will not read its stop back")
    if did_not_come_back:
        print(f"  {len(did_not_come_back)} seat(s) decided for restart did not come "
              f"back: {', '.join(did_not_come_back)} — each is left down and reported "
              "above (parking it and asking is nedschorus#242 change 3, not built)")
    if windows_not_opened:
        print(f"  {len(windows_not_opened)} box window(s) could not be opened: "
              f"{', '.join(windows_not_opened)} — reported above")
    return 1 if did_not_come_back or windows_not_opened else 0


if __name__ == "__main__":
    sys.exit(main())
