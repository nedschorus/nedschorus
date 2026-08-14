#!/usr/bin/env python3
"""Print the status line.

Wire it as the statusLine command in settings.json. The harness pipes one
JSON object on stdin at every refresh.

(Until 2026-08-12 this script was also half of the handoff auto-trigger,
relaying the context percentage to a side file for the Stop hook — cut when
the hook moved to reading the transcript, which covers every session type;
see handoff-context-threshold-hook.py.)

A malformed or unexpected payload never breaks the status line: the script
prints what it can and exits 0, because a broken status line is worse than
none, and the next refresh is a second away. Every field below is optional
in that same spirit — a payload missing one drops that segment rather than
failing.

The visible line, left to right (user-walked 2026-08-08):

  ned-box:~/agents/choirmaster (choirmaster) │ Opus 5 · high │ 46% 2h 77% 3d 89%

  host         green — which machine this session runs on. The user drives
               from a Mac over SSH while the agents run here, so the box name
               is the one thing a pane cannot be assumed to share.
  path         blue, home abbreviated to ~. One agent, one worktree, so
               several panes differ mainly by this.
  (branch)     read out of .git/HEAD directly, no subprocess. Redundant with
               the directory name today; not redundant on a detached HEAD or
               a slice branch, where committing to the wrong branch is silent.
  agent        agent.name, present only for a session launched with
               --agent <name>; absent for an ordinary session.
  model        model.display_name
  effort       effort.level
  the numbers  five values, all REMAINING, in one block:
                 <context>% <5h-time-left> <5h>% <7d-time-left> <7d>%
               Quota remaining is 100 - rate_limits.*.used_percentage; the
               times count down to each window's resets_at.

The three percentages are colored by how much is left, so a line that needs
attention looks different from one that does not.

Deliberately not shown, having been weighed and dropped: username (identical
in every pane), cost and lines changed, thinking (on unless deliberately
disabled, so it renders as a constant), fast mode, output style, session
name, and the worktree and pull-request fields.

Payload fields are those of Claude Code 2.1.220 and 2.1.226, read from the
binary's status line builder rather than from documentation.
"""

import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SEPARATOR = " │ "

RESET = "\033[00m"
GREEN_BOLD = "\033[01;32m"
BLUE_BOLD = "\033[01;34m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RED_BOLD = "\033[01;31m"

# Thresholds on how much is LEFT — of the context window, or of a quota
# window. The handoff fires at roughly half the context used, so the first
# warning arrives a little before the trigger rather than with it.
COMFORTABLE_REMAINING_PERCENT = 55.0
TIGHT_REMAINING_PERCENT = 25.0

SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400


def colored(text: str, color: str) -> str:
    return f"{color}{text}{RESET}"


def color_for_remaining(remaining_percent: float) -> str:
    if remaining_percent >= COMFORTABLE_REMAINING_PERCENT:
        return GREEN
    if remaining_percent >= TIGHT_REMAINING_PERCENT:
        return YELLOW
    return RED


def remaining_percent_text(remaining_percent: float) -> str:
    return colored(f"{remaining_percent:.0f}%", color_for_remaining(remaining_percent))


def abbreviated_path(working_directory: str) -> str:
    """Render the path as a shell prompt does: the home directory as ~."""
    home = str(Path.home())
    if working_directory == home:
        return "~"
    if working_directory.startswith(home + "/"):
        return "~" + working_directory[len(home):]
    return working_directory


def git_head_file(working_directory: Path) -> Path | None:
    """Locate the HEAD file governing this directory, worktrees included.

    A worktree's .git is a file pointing at the real git directory, so the
    branch cannot be read from a fixed relative path.
    """
    for directory in [working_directory, *working_directory.parents]:
        git_path = directory / ".git"
        if git_path.is_dir():
            return git_path / "HEAD"
        if git_path.is_file():
            try:
                pointer = git_path.read_text(encoding="utf-8").strip()
            except OSError:
                return None
            if pointer.startswith("gitdir:"):
                return Path(pointer.split(":", 1)[1].strip()) / "HEAD"
            return None
    return None


def git_branch(working_directory: str) -> str:
    """The current branch, or the short commit id when HEAD is detached."""
    if not working_directory:
        return ""
    head_file = git_head_file(Path(working_directory))
    if head_file is None:
        return ""
    try:
        head = head_file.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    branch_reference = "ref: refs/heads/"
    if head.startswith(branch_reference):
        return head[len(branch_reference):]
    return head[:8]


def location_segment(working_directory: str) -> str:
    """host:path (branch) — where this session is, on which machine."""
    host = os.uname().nodename.split(".")[0]

    pieces = []
    if host:
        pieces.append(colored(host, GREEN_BOLD))
    if working_directory:
        prefix = ":" if pieces else ""
        pieces.append(prefix + colored(abbreviated_path(working_directory), BLUE_BOLD))
    branch = git_branch(working_directory)
    if branch:
        pieces.append(f" ({branch})")
    return "".join(pieces)


def agent_segment(payload: dict) -> str:
    """The named agent type, when the session was launched as one."""
    return str(payload.get("agent", {}).get("name", "") or "")


def model_segment(payload: dict) -> str:
    """Model and effort — the two facts that set what the session costs."""
    model = payload.get("model", {}).get("display_name", "")
    effort = payload.get("effort", {}).get("level", "")
    return " · ".join(str(part) for part in (model, effort) if part)


def time_until(reset_timestamp: str) -> str:
    """Coarse countdown to a quota reset: days, else hours, else minutes."""
    try:
        resets_at = datetime.fromisoformat(reset_timestamp.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return ""
    if resets_at.tzinfo is None:
        resets_at = resets_at.replace(tzinfo=timezone.utc)

    seconds_left = (resets_at - datetime.now(timezone.utc)).total_seconds()
    if seconds_left <= 0:
        return "now"
    if seconds_left >= SECONDS_PER_DAY:
        return f"{int(seconds_left // SECONDS_PER_DAY)}d"
    if seconds_left >= SECONDS_PER_HOUR:
        return f"{int(seconds_left // SECONDS_PER_HOUR)}h"
    return f"{int(seconds_left // SECONDS_PER_MINUTE)}m"


def consumption_segment(payload: dict) -> str:
    """<context>% <5h-left> <5h>% <7d-left> <7d>% — everything remaining."""
    parts = []

    context_remaining = payload.get("context_window", {}).get("remaining_percentage")
    if isinstance(context_remaining, (int, float)):
        parts.append(remaining_percent_text(float(context_remaining)))

    rate_limits = payload.get("rate_limits", {})
    if not isinstance(rate_limits, dict):
        rate_limits = {}
    for key in ("five_hour", "seven_day"):
        window = rate_limits.get(key, {})
        if not isinstance(window, dict):
            continue
        countdown = time_until(window.get("resets_at", ""))
        if countdown:
            parts.append(countdown)
        used = window.get("used_percentage")
        if isinstance(used, (int, float)):
            parts.append(remaining_percent_text(100.0 - float(used)))

    return " ".join(parts)


def backup_health_segment() -> str:
    """Warn when this machine's backups have stopped; empty when they are fine.

    First in the line rather than last, because a line that is truncated or
    wrapped loses its tail, and this is the one segment whose whole purpose is
    to be seen. It appears only when something is wrong, so the jarring change
    of shape is the point.

    Loaded by path because the checker's filename is hyphenated, and lazily so
    that a missing or broken checker costs nothing until the line is rendered.
    Any failure yields an empty segment: a health check that blanks the status
    line would be a worse fault than the one it reports.
    """
    try:
        checker_path = Path(__file__).with_name("backup-health-check.py")
        if not checker_path.exists():
            return ""
        specification = importlib.util.spec_from_file_location(
            "backup_health_check", checker_path)
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        headline, _detail = module.diagnose()
        if not headline:
            return ""
        return colored(f"⚠ {headline}", RED_BOLD)
    except Exception:  # noqa: BLE001 - see docstring
        return ""


def status_line_text(payload: dict) -> str:
    """Compose the visible line; every segment is independently optional."""
    working_directory = payload.get("workspace", {}).get("current_dir") or payload.get("cwd", "")
    segments = [
        backup_health_segment(),
        location_segment(working_directory),
        agent_segment(payload),
        model_segment(payload),
        consumption_segment(payload),
    ]
    return SEPARATOR.join(segment for segment in segments if segment)


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            payload = {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = {}

    try:
        print(status_line_text(payload))
    except Exception:  # noqa: BLE001 - no rendering fault may blank the line
        print(payload.get("model", {}).get("display_name", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
