#!/usr/bin/env python3
"""Ship one walk's files to the log-store's `walk/` kind on ned-box.

Usage:
  scripts/walk-files-ship.py <walk name>
  scripts/walk-files-ship.py docs/walk/<walk name>-minutes.md    (any one of its files)

WHY. A walk-me-through walk writes its files into docs/walk/, which is
gitignored, so neither Git nor anything else preserves them there. The
minutes are the record of the user-rulings and the mechanism by which an
interrupted walk resumes, so a directory nothing preserves is the wrong place
for their only copy.

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

The five paths are built from the name, never found by a glob of
docs/walk/<name>*, because one walk's name can be a prefix of another's; a
glob of <name>-*.md is used only for the stderr note below. A walk lacking its walk
text or its minutes is not shippable (exit 64). A missing draft or suggestions
file is noted on stderr and the rest ships. Dispositions ships when present,
and its absence is not noted.
Every other file in the walk's directory whose name is the walk's name, a
hyphen, anything, then .md -- what the glob <name>-*.md matches -- is noted on
stderr and not shipped; it is either another walk's or a file none of the five
roles covers.

In the store, and only there, the walk text can also have revised copies,
<name>-revised-<n>.md, which REVISED COPIES below describes.

THE RULES. The minutes and the dispositions are replaced in the store; the
draft, the suggestions and the walk text are add-only, as a
cold-read-record's files are, and a walk text the store would refuse ships
as a revised copy instead. The dispositions are replaced because a
cold-read walk's dispositions file is a status file updated after the walk
closes, not only a record kept as first written. The rules are PER FILE:

  ADD-ONLY: draft, suggestions, walk text. A file not yet in the
    store is added; one already there with the same bytes is left alone; one
    already there with DIFFERENT bytes is refused BY NAME -- the one stdout line
    opens REFUSED:, names each such file with the store's sha256 and the local
    one, and the exit is 2 -- while the other files still ship. The record
    shipper, nc-systems/cold-read/cold-read-record-ship.py (see WHAT THIS
    IS), refuses a whole record before copying anything. A walk differs
    because the walk-me-through skill runs this program again whenever a
    walk is reopened and closed, and a reopened walk that re-planned has a
    changed walk text; a whole-walk refusal would then never deliver the one
    thing the second shipment exists for, the minutes. The walk text has two
    exceptions, APPENDED TO and REVISED COPIES below, so it is never refused
    except when another shipment changes the store while this one runs;
    draft and suggestions have none.
  APPENDED TO: the walk text, and it alone. A stored walk text whose bytes
    are an exact PREFIX of the local one -- the local file only had content
    added after the stored bytes -- is replaced instead of refused. A walk text grows as
    its items are presented, so a shipment before the close, which WHO CALLS
    IT allows, followed by the close's own is ordinary; refusing the grown
    file would leave the store holding only the items presented before the
    first shipment.
    THE TEST IS THE BYTES, never lines and never a diff: the stored size says
    how many leading bytes of the local file to hash, and they must hash to
    the sha256 the store reported for the whole stored file. Identical bytes
    are not an append -- they are the already-there case above, and a run
    that finds them copies nothing. A shorter local file is content removed
    and a same-length difference is content changed; both fail this test and
    ship as a revised copy, under REVISED COPIES below. So does a longer file
    with a byte changed before its added part, which is the whole difference
    between this test and "the local file is longer": a session must never
    overwrite the store's copy with a stale one, and a stale copy that also
    grew is exactly that. A store listing that reports a digest and no size
    cannot be tested, and the walk text ships as a revised copy.
  REVISED COPIES: the walk text, when the store's latest copy is neither
    the same bytes as the local one nor an exact prefix of it, as when the
    agent rewrites an item the user did not follow. The local walk text is
    added beside the store's copies as <name>-revised-<n>.md, n one more than
    the highest the store holds, starting at 1, and a stderr line names the
    copy it differs from and the copy it ships as. The store's latest copy
    is the highest-numbered revised copy, or the walk text itself while there
    is none, and the same bytes and APPENDED TO tests above are made against
    it, never against an older copy: so a walk text whose bytes match an
    older copy, as after an edit is undone, ships as a new revised copy, and
    the highest-numbered copy is always the walk text as last shipped. A
    revised copy is add-only like the walk text, placed by hard link; only
    the latest one is ever replaced, under APPENDED TO. A file is a revised
    copy only when n is written in digits with no leading zero, so another
    walk whose name begins with this one's name and "-revised-" is not
    counted. The store's copies are listed by a shell glob on the store,
    before the digests are read; a listing that fails is FAILED, exit 1,
    with nothing copied.
  REPLACED: the minutes and the dispositions, each on its own. A minutes
    or dispositions file the store does not hold yet is added, and counted as added on the stdout
    line, with no stderr line. A stored copy
    with different bytes is overwritten, and each displaced copy's sha256 is
    announced on its own stderr line, as scripts/seat-shared-file-ship.py
    announces a replacement, so a fresh session shipping an older local copy
    over a newer stored one leaves a trace, and the displaced bytes can be
    found by digest in the store's Timeshift snapshots while one taken before
    the replacement is still kept; the line states no cadence, for the reason
    scripts/seat-shared-file-ship.py's docstring records under THE SNAPSHOT
    CADENCE IS NOT A PROMISE. A walk text replaced under APPENDED TO is
    announced the same way, on a stderr line of its own. Each such stderr
    line also names the walk in which the user decided the rule that allowed
    the replacement; that walk's walk-minutes are at
    nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/<the walk the stderr line names>-minutes.md.
    The copy passes
    --ignore-times, for the reason rsync_one_file in
    scripts/seat-shared-file-ship.py records:
    openrsync on this Mac silently skips a same-size, same-second revision
    otherwise.
  FAIL LOUDLY: an unreachable ned-box prints a line opening FAILED and exits 1
    with the files still on disk; ssh runs in batch mode with a connect
    timeout. Shipping is the only thing between a walk's rulings and their
    loss, so a failure to ship is never reported as a clean result.

TWO SHIPMENTS OF ONE WALK AT ONCE. The rules above are decided on the
store's listing, and the copy takes seconds over ssh; a second shipment of the
same walk landing a file in those seconds was overwritten without a word, and
both printed shipped: (GHI "Two shipments of one cold-read-record name at the
same moment can lose a report while both say it shipped",
https://github.com/nedschorus/nedschorus/issues/910, measured for the record
shipper). So the files are copied into a staging directory in walk/
(`.ship-staging-<name>-<random>`, removed once they are in place) and put in
place by the record shipper's two steps: an add-only file by hard link, which
is never made over an existing file (link_staged_files_never_over_existing),
and a replaced file by rename, the store's digest of what it displaces read
in the same step (replace_with_staged_files). A walk text the walk only added to is renamed
in only while the store still holds the copy it was tested against and no newer
revised copy has been added. The
outcome is judged on what the store holds afterwards: an add-only file
holding another shipment's bytes is REFUSED by name, a walk text changed in
the store meanwhile is REFUSED by name, a minutes or dispositions file another
shipment landed first is replaced and its digest announced as any
replacement is, a walk text whose latest copy another shipment followed with
a newer revised copy is REFUSED by name, and a file that does not hold this run's bytes afterwards --
another shipment's rename came after this one's, or the file is missing --
makes the line FAILED, exit 1. The replace step takes no lock: a walk's
files are shipped by the seat that runs the walk, one shipment after
another. A read-back cannot see a rename that runs after it, so instead the
replace step renames nothing while another staging directory for the same
walk exists, and the line is FAILED naming it (see NO LOCK; A CHECK INSTEAD
in the record shipper's replace_with_staged_files).

A LEFTOVER STAGING DIRECTORY. A shipment that is killed, or loses ned-box
partway, can leave its staging directory behind; nothing removes it later. A
shipment that cannot remove its own staging directory says so: its line is
FAILED, exit 1, naming the directory and the command that deletes it.
Only the replace step looks for another staging directory, and it runs
whenever the minutes or the dispositions differ from the store's copy or
are not in the store yet, or the walk text was only added to. So a leftover
one stops nearly every later shipment of that walk, with the FAILED line
above; a shipment whose minutes, dispositions and walk text the store
already holds unchanged does not look, and is not stopped. The stderr line
printed with that FAILED line says what to do: when no other shipment of the walk is
running, which `pgrep -lf walk-files-ship` on both machines shows, delete
the directory the FAILED line names and run this program again. The
directory is on ned-box: there delete it with
`rm -rf -- <the path the FAILED line names>`, and from the Mac with
`ssh nedlern@ned-box 'rm -rf -- <the path the FAILED line names>'`.

WHO CALLS IT. The agent running a walk, when the walk's closing sentence is
delivered, and again if the walk is reopened and closed. The agent may also
run this program before the close, such as before a handoff, so that the
store holds the walk so far; the close's run then ships the grown files. The
stdout line ends with the minutes' citation in scp form, which the closing
sentence turns into its link to the walk-minutes; OUTPUT says which FAILED
lines carry no citation.

WHAT THIS IS: the THIRD CALLER of nc-systems/cold-read/cold-read-record-ship.py, imported by
importlib the way scripts/seat-shared-file-ship.py and
scripts/sanity-check-record-ship.py import it, so the store's location, the ssh
and rsync invocations and the store's README stay defined in one place (the
user, 2026-09-11: "I don't want 3 varients of the same thing"). The copy host
and the citation host are kept apart as scripts/seat-shared-file-ship.py
keeps them: on
ned-box the copy is local and the citation still names the host.

OUTPUT. Exactly one line on stdout, opening `shipped:`, `REFUSED:` or
`FAILED:`. Everything else is on stderr. The line ends with the minutes'
citation whenever the shipment judged every file: `shipped:`, even when
nothing was copied because every file was already there with the same
bytes; `REFUSED:`; and the `FAILED:` line that names files not holding this
shipment's bytes, or this run's staging directory left behind after the files
were placed. A `FAILED:` line that stops the shipment before then says what stopped the shipment and carries no citation:
a bad invocation, a store that could not be reached, prepared or listed, a
copy or placing step that failed, another staging directory, or ssh or rsync
that could not be started. A FAILED line for a copy or placing step that
failed ends with the command that reruns the shipment. That line, and the one
for another staging directory, also names this run's own staging directory
when it could not be removed, with the command that deletes it, which loses
nothing and is to be run before the rerun. A
walk that cannot be shipped is a FAILED line naming the missing files.
The citation is always the minutes', never the dispositions': the minutes
are the record of the rulings and what a resumed walk reads.

Exit 0 when every file shipped or was already there; 2 when an add-only file
was refused, which for the walk text happens only when another shipment
changed the store while this one ran; 1 when the store could not be reached or written, a file does
not hold this shipment's bytes after the copy, another staging directory for
the walk stopped the replace step, or this run's staging directory could not
be removed; 64 for a bad invocation, which is a missing,
extra or unknown argument as well as a walk that cannot be shipped. When
both 1 and 2 apply, 1 wins and the line opens `FAILED:`. A `FAILED:` line
that carries the citation lists the refused files after what failed; an
earlier `FAILED:` line names no refused file.

THE DESTINATION is the record shipper's one constant with the kind swapped to
`walk/`. Its environment override, COLD_READ_RECORD_SHIP_DESTINATION, moves this
kind with it, which is how the tests point at a scratch directory.
"""

import argparse
import errno
import hashlib
import importlib.util
import os
import pathlib
import re
import secrets
import shlex
import subprocess
import sys
import tempfile
import typing

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PROGRAM = "walk-files-ship"
WALK_DIRECTORY = REPO_ROOT / "docs" / "walk"
WALK_KIND_DIRECTORY = "walk"

# The record shipper is imported rather than copied, so the shippers cannot
# drift on what the store is, how ssh and rsync are invoked, or how an
# scp-form destination is split. importlib, because the filename has hyphens.
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
# other role is add-only.
REPLACED_ROLE_SUFFIXES = (MINUTES_ROLE_SUFFIX, "-dispositions")
# The one add-only role a run replaces when the local file only grew (see
# APPENDED TO in the docstring). Every other add-only role is refused on any
# difference.
ROLE_SUFFIX_REPLACED_WHEN_ONLY_APPENDED_TO = WALK_TEXT_ROLE_SUFFIX
# A walk text the store holds that is not a byte prefix of the local one is
# shipped beside it as <name>-revised-<n>.md, n counting up from 1, and never
# refused (see REVISED COPIES in the docstring).
REVISED_WALK_TEXT_NAME_INFIX = "-revised-"
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
    role suffix alone, because a walk's own name may end in a role suffix:
    docs/walk/cold-read-and-walk-file-names-and-dispositions.md is a walk text,
    and stripping alone would resolve it to a shorter walk that does not exist. The
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


def revised_walk_text_file_name(name: str, number: int) -> str:
    return f"{name}{REVISED_WALK_TEXT_NAME_INFIX}{number}.md"


def revised_walk_text_number(name: str, file_name: str) -> typing.Optional[int]:
    """n when file_name is <name>-revised-<n>.md with n a positive whole
    number written without leading zeros, else None, so another walk whose
    name begins with this one's is never read as this walk's copy."""
    matched = re.fullmatch(re.escape(name + REVISED_WALK_TEXT_NAME_INFIX)
                           + r"([1-9][0-9]*)\.md", file_name)
    return int(matched.group(1)) if matched else None


def stored_revised_walk_text_numbers(copy_host, walk_path: pathlib.PurePosixPath,
                                     name: str):
    """(process, sorted numbers of the walk's revised copies the store holds),
    with None for the numbers when the store cannot be listed. A store
    directory that does not exist yet holds none."""
    if copy_host is None:

        def list_stored():
            directory = pathlib.Path(walk_path)
            if not directory.is_dir():
                return []
            # is_file() answers False for an entry it cannot stat, so a
            # directory that cannot be entered would read as holding no copy.
            if not os.access(directory, os.R_OK | os.X_OK):
                raise PermissionError(errno.EACCES, os.strerror(errno.EACCES), str(directory))
            return [path.name for path in directory.iterdir() if path.is_file()]

        listed, names = shipper.local_store_step_wrapper_returning_completed_process_and_value_or_os_error_as_failed_result(
            list_stored)
    else:
        # The glob's fixed part is quoted, its * is not; an unmatched glob is
        # left as written, which the -f test drops. `ls` is not used, so a
        # name is never mangled by its output format. A directory that cannot
        # be entered or read exits 1: the glob would otherwise match nothing
        # and read as "no revised copies".
        quoted_directory = shlex.quote(str(walk_path))
        pattern = shlex.quote(name + REVISED_WALK_TEXT_NAME_INFIX) + "*.md"
        script = (f"[ -d {quoted_directory} ] || exit 0; "
                  f"cd -- {quoted_directory} || exit 1; [ -r . ] || exit 1; "
                  f"for f in {pattern}; do if [ -f \"$f\" ]; then printf '%s\\n' \"$f\"; fi; done; exit 0")
        listed = subprocess.run(shipper.SSH_COMMAND + [copy_host, script],
                                capture_output=True, text=True, check=False)
        names = listed.stdout.splitlines() if listed.returncode == 0 else None
    if names is None:
        return listed, None
    numbers = sorted(number for number in (revised_walk_text_number(name, file_name)
                                           for file_name in names)
                     if number is not None)
    return listed, numbers


def store_file_role_rank(name: str, file_name: str) -> int:
    """The place of a store file of this walk in the roles' order, a revised
    copy taking the walk text's place, so the stdout line and the stderr
    announcements list files in one order."""
    for rank, (suffix, _) in enumerate(WALK_FILE_ROLES):
        if file_name == walk_file_name(name, suffix):
            return rank
    return [suffix for suffix, _ in WALK_FILE_ROLES].index(WALK_TEXT_ROLE_SUFFIX)


def sha256_of(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class StoredWalkFile(typing.NamedTuple):
    """What the store reports about one file it holds. The size is what the
    APPENDED TO rule needs -- how many leading bytes of the local file to
    hash -- and is None when the listing gave a digest and no size, in which
    case that rule cannot be applied and the walk text ships as a revised
    copy."""

    sha256: str
    size_in_bytes: typing.Optional[int]


def store_digests_and_sizes(copy_host, targets: list):
    """({target path: StoredWalkFile} for the targets that exist in the store,
    process). One round trip remotely: for each target that is a file, the
    sha256sum line sha256sum itself prints, and a size line of this program's
    own. An unreachable host is the process's non-zero return with a dict of
    None, and so is a local read that fails, and a stored file sha256sum
    cannot hash: the remote loop exits
    1 at it. Without that exit the loop would go on, its last `printf` would
    make the script exit 0, and the file would be missing from the listing,
    which the caller reads as not stored, so an add-only file in the store
    would be copied over."""
    if copy_host is None:

        def read_stored():
            stored = {}
            for target in targets:
                path = pathlib.Path(target)
                if path.is_file():
                    stored[str(target)] = StoredWalkFile(sha256_of(path),
                                                         path.stat().st_size)
            return stored

        return shipper.local_store_step_wrapper_returning_completed_process_and_value_or_os_error_as_failed_result(
            read_stored)
    quoted = " ".join(shlex.quote(str(target)) for target in targets)
    # sha256sum prints its own line; printf prints the size line beside it, in
    # one round trip. The format is quoted for the remote shell, its trailing
    # backslash-n included, and `wc -c` reads the file rather than being given
    # its name, so no padded count and no name reach the line.
    size_line_format = STORE_LISTING_SIZE_LINE_PREFIX + "%s  %s" + "\\n"
    script = (f'for f in {quoted}; do if [ -f "$f" ]; then sha256sum -- "$f" || exit 1; '
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
    its added part all answer False, so all three ship as a revised copy."""
    if in_store.size_in_bytes is None or in_store.size_in_bytes >= source.stat().st_size:
        return False
    with source.open("rb") as opened:
        leading = opened.read(in_store.size_in_bytes)
    return (len(leading) == in_store.size_in_bytes
            and hashlib.sha256(leading).hexdigest() == in_store.sha256)


def rsync_files(copy_host, sources: list, walk_path: pathlib.PurePosixPath):
    """The files to add or replace, in one rsync, flat into `walk_path`: the
    run's staging directory in walk/, which rsync creates (see TWO SHIPMENTS
    OF ONE WALK AT ONCE). -a, --ignore-times (see REPLACED above), never
    --delete or --inplace: rsync writes each file whole or not at all."""
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


class PlannedWalkFileReplacement(typing.NamedTuple):
    """A file the listing found this run may replace: a minutes or
    dispositions file, which is replaced whatever the store holds
    (`required_sha256` None), or a walk text the walk only added to, which
    is replaced only while the store still holds the copy that was tested
    (`required_sha256` that copy's digest) and that copy is still the latest:
    `must_be_absent_name` is the revised copy the next shipment would add,
    and since copies are numbered one after another, its absence shows no
    newer copy has been added. `target_name` is the store's name for it: the
    source's own, or the walk's latest revised copy."""

    source: pathlib.Path
    role_name: str
    required_sha256: typing.Optional[str]
    ruling: str
    target_name: str
    must_be_absent_name: typing.Optional[str] = None


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


def staging_directory_left_behind_failed_line_sentences_with_path_reason_and_rm_command(copy_host, staging_dir, why: str) -> str:
    """What a FAILED line says when remove_staging_directory could not remove
    this run's staging directory: the replace step of every later shipment of
    the walk stops on it until it is deleted."""
    shown = f"{copy_host}:{staging_dir}" if copy_host else str(staging_dir)
    command = f"rm -rf -- {shlex.quote(str(staging_dir))}"
    if copy_host:
        command = f"ssh {copy_host} {shlex.quote(command)}"
    return (f"This run's staging directory {shown} is left behind: removing it "
            f"failed ({why}). Until it is deleted it stops nearly every later "
            f"shipment of this walk. Deleting it loses nothing, because every "
            f"shipment copies the walk's files again into a new staging directory "
            f"of its own; delete it with `{command}`.")


def stopped_shipment_failed_line_with_rerun_command(copy_host, name: str,
                                                    directory: pathlib.Path,
                                                    staging_dir, what_failed: str,
                                                    why: typing.Optional[str]) -> str:
    """The FAILED line of a copy or placing step that failed: it ends with the
    command that reruns this shipment, after the deletion of this run's
    staging directory when that could not be removed, since the rerun's
    replace step would stop on it."""
    walk_argument = (name if directory == WALK_DIRECTORY
                     else str(directory / walk_file_name(name, MINUTES_ROLE_SUFFIX)))
    rerun = (f"{shlex.quote(str(REPO_ROOT / 'scripts' / 'walk-files-ship.py'))} "
             f"{shlex.quote(walk_argument)}")
    if why:
        return (f"FAILED: {name} — {what_failed}. "
                f"{staging_directory_left_behind_failed_line_sentences_with_path_reason_and_rm_command(copy_host, staging_dir, why)} "
                f"Then rerun: `{rerun}`")
    return f"FAILED: {name} — {what_failed}. Rerun: `{rerun}`"


def ship_walk(destination: WalkStoreDestination, name: str,
              directory: pathlib.Path) -> int:
    """One walk, one stdout line, one exit code. A new revised copy of the
    walk text is copied from a file of its own name in a temporary
    directory, because the store's add-only placing links a staged file
    under the name it was staged with."""
    with tempfile.TemporaryDirectory(prefix=f"{PROGRAM}-") as revised_copies:
        return ship_walk_with_revised_copies_directory(
            destination, name, directory, pathlib.Path(revised_copies))


def ship_walk_with_revised_copies_directory(destination: WalkStoreDestination,
                                            name: str, directory: pathlib.Path,
                                            revised_copies: pathlib.Path) -> int:
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
    revised_numbers = []
    if WALK_TEXT_ROLE_SUFFIX in present:
        listed, revised_numbers = stored_revised_walk_text_numbers(
            destination.copy_host, destination.walk_path, name)
        if revised_numbers is None:
            reason = shipper.failed_log_store_step_reason_text_local_stdout_or_ned_box_unreachable_or_ssh_exit(
                destination.copy_host, listed)
            print(f"FAILED: {name} — {reason}; the walk's files stay on disk, unshipped.")
            sys.stderr.write(listed.stderr)
            return EXIT_FAILED
    revised_targets = {number: destination.walk_path / revised_walk_text_file_name(name, number)
                       for number in revised_numbers}
    listed, stored = store_digests_and_sizes(destination.copy_host,
                                             list(targets.values())
                                             + list(revised_targets.values()))
    if stored is None:
        reason = shipper.failed_log_store_step_reason_text_local_stdout_or_ned_box_unreachable_or_ssh_exit(
            destination.copy_host, listed)
        print(f"FAILED: {name} — {reason}; the walk's files stay on disk, unshipped.")
        sys.stderr.write(listed.stderr)
        return EXIT_FAILED

    # Each file's plan is decided on the listing; its outcome on what the
    # store holds after the copy (see TWO SHIPMENTS OF ONE WALK AT ONCE).
    to_place, to_replace, unchanged, refused = [], [], [], []
    role_name_of = dict(WALK_FILE_ROLES)
    local_digests = {}
    for suffix, source in present.items():
        local_digest = sha256_of(source)
        local_digests[source.name] = local_digest
        in_store = stored.get(str(targets[suffix]))
        if suffix == WALK_TEXT_ROLE_SUFFIX:
            # See REVISED COPIES in the docstring: once a revised copy
            # exists, the highest-numbered one is the walk text as last
            # shipped, and the rules apply to it, not to the original.
            latest_name, latest = source.name, in_store
            if revised_numbers:
                latest_name = revised_walk_text_file_name(name, revised_numbers[-1])
                latest = stored.get(str(revised_targets[revised_numbers[-1]]))
            local_digests[latest_name] = local_digest
            if latest is not None and latest.sha256 == local_digest:
                unchanged.append(latest_name)
            elif latest is None and not revised_numbers:
                to_place.append(source)
            elif latest is not None and stored_copy_is_an_exact_prefix(source, latest):
                to_replace.append(PlannedWalkFileReplacement(
                    source, role_name_of[suffix], latest.sha256,
                    APPENDED_TO_RULING.format(stored_bytes=latest.size_in_bytes,
                                              local_bytes=source.stat().st_size),
                    latest_name,
                    revised_walk_text_file_name(
                        name, (revised_numbers[-1] if revised_numbers else 0) + 1)))
            else:
                revised_name = revised_walk_text_file_name(
                    name, (revised_numbers[-1] if revised_numbers else 0) + 1)
                revised_copy = revised_copies / revised_name
                revised_copy.write_bytes(source.read_bytes())
                local_digests[revised_name] = local_digest
                to_place.append(revised_copy)
                print(f"{PROGRAM}: {source.name} differs from {latest_name} in the "
                      f"store by more than added text, so it ships beside it as "
                      f"{revised_name}; the store keeps {latest_name} as it is.",
                      file=sys.stderr)
        elif in_store is not None and in_store.sha256 == local_digest:
            unchanged.append(source.name)
        elif suffix in REPLACED_ROLE_SUFFIXES:
            to_replace.append(PlannedWalkFileReplacement(
                source, role_name_of[suffix], None, REPLACED_ROLE_RULING, source.name))
        elif in_store is None:
            to_place.append(source)
        else:
            refused.append(f"{source.name} (store sha256 {in_store.sha256}, "
                           f"local sha256 {local_digest})")

    # One WalkFileReplacement per replaced file, in the roles' order, which
    # puts the walk text before the minutes and the minutes before the
    # dispositions. `lost` names a file whose copy is not what the store holds.
    added, replaced, lost = set(), [], []
    staging_left_behind = None
    if to_place or to_replace:
        staging_dir = destination.walk_path / (
            f"{shipper.STAGING_DIRECTORY_PREFIX}{name}-{secrets.token_hex(6)}")
        copied = rsync_files(destination.copy_host,
                             to_place + [planned.source for planned in to_replace],
                             staging_dir)
        if copied.returncode != 0:
            why = shipper.remove_staging_directory(destination.copy_host, staging_dir)
            reason = ("ned-box unreachable"
                      if copied.returncode == shipper.RSYNC_EXIT_CONNECTION_FAILED
                      else f"rsync exit {copied.returncode}")
            print(stopped_shipment_failed_line_with_rerun_command(
                destination.copy_host, name, directory, staging_dir,
                f"{reason} during the copy", why))
            sys.stderr.write(copied.stderr)
            return EXIT_FAILED
        outcomes = {}
        if to_replace:
            renamed, outcomes = shipper.replace_with_staged_files(
                destination.copy_host, staging_dir, destination.walk_path,
                [(planned.source.name, planned.target_name, planned.required_sha256,
                  planned.must_be_absent_name)
                 for planned in to_replace])
            if isinstance(outcomes, shipper.OtherShipmentStaging):
                why = shipper.remove_staging_directory(destination.copy_host, staging_dir)
                failed, instruction = shipper.other_shipment_failure_lines(name, outcomes)
                if why:
                    failed += " " + staging_directory_left_behind_failed_line_sentences_with_path_reason_and_rm_command(
                        destination.copy_host, staging_dir, why)
                print(failed)
                sys.stderr.write(instruction + "\n")
                return EXIT_FAILED
            if outcomes is None:
                why = shipper.remove_staging_directory(destination.copy_host, staging_dir)
                reason = shipper.failed_log_store_step_reason_text_local_stdout_or_ned_box_unreachable_or_ssh_exit(
                    destination.copy_host, renamed)
                print(stopped_shipment_failed_line_with_rerun_command(
                    destination.copy_host, name, directory, staging_dir,
                    f"{reason} while putting the copied files in place", why))
                sys.stderr.write(renamed.stderr)
                return EXIT_FAILED
        for planned in to_replace:
            file_name = planned.target_name
            local_digest = local_digests[planned.source.name]
            outcome = outcomes.get(file_name)
            if outcome is None:
                lost.append(f"{file_name} (not in the store after the copy)")
            elif not outcome.replaced and outcome.displaced_sha256 == planned.required_sha256:
                refused.append(f"{file_name} (no longer the store's latest copy: "
                               f"another shipment added {planned.must_be_absent_name} "
                               f"while this run ran; local sha256 {local_digest})")
            elif not outcome.replaced:
                refused.append(f"{file_name} (changed in the store while this run "
                               f"ran: store sha256 {outcome.displaced_sha256}, "
                               f"local sha256 {local_digest})")
            elif outcome.stored_sha256 != local_digest:
                lost.append(f"{file_name} (replaced again by another shipment while "
                            f"this run ran: store sha256 {outcome.stored_sha256}, "
                            f"local sha256 {local_digest})")
            elif outcome.displaced_sha256 is None:
                added.add(file_name)
            elif outcome.displaced_sha256 == local_digest:
                unchanged.append(file_name)
            else:
                replaced.append(WalkFileReplacement(
                    file_name, planned.role_name, outcome.displaced_sha256,
                    local_digest, planned.ruling))
        after = {}
        if to_place:
            placed, after = shipper.link_staged_files_never_over_existing(
                destination.copy_host, staging_dir, destination.walk_path,
                [source.name for source in to_place])
            if after is None:
                why = shipper.remove_staging_directory(destination.copy_host, staging_dir)
                reason = shipper.failed_log_store_step_reason_text_local_stdout_or_ned_box_unreachable_or_ssh_exit(
                    destination.copy_host, placed)
                print(stopped_shipment_failed_line_with_rerun_command(
                    destination.copy_host, name, directory, staging_dir,
                    f"{reason} while putting the copied files in place", why))
                sys.stderr.write(placed.stderr)
                return EXIT_FAILED
        else:
            why = shipper.remove_staging_directory(destination.copy_host, staging_dir)
            if why:
                staging_left_behind = staging_directory_left_behind_failed_line_sentences_with_path_reason_and_rm_command(
                    destination.copy_host, staging_dir, why)
        for source in to_place:
            in_store_now = after.get(source.name)
            if in_store_now == local_digests[source.name]:
                added.add(source.name)
            elif in_store_now is None:
                lost.append(f"{source.name} (not in the store after the copy)")
            else:
                refused.append(f"{source.name} (store sha256 {in_store_now}, "
                               f"local sha256 {local_digests[source.name]})")
        replaced.sort(key=lambda replacement: (store_file_role_rank(name, replacement.file_name),
                                               replacement.file_name))
    added = sorted(added, key=lambda file_name: (store_file_role_rank(name, file_name), file_name))
    # Built from the record shipper's constant, not the destination, which may
    # be a local override the snapshots never hold.
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
    if lost or staging_left_behind:
        sentences = []
        if lost:
            sentences.append(f"not in the store as this run copied them: {'; '.join(lost)}.")
        if staging_left_behind:
            sentences.append(staging_left_behind)
        if refused:
            sentences.append(f"Refused, add-only: {'; '.join(refused)}.")
        if lost:
            sentences.append("Ship the walk again only from the checkout whose copy "
                             "the store should keep.")
        print(f"FAILED: {name} — {' '.join(sentences)} The rest: {summary}; "
              f"minutes at {citation}")
        return EXIT_FAILED
    if refused:
        print(f"REFUSED: {name} — already in the store with different content and "
              f"not replaced, add-only: {'; '.join(refused)}. The rest: {summary}; "
              f"minutes at {citation}")
        return EXIT_REFUSED
    print(f"shipped: {name} — {summary}; minutes at {citation}")
    return EXIT_SHIPPED


class FailedLineArgumentParser(argparse.ArgumentParser):
    """argparse's own error() prints usage on stderr and exits 2; OUTPUT
    promises one FAILED line on stdout and exit 64 for a bad invocation."""

    def error(self, message):
        print(f"FAILED: bad invocation — {message}; {self.format_usage().strip()}")
        sys.exit(EXIT_BAD_INVOCATION)


def main() -> int:
    parser = FailedLineArgumentParser(
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
