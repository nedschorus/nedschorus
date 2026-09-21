#!/usr/bin/env python3
"""Tests for handoff-supervisor.py.

Run: python3 nc-systems/handoff/tests/handoff-supervisor-test.py
Add --canary to also run the two live task-preseed canaries, which launch
real headless sessions. Pre-seed rides undocumented harness state; an
upgrade breaking it shows up as a successor finding its predecessor's tasks
missing (the queues are the backstop), and these two cases are the
diagnosis to run when that fires.

Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import dataclasses
import importlib.util
import inspect
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

# This suite sits at nc-systems/handoff/tests/, so the system it tests is one
# directory up and the repository root is three. SYSTEM_DIRECTORY and
# REPOSITORY_ROOT name those depths once each; a with_name() lookup here
# would resolve inside tests/ and find nothing.
SYSTEM_DIRECTORY = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = SYSTEM_DIRECTORY.parent.parent

SCRIPT_PATH = SYSTEM_DIRECTORY / "handoff-supervisor.py"

_spec = importlib.util.spec_from_file_location("handoff_supervisor", SCRIPT_PATH)
supervisor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(supervisor)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def nothing_is_appended_to(prompt, tail, expected_rest_of_prompt):
    """`tail` is in `prompt`, and what follows it is EXACTLY
    `expected_rest_of_prompt` -- through to the end of the prompt.

    A plain `tail in prompt` passes when text is APPENDED to the pinned
    sentence, which is how three of these pins went blind: each was named
    "exactly" while an extra sentence bolted onto the end of the real one was
    invisible (swept 2026-09-20).

    The first repair listed the sentences that may legitimately follow and
    accepted any rest STARTING with one of them. That bounded the beginning of
    what follows and never its end, so the defect survived in the shape it was
    written to catch: " NOTE: Resume each one by its id." appended to the
    orphaned-subagent roster sentence left all 228 cases green, and resume-by-id
    is the exact instruction that sentence exists to keep out of a successor's
    prompt -- a dead subagent cannot be resumed by id across a reincarnation
    (probed 2026-08-29). Reviewed 2026-09-21.

    So the rest is pinned whole. build_ignition_prompt's segments are
    conditional in production, but each case's own fixture decides every one of
    them, so what follows the pinned sentence is fully determined and can be
    spelled out to the last character. A fixture that gains a branch sync, a
    roster, an unterminated verbatim block, or a different next step must extend
    `expected_rest_of_prompt` with the segment it adds -- never reopen the tail.
    """
    return tail in prompt and prompt.split(tail, 1)[1] == expected_rest_of_prompt


def run_offline_cases(workspace: Path):
    # --- Handoff parsing --------------------------------------------------
    handoff_path = workspace / "agent-handoff.md"
    handoff_path.write_text(
        "# Handoff\n"
        "\n"
        "written-at: 2026-08-06T12:00:00Z\n"
        "read-starting-here: the prompt that opened this topic\n"
        "next-step: land the supervisor tests\n"
        "restart-counter: 7\n"
        "\n"
        "Prose below the fields: next-step: this later line must not win.\n",
        encoding="utf-8",
    )
    fields = supervisor.parse_handoff_file(handoff_path)
    check("parses each handoff field", fields["restart-counter"] == "7", str(fields))
    check("first occurrence of a field wins", fields["next-step"] == "land the supervisor tests", fields["next-step"])
    check("reads the counter as an integer", supervisor.counter_from(fields) == 7)
    check("a missing counter reads as None", supervisor.counter_from({}) is None)
    check("a non-numeric counter reads as None", supervisor.counter_from({"restart-counter": "soon"}) is None)

    # --- Consumed-marker semantics ---------------------------------------
    state_path = workspace / "agent-supervisor-state.json"
    check("absent state starts fresh", supervisor.read_supervisor_state(state_path)["consumed_counter"] is None)
    supervisor.write_supervisor_state(state_path, {"consumed_counter": 7, "session_id": "s", "generation": 3})
    check("state round-trips", supervisor.read_supervisor_state(state_path)["consumed_counter"] == 7)
    state_path.write_text("{ not json", encoding="utf-8")
    check("unreadable state starts fresh", supervisor.read_supervisor_state(state_path)["generation"] == 0)

    # --- Heartbeat and liveness ------------------------------------------
    heartbeat_state_path = workspace / "heartbeat-supervisor-state.json"
    alive, explanation = supervisor.supervisor_liveness(heartbeat_state_path)
    check(
        "no state file reads as no supervisor",
        not alive and "no supervisor state" in explanation,
        explanation,
    )

    heartbeat_lock_path = workspace / "heartbeat-supervisor.lock"

    supervisor.write_supervisor_state(heartbeat_state_path, {"session_id": "s"})
    alive, explanation = supervisor.supervisor_liveness(heartbeat_state_path)
    check("a state file with no lock beside it reads as dead",
          not alive and "no supervisor is watching" in explanation
          and "no supervisor lock" in explanation, explanation)

    # THE 60-SECOND HOLE (nedschorus#242 change 1). A heartbeat stamped a
    # moment ago says nothing about whether the supervisor is still there: it
    # was read as fresh for sixty seconds after the last stamp, so a
    # supervisor killed seconds ago still read as alive — measured on ned-box,
    # recovery refused a killed seat until 60 seconds after the kill, and the
    # login restart was predicted to fall inside that window on a fast boot.
    supervisor.stamp_heartbeat(heartbeat_state_path, {"session_id": "s"})
    heartbeat_lock_path.write_text("99999999\n", encoding="utf-8")
    alive, explanation = supervisor.supervisor_liveness(heartbeat_state_path)
    check("a stamp from a second ago does NOT read as alive when the process is gone",
          not alive, explanation)
    check("and it says the recorded process is not there",
          "99999999" in explanation, explanation)

    # The mirror: the heartbeat no longer decides in either direction. A
    # supervisor busy enough to have missed its stamps is still running.
    with a_process_that_looks_like_a_supervisor(workspace, "heartbeat") as running:
        heartbeat_lock_path.write_text(f"{running.pid}\n", encoding="utf-8")
        supervisor.write_supervisor_state(
            heartbeat_state_path,
            {"last_poll_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()},
        )
        alive, explanation = supervisor.supervisor_liveness(heartbeat_state_path)
        check("a stamp five minutes old reads as ALIVE when the supervisor is running",
              alive, explanation)
        check("and the heartbeat age is still reported, since it is worth knowing",
              "5m" in explanation or "300s" in explanation or "minute" in explanation,
              explanation)

        # A state file that cannot be read at all does not change the verdict:
        # the process answers the question, the file only colours the detail.
        supervisor.write_supervisor_state(heartbeat_state_path,
                                          {"last_poll_at": "not a timestamp"})
        alive, explanation = supervisor.supervisor_liveness(heartbeat_state_path)
        check("an unreadable stamp does not kill a supervisor that is running",
              alive, explanation)

        # A stamp with no timezone is read as UTC, the only writer's zone; a
        # naive stamp used to raise TypeError on the subtraction instead.
        bare_stamp = (datetime.now(timezone.utc) - timedelta(seconds=3)).replace(tzinfo=None)
        supervisor.write_supervisor_state(heartbeat_state_path,
                                          {"last_poll_at": bare_stamp.isoformat()})
        alive, explanation = supervisor.supervisor_liveness(heartbeat_state_path)
        check("a stamp with no timezone reads as UTC, reporting its age in seconds",
              alive and any(explanation.endswith(f", last heartbeat {age}s ago")
                            for age in range(10)),
              explanation)

        check_result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--check", "--agent", "heartbeat",
             "--handoff-dir", str(workspace)],
            capture_output=True, text=True, check=False,
        )
        check("--check exits zero for a live supervisor", check_result.returncode == 0,
              f"code {check_result.returncode}: {check_result.stdout.strip()}")

    # Process-id reuse through the lock: the id is live again, as something else.
    unrelated = subprocess.Popen(  # pylint: disable=consider-using-with
        [sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        heartbeat_lock_path.write_text(f"{unrelated.pid}\n", encoding="utf-8")
        supervisor.stamp_heartbeat(heartbeat_state_path, {"session_id": "s"})
        alive, explanation = supervisor.supervisor_liveness(heartbeat_state_path)
        check("a reused process id does not resurrect a dead supervisor",
              not alive and "not a supervisor" in explanation, explanation)
    finally:
        unrelated.kill()
        unrelated.wait()

    heartbeat_lock_path.write_text("not a number\n", encoding="utf-8")
    alive, explanation = supervisor.supervisor_liveness(heartbeat_state_path)
    check("an unreadable lock reads as dead", not alive, explanation)

    heartbeat_lock_path.unlink(missing_ok=True)
    check_result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--check", "--agent", "heartbeat",
         "--handoff-dir", str(workspace)],
        capture_output=True, text=True, check=False,
    )
    check("--check exits non-zero for a dead supervisor", check_result.returncode == 1,
          f"code {check_result.returncode}: {check_result.stdout.strip()}")

    # --- The written-at stamp and wariness sentence -----------------------
    # The successor computes the elapsed time from `date` itself and applies
    # age-proportional wariness (user-approved 2026-08-30); the sentence
    # carries the handoff's written-at stamp rendered as UTC with a Z, never
    # a composition-time elapsed phrase. The sentence ends at the gap itself
    # (user's second round, ruled 2026-08-30 on a rendered mock): the "the
    # older it is, the more you must re-verify" tail was cut, so the exact
    # equality below FAILS against the pre-revision supervisor.
    recent = (datetime.now(timezone.utc) - timedelta(minutes=12)).isoformat()
    check("a Z-suffixed written-at is rendered exactly, with the wariness rule",
          supervisor.written_at_wariness_sentence("2026-08-30T18:04:00Z")
          == ("written at 2026-08-30T18:04:00Z. Calculate from `date` how long "
              "ago that was, and be wary of obsolescence and drift in everything "
              "in this handoff in proportion to that gap."),
          supervisor.written_at_wariness_sentence("2026-08-30T18:04:00Z"))
    check("a +00:00 offset with microseconds renders as the same UTC stamp with a Z",
          supervisor.written_at_wariness_sentence("2026-08-30T18:04:00.123456+00:00")
          .startswith("written at 2026-08-30T18:04:00Z. "),
          supervisor.written_at_wariness_sentence("2026-08-30T18:04:00.123456+00:00"))
    check("a non-UTC offset converts to UTC before rendering",
          supervisor.written_at_wariness_sentence("2026-08-30T11:04:00-07:00")
          .startswith("written at 2026-08-30T18:04:00Z. "),
          supervisor.written_at_wariness_sentence("2026-08-30T11:04:00-07:00"))
    check("unparseable timestamp still warns",
          "stale" in supervisor.written_at_wariness_sentence("whenever"))
    return recent


def stub_process(poll_result):
    """A stand-in for a session process: poll() reports the given exit state."""
    return SimpleNamespace(poll=lambda: poll_result)


def run_exit_handoff_cases(workspace: Path):
    """A headless session exits when its turn ends, so its handoff arrives AS
    a process exit. Exit with a new counter on disk must read as a handoff;
    exit without one is abandonment."""
    handoff_path = workspace / "exitcase-handoff.md"
    state_path = workspace / "exitcase-supervisor-state.json"

    handoff_path.write_text(
        "written-at: 2026-08-06T12:00:00Z\nnext-step: drain the tasks\nrestart-counter: 8\n",
        encoding="utf-8",
    )
    fields = supervisor.wait_for_handoff(stub_process(0), handoff_path, 7, state_path, {})
    check(
        "exit with a new counter reads as a handoff",
        fields is not None and supervisor.counter_from(fields) == 8,
        str(fields),
    )

    fields = supervisor.wait_for_handoff(stub_process(0), handoff_path, 8, state_path, {})
    check("exit with the already-consumed counter reads as abandonment", fields is None, str(fields))

    fields = supervisor.wait_for_handoff(
        stub_process(0), workspace / "never-written-handoff.md", 7, state_path, {}
    )
    check("exit with no handoff file reads as abandonment", fields is None, str(fields))

    fields = supervisor.wait_for_handoff(stub_process(None), handoff_path, 7, state_path, {})
    check(
        "a running session's new handoff is seen without an exit",
        fields is not None and supervisor.counter_from(fields) == 8,
        str(fields),
    )


def run_adoption_cases(workspace: Path):
    """Adopting a running session is what lets a hand-started agent reincarnate:
    a supervisor normally owns only the process it launched itself."""
    # Not a context manager: the point is a process this test does NOT own a
    # handle to in the supervisor, which is what adoption exists for.
    sleeper = subprocess.Popen(  # pylint: disable=consider-using-with
        [sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        adopted = supervisor.AdoptedSession("some-session-id", sleeper.pid)
        check("an adopted live process reads as running", adopted.poll() is None)
        adopted.terminate()
        sleeper.wait(timeout=10)
        check("an adopted process can be terminated", adopted.poll() == 0)
        check("terminating an already-gone process is not an error",
              adopted.terminate() is None)
    finally:
        if sleeper.poll() is None:
            sleeper.kill()
            sleeper.wait()

    gone = supervisor.AdoptedSession("some-session-id", 99999999)
    check("a process id that does not exist reads as gone", gone.poll() == 0)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", "adopter",
         "--handoff-dir", str(workspace), "--adopt-session-id", "an-id"],
        capture_output=True, text=True, check=False,
    )
    check("adopting without a process id is refused", result.returncode == 2, result.stderr)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", "adopter", "--cd", str(workspace),
         "--handoff-dir", str(workspace), "--adopt-session-id", "an-id",
         "--adopt-process-id", "99999999"],
        capture_output=True, text=True, check=False,
    )
    check("adopting a process that is already gone is refused",
          result.returncode == 2 and "already gone" in result.stderr, result.stderr)


def run_dont_restart_without_a_terminal_case(workspace: Path):
    """A supervisor whose stdin is redirected has no terminal. Asking `restart? y/n`
    there raises EOFError before the consumed counter is recorded, so the next
    supervisor re-fires on the stale handoff — launching a session and killing
    it immediately."""
    handoff_directory = workspace / "noterm"
    handoff_directory.mkdir(parents=True, exist_ok=True)
    (handoff_directory / "noterm-handoff.md").write_text(
        "written-at: 2026-08-06T12:00:00Z\n"
        "next-step: should not relaunch\n"
        "restart-counter: 1\n"
        "dont-restart: the user asked to be consulted\n",
        encoding="utf-8",
    )
    stub_agent = handoff_directory / "stub-agent"
    stub_agent.write_text("#!/bin/sh\nsleep 30\n", encoding="utf-8")
    stub_agent.chmod(0o755)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", "noterm", "--cd", str(workspace),
         "--handoff-dir", str(handoff_directory), "--agent-command", str(stub_agent)],
        capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL, timeout=60,
    )
    check("dont-restart without a terminal exits cleanly, not on EOFError",
          result.returncode == 0 and "EOFError" not in result.stderr, result.stderr[-300:])
    check("dont-restart without a terminal says why it stopped",
          "no terminal to ask on" in result.stdout, result.stdout[-300:])

    state = supervisor.read_supervisor_state(handoff_directory / "noterm-supervisor-state.json")
    check("the consumed counter is recorded before stopping",
          state.get("consumed_counter") == 1, str(state))
    # nedschorus#242 change 2: a seat stood down on dont-restart carries an exit
    # record, so recovery offers it rather than resuming a session that asked
    # not to be relaunched. This stop is boot-ignition's, before any launch, so
    # the code is unknown — and present all the same.
    check("dont-restart at boot records the agent's exit, its code unknown",
          supervisor.agent_exit_record_from_supervisor_state(state) is not None
          and state.get(supervisor.AGENT_EXIT_CODE_STATE_KEY, "absent") is None,
          str(state))


def run_first_prompt_file_cases(workspace: Path):
    """The founding boot passes its prompt as a file the supervisor reads
    itself, so the content never rides through nested shell quoting."""
    prompt_path = workspace / "founding-prompt.txt"
    prompt_path.write_text("You are choirmaster.\nRead the plan.\n", encoding="utf-8")
    stub_agent = workspace / "prompt-stub-agent"
    stub_agent.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    stub_agent.chmod(0o755)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", "promptcase", "--cd", str(workspace),
         "--handoff-dir", str(workspace / "prompt-handoffs"),
         "--agent-command", str(stub_agent),
         "--first-prompt-file", str(workspace / "no-such-prompt.txt")],
        capture_output=True, text=True, check=False, timeout=30,
    )
    check("a missing first-prompt file is refused before launch",
          result.returncode == 2 and "does not exist" in result.stderr, result.stderr[-200:])

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", "promptcase", "--cd", str(workspace),
         "--handoff-dir", str(workspace / "prompt-handoffs"),
         "--agent-command", str(stub_agent),
         "--first-prompt-file", str(prompt_path)],
        capture_output=True, text=True, check=False, timeout=30,
    )
    check("a first-prompt file launches cleanly", result.returncode == 0, result.stderr[-200:])


@contextlib.contextmanager
def a_process_that_looks_like_a_supervisor(workspace: Path, agent: str,
                                          agent_argument=None, equals_form=False):
    """A live process whose command line is a supervisor's for `agent`.

    The identity check reads the command line, so the process has to have a
    real one: a file actually NAMED handoff-supervisor.py, run with --agent.
    It sleeps; nothing about the supervisor's behaviour is being tested here,
    only that it can be recognised.
    """
    stub_directory = workspace / f"looks-like-a-supervisor-for-{agent}"
    stub_directory.mkdir(parents=True, exist_ok=True)
    stub = stub_directory / "handoff-supervisor.py"
    stub.write_text("import time\ntime.sleep(120)\n", encoding="utf-8")
    named = agent if agent_argument is None else agent_argument
    arguments = ([f"--agent={named}"] if equals_form else ["--agent", named])
    process = subprocess.Popen(  # pylint: disable=consider-using-with
        [sys.executable, str(stub), *arguments, "--cd", str(stub_directory)])
    try:
        yield process
    finally:
        process.kill()
        process.wait()


def run_process_identity_cases(workspace: Path):
    """A supervisor is judged by its process, not by how fresh its heartbeat is
    (nedschorus#242 change 1).

    The heartbeat cannot answer "is one running now". It is stamped every
    HEARTBEAT_INTERVAL_SECONDS, and the rule this replaced read it as fresh for
    sixty seconds afterwards, so for a full minute after a supervisor died the
    file still said it was alive — and that minute is exactly when the login
    restart runs.
    A bare process-id check cannot answer it either: ids are reused across the
    very reboot this serves, and the lock file holding one outlives the boot.
    """
    for impossible in (0, -1, -12345):
        alive, detail = supervisor.process_is_supervisor_for_agent(impossible, "x")
        check(f"process id {impossible} is not a supervisor", not alive, detail)

    alive, detail = supervisor.process_is_supervisor_for_agent(99999999, "x")
    check("a process id that is not running is not a supervisor", not alive, detail)

    # Process-id reuse, which is the whole reason a bare check will not do.
    unrelated = subprocess.Popen(  # pylint: disable=consider-using-with
        [sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        alive, detail = supervisor.process_is_supervisor_for_agent(unrelated.pid, "x")
        check("a live process that is not a supervisor is not one, however live it is",
              not alive and "not a supervisor" in detail, detail)
    finally:
        unrelated.kill()
        unrelated.wait()

    # ps is a program and a program can fail to run — a fork or exec failure
    # under load, which this machine reaches when several sweeps run at once.
    # That is a third answer, and filing it under "not running" makes a
    # confident false statement about a live process (found in review of
    # a82b49e). The reader keeps the three apart.
    ps_could_not_run = lambda process_id: (None, False)
    ps_says_no_such_process = lambda process_id: (None, True)

    # The real reader's own three answers, with nothing patched inside it: a
    # live process, a dead one, and ps not running at all. The last is driven
    # by making ps unfindable, which is a genuine OSError out of
    # subprocess.run — the same path a fork or exec failure under load takes.
    # Injected readers cannot cover this, so without it the defect found in
    # review of a82b49e could be reintroduced in the reader and no case would
    # notice.
    line, answered = supervisor.read_process_command_line(os.getpid())
    check("the real reader reads this process's own command line",
          answered and line is not None and "python" in line.lower(), (answered, line))
    line, answered = supervisor.read_process_command_line(99999999)
    check("the real reader says ps ANSWERED for a process that is not there",
          answered and line is None, (answered, line))
    real_search_path = os.environ.get("PATH", "")
    try:
        os.environ["PATH"] = ""
        line, answered = supervisor.read_process_command_line(os.getpid())
        check("the real reader says ps did NOT answer when ps cannot be run",
              not answered and line is None, (answered, line))
    finally:
        os.environ["PATH"] = real_search_path
    check("and the reader works again once ps is findable",
          supervisor.read_process_command_line(os.getpid())[1])

    # The OTHER way ps fails to answer: it runs and never finishes. Driven with
    # a real `ps` early on PATH that really hangs, a real subprocess.run
    # timeout, and a real TimeoutExpired — nothing patched inside the reader,
    # for the same reason as the block above.
    #
    # This case exists because mutation 18 of the #328 self-check SURVIVED:
    # dropping subprocess.SubprocessError from the reader's except tuple leaves
    # TimeoutExpired escaping the reader, which kills a supervisor at startup
    # instead of reporting "could not ask" and falling back to os.kill. Nothing
    # exercised the timeout, so nothing noticed. The 15 is now a module
    # constant precisely so this case can lower it; a default argument could not
    # be lowered from here, which is the trap the NOTE in
    # process_is_supervisor_for_agent describes.
    hanging_ps_directory = workspace / "hanging-ps"
    hanging_ps_directory.mkdir()
    hanging_ps = hanging_ps_directory / "ps"
    hanging_ps.write_text("#!/bin/sh\nsleep 30\n", encoding="utf-8")
    hanging_ps.chmod(0o755)
    real_read_timeout = supervisor.PROCESS_COMMAND_LINE_READ_TIMEOUT_SECONDS
    try:
        os.environ["PATH"] = f"{hanging_ps_directory}:{real_search_path}"
        supervisor.PROCESS_COMMAND_LINE_READ_TIMEOUT_SECONDS = 0.25
        started_waiting = time.monotonic()
        line, answered = supervisor.read_process_command_line(os.getpid())
        waited = time.monotonic() - started_waiting
    finally:
        os.environ["PATH"] = real_search_path
        supervisor.PROCESS_COMMAND_LINE_READ_TIMEOUT_SECONDS = real_read_timeout
    check("a ps that hangs is reported as not having answered, not as 'no such process'",
          not answered and line is None, (answered, line))
    check("and the reader gives up at the timeout instead of waiting out ps",
          waited < 5, waited)
    check("and the timeout is a module constant the suite can lower, not a literal",
          supervisor.PROCESS_COMMAND_LINE_READ_TIMEOUT_SECONDS == 15,
          supervisor.PROCESS_COMMAND_LINE_READ_TIMEOUT_SECONDS)

    alive, detail = supervisor.process_is_supervisor_for_agent(
        99999999, "x", read_command_line=ps_says_no_such_process)
    check("ps answering 'no such process' means not a supervisor",
          not alive and "not running" in detail, detail)

    # os.kill answers EXISTENCE and cannot fail to: ProcessLookupError means
    # gone. So a lock left by a crashed supervisor, holding an id that no longer
    # exists, is still recognised as stale with no ps at all. Without this the
    # fail-closed rule wedged the ordinary post-crash state — the very state the
    # lock's reclaim exists to serve.
    check("os.kill says a process that is not there is not there",
          not supervisor.process_exists_by_signal(99999999))
    check("and says this process is",
          supervisor.process_exists_by_signal(os.getpid()))
    # A process that exists but cannot be signalled still exists. Process 1 is
    # root-owned on both machines, so os.kill raises PermissionError for it
    # while the process is plainly there; reading that as "gone" would be the
    # unsafe direction. Signal 0 sends nothing, so this probe is inert.
    #
    # LIMIT, stated rather than discovered: this case is VACUOUS under root.
    # As root os.kill(1, 0) simply succeeds, so the assertion passes through
    # the success branch and the PermissionError branch it was written for is
    # never reached. It is honest for this fleet, which runs as nedlern on
    # ned-box and el on the Mac, and it is not a check anyone should trust
    # after a change to who the seats run as. main-gatekeeper-test.py detects
    # the same condition and skips; here the case is kept unconditional because
    # passing vacuously is harmless and disappearing silently is not.
    check("a process that exists but cannot be signalled still counts as existing",
          supervisor.process_exists_by_signal(1))

    alive, detail = supervisor.process_is_supervisor_for_agent(
        99999999, "x", read_command_line=ps_could_not_run)
    check("with no ps, a dead id is still answered: not a supervisor",
          not alive and "os.kill" in detail, detail)

    # Only a process that really exists, and cannot be identified, is assumed
    # to be a supervisor.
    unidentifiable = subprocess.Popen(  # pylint: disable=consider-using-with
        [sys.executable, "-c", "import time; time.sleep(60)"])
    complaints = io.StringIO()
    try:
        with contextlib.redirect_stderr(complaints):
            alive, detail = supervisor.process_is_supervisor_for_agent(
                unidentifiable.pid, "x", read_command_line=ps_could_not_run)
        check("a live but unidentifiable process IS assumed to be the supervisor",
              alive, detail)
        check("and it says it cannot tell, rather than claiming the process is gone",
              "cannot tell" in detail and "not running" not in detail, detail)
        check("and the wedge is not mute: it says so on stderr, naming ps",
              "could not identify" in complaints.getvalue()
              and "ps could not be run" in complaints.getvalue(),
              complaints.getvalue())
        check("and names the way out, since whoever asked is now stuck on an assumption",
              "lock is removed" in complaints.getvalue(), complaints.getvalue())
        # The remedy is the same for every caller; the CONSEQUENCE is not. This
        # sentence once said "this seat will not start", which is true of
        # claim_supervisor_lock and of nothing else that asks — the other
        # callers refuse a repair, stop an agent, or set an exit code
        # (#328 follow-up round, nedschorus#242).
        check("and does not claim a consequence only one of the callers has",
              "this seat will not start" not in complaints.getvalue(),
              complaints.getvalue())
    finally:
        unidentifiable.kill()
        unidentifiable.wait()

    with a_process_that_looks_like_a_supervisor(workspace, "identity-seat") as running:
        alive, detail = supervisor.process_is_supervisor_for_agent(
            running.pid, "identity-seat")
        check("a running supervisor for this agent is recognised", alive, detail)
        # Seat names are letters, digits, hyphen and underscore, so the agent
        # argument is matched whole. A substring test would read this process
        # as the supervisor of a different seat whose name it merely begins.
        for other in ("identity-seat-2", "identity", "dentity-seat", "IDENTITY-SEAT"):
            alive, detail = supervisor.process_is_supervisor_for_agent(running.pid, other)
            check(f"it is not the supervisor of {other}", not alive, detail)

    check("and once it is gone it is no longer recognised",
          not supervisor.process_is_supervisor_for_agent(running.pid, "identity-seat")[0])

    # argparse accepts --agent=NAME as well as --agent NAME. No launcher writes
    # it that way today (checked across both launchers and both recovery
    # tools), but a supervisor started by hand that way must still be
    # recognised — otherwise its lock reads as stale and a second supervisor
    # starts on the same agent, which is what the lock exists to prevent.
    with a_process_that_looks_like_a_supervisor(
            workspace, "equals-seat", equals_form=True) as running:
        alive, detail = supervisor.process_is_supervisor_for_agent(
            running.pid, "equals-seat")
        check("a supervisor started with --agent=NAME is recognised too", alive, detail)

    # A python process running some other script for the same agent is not a
    # supervisor: the script name has to match as well as the agent.
    other_script = workspace / "not-the-supervisor.py"
    other_script.write_text("import time\ntime.sleep(120)\n", encoding="utf-8")
    impostor = subprocess.Popen(  # pylint: disable=consider-using-with
        [sys.executable, str(other_script), "--agent", "identity-seat"])
    try:
        alive, detail = supervisor.process_is_supervisor_for_agent(
            impostor.pid, "identity-seat")
        check("another script run with the same --agent is not the supervisor",
              not alive, detail)
    finally:
        impostor.kill()
        impostor.wait()


def run_lock_cases(workspace: Path):
    """Two supervisors on one agent would each kill the session and each launch
    a successor, so the second must refuse to start."""
    lock_path = workspace / "locktest-supervisor.lock"
    check("the lock is claimable when free", supervisor.claim_supervisor_lock(lock_path))
    check("the lock records the holder", lock_path.read_text().strip() == str(os.getpid()))
    check("the same process may re-enter its own lock", supervisor.claim_supervisor_lock(lock_path))

    lock_path.write_text("99999999\n", encoding="utf-8")
    check("a lock held by a dead process is reclaimed", supervisor.claim_supervisor_lock(lock_path))

    # Changed with nedschorus#242 change 1: a live process id is not enough.
    # The lock file survives a reboot, and process ids are reused across
    # exactly that reboot, so a stale lock whose id now belongs to something
    # else would refuse the very supervisor the login restart just asked for.
    # What blocks a second supervisor is a live supervisor FOR THIS AGENT.
    live_stranger = subprocess.Popen(  # pylint: disable=consider-using-with
        [sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        lock_path.write_text(f"{live_stranger.pid}\n", encoding="utf-8")
        check("a lock whose id now belongs to an unrelated live process is reclaimed",
              supervisor.claim_supervisor_lock(lock_path))
    finally:
        live_stranger.kill()
        live_stranger.wait()

    with a_process_that_looks_like_a_supervisor(workspace, "locktest") as running:
        lock_path.write_text(f"{running.pid}\n", encoding="utf-8")
        check("a lock held by a live supervisor for this agent blocks a second one",
              not supervisor.claim_supervisor_lock(lock_path))

    # The same lock, the same id, once that supervisor is gone.
    check("and is reclaimed once that supervisor has exited",
          supervisor.claim_supervisor_lock(lock_path))

    # Both callers of the identity check must fail CLOSED when ps cannot be
    # asked. For the lock that means refusing to claim: a seat that stays down
    # is visible and recoverable, while two supervisors on one agent each kill
    # the session and each launch a successor. This is the caller with nothing
    # behind it — assess_seat still has the tmux check ahead of it, this has
    # none (found in review of a82b49e).
    with a_process_that_looks_like_a_supervisor(workspace, "locktest") as running:
        lock_path.write_text(f"{running.pid}\n", encoding="utf-8")
        real_identity_check = supervisor.process_is_supervisor_for_agent
        try:
            supervisor.process_is_supervisor_for_agent = (
                lambda process_id, agent_name, **_: real_identity_check(
                    process_id, agent_name,
                    read_command_line=lambda _p: (None, False)))
            check("a lock is NOT reclaimed when ps could not say who holds it",
                  not supervisor.claim_supervisor_lock(lock_path))
            check("and the live supervisor still holds it",
                  lock_path.read_text().strip() == str(running.pid),
                  lock_path.read_text())
        finally:
            supervisor.process_is_supervisor_for_agent = real_identity_check

    # THE WEDGE, which fail-closed-everywhere would have shipped. A crashed seat
    # leaves a stale lock holding a dead id, and claim_supervisor_lock runs when
    # a supervisor STARTS. Refusing to reclaim that lock whenever ps is
    # unavailable means no supervisor can start for the seat at all — breaking
    # exactly the state the reclaim exists to serve. os.kill answers it.
    lock_path.write_text("99999999\n", encoding="utf-8")
    real_identity_check = supervisor.process_is_supervisor_for_agent
    try:
        supervisor.process_is_supervisor_for_agent = (
            lambda process_id, agent_name, **_: real_identity_check(
                process_id, agent_name, read_command_line=lambda _p: (None, False)))
        check("a crashed seat's stale lock is still reclaimed when ps cannot be run",
              supervisor.claim_supervisor_lock(lock_path))
    finally:
        supervisor.process_is_supervisor_for_agent = real_identity_check

    # The same unknown answer through supervisor_liveness: a supervisor that
    # cannot be ruled out is reported as watching, so nothing recovers over it.
    unknown_state_path = workspace / "unknown-supervisor-state.json"
    unknown_lock_path = workspace / "unknown-supervisor.lock"
    supervisor.stamp_heartbeat(unknown_state_path, {"session_id": "s"})
    # A process that really exists, so existence is not what is unknown here —
    # only its identity is. A dead id would now be answered outright.
    unidentifiable = subprocess.Popen(  # pylint: disable=consider-using-with
        [sys.executable, "-c", "import time; time.sleep(60)"])
    unknown_lock_path.write_text(f"{unidentifiable.pid}\n", encoding="utf-8")
    real_identity_check = supervisor.process_is_supervisor_for_agent
    try:
        supervisor.process_is_supervisor_for_agent = (
            lambda process_id, agent_name, **_: real_identity_check(
                process_id, agent_name, read_command_line=lambda _p: (None, False)))
        with contextlib.redirect_stderr(io.StringIO()):
            alive, explanation = supervisor.supervisor_liveness(unknown_state_path)
        check("a supervisor that cannot be ruled out reads as watching",
              alive and "cannot tell" in explanation, explanation)

        # And the dead-id case through the same path: answered, not assumed.
        unknown_lock_path.write_text("99999999\n", encoding="utf-8")
        alive, explanation = supervisor.supervisor_liveness(unknown_state_path)
        check("a dead id reads as no supervisor even when ps cannot be run",
              not alive and "os.kill" in explanation, explanation)
    finally:
        supervisor.process_is_supervisor_for_agent = real_identity_check
        unidentifiable.kill()
        unidentifiable.wait()
    unknown_state_path.unlink(missing_ok=True)
    unknown_lock_path.unlink(missing_ok=True)

    # The agent name comes from the lock's own filename, so a lock that does
    # not follow the convention still reclaims rather than wedging a seat.
    odd_lock = workspace / "no-convention.lock"
    odd_lock.write_text("99999999\n", encoding="utf-8")
    check("a lock whose name carries no agent is still reclaimable",
          supervisor.claim_supervisor_lock(odd_lock))
    odd_lock.unlink(missing_ok=True)

    lock_path.write_text("not a number\n", encoding="utf-8")
    check("an unreadable lock is reclaimed", supervisor.claim_supervisor_lock(lock_path))
    lock_path.unlink(missing_ok=True)


def run_multi_line_next_step_cases(workspace: Path, recent: str):
    """R20's reader half: a verbatim block is parsed, preferred, and survives.

    Format in nc-systems/handoff/handoff-design.md. The block is the last
    thing in the file and its lines are taken verbatim; an unterminated block
    is a damaged handoff and falls back to the collapsed line rather than
    handing over a partial instruction.
    """
    handoff = workspace / "block-handoff.md"
    handoff.write_text(
        "written-at: " + recent + "\n"
        "next-step: FIRST ACTION: run it. THEN: fix the locale case.\n"
        "restart-counter: 7\n"
        "written-in: /Users/el/agents/git-infra\n"
        "next-step-verbatim: <<END-OF-NEXT-STEP\n"
        "FIRST ACTION: run it.\n"
        "\n"
        "THEN: fix the locale case.\n"
        "restart-counter: 999\n"
        "END-OF-NEXT-STEP\n",
        encoding="utf-8")
    fields = supervisor.parse_handoff_file(handoff)

    check("the verbatim block is parsed with its line breaks intact",
          fields.get("next-step-verbatim")
          == "FIRST ACTION: run it.\n\nTHEN: fix the locale case.\nrestart-counter: 999",
          repr(fields.get("next-step-verbatim")))
    check("a field-shaped line INSIDE the block does not shadow the real field",
          fields.get("restart-counter") == "7", fields.get("restart-counter"))
    check("the collapsed next-step is still parsed alongside the block",
          fields.get("next-step", "").startswith("FIRST ACTION: run it. THEN:"),
          fields.get("next-step"))
    check("a terminated block sets no unterminated flag",
          "next-step-verbatim-unterminated" not in fields, str(sorted(fields)))

    prompt = supervisor.build_ignition_prompt(Path("/tmp/d.md"), fields)
    check("the initial agent instructions carry the block's line breaks",
          "FIRST ACTION: run it.\n\nTHEN: fix the locale case." in prompt, repr(prompt))
    check("the initial agent instructions prefer the verbatim block over the collapsed line",
          "run it. THEN: fix" not in prompt, repr(prompt))

    # An unterminated block is damaged: the collapsed line is always present,
    # so the fallback is a correct instruction rather than a partial one.
    truncated = workspace / "truncated-handoff.md"
    truncated.write_text(
        "written-at: " + recent + "\n"
        "next-step: the collapsed instruction survives\n"
        "next-step-verbatim: <<END-OF-NEXT-STEP\n"
        "a first line that never ends\n",
        encoding="utf-8")
    truncated_fields = supervisor.parse_handoff_file(truncated)
    check("an unterminated block yields no verbatim value at all",
          "next-step-verbatim" not in truncated_fields, str(sorted(truncated_fields)))
    check("an unterminated block is recorded as unterminated",
          truncated_fields.get("next-step-verbatim-unterminated") == "yes",
          str(truncated_fields))
    truncated_prompt = supervisor.build_ignition_prompt(Path("/tmp/d.md"), truncated_fields)
    check("an unterminated block falls back to the collapsed next-step",
          "the collapsed instruction survives" in truncated_prompt, repr(truncated_prompt))
    # Bounded at BOTH ends. `"unterminated" in prompt` was the whole guard
    # until 2026-09-21, so a sentence appended to the note was invisible: the
    # note is composed inline onto the preamble and nothing pinned what
    # followed it. This fixture has a next step and no sync report or roster,
    # so what follows the note is fully determined.
    check("an unterminated block tells the successor what happened, and nothing is appended to it",
          truncated_prompt.split(
              " NOTE: this handoff's verbatim next-step block was unterminated, so what "
              "follows is the collapsed one-line form and may have lost structure.", 1
          )[1:] == ["\n\nThen take the next step:\nthe collapsed instruction survives"],
          repr(truncated_prompt))
    # The note itself, word for word, held as the module constant it now lives
    # in, so the wording keeps a guard no change of fixture can take away.
    check("the unterminated-block note is word for word what the prompt carries",
          supervisor.UNTERMINATED_NEXT_STEP_BLOCK_NOTE == (
              " NOTE: this handoff's verbatim next-step block was unterminated, so what "
              "follows is the collapsed one-line form and may have lost structure."),
          repr(supervisor.UNTERMINATED_NEXT_STEP_BLOCK_NOTE))

    # A trailing double space is a markdown hard break: the one function whose
    # purpose is carrying text unaltered must not strip it (PR #108 review).
    hard_break = workspace / "hardbreak-handoff.md"
    hard_break.write_text(
        "written-at: " + recent + "\n"
        "next-step: collapsed\n"
        "next-step-verbatim: <<END-OF-NEXT-STEP\n"
        "FIRST ACTION: read the anchor.\n"
        "THEN: present item 3.  \n"
        "END-OF-NEXT-STEP\n",
        encoding="utf-8")
    hard_break_fields = supervisor.parse_handoff_file(hard_break)
    check("a trailing markdown hard break survives to the successor",
          supervisor.next_step_from(hard_break_fields)
          == "FIRST ACTION: read the anchor.\nTHEN: present item 3.  ",
          repr(supervisor.next_step_from(hard_break_fields)))

    # The terminator is matched as an EXACT line on both ends. An indented
    # lookalike — one inside a fenced code block, say — is content, and the
    # writer refuses on the same comparison, so the ends cannot disagree.
    lookalike = workspace / "lookalike-handoff.md"
    lookalike.write_text(
        "written-at: " + recent + "\n"
        "next-step: collapsed\n"
        "next-step-verbatim: <<END-OF-NEXT-STEP\n"
        "line one\n"
        "    END-OF-NEXT-STEP\n"
        "line two\n"
        "END-OF-NEXT-STEP\n",
        encoding="utf-8")
    lookalike_fields = supervisor.parse_handoff_file(lookalike)
    check("an indented terminator lookalike does not end the block",
          lookalike_fields.get("next-step-verbatim")
          == "line one\n    END-OF-NEXT-STEP\nline two",
          repr(lookalike_fields.get("next-step-verbatim")))

    # A handoff written before this format existed has no block and must be
    # read exactly as it always was.
    legacy = workspace / "legacy-handoff.md"
    legacy.write_text("written-at: " + recent + "\nnext-step: do the old thing\n", encoding="utf-8")
    legacy_prompt = supervisor.build_ignition_prompt(
        Path("/tmp/d.md"), supervisor.parse_handoff_file(legacy))
    check("a handoff with no block still ignites from next-step",
          "do the old thing" in legacy_prompt, repr(legacy_prompt))

    # End to end: what the writer wrote is what the reader hands over.
    writer_script = SYSTEM_DIRECTORY / "handoff-write-and-check-supervisor.py"
    original = ("FIRST ACTION: read the anchor.\n"
                "\n"
                "THEN: present item 3, and keep the indentation:\n"
                "    - a nested bullet\n"
                "CONTEXT: nothing else.")
    next_step_file = workspace / "round-trip-next-step.txt"
    next_step_file.write_text(original + "\n", encoding="utf-8")
    # The seat variables too: run inside a supervised seat, the writer would
    # otherwise record that seat's directory rather than this fixture's.
    environment = {key: value for key, value in os.environ.items()
                   if key not in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_PID",
                                  "NEDSCHORUS_HANDOFF_SUPERVISOR_AGENT_NAME",
                                  "NEDSCHORUS_HANDOFF_SUPERVISOR_WORKING_DIRECTORY",
                                  "NEDSCHORUS_HANDOFF_SUPERVISOR_SESSION_ID")}
    environment["HANDOFF_SKIP_PROTECTION_AUDIT"] = "1"
    subprocess.run(
        [sys.executable, str(writer_script), "--agent", "roundtrip",
         "--next-step-file", str(next_step_file), "--handoff-dir", str(workspace)],
        capture_output=True, text=True, check=False, env=environment)
    round_tripped = supervisor.parse_handoff_file(workspace / "roundtrip-handoff.md")
    # The preference rule is inlined rather than calling next_step_from, so this
    # case fails cleanly against a base that has no such function instead of
    # crashing the suite. What it is testing is text preservation end to end;
    # the function itself is covered by the ignition-prompt cases above.
    carried = round_tripped.get("next-step-verbatim") or round_tripped.get("next-step", "")
    check("writer to reader round trip preserves the next step exactly",
          carried == original, repr(carried))


def run_launch_and_retention_cases(workspace: Path, recent: str):
    # --- Initial agent instructions (the ignition prompt) -----------------
    prompt = supervisor.build_ignition_prompt(
        Path("/tmp/dialog-0002.md"),
        {"written-at": "2026-08-30T17:20:00Z", "next-step": "finish the supervisor"},
    )
    check("ignition names the dialog path", "/tmp/dialog-0002.md" in prompt, prompt)
    # The exact opening line (template text user-approved 2026-08-30; tail
    # cut in the user's second round the same day, ruled on a rendered
    # mock): the written-at stamp rides it, and the successor computes the
    # gap from `date` itself. Against the pre-revision supervisor this fails
    # — the opener there carried the "the older it is, the more you must
    # re-verify" tail after the gap.
    check("ignition opens with the written-at stamp and the wariness rule, exactly",
          prompt.startswith(
              "Read /tmp/dialog-0002.md — the dialog from the session you are "
              "continuing, written at 2026-08-30T17:20:00Z. Calculate from `date` "
              "how long ago that was, and be wary of obsolescence and drift in "
              "everything in this handoff in proportion to that gap."),
          prompt[:400])
    check("the wariness tail past the gap is cut",
          "the older it is" not in prompt and "re-verify against the live state" not in prompt,
          prompt[:500])
    check("the composition-time elapsed phrase is gone", "minutes ago" not in prompt, prompt)
    # The open-walks duty (user-ruled 2026-08-30, second round), immediately
    # after the wariness sentence. Exact text; absent from the pre-revision
    # supervisor, so this pin fails there.
    check("ignition carries the open-walks duty, exactly",
          "in proportion to that gap. This handoff should list what items or "
          "walks are open. Display them to the user, and continue them when "
          "you get a chance." in prompt,
          prompt[:600])
    # The pointer at the supervisor itself (user-ruled 2026-08-30, second
    # round), after the open-walks duty. Exact text; absent before.
    check("ignition points at the supervisor that composed it, exactly",
          nothing_is_appended_to(
              prompt,
              "continue them when you get a chance. This session was launched by "
              "nc-systems/handoff/handoff-supervisor.py, which watches this seat and composed "
              "this prompt — read it if you need to investigate the handoff "
              "mechanism.",
              # This fixture passes no sync report and no roster, and its
              # verbatim block is not unterminated, so the pointer sentence is
              # the last of the preamble and only the next step follows it.
              "\n\nThen take the next step:\nfinish the supervisor"),
          prompt[:800])
    # The sentence itself, word for word, held as the module constant it now
    # lives in. The pin above carries it into one composed prompt; this one
    # holds the constant, so the wording keeps a guard of its own that no
    # change of fixture can quietly take away.
    check("the supervisor-pointer sentence is word for word what the user ruled",
          supervisor.SUPERVISOR_POINTER_SENTENCE == (
              "This session was launched by nc-systems/handoff/handoff-supervisor.py, which "
              "watches this seat and composed this prompt — read it if you need "
              "to investigate the handoff mechanism."),
          repr(supervisor.SUPERVISOR_POINTER_SENTENCE))
    # The branch-state line (user-ruled 2026-08-30, second round): the sync's
    # own one-line result, then the static instruction. Called through
    # try/except so this case FAILS cleanly against a supervisor whose
    # builder does not take the parameter, instead of crashing the suite.
    try:
        synced_prompt = supervisor.build_ignition_prompt(
            Path("/tmp/dialog-0002.md"),
            {"written-at": "2026-08-30T17:20:00Z", "next-step": "finish the supervisor"},
            branch_sync_report="branch sync: fixture-branch is 3 commit(s) behind main",
        )
    except TypeError:
        synced_prompt = ""
    check("ignition carries the branch sync's own one-line result",
          "branch sync: fixture-branch is 3 commit(s) behind main" in synced_prompt,
          synced_prompt[:900])
    # The constant itself, word for word. The three checks below carry it into
    # the prompt but each is containment, so until 2026-09-20 an extra sentence
    # bolted onto the end of BRANCH_STATE_INSTRUCTION was invisible to all of
    # them. This is the sentence every reincarnated seat reads about its own
    # branch: the wording it replaced had a seat merge main into a branch under
    # review thirty seconds after reading it (2026-09-15), against the ruling
    # of 2026-09-14 that working branches never take merges from main, and the
    # user replaced it word for word on 2026-09-16. Drift here is unruled
    # instruction that seats act on at once. The CONFLICTING sentence is his
    # too (2026-09-21): "leave it as it is" alone dead-ends a seat whose pull
    # request conflicts, because a commit on top cannot clear a conflict.
    check("the branch-state instruction is word for word what the user ruled",
          supervisor.BRANCH_STATE_INSTRUCTION == (
              " \u2014 If this branch has never been pushed, rebase it onto origin/main "
              "before your first substantive action and rerun the tests for what you "
              "touched. If it is pushed, leave it as it is, and start new work on a "
              "branch from origin/main. If `gh pr view` reports its pull request "
              "CONFLICTING, merge origin/main into it by hand, once, and announce the "
              "new head. If this seat has "
              "open pull requests, check their state with `gh`: merge-lane reviews and "
              "merges them; a changes-requested one gets a fix round from a fresh agent "
              "\u2014 never extend a head you've already announced."),
          repr(supervisor.BRANCH_STATE_INSTRUCTION))
    # This fixture passes no roster and its verbatim block is not
    # unterminated, so the branch-state segment ends the preamble and only the
    # next step follows it. Pinned as a tail rather than by containment: the
    # instruction is a constant, but the segment is COMPOSED at the call site
    # (`lines.append(branch_sync_report + BRANCH_STATE_INSTRUCTION)`), and text
    # appended there lands outside the constant's equality pin -- measured
    # 2026-09-21, " If unclear, rebase onto origin/main anyway." appended at
    # that call site left both suites fully green.
    expected_rest_after_the_branch_state_line = (
        "\n\nThen take the next step:\nfinish the supervisor")
    check("the branch-state instruction follows the sync result, exactly, and nothing is appended at the call site",
          nothing_is_appended_to(
              synced_prompt,
              "branch sync: fixture-branch is 3 commit(s) behind main — If this "
              "branch has never been pushed, rebase it onto origin/main before your "
              "first substantive action and rerun the tests for what you touched. "
              "If it is pushed, leave it as it is, and start new work on a branch "
              "from origin/main. If `gh pr view` reports its pull request "
              "CONFLICTING, merge origin/main into it by hand, once, and announce "
              "the new head. If this seat has "
              "open pull requests, check their state with `gh`: merge-lane reviews "
              "and merges them; a changes-requested one gets a fix round from a "
              "fresh agent — never extend a head you've already announced.",
              expected_rest_after_the_branch_state_line),
          "rest after the pinned line: "
          + repr(synced_prompt.split("already announced.", 1)[-1])
          + "; expected: " + repr(expected_rest_after_the_branch_state_line))
    # The supervisor's other ignition shape composes the same instruction at a
    # second call site (`BootRecoveryIgnitionPlan.compose`), and nothing pinned
    # what that one produced: measured 2026-09-21, the same appended sentence
    # there left handoff-supervisor-test at 234 PASS / 0 FAIL and
    # recover-crashed-seats-test at 345 passed / 0 failed. The whole prompt is
    # pinned, so an append anywhere in it -- inside the constant or after it --
    # fails here.
    boot_recovery_prompt = supervisor.BootRecoveryIgnitionPlan(
        "finish the supervisor").compose(
            "branch sync: fixture-branch is 3 commit(s) behind main")
    check("the boot-recovery prompt is exactly its next step, the recovery note, and the branch-state line",
          boot_recovery_prompt == (
              "finish the supervisor\n\n(Recovered at supervisor boot: the previous "
              "session's dialog extract is unavailable; this next-step and the "
              "repository are your whole context.) branch sync: fixture-branch is 3 "
              "commit(s) behind main — If this branch has never been pushed, rebase "
              "it onto origin/main before your first substantive action and rerun the "
              "tests for what you touched. If it is pushed, leave it as it is, and "
              "start new work on a branch from origin/main. If `gh pr view` reports "
              "its pull request CONFLICTING, merge origin/main into it by hand, "
              "once, and announce the new head. If this seat has open "
              "pull requests, check their state with `gh`: merge-lane reviews and "
              "merges them; a changes-requested one gets a fix round from a fresh "
              "agent — never extend a head you've already announced."),
          repr(boot_recovery_prompt))
    # The branch-state half of that instruction, pinned as its own exact line
    # (user-ruled 2026-09-16, "y", item 1 of nedschorus#418, verbatim). It
    # replaced the 2026-08-31 catch-up sentence, which a seat read as "merge
    # main" on 2026-09-15; nedschorus#324 rules merges from main out — rebase
    # a never-pushed branch, leave a pushed one alone.
    check("the branch-state instruction rebases a never-pushed branch and leaves a pushed one, exactly",
          " — If this branch has never been pushed, rebase it onto origin/main "
          "before your first substantive action and rerun the tests for what "
          "you touched. If it is pushed, leave it as it is, and start new work "
          "on a branch from origin/main." in synced_prompt,
          synced_prompt[:1100])
    check("the superseded 2026-08-30 and 2026-08-31 catch-up wordings are gone from the initial agent instructions",
          "when safe" not in synced_prompt
          and "if you can't resolve them" not in synced_prompt
          and "catch up with origin/main" not in synced_prompt
          and "resolve conflicts you can verify" not in synced_prompt
          and "git merge" not in synced_prompt,
          synced_prompt[:1100])
    check("the branch-state line precedes the next step",
          "" if not synced_prompt else
          synced_prompt.index("branch sync:") < synced_prompt.index("Then take the next step:"),
          synced_prompt[:1100])
    # A caller without a sync report gets no branch-state segment at all —
    # never invented placeholder wording, which the user has not seen.
    check("without a sync report the prompt says nothing about branch state",
          "branch sync" not in prompt and "origin/main" not in prompt, prompt)
    # The task-count line was CUT (user-ruled 2026-08-30: the task list is a
    # standing tool; the count line is junk). Pinned behaviorally — the OLD
    # supervisor put "Confirm N task(s) are visible to you" into every
    # initial agent instructions unconditionally — and structurally below, where neither
    # the builder nor the plan accepts a count any more.
    check("the task-count line is cut from the initial agent instructions",
          "task(s) are visible" not in prompt and "Confirm" not in prompt, prompt)
    check("build_ignition_prompt no longer takes a task count",
          "task_count" not in inspect.signature(supervisor.build_ignition_prompt).parameters,
          str(inspect.signature(supervisor.build_ignition_prompt)))
    check("DialogIgnitionPlan no longer holds a task count",
          "task_count" not in {field.name for field in
                               dataclasses.fields(supervisor.DialogIgnitionPlan)},
          str([field.name for field in dataclasses.fields(supervisor.DialogIgnitionPlan)]))
    check("ignition carries the next step", "finish the supervisor" in prompt, prompt)
    prompt_without_step = supervisor.build_ignition_prompt(Path("/tmp/d.md"), {"written-at": recent})
    # Bounded at the END, which containment alone never was: this sentence
    # closes the prompt, so anything appended to it would have been invisible
    # to `"continue from where that dialog ends" in prompt`.
    check("ignition survives a missing next-step, and that sentence ends the prompt",
          prompt_without_step.endswith(" Then continue from where that dialog ends."),
          repr(prompt_without_step))
    check("the no-next-step tail is word for word what the prompt carries",
          supervisor.NO_NEXT_STEP_TAIL_SENTENCE == " Then continue from where that dialog ends.",
          repr(supervisor.NO_NEXT_STEP_TAIL_SENTENCE))
    # The queue-status line was CUT from the prompt (user-ruled 2026-08-29,
    # expiring his 2026-08-12 #32 ruling: "Also useless is the reminder there
    # are files in the queues. Thats what queues are for."). The cut is
    # pinned structurally — nothing can thread a queue status into the
    # prompt, because neither the builder nor the plan accepts one — and
    # behaviorally in run_recycle_prompt_composition_cases below, where the
    # OLD supervisor put the line into every reincarnation prompt unconditionally.
    check("build_ignition_prompt no longer takes a queue status",
          "queue_status" not in inspect.signature(supervisor.build_ignition_prompt).parameters,
          str(inspect.signature(supervisor.build_ignition_prompt)))
    check("DialogIgnitionPlan no longer holds a queue status",
          "queue_status" not in {field.name for field in
                                 dataclasses.fields(supervisor.DialogIgnitionPlan)},
          str([field.name for field in dataclasses.fields(supervisor.DialogIgnitionPlan)]))

    # --- The launch clock is CUT ------------------------------------------
    # The user cut his own nedschorus#175 sentence ("The clock read ... take
    # every time stamp from `date`, never from estimate") on the rendered
    # mock, 2026-08-30: the `date` discipline now rides only the opener's
    # "Calculate from `date`". Pinned behaviorally — the pre-revision
    # supervisor put the sentence into every set of initial agent instructions — and
    # structurally: neither the builder nor the plan threads a launch time
    # any more, and the sentence's helper is gone from the module.
    check("the launch-clock sentence is cut from the initial agent instructions",
          "The clock read" not in prompt and "never from estimate" not in prompt,
          prompt)
    check("build_ignition_prompt no longer takes a launch time",
          "launch_time" not in inspect.signature(supervisor.build_ignition_prompt).parameters,
          str(inspect.signature(supervisor.build_ignition_prompt)))
    check("the launch-clock helper is gone from the supervisor",
          not hasattr(supervisor, "launch_clock_sentence"),
          str(getattr(supervisor, "launch_clock_sentence", None)))

    # --- Retention --------------------------------------------------------
    for generation in range(1, 6):
        (workspace / f"agent-dialog-{generation:04d}.md").write_text("x", encoding="utf-8")
    supervisor.prune_old_generations(workspace, "agent-dialog")
    remaining = sorted(item.name for item in workspace.glob("agent-dialog-*.md"))
    check(
        "retention keeps the newest two generations",
        remaining == ["agent-dialog-0004.md", "agent-dialog-0005.md"],
        str(remaining),
    )

    # A long dialog's -complete.md companion belongs to its generation and does
    # not take a generation's place. Before 2026-09-16 the pruner counted files,
    # so generation 5's companion evicted generation 4's tail on arrival.
    retention_with_companions = workspace / "retention-with-companions"
    retention_with_companions.mkdir()
    for name in ("agent-dialog-0003.md", "agent-dialog-0003-complete.md",
                 "agent-dialog-0004.md", "agent-dialog-0004-complete.md",
                 "agent-dialog-0005.md", "agent-dialog-0005-complete.md"):
        (retention_with_companions / name).write_text("x", encoding="utf-8")
    supervisor.prune_old_generations(retention_with_companions, "agent-dialog")
    remaining = sorted(item.name for item in retention_with_companions.glob("*.md"))
    check(
        "retention keeps both files of each of the newest two generations",
        remaining == ["agent-dialog-0004-complete.md", "agent-dialog-0004.md",
                      "agent-dialog-0005-complete.md", "agent-dialog-0005.md"],
        str(remaining),
    )

    # Only a long dialog gets a companion, so neighbouring generations can
    # differ: the newest short, the one before long.
    retention_mixed = workspace / "retention-mixed-companions"
    retention_mixed.mkdir()
    for name in ("agent-dialog-0003.md", "agent-dialog-0004.md",
                 "agent-dialog-0004-complete.md", "agent-dialog-0005.md"):
        (retention_mixed / name).write_text("x", encoding="utf-8")
    supervisor.prune_old_generations(retention_mixed, "agent-dialog")
    remaining = sorted(item.name for item in retention_mixed.glob("*.md"))
    check(
        "retention keeps a long previous generation whole beside a short newest one",
        remaining == ["agent-dialog-0004-complete.md", "agent-dialog-0004.md",
                      "agent-dialog-0005.md"],
        str(remaining),
    )

    # The handoff family is pruned in the same directory: its numbered archives
    # go, and the live <seat>-handoff.md the next reincarnation polls stays.
    retention_handoffs = workspace / "retention-handoff-archives"
    retention_handoffs.mkdir()
    for name in ("agent-handoff.md", "agent-handoff-0001.md",
                 "agent-handoff-0002.md", "agent-handoff-0003.md"):
        (retention_handoffs / name).write_text("x", encoding="utf-8")
    supervisor.prune_old_generations(retention_handoffs, "agent-handoff")
    remaining = sorted(item.name for item in retention_handoffs.glob("*.md"))
    check(
        "handoff retention keeps two archives and never the live handoff file's place",
        remaining == ["agent-handoff-0002.md", "agent-handoff-0003.md", "agent-handoff.md"],
        str(remaining),
    )

    # --- Queue status -----------------------------------------------------
    project = workspace / "project"
    (project / "nc-queue").mkdir(parents=True)
    (project / "nc-queue" / "2026-07-28-older-note.md").write_text("x", encoding="utf-8")
    (project / "nc-queue" / "2026-08-01-newer-note.md").write_text("x", encoding="utf-8")
    (project / "nc-queue" / "README.md").write_text("x", encoding="utf-8")
    (project / "docs" / "nedschorus-wiki" / "queue").mkdir(parents=True)
    line = supervisor.queue_status_line(project)
    check("queue status counts a loaded queue", "nc-queue: 2" in line, line)
    check("queue status names the oldest item", "2026-07-28-older-note.md" in line, line)
    check("queue status reports an empty queue", "docs/nedschorus-wiki/queue: empty" in line, line)

    # --- Task pre-seed (file mechanics, no session) -----------------------
    # CLAUDE_CODE_TASK_LIST_ID is removed for the un-pinned cases and set
    # explicitly for the pinned ones, never inherited: after nedschorus#141
    # every wrapper-launched seat has it set, so a suite that read the
    # ambient value would take a different path depending on who ran it.
    original_tasks_root = supervisor.TASKS_ROOT
    original_pin = os.environ.get("CLAUDE_CODE_TASK_LIST_ID")

    def task_record_count(list_id: str) -> int:
        directory = supervisor.TASKS_ROOT / list_id
        return len(list(directory.glob("*.json"))) if directory.is_dir() else 0

    try:
        os.environ.pop("CLAUDE_CODE_TASK_LIST_ID", None)
        supervisor.TASKS_ROOT = workspace / "tasks"
        retiring, successor = "old-session", "new-session"
        (supervisor.TASKS_ROOT / retiring).mkdir(parents=True)
        for task_id in (1, 2):
            (supervisor.TASKS_ROOT / retiring / f"{task_id}.json").write_text(
                json.dumps({"id": task_id, "status": "pending"}), encoding="utf-8"
            )
        check("unpinned: no pinned list id is reported",
              supervisor.pinned_task_list_id() == "",
              supervisor.pinned_task_list_id())
        copied = supervisor.preseed_tasks(retiring, successor)
        check("pre-seed copies every task record", copied == 2, f"copied {copied}")
        check("pre-seed puts the records where the successor will read them",
              task_record_count(successor) == 2, task_record_count(successor))
        check("pre-seed leaves the source intact", task_record_count(retiring) == 2)
        check("pre-seed of a taskless session copies nothing", supervisor.preseed_tasks("never-existed", "x") == 0)

        # --- Reincarnation under a PINNED list (nedschorus#141) -----------
        # The seat's generations share one launcher-pinned store, so a
        # reincarnation copies nothing and the seat's records survive untouched.
        # (The ignition count-check this block once guarded — "Confirm 0
        # task(s) are visible to you" over a list holding N — was cut with
        # the task-count line, user-ruled 2026-08-30.) Shaped like a real
        # reincarnation: tasks already in the seat's store, a fresh successor id,
        # nothing copied.
        pinned_id = "handoff-supervisor-test-pin-tasks"
        os.environ["CLAUDE_CODE_TASK_LIST_ID"] = pinned_id
        pinned_store = supervisor.TASKS_ROOT / pinned_id
        pinned_store.mkdir(parents=True)
        for task_id in (1, 2, 3):
            (pinned_store / f"{task_id}.json").write_text(
                json.dumps({"id": str(task_id), "subject": f"pinned task {task_id}",
                            "status": "pending", "blocks": [], "blockedBy": []}),
                encoding="utf-8")
        pinned_successor = "successor-session-that-names-no-store"
        check("pinned: the list id is read from the environment",
              supervisor.pinned_task_list_id() == pinned_id,
              supervisor.pinned_task_list_id())
        check("pinned: nothing is pre-seeded — one store, both generations",
              supervisor.preseed_tasks(retiring, pinned_successor) == 0)
        check("pinned: no directory is created for the successor's session id",
              not (supervisor.TASKS_ROOT / pinned_successor).exists(),
              str(supervisor.TASKS_ROOT / pinned_successor))
        check("pinned: the seat's own records are left untouched",
              sorted(p.name for p in pinned_store.glob("*.json"))
              == ["1.json", "2.json", "3.json"],
              sorted(p.name for p in pinned_store.glob("*.json")))
        # The un-pinned store this block started with must not have been
        # disturbed by any of the above.
        os.environ.pop("CLAUDE_CODE_TASK_LIST_ID", None)
        check("pinned cases left the un-pinned fixture alone",
              task_record_count(retiring) == 2,
              task_record_count(retiring))
    finally:
        supervisor.TASKS_ROOT = original_tasks_root
        if original_pin is None:
            os.environ.pop("CLAUDE_CODE_TASK_LIST_ID", None)
        else:
            os.environ["CLAUDE_CODE_TASK_LIST_ID"] = original_pin


def run_preseed_canaries() -> None:
    """Live canaries: does a fresh session read the seat's pinned task list?

    Canary 1: a fresh session launched with the seat's pinned list id reads
    task records that were on disk before it booted — the successor half of
    a reincarnation, which is how the fleet carries tasks since nedschorus#141.
    Canary 2: a task that session creates allocates above the existing ids,
    leaving the earlier records untouched.

    Two variables, because either alone proves nothing here.
    CLAUDE_CODE_ENABLE_TODO_TOOLS=1 is what makes the task tools exist at
    all from Claude Code 2.1.233 onward; without it the canary would report
    a failure that is only the tools being absent.
    CLAUDE_CODE_TASK_LIST_ID is the binding under test.

    The store is a throwaway id, created and removed by this function. No
    seat's real list is read or written.
    """
    session_id = str(uuid.uuid4())
    pinned_list_id = f"handoff-supervisor-canary-{uuid.uuid4().hex[:8]}-tasks"
    task_directory = supervisor.TASKS_ROOT / pinned_list_id
    task_directory.mkdir(parents=True, exist_ok=True)
    # The record shape is the harness's own, read from live task stores: the
    # id is a STRING, and blocks/blockedBy are present. A record with an
    # integer id is silently dropped by TaskList while still counting toward
    # the next allocated id — measured 2026-08-06, and the reason this
    # fixture is written out longhand rather than approximated.
    for task_id, subject in (("1", "carried task alpha"), ("2", "carried task beta")):
        (task_directory / f"{task_id}.json").write_text(
            json.dumps(
                {
                    "id": task_id,
                    "subject": subject,
                    "description": f"seeded by the canary: {subject}",
                    "status": "pending",
                    "blocks": [],
                    "blockedBy": [],
                }
            ),
            encoding="utf-8",
        )

    try:
        result = subprocess.run(
            [
                "claude", "-p", "--session-id", session_id,
                "List your current tasks with the TaskList tool, then create one new task "
                "titled 'canary successor task'. Report the subjects you saw and the new task's id.",
            ],
            capture_output=True, text=True, timeout=300, check=False,
            env={**os.environ,
                 "CLAUDE_CODE_TASK_LIST_ID": pinned_list_id,
                 "CLAUDE_CODE_ENABLE_TODO_TOOLS": "1"},
        )
        transcript = result.stdout

        check("canary 1: successor reads the seat's pinned tasks",
              "alpha" in transcript and "beta" in transcript, transcript[:400])

        seeded_intact = all((task_directory / f"{n}.json").is_file() for n in (1, 2))
        new_files = sorted(int(p.stem) for p in task_directory.glob("*.json") if p.stem.isdigit())
        check("canary 2: seeded records are untouched", seeded_intact, str(new_files))
        check("canary 2: new task ids allocate above the seeded maximum", max(new_files) >= 3, str(new_files))
    finally:
        # The throwaway store goes even when a check above failed, so a red
        # run does not strand a directory beside the fleet's real lists.
        shutil.rmtree(task_directory, ignore_errors=True)
        print(f"(canary store {task_directory} removed: "
              f"{'gone' if not task_directory.exists() else 'STILL PRESENT'})")


def git_in(arguments, cwd):
    completed = subprocess.run(["git", *arguments], cwd=str(cwd),
                               capture_output=True, text=True, check=False)
    if completed.returncode != 0 and arguments[0] not in ("merge",):
        raise AssertionError(f"git {' '.join(arguments)} failed: {completed.stderr}")
    return completed


def run_branch_sync_cases(workspace: Path):
    """Every branch of sync_working_branch_with_main, against real repositories.

    The function only ever fast-forwards, so the cases that matter most are the
    ones where it must NOT act: a dirty tree, a diverged branch, a directory
    that is not a checkout at all.
    """
    root = workspace / "branch-sync"
    root.mkdir()

    check("a directory that is not a checkout syncs to nothing",
          "nothing to sync" in supervisor.sync_working_branch_with_main(root))

    remote = root / "remote.git"
    git_in(["init", "--quiet", "--bare", "--initial-branch=main", str(remote)], root)
    seed = root / "seed"
    git_in(["clone", "--quiet", str(remote), str(seed)], root)
    git_in(["config", "user.name", "fixture"], seed)
    git_in(["config", "user.email", "fixture@nedschorus.invalid"], seed)
    (seed / "README.md").write_text("seed\n", encoding="utf-8")
    git_in(["add", "-A"], seed)
    git_in(["commit", "--quiet", "-m", "seed"], seed)
    git_in(["push", "--quiet", "origin", "main"], seed)

    # The agent's home: a clone on its own branch, as every agent home is.
    home = root / "agent-home"
    git_in(["clone", "--quiet", str(remote), str(home)], root)
    git_in(["config", "user.name", "agent"], home)
    git_in(["config", "user.email", "agent@nedschorus.invalid"], home)
    git_in(["checkout", "--quiet", "-b", "agent-branch"], home)

    check("a branch level with main reports current",
          "current with main" in supervisor.sync_working_branch_with_main(home))

    # Main moves ahead; the agent's clean branch must fast-forward onto it.
    (seed / "README.md").write_text("seed\nfrom main\n", encoding="utf-8")
    git_in(["add", "-A"], seed)
    git_in(["commit", "--quiet", "-m", "main moves ahead"], seed)
    git_in(["push", "--quiet", "origin", "main"], seed)

    report = supervisor.sync_working_branch_with_main(home)
    check("a clean branch behind main fast-forwards", "fast-forwarded to main" in report, report)
    check("the fast-forward really moved the files",
          (home / "README.md").read_text(encoding="utf-8") == "seed\nfrom main\n")

    # Uncommitted work is never disturbed, however far behind the branch is.
    (seed / "README.md").write_text("seed\nfrom main\nfurther\n", encoding="utf-8")
    git_in(["add", "-A"], seed)
    git_in(["commit", "--quiet", "-m", "main moves again"], seed)
    git_in(["push", "--quiet", "origin", "main"], seed)
    (home / "work-in-progress.txt").write_text("half a thought\n", encoding="utf-8")

    report = supervisor.sync_working_branch_with_main(home)
    check("a dirty tree is left exactly as it is", "left as is" in report, report)
    check("the uncommitted file survives the sync", (home / "work-in-progress.txt").is_file())
    check("a dirty tree is not fast-forwarded",
          (home / "README.md").read_text(encoding="utf-8") == "seed\nfrom main\n")

    # A branch carrying its own commits is reported, never merged: a conflicted
    # merge waiting for an agent that has not woken up is worse than being behind.
    (home / "work-in-progress.txt").unlink()
    (home / "agent-note.txt").write_text("finished thought\n", encoding="utf-8")
    git_in(["add", "-A"], home)
    git_in(["commit", "--quiet", "-m", "the agent's own work"], home)

    report = supervisor.sync_working_branch_with_main(home)
    check("a diverged branch is reported, not merged",
          report.startswith("branch sync: agent-branch is 1 ahead of main"), report)
    check("the diverged report counts both directions",
          "1 ahead of main" in report and "1 behind" in report, report)
    # Nor does the report tell the agent to merge (user-ruled 2026-09-16, "y",
    # item 1 of nedschorus#418): on 2026-09-15 a seat handed "merge when ready
    # (git merge origin/main)" merged main into a branch under review, which
    # nedschorus#324 rules out. Checked on the prompt the report is composed
    # into, which is what the seat actually reads.
    diverged_prompt = supervisor.build_ignition_prompt(
        Path("/tmp/dialog-0002.md"),
        {"written-at": "2026-09-16T09:00:00Z", "next-step": "finish the review fix"},
        branch_sync_report=report,
    )
    check("the diverged-branch initial agent instructions never say to merge main",
          "git merge" not in diverged_prompt and "merge when ready" not in diverged_prompt,
          diverged_prompt)
    check("the diverged-branch initial agent instructions carry the rebase-or-leave-it sentence",
          "branch sync: agent-branch is 1 ahead of main and 1 behind — If this "
          "branch has never been pushed, rebase it onto origin/main before your "
          "first substantive action and rerun the tests for what you touched. "
          "If it is pushed, leave it as it is, and start new work on a branch "
          "from origin/main." in diverged_prompt,
          diverged_prompt)
    check("a diverged branch keeps its own commit",
          git_in(["log", "-1", "--format=%s"], home).stdout.strip() == "the agent's own work")

    # Ahead-only: everything main has, plus local work. Nothing to pull.
    git_in(["merge", "--no-edit", "--quiet", "origin/main"], home)
    report = supervisor.sync_working_branch_with_main(home)
    check("a branch ahead of main with all of main reports nothing to pull",
          "nothing to pull" in report, report)


def run_no_seat_recycle_refusal_case(workspace: Path):
    """A handoff arriving at a supervisor with no terminal must not reincarnate:
    the successor would inherit this stdio and die at its first need for
    input (observed 2026-08-14 — an adopted console session was killed and
    its successor reported into a log file). The session stays up and the
    handoff stays unconsumed for a seated supervisor."""
    handoff_directory = workspace / "noseat"
    handoff_directory.mkdir(parents=True, exist_ok=True)
    stub_agent = handoff_directory / "stub-agent"
    stub_agent.write_text(
        "#!/bin/sh\n"
        "exec >/dev/null 2>&1\n"  # release the supervisor's pipes, or the test waits out the sleep
        "printf 'written-at: 2026-08-14T00:00:00Z\\nnext-step: recycle me\\nrestart-counter: 9\\n' "
        f"> '{handoff_directory}/noseat-handoff.md'\n"
        "sleep 30\n",
        encoding="utf-8",
    )
    stub_agent.chmod(0o755)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", "noseat", "--cd", str(workspace),
         "--handoff-dir", str(handoff_directory), "--agent-command", str(stub_agent)],
        capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL, timeout=60,
    )
    check("a handoff without a seat stops the supervisor cleanly",
          result.returncode == 0, result.stderr[-300:])
    check("the refusal names the missing terminal, before any kill",
          "no terminal to seat a successor" in result.stdout, result.stdout[-400:])
    state = supervisor.read_supervisor_state(handoff_directory / "noseat-supervisor-state.json")
    check("the handoff stays unconsumed for a seated supervisor",
          state.get("consumed_counter") is None, str(state))
    # The session is left alive at this stop, so nothing exited: no record.
    check("a stop that leaves the session up records no agent exit",
          supervisor.agent_exit_record_from_supervisor_state(state) is None
          and supervisor.AGENT_EXIT_CODE_STATE_KEY not in state, str(state))


class StubLaunchedSession:
    """A launched session's stand-in for the in-process cases: poll() reports
    exit_code once the session has ended, and terminate() ends it, as a real
    session's returncode is set only when its end is observed."""

    def __init__(self, exit_code, ended=True):
        self.returncode = None
        self.exit_code = exit_code
        self.ended = ended

    def poll(self):
        if self.ended:
            self.returncode = self.exit_code
        return self.returncode

    def terminate(self):
        self.ended = True

    def kill(self):
        self.ended = True

    def wait(self, timeout=None):
        return self.poll()


@contextlib.contextmanager
def supervisor_names_replaced(**replacements):
    """Replace module-level names the supervisor looks up when it runs — its
    functions, and `input`, which it otherwise finds in builtins — and a
    terminal on stdin when `stdin_isatty` is given; everything is put back."""
    stdin_isatty = replacements.pop("stdin_isatty", None)
    missing = object()
    saved = {name: supervisor.__dict__.get(name, missing) for name in replacements}
    saved_stdin = sys.stdin
    for name, value in replacements.items():
        setattr(supervisor, name, value)
    if stdin_isatty is not None:
        sys.stdin = SimpleNamespace(isatty=lambda: stdin_isatty)
    try:
        yield
    finally:
        sys.stdin = saved_stdin
        for name, value in saved.items():
            if value is missing:
                delattr(supervisor, name)
            else:
                setattr(supervisor, name, value)


def run_agent_exit_record_cases(workspace: Path):
    """nedschorus#242 change 2 (ruled 2026-09-02, the #120 overview § Ruled
    2026-09-02: record how the agent exited). Every stop after a session's end
    that launches no successor records the agent's exit code and the time in
    the state file; recover-crashed-seats.py offers such a seat instead of
    resuming it. The record is cleared before every launch or adoption, so a
    seat that once exited cleanly and later crashed does not read as clean."""
    # --- End to end: the real exit code of a real session -----------------
    name = "exitrecord"
    handoff_directory = workspace / name
    handoff_directory.mkdir(parents=True, exist_ok=True)
    state_path = handoff_directory / f"{name}-supervisor-state.json"
    stub_agent = handoff_directory / "stub-agent"
    for case_name, stub_body, expected_code in (
            ("a clean exit", "exit 0\n", 0),
            ("a nonzero exit", "exit 3\n", 3),
            # Negative, as Popen reports a signal: recorded as-is.
            ("an exit by SIGTERM", "kill -TERM $$\n", -15)):
        stub_agent.write_text("#!/bin/sh\n" + stub_body, encoding="utf-8")
        stub_agent.chmod(0o755)
        before = datetime.now(timezone.utc).replace(microsecond=0)
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--agent", name, "--cd", str(workspace),
             "--handoff-dir", str(handoff_directory), "--agent-command", str(stub_agent)],
            capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL, timeout=60,
        )
        state = supervisor.read_supervisor_state(state_path)
        record = supervisor.agent_exit_record_from_supervisor_state(state)
        try:
            recorded_at = datetime.fromisoformat(record[1]) if record else None
        except ValueError:
            recorded_at = None
        check(f"EXIT RECORD: {case_name} without a handoff records exit code {expected_code}",
              result.returncode == 0
              and "session ended without a handoff; supervisor stopping" in result.stdout
              and record is not None and record[0] == expected_code
              and state.get(supervisor.AGENT_EXIT_CODE_STATE_KEY) == expected_code,
              f"{state} {result.stdout[-300:]} {result.stderr[-300:]}")
        check(f"EXIT RECORD: {case_name} records when, in UTC, at the stop",
              recorded_at is not None and recorded_at.tzinfo is not None
              and before <= recorded_at <= datetime.now(timezone.utc),
              str(state))

    # The in-cycle dont-restart stop, with no terminal to ask on: the session
    # wrote its handoff and stayed up, so the supervisor terminated it before
    # standing the seat down — and records that termination's code as-is.
    name = "exitrecorddontrestart"
    handoff_directory = workspace / name
    handoff_directory.mkdir(parents=True, exist_ok=True)
    stub_agent = handoff_directory / "stub-agent"
    stub_agent.write_text(
        "#!/bin/sh\n"
        "exec >/dev/null 2>&1\n"
        "printf 'written-at: 2026-09-17T00:00:00Z\\nnext-step: stand down\\n"
        "restart-counter: 1\\ndont-restart: the user closes this seat\\n' "
        f"> '{handoff_directory}/{name}-handoff.md'\n"
        "exec sleep 30\n",
        encoding="utf-8",
    )
    stub_agent.chmod(0o755)
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", name, "--cd", str(workspace),
         "--handoff-dir", str(handoff_directory), "--agent-command", str(stub_agent)],
        capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL, timeout=90,
    )
    state = supervisor.read_supervisor_state(handoff_directory / f"{name}-supervisor-state.json")
    check("EXIT RECORD: the in-cycle dont-restart stop records the terminated session's code",
          result.returncode == 0 and "no terminal to ask on; stopping" in result.stdout
          and state.get("consumed_counter") == 1
          and supervisor.agent_exit_record_from_supervisor_state(state) is not None
          and state.get(supervisor.AGENT_EXIT_CODE_STATE_KEY) == -15,
          f"{state} {result.stdout[-300:]} {result.stderr[-300:]}")

    # --- In process: the paths a subprocess cannot reach -------------------
    def settings_for(case: str, adopted_session=None):
        directory = workspace / f"exitrecord-in-process-{case}"
        directory.mkdir(parents=True, exist_ok=True)
        return supervisor.SupervisorSettings(
            agent=f"exitrecord{case}", working_directory=workspace,
            handoff_directory=directory, agent_command="unused-stub-agent",
            first_prompt="", adopted_session=adopted_session)

    def launch_recording(sessions, launched_state_snapshots, settings):
        def launch(agent_command, session_id, working_directory, prompt, **_):
            launched_state_snapshots.append(
                json.loads(settings.state_path.read_text(encoding="utf-8")))
            return sessions.pop(0)
        return launch

    no_branch_sync = lambda working_directory: "branch sync: not a git checkout, nothing to sync"

    # Cleared at launch: a record left by an earlier stop is gone from the state
    # file before the next session starts, and the stop after that session
    # writes a record of its own.
    settings = settings_for("cleared")
    supervisor.write_supervisor_state(settings.state_path, {
        "consumed_counter": None, "session_id": "earlier-session", "generation": 2,
        supervisor.AGENT_EXIT_CODE_STATE_KEY: 0,
        supervisor.AGENT_EXIT_RECORDED_AT_STATE_KEY: "2026-01-01T00:00:00+00:00"})
    snapshots = []
    with supervisor_names_replaced(
            launch_agent_session=launch_recording([StubLaunchedSession(9)], snapshots, settings),
            sync_working_branch_with_main=no_branch_sync), \
            contextlib.redirect_stdout(io.StringIO()):
        supervisor.supervise_sessions(settings)
    state = supervisor.read_supervisor_state(settings.state_path)
    check("EXIT RECORD: an earlier record is cleared from the state file before the launch",
          len(snapshots) == 1
          and supervisor.AGENT_EXIT_CODE_STATE_KEY not in snapshots[0]
          and supervisor.AGENT_EXIT_RECORDED_AT_STATE_KEY not in snapshots[0],
          str(snapshots))
    check("EXIT RECORD: and the launched session's own end is recorded afresh",
          supervisor.agent_exit_record_from_supervisor_state(state) is not None
          and state[supervisor.AGENT_EXIT_CODE_STATE_KEY] == 9
          and state[supervisor.AGENT_EXIT_RECORDED_AT_STATE_KEY] != "2026-01-01T00:00:00+00:00",
          str(state))

    # Cleared at adoption too, and an adopted session's code is unknown — its
    # poll() says 0 for any process that is merely gone — so it is recorded as
    # null rather than skipped.
    settings = settings_for("adopted", supervisor.AdoptedSession("adopted-session", 99999999))
    supervisor.write_supervisor_state(settings.state_path, {
        supervisor.AGENT_EXIT_CODE_STATE_KEY: 0,
        supervisor.AGENT_EXIT_RECORDED_AT_STATE_KEY: "2026-01-01T00:00:00+00:00"})
    written_states = []
    real_write_supervisor_state = supervisor.write_supervisor_state

    def write_recording(state_path, state):
        written_states.append(dict(state))
        real_write_supervisor_state(state_path, state)

    with supervisor_names_replaced(write_supervisor_state=write_recording), \
            contextlib.redirect_stdout(io.StringIO()):
        supervisor.supervise_sessions(settings)
    state = supervisor.read_supervisor_state(settings.state_path)
    check("EXIT RECORD: an earlier record is cleared before an adopted session is watched",
          written_states and supervisor.AGENT_EXIT_CODE_STATE_KEY not in written_states[0],
          str(written_states))
    check("EXIT RECORD: an adopted session's end is recorded with its code unknown",
          supervisor.agent_exit_record_from_supervisor_state(state) is not None
          and state.get(supervisor.AGENT_EXIT_CODE_STATE_KEY, "absent") is None,
          str(state))

    # A handoff arrives with a terminal to ask on. The session is still running
    # when it is written, so the supervisor stops it itself (SIGTERM, -15).
    def launch_writing_a_handoff(settings, session, handoff_text):
        def launch(agent_command, session_id, working_directory, prompt, **_):
            settings.handoff_path.write_text(handoff_text, encoding="utf-8")
            return session
        return launch

    # dont-restart answered n at the terminal.
    settings = settings_for("answeredn")
    supervisor.write_supervisor_state(settings.state_path, {"consumed_counter": 1})
    with supervisor_names_replaced(
            launch_agent_session=launch_writing_a_handoff(
                settings, StubLaunchedSession(-15, ended=False),
                "restart-counter: 2\nnext-step: stand down\ndont-restart: closing\n"),
            sync_working_branch_with_main=no_branch_sync,
            input=lambda prompt: "n", stdin_isatty=True), \
            contextlib.redirect_stdout(io.StringIO()):
        supervisor.supervise_sessions(settings)
    state = supervisor.read_supervisor_state(settings.state_path)
    check("EXIT RECORD: dont-restart answered n records the stopped session's code",
          state.get("consumed_counter") == 2
          and supervisor.agent_exit_record_from_supervisor_state(state) is not None
          and state.get(supervisor.AGENT_EXIT_CODE_STATE_KEY) == -15,
          str(state))

    # The dialog extraction fails, so no successor is launched: the stopped
    # session's end is recorded, and the handoff stays unconsumed.
    settings = settings_for("extractionfailed")
    supervisor.write_supervisor_state(settings.state_path, {"consumed_counter": 1})
    with supervisor_names_replaced(
            launch_agent_session=launch_writing_a_handoff(
                settings, StubLaunchedSession(-15, ended=False),
                "restart-counter: 2\nnext-step: carry on\n"),
            sync_working_branch_with_main=no_branch_sync,
            extract_dialog=lambda session_id, working_directory, output_path: False,
            stdin_isatty=True), \
            contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        supervisor.supervise_sessions(settings)
    state = supervisor.read_supervisor_state(settings.state_path)
    check("EXIT RECORD: a failed extraction records the stopped session, handoff unconsumed",
          state.get("consumed_counter") == 1
          and supervisor.agent_exit_record_from_supervisor_state(state) is not None
          and state.get(supervisor.AGENT_EXIT_CODE_STATE_KEY) == -15,
          str(state))


def run_by_hand_resume_cases(workspace: Path):
    """nedschorus#242 change 5 (ruled 2026-09-02, the #120 overview § Ruled:
    what happens when a restart fails): a by-hand `launch-claude-mac <seat>` of
    a seat with no waiting handoff and no recorded exit resumes its last
    transcript instead of minting an empty session.

    Measured 2026-09-02 on both machines, and the shape of the 2026-08-21 tmux
    death: three supervisors fell through to their first-prompt path and minted
    near-empty successors while three intact 1-2MB transcripts sat on disk. The
    first case below is that defect written down; it fails against the code as
    it stood before this change.

    The seat's project directory is stubbed rather than derived, so these cases
    never read or write the real ~/.claude/projects.
    """
    directory = workspace / "by-hand-resume"
    directory.mkdir(parents=True, exist_ok=True)
    projects = workspace / "by-hand-resume-projects"
    projects.mkdir(parents=True, exist_ok=True)

    def write_transcript(session_id: str, first_turn: str, assistant_turns: int):
        lines = [json.dumps({"type": "user", "message": {"content": first_turn}})]
        for _ in range(assistant_turns):
            lines.append(json.dumps(
                {"type": "assistant", "message": {"model": "claude", "content": "work"}}))
        path = projects / f"{session_id}.jsonl"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def settings_for(case: str):
        case_directory = directory / case
        case_directory.mkdir(parents=True, exist_ok=True)
        return supervisor.SupervisorSettings(
            agent=f"byhand{case}", working_directory=workspace,
            handoff_directory=case_directory, agent_command="unused-stub-agent",
            first_prompt="")

    no_branch_sync = lambda working_directory: (
        "branch sync: not a git checkout, nothing to sync")

    def launch_once(settings):
        """(session_id, prompt, resume) of the one launch, which then ends."""
        launched = []

        def launch(agent_command, session_id, working_directory, prompt, **kwargs):
            launched.append((session_id, prompt, kwargs.get("resume")))
            return StubLaunchedSession(0)

        with supervisor_names_replaced(
                launch_agent_session=launch,
                project_directory_for_working_directory=lambda _: projects,
                sync_working_branch_with_main=no_branch_sync), \
                contextlib.redirect_stdout(io.StringIO()):
            supervisor.supervise_sessions(settings)
        return launched[0] if launched else (None, None, None)

    # 1. The defect: real work on disk, nothing to say the seat stopped on
    # purpose. Before this change the supervisor minted a new id and told the
    # agent no handoff exists.
    crashed = write_transcript("crashed-with-real-work", "do the thing", assistant_turns=4)
    settings = settings_for("crash")
    supervisor.write_supervisor_state(settings.state_path, {"generation": 1})
    session_id, prompt, resume = launch_once(settings)
    check("BY HAND: a seat with no handoff and no recorded exit resumes its last transcript",
          session_id == crashed.stem and resume is True,
          (session_id, resume, crashed.stem))
    check("BY HAND: and the resumed session is told the previous one ended without a handoff",
          prompt == supervisor.RESUME_PROMPT_WHEN_A_SESSION_ENDED_WITHOUT_A_HANDOFF
          and "No handoff exists yet" not in (prompt or ""),
          prompt)

    # 2. A recorded exit means the seat was stopped under supervision, not
    # crashed. recover-crashed-seats.py reads the same record the same way:
    # any record counts, whatever its code.
    settings = settings_for("recorded-exit")
    supervisor.write_supervisor_state(settings.state_path, {
        "generation": 1,
        supervisor.AGENT_EXIT_CODE_STATE_KEY: 0,
        supervisor.AGENT_EXIT_RECORDED_AT_STATE_KEY: "2026-01-01T00:00:00+00:00"})
    session_id, prompt, resume = launch_once(settings)
    check("BY HAND: a seat carrying a recorded exit still gets a fresh session",
          resume is not True and session_id != crashed.stem,
          (session_id, resume))
    check("BY HAND: and that fresh session gets the no-handoff prompt",
          "No handoff exists yet" in (prompt or ""), prompt)

    # 3. Nothing worth resuming: every transcript is a session this machinery
    # minted that then did nothing. Starting fresh is right, and the run must
    # not resume one of them.
    empty_projects = workspace / "by-hand-resume-projects-empty"
    empty_projects.mkdir(parents=True, exist_ok=True)
    (empty_projects / "failed-successor.jsonl").write_text(
        json.dumps({"type": "user",
                    "message": {"content": "You are x. No handoff exists yet; ask what "
                                           "to work on."}}) + "\n",
        encoding="utf-8")
    settings = settings_for("nothing-worth-resuming")
    supervisor.write_supervisor_state(settings.state_path, {"generation": 1})
    launched = []

    def launch_empty(agent_command, session_id, working_directory, prompt, **kwargs):
        launched.append((session_id, prompt, kwargs.get("resume")))
        return StubLaunchedSession(0)

    with supervisor_names_replaced(
            launch_agent_session=launch_empty,
            project_directory_for_working_directory=lambda _: empty_projects,
            sync_working_branch_with_main=no_branch_sync), \
            contextlib.redirect_stdout(io.StringIO()):
        supervisor.supervise_sessions(settings)
    check("BY HAND: a seat whose every transcript is an empty successor starts fresh",
          launched and launched[0][2] is not True
          and launched[0][0] != "failed-successor",
          str(launched))

    # 4. An unconsumed handoff is the fresher truth and boot-ignition takes it,
    # exactly as before: the by-hand resume must not steal a waiting handoff.
    settings = settings_for("waiting-handoff")
    supervisor.write_supervisor_state(settings.state_path, {"generation": 1})
    settings.handoff_path.write_text(
        "# Handoff\nrestart-counter: 4\nnext-step: carry on\n", encoding="utf-8")
    session_id, prompt, resume = launch_once(settings)
    check("BY HAND: a waiting handoff still wins, and is not resumed over",
          resume is not True and session_id != crashed.stem,
          (session_id, resume))


def run_boot_ignition_case(workspace: Path):
    """A fresh boot that finds an unconsumed handoff ignites from it directly.
    Launching first and letting the wait loop find the file would kill the
    just-born session for a handoff that predates it (observed 2026-08-14 in
    the crash-restart window)."""
    handoff_directory = workspace / "bootignite"
    handoff_directory.mkdir(parents=True, exist_ok=True)
    (handoff_directory / "bootignite-handoff.md").write_text(
        "written-at: 2026-08-14T00:00:00Z\nnext-step: resume the audit\nrestart-counter: 5\n",
        encoding="utf-8",
    )
    supervisor.write_supervisor_state(
        handoff_directory / "bootignite-supervisor-state.json",
        {"consumed_counter": 4, "session_id": "no-such-session", "generation": 4},
    )
    record_path = handoff_directory / "launch-record.txt"
    stub_agent = handoff_directory / "stub-agent"
    stub_agent.write_text(
        "#!/bin/sh\n"
        "exec >/dev/null 2>&1\n"
        # The prompt is the LAST argument, whatever flags precede it:
        # launch_agent_session appends it after --session-id and any
        # --remote-control. Reading it by position ("$3") was correct until
        # --remote-control landed (fe70fe3), after which this stub recorded the
        # flag name instead of the prompt and the case below failed.
        "for launched_prompt; do :; done\n"
        f"printf '%s\\n' \"$launched_prompt\" > '{record_path}'\n"
        "exit 0\n",
        encoding="utf-8",
    )
    stub_agent.chmod(0o755)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", "bootignite", "--cd", str(workspace),
         "--handoff-dir", str(handoff_directory), "--agent-command", str(stub_agent)],
        capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL, timeout=60,
    )
    check("boot with an unconsumed handoff exits cleanly after the ignition session",
          result.returncode == 0, result.stderr[-300:])
    check("the boot says it is igniting from the unconsumed handoff",
          "igniting from an unconsumed handoff" in result.stdout, result.stdout[-400:])
    launched = record_path.read_text(encoding="utf-8") if record_path.is_file() else ""
    check("the initial agent instructions carry the handoff's next step",
          "resume the audit" in launched, launched[:200])
    # The boot-recovery path builds its own prompt: no dialog extract exists,
    # so the next-step and the repository are the successor's whole context.
    # It composes at the launch site through the same threading as the dialog
    # path, which since the user's second round (2026-08-30) carries the
    # branch sync's result instead of the launch clock — the clock sentence
    # was cut by the user himself on the rendered mock. This is the
    # end-to-end proof that the report produced at the launch site reaches
    # the launched prompt: the workspace is what it is, so only the stable
    # "branch sync:" prefix of the report is pinned, never one variant.
    check("the launch-clock sentence is cut from the boot-recovery initial agent instructions",
          launched and "The clock read" not in launched
          and "never from estimate" not in launched,
          launched[:400])
    check("the boot-recovery initial agent instructions carry the sync's own report",
          "branch sync:" in launched, launched[:400])
    check("the boot-recovery initial agent instructions carry the branch-state instruction, exactly",
          " — If this branch has never been pushed, rebase it onto origin/main "
          "before your first substantive action and rerun the tests for what "
          "you touched. If it is pushed, leave it as it is, and start new work "
          "on a branch from origin/main. If `gh pr view` reports its pull "
          "request CONFLICTING, merge origin/main into it by hand, once, and "
          "announce the new head. If this seat has open pull requests, "
          "check their state with `gh`: merge-lane reviews and merges them; a "
          "changes-requested one gets a fix round from a fresh agent — never "
          "extend a head you've already announced."
          in launched,
          launched[:700])
    state = supervisor.read_supervisor_state(handoff_directory / "bootignite-supervisor-state.json")
    check("boot-ignition consumes the handoff counter", state.get("consumed_counter") == 5, str(state))



def run_appended_system_prompt_cases(workspace: Path):
    """Every launched session gets --append-system-prompt-file, and a missing
    file degrades the session rather than losing the seat.

    The supervisor owns this flag rather than the launchers because a
    supervisor is started three ways -- launch-claude-mac, launch-claude-ubuntu
    and resupervise-seat.py -- and a flag living in the launchers would leave a
    recovered seat silently running without the appended text.
    """
    def boot_once(name: str, extra_arguments: list):
        """Boot-ignite once with an argument-recording stub; return its argv,
        one argument per line, and the supervisor's stderr."""
        handoff_directory = workspace / name
        handoff_directory.mkdir(parents=True, exist_ok=True)
        (handoff_directory / f"{name}-handoff.md").write_text(
            "written-at: 2026-08-31T00:00:00Z\nnext-step: carry on\nrestart-counter: 5\n",
            encoding="utf-8",
        )
        supervisor.write_supervisor_state(
            handoff_directory / f"{name}-supervisor-state.json",
            {"consumed_counter": 4, "session_id": "no-such-session", "generation": 4},
        )
        record_path = handoff_directory / "argv.txt"
        stub_agent = handoff_directory / "stub-agent"
        # Records EVERY argument, one per line -- the neighbouring boot case
        # records only the last one, which cannot see a flag.
        stub_agent.write_text(
            "#!/bin/sh\n"
            "exec >/dev/null 2>&1\n"
            f"printf '%s\\n' \"$@\" > '{record_path}'\n"
            "exit 0\n",
            encoding="utf-8",
        )
        stub_agent.chmod(0o755)
        finished = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--agent", name, "--cd", str(workspace),
             "--handoff-dir", str(handoff_directory),
             "--agent-command", str(stub_agent)] + extra_arguments,
            capture_output=True, text=True, check=False,
            stdin=subprocess.DEVNULL, timeout=60,
        )
        argv = record_path.read_text(encoding="utf-8") if record_path.is_file() else ""
        return argv, finished.stderr

    def warning_lines_about_no_separator(stderr: str) -> list:
        return [line for line in stderr.splitlines()
                if line.startswith("handoff-supervisor: no --- line")]

    # A file with no `---` line is all agent text: it goes to the CLI whole,
    # through its own path, as every file did before the split -- with a
    # warning, because the file may have lost the line that keeps editor notes
    # out of the seats.
    prompt_file = workspace / "appended-system-prompt.md"
    prompt_file.write_text("You may commission subagents on your own initiative.\n",
                           encoding="utf-8")

    argv, stderr = boot_once("appendon", ["--agent-append-system-prompt-file", str(prompt_file)])
    check("the launched session carries --append-system-prompt-file",
          "--append-system-prompt-file" in argv.splitlines(), argv)
    check("a file with no --- line is sent whole, through the path it was given",
          str(prompt_file) in argv.splitlines(), argv)
    check("and the supervisor prints exactly one warning line saying so",
          len(warning_lines_about_no_separator(stderr)) == 1
          and str(prompt_file) in warning_lines_about_no_separator(stderr)[0], stderr)
    check("and writes no agent-part file for it",
          not (workspace / "appendon" / "appendon-appended-system-prompt-agent-part.md").exists())
    # The prompt is read by position in the neighbouring case and by every
    # reader of this command; a flag appended after it would BE the prompt.
    lines = [line for line in argv.splitlines() if line]
    check("the prompt is still the last argument, after the new flag",
          lines and lines[-1] not in ("--append-system-prompt-file", str(prompt_file)),
          repr(lines[-3:] if lines else lines))

    # A file with notes above its `---` line: only the part below reaches the
    # session. Before this, the whole file went, and every seat's system prompt
    # carried the notes to editors, "Keep it SHORT" included (observed
    # 2026-09-16 in the cold-read-research seat; user-ruled "fix 2").
    split_file = workspace / "appended-system-prompt-with-notes.md"
    split_file.write_text(
        "# Notes heading\n"
        "\n"
        "Keep it SHORT. EDITOR-NOTE-MARKER\n"
        "\n"
        "---\n"
        "\n"
        "\n"
        "AGENT-TEXT-MARKER: you may commission subagents.\n"
        "\n"
        "---\n"
        "SECOND-SECTION-MARKER after a later --- line, still agent text.\n",
        encoding="utf-8",
    )
    argv, stderr = boot_once("appendsplit", ["--agent-append-system-prompt-file", str(split_file)])
    agent_part_path = workspace / "appendsplit" / "appendsplit-appended-system-prompt-agent-part.md"
    argument_lines = argv.splitlines()
    flag_value = (argument_lines[argument_lines.index("--append-system-prompt-file") + 1]
                  if "--append-system-prompt-file" in argument_lines[:-1] else "")
    check("a file with a --- line is sent through the supervisor's agent-part file",
          flag_value == str(agent_part_path), argv)
    check("and not through its own path",
          str(split_file) not in argument_lines, argv)
    sent = agent_part_path.read_text(encoding="utf-8") if agent_part_path.is_file() else ""
    check("the text sent excludes everything above the --- line",
          sent.strip() != ""
          and "EDITOR-NOTE-MARKER" not in sent and "Notes heading" not in sent, sent)
    check("the text sent is what is below it, from its first non-blank line",
          sent.startswith("AGENT-TEXT-MARKER: you may commission subagents.\n"), repr(sent))
    check("the split is at the FIRST --- line: a later one stays in the text sent",
          "---\nSECOND-SECTION-MARKER" in sent, repr(sent))
    check("a file with a --- line launches with no warning",
          not warning_lines_about_no_separator(stderr), stderr)

    # The real committed file, through the default path, end to end.
    argv, stderr = boot_once("appendcommitted", [])
    agent_part_path = (workspace / "appendcommitted"
                       / "appendcommitted-appended-system-prompt-agent-part.md")
    sent = agent_part_path.read_text(encoding="utf-8") if agent_part_path.is_file() else ""
    check("by default the committed file is sent through the agent-part file",
          str(agent_part_path) in argv.splitlines(), argv)
    check("what the committed file sends carries none of its notes to editors",
          sent.strip() != "" and "Everything above this line is a note" not in sent,
          repr(sent[:300]))

    argv, stderr = boot_once("appendoff", ["--agent-append-system-prompt-file", ""])
    check("an empty value launches with no such flag",
          "--append-system-prompt-file" not in argv.splitlines(), argv)

    missing = workspace / "no-such-appended-prompt.md"
    argv, stderr = boot_once("appendmissing", ["--agent-append-system-prompt-file", str(missing)])
    check("a missing file does not lose the seat -- the session still launches",
          argv.strip() != "", "the stub agent recorded nothing, so no session launched")
    check("a missing file launches with no such flag",
          "--append-system-prompt-file" not in argv.splitlines(), argv)


def run_appended_system_prompt_agent_part_cases(workspace: Path):
    """Where agent_part_of_appended_system_prompt splits a file, on the committed
    file and on made-up ones, and the launch-site fallbacks that keep a launch
    from ever failing over the appended text."""
    split = supervisor.agent_part_of_appended_system_prompt

    committed_text = supervisor.DEFAULT_APPENDED_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    agent_text, separator_found = split(committed_text)
    check("the committed appended-system-prompt file has a --- line", separator_found)
    check("its agent part does not contain the notes' closing sentence",
          "Everything above this line is a note" not in agent_text, agent_text)
    last_committed_line = [line for line in committed_text.splitlines() if line.strip()][-1]
    check("its agent part runs to the end of the file",
          agent_text.rstrip("\n").endswith(last_committed_line), repr(agent_text[-200:]))

    agent_text, separator_found = split("notes\n  ---\t\n\n   \nagent\n\nmore agent\n")
    check("a --- line with surrounding whitespace is the separator",
          separator_found and agent_text == "agent\n\nmore agent\n", repr(agent_text))

    for lookalike in ("----", "--- notes", "- - -", "`---`"):
        text = f"notes\n{lookalike}\nagent\n"
        agent_text, separator_found = split(text)
        check(f"{lookalike!r} is not the separator, so the text comes back whole",
              not separator_found and agent_text == text, repr(agent_text))

    agent_text, separator_found = split("no separator here\n")
    check("text with no --- line comes back whole, and says so",
          not separator_found and agent_text == "no separator here\n", repr(agent_text))

    # The launch-site fallbacks, called directly.
    for_launch = supervisor.appended_system_prompt_file_for_launch
    check("an empty source path launches without the flag",
          for_launch("", workspace / "unused-agent-part.md") == "")

    unreadable_stderr = io.StringIO()
    with contextlib.redirect_stderr(unreadable_stderr):
        chosen = for_launch(str(workspace / "vanished-appended-prompt.md"),
                            workspace / "vanished-agent-part.md")
    check("a source gone by launch time launches without the flag, with one warning line",
          chosen == "" and len(unreadable_stderr.getvalue().splitlines()) == 1
          and unreadable_stderr.getvalue().startswith("handoff-supervisor: "),
          repr((chosen, unreadable_stderr.getvalue())))

    source = workspace / "appended-prompt-unwritable-destination.md"
    source.write_text("notes\n---\nagent\n", encoding="utf-8")
    unwritable_stderr = io.StringIO()
    with contextlib.redirect_stderr(unwritable_stderr):
        chosen = for_launch(str(source), workspace / "no-such-directory" / "agent-part.md")
    check("an agent part that cannot be written sends the whole file, with one warning line",
          chosen == str(source) and len(unwritable_stderr.getvalue().splitlines()) == 1
          and unwritable_stderr.getvalue().startswith("handoff-supervisor: "),
          repr((chosen, unwritable_stderr.getvalue())))

    # Read at every launch: an edit between two launches reaches the second.
    agent_part_path = workspace / "reread-agent-part.md"
    source.write_text("notes\n---\nfirst agent text\n", encoding="utf-8")
    for_launch(str(source), agent_part_path)
    source.write_text("notes\n---\nsecond agent text\n", encoding="utf-8")
    for_launch(str(source), agent_part_path)
    check("the source is re-read at each launch, so an edit reaches the next one",
          agent_part_path.read_text(encoding="utf-8") == "second agent text\n",
          agent_part_path.read_text(encoding="utf-8"))


def run_launched_session_seat_environment_cases(workspace: Path):
    """Every launched session is told the seat's name and directory, and its own
    session id.

    The handoff writer the agent runs names its handoff after the name this
    supervisor watches only if the session carries it: taken from the shell's
    working directory instead, a `cd scripts` or a worktree names the handoff
    after that directory, and nothing polls the file (user-ruled 2026-09-16).
    The agent command here is a real child process that records what its
    environment holds, so what is proven is what a launched session sees.
    The supervisor itself is started with decoy values of all three variables,
    as it would be when run from inside another seat's session, so an
    inherited value cannot pass for a value the supervisor set.

    The session id is what confines the name and directory to this session:
    the writer honours them only where CLAUDE_CODE_SESSION_ID equals it, and a
    child `claude` the session starts inherits all three under its own id
    (PR #414 review, 2026-09-16). So it must be the id launched, the one on
    the command line and in the state file.
    """
    name = "launchenvseat"
    handoff_directory = workspace / name
    handoff_directory.mkdir(parents=True, exist_ok=True)
    seat_directory = workspace / "launchenvseat-directory"
    seat_directory.mkdir(parents=True, exist_ok=True)
    record_path = handoff_directory / "environment.json"
    stub_agent = handoff_directory / "stub-agent"
    stub_agent.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        f"with open({str(record_path)!r}, 'w', encoding='utf-8') as handle:\n"
        "    recorded = {variable: os.environ.get(variable) for variable in (\n"
        "        'NEDSCHORUS_HANDOFF_SUPERVISOR_AGENT_NAME',\n"
        "        'NEDSCHORUS_HANDOFF_SUPERVISOR_WORKING_DIRECTORY',\n"
        "        'NEDSCHORUS_HANDOFF_SUPERVISOR_SESSION_ID')}\n"
        "    recorded['argv'] = sys.argv[1:]\n"
        "    json.dump(recorded, handle)\n",
        encoding="utf-8",
    )
    stub_agent.chmod(0o755)
    environment = dict(os.environ)
    environment["NEDSCHORUS_HANDOFF_SUPERVISOR_AGENT_NAME"] = "decoy-outer-seat"
    environment["NEDSCHORUS_HANDOFF_SUPERVISOR_WORKING_DIRECTORY"] = str(workspace / "decoy-outer-seat")
    environment["NEDSCHORUS_HANDOFF_SUPERVISOR_SESSION_ID"] = "decoy-outer-session"
    subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", name, "--cd", str(seat_directory),
         "--handoff-dir", str(handoff_directory), "--agent-command", str(stub_agent)],
        capture_output=True, text=True, check=False,
        stdin=subprocess.DEVNULL, timeout=60, env=environment,
    )
    recorded = (json.loads(record_path.read_text(encoding="utf-8"))
                if record_path.is_file() else {})
    check("the launched session ran and recorded its environment",
          record_path.is_file(), "the stub agent wrote no record, so no session launched")
    check("the launched session is told the agent name its supervisor watches",
          recorded.get("NEDSCHORUS_HANDOFF_SUPERVISOR_AGENT_NAME") == name, str(recorded))
    # main() resolves --cd, so on macOS a /var tempdir arrives as /private/var.
    check("the launched session is told the directory its supervisor launched it in",
          recorded.get("NEDSCHORUS_HANDOFF_SUPERVISOR_WORKING_DIRECTORY")
          == str(seat_directory.resolve()), str(recorded))
    launched_argv = recorded.get("argv") or []
    launched_session_id = (launched_argv[launched_argv.index("--session-id") + 1]
                           if "--session-id" in launched_argv[:-1] else None)
    state = supervisor.read_supervisor_state(handoff_directory / f"{name}-supervisor-state.json")
    check("the launched session is told the session id it was launched with",
          launched_session_id is not None
          and recorded.get("NEDSCHORUS_HANDOFF_SUPERVISOR_SESSION_ID") == launched_session_id
          and state.get("session_id") == launched_session_id,
          f"{recorded} state session_id={state.get('session_id')}")


def run_spawned_subagent_roster_cases(workspace: Path, recent: str):
    """The successor is told which subagents were still working when the
    session it replaces ended, and that it may need to re-commission
    similar agents.

    Ruled 2026-08-23 (record the subagents, do not wait for them), narrowed
    2026-08-29, reworded in the user's second round (ruled 2026-08-30 on a
    rendered mock): the writer records only subagents still working at write
    time, so every roster entry the supervisor reads is one the reincarnation
    itself killed. The prompt says re-commission, never restart or resume,
    because resume-by-id across a reincarnation is impossible — probed 2026-08-29:
    SendMessage to a predecessor's subagent id returns "No transcript found"
    (the resolver is session-scoped) although the transcript survives at
    <predecessor-session-dir>/subagents/agent-<id>.jsonl.
    """
    roster_fields = {
        "written-at": recent,
        "next-step": "merge the queue",
        # Synthetic ids, in the narrowed field shape: agent id and job
        # description only — every recorded entry is still working by
        # construction, so the field carries no event and no timestamp.
        "spawned-subagent-1": 'afixture0cutoff01 "Fix ignored-path write blind spot"',
        "spawned-subagent-2": 'afixture0cutoff02 "Review PR 150 independently"',
    }
    predecessor_directory = Path("/tmp/projects/-fixture-seat/0000-session-id")
    prompt = supervisor.build_ignition_prompt(
        Path("/tmp/d.md"), roster_fields, predecessor_directory)
    check("ignition counts the subagents still working at the reincarnation",
          "had 2 subagent(s) still working when it ended" in prompt, prompt)
    check("ignition names each subagent and what it was doing",
          "afixture0cutoff01" in prompt and "Fix ignored-path write blind spot" in prompt
          and "afixture0cutoff02" in prompt and "Review PR 150 independently" in prompt, prompt)
    # The roster sentence's tail, exactly as the user reworded it (ruled
    # 2026-08-30 on a rendered mock). Against the pre-revision supervisor
    # this fails — the sentence there read "Re-commission each — a fresh
    # agent on the job; the dead one's full transcript is at ... if its
    # state matters. A dead subagent cannot be resumed by id."
    check("ignition says the successor may need to re-commission similar agents, exactly",
          nothing_is_appended_to(
              prompt,
              ". You may need to re-commission similar agents. If you need more "
              "context, the dead agents' full transcripts are at "
              f"{predecessor_directory}/subagents/agent-<id>.jsonl.",
              # The roster sentence is the last of the preamble, and this
              # fixture's verbatim block is not unterminated, so only the next
              # step follows it.
              "\n\nThen take the next step:\nmerge the queue"),
          prompt)
    # The sentence itself, word for word, as the module template it now lives
    # in. Three insertions the caller computes -- the count, the joined
    # roster, and the directory the dead agents' transcripts survive in -- so
    # the pin holds the template with its placeholders spelled out.
    check("the orphaned-subagent roster sentence is word for word what the user ruled",
          supervisor.ORPHANED_SUBAGENT_ROSTER_SENTENCE_TEMPLATE == (
              "The session you are replacing had {subagent_count} subagent(s) still "
              "working when it ended: {joined_roster}. You may need to re-commission "
              "similar agents. If you need more context, the dead agents' full "
              "transcripts are at {transcript_directory}/subagents/agent-<id>.jsonl."),
          repr(supervisor.ORPHANED_SUBAGENT_ROSTER_SENTENCE_TEMPLATE))
    check("the first-round roster wording is gone",
          "Re-commission each" not in prompt and "if its state matters" not in prompt
          and "cannot be resumed by id" not in prompt, prompt)
    # The 2026-08-23 sentence is gone with the entries it explained: nothing
    # in the roster is completed any more, and the successor is never told to
    # restart — the probe measured that a restart by id cannot work.
    check("the completed-means-stopped sentence is cut",
          "means that subagent stopped" not in prompt, prompt)
    check("ignition never says restart",
          "restart" not in prompt.lower(), prompt)
    # A caller with no predecessor directory (a direct or test caller — the
    # supervisor always composes one) gets the directory PATTERN, named as a
    # placeholder rather than an invented path.
    fallback_prompt = supervisor.build_ignition_prompt(Path("/tmp/d.md"), roster_fields)
    check("without a predecessor directory the prompt names the pattern",
          "<predecessor-session-dir>/subagents/agent-<id>.jsonl" in fallback_prompt,
          fallback_prompt)

    # The roster is optional, and its absence must read as silence rather than
    # as an empty list: when nothing was still working the prompt says NOTHING
    # about subagents (user-ruled 2026-08-29). A handoff written before this
    # field existed reads the same way.
    older_prompt = supervisor.build_ignition_prompt(
        Path("/tmp/d.md"), {"written-at": recent, "next-step": "merge the queue"},
        predecessor_directory)
    check("ignition says nothing about subagents when the handoff has no roster",
          "subagent" not in older_prompt, older_prompt)

    # Order is the writer's, not the dict's or a string sort's: field 10 comes
    # after field 9, and the successor reads them in the order they were spawned.
    many = {"written-at": recent, "next-step": "carry on"}
    for ordinal in range(1, 12):
        many[f"spawned-subagent-{ordinal}"] = f'agent-{ordinal:02d} "job {ordinal:02d}"'
    ordered_prompt = supervisor.build_ignition_prompt(Path("/tmp/d.md"), many)
    check("the roster keeps the writer's order past nine subagents",
          ordered_prompt.index("agent-09") < ordered_prompt.index("agent-10")
          < ordered_prompt.index("agent-11"), ordered_prompt)

    # A handoff file written by the writer must read back as a roster, so the
    # two ends cannot drift apart on the field name.
    handoff_path = workspace / "roster-handoff.md"
    handoff_path.write_text(
        "written-at: 2026-08-23T22:00:00Z\n"
        "next-step: merge the queue\n"
        "restart-counter: 3\n"
        "spawned-subagent-1: afixture0cutoff01 \"Fix ignored-path\"\n"
        "next-step-verbatim: <<END-OF-NEXT-STEP\n"
        "merge the queue\n"
        "and then rest\n"
        "END-OF-NEXT-STEP\n",
        encoding="utf-8",
    )
    parsed = supervisor.parse_handoff_file(handoff_path)
    check("a roster field survives the handoff-file parser",
          supervisor.spawned_subagent_roster_from(parsed)
          == [parsed["spawned-subagent-1"]], str(parsed))
    check("the roster does not disturb the verbatim block beneath it",
          supervisor.next_step_from(parsed) == "merge the queue\nand then rest",
          repr(supervisor.next_step_from(parsed)))


def run_recycle_prompt_composition_cases(workspace: Path, recent: str):
    """carry_over_to_successor, with the extractor stubbed: what the reincarnation
    actually prints to the console, and what it actually puts in the prompt.

    Two rulings of 2026-08-29 meet here. The queue-status line is CUT from
    the initial agent instructions but the console print STAYS — before this change the
    supervisor threaded queue status into every reincarnation prompt
    unconditionally (queue_status_line always returns a truthy string), so
    the prompt assertion below fails against that code. And the plan now
    carries the predecessor's session directory, composed from the retiring
    session id, so the roster sentence can name where the dead subagents'
    transcripts survive.
    """
    home = workspace / "recycle-composition"
    handoff_directory = home / "handoffs"
    handoff_directory.mkdir(parents=True)
    working_directory = home / "seat"
    (working_directory / "nc-queue").mkdir(parents=True)
    (working_directory / "nc-queue" / "2026-07-30-stale-item.md").write_text("x", encoding="utf-8")
    settings = supervisor.SupervisorSettings(
        agent="composer", working_directory=working_directory,
        handoff_directory=handoff_directory, agent_command="true", first_prompt="")
    settings.handoff_path.write_text(
        "written-at: " + recent + "\n"
        "next-step: keep composing\n"
        "restart-counter: 2\n"
        "spawned-subagent-1: afixture0cutoff01 \"Fix ignored-path write blind spot\"\n",
        encoding="utf-8")
    handoff_fields = supervisor.parse_handoff_file(settings.handoff_path)

    original_extract_dialog = supervisor.extract_dialog
    original_tasks_root = supervisor.TASKS_ROOT
    original_pin = os.environ.get("CLAUDE_CODE_TASK_LIST_ID")
    console = io.StringIO()
    try:
        supervisor.extract_dialog = (
            lambda session_id, working_directory, output_path:
            output_path.write_text("the extracted dialog\n", encoding="utf-8") > 0)
        supervisor.TASKS_ROOT = home / "tasks"
        os.environ.pop("CLAUDE_CODE_TASK_LIST_ID", None)
        with contextlib.redirect_stdout(console):
            successor_id, plan = supervisor.carry_over_to_successor(
                settings, "0000-retiring-session", handoff_fields, generation=3)
    finally:
        supervisor.extract_dialog = original_extract_dialog
        supervisor.TASKS_ROOT = original_tasks_root
        if original_pin is None:
            os.environ.pop("CLAUDE_CODE_TASK_LIST_ID", None)
        else:
            os.environ["CLAUDE_CODE_TASK_LIST_ID"] = original_pin

    printed = console.getvalue()
    check("a reincarnation still prints the queue status to its own console",
          "handoff-supervisor: queues — nc-queue: 1, oldest 2026-07-30-stale-item.md" in printed,
          printed)
    check("the plan names the predecessor's session directory, composed from its id",
          plan is not None and plan.predecessor_session_directory
          == supervisor.project_directory_for_working_directory(working_directory)
          / "0000-retiring-session",
          str(plan and plan.predecessor_session_directory))
    # compose() takes the branch sync's one-line report since the user's
    # second round (2026-08-30) — the launch site produces it immediately
    # before composing, exactly where the launch clock used to be read.
    # Guarded so the cases below FAIL cleanly against the pre-revision plan
    # instead of crashing the suite: compose(launch_time) there feeds the
    # report string to the clock helper, which raises on it.
    try:
        prompt = plan.compose("branch sync: composer-branch is 2 commit(s) behind main")
    except (TypeError, AttributeError):
        prompt = ""
    check("the reincarnation prompt carries no queue status",
          "Queue status" not in prompt and "queues —" not in prompt, prompt)
    check("the reincarnation prompt carries no task-count line",
          "task(s) are visible" not in prompt, prompt)
    check("the reincarnation prompt carries no launch-clock sentence",
          "The clock read" not in prompt and "never from estimate" not in prompt, prompt)
    check("the reincarnation prompt stamps the written-at and defers the gap to `date`",
          "written at 20" in prompt
          and "Calculate from `date` how long ago that was" in prompt, prompt)
    check("the reincarnation prompt carries the branch-state line the plan was composed with",
          "branch sync: composer-branch is 2 commit(s) behind main — If this "
          "branch has never been pushed, rebase it onto origin/main before your "
          "first substantive action"
          in prompt, prompt)
    check("the reincarnation prompt points at the predecessor's subagent transcripts",
          f"{plan.predecessor_session_directory}/subagents/agent-<id>.jsonl" in prompt, prompt)
    check("the reincarnation prompt still ignites from the next step",
          "keep composing" in prompt, prompt)


def run_retiring_session_id_from_the_handoff_cases(workspace: Path, recent: str):
    """carry_over_to_successor reads the retiring session's id off the handoff.

    Both callers pass the id from the supervisor's state file, which names the
    session this supervisor launched; the handoff's own written-by-session
    names the session that wrote it. The divergent case below FAILS against
    code that trusts the state file: it extracts, pre-seeds and cites the
    launched session instead of the writer. The two fallback cases — field
    absent (an older handoff) and field "unknown" (a session with no
    CLAUDE_CODE_SESSION_ID) — pass either way; they are here so the
    preference cannot be turned into a requirement.

    The task store is keyed by session id only when the launchers' pin is
    absent, so the pin is popped for the duration: with it set, preseed_tasks
    returns 0 without reading any store and the task assertions would prove
    nothing.
    """
    home = workspace / "retiring-session-id-from-the-handoff"
    tasks_root = home / "tasks"

    def carry_over(case_name: str, written_by_session_line: str,
                   tracked_session_id: str, handoff_session_id: str):
        """One carry_over_to_successor run, with the extractor recording its id.

        Seeds a task record under BOTH candidate session ids, with the id in
        the record, so the copy that reaches the successor names the store it
        came from rather than merely existing.
        """
        case_home = home / case_name
        handoff_directory = case_home / "handoffs"
        handoff_directory.mkdir(parents=True)
        working_directory = case_home / "seat"
        working_directory.mkdir(parents=True)
        for store_session_id in (tracked_session_id, handoff_session_id):
            store = tasks_root / store_session_id
            store.mkdir(parents=True, exist_ok=True)
            (store / "1.json").write_text(
                json.dumps({"task": f"a task of {store_session_id}"}), encoding="utf-8")
        settings = supervisor.SupervisorSettings(
            agent="carrier", working_directory=working_directory,
            handoff_directory=handoff_directory, agent_command="true", first_prompt="")
        settings.handoff_path.write_text(
            "written-at: " + recent + "\n"
            "next-step: keep carrying\n"
            "restart-counter: 4\n"
            + written_by_session_line,
            encoding="utf-8")
        handoff_fields = supervisor.parse_handoff_file(settings.handoff_path)

        extracted_from = []

        def recording_extract_dialog(session_id, extract_working_directory, output_path):
            extracted_from.append(session_id)
            output_path.write_text(f"the dialog of {session_id}\n", encoding="utf-8")
            return True

        original_extract_dialog = supervisor.extract_dialog
        original_tasks_root = supervisor.TASKS_ROOT
        original_pin = os.environ.get("CLAUDE_CODE_TASK_LIST_ID")
        console = io.StringIO()
        try:
            supervisor.extract_dialog = recording_extract_dialog
            supervisor.TASKS_ROOT = tasks_root
            os.environ.pop("CLAUDE_CODE_TASK_LIST_ID", None)
            with contextlib.redirect_stdout(console):
                successor_id, plan = supervisor.carry_over_to_successor(
                    settings, tracked_session_id, handoff_fields, generation=5)
        finally:
            supervisor.extract_dialog = original_extract_dialog
            supervisor.TASKS_ROOT = original_tasks_root
            if original_pin is None:
                os.environ.pop("CLAUDE_CODE_TASK_LIST_ID", None)
            else:
                os.environ["CLAUDE_CODE_TASK_LIST_ID"] = original_pin

        carried_task = tasks_root / successor_id / "1.json"
        return SimpleNamespace(
            extracted_from=extracted_from,
            successor_id=successor_id,
            plan=plan,
            printed=console.getvalue(),
            carried_task=(carried_task.read_text(encoding="utf-8")
                          if carried_task.is_file() else ""),
            predecessor_session_directory_for=lambda session_id: (
                supervisor.project_directory_for_working_directory(working_directory)
                / session_id),
        )

    # --- The handoff's writer is not the session the supervisor launched ---
    launched = "ac2b8ebe-the-session-the-supervisor-launched"
    writer = "145a31fd-the-session-that-wrote-the-handoff"
    diverged = carry_over("diverged", f"written-by-session: {writer}\n", launched, writer)
    check("the dialog is extracted from the session that wrote the handoff",
          diverged.extracted_from == [writer], str(diverged.extracted_from))
    check("the plan names the writing session's directory, not the launched one's",
          diverged.plan is not None
          and diverged.plan.predecessor_session_directory
          == diverged.predecessor_session_directory_for(writer),
          str(diverged.plan and diverged.plan.predecessor_session_directory))
    check("the successor is pre-seeded from the writing session's task store",
          writer in diverged.carried_task, diverged.carried_task)
    check("the console names both ids when the handoff's writer is not the tracked session",
          writer in diverged.printed and launched in diverged.printed, diverged.printed)

    # --- Fallbacks: nothing to prefer, so the tracked id stands -----------
    absent = carry_over("absent", "", "0000-tracked-with-no-field", "0000-unused-by-this-case")
    check("a handoff without the field falls back to the tracked session",
          absent.extracted_from == ["0000-tracked-with-no-field"], str(absent.extracted_from))
    check("the fallback plan names the tracked session's directory",
          absent.plan is not None
          and absent.plan.predecessor_session_directory
          == absent.predecessor_session_directory_for("0000-tracked-with-no-field"),
          str(absent.plan and absent.plan.predecessor_session_directory))
    check("the fallback pre-seeds from the tracked session's task store",
          "0000-tracked-with-no-field" in absent.carried_task, absent.carried_task)

    unknown = carry_over("unknown", "written-by-session: unknown\n",
                         "0000-tracked-under-unknown", "0000-also-unused")
    check("a handoff whose writer is `unknown` falls back to the tracked session",
          unknown.extracted_from == ["0000-tracked-under-unknown"], str(unknown.extracted_from))
    check("the `unknown` fallback plan names the tracked session's directory",
          unknown.plan is not None
          and unknown.plan.predecessor_session_directory
          == unknown.predecessor_session_directory_for("0000-tracked-under-unknown"),
          str(unknown.plan and unknown.plan.predecessor_session_directory))
    check("the `unknown` fallback pre-seeds from the tracked session's task store",
          "0000-tracked-under-unknown" in unknown.carried_task, unknown.carried_task)


with tempfile.TemporaryDirectory() as temporary_directory:
    recent_timestamp = run_offline_cases(Path(temporary_directory))
    run_branch_sync_cases(Path(temporary_directory))
    run_exit_handoff_cases(Path(temporary_directory))
    run_adoption_cases(Path(temporary_directory))
    run_dont_restart_without_a_terminal_case(Path(temporary_directory))
    run_no_seat_recycle_refusal_case(Path(temporary_directory))
    run_agent_exit_record_cases(Path(temporary_directory))
    run_by_hand_resume_cases(Path(temporary_directory))
    run_boot_ignition_case(Path(temporary_directory))
    run_appended_system_prompt_cases(Path(temporary_directory))
    run_appended_system_prompt_agent_part_cases(Path(temporary_directory))
    run_launched_session_seat_environment_cases(Path(temporary_directory))
    run_first_prompt_file_cases(Path(temporary_directory))
    run_process_identity_cases(Path(temporary_directory))
    run_lock_cases(Path(temporary_directory))
    run_multi_line_next_step_cases(Path(temporary_directory), recent_timestamp)
    run_launch_and_retention_cases(Path(temporary_directory), recent_timestamp)
    run_spawned_subagent_roster_cases(Path(temporary_directory), recent_timestamp)
    run_recycle_prompt_composition_cases(Path(temporary_directory), recent_timestamp)
    run_retiring_session_id_from_the_handoff_cases(Path(temporary_directory), recent_timestamp)

# --- The depths this system's move depends on (added 2026-09-20) ----------
# When main-gatekeeper moved into nc-systems/, its suite kept a
# `SCRIPT_PATH.parent.parent` that had meant the repository root from scripts/
# and silently began naming nc-systems/ instead. Nothing failed, so nothing
# said so. These cases pin every depth this system resolves across, in both
# the suite and the code, so the same slip here fails out loud.
check("the suite's REPOSITORY_ROOT is the repository, not nc-systems/",
      (REPOSITORY_ROOT / "scripts").is_dir() and (REPOSITORY_ROOT / ".git").exists(),
      str(REPOSITORY_ROOT))
check("the suite's SYSTEM_DIRECTORY holds the script it tests",
      SCRIPT_PATH.is_file(), str(SCRIPT_PATH))
check("the supervisor's own REPOSITORY_ROOT is the repository",
      (supervisor.REPOSITORY_ROOT / "scripts").is_dir(),
      str(supervisor.REPOSITORY_ROOT))
# The two files that deliberately did NOT move in step 1: a running supervisor
# resolves them at import, so they stay in scripts/ until every live supervisor
# runs from nc-systems/handoff/.
check("the extractor the supervisor points at is on disk where it stays",
      supervisor.EXTRACTOR_PATH.is_file(), str(supervisor.EXTRACTOR_PATH))
check("the extractor is still under scripts/, not inside this system",
      supervisor.EXTRACTOR_PATH.parent.name == "scripts",
      str(supervisor.EXTRACTOR_PATH))
check("the appended-system-prompt default resolves under docs/agents",
      supervisor.DEFAULT_APPENDED_SYSTEM_PROMPT_PATH.is_file(),
      str(supervisor.DEFAULT_APPENDED_SYSTEM_PROMPT_PATH))

if "--canary" in sys.argv:
    print("\n-- live pre-seed canaries (launching real sessions) --")
    run_preseed_canaries()
else:
    print("\n(skipped the live pre-seed canaries; pass --canary to run them)")

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
