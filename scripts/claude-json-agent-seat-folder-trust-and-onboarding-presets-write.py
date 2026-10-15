#!/usr/bin/env python3
"""Pre-answer the Claude Code screens that would stop an agent-seat's agent-session at start.

Writes three things into ~/.claude.json, Claude Code's own state file, and only
those that are missing or different:
  - projects[<agent-seat folder>].hasTrustDialogAccepted = true, which answers
    the folder-trust dialog for that folder;
  - hasCompletedOnboarding = true, which keeps the onboarding screens (the
    theme picker first) off;
  - theme = "light", only when no theme is set; a theme already set is kept.

A detached launch has no one to answer those screens. The handoff-supervisor
also starts agent-sessions with IS_DEMO=1, which skips them; these presets keep
them off if a Claude Code update changes what IS_DEMO does, and the trust
preset means a session that skips the trust dialog runs in a folder trusted on
purpose.

Used by scripts/launch-claude-mac, by scripts/launch-claude-ubuntu on the box,
and by scripts/recover-crashed-seats.py before it starts a supervisor itself.

Usage: claude-json-agent-seat-folder-trust-and-onboarding-presets-write.py AGENT_SEAT_FOLDER
Exits 0 when the file holds the presets, written or already there; exits 1,
with the cause on stderr, when the file cannot be read as JSON or cannot be
written. An unparseable file is never overwritten: it holds the account's
credentials, and replacing it would sign the machine out.
"""

import json
import os
import pathlib
import sys
import tempfile

THEME_SET_WHEN_NONE_IS_SET = "light"
TEMPORARY_FILE_PREFIX = ".claude.json."
TEMPORARY_FILE_SUFFIX = ".launch-claude-writing"


class ClaudeJsonNotAJsonObjectError(ValueError):
    """~/.claude.json exists but does not hold a JSON object."""


def claude_json_path() -> pathlib.Path:
    return pathlib.Path(os.path.expanduser("~/.claude.json"))


def claude_json_agent_seat_folder_trust_and_onboarding_presets_write(
        claude_json: pathlib.Path, agent_seat_folder: str) -> bool:
    """Write the presets into claude_json; return True if the file was written."""
    exists = claude_json.exists()
    if exists:
        text = claude_json.read_text(encoding="utf-8")
        try:
            settings = json.loads(text)
        except ValueError as error:
            raise ClaudeJsonNotAJsonObjectError(
                f"{claude_json} is not valid JSON ({error})") from error
        if not isinstance(settings, dict):
            raise ClaudeJsonNotAJsonObjectError(
                f"{claude_json} holds JSON of type {type(settings).__name__}, not an object")
    else:
        settings = {}
    folder = os.path.abspath(os.path.expanduser(agent_seat_folder))
    project = settings.setdefault("projects", {}).setdefault(folder, {})
    changed = False
    if project.get("hasTrustDialogAccepted") is not True:
        project["hasTrustDialogAccepted"] = True
        changed = True
    if settings.get("hasCompletedOnboarding") is not True:
        settings["hasCompletedOnboarding"] = True
        changed = True
    if "theme" not in settings:
        settings["theme"] = THEME_SET_WHEN_NONE_IS_SET
        changed = True
    if not changed:
        return False
    # Running agent-sessions write this file too, so it is replaced, never truncated:
    # a reader sees the whole old file or the whole new one. The temporary file sits in
    # the target's own directory because os.replace is atomic only within one filesystem,
    # and its name is unique because two launches can overlap.
    # Path.write_text raises when the write fails; a plain open().write() can lose that
    # error at deallocation and then publish an empty file.
    # os.replace keeps the temporary file's mode, so the target's mode is carried over;
    # a new file is 0600 because it holds credentials.
    # Not fixed: a write by an agent-session between the read and the replace is lost.
    mode = claude_json.stat().st_mode & 0o777 if exists else 0o600
    handle, temporary = tempfile.mkstemp(dir=str(claude_json.parent),
                                         prefix=TEMPORARY_FILE_PREFIX,
                                         suffix=TEMPORARY_FILE_SUFFIX)
    os.close(handle)
    pathlib.Path(temporary).write_text(json.dumps(settings, indent=2), encoding="utf-8")
    os.chmod(temporary, mode)
    os.replace(temporary, claude_json)
    return True


USAGE = "usage: claude-json-agent-seat-folder-trust-and-onboarding-presets-write.py AGENT_SEAT_FOLDER"


def main(arguments) -> int:
    if arguments in (["-h"], ["--help"]):
        print(USAGE)
        print(__doc__.split("\n\n")[0])
        return 0
    # An option is never a folder name: writing it would trust a folder nobody meant.
    if len(arguments) != 1 or arguments[0].startswith("-"):
        print(USAGE, file=sys.stderr)
        return 2
    path = claude_json_path()
    try:
        claude_json_agent_seat_folder_trust_and_onboarding_presets_write(path, arguments[0])
    except (ClaudeJsonNotAJsonObjectError, OSError) as error:
        print(f"claude-json-agent-seat-folder-trust-and-onboarding-presets-write: {error}. "
              f"{path} was left unchanged, so the agent-session may stop at Claude Code's "
              "folder-trust dialog or onboarding screens.\n"
              f"If {path} is not valid JSON: restore it from the newest copy in "
              "~/.claude/backups/ that is valid JSON, then launch again.\n"
              "Otherwise: fix the cause named above, then launch again.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
