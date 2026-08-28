#!/usr/bin/env python3
"""Run a full cold-read grid against a document.

One invocation = one review: eight cells ({restate, defect-hunt} x
{good, floor} x {claude, codex}) launched in parallel, every report saved
into a dated record directory, progress and next-step instructions printed
for the reviewing agent as reviews land.

Usage:
  scripts/cold-read-grid.py --target docs/drafts/foo.md

Exit codes: 0 all cells ran, 1 one or more cells failed, 2 bad invocation
(including a target this instrument refuses to review), 3 the target file
changed while the cells were running, so every report in the set describes a
document that no longer exists in the form reviewed.
"""

import argparse
import datetime
import hashlib
import pathlib
import re
import subprocess
import sys
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
RECORDS_DIR = REPO_ROOT / "cold-read-records"
# Cell launchers, one per runtime.
CELL_LAUNCHERS = {
    "claude": REPO_ROOT / "scripts" / "cold-read-claude-cell.py",
    "codex": REPO_ROOT / "scripts" / "cold-read-codex-cell.py",
}
PASSES = ["restate", "defect-hunt"]
TIERS = ["good", "floor"]

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

# Prepended to every report in a set whose target changed under it. Read by
# people and by whatever reads these records next; the reports are KEPT --
# they are evidence of what a reviewer saw -- but nothing downstream should
# read them as a review of the file as it now stands.
TARGET_CHANGED_MARKER_PREFIX = "<!-- TARGET CHANGED DURING RUN:"

COMPLETION_INSTRUCTIONS = """\
All eight reviews are complete, in {record_dir}, one file per reviewer.

Read every report in full. The restate reports show what a reader took each
sentence to mean — compare them against what you intended; a confident
misreading is a defect in the file, not in the reader. The defect-hunt
reports flag defects with each reviewer's own confidence; expect heavy
overlap — the same defect found independently by several reviewers is one
defect.

Keep your judgments provisional until you have read all eight, as later
reports may offer more insight than earlier ones. Then formulate your draft
response: which problems are real, and what you propose to do about each.
Walk that with the user using the walk-me-through skill, ordered from most
important to least. The walk's anchor is {record_dir}/dispositions.md.

These records are machine-local and gitignored (user-ruled 2026-08-14): never
commit them. Leave {record_dir} in place once the work it served has landed —
these records are kept, not deleted: like other logs they are useful for
analysis later (user-ruled 2026-08-25). The findings still belong in the
reviewed document and the rulings in its governing document; this directory is
what produced them, not where they live."""


def make_record_dir(target: pathlib.Path) -> pathlib.Path:
    date = datetime.date.today().isoformat()
    base = f"{date}-{target.stem}"
    record_dir = RECORDS_DIR / base
    suffix = 2
    while record_dir.exists():
        record_dir = RECORDS_DIR / f"{base}-{suffix}"
        suffix += 1
    record_dir.mkdir(parents=True)
    return record_dir


def reference_integrity_pre_pass(target: pathlib.Path, record_dir: pathlib.Path) -> None:
    """Cheap grounding check: every path-like reference in the target either
    resolves (relative to the repo root or the target's directory) or is
    listed as unresolved. Result saved into the record for the reviewing
    agent; unresolved references are leads, not verdicts."""
    text = target.read_text(encoding="utf-8")
    candidates = sorted(set(re.findall(
        r"[\w./-]+/[\w./-]+|[\w-]+\.(?:md|py|sh|json|yaml|toml)", text)))
    lines = ["# Reference-integrity pre-pass", ""]
    for candidate in candidates:
        clean = candidate.strip(".,;:")
        resolved = (REPO_ROOT / clean).exists() or (target.parent / clean).exists()
        lines.append(f"- {'ok' if resolved else 'UNRESOLVED'}: `{clean}`")
    if not candidates:
        lines.append("- no path-like references found")
    (record_dir / f"{record_dir.name}--reference-check.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")


def target_content_fingerprint(target: pathlib.Path) -> str:
    """The target's bytes, hashed. "" when the file cannot be read at all.

    Content rather than mtime: an editor that writes and restores a file
    leaves a changed mtime and an unchanged document, and that is not the
    event this guard exists for. A file deleted or made unreadable mid-run
    yields "", which differs from any real digest and so counts as a change.

    `path_content_fingerprint` in scripts/cold-read-cell-common.py is the same
    idea applied to every path in the working tree, and the name here echoes
    it deliberately. The two stay separate because the grid launches the cell
    scripts as programs and never loads that module, and because they answer
    different questions about an unreadable path: the detector distinguishes
    absent from unreadable from a directory, since it must tell a creation
    from a deletion, while one target that cannot be read is simply not the
    document that was fingerprinted at launch.
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
and run the grid again against the settled text.

Keep the set. Each report still records truthfully what one reviewer read, which
is evidence of what the reviewers saw — not of how the file now stands.
"""


def mark_reports_target_changed(
    record_dir: pathlib.Path, target: pathlib.Path, before: str, after: str,
) -> str:
    """Stamp every report in the set as reviewing a document that moved.

    WHAT HAPPENED (2026-08-24). The merge-lane seat had to mark a whole record
    set COMPROMISED because the target was edited while the cells ran. The
    tell was subtle and nearly missed: a clean-looking report whose "clean
    sections" list simply omitted the sections that had changed underneath it.
    Nothing in the record said the file had moved, so the only way to catch it
    was to notice an absence.

    The reports are marked, never deleted: each still records truthfully what
    one reviewer read, which is evidence. What the marker removes is the
    possibility of reading them as a review of the file as it now stands.
    """
    # WHAT THE TWO FINGERPRINTS PROVE, and no more: the bytes differed between
    # the moment before the cells launched and the moment after the last one
    # finished. They do not say when in that window the edit landed, so they
    # cannot say that it landed while a reviewer was reading, nor which text
    # any one report describes — the ordinary case is an edit part-way through,
    # with some cells having opened the file before it and some after. The
    # marker is the durable half of this check: these records are kept, so a
    # sentence claiming more than the check knows would outlive the run.
    detail = (
        f"{target}'s bytes differed between the moment the cells launched and the "
        f"moment the last one finished — sha256 {before[:12] or 'unreadable'} then "
        f"{after[:12] or 'unreadable'}. Which text any one report in this directory "
        f"describes is unknown: the edit may have landed before a given reviewer "
        f"opened the file or after. Treat this set as evidence of what reviewers "
        f"saw, not as a review of the current file; re-run the grid against the "
        f"settled document."
    )
    marker = f"{TARGET_CHANGED_MARKER_PREFIX} {detail} -->"
    for report_path in sorted(record_dir.glob("*.md")):
        lines = report_path.read_text(encoding="utf-8").split("\n")
        # After the provenance stamp when there is one, so the stamp stays the
        # first line every reader and parser of these records expects; at the
        # top otherwise (the reference-integrity pre-pass carries no stamp).
        insert_at = 1 if lines and lines[0].startswith("<!-- provenance:") else 0
        lines.insert(insert_at, marker)
        report_path.write_text("\n".join(lines), encoding="utf-8")
    return detail


def launch_cells(target: pathlib.Path, record_dir: pathlib.Path) -> dict:
    """Start all eight cells in parallel. Returns {report_path: (process,
    stderr_path)}. The parent's file handles are closed right after each
    spawn; the child keeps its own copies, so a with-block is the wrong
    shape here."""
    running = {}
    for runtime, launcher in CELL_LAUNCHERS.items():
        for cell_pass in PASSES:
            for tier in TIERS:
                pass_token = "hunt" if cell_pass == "defect-hunt" else cell_pass
                # THE FILE NAME CARRIES THE RUN (user-ruled 2026-08-25). Every
                # file this grid writes into a record directory is prefixed
                # with that directory's own name, so a report says which run
                # produced it wherever it is later found or copied. Before
                # this, all eight of a run's reports were named for the cell
                # alone -- `codex-hunt-floor.md` and seven like it -- and two
                # grids running at once in one checkout (three did that day)
                # each had a file of every one of those names. A cell of the
                # first run that wrote nothing could then have the second
                # run's correctly placed report recovered as its own: the
                # first run holds a review of the wrong document under its
                # stamp, and the second loses the review it produced.
                report_path = record_dir / (
                    f"{record_dir.name}--{runtime}-{pass_token}-{tier}.md")
                stderr_path = record_dir / (report_path.name + ".stderr.log")
                # The reviewer writes the report itself; the cell is told
                # where. Capturing the model's chat text was what lost
                # findings written before a tool call (measured 2026-08-23),
                # so nothing here redirects stdout into the report any more.
                err = open(stderr_path, "w", encoding="utf-8")  # pylint: disable=consider-using-with
                process = subprocess.Popen(  # pylint: disable=consider-using-with
                    [str(launcher), "--cell", cell_pass, "--tier", tier,
                     "--target", str(target), "--report", str(report_path)],
                    stdout=err, stderr=err, stdin=subprocess.DEVNULL,
                )
                err.close()
                running[report_path] = (process, stderr_path)
    return running


def wait_for_cells(running: dict) -> list:
    """Poll until every cell finishes; print per-report progress; return the
    list of failed report names."""
    failures = []
    while running:
        time.sleep(5)
        for report_path in list(running):
            process, stderr_path = running[report_path]
            code = process.poll()
            if code is None:
                continue
            del running[report_path]
            # A cell's exit code is not on its own evidence that a review
            # happened: the report is (nedschorus#164). The cell enforces the
            # same rule, and the grid checks again rather than trusting it,
            # because the grid is what tells the reviewing agent below what to
            # believe — and eight "saved" lines over empty files read as eight
            # reviewers finding nothing.
            has_report = (
                report_path.is_file()
                and report_path.read_text(encoding="utf-8").strip() != ""
            )
            if code == 0 and has_report:
                # THREE THINGS EXIST ONLY IN THIS LOG, and this is the branch
                # that deletes it -- so without lifting them out first, the one
                # path where each is produced is the path where it is
                # destroyed. All three are carried onto the grid's own output,
                # which is what the reviewing agent actually reads.
                #
                # WHAT THE STRAY-WRITE CHECK FOUND, and whether it ran at all.
                # A stray edit is ordinary cleanup for that agent, not something
                # to escalate. A cell whose `git status` could not answer -- an
                # index.lock held by another agent in the same checkout is the
                # ordinary way, and the cell says in as many words that this is
                # a failure to look, not a clean result -- otherwise reported
                # here exactly like a cell that looked and found nothing, and a
                # whole grid run read as clean when nothing had been checked at
                # all (nedschorus#167). That second clause matches the phrase the
                # cell module pins for it as STRAY_WRITE_CHECK_SKIPPED_PHRASE;
                # keep the two in step.
                #
                # A FALLBACK IS NEVER SILENT (user-ruled 2026-08-25: "I'm ok
                # with the fable falling back to opus too. I just don't want it
                # to fail silently"). Before this, a fallback was recorded only
                # in the report's own `fallback_from=` provenance stamp, which
                # nobody sees unless they open that file -- so a cell reviewed by
                # the chain's second model was indistinguishable, here, from one
                # reviewed by the model asked for. The cell's own line already
                # names the model that produced the report and every model that
                # failed ahead of it with the reason each failed; the report
                # name says which cell it was.
                # A RECOVERY IS NEVER SILENT EITHER (user-ruled 2026-08-25),
                # for the same reason a fallback is not: the cell was one
                # character from losing a finished 33-finding review that day,
                # and a run that nearly lost its work should say so where the
                # reviewing agent reads rather than in a log this branch is
                # about to delete. The report itself is intact; what the line
                # buys is a reader who knows the model mistyped the directory
                # it was given, which is worth knowing before trusting the
                # rest of what it did.
                for line in stderr_path.read_text(encoding="utf-8").splitlines():
                    if "changed files outside its report" in line:
                        print(f"STRAY WRITE: {line.strip()}", flush=True)
                    if "stray writes were not checked for this run" in line:
                        print(f"WRITE CHECK DID NOT RUN: {report_path.name} — "
                              f"{line.strip()}", flush=True)
                    if "fell back to" in line:
                        print(f"FELL BACK: {report_path.name} — {line.strip()}",
                              flush=True)
                    if "recovered a near-miss report" in line:
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
    # target must leave no record directory behind and start no reviewers.
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

    record_dir = make_record_dir(target)
    reference_integrity_pre_pass(target, record_dir)

    print(f"Launched eight reviewers against {target}. Reports appear in "
          f"{record_dir} as each completes — read each as it arrives.")

    # THE TARGET IS FROZEN FOR THE RUN, and this is how the grid knows whether
    # it stayed frozen: the bytes are fingerprinted the moment before the cells
    # start and again the moment after the last one finishes. Eight reviewers
    # reading one file over half an hour cannot themselves be stopped from
    # disagreeing if the file moves under them; what this can do is refuse to
    # let the resulting set pass for a review of the current document.
    target_before = target_content_fingerprint(target)
    failures = wait_for_cells(launch_cells(target, record_dir))
    target_after = target_content_fingerprint(target)
    target_changed = target_before != target_after
    if target_changed:
        detail = mark_reports_target_changed(
            record_dir, target, target_before, target_after)
        print(f"TARGET CHANGED DURING RUN: {detail}", flush=True)

    print()
    # A moved target and a settled one call for opposite next actions, so they
    # get different closing text: triage the set, or stop and run it again.
    if target_changed:
        print(TARGET_CHANGED_INSTRUCTIONS.format(record_dir=record_dir))
    else:
        print(COMPLETION_INSTRUCTIONS.format(record_dir=record_dir))
    if failures:
        # A moved target changes what an absent review means, so the note that
        # names them changes with it: on the settled path the set is merely
        # short and the missing cells are worth rerunning singly before triage;
        # on the changed path there is no triage for them to be short for,
        # because the whole set is being replaced. The two conditions are
        # independent and do land together.
        what_to_do = (
            "Rerunning them singly would not help: the set they belong to is "
            "being replaced by a run against the settled document."
            if target_changed else
            "Rerun them singly with the cell launchers before triage, or note "
            "their absence in dispositions.md."
        )
        print(f"\nNOTE: {len(failures)} review(s) failed and are absent from the "
              f"record: {', '.join(failures)}. {what_to_do}")
    # A moved target outranks a failed cell in the exit code: failed cells
    # leave a smaller review, while a moved target leaves one that describes
    # the wrong document, and the second is the condition a caller most needs
    # to branch on.
    if target_changed:
        return 3
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
