#!/usr/bin/env python3
"""Find the emergency-stop file in force, for the emergency-stop skill's
program and for every hook that behaves differently during an emergency stop.

The emergency-stop folder is the log-store's `emergency-stop/`: on ned-box
/home/nedlern/nedschorus-logs/emergency-stop/, on the Mac the same folder
through its mount, /Volumes/nedhome/nedschorus-logs/emergency-stop/.
NEDSCHORUS_EMERGENCY_STOP_FOLDER overrides both, for tests.

Only files named by the UTC time a stop started, as STOP_FILE_NAME_PATTERN
matches, are stop files; the repair brief and anything else in the folder is
ignored. The newest stop file is in force while its last line is not a lift
line. A lift line counts only as the file's last line and only at the start
of that line, so words inside a quote cannot lift a stop.

read_state() returns one of:
- NoStop: the folder is missing or holds no stop file, or the newest is lifted;
  a lifted newest file is reported as Lifted so a hook can say so once.
- InForce: the newest stop file has no lift line; its text is returned.
- Unreadable: the folder exists but the newest stop file cannot be read or
  decoded. Callers treat it as a stop in force.
- FolderUnreachable: the folder's parent, the log-store, cannot be reached,
  as on a Mac whose mount of ned-box is gone. Callers show "emergency-stop
  state unknown" and let work continue.

It never raises for a missing or unreadable folder or file; it raises only
for a programming error."""

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

NED_BOX_LOG_STORE = Path("/home/nedlern/nedschorus-logs")
MAC_LOG_STORE = Path("/Volumes/nedhome/nedschorus-logs")
FOLDER_NAME = "emergency-stop"
FOLDER_OVERRIDE_VARIABLE = "NEDSCHORUS_EMERGENCY_STOP_FOLDER"
STOP_FILE_NAME_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z\.md")
LIFT_LINE_PREFIX = "#emergency_stop_lifted "
COORDINATING_LINE_PREFIX = "coordinating agent-seat: "


@dataclass
class NoStop:
    folder: Path


@dataclass
class Lifted:
    path: Path
    lift_line: str


@dataclass
class InForce:
    path: Path
    text: str


@dataclass
class Unreadable:
    path: Path
    error: str


@dataclass
class FolderUnreachable:
    folder: Path
    error: str


def emergency_stop_folder(environment=None, platform=None):
    environment = os.environ if environment is None else environment
    platform = sys.platform if platform is None else platform
    override = environment.get(FOLDER_OVERRIDE_VARIABLE)
    if override:
        return Path(override)
    log_store = MAC_LOG_STORE if platform == "darwin" else NED_BOX_LOG_STORE
    return log_store / FOLDER_NAME


def last_line(text):
    lines = [line for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def coordinating_agent_seat(text):
    """The agent-seat named on the stop file's last coordinating line, or None."""
    named = None
    for line in text.splitlines():
        if line.startswith(COORDINATING_LINE_PREFIX):
            named = line[len(COORDINATING_LINE_PREFIX):].strip() or None
    return named


def read_state(folder):
    try:
        names = sorted(entry.name for entry in folder.iterdir()
                       if STOP_FILE_NAME_PATTERN.fullmatch(entry.name))
    except FileNotFoundError:
        if folder.parent.is_dir():
            return NoStop(folder)
        return FolderUnreachable(folder, f"{folder.parent} does not exist or cannot be reached")
    except OSError as error:
        return FolderUnreachable(folder, str(error))
    if not names:
        return NoStop(folder)
    newest = folder / names[-1]
    try:
        text = newest.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return Unreadable(newest, str(error))
    final = last_line(text)
    if final.startswith(LIFT_LINE_PREFIX):
        return Lifted(newest, final)
    return InForce(newest, text)
