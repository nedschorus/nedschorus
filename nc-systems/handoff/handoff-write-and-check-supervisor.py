#!/usr/bin/env python3
"""Write the handoff file for a retiring session, and report who is watching.

The handoff system's writer (specification:
nc-systems/handoff/handoff-design.md). The retiring agent writes one
thing — the prompt telling its successor what to do first — and this script
does everything else a machine can do: it stamps the timestamp, derives the
restart counter, derives the roster of subagents still working — the ones the
reincarnation is about to kill mid-job — formats and writes the file, then checks
whether a supervisor is actually watching and tells the agent what that means
for it.

Usage:
  handoff-write-and-check-supervisor.py --agent <name> --next-step-file <path>
                                        [--dont-restart] [--claim]

`--claim` is for two situations, and both are worth knowing before you meet
them: this seat's FIRST handoff under a name that a handoff file already holds
from a DIFFERENT directory, and its first under a NEW name in a directory
whose existing name a supervisor already answers for. The refusal exists because two seats sharing a name
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
specified in nc-systems/handoff/handoff-design.md). `next-step:` is
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

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

_supervisor_spec = importlib.util.spec_from_file_location(
    "handoff_supervisor", Path(__file__).with_name("handoff-supervisor.py")
)
supervisor = importlib.util.module_from_spec(_supervisor_spec)
_supervisor_spec.loader.exec_module(supervisor)


NEXT_STEP_VERBATIM_FIELD = "next-step-verbatim"
NEXT_STEP_BLOCK_OPENING_MARKER = "<<END-OF-NEXT-STEP"
NEXT_STEP_BLOCK_TERMINATOR = "END-OF-NEXT-STEP"

PROJECTS_ROOT = supervisor.PROJECTS_ROOT
project_directory_for_working_directory = supervisor.project_directory_for_working_directory

HANDOFF_SUPERVISOR_AGENT_NAME_ENVIRONMENT_VARIABLE = (
    supervisor.HANDOFF_SUPERVISOR_AGENT_NAME_ENVIRONMENT_VARIABLE
)
HANDOFF_SUPERVISOR_WORKING_DIRECTORY_ENVIRONMENT_VARIABLE = (
    supervisor.HANDOFF_SUPERVISOR_WORKING_DIRECTORY_ENVIRONMENT_VARIABLE
)
HANDOFF_SUPERVISOR_SESSION_ID_ENVIRONMENT_VARIABLE = (
    supervisor.HANDOFF_SUPERVISOR_SESSION_ID_ENVIRONMENT_VARIABLE
)

DEFAULT_AGENT_NAME_RULE_TEXT = (
    f"the name the handoff-supervisor that launched this session watches "
    f"({HANDOFF_SUPERVISOR_AGENT_NAME_ENVIRONMENT_VARIABLE}), else the working directory's name"
)

# Number each subagent field: the reader takes only the first occurrence of a key.
SPAWNED_SUBAGENT_FIELD_PREFIX = "spawned-subagent-"

# Only spawn and resume imply ongoing work; unrecognized notification statuses count as ended.
STILL_WORKING_SUBAGENT_LAST_EVENTS = ("spawned", "resumed")

# Prefilter megabytes of tool output before parsing possible subagent events.
SUBAGENT_EVENT_RECORD_MARKERS = ("async_launched", "resumedAgentId", "<task-notification>")


def collapse_to_one_line(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def verbatim_block_lines(text: str):
    """Return multiline content without outer blank lines, or [] for a single line."""
    if "\n" not in text.strip("\n"):
        return []
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines if len(lines) > 1 else []


def consumed_counter_from_state(state_path: Path):
    if not state_path.is_file():
        return None
    try:
        value = json.loads(state_path.read_text(encoding="utf-8")).get("consumed_counter")
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None
    return value if isinstance(value, int) else None


def next_restart_counter(handoff_path: Path, state_path: Path) -> int:
    """Return a counter newer than both the handoff and the supervisor's consumed state."""
    from_file = supervisor.counter_from(supervisor.parse_handoff_file(handoff_path)) \
        if handoff_path.is_file() else None
    from_state = consumed_counter_from_state(state_path)
    highest_seen = max(value for value in (from_file, from_state, 0) if value is not None)
    return highest_seen + 1


def handoff_supervisor_launched_this_session() -> bool:
    """Return whether supervisor variables identify this session."""
    # Child sessions inherit supervisor variables but have their own CLAUDE_CODE_SESSION_ID.
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    return bool(session_id) and session_id == os.environ.get(
        HANDOFF_SUPERVISOR_SESSION_ID_ENVIRONMENT_VARIABLE, "")


def default_agent_name() -> str:
    """Return the supervising seat's name, falling back to the working directory name."""
    # The shell may have changed directories; use supervisor identity only for its launched session.
    launched_as = (os.environ.get(HANDOFF_SUPERVISOR_AGENT_NAME_ENVIRONMENT_VARIABLE, "")
                   if handoff_supervisor_launched_this_session() else "")
    return launched_as or Path.cwd().name


def agent_seat_working_directory() -> Path:
    """Return the supervisor's launch directory, falling back to cwd."""
    # Transcript lookup is keyed by launch directory, not the shell's current directory.
    launched_in = (os.environ.get(HANDOFF_SUPERVISOR_WORKING_DIRECTORY_ENVIRONMENT_VARIABLE, "")
                   if handoff_supervisor_launched_this_session() else "")
    return Path(launched_in) if launched_in else Path.cwd()


def claiming_directory(handoff_path: Path) -> str:
    """Return the directory that last wrote the handoff, or an empty string."""
    if not handoff_path.is_file():
        return ""
    return supervisor.parse_handoff_file(handoff_path).get("written-in", "")


def supervised_name_for_this_directory(handoff_directory: Path, agent: str,
                                       seat_directory: Path) -> str:
    """Return this directory's supervised seat name, or an empty string."""
    # Require supervisor state: stray handoffs alone do not prove a name is watched.
    here = str(seat_directory.resolve())
    for other_handoff in supervisor.handoff_file_paths(handoff_directory):
        other = other_handoff.name[: -len(supervisor.HANDOFF_FILE_SUFFIX)]
        if other == agent:
            continue
        if not supervisor.supervisor_state_path(handoff_directory, other).is_file():
            continue
        written_in = claiming_directory(other_handoff)
        if written_in and str(Path(written_in).resolve()) == here:
            return other
    return ""


def find_session_transcript(session_id: str, working_directory: Path):
    """Return the session transcript path, or None if absent or ambiguous."""
    if not session_id or session_id == "unknown":
        return None
    keyed_path = project_directory_for_working_directory(working_directory) / f"{session_id}.jsonl"
    if keyed_path.is_file():
        return keyed_path
    matches = sorted(PROJECTS_ROOT.glob(f"*/{session_id}.jsonl"))
    return matches[0] if len(matches) == 1 else None


def timestamp_to_whole_seconds(stamp: str) -> str:
    match = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", stamp or "")
    return f"{match.group(1)}Z" if match else "an unrecorded time"


def task_notification_text(record: dict):
    """Return a task-notification body from queue, user or attachment records, or None."""
    # An enqueued notification may never reach a user turn.
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
    """Return this session's spawned subagents in spawn order with their last events."""
    # Agent results acknowledge spawn, not completion; terminal events arrive in notifications.
    # Predecessor rosters are not inherited; deferred work must remain in next-step.
    roster = []
    by_agent_id = {}
    with transcript_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not any(marker in line for marker in SUBAGENT_EVENT_RECORD_MARKERS):
                continue
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue  # The transcript writer may still be appending this record.
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
                            # Descriptions are free text; newlines would split a handoff field.
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
            # One notification can assign a single status to several task IDs.
            for task_id in re.findall(r"<task-id>(.*?)</task-id>",
                                      notification):
                entry = by_agent_id.get(task_id)
                if entry is None:
                    continue
                # Repeated notifications are echoes, not new events; preserve the first arrival time.
                if status.group(1) != entry["last_event"]:
                    entry["last_event"] = status.group(1)
                    entry["last_event_at"] = stamp
    return roster


def still_working_subagent_entries(roster) -> list:
    return [entry for entry in roster
            if entry["last_event"] in STILL_WORKING_SUBAGENT_LAST_EVENTS]


def spawned_subagent_field_lines(roster) -> list:
    """Render working subagents as numbered handoff fields."""
    lines = []
    for ordinal, entry in enumerate(roster, start=1):
        described = f' "{entry["description"]}"' if entry["description"] else ""
        lines.append(
            f"{SPAWNED_SUBAGENT_FIELD_PREFIX}{ordinal}: {entry['agent_id']}{described}"
        )
    return lines


def spawned_subagent_roster_for_this_session(working_directory: Path):
    """Return (roster field lines, console status), reporting failures without blocking handoff."""
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
    still_working = still_working_subagent_entries(roster)
    if not still_working:
        return [], (f"spawned-subagent roster: all {len(roster)} spawned subagent(s) had "
                    "ended by this handoff; none recorded (ended subagents are not "
                    "carried, ruled 2026-08-29)")
    return (spawned_subagent_field_lines(still_working),
            f"spawned-subagent roster: {len(still_working)} still-working subagent(s) "
            f"recorded for the successor, of {len(roster)} spawned")


def write_handoff_file(handoff_path: Path, next_step: str, counter: int, dont_restart: bool,
                       seat_directory: Path, spawned_subagent_lines=(), verbatim_lines=()) -> None:
    """Write the handoff atomically so readers cannot see a partial file."""
    lines = [
        f"written-at: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"next-step: {next_step}",
        f"restart-counter: {counter}",
        # Compare directories, not session IDs: reincarnations share a directory but have distinct sessions.
        f"written-in: {seat_directory}",
        f"written-by-session: {os.environ.get('CLAUDE_CODE_SESSION_ID', 'unknown')}",
    ]
    if dont_restart:
        lines.append("dont-restart: the user asked to be consulted before a relaunch")

    lines.extend(spawned_subagent_lines)

    # Write the block last so field-like content cannot shadow actual fields.
    if verbatim_lines:
        lines.append(f"{NEXT_STEP_VERBATIM_FIELD}: {NEXT_STEP_BLOCK_OPENING_MARKER}")
        lines.extend(verbatim_lines)
        lines.append(NEXT_STEP_BLOCK_TERMINATOR)

    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = handoff_path.with_suffix(handoff_path.suffix + ".partial")
    temporary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(temporary_path, handoff_path)




def run_branch_protection_audit() -> str:
    """Return an audit status line without letting audit failures block handoff."""
    if os.environ.get("HANDOFF_SKIP_PROTECTION_AUDIT"):
        return "branch-protection audit: skipped (HANDOFF_SKIP_PROTECTION_AUDIT set)"
    gatekeeper_path = (REPOSITORY_ROOT
                       / "nc-systems" / "main-gatekeeper" / "main-gatekeeper.py")
    if not gatekeeper_path.is_file():
        return f"branch-protection audit: audit-failed — no gatekeeper at {gatekeeper_path}"
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
        help=f"agent name; names the handoff file. Defaults to {DEFAULT_AGENT_NAME_RULE_TEXT}, "
             "which is unique per worktree — pass this only to name a seat deliberately, "
             "as the launchers do.",
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
    parser.add_argument("--handoff-dir", default="~/.claude/handoffs", help="handoff directory on this machine only, not committed")
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

    verbatim_lines = verbatim_block_lines(next_step_text)
    # Match the reader's exact terminator rule; indented lookalikes are content.
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
    seat_directory = agent_seat_working_directory()
    handoff_directory = Path(arguments.handoff_dir).expanduser()
    handoff_path = supervisor.handoff_file_path(handoff_directory, agent)
    state_path = supervisor.supervisor_state_path(handoff_directory, agent)

    # Resolve symlinks before comparing seat directories.
    # Compute the supervised name before advising --claim, which waives both refusals.
    supervised_name = supervised_name_for_this_directory(handoff_directory, agent, seat_directory)
    held_by = claiming_directory(handoff_path)
    held_by_resolved = str(Path(held_by).resolve()) if held_by else ""
    if held_by and held_by_resolved != str(seat_directory.resolve()) and not arguments.claim:
        if supervised_name:
            exits = (
                f"Rerun with --agent {supervised_name} -- this directory's supervised name, "
                f"the only name whose handoff is read here -- or omit --agent entirely (it "
                f"defaults to {DEFAULT_AGENT_NAME_RULE_TEXT}, here {default_agent_name()}). "
                f"Do NOT pass --claim to take {agent} from {held_by}: --claim also waives the "
                f"supervised-name check, and a handoff under {agent} would never be read here."
            )
        else:
            exits = (
                f"Either run with --agent <a name of your own> (the default is "
                f"{DEFAULT_AGENT_NAME_RULE_TEXT}, here {default_agent_name()}), or pass --claim "
                f"to take the name from it -- knowing that --claim also waives the check that no "
                f"supervisor answers for this directory under another name, which has just been "
                f"made and found none."
            )
        print(
            f"handoff-write-and-check-supervisor: {handoff_path} belongs to a seat in "
            f"{held_by}, and this session is in {seat_directory}. Nothing was written, because "
            f"writing would destroy a handoff that seat may not have acted on yet. {exits}",
            file=sys.stderr,
        )
        return 2

    # An unwatched name would strand the handoff even when this directory has a live supervisor.
    if supervised_name and not state_path.is_file() and not arguments.claim:
        print(
            f"handoff-write-and-check-supervisor: no supervisor has ever run under the name "
            f"{agent}, but {supervisor.handoff_file_path(handoff_directory, supervised_name)} "
            f"was written "
            f"from this very directory ({seat_directory}) and has a supervisor state beside it. "
            f"{supervised_name} is this seat's supervised name. Nothing was written, because a "
            f"handoff under a name nothing polls is never read: the supervisor keeps waiting on "
            f"{supervisor.handoff_file_path(handoff_directory, supervised_name).name} and this "
            f"session is never reincarnated (measured "
            f"2026-09-15, five hours and a lost session). Rerun with --agent {supervised_name}, "
            f"or omit --agent entirely -- it defaults to {DEFAULT_AGENT_NAME_RULE_TEXT}, here "
            f"{default_agent_name()} -- or pass --claim if this seat really is being re-founded "
            f"as {agent}.",
            file=sys.stderr,
        )
        return 2

    counter = next_restart_counter(handoff_path, state_path)
    spawned_subagent_lines, roster_report = spawned_subagent_roster_for_this_session(seat_directory)
    write_handoff_file(handoff_path, next_step, counter, arguments.dont_restart, seat_directory,
                       spawned_subagent_lines=spawned_subagent_lines,
                       verbatim_lines=verbatim_lines)
    print(f"handoff-write-and-check-supervisor: wrote {handoff_path} (restart-counter {counter})")
    print(f"handoff-write-and-check-supervisor: {roster_report}")
    print(f"handoff-write-and-check-supervisor: {run_branch_protection_audit()}")

    alive, explanation = supervisor.supervisor_liveness(state_path)
    if alive:
        # With ps unavailable, a held lock only implies a supervisor; do not promise takeover.
        print(
            f"handoff-write-and-check-supervisor: {explanation}. Stop working now and wait — "
            "if it is watching, it takes over within seconds."
        )
        return 0

    # Use the supervised launcher to consume the waiting handoff.
    # Print --machine explicitly: the default is Mac, but a box seat must be recovered on the box.
    machine = "ubuntu" if sys.platform.startswith("linux") else "mac"
    print(
        f"handoff-write-and-check-supervisor: {explanation} — and this seat has no supervisor to "
        f"reincarnate it. The handoff is written at {handoff_path}; nothing will act on it by itself. "
        "Tell the user: to seat a supervised successor, run "
        f"`scripts/resupervise-seat.py {agent} --machine {machine}` — it clears this seat's stale "
        "tmux session and relaunches, and the supervisor ignites from the handoff. Relaunching "
        "`claude` by hand instead produces another unsupervised seat. Until then, keep working."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
