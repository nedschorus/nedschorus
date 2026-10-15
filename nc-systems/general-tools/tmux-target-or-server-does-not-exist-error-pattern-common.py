#!/usr/bin/env python3
"""Tell tmux's "that session or server does not exist" answers from its other failures.

A tmux probe that exits nonzero either answered "no such target here" or could
not answer at all, such as a client and server of different tmux versions. A
program that reads every failure as "absent" acts on an answer tmux never gave.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "tmux_target_or_server_does_not_exist_error_pattern_common", <path>)
"""

import re

# What tmux 3.6 prints when the target is absent: another session or window holds the
# server ("can't find session", "can't find window", "can't find pane"), the server holds
# none ("no current target", from has-session; display-message -p exits 0 and prints
# nothing there), the socket refuses ("no server running"), or no socket file.
# Each pair is the wording an agent is shown and the regex that matches it; messages that
# list these answers take them from here, so the list and the pattern cannot drift.
TMUX_TARGET_OR_SERVER_DOES_NOT_EXIST_ERROR_WORDINGS = (
    ("can't find session", r"can't find session"),
    ("can't find window", r"can't find window"),
    ("can't find pane", r"can't find pane"),
    ("no current target", r"no current target"),
    ("no server running", r"no server running"),
    ("error connecting to ... (No such file or directory)",
     r"error connecting to .*\(No such file or directory\)"),
)
TMUX_TARGET_OR_SERVER_DOES_NOT_EXIST_ERROR_PATTERN = re.compile(
    "|".join(regex for _, regex in TMUX_TARGET_OR_SERVER_DOES_NOT_EXIST_ERROR_WORDINGS))

def tmux_error_text_says_target_or_server_does_not_exist(tmux_error_text):
    """Return True when tmux's error text says the target or its server does not exist."""
    return bool(TMUX_TARGET_OR_SERVER_DOES_NOT_EXIST_ERROR_PATTERN.search(tmux_error_text or ""))
