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
                           and updated after it as the findings' status moves

The five paths are built from the name; nothing here globs docs/walk/<name>*,
because one walk's name can be a prefix of another's. A walk lacking its walk
text or its minutes is not shippable (exit 64). A missing draft or suggestions
file is noted on stderr and the rest ships. Dispositions ships when present.
Other files that begin with the walk's name are noted on stderr and not
shipped; they are either another walk's or a shape the ruling did not name.

THE RULES. The first ruling (item 7 above) said "draft, suggestions and walk
text add-only like records; the minutes are the one file it replaces", and
this program shipped dispositions add-only because that ruling listed nothing
else. The user then ruled (2026-09-18, walk
skill-sentences-and-shipper-questions-2026-09-18, item 5) that the
dispositions file is replaced exactly like the minutes, because a cold-read
walk's dispositions "is not just a historical log to be preserved, it is a
sometimes updated status file". The rules are PER FILE:

  ADD-ONLY: draft, suggestions, walk text. A file not yet in the
    store is added; one already there with the same bytes is left alone; one
    already there with DIFFERENT bytes is refused BY NAME -- the one stdout line
    opens REFUSED:, names each such file with the store's sha256 and the local
    one, and the exit is 2 -- while the other files still ship. The record
    shipper refuses a whole record before copying anything. A walk differs
    because the ruling says to run this "again if the walk is reopened and
    closed", and a reopened walk that re-planned has a changed walk text; a
    whole-walk refusal would then never deliver the one thing the second run
    exists for, the minutes. The walk text has one exception, APPENDED TO
    below; draft and suggestions have none.
  APPENDED TO: the walk text, and it alone. A stored walk text whose bytes
    are an exact PREFIX of the local one -- the local file only had content
    added after it -- is replaced instead of refused (user-ruled 2026-09-21,
    item 3 of the walk md-skills-seat-questions-and-concerns-2026-09-21). A
    walk text grows as its items are presented, so shipping mid-walk and
    again at the close is ordinary, and the close refused a file nothing had
    rewritten: the store's copy of the walk
    md-skills-seat-open-decisions-2026-09-20 held 134 lines of the local
    copy's 341, not one of the 134 changed, and the store held four of that
    walk's fifteen items until it was re-shipped under this rule.
    THE TEST IS THE BYTES, never lines and never a diff: the stored size says
    how many leading bytes of the local file to hash, and they must hash to
    the sha256 the store reported for the whole stored file. Identical bytes
    are not an append -- they are the already-there case above, and a run
    that finds them copies nothing. A shorter local file is content removed
    and a same-length difference is content changed; both fail this test and
    are refused with the text above. So is a longer file with a byte changed
    before its added part, which is the whole difference between this test
    and "the local file is longer": the refusal exists to catch a session
    overwriting the store with a stale copy, and a stale copy that also grew
    is exactly that. A store listing that reports a digest and no size cannot
    be tested and is refused, as before.
  REPLACED: the minutes and the dispositions, each on its own. A stored copy
    with different bytes is overwritten, and each displaced copy's sha256 is
    announced on its own stderr line, as scripts/seat-shared-file-ship.py
    announces a replacement, so a fresh session shipping an older local copy
    over a newer stored one leaves a trace, and the displaced bytes can be
    found by digest in the store's Timeshift snapshots while one taken before
    the replacement is still kept; the line states no cadence, for the reason
    scripts/seat-shared-file-ship.py's docstring records under THE SNAPSHOT
    CADENCE IS NOT A PROMISE. An appended-to walk
    text is announced on the same line in the same form, its own ruling
    named. The copy passes
    --ignore-times, for the reason that program's rsync_one_file records:
    openrsync on this Mac silently skips a same-size, same-second revision
    otherwise.
  FAIL LOUDLY: an unreachable ned-box prints a line opening FAILED and exits 1
    with the files still on disk; ssh runs in batch mode with a connect
    timeout. Shipping is the only thing between a walk's rulings and their
    loss, so a failure to ship is never a clean result -- the rule
    report_stray_writes states in nc-systems/cold-read/cold-read-cell-common.py.

The minutes' citation at the end of the stdout line is the minutes' still,
never the dispositions': the minutes are the record of the rulings and what a
resumed walk reads.

WHO CALLS IT. The agent running a walk, when the walk's closing sentence is
delivered, and again if the walk is reopened and closed. The one stdout line
ends with the minutes' citation in scp form, which is the link that closing
sentence wants.

WHAT THIS IS: the THIRD CALLER of nc-systems/cold-read/cold-read-record-ship.py, imported by
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
    "cold_read_record_ship", REPO_ROOT / "nc-systems" / "cold-read" / "cold-read-record-ship.py")
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
MINUTES_ROLE_SUFFIX = "-minutes"
WALK_TEXT_ROLE_SUFFIX = ""
REQUIRED_ROLE_SUFFIXES = (WALK_TEXT_ROLE_SUFFIX, MINUTES_ROLE_SUFFIX)
NOTED_WHEN_ABSENT_ROLE_SUFFIXES = ("-draft", "-suggestions")
# The files a walk replaces in the store (see REPLACED in the docstring); every
# other role is add-only. The minutes since the first ruling; the dispositions
# since the second (user-ruled 2026-09-18, walk
# skill-sentences-and-shipper-questions-2026-09-18, item 5).
REPLACED_ROLE_SUFFIXES = (MINUTES_ROLE_SUFFIX, "-dispositions")
# The one add-only role a run replaces when the local file only grew (see
# APPENDED TO in the docstring; user-ruled 2026-09-21, item 3 of the walk
# md-skills-seat-questions-and-concerns-2026-09-21). Every other add-only role
# is refused on any difference.
ROLE_SUFFIX_REPLACED_WHEN_ONLY_APPENDED_TO = WALK_TEXT_ROLE_SUFFIX
# What the store's listing prefixes a file's size in bytes with, so one
# round trip carries both facts the rules need and the sha256sum lines keep
# the format sha256sum itself prints.
STORE_LISTING_SIZE_LINE_PREFIX = "size "


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
    from a path to any one of the walk's files. The path form is what the tests
    use, docs/walk/ being gitignored.

    In the path form the walk's name is found by PRESENCE, not by stripping a
    role suffix alone, because a walk's own name may end in a role suffix: the
    reviewer's case, docs/walk/cold-read-and-walk-file-names-and-dispositions.md,
    which stripping alone resolved to a shorter walk that does not exist. The
    candidates are the full stem and, for each role suffix the stem ends with,
    the stem without it; the longest candidate whose required files (the walk
    text and the minutes) are both in the directory is the walk. When none
    qualifies, the stripped form is returned as before, so the FAILED line still
    names a sensible walk."""
    if "/" in argument or argument.endswith(".md"):
        path = pathlib.Path(argument)
        if not path.is_absolute():
            path = REPO_ROOT / path
        directory = path.parent.resolve()
        stem = path.name[:-3] if path.name.endswith(".md") else path.name
        candidates = [stem]
        for suffix, _ in WALK_FILE_ROLES:
            if suffix and stem.endswith(suffix):
                candidates.append(stem[:-len(suffix)])
        for candidate in candidates:
            if all((directory / walk_file_name(candidate, suffix)).is_file()
                   for suffix in REQUIRED_ROLE_SUFFIXES):
                return candidate, directory
        return candidates[-1], directory
    return argument, WALK_DIRECTORY


def walk_file_name(name: str, suffix: str) -> str:
    return f"{name}{suffix}.md"


def sha256_of(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class StoredWalkFile(typing.NamedTuple):
    """What the store reports about one file it holds. The size is what the
    APPENDED TO rule needs -- how many leading bytes of the local file to
    hash -- and is None when the listing gave a digest and no size, in which
    case that rule cannot be applied and the difference is refused."""

    sha256: str
    size_in_bytes: typing.Optional[int]


def store_digests_and_sizes(copy_host, targets: list):
    """({target path: StoredWalkFile} for the targets that exist in the store,
    process). One round trip remotely: for each target that is a file, the
    sha256sum line sha256sum itself prints, and a size line of this program's
    own. An unreachable host is the process's non-zero return with a dict of
    None."""
    if copy_host is None:
        stored = {}
        for target in targets:
            path = pathlib.Path(target)
            if path.is_file():
                stored[str(target)] = StoredWalkFile(sha256_of(path),
                                                     path.stat().st_size)
        return subprocess.CompletedProcess([], 0, "", ""), stored
    quoted = " ".join(shlex.quote(str(target)) for target in targets)
    # sha256sum prints its own line; printf prints the size line beside it, in
    # one round trip. The format is quoted for the remote shell, its trailing
    # backslash-n included, and `wc -c` reads the file rather than being given
    # its name, so no padded count and no name reach the line.
    size_line_format = STORE_LISTING_SIZE_LINE_PREFIX + "%s  %s" + "\\n"
    script = (f'for f in {quoted}; do if [ -f "$f" ]; then sha256sum -- "$f"; '
              f'printf {shlex.quote(size_line_format)} "$(wc -c < "$f")" "$f"; '
              f'fi; done')
    completed = subprocess.run(shipper.SSH_COMMAND + [copy_host, script],
                               capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return completed, None
    digests, sizes = {}, {}
    for line in completed.stdout.splitlines():
        if line.startswith(STORE_LISTING_SIZE_LINE_PREFIX):
            # Read before the digest form below, which would otherwise take
            # "size 134" for a digest. BSD `wc` pads its count where GNU `wc`
            # on ned-box does not, so the count is stripped before it is read.
            reported = line[len(STORE_LISTING_SIZE_LINE_PREFIX):].lstrip()
            count, _, target = reported.partition("  ")
            if count.isdigit() and target:
                sizes[target] = int(count)
            continue
        digest, _, target = line.partition("  ")
        if digest and target:
            digests[target] = digest
    return completed, {target: StoredWalkFile(digest, sizes.get(target))
                       for target, digest in digests.items()}


def stored_copy_is_an_exact_prefix(source: pathlib.Path,
                                   in_store: StoredWalkFile) -> bool:
    """True when the store's bytes are an exact leading slice of the local
    file's: the local file only had content added after them (the APPENDED TO
    rule). Never a line comparison and never a diff -- the stored size says
    how many leading bytes to hash, and the store's own sha256 is what they
    must equal.

    Identical files are not an append and never reach here: the caller has
    already routed them to the already-there path, and the strict < excludes
    them anyway. A shorter local file (content removed), a same-length
    difference (content changed) and a longer file with a byte changed before
    its added part all answer False, so all three stay refused."""
    if in_store.size_in_bytes is None or in_store.size_in_bytes >= source.stat().st_size:
        return False
    with source.open("rb") as opened:
        leading = opened.read(in_store.size_in_bytes)
    return (len(leading) == in_store.size_in_bytes
            and hashlib.sha256(leading).hexdigest() == in_store.sha256)


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


class WalkFileReplacement(typing.NamedTuple):
    """One file this run replaces in the store, and the rule that allowed it.
    `ruling` is the sentence the stderr announcement carries between the two
    digests, so a reader of the store sees which ruling let the store's copy
    go."""

    file_name: str
    role_name: str
    displaced_sha256: str
    local_sha256: str
    ruling: str


REPLACED_ROLE_RULING = (
    "The minutes and the dispositions are the two files a walk replaces "
    "(user-ruled 2026-09-18, walk skill-sentences-and-shipper-questions-2026-09-18 "
    "item 5).")
APPENDED_TO_RULING = (
    "The stored copy was an exact byte prefix of this one — its {stored_bytes} "
    "bytes are the first {stored_bytes} of these {local_bytes}, so the walk text "
    "was only added to and nothing already in the store was rewritten, which is "
    "the one difference an add-only walk text is replaced on (user-ruled "
    "2026-09-21, item 3 of the walk "
    "md-skills-seat-questions-and-concerns-2026-09-21).")


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

    minutes_target = destination.walk_path / walk_file_name(name, MINUTES_ROLE_SUFFIX)
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
    listed, stored = store_digests_and_sizes(destination.copy_host,
                                             list(targets.values()))
    if stored is None:
        reason = ("ned-box unreachable"
                  if listed.returncode == shipper.RSYNC_EXIT_CONNECTION_FAILED
                  else f"ssh exit {listed.returncode}")
        print(f"FAILED: {name} — {reason}; the walk's files stay on disk, unshipped.")
        sys.stderr.write(listed.stderr)
        return EXIT_FAILED

    to_copy, added, unchanged, refused = [], [], [], []
    # One WalkFileReplacement per replaced file, in the roles' order, which
    # puts the walk text before the minutes and the minutes before the
    # dispositions.
    replaced = []
    role_name_of = dict(WALK_FILE_ROLES)
    for suffix, source in present.items():
        local_digest = sha256_of(source)
        in_store = stored.get(str(targets[suffix]))
        if in_store is None:
            to_copy.append(source)
            added.append(source.name)
        elif in_store.sha256 == local_digest:
            unchanged.append(source.name)
        elif suffix in REPLACED_ROLE_SUFFIXES:
            to_copy.append(source)
            replaced.append(WalkFileReplacement(
                source.name, role_name_of[suffix], in_store.sha256, local_digest,
                REPLACED_ROLE_RULING))
        elif (suffix == ROLE_SUFFIX_REPLACED_WHEN_ONLY_APPENDED_TO
              and stored_copy_is_an_exact_prefix(source, in_store)):
            to_copy.append(source)
            replaced.append(WalkFileReplacement(
                source.name, role_name_of[suffix], in_store.sha256, local_digest,
                APPENDED_TO_RULING.format(stored_bytes=in_store.size_in_bytes,
                                          local_bytes=source.stat().st_size)))
        else:
            refused.append(f"{source.name} (store sha256 {in_store.sha256}, "
                           f"local sha256 {local_digest})")

    if to_copy:
        copied = rsync_files(destination.copy_host, to_copy, destination.walk_path)
        if copied.returncode != 0:
            reason = ("ned-box unreachable"
                      if copied.returncode == shipper.RSYNC_EXIT_CONNECTION_FAILED
                      else f"rsync exit {copied.returncode}")
            print(f"FAILED: {name} — {reason} during the copy; a later run finishes it.")
            sys.stderr.write(copied.stderr)
            return EXIT_FAILED
    # The walk kind's directory in the store on ned-box, which the snapshots
    # copy, built from the record shipper's constant, never written out again
    # here; the destination may be a local override, the snapshots never.
    stored_walk_directory = (shipper.split_destination(
        shipper.LOG_STORE_RECORDS_DESTINATION)[1].parent / WALK_KIND_DIRECTORY)
    for replacement in replaced:
        # One line per replaced file, never on stdout: that line is the summary
        # and the citation. See REPLACED and APPENDED TO in the module
        # docstring for what this line is for; the sentence in the middle is
        # the rule that allowed this particular replacement.
        print(f"{PROGRAM}: REPLACED {replacement.file_name} in the store — the content "
              f"it held was sha256 {replacement.displaced_sha256}, and what is there "
              f"now is sha256 {replacement.local_sha256}. {replacement.ruling} If "
              f"the displaced {replacement.role_name} were wanted, look for the file "
              f"whose sha256 is the first digest on this line in ned-box's Timeshift "
              f"snapshots: on ned-box, run `sha256sum "
              f"/mnt/backup/timeshift/snapshots/*/localhost"
              f"{shlex.quote(str(stored_walk_directory / replacement.file_name))}` "
              f"and take a snapshot "
              f"whose line shows that digest.", file=sys.stderr)

    parts = []
    if added:
        parts.append(f"{len(added)} file(s) added ({', '.join(added)})")
    for replacement in replaced:
        parts.append(f"{replacement.role_name} replaced")
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
