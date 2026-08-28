#!/usr/bin/env python3
"""Run a full cold-read grid against a document.

One invocation = one review: eight cells ({restate, defect-hunt} x
{good, floor} x {claude, codex}) launched in parallel, every report saved
into a dated record directory, progress and next-step instructions printed
for the reviewing agent as reviews land.

Usage:
  scripts/cold-read-grid.py --target docs/drafts/foo.md

Exit codes: 0 all cells ran, 1 one or more cells failed, 2 bad invocation.
"""

import argparse
import datetime
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
commit them. Delete {record_dir} once the work it served has landed — the
findings belong in the reviewed document, the rulings in its governing
document, and this directory is the working material that produced them."""


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
    (record_dir / "reference-check.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


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
                report_path = record_dir / f"{runtime}-{pass_token}-{tier}.md"
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
                for line in stderr_path.read_text(encoding="utf-8").splitlines():
                    if "changed files outside its report" in line:
                        print(f"STRAY WRITE: {line.strip()}", flush=True)
                    if "stray writes were not checked for this run" in line:
                        print(f"WRITE CHECK DID NOT RUN: {report_path.name} — "
                              f"{line.strip()}", flush=True)
                    if "fell back to" in line:
                        print(f"FELL BACK: {report_path.name} — {line.strip()}",
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
    for runtime, launcher in CELL_LAUNCHERS.items():
        if not launcher.is_file():
            print(f"cold-read-grid: {runtime} cell launcher missing: {launcher}", file=sys.stderr)
            return 2

    record_dir = make_record_dir(target)
    reference_integrity_pre_pass(target, record_dir)

    print(f"Launched eight reviewers against {target}. Reports appear in "
          f"{record_dir} as each completes — read each as it arrives.")

    failures = wait_for_cells(launch_cells(target, record_dir))

    print()
    print(COMPLETION_INSTRUCTIONS.format(record_dir=record_dir))
    if failures:
        print(f"\nNOTE: {len(failures)} review(s) failed and are absent from the "
              f"record: {', '.join(failures)}. Rerun them singly with the cell "
              f"launchers before triage, or note their absence in dispositions.md.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
