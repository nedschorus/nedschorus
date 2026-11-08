#!/usr/bin/env python3
"""Stub under the old name of the Stop hook
walk-me-through-agent-reply-to-user-not-ending-with-waiting-item-closing-line-refusal-stop-hook.py:
runs that file as __main__, so it reads this process's stdin and argv and its
exit code is this process's.

Claude Code reads its hooks when an agent-session starts, so an agent-session
started before the rename still runs this path; without this file every one of
its replies would be blocked with "can't open file" until it restarts. Delete
this file once no claude process started before the rename remains, on ned-box
and on the Mac.
"""
import runpy
from pathlib import Path

runpy.run_path(
    str(Path(__file__).resolve().parent
        / "walk-me-through-agent-reply-to-user-not-ending-with-waiting-item-closing-line-refusal-stop-hook.py"),
    run_name="__main__")
