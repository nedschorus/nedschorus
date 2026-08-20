#!/usr/bin/env python3
"""Tests for handoff-write-and-check-supervisor.py.

Run: python3 scripts/handoff-write-and-check-supervisor-test.py

Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import os
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
    """Invoke the script as the agent would, returning its completed process.

    The session identity is scrubbed from the environment deliberately. These
    tests run inside a live Claude session, and leaving CLAUDE_PID set would
    have the writer start a real supervisor that kills the very session
    running the tests.
    """
    next_step_path = workspace / "next-step.txt"
    next_step_path.write_text(next_step_text, encoding="utf-8")
    scrubbed_environment = {
        key: value for key, value in os.environ.items()
        if key not in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_PID")
    }
    scrubbed_environment["HANDOFF_SKIP_PROTECTION_AUDIT"] = "1"  # offline tests never call GitHub
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", "tester",
         "--next-step-file", str(next_step_path), "--handoff-dir", str(workspace),
         *extra_arguments],
        capture_output=True, text=True, check=False, env=scrubbed_environment,
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


def handoff_text(workspace: Path, agent: str) -> str:
    return (workspace / f"{agent}-handoff.md").read_text(encoding="utf-8")


def run_multi_line_next_step_cases(workspace: Path):
    """R20: a multi-line next step survives, without changing what old readers see.

    Format in docs/cross-project/fast-handoff-design.md. `next-step:` stays the
    collapsed single line every existing reader handles; a verbatim block is
    appended LAST when, and only when, the text spans lines.
    """
    multi_line = (
        "FIRST ACTION: run the suite.\n"
        "THEN: fix only the locale case.\n"
        "\n"
        "CONTEXT: PRs 86-91 are merged.\n"
    )
    run_writer(workspace, multi_line, "--agent", "blockcase")
    written = handoff_text(workspace, "blockcase")
    lines = written.splitlines()

    check("a multi-line next step still writes a collapsed next-step line",
          "next-step: FIRST ACTION: run the suite. THEN: fix only the locale case. "
          "CONTEXT: PRs 86-91 are merged." in written, written)
    check("a multi-line next step adds the verbatim block",
          "next-step-verbatim: <<END-OF-NEXT-STEP" in written, written)
    check("the block is written LAST, so its lines cannot shadow a real field",
          lines[-1] == "END-OF-NEXT-STEP"
          and lines.index("next-step-verbatim: <<END-OF-NEXT-STEP")
          > max(index for index, line in enumerate(lines) if line.startswith("written-in:")),
          written)
    check("the block preserves the interior blank line",
          "THEN: fix only the locale case.\n\nCONTEXT:" in written, written)
    check("the block does not carry a trailing blank line",
          "\n\nEND-OF-NEXT-STEP" not in written, written)

    # The common case must not change shape at all.
    run_writer(workspace, "one line only\n", "--agent", "singlecase")
    check("a single-line next step writes no block at all",
          "next-step-verbatim" not in handoff_text(workspace, "singlecase"),
          handoff_text(workspace, "singlecase"))

    run_writer(workspace, "\n\n  one line  \n\n", "--agent", "paddedcase")
    check("one line of content wrapped in blank lines writes no block",
          "next-step-verbatim" not in handoff_text(workspace, "paddedcase"),
          handoff_text(workspace, "paddedcase"))

    # A line equal to the terminator would end the block early, so the value
    # would read back as something other than what was given.
    refused = run_writer(workspace, "do the thing\nEND-OF-NEXT-STEP\nand then this\n",
                         "--agent", "terminatorcase")
    check("a next step containing the terminator line is refused",
          refused.returncode == 2, str(refused.returncode))
    check("the terminator refusal names the terminator",
          "END-OF-NEXT-STEP" in refused.stderr, refused.stderr)
    check("the terminator refusal writes nothing",
          not (workspace / "terminatorcase-handoff.md").exists())

    # The refusal is on an EXACT line match, matching the reader. An indented
    # lookalike is ordinary content and must be written, not refused.
    lookalike = run_writer(workspace, "line one\n    END-OF-NEXT-STEP\nline two\n",
                           "--agent", "lookalikecase")
    # Read through exists() rather than handoff_text(): against an implementation
    # that refuses this input there is no file, and a missing-file traceback is
    # not a test result. A crash cannot be told apart from a failure by anyone
    # reading the output.
    lookalike_file = workspace / "lookalikecase-handoff.md"
    check("an indented terminator lookalike is written as content, not refused",
          lookalike_file.exists()
          and "    END-OF-NEXT-STEP" in lookalike_file.read_text(encoding="utf-8"),
          lookalike.stderr or "no file written")

    # The empty refusal is applied to the COLLAPSED value, before any block is
    # considered, so whitespace-only input is refused rather than written as an
    # empty block.
    whitespace_only = run_writer(workspace, "\n   \n\t\n", "--agent", "whitespacecase")
    check("a whitespace-only multi-line next step is still refused",
          whitespace_only.returncode == 2, str(whitespace_only.returncode))


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
    check("with no supervisor, the writer exits 1",
          result.returncode == 1, result.stdout)
    check("with no supervisor, the agent is told to keep working",
          "keep working" in result.stdout, result.stdout)
    check("with no supervisor, the write still happened",
          (workspace / "tester-handoff.md").is_file(), "handoff missing")
    check("with no supervisor, the agent is told the supervised recovery path",
          "resupervise-seat.py tester --machine " in result.stdout
          and str(workspace / "tester-handoff.md") in result.stdout,
          result.stdout)
    check("with no supervisor, the by-hand relaunch is named as the wrong path",
          "another unsupervised seat" in result.stdout, result.stdout)
    check("no supervisor is started for an unseated session",
          not (workspace / "tester-supervisor.log").is_file()
          and "Stop working now and wait" not in result.stdout,
          result.stdout)

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


def run_console_identity_case(workspace: Path):
    """The adopt-and-recycle path is gone (removed 2026-08-14): a session with
    a full environment identity gets exactly the same answer as one without —
    handoff written, nobody watching, relaunch by hand. The identity that once
    triggered a doomed detached supervisor must trigger nothing."""
    next_step_path = workspace / "identity-next-step.txt"
    next_step_path.write_text("Continue the walk.", encoding="utf-8")
    environment = dict(os.environ)
    environment["CLAUDE_CODE_SESSION_ID"] = "test-session"
    environment["CLAUDE_PID"] = "12345"
    environment["HANDOFF_SKIP_PROTECTION_AUDIT"] = "1"
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", "identcase",
         "--next-step-file", str(next_step_path), "--handoff-dir", str(workspace)],
        capture_output=True, text=True, check=False, env=environment,
    )
    check("a session with environment identity still gets no supervisor",
          result.returncode == 1 and not (workspace / "identcase-supervisor.log").is_file(),
          result.stdout + result.stderr)
    check("the identity path also names the supervised recovery path",
          "resupervise-seat.py identcase --machine " in result.stdout, result.stdout)
    # The seat's machine must be named, never left to the default: the same agent
    # name on both machines is two unrelated seats, so a box seat's advice run on
    # the Mac would target a same-named Mac seat.
    check("the advice names the machine it was printed on",
          ("--machine ubuntu" if sys.platform.startswith("linux") else "--machine mac")
          in result.stdout, result.stdout)


def run_agent_name_and_claim_cases(workspace: Path):
    """One agent name is one seat, and a seat is one directory.

    The name selects the handoff file, the supervisor state and the lock, so
    two sessions sharing a name share all three. On 2026-08-16 two
    hand-started sessions were both called `new-vp`: one wrote counter 10,
    the other wrote counter 11 seconds later, and the first was gone — never
    archived, because retention keeps the last two generations of one file
    rather than one file per session.
    """
    seat_one = workspace / "seat-one"
    seat_two = workspace / "seat-two"
    handoffs = workspace / "handoffs"
    for directory in (seat_one, seat_two, handoffs):
        directory.mkdir(parents=True, exist_ok=True)

    def write_from(directory: Path, text: str, *extra):
        next_step_path = directory / "next-step.txt"
        next_step_path.write_text(text, encoding="utf-8")
        environment = {
            key: value for key, value in os.environ.items()
            if key not in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_PID")
        }
        environment["HANDOFF_SKIP_PROTECTION_AUDIT"] = "1"
        return subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--next-step-file", str(next_step_path),
             "--handoff-dir", str(handoffs), *extra],
            capture_output=True, text=True, check=False, env=environment, cwd=str(directory),
        )

    # The name defaults to the directory, which is unique per worktree.
    write_from(seat_one, "first seat's work")
    check("the agent name defaults to the working directory's name",
          (handoffs / "seat-one-handoff.md").is_file(),
          str(sorted(item.name for item in handoffs.iterdir())))

    # Resolved, because macOS reports /private/var where the tempdir says /var.
    first_body = (handoffs / "seat-one-handoff.md").read_text(encoding="utf-8")
    check("the handoff records the directory that wrote it",
          f"written-in: {seat_one.resolve()}" in first_body, first_body)

    # A second seat gets its own file rather than the first seat's.
    write_from(seat_two, "second seat's work")
    check("a second directory writes its own handoff, not the first's",
          (handoffs / "seat-two-handoff.md").is_file(),
          str(sorted(item.name for item in handoffs.iterdir())))
    check("the first seat's handoff is untouched",
          (handoffs / "seat-one-handoff.md").read_text(encoding="utf-8") == first_body)

    # The collision that actually happened: a foreign directory, one name.
    foreign = write_from(seat_two, "would clobber", "--agent", "seat-one")
    check("a foreign directory claiming the name is refused", foreign.returncode == 2, foreign.stderr)
    check("the refusal names both directories",
          str(seat_one) in foreign.stderr and str(seat_two) in foreign.stderr, foreign.stderr)
    check("the refusal teaches the fix", "--claim" in foreign.stderr, foreign.stderr)
    check("nothing was written on the refusal",
          (handoffs / "seat-one-handoff.md").read_text(encoding="utf-8") == first_body)

    # Succession is not a collision: the same directory writes again.
    again = write_from(seat_one, "same seat, next generation")
    check("the same directory may write its own handoff again", again.returncode != 2, again.stderr)

    # --claim is the deliberate override.
    claimed = write_from(seat_two, "taking the name", "--agent", "seat-one", "--claim")
    check("--claim takes the name deliberately", claimed.returncode != 2, claimed.stderr)
    check("--claim really replaced the contents",
          "taking the name" in (handoffs / "seat-one-handoff.md").read_text(encoding="utf-8"))


with tempfile.TemporaryDirectory() as temporary_directory:
    run_collapse_cases()
    run_multi_line_next_step_cases(Path(temporary_directory))
    run_counter_cases(Path(temporary_directory))
    run_invocation_cases(Path(temporary_directory))
    run_liveness_report_cases(Path(temporary_directory))
    run_console_identity_case(Path(temporary_directory))
    run_agent_name_and_claim_cases(Path(temporary_directory))

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
