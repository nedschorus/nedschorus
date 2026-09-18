#!/usr/bin/env python3
"""Tests for scripts/walk-files-ship.py: the per-file rules (add-only by name,
the minutes replaced, fail loudly), the five paths built without a glob, the
exits, the one-line stdout, and the shape of the remote invocation.

Two modes, as scripts/cold-read-record-ship-test.py has them. LOCAL: the
destination override names a scratch directory and the real rsync on this
machine does the copy, so add-only, replace and the README are exercised for
real. REMOTE: the override is the ruled scp-form destination and stub `ssh` and
`rsync` binaries on PATH record what they were asked. Nothing here touches
ned-box. The walk lives in a scratch directory, docs/walk/ being gitignored,
which is what the path form of the argument is for.

Run: python3 scripts/walk-files-ship-test.py   (exit 0 = all passed)
"""

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
SHIP = SCRIPTS_DIR / "walk-files-ship.py"
DESTINATION_VARIABLE = "COLD_READ_RECORD_SHIP_DESTINATION"
RULED_RECORDS_DESTINATION = "nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records"
RULED_WALK_PATH = "/home/nedlern/nedschorus-logs/walk"

STUB_RECORDER = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["WALK_SHIP_TEST_ARGV_LOG"], "a") as log:
    log.write(json.dumps(sys.argv) + "\\n")
"""

failures = []


def check(case_name, condition, detail=""):
    print(f"{'ok' if condition else 'FAIL'}: {case_name}")
    if not condition:
        failures.append(case_name)
        if detail:
            print(f"      {detail}")


def write_walk(directory: pathlib.Path, name: str, files: dict) -> pathlib.Path:
    directory.mkdir(parents=True, exist_ok=True)
    for suffix, text in files.items():
        (directory / f"{name}{suffix}.md").write_text(text, encoding="utf-8")
    return directory / f"{name}.md"


def ship(destination, *args, extra_env=None):
    env = dict(os.environ)
    env[DESTINATION_VARIABLE] = destination
    env.update(extra_env or {})
    return subprocess.run([sys.executable, str(SHIP), *args],
                          capture_output=True, text=True, check=False, env=env)


def one_line(text: str) -> bool:
    return text.count("\n") == 1 and not text.rstrip("\n").count("\n")


WALK = "demo-walk-2026-09-18"
FILES = {"-draft": "# draft\n", "-suggestions": "# suggestions\n",
         "": "# walk\n\n## Item 1 of 2\n", "-minutes": "# minutes\n\nItem 1 ruled.\n"}

with tempfile.TemporaryDirectory(prefix="walk-files-ship-test-") as scratch_name:
    scratch = pathlib.Path(scratch_name)
    store_root = scratch / "store"
    local_destination = str(store_root / "cold-read-records")
    store_walk = store_root / "walk"
    walks = scratch / "walks"
    walk_text = write_walk(walks, WALK, FILES)
    # A sibling whose name has this walk's name as a prefix, in the same
    # directory: the naming page's reason for building paths, never globbing.
    sibling = f"{WALK}-extra"
    write_walk(walks, sibling, FILES)

    # --- First ship: four files, flat, README, one line with the citation ----
    result = ship(local_destination, str(walk_text))
    check("first ship exits 0 with one line opening shipped:",
          result.returncode == 0 and result.stdout.startswith("shipped:")
          and one_line(result.stdout), result.stdout + result.stderr)
    check("the four files are flat in the store's walk/ under their own names",
          sorted(p.name for p in store_walk.iterdir())
          == sorted(f"{WALK}{s}.md" for s in FILES))
    check("the sibling walk that shares the prefix was not shipped",
          not any(sibling in p.name for p in store_walk.iterdir()))
    check("the line ends with the minutes' citation",
          result.stdout.rstrip().endswith(f"minutes at {store_walk}/{WALK}-minutes.md"),
          result.stdout)
    check("the line counts the files added", "4 file(s) added" in result.stdout, result.stdout)
    check("the store's root gained the README saying what the store is",
          (store_root / "README.md").is_file()
          and "walk/" in (store_root / "README.md").read_text(encoding="utf-8"))
    check("the sibling's files were named on stderr as not shipped",
          f"{sibling}.md" in result.stderr and "not shipped" in result.stderr, result.stderr)

    # --- Nothing new: nothing touched ---------------------------------------
    stored_minutes = store_walk / f"{WALK}-minutes.md"
    stored_walk_text = store_walk / f"{WALK}.md"
    before = {p.name: p.stat().st_mtime_ns for p in store_walk.iterdir()}
    result = ship(local_destination, str(walk_text))
    check("a second run with nothing changed exits 0 and says everything is already there",
          result.returncode == 0 and "4 already there unchanged" in result.stdout
          and "added" not in result.stdout and "replaced" not in result.stdout,
          result.stdout)
    check("the second run touched nothing in the store",
          before == {p.name: p.stat().st_mtime_ns for p in store_walk.iterdir()})

    # --- The minutes are replaced; the replacement is announced --------------
    old_minutes_digest = subprocess.run(
        ["shasum", "-a", "256", str(stored_minutes)], capture_output=True, text=True).stdout.split()[0]
    (walks / f"{WALK}-minutes.md").write_text("# minutes\n\nItem 1 ruled.\nItem 2 ruled.\n",
                                             encoding="utf-8")
    result = ship(local_destination, str(walk_text))
    check("edited minutes are replaced, exit 0, one line saying so",
          result.returncode == 0 and "minutes replaced" in result.stdout
          and one_line(result.stdout), result.stdout)
    check("the store now holds the new minutes",
          stored_minutes.read_text(encoding="utf-8").endswith("Item 2 ruled.\n"))
    check("the replacement is announced on stderr with the displaced sha256",
          "REPLACED" in result.stderr and old_minutes_digest in result.stderr, result.stderr)
    check("the replacement announcement is not on stdout",
          "REPLACED" not in result.stdout)

    # Same length, same second: the case openrsync skips without --ignore-times.
    stored_minutes.write_text("# minutes\n\nItem 1 ruled.\nItem 2 ruled.\n", encoding="utf-8")
    (walks / f"{WALK}-minutes.md").write_text("# minutes\n\nItem 1 ruled.\nItem 2 RULED.\n",
                                             encoding="utf-8")
    os.utime(walks / f"{WALK}-minutes.md", ns=(stored_minutes.stat().st_atime_ns,
                                               stored_minutes.stat().st_mtime_ns))
    result = ship(local_destination, str(walk_text))
    check("a same-size same-mtime revision of the minutes is still copied",
          result.returncode == 0 and "minutes replaced" in result.stdout
          and stored_minutes.read_text(encoding="utf-8").endswith("Item 2 RULED.\n"),
          result.stdout + result.stderr)

    # --- Dispositions written later joins the rest ---------------------------
    (walks / f"{WALK}-dispositions.md").write_text("# dispositions\n", encoding="utf-8")
    result = ship(local_destination, str(walk_text))
    check("a dispositions file written at the close is added on the next run",
          result.returncode == 0 and "1 file(s) added" in result.stdout
          and f"{WALK}-dispositions.md" in result.stdout
          and (store_walk / f"{WALK}-dispositions.md").is_file(), result.stdout)

    # --- An add-only file that differs is refused by name; the rest ships -----
    (walks / f"{WALK}.md").write_text("# walk\n\n## Item 1 of 3\n", encoding="utf-8")
    (walks / f"{WALK}-minutes.md").write_text("# minutes\n\nre-planned to 3 items\n",
                                             encoding="utf-8")
    result = ship(local_destination, str(walk_text))
    check("a changed walk text is REFUSED with exit 2 and one line",
          result.returncode == 2 and result.stdout.startswith("REFUSED:")
          and one_line(result.stdout), result.stdout)
    check("the refusal names the file with both digests and says add-only",
          f"{WALK}.md (store sha256" in result.stdout and "local sha256" in result.stdout
          and "add-only" in result.stdout, result.stdout)
    check("the store's walk text was not replaced",
          stored_walk_text.read_text(encoding="utf-8") == FILES[""])
    check("the minutes were still replaced on the refused run (per-file rules)",
          "minutes replaced" in result.stdout
          and stored_minutes.read_text(encoding="utf-8").endswith("re-planned to 3 items\n"),
          result.stdout)
    check("the refused line still ends with the minutes' citation",
          result.stdout.rstrip().endswith(f"{WALK}-minutes.md"), result.stdout)
    (walks / f"{WALK}.md").write_text(FILES[""], encoding="utf-8")

    # --- Argument forms -------------------------------------------------------
    result = ship(local_destination, str(walks / f"{WALK}-suggestions.md"))
    check("a path to any of the walk's files names the walk (role suffix stripped)",
          result.returncode == 0 and result.stdout.startswith(f"shipped: {WALK} "),
          result.stdout)
    result = ship(local_destination, "no-such-walk-anywhere")
    check("a bare name resolves under docs/walk/ and a walk not there is exit 64 FAILED",
          result.returncode == 64 and result.stdout.startswith("FAILED:")
          and "docs/walk" in result.stdout, result.stdout)
    # A walk whose own name ends in a role suffix: the name is found by which
    # candidate has its walk text and minutes present, not by stripping alone
    # (the reviewer's case, cold-read-and-walk-file-names-and-dispositions).
    suffixed = "walk-about-dispositions"
    suffixed_walk_text = write_walk(walks, suffixed, FILES)
    result = ship(local_destination, str(suffixed_walk_text))
    check("a walk whose name ends in a role suffix is found by its walk-text path",
          result.returncode == 0 and result.stdout.startswith(f"shipped: {suffixed} "),
          result.stdout + result.stderr)
    result = ship(local_destination, str(walks / f"{suffixed}-minutes.md"))
    check("the same walk shipped by its minutes path resolves to the same name",
          result.returncode == 0 and result.stdout.startswith(f"shipped: {suffixed} "),
          result.stdout + result.stderr)

    # --- Missing files ------------------------------------------------------
    partial = "partial-walk"
    write_walk(walks, partial, {"": "# walk\n"})
    result = ship(local_destination, str(walks / f"{partial}.md"))
    check("a walk without minutes is not shippable: exit 64, FAILED names the file",
          result.returncode == 64 and result.stdout.startswith("FAILED:")
          and f"{partial}-minutes.md" in result.stdout, result.stdout)
    write_walk(walks, partial, {"": "# walk\n", "-minutes": "# minutes\n"})
    result = ship(local_destination, str(walks / f"{partial}.md"))
    check("a walk without draft or suggestions ships, and stderr notes each missing file",
          result.returncode == 0 and "2 file(s) added" in result.stdout
          and f"{partial}-draft.md" in result.stderr
          and f"{partial}-suggestions.md" in result.stderr, result.stdout + result.stderr)

    # --- The store cannot be written: FAILED, exit 1 --------------------------
    result = ship(str(scratch / "no-store" / "cold-read-records"), str(walk_text),
                  extra_env={"PATH": str(scratch / "empty-bin")})
    check("a copy that cannot run is FAILED with exit 1, not a clean result",
          result.returncode == 1 and result.stdout.startswith("FAILED:")
          and one_line(result.stdout), result.stdout + result.stderr)

    # --- The remote invocation, read from stubs -------------------------------
    stubs = scratch / "stub-bin"
    stubs.mkdir()
    for binary in ("ssh", "rsync"):
        stub = stubs / binary
        stub.write_text(STUB_RECORDER, encoding="utf-8")
        stub.chmod(0o755)
    argv_log = scratch / "argv.jsonl"
    result = ship(RULED_RECORDS_DESTINATION, str(walk_text), extra_env={
        "PATH": f"{stubs}{os.pathsep}{os.environ.get('PATH', '')}",
        "WALK_SHIP_TEST_ARGV_LOG": str(argv_log)})
    calls = [json.loads(line) for line in argv_log.read_text().splitlines()]
    ssh_calls = [c for c in calls if c[0].endswith("ssh")]
    rsync_calls = [c for c in calls if c[0].endswith("rsync")]
    check("remote mode exits 0 and reports the files as added",
          result.returncode == 0 and result.stdout.startswith("shipped:")
          and "5 file(s) added" in result.stdout, result.stdout + result.stderr)
    check("the line cites the minutes with the host, in scp form",
          result.stdout.rstrip().endswith(
              f"minutes at nedlern@ned-box:{RULED_WALK_PATH}/{WALK}-minutes.md"),
          result.stdout)
    check("every ssh call runs in batch mode with a connect timeout",
          ssh_calls and all("BatchMode=yes" in c and any(a.startswith("ConnectTimeout=") for a in c)
                            for c in ssh_calls), str(ssh_calls))
    check("the store is prepared over ssh: mkdir -p of walk/ and the README when absent",
          any("mkdir -p" in " ".join(c) and "README.md" in " ".join(c)
              and RULED_WALK_PATH in " ".join(c) for c in ssh_calls), str(ssh_calls))
    check("the store's digests come from one ssh call naming each of the five paths",
          sum(1 for c in ssh_calls if "sha256sum" in " ".join(c)) == 1
          and all(f"{RULED_WALK_PATH}/{WALK}{s}.md" in " ".join(c)
                  for c in ssh_calls if "sha256sum" in " ".join(c)
                  for s in list(FILES) + ["-dispositions"]), str(ssh_calls))
    check("exactly one rsync call, the five files flat into walk/, over batch-mode ssh",
          len(rsync_calls) == 1 and "-a" in rsync_calls[0] and "--ignore-times" in rsync_calls[0]
          and "ssh -o BatchMode=yes -o ConnectTimeout=10" in rsync_calls[0]
          and rsync_calls[0][-1] == f"nedlern@ned-box:{RULED_WALK_PATH}/"
          and sorted(pathlib.Path(a).name for a in rsync_calls[0][-6:-1])
          == sorted(f"{WALK}{s}.md" for s in list(FILES) + ["-dispositions"]),
          str(rsync_calls))
    check("rsync is never asked to delete or to write in place",
          not any(flag in rsync_calls[0] for flag in ("--delete", "--inplace")),
          str(rsync_calls))

    # --- On ned-box the copy is local and the citation still names the host --
    spec = importlib.util.spec_from_file_location("walk_files_ship", SHIP)
    module = importlib.util.module_from_spec(spec)
    saved = os.environ.pop(DESTINATION_VARIABLE, None)
    try:
        spec.loader.exec_module(module)
        module.shipper.socket.gethostname = lambda: "ned-box"
        destination = module.walk_destination_for_this_machine()
    finally:
        if saved is not None:
            os.environ[DESTINATION_VARIABLE] = saved
    check("on ned-box the copy host is None and the citation host is still ned-box",
          destination.copy_host is None and destination.citation_host == "nedlern@ned-box"
          and str(destination.walk_path) == RULED_WALK_PATH, str(destination))

    # --- The README the record shipper writes describes this kind and program --
    check("the store README names walk/, this program, its five files and the split rule",
          all(s in module.shipper.STORE_README for s in
              ("`walk/`", "walk-files-ship.py", "dispositions", "minutes")))

print()
if failures:
    print(f"{len(failures)} case(s) FAILED:")
    for case_name in failures:
        print(f"  - {case_name}")
    sys.exit(1)
print("all passed")
