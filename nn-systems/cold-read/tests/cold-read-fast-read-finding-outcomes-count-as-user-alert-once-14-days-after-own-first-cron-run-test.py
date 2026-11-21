#!/usr/bin/env python3
"""Cases for nn-systems/cold-read/cold-read-fast-read-finding-outcomes-count-as-user-alert-once-14-days-after-own-first-cron-run.py,
each run as a subprocess with a scratch HOME, so its state and the user-alerts it writes stay in the scratch
directory: the first run starts the 14 days; a run before they pass waits; the run after writes the count as one
user-alert and every later run writes none; and each failure, a count that cannot be made, a state file that cannot
be read, an alert that cannot be written and a state file that cannot be written after it, exits 1.

Run: python3 nn-systems/cold-read/tests/cold-read-fast-read-finding-outcomes-count-as-user-alert-once-14-days-after-own-first-cron-run-test.py
Prints one line per case and exits non-zero if any case fails.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

JOB_NAME = "cold-read-fast-read-finding-outcomes-count-as-user-alert-once-14-days-after-own-first-cron-run"
PROGRAM = Path(__file__).resolve().parents[1] / f"{JOB_NAME}.py"
FIRST_RUN = "2026-12-01T08:15:00+00:00"
THIRTEEN_DAYS_LATER = "2026-12-14T08:15:00+00:00"
FOURTEEN_DAYS_LATER = "2026-12-15T08:15:00+00:00"

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def described(result):
    return f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}"


def run(home, now, records):
    return subprocess.run([sys.executable, str(PROGRAM), "--now", now, "--cold-read-records", str(records)],
                          capture_output=True, text=True, env=dict(os.environ, HOME=str(home)))


def state(home):
    return home / ".local" / "state" / "nedsnodes" / JOB_NAME


def pending_alerts(home):
    pending = home / ".local" / "state" / "nedsnodes" / "user-alerts" / "pending"
    return [json.loads(path.read_text()) for path in sorted(pending.glob("*.json"))] if pending.is_dir() else []


with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)
    records = scratch / "cold-read-records"
    (records / "a-2026-12-02").mkdir(parents=True)
    (records / "a-2026-12-02" / "cold-read-fast-read.md").write_text("## Question 2: Where you struggled\n\n1. x\n")
    (records / "a-2026-12-02" / "cold-read-fast-read-finding-outcomes.json").write_text(json.dumps(
        {"findings": [{"finding": "Q2.1", "question": 2, "number": 1, "outcome": "applied"}]}))

    home = scratch / "home"
    first = run(home, FIRST_RUN, records)
    check("the first run records its time, says when the count is due, writes no alert, and exits 0",
          first.returncode == 0 and "the count is made 14 days from now, 2026-12-15" in first.stdout
          and json.loads((state(home) / "first-run.json").read_text())["first_run"] == FIRST_RUN
          and pending_alerts(home) == [], described(first))
    waiting = run(home, THIRTEEN_DAYS_LATER, records)
    check("a run before the 14 days have passed waits, writing no alert",
          waiting.returncode == 0 and "Waiting: the count is made on 2026-12-15." in waiting.stdout
          and pending_alerts(home) == [], described(waiting))
    due = run(home, FOURTEEN_DAYS_LATER, records)
    alerts = pending_alerts(home)
    check("the run once 14 days have passed writes the count's table as one user-alert, whose action asks for "
          "this job's removal, records that it did, and exits 0",
          due.returncode == 0 and len(alerts) == 1
          and alerts[0]["title"] == ("How often agents applied each cold-read-fast-read question's findings, "
                                     "over two weeks")
          and "| Question 2, Where you struggled | 1 | 0 | 100% |" in alerts[0]["alert_text"]
          and f"remove the job {JOB_NAME}" in alerts[0]["action"]
          and json.loads((state(home) / "user-alert-written.json").read_text())["user_alert_id"] == alerts[0]["id"],
          described(due))
    later = run(home, "2026-12-16T08:15:00+00:00", records)
    check("every later run writes no alert and says the count's alert was written before",
          later.returncode == 0 and len(pending_alerts(home)) == 1 and "was written before" in later.stdout,
          described(later))

    home = scratch / "home-count-fails"
    run(home, FIRST_RUN, records)
    failed = run(home, FOURTEEN_DAYS_LATER, scratch / "no-such-records")
    alerts = pending_alerts(home)
    check("a count that cannot be made writes a user-alert saying so, records no count, and exits 1, so the next "
          "run tries again",
          failed.returncode == 1 and len(alerts) == 1
          and alerts[0]["title"] == "The two-week count of cold-read-fast-read finding outcomes could not be made"
          and "cannot be listed" in alerts[0]["alert_text"]
          and not (state(home) / "user-alert-written.json").exists(), described(failed))

    home = scratch / "home-count-fails-and-alert-unwritable"
    run(home, FIRST_RUN, records)
    (home / ".local" / "state" / "nedsnodes" / "user-alerts").write_text("a file where the folder should be")
    neither = run(home, FOURTEEN_DAYS_LATER, scratch / "no-such-records")
    check("a count that cannot be made, whose alert cannot be written either, says both on stderr, exit 1",
          neither.returncode == 1 and "No finding outcomes were counted" in neither.stderr
          and "The user-alert saying so could not be written either" in neither.stderr, described(neither))

    home = scratch / "home-state-unreadable"
    state(home).mkdir(parents=True)
    (state(home) / "first-run.json").write_text("not json")
    unreadable = run(home, FOURTEEN_DAYS_LATER, records)
    check("a first-run file that cannot be read is reported on stderr, with no count and no alert, exit 1",
          unreadable.returncode == 1 and "could not be read or written, so no count was made" in unreadable.stderr
          and pending_alerts(home) == [], described(unreadable))

    home = scratch / "home-alert-unwritable"
    run(home, FIRST_RUN, records)
    (home / ".local" / "state" / "nedsnodes" / "user-alerts").write_text("a file where the folder should be")
    unwritable = run(home, FOURTEEN_DAYS_LATER, records)
    check("an alert that cannot be written is reported on stderr, the count not recorded as done, exit 1",
          unwritable.returncode == 1 and "The count's user-alert could not be written" in unwritable.stderr
          and not (state(home) / "user-alert-written.json").exists(), described(unwritable))

    home = scratch / "home-done-file-unwritable"
    run(home, FIRST_RUN, records)
    (state(home) / "user-alert-written.json").mkdir()
    not_recorded = run(home, FOURTEEN_DAYS_LATER, records)
    check("an alert written whose record of being written cannot be saved is reported on stderr, exit 1",
          not_recorded.returncode == 1 and len(pending_alerts(home)) == 1
          and "could not be, so the next run writes the count again" in not_recorded.stderr, described(not_recorded))

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
