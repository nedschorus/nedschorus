#!/usr/bin/env python3
"""Tests for the handoff auto-trigger (handoff-context-threshold-hook.py).

The hook reads the session's used-context share from its transcript, so every
case drives it with a transcript file, exactly as the harness does.

Run: python3 scripts/handoff-context-threshold-hook-test.py
"""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HOOK_SCRIPT = Path(__file__).with_name("handoff-context-threshold-hook.py")

_hook_spec = importlib.util.spec_from_file_location("handoff_threshold_hook", HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_hook_spec)
_hook_spec.loader.exec_module(hook)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run_hook(stdin_payload, extra_arguments=()):
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT), *extra_arguments],
        input=json.dumps(stdin_payload), capture_output=True, text=True, check=False,
    )


SPAWNED_SUBAGENT_MARKER = hook.SPAWNED_SUBAGENT_STATUS


def run_hook_in_process(stdin_payload, scan_replacement=None, extra_arguments=()):
    """Call main() here rather than as a subprocess, so the scan can be made
    to fail on demand.

    The unreadable-transcript path cannot be reached end to end from outside:
    a transcript the process cannot read fails the used-share read first, and
    the hook exits before the scan runs. Replacing the scan is what puts
    main() in front of the case it has to handle — a scan that raises instead
    of answering — which is the behaviour under test here. That the real scan
    raises on a real unreadable file is pinned separately, above.
    """
    # main() calls work_in_flight, the one-pass scan for subagents and
    # background tasks alike; replacing anything else here would leave main()
    # running the real scan and these cases testing nothing.
    real_scan = hook.work_in_flight
    if scan_replacement is not None:
        hook.work_in_flight = scan_replacement
    captured_stderr = io.StringIO()
    real_stdin = sys.stdin
    sys.stdin = io.StringIO(json.dumps(stdin_payload))
    try:
        with contextlib.redirect_stderr(captured_stderr):
            code = hook.main(list(extra_arguments))
    except Exception as escaped:  # a main() that does not handle the scan's refusal
        # Reported as a failing outcome rather than allowed to abort the run:
        # "the hook crashed" is an answer these cases want to see and judge,
        # and a mutation check learns nothing from a run that stops early.
        code, captured_stderr = -1, io.StringIO(f"main() raised {escaped!r}")
    finally:
        sys.stdin = real_stdin
        hook.work_in_flight = real_scan
    return code, captured_stderr.getvalue()


def half_written_spawn_line(agent_id="a2573a7737ae643dc"):
    """A spawn record as it looks caught mid-append: the marker written, the
    closing braces not yet.

    The cut has to land after `async_launched`, because only a line carrying
    that marker is a spawn candidate at all — a cut before it would produce an
    ordinary unparsed line, which the scan is supposed to pass over, and the
    case would then pin nothing.
    """
    text = json.dumps(subagent_spawn_record(agent_id))[:-15]
    assert SPAWNED_SUBAGENT_MARKER in text, "fixture no longer carries the spawn marker"
    return text


def raises_could_not_read(transcript_path):
    """True when the scan refuses to answer for this transcript."""
    try:
        hook.spawned_subagent_ids_in_flight(str(transcript_path))
    except hook.TranscriptCouldNotBeFullyRead:
        return True
    return False


def usage_record(input_tokens, cache_read=0, cache_creation=0, model="claude-fable-5"):
    return {"type": "assistant", "message": {
        "model": model,
        "usage": {"input_tokens": input_tokens, "cache_read_input_tokens": cache_read,
                  "cache_creation_input_tokens": cache_creation},
    }}


def transcript_with_usage(directory, name, input_tokens, cache_read=0, cache_creation=0,
                          model="claude-fable-5"):
    path = Path(directory) / name
    path.write_text(
        json.dumps(usage_record(input_tokens, cache_read, cache_creation, model)) + "\n",
        encoding="utf-8",
    )
    return path


def transcript_of(directory, name, records):
    path = Path(directory) / name
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n",
                    encoding="utf-8")
    return path


# The three record shapes below were read off real transcripts under
# ~/.claude/projects/ on 2026-08-27 and trimmed to the fields the hook reads.
# Nothing there was modified.


def subagent_spawn_record(agent_id, description="a builder subagent"):
    """The Agent tool's async tool_result: the launch of one subagent."""
    return {
        "type": "user",
        "message": {"role": "user", "content": [{
            "tool_use_id": f"toolu_{agent_id}", "type": "tool_result",
            "content": [{"type": "text", "text": (
                "Async agent launched successfully.\n"
                f"agentId: {agent_id} (internal ID - do not mention to user.)")}],
        }]},
        "toolUseResult": {"isAsync": True, "status": "async_launched",
                          "agentId": agent_id, "description": description},
    }


def subagent_completion_record(agent_id, record_type="attachment"):
    """A completion notification, in either shape the harness delivers.

    `attachment` is what a busy session gets — six of the fourteen subagents
    that finished in the 2026-08-27 transcript produced only this shape —
    and `user` is what an idle one gets. The hook must read both.
    """
    notification = (
        "<task-notification>\n"
        f"<task-id>{agent_id}</task-id>\n"
        "<status>completed</status>\n"
        f'<summary>Agent "{agent_id}" finished</summary>\n'
        "</task-notification>"
    )
    if record_type == "attachment":
        return {"type": "attachment",
                "attachment": {"type": "queued_command", "prompt": notification}}
    return {"type": "user", "origin": {"kind": "task-notification"},
            "message": {"role": "user", "content": notification}}


def monitor_start_record(task_id="b45e25tz2"):
    """A Monitor tool result: a taskId, and no agentId — not a subagent."""
    return {
        "type": "user",
        "message": {"role": "user", "content": [{
            "tool_use_id": f"toolu_{task_id}", "type": "tool_result",
            "content": f"Monitor started (task {task_id}, persistent).",
        }]},
        "toolUseResult": {"taskId": task_id, "timeoutMs": 0, "persistent": True},
    }


# The two shapes below were read off session 44674c20 of 2026-09-14, the
# cold-read grid run that this deferral was extended for, and trimmed to the
# fields the hook reads.

GRID_LAUNCHED_AT = "2026-09-14T22:41:47.899Z"
GRID_FINISHED_AT = "2026-09-14T23:09:05.782Z"  # 27 minutes later, exit 0


def utc_iso(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def background_task_launch_record(task_id="b27dndn4c", launched_at=GRID_LAUNCHED_AT,
                                  description="Run the six-reviewer cold-read grid"):
    """The Bash tool's run_in_background tool_result: the launch of one
    background task. Its toolUseResult carries a backgroundTaskId and no
    agentId; the record's own timestamp is when the task started."""
    record = {
        "type": "user",
        "message": {"role": "user", "content": [{
            "tool_use_id": f"toolu_{task_id}", "type": "tool_result",
            "content": (
                f"Command running in background with ID: {task_id}. Output is "
                f"being written to: /tmp/tasks/{task_id}.output. You will be "
                "notified when it completes."),
            "is_error": False,
        }]},
        "toolUseResult": {"stdout": "", "stderr": "", "interrupted": False,
                          "isImage": False, "noOutputExpected": False,
                          "backgroundTaskId": task_id},
    }
    if launched_at is not None:
        record["timestamp"] = launched_at
    return record


def background_task_completion_record(task_id="b27dndn4c", finished_at=GRID_FINISHED_AT,
                                      status="completed"):
    """A background task's completion notification, in the busy-session shape
    (a queued_command attachment); the <task-id> tag is the same one a
    subagent's completion carries."""
    notification = (
        "<task-notification>\n"
        f"<task-id>{task_id}</task-id>\n"
        f"<tool-use-id>toolu_{task_id}</tool-use-id>\n"
        f"<output-file>/tmp/tasks/{task_id}.output</output-file>\n"
        f"<status>{status}</status>\n"
        f'<summary>Background command "Run the six-reviewer cold-read grid" '
        f"{status} (exit code 0)</summary>\n"
        "</task-notification>"
    )
    return {"type": "attachment", "timestamp": finished_at,
            "attachment": {"type": "queued_command", "prompt": notification,
                           "commandMode": "task-notification"}}


def bash_stdout_record_mentioning_the_marker():
    """An ordinary foreground Bash result whose stdout happens to contain the
    word backgroundTaskId — a grep over a transcript prints exactly this. Its
    toolUseResult has no such key, so it is not a launch."""
    return {
        "type": "user", "timestamp": GRID_LAUNCHED_AT,
        "message": {"role": "user", "content": [{
            "tool_use_id": "toolu_grep", "type": "tool_result",
            "content": '236:{"toolUseResult":{"backgroundTaskId":"b27dndn4c"}}',
        }]},
        "toolUseResult": {"stdout": '236:{"toolUseResult":{"backgroundTaskId":"b27dndn4c"}}',
                          "stderr": "", "interrupted": False, "isImage": False},
    }


with tempfile.TemporaryDirectory() as workspace:
    # --- The window table -------------------------------------------------
    check("window lookup knows the million-token models",
          hook.context_window_for("claude-fable-5") == 1_000_000
          and hook.context_window_for("claude-opus-5") == 1_000_000
          and hook.context_window_for("claude-sonnet-5") == 1_000_000)
    check("window lookup knows the 200k model",
          hook.context_window_for("claude-haiku-4-5-20251001") == 200_000)
    check("an unknown model falls back to the default window",
          hook.context_window_for("claude-something-unreleased") == 200_000)

    # --- Reading the used share from a transcript -------------------------
    transcript = Path(workspace) / "probe-transcript.jsonl"
    transcript.write_text(
        "\n".join(
            json.dumps(record)
            for record in (
                {"type": "user", "message": {"content": "hello"}},
                {"type": "assistant", "message": {
                    "model": "claude-fable-5",
                    "usage": {"input_tokens": 10, "cache_read_input_tokens": 90,
                              "cache_creation_input_tokens": 0},
                }},
                {"type": "assistant", "message": {
                    "model": "claude-fable-5",
                    "usage": {"input_tokens": 100_000, "cache_read_input_tokens": 500_000,
                              "cache_creation_input_tokens": 50_000},
                }},
            )
        ),
        encoding="utf-8",
    )
    used = hook.context_used_percentage_from_transcript(str(transcript))
    check("transcript reports the newest turn's usage as a percentage",
          used is not None and abs(used - 65.0) < 0.01, str(used))
    check("an absent transcript reports nothing",
          hook.context_used_percentage_from_transcript(str(Path(workspace) / "nope.jsonl")) is None)
    check("a transcript with no assistant turn reports nothing",
          hook.context_used_percentage_from_transcript(str(Path(workspace) / "empty.jsonl"))
          is None)

    # --- Tail read: the newest record must be found regardless of size ----
    newest = {"type": "assistant", "message": {
        "model": "claude-fable-5",
        "usage": {"input_tokens": 400_000, "cache_read_input_tokens": 0,
                  "cache_creation_input_tokens": 0},
    }}
    # A run of oversized tool-result records after the last usage-bearing
    # turn pushes it beyond the first read window — the doubling must reach it.
    buried = Path(workspace) / "buried-transcript.jsonl"
    filler = json.dumps({"type": "user", "message": {"content": [
        {"type": "tool_result", "content": "x" * 200_000}]}})
    buried.write_text(
        "\n".join([json.dumps(newest)] + [filler] * 6) + "\n", encoding="utf-8"
    )
    check(
        "tail read doubles past oversized records to reach the newest turn",
        abs(hook.context_used_percentage_from_transcript(str(buried)) - 40.0) < 0.01,
        str(hook.context_used_percentage_from_transcript(str(buried))),
    )

    # A transcript smaller than the first window is read whole in one pass.
    tiny = Path(workspace) / "tiny-transcript.jsonl"
    tiny.write_text(json.dumps(newest) + "\n", encoding="utf-8")
    check("tail read handles a transcript smaller than one window",
          abs(hook.context_used_percentage_from_transcript(str(tiny)) - 40.0) < 0.01)

    # The last line may be a partial write while the session is running.
    partial = Path(workspace) / "partial-tail-transcript.jsonl"
    partial.write_text(json.dumps(newest) + '\n{"type": "assistant", "mess',
                       encoding="utf-8")
    check("tail read skips a partially-written final record",
          abs(hook.context_used_percentage_from_transcript(str(partial)) - 40.0) < 0.01)

    # --- Which subagents are still in flight -------------------------------
    # A reincarnation kills the session's in-process subagents with it (2026-08-27),
    # so the hook has to know which of them are running before it fires.
    one_running = transcript_of(workspace, "one-subagent-running.jsonl", [
        usage_record(100_000, cache_read=450_000),
        subagent_spawn_record("a2573a7737ae643dc", "Build the cold-read tool"),
    ])
    check("a spawned subagent with no completion is in flight",
          hook.spawned_subagent_ids_in_flight(str(one_running)) == ["a2573a7737ae643dc"],
          str(hook.spawned_subagent_ids_in_flight(str(one_running))))

    one_finished = transcript_of(workspace, "one-subagent-finished.jsonl", [
        usage_record(100_000, cache_read=450_000),
        subagent_spawn_record("a2573a7737ae643dc"),
        subagent_completion_record("a2573a7737ae643dc"),
    ])
    check("a completion notification takes its subagent out of flight",
          hook.spawned_subagent_ids_in_flight(str(one_finished)) == [],
          str(hook.spawned_subagent_ids_in_flight(str(one_finished))))

    user_shape_finish = transcript_of(workspace, "finish-as-user-record.jsonl", [
        usage_record(100_000, cache_read=450_000),
        subagent_spawn_record("adbfe6c3d2693dd51"),
        subagent_completion_record("adbfe6c3d2693dd51", record_type="user"),
    ])
    check("a completion delivered as a user record counts too",
          hook.spawned_subagent_ids_in_flight(str(user_shape_finish)) == [],
          str(hook.spawned_subagent_ids_in_flight(str(user_shape_finish))))

    mixed = transcript_of(workspace, "mixed-subagents.jsonl", [
        usage_record(100_000, cache_read=450_000),
        subagent_spawn_record("aea1c60434f2b380d", "Zero-context review"),
        subagent_spawn_record("a2573a7737ae643dc", "Build the cold-read tool"),
        subagent_completion_record("aea1c60434f2b380d"),
        monitor_start_record(),
    ])
    check("only the unfinished subagent is in flight, in spawn order",
          hook.spawned_subagent_ids_in_flight(str(mixed)) == ["a2573a7737ae643dc"],
          str(hook.spawned_subagent_ids_in_flight(str(mixed))))

    monitor_only = transcript_of(workspace, "monitor-only.jsonl", [
        usage_record(100_000, cache_read=450_000),
        monitor_start_record("b45e25tz2"),
        subagent_completion_record("b45e25tz2"),
    ])
    check("a monitor is not a subagent — its result carries no agentId",
          hook.spawned_subagent_ids_in_flight(str(monitor_only)) == [],
          str(hook.spawned_subagent_ids_in_flight(str(monitor_only))))

    check("an absent transcript reports nothing in flight",
          hook.spawned_subagent_ids_in_flight(str(Path(workspace) / "nope.jsonl")) == [])

    # --- Which background tasks are still in flight -------------------------
    # A reincarnation kills a background Bash task with the session too. On
    # 2026-09-14 session 831c08ee handed off at 50% with the cold-read grid
    # running as one; the grid and its six reviewer cells died 12.7 minutes
    # in, and five of six reports were lost. User-ruled 2026-09-14: count a
    # background task as work in flight, bounded by a wall-clock wait, since
    # nothing in the transcript can tell a running task from a stuck one.
    thirty_minutes = 30 * 60
    grid_at_13_minutes = datetime(2026, 9, 14, 22, 54, 47, tzinfo=timezone.utc)
    grid_at_31_minutes = datetime(2026, 9, 14, 23, 12, 47, tzinfo=timezone.utc)

    grid_running = transcript_of(workspace, "grid-running.jsonl", [
        usage_record(100_000, cache_read=450_000),
        background_task_launch_record("b27dndn4c"),
        monitor_start_record("bwk7aucu8"),
        subagent_completion_record("bwk7aucu8"),  # a monitor event, not a finish
    ])
    flight = hook.work_in_flight(str(grid_running), thirty_minutes, now=grid_at_13_minutes)
    check("a background task younger than the wait, with no completion, is in flight",
          flight.background_task_ids == ["b27dndn4c"] and flight.subagent_ids == [],
          f"background={flight.background_task_ids} subagents={flight.subagent_ids}")

    grid_finished = transcript_of(workspace, "grid-finished.jsonl", [
        usage_record(100_000, cache_read=450_000),
        background_task_launch_record("b27dndn4c"),
        background_task_completion_record("b27dndn4c"),
    ])
    flight = hook.work_in_flight(str(grid_finished), thirty_minutes, now=grid_at_13_minutes)
    check("a background task's completion notification takes it out of flight",
          flight.background_task_ids == [], str(flight.background_task_ids))

    # Past the wait the task is presumed stuck or open-ended and no longer
    # holds the handoff: the transcript carries no pid, the Bash timeout is not
    # enforced on a background task, and its output file is silent when stdout
    # is redirected, as the grid's was. The wait is the only instrument.
    flight = hook.work_in_flight(str(grid_running), thirty_minutes, now=grid_at_31_minutes)
    check("a background task older than the wait is no longer in flight",
          flight.background_task_ids == [], str(flight.background_task_ids))

    # The launch is at 22:41:47.899, so this now makes the age exactly
    # 1800.000 s: a whole-second now left it 1799.101 and pinned nothing
    # (merge-lane review of #361, confirmed by mutation: <= flipped to <
    # still passed).
    flight = hook.work_in_flight(str(grid_running), thirty_minutes,
                                 now=datetime(2026, 9, 14, 23, 11, 47, 899000, tzinfo=timezone.utc))
    check("a background task exactly at the wait is still in flight",
          flight.background_task_ids == ["b27dndn4c"], str(flight.background_task_ids))

    # A launch whose age cannot be read fails closed, like everything else the
    # scan cannot tell: it counts, and the ceiling bounds it.
    undated_launch = transcript_of(workspace, "grid-undated-launch.jsonl", [
        usage_record(100_000, cache_read=450_000),
        background_task_launch_record("b27dndn4c", launched_at=None),
    ])
    flight = hook.work_in_flight(str(undated_launch), thirty_minutes, now=grid_at_31_minutes)
    check("a launch record with no timestamp is treated as in flight",
          flight.background_task_ids == ["b27dndn4c"], str(flight.background_task_ids))
    unparseable_launch = transcript_of(workspace, "grid-unparseable-launch-time.jsonl", [
        usage_record(100_000, cache_read=450_000),
        background_task_launch_record("b27dndn4c", launched_at="yesterday"),
    ])
    flight = hook.work_in_flight(str(unparseable_launch), thirty_minutes, now=grid_at_31_minutes)
    check("a launch record whose timestamp does not parse is treated as in flight",
          flight.background_task_ids == ["b27dndn4c"], str(flight.background_task_ids))

    # The marker is a key of toolUseResult, not a word: a grep over a
    # transcript prints the word into an ordinary Bash result.
    marker_in_stdout = transcript_of(workspace, "marker-in-stdout.jsonl", [
        usage_record(100_000, cache_read=450_000),
        bash_stdout_record_mentioning_the_marker(),
    ])
    flight = hook.work_in_flight(str(marker_in_stdout), thirty_minutes, now=grid_at_13_minutes)
    check("a Bash result that merely prints the word backgroundTaskId is not a launch",
          flight.background_task_ids == [], str(flight.background_task_ids))

    both_kinds = transcript_of(workspace, "subagent-and-background-task.jsonl", [
        usage_record(100_000, cache_read=450_000),
        subagent_spawn_record("a2573a7737ae643dc", "Build the cold-read tool"),
        background_task_launch_record("b27dndn4c"),
        background_task_launch_record("bzzzzzzzz"),
        background_task_completion_record("bzzzzzzzz"),
    ])
    flight = hook.work_in_flight(str(both_kinds), thirty_minutes, now=grid_at_13_minutes)
    check("the one-pass scan reports both kinds, each in launch order",
          flight.subagent_ids == ["a2573a7737ae643dc"]
          and flight.background_task_ids == ["b27dndn4c"],
          f"background={flight.background_task_ids} subagents={flight.subagent_ids}")
    check("the subagent-only view still excludes background tasks",
          hook.spawned_subagent_ids_in_flight(str(both_kinds)) == ["a2573a7737ae643dc"],
          str(hook.spawned_subagent_ids_in_flight(str(both_kinds))))

    truncated_launch = Path(workspace) / "truncated-background-launch.jsonl"
    launch_text = json.dumps(background_task_launch_record("b27dndn4c"))
    cut = launch_text.index('"backgroundTaskId"') + len('"backgroundTaskId": "b27d')
    truncated_launch.write_text(
        json.dumps(usage_record(100_000, cache_read=450_000)) + "\n" + launch_text[:cut],
        encoding="utf-8")
    try:
        hook.work_in_flight(str(truncated_launch), thirty_minutes, now=grid_at_13_minutes)
        refused = False
    except hook.TranscriptCouldNotBeFullyRead:
        refused = True
    check("a background launch record cut off mid-write is not read as nothing running",
          refused, "the scan answered instead of refusing")

    # --- "Could not tell" is not "nothing is running" ----------------------
    # A spawn record caught mid-append is not observed in practice — 841
    # transcripts, none ending mid-line, and 3,800 concurrent-append probes
    # showing no partial record (merge-lane review of #180). It is guarded
    # anyway because the costs are not symmetric: skipping such a line reports
    # an empty list, which main() fires on, killing the subagent whose spawn
    # record was the half-written line. These cases pin the refusal, and the
    # case below pins its scope — a record cut before its marker is not a
    # candidate, so this guard never sees it.
    truncated_spawn = Path(workspace) / "truncated-spawn.jsonl"
    truncated_spawn.write_text(
        json.dumps(usage_record(100_000, cache_read=450_000)) + "\n"
        + half_written_spawn_line(),
        encoding="utf-8")
    check("a spawn record cut off mid-write is not read as nothing running",
          raises_could_not_read(truncated_spawn),
          "the scan answered instead of refusing")

    # The fail-closed rule must not fire on every boundary: only a line that
    # carries the spawn marker is parsed at all, so the ordinary half-written
    # record — the common case — is passed over exactly as before.
    truncated_other = Path(workspace) / "truncated-ordinary-line.jsonl"
    truncated_other.write_text(
        json.dumps(usage_record(100_000, cache_read=450_000)) + "\n"
        + json.dumps(subagent_spawn_record("a2573a7737ae643dc")) + "\n"
        + '{"type": "assistant", "mess',
        encoding="utf-8")
    check("an ordinary half-written line still reports the flight normally",
          hook.spawned_subagent_ids_in_flight(str(truncated_other)) == ["a2573a7737ae643dc"],
          str(hook.spawned_subagent_ids_in_flight(str(truncated_other))))

    # A read that fails outright says so too. The suite assumes it is not run
    # as root, for whom mode 000 is still readable.
    unreadable = Path(workspace) / "unreadable-transcript.jsonl"
    unreadable.write_text(
        json.dumps(usage_record(100_000, cache_read=450_000)) + "\n", encoding="utf-8")
    os.chmod(unreadable, 0o000)
    try:
        check("an unreadable transcript is not read as nothing running",
              raises_could_not_read(unreadable))
    finally:
        os.chmod(unreadable, 0o600)

    # --- The hook, as the harness runs it: a subprocess reading stdin -----
    # Probe session ids are namespaced to this test; their fired markers land
    # in the real handoff directory and are removed on the way out.
    PROBE_SESSION_ID = "handoff-threshold-hook-test-session"
    marker_file = hook.HANDOFF_DIRECTORY / f"{PROBE_SESSION_ID}-handoff-asked"
    # The deferral cases get session ids of their own: one case asserts that no
    # marker exists, and a marker another case wrote would hide that failure.
    DEFERRAL_PROBE_SESSION_ID = "handoff-threshold-hook-test-deferral-session"
    CEILING_PROBE_SESSION_ID = "handoff-threshold-hook-test-ceiling-session"
    UNKNOWN_PROBE_SESSION_ID = "handoff-threshold-hook-test-unknown-count-session"
    deferral_marker_file = (
        hook.HANDOFF_DIRECTORY / f"{DEFERRAL_PROBE_SESSION_ID}-handoff-asked")
    ceiling_marker_file = (
        hook.HANDOFF_DIRECTORY / f"{CEILING_PROBE_SESSION_ID}-handoff-asked")
    # The second marker: written the first time the hook defers, so the
    # deferral is said once instead of at every boundary.
    deferred_marker_file = (
        hook.HANDOFF_DIRECTORY / f"{DEFERRAL_PROBE_SESSION_ID}-handoff-deferred")
    ceiling_deferred_marker_file = (
        hook.HANDOFF_DIRECTORY / f"{CEILING_PROBE_SESSION_ID}-handoff-deferred")
    unknown_marker_file = (
        hook.HANDOFF_DIRECTORY / f"{UNKNOWN_PROBE_SESSION_ID}-handoff-asked")
    unknown_deferred_marker_file = (
        hook.HANDOFF_DIRECTORY / f"{UNKNOWN_PROBE_SESSION_ID}-handoff-deferred")
    for probe_marker in (deferral_marker_file, ceiling_marker_file,
                         deferred_marker_file, ceiling_deferred_marker_file,
                         unknown_marker_file, unknown_deferred_marker_file):
        probe_marker.unlink(missing_ok=True)
    # On a fresh machine nothing has created the handoff directory yet.
    hook.HANDOFF_DIRECTORY.mkdir(parents=True, exist_ok=True)

    quiet = transcript_with_usage(workspace, "quiet.jsonl", 100_000, cache_read=100_000)
    loud = transcript_with_usage(workspace, "loud.jsonl", 100_000, cache_read=500_000,
                                 cache_creation=50_000)

    try:
        result = run_hook({"session_id": PROBE_SESSION_ID, "transcript_path": str(quiet)})
        check("hook stays silent below the threshold",
              result.returncode == 0 and not result.stderr.strip(),
              f"code {result.returncode}, stderr {result.stderr[:120]}")

        result = run_hook({"session_id": PROBE_SESSION_ID, "transcript_path": str(loud)})
        check("hook fires at the threshold", result.returncode == 2, f"code {result.returncode}")
        check("hook names the handoff skill", "handoff skill" in result.stderr, result.stderr[:160])
        # The message says to run the skill and nothing else: the skill carries the
        # procedure, and a second copy here went stale twice in one day.
        check("hook says only to run the skill",
              result.stderr.strip() == "Run the handoff skill now.", result.stderr[:160])

        result = run_hook({"session_id": PROBE_SESSION_ID, "transcript_path": str(loud)})
        check("hook fires only once per session", result.returncode == 0, f"code {result.returncode}")

        marker_file.unlink(missing_ok=True)
        result = run_hook({"session_id": PROBE_SESSION_ID, "transcript_path": str(loud)},
                          ("--threshold-used-percentage", "75"))
        check("threshold is configurable", result.returncode == 0, f"code {result.returncode}")

        # --- The deferral while subagents run (user-ruled 2026-08-27) -----
        # The transcripts below are the same session at three moments: one
        # subagent running, that subagent finished, and the context past the
        # ceiling. A monitor sits beside the subagent throughout, because the
        # count in the message must not include it.
        running = transcript_of(workspace, "deferral-running.jsonl", [
            usage_record(100_000, cache_read=450_000),  # 55% — over 50, under 65
            monitor_start_record(),
            subagent_spawn_record("a2573a7737ae643dc", "Build the cold-read tool"),
        ])
        finished = transcript_of(workspace, "deferral-finished.jsonl", [
            usage_record(100_000, cache_read=450_000),
            monitor_start_record(),
            subagent_spawn_record("a2573a7737ae643dc", "Build the cold-read tool"),
            subagent_completion_record("a2573a7737ae643dc"),
        ])
        past_ceiling = transcript_of(workspace, "deferral-past-ceiling.jsonl", [
            usage_record(100_000, cache_read=600_000),  # 70% — over the ceiling
            subagent_spawn_record("a2573a7737ae643dc", "Build the cold-read tool"),
        ])

        result = run_hook({"session_id": DEFERRAL_PROBE_SESSION_ID,
                           "transcript_path": str(running)})
        check("hook defers instead of firing while a subagent runs",
              result.returncode == 2 and "handoff deferred" in result.stderr,
              f"code {result.returncode}, stderr {result.stderr[:200]}")
        check("the deferral does not tell the agent to run the skill",
              "Run the handoff skill now." not in result.stderr, result.stderr[:200])
        check("the deferral counts subagents and not monitors",
              "1 subagent(s) run" in result.stderr, result.stderr[:200])
        check("the deferral says how full the context is",
              "Context at 55%" in result.stderr, result.stderr[:200])
        check("the deferral tells the agent to spawn no more subagents",
              "Spawn no new subagents" in result.stderr, result.stderr[:200])
        # The notice used to promise the handoff waits until the subagents
        # finish, full stop. The ceiling overrides that, and an agent reading
        # a guarantee its work is safe should be told the one thing that cuts
        # it off (merge-lane review of #180, 2026-08-28).
        check("the deferral names the ceiling as the other way the handoff fires",
              "ceiling" in result.stderr, result.stderr[:250])
        check("a deferral writes the deferral marker and not the fired one",
              deferred_marker_file.exists() and not deferral_marker_file.exists(),
              f"deferred={deferred_marker_file.exists()} "
              f"fired={deferral_marker_file.exists()}")

        # Said once, then quiet. Speaking at every boundary would refuse the
        # stop at every boundary, which drives an idle session into a loop of
        # short turns for as long as the subagent runs; the completion
        # notification wakes it without any help from this hook.
        result = run_hook({"session_id": DEFERRAL_PROBE_SESSION_ID,
                           "transcript_path": str(running)})
        check("a second deferred turn is silent, so the session can go idle",
              result.returncode == 0 and not result.stderr.strip(),
              f"code {result.returncode}, stderr {result.stderr[:200]}")
        check("a silent deferred turn still writes no fired marker",
              not deferral_marker_file.exists(), str(deferral_marker_file))

        result = run_hook({"session_id": DEFERRAL_PROBE_SESSION_ID,
                           "transcript_path": str(finished)})
        check("the same session fires once its subagent has finished",
              result.returncode == 2 and result.stderr.strip() == "Run the handoff skill now.",
              f"code {result.returncode}, stderr {result.stderr[:200]}")
        check("firing after a deferral writes the fired marker",
              deferral_marker_file.exists(), str(deferral_marker_file))
        # Left in place: the fired marker is what governs repeats, and
        # clearing this one at the fire would tell nobody anything.
        check("firing leaves the deferral marker where it was",
              deferred_marker_file.exists(), str(deferred_marker_file))
        deferral_marker_file.unlink(missing_ok=True)
        deferred_marker_file.unlink(missing_ok=True)

        # The ceiling overrides a deferral already in progress: this session
        # deferred at 55%, kept working, and arrived at 70% with the subagent
        # still running.
        result = run_hook({"session_id": CEILING_PROBE_SESSION_ID,
                           "transcript_path": str(running)})
        check("the ceiling session defers first, as the deferral session did",
              result.returncode == 2 and "handoff deferred" in result.stderr,
              f"code {result.returncode}, stderr {result.stderr[:200]}")
        result = run_hook({"session_id": CEILING_PROBE_SESSION_ID,
                           "transcript_path": str(past_ceiling)})
        check("above the ceiling the handoff fires with a subagent still running",
              result.returncode == 2 and result.stderr.strip() == "Run the handoff skill now.",
              f"code {result.returncode}, stderr {result.stderr[:200]}")
        check("firing above the ceiling writes the fired marker",
              ceiling_marker_file.exists(), str(ceiling_marker_file))
        ceiling_marker_file.unlink(missing_ok=True)
        ceiling_deferred_marker_file.unlink(missing_ok=True)

        result = run_hook({"session_id": CEILING_PROBE_SESSION_ID,
                           "transcript_path": str(running)},
                          ("--ceiling-used-percentage", "50"))
        check("a lowered ceiling fires at a share that would otherwise defer",
              result.returncode == 2 and result.stderr.strip() == "Run the handoff skill now.",
              f"code {result.returncode}, stderr {result.stderr[:200]}")
        ceiling_marker_file.unlink(missing_ok=True)
        ceiling_deferred_marker_file.unlink(missing_ok=True)

        # --- A scan that could not finish defers, and says the count is
        # unknown (merge-lane review of #180, 2026-08-28). Firing here would
        # kill the very subagent whose spawn record could not be read.
        truncated_at_threshold = Path(workspace) / "deferral-truncated-spawn.jsonl"
        truncated_at_threshold.write_text(
            json.dumps(usage_record(100_000, cache_read=450_000)) + "\n"  # 55%
            + half_written_spawn_line(),
            encoding="utf-8")
        result = run_hook({"session_id": UNKNOWN_PROBE_SESSION_ID,
                           "transcript_path": str(truncated_at_threshold)})
        check("a truncated spawn record defers instead of firing",
              result.returncode == 2 and "handoff deferred" in result.stderr,
              f"code {result.returncode}, stderr {result.stderr[:200]}")
        check("the deferral says the count is unknown, and does not invent one",
              "unknown" in result.stderr and "subagent(s) run" not in result.stderr,
              result.stderr[:250])
        check("a truncated spawn record does not tell the agent to hand off",
              "Run the handoff skill now." not in result.stderr, result.stderr[:200])
        check("an unknown-count deferral writes the deferral marker, not the fired one",
              unknown_deferred_marker_file.exists() and not unknown_marker_file.exists(),
              f"deferred={unknown_deferred_marker_file.exists()} "
              f"fired={unknown_marker_file.exists()}")
        unknown_marker_file.unlink(missing_ok=True)
        unknown_deferred_marker_file.unlink(missing_ok=True)

        # The read-error path, reached where it can be reached: main() in
        # front of a scan that raises. See run_hook_in_process.
        def scan_that_cannot_read(_transcript_path, *_arguments, **_keywords):
            raise hook.TranscriptCouldNotBeFullyRead("unreadable in this test")

        code, stderr = run_hook_in_process(
            {"session_id": UNKNOWN_PROBE_SESSION_ID,
             "transcript_path": str(running)},
            scan_replacement=scan_that_cannot_read)
        check("an unreadable transcript at the scan defers rather than firing",
              code == 2 and "handoff deferred" in stderr and "unknown" in stderr,
              f"code {code}, stderr {stderr[:250]}")
        check("the unreadable-transcript deferral writes no fired marker",
              not unknown_marker_file.exists(), str(unknown_marker_file))
        unknown_marker_file.unlink(missing_ok=True)
        unknown_deferred_marker_file.unlink(missing_ok=True)

        # Above the ceiling an unknown count postpones nothing: the ceiling is
        # what bounds a wait whose end the hook cannot see.
        code, stderr = run_hook_in_process(
            {"session_id": UNKNOWN_PROBE_SESSION_ID,
             "transcript_path": str(past_ceiling)},
            scan_replacement=scan_that_cannot_read)
        check("above the ceiling an unknown count still fires the handoff",
              code == 2 and stderr.strip() == "Run the handoff skill now.",
              f"code {code}, stderr {stderr[:200]}")
        unknown_marker_file.unlink(missing_ok=True)
        unknown_deferred_marker_file.unlink(missing_ok=True)

        below_threshold = transcript_of(workspace, "deferral-below-threshold.jsonl", [
            usage_record(100_000, cache_read=300_000),  # 40% — nothing to say yet
            subagent_spawn_record("a2573a7737ae643dc", "Build the cold-read tool"),
        ])
        result = run_hook({"session_id": DEFERRAL_PROBE_SESSION_ID,
                           "transcript_path": str(below_threshold)})
        check("below the threshold a running subagent draws no message at all",
              result.returncode == 0 and not result.stderr.strip(),
              f"code {result.returncode}, stderr {result.stderr[:200]}")

        # --- The deferral while a background task runs (user-ruled 2026-09-14) --
        # The same session at four moments: the grid launched ten minutes ago,
        # the grid finished, the grid launched two hours ago (presumed stuck or
        # open-ended), and the context past the ceiling. These run the hook as
        # the harness does, so the launch times are relative to the real clock.
        BACKGROUND_PROBE_SESSION_ID = "handoff-threshold-hook-test-background-task-session"
        background_marker_file = (
            hook.HANDOFF_DIRECTORY / f"{BACKGROUND_PROBE_SESSION_ID}-handoff-asked")
        background_deferred_marker_file = (
            hook.HANDOFF_DIRECTORY / f"{BACKGROUND_PROBE_SESSION_ID}-handoff-deferred")
        background_marker_file.unlink(missing_ok=True)
        background_deferred_marker_file.unlink(missing_ok=True)
        clock = datetime.now(timezone.utc)
        ten_minutes_ago = utc_iso(clock - timedelta(minutes=10))
        two_hours_ago = utc_iso(clock - timedelta(hours=2))

        grid_young = transcript_of(workspace, "background-task-young.jsonl", [
            usage_record(100_000, cache_read=450_000),  # 55% — over 50, under 65
            monitor_start_record("bwk7aucu8"),
            background_task_launch_record("b27dndn4c", launched_at=ten_minutes_ago),
        ])
        grid_done = transcript_of(workspace, "background-task-finished.jsonl", [
            usage_record(100_000, cache_read=450_000),
            monitor_start_record("bwk7aucu8"),
            background_task_launch_record("b27dndn4c", launched_at=ten_minutes_ago),
            background_task_completion_record("b27dndn4c", finished_at=utc_iso(clock)),
        ])
        grid_old = transcript_of(workspace, "background-task-old.jsonl", [
            usage_record(100_000, cache_read=450_000),
            background_task_launch_record("b27dndn4c", launched_at=two_hours_ago),
        ])
        grid_past_ceiling = transcript_of(workspace, "background-task-past-ceiling.jsonl", [
            usage_record(100_000, cache_read=600_000),  # 70% — over the ceiling
            background_task_launch_record("b27dndn4c", launched_at=ten_minutes_ago),
        ])
        both_running = transcript_of(workspace, "subagent-and-background-task-running.jsonl", [
            usage_record(100_000, cache_read=450_000),
            subagent_spawn_record("a2573a7737ae643dc", "Build the cold-read tool"),
            background_task_launch_record("b27dndn4c", launched_at=ten_minutes_ago),
        ])

        try:
            result = run_hook({"session_id": BACKGROUND_PROBE_SESSION_ID,
                               "transcript_path": str(grid_young)})
            check("hook defers instead of firing while a background task runs",
                  result.returncode == 2 and "handoff deferred" in result.stderr,
                  f"code {result.returncode}, stderr {result.stderr[:200]}")
            check("the background-task deferral counts the task and not the monitor",
                  "1 background task(s) run" in result.stderr
                  and "subagent(s)" not in result.stderr.split("Spawn")[0],
                  result.stderr[:250])
            check("the deferral tells the agent to start no new background tasks",
                  "start no new background tasks" in result.stderr, result.stderr[:250])
            check("the deferral names the wait as a way the handoff fires",
                  "30 minute" in result.stderr, result.stderr[:300])
            check("a background-task deferral writes the deferral marker and not the fired one",
                  background_deferred_marker_file.exists() and not background_marker_file.exists(),
                  f"deferred={background_deferred_marker_file.exists()} "
                  f"fired={background_marker_file.exists()}")

            result = run_hook({"session_id": BACKGROUND_PROBE_SESSION_ID,
                               "transcript_path": str(grid_young)})
            check("a second deferred turn behind a background task is silent",
                  result.returncode == 0 and not result.stderr.strip(),
                  f"code {result.returncode}, stderr {result.stderr[:200]}")

            result = run_hook({"session_id": BACKGROUND_PROBE_SESSION_ID,
                               "transcript_path": str(grid_done)})
            check("the same session fires once its background task has finished",
                  result.returncode == 2 and result.stderr.strip() == "Run the handoff skill now.",
                  f"code {result.returncode}, stderr {result.stderr[:200]}")
            background_marker_file.unlink(missing_ok=True)
            background_deferred_marker_file.unlink(missing_ok=True)

            result = run_hook({"session_id": BACKGROUND_PROBE_SESSION_ID,
                               "transcript_path": str(grid_old)})
            check("a background task older than the wait does not hold the handoff",
                  result.returncode == 2 and result.stderr.strip() == "Run the handoff skill now.",
                  f"code {result.returncode}, stderr {result.stderr[:200]}")
            check("an outlived wait writes no deferral marker",
                  not background_deferred_marker_file.exists(),
                  str(background_deferred_marker_file))
            background_marker_file.unlink(missing_ok=True)

            # The wait ends a deferral already in progress: this session
            # deferred while the task was young, went quiet, and reaches its
            # next boundary after the task has outlived the wait. The deferred
            # marker must not keep it quiet then — the marker only stops the
            # notice repeating, and an empty flight fires whatever it says.
            result = run_hook({"session_id": BACKGROUND_PROBE_SESSION_ID,
                               "transcript_path": str(grid_young)})
            check("the outlived-wait session defers first, as the young-task session did",
                  result.returncode == 2 and "handoff deferred" in result.stderr
                  and background_deferred_marker_file.exists(),
                  f"code {result.returncode}, stderr {result.stderr[:200]}")
            result = run_hook({"session_id": BACKGROUND_PROBE_SESSION_ID,
                               "transcript_path": str(grid_old)})
            check("a session that deferred fires once its background task outlives the wait",
                  result.returncode == 2 and result.stderr.strip() == "Run the handoff skill now."
                  and background_marker_file.exists(),
                  f"code {result.returncode}, stderr {result.stderr[:200]}")
            background_marker_file.unlink(missing_ok=True)
            background_deferred_marker_file.unlink(missing_ok=True)

            result = run_hook({"session_id": BACKGROUND_PROBE_SESSION_ID,
                               "transcript_path": str(grid_young)},
                              ("--background-task-wait-minutes", "5"))
            check("the wait is configurable: a five-minute wait fires on a ten-minute-old task",
                  result.returncode == 2 and result.stderr.strip() == "Run the handoff skill now.",
                  f"code {result.returncode}, stderr {result.stderr[:200]}")
            background_marker_file.unlink(missing_ok=True)
            background_deferred_marker_file.unlink(missing_ok=True)

            result = run_hook({"session_id": BACKGROUND_PROBE_SESSION_ID,
                               "transcript_path": str(grid_past_ceiling)})
            check("above the ceiling the handoff fires with a background task still running",
                  result.returncode == 2 and result.stderr.strip() == "Run the handoff skill now.",
                  f"code {result.returncode}, stderr {result.stderr[:200]}")
            background_marker_file.unlink(missing_ok=True)
            background_deferred_marker_file.unlink(missing_ok=True)

            result = run_hook({"session_id": BACKGROUND_PROBE_SESSION_ID,
                               "transcript_path": str(both_running)})
            check("a deferral behind both kinds names both",
                  "1 subagent(s) and 1 background task(s) run" in result.stderr,
                  result.stderr[:250])
        finally:
            background_marker_file.unlink(missing_ok=True)
            background_deferred_marker_file.unlink(missing_ok=True)

        result = run_hook({})
        check("hook stays silent with no session id", result.returncode == 0)

        result = run_hook({"session_id": "session-with-no-transcript"})
        check("hook stays silent with no transcript path", result.returncode == 0)

        result = run_hook({"session_id": "session-before-first-turn",
                           "transcript_path": str(Path(workspace) / "not-written-yet.jsonl")})
        check("hook stays silent before the first turn completes", result.returncode == 0)
    finally:
        marker_file.unlink(missing_ok=True)
        deferral_marker_file.unlink(missing_ok=True)
        ceiling_marker_file.unlink(missing_ok=True)
        deferred_marker_file.unlink(missing_ok=True)
        ceiling_deferred_marker_file.unlink(missing_ok=True)
        unknown_marker_file.unlink(missing_ok=True)
        unknown_deferred_marker_file.unlink(missing_ok=True)

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
