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
nc-systems/handoff/handoff-supervisor.py calls
claude_json_onboarding_presets_write, which writes the onboarding and theme
presets without the trust preset, before every agent-session it launches,
relaunches included: a /logout can clear hasCompletedOnboarding while a
supervisor runs.

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
# Keyed on the exact type, because bool is a subclass of int.
JSON_TYPE_NAME_BY_PYTHON_TYPE = {list: "array", str: "string", int: "number",
                                 float: "number", bool: "boolean", type(None): "null"}


class ClaudeJsonNotAJsonObjectError(ValueError):
    """~/.claude.json exists but does not hold a JSON object."""


class ClaudeJsonNotValidJsonError(ClaudeJsonNotAJsonObjectError):
    """~/.claude.json exists but cannot be read as JSON at all."""


def claude_json_path() -> pathlib.Path:
    return pathlib.Path(os.path.expanduser("~/.claude.json"))


def claude_json_settings_read(claude_json: pathlib.Path) -> dict:
    """Return claude_json's settings, or {} when the file does not exist."""
    if not claude_json.exists():
        return {}
    # A file that is not UTF-8 raises UnicodeDecodeError, a ValueError, so it is
    # reported like any other file that is not valid JSON.
    try:
        settings = json.loads(claude_json.read_text(encoding="utf-8"))
    except ValueError as error:
        raise ClaudeJsonNotValidJsonError(
            f"{claude_json} is not valid JSON ({error})") from error
    if not isinstance(settings, dict):
        raise ClaudeJsonNotAJsonObjectError(
            f"{claude_json} holds a JSON {JSON_TYPE_NAME_BY_PYTHON_TYPE[type(settings)]}, "
            "not an object")
    return settings


def onboarding_presets_set(settings: dict) -> bool:
    """Set the onboarding presets in settings; return True if anything changed."""
    changed = False
    if settings.get("hasCompletedOnboarding") is not True:
        settings["hasCompletedOnboarding"] = True
        changed = True
    if "theme" not in settings:
        settings["theme"] = THEME_SET_WHEN_NONE_IS_SET
        changed = True
    return changed


def claude_json_settings_replace(claude_json: pathlib.Path, settings: dict) -> None:
    # Running agent-sessions write this file too, so it is replaced, never truncated:
    # a reader sees the whole old file or the whole new one. The temporary file sits in
    # the target's own directory because os.replace is atomic only within one filesystem,
    # and its name is unique because two launches can overlap.
    # Path.write_text raises when the write fails; a plain open().write() can lose that
    # error at deallocation and then publish an empty file.
    # os.replace keeps the temporary file's mode, so the target's mode is carried over;
    # a new file is 0600 because it holds credentials.
    # Not fixed: a write by an agent-session between the read and the replace is lost.
    mode = claude_json.stat().st_mode & 0o777 if claude_json.exists() else 0o600
    handle, temporary = tempfile.mkstemp(dir=str(claude_json.parent),
                                         prefix=TEMPORARY_FILE_PREFIX,
                                         suffix=TEMPORARY_FILE_SUFFIX)
    os.close(handle)
    pathlib.Path(temporary).write_text(json.dumps(settings, indent=2), encoding="utf-8")
    os.chmod(temporary, mode)
    os.replace(temporary, claude_json)


def claude_json_agent_seat_folder_trust_and_onboarding_presets_write(
        claude_json: pathlib.Path, agent_seat_folder: str) -> bool:
    """Write the presets into claude_json; return True if the file was written."""
    settings = claude_json_settings_read(claude_json)
    folder = os.path.abspath(os.path.expanduser(agent_seat_folder))
    project = settings.setdefault("projects", {}).setdefault(folder, {})
    changed = False
    if project.get("hasTrustDialogAccepted") is not True:
        project["hasTrustDialogAccepted"] = True
        changed = True
    changed = onboarding_presets_set(settings) or changed
    if not changed:
        return False
    claude_json_settings_replace(claude_json, settings)
    return True


def claude_json_onboarding_presets_write(claude_json: pathlib.Path) -> bool:
    """Write only the onboarding and theme presets, no folder trust; return True if written."""
    settings = claude_json_settings_read(claude_json)
    if not onboarding_presets_set(settings):
        return False
    claude_json_settings_replace(claude_json, settings)
    return True


def claude_json_presets_failure_remedy(error: Exception, claude_json: pathlib.Path,
                                       run_again: str = "") -> str:
    """The one remedy that fits the failure the presets write raised.

    run_again, such as "launch again", is added to each instruction as
    "; after that, <run_again>"; a caller that has nothing to run again passes nothing.
    """
    then = f"; after that, {run_again}" if run_again else ""
    backups = claude_json.parent / ".claude" / "backups"
    if isinstance(error, ClaudeJsonNotValidJsonError):
        wanted = "is valid JSON"
    elif isinstance(error, ClaudeJsonNotAJsonObjectError):
        wanted = "holds a JSON object"
    else:
        # The write makes a temporary file beside claude_json and replaces claude_json
        # with it, so both the file and its folder must be writable.
        return (f"Fix the cause named above{then}. For a permission error, make {claude_json} "
                f"and its folder {claude_json.parent}/ writable by the account this program "
                f"runs as; for a full disk, free space on the disk that holds {claude_json}.")
    return (f"{claude_json} holds the Claude Code login, so the user restores or moves it; "
            "an agent that reads this tells the user and does not replace the file.\n"
            f"The user restores {claude_json} from the newest copy in {backups}/ that {wanted}{then}.\n"
            f"If no copy in {backups}/ {wanted}, the user moves {claude_json} aside, such as to "
            f"{claude_json}.unreadable{then}. The next launch writes a new {claude_json}, "
            "and the user may have to log in to Claude Code again.")


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
              f"{path} was left unchanged, and no agent-session was started, because one "
              "started without these presets could stop unattended at Claude Code's "
              "folder-trust dialog or onboarding screens.\n"
              + claude_json_presets_failure_remedy(error, path, "launch again"),
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
