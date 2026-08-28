#!/usr/bin/env python3
"""Write the handoff file for a retiring session, and report who is watching.

The handoff system's writer (specification:
docs/cross-project/fast-handoff-design.md). The retiring agent writes one
thing — the prompt telling its successor what to do first — and this script
does everything else a machine can do: it stamps the timestamp, derives the
restart counter, derives the roster of subagents this session spawned,
formats and writes the file, then checks whether a supervisor is actually
watching and tells the agent what that means for it.

Usage:
  handoff-write-and-check-supervisor.py --agent <name> --next-step-file <path>
                                        [--dont-restart] [--claim]

`--claim` is for one situation, and it is worth knowing before you meet it:
this seat's FIRST handoff under a name that a handoff file already holds from
a DIFFERENT directory. The refusal exists because two seats sharing a name
means one handoff is about to be lost unread (observed 2026-08-16, counter 10
overwritten by counter 11 seconds later). But a seat legitimately inherits a
name when it moves directories or is re-founded elsewhere, and then the
refusal is the only thing standing between it and its own first handoff.
`--claim` takes the name, overwriting whatever handoff stands, with no
approval check: the refusal text is the guard and the typed flag in the
transcript is the audit trail (R9). Read the refusal before passing it — it
names the directory currently holding the name, which is what tells you
whether you are inheriting or colliding.

The next step arrives as a FILE rather than an argument so that backticks,
quotes, and newlines survive: a shell mangles all three inside an inline
argument.

A multi-line next step is written TWICE, and this is deliberate (R20; format
specified in docs/cross-project/fast-handoff-design.md). `next-step:` is
always the whitespace-collapsed single line, because that is what every
reader already handles — including a supervisor process that started before
this format existed and is still running. When the text spans lines, a
`next-step-verbatim:` block carrying it unaltered is appended LAST, after
every computed field, so a content line that happens to look like
`key: value` cannot shadow a real field: the real fields precede it and the
reader takes the first occurrence of a key.

Writing the marker on the `next-step:` line instead would be the obvious
design and is wrong: an older supervisor would boot its successor with the
marker string as its entire instruction, silently.

The liveness report is part of this script rather than a second command
because the two are one decision: a handoff nobody is watching must not stop
the agent working, and an agent that runs only the first half of a two-step
procedure would stop anyway.

Exit codes: 0 written and a supervisor is watching, 1 written but nothing is
watching, 2 bad invocation or an empty next step.
"""

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_supervisor_spec = importlib.util.spec_from_file_location(
    "handoff_supervisor", Path(__file__).with_name("handoff-supervisor.py")
)
supervisor = importlib.util.module_from_spec(_supervisor_spec)
_supervisor_spec.loader.exec_module(supervisor)


NEXT_STEP_VERBATIM_FIELD = "next-step-verbatim"
NEXT_STEP_BLOCK_OPENING_MARKER = "<<END-OF-NEXT-STEP"
NEXT_STEP_BLOCK_TERMINATOR = "END-OF-NEXT-STEP"

PROJECTS_ROOT = Path.home() / ".claude" / "projects"

# One numbered field per subagent: `spawned-subagent-1`, `spawned-subagent-2`.
# A repeated key would not work — the reader takes the first occurrence of a
# key, so every subagent but the first would be dropped.
SPAWNED_SUBAGENT_FIELD_PREFIX = "spawned-subagent-"

# No transcript record can describe a subagent event without carrying one of
# these strings, so a line carrying none of them is never parsed. A session
# transcript runs to megabytes of tool output; this substring pre-filter is
# what keeps deriving the roster from parsing all of it.
SUBAGENT_EVENT_RECORD_MARKERS = ("async_launched", "resumedAgentId", "<task-notification>")


def collapse_to_one_line(text: str) -> str:
    """Collapse every run of whitespace into a single space."""
    return re.sub(r"\s+", " ", text).strip()


def verbatim_block_lines(text: str):
    """The lines of a multi-line next step, or [] when it does not need a block.

    Blank lines between the first and last non-blank lines are kept — they are
    part of what the agent wrote. Blank lines before the first and after the
    last are not written at all.
    """
    if "\n" not in text.strip("\n"):
        # One line of content, however much surrounding whitespace: the
        # collapsed `next-step:` field already carries it exactly.
        return []
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines if len(lines) > 1 else []


def consumed_counter_from_state(state_path: Path):
    """Return the counter the supervisor has already acted on, if any."""
    if not state_path.is_file():
        return None
    try:
        value = json.loads(state_path.read_text(encoding="utf-8")).get("consumed_counter")
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None
    return value if isinstance(value, int) else None


def next_restart_counter(handoff_path: Path, state_path: Path) -> int:
    """Return a counter the supervisor is guaranteed to read as new.

    The previous handoff file is the ordinary source, but it can be missing,
    malformed, or older than what the supervisor has already consumed. Taking
    the higher of the two is what keeps this from writing a counter the
    supervisor will ignore — a silent failure to recycle, with a handoff on
    disk and nothing acting on it.
    """
    from_file = supervisor.counter_from(supervisor.parse_handoff_file(handoff_path)) \
        if handoff_path.is_file() else None
    from_state = consumed_counter_from_state(state_path)
    highest_seen = max(value for value in (from_file, from_state, 0) if value is not None)
    return highest_seen + 1


def default_agent_name() -> str:
    """The working directory's name, which is already unique per seat.

    An agent name selects the handoff file, the supervisor state and the lock,
    so two sessions sharing a name share all three. Nothing enforced
    uniqueness and the name was a free-text argument, so every hand-started
    session on this Mac was called `new-vp` and they overwrote each other's
    handoffs: on 2026-08-16 one session wrote counter 10 and another wrote
    counter 11 seconds later, and the first was gone — never archived, because
    retention keeps the last two GENERATIONS of one file, not one file per
    session.

    A worktree directory name is unique by construction — Claude Code appends
    a random suffix for exactly that reason — so defaulting to it removes the
    collision without anyone having to invent a name. An explicit --agent
    still wins, which is how the launchers name their seats.
    """
    return Path.cwd().name


def claiming_directory(handoff_path: Path) -> str:
    """Which directory last wrote this handoff, or '' if it does not say."""
    if not handoff_path.is_file():
        return ""
    return supervisor.parse_handoff_file(handoff_path).get("written-in", "")


def project_directory_for_working_directory(working_directory: Path) -> Path:
    """Return the ~/.claude/projects directory holding a worktree's sessions.

    The harness mangles the absolute path by replacing every character that is
    not alphanumeric, a dash, or an underscore with a dash.
    """
    mangled = "".join(
        character if (character.isalnum() or character in "-_") else "-"
        for character in str(working_directory)
    )
    return PROJECTS_ROOT / mangled


def find_session_transcript(session_id: str, working_directory: Path):
    """Locate a session's JSONL by id: keyed lookup first, then a search.

    Returns None rather than raising. The roster is one extra field on a
    handoff; a handoff must still be written when the transcript cannot be
    found, and an ambiguous search hit is no better than none.
    """
    if not session_id or session_id == "unknown":
        return None
    keyed_path = project_directory_for_working_directory(working_directory) / f"{session_id}.jsonl"
    if keyed_path.is_file():
        return keyed_path
    matches = sorted(PROJECTS_ROOT.glob(f"*/{session_id}.jsonl"))
    return matches[0] if len(matches) == 1 else None


def timestamp_to_whole_seconds(stamp: str) -> str:
    """`2026-08-23T19:55:24.756Z` -> `2026-08-23T19:55:24Z`, as `written-at` reads."""
    match = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", stamp or "")
    return f"{match.group(1)}Z" if match else "an unrecorded time"


def task_notification_text(record: dict):
    """The `<task-notification>` body a transcript record carries, or None.

    One notification reaches the transcript ONE TO THREE TIMES — never four —
    in one of four observed combinations of record type. Measured by grouping
    records on an identical notification body across three merge-lane session
    transcripts spanning 2026-08-21 to 2026-08-24; the counts below are that
    measurement, one per session, not an estimate:

        enqueue only                          3 / 4 / 3
        enqueue + remove                      1 / 33 / 0
        enqueue + delivered user turn        17 / 158 / 17
        enqueue + remove + attachment copy   13 / 69 / 23

    Enqueue and remove are `queue-operation` records, the delivered turn is a
    `user` record, and the copy is an `attachment` record.

    Every combination is read rather than only the delivered one, because the
    first of them is a notification nothing ever delivered — and an
    undelivered notification is invisible to a reader that only takes the
    delivered turn.

    What that combination actually held, stated as measured rather than as
    imagined: all ten enqueue-only specimens across the three sessions carry
    `killed` at the session's death — eight naming background tasks, and two
    naming subagents, both in 3f4965a7. A subagent whose COMPLETION was
    enqueued and never delivered has no specimen in any of the three. That
    variant is handled because reading every combination is what makes any
    undelivered notification visible, not because it was observed.
    """
    if record.get("type") == "user":
        message = record.get("message")
        content = message.get("content") if isinstance(message, dict) else None
    elif record.get("type") == "queue-operation":
        content = record.get("content")
    elif record.get("type") == "attachment":
        attachment = record.get("attachment")
        content = attachment.get("prompt") if isinstance(attachment, dict) else None
    else:
        return None
    if isinstance(content, str) and content.startswith("<task-notification>"):
        return content
    return None


def spawned_subagent_roster(transcript_path: Path) -> list:
    """Every subagent this session SPAWNED, in spawn order, with its last event.

    Each entry is a dict: agent_id, description, spawned_at, last_event,
    last_event_at. Ordinary reading of one session's own transcript.

    **Spawned, not running.** The roster deliberately does not try to say
    which subagents are alive. On 2026-08-23 the merge-lane seat's fixer for
    pull request #150 was NOT running when its session was recycled: it had
    finished a round and was sitting idle, resumable, still owning the
    unfinished fix. Its branch and worktree survived on disk; only the
    knowledge that it existed was lost. A roster filtered to running
    subagents would have excluded the one orphan it was built to catch, so
    the writer records what a machine can know and the successor judges which
    entries still own work. The user ruled on 2026-08-23 that killing and
    restarting subagents is the standing policy and that the fix is to record
    them, not to wait for them.

    **Liveness is not inferred from unmatched tool_use/tool_result pairs**,
    and that is worth stating because it is the obvious wrong answer: the
    `Agent` tool returns its result at SPAWN time ("Async agent launched
    successfully... you will be notified when it completes"), so every spawn
    is a matched pair whatever becomes of the subagent. Completion arrives
    later, as separate `<task-notification>` records.

    **Background monitors are excluded structurally, not by their ids.** A
    monitor's tool result carries `taskId`/`persistent` and no `agentId`, so
    keying spawns on `status == "async_launched"` with an `agentId` selects
    subagents only. Measured on session `40a16b9c` of 2026-08-23, where nine
    subagents and eight monitors ran. Eight by either of two independent
    countings — `Monitor` tool-use blocks, and tool results carrying
    `persistent: true`. Counting every distinct `taskId` without an `agentId`
    instead gives fifteen, because backgrounded `Bash` tasks carry a `taskId`
    too; `persistent` is what separates a monitor from one of those.

    **One generation of memory, deliberately.** The roster a session writes
    holds the subagents THAT session spawned. Nothing a predecessor recorded
    is carried into it, so an entry a successor reads, judges can wait, and
    defers is absent from the roster its own recycle writes — and the orphan
    drops back to prose, which is the failure this field exists to remove.
    Carrying unresolved entries across recycles is a larger change and is not
    attempted here; the scope is stated so that a reader does not assume a
    persistence the code does not provide. A deferred subagent that still
    matters belongs in `next-step`, which does survive the next recycle.
    """
    roster = []
    by_agent_id = {}
    with transcript_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not any(marker in line for marker in SUBAGENT_EVENT_RECORD_MARKERS):
                continue
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue  # the transcript is read while its writer is still running
            if not isinstance(record, dict):
                continue
            stamp = timestamp_to_whole_seconds(record.get("timestamp", ""))

            result = record.get("toolUseResult")
            if isinstance(result, dict):
                agent_id = result.get("agentId")
                if result.get("status") == "async_launched" and agent_id:
                    if agent_id not in by_agent_id:
                        entry = {
                            "agent_id": agent_id,
                            # Collapsed: a description is free text from the
                            # spawning call, and a newline inside one would
                            # split the roster's line in the handoff file.
                            "description": collapse_to_one_line(str(result.get("description") or "")),
                            "spawned_at": stamp,
                            "last_event": "spawned",
                            "last_event_at": stamp,
                        }
                        by_agent_id[agent_id] = entry
                        roster.append(entry)
                    continue
                resumed = by_agent_id.get(result.get("resumedAgentId"))
                if resumed is not None:
                    resumed["last_event"] = "resumed"
                    resumed["last_event_at"] = stamp
                    continue

            notification = task_notification_text(record)
            if notification is None:
                continue
            status = re.search(r"<status>(.*?)</status>", notification)
            if status is None:
                continue
            # EVERY task-id in the notification, not just the first. One
            # notification can name several agents under a single <status>:
            # that is the shape the harness uses to report agents from a
            # previous session with no completion record, which is the
            # highest-value event this roster carries. Reading only the first
            # left every later agent holding whatever it had before.
            # Specimen, in this seat's own history: session 3f4965a7 at
            # 2026-08-21T19:31:05Z names a3fe2b9aecae01f3b and
            # a677554663305e800 — both subagents that session spawned — under
            # <status>stopped</status>. Truncate that transcript at the
            # notification and the single-id derivation reports the second
            # agent as "killed at 18:38:09Z", 53 minutes early and under the
            # wrong event name. Ids that name background tasks rather than
            # subagents are not in by_agent_id and are skipped.
            for task_id in re.findall(r"<task-id>(.*?)</task-id>",
                                      notification):
                entry = by_agent_id.get(task_id)
                if entry is None:
                    continue
                # Only a CHANGE of status is a new event. The same completion
                # is announced up to three times, so taking every announcement
                # would date the event at its last echo rather than at its
                # arrival.
                if status.group(1) != entry["last_event"]:
                    entry["last_event"] = status.group(1)
                    entry["last_event_at"] = stamp
    return roster


def spawned_subagent_field_lines(roster) -> list:
    """Render a roster as the handoff file's numbered `key: value` lines."""
    lines = []
    for ordinal, entry in enumerate(roster, start=1):
        described = f' "{entry["description"]}"' if entry["description"] else ""
        lines.append(
            f"{SPAWNED_SUBAGENT_FIELD_PREFIX}{ordinal}: {entry['agent_id']}{described}"
            f" spawned at {entry['spawned_at']},"
            f" last event {entry['last_event']} at {entry['last_event_at']}"
        )
    return lines


def spawned_subagent_roster_for_this_session(working_directory: Path):
    """Return (field lines, one line for the console) for the running session.

    Never raises, on the same principle as the branch-protection audit below:
    a broken derivation must not break a handoff. When it cannot produce a
    roster it says so on the console, so the retiring agent knows to name its
    subagents in the next step by hand rather than assuming they were
    recorded — silence about subagents is the failure this field exists to
    remove, and a silent failure to derive them would reinstate it.
    """
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not session_id:
        return [], ("spawned-subagent roster: not derived — CLAUDE_CODE_SESSION_ID is unset, so this "
                    "script cannot find the transcript. Name any subagents in the next step by hand.")
    try:
        transcript_path = find_session_transcript(session_id, working_directory)
        if transcript_path is None:
            return [], (f"spawned-subagent roster: not derived — no single transcript found for session "
                        f"{session_id} under {PROJECTS_ROOT}. Name any subagents in the next step by hand.")
        roster = spawned_subagent_roster(transcript_path)
    except Exception as error:  # noqa: BLE001 - the roster never blocks a handoff
        return [], (f"spawned-subagent roster: not derived — {type(error).__name__}: {error}. "
                    "Name any subagents in the next step by hand.")
    if not roster:
        return [], "spawned-subagent roster: this session spawned no subagents"
    return (spawned_subagent_field_lines(roster),
            f"spawned-subagent roster: {len(roster)} subagent(s) recorded for the successor")


def write_handoff_file(handoff_path: Path, next_step: str, counter: int, dont_restart: bool,
                       spawned_subagent_lines=(), verbatim_lines=()) -> None:
    """Write the handoff file in one step, so no reader sees it half-written."""
    lines = [
        f"written-at: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"next-step: {next_step}",
        f"restart-counter: {counter}",
        # Who wrote this, so a collision is detectable rather than silent.
        # written-in is the discriminator, not the session id: successive
        # generations of one seat are different sessions in the SAME
        # directory, while two seats sharing a name are different directories.
        f"written-in: {Path.cwd()}",
        f"written-by-session: {os.environ.get('CLAUDE_CODE_SESSION_ID', 'unknown')}",
    ]
    if dont_restart:
        lines.append("dont-restart: the user asked to be consulted before a relaunch")

    # The subagents this session spawned die with it, and until this field
    # existed nothing told the successor they had ever run (2026-08-23; see
    # spawned_subagent_roster). Written as ordinary fields, before the block.
    lines.extend(spawned_subagent_lines)

    # LAST, always: a block's content lines can look like fields, and only the
    # position guarantees they cannot shadow one.
    if verbatim_lines:
        lines.append(f"{NEXT_STEP_VERBATIM_FIELD}: {NEXT_STEP_BLOCK_OPENING_MARKER}")
        lines.extend(verbatim_lines)
        lines.append(NEXT_STEP_BLOCK_TERMINATOR)

    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = handoff_path.with_suffix(handoff_path.suffix + ".partial")
    temporary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(temporary_path, handoff_path)


# The adopt-and-recycle path once lived here: with no supervisor watching, this
# script started a detached one that adopted the running session, killed it, and
# relaunched. Removed 2026-08-14 after its second observed failure: a successor
# inherits the supervisor's stdio, and a detached supervisor's console is a log
# file, so every successor it launched died at its first need for input — the
# desktop-app case observed 2026-08-11, the terminal-console case 2026-08-14.
# Only a seat-owning supervisor (a tmux pane via the launchers) can recycle;
# every other seat hands off by the user relaunching and pointing the fresh
# session at the handoff file.


def run_branch_protection_audit() -> str:
    """Slice 5's ruled anchor (2026-08-12): the branch-protection audit rides
    each session recycle. One line, never blocking — an unreadable wall is a
    named finding, and a broken audit must never break a handoff."""
    if os.environ.get("HANDOFF_SKIP_PROTECTION_AUDIT"):
        return "branch-protection audit: skipped (HANDOFF_SKIP_PROTECTION_AUDIT set)"
    gatekeeper_path = Path(__file__).with_name("git-gatekeeper.py")
    if not gatekeeper_path.is_file():
        return "branch-protection audit: audit-failed — no gatekeeper beside this script"
    try:
        completed = subprocess.run(
            [sys.executable, str(gatekeeper_path), "audit"],
            capture_output=True, text=True, check=False, timeout=45,
        )
        payload = json.loads(completed.stdout)
        return f"branch-protection audit: {payload.get('summary', completed.stdout.strip())}"
    except Exception as error:  # noqa: BLE001 - the audit never blocks a handoff
        return f"branch-protection audit: audit-failed — {type(error).__name__}: {error}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Write the handoff file that retires this session.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--agent", default=None,
        help="agent name; names the handoff file. Defaults to the working "
             "directory's name, which is unique per worktree — pass this only "
             "to name a seat deliberately, as the launchers do.",
    )
    parser.add_argument(
        "--claim", action="store_true",
        help="write even though another directory holds this agent name, taking the name from it",
    )
    parser.add_argument(
        "--next-step-file", required=True,
        help="file holding the prompt for the successor; written collapsed to one line, and "
             "also verbatim when it spans several lines",
    )
    parser.add_argument(
        "--dont-restart", action="store_true",
        help="ask the supervisor to confirm before relaunching, instead of relaunching automatically",
    )
    parser.add_argument("--handoff-dir", default="~/.claude/handoffs", help="machine-local handoff directory")
    arguments = parser.parse_args(argv)

    next_step_path = Path(arguments.next_step_file).expanduser()
    if not next_step_path.is_file():
        print(f"handoff-write-and-check-supervisor: no such file: {next_step_path}", file=sys.stderr)
        return 2

    next_step_text = next_step_path.read_text(encoding="utf-8")
    next_step = collapse_to_one_line(next_step_text)
    if not next_step:
        print(
            "handoff-write-and-check-supervisor: the next-step file is empty — the successor would boot "
            "with no instruction, so nothing was written",
            file=sys.stderr,
        )
        return 2

    # The empty refusal above is applied to the COLLAPSED value, before any
    # block is considered, so a next step that is only whitespace is refused
    # rather than written as an empty block.
    verbatim_lines = verbatim_block_lines(next_step_text)
    # EXACT match, the same comparison the reader ends a block on. A stripped
    # match here would refuse indented lookalikes the reader would have kept as
    # content, and the two ends must agree on exactly one rule.
    offending = [line for line in verbatim_lines if line == NEXT_STEP_BLOCK_TERMINATOR]
    if offending:
        print(
            "handoff-write-and-check-supervisor: the next step contains a line equal to the block "
            f"terminator ({NEXT_STEP_BLOCK_TERMINATOR}), which would end the block early and change "
            "what the successor reads. Reword that line and rerun. Nothing was written.",
            file=sys.stderr,
        )
        return 2

    agent = arguments.agent or default_agent_name()
    handoff_directory = Path(arguments.handoff_dir).expanduser()
    handoff_path = handoff_directory / f"{agent}-handoff.md"
    state_path = handoff_directory / f"{agent}-supervisor-state.json"

    # Refuse a foreign claim rather than overwrite it. Successive generations
    # of one seat run in the same directory, so a DIFFERENT directory holding
    # this name means two seats share it and one handoff is about to be lost
    # unread -- observed 2026-08-16, counter 10 overwritten by counter 11
    # seconds later, with no archived copy because retention keeps the last
    # two generations of the file rather than one file per session.
    # Compare RESOLVED paths: on macOS /var is a symlink to /private/var, so
    # the same seat can describe itself two ways and would otherwise look
    # foreign to itself and refuse its own handoff.
    held_by = claiming_directory(handoff_path)
    held_by_resolved = str(Path(held_by).resolve()) if held_by else ""
    if held_by and held_by_resolved != str(Path.cwd().resolve()) and not arguments.claim:
        print(
            f"handoff-write-and-check-supervisor: {handoff_path} belongs to a seat in "
            f"{held_by}, and this session is in {Path.cwd()}. Nothing was written, because "
            f"writing would destroy a handoff that seat may not have acted on yet. Either "
            f"run with --agent <a name of your own> (the default is this directory's name, "
            f"{default_agent_name()}), or pass --claim to take the name from it.",
            file=sys.stderr,
        )
        return 2

    counter = next_restart_counter(handoff_path, state_path)
    spawned_subagent_lines, roster_report = spawned_subagent_roster_for_this_session(Path.cwd())
    write_handoff_file(handoff_path, next_step, counter, arguments.dont_restart,
                       spawned_subagent_lines=spawned_subagent_lines,
                       verbatim_lines=verbatim_lines)
    print(f"handoff-write-and-check-supervisor: wrote {handoff_path} (restart-counter {counter})")
    print(f"handoff-write-and-check-supervisor: {roster_report}")
    print(f"handoff-write-and-check-supervisor: {run_branch_protection_audit()}")

    alive, explanation = supervisor.supervisor_liveness(state_path)
    if alive:
        print(
            f"handoff-write-and-check-supervisor: {explanation}. Stop working now and wait — "
            "it takes over within seconds."
        )
        return 0

    # What to tell the user changed on 2026-08-14, when the supervisor learned to
    # ignite from an unconsumed handoff at boot: the old advice here — relaunch
    # claude by hand and point it at the file — rebuilds the very state this
    # branch is reporting, a seat running with nothing watching it. The launcher
    # is the supervised path, and scripts/resupervise-seat.py performs the whole
    # procedure (it refuses unless this handoff is genuinely waiting).
    # --machine is printed explicitly, never left to the default. The same agent
    # name is permitted on both machines and means two unrelated seats, so a box
    # seat printing the bare command would have the operator run it on the Mac
    # against a same-named MAC seat: the recovery would refuse only if that Mac
    # seat had no waiting handoff of its own, which is not something this advice
    # may assume. Linux here means the box, since that is the fleet's only
    # non-Mac machine; the flag is stated on both so the printed line is
    # copy-paste-correct wherever it is read.
    machine = "ubuntu" if sys.platform.startswith("linux") else "mac"
    print(
        f"handoff-write-and-check-supervisor: {explanation} — and this seat has no supervisor to "
        f"recycle it. The handoff is written at {handoff_path}; nothing will act on it by itself. "
        "Tell the user: to seat a supervised successor, run "
        f"`scripts/resupervise-seat.py {agent} --machine {machine}` — it clears this seat's stale "
        "tmux session and relaunches, and the supervisor ignites from the handoff. Relaunching "
        "`claude` by hand instead produces another unsupervised seat. Until then, keep working."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
