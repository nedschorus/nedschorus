#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/stop-signal-sigterm-or-sighup-raises-system-exit-so-cleanup-runs-common.py.

scripts/pull-request-mutation-testing-survivors.py and scripts/ghi-issue-write.py reach this module
through their own suites. These cases pin the module directly: a child process that holds a directory
inside the context manager is sent each stop signal, and must remove the directory in its finally and
exit 128 plus the signal number; and the handlers in place before the block are back after it.

Run: python3 nc-systems/general-tools/tests/stop-signal-sigterm-or-sighup-raises-system-exit-so-cleanup-runs-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

MODULE_PATH = (Path(__file__).resolve().parents[1]
               / "stop-signal-sigterm-or-sighup-raises-system-exit-so-cleanup-runs-common.py")
_spec = importlib.util.spec_from_file_location(
    "stop_signal_sigterm_or_sighup_raises_system_exit_so_cleanup_runs_common", MODULE_PATH)
stop_signals = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stop_signals)

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


# The child makes its directory, says so on stdout, and waits to be stopped; only its finally removes
# the directory.
CHILD = r'''
import importlib.util, shutil, sys, time
from pathlib import Path
spec = importlib.util.spec_from_file_location("stop_signals", sys.argv[1])
stop_signals = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stop_signals)
directory = Path(sys.argv[2])
with stop_signals.stop_signals_raise_system_exit_so_cleanup_runs():
    try:
        directory.mkdir()
        print("ready", flush=True)
        time.sleep(60)
    finally:
        shutil.rmtree(directory)
'''


def stopped_child(signal_number):
    """The child's exit code and whether its directory is left, after signal_number reaches it."""
    with tempfile.TemporaryDirectory() as scratch:
        directory = Path(scratch) / "held"
        child = subprocess.Popen([sys.executable, "-c", CHILD, str(MODULE_PATH), str(directory)],
                                 stdout=subprocess.PIPE, text=True)
        try:
            ready = child.stdout.readline().strip()
            child.send_signal(signal_number)
            returncode = child.wait(timeout=30)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()
        return ready, returncode, directory.exists()


for signal_number in (signal.SIGTERM, signal.SIGHUP):
    name = signal.Signals(signal_number).name
    ready, returncode, left = stopped_child(signal_number)
    check(f"{name} inside the block runs the finally that removes the directory, "
          f"and the process exits 128 plus the signal number",
          ready == "ready" and returncode == 128 + signal_number and not left,
          (ready, returncode, left))


def sentinel_handler(_signal_number, _frame):
    pass


previous = {number: signal.signal(number, sentinel_handler) for number in stop_signals.STOP_SIGNALS}
try:
    with stop_signals.stop_signals_raise_system_exit_so_cleanup_runs():
        inside = {number: signal.getsignal(number) for number in stop_signals.STOP_SIGNALS}
        raised = None
        try:
            signal.raise_signal(signal.SIGTERM)
            time.sleep(0)
        except SystemExit as stop:
            raised = stop.code
    after = {number: signal.getsignal(number) for number in stop_signals.STOP_SIGNALS}
finally:
    for number, handler in previous.items():
        signal.signal(number, handler)
check("inside the block both stop signals have the module's handler",
      all(handler is stop_signals.raise_system_exit_for_stop_signal for handler in inside.values()),
      inside)
check("in this process too, SIGTERM inside the block raises SystemExit(143)", raised == 143, raised)
check("after the block each stop signal has the handler it had before",
      all(handler is sentinel_handler for handler in after.values()), after)

print()
if failures:
    print(f"{failures} case(s) failed")
    sys.exit(1)
print("all cases passed")
