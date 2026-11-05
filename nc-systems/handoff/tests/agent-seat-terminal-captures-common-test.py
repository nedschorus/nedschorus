#!/usr/bin/env python3
"""Tests for nc-systems/handoff/agent-seat-terminal-captures-common.py: which directory each
machine captures into, how a terminal capture is named, and every way its start can fail
without stopping the agent-seat. tmux is a stub first on PATH here; the real tmux, with the real
handoff-supervisor in its pane, is in handoff-supervisor-terminal-capture-test.py.

Run: python3 nc-systems/handoff/tests/agent-seat-terminal-captures-common-test.py   (exit 0 = all passed)
"""

import importlib.util
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "agent-seat-terminal-captures-common.py"
_spec = importlib.util.spec_from_file_location("agent_seat_terminal_captures_common", MODULE_PATH)
captures = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(captures)

failures = []


def check(case_name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {case_name}")
    if not condition:
        failures.append(case_name)
        if detail:
            print(f"      {detail}")


OVERRIDE = captures.AGENT_SEAT_TERMINAL_CAPTURES_DESTINATION_ENVIRONMENT_VARIABLE
IN_A_PANE = {"TMUX": "/tmp/tmux-1000/stub-seat,1,0", "TMUX_PANE": "%7"}


def stub_tmux(directory: Path, body: str) -> Path:
    """A tmux first on PATH that logs its arguments to argv.json, then runs body."""
    directory.mkdir(parents=True, exist_ok=True)
    stub = directory / "tmux"
    stub.write_text(
        f"#!{sys.executable}\nimport json, sys, time\n"
        f"open({str(directory / 'argv.json')!r}, 'w').write(json.dumps(sys.argv[1:]))\n" + body,
        encoding="utf-8")
    stub.chmod(0o755)
    return directory


def start_with(environment: dict) -> str:
    with mock.patch.dict(os.environ, environment, clear=True):
        return captures.agent_seat_terminal_capture_start_in_this_tmux_pane("MD-skills")


with tempfile.TemporaryDirectory() as scratch_name:
    scratch = Path(scratch_name)
    base_environment = {key: value for key, value in os.environ.items()
                        if key not in ("TMUX", "TMUX_PANE", OVERRIDE)}

    # -- which directory each machine captures into ---------------------------------------------
    with mock.patch.dict(os.environ, base_environment, clear=True):
        on_ned_box = captures.agent_seat_terminal_captures_directory_on_this_machine_find("ned-box.local")
        on_the_mac = captures.agent_seat_terminal_captures_directory_on_this_machine_find("els-MacBook-Pro")
    check("on ned-box the terminal captures go straight into the log-store, beside the mirrored transcripts",
          on_ned_box == Path("/home/nedlern/nedschorus-logs/agent-session-files-by-machine/ned-box/"
                             "agent-seat-terminal-captures"), str(on_ned_box))
    check("on the Mac the terminal captures go under ~/.claude, where the transcript mirror copies them from",
          on_the_mac == Path.home() / ".claude" / "agent-seat-terminal-captures", str(on_the_mac))
    with mock.patch.dict(os.environ, dict(base_environment, **{OVERRIDE: str(scratch / "elsewhere")}),
                         clear=True):
        overridden = captures.agent_seat_terminal_captures_directory_on_this_machine_find("ned-box")
    check(f"{OVERRIDE} replaces the directory on either machine", overridden == scratch / "elsewhere",
          str(overridden))

    # -- how a terminal capture is named----------------------------------------------------------
    named = captures.agent_seat_terminal_capture_file_path_build(
        "merge-lane-2", time.strptime("2026-11-05 14:03:22", "%Y-%m-%d %H:%M:%S"), Path("/r"))
    check("a terminal capture is <directory>/<agent-seat>/<UTC start>-<agent-seat>-terminal-capture.log",
          named == Path("/r/merge-lane-2/20261105T140322Z-merge-lane-2-terminal-capture.log"), str(named))

    # -- the start of a terminal capture, and each way it fails -----------------------------------------
    captures_directory = scratch / "captures with a space"
    in_pane_environment = dict(base_environment, **IN_A_PANE, **{OVERRIDE: str(captures_directory)})

    for hostname, launch_command in (("ned-box", "launch-claude-ubuntu MD-skills"),
                                     ("els-MacBook-Pro", "launch-claude-mac MD-skills")):
        with mock.patch.object(captures.socket, "gethostname", return_value=hostname):
            line = start_with(dict(base_environment, **{OVERRIDE: str(captures_directory)}))
        check(f"outside a tmux pane on {hostname} nothing is captured, and the line says why and "
              f"gives this agent-seat's own launch command, `{launch_command}`",
              line.startswith("this agent-seat's terminal output is not being captured to a file: "
                              "this handoff-supervisor is not in a tmux pane")
              and f"`{launch_command}`, run on the Mac" in line and "do not stop it" in line
              and not captures_directory.exists(), line)

    succeeding = stub_tmux(scratch / "succeeding-tmux", "sys.exit(0)\n")
    line = start_with(dict(in_pane_environment,
                           PATH=f"{succeeding}{os.pathsep}{base_environment.get('PATH', '')}"))
    argv = json.loads((succeeding / "argv.json").read_text())
    captured_files = list((captures_directory / "MD-skills").glob("*")) \
        if (captures_directory / "MD-skills").is_dir() else []
    check("in a tmux pane the start pipes that pane, without -o, into cat appending to the "
          "terminal capture's path, quoted for the shell tmux runs it in",
          argv[:3] == ["pipe-pane", "-t", "%7"] and "-o" not in argv and len(argv) == 4
          and argv[3].startswith("exec cat >> '") and str(captures_directory) in argv[3]
          and "/MD-skills/" in argv[3] and argv[3].endswith("-MD-skills-terminal-capture.log'"), str(argv))
    check("the start makes the agent-seat's directory and says where the terminal output is captured",
          line.startswith(f"this agent-seat's terminal output is captured to {captures_directory}/MD-skills/")
          and line.endswith("-MD-skills-terminal-capture.log")
          and (captures_directory / "MD-skills").is_dir() and captured_files == [], line)

    for label, body, expected in (
            ("exits nonzero with an error", "sys.stderr.write('no such pane: %7\\n'); sys.exit(1)\n",
             "tmux pipe-pane exited 1: no such pane: %7."),
            ("exits nonzero saying nothing", "sys.exit(3)\n", "tmux pipe-pane exited 3, saying nothing."),
    ):
        failing = stub_tmux(scratch / f"tmux-that-{label.replace(' ', '-')}", body)
        line = start_with(dict(in_pane_environment,
                               PATH=f"{failing}{os.pathsep}{base_environment.get('PATH', '')}"))
        check(f"a tmux that {label}: nothing is captured, the line passes on tmux's exit and words, "
              "and says the agent-seat runs on",
              line == (f"this agent-seat's terminal output is not being captured to a file: {expected}\n"
                       f"{captures.AGENT_SEAT_TERMINAL_CAPTURE_NOT_STARTED_AGENT_SEAT_RUNS_UNCAPTURED_MESSAGE_LINE}"), line)

    hanging = stub_tmux(scratch / "hanging-tmux", "time.sleep(30)\n")
    with mock.patch.object(captures, "TMUX_PIPE_PANE_TIMEOUT_SECONDS", 1):
        line = start_with(dict(in_pane_environment,
                               PATH=f"{hanging}{os.pathsep}{base_environment.get('PATH', '')}"))
    check("a tmux that does not answer is given up on at the timeout, and the line says so",
          line.startswith("this agent-seat's terminal output is not being captured to a file: tmux pipe-pane could not run")
          and "timed out" in line and line.endswith(captures.AGENT_SEAT_TERMINAL_CAPTURE_NOT_STARTED_AGENT_SEAT_RUNS_UNCAPTURED_MESSAGE_LINE), line)

    empty_path_directory = scratch / "no-tmux-here"
    empty_path_directory.mkdir()
    line = start_with(dict(in_pane_environment, PATH=str(empty_path_directory)))
    check("no tmux on PATH: nothing is captured, and the line says tmux could not run",
          line.startswith("this agent-seat's terminal output is not being captured to a file: tmux pipe-pane could not run (")
          and line.endswith(captures.AGENT_SEAT_TERMINAL_CAPTURE_NOT_STARTED_AGENT_SEAT_RUNS_UNCAPTURED_MESSAGE_LINE), line)

    a_file_not_a_directory = scratch / "a-file"
    a_file_not_a_directory.write_text("", encoding="utf-8")
    line = start_with(dict(in_pane_environment, **{OVERRIDE: str(a_file_not_a_directory)},
                           PATH=f"{succeeding}{os.pathsep}{base_environment.get('PATH', '')}"))
    check("a captures directory that cannot be made: nothing is captured, and the line names it",
          line.startswith(f"this agent-seat's terminal output is not being captured to a file: the directory "
                          f"{a_file_not_a_directory}/MD-skills could not be made (")
          and f"run `ls -ld {a_file_not_a_directory}/MD-skills`" in line
          and "tell the user which directory" in line, line)

print()
if failures:
    print(f"{len(failures)} case(s) FAILED:")
    for name in failures:
        print(f"  - {name}")
    sys.exit(1)
print("all cases passed")
