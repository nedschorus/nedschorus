#!/usr/bin/env python3
"""Tests for handoff-supervisor.py.

Run: python3 scripts/handoff-supervisor-test.py
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
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

SCRIPT_PATH = Path(__file__).with_name("handoff-supervisor.py")

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

    supervisor.write_supervisor_state(heartbeat_state_path, {"session_id": "s"})
    alive, explanation = supervisor.supervisor_liveness(heartbeat_state_path)
    check("state without a heartbeat reads as dead", not alive and "no heartbeat" in explanation, explanation)

    supervisor.stamp_heartbeat(heartbeat_state_path, {"session_id": "s"})
    alive, explanation = supervisor.supervisor_liveness(heartbeat_state_path)
    check("a fresh stamp reads as alive", alive, explanation)

    supervisor.write_supervisor_state(
        heartbeat_state_path,
        {"last_poll_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()},
    )
    alive, explanation = supervisor.supervisor_liveness(heartbeat_state_path)
    check("a stale stamp reads as dead", not alive and "no supervisor is watching" in explanation, explanation)

    supervisor.write_supervisor_state(heartbeat_state_path, {"last_poll_at": "not a timestamp"})
    alive, explanation = supervisor.supervisor_liveness(heartbeat_state_path)
    check("an unreadable stamp reads as dead", not alive and "unreadable" in explanation, explanation)

    check_result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--check", "--agent", "heartbeat",
         "--handoff-dir", str(workspace)],
        capture_output=True, text=True, check=False,
    )
    check("--check exits non-zero for a dead supervisor", check_result.returncode == 1,
          f"code {check_result.returncode}: {check_result.stdout.strip()}")

    supervisor.stamp_heartbeat(heartbeat_state_path, {"session_id": "s"})
    check_result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--check", "--agent", "heartbeat",
         "--handoff-dir", str(workspace)],
        capture_output=True, text=True, check=False,
    )
    check("--check exits zero for a live supervisor", check_result.returncode == 0,
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
    """Adopting a running session is what lets a hand-started agent recycle:
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
    """A supervisor an agent started has no terminal. Asking `restart? y/n`
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


def run_lock_cases(workspace: Path):
    """Two supervisors on one agent would each kill the session and each launch
    a successor, so the second must refuse to start."""
    lock_path = workspace / "locktest-supervisor.lock"
    check("the lock is claimable when free", supervisor.claim_supervisor_lock(lock_path))
    check("the lock records the holder", lock_path.read_text().strip() == str(os.getpid()))
    check("the same process may re-enter its own lock", supervisor.claim_supervisor_lock(lock_path))

    lock_path.write_text("99999999\n", encoding="utf-8")
    check("a lock held by a dead process is reclaimed", supervisor.claim_supervisor_lock(lock_path))

    live_holder = subprocess.Popen(  # pylint: disable=consider-using-with
        [sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        lock_path.write_text(f"{live_holder.pid}\n", encoding="utf-8")
        check("a lock held by a live process blocks a second supervisor",
              not supervisor.claim_supervisor_lock(lock_path))
    finally:
        live_holder.kill()
        live_holder.wait()

    lock_path.write_text("not a number\n", encoding="utf-8")
    check("an unreadable lock is reclaimed", supervisor.claim_supervisor_lock(lock_path))
    lock_path.unlink(missing_ok=True)


def run_multi_line_next_step_cases(workspace: Path, recent: str):
    """R20's reader half: a verbatim block is parsed, preferred, and survives.

    Format in docs/cross-project/fast-handoff-design.md. The block is the last
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
    check("the ignition prompt carries the block's line breaks",
          "FIRST ACTION: run it.\n\nTHEN: fix the locale case." in prompt, repr(prompt))
    check("the ignition prompt prefers the verbatim block over the collapsed line",
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
    check("an unterminated block tells the successor what happened",
          "unterminated" in truncated_prompt, repr(truncated_prompt))

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
    writer_script = Path(__file__).with_name("handoff-write-and-check-supervisor.py")
    original = ("FIRST ACTION: read the anchor.\n"
                "\n"
                "THEN: present item 3, and keep the indentation:\n"
                "    - a nested bullet\n"
                "CONTEXT: nothing else.")
    next_step_file = workspace / "round-trip-next-step.txt"
    next_step_file.write_text(original + "\n", encoding="utf-8")
    environment = {key: value for key, value in os.environ.items()
                   if key not in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_PID")}
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
    # --- Ignition prompt --------------------------------------------------
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
          "continue them when you get a chance. This session was launched by "
          "scripts/handoff-supervisor.py, which watches this seat and composed "
          "this prompt — read it if you need to investigate the handoff "
          "mechanism." in prompt,
          prompt[:800])
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
    check("the branch-state instruction follows the sync result, exactly",
          "branch sync: fixture-branch is 3 commit(s) behind main — if behind, "
          "catch up with origin/main when safe. On conflicts, if you can't "
          "resolve them, explain the situation to the user. If this seat has "
          "open pull requests, check their state with `gh`: merge-lane reviews "
          "and merges them; a changes-requested one gets a fix round from a "
          "fresh agent — never extend a head you've already announced."
          in synced_prompt,
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
    # ignition prompt unconditionally — and structurally below, where neither
    # the builder nor the plan accepts a count any more.
    check("the task-count line is cut from the ignition prompt",
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
    check("ignition survives a missing next-step", "continue from where that dialog ends" in prompt_without_step)
    # The queue-status line was CUT from the prompt (user-ruled 2026-08-29,
    # expiring his 2026-08-12 #32 ruling: "Also useless is the reminder there
    # are files in the queues. Thats what queues are for."). The cut is
    # pinned structurally — nothing can thread a queue status into the
    # prompt, because neither the builder nor the plan accepts one — and
    # behaviorally in run_recycle_prompt_composition_cases below, where the
    # OLD supervisor put the line into every recycle prompt unconditionally.
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
    # supervisor put the sentence into every ignition prompt — and
    # structurally: neither the builder nor the plan threads a launch time
    # any more, and the sentence's helper is gone from the module.
    check("the launch-clock sentence is cut from the ignition prompt",
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

    # --- Queue status -----------------------------------------------------
    project = workspace / "project"
    (project / "nc-queue").mkdir(parents=True)
    (project / "nc-queue" / "2026-07-28-older-note.md").write_text("x", encoding="utf-8")
    (project / "nc-queue" / "2026-08-01-newer-note.md").write_text("x", encoding="utf-8")
    (project / "nc-queue" / "README.md").write_text("x", encoding="utf-8")
    (project / "docs" / "wiki" / "queue").mkdir(parents=True)
    line = supervisor.queue_status_line(project)
    check("queue status counts a loaded queue", "nc-queue: 2" in line, line)
    check("queue status names the oldest item", "2026-07-28-older-note.md" in line, line)
    check("queue status reports an empty queue", "docs/wiki/queue: empty" in line, line)

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

        # --- Recycle under a PINNED list (nedschorus#141) -----------------
        # The seat's generations share one launcher-pinned store, so a
        # recycle copies nothing and the seat's records survive untouched.
        # (The ignition count-check this block once guarded — "Confirm 0
        # task(s) are visible to you" over a list holding N — was cut with
        # the task-count line, user-ruled 2026-08-30.) Shaped like a real
        # recycle: tasks already in the seat's store, a fresh successor id,
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
    a recycle, which is how the fleet carries tasks since nedschorus#141.
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
    check("a diverged branch is reported, not merged", "merge when ready" in report, report)
    check("the diverged report counts both directions",
          "1 ahead of main" in report and "1 behind" in report, report)
    check("a diverged branch keeps its own commit",
          git_in(["log", "-1", "--format=%s"], home).stdout.strip() == "the agent's own work")

    # Ahead-only: everything main has, plus local work. Nothing to pull.
    git_in(["merge", "--no-edit", "--quiet", "origin/main"], home)
    report = supervisor.sync_working_branch_with_main(home)
    check("a branch ahead of main with all of main reports nothing to pull",
          "nothing to pull" in report, report)


def run_no_seat_recycle_refusal_case(workspace: Path):
    """A handoff arriving at a supervisor with no terminal must not recycle:
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
    check("the ignition prompt carries the handoff's next step",
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
    check("the launch-clock sentence is cut from the boot-recovery ignition prompt",
          launched and "The clock read" not in launched
          and "never from estimate" not in launched,
          launched[:400])
    check("the boot-recovery ignition prompt carries the sync's own report",
          "branch sync:" in launched, launched[:400])
    check("the boot-recovery ignition prompt carries the branch-state instruction, exactly",
          " — if behind, catch up with origin/main when safe. On conflicts, if "
          "you can't resolve them, explain the situation to the user. If this "
          "seat has open pull requests, check their state with `gh`: merge-lane "
          "reviews and merges them; a changes-requested one gets a fix round "
          "from a fresh agent — never extend a head you've already announced."
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
    def boot_once(name: str, extra_arguments: list) -> str:
        """Boot-ignite once with an argument-recording stub; return its argv."""
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
        subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--agent", name, "--cd", str(workspace),
             "--handoff-dir", str(handoff_directory),
             "--agent-command", str(stub_agent)] + extra_arguments,
            capture_output=True, text=True, check=False,
            stdin=subprocess.DEVNULL, timeout=60,
        )
        return record_path.read_text(encoding="utf-8") if record_path.is_file() else ""

    prompt_file = workspace / "appended-system-prompt.md"
    prompt_file.write_text("You may commission subagents on your own initiative.\n",
                           encoding="utf-8")

    argv = boot_once("appendon", ["--agent-append-system-prompt-file", str(prompt_file)])
    check("the launched session carries --append-system-prompt-file",
          "--append-system-prompt-file" in argv.splitlines(), argv)
    check("it carries the path it was given",
          str(prompt_file) in argv.splitlines(), argv)
    # The prompt is read by position in the neighbouring case and by every
    # reader of this command; a flag appended after it would BE the prompt.
    lines = [line for line in argv.splitlines() if line]
    check("the prompt is still the last argument, after the new flag",
          lines and lines[-1] not in ("--append-system-prompt-file", str(prompt_file)),
          repr(lines[-3:] if lines else lines))

    argv = boot_once("appendoff", ["--agent-append-system-prompt-file", ""])
    check("an empty value launches with no such flag",
          "--append-system-prompt-file" not in argv.splitlines(), argv)

    missing = workspace / "no-such-appended-prompt.md"
    argv = boot_once("appendmissing", ["--agent-append-system-prompt-file", str(missing)])
    check("a missing file does not lose the seat -- the session still launches",
          argv.strip() != "", "the stub agent recorded nothing, so no session launched")
    check("a missing file launches with no such flag",
          "--append-system-prompt-file" not in argv.splitlines(), argv)


def run_spawned_subagent_roster_cases(workspace: Path, recent: str):
    """The successor is told which subagents were still working when the
    session it replaces ended, and that it may need to re-commission
    similar agents.

    Ruled 2026-08-23 (record the subagents, do not wait for them), narrowed
    2026-08-29, reworded in the user's second round (ruled 2026-08-30 on a
    rendered mock): the writer records only subagents still working at write
    time, so every roster entry the supervisor reads is one the recycle
    itself killed. The prompt says re-commission, never restart or resume,
    because resume-by-id across a recycle is impossible — probed 2026-08-29:
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
    check("ignition counts the subagents still working at the recycle",
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
          ". You may need to re-commission similar agents. If you need more "
          "context, the dead agents' full transcripts are at "
          f"{predecessor_directory}/subagents/agent-<id>.jsonl." in prompt,
          prompt)
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
    """carry_over_to_successor, with the extractor stubbed: what the recycle
    actually prints to the console, and what it actually puts in the prompt.

    Two rulings of 2026-08-29 meet here. The queue-status line is CUT from
    the ignition prompt but the console print STAYS — before this change the
    supervisor threaded queue status into every recycle prompt
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
    check("a recycle still prints the queue status to its own console",
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
    check("the recycle prompt carries no queue status",
          "Queue status" not in prompt and "queues —" not in prompt, prompt)
    check("the recycle prompt carries no task-count line",
          "task(s) are visible" not in prompt, prompt)
    check("the recycle prompt carries no launch-clock sentence",
          "The clock read" not in prompt and "never from estimate" not in prompt, prompt)
    check("the recycle prompt stamps the written-at and defers the gap to `date`",
          "written at 20" in prompt
          and "Calculate from `date` how long ago that was" in prompt, prompt)
    check("the recycle prompt carries the branch-state line the plan was composed with",
          "branch sync: composer-branch is 2 commit(s) behind main — if behind, "
          "catch up with origin/main when safe." in prompt, prompt)
    check("the recycle prompt points at the predecessor's subagent transcripts",
          f"{plan.predecessor_session_directory}/subagents/agent-<id>.jsonl" in prompt, prompt)
    check("the recycle prompt still ignites from the next step",
          "keep composing" in prompt, prompt)


with tempfile.TemporaryDirectory() as temporary_directory:
    recent_timestamp = run_offline_cases(Path(temporary_directory))
    run_branch_sync_cases(Path(temporary_directory))
    run_exit_handoff_cases(Path(temporary_directory))
    run_adoption_cases(Path(temporary_directory))
    run_dont_restart_without_a_terminal_case(Path(temporary_directory))
    run_no_seat_recycle_refusal_case(Path(temporary_directory))
    run_boot_ignition_case(Path(temporary_directory))
    run_appended_system_prompt_cases(Path(temporary_directory))
    run_first_prompt_file_cases(Path(temporary_directory))
    run_lock_cases(Path(temporary_directory))
    run_multi_line_next_step_cases(Path(temporary_directory), recent_timestamp)
    run_launch_and_retention_cases(Path(temporary_directory), recent_timestamp)
    run_spawned_subagent_roster_cases(Path(temporary_directory), recent_timestamp)
    run_recycle_prompt_composition_cases(Path(temporary_directory), recent_timestamp)

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
