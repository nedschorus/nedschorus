#!/usr/bin/env python3
"""Tests for scripts/cold-read-record-ship.py: the three rules, the exits, the
one-line stdout, --all, and the shape of the remote invocation.

Two modes, as the script's docstring says. LOCAL: the destination override
names a scratch directory and the real rsync on this machine does the copy,
so add-only, refuse-on-difference and the README are exercised for real.
REMOTE: the override is the ruled scp-form destination and stub `ssh` and
`rsync` binaries on PATH record what they were asked, so the case reads the
invocation without a network. Nothing here touches ned-box.

Run: python3 scripts/cold-read-record-ship-test.py   (exit 0 = all passed)
"""

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
SHIP = SCRIPTS_DIR / "cold-read-record-ship.py"
DESTINATION_VARIABLE = "COLD_READ_RECORD_SHIP_DESTINATION"
RULED_DESTINATION = "nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records"

# The stub for both `ssh` and `rsync`: append argv to the log named in the
# environment and exit 0 printing nothing, which for the inventory call
# means "no such directory in the store yet".
STUB_RECORDER = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["RECORD_SHIP_TEST_ARGV_LOG"], "a") as log:
    log.write(json.dumps(sys.argv) + "\\n")
"""

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


def ship(destination, *args, extra_env=None, script=SHIP):
    env = dict(os.environ)
    env[DESTINATION_VARIABLE] = destination
    env.update(extra_env or {})
    return subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True, check=False, env=env)


REPORT_A = "<!-- provenance: runtime=claude model=opus -->\n# A\n\nfinding one\n"
REPORT_B = "<!-- provenance: runtime=codex model=gpt -->\n# B\n\nfinding two\n"

with tempfile.TemporaryDirectory(prefix="cold-read-record-ship-test-") as scratch_name:
    scratch = pathlib.Path(scratch_name)
    store_root = scratch / "store"
    local_destination = str(store_root / "cold-read-records")
    records = scratch / "records"

    # --- Rule 1, add-only, and the README ----------------------------------
    demo = make_record(records, "2026-09-07-demo", {"a.md": REPORT_A, "b.md": REPORT_B})
    result = ship(local_destination, str(demo))
    check("first ship exits 0 with one line opening shipped:",
          result.returncode == 0 and result.stdout.startswith("shipped:")
          and result.stdout.count("\n") == 1, result.stdout + result.stderr)
    check("the two files are in the store under the record's own name",
          sorted(p.name for p in (store_root / "cold-read-records" / demo.name).iterdir())
          == ["a.md", "b.md"])
    check("the store's root gained a README saying what the store is",
          (store_root / "README.md").is_file()
          and "log-store" in (store_root / "README.md").read_text(encoding="utf-8"))
    check("the line names the store path the files went to",
          demo.name in result.stdout and "2 file(s) added" in result.stdout, result.stdout)

    stored_a = store_root / "cold-read-records" / demo.name / "a.md"
    mtime_before = stored_a.stat().st_mtime_ns
    result = ship(local_destination, str(demo))
    check("a second run with nothing new exits 0 and says so",
          result.returncode == 0 and "nothing new" in result.stdout, result.stdout)
    check("the second run touched nothing in the store",
          stored_a.stat().st_mtime_ns == mtime_before)

    (demo / "dispositions.md").write_text("# dispositions\n\nnone\n", encoding="utf-8")
    result = ship(local_destination, str(demo))
    check("dispositions.md written later joins the reports on the next run",
          result.returncode == 0 and "1 file(s) added" in result.stdout
          and (store_root / "cold-read-records" / demo.name / "dispositions.md").is_file(),
          result.stdout)

    os.utime(demo / "b.md")  # same bytes, newer mtime
    result = ship(local_destination, str(demo))
    check("a same-content file with a newer mtime is not a difference and not re-sent",
          result.returncode == 0 and "nothing new" in result.stdout, result.stdout)

    # --- Rule 2, refuse on difference --------------------------------------
    (demo / "a.md").write_text(
        "<!-- provenance: runtime=claude model=opus-rerun -->\n# A\n\nfinding one, reworded\n",
        encoding="utf-8")
    (demo / "late.md").write_text("# late\n", encoding="utf-8")
    result = ship(local_destination, str(demo))
    check("a differing file is REFUSED with exit 2",
          result.returncode == 2 and result.stdout.startswith("REFUSED:"), result.stdout)
    check("the refusal names the file and prints both provenance comments",
          "a.md" in result.stdout and "model=opus " in result.stdout
          and "model=opus-rerun" in result.stdout, result.stdout)
    check("the refusal tells the person what to do: rename the local directory -2",
          "-2 suffix" in result.stdout, result.stdout)
    check("nothing was copied on a refused run, not even the new file",
          not (store_root / "cold-read-records" / demo.name / "late.md").exists()
          and stored_a.read_text(encoding="utf-8") == REPORT_A)
    (demo / "a.md").write_text(REPORT_A, encoding="utf-8")

    (demo / "dispositions.md").write_text("# dispositions\n\nrewritten\n", encoding="utf-8")
    result = ship(local_destination, str(demo))
    check("a differing file with no provenance comment says so instead of crashing",
          result.returncode == 2 and "(no provenance comment)" in result.stdout, result.stdout)
    (demo / "dispositions.md").write_text("# dispositions\n\nnone\n", encoding="utf-8")

    # --- Rule 3, fail loudly -------------------------------------------------
    result = ship("nobody@no-such-host.invalid:/tmp/no-store", str(demo))
    check("an unreachable host is FAILED with exit 1 and one stdout line",
          result.returncode == 1 and result.stdout.startswith("FAILED:")
          and result.stdout.count("\n") == 1, result.stdout)
    check("the FAILED line says the record stays on disk",
          "stays on disk" in result.stdout, result.stdout)

    # --- Bad invocations -------------------------------------------------------
    for case_name, args in (
        ("no argument at all", ()),
        ("a directory and --all together", (str(demo), "--all")),
        ("a directory that does not exist", (str(records / "2026-01-01-nothing"),)),
        ("an empty directory", (str(make_record(records, "2026-01-02-empty", {})),)),
    ):
        result = ship(local_destination, *args)
        check(f"{case_name} exits 64 with FAILED on stdout",
              result.returncode == 64 and result.stdout.startswith("FAILED"),
              f"exit {result.returncode}: {result.stdout}")

    # --- --all: continues past a refusal, lists it, exits 2 -------------------
    # --all reads cold-read-records/ beside the script's own repository root,
    # so the case runs a copy of the script from a scratch repository.
    scratch_repo = scratch / "repo"
    (scratch_repo / "scripts").mkdir(parents=True)
    shutil.copy(SHIP, scratch_repo / "scripts" / SHIP.name)
    scratch_ship = scratch_repo / "scripts" / SHIP.name
    all_store = str(scratch / "store-all" / "cold-read-records")
    good = make_record(scratch_repo / "cold-read-records", "2026-09-01-good", {"r.md": REPORT_A})
    bad = make_record(scratch_repo / "cold-read-records", "2026-09-02-bad", {"r.md": REPORT_B})
    (scratch_repo / "cold-read-records" / "stray-file.txt").write_text("not a directory\n")
    ship(all_store, str(bad))  # bad is in the store once...
    (bad / "r.md").write_text(REPORT_A, encoding="utf-8")  # ...and now differs locally
    result = ship(all_store, "--all", script=scratch_ship)
    lines = result.stdout.splitlines()
    check("--all ships the good directory, refuses the differing one, and goes on",
          any(line.startswith("shipped: 2026-09-01-good") for line in lines)
          and any(line.startswith("REFUSED: 2026-09-02-bad") for line in lines),
          result.stdout + result.stderr)
    check("--all ends with one summary line naming the refused directory and exits 2",
          lines and lines[-1].startswith("--all:") and "1 shipped" in lines[-1]
          and "1 refused (2026-09-02-bad)" in lines[-1] and result.returncode == 2,
          result.stdout)
    check("--all ignores a stray file beside the record directories",
          "stray-file" not in result.stdout and "of 2" in lines[-1], result.stdout)

    # --- The remote invocation, read from stubs ---------------------------------
    stubs = scratch / "stub-bin"
    stubs.mkdir()
    for name in ("ssh", "rsync"):
        stub = stubs / name
        stub.write_text(STUB_RECORDER, encoding="utf-8")
        stub.chmod(0o755)
    argv_log = scratch / "argv.jsonl"
    result = ship(RULED_DESTINATION, str(demo), extra_env={
        "PATH": f"{stubs}{os.pathsep}{os.environ.get('PATH', '')}",
        "RECORD_SHIP_TEST_ARGV_LOG": str(argv_log)})
    calls = [json.loads(line) for line in argv_log.read_text().splitlines()]
    ssh_calls = [c for c in calls if c[0].endswith("ssh")]
    rsync_calls = [c for c in calls if c[0].endswith("rsync")]
    check("remote mode exits 0 and reports the files as added",
          result.returncode == 0 and result.stdout.startswith("shipped:"),
          result.stdout + result.stderr)
    check("every ssh call runs in batch mode with a connect timeout",
          ssh_calls and all("BatchMode=yes" in c and any(a.startswith("ConnectTimeout=") for a in c)
                            for c in ssh_calls), str(ssh_calls))
    check("the store is prepared over ssh: mkdir -p of the records path and the README when absent",
          any("mkdir -p" in " ".join(c) and "README.md" in " ".join(c)
              and "/home/nedlern/nedschorus-logs/cold-read-records" in " ".join(c)
              for c in ssh_calls), str(ssh_calls))
    check("the store's inventory is one ssh call running sha256sum under the record's directory",
          any("sha256sum" in " ".join(c) and f"cold-read-records/{demo.name}" in " ".join(c)
              for c in ssh_calls), str(ssh_calls))
    check("exactly one rsync call, add-only, over batch-mode ssh, into the record's own directory",
          len(rsync_calls) == 1 and "-a" in rsync_calls[0]
          and "--ignore-existing" in rsync_calls[0]
          and "ssh -o BatchMode=yes -o ConnectTimeout=10" in rsync_calls[0]
          and rsync_calls[0][-2] == f"{demo.resolve()}/"
          and rsync_calls[0][-1] == f"{RULED_DESTINATION}/{demo.name}/",
          str(rsync_calls))
    check("rsync is never asked to delete or to write in place",
          not any(flag in rsync_calls[0] for flag in ("--delete", "--inplace")),
          str(rsync_calls))
    check("the destination constant in the script is the ruled one",
          f'LOG_STORE_RECORDS_DESTINATION = "{RULED_DESTINATION}"'
          in SHIP.read_text(encoding="utf-8"))

print()
if failures:
    print(f"{len(failures)} case(s) FAILED:")
    for name in failures:
        print(f"  - {name}")
    sys.exit(1)
print("all cases passed")
