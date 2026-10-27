#!/usr/bin/env python3
"""Cases for the shared user-alerts module: writing an alert, claiming it once among concurrent agent-sessions,
and returning or deleting a claimed alert by what the walk-minutes record.

Every case points HOME at a scratch directory, so the user's own alerts and walk-minutes are never touched.
Prints one line per case and exits non-zero if any case fails.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

MODULE_FILE = (Path(__file__).resolve().parents[1]
               / "user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py")
_specification = importlib.util.spec_from_file_location(
    "user_alerts_pending_and_claimed_files_write_claim_release_and_delete_common", MODULE_FILE)
alerts = importlib.util.module_from_spec(_specification)
_specification.loader.exec_module(alerts)

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def fresh_home(root, name):
    home = root / name
    home.mkdir()
    os.environ["HOME"] = str(home)
    return home / ".local/state/nedschorus/user-alerts"


class RenameRacedByAnotherAgentSession:
    """os, except that each rename first finds its source gone, as when another agent-session moved it."""

    def __getattr__(self, name):
        return getattr(os, name)

    @staticmethod
    def rename(source, target):
        raise FileNotFoundError(2, "No such file or directory", str(source))


def claimed_at(directory, alert_id, moment):
    path = directory / "claimed" / f"{alert_id}.json"
    os.utime(path, (moment.timestamp(), moment.timestamp()))
    return path


def run_write_cases(root):
    directory = fresh_home(root, "write")
    alert_id = alerts.user_alert_write_to_pending("merge-lane-2 is down", "notice\n  ssh x", "restart it", now=NOW)
    written = directory / "pending" / f"{alert_id}.json"
    alert = json.loads(written.read_text(encoding="utf-8")) if written.is_file() else {}
    check("an alert is written into pending/ with its id, time, title, notice text and action",
          alert == {"id": alert_id, "written_at": "2026-10-27T12:00:00+00:00", "title": "merge-lane-2 is down",
                    "alert_text": "notice\n  ssh x", "action": "restart it"}, repr(alert))
    check("the alert's id starts with the UTC time it was written",
          alert_id.startswith("20261027T120000Z-"), alert_id)
    check("nothing is left in being-written/, where the file was written before its rename",
          list((directory / "being-written").iterdir()) == [], repr(list((directory / "being-written").iterdir())))


def run_claim_cases(root):
    directory = fresh_home(root, "claim")
    check("with no pending/ directory, nothing is claimed", alerts.user_alerts_claim_every_pending_by_rename_into_claimed(now=NOW) == [])
    first = alerts.user_alert_write_to_pending("one", "text", "act", now=NOW - timedelta(hours=2))
    second = alerts.user_alert_write_to_pending("two", "text", "act", now=NOW - timedelta(hours=1))
    claimed = alerts.user_alerts_claim_every_pending_by_rename_into_claimed(now=NOW)
    check("a claim returns every pending alert, oldest first",
          [alert["id"] for alert in claimed] == [first, second], repr(claimed))
    check("a claim moves each alert from pending/ into claimed/",
          list((directory / "pending").iterdir()) == []
          and sorted(path.stem for path in (directory / "claimed").iterdir()) == [first, second])
    mtime = (directory / "claimed" / f"{first}.json").stat().st_mtime
    check("a claimed alert's modification time is the claim time, not the time it was written",
          mtime == NOW.timestamp(), repr(mtime))
    check("a second claim finds nothing left to claim", alerts.user_alerts_claim_every_pending_by_rename_into_claimed(now=NOW) == [])

    directory = fresh_home(root, "claim-raced")
    alerts.user_alert_write_to_pending("one", "text", "act", now=NOW)
    real_os = alerts.os
    alerts.os = RenameRacedByAnotherAgentSession()
    try:
        raised, claimed = None, None
        try:
            claimed = alerts.user_alerts_claim_every_pending_by_rename_into_claimed(now=NOW)
        except Exception as error:  # noqa: BLE001 - the case checks that nothing escapes
            raised = error
    finally:
        alerts.os = real_os
    check("an alert another agent-session claimed first is skipped, not an error",
          raised is None and claimed == [], repr((raised, claimed)))


CONCURRENT_CLAIMER = """
import importlib.util, json, sys, time
from pathlib import Path
specification = importlib.util.spec_from_file_location("alerts", sys.argv[1])
alerts = importlib.util.module_from_spec(specification)
specification.loader.exec_module(alerts)
while not Path(sys.argv[2]).exists():
    time.sleep(0.001)
print(json.dumps([alert["id"] for alert in alerts.user_alerts_claim_every_pending_by_rename_into_claimed()]))
"""


def run_concurrent_claim_cases(root):
    directory = fresh_home(root, "concurrent")
    alert_ids = [alerts.user_alert_write_to_pending(f"alert {n}", "text", "act") for n in range(20)]
    start = root / "concurrent-start"
    claimers = [subprocess.Popen([sys.executable, "-c", CONCURRENT_CLAIMER, str(MODULE_FILE), str(start)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=dict(os.environ))
                for _ in range(2)]
    start.touch()
    results = [claimer.communicate(timeout=60) for claimer in claimers]
    claimed = [alert_id for output, _ in results for alert_id in json.loads(output or "[]")]
    check("two agent-sessions claiming at once: each alert is claimed by exactly one, and neither fails",
          sorted(claimed) == sorted(alert_ids) and all(claimer.returncode == 0 for claimer in claimers)
          and all(error == "" for _, error in results), repr(results))
    check("after two concurrent claims every alert is in claimed/ once, and none in pending/",
          sorted(path.stem for path in (directory / "claimed").iterdir()) == sorted(alert_ids)
          and list((directory / "pending").iterdir()) == [])


def run_release_cases(root):
    directory = fresh_home(root, "release")
    home = Path(os.environ["HOME"])
    unrecorded = alerts.user_alert_write_to_pending("unrecorded", "text", "act")
    in_open_walk = alerts.user_alert_write_to_pending("open walk", "text", "act")
    in_closed_walk = alerts.user_alert_write_to_pending("closed walk", "text", "act")
    fresh = alerts.user_alert_write_to_pending("fresh", "text", "act")
    alerts.user_alerts_claim_every_pending_by_rename_into_claimed(now=NOW)
    for alert_id in (unrecorded, in_open_walk, in_closed_walk):
        claimed_at(directory, alert_id, NOW - timedelta(minutes=31))
    claimed_at(directory, fresh, NOW - timedelta(minutes=29))
    open_walk = home / "agents/merge-lane-2/docs/walk"
    open_walk.mkdir(parents=True)
    (open_walk / "a-walk-minutes.md").write_text(f"- Re-planned.\n#user_alert {in_open_walk}\n", encoding="utf-8")
    closed_walk = home / "nedschorus-logs/walk"
    closed_walk.mkdir(parents=True)
    (closed_walk / "b-walk-minutes.md").write_text(f"#user_alert {in_closed_walk}\n", encoding="utf-8")
    (closed_walk / "b-walk.md").write_text(f"#user_alert {unrecorded}\n", encoding="utf-8")
    alerts.user_alerts_claimed_delete_if_recorded_in_approval_walk_minutes_else_release_to_pending_after_30_minutes(now=NOW)
    pending = sorted(path.stem for path in (directory / "pending").iterdir())
    claimed = sorted(path.stem for path in (directory / "claimed").iterdir())
    check("a claimed alert no walk-minutes name returns to pending/ after 30 minutes; a walk-document naming it "
          "does not count", pending == [unrecorded], repr(pending))
    check("claimed alerts that open or closed walk-minutes name are deleted, and one claimed under 30 minutes "
          "ago stays", claimed == [fresh], repr(claimed))

    directory = fresh_home(root, "release-raced")
    alert_id = alerts.user_alert_write_to_pending("raced", "text", "act")
    alerts.user_alerts_claim_every_pending_by_rename_into_claimed(now=NOW)
    claimed_at(directory, alert_id, NOW - timedelta(hours=1))
    real_os = alerts.os
    alerts.os = RenameRacedByAnotherAgentSession()
    try:
        raised = None
        try:
            alerts.user_alerts_claimed_delete_if_recorded_in_approval_walk_minutes_else_release_to_pending_after_30_minutes(now=NOW)
        except Exception as error:  # noqa: BLE001 - the case checks that nothing escapes
            raised = error
    finally:
        alerts.os = real_os
    check("a claimed alert another agent-session returned first is skipped, not an error",
          raised is None, repr(raised))

    fresh_home(root, "release-empty")
    check("with no claimed/ directory, releasing does nothing",
          alerts.user_alerts_claimed_delete_if_recorded_in_approval_walk_minutes_else_release_to_pending_after_30_minutes(now=NOW) is None)


with tempfile.TemporaryDirectory() as temporary_directory:
    scratch = Path(temporary_directory)
    run_write_cases(scratch)
    run_claim_cases(scratch)
    run_concurrent_claim_cases(scratch)
    run_release_cases(scratch)

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
