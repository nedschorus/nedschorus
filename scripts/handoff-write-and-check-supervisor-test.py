#!/usr/bin/env python3
"""Tests for handoff-write-and-check-supervisor.py.

Run: python3 scripts/handoff-write-and-check-supervisor-test.py

Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("handoff-write-and-check-supervisor.py")

_spec = importlib.util.spec_from_file_location("handoff_write_and_check_supervisor", SCRIPT_PATH)
writer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(writer)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run_writer(workspace: Path, next_step_text: str, *extra_arguments):
    """Invoke the script as the agent would, returning its completed process."""
    next_step_path = workspace / "next-step.txt"
    next_step_path.write_text(next_step_text, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", "tester",
         "--next-step-file", str(next_step_path), "--handoff-dir", str(workspace),
         *extra_arguments],
        capture_output=True, text=True, check=False,
    )


def run_collapse_cases():
    check(
        "a multi-line next step collapses to one line",
        writer.collapse_to_one_line("first line\nsecond line\n\nthird") == "first line second line third",
        writer.collapse_to_one_line("first line\nsecond line\n\nthird"),
    )
    check("runs of spaces and tabs collapse", writer.collapse_to_one_line("a  \t b") == "a b")
    check("surrounding whitespace is stripped", writer.collapse_to_one_line("\n  text  \n") == "text")
    check("whitespace-only text collapses to empty", writer.collapse_to_one_line(" \n\t ") == "")


def run_counter_cases(workspace: Path):
    handoff_path = workspace / "counter-handoff.md"
    state_path = workspace / "counter-supervisor-state.json"

    check("no previous handoff starts the counter at 1",
          writer.next_restart_counter(handoff_path, state_path) == 1)

    handoff_path.write_text("restart-counter: 4\n", encoding="utf-8")
    check("an existing counter increments",
          writer.next_restart_counter(handoff_path, state_path) == 5)

    handoff_path.write_text("restart-counter: not a number\n", encoding="utf-8")
    check("an unreadable counter still starts at 1 when nothing was consumed",
          writer.next_restart_counter(handoff_path, state_path) == 1)

    # The hazard this guards: a handoff file that lost or never carried a counter,
    # beside a supervisor that has already consumed higher values. Writing 1 there
    # would leave a handoff on disk that the supervisor ignores forever.
    state_path.write_text(json.dumps({"consumed_counter": 9}), encoding="utf-8")
    check("an unreadable counter clears the consumed value",
          writer.next_restart_counter(handoff_path, state_path) == 10)

    handoff_path.write_text("restart-counter: 2\n", encoding="utf-8")
    check("a stale handoff file cannot write a counter the supervisor would ignore",
          writer.next_restart_counter(handoff_path, state_path) == 10)

    state_path.write_text("{ not json", encoding="utf-8")
    check("unreadable supervisor state falls back to the handoff file",
          writer.next_restart_counter(handoff_path, state_path) == 3)


def run_invocation_cases(workspace: Path):
    result = run_writer(workspace, "Read the design doc, then continue.\nSecond line here.")
    handoff_path = workspace / "tester-handoff.md"
    # Exit 0 and 1 both mean written; they differ on whether a supervisor is
    # watching, which run_liveness_report_cases covers. Only 2 means nothing
    # was written.
    check("the writer accepts a well-formed invocation", result.returncode != 2, result.stderr)
    fields = writer.supervisor.parse_handoff_file(handoff_path)
    check("the written file parses as the supervisor reads it", set(fields) >= {
        "written-at", "next-step", "restart-counter"}, str(fields))
    check("the next step survives its newline",
          fields["next-step"] == "Read the design doc, then continue. Second line here.",
          fields["next-step"])
    check("the counter starts at 1", fields["restart-counter"] == "1", fields["restart-counter"])
    check("the timestamp is UTC ISO 8601",
          fields["written-at"].endswith("Z") and fields["written-at"][4] == "-",
          fields["written-at"])
    check("dont-restart is absent unless asked", "dont-restart" not in fields, str(fields))

    result = run_writer(workspace, "Continue from the trial.")
    fields = writer.supervisor.parse_handoff_file(handoff_path)
    check("a second write increments the counter", fields["restart-counter"] == "2", result.stdout)

    result = run_writer(workspace, "Stop and ask first.", "--dont-restart")
    fields = writer.supervisor.parse_handoff_file(handoff_path)
    check("dont-restart is written when asked", "dont-restart" in fields, str(fields))

    result = run_writer(workspace, "   \n\t  ")
    check("an empty next step is refused", result.returncode == 2, result.stdout)
    check("the refusal explains why", "empty" in result.stderr, result.stderr)
    fields = writer.supervisor.parse_handoff_file(handoff_path)
    check("a refused write leaves the previous handoff intact",
          fields["next-step"] == "Stop and ask first.", fields["next-step"])

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", "tester",
         "--next-step-file", str(workspace / "no-such-file.txt"),
         "--handoff-dir", str(workspace)],
        capture_output=True, text=True, check=False,
    )
    check("a missing next-step file is refused", result.returncode == 2, result.stdout)

    check("no partial file is left behind",
          not list(workspace.glob("*.partial")), str(list(workspace.glob("*.partial"))))


def run_liveness_report_cases(workspace: Path):
    """The write and the liveness report are one decision: a handoff nobody is
    watching must not stop the agent working."""
    result = run_writer(workspace, "Continue the walk.")
    check("with no supervisor, the writer exits 1", result.returncode == 1, result.stdout)
    check("with no supervisor, the agent is told to keep working",
          "keep working" in result.stderr, result.stderr)
    check("with no supervisor, the write still happened",
          (workspace / "tester-handoff.md").is_file(), "handoff missing")

    writer.supervisor.stamp_heartbeat(workspace / "tester-supervisor-state.json", {"session_id": "s"})
    result = run_writer(workspace, "Continue the walk.")
    check("with a live supervisor, the writer exits 0", result.returncode == 0, result.stderr)
    check("with a live supervisor, the agent is told to stop and wait",
          "Stop working now and wait" in result.stdout, result.stdout)

    writer.supervisor.write_supervisor_state(
        workspace / "tester-supervisor-state.json", {"last_poll_at": "not a timestamp"}
    )
    result = run_writer(workspace, "Continue the walk.")
    check("an unreadable heartbeat reads as nobody watching", result.returncode == 1, result.stdout)


with tempfile.TemporaryDirectory() as temporary_directory:
    run_collapse_cases()
    run_counter_cases(Path(temporary_directory))
    run_invocation_cases(Path(temporary_directory))
    run_liveness_report_cases(Path(temporary_directory))

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
