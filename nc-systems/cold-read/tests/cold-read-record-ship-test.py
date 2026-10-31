#!/usr/bin/env python3
"""Tests for nc-systems/cold-read/cold-read-record-ship.py: the four rules, the exits, the
one-line stdout, --all, and the shape of the remote invocation.

Two modes, as the script's docstring says. LOCAL: the destination override
names a scratch directory and the real rsync on this machine does the copy,
so add-only, refuse-on-difference, the triage.md replacement and the README
are exercised for real.
REMOTE: the override is the ruled scp-form destination and stub `ssh` and
`rsync` binaries on PATH record what they were asked, so the case reads the
invocation without a network. Nothing here touches ned-box.

IN-PROCESS: the program is loaded with importlib and `socket.gethostname` is
patched, the only way to reach the ned-box branch -- a subprocess's hostname
cannot be faked -- where the copy is local but the printed citation must
still name the host (nedschorus#299). Nothing here touches ned-box.

Run: python3 nc-systems/cold-read/tests/cold-read-record-ship-test.py   (exit 0 = all passed)
"""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import socket
import pathlib
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

# This suite sits in nc-systems/cold-read/tests/; the programs it tests are
# one directory up.
SYSTEM_DIRECTORY = pathlib.Path(__file__).resolve().parent.parent
SHIP = SYSTEM_DIRECTORY / "cold-read-record-ship.py"
DESTINATION_VARIABLE = "COLD_READ_RECORD_SHIP_DESTINATION"
RULED_DESTINATION = "nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records"

# What a stub `ssh` answers to the call that runs the placing step: the outcome of a store no other shipment is writing to, in which every
# file the request names is new and lands with the bytes the shipment asked
# for -- except triage.md when the environment says the store already holds
# one, which the step replaces, announcing the digest it held. The request
# arrives as JSON on stdin; it is appended to the log beside the argv log.
STUB_ANSWER_TO_PLACING = """
script = sys.argv[-1]
if "# cold-read-record-ship: place staged files" in script:
    request = json.load(sys.stdin)
    with open(os.environ["RECORD_SHIP_TEST_ARGV_LOG"] + ".requests", "a") as log:
        log.write(json.dumps(request) + "\\n")
    local = request["local_digests"]
    held_triage = os.environ.get("RECORD_SHIP_TEST_STORED_TRIAGE_DIGEST")
    replaceable = request["replaceable"]
    displaced = held_triage if held_triage and replaceable in local else None
    added = sorted(relative for relative in local
                   if not (displaced and relative == replaceable))
    print(json.dumps({"differing": [], "added": added,
                      "displaced": displaced, "stored": dict(local)}))
    sys.exit(0)
"""

# The stub for both `ssh` and `rsync`: append argv to the log named in the
# environment and exit 0 printing nothing, which for the inventory call
# means "no such directory in the store yet", and answer the placing call.
STUB_RECORDER = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["RECORD_SHIP_TEST_ARGV_LOG"], "a") as log:
    log.write(json.dumps(sys.argv) + "\\n")
""" + STUB_ANSWER_TO_PLACING

# A stub `ssh` that records what it was asked as the recorder above does and
# ANSWERS the inventory call: the script that runs sha256sum gets one line
# naming triage.md with the digest the environment holds, which is a store
# that already keeps a triage from before the approval-walk. Every other file
# is absent from the answer and so is new. Without an answer no remote case
# ever reaches the replace path, every file there looking new.
STUB_INVENTORY_ANSWERING_SSH = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["RECORD_SHIP_TEST_ARGV_LOG"], "a") as log:
    log.write(json.dumps(sys.argv) + "\\n")
""" + STUB_ANSWER_TO_PLACING + """
if "sha256sum" in sys.argv[-1]:
    print(os.environ["RECORD_SHIP_TEST_STORED_TRIAGE_DIGEST"] + "  ./triage.md")
"""

failures = []


def check(case_name, condition, detail=""):
    print(f"{'ok' if condition else 'FAIL'}: {case_name}")
    if not condition:
        failures.append(case_name)
        if detail:
            print(f"      {detail}")


def leftover_temporaries(root: pathlib.Path) -> list:
    """The names of every temporary the README refresh left in the store's
    root. Globbed rather than named, both sites now taking a unique name from
    mktemp or mkstemp instead of a fixed README.md.new."""
    return sorted(p.name for p in root.glob("README.md.*"))


def make_record(root: pathlib.Path, name: str, files: dict) -> pathlib.Path:
    record = root / name
    record.mkdir(parents=True, exist_ok=True)
    for relative, text in files.items():
        path = record / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return record


def ship(destination, *args, extra_env=None, script=SHIP, current_directory=None):
    env = dict(os.environ)
    env[DESTINATION_VARIABLE] = destination
    env.update(extra_env or {})
    return subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True, check=False, env=env,
                          cwd=current_directory)


REPORT_A = "<!-- provenance: runtime=claude model=opus -->\n# A\n\nfinding one\n"
REPORT_B = "<!-- provenance: runtime=codex model=gpt -->\n# B\n\nfinding two\n"

with tempfile.TemporaryDirectory(prefix="cold-read-record-ship-test-") as scratch_name:
    # Resolved: the shipper resolves the record path, and the suite runner's TMPDIR is a symlink.
    scratch = pathlib.Path(scratch_name).resolve()
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
    # The README lists each kind with its owner and nothing else (user-ruled
    # 2026-09-27, walk file-naming-page-revision-2026-09-23, item 9): every
    # owner it names by path must exist, and no naming rule may come back.
    readme_text = (store_root / "README.md").read_text(encoding="utf-8")
    check("the README lists all twelve kinds",
          all(f"- `{kind}/` -- " in readme_text
              for kind in ("cold-read-records", "sanity-check-records", "walk",
                           "agent-session-files-by-machine", "session-dialogs", "seats", "analysis",
                           "daily-full-test-runs", "pull-request-head-test-runs",
                           "daily-memory-review-marks",
                           "handoff-agent-seat-died-without-session-handoff-restart-watcher",
                           "uncommitted-work-snapshot-hook-real-claude-session-weekly-owner-checks")),
          readme_text)
    readme_owner_paths = [token for token in readme_text.split("`")
                          if token.endswith(".py") and "/" in token]
    repository_root = SYSTEM_DIRECTORY.parent.parent
    check("every program the README names as an owner exists in the repository",
          readme_owner_paths
          and all((repository_root / path).is_file() for path in readme_owner_paths),
          repr(readme_owner_paths))
    check("the README restates no naming rule and no longer points at the "
          "file-naming wiki page",
          "triage.md" not in readme_text and "YYYY" not in readme_text
          and "nedschorus-file-naming-and-location-standards.md" not in readme_text,
          readme_text)
    check("the line names the store path the files went to",
          demo.name in result.stdout and "2 file(s) added" in result.stdout, result.stdout)

    stored_a = store_root / "cold-read-records" / demo.name / "a.md"
    mtime_before = stored_a.stat().st_mtime_ns
    result = ship(local_destination, str(demo))
    check("a second run with nothing new exits 0 and says so",
          result.returncode == 0 and "nothing new" in result.stdout, result.stdout)
    check("the second run touched nothing in the store",
          stored_a.stat().st_mtime_ns == mtime_before)

    # --- The README is refreshed when it differs, not only when absent -----
    # It was written once when the store was new and never again, so every
    # ruling that changed the text left the live file behind (user-ruled
    # 2026-09-19, walk file-naming-and-location-standards-cold-read-findings,
    # item 5). A stale README is the state this checks: not missing, wrong.
    readme_path = store_root / "README.md"
    fresh = readme_path.read_text(encoding="utf-8")
    readme_path.write_text("# stale\n\ndispositions.md\n", encoding="utf-8")
    result = ship(local_destination, str(demo))
    check("a README whose text differs is rewritten from the program's copy",
          result.returncode == 0
          and readme_path.read_text(encoding="utf-8") == fresh, result.stdout)

    readme_mtime_before = readme_path.stat().st_mtime_ns
    result = ship(local_destination, str(demo))
    check("a README that already matches is left alone, not rewritten each run",
          result.returncode == 0
          and readme_path.stat().st_mtime_ns == readme_mtime_before)

    # --- The refreshed README LANDS BY RENAME, at both sites ----------------
    # An interrupted refresh must not leave the live README empty or partial.
    # The ssh link to ned-box dropped eight times across 2026-09-19 and
    # 2026-09-20, the last with `client_loop: send disconnect: Broken pipe`,
    # so an interrupted shipment is a measured condition on this path rather
    # than a hypothetical one, and the README is the store's own index: left
    # half-written, nothing repairs it until a later shipment happens to run
    # to completion.
    #
    # THE INODE IS THE EVIDENCE. A rename gives the README a new inode and
    # publishes the text in one step, so a reader sees the old file whole or
    # the new file whole. Writing over the live file keeps its inode and is
    # the shape that can be caught half-done, so an unchanged inode with
    # changed text is the failure these two cases catch.
    readme_path.write_text("# stale\n\ndispositions.md\n", encoding="utf-8")
    stale_inode = readme_path.stat().st_ino
    result = ship(local_destination, str(demo))
    check("locally the refreshed README is a temporary renamed over the old "
          "one, not the live file written through",
          result.returncode == 0
          and readme_path.read_text(encoding="utf-8") == fresh
          and readme_path.stat().st_ino != stale_inode,
          result.stdout + result.stderr)
    check("locally no temporary is left beside the README once it has landed",
          not leftover_temporaries(store_root),
          str(leftover_temporaries(store_root)))

    # The remote script, replayed by a real /bin/sh, in the three states the
    # store can be in. The suite's stub `ssh` records the invocation and runs
    # nothing, so without this the shell was never parsed or executed by any
    # case -- and the shell is where the landing happens.
    _record_shipper_spec = importlib.util.spec_from_file_location(
        "cold_read_record_ship_replayed", SHIP)
    record_shipper = importlib.util.module_from_spec(_record_shipper_spec)
    _record_shipper_spec.loader.exec_module(record_shipper)

    def remote_readme_script(root: pathlib.Path) -> str:
        return record_shipper.make_directory_and_refresh_readme_script(
            root / "cold-read-records", root)

    def refresh_readme_through_real_sh(root: pathlib.Path, text=None):
        """The remote script for this root, run by a real sh with the text on
        stdin, exactly as ssh delivers it to ned-box's dash. `text` shorter
        than the whole is a stream that ended early."""
        return subprocess.run(
            ["/bin/sh", "-c", remote_readme_script(root)],
            input=record_shipper.STORE_README if text is None else text,
            capture_output=True, text=True, check=False)

    replay_root = scratch / "replayed-store"
    replay_readme = replay_root / "README.md"
    replayed = refresh_readme_through_real_sh(replay_root)
    check("replayed by a real sh on a store that has neither directory nor "
          "README, the script makes both and leaves no temporary",
          replayed.returncode == 0
          and (replay_root / "cold-read-records").is_dir()
          and replay_readme.read_text(encoding="utf-8")
          == record_shipper.STORE_README
          and not leftover_temporaries(replay_root),
          replayed.stdout + replayed.stderr)

    replay_readme.write_text("# stale\n\ndispositions.md\n", encoding="utf-8")
    replay_stale_inode = replay_readme.stat().st_ino
    replayed = refresh_readme_through_real_sh(replay_root)
    check("remotely a stale README is replaced by RENAMING the temporary over "
          "it, so a dropped ssh cannot leave it empty or half-written",
          replayed.returncode == 0
          and replay_readme.read_text(encoding="utf-8")
          == record_shipper.STORE_README
          and replay_readme.stat().st_ino != replay_stale_inode
          and not leftover_temporaries(replay_root),
          replayed.stdout + replayed.stderr)

    replay_inode = replay_readme.stat().st_ino
    replay_mtime = replay_readme.stat().st_mtime_ns
    replayed = refresh_readme_through_real_sh(replay_root)
    check("remotely a README that already matches is neither rewritten nor "
          "renamed over, and the temporary is cleaned up all the same",
          replayed.returncode == 0
          and replay_readme.stat().st_ino == replay_inode
          and replay_readme.stat().st_mtime_ns == replay_mtime
          and not leftover_temporaries(replay_root),
          replayed.stdout + replayed.stderr)

    check("the temporary is made BESIDE the README, in the store's root, so "
          "the rename that lands it stays within one filesystem",
          f"mktemp '{replay_root}/README.md.XXXXXX'"
          in remote_readme_script(replay_root),
          remote_readme_script(replay_root))

    check("the landed README is readable by more than its owner, mktemp "
          "having made the temporary 0600",
          replay_readme.stat().st_mode & 0o444 == 0o444,
          oct(replay_readme.stat().st_mode))

    # --- A STREAM THAT ENDS EARLY IS REFUSED, NOT LANDED --------------------
    # A dropped ssh link is not an error the remote shell can see: it is a
    # clean EOF on a short stream, so `cat` returns 0 on the prefix that
    # arrived, `cmp` finds a real difference, and the rename publishes the
    # truncation over a correct README with the script exiting 0. The merge
    # lane measured exactly that at the previous head on 2026-09-21: a 60-byte
    # prefix replaced the live README, return code 0, nothing on stderr.
    # Killing the writer is a DIFFERENT failure -- there `cat` itself fails --
    # and does not reach this one, so these cases end the stream cleanly.
    good_inode = replay_readme.stat().st_ino
    truncated = refresh_readme_through_real_sh(
        replay_root, record_shipper.STORE_README[:60])
    check("a README text that ends early on a cleanly closed stream is "
          "refused: nothing is landed, the good README keeps its inode and its "
          "text, and the refusal is neither silent nor exit 0",
          truncated.returncode != 0
          and truncated.stderr.strip()
          and replay_readme.read_text(encoding="utf-8")
          == record_shipper.STORE_README
          and replay_readme.stat().st_ino == good_inode
          and not leftover_temporaries(replay_root),
          f"rc={truncated.returncode} stderr={truncated.stderr!r} "
          f"left={leftover_temporaries(replay_root)}")

    truncated_fresh_root = scratch / "replayed-store-that-was-new"
    truncated_fresh = refresh_readme_through_real_sh(
        truncated_fresh_root, record_shipper.STORE_README[:60])
    check("on a store with no README yet, a stream that ends early leaves no "
          "README at all rather than a truncated one",
          truncated_fresh.returncode != 0
          and not (truncated_fresh_root / "README.md").exists()
          and not leftover_temporaries(truncated_fresh_root),
          f"rc={truncated_fresh.returncode} "
          f"left={leftover_temporaries(truncated_fresh_root)}")

    # --- TWO SHIPMENTS PREPARING ONE STORE AT ONCE, at both sites -----------
    # Every shipment of every kind refreshes this README, from every seat, and
    # nothing locks. On one fixed temporary name they collide: the winner's
    # closing `rm -f` falls between the loser's `cat` and its `cmp`, so the
    # loser fails on a store that is correct, and with the two sending
    # different text -- two checkouts at different commits -- the winner's
    # rename takes the inode out from under a writer still holding it open.
    #
    # REMOTELY, with two real shells: each is held in `cat` with its stdin
    # open and nothing written, so both have made their temporary before
    # either lands. That is the state the collision needs, and it is reached by
    # waiting for the temporaries to appear rather than by a timed sleep.
    overlap_root = scratch / "overlapped-replayed-store"
    holders = [subprocess.Popen(
        ["/bin/sh", "-c", remote_readme_script(overlap_root)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True) for _ in range(2)]
    deadline = time.monotonic() + 5
    while (len(leftover_temporaries(overlap_root)) < 2
           and time.monotonic() < deadline):
        time.sleep(0.01)
    temporaries_in_flight = leftover_temporaries(overlap_root)
    finished = [holder.communicate(record_shipper.STORE_README)
                for holder in holders]
    check("remotely, two shipments preparing one store at once each hold "
          "their own temporary, so neither takes the other's: both exit 0 and "
          "the README is whole",
          len(temporaries_in_flight) == 2
          and all(holder.returncode == 0 for holder in holders)
          and (overlap_root / "README.md").read_text(encoding="utf-8")
          == record_shipper.STORE_README
          and not leftover_temporaries(overlap_root),
          f"in flight={temporaries_in_flight} "
          f"rc={[holder.returncode for holder in holders]} "
          f"stderr={[out[1] for out in finished]} "
          f"left={leftover_temporaries(overlap_root)}")

    # LOCALLY, which is the path the seats take: they run on ned-box, where
    # the copy is local and `refresh_store_readme` does the landing. The second
    # shipment here runs INSIDE the first's rename, so the interleaving is
    # exact rather than timed; on one fixed name the first's os.replace then
    # raises FileNotFoundError, an uncaught traceback on a correct store.
    local_overlap_root = scratch / "overlapped-local-store"
    local_overlap_root.mkdir()
    local_overlap_readme = local_overlap_root / "README.md"
    local_overlap_readme.write_text("# stale\n\ndispositions.md\n",
                                    encoding="utf-8")
    temporaries_renamed = []
    real_replace = os.replace
    second_shipment = {"ran": False}

    def replace_with_a_second_shipment_in_flight(source, target):
        temporaries_renamed.append(pathlib.Path(source).name)
        if not second_shipment["ran"]:
            second_shipment["ran"] = True
            record_shipper.refresh_store_readme(local_overlap_root)
        return real_replace(source, target)

    os.replace = replace_with_a_second_shipment_in_flight
    try:
        record_shipper.refresh_store_readme(local_overlap_root)
        overlap_failure = None
    except OSError as error:
        overlap_failure = error
    finally:
        os.replace = real_replace
    check("locally, a second shipment landing inside the first's rename does "
          "not take the first's temporary: the two names differ, both land, "
          "and neither raises",
          overlap_failure is None
          and second_shipment["ran"]
          and len(set(temporaries_renamed)) == 2
          and local_overlap_readme.read_text(encoding="utf-8")
          == record_shipper.STORE_README
          and not leftover_temporaries(local_overlap_root),
          f"{overlap_failure!r} renamed={temporaries_renamed} "
          f"left={leftover_temporaries(local_overlap_root)}")
    check("locally too the landed README is readable by more than its owner, "
          "mkstemp having made the temporary 0600",
          local_overlap_readme.stat().st_mode & 0o444 == 0o444,
          oct(local_overlap_readme.stat().st_mode))

    (demo / "triage.md").write_text("# triage\n\nnone\n", encoding="utf-8")
    result = ship(local_destination, str(demo))
    check("triage.md written later joins the reports on the next run",
          result.returncode == 0 and "1 file(s) added" in result.stdout
          and (store_root / "cold-read-records" / demo.name / "triage.md").is_file(),
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
    check("the refusal tells the person what to do: the mv to a free name and the ship command",
          f"`mv {demo} {records / '2026-09-07-demo-2'}`, a name free in this checkout and "
          f"in the store when this ran, then ship the renamed directory with "
          f"`{SHIP} {records / '2026-09-07-demo-2'}`." in result.stdout, result.stdout)
    check("nothing was copied on a refused run, not even the new file",
          not (store_root / "cold-read-records" / demo.name / "late.md").exists()
          and stored_a.read_text(encoding="utf-8") == REPORT_A)
    (demo / "a.md").write_text(REPORT_A, encoding="utf-8")

    stored_b = store_root / "cold-read-records" / demo.name / "b.md"
    (demo / "a.md").write_text(
        "<!-- provenance: runtime=claude model=opus-rerun -->\n# A\n\nfinding one, reworded\n",
        encoding="utf-8")
    (demo / "b.md").write_text(
        "<!-- provenance: runtime=codex model=gpt-rerun -->\n# B\n\nfinding two, reworded\n",
        encoding="utf-8")
    result = ship(local_destination, str(demo))
    check("two differing files at once are REFUSED with exit 2",
          result.returncode == 2 and result.stdout.startswith("REFUSED:"), result.stdout)
    check("two differing files still make exactly one stdout line",
          result.stdout.count("\n") == 1, result.stdout)
    check("the one line names both files and carries all four provenance comments",
          "a.md" in result.stdout and "b.md" in result.stdout
          and "model=opus " in result.stdout and "model=opus-rerun" in result.stdout
          and "model=gpt " in result.stdout and "model=gpt-rerun" in result.stdout,
          result.stdout)
    check("nothing was copied on the two-file refusal either",
          not (store_root / "cold-read-records" / demo.name / "late.md").exists()
          and stored_a.read_text(encoding="utf-8") == REPORT_A
          and stored_b.read_text(encoding="utf-8") == REPORT_B)
    (demo / "a.md").write_text(REPORT_A, encoding="utf-8")
    (demo / "b.md").write_text(REPORT_B, encoding="utf-8")

    # A differing file with no provenance comment, on a file that is NOT
    # triage.md: since the 2026-09-20 ruling triage.md is replaced rather than
    # refused, and this case is about the refusal's text.
    notes = demo / "notes-with-no-provenance.md"
    notes.write_text("# notes\n\nas shipped\n", encoding="utf-8")
    ship(local_destination, str(demo))
    notes.write_text("# notes\n\nreworded\n", encoding="utf-8")
    result = ship(local_destination, str(demo))
    check("a differing file with no provenance comment says so instead of crashing",
          result.returncode == 2 and "(no provenance comment)" in result.stdout, result.stdout)
    notes.write_text("# notes\n\nas shipped\n", encoding="utf-8")

    # --- Rule 4: the record's triage.md is REPLACED, each displaced copy's
    # sha256 announced ------------------------------------------------------
    #
    # triage.md is the one file in a cold-read-record written twice on purpose:
    # the agent triages the reviewers' findings into it, then it is written
    # again with the user's rulings once the approval-walk closes. Add-only
    # refused that second write. The post-walk triage of the record
    # 2026-09-14-nedschorus-file-naming-and-location-standards-3 reached the
    # store on 2026-09-20 only because the file had also been renamed
    # dispositions.md -> triage.md two days earlier, so the shipper saw a name
    # it did not hold; under its old name five of the user's rulings would have
    # been refused (user-ruled 2026-09-20, item 4 of the walk
    # md-skills-seat-open-decisions-2026-09-20).
    #
    # late.md, which the refusal cases left on disk, reached the store with
    # the notes above and stays in the local directory: a store record holding
    # a file the local one lacks is refused as another read's.
    stored_triage = store_root / "cold-read-records" / demo.name / "triage.md"
    triage_as_first_shipped = stored_triage.read_text(encoding="utf-8")
    displaced_digest = hashlib.sha256(
        triage_as_first_shipped.encode("utf-8")).hexdigest()
    triage_after_the_walk = "# triage\n\nfinding one: applied after the walk.\n"
    landed_digest = hashlib.sha256(triage_after_the_walk.encode("utf-8")).hexdigest()
    (demo / "triage.md").write_text(triage_after_the_walk, encoding="utf-8")
    result = ship(local_destination, str(demo))
    check("a triage.md rewritten after the approval-walk replaces the store's "
          "copy instead of being refused",
          result.returncode == 0 and result.stdout.startswith("shipped:")
          and result.stdout.count("\n") == 1
          and stored_triage.read_text(encoding="utf-8") == triage_after_the_walk,
          f"exit {result.returncode}: {result.stdout}{result.stderr}")
    check("the one stdout line says the triage was replaced, and the citation "
          "still names the record in the store",
          "triage.md replaced" in result.stdout and demo.name in result.stdout,
          result.stdout)
    check("the displaced copy's sha256 and the landed one are announced on "
          "stderr, so a triage shipped three times leaves a trace of each",
          "REPLACED" in result.stderr and displaced_digest in result.stderr
          and landed_digest in result.stderr, result.stderr)
    check("the replacement is announced on stderr and never on the one stdout line",
          "REPLACED" not in result.stdout, result.stdout)
    check("the replacement tells the agent to match the displaced digest across the snapshots at the file's full path in the store on ned-box, not to search by path: a replaced file keeps its path, so the newest snapshots holding it hold the replacement",
          ("sha256sum /mnt/backup/timeshift/snapshots/*/localhost"
           f"/home/nedlern/nedschorus-logs/cold-read-records/{demo.name}/triage.md") in result.stderr
          and "find-deleted-path-across-backups" not in result.stderr
          and "sudo timeshift --list" not in result.stderr
          and "every ten minutes" not in result.stderr, result.stderr)

    stored_report_mtime = stored_a.stat().st_mtime_ns
    triage_mtime_after_replacement = stored_triage.stat().st_mtime_ns
    result = ship(local_destination, str(demo))
    check("a triage.md identical to the store's is not rewritten and nothing "
          "is announced",
          result.returncode == 0 and "nothing new" in result.stdout
          and "REPLACED" not in result.stderr
          and stored_triage.stat().st_mtime_ns == triage_mtime_after_replacement
          and stored_a.stat().st_mtime_ns == stored_report_mtime,
          f"{result.stdout}{result.stderr}")

    # A same-length revision carrying the stored copy's own modification time:
    # rsync's quick check is size and modification time to the second, and it
    # skips a file the two agree on -- measured on this Mac's openrsync, where a
    # 5-byte file with a matching mtime was not copied without --ignore-times.
    # Without the flag the store would keep its old bytes behind a line saying
    # they had been replaced. The two revisions must be the same length or the
    # case stops asking that question, so the case checks that first.
    same_length_revision = "# triage\n\nfinding one: refused after the walk.\n"
    check("the two triage revisions are the same length, which is what puts "
          "rsync's size-and-time check in play",
          len(same_length_revision) == len(triage_after_the_walk),
          f"{len(same_length_revision)} vs {len(triage_after_the_walk)}")
    (demo / "triage.md").write_text(same_length_revision, encoding="utf-8")
    stored_times = stored_triage.stat()
    os.utime(demo / "triage.md",
             ns=(stored_times.st_atime_ns, stored_times.st_mtime_ns))
    result = ship(local_destination, str(demo))
    check("a same-length triage.md carrying the stored copy's own modification "
          "time is still copied, not skipped by rsync's size-and-time check",
          result.returncode == 0
          and stored_triage.read_text(encoding="utf-8") == same_length_revision,
          f"exit {result.returncode}: {result.stdout}{result.stderr}")

    # Rule 2 still governs the rest of the record, and a refused run copies
    # nothing -- the triage included, however replaceable it is on its own.
    (demo / "a.md").write_text(
        "<!-- provenance: runtime=claude model=opus-rerun -->\n# A\n\nfinding one, reworded\n",
        encoding="utf-8")
    (demo / "triage.md").write_text("# triage\n\nwritten during a refusal\n",
                                    encoding="utf-8")
    result = ship(local_destination, str(demo))
    check("a differing report is REFUSED with exit 2 even though the triage "
          "beside it is replaceable",
          result.returncode == 2 and result.stdout.startswith("REFUSED:")
          and "a.md" in result.stdout, result.stdout)
    check("the refused run replaced nothing: the store keeps the triage it had "
          "and says nothing about a replacement",
          stored_triage.read_text(encoding="utf-8") == same_length_revision
          and "REPLACED" not in result.stderr,
          stored_triage.read_text(encoding="utf-8") + result.stderr)
    (demo / "a.md").write_text(REPORT_A, encoding="utf-8")
    (demo / "triage.md").write_text(same_length_revision, encoding="utf-8")

    # ONLY THE RECORD'S OWN triage.md. Under target/ lie the frozen
    # cold-read-target's bytes at its own repository path, so a document named
    # triage.md that was itself reviewed lives there -- and it is a report's
    # peer, add-only, never the record's triage.
    frozen_triage = demo / "target" / "docs" / "triage.md"
    frozen_triage.parent.mkdir(parents=True, exist_ok=True)
    frozen_triage.write_text("# the reviewed document\n\nas read\n", encoding="utf-8")
    result = ship(local_destination, str(demo))
    check("the frozen cold-read-target's own triage.md ships as an ordinary "
          "added file",
          result.returncode == 0 and "1 file(s) added" in result.stdout,
          f"exit {result.returncode}: {result.stdout}{result.stderr}")
    stored_frozen_triage = (store_root / "cold-read-records" / demo.name
                            / "target" / "docs" / "triage.md")
    frozen_triage.write_text("# the reviewed document\n\nedited\n", encoding="utf-8")
    result = ship(local_destination, str(demo))
    check("a triage.md under the frozen cold-read-target is REFUSED, not "
          "replaced: only the record's own top-level triage.md is replaceable",
          result.returncode == 2 and result.stdout.startswith("REFUSED:")
          and "target/docs/triage.md" in result.stdout
          and stored_frozen_triage.read_text(encoding="utf-8")
          == "# the reviewed document\n\nas read\n",
          f"exit {result.returncode}: {result.stdout}")
    frozen_triage.write_text("# the reviewed document\n\nas read\n", encoding="utf-8")

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
    # The whole nc-systems/cold-read/ directory, __pycache__ aside, so a shared module
    # added tomorrow needs no edit here (user-ruled 2026-09-20, walk
    # md-skills-seat-open-decisions-2026-09-20 item 3).
    shutil.copytree(SYSTEM_DIRECTORY, scratch_repo / "nc-systems" / "cold-read",
                    ignore=shutil.ignore_patterns("__pycache__"))
    scratch_ship = scratch_repo / "nc-systems" / "cold-read" / SHIP.name
    all_store = str(scratch / "store-all" / "cold-read-records")
    good = make_record(scratch_repo / "cold-read-records", "2026-09-01-good", {"r.md": REPORT_A})
    bad = make_record(scratch_repo / "cold-read-records", "2026-09-02-bad", {"r.md": REPORT_B})
    (scratch_repo / "cold-read-records" / "stray-file.txt").write_text("not a directory\n")
    make_record(scratch_repo / "cold-read-records", "2026-08-30-empty", {})
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
          "stray-file" not in result.stdout and "of 3" in lines[-1], result.stdout)
    check("--all skips an empty directory with a note and counts it skipped, not failed",
          any(line == "skipped: 2026-08-30-empty — empty directory" for line in lines)
          and "0 failed" in lines[-1] and "1 skipped (2026-08-30-empty)" in lines[-1],
          result.stdout)
    # With the refused directory made good again, an empty one alone leaves
    # --all at exit 0: the finding from PR #285's review was that it did not.
    (bad / "r.md").write_text(REPORT_B, encoding="utf-8")
    result = ship(all_store, "--all", script=scratch_ship)
    check("an empty directory alone does not make --all exit non-zero",
          result.returncode == 0 and "1 skipped" in result.stdout.splitlines()[-1],
          f"exit {result.returncode}: {result.stdout}")

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
    check("the store is prepared over ssh: mkdir -p of the records path and the README",
          any("mkdir -p" in " ".join(c) and "README.md" in " ".join(c)
              and "/home/nedlern/nedschorus-logs/cold-read-records" in " ".join(c)
              for c in ssh_calls), str(ssh_calls))
    check("the README is compared and renamed into place only on a "
          "difference, never written only when absent",
          any("cmp -s" in " ".join(c) and "mv --" in " ".join(c)
              and "test -e" not in " ".join(c)
              for c in ssh_calls if "README.md" in " ".join(c)), str(ssh_calls))
    check("the store's inventory is one ssh call running sha256sum under the record's directory",
          any("sha256sum" in " ".join(c) and f"cold-read-records/{demo.name}" in " ".join(c)
              for c in ssh_calls), str(ssh_calls))
    staging_prefix = f"{RULED_DESTINATION}/.ship-staging-{demo.name}-"
    check("exactly one rsync call, over batch-mode ssh, into a staging "
          "directory beside the record's own, named for the record",
          len(rsync_calls) == 1 and "-a" in rsync_calls[0]
          and "ssh -o BatchMode=yes -o ConnectTimeout=10" in rsync_calls[0]
          and rsync_calls[0][-2] == f"{demo.resolve()}/"
          and re.fullmatch(re.escape(staging_prefix) + "[0-9a-f]{12}/", rsync_calls[0][-1]),
          str(rsync_calls))
    placing_calls = [c for c in ssh_calls
                     if "# cold-read-record-ship: place staged files" in c[-1]]
    inventory_calls = [i for i, c in enumerate(calls) if c[0].endswith("ssh")
                       and "sha256sum" in c[-1] and "place staged files" not in c[-1]]
    copy_indexes = [i for i, c in enumerate(calls) if c[0].endswith("rsync")]
    placing_indexes = [i for i, c in enumerate(calls) if c[0].endswith("ssh")
                       and "place staged files" in c[-1]]
    check("remotely the inventory, the copy into staging and the one placing "
          "step run in that order, and no other ssh call makes or removes a "
          "directory in the store",
          len(inventory_calls) == 1 and len(copy_indexes) == 1
          and len(placing_indexes) == 1
          and inventory_calls[0] < copy_indexes[0] < placing_indexes[0]
          and not any("mkdir --" in c[-1] or "rmdir" in c[-1] for c in ssh_calls),
          f"inventory {inventory_calls} copy {copy_indexes} placing {placing_indexes}")
    staging_used = rsync_calls[0][-1][len(f"{RULED_DESTINATION}/"):].rstrip("/") \
        if rsync_calls else ""
    requests_log = pathlib.Path(f"{argv_log}.requests")
    placing_requests = [json.loads(line) for line in
                        requests_log.read_text().splitlines()] \
        if requests_log.exists() else []
    check("then one ssh call runs the step as a python3 program, its request "
          "-- the record's directory in the store, the staging directory the "
          "copy filled, and every local file's digest -- on stdin, not in the "
          "command line a shell parses",
          len(placing_calls) == 1 and placing_calls[0][-1].startswith("python3 -c ")
          and staging_used not in placing_calls[0][-1]
          and len(placing_requests) == 1
          and placing_requests[0]["store_dir"]
          == f"/home/nedlern/nedschorus-logs/cold-read-records/{demo.name}"
          and placing_requests[0]["staging_dir"]
          == f"/home/nedlern/nedschorus-logs/cold-read-records/{staging_used}"
          and sorted(placing_requests[0]["local_digests"])
          == sorted(p.relative_to(demo).as_posix() for p in demo.rglob("*") if p.is_file()),
          f"{placing_calls} {placing_requests}")
    check("rsync is never asked to delete or to write in place",
          not any(flag in rsync_calls[0] for flag in ("--delete", "--inplace")),
          str(rsync_calls))
    check("the destination constant in the script is the ruled one",
          f'LOG_STORE_RECORDS_DESTINATION = "{RULED_DESTINATION}"'
          in SHIP.read_text(encoding="utf-8"))

    # --- The REPLACEMENT's remote invocation, read from stubs ------------------
    # The recorder above answers the inventory with nothing, so every file looks
    # new to it and the replace path is never reached. This stub `ssh` answers
    # the inventory call with a triage.md digest that differs from the local
    # file's, which is a store that already holds a triage from before the
    # approval-walk.
    answering_stubs = scratch / "stub-bin-answering-the-inventory"
    answering_stubs.mkdir()
    (answering_stubs / "ssh").write_text(STUB_INVENTORY_ANSWERING_SSH, encoding="utf-8")
    (answering_stubs / "ssh").chmod(0o755)
    (answering_stubs / "rsync").write_text(STUB_RECORDER, encoding="utf-8")
    (answering_stubs / "rsync").chmod(0o755)
    stored_triage_digest = "0" * 64
    remote_record = make_record(records, "2026-09-20-remote-replace",
                                {"a.md": REPORT_A,
                                 "triage.md": "# triage\n\nafter the walk\n"})
    replace_log = scratch / "argv-replace.jsonl"
    result = ship(RULED_DESTINATION, str(remote_record), extra_env={
        "PATH": f"{answering_stubs}{os.pathsep}{os.environ.get('PATH', '')}",
        "RECORD_SHIP_TEST_ARGV_LOG": str(replace_log),
        "RECORD_SHIP_TEST_STORED_TRIAGE_DIGEST": stored_triage_digest})
    replace_calls = [json.loads(line) for line in replace_log.read_text().splitlines()]
    replace_rsync_calls = [c for c in replace_calls if c[0].endswith("rsync")]
    check("remotely a triage.md the store already holds with other bytes is "
          "shipped, not refused",
          result.returncode == 0 and result.stdout.startswith("shipped:")
          and "triage.md replaced" in result.stdout,
          f"exit {result.returncode}: {result.stdout}{result.stderr}")
    check("the replacement takes no rsync of its own: the one copy is into "
          "staging, and the placing step renames triage.md from there",
          len(replace_rsync_calls) == 1
          and ".ship-staging-" in replace_rsync_calls[0][-1],
          str(replace_rsync_calls))
    check("the digest the store reported for the displaced triage is announced "
          "on stderr",
          "REPLACED" in result.stderr and stored_triage_digest in result.stderr,
          result.stderr)

    # --- A FAILED ssh IS SAID, NOT READ AS AN ANSWER -------------------------
    # This stub `ssh` answers the inventory with a digest for a.md that is not
    # the local one, fails `head -n 1` and `rm -rf` as a dropped link does, and
    # passes everything else to the recorder. The stub `rsync` exits as
    # RECORD_SHIP_TEST_RSYNC_EXIT says.
    failing_ssh_stubs = scratch / "stub-bin-ssh-failing-reads-and-removals"
    failing_ssh_stubs.mkdir()
    (failing_ssh_stubs / "ssh").write_text(STUB_RECORDER.replace(
        "import json, os, sys\n", "import json, os, sys\n"
        "script = sys.argv[-1]\n"
        "if script.startswith('head -n 1 ') or script.startswith('rm -rf '):\n"
        "    with open(os.environ['RECORD_SHIP_TEST_ARGV_LOG'], 'a') as log:\n"
        "        log.write(json.dumps(sys.argv) + '\\n')\n"
        "    sys.stderr.write('Connection closed by remote host\\n')\n"
        "    sys.exit(255)\n"
        "if 'sha256sum' in script and os.environ.get('RECORD_SHIP_TEST_STORE_HOLDS_OTHER_A'):\n"
        "    print('0' * 64 + '  ./a.md')\n"
        "    sys.exit(0)\n", 1), encoding="utf-8")
    (failing_ssh_stubs / "ssh").chmod(0o755)
    (failing_ssh_stubs / "rsync").write_text(
        "#!/usr/bin/env python3\nimport os, sys\n"
        "sys.exit(int(os.environ.get('RECORD_SHIP_TEST_RSYNC_EXIT', '0')))\n", encoding="utf-8")
    (failing_ssh_stubs / "rsync").chmod(0o755)
    failing_ssh_path = f"{failing_ssh_stubs}{os.pathsep}{os.environ.get('PATH', '')}"

    unread_record = make_record(records, "2026-09-21-store-copy-unread", {"a.md": REPORT_A})
    result = ship(RULED_DESTINATION, str(unread_record), extra_env={
        "PATH": failing_ssh_path,
        "RECORD_SHIP_TEST_ARGV_LOG": str(scratch / "argv-store-copy-unread.jsonl"),
        "RECORD_SHIP_TEST_STORE_HOLDS_OTHER_A": "1"})
    check("a store copy whose first line ssh could not read is REFUSED saying so, "
          "not described as having no provenance comment",
          result.returncode == 2 and result.stdout.startswith("REFUSED:")
          and "store: (could not be read: ssh exit 255: Connection closed by remote host)"
          in result.stdout
          and f"local: {REPORT_A.splitlines()[0]}" in result.stdout,
          f"exit {result.returncode}: {result.stdout}{result.stderr}")

    left_record = make_record(records, "2026-09-21-staging-left", {"a.md": REPORT_A})
    left_log = scratch / "argv-staging-left.jsonl"
    result = ship(RULED_DESTINATION, str(left_record), extra_env={
        "PATH": failing_ssh_path, "RECORD_SHIP_TEST_ARGV_LOG": str(left_log),
        "RECORD_SHIP_TEST_RSYNC_EXIT": "23"})
    removal_calls = [json.loads(line) for line in left_log.read_text().splitlines()
                     if '"rm -rf ' in line]
    staging_named = (shlex.split(removal_calls[0][-1])[-1] if removal_calls else "")
    check("a failed copy whose staging directory ssh could not remove names that "
          "directory and why on the FAILED line",
          result.returncode == 1 and result.stdout.startswith("FAILED:")
          and "rsync exit 23 during the copy" in result.stdout
          and ".ship-staging-2026-09-21-staging-left-" in staging_named
          and f"the staging directory nedlern@ned-box:{staging_named}, if the copy made it, "
              f"could not be removed (ssh exit 255: Connection closed by remote host)"
          in result.stdout
          and f"if {staging_named} is there, delete it" in result.stderr,
          f"exit {result.returncode}: {result.stdout}{result.stderr}; removals={removal_calls}")

    # The local legs, in process: a first line that cannot be read, and a
    # staging path that cannot be removed.
    local_spec = importlib.util.spec_from_file_location("cold_read_record_ship_local_legs", SHIP)
    local_legs = importlib.util.module_from_spec(local_spec)
    local_spec.loader.exec_module(local_legs)
    missing_report = scratch / "no-such-report.md"
    described = local_legs.described_provenance_comment(local_legs.local_first_line, missing_report)
    check("a local first line that cannot be read is described as unreadable",
          described.startswith("(could not be read: ") and str(missing_report) in described,
          described)
    not_a_directory = scratch / "a-file-where-a-staging-directory-was-expected"
    not_a_directory.write_text("x\n", encoding="utf-8")
    check("a local staging path that cannot be removed returns why",
          local_legs.remove_staging_directory(None, not_a_directory) is not None,
          "returned None")
    check("a local staging directory that is already gone is not a failure",
          local_legs.remove_staging_directory(None, scratch / "never-made") is None)

    # --- IN-PROCESS: on ned-box the copy is local, the citation is not ------
    # Loaded in this process so socket.gethostname can be patched; the
    # override is removed so the constant decides, as it does in production.
    saved_gethostname = socket.gethostname
    saved_destination = os.environ.pop(DESTINATION_VARIABLE, None)
    try:
        socket.gethostname = lambda: "ned-box"
        spec = importlib.util.spec_from_file_location("cold_read_record_ship_on_ned_box", SHIP)
        on_ned_box = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(on_ned_box)
        copy_host, _ = on_ned_box.destination_for_this_machine()
        box_store = scratch / "box-store" / "cold-read-records"
        box_record = make_record(scratch / "box-records", "2026-09-09-on-the-box",
                                 {"a.md": REPORT_A})
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            code = on_ned_box.ship_one(copy_host, pathlib.PurePosixPath(box_store), box_record)
    finally:
        socket.gethostname = saved_gethostname
        if saved_destination is not None:
            os.environ[DESTINATION_VARIABLE] = saved_destination

    check("on ned-box the COPY needs no host, the store being a directory on that "
          "machine's own disk", copy_host is None, repr(copy_host))
    check("on ned-box the copy is local and the printed citation still names the "
          "host, so the line pasted into a document resolves from the Mac as well",
          code == 0 and printed.getvalue().startswith("shipped:")
          and f"nedlern@ned-box:{box_store}/{box_record.name}" in printed.getvalue()
          and (box_store / box_record.name / "a.md").read_text(encoding="utf-8") == REPORT_A,
          printed.getvalue())

    # --- TWO SHIPMENTS OF ONE RECORD NAME AT ONCE ----------------------------
    # Two checkouts ship a record of one name in the same second. The other
    # shipment's file is made to land at a chosen moment of this one -- after
    # this one has taken the store's inventory, or after its copy has run -- by
    # wrapping the call that marks that moment, in this process. Whichever
    # shipment's file is not the one the store keeps must not print shipped:.
    racing_spec = importlib.util.spec_from_file_location(
        "cold_read_record_ship_two_shipments", SHIP)
    racing = importlib.util.module_from_spec(racing_spec)
    racing_spec.loader.exec_module(racing)
    saved_destination = os.environ.pop(DESTINATION_VARIABLE, None)
    saved_store_inventory = racing.store_inventory
    saved_subprocess_run = subprocess.run

    def ship_while_the_other_lands(case_label, other_report, moment):
        """Ship a record whose fast-read.md is REPORT_A while the other
        shipment's fast-read.md, `other_report`, lands in the store at
        `moment`: "after-inventory" or "after-copy". Returns the exit code,
        the stdout, the bytes the store keeps, and what the shipment left
        in the store's records directory beside the record."""
        race_store = scratch / f"race-store-{case_label}" / "cold-read-records"
        race_record = make_record(scratch / f"race-records-{case_label}",
                                  "explain-reply-draft-seat-a-151738-2026-10-01",
                                  {"fast-read.md": REPORT_A,
                                   "target/docs/reply.md": "# the reply\n"})
        landed_path = race_store / race_record.name / "fast-read.md"

        def land_the_other():
            landed_path.parent.mkdir(parents=True, exist_ok=True)
            landed_path.write_text(other_report, encoding="utf-8")

        def inventory_then_land(host, store_dir):
            answer = saved_store_inventory(host, store_dir)
            if moment == "after-inventory" and not landed_path.exists():
                land_the_other()
            return answer

        copies_run = []

        def run_then_land(command, *args, **kwargs):
            completed = saved_subprocess_run(command, *args, **kwargs)
            if moment == "after-copy" and command and command[0] == "rsync" \
                    and not copies_run:
                copies_run.append(command)
                # Written over whatever this shipment's copy put there: the
                # other shipment's rsync, which found no file when it looked,
                # renaming its temporary into place after this one's did.
                land_the_other()
            return completed

        printed = io.StringIO()
        racing.store_inventory = inventory_then_land
        subprocess.run = run_then_land
        try:
            with contextlib.redirect_stdout(printed), \
                    contextlib.redirect_stderr(io.StringIO()):
                code = racing.ship_one(None, pathlib.PurePosixPath(race_store),
                                       race_record)
        finally:
            racing.store_inventory = saved_store_inventory
            subprocess.run = saved_subprocess_run
        kept = landed_path.read_text(encoding="utf-8") if landed_path.exists() else None
        beside = sorted(p.name for p in race_store.iterdir() if p.name != race_record.name)
        return code, printed.getvalue(), kept, beside

    try:
        code, out, kept, beside = ship_while_the_other_lands(
            "between-inventory-and-copy", REPORT_B, "after-inventory")
        check("the other shipment's differing report landing between this "
              "shipment's inventory and its copy makes this one REFUSED, never "
              "shipped:, its own report not being what the store keeps",
              code == 2 and out.startswith("REFUSED:") and "fast-read.md" in out
              and out.count("\n") == 1,
              f"exit {code}: {out}")
        check("that refusal leaves the other shipment's report in the store, "
              "not overwritten", kept == REPORT_B, repr(kept))
        check("and the refused shipment placed nothing after the taken file: "
              "its target/ copy, which sorts after fast-read.md, is not in the "
              "store beside the other shipment's report",
              not (scratch / "race-store-between-inventory-and-copy"
                   / "cold-read-records"
                   / "explain-reply-draft-seat-a-151738-2026-10-01"
                   / "target").exists())

        code, out, kept, beside = ship_while_the_other_lands(
            "after-the-copy-ran", REPORT_B, "after-copy")
        check("the other shipment's differing report landing after this "
              "shipment's copy ran still never lets both print shipped: -- "
              "this one refuses, or its report is the one the store keeps",
              (code == 2 and out.startswith("REFUSED:") and kept == REPORT_B)
              or (code == 0 and out.startswith("shipped:") and kept == REPORT_A),
              f"exit {code}: {out}; store keeps {kept!r}")

        code, out, kept, beside = ship_while_the_other_lands(
            "same-bytes", REPORT_A, "after-inventory")
        check("the other shipment landing the SAME bytes between inventory and "
              "copy is no difference: this one is shipped:, exit 0",
              code == 0 and out.startswith("shipped:") and kept == REPORT_A,
              f"exit {code}: {out}")
        check("a shipment leaves nothing in the store beside the record "
              "directory, whether it shipped or refused",
              beside == [] and not any(
                  p.name != "explain-reply-draft-seat-a-151738-2026-10-01"
                  for case_label in ("between-inventory-and-copy",
                                     "after-the-copy-ran", "same-bytes")
                  for p in (scratch / f"race-store-{case_label}"
                            / "cold-read-records").iterdir()),
              str(beside))
    finally:
        if saved_destination is not None:
            os.environ[DESTINATION_VARIABLE] = saved_destination

    # The step ned-box runs, as the python3 program the ssh call sends, run by
    # a real sh and python3 on scratch paths with its request on stdin. The
    # stubs above answer it without running it, so this is where the program
    # as sent -- the function's own source and the line that drives it -- is
    # parsed and executed.
    def step_through_real_python3(case_label, stored):
        staging = scratch / f"placing-{case_label}" / ".ship-staging-r-0"
        store = scratch / f"placing-{case_label}" / "r"
        contents = {"a.md": "a\n", "b.md": "b, this shipment's\n",
                    "sub dir/c.md": "c\n", "triage.md": "triage, this shipment's\n"}
        for relative, text in contents.items():
            (staging / relative).parent.mkdir(parents=True, exist_ok=True)
            (staging / relative).write_text(text, encoding="utf-8")
        store.mkdir(parents=True, exist_ok=True)
        for relative, text in stored.items():
            (store / relative).write_text(text, encoding="utf-8")
        digests = {relative: hashlib.sha256(text.encode()).hexdigest()
                   for relative, text in contents.items()}
        request = {"store_dir": str(store), "staging_dir": str(staging),
                   "local_digests": digests, "replaceable": "triage.md"}
        replayed = subprocess.run(
            ["/bin/sh", "-c",
             f"python3 -c {shlex.quote(racing.place_staged_files_program())}"],
            input=json.dumps(request), capture_output=True, text=True, check=False)
        held = {p.relative_to(store).as_posix(): p.read_text(encoding="utf-8")
                for p in store.rglob("*") if p.is_file()}
        try:
            outcome = json.loads(replayed.stdout)
        except ValueError:
            outcome = None
        return replayed, outcome, held, staging, store, digests

    replayed, outcome, held, staging, _, digests = step_through_real_python3(
        "fresh", {"triage.md": "triage, the store's\n"})
    check("run by a real python3, the step places every new file by link, a "
          "path with a space in it included, replaces the store's triage.md "
          "and announces the digest it held, and removes the staging directory",
          replayed.returncode == 0 and outcome is not None
          and outcome["added"] == ["a.md", "b.md", "sub dir/c.md"]
          and outcome["displaced"]
          == hashlib.sha256(b"triage, the store's\n").hexdigest()
          and outcome["stored"] == digests
          and held == {"a.md": "a\n", "b.md": "b, this shipment's\n",
                       "sub dir/c.md": "c\n", "triage.md": "triage, this shipment's\n"}
          and not staging.exists(),
          f"{outcome} {held} {replayed.stderr}")
    replayed, outcome, held, staging, _, _ = step_through_real_python3(
        "taken", {"b.md": "b, the other's\n", "triage.md": "triage, the store's\n"})
    check("an add-only file the store holds with other bytes is named as "
          "differing, and nothing is placed or replaced, triage.md included",
          replayed.returncode == 0 and outcome is not None
          and outcome["differing"] == ["b.md"]
          and held == {"b.md": "b, the other's\n", "triage.md": "triage, the store's\n"}
          and not staging.exists(),
          f"{outcome} {held} {replayed.stderr}")

    # The walk shipper's add-only linking script, scripts/walk-files-ship.py's:
    # a name taken by other bytes is left as it was, and placing goes on past it.
    staging = scratch / "placing-go-on" / ".ship-staging-w-0"
    store = scratch / "placing-go-on" / "w"
    go_on_contents = {"a.md": "a\n", "b.md": "b, this shipment's\n", "c.md": "c\n"}
    for relative, text in go_on_contents.items():
        (staging / relative).parent.mkdir(parents=True, exist_ok=True)
        (staging / relative).write_text(text, encoding="utf-8")
    store.mkdir(parents=True, exist_ok=True)
    (store / "b.md").write_text("b, the other's\n", encoding="utf-8")
    replayed = subprocess.run(
        ["/bin/sh", "-c", racing.link_staged_files_never_over_existing_script(
            pathlib.PurePosixPath(staging), pathlib.PurePosixPath(store),
            sorted(go_on_contents))], capture_output=True, text=True, check=False)
    check("replayed by a real sh, the walk shipper's linking script leaves a name "
          "taken by other bytes as it was, places the files after it, and prints "
          "the store's digest of each",
          replayed.returncode == 0 and not staging.exists()
          and {p.name: p.read_text(encoding="utf-8") for p in store.iterdir()}
          == {"a.md": "a\n", "b.md": "b, the other's\n", "c.md": "c\n"}
          and (hashlib.sha256("b, the other's\n".encode()).hexdigest() + "  b.md"
               in replayed.stdout.splitlines()),
          f"{replayed.stdout} {replayed.stderr}")

    # The replacing script ned-box runs for the walk and seat shippers,
    # replayed by a real /bin/sh on scratch paths.
    staging = scratch / "replacing" / ".ship-staging-x-0"
    store = scratch / "replacing" / "x"
    staged_texts = {"m.md": "minutes, this shipment's\n",
                    "w x.md": "walk text, this shipment's\n",
                    "v.md": "walk text, this shipment's\n",
                    "new.md": "new\n"}
    for relative, text in staged_texts.items():
        (staging / relative).parent.mkdir(parents=True, exist_ok=True)
        (staging / relative).write_text(text, encoding="utf-8")
    store.mkdir(parents=True, exist_ok=True)
    stored_texts = {"m.md": "minutes, the other's\n", "w x.md": "walk text, tested\n",
                    "v.md": "walk text, changed since\n"}
    for relative, text in stored_texts.items():
        (store / relative).write_text(text, encoding="utf-8")
    sha = {text: hashlib.sha256(text.encode()).hexdigest()
           for text in list(staged_texts.values()) + list(stored_texts.values())}
    replacements = [("m.md", "m.md", None),
                    ("w x.md", "w x.md", sha["walk text, tested\n"]),
                    ("v.md", "v.md", sha["walk text, tested\n"]),
                    ("new.md", "renamed.md", None)]
    replayed = subprocess.run(["/bin/sh", "-c", racing.replace_with_staged_files_script(
        pathlib.PurePosixPath(staging), pathlib.PurePosixPath(store), replacements)],
        capture_output=True, text=True, check=False)
    lines = replayed.stdout.splitlines()
    check("replayed by a real sh, the replacing script renames over a file "
          "when no digest is required, and prints the digest it displaced",
          replayed.returncode == 0
          and (store / "m.md").read_text(encoding="utf-8") == "minutes, this shipment's\n"
          and f"replaced {sha['minutes, the other' + chr(39) + 's' + chr(10)]} m.md" in lines,
          f"{replayed.stdout} {replayed.stderr}")
    check("it renames over a file whose digest is the required one, a name "
          "with a space in it included",
          (store / "w x.md").read_text(encoding="utf-8") == "walk text, this shipment's\n"
          and f"replaced {sha['walk text, tested' + chr(10)]} w x.md" in lines,
          replayed.stdout)
    check("it keeps a file whose digest is not the required one, and says so",
          (store / "v.md").read_text(encoding="utf-8") == "walk text, changed since\n"
          and f"kept {sha['walk text, changed since' + chr(10)]} v.md" in lines,
          replayed.stdout)
    check("it renames a staged file to another name in the store, nothing "
          "displaced being a dash",
          (store / "renamed.md").read_text(encoding="utf-8") == "new\n"
          and "replaced - renamed.md" in lines, replayed.stdout)
    check("and it prints the store's digest of every name afterwards, which is "
          "what the module reads back",
          all(f"stored {hashlib.sha256((store / name).read_bytes()).hexdigest()} {name}"
              in lines for name in ("m.md", "w x.md", "v.md", "renamed.md")),
          replayed.stdout)

    # Shipped in this process, with what it prints captured. An OSError that
    # escapes ship_one is returned as the printed text, so the calling case
    # fails by name instead of ending this file.
    def ship_in_process(store, record):
        printed, announced = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(printed), contextlib.redirect_stderr(announced):
                code = racing.ship_one(None, pathlib.PurePosixPath(store), record)
        except OSError as escaped:
            return None, f"raised {escaped!r}", announced.getvalue()
        return code, printed.getvalue(), announced.getvalue()

    # Another shipment of the name landing a file between the placing step's
    # inventory and the link: the link is never made over it, placing stops
    # there, and the read-back refuses.
    unlocked_store = scratch / "unlocked-store" / "cold-read-records"
    unlocked_record = make_record(scratch / "unlocked-records", "unlocked-2026-10-01",
                                  {"a.md": REPORT_A, "b.md": REPORT_A, "c.md": REPORT_A})
    saved_link = os.link

    def link_after_the_other_lands_b(source, target, *args, **kwargs):
        if pathlib.Path(target).name == "b.md":
            pathlib.Path(target).write_text(REPORT_B, encoding="utf-8")
        return saved_link(source, target, *args, **kwargs)

    os.link = link_after_the_other_lands_b
    try:
        code, out, err = ship_in_process(unlocked_store, unlocked_record)
    finally:
        os.link = saved_link
    unlocked_held = {p.name: p.read_text(encoding="utf-8")
                     for p in (unlocked_store / unlocked_record.name).iterdir()}
    check("a file another shipment lands just before the link is never "
          "overwritten: placing stops there and the shipment is REFUSED",
          code == 2 and out.startswith("REFUSED:") and "b.md" in out
          and unlocked_held == {"a.md": REPORT_A, "b.md": REPORT_B},
          f"exit {code}: {out}{err} {unlocked_held}")

    # The same landing, with a triage.md the store holds with other bytes:
    # placing stopped, so the shipment is REFUSED and the store's triage.md is
    # left as it was, never replaced by a shipment that does not ship.
    stopped_store = scratch / "stopped-store" / "cold-read-records"
    stopped_record = make_record(scratch / "stopped-records", "stopped-2026-10-02",
                                 {"a.md": REPORT_A, "b.md": REPORT_A,
                                  "triage.md": "# triage, ours\n"})
    stopped_triage = stopped_store / stopped_record.name / "triage.md"
    stopped_triage.parent.mkdir(parents=True)
    stopped_triage.write_text("# triage, the store's\n", encoding="utf-8")
    os.link = link_after_the_other_lands_b
    try:
        code, out, err = ship_in_process(stopped_store, stopped_record)
    finally:
        os.link = saved_link
    check("when placing stops at a file another shipment landed, the shipment "
          "is REFUSED and the store's triage.md is not replaced, nor announced "
          "as replaced",
          code == 2 and out.startswith("REFUSED:") and "b.md" in out
          and stopped_triage.read_text(encoding="utf-8") == "# triage, the store's\n"
          and "REPLACED" not in err,
          f"exit {code}: {out}{err}")

    # --- A triage.md another shipment placed first is replaced, rule 4 -------
    triage_store = scratch / "triage-race-store" / "cold-read-records"
    triage_record = make_record(scratch / "triage-race-records", "triage-race-2026-10-01",
                                {"a.md": "# shared\n", "triage.md": "# triage, ours\n"})
    landed_triage = triage_store / triage_record.name / "triage.md"
    theirs = "# triage, the other shipment's\n"

    def inventory_then_land_triage(host, store_dir):
        answer = saved_store_inventory(host, store_dir)
        if not landed_triage.exists():
            landed_triage.parent.mkdir(parents=True, exist_ok=True)
            landed_triage.write_text(theirs, encoding="utf-8")
        return answer

    racing.store_inventory = inventory_then_land_triage
    try:
        code, out, err = ship_in_process(triage_store, triage_record)
    finally:
        racing.store_inventory = saved_store_inventory
    check("a differing triage.md another shipment placed after this one's "
          "inventory is replaced under rule 4 and shipped:, never REFUSED with "
          "the -2 rename",
          code == 0 and out.startswith("shipped:") and "triage.md replaced" in out
          and landed_triage.read_text(encoding="utf-8") == "# triage, ours\n",
          f"exit {code}: {out}{err}")
    check("the replacement announces the other shipment's digest as the "
          "displaced one, on stderr",
          "REPLACED triage.md" in err
          and hashlib.sha256(theirs.encode()).hexdigest() in err, err)

    # --- An overlapping replacement of triage.md lands after this one's -----
    # Both shipments replace triage.md; the other's rename lands second, so
    # this shipment's read-back holds the other's triage: never shipped:.
    overtaken_store = scratch / "overtaken-store" / "cold-read-records"
    overtaken_record = make_record(scratch / "overtaken-records", "overtaken-2026-10-02",
                                   {"a.md": "# shared\n", "triage.md": "# triage, ours\n"})
    overtaken_triage = overtaken_store / overtaken_record.name / "triage.md"
    overtaken_triage.parent.mkdir(parents=True)
    overtaken_triage.write_text("# triage, the store's\n", encoding="utf-8")
    saved_replace = os.replace

    def replace_then_the_other_replaces(source, target, *args, **kwargs):
        saved_replace(source, target, *args, **kwargs)
        if pathlib.Path(target).name == "triage.md":
            pathlib.Path(target).write_text(theirs, encoding="utf-8")

    os.replace = replace_then_the_other_replaces
    try:
        code, out, err = ship_in_process(overtaken_store, overtaken_record)
    finally:
        os.replace = saved_replace
    check("a triage.md another shipment replaces after this one's replacement "
          "is REFUSED naming triage.md, and never shipped:",
          code == 2 and out.startswith("REFUSED:") and "triage.md" in out
          and "shipped:" not in out,
          f"exit {code}: {out}{err}")

    # --- A new file the placing leaves out is FAILED, never shipped: ---------
    unplaced_store = scratch / "unplaced-store" / "cold-read-records"
    unplaced_record = make_record(scratch / "unplaced-records", "unplaced-2026-10-01",
                                  {"a.md": REPORT_A, "b.md": REPORT_B})
    saved_link = os.link

    def link_refusing_b(source, target, *args, **kwargs):
        if pathlib.Path(target).name == "b.md":
            raise PermissionError(13, "Permission denied", str(target))
        return saved_link(source, target, *args, **kwargs)

    os.link = link_refusing_b
    try:
        code, out, err = ship_in_process(unplaced_store, unplaced_record)
    finally:
        os.link = saved_link
    check("a new file the placing could not link is FAILED, exit 1, naming it, "
          "and never shipped:",
          code == 1 and out.startswith("FAILED:")
          and "not in the store after the copy: b.md" in out, f"exit {code}: {out}{err}")

    # --- A copy into staging that fails leaves no staging directory ----------
    failing_store = scratch / "failing-copy-store" / "cold-read-records"
    failing_record = make_record(scratch / "failing-copy-records", "failing-copy-2026-10-01",
                                 {"a.md": REPORT_A})

    def rsync_then_exit_23(command, *args, **kwargs):
        completed = saved_subprocess_run(command, *args, **kwargs)
        if command and command[0] == "rsync" and ".ship-staging-" in command[-1]:
            return subprocess.CompletedProcess(command, 23, completed.stdout, "partial transfer\n")
        return completed

    subprocess.run = rsync_then_exit_23
    try:
        code, out, err = ship_in_process(failing_store, failing_record)
    finally:
        subprocess.run = saved_subprocess_run
    check("a copy into staging that exits 23 is FAILED, and the staging directory "
          "it filled is removed",
          code == 1 and out.startswith("FAILED:") and "rsync exit 23" in out
          and sorted(p.name for p in failing_store.iterdir()) == [],
          f"exit {code}: {out}; left: {sorted(p.name for p in failing_store.iterdir())}")

    # --- A local placing step that hits an OS error names that error ---------
    denied_store = scratch / "denied-store" / "cold-read-records"
    denied_record = make_record(scratch / "denied-records", "denied-2026-10-01",
                                {"a.md": REPORT_A})
    saved_place = racing.place_staged_files_and_read_them_back

    def place_denied(request):
        raise PermissionError(13, "Permission denied", request["store_dir"])

    racing.place_staged_files_and_read_them_back = place_denied
    try:
        code, out, err = ship_in_process(denied_store, denied_record)
    finally:
        racing.place_staged_files_and_read_them_back = saved_place
    check("a local placing step that hits an OS error prints that error as the "
          "reason, not an ssh exit",
          code == 1 and out.startswith("FAILED: denied-2026-10-01 — Permission denied "
                                       "while placing the copied files; a later run finishes it.")
          and "ssh" not in out,
          f"exit {code}: {out}")

# --- The replace step renames nothing beside another shipment's staging ----
_overlap_spec = importlib.util.spec_from_file_location("cold_read_record_ship_overlap", SHIP)
overlap_shipper = importlib.util.module_from_spec(_overlap_spec)
_overlap_spec.loader.exec_module(overlap_shipper)
with tempfile.TemporaryDirectory(prefix="cold-read-record-ship-overlap-test-") as overlap_name:
    overlap_store = pathlib.Path(overlap_name) / "store"
    own = overlap_store / ".ship-staging-walk b-0123456789ab"
    other = overlap_store / ".ship-staging-walk b-aaaaaaaaaaaa"
    longer_name = overlap_store / ".ship-staging-walk b-c-bbbbbbbbbbbb"
    for directory in (own, other, longer_name):
        directory.mkdir(parents=True)
    (own / "x").write_text("this shipment\n", encoding="utf-8")
    (overlap_store / "x").write_text("the other shipment\n", encoding="utf-8")
    script = overlap_shipper.replace_with_staged_files_script(
        pathlib.PurePosixPath(own), pathlib.PurePosixPath(overlap_store), [("x", "x", None)])
    ran = subprocess.run(["sh", "-c", script], capture_output=True, text=True, check=False)
    check("the remote replace step, run by a real sh, names another staging directory "
          "of the same name and renames nothing; one for a longer name is not counted",
          ran.returncode == 0 and ran.stdout == f"other - {other}\n"
          and (overlap_store / "x").read_text(encoding="utf-8") == "the other shipment\n",
          repr(ran.stdout) + ran.stderr)
    _, local_outcome = overlap_shipper.replace_with_staged_files(
        None, own, overlap_store, [("x", "x", None)])
    check("the local replace step returns OtherShipmentStaging naming it, and renames nothing",
          isinstance(local_outcome, overlap_shipper.OtherShipmentStaging)
          and local_outcome.paths == (str(other),)
          and (overlap_store / "x").read_text(encoding="utf-8") == "the other shipment\n",
          repr(local_outcome))
    other.rmdir()
    ran = subprocess.run(["sh", "-c", script], capture_output=True, text=True, check=False)
    check("with no other staging directory, the remote replace step renames as before",
          ran.returncode == 0 and ran.stdout.startswith("replaced ")
          and (overlap_store / "x").read_text(encoding="utf-8") == "this shipment\n",
          repr(ran.stdout) + ran.stderr)

# --- A local store step that hits an OS error returns the failed result -----
# The ssh path's failure is exit nonzero and a value of None; the local path
# must fail the same way, not raise, so each caller prints its FAILED line.
_failing_spec = importlib.util.spec_from_file_location("cold_read_record_ship_local_failure", SHIP)
failing_shipper = importlib.util.module_from_spec(_failing_spec)
_failing_spec.loader.exec_module(failing_shipper)


@contextlib.contextmanager
def os_error_from(owner, attribute, raises_for):
    """Patch owner.attribute so a call whose arguments raises_for accepts
    raises OSError 28; every other call runs the real one."""
    real = getattr(owner, attribute)

    def patched(*args, **kwargs):
        if raises_for(*args, **kwargs):
            raise OSError(28, "No space left on device (injected)")
        return real(*args, **kwargs)

    setattr(owner, attribute, patched)
    try:
        yield
    finally:
        setattr(owner, attribute, real)


def returned_or_raised(call):
    """call()'s value, or the OSError it raised: a step that raises again then
    fails its case by name instead of ending this file."""
    try:
        return call()
    except OSError as escaped:
        return escaped


def failed_as_ssh_fails(outcome):
    """Whether a (process, value) outcome is the ssh path's failed result."""
    return (isinstance(outcome, tuple) and outcome[0].returncode == 1
            and outcome[1] is None
            and outcome[0].stdout == "No space left on device (injected)")


with tempfile.TemporaryDirectory(prefix="cold-read-record-ship-local-failure-test-") as failing_name:
    failing_scratch = pathlib.Path(failing_name)

    records_path = failing_scratch / "ensure-store" / "cold-read-records"
    with os_error_from(pathlib.Path, "mkdir", lambda path, *a, **k: path == records_path):
        ensured = returned_or_raised(lambda: (
            failing_shipper.ensure_store(None, pathlib.PurePosixPath(records_path)), None))
        record = make_record(failing_scratch / "ensure-records", "ensure-2026-10-25",
                             {"a.md": REPORT_A})
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed), contextlib.redirect_stderr(io.StringIO()):
            code = returned_or_raised(lambda: failing_shipper.ship_one(
                None, pathlib.PurePosixPath(records_path), record))
    check("a local ensure_store whose mkdir raises OSError returns exit 1 with the "
          "OS's reason, and ship_one prints a FAILED line",
          failed_as_ssh_fails(ensured) and code == 1
          and printed.getvalue().startswith("FAILED: ensure-2026-10-25"),
          f"{ensured!r}; exit {code}: {printed.getvalue()}")

    inventory_store = failing_scratch / "inventory-store" / "cold-read-records"
    stored_file = inventory_store / "inventory-2026-10-25" / "a.md"
    stored_file.parent.mkdir(parents=True)
    stored_file.write_text(REPORT_A, encoding="utf-8")
    record = make_record(failing_scratch / "inventory-records", "inventory-2026-10-25",
                         {"a.md": REPORT_A})
    with os_error_from(pathlib.Path, "read_bytes", lambda path: path == stored_file):
        listed = returned_or_raised(lambda: failing_shipper.store_inventory(
            None, pathlib.PurePosixPath(stored_file.parent)))
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed), contextlib.redirect_stderr(io.StringIO()):
            code = returned_or_raised(lambda: failing_shipper.ship_one(
                None, pathlib.PurePosixPath(inventory_store), record))
    check("a local store_inventory whose read raises OSError returns exit 1 and None, and "
          "ship_one's FAILED line names the OS's reason, not an ssh exit",
          failed_as_ssh_fails(listed) and code == 1
          and printed.getvalue().startswith(
              "FAILED: inventory-2026-10-25 — No space left on device (injected);")
          and "ssh exit" not in printed.getvalue(),
          f"{listed!r}; exit {code}: {printed.getvalue()}")

    link_staging = failing_scratch / "link-store" / ".ship-staging-l-0123456789ab"
    link_store = failing_scratch / "link-store"
    (link_staging / "sub").mkdir(parents=True)
    (link_staging / "sub" / "x").write_text("x\n", encoding="utf-8")
    with os_error_from(pathlib.Path, "mkdir", lambda path, *a, **k: path == link_store / "sub"):
        placed = returned_or_raised(lambda: failing_shipper.link_staged_files_never_over_existing(
            None, pathlib.PurePosixPath(link_staging), pathlib.PurePosixPath(link_store),
            ["sub/x"]))
    check("a local link_staged_files_never_over_existing whose mkdir raises OSError "
          "returns exit 1 and None, and removes the staging directory",
          failed_as_ssh_fails(placed) and not link_staging.exists(), repr(placed))

    replace_store = failing_scratch / "replace-store"
    replace_staging = replace_store / ".ship-staging-r-0123456789ab"
    replace_staging.mkdir(parents=True)
    (replace_staging / "m.md").write_text("new minutes\n", encoding="utf-8")
    (replace_store / "m.md").write_text("old minutes\n", encoding="utf-8")
    renamed_targets = set()
    real_os_replace = os.replace

    def replace_and_note(source, target, *args, **kwargs):
        real_os_replace(source, target, *args, **kwargs)
        renamed_targets.add(pathlib.Path(target))

    os.replace = replace_and_note
    try:
        with os_error_from(pathlib.Path, "read_bytes",
                           lambda path: path in renamed_targets):
            renamed = returned_or_raised(lambda: failing_shipper.replace_with_staged_files(
                None, pathlib.PurePosixPath(replace_staging),
                pathlib.PurePosixPath(replace_store), [("m.md", "m.md", None)]))
    finally:
        os.replace = real_os_replace
    check("a local replace_with_staged_files whose read-back after the renames raises "
          "OSError returns exit 1 and None, the rename done",
          failed_as_ssh_fails(renamed)
          and (replace_store / "m.md").read_text(encoding="utf-8") == "new minutes\n",
          repr(renamed))

# --- A failed store step's reason: local stdout, ned-box unreachable, ssh exit --
failure_reason = (failing_shipper
                  .failed_log_store_step_reason_text_local_stdout_or_ned_box_unreachable_or_ssh_exit)
check("a failed local store step's reason is its stdout, the OS's reason, not an ssh exit",
      failure_reason(None, subprocess.CompletedProcess([], 1, "Permission denied", ""))
      == "Permission denied")
check("a failed remote store step that ssh exited 255 on gives 'ned-box unreachable'",
      failure_reason("nedlern@ned-box", subprocess.CompletedProcess([], 255, "out", ""))
      == "ned-box unreachable")
check("a failed remote store step with any other exit gives 'ssh exit N'",
      failure_reason("nedlern@ned-box", subprocess.CompletedProcess([], 1, "out", ""))
      == "ssh exit 1")

# --- A relative record directory means the one under the current directory --
# Run from a directory outside the shipper's checkout with a relative path:
# the record under that directory is the one shipped.
with tempfile.TemporaryDirectory(prefix="cold-read-record-ship-relative-test-") as relative_name:
    relative_scratch = pathlib.Path(relative_name)
    relative_store = relative_scratch / "store" / "cold-read-records"
    relative_record = make_record(relative_scratch / "records", "2026-10-21-relative-path",
                                  {"a.md": REPORT_A})
    result = ship(str(relative_store), "records/2026-10-21-relative-path",
                  current_directory=relative_scratch)
    check("a relative record directory is shipped from under the current directory, "
          "not the shipper's checkout",
          result.returncode == 0 and result.stdout.startswith("shipped:")
          and (relative_store / relative_record.name / "a.md").read_text(encoding="utf-8")
          == REPORT_A,
          result.stdout + result.stderr)

# --- A record name free in the store, and a store record of another read ----
# A fast read named its record from its own checkout's cold-read-records/
# alone, while another worktree's cold-read-full-run already held that name in
# the store; the fast read's files all had names the full run's lacked, so
# shipping added them to the full run's record. Another fast read took a name
# another seat's read held in the store, and shipping refused it only because
# both had a fast-read.md.
with tempfile.TemporaryDirectory(prefix="cold-read-record-ship-store-names-test-") as names_name:
    # Resolved: the shipper resolves the record path, and the suite runner's TMPDIR is a symlink.
    names_scratch = pathlib.Path(names_name).resolve()
    _names_shipper_spec = importlib.util.spec_from_file_location(
        "cold_read_record_ship_store_names", SHIP)
    names_shipper = importlib.util.module_from_spec(_names_shipper_spec)
    _names_shipper_spec.loader.exec_module(names_shipper)
    names_store = names_scratch / "store" / "cold-read-records"
    (names_store / "a-2026-10-25").mkdir(parents=True)
    (names_store / "b-2026-10-25").mkdir()
    (names_store / "not-a-record.md").write_text("x\n", encoding="utf-8")

    names, unlisted = names_shipper.log_store_listed_record_directory_names_or_listing_failure_reason(None, names_store)
    check("locally, the store's names are its directories, not its files",
          names == {"a-2026-10-25", "b-2026-10-25"} and unlisted is None, f"{names} {unlisted}")
    names, unlisted = names_shipper.log_store_listed_record_directory_names_or_listing_failure_reason(
        None, names_scratch / "no-store-yet")
    check("a store not yet made holds no names", names == set() and unlisted is None,
          f"{names} {unlisted}")
    if os.geteuid() != 0:
        unreadable_store = names_scratch / "unreadable-store"
        unreadable_store.mkdir()
        unreadable_store.chmod(0)
        try:
            names, unlisted = names_shipper.log_store_listed_record_directory_names_or_listing_failure_reason(None, unreadable_store)
        finally:
            unreadable_store.chmod(0o755)
        check("a local store that cannot be listed gives no names and says why",
              names is None and unlisted is not None and str(unreadable_store) in unlisted,
              f"{names} {unlisted}")

    # The remote listing's shell, run by a real sh in place of ssh: sh -c gets
    # the host as $1 and the script as $2.
    real_ssh_command = names_shipper.SSH_COMMAND
    unreachable_ssh_command = ["sh", "-c", "echo 'ssh: connect: No route to host' >&2; exit 255",
                               "ssh-replay"]
    names_shipper.SSH_COMMAND = ["sh", "-c", 'eval "$2"', "ssh-replay"]
    try:
        remote_names, remote_unlisted = names_shipper.log_store_listed_record_directory_names_or_listing_failure_reason(
            "nobody@ned-box", names_store)
        absent_names, absent_unlisted = names_shipper.log_store_listed_record_directory_names_or_listing_failure_reason(
            "nobody@ned-box", names_scratch / "no store yet")
        names_shipper.SSH_COMMAND = unreachable_ssh_command
        failed_names, failed_unlisted = names_shipper.log_store_listed_record_directory_names_or_listing_failure_reason(
            "nobody@ned-box", names_store)
        names_shipper.SSH_COMMAND = ["sh", "-c", "kill -TERM $$", "ssh-replay"]
        killed_names, killed_unlisted = names_shipper.log_store_listed_record_directory_names_or_listing_failure_reason(
            "nobody@ned-box", names_store)
    finally:
        names_shipper.SSH_COMMAND = real_ssh_command
    check("remotely, the store's names are its directories, one per line",
          remote_names == {"a-2026-10-25", "b-2026-10-25"} and remote_unlisted is None,
          f"{remote_names} {remote_unlisted}")
    check("remotely, a store not yet made holds no names", absent_names == set()
          and absent_unlisted is None, f"{absent_names} {absent_unlisted}")
    check("remotely, a listing ssh could not make gives no names, with ssh's exit and error",
          failed_names is None and "exited 255" in failed_unlisted
          and "No route to host" in failed_unlisted, f"{failed_names} {failed_unlisted}")
    check("remotely, a listing whose ssh a signal ended gives no names, not an empty store",
          killed_names is None and "exited -15" in killed_unlisted,
          f"{killed_names} {killed_unlisted}")

    names_records = names_scratch / "records"
    (names_records / "SKILL-handoff-2026-10-25").mkdir(parents=True)
    (names_store / "SKILL-handoff-2026-10-25").mkdir()
    (names_store / "SKILL-handoff-2026-10-25-2").mkdir()
    (names_store / "item-19-1-2026-10-25").mkdir()
    real_destination = os.environ.get(DESTINATION_VARIABLE)
    os.environ[DESTINATION_VARIABLE] = str(names_store)
    try:
        handoff_record, handoff_unlisted = (
            names_shipper.cold_read_first_unused_record_directory_name_in_checkout_and_log_store_with_log_store_listing_error(
                names_records / "SKILL-handoff-2026-10-25"))
        item_record, item_unlisted = (
            names_shipper.cold_read_first_unused_record_directory_name_in_checkout_and_log_store_with_log_store_listing_error(
                names_records / "item-19-1-2026-10-25"))
        free_record, _ = names_shipper.cold_read_first_unused_record_directory_name_in_checkout_and_log_store_with_log_store_listing_error(
            names_records / "c-2026-10-25")
        os.environ[DESTINATION_VARIABLE] = "nobody@ned-box:" + str(names_store)
        names_shipper.SSH_COMMAND = unreachable_ssh_command
        try:
            unlisted_record, unlisted_reason = (
                names_shipper.cold_read_first_unused_record_directory_name_in_checkout_and_log_store_with_log_store_listing_error(
                    names_records / "SKILL-handoff-2026-10-25"))
        finally:
            names_shipper.SSH_COMMAND = real_ssh_command
    finally:
        if real_destination is None:
            os.environ.pop(DESTINATION_VARIABLE, None)
        else:
            os.environ[DESTINATION_VARIABLE] = real_destination
    check("the SKILL-handoff case: a name the checkout holds and the -2 the store "
          "holds are both passed over, giving -3",
          handoff_record == names_records / "SKILL-handoff-2026-10-25-3"
          and handoff_unlisted is None, f"{handoff_record} {handoff_unlisted}")
    check("the item-19-1 case: a name only the store holds is passed over, giving -2",
          item_record == names_records / "item-19-1-2026-10-25-2" and item_unlisted is None,
          f"{item_record} {item_unlisted}")
    check("a name free in both is used as it is, and no directory is made",
          free_record == names_records / "c-2026-10-25" and not free_record.exists(),
          str(free_record))
    check("when the store cannot be listed, the name free in the checkout is given "
          "with the reason, for the caller to print",
          unlisted_record == names_records / "SKILL-handoff-2026-10-25-2"
          and "No route to host" in unlisted_reason, f"{unlisted_record} {unlisted_reason}")
    line = names_shipper.log_store_listing_failed_record_name_may_collide_warning_line(
        "some-program", unlisted_record, unlisted_reason)
    check("the line a caller prints names the program, the record name and the reason",
          line.startswith("some-program: ") and "SKILL-handoff-2026-10-25-2" in line
          and unlisted_reason in line, line)

    # The SKILL-handoff shipment itself: the store's record holds a full run's
    # files, and the local directory of that name holds a fast read's.
    full_run_files = {"claude-hunt-deep.md": REPORT_A, "codex-hunt-deep.md": REPORT_B,
                      "reference-check.md": "# references\n",
                      "target/.claude/skills/handoff/SKILL.md": "# handoff\n"}
    make_record(names_store, "SKILL-handoff-2026-10-25-2", full_run_files)
    store_files_before = sorted(
        p.relative_to(names_store).as_posix() for p in names_store.rglob("*") if p.is_file())
    fast_read_record = make_record(names_records, "SKILL-handoff-2026-10-25-2", {
        "fast-read.md": REPORT_A, "fast-read.md.agent-session.json": "{}\n",
        "SKILL-with-sentence-ids.md": "# handoff [S1]\n",
        "target/home/nedlern/elsewhere/.claude/skills/handoff/SKILL.md": "# handoff, edited\n"})
    result = ship(str(names_store), str(fast_read_record))
    store_files_after = sorted(
        p.relative_to(names_store).as_posix() for p in names_store.rglob("*") if p.is_file())
    check("a store record holding files the local directory lacks is REFUSED with exit 2, "
          "though no file name is in both",
          result.returncode == 2 and result.stdout.startswith("REFUSED:")
          and result.stdout.count("\n") == 1, result.stdout + result.stderr)
    rename = (f"`mv {fast_read_record} {names_records / 'SKILL-handoff-2026-10-25-3'}`, a name "
              f"free in this checkout and in the store when this ran")
    check("the refusal names the store's files the local directory lacks, and gives the "
          "rename to the first -N after the date free here and in the store",
          all(relative in result.stdout for relative in full_run_files)
          and "fast-read.md" not in result.stdout
          and str(names_store / "SKILL-handoff-2026-10-25-2") in result.stdout
          and rename in result.stdout
          and f"then ship the renamed directory with `{SHIP} "
              f"{names_records / 'SKILL-handoff-2026-10-25-3'}`." in result.stdout,
          result.stdout)
    check("nothing was copied into the other read's record",
          store_files_after == store_files_before,
          str(sorted(set(store_files_after) - set(store_files_before))))

    # The same refusal when the store's names cannot be read after its
    # inventory: the rename is free in this checkout only, and says so.
    real_listing = names_shipper.log_store_listed_record_directory_names_or_listing_failure_reason
    names_shipper.log_store_listed_record_directory_names_or_listing_failure_reason = (
        lambda host, records_path: (None, "listing failed: injected"))
    unlisted_stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(unlisted_stdout):
            unlisted_code = names_shipper.ship_one(None, names_store, fast_read_record)
    finally:
        names_shipper.log_store_listed_record_directory_names_or_listing_failure_reason = real_listing
    check("when the store's names cannot be read, the refusal's rename is to the first -N "
          "free in this checkout, and it says the store may hold that name",
          unlisted_code == 2
          and f"`mv {fast_read_record} {names_records / 'SKILL-handoff-2026-10-25-3'}`, a name "
              f"free in this checkout; the store's names could not be read (listing failed: "
              f"injected), so the store may hold it" in unlisted_stdout.getvalue(),
          unlisted_stdout.getvalue())

    # A directory named by its date alone is offered -2; one not ending in a
    # date keeps its whole name and gains the -N.
    (names_store / "plain-2026-10-26").mkdir()
    (names_store / "plain-2026-10-26" / "other.md").write_text("other read\n", encoding="utf-8")
    plain_record = make_record(names_records, "plain-2026-10-26", {"mine.md": "mine\n"})
    plain = ship(str(names_store), str(plain_record))
    (names_store / "2026-10-26-dated-first").mkdir()
    (names_store / "2026-10-26-dated-first" / "other.md").write_text("x\n", encoding="utf-8")
    dated_first_record = make_record(names_records, "2026-10-26-dated-first", {"mine.md": "m\n"})
    dated_first = ship(str(names_store), str(dated_first_record))
    check("the rename of a date-named directory is its name with -2",
          f"{names_records / 'plain-2026-10-26-2'}`" in plain.stdout, plain.stdout)
    check("the rename of a directory not ending in a date is its whole name with -2",
          f"{names_records / '2026-10-26-dated-first-2'}`" in dated_first.stdout,
          dated_first.stdout)
    # A date-first name may end in digits of its own, so its -2 is kept and
    # the rename gains another -N.
    (names_store / "2026-10-26-dated-first-2").mkdir()
    (names_store / "2026-10-26-dated-first-2" / "other.md").write_text("x\n", encoding="utf-8")
    dated_first_2_record = make_record(names_records, "2026-10-26-dated-first-2",
                                       {"mine.md": "m\n"})
    dated_first_2 = ship(str(names_store), str(dated_first_2_record))
    check("the rename of a date-first directory ending in -2 is its whole name with -2",
          f"`mv {dated_first_2_record} {names_records / '2026-10-26-dated-first-2-2'}`"
          in dated_first_2.stdout, dated_first_2.stdout)

    # The ship command the refusal gives runs from a path with a space in it.
    spaced_program = "/home/someone/checkout with space/cold-read-record-ship.py"
    real_program = sys.argv[0]
    sys.argv[0] = spaced_program
    spaced_stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(spaced_stdout):
            spaced_code = names_shipper.ship_one(None, names_store, plain_record)
    finally:
        sys.argv[0] = real_program
    check("the refusal's ship command quotes a program path holding a space",
          spaced_code == 2
          and f"`'{spaced_program}' {names_records / 'plain-2026-10-26-2'}`."
              in spaced_stdout.getvalue(),
          spaced_stdout.getvalue())

    # A file in both copies with other bytes: the rename passes over the -2
    # the store already holds, as the refusal of another read's files does.
    make_record(names_store, "differing-2026-10-26", {"a.md": REPORT_A})
    (names_store / "differing-2026-10-26-2").mkdir()
    differing_record = make_record(names_records, "differing-2026-10-26", {"a.md": REPORT_B})
    differing = ship(str(names_store), str(differing_record))
    check("a differing file's refusal gives the rename to the first -N free in the checkout "
          "and in the store, passing over a -2 only the store holds, and the ship command",
          differing.returncode == 2
          and "already in the store with different content" in differing.stdout
          and f"`mv {differing_record} {names_records / 'differing-2026-10-26-3'}`, a name "
              f"free in this checkout and in the store when this ran, then ship the renamed "
              f"directory with `{SHIP} {names_records / 'differing-2026-10-26-3'}`."
              in differing.stdout,
          differing.stdout)

print()
if failures:
    print(f"{len(failures)} case(s) FAILED:")
    for name in failures:
        print(f"  - {name}")
    sys.exit(1)
print("all cases passed")
