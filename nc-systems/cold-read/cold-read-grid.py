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
and the run fingerprints BOTH the copy and the original at the end, because
the records tree is gitignored and an edit to the copy would otherwise be
invisible to the cold-read-cell's `git status` stray-write detector. At the
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

A RUN STOPS AS SOON AS ITS COLD-READ-TARGET MOVES (user-ruled 2026-09-23, walk
cold-read-research-decisions-waiting-on-the-user-2026-09-23, item 6: "n, and
yes abort early"). A set read against a document that has since changed is
discarded and the document read again, so a reviewer still reading after the
move is spending the rest of a 10-20 minute read on a review nobody will
triage. Both fingerprints are therefore taken at every poll, not only at the
end: the first poll that sees either the original or the frozen copy differ
while any cold-read-cell is still running stops every running cold-read-cell
with its children, marks what the set holds, and exits 3. Every poll, which
is every 5 seconds, because hashing a Markdown file costs microseconds: a
slower cadence would buy nothing and add a timer. The end-of-run comparison
stays, for a move after the last cold-read-cell has finished, which stops
nothing. A cold-read-cell is stopped with its children because it is a launcher
whose model CLI runs as a child process: stopping the launcher alone would
leave the CLI reading, spending tokens, and free to write its report into the
record after the marker went on.

Exit codes: 0 all cold-read-cells ran, 1 one or more reports are absent, 2 no
cold-read-cell was launched (a bad invocation, a cold-read-target this
instrument refuses to review, or a cold-read-target that could not be frozen
into the cold-read-record), 3 the cold-read-target changed while the
cold-read-cells were
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
import signal
import subprocess
import sys
import time
import typing

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
# Import shared status phrases so launcher output and grid parsing cannot drift.
_common_spec = importlib.util.spec_from_file_location(
    "cold_read_cell_common", pathlib.Path(__file__).with_name("cold-read-cell-common.py")
)
cell_common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(cell_common)
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

TARGET_CHANGED_MARKER_PREFIX = "<!-- TARGET CHANGED DURING RUN:"
INCOMPLETE_SET_MARKER_PREFIX = "<!-- INCOMPLETE SET:"
GRID_MARKER_PREFIXES = (TARGET_CHANGED_MARKER_PREFIX, INCOMPLETE_SET_MARKER_PREFIX)

# These prefixes are consumed by the cold-read skill's Monitor; FAILED keeps its no-colon form.
RETRYING_PREFIX = "RETRYING:"
AGENT_BINARY_DOWN_PREFIX = "AGENT-BINARY DOWN:"
STOPPED_CELL_WRITE_CHECK_LINE = (
    "this cell was stopped before its stray-write check ran, which is a failure "
    "to look, not a clean result. Before the new run, read `git status` against "
    "the edits you know are your own and revert only what you did not write.")

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


def make_record_dir(target: pathlib.Path, now: datetime.datetime) -> pathlib.Path:
    """Create and return the first unused record directory for this document and day."""
    record_dir = record_names.fresh_record_directory(
        RECORDS_DIR / record_directory_name_for_target(target, now))
    record_dir.mkdir(parents=True)
    return record_dir


def reference_integrity_pre_pass(target: pathlib.Path, record_dir: pathlib.Path) -> None:
    """Save unresolved references as leads for the reviewer."""
    text = target.read_text(encoding="utf-8")
    # A filename can contain more than one dot.
    candidates = sorted(set(re.findall(
        r"[\w./-]+/[\w./-]+|[\w-]+(?:\.[\w-]+)*\.(?:md|py|sh|json|yaml|toml)",
        text)))
    lines = ["# Reference-integrity pre-pass", ""]
    for candidate in candidates:
        # Strip trailing punctuation only; leading dots belong to paths.
        clean = candidate.rstrip(".,;:")
        resolved = (REPO_ROOT / clean).exists() or (target.parent / clean).exists()
        lines.append(f"- {'ok' if resolved else 'UNRESOLVED'}: `{clean}`")
    if not candidates:
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


def moved_target(target: pathlib.Path, frozen_target: pathlib.Path,
                 before: str) -> typing.Optional[tuple]:
    """Return (path, current hash) for a changed file, preferring the frozen copy, or None."""
    frozen_now = target_content_fingerprint(frozen_target)
    if frozen_now != before:
        return frozen_target, frozen_now
    target_now = target_content_fingerprint(target)
    if target_now != before:
        return target, target_now
    return None


WINDOW_SEEN_AT_END = ("differed between the moment the cells launched and the "
                      "moment the last one finished")
WINDOW_SEEN_MID_RUN = ("changed while the cells were still running, and the run "
                       "stopped the ones still reading")


TARGET_CHANGED_INSTRUCTIONS = """\
The reports are in {record_dir}, and every one of them is marked: the document's
bytes {window}, so this set is not a review of the document as it now stands.

Do not triage this set as a review of the document. Stop editing the document
and start a new cold-read run against the settled text.

Keep the set. Each report still records truthfully what one reviewer read, which
is evidence of what the reviewers saw — not of how the file now stands.
"""


def mark_reports_target_changed(
    record_dir: pathlib.Path, target: pathlib.Path, before: str, after: str,
    seen_mid_run: bool = False,
) -> str:
    """Mark reports as describing a changed target and return the marker."""
    # Fingerprints establish differing bytes, not when the edit occurred.
    # A changed original leaves the frozen review intact; a changed copy makes reviewed bytes uncertain.
    changed_path_is_the_frozen_copy = record_dir in target.parents
    if changed_path_is_the_frozen_copy:
        what_the_reports_describe = (
            "Which text any one report in this directory describes is unknown: "
            "the edit may have landed before a given reviewer opened the file "
            "or after."
        )
    else:
        what_the_reports_describe = (
            "Every report in this directory describes the frozen copy under "
            "target/, which did not move; what moved is the document in the "
            "repository."
        )
    window = WINDOW_SEEN_MID_RUN if seen_mid_run else WINDOW_SEEN_AT_END
    detail = (
        f"{target}'s bytes {window} — sha256 {before[:12] or 'unreadable'} then "
        f"{after[:12] or 'unreadable'}. {what_the_reports_describe} Treat this set "
        f"as evidence of what reviewers saw, not as a review of the current file; "
        f"start a new cold-read run against the settled document."
    )
    mark_every_report(record_dir, f"{TARGET_CHANGED_MARKER_PREFIX} {detail} -->")
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


def process_parents() -> dict:
    """Return {pid: parent pid}, or an empty mapping if ps fails."""
    try:
        completed = subprocess.run(["ps", "-A", "-o", "pid=", "-o", "ppid="],
                                   capture_output=True, text=True, check=False)
    except OSError:
        return {}
    parents = {}
    for line in completed.stdout.splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[0].isdigit() and fields[1].isdigit():
            parents[int(fields[0])] = int(fields[1])
    return parents


def stop_process_tree(process: subprocess.Popen, grace_seconds: float = 5.0) -> None:
    """Stop a launcher and its descendants."""
    # Freeze top-down before collecting descendants; killing the launcher first orphans them.
    frozen = []
    tried = set()
    frontier = [process.pid]
    while frontier:
        for pid in frontier:
            tried.add(pid)
            try:
                os.kill(pid, signal.SIGSTOP)
            except (ProcessLookupError, PermissionError):
                continue
            frozen.append(pid)
        # Track attempted stops too; retrying an un-stoppable process would loop forever.
        frontier = [pid for pid, parent in process_parents().items()
                    if parent in frozen and pid not in tried]
    for signal_number in (signal.SIGTERM, signal.SIGCONT):
        for pid in frozen:
            try:
                os.kill(pid, signal_number)
            except (ProcessLookupError, PermissionError):
                pass
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        pass
    for pid in frozen:
        try:
            os.kill(pid, signal.SIGKILL)
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

    record_dir = make_record_dir(target, record_clock_reading())
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
    print(f"Launched six reviewers against {target}. Reports appear in "
          f"{record_dir} as each completes — read each as it arrives.")

    outcome = wait_for_cells(
        launch_cells(frozen_target, record_dir, target),
        lambda: moved_target(target, frozen_target, target_before),
        float(os.environ.get(TARGET_CHECK_INTERVAL_OVERRIDE_VARIABLE) or 0),
        float(os.environ.get(CELL_POLL_INTERVAL_OVERRIDE_VARIABLE)
              or CELL_POLL_INTERVAL_DEFAULT_SECONDS))
    # Prefer the final comparison: the frozen copy may change after a poll detects a changed original.
    # Retain the poll result if the changed bytes were restored before the final comparison.
    move = moved_target(target, frozen_target, target_before) or outcome.moved_mid_run
    target_changed = move is not None
    if target_changed:
        changed_path, changed_after = move
        detail = mark_reports_target_changed(
            record_dir, changed_path, target_before, changed_after,
            seen_mid_run=outcome.moved_mid_run is not None)
        print(f"TARGET CHANGED DURING RUN: {detail}", flush=True)

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
