#!/usr/bin/env python3
"""Everything an md-review cell does except invoke its model.

WHY THIS FILE EXISTS (user-ruled 2026-08-23). The Claude and Codex cells
are meant to differ in one thing only: the invocation of the model. Every
other step -- how arguments are parsed, how the target is resolved, how
the prompt is composed, where the report is written, how a run that
produced no report is refused, and how provenance is stamped -- is the
same work, and until now it was the same work written twice. Two copies
drift; an import cannot. The cells load this module rather than repeat it.

WHAT CHANGED AND WHY, in one paragraph, because it is the reason this
module exists at all. Both cells used to capture the model's *last
message* -- Claude through `-p --output-format text`, Codex through
`--output-last-message`. Measured 2026-08-23: text a model writes before
a tool call is discarded by that capture. Given a prompt that says "say
ALPHA, read a file, say OMEGA", with the Read tool allowed exactly as the
review cells allow it, stdout held OMEGA alone. The cells hand their
reviewers Read, Grep and Glob, so a reviewer that writes findings, checks
something, then writes its closing line ships only the closing line --
which is what a real Sonnet cell did that day, emitting the trailing
"clean sections:" summary and none of the findings it asserted existed.
The fix removes the dependency instead of narrowing it: the reviewer
writes its findings to a path, and nothing depends on message-capture
semantics any more.

THE INVARIANT THIS MODULE ENFORCES, borrowed from this repository's own
production review cell (scripts/code-review-codex-cell.py): **a report
exists if and only if the run succeeded.** A run that finishes without a
report is not a review that found nothing -- it is a review that did not
happen, and it fails loudly. An empty report file is removed rather than
kept, so no later reader can mistake a stub for a clean result.

WRITES ARE DETECTED, NOT BLOCKED (user-ruled 2026-08-23). The reviewer
needs write access to produce its report, so the read-only tool set that
used to force findings through chat text is gone. What replaces it is
cheap and exact: the report goes in `md-review-records/`, which is
gitignored, so a clean `git status` after the run means the reviewer wrote
only where it was told. A tracked-file change is a stray write and is
reported. This follows the project's rule that a guard names the behavior
it defends against: the behavior here is an ordinary agent writing to the
wrong path by accident, not an attacker.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PROMPTS_DIR = REPO_ROOT / ".claude" / "skills" / "md-review" / "prompts"

CELL_CHOICES = ["restate", "defect-hunt"]
TIER_CHOICES = ["good", "floor"]


class CellRefusal(Exception):
    """A refusal that names its own fix. Carries the exit code to return."""

    def __init__(self, message: str, exit_code: int = 2):
        super().__init__(message)
        self.exit_code = exit_code


def build_argument_parser(description: str, model_help: str) -> argparse.ArgumentParser:
    """The argument surface both cells present. Identical by construction."""
    parser = argparse.ArgumentParser(
        description=description, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--cell", required=True, choices=CELL_CHOICES)
    parser.add_argument("--tier", required=True, choices=TIER_CHOICES)
    parser.add_argument(
        "--target", required=True,
        help="document path, relative to the repo root or absolute",
    )
    parser.add_argument(
        "--report", required=True,
        help="file the reviewer writes its findings to; the caller names it, "
             "and a run that leaves it absent or empty fails",
    )
    parser.add_argument("--model", help=model_help)
    return parser


def resolve_target(target_argument: str) -> pathlib.Path:
    target = pathlib.Path(target_argument)
    if not target.is_absolute():
        target = REPO_ROOT / target
    if not target.is_file():
        raise CellRefusal(f"target not found: {target}")
    return target


def resolve_report_path(report_argument: str) -> pathlib.Path:
    """The report path, made absolute and pre-cleared.

    Pre-clearing matters for the invariant: if a stale report from an
    earlier run were left in place, a run that produced nothing would be
    indistinguishable from one that succeeded.
    """
    report = pathlib.Path(report_argument)
    if not report.is_absolute():
        report = REPO_ROOT / report
    if report.exists() and not report.is_file():
        raise CellRefusal(f"report path is not a file: {report}")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.unlink(missing_ok=True)
    return report


def compose_prompt(cell: str, target: pathlib.Path, report: pathlib.Path) -> str:
    """The exact text the model receives.

    Both runtimes read the same template, so the two legs cannot drift.
    This function is also what the review harness calls to render a
    prompt for review: reviewing a hand-composed approximation would be
    reviewing a fiction that merely resembles what runs.
    """
    template_path = PROMPTS_DIR / f"{cell}.md"
    if not template_path.is_file():
        raise CellRefusal(f"prompt template missing: {template_path}")
    return (
        template_path.read_text(encoding="utf-8")
        .replace("{TARGET_PATH}", str(target))
        .replace("{REPORT_PATH}", str(report))
    )


def tracked_files_changed() -> list[str]:
    """Paths the run modified that git tracks -- i.e. stray writes.

    The report itself lives under the gitignored records directory, so a
    reviewer that wrote only where it was told leaves this empty. Reported,
    never blocked, per the ruling above.
    """
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        # Not fatal, and not silently swallowed either: the caller is told
        # the detector could not run, which is different from it passing.
        return [f"(git status failed: {completed.stderr.strip() or 'no detail'})"]
    return [line[3:] for line in completed.stdout.splitlines() if line[3:]]


def verify_report(program: str, report: pathlib.Path) -> None:
    """Enforce: a report exists iff the run succeeded.

    An absent or blank report is a review that did not happen. The blank
    file is removed so that no later reader -- and no grid that checks only
    for a file -- can read a stub as a completed review.
    """
    if not report.is_file():
        raise CellRefusal(
            f"{program}: the model exited without writing {report}. "
            "A run that produced no report is not a review that found "
            "nothing; treat it as failed and re-run.",
            exit_code=1,
        )
    if not report.read_text(encoding="utf-8").strip():
        report.unlink(missing_ok=True)
        report_name = report.name
        raise CellRefusal(
            f"{program}: the model wrote {report_name} but left it empty. "
            "The empty file has been removed so it cannot read as a clean "
            "review; treat this as failed and re-run.",
            exit_code=1,
        )


def stamp_provenance(
    report: pathlib.Path, *, runtime: str, model: str, effort: str,
    cell: str, tier: str, target_argument: str, fallback_from: str = "",
) -> None:
    """Prepend the provenance line the records convention requires.

    `model=` always names the model that actually produced the text below
    it. `fallback_from=` appears only when an earlier model in a chain
    failed, so a degraded cell is visible in the record rather than only
    in a log.
    """
    fallback_note = f"fallback_from={fallback_from} " if fallback_from else ""
    stamp = (
        f"<!-- provenance: runtime={runtime} model={model} {fallback_note}"
        f"effort={effort} cell={cell} tier={tier} target={target_argument} -->\n\n"
    )
    report.write_text(stamp + report.read_text(encoding="utf-8"), encoding="utf-8")


def run_model_chain(
    *, program: str, runtime: str, chain, effort: str, build_invocation,
    prompt: str, report: pathlib.Path, cell: str, tier: str, target_argument: str,
) -> int:
    """Try each model in turn until one produces a report; then stamp it.

    This loop is shared deliberately. It is the whole of what a cell does
    around its model, and the two runtimes' only real difference is
    `build_invocation`, which returns the argv to run and the text to feed
    on stdin (None when the runtime takes the prompt as an argument).

    A model that exits non-zero and a model that exits 0 having written no
    report are the same event here: no review was produced, so the chain
    advances. Before the report became a file the second case was
    undetectable, so a model that died quietly ended the chain with a
    clean-looking stamp.
    """
    failed_attempts: list[str] = []
    produced_by = ""
    for model in chain:
        command, stdin_text = build_invocation(model, prompt)
        # stdin MUST be closed explicitly when a runtime takes the prompt as an
        # argument. `codex exec` treats a piped-open stdin as content to append
        # and reads it to EOF before starting the turn, so an inherited
        # never-closing descriptor deadlocks the cell (measured 2026-08-03:
        # four cells frozen 24 minutes in background execution). Passing
        # input=None would leave this process's stdin inherited, so the None
        # case is spelled out rather than left to subprocess's default.
        stdin_arguments = (
            {"input": stdin_text} if stdin_text is not None
            else {"stdin": subprocess.DEVNULL}
        )
        completed = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=sys.stderr,
            cwd=REPO_ROOT,
            text=True,
            check=False,
            **stdin_arguments,
        )
        if completed.returncode != 0:
            failed_attempts.append(f"{model}(exit{completed.returncode})")
            print(f"{program}: {model} failed (exit {completed.returncode})", file=sys.stderr)
            continue
        try:
            verify_report(program, report)
        except CellRefusal as refusal:
            failed_attempts.append(f"{model}(no-report)")
            print(str(refusal), file=sys.stderr)
            continue
        produced_by = model
        break

    if not produced_by:
        print(
            f"{program}: every model for this cell failed — "
            + ", ".join(failed_attempts)
            + ". No report was produced; the cell failed rather than leaving a "
              "stub that would read as a completed review.",
            file=sys.stderr,
        )
        return 1

    if failed_attempts:
        print(
            f"{program}: fell back to {produced_by} after "
            + ", ".join(failed_attempts)
            + ". The report's provenance stamp records this.",
            file=sys.stderr,
        )

    stamp_provenance(
        report, runtime=runtime, model=produced_by, effort=effort, cell=cell,
        tier=tier, target_argument=target_argument,
        fallback_from="+".join(failed_attempts),
    )
    report_stray_writes(program)
    print(f"{program}: report written to {report}", file=sys.stderr)
    return 0


def run_cell(
    *, program: str, runtime: str, description: str, model_help: str,
    tier_to_model_chain: dict, tier_to_effort: dict, invocation_builder,
) -> int:
    """A whole cell, start to finish. Each launcher is this call plus its pins.

    Everything here is identical for both runtimes, which is the point: a
    launcher supplies its model chain, its effort mapping, and a factory that
    builds its own invocation, and nothing else. Anything that grows here
    grows for both legs at once and cannot drift between them.
    """
    parser = build_argument_parser(description, model_help)
    args = parser.parse_args()

    try:
        target = resolve_target(args.target)
        report = resolve_report_path(args.report)
        prompt = compose_prompt(args.cell, target, report)
    except CellRefusal as refusal:
        print(f"{program}: {refusal}", file=sys.stderr)
        return refusal.exit_code

    # An explicit --model is honored exactly, with no fallback: a caller who
    # names a model is answering the question the chain exists to answer, and
    # silently running a different one would defeat the request.
    chain = (args.model,) if args.model else tier_to_model_chain[args.tier]
    effort = tier_to_effort[args.tier]

    return run_model_chain(
        program=program, runtime=runtime, chain=chain, effort=effort,
        build_invocation=invocation_builder(effort), prompt=prompt,
        report=report, cell=args.cell, tier=args.tier,
        target_argument=args.target,
    )


def report_stray_writes(program: str) -> None:
    """Print stray writes, if any. Never raises: detection, not blocking."""
    stray = tracked_files_changed()
    if stray:
        print(
            f"{program}: the reviewer changed tracked files, which it should "
            f"not have — {', '.join(stray)}. The report still stands; inspect "
            "and revert these separately.",
            file=sys.stderr,
        )
