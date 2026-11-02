#!/usr/bin/env python3
"""Give every subagent a scratch folder of its own, and tell it in its prompt to write there.

A PreToolUse hook on the Agent tool. Subagents that run at once share their parent
agent-session's scratchpad directory, so two of them can write files of the same name
there and each read the other's. For each Agent call this hook makes a new folder in
the scratchpad, named from the call's `description` as a lowercase hyphenated slug
plus a random suffix, such as `clean-worktrees-extension-k3f9x2ab`, and returns the
call's whole input as `updatedInput` with SCRATCH_FOLDER_PROMPT_LINE appended to its
`prompt`. It also records the folder's path in a file named after the call's
tool_use_id, in RECORDED_FOLDER_PATHS_DIRECTORY_NAME inside the scratchpad, so that
claude-code-agent-tool-subagent-scratch-folder-path-to-launching-agent-hook.py can tell
the launching agent where the folder is.

The output carries no permissionDecision, so the Agent call goes through the same
permission flow as without the hook.

The scratchpad is `<temp root>/claude-<uid>/<project slug>/<session_id>/scratchpad`,
the shape Claude Code uses: the temp root is CLAUDE_CODE_TMPDIR, or the system temp
directory when that is unset, and the project slug is the name of the directory that
holds the payload's transcript_path. The hook uses that path only when
`<temp root>/claude-<uid>` already exists, which shows Claude Code keeps its sessions
under that root; it makes the directories below it when missing, since Claude Code makes
them only on first use, which in a new session comes after the first Agent call.

It does not handle a scratchpad that Claude Code places anywhere else; then it changes
nothing. When it cannot find the scratchpad or make the folder, it lets the Agent call
through unchanged, prints why on stderr and exits 1, which Claude Code shows the user
without blocking the call. When only the record for the second hook cannot be written,
the subagent still gets its folder and its line, the launching agent is not told the
folder's path, and the hook says so on stderr and in a systemMessage, which the user
sees; it exits 0 there, because Claude Code ignores updatedInput from a hook that exits
nonzero. Recorded files are removed by
the second hook; one whose Agent call failed stays in the scratchpad.
"""

import json
import os
import re
import sys
import tempfile
from pathlib import Path

HOOK_NAME = "claude-code-agent-tool-subagent-scratch-folder-make-and-prompt-write-scratch-only-here-line-add-hook"

SCRATCH_FOLDER_PROMPT_LINE = (
    "Write your scratch files, such as a draft pull request description, only under "
    "{folder}, a folder of your own.")

RECORDED_FOLDER_PATHS_DIRECTORY_NAME = ".agent-tool-subagent-scratch-folder-paths-by-tool-use-id"

FOLDER_NAME_WHEN_DESCRIPTION_IS_EMPTY = "subagent"
FOLDER_NAME_SLUG_MAXIMUM_LENGTH = 60

# A tool_use_id becomes a file name, so only these characters are accepted.
TOOL_USE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class ScratchpadNotFound(Exception):
    pass


def session_scratchpad_directory(payload, environment) -> Path:
    """The session's scratchpad directory, made if missing."""
    session_id = payload.get("session_id")
    transcript_path = payload.get("transcript_path")
    if not isinstance(session_id, str) or not session_id or "/" in session_id:
        raise ScratchpadNotFound(f"the hook's input has no usable session_id ({session_id!r})")
    if not isinstance(transcript_path, str) or not transcript_path:
        raise ScratchpadNotFound("the hook's input has no transcript_path, which gives the project slug")
    project_slug = Path(transcript_path).parent.name
    temp_root = environment.get("CLAUDE_CODE_TMPDIR") or tempfile.gettempdir()
    user_temp_directory = Path(temp_root) / f"claude-{os.getuid()}"
    if not user_temp_directory.is_dir():
        raise ScratchpadNotFound(
            f"{user_temp_directory} does not exist, so the session's scratchpad is not where "
            "this hook expects Claude Code to keep it")
    scratchpad = user_temp_directory / project_slug / session_id / "scratchpad"
    try:
        scratchpad.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ScratchpadNotFound(f"could not make {scratchpad}: {error}") from error
    return scratchpad


def folder_name_slug(description) -> str:
    text = description if isinstance(description, str) else ""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = slug[:FOLDER_NAME_SLUG_MAXIMUM_LENGTH].rstrip("-")
    return slug or FOLDER_NAME_WHEN_DESCRIPTION_IS_EMPTY


def recorded_folder_path_file(scratchpad: Path, tool_use_id) -> Path:
    if not isinstance(tool_use_id, str) or not TOOL_USE_ID_PATTERN.match(tool_use_id):
        raise ValueError(f"the hook's input has no usable tool_use_id ({tool_use_id!r})")
    return scratchpad / RECORDED_FOLDER_PATHS_DIRECTORY_NAME / tool_use_id


def main(stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr, environment=os.environ) -> int:
    payload = json.loads(stdin.read() or "{}")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        print(f"{HOOK_NAME}: the Agent call's tool_input is not an object, so no scratch folder "
              "was made and the call goes ahead unchanged.", file=stderr)
        return 1
    try:
        scratchpad = session_scratchpad_directory(payload, environment)
        folder = Path(tempfile.mkdtemp(prefix=folder_name_slug(tool_input.get("description")) + "-",
                                       dir=scratchpad))
    except (ScratchpadNotFound, OSError) as error:
        print(f"{HOOK_NAME}: no scratch folder was made for this subagent, and the Agent call goes "
              f"ahead unchanged: {error}.", file=stderr)
        return 1

    updated_input = dict(tool_input)
    prompt = updated_input.get("prompt")
    prompt = prompt if isinstance(prompt, str) else ""
    updated_input["prompt"] = prompt + "\n\n" + SCRATCH_FOLDER_PROMPT_LINE.format(folder=folder)
    output = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": updated_input}}

    try:
        record = recorded_folder_path_file(scratchpad, payload.get("tool_use_id"))
        record.parent.mkdir(exist_ok=True)
        record.write_text(str(folder))
    except (ValueError, OSError) as error:
        note = (f"{HOOK_NAME}: the subagent was given the scratch folder {folder}, but the agent "
                f"that launched it will not be told the path: {error}.")
        print(note, file=stderr)
        output["systemMessage"] = note
    json.dump(output, stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
