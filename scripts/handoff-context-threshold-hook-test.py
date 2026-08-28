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
    real_scan = hook.spawned_subagent_ids_in_flight
    if scan_replacement is not None:
        hook.spawned_subagent_ids_in_flight = scan_replacement
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
        hook.spawned_subagent_ids_in_flight = real_scan
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
    # A recycle kills the session's in-process subagents with it (2026-08-27),
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

    # --- "Could not tell" is not "nothing is running" ----------------------
    # The hook reads a transcript its session is still appending to, so the
    # last line is often half-written. Skipping such a line here would report
    # an empty list, which main() would fire on — killing the subagent whose
    # spawn record was the half-written line (merge-lane review of #180).
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
        def scan_that_cannot_read(_transcript_path):
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
