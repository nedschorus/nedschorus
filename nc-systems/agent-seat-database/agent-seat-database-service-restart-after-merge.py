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
service runs the merged code and no person has to restart it. When the caller
has no XDG_RUNTIME_DIR, systemctl is given /run/user/<uid>, where the user
bus lives. A change to the unit file itself is not picked up this way: run the
unit's install step again.

Git ignores a post-merge hook's exit code; the merge stands either way. Git
puts this program's output on its own stderr; checkout-freshness-catch-up.py,
which fast-forwards the reference-checkout, shows the user any FAILED line.

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

PROGRAM = "nc-systems/agent-seat-database/agent-seat-database-service-restart-after-merge.py"
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
              f"Run `XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user restart {UNIT_NAME}` "
              f"on ned-box. A restart is safe even if the merge did not change the service.\n"
              f"If systemctl says the unit was not found, the unit's install step has not run "
              f"on ned-box yet; that step is the user's, so do nothing.\n"
              f"If systemctl fails for another reason, run `journalctl --user -u {UNIT_NAME} -n 50` "
              f"on ned-box. Then, if you are a subagent, tell the agent that dispatched you; "
              f"otherwise tell the user. Say that the agent-seat database service could not be "
              f"restarted after a merge, and quote this message from the FAILED line up to, but "
              f"not including, the line that starts \"Run\", what systemctl said and journalctl's last lines.",
              file=sys.stderr)
        return EXIT_FAILED
    if not changed.stdout.strip():
        return EXIT_DONE
    # An agent's Stop hook can run this merge without XDG_RUNTIME_DIR, and
    # systemctl --user then cannot find the user bus, which lives there.
    environment = {**os.environ}
    environment.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    restarted = subprocess.run(["systemctl", "--user", "restart", UNIT_NAME],
                               capture_output=True, text=True, env=environment)
    if restarted.returncode != 0:
        print(f"{PROGRAM}: FAILED — the merge changed the agent-seat database service, and "
              f"`systemctl --user restart {UNIT_NAME}` exited {restarted.returncode}, so the "
              f"service may still run the code from before the merge, or not run at all. "
              f"systemctl said: {restarted.stderr.strip()}\n"
              f"If systemctl said the unit was not found, the unit's install step has not "
              f"run on ned-box yet; it is the user's, so do nothing.\n"
              f"Otherwise run `journalctl --user -u {UNIT_NAME} -n 50` on ned-box and tell the "
              f"user that the agent-seat database service failed to restart after a merge, "
              f"quoting systemctl's line above and journalctl's last lines. If you are a "
              f"subagent, tell the agent that dispatched you instead, with the same quotes.",
              file=sys.stderr)
        return EXIT_FAILED
    print(f"{PROGRAM}: restarted {UNIT_NAME}, since the merge changed the service")
    return EXIT_DONE


if __name__ == "__main__":
    sys.exit(main())
