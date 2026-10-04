#!/usr/bin/env python3
"""Print the status line from the harness's JSON payload on stdin.

Configure as the statusLine command in settings.json. Missing or malformed
fields omit their segments: a rendering fault must not blank the whole line.
"""

# Defer annotations so Path | None does not fail at import on Python 3.9.
from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Spaces and color separate segments without spending width on dividers.
SEPARATOR = "  "

RESET = "\033[00m"
GREEN_BOLD = "\033[01;32m"
BLUE_BOLD = "\033[01;34m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RED_BOLD = "\033[01;31m"

# Warn shortly before the handoff trigger at roughly half the context used.
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


def working_directory_name(working_directory: str) -> str:
    # Full paths crowd model and quota segments out of narrow panes.
    if not working_directory:
        return ""
    path = Path(working_directory)
    if path == Path.home():
        return "~"
    return path.name or working_directory


def git_head_file(working_directory: Path) -> Path | None:
    """Locate the governing HEAD file, including worktree .git indirection."""
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


def freshness_suffix(working_directory: str) -> str:
    """Return the behind-count suffix from the freshness stamp, marking failed fetches with ?."""
    # The Stop hook writes the stamp; rendering the status line must not fetch.
    if not working_directory:
        return ""
    head_file = git_head_file(Path(working_directory))
    if head_file is None:
        return ""
    try:
        stamp = json.loads((head_file.parent / "checkout-freshness-stamp.json")
                           .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    behind = stamp.get("behind")
    doubt = not stamp.get("fetch_ok", True)
    if isinstance(behind, int) and behind > 0:
        return f"⇣{behind}{'?' if doubt else ''}"
    if doubt:
        # A failed fetch makes even a zero behind-count stale; show the uncertainty.
        return "⇣?"
    return ""


def location_segment(working_directory: str) -> str:
    host = os.uname().nodename.split(".")[0]

    pieces = []
    if host:
        pieces.append(colored(host, GREEN_BOLD))
    if working_directory:
        prefix = ":" if pieces else ""
        pieces.append(prefix + colored(working_directory_name(working_directory), BLUE_BOLD))
    freshness = freshness_suffix(working_directory)
    if freshness:
        pieces.append(" " + colored(freshness, RED_BOLD))
    return "".join(pieces)


def agent_segment(payload: dict) -> str:
    return str(payload.get("agent", {}).get("name", "") or "")


def model_segment(payload: dict) -> str:
    model = payload.get("model", {}).get("display_name", "")
    effort = payload.get("effort", {}).get("level", "")
    return " · ".join(str(part) for part in (model, effort) if part)


def time_until(reset_timestamp: str | int | float) -> str:
    """Return a coarse countdown to a quota reset."""
    # resets_at is epoch seconds. Do not parse numeric strings as seconds: an ISO year is ambiguous.
    if isinstance(reset_timestamp, bool):
        return ""
    if isinstance(reset_timestamp, (int, float)):
        try:
            resets_at = datetime.fromtimestamp(reset_timestamp, timezone.utc)
        except (OSError, OverflowError, ValueError):
            return ""
    else:
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
    """Return remaining context and quota percentages with reset countdowns."""
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
    """Return a backup warning, or an empty string when healthy or unavailable."""
    # Place the warning first so truncation cannot hide it; checker failures must not blank the line.
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
    except Exception:  # noqa: BLE001 - a checker failure must not blank the status line
        return ""


def status_line_text(payload: dict) -> str:
    working_directory = payload.get("workspace", {}).get("current_dir") or payload.get("cwd", "")
    segments = [
        backup_health_segment(),
        location_segment(working_directory),
        agent_segment(payload),
        model_segment(payload),
        consumption_segment(payload),
    ]
    return SEPARATOR.join(segment for segment in segments if segment)


PAYLOAD_CAPTURE_VARIABLE = "NEDSCHORUS_STATUSLINE_PAYLOAD_CAPTURE"


def capture_payload(payload: dict) -> None:
    """Capture a live harness payload when the diagnostic environment variable is set."""
    # Fixtures cannot verify their own assumptions about harness field types; the canary needs live data.
    destination = os.environ.get(PAYLOAD_CAPTURE_VARIABLE)
    if not destination:
        return
    try:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    except (OSError, TypeError, ValueError):
        return


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            payload = {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = {}

    capture_payload(payload)

    try:
        print(status_line_text(payload))
    except Exception:  # noqa: BLE001 - no rendering fault may blank the line
        print(payload.get("model", {}).get("display_name", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
