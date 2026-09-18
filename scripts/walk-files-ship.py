#!/usr/bin/env python3
"""Ship one walk's files to the log-store's `walk/` kind on ned-box.

Usage:
  scripts/walk-files-ship.py <walk name>
  scripts/walk-files-ship.py docs/walk/<walk name>-minutes.md    (any one of its files)

WHY (user-ruled 2026-09-18, item 7 of the walk
cold-read-and-walk-file-names-and-dispositions; nedschorus#335). A walk-me-through
walk writes its files into docs/walk/, gitignored since PR #308, and until this
program every walk file in the store was put there by hand at the walk's close,
the interim rule the .gitignore comment stated. The minutes are the record of
the user's rulings and the mechanism by which an interrupted walk resumes, so a
directory nothing preserves is the wrong place for their only copy.

WHAT A WALK'S FILES ARE. Five, flat in docs/walk/ and flat in the store's
walk/, each named by the walk's name and a role suffix
(.claude/skills/walk-me-through/SKILL.md):

  <name>-draft.md          the walk as first written, before the fast read
  <name>-suggestions.md    the fast read's suggestions on the draft
  <name>.md                the walk text presented to the user
  <name>-minutes.md        the rulings and the recovery position, written as
                           the walk proceeds
  <name>-dispositions.md   a cold-read walk's fifth file, written at its close

The five paths are built from the name; nothing here globs docs/walk/<name>*,
because one walk's name can be a prefix of another's. A walk lacking its walk
text or its minutes is not shippable (exit 64). A missing draft or suggestions
file is noted on stderr and the rest ships. Dispositions ships when present.
Other files that begin with the walk's name are noted on stderr and not
shipped; they are either another walk's or a shape the ruling did not name.

THE RULES, from the ruling: "draft, suggestions and walk text add-only like
records; the minutes are the one file it replaces". They are PER FILE:

  ADD-ONLY: draft, suggestions, walk text, dispositions. A file not yet in the
    store is added; one already there with the same bytes is left alone; one
    already there with DIFFERENT bytes is refused BY NAME -- the one stdout line
    opens REFUSED:, names each such file with the store's sha256 and the local
    one, and the exit is 2 -- while the other files still ship. The record
    shipper refuses a whole record before copying anything. A walk differs
    because the ruling says to run this "again if the walk is reopened and
    closed", and a reopened walk that re-planned has a changed walk text; a
    whole-walk refusal would then never deliver the one thing the second run
    exists for, the minutes.
  REPLACED: the minutes, and only the minutes. The displaced copy's sha256 is
    announced on stderr, as scripts/seat-shared-file-ship.py announces a
    replacement, so a fresh session shipping an older local copy over a newer
    stored one leaves a trace, and the displaced bytes can be found by digest in
    the store's Timeshift snapshots. The copy passes --ignore-times, for the
    reason that program's rsync_one_file records: openrsync on this Mac
    silently skips a same-size, same-second revision otherwise.
  FAIL LOUDLY: an unreachable ned-box prints a line opening FAILED and exits 1
    with the files still on disk; ssh runs in batch mode with a connect
    timeout. Shipping is the only thing between a walk's rulings and their
    loss, so a failure to ship is never a clean result -- the rule
    report_stray_writes states in scripts/cold-read-cell-common.py.

Dispositions is under ADD-ONLY because the ruling names the minutes as "the
one file it replaces" and lists nothing else. Whether a reopened cold-read walk
may rewrite its dispositions is a question this program leaves to the user.

WHO CALLS IT. The agent running a walk, when the walk's closing sentence is
delivered, and again if the walk is reopened and closed. The one stdout line
ends with the minutes' citation in scp form, which is the link that closing
sentence wants.

WHAT THIS IS: the THIRD CALLER of scripts/cold-read-record-ship.py, imported by
importlib the way scripts/seat-shared-file-ship.py and
scripts/sanity-check-record-ship.py import it, so the store's location, the ssh
and rsync invocations and the store's README stay defined in one place (the
user, 2026-09-11: "I don't want 3 varients of the same thing"). The copy host
and the citation host are kept apart as the seats shipper keeps them: on
ned-box the copy is local and the citation still names the host.

OUTPUT. Exactly one line on stdout -- `shipped:`, `REFUSED:` or `FAILED:` --
ending, when anything reached the store, with the minutes' citation. Everything
else is on stderr. Exit 0 when every file shipped or was already there, 2 when
any add-only file was refused, 1 when the store could not be reached or written,
64 for a bad invocation.

THE DESTINATION is the record shipper's one constant with the kind swapped to
`walk/`. Its environment override, COLD_READ_RECORD_SHIP_DESTINATION, moves this
kind with it, which is how the tests point at a scratch directory.
"""

import argparse
import hashlib
import importlib.util
import os
import pathlib
import shlex
import subprocess
import sys
import typing

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PROGRAM = "walk-files-ship"
WALK_DIRECTORY = REPO_ROOT / "docs" / "walk"
WALK_KIND_DIRECTORY = "walk"

# The record shipper is imported rather than copied, so the shippers cannot
# drift on what the store is, how ssh and rsync are invoked, or how an
# scp-form destination is split. The convention -- importlib for a module
# whose filename has hyphens -- is scripts/seat-shared-file-ship.py's.
_shipper_spec = importlib.util.spec_from_file_location(
    "cold_read_record_ship", REPO_ROOT / "scripts" / "cold-read-record-ship.py")
shipper = importlib.util.module_from_spec(_shipper_spec)
_shipper_spec.loader.exec_module(shipper)

EXIT_SHIPPED = shipper.EXIT_SHIPPED
EXIT_FAILED = shipper.EXIT_FAILED
EXIT_REFUSED = shipper.EXIT_REFUSED
EXIT_BAD_INVOCATION = shipper.EXIT_BAD_INVOCATION

# (role suffix, role name) in the order the skill names them; "" is the walk
# text. The suffixes are also what walk_name_and_directory strips from a path.
WALK_FILE_ROLES = (
    ("-draft", "draft"),
    ("-suggestions", "suggestions"),
    ("", "walk text"),
    ("-minutes", "minutes"),
    ("-dispositions", "dispositions"),
)
REQUIRED_ROLE_SUFFIXES = ("", "-minutes")
NOTED_WHEN_ABSENT_ROLE_SUFFIXES = ("-draft", "-suggestions")
REPLACED_ROLE_SUFFIX = "-minutes"


class WalkStoreDestination(typing.NamedTuple):
    """Where this run copies to, what host its citation names, and the path.
    Two hosts for the reason scripts/seat-shared-file-ship.py gives: on
    ned-box the copy is local (None) and the citation still names ned-box."""

    copy_host: typing.Optional[str]
    citation_host: typing.Optional[str]
    walk_path: pathlib.PurePosixPath


def walk_destination_for_this_machine() -> WalkStoreDestination:
    """The record shipper's destination with the kind swapped to `walk`.
    Under the environment override both hosts come from the override, where a
    bare local path legitimately has none; otherwise the citation host is the
    constant's whatever machine this is, and the copy host is None on ned-box."""
    copy_host, records_path = shipper.destination_for_this_machine()
    if os.environ.get(shipper.DESTINATION_ENVIRONMENT_VARIABLE):
        citation_host = copy_host
    else:
        citation_host, _ = shipper.split_destination(
            shipper.LOG_STORE_RECORDS_DESTINATION)
    return WalkStoreDestination(copy_host, citation_host,
                                records_path.parent / WALK_KIND_DIRECTORY)


def walk_name_and_directory(argument: str):
    """(walk name, directory) from a walk name, resolved under docs/walk/, or
    from a path to any one of the walk's files, whose role suffix is stripped.
    The path form is what the tests use, docs/walk/ being gitignored."""
    if "/" in argument or argument.endswith(".md"):
        path = pathlib.Path(argument)
        if not path.is_absolute():
            path = REPO_ROOT / path
        stem = path.name[:-3] if path.name.endswith(".md") else path.name
        for suffix, _ in WALK_FILE_ROLES:
            if suffix and stem.endswith(suffix):
                stem = stem[:-len(suffix)]
                break
        return stem, path.parent.resolve()
    return argument, WALK_DIRECTORY


def walk_file_name(name: str, suffix: str) -> str:
    return f"{name}{suffix}.md"


def sha256_of(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def store_digests(copy_host, targets: list):
    """({target path: sha256} for the targets that exist in the store, process).
    One round trip remotely: sha256sum of each target that is a file. An
    unreachable host is the process's non-zero return with a dict of None."""
    if copy_host is None:
        digests = {}
        for target in targets:
            path = pathlib.Path(target)
            if path.is_file():
                digests[str(target)] = sha256_of(path)
        return subprocess.CompletedProcess([], 0, "", ""), digests
    quoted = " ".join(shlex.quote(str(target)) for target in targets)
    script = (f"for f in {quoted}; do if [ -f \"$f\" ]; then sha256sum -- \"$f\"; fi; done")
    completed = subprocess.run(shipper.SSH_COMMAND + [copy_host, script],
                               capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return completed, None
    digests = {}
    for line in completed.stdout.splitlines():
        digest, _, target = line.partition("  ")
        if digest and target:
            digests[target] = digest
    return completed, digests


def rsync_files(copy_host, sources: list, walk_path: pathlib.PurePosixPath):
    """The files to add or replace, in one rsync, flat into the store's walk/.
    -a, --ignore-times (see REPLACED above), never --delete or --inplace: rsync
    writes each file whole or not at all."""
    destination = f"{copy_host}:{walk_path}/" if copy_host else f"{walk_path}/"
    command = ["rsync", "-a", "--ignore-times", "--timeout",
               shipper.RSYNC_IO_TIMEOUT_SECONDS]
    if copy_host:
        command += ["-e", " ".join(shipper.SSH_COMMAND)]
    return subprocess.run(command + [str(source) for source in sources] + [destination],
                          capture_output=True, text=True, check=False)


def ship_walk(destination: WalkStoreDestination, name: str,
              directory: pathlib.Path) -> int:
    """One walk, one stdout line, one exit code."""
    present = {suffix: directory / walk_file_name(name, suffix)
               for suffix, _ in WALK_FILE_ROLES
               if (directory / walk_file_name(name, suffix)).is_file()}
    missing_required = [walk_file_name(name, suffix)
                        for suffix in REQUIRED_ROLE_SUFFIXES if suffix not in present]
    if missing_required:
        print(f"FAILED: {name} — not a walk that can be shipped: "
              f"{', '.join(missing_required)} not found in {directory}")
        return EXIT_BAD_INVOCATION
    for suffix in NOTED_WHEN_ABSENT_ROLE_SUFFIXES:
        if suffix not in present:
            print(f"{PROGRAM}: no {walk_file_name(name, suffix)} in {directory}; "
                  f"shipping the walk without it", file=sys.stderr)
    role_names = {walk_file_name(name, suffix) for suffix, _ in WALK_FILE_ROLES}
    others = sorted(p.name for p in directory.glob(f"{name}-*.md")
                    if p.name not in role_names)
    if others:
        print(f"{PROGRAM}: not shipped, not one of the walk's five roles (another "
              f"walk's, or a shape the ruling did not name): {', '.join(others)}",
              file=sys.stderr)

    minutes_target = destination.walk_path / walk_file_name(name, REPLACED_ROLE_SUFFIX)
    citation = (f"{destination.citation_host}:{minutes_target}"
                if destination.citation_host else str(minutes_target))

    ensured = shipper.ensure_store(destination.copy_host, destination.walk_path)
    if ensured.returncode != 0:
        print(f"FAILED: {name} — could not reach the log-store to prepare it "
              f"({destination.copy_host or destination.walk_path}, exit "
              f"{ensured.returncode}); the walk's files stay on disk, unshipped.")
        sys.stderr.write(ensured.stderr)
        return EXIT_FAILED

    targets = {suffix: destination.walk_path / walk_file_name(name, suffix)
               for suffix in present}
    listed, stored = store_digests(destination.copy_host, list(targets.values()))
    if stored is None:
        reason = ("ned-box unreachable"
                  if listed.returncode == shipper.RSYNC_EXIT_CONNECTION_FAILED
                  else f"ssh exit {listed.returncode}")
        print(f"FAILED: {name} — {reason}; the walk's files stay on disk, unshipped.")
        sys.stderr.write(listed.stderr)
        return EXIT_FAILED

    to_copy, added, unchanged, refused = [], [], [], []
    replaced_digest = None
    local_minutes_digest = None
    for suffix, source in present.items():
        local_digest = sha256_of(source)
        in_store = stored.get(str(targets[suffix]))
        if in_store is None:
            to_copy.append(source)
            added.append(source.name)
        elif in_store == local_digest:
            unchanged.append(source.name)
        elif suffix == REPLACED_ROLE_SUFFIX:
            to_copy.append(source)
            replaced_digest, local_minutes_digest = in_store, local_digest
        else:
            refused.append(f"{source.name} (store sha256 {in_store}, local sha256 {local_digest})")

    if to_copy:
        copied = rsync_files(destination.copy_host, to_copy, destination.walk_path)
        if copied.returncode != 0:
            reason = ("ned-box unreachable"
                      if copied.returncode == shipper.RSYNC_EXIT_CONNECTION_FAILED
                      else f"rsync exit {copied.returncode}")
            print(f"FAILED: {name} — {reason} during the copy; a later run finishes it.")
            sys.stderr.write(copied.stderr)
            return EXIT_FAILED
    if replaced_digest is not None:
        # Never on stdout: that line is the summary and the citation. See
        # REPLACED in the module docstring for what this line is for.
        print(f"{PROGRAM}: REPLACED {walk_file_name(name, REPLACED_ROLE_SUFFIX)} in the "
              f"store — the content it held was sha256 {replaced_digest}, and what is "
              f"there now is sha256 {local_minutes_digest}. The minutes are the one "
              f"file a walk replaces (user-ruled 2026-09-18). If the displaced bytes "
              f"were wanted — a fresh session can hold an older copy than the store's "
              f"— the store is snapshotted every ten minutes by Timeshift, and the "
              f"digest above says which file to look for.", file=sys.stderr)

    parts = []
    if added:
        parts.append(f"{len(added)} file(s) added ({', '.join(added)})")
    if replaced_digest is not None:
        parts.append("minutes replaced")
    if unchanged:
        parts.append(f"{len(unchanged)} already there unchanged")
    summary = "; ".join(parts) if parts else "nothing to copy"
    if refused:
        print(f"REFUSED: {name} — already in the store with different content and "
              f"not replaced, add-only: {'; '.join(refused)}. The rest: {summary}; "
              f"minutes at {citation}")
        return EXIT_REFUSED
    print(f"shipped: {name} — {summary}; minutes at {citation}")
    return EXIT_SHIPPED


def main() -> int:
    parser = argparse.ArgumentParser(
        prog=PROGRAM, description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("walk", help="the walk's name (its files are under docs/walk/), "
                                     "or a path to any one of its files")
    arguments = parser.parse_args()
    name, directory = walk_name_and_directory(arguments.walk)
    if not name or "/" in name:
        print(f"FAILED: {arguments.walk!r} does not name a walk")
        return EXIT_BAD_INVOCATION
    try:
        return ship_walk(walk_destination_for_this_machine(), name, directory)
    except OSError as error:
        # ssh or rsync itself could not be run. Loud, as the rules say: a
        # traceback exits 1 too, but prints no line a caller can read.
        print(f"FAILED: {name} — could not run the copy ({error}); the walk's "
              f"files stay on disk, unshipped.")
        return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
