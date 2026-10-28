#!/usr/bin/env python3
"""Write, claim and release the user's alerts: one JSON file per alert under ~/.local/state/nedschorus/user-alerts/
on ned-box, the home directory read from HOME when each function runs.

A program that must tell the user something calls user_alert_write_to_pending, which writes the alert into
being-written/ and renames it into pending/, so no reader sees half a file. The alert holds `id`, `written_at` (UTC,
ISO 8601), `title`, `alert_text`, and `action`: what an agent on ned-box can do about it, or that only the
user can act, and where.

The walk-me-through UserPromptSubmit hook, on each prompt the user types into a ned-box agent-session, first
calls user_alerts_claimed_delete_if_recorded_in_approval_walk_minutes_else_release_to_pending_after_30_minutes, then user_alerts_claim_every_pending_by_rename_into_claimed, so an alert
it returns to pending/ is claimed again by the same prompt. A claim is an os.rename into claimed/, which
succeeds for one caller only, so each alert goes to one agent-session. The claim sets the file's modification
time to the claim time, because a rename keeps the old one, and that time is what the 30-minute limit reads.

Failures: a file another agent-session moved first is skipped, never an error. A pending or claimed file that
is not a JSON object raises ValueError, and any other OSError is raised, to the caller, which reports it.
"""
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

USER_ALERTS_RELATIVE_TO_HOME = Path(".local") / "state" / "nedschorus" / "user-alerts"
CLAIM_LIMIT_SECONDS = 30 * 60
USER_ALERT_LINE = re.compile(r"#user_alert\s+(\S+)")
# Walk-minutes on ned-box, relative to the home directory: closed ones in the log-store, open ones under
# docs/walk/ of each checkout, which are agent-homes, the worktrees beside or inside them, and the
# reference-checkout and its worktrees.
WALK_MINUTES_PATTERNS = (
    "nedschorus-logs/walk/*-minutes.md",
    "agents/*/docs/walk/*-minutes.md",
    "agents/*/*/docs/walk/*-minutes.md",
    "agents/*/.claude/worktrees/*/docs/walk/*-minutes.md",
    "Projects/nedschorus/docs/walk/*-minutes.md",
    "Projects/nedschorus/.claude/worktrees/*/docs/walk/*-minutes.md",
)


def user_alerts_directory():
    return Path.home() / USER_ALERTS_RELATIVE_TO_HOME


def user_alert_write_to_pending(title, alert_text, action, now=None):
    """Write one alert into pending/ and return its id."""
    now = now or datetime.now(timezone.utc)
    directory = user_alerts_directory()
    alert_id = f"{now.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    alert = {"id": alert_id, "written_at": now.isoformat(timespec="seconds"), "title": title,
             "alert_text": alert_text, "action": action}
    being_written, pending = directory / "being-written", directory / "pending"
    being_written.mkdir(parents=True, exist_ok=True)
    pending.mkdir(parents=True, exist_ok=True)
    written = being_written / f"{alert_id}.json"
    written.write_text(json.dumps(alert, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.rename(written, pending / written.name)
    return alert_id


def user_alert_read_from_json_file(path):
    alert = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(alert, dict):
        raise ValueError(f"{path} holds no JSON object")
    return alert


def user_alerts_claim_every_pending_by_rename_into_claimed(now=None):
    """Move every alert in pending/ into claimed/, and return the alerts this call claimed, oldest first."""
    directory = user_alerts_directory()
    pending, claimed = directory / "pending", directory / "claimed"
    if not pending.is_dir():
        return []
    claim_time = (now or datetime.now(timezone.utc)).timestamp()
    alerts = []
    for path in sorted(pending.glob("*.json")):
        claimed.mkdir(parents=True, exist_ok=True)
        target = claimed / path.name
        try:
            os.rename(path, target)
            os.utime(target, (claim_time, claim_time))
            alerts.append(user_alert_read_from_json_file(target))
        except FileNotFoundError:
            # Another agent-session claimed it first, or returned it to pending/ in the moment after the rename.
            continue
    return alerts


def walk_minutes_files(home):
    return [path for pattern in WALK_MINUTES_PATTERNS for path in sorted(Path(home).glob(pattern))]


def user_alert_ids_named_in_walk_minutes(home):
    """Every id a `#user_alert <id>` line names in any walk-minutes on ned-box."""
    ids = set()
    for path in walk_minutes_files(home):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            # A worktree removed while this ran.
            continue
        if "#user_alert" in text:
            ids.update(USER_ALERT_LINE.findall(text))
    return ids


def user_alerts_claimed_delete_if_recorded_in_approval_walk_minutes_else_release_to_pending_after_30_minutes(now=None):
    """Delete every claimed alert some walk-minutes name, and move back to pending/ every other claimed alert
    claimed more than CLAIM_LIMIT_SECONDS ago. The walk-minutes are read only when some claimed alert is older
    than that, so a prompt costs two directory listings while alerts are fresh or absent."""
    directory = user_alerts_directory()
    claimed = directory / "claimed"
    if not claimed.is_dir():
        return
    now_seconds = (now or datetime.now(timezone.utc)).timestamp()
    old = []
    for path in sorted(claimed.glob("*.json")):
        try:
            if now_seconds - path.stat().st_mtime > CLAIM_LIMIT_SECONDS:
                old.append(path)
        except FileNotFoundError:
            continue
    if not old:
        return
    recorded = user_alert_ids_named_in_walk_minutes(Path.home())
    (directory / "pending").mkdir(parents=True, exist_ok=True)
    for path in old:
        try:
            if path.stem in recorded:
                path.unlink()
            else:
                os.rename(path, directory / "pending" / path.name)
        except FileNotFoundError:
            # Another agent-session's prompt moved or deleted it first.
            continue
