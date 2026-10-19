#!/usr/bin/env python3
"""Run a cold-read-full-run against a cold-read-target.

One invocation = one review: six cold-read-cells launched in parallel -- the
defect-hunt pass in four ({deep, second} x {claude, codex}) and the
terminology pass in two (deep x {claude, codex}) -- every report saved
into a cold-read-record named
`cold-read-records/<file stem>-<YYYY-MM-DD>/`, or `SKILL-<skill name>-<YYYY-MM-DD>/` for a skill
(a -2, -3 suffix for a second read of the document that day), progress and next-step
instructions printed for the reviewing agent as reviews land.

Usage:
  nc-systems/cold-read/cold-read-grid.py --target docs/drafts/foo.md

The cold-read-record holds one report per cold-read-cell, the reference-check
file, and under target/ the exact bytes reviewed at the cold-read-target's own
repository path (frozen at launch, the same read that fingerprints it).

AT MOST THREE COLD-READ-FULL-RUNS OF A CHANGE, THEN THE USER DECIDES. Before
it creates anything, the grid lists the cold-read-records in the log-store and
in this checkout, counts those that froze this document, under its present
path or an earlier one `git log --follow` shows, and hold a grid report written
after the commit on origin/main's first-parent line that last changed the
document -- for a merged topic branch, the merge, not the topic's own commit --
prints
"cold-read-full-run N of 3", and refuses a fourth. A flag saying the user
decided to run again or to change the design makes the run number 1, and the
marker file it leaves in its record starts the count again for later runs.
Inside design-to-main, whose own limit of two rounds bounds a writer's cold
reads, a second flag skips the count: the run is neither counted nor refused,
and the marker file it leaves keeps its record out of every later count. The
two flags say opposite things, so the grid refuses both together. A log-store or git history that cannot be read does not stop the read, as
with shipping: the run goes ahead and says EARLIER COLD-READ-FULL-RUNS NOT COUNTED
instead of a count.

THE FROZEN COPY IS WHAT THE COLD-READ-CELLS READ, and it is read-only
(user-ruled 2026-08-28). Every cell used to open the live document, so an edit
part-way through a run left some reports describing the old text and some the
new, with nothing in the record saying which — the 2026-08-24 failure that
marked a whole set COMPROMISED. Detecting that was the earlier answer and it
could be silenced: a stray edit reverted mid-run, which the /cold-read skill
tells the operator to do, restores the original bytes and both endpoint
fingerprints match. Reading a copy removes the failure instead of detecting it.
Consequences a reader should expect: a report's `path:line` citations name the
copy's path inside the cold-read-record, which is where the text it reviewed
is; each cold-read-cell is also given the original's path (`--target-origin`)
and told to resolve the document's relative references from the original's
directory, because only the document itself is copied and a link such as
`../issues/x.md` has nothing beside the copy to reach -- the reference
pre-pass resolves those links against the original too, so the record and the
reviewers agree on what a link names (asked for by both reviews of 2026-09-23);
and the run fingerprints the copy, because the records tree is gitignored and
an edit to the copy would otherwise be invisible to the cold-read-cell's
`git status` stray-write detector. Each report's provenance stamp carries the
copy's sha256 (`target_sha256=`), so the bytes a report reviewed are named in
the report itself. At the
end of the run the cold-read-record is shipped to the log-store on ned-box by
nc-systems/cold-read/cold-read-record-ship.py, whatever the run's outcome, and the shipper's
one line is printed as `record:`; a shipping failure is reported, never fatal
(user-ruled 2026-09-07). The one run that ships nothing is the one that could
not freeze the target: it exits 2 before any cold-read-cell launches, so its
record holds the reference check alone and no report to keep.

WHEN A COLD-READ-CELL FAILS (nedschorus#413; the design, user-reviewed
2026-09-16 and 2026-09-17, is
nc-systems/cold-read/cold-read-grid-cell-failure-handling-design.md). Every
cold-read-cell whose attempt ends without a landed report is retried once,
at once, with the same model -- no cold-read-cell is special (user-ruled
2026-09-11) -- and the first attempt's log is kept as
`<report file name>.attempt-1.stderr.log`. Each failed attempt is reported
with its CAUSE, the `cause:` line the cold-read-cell program prints
(nc-systems/cold-read/cold-read-cell-common.py, classify_failed_attempt) or, when it left
none, one the cold-read-grid names itself: `RETRYING:` at the first failure,
`FAILED (exit N):` at the second, after which the report is ABSENT. When
every cold-read-cell of one agent-binary has landed or is absent for the same
agent-binary-wide cause, one `AGENT-BINARY DOWN:` line says so. Every run closes
with one closing text built from what landed: all landed, some landed (the
set is valid and incomplete, and is triaged), none landed, or the
cold-read-target changed, whatever else happened. When any report is absent
every .md file in the record is marked `<!-- INCOMPLETE SET: ... -->`, and
when an absent report's cause is one the user can clear the closing text
ends "Tell the user: ...". A cause changes what is reported, never what is
decided: the retry, the absence, the closing text and the exit code turn
only on whether a report landed. No timeout: a cold-read-cell that hangs
holds the run (user-ruled 2026-09-17: add one if a hang is ever seen).

AN EDIT TO THE ORIGINAL STOPS NOTHING.
Every cold-read-cell reads the frozen copy, so an edit to the original leaves
each report a review of bytes that are still in the record: the run finishes,
exits as it would have, and prints one #cold_read_target_changed_during_run line
naming the copy the set reviewed, so the triage reads findings against the
copy and carries each fix to the document as it now stands.

A RUN STOPS AS SOON AS ITS FROZEN COPY MOVES (user-ruled 2026-09-23, walk
cold-read-research-decisions-waiting-on-the-user-2026-09-23, item 6: "n, and
yes abort early"). An edit to the copy means no report can say which text it
read, so a reviewer still reading is spending the rest of a 10-20 minute read
on a review nobody will triage. The copy's fingerprint is therefore taken at
every poll, not only at the end: the first poll that sees it differ while any
cold-read-cell is still running stops every running cold-read-cell with its
children, marks what the set holds, and exits 3. Every poll, which is every 5
seconds, because hashing a Markdown file costs microseconds: a slower cadence
would buy nothing and add a timer. The end-of-run comparison stays, for a move
after the last cold-read-cell has finished, which stops nothing. A
cold-read-cell is stopped with its children because it is a launcher whose
model CLI runs as a child process: stopping the launcher alone would leave the
CLI reading, spending tokens, and free to write its report into the record
after the marker went on.

A RUN STOPPED BECAUSE ITS FROZEN COPY MOVED DOES NOT COUNT toward the three:
the marker file it leaves in its record keeps the record out of every later
count, so the new run the closing text asks for is never refused as a fourth.
A document that keeps changing would then loop, so the third such stop in a row
since the count last started ends the attempt: its closing text says to tell
the user instead of starting a new run, and a run launched after it is refused
until the user rules.

Exit codes: 0 all cold-read-cells ran, 1 one or more reports are absent, 2 no
cold-read-cell was launched (a bad invocation, a cold-read-target this
instrument refuses to review, or a cold-read-target that could not be frozen
into the cold-read-record), 3 the frozen copy changed while the
cold-read-cells were running, so no report in the set can say which text it
reviewed. An edit to the original alone changes no exit code.
"""

import argparse
import collections
import datetime
import hashlib
import importlib.util
import os
import pathlib
import re
import shlex
import signal
import subprocess
import sys
import time
import typing
import urllib.parse

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
_record_names_spec = importlib.util.spec_from_file_location(
    "cold_read_record_names",
    pathlib.Path(__file__).with_name("cold-read-record-names.py"))
record_names = importlib.util.module_from_spec(_record_names_spec)
_record_names_spec.loader.exec_module(record_names)
RECORDS_DIR = record_names.RECORDS_DIR
CELL_LAUNCHERS = {
    "claude": pathlib.Path(__file__).with_name("cold-read-claude-cell.py"),
    "codex": pathlib.Path(__file__).with_name("cold-read-codex-cell.py"),
}
RECORD_SHIPPER = pathlib.Path(__file__).with_name("cold-read-record-ship.py")
_record_shipper_spec = importlib.util.spec_from_file_location(
    "cold_read_record_ship", RECORD_SHIPPER)
record_shipper = importlib.util.module_from_spec(_record_shipper_spec)
_record_shipper_spec.loader.exec_module(record_shipper)
# Import shared status phrases so launcher output and grid parsing cannot drift.
_common_spec = importlib.util.spec_from_file_location(
    "cold_read_cell_common", pathlib.Path(__file__).with_name("cold-read-cell-common.py")
)
cell_common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(cell_common)
_git_redirecting_removal_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_variables_removal_common",
    REPO_ROOT / "nc-systems" / "general-tools"
    / "git-redirecting-environment-variables-removal-common.py")
git_redirecting_removal = importlib.util.module_from_spec(_git_redirecting_removal_spec)
_git_redirecting_removal_spec.loader.exec_module(git_redirecting_removal)
_ned_box_home_spec = importlib.util.spec_from_file_location(
    "ned_box_home_directory_and_its_mac_mount_point_path_constants_common",
    REPO_ROOT / "nc-systems" / "general-tools"
    / "ned-box-home-directory-and-its-mac-mount-point-path-constants-common.py")
ned_box_home_path_constants = importlib.util.module_from_spec(_ned_box_home_spec)
_ned_box_home_spec.loader.exec_module(ned_box_home_path_constants)
# The log also contains runtime and model text; only program-prefixed lines are cell status.
CELL_PROGRAM_NAMES = tuple(path.stem for path in CELL_LAUNCHERS.values())
# Pin terminology effort explicitly so launcher tier-map changes cannot change the pass.
GRID_CELL_ROSTER = (
    ("defect-hunt", "deep", None),
    ("defect-hunt", "second", None),
    ("terminology", "deep", "max"),
)

# Logs, reports and captures record observations; cold reads must not revise that evidence.
UNREVIEWABLE_TARGET_GENRE_SUFFIXES = ("-log", "-report", "-capture")

FROZEN_COPY_CHANGED_HASHTAG = "#frozen_copy_changed_during_run"
COLD_READ_TARGET_CHANGED_HASHTAG = "#cold_read_target_changed_during_run"
FROZEN_COPY_CHANGED_MARKER_PREFIX = f"<!-- {FROZEN_COPY_CHANGED_HASHTAG}"
INCOMPLETE_SET_MARKER_PREFIX = "<!-- INCOMPLETE SET:"
GRID_MARKER_PREFIXES = (FROZEN_COPY_CHANGED_MARKER_PREFIX, INCOMPLETE_SET_MARKER_PREFIX)

# These prefixes are consumed by the cold-read skill's Monitor; FAILED keeps its no-colon form.
RETRYING_PREFIX = "RETRYING:"
AGENT_BINARY_DOWN_PREFIX = "AGENT-BINARY DOWN:"
STOPPED_CELL_WRITE_CHECK_LINE = (
    "this cell was stopped before its stray-write check ran, which is a failure "
    "to look, not a clean result. Before the new run, read `git status` against "
    "the edits you know are your own, revert only what a reviewer evidently wrote, "
    "and ask the user about any other change you did not make.")

ALL_LANDED_OPENING = "All six reports landed in {record_dir}, one file per reviewer."
SOME_LANDED_OPENING = (
    "{landed} of {launched} reports landed in {record_dir}. The set is valid "
    "and incomplete: triage the reports that landed.")
NONE_LANDED_OPENING = "No report landed in {record_dir}, so there is nothing to triage."
NONE_LANDED_CLOSING = (
    "Start a new cold-read-full-run once the causes above that the user can "
    "clear are cleared, or at once if none of them is.")
RECORD_ABSENCES_SENTENCE = "Record each absent report and its cause in triage.md."

COMPLETION_BODY = """\
Read every report in full. The defect-hunt reports flag defects with each
reviewer's own confidence; expect heavy overlap — the same defect found
independently by several reviewers is one defect. The terminology reports
list the document's terms that fail one of five criteria, with the
criteria numbers per item and a closing counts line; triage them the same
way as the defect-hunt reports.

Keep your judgments provisional until you have read {read_until}, as later
reports may offer more insight than earlier ones. Then formulate your draft
response: which problems are real, and what you propose to do about each.
A problem one reviewer alone reports is real. Then apply your changes, and
take to the user only what step 9 of the /cold-read skill sends to the
user.{record_absences}

This record was shipped to the log-store on ned-box when the run ended (the
`record:` line above says whether it arrived); once triage.md is written,
run `nc-systems/cold-read/cold-read-record-ship.py {record_dir}` so it joins the reports
there. cold-read-records/ stays gitignored: never commit it. Leave {record_dir}
in place once the work it served has landed — these records are kept, not
deleted: like other logs they are useful for analysis later (user-ruled
2026-08-25). The findings still belong in the reviewed document and the
rulings in its governing document; this directory is what produced them, not
where they live."""


RECORD_CLOCK_OVERRIDE_VARIABLE = "COLD_READ_RECORD_CLOCK_OVERRIDE"
RECORD_CLOCK_OVERRIDE_FORMAT = "%Y-%m-%dT%H:%M"

# Tests can defer polling to isolate the end-of-run comparison from cell-exit timing.
TARGET_CHECK_INTERVAL_OVERRIDE_VARIABLE = "COLD_READ_GRID_TARGET_CHECK_INTERVAL_SECONDS"
# Tests shorten the poll so stub cells that finish at once are not waited on for seconds.
CELL_POLL_INTERVAL_OVERRIDE_VARIABLE = "COLD_READ_GRID_CELL_POLL_INTERVAL_SECONDS"
CELL_POLL_INTERVAL_DEFAULT_SECONDS = 5.0


def record_clock_reading() -> datetime.datetime:
    """Read one local time for both record date and time, avoiding a midnight split."""
    override = os.environ.get(RECORD_CLOCK_OVERRIDE_VARIABLE)
    if override:
        return datetime.datetime.strptime(override, RECORD_CLOCK_OVERRIDE_FORMAT)
    return datetime.datetime.now()


record_name_for_target = record_names.record_name_for_target
record_directory_name_for_target = record_names.record_directory_name_for_target


FULL_RUN_LIMIT = 3
USER_RULED_COUNT_RESTART_FLAG = "--user-ruled-cold-read-full-run-count-restart"
USER_RULED_COUNT_RESTART_MARKER_NAME = "user-ruled-cold-read-full-run-count-restart-marker.txt"
COUNT_SKIPPED_INSIDE_DESIGN_TO_MAIN_FLAG = "--cold-read-full-run-count-skipped-inside-design-to-main"
COUNT_SKIPPED_INSIDE_DESIGN_TO_MAIN_MARKER_NAME = (
    "cold-read-full-run-count-skipped-inside-design-to-main-marker.txt")
FROZEN_COPY_CHANGED_STOP_MARKER_NAME = "frozen-copy-changed-during-run-stop-marker.txt"
FROZEN_COPY_CHANGED_STOPS_IN_A_ROW_LIMIT = 3
# A grid report's name. Older records prefix each report with "<record name>--".
# A fast read's record holds fast-read.md and, beside it, a copy of the target
# marked with sentence ids, whose name matches this pattern too when the
# target's stem starts claude- or codex-, so that copy is excluded by suffix.
FULL_RUN_REPORT_NAME_PATTERN = re.compile(r"^(?:.*--)?(?:claude|codex)-.*\.md$")


class FullRunCountUnavailable(Exception):
    """The log-store or the document's git history could not be read."""


def git_output(target: pathlib.Path, *arguments) -> str:
    completed = subprocess.run(["git", "-C", str(target.parent), *arguments],
                               capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise FullRunCountUnavailable(
            f"git {' '.join(arguments)} on {target} exited {completed.returncode}: "
            f"{completed.stderr.strip()}")
    return completed.stdout


def frozen_paths_and_landing_time(target: pathlib.Path) -> tuple:
    """The paths a record freezes this document under -- its present one and
    every earlier one git shows -- and when main last took a change to it, so
    that only the runs reviewing the change in hand count. A document outside
    any git repository has one path and no landing time."""
    resolved = target.resolve()
    top = subprocess.run(["git", "-C", str(target.parent), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True, check=False)
    if top.returncode != 0:
        return {str(pathlib.Path(*resolved.parts[1:]))}, None
    relative = str(resolved.relative_to(pathlib.Path(top.stdout.strip()).resolve()))
    history = git_output(target, "log", "--follow", "--name-only", "--format=", "--", target.name)
    paths = {relative} | {line for line in history.splitlines() if line.strip()}
    has_main = subprocess.run(
        ["git", "-C", str(target.parent), "rev-parse", "--verify", "--quiet", "origin/main"],
        capture_output=True, text=True, check=False).returncode == 0
    # --first-parent: a merge commit is TREESAME to its topic parent, so plain
    # `git log` simplifies it away and reports the topic commit's older time.
    # Every path is given, so a document renamed on a branch not yet merged is
    # found on main under its earlier name.
    landed = git_output(target, "log", "-1", "--first-parent", "--format=%ct", "origin/main", "--",
                        *(f":(top,literal){path}" for path in sorted(paths))).strip() \
        if has_main else ""
    return paths, float(landed) if landed else None


def record_file_listing(host, store) -> list:
    """Every '<record directory>/<path>\t<mtime>' under one cold-read-records tree."""
    if not host:
        # Listed in Python: the Mac's find has no -printf.
        store = pathlib.Path(store)
        if not store.is_dir():
            raise FullRunCountUnavailable(f"listing {store} failed: no such directory")
        def unreadable(error):
            raise FullRunCountUnavailable(f"listing {store} failed: {error}") from error
        try:
            listing = []
            for directory, _, files in os.walk(store, onerror=unreadable):
                if pathlib.Path(directory) == store:
                    continue
                for name in files:
                    path = pathlib.Path(directory, name)
                    listing.append(f"{path.relative_to(store)}\t{path.stat().st_mtime}")
            return sorted(listing)
        except OSError as error:
            raise FullRunCountUnavailable(f"listing {store} failed: {error}") from error
    # The store a remote host holds is on ned-box, whose find is GNU find.
    command = record_shipper.SSH_COMMAND + [host, shlex.join(
        ["find", str(store), "-mindepth", "2", "-type", "f", "-printf", "%P\t%T@\n"])]
    listing = subprocess.run(command, capture_output=True, text=True, check=False)
    if listing.returncode != 0:
        raise FullRunCountUnavailable(
            f"listing {host}:{store} exited {listing.returncode}: {listing.stderr.strip()}")
    return listing.stdout.splitlines()


def earlier_full_runs_since_count_start(frozen_paths: set, landed_at, listing: list) -> list:
    """The record directories of this document's cold-read-full-runs since
    main last took a change to it, oldest first, from the last one started on
    the user's ruling onward."""
    return full_run_history_since_count_start(frozen_paths, landed_at, listing)[0]


def full_run_history_since_count_start(frozen_paths: set, landed_at, listing: list) -> tuple:
    """The counted runs' record directories, oldest first, and how many runs
    in a row, ending with the latest, stopped because their frozen copy moved."""
    records = {}
    for line in listing:
        path, _, mtime = line.rpartition("\t")
        directory, _, inside = path.partition("/")
        # An interrupted shipment's staging copy holds the same files as its record.
        if directory.startswith(record_shipper.STAGING_DIRECTORY_PREFIX):
            continue
        record = records.setdefault(directory, {"frozen": False, "reported": None, "marked": None,
                                                "inside_design_to_main": False, "stopped": None})
        frozen = inside.removeprefix(record_names.FROZEN_TARGET_DIRECTORY_NAME + "/")
        if frozen != inside and any(frozen == p or frozen.endswith("/" + p) for p in frozen_paths):
            record["frozen"] = True
        elif (FULL_RUN_REPORT_NAME_PATTERN.match(inside)
              and not inside.endswith(record_names.GENERATED_INPUT_COPY_SUFFIXES)):
            record["reported"] = max(record["reported"] or 0.0, float(mtime))
        elif inside == USER_RULED_COUNT_RESTART_MARKER_NAME:
            record["marked"] = float(mtime)
        elif inside == COUNT_SKIPPED_INSIDE_DESIGN_TO_MAIN_MARKER_NAME:
            record["inside_design_to_main"] = True
        elif inside == FROZEN_COPY_CHANGED_STOP_MARKER_NAME:
            record["stopped"] = float(mtime)
    # The marker is written when its run starts, before any report, so a run
    # whose every cell failed still restarts the count.
    count_start = max([landed_at or 0.0] + [record["marked"] for record in records.values()
                                             if record["frozen"] and record["marked"] is not None])
    mine = {directory: record for directory, record in records.items()
            if record["frozen"] and not record["inside_design_to_main"]}
    runs = sorted((record["reported"], directory) for directory, record in mine.items()
                  if record["stopped"] is None
                  and record["reported"] and record["reported"] > count_start)
    stops = [(record["stopped"], directory) for directory, record in mine.items()
             if record["stopped"] is not None and record["stopped"] > count_start]
    stops_in_a_row = 0
    for _, directory in sorted(runs + stops, reverse=True):
        if mine[directory]["stopped"] is None:
            break
        stops_in_a_row += 1
    return [directory for _, directory in runs], stops_in_a_row


def earlier_full_runs_of(target: pathlib.Path) -> tuple:
    """Counted from the log-store and from this checkout's own records, which
    hold a run whose shipping failed; returned as full_run_history_since_count_start returns."""
    frozen_paths, landed_at = frozen_paths_and_landing_time(target)
    listing = record_file_listing(*record_shipper.destination_for_this_machine())
    if RECORDS_DIR.is_dir():
        listing += record_file_listing(None, RECORDS_DIR)
    return full_run_history_since_count_start(frozen_paths, landed_at, listing)


def make_record_dir(target: pathlib.Path, now: datetime.datetime) -> pathlib.Path:
    """Create and return the first unused record directory for this document and day."""
    record_dir = record_names.fresh_record_directory(
        RECORDS_DIR / record_directory_name_for_target(target, now))
    record_dir.mkdir(parents=True)
    return record_dir


# A link ends where Markdown, HTML or a quote closes it.
URL_BODY = r"[^\s)\]>\"'`<]+"
MAC_MOUNT_OF_NED_BOX_HOME = ned_box_home_path_constants.MAC_MOUNT_OF_NED_BOX_HOME + "/"
NED_BOX_HOME = ned_box_home_path_constants.NED_BOX_HOME + "/"
MAC_HOME = "/Users/el/"


def without_trailing_sentence_punctuation(reference: str) -> str:
    """A reference without the one punctuation mark a sentence puts after it."""
    # A period after another dot is kept: a run of dots, such as a "..." placeholder, is part of what was written.
    return re.sub(r"[,;:]$|(?<!\.)\.$", "", reference)


def file_link_path(link: str) -> str:
    """The file a file:// link names, without its #fragment or ?query."""
    # The URL is parsed before %-escapes are decoded, so an escaped # stays in the file name.
    return urllib.parse.unquote(urllib.parse.urlsplit(without_trailing_sentence_punctuation(link)).path)


def file_link_status(path: str) -> str:
    """ok, UNRESOLVED, or not checkable when the path is under a root this machine does not have."""
    if pathlib.Path(path).exists():
        return "ok"
    # The Mac reaches ned-box's home through its mount, so a link written for the Mac names a ned-box file.
    if path.startswith(MAC_MOUNT_OF_NED_BOX_HOME) and pathlib.Path(NED_BOX_HOME).is_dir():
        on_ned_box = NED_BOX_HOME + path[len(MAC_MOUNT_OF_NED_BOX_HOME):]
        return "ok" if pathlib.Path(on_ned_box).exists() else "UNRESOLVED"
    for root in (MAC_HOME, NED_BOX_HOME, MAC_MOUNT_OF_NED_BOX_HOME):
        if path.startswith(root) and not pathlib.Path(root).is_dir():
            return "not checkable on this machine"
    return "UNRESOLVED"


def reference_integrity_pre_pass(target: pathlib.Path, record_dir: pathlib.Path) -> None:
    """Save unresolved references as leads for the reviewer."""
    raw_text = target.read_text(encoding="utf-8")
    file_link_paths = sorted({file_link_path(link)
                              for link in re.findall(r"file:///" + URL_BODY, raw_text)})
    # A URL's tail looks like a path, so URLs are removed before matching.
    text = re.sub(r"[A-Za-z][A-Za-z0-9+.-]*://" + URL_BODY, " ", raw_text)
    # A filename can contain more than one dot.
    candidates = sorted(set(re.findall(
        r"[\w./-]+/[\w./-]+|[\w-]+(?:\.[\w-]+)*\.(?:md|py|sh|json|yaml|toml)",
        text)))
    # Prose names a file by its bare name wherever the file lives, and a draft
    # names files it adds before they are committed.
    listing = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--cached", "--others", "--exclude-standard"],
        capture_output=True, text=True,
        env=git_redirecting_removal.environment_without_git_redirecting_variables())
    name_counts = collections.Counter(
        pathlib.PurePosixPath(path).name for path in listing.stdout.splitlines())
    lines = ["# Reference-integrity pre-pass", ""]
    for path in file_link_paths:
        lines.append(f"- {file_link_status(path)}: `{path}`")
    if listing.returncode != 0:
        # The pre-pass is a lead for the reviewer, so it goes on without the lookup.
        lines += [f"- bare file names were not looked up: git ls-files exited"
                  f" {listing.returncode}: {listing.stderr.strip()}", ""]
    for candidate in candidates:
        clean = without_trailing_sentence_punctuation(candidate)
        resolved = (REPO_ROOT / clean).exists() or (target.parent / clean).exists()
        sharing = name_counts[clean] if "/" not in clean else 0
        # A bare name names a file only when one file has it.
        note = f" ({sharing} files have this name)" if not resolved and sharing > 1 else ""
        lines.append(f"- {'ok' if resolved or sharing == 1 else 'UNRESOLVED'}: `{clean}`{note}")
    if not candidates and not file_link_paths:
        lines.append("- no path-like references found")
    (record_dir / "reference-check.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")


def freeze_target(target: pathlib.Path, record_dir: pathlib.Path) -> str:
    """Copy the target and return its SHA-256, or an empty string when unreadable."""
    # Read once so copy and digest agree; read-only mode protects a copy git status cannot see.
    try:
        content = target.read_bytes()
    except OSError:
        return ""
    frozen = record_names.frozen_target_path(target, record_dir)
    frozen.parent.mkdir(parents=True, exist_ok=True)
    frozen.write_bytes(content)
    frozen.chmod(0o444)
    return hashlib.sha256(content).hexdigest()


def ship_record(record_dir: pathlib.Path) -> str:
    """Return the shipper's status line, reporting failures without raising."""
    try:
        completed = subprocess.run(
            [sys.executable, str(RECORD_SHIPPER), str(record_dir)],
            capture_output=True, text=True, check=False)
    except OSError as error:
        return f"FAILED: the shipper could not be run ({error}); the record stays on disk."
    sys.stderr.write(completed.stderr)
    line = completed.stdout.strip().splitlines()
    return line[0] if line else (
        f"FAILED: the shipper printed nothing (exit {completed.returncode}); "
        f"the record stays on disk.")


def target_content_fingerprint(target: pathlib.Path) -> str:
    """Return the content hash, or an empty string when unreadable."""
    # mtime changes on save-and-undo; polling still cannot detect edits reverted between polls.
    try:
        return hashlib.sha256(target.read_bytes()).hexdigest()
    except OSError:
        return ""


def moved_frozen_copy(frozen_target: pathlib.Path,
                      before: str) -> typing.Optional[tuple]:
    """Return (path, current hash) when the frozen copy changed, or None."""
    frozen_now = target_content_fingerprint(frozen_target)
    if frozen_now != before:
        return frozen_target, frozen_now
    return None


def original_changed_line(target: pathlib.Path, frozen_target: pathlib.Path,
                          before: str, frozen_changed: bool) -> str:
    """Return the line naming the copy reviewed when the original changed, or ""."""
    after = target_content_fingerprint(target)
    if after == before:
        return ""
    changed = (f"{COLD_READ_TARGET_CHANGED_HASHTAG} {target}'s bytes changed after the cells "
               f"launched — sha256 {before[:12]} then {after[:12] or 'unreadable'}. ")
    if frozen_changed:
        return (changed + f"The frozen copy {frozen_target} changed too, so the "
                f"{FROZEN_COPY_CHANGED_HASHTAG} line above says what to do with the set.")
    return (changed + f"Every report reviews the frozen copy {frozen_target} (sha256 "
            f"{before[:12]}), which did not change, so the set stands: triage it "
            f"against that copy, then carry each fix to the document as it now stands.")


WINDOW_SEEN_AT_END = ("differed between the moment the cells launched and the "
                      "moment the last one finished")
WINDOW_SEEN_MID_RUN = ("changed while the cells were still running, and the run "
                       "stopped the ones still reading")


TARGET_CHANGED_INSTRUCTIONS = """\
The reports are in {record_dir}, and every one of them is marked: the frozen
copy's bytes {window}, so no report can say which text it reviewed.

Do not triage this set as a review of the document. Find what edited the
frozen copy.

Keep the set. Each report still records truthfully what one reviewer read, which
is evidence of what the reviewers saw — not of how the file now stands.
"""


def frozen_copy_stop_count_line(stop_number: int) -> str:
    """Say where this stop leaves the attempt, for the closing text."""
    if stop_number < FROZEN_COPY_CHANGED_STOPS_IN_A_ROW_LIMIT:
        return (f"Start a new cold-read run. This run does not count toward the "
                f"{FULL_RUN_LIMIT} cold-read-full-runs: it is stop {stop_number} of "
                f"{FROZEN_COPY_CHANGED_STOPS_IN_A_ROW_LIMIT} in a row because the frozen "
                f"copy changed.")
    return (f"This is stop {stop_number} in a row because the frozen copy changed, which "
            f"ends the attempt: do not start a new cold-read run. Tell the user, and ask "
            f"whether to stop, run again with {USER_RULED_COUNT_RESTART_FLAG}, or change "
            f"the document's design first and then run again with that flag.")


def mark_reports_target_changed(
    record_dir: pathlib.Path, target: pathlib.Path, before: str, after: str,
    seen_mid_run: bool = False,
) -> str:
    """Mark reports as reviewing a frozen copy that changed and return the marker."""
    # Fingerprints establish differing bytes, not when the edit occurred.
    what_the_reports_describe = (
        "Which text any one report in this directory describes is unknown: "
        "the edit may have landed before a given reviewer opened the file "
        "or after."
    )
    window = WINDOW_SEEN_MID_RUN if seen_mid_run else WINDOW_SEEN_AT_END
    detail = (
        f"{target}'s bytes {window} — sha256 {before[:12] or 'unreadable'} then "
        f"{after[:12] or 'unreadable'}. {what_the_reports_describe} Treat this set "
        f"as evidence of what reviewers saw, not as a review of the document."
    )
    mark_every_report(record_dir, f"{FROZEN_COPY_CHANGED_MARKER_PREFIX} {detail} -->")
    return detail


def mark_every_report(record_dir: pathlib.Path, marker: str) -> None:
    """Insert a marker after provenance and existing markers in every Markdown report."""
    for report_path in sorted(record_dir.glob("*.md")):
        lines = report_path.read_text(encoding="utf-8").split("\n")
        insert_at = 1 if lines and lines[0].startswith("<!-- provenance:") else 0
        while insert_at < len(lines) and lines[insert_at].startswith(GRID_MARKER_PREFIXES):
            insert_at += 1
        lines.insert(insert_at, marker)
        report_path.write_text("\n".join(lines), encoding="utf-8")


def incomplete_set_marker(absent: dict, launched: int) -> str:
    """Return a marker naming missing reports and their failure causes."""
    named = ", ".join(f"{report.cell_name} ({report.cause_class}"
                      f"{cell_common.CAUSE_SEPARATOR}{report.detail})"
                      for report in absent.values())
    return (f"{INCOMPLETE_SET_MARKER_PREFIX} {len(absent)} of {launched} reports "
            f"absent{cell_common.CAUSE_SEPARATOR}{named} -->")


def cell_report_path(
    record_dir: pathlib.Path, runtime: str, cell_pass: str, tier: str,
) -> pathlib.Path:
    pass_token = "hunt" if cell_pass == "defect-hunt" else cell_pass
    return record_dir / f"{runtime}-{pass_token}-{tier}.md"


class CellAttempt(typing.NamedTuple):
    """One launch attempt, with no process when startup fails."""

    report_path: pathlib.Path
    command: list
    attempt: int
    process: typing.Optional[subprocess.Popen]
    stderr_path: pathlib.Path
    start_error: str


class AbsentReport(typing.NamedTuple):
    """A missing report with the second attempt's cause and log."""

    cell_name: str
    runtime: str
    cause_class: str
    detail: str
    log_path: pathlib.Path


class RunOutcome(typing.NamedTuple):
    """Landed, absent and stopped cells, agent-binary failures, and any target change."""

    landed: list
    absent: dict
    down: dict
    stopped: list
    moved_mid_run: typing.Optional[tuple]


def cell_name_of(report_path: pathlib.Path) -> str:
    return report_path.stem


def runtime_of(cell_name: str) -> str:
    return cell_name.split("-", 1)[0]


def start_attempt(command: list, report_path: pathlib.Path, attempt: int,
                  stderr_path: pathlib.Path) -> CellAttempt:
    """Launch a cell with output logged; return an attempt even if startup fails."""
    with open(stderr_path, "w", encoding="utf-8") as err:
        try:
            process = subprocess.Popen(  # pylint: disable=consider-using-with
                command, stdout=err, stderr=err, stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as error:
            err.write(f"cold-read-grid: could not start {command[0]}: {error}\n")
            return CellAttempt(report_path, command, attempt, None, stderr_path, str(error))
    return CellAttempt(report_path, command, attempt, process, stderr_path, "")


def launch_cells(target: pathlib.Path, record_dir: pathlib.Path,
                 target_origin: pathlib.Path) -> dict:
    """Return {report_path: CellAttempt} for reviewers of the frozen target."""
    running = {}
    for runtime, launcher in CELL_LAUNCHERS.items():
        for cell_pass, tier, effort in GRID_CELL_ROSTER:
            report_path = cell_report_path(record_dir, runtime, cell_pass, tier)
            stderr_path = record_dir / (report_path.name + ".stderr.log")
            command = [str(launcher), "--cell", cell_pass, "--tier", tier,
                       "--target", str(target),
                       "--target-origin", str(target_origin),
                       "--report", str(report_path)]
            # An explicit effort bypasses the launcher's tier-map default.
            if effort:
                command += ["--effort", effort]
            # The reviewer writes its report; captured chat can omit findings written before tool calls.
            running[report_path] = start_attempt(command, report_path, 1, stderr_path)
    return running


def cell_status_line(line: str, phrase: str) -> bool:
    """Return whether a cell's own status line begins with phrase."""
    stripped = line.strip()
    return any(stripped.startswith(f"{program}: {phrase}")
               for program in CELL_PROGRAM_NAMES)


def lift_cell_status_lines(report_path: pathlib.Path, log_lines: list) -> None:
    """Print cell status lines before successful-attempt logs are deleted."""
    for line in log_lines:
        if cell_status_line(line, cell_common.STRAY_WRITE_PHRASE):
            print(f"STRAY WRITE: {line.strip()}", flush=True)
        if cell_status_line(line, cell_common.STRAY_WRITE_CHECK_SKIPPED_PHRASE):
            print(f"WRITE CHECK DID NOT RUN: {report_path.name} — "
                  f"{line.strip()}", flush=True)
        if cell_status_line(line, cell_common.FELL_BACK_PHRASE):
            print(f"FELL BACK: {report_path.name} — {line.strip()}", flush=True)
        if cell_status_line(line, cell_common.NEAR_MISS_RECOVERY_PHRASE):
            print(f"RECOVERED: {report_path.name} — {line.strip()}", flush=True)


def cause_of_failed_attempt(attempt: CellAttempt, exit_code, log_lines: list) -> tuple:
    """Return (cause class, detail), preferring the last cell-authored cause line."""
    if attempt.process is None:
        return "program-unstartable", attempt.start_error
    cause_lines = [line.strip() for line in log_lines
                   if cell_status_line(line, cell_common.CAUSE_PHRASE)]
    if cause_lines:
        text = cause_lines[-1].split(f": {cell_common.CAUSE_PHRASE} ", 1)[1]
        # strip() removes the trailing space from an empty-detail cause line.
        cause_class, _, detail = text.partition(cell_common.CAUSE_SEPARATOR.rstrip())
        return cause_class, detail.strip()
    if exit_code == 0:
        return "no-report", "no report written"
    non_empty = [line.strip() for line in log_lines if line.strip()]
    detail = (non_empty[-1][:cell_common.CAUSE_DETAIL_MAX_CHARACTERS]
              if non_empty else "no output")
    return f"exit-{exit_code}", detail


def announce_agent_binary_down(cells_by_runtime: dict, outcome: RunOutcome) -> None:
    for runtime, cells in cells_by_runtime.items():
        if runtime in outcome.down:
            continue
        absences = [report for report in outcome.absent.values()
                    if report.runtime == runtime]
        if not absences:
            continue
        if any(cell not in outcome.absent and cell not in outcome.landed for cell in cells):
            continue
        classes = {report.cause_class for report in absences}
        if len(classes) != 1 or not classes <= cell_common.AGENT_BINARY_WIDE_CAUSE_CLASSES:
            continue
        last = absences[-1]
        outcome.down[runtime] = (last.cause_class, last.detail, len(absences))
        print(f"{AGENT_BINARY_DOWN_PREFIX} {runtime}{cell_common.CAUSE_SEPARATOR}"
              f"{last.cause_class}{cell_common.CAUSE_SEPARATOR}{last.detail}; "
              f"{len(absences)} reports absent", flush=True)


def stop_process_tree(process: subprocess.Popen, grace_seconds: float = 5.0) -> None:
    """Stop a cell's process group and reap its launcher."""
    # macOS answers EPERM, not ESRCH, for a group whose members have all exited.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        pass
    # Children may remain in the group after the launcher exits.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    process.wait()


def wait_for_cells(running: dict,
                   target_move: typing.Callable[[], typing.Optional[tuple]],
                   target_check_interval_seconds: float = 0.0,
                   cell_poll_interval_seconds: float = CELL_POLL_INTERVAL_DEFAULT_SECONDS,
                   ) -> RunOutcome:
    """Retry failed cells once and wait for reports, absences or a changed target."""
    # A successful exit alone does not prove a review exists; require a nonempty report.
    outcome = RunOutcome([], {}, {}, [], None)
    last_target_check = time.monotonic()
    cells_by_runtime = {}
    for report_path in running:
        cells_by_runtime.setdefault(
            runtime_of(cell_name_of(report_path)), []).append(cell_name_of(report_path))
    while running:
        time.sleep(cell_poll_interval_seconds)
        for report_path in list(running):
            attempt = running[report_path]
            code = None if attempt.process is None else attempt.process.poll()
            if attempt.process is not None and code is None:
                continue
            del running[report_path]
            name = cell_name_of(report_path)
            log_lines = attempt.stderr_path.read_text(encoding="utf-8").splitlines()
            lift_cell_status_lines(report_path, log_lines)
            has_report = (
                report_path.is_file()
                and report_path.read_text(encoding="utf-8").strip() != ""
            )
            if attempt.process is not None and code == 0 and has_report:
                attempt.stderr_path.unlink(missing_ok=True)
                print(f"saved: {report_path}", flush=True)
                outcome.landed.append(name)
            else:
                cause_class, detail = cause_of_failed_attempt(attempt, code, log_lines)
                cause = f"{cause_class}{cell_common.CAUSE_SEPARATOR}{detail}"
                if attempt.attempt == 1:
                    kept = report_path.with_name(report_path.name + ".attempt-1.stderr.log")
                    attempt.stderr_path.rename(kept)
                    print(f"{RETRYING_PREFIX} {name}{cell_common.CAUSE_SEPARATOR}{cause} "
                          f"(first attempt's log kept: {kept})", flush=True)
                    retry_log = report_path.with_name(report_path.name + ".attempt-2.stderr.log")
                    running[report_path] = start_attempt(attempt.command, report_path, 2, retry_log)
                else:
                    exit_text = "none" if attempt.process is None else str(code)
                    print(f"FAILED (exit {exit_text}): {name}{cell_common.CAUSE_SEPARATOR}"
                          f"{cause} (stderr kept: {attempt.stderr_path})", flush=True)
                    outcome.absent[name] = AbsentReport(
                        name, runtime_of(name), cause_class, detail, attempt.stderr_path)
            announce_agent_binary_down(cells_by_runtime, outcome)
        if running and time.monotonic() - last_target_check >= target_check_interval_seconds:
            last_target_check = time.monotonic()
            move = target_move()
            if move is not None:
                for report_path, attempt in running.items():
                    if attempt.process is not None:
                        stop_process_tree(attempt.process)
                    outcome.stopped.append(cell_name_of(report_path))
                    # Stopped cells never reach the post-model stray-write check; absence of results is not a clean check.
                    log_lines = (attempt.stderr_path.read_text(encoding="utf-8").splitlines()
                                 if attempt.stderr_path.is_file() else [])
                    lift_cell_status_lines(report_path, log_lines)
                    print(f"WRITE CHECK DID NOT RUN: {report_path.name} — {STOPPED_CELL_WRITE_CHECK_LINE}",
                          flush=True)
                return outcome._replace(moved_mid_run=move)
    return outcome


def tell_the_user_sentence(absent: dict) -> str:
    """Return user-actionable causes with their logs, or an empty string."""
    causes = {}
    for report in absent.values():
        if report.cause_class in cell_common.USER_CLEARABLE_CAUSE_CLASSES:
            causes[(report.runtime, report.cause_class)] = report
    if not causes:
        return ""
    return "Tell the user: " + "; ".join(
        f"{report.runtime} {report.cause_class}{cell_common.CAUSE_SEPARATOR}"
        f"{report.detail} (log: {report.log_path})"
        for report in causes.values()) + "."


def absence_lines(outcome: RunOutcome) -> str:
    """Return absence and agent-binary failure lines without repeating the Monitor prefix."""
    lines = [f"- {report.cell_name}: {report.cause_class}{cell_common.CAUSE_SEPARATOR}"
             f"{report.detail} (log: {report.log_path})"
             for report in outcome.absent.values()]
    lines += [f"- {runtime} is down: {cause_class}{cell_common.CAUSE_SEPARATOR}{detail}; "
              f"{count} reports absent"
              for runtime, (cause_class, detail, count) in outcome.down.items()]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--target", required=True, help="document path, relative to the repo root or absolute"
    )
    parser.add_argument(
        USER_RULED_COUNT_RESTART_FLAG, action="store_true",
        help=f"the user ruled, after this document's cold-read-full-run {FULL_RUN_LIMIT} "
             f"of {FULL_RUN_LIMIT}, to run again or to change the design; this run "
             f"starts the count again at 1")
    parser.add_argument(
        COUNT_SKIPPED_INSIDE_DESIGN_TO_MAIN_FLAG, action="store_true",
        help="this run is a writer's cold read inside design-to-main, whose own limit "
             "bounds it; the run is not counted, refused or counted later")
    args = parser.parse_args()

    target = pathlib.Path(args.target)
    if not target.is_absolute():
        target = REPO_ROOT / target
    if not target.is_file():
        print(f"cold-read-grid: target not found: {target}", file=sys.stderr)
        return 2
    # Reject before creating a record or launching reviewers.
    for genre_suffix in UNREVIEWABLE_TARGET_GENRE_SUFFIXES:
        if target.stem.endswith(genre_suffix):
            print(
                f"cold-read-grid: refusing {target.name} — its name ends in the "
                f"genre suffix `{genre_suffix}`, which marks a document that only "
                f"reports what happened. nedschorus#152 rules documents of that "
                f"genre out of the review path entirely. No reviewers were "
                f"launched and no record directory was created. If this document "
                f"should be cold-read, rename it out of the genre or amend "
                f"nedschorus#152 — do not work around this refusal.",
                file=sys.stderr,
            )
            return 2
    for runtime, launcher in CELL_LAUNCHERS.items():
        if not launcher.is_file():
            print(f"cold-read-grid: {runtime} cell launcher missing: {launcher}", file=sys.stderr)
            return 2

    user_ruled_count_restart = args.user_ruled_cold_read_full_run_count_restart
    count_skipped_inside_design_to_main = args.cold_read_full_run_count_skipped_inside_design_to_main
    if user_ruled_count_restart and count_skipped_inside_design_to_main:
        print(f"cold-read-grid: refusing to run with both {USER_RULED_COUNT_RESTART_FLAG} and "
              f"{COUNT_SKIPPED_INSIDE_DESIGN_TO_MAIN_FLAG}: the first restarts the count of "
              f"this document's cold-read-full-runs, the second keeps this run out of the "
              f"count. No reviewer was launched and no record directory was created.\n"
              f"Inside design-to-main, run again with {COUNT_SKIPPED_INSIDE_DESIGN_TO_MAIN_FLAG} "
              f"alone.\n"
              f"Outside design-to-main, after the user ruled to run again, run again with "
              f"{USER_RULED_COUNT_RESTART_FLAG} alone.", file=sys.stderr)
        return 2
    # Like shipping, counting needs ned-box, and a review must not wait on ned-box.
    count_unavailable = None
    earlier_runs = []
    stops_in_a_row = 0
    if not count_skipped_inside_design_to_main:
        try:
            earlier_runs, stops_in_a_row = earlier_full_runs_of(target)
        except FullRunCountUnavailable as error:
            count_unavailable = str(error)
    if user_ruled_count_restart:
        stops_in_a_row = 0
    if stops_in_a_row >= FROZEN_COPY_CHANGED_STOPS_IN_A_ROW_LIMIT:
        print(f"cold-read-grid: refusing a cold-read-full-run of {target.name}: its last "
              f"{stops_in_a_row} cold-read-full-runs in a row stopped because the frozen "
              f"copy changed during the run, which ends the attempt. No reviewer was "
              f"launched and no record directory was created.\n"
              f"Tell the user, and ask whether to stop, run again, or change the "
              f"document's design.\n"
              f"If the user rules to run again, run again with "
              f"{USER_RULED_COUNT_RESTART_FLAG}.\n"
              f"If the user rules to change the design, make the change first, then "
              f"run again with {USER_RULED_COUNT_RESTART_FLAG}.\n"
              f"If the user rules to stop, give the user the document to read as it "
              f"stands.", file=sys.stderr)
        return 2
    run_number = 1 if user_ruled_count_restart else len(earlier_runs) + 1
    if run_number > FULL_RUN_LIMIT:
        print(f"cold-read-grid: refusing cold-read-full-run {run_number} of "
              f"{target.name}: a change to a document gets at most {FULL_RUN_LIMIT} "
              f"before the user decides whether it gets more, and {len(earlier_runs)} "
              f"were made since origin/main last took a change to it: "
              f"{', '.join(earlier_runs)}. No reviewer was "
              f"launched and no record directory was created.\n"
              f"Bring the user the number of findings each of those runs' triage.md "
              f"in the log-store lists, and ask whether to stop, run again, or change "
              f"the document's design.\n"
              f"If the user rules to run again, run again with "
              f"{USER_RULED_COUNT_RESTART_FLAG}.\n"
              f"If the user rules to change the design, make the change first, then "
              f"run again with {USER_RULED_COUNT_RESTART_FLAG}.\n"
              f"If the user rules to stop, give the user the document to read as it "
              f"stands.", file=sys.stderr)
        return 2

    record_dir = make_record_dir(target, record_clock_reading())
    if user_ruled_count_restart:
        # The marker restarts the count for every later run of this document.
        (record_dir / USER_RULED_COUNT_RESTART_MARKER_NAME).write_text(
            "The user ruled to run this document's cold-read-full-runs again.\n",
            encoding="utf-8")
    if count_skipped_inside_design_to_main:
        # Written at the start, like the restart marker, so a run whose every cell failed is still left out.
        (record_dir / COUNT_SKIPPED_INSIDE_DESIGN_TO_MAIN_MARKER_NAME).write_text(
            "This cold-read-full-run ran inside design-to-main and is not counted.\n",
            encoding="utf-8")
    reference_integrity_pre_pass(target, record_dir)

    # All reviewers read the frozen bytes so live edits cannot split the review across versions.
    target_before = freeze_target(target, record_dir)
    frozen_target = record_names.frozen_target_path(target, record_dir)
    if not target_before or not frozen_target.is_file():
        print(f"cold-read-grid: could not freeze {target} into {frozen_target}; "
              f"no cold-read-cell was launched. The frozen copy is what the "
              f"reviewers read, so a run without it has no guarantee to offer. "
              f"The record directory {record_dir} was created before this and "
              f"holds the reference check alone; delete it or leave it.",
              file=sys.stderr)
        return 2
    # Freezing can fail, so announce launch only after the copy succeeds.
    if count_skipped_inside_design_to_main:
        print(f"cold-read-full-run count skipped for {target.name}: this run is inside design-to-main.")
    elif count_unavailable is None:
        print(f"cold-read-full-run {run_number} of {FULL_RUN_LIMIT} for {target.name}.")
    else:
        print(f"EARLIER COLD-READ-FULL-RUNS NOT COUNTED: this run went ahead without "
              f"counting the earlier cold-read-full-runs of {target.name}: "
              f"{count_unavailable}\n"
              f"Tell the user what this line says.")
    print(f"Launched six reviewers against {target}. Reports appear in "
          f"{record_dir} as each completes — read each as it arrives.")

    outcome = wait_for_cells(
        launch_cells(frozen_target, record_dir, target),
        lambda: moved_frozen_copy(frozen_target, target_before),
        float(os.environ.get(TARGET_CHECK_INTERVAL_OVERRIDE_VARIABLE) or 0),
        float(os.environ.get(CELL_POLL_INTERVAL_OVERRIDE_VARIABLE)
              or CELL_POLL_INTERVAL_DEFAULT_SECONDS))
    # Retain the poll result if the changed bytes were restored before the final comparison.
    move = moved_frozen_copy(frozen_target, target_before) or outcome.moved_mid_run
    target_changed = move is not None
    if target_changed:
        changed_path, changed_after = move
        detail = mark_reports_target_changed(
            record_dir, changed_path, target_before, changed_after,
            seen_mid_run=outcome.moved_mid_run is not None)
        print(f"{FROZEN_COPY_CHANGED_HASHTAG} {detail}", flush=True)
        # Written before shipping, so the stop is in the record every later count reads.
        (record_dir / FROZEN_COPY_CHANGED_STOP_MARKER_NAME).write_text(
            "This cold-read-full-run stopped because its frozen copy changed; it is not counted.\n",
            encoding="utf-8")
    original_line = original_changed_line(target, frozen_target, target_before,
                                          target_changed)
    if original_line:
        print(original_line, flush=True)

    launched = len(CELL_LAUNCHERS) * len(GRID_CELL_ROSTER)
    if outcome.absent:
        # Keep target-changed first, and add all markers before shipping: the store refuses changed bytes.
        mark_every_report(record_dir, incomplete_set_marker(outcome.absent, launched))

    print(f"record: {ship_record(record_dir)}", flush=True)

    print()
    tell = tell_the_user_sentence(outcome.absent)
    absences = absence_lines(outcome)
    if target_changed:
        print(TARGET_CHANGED_INSTRUCTIONS.format(
            record_dir=record_dir,
            window=WINDOW_SEEN_MID_RUN if outcome.moved_mid_run else WINDOW_SEEN_AT_END))
        print(frozen_copy_stop_count_line(stops_in_a_row + 1))
        if outcome.stopped:
            print("Stopped before finishing: " + ", ".join(outcome.stopped) + ".")
        if absences:
            print(absences)
    elif not outcome.absent:
        print(ALL_LANDED_OPENING.format(record_dir=record_dir))
        print()
        print(COMPLETION_BODY.format(record_dir=record_dir, read_until="all six",
                                     record_absences=""))
    elif outcome.landed:
        print(SOME_LANDED_OPENING.format(landed=len(outcome.landed), launched=launched,
                                         record_dir=record_dir))
        print(absences)
        print()
        print(COMPLETION_BODY.format(record_dir=record_dir,
                                     read_until="every report that landed",
                                     record_absences=" " + RECORD_ABSENCES_SENTENCE))
    else:
        print(NONE_LANDED_OPENING.format(record_dir=record_dir))
        print(absences)
        print(NONE_LANDED_CLOSING)
    if tell:
        print(tell)
    # A changed target invalidates the review; missing reports only make the review incomplete.
    if target_changed:
        return 3
    return 1 if outcome.absent else 0

if __name__ == "__main__":
    sys.exit(main())
