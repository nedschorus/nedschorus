#!/usr/bin/env python3
"""Request a handoff before context runs out.

It counts the context used plus the tokens the session's compactions dropped, and asks for the
/handoff skill once that count reaches --threshold-used-percentage of the context window.
Below --ceiling-used-percentage, by the same count, it defers instead, saving the work it waits for in
<session>-handoff-deferred in ~/.claude/handoffs/, while Claude Code's background_tasks list
shows a running subagent, workflow or background shell task younger than its kind's wait-limit,
from BACKGROUND_TASK_WAIT_LIMIT_MINUTES_BY_KIND, or while a
transcript it reads launch records from cannot be read, since it then cannot tell what runs.
With no background_tasks list it counts nothing as running.

The post-compaction hook deletes only <session>-handoff-asked, so while <session>-handoff-deferred
exists the hook still fires below the threshold once the awaited work has finished; it then
moves that file to <session>-handoff-deferred-fired, where the writer script reads when the
deferral began.

.claude/settings.json registers it under Stop alone, and a subagent's turn raises SubagentStop,
so it never runs in a subagent; the subagent line in HANDOFF_DEFERRED_MARKER_NOT_DELETED follows
the tool-message page's rule for messages that send an agent to the user.

Stop-hook payloads lack context usage; headless sessions lack a status line.
The transcript supplies usage for both interactive and headless sessions."""

import argparse
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Every Stop hook obeys this rule first: see the module's docstring.
_stop_hooks_stay_silent_rule_specification = importlib.util.spec_from_file_location(
    "claude_code_stop_hooks_stay_silent_while_agent_answers_a_stop_hook_rule_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "claude-code-stop-hooks-stay-silent-while-agent-answers-a-stop-hook-rule-common.py")
stop_hooks_stay_silent_rule = importlib.util.module_from_spec(_stop_hooks_stay_silent_rule_specification)
_stop_hooks_stay_silent_rule_specification.loader.exec_module(stop_hooks_stay_silent_rule)

_transcript_records_specification = importlib.util.spec_from_file_location(
    "claude_code_session_transcript_records_read_backward_common",
    Path(__file__).resolve().with_name("claude-code-session-transcript-records-read-backward-common.py"))
transcript_records = importlib.util.module_from_spec(_transcript_records_specification)
_transcript_records_specification.loader.exec_module(transcript_records)

_interim_recognizer_specification = importlib.util.spec_from_file_location(
    "claude_code_subagent_task_notification_interim_recognizer_common",
    Path(__file__).resolve().with_name(
        "claude-code-subagent-task-notification-interim-recognizer-common.py"))
interim_recognizer = importlib.util.module_from_spec(_interim_recognizer_specification)
_interim_recognizer_specification.loader.exec_module(interim_recognizer)

_deferred_marker_file_specification = importlib.util.spec_from_file_location(
    "handoff_deferred_marker_and_refused_commands_files_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "handoff"
    / "handoff-deferred-marker-and-refused-commands-files-common.py")
handoff_deferred_marker_and_refused_commands_files_common = importlib.util.module_from_spec(_deferred_marker_file_specification)
_deferred_marker_file_specification.loader.exec_module(handoff_deferred_marker_and_refused_commands_files_common)

HANDOFF_DIRECTORY = Path.home() / ".claude" / "handoffs"

# Compaction clears this shared marker because the session id survives.
HANDOFF_ASKED_MARKER_SUFFIX = "-handoff-asked"


def handoff_asked_marker_path(session_id: str) -> Path:
    # Read HANDOFF_DIRECTORY at call time so tests can redirect marker writes.
    return HANDOFF_DIRECTORY / f"{session_id}{HANDOFF_ASKED_MARKER_SUFFIX}"


def deferred_marker_path(session_id: str) -> Path:
    return handoff_deferred_marker_and_refused_commands_files_common.handoff_deferred_marker_path(
        HANDOFF_DIRECTORY, session_id)

# Caller-owned reincarnation must not replace the caller's answer with a handoff.
REINCARNATION_OWNED_BY_CALLER_VARIABLE = "NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER"

# Unknown models use the default, and the handoff instruction names the model id so the table gets updated.
CONTEXT_WINDOW_TOKENS_BY_MODEL_PREFIX = {
    "claude-fable-5": 1_000_000,
    "claude-mythos-5": 1_000_000,
    "claude-opus-5": 1_000_000,
    "claude-opus-4": 1_000_000,
    "claude-sonnet-5": 1_000_000,
    "claude-sonnet-4-6": 1_000_000,
    "claude-haiku-4-5": 200_000,
}
DEFAULT_CONTEXT_WINDOW_TOKENS = 200_000

# scripts/agent-seat-due-task-raise-hook.py reads this to tell a handoff is due at the same Stop.
DEFAULT_THRESHOLD_USED_PERCENTAGE = 33.0

FIRST_TAIL_READ_BYTES = 256 * 1024

# Messages below follow docs/nedschorus-wiki/nedschorus-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
# Keep the procedure in the skill so hook instructions cannot drift from it.
# The count can pass 100% of the window, so a compacted session's message gives both shares.
SHARE_WITH_COMPACTION_DROPPED = (
    "{used_percentage:.0f}% ({used_plus_dropped_percentage:.0f}% counting the "
    "tokens its compactions dropped, the figure compared with the threshold and the ceiling)"
)

HANDOFF_INSTRUCTION = (
    "This session has used {share} of its context window, which has "
    "reached the reincarnation threshold. Run the /handoff skill now."
)

MODEL_ID_NOT_IN_CONTEXT_WINDOW_TABLE_LINE = (
    "The model id {model} is not in CONTEXT_WINDOW_TOKENS_BY_MODEL_PREFIX, the threshold-hook's "
    "context-window table in scripts/handoff-context-threshold-hook.py, so the {share} of its "
    "context window this session has used assumes a {default_window_thousands}K window; tell the "
    "user, so the table can be updated."
)

BACKGROUND_TASKS_LIST_MISSING_SENTENCE = (
    "Claude Code sent no background_tasks list, so the threshold-hook could not see running "
    "subagents or background tasks, and this session-handoff stops any still running; tell the "
    "user that claude {claude_version} may be too old to send that list."
)
CLAUDE_VERSION_TIMEOUT_SECONDS = 10

# The approved ban on new work; the wait no longer counts work started after the deferral began.
NEW_WORK_DURING_HANDOFF_DEFERRAL_INSTRUCTION = (
    "Carry on, open approval-walks included. Short work, which usually ends "
    "within 10 minutes, such as a cold-read-fast-read, may start; run such work "
    "as a subagent or a background Bash task. When you run the handoff writer "
    "script, nc-systems/handoff/handoff-write-and-check-supervisor.py, before "
    "this agent-session ends, it names in your session-handoff each subagent "
    "still working, whenever it started, and each background Bash task that "
    "started since this handoff-deferral began and is still running, so you need "
    "not add that work to "
    "your task list; the end of this agent-session stops that work. Your "
    "successor is shown that work, and "
    "decides whether to start it again. If the writer script says it could not list "
    "that work, it says what to name by hand; name it in the session-handoff's next "
    "step. Do not start long "
    "work, such as a cold-read-full-run or a pull-request review: add it to "
    "your task list for your successor."
)

HANDOFF_DEFERRED_MARKER_NOT_DELETED = (
    "The threshold-hook could not delete this agent-session's handoff-deferral marker "
    "{path} on {host}: {error}. If this agent-session keeps working after a compaction "
    "instead of handing off, the threshold-hook asks for the /handoff skill again, even "
    "below the threshold, because the marker is still there.\n"
    "The text for the user: \"On {host}, the threshold-hook could not delete the "
    "handoff-deferral marker {path} ({error}). Please check why that path cannot be "
    "deleted, and delete it.\"\n"
    "If you are a subagent, put that text in your final report to the agent that "
    "dispatched you, and do not run the /handoff skill.\n"
    "Otherwise, in the same reply, give the user that text word for word, then run the "
    "/handoff skill, as the threshold-hook's instruction just before this message says, "
    "without waiting for an answer."
)

WAIT_LIMIT_TABLE_LOCATION = (
    "BACKGROUND_TASK_WAIT_LIMIT_MINUTES_BY_KIND in scripts/handoff-context-threshold-hook.py")
WAIT_LIMIT_TABLE_SENTENCE = f"Each kind's wait-limit is in {WAIT_LIMIT_TABLE_LOCATION}."

HANDOFF_DEFERRED_NOTICE = (
    "Context at {share} — handoff deferred while {running} run, because a "
    "handoff now would stop them.\n"
    "Do not run the /handoff skill now; carry on with your work, and a later "
    "system message will tell you when to run it. That message comes once "
    "the work running now has finished ({awaited}), with a background task, "
    "though not a subagent, counted as finished once it is as old as its kind's "
    "wait-limit even if it still runs, or once this session's context reaches the {ceiling:g}% ceiling. "
    + WAIT_LIMIT_TABLE_SENTENCE + " "
    "Work you start from now on does not delay that message, and when the "
    "handoff comes, it stops whatever is still running.\n"
    + NEW_WORK_DURING_HANDOFF_DEFERRAL_INSTRUCTION
)

HANDOFF_DEFERRED_UNKNOWN_COUNT_NOTICE = (
    "Context at {share} — handoff deferred: the transcript could not be fully "
    "read, so what is running is unknown, and a handoff now could stop it.\n"
    "Do not run the /handoff skill now; carry on with your work, and a later "
    "system message will tell you when to run it. That message comes once "
    "the hook can read the whole transcript and finds that the work started "
    "before now has finished, with a background task, though not a subagent, "
    "counted as finished once it is as old as its kind's wait-limit even if it "
    "still runs, or once "
    "this session's context reaches the {ceiling:g}% ceiling. "
    + WAIT_LIMIT_TABLE_SENTENCE + " Work you start "
    "from now on does not delay that message, and when the handoff comes, it "
    "stops whatever is still running.\n"
    + NEW_WORK_DURING_HANDOFF_DEFERRAL_INSTRUCTION
)

# Appended when an earlier marker file could not be read; the deferral starts again from now.
UNREADABLE_MARKER_REPLACED_LINE = (
    "The hook could not read this session's earlier handoff-deferral record "
    "({problem}), so the hook replaced that record with a new one: the work the "
    "hook now waits for is the work running now. Nothing for you to do about this."
)

# Without the record, the next turn's end would defer again and repeat this notice.
MARKER_NOT_WRITTEN_LINE = (
    "The hook could not save the list of work it waits for ({problem}), so at "
    "the end of your next turn it will defer again and repeat this notice. "
    "The second time you see this line about the list, tell the user, once: "
    "\"The handoff threshold hook cannot write {marker}, so it repeats its "
    "deferral notice at every turn's end; the session-handoff still fires at "
    "the context ceiling.\""
)


def awaited_phrase(flight: WorkInFlight) -> str:
    """Return the ids of the work the deferral waits for, by kind."""
    parts = [f"subagent {agent_id}" for agent_id in flight.subagent_ids]
    parts += [f"workflow {workflow_id}" for workflow_id in flight.workflow_ids]
    parts += [f"background task {task_id}" for task_id in flight.background_task_ids]
    return ", ".join(parts)


# A background Bash task holds the session-handoff while younger than its kind's wait-limit; past
# it the task is presumed stuck or open-ended. The first kind with a pattern that matches the whole
# command (re.fullmatch, ignoring case) is the task's kind. Work kinds come before waiting-task and
# match a name anywhere, so a command that both does work and waits keeps the work's limit.
# A waiting-task pattern spells out one whole command, because any work beside the wait would get 0
# and be killed by the handoff: each operand is one _WORD, which cannot hold a backtick,
# a command substitution or an unquoted separator. A variable name is read whole, or a failed
# match backtracks over every way to split it.
_WORD = r"""(?:[^\s;&|<>()`$'"\\]|\$\w+(?!\w)|\$\{\w+\}|'[^']*'|"(?:[^"`$\\]|\$\w+(?!\w)|\$\{\w+\})*")+"""
_ARGUMENTS = r"(?:[ \t]+" + _WORD + r")*"
_REDIRECTIONS = r"(?:[ \t]*(?:\d?>&\d|(?:\d?>>?|&>|<)[ \t]*" + _WORD + r"))*"
_COMMAND_END = r"[ \t]*(?:;|\n)\s*"
_COMMAND_PREFIX = r"\s*(?:(?:(?:cd|export)[ \t]+" + _WORD + r"|[A-Za-z_]\w*=(?:" + _WORD + r")?)[ \t]*(?:&&|;|\n)\s*)*"
_TO_THE_END = _REDIRECTIONS + r"[ \t]*;?\s*"
_WATCHER = (r"(?:bash[ \t]+|python3(?:[ \t]+-u)?[ \t]+)?(?:" + _WORD + r"/)?"
            r"(?:watch-and-merge-provisional[\w.-]*|wait-review-runs[\w.-]*"
            r"|wait-for-next-pull-request-event[\w.-]*|watch-open-pull-requests-nbd\.py)"
            + _ARGUMENTS + _REDIRECTIONS
            + r"""(?:[ \t]*\|[ \t]*(?:grep[ \t]+-v[ \t]+(?:'[^']*'|"[^"`$\\]*")|tail[ \t]+-n?[ \t]*\d+))*""")
_LOOP_CONDITION_CHECK = r"(?:![ \t]+)?(?:grep|pgrep|kill[ \t]+-0|test|\[|true|:)" + _ARGUMENTS + _REDIRECTIONS
_DEADLINE = r"\$\(date[ \t]+\+%s\)"
WAIT_LIMIT_TABLE_WAITING_TASK_KIND_NAME = "waiting-task"
BACKGROUND_TASK_WAIT_LIMIT_MINUTES_BY_KIND = (
    ("nc-mutation-testing", (r".*(?:mutation|mutmut|mutant).*",), 105.0),
    ("test-suite", (r".*(?:run-all-test-suites\.py|pytest|-test\.py\b|_test\.py\b|unittest"
                    r"|head-tests-with-retry|head-test-run|test-suite|run-suites).*",), 90.0),
    (WAIT_LIMIT_TABLE_WAITING_TASK_KIND_NAME, tuple(_COMMAND_PREFIX + shape + _TO_THE_END for shape in (
        r"sleep[ \t]+" + _WORD,
        r"gh[ \t]+pr[ \t]+checks(?=[^\n;&|]*--watch)" + _ARGUMENTS,
        r"gh[ \t]+run[ \t]+watch" + _ARGUMENTS,
        _WATCHER,
        r"(?:until|while)[ \t]+" + _LOOP_CONDITION_CHECK
        + r"(?:[ \t]*(?:&&|\|\|)[ \t]*" + _LOOP_CONDITION_CHECK + r")*"
        + _COMMAND_END + r"do\s+sleep[ \t]+" + _WORD + _COMMAND_END + r"done",
        r"end=\$\(\([ \t]*" + _DEADLINE + r"[ \t]*\+[ \t]*\d+[ \t]*\)\)" + _COMMAND_END
        + r"while[ \t]+\[[ \t]+" + _DEADLINE + r"[ \t]+-lt[ \t]+\$end[ \t]+\]" + _COMMAND_END
        + r"do\s+" + _WATCHER + _COMMAND_END + r"done")), 0.0),
)
# Allows a slow cold-read-full-run with one cell relaunch.
BACKGROUND_TASK_WAIT_LIMIT_MINUTES_WHEN_NO_KIND_MATCHES = 75.0
BACKGROUND_TASK_KIND_WHEN_NO_KIND_MATCHES = "no kind in the table matched"
_COMPILED_WAIT_LIMIT_KINDS = [
    (kind, [re.compile(pattern, re.I | re.S) for pattern in patterns], minutes)
    for kind, patterns, minutes in BACKGROUND_TASK_WAIT_LIMIT_MINUTES_BY_KIND]


def background_task_kind_and_wait_limit_minutes_from_command(command) -> tuple:
    """Return (kind, wait-limit in minutes) of the first kind with a pattern that matches the whole
    command; a command no pattern matches, or None for an unknown command, gets the no-match limit."""
    if isinstance(command, str):
        for kind, patterns, minutes in _COMPILED_WAIT_LIMIT_KINDS:
            if any(pattern.fullmatch(command) for pattern in patterns):
                return kind, minutes
    return BACKGROUND_TASK_KIND_WHEN_NO_KIND_MATCHES, BACKGROUND_TASK_WAIT_LIMIT_MINUTES_WHEN_NO_KIND_MATCHES


def background_task_still_within_wait(age_seconds, wait_limit_seconds) -> bool:
    """A task with no readable launch time counts as within its wait, unless its limit is 0."""
    if wait_limit_seconds <= 0:
        return False
    return age_seconds is None or age_seconds < wait_limit_seconds

# Covers a subagent just woken by its own background task, before it has launched or written more.
SUBAGENT_OWN_TRANSCRIPT_RECENT_WRITE_SECONDS = 5 * 60

# Claude Code gives every Stop hook this list of the session's running work: subagents, workflows,
# and background shell tasks, a subagent's own included. A subagent waiting on its own shell task
# leaves the list while it waits; the shell task stays on it.
BACKGROUND_TASKS_PAYLOAD_KEY = "background_tasks"
SHELL_TASK_TYPE = "shell"
SUBAGENT_TASK_TYPE = "subagent"
WORKFLOW_TASK_TYPE = "workflow"
RUNNING_TASK_STATUS = "running"

# The list shows a Monitor as a shell task; only its launch record, which carries this key, tells it apart.
MONITOR_LAUNCH_KEY = "timeoutMs"


class TranscriptCouldNotBeFullyRead(Exception):
    """An incomplete scan must not be mistaken for no work in flight."""


SPAWNED_SUBAGENT_STATUS = "async_launched"

# SendMessage to a finished subagent resumes it under the same task-id; its next notification decides.
RESUMED_SUBAGENT_KEY = "resumedAgentId"

# Check a toolUseResult key, not raw text: foreground grep output can contain the launch marker.
BACKGROUND_TASK_LAUNCH_KEY = "backgroundTaskId"

# Claude Code writes no task-notification for a task TaskStop stops; only the TaskStop result,
# whose toolUseResult carries this key beside task_id, records that the task ended.
TASK_STOP_TOOL_RESULT_MARKER_KEY = "task_type"

# Only the assistant record of a Bash call run in the background carries this input key.
BACKGROUND_BASH_CALL_KEY = '"run_in_background"'

# Completion notifications use these tags across several record types.
TASK_NOTIFICATION_PATTERN = re.compile(r"<task-notification>(.*?)</task-notification>", re.S)
TASK_NOTIFICATION_TASK_ID_PATTERN = re.compile(r"<task-id>([^<]+)</task-id>")


def background_bash_commands_by_tool_use_id_from_line(line: str) -> dict:
    """Return {tool_use id: command} for the Bash calls run in the background in this transcript
    line; a line that does not parse gives none, so its task gets the no-match wait-limit."""
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return {}
    message = record.get("message") if isinstance(record, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    commands = {}
    for block in content if isinstance(content, list) else []:
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        tool_input = block.get("input")
        if isinstance(tool_input, dict) and tool_input.get("run_in_background") is True:
            commands[block.get("id")] = tool_input.get("command")
    return commands


def tool_result_tool_use_id(record):
    """Return the tool_use id the record's first tool_result answers, or None."""
    message = record.get("message") if isinstance(record, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    for block in content if isinstance(content, list) else []:
        if isinstance(block, dict) and block.get("type") == "tool_result":
            return block.get("tool_use_id")
    return None


def claude_version_or_why_unread() -> str:
    """Return what `claude --version` prints, or a parenthesis saying why it could not be read."""
    try:
        completed = subprocess.run(["claude", "--version"], capture_output=True, text=True,
                                   timeout=CLAUDE_VERSION_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.SubprocessError) as problem:
        return f"(version unknown: running claude --version failed: {problem})"
    version = completed.stdout.strip()
    if completed.returncode != 0 or not version:
        output = (completed.stdout + completed.stderr).strip()
        return (f"(version unknown: claude --version exited {completed.returncode} "
                f"with output {output!r})")
    return version


def hook_payload_from_stdin() -> dict:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def context_window_tokens_from_table_or_none(model: str):
    """Return the model's context window in tokens from the table, or None when no prefix matches."""
    for prefix, window in CONTEXT_WINDOW_TOKENS_BY_MODEL_PREFIX.items():
        if model.startswith(prefix):
            return window
    return None


def newest_assistant_message(path: Path):
    """Return the newest assistant message with usage."""
    # Read backwards to avoid parsing the whole session at every turn boundary.
    file_size = path.stat().st_size
    window = FIRST_TAIL_READ_BYTES

    while True:
        with path.open("rb") as handle:
            start = max(0, file_size - window)
            handle.seek(start)
            chunk = handle.read()

        lines = chunk.split(b"\n")
        if start > 0:
            lines = lines[1:]  # the first line is a fragment of an earlier record

        for raw_line in reversed(lines):
            if not raw_line.strip():
                continue
            try:
                record = json.loads(raw_line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if record.get("type") != "assistant":
                continue
            message = record.get("message", {})
            if message.get("usage"):
                return message

        if start == 0:
            return None
        window *= 2


def context_used_tokens_window_and_model_from_transcript(transcript_path: str):
    """Return (used context tokens, context window tokens, model id), or None when unavailable."""
    if not transcript_path:
        return None
    path = Path(transcript_path).expanduser()
    if not path.is_file():
        return None

    try:
        message = newest_assistant_message(path)
    except OSError:
        return None
    if message is None:
        return None

    model = message.get("model", "")
    window = context_window_tokens_from_table_or_none(model)
    if window is None:
        window = DEFAULT_CONTEXT_WINDOW_TOKENS
    return used_tokens_of(message["usage"]), window, model


def context_used_percentage_from_transcript(transcript_path: str):
    """Return used context as a percentage, or None when unavailable."""
    reading = context_used_tokens_window_and_model_from_transcript(transcript_path)
    if reading is None:
        return None
    used_tokens, window, _model = reading
    return 100.0 * used_tokens / window


COMPACTION_RECORD_SUBTYPE = "compact_boundary"


def compaction_dropped_tokens_from_transcript(transcript_path: str) -> int:
    """Return the tokens all of the session's compactions dropped; 0 when it has none."""
    dropped_tokens = 0
    # Bytes that are not UTF-8 are read past: raising on them would stop the hook at every Stop.
    with Path(transcript_path).expanduser().open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if COMPACTION_RECORD_SUBTYPE not in line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Claude Code keeps the running total on each compaction record, so the newest one counts.
            if isinstance(record, dict) and record.get("subtype") == COMPACTION_RECORD_SUBTYPE:
                dropped_tokens = record["compactMetadata"]["cumulativeDroppedTokens"]
    return dropped_tokens


def context_used_plus_compaction_dropped_percentage_from_transcript(transcript_path: str):
    """Return the context used plus the tokens compactions dropped, as a percentage of the context
    window: the count the threshold and the ceiling are measured by. None when unavailable."""
    reading = context_used_tokens_window_and_model_from_transcript(transcript_path)
    if reading is None:
        return None
    used_tokens, window, _model = reading
    return 100.0 * (used_tokens + compaction_dropped_tokens_from_transcript(transcript_path)) / window


USED_TOKEN_FIELDS = ("input_tokens", "cache_read_input_tokens",
                     "cache_creation_input_tokens")
USAGE_ITERATIONS_FIELD = "iterations"
OWN_PASS_ITERATION_TYPE = "message"


def used_tokens_of(usage: dict) -> int:
    """Return the largest context used by this model's own passes."""
    # Top-level usage sums iterations; advisor passes use a different context and must be excluded.
    iterations = usage.get(USAGE_ITERATIONS_FIELD)
    if isinstance(iterations, list):
        own_passes = [
            sum(entry.get(field, 0) or 0 for field in USED_TOKEN_FIELDS)
            for entry in iterations
            if isinstance(entry, dict)
            and entry.get("type", OWN_PASS_ITERATION_TYPE) == OWN_PASS_ITERATION_TYPE
        ]
        if own_passes:
            return max(own_passes)
    return sum(usage.get(field, 0) or 0 for field in USED_TOKEN_FIELDS)


class WorkInFlight:
    """An empty scan must be falsy; a tuple of empty lists would still be truthy."""

    def __init__(self, subagent_ids, background_task_ids, workflow_ids=(), launched_at_by_id=None,
                 launching_subagent_id_by_task_id=None):
        self.subagent_ids = list(subagent_ids)
        self.background_task_ids = list(background_task_ids)
        self.workflow_ids = list(workflow_ids)
        # None for an id whose launch record carries no readable timestamp.
        self.launched_at_by_id = dict(launched_at_by_id or {})
        # Claude Code's list drops a subagent while it waits on its own shell task, so the deferral
        # waits for that task in its place.
        self.launching_subagent_id_by_task_id = dict(launching_subagent_id_by_task_id or {})

    def __bool__(self):
        return bool(self.subagent_ids or self.background_task_ids or self.workflow_ids)


def running_phrase(flight: WorkInFlight) -> str:
    """Return counts of the kinds of work in flight."""
    parts = []
    if flight.subagent_ids:
        parts.append(f"{len(flight.subagent_ids)} subagent(s)")
    if flight.workflow_ids:
        parts.append(f"{len(flight.workflow_ids)} workflow(s)")
    if flight.background_task_ids:
        parts.append(f"{len(flight.background_task_ids)} background task(s)")
    return " and ".join(parts)


def record_time(record):
    """Return the record's timestamp as an aware datetime, or None if unreadable."""
    # Python before 3.11 requires replacing the ISO 8601 trailing Z for fromisoformat.
    stamp = record.get("timestamp") if isinstance(record, dict) else None
    if not isinstance(stamp, str):
        return None
    try:
        moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def record_age_seconds(record, now):
    """Return seconds since the record timestamp, or None if unreadable."""
    moment = record_time(record)
    return None if moment is None else (now - moment).total_seconds()


def spawned_subagent_ids_in_flight(transcript_path: str) -> list:
    """Return Agent-tool ids the session transcript's notices leave running, excluding
    background Bash tasks."""
    return work_in_flight(transcript_path, background_task_wait_seconds=0,
                          should_read_subagent_own_transcripts=False).subagent_ids


def work_in_flight(transcript_path: str, background_task_wait_seconds=None,
                   now=None, should_read_subagent_own_transcripts=True,
                   should_raise_on_undecodable_bytes=False) -> WorkInFlight:
    """Return running subagents and background tasks in launch order.

    A subagent counts from its spawn, or from a resume after a SendMessage, until a final
    task-notification or a TaskStop call stops it; a TaskStop also ends a background task, and the
    background tasks of a subagent it stopped. One whose last task-notification is interim counts
    only while its own transcript shows work in flight; should_read_subagent_own_transcripts=False
    counts it from the notices alone.
    should_raise_on_undecodable_bytes=True raises TranscriptCouldNotBeFullyRead on bytes that are
    not UTF-8 anywhere in the file, instead of reading past them.
    background_task_wait_seconds=None gives each background task its kind's wait-limit, from the
    command of the Bash call that launched it; a number gives every task that wait instead.
    """
    # Scan the whole transcript: a running task may have launched hours before the tail.
    # Unreadable candidates raise; treating an incomplete scan as empty could kill running work.
    path = Path(transcript_path).expanduser() if transcript_path else None
    if path is None or not path.is_file():
        return WorkInFlight([], [])
    if now is None:
        now = datetime.now(timezone.utc)

    spawned_ids = []
    launched_task_ids = []
    launched_task_age = {}
    launched_task_command = {}
    background_command_by_tool_use_id = {}
    launched_at_by_id = {}
    # The last notification, TaskStop or resume for a task-id decides: an interim notification
    # leaves its subagent running, and a resume clears the entry so the subagent counts again.
    last_notification_is_interim = {}
    # Task-ids a TaskStop ended and no resume has restarted since.
    stopped_ids = set()
    try:
        decoding_errors = "strict" if should_raise_on_undecodable_bytes else "replace"
        with path.open("r", encoding="utf-8", errors=decoding_errors) as handle:
            for line_number, line in enumerate(handle, start=1):
                is_spawn_candidate = SPAWNED_SUBAGENT_STATUS in line
                is_launch_candidate = BACKGROUND_TASK_LAUNCH_KEY in line
                is_resume_candidate = RESUMED_SUBAGENT_KEY in line
                is_stop_candidate = TASK_STOP_TOOL_RESULT_MARKER_KEY in line
                if is_spawn_candidate or is_launch_candidate or is_resume_candidate or \
                        is_stop_candidate:
                    try:
                        record = json.loads(line)
                    except (json.JSONDecodeError, UnicodeDecodeError) as problem:
                        # A stop record not read only leaves its task counted as running.
                        if is_spawn_candidate or is_launch_candidate or is_resume_candidate:
                            raise TranscriptCouldNotBeFullyRead(
                                f"{path}, line {line_number}: a spawn, resume or launch record did "
                                f"not parse ({problem}); the line's first 200 characters: "
                                f"{line[:200].rstrip()!r}"
                            ) from problem
                        record = None
                    tool_result = record.get("toolUseResult") if isinstance(record, dict) else None
                    if not isinstance(tool_result, dict):
                        tool_result = {}
                    if is_spawn_candidate and \
                            tool_result.get("status") == SPAWNED_SUBAGENT_STATUS:
                        agent_id = tool_result.get("agentId")
                        if agent_id and agent_id not in spawned_ids:
                            spawned_ids.append(agent_id)
                            launched_at_by_id[agent_id] = record_time(record)
                    # A resume clears the subagent's last notification and its stop, so it counts
                    # as in flight again; a record without the key uses None, which is never a key.
                    last_notification_is_interim.pop(tool_result.get(RESUMED_SUBAGENT_KEY), None)
                    stopped_ids.discard(tool_result.get(RESUMED_SUBAGENT_KEY))
                    if is_launch_candidate:
                        task_id = tool_result.get(BACKGROUND_TASK_LAUNCH_KEY)
                        if task_id and task_id not in launched_task_age:
                            launched_task_ids.append(task_id)
                            launched_task_age[task_id] = record_age_seconds(record, now)
                            launched_task_command[task_id] = background_command_by_tool_use_id.get(
                                tool_result_tool_use_id(record))
                            launched_at_by_id[task_id] = record_time(record)
                    stopped_id = tool_result.get("task_id")
                    if TASK_STOP_TOOL_RESULT_MARKER_KEY in tool_result and isinstance(stopped_id, str):
                        last_notification_is_interim[stopped_id] = False
                        stopped_ids.add(stopped_id)
                if BACKGROUND_BASH_CALL_KEY in line:
                    background_command_by_tool_use_id.update(
                        background_bash_commands_by_tool_use_id_from_line(line))
                if "<task-id>" in line:
                    for notification in TASK_NOTIFICATION_PATTERN.findall(line):
                        interim = interim_recognizer.task_notification_is_interim(notification)
                        for task_id in TASK_NOTIFICATION_TASK_ID_PATTERN.findall(notification):
                            # An interim notice queued before a TaskStop can arrive after it.
                            if interim and task_id in stopped_ids:
                                continue
                            last_notification_is_interim[task_id] = interim
    except (OSError, UnicodeDecodeError) as problem:
        raise TranscriptCouldNotBeFullyRead(f"{path}: {problem}") from problem

    finished_ids = {task_id for task_id, interim in last_notification_is_interim.items()
                    if not interim}

    def still_within_wait(task_id):
        wait_limit_seconds = (
            background_task_kind_and_wait_limit_minutes_from_command(launched_task_command[task_id])[1] * 60
            if background_task_wait_seconds is None else background_task_wait_seconds)
        return background_task_still_within_wait(launched_task_age[task_id], wait_limit_seconds)

    def subagent_still_in_flight(agent_id):
        if agent_id in finished_ids:
            return False
        # A subagent with no notice since its spawn or resume has not stopped; only an interim
        # last notice is doubted.
        if agent_id not in last_notification_is_interim or not should_read_subagent_own_transcripts:
            return True
        return subagent_own_transcript_shows_work_in_flight(
            subagent_transcript_path(path, agent_id), background_task_wait_seconds, now)

    return WorkInFlight(
        [agent_id for agent_id in spawned_ids if subagent_still_in_flight(agent_id)],
        [task_id for task_id in launched_task_ids
         if task_id not in finished_ids and still_within_wait(task_id)],
        launched_at_by_id=launched_at_by_id,
    )


def work_in_flight_from_background_tasks(background_tasks: list, transcript_path: str,
                                        background_task_wait_seconds=None,
                                        now=None) -> WorkInFlight:
    """Return the running subagents, workflows and background shell tasks on Claude Code's list.

    The list gives no start time and shows a Monitor as a shell task, so each listed shell task's
    launch record is looked up in the session's transcript and its subagents' transcripts, the
    Workflow-tool agents' included: a shell task launched by the Monitor tool holds nothing, nor
    does one at least as old as its wait; one whose launch no transcript records counts as
    within its wait, unless its wait is 0. background_task_wait_seconds=None gives each shell task
    its kind's wait-limit, from the list entry's command; a number gives every task that wait. Each listed subagent and shell
    task is dated by its launch record, for a deferral that saved no list, and so is each subagent
    off the list whose transcript launched a listed shell task; a workflow, or work whose launch no
    transcript records, has no date. An entry that is not a running subagent, workflow or
    shell task holds nothing. Raises TranscriptCouldNotBeFullyRead when a transcript cannot be read,
    or a line naming a listed shell task or subagent does not parse.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    running = [entry for entry in background_tasks
               if isinstance(entry, dict) and entry.get("status") == RUNNING_TASK_STATUS
               and isinstance(entry.get("id"), str)]

    def ids_of(task_type):
        return [entry["id"] for entry in running if entry.get("type") == task_type]

    shell_ids = ids_of(SHELL_TASK_TYPE)
    launch_ages, monitor_ids, launching_subagent_id_by_task_id = (
        shell_task_launch_ages_and_monitor_ids(transcript_path, shell_ids, now))

    command_by_id = {entry["id"]: entry.get("command") for entry in running}

    def still_within_wait(task_id):
        wait_limit_seconds = (
            background_task_kind_and_wait_limit_minutes_from_command(command_by_id.get(task_id))[1] * 60
            if background_task_wait_seconds is None else background_task_wait_seconds)
        return background_task_still_within_wait(launch_ages.get(task_id), wait_limit_seconds)

    subagent_ids = ids_of(SUBAGENT_TASK_TYPE)
    launching_subagent_ids_off_the_list = sorted(
        set(launching_subagent_id_by_task_id.values()) - set(subagent_ids))
    launched_at_by_id = subagent_launched_at_by_id_from_transcript_spawn_records(
        transcript_path, subagent_ids + launching_subagent_ids_off_the_list)
    launched_at_by_id.update({task_id: now - timedelta(seconds=age)
                              for task_id, age in launch_ages.items() if age is not None})
    return WorkInFlight(
        subagent_ids,
        [task_id for task_id in shell_ids
         if task_id not in monitor_ids and still_within_wait(task_id)],
        ids_of(WORKFLOW_TASK_TYPE),
        launched_at_by_id=launched_at_by_id,
        launching_subagent_id_by_task_id=launching_subagent_id_by_task_id,
    )


def subagent_launched_at_by_id_from_transcript_spawn_records(transcript_path: str, subagent_ids: list) -> dict:
    """Return {subagent id: launch time, or None if undated} for the ids whose spawn record the
    session transcript holds. A missing transcript holds none."""
    launched_at_by_id = {}
    if not subagent_ids or not transcript_path:
        return launched_at_by_id
    path = Path(transcript_path).expanduser()
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_number, line in enumerate(handle, start=1):
                if SPAWNED_SUBAGENT_STATUS not in line or not any(
                        agent_id in line for agent_id in subagent_ids):
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as problem:
                    raise TranscriptCouldNotBeFullyRead(
                        f"{path}, line {line_number}: this line holds the id of a subagent on Claude "
                        f"Code's background_tasks list and the text {SPAWNED_SUBAGENT_STATUS!r}, which "
                        f"marks the record of a subagent's launch, but is not valid JSON ({problem}); "
                        f"the transcript is not read past this line") from problem
                tool_result = record.get("toolUseResult") if isinstance(record, dict) else None
                if isinstance(tool_result, dict) \
                        and tool_result.get("status") == SPAWNED_SUBAGENT_STATUS \
                        and tool_result.get("agentId") in subagent_ids:
                    launched_at_by_id.setdefault(tool_result["agentId"], record_time(record))
    except FileNotFoundError:
        return launched_at_by_id
    except OSError as problem:
        raise TranscriptCouldNotBeFullyRead(f"{path}: {problem}") from problem
    return launched_at_by_id


def shell_task_launch_ages_and_monitor_ids(transcript_path: str, shell_ids: list, now):
    """Return ({shell task id: seconds since its launch record, or None if undated},
    {ids whose launch record is the Monitor tool's},
    {shell task id: id of the subagent whose transcript holds its launch record})
    for the ids the transcripts record."""
    launch_ages, monitor_ids, launching_subagent_id_by_task_id = {}, set(), {}
    if not shell_ids or not transcript_path:
        return launch_ages, monitor_ids, launching_subagent_id_by_task_id
    session_path = Path(transcript_path).expanduser()
    subagent_directory = session_path.with_suffix("") / "subagents"
    # An undated subagent shell task counts as within its wait, so a subagent directory that
    # cannot be listed only keeps the handoff waiting, up to the ceiling.
    paths = [session_path, *session_subagent_transcript_paths(session_path)]
    for path in paths:
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not any(task_id in line for task_id in shell_ids):
                        continue
                    if BACKGROUND_TASK_LAUNCH_KEY not in line and MONITOR_LAUNCH_KEY not in line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as problem:
                        raise TranscriptCouldNotBeFullyRead(
                            f"{path}, line {line_number}: this line holds the id of a shell task on "
                            f"Claude Code's background_tasks list and the text {BACKGROUND_TASK_LAUNCH_KEY!r} or "
                            f"{MONITOR_LAUNCH_KEY!r}, which mark the record of a background task's launch, "
                            f"but is not valid JSON ({problem}); the transcript is not read past this line; "
                            f"the line's first 200 characters: {line[:200].rstrip()!r}"
                        ) from problem
                    tool_result = record.get("toolUseResult") if isinstance(record, dict) else None
                    if not isinstance(tool_result, dict):
                        continue
                    if tool_result.get(BACKGROUND_TASK_LAUNCH_KEY) in shell_ids:
                        launch_ages.setdefault(tool_result[BACKGROUND_TASK_LAUNCH_KEY],
                                               record_age_seconds(record, now))
                        # A Workflow-tool agent's task is tied to no subagent: the workflow is
                        # listed while its agents run, and their tasks are killed with it.
                        if path.parent == subagent_directory \
                                and path.stem.startswith(SUBAGENT_TRANSCRIPT_PREFIX):
                            launching_subagent_id_by_task_id.setdefault(
                                tool_result[BACKGROUND_TASK_LAUNCH_KEY],
                                path.stem[len(SUBAGENT_TRANSCRIPT_PREFIX):])
                    if MONITOR_LAUNCH_KEY in tool_result and tool_result.get("taskId") in shell_ids:  # pragma: no mutate, only a Monitor's result carries timeoutMs and it always carries a taskId, while the other results with a taskId are task-list updates, whose numeric ids no shell task has, so or acts as and
                        monitor_ids.add(tool_result["taskId"])
        except OSError as problem:
            raise TranscriptCouldNotBeFullyRead(f"{path}: {problem}") from problem
    return launch_ages, monitor_ids, launching_subagent_id_by_task_id


SUBAGENT_TRANSCRIPT_PREFIX = "agent-"


def session_subagent_transcript_paths(session_transcript_path) -> list:
    """Return the session's subagent transcripts, sorted: the Agent-tool subagents' beside the
    session's, then the Workflow-tool agents', one directory per workflow run under workflows/."""
    subagent_directory = Path(session_transcript_path).with_suffix("") / "subagents"
    # A workflow run's directory also holds journal.jsonl, which is not a transcript.
    return [*sorted(subagent_directory.glob("*.jsonl")),
            *sorted(subagent_directory.glob(f"workflows/*/{SUBAGENT_TRANSCRIPT_PREFIX}*.jsonl"))]


def subagent_transcript_path(session_transcript_path, agent_id) -> Path:
    """Return where Claude Code writes the subagent's own transcript, beside the session's."""
    return (Path(session_transcript_path).with_suffix("") / "subagents"
            / f"{SUBAGENT_TRANSCRIPT_PREFIX}{agent_id}.jsonl")


def subagent_own_transcript_shows_work_in_flight(subagent_path: Path,
                                                 background_task_wait_seconds,
                                                 now) -> bool:
    """Return True while the subagent's own transcript was written within the recent-write
    window, or shows a background task of its own still within its wait.

    A missing transcript shows neither, so the subagent counts as finished. One that cannot be
    looked up or read, or holds bytes that are not UTF-8, raises TranscriptCouldNotBeFullyRead.
    """
    # Path.is_file() returns False on any failed stat, which would release a subagent whose
    # transcript exists but cannot be reached.
    try:
        subagent_path.stat()
    except FileNotFoundError:
        return False
    except OSError as problem:
        raise TranscriptCouldNotBeFullyRead(f"{subagent_path}: {problem}") from problem
    try:
        for record in transcript_records.records_newest_first(subagent_path):
            age = record_age_seconds(record, now)
            if age is not None:
                if age <= SUBAGENT_OWN_TRANSCRIPT_RECENT_WRITE_SECONDS:
                    return True
                break
    except (OSError, UnicodeDecodeError) as problem:
        raise TranscriptCouldNotBeFullyRead(f"{subagent_path}: {problem}") from problem
    return bool(work_in_flight(str(subagent_path), background_task_wait_seconds, now=now,
                               should_raise_on_undecodable_bytes=True).background_task_ids)


def awaited_work_still_in_flight(marker, flight: WorkInFlight) -> bool:
    """Return whether any work the deferral waits for is still in flight."""
    if marker.awaited_work_is_unknown:
        # No list was saved: wait for what was launched before the deferral began.
        def launched_before_deferral(work_id):
            # A subagent's own shell task stands in for the subagent, which is off the list while
            # the task runs, so it is dated by the subagent's launch.
            launched_at = flight.launched_at_by_id.get(
                flight.launching_subagent_id_by_task_id.get(work_id, work_id))
            return launched_at is None or launched_at <= marker.deferral_began_at
        return any(launched_before_deferral(work_id) for work_id in
                   flight.subagent_ids + flight.workflow_ids + flight.background_task_ids)
    awaited_subagent_ids = set(marker.awaited_subagent_ids)
    return bool(awaited_subagent_ids & set(flight.subagent_ids)
                or set(marker.awaited_workflow_ids) & set(flight.workflow_ids)
                or set(marker.awaited_background_task_ids) & set(flight.background_task_ids)
                or any(flight.launching_subagent_id_by_task_id.get(task_id) in awaited_subagent_ids
                       for task_id in flight.background_task_ids))


def defer(session_id, used, share, flight, arguments, unreadable_marker_problem=None,
          now=None) -> int:
    """Save the work in flight as the work to wait for, and tell the agent the handoff is deferred."""
    count_is_known = flight is not None
    marker_record = handoff_deferred_marker_and_refused_commands_files_common.HandoffDeferredMarker(
        used_percentage=used,
        deferral_began_at=now or datetime.now(timezone.utc),
        # A subagent off the list while it waits on its own shell task returns to the list when the
        # task ends, and must still be waited for then.
        awaited_subagent_ids=(flight.subagent_ids + [
            flight.launching_subagent_id_by_task_id[task_id] for task_id in flight.background_task_ids
            if flight.launching_subagent_id_by_task_id.get(task_id) not in (None, *flight.subagent_ids)]
            if count_is_known else []),
        awaited_background_task_ids=flight.background_task_ids if count_is_known else [],
        awaited_work_is_unknown=not count_is_known,
        awaited_workflow_ids=flight.workflow_ids if count_is_known else [],
    )
    lines = [
        HANDOFF_DEFERRED_NOTICE.format(
            share=share, running=running_phrase(flight), awaited=awaited_phrase(flight),
            ceiling=arguments.ceiling_used_percentage)
        if count_is_known
        else HANDOFF_DEFERRED_UNKNOWN_COUNT_NOTICE.format(
            share=share, ceiling=arguments.ceiling_used_percentage)
    ]
    try:
        handoff_deferred_marker_and_refused_commands_files_common.handoff_deferred_marker_write(HANDOFF_DIRECTORY, session_id, marker_record)
        if unreadable_marker_problem:
            lines.append(UNREADABLE_MARKER_REPLACED_LINE.format(problem=unreadable_marker_problem))
    except OSError as problem:
        lines.append(MARKER_NOT_WRITTEN_LINE.format(
            problem=problem,
            marker=handoff_deferred_marker_and_refused_commands_files_common.handoff_deferred_marker_path(HANDOFF_DIRECTORY, session_id)))
    print("\n".join(lines), file=sys.stderr)
    return 2  # exit 2 surfaces stderr to the agent as a system message


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fire the handoff skill when context runs low.",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--threshold-used-percentage", type=float,
                        default=DEFAULT_THRESHOLD_USED_PERCENTAGE,
                        help="the share of the context window, in percent, that the context used "
                             "plus the tokens compactions dropped must reach for the hook to ask "
                             "for the /handoff skill: the reincarnation threshold")
    parser.add_argument(
        "--ceiling-used-percentage", type=float, default=65.0,
        help="the share of the context window, in percent, at or above which the context used "
             "plus the tokens compactions dropped fires the handoff even with work in flight",
    )
    arguments = parser.parse_args(argv)

    if os.environ.get(REINCARNATION_OWNED_BY_CALLER_VARIABLE):
        return 0

    payload = hook_payload_from_stdin()
    if stop_hooks_stay_silent_rule.stop_hook_stays_silent_while_agent_answers_a_stop_hook(payload):
        return 0
    session_id = payload.get("session_id", "")
    if not session_id:
        return 0

    transcript_path = payload.get("transcript_path", "")
    background_tasks = payload.get(BACKGROUND_TASKS_PAYLOAD_KEY)
    background_tasks_list_is_missing = not isinstance(background_tasks, list)
    reading = context_used_tokens_window_and_model_from_transcript(transcript_path)
    if reading is None:
        return 0
    used_tokens, window, model = reading
    dropped_tokens = compaction_dropped_tokens_from_transcript(transcript_path)
    used = 100.0 * (used_tokens + dropped_tokens) / window
    share = (SHARE_WITH_COMPACTION_DROPPED.format(
                 used_percentage=100.0 * used_tokens / window, used_plus_dropped_percentage=used)
             if dropped_tokens else f"{used:.0f}%")
    # The count can fall below the threshold after a deferral, as when the session moves to a model
    # with a larger window; a compaction does not lower it. The deferred marker records that the
    # threshold was passed, so the handoff its notice promised still comes.
    if used < arguments.threshold_used_percentage and not deferred_marker_path(session_id).exists():
        return 0

    fired_marker = handoff_asked_marker_path(session_id)
    if fired_marker.exists():
        return 0

    # Reincarnation kills in-process work; defer below the ceiling so work can finish.
    if used < arguments.ceiling_used_percentage:
        # An incomplete scan is not an all-clear; defer only as far as the context ceiling.
        try:
            flight = (WorkInFlight([], []) if background_tasks_list_is_missing
                      else work_in_flight_from_background_tasks(background_tasks, transcript_path))
            count_is_known = True
        except TranscriptCouldNotBeFullyRead:
            flight = None
            count_is_known = False

        try:
            marker = handoff_deferred_marker_and_refused_commands_files_common.handoff_deferred_marker_read(HANDOFF_DIRECTORY, session_id)
            unreadable_marker_problem = None
        except handoff_deferred_marker_and_refused_commands_files_common.HandoffDeferredMarkerUnreadable as problem:
            marker = None
            unreadable_marker_problem = str(problem)

        if marker is not None:
            # Repeating the notice would drive idle sessions into a loop; completion notifications wake them.
            if not count_is_known or awaited_work_still_in_flight(marker, flight):
                return 0
        elif not count_is_known or flight:
            return defer(session_id, used, share, flight, arguments, unreadable_marker_problem)

    try:
        # A failed marker write would repeat the handoff request every turn.
        HANDOFF_DIRECTORY.mkdir(parents=True, exist_ok=True)
        fired_marker.write_text(f"{used:.1f}\n", encoding="utf-8")
    except OSError:
        pass

    print(HANDOFF_INSTRUCTION.format(share=share), file=sys.stderr)
    if background_tasks_list_is_missing:
        print(BACKGROUND_TASKS_LIST_MISSING_SENTENCE.format(
                  claude_version=claude_version_or_why_unread()),
              file=sys.stderr)
    # The deferral's promise is kept; left in place, the marker would refire the
    # instruction below the threshold after every later compaction. It is moved, not
    # deleted, because the handoff writer still needs the deferral's start time.
    deferred_marker = deferred_marker_path(session_id)
    try:
        handoff_deferred_marker_and_refused_commands_files_common.handoff_deferred_marker_move_aside_at_fire(
            HANDOFF_DIRECTORY, session_id)
    except OSError as error:
        print(HANDOFF_DEFERRED_MARKER_NOT_DELETED.format(
                  path=deferred_marker, host=socket.gethostname(), error=error),
              file=sys.stderr)
    # Printed last: the marker message above refers to the instruction just before it.
    if context_window_tokens_from_table_or_none(model) is None:
        print(MODEL_ID_NOT_IN_CONTEXT_WINDOW_TABLE_LINE.format(
                  model=model, share=share,
                  default_window_thousands=DEFAULT_CONTEXT_WINDOW_TOKENS // 1000),
              file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
