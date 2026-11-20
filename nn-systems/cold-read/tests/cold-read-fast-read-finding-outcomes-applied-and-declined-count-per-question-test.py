#!/usr/bin/env python3
"""Cases for nn-systems/cold-read/cold-read-fast-read-finding-outcomes-applied-and-declined-count-per-question.py,
run as a subprocess on scratch cold-read-records directories: the table's counts and shares, the line on records
without outcomes, a shipment's leftover staging copy, an unreadable outcomes file, and a records directory that cannot be listed.

Run: python3 nn-systems/cold-read/tests/cold-read-fast-read-finding-outcomes-applied-and-declined-count-per-question-test.py
Prints one line per case and exits non-zero if any case fails.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROGRAM = (Path(__file__).resolve().parents[1]
           / "cold-read-fast-read-finding-outcomes-applied-and-declined-count-per-question.py")
OUTCOMES_FILE_NAME = "cold-read-fast-read-finding-outcomes.json"
FINDINGS_REPORT = "## Question 2: Where you struggled\n\n1. x\n"

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def record(records, name, outcomes=None, report=FINDINGS_REPORT, report_time=None):
    directory = records / name
    directory.mkdir(parents=True)
    (directory / "cold-read-fast-read.md").write_text(report, encoding="utf-8")
    if report_time is not None:
        os.utime(directory / "cold-read-fast-read.md", (report_time, report_time))
    if outcomes is not None:
        (directory / OUTCOMES_FILE_NAME).write_text(json.dumps({"findings": [
            {"finding": f"Q{question}.{index}", "question": question, "number": index, "outcome": outcome}
            for index, (question, outcome) in enumerate(outcomes, 1)]}), encoding="utf-8")
    return directory


def run(records):
    return subprocess.run([sys.executable, str(PROGRAM), "--cold-read-records", str(records)],
                          capture_output=True, text=True)


with tempfile.TemporaryDirectory() as scratch:
    records = Path(scratch) / "cold-read-records"
    record(records, "old-2026-09-01", report_time=1_000_000_000)
    record(records, "a-2026-11-19", [(2, "applied"), (2, "declined"), (4, "applied")], report_time=2_000_000_000)
    record(records, "b-2026-11-20", [(2, "applied"), (3, "declined")], report_time=2_000_000_100)
    record(records, "c-2026-11-21", report_time=2_000_000_200)
    record(records, "d-2026-11-21", report="## Question 2: Where you struggled\n\nNo issues\n",
           report_time=2_000_000_300)
    # A read that failed after freezing its target leaves a record with no report.
    (records / "e-2026-11-21" / "target").mkdir(parents=True)
    result = run(records)
    lines = result.stdout.splitlines()
    check("the table counts each question's applied and declined findings across the records, with the applied "
          "share, and exits 0",
          result.returncode == 0
          and lines[0].startswith(f"Cold-read-fast-read finding outcomes in {records}: 2 records hold them, "
                                  "the first for a report written ")
          and "| Question 2, Where you struggled | 2 | 1 | 67% |" in lines
          and "| Question 3, What it does not cover that it implies it should | 0 | 1 | 0% |" in lines
          and "| Question 4, What should be code | 1 | 0 | 100% |" in lines
          and "| All questions | 3 | 2 | 60% |" in lines, result.stdout + result.stderr)
    check("below the table, one line counts the records with findings since the first outcomes that hold none, "
          "leaving out older records, records without findings and a record with no report",
          lines[-1].startswith("Of the 3 records whose fast read report has findings and was written no earlier "
                               "than the first report whose record holds outcomes, 1 hold no outcomes"), lines[-1:])

    (records / "b-2026-11-20" / OUTCOMES_FILE_NAME).write_text("not json", encoding="utf-8")
    result = run(records)
    check("an outcomes file that is not the program's JSON is left out of the table and named on stderr, exit 1",
          result.returncode == 1 and "| Question 2, Where you struggled | 1 | 1 | 50% |" in result.stdout
          and f"{records / 'b-2026-11-20' / OUTCOMES_FILE_NAME}:" in result.stderr, result.stdout + result.stderr)

    staged = Path(scratch) / "staged"
    record(staged, "a-2026-11-19", [(2, "applied"), (4, "declined")], report_time=2_000_000_000)
    # cold-read-record-ship.py leaves a staging copy beside the record when a shipment stops before removing it.
    record(staged, ".ship-staging-a-2026-11-19-0123456789ab", [(2, "applied"), (4, "declined")],
           report_time=2_000_000_000)
    result = run(staged)
    check("a shipment's leftover staging copy beside a record is not counted as a record of its own",
          result.returncode == 0 and "1 records hold them" in result.stdout.splitlines()[0]
          and "| All questions | 1 | 1 | 50% |" in result.stdout, result.stdout + result.stderr)

    empty = Path(scratch) / "empty"
    empty.mkdir()
    result = run(empty)
    check("with no outcomes anywhere, each share says none recorded",
          result.returncode == 0 and "| All questions | 0 | 0 | none recorded |" in result.stdout, result.stdout)

    result = run(Path(scratch) / "no-such-directory")
    check("a records directory that cannot be listed is reported on stderr with nothing counted, exit 1",
          result.returncode == 1 and result.stdout == ""
          and result.stderr.startswith("No finding outcomes were counted: ") and "cannot be listed" in result.stderr,
          result.stderr)

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
