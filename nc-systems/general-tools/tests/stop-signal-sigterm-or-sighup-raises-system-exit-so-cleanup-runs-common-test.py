#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/stop-signal-sigterm-or-sighup-raises-system-exit-so-cleanup-runs-common.py.

scripts/pull-request-mutation-testing-survivors.py and scripts/ghi-issue-write.py reach this module
through their own suites. These cases pin the module directly: a child process that holds a directory
inside the context manager is sent each stop signal, and must remove the directory in its finally and
exit 128 plus the signal number; a child started with SIGHUP ignored, as under nohup, keeps running
when SIGHUP reaches it and still cleans up on SIGTERM; and the handlers in place before the block are
back after it. A child that does not exit within CHILD_EXIT_TIMEOUT_SECONDS of a signal is killed and
its case fails, so the remaining cases still run.

Run: python3 nc-systems/general-tools/tests/stop-signal-sigterm-or-sighup-raises-system-exit-so-cleanup-runs-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
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


CHILD_EXIT_TIMEOUT_SECONDS = 30
# Long enough for an unignored SIGHUP to end the child, which takes well under a second.
IGNORED_SIGNAL_GRACE_SECONDS = 2


@contextlib.contextmanager
def child_holding_directory(sighup_ignored=False):
    """The running child, its first stdout line and its directory; the child is killed if still running."""
    # Set explicitly: a child left to inherit would get SIG_IGN when this test runs under nohup.
    sighup_disposition = signal.SIG_IGN if sighup_ignored else signal.SIG_DFL
    with tempfile.TemporaryDirectory() as scratch:
        directory = Path(scratch) / "held"
        child = subprocess.Popen([sys.executable, "-c", CHILD, str(MODULE_PATH), str(directory)],
                                 stdout=subprocess.PIPE, text=True,
                                 preexec_fn=lambda: signal.signal(signal.SIGHUP, sighup_disposition))
        try:
            yield child, child.stdout.readline().strip(), directory
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()
            child.stdout.close()


def exit_code_within(child, seconds):
    """The child's exit code, or None when it has not exited within seconds."""
    try:
        return child.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        return None


def stop_detail(ready, returncode, left):
    if returncode is None:
        return f"the child did not exit within {CHILD_EXIT_TIMEOUT_SECONDS} s of the signal"
    return (ready, returncode, left)


for signal_number in (signal.SIGTERM, signal.SIGHUP):
    name = signal.Signals(signal_number).name
    with child_holding_directory() as (child, ready, directory):
        child.send_signal(signal_number)
        returncode = exit_code_within(child, CHILD_EXIT_TIMEOUT_SECONDS)
        left = directory.exists()
    check(f"{name} inside the block runs the finally that removes the directory, "
          f"and the process exits 128 plus the signal number",
          ready == "ready" and returncode == 128 + signal_number and not left,
          stop_detail(ready, returncode, left))

suite_sighup = signal.signal(signal.SIGHUP, signal.SIG_IGN)
try:
    with child_holding_directory() as (child, ready, directory):
        child.send_signal(signal.SIGHUP)
        returncode = exit_code_within(child, CHILD_EXIT_TIMEOUT_SECONDS)
        left = directory.exists()
finally:
    signal.signal(signal.SIGHUP, suite_sighup)
check("when this suite runs with SIGHUP ignored, as under nohup, SIGHUP still ends a child "
      "started without SIGHUP ignored, exiting 128 plus the signal number",
      ready == "ready" and returncode == 128 + signal.SIGHUP and not left,
      stop_detail(ready, returncode, left))

with child_holding_directory(sighup_ignored=True) as (child, ready, directory):
    child.send_signal(signal.SIGHUP)
    after_sighup = exit_code_within(child, IGNORED_SIGNAL_GRACE_SECONDS)
    child.send_signal(signal.SIGTERM)
    returncode = exit_code_within(child, CHILD_EXIT_TIMEOUT_SECONDS)
    left = directory.exists()
check("a child started with SIGHUP ignored is still running after SIGHUP reaches it",
      ready == "ready" and after_sighup is None, (ready, after_sighup))
check("SIGTERM still runs the finally in a child started with SIGHUP ignored, "
      "and the process exits 143",
      after_sighup is None and returncode == 143 and not left,
      stop_detail(ready, returncode, left))

with child_holding_directory() as (child, ready, directory):
    timed_out = exit_code_within(child, 0.5)
check("a child that has not exited when the wait times out gives None and is killed afterwards",
      timed_out is None and child.poll() is not None, (timed_out, child.poll()))


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
