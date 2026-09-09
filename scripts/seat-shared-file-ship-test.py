#!/usr/bin/env python3
"""Tests for scripts/seat-shared-file-ship.py: the seat name, the three rules,
the exits, the one-line stdout that IS the citation, and the remote shape.

Three modes. LOCAL and REMOTE are the record shipper's test's. LOCAL: the
destination override names a scratch directory and the real rsync copies, so
add-only, refuse-on-difference and the README writes are exercised for real.
REMOTE: the override is the ruled scp-form destination and stub `ssh` and
`rsync` binaries on PATH record what they were asked, so the invocation is
read without a network. IN-PROCESS: the program is loaded with importlib and
`socket.gethostname` is patched, which is the only way to reach the ned-box
branch -- a subprocess's hostname cannot be faked -- where the copy is local
but the citation must still name the host. Nothing here touches ned-box.

Run: python3 scripts/seat-shared-file-ship-test.py   (exit 0 = all passed)
"""

import contextlib
import importlib.util
import io
import json
import os
import pathlib
import socket
import subprocess
import sys
import tempfile

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
SHIP = SCRIPTS_DIR / "seat-shared-file-ship.py"
RECORD_SHIP = SCRIPTS_DIR / "cold-read-record-ship.py"
DESTINATION_VARIABLE = "COLD_READ_RECORD_SHIP_DESTINATION"
SEAT_VARIABLE = "CLAUDE_CODE_TASK_LIST_ID"
RULED_RECORDS_DESTINATION = (
    "nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records")
RULED_SEATS_DESTINATION = "nedlern@ned-box:/home/nedlern/nedschorus-logs/seats"

STUB_RECORDER = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["SEAT_SHIP_TEST_ARGV_LOG"], "a") as log:
    log.write(json.dumps(sys.argv) + "\\n")
"""

failures = []

# The record shipper is imported for its STORE_README, so the case that checks
# a store born here compares against the one text rather than a copy of it.
_record_shipper_spec = importlib.util.spec_from_file_location(
    "cold_read_record_ship_under_test", RECORD_SHIP)
record_shipper = importlib.util.module_from_spec(_record_shipper_spec)
_record_shipper_spec.loader.exec_module(record_shipper)


def load_ship_module(module_name):
    """The program under test, loaded into this process under its own name.

    Used only where a subprocess cannot reach the behavior: the ned-box
    branch, which turns on `socket.gethostname`, and the citation a local
    copy prints.
    """
    spec = importlib.util.spec_from_file_location(module_name, SHIP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def two_hosts_of(destination):
    """(copy host, citation host), or a description of what came back instead.

    A destination that does not tell the two hosts apart -- the shape this
    program had when it printed a hostless citation on ned-box -- FAILS the
    cases below rather than aborting the run with an AttributeError.
    """
    try:
        return destination.copy_host, destination.citation_host
    except AttributeError:
        return ("no copy_host/citation_host: " + repr(destination),) * 2


def check(case_name, condition, detail=""):
    print(f"{'ok' if condition else 'FAIL'}: {case_name}")
    if not condition:
        failures.append(case_name)
        if detail:
            print(f"      {detail}")


def ship(destination, *args, extra_env=None):
    env = dict(os.environ)
    env[DESTINATION_VARIABLE] = destination
    env.pop(SEAT_VARIABLE, None)
    env.update(extra_env or {})
    return subprocess.run([sys.executable, str(SHIP), *args],
                          capture_output=True, text=True, check=False, env=env)


with tempfile.TemporaryDirectory(prefix="seat-shared-file-ship-test-") as scratch_name:
    scratch = pathlib.Path(scratch_name)
    store_root = scratch / "store"
    # The override names the RECORDS kind, as the record shipper's does; the
    # program derives the seats kind from its parent. Pointing the test at
    # the records path is what proves that derivation.
    local_destination = str(store_root / "cold-read-records")
    seats_root = store_root / "seats"
    work = scratch / "work"
    work.mkdir(parents=True)

    survey = work / "survey-2026-09-08.md"
    survey.write_text("# survey\n\n127 unresolvable, 14 resolvable\n", encoding="utf-8")

    # --- The seat name -----------------------------------------------------
    result = ship(local_destination, str(survey))
    check("with no seat name and no environment, it refuses with exit 64",
          result.returncode == 64 and "no seat name" in result.stderr,
          result.stdout + result.stderr)
    check("the refusal names the environment variable and the shape it wants",
          SEAT_VARIABLE in result.stderr and "nedschorus-<seat>-tasks" in result.stderr,
          result.stderr)

    result = ship(local_destination, str(survey),
                  extra_env={SEAT_VARIABLE: "nedschorus-cold-read-research-tasks"})
    check("the seat name is taken from the supervisor's task-list id",
          result.returncode == 0
          and (seats_root / "cold-read-research" / survey.name).is_file(),
          result.stdout + result.stderr)

    result = ship(local_destination, str(survey), "--seat", "merge-lane")
    check("--seat overrides the environment",
          result.returncode == 0
          and (seats_root / "merge-lane" / survey.name).is_file(),
          result.stdout + result.stderr)

    for bad in ("a/b", "..", "."):
        result = ship(local_destination, str(survey), "--seat", bad)
        check(f"a seat name of {bad!r} is refused as not one path segment",
              result.returncode == 64, result.stdout + result.stderr)

    result = ship(local_destination, str(survey),
                  extra_env={SEAT_VARIABLE: "some-other-tool-list"})
    check("a task-list id of another shape yields no seat name, not a guess",
          result.returncode == 64, result.stdout + result.stderr)

    # --- The citation is the whole of stdout -------------------------------
    fresh = work / "measurement.md"
    fresh.write_text("# measurement\n", encoding="utf-8")
    result = ship(local_destination, str(fresh), "--seat", "cold-read-research")
    expected_citation = str(seats_root / "cold-read-research" / "measurement.md")
    check("stdout is exactly one line and it is the citation to paste",
          result.stdout.strip() == expected_citation
          and result.stdout.count("\n") == 1,
          repr(result.stdout))

    # --- Rule 1, add-only; rule 2, refuse on difference --------------------
    stored = seats_root / "cold-read-research" / "measurement.md"
    mtime_before = stored.stat().st_mtime_ns
    result = ship(local_destination, str(fresh), "--seat", "cold-read-research")
    check("shipping the identical file again exits 0 and copies nothing",
          result.returncode == 0 and "byte-identical" in result.stderr
          and stored.stat().st_mtime_ns == mtime_before,
          result.stdout + result.stderr)
    check("the identical re-ship still prints the citation, so it is always "
          "obtainable", result.stdout.strip() == expected_citation, result.stdout)

    fresh.write_text("# measurement\n\nrevised\n", encoding="utf-8")
    result = ship(local_destination, str(fresh), "--seat", "cold-read-research")
    check("a different file of the same name is REFUSED with exit 2",
          result.returncode == 2 and result.stdout.startswith("REFUSED:"),
          result.stdout + result.stderr)
    check("the refusal copied nothing, leaving the stored file as it was",
          stored.read_text(encoding="utf-8") == "# measurement\n"
          and stored.stat().st_mtime_ns == mtime_before)
    check("the refusal prints both digests and the scp command to read the "
          "stored one",
          "store has sha256" in result.stderr and "scp " in result.stderr,
          result.stderr)

    result = ship(local_destination, str(fresh), "--seat", "cold-read-research",
                  "--as", "measurement-2.md")
    check("--as ships the revision under another name, exit 0",
          result.returncode == 0
          and (seats_root / "cold-read-research" / "measurement-2.md").is_file(),
          result.stdout + result.stderr)
    check("the citation printed is the --as name, not the local one",
          result.stdout.strip().endswith("/measurement-2.md"), result.stdout)

    result = ship(local_destination, str(fresh), str(survey), "--seat", "x",
                  "--as", "one.md")
    check("--as with two files is a bad invocation, exit 64",
          result.returncode == 64, result.stdout + result.stderr)
    result = ship(local_destination, str(fresh), "--seat", "x", "--as", "a/b.md")
    check("--as with a path separator is a bad invocation, exit 64",
          result.returncode == 64, result.stdout + result.stderr)

    # --- Rule 3, and the not-a-file case -----------------------------------
    result = ship(local_destination, str(work / "no-such-file.md"),
                  "--seat", "cold-read-research")
    check("a missing file FAILS with exit 1 and says which",
          result.returncode == 1 and result.stdout.startswith("FAILED:")
          and "no-such-file.md" in result.stdout, result.stdout)

    result = ship(local_destination, str(work), "--seat", "cold-read-research")
    check("a directory is not a file and FAILS rather than shipping a tree",
          result.returncode == 1 and result.stdout.startswith("FAILED:"),
          result.stdout)

    # --- Several files in one run, worst outcome is the exit code ----------
    good = work / "good.md"
    good.write_text("# good\n", encoding="utf-8")
    result = ship(local_destination, str(good), str(work / "missing.md"),
                  "--seat", "cold-read-research")
    check("one good file and one missing: the good one ships and the exit is 1",
          result.returncode == 1
          and (seats_root / "cold-read-research" / "good.md").is_file()
          and len(result.stdout.strip().splitlines()) == 2, result.stdout)

    # --- The README gains the kind, and is appended to, never rewritten ----
    readme = store_root / "README.md"
    readme.write_text("# nedschorus-logs\n\n- `cold-read-records/` -- runs.\n",
                      encoding="utf-8")
    result = ship(local_destination, str(good), "--seat", "late-seat")
    text = readme.read_text(encoding="utf-8")
    check("an existing README gains the seats bullet",
          "`seats/`" in text and "organized by PRODUCER" in text, text)
    check("the append kept every line the README already had",
          text.startswith("# nedschorus-logs\n\n- `cold-read-records/` -- runs.\n"),
          text)
    before = text
    ship(local_destination, str(good), "--seat", "late-seat-2")
    check("a README that already describes the kind is not appended to twice",
          readme.read_text(encoding="utf-8") == before)

    # --- A store this program writes first is born with the whole README ---
    born_here_root = scratch / "store-born-here"
    result = ship(str(born_here_root / "cold-read-records"), str(good),
                  "--seat", "cold-read-research")
    born_here_readme = born_here_root / "README.md"
    born_here_text = (born_here_readme.read_text(encoding="utf-8")
                      if born_here_readme.is_file() else "")
    check("a store root with no README gets the record shipper's whole store "
          "README, not a lone bullet and not nothing",
          result.returncode == 0
          and born_here_text == record_shipper.STORE_README,
          result.stdout + result.stderr + repr(born_here_text[:200]))
    check("that README already lists the seats kind, so no bullet is appended "
          "to it",
          born_here_text.count("`seats/`") == 1
          and "organized by PRODUCER" in born_here_text, born_here_text)

    # --- The two copies of the bullet must not drift -----------------------
    bullet_start = "- `seats/` -- the one kind organized by PRODUCER"
    ship_text = SHIP.read_text(encoding="utf-8")
    record_text = RECORD_SHIP.read_text(encoding="utf-8")
    check("the seats bullet is in both programs, so a fresh store is born "
          "complete and an old one is completed on first use",
          bullet_start in ship_text and bullet_start in record_text)
    ship_bullet = ship_text.split(bullet_start, 1)[1].split('"""', 1)[0]
    record_bullet = record_text.split(bullet_start, 1)[1].split("\n\n", 1)[0]
    check("the two copies of the bullet are the same text",
          ship_bullet.strip().rstrip('\\n').strip()
          == record_bullet.strip().rstrip('\\n').strip(),
          f"{ship_bullet!r}\n      {record_bullet!r}")

    # --- REMOTE mode: read the invocation without a network ----------------
    stub_dir = scratch / "stubs"
    stub_dir.mkdir()
    argv_log = scratch / "argv.log"
    for name in ("ssh", "rsync"):
        stub = stub_dir / name
        stub.write_text(STUB_RECORDER, encoding="utf-8")
        stub.chmod(0o755)
    remote_env = {
        "PATH": f"{stub_dir}{os.pathsep}{os.environ['PATH']}",
        "SEAT_SHIP_TEST_ARGV_LOG": str(argv_log),
    }
    result = ship(RULED_RECORDS_DESTINATION, str(good),
                  "--seat", "cold-read-research", extra_env=remote_env)
    calls = [json.loads(line) for line in
             argv_log.read_text(encoding="utf-8").splitlines()]
    ssh_calls = [c for c in calls if c[0].endswith("ssh")]
    rsync_calls = [c for c in calls if c[0].endswith("rsync")]
    check("the remote run prints the ruled seats citation, derived from the "
          "records constant",
          result.stdout.strip()
          == f"{RULED_SEATS_DESTINATION}/cold-read-research/good.md",
          result.stdout + result.stderr)
    check("every ssh call is batch mode with a connect timeout, so nothing "
          "waits on a prompt",
          ssh_calls and all("BatchMode=yes" in " ".join(c)
                            and "ConnectTimeout=10" in " ".join(c)
                            for c in ssh_calls), str(ssh_calls))
    readme_calls = [c for c in ssh_calls
                    if "mkdir -p" in " ".join(c)
                    and "seats/cold-read-research" in " ".join(c)]
    check("one ssh call makes the seat's directory and carries the README "
          "program, which adds the kind only when it is absent",
          len(readme_calls) == 1
          and "`seats/`" in " ".join(readme_calls[0])
          and "README.md" in " ".join(readme_calls[0]),
          str(ssh_calls))
    check("the remote README is written whole and renamed, never appended in "
          "place, so an interrupted run leaves no half file",
          "os.replace" in " ".join(readme_calls[0])
          and ".new" in " ".join(readme_calls[0]), str(readme_calls))
    check("one ssh call asks for the stored file's sha256 before copying",
          any("sha256sum" in " ".join(c) for c in ssh_calls), str(ssh_calls))
    check("exactly one rsync call, into the seat's own directory, over batch "
          "ssh",
          len(rsync_calls) == 1 and "-a" in rsync_calls[0]
          and "ssh -o BatchMode=yes -o ConnectTimeout=10" in rsync_calls[0]
          and rsync_calls[0][-2] == str(good)
          and rsync_calls[0][-1]
          == f"{RULED_SEATS_DESTINATION}/cold-read-research/good.md",
          str(rsync_calls))
    check("rsync is never asked to delete or to write in place",
          not any(flag in rsync_calls[0] for flag in ("--delete", "--inplace")),
          str(rsync_calls))
    # The store's location is defined once, in the record shipper. This
    # program may READ that constant -- the citation host comes from it --
    # but every mention must be an attribute of the imported shipper, and the
    # store's path must not be written out again here in any form.
    ship_code = ship_text.split('"""', 2)[2]
    check("the seats path is derived from the record shipper's constant, not "
          "written again here",
          all(before.endswith("shipper.")
              for before in ship_code.split("LOG_STORE")[:-1])
          and "nedschorus-logs" not in ship_code,
          "the seats program should hold no store constant of its own")

    # --- IN-PROCESS: on ned-box the copy is local, the citation is not ------
    saved_gethostname = socket.gethostname
    saved_destination = os.environ.pop(DESTINATION_VARIABLE, None)
    try:
        socket.gethostname = lambda: "ned-box"
        on_ned_box = load_ship_module(
            "seat_shared_file_ship_on_ned_box").seats_path_for_this_machine()
        socket.gethostname = lambda: "some-other-machine"
        off_the_store = load_ship_module(
            "seat_shared_file_ship_off_the_store").seats_path_for_this_machine()
    finally:
        socket.gethostname = saved_gethostname
        if saved_destination is not None:
            os.environ[DESTINATION_VARIABLE] = saved_destination

    check("on ned-box the COPY needs no host, the store being a directory on "
          "that machine's own disk",
          two_hosts_of(on_ned_box)[0] is None, repr(on_ned_box))
    check("on ned-box the CITATION still names the host, so the line pasted "
          "into a document resolves from the Mac as well",
          two_hosts_of(on_ned_box)[1] == "nedlern@ned-box", repr(on_ned_box))
    check("what ned-box prints is the ruled scp-form seats citation",
          f"{two_hosts_of(on_ned_box)[1]}:{on_ned_box[-1]}"
          == RULED_SEATS_DESTINATION, repr(on_ned_box))
    check("off the store's machine the two hosts are the same host, the "
          "store's",
          two_hosts_of(off_the_store) == ("nedlern@ned-box", "nedlern@ned-box"),
          repr(off_the_store))

    citation_module = load_ship_module("seat_shared_file_ship_citation_host")
    check("the program keeps the copy's host and the citation's host apart in "
          "one named value",
          hasattr(citation_module, "SeatsStoreDestination"),
          "a destination with a copy host and a citation host is what stops "
          "the two being collapsed back into one")
    if hasattr(citation_module, "SeatsStoreDestination"):
        # The whole finding, end to end and without a network: a copy made
        # locally, as it is on ned-box, whose citation carries the host.
        hosted_root = scratch / "store-hosted-citation"
        hosted = citation_module.SeatsStoreDestination(
            copy_host=None,
            citation_host="nedlern@ned-box",
            seats_path=hosted_root / "seats")
        stored_good = hosted_root / "seats" / "cold-read-research" / "good.md"
        hosted_citation = f"nedlern@ned-box:{stored_good}"
        printed, complained = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(printed), \
                contextlib.redirect_stderr(complained):
            outcome = citation_module.ship_one_file(
                hosted, "cold-read-research", good, "good.md")
        check("a copy made locally still prints a citation carrying the host, "
              "which is what ned-box must print",
              outcome == 0 and printed.getvalue().strip() == hosted_citation,
              printed.getvalue() + complained.getvalue())
        check("the local copy really happened, with no ssh in it",
              stored_good.is_file())

        printed, complained = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(printed), \
                contextlib.redirect_stderr(complained):
            refusal = citation_module.ship_one_file(
                hosted, "cold-read-research", survey, "good.md")
        check("the refusal's scp hint carries the host too, so the stored "
              "file can actually be fetched",
              refusal == 2 and f"scp {hosted_citation} ./" in complained.getvalue(),
              printed.getvalue() + complained.getvalue())

print()
if failures:
    print(f"{len(failures)} case(s) FAILED:")
    for name in failures:
        print(f"  - {name}")
    sys.exit(1)
print("all cases passed")
