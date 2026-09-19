#!/usr/bin/env python3
"""Run a cold-read-full-run against a cold-read-target.

One invocation = one review: six cold-read-cells launched in parallel -- the
defect-hunt pass in four ({good, floor} x {claude, codex}) and the
terminology pass in two (good x {claude, codex}) -- every report saved
into a cold-read-record named
`cold-read-records/<file stem>-<YYYY-MM-DD>/`, or `SKILL-<skill name>-<YYYY-MM-DD>/` for a skill
(a -2, -3 suffix for a second read of the document that day), progress and next-step
instructions printed for the reviewing agent as reviews land.

Usage:
  scripts/cold-read-grid.py --target docs/drafts/foo.md

The cold-read-record holds one report per cold-read-cell, the reference-check
file, and under target/ the exact bytes reviewed at the cold-read-target's own
repository path (frozen at launch, the same read that fingerprints it). At the
end of the run the cold-read-record is shipped to the log-store on ned-box by
scripts/cold-read-record-ship.py, whatever the run's outcome, and the shipper's
one line is printed as `record:`; a shipping failure is reported, never fatal
(user-ruled 2026-09-07).

WHEN A COLD-READ-CELL FAILS (nedschorus#413; the design, user-reviewed
2026-09-16 and 2026-09-17, is
docs/issues/413-cold-read-grid-cell-failure-handling-design.md). Every
cold-read-cell whose attempt ends without a landed report is retried once,
at once, with the same model -- no cold-read-cell is special (user-ruled
2026-09-11) -- and the first attempt's log is kept as
`<report file name>.attempt-1.stderr.log`. Each failed attempt is reported
with its CAUSE, the `cause:` line the cold-read-cell program prints
(scripts/cold-read-cell-common.py, classify_failed_attempt) or, when it left
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

Exit codes: 0 all cold-read-cells ran, 1 one or more reports are absent, 2
bad invocation (including a cold-read-target this instrument refuses to
review), 3 the cold-read-target changed while the cold-read-cells were
running, so every report in the set describes a document that no longer
exists in the form reviewed.
"""

import argparse
import datetime
import hashlib
import importlib.util
import os
import pathlib
import re
import subprocess
import sys
import time
import typing

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
RECORDS_DIR = REPO_ROOT / "cold-read-records"
# cold-read-cell launchers, one per runtime.
CELL_LAUNCHERS = {
    "claude": REPO_ROOT / "scripts" / "cold-read-claude-cell.py",
    "codex": REPO_ROOT / "scripts" / "cold-read-codex-cell.py",
}
# The program that copies a finished cold-read-record to the log-store on
# ned-box (user-ruled 2026-09-07: cold-read-records are logs, not system, and
# never enter git). Run at the end of every cold-read-full-run, whatever the
# outcome; its one line is printed and the run goes on, because a store that
# cannot be reached is no reason to lose a review that landed.
RECORD_SHIPPER = REPO_ROOT / "scripts" / "cold-read-record-ship.py"
# Where the cold-read-target's bytes are frozen inside the cold-read-record:
# under this name, at the cold-read-target's own repository path, so a
# reader of an old cold-read-record sees both the exact text reviewed
# and where it lived.
FROZEN_TARGET_DIRECTORY_NAME = "target"
# The cold-read-cells' shared module, loaded the way the cold-read-cells
# load it, for the status phrases it pins. Imported rather than copied so
# the cold-read-grid and the cold-read-cells cannot drift on the words the
# cold-read-grid lifts out of a cold-read-cell's log.
_common_spec = importlib.util.spec_from_file_location(
    "cold_read_cell_common", pathlib.Path(__file__).with_name("cold-read-cell-common.py")
)
cell_common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(cell_common)
# The name each cold-read-cell program prints at the head of every line that is
# its own -- the PROGRAM constant in each launcher, which equals the launcher's
# filename stem. A cold-read-cell's log also carries its runtime's stderr,
# re-emitted whole, and the Codex CLI writes the model's text there; a line
# that does not begin with one of these names is the model's, or the runtime's,
# not the cold-read-cell's.
CELL_PROGRAM_NAMES = tuple(path.stem for path in CELL_LAUNCHERS.values())
# THE ROSTER: one entry per (pass, tier) the cold-read-grid launches on EACH
# runtime, with the effort the cold-read-grid pins for it -- None leaves the
# effort to the launcher's own tier map. Six cold-read-cells in all.
#
# The restate pass was cut 2026-08-30 (user-ruled that day). Measured on both
# labelled 2026-08-26 targets: mining several readers' restatements for
# disagreement located no defect the defect hunt had not already located, so
# its four cold-read-cells bought reading time and nothing the triage could
# use. A restatement is still an author's tool -- the restate cold-read-cell
# and its prompt remain invocable singly through the cold-read-cell launchers;
# what is cut is only this default roster.
#
# The terminology pass was added 2026-09-05 (user-ruled that day): the
# cold-read-target's key-terms against five criteria, on the good
# cold-read-tier of both runtimes only, at max effort on both. Measured
# on the final prompt by the cold-read-research seat (REPORT.md under
# ~/agents/cold-read-research/cold-read-records/2026-09-03-cold-read-tier-roster-campaign/,
# section "Addendum 2026-09-04 late"; on that machine only and not committed,
# which is why the numbers are inline here): opus-max flagged 20/15/28
# key-terms on three targets and sol-max 44/41/49; no cheaper cold-read-cell
# added a criterion-1 catch, so no floor cold-read-cell runs for this pass;
# wall clock 16-20 min per cold-read-cell, inside the defect-hunt strong
# cold-read-cells' 18-23. The effort is passed to the launchers explicitly
# rather than left to their tier maps, which happen to pin max for the good
# cold-read-tier today: a later change to either map would otherwise move this
# pass silently. The defect-hunt cold-read-cells carry no override, so their
# pins stay the launchers' own.
GRID_CELL_ROSTER = (
    ("defect-hunt", "good", None),
    ("defect-hunt", "floor", None),
    ("terminology", "good", "max"),
)

# Documents this instrument refuses to review, keyed on the genre suffix its
# filename stem ends in (nedschorus#152). A `-log`, `-report` or `-capture`
# only records what happened; there is nothing in it for a cold read to
# improve, and the ruling stamps such files carry are content rather than
# defects. ONE list, here, because the rule is one rule: a second copy
# somewhere else is how two instruments come to disagree about what a genre
# is. The refusal is announced rather than silent -- nedschorus#152's own
# reasoning: "A suffix list can miss a genre nobody anticipated; announcing
# the skip is what makes that visible instead of silent." A miss is then a
# document someone can see was reviewed, not one that vanished.
UNREVIEWABLE_TARGET_GENRE_SUFFIXES = ("-log", "-report", "-capture")

# Prepended to every report in a set whose cold-read-target changed under
# it. Read by people and by whatever reads these cold-read-records next; the
# reports are KEPT -- they are evidence of what a reviewer saw -- but nothing
# downstream should read them as a review of the file as it now stands.
TARGET_CHANGED_MARKER_PREFIX = "<!-- TARGET CHANGED DURING RUN:"
# Prepended likewise to every .md file of a set with an absent report
# (user-ruled 2026-09-11, point 5: "a marker line naming the absent cells and
# their errors goes at the top of every report in the record directory, so a
# later reader of the record sees what was not looked at"). When the
# cold-read-target also changed, that marker goes first.
INCOMPLETE_SET_MARKER_PREFIX = "<!-- INCOMPLETE SET:"
GRID_MARKER_PREFIXES = (TARGET_CHANGED_MARKER_PREFIX, INCOMPLETE_SET_MARKER_PREFIX)

# The lines the cold-read-grid prints as a cold-read-cell fails, in the
# forms the cold-read skill's Monitor watches for. A FAILED line keeps its
# `FAILED (exit` opening, the one marker carrying no colon.
RETRYING_PREFIX = "RETRYING:"
AGENT_BINARY_DOWN_PREFIX = "AGENT-BINARY DOWN:"

# ONE CLOSING TEXT FOR EVERY RUN (user-ruled 2026-09-11, point 3, replacing
# the Opus-absent and Fable-only branches of 2026-09-04: "why is opus
# special? I don't think it should be."), in four variants built from what
# landed. Point 4: "A report set missing a cell after its retry is VALID AND
# INCOMPLETE. The run is not void." -- the reports that landed are triaged as
# the review that was asked for; only a changed cold-read-target makes a set
# not valid.
ALL_LANDED_OPENING = "All six reports landed in {record_dir}, one file per reviewer."
SOME_LANDED_OPENING = (
    "{landed} of {launched} reports landed in {record_dir}. The set is valid "
    "and incomplete: triage the reports that landed.")
NONE_LANDED_OPENING = "No report landed in {record_dir}, so there is nothing to triage."
NONE_LANDED_CLOSING = (
    "Start a new cold-read-full-run once the causes above that the user can "
    "clear are cleared, or at once if none of them is.")
# The record's triage file is triage.md since 2026-09-18 (walk
# docs/walk/cold-read-and-walk-file-names-and-dispositions, item 3); the
# ruling of 2026-09-11 named it by the name it had then, dispositions.md.
RECORD_ABSENCES_SENTENCE = "Record each absent report and its cause in triage.md."

COMPLETION_BODY = """\
Read every report in full. The defect-hunt reports flag defects with each
reviewer's own confidence; expect heavy overlap — the same defect found
independently by several reviewers is one defect. The terminology reports
list the document's key-terms that fail one of five criteria, with the
criteria numbers per item and a closing counts line; triage them the same
way as the defect-hunt reports.

Keep your judgments provisional until you have read {read_until}, as later
reports may offer more insight than earlier ones. Then formulate your draft
response: which problems are real, and what you propose to do about each.
Walk that with the user using the walk-me-through skill, ordered from most
important to least.{record_absences}

This record was shipped to the log-store on ned-box when the run ended (the
`record:` line above says whether it arrived); once triage.md is written,
run `scripts/cold-read-record-ship.py {record_dir}` so it joins the reports
there. cold-read-records/ stays gitignored: never commit it. Leave {record_dir}
in place once the work it served has landed — these records are kept, not
deleted: like other logs they are useful for analysis later (user-ruled
2026-08-25). The findings still belong in the reviewed document and the
rulings in its governing document; this directory is what produced them, not
where they live."""


# THE RECORD-NAME RULE (user-ruled 2026-09-18, walk
# docs/walk/cold-read-and-walk-file-names-and-dispositions, item 4):
# `<file stem>-<YYYY-MM-DD>`, and `SKILL-<skill name>-<YYYY-MM-DD>` for a
# skill, whose stem is always SKILL and whose name is its directory's; a
# second read of one document on one day takes -2, -3. The document comes
# first so every read of one document sits together in the log-store's
# listing, and the date is all the time a reader needs. It replaced
# `<YYYY-MM-DD>-<HHMM>-<parent directory>-<file stem>` (ruled 2026-09-16),
# and knowingly gives up what that form bought: two documents with the same
# stem in different directories read on one day come out as -2 of each other
# (the record's target/ shows which was which), and the -N count says nothing
# about which draft each read was. Both accepted at the walk, since the name
# is now shared with the walk that rules on the read (item 6) and has to be
# short enough to type. Restated, not imported, in
# scripts/cold-read-fast-read.py, because the cold-read-grid is a program
# rather than a module; the two must stay identical. The files inside the
# record carry none of this name (item 5): the directory says which read, the
# file says which agent ran which attack.
RECORD_CLOCK_OVERRIDE_VARIABLE = "COLD_READ_RECORD_CLOCK_OVERRIDE"
RECORD_CLOCK_OVERRIDE_FORMAT = "%Y-%m-%dT%H:%M"


def record_clock_reading() -> datetime.datetime:
    """The ONE local clock reading a cold-read-record's date and time are both
    taken from, so the two cannot disagree across midnight.

    COLD_READ_RECORD_CLOCK_OVERRIDE, when set as `YYYY-MM-DDTHH:MM`, is read
    instead of the clock: it is how the test suites name a cold-read-record
    exactly without depending on the wall clock or flaking across a minute
    boundary.
    The override is a clock value, not a finished name, so the tests still go
    through the formatting below.
    """
    override = os.environ.get(RECORD_CLOCK_OVERRIDE_VARIABLE)
    if override:
        return datetime.datetime.strptime(override, RECORD_CLOCK_OVERRIDE_FORMAT)
    return datetime.datetime.now()


def record_name_for_target(target: pathlib.Path) -> str:
    """The cold-read-target's part of a cold-read-record name: its file stem,
    except that a file whose stem is exactly `SKILL` -- every skill in this
    project is `.claude/skills/<name>/SKILL.md` -- is `SKILL-<skill name>`,
    the name being its directory's."""
    if target.stem == "SKILL" and target.parent.name:
        return f"SKILL-{target.parent.name}"
    return target.stem


def record_directory_name_for_target(
    target: pathlib.Path, now: datetime.datetime,
) -> str:
    """`<document part>-<YYYY-MM-DD>`, before any -2, -3 suffix. Only the
    date of the clock reading is used."""
    return f"{record_name_for_target(target)}-{now.strftime('%Y-%m-%d')}"


def make_record_dir(target: pathlib.Path, now: datetime.datetime) -> pathlib.Path:
    """Create and return the record directory: the day's name, or the
    first of -2, -3, ... that is not taken (a second read of the document
    that day)."""
    base = record_directory_name_for_target(target, now)
    record_dir = RECORDS_DIR / base
    suffix = 2
    while record_dir.exists():
        record_dir = RECORDS_DIR / f"{base}-{suffix}"
        suffix += 1
    record_dir.mkdir(parents=True)
    return record_dir


def reference_integrity_pre_pass(target: pathlib.Path, record_dir: pathlib.Path) -> None:
    """Cheap grounding check: every path-like reference in the cold-read-target
    either resolves (relative to the repo root or the cold-read-target's
    directory) or is listed as unresolved. Result saved into the
    cold-read-record for the reviewing agent; unresolved references are leads,
    not verdicts."""
    text = target.read_text(encoding="utf-8")
    candidates = sorted(set(re.findall(
        r"[\w./-]+/[\w./-]+|[\w-]+\.(?:md|py|sh|json|yaml|toml)", text)))
    lines = ["# Reference-integrity pre-pass", ""]
    for candidate in candidates:
        # Trailing only: a leading dot is part of the path, not
        # punctuation. Stripping both ends turned every `.claude/...`
        # reference into an unresolvable one, which is most of the
        # instruction files this check exists to ground.
        clean = candidate.rstrip(".,;:")
        resolved = (REPO_ROOT / clean).exists() or (target.parent / clean).exists()
        lines.append(f"- {'ok' if resolved else 'UNRESOLVED'}: `{clean}`")
    if not candidates:
        lines.append("- no path-like references found")
    (record_dir / "reference-check.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")


def frozen_target_path(target: pathlib.Path, record_dir: pathlib.Path) -> pathlib.Path:
    """record_dir/target/<repository path>; a cold-read-target outside the
    repository keeps its absolute path minus the leading slash, so nothing
    collides and the path still says where the file was."""
    try:
        relative = target.resolve().relative_to(REPO_ROOT)
    except ValueError:
        relative = pathlib.Path(*target.resolve().parts[1:])
    return record_dir / FROZEN_TARGET_DIRECTORY_NAME / relative


def freeze_target(target: pathlib.Path, record_dir: pathlib.Path) -> str:
    """Copy the cold-read-target's bytes into the cold-read-record and return
    their sha256.

    One read serves both, so the frozen copy and the fingerprint the
    cold-read-grid compares at the end of the run describe the same bytes by
    construction (user-ruled 2026-09-07: freeze the reviewed cold-read-target
    into each cold-read-record; the hash alone left a reader of an old
    cold-read-record with reports but not the text they reviewed). ""
    when the file cannot be read, as the fingerprint function returns, and
    then nothing is frozen.
    """
    try:
        content = target.read_bytes()
    except OSError:
        return ""
    frozen = frozen_target_path(target, record_dir)
    frozen.parent.mkdir(parents=True, exist_ok=True)
    frozen.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def ship_record(record_dir: pathlib.Path) -> str:
    """Run the shipper on the cold-read-record and return its one line, or a
    FAILED line of this program's own when the shipper could not run. Never
    raises: the shipper's outcome is reported, not enforced."""
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
    """The cold-read-target's bytes, hashed. "" when the file cannot be read at all.

    mtime moves whenever the file is written, so an editor that saves and
    undoes would trip an mtime guard with nothing wrong. The guard exists so
    no report describes bytes that are not the document's. It compares only
    the two endpoints, so an edit made and undone between them leaves no
    trace, and a cell that read the edited version is not flagged. A file
    deleted or made unreadable mid-run yields "", which differs from any real
    digest and so counts as a change.

    `path_content_fingerprint` in scripts/cold-read-cell-common.py is the same
    idea applied to every path in the working tree, and the name here echoes
    it deliberately. The two stay separate because the cold-read-grid launches
    the cold-read-cell scripts as programs and never loads that module, and
    because they answer different questions about an unreadable path: the
    detector distinguishes absent from unreadable from a directory, since
    it must tell a creation from a deletion, while one cold-read-target that
    cannot be read is simply not the document that was fingerprinted at launch.
    """
    try:
        return hashlib.sha256(target.read_bytes()).hexdigest()
    except OSError:
        return ""


TARGET_CHANGED_INSTRUCTIONS = """\
The reports are in {record_dir}, and every one of them is marked: the document's
bytes differed between the moment the cells launched and the moment the last one
finished, so which text any one report describes is unknown.

Do not triage this set as a review of the document. Stop editing the document
and start a new cold-read run against the settled text.

Keep the set. Each report still records truthfully what one reviewer read, which
is evidence of what the reviewers saw — not of how the file now stands.
"""


def mark_reports_target_changed(
    record_dir: pathlib.Path, target: pathlib.Path, before: str, after: str,
) -> str:
    """Stamp every report in the set as reviewing a cold-read-target that moved.

    WHAT HAPPENED (2026-08-24). The merge-lane seat had to mark a whole record
    set COMPROMISED because the cold-read-target was edited while the
    cold-read-cells ran. The tell was subtle and nearly missed: a clean-looking
    report whose "clean sections" list simply omitted the sections that had
    changed underneath it. Nothing in the cold-read-record said the file had
    moved, so the only way to catch it was to notice an absence.

    The reports are marked, never deleted: each still records truthfully what
    one reviewer read, which is evidence. What the marker removes is the
    possibility of reading them as a review of the file as it now stands.
    """
    # WHAT THE TWO FINGERPRINTS PROVE, and no more: the bytes differed between
    # the moment before the cold-read-cells launched and the moment after
    # the last one finished. They do not say when in that window the edit
    # landed, so they cannot say that it landed while a reviewer was reading,
    # nor which text any one report describes — the ordinary case is an edit
    # part-way through, with some cold-read-cells having opened the file before
    # it and some after. The marker is the durable half of this check: these
    # cold-read-records are kept, so a sentence claiming more than the check
    # knows would outlive the run.
    detail = (
        f"{target}'s bytes differed between the moment the cells launched and the "
        f"moment the last one finished — sha256 {before[:12] or 'unreadable'} then "
        f"{after[:12] or 'unreadable'}. Which text any one report in this directory "
        f"describes is unknown: the edit may have landed before a given reviewer "
        f"opened the file or after. Treat this set as evidence of what reviewers "
        f"saw, not as a review of the current file; start a new cold-read run "
        f"against the settled document."
    )
    mark_every_report(record_dir, f"{TARGET_CHANGED_MARKER_PREFIX} {detail} -->")
    return detail


def mark_every_report(record_dir: pathlib.Path, marker: str) -> None:
    """One marker line into every .md file of the set: the reports that
    landed and the reference-check file. After the provenance stamp when
    there is one, so the stamp stays the first line every reader and parser
    of these cold-read-records expects, and after any marker already there,
    so the target-changed marker written first stays first; at the top
    otherwise (the reference-integrity pre-pass carries no stamp)."""
    for report_path in sorted(record_dir.glob("*.md")):
        lines = report_path.read_text(encoding="utf-8").split("\n")
        insert_at = 1 if lines and lines[0].startswith("<!-- provenance:") else 0
        while insert_at < len(lines) and lines[insert_at].startswith(GRID_MARKER_PREFIXES):
            insert_at += 1
        lines.insert(insert_at, marker)
        report_path.write_text("\n".join(lines), encoding="utf-8")


def incomplete_set_marker(absent: dict, launched: int) -> str:
    """`<!-- INCOMPLETE SET: 2 of 6 reports absent — claude-hunt-good
    (account-limit — resets 8:50pm (America/Los_Angeles)), ... -->`."""
    named = ", ".join(f"{report.cell_name} ({report.cause_class}"
                      f"{cell_common.CAUSE_SEPARATOR}{report.detail})"
                      for report in absent.values())
    return (f"{INCOMPLETE_SET_MARKER_PREFIX} {len(absent)} of {launched} reports "
            f"absent{cell_common.CAUSE_SEPARATOR}{named} -->")


def cell_report_path(
    record_dir: pathlib.Path, runtime: str, cell_pass: str, tier: str,
) -> pathlib.Path:
    """Where one cold-read-cell's report goes: `<record dir>/<runtime>-<pass token>-<tier>.md`.

    THE FILE SAYS WHICH AGENT RAN WHICH ATTACK, AND NOTHING ELSE (user-ruled
    2026-09-18, walk docs/walk/cold-read-and-walk-file-names-and-dispositions,
    item 5); the directory says which read. From 2026-09-15 to 2026-09-18
    every file carried the record's name as a prefix, added on 2026-08-25
    because two cold-read-full-runs going at once in one checkout each held a
    `codex-hunt-floor.md`, and a cold-read-cell of the first run that wrote
    nothing could have the second run's correctly placed report recovered as
    its own. That case is now met where it arises, in the cold-read-cell's
    near-miss recovery (scripts/cold-read-cell-common.py,
    recover_near_miss_report), which never takes a file from a directory the
    instrument built. THE GAP THAT LEAVES, seen and left open (user-ruled
    2026-09-18, walk docs/walk/skill-sentences-and-shipper-questions-2026-09-18,
    item 6, no guard): a same-day second read is the `-2` record, and a
    cold-read-cell of that read that drops the `-2` -- the one-character kind
    of miss of 2026-08-25 -- writes its report into the first read's directory
    under the first read's own file name, where the first read stamps it as
    its own and neither read can tell, because the file name no longer says
    which read it belongs to. No such drop has been seen; if a `-2` read's
    report ever goes missing, look in the first read's directory.

    The pass token is the cell name, except that defect-hunt is `hunt` --
    the token every record set since 2026-08-25 has carried. One function
    composes the name, and the cold-read-grid names a cold-read-cell on its
    RETRYING, FAILED and closing lines by that file name's stem.
    """
    pass_token = "hunt" if cell_pass == "defect-hunt" else cell_pass
    return record_dir / f"{runtime}-{pass_token}-{tier}.md"


class CellAttempt(typing.NamedTuple):
    """One launch of a cold-read-cell program. `process` is None when the
    program could not be started at all, and `start_error` then holds the
    OSError's text, which is also the attempt's log's only content."""

    report_path: pathlib.Path
    command: list
    attempt: int
    process: typing.Optional[subprocess.Popen]
    stderr_path: pathlib.Path
    start_error: str


class AbsentReport(typing.NamedTuple):
    """A cold-read-cell whose retry also ended without a landed report, with
    the second attempt's cause and the log it came from."""

    cell_name: str
    runtime: str
    cause_class: str
    detail: str
    log_path: pathlib.Path


class RunOutcome(typing.NamedTuple):
    """What the cold-read-cells left: the cell names that landed, in order;
    the absent reports by cell name, in the order they became absent; and
    per agent-binary that went down, (cause class, detail, reports absent)."""

    landed: list
    absent: dict
    down: dict


def cell_name_of(report_path: pathlib.Path) -> str:
    """`claude-hunt-good` from `.../claude-hunt-good.md`: the agent-binary, pass
    token and tier the report's file name is, which is how the grid's own
    lines name a cold-read-cell."""
    return report_path.stem


def runtime_of(cell_name: str) -> str:
    return cell_name.split("-", 1)[0]


def start_attempt(command: list, report_path: pathlib.Path, attempt: int,
                  stderr_path: pathlib.Path) -> CellAttempt:
    """Launch one attempt of a cold-read-cell program, its stdout and stderr
    into `stderr_path`. A program the cold-read-grid cannot start -- Popen
    raising, as for a launcher that lost its execute permission -- is a
    failed attempt like any other (user-ruled 2026-09-16, the design's
    section 3): the error is written to the attempt's log as its only content
    and the attempt is returned with no process, so the retry runs.
    The parent's handle is closed right after the spawn; the child keeps its
    own copy."""
    with open(stderr_path, "w", encoding="utf-8") as err:
        try:
            process = subprocess.Popen(  # pylint: disable=consider-using-with
                command, stdout=err, stderr=err, stdin=subprocess.DEVNULL,
            )
        except OSError as error:
            err.write(f"cold-read-grid: could not start {command[0]}: {error}\n")
            return CellAttempt(report_path, command, attempt, None, stderr_path, str(error))
    return CellAttempt(report_path, command, attempt, process, stderr_path, "")


def launch_cells(target: pathlib.Path, record_dir: pathlib.Path) -> dict:
    """Start all six cold-read-cells in parallel, each on its first attempt.
    Returns {report_path: CellAttempt}."""
    running = {}
    for runtime, launcher in CELL_LAUNCHERS.items():
        for cell_pass, tier, effort in GRID_CELL_ROSTER:
            report_path = cell_report_path(record_dir, runtime, cell_pass, tier)
            stderr_path = record_dir / (report_path.name + ".stderr.log")
            command = [str(launcher), "--cell", cell_pass, "--tier", tier,
                       "--target", str(target), "--report", str(report_path)]
            # A roster effort is the cold-read-grid's pin for that
            # cold-read-cell, passed on the command line where the launcher
            # honors it exactly, with no fallback to its tier map.
            if effort:
                command += ["--effort", effort]
            # The reviewer writes the report itself; the cold-read-cell is told
            # where. Capturing the model's chat text was what lost
            # findings written before a tool call (measured 2026-08-23),
            # so nothing here redirects stdout into the report any more.
            running[report_path] = start_attempt(command, report_path, 1, stderr_path)
    return running


def cell_status_line(line: str, phrase: str) -> bool:
    """True when `line` is a cold-read-cell program's own status line carrying `phrase`.

    The cold-read-cell writes every line of its own as `<program>: <sentence>`,
    and the phrases the cold-read-grid lifts each open that sentence, so the
    test is that the line begins with a cold-read-cell program's name, a colon,
    a space, and the phrase.
    Anything else in the log -- the runtime's stderr, the model's echoed text
    -- fails it however many times the phrase appears inside (nedschorus#244).
    """
    stripped = line.strip()
    return any(stripped.startswith(f"{program}: {phrase}")
               for program in CELL_PROGRAM_NAMES)


def lift_cell_status_lines(report_path: pathlib.Path, log_lines: list) -> None:
    """Carry the cold-read-cell's own status lines onto the cold-read-grid's
    output, which is what the reviewing agent reads.

    THREE THINGS EXIST ONLY IN THE LOG, and the landed path deletes it -- so
    without lifting them out first, the one path where each is produced is
    the path where it is destroyed. A failed first attempt's log is renamed
    rather than deleted, but its stray-write lines are lifted too: the retry
    takes its own baseline after the first attempt's write, so a stray write
    by a failed first attempt would otherwise never be reported.

    WHAT THE STRAY-WRITE CHECK FOUND, and whether it ran at all. A stray
    edit is ordinary cleanup for that agent, not something to escalate. A
    cold-read-cell whose `git status` could not answer -- an index.lock held
    by another agent in the same checkout is the ordinary way, and the
    cold-read-cell says in as many words that this is a failure to look, not
    a clean result -- was otherwise reported here exactly like a
    cold-read-cell that looked and found nothing, and a whole
    cold-read-full-run read as clean when nothing had been checked at all
    (nedschorus#167).

    EACH IS MATCHED ONLY ON A LINE THE COLD-READ-CELL ITSELF BEGAN. The
    cold-read-cell re-emits its runtime's stderr into this same log, and the
    Codex CLI writes the model's text there -- so on 2026-09-02 a
    cold-read-target that quoted a code comment containing "fell back to"
    made two cold-read-cells read as fallen back when both had run on the
    models asked for (nedschorus#244). A bare substring test cannot tell the
    cold-read-cell's sentence from the model's; the program prefix can. The
    phrases come from the cold-read-cell module, where each is pinned as a
    contract with this loop.

    A FALLBACK IS NEVER SILENT (user-ruled 2026-08-25: "I'm ok with the
    fable falling back to opus too. I just don't want it to fail silently").
    The cold-read-cell's own line names the model that produced the report
    and every model that failed ahead of it; since 2026-09-04 every pinned
    chain has one model, so this line is lifted for a chain a ruling may pin
    later and for nothing that runs today. A RECOVERY IS NEVER SILENT EITHER
    (user-ruled 2026-08-25): the cold-read-cell was one character from losing
    a finished 33-finding review that day, and a run that nearly lost its
    work should say so where the reviewing agent reads.
    """
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
    """(class, detail) of an attempt that produced no report.

    The cold-read-cell program names its own cause: the LAST `cause:` line of
    its own in the log, because model text echoed earlier in the log could
    hold a quoted one. When the log holds none, the cold-read-grid names the
    cause from what it sees: `program-unstartable` when no program ran,
    `no-report` for an exit of 0 with no landed report, and otherwise
    `exit-N` with the log's last non-empty line as the detail.
    """
    if attempt.process is None:
        return "program-unstartable", attempt.start_error
    cause_lines = [line.strip() for line in log_lines
                   if cell_status_line(line, cell_common.CAUSE_PHRASE)]
    if cause_lines:
        text = cause_lines[-1].split(f": {cell_common.CAUSE_PHRASE} ", 1)[1]
        # The separator without its trailing space: a cause line with an
        # empty detail (`cause: account-limit — `, the agent-binary having
        # printed its limit text with nothing after it) lost that space to
        # strip() above, and partitioning on the full separator then left the
        # class as "account-limit —", which matched no class the grid knows.
        cause_class, _, detail = text.partition(cell_common.CAUSE_SEPARATOR.rstrip())
        return cause_class, detail.strip()
    if exit_code == 0:
        return "no-report", "no report written"
    non_empty = [line.strip() for line in log_lines if line.strip()]
    detail = (non_empty[-1][:cell_common.CAUSE_DETAIL_MAX_CHARACTERS]
              if non_empty else "no output")
    return f"exit-{exit_code}", detail


def announce_agent_binary_down(cells_by_runtime: dict, outcome: RunOutcome) -> None:
    """Print AGENT-BINARY DOWN once per agent-binary, when its condition is met
    (user's direction 2026-09-14: "If opus is down, claude is down, so that
    should be reported"; the design's section 5, as the user revised it on
    2026-09-16): a cold-read-cell is absent with an agent-binary-wide class,
    and every other cold-read-cell of that agent-binary has landed or is absent
    with the same class. The detail is that of the last to become absent.
    A model limit is not the agent-binary being down, and absent reports with
    different or unrecognised causes are three facts the cold-read-grid
    cannot join into one; both are listed one by one in the closing text."""
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


def wait_for_cells(running: dict) -> RunOutcome:
    """Poll until every cold-read-cell has landed or is absent; print per-report
    progress; relaunch each cold-read-cell once when its first attempt fails.

    RETRY ONCE, HERE (user-ruled 2026-09-11, point 1: "Every failed cell is
    retried once, automatically, with the SAME model. No cell is special.").
    The cold-read-grid is what sees the first failure and can report it, and
    one relaunch here covers both agent-binaries and every attempt that ends with
    the program exiting or never starting. The same command, at once, while
    the other cold-read-cells keep running; exit 64 too, since a refused
    relaunch costs seconds; a cause a retry cannot fix too, because
    suppressing the retry would let the cause decide what the grid does. The
    first attempt's log is renamed `.attempt-1.stderr.log` and kept, since it
    records a failure that happened; the retry writes `.attempt-2.stderr.log`,
    deleted when the retry lands as any landed report's log is. A retry that
    fails makes the report ABSENT, with the second attempt's cause (point 2:
    "A cell that fails twice is reported absent at the moment of its second
    failure, with its exit code and the tail of its error").

    A COLD-READ-CELL'S EXIT CODE IS NOT ON ITS OWN EVIDENCE that a review
    happened: the report is (nedschorus#164). The cold-read-cell enforces the
    same rule, and the cold-read-grid checks again rather than trusting it,
    because the cold-read-grid is what tells the reviewing agent what to
    believe -- six "saved" lines over empty files read as six reviewers
    finding nothing.
    """
    outcome = RunOutcome([], {}, {})
    cells_by_runtime = {}
    for report_path in running:
        cells_by_runtime.setdefault(
            runtime_of(cell_name_of(report_path)), []).append(cell_name_of(report_path))
    while running:
        time.sleep(5)
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
    return outcome


def tell_the_user_sentence(absent: dict) -> str:
    """"Tell the user: <causes>." when any absent report's cause is one the
    user can clear, else "". One cause per agent-binary and class, taking the
    detail and log of the last of them to become absent; each carries the
    path of the kept log it came from, because a cause read from text can
    mislead and the user can check it (the design's section 2)."""
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
    """The absent reports one per line, then each agent-binary that is down,
    restated without the AGENT-BINARY DOWN: prefix so the skill's Monitor sees
    that line once."""
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
    args = parser.parse_args()

    target = pathlib.Path(args.target)
    if not target.is_absolute():
        target = REPO_ROOT / target
    if not target.is_file():
        print(f"cold-read-grid: target not found: {target}", file=sys.stderr)
        return 2
    # Before anything is created and before anything is launched: a refused
    # cold-read-target must leave no cold-read-record behind and
    # start no reviewers.
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

    record_dir = make_record_dir(target, record_clock_reading())
    reference_integrity_pre_pass(target, record_dir)

    print(f"Launched six reviewers against {target}. Reports appear in "
          f"{record_dir} as each completes — read each as it arrives.")

    # THE COLD-READ-TARGET IS FROZEN FOR THE RUN, and this is how the
    # cold-read-grid knows whether it stayed frozen: the bytes are
    # fingerprinted the moment before the cold-read-cells start and again the
    # moment after the last one finishes. Eight reviewers reading one file over
    # half an hour cannot themselves be stopped from disagreeing if the file
    # moves under them; what this can do is refuse to let the resulting set
    # pass for a review of the current document.
    target_before = freeze_target(target, record_dir)
    outcome = wait_for_cells(launch_cells(target, record_dir))
    target_after = target_content_fingerprint(target)
    target_changed = target_before != target_after
    if target_changed:
        detail = mark_reports_target_changed(
            record_dir, target, target_before, target_after)
        print(f"TARGET CHANGED DURING RUN: {detail}", flush=True)

    launched = len(CELL_LAUNCHERS) * len(GRID_CELL_ROSTER)
    if outcome.absent:
        # After the target-changed marker when both apply, so that one stays
        # first; the reports are kept, and a reader who opens one in the
        # log-store months later sees which reports its set lacked. BEFORE
        # THE SHIP, because the shipper is add-only and refuses a record
        # whose stored file differs from the local one: what ships must be
        # the record's final bytes, or the post-triage ship of triage.md is
        # refused over reports that gained this marker after they shipped.
        mark_every_report(record_dir, incomplete_set_marker(outcome.absent, launched))

    # The cold-read-record goes to the log-store now, whatever landed: a set
    # marked TARGET CHANGED is evidence too, and a failed cold-read-cell's
    # log is part of the cold-read-record. triage.md is not written
    # yet; the agent ships again after writing it, and the shipper adds
    # it beside the reports.
    print(f"record: {ship_record(record_dir)}", flush=True)

    print()
    # ONE CLOSING TEXT, IN FOUR VARIANTS, FROM WHAT LANDED. A changed
    # cold-read-target outranks everything: a set read against a document
    # that changed during the run is not valid, whatever else happened.
    # Otherwise the set is valid, and incomplete when a report is absent
    # (user-ruled 2026-09-11, point 4) -- the reports that landed are triaged
    # as the review that was asked for, and each absence is recorded. The
    # absent reports and any agent-binary that is down are listed in every
    # variant that has them, and a cause the user can clear ends the text.
    tell = tell_the_user_sentence(outcome.absent)
    absences = absence_lines(outcome)
    if target_changed:
        print(TARGET_CHANGED_INSTRUCTIONS.format(record_dir=record_dir))
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
    # A moved cold-read-target outranks an absent report in the exit code:
    # absent reports leave a smaller review, while a moved cold-read-target
    # leaves one that describes the wrong document, and the second is the
    # condition a caller most needs to branch on. Exit codes are unchanged
    # by the retry: an agent reads the closing text, not the code.
    if target_changed:
        return 3
    return 1 if outcome.absent else 0

if __name__ == "__main__":
    sys.exit(main())
