#!/usr/bin/env python3
"""Tests for scripts/sanity-check-record-ship.py (nedschorus#392).

The ship logic is the record shipper's and is tested by
nc-systems/cold-read/tests/cold-read-record-ship-test.py; what is tested here is what this
program adds: the store's kind is `sanity-check-records/`, the checkout's
directory of the same name is what --all reads, and the consequences the
runner's closing line promises — a second ship sends only the new
finding-dispositions.md, and one edited after it was shipped is refused rather
than replaced.

LOCAL MODE only: the destination override names a scratch directory and the
real rsync on this machine does the copy, so add-only and refuse-on-difference
are exercised for real. Nothing here touches ned-box. The remote invocation's
shape is the record shipper's and is covered by its own suite.

Run: python3 scripts/sanity-check-record-ship-test.py   (exit 0 = all passed)
"""

import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
SHIP = SCRIPTS_DIR / "sanity-check-record-ship.py"
DESTINATION_VARIABLE = "COLD_READ_RECORD_SHIP_DESTINATION"
RULED_DESTINATION = "nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records"

_spec = importlib.util.spec_from_file_location("sanity_check_record_ship", SHIP)
shipper_under_test = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(shipper_under_test)

failures = []


def check(case_name, condition, detail=""):
    print(f"{'ok' if condition else 'FAIL'}: {case_name}")
    if not condition:
        failures.append(case_name)
        if detail:
            print(f"      {detail}")


def make_record(root: pathlib.Path, name: str, files: dict) -> pathlib.Path:
    record = root / name
    record.mkdir(parents=True, exist_ok=True)
    for relative, text in files.items():
        path = record / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return record


def ship(destination, *args, script=SHIP):
    env = dict(os.environ)
    env[DESTINATION_VARIABLE] = destination
    return subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True, check=False, env=env)


CUT_REPORT = "<!-- provenance: runtime=claude model=opus -->\n# cut\n\nfinding one\n"
MECHANIZATION_REPORT = "<!-- provenance: runtime=codex model=gpt -->\n# mechanization\n\nfinding two\n"
DISPOSITIONS = "# Dispositions\n\nfinding one: ruled by the user.\n"

with tempfile.TemporaryDirectory(prefix="sanity-check-record-ship-test-") as scratch_name:
    scratch = pathlib.Path(scratch_name)

    # --- The destination is the record shipper's, with the kind swapped -------
    # The store's location stays defined in one place; this program only picks
    # the kind directory beside cold-read-records/.
    ruled_host, ruled_path = None, None
    saved = os.environ.pop(DESTINATION_VARIABLE, None)
    try:
        ruled_host, ruled_path = shipper_under_test.destination_for_this_machine()
    finally:
        if saved is not None:
            os.environ[DESTINATION_VARIABLE] = saved
    record_shipper_path = pathlib.PurePosixPath(RULED_DESTINATION.split(":", 1)[1])
    check("the ruled destination is the record shipper's store, kind sanity-check-records",
          ruled_path.name == "sanity-check-records"
          and ruled_path.parent == record_shipper_path.parent,
          f"{ruled_host}:{ruled_path}")

    # --- One record ships into that kind --------------------------------------
    store = scratch / "store"
    local_destination = str(store / "cold-read-records")
    records = scratch / "sanity-check-records"
    record = make_record(records, "2026-09-17-design-to-main-state-machine-design", {
        "cut-claude.md": CUT_REPORT,
        "mechanization-codex.md": MECHANIZATION_REPORT,
        "scratch/cut-claude/notes.md": "working notes\n",
    })
    result = ship(local_destination, str(record))
    shipped_dir = store / "sanity-check-records" / record.name
    check("a record ships, one shipped: line, exit 0",
          result.returncode == 0 and result.stdout.startswith("shipped: "),
          f"exit {result.returncode}: {result.stdout}{result.stderr}")
    check("it lands under sanity-check-records/ in the store, not cold-read-records/",
          (shipped_dir / "cut-claude.md").is_file()
          and not (store / "cold-read-records" / record.name).exists(),
          sorted(p.name for p in store.iterdir()))
    check("a cell's scratch directory ships with the reports",
          (shipped_dir / "scratch" / "cut-claude" / "notes.md").is_file(),
          sorted(str(p.relative_to(shipped_dir)) for p in shipped_dir.rglob("*")))
    check("the store's README points at the wiki page rather than naming "
          "this kind, which it listed until 2026-09-19",
          "nedschorus-file-naming-and-location-standards.md"
          in (store / "README.md").read_text(encoding="utf-8"),
          (store / "README.md").read_text(encoding="utf-8")[:400])

    # --- The second ship sends only finding-dispositions.md -------------------
    # What the runner's closing line promises the requesting agent.
    (record / "finding-dispositions.md").write_text(DISPOSITIONS, encoding="utf-8")
    result = ship(local_destination, str(record))
    check("shipping again adds only the new dispositions file",
          result.returncode == 0 and "1 file(s) added" in result.stdout,
          f"exit {result.returncode}: {result.stdout}")
    check("and that file is in the store",
          (shipped_dir / "finding-dispositions.md").read_text(encoding="utf-8") == DISPOSITIONS)

    # --- An edited dispositions file is refused, not replaced -----------------
    (record / "finding-dispositions.md").write_text(
        DISPOSITIONS + "finding two: set aside.\n", encoding="utf-8")
    result = ship(local_destination, str(record))
    check("a dispositions file edited after it shipped is REFUSED, exit 2",
          result.returncode == 2 and result.stdout.startswith("REFUSED: "),
          f"exit {result.returncode}: {result.stdout}")
    check("the refusal names the differing file and leaves the store's copy alone",
          "finding-dispositions.md" in result.stdout
          and (shipped_dir / "finding-dispositions.md").read_text(encoding="utf-8") == DISPOSITIONS,
          result.stdout)

    # --- A replaced triage names this kind's directory ------------------------
    # The record shipper builds the printed path; its own constant names
    # cold-read-records, and a sanity-check record lives under
    # sanity-check-records, where the command must look.
    triaged = make_record(records, "2026-09-23-triage-replacement", {
        "cut-claude.md": CUT_REPORT, "triage.md": "# triage\n"})
    ship(local_destination, str(triaged))
    (triaged / "triage.md").write_text("# triage\n\nrevised\n", encoding="utf-8")
    result = ship(local_destination, str(triaged))
    check("a replaced sanity-check triage prints the sha256sum path under sanity-check-records, not cold-read-records",
          result.returncode == 0 and "REPLACED" in result.stderr
          and ("sha256sum /mnt/backup/timeshift/snapshots/*/localhost"
               f"/home/nedlern/nedschorus-logs/sanity-check-records/{triaged.name}/triage.md")
          in result.stderr
          and "localhost/home/nedlern/nedschorus-logs/cold-read-records/" not in result.stderr,
          result.stderr)

    # --- Bad invocation --------------------------------------------------------
    result = ship(local_destination)
    check("no argument exits 64 with FAILED on stdout",
          result.returncode == 64 and result.stdout.startswith("FAILED"),
          f"exit {result.returncode}: {result.stdout}")

    # --- --all reads sanity-check-records/ beside the script's repository root -
    # As in the record shipper's suite: --all looks beside the script itself, so
    # the case runs a copy of it from a scratch repository.
    scratch_repo = scratch / "repo"
    # The whole scripts/ directory, __pycache__ aside, so a shared module
    # added tomorrow needs no edit here (user-ruled 2026-09-20, walk
    # md-skills-seat-open-decisions-2026-09-20 item 3).
    shutil.copytree(SCRIPTS_DIR, scratch_repo / "scripts",
                    ignore=shutil.ignore_patterns("__pycache__"))
    # The record shipper it loads lives with the cold read, not in scripts/.
    shutil.copytree(SCRIPTS_DIR.parent / "nc-systems" / "cold-read",
                    scratch_repo / "nc-systems" / "cold-read",
                    ignore=shutil.ignore_patterns("__pycache__"))
    scratch_ship = scratch_repo / "scripts" / SHIP.name
    all_store = str(scratch / "all-store" / "cold-read-records")
    good = make_record(scratch_repo / "sanity-check-records", "2026-09-10-good",
                       {"cut-claude.md": CUT_REPORT})
    make_record(scratch_repo / "sanity-check-records", "2026-09-11-empty", {})
    # A cold-read record beside it must not be swept up by this program's --all.
    make_record(scratch_repo / "cold-read-records", "2026-09-10-not-this-kind",
                {"r.md": CUT_REPORT})
    result = ship(all_store, "--all", script=scratch_ship)
    lines = result.stdout.splitlines()
    check("--all ships this kind's records and skips an empty directory, exit 0",
          result.returncode == 0
          and any(line.startswith(f"shipped: {good.name}") for line in lines)
          and any(line == "skipped: 2026-09-11-empty — empty directory" for line in lines),
          result.stdout + result.stderr)
    check("--all leaves cold-read records alone",
          "not-this-kind" not in result.stdout and "of 2" in lines[-1], result.stdout)

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
