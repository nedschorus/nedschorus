#!/usr/bin/env python3
"""The first words of every headless `claude -p` command line a program here runs.

A `claude -p` session loads the claude.ai connectors of the account it is
logged in to, such as Gmail, Google Drive and Google Calendar, whatever
--tools, --allowedTools or --permission-mode say; only --strict-mcp-config
keeps them out. A connector call such as sending an email or sharing a file
cannot be undone. A session given no --permission-mode takes the user's
default, which on ned-box is bypassPermissions. The user-wide
~/.claude/settings.json turns the advisor tool on, and a session started with
--settings '{"advisorModel": ""}' has none.

So every program that starts `claude -p` begins its command line with
claude_code_headless_run_command_line_prefix_build(), which names the permission
mode the caller chose and carries the caller's own settings in its one
--settings, and appends its own flags after it, never a --settings of its own.
nc-systems/general-tools/tests/claude-code-headless-run-every-launch-uses-common-command-line-prefix-test.py
fails when a program writes out a `claude -p` command line of its own, passes
bypassPermissions, or adds a --settings after the prefix.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "claude_code_headless_run_command_line_prefix_with_no_connectors_and_explicit_permission_mode_common", <path>)
"""

import json

CLAUDE_CODE_PROGRAM = "claude"
CLAUDE_CODE_SETTINGS_THAT_TURN_THE_ADVISOR_TOOL_OFF = {"advisorModel": ""}


def claude_code_headless_run_command_line_prefix_build(permission_mode, program=CLAUDE_CODE_PROGRAM,
                                                       caller_claude_code_session_settings=None):
    """Return [program, "-p", "--strict-mcp-config", "--permission-mode", permission_mode,
    "--settings", <caller_claude_code_session_settings as JSON, with the advisor turned off>].

    The advisor setting wins over an advisorModel in caller_claude_code_session_settings,
    which is left unchanged.
    "-p" stays second, so a caller may put its prompt straight after the returned list.
    """
    return [program, "-p", "--strict-mcp-config", "--permission-mode", permission_mode,
            "--settings", json.dumps({**(caller_claude_code_session_settings or {}),
                                      **CLAUDE_CODE_SETTINGS_THAT_TURN_THE_ADVISOR_TOOL_OFF})]
