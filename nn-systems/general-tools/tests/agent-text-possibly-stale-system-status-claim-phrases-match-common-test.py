#!/usr/bin/env python3
"""Tests for nn-systems/general-tools/agent-text-possibly-stale-system-status-claim-phrases-match-common.py.

Run: python3 nn-systems/general-tools/tests/agent-text-possibly-stale-system-status-claim-phrases-match-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

_spec = importlib.util.spec_from_file_location(
    "agent_text_possibly_stale_system_status_claim_phrases_match_common",
    REPOSITORY_ROOT / "nn-systems" / "general-tools"
    / "agent-text-possibly-stale-system-status-claim-phrases-match-common.py")
claims = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(claims)

failures = 0


def check(name, condition, detail=""):
    global failures
    print(("PASS " if condition else "FAIL ") + name + ("" if condition else f": {detail!r}"))
    if not condition:
        failures += 1


# Sentences agents wrote that the user corrected, each with the pattern that must catch it.
CAUGHT = [
    ("offline", "Task #421, \"Tell cold-read-research which held branches ned-box-helper deleted\", is still on hold "
                "because cold-read-research is offline."),
    ("offline", "Every cold-read-research session on your Mac is offline, so I couldn't message it directly."),
    ("back online", "The promise to message cold-read-research once it's back online is on my task list as task #421."),
    ("none running", "I tried messaging cold-read-research again just now. None of its sessions is live; the most "
                     "recent was last active 8 days ago."),
    ("none running", "No agent is running in any of them, so they aren't causing the error."),
    ("logged out", "The sixth failed because **`claude` is logged out on the Mac**."),
    ("logged in to an account", "I'm back, and that also explains your missing sessions: **your machines are logged "
                                "in to two different Claude accounts.**"),
    ("still broken", "As far as I can find, the name-check agent is still broken on ned-box:"),
    ("still waiting", "Tasks #743 and #748 are still waiting on reboot-test and on cold-read-research."),
    ("stopped", "The crontab is empty apart from one commented line, so every scheduled job on ned-box is gone, not "
                "only the dialogs refresh."),
    ("stopped", "The session dialogs stopped updating at **22:10 last night**, and that's on purpose."),
    ("down", "First action: re-arm the three watchers, which are down right now."),
    ("unreachable", "ned-box is unreachable from the Mac, so I left the step for later."),
    ("unreachable", "Still looking at why the drive won't mount; I'm reading the system log now."),
    ("not running", "The handoff-supervisor of merge-lane-2 is not running."),
]
for expected, sentence in CAUGHT:
    found = claims.possibly_stale_system_status_claim_phrases_find(sentence)
    check(f"caught as {expected}: {sentence[:60]}", expected in [name for name, _ in found], found)

# What agents say while they work, and sentences that name a status without claiming it now.
NOT_CAUGHT = [
    "The tests are still running.",
    "I started the test suites; they are running now.",
    "I wrote the report to docs/walk/report.md.",
    "The walk is still waiting on item 3.1.",
    "I'm still waiting for your answer on whether to resume the walk.",
    "Item 1 of 9 is on hold until you've read the rewrite.",
    "The rename subagent is still waiting for its test run to finish.",
    "If ned-box is down, the hook skips the search.",
    "The cost is about 25 seconds, only while ned-box is down.",
    "A daily check lists the worktrees of any agent-seat whose handoff-supervisor is not running.",
    "The count is down to 3 failures.",
    "Write down the command you ran.",
    "The sweep stopped partway, but its list was saved.",
    "Python can't reach the artifact tool, since it is part of Claude Code.",
    "The six tasks will come back up when the pull request merges.",
    "The hook prints `ned-box is unreachable` when ssh fails.",
    "> cold-read-research is offline",
    "The message said \"claude is logged out\" in its first line.",
    "It is not running the right command.",
]
for sentence in NOT_CAUGHT:
    found = claims.possibly_stale_system_status_claim_phrases_find(sentence)
    check(f"not caught: {sentence[:60]}", found == [], found)

found = claims.possibly_stale_system_status_claim_phrases_find(
    "ned-box is down.\nAnd cold-read-research is offline.")
check("matches come back in text order with their phrases",
      found == [("down", "is down"), ("offline", "offline")], found)

print(f"{'FAILED' if failures else 'OK'}: {failures} failure(s)")
sys.exit(1 if failures else 0)
