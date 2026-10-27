#!/usr/bin/env python3
"""Restart the agent-seat database service when a merge into ned-box's reference-checkout changes it.

Usage (git runs it from scripts/git-client-side-hooks/post-merge, in the
checkout's top directory, after every merge, a fast-forward included):
  nc-systems/agent-seat-database/agent-seat-database-service-restart-after-merge.py
      [--reference-checkout DIR]

  --reference-checkout  default /home/nedlern/Projects/nedschorus, ned-box's
                        reference-checkout, from which the systemd user unit
                        agent-seat-database-service.service runs the service

Every checkout of the clone on both machines runs the same post-merge hook,
because core.hooksPath names the reference-checkout's hook directory. In any
checkout but ned-box's reference-checkout this program does nothing. There,
when `git diff ORIG_HEAD HEAD` names a file of SERVICE_FILES, it runs
`systemctl --user restart agent-seat-database-service.service`, so the
service runs the merged code and no person has to restart it. A change to the
unit file itself is not picked up this way: run the unit's install step again.

Git ignores a post-merge hook's exit code; the merge stands either way.

Exit codes: 0 nothing to restart, or the restart succeeded; 1 git could not
list the merge's changes, or the restart failed, with git's or systemctl's
error on standard error.
"""

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

PROGRAM = "agent-seat-database-service-restart-after-merge"
UNIT_NAME = "agent-seat-database-service.service"
SERVICE_FILES = ("nc-systems/agent-seat-database/agent-seat-database-service.py",)
EXIT_DONE = 0
EXIT_FAILED = 1

_ned_box_paths_spec = importlib.util.spec_from_file_location(
    "ned_box_home_directory_and_its_mac_mount_point_path_constants_common",
    Path(__file__).resolve().parents[1] / "general-tools"
    / "ned-box-home-directory-and-its-mac-mount-point-path-constants-common.py")
ned_box_paths = importlib.util.module_from_spec(_ned_box_paths_spec)
_ned_box_paths_spec.loader.exec_module(ned_box_paths)

NED_BOX_REFERENCE_CHECKOUT = f"{ned_box_paths.NED_BOX_HOME}/Projects/nedschorus"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--reference-checkout", default=NED_BOX_REFERENCE_CHECKOUT)
    arguments = parser.parse_args(argv)
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if top.returncode != 0 or os.path.realpath(top.stdout.strip()) \
            != os.path.realpath(arguments.reference_checkout):
        return EXIT_DONE
    changed = subprocess.run(["git", "diff", "--name-only", "ORIG_HEAD", "HEAD", "--",
                              *SERVICE_FILES], capture_output=True, text=True)
    if changed.returncode != 0:
        print(f"{PROGRAM}: FAILED — `git diff --name-only ORIG_HEAD HEAD` in "
              f"{arguments.reference_checkout} exited {changed.returncode}, so this merge's "
              f"changes to the agent-seat database service are unknown and the service was not "
              f"restarted: {changed.stderr.strip()}\n"
              f"If the merge changed {', '.join(SERVICE_FILES)}, restart the service on ned-box "
              f"with `systemctl --user restart {UNIT_NAME}`.", file=sys.stderr)
        return EXIT_FAILED
    if not changed.stdout.strip():
        return EXIT_DONE
    restarted = subprocess.run(["systemctl", "--user", "restart", UNIT_NAME],
                               capture_output=True, text=True)
    if restarted.returncode != 0:
        print(f"{PROGRAM}: FAILED — the merge changed the agent-seat database service, and "
              f"`systemctl --user restart {UNIT_NAME}` exited {restarted.returncode}, so the "
              f"service may still run the code from before the merge, or not run at all. "
              f"systemctl said: {restarted.stderr.strip()}\n"
              f"What to do: on ned-box, read `systemctl --user status {UNIT_NAME}` and "
              f"`journalctl --user -u {UNIT_NAME} -n 50`. If the unit is not installed, its "
              f"install step has not run yet: leave it to the user. Otherwise tell the user "
              f"that the service failed to restart after the merge, with what systemctl and "
              f"journalctl printed. If you are a subagent, pass the same fact to the agent that "
              f"dispatched you.", file=sys.stderr)
        return EXIT_FAILED
    print(f"{PROGRAM}: restarted {UNIT_NAME}, since the merge changed the service")
    return EXIT_DONE


if __name__ == "__main__":
    sys.exit(main())
