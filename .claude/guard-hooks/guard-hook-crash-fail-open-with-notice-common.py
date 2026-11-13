#!/usr/bin/env python3
"""Let a PreToolUse guard that crashes let the tool call go ahead, telling the agent and the user.

A guard that stops on an exception nothing caught exits 1, which shows the user one line and
the agent nothing, while the call goes ahead anyway. A guard wraps its module-level loads and
its main() in guard_hook_crash_fail_open_with_notice_context_manager, so that the call still
goes ahead, and the agent, in additionalContext, and the user, in systemMessage, are told which
guard crashed, with what exception, and that the call went ahead unchecked.

Only the Python standard library is used here, because a guard loads this module before
anything else, and a failure to load this module is the one crash a guard cannot report.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "guard_hook_crash_fail_open_with_notice_common", <path>)
"""

import contextlib
import json
import socket
import sys
import traceback
from pathlib import Path


def guard_hook_crash_notice_hook_output_json_text(guard_file, error):
    """Return the PreToolUse JSON that lets the call go ahead and says the guard crashed."""
    guard_name = Path(guard_file).name
    host = socket.gethostname().split(".")[0]
    # Frames inside importlib say nothing about which file to fix.
    frames = [frame for frame in traceback.extract_tb(error.__traceback__)
              if not frame.filename.startswith("<frozen")]
    place = f", at {Path(frames[-1].filename).name}:{frames[-1].lineno}" if frames else ""
    crash = f"{type(error).__name__}: {error}{place}"
    agent_notice = (
        f"The guard hook {guard_name} crashed on {host} ({crash}), so this tool call went ahead "
        f"without being checked, and the call has run. A crashed guard lets the call go ahead "
        f"so that the crash does not stop work; the user has been shown that the guard crashed.\n"
        f"Check, from the call's input and its result, whether the call did what {guard_name} "
        f"exists to stop; the docstring at the top of {guard_file} says what that is.\n"
        f"If the call did, or you cannot tell, tell the user what the call did, or, if you are a "
        f"subagent, tell the agent that dispatched you; do not undo the call before that answer "
        f"comes, because an undo can do further damage.\n"
        f"If the call did not, go on with your task.")
    user_notice = (
        f"The guard hook {guard_name} crashed on {host} and let a tool call through unchecked "
        f"({crash}). The agent has been told to check what the call did.")
    return json.dumps({
        "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": agent_notice},
        "systemMessage": user_notice,
    })


@contextlib.contextmanager
def guard_hook_crash_fail_open_with_notice_context_manager(guard_file, running_as_hook):
    """On an Exception inside the block, print the crash notice and exit 0 when running_as_hook.

    running_as_hook is the guard's `__name__ == "__main__"`. When it is false, as when a test
    imports the guard, the exception is raised unchanged, so a crash fails the test instead of
    exiting 0. SystemExit is not an Exception, so a guard's own exit, a refusal's 2 included,
    passes through unchanged.
    """
    try:
        yield
    except Exception as error:
        if not running_as_hook:
            raise
        print(guard_hook_crash_notice_hook_output_json_text(guard_file, error))
        sys.exit(0)
