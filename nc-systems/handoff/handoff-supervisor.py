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
  4. Carry the tasks forward: nothing to do under a seat-pinned task list,
     where every generation shares one store; otherwise copy the retiring
     session's records into the successor's task directory.
  5. Print one queue-status line — to the console only. It does not ride
     the initial agent instructions (user-ruled 2026-08-29: "Also useless is the
     reminder there are files in the queues. Thats what queues are for.").
  6. Launch the successor with the initial agent instructions.
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

Never pass --allowedTools on the launch: it silently swallows the positional
prompt, so the successor would boot with no instructions at all.

Exit codes: 0 clean stop, 2 bad invocation, 3 the agent command is missing.
"""

import argparse
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

# Which of a seat's transcripts is worth resuming — the same judgement
# recover-crashed-seats.py makes, from the one module that defines it, so the
# two programs cannot call one seat's transcripts two different things (issue
# 242's change 5). The convention — importlib for a module whose filename has
# hyphens — is scripts/cold-read-cell-common.py's.
# This file sits at nc-systems/handoff/, so the repository root is two
# directories up; parents[2] names that depth once instead of chaining .parent
# three times. Every path below that leaves this system is derived from it,
# because a sibling lookup is what breaks when a system moves: before the move
# to nc-systems/handoff/ the three paths below were with_name() calls that
# happened to be right only while this file lived in scripts/.
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIRECTORY = REPOSITORY_ROOT / "scripts"

_worth_resuming_spec = importlib.util.spec_from_file_location(
    "seat_transcript_worth_resuming",
    SCRIPTS_DIRECTORY / "seat-transcript-worth-resuming.py")
worth_resuming = importlib.util.module_from_spec(_worth_resuming_spec)
_worth_resuming_spec.loader.exec_module(worth_resuming)

# The first turn a resumed session gets when no first prompt was given. One
# definition, because two paths reach it: --resume-session-id, which only
# recover-crashed-seats.py passes, and the by-hand resume below. Its opening is
# an EMPTY_SUCCESSOR_MARKERS entry in that tool, so a session resumed under it
# that then does nothing is still recognised as workless — reword this and that
# recognition breaks (pinned in recover-crashed-seats-test.py's F8 group).
RESUME_PROMPT_WHEN_A_SESSION_ENDED_WITHOUT_A_HANDOFF = (
    "This session was resumed by crash recovery (nedschorus#120): the "
    "previous session ended without writing a handoff. Re-verify in-flight "
    "state before trusting it, then continue the work underway."
)

TASKS_ROOT = Path.home() / ".claude" / "tasks"
PROJECTS_ROOT = Path.home() / ".claude" / "projects"
# The extractor stays in scripts/ until every live supervisor runs from this
# directory: a supervisor resolves this path at import, so a running one
# would lose it the moment the file moved. It joins this system in step 2.
EXTRACTOR_PATH = SCRIPTS_DIRECTORY / "handoff-extract-conversation.py"
HANDOFF_POLL_SECONDS = 2.0
GENERATIONS_KEPT = 2

# The file whose agent part is appended to every launched session's system
# prompt: the text below its first `---` line, above which are notes to whoever
# edits the file. The supervisor writes that part to a file of its own at each
# launch and passes that file through `claude --append-system-prompt-file`; see
# appended_system_prompt_file_for_launch. The default is a COMMITTED file, and the
# supervisor rather than the launchers owns the flag on purpose: a supervisor is
# started by launch-claude-mac, by launch-claude-ubuntu, and by
# resupervise-seat.py, so putting it in the launchers would leave a recovered
# seat silently running without it. One place, every path.
DEFAULT_APPENDED_SYSTEM_PROMPT_PATH = (
    REPOSITORY_ROOT / "docs" / "agents"
    / "seat-session-appended-system-prompt.md"
)

# Set in the environment of every agent session this supervisor launches, and
# read by handoff-write-and-check-supervisor.py as the seat's name and
# directory (user-ruled 2026-09-16). Without them the writer took both from its
# own working directory, which is the seat's only until the agent runs it after
# a `cd` or from a worktree -- and a handoff under the wrong name lands in a
# file this supervisor never polls, so the session runs on to context
# exhaustion instead of reincarnating.
#
# The session id rides with them because every process the session starts
# inherits them, a child `claude -p` included (scripts/ghi-info-ask.py), and a
# child that hands off under them reincarnates the PARENT seat with the
# child's next step (PR #414 review, 2026-09-16). The writer trusts the name
# and directory only where CLAUDE_CODE_SESSION_ID equals this id, and a child
# `claude` has its own.
HANDOFF_SUPERVISOR_AGENT_NAME_ENVIRONMENT_VARIABLE = "NEDSCHORUS_HANDOFF_SUPERVISOR_AGENT_NAME"
HANDOFF_SUPERVISOR_WORKING_DIRECTORY_ENVIRONMENT_VARIABLE = (
    "NEDSCHORUS_HANDOFF_SUPERVISOR_WORKING_DIRECTORY"
)
HANDOFF_SUPERVISOR_SESSION_ID_ENVIRONMENT_VARIABLE = "NEDSCHORUS_HANDOFF_SUPERVISOR_SESSION_ID"

# The supervisor stamps its state file while polling. The stamp once decided
# whether a supervisor was still watching: a stamp under sixty seconds old read
# as alive, until nedschorus#242 change 1 (2026-09-12) replaced that rule with
# a check of the supervisor's process (process_is_supervisor_for_agent). Two
# readers remain: restart-live-seats-at-login.py, which picks the seats that
# were running when the machine stopped, and heartbeat_age_sentence, which only
# reports the age beside a verdict the process check has already settled.
# Stamped on an interval rather than every poll to keep the write rate low.
HEARTBEAT_INTERVAL_SECONDS = 10.0

# How long `ps` gets to answer before read_process_command_line gives up and
# reports that it could not be asked. Read from the module INSIDE that function
# rather than bound as a default argument, so a case can lower it and exercise
# the timeout against a real `ps` that really hangs — see the NOTE in
# process_is_supervisor_for_agent for what default-argument binding costs a test.
PROCESS_COMMAND_LINE_READ_TIMEOUT_SECONDS = 15


NEXT_STEP_VERBATIM_FIELD = "next-step-verbatim"
NEXT_STEP_BLOCK_OPENING_MARKER = "<<END-OF-NEXT-STEP"
NEXT_STEP_BLOCK_TERMINATOR = "END-OF-NEXT-STEP"
NEXT_STEP_BLOCK_UNTERMINATED_FIELD = "next-step-verbatim-unterminated"
SPAWNED_SUBAGENT_FIELD_PREFIX = "spawned-subagent-"
WRITTEN_BY_SESSION_FIELD = "written-by-session"
# What the writer stamps when the retiring session has no
# CLAUDE_CODE_SESSION_ID to name (handoff-write-and-check-supervisor.py,
# write_handoff_file): a placeholder, never a session id.
WRITTEN_BY_SESSION_UNKNOWN_VALUE = "unknown"

# Appended to sync_working_branch_with_main's one-line result in the ignition
# prompt. The wording is the user's; only the sync line it follows is computed.
# The open-pull-requests sentence is the 2026-08-30 ruling on a rendered mock
# of the prompt. The branch-state sentence was replaced by the user on
# 2026-09-16 ("y", item 1 of nedschorus#418) to match nedschorus#324, the
# 2026-09-14 ruling that working branches never get merges from main — the
# rule scripts/checkout-freshness-catch-up.py enforces: a never-pushed branch
# is rebased onto origin/main, a pushed one is left as it is. The sentence it
# replaced (2026-08-31) said to catch up with origin/main and resolve
# conflicts, and on 2026-09-15, thirty seconds after reading it, a seat merged
# main into a branch whose pull request (#387) was under review.
BRANCH_STATE_INSTRUCTION = (
    " — If this branch has never been pushed, rebase it onto origin/main "
    "before your first substantive action and rerun the tests for what you "
    "touched. If it is pushed, leave it as it is, and start new work on a "
    "branch from origin/main. If `gh pr view` reports its pull request "
    "CONFLICTING, merge origin/main into it by hand, once, and announce the "
    "new head. If this seat has "
    "open pull requests, check their state with `gh`: merge-lane reviews and "
    "merges them; a changes-requested one gets a fix round from a fresh agent "
    "— never extend a head you've already announced."
)

# The pointer at the script that composed the prompt, carried by every set of
# initial agent instructions build_ignition_prompt writes. The wording is the
# user's, ruled 2026-08-30 on a rendered mock of the prompt, in his second
# round. It lived inline in build_ignition_prompt's `lines` list until it was
# hoisted here: an equality pin can only hold a constant, and text composed at
# a call site lands outside every pin the test file has.
SUPERVISOR_POINTER_SENTENCE = (
    "This session was launched by nc-systems/handoff/handoff-supervisor.py, which "
    "watches this seat and composed this prompt — read it if you need to "
    "investigate the handoff mechanism."
)

# The orphaned-subagent duty, narrowed 2026-08-29, softened to "may need" in
# the user's second round (ruled 2026-08-30 on the same rendered mock): the
# writer records only subagents still working at the reincarnation, so every
# entry here is one the reincarnation killed mid-job. Re-commission rather than
# resume, because a dead subagent cannot be resumed by id across a
# reincarnation: probed 2026-08-29, SendMessage to a predecessor's subagent id
# returns "No transcript found" (the resolver is session-scoped) even though
# the transcript survives on disk at
# <predecessor-session-dir>/subagents/agent-<id>.jsonl.
# `agent-<id>.jsonl` stays a literal pattern: each entry names its own id, so
# the successor substitutes per entry.
#
# A template rather than a plain string, because the sentence takes three
# insertions the caller computes — the count, the joined roster, and the
# directory the transcripts survive in. Hoisted here for the same reason as
# SUPERVISOR_POINTER_SENTENCE: only a constant can be pinned by equality.
ORPHANED_SUBAGENT_ROSTER_SENTENCE_TEMPLATE = (
    "The session you are replacing had {subagent_count} subagent(s) still working when it ended: "
    "{joined_roster}. You may need to re-commission similar agents. If you need more "
    "context, the dead agents' full transcripts are at "
    "{transcript_directory}/subagents/agent-<id>.jsonl."
)


# The two tail sentences of build_ignition_prompt, hoisted for the same reason
# as the two above: only a constant can be pinned by equality. Until 2026-09-21
# each was reached by a containment check alone -- `"unterminated" in prompt`
# and `"continue from where that dialog ends" in prompt` -- so a sentence
# appended to either was invisible. Same class as the two branch-state call
# sites closed in pull request [the ignition prompt's sentences are constants,
# and both branch-state call sites are pinned whole]
# (https://github.com/nedschorus/nedschorus/pull/590). Each carries its own
# leading space, because each is concatenated onto a preamble that does not
# end in one.
UNTERMINATED_NEXT_STEP_BLOCK_NOTE = (
    " NOTE: this handoff's verbatim next-step block was unterminated, so what "
    "follows is the collapsed one-line form and may have lost structure."
)
NO_NEXT_STEP_TAIL_SENTENCE = " Then continue from where that dialog ends."


def parse_handoff_file(handoff_path: Path) -> dict:
    """Read the agent-written handoff into a dict of its `key: value` lines.

    One field may span lines: `next-step-verbatim`, whose value is the opening
    marker followed by the successor's instruction verbatim, ended by a line
    that is exactly the terminator (R20; format in
    nc-systems/handoff/handoff-design.md). The writer appends that block
    last, after every computed field, so the lines inside it cannot shadow a
    real field — first occurrence still wins, and the real fields came first.

    An unterminated block is a damaged handoff. It is NOT returned as a value:
    the field is left absent so every caller's "prefer verbatim when present"
    is literally true, and a separate flag records that the block was seen
    unterminated, so the successor can be told rather than silently handed the
    collapsed form.
    """
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
                # EXACT line, not a stripped match. An indented lookalike —
                # a terminator inside a fenced code block, say — is content,
                # and the writer refuses on the same exact comparison, so the
                # two ends cannot disagree about where a block ends.
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

        if key not in fields:  # first occurrence wins; later prose cannot overwrite a field
            fields[key] = value
    return fields


# The session this supervisor LAUNCHED, which is not the same thing as the
# session running now. It is written only at a launch, so a session that takes
# over the worktree mid-life leaves it naming a session that has ended, until
# the next launch overwrites it.
#
# It was called "session_id" until 2026-09-21, and that name is what went
# wrong. This seat read it as "the session", twice told the user consequences
# that followed from that reading, and both were false: crash recovery does not
# consult it (seat-transcript-worth-resuming.py picks the newest transcript by
# mtime), and ghi-info-ask.py is not a second consumer of it -- that program
# keeps its OWN unrelated session under an identical key in its own
# .ghi-info-state.json, and the collision of the two bare names is what produced
# the false claim. Renamed on the user's ruling at item 12 of walk
# md-skills-seat-open-decisions-2026-09-20: the field is marked provisional by
# being named for what it holds, because a key name travels with the data into
# every file and reader while a comment stays at one site.
LAUNCHED_SESSION_ID_STATE_KEY = "launched_session_id"
# Read-only, for state files written before the rename. read_supervisor_state
# migrates it in, every write after that uses the new key alone, so a state file
# converts on the first read a renamed supervisor gives it. Removable once no
# live seat carries a state file older than 2026-09-21.
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
    """Record that a supervisor is alive and watching, right now."""
    state["last_poll_at"] = datetime.now(timezone.utc).isoformat()
    write_supervisor_state(state_path, state)


# The exit record (nedschorus#242 change 2, ruled 2026-09-02; the #120 overview,
# § Ruled 2026-09-02: record how the agent exited). A supervisor that outlived its
# agent saw the ending, and one killed with the machine or the tmux server never
# gets to write this — so recover-crashed-seats.py offers a seat carrying a
# record instead of resuming it, and resumes one without. Presence is the
# signal, not the code: the code is null where this supervisor had no child
# process to read it from.
AGENT_EXIT_CODE_STATE_KEY = "agent_exit_code"
AGENT_EXIT_RECORDED_AT_STATE_KEY = "agent_exit_recorded_at"


def record_agent_exit_in_supervisor_state(state_path: Path, state: dict, exit_code) -> None:
    """Write the exit record, as the last thing before a supervisor stops without
    launching a successor. exit_code is the session's own, a negative one for a
    signal, or None when it is unknown."""
    state[AGENT_EXIT_CODE_STATE_KEY] = exit_code
    state[AGENT_EXIT_RECORDED_AT_STATE_KEY] = datetime.now(timezone.utc).isoformat(
        timespec="seconds")
    write_supervisor_state(state_path, state)


def clear_agent_exit_record_from_supervisor_state(state: dict) -> None:
    """Drop the exit record before a session is launched or adopted, so the record
    always describes the most recent session: a seat that once exited cleanly
    and later crashed must read as crashed."""
    state.pop(AGENT_EXIT_CODE_STATE_KEY, None)
    state.pop(AGENT_EXIT_RECORDED_AT_STATE_KEY, None)


def agent_exit_record_from_supervisor_state(state: dict):
    """(exit_code, recorded_at) when the state carries an exit record, else None."""
    if AGENT_EXIT_RECORDED_AT_STATE_KEY not in state:
        return None
    return state.get(AGENT_EXIT_CODE_STATE_KEY), state[AGENT_EXIT_RECORDED_AT_STATE_KEY]


SUPERVISOR_STATE_FILE_SUFFIX = "-supervisor-state.json"
SUPERVISOR_LOCK_FILE_SUFFIX = "-supervisor.lock"
# The session-handoff a seat writes and its supervisor waits on, named after the
# agent like the two above. Composed only by handoff_file_path() and
# handoff_file_paths() below. agent_name_from_supervisor_file does NOT take this
# suffix apart: a handoff file is not a supervisor file, and the seat name it
# would return is already in hand wherever a handoff path is built.
HANDOFF_FILE_SUFFIX = "-handoff.md"
# This script's own name, as it appears in a running supervisor's command line.
SUPERVISOR_SCRIPT_FILE_NAME = "handoff-supervisor.py"


def agent_name_from_supervisor_file(path: Path) -> str:
    """The agent a supervisor state file or lock file belongs to.

    Both are named after the agent — <agent>-supervisor-state.json and
    <agent>-supervisor.lock — so the name is the one place the agent is
    recorded for a file handed to us on its own. A path that follows neither
    convention yields its whole stem, which matches no running supervisor and
    so reads as dead rather than wedging the seat.
    """
    for suffix in (SUPERVISOR_STATE_FILE_SUFFIX, SUPERVISOR_LOCK_FILE_SUFFIX):
        if path.name.endswith(suffix):
            return path.name[:-len(suffix)]
    return path.stem


def supervisor_state_path(handoff_directory: Path, agent: str) -> Path:
    """Where `agent`'s supervisor state file lives under `handoff_directory`.

    The inverse of agent_name_from_supervisor_file above, and with it the one
    place the state file's name is composed. Five programs need this path --
    this one, the recovery tool, resupervise-seat.py, the login restart and
    the handoff writer -- and each used to build it from its own f-string, so
    a rename had eleven sites to find and no test that found them (walk
    file-naming-and-location-standards-cold-read-findings, item 4, user-ruled
    2026-09-19: reduce each repeated name to one definition).
    """
    return Path(handoff_directory) / f"{agent}{SUPERVISOR_STATE_FILE_SUFFIX}"


def supervisor_lock_path(handoff_directory: Path, agent: str) -> Path:
    """Where `agent`'s supervisor lock file lives under `handoff_directory`.

    The lock beside the state file, composed here for the same reason.
    """
    return Path(handoff_directory) / f"{agent}{SUPERVISOR_LOCK_FILE_SUFFIX}"


def supervisor_state_paths(handoff_directory: Path) -> list:
    """Every seat's supervisor state file under `handoff_directory`, sorted.

    The login restart reads them all to decide which seats were live at the
    stop, and it used to glob f"*{SUPERVISOR_STATE_FILE_SUFFIX}" itself. A
    search pattern spells the name out as surely as a path does, so it
    belongs here with the rest. Pair it with agent_name_from_supervisor_file
    above to get each seat's name back.
    """
    directory = Path(handoff_directory)
    if not directory.is_dir():
        return []
    return sorted(directory.glob(f"*{SUPERVISOR_STATE_FILE_SUFFIX}"))


def handoff_file_path(handoff_directory: Path, agent: str) -> Path:
    """Where `agent`'s session-handoff lives under `handoff_directory`.

    The one place the handoff file's name is composed. Four programs need this
    path -- this supervisor, which waits on it; the handoff writer, which writes
    it; the recovery tool and resupervise-seat.py, which read it -- and until
    2026-09-20 each built it from its own f-string: eight sites across the four,
    one of them a local `suffix` variable in the writer. A rename that missed one
    left that program composing the old name, and the failure is silent in the
    worst direction: the supervisor writes <seat>-handoff.md, the recovery tool
    looks for something else, finds nothing, and reports a seat that handed off
    cleanly as one that died leaving no handoff.

    User-ruled 2026-09-20, item 2 of the walk
    md-skills-seat-open-decisions-2026-09-20. The eight sites were measured on
    main at 986bc31 on 2026-09-19 and re-measured unchanged on 2026-09-20,
    excluding test files -- whose literals are the assertion -- and three prose
    mentions in handoff-write-and-check-supervisor.py's docstrings. PR "The
    supervisor's state and lock file names are defined once"
    (nedschorus/nedschorus#545), which gave the state and lock files their
    constants and the guard beside them, left this name out because the ruling
    it carried out (item 4 of the walk
    file-naming-and-location-standards-cold-read-findings, 2026-09-19) named the
    supervisor state file, the cold-read-record names and the walk-file endings.
    The handoff name was measured while that work was carried out and recorded
    on docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md as
    its own unruled topic.

    Named handoff_file_path, not the walk's handoff_path, because handoff_path is
    already the SupervisorSettings property below, a parameter of
    parse_handoff_file and wait_for_handoff, and a local in three other scripts.
    A module-level function of that name is also a second FunctionDef named
    handoff_path in this file, and the guard collects its composing helpers by
    that name: it would find two, fail its own helper case, and exempt the
    property's body from the check that watches it.
    """
    return Path(handoff_directory) / f"{agent}{HANDOFF_FILE_SUFFIX}"


def handoff_file_paths(handoff_directory: Path) -> list:
    """Every seat's session-handoff under `handoff_directory`, sorted.

    The handoff writer reads them all to find the name a seat working in this
    very directory already hands off under, and it used to glob the suffix from a
    local copy of it. A search pattern spells the name out as surely as a path
    does, as supervisor_state_paths above says, so it belongs here with the rest.
    Pair it with HANDOFF_FILE_SUFFIX to get each seat's name back.
    """
    directory = Path(handoff_directory)
    if not directory.is_dir():
        return []
    return sorted(directory.glob(f"*{HANDOFF_FILE_SUFFIX}"))


def read_process_command_line(process_id: int):
    """(command_line, ps_answered) for a process id.

    THREE outcomes, not two, and keeping them apart is the point:

      (line, True)   ps ran and the process is there.
      (None, True)   ps ran and said there is no such process.
      (None, False)  ps could not be asked at all — it failed to start, or it
                     timed out. We do not know anything about the process.

    The `os.kill(pid, 0)` this replaced had only the first two: it answered, or
    it raised something that told us which answer it was. `ps` is a program,
    and a program can fail to run — a fork or exec failure under load, say,
    which this machine reaches when several test sweeps run at once. Folding
    "could not ask" into "not running" makes a confident false statement about
    a live process, and the callers act on it (found in review of a82b49e).

    `ps -ww -p` works on both machines (measured 2026-09-11 on the Mac and on
    ned-box). The -ww matters: without it macOS truncates the output to the
    terminal width even through a pipe, which would cut the --agent argument
    off exactly the long paths the fleet uses.
    """
    try:
        finished = subprocess.run(["ps", "-ww", "-p", str(process_id), "-o", "args="],
                                  capture_output=True, text=True, check=False,
                                  timeout=PROCESS_COMMAND_LINE_READ_TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return None, False
    # A non-zero exit is ps's answer for "no such process", not a failure to
    # answer, and ps has no distinct exit code for its own troubles — so a
    # non-zero exit with nothing on stdout is taken at its word. Only never
    # having run at all counts as not knowing.
    command_line = finished.stdout.strip()
    return (command_line or None), True


def process_exists_by_signal(process_id: int) -> bool:
    """Is there a process with this id? Answered by `os.kill(pid, 0)`.

    This is the one question that cannot go unanswered: the call either returns,
    or raises something that says which answer it is. ProcessLookupError means
    gone; success means it is there; PermissionError means it is there and
    belongs to someone else. It is used only where `ps` could not be asked —
    `os.kill` cannot say WHAT a process is, which is the whole reason `ps`
    replaced it for identity.
    """
    try:
        os.kill(process_id, 0)
        return True
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        return True


def process_is_supervisor_for_agent(process_id, agent_name: str,
                                    read_command_line=read_process_command_line):
    """(is_it, explanation): is this process a live supervisor for this agent?

    Ruled in nedschorus#242 change 1, and it replaces two weaker tests.

    Heartbeat age cannot answer the question. The rule this replaced read the
    stamp as fresh for sixty seconds after the last poll, so for a minute after
    a supervisor died its state file still said a supervisor was watching.
    Measured on ned-box (docs/issues/120-recover-crashed-seats-design.md § Two
    defects): after a seat's tmux server was killed, recover-crashed-seats.py
    refused the seat at 8, 24, 39 and 54 seconds and accepted it at 60. The
    login restart of nedschorus#116, which runs that recovery soon after boot,
    was predicted to be refused the same way, depending on how fast the
    machine boots.

    A bare process-id check cannot answer it either. The lock file recording
    the id outlives a reboot, and ids are reused across the very reboot this
    serves, so the id alone can name something else entirely. Hence the
    command line: the process must be running THIS script, with THIS agent.
    The agent argument is compared whole rather than by substring, because
    `--agent prof` would otherwise match the supervisor of `prof-2`.

    **When `ps` cannot be asked, existence is still answerable.** `os.kill`
    cannot say what a process is, but it cannot fail to say whether one is
    there — so a lock left by a crashed supervisor, holding an id that no longer
    exists, is still recognised as stale without `ps`. Only when a process with
    that id really does exist, and `ps` cannot say what it is, is the answer
    yes-by-assumption: failing closed leaves a seat down until someone looks,
    which is visible and recoverable, while failing open starts a second
    supervisor on an agent that already has one — and those two would each kill
    the session and each launch a successor, which is the thing the lock exists
    to prevent and is neither visible nor self-correcting. The detail says so
    rather than pretending to a certainty we do not have, and that case also
    says it on stderr, because a seat that will not start is the moment an
    operator most needs a true sentence about why.

    **That is a trade, and it was first written down as though it were free.**
    A caller acting on `True` here is acting on an assumption, and two of
    supervisor_liveness's callers act on it by telling someone to wait:
    handoff-write-and-check-supervisor stops an agent that has just written a
    handoff, and resupervise-seat refuses to repair the seat. If no supervisor
    is in fact there, that agent waits on nobody. The direction is still right —
    a stranded agent whose handoff is written on disk is recoverable by hand,
    two supervisors each killing a session and writing a successor are not — but
    the cost is real, so the sentences those two print say "if it is watching"
    rather than promising that it is (#328 follow-up round, nedschorus#242).

    NOTE for anyone reproducing this: `read_command_line` is a default argument,
    bound when this function was defined. Replacing the module's
    `read_process_command_line` afterwards does NOT reach it, and the real `ps`
    runs instead — so a harness that patches the module attribute sees the
    behaviour it was trying to replace and reports no defect. Substitute this
    whole function, or pass `read_command_line=` explicitly.
    """
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
        # The consequence clause is deliberately caller-agnostic. It used to say
        # "this seat will not start", which is claim_supervisor_lock's outcome
        # and only its outcome — the other callers refuse a repair, stop an
        # agent, or set an exit code. The remedy is the same for all of them.
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
    """Return (is_alive, explanation) for the supervisor owning this state file.

    The verdict is the supervisor's PROCESS, found through the lock file beside
    this one, confirmed by its command line (nedschorus#242 change 1). The
    heartbeat is reported because its age is worth knowing, but it no longer
    decides: see process_is_supervisor_for_agent for why it cannot.

    The process id is taken from the lock rather than the state file because
    the lock is written once when a supervisor claims an agent, while the state
    file is truncated and rewritten every HEARTBEAT_INTERVAL_SECONDS — a read
    landing mid-write sees it empty, which would read as a dead supervisor on a
    live one.
    """
    if not state_path.is_file():
        return False, f"no supervisor state at {state_path} — none has ever run for this agent"

    agent_name = agent_name_from_supervisor_file(state_path)
    lock_path = supervisor_lock_path(state_path.parent, agent_name)
    # Every dead verdict opens with the same words, so a caller can report the
    # verdict and the reason without knowing which reason it got; resupervise-seat
    # prints this sentence as its own reason for proceeding.
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
    """", last heartbeat 3s ago" when the state file carries a readable stamp,
    else "". Reported alongside a verdict the process has already settled: a
    supervisor busy enough to have missed its stamps is still a supervisor,
    but how far behind it is remains worth saying."""
    stamped = read_supervisor_state(state_path).get("last_poll_at")
    if not stamped:
        return ", no heartbeat recorded yet"
    try:
        last_poll = datetime.fromisoformat(stamped)
    except ValueError:
        return f", unreadable heartbeat {stamped!r}"
    if last_poll.tzinfo is None:
        last_poll = last_poll.replace(tzinfo=timezone.utc)  # the only writer stamps UTC
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
    """The dialog line's tail: the handoff's written-at stamp plus the
    wariness rule, for the initial agent instructions.

    The successor computes the elapsed time itself from `date` and applies
    age-proportional wariness (user-approved 2026-08-30). This replaces a
    composition-time elapsed phrase, which read "0 minutes ago" even on
    ignitions consumed much later. The stamp is the handoff's own written-at
    field rendered as UTC ISO-8601 with a Z suffix — never invented: an
    unreadable field falls back to the standing warning, not a made-up time.
    The sentence ends at the gap itself since the user's second round
    (ruled 2026-08-30 on a rendered mock): the "the older it is, the more
    you must re-verify" tail was cut as saying nothing the gap does not.
    """
    try:
        written = datetime.fromisoformat(written_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return "written at an unrecorded time — treat every pointer in it as possibly stale."
    if written.tzinfo is None:
        written = written.replace(tzinfo=timezone.utc)  # the field is documented as UTC
    stamp = written.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (f"written at {stamp}. Calculate from `date` how long ago that was, "
            "and be wary of obsolescence and drift in everything in this handoff "
            "in proportion to that gap.")


def pinned_task_list_id() -> str:
    """The seat-keyed task list id the launchers pin, or "" when unpinned.

    scripts/launch-claude-mac and scripts/launch-claude-ubuntu export
    CLAUDE_CODE_TASK_LIST_ID="nedschorus-<seat name>-tasks" into the seat's
    environment.
    This supervisor is started inside that environment and passes it on by
    inheritance to every session it launches, so when the variable is set,
    ALL of a seat's generations read and write one store,
    ~/.claude/tasks/nedschorus-<seat name>-tasks/, and the session id names no store at
    all. Read from the environment rather than recomposed from --agent: the
    launcher is the one place the id is composed, and a second composition
    here would be a second thing to keep in step.
    """
    return os.environ.get("CLAUDE_CODE_TASK_LIST_ID", "").strip()


def preseed_tasks(retiring_session_id: str, successor_session_id: str) -> int:
    """Copy task records into the successor's directory before it boots.

    Rides undocumented harness state: tasks are <N>.json files under
    ~/.claude/tasks/<session-id>/, and a session started with an explicit id
    reads whatever is already there. An upgrade breaking this is detected by
    the successor finding its predecessor's tasks missing, with the queues as
    the backstop (the ignition count-check that used to announce the count
    was cut with the task-count line, user-ruled 2026-08-30; per-upgrade
    canary re-runs were dropped as a remembered duty, user-ruled 2026-08-12);
    the canaries in handoff-supervisor-test.py (--canary) diagnose it when
    that fires.

    None of that applies under a pinned list, which is why this returns 0
    without copying there: the retiring and successor sessions already share
    one store, so there is no source and no destination to speak of, and the
    detection story above describes the un-pinned path only.
    """
    if pinned_task_list_id():
        return 0
    source = TASKS_ROOT / retiring_session_id
    if not source.is_dir():
        return 0
    destination = TASKS_ROOT / successor_session_id
    destination.mkdir(parents=True, exist_ok=True)
    copied = 0
    for task_file in sorted(source.glob("*.json")):
        shutil.copy2(task_file, destination / task_file.name)
        copied += 1
    return copied


def project_directory_for_working_directory(working_directory: Path) -> Path:
    """Return the ~/.claude/projects directory holding a worktree's sessions.

    The harness mangles the absolute path by replacing every character that is
    not alphanumeric, a dash, or an underscore with a dash.

    Lives here rather than in the writer (where it was born) because the
    supervisor is the base module: the writer imports the supervisor, and both
    need the mangling — the writer to find the retiring session's transcript,
    the supervisor to name the predecessor's subagent-transcript directory in
    the initial agent instructions. The writer aliases this function, so there is one
    copy of the rule.
    """
    mangled = "".join(
        character if (character.isalnum() or character in "-_") else "-"
        for character in str(working_directory)
    )
    return PROJECTS_ROOT / mangled


def queue_status_line(working_directory: Path) -> str:
    """Report each queue's depth and oldest item, so rot stays visible.

    Console-only since 2026-08-29: the user expired his 2026-08-12 #32 ruling
    that this line rides the initial agent instructions ("Also useless is the reminder
    there are files in the queues. Thats what queues are for."). The
    supervisor still prints it for a watched pane or the log."""
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
    """Write the retiring session's dialog to disk. Returns True on success.

    No boundary is passed: the extractor carries the tail that clears its word
    floor, so nothing here depends on a judgment the retiring agent made.
    """
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
    """The successor's instruction: the verbatim block when it is present and
    terminated, otherwise the collapsed single line.

    The collapsed line is always written, so the fallback is a correct
    instruction rather than a partial one.

    The block is returned EXACTLY as parsed. Stripping it here would be the
    quiet kind of wrong: a trailing double space is a markdown hard break, so
    a bare .rstrip() deletes formatting the agent chose, in the one function
    whose whole purpose is carrying the text unaltered. Emptiness is tested
    on a stripped copy; the value returned is never the stripped one.
    """
    verbatim = handoff_fields.get(NEXT_STEP_VERBATIM_FIELD, "")
    if verbatim.strip():
        return verbatim
    return handoff_fields.get("next-step", "").strip()


def spawned_subagent_roster_from(handoff_fields: dict) -> list:
    """The retiring session's subagent roster, in the order the writer wrote it.

    One numbered field per subagent (`spawned-subagent-1`, `-2`, ...), because
    a repeated key would lose every subagent but the first: the parser takes
    the first occurrence of a key. Fields the writer never wrote simply are
    not there — an older handoff yields an empty roster and the ignition
    prompt says nothing about subagents.

    Since 2026-08-29 the writer records only subagents still working when the
    handoff is written, so every entry here is one the reincarnation killed mid-job
    and the successor should re-commission. Subagents that completed, failed,
    or were stopped are not in the handoff at all (user-ruled 2026-08-29).
    """
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
                          branch_sync_report: str = "") -> str:
    """Compose the successor's first prompt.

    The prompt is tuned like a CLAUDE.md file (user-ruled 2026-08-29: "we
    should only put in the stuff that they need to know at their start. The
    rest they can look up if they need to"). It carries the dialog line —
    the extract path with the handoff's written-at stamp and the wariness
    rule (see written_at_wariness_sentence) — the open-walks duty, the
    pointer at this script, the branch-state line, the malformed-block note
    when the verbatim block was damaged, and the next step — plus, only when
    the handoff recorded subagents still working at the reincarnation, the
    roster sentence (ORPHANED_SUBAGENT_ROSTER_SENTENCE_TEMPLATE). Every
    boilerplate sentence is the user's, ruled
    2026-08-30 on a rendered mock of the prompt. Queue status does not
    ride it (the user expired that 2026-08-12 ruling on 2026-08-29); the
    supervisor prints it to its own console instead. The task-count check
    was cut too (user-ruled 2026-08-30: the task list is a standing tool;
    the count line is junk). The launch-clock sentence — the user's own
    nedschorus#175 wording — was cut by the user himself on the same mock
    (2026-08-30); the `date` discipline now rides only the dialog line's
    "Calculate from `date`".

    predecessor_session_directory is the retiring session's directory under
    ~/.claude/projects — the place its subagents' transcripts survive
    (`<dir>/subagents/agent-<id>.jsonl`). The supervisor composes it from the
    retiring session id and the working directory; a caller without one gets
    the literal `<predecessor-session-dir>` placeholder in the sentence.

    branch_sync_report is sync_working_branch_with_main's one-line result —
    fast-forwarded, ahead, behind counts, or the refusal's reason. The
    supervisor runs the sync immediately before launch_agent_session and
    passes the line in — see DialogIgnitionPlan, which holds everything else
    until that moment, so the prompt reports the sync that actually ran for
    this launch and not an earlier state. A caller that supplies nothing
    gets no branch-state segment at all rather than an invented one: every
    sentence here is ruled wording, and a placeholder would be wording the
    user never saw.
    """
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
    roster = spawned_subagent_roster_from(handoff_fields)
    if roster:
        # The sentence and the reasoning behind its wording live with
        # ORPHANED_SUBAGENT_ROSTER_SENTENCE_TEMPLATE; only the three
        # insertions are computed here.
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
    # The next step keeps its own line breaks: it is handed to the successor as
    # one argv element, so newlines survive delivery. Joining it into the
    # preamble would flatten exactly what the block form exists to preserve.
    return f"{preamble}\n\nThen take the next step:\n{next_step}"


@dataclass
class DialogIgnitionPlan:
    """The successor's first prompt, composed all but the branch-state line.

    Everything here is known when the retiring session's dialog is extracted.
    The branch-state line is not, because the branch sync runs between that
    work and the launch, and the prompt hands the successor the sync's own
    one-line result — a report an earlier composition could not contain.
    Holding the parts and composing at the launch site keeps the line true;
    compose() is called there with the report just produced. (The launch
    clock traveled this same way until the user cut its sentence on the
    rendered mock, 2026-08-30.)
    """
    extract_path: Path
    handoff_fields: dict
    # The retiring session's directory under ~/.claude/projects, where its
    # subagents' transcripts survive the reincarnation. Optional so a direct caller
    # without one still composes; the supervisor always passes it.
    predecessor_session_directory: Optional[Path] = None

    def compose(self, branch_sync_report: str) -> str:
        return build_ignition_prompt(self.extract_path, self.handoff_fields,
                                     self.predecessor_session_directory,
                                     branch_sync_report=branch_sync_report)


@dataclass
class BootRecoveryIgnitionPlan:
    """The prompt for a boot with a handoff but no dialog to hand over.

    The retiring session's transcript could not be extracted — a new machine,
    or the transcript is gone — so the next-step and the repository are the
    successor's whole context. That is the thinnest context this supervisor
    ever launches on, and the reason this plan exists rather than an f-string:
    it composes at the launch site, so the successor that can least afford a
    stale picture of its branch is not the one launched without the
    branch-state line the dialog path carries.
    """
    next_step: str

    def compose(self, branch_sync_report: str) -> str:
        prompt = (
            f"{self.next_step}\n\n(Recovered at supervisor boot: the previous "
            "session's dialog extract is unavailable; this next-step and the "
            "repository are your whole context.)"
        )
        if branch_sync_report:
            prompt += " " + branch_sync_report + BRANCH_STATE_INSTRUCTION
        return prompt


def prune_old_generations(directory: Path, stem: str) -> None:
    """Keep every file of the newest GENERATIONS_KEPT generations of one family.

    A generation is the number after the stem: `<stem>-0041.md`, and for a
    dialog also `<stem>-0041-complete.md`, the companion the extractor writes
    beside the tail when the dialog runs longer than the tail carries.

    This used to keep the newest GENERATIONS_KEPT FILES, so that companion took
    one of the two places and every long dialog deleted the previous
    generation's tail on arrival. Measured 2026-09-16 on the Mac: five seats
    held handoff archives for two generations and dialog tails for one. Counting
    by number keeps what the module docstring promises, the current and the
    previous. A file under the stem whose name carries
    no generation number is not counted and not deleted.
    """
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
    """Run git in the agent's directory; never raise, whatever goes wrong."""
    try:
        return subprocess.run(
            ["git", *arguments], cwd=str(working_directory),
            capture_output=True, text=True, check=False, timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return subprocess.CompletedProcess(arguments, 1, "", f"{type(error).__name__}: {error}")


def sync_working_branch_with_main(working_directory: Path) -> str:
    """Bring the agent's branch to main before a session starts, and return
    one line of report describing what was or was not done.

    Ruled 2026-08-13. An agent's home sits on its own branch only because git
    refuses one branch in two worktrees — nobody chose a long-lived personal
    branch, and left alone it drifts from main until someone merges by hand.
    Syncing here, between sessions, is the one safe moment: the previous
    session has exited and the next has not started, so no agent is holding a
    mental model of the tree.

    Deliberately conservative — it only ever fast-forwards:

    * uncommitted work, a failed fetch, no origin/main, or a branch carrying
      commits main does not have: report and change nothing;
    * strictly behind main with a clean tree: fast-forward.

    Never a merge, because a conflicted merge left in the tree before the agent
    wakes is worse than being behind: the branch counts go in the report and
    the agent, which can judge, decides. The agent never merges either:
    BRANCH_STATE_INSTRUCTION, appended to the report, tells it to rebase a
    branch that has never been pushed and rerun the tests for what it touched,
    and to leave a pushed branch as it is (nedschorus#324) — a rebase that can
    conflict needs an actor with judgment, which is the agent and never this
    script.

    Never call this while a session is running in that directory. Doing so
    would rewrite the files under a working agent, which believes it knows
    what its tree contains. There are exactly two ways supervise_sessions
    reaches a directory, and only the first is safe:

    * LAUNCH — the supervisor is about to start a session. Nothing is running
      there, so the sync happens here.
    * ADOPTION — a session is already running there, started by hand or by a
      previous supervisor. It is never synced; it stays as it is until it
      exits and the next launch syncs it.

    The cost of that rule is that a long-lived session drifts arbitrarily far
    from main with nothing announcing it, since sync is the only mechanism and
    it fires once, before the session begins. The design's answer is that
    sessions reincarnate often; a session that does not reincarnate should re-check
    main itself rather than trust what it read at start.
    """
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

    dirty = run_git_here(["status", "--porcelain"], working_directory, timeout=30).stdout.strip()
    if dirty:
        return (f"branch sync: {branch} left as is — {len(dirty.splitlines())} uncommitted "
                f"path(s) in the tree{fetch_note}")

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
            return (f"branch sync: {branch} could not fast-forward: "
                    f"{merged.stderr.strip() or 'no detail'}{fetch_note}")
        tip = run_git_here(["rev-parse", "--short", "HEAD"],
                           working_directory, timeout=15).stdout.strip()
        return f"branch sync: {branch} fast-forwarded to main ({tip}){fetch_note}"

    ahead = run_git_here(["rev-list", "--count", "origin/main..HEAD"],
                         working_directory, timeout=30).stdout.strip() or "?"
    behind = run_git_here(["rev-list", "--count", "HEAD..origin/main"],
                          working_directory, timeout=30).stdout.strip() or "?"
    return f"branch sync: {branch} is {ahead} ahead of main and {behind} behind{fetch_note}"


# The line that ends the editor notes in an appended-system-prompt file.
APPENDED_SYSTEM_PROMPT_EDITOR_NOTES_SEPARATOR_LINE = "---"


def agent_part_of_appended_system_prompt(file_text: str):
    """(agent_text, separator_found) for the text of an appended-system-prompt file.

    The file has two parts, split by its first line that is exactly `---` once
    surrounding whitespace is set aside. Above it are notes to whoever edits the
    file; below it is the text the agents receive. The agent text is everything
    after that line with its leading blank lines dropped, and is otherwise
    returned untouched. A file with no such line comes back whole, with
    separator_found False, so the caller can warn.

    Passing the whole file put the notes in every seat's system prompt, where an
    agent can read "Keep it SHORT" as an instruction to itself. That was
    observed 2026-09-16 in the cold-read-research seat's own system prompt, and
    the user ruled "fix 2": send only the part below the line.
    """
    lines = file_text.splitlines(keepends=True)
    for position, line in enumerate(lines):
        if line.strip() == APPENDED_SYSTEM_PROMPT_EDITOR_NOTES_SEPARATOR_LINE:
            agent_lines = lines[position + 1:]
            while agent_lines and not agent_lines[0].strip():
                agent_lines.pop(0)
            return "".join(agent_lines), True
    return file_text, False


def appended_system_prompt_file_for_launch(source_path: str, agent_part_path: Path) -> str:
    """The path to pass to `claude --append-system-prompt-file` for one launch.

    Writes the agent part of the file at source_path (see
    agent_part_of_appended_system_prompt) to agent_part_path and returns
    agent_part_path. That file belongs to this supervisor. It sits beside the
    seat's handoff and state files and is rewritten at the seat's every launch.
    The CLI reads it once, at startup, and refuses to start if it is missing, so
    it is written just before the launch and never deleted.

    The source is read here, at every launch, not once when the supervisor
    starts. When the CLI read the source itself, an edit reached each seat at
    its next launch, and reading it here keeps that true.

    A launch never fails because of this. The fallbacks, each with one warning
    line:
      * the source has no `---` line: return source_path, so the CLI gets the
        whole file, as it did before the split;
      * the agent part cannot be written: return source_path as well;
      * the source cannot be read (an older checkout, or one mid-rebase):
        return "", so the session launches without the flag, as main() does
        when the file is missing at supervisor start.
    An empty source_path means launch without the flag, and returns "".
    """
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
    # Absolute, because the session resolves it from its own working directory,
    # which need not be this supervisor's.
    return os.path.abspath(agent_part_path)


def launch_agent_session(agent_command: str, session_id: str, working_directory: Path,
                         prompt: str, resume: bool = False,
                         remote_control_name: str = "",
                         appended_system_prompt_file: str = "",
                         handoff_supervisor_agent_name: str = ""):
    """Start one interactive session, inheriting this console's terminal.

    resume=True launches `--resume <id>` instead of `--session-id <id>`: the
    crash-recovery path (nedschorus#120), where the session to run already
    has a transcript and must continue it. The CLI reuses the resumed id in
    place (--fork-session is the opt-out), so the state file's session_id
    stays correct for extraction at the next reincarnation — confirmed live
    2026-08-21, when the crash-recovered seats' transcripts grew under
    their original ids.

    remote_control_name launches with `--remote-control <name>`, which turns
    Remote Control on for the session and fixes the name it answers to. Both
    halves matter for cross-machine agent messaging: a session on another
    machine is reachable only while it is connected to Remote Control, and it
    is addressed by its Remote Control title, never by its local session name.
    Left to itself the CLI derives that title from the conversation and
    rewrites it as the conversation moves on, so a seat's address drifts under
    anyone trying to use it — observed 2026-08-27, when the Mac's mac-prof
    seat answered from three different titles inside twenty minutes. Passing
    the seat's own name pins it: this seat is `prof` on every machine, for the
    life of the session. An empty value launches without the flag, leaving the
    CLI's own defaults in charge.

    This widens what a seat's name means. It named local files; now it is also
    the address agents on other machines use, so two seats sharing a name are
    no longer merely confusing — they are ambiguous to a sender. The derived
    titles this replaces could not collide, because the CLI qualified them with
    the hostname. The fleet already keeps its names distinct by habit (the Mac
    runs `mac-prof` where this box runs `prof`); this makes the habit load-
    bearing, which is why --agent's own help text now says so.

    handoff_supervisor_agent_name and working_directory also reach the session
    as environment variables (HANDOFF_SUPERVISOR_AGENT_NAME_ENVIRONMENT_VARIABLE
    and HANDOFF_SUPERVISOR_WORKING_DIRECTORY_ENVIRONMENT_VARIABLE), so the
    handoff writer the agent runs names its handoff after the name this
    supervisor watches and records the directory the session was launched in,
    wherever the agent's shell happens to be standing when it runs it.
    session_id reaches it too (HANDOFF_SUPERVISOR_SESSION_ID_ENVIRONMENT_VARIABLE),
    on both the --session-id and --resume paths, because the writer honours the
    other two only in the session whose CLAUDE_CODE_SESSION_ID matches it: a
    child `claude` the session starts inherits all three but has its own id
    (PR #414 review, 2026-09-16)."""
    flag = "--resume" if resume else "--session-id"
    command = [agent_command, flag, session_id]
    if remote_control_name:
        command += ["--remote-control", remote_control_name]
    if appended_system_prompt_file:
        command += ["--append-system-prompt-file", appended_system_prompt_file]
    # The prompt stays LAST, after every flag — the stub agent in the test suite
    # reads it by taking the final argument, and a flag appended after it would
    # be read as the prompt.
    command.append(prompt)
    session_environment = dict(os.environ)
    session_environment[HANDOFF_SUPERVISOR_AGENT_NAME_ENVIRONMENT_VARIABLE] = handoff_supervisor_agent_name
    session_environment[HANDOFF_SUPERVISOR_WORKING_DIRECTORY_ENVIRONMENT_VARIABLE] = str(working_directory)
    session_environment[HANDOFF_SUPERVISOR_SESSION_ID_ENVIRONMENT_VARIABLE] = session_id
    return subprocess.Popen(command, cwd=str(working_directory), env=session_environment)


class AdoptedSession:
    """A session this supervisor did not launch, identified by process id.

    A supervisor normally owns the process it started and can terminate it
    through that handle. A session started by hand — the founding boot, or any
    agent a person launched in a console — has no such owner, so it can never
    reincarnate. Adoption closes that: handoff-supervisor.py run by hand with
    --adopt-session-id and --adopt-process-id watches the named process, and
    everything after the kill is identical to the ordinary cycle. No launcher
    or recovery script passes those flags (deferred 2026-08-19); the writer
    script started an adopting supervisor itself until 2026-08-14.
    """

    # Not this supervisor's child, so its exit status cannot be read: poll()'s 0
    # means only "gone". The exit record stores the code as unknown.
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
            return None  # alive, owned by someone else
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
        """Block until the process is gone, or raise once the timeout passes."""
        deadline = time.monotonic() + (timeout if timeout is not None else 0)
        while self.poll() is None:
            if timeout is not None and time.monotonic() > deadline:
                raise subprocess.TimeoutExpired(f"pid {self.process_id}", timeout)
            time.sleep(0.2)
        return 0


def claim_supervisor_lock(lock_path: Path) -> bool:
    """Take the one-supervisor-per-agent lock, or report it already held.

    Two supervisors on one agent would each kill the session and each launch a
    successor, so the second must not start. A lock left by a supervisor that
    died is reclaimed: the recorded process id is checked before the lock is
    believed.

    What is checked is that the id names a live supervisor OF THIS AGENT, not
    merely a live process (nedschorus#242 change 1). This file survives a
    reboot and ids are reused across it, so a stale lock whose id now belongs
    to something unrelated would otherwise refuse the very supervisor the login
    restart just asked for — and refuse it for as long as the lock sat there.
    The agent is taken from this file's own name.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            holder = int(lock_path.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            holder = None
        if holder is not None and holder != os.getpid():
            held, _ = process_is_supervisor_for_agent(
                holder, agent_name_from_supervisor_file(lock_path))
            if held:
                return False  # a live supervisor already holds this agent
        lock_path.unlink(missing_ok=True)  # the holder is gone; reclaim it
        return claim_supervisor_lock(lock_path)
    os.write(descriptor, f"{os.getpid()}\n".encode("utf-8"))
    os.close(descriptor)
    return True


def wait_for_handoff(process, handoff_path: Path, consumed_counter, state_path: Path, state: dict):
    """Block until the agent writes a new handoff, or the session exits.

    Returns the handoff fields when a counter above `consumed_counter`
    appears, or None if the session ended on its own without writing one.
    Stamps the heartbeat while it waits. The stamp no longer decides liveness
    (nedschorus#242 change 1); see HEARTBEAT_INTERVAL_SECONDS for its readers.

    The exit check must not preempt the file check: a headless session exits
    when its turn ends, so its handoff arrives AS a process exit — the file
    was written during the turn, before the exit was observable. Exit with a
    new counter on disk is a handoff; exit without one is abandonment.
    """
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
    """Everything one supervisor needs, resolved from the command line."""

    agent: str
    working_directory: Path
    handoff_directory: Path
    agent_command: str
    first_prompt: str
    # Crash recovery (nedschorus#120): a session id whose transcript the FIRST
    # launch resumes (`claude --resume`) instead of starting fresh. Later
    # reincarnations mint fresh ids as always. The caller is responsible for having
    # checked that no unconsumed handoff waits — boot-ignition is skipped.
    resume_session_id: str = ""
    # The file whose part below its first `---` line is appended to each launched
    # session's system prompt; "" launches without it.
    appended_system_prompt_file: str = ""
    # A real annotation, not a string: this module is loaded by importlib in the
    # threshold hook and the tests, where a forward reference cannot resolve.
    adopted_session: Optional[AdoptedSession] = None

    @property
    def handoff_path(self) -> Path:
        # The module function, not this property: a method body never resolves a
        # bare name in its own class namespace.
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
    """Extract, archive, prune, and build the successor's launch.

    Returns (successor_session_id, DialogIgnitionPlan), or (None, None) when
    extraction failed and relaunching would lose the dialog. The plan is not
    yet a prompt: the caller composes it at the launch, with the branch sync
    run there, so the branch-state line the successor reads names its own
    launch.

    The retiring session is the one that WROTE the handoff, not the one this
    supervisor launched, whenever the handoff says which it was. Both callers
    pass the id from the supervisor's state file, which records the session
    the supervisor started; the writer stamps written-by-session from
    CLAUDE_CODE_SESSION_ID inside the session actually retiring
    (handoff-write-and-check-supervisor.py, write_handoff_file). The two
    diverge when a session the supervisor did not launch takes over the
    worktree mid-life: the adoption path (AdoptedSession,
    --adopt-session-id) runs at supervisor startup only, so nothing updates
    the state file afterwards.

    That happened at the MD-skills seat on 2026-09-20/21. The state file held
    session ac2b8ebe-b95f-4599-a30e-aed1d554cef3, which ENDED at 22:00Z; a
    session the supervisor had not launched started in the same worktree two
    minutes later and ran as the seat from 22:02Z to 00:56Z, writing
    generation 27's handoff with written-by-session:
    145a31fd-d1eb-4ea6-9463-70b5c9f9c9d9. The extract handed to the successor,
    MD-skills-dialog-0027.md, therefore carried ac2b8ebe's final turns and
    none of the work 145a31fd had done, and nothing in the handoff or the
    console said so.

    The fallback is the tracked id, which is all there ever was: handoffs
    older than the field do not carry it, and a session with no
    CLAUDE_CODE_SESSION_ID writes the literal WRITTEN_BY_SESSION_UNKNOWN_VALUE
    rather than an id. Preferring the handoff's id once, here, also corrects
    preseed_tasks and the predecessor session directory below, which read the
    same id. No tasks were lost on 2026-09-20: the launchers pin a per-seat
    store (~/.claude/tasks/nedschorus-<seat>-tasks/), so preseed_tasks copied
    nothing and had nothing to get wrong. The un-pinned path is keyed by
    session id and would have pre-seeded the wrong session's tasks.
    """
    handoff_written_by_session = handoff_fields.get(WRITTEN_BY_SESSION_FIELD, "")
    if (handoff_written_by_session
            and handoff_written_by_session != WRITTEN_BY_SESSION_UNKNOWN_VALUE
            and handoff_written_by_session != retiring_session_id):
        print(f"handoff-supervisor: the handoff names session "
              f"{handoff_written_by_session} as its writer, not the tracked "
              f"{retiring_session_id}; carrying over the writer's dialog and tasks")
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

    # Console only: the queue-status line does not ride the initial agent instructions
    # (user-ruled 2026-08-29, expiring the 2026-08-12 #32 ruling).
    print(f"handoff-supervisor: {queue_status_line(settings.working_directory)}")

    successor_session_id = str(uuid.uuid4())
    # Two stories, and the console must not tell the wrong one: under a
    # pinned list nothing is carried because nothing needs to be, and
    # printing "carried 0 task record(s)" there reads as a failure to carry.
    pinned_list = pinned_task_list_id()
    if pinned_list:
        print(f"handoff-supervisor: tasks live in the seat-pinned list {pinned_list}; "
              f"the successor opens that same list, so nothing is carried")
    else:
        copied = preseed_tasks(retiring_session_id, successor_session_id)
        print(f"handoff-supervisor: carried {copied} task record(s) to the successor")

    plan = DialogIgnitionPlan(
        extract_path, handoff_fields,
        project_directory_for_working_directory(settings.working_directory) / retiring_session_id,
    )
    return successor_session_id, plan


def supervise_sessions(settings: SupervisorSettings) -> int:
    """Launch, watch, and reincarnate sessions until one ends without a handoff.

    Every stop that follows a session's end without launching a successor writes
    the exit record first (record_agent_exit_in_supervisor_state); the stop that
    leaves a live session up for a seated supervisor does not."""
    state = read_supervisor_state(settings.state_path)
    generation = state.get("generation", 0)
    if settings.first_prompt:
        prompt = settings.first_prompt
    elif settings.resume_session_id:
        # A resumed session holds its full pre-crash context; the no-handoff
        # default would tell it to ask for work it already has (PR #131
        # review round 3, P3-4 — the recovery script writes a richer prompt
        # file, and this default makes the by-hand flag equally truthful).
        prompt = RESUME_PROMPT_WHEN_A_SESSION_ENDED_WITHOUT_A_HANDOFF
    else:
        prompt = f"You are {settings.agent}. No handoff exists yet; ask what to work on."

    adopted = settings.adopted_session
    # Set when the next launch is an ignition: the prompt is composed from it
    # at the launch site, so the branch-state line it carries reports the
    # sync that runs there.
    ignition_plan = None
    # A fresh start always mints a new session id. Reusing the one in the state
    # file would launch `claude --session-id` against a transcript that already
    # exists — and if the supervisor died while its agent kept running, would put
    # two processes on one session id. Adoption is how a running session is
    # picked back up; resume (nedschorus#120) is how a CRASHED session's
    # transcript is continued, and applies to the first launch only.
    resume_first_launch = bool(settings.resume_session_id) and adopted is None
    if adopted:
        session_id = adopted.session_id
    elif resume_first_launch:
        session_id = settings.resume_session_id
    else:
        session_id = str(uuid.uuid4())

    print(f"handoff-supervisor: {settings.agent} in {settings.working_directory}")
    print(f"handoff-supervisor: watching {settings.handoff_path}")

    # The resume path (crash recovery, nedschorus#120) must not meet a stale
    # handoff either: the recovery script defers to boot-ignition when one
    # waits, but this flag can be run by hand, and the wait loop would then
    # kill the just-resumed session for a file predating it (PR #131 review,
    # finding 4). Mark any waiting handoff consumed BEFORE the resume launch —
    # the operator chose the transcript over the handoff by passing the flag.
    if resume_first_launch and settings.handoff_path.is_file():
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

    # A fresh boot may find an unconsumed handoff — a crash or reboot ended the
    # previous cycle after the write but before a supervisor acted on it. Ignite
    # from it directly. Launching first and letting the wait loop find the file
    # would kill the just-born session for a handoff that predates it.
    if adopted is None and not resume_first_launch and settings.handoff_path.is_file():
        boot_fields = parse_handoff_file(settings.handoff_path)
        boot_counter = counter_from(boot_fields)
        consumed = state.get("consumed_counter")
        if boot_counter is not None and (consumed is None or boot_counter > consumed):
            if boot_fields.get("dont-restart"):
                # The handoff asks for a consultation before any relaunch;
                # boot-ignition must not steamroll it. Same terminal rule as
                # the in-cycle dont-restart branch below. Stopping here is a
                # seat stood down on purpose, so it is recorded as an exit —
                # its code unknown, since the session ended before this
                # supervisor started.
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
                # No retiring transcript to extract (new machine, or it is
                # gone). The next-step still carries the work: ignite with it
                # alone rather than discarding the handoff.
                successor_session_id = str(uuid.uuid4())
                ignition_plan = BootRecoveryIgnitionPlan(next_step_from(boot_fields))
                print("handoff-supervisor: igniting from an unconsumed handoff without a dialog extract")
            else:
                print("handoff-supervisor: igniting from an unconsumed handoff left by a previous cycle")
            state["consumed_counter"] = boot_counter
            session_id = successor_session_id

    # Issue 242's change 5, ruled 2026-09-02: a by-hand launch resumes a
    # crashed seat. Reaching here having taken none of the branches above means
    # no first prompt, no --resume-session-id, no adopted session and no
    # unconsumed handoff — which is what `launch-claude-mac <seat>` or
    # `launch-claude-ubuntu <seat>` looks like on a seat that is simply down.
    # Until now that minted an empty session whose first turn said "No handoff
    # exists yet; ask what to work on", discarding the crashed context;
    # measured on both machines 2026-09-02, and the shape of the 2026-08-21
    # tmux death, where three supervisors minted near-empty successors beside
    # three intact 1-2MB transcripts.
    #
    # A recorded exit means the seat was stopped under supervision rather than
    # crashed, and still gets the fresh session. Any record counts, whatever
    # its code and whether or not the code is known, which is the rule
    # recover-crashed-seats.py applies to the same state file — so a seat this
    # supervisor resumes by hand is a seat that tool would also call a crash.
    if (not settings.first_prompt and not settings.resume_session_id
            and adopted is None and ignition_plan is None
            and agent_exit_record_from_supervisor_state(state) is None):
        by_hand_session_id, by_hand_detail = worth_resuming.newest_real_transcript(
            project_directory_for_working_directory(settings.working_directory))
        if by_hand_session_id is not None:
            # Reported in the terminal, as the design asks: this is a by-hand
            # launch, so someone is reading it.
            print("handoff-supervisor: no waiting handoff and no recorded exit — "
                  f"resuming this seat's last transcript {by_hand_session_id} "
                  "rather than starting it empty")
            session_id = by_hand_session_id
            resume_first_launch = True
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
            process, adopted = adopted, None  # adoption applies to this pass only
        else:
            # Only on the launch path: an adopted session is alive in this
            # directory, and changing files under a working agent is the one
            # thing this must never do.
            branch_sync_report = sync_working_branch_with_main(settings.working_directory)
            print(f"handoff-supervisor: {branch_sync_report}")
            if ignition_plan is not None:
                # Here, not where the plan was made: the sync above is what
                # produces the branch-state line the prompt carries, and it
                # cannot run earlier — the retiring session still owned the
                # tree when the plan was composed.
                prompt = ignition_plan.compose(branch_sync_report)
                ignition_plan = None
            # Read after the sync: where the file sits in the seat's own
            # checkout, the sync may just have brought it forward.
            appended_system_prompt_file = appended_system_prompt_file_for_launch(
                settings.appended_system_prompt_file,
                settings.appended_system_prompt_agent_part_path,
            )
            verb = "resuming" if resume_first_launch else "launching"
            print(f"handoff-supervisor: {verb} session {session_id} (generation {generation})")
            process = launch_agent_session(
                settings.agent_command, session_id, settings.working_directory, prompt,
                resume=resume_first_launch, remote_control_name=settings.agent,
                appended_system_prompt_file=appended_system_prompt_file,
                handoff_supervisor_agent_name=settings.agent,
            )
            resume_first_launch = False  # recovery applies to the first launch only

        handoff_fields = wait_for_handoff(
            process, settings.handoff_path, state.get("consumed_counter"), settings.state_path, state
        )
        if handoff_fields is None:
            # wait_for_handoff saw poll() report the exit, which is what sets a
            # launched session's returncode; an adopted one's stays None.
            record_agent_exit_in_supervisor_state(settings.state_path, state, process.returncode)
            print("handoff-supervisor: session ended without a handoff; supervisor stopping")
            return 0

        # A successor inherits this process's stdio, so without a terminal
        # there is no seat to relaunch onto: the successor reads EOF at its
        # first need for input and dies after one turn — observed 2026-08-14,
        # when an adopted console session was killed and its successor
        # reported into a log file. Refusing BEFORE the kill and the consume
        # leaves the session alive and its handoff intact for a seated
        # supervisor (a launcher-owned tmux pane) or a by-hand relaunch.
        # dont-restart is exempt: that flow consumes and stops without ever
        # launching a successor, which needs no seat.
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
                # Nobody can answer: this supervisor has no terminal (its stdin
                # is redirected, not a launcher's tmux pane), and asking would
                # raise EOFError before the consumed counter is recorded —
                # leaving the next supervisor to re-fire on a stale handoff. Not
                # relaunching is the answer dont-restart asks for, so take it.
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
            # The session is stopped and no successor follows. The handoff stays
            # unconsumed, so recovery still defers to boot-ignition over this record.
            record_agent_exit_in_supervisor_state(settings.state_path, state, process.returncode)
            return 0

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

    # A missing file WARNS and launches without it, rather than refusing. The
    # default points into the checkout beside this script, and a supervisor run
    # from a tree that does not have the file yet — an older checkout, or one
    # mid-rebase — must still be able to seat its agent. Losing the appended
    # text degrades a session; refusing to launch loses the seat.
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
        first_prompt=arguments.first_prompt,
        resume_session_id=arguments.resume_session_id,
        appended_system_prompt_file=appended_system_prompt_file,
        adopted_session=adopted,
    )

    if not claim_supervisor_lock(settings.lock_path):
        print(
            f"handoff-supervisor: another supervisor already holds {settings.agent} "
            f"({settings.lock_path}); not starting a second one",
            file=sys.stderr,
        )
        return 4

    try:
        return supervise_sessions(settings)
    finally:
        settings.lock_path.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
