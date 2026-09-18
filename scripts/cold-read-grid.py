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

Exit codes: 0 all cold-read-cells ran, 1 one or more cold-read-cells failed,
2 bad invocation (including a cold-read-target this instrument refuses
to review), 3 the cold-read-target changed while the cold-read-cells were
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

COMPLETION_INSTRUCTIONS = """\
All six reviews are complete, in {record_dir}, one file per reviewer.

Read every report in full. The defect-hunt reports flag defects with each
reviewer's own confidence; expect heavy overlap — the same defect found
independently by several reviewers is one defect. The terminology reports
list the document's key-terms that fail one of five criteria, with the
criteria numbers per item and a closing counts line; triage them the same
way as the defect-hunt reports.

Keep your judgments provisional until you have read all six, as later
reports may offer more insight than earlier ones. Then formulate your draft
response: which problems are real, and what you propose to do about each.
Walk that with the user using the walk-me-through skill, ordered from most
important to least.

This record was shipped to the log-store on ned-box when the run ended (the
`record:` line above says whether it arrived); once triage.md is written,
run `scripts/cold-read-record-ship.py {record_dir}` so it joins the reports
there. cold-read-records/ stays gitignored: never commit it. Leave {record_dir}
in place once the work it served has landed — these records are kept, not
deleted: like other logs they are useful for analysis later (user-ruled
2026-08-25). The findings still belong in the reviewed document and the
rulings in its governing document; this directory is what produced them, not
where they live."""

# The closing text when an Opus cold-read-cell -- the good Claude
# cold-read-cell of either pass -- produced no report (user-ruled 2026-09-04:
# "If opus fails we stop working and wait for it to come back"). It replaces
# COMPLETION_INSTRUCTIONS rather than following it, because a reader told the
# reviews are complete and then told to stop has been told two things. The
# reports that did land are kept, unread: a read of this cold-read-target is
# the six-cell set, and the set is run again when Opus is back.
OPUS_ABSENT_INSTRUCTIONS = """\
An Opus review did not land, so this is not the review that was asked for.

Stop here. Do not triage the reports in {record_dir}, do not rerun the Opus
cell on another model, and do not start editing the document on the strength
of the reviews that did land. Wait for Opus to come back, then start a new
cold-read run against the same document. Keep {record_dir}: like every record
directory it is kept, not deleted (user-ruled 2026-08-25), and its FAILED
line says what the Opus cell reported."""


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
    marker = f"{TARGET_CHANGED_MARKER_PREFIX} {detail} -->"
    for report_path in sorted(record_dir.glob("*.md")):
        lines = report_path.read_text(encoding="utf-8").split("\n")
        # After the provenance stamp when there is one, so the stamp stays the
        # first line every reader and parser of these cold-read-records
        # expects; at the top otherwise (the reference-integrity pre-pass
        # carries no stamp).
        insert_at = 1 if lines and lines[0].startswith("<!-- provenance:") else 0
        lines.insert(insert_at, marker)
        report_path.write_text("\n".join(lines), encoding="utf-8")
    return detail


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
    instrument built.

    The pass token is the cell name, except that defect-hunt is `hunt` --
    the token every record set since 2026-08-25 has carried. One function
    composes the name so main() can ask which cold-read-cell a failed report
    belonged to by the same rule that named it.
    """
    pass_token = "hunt" if cell_pass == "defect-hunt" else cell_pass
    return record_dir / f"{runtime}-{pass_token}-{tier}.md"


def launch_cells(target: pathlib.Path, record_dir: pathlib.Path) -> dict:
    """Start all six cold-read-cells in parallel. Returns {report_path:
    (process, stderr_path)}. The parent's file handles are closed right after
    each spawn; the child keeps its own copies, so a with-block is the wrong
    shape here."""
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
            err = open(stderr_path, "w", encoding="utf-8")  # pylint: disable=consider-using-with
            process = subprocess.Popen(  # pylint: disable=consider-using-with
                command, stdout=err, stderr=err, stdin=subprocess.DEVNULL,
            )
            err.close()
            running[report_path] = (process, stderr_path)
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


def wait_for_cells(running: dict) -> list:
    """Poll until every cold-read-cell finishes; print per-report progress;
    return the list of failed report names."""
    failures = []
    while running:
        time.sleep(5)
        for report_path in list(running):
            process, stderr_path = running[report_path]
            code = process.poll()
            if code is None:
                continue
            del running[report_path]
            # A cold-read-cell's exit code is not on its own evidence
            # that a review happened: the report is (nedschorus#164). The
            # cold-read-cell enforces the same rule, and the cold-read-grid
            # checks again rather than trusting it, because the cold-read-grid
            # is what tells the reviewing agent below what to believe — and
            # six "saved" lines over empty files read as six reviewers finding
            # nothing.
            has_report = (
                report_path.is_file()
                and report_path.read_text(encoding="utf-8").strip() != ""
            )
            if code == 0 and has_report:
                # THREE THINGS EXIST ONLY IN THIS LOG, and this is the branch
                # that deletes it -- so without lifting them out first, the one
                # path where each is produced is the path where it is
                # destroyed. All three are carried onto the cold-read-grid's
                # own output, which is what the reviewing agent actually reads.
                #
                # WHAT THE STRAY-WRITE CHECK FOUND, and whether it ran at all.
                # A stray edit is ordinary cleanup for that agent, not something
                # to escalate. A cold-read-cell whose `git status` could
                # not answer -- an index.lock held by another agent in the
                # same checkout is the ordinary way, and the cold-read-cell
                # says in as many words that this is a failure to look, not
                # a clean result -- otherwise reported here exactly like a
                # cold-read-cell that looked and found nothing, and a whole
                # cold-read-full-run read as clean when nothing had been
                # checked at all (nedschorus#167).
                #
                # EACH IS MATCHED ONLY ON A LINE THE COLD-READ-CELL ITSELF
                # BEGAN. The cold-read-cell re-emits its runtime's stderr
                # into this same log, and the Codex CLI writes the model's
                # text there -- so on 2026-09-02 a cold-read-target that
                # quoted a code comment containing "fell back to" made two
                # cold-read-cells read as fallen back when both had run on
                # the models asked for (nedschorus#244). A bare substring
                # test cannot tell the cold-read-cell's sentence from the
                # model's; the program prefix can. The phrases come from
                # the cold-read-cell module, where each is pinned as a
                # contract with this loop.
                #
                # A FALLBACK IS NEVER SILENT (user-ruled 2026-08-25: "I'm ok
                # with the fable falling back to opus too. I just don't want it
                # to fail silently"). Before this, a fallback was recorded only
                # in the report's own `fallback_from=` provenance stamp, which
                # nobody sees unless they open that file -- so a cold-read-cell
                # reviewed by the chain's second model was indistinguishable,
                # here, from one reviewed by the model asked for. The
                # cold-read-cell's own line already names the model that
                # produced the report and every model that failed ahead of
                # it with the reason each failed; the report name says which
                # cold-read-cell it was. Since 2026-09-04 every pinned chain
                # has one model (the user ruled Opus falling back to Fable
                # invalid), so this line is lifted for a chain a ruling may pin
                # later and for nothing that runs today.
                # A RECOVERY IS NEVER SILENT EITHER (user-ruled 2026-08-25),
                # for the same reason a fallback is not: the cold-read-cell
                # was one character from losing a finished 33-finding review
                # that day, and a run that nearly lost its work should say so
                # where the reviewing agent reads rather than in a log this
                # branch is about to delete. The report itself is intact;
                # what the line buys is a reader who knows the model mistyped
                # the directory it was given, which is worth knowing before
                # trusting the rest of what it did.
                for line in stderr_path.read_text(encoding="utf-8").splitlines():
                    if cell_status_line(line, cell_common.STRAY_WRITE_PHRASE):
                        print(f"STRAY WRITE: {line.strip()}", flush=True)
                    if cell_status_line(line, cell_common.STRAY_WRITE_CHECK_SKIPPED_PHRASE):
                        print(f"WRITE CHECK DID NOT RUN: {report_path.name} — "
                              f"{line.strip()}", flush=True)
                    if cell_status_line(line, cell_common.FELL_BACK_PHRASE):
                        print(f"FELL BACK: {report_path.name} — {line.strip()}",
                              flush=True)
                    if cell_status_line(line, cell_common.NEAR_MISS_RECOVERY_PHRASE):
                        print(f"RECOVERED: {report_path.name} — {line.strip()}",
                              flush=True)
                stderr_path.unlink(missing_ok=True)
                print(f"saved: {report_path}", flush=True)
                continue
            if code == 0 and not has_report:
                failures.append(report_path.name)
                print(f"FAILED (exit 0, no report): {report_path.name} — the cell "
                      f"reported success without writing a review; treat as failed "
                      f"and rerun (stderr kept: {stderr_path})", flush=True)
                continue
            failures.append(report_path.name)
            hint = ""
            stderr_tail = stderr_path.read_text(encoding="utf-8")[-2000:]
            if "401" in stderr_tail or "Not logged in" in stderr_tail:
                hint = " — the runtime is logged out; ask the user to log in, then rerun this cell"
            print(f"FAILED (exit {code}): {report_path.name}{hint} "
                  f"(stderr kept: {stderr_path})", flush=True)
    return failures


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
    failures = wait_for_cells(launch_cells(target, record_dir))
    target_after = target_content_fingerprint(target)
    target_changed = target_before != target_after
    if target_changed:
        detail = mark_reports_target_changed(
            record_dir, target, target_before, target_after)
        print(f"TARGET CHANGED DURING RUN: {detail}", flush=True)

    # The cold-read-record goes to the log-store now, whatever landed: a set
    # marked TARGET CHANGED is evidence too, and a failed cold-read-cell's
    # log is part of the cold-read-record. triage.md is not written
    # yet; the agent ships again after writing it, and the shipper adds
    # it beside the reports.
    print(f"record: {ship_record(record_dir)}", flush=True)

    print()
    # WHICH COLD-READ-CELL FAILED DECIDES WHAT THE READER DOES NEXT (user-ruled
    # 2026-09-04: "opus falling back to fable is not valid. If opus fails we
    # stop working and wait for it to come back. If fable is not available,
    # just note that and continue"). The Claude cold-read-cells are
    # single-model since that ruling, so a failed Claude cold-read-cell is
    # that model being unavailable, and the two models mean opposite things
    # to the read: the good cold-read-tier's Opus is the read's deepest
    # seat -- in BOTH passes, so the good Claude cold-read-cell of either
    # pass failing is the Opus-absent case -- and a review without it is not
    # the review that was asked for; the floor cold-read-tier's Fable is a
    # when-available addition, because the account's Fable limit is hit often
    # enough (2026-08-23; four cold-read-cells on 2026-09-03) that a read which
    # stopped for it would stop often, and the five cold-read-cells that remain
    # are the 2026-09-03 campaign's standing full-tier set plus the Codex floor
    # and the two terminology cold-read-cells. Which cold-read-cells those are
    # is asked of the roster by the rule that named the reports, so a stem that
    # happens to contain a cell-shaped fragment cannot be mistaken for one.
    opus_report_names = {
        cell_report_path(record_dir, "claude", cell_pass, tier).name
        for cell_pass, tier, _effort in GRID_CELL_ROSTER if tier == "good"}
    fable_report_names = {
        cell_report_path(record_dir, "claude", cell_pass, tier).name
        for cell_pass, tier, _effort in GRID_CELL_ROSTER if tier == "floor"}
    opus_cell_failed = any(name in opus_report_names for name in failures)
    only_fable_cell_failed = (
        failures != [] and not opus_cell_failed
        and all(name in fable_report_names for name in failures))
    # A moved cold-read-target and a settled one call for opposite next
    # actions, so they get different closing text: triage the set, or
    # stop and run it again.
    # An absent Opus review outranks a settled cold-read-target: there
    # is nothing to triage until Opus is back, whatever the other
    # cold-read-cells landed.
    if target_changed:
        print(TARGET_CHANGED_INSTRUCTIONS.format(record_dir=record_dir))
    elif opus_cell_failed:
        print(OPUS_ABSENT_INSTRUCTIONS.format(record_dir=record_dir))
    else:
        print(COMPLETION_INSTRUCTIONS.format(record_dir=record_dir))
    if failures:
        # A moved cold-read-target changes what an absent review means,
        # so the note that names them changes with it: on the settled path
        # the set is merely short and the missing cold-read-cells are worth
        # rerunning singly before triage; on the changed path there is no
        # triage for them to be short for, because the whole set is being
        # replaced. The two conditions are independent and do land together.
        # An absent Opus review is its own case on either path: rerunning
        # singly is what the reader must NOT do until Opus is back, and an
        # absent Fable review on a settled cold-read-target is the one absence
        # the reader continues past.
        if target_changed:
            what_to_do = (
                "Rerunning them singly would not help: the set they belong to is "
                "being replaced by a run against the settled document."
                + (" Wait for Opus to come back before that run." if opus_cell_failed
                   else ""))
        elif opus_cell_failed:
            what_to_do = (
                "Do not rerun the Opus cell on another model and do not triage "
                "the reports that landed: wait for Opus to come back, then start "
                "a new cold-read run.")
        elif only_fable_cell_failed:
            what_to_do = (
                "That is the Fable floor cell, a when-available seat: note its "
                "absence in triage.md and continue with the reports that "
                "landed, which are the Opus, Codex good and Codex floor "
                "defect-hunt reviews and the Opus and Codex terminology reviews.")
        else:
            what_to_do = (
                "Rerun them singly with the cell launchers before triage, or note "
                "their absence in triage.md.")
        print(f"\nNOTE: {len(failures)} review(s) failed and are absent from the "
              f"record: {', '.join(failures)}. {what_to_do}")
    # A moved cold-read-target outranks a failed cold-read-cell in the exit
    # code: failed cold-read-cells leave a smaller review, while a moved
    # cold-read-target leaves one that describes the wrong document, and the
    # second is the condition a caller most needs to branch on.
    if target_changed:
        return 3
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
