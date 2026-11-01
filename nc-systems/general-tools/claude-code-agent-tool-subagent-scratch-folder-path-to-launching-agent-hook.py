#!/usr/bin/env python3
"""Tell the agent that launched a subagent where that subagent's scratch folder is.

A PostToolUse hook on the Agent tool. The PreToolUse hook
claude-code-agent-tool-subagent-scratch-folder-make-and-prompt-write-scratch-only-here-line-add-hook.py
makes the folder, appends a line naming it to the subagent's prompt, and records the
folder's path in a file named after the call's tool_use_id; Claude Code gives both hooks
the same tool_use_id for one call. The launching agent never sees the appended line, so
this hook reads the recorded file, deletes it, and returns the path as additionalContext.

When the scratchpad cannot be found, the tool_use_id is unusable, or there is no recorded
file, the PreToolUse hook made no folder or no record and has already said why, so this
hook stays silent. When the recorded file exists but cannot be read or deleted, it prints
why on stderr and exits 1, which Claude Code shows the user.
"""

import importlib.util
import json
import os
import sys
from pathlib import Path

_folder_maker_spec = importlib.util.spec_from_file_location(
    "claude_code_agent_tool_subagent_scratch_folder_make_and_prompt_write_scratch_only_here_line_add_hook",
    Path(__file__).resolve().with_name(
        "claude-code-agent-tool-subagent-scratch-folder-make-and-prompt-write-scratch-only-here-line-add-hook.py"))
folder_maker = importlib.util.module_from_spec(_folder_maker_spec)
_folder_maker_spec.loader.exec_module(folder_maker)

HOOK_NAME = "claude-code-agent-tool-subagent-scratch-folder-path-to-launching-agent-hook"

LAUNCHING_AGENT_FOLDER_PATH_MESSAGE = (
    "The subagent you just launched (description: {description!r}) was told to write its "
    "scratch files only under {folder}. Look there for any file it wrote.")


def main(stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr, environment=os.environ) -> int:
    payload = json.loads(stdin.read() or "{}")
    try:
        scratchpad = folder_maker.session_scratchpad_directory(payload, environment)
        record = folder_maker.recorded_folder_path_file(scratchpad, payload.get("tool_use_id"))
    except (folder_maker.ScratchpadNotFound, ValueError):
        return 0  # The PreToolUse hook failed the same way and has already said so.
    try:
        folder = record.read_text().strip()
        record.unlink()
    except FileNotFoundError:
        return 0
    except OSError as error:
        print(f"{HOOK_NAME}: the agent that launched this subagent is not told where its scratch "
              f"folder is: {error}.", file=stderr)
        return 1
    tool_input = payload.get("tool_input")
    description = tool_input.get("description", "") if isinstance(tool_input, dict) else ""
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": LAUNCHING_AGENT_FOLDER_PATH_MESSAGE.format(description=description, folder=folder)}},
        stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
