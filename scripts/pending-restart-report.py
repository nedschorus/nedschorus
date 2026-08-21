#!/usr/bin/env python3
"""Report whether this machine needs a reboot, or a daemon needs restarting.

Why this exists: on 2026-08-20 ned-box rebooted itself at 02:00 under
unattended-upgrades and destroyed a live agent seat that had written no
handoff. The automatic reboot was then disabled, which trades a surprise
reboot for a silent backlog: the kernel on disk drifts ahead of the running
one and nothing says so. This script is what says so
(nedschorus#116).

THE REPORT CARRIES THE VERDICT, not the exit code. The exit code is a
convenience for callers that want to branch without parsing:

  0   nothing pending
  10  a reboot is required
  11  no reboot needed, but daemons are holding deleted libraries
  2   could not determine (unsupported platform, or a probe failed)

Signals, and what each one means:

  /var/run/reboot-required        a package asked for a reboot. Kernel
                                  upgrades always set it. Its companion
                                  /var/run/reboot-required.pkgs names who.
  needrestart -b                  processes still mapping deleted library
                                  files -- the glibc/openssl case, fixable
                                  by restarting those services rather than
                                  the machine.

macOS has no equivalent flag and does not reboot itself, so there the
operator is the trigger; this script says that rather than guessing.
"""

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

REBOOT_FLAG = Path("/var/run/reboot-required")
REBOOT_PKGS = Path("/var/run/reboot-required.pkgs")

EXIT_NOTHING_PENDING = 0
EXIT_COULD_NOT_DETERMINE = 2
EXIT_REBOOT_REQUIRED = 10
EXIT_DAEMONS_ONLY = 11


def read_reboot_required():
    """Return (required, packages). packages is [] when the list is absent."""
    if not REBOOT_FLAG.exists():
        return False, []
    packages = []
    if REBOOT_PKGS.exists():
        try:
            packages = [
                line.strip()
                for line in REBOOT_PKGS.read_text().splitlines()
                if line.strip()
            ]
        except OSError:
            # The flag is what matters; an unreadable companion list is not
            # a reason to report "nothing pending".
            packages = []
    return True, packages


def read_needrestart():
    """Return (services, note). services is [] when none need restarting.

    note is a human-readable reason when the probe could not run, else None.
    """
    if shutil.which("needrestart") is None:
        return [], "needrestart is not installed"
    try:
        finished = subprocess.run(
            ["needrestart", "-b"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [], f"needrestart could not be run: {exc}"
    services = []
    for line in finished.stdout.splitlines():
        # Batch mode emits NEEDRESTART-SVC: <unit> for each affected service.
        if line.startswith("NEEDRESTART-SVC:"):
            name = line.split(":", 1)[1].strip()
            if name:
                services.append(name)
    return services, None


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Report whether a reboot or daemon restart is pending."
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="print nothing when nothing is pending (for launch-time use)",
    )
    args = parser.parse_args(argv)

    if platform.system() != "Linux":
        if not args.quiet:
            print(
                f"pending-restart-report: {platform.system()} has no "
                "reboot-required flag; this machine does not restart itself, "
                "so the operator is the trigger."
            )
        return EXIT_COULD_NOT_DETERMINE

    reboot_required, packages = read_reboot_required()
    services, needrestart_note = read_needrestart()

    if not reboot_required and not services:
        if not args.quiet:
            note = f" ({needrestart_note})" if needrestart_note else ""
            print(f"pending-restart-report: nothing pending{note}")
        return EXIT_NOTHING_PENDING

    lines = []
    if reboot_required:
        lines.append("pending-restart-report: A REBOOT IS REQUIRED.")
        if packages:
            lines.append(f"  asked for by: {', '.join(packages)}")
        else:
            lines.append(
                "  no package list at /var/run/reboot-required.pkgs; "
                "the flag alone is authoritative"
            )
    if services:
        lines.append(
            f"pending-restart-report: {len(services)} service(s) hold deleted "
            "libraries and want restarting:"
        )
        for name in services:
            lines.append(f"  {name}")
    if needrestart_note and not services:
        lines.append(f"  (daemon check skipped: {needrestart_note})")
    lines.append(
        "  Seats do not survive a reboot. Hand them off first -- see "
        "nedschorus#116."
    )
    print("\n".join(lines))

    return EXIT_REBOOT_REQUIRED if reboot_required else EXIT_DAEMONS_ONLY


if __name__ == "__main__":
    sys.exit(main())
