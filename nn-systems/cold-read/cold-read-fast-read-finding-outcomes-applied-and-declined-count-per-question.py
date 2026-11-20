#!/usr/bin/env python3
"""Count, for each question of the cold-read-fast-read, how many of its findings agents applied and how many they
declined, across every cold-read-record in the log-store, and print the counts as a table.

Usage:
  python3 nn-systems/cold-read/cold-read-fast-read-finding-outcomes-applied-and-declined-count-per-question.py
      [--cold-read-records DIRECTORY]

The outcomes are the cold-read-fast-read-finding-outcomes.json file a record holds once an agent has run
cold-read-fast-read.py --record-finding-outcomes-in-cold-read-record on it. The records are read from the
log-store's cold-read-records directory, the path in cold-read-record-ship.py's LOG_STORE_RECORDS_DESTINATION, on
ned-box as it is and on the Mac through its mount of ned-box's home, or from DIRECTORY when it is given. Below the
table, one line says how many of the records whose report has findings and was written no earlier than the first
report whose record holds outcomes hold none, since a share counted only from the reads whose findings were recorded can mislead.

Exit status: 0 when every outcomes file was read; 1 when the records directory cannot be read, printing why, or
when an outcomes file is not the JSON cold-read-fast-read.py writes, printing the table without it and naming it.
"""
import argparse
import collections
import datetime
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


finding_outcomes = _load("cold_read_fast_read_report_findings_parse_and_finding_outcomes_check_common",
                         HERE / "cold-read-fast-read-report-findings-parse-and-finding-outcomes-check-common.py")
record_shipper = _load("cold_read_record_ship", HERE / "cold-read-record-ship.py")
ned_box_home = _load("ned_box_home_directory_and_its_mac_mount_point_path_constants_common",
                     HERE.parent / "general-tools"
                     / "ned-box-home-directory-and-its-mac-mount-point-path-constants-common.py")


class RecordsDirectoryUnreadable(Exception):
    """The cold-read-records directory cannot be listed; its argument says why."""


def log_store_cold_read_records_directory():
    """The log-store's cold-read-records directory as this machine reaches it, or None, and the paths tried."""
    _, path = record_shipper.split_destination(record_shipper.LOG_STORE_RECORDS_DESTINATION)
    candidates = [Path(str(path))]
    if str(path).startswith(ned_box_home.NED_BOX_HOME + "/"):
        candidates.append(Path(ned_box_home.MAC_MOUNT_OF_NED_BOX_HOME + str(path)[len(ned_box_home.NED_BOX_HOME):]))
    return next((candidate for candidate in candidates if candidate.is_dir()), None), candidates


def cold_read_fast_read_finding_outcomes_count_table(records_directory):
    """Return (the table as text, the unreadable outcomes files, one line each). Raise RecordsDirectoryUnreadable
    when records_directory cannot be listed."""
    try:
        # An interrupted shipment's staging copy holds the same files as its record.
        records = sorted(path for path in Path(records_directory).iterdir()
                         if path.is_dir() and not path.name.startswith(record_shipper.STAGING_DIRECTORY_PREFIX))
    except OSError as error:
        raise RecordsDirectoryUnreadable(f"{records_directory} cannot be listed: {error}") from error
    counts = {question: collections.Counter() for question in finding_outcomes.FINDING_QUESTION_NUMBERS}
    unreadable, recorded, first_recorded = [], 0, None
    for record in records:
        outcomes_file = finding_outcomes.finding_outcomes_file_path(record)
        try:
            outcomes = finding_outcomes.finding_outcomes_read(record)
        except (OSError, ValueError) as error:
            unreadable.append(f"{outcomes_file}: {error}")
            continue
        if outcomes is None:
            continue
        recorded += 1
        # The report's time, not the outcomes file's, so the first record with outcomes counts among those since.
        report = finding_outcomes.cold_read_fast_read_record_report_path(record)
        written = (report if report.is_file() else outcomes_file).stat().st_mtime
        first_recorded = written if first_recorded is None else min(first_recorded, written)
        for entry in outcomes:
            if entry["question"] in counts:
                counts[entry["question"]][entry["outcome"]] += 1
    lines = [f"Cold-read-fast-read finding outcomes in {records_directory}: {recorded} records hold them"
             + (f", the first for a report written {datetime.date.fromtimestamp(first_recorded).isoformat()}." if recorded
                else "."), "",
             "| Question | Applied | Declined | Applied share |", "|---|---|---|---|"]
    total = collections.Counter()
    for question, counted in counts.items():
        total.update(counted)
        lines.append(table_row(f"Question {question}, {finding_outcomes.FINDING_QUESTION_TITLES[question]}", counted))
    lines.append(table_row("All questions", total))
    if recorded:
        lines += ["", records_without_outcomes_line(records, first_recorded)]
    return "\n".join(lines) + "\n", unreadable


def table_row(label, counted):
    applied, declined = counted[finding_outcomes.APPLIED], counted[finding_outcomes.DECLINED]
    share = f"{round(100 * applied / (applied + declined))}%" if applied + declined else "none recorded"
    return f"| {label} | {applied} | {declined} | {share} |"


def records_without_outcomes_line(records, first_recorded):
    """How many records whose report has findings and was written no earlier than the first report whose record
    holds outcomes hold none."""
    since, without = 0, 0
    for record in records:
        report = finding_outcomes.cold_read_fast_read_record_report_path(record)
        try:
            if report.stat().st_mtime < first_recorded:
                continue
            findings = finding_outcomes.cold_read_fast_read_record_findings(record)
        except OSError:
            continue  # A record whose read failed holds no report, and so no findings to record.
        if not findings:
            continue
        since += 1
        if not finding_outcomes.finding_outcomes_file_path(record).is_file():
            without += 1
    return (f"Of the {since} records whose fast read report has findings and was written no earlier than the "
            f"first report whose record holds outcomes, {without} hold no outcomes, so their findings are not counted "
            f"above.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cold-read-records", type=Path, metavar="DIRECTORY",
                        help="the cold-read-records directory to count, instead of the log-store's")
    arguments = parser.parse_args(argv)
    directory = arguments.cold_read_records
    if directory is None:
        directory, tried = log_store_cold_read_records_directory()
        if directory is None:
            print(f"No finding outcomes were counted: the log-store's cold-read-records directory is not reachable "
                  f"from this machine at {' or '.join(str(path) for path in tried)}.", file=sys.stderr)
            return 1
    try:
        table, unreadable = cold_read_fast_read_finding_outcomes_count_table(directory)
    except RecordsDirectoryUnreadable as error:
        print(f"No finding outcomes were counted: {error.args[0]}", file=sys.stderr)
        return 1
    print(table, end="")
    if unreadable:
        print("These outcomes files could not be read, so the table leaves them out:\n" + "\n".join(unreadable),
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
