#!/usr/bin/env python3
"""Tests that starting an agent-seat's handoff-supervisor in a tmux pane turns on the capture of
that pane's terminal output, and that a second supervisor start in the same pane, as at a
restart onto main's code at a session-handoff, opens a new terminal capture instead of ending the
capture.

The real supervisor runs as the pane command of a real tmux server under a private TMUX_TMPDIR,
so no agent-seat's tmux server is reachable; the agent it launches is a stub that prints a marker
and exits 0, which stops the supervisor. The captures directory is a scratch one, named by
AGENT_SEAT_TERMINAL_CAPTURES_DESTINATION.

It also checks that a suite run from an agent-seat's own tmux pane, as agents run test files,
starts no pipe-pane on that pane: TMUX and TMUX_PANE are set, and a stub tmux that records its
calls is first on PATH, before handoff-supervisor-test-fixture.py loads.

Run: python3 nc-systems/handoff/tests/handoff-supervisor-terminal-capture-test.py
(exit 0 = all passed)
"""

import importlib.util
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().parents[3] / "scripts"
    / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

# As in an agent-seat's own pane, before the fixture loads; the fixture must drop both.
CALLING_PANE_TMUX = "/tmp/tmux-calling-seat/default,1,0"
CALLING_PANE = "%99"
os.environ["TMUX"] = CALLING_PANE_TMUX
os.environ["TMUX_PANE"] = CALLING_PANE

_handoff_supervisor_test_fixture_spec = importlib.util.spec_from_file_location(
    "handoff_supervisor_test_fixture",
    Path(__file__).resolve().with_name("handoff-supervisor-test-fixture.py"))
fixture = importlib.util.module_from_spec(_handoff_supervisor_test_fixture_spec)
_handoff_supervisor_test_fixture_spec.loader.exec_module(fixture)

check = fixture.check
SCRIPT_PATH = fixture.SCRIPT_PATH
captures = fixture.supervisor.agent_seat_terminal_captures
SEAT = "terminal-capture-seat"
WAIT_SECONDS = 60


def tmux(socket_directory: Path, *arguments):
    return subprocess.run(["tmux", "-S", str(socket_directory / "seat"), *arguments],
                          capture_output=True, text=True, check=False)


def wait_until(condition, seconds=WAIT_SECONDS):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.2)
    return condition()


tmux_directory = Path(tempfile.mkdtemp(prefix="tcap-", dir="/tmp" if os.path.isdir("/tmp") else None))
try:
    with fixture.handoff_supervisor_suite_workspace() as workspace:
        check("loading the fixture drops the calling pane's TMUX and TMUX_PANE, and points the "
              "terminal captures at the scratch HOME",
              "TMUX" not in os.environ and "TMUX_PANE" not in os.environ
              and os.environ.get(captures.AGENT_SEAT_TERMINAL_CAPTURES_DESTINATION_ENVIRONMENT_VARIABLE, "")
              .startswith(str(fixture.SCRATCH_HOME_DIRECTORY)),
              f"TMUX={os.environ.get('TMUX')!r} TMUX_PANE={os.environ.get('TMUX_PANE')!r}")
        os.environ["TMUX_TMPDIR"] = str(tmux_directory)
        captures_directory = workspace / "captures"
        os.environ[captures.AGENT_SEAT_TERMINAL_CAPTURES_DESTINATION_ENVIRONMENT_VARIABLE] = str(captures_directory)
        seat_directory = workspace / "seat"
        seat_directory.mkdir()
        counter = workspace / "launches"
        stub_agent = workspace / "stub-agent"
        stub_agent.write_text(
            f"#!{sys.executable}\n"
            f"from pathlib import Path\ncounter = Path({str(counter)!r})\n"
            "launch = len(counter.read_text().splitlines()) + 1 if counter.exists() else 1\n"
            "counter.write_text(counter.read_text() + 'x\\n' if counter.exists() else 'x\\n')\n"
            "print(f'Do you trust this folder? stub-agent-launch-{launch}', flush=True)\n",
            encoding="utf-8")
        stub_agent.chmod(0o755)
        supervisor_start = " ".join(shlex.quote(word) for word in (
            sys.executable, str(SCRIPT_PATH), "--agent", SEAT, "--cd", str(seat_directory),
            "--handoff-dir", str(workspace / "handoffs"), "--agent-command", str(stub_agent),
            "--agent-update-timeout-seconds", "0"))
        recording_tmux_directory = workspace / "recording-tmux"
        recording_tmux_directory.mkdir()
        recorded_calls = workspace / "recorded-tmux-calls"
        (recording_tmux_directory / "tmux").write_text(
            f"#!{sys.executable}\nimport sys\n"
            f"open({str(recorded_calls)!r}, 'a').write(' '.join(sys.argv[1:]) + '\\n')\n",
            encoding="utf-8")
        (recording_tmux_directory / "tmux").chmod(0o755)
        started_from_a_suite = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--agent", SEAT, "--cd", str(seat_directory),
             "--handoff-dir", str(workspace / "handoffs-of-the-suite-run"), "--agent-command", str(stub_agent),
             "--agent-update-timeout-seconds", "0"],
            capture_output=True, text=True, check=False, timeout=WAIT_SECONDS,
            env=dict(os.environ, PATH=f"{recording_tmux_directory}{os.pathsep}{os.environ.get('PATH', '')}"))
        calls = recorded_calls.read_text(encoding="utf-8") if recorded_calls.exists() else ""
        check(f"a supervisor a suite starts from an agent-seat's own pane ({CALLING_PANE}) runs no "
              "tmux pipe-pane on it, and says its own terminal output is not captured",
              "pipe-pane" not in calls and CALLING_PANE not in calls
              and "is not being captured to a file: this handoff-supervisor is not in a tmux pane"
              in started_from_a_suite.stdout,
              f"tmux calls {calls!r}; stdout {started_from_a_suite.stdout[-1500:]!r}")
        if counter.exists():
            counter.unlink()

        configuration = tmux_directory / "empty.conf"
        configuration.write_text("set -g remain-on-exit on\n", encoding="utf-8")
        started = subprocess.run(
            ["tmux", "-S", str(tmux_directory / "seat"), "-f", str(configuration), "new-session", "-d",
             "-s", SEAT, "-x", "200", "-y", "50",
             f"{supervisor_start}; sleep 1; {supervisor_start}"],
            capture_output=True, text=True, check=False)
        check("a private tmux server starts with the supervisor as its pane command",
              started.returncode == 0, started.stderr)

        seat_captures = captures_directory / SEAT
        pane_dead = wait_until(lambda: tmux(tmux_directory, "display-message", "-p", "-t", SEAT,
                                            "#{pane_dead}").stdout.strip() == "1")
        capture_files = sorted(seat_captures.glob("*")) if seat_captures.is_dir() else []

        def capture_text(index):
            return capture_files[index].read_text(encoding="utf-8", errors="replace") \
                if len(capture_files) > index else ""

        wait_until(lambda: "stub-agent-launch-2" in capture_text(1), seconds=10)
        pane_pipe = tmux(tmux_directory, "display-message", "-p", "-t", SEAT, "#{pane_pipe}").stdout.strip()
        check("both supervisor starts ran to their end in the pane", pane_dead,
              tmux(tmux_directory, "capture-pane", "-p", "-t", SEAT).stdout)
        check("each supervisor start opened its own terminal capture, named "
              "<UTC start>-<agent-seat>-terminal-capture.log in the agent-seat's directory",
              len(capture_files) == 2
              and all(path.name.endswith(f"-{SEAT}-terminal-capture.log") for path in capture_files),
              str(capture_files))
        check("the first terminal capture holds what the pane showed during the first start: the "
              "supervisor's line naming the capture, and the agent's output",
              f"this agent-seat's terminal output is captured to {capture_files[0] if capture_files else ''}"
              in capture_text(0)
              and "stub-agent-launch-1" in capture_text(0) and "stub-agent-launch-2" not in capture_text(0),
              repr(capture_text(0)[-1500:]))
        check("the second supervisor start in the same pane captures on, into the second file, "
              "instead of closing the pane's pipe",
              "stub-agent-launch-2" in capture_text(1) and pane_pipe == "1",
              f"pane_pipe {pane_pipe!r}; {capture_text(1)[-1500:]!r}")
finally:
    subprocess.run(["tmux", "-S", str(tmux_directory / "seat"), "kill-server"],
                   capture_output=True, check=False)
    shutil.rmtree(tmux_directory, ignore_errors=True)

fixture.print_summary_and_exit_nonzero_if_any_case_failed()
