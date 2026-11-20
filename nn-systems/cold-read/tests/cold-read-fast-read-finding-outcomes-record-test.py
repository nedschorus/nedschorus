#!/usr/bin/env python3
"""Cases for cold-read-fast-read.py --record-finding-outcomes-in-cold-read-record: the ready-made command a read
prints, filled in and run, writes the record's outcomes file once and ships the record; each refusal writes
nothing and exits 64; a record that does not reach the log-store keeps its outcomes file and exits 1.

Every case runs the program as a subprocess on a scratch record, shipping to a scratch log-store through the
shipper's COLD_READ_RECORD_SHIP_DESTINATION, so no case reaches ned-box or launches a cold-read-cell.

Run: python3 nn-systems/cold-read/tests/cold-read-fast-read-finding-outcomes-record-test.py
Prints one line per case and exits non-zero if any case fails.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1] / "cold-read-fast-read.py"
_spec = importlib.util.spec_from_file_location("cold_read_fast_read_under_test", PROGRAM)
fast_read = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fast_read)
OUTCOMES_FILE_NAME = fast_read.record_names.COLD_READ_FAST_READ_FINDING_OUTCOMES_FILE_NAME
PLACEHOLDER = fast_read.finding_outcomes.FINDING_OUTCOME_PLACEHOLDER

REPORT = """\
## Question 1: What it says

[s1]
- a point

## Question 2: Where you struggled

1. `"the freeze"`: undefined.

## Question 3: What it does not cover that it implies it should

No issues

## Question 4: What should be code

1. "renames each of the 16" — a script can do it.
"""

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def scratch_record(root, name, report=REPORT):
    record = root / "cold-read-records" / name
    (record / "target").mkdir(parents=True)
    (record / "target" / "a.md").write_text("A document.\n", encoding="utf-8")
    if report is not None:
        (record / "cold-read-fast-read.md").write_text(report, encoding="utf-8")
    return record


def run(arguments, store, shell_command=None):
    environment = dict(os.environ, COLD_READ_RECORD_SHIP_DESTINATION=str(store))
    if shell_command is not None:
        return subprocess.run(["bash", "-c", shell_command], capture_output=True, text=True, env=environment)
    return subprocess.run([sys.executable, str(PROGRAM), *arguments], capture_output=True, text=True,
                          env=environment)


def record_arguments(record, *values):
    return ["--record-finding-outcomes-in-cold-read-record", str(record),
            *[part for value in values for part in ("--finding-outcome", value)]]


with tempfile.TemporaryDirectory() as scratch:
    # Resolved, as the program resolves the record it is given: the test sandbox puts TMPDIR behind a symlink.
    root = Path(scratch).resolve()
    store = root / "log-store" / "cold-read-records"
    store.mkdir(parents=True)

    record = scratch_record(root, "a-2026-11-19")
    told = fast_read.finding_outcomes_to_record_lines(record)
    lines = told.splitlines()
    check("after a read whose report has findings, stderr lists each finding by id with its opening, then the "
          "ready-made command naming this program and the record",
          lines[0] == "cold-read-fast-read: the report has 2 findings:"
          and lines[1] == '  Q2.1: `"the freeze"`: undefined.'
          and lines[2].startswith('  Q4.1: "renames each of the 16"')
          and lines[4] == f"python3 {PROGRAM} --record-finding-outcomes-in-cold-read-record {record} \\"
          and lines[5] == f"  --finding-outcome 'Q2.1={PLACEHOLDER}' \\"
          and lines[6] == f"  --finding-outcome 'Q4.1={PLACEHOLDER}'", told)
    no_findings = scratch_record(root, "b-2026-11-19", "## Question 2: Where you struggled\n\nNo issues\n")
    check("after a read whose report has no findings, stderr says it needs no outcomes",
          fast_read.finding_outcomes_to_record_lines(no_findings)
          == "cold-read-fast-read: the report has no findings, so it needs no finding outcomes.")

    command = "\n".join(lines[4:]).replace(f"'Q2.1={PLACEHOLDER}'", "'Q2.1=applied'").replace(
        f"'Q4.1={PLACEHOLDER}'", "'Q4.1=declined: `grep` already finds them, at $0 cost'")
    result = run(None, store, shell_command=command)
    outcomes_file = record / OUTCOMES_FILE_NAME
    written = json.loads(outcomes_file.read_text(encoding="utf-8")) if outcomes_file.is_file() else {}
    check("the ready-made command, filled in and run as printed, writes each outcome, ships the record, prints "
          "the file's path and exits 0",
          result.returncode == 0 and result.stdout.strip() == str(outcomes_file)
          and "record: shipped:" in result.stderr
          and [entry["outcome"] for entry in written.get("findings", [])] == ["applied", "declined"]
          and written["findings"][1]["reason"] == "`grep` already finds them, at $0 cost"
          and (store / record.name / OUTCOMES_FILE_NAME).read_bytes() == outcomes_file.read_bytes(),
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr[-600:]!r}")
    before = outcomes_file.read_bytes()
    result = run(record_arguments(record, "Q2.1=declined: changed my mind", "Q4.1=applied"), store)
    check("outcomes recorded once are refused a second time, exit 64, the file left as it was, and the refusal "
          "says how to ship the record",
          result.returncode == 64 and result.stdout.startswith("REFUSED")
          and "already holds this record's finding outcomes" in result.stderr
          and "cold-read-record-ship.py" in result.stderr and outcomes_file.read_bytes() == before,
          f"exit {result.returncode}; stderr={result.stderr[-400:]!r}")

    for index, (case, values, expected) in enumerate((
            ("a list that leaves a finding out", ["Q2.1=applied"], "No outcome is given for Q4.1."),
            ("a list naming a finding the report does not have",
             ["Q2.1=applied", "Q4.1=applied", "Q3.1=applied"], "names Q3.1, which is no finding of the report"),
            ("a value still holding the placeholder", ["Q2.1=applied", f"Q4.1={PLACEHOLDER}"],
             "which is neither `applied` nor `declined: <reason>`"))):
        fresh = scratch_record(root, f"refused-{index}-2026-11-19")
        result = run(record_arguments(fresh, *values), store)
        check(f"{case} is refused, exit 64, writing nothing, and the refusal lists the report's findings",
              result.returncode == 64 and result.stdout.startswith("REFUSED") and expected in result.stderr
              and "  Q4.1: " in result.stderr and not (fresh / OUTCOMES_FILE_NAME).exists()
              and not (store / fresh.name).exists(),
              f"exit {result.returncode}; stderr={result.stderr[-400:]!r}")

    result = run(record_arguments(no_findings, "Q2.1=applied"), store)
    check("a record whose report has no findings is refused, writing nothing",
          result.returncode == 64 and "has no findings, so it needs no finding outcomes" in result.stderr
          and not (no_findings / OUTCOMES_FILE_NAME).exists(), result.stderr[-300:])
    no_report = scratch_record(root, "c-2026-11-19", report=None)
    result = run(record_arguments(no_report, "Q2.1=applied"), store)
    check("a directory holding no fast read report is refused, writing nothing",
          result.returncode == 64 and "holds no cold-read-fast-read report" in result.stderr
          and not (no_report / OUTCOMES_FILE_NAME).exists(), result.stderr[-300:])

    unshipped = scratch_record(root, "d-2026-11-19")
    result = run(record_arguments(unshipped, "Q2.1=applied", "Q4.1=applied"),
                 "nobody@no-such-host.invalid:/tmp/no-store")
    check("when the record cannot reach the log-store, the outcomes file stays written, its path is printed, "
          "stderr says how to ship the record, and the exit is 1",
          result.returncode == 1 and result.stdout.strip() == str(unshipped / OUTCOMES_FILE_NAME)
          and (unshipped / OUTCOMES_FILE_NAME).is_file() and "record: FAILED" in result.stderr
          and "did not reach the log-store" in result.stderr and "cold-read-record-ship.py" in result.stderr,
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr[-600:]!r}")

    result = subprocess.run([sys.executable, str(PROGRAM), "--finding-outcome", "Q2.1=applied"],
                            capture_output=True, text=True)
    check("--finding-outcome without the record option, and without --target, is a usage error",
          result.returncode == 2 and "give --target, or --record-finding-outcomes-in-cold-read-record" in result.stderr,
          result.stderr[-300:])

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
