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
import socket
import pathlib
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

# The stub for both `ssh` and `rsync`: append argv to the log named in the
# environment and exit 0 printing nothing, which for the inventory call
# means "no such directory in the store yet".
STUB_RECORDER = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["RECORD_SHIP_TEST_ARGV_LOG"], "a") as log:
    log.write(json.dumps(sys.argv) + "\\n")
"""

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
    check("the README points at the wiki page for the naming rules "
          "rather than restating them",
          "nedschorus-file-naming-and-location-standards.md"
          in (store_root / "README.md").read_text(encoding="utf-8"))
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
    check("the refusal tells the person what to do: rename the local directory -2",
          "-2 suffix" in result.stdout, result.stdout)
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
    # late.md, which the refusal cases left on disk unshipped to prove that a
    # refused run copies nothing, is removed first so these cases count adds
    # and replacements and nothing else.
    (demo / "late.md").unlink()
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
    single_file_calls = [c for c in replace_rsync_calls
                         if c[-1].endswith(f"{remote_record.name}/triage.md")]
    check("remotely a triage.md the store already holds with other bytes is "
          "shipped, not refused",
          result.returncode == 0 and result.stdout.startswith("shipped:")
          and "triage.md replaced" in result.stdout,
          f"exit {result.returncode}: {result.stdout}{result.stderr}")
    check("the replacement is a second rsync of that one file, over batch-mode "
          "ssh, into the record's own directory in the store",
          len(replace_rsync_calls) == 2 and len(single_file_calls) == 1
          and single_file_calls[0][-2] == f"{remote_record.resolve()}/triage.md"
          and single_file_calls[0][-1]
          == f"{RULED_DESTINATION}/{remote_record.name}/triage.md"
          and "ssh -o BatchMode=yes -o ConnectTimeout=10" in single_file_calls[0],
          str(replace_rsync_calls))
    check("the replacing rsync passes --ignore-times, rsync's size-and-time "
          "check being what would skip a same-length revision, and is never "
          "asked to delete or to write in place",
          single_file_calls and "--ignore-times" in single_file_calls[0]
          and not any(flag in single_file_calls[0]
                      for flag in ("--delete", "--inplace", "--ignore-existing")),
          str(single_file_calls))
    check("the digest the store reported for the displaced triage is announced "
          "on stderr",
          "REPLACED" in result.stderr and stored_triage_digest in result.stderr,
          result.stderr)

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

print()
if failures:
    print(f"{len(failures)} case(s) FAILED:")
    for name in failures:
        print(f"  - {name}")
    sys.exit(1)
print("all cases passed")
