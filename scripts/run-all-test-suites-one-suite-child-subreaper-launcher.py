#!/usr/bin/env python3
"""Run one test suite's command as the child of a Linux child subreaper, for
scripts/run-all-test-suites.py.

Usage: python3 -I run-all-test-suites-one-suite-child-subreaper-launcher.py <command> [<argument> ...]

The runner starts this program in place of a suite that runs outside an nc-test-sandbox.
It makes itself a child subreaper, prctl(PR_SET_CHILD_SUBREAPER), then starts the command
in its own process group, so a process the suite starts whose parent ends before it is
reparented to this program rather than to PID 1. It stays below the suite in
/proc/<pid>/task/*/children, where the runner's kill finds it; this program reaps it if it
ends first.

It ends as soon as the command ends: exit status N for an exit with N, or killed by signal
N for a command killed by signal N, so the runner reads the same result as without it.
Processes the suite left running then are reparented onward, as without this program.
SIGKILL to its process group, as the runner sends, kills it and the command alike.

It fails, with exit status 125 and the reason on stderr, before starting the command, when
prctl refuses or the command cannot start. Linux only."""

import ctypes
import os
import signal
import subprocess
import sys

PR_SET_CHILD_SUBREAPER = 36
CHILD_SUBREAPER_LAUNCHER_SUITE_NOT_STARTED_EXIT_STATUS = 125
LAUNCH_FAILED_MESSAGE_TEMPLATE = (
    "{program}: the nc-test-suite `{command}` was not started, so the runner reports it "
    "FAIL although none of its cases ran: {reason}.\n"
    "scripts/run-all-test-suites.py starts each suite outside an nc-test-sandbox through this "
    "program, so that processes the suite leaves behind can be found and killed.\n"
    "Run the same scripts/run-all-test-suites.py command again once, in case the cause has "
    "passed.\n"
    "If the same message comes back, and you are an agent-seat: send reboot-test, the "
    "agent-seat that owns the runner, this message and the machine it ran on, with "
    "SendMessage, and say in what you report that this suite did not run.\n"
    "If the same message comes back, and you are a subagent: do not message reboot-test; pass "
    "this message and the machine it ran on to the agent that dispatched you.\n")


def end_like(returncode):
    """Exit as the command did: with its status, or killed by its signal."""
    if returncode >= 0:
        sys.exit(returncode)
    signal_number = -returncode
    # SIGKILL and SIGSTOP take no handler, and need none: they always act.
    if signal_number not in (signal.SIGKILL, signal.SIGSTOP):
        signal.signal(signal_number, signal.SIG_DFL)
    os.kill(os.getpid(), signal_number)
    # A signal that does not end a process with its default action, such as SIGCHLD.
    sys.exit(128 + signal_number)


def main(command):
    def failed(reason):
        sys.stderr.write(LAUNCH_FAILED_MESSAGE_TEMPLATE.format(
            program=sys.argv[0], command=" ".join(command), reason=reason))
        return CHILD_SUBREAPER_LAUNCHER_SUITE_NOT_STARTED_EXIT_STATUS

    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) != 0:
        return failed(f"prctl(PR_SET_CHILD_SUBREAPER) failed: "
                      f"{os.strerror(ctypes.get_errno())}")
    try:
        suite = subprocess.Popen(command)
    except OSError as error:
        return failed(f"the command could not start: {error}")
    while True:
        # Reaps the orphans it adopts as well as the suite.
        pid, status = os.waitpid(-1, 0)
        if pid == suite.pid:
            end_like(os.waitstatus_to_exitcode(status))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"{sys.argv[0]}: no command given, so nothing was run.\n"
              f"This program is for scripts/run-all-test-suites.py to start, with a suite's "
              f"command; do not run it yourself. To run one nc-test-suite, run "
              f"`python3 scripts/run-all-test-suites.py --only-suites-named <suite path>` from "
              f"the checkout's top directory, <suite path> being the suite's path from there, "
              f"as `git ls-files` prints it.", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
