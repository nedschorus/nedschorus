#!/usr/bin/env python3
"""Run one agent session and reincarnate it when it writes a handoff.

The handoff system's supervisor (specification:
nc-systems/handoff/handoff-design.md). One supervisor per agent, run in
that agent's console. It owns the whole reincarnation cycle because an agent
cannot exit itself: /clear and /exit are unavailable to it, and self-SIGTERM
trips the safety classifier.

The cycle, per reincarnation:
  1. Watch the handoff file for a restart-counter above the last consumed.
  2. Kill the running session.
  3. Extract its dialog to disk before anything else proceeds.
  4. Each generation opens the same launcher-pinned task list.
  5. Print one queue-status line — to the console only. It does not ride
     the initial agent instructions (user-ruled 2026-08-29: "Also useless is the
     reminder there are files in the queues. Thats what queues are for.").
  6. Launch the successor with the initial agent instructions. Beside the
     branch sync's line they carry, for agent-instructions-editor alone, one
     line per system whose code moved on
     main past the commit its overview was checked against, until the user has been shown
     that overview's refresh that day (overview_refresh_due_lines), plus
     one line saying so when the day's reminder marks cannot be read,
     and, on the Mac from noon Pacific, one line when the day's memory review
     is due (memory_review_due_lines).
     Every launch, a resume included, also carries the agent-seat's leftover
     work-snapshots whose worktree is gone or no longer holds their changes,
     with the steps to restore them
     (uncommitted_work_snapshot_text).
  7. Keep the current and previous handoff and extract; delete older ones.

The handoff file the agent writes (simple `key: value` lines):
  written-at:           UTC timestamp, ISO 8601
  next-step:            the first action the successor takes
  restart-counter:      predecessor's counter plus one
  dont-restart:         optional; any value makes the supervisor ask before relaunching
  spawned-subagent-<n>: optional, one per subagent still working when the
                        handoff was written; the reincarnation kills them, so the
                        successor is told it may need to re-commission
                        similar agents. Subagents that completed, failed, or
                        were stopped are not recorded at all (user-ruled
                        2026-08-29)

How much dialog to carry is not among them: the extractor takes the tail that
clears its word floor, so the retiring agent exercises no judgment over what
its successor receives.

When a session dies WITHOUT writing a handoff, the supervisor resumes it
rather than standing the seat down (user-ruled 2026-09-21, GHI [The
handoff-supervisor resumes a session that died without a handoff, instead of
stopping the seat](https://github.com/nedschorus/nedschorus/issues/613)). The
behaviour that prompted it: on 2026-09-21 the MD-skills seat finished a turn
cleanly, sat idle for 4m41s, was terminated with exit code 143 beside an
intact 6.4 MB transcript, and stayed dark until the user happened to look.
The supervisor can know the MANNER of a death and never its AGENT — POSIX
does not tell a parent who sent a signal, and the child's dying words go to
the console it inherited, never to this process — so the choice is made on
process.returncode alone (resume_or_stop_after_a_death_without_a_handoff):

  0              stop.   A clean exit is a decision, not a crash
  143 / -15      resume. SIGTERM
  137 / -9       resume. SIGKILL — OOM or `kill -9`
  other non-zero resume. The CLI exited with an error status
  None           stop.   An adopted session, whose code this supervisor
                         never owned

Two gates hold every resume: CONSECUTIVE_RESUMES_WITHOUT_NEW_WORK_BUDGET, and
the no-terminal refusal that already guards a successor — a resumed session
needs a seat exactly as a successor does. Every stopping path still writes the
exit record, so scripts/recover-crashed-seats.py remains the fallback and its
offer-versus-resume behaviour is unchanged.

Never pass --allowedTools on the launch: it silently swallows the positional
prompt, so the successor would boot with no instructions at all.

Starting a supervisor requires a nonempty CLAUDE_CODE_TASK_LIST_ID from
scripts/launch-claude-mac or scripts/launch-claude-ubuntu.

Exit codes: 0 clean stop, 2 bad invocation, 3 the agent command is missing,
4 the supervisor lock could not be claimed.
"""

import argparse
import ctypes
import fcntl
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIRECTORY = REPOSITORY_ROOT / "scripts"

_worth_resuming_spec = importlib.util.spec_from_file_location(
    "seat_transcript_worth_resuming",
    SCRIPTS_DIRECTORY / "seat-transcript-worth-resuming.py")
worth_resuming = importlib.util.module_from_spec(_worth_resuming_spec)
_worth_resuming_spec.loader.exec_module(worth_resuming)

_agent_binary_update_under_lock_spec = importlib.util.spec_from_file_location(
    "agent_binary_update_under_lock",
    SCRIPTS_DIRECTORY / "agent-binary-update-under-lock.py")
agent_binary_update_under_lock = importlib.util.module_from_spec(
    _agent_binary_update_under_lock_spec)
_agent_binary_update_under_lock_spec.loader.exec_module(agent_binary_update_under_lock)

_architecture_overview_path_template_and_checked_against_commit_reader_spec = importlib.util.spec_from_file_location(
    "architecture_overview_path_template_and_checked_against_commit_reader",
    SCRIPTS_DIRECTORY / "architecture-overview-path-template-and-checked-against-commit-reader.py")
architecture_overview_path_template_and_checked_against_commit_reader = importlib.util.module_from_spec(
    _architecture_overview_path_template_and_checked_against_commit_reader_spec)
_architecture_overview_path_template_and_checked_against_commit_reader_spec.loader.exec_module(architecture_overview_path_template_and_checked_against_commit_reader)

DAILY_MEMORY_REVIEW_MARK_PATH = Path(__file__).resolve().with_name("daily-memory-review-mark.py")
_daily_memory_review_mark_spec = importlib.util.spec_from_file_location(
    "daily_memory_review_mark", DAILY_MEMORY_REVIEW_MARK_PATH)
daily_memory_review_mark = importlib.util.module_from_spec(_daily_memory_review_mark_spec)
_daily_memory_review_mark_spec.loader.exec_module(daily_memory_review_mark)

DAILY_OVERVIEW_REFRESH_REMINDER_MARK_PATH = Path(__file__).resolve().with_name(
    "daily-overview-refresh-reminder-mark.py")
_daily_overview_refresh_reminder_mark_spec = importlib.util.spec_from_file_location(
    "daily_overview_refresh_reminder_mark", DAILY_OVERVIEW_REFRESH_REMINDER_MARK_PATH)
daily_overview_refresh_reminder_mark = importlib.util.module_from_spec(
    _daily_overview_refresh_reminder_mark_spec)
_daily_overview_refresh_reminder_mark_spec.loader.exec_module(
    daily_overview_refresh_reminder_mark)

_checkout_freshness_catch_up_spec = importlib.util.spec_from_file_location(
    "checkout_freshness_catch_up", SCRIPTS_DIRECTORY / "checkout-freshness-catch-up.py")
checkout_freshness_catch_up = importlib.util.module_from_spec(_checkout_freshness_catch_up_spec)
_checkout_freshness_catch_up_spec.loader.exec_module(checkout_freshness_catch_up)

UNCOMMITTED_WORK_SNAPSHOTS_PATH = Path(__file__).resolve().with_name(
    "uncommitted-work-snapshots.py")
_uncommitted_work_snapshots_spec = importlib.util.spec_from_file_location(
    "uncommitted_work_snapshots", UNCOMMITTED_WORK_SNAPSHOTS_PATH)
uncommitted_work_snapshots = importlib.util.module_from_spec(_uncommitted_work_snapshots_spec)
_uncommitted_work_snapshots_spec.loader.exec_module(uncommitted_work_snapshots)

# The opening is an EMPTY_SUCCESSOR_MARKERS entry used to recognize a workless resume.
RESUME_PROMPT_WHEN_A_SESSION_ENDED_WITHOUT_A_HANDOFF = (
    "This session was resumed by crash recovery (nedschorus#120): the "
    "previous session ended without writing a handoff. Re-verify in-flight "
    "state before trusting it, then continue the work underway."
)

# subprocess reports signals as negative return codes; shell wrappers report 128 + signal.
SIGTERM_SESSION_EXIT_CODES = (143, -15)
SIGKILL_SESSION_EXIT_CODES = (137, -9)

# Repeated workless resumes can loop indefinitely and spend money on each launch.
CONSECUTIVE_RESUMES_WITHOUT_NEW_WORK_BUDGET = 1

PROJECTS_ROOT = Path.home() / ".claude" / "projects"
# Live supervisors resolve this path at import; moving the extractor would break those processes.
EXTRACTOR_PATH = SCRIPTS_DIRECTORY / "handoff-extract-conversation.py"
CLEAN_WORKTREES_PATH = SCRIPTS_DIRECTORY / "clean-worktrees.py"
FINISHED_WORKTREE_REMOVAL_TIMEOUT_SECONDS = 180
WORKTREE_CLEANER_STOP_GRACE_SECONDS = 5
HANDOFF_POLL_SECONDS = 2.0
GENERATIONS_KEPT = 2

# The supervisor owns the prompt flag so recovery launches receive the same instructions as launcher boots.
DEFAULT_APPENDED_SYSTEM_PROMPT_PATH = (
    REPOSITORY_ROOT / "docs" / "agents"
    / "seat-session-appended-system-prompt.md"
)

# The writer needs the launch directory after a cd; the session ID prevents a child session from handing off its parent.
HANDOFF_SUPERVISOR_AGENT_NAME_ENVIRONMENT_VARIABLE = "NEDSCHORUS_HANDOFF_SUPERVISOR_AGENT_NAME"
HANDOFF_SUPERVISOR_WORKING_DIRECTORY_ENVIRONMENT_VARIABLE = (
    "NEDSCHORUS_HANDOFF_SUPERVISOR_WORKING_DIRECTORY"
)
HANDOFF_SUPERVISOR_SESSION_ID_ENVIRONMENT_VARIABLE = "NEDSCHORUS_HANDOFF_SUPERVISOR_SESSION_ID"

# Heartbeat age serves login recovery and diagnostics; live ownership requires a process check.
HEARTBEAT_INTERVAL_SECONDS = 10.0

# Read the timeout at call time so tests can override it after import.
PROCESS_COMMAND_LINE_READ_TIMEOUT_SECONDS = 15


NEXT_STEP_VERBATIM_FIELD = "next-step-verbatim"
NEXT_STEP_BLOCK_OPENING_MARKER = "<<END-OF-NEXT-STEP"
NEXT_STEP_BLOCK_TERMINATOR = "END-OF-NEXT-STEP"
NEXT_STEP_BLOCK_UNTERMINATED_FIELD = "next-step-verbatim-unterminated"
SPAWNED_SUBAGENT_FIELD_PREFIX = "spawned-subagent-"
WRITTEN_BY_SESSION_FIELD = "written-by-session"
WRITTEN_BY_SESSION_UNKNOWN_VALUE = "unknown"

BRANCH_STATE_INSTRUCTION = (
    " — If this branch has never been pushed, rebase it onto origin/main "
    "before your first substantive action and rerun the tests for what you "
    "touched. If it is pushed, leave it as it is, and start new work on a "
    "branch from origin/main. If this seat has "
    "open pull requests, check their state with `gh`: merge-lane-2 reviews "
    "and merges them; when one has a review with findings, dispatch a forked "
    "subagent to fix it — never extend a head you've already pushed. When "
    "one conflicts with main, clear the conflict with the hand-merge that "
    "scripts/branch-conflict-check.py describes."
)

# Overview refreshes are this agent-seat's job; other agent-seats have jobs of their own.
AGENT_SEAT_GIVEN_OVERVIEW_REFRESH_LINES = "agent-instructions-editor"

SYSTEM_OVERVIEW_PATH_TEMPLATE = architecture_overview_path_template_and_checked_against_commit_reader.PATH_TEMPLATE

# The draft suffix avoids a tracked-name collision; the queue permits drafting before overview approval.
SYSTEM_OVERVIEW_DRAFT_PATH_TEMPLATE = (
    "docs/nedschorus-wiki/queue/nedschorus-{system}-architecture-overview-draft.md")

OVERVIEW_REFRESH_CHECK_GIT_TIMEOUT_SECONDS = 15

OVERVIEW_REFRESH_CHECK_GH_TIMEOUT_SECONDS = 30

OVERVIEW_REFRESH_REMINDER_MARKS_READ_TIMEOUT_SECONDS = 30

OVERVIEW_REFRESH_DUE_INSTRUCTION_TEMPLATE = (
    " — Dispatch a subagent to write {overview_draft_path}: a copy of "
    "{overview_path} refreshed against the commits "
    "`{commit_listing_command}` lists, as "
    "docs/nedschorus-wiki/nedschorus-how-to-write-an-architecture-overview.md "
    "defines a refresh, ending in the line `{checked_against_line}`. When the subagent reports, show the user the "
    "diff between {overview_path} and {overview_draft_path}. Once the user "
    "has been shown the diff, run `python3 {reminder_mark_script} {system}`. "
    "When the user approves the diff, write {overview_path} from "
    "{overview_draft_path} and delete {overview_draft_path}."
)

OVERVIEW_REFRESH_REMINDER_MARKS_UNREAD_TEMPLATE = (
    "overview check could not read the day's reminder marks in {marks_location}, "
    "so no line is withheld for a reminder already given: {error}"
    " — Before you act on any overview-refresh line in this prompt, tell the "
    "user that the handoff-supervisor could not read the day's overview-refresh "
    "reminder marks, giving the location {marks_location} and the error above, "
    "and that an overview-refresh line in this prompt may therefore repeat a "
    "refresh the user was already shown today."
)

# Appended only when ned-box gave no answer; an answer that does not parse
# came from ned-box, so the ssh check would mislead.
OVERVIEW_REFRESH_REMINDER_MARKS_NED_BOX_DID_NOT_ANSWER_SENTENCE = (
    " Because ned-box did not answer this machine, also tell the user that "
    "`ssh nedlern@ned-box true`, run on the Mac, shows whether ned-box answers "
    "again, and that the next agent-session's start reads the marks again."
)

MEMORY_REVIEW_DUE_FROM_PACIFIC_HOUR = 12

MEMORY_REVIEW_CHECK_READ_TIMEOUT_SECONDS = 30

MEMORY_REVIEW_DUE_INSTRUCTION_TEMPLATE = (
    ". A memory store holds notes that agents saved for later agents. Nothing "
    "makes a later agent read a note at the moment it matters, so each entry "
    "goes to the user for a ruling, and then the entry is deleted. This review "
    "runs on the Mac, which reads both machines' stores.\n"
    "Before anything else, run `python3 {mark_script} started`.\n"
    "The Mac's store is {mac_memory_store}. ned-box's store is "
    "{ned_box_memory_store_mac_mount}. If that ned-box path does not open, use "
    "{ned_box_memory_store} over ssh, and run the shell commands for ned-box's "
    "entries there over ssh.\n"
    "Put every entry of both stores to the user in one approval-walk with the "
    "/walk-me-through skill, one entry per item. Items whose entries have little "
    "at stake may be shown together in one message, each keeping its own item "
    "number, as the skill allows.\n"
    "In each item, show the entry's text and recommend one outcome: a fix to an "
    "instruction file now, which is best; a task on your task list; a GitHub "
    "issue filed with /ghi-write; or nothing, if the entry is stale.\n"
    "When the user rules on an entry, carry out his ruling. Then delete the "
    "entry's file, and remove its line from that store's MEMORY.md index, both "
    "with shell commands.\n"
    "Do not edit an entry: the instruction-file guard refuses every Edit or "
    "Write into a memory store.\n"
    "When the approval-walk closes, run `python3 {mark_script} done`."
)

SUPERVISOR_POINTER_SENTENCE = (
    "This session was launched by nc-systems/handoff/handoff-supervisor.py, which "
    "watches this seat and composed this prompt — read it if you need to "
    "investigate the handoff mechanism."
)

# Subagent IDs resolve only within their session, so a successor must re-commission unfinished work.
ORPHANED_SUBAGENT_ROSTER_SENTENCE_TEMPLATE = (
    "The session you are replacing had {subagent_count} subagent(s) still working when it ended: "
    "{joined_roster}. You may need to re-commission similar agents. If you need more "
    "context, the dead agents' full transcripts are at "
    "{transcript_directory}/subagents/agent-<id>.jsonl."
)


# Leading spaces separate these suffixes from the preambles they are appended to.
UNTERMINATED_NEXT_STEP_BLOCK_NOTE = (
    " NOTE: this handoff's verbatim next-step block was unterminated, so what "
    "follows is the collapsed one-line form and may have lost structure."
)
NO_NEXT_STEP_TAIL_SENTENCE = " Then continue from where that dialog ends."


def parse_handoff_file(handoff_path: Path) -> dict:
    """Return handoff fields, flagging an unterminated verbatim block separately."""
    fields = {}
    lines = handoff_path.read_text(encoding="utf-8").splitlines()
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        index += 1
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip().lower()
        value = value.strip()

        if key == NEXT_STEP_VERBATIM_FIELD and value == NEXT_STEP_BLOCK_OPENING_MARKER:
            block, terminated = [], False
            while index < len(lines):
                candidate = lines[index]
                index += 1
                # Match the terminator exactly: an indented lookalike inside a code fence is content.
                if candidate == NEXT_STEP_BLOCK_TERMINATOR:
                    terminated = True
                    break
                block.append(candidate)
            if terminated:
                if key not in fields:
                    fields[key] = "\n".join(block)
            else:
                fields[NEXT_STEP_BLOCK_UNTERMINATED_FIELD] = "yes"
            continue

        if key not in fields:  # First occurrence wins so later prose cannot overwrite a field.
            fields[key] = value
    return fields


# This names the launched or adopted session; a later worktree takeover does not update it.
LAUNCHED_SESSION_ID_STATE_KEY = "launched_session_id"
# Read compatibility for existing state files; subsequent writes use only the new key.
LEGACY_SESSION_ID_STATE_KEY = "session_id"


def fresh_supervisor_state() -> dict:
    return {"consumed_counter": None, LAUNCHED_SESSION_ID_STATE_KEY: None, "generation": 0}


def read_supervisor_state(state_path: Path) -> dict:
    if not state_path.is_file():
        return fresh_supervisor_state()
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        print("handoff-supervisor: unreadable state file; starting fresh", file=sys.stderr)
        return fresh_supervisor_state()
    if (LAUNCHED_SESSION_ID_STATE_KEY not in state
            and LEGACY_SESSION_ID_STATE_KEY in state):
        state[LAUNCHED_SESSION_ID_STATE_KEY] = state.pop(LEGACY_SESSION_ID_STATE_KEY)
    return state


def write_supervisor_state(state_path: Path, state: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def stamp_heartbeat(state_path: Path, state: dict) -> None:
    state["last_poll_at"] = datetime.now(timezone.utc).isoformat()
    write_supervisor_state(state_path, state)


# Record presence distinguishes a supervised exit from a crash, even when the exit code is unknown.
AGENT_EXIT_CODE_STATE_KEY = "agent_exit_code"
AGENT_EXIT_RECORDED_AT_STATE_KEY = "agent_exit_recorded_at"


def record_agent_exit_in_supervisor_state(state_path: Path, state: dict, exit_code) -> None:
    # A signal exit code is negative; an adopted session's unknown code is None.
    state[AGENT_EXIT_CODE_STATE_KEY] = exit_code
    state[AGENT_EXIT_RECORDED_AT_STATE_KEY] = datetime.now(timezone.utc).isoformat(
        timespec="seconds")
    write_supervisor_state(state_path, state)


def clear_agent_exit_record_from_supervisor_state(state: dict) -> None:
    # Clear before launch or adoption so an old clean exit cannot mask a later crash.
    state.pop(AGENT_EXIT_CODE_STATE_KEY, None)
    state.pop(AGENT_EXIT_RECORDED_AT_STATE_KEY, None)


def agent_exit_record_from_supervisor_state(state: dict):
    """Return (exit_code, recorded_at), or None without an exit record."""
    if AGENT_EXIT_RECORDED_AT_STATE_KEY not in state:
        return None
    return state.get(AGENT_EXIT_CODE_STATE_KEY), state[AGENT_EXIT_RECORDED_AT_STATE_KEY]


@dataclass(frozen=True)
class DeathWithoutAHandoffDecision:
    """A restart decision with a reason for the console."""

    resume: bool
    reason: str


def resume_or_stop_after_a_death_without_a_handoff(exit_code) -> DeathWithoutAHandoffDecision:
    # POSIX does not identify the signal sender, and interactive stderr belongs to the terminal.
    # A clean exit is deliberate; an adopted process with no exit code gives no basis for resuming.
    if exit_code is None:
        return DeathWithoutAHandoffDecision(
            False,
            "the session's exit code is unknown — an adopted session, whose code "
            "this supervisor never owned; not resuming")
    if exit_code == 0:
        return DeathWithoutAHandoffDecision(
            False,
            "the session exited cleanly (exit code 0), which is a decision rather "
            "than a crash; not resuming")
    if exit_code in SIGTERM_SESSION_EXIT_CODES:
        return DeathWithoutAHandoffDecision(
            True, f"the session was killed by SIGTERM (exit code {exit_code})")
    if exit_code in SIGKILL_SESSION_EXIT_CODES:
        return DeathWithoutAHandoffDecision(
            True, f"the session was killed by SIGKILL — OOM or `kill -9` "
                  f"(exit code {exit_code})")
    return DeathWithoutAHandoffDecision(
        True, f"the session exited with an error status (exit code {exit_code})")


SUPERVISOR_STATE_FILE_SUFFIX = "-supervisor-state.json"
SUPERVISOR_LOCK_FILE_SUFFIX = "-supervisor.lock"
HANDOFF_FILE_SUFFIX = "-handoff.md"
SUPERVISOR_SCRIPT_FILE_NAME = "handoff-supervisor.py"


def agent_name_from_supervisor_file(path: Path) -> str:
    """Return the agent name, falling back to the stem for an unrecognized suffix."""
    for suffix in (SUPERVISOR_STATE_FILE_SUFFIX, SUPERVISOR_LOCK_FILE_SUFFIX):
        if path.name.endswith(suffix):
            return path.name[:-len(suffix)]
    return path.stem


def supervisor_state_path(handoff_directory: Path, agent: str) -> Path:
    return Path(handoff_directory) / f"{agent}{SUPERVISOR_STATE_FILE_SUFFIX}"


def supervisor_lock_path(handoff_directory: Path, agent: str) -> Path:
    return Path(handoff_directory) / f"{agent}{SUPERVISOR_LOCK_FILE_SUFFIX}"


def supervisor_state_paths(handoff_directory: Path) -> list:
    """Return every seat's supervisor state file, sorted."""
    directory = Path(handoff_directory)
    if not directory.is_dir():
        return []
    return sorted(directory.glob(f"*{SUPERVISOR_STATE_FILE_SUFFIX}"))


def handoff_file_path(handoff_directory: Path, agent: str) -> Path:
    return Path(handoff_directory) / f"{agent}{HANDOFF_FILE_SUFFIX}"


def handoff_file_paths(handoff_directory: Path) -> list:
    """Return every seat's session-handoff, sorted."""
    directory = Path(handoff_directory)
    if not directory.is_dir():
        return []
    return sorted(directory.glob(f"*{HANDOFF_FILE_SUFFIX}"))


def read_process_command_line(process_id: int):
    """Return (command_line, ps_answered), distinguishing absence from an unanswered query."""
    # macOS truncates ps output to terminal width even through a pipe unless -ww is given.
    try:
        finished = subprocess.run(["ps", "-ww", "-p", str(process_id), "-o", "args="],
                                  capture_output=True, text=True, check=False,
                                  timeout=PROCESS_COMMAND_LINE_READ_TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return None, False
    # ps uses nonzero for absence without distinguishing its own errors; only failure to run is treated as unanswered.
    command_line = finished.stdout.strip()
    return (command_line or None), True


def process_exists_by_signal(process_id: int) -> bool:
    try:
        os.kill(process_id, 0)
        return True
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        return True


def process_is_supervisor_for_agent(process_id, agent_name: str,
                                    read_command_line=read_process_command_line):
    """Return (is_supervisor, explanation), assuming ownership when a live PID cannot be identified."""
    # PIDs survive in locks and can be reused; heartbeat freshness does not prove ownership.
    # An unidentified live PID must block another supervisor, which could kill and relaunch the same session.
    # Tests must pass read_command_line explicitly; replacing the module attribute cannot change the bound default.
    try:
        process_id = int(process_id)
    except (TypeError, ValueError):
        return False, f"process id {process_id!r} is not a number"
    if process_id <= 0:
        return False, f"process id {process_id} cannot name a process"

    command_line, ps_answered = read_command_line(process_id)
    if not ps_answered:
        if not process_exists_by_signal(process_id):
            return False, (f"process {process_id} is not running — ps could not be run, "
                           "but os.kill reports no such process")
        print(f"handoff-supervisor: could not identify process {process_id} — ps could "
              f"not be run. A process with that id exists, so it is treated as a live "
              f"supervisor of {agent_name}; if none is in fact running, whatever asked "
              "is acting on that assumption until ps works or the lock is removed by hand.",
              file=sys.stderr)
        return True, (f"cannot tell whether process {process_id} is the supervisor of "
                      f"{agent_name} — ps could not be run and a process with that id "
                      "exists, so a supervisor is assumed present rather than risk "
                      "starting a second one")
    if command_line is None:
        return False, f"process {process_id} is not running"

    words = command_line.split()
    runs_this_script = any(word.rpartition("/")[2] == SUPERVISOR_SCRIPT_FILE_NAME
                           for word in words)
    named_agents = [word.partition("=")[2] for word in words if word.startswith("--agent=")]
    named_agents += [words[position + 1] for position, word in enumerate(words)
                     if word == "--agent" and position + 1 < len(words)]
    if runs_this_script and agent_name in named_agents:
        return True, f"process {process_id} is the supervisor of {agent_name}"
    return False, (f"process {process_id} is live but not a supervisor of {agent_name}: "
                   f"{command_line}")


def supervisor_liveness(state_path: Path):
    """Return (is_alive, explanation) for the supervisor owning this state file."""
    # Read the PID from the lock: heartbeat writes truncate the state file, so a concurrent read can see it empty.
    if not state_path.is_file():
        return False, f"no supervisor state at {state_path} — none has ever run for this agent"

    agent_name = agent_name_from_supervisor_file(state_path)
    lock_path = supervisor_lock_path(state_path.parent, agent_name)
    # Callers reuse this common opening when reporting why recovery may proceed.
    if not lock_path.is_file():
        return False, (f"no supervisor is watching — no supervisor lock at {lock_path}, "
                       "and a supervisor removes it when it stops cleanly")
    try:
        holder = int(lock_path.read_text(encoding="utf-8").strip())
    except (ValueError, OSError) as error:
        return False, (f"no supervisor is watching — the supervisor lock at {lock_path} "
                       f"is unreadable: {error}")

    running, identity = process_is_supervisor_for_agent(holder, agent_name)
    if running:
        return True, f"supervisor alive — {identity}{heartbeat_age_sentence(state_path)}"
    return False, f"no supervisor is watching — {identity}"


def heartbeat_age_sentence(state_path: Path) -> str:
    """Return a heartbeat-age suffix, or an empty string without a readable stamp."""
    stamped = read_supervisor_state(state_path).get("last_poll_at")
    if not stamped:
        return ", no heartbeat recorded yet"
    try:
        last_poll = datetime.fromisoformat(stamped)
    except ValueError:
        return f", unreadable heartbeat {stamped!r}"
    if last_poll.tzinfo is None:
        last_poll = last_poll.replace(tzinfo=timezone.utc)
    age_seconds = (datetime.now(timezone.utc) - last_poll).total_seconds()
    if age_seconds >= 60:
        return f", last heartbeat {age_seconds / 60:.0f}m ago"
    return f", last heartbeat {age_seconds:.0f}s ago"


def counter_from(fields: dict):
    raw = fields.get("restart-counter")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def written_at_wariness_sentence(written_at: str) -> str:
    """Return the handoff timestamp and wariness instruction for the successor."""
    # Carry the timestamp, not elapsed time computed here: the prompt may be consumed much later.
    try:
        written = datetime.fromisoformat(written_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return "written at an unrecorded time — treat every pointer in it as possibly stale."
    if written.tzinfo is None:
        written = written.replace(tzinfo=timezone.utc)
    stamp = written.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (f"written at {stamp}. Calculate from `date` how long ago that was, "
            "and be wary of obsolescence and drift in everything in this handoff "
            "in proportion to that gap.")


def pinned_task_list_id() -> str:
    """Return the launcher-pinned task list ID, or an empty string when unpinned."""
    return os.environ.get("CLAUDE_CODE_TASK_LIST_ID", "").strip()


def project_directory_for_working_directory(working_directory: Path) -> Path:
    """Return the harness project directory holding the worktree's sessions."""
    mangled = "".join(
        character if (character.isalnum() or character in "-_") else "-"
        for character in str(working_directory)
    )
    return PROJECTS_ROOT / mangled


def substantive_turn_count_of_session_transcript(session_id: str, working_directory: Path) -> int:
    """Return the session's substantive turn count, or zero if unreadable."""
    # Launch prompts and synthetic error records grow the transcript without work and must not reset the budget.
    transcript_path = (project_directory_for_working_directory(working_directory)
                       / f"{session_id}.jsonl")
    return worth_resuming.substantive_turn_count(transcript_path)


def queue_status_line(working_directory: Path) -> str:
    """Return each queue's depth and oldest item for the console."""
    reports = []
    for queue_directory in ("nc-queue", "docs/issues/queue", "docs/nedschorus-wiki/queue", "legacy-feature-queue"):
        directory = working_directory / queue_directory
        if not directory.is_dir():
            continue
        entries = sorted(
            item for item in directory.glob("*.md") if item.name.lower() != "readme.md"
        )
        if not entries:
            reports.append(f"{queue_directory}: empty")
            continue
        oldest = min(entries, key=lambda item: item.name)
        reports.append(f"{queue_directory}: {len(entries)}, oldest {oldest.name}")
    return "queues — " + ("; ".join(reports) if reports else "none found")


def extract_dialog(session_id: str, working_directory: Path, output_path: Path) -> bool:
    """Write the retiring session's dialog; return whether extraction succeeded."""
    result = subprocess.run(
        [
            sys.executable, str(EXTRACTOR_PATH),
            "--session-id", session_id,
            "--cd", str(working_directory),
            "--output", str(output_path),
        ],
        check=False,
    )
    return result.returncode == 0


def next_step_from(handoff_fields: dict) -> str:
    """Return the intact verbatim instruction, falling back to the collapsed line."""
    # Do not strip the returned block: trailing double spaces are Markdown hard breaks.
    verbatim = handoff_fields.get(NEXT_STEP_VERBATIM_FIELD, "")
    if verbatim.strip():
        return verbatim
    return handoff_fields.get("next-step", "").strip()


def spawned_subagent_roster_from(handoff_fields: dict) -> list:
    """Return the unfinished subagent roster in writer order."""
    numbered = []
    for key, value in handoff_fields.items():
        if not key.startswith(SPAWNED_SUBAGENT_FIELD_PREFIX):
            continue
        ordinal = key[len(SPAWNED_SUBAGENT_FIELD_PREFIX):]
        if ordinal.isdigit() and value:
            numbered.append((int(ordinal), value))
    return [value for _, value in sorted(numbered)]


def build_ignition_prompt(extract_path: Path, handoff_fields: dict,
                          predecessor_session_directory: Optional[Path] = None,
                          branch_sync_report: str = "",
                          overview_refresh_due: tuple = (),
                          memory_review_due: tuple = ()) -> str:
    next_step = next_step_from(handoff_fields)
    lines = [
        f"Read {extract_path} — the dialog from the session you are continuing, "
        + written_at_wariness_sentence(handoff_fields.get("written-at", "")),
        "This handoff should list what items or walks are open. Display them "
        "to the user, and continue them when you get a chance.",
        SUPERVISOR_POINTER_SENTENCE,
    ]
    if branch_sync_report:
        lines.append(branch_sync_report + BRANCH_STATE_INSTRUCTION)
    lines.extend(overview_refresh_due)
    lines.extend(memory_review_due)
    roster = spawned_subagent_roster_from(handoff_fields)
    if roster:
        transcript_directory = (predecessor_session_directory
                                if predecessor_session_directory
                                else "<predecessor-session-dir>")
        lines.append(ORPHANED_SUBAGENT_ROSTER_SENTENCE_TEMPLATE.format(
            subagent_count=len(roster),
            joined_roster="; ".join(roster),
            transcript_directory=transcript_directory,
        ))
    preamble = " ".join(lines)
    if handoff_fields.get(NEXT_STEP_BLOCK_UNTERMINATED_FIELD):
        preamble += UNTERMINATED_NEXT_STEP_BLOCK_NOTE
    if not next_step:
        return preamble + NO_NEXT_STEP_TAIL_SENTENCE
    # Keep line breaks: the next step is one argv element and may contain Markdown formatting.
    return f"{preamble}\n\nThen take the next step:\n{next_step}"


@dataclass
class DialogIgnitionPlan:
    """Prompt inputs held until the launch-time branch sync can supply its report."""
    extract_path: Path
    handoff_fields: dict
    predecessor_session_directory: Optional[Path] = None

    def compose(self, branch_sync_report: str,
                overview_refresh_due: tuple = (),
                memory_review_due: tuple = ()) -> str:
        return build_ignition_prompt(self.extract_path, self.handoff_fields,
                                     self.predecessor_session_directory,
                                     branch_sync_report=branch_sync_report,
                                     overview_refresh_due=overview_refresh_due,
                                     memory_review_due=memory_review_due)


@dataclass
class BootRecoveryIgnitionPlan:
    """A launch-time prompt for a handoff whose transcript cannot be extracted."""
    next_step: str

    def compose(self, branch_sync_report: str,
                overview_refresh_due: tuple = (),
                memory_review_due: tuple = ()) -> str:
        prompt = (
            f"{self.next_step}\n\n(Recovered at supervisor boot: the previous "
            "session's dialog extract is unavailable; this next-step and the "
            "repository are your whole context.)"
        )
        if branch_sync_report:
            prompt += " " + branch_sync_report + BRANCH_STATE_INSTRUCTION
        for line in overview_refresh_due:
            prompt += " " + line
        for line in memory_review_due:
            prompt += " " + line
        return prompt


def prune_old_generations(directory: Path, stem: str) -> None:
    # A tail and its -complete companion share one generation; counting files would evict the previous tail.
    numbered_file_name = re.compile(rf"{re.escape(stem)}-(\d+)(?:-complete)?\.md")
    files_by_generation = {}
    for item in directory.glob(f"{stem}-*.md"):
        match = numbered_file_name.fullmatch(item.name)
        if match:
            files_by_generation.setdefault(int(match.group(1)), []).append(item)
    for generation in sorted(files_by_generation)[:-GENERATIONS_KEPT]:
        for stale in files_by_generation[generation]:
            stale.unlink()


def run_git_here(arguments: list, working_directory: Path, timeout: int = 60):
    """Run git in the agent's directory, returning failures without raising."""
    try:
        return subprocess.run(
            ["git", *arguments], cwd=str(working_directory),
            capture_output=True, text=True, check=False, timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return subprocess.CompletedProcess(arguments, 1, "", f"{type(error).__name__}: {error}")


def sync_working_branch_with_main(working_directory: Path) -> str:
    """Fast-forward a strictly behind checkout, on a branch or detached, that has no
    uncommitted tracked change and no git operation in progress; return a report
    without raising. Untracked files do not block: git refuses on its own to
    overwrite one, and names it."""
    # Only call between sessions: syncing under a live agent invalidates its view of the tree.
    # Fast-forward only; resolving a conflict requires the agent's judgment.
    toplevel = run_git_here(["rev-parse", "--show-toplevel"], working_directory, timeout=15)
    if toplevel.returncode != 0:
        return "branch sync: not a git checkout, nothing to sync"

    fetched = run_git_here(["fetch", "--quiet", "origin"], working_directory)
    fetch_note = "" if fetched.returncode == 0 else " (fetch failed, comparing against what is on disk)"

    if run_git_here(["rev-parse", "--verify", "--quiet", "origin/main"],
                    working_directory, timeout=15).returncode != 0:
        return f"branch sync: no origin/main to sync with{fetch_note}"

    branch = run_git_here(["rev-parse", "--abbrev-ref", "HEAD"],
                          working_directory, timeout=15).stdout.strip() or "HEAD"

    reasons = []
    tracked_changes = checkout_freshness_catch_up.uncommitted_tracked_change_count(
        working_directory)
    if tracked_changes is None:
        reasons.append("git status unreadable")
    elif tracked_changes:
        reasons.append(f"{tracked_changes} uncommitted tracked change(s)")
    git_dir = checkout_freshness_catch_up.git_directory(working_directory)
    marker = (checkout_freshness_catch_up.in_progress_marker(git_dir)
              if git_dir is not None else None)
    if marker is not None:
        operation = checkout_freshness_catch_up.in_progress_operation(git_dir, marker)
        reasons.append(f"a {operation} in progress")
    if reasons:
        return f"branch sync: {branch} left as is — {'; '.join(reasons)}{fetch_note}"

    if run_git_here(["merge-base", "--is-ancestor", "origin/main", "HEAD"],
                    working_directory, timeout=15).returncode == 0:
        ahead = run_git_here(["rev-list", "--count", "origin/main..HEAD"],
                             working_directory, timeout=30).stdout.strip() or "?"
        if ahead == "0":
            return f"branch sync: {branch} is current with main{fetch_note}"
        return (f"branch sync: {branch} is {ahead} commit(s) ahead of main and has all of "
                f"it — nothing to pull{fetch_note}")

    if run_git_here(["merge-base", "--is-ancestor", "HEAD", "origin/main"],
                    working_directory, timeout=15).returncode == 0:
        merged = run_git_here(["merge", "--ff-only", "origin/main"], working_directory)
        if merged.returncode != 0:
            error = "; ".join(line.strip() for line in merged.stderr.splitlines()
                              if line.strip())
            return f"branch sync: {branch} left as is — {error or 'no detail'}{fetch_note}"
        tip = run_git_here(["rev-parse", "--short", "HEAD"],
                           working_directory, timeout=15).stdout.strip()
        return f"branch sync: {branch} fast-forwarded to main ({tip}){fetch_note}"

    ahead = run_git_here(["rev-list", "--count", "origin/main..HEAD"],
                         working_directory, timeout=30).stdout.strip() or "?"
    behind = run_git_here(["rev-list", "--count", "HEAD..origin/main"],
                          working_directory, timeout=30).stdout.strip() or "?"
    return f"branch sync: {branch} is {ahead} ahead of main and {behind} behind{fetch_note}"


def overview_check_git_output(arguments: list, working_directory: Path, failure_prefix: str,
                              timeout: int = 60, empty_is_failure: bool = True):
    """Return git's stripped stdout, or None after printing what failed; the overview check reports every git failure."""
    result = run_git_here(arguments, working_directory, timeout=timeout)
    output = result.stdout.strip()
    if result.returncode != 0 or (empty_is_failure and not output):
        print(f"handoff-supervisor: {failure_prefix}: git {' '.join(arguments)} failed: "
              f"{result.stderr.strip() or 'no detail'}")
        return None
    return output


def overview_refresh_due_lines(working_directory: Path,
                               now: Optional[datetime] = None) -> tuple:
    """Return unsuppressed overview-refresh reminders, and a line for a reminder-marks read failure; never block launch."""
    # Read origin/main so unmerged seat work cannot trigger a refresh; Markdown-only refreshes must not trigger another.
    # The checked-against commit may name a merge, so compare the commit range rather than last-commit identity.
    timeout = OVERVIEW_REFRESH_CHECK_GIT_TIMEOUT_SECONDS
    try:
        # Resolve and verify together: an empty ref in the range would silently select HEAD.
        # Resolve once, in full, so a fetch between two reads cannot make the range and the line name different commits.
        stopped = "overview check stopped"
        main_commit_full = overview_check_git_output(
            ["rev-parse", "--verify", "--quiet", "origin/main^{commit}"],
            working_directory, stopped, timeout=timeout)
        if main_commit_full is None:
            return ()
        main_commit = overview_check_git_output(
            ["rev-parse", "--short", main_commit_full], working_directory, stopped,
            timeout=timeout)
        if main_commit is None:
            return ()
        listed = overview_check_git_output(
            ["ls-tree", "-d", "--name-only", main_commit_full, "nc-systems/"],
            working_directory, stopped, timeout=timeout, empty_is_failure=False)
        if listed is None:
            return ()
    except Exception as error:
        print(f"handoff-supervisor: overview check stopped: "
              f"{type(error).__name__}: {error}")
        return ()
    due = []
    for system_directory in listed.splitlines():
        system = system_directory.rsplit("/", 1)[-1]
        try:
            overview_path = SYSTEM_OVERVIEW_PATH_TEMPLATE.format(system=system)
            shown = subprocess.run(
                ["git", "show", f"{main_commit_full}:{overview_path}"],
                cwd=str(working_directory), capture_output=True, check=False,
                timeout=timeout)
            if shown.returncode != 0:
                continue
            checked_commit = architecture_overview_path_template_and_checked_against_commit_reader.checked_against_commit(
                shown.stdout.decode("utf-8", errors="replace"))
            if checked_commit is None:
                continue
            commit_range = f"{checked_commit}..{main_commit}"
            pathspecs = [f"nc-systems/{system}/", f":(exclude)nc-systems/{system}/*.md"]
            moved = overview_check_git_output(
                ["log", "--no-merges", "--format=%h", commit_range, "--", *pathspecs],
                working_directory, f"overview check for {system} passed over",
                empty_is_failure=False)
            if moved is None:
                continue
            count = len(moved.split())
            if not count:
                continue
            commit_listing_command = (
                f"git log --no-merges {commit_range} -- "
                + " ".join(f"'{pathspec}'" if ":(" in pathspec else pathspec
                           for pathspec in pathspecs))
            overview_draft_path = SYSTEM_OVERVIEW_DRAFT_PATH_TEMPLATE.format(system=system)
            due.append((system, overview_path,
                f"overview refresh due: {system} — {count} commit(s) under "
                f"nc-systems/{system}/ since the commit its overview was checked "
                f"against, in "
                f"{commit_range}"
                + OVERVIEW_REFRESH_DUE_INSTRUCTION_TEMPLATE.format(
                    overview_path=overview_path,
                    overview_draft_path=overview_draft_path,
                    commit_listing_command=commit_listing_command,
                    checked_against_line=(
                        architecture_overview_path_template_and_checked_against_commit_reader.CHECKED_AGAINST_LINE_TEMPLATE.format(
                            commit=main_commit_full)),
                    reminder_mark_script=DAILY_OVERVIEW_REFRESH_REMINDER_MARK_PATH,
                    system=system)))
        except Exception as error:
            print(f"handoff-supervisor: overview check for {system} passed over: "
                  f"{type(error).__name__}: {error}")
    if not due:
        return ()
    try:
        answered = subprocess.run(
            ["gh", "pr", "list", "--repo", "nedschorus/nedschorus", "--state", "open",
             "--json", "url,title,files", "--limit", "200"],
            capture_output=True, text=True, check=False,
            timeout=OVERVIEW_REFRESH_CHECK_GH_TIMEOUT_SECONDS)
        if answered.returncode != 0:
            unanswered = (f"gh exited {answered.returncode}: "
                          + ((answered.stderr.strip().splitlines() or ["no detail"])[0]))
        else:
            unanswered = None
            changing_pull_request_by_path = {}
            for pull_request in json.loads(answered.stdout):
                title_and_url = (pull_request["title"], pull_request["url"])
                for changed_file in pull_request["files"]:
                    changing_pull_request_by_path.setdefault(
                        changed_file["path"], title_and_url)
    except Exception as error:
        unanswered = f"{type(error).__name__}: {error}"
    # An unavailable PR list must not suppress a needed reminder; a duplicate is preferable to silence.
    if unanswered is not None:
        print(f"handoff-supervisor: overview check could not ask GitHub which open "
              f"pull requests change an overview, so no line is withheld for a "
              f"pull request: {unanswered}")
        still_to_give = [(system, line) for system, _, line in due]
    else:
        still_to_give = []
        # Any open change to the overview could conflict with another refresh.
        for system, overview_path, line in due:
            if overview_path not in changing_pull_request_by_path:
                still_to_give.append((system, line))
                continue
            title, url = changing_pull_request_by_path[overview_path]
            print(f"handoff-supervisor: overview check for {system} withheld its line: "
                  f"the open pull request \"{title}\" ({url}) already changes "
                  f"{overview_path}")
    if not still_to_give:
        return ()
    # The seat marks only after showing the diff, so a seat that dies first cannot consume the daily reminder.
    reminder_mark = daily_overview_refresh_reminder_mark
    try:
        today = reminder_mark.pacific_date_of(now or datetime.now(timezone.utc))
        reminder_marks = reminder_mark.read_daily_overview_refresh_reminder_marks(
            today, OVERVIEW_REFRESH_REMINDER_MARKS_READ_TIMEOUT_SECONDS)
    except Exception as error:
        # Unknown reminder state must not violate the daily reminder floor.
        # The failure travels as a line so both the console and the successor see it.
        return tuple(line for _, line in still_to_give) + (
            OVERVIEW_REFRESH_REMINDER_MARKS_UNREAD_TEMPLATE.format(
                marks_location=reminder_mark.daily_overview_refresh_reminder_mark_citation(''),
                error=f"{type(error).__name__}: {error}")
            + (OVERVIEW_REFRESH_REMINDER_MARKS_NED_BOX_DID_NOT_ANSWER_SENTENCE
               if getattr(error, "ned_box_did_not_answer", False) else ""),)
    lines = []
    for system, line in still_to_give:
        file_name = reminder_mark.daily_overview_refresh_reminder_mark_file_name(today, system)
        if file_name not in reminder_marks:
            lines.append(line)
            continue
        citation = reminder_mark.daily_overview_refresh_reminder_mark_citation(file_name)
        written_at = reminder_marks[file_name].strip()
        if not reminder_mark.reminder_mark_text_is_a_time(written_at):
            print(f"handoff-supervisor: overview check for {system} gives its line: the "
                  f"day's reminder mark {citation} does not hold the time it was "
                  f"written, but {written_at!r}")
            lines.append(line)
            continue
        print(f"handoff-supervisor: overview check for {system} withheld its line: the "
              f"user was shown this overview's refresh today, at {written_at}, as "
              f"{citation} records")
    return tuple(lines)


def memory_review_due_lines(now: Optional[datetime] = None) -> tuple:
    """Return the daily memory-review reminder, or no lines when unavailable or not due."""
    # Only the Mac can reach both stores; SSH reads have a timeout that a hung Samba mount lacks.
    # A started mark survives a mid-review death to suppress duplicates until the next Pacific noon.
    mark_module = daily_memory_review_mark
    try:
        if mark_module.this_machine_is_ned_box():
            return ()
        pacific_now = mark_module.pacific_time_of(now or datetime.now(timezone.utc))
        if pacific_now.hour < MEMORY_REVIEW_DUE_FROM_PACIFIC_HOUR:
            return ()
        today = pacific_now.date().isoformat()
        timeout = MEMORY_REVIEW_CHECK_READ_TIMEOUT_SECONDS
        ned_box_store, review_marks = mark_module.read_memory_store_and_review_marks(
            mark_module.NED_BOX_SSH_TARGET, mark_module.NED_BOX_MEMORY_STORE_DIRECTORY,
            mark_module.DAILY_MEMORY_REVIEW_MARKS_DIRECTORY, timeout)
        mac_store, _ = mark_module.read_memory_store_and_review_marks(
            None, mark_module.MAC_MEMORY_STORE_DIRECTORY, "", timeout)
    except Exception as error:
        print(f"handoff-supervisor: memory review check gave no line: "
              f"{type(error).__name__}: {error}")
        return ()
    if any(mark_module.daily_memory_review_mark_file_name(today, mark) in review_marks
           for mark in mark_module.DAILY_MEMORY_REVIEW_MARK_KINDS):
        return ()
    mac_entries = mark_module.memory_store_entry_count(mac_store)
    ned_box_entries = mark_module.memory_store_entry_count(ned_box_store)
    last_done = mark_module.latest_done_mark(review_marks)
    if last_done is None:
        if not mac_entries and not ned_box_entries:
            return ()
        since = "and no review is recorded as done"
    else:
        done_date, done_digest = last_done
        if mark_module.memory_stores_digest(mac_store, ned_box_store) == done_digest:
            return ()
        since = f"changed since the review done on {done_date}"

    def entries(count):
        return f"{count} entry" if count == 1 else f"{count} entries"

    return (f"memory review due: the Mac's memory store holds {entries(mac_entries)} "
            f"and ned-box's holds {entries(ned_box_entries)}, {since}"
            + MEMORY_REVIEW_DUE_INSTRUCTION_TEMPLATE.format(
                mark_script=DAILY_MEMORY_REVIEW_MARK_PATH,
                mac_memory_store=mark_module.MAC_MEMORY_STORE_DIRECTORY + "/",
                ned_box_memory_store_mac_mount=(
                    mark_module.NED_BOX_MEMORY_STORE_MAC_MOUNT_DIRECTORY + "/"),
                ned_box_memory_store=mark_module.ned_box_memory_store_citation()),)


def uncommitted_work_snapshot_text(agent: str, working_directory: Path,
                                   handoff_directory: Path) -> str:
    """The first prompt's paragraph on the agent-seat's leftover work-snapshots, or ""."""
    text = uncommitted_work_snapshots.first_prompt_text(
        working_directory, agent, handoff_directory)
    if text:
        print(f"handoff-supervisor: {text.splitlines()[0]}")
    return text


def remove_finished_worktrees_at_handoff(
        working_directory: Path,
        timeout_seconds: int = FINISHED_WORKTREE_REMOVAL_TIMEOUT_SECONDS) -> str:
    """Run worktree cleanup and return a report without blocking the handoff on failure."""
    # Remove git environment overrides so deletions cannot target another repository.
    # Unbuffered output preserves partial counts; a separate process group lets timeout stop git and lsof too.
    environment = {name: value for name, value in os.environ.items()
                   if name not in ("GIT_DIR", "GIT_WORK_TREE")}
    try:
        cleaner = subprocess.Popen(
            [sys.executable, "-u", str(CLEAN_WORKTREES_PATH), "--remove",
             "--repo", str(working_directory)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env=environment, start_new_session=True,
        )
        stdout, stderr = cleaner.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        partial = stop_worktree_cleaner_process_group(cleaner)
        return (summarize_worktree_cleanup_output(partial.splitlines())
                + f"; clean-worktrees.py --remove did not finish in {timeout_seconds} s "
                  f"and was stopped, so the counts cover only what it did before the stop")
    except (OSError, subprocess.SubprocessError) as error:
        return (f"worktree cleanup: clean-worktrees.py could not be run: "
                f"{type(error).__name__}: {error}")
    report = summarize_worktree_cleanup_output(stdout.splitlines())
    if (cleaner.returncode != 0 and "FAILED" not in stdout
            and "work-snapshot failure(s)" not in report):
        detail = stderr.strip().splitlines()[-1:] or ["no detail"]
        report += f"; clean-worktrees.py exited {cleaner.returncode}: {detail[0]}"
    return report


def stop_worktree_cleaner_process_group(cleaner) -> str:
    """Stop the cleaner and its children; return the output collected before stopping."""
    # SIGTERM lets git remove its lock files; SIGKILL does not.
    partial = ""
    for signal_number in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(cleaner.pid, signal_number)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            return cleaner.communicate(timeout=WORKTREE_CLEANER_STOP_GRACE_SECONDS)[0] or ""
        except subprocess.TimeoutExpired as still_open:
            partial = still_open.stdout or ""
    if isinstance(partial, bytes):
        partial = partial.decode("utf-8", errors="replace")
    return partial


def summarize_worktree_cleanup_output(lines) -> str:
    """Return one report line from the cleaner's output."""
    removed = sum(1 for line in lines if ": removed" in line)
    deleted = sum(1 for line in lines
                  if (line.startswith("branch ") and ": deleted" in line)
                  or (": removed" in line and line.endswith(" deleted")))
    failed = [line for line in lines if "FAILED" in line]
    refused = [line for line in lines if "left in place" in line]
    unchecked = [line for line in lines
                 if ": kept — " in line
                 and ("(lsof)" in line or "lsof is not installed" in line)]
    discarded = [line for line in lines if ": discarded with it " in line]
    snapshots_deleted = [line for line in lines
                         if line.startswith("work-snapshot ") and ": deleted, first listed " in line]
    # A duplicate held nothing a newer leftover does not, so only its count is worth a line.
    duplicates_deleted = [line for line in lines
                          if line.startswith("work-snapshot ") and ": deleted, a duplicate " in line]
    snapshot_failures = [line for line in lines
                         if line.startswith("work-snapshots: could not be listed")
                         or (line.startswith("work-snapshot ")
                             and (": deletion failed: " in line
                                  or ": could not be checked, kept: " in line))]
    announced = {line.partition(": removing it will discard ")[0]:
                 line.partition(": removing it will discard ")[2]
                 for line in lines if ": removing it will discard " in line}
    # Each worktree lands in one bucket: confirmed, failed (with what it announced), or unconfirmed.
    settled = ({line.partition(": discarded with it ")[0] for line in discarded}
               | {line.partition(": removal FAILED")[0] for line in failed})
    unconfirmed = [f"{name}: removing it will discard {files}"
                   for name, files in announced.items() if name not in settled]
    failed = [line + (f" (it had announced: {announced[line.partition(': removal FAILED')[0]]}; "
                      f"those files may be partly gone)"
                      if line.partition(": removal FAILED")[0] in announced else "")
              for line in failed]
    report = (f"worktree cleanup: {removed} finished worktree(s) removed, "
              f"{deleted} branch ref(s) with nothing beyond main deleted")
    if discarded:
        report += (f"; {len(discarded)} of the removed held uncommitted, untracked or "
                   f"ignored files: " + "; ".join(discarded))
    if unconfirmed:
        report += (f"; {len(unconfirmed)} removal(s) started but not confirmed, so these "
                   f"files may be partly gone: " + "; ".join(unconfirmed))
    if failed:
        report += f"; {len(failed)} failed: " + "; ".join(failed)
    if refused:
        report += f"; {len(refused)} branch(es) left in place: " + "; ".join(refused)
    if unchecked:
        report += (f"; {len(unchecked)} worktree(s) kept because the vacancy check "
                   f"could not be run: " + unchecked[0].split(": kept — ", 1)[-1])
    if snapshots_deleted:
        report += (f"; {len(snapshots_deleted)} leftover work-snapshot(s) deleted: "
                   + "; ".join(snapshots_deleted))
    if duplicates_deleted:
        report += f"; {len(duplicates_deleted)} duplicate work-snapshot(s) deleted"
    if snapshot_failures:
        report += (f"; {len(snapshot_failures)} work-snapshot failure(s): "
                   + "; ".join(snapshot_failures))
    return report


APPENDED_SYSTEM_PROMPT_EDITOR_NOTES_SEPARATOR_LINE = "---"


def agent_part_of_appended_system_prompt(file_text: str):
    """Return (agent_text, separator_found), leaving separator-free text whole."""
    # The text above the separator is editor guidance and must not become agent instructions.
    lines = file_text.splitlines(keepends=True)
    for position, line in enumerate(lines):
        if line.strip() == APPENDED_SYSTEM_PROMPT_EDITOR_NOTES_SEPARATOR_LINE:
            agent_lines = lines[position + 1:]
            while agent_lines and not agent_lines[0].strip():
                agent_lines.pop(0)
            return "".join(agent_lines), True
    return file_text, False


def appended_system_prompt_file_for_launch(source_path: str, agent_part_path: Path) -> str:
    """Return the prepared prompt path, the source on write failure, or an empty string if unreadable."""
    # The CLI reads the file at startup and refuses a missing file; write before launch and retain it.
    if not source_path:
        return ""
    try:
        source_text = Path(source_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"handoff-supervisor: could not read the appended-system-prompt file "
              f"{source_path} ({error}) — launching this session without it",
              file=sys.stderr)
        return ""
    agent_text, separator_found = agent_part_of_appended_system_prompt(source_text)
    if not separator_found:
        print(f"handoff-supervisor: no --- line in the appended-system-prompt file "
              f"{source_path} — appending the whole file",
              file=sys.stderr)
        return source_path
    try:
        agent_part_path.write_text(agent_text, encoding="utf-8")
    except OSError as error:
        print(f"handoff-supervisor: could not write the agent part of {source_path} to "
              f"{agent_part_path} ({error}) — appending the whole file",
              file=sys.stderr)
        return source_path
    # The session may resolve relative paths from a different working directory.
    return os.path.abspath(agent_part_path)


AGENT_BINARY_UPDATE_TIMEOUT_SECONDS = 120


def update_agent_binary(agent_command: str, timeout_seconds: int) -> None:
    # Background auto-update is disabled; updating here covers every relaunch.
    # Running sessions pin retained version directories, so swapping the installed binary leaves them intact.
    if not timeout_seconds:
        return
    print(f"handoff-supervisor: checking for a {agent_command} update")
    agent_binary_update_under_lock.run_agent_binary_update_under_lock(
        [agent_command, "update"], timeout_seconds, "handoff-supervisor")


def launch_agent_session(agent_command: str, session_id: str, working_directory: Path,
                         prompt: str, resume: bool = False,
                         remote_control_name: str = "",
                         appended_system_prompt_file: str = "",
                         handoff_supervisor_agent_name: str = "",
                         update_timeout_seconds: int = 0):
    """Start an interactive session inheriting this console's terminal."""
    # --resume retains the transcript ID; --remote-control pins the address that otherwise drifts with conversation.
    # --remote-control names only the Remote Control entry: without --name, the name same-machine
    # peers address is derived from the working directory plus a code that changes every agent-session.
    # The prefix keeps the agent-seat's name on an entry that /remote-control re-creates with a default name.
    update_agent_binary(agent_command, update_timeout_seconds)
    flag = "--resume" if resume else "--session-id"
    command = [agent_command, flag, session_id]
    if remote_control_name:
        command += ["--remote-control", remote_control_name,
                    "--name", remote_control_name,
                    "--remote-control-session-name-prefix", remote_control_name]
    if appended_system_prompt_file:
        command += ["--append-system-prompt-file", appended_system_prompt_file]
    # The test stub reads the final argument as the prompt, so no flag may follow it.
    command.append(prompt)
    session_environment = dict(os.environ)
    session_environment[HANDOFF_SUPERVISOR_AGENT_NAME_ENVIRONMENT_VARIABLE] = handoff_supervisor_agent_name
    session_environment[HANDOFF_SUPERVISOR_WORKING_DIRECTORY_ENVIRONMENT_VARIABLE] = str(working_directory)
    session_environment[HANDOFF_SUPERVISOR_SESSION_ID_ENVIRONMENT_VARIABLE] = session_id
    return subprocess.Popen(command, cwd=str(working_directory), env=session_environment)


class AdoptedSession:
    """A session this supervisor did not launch, identified by process ID."""

    # An adopted process is not our child: poll() can report disappearance, not an exit status.
    returncode = None

    def __init__(self, session_id: str, process_id: int):
        self.session_id = session_id
        self.process_id = process_id

    def poll(self):
        """Return None while the process is alive, 0 once it is gone."""
        try:
            os.kill(self.process_id, 0)
        except ProcessLookupError:
            return 0
        except PermissionError:
            return None
        return None

    def terminate(self):
        try:
            os.kill(self.process_id, signal.SIGTERM)
        except ProcessLookupError:
            pass

    def kill(self):
        try:
            os.kill(self.process_id, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def wait(self, timeout=None):
        """Block until the process is gone, or raise on timeout."""
        deadline = time.monotonic() + (timeout if timeout is not None else 0)
        while self.poll() is None:
            if timeout is not None and time.monotonic() > deadline:
                raise subprocess.TimeoutExpired(f"pid {self.process_id}", timeout)
            time.sleep(0.2)
        return 0


def supervisor_lock_filesystem_is_local(directory: Path):
    """Return whether the filesystem is local, with its type for a refusal."""
    if sys.platform == "darwin":
        # Darwin's statvfs omits MNT_LOCAL; statfs64 exposes the mount flag.
        class DarwinSupervisorLockFilesystem(ctypes.Structure):
            _fields_ = [
                ("block_size", ctypes.c_uint32), ("io_size", ctypes.c_int32),
                ("counts", ctypes.c_uint64 * 5), ("fsid", ctypes.c_int32 * 2),
                ("owner", ctypes.c_uint32), ("type", ctypes.c_uint32),
                ("flags", ctypes.c_uint32), ("subtype", ctypes.c_uint32),
                ("type_name", ctypes.c_char * 16),
                ("mount_on", ctypes.c_char * 1024),
                ("mount_from", ctypes.c_char * 1024),
                ("reserved", ctypes.c_uint32 * 8),
            ]

        filesystem = DarwinSupervisorLockFilesystem()
        statfs = ctypes.CDLL(None, use_errno=True).statfs64
        statfs.argtypes = [ctypes.c_char_p, ctypes.POINTER(DarwinSupervisorLockFilesystem)]
        statfs.restype = ctypes.c_int
        if statfs(os.fsencode(directory), ctypes.byref(filesystem)) != 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error), str(directory))
        return bool(filesystem.flags & 0x1000), filesystem.type_name.decode()
    if sys.platform == "linux":
        finished = subprocess.run(
            ["/usr/bin/stat", "-f", "-c", "%T", str(directory)],
            capture_output=True, text=True, check=True)
        filesystem = finished.stdout.strip()
        # Unknown types are refused because they may implement remote locking.
        return filesystem in {"ext2/ext3", "xfs", "btrfs", "tmpfs", "ramfs",
                              "overlayfs", "zfs", "f2fs"}, filesystem
    raise RuntimeError(f"cannot establish local filesystem on {sys.platform}")


def refuse_old_code_supervisor(lock_file, agent: str):
    # Delete this check once no supervisor started before this change is running.
    try:
        holder = int(lock_file.read().strip())
    except ValueError:
        return
    if holder <= 0:
        return
    try:
        finished = subprocess.run(
            ["ps", "-ww", "-p", str(holder), "-o", "args="],
            capture_output=True, text=True, timeout=PROCESS_COMMAND_LINE_READ_TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError(f"changeover check for {agent} failed: ps could not be run: {error}") from error
    if finished.returncode == 1 and not finished.stdout.strip() and not finished.stderr.strip():
        return
    if finished.returncode != 0:
        raise RuntimeError(f"changeover check for {agent} failed: ps exited "
                           f"{finished.returncode}: {finished.stderr.strip()}")
    words = finished.stdout.split()
    named_agents = [word.partition("=")[2] for word in words if word.startswith("--agent=")]
    named_agents += [words[index + 1] for index, word in enumerate(words)
                     if word == "--agent" and index + 1 < len(words)]
    if (any(word.rpartition("/")[2] == SUPERVISOR_SCRIPT_FILE_NAME for word in words)
            and agent in named_agents):
        raise RuntimeError(f"old-code supervisor {holder} is running for {agent}")


def claim_supervisor_lock(lock_path: Path):
    """Return an open file holding the agent's lifetime exclusive lock."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    local, filesystem = supervisor_lock_filesystem_is_local(lock_path.parent)
    if not local:
        raise RuntimeError(f"lock directory {lock_path.parent} is on {filesystem}, "
                           "which is not a confirmed local filesystem")
    agent = agent_name_from_supervisor_file(lock_path)
    for _ in range(3):
        lock_file = lock_path.open("a+", encoding="utf-8")
        try:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                lock_file.seek(0)
                holder = lock_file.read().strip()
                raise RuntimeError(f"supervisor {holder or '(PID not yet written)'} "
                                   f"is already running for {agent}") from error
            try:
                same_file = os.path.samestat(os.fstat(lock_file.fileno()), lock_path.stat())
            except FileNotFoundError:
                same_file = False
            # An exiting holder can unlink after we open, before we acquire flock.
            if not same_file:
                lock_file.close()
                continue
            lock_file.seek(0)
            refuse_old_code_supervisor(lock_file, agent)
            lock_file.seek(0)
            lock_file.truncate()
            lock_file.write(f"{os.getpid()}\n")
            lock_file.flush()
            return lock_file
        except BaseException:
            lock_file.close()
            raise
    raise RuntimeError(f"lock path {lock_path} changed during all three claim attempts")


def release_supervisor_lock(lock_path: Path, lock_file):
    try:
        lock_path.unlink()
    finally:
        lock_file.close()


def wait_for_handoff(process, handoff_path: Path, consumed_counter, state_path: Path, state: dict):
    """Return a new handoff's fields, or None when the session exits without one."""
    # Check the file before exit: a headless session can write its handoff and exit in the same turn.
    last_stamp = 0.0
    while True:
        exited = process.poll() is not None

        if time.monotonic() - last_stamp >= HEARTBEAT_INTERVAL_SECONDS:
            stamp_heartbeat(state_path, state)
            last_stamp = time.monotonic()

        if handoff_path.is_file():
            fields = parse_handoff_file(handoff_path)
            counter = counter_from(fields)
            if counter is not None and (consumed_counter is None or counter > consumed_counter):
                return fields

        if exited:
            return None

        time.sleep(HANDOFF_POLL_SECONDS)


def stop_session(process) -> None:
    process.terminate()
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        print("handoff-supervisor: session ignored terminate; killing", file=sys.stderr)
        process.kill()
        process.wait()


@dataclass
class SupervisorSettings:
    """Resolved settings for one supervisor."""

    agent: str
    working_directory: Path
    handoff_directory: Path
    agent_command: str
    first_prompt: str
    # A recovery that chose not to resume says so; a repeated founding --first-prompt-file must not.
    first_prompt_wins_over_crashed_transcript: bool = False
    # The caller must check for an unconsumed handoff before resuming, because resume skips boot-ignition.
    resume_session_id: str = ""
    appended_system_prompt_file: str = ""
    agent_update_timeout_seconds: int = AGENT_BINARY_UPDATE_TIMEOUT_SECONDS
    # Keep a real annotation: importlib callers cannot resolve this as a forward reference.
    adopted_session: Optional[AdoptedSession] = None

    @property
    def handoff_path(self) -> Path:
        return handoff_file_path(self.handoff_directory, self.agent)

    @property
    def state_path(self) -> Path:
        return supervisor_state_path(self.handoff_directory, self.agent)

    @property
    def lock_path(self) -> Path:
        return supervisor_lock_path(self.handoff_directory, self.agent)

    @property
    def appended_system_prompt_agent_part_path(self) -> Path:
        return self.handoff_directory / f"{self.agent}-appended-system-prompt-agent-part.md"


def carry_over_to_successor(settings: SupervisorSettings, retiring_session_id: str,
                            handoff_fields: dict, generation: int):
    """Return (successor_session_id, ignition_plan), or (None, None) if extraction fails."""
    # Prefer written-by-session: another session may have taken over the worktree since the supervisor launched.
    handoff_written_by_session = handoff_fields.get(WRITTEN_BY_SESSION_FIELD, "")
    if (handoff_written_by_session
            and handoff_written_by_session != WRITTEN_BY_SESSION_UNKNOWN_VALUE
            and handoff_written_by_session != retiring_session_id):
        print(f"handoff-supervisor: the handoff names session "
              f"{handoff_written_by_session} as its writer, not the tracked "
              f"{retiring_session_id}; carrying over the writer's dialog")
        retiring_session_id = handoff_written_by_session

    extract_path = settings.handoff_directory / f"{settings.agent}-dialog-{generation:04d}.md"
    extracted = extract_dialog(retiring_session_id, settings.working_directory, extract_path)
    if not extracted:
        print(
            "handoff-supervisor: extraction failed; not relaunching "
            "(the transcript is intact — recover by hand)",
            file=sys.stderr,
        )
        return None, None

    shutil.copy2(
        settings.handoff_path,
        settings.handoff_directory / f"{settings.agent}-handoff-{generation:04d}.md",
    )
    prune_old_generations(settings.handoff_directory, f"{settings.agent}-dialog")
    prune_old_generations(settings.handoff_directory, f"{settings.agent}-handoff")

    print(f"handoff-supervisor: {queue_status_line(settings.working_directory)}")

    successor_session_id = str(uuid.uuid4())
    plan = DialogIgnitionPlan(
        extract_path, handoff_fields,
        project_directory_for_working_directory(settings.working_directory) / retiring_session_id,
    )
    return successor_session_id, plan


def supervise_sessions(settings: SupervisorSettings) -> int:
    state = read_supervisor_state(settings.state_path)
    generation = state.get("generation", 0)
    if settings.first_prompt:
        prompt = settings.first_prompt
    elif settings.resume_session_id:
        # A resumed session retains its context and must not be told to ask for work it already has.
        prompt = RESUME_PROMPT_WHEN_A_SESSION_ENDED_WITHOUT_A_HANDOFF
    else:
        prompt = f"You are {settings.agent}. No handoff exists yet; ask what to work on."

    adopted = settings.adopted_session
    # Compose at launch so the branch-state line reports the sync performed for that launch.
    ignition_plan = None
    # Reusing a state-file ID for a fresh launch can collide with an existing transcript or live session.
    next_launch_resumes_the_session = bool(settings.resume_session_id) and adopted is None
    # Charge at launch so startup resumes count, and a successor does not inherit a predecessor's spent budget.
    consecutive_resumes_without_new_work = 0
    substantive_turns_at_the_last_resume = None
    if adopted:
        session_id = adopted.session_id
    elif next_launch_resumes_the_session:
        session_id = settings.resume_session_id
    else:
        session_id = str(uuid.uuid4())

    print(f"handoff-supervisor: {settings.agent} in {settings.working_directory}")
    print(f"handoff-supervisor: watching {settings.handoff_path}")

    # Consume a waiting handoff before resume, or the wait loop would kill the resumed session for an old handoff.
    if next_launch_resumes_the_session and settings.handoff_path.is_file():
        stale_fields = parse_handoff_file(settings.handoff_path)
        stale_counter = counter_from(stale_fields)
        if stale_counter is not None and stale_counter > (state.get("consumed_counter") or 0):
            print(
                f"handoff-supervisor: a handoff (counter {stale_counter}) predates this "
                "resume; marking it consumed so it cannot kill the resumed session. "
                "If that handoff was the fresher truth, stop and relaunch WITHOUT "
                "--resume-session-id — boot-ignition will consume it."
            )
            state["consumed_counter"] = stale_counter

    # Process an existing handoff before launching, or the wait loop would kill the new session for an old handoff.
    if adopted is None and not next_launch_resumes_the_session and settings.handoff_path.is_file():
        boot_fields = parse_handoff_file(settings.handoff_path)
        boot_counter = counter_from(boot_fields)
        consumed = state.get("consumed_counter")
        if boot_counter is not None and (consumed is None or boot_counter > consumed):
            if boot_fields.get("dont-restart"):
                # Boot recovery must honor dont-restart too; a deliberate stand-down needs an exit record.
                if not sys.stdin.isatty():
                    print("handoff-supervisor: dont-restart, and no terminal to ask on; stopping")
                    state["consumed_counter"] = boot_counter
                    record_agent_exit_in_supervisor_state(settings.state_path, state, None)
                    return 0
                if input("handoff-supervisor: restart? y/n ").strip().lower() != "y":
                    print("handoff-supervisor: stopping at the agent's request")
                    state["consumed_counter"] = boot_counter
                    record_agent_exit_in_supervisor_state(settings.state_path, state, None)
                    return 0
            generation += 1
            retiring_session_id = state.get(LAUNCHED_SESSION_ID_STATE_KEY)
            successor_session_id, ignition_plan = (
                carry_over_to_successor(settings, retiring_session_id, boot_fields, generation)
                if retiring_session_id else (None, None)
            )
            if successor_session_id is None:
                # When the retiring transcript is unavailable, the next step still provides work to carry forward.
                successor_session_id = str(uuid.uuid4())
                ignition_plan = BootRecoveryIgnitionPlan(next_step_from(boot_fields))
                print("handoff-supervisor: igniting from an unconsumed handoff without a dialog extract")
            else:
                print("handoff-supervisor: igniting from an unconsumed handoff left by a previous cycle")
            state["consumed_counter"] = boot_counter
            session_id = successor_session_id

    # An exit record means a supervised stop; without one, resume the crashed context instead of starting empty.
    # A first prompt does not exempt a seat: relaunch commands keep their --first-prompt-file long after the founding boot.
    if (not settings.resume_session_id
            and not settings.first_prompt_wins_over_crashed_transcript
            and adopted is None and ignition_plan is None
            and agent_exit_record_from_supervisor_state(state) is None):
        by_hand_session_id, by_hand_detail = worth_resuming.newest_real_transcript(
            project_directory_for_working_directory(settings.working_directory))
        if by_hand_session_id is not None:
            print("handoff-supervisor: no waiting handoff and no recorded exit — "
                  f"resuming this seat's last transcript {by_hand_session_id} "
                  "rather than starting it empty")
            if settings.first_prompt:
                print("handoff-supervisor: ignoring the first prompt from --first-prompt or "
                      "--first-prompt-file, because this seat already has a transcript worth "
                      "resuming; a first prompt is used only for a seat with no transcript worth "
                      "resuming, unless --first-prompt-file-wins-over-crashed-transcript is also given")
            session_id = by_hand_session_id
            next_launch_resumes_the_session = True
            prompt = RESUME_PROMPT_WHEN_A_SESSION_ENDED_WITHOUT_A_HANDOFF
        else:
            print("handoff-supervisor: no waiting handoff and no recorded exit, and "
                  f"nothing worth resuming ({by_hand_detail}); starting fresh")

    while True:
        state.update({LAUNCHED_SESSION_ID_STATE_KEY: session_id,
                      "generation": generation})
        clear_agent_exit_record_from_supervisor_state(state)
        write_supervisor_state(settings.state_path, state)

        if adopted is not None:
            print(
                f"handoff-supervisor: adopted running session {session_id} "
                f"(process {adopted.process_id}, generation {generation})"
            )
            process, adopted = adopted, None
        else:
            # An adopted session is still working in this directory, so syncing would change files under it.
            branch_sync_report = sync_working_branch_with_main(settings.working_directory)
            print(f"handoff-supervisor: {branch_sync_report}")
            if ignition_plan is not None:
                # Sync after the retiring session releases the tree; then compose the prompt using the fetched main.
                overview_refresh_due = (
                    overview_refresh_due_lines(settings.working_directory)
                    if settings.agent == AGENT_SEAT_GIVEN_OVERVIEW_REFRESH_LINES else ())
                for line in overview_refresh_due:
                    print(f"handoff-supervisor: {line}")
                memory_review_due = memory_review_due_lines()
                for line in memory_review_due:
                    print(f"handoff-supervisor: {line}")
                prompt = ignition_plan.compose(branch_sync_report, overview_refresh_due,
                                               memory_review_due)
                ignition_plan = None
            # Read after sync, which may have updated the prompt file.
            appended_system_prompt_file = appended_system_prompt_file_for_launch(
                settings.appended_system_prompt_file,
                settings.appended_system_prompt_agent_part_path,
            )
            if next_launch_resumes_the_session:
                consecutive_resumes_without_new_work += 1
                substantive_turns_at_the_last_resume = (
                    substantive_turn_count_of_session_transcript(
                        session_id, settings.working_directory))
            else:
                consecutive_resumes_without_new_work = 0
                substantive_turns_at_the_last_resume = None
            verb = "resuming" if next_launch_resumes_the_session else "launching"
            print(f"handoff-supervisor: {verb} session {session_id} (generation {generation})")
            # Read at each launch: a resume after a crash is when a dead agent's work-snapshots appear.
            leftover_work_snapshots = uncommitted_work_snapshot_text(
                settings.agent, settings.working_directory, settings.handoff_directory)
            launch_prompt = (f"{prompt}\n\n{leftover_work_snapshots}"
                             if leftover_work_snapshots else prompt)
            process = launch_agent_session(
                settings.agent_command, session_id, settings.working_directory, launch_prompt,
                resume=next_launch_resumes_the_session, remote_control_name=settings.agent,
                appended_system_prompt_file=appended_system_prompt_file,
                handoff_supervisor_agent_name=settings.agent,
                update_timeout_seconds=settings.agent_update_timeout_seconds,
            )
            next_launch_resumes_the_session = False

        handoff_fields = wait_for_handoff(
            process, settings.handoff_path, state.get("consumed_counter"), settings.state_path, state
        )
        if handoff_fields is None:
            death = resume_or_stop_after_a_death_without_a_handoff(process.returncode)
            print(f"handoff-supervisor: {death.reason}")
            if death.resume:
                # Only substantive work restores the resume budget; launch bookkeeping must not sustain a loop.
                substantive_turns = substantive_turn_count_of_session_transcript(
                    session_id, settings.working_directory)
                if (substantive_turns_at_the_last_resume is None
                        or substantive_turns > substantive_turns_at_the_last_resume):
                    consecutive_resumes_without_new_work = 0
                if consecutive_resumes_without_new_work >= CONSECUTIVE_RESUMES_WITHOUT_NEW_WORK_BUDGET:
                    print(f"handoff-supervisor: {consecutive_resumes_without_new_work} consecutive "
                          "resume(s) added nothing to this session's transcript — it is looping, "
                          "and each launch costs money; not resuming again")
                # A resumed session inherits stdio and will read EOF without a terminal.
                elif not sys.stdin.isatty():
                    print("handoff-supervisor: this supervisor has no terminal to seat a resumed "
                          "session on — not resuming. A seated supervisor "
                          "(launch-claude-ubuntu / launch-claude-mac) or "
                          "scripts/recover-crashed-seats.py picks this seat up.")
                else:
                    print("handoff-supervisor: resuming it where it died "
                          f"(resume {consecutive_resumes_without_new_work + 1} of "
                          f"{CONSECUTIVE_RESUMES_WITHOUT_NEW_WORK_BUDGET} before the transcript "
                          "has to grow again)")
                    prompt = RESUME_PROMPT_WHEN_A_SESSION_ENDED_WITHOUT_A_HANDOFF
                    next_launch_resumes_the_session = True
                    continue
            record_agent_exit_in_supervisor_state(settings.state_path, state, process.returncode)
            print("handoff-supervisor: session ended without a handoff; supervisor stopping")
            return 0

        # Check before killing or consuming: without a terminal a successor reads EOF; leave the handoff recoverable.
        # dont-restart needs no terminal because no successor launches.
        if not sys.stdin.isatty() and not handoff_fields.get("dont-restart"):
            print(
                "handoff-supervisor: a handoff arrived, but this supervisor has no terminal to "
                "seat a successor on — not reincarnating. The session stays up and the handoff stays "
                "unconsumed; a seated supervisor (launch-claude-ubuntu / launch-claude-mac) or a "
                "by-hand relaunch picks it up. Stopping."
            )
            return 0

        stop_session(process)
        generation += 1

        if handoff_fields.get("dont-restart"):
            if not sys.stdin.isatty():
                # Without a terminal, asking would raise EOFError before consuming the handoff and trigger it again next time.
                print("handoff-supervisor: dont-restart, and no terminal to ask on; stopping")
                answer = "n"
            else:
                answer = input("handoff-supervisor: restart? y/n ").strip().lower()
            if answer != "y":
                print("handoff-supervisor: stopping at the agent's request")
                state["consumed_counter"] = counter_from(handoff_fields)
                record_agent_exit_in_supervisor_state(settings.state_path, state,
                                                      process.returncode)
                return 0

        successor_session_id, ignition_plan = carry_over_to_successor(
            settings, session_id, handoff_fields, generation
        )
        if successor_session_id is None:
            # Leave the handoff unconsumed so recovery still prefers boot-ignition to the exit record.
            record_agent_exit_in_supervisor_state(settings.state_path, state, process.returncode)
            return 0

        print(f"handoff-supervisor: "
              f"{remove_finished_worktrees_at_handoff(settings.working_directory)}")

        state["consumed_counter"] = counter_from(handoff_fields)
        session_id = successor_session_id


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run and reincarnate one agent session.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--agent", required=True,
                        help="agent name; names the handoff and state files, and the Remote "
                             "Control name the session answers to. That name is how agents on "
                             "OTHER machines address this seat, so it has to be unique across "
                             "the whole fleet, not just this machine")
    parser.add_argument("--cd", default=".", help="the agent's worktree")
    parser.add_argument("--handoff-dir", default="~/.claude/handoffs", help="handoff directory on this machine only, not committed")
    parser.add_argument("--agent-command", default="claude", help="the CLI to launch")
    parser.add_argument(
        "--agent-update-timeout-seconds", type=int,
        default=AGENT_BINARY_UPDATE_TIMEOUT_SECONDS,
        help="seconds allowed for the agent update run before each launch; "
             "0 skips the update")
    parser.add_argument(
        "--agent-append-system-prompt-file",
        default=str(DEFAULT_APPENDED_SYSTEM_PROMPT_PATH),
        help="file whose text below its first --- line is appended to every launched "
             "session's system prompt; a file with no such line is appended whole, with "
             "a warning (default: the committed "
             "docs/agents/seat-session-appended-system-prompt.md beside this script). "
             "Pass an empty string to launch without it.",
    )
    parser.add_argument("--first-prompt", default="", help="prompt for the first session (no handoff yet)")
    parser.add_argument(
        "--first-prompt-file", default="",
        help="file holding the first session's prompt; read here so no caller "
             "has to smuggle file content through nested shell quoting",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="report whether a supervisor is watching this agent, then exit (0 alive, 1 not)",
    )
    parser.add_argument(
        "--resume-session-id", default="",
        help="crash recovery (nedschorus#120): the first launch resumes this "
             "session's transcript (claude --resume) instead of starting fresh; "
             "later reincarnations mint fresh ids as always. A handoff already on disk "
             "is marked consumed rather than igniting or reincarnating — passing this "
             "flag chooses the transcript over any waiting handoff",
    )
    parser.add_argument(
        "--first-prompt-file-wins-over-crashed-transcript", action="store_true",
        help="start fresh on --first-prompt-file even when this seat has a crashed "
             "transcript worth resuming; for a recovery that chose not to resume, such as "
             "recover-crashed-seats.py --ignite-fallback. Without it, a crashed transcript "
             "wins over --first-prompt-file",
    )
    parser.add_argument(
        "--adopt-session-id", default="",
        help="watch an already-running session with this id instead of launching one",
    )
    parser.add_argument(
        "--adopt-process-id", type=int, default=0,
        help="process id of the already-running session to adopt; required with --adopt-session-id",
    )
    arguments = parser.parse_args(argv)

    if arguments.check:
        state_path = supervisor_state_path(
            Path(arguments.handoff_dir).expanduser(), arguments.agent)
        alive, explanation = supervisor_liveness(state_path)
        print(explanation)
        return 0 if alive else 1

    if not pinned_task_list_id():
        print(
            "handoff-supervisor: startup stopped because the agent-seat was not started "
            "by a launcher that pins its task list; CLAUDE_CODE_TASK_LIST_ID is unset or empty.\n"
            "For an agent-seat on the Mac, start it on the Mac with scripts/launch-claude-mac.\n"
            "For an agent-seat on ned-box, start it on the Mac with scripts/launch-claude-ubuntu, "
            "which reaches ned-box over ssh.",
            file=sys.stderr,
        )
        return 2

    if bool(arguments.adopt_session_id) != bool(arguments.adopt_process_id):
        parser.error("--adopt-session-id and --adopt-process-id must be given together")
    if arguments.resume_session_id and arguments.adopt_session_id:
        parser.error("--resume-session-id and --adopt-session-id are different recoveries: "
                     "resume continues a DEAD session's transcript, adopt watches a LIVE one")

    adopted = None
    if arguments.adopt_session_id:
        adopted = AdoptedSession(arguments.adopt_session_id, arguments.adopt_process_id)
        if adopted.poll() is not None:
            print(
                f"handoff-supervisor: process {arguments.adopt_process_id} is already gone; "
                "nothing to adopt",
                file=sys.stderr,
            )
            return 2

    if arguments.first_prompt_file_wins_over_crashed_transcript and not arguments.first_prompt_file:
        parser.error("--first-prompt-file-wins-over-crashed-transcript needs --first-prompt-file")
    if arguments.first_prompt_file:
        prompt_path = Path(arguments.first_prompt_file).expanduser()
        if not prompt_path.is_file():
            parser.error(f"--first-prompt-file does not exist: {prompt_path}")
        arguments.first_prompt = prompt_path.read_text(encoding="utf-8").strip()

    working_directory = Path(arguments.cd).expanduser().resolve()
    if not working_directory.is_dir():
        parser.error(f"--cd is not a directory: {working_directory}")
    if shutil.which(arguments.agent_command) is None:
        print(f"handoff-supervisor: no such command: {arguments.agent_command}", file=sys.stderr)
        return 3

    # A missing prompt file must not strand a seat running from an older or mid-rebase checkout.
    appended_system_prompt_file = arguments.agent_append_system_prompt_file
    if appended_system_prompt_file and not Path(appended_system_prompt_file).is_file():
        print(
            f"handoff-supervisor: no appended-system-prompt file at "
            f"{appended_system_prompt_file} — launching sessions without it",
            file=sys.stderr,
        )
        appended_system_prompt_file = ""

    handoff_directory = Path(arguments.handoff_dir).expanduser()
    handoff_directory.mkdir(parents=True, exist_ok=True)

    settings = SupervisorSettings(
        agent=arguments.agent,
        working_directory=working_directory,
        handoff_directory=handoff_directory,
        agent_command=arguments.agent_command,
        agent_update_timeout_seconds=arguments.agent_update_timeout_seconds,
        first_prompt=arguments.first_prompt,
        resume_session_id=arguments.resume_session_id,
        first_prompt_wins_over_crashed_transcript=(
            arguments.first_prompt_file_wins_over_crashed_transcript),
        appended_system_prompt_file=appended_system_prompt_file,
        adopted_session=adopted,
    )

    try:
        lock_file = claim_supervisor_lock(settings.lock_path)
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"handoff-supervisor: startup stopped: {error}", file=sys.stderr)
        return 4

    try:
        return supervise_sessions(settings)
    finally:
        release_supervisor_lock(settings.lock_path, lock_file)


if __name__ == "__main__":
    sys.exit(main())
