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


def run_writer(workspace: Path, next_step_text: str, *extra_arguments, environment_overrides=None):
    """Invoke the script as the agent would, returning its completed process.

    The session identity is scrubbed from the environment deliberately. These
    tests run inside a live Claude session, and leaving CLAUDE_PID set would
    have the writer start a real supervisor that kills the very session
    running the tests.

    environment_overrides is how the roster cases point the writer at a fake
    HOME and a fake session id: the roster is derived from the running
    session's transcript, so exercising it end to end means giving the writer
    a session whose transcript is a fixture rather than this test run's own.
    """
    next_step_path = workspace / "next-step.txt"
    next_step_path.write_text(next_step_text, encoding="utf-8")
    scrubbed_environment = {
        key: value for key, value in os.environ.items()
        if key not in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_PID")
    }
    scrubbed_environment["HANDOFF_SKIP_PROTECTION_AUDIT"] = "1"  # offline tests never call GitHub
    scrubbed_environment.update(environment_overrides or {})
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



# ---------------------------------------------------------------------------
# The roster of subagents the retiring session spawned.
#
# The records below are trimmed copies of real ones, taken from the merge-lane
# session transcripts of 2026-08-23 (the session that died owning pull request
# #150's fixer, and its successor). Their SHAPE is the thing under test — the
# derivation reads a harness format nothing else in this repository defines —
# so they are reproduced field for field rather than idealised.

SPAWN_NOTICE_TEXT = (
    "Async agent launched successfully. (This tool result is internal metadata — never quote or "
    "paste any part of it, including the agentId below, into a user-facing reply.)\n"
    "agentId: {agent_id} (internal ID - do not mention to user. Use SendMessage with "
    "to: '{agent_id}', summary: '<5-10 word recap>' to continue this agent.)\n"
    "The agent is working in the background. You will be notified automatically when it completes."
)


def spawn_record(agent_id: str, description: str, timestamp: str) -> dict:
    """A subagent spawn, as the harness writes it.

    The tool_result is present and matched — it arrives at SPAWN time, saying
    the agent was launched — which is exactly why the derivation must not read
    an unmatched tool_use as a running subagent.
    """
    tool_use_id = f"toolu_{agent_id}"
    return {
        "parentUuid": "4fcc9127-dd74-41e8-9bd2-995b89006d15", "isSidechain": False, "type": "user",
        "message": {"role": "user", "content": [{
            "tool_use_id": tool_use_id, "type": "tool_result",
            "content": [{"type": "text", "text": SPAWN_NOTICE_TEXT.format(agent_id=agent_id)}],
        }]},
        "uuid": f"uuid-{agent_id}", "timestamp": timestamp,
        "toolUseResult": {
            "isAsync": True, "status": "async_launched", "agentId": agent_id,
            "description": description, "resolvedModel": "claude-opus-5[1m]",
            "prompt": "the commissioning prompt, which can run to thousands of words",
            "outputFile": f"/private/tmp/tasks/{agent_id}.output", "canReadOutputFile": False,
        },
        "sessionId": FIXTURE_SESSION_ID,
    }


def resume_record(agent_id: str, timestamp: str) -> dict:
    """A SendMessage that resumed a subagent. Not every SendMessage does:
    the same tool addresses other seats by name, and only a result carrying
    resumedAgentId says a subagent was reached."""
    return {
        "type": "user", "timestamp": timestamp, "uuid": f"uuid-resume-{agent_id}",
        "message": {"role": "user", "content": [{
            "tool_use_id": f"toolu_resume_{agent_id}", "type": "tool_result",
            "content": [{"type": "text", "text": "{\"success\":true}"}],
        }]},
        "toolUseResult": {
            "success": True, "message": f"Resuming agent {agent_id[:7]}",
            "resumedAgentId": agent_id,
            "pin": {"id": agent_id, "name": agent_id, "ref": "330caf"},
        },
        "sessionId": FIXTURE_SESSION_ID,
    }


def notification_body(task_id: str, status: str, summary: str) -> str:
    return (
        "<task-notification>\n"
        f"<task-id>{task_id}</task-id>\n"
        f"<tool-use-id>toolu_{task_id}</tool-use-id>\n"
        f"<output-file>/private/tmp/tasks/{task_id}.output</output-file>\n"
        f"<status>{status}</status>\n"
        f"<summary>{summary}</summary>\n"
        "<result>what the agent reported back</result>\n"
        "</task-notification>"
    )


def notification_records(task_id: str, status: str, summary: str, enqueued_at: str,
                         delivered_at: str = "", removed_at: str = "") -> list:
    """One notification as the transcript carries it: one to three records.

    Enqueued, optionally delivered as a user turn and copied as an attachment,
    optionally removed from the queue. Measured across three real session
    transcripts, no notification body ever appears more than three times, and
    four combinations occur — see `task_notification_text` in the writer for
    the counts. A subagent that finishes as its session is dying gets only the
    enqueue, which is why the derivation reads every combination — and why it
    must not count the echoes as separate events.

    This helper can emit all four records at once, which the real transcripts
    never do. That is deliberate: a fixture that emits the maximum exercises
    the de-duplication harder than a replay would.
    """
    body = notification_body(task_id, status, summary)
    records = [{"type": "queue-operation", "operation": "enqueue", "timestamp": enqueued_at,
                "sessionId": FIXTURE_SESSION_ID, "content": body}]
    if delivered_at:
        records.append({"type": "user", "timestamp": delivered_at, "uuid": f"uuid-notify-{task_id}",
                        "message": {"role": "user", "content": body},
                        "sessionId": FIXTURE_SESSION_ID})
        records.append({"type": "attachment", "timestamp": delivered_at,
                        "uuid": f"uuid-attach-{task_id}",
                        "attachment": {"type": "queued_command", "prompt": body},
                        "sessionId": FIXTURE_SESSION_ID})
    if removed_at:
        records.append({"type": "queue-operation", "operation": "remove", "timestamp": removed_at,
                        "sessionId": FIXTURE_SESSION_ID, "content": body})
    return records


def monitor_records(task_id: str, timestamp: str, killed_at: str) -> list:
    """A background monitor: launched by the Monitor tool, and killed later.

    It notifies through the very same channel as a subagent, so nothing but
    the launch record's shape tells the two apart — a monitor's result carries
    taskId and persistent, never agentId.
    """
    return [
        {"type": "user", "timestamp": timestamp, "uuid": f"uuid-monitor-{task_id}",
         "toolUseResult": {"taskId": task_id, "timeoutMs": 0, "persistent": True},
         "sessionId": FIXTURE_SESSION_ID},
        *notification_records(task_id, "killed", f'Monitor "{task_id}" stopped',
                              killed_at, delivered_at=killed_at),
    ]


# THIS TRANSCRIPT IS CONSTRUCTED, and its ids are synthetic on purpose.
#
# An earlier revision used the real agent ids from session
# 40a16b9c of 2026-08-23 and annotated them with events that did not happen to
# those agents — one was labelled as owning pull request #150's fix when it in
# fact produced #147, and two were labelled "never notified" and "finished as
# the session died" when both had completed, an hour apart, well before that
# session ended. A reader checking the fixture against the transcript would
# have found the labels false. Synthetic ids cannot make a false claim about a
# real agent, so the fixture says what it is instead of borrowing authority it
# does not have.
#
# One case here has NO real specimen anywhere in that session: every one of
# its nine subagents completed, so "spawned, never notified" has never been
# observed. It is exercised because the derivation must handle it — a subagent
# whose session dies before its notification is delivered — not because it was
# seen. That is precisely why the fixture is constructed rather than replayed.
FIXTURE_SESSION_ID = "00000000-0000-4000-8000-00000000f153"
FIXTURE_IDLE_AGENT = "afixture0idle0001"      # completed a round, then sat idle
FIXTURE_SILENT_AGENT = "afixture0silent01"    # spawned, never notified (no real specimen)
FIXTURE_UNDELIVERED_AGENT = "afixture0undeliv1"  # completion enqueued, never delivered
FIXTURE_MONITOR_TASK = "b41fasmax"            # a background monitor, not a subagent


def write_fixture_transcript(path: Path) -> None:
    records = [
        spawn_record(FIXTURE_IDLE_AGENT, "Fix ignored-path write blind spot",
                     "2026-08-23T19:55:24.756Z"),
        *monitor_records(FIXTURE_MONITOR_TASK, "2026-08-23T20:01:00.000Z",
                         "2026-08-23T22:08:12.478Z"),
        spawn_record(FIXTURE_UNDELIVERED_AGENT, "Fix output-path\ndirectory traceback",
                     "2026-08-23T20:12:30.967Z"),
        resume_record(FIXTURE_IDLE_AGENT, "2026-08-23T20:33:42.513Z"),
        *notification_records(FIXTURE_IDLE_AGENT, "completed", 'Agent "Fix ignored-path" finished',
                              "2026-08-23T20:52:59.408Z", delivered_at="2026-08-23T20:52:59.408Z",
                              removed_at="2026-08-23T20:53:10.725Z"),
        spawn_record(FIXTURE_SILENT_AGENT, "Review PR 150 independently",
                     "2026-08-23T21:32:36.303Z"),
        # Enqueued only: the session was killed before this one was delivered.
        *notification_records(FIXTURE_UNDELIVERED_AGENT, "completed",
                              'Agent "Fix output-path" finished', "2026-08-23T21:40:02.000Z"),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")


def run_spawned_subagent_roster_cases(workspace: Path):
    """The roster of subagents the retiring session spawned (ruled 2026-08-23).

    The motivating loss: a fixer subagent owning pull request #150 died with
    its session, and nothing in the handoff said it had ever existed.
    """
    transcript_path = workspace / "roster-fixture.jsonl"
    write_fixture_transcript(transcript_path)
    roster = writer.spawned_subagent_roster(transcript_path)
    by_id = {entry["agent_id"]: entry for entry in roster}

    check("the roster holds every subagent spawned and nothing else",
          [entry["agent_id"] for entry in roster]
          == [FIXTURE_IDLE_AGENT, FIXTURE_UNDELIVERED_AGENT, FIXTURE_SILENT_AGENT],
          str([entry["agent_id"] for entry in roster]))
    check("a background monitor is not a subagent",
          FIXTURE_MONITOR_TASK not in by_id and not any(
              FIXTURE_MONITOR_TASK in entry["agent_id"] for entry in roster),
          str(list(by_id)))

    # The orphan the field exists for: it had STOPPED, and still owned the
    # unfinished fix. A roster of running subagents would have dropped it.
    check("a subagent that spawned, was resumed and completed reports its completion",
          by_id[FIXTURE_IDLE_AGENT]["last_event"] == "completed",
          str(by_id[FIXTURE_IDLE_AGENT]))
    check("the completion is dated when it arrived, not when its last echo was filed",
          by_id[FIXTURE_IDLE_AGENT]["last_event_at"] == "2026-08-23T20:52:59Z",
          str(by_id[FIXTURE_IDLE_AGENT]))
    check("the spawn time survives the later events",
          by_id[FIXTURE_IDLE_AGENT]["spawned_at"] == "2026-08-23T19:55:24Z",
          str(by_id[FIXTURE_IDLE_AGENT]))

    # The trap Constraint B names: the spawn's tool_result arrives immediately,
    # so a matched pair proves nothing. Only a notification says it finished.
    check("a subagent that never notified reports its spawn as its last event",
          by_id[FIXTURE_SILENT_AGENT]["last_event"] == "spawned"
          and by_id[FIXTURE_SILENT_AGENT]["last_event_at"] == "2026-08-23T21:32:36Z",
          str(by_id[FIXTURE_SILENT_AGENT]))
    check("a completion enqueued but never delivered still counts as an event",
          by_id[FIXTURE_UNDELIVERED_AGENT]["last_event"] == "completed",
          str(by_id[FIXTURE_UNDELIVERED_AGENT]))
    check("a newline in a description cannot split the roster's line",
          "\n" not in by_id[FIXTURE_UNDELIVERED_AGENT]["description"]
          and by_id[FIXTURE_UNDELIVERED_AGENT]["description"]
          == "Fix output-path directory traceback",
          repr(by_id[FIXTURE_UNDELIVERED_AGENT]["description"]))

    field_lines = writer.spawned_subagent_field_lines(roster)
    check("each subagent gets its own numbered field",
          [line.split(":")[0] for line in field_lines]
          == ["spawned-subagent-1", "spawned-subagent-2", "spawned-subagent-3"],
          str(field_lines))
    check("a field line names the agent, its task, its spawn and its last event",
          field_lines[0] == (f'spawned-subagent-1: {FIXTURE_IDLE_AGENT} '
                             '"Fix ignored-path write blind spot" '
                             'spawned at 2026-08-23T19:55:24Z, '
                             'last event completed at 2026-08-23T20:52:59Z'),
          field_lines[0])

    # An empty transcript is not an error: a session may spawn nothing.
    empty_path = workspace / "roster-empty.jsonl"
    empty_path.write_text("", encoding="utf-8")
    check("a session that spawned nothing has an empty roster",
          writer.spawned_subagent_roster(empty_path) == [])
    check("an empty roster writes no fields",
          writer.spawned_subagent_field_lines([]) == [])


def run_roster_never_blocks_a_handoff_cases(workspace: Path):
    """A roster that cannot be derived must not cost the seat its handoff.

    Same principle as the branch-protection audit: the failure is reported on
    the console, where the retiring agent can act on it by naming its
    subagents in the next step by hand.
    """
    home = workspace / "fake-home"
    projects = home / ".claude" / "projects" / "-fixture-project"
    write_fixture_transcript(projects / f"{FIXTURE_SESSION_ID}.jsonl")
    handoffs = workspace / "roster-handoffs"
    handoffs.mkdir(parents=True, exist_ok=True)

    written = run_writer(
        handoffs, "carry on\n", "--agent", "rostercase",
        environment_overrides={"HOME": str(home), "CLAUDE_CODE_SESSION_ID": FIXTURE_SESSION_ID},
    )
    body = handoff_text(handoffs, "rostercase")
    check("the handoff carries one field per subagent the session spawned",
          body.count("spawned-subagent-") == 3, body)
    check("the writer reports the roster it recorded",
          "3 subagent(s) recorded" in written.stdout, written.stdout)

    # The roster is an ordinary field, so it must precede the verbatim block —
    # the block is last precisely so its content cannot shadow a real field.
    with_block = run_writer(
        handoffs, "first line\nsecond line\n", "--agent", "rosterblockcase",
        environment_overrides={"HOME": str(home), "CLAUDE_CODE_SESSION_ID": FIXTURE_SESSION_ID},
    )
    block_body = handoff_text(handoffs, "rosterblockcase")
    block_lines = block_body.splitlines()
    check("the roster is written before the verbatim block",
          max(index for index, line in enumerate(block_lines)
              if line.startswith("spawned-subagent-"))
          < block_lines.index("next-step-verbatim: <<END-OF-NEXT-STEP"),
          block_body)
    check("the roster fields read back as fields",
          writer.supervisor.parse_handoff_file(handoffs / "rosterblockcase-handoff.md")
          .get("spawned-subagent-3", "").startswith(FIXTURE_SILENT_AGENT),
          str(with_block.returncode))

    # No transcript for the named session: the handoff is still written.
    missing = run_writer(
        handoffs, "carry on\n", "--agent", "rostermissingcase",
        environment_overrides={"HOME": str(home),
                               "CLAUDE_CODE_SESSION_ID": "00000000-0000-0000-0000-000000000000"},
    )
    missing_body = handoff_text(handoffs, "rostermissingcase")
    check("a missing transcript still writes the handoff",
          "next-step: carry on" in missing_body, missing_body)
    check("a missing transcript writes no roster field",
          "spawned-subagent-" not in missing_body, missing_body)
    check("a missing transcript tells the agent to name its subagents by hand",
          "not derived" in missing.stdout and "by hand" in missing.stdout, missing.stdout)

    # No session id at all — the case every existing test already runs under.
    unidentified = run_writer(handoffs, "carry on\n", "--agent", "rosterunidentifiedcase")
    check("a session with no id still writes the handoff",
          (handoffs / "rosterunidentifiedcase-handoff.md").is_file(), unidentified.stderr)
    check("a session with no id says why the roster is missing",
          "CLAUDE_CODE_SESSION_ID is unset" in unidentified.stdout, unidentified.stdout)


with tempfile.TemporaryDirectory() as temporary_directory:
    run_collapse_cases()
    run_multi_line_next_step_cases(Path(temporary_directory))
    run_counter_cases(Path(temporary_directory))
    run_invocation_cases(Path(temporary_directory))
    run_liveness_report_cases(Path(temporary_directory))
    run_console_identity_case(Path(temporary_directory))
    run_agent_name_and_claim_cases(Path(temporary_directory))
    run_spawned_subagent_roster_cases(Path(temporary_directory))
    run_roster_never_blocks_a_handoff_cases(Path(temporary_directory))

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
