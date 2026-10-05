#!/usr/bin/env python3
"""Tests for handoff-supervisor.py: what a successor is told, and what it
inherits.

The handoff file and the supervisor's state file as the supervisor reads
them; the initial agent instructions it composes, with the branch-sync,
overview-refresh and memory-review lines they carry; the dialog retention across
reincarnations; and the prompts of a boot
ignition and of a first launch. The supervisor's other cases are in
handoff-supervisor-session-launch-and-seat-lock-test.py and
handoff-supervisor-session-end-and-resume-test.py, beside this file.

Run: python3 nc-systems/handoff/tests/handoff-supervisor-successor-prompt-test.py
Add --canary to also run the two live pinned-task-list canaries, which launch
real headless sessions. Task-list pinning rides undocumented harness state; an
upgrade breaking it shows up as a successor finding its predecessor's tasks
missing (the queues are the backstop), and these two cases are the
diagnosis to run when that fires.

Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import dataclasses
import functools
import importlib.util
import inspect
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

# Before anything runs git: a run started with GIT_DIR set, or with another
# variable that redirects git, must keep this suite's git, and the git of every
# supervisor it starts, out of the repository the variable names. This suite
# sits at nc-systems/handoff/tests/, so the repository root is three
# directories up.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().parents[3] / "scripts"
    / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

_handoff_supervisor_test_fixture_spec = importlib.util.spec_from_file_location(
    "handoff_supervisor_test_fixture",
    Path(__file__).resolve().with_name("handoff-supervisor-test-fixture.py"))
fixture = importlib.util.module_from_spec(_handoff_supervisor_test_fixture_spec)
_handoff_supervisor_test_fixture_spec.loader.exec_module(fixture)

supervisor = fixture.supervisor
check = fixture.check
SCRIPT_PATH = fixture.SCRIPT_PATH
SYSTEM_DIRECTORY = fixture.SYSTEM_DIRECTORY
REPOSITORY_ROOT = fixture.REPOSITORY_ROOT
git_in = fixture.git_in
a_process_that_looks_like_a_supervisor = fixture.a_process_that_looks_like_a_supervisor
StubLaunchedSession = fixture.StubLaunchedSession
supervisor_names_replaced = fixture.supervisor_names_replaced


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
    supervisor.write_supervisor_state(state_path, {"consumed_counter": 7, "launched_session_id": "s", "generation": 3})
    check("state round-trips", supervisor.read_supervisor_state(state_path)["consumed_counter"] == 7)
    state_path.write_text("{ not json", encoding="utf-8")
    check("unreadable state starts fresh", supervisor.read_supervisor_state(state_path)["generation"] == 0)

    # --- The launched-session key, and its migration ----------------------
    # A state file written before 2026-09-21 carries the field under the bare
    # name "session_id". A supervisor reading one must come away with the same
    # value under the new name, or carry_over_to_successor sees no retiring
    # session and the seat ignites dialog-less -- losing the conversation tail
    # of every live seat on the fleet's first restart after the rename.
    legacy_state_path = workspace / "legacy-key-supervisor-state.json"
    legacy_state_path.write_text(
        json.dumps({"consumed_counter": 2, "session_id": "written-before-the-rename",
                    "generation": 5}),
        encoding="utf-8")
    migrated = supervisor.read_supervisor_state(legacy_state_path)
    check("a pre-rename state file migrates its session id to the new key",
          migrated[supervisor.LAUNCHED_SESSION_ID_STATE_KEY] == "written-before-the-rename",
          str(migrated))
    check("migrating drops the old key rather than keeping both",
          supervisor.LEGACY_SESSION_ID_STATE_KEY not in migrated, str(migrated))
    check("migrating leaves the rest of the state alone",
          migrated["consumed_counter"] == 2 and migrated["generation"] == 5, str(migrated))

    supervisor.write_supervisor_state(legacy_state_path, migrated)
    on_disk = json.loads(legacy_state_path.read_text(encoding="utf-8"))
    check("the next write persists the new key and not the old",
          supervisor.LAUNCHED_SESSION_ID_STATE_KEY in on_disk
          and supervisor.LEGACY_SESSION_ID_STATE_KEY not in on_disk, str(on_disk))

    # The new key wins when a file somehow carries both, so a half-migrated
    # file cannot resurrect a stale id.
    both_state_path = workspace / "both-keys-supervisor-state.json"
    both_state_path.write_text(
        json.dumps({"session_id": "stale", "launched_session_id": "current"}),
        encoding="utf-8")
    check("the new key wins over a leftover old one",
          supervisor.read_supervisor_state(both_state_path)[
              supervisor.LAUNCHED_SESSION_ID_STATE_KEY] == "current")

    check("a fresh state names the launched session, not a bare session",
          supervisor.LAUNCHED_SESSION_ID_STATE_KEY in supervisor.fresh_supervisor_state()
          and "session_id" not in supervisor.fresh_supervisor_state())

    # --- Heartbeat and liveness ------------------------------------------
    heartbeat_state_path = workspace / "heartbeat-supervisor-state.json"
    alive, explanation = supervisor.supervisor_liveness(heartbeat_state_path)
    check(
        "no state file reads as no supervisor",
        not alive and "no supervisor state" in explanation,
        explanation,
    )

    heartbeat_lock_path = workspace / "heartbeat-supervisor.lock"

    supervisor.write_supervisor_state(heartbeat_state_path, {"launched_session_id": "s"})
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
    supervisor.stamp_heartbeat(heartbeat_state_path, {"launched_session_id": "s"})
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
        supervisor.stamp_heartbeat(heartbeat_state_path, {"launched_session_id": "s"})
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
         "--agent-command", str(stub_agent), "--agent-update-timeout-seconds", "0",
         "--first-prompt-file", str(workspace / "no-such-prompt.txt")],
        capture_output=True, text=True, check=False, timeout=30,
    )
    check("a missing first-prompt file is refused before launch",
          result.returncode == 2 and "does not exist" in result.stderr, result.stderr[-200:])

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", "promptcase", "--cd", str(workspace),
         "--handoff-dir", str(workspace / "prompt-handoffs"),
         "--agent-command", str(stub_agent), "--agent-update-timeout-seconds", "0",
         "--first-prompt-file", str(prompt_path)],
        capture_output=True, text=True, check=False, timeout=30,
    )
    check("a first-prompt file launches cleanly", result.returncode == 0, result.stderr[-200:])


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
    # instruction that seats act on at once.
    check("the branch-state instruction is word for word what the user ruled",
          supervisor.BRANCH_STATE_INSTRUCTION == (
              " \u2014 If this branch has never been pushed, rebase it onto origin/main "
              "before your first substantive action and rerun the tests for what you "
              "touched. If it is pushed, leave it as it is, and start new work on a "
              "branch from origin/main. If this seat has "
              "open pull requests, check their state with `gh`: merge-lane-2 reviews "
              "and merges them; when one has a review with findings, dispatch a forked "
              "subagent to fix it \u2014 never extend a head you've already pushed. When one conflicts with main, clear the conflict with the hand-merge that scripts/branch-conflict-check.py describes."),
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
              "from origin/main. If this seat has "
              "open pull requests, check their state with `gh`: merge-lane-2 reviews "
              "and merges them; when one has a review with findings, dispatch a "
              "forked subagent to fix it — never extend a head you've already pushed. When one conflicts with main, clear the conflict with the hand-merge that scripts/branch-conflict-check.py describes.",
              expected_rest_after_the_branch_state_line),
          "rest after the pinned line: "
          + repr(synced_prompt.split("branch-conflict-check.py describes.", 1)[-1])
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
              "start new work on a branch from origin/main. If this seat has open "
              "pull requests, check their state with `gh`: merge-lane-2 reviews and "
              "merges them; when one has a review with findings, dispatch a forked "
              "subagent to fix it — never extend a head you've already pushed. When one conflicts with main, clear the conflict with the hand-merge that scripts/branch-conflict-check.py describes."),
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
    task_directory = Path.home() / ".claude" / "tasks" / pinned_list_id
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


# The overview-refresh-due instruction, word for word. A template: the
# overview, its draft, the command and the commit are filled in per system.
# The subagent writes a draft in the wiki's queue directory, and the seat
# writes the overview only once the user has approved the diff: the
# instruction-file guard refuses an agent's write to a wiki page without the
# user's approval, and a subagent cannot ask him for it. The draft has a name
# of its own, the overview's with a -draft ending, so the file-name collision
# hook has nothing to say about it. Once the user has been shown the diff the
# seat marks the day's reminder as given, which keeps the line from every
# other seat until the next day.
EXPECTED_OVERVIEW_REFRESH_DUE_INSTRUCTION_TEMPLATE = (
    " — Dispatch a subagent to write {overview_draft_path}: a copy of "
    "{overview_path} refreshed against the commits "
    "`{commit_listing_command}` lists, as "
    "docs/issues/670-refresh-design-when-a-system-s-code-lands.md defines a "
    "refresh, with the pinned line "
    "`{landing_pin_prefix}{main_commit}](<commit url>) on <YYYY-MM-DD> — "
    "<what landed>` appended. When the subagent reports, show the user the "
    "diff between {overview_path} and {overview_draft_path}. Once the user "
    "has been shown the diff, run `python3 {reminder_mark_script} {system}`. "
    "When the user approves the diff, write {overview_path} from "
    "{overview_draft_path} and delete {overview_draft_path}."
)

DAILY_OVERVIEW_REFRESH_REMINDER_MARK_SCRIPT_PATH = (
    SYSTEM_DIRECTORY / "daily-overview-refresh-reminder-mark.py")

# The line a successor is given when the day's reminder marks cannot be read,
# word for word. A template: the marks' location and the error are filled in.
EXPECTED_OVERVIEW_REFRESH_REMINDER_MARKS_UNREAD_TEMPLATE = (
    "overview check could not read the day's reminder marks in {marks_location}, "
    "so no line is withheld for a reminder already given: {error}"
    " — Before you act on any overview-refresh line in this prompt, tell the "
    "user that the handoff-supervisor could not read the day's overview-refresh "
    "reminder marks, giving the location {marks_location} and the error above, "
    "and that an overview-refresh line in this prompt may therefore repeat a "
    "refresh the user was already shown today."
)

# Appended to that line only when ned-box gave no answer, word for word.
EXPECTED_OVERVIEW_REFRESH_REMINDER_MARKS_NED_BOX_DID_NOT_ANSWER_SENTENCE = (
    " Because ned-box did not answer this machine, also tell the user that "
    "`ssh nedlern@ned-box true`, run on the Mac, shows whether ned-box answers "
    "again, and that the next agent-session's start reads the marks again."
)

REMINDER_MARKS_UNREAD_LINE_OPENING = "overview check could not read the day's reminder marks in "


def expected_overview_refresh_due_line(system: str, pinned: str, main: str,
                                       count: int) -> str:
    """The whole line for a fixture system, spelled out, so a change to the
    report, the template, a command or where the draft goes fails the pin."""
    overview = f"docs/nedschorus-wiki/nedschorus-{system}-system-overview.md"
    draft = f"docs/nedschorus-wiki/queue/nedschorus-{system}-system-overview-draft.md"
    return (
        f"overview refresh due: {system} — {count} commit(s) under nc-systems/{system}/ "
        f"since its overview's pinned commit, in {pinned}..{main} — Dispatch a "
        f"subagent to write {draft}: a copy of {overview} refreshed "
        f"against the commits `git log --no-merges {pinned}..{main} -- nc-systems/{system}/ "
        f"':(exclude)nc-systems/{system}/*.md'` lists, as "
        "docs/issues/670-refresh-design-when-a-system-s-code-lands.md defines a "
        "refresh, with the pinned line `**Pinned to what landed:** "
        f"commit [{main}](<commit url>) on <YYYY-MM-DD> — <what landed>` appended. "
        f"When the subagent reports, show the user the diff between {overview} and "
        f"{draft}. Once the user has been shown the diff, run `python3 "
        f"{DAILY_OVERVIEW_REFRESH_REMINDER_MARK_SCRIPT_PATH} {system}`. When the user "
        f"approves the diff, write {overview} from {draft} and delete {draft}.")


def expected_widget_overview_refresh_due_line(pinned: str, main: str, count: int) -> str:
    """The whole line for the fixture system `widget`."""
    return expected_overview_refresh_due_line("widget", pinned, main, count)


def overview_refresh_due_or_missing(directory: Path, now=None):
    """overview_refresh_due_lines's result, or the string "missing" against a
    supervisor that has no such function, so each case FAILS cleanly there
    instead of crashing the suite. now, when given, is the moment whose day
    the once-a-day cases judge."""
    due = getattr(supervisor, "overview_refresh_due_lines", None)
    if due is None:
        return "missing"
    if now is None:
        return due(directory)
    if "now" not in inspect.signature(due).parameters:
        return "missing"
    return due(directory, now=now)


def write_gh_answering_no_open_pull_requests(directory: Path) -> Path:
    """Write into directory a fake `gh` that answers an empty list of open pull
    requests, and return directory, for the front of PATH. A case whose system
    is due reaches the supervisor's `gh pr list`; with this first on PATH it
    never asks the real GitHub."""
    directory.mkdir()
    fake_gh = directory / "gh"
    fake_gh.write_text("#!/bin/sh\nprintf '[]\\n'\n", encoding="utf-8")
    fake_gh.chmod(0o755)
    return directory


@contextlib.contextmanager
def gh_answering_no_open_pull_requests_first_on_path(directory: Path):
    original_path = os.environ.get("PATH", "")
    os.environ["PATH"] = (f"{write_gh_answering_no_open_pull_requests(directory)}"
                          f"{os.pathsep}{original_path}")
    try:
        yield
    finally:
        os.environ["PATH"] = original_path


def run_overview_refresh_due_cases(workspace: Path):
    """overview_refresh_due_lines against real repositories, one fixture
    repository whose origin/main is moved by hand the way the branch sync's
    fetch would move it.

    Ruled 2026-09-23 (item 14 of the walk
    what-a-design-becomes-when-its-code-lands-2026-09-22): when a system's
    code under nc-systems/<system>/ has moved on main past the commit pinned
    in its overview, the successor's first prompt says so beside the
    branch-sync line. The cases the build was asked for: moved past (the line,
    naming the system and the range), current (no line), no pin (skipped, no
    error), and a pin naming a commit the repository does not hold, which the
    pinned-line reader's rule counts as no pin.
    """
    root = workspace / "overview-refresh-due"
    root.mkdir()
    check("a directory that is not a checkout reports no overview refresh",
          overview_refresh_due_or_missing(root) == (),
          repr(overview_refresh_due_or_missing(root)))

    repository = root / "repository"
    repository.mkdir()
    git_in(["init", "--quiet", "--initial-branch=main"], repository)
    git_in(["config", "user.name", "fixture"], repository)
    git_in(["config", "user.email", "fixture@nedschorus.invalid"], repository)

    def commit(texts_by_path, message):
        for relative, text in texts_by_path.items():
            path = repository / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        git_in(["add", "-A"], repository)
        git_in(["commit", "--quiet", "-m", message], repository)
        return git_in(["rev-parse", "HEAD"], repository).stdout.strip()

    def publish():
        # What the branch sync's fetch leaves behind: origin/main at this commit.
        git_in(["update-ref", "refs/remotes/origin/main", "HEAD"], repository)
        return git_in(["rev-parse", "--short", "HEAD"], repository).stdout.strip()

    def pinned_line(sha):
        # As every pinned line on main writes it: seven hex characters in the
        # brackets and the full sha in the link.
        return (f"**Pinned to what landed:** commit [{sha[:7]}]"
                f"(https://github.com/nedschorus/nedschorus/commit/{sha}) on "
                "2026-09-28 — the widget as it landed.")

    widget_overview = "docs/nedschorus-wiki/nedschorus-widget-system-overview.md"
    landed = commit({"nc-systems/widget/widget.py": "print('widget')\n"}, "the widget lands")
    commit({widget_overview: "# The widget: an overview\n\nIt widgets.\n\n"
            + pinned_line(landed) + "\n"}, "the widget's overview, pinned")

    check("a repository with no origin/main reports no overview refresh",
          overview_refresh_due_or_missing(repository) == (),
          repr(overview_refresh_due_or_missing(repository)))

    publish()
    check("a system whose overview is pinned to its last code commit gets no line",
          overview_refresh_due_or_missing(repository) == (),
          repr(overview_refresh_due_or_missing(repository)))

    # The seat's own branch carrying a commit main does not have: what landed
    # is what a refresh follows, so an unlanded commit makes nothing due.
    commit({"nc-systems/widget/widget.py": "print('unlanded')\n"}, "the seat's own work")
    check("a commit on the seat's branch that main does not have makes nothing due",
          overview_refresh_due_or_missing(repository) == (),
          repr(overview_refresh_due_or_missing(repository)))
    git_in(["reset", "--quiet", "--hard", "HEAD~1"], repository)

    # A refresh appends its pinned line to the design, and the design lives
    # under nc-systems/<system>/: were Markdown there counted, every refresh's
    # own commit would make the overview due again, forever.
    commit({"nc-systems/widget/widget-design.md": "# Design\n\n" + pinned_line(landed) + "\n",
            "nc-systems/widget/tests/widget-notes.md": "notes\n"},
           "the widget's design is pinned, and a note beside its tests")
    publish()
    check("a commit that changes only Markdown under the system makes nothing due",
          overview_refresh_due_or_missing(repository) == (),
          repr(overview_refresh_due_or_missing(repository)))

    grown = commit({"nc-systems/widget/widget.py": "print('widget, grown')\n"},
                   "the widget grows")
    main = publish()
    expected = expected_widget_overview_refresh_due_line(landed[:7], main, 1)
    due = overview_refresh_due_or_missing(repository)
    check("a system whose code moved past its overview's pinned commit gets one line, "
          "naming the system and the range, exactly",
          due == (expected,), f"{due!r}\nexpected: {expected!r}")
    listed = git_in(["log", "--no-merges", "--format=%H", f"{landed[:7]}..{main}", "--",
                     "nc-systems/widget/", ":(exclude)nc-systems/widget/*.md"],
                    repository).stdout.split()
    check("the command the line hands the successor lists exactly the commit that moved",
          listed == [grown], str(listed))

    # Systems that are skipped, beside the one that is due. gadget's overview
    # names its commit only in prose, the form the handoff overview used before
    # its pinned line; sprocket has no overview; gizmo's pinned line names a
    # well-formed sha this repository holds no commit for, and a pinned line
    # counts only when its commit resolves.
    absent = "abc1234"
    commit({"nc-systems/gadget/gadget.py": "print('gadget')\n",
            "docs/nedschorus-wiki/nedschorus-gadget-system-overview.md":
                f"# The gadget\n\nChecked against the code at commit [{landed[:7]}] "
                "on 2026-09-28.\n",
            "nc-systems/sprocket/sprocket.py": "print('sprocket')\n",
            "nc-systems/gizmo/gizmo.py": "print('gizmo')\n",
            "docs/nedschorus-wiki/nedschorus-gizmo-system-overview.md":
                "# The gizmo\n\n" + f"**Pinned to what landed:** commit [{absent}]"
                f"(https://github.com/nedschorus/nedschorus/commit/{absent}) on "
                "2026-09-28 — the gizmo.\n"},
           "three systems land, none with a pinned line that counts")
    main = publish()
    expected = expected_widget_overview_refresh_due_line(landed[:7], main, 1)
    due = overview_refresh_due_or_missing(repository)
    check("systems whose overview has no pinned line, or no overview at all, are "
          "skipped without error",
          due == (expected,), f"{due!r}\nexpected: {expected!r}")
    # The first condition proves the fixture holds no commit by that name.
    absent_names_no_commit = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", absent + "^{commit}"],
        cwd=str(repository), capture_output=True, check=False).returncode != 0
    check("a pinned line naming a commit the repository does not hold counts as no pin",
          absent_names_no_commit and due != "missing"
          and not any("gizmo" in line for line in due),
          repr(due))

    # Each refresh appends a pinned line, so the last one is the overview's pin.
    commit({widget_overview: "# The widget: an overview\n\nIt widgets.\n\n"
            + pinned_line(landed) + "\n\n" + pinned_line(grown) + "\n"},
           "the widget's overview is refreshed and pinned again")
    publish()
    check("of several pinned lines, the last is the overview's pin",
          overview_refresh_due_or_missing(repository) == (),
          repr(overview_refresh_due_or_missing(repository)))

    # The two failures the round-1 reviews of the pull request that built this
    # asked about (2026-09-28). The widget moves again first, so a line is due
    # and each failure has something to lose.
    commit({"nc-systems/widget/widget.py": "print('widget, grown again')\n"},
           "the widget grows again")
    main = publish()
    expected = expected_widget_overview_refresh_due_line(grown[:7], main, 1)
    due = overview_refresh_due_or_missing(repository)
    check("a system that moves past its latest pin is due again",
          due == (expected,), f"{due!r}\nexpected: {expected!r}")

    # origin/main verified but its short name unreadable: an empty name would
    # make the range `<pinned>..`, which git reads against the seat's HEAD.
    real_run_git_here = supervisor.run_git_here

    def run_git_here_that_cannot_name_a_commit(arguments, working_directory, timeout=60):
        if arguments[0] == "rev-parse" and "--short" in arguments:
            return subprocess.CompletedProcess(arguments, 1, "", "stub: timed out")
        return real_run_git_here(arguments, working_directory, timeout=timeout)

    supervisor.run_git_here = run_git_here_that_cannot_name_a_commit
    try:
        due = overview_refresh_due_or_missing(repository)
    finally:
        supervisor.run_git_here = real_run_git_here
    check("when origin/main's commit cannot be named, no line is given, never a "
          "range read against the seat's HEAD",
          due == (), repr(due))

    # A read of one system's overview that hangs. aardvark sorts before widget,
    # so ending the loop there would lose widget's line.
    commit({"nc-systems/aardvark/aardvark.py": "print('aardvark')\n"}, "the aardvark lands")
    main = publish()
    expected = expected_widget_overview_refresh_due_line(grown[:7], main, 1)
    real_git = shutil.which("git")
    stub_directory = root / "git-that-hangs-on-one-overview"
    stub_directory.mkdir()
    stub_git = stub_directory / "git"
    stub_git.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        '  *"show origin/main:docs/nedschorus-wiki/nedschorus-aardvark-system-overview.md"*)\n'
        "    exec sleep 30 ;;\n"
        "esac\n"
        f'exec "{real_git}" "$@"\n',
        encoding="utf-8")
    stub_git.chmod(0o755)

    # The supervisor gives every git call in the check the same timeout, so a
    # timeout short enough to end the hang quickly also ends a slow rev-parse,
    # ls-tree or widget read on a loaded machine, and the check then returns
    # () with nothing on the console. Only the hung read keeps the short one.
    class SubprocessWhereOnlyTheHungReadTimesOutQuickly:
        def __getattr__(self, name):
            return getattr(subprocess, name)

        def run(self, arguments, *positional, **keywords):
            if "timeout" in keywords and not any(
                    "nedschorus-aardvark-system-overview.md" in str(argument)
                    for argument in arguments):
                keywords["timeout"] = 60
            return subprocess.run(arguments, *positional, **keywords)

    original_path = os.environ.get("PATH", "")
    had_timeout = hasattr(supervisor, "OVERVIEW_REFRESH_CHECK_GIT_TIMEOUT_SECONDS")
    original_timeout = getattr(supervisor, "OVERVIEW_REFRESH_CHECK_GIT_TIMEOUT_SECONDS", None)
    supervisor.OVERVIEW_REFRESH_CHECK_GIT_TIMEOUT_SECONDS = 1
    real_supervisor_subprocess = supervisor.subprocess
    supervisor.subprocess = SubprocessWhereOnlyTheHungReadTimesOutQuickly()
    console = io.StringIO()
    os.environ["PATH"] = f"{stub_directory}{os.pathsep}{original_path}"
    try:
        with contextlib.redirect_stdout(console):
            due = overview_refresh_due_or_missing(repository)
    finally:
        os.environ["PATH"] = original_path
        supervisor.subprocess = real_supervisor_subprocess
        if had_timeout:
            supervisor.OVERVIEW_REFRESH_CHECK_GIT_TIMEOUT_SECONDS = original_timeout
        else:
            del supervisor.OVERVIEW_REFRESH_CHECK_GIT_TIMEOUT_SECONDS
    check("a read of one system's overview that times out passes over that system "
          "only, and a later system that is due still gets its line",
          due == (expected,), f"{due!r}\nexpected: {expected!r}\n{console.getvalue()}")
    check("the system passed over is named on the console with the cause",
          "handoff-supervisor: overview check for aardvark passed over: TimeoutExpired"
          in console.getvalue(), console.getvalue())


def run_overview_refresh_withheld_while_pull_request_open_cases(workspace: Path):
    """A due system's line is withheld while an open pull request already
    changes its overview, and given as before when GitHub cannot be asked.

    Ruled 2026-09-29 (item 11 of the walk open-items-this-seat-holds-2026-09-24,
    "y"): the refresh does nothing while an open pull request already refreshes
    that overview. A fake `gh` on PATH answers each case and records every call.
    """
    root = workspace / "overview-refresh-withheld"
    root.mkdir()
    repository = root / "repository"
    repository.mkdir()
    git_in(["init", "--quiet", "--initial-branch=main"], repository)
    git_in(["config", "user.name", "fixture"], repository)
    git_in(["config", "user.email", "fixture@nedschorus.invalid"], repository)

    def commit(texts_by_path, message):
        for relative, text in texts_by_path.items():
            path = repository / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        git_in(["add", "-A"], repository)
        git_in(["commit", "--quiet", "-m", message], repository)
        return git_in(["rev-parse", "HEAD"], repository).stdout.strip()

    def publish():
        git_in(["update-ref", "refs/remotes/origin/main", "HEAD"], repository)
        return git_in(["rev-parse", "--short", "HEAD"], repository).stdout.strip()

    def pinned_line(sha, system):
        return (f"**Pinned to what landed:** commit [{sha[:7]}]"
                f"(https://github.com/nedschorus/nedschorus/commit/{sha}) on "
                f"2026-09-28 — the {system} as it landed.")

    fake_gh_count = [0]

    def due_with_a_fake_gh(body, gh_timeout=None, without_gh=False):
        """overview_refresh_due_lines's result, its console, and the calls the
        fake `gh` recorded. body is the fake's shell after it records the call.
        without_gh puts only git on PATH, so no `gh` is found at all."""
        fake_gh_count[0] += 1
        directory = root / f"fake-gh-{fake_gh_count[0]}"
        directory.mkdir()
        calls = directory / "calls"
        if without_gh:
            # python3 too: the day's reminder marks are read through it.
            for program in ("git", "python3"):
                (directory / program).symlink_to(shutil.which(program))
            search_path = str(directory)
        else:
            fake_gh = directory / "gh"
            fake_gh.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$*" >> "' + str(calls) + '"\n' + body + "\n",
                encoding="utf-8")
            fake_gh.chmod(0o755)
            search_path = f"{directory}{os.pathsep}{os.environ.get('PATH', '')}"
        original_path = os.environ.get("PATH", "")
        had_timeout = hasattr(supervisor, "OVERVIEW_REFRESH_CHECK_GH_TIMEOUT_SECONDS")
        original_timeout = getattr(supervisor, "OVERVIEW_REFRESH_CHECK_GH_TIMEOUT_SECONDS", None)
        if gh_timeout is not None:
            supervisor.OVERVIEW_REFRESH_CHECK_GH_TIMEOUT_SECONDS = gh_timeout
        console = io.StringIO()
        os.environ["PATH"] = search_path
        try:
            with contextlib.redirect_stdout(console):
                due = overview_refresh_due_or_missing(repository)
        finally:
            os.environ["PATH"] = original_path
            if had_timeout:
                supervisor.OVERVIEW_REFRESH_CHECK_GH_TIMEOUT_SECONDS = original_timeout
            elif hasattr(supervisor, "OVERVIEW_REFRESH_CHECK_GH_TIMEOUT_SECONDS"):
                del supervisor.OVERVIEW_REFRESH_CHECK_GH_TIMEOUT_SECONDS
        recorded = calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []
        return due, console.getvalue(), recorded

    def gh_answering(pull_requests):
        answer = root / f"answer-{uuid.uuid4().hex}.json"
        answer.write_text(json.dumps(pull_requests), encoding="utf-8")
        return f"cat '{answer}'"

    widget_overview = "docs/nedschorus-wiki/nedschorus-widget-system-overview.md"
    gadget_overview = "docs/nedschorus-wiki/nedschorus-gadget-system-overview.md"
    landed = commit({"nc-systems/widget/widget.py": "print('widget')\n"}, "the widget lands")
    commit({widget_overview: "# The widget\n\n" + pinned_line(landed, "widget") + "\n"},
           "the widget's overview, pinned")
    publish()

    due, console, calls = due_with_a_fake_gh(gh_answering([]))
    check("when no system is due, gh is never asked",
          due == () and calls == [], f"{due!r} {calls!r}\n{console}")

    commit({"nc-systems/widget/widget.py": "print('widget, grown')\n"}, "the widget grows")
    main = publish()
    expected = expected_widget_overview_refresh_due_line(landed[:7], main, 1)
    refresh_title = "The widget overview is refreshed against what landed"
    refresh_url = "https://github.com/nedschorus/nedschorus/pull/9001"

    due, console, calls = due_with_a_fake_gh(gh_answering([
        {"url": refresh_url, "title": refresh_title,
         "files": [{"path": widget_overview}, {"path": "nc-systems/widget/widget-design.md"}]}]))
    check("a due system whose overview an open pull request changes gets no line",
          due == (), f"{due!r}\n{console}")
    check("the console names the system and the open pull request that changes its "
          "overview",
          f"handoff-supervisor: overview check for widget withheld its line: the open "
          f"pull request \"{refresh_title}\" ({refresh_url}) already changes "
          f"{widget_overview}" in console, console)
    check("gh is asked once, for the open pull requests and the files each changes",
          calls == ["pr list --repo nedschorus/nedschorus --state open "
                    "--json url,title,files --limit 200"], repr(calls))

    due, console, calls = due_with_a_fake_gh(gh_answering([
        {"url": refresh_url, "title": "The widget grows a second handle",
         "files": [{"path": "nc-systems/widget/widget.py"},
                   {"path": "docs/nedschorus-wiki/nedschorus-glossary.md"}]}]))
    check("an open pull request that changes other files only leaves the line given",
          due == (expected,), f"{due!r}\nexpected: {expected!r}\n{console}")

    due, console, calls = due_with_a_fake_gh(
        "echo 'gh: To get started with GitHub CLI, please run:  gh auth login' >&2\n"
        "echo 'second line of complaint' >&2\nexit 4")
    check("when gh exits nonzero, the line is given",
          due == (expected,), f"{due!r}\nexpected: {expected!r}\n{console}")
    check("when gh exits nonzero, the console says so, with gh's first line",
          "handoff-supervisor: overview check could not ask GitHub which open pull "
          "requests change an overview, so no line is withheld for a pull request: "
          "gh exited 4: "
          "gh: To get started with GitHub CLI, please run:  gh auth login\n" in console,
          console)

    due, console, calls = due_with_a_fake_gh("", without_gh=True)
    check("when gh is absent, the line is given",
          due == (expected,), f"{due!r}\nexpected: {expected!r}\n{console}")
    check("when gh is absent, the console says so",
          "so no line is withheld for a pull request: FileNotFoundError" in console,
          console)

    due, console, calls = due_with_a_fake_gh("echo 'this is not json'")
    check("when gh's output does not parse, the line is given and the console says so",
          due == (expected,)
          and "so no line is withheld for a pull request: JSONDecodeError" in console,
          f"{due!r}\nexpected: {expected!r}\n{console}")

    due, console, calls = due_with_a_fake_gh("exec sleep 30", gh_timeout=1)
    check("when gh times out, the line is given and the console says so",
          due == (expected,)
          and "so no line is withheld for a pull request: TimeoutExpired" in console,
          f"{due!r}\nexpected: {expected!r}\n{console}")

    # Two systems due, one of them with an open pull request changing its
    # overview: only the other system's line is given.
    gadget_landed = commit({"nc-systems/gadget/gadget.py": "print('gadget')\n"},
                           "the gadget lands")
    commit({gadget_overview: "# The gadget\n\n" + pinned_line(gadget_landed, "gadget") + "\n"},
           "the gadget's overview, pinned")
    commit({"nc-systems/gadget/gadget.py": "print('gadget, grown')\n"}, "the gadget grows")
    main = publish()
    expected = expected_widget_overview_refresh_due_line(landed[:7], main, 1)
    gadget_title = "The gadget overview is refreshed against what landed"
    gadget_url = "https://github.com/nedschorus/nedschorus/pull/9002"
    due, console, calls = due_with_a_fake_gh(gh_answering([
        {"url": gadget_url, "title": gadget_title, "files": [{"path": gadget_overview}]}]))
    check("of two due systems, only the one whose overview no open pull request "
          "changes gets its line",
          due == (expected,), f"{due!r}\nexpected: {expected!r}\n{console}")
    check("the console names the system whose line was withheld, and its pull request",
          f"overview check for gadget withheld its line: the open pull request "
          f"\"{gadget_title}\" ({gadget_url})" in console
          and "overview check for widget withheld" not in console, console)


def run_overview_refresh_once_a_day_cases(workspace: Path):
    """A due system's line is given once a day, to whichever seat reincarnates
    first that day, on either machine.

    Ruled 2026-10-01, the user's "y" to the merge-lane-2 seat, recorded at
    https://github.com/nedschorus/nedschorus/pull/852#issuecomment-5939116857:
    "one reminder a day for each overview that is behind, from whichever seat
    starts up first that day; the other seats stay quiet until the next day."
    The day's reminder is a mark in the log-store, one per system, which the
    seat writes once the user has been shown the diff.

    No case reaches ned-box. The marks directory is a fixture directory, set
    through daily_overview_refresh_reminder_mark's constant; ned-box is played
    by an ssh first on PATH that records the host of each call and runs its
    body; the machine is named per case; a fake `gh` answers for GitHub; and
    the moment is passed in.
    """
    root = workspace / "overview-refresh-once-a-day"
    root.mkdir()
    repository = root / "repository"
    repository.mkdir()
    git_in(["init", "--quiet", "--initial-branch=main"], repository)
    git_in(["config", "user.name", "fixture"], repository)
    git_in(["config", "user.email", "fixture@nedschorus.invalid"], repository)

    def commit(texts_by_path, message):
        for relative, text in texts_by_path.items():
            path = repository / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        git_in(["add", "-A"], repository)
        git_in(["commit", "--quiet", "-m", message], repository)
        return git_in(["rev-parse", "HEAD"], repository).stdout.strip()

    def publish():
        git_in(["update-ref", "refs/remotes/origin/main", "HEAD"], repository)
        return git_in(["rev-parse", "--short", "HEAD"], repository).stdout.strip()

    def pinned_line(sha, system):
        return (f"**Pinned to what landed:** commit [{sha[:7]}]"
                f"(https://github.com/nedschorus/nedschorus/commit/{sha}) on "
                f"2026-09-28 — the {system} as it landed.")

    reminder_mark = getattr(supervisor, "daily_overview_refresh_reminder_mark", None)
    marks_directory = root / "daily-overview-refresh-reminder-marks"
    no_open_pull_requests = write_gh_answering_no_open_pull_requests(
        root / "gh-answering-no-open-pull-requests")
    fake_count = [0]

    def fake_gh_running(body) -> Path:
        """A directory holding a fake `gh` whose shell is body."""
        fake_count[0] += 1
        directory = root / f"fake-gh-{fake_count[0]}"
        directory.mkdir()
        (directory / "gh").write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
        (directory / "gh").chmod(0o755)
        return directory

    def gh_answering(pull_requests) -> Path:
        answer = root / f"answer-{uuid.uuid4().hex}.json"
        answer.write_text(json.dumps(pull_requests), encoding="utf-8")
        return fake_gh_running(f"cat '{answer}'")

    @contextlib.contextmanager
    def reminder_marks_in_place(ssh_body=SSH_THAT_RUNS_THE_COMMAND_HERE,
                                hostname="a-mac-that-is-not-ned-box", read_timeout=None,
                                gh_directory=no_open_pull_requests):
        """Yields the file the fake ssh records its calls' hosts in."""
        fake_count[0] += 1
        directory = root / f"fake-ssh-{fake_count[0]}"
        directory.mkdir()
        calls = directory / "calls"
        fake_ssh = directory / "ssh"
        fake_ssh.write_text(
            '#!/bin/sh\nwhile [ "$1" = "-o" ]; do shift 2; done\n'
            'printf "%s\\n" "$1" >> "' + str(calls) + '"\nshift\n' + ssh_body + "\n",
            encoding="utf-8")
        fake_ssh.chmod(0o755)
        missing = object()
        saved = []

        def replace(owner, name, value):
            saved.append((owner, name, getattr(owner, name, missing)))
            setattr(owner, name, value)

        if reminder_mark is not None:
            replace(reminder_mark, "DAILY_OVERVIEW_REFRESH_REMINDER_MARKS_DIRECTORY",
                    str(marks_directory))
            replace(reminder_mark, "ssh_target_for_this_machine",
                    fixture.SSH_TARGET_FOR_THIS_MACHINE_UNPATCHED)
        if read_timeout is not None:
            replace(supervisor, "OVERVIEW_REFRESH_REMINDER_MARKS_READ_TIMEOUT_SECONDS",
                    read_timeout)
        replace(socket, "gethostname", lambda: hostname)
        original_path = os.environ.get("PATH", "")
        os.environ["PATH"] = (f"{directory}{os.pathsep}{gh_directory}{os.pathsep}"
                              f"{original_path}")
        try:
            yield calls
        finally:
            os.environ["PATH"] = original_path
            for owner, name, value in reversed(saved):
                if value is missing:
                    delattr(owner, name)
                else:
                    setattr(owner, name, value)

    def due_at(now, **in_place_options):
        """overview_refresh_due_lines's result at now, its console, and the
        hosts the fake ssh was called for."""
        console = io.StringIO()
        with reminder_marks_in_place(**in_place_options) as calls, \
                contextlib.redirect_stdout(console):
            due = overview_refresh_due_or_missing(repository, now=now)
        recorded = calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []
        return due, console.getvalue(), recorded

    def mark_as_the_seat_would(system, now, hostname="a-mac-that-is-not-ned-box"):
        """Write the day's mark with the mark program itself."""
        if reminder_mark is None:
            return
        with reminder_marks_in_place(hostname=hostname), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            reminder_mark.main([system], now=now)

    def mark_citation(file_name):
        return f"nedlern@ned-box:{marks_directory}/{file_name}"

    # 2026-10-01 in America/Los_Angeles is PDT, UTC-7.
    morning = datetime(2026, 10, 1, 16, 0, tzinfo=timezone.utc)            # 09:00 Pacific
    an_hour_later = datetime(2026, 10, 1, 17, 0, tzinfo=timezone.utc)      # 10:00 Pacific
    late_that_evening = datetime(2026, 10, 2, 5, 0, tzinfo=timezone.utc)   # 22:00 Pacific,
    #                                                 already 2026-10-02 in UTC and in Tokyo
    early_the_next_day = datetime(2026, 10, 2, 8, 0, tzinfo=timezone.utc)  # 01:00 Pacific

    widget_overview = "docs/nedschorus-wiki/nedschorus-widget-system-overview.md"
    gadget_overview = "docs/nedschorus-wiki/nedschorus-gadget-system-overview.md"
    widget_landed = commit({"nc-systems/widget/widget.py": "print('widget')\n"},
                           "the widget lands")
    gadget_landed = commit({"nc-systems/gadget/gadget.py": "print('gadget')\n"},
                           "the gadget lands")
    commit({widget_overview: "# The widget\n\n" + pinned_line(widget_landed, "widget") + "\n",
            gadget_overview: "# The gadget\n\n" + pinned_line(gadget_landed, "gadget") + "\n"},
           "both overviews, pinned")
    publish()

    due, console, calls = due_at(morning)
    check("when no system is due, the day's reminder marks are never read",
          due == () and calls == [], f"{due!r} {calls!r}\n{console}")

    commit({"nc-systems/widget/widget.py": "print('widget, grown')\n",
            "nc-systems/gadget/gadget.py": "print('gadget, grown')\n"}, "both grow")
    main = publish()
    widget_line = expected_overview_refresh_due_line("widget", widget_landed[:7], main, 1)
    gadget_line = expected_overview_refresh_due_line("gadget", gadget_landed[:7], main, 1)

    due, console, calls = due_at(morning)
    check("the first seat of the day is given each due system's line, before noon as after",
          due == (gadget_line, widget_line),
          f"{due!r}\nexpected: {(gadget_line, widget_line)!r}\n{console}")
    check("from the Mac, the day's reminder marks are read once, over ssh to nedlern@ned-box",
          calls == ["nedlern@ned-box"], repr(calls))
    check("with no mark for today, nothing is withheld and the console says nothing of marks",
          "withheld" not in console and "reminder mark" not in console, console)

    # The seat runs the mark program once the user has been shown the diff.
    mark_as_the_seat_would("widget", morning + timedelta(minutes=5))
    widget_mark = marks_directory / "2026-10-01-widget.txt"
    check("the mark the seat writes for a system is today's file for that system",
          widget_mark.is_file()
          and widget_mark.read_text(encoding="utf-8") == "2026-10-01T16:05:00Z\n",
          repr(sorted(path.name for path in marks_directory.iterdir())
               if marks_directory.is_dir() else None))

    due, console, calls = due_at(an_hour_later)
    check("a later seat the same day is not given the line of a system whose mark is "
          "today's, and is given the other system's line",
          due == (gadget_line,), f"{due!r}\nexpected: {(gadget_line,)!r}\n{console}")
    check("the console says why the line was withheld, naming the mark and its time",
          "handoff-supervisor: overview check for widget withheld its line: the user was "
          "shown this overview's refresh today, at 2026-10-01T16:05:00Z, as "
          f"{mark_citation('2026-10-01-widget.txt')} records\n" in console
          and "overview check for gadget withheld" not in console, console)

    with local_time_zone("Asia/Tokyo"):
        due, console, calls = due_at(late_that_evening)
    check("the day is the Pacific date: late that evening, already tomorrow in UTC and in "
          "the machine's own zone, the line stays withheld",
          due == (gadget_line,), f"{due!r}\n{console}")

    due, console, calls = due_at(early_the_next_day)
    check("the next day the first seat is given the line again: a mark from the day "
          "before does not withhold",
          due == (gadget_line, widget_line) and "withheld" not in console,
          f"{due!r}\n{console}")

    # At least once a day decides every failure: marks that cannot be read
    # withhold nothing.
    due, console, calls = due_at(
        an_hour_later,
        ssh_body="echo 'ssh: connect to host ned-box port 22: No route to host' >&2\n"
                 "echo 'second line' >&2\nexit 255")
    unreachable_line = EXPECTED_OVERVIEW_REFRESH_REMINDER_MARKS_UNREAD_TEMPLATE.format(
        marks_location=mark_citation(""),
        error="DailyMemoryReviewReadOrWriteFailed: ssh nedlern@ned-box exited 255: ssh: "
              "connect to host ned-box port 22: No route to host"
    ) + EXPECTED_OVERVIEW_REFRESH_REMINDER_MARKS_NED_BOX_DID_NOT_ANSWER_SENTENCE
    check("when ned-box cannot be reached, every due line is given, the marked system's "
          "too, and after them one line saying what could not be read, with ssh's first "
          "line, for the successor to tell the user",
          due == (gadget_line, widget_line, unreachable_line),
          f"{due!r}\nexpected: {(gadget_line, widget_line, unreachable_line)!r}\n{console}")
    # The supervisor prints every returned line, so printing here too would
    # show the failure twice.
    check("when ned-box cannot be reached, the overview check prints nothing of the "
          "failure itself",
          "could not read the day's reminder marks" not in console, console)

    due, console, calls = due_at(an_hour_later, ssh_body="exec sleep 30", read_timeout=1)
    check("when the read of the marks times out, every due line is given and then the "
          "line saying so, with the timeout",
          due[:2] == (gadget_line, widget_line) and len(due) == 3
          and due[2].startswith(REMINDER_MARKS_UNREAD_LINE_OPENING)
          and "ssh nedlern@ned-box timed out after 1 s" in due[2]
          and due[2].endswith(
              EXPECTED_OVERVIEW_REFRESH_REMINDER_MARKS_NED_BOX_DID_NOT_ANSWER_SENTENCE),
          f"{due!r}\n{console}")

    due, console, calls = due_at(an_hour_later, ssh_body="echo 'this is not json'")
    check("when the read's output does not parse, every due line is given and then the "
          "line saying so",
          due[:2] == (gadget_line, widget_line) and len(due) == 3
          and due[2].startswith(REMINDER_MARKS_UNREAD_LINE_OPENING)
          and "does not parse" in due[2], f"{due!r}\n{console}")
    # ned-box answered, so the line must not say it did not.
    unparsable_line = EXPECTED_OVERVIEW_REFRESH_REMINDER_MARKS_UNREAD_TEMPLATE.format(
        marks_location=mark_citation(""),
        error="DailyMemoryReviewReadOrWriteFailed: ssh nedlern@ned-box answered with "
              "output that does not parse: JSONDecodeError: Expecting value: line 1 "
              "column 1 (char 0)")
    check("when ned-box answers with output that does not parse, the line does not say "
          "ned-box did not answer, nor give the check for whether ned-box answers",
          due[2:] == (unparsable_line,), f"{due[2:]!r}\nexpected: {(unparsable_line,)!r}")

    due, console, calls = due_at(
        an_hour_later, ssh_body="echo 'python3: command not found' >&2\nexit 127")
    check("when ssh reaches ned-box but the read there exits other than 255, the line "
          "does not say ned-box did not answer",
          len(due) == 3 and due[2].startswith(REMINDER_MARKS_UNREAD_LINE_OPENING)
          and "exited 127" in due[2]
          and "did not answer" not in due[2], f"{due!r}\n{console}")

    # Any other exception carries no word on whether ned-box answered.
    def read_that_raises_without_the_attribute(*_arguments, **_options):
        raise RuntimeError("the marks read broke in this fixture")

    if reminder_mark is not None:
        unpatched_read = reminder_mark.read_daily_overview_refresh_reminder_marks
        reminder_mark.read_daily_overview_refresh_reminder_marks = (
            read_that_raises_without_the_attribute)
        try:
            due, console, calls = due_at(an_hour_later)
        finally:
            reminder_mark.read_daily_overview_refresh_reminder_marks = unpatched_read
    check("when the marks read raises an exception that says nothing of ned-box "
          "answering, the line does not say ned-box did not answer",
          len(due) == 3 and due[2].startswith(REMINDER_MARKS_UNREAD_LINE_OPENING)
          and "RuntimeError: the marks read broke in this fixture" in due[2]
          and "did not answer" not in due[2], f"{due!r}\n{console}")

    # A mark for today that does not hold the time it was written is not a
    # mark: a file cut short as it was written, or one written by hand.
    gadget_mark = marks_directory / "2026-10-01-gadget.txt"
    for text, what in (("", "empty"), ("shown to the user\n", "not a time")):
        gadget_mark.write_text(text, encoding="utf-8")
        due, console, calls = due_at(an_hour_later)
        check(f"a mark for today whose text is {what} does not withhold its line, while "
              "the other system's good mark still withholds",
              due == (gadget_line,), f"{due!r}\n{console}")
        check(f"the console says the mark whose text is {what} does not hold a time",
              "handoff-supervisor: overview check for gadget gives its line: the day's "
              f"reminder mark {mark_citation('2026-10-01-gadget.txt')} does not hold the "
              f"time it was written, but {text.strip()!r}\n" in console, console)

    mark_as_the_seat_would("gadget", morning + timedelta(minutes=40))
    due, console, calls = due_at(an_hour_later)
    check("when the user has been shown every due overview's refresh today, no line is "
          "given, and the console names each mark",
          due == ()
          and f"{mark_citation('2026-10-01-gadget.txt')} records" in console
          and f"{mark_citation('2026-10-01-widget.txt')} records" in console,
          f"{due!r}\n{console}")

    due, console, calls = due_at(an_hour_later, hostname="ned-box")
    check("on ned-box the marks are read locally, with no ssh, and withhold the same",
          due == () and calls == [], f"{due!r} {calls!r}\n{console}")
    due, console, calls = due_at(early_the_next_day, hostname="ned-box")
    check("on ned-box, the next day, the first seat is given each line again",
          due == (gadget_line, widget_line) and calls == [], f"{due!r} {calls!r}\n{console}")

    # The open-pull-request check stays as it was, and comes first.
    refresh_title = "Both overviews are refreshed against what landed"
    refresh_url = "https://github.com/nedschorus/nedschorus/pull/9003"
    due, console, calls = due_at(early_the_next_day, gh_directory=gh_answering([
        {"url": refresh_url, "title": refresh_title,
         "files": [{"path": widget_overview}, {"path": gadget_overview}]}]))
    check("an open pull request that changes an overview still withholds its line, and "
          "with no line left to give the marks are never read",
          due == () and calls == []
          and f"overview check for widget withheld its line: the open pull request "
              f"\"{refresh_title}\" ({refresh_url}) already changes {widget_overview}"
              in console, f"{due!r} {calls!r}\n{console}")
    due, console, calls = due_at(early_the_next_day, gh_directory=gh_answering([
        {"url": refresh_url, "title": refresh_title, "files": [{"path": widget_overview}]}]))
    check("of two due systems with no mark for the day, the one whose overview an open "
          "pull request changes is withheld and the other is given",
          due == (gadget_line,), f"{due!r}\n{console}")

    due, console, calls = due_at(an_hour_later, gh_directory=fake_gh_running(
        "echo 'gh: To get started with GitHub CLI, please run:  gh auth login' >&2\nexit 4"))
    check("when GitHub cannot be asked, a reminder already given today still withholds "
          "its line",
          due == () and "so no line is withheld for a pull request: gh exited 4" in console
          and f"{mark_citation('2026-10-01-widget.txt')} records" in console,
          f"{due!r}\n{console}")
    due, console, calls = due_at(early_the_next_day, gh_directory=fake_gh_running(
        "echo 'gh: To get started with GitHub CLI, please run:  gh auth login' >&2\nexit 4"))
    check("when GitHub cannot be asked and no reminder has been given that day, every "
          "due line is given",
          due == (gadget_line, widget_line), f"{due!r}\n{console}")


def run_overview_refresh_due_prompt_cases(workspace: Path):
    """Where the overview-refresh-due line goes: right after the branch-state
    line, at both call sites that compose it, and nothing appended."""
    check("the overview-refresh-due instruction is word for word what was built",
          getattr(supervisor, "OVERVIEW_REFRESH_DUE_INSTRUCTION_TEMPLATE", None)
          == EXPECTED_OVERVIEW_REFRESH_DUE_INSTRUCTION_TEMPLATE,
          repr(getattr(supervisor, "OVERVIEW_REFRESH_DUE_INSTRUCTION_TEMPLATE", None)))
    check("the reminder mark command the overview line names is the program beside "
          "the supervisor",
          getattr(supervisor, "DAILY_OVERVIEW_REFRESH_REMINDER_MARK_PATH", None)
          == DAILY_OVERVIEW_REFRESH_REMINDER_MARK_SCRIPT_PATH
          and DAILY_OVERVIEW_REFRESH_REMINDER_MARK_SCRIPT_PATH.is_file(),
          repr(getattr(supervisor, "DAILY_OVERVIEW_REFRESH_REMINDER_MARK_PATH", None)))
    # The instruction and the two hooks that meet a subagent following it
    # agree. The instruction-file guard lets the subagent write the draft the
    # instruction names, and refuses the overview itself until the user has
    # approved. The file-name collision hook, which runs after every Edit and
    # Write, says nothing about the draft. Run over a scratch checkout in
    # which the overview is a tracked file, as it is on main, so no real
    # approval marker is in the guard's reach and the collision hook has a
    # tracked name to compare the draft's with.
    guarded_checkout = workspace / "overview-draft-guard-checkout"
    guarded_checkout.mkdir()
    git_in(["init", "--quiet", "--initial-branch=main"], guarded_checkout)
    git_in(["config", "user.name", "fixture"], guarded_checkout)
    git_in(["config", "user.email", "fixture@nedschorus.invalid"], guarded_checkout)
    widget_overview = getattr(
        supervisor, "SYSTEM_OVERVIEW_PATH_TEMPLATE", "missing").format(system="widget")
    widget_overview_draft = getattr(
        supervisor, "SYSTEM_OVERVIEW_DRAFT_PATH_TEMPLATE", "missing").format(system="widget")
    (guarded_checkout / widget_overview).parent.mkdir(parents=True, exist_ok=True)
    (guarded_checkout / widget_overview).write_text("# The widget\n", encoding="utf-8")
    git_in(["add", "--", widget_overview], guarded_checkout)
    git_in(["commit", "--quiet", "-m", "the widget's overview"], guarded_checkout)

    def instruction_file_guard_exit_code(relative_path: str) -> int:
        return subprocess.run(
            [sys.executable, str(REPOSITORY_ROOT / ".claude" / "hooks" / "instruction-file-guard.py")],
            input=json.dumps({"cwd": str(guarded_checkout),
                              "tool_input": {"file_path": str(guarded_checkout / relative_path)}}),
            capture_output=True, text=True, check=False).returncode

    def file_name_collision_warning(relative_path: str) -> str:
        """What scripts/file-name-collision-warning-hook.py prints for an
        agent that has just written relative_path in the scratch checkout:
        its warning, or the empty string."""
        written = guarded_checkout / relative_path
        written.parent.mkdir(parents=True, exist_ok=True)
        written.write_text("# The widget, refreshed\n", encoding="utf-8")
        try:
            return subprocess.run(
                [sys.executable,
                 str(REPOSITORY_ROOT / "scripts" / "file-name-collision-warning-hook.py")],
                input=json.dumps({"cwd": str(guarded_checkout),
                                  "tool_input": {"file_path": str(written)}}),
                capture_output=True, text=True, check=False).stdout
        finally:
            written.unlink()

    check("the instruction-file guard lets a subagent write the overview's draft",
          instruction_file_guard_exit_code(widget_overview_draft) == 0, widget_overview_draft)
    check("the instruction-file guard refuses an unapproved write to the overview itself",
          instruction_file_guard_exit_code(widget_overview) == 2, widget_overview)
    printed = file_name_collision_warning(widget_overview_draft)
    check("the file-name collision hook says nothing when a subagent writes the overview's draft",
          printed == "", f"{widget_overview_draft}: {printed}")
    # The control: the hook is live in this checkout, so the silence above is
    # the draft's name and not a hook that could not run.
    draft_under_the_overviews_own_name = (
        widget_overview_draft.rsplit("/", 1)[0] + "/" + widget_overview.rsplit("/", 1)[-1])
    printed = file_name_collision_warning(draft_under_the_overviews_own_name)
    check("the file-name collision hook warns about a second file under the overview's own name",
          "file-name-collision-warning" in printed and widget_overview in printed,
          f"{draft_under_the_overviews_own_name}: {printed}")
    # The convention finds the one overview on main, and that overview carries
    # a pinned line the reader counts: without one the check reports nothing
    # for the handoff system, silently.
    handoff_overview = REPOSITORY_ROOT / getattr(
        supervisor, "SYSTEM_OVERVIEW_PATH_TEMPLATE", "missing").format(system="handoff")
    check("the overview path convention names the handoff system's overview",
          handoff_overview.is_file(), str(handoff_overview))
    reader = getattr(supervisor, "stale_code_citation_check", None)
    check("the handoff overview carries a pinned line the pinned-line reader counts",
          reader is not None and handoff_overview.is_file()
          and bool(reader.landing_pin_commits(
              handoff_overview.read_text(encoding="utf-8"), REPOSITORY_ROOT)),
          str(handoff_overview))

    line = expected_widget_overview_refresh_due_line("1111111", "2222222", 3)
    branch_state_line = (
        "branch sync: fixture-branch is 3 commit(s) behind main — If this "
        "branch has never been pushed, rebase it onto origin/main before your "
        "first substantive action and rerun the tests for what you touched. "
        "If it is pushed, leave it as it is, and start new work on a branch "
        "from origin/main. If this seat has "
        "open pull requests, check their state with `gh`: merge-lane-2 reviews "
        "and merges them; when one has a review with findings, dispatch a "
        "forked subagent to fix it — never extend a head you've already pushed. When one conflicts with main, clear the conflict with the hand-merge that scripts/branch-conflict-check.py describes.")
    fields = {"written-at": "2026-09-28T17:20:00Z", "next-step": "finish the supervisor"}
    try:
        prompt = supervisor.build_ignition_prompt(
            Path("/tmp/dialog-0002.md"), fields,
            branch_sync_report="branch sync: fixture-branch is 3 commit(s) behind main",
            overview_refresh_due=(line,))
    except TypeError:
        prompt = ""
    expected_rest = " " + line + "\n\nThen take the next step:\nfinish the supervisor"
    check("the overview-refresh-due line follows the branch-state line, exactly, and "
          "nothing is appended at the call site",
          nothing_is_appended_to(prompt, branch_state_line, expected_rest),
          "rest after the branch-state line: "
          + repr(prompt.split("branch-conflict-check.py describes.", 1)[-1])
          + "; expected: " + repr(expected_rest))
    try:
        plan_prompt = supervisor.DialogIgnitionPlan(Path("/tmp/dialog-0002.md"), fields).compose(
            "branch sync: fixture-branch is 3 commit(s) behind main", (line,))
    except TypeError:
        plan_prompt = "compose takes no overview lines"
    check("the dialog plan hands its overview lines to the prompt it composes",
          plan_prompt == prompt and prompt != "", repr(plan_prompt))
    try:
        boot_recovery_prompt = supervisor.BootRecoveryIgnitionPlan(
            "finish the supervisor").compose(
                "branch sync: fixture-branch is 3 commit(s) behind main", (line,))
    except TypeError:
        boot_recovery_prompt = ""
    check("the boot-recovery prompt is its next step, the recovery note, the "
          "branch-state line and the overview-refresh-due line, exactly",
          boot_recovery_prompt == (
              "finish the supervisor\n\n(Recovered at supervisor boot: the previous "
              "session's dialog extract is unavailable; this next-step and the "
              "repository are your whole context.) " + branch_state_line + " " + line),
          repr(boot_recovery_prompt))

    # End to end: a supervisor igniting a seat whose checkout has a system due
    # hands the successor the line, after the branch-state instruction, and
    # prints it on its console.
    seat = workspace / "overview-refresh-due-seat"
    seat.mkdir()
    git_in(["init", "--quiet", "--initial-branch=main"], seat)
    git_in(["config", "user.name", "fixture"], seat)
    git_in(["config", "user.email", "fixture@nedschorus.invalid"], seat)
    (seat / "nc-systems" / "widget").mkdir(parents=True)
    (seat / "nc-systems" / "widget" / "widget.py").write_text("print(1)\n", encoding="utf-8")
    git_in(["add", "-A"], seat)
    git_in(["commit", "--quiet", "-m", "the widget lands"], seat)
    landed = git_in(["rev-parse", "HEAD"], seat).stdout.strip()
    (seat / "docs" / "nedschorus-wiki").mkdir(parents=True)
    (seat / "docs" / "nedschorus-wiki" / "nedschorus-widget-system-overview.md").write_text(
        f"# The widget\n\n**Pinned to what landed:** commit [{landed[:7]}]"
        f"(https://github.com/nedschorus/nedschorus/commit/{landed}) on 2026-09-28 "
        "— the widget.\n", encoding="utf-8")
    (seat / "nc-systems" / "widget" / "widget.py").write_text("print(2)\n", encoding="utf-8")
    git_in(["add", "-A"], seat)
    git_in(["commit", "--quiet", "-m", "the overview is pinned and the widget grows"], seat)
    git_in(["update-ref", "refs/remotes/origin/main", "HEAD"], seat)
    main = git_in(["rev-parse", "--short", "HEAD"], seat).stdout.strip()
    expected = expected_widget_overview_refresh_due_line(landed[:7], main, 1)

    handoff_directory = workspace / "overview-refresh-due-handoffs"
    handoff_directory.mkdir()
    (handoff_directory / "refreshdue-handoff.md").write_text(
        "written-at: 2026-09-28T00:00:00Z\nnext-step: resume the audit\nrestart-counter: 5\n",
        encoding="utf-8")
    supervisor.write_supervisor_state(
        handoff_directory / "refreshdue-supervisor-state.json",
        {"consumed_counter": 4, "launched_session_id": "no-such-session", "generation": 4})
    record_path = handoff_directory / "launch-record.txt"
    stub_agent = handoff_directory / "stub-agent"
    stub_agent.write_text(
        "#!/bin/sh\n"
        "exec >/dev/null 2>&1\n"
        "for launched_prompt; do :; done\n"
        f"printf '%s\\n' \"$launched_prompt\" > '{record_path}'\n"
        "exit 0\n",
        encoding="utf-8")
    stub_agent.chmod(0o755)
    no_open_pull_requests = write_gh_answering_no_open_pull_requests(
        handoff_directory / "gh-answering-no-open-pull-requests")
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", "refreshdue", "--cd", str(seat),
         "--handoff-dir", str(handoff_directory), "--agent-command", str(stub_agent),
         "--agent-update-timeout-seconds", "0"],
        capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL, timeout=60,
        env={**os.environ,
             "PATH": f"{no_open_pull_requests}{os.pathsep}{os.environ.get('PATH', '')}"})
    launched = record_path.read_text(encoding="utf-8") if record_path.is_file() else ""
    check("an ignited successor's prompt carries the overview-refresh-due line after "
          "the branch-state instruction",
          expected in launched and "already pushed." in launched
          and launched.index("already pushed.") < launched.index(expected),
          f"{result.returncode} {launched[-900:]!r} {result.stdout[-600:]}")
    check("the supervisor prints the overview-refresh-due line on its console",
          f"handoff-supervisor: {expected}" in result.stdout, result.stdout[-900:])

    # End to end, the marks unreadable: the successor is given the due line and,
    # after it, the line saying the marks could not be read, and the console
    # shows that line once. The read goes over ssh from the Mac and through
    # /bin/sh to python3 on ned-box; a fake of each, first on PATH, fails it
    # on either machine.
    unread_directory = workspace / "overview-refresh-marks-unread-handoffs"
    unread_directory.mkdir()
    (unread_directory / "marksunread-handoff.md").write_text(
        "written-at: 2026-09-28T00:00:00Z\nnext-step: resume the audit\nrestart-counter: 5\n",
        encoding="utf-8")
    supervisor.write_supervisor_state(
        unread_directory / "marksunread-supervisor-state.json",
        {"consumed_counter": 4, "launched_session_id": "no-such-session", "generation": 4})
    unread_record_path = unread_directory / "launch-record.txt"
    unread_stub_agent = unread_directory / "stub-agent"
    unread_stub_agent.write_text(
        stub_agent.read_text(encoding="utf-8").replace(str(record_path),
                                                       str(unread_record_path)),
        encoding="utf-8")
    unread_stub_agent.chmod(0o755)
    failing_read_directory = unread_directory / "failing-marks-read"
    failing_read_directory.mkdir()
    for program in ("ssh", "python3"):
        (failing_read_directory / program).write_text(
            "#!/bin/sh\necho 'marks read failed in this fixture' >&2\nexit 255\n",
            encoding="utf-8")
        (failing_read_directory / program).chmod(0o755)
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", "marksunread", "--cd", str(seat),
         "--handoff-dir", str(unread_directory), "--agent-command", str(unread_stub_agent),
         "--agent-update-timeout-seconds", "0"],
        capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL, timeout=60,
        env={**os.environ,
             "PATH": f"{failing_read_directory}{os.pathsep}{no_open_pull_requests}"
                     f"{os.pathsep}{os.environ.get('PATH', '')}"})
    launched = (unread_record_path.read_text(encoding="utf-8")
                if unread_record_path.is_file() else "")
    check("an ignited successor whose reminder marks cannot be read is given the "
          "overview-refresh-due line and, after it, the line saying the marks could "
          "not be read, with the error, and the instruction to tell the user",
          expected in launched and REMINDER_MARKS_UNREAD_LINE_OPENING in launched
          and launched.index(expected) < launched.index(REMINDER_MARKS_UNREAD_LINE_OPENING)
          and "marks read failed in this fixture" in launched
          and "Before you act on any overview-refresh line in this prompt, tell the user"
          in launched,
          f"{result.returncode} {launched[-1500:]!r} {result.stdout[-900:]}")
    check("the supervisor prints the line saying the marks could not be read on its "
          "console, once",
          result.stdout.count("handoff-supervisor: " + REMINDER_MARKS_UNREAD_LINE_OPENING) == 1,
          result.stdout[-1500:])
    check("the template the supervisor fills is word for word what was built",
          getattr(supervisor, "OVERVIEW_REFRESH_REMINDER_MARKS_UNREAD_TEMPLATE", None)
          == EXPECTED_OVERVIEW_REFRESH_REMINDER_MARKS_UNREAD_TEMPLATE,
          repr(getattr(supervisor, "OVERVIEW_REFRESH_REMINDER_MARKS_UNREAD_TEMPLATE", None)))
    check("the sentence for ned-box giving no answer is word for word what was built",
          getattr(supervisor,
                  "OVERVIEW_REFRESH_REMINDER_MARKS_NED_BOX_DID_NOT_ANSWER_SENTENCE", None)
          == EXPECTED_OVERVIEW_REFRESH_REMINDER_MARKS_NED_BOX_DID_NOT_ANSWER_SENTENCE,
          repr(getattr(supervisor,
                       "OVERVIEW_REFRESH_REMINDER_MARKS_NED_BOX_DID_NOT_ANSWER_SENTENCE",
                       None)))


# The memory-review-due instruction, word for word. A template: the mark
# command's path and the stores' paths are filled in.
EXPECTED_MEMORY_REVIEW_DUE_INSTRUCTION_TEMPLATE = (
    " — Run `python3 {mark_script} started` first. Then put every entry of "
    "both memory stores, {mac_memory_store} on the Mac and ned-box's at "
    "{ned_box_memory_store_mac_mount} (when that path does not open, "
    "{ned_box_memory_store} over ssh, and run this review's shell commands "
    "there over ssh too), to the user in an approval-walk with the "
    "/walk-me-through skill, one entry per item; entries with little at stake "
    "may be shown together, as the skill allows. In each item, show the "
    "entry's text and recommend what it should become: a fix to an "
    "instruction file now, which is best; a task on your task list; a GitHub "
    "issue filed with /ghi-write; or nothing, when the entry is stale. Carry "
    "out the user's ruling, then delete the entry's file and remove its line "
    "from that store's MEMORY.md index, both with shell commands. Do not edit "
    "an entry: the instruction-file guard refuses every Edit or Write into a "
    "memory store. When the walk closes, run `python3 {mark_script} done`."
)

# ned-box's store as the Mac opens it through the Samba mount of ned-box's
# home. The fixtures leave it as it is: the supervisor never reads the mount,
# it only names it.
NED_BOX_MEMORY_STORE_MAC_MOUNT_PATH = (
    "/Volumes/nedhome/.claude/projects/-home-nedlern-Projects-nedschorus/memory")

DAILY_MEMORY_REVIEW_MARK_SCRIPT_PATH = SYSTEM_DIRECTORY / "daily-memory-review-mark.py"

# 12:00 in America/Los_Angeles on 2026-09-30, which is PDT, UTC-7.
MEMORY_REVIEW_PACIFIC_NOON = datetime(2026, 9, 30, 19, 0, tzinfo=timezone.utc)

# The fake ssh's default: skip the options, record the host, and run the
# command it was handed here, as ned-box would run it.
SSH_THAT_RUNS_THE_COMMAND_HERE = 'exec /bin/sh -c "$1"'


def expected_memory_review_due_line(mac_store, ned_box_store, mac_entries,
                                    ned_box_entries, since) -> str:
    """The whole line, spelled out, so a change to the report, the template or
    a path fails the pin."""
    mark = DAILY_MEMORY_REVIEW_MARK_SCRIPT_PATH
    return (
        f"memory review due: the Mac's memory store holds {mac_entries} and "
        f"ned-box's holds {ned_box_entries}, {since} — Run `python3 {mark} started` "
        "first. Then put every entry of both memory stores, "
        f"{mac_store}/ on the Mac and ned-box's at {NED_BOX_MEMORY_STORE_MAC_MOUNT_PATH}/ "
        f"(when that path does not open, nedlern@ned-box:{ned_box_store}/ over ssh, "
        "and run this review's shell commands there over ssh too), to the user in an "
        "approval-walk with the /walk-me-through skill, one entry per item; entries with "
        "little at stake may be shown together, as the skill allows. In each item, show "
        "the entry's text and recommend what it should become: a fix to an instruction "
        "file now, which is best; a task on your task list; a GitHub issue filed with "
        "/ghi-write; or nothing, when the entry is stale. Carry out the user's ruling, "
        "then delete the entry's file and remove its line from that store's MEMORY.md "
        "index, both with shell commands. Do not edit an entry: the instruction-file "
        "guard refuses every Edit or Write into a memory store. When the walk closes, run "
        f"`python3 {mark} done`.")


def memory_review_due_or_missing(now):
    """memory_review_due_lines's result at now, or the string "missing" against
    a supervisor that has no such function, so each case FAILS cleanly there
    instead of crashing the suite."""
    due = getattr(supervisor, "memory_review_due_lines", None)
    return "missing" if due is None else due(now=now)


@contextlib.contextmanager
def local_time_zone(name: str):
    """The machine's own zone, for this process, is name."""
    saved = os.environ.get("TZ")
    os.environ["TZ"] = name
    time.tzset()
    try:
        yield
    finally:
        if saved is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = saved
        time.tzset()


class MemoryReviewFixture:
    """Two fixture stores and a marks directory stand in for the real ones,
    through daily_memory_review_mark's constants; an ssh first on PATH records
    the host of each call and runs its body; and the machine is named, so the
    cases mean the same on ned-box as on the Mac."""

    def __init__(self, root: Path):
        self.root = root
        self.mac_store = root / "mac-memory-store"
        self.ned_box_store = root / "ned-box-memory-store"
        self.marks = root / "daily-memory-review-marks"
        self.mark_module = getattr(supervisor, "daily_memory_review_mark", None)
        self.fake_ssh_count = 0

    @contextlib.contextmanager
    def in_place(self, ssh_body=SSH_THAT_RUNS_THE_COMMAND_HERE, read_timeout=None,
                 hostname="a-mac-that-is-not-ned-box", mac_store=None, ned_box_store=None):
        """Yields the file the fake ssh records its calls' hosts in."""
        self.fake_ssh_count += 1
        directory = self.root / f"fake-ssh-{self.fake_ssh_count}"
        directory.mkdir()
        calls = directory / "calls"
        fake_ssh = directory / "ssh"
        fake_ssh.write_text(
            '#!/bin/sh\nwhile [ "$1" = "-o" ]; do shift 2; done\n'
            'printf "%s\\n" "$1" >> "' + str(calls) + '"\nshift\n' + ssh_body + "\n",
            encoding="utf-8")
        fake_ssh.chmod(0o755)
        missing = object()
        saved = []

        def replace(owner, name, value):
            saved.append((owner, name, getattr(owner, name, missing)))
            setattr(owner, name, value)

        if self.mark_module is not None:
            replace(self.mark_module, "MAC_MEMORY_STORE_DIRECTORY", str(mac_store or self.mac_store))
            replace(self.mark_module, "NED_BOX_MEMORY_STORE_DIRECTORY",
                    str(ned_box_store or self.ned_box_store))
            replace(self.mark_module, "DAILY_MEMORY_REVIEW_MARKS_DIRECTORY", str(self.marks))
        if read_timeout is not None:
            replace(supervisor, "MEMORY_REVIEW_CHECK_READ_TIMEOUT_SECONDS", read_timeout)
        replace(socket, "gethostname", lambda: hostname)
        original_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{directory}{os.pathsep}{original_path}"
        try:
            yield calls
        finally:
            os.environ["PATH"] = original_path
            for owner, name, value in reversed(saved):
                if value is missing:
                    delattr(owner, name)
                else:
                    setattr(owner, name, value)

    def due_at(self, now, **in_place_options):
        """memory_review_due_lines's result at now, its console, and the hosts
        the fake ssh was called for."""
        console = io.StringIO()
        with self.in_place(**in_place_options) as calls, contextlib.redirect_stdout(console):
            due = memory_review_due_or_missing(now)
        recorded = calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []
        return due, console.getvalue(), recorded

    def mark(self, kind, now):
        """Write a mark with the mark program itself, as the seat would."""
        if self.mark_module is None:
            return
        with self.in_place(), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            self.mark_module.main([kind], now=now)


def run_memory_review_due_cases(workspace: Path):
    """memory_review_due_lines against fixture stores and marks, at chosen
    moments, with ned-box played by an ssh that runs its command here.

    Ruled 2026-09-30 (item 3 of the walk
    eight-deferrals-with-no-trigger-2026-09-29, "y"): from noon Pacific, a Mac
    supervisor's successor is asked for the day's review of both machines'
    memory stores, unless today's review has started or is done, or neither
    store changed since the last one was done.
    """
    root = workspace / "memory-review-due"
    root.mkdir()
    fixture = MemoryReviewFixture(root)
    for store in (fixture.mac_store, fixture.ned_box_store):
        store.mkdir()
        (store / "MEMORY.md").write_text("- [An entry](an-entry.md) — the index\n",
                                         encoding="utf-8")
    (fixture.mac_store / "mac-entry-one.md").write_text("one\n", encoding="utf-8")
    (fixture.mac_store / "mac-entry-two.md").write_text("two\n", encoding="utf-8")
    (fixture.ned_box_store / "ned-box-entry.md").write_text("box\n", encoding="utf-8")
    noon = MEMORY_REVIEW_PACIFIC_NOON
    day = timedelta(days=1)

    def line(since):
        return expected_memory_review_due_line(
            fixture.mac_store, fixture.ned_box_store, "2 entries", "1 entry", since)

    never_done = "and no review is recorded as done"

    due, console, calls = fixture.due_at(noon - timedelta(minutes=1))
    check("MEMORY REVIEW: before noon Pacific, no line is given and nothing is read",
          due == () and calls == [], f"{due!r} {calls!r}\n{console}")

    due, console, calls = fixture.due_at(noon)
    check("MEMORY REVIEW: from noon Pacific with no marks, the line is given, exactly",
          due == (line(never_done),), f"{due!r}\nexpected: {line(never_done)!r}\n{console}")
    check("MEMORY REVIEW: ned-box's store and the marks are read in one ssh call to "
          "nedlern@ned-box", calls == ["nedlern@ned-box"], repr(calls))

    # The zone is named: under Tokyo's zone, 19:00Z is 04:00 and 10:00Z is
    # 19:00 on the machine's clock, while in Pacific time they are noon and 03:00.
    with local_time_zone("Asia/Tokyo"):
        at_pacific_noon, _, _ = fixture.due_at(noon)
        at_pacific_three_in_the_morning, _, _ = fixture.due_at(noon - timedelta(hours=9))
    check("MEMORY REVIEW: noon is read in America/Los_Angeles, not in the machine's zone",
          at_pacific_noon == (line(never_done),) and at_pacific_three_in_the_morning == (),
          f"{at_pacific_noon!r} {at_pacific_three_in_the_morning!r}")

    empty_mac_store = root / "empty-mac-memory-store"
    empty_ned_box_store = root / "empty-ned-box-memory-store"
    for store in (empty_mac_store, empty_ned_box_store):
        store.mkdir()
        (store / "MEMORY.md").write_text("", encoding="utf-8")
    due, console, calls = fixture.due_at(noon, mac_store=empty_mac_store,
                                         ned_box_store=empty_ned_box_store)
    check("MEMORY REVIEW: with no marks and no entry in either store, no line is given",
          due == (), f"{due!r}\n{console}")

    # Started today: no line for the rest of the Pacific day, which at 03:00Z
    # the next morning in UTC still is.
    fixture.mark("started", noon + timedelta(minutes=5))
    due, console, calls = fixture.due_at(noon + timedelta(hours=1))
    check("MEMORY REVIEW: after noon with a started mark for today, no line is given",
          due == (), f"{due!r}\n{console}")
    due, console, calls = fixture.due_at(noon + timedelta(hours=8))
    check("MEMORY REVIEW: today is the Pacific date, not the UTC one",
          due == (), f"{due!r}\n{console}")

    # A seat that died mid-walk left only yesterday's started mark: the next
    # noon asks again.
    due, console, calls = fixture.due_at(noon + day)
    check("MEMORY REVIEW: a started mark from an earlier day keeps nothing quiet at "
          "the next noon", due == (line(never_done),),
          f"{due!r}\nexpected: {line(never_done)!r}\n{console}")

    # Done today: no line for the rest of the day, even once a store changes.
    fixture.mark("done", noon + day + timedelta(minutes=30))
    due, console, calls = fixture.due_at(noon + day + timedelta(hours=1))
    check("MEMORY REVIEW: after noon with a done mark for today, no line is given",
          due == (), f"{due!r}\n{console}")
    (fixture.ned_box_store / "ned-box-entry.md").write_text("box, edited\n", encoding="utf-8")
    due, console, calls = fixture.due_at(noon + day + timedelta(hours=2))
    check("MEMORY REVIEW: a done mark for today keeps the day quiet after a store changes",
          due == (), f"{due!r}\n{console}")
    (fixture.ned_box_store / "ned-box-entry.md").write_text("box\n", encoding="utf-8")

    due, console, calls = fixture.due_at(noon + 2 * day)
    check("MEMORY REVIEW: stores unchanged since the last done mark give no line",
          due == (), f"{due!r}\n{console}")

    (fixture.mac_store / "mac-entry-two.md").write_text("two, edited\n", encoding="utf-8")
    due, console, calls = fixture.due_at(noon + 2 * day + timedelta(minutes=1))
    changed = line("changed since the review done on 2026-10-01")
    check("MEMORY REVIEW: a store changed since the last done mark gives the line, "
          "naming that review's date", due == (changed,),
          f"{due!r}\nexpected: {changed!r}\n{console}")

    # Each failure below has a due line to lose.
    due, console, calls = fixture.due_at(
        noon + 2 * day + timedelta(minutes=2),
        ssh_body="echo 'ssh: connect to host ned-box port 22: No route to host' >&2\n"
                 "echo 'second line of complaint' >&2\nexit 255")
    check("MEMORY REVIEW: when ned-box cannot be reached, no line is given",
          due == (), f"{due!r}\n{console}")
    check("MEMORY REVIEW: when ned-box cannot be reached, the console says why, in one line",
          console == "handoff-supervisor: memory review check gave no line: "
          "DailyMemoryReviewReadOrWriteFailed: ssh nedlern@ned-box exited 255: ssh: "
          "connect to host ned-box port 22: No route to host\n", console)

    due, console, calls = fixture.due_at(noon + 2 * day + timedelta(minutes=3),
                                         ssh_body="exec sleep 30", read_timeout=1)
    check("MEMORY REVIEW: when the ssh read times out, no line is given and the console "
          "says why", due == ()
          and "memory review check gave no line: DailyMemoryReviewReadOrWriteFailed: ssh "
          "nedlern@ned-box timed out after 1 s" in console, f"{due!r}\n{console}")

    due, console, calls = fixture.due_at(noon + 2 * day + timedelta(minutes=4),
                                         hostname="ned-box")
    check("MEMORY REVIEW: running on ned-box, no line is given and nothing is read",
          due == () and calls == [] and console == "", f"{due!r} {calls!r}\n{console}")


def run_memory_review_due_prompt_cases(workspace: Path):
    """Where the memory-review-due line goes: right after the branch-state line
    and the overview lines, at both call sites that compose it, and nothing
    appended; and the launch site hands it to the successor."""
    check("MEMORY REVIEW: the instruction is word for word what was built",
          getattr(supervisor, "MEMORY_REVIEW_DUE_INSTRUCTION_TEMPLATE", None)
          == EXPECTED_MEMORY_REVIEW_DUE_INSTRUCTION_TEMPLATE,
          repr(getattr(supervisor, "MEMORY_REVIEW_DUE_INSTRUCTION_TEMPLATE", None)))
    check("MEMORY REVIEW: the mark program the line names is the one beside the supervisor",
          getattr(supervisor, "DAILY_MEMORY_REVIEW_MARK_PATH", None)
          == DAILY_MEMORY_REVIEW_MARK_SCRIPT_PATH
          and DAILY_MEMORY_REVIEW_MARK_SCRIPT_PATH.is_file(),
          repr(getattr(supervisor, "DAILY_MEMORY_REVIEW_MARK_PATH", None)))

    overview_line = expected_widget_overview_refresh_due_line("1111111", "2222222", 3)
    memory_line = expected_memory_review_due_line(
        Path("/fixture/mac-memory-store"), Path("/fixture/ned-box-memory-store"),
        "2 entries", "1 entry", "and no review is recorded as done")
    branch_sync_report = "branch sync: fixture-branch is 3 commit(s) behind main"
    branch_state_line = (
        branch_sync_report + " — If this "
        "branch has never been pushed, rebase it onto origin/main before your "
        "first substantive action and rerun the tests for what you touched. "
        "If it is pushed, leave it as it is, and start new work on a branch "
        "from origin/main. If this seat has "
        "open pull requests, check their state with `gh`: merge-lane-2 reviews "
        "and merges them; when one has a review with findings, dispatch a "
        "forked subagent to fix it — never extend a head you've already pushed. When one conflicts with main, clear the conflict with the hand-merge that scripts/branch-conflict-check.py describes.")
    fields = {"written-at": "2026-09-30T19:20:00Z", "next-step": "finish the review"}
    try:
        prompt = supervisor.build_ignition_prompt(
            Path("/tmp/dialog-0002.md"), fields, branch_sync_report=branch_sync_report,
            overview_refresh_due=(overview_line,), memory_review_due=(memory_line,))
    except TypeError:
        prompt = ""
    expected_rest = (" " + overview_line + " " + memory_line
                     + "\n\nThen take the next step:\nfinish the review")
    check("MEMORY REVIEW: the line follows the branch-state line and the overview line, "
          "exactly, and nothing is appended at the call site",
          nothing_is_appended_to(prompt, branch_state_line, expected_rest),
          "rest after the branch-state line: "
          + repr(prompt.split("branch-conflict-check.py describes.", 1)[-1])
          + "; expected: " + repr(expected_rest))
    try:
        plan_prompt = supervisor.DialogIgnitionPlan(Path("/tmp/dialog-0002.md"), fields).compose(
            branch_sync_report, (overview_line,), (memory_line,))
    except TypeError:
        plan_prompt = "compose takes no memory review line"
    check("MEMORY REVIEW: the dialog plan hands its memory review line to the prompt it "
          "composes", plan_prompt == prompt and prompt != "", repr(plan_prompt))
    recovery_note = ("\n\n(Recovered at supervisor boot: the previous session's dialog "
                     "extract is unavailable; this next-step and the repository are your "
                     "whole context.) ")
    try:
        boot_recovery_prompt = supervisor.BootRecoveryIgnitionPlan("finish the review").compose(
            branch_sync_report, (overview_line,), (memory_line,))
    except TypeError:
        boot_recovery_prompt = ""
    check("MEMORY REVIEW: the boot-recovery prompt is its next step, the recovery note, "
          "the branch-state line, the overview line and the memory review line, exactly",
          boot_recovery_prompt == ("finish the review" + recovery_note + branch_state_line
                                   + " " + overview_line + " " + memory_line),
          repr(boot_recovery_prompt))

    # Through the launch site: a supervisor igniting from an unconsumed handoff
    # at noon Pacific, with the real check against fixture stores, hands the
    # successor the line after the overview line and prints it on its console.
    root = workspace / "memory-review-due-launch"
    root.mkdir()
    fixture = MemoryReviewFixture(root)
    for store in (fixture.mac_store, fixture.ned_box_store):
        store.mkdir()
        (store / "MEMORY.md").write_text("- [An entry](an-entry.md)\n", encoding="utf-8")
    (fixture.mac_store / "mac-entry-one.md").write_text("one\n", encoding="utf-8")
    (fixture.mac_store / "mac-entry-two.md").write_text("two\n", encoding="utf-8")
    (fixture.ned_box_store / "ned-box-entry.md").write_text("box\n", encoding="utf-8")
    launched_memory_line = expected_memory_review_due_line(
        fixture.mac_store, fixture.ned_box_store, "2 entries", "1 entry",
        "and no review is recorded as done")
    handoff_directory = root / "handoffs"
    handoff_directory.mkdir()
    settings = supervisor.SupervisorSettings(
        agent="memoryreviewdue", working_directory=root, handoff_directory=handoff_directory,
        agent_command="unused-stub-agent", first_prompt="")
    settings.handoff_path.write_text(
        "written-at: 2026-09-30T00:00:00Z\nnext-step: resume the audit\nrestart-counter: 5\n",
        encoding="utf-8")
    supervisor.write_supervisor_state(
        settings.state_path,
        {"consumed_counter": 4, "launched_session_id": "no-such-session", "generation": 4})
    launched_prompts = []

    def launch_recording(agent_command, session_id, working_directory, prompt, **_):
        launched_prompts.append(prompt)
        return StubLaunchedSession(0)

    real_memory_review_due_lines = getattr(supervisor, "memory_review_due_lines", None)
    at_noon = (functools.partial(real_memory_review_due_lines, now=MEMORY_REVIEW_PACIFIC_NOON)
               if real_memory_review_due_lines else (lambda: ()))
    console = io.StringIO()
    with fixture.in_place(), supervisor_names_replaced(
            launch_agent_session=launch_recording,
            sync_working_branch_with_main=lambda working_directory: branch_sync_report,
            overview_refresh_due_lines=lambda working_directory: (overview_line,),
            memory_review_due_lines=at_noon,
            stdin_isatty=False), contextlib.redirect_stdout(console):
        supervisor.supervise_sessions(settings)
    check("MEMORY REVIEW: an ignited successor's prompt carries the line after the "
          "branch-state line and the overview line, exactly",
          launched_prompts == ["resume the audit" + recovery_note + branch_state_line
                               + " " + overview_line + " " + launched_memory_line],
          f"{launched_prompts!r}\n{console.getvalue()[-900:]}")
    check("MEMORY REVIEW: the supervisor prints the line on its console",
          f"handoff-supervisor: {launched_memory_line}\n" in console.getvalue(),
          console.getvalue()[-900:])


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
        {"consumed_counter": 4, "launched_session_id": "no-such-session", "generation": 4},
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
         "--handoff-dir", str(handoff_directory), "--agent-command", str(stub_agent), "--agent-update-timeout-seconds", "0"],
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
          "on a branch from origin/main. If this seat has open pull requests, "
          "check their state with `gh`: merge-lane-2 reviews and merges them; "
          "when one has a review with findings, dispatch a forked subagent to "
          "fix it — never extend a head you've already pushed. When one conflicts with main, clear the conflict with the hand-merge that scripts/branch-conflict-check.py describes."
          in launched,
          launched[:700])
    state = supervisor.read_supervisor_state(handoff_directory / "bootignite-supervisor-state.json")
    check("boot-ignition consumes the handoff counter", state.get("consumed_counter") == 5, str(state))


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
    console = io.StringIO()
    try:
        supervisor.extract_dialog = (
            lambda session_id, working_directory, output_path:
            output_path.write_text("the extracted dialog\n", encoding="utf-8") > 0)
        with contextlib.redirect_stdout(console):
            successor_id, plan = supervisor.carry_over_to_successor(
                settings, "0000-retiring-session", handoff_fields, generation=3)
    finally:
        supervisor.extract_dialog = original_extract_dialog

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
    code that trusts the state file: it extracts and cites the
    launched session instead of the writer. The two fallback cases — field
    absent (an older handoff) and field "unknown" (a session with no
    CLAUDE_CODE_SESSION_ID) — pass either way; they are here so the
    preference cannot be turned into a requirement.
    """
    home = workspace / "retiring-session-id-from-the-handoff"

    def carry_over(case_name: str, written_by_session_line: str,
                   tracked_session_id: str):
        """One carry_over_to_successor run, with the extractor recording its id."""
        case_home = home / case_name
        handoff_directory = case_home / "handoffs"
        handoff_directory.mkdir(parents=True)
        working_directory = case_home / "seat"
        working_directory.mkdir(parents=True)
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
        console = io.StringIO()
        try:
            supervisor.extract_dialog = recording_extract_dialog
            with contextlib.redirect_stdout(console):
                successor_id, plan = supervisor.carry_over_to_successor(
                    settings, tracked_session_id, handoff_fields, generation=5)
        finally:
            supervisor.extract_dialog = original_extract_dialog

        return SimpleNamespace(
            extracted_from=extracted_from,
            successor_id=successor_id,
            plan=plan,
            printed=console.getvalue(),
            predecessor_session_directory_for=lambda session_id: (
                supervisor.project_directory_for_working_directory(working_directory)
                / session_id),
        )

    # --- The handoff's writer is not the session the supervisor launched ---
    launched = "ac2b8ebe-the-session-the-supervisor-launched"
    writer = "145a31fd-the-session-that-wrote-the-handoff"
    diverged = carry_over("diverged", f"written-by-session: {writer}\n", launched)
    check("the dialog is extracted from the session that wrote the handoff",
          diverged.extracted_from == [writer], str(diverged.extracted_from))
    check("the plan names the writing session's directory, not the launched one's",
          diverged.plan is not None
          and diverged.plan.predecessor_session_directory
          == diverged.predecessor_session_directory_for(writer),
          str(diverged.plan and diverged.plan.predecessor_session_directory))
    check("the console names both ids when the handoff's writer is not the tracked session",
          writer in diverged.printed and launched in diverged.printed, diverged.printed)

    # --- Fallbacks: nothing to prefer, so the tracked id stands -----------
    absent = carry_over("absent", "", "0000-tracked-with-no-field")
    check("a handoff without the field falls back to the tracked session",
          absent.extracted_from == ["0000-tracked-with-no-field"], str(absent.extracted_from))
    check("the fallback plan names the tracked session's directory",
          absent.plan is not None
          and absent.plan.predecessor_session_directory
          == absent.predecessor_session_directory_for("0000-tracked-with-no-field"),
          str(absent.plan and absent.plan.predecessor_session_directory))

    unknown = carry_over("unknown", "written-by-session: unknown\n",
                         "0000-tracked-under-unknown")
    check("a handoff whose writer is `unknown` falls back to the tracked session",
          unknown.extracted_from == ["0000-tracked-under-unknown"], str(unknown.extracted_from))
    check("the `unknown` fallback plan names the tracked session's directory",
          unknown.plan is not None
          and unknown.plan.predecessor_session_directory
          == unknown.predecessor_session_directory_for("0000-tracked-under-unknown"),
          str(unknown.plan and unknown.plan.predecessor_session_directory))


with fixture.handoff_supervisor_suite_workspace() as workspace:
    recent_timestamp = run_offline_cases(workspace)
    run_branch_sync_cases(workspace)
    with gh_answering_no_open_pull_requests_first_on_path(
            workspace / "gh-answering-no-open-pull-requests"):
        run_overview_refresh_due_cases(workspace)
    run_overview_refresh_withheld_while_pull_request_open_cases(workspace)
    run_overview_refresh_once_a_day_cases(workspace)
    run_overview_refresh_due_prompt_cases(workspace)
    run_memory_review_due_cases(workspace)
    run_memory_review_due_prompt_cases(workspace)
    run_boot_ignition_case(workspace)
    run_first_prompt_file_cases(workspace)
    run_multi_line_next_step_cases(workspace, recent_timestamp)
    run_launch_and_retention_cases(workspace, recent_timestamp)
    run_spawned_subagent_roster_cases(workspace, recent_timestamp)
    run_recycle_prompt_composition_cases(workspace, recent_timestamp)
    run_retiring_session_id_from_the_handoff_cases(workspace, recent_timestamp)

# --- The depths this system's move depends on (added 2026-09-20) ----------
# When main-gatekeeper moved into nc-systems/, its suite kept a
# `SCRIPT_PATH.parent.parent` that had meant the repository root from scripts/
# and silently began naming nc-systems/ instead. Nothing failed, so nothing
# said so. These cases pin every depth this system resolves across, in both
# the suites' fixture and the code, so the same slip here fails out loud.
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
    print("\n-- live pinned-task-list canaries (launching real sessions) --")
    run_preseed_canaries()
else:
    print("\n(skipped the live pinned-task-list canaries; pass --canary to run them)")

fixture.print_summary_and_exit_nonzero_if_any_case_failed()
