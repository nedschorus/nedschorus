#!/usr/bin/env python3
"""An agent-seat's tmux server that scripts/recover-crashed-seats.py starts from cron runs under the user's systemd manager.

Starts a throwaway tmux server, on a socket of its own and running only `sleep`, with
recover-crashed-seats.py's own systemd-run prefix and run_tmux, from an environment
holding neither XDG_RUNTIME_DIR nor DBUS_SESSION_BUS_ADDRESS, as cron gives, and checks
that the server's cgroup is under user@<uid>.service, beside the test suites' slice. The
server is ended with kill-server on its own socket, and that socket's file is removed; no
other tmux server is touched.

Linux with the user's session bus, systemd-run and tmux only; elsewhere every case is
skipped. The nc-test-sandbox hides /run/user/<uid>, so the runner runs this suite
without any sandbox; run inside a sandbox anyway, it skips.

Run: python3 scripts/recover-crashed-seats-started-tmux-server-lands-in-user-systemd-manager-cgroup-without-xdg-runtime-dir-real-process-test.py   (exit 0 = all passed)
"""

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().with_name("recover-crashed-seats.py")

failures = []


def check(case_name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {case_name}")
    if not condition:
        failures.append(case_name)
        if detail:
            print(f"      {detail!r}"[:1500])


def unavailable_because():
    if not sys.platform.startswith("linux"):
        return f"{sys.platform} has no systemd user manager"
    if os.environ.get("RUN_ALL_TEST_SUITES_INSIDE_SIGNAL_SANDBOX"):
        return "this suite is inside a sandbox, which hides the user's session bus"
    if not Path(f"/run/user/{os.getuid()}/bus").exists():
        return f"/run/user/{os.getuid()}/bus does not exist"
    for program in ("systemd-run", "tmux"):
        if shutil.which(program) is None:
            return f"{program} is not on PATH"
    return None


why = unavailable_because()
if why is not None:
    print(f"SKIP  every case: {why}")
    sys.exit(0)

spec = importlib.util.spec_from_file_location("recover_crashed_seats", SCRIPT_PATH)
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)

socket_name = f"recover-crashed-seats-user-scope-real-test-{os.getpid()}"
cron_environment = {name: value for name, value in os.environ.items()
                    if name not in ("XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS",
                                    "TMUX", "TMUX_PANE")}
prefix, failure = (
    recovery.agent_seat_tmux_server_user_systemd_scope_command_prefix_or_manager_unreachable_reason(
        socket_name, cron_environment))
check("from an environment with no XDG_RUNTIME_DIR, the user manager is reached",
      failure is None and prefix[:3] == ["systemd-run", "--user", "--scope"], (prefix, failure))
if failure is None:
    try:
        started = recovery.run_tmux("new-session", "-d", "-s", socket_name, "sleep 120",
                                    socket_name=socket_name, environment=cron_environment,
                                    command_prefix=prefix)
        check("the tmux server starts", started is not None and started.returncode == 0,
              started and (started.returncode, started.stderr))
        answered = recovery.run_tmux("display-message", "-p", "#{pid}", socket_name=socket_name,
                                     environment=cron_environment)
        server_cgroup = ""
        if answered is not None and answered.returncode == 0 and answered.stdout.strip().isdigit():
            server_cgroup = Path(f"/proc/{answered.stdout.strip()}/cgroup").read_text().strip()
        check("the tmux server's cgroup is under the user's systemd manager, where the test "
              "suites' slice is",
              f"/user@{os.getuid()}.service/" in server_cgroup,
              (server_cgroup, answered and (answered.returncode, answered.stdout, answered.stderr)))
    finally:
        recovery.run_tmux("kill-server", socket_name=socket_name, environment=cron_environment)
        # kill-server leaves the socket file behind, and each run's name is new.
        (Path(cron_environment.get("TMUX_TMPDIR") or "/tmp") / f"tmux-{os.getuid()}"
         / socket_name).unlink(missing_ok=True)

print(f"{len(failures)} failed" if failures else "all cases passed")
sys.exit(1 if failures else 0)
