#!/usr/bin/env python3
"""Tests for the handoff auto-trigger (handoff-context-threshold-hook.py).

The hook reads the session's used-context share from its transcript, so every
case drives it with a transcript file, exactly as the harness does.

Every case runs under a HOME of this suite's own, so the markers the hook
writes land in a directory this suite made and never in the real
~/.claude/handoffs. HOME is what decides that directory, because the hook
computes HANDOFF_DIRECTORY from Path.home() at import -- so the redirect
happens before the hook module is loaded below, and it reaches the subprocess
cases too, which inherit this environment through run_hook. The sibling suite
post-compaction-session-continues-hook-test.py is the pattern followed here.

MEASURED 2026-09-21, before the redirect existed: two runs of this suite at
once both went red, on 3 attempts of 3, with 3 to 9 cases failing and a
different set each time. The probe session ids below are fixed strings, so
concurrent runs shared one namespace in one real directory and each deleted
the other's markers out from under the other's assertions. The reviewer of
"systemd unit installer: --remove reports a failed disable or reload and exits
1" had already recorded this suite creating the real ~/.claude/handoffs on a
fresh machine; that is the same defect seen from its quiet side.

Run: python3 scripts/handoff-context-threshold-hook-test.py
"""

import argparse
import atexit
import ast
import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# The suite's own HOME; the module docstring says why. LAUNCH_HOME is captured
# before the redirect, because the first case pins that the hook's directory is
# this suite's own and not the one the suite was started under.
LAUNCH_HOME = Path.home()
SUITE_HOME = Path(tempfile.mkdtemp(prefix="handoff-threshold-hook-test-home-"))
os.environ["HOME"] = str(SUITE_HOME)
atexit.register(lambda: shutil.rmtree(SUITE_HOME, ignore_errors=True))

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


HANDOFF_INSTRUCTION_PATTERN = re.compile(
    r"This session has used \d+% of its context window, which has reached the "
    r"reincarnation threshold\. Run the /handoff skill now\.")


DO_NOT_RUN_HANDOFF_SKILL_YET_INSTRUCTION = (
    "Do not run the /handoff skill now; carry on with your work, and a later "
    "system message will tell you when to run it.")


for notice in (hook.HANDOFF_DEFERRED_NOTICE, hook.HANDOFF_DEFERRED_UNKNOWN_COUNT_NOTICE):
    check("the deferral timeout counts a task as finished without stopping the task",
          "even if it still runs" in notice,
          notice)
    check("the deferral says the handoff stops remaining work when the handoff comes",
          "when the handoff comes, it stops whatever is still running." in notice, notice)

guard_source = HOOK_SCRIPT.parent.parent / ".claude/guard-hooks/handoff-deferral-cold-read-full-run-launch-refusal-hook.py"
for statement in ast.parse(guard_source.read_text(encoding="utf-8")).body:
    if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "COLD_READ_FULL_RUN_REFUSED_AND_SAVED_REASON"
            for target in statement.targets):
        reason = ast.literal_eval(statement.value)
        check("the refusal says the handoff writer adds the command without agent action",
              "The handoff writer script, nc-systems/handoff/handoff-write-and-check-supervisor.py,"
              " adds the command to your session-handoff, so you need not." in reason,
              reason)
        break
else:
    check("the refusal reason exists", False)


def opens_a_line_with_do_not_run_handoff_skill_yet(stderr):
    return any(line.startswith(DO_NOT_RUN_HANDOFF_SKILL_YET_INSTRUCTION)
               for line in stderr.splitlines())


def is_handoff_instruction(stderr):
    """The hook's whole message is the handoff instruction, the share filled in."""
    return HANDOFF_INSTRUCTION_PATTERN.fullmatch(stderr.strip()) is not None


COMPACTED_HANDOFF_INSTRUCTION_PATTERN = re.compile(
    r"This session has used \d+% \(\d+% counting the tokens its compactions dropped, "
    r"the figure compared with the threshold and the ceiling\) "
    r"of its context window, which has reached the reincarnation threshold\. "
    r"Run the /handoff skill now\.")


def is_compacted_handoff_instruction(stderr):
    """The handoff instruction for a compacted session, both shares filled in."""
    return COMPACTED_HANDOFF_INSTRUCTION_PATTERN.fullmatch(stderr.strip()) is not None


def with_background_tasks_list(stdin_payload, background_tasks_list_is_missing):
    """Claude Code sends the list at every Stop; a payload without one gets an empty list,
    unless the case is about a payload that lacks it."""
    if background_tasks_list_is_missing or hook.BACKGROUND_TASKS_PAYLOAD_KEY in stdin_payload:
        return stdin_payload
    return {**stdin_payload, hook.BACKGROUND_TASKS_PAYLOAD_KEY: []}


def list_entry(task_id, task_type, status="running", command=None):
    """One entry of Claude Code's background_tasks list, trimmed from real Stop hook input."""
    entry = {"id": task_id, "type": task_type, "status": status,
             "description": f"a {task_type}"}
    if command is not None:
        entry["command"] = command
    return entry


def run_hook(stdin_payload, extra_arguments=(), extra_environment=None,
             background_tasks_list_is_missing=False):
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT), *extra_arguments],
        input=json.dumps(with_background_tasks_list(stdin_payload,
                                                    background_tasks_list_is_missing)),
        capture_output=True, text=True, check=False,
        env={**os.environ, **(extra_environment or {})},
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
    # main() counts running work with work_in_flight_from_background_tasks alone;
    # replacing anything else here would leave main() running the real reader and
    # these cases testing nothing.
    real_scan = hook.work_in_flight_from_background_tasks
    if scan_replacement is not None:
        hook.work_in_flight_from_background_tasks = scan_replacement
    captured_stderr = io.StringIO()
    real_stdin = sys.stdin
    sys.stdin = io.StringIO(json.dumps(with_background_tasks_list(stdin_payload, False)))
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
        hook.work_in_flight_from_background_tasks = real_scan
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


def raises_list_could_not_read(entries, transcript_path):
    """True when the list reader refuses rather than answering for the transcripts."""
    try:
        hook.work_in_flight_from_background_tasks(
            entries, str(transcript_path))
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


def compaction_record(cumulative_dropped_tokens, pre_tokens=448_678, post_tokens=24_858):
    """A compaction record as Claude Code writes it, trimmed to the fields beside the one the hook reads."""
    return {
        "type": "system", "subtype": "compact_boundary",
        "content": "Conversation compacted", "level": "info",
        "timestamp": "2026-10-21T05:54:37.110Z",
        "compactMetadata": {"trigger": "auto", "preTokens": pre_tokens,
                            "postTokens": post_tokens,
                            "cumulativeDroppedTokens": cumulative_dropped_tokens},
    }


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


# A real interim notification, trimmed to the fields the hook reads.
INCIDENT_SUBAGENT_ID = "a68d25248370ee861"
INCIDENT_INTERIM_NOTIFICATION = (
    "<task-notification>\n"
    "<task-id>a68d25248370ee861</task-id>\n"
    "<tool-use-id>toolu_01ND98sByPRjfgSm7HcRmtiJ</tool-use-id>\n"
    "<output-file>/private/tmp/claude-501/-Users-el-agents-cold-read-research/"
    "edfee8d0-7356-4230-ab2f-89ee493a6701/tasks/a68d25248370ee861.output</output-file>\n"
    "<status>completed</status>\n"
    '<summary>Agent "Fix-round for PR 2045" is waiting on its own background work</summary>\n'
    "<note>This agent stopped with background work of its own still running. It may resume "
    "on its own when that work completes or reports, and the same task-id notifies again if "
    "it does; the result below may be interim.</note>\n"
    "<result>Waiting on the test run.</result>\n"
    "<usage><subagent_tokens>284937</subagent_tokens><tool_uses>35</tool_uses>"
    "<duration_ms>816408</duration_ms></usage>\n"
    "</task-notification>")
# The other interim form: the <result> says the report has not come yet.
NOT_YET_REPORTED_INTERIM_NOTIFICATION = (
    "<task-notification>\n"
    "<task-id>a68d25248370ee861</task-id>\n"
    "<status>completed</status>\n"
    '<summary>Agent "Fix marker-before-ship in grid PR" finished</summary>\n'
    "<result>This agent has not reported yet: it is waiting on its own background work and "
    "will deliver its report through SubagentHandback when that finishes.\n</result>\n"
    "</task-notification>")
# The final notification for the same task-id.
FINAL_NOTIFICATION_AFTER_INTERIM = (
    "<task-notification>\n"
    "<task-id>a68d25248370ee861</task-id>\n"
    "<status>completed</status>\n"
    '<summary>Agent "Fable check of decisions 4 and 5" finished</summary>\n'
    "<note>A task-notification fires each time this agent stops with no live background "
    "children of its own. The user can send it another message and resume it, so the same "
    "task-id may notify more than once.</note>\n"
    '<result>This agent\'s report was delivered to you as a message from "a68d25248370ee861" '
    "(its SubagentHandback call). Read it there; it is not repeated here.\n</result>\n"
    "</task-notification>")


def notification_records(notification, timestamp="2026-10-27T21:31:58.572Z"):
    """The enqueue and the user record the harness writes for one delivered notification."""
    return [
        {"type": "queue-operation", "operation": "enqueue", "timestamp": timestamp,
         "content": notification},
        {"type": "user", "timestamp": timestamp, "origin": {"kind": "task-notification"},
         "message": {"role": "user", "content": notification}},
    ]


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


def task_stop_record(task_id, task_type):
    """A TaskStop tool_result that stopped the task, read off a real transcript and trimmed to
    the fields the hook reads."""
    message = f"Successfully stopped task: {task_id} (Sweep this seat's leftover worktrees)"
    result = {"message": message, "task_id": task_id, "task_type": task_type,
              "command": "Sweep this seat's leftover worktrees"}
    return {
        "type": "user", "timestamp": GRID_LAUNCHED_AT,
        "message": {"role": "user", "content": [{
            "tool_use_id": f"toolu_stop_{task_id}", "type": "tool_result",
            "content": json.dumps(result)}]},
        "toolUseResult": result,
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


# A subagent that finished, was resumed by SendMessage, and finished again, read off a real
# transcript; trimmed to the fields the hook reads.
RESUMED_SUBAGENT_ID = "ac25f42af3e1481af"
RESUMED_SUBAGENT_FINAL_NOTIFICATION = (
    "<task-notification>\n"
    "<task-id>ac25f42af3e1481af</task-id>\n"
    "<tool-use-id>toolu_01AgYc8eUQGoaYS9jynrNu53</tool-use-id>\n"
    "<status>completed</status>\n"
    '<summary>Agent "Fix GHI 1112\'s fast-read findings" finished</summary>\n'
    "<note>A task-notification fires each time this agent stops with no live background "
    "children of its own. The user can send it another message and resume it, so the same "
    "task-id may notify more than once.</note>\n"
    '<result>This agent\'s report was delivered to you as a message from "ac25f42af3e1481af" '
    "(its SubagentHandback call). Read it there; it is not repeated here.\n</result>\n"
    "</task-notification>")


def subagent_resume_record(agent_id=RESUMED_SUBAGENT_ID, timestamp="2026-10-13T19:35:53.110Z"):
    """The SendMessage tool_result that resumes a finished subagent."""
    result = {"success": True, "message": f"Resuming agent {agent_id[:7]}",
              "resumedAgentId": agent_id,
              "pin": {"id": agent_id, "name": agent_id, "ref": "6f1f0b"}}
    return {
        "type": "user", "timestamp": timestamp,
        "message": {"role": "user", "content": [{
            "tool_use_id": "toolu_01AHzbGageT9pSdG6yHP3VB5", "type": "tool_result",
            "content": [{"type": "text", "text": json.dumps(result)}]}]},
        "toolUseResult": result,
    }


def bash_stdout_record_mentioning_a_resume():
    """A foreground Bash result whose stdout is a grep hit on a resume record, as a search of
    transcripts for resumedAgentId prints it; its own toolUseResult has no such key."""
    hit = '838:{"toolUseResult":{"resumedAgentId":"ac25f42af3e1481af"}}'
    return {
        "type": "user", "timestamp": "2026-10-13T19:40:00.000Z",
        "message": {"role": "user", "content": [{
            "tool_use_id": "toolu_grep_resume", "type": "tool_result", "content": hit}]},
        "toolUseResult": {"stdout": hit, "stderr": "", "interrupted": False, "isImage": False},
    }


with tempfile.TemporaryDirectory() as workspace:
    # --- The suite's own handoff directory -------------------------------
    # Fails if the redirect above is removed: without it HANDOFF_DIRECTORY is
    # the real ~/.claude/handoffs, which is under the launch HOME. The
    # subprocess half needs no case of its own -- every marker case below
    # asserts a path under SUITE_HOME, so a subprocess that did not inherit
    # this environment would fail those instead.
    check("the hook's handoff directory is this suite's own, not the real one",
          SUITE_HOME in hook.HANDOFF_DIRECTORY.parents
          and LAUNCH_HOME not in hook.HANDOFF_DIRECTORY.parents,
          f"HANDOFF_DIRECTORY={hook.HANDOFF_DIRECTORY}, "
          f"suite HOME={SUITE_HOME}, launch HOME={LAUNCH_HOME}")

    # --- The window table -------------------------------------------------
    check("window lookup knows the million-token models",
          hook.context_window_tokens_from_table_or_none("claude-fable-5") == 1_000_000
          and hook.context_window_tokens_from_table_or_none("claude-opus-5") == 1_000_000
          and hook.context_window_tokens_from_table_or_none("claude-sonnet-5") == 1_000_000)
    check("window lookup knows the 200k model by a table prefix",
          hook.context_window_tokens_from_table_or_none("claude-haiku-4-5-20251001") == 200_000)
    check("window lookup finds no window for a model id not in the table",
          hook.context_window_tokens_from_table_or_none("claude-something-unreleased") is None)

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

    # --- A multi-pass reply: the largest pass, not the sum ----------------
    # Measured 2026-09-17 in session 8b3cd015: an advisor reply's top-level
    # cache_read_input_tokens was 1,111,912, the sum of two passes of this
    # model, against a real context of about 557,000. Read as the sum, this
    # hook sees 111% of the window and fires above its own ceiling -- with a
    # cold-read grid running, the failure that cost five of six reports on
    # 2026-09-14.
    advisor_reply = {"type": "assistant", "message": {
        "model": "claude-fable-5",
        "usage": {
            "input_tokens": 4, "cache_read_input_tokens": 1_111_912,
            "cache_creation_input_tokens": 2_013,
            "iterations": [
                {"type": "message", "input_tokens": 2,
                 "cache_read_input_tokens": 555_460, "cache_creation_input_tokens": 992},
                {"type": "advisor_message", "input_tokens": 489_161,
                 "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
                {"type": "message", "input_tokens": 2,
                 "cache_read_input_tokens": 556_452, "cache_creation_input_tokens": 1_021},
            ],
        },
    }}
    advisor_transcript = Path(workspace) / "advisor.jsonl"
    advisor_transcript.write_text(json.dumps(advisor_reply) + "\n", encoding="utf-8")
    used = hook.context_used_percentage_from_transcript(str(advisor_transcript))
    check("an advisor reply is read as its largest own pass, not the sum",
          used is not None and abs(used - 55.7) < 0.1, str(used))
    check("the advisor model's own pass is left out of the share",
          hook.used_tokens_of(advisor_reply["message"]["usage"]) == 557_475,
          str(hook.used_tokens_of(advisor_reply["message"]["usage"])))
    check("an ordinary reply, with no iterations, is read as before",
          hook.used_tokens_of({"input_tokens": 10, "cache_read_input_tokens": 500_000,
                               "cache_creation_input_tokens": 100}) == 500_110)
    check("an iterations list with no pass of this model falls back to the top-level fields",
          hook.used_tokens_of({"input_tokens": 7, "cache_read_input_tokens": 3,
                               "cache_creation_input_tokens": 0,
                               "iterations": [{"type": "advisor_message",
                                               "input_tokens": 400_000}]}) == 10)
    check("an iterations entry with no type is taken as this model's own pass",
          hook.used_tokens_of({"input_tokens": 1, "cache_read_input_tokens": 1,
                               "cache_creation_input_tokens": 0,
                               "iterations": [{"input_tokens": 300}]}) == 300)

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

    # --- The tokens compactions dropped ----------------------------------
    no_compaction = transcript_of(workspace, "no-compaction.jsonl", [usage_record(200_000)])
    check("a transcript with no compaction record drops no tokens",
          hook.compaction_dropped_tokens_from_transcript(str(no_compaction)) == 0,
          str(hook.compaction_dropped_tokens_from_transcript(str(no_compaction))))
    two_compactions = transcript_of(workspace, "two-compactions.jsonl", [
        compaction_record(100_000), usage_record(300_000),
        compaction_record(250_000), usage_record(200_000)])
    check("the newest compaction record's running total is the one read",
          hook.compaction_dropped_tokens_from_transcript(str(two_compactions)) == 250_000,
          str(hook.compaction_dropped_tokens_from_transcript(str(two_compactions))))
    check("the count the hook measures is the context used plus the tokens compactions dropped",
          abs(hook.context_used_plus_compaction_dropped_percentage_from_transcript(
              str(two_compactions)) - 45.0) < 0.01,
          str(hook.context_used_plus_compaction_dropped_percentage_from_transcript(
              str(two_compactions))))
    fractional_count = transcript_of(workspace, "fractional-count.jsonl", [
        compaction_record(255_000), usage_record(200_000)])
    check("that count keeps its fraction",
          abs(hook.context_used_plus_compaction_dropped_percentage_from_transcript(
              str(fractional_count)) - 45.5) < 0.01,
          str(hook.context_used_plus_compaction_dropped_percentage_from_transcript(
              str(fractional_count))))
    check("that count is None for a transcript with no usage",
          hook.context_used_plus_compaction_dropped_percentage_from_transcript(
              str(Path(workspace) / "not-there.jsonl")) is None)
    # Quoting a compaction record, in a message or a hook's output, writes its subtype into another record.
    quoted = transcript_of(workspace, "compaction-quoted.jsonl", [
        compaction_record(100_000), usage_record(300_000),
        {"type": "user", "message": {"content": json.dumps(compaction_record(900_000))}},
        {"type": "system", "subtype": "stop_hook_summary",
         "content": json.dumps(compaction_record(800_000))},
        usage_record(200_000)])
    check("a quoted compaction record is not read as one",
          hook.compaction_dropped_tokens_from_transcript(str(quoted)) == 100_000,
          str(hook.compaction_dropped_tokens_from_transcript(str(quoted))))
    buried_compaction = Path(workspace) / "buried-compaction.jsonl"
    buried_compaction.write_text("\n".join(
        [json.dumps(compaction_record(250_000))] + [filler] * 6
        + [json.dumps(usage_record(200_000))]) + "\n", encoding="utf-8")
    check("a compaction record behind many large later records is still found",
          hook.compaction_dropped_tokens_from_transcript(str(buried_compaction)) == 250_000,
          str(hook.compaction_dropped_tokens_from_transcript(str(buried_compaction))))
    # The work-in-flight scan reads past such bytes too; raising here would stop the hook at every Stop.
    undecodable = Path(workspace) / "compaction-undecodable.jsonl"
    undecodable.write_bytes(
        (json.dumps(compaction_record(150_000)) + "\n").encode("utf-8")
        + b'{"type": "user", "note": "\xff\xfe"}\n'
        + (json.dumps(usage_record(200_000)) + "\n").encode("utf-8"))
    check("bytes that are not UTF-8 in the transcript are read past",
          hook.compaction_dropped_tokens_from_transcript(str(undecodable)) == 150_000,
          str(hook.compaction_dropped_tokens_from_transcript(str(undecodable))))
    partial_compaction = Path(workspace) / "compaction-partial.jsonl"
    partial_compaction.write_text(
        json.dumps(compaction_record(150_000)) + "\n" + json.dumps(usage_record(200_000)) + "\n"
        + json.dumps(compaction_record(400_000))[:60], encoding="utf-8")
    check("a compaction record Claude Code is still writing is skipped",
          hook.compaction_dropped_tokens_from_transcript(str(partial_compaction)) == 150_000,
          str(hook.compaction_dropped_tokens_from_transcript(str(partial_compaction))))
    torn_compaction = Path(workspace) / "compaction-torn-then-whole.jsonl"
    torn_compaction.write_text(
        json.dumps(compaction_record(100_000))[:60] + "\n"
        + json.dumps(compaction_record(150_000)) + "\n" + json.dumps(usage_record(200_000)) + "\n",
        encoding="utf-8")
    check("a line naming a compaction that is not JSON does not stop the scan before later records",
          hook.compaction_dropped_tokens_from_transcript(str(torn_compaction)) == 150_000,
          str(hook.compaction_dropped_tokens_from_transcript(str(torn_compaction))))

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

    # An interim notification is not the subagent's end: the last notification decides.
    interim_last = transcript_of(workspace, "interim-notification-last.jsonl", [
        usage_record(100_000, cache_read=450_000),
        subagent_spawn_record(INCIDENT_SUBAGENT_ID, "Fix-round for PR 2045"),
        *notification_records(INCIDENT_INTERIM_NOTIFICATION),
    ])
    check("a subagent whose last notification is interim is in flight",
          hook.spawned_subagent_ids_in_flight(str(interim_last)) == [INCIDENT_SUBAGENT_ID],
          str(hook.spawned_subagent_ids_in_flight(str(interim_last))))
    not_yet_reported_last = transcript_of(workspace, "not-yet-reported-notification-last.jsonl", [
        usage_record(100_000, cache_read=450_000),
        subagent_spawn_record(INCIDENT_SUBAGENT_ID),
        *notification_records(NOT_YET_REPORTED_INTERIM_NOTIFICATION),
    ])
    check("a last notification whose result says the report has not come is interim too",
          hook.spawned_subagent_ids_in_flight(str(not_yet_reported_last))
          == [INCIDENT_SUBAGENT_ID],
          str(hook.spawned_subagent_ids_in_flight(str(not_yet_reported_last))))
    final_after_interim = transcript_of(workspace, "final-notification-after-interim.jsonl", [
        usage_record(100_000, cache_read=450_000),
        subagent_spawn_record(INCIDENT_SUBAGENT_ID),
        *notification_records(INCIDENT_INTERIM_NOTIFICATION),
        *notification_records(FINAL_NOTIFICATION_AFTER_INTERIM, "2026-10-27T21:45:00.000Z"),
    ])
    check("a final notification after an interim one takes the subagent out of flight",
          hook.spawned_subagent_ids_in_flight(str(final_after_interim)) == [],
          str(hook.spawned_subagent_ids_in_flight(str(final_after_interim))))
    in_text_block_list = transcript_of(workspace, "final-notification-in-text-block-list.jsonl", [
        usage_record(100_000, cache_read=450_000),
        subagent_spawn_record(INCIDENT_SUBAGENT_ID),
        {"type": "user", "timestamp": "2026-10-27T21:45:00.000Z",
         "message": {"role": "user", "content": [
             {"type": "text", "text": "Earlier text."},
             {"type": "text", "text": FINAL_NOTIFICATION_AFTER_INTERIM}]}},
    ])
    check("a final notification held only inside a list of text blocks takes the subagent out of "
          "flight",
          hook.spawned_subagent_ids_in_flight(str(in_text_block_list)) == [],
          str(hook.spawned_subagent_ids_in_flight(str(in_text_block_list))))

    # A SendMessage to a finished subagent resumes it, under the same task-id.
    resumed_after_final = transcript_of(workspace, "resumed-after-final-notification.jsonl", [
        usage_record(100_000, cache_read=450_000),
        subagent_spawn_record(RESUMED_SUBAGENT_ID, "Fix GHI 1112's fast-read findings"),
        *notification_records(RESUMED_SUBAGENT_FINAL_NOTIFICATION, "2026-10-13T19:35:01.611Z"),
        subagent_resume_record(),
    ])
    check("a subagent resumed after its final notification is in flight again",
          hook.spawned_subagent_ids_in_flight(str(resumed_after_final)) == [RESUMED_SUBAGENT_ID],
          str(hook.spawned_subagent_ids_in_flight(str(resumed_after_final))))
    resumed_and_finished_again = transcript_of(workspace, "resumed-and-finished-again.jsonl", [
        usage_record(100_000, cache_read=450_000),
        subagent_spawn_record(RESUMED_SUBAGENT_ID),
        *notification_records(RESUMED_SUBAGENT_FINAL_NOTIFICATION, "2026-10-13T19:35:01.611Z"),
        subagent_resume_record(),
        *notification_records(RESUMED_SUBAGENT_FINAL_NOTIFICATION, "2026-10-13T19:37:28.832Z"),
    ])
    check("a resumed subagent's next final notification takes it out of flight",
          hook.spawned_subagent_ids_in_flight(str(resumed_and_finished_again)) == [],
          str(hook.spawned_subagent_ids_in_flight(str(resumed_and_finished_again))))
    resumed_unknown_agent = transcript_of(workspace, "resumed-agent-never-spawned-here.jsonl", [
        usage_record(100_000, cache_read=450_000),
        subagent_resume_record(),
    ])
    check("a resume of a subagent this transcript never spawned adds nothing",
          hook.spawned_subagent_ids_in_flight(str(resumed_unknown_agent)) == [],
          str(hook.spawned_subagent_ids_in_flight(str(resumed_unknown_agent))))
    resume_word_in_stdout = transcript_of(workspace, "resume-word-in-stdout.jsonl", [
        usage_record(100_000, cache_read=450_000),
        subagent_spawn_record(RESUMED_SUBAGENT_ID),
        *notification_records(RESUMED_SUBAGENT_FINAL_NOTIFICATION, "2026-10-13T19:35:01.611Z"),
        bash_stdout_record_mentioning_a_resume(),
    ])
    check("a Bash result that merely prints a resume record is not a resume",
          hook.spawned_subagent_ids_in_flight(str(resume_word_in_stdout)) == [],
          str(hook.spawned_subagent_ids_in_flight(str(resume_word_in_stdout))))
    truncated_resume = Path(workspace) / "truncated-resume.jsonl"
    resume_text = json.dumps(subagent_resume_record())
    truncated_resume.write_text(
        json.dumps(subagent_spawn_record(RESUMED_SUBAGENT_ID)) + "\n"
        + json.dumps(notification_records(RESUMED_SUBAGENT_FINAL_NOTIFICATION)[0]) + "\n"
        + resume_text[:resume_text.index('"resumedAgentId"') + len('"resumedAgentId": "ac25')],
        encoding="utf-8")
    check("a resume record cut off mid-write is not read as the subagent having finished",
          raises_could_not_read(truncated_resume), "the scan answered instead of refusing")

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

    # The launch is at 22:41:47.899, so these nows make the age exactly 1800.000 s and one
    # millisecond less: a whole-second now would leave it 1799.101 and pin nothing.
    flight = hook.work_in_flight(str(grid_running), thirty_minutes,
                                 now=datetime(2026, 9, 14, 23, 11, 47, 899000, tzinfo=timezone.utc))
    check("a background task exactly as old as the wait is no longer in flight",
          flight.background_task_ids == [], str(flight.background_task_ids))
    flight = hook.work_in_flight(str(grid_running), thirty_minutes,
                                 now=datetime(2026, 9, 14, 23, 11, 47, 898000, tzinfo=timezone.utc))
    check("a background task a millisecond younger than the wait is still in flight",
          flight.background_task_ids == ["b27dndn4c"], str(flight.background_task_ids))

    # The first kind whose pattern matches the command gives the wait-limit; a work kind comes
    # before waiting-task, so a command that both waits and does work keeps the work's limit.
    for command, expected_minutes in (
            ("python3 scripts/run-all-test-suites.py", 90),
            ("python3 scripts/handoff-context-threshold-hook-test.py", 90),
            # A work kind's name is found past a line break and in any case.
            ("cd /home/nedlern/x\npython3 scripts/run-all-test-suites.py", 90),
            ("PYTHON3 SCRIPTS/RUN-ALL-TEST-SUITES.PY", 90),
            ("python3 scripts/mutation-testing-changed-lines-quick-or-full-pass-survivors.py --quick", 105),
            ("gh pr checks 3101 --watch --interval 30", 0),
            ("gh run watch 12345", 0),
            ("python3 -u scripts/watch-open-pull-requests-nbd.py --exit-after-first-poll-with-events", 0),
            ("cd /home/nedlern/x && until grep -q done out.txt; do sleep 5; done", 0),
            ("while kill -0 4242; do sleep 30; done", 0),
            ("sleep 120; echo finished", 75),
            ("sleep 120 >/dev/null 2>&1", 0),
            ("sleep 600 && python3 nc-systems/cold-read/cold-read-grid.py", 75),
            ("until grep -q done out.txt; do sleep 5; done; python3 scripts/run-all-test-suites.py", 90),
            ("until [ -f /tmp/r ]; do sleep 5; done; python3 nc-systems/cold-read/cold-read-grid.py --target CLAUDE.md", 75),
            ("while pgrep -f x >/dev/null; do sleep 20; done; python3 scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py 1 2 3", 75),
            ("until [ -s first.out ]; do sleep 10; done && python3 nc-systems/cold-read/cold-read-fast-read.py --target a.md", 75),
            ("until grep -q done out.txt; do sleep 5; done; cat out.txt | tail -5", 75),
            ("until [ -f x ]; do sleep 5; done; for p in 1 2 3; do python3 scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py $p; done", 75),
            ("while kill -0 4242; do\n  sleep 30\ndone > /dev/null 2>&1", 0),
            ("gh pr checks 3101 --watch && gh pr merge 3101", 75),
            ("while kill -0 4242; do sleep 30; done && echo finished; gh pr view 12", 75),
            ("for f in scripts/*-test.py; do python3 $f; done", 90),
            ("while read -r line; do echo \"$line\" >> out.txt; done < in.txt", 75),
            ("python3 nc-systems/cold-read/cold-read-grid.py --target docs/x.md", 75),
            (None, 75)):
        seconds = hook.background_task_kind_and_wait_limit_minutes_from_command(command)[1] * 60
        check(f"the wait-limit of {command!r} is {expected_minutes} minutes",
              seconds == expected_minutes * 60, seconds)

    # Each waiting-task shape, as recorded background launches wrote it, gets 0 alone; with work
    # beside it, before it, after it or inside its loop, the command gets the no-match limit.
    waiter = "/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/loop/watch-and-merge-provisional-ghi-md-edits.sh"
    waiting_task_shapes = (
        "sleep 120",
        "sleep 120 >/dev/null 2>&1",
        "gh pr checks 3101 --watch --interval 30",
        "gh run watch 12345",
        f"bash {waiter}",
        waiter,
        f"bash {waiter} 2>&1 | tail -30",
        "python3 -u scripts/watch-open-pull-requests-nbd.py --exit-after-first-poll-with-events",
        "/tmp/claude-1000/x/scratchpad/wait-review-runs.sh",
        "until grep -q done out.txt; do sleep 5; done",
        "while kill -0 4242; do sleep 30; done",
        "until [ -f /tmp/r ] && grep -q '^exit=' /tmp/r; do sleep 10; done",
        "while pgrep -f x >/dev/null; do\n  sleep 20\ndone > /dev/null 2>&1",
        "end=$(( $(date +%s) + 1200 )); while [ $(date +%s) -lt $end ]; do "
        f"bash {waiter} 2>&1 | grep -v '^watcher exit 0' | tail -30; done",
    )
    work = "./work.sh"
    for shape in waiting_task_shapes:
        check(f"the waiting-task shape {shape!r} alone has a wait-limit of 0",
              hook.background_task_kind_and_wait_limit_minutes_from_command(shape)[1] * 60 == 0,
              hook.background_task_kind_and_wait_limit_minutes_from_command(shape)[1] * 60)
        for separator in ("; ", ";", " && ", " || ", " | ", " & ", "\n"):
            for command in (shape + separator + work, work + separator + shape):
                seconds = hook.background_task_kind_and_wait_limit_minutes_from_command(command)[1] * 60
                check(f"work beside a wait, {command!r}, has the no-match wait-limit",
                      seconds == 75 * 60, seconds)
    for command in (
            f"while true; do {work}; sleep 60; done",
            f"while true; do sleep 60; {work}; done",
            f"until {work}; do sleep 5; done",
            f"until grep -q done out.txt; do sleep 5; done; {work}",
            f"until grep -q done out.txt && {work}; do sleep 5; done",
            f"end=$(( $(date +%s) + 1200 )); while [ $(date +%s) -lt $end ]; do bash {waiter}; {work}; done",
            f"end=$(( $(date +%s) + 1200 )); while [ $(date +%s) -lt $end ]; do {work}; bash {waiter}; done",
            f"bash {waiter} 2>&1 | {work}",
            f"{work};{waiter}",
            f"X=$({work}); sleep 5",
            f"cd $({work}) && sleep 5",
            f"cd `{work}` && sleep 5",
            f"sleep `{work}`",
            f'sleep "$({work})"',
            f'until grep -q "$({work})" out.txt; do sleep 5; done',
            f"bash {waiter} $({work})",
            f"sleep 120 > $({work})",
            "sleep 120 >/dev/null;./work.sh",
            "gh run watch 12345 && gh pr merge 3101",
            "cd /home/nedlern/agents/merge-lane-2; H=/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers; "
            "python3 scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py "
            "3220 abc t > $H/merge-3220.log 2>&1; while true; do bash $H/loop/watch-and-merge-provisional-ghi-md-edits.sh; done",
            "python3 scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py 3220 abc t "
            "> x 2>&1; while true; do bash h/loop/watch-and-merge-provisional-ghi-md-edits.sh; done"):
        seconds = hook.background_task_kind_and_wait_limit_minutes_from_command(command)[1] * 60
        check(f"work inside or around a wait, {command!r}, has the no-match wait-limit",
              seconds == 75 * 60, seconds)
    # A variable name the pattern could split many ways made a failed match take minutes.
    # Five repetitions take about 9 s when that returns, so this case fails by name, not by timeout.
    many_variables = "export A=$CLAUDE_PROJECT_DIR/a; " * 5 + work
    started = time.monotonic()
    seconds = hook.background_task_kind_and_wait_limit_minutes_from_command(many_variables)[1] * 60
    check("a command of many variables that matches no kind is read within a second",
          seconds == 75 * 60 and time.monotonic() - started < 1, time.monotonic() - started)

    # With no wait given, the transcript scan gives each task its kind's wait-limit from the
    # command of the Bash call whose tool_use id the launch record answers.
    def background_bash_call_record(task_id, command, launched_at):
        return {"type": "assistant", "timestamp": launched_at,
                "message": {"role": "assistant", "content": [{
                    "type": "tool_use", "id": f"toolu_{task_id}", "name": "Bash",
                    "input": {"command": command, "description": "x",
                              "run_in_background": True}}]}}

    eighty_minutes_after_launch = datetime(2026, 9, 15, 0, 1, 47, 899000, tzinfo=timezone.utc)
    for command, in_flight in (("python3 scripts/run-all-test-suites.py", True),
                               ("python3 nc-systems/cold-read/cold-read-grid.py", False),
                               (None, False)):
        records = [usage_record(100_000, cache_read=450_000)]
        if command is not None:
            records.append(background_bash_call_record("b27dndn4c", command, GRID_LAUNCHED_AT))
        records.append(background_task_launch_record("b27dndn4c"))
        by_kind = transcript_of(workspace, f"grid-by-kind-{in_flight}-{command is None}.jsonl", records)
        flight = hook.work_in_flight(str(by_kind), now=eighty_minutes_after_launch)
        check(f"an 80-minute-old task launched by {command!r} is "
              f"{'in flight' if in_flight else 'not in flight'} by its kind's wait-limit",
              flight.background_task_ids == (["b27dndn4c"] if in_flight else []),
              str(flight.background_task_ids))
    waiting = transcript_of(workspace, "grid-by-kind-waiting-task.jsonl", [
        usage_record(100_000, cache_read=450_000),
        background_bash_call_record("b27dndn4c", "gh pr checks 3101 --watch", GRID_LAUNCHED_AT),
        background_task_launch_record("b27dndn4c")])
    flight = hook.work_in_flight(str(waiting), now=grid_at_13_minutes)
    check("a 13-minute-old waiting-task is not in flight by the transcript scan",
          flight.background_task_ids == [], str(flight.background_task_ids))
    torn_call = transcript_of(workspace, "grid-by-kind-torn-call.jsonl", [
        usage_record(100_000, cache_read=450_000),
        background_task_launch_record("b27dndn4c")])
    torn_text = torn_call.read_text(encoding="utf-8")
    torn_call.write_text(torn_text.replace(
        "\n", '\n{"message": {"content": [{"type": "tool_use", "id": "toolu_b27dndn4c", '
               '"input": {"command": "gh pr checks 1 --watch", "run_in_background": true\n', 1),
        encoding="utf-8")
    flight = hook.work_in_flight(str(torn_call), now=grid_at_13_minutes)
    check("a Bash call line that does not parse leaves its task the no-match wait-limit",
          flight.background_task_ids == ["b27dndn4c"], str(flight.background_task_ids))

    # Only a tool_use block whose run_in_background is the boolean true is a background Bash call,
    # wherever it stands among the line's blocks. The other block types sort before and after
    # "tool_use", so an ordering comparison in place of != would let one of them through.
    background_call = {"type": "tool_use", "id": "toolu_late",
                       "input": {"command": "sleep 1", "run_in_background": True}}
    for content, expected in (
            ([{"type": "text", "text": "Launching."}, background_call], {"toolu_late": "sleep 1"}),
            ([{"type": "server_tool_use", "id": "toolu_server",
               "input": {"command": "sleep 1", "run_in_background": True}}], {}),
            ([{"type": "web_search_tool_result", "id": "toolu_result",
               "input": {"command": "sleep 1", "run_in_background": True}}], {}),
            ([{"type": "tool_use", "id": "toolu_one",
               "input": {"command": "sleep 1", "run_in_background": 1}}], {})):
        line = json.dumps({"type": "assistant", "message": {"role": "assistant", "content": content}})
        commands = hook.background_bash_commands_by_tool_use_id_from_line(line)
        check(f"the background Bash calls in content {content!r} are {expected!r}",
              commands == expected, str(commands))

    # The tool_use id is the first tool_result block's, past blocks of types that sort before
    # and after "tool_result".
    for content, expected in (
            ([{"type": "text", "text": "x"}, {"type": "tool_result", "tool_use_id": "toolu_answered"}],
             "toolu_answered"),
            ([{"type": "tool_use", "id": "toolu_call"}, {"type": "tool_result", "tool_use_id": "toolu_answered"}],
             "toolu_answered"),
            ([{"type": "text", "text": "x"}], None)):
        answered = hook.tool_result_tool_use_id({"type": "user", "message": {"role": "user", "content": content}})
        check(f"the tool_result in content {content!r} answers {expected!r}",
              answered == expected, str(answered))

    # A limit of 0 or below means the task is never waited for; any positive limit, however
    # short, waits for a task whose age cannot be read and for one younger than the limit.
    for age_seconds, wait_limit_seconds, expected in (
            (None, -60, False), (None, 0, False), (None, 1, True), (0, 1, True), (0.5, 0.75, True),
            (1, 1, False)):
        within = hook.background_task_still_within_wait(age_seconds, wait_limit_seconds)
        check(f"a task aged {age_seconds!r} s under a {wait_limit_seconds!r} s wait-limit is "
              f"{'within' if expected else 'past'} its wait", within is expected, str(within))

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
        truncated_launch_message = ""
    except hook.TranscriptCouldNotBeFullyRead as problem:
        refused = True
        truncated_launch_message = str(problem)
    check("a background launch record cut off mid-write is not read as nothing running",
          refused, "the scan answered instead of refusing")
    check("the scan's refusal names the line number of the record that did not parse",
          f"{truncated_launch}, line 2: " in truncated_launch_message, truncated_launch_message)
    check("the scan's refusal quotes the start of the line that did not parse",
          repr(launch_text[:cut][:200]) in truncated_launch_message, truncated_launch_message)
    long_broken_launch = Path(workspace) / "long-broken-background-launch.jsonl"
    long_broken_line = '{"toolUseResult": {"backgroundTaskId": "b27dndn4c", "x": "' + "a" * 300
    long_broken_launch.write_text(long_broken_line + "\n", encoding="utf-8")
    try:
        hook.work_in_flight(str(long_broken_launch), thirty_minutes, now=grid_at_13_minutes)
        long_broken_message = ""
    except hook.TranscriptCouldNotBeFullyRead as problem:
        long_broken_message = str(problem)
    check("the scan's refusal quotes exactly the first 200 characters of a longer line",
          repr(long_broken_line[:200]) in long_broken_message, long_broken_message[-260:])

    # Claude Code writes no task-notification for a task TaskStop stops, only this result.
    bash_stopped = transcript_of(workspace, "background-task-stopped.jsonl", [
        usage_record(100_000, cache_read=450_000),
        background_task_launch_record("b27dndn4c"),
        background_task_launch_record("bzzzzzzzz"),
        task_stop_record("b27dndn4c", "local_bash"),
    ])
    flight = hook.work_in_flight(str(bash_stopped), float("inf"), now=grid_at_13_minutes)
    check("a background task TaskStop stopped is not in flight; one it did not stop still is",
          flight.background_task_ids == ["bzzzzzzzz"], str(flight.background_task_ids))

    # A subagent reports interim while its own background command runs; the parent then stops the
    # subagent with TaskStop, which kills the command with it and writes no notification for either.
    subagent_stopped = transcript_of(workspace, "subagent-stopped.jsonl", [
        usage_record(100_000, cache_read=450_000),
        subagent_spawn_record("a01d1eb8fe1e4066a"),
        *notification_records(
            "<task-notification>\n<task-id>a01d1eb8fe1e4066a</task-id>\n<status>completed"
            "</status>\n<note>This agent stopped with background work of its own still running; "
            "the result below may be interim.</note>\n<result>12 of 15 deleted.</result>\n"
            "</task-notification>"),
        task_stop_record("a01d1eb8fe1e4066a", "local_agent"),
    ])
    stopped_subagent_own = hook.subagent_transcript_path(subagent_stopped, "a01d1eb8fe1e4066a")
    stopped_subagent_own.parent.mkdir(parents=True, exist_ok=True)
    transcript_of(stopped_subagent_own.parent, stopped_subagent_own.name,
                  [background_task_launch_record("bdrdn0t9k")])
    flight = hook.work_in_flight(str(subagent_stopped), float("inf"), now=grid_at_13_minutes)
    check("a subagent TaskStop stopped after an interim report is not in flight, though its own "
          "background command never notified",
          flight.subagent_ids == [], str(flight.subagent_ids))

    # An interim notification queued before the TaskStop can be delivered after it; the stop holds.
    interim_copy_after_stop = transcript_of(workspace, "subagent-stopped-interim-copy-after.jsonl", [
        usage_record(100_000, cache_read=450_000),
        subagent_spawn_record("a01d1eb8fe1e4066a"),
        task_stop_record("a01d1eb8fe1e4066a", "local_agent"),
        *notification_records(
            "<task-notification>\n<task-id>a01d1eb8fe1e4066a</task-id>\n<status>completed"
            "</status>\n<note>This agent stopped with background work of its own still running; "
            "the result below may be interim.</note>\n<result>12 of 15 deleted.</result>\n"
            "</task-notification>"),
    ])
    copy_subagent_own = hook.subagent_transcript_path(interim_copy_after_stop, "a01d1eb8fe1e4066a")
    copy_subagent_own.parent.mkdir(parents=True, exist_ok=True)
    transcript_of(copy_subagent_own.parent, copy_subagent_own.name,
                  [background_task_launch_record("bdrdn0t9k")])
    flight = hook.work_in_flight(str(interim_copy_after_stop), float("inf"), now=grid_at_13_minutes)
    check("an interim notification delivered after a TaskStop does not put the stopped subagent "
          "back in flight",
          flight.subagent_ids == [], str(flight.subagent_ids))
    resumed_after_stop_then_interim = transcript_of(
        workspace, "subagent-stopped-resumed-then-interim.jsonl", [
            usage_record(100_000, cache_read=450_000),
            subagent_spawn_record("a01d1eb8fe1e4066a"),
            task_stop_record("a01d1eb8fe1e4066a", "local_agent"),
            subagent_resume_record("a01d1eb8fe1e4066a"),
            *notification_records(
                "<task-notification>\n<task-id>a01d1eb8fe1e4066a</task-id>\n<status>completed"
                "</status>\n<note>This agent stopped with background work of its own still "
                "running; the result below may be interim.</note>\n<result>Waiting.</result>\n"
                "</task-notification>"),
        ])
    resumed_own = hook.subagent_transcript_path(resumed_after_stop_then_interim, "a01d1eb8fe1e4066a")
    resumed_own.parent.mkdir(parents=True, exist_ok=True)
    # The subagent's own transcript shows no running work, so only an applied interim notice
    # takes it out of flight; a stop the resume failed to clear would skip the notice.
    transcript_of(resumed_own.parent, resumed_own.name, [])
    flight = hook.work_in_flight(str(resumed_after_stop_then_interim), float("inf"),
                                 now=grid_at_13_minutes)
    check("an interim notification after a resume that followed a TaskStop is applied",
          flight.subagent_ids == [], str(flight.subagent_ids))

    # A cut-off stop record, unlike a cut-off launch, is skipped: missing it only leaves the task
    # counted as running.
    stop_cut_off = Path(workspace) / "background-task-stop-cut-off.jsonl"
    stop_text = json.dumps(task_stop_record("b27dndn4c", "local_bash"))
    stop_cut_off.write_text(
        json.dumps(background_task_launch_record("b27dndn4c")) + "\n"
        + stop_text[:stop_text.index('"task_type"') + len('"task_type": "loc')], encoding="utf-8")
    flight = hook.work_in_flight(str(stop_cut_off), float("inf"), now=grid_at_13_minutes)
    check("a TaskStop result cut off mid-write is skipped and leaves its task in flight",
          flight.background_task_ids == ["b27dndn4c"], str(flight.background_task_ids))

    # A TaskStop and a resume of the same subagent: whichever comes later in the transcript decides.
    stopped_then_resumed = transcript_of(workspace, "subagent-stopped-then-resumed.jsonl", [
        usage_record(100_000, cache_read=450_000),
        subagent_spawn_record(RESUMED_SUBAGENT_ID),
        task_stop_record(RESUMED_SUBAGENT_ID, "local_agent"),
        subagent_resume_record(),
    ])
    flight = hook.work_in_flight(str(stopped_then_resumed), float("inf"), now=grid_at_13_minutes)
    check("a subagent TaskStop stopped and then resumed is in flight again",
          flight.subagent_ids == [RESUMED_SUBAGENT_ID], str(flight.subagent_ids))
    resumed_then_stopped = transcript_of(workspace, "subagent-resumed-then-stopped.jsonl", [
        usage_record(100_000, cache_read=450_000),
        subagent_spawn_record(RESUMED_SUBAGENT_ID),
        *notification_records(RESUMED_SUBAGENT_FINAL_NOTIFICATION, "2026-10-13T19:35:01.611Z"),
        subagent_resume_record(),
        task_stop_record(RESUMED_SUBAGENT_ID, "local_agent"),
    ])
    flight = hook.work_in_flight(str(resumed_then_stopped), float("inf"), now=grid_at_13_minutes)
    check("a resumed subagent that TaskStop then stopped is not in flight",
          flight.subagent_ids == [], str(flight.subagent_ids))

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
    # in this suite's own handoff directory -- never the real one, since the
    # redirect above gives the suite its own HOME -- and are removed on the
    # way out.
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
    CALLER_OWNED_PROBE_SESSION_ID = "handoff-threshold-hook-test-caller-owned-session"
    caller_owned_marker_file = (
        hook.HANDOFF_DIRECTORY / f"{CALLER_OWNED_PROBE_SESSION_ID}-handoff-asked")
    for probe_marker in (deferral_marker_file, ceiling_marker_file,
                         deferred_marker_file, ceiling_deferred_marker_file,
                         unknown_marker_file, unknown_deferred_marker_file,
                         caller_owned_marker_file):
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

        result = run_hook({"session_id": PROBE_SESSION_ID, "transcript_path": str(loud),
                           "stop_hook_active": True})
        check("hook stays silent at the threshold while the agent answers a Stop hook",
              result.returncode == 0 and not result.stderr.strip() and not result.stdout.strip(),
              f"code {result.returncode}, stderr {result.stderr[:120]}")
        check("hook marks nothing fired while the agent answers a Stop hook",
              not marker_file.exists(), marker_file)

        result = run_hook({"session_id": PROBE_SESSION_ID, "transcript_path": str(loud)})
        check("hook fires at the threshold", result.returncode == 2, f"code {result.returncode}")
        check("hook names the handoff skill", "handoff skill" in result.stderr, result.stderr[:160])
        # The message says to run the skill and nothing else: the skill carries the
        # procedure, and a second copy here went stale twice in one day.
        check("hook says only to run the skill",
              is_handoff_instruction(result.stderr), result.stderr[:160])
        check("hook gives the context share that reached the threshold",
              result.stderr.strip().startswith("This session has used ")
              and "% of its context window" in result.stderr, result.stderr[:160])
        loud_share = hook.context_used_percentage_from_transcript(str(loud))
        check("the share it gives is the share the transcript reached",
              loud_share is not None and result.stderr.strip().startswith(
                  f"This session has used {loud_share:.0f}% of its context window"),
              (loud_share, result.stderr[:160]))

        result = run_hook({"session_id": PROBE_SESSION_ID, "transcript_path": str(loud)})
        check("hook fires only once per session", result.returncode == 0, f"code {result.returncode}")

        # 70,000 of the 200,000-token default is 35%, past the threshold.
        unlisted_model = transcript_with_usage(workspace, "unlisted-model.jsonl", 70_000,
                                               model="claude-something-unreleased")
        marker_file.unlink(missing_ok=True)
        result = run_hook({"session_id": PROBE_SESSION_ID, "transcript_path": str(unlisted_model)})
        message_lines = result.stderr.strip().splitlines()
        check("for a model id not in the table, the hook fires with the instruction and then "
              "names the model id and the default window it assumed",
              result.returncode == 2 and len(message_lines) == 2
              and HANDOFF_INSTRUCTION_PATTERN.fullmatch(message_lines[0]) is not None
              and message_lines[1] == (
                  "The model id claude-something-unreleased is not in "
                  "CONTEXT_WINDOW_TOKENS_BY_MODEL_PREFIX, the threshold-hook's context-window "
                  "table in scripts/handoff-context-threshold-hook.py, so the 35% of its context "
                  "window this session has used assumes a 200K window; tell the user, so the "
                  "table can be updated."),
              f"code {result.returncode}, stderr {result.stderr!r}")

        # At the 200,000 default, // 999 also gives 200, so only a larger default tells a
        # wrong divisor from the right one.
        unlisted_model_at_a_million = transcript_with_usage(
            workspace, "unlisted-model-at-a-million.jsonl", 350_000, model="claude-something-unreleased")
        marker_file.unlink(missing_ok=True)
        real_default_window = hook.DEFAULT_CONTEXT_WINDOW_TOKENS
        hook.DEFAULT_CONTEXT_WINDOW_TOKENS = 1_000_000
        try:
            code, stderr = run_hook_in_process(
                {"session_id": PROBE_SESSION_ID, "transcript_path": str(unlisted_model_at_a_million)})
        finally:
            hook.DEFAULT_CONTEXT_WINDOW_TOKENS = real_default_window
        check("for a model id not in the table, the default window it names is the default in "
              "thousands, whatever the default is",
              code == 2 and "so the 35% of its context window this session has used assumes a "
                            "1000K window;" in stderr,
              f"code {code}, stderr {stderr!r}")

        marker_file.unlink(missing_ok=True)
        result = run_hook({"session_id": PROBE_SESSION_ID, "transcript_path": str(loud)},
                          ("--threshold-used-percentage", "75"))
        check("threshold is configurable", result.returncode == 0, f"code {result.returncode}")

        # The default threshold is a third of the window: 35% fires, 30% does not.
        just_over = transcript_with_usage(workspace, "just-over-a-third.jsonl", 100_000,
                                          cache_read=250_000)
        just_under = transcript_with_usage(workspace, "just-under-a-third.jsonl", 100_000,
                                           cache_read=200_000)
        marker_file.unlink(missing_ok=True)
        result = run_hook({"session_id": PROBE_SESSION_ID, "transcript_path": str(just_under)})
        check("by default the hook stays silent at 30% of the window",
              result.returncode == 0 and not result.stderr.strip(),
              f"code {result.returncode}, stderr {result.stderr[:120]}")
        result = run_hook({"session_id": PROBE_SESSION_ID, "transcript_path": str(just_over)})
        check("by default the hook fires at 35% of the window",
              result.returncode == 2 and is_handoff_instruction(result.stderr),
              f"code {result.returncode}, stderr {result.stderr[:120]}")

        # --- The context used plus the tokens compactions dropped ------------
        # A compaction cuts a long session back to a few tens of thousands of tokens, so the
        # context used alone could stay under the threshold for ever.
        compacted_under = transcript_of(workspace, "compacted-under.jsonl", [
            compaction_record(120_000), usage_record(200_000)])  # 20% + 12% = 32%
        compacted_at = transcript_of(workspace, "compacted-at.jsonl", [
            compaction_record(130_000), usage_record(200_000)])  # 20% + 13% = 33%
        marker_file.unlink(missing_ok=True)
        result = run_hook({"session_id": PROBE_SESSION_ID, "transcript_path": str(compacted_under)})
        check("a compacted session stays silent at 32% counting the dropped tokens",
              result.returncode == 0 and not result.stderr.strip() and not marker_file.exists(),
              f"code {result.returncode}, stderr {result.stderr[:160]}")
        result = run_hook({"session_id": PROBE_SESSION_ID, "transcript_path": str(compacted_at)})
        check("a compacted session at 20% fires at 33% counting the dropped tokens",
              result.returncode == 2 and is_compacted_handoff_instruction(result.stderr)
              and marker_file.exists(),
              f"code {result.returncode}, stderr {result.stderr[:200]}")
        check("the compacted handoff gives both shares",
              ("used 20% (33% counting the tokens its compactions dropped, the figure compared "
               "with the threshold and the ceiling)") in result.stderr,
              result.stderr[:200])
        compacted_fractional = transcript_of(workspace, "compacted-fractional.jsonl", [
            compaction_record(137_000), usage_record(200_000)])  # 20% + 13.7% = 33.7%
        marker_file.unlink(missing_ok=True)
        result = run_hook({"session_id": PROBE_SESSION_ID,
                           "transcript_path": str(compacted_fractional)})
        check("the compacted handoff rounds the count with the dropped tokens, not truncates it",
              "used 20% (34% counting the tokens its compactions dropped" in result.stderr,
              result.stderr[:200])
        # 90.6% is the context used alone: it truncates to 90, a 1% larger factor gives 91.5 and
        # a 1% smaller one 89.7, so the share must be computed exactly to read 91%.
        compacted_used_fractional = transcript_of(workspace, "compacted-used-fractional.jsonl", [
            compaction_record(10_000), usage_record(906_000)])  # 90.6% + 1% = 91.6%
        marker_file.unlink(missing_ok=True)
        result = run_hook({"session_id": PROBE_SESSION_ID,
                           "transcript_path": str(compacted_used_fractional)})
        check("the compacted handoff rounds the context used alone, not truncates it",
              "used 91% (92% counting the tokens its compactions dropped" in result.stderr,
              result.stderr[:200])

        # --- A session its caller reincarnates is left alone ---------------
        # 2026-09-16: ghi-guide-agent, run by scripts/ghi-guide-agent-ask.py as `claude -p`
        # turns, crossed the threshold mid-answer, and the handoff notice came
        # back to the caller in place of the reading list.
        result = run_hook(
            {"session_id": CALLER_OWNED_PROBE_SESSION_ID, "transcript_path": str(loud)},
            extra_environment={hook.REINCARNATION_OWNED_BY_CALLER_VARIABLE:
                               "scripts/ghi-guide-agent-ask.py"})
        check("hook stays silent past the threshold when the caller reincarnates the session",
              result.returncode == 0 and not result.stderr.strip()
              and not caller_owned_marker_file.exists(),
              f"code {result.returncode}, stderr {result.stderr[:120]}")

        result = run_hook(
            {"session_id": CALLER_OWNED_PROBE_SESSION_ID, "transcript_path": str(loud)})
        check("the same session fires as usual without the variable",
              result.returncode == 2 and caller_owned_marker_file.exists(),
              f"code {result.returncode}, stderr {result.stderr[:120]}")

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
        # Claude Code's list at the "running" moment: the list shows the monitor as a shell task.
        subagent_listed = [list_entry("a2573a7737ae643dc", "subagent")]
        subagent_and_monitor_listed = [*subagent_listed, list_entry("b45e25tz2", "shell")]

        # The ceiling measures the same count as the threshold: 20% used plus 50% dropped is 70%.
        DROPPED_CEILING_PROBE_SESSION_ID = "handoff-threshold-hook-test-dropped-ceiling-session"
        dropped_ceiling_markers = (
            hook.handoff_asked_marker_path(DROPPED_CEILING_PROBE_SESSION_ID),
            hook.HANDOFF_DIRECTORY / f"{DROPPED_CEILING_PROBE_SESSION_ID}-handoff-deferred")
        compacted_below_ceiling = transcript_of(workspace, "compacted-below-ceiling.jsonl", [
            compaction_record(400_000), usage_record(200_000),  # 20% + 40% = 60%
            subagent_spawn_record("a2573a7737ae643dc", "Build the cold-read tool")])
        compacted_past_ceiling = transcript_of(workspace, "compacted-past-ceiling.jsonl", [
            compaction_record(500_000), usage_record(200_000),  # 20% + 50% = 70%
            subagent_spawn_record("a2573a7737ae643dc", "Build the cold-read tool")])
        try:
            result = run_hook({"session_id": DROPPED_CEILING_PROBE_SESSION_ID,
                               "transcript_path": str(compacted_below_ceiling),
                               "background_tasks": subagent_listed})
            check("a compacted session below the ceiling counting the dropped tokens defers, "
                  "giving both shares",
                  result.returncode == 2 and "handoff deferred" in result.stderr
                  and ("Context at 20% (60% counting the tokens its compactions dropped, the figure "
                       "compared with the threshold and the ceiling)")
                  in result.stderr and not dropped_ceiling_markers[0].exists(),
                  f"code {result.returncode}, stderr {result.stderr[:200]}")
            for marker in dropped_ceiling_markers:
                marker.unlink(missing_ok=True)
            result = run_hook({"session_id": DROPPED_CEILING_PROBE_SESSION_ID,
                               "transcript_path": str(compacted_past_ceiling),
                               "background_tasks": subagent_listed})
            check("a compacted session at 20% used fires past the ceiling counting the dropped "
                  "tokens, though a subagent runs",
                  result.returncode == 2 and is_compacted_handoff_instruction(result.stderr)
                  and dropped_ceiling_markers[0].exists(),
                  f"code {result.returncode}, stderr {result.stderr[:200]}")
        finally:
            for marker in dropped_ceiling_markers:
                marker.unlink(missing_ok=True)

        result = run_hook({"session_id": DEFERRAL_PROBE_SESSION_ID,
                           "transcript_path": str(running),
                           "background_tasks": subagent_and_monitor_listed})
        check("hook defers instead of firing while a subagent runs",
              result.returncode == 2 and "handoff deferred" in result.stderr,
              f"code {result.returncode}, stderr {result.stderr[:200]}")
        check("the deferral does not tell the agent to run the skill",
              "Run the /handoff skill now." not in result.stderr, result.stderr[:200])
        check("the deferral counts subagents and not monitors",
              "1 subagent(s) run" in result.stderr, result.stderr[:200])
        check("the deferral says how full the context is",
              "Context at 55%" in result.stderr, result.stderr[:200])
        check("the deferral gives the approved instruction on new work, on a line of its own",
              hook.NEW_WORK_DURING_HANDOFF_DEFERRAL_INSTRUCTION in result.stderr.splitlines(),
              result.stderr[-600:])
        check("the deferral names the work it waits for",
              "(subagent a2573a7737ae643dc)" in result.stderr, result.stderr[:600])
        check("the instruction on new work says the handoff writer, not the agent, adds stopped work to the session-handoff",
              "When you run the handoff writer script, nc-systems/handoff/handoff-write-and-check-supervisor.py,"
              " before this agent-session ends, it names in your session-handoff each subagent still working,"
              " whenever it started, and each background Bash task that started since this handoff-deferral"
              " began and is still running, so you need not add that work to your task list"
              in hook.NEW_WORK_DURING_HANDOFF_DEFERRAL_INSTRUCTION,
              hook.NEW_WORK_DURING_HANDOFF_DEFERRAL_INSTRUCTION)
        # Agents read "handoff" in the notice and ran the skill anyway.
        check("the deferral tells the agent, on a line of its own, not to run the skill yet",
              opens_a_line_with_do_not_run_handoff_skill_yet(result.stderr),
              result.stderr[:400])
        check("the deferral gives the ceiling as a number",
              "65% ceiling" in result.stderr, result.stderr[:500])
        # A reader could not tell whether the time limit bounds subagents too.
        check("the deferral says the time limit bounds background tasks, not subagents",
              "a background task, though not a subagent, counted as finished once it is as old as"
              " its kind's wait-limit" in result.stderr, result.stderr[:600])
        check("the deferral says work started from now on does not delay the handoff",
              "Work you start from now on does not delay that message" in result.stderr,
              result.stderr[:700])
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
                           "transcript_path": str(running),
                           "background_tasks": subagent_and_monitor_listed})
        check("a second deferred turn is silent, so the session can go idle",
              result.returncode == 0 and not result.stderr.strip(),
              f"code {result.returncode}, stderr {result.stderr[:200]}")
        check("a silent deferred turn still writes no fired marker",
              not deferral_marker_file.exists(), str(deferral_marker_file))

        result = run_hook({"session_id": DEFERRAL_PROBE_SESSION_ID,
                           "transcript_path": str(finished)})
        check("the same session fires once its subagent has finished",
              result.returncode == 2 and is_handoff_instruction(result.stderr),
              f"code {result.returncode}, stderr {result.stderr[:200]}")
        check("firing after a deferral writes the fired marker",
              deferral_marker_file.exists(), str(deferral_marker_file))
        # Left in place, it would hold the session past the below-threshold
        # return after every later compaction, refiring the instruction.
        check("firing removes the deferral marker",
              not deferred_marker_file.exists(), str(deferred_marker_file))
        # The handoff writer reads the deferral's start time after the fire.
        moved_deferred_marker_file = (
            hook.HANDOFF_DIRECTORY / f"{DEFERRAL_PROBE_SESSION_ID}-handoff-deferred-fired")
        check("firing keeps the deferral's record, moved aside, for the handoff writer",
              moved_deferred_marker_file.exists()
              and "deferral_began_at" in moved_deferred_marker_file.read_text(encoding="utf-8"),
              str(moved_deferred_marker_file))
        deferral_marker_file.unlink(missing_ok=True)
        deferred_marker_file.unlink(missing_ok=True)
        moved_deferred_marker_file.unlink(missing_ok=True)

        # The ceiling overrides a deferral already in progress: this session
        # deferred at 55%, kept working, and arrived at 70% with the subagent
        # still running.
        result = run_hook({"session_id": CEILING_PROBE_SESSION_ID,
                           "transcript_path": str(running),
                           "background_tasks": subagent_and_monitor_listed})
        check("the ceiling session defers first, as the deferral session did",
              result.returncode == 2 and "handoff deferred" in result.stderr,
              f"code {result.returncode}, stderr {result.stderr[:200]}")
        result = run_hook({"session_id": CEILING_PROBE_SESSION_ID,
                           "transcript_path": str(past_ceiling),
                           "background_tasks": subagent_listed})
        check("above the ceiling the handoff fires with a subagent still running",
              result.returncode == 2 and is_handoff_instruction(result.stderr),
              f"code {result.returncode}, stderr {result.stderr[:200]}")
        check("firing above the ceiling writes the fired marker",
              ceiling_marker_file.exists(), str(ceiling_marker_file))
        ceiling_marker_file.unlink(missing_ok=True)
        ceiling_deferred_marker_file.unlink(missing_ok=True)

        result = run_hook({"session_id": CEILING_PROBE_SESSION_ID,
                           "transcript_path": str(running),
                           "background_tasks": subagent_and_monitor_listed},
                          ("--ceiling-used-percentage", "50"))
        check("a lowered ceiling fires at a share that would otherwise defer",
              result.returncode == 2 and is_handoff_instruction(result.stderr),
              f"code {result.returncode}, stderr {result.stderr[:200]}")
        ceiling_marker_file.unlink(missing_ok=True)
        ceiling_deferred_marker_file.unlink(missing_ok=True)

        # --- A read that could not finish defers, and says the count is
        # unknown (merge-lane review of #180, 2026-08-28). Firing here would
        # kill the very task whose launch record could not be read.
        truncated_at_threshold = Path(workspace) / "deferral-truncated-launch.jsonl"
        truncated_at_threshold.write_text(
            json.dumps(usage_record(100_000, cache_read=450_000)) + "\n"  # 55%
            + '{"toolUseResult": {"backgroundTaskId": "bshelltorn"\n',
            encoding="utf-8")
        result = run_hook({"session_id": UNKNOWN_PROBE_SESSION_ID,
                           "transcript_path": str(truncated_at_threshold),
                           "background_tasks": [list_entry("bshelltorn", "shell")]})
        check("a listed shell task whose launch record is cut off defers instead of firing",
              result.returncode == 2 and "handoff deferred" in result.stderr,
              f"code {result.returncode}, stderr {result.stderr[:200]}")
        check("the deferral says the count is unknown, and does not invent one",
              "unknown" in result.stderr and "background task(s) run" not in result.stderr,
              result.stderr[:250])
        check("a cut-off launch record does not tell the agent to hand off",
              "Run the /handoff skill now." not in result.stderr, result.stderr[:200])
        check("the unknown-count deferral tells the agent, on a line of its own, "
              "not to run the skill yet",
              opens_a_line_with_do_not_run_handoff_skill_yet(result.stderr),
              result.stderr[:400])
        check("the unknown-count deferral gives the ceiling as a number",
              "65% ceiling" in result.stderr, result.stderr[:500])
        check("an unknown-count deferral writes the deferral marker, not the fired one",
              unknown_deferred_marker_file.exists() and not unknown_marker_file.exists(),
              f"deferred={unknown_deferred_marker_file.exists()} "
              f"fired={unknown_marker_file.exists()}")
        unknown_marker_file.unlink(missing_ok=True)
        unknown_deferred_marker_file.unlink(missing_ok=True)

        # The read-error path, reached where it can be reached: main() in
        # front of a scan that raises. See run_hook_in_process.
        def scan_that_cannot_read(*_arguments, **_keywords):
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
              code == 2 and is_handoff_instruction(stderr),
              f"code {code}, stderr {stderr[:200]}")
        unknown_marker_file.unlink(missing_ok=True)
        unknown_deferred_marker_file.unlink(missing_ok=True)

        below_threshold = transcript_of(workspace, "deferral-below-threshold.jsonl", [
            usage_record(100_000, cache_read=150_000),  # 25% — nothing to say yet
            subagent_spawn_record("a2573a7737ae643dc", "Build the cold-read tool"),
        ])
        result = run_hook({"session_id": DEFERRAL_PROBE_SESSION_ID,
                           "transcript_path": str(below_threshold),
                           "background_tasks": subagent_listed})
        check("below the threshold a running subagent draws no message at all",
              result.returncode == 0 and not result.stderr.strip(),
              f"code {result.returncode}, stderr {result.stderr[:200]}")

        # --- A deferral whose count then fell below the threshold ------------
        # Without the deferred marker, every Stop after the fall returns at
        # the threshold check, so the promised handoff message never comes.
        COMPACTED_PROBE_SESSION_ID = "handoff-threshold-hook-test-compacted-deferral-session"
        compacted_marker_file = (
            hook.HANDOFF_DIRECTORY / f"{COMPACTED_PROBE_SESSION_ID}-handoff-asked")
        compacted_deferred_marker_file = (
            hook.HANDOFF_DIRECTORY / f"{COMPACTED_PROBE_SESSION_ID}-handoff-deferred")
        compacted_payload = {"session_id": COMPACTED_PROBE_SESSION_ID}
        compacted_finished = transcript_of(workspace, "compacted-deferral-finished.jsonl", [
            usage_record(100_000, cache_read=130_000),  # 23%
            subagent_spawn_record("a2573a7737ae643dc", "Build the cold-read tool"),
            subagent_completion_record("a2573a7737ae643dc"),
        ])
        try:
            result = run_hook({**compacted_payload, "transcript_path": str(running),
                               "background_tasks": subagent_and_monitor_listed})
            check("the compacted-deferral session defers first, at 55%",
                  result.returncode == 2 and "handoff deferred" in result.stderr
                  and compacted_deferred_marker_file.exists(),
                  f"code {result.returncode}, stderr {result.stderr[:200]}")

            result = run_hook({**compacted_payload, "transcript_path": str(below_threshold),
                               "background_tasks": subagent_listed})
            check("below the threshold after a deferral, a running subagent still holds the handoff",
                  result.returncode == 0 and not result.stderr.strip()
                  and not compacted_marker_file.exists(),
                  f"code {result.returncode}, stderr {result.stderr[:200]}")

            result = run_hook({**compacted_payload, "transcript_path": str(compacted_finished)})
            check("below the threshold after a deferral, the handoff fires once nothing runs",
                  result.returncode == 2 and is_handoff_instruction(result.stderr),
                  f"code {result.returncode}, stderr {result.stderr[:200]}")
            check("firing below the threshold after a deferral writes the fired marker",
                  compacted_marker_file.exists(), str(compacted_marker_file))

            result = run_hook({**compacted_payload, "transcript_path": str(compacted_finished)})
            check("the fired marker still stops a repeat below the threshold",
                  result.returncode == 0 and not result.stderr.strip(),
                  f"code {result.returncode}, stderr {result.stderr[:200]}")
            check("firing after a deferral deletes the deferred marker",
                  not compacted_deferred_marker_file.exists(), str(compacted_deferred_marker_file))

            # A later compaction deletes the fired marker, as the post-compaction hook does.
            compacted_marker_file.unlink(missing_ok=True)
            result = run_hook({**compacted_payload, "transcript_path": str(compacted_finished)})
            check("after the deferral's handoff fired and a later compaction, a Stop below "
                  "the threshold is silent",
                  result.returncode == 0 and not result.stderr.strip()
                  and not compacted_marker_file.exists(),
                  f"code {result.returncode}, stderr {result.stderr[:200]}")
            compacted_marker_file.unlink(missing_ok=True)
            compacted_deferred_marker_file.unlink(missing_ok=True)

            # A deferred marker the hook cannot remove: a directory in its place, with a
            # file where it would be moved, makes the move raise, so the hook must say so
            # and still send the instruction.
            compacted_deferred_marker_file.mkdir()
            compacted_moved_marker_file = (
                hook.HANDOFF_DIRECTORY / f"{COMPACTED_PROBE_SESSION_ID}-handoff-deferred-fired")
            compacted_moved_marker_file.write_text("in the way\n", encoding="utf-8")
            try:
                result = run_hook({**compacted_payload, "transcript_path": str(compacted_finished)})
                instruction, _, rest = result.stderr.partition("\n")
                check("a deferred marker the hook cannot delete still lets the instruction go",
                      result.returncode == 2 and is_handoff_instruction(instruction),
                      f"code {result.returncode}, stderr {result.stderr[:300]}")
                check("a deferred marker the hook cannot delete is reported after the instruction",
                      "could not delete this agent-session's handoff-deferral marker" in rest
                      and str(compacted_deferred_marker_file) in rest,
                      f"stderr {result.stderr[:300]}")
                check("the report gives the user's text with the machine, before the handoff",
                      "in the same reply, give the user that text word for word, then run the" in rest
                      and f'"On {socket.gethostname()}, the threshold-hook could not delete' in rest
                      and "Please check why that path cannot be deleted, and delete it." in rest,
                      f"stderr {result.stderr[:600]}")
                check("the report tells a subagent where to send the text",
                      "If you are a subagent, put that text in your final report to the agent "
                      "that dispatched you" in rest,
                      f"stderr {result.stderr[:600]}")
            finally:
                compacted_deferred_marker_file.rmdir()
                compacted_moved_marker_file.unlink(missing_ok=True)
                compacted_marker_file.unlink(missing_ok=True)

            # The unknown-count deferral: the transcript first could not be read,
            # then the context fell below the threshold.
            code, stderr = run_hook_in_process(
                {**compacted_payload, "transcript_path": str(running)},
                scan_replacement=scan_that_cannot_read)
            check("the compacted-deferral session defers with an unknown count first",
                  code == 2 and "unknown" in stderr and compacted_deferred_marker_file.exists(),
                  f"code {code}, stderr {stderr[:200]}")
            code, stderr = run_hook_in_process(
                {**compacted_payload, "transcript_path": str(compacted_finished)},
                scan_replacement=scan_that_cannot_read)
            check("below the threshold an unreadable transcript still holds an unknown-count deferral",
                  code == 0 and not stderr.strip() and not compacted_marker_file.exists(),
                  f"code {code}, stderr {stderr[:200]}")
            code, stderr = run_hook_in_process(
                {**compacted_payload, "transcript_path": str(compacted_finished)})
            check("below the threshold an unknown-count deferral fires once the transcript reads "
                  "fully and nothing runs",
                  code == 2 and is_handoff_instruction(stderr) and compacted_marker_file.exists(),
                  f"code {code}, stderr {stderr[:200]}")
        finally:
            compacted_marker_file.unlink(missing_ok=True)
            compacted_deferred_marker_file.unlink(missing_ok=True)

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
        # Claude Code's list at each moment; grid_done's is empty.
        grid_young_listed = [list_entry("b27dndn4c", "shell"), list_entry("bwk7aucu8", "shell")]
        grid_old_listed = grid_past_ceiling_listed = [list_entry("b27dndn4c", "shell")]
        both_running_listed = [list_entry("a2573a7737ae643dc", "subagent"),
                               list_entry("b27dndn4c", "shell")]
        both_running = transcript_of(workspace, "subagent-and-background-task-running.jsonl", [
            usage_record(100_000, cache_read=450_000),
            subagent_spawn_record("a2573a7737ae643dc", "Build the cold-read tool"),
            background_task_launch_record("b27dndn4c", launched_at=ten_minutes_ago),
        ])

        try:
            result = run_hook({"session_id": BACKGROUND_PROBE_SESSION_ID,
                               "transcript_path": str(grid_young),
                               "background_tasks": grid_young_listed})
            check("hook defers instead of firing while a background task runs",
                  result.returncode == 2 and "handoff deferred" in result.stderr,
                  f"code {result.returncode}, stderr {result.stderr[:200]}")
            check("the background-task deferral counts the task and not the monitor",
                  "1 background task(s) run" in result.stderr
                  and "subagent" not in result.stderr.splitlines()[0],
                  result.stderr[:250])
            check("the background-task deferral names the task it waits for",
                  "(background task b27dndn4c)" in result.stderr, result.stderr[:600])
            check("the deferral names the wait-limit table as a way the handoff fires",
                  "wait-limit" in result.stderr
                  and "BACKGROUND_TASK_WAIT_LIMIT_MINUTES_BY_KIND in "
                      "scripts/handoff-context-threshold-hook.py" in result.stderr,
                  result.stderr[:900])
            check("a background-task deferral writes the deferral marker and not the fired one",
                  background_deferred_marker_file.exists() and not background_marker_file.exists(),
                  f"deferred={background_deferred_marker_file.exists()} "
                  f"fired={background_marker_file.exists()}")

            result = run_hook({"session_id": BACKGROUND_PROBE_SESSION_ID,
                               "transcript_path": str(grid_young),
                               "background_tasks": grid_young_listed})
            check("a second deferred turn behind a background task is silent",
                  result.returncode == 0 and not result.stderr.strip(),
                  f"code {result.returncode}, stderr {result.stderr[:200]}")

            result = run_hook({"session_id": BACKGROUND_PROBE_SESSION_ID,
                               "transcript_path": str(grid_done)})
            check("the same session fires once its background task has finished",
                  result.returncode == 2 and is_handoff_instruction(result.stderr),
                  f"code {result.returncode}, stderr {result.stderr[:200]}")
            background_marker_file.unlink(missing_ok=True)
            background_deferred_marker_file.unlink(missing_ok=True)

            result = run_hook({"session_id": BACKGROUND_PROBE_SESSION_ID,
                               "transcript_path": str(grid_old),
                               "background_tasks": grid_old_listed})
            check("a background task older than the wait does not hold the handoff",
                  result.returncode == 2 and is_handoff_instruction(result.stderr),
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
                               "transcript_path": str(grid_young),
                               "background_tasks": grid_young_listed})
            check("the outlived-wait session defers first, as the young-task session did",
                  result.returncode == 2 and "handoff deferred" in result.stderr
                  and background_deferred_marker_file.exists(),
                  f"code {result.returncode}, stderr {result.stderr[:200]}")
            result = run_hook({"session_id": BACKGROUND_PROBE_SESSION_ID,
                               "transcript_path": str(grid_old),
                               "background_tasks": grid_old_listed})
            check("a session that deferred fires once its background task outlives the wait",
                  result.returncode == 2 and is_handoff_instruction(result.stderr)
                  and background_marker_file.exists(),
                  f"code {result.returncode}, stderr {result.stderr[:200]}")
            background_marker_file.unlink(missing_ok=True)
            background_deferred_marker_file.unlink(missing_ok=True)

            result = run_hook({"session_id": BACKGROUND_PROBE_SESSION_ID,
                               "transcript_path": str(grid_young),
                               "background_tasks": [list_entry(
                                   "b27dndn4c", "shell", command="gh pr checks 3101 --watch")]})
            check("a waiting-task's wait-limit of 0 fires on a ten-minute-old task",
                  result.returncode == 2 and is_handoff_instruction(result.stderr),
                  f"code {result.returncode}, stderr {result.stderr[:200]}")
            background_marker_file.unlink(missing_ok=True)
            background_deferred_marker_file.unlink(missing_ok=True)

            result = run_hook({"session_id": BACKGROUND_PROBE_SESSION_ID,
                               "transcript_path": str(grid_past_ceiling),
                               "background_tasks": grid_past_ceiling_listed})
            check("above the ceiling the handoff fires with a background task still running",
                  result.returncode == 2 and is_handoff_instruction(result.stderr),
                  f"code {result.returncode}, stderr {result.stderr[:200]}")
            background_marker_file.unlink(missing_ok=True)
            background_deferred_marker_file.unlink(missing_ok=True)

            result = run_hook({"session_id": BACKGROUND_PROBE_SESSION_ID,
                               "transcript_path": str(both_running),
                               "background_tasks": both_running_listed})
            check("a deferral behind both kinds names both",
                  "1 subagent(s) and 1 background task(s) run" in result.stderr,
                  result.stderr[:250])
        finally:
            background_marker_file.unlink(missing_ok=True)
            background_deferred_marker_file.unlink(missing_ok=True)

        # --- Claude Code's background_tasks list decides what runs ----------
        # The entry shapes are trimmed from real Stop hook input; the list shows a
        # Monitor as a shell task, and a subagent waiting on its own shell task
        # leaves the list while that task stays on it.
        LIST_PROBE_SESSION_ID = "handoff-threshold-hook-test-background-tasks-list-session"
        list_fired_marker_file = hook.handoff_asked_marker_path(LIST_PROBE_SESSION_ID)
        list_deferred_marker_file = hook.deferred_marker_path(LIST_PROBE_SESSION_ID)

        def clear_list_markers():
            list_fired_marker_file.unlink(missing_ok=True)
            list_deferred_marker_file.unlink(missing_ok=True)

        clock = datetime.now(timezone.utc)
        ten_minutes_ago = utc_iso(clock - timedelta(minutes=10))
        two_hours_ago = utc_iso(clock - timedelta(hours=2))
        # The transcript shows a subagent spawned and never finished, so a hook
        # that read the transcript instead of the list would defer.
        list_session = transcript_of(workspace, "background-tasks-list-session.jsonl", [
            usage_record(100_000, cache_read=450_000),  # 55%
            subagent_spawn_record("a2573a7737ae643dc", "Build the cold-read tool"),
            background_task_launch_record("bshellyoung", launched_at=ten_minutes_ago),
            background_task_launch_record("bshellold", launched_at=two_hours_ago),
            monitor_start_record("bmonitor01"),
        ])
        list_subagents = list_session.with_suffix("") / "subagents"
        list_subagents.mkdir(parents=True, exist_ok=True)
        transcript_of(list_subagents, "agent-a2573a7737ae643dc.jsonl", [
            background_task_launch_record("bsubyoung", launched_at=ten_minutes_ago),
            background_task_launch_record("bsubold", launched_at=two_hours_ago),
        ])

        def flight_of(entries, transcript=list_session):
            return hook.work_in_flight_from_background_tasks(
                entries, str(transcript), now=clock)

        flight = flight_of([])
        check("an empty list holds nothing, whatever the transcript's notices say", not flight,
              f"{flight.subagent_ids} {flight.background_task_ids} {flight.workflow_ids}")
        flight = flight_of([list_entry("a1", "subagent")])
        check("a listed running subagent holds the handoff", flight.subagent_ids == ["a1"],
              str(flight.subagent_ids))
        flight = flight_of([list_entry("w1", "workflow")])
        check("a listed running workflow holds the handoff", flight.workflow_ids == ["w1"],
              str(flight.workflow_ids))
        check("a list holding only a running workflow counts as work in flight", bool(flight),
              f"{flight.subagent_ids} {flight.background_task_ids} {flight.workflow_ids}")
        flight = flight_of([list_entry("bshellyoung", "shell")])
        check("a shell task launched within the wait holds the handoff",
              flight.background_task_ids == ["bshellyoung"], str(flight.background_task_ids))
        flight = flight_of([list_entry("bshellold", "shell")])
        check("a shell task launched longer ago than the wait holds nothing", not flight,
              str(flight.background_task_ids))
        flight = flight_of([list_entry("bsubyoung", "shell")])
        check("a subagent's own shell task within the wait holds the handoff, dated from the"
              " subagent's transcript", flight.background_task_ids == ["bsubyoung"],
              str(flight.background_task_ids))
        check("a subagent's own shell task is tied to the subagent whose transcript launched it",
              flight.launching_subagent_id_by_task_id == {"bsubyoung": "a2573a7737ae643dc"},
              str(flight.launching_subagent_id_by_task_id))
        flight = flight_of([list_entry("bshellyoung", "shell")])
        check("the session's own shell task is tied to no subagent",
              flight.launching_subagent_id_by_task_id == {},
              str(flight.launching_subagent_id_by_task_id))
        flight = flight_of([list_entry("bsubold", "shell")])
        check("a subagent's own shell task past the wait holds nothing", not flight,
              str(flight.background_task_ids))
        # A Workflow-tool agent keeps its transcript a level deeper, under
        # subagents/workflows/<run>/, beside a journal.jsonl. The layout and journal lines are
        # copied from a real headless probe session; its transcript carries no toolUseResult,
        # so the launch records take the interactive shape above.
        workflow_session = transcript_of(workspace, "65d644bd-b689-43c4-b258-efed0a8087b4.jsonl", [
            usage_record(100_000, cache_read=450_000)])
        workflow_run = workflow_session.with_suffix("") / "subagents" / "workflows" / "wf_b109740f-730"
        workflow_run.mkdir(parents=True, exist_ok=True)
        transcript_of(workflow_run, "agent-a59a8abb54ebd7b15.jsonl", [
            background_task_launch_record("bxecf0mah", launched_at=two_hours_ago),
            background_task_launch_record("bwfyoung1", launched_at=ten_minutes_ago),
            monitor_start_record("bwfmonitor"),
        ])
        (workflow_run / "journal.jsonl").write_text(
            '{"type":"launched"}\n'
            '{"type":"started","agentId":"a59a8abb54ebd7b15","label":"probe-sleep"}\n'
            'not JSON, yet naming bxecf0mah and "backgroundTaskId"\n', encoding="utf-8")

        def workflow_flight_of(entries):
            return flight_of(entries, transcript=workflow_session)

        flight = workflow_flight_of([list_entry("w2c4bv83u", "workflow"),
                                     list_entry("bxecf0mah", "shell")])
        check("a Workflow-tool agent's shell task past the wait holds nothing, dated from the"
              " agent's transcript under subagents/workflows/",
              flight.background_task_ids == [] and flight.workflow_ids == ["w2c4bv83u"],
              f"{flight.background_task_ids} {flight.workflow_ids}")
        flight = workflow_flight_of([list_entry("bwfyoung1", "shell")])
        check("a Workflow-tool agent's shell task within the wait holds the handoff, tied to no"
              " subagent", flight.background_task_ids == ["bwfyoung1"]
              and flight.launching_subagent_id_by_task_id == {},
              f"{flight.background_task_ids} {flight.launching_subagent_id_by_task_id}")
        flight = workflow_flight_of([list_entry("bwfmonitor", "shell")])
        check("a Monitor a Workflow-tool agent started holds nothing", not flight,
              str(flight.background_task_ids))
        flight = flight_of([list_entry("bmonitor01", "shell")])
        check("a Monitor, which the list shows as a shell task, holds nothing", not flight,
              str(flight.background_task_ids))
        flight = flight_of([list_entry("bunrecorded", "shell")])
        check("a shell task no transcript records counts as within its wait",
              flight.background_task_ids == ["bunrecorded"], str(flight.background_task_ids))
        # Launch records carry milliseconds, so the clock is cut to them for an age of exactly a
        # wait-limit, and one millisecond less.
        boundary_clock = clock.replace(microsecond=clock.microsecond // 1000 * 1000)
        for kind_name, command, limit_minutes in (
                ("nc-mutation-testing",
                 "python3 scripts/mutation-testing-changed-lines-quick-or-full-pass-survivors.py", 105),
                ("test-suite", "cd /tmp/x && python3 scripts/run-all-test-suites.py", 90),
                ("a command no kind matches", "python3 nc-systems/cold-read/cold-read-grid.py", 75)):
            for age, holds in ((timedelta(minutes=limit_minutes), False),
                               (timedelta(minutes=limit_minutes) - timedelta(milliseconds=1), True)):
                boundary_session = transcript_of(
                    workspace, f"background-tasks-list-{limit_minutes}-{holds}.jsonl", [
                        usage_record(100_000, cache_read=450_000),
                        background_task_launch_record(
                            "bshellboundary", launched_at=utc_iso(boundary_clock - age))])
                flight = hook.work_in_flight_from_background_tasks(
                    [list_entry("bshellboundary", "shell", command=command)], str(boundary_session),
                    now=boundary_clock)
                check(f"a {kind_name} shell task {age} old "
                      f"{'holds' if holds else 'no longer holds'} the handoff",
                      flight.background_task_ids == (["bshellboundary"] if holds else []),
                      str(flight.background_task_ids))
        flight = flight_of([list_entry("bunrecorded", "shell", command="gh pr checks 3101 --watch")])
        check("an undated waiting-task holds nothing: its wait-limit of 0 beats the unknown age",
              not flight, str(flight.background_task_ids))
        flight = hook.work_in_flight_from_background_tasks(
            [list_entry("bunrecorded", "shell", command="gh pr checks 3101 --watch")],
            str(list_session), 10 * 60, now=clock)
        check("a wait given in seconds applies to every kind, a waiting-task's included",
              flight.background_task_ids == ["bunrecorded"], str(flight.background_task_ids))
        # A line naming a listed shell task that is not its launch record must not end the reading
        # of the transcript, or a later launch record goes unread and its task counts as undated.
        three_hours_ago = utc_iso(clock - timedelta(hours=3))
        mentioned_without_launch_key = transcript_of(
            workspace, "background-tasks-list-task-mentioned-before-later-launch.jsonl", [
                usage_record(100_000, cache_read=450_000),
                background_task_launch_record("bshellearlier", launched_at=three_hours_ago),
                {"type": "assistant", "message": {"role": "assistant", "content": [
                    {"type": "text", "text": "bshellearlier is still running."}]}},
                background_task_launch_record("bshelllater", launched_at=two_hours_ago),
            ])
        flight = flight_of([list_entry("bshellearlier", "shell"), list_entry("bshelllater", "shell")],
                           transcript=mentioned_without_launch_key)
        check("a line naming a listed shell task without a launch key leaves later launch records"
              " read", not flight, str(flight.background_task_ids))
        # The assistant's own tool call can quote the launch key; it carries no toolUseResult.
        quoted_launch_key = transcript_of(
            workspace, "background-tasks-list-launch-key-quoted-before-later-launch.jsonl", [
                usage_record(100_000, cache_read=450_000),
                background_task_launch_record("bshellearlier", launched_at=three_hours_ago),
                {"type": "assistant", "message": {"role": "assistant", "content": [
                    {"type": "tool_use", "name": "Bash", "input": {
                        "command": "grep -c 'backgroundTaskId.*bshellearlier' session.jsonl"}}]}},
                background_task_launch_record("bshelllater", launched_at=two_hours_ago),
            ])
        flight = flight_of([list_entry("bshellearlier", "shell"), list_entry("bshelllater", "shell")],
                           transcript=quoted_launch_key)
        check("a line quoting the launch key and a listed shell task with no toolUseResult leaves"
              " later launch records read", not flight, str(flight.background_task_ids))
        flight = flight_of([list_entry("a1", "subagent", status="completed"),
                            list_entry("x1", "some-later-kind"), "not an entry",
                            {"type": "subagent", "status": "running"},
                            {"id": "bnostatus", "type": "shell"}])
        check("a finished entry, an unknown kind, malformed entries and an entry with no status"
              " hold nothing", not flight,
              f"{flight.subagent_ids} {flight.background_task_ids} {flight.workflow_ids}")
        # With no saved list, only work launched before the deferral began holds the handoff,
        # so the list's entries must carry their launch times from the transcripts.
        list_unknown_began = clock - timedelta(minutes=30)
        list_unknown_marker = hook.handoff_deferred_marker_and_refused_commands_files_common.HandoffDeferredMarker(
            used_percentage=40.0, deferral_began_at=list_unknown_began, awaited_subagent_ids=[],
            awaited_background_task_ids=[], awaited_work_is_unknown=True)
        late_spawn = dict(subagent_spawn_record("alatespawn"), timestamp=ten_minutes_ago)
        early_spawn = dict(subagent_spawn_record("aearlyspawn"), timestamp=two_hours_ago)
        list_unknown_session = transcript_of(workspace, "background-tasks-list-unknown-count.jsonl", [
            usage_record(100_000, cache_read=450_000), late_spawn, early_spawn,
            background_task_launch_record("bshellyoung", launched_at=ten_minutes_ago),
        ])
        flight = flight_of([list_entry("alatespawn", "subagent"), list_entry("bshellyoung", "shell")],
                           transcript=list_unknown_session)
        check("with no saved list, a listed subagent and shell task launched after the deferral"
              " began do not hold the handoff",
              not hook.awaited_work_still_in_flight(list_unknown_marker, flight),
              flight.launched_at_by_id)
        flight = flight_of([list_entry("aearlyspawn", "subagent")], transcript=list_unknown_session)
        check("with no saved list, a listed subagent launched before the deferral began holds it",
              hook.awaited_work_still_in_flight(list_unknown_marker, flight), flight.launched_at_by_id)
        flight = flight_of([list_entry("anospawn", "subagent")], transcript=list_unknown_session)
        check("with no saved list, a listed subagent whose launch no transcript records holds it",
              hook.awaited_work_still_in_flight(list_unknown_marker, flight), flight.launched_at_by_id)
        # A subagent launched before the deferral leaves the list while it waits on a shell task it
        # starts after the deferral began; that task stands in for the subagent and holds the handoff.
        owner_session = transcript_of(workspace, "background-tasks-list-unknown-count-owner.jsonl", [
            usage_record(100_000, cache_read=450_000),
            dict(subagent_spawn_record("aearlyowner"), timestamp=two_hours_ago),
            dict(subagent_spawn_record("alateowner"), timestamp=ten_minutes_ago),
        ])
        owner_subagents = owner_session.with_suffix("") / "subagents"
        owner_subagents.mkdir(parents=True, exist_ok=True)
        transcript_of(owner_subagents, "agent-aearlyowner.jsonl", [
            background_task_launch_record("bearlyownertask", launched_at=ten_minutes_ago)])
        transcript_of(owner_subagents, "agent-alateowner.jsonl", [
            background_task_launch_record("blateownertask", launched_at=ten_minutes_ago)])
        flight = flight_of([list_entry("bearlyownertask", "shell")], transcript=owner_session)
        check("with no saved list, a shell task started after the deferral began by a subagent"
              " launched before it, now off the list, holds the handoff",
              hook.awaited_work_still_in_flight(list_unknown_marker, flight), flight.launched_at_by_id)
        flight = flight_of([list_entry("blateownertask", "shell")], transcript=owner_session)
        check("with no saved list, a shell task of a subagent launched after the deferral began"
              " does not hold the handoff",
              not hook.awaited_work_still_in_flight(list_unknown_marker, flight), flight.launched_at_by_id)
        torn_spawn = transcript_of(workspace, "background-tasks-list-torn-spawn.jsonl", [
            usage_record(100_000, cache_read=450_000)])
        with torn_spawn.open("a", encoding="utf-8") as handle:
            handle.write('{"toolUseResult": {"status": "async_launched", "agentId": "alatespawn"\n')
        check("a spawn line naming a listed subagent that does not parse cannot be read past",
              raises_list_could_not_read([list_entry("alatespawn", "subagent")], torn_spawn))
        spawn_directory = Path(workspace) / "background-tasks-list-transcript-is-a-directory.jsonl"
        spawn_directory.mkdir()
        check("a session transcript that cannot be opened cannot date a listed subagent",
              raises_list_could_not_read([list_entry("alatespawn", "subagent")], spawn_directory))
        flight = flight_of([list_entry("a1", "subagent")],
                           transcript=Path(workspace) / "no-such-transcript.jsonl")
        check("a missing session transcript leaves a listed subagent undated, and it is still awaited",
              flight.subagent_ids == ["a1"] and flight.launched_at_by_id == {},
              f"{flight.subagent_ids} {flight.launched_at_by_id}")
        check("a missing session transcript cannot date a listed shell task",
              raises_list_could_not_read([list_entry("bshellyoung", "shell")],
                                         Path(workspace) / "no-such-transcript.jsonl"))
        torn = transcript_of(workspace, "background-tasks-list-torn.jsonl", [
            usage_record(100_000, cache_read=450_000)])
        with torn.open("a", encoding="utf-8") as handle:
            handle.write('{"toolUseResult": {"backgroundTaskId": "bshellyoung"\n')
        check("a line naming a listed shell task that does not parse cannot be read past",
              raises_list_could_not_read([list_entry("bshellyoung", "shell")], torn))
        try:
            hook.work_in_flight_from_background_tasks(
                [list_entry("bshellyoung", "shell")], str(torn))
            torn_message = ""
        except hook.TranscriptCouldNotBeFullyRead as problem:
            torn_message = str(problem)
        check("the unparsable line is named by its number and text",
              ", line 2:" in torn_message and '"bshellyoung"' in torn_message, torn_message)
        long_torn = transcript_of(workspace, "background-tasks-list-long-torn.jsonl", [
            usage_record(100_000, cache_read=450_000)])
        long_line = '{"toolUseResult": {"backgroundTaskId": "bshellyoung", "x": "' + "a" * 300
        with long_torn.open("a", encoding="utf-8") as handle:
            handle.write(long_line + "\n")
        try:
            hook.work_in_flight_from_background_tasks(
                [list_entry("bshellyoung", "shell")], str(long_torn))
            long_message = ""
        except hook.TranscriptCouldNotBeFullyRead as problem:
            long_message = str(problem)
        check("the unparsable line's text is cut at exactly its first 200 characters",
              repr(long_line[:200]) in long_message, long_message[-260:])
        unreadable_subagents = transcript_of(
            workspace, "background-tasks-list-unreadable-subagent.jsonl",
            [usage_record(100_000, cache_read=450_000)])
        unreadable_directory = unreadable_subagents.with_suffix("") / "subagents"
        unreadable_directory.mkdir(parents=True, exist_ok=True)
        (unreadable_directory / "agent-a9.jsonl").mkdir()  # opening a directory raises
        check("a subagent transcript that cannot be opened cannot be read past",
              raises_list_could_not_read([list_entry("bshellyoung", "shell")],
                                         unreadable_subagents))

        try:
            clear_list_markers()
            result = run_hook({"session_id": LIST_PROBE_SESSION_ID,
                               "transcript_path": str(list_session),
                               "background_tasks": [list_entry("w1", "workflow"),
                                                    list_entry("bshellyoung", "shell")]})
            check("the hook defers behind a listed workflow and names it",
                  result.returncode == 2
                  and "1 workflow(s) and 1 background task(s) run" in result.stderr,
                  f"code {result.returncode}, stderr {result.stderr[:250]}")
            saved = json.loads(list_deferred_marker_file.read_text(encoding="utf-8"))
            check("a deferral behind a listed workflow saves it as awaited work and names it",
                  saved.get("awaited_workflow_ids") == ["w1"] and "workflow w1" in result.stderr,
                  f"marker {saved}, stderr {result.stderr[:400]}")
            result = run_hook({"session_id": LIST_PROBE_SESSION_ID,
                               "transcript_path": str(list_session),
                               "background_tasks": [list_entry("w1", "workflow"),
                                                    list_entry("w2", "workflow")]})
            check("while an awaited workflow runs, a later turn stays silent",
                  result.returncode == 0 and not result.stderr.strip(),
                  f"code {result.returncode}, stderr {result.stderr[:250]}")
            result = run_hook({"session_id": LIST_PROBE_SESSION_ID,
                               "transcript_path": str(list_session),
                               "background_tasks": [list_entry("w2", "workflow")]})
            check("a workflow started after the deferral began does not hold the handoff",
                  result.returncode == 2 and is_handoff_instruction(result.stderr),
                  f"code {result.returncode}, stderr {result.stderr[:250]}")
            clear_list_markers()
            result = run_hook({"session_id": LIST_PROBE_SESSION_ID,
                               "transcript_path": str(list_session),
                               "background_tasks": [list_entry("a2573a7737ae643dc", "subagent")]})
            check("the hook defers behind a listed subagent",
                  result.returncode == 2 and "handoff deferred" in result.stderr,
                  f"code {result.returncode}, stderr {result.stderr[:250]}")
            # Claude Code's list drops a subagent while it waits on its own shell task.
            result = run_hook({"session_id": LIST_PROBE_SESSION_ID,
                               "transcript_path": str(list_session),
                               "background_tasks": [list_entry("bsubyoung", "shell")]})
            check("an awaited subagent's own shell task holds the handoff while the subagent waits"
                  " off the list", result.returncode == 0 and not result.stderr.strip(),
                  f"code {result.returncode}, stderr {result.stderr[:250]}")
            result = run_hook({"session_id": LIST_PROBE_SESSION_ID,
                               "transcript_path": str(list_session),
                               "background_tasks": [list_entry("bshellyoung", "shell")]})
            check("a shell task neither awaited nor launched by an awaited subagent does not hold it",
                  result.returncode == 2 and is_handoff_instruction(result.stderr),
                  f"code {result.returncode}, stderr {result.stderr[:250]}")
            clear_list_markers()
            result = run_hook({"session_id": LIST_PROBE_SESSION_ID,
                               "transcript_path": str(list_session), "background_tasks": []})
            check("the hook fires on an empty list though the transcript shows an unfinished"
                  " subagent", result.returncode == 2 and is_handoff_instruction(result.stderr),
                  f"code {result.returncode}, stderr {result.stderr[:250]}")
            # Without the list nothing counts as running, whatever the transcript shows; the
            # message names the claude whose version the hook read.
            fake_claude_directory = Path(workspace) / "fake-claude-bin"
            fake_claude_directory.mkdir(exist_ok=True)
            fake_claude = fake_claude_directory / "claude"

            def missing_list_run(fake_claude_script, expected_version_text):
                clear_list_markers()
                if fake_claude_script is None:
                    fake_claude.unlink(missing_ok=True)
                else:
                    fake_claude.write_text(fake_claude_script, encoding="utf-8")
                    fake_claude.chmod(0o755)
                result = run_hook({"session_id": LIST_PROBE_SESSION_ID,
                                   "transcript_path": str(list_session)},
                                  extra_environment={"PATH": str(fake_claude_directory)},
                                  background_tasks_list_is_missing=True)
                instruction, _, rest = result.stderr.partition("\n")
                expected = hook.BACKGROUND_TASKS_LIST_MISSING_SENTENCE.format(
                    claude_version=expected_version_text)
                return result, instruction, rest.strip(), expected

            result, instruction, rest, expected = missing_list_run(
                "#!/bin/sh\necho '9.9.9 (Claude Code)'\n", "9.9.9 (Claude Code)")
            check("without the list the hook hands off at the threshold though the transcript "
                  "shows an unfinished subagent",
                  result.returncode == 2 and is_handoff_instruction(instruction)
                  and list_fired_marker_file.exists() and not list_deferred_marker_file.exists(),
                  f"code {result.returncode}, stderr {result.stderr[:300]}")
            check("without the list the handoff message adds the missing-list sentence with the "
                  "version claude --version printed", rest == expected,
                  f"got {rest!r}, expected {expected!r}")
            check("the missing-list sentence is the approved text",
                  expected == "Claude Code sent no background_tasks list, so the threshold-hook "
                  "could not see running subagents or background tasks, and this session-handoff "
                  "stops any still running; tell the user that claude 9.9.9 (Claude Code) may be "
                  "too old to send that list.", expected)

            result, instruction, rest, _ = missing_list_run(None, "")
            check("when claude cannot be run, the missing-list sentence says so in place of the "
                  "version",
                  result.returncode == 2 and is_handoff_instruction(instruction)
                  and "tell the user that claude (version unknown: running claude --version "
                  "failed: " in rest and rest.endswith(") may be too old to send that list."),
                  rest)

            result, instruction, rest, expected = missing_list_run(
                "#!/bin/sh\necho 'not logged in' >&2\nexit 3\n",
                "(version unknown: claude --version exited 3 with output 'not logged in')")
            check("when claude --version fails, the missing-list sentence gives its exit status "
                  "and output in place of the version",
                  result.returncode == 2 and rest == expected,
                  f"got {rest!r}, expected {expected!r}")

            result, instruction, rest, expected = missing_list_run(
                "#!/bin/sh\necho '9.9.9 (Claude Code)'\nexit 3\n",
                "(version unknown: claude --version exited 3 with output '9.9.9 (Claude Code)')")
            check("when claude --version prints a version but exits nonzero, the missing-list "
                  "sentence gives its exit status in place of the version",
                  rest == expected, f"got {rest!r}, expected {expected!r}")

            result, instruction, rest, expected = missing_list_run(
                "#!/bin/sh\necho '9.9.9 (Claude Code)'\nkill -TERM $$\n",
                "(version unknown: claude --version exited -15 with output '9.9.9 (Claude Code)')")
            check("when claude --version is killed by a signal, the missing-list sentence says so "
                  "in place of the version", rest == expected, f"got {rest!r}, expected {expected!r}")

            result, instruction, rest, expected = missing_list_run(
                "#!/bin/sh\nexit 0\n",
                "(version unknown: claude --version exited 0 with output '')")
            check("when claude --version prints nothing, the missing-list sentence says so in "
                  "place of the version", rest == expected, f"got {rest!r}, expected {expected!r}")

            # A deferral already in progress ends when a later Stop's input lacks the list.
            clear_list_markers()
            run_hook({"session_id": LIST_PROBE_SESSION_ID, "transcript_path": str(list_session),
                      "background_tasks": [list_entry("a2573a7737ae643dc", "subagent")]})
            fake_claude.write_text("#!/bin/sh\necho '9.9.9 (Claude Code)'\n", encoding="utf-8")
            result = run_hook({"session_id": LIST_PROBE_SESSION_ID,
                               "transcript_path": str(list_session)},
                              extra_environment={"PATH": str(fake_claude_directory)},
                              background_tasks_list_is_missing=True)
            check("a deferral in progress hands off at the next Stop whose input lacks the list",
                  result.returncode == 2 and result.stderr.startswith("This session has used ")
                  and "Claude Code sent no background_tasks list" in result.stderr
                  and list_fired_marker_file.exists(),
                  f"code {result.returncode}, stderr {result.stderr[:300]}")

            # Above the ceiling the hook needs no list, but the handoff still stops what runs.
            clear_list_markers()
            result = run_hook({"session_id": LIST_PROBE_SESSION_ID,
                               "transcript_path": str(grid_past_ceiling)},
                              extra_environment={"PATH": str(fake_claude_directory)},
                              background_tasks_list_is_missing=True)
            check("above the ceiling a Stop without the list also carries the missing-list sentence",
                  result.returncode == 2 and "Claude Code sent no background_tasks list" in result.stderr,
                  f"code {result.returncode}, stderr {result.stderr[:300]}")
            clear_list_markers()
            result = run_hook({"session_id": LIST_PROBE_SESSION_ID,
                               "transcript_path": str(torn),
                               "background_tasks": [list_entry("bshellyoung", "shell")]})
            check("a listed shell task the transcripts cannot date defers as unknown work",
                  result.returncode == 2 and "could not be fully read" in result.stderr,
                  f"code {result.returncode}, stderr {result.stderr[:250]}")
        finally:
            clear_list_markers()

        # --- Below the threshold, nothing fires ------------------------------
        SHARE_PROBE_SESSION_ID = "handoff-threshold-hook-test-share-session"
        share_fired_marker_file = hook.handoff_asked_marker_path(SHARE_PROBE_SESSION_ID)
        share_payload = {"session_id": SHARE_PROBE_SESSION_ID}
        # Live sessions keep walk-closed markers written before the lower threshold was removed.
        share_walk_closed_marker_file = hook.HANDOFF_DIRECTORY / (
            f"{SHARE_PROBE_SESSION_ID}"
            "-handoff-due-at-lower-context-threshold-after-approval-walk-closed")
        share_walk_closed_marker_file.write_text("", encoding="utf-8")

        twenty_one = transcript_of(workspace, "twenty-one.jsonl", [usage_record(210_000)])
        try:
            result = run_hook({**share_payload, "transcript_path": str(twenty_one)})
        finally:
            share_walk_closed_marker_file.unlink(missing_ok=True)
        check("the hook stays silent at 21%, even with a walk-closed marker left on disk",
              result.returncode == 0 and not result.stderr.strip()
              and not share_fired_marker_file.exists(),
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
        caller_owned_marker_file.unlink(missing_ok=True)

# --- The deferral waits only for the work in flight when it began ---
# Work started later must not hold it, or a session that keeps working is held to the ceiling.
with tempfile.TemporaryDirectory() as wait_set_workspace:
    hook.HANDOFF_DIRECTORY.mkdir(parents=True, exist_ok=True)
    clock = datetime.now(timezone.utc)

    def spawned_at(agent_id, moment):
        return {**subagent_spawn_record(agent_id), "timestamp": utc_iso(moment)}

    def probe(name, records):
        return transcript_of(wait_set_workspace, f"{name}.jsonl",
                             [usage_record(100_000, cache_read=450_000), *records])  # 55%

    def markers_of(session_id):
        return (hook.handoff_asked_marker_path(session_id),
                hook.handoff_deferred_marker_and_refused_commands_files_common.handoff_deferred_marker_path(
                    hook.HANDOFF_DIRECTORY, session_id))

    def clear(session_id):
        for marker in markers_of(session_id):
            if marker.is_dir():
                marker.rmdir()
            else:
                marker.unlink(missing_ok=True)

    def scan_that_cannot_read_the_transcript(*_arguments, **_keywords):
        raise hook.TranscriptCouldNotBeFullyRead("unreadable in this test")

    first, late = "a1111111111111111", "a2222222222222222"
    only_first_running = probe("wait-set-first-running",
                               [spawned_at(first, clock - timedelta(minutes=3))])
    first_and_late_running = probe("wait-set-first-and-late-running", [
        spawned_at(first, clock - timedelta(minutes=3)),
        spawned_at(late, clock + timedelta(seconds=30))])
    first_done_late_running = probe("wait-set-first-done-late-running", [
        spawned_at(first, clock - timedelta(minutes=3)),
        spawned_at(late, clock + timedelta(seconds=30)),
        subagent_completion_record(first)])
    nothing_running = probe("wait-set-nothing-running", [
        spawned_at(first, clock - timedelta(minutes=3)), subagent_completion_record(first)])

    WAIT_SET_SESSION_ID = "handoff-threshold-hook-test-wait-set-session"
    fired, deferred = markers_of(WAIT_SET_SESSION_ID)
    clear(WAIT_SET_SESSION_ID)
    try:
        result = run_hook({"session_id": WAIT_SET_SESSION_ID,
                           "transcript_path": str(only_first_running),
                           "background_tasks": [list_entry(first, "subagent")]})
        saved = json.loads(deferred.read_text(encoding="utf-8")) if deferred.is_file() else {}
        check("the first deferral saves the work then in flight in the deferred marker file",
              result.returncode == 2 and saved.get("awaited_subagent_ids") == [first]
              and saved.get("awaited_background_task_ids") == []
              and saved.get("awaited_work_is_unknown") is False
              and isinstance(saved.get("deferral_began_at"), str),
              f"code {result.returncode}, marker {saved}")

        result = run_hook({"session_id": WAIT_SET_SESSION_ID,
                           "transcript_path": str(first_and_late_running),
                           "background_tasks": [list_entry(first, "subagent"), list_entry(late, "subagent")]})
        check("while saved work runs, a later turn stays silent though new work also runs",
              result.returncode == 0 and not result.stderr.strip() and not fired.exists(),
              f"code {result.returncode}, stderr {result.stderr[:200]}")
        saved_again = json.loads(deferred.read_text(encoding="utf-8"))
        check("a later turn leaves the saved work as it was",
              saved_again.get("awaited_subagent_ids") == [first], saved_again)

        result = run_hook({"session_id": WAIT_SET_SESSION_ID,
                           "transcript_path": str(first_done_late_running),
                           "background_tasks": [list_entry(late, "subagent")]})
        check("the handoff fires once the saved work has finished, though work started later "
              "still runs",
              result.returncode == 2 and is_handoff_instruction(result.stderr) and fired.exists(),
              f"code {result.returncode}, stderr {result.stderr[:200]}")
    finally:
        clear(WAIT_SET_SESSION_ID)

    # A deferral whose first read could not finish saved no list. The background_tasks list
    # carries no launch time, so every listed piece of work holds it until the list is empty.
    UNKNOWN_SET_SESSION_ID = "handoff-threshold-hook-test-unknown-wait-set-session"
    fired, deferred = markers_of(UNKNOWN_SET_SESSION_ID)
    clear(UNKNOWN_SET_SESSION_ID)
    try:
        code, stderr = run_hook_in_process(
            {"session_id": UNKNOWN_SET_SESSION_ID, "transcript_path": str(only_first_running),
             "background_tasks": [list_entry(first, "subagent")]},
            scan_replacement=scan_that_cannot_read_the_transcript)
        saved = json.loads(deferred.read_text(encoding="utf-8")) if deferred.is_file() else {}
        check("an unknown-count deferral saves that its awaited work is unknown",
              code == 2 and saved.get("awaited_work_is_unknown") is True
              and hook.NEW_WORK_DURING_HANDOFF_DEFERRAL_INSTRUCTION in stderr.splitlines(),
              f"code {code}, marker {saved}, stderr {stderr[-300:]}")
        result = run_hook({"session_id": UNKNOWN_SET_SESSION_ID,
                           "transcript_path": str(first_and_late_running),
                           "background_tasks": [list_entry(first, "subagent"), list_entry(late, "subagent")]})
        check("after an unknown-count deferral, listed work holds the handoff",
              result.returncode == 0 and not result.stderr.strip() and not fired.exists(),
              f"code {result.returncode}, stderr {result.stderr[:200]}")
        result = run_hook({"session_id": UNKNOWN_SET_SESSION_ID,
                           "transcript_path": str(nothing_running)})
        check("after an unknown-count deferral, the handoff fires once the list is empty",
              result.returncode == 2 and is_handoff_instruction(result.stderr),
              f"code {result.returncode}, stderr {result.stderr[:200]}")
    finally:
        clear(UNKNOWN_SET_SESSION_ID)

    # A marker file the hook cannot read, such as one written before the saved list existed,
    # is reported and replaced, not taken as no deferral and not taken as an all-clear.
    LEGACY_MARKER_SESSION_ID = "handoff-threshold-hook-test-legacy-marker-session"
    fired, deferred = markers_of(LEGACY_MARKER_SESSION_ID)
    clear(LEGACY_MARKER_SESSION_ID)
    try:
        deferred.write_text("55.0\n", encoding="utf-8")
        result = run_hook({"session_id": LEGACY_MARKER_SESSION_ID,
                           "transcript_path": str(first_and_late_running),
                           "background_tasks": [list_entry(first, "subagent"), list_entry(late, "subagent")]})
        saved = json.loads(deferred.read_text(encoding="utf-8"))
        check("a marker file without the saved list is reported and replaced by the work "
              "running now",
              result.returncode == 2 and "could not read this session's earlier" in result.stderr
              and "the hook replaced that record with a new one" in result.stderr
              and "the work the hook now waits for is the work running now" in result.stderr
              and sorted(saved.get("awaited_subagent_ids", [])) == sorted([first, late]),
              f"code {result.returncode}, marker {saved}, stderr {result.stderr[-400:]}")
        clear(LEGACY_MARKER_SESSION_ID)

        deferred.write_text("55.0\n", encoding="utf-8")
        result = run_hook({"session_id": LEGACY_MARKER_SESSION_ID,
                           "transcript_path": str(nothing_running)})
        check("a marker file without the saved list, with nothing running, lets the handoff fire",
              result.returncode == 2 and is_handoff_instruction(result.stderr),
              f"code {result.returncode}, stderr {result.stderr[:200]}")
        clear(LEGACY_MARKER_SESSION_ID)

        deferred.write_text("{}", encoding="utf-8")
        os.chmod(deferred, 0o000)
        try:
            result = run_hook({"session_id": LEGACY_MARKER_SESSION_ID,
                               "transcript_path": str(only_first_running),
                           "background_tasks": [list_entry(first, "subagent")]})
        finally:
            os.chmod(deferred, 0o600)
        check("a marker file that cannot be opened is reported and replaced",
              result.returncode == 2 and "could not read this session's earlier" in result.stderr
              and "Permission denied" in result.stderr
              and json.loads(deferred.read_text(encoding="utf-8")).get("awaited_subagent_ids")
              == [first],
              f"code {result.returncode}, stderr {result.stderr[-400:]}")
        clear(LEGACY_MARKER_SESSION_ID)

        # A directory where the marker file goes can be neither read nor replaced.
        deferred.mkdir()
        result = run_hook({"session_id": LEGACY_MARKER_SESSION_ID,
                           "transcript_path": str(only_first_running),
                           "background_tasks": [list_entry(first, "subagent")]})
        check("a deferral whose list cannot be saved says so, and says the notice will repeat",
              result.returncode == 2 and "handoff deferred" in result.stderr
              and "could not save the list of work it waits for" in result.stderr
              and str(deferred) in result.stderr
              and "The second time you see this line about the list, tell the user, once:" in result.stderr
              and "could not read this session's earlier" not in result.stderr,
              f"code {result.returncode}, stderr {result.stderr[-500:]}")
    finally:
        clear(LEGACY_MARKER_SESSION_ID)

    # With no saved list, work launched at the very moment the deferral began still counts.
    began = datetime(2026, 10, 28, 20, 12, tzinfo=timezone.utc)
    unknown_marker = hook.handoff_deferred_marker_and_refused_commands_files_common.HandoffDeferredMarker(
        used_percentage=40.0, deferral_began_at=began, awaited_subagent_ids=[],
        awaited_background_task_ids=[], awaited_work_is_unknown=True)
    check("with no saved list, work launched as the deferral began holds the handoff",
          hook.awaited_work_still_in_flight(
              unknown_marker, hook.WorkInFlight([], ["b1"], launched_at_by_id={"b1": began})))
    check("with no saved list, work whose launch time is unknown holds the handoff",
          hook.awaited_work_still_in_flight(
              unknown_marker, hook.WorkInFlight(["a1"], [], launched_at_by_id={"a1": None})))
    check("with no saved list, work launched after the deferral began does not hold it",
          not hook.awaited_work_still_in_flight(
              unknown_marker, hook.WorkInFlight(["a1"], [], launched_at_by_id={"a1": began + timedelta(seconds=1)})))
    workflow_marker = hook.handoff_deferred_marker_and_refused_commands_files_common.HandoffDeferredMarker(
        used_percentage=40.0, deferral_began_at=began, awaited_subagent_ids=[],
        awaited_background_task_ids=[], awaited_work_is_unknown=False, awaited_workflow_ids=["w1"])
    check("an awaited workflow still running holds the handoff",
          hook.awaited_work_still_in_flight(workflow_marker, hook.WorkInFlight([], [], ["w1"])))
    check("with no saved list, a workflow whose launch time is unknown holds the handoff",
          hook.awaited_work_still_in_flight(unknown_marker, hook.WorkInFlight([], [], ["w9"])))
    check("with no saved list, a subagent's own shell task launched after the deferral began is"
          " dated by its subagent's earlier launch, and holds the handoff",
          hook.awaited_work_still_in_flight(unknown_marker, hook.WorkInFlight(
              [], ["T"], launched_at_by_id={"T": began + timedelta(minutes=5),
                                            "A": began - timedelta(hours=1)},
              launching_subagent_id_by_task_id={"T": "A"})))
    check("with no saved list, a subagent's own shell task whose subagent was launched after the"
          " deferral began does not hold the handoff",
          not hook.awaited_work_still_in_flight(unknown_marker, hook.WorkInFlight(
              [], ["T"], launched_at_by_id={"T": began - timedelta(hours=1),
                                            "A": began + timedelta(minutes=5)},
              launching_subagent_id_by_task_id={"T": "A"})))
    # A deferral that begins while a subagent waits off the list on its own shell task must still
    # wait for that subagent once the task ends and the subagent is back on the list.
    with tempfile.TemporaryDirectory() as owner_workspace:
        saved_handoff_directory = hook.HANDOFF_DIRECTORY
        hook.HANDOFF_DIRECTORY = Path(owner_workspace)
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                hook.defer("owner-off-list", 40.0, "40%",
                           hook.WorkInFlight([], ["T"], launching_subagent_id_by_task_id={"T": "A"}),
                           argparse.Namespace(ceiling_used_percentage=65.0),
                           now=began)
            owner_marker = hook.handoff_deferred_marker_and_refused_commands_files_common.handoff_deferred_marker_read(
                Path(owner_workspace), "owner-off-list")
        finally:
            hook.HANDOFF_DIRECTORY = saved_handoff_directory
    check("a deferral begun while a subagent waits off the list on its own shell task waits for"
          " that subagent once it is back on the list",
          hook.awaited_work_still_in_flight(owner_marker, hook.WorkInFlight(["A"], [])),
          owner_marker)
    # A launch record whose time carries no zone is read as UTC, so it compares with the deferral's start.
    check("a launch time with no time zone is read as UTC",
          hook.record_time({"timestamp": "2026-10-28T20:12:00"}) == began,
          hook.record_time({"timestamp": "2026-10-28T20:12:00"}))
    check("a launch time with a zone keeps it",
          hook.record_time({"timestamp": "2026-10-28T21:12:00+01:00"}) == began,
          hook.record_time({"timestamp": "2026-10-28T21:12:00+01:00"}))

# The shared reader of a transcript line's task events, which work_in_flight and the writer's
# roster both call.
read_line = hook.task_events_from_claude_code_transcript_line
spawn_line = json.dumps(subagent_spawn_record("a2573a7737ae643dc", description="the builder"))
check("the reader returns a spawn with its subagent's id and description",
      [(event.kind, event.task_id, event.description)
       for event in read_line(spawn_line, "here", should_raise_on_unparseable_spawn_or_resume_line=True)]
      == [(hook.SUBAGENT_SPAWNED_BY_AGENT_TOOL_TASK_EVENT, "a2573a7737ae643dc", "the builder")],
      read_line(spawn_line, "here", should_raise_on_unparseable_spawn_or_resume_line=True))
two_ids_notification = (
    "<task-notification>\n<task-id>a3fe2b9aecae01f3b</task-id>\n<task-id>a677554663305e800</task-id>\n"
    "<status>stopped</status>\n<summary>No completion record was found</summary>\n"
    "</task-notification>")
notification_events = read_line(
    json.dumps(notification_records(two_ids_notification)[1]), "here",
    should_raise_on_unparseable_spawn_or_resume_line=True)
check("the reader returns one notification event for each task-id, with the status",
      [(event.kind, event.task_id, event.status, event.is_interim) for event in notification_events]
      == [(hook.TASK_NOTIFICATION_TASK_EVENT, "a3fe2b9aecae01f3b", "stopped", False),
          (hook.TASK_NOTIFICATION_TASK_EVENT, "a677554663305e800", "stopped", False)],
      notification_events)
interim_events = read_line(json.dumps(notification_records(INCIDENT_INTERIM_NOTIFICATION)[1]),
                           "here", should_raise_on_unparseable_spawn_or_resume_line=True)
check("the reader marks an interim notification",
      [(event.task_id, event.is_interim) for event in interim_events]
      == [(INCIDENT_SUBAGENT_ID, True)], interim_events)
# The line holds the notification JSON-escaped; whitespace opening the <result> must still read
# as whitespace.
result_opening_with_whitespace_events = read_line(
    json.dumps(notification_records(NOT_YET_REPORTED_INTERIM_NOTIFICATION.replace(
        "<result>", "<result>\n\t"))[1]),
    "here", should_raise_on_unparseable_spawn_or_resume_line=True)
check("the reader marks interim a notification whose <result> opens with whitespace, then says the "
      "report has not come",
      [(event.task_id, event.is_interim) for event in result_opening_with_whitespace_events]
      == [(INCIDENT_SUBAGENT_ID, True)], result_opening_with_whitespace_events)
monitor_event_notification = (
    "<task-notification>\n<task-id>bzshcbek2</task-id>\n"
    '<summary>Monitor event: "report files appearing"</summary>\n<event>update</event>\n'
    "</task-notification>")
monitor_events = read_line(json.dumps(notification_records(monitor_event_notification)[1]), "here",
                           should_raise_on_unparseable_spawn_or_resume_line=True)
check("the reader gives a notification with no <status>, a Monitor event's, no status",
      [(event.task_id, event.status) for event in monitor_events] == [("bzshcbek2", None)],
      monitor_events)
check("the reader returns a resume and a TaskStop",
      [(event.kind, event.task_id) for line in (
          json.dumps(subagent_resume_record()), json.dumps(task_stop_record("b5x7", "local_bash")))
       for event in read_line(line, "here", should_raise_on_unparseable_spawn_or_resume_line=True)]
      == [(hook.SUBAGENT_RESUMED_BY_SEND_MESSAGE_TASK_EVENT, RESUMED_SUBAGENT_ID),
          (hook.STOPPED_BY_TASK_STOP_EVENT, "b5x7")])
cut_resume_line = json.dumps(subagent_resume_record())[:-30]
for cut_line, marker in ((half_written_spawn_line(), "spawn"), (cut_resume_line, "resume")):
    try:
        read_line(cut_line, "transcript.jsonl, line 7",
                  should_raise_on_unparseable_spawn_or_resume_line=True)
        refusal = None
    except hook.TranscriptCouldNotBeFullyRead as problem:
        refusal = str(problem)
    check(f"asked to raise, the reader refuses a {marker} line that does not parse, naming the line",
          refusal is not None and refusal.startswith("transcript.jsonl, line 7: "), refusal)
    check(f"asked to skip, the reader returns no events for a {marker} line that does not parse",
          read_line(cut_line, "here", should_raise_on_unparseable_spawn_or_resume_line=False) == [])
cut_stop_line = json.dumps(task_stop_record("b5x7", "local_bash"))[:-20]
cut_notification_line = json.dumps(notification_records(FINAL_NOTIFICATION_AFTER_INTERIM)[1])[:-20]
check("asked to raise, the reader still skips a TaskStop or notification line that does not parse",
      read_line(cut_stop_line, "here", should_raise_on_unparseable_spawn_or_resume_line=True) == []
      and read_line(cut_notification_line, "here",
                    should_raise_on_unparseable_spawn_or_resume_line=True) == [])
check("the reader returns no events for a marker line that parses to something other than an object",
      read_line('["async_launched", "resumedAgentId"]', "here",
                should_raise_on_unparseable_spawn_or_resume_line=True) == [])
try:
    read_line(spawn_line, "here")
    caller_must_choose = False
except TypeError:
    caller_must_choose = True
check("a caller of the reader must choose whether a line that does not parse raises",
      caller_must_choose)

# --help prints each flag's default, so an agent reads it there and not from the source.
help_result = subprocess.run([sys.executable, str(HOOK_SCRIPT), "--help"],
                             capture_output=True, text=True, check=False)
check("--help exits 0", help_result.returncode == 0, help_result.stderr)
# argparse wraps help text, so a default can be split across lines.
help_text = " ".join(help_result.stdout.split())
help_flags = [flag for flag in re.findall(r"^\s+(--[a-z][a-z-]*)", help_result.stdout, re.MULTILINE)
              if flag != "--help"]
check("--help lists the hook's two flags",
      help_flags == ["--threshold-used-percentage", "--ceiling-used-percentage"], help_flags)
for flag, default in (("--threshold-used-percentage", 33.0),
                      ("--ceiling-used-percentage", 65.0)):
    flag_entry = re.search(re.escape(flag) + r" [A-Z_]+ (.*?)(?= --[a-z]|$)", help_text)
    check(f"--help shows {flag}'s default, {default}",
          flag_entry is not None and flag_entry.group(1).endswith(f"(default: {default})"),
          flag_entry.group(1) if flag_entry else help_text)


def runtime_union_annotations(path):
    """Each `X | Y` annotation Python evaluates at import, which Python 3.9 cannot."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    if any(isinstance(node, ast.ImportFrom) and node.module == "__future__"
           and any(alias.name == "annotations" for alias in node.names) for node in tree.body):
        return []
    annotations = [node.annotation for node in ast.walk(tree) if isinstance(node, (ast.AnnAssign, ast.arg))]
    annotations += [node.returns for node in ast.walk(tree)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return [f"{path.name}:{annotation.lineno}" for annotation in annotations if annotation is not None
            and any(isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr) for node in ast.walk(annotation))]


# The Mac's python3 is Apple's 3.9, which runs this hook and the handoff writer that imports it.
for importing_script in (HOOK_SCRIPT,
                         HOOK_SCRIPT.parent.parent / "nc-systems" / "handoff" / "handoff-write-and-check-supervisor.py"):
    union_annotations = runtime_union_annotations(importing_script)
    check(f"{importing_script.name} imports under Python 3.9: no `X | None` annotation evaluated at import",
          not union_annotations, union_annotations)

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
