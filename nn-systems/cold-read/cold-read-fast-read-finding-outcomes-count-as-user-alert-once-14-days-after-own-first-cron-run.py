#!/usr/bin/env python3
"""Fourteen days after this program's own first run, count how often each cold-read-fast-read question's findings
were applied and declined, and write the table as one user-alert, which becomes an item of the user's
approval-walk; then do nothing on every later run.

    python3 <this file>

It runs once a day on ned-box, from the table nn-systems/general-tools/scheduled-jobs-on-each-machine.json,
which nn-systems/general-tools/install-scheduled-jobs-on-this-machine.py installs as this cron line:
    15 8 * * * /usr/bin/python3 /home/nedlern/Projects/nedsnodes/nn-systems/cold-read/cold-read-fast-read-finding-outcomes-count-as-user-alert-once-14-days-after-own-first-cron-run.py >> /home/nedlern/.claude/cold-read-fast-read-finding-outcomes-count-as-user-alert-once-14-days-after-own-first-cron-run.log 2>&1

Cron has no schedule that runs once, so the program keeps its own state, in STATE_RELATIVE_TO_HOME under the home
directory read from HOME: `first-run.json`, written on its first run with that time, which starts the 14 days; and
`user-alert-written.json`, written once the alert is, naming it, after which every run only says so. The count is
nn-systems/cold-read/cold-read-fast-read-finding-outcomes-applied-and-declined-count-per-question.py's, over the
log-store's cold-read-records, and the alert is written through
nn-systems/general-tools/user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py. The
alert's action asks for this job's removal from the table, since it has done its one count.

Exit status: 0 when the program waits, wrote the alert, or wrote it before. 1 when the count could not be made,
writing a user-alert saying so, and trying again on the next day's run; or when an alert or the state file could
not be written. Its output goes to the cron log above.
"""
import argparse
import datetime
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
THIS_PROGRAM = "nn-systems/cold-read/cold-read-fast-read-finding-outcomes-count-as-user-alert-once-14-days-after-own-first-cron-run.py"
JOB_NAME = "cold-read-fast-read-finding-outcomes-count-as-user-alert-once-14-days-after-own-first-cron-run"
STATE_RELATIVE_TO_HOME = Path(".local") / "state" / "nedsnodes" / JOB_NAME
FIRST_RUN_FILE_NAME = "first-run.json"
USER_ALERT_WRITTEN_FILE_NAME = "user-alert-written.json"
DAYS_AFTER_FIRST_RUN = 14


def _load(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


outcomes_count = _load("cold_read_fast_read_finding_outcomes_applied_and_declined_count_per_question",
                       HERE / "cold-read-fast-read-finding-outcomes-applied-and-declined-count-per-question.py")
user_alerts = _load(
    "user_alerts_pending_and_claimed_files_write_claim_release_and_delete_common",
    HERE.parent / "general-tools" / "user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py")

COUNT_TITLE = "How often agents applied each cold-read-fast-read question's findings, over two weeks"
COUNT_TEXT_OPENING = (
    "Since cold-read-fast-read.py began asking agents to record whether they applied or declined each finding of a "
    "fast read, and the approval-walk began refusing to present an item until they had, two weeks have passed. "
    "The table counts every finding outcome in the log-store's cold-read-records, by the question that raised the "
    "finding. An \"applied\" is the agent's own word; nothing checks it.\n\n")
COUNT_ACTION = (
    "Only the user can decide, from the table, whether to keep, change or drop a question of the cold-read-fast-read, "
    "and whether agents keep recording outcomes. Present the table with a recommendation for each question. An "
    f"agent on ned-box should also remove the job {JOB_NAME} from "
    "nn-systems/general-tools/scheduled-jobs-on-each-machine.json in a pull request, since it has made its one count "
    "and only says so on each later run.")
FAILED_TITLE = "The two-week count of cold-read-fast-read finding outcomes could not be made"
FAILED_ACTION = (
    f"An agent on ned-box can run python3 {THIS_PROGRAM} by hand, read the error it prints, and fix its cause; the job "
    "tries again each day, and writes the count's user-alert once a run succeeds.")


def state_directory():
    return Path.home() / STATE_RELATIVE_TO_HOME


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cold-read-records", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--now", type=datetime.datetime.fromisoformat, help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    now = arguments.now or datetime.datetime.now(datetime.timezone.utc)
    state = state_directory()
    written_file, first_run_file = state / USER_ALERT_WRITTEN_FILE_NAME, state / FIRST_RUN_FILE_NAME
    try:
        if written_file.is_file():
            print(f"The count's user-alert was written before, as {written_file} says; nothing to do. The job "
                  f"{JOB_NAME} can be removed from the scheduled jobs table.")
            return 0
        if not first_run_file.is_file():
            write_json(first_run_file, {"first_run": now.isoformat(timespec="seconds")})
            print(f"First run: the count is made {DAYS_AFTER_FIRST_RUN} days from now, "
                  f"{(now + datetime.timedelta(days=DAYS_AFTER_FIRST_RUN)).date().isoformat()}.")
            return 0
        due = (datetime.datetime.fromisoformat(json.loads(first_run_file.read_text(encoding="utf-8"))["first_run"])
               + datetime.timedelta(days=DAYS_AFTER_FIRST_RUN))
    except (OSError, ValueError, KeyError) as error:
        print(f"The state in {state} could not be read or written, so no count was made: {error!r}", file=sys.stderr)
        return 1
    if now < due:
        print(f"Waiting: the count is made on {due.date().isoformat()}.")
        return 0
    directory, tried = (arguments.cold_read_records, None) if arguments.cold_read_records else (
        outcomes_count.log_store_cold_read_records_directory())
    try:
        if directory is None:
            raise outcomes_count.RecordsDirectoryUnreadable(
                f"the log-store's cold-read-records directory is not reachable at "
                f"{' or '.join(str(path) for path in tried)}")
        table, unreadable = outcomes_count.cold_read_fast_read_finding_outcomes_count_table(directory)
    except outcomes_count.RecordsDirectoryUnreadable as error:
        text = f"No finding outcomes were counted: {error.args[0]}"
        print(text, file=sys.stderr)
        try:
            user_alerts.user_alert_write_to_pending(FAILED_TITLE, text, FAILED_ACTION)
        except OSError as alert_error:
            print(f"The user-alert saying so could not be written either, so no alert reached pending/: "
                  f"{alert_error!r}", file=sys.stderr)
        return 1
    text = COUNT_TEXT_OPENING + table + (
        "\nThese outcomes files could not be read, so the table leaves them out:\n" + "\n".join(unreadable)
        if unreadable else "")
    print(text)
    try:
        alert_id = user_alerts.user_alert_write_to_pending(COUNT_TITLE, text, COUNT_ACTION)
    except OSError as error:
        print(f"The count's user-alert could not be written, so no alert reached pending/; the next run tries "
              f"again: {error!r}", file=sys.stderr)
        return 1
    try:
        write_json(written_file, {"user_alert_id": alert_id, "written_at": now.isoformat(timespec="seconds")})
    except OSError as error:
        print(f"User-alert {alert_id} was written, but {written_file} could not be, so the next run writes the "
              f"count again: {error!r}", file=sys.stderr)
        return 1
    print(f"This program wrote user-alert {alert_id} into the user-alerts pending/ folder.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
