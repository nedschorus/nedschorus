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
iTerm window onto each, running launch-claude-ubuntu, which attaches. A box
seat that already has a window attached since the Mac booted gets no second
one: recovery on the box opens a window on the Mac after each seat it brings
up, and when the box restarts its seats while the Mac is logged in, that
window can come first. When the box does not answer — it may be rebooting
too — the run retries for a bounded time and then reports the box's windows
as missing, with the by-hand command, rather than opening nothing quietly.
Each seat runs on a tmux server named after it, which launch-claude-ubuntu
creates when it starts the seat, and an older seat may still run on the
shared `default` server, which can hold several. When the box's tmux fails on a seat's own server or session for any
reason but that server or session being gone, that seat alone gets no window,
and the report names it with tmux's error and the command that opens its
window. When tmux fails on the `default` server, which seats it holds is
unknown, so no box seat gets a window, and the report says the box did not
answer, quoting tmux's error. On
the box this job asks the Mac for no windows itself: recovery opens a window
on the Mac after each seat it brings up, and a window that does not open
makes this run exit nonzero, with the seat counted as come up.

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
  - The seats whose heartbeats are within LIVE_SET_WINDOW_SECONDS of the
    anchor were running at the stop, and are restarted — however long before
    boot the anchor is. Ruled 2026-09-15 (the user: "I'd just restart
    anything that looks like it was accidentally shut down at roughly the
    time of shutdown. It's easy to shut down an agent that isn't useful"),
    replacing the 2026-09-02 rule that an anchor more than an hour before
    boot only offered its seats: a seat restarted wrongly costs one stop,
    a seat left down costs its work.
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
from datetime import datetime, timezone
from pathlib import Path

_supervisor_spec = importlib.util.spec_from_file_location(
    "handoff_supervisor", Path(__file__).resolve().parent.parent
    / "nc-systems" / "handoff" / "handoff-supervisor.py"
)
supervisor = importlib.util.module_from_spec(_supervisor_spec)
_supervisor_spec.loader.exec_module(supervisor)

# Share recovery report markers so failures do not depend on parsing free text.
RECOVERY_TOOL_PATH = Path(__file__).with_name("recover-crashed-seats.py")
_recovery_spec = importlib.util.spec_from_file_location(
    "recover_crashed_seats", RECOVERY_TOOL_PATH)
recovery = importlib.util.module_from_spec(_recovery_spec)
_recovery_spec.loader.exec_module(recovery)

_records_reader_spec = importlib.util.spec_from_file_location(
    "agent_seat_state_records_reader", Path(__file__).resolve().parent.parent
    / "nc-systems" / "handoff" / "agent-seat-state-records-reader.py"
)
records_reader = importlib.util.module_from_spec(_records_reader_spec)
_records_reader_spec.loader.exec_module(records_reader)
_tmux_error_pattern_spec = importlib.util.spec_from_file_location(
    "tmux_target_or_server_does_not_exist_error_pattern_common",
    Path(__file__).resolve().parent.parent / "nc-systems" / "general-tools"
    / "tmux-target-or-server-does-not-exist-error-pattern-common.py"
)
tmux_error_pattern = importlib.util.module_from_spec(_tmux_error_pattern_spec)
_tmux_error_pattern_spec.loader.exec_module(tmux_error_pattern)
LIVE_SET_WINDOW_SECONDS = records_reader.LIVE_SET_WINDOW_SECONDS
RUN_LOG_FILE_NAME = records_reader.RUN_LOG_FILE_NAME
BOOT_MATCH_TOLERANCE_SECONDS = records_reader.BOOT_MATCH_TOLERANCE_SECONDS
describe_gap = records_reader.describe_gap
read_supervisor_heartbeat = records_reader.read_supervisor_heartbeat
read_earlier_run_for_this_boot = records_reader.read_earlier_run_for_this_boot
read_stop_of_run_log_line = records_reader.read_stop_of_run_log_line
select_seats_live_at_the_stop = records_reader.select_seats_live_at_the_stop


def parse_darwin_kern_boottime(text: str) -> datetime:
    match = re.search(r"\bsec = (\d+)", text)
    if match is None:
        raise ValueError(f"no sec field in kern.boottime output: {text!r}")
    return datetime.fromtimestamp(int(match.group(1)), timezone.utc)


def parse_uptime_since(text: str) -> datetime:
    """Parse uptime -s in the machine’s local timezone."""
    return datetime.strptime(text.strip(), "%Y-%m-%d %H:%M:%S").astimezone()


def machine_boot_time() -> datetime:
    if sys.platform == "darwin":
        command, parse = ["sysctl", "-n", "kern.boottime"], parse_darwin_kern_boottime
    else:
        command, parse = ["uptime", "-s"], parse_uptime_since
    completed = subprocess.run(command, capture_output=True, text=True, check=True)
    return parse(completed.stdout)


def current_time() -> datetime:
    return datetime.now(timezone.utc)


def append_selection_to_run_log(handoff_directory: Path, boot_at: datetime,
                                anchor, anchor_is_the_stop: bool, decisions,
                                run_at: datetime, launched=None, box_windows=None):
    """Append decisions and launch outcomes; return whether the write succeeded."""
    # Record no stop when the derived anchor is degraded, or later runs may restart older dead seats.
    # A null launched field means no attempt; an empty list means an attempt brought no seats up.
    log_path = handoff_directory / RUN_LOG_FILE_NAME
    entry = {
        "run_at": run_at.isoformat(timespec="seconds"),
        "boot_at": boot_at.isoformat(),
        "stop_at": anchor.isoformat() if anchor_is_the_stop else None,
        "anchor_at": None if anchor is None else anchor.isoformat(),
        "seats": {seat: verdict for seat, verdict, _ in decisions},
        "launched": None if launched is None else sorted(launched),
        # Distinguish no live box seats from a box that never answered.
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


BOX_LAUNCHER_PATH = Path(__file__).with_name("launch-claude-ubuntu")
WINDOW_OPENER_PATH = Path(__file__).with_name("open-iterm-window-running-command")
# A LaunchAgent has no terminal for SSH prompts.
BOX_QUERY_SSH_OPTIONS = ("-o", "BatchMode=yes", "-o", "ConnectTimeout=10")
# The box may still be booting at Mac login; retry connection failures, not answers from the box.
BOX_QUERY_DEADLINE_SECONDS = 150.0
BOX_QUERY_RETRY_SECONDS = 5.0
# Seat homes exclude the fleet-anchor keep-alive session; after-exit shells still need windows.
# The box launcher always uses ~/agents and reads no agents-root override.
# A seat whose newest client attached at or after the Mac's boot already has a window from
# this login; a client from before it is a window the reboot closed, whose ssh the box may
# not have noticed yet, so it does not count.
AGENT_SEAT_CLIENT_ATTACHED_SINCE_MAC_BOOT_LISTING_TEXT = "attached"
# The listing prints each failed tmux command on stderr after this text and the seat it
# failed on, for the Mac to tell tmux's "that server or session is gone" answers from its
# failures. A failure on the default server names this placeholder instead, since that
# server can hold several seats.
NED_BOX_LISTING_TMUX_FAILURE_PREFIX = "tmux failed on the box:"
NED_BOX_LISTING_TMUX_FAILURE_SEAT_PLACEHOLDER_FOR_SHARED_DEFAULT_SERVER = "*"


def ned_box_running_agent_seats_list_command_marking_clients_attached_since_mac_boot(
        mac_booted_at_epoch_seconds: int) -> str:
    return (
        'report_tmux_failure() { failed_seat=$1; shift; printf "%s %s %s\\n" '
        f'"{NED_BOX_LISTING_TMUX_FAILURE_PREFIX}" "$failed_seat" '
        '"$(printf "%s" "$*" | tr "\\n" " ")" >&2; }; '
        'for seat_socket_path in "${TMUX_TMPDIR:-/tmp}/tmux-$(id -u)"/*; do '
        '[ -S "$seat_socket_path" ] || continue; '
        'if ! seat_names=$(tmux -S "$seat_socket_path" list-sessions -F "#{session_name}" 2>&1); '
        'then socket_name=$(basename "$seat_socket_path"); '
        'if [ "$socket_name" = default ]; '
        f'then report_tmux_failure "{NED_BOX_LISTING_TMUX_FAILURE_SEAT_PLACEHOLDER_FOR_SHARED_DEFAULT_SERVER}" '
        '"tmux -S $seat_socket_path list-sessions: $seat_names"; '
        'elif [ -d "$HOME/agents/$socket_name" ]; '
        'then report_tmux_failure "$socket_name" "tmux -S $seat_socket_path list-sessions: '
        '$seat_names"; fi; '
        'continue; fi; '
        'printf "%s\\n" "$seat_names" | while read -r seat_name; do '
        '[ -n "$seat_name" ] || continue; '
        'if ! client_times=$(tmux -S "$seat_socket_path" list-clients -t "=$seat_name" '
        '-F "#{client_created}" 2>&1); '
        'then [ -d "$HOME/agents/$seat_name" ] && report_tmux_failure "$seat_name" '
        '"tmux -S $seat_socket_path list-clients -t =$seat_name: $client_times"; continue; fi; '
        'newest=$(printf "%s\\n" "$client_times" | sort -n | tail -n 1); '
        f'if [ "${{newest:-0}}" -ge {int(mac_booted_at_epoch_seconds)} ]; '
        f'then echo "$seat_name {AGENT_SEAT_CLIENT_ATTACHED_SINCE_MAC_BOOT_LISTING_TEXT}"; '
        'else echo "$seat_name"; fi; '
        'done; '
        'done | sort -u | while read -r seat_name attached; do '
        '[ -d "$HOME/agents/$seat_name" ] && echo "$seat_name${attached:+ $attached}"; '
        'done; true'
    )


def agent_box() -> str:
    """Return the SSH destination using the launcher’s resolution rules."""
    return os.environ.get("NEDSCHORUS_AGENT_BOX", "ned")


def box_seat_query_command(mac_booted_at: datetime, box: str = None) -> list:
    return ["ssh", *BOX_QUERY_SSH_OPTIONS, box or agent_box(),
            ned_box_running_agent_seats_list_command_marking_clients_attached_since_mac_boot(
                int(mac_booted_at.timestamp()))]


def ned_box_agent_seat_listing_parse_into_needing_window_and_attached_since_mac_boot(listing: str):
    """Return (seats to open a window onto, seats already attached since the Mac booted)."""
    seats, already_attached = set(), set()
    for line in listing.splitlines():
        words = line.split()
        if not words:
            continue
        if words[1:] == [AGENT_SEAT_CLIENT_ATTACHED_SINCE_MAC_BOOT_LISTING_TEXT]:
            already_attached.add(words[0])
        else:
            seats.add(words[0])
    # A seat listed on two sockets, one with a window, has its window.
    return sorted(seats - already_attached), sorted(already_attached)


def ask_the_box_which_seats_are_alive(mac_booted_at: datetime, run=subprocess.run,
                                      deadline_seconds=BOX_QUERY_DEADLINE_SECONDS,
                                      retry_seconds=BOX_QUERY_RETRY_SECONDS, sleep=time.sleep,
                                      monotonic=time.monotonic):
    """Return (seats without a window, detail, seats already attached, withheld seats).

    seats is None when the box did not answer, or tmux failed on its shared default
    server; withheld is a list of (seat, tmux's failure) for seats whose own tmux server or
    session failed, which get no window."""
    started = monotonic()
    attempts = 0
    while True:
        attempts += 1
        try:
            finished = run(box_seat_query_command(mac_booted_at), stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True)
        except OSError as error:
            return None, f"could not run ssh: {error}", [], []
        if finished.returncode == 0:
            tmux_failures = []
            for line in finished.stderr.splitlines():
                if not line.startswith(NED_BOX_LISTING_TMUX_FAILURE_PREFIX):
                    continue
                failed_seat, _, failure = (
                    line[len(NED_BOX_LISTING_TMUX_FAILURE_PREFIX):].strip().partition(" "))
                # A seat that fails on both its own server and the default one is one failure.
                if not tmux_error_pattern.tmux_error_text_says_target_or_server_does_not_exist(
                        failure) and failed_seat not in dict(tmux_failures):
                    tmux_failures.append((failed_seat, failure.strip()))
            shared = [failure for failed_seat, failure in tmux_failures
                      if failed_seat
                      == NED_BOX_LISTING_TMUX_FAILURE_SEAT_PLACEHOLDER_FOR_SHARED_DEFAULT_SERVER]
            if shared:
                return None, ("its tmux could not list the seats on its shared default "
                              "server: " + "; ".join(shared)), [], []
            seats, already_attached = (
                ned_box_agent_seat_listing_parse_into_needing_window_and_attached_since_mac_boot(
                    finished.stdout))
            # A seat whose own server failed can still be listed from the default server;
            # it stays withheld, since whether its own server holds a live seat is unknown.
            withheld_seats = {failed_seat for failed_seat, _ in tmux_failures}
            return ([seat for seat in seats if seat not in withheld_seats],
                    f"answered on attempt {attempts}",
                    [seat for seat in already_attached if seat not in withheld_seats],
                    tmux_failures)
        if finished.returncode != 255:
            return None, (f"the box answered with exit {finished.returncode}: "
                          f"{finished.stderr.strip()}"), [], []
        if monotonic() - started >= deadline_seconds:
            return None, (f"unreachable for {int(deadline_seconds)}s over {attempts} "
                          f"attempt(s) (ssh exit 255: {finished.stderr.strip()})"), [], []
        sleep(retry_seconds)


def window_command_for_box_seat(seat: str) -> list:
    return [str(WINDOW_OPENER_PATH), str(BOX_LAUNCHER_PATH), seat]


def open_windows_onto_box_seats(seats, run=subprocess.run):
    """Return (opened seats, per-seat reports), trying every seat despite failures."""
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


def restore_box_windows(dry_run: bool, mac_booted_at: datetime, platform: str = sys.platform,
                        run=subprocess.run, sleep=time.sleep, monotonic=time.monotonic):
    """Return the attempted, answered, detail, seats, already_attached, opened and reports fields."""
    if platform != "darwin":
        return {"attempted": False}
    seats, detail, already_attached, withheld = ask_the_box_which_seats_are_alive(
        mac_booted_at, run=run, deadline_seconds=0 if dry_run else BOX_QUERY_DEADLINE_SECONDS,
        sleep=sleep, monotonic=monotonic)
    outcome = {"attempted": True, "answered": seats is not None, "detail": detail,
               "seats": seats, "already_attached": already_attached, "withheld": withheld,
               "opened": [], "reports": []}
    if seats and not dry_run:
        outcome["opened"], outcome["reports"] = open_windows_onto_box_seats(seats, run=run)
    return outcome


def recovery_command_for_seat(seat: str, handoff_directory: Path,
                              platform: str = sys.platform) -> list:
    command = [sys.executable, str(RECOVERY_TOOL_PATH), seat,
               "--handoff-dir", str(handoff_directory)]
    if platform == "darwin":
        command.append("--open-iterm-window-per-seat")
    return command


def seat_came_up(exit_code, report: str) -> bool:
    # A confirmed already-running supervisor counts as up even though no seat was launched,
    # and so does a seat whose window on the Mac did not open.
    return (exit_code in (0, recovery.ALL_AGENT_SEATS_RECOVERED_BUT_MAC_WINDOW_OPEN_FAILED_EXIT_STATUS)
            and not any(marker in report
                        for marker in recovery.SEAT_NOT_RECOVERED_REPORT_MARKERS))


def launch_seats_decided_restart(decisions, handoff_directory: Path,
                                 run=subprocess.run, platform: str = sys.platform):
    """Return (seats that came up, per-seat reports), trying every restart independently."""
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
            # argparse refusals can leave stdout empty, making the exit code the only report.
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
    # Record after launch so outcomes are known; interruption leaves later runs offering seats instead of duplicating starts.
    if arguments.dry_run:
        launched, reports = None, []
    else:
        launched, reports = launch_seats_decided_restart(decisions, arguments.handoff_dir)
    # Every Mac login loses the windows onto box seats, regardless of local seat verdicts.
    box_windows = restore_box_windows(arguments.dry_run, boot_at)
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
        # A recorded run with an unknown stop differs from no recorded run.
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
            # Use this run’s handoff directory in the manual recovery command.
            print("    not launched; to bring it back by hand: " + " ".join(
                recovery_command_for_seat(seat, arguments.handoff_dir)[1:]))
    windows_not_opened = []
    if box_windows["attempted"]:
        box = agent_box()
        if not box_windows["answered"]:
            print(f"  box {box}: did not answer ({box_windows['detail']}) — its windows are "
                  f"missing; when it is back, one window per seat by hand: "
                  f"{BOX_LAUNCHER_PATH} <seat>")
        elif not (box_windows["seats"] or box_windows["already_attached"]
                  or box_windows["withheld"]):
            print(f"  box {box}: no live seats, so no windows to open")
        elif arguments.dry_run:
            if box_windows["seats"]:
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
        for seat in box_windows["already_attached"]:
            print(f"  box {box}: {seat} already has a window attached since this Mac "
                  "booted, so no other was opened")
        # Its tmux could not say whether the seat is alive or already has a window, so
        # opening one could attach a second window or start a duplicate seat.
        for seat, failure in box_windows["withheld"]:
            windows_not_opened.append(seat)
            print(f"  box {box}: NO WINDOW onto {seat} — the box's tmux failed on it ({failure}), "
                  f"so whether it is alive is unknown; once that tmux error is fixed on {box}, "
                  f"run on this Mac: {BOX_LAUNCHER_PATH} {seat}")
    # On the box, recovery opened each restarted seat's window on the Mac and reported
    # one that did not open in that seat's line, printed above.
    windows_not_opened += [seat for seat, came_up, report in reports
                           if came_up and recovery.AGENT_SEAT_MAC_WINDOW_NOT_OPENED_REPORT_TEXT in report]
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
