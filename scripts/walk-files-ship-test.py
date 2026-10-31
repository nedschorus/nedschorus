#!/usr/bin/env python3
"""Tests for scripts/walk-files-ship.py: the per-file rules (add-only by name,
the minutes and the dispositions replaced, a walk text the walk only added to
replaced, fail loudly), the five paths built
without a glob, the
exits, the one-line stdout, and the shape of the remote invocation.

Two modes, as nc-systems/cold-read/tests/cold-read-record-ship-test.py has them. LOCAL: the
destination override names a scratch directory and the real rsync on this
machine does the copy, so add-only, replace and the README are exercised for
real. REMOTE: the override is the ruled scp-form destination and stub `ssh` and
`rsync` binaries on PATH record what they were asked; one remote case's
stand-in ssh instead runs the remote script under sh against a scratch store
named by a stand-in host. Nothing here touches ned-box or the log-store.
The walk lives in a scratch directory, docs/walk/ being gitignored, which is
what the path form of the argument is for.

Run: python3 scripts/walk-files-ship-test.py   (exit 0 = all passed)
"""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import traceback

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
SHIP = SCRIPTS_DIR / "walk-files-ship.py"
DESTINATION_VARIABLE = "COLD_READ_RECORD_SHIP_DESTINATION"
RULED_RECORDS_DESTINATION = "nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records"
RULED_WALK_PATH = "/home/nedlern/nedschorus-logs/walk"

# What a stub `ssh` answers to the two calls that put the copied files in
# place, as a store no other shipment is writing to answers: every placed file
# and every replaced file holds the staged file's bytes, read from the walk's
# own directory (WALK_SHIP_TEST_WALK_DIRECTORY), a replaced one displacing the
# stored file WALK_SHIP_TEST_STORED_DIGEST_LINE names, if it is that one.
STUB_ANSWER_TO_PUTTING_IN_PLACE = """
script = sys.argv[-1]
def set_line_words():
    import shlex
    return shlex.split(next(line for line in script.splitlines()
                            if line.startswith("set -- "))[len("set -- "):])
if "# cold-read-record-ship: link staged files" in script:
    import hashlib, shlex
    loop = next(line for line in script.splitlines()
                if line.startswith("for relative in "))
    for relative in shlex.split(loop[len("for relative in "):-len("; do")]):
        with open(os.path.join(os.environ["WALK_SHIP_TEST_WALK_DIRECTORY"], relative), "rb") as f:
            print(hashlib.sha256(f.read()).hexdigest() + "  " + relative)
    sys.exit(0)
if "# cold-read-record-ship: replace with staged files" in script:
    import hashlib
    words = set_line_words()
    digest, _, path = os.environ.get("WALK_SHIP_TEST_STORED_DIGEST_LINE", "").partition("  ")
    stored = {os.path.basename(path): digest} if path else {}
    for staged, target in zip(words[0::4], words[1::4]):
        with open(os.path.join(os.environ["WALK_SHIP_TEST_WALK_DIRECTORY"], staged), "rb") as f:
            local = hashlib.sha256(f.read()).hexdigest()
        print("replaced " + stored.get(target, "-") + " " + target)
        print("stored " + local + " " + target)
    sys.exit(0)
"""

STUB_RECORDER = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["WALK_SHIP_TEST_ARGV_LOG"], "a") as log:
    log.write(json.dumps(sys.argv) + "\\n")
""" + STUB_ANSWER_TO_PUTTING_IN_PLACE

# An ssh stub for a store that already holds one file: when asked for digests
# it answers, as sha256sum does, that the file is there with the digest the
# test put in WALK_SHIP_TEST_STORED_DIGEST_LINE, and, when the test also set
# WALK_SHIP_TEST_STORED_SIZE_LINE, with the size line the program asks for
# beside it -- the line the append exception reads, and the only place it is
# parsed, local mode taking the size from the file itself. A test that leaves
# the size line unset is a store listing that reported no size. Records argv
# too.
STUB_SSH_WITH_ONE_STORED_FILE = STUB_RECORDER + """
if any("sha256sum" in a for a in sys.argv):
    print(os.environ["WALK_SHIP_TEST_STORED_DIGEST_LINE"])
    size_line = os.environ.get("WALK_SHIP_TEST_STORED_SIZE_LINE")
    if size_line:
        print(size_line)
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
    if args and args[0].endswith(".md"):
        env["WALK_SHIP_TEST_WALK_DIRECTORY"] = str(pathlib.Path(args[0]).parent)
    env.update(extra_env or {})
    return subprocess.run([sys.executable, str(SHIP), *args],
                          capture_output=True, text=True, check=False, env=env)


def digest_of_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_or_none(path: pathlib.Path):
    """The file's text, or None when it is missing, so a check whose file was
    never written fails its own case instead of ending this file."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


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
          and "log-store" in (store_root / "README.md").read_text(encoding="utf-8"))
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
    check("the replacement tells the agent to match the displaced digest across the snapshots at the file's full path in the store on ned-box, not to search by path: a replaced file keeps its path, so the newest snapshots holding it hold the replacement",
          ("sha256sum /mnt/backup/timeshift/snapshots/*/localhost"
           f"/home/nedlern/nedschorus-logs/walk/{WALK}-minutes.md") in result.stderr
          and "find-deleted-path-across-backups" not in result.stderr
          and "sudo timeshift --list" not in result.stderr
          and "every ten minutes" not in result.stderr, result.stderr)

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

    # --- One run both replaces and links ------------------------------------
    both_walk = "both-steps-walk-2026-10-02"
    both_text = write_walk(walks, both_walk, FILES)
    first = ship(local_destination, str(both_text))
    (walks / f"{both_walk}-minutes.md").write_text("# minutes\n\nEdited.\n", encoding="utf-8")
    (walks / f"{both_walk}-dispositions.md").write_text("# dispositions\n", encoding="utf-8")
    result = ship(local_destination, str(both_text))
    check("one run that replaces the minutes and links a new dispositions file "
          "does both, exit 0",
          first.returncode == 0 and result.returncode == 0
          and "minutes replaced" in result.stdout and "1 file(s) added" in result.stdout
          and (store_walk / f"{both_walk}-minutes.md").read_text(encoding="utf-8")
          == "# minutes\n\nEdited.\n"
          and (store_walk / f"{both_walk}-dispositions.md").is_file(),
          f"{first.stdout} {result.stdout} {result.stderr}")

    # --- The dispositions are replaced like the minutes, and announced --------
    # (user-ruled 2026-09-18, walk skill-sentences-and-shipper-questions-2026-09-18
    # item 5: the dispositions file "is a sometimes updated status file").
    stored_dispositions = store_walk / f"{WALK}-dispositions.md"
    old_dispositions_digest = subprocess.run(
        ["shasum", "-a", "256", str(stored_dispositions)],
        capture_output=True, text=True).stdout.split()[0]
    (walks / f"{WALK}-dispositions.md").write_text(
        "# dispositions\n\nF1 fixed in PR later.\n", encoding="utf-8")
    result = ship(local_destination, str(walk_text))
    check("edited dispositions are replaced, exit 0, one line saying so",
          result.returncode == 0 and "dispositions replaced" in result.stdout
          and "REFUSED" not in result.stdout and one_line(result.stdout),
          result.stdout + result.stderr)
    check("the store now holds the new dispositions",
          stored_dispositions.read_text(encoding="utf-8").endswith("F1 fixed in PR later.\n"))
    check("the dispositions replacement is announced on stderr, naming the file, "
          "with the displaced sha256",
          any("REPLACED" in line and f"{WALK}-dispositions.md" in line
              and old_dispositions_digest in line
              for line in result.stderr.splitlines()), result.stderr)
    check("the dispositions replacement announcement is not on stdout",
          "REPLACED" not in result.stdout)
    check("the line still ends with the minutes' citation, not the dispositions'",
          result.stdout.rstrip().endswith(f"minutes at {store_walk}/{WALK}-minutes.md"),
          result.stdout)

    # --- A walk text the store holds that the local one does not merely add to
    # ships beside it as <walk>-revised-<n>.md, and is never refused; the
    # highest-numbered copy is the one the rules then apply to (see REVISED
    # COPIES in the shipper's docstring). Two store files that only look like
    # revised copies, a zero-padded number and a longer infix, must not count.
    def revised(number):
        return store_walk / f"{WALK}-revised-{number}.md"

    def revised_text(number):
        return text_or_none(revised(number))

    def store_names():
        return sorted(p.name for p in store_walk.iterdir())

    (store_walk / f"{WALK}-revised-01.md").write_text("not a revised copy\n", encoding="utf-8")
    (store_walk / f"{WALK}-revisedish-7.md").write_text("not a revised copy\n", encoding="utf-8")
    re_planned = "# walk\n\n## Item 1 of 3\n"
    (walks / f"{WALK}.md").write_text(re_planned, encoding="utf-8")
    (walks / f"{WALK}-minutes.md").write_text("# minutes\n\nre-planned to 3 items\n",
                                             encoding="utf-8")
    result = ship(local_destination, str(walk_text))
    check("a changed walk text is not REFUSED: it ships as revised copy 1, exit 0, one line",
          result.returncode == 0 and result.stdout.startswith("shipped:")
          and f"{WALK}-revised-1.md" in result.stdout and "REFUSED" not in result.stdout
          and one_line(result.stdout), result.stdout + result.stderr)
    check("revised copy 1 holds the changed walk text, and the original is kept as it was",
          revised_text(1) == re_planned
          and stored_walk_text.read_text(encoding="utf-8") == FILES[""],
          str(store_names()))
    check("the zero-padded and longer-infix look-alikes were not counted as copies",
          not revised(2).exists() and f"{WALK}-revised-01.md" in store_names(),
          str(store_names()))
    check("stderr says why the walk text shipped as a revised copy, naming both files",
          any(f"{WALK}.md differs from {WALK}.md" in line and f"{WALK}-revised-1.md" in line
              for line in result.stderr.splitlines()), result.stderr)
    check("the minutes were still replaced on the same run (per-file rules)",
          "minutes replaced" in result.stdout
          and stored_minutes.read_text(encoding="utf-8").endswith("re-planned to 3 items\n"),
          result.stdout)
    check("the line still ends with the minutes' citation",
          result.stdout.rstrip().endswith(f"{WALK}-minutes.md"), result.stdout)

    result = ship(local_destination, str(walk_text))
    check("the same walk text again is already there as revised copy 1: no copy 2",
          result.returncode == 0 and "already there unchanged" in result.stdout
          and not revised(2).exists() and "added" not in result.stdout,
          result.stdout + str(store_names()))

    displaced_revised_digest = digest_of_file(revised(1)) if revised(1).is_file() else "no revised copy 1 to digest"
    appended_re_planned = re_planned + "\n## Item 2 of 3\n"
    (walks / f"{WALK}.md").write_text(appended_re_planned, encoding="utf-8")
    result = ship(local_destination, str(walk_text))
    check("appended walk text: the latest revised copy, an exact prefix of the local "
          "one, is replaced in place, exit 0, no new copy",
          result.returncode == 0 and "walk text replaced" in result.stdout
          and revised_text(1) == appended_re_planned
          and not revised(2).exists() and one_line(result.stdout),
          result.stdout + result.stderr)
    check("appended walk text: the trace names the revised copy, the displaced "
          "sha256 and the prefix, on stderr only",
          any("REPLACED" in line and f"{WALK}-revised-1.md" in line
              and displaced_revised_digest in line and "exact byte prefix" in line
              for line in result.stderr.splitlines())
          and "REPLACED" not in result.stdout, result.stderr)
    check("appended walk text: the original is still untouched",
          stored_walk_text.read_text(encoding="utf-8") == FILES[""])

    for label, text, number in (
            ("shorter walk text (content removed)", re_planned, 2),
            ("same-length walk text (a byte changed)",
             appended_re_planned.replace("Item 1", "Item X"), 3),
            ("changed early and appended, longer than the latest copy",
             appended_re_planned.replace("Item 1", "Item Y") + "\n## Item 3 of 3\n", 4),
            ("the original's bytes again, while revised copies exist", FILES[""], 5)):
        before_copies = {name: (store_walk / name).read_bytes() for name in store_names()}
        (walks / f"{WALK}.md").write_text(text, encoding="utf-8")
        result = ship(local_destination, str(walk_text))
        check(f"{label}: ships as revised copy {number}, exit 0, never REFUSED",
              result.returncode == 0 and f"{WALK}-revised-{number}.md" in result.stdout
              and "REFUSED" not in result.stdout
              and revised_text(number) == text,
              result.stdout + result.stderr)
        check(f"{label}: every file the store held before is unchanged",
              all((store_walk / name).read_bytes() == content
                  for name, content in before_copies.items()
                  if not name.endswith("-minutes.md")), str(store_names()))

    appended_to_latest = FILES[""] + "\n## Item 2 of 2, added to the latest copy\n"
    (walks / f"{WALK}.md").write_text(appended_to_latest, encoding="utf-8")
    result = ship(local_destination, str(walk_text))
    check("with five revised copies, a walk text that only adds to the highest-numbered "
          "one replaces that copy, never an older one, and makes no new copy",
          result.returncode == 0 and "walk text replaced" in result.stdout
          and revised_text(5) == appended_to_latest
          and revised_text(1) == appended_re_planned
          and not revised(6).exists(), result.stdout + result.stderr)

    blocked_store = store_root / "walk"
    blocked_store.chmod(0o300)
    try:
        (walks / f"{WALK}.md").write_text(re_planned + "never shipped\n", encoding="utf-8")
        result = ship(local_destination, str(walk_text))
    finally:
        blocked_store.chmod(0o755)
    check("a store whose revised copies cannot be listed is FAILED, exit 1, one line, "
          "and no copy is made",
          result.returncode == 1 and result.stdout.startswith("FAILED:")
          and one_line(result.stdout) and not revised(6).exists(),
          result.stdout + result.stderr)
    # A new revised copy is listed in the roles' order, in the walk text's place.
    order_walk = "order-walk-2026-10-31"
    order_walk_text = write_walk(walks, order_walk, FILES)
    (store_walk / f"{order_walk}.md").write_text("# an older walk text\n", encoding="utf-8")
    result = ship(local_destination, str(order_walk_text))
    check("files added with a new revised copy are listed draft, suggestions, revised copy, minutes",
          f"4 file(s) added ({order_walk}-draft.md, {order_walk}-suggestions.md, "
          f"{order_walk}-revised-1.md, {order_walk}-minutes.md)" in result.stdout,
          result.stdout + result.stderr)

    # The remote-mode cases below need a walk text that only adds to FILES[""].
    (walks / f"{WALK}.md").write_text(FILES[""] + "\n## Item 2 of 2\n", encoding="utf-8")

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

    for label, arguments in (("no argument", ()),
                             ("two arguments", (str(walk_text), str(walk_text))),
                             ("an unknown option", ("--no-such-option", str(walk_text)))):
        result = ship(local_destination, *arguments)
        check(f"a bad invocation, {label}, is one FAILED line on stdout and exit 64, "
              f"as OUTPUT promises, not argparse's exit 2",
              result.returncode == 64 and result.stdout.startswith("FAILED: bad invocation")
              and one_line(result.stdout), f"exit {result.returncode}: {result.stdout}{result.stderr}")

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
    placing_marker = "# cold-read-record-ship: link staged files"
    replacing_marker = "# cold-read-record-ship: replace with staged files"
    listing_calls = [c for c in ssh_calls if "sha256sum" in " ".join(c)
                     and placing_marker not in c[-1] and replacing_marker not in c[-1]]
    check("the store's digests come from one ssh call naming each of the five paths",
          len(listing_calls) == 1
          and all(f"{RULED_WALK_PATH}/{WALK}{s}.md" in " ".join(listing_calls[0])
                  for s in list(FILES) + ["-dispositions"]), str(ssh_calls))
    staging_prefix = f"nedlern@ned-box:{RULED_WALK_PATH}/.ship-staging-{WALK}-"
    check("exactly one rsync call, the five files flat into a staging directory "
          "in walk/ named for the walk, over batch-mode ssh",
          len(rsync_calls) == 1 and "-a" in rsync_calls[0] and "--ignore-times" in rsync_calls[0]
          and "ssh -o BatchMode=yes -o ConnectTimeout=10" in rsync_calls[0]
          and rsync_calls[0][-1].startswith(staging_prefix)
          and rsync_calls[0][-1].endswith("/")
          and sorted(pathlib.Path(a).name for a in rsync_calls[0][-6:-1])
          == sorted(f"{WALK}{s}.md" for s in list(FILES) + ["-dispositions"]),
          str(rsync_calls))
    placing_calls = [c for c in ssh_calls if placing_marker in c[-1]]
    replacing_calls = [c for c in ssh_calls if replacing_marker in c[-1]]
    check("then one ssh call links the add-only files into walk/, never over an "
          "existing file, and removes the staging directory",
          len(placing_calls) == 1 and "ln -- " in placing_calls[0][-1]
          and "ln -f" not in placing_calls[0][-1]
          and all(f"{WALK}{s}.md" in placing_calls[0][-1] for s in ("-draft", "-suggestions", ""))
          and f"{WALK}-minutes.md" not in placing_calls[0][-1]
          and f"rm -rf -- {RULED_WALK_PATH}/.ship-staging-{WALK}-" in placing_calls[0][-1],
          str(placing_calls))
    check("and one ssh call renames the minutes and the dispositions into walk/, "
          "the two files a walk replaces",
          len(replacing_calls) == 1 and "mv -f -- " in replacing_calls[0][-1]
          and f"{WALK}-minutes.md" in replacing_calls[0][-1]
          and f"{WALK}-dispositions.md" in replacing_calls[0][-1]
          and f"{WALK}-draft.md" not in replacing_calls[0][-1],
          str(replacing_calls))
    check("rsync is never asked to delete or to write in place",
          not any(flag in rsync_calls[0] for flag in ("--delete", "--inplace")),
          str(rsync_calls))

    # Remote mode, a store that already holds a different dispositions file:
    # replaced, not refused, and the displaced digest the store reported is
    # what stderr announces.
    stubs_with_store = scratch / "stub-bin-with-store"
    stubs_with_store.mkdir()
    for binary, text in (("ssh", STUB_SSH_WITH_ONE_STORED_FILE), ("rsync", STUB_RECORDER)):
        stub = stubs_with_store / binary
        stub.write_text(text, encoding="utf-8")
        stub.chmod(0o755)
    stored_digest = "0123456789abcdef" * 4
    argv_log_with_store = scratch / "argv-with-store.jsonl"
    result = ship(RULED_RECORDS_DESTINATION, str(walk_text), extra_env={
        "PATH": f"{stubs_with_store}{os.pathsep}{os.environ.get('PATH', '')}",
        "WALK_SHIP_TEST_ARGV_LOG": str(argv_log_with_store),
        "WALK_SHIP_TEST_STORED_DIGEST_LINE":
            f"{stored_digest}  {RULED_WALK_PATH}/{WALK}-dispositions.md"})
    calls = [json.loads(line) for line in argv_log_with_store.read_text().splitlines()]
    rsync_calls = [c for c in calls if c[0].endswith("rsync")]
    check("remote mode replaces a differing stored dispositions file: exit 0, "
          "four added and dispositions replaced",
          result.returncode == 0 and result.stdout.startswith("shipped:")
          and "4 file(s) added" in result.stdout and "dispositions replaced" in result.stdout
          and one_line(result.stdout), result.stdout + result.stderr)
    check("remote mode announces the dispositions replacement on stderr with the "
          "digest the store reported",
          any("REPLACED" in line and f"{WALK}-dispositions.md" in line
              and stored_digest in line for line in result.stderr.splitlines()),
          result.stderr)
    check("remote mode's one rsync call still carries the dispositions file",
          len(rsync_calls) == 1
          and any(pathlib.Path(a).name == f"{WALK}-dispositions.md" for a in rsync_calls[0]),
          str(rsync_calls))

    # Remote mode, a store whose walk text is an exact prefix of the local one.
    # The size beside the digest is what the append exception reads, and this
    # is the only mode that parses it out of the store's listing: local mode
    # reads the stored file's own size.
    stored_prefix_bytes = FILES[""].encode("utf-8")
    stored_prefix_digest = hashlib.sha256(stored_prefix_bytes).hexdigest()
    argv_log_appended = scratch / "argv-appended.jsonl"
    result = ship(RULED_RECORDS_DESTINATION, str(walk_text), extra_env={
        "PATH": f"{stubs_with_store}{os.pathsep}{os.environ.get('PATH', '')}",
        "WALK_SHIP_TEST_ARGV_LOG": str(argv_log_appended),
        "WALK_SHIP_TEST_STORED_DIGEST_LINE":
            f"{stored_prefix_digest}  {RULED_WALK_PATH}/{WALK}.md",
        "WALK_SHIP_TEST_STORED_SIZE_LINE":
            f"size {len(stored_prefix_bytes)}  {RULED_WALK_PATH}/{WALK}.md"})
    calls = [json.loads(line) for line in argv_log_appended.read_text().splitlines()]
    rsync_calls = [c for c in calls if c[0].endswith("rsync")]
    check("remote mode reads the size beside the digest and replaces a walk text "
          "the walk only added to: exit 0, four added and walk text replaced",
          result.returncode == 0 and result.stdout.startswith("shipped:")
          and "4 file(s) added" in result.stdout and "walk text replaced" in result.stdout
          and "REFUSED" not in result.stdout and one_line(result.stdout),
          result.stdout + result.stderr)
    check("remote mode announces the walk text replacement with the digest the store "
          "reported and the prefix that allowed it",
          any("REPLACED" in line and f"{WALK}.md" in line and stored_prefix_digest in line
              and "exact byte prefix" in line for line in result.stderr.splitlines()),
          result.stderr)
    check("remote mode's one rsync call carries the walk text it replaced",
          len(rsync_calls) == 1
          and any(pathlib.Path(a).name == f"{WALK}.md" for a in rsync_calls[0]),
          str(rsync_calls))

    # Remote mode, a `sha256sum` that fails on a file the store holds (the
    # Codex review cell's question in the merge review of PR "The walk-files
    # shipper replaces a walk text the walk only added to",
    # https://github.com/nedschorus/nedschorus/pull/653). The
    # stand-in ssh RUNS the remote script under sh, so the loop the program
    # builds is what is tested, against a scratch store named by a stand-in
    # host; the stand-in sha256sum on PATH fails on the stored walk text and
    # hashes anything else; the stand-in rsync copies for real, so an
    # overwrite would show in the store. The stored walk text differs from the
    # local one and is not its prefix: listed, it is refused; missing from the
    # listing, it reads as not stored and is copied over.
    stubs_running_the_listing = scratch / "stub-bin-running-the-listing"
    stubs_running_the_listing.mkdir()
    for binary, text in (
            ("ssh", STUB_RECORDER + "import subprocess\n"
                    "sys.exit(subprocess.run(['sh', '-c', sys.argv[-1]]).returncode)\n"),
            ("sha256sum", "#!/usr/bin/env python3\n"
                          "import hashlib, os, sys\n"
                          "for path in [a for a in sys.argv[1:] if a != '--']:\n"
                          "    if os.path.basename(path) == os.environ['WALK_SHIP_TEST_SHA256SUM_FAILS_ON']:\n"
                          "        print(f'sha256sum: {path}: Permission denied', file=sys.stderr)\n"
                          "        sys.exit(1)\n"
                          "    with open(path, 'rb') as opened:\n"
                          "        print(f'{hashlib.sha256(opened.read()).hexdigest()}  {path}')\n"),
            ("rsync", STUB_RECORDER + "import shutil\n"
                      "directory = sys.argv[-1].partition(':')[2]\n"
                      "for source in [a for a in sys.argv[1:-1] if os.path.isfile(a)]:\n"
                      "    shutil.copyfile(source, os.path.join(directory, os.path.basename(source)))\n")):
        stub = stubs_running_the_listing / binary
        stub.write_text(text, encoding="utf-8")
        stub.chmod(0o755)
    listing_store = scratch / "listing-store"
    (listing_store / "walk").mkdir(parents=True)
    stored_walk_text_it_cannot_hash = "# walk\n\n## Item 1 of 2, as the store holds it\n"
    (listing_store / "walk" / f"{WALK}.md").write_text(stored_walk_text_it_cannot_hash,
                                                       encoding="utf-8")
    argv_log_listing = scratch / "argv-listing.jsonl"
    result = ship(f"stand-in-store-host:{listing_store}/cold-read-records", str(walk_text),
                  extra_env={
                      "PATH": f"{stubs_running_the_listing}{os.pathsep}{os.environ.get('PATH', '')}",
                      "WALK_SHIP_TEST_ARGV_LOG": str(argv_log_listing),
                      "WALK_SHIP_TEST_SHA256SUM_FAILS_ON": f"{WALK}.md"})
    calls = [json.loads(line) for line in argv_log_listing.read_text().splitlines()]
    check("a sha256sum that fails on a stored file is FAILED with exit 1 and one line "
          "saying nothing shipped, never read as that file not being stored",
          result.returncode == 1 and result.stdout.startswith("FAILED:")
          and "unshipped" in result.stdout and one_line(result.stdout),
          result.stdout + result.stderr)
    check("a sha256sum that fails on a stored file: its own error is passed on stderr",
          f"sha256sum: {listing_store}/walk/{WALK}.md: Permission denied" in result.stderr,
          result.stderr)
    check("a sha256sum that fails on a stored file: no rsync is run and the store's "
          "walk text is untouched",
          not any(c[0].endswith("rsync") for c in calls)
          and (listing_store / "walk" / f"{WALK}.md").read_text(encoding="utf-8")
          == stored_walk_text_it_cannot_hash, str(calls))

    # Remote mode lists the walk's revised copies with the shell glob the
    # program builds, run under sh against a scratch store: it must find
    # revised copy 1, skip a zero-padded look-alike, and add copy 2.
    revised_store = scratch / "revised-store"
    (revised_store / "walk").mkdir(parents=True)
    for file_name, text in ((f"{WALK}.md", "# walk, as first shipped\n"),
                            (f"{WALK}-revised-1.md", "# walk, revised once\n"),
                            (f"{WALK}-revised-01.md", "a look-alike\n")):
        (revised_store / "walk" / file_name).write_text(text, encoding="utf-8")
    # Every remote step runs for real here, under sh, with the system's own
    # sha256sum, so the store ends as a real shipment would leave it.
    stubs_running_every_step = scratch / "stub-bin-running-every-step"
    stubs_running_every_step.mkdir()
    for binary, text in (
            ("ssh", "#!/usr/bin/env python3\nimport os, signal, subprocess, sys\n"
                    "failure = os.environ.get('WALK_SHIP_TEST_REVISED_LISTING_FAILS')\n"
                    "if failure and '-revised-' in sys.argv[-1]:\n"
                    "    if failure == 'signal':\n"
                    "        os.kill(os.getpid(), signal.SIGTERM)\n"
                    "    sys.exit(255)\n"
                    "landing = os.environ.get('WALK_SHIP_TEST_LANDS_BEFORE_REPLACE')\n"
                    "if landing and '# cold-read-record-ship: replace with staged files' in sys.argv[-1]:\n"
                    "    with open(landing, 'w') as landed:\n"
                    "        landed.write('# walk, the other checkout\\'s revision\\n')\n"
                    "sys.exit(subprocess.run(['sh', '-c', sys.argv[-1]]).returncode)\n"),
            ("rsync", "#!/usr/bin/env python3\nimport os, shutil, sys\n"
                      "directory = sys.argv[-1].partition(':')[2]\n"
                      "os.makedirs(directory, exist_ok=True)\n"
                      "for source in [a for a in sys.argv[1:-1] if os.path.isfile(a)]:\n"
                      "    shutil.copyfile(source, os.path.join(directory, os.path.basename(source)))\n")):
        stub = stubs_running_every_step / binary
        stub.write_text(text, encoding="utf-8")
        stub.chmod(0o755)
    result = ship(f"stand-in-store-host:{revised_store}/cold-read-records", str(walk_text),
                  extra_env={
                      "PATH": f"{stubs_running_every_step}{os.pathsep}{os.environ.get('PATH', '')}"})
    check("remote mode lists the revised copies under sh and adds copy 2 beside copy 1",
          result.returncode == 0 and f"{WALK}-revised-2.md" in result.stdout
          and text_or_none(revised_store / "walk" / f"{WALK}-revised-2.md")
          == walk_text.read_text(encoding="utf-8")
          and text_or_none(revised_store / "walk" / f"{WALK}-revised-1.md")
          == "# walk, revised once\n", result.stdout + result.stderr)
    # A listing of the revised copies that fails, by an exit or by a signal, is
    # FAILED with one line and copies nothing, never read as "no copies".
    for failure in ("exit", "signal"):
        before_copies = sorted(p.name for p in (revised_store / "walk").iterdir())
        result = ship(f"stand-in-store-host:{revised_store}/cold-read-records", str(walk_text),
                      extra_env={
                          "PATH": f"{stubs_running_every_step}{os.pathsep}{os.environ.get('PATH', '')}",
                          "WALK_SHIP_TEST_REVISED_LISTING_FAILS": failure})
        check(f"remote mode: a revised-copy listing that fails by {failure} is FAILED, exit 1, "
              f"one line, and nothing is copied",
              result.returncode == 1 and result.stdout.startswith("FAILED:")
              and one_line(result.stdout) and "unshipped" in result.stdout
              and sorted(p.name for p in (revised_store / "walk").iterdir()) == before_copies,
              result.stdout + result.stderr)
    # Remote mode, under sh: the other shipment adds revised copy 1 just
    # before this one's replace step, so the walk text this one only added
    # to is no longer the store's latest copy: REFUSED, the original not
    # appended to.
    overtaken_store = scratch / "overtaken-store"
    (overtaken_store / "walk").mkdir(parents=True)
    (overtaken_store / "walk" / f"{WALK}.md").write_text(FILES[""], encoding="utf-8")
    grown_walk_text = write_walk(scratch / "overtaken-walks", WALK,
                                 {**FILES, "": FILES[""] + "\n## Item 2 of 2\n"})
    landing_path = overtaken_store / "walk" / f"{WALK}-revised-1.md"
    result = ship(f"stand-in-store-host:{overtaken_store}/cold-read-records",
                  str(grown_walk_text), extra_env={
                      "PATH": f"{stubs_running_every_step}{os.pathsep}{os.environ.get('PATH', '')}",
                      "WALK_SHIP_TEST_LANDS_BEFORE_REPLACE": str(landing_path)})
    check("remote mode: a walk text only added to, overtaken by another shipment's "
          "revised copy 1 before the replace step, is REFUSED, exit 2, naming it, "
          "and the original is not appended to",
          result.returncode == 2 and result.stdout.startswith("REFUSED:")
          and f"{WALK}-revised-1.md" in result.stdout and one_line(result.stdout)
          and (overtaken_store / "walk" / f"{WALK}.md").read_text(encoding="utf-8")
          == FILES[""] and landing_path.is_file(),
          result.stdout + result.stderr)
    # A store walk/ that cannot be read (0300: cd works, the glob matches
    # nothing) or cannot be entered (0600: cd fails) is FAILED with one line
    # and copies nothing, never read as "no revised copies"; locally and
    # under sh. Without it, the walk text would ship as revised copy 1 while
    # copy 1 exists.
    for mode in (0o300, 0o600):
        for where in ("remote", "local"):
            before_copies = sorted(p.name for p in (revised_store / "walk").iterdir())
            (revised_store / "walk").chmod(mode)
            try:
                if where == "remote":
                    result = ship(f"stand-in-store-host:{revised_store}/cold-read-records",
                                  str(walk_text), extra_env={
                                      "PATH": f"{stubs_running_every_step}{os.pathsep}"
                                              f"{os.environ.get('PATH', '')}"})
                else:
                    result = ship(f"{revised_store}/cold-read-records", str(walk_text))
            finally:
                (revised_store / "walk").chmod(0o700)
            check(f"{where} mode: a store walk/ of mode {mode:o}, whose revised copies "
                  f"cannot be listed, is FAILED, exit 1, one line, and nothing is copied",
                  result.returncode == 1 and result.stdout.startswith("FAILED:")
                  and one_line(result.stdout) and "unshipped" in result.stdout
                  and sorted(p.name for p in (revised_store / "walk").iterdir()) == before_copies,
                  result.stdout + result.stderr)

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

    # --- The README the record shipper writes names walk/'s owners only -----
    # It listed `walk/` and this program's five files until 2026-09-19, and
    # went stale at every ruling that changed them (user-ruled, walk
    # file-naming-and-location-standards-cold-read-findings, item 5). It lists
    # the kinds again since 2026-09-27, each naming only its owner (user-ruled,
    # walk file-naming-page-revision-2026-09-23, item 9): what a walk's files
    # are called stays the walk-me-through skill's, so no ending may appear.
    check("the store README's walk/ line names the walk-me-through skill and "
          "this program, and none of the walk files' endings",
          "- `walk/` -- " in module.shipper.STORE_README
          and "walk-me-through skill" in module.shipper.STORE_README
          and "scripts/walk-files-ship.py" in module.shipper.STORE_README
          and not any(ending in module.shipper.STORE_README
                      for ending in ("-draft.md", "-suggestions.md",
                                     "-minutes.md", "-dispositions.md")),
          module.shipper.STORE_README)

# --- TWO SHIPMENTS OF ONE WALK AT ONCE --------------------------------------
# Two checkouts ship the same walk in the same seconds. The other shipment's
# file is made to land at a chosen moment of this one, in this process: after
# this one has listed the store ("after-listing"), after its rsync has run
# ("after-copy"), or the instant after its own rename put a replaced file in
# place ("after-rename"). Whatever the store keeps, this shipment must say so:
# never shipped: while the store holds another shipment's bytes under an
# add-only name, and never a replacement nobody announced.
with tempfile.TemporaryDirectory(prefix="walk-files-ship-race-test-") as race_scratch_name:
    race_scratch = pathlib.Path(race_scratch_name)
    racing_spec = importlib.util.spec_from_file_location("walk_files_ship_racing", SHIP)
    racing = importlib.util.module_from_spec(racing_spec)
    saved_destination = os.environ.pop(DESTINATION_VARIABLE, None)
    try:
        racing_spec.loader.exec_module(racing)
    finally:
        if saved_destination is not None:
            os.environ[DESTINATION_VARIABLE] = saved_destination
    saved_listing = racing.store_digests_and_sizes
    saved_subprocess_run = subprocess.run
    saved_os_replace = os.replace

    def ship_while_the_other_lands(case_label, local_files, stored_files,
                                   landing_suffix, landing_text, moment):
        """Ship a walk whose files are `local_files` into a store holding
        `stored_files`, while the other shipment's `landing_suffix` file,
        `landing_text`, lands at `moment`. Returns the exit code, stdout,
        stderr, the store's walk/ texts by suffix, and the names in walk/."""
        walk_directory = race_scratch / f"walks-{case_label}"
        write_walk(walk_directory, WALK, local_files)
        walk_store = race_scratch / f"store-{case_label}" / "walk"
        walk_store.mkdir(parents=True)
        for suffix, text in stored_files.items():
            (walk_store / f"{WALK}{suffix}.md").write_text(text, encoding="utf-8")
        landed_path = walk_store / f"{WALK}{landing_suffix}.md"
        landed = []

        def land_the_other():
            if not landed:
                landed.append(moment)
                landed_path.write_text(landing_text, encoding="utf-8")

        def listing_then_land(copy_host, targets):
            answer = saved_listing(copy_host, targets)
            if moment == "after-listing":
                land_the_other()
            return answer

        def run_then_land(command, *args, **kwargs):
            completed = saved_subprocess_run(command, *args, **kwargs)
            if moment == "after-copy" and command and command[0] == "rsync":
                # Written over whatever this shipment's copy put there: the
                # other shipment's copy, which listed the store before this
                # one's landed, finishing after it.
                land_the_other()
            return completed

        def replace_then_land(source, destination, *args, **kwargs):
            saved_os_replace(source, destination, *args, **kwargs)
            if moment == "after-rename" and pathlib.Path(destination) == landed_path:
                land_the_other()

        destination = racing.WalkStoreDestination(None, None,
                                                  pathlib.PurePosixPath(walk_store))
        out, err = io.StringIO(), io.StringIO()
        racing.store_digests_and_sizes = listing_then_land
        subprocess.run = run_then_land
        os.replace = replace_then_land
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = racing.ship_walk(destination, WALK, walk_directory)
        finally:
            racing.store_digests_and_sizes = saved_listing
            subprocess.run = saved_subprocess_run
            os.replace = saved_os_replace
        kept = {suffix: (walk_store / f"{WALK}{suffix}.md").read_text(encoding="utf-8")
                for suffix in ("-draft", "-suggestions", "", "-minutes", "-dispositions")
                if (walk_store / f"{WALK}{suffix}.md").is_file()}
        return (code, out.getvalue(), err.getvalue(), kept,
                sorted(p.name for p in walk_store.iterdir()))

    def digest_of(text):
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    other_draft = "# draft, the other checkout's\n"
    code, out, err, kept, names = ship_while_the_other_lands(
        "draft-taken", FILES, {}, "-draft", other_draft, "after-listing")
    check("an add-only draft the other shipment lands between this one's listing "
          "and its copy is REFUSED by name, never shipped:",
          code == 2 and out.startswith("REFUSED:") and f"{WALK}-draft.md" in out
          and one_line(out), f"exit {code}: {out}{err}")
    check("that refusal leaves the other shipment's draft in the store, not "
          "overwritten", kept.get("-draft") == other_draft, repr(kept.get("-draft")))
    check("and the walk's other files still ship: the minutes and the walk text "
          "are this checkout's", kept.get("-minutes") == FILES["-minutes"]
          and kept.get("") == FILES[""], repr(kept))

    code, out, err, kept, names = ship_while_the_other_lands(
        "draft-taken-after-copy", FILES, {}, "-draft", other_draft, "after-copy")
    check("an add-only draft the other shipment lands after this one's copy ran "
          "never lets this one print shipped: while the store holds the other's",
          (code == 2 and out.startswith("REFUSED:") and kept.get("-draft") == other_draft)
          or (code == 0 and out.startswith("shipped:") and kept.get("-draft") == FILES["-draft"]),
          f"exit {code}: {out}; store keeps {kept.get('-draft')!r}")

    code, out, err, kept, names = ship_while_the_other_lands(
        "draft-same-bytes", FILES, {}, "-draft", FILES["-draft"], "after-listing")
    check("the other shipment landing the SAME draft bytes is no difference: "
          "shipped:, exit 0",
          code == 0 and out.startswith("shipped:") and kept.get("-draft") == FILES["-draft"],
          f"exit {code}: {out}{err}")

    stored_prefix = FILES[""]
    grown_here = dict(FILES, **{"": FILES[""] + "\n## Item 2 of 2, this checkout's\n"})
    grown_there = FILES[""] + "\n## Item 2 of 2, the other checkout's\n"
    code, out, err, kept, names = ship_while_the_other_lands(
        "walk-text-grown-there", grown_here, {"": stored_prefix}, "", grown_there,
        "after-listing")
    check("a walk text the other shipment replaced between this one's listing and "
          "its copy is REFUSED by name, though this one only added to the copy it "
          "listed", code == 2 and out.startswith("REFUSED:") and f"{WALK}.md" in out
          and one_line(out), f"exit {code}: {out}{err}")
    check("that refusal leaves the other shipment's walk text in the store",
          kept.get("") == grown_there, repr(kept.get("")))

    # The other shipment adds the next revised copy between this one's listing
    # and its replace step, leaving the copy this one tested unchanged: the
    # copy is no longer the store's latest, so this one is REFUSED and appends
    # nothing, at revised copy 1 (no copy before) and at copy 2 (one before).
    other_revised = "# walk, the other checkout's revision\n"
    for label, stored, latest_suffix, landing in (
            ("walk-text-overtaken-by-revised-1", {"": stored_prefix}, "", "-revised-1"),
            ("walk-text-overtaken-by-revised-2", {"": "# walk, as first shipped\n",
                                                  "-revised-1": stored_prefix},
             "-revised-1", "-revised-2")):
        code, out, err, kept, names = ship_while_the_other_lands(
            label, grown_here, stored, landing, other_revised, "after-listing")
        walk_store = race_scratch / f"store-{label}" / "walk"
        check(f"{label}: a walk text this one only added to, overtaken by the other "
              f"shipment's {WALK}{landing}.md, is REFUSED, exit 2, one line naming it",
              code == 2 and out.startswith("REFUSED:") and f"{WALK}{landing}.md" in out
              and one_line(out), f"exit {code}: {out}{err}")
        check(f"{label}: the copy it tested is not appended to, and the other's "
              f"revised copy is kept",
              (walk_store / f"{WALK}{latest_suffix}.md").read_text(encoding="utf-8")
              == stored_prefix
              and (walk_store / f"{WALK}{landing}.md").read_text(encoding="utf-8")
              == other_revised, str(names))

    other_minutes = "# minutes, the other checkout's\n"
    code, out, err, kept, names = ship_while_the_other_lands(
        "minutes-landed", FILES, {}, "-minutes", other_minutes, "after-listing")
    check("minutes the other shipment lands after this one listed none are "
          "replaced, by the minutes' rule: shipped:, exit 0, this checkout's "
          "minutes kept", code == 0 and out.startswith("shipped:")
          and kept.get("-minutes") == FILES["-minutes"], f"exit {code}: {out}{err}")
    check("and that replacement is announced on stderr with the displaced "
          "minutes' digest, never silent",
          any("REPLACED" in line and f"{WALK}-minutes.md" in line
              and digest_of(other_minutes) in line for line in err.splitlines()),
          err)

    code, out, err, kept, names = ship_while_the_other_lands(
        "minutes-after-copy", FILES, {}, "-minutes", other_minutes, "after-copy")
    check("minutes the other shipment lands after this one's copy ran: either "
          "this one's are kept and the displaced digest announced, or this one "
          "is FAILED -- never shipped: over the other's minutes",
          (code == 0 and out.startswith("shipped:")
           and kept.get("-minutes") == FILES["-minutes"]
           and digest_of(other_minutes) in err)
          or (code == 1 and out.startswith("FAILED:")
              and kept.get("-minutes") == other_minutes),
          f"exit {code}: {out}{err}; store keeps {kept.get('-minutes')!r}")

    code, out, err, kept, names = ship_while_the_other_lands(
        "minutes-after-rename", FILES, {}, "-minutes", other_minutes, "after-rename")
    check("minutes the other shipment renames in the instant after this one's: "
          "FAILED, exit 1, naming the minutes, never shipped:",
          code == 1 and out.startswith("FAILED:") and f"{WALK}-minutes.md" in out
          and one_line(out) and kept.get("-minutes") == other_minutes,
          f"exit {code}: {out}{err}")

    check("no shipment leaves anything in the store's walk/ beside the walk's "
          "own files", all(
              all(not name.startswith(".") for name in
                  (p.name for p in (race_scratch / f"store-{label}" / "walk").iterdir()))
              for label in ("draft-taken", "draft-taken-after-copy", "draft-same-bytes",
                            "walk-text-grown-there", "walk-text-overtaken-by-revised-1",
                            "walk-text-overtaken-by-revised-2", "minutes-landed",
                            "minutes-after-copy", "minutes-after-rename")),
          str(names))

# --- A walk's close writes no handoff marker ----------------------------------
with tempfile.TemporaryDirectory(prefix="walk-files-ship-test-close-") as close_scratch_name:
    close_scratch = pathlib.Path(close_scratch_name)
    close_home = close_scratch / "home"
    close_home.mkdir()
    CLOSE_WALK = "close-demo-walk-2026-10-27"
    closed_minutes = ("# minutes\n\nItem 1 ruled.\n\n#next_to_present item 2 of 2\n"
                      "Item 2 ruled.\n\n#next_to_present none, closed\n")
    close_walk_text = write_walk(close_scratch / "walks", CLOSE_WALK,
                                 {**FILES, "-minutes": closed_minutes})
    result = ship(str(close_scratch / "store" / "cold-read-records"), str(close_walk_text),
                  extra_env={"HOME": str(close_home),
                             "CLAUDE_CODE_SESSION_ID": "walk-files-ship-test-session"})
    handoffs_directory = close_home / ".claude" / "handoffs"
    handoff_files = (sorted(str(path) for path in handoffs_directory.rglob("*"))
                     if handoffs_directory.exists() else [])
    check("shipping closed minutes with a session id set exits 0 and writes "
          "nothing under ~/.claude/handoffs",
          result.returncode == 0 and result.stdout.startswith("shipped:")
          and not handoff_files,
          f"exit {result.returncode}: {result.stdout}{result.stderr}; "
          f"under ~/.claude/handoffs: {handoff_files}")

# --- Failures after part of a shipment reached the store ---------------------
# "ssh" in the prefix puts it in every path these FAILED lines carry, so a
# check for "ssh" as a bare substring fails on every run, not on a rare
# random name.
with tempfile.TemporaryDirectory(prefix="walk-files-ship-test-partial-ssh-") as partial_scratch_name:
    partial_scratch = pathlib.Path(partial_scratch_name)
    PARTIAL_WALK = "partial-demo-walk-2026-10-24"
    partial_minutes = "# minutes\n\nItem 1 ruled.\n\n#next_to_present item 2 of 2\n"

    # The minutes land, then the add-only placement fails.
    partial_spec = importlib.util.spec_from_file_location("walk_files_ship_partial", SHIP)
    partial = importlib.util.module_from_spec(partial_spec)
    partial_spec.loader.exec_module(partial)
    partial_walks = partial_scratch / "partial-walks"
    write_walk(partial_walks, PARTIAL_WALK, {**FILES, "-minutes": partial_minutes})
    partial_store = partial_scratch / "partial-store" / "walk"
    partial_store.mkdir(parents=True)
    partial_destination = partial.WalkStoreDestination(
        None, None, pathlib.PurePosixPath(partial_store))
    real_placement = partial.shipper.link_staged_files_never_over_existing

    def placement_that_fails(copy_host, staging_dir, walk_path, names):
        return subprocess.CompletedProcess([], 255, "Disk quota exceeded (injected)", "injected: ssh exit 255\n"), None

    def rerun_sentence(module, walks, walk):
        return (f"`{module.REPO_ROOT}/scripts/walk-files-ship.py "
                f"{walks}/{walk}-minutes.md`")

    def ship_in_process():
        # An injected OSError that escapes ship_walk fails the calling case by
        # name, instead of ending this file before its later cases run.
        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = partial.ship_walk(partial_destination, PARTIAL_WALK, partial_walks)
        except OSError:
            check("ship_walk returns rather than raising OSError", False,
                  traceback.format_exc())
            return None, out.getvalue(), err.getvalue()
        return code, out.getvalue(), err.getvalue()

    partial.shipper.link_staged_files_never_over_existing = placement_that_fails
    try:
        failed_code, failed_out, failed_err = ship_in_process()
        staging_left_after_failed_placement = sorted(
            path.name for path in partial_store.glob(".ship-staging-*"))
        partial.shipper.link_staged_files_never_over_existing = real_placement
        retry_code, retry_out, retry_err = ship_in_process()
    finally:
        partial.shipper.link_staged_files_never_over_existing = real_placement
    check("a run whose minutes land but whose add-only placement fails is FAILED, exit 1",
          failed_code == 1 and failed_out.startswith("FAILED:")
          and (partial_store / f"{PARTIAL_WALK}-minutes.md").is_file(),
          f"exit {failed_code}: {failed_out}{failed_err}")
    check("an add-only placement that fails removes this run's staging directory, "
          "which would otherwise stop the next shipment",
          not staging_left_after_failed_placement
          and failed_out == (f"FAILED: {PARTIAL_WALK} — Disk quota exceeded (injected) "
                             f"while putting the copied files in place. Rerun: "
                             f"{rerun_sentence(partial, partial_walks, PARTIAL_WALK)}\n"),
          f"left in the store: {staging_left_after_failed_placement}; {failed_out}")
    check("the retry after that partial failure ships the rest",
          retry_code == 0 and retry_out.startswith("shipped:")
          and "already there unchanged" in retry_out,
          f"exit {retry_code}: {retry_out}{retry_err}")

    # The renames of the replaced files put the minutes in place, then fail
    # without saying which were done.
    partial_walks = partial_scratch / "partial-walks-renames"
    write_walk(partial_walks, PARTIAL_WALK, {**FILES, "-minutes": partial_minutes})
    partial_store = partial_scratch / "partial-store-renames" / "walk"
    partial_store.mkdir(parents=True)
    partial_destination = partial.WalkStoreDestination(
        None, None, pathlib.PurePosixPath(partial_store))
    real_renames = partial.shipper.replace_with_staged_files
    minutes_file_name = f"{PARTIAL_WALK}-minutes.md"

    def renames_that_fail_after_the_minutes(copy_host, staging_dir, walk_path, files):
        os.replace(pathlib.Path(staging_dir) / minutes_file_name,
                   pathlib.Path(walk_path) / minutes_file_name)
        return subprocess.CompletedProcess([], 255, "Disk quota exceeded (injected)", "injected: ssh exit 255\n"), None

    partial.shipper.replace_with_staged_files = renames_that_fail_after_the_minutes
    try:
        failed_code, failed_out, failed_err = ship_in_process()
        partial.shipper.replace_with_staged_files = real_renames
        retry_code, retry_out, retry_err = ship_in_process()
    finally:
        partial.shipper.replace_with_staged_files = real_renames
    check("a run whose renames put the minutes in place, then fail without "
          "saying which were done, is FAILED, exit 1",
          failed_code == 1 and failed_out.startswith("FAILED:")
          and (partial_store / minutes_file_name).is_file(),
          f"exit {failed_code}: {failed_out}{failed_err}")
    check("the retry after those failed renames ships the rest",
          retry_code == 0 and retry_out.startswith("shipped:")
          and "already there unchanged" in retry_out,
          f"exit {retry_code}: {retry_out}{retry_err}")

    # The minutes are in the store unchanged and only the dispositions are replaced.
    partial_walks = partial_scratch / "partial-walks-dispositions"
    write_walk(partial_walks, PARTIAL_WALK,
               {**FILES, "-minutes": partial_minutes, "-dispositions": "# dispositions\n"})
    partial_store = partial_scratch / "partial-store-dispositions" / "walk"
    partial_store.mkdir(parents=True)
    partial_destination = partial.WalkStoreDestination(
        None, None, pathlib.PurePosixPath(partial_store))
    try:
        first_code, first_out, first_err = ship_in_process()
        (partial_walks / f"{PARTIAL_WALK}-dispositions.md").write_text(
            "# dispositions\n\nItem 1: approved.\n", encoding="utf-8")

        def renames_that_fail(copy_host, staging_dir, walk_path, files):
            return subprocess.CompletedProcess([], 255, "Disk quota exceeded (injected)", "injected: ssh exit 255\n"), None

        partial.shipper.replace_with_staged_files = renames_that_fail
        failed_code, failed_out, failed_err = ship_in_process()
    finally:
        partial.shipper.replace_with_staged_files = real_renames
    check("the first shipment of the walk with dispositions succeeds",
          first_code == 0 and first_out.startswith("shipped:"),
          f"exit {first_code}: {first_out}{first_err}")
    check("a run whose minutes are already in the store unchanged, and whose renames "
          "of the replaced dispositions fail, is FAILED, exit 1",
          failed_code == 1 and failed_out.startswith("FAILED:")
          and failed_out == (f"FAILED: {PARTIAL_WALK} — Disk quota exceeded (injected) "
                             f"while putting the copied files in place. Rerun: "
                             f"{rerun_sentence(partial, partial_walks, PARTIAL_WALK)}\n"),
          f"exit {failed_code}: {failed_out}{failed_err}")

    # On the local path a rename that fails raises OSError, which must reach
    # ship_walk as a failed result.
    saved_os_replace = os.replace
    for failing_suffix, minutes_land in (("-dispositions", True), ("-minutes", False)):
        partial_walks = partial_scratch / f"local-rename{failing_suffix}-walks"
        write_walk(partial_walks, PARTIAL_WALK,
                   {**FILES, "-minutes": partial_minutes, "-dispositions": "# dispositions\n"})
        partial_store = partial_scratch / f"local-rename{failing_suffix}-store" / "walk"
        partial_store.mkdir(parents=True)
        partial_destination = partial.WalkStoreDestination(
            None, None, pathlib.PurePosixPath(partial_store))
        failing_name = f"{PARTIAL_WALK}{failing_suffix}.md"

        def replace_that_fails_on(source, destination, *args, **kwargs):
            if pathlib.Path(destination) == partial_store / failing_name:
                raise OSError(28, "No space left on device (injected)")
            saved_os_replace(source, destination, *args, **kwargs)

        os.replace = replace_that_fails_on
        try:
            failed_code, failed_out, failed_err = ship_in_process()
            os.replace = saved_os_replace
            minutes_after_failed_run = (partial_store / minutes_file_name).is_file()
            retry_code, retry_out, retry_err = ship_in_process()
        finally:
            os.replace = saved_os_replace
        check(f"a local run whose rename of {failing_name} raises OSError is FAILED, "
              f"exit 1, and names the OS's reason",
              failed_code == 1 and failed_out.startswith("FAILED:")
              and one_line(failed_out) and "No space left on device" in failed_out
              and minutes_after_failed_run == minutes_land,
              f"exit {failed_code}: {failed_out}{failed_err}")
        check(f"the retry after the local rename of {failing_name} failed ships the rest",
              retry_code == 0 and retry_out.startswith("shipped:"),
              f"exit {retry_code}: {retry_out}{retry_err}")

    # A local read of one file in the store that fails. The store starts
    # empty, the staged copies sit in a directory below it, and a replaced
    # file is read before its rename only when the store holds it, so a file
    # the run puts there is first read by the read-back after it is placed.
    saved_read_bytes = pathlib.Path.read_bytes

    def ship_with_read_failing_for(failing_name):
        def read_bytes_that_fails(path):
            if path == partial_store / failing_name:
                raise OSError(28, "No space left on device (injected)")
            return saved_read_bytes(path)

        pathlib.Path.read_bytes = read_bytes_that_fails
        try:
            return ship_in_process()
        finally:
            pathlib.Path.read_bytes = saved_read_bytes

    def fresh_walk_and_store(label):
        global partial_walks, partial_store, partial_destination
        partial_walks = partial_scratch / f"local-read-{label}-walks"
        write_walk(partial_walks, PARTIAL_WALK, {**FILES, "-minutes": partial_minutes})
        partial_store = partial_scratch / f"local-read-{label}-store" / "walk"
        partial_store.mkdir(parents=True)
        partial_destination = partial.WalkStoreDestination(
            None, None, pathlib.PurePosixPath(partial_store))

    fresh_walk_and_store("after-rename")
    failed_code, failed_out, failed_err = ship_with_read_failing_for(minutes_file_name)
    check("a local run whose read-back of the stored digests after the renames raises "
          "OSError is FAILED, exit 1, and names the OS's reason, the minutes being "
          "in the store",
          failed_code == 1 and failed_out.startswith("FAILED:")
          and one_line(failed_out) and "No space left on device" in failed_out
          and (partial_store / minutes_file_name).is_file(),
          f"exit {failed_code}: {failed_out}{failed_err}")

    fresh_walk_and_store("after-link")
    draft_name = f"{PARTIAL_WALK}-draft.md"
    failed_code, failed_out, failed_err = ship_with_read_failing_for(draft_name)
    check("a local run whose read-back after the add-only links raises OSError is "
          "FAILED, exit 1, and names the OS's reason and not an ssh exit",
          failed_code == 1
          and failed_out.startswith(f"FAILED: {PARTIAL_WALK} — No space left on device "
                                    f"(injected) while putting the copied files in place")
          and "ssh exit" not in failed_out,
          f"exit {failed_code}: {failed_out}{failed_err}")

    fresh_walk_and_store("listing")
    (partial_store / draft_name).write_text(FILES["-draft"], encoding="utf-8")
    failed_code, failed_out, failed_err = ship_with_read_failing_for(draft_name)
    check("a local run whose listing of the store raises OSError is FAILED, exit 1, "
          "names the OS's reason and not an ssh exit, and copies nothing",
          failed_code == 1
          and failed_out.startswith(f"FAILED: {PARTIAL_WALK} — No space left on device "
                                    f"(injected); the walk's files stay on disk")
          and "ssh exit" not in failed_out and not (partial_store / minutes_file_name).exists(),
          f"exit {failed_code}: {failed_out}{failed_err}")

    # The store's listing names revised copy 1, which is gone before its
    # digest is read, beside a walk text with other bytes: the local walk
    # text still ships as the next revised copy, never by its own name, where
    # the add-only placing would refuse it.
    fresh_walk_and_store("revised-copy-gone")
    walk_text_name = f"{PARTIAL_WALK}.md"
    (partial_store / walk_text_name).write_text("# walk, an older checkout's\n", encoding="utf-8")
    real_revised_listing = partial.stored_revised_walk_text_numbers
    partial.stored_revised_walk_text_numbers = (
        lambda copy_host, walk_path, name: (subprocess.CompletedProcess([], 0, "", ""), [1]))
    try:
        gone_code, gone_out, gone_err = ship_in_process()
    finally:
        partial.stored_revised_walk_text_numbers = real_revised_listing
    check("a revised copy the listing named but the digest read did not find: the walk text "
          "ships as revised copy 2, exit 0, and the stored walk text is kept",
          gone_code == 0 and gone_out.startswith("shipped:")
          and text_or_none(partial_store / f"{PARTIAL_WALK}-revised-2.md") == FILES[""]
          and text_or_none(partial_store / walk_text_name) == "# walk, an older checkout's\n",
          f"exit {gone_code}: {gone_out}{gone_err}")

# --- This run's staging directory cannot be removed ---------------------------
with tempfile.TemporaryDirectory(prefix="walk-files-ship-test-left-behind-") as left_scratch_name:
    left_scratch = pathlib.Path(left_scratch_name)
    LEFT_WALK = "left-behind-demo-walk-2026-10-29"
    left_spec = importlib.util.spec_from_file_location("walk_files_ship_left_behind", SHIP)
    left = importlib.util.module_from_spec(left_spec)
    left_spec.loader.exec_module(left)
    real_removal = left.shipper.remove_staging_directory
    real_left_rsync = left.rsync_files
    real_left_renames = left.shipper.replace_with_staged_files
    staging_marker = f".ship-staging-{LEFT_WALK}-"

    def removal_that_fails(copy_host, staging_dir):
        return "Permission denied (injected)"

    def left_walk_and_store(label):
        walks = left_scratch / f"{label}-walks"
        write_walk(walks, LEFT_WALK, FILES)
        store = left_scratch / f"{label}-store" / "walk"
        store.mkdir(parents=True)
        return walks, store, left.WalkStoreDestination(None, None, pathlib.PurePosixPath(store))

    def ship_left(walks, destination, removal=removal_that_fails):
        out, err = io.StringIO(), io.StringIO()
        left.shipper.remove_staging_directory = removal
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = left.ship_walk(destination, LEFT_WALK, walks)
        finally:
            left.shipper.remove_staging_directory = real_removal
        return code, out.getvalue(), err.getvalue()

    def names_the_directory_and_its_deletion(line, store):
        return (f"{store}/{staging_marker}" in line and "Permission denied (injected)" in line
                and f"`rm -rf -- {store}/{staging_marker}" in line)

    def deletion_then_rerun(line, walks, store, what_failed):
        return (line.startswith(f"FAILED: {LEFT_WALK} — {what_failed}. This run's "
                                f"staging directory {store}/{staging_marker}")
                and one_line(line) and names_the_directory_and_its_deletion(line, store)
                and "Deleting it loses nothing" in line
                and line.endswith(f"`. Then rerun: `{left.REPO_ROOT}/scripts/walk-files-ship.py "
                                  f"{walks}/{LEFT_WALK}-minutes.md`\n"))

    # A shipment whose files all land, then whose staging directory stays.
    walks, store, destination = left_walk_and_store("after-placing")
    first = ship_left(walks, destination, removal=real_removal)
    (walks / f"{LEFT_WALK}-minutes.md").write_text("# minutes\n\nItem 2 ruled.\n",
                                                    encoding="utf-8")
    code, out, err = ship_left(walks, destination)
    check("the first shipment of the walk whose staging directory later stays succeeds",
          first[0] == 0, str(first))
    check("a shipment whose minutes are replaced but whose staging directory cannot be "
          "removed is FAILED, exit 1, one line naming the directory, why, the command "
          "that deletes it, and the minutes' citation",
          code == 1 and out.startswith(f"FAILED: {LEFT_WALK} — This run's staging directory")
          and one_line(out) and names_the_directory_and_its_deletion(out, store)
          and "minutes replaced" in out
          and "Ship the walk again only from the checkout" not in out
          and out.rstrip().endswith(f"minutes at {store}/{LEFT_WALK}-minutes.md")
          and (store / f"{LEFT_WALK}-minutes.md").read_text(encoding="utf-8").endswith("Item 2 ruled.\n"),
          f"exit {code}: {out}{err}")
    (walks / f"{LEFT_WALK}-minutes.md").write_text("# minutes\n\nItem 3 ruled.\n",
                                                    encoding="utf-8")
    code, out, err = ship_left(walks, destination, removal=real_removal)
    check("the directory it named stops the next shipment that replaces a file, which "
          "is why it is FAILED and not shipped",
          code == 1 and out.startswith(f"FAILED: {LEFT_WALK} — another shipment")
          and f"{store}/{staging_marker}" in out, f"exit {code}: {out}{err}")

    # The same, with an add-only file refused: 1 wins over 2.
    walks, store, destination = left_walk_and_store("refused-too")
    first = ship_left(walks, destination, removal=real_removal)
    # The draft, not the walk text: a rewritten walk text ships as a revised
    # copy, and placing that copy removes the staging directory itself.
    (walks / f"{LEFT_WALK}-draft.md").write_text("# draft, rewritten\n", encoding="utf-8")
    (walks / f"{LEFT_WALK}-minutes.md").write_text("# minutes\n\nItem 2 ruled.\n",
                                                    encoding="utf-8")
    code, out, err = ship_left(walks, destination)
    check("a staging directory left behind on a run that also refuses an add-only file "
          "is FAILED, exit 1, and lists the refused file after it",
          first[0] == 0 and code == 1 and out.startswith(f"FAILED: {LEFT_WALK} — This run's")
          and one_line(out) and names_the_directory_and_its_deletion(out, store)
          and out.index("staging directory") < out.index(f"Refused, add-only: {LEFT_WALK}-draft.md")
          and out.rstrip().endswith(f"minutes at {store}/{LEFT_WALK}-minutes.md"),
          f"exit {code}: {out}{err}")

    # A copy that fails, then a removal that fails.
    walks, store, destination = left_walk_and_store("copy-failed")

    def copy_that_fails(copy_host, sources, walk_path):
        return subprocess.CompletedProcess([], 23, "", "injected: rsync exit 23\n")

    left.rsync_files = copy_that_fails
    try:
        code, out, err = ship_left(walks, destination)
    finally:
        left.rsync_files = real_left_rsync
    check("a copy that fails and a staging directory that cannot be removed is FAILED, "
          "exit 1, naming the directory and the command that deletes it, then the "
          "command that reruns the shipment",
          code == 1 and deletion_then_rerun(out, walks, store, "rsync exit 23 during the copy"),
          f"exit {code}: {out}{err}")

    # Renames that fail, then a removal that fails.
    walks, store, destination = left_walk_and_store("renames-failed")

    def renames_that_fail_left(copy_host, staging_dir, walk_path, files):
        return subprocess.CompletedProcess([], 255, "Disk quota exceeded (injected)", "injected: ssh exit 255\n"), None

    left.shipper.replace_with_staged_files = renames_that_fail_left
    try:
        code, out, err = ship_left(walks, destination)
    finally:
        left.shipper.replace_with_staged_files = real_left_renames
    check("renames that fail and a staging directory that cannot be removed is FAILED, "
          "exit 1, naming the directory and the command that deletes it",
          code == 1 and deletion_then_rerun(
              out, walks, store,
              "Disk quota exceeded (injected) while putting the copied files in place"),
          f"exit {code}: {out}{err}")

    # An add-only placement that fails, then a removal that fails.
    walks, store, destination = left_walk_and_store("placement-failed")
    real_left_placement = left.shipper.link_staged_files_never_over_existing

    def placement_that_fails_left(copy_host, staging_dir, walk_path, names):
        return subprocess.CompletedProcess([], 255, "Disk quota exceeded (injected)", "injected: ssh exit 255\n"), None

    left.shipper.link_staged_files_never_over_existing = placement_that_fails_left
    try:
        code, out, err = ship_left(walks, destination)
    finally:
        left.shipper.link_staged_files_never_over_existing = real_left_placement
    check("an add-only placement that fails and a staging directory that cannot be "
          "removed is FAILED, exit 1, naming the directory and the command that deletes it",
          code == 1 and deletion_then_rerun(
              out, walks, store,
              "Disk quota exceeded (injected) while putting the copied files in place"),
          f"exit {code}: {out}{err}")

    # Another shipment's staging directory, then a removal that fails.
    walks, store, destination = left_walk_and_store("other-staging")
    other_staging = store / f"{staging_marker}0123456789ab"
    other_staging.mkdir()
    code, out, err = ship_left(walks, destination)
    check("another staging directory and this run's own that cannot be removed is "
          "FAILED, exit 1, naming both and the command that deletes this run's",
          code == 1 and out.startswith(f"FAILED: {LEFT_WALK} — another shipment")
          and str(other_staging) in out and one_line(out)
          and out.count(staging_marker) == 3
          and names_the_directory_and_its_deletion(out, store), f"exit {code}: {out}{err}")

    remote_sentences = left.staging_directory_left_behind_failed_line_sentences_with_path_reason_and_rm_command(
        "nedlern@ned-box",
        pathlib.PurePosixPath("/home/nedlern/nedschorus-logs/walk/.ship-staging-w-0123456789ab"),
        "ssh exit 255")
    check("from another machine the staging directory is named with its host, and the "
          "command that deletes it runs over ssh, quoted for the remote shell",
          "directory nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/.ship-staging-w-0123456789ab "
          in remote_sentences
          and "`ssh nedlern@ned-box 'rm -rf -- /home/nedlern/nedschorus-logs/walk/.ship-staging-w-0123456789ab'`"
          in remote_sentences, remote_sentences)

    def rerun_line_for(directory, walk="named-walk-2026-10-31"):
        return left.walk_files_ship_copy_or_place_step_failed_line_with_shipment_rerun_command_builder(
            None, walk, directory,
            pathlib.PurePosixPath("/store/walk/.ship-staging-x"),
            "rsync exit 23 during the copy", None)

    named_line = rerun_line_for(pathlib.Path(str(left.WALK_DIRECTORY)))
    check("a walk found under docs/walk/ by its name is rerun by its name",
          named_line == (f"FAILED: named-walk-2026-10-31 — rsync exit 23 during the copy. "
                         f"Rerun: `{left.REPO_ROOT}/scripts/walk-files-ship.py "
                         f"named-walk-2026-10-31`"), named_line)
    below_line = rerun_line_for(left.WALK_DIRECTORY / "older")
    check("a walk in a directory below docs/walk/ is rerun by the path to its minutes",
          below_line.endswith(f"walk-files-ship.py "
                              f"{left.WALK_DIRECTORY}/older/named-walk-2026-10-31-minutes.md`"),
          below_line)
    dash_line = rerun_line_for(pathlib.Path(str(left.WALK_DIRECTORY)), walk="-dash-walk")
    check("a walk under docs/walk/ whose name begins with a dash is rerun by the path to "
          "its minutes, which argparse cannot read as an option",
          dash_line.endswith(f"walk-files-ship.py {left.WALK_DIRECTORY}/-dash-walk-minutes.md`"),
          dash_line)

print()
if failures:
    print(f"{len(failures)} case(s) FAILED:")
    for case_name in failures:
        print(f"  - {case_name}")
    sys.exit(1)
print("all passed")
