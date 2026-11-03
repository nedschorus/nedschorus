#!/usr/bin/env python3
"""Read and write an agent-session's handoff-deferred marker file and its file of refused commands.

The threshold hook, scripts/handoff-context-threshold-hook.py, writes the marker file at the
first handoff-deferral: when the deferral began, and the subagents and background Bash tasks
then in flight, which are the only work later turns wait for. The cold-read-grid refusal hook
refuses a cold-read-full-run while the marker file exists and appends the refused command to
the file of refused commands. The handoff writer script reads both to list, in the
session-handoff, the work the deferral did not wait for. When the threshold hook fires the
handoff instruction it moves the marker file aside, so a later compaction cannot refire it, and
the writer reads the moved record; a record left by an earlier deferral that fired is read only
when no marker file exists, and then lists only background tasks still running, which the
session-handoff stops anyway.

Both files live in the handoff directory and are named by the Claude Code session id, which a
hook running inside a subagent also receives, as the id of the agent-session that started it.

handoff_deferred_marker_read raises HandoffDeferredMarkerUnreadable for a marker file that
cannot be read or does not hold the JSON record below, such as one a threshold hook wrote
before the record existed, which holds only the context share. cold_read_full_run_commands_refused_during_handoff_deferral_read
raises ColdReadFullRunCommandsRefusedDuringHandoffDeferralUnreadable likewise. Writes raise OSError.

Load it by path, under the snake_case form of its file name.
"""

# Deferred annotations let the module load on the Mac's system Python 3.9.
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

HANDOFF_DEFERRED_MARKER_SUFFIX = "-handoff-deferred"
HANDOFF_DEFERRED_MARKER_MOVED_AT_FIRE_SUFFIX = "-handoff-deferred-fired"
COLD_READ_FULL_RUN_COMMANDS_REFUSED_DURING_HANDOFF_DEFERRAL_SUFFIX = "-cold-read-full-run-commands-refused-during-handoff-deferral.jsonl"


def default_handoff_directory() -> Path:
    # Read HOME at call time so a test that redirects HOME redirects these files.
    return Path.home() / ".claude" / "handoffs"


class HandoffDeferredMarkerUnreadable(Exception):
    """The marker file exists but its record cannot be read."""


class ColdReadFullRunCommandsRefusedDuringHandoffDeferralUnreadable(Exception):
    """The file of refused commands exists but cannot be read."""


class HandoffDeferredMarker:
    """The marker file's record.

    awaited_work_is_unknown is True when the threshold hook could not read the whole transcript
    at the deferral; the id lists are then empty, and the awaited work is the work launched
    before deferral_began_at.
    """

    # A dataclass cannot be used: it needs its module in sys.modules, and loading by path skips that.
    def __init__(self, used_percentage, deferral_began_at, awaited_subagent_ids,
                 awaited_background_task_ids, awaited_work_is_unknown):
        self.used_percentage = used_percentage
        self.deferral_began_at = deferral_began_at
        self.awaited_subagent_ids = list(awaited_subagent_ids)
        self.awaited_background_task_ids = list(awaited_background_task_ids)
        self.awaited_work_is_unknown = awaited_work_is_unknown


def handoff_deferred_marker_path(handoff_directory: Path, session_id: str) -> Path:
    return Path(handoff_directory) / f"{session_id}{HANDOFF_DEFERRED_MARKER_SUFFIX}"


def handoff_deferred_marker_moved_at_fire_path(handoff_directory: Path, session_id: str) -> Path:
    return Path(handoff_directory) / f"{session_id}{HANDOFF_DEFERRED_MARKER_MOVED_AT_FIRE_SUFFIX}"


def handoff_deferred_marker_move_aside_at_fire(handoff_directory: Path, session_id: str):
    """Move the marker file to its fired path; return that path, or None when there is no marker.

    Raises OSError when the marker exists and cannot be moved.
    """
    moved = handoff_deferred_marker_moved_at_fire_path(handoff_directory, session_id)
    try:
        os.replace(handoff_deferred_marker_path(handoff_directory, session_id), moved)
    except FileNotFoundError:
        return None
    return moved


def utc_iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _write_whole(path: Path, text: str) -> None:
    # Written whole, so the grid hook and the writer script never read half a record.
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    try:
        partial.write_text(text, encoding="utf-8")
        os.replace(partial, path)
    except OSError:
        partial.unlink(missing_ok=True)
        raise


def handoff_deferred_marker_write(handoff_directory: Path, session_id: str,
                                  marker: HandoffDeferredMarker) -> Path:
    path = handoff_deferred_marker_path(handoff_directory, session_id)
    _write_whole(path, json.dumps({
        "used_percentage": round(marker.used_percentage, 1),
        "deferral_began_at": utc_iso(marker.deferral_began_at),
        "awaited_subagent_ids": list(marker.awaited_subagent_ids),
        "awaited_background_task_ids": list(marker.awaited_background_task_ids),
        "awaited_work_is_unknown": bool(marker.awaited_work_is_unknown),
    }) + "\n")
    return path


def handoff_deferred_marker_read(handoff_directory: Path, session_id: str):
    """Return the session's HandoffDeferredMarker, or None when it has no marker file."""
    return _handoff_deferred_record_read(handoff_deferred_marker_path(handoff_directory, session_id))


def handoff_deferral_record_read_from_marker_or_moved_at_fire(handoff_directory: Path, session_id: str):
    """Return the marker file's record, else the one the fire moved aside, else None."""
    marker = handoff_deferred_marker_read(handoff_directory, session_id)
    if marker is not None:
        return marker
    return _handoff_deferred_record_read(
        handoff_deferred_marker_moved_at_fire_path(handoff_directory, session_id))


def _handoff_deferred_record_read(path: Path):
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as problem:
        raise HandoffDeferredMarkerUnreadable(f"{path}: {problem}") from problem
    try:
        record = json.loads(text)
        if not isinstance(record, dict):
            raise ValueError("it does not hold a JSON object")
        began_at = datetime.fromisoformat(str(record["deferral_began_at"]).replace("Z", "+00:00"))
        if began_at.tzinfo is None:
            raise ValueError("deferral_began_at has no time zone")
        subagent_ids = record["awaited_subagent_ids"]
        background_task_ids = record["awaited_background_task_ids"]
        if not isinstance(subagent_ids, list) or not isinstance(background_task_ids, list):
            raise ValueError("an awaited list is not a list")
        return HandoffDeferredMarker(
            used_percentage=float(record["used_percentage"]),
            deferral_began_at=began_at,
            awaited_subagent_ids=[str(item) for item in subagent_ids],
            awaited_background_task_ids=[str(item) for item in background_task_ids],
            awaited_work_is_unknown=bool(record["awaited_work_is_unknown"]),
        )
    except (ValueError, KeyError, TypeError) as problem:
        raise HandoffDeferredMarkerUnreadable(
            f"{path} does not hold the handoff-deferral record ({type(problem).__name__}: "
            f"{problem}); its first line is {text.splitlines()[0][:80] if text else ''!r}"
        ) from problem


def handoff_deferred_marker_exists(handoff_directory: Path, session_id: str) -> bool:
    """Return whether the marker file exists; raises OSError when that cannot be told."""
    # Path.exists() answers False on a failed stat, which would read as no deferral.
    try:
        handoff_deferred_marker_path(handoff_directory, session_id).stat()
    except FileNotFoundError:
        return False
    return True


def cold_read_full_run_commands_refused_during_handoff_deferral_path(handoff_directory: Path, session_id: str) -> Path:
    return Path(handoff_directory) / f"{session_id}{COLD_READ_FULL_RUN_COMMANDS_REFUSED_DURING_HANDOFF_DEFERRAL_SUFFIX}"


def cold_read_full_run_command_refused_during_handoff_deferral_append(handoff_directory: Path, session_id: str,
                                          command: str, working_directory: str,
                                          now: datetime | None = None) -> Path:
    path = cold_read_full_run_commands_refused_during_handoff_deferral_path(handoff_directory, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"command": command, "working_directory": working_directory,
                       "refused_at": utc_iso(now or datetime.now(timezone.utc))})
    # One write of one line, so two subagents refused at once do not interleave their lines.
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return path


def cold_read_full_run_commands_refused_during_handoff_deferral_read(handoff_directory: Path, session_id: str) -> list:
    """Return [{command, working_directory, refused_at}, ...] in refusal order; [] when none."""
    path = cold_read_full_run_commands_refused_during_handoff_deferral_path(handoff_directory, session_id)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except (OSError, UnicodeDecodeError) as problem:
        raise ColdReadFullRunCommandsRefusedDuringHandoffDeferralUnreadable(f"{path}: {problem}") from problem
    entries = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            if not isinstance(entry, dict) or not isinstance(entry.get("command"), str):
                raise ValueError("it is not an object with a command")
        except ValueError as problem:
            raise ColdReadFullRunCommandsRefusedDuringHandoffDeferralUnreadable(
                f"{path} line {number}: {problem}") from problem
        entries.append(entry)
    return entries
