#!/usr/bin/env python3
"""Copy ned-box's newest agent-seat database backup to the Mac over ssh, so a backup survives the loss of ned-box.

Usage:
  nc-systems/agent-seat-database/agent-seat-database-newest-backup-copy-to-mac.py
      [--mac-backup-directory DIR]

  --mac-backup-directory  default ~/backups/agent-seat-database on the Mac

The Mac runs it each night, from the table
nc-systems/general-tools/scheduled-jobs-on-each-machine.json, which
nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py installs as
a launchd job at 04:15, after ned-box's nightly backup at 02:15; a run missed
while the Mac sleeps starts at the next wake.

It lists ned-box's ~/backups/agent-seat-database/ over ssh as nedlern@ned-box,
takes the newest agent-seat-database-<UTC time>.sqlite3, and copies it under
the same name into the Mac's directory, through a .partial file renamed when
the copy is whole. A copy the Mac already has is not copied again. Copies on
the Mac are never deleted.

Exit codes: 0 the newest backup is on the Mac; 1 ssh failed, or ned-box holds
no backup yet; the reason on standard error.
"""

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

PROGRAM = "agent-seat-database-newest-backup-copy-to-mac"
NED_BOX_SSH_TARGET = "nedlern@ned-box"
SSH_COMMAND = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", NED_BOX_SSH_TARGET]
MAC_BACKUP_DIRECTORY = Path.home() / "backups" / "agent-seat-database"
EXIT_NEWEST_BACKUP_ON_THE_MAC = 0
EXIT_NOT_COPIED = 1

_ned_box_paths_spec = importlib.util.spec_from_file_location(
    "ned_box_home_directory_and_its_mac_mount_point_path_constants_common",
    Path(__file__).resolve().parents[1] / "general-tools"
    / "ned-box-home-directory-and-its-mac-mount-point-path-constants-common.py")
ned_box_paths = importlib.util.module_from_spec(_ned_box_paths_spec)
_ned_box_paths_spec.loader.exec_module(ned_box_paths)

NED_BOX_BACKUP_DIRECTORY = f"{ned_box_paths.NED_BOX_HOME}/backups/agent-seat-database"


def not_copied(what_failed, detail):
    print(f"{PROGRAM}: FAILED — {what_failed}, so the Mac holds no copy of ned-box's newest "
          f"agent-seat database backup from this run.\n{detail}\n"
          f"The next nightly run tries again. If the next run fails the same way, tell the user "
          f"which step failed and what it printed above. If you are a subagent, pass the same "
          f"fact to the agent that dispatched you.", file=sys.stderr)
    return EXIT_NOT_COPIED


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--mac-backup-directory", default=str(MAC_BACKUP_DIRECTORY))
    arguments = parser.parse_args(argv)
    listed = subprocess.run([*SSH_COMMAND, f"ls -1 {NED_BOX_BACKUP_DIRECTORY}"],
                            capture_output=True, text=True)
    if listed.returncode != 0:
        return not_copied(f"listing {NED_BOX_SSH_TARGET}:{NED_BOX_BACKUP_DIRECTORY} failed",
                          f"ssh exited {listed.returncode}: {listed.stderr.strip()}")
    backups = sorted(name for name in listed.stdout.split()
                     if name.startswith("agent-seat-database-") and name.endswith(".sqlite3"))
    if not backups:
        return not_copied(f"{NED_BOX_SSH_TARGET}:{NED_BOX_BACKUP_DIRECTORY} holds no backup",
                          "ned-box's nightly job, "
                          "agent-seat-database-nightly-backup-with-integrity-check, writes "
                          "its output to ~/.claude/agent-seat-database-nightly-backup-with-"
                          "integrity-check.log on ned-box; read it for why.")
    newest = backups[-1]
    mac_directory = Path(arguments.mac_backup_directory)
    mac_copy = mac_directory / newest
    if mac_copy.exists():
        print(f"{PROGRAM}: {mac_copy} is already on the Mac")
        return EXIT_NEWEST_BACKUP_ON_THE_MAC
    mac_directory.mkdir(parents=True, exist_ok=True)
    partial = mac_copy.with_name(newest + ".partial")
    with open(partial, "wb") as written:
        copied = subprocess.run([*SSH_COMMAND, f"cat {NED_BOX_BACKUP_DIRECTORY}/{newest}"],
                                stdout=written, stderr=subprocess.PIPE, text=False)
    if copied.returncode != 0:
        partial.unlink()
        return not_copied(f"copying {NED_BOX_SSH_TARGET}:{NED_BOX_BACKUP_DIRECTORY}/{newest} "
                          f"failed", f"ssh exited {copied.returncode}: "
                                     f"{copied.stderr.decode('utf-8', 'replace').strip()}")
    partial.rename(mac_copy)
    print(f"{PROGRAM}: copied {newest} to {mac_copy}")
    return EXIT_NEWEST_BACKUP_ON_THE_MAC


if __name__ == "__main__":
    sys.exit(main())
