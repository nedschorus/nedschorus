#!/usr/bin/env python3
"""restart-live-seats-at-login — at login, bring back the seats that were
running when this machine stopped (nedschorus#116).

Built in the order the #116 design lays out (§ The build, in order). This
first piece is the selection alone: which seats were running at the stop,
read from their supervisors' heartbeats. It launches nothing; until the
restart step lands it runs only with --dry-run, and says so.

The rule, from docs/issues/116-fleet-survives-machine-restart-design.md
§ Ruled 2026-08-31 and its 2026-09-02 amendments:

  - Every supervisor stamps last_poll_at into
    ~/.claude/handoffs/<seat>-supervisor-state.json every
    HEARTBEAT_INTERVAL_SECONDS while it runs.
  - The anchor is the newest stamp before this boot; it approximates the
    moment the machine stopped. A stamp since boot belongs to a seat running
    now — recovered by hand, or started by an earlier run of this program —
    and is neither the anchor nor restarted.
  - Anchor within an hour before boot: the seats stamped within
    LIVE_SET_WINDOW_SECONDS of it were running at the stop, and are
    restarted.
  - Anchor longer before boot: either nothing was running when the machine
    stopped, or it sat off a long time. Nothing is started silently; those
    seats are offered — restart, park, or finished.
  - A state file whose heartbeat cannot be read — empty, cut off, no stamp,
    a stamp that does not parse, or one in the future — is treated as
    running at the stop, and restarted. A reboot in the middle of the
    supervisor's whole-file write leaves exactly that, and the user's answer
    (2026-09-11) was to try the resume: "Resume or continue works perfectly
    99% of the time, so I'd try that."
  - A seat with no state file is not considered: the supervisor writes the
    file on its first launch and never deletes it, so a seat without one
    never ran under a supervisor.

Usage:
  restart-live-seats-at-login.py --dry-run [--handoff-dir DIR]
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


def select_seats_live_at_the_stop(handoff_directory: Path, boot_at: datetime,
                                  now: datetime):
    """(anchor, decisions): the newest heartbeat before boot, or None, and one
    (seat, verdict, reason) per supervisor state file. Verdicts: restart,
    offer, not-running-at-the-stop, running-since-boot."""
    if not handoff_directory.is_dir():
        return None, []
    readings = []
    for state_path in sorted(handoff_directory.glob(f"*{SUPERVISOR_STATE_FILE_SUFFIX}")):
        seat = state_path.name[:-len(SUPERVISOR_STATE_FILE_SUFFIX)]
        stamp, problem = read_supervisor_heartbeat(state_path, now)
        readings.append((seat, stamp, problem))

    anchor = max((stamp for _, stamp, _ in readings
                  if stamp is not None and stamp < boot_at), default=None)
    anchor_is_recent = (anchor is not None
                        and (boot_at - anchor).total_seconds()
                        <= RECENT_ANCHOR_BEFORE_BOOT_SECONDS)

    decisions = []
    for seat, stamp, problem in readings:
        if stamp is None:
            decisions.append((seat, "restart", (
                f"its heartbeat cannot be read ({problem}); treated as running "
                "at the stop — the user's answer 2026-09-11: try the resume")))
        elif stamp >= boot_at:
            decisions.append((seat, "running-since-boot", (
                f"stamped {stamp.isoformat(timespec='seconds')}, since boot")))
        elif (anchor - stamp).total_seconds() > LIVE_SET_WINDOW_SECONDS:
            decisions.append((seat, "not-running-at-the-stop", (
                f"stamped {describe_gap(anchor - stamp)} before the stop")))
        elif anchor_is_recent:
            decisions.append((seat, "restart", (
                f"stamped {describe_gap(anchor - stamp)} before the stop, which "
                f"was {describe_gap(boot_at - anchor)} before boot")))
        else:
            decisions.append((seat, "offer", (
                f"running at a stop {describe_gap(boot_at - anchor)} before boot, "
                "too long to restart silently: offer restart, park, or finished")))
    return anchor, decisions


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Select, from supervisor heartbeats, the seats that were "
                    "running when this machine stopped.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="report the selection and launch nothing (required "
                             "until the restart step is built)")
    parser.add_argument("--handoff-dir", type=Path,
                        default=Path("~/.claude/handoffs").expanduser(),
                        help="where the supervisor state files live")
    arguments = parser.parse_args(argv)
    if not arguments.dry_run:
        parser.error("only --dry-run exists so far: the restart step "
                     "(nedschorus#116, build step 4) is not built yet")

    boot_at = machine_boot_time()
    now = datetime.now(timezone.utc)
    anchor, decisions = select_seats_live_at_the_stop(arguments.handoff_dir,
                                                      boot_at, now)
    print("restart-live-seats-at-login: dry run, the selection only; nothing is launched")
    print(f"  boot {boot_at.isoformat(timespec='seconds')}")
    if anchor is None:
        print("  no heartbeat before boot: no supervisor was running when the machine stopped")
    else:
        print(f"  the stop: newest heartbeat before boot "
              f"{anchor.isoformat(timespec='seconds')}, "
              f"{describe_gap(boot_at - anchor)} before boot")
    for seat, verdict, reason in decisions:
        print(f"  {seat}: {verdict} — {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
