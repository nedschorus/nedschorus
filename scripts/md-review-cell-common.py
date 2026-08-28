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
gitignored and therefore invisible to `git status`. Before the model runs
and again afterwards the cell records what every path `git status` names
holds, and reports the DIFFERENCE -- so a dirty tree the run did not cause
is not blamed on the reviewer, while a path the reviewer created, or edited
though it was already dirty, is named. It reports on
every exit path, including failures, because a reviewer that edited the
document instead of reviewing it leaves an edit worth naming whether or not
it also produced a report. This follows the project's rule that a guard names the behavior
it defends against: the behavior here is an ordinary agent writing to the
wrong path by accident, not an attacker.
"""

from __future__ import annotations

import argparse
import hashlib
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


class WriteDetectorUnavailable(Exception):
    """git status could not answer, so nothing was detected either way.

    Raised rather than returned as a path-shaped string: a caller that
    printed such a string told the operator to "inspect and revert" a
    sentence, which reads as a stray write that never happened. Failing to
    look and looking and finding nothing are different outcomes and must
    not share a representation.
    """


def path_content_fingerprint(path: pathlib.Path) -> str:
    """What one path holds right now, as a short string to compare later.

    Content rather than mtime: a tool that writes a file and puts its old
    text back leaves a changed mtime and an unchanged document, and that is
    not the event this guard exists for.

    A path that is missing, a directory, or unreadable gets a marker rather
    than a hash, so those states stay distinct from each other and from any
    file content: a path absent at the baseline and holding a file afterwards
    is a creation, not two markers that happen to differ. Read in blocks
    because an untracked path git names here can be any size.
    """
    if path.is_dir():
        return "directory"
    fingerprint = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1 << 16), b""):
                fingerprint.update(block)
    except FileNotFoundError:
        return "absent"
    except OSError as error:
        return f"unreadable:{type(error).__name__}"
    return fingerprint.hexdigest()


def working_tree_state() -> set:
    """Every path git reports as changed, INCLUDING untracked ones, each
    paired with a fingerprint of what that path holds.

    CONTENT, NOT NAMES, and that is the whole point of the pairing. A
    snapshot of names alone cannot see an edit to a path that was already
    dirty when it was taken: the name is in both snapshots and cancels out of
    the comparison. md-review's ordinary subject is a draft that has not
    landed, so the document under review -- the very file a reviewer is most
    likely to edit by accident -- is normally already dirty, and the detector
    was blind in exactly the case it exists for (measured on nedschorus#167:
    a reviewer edit inside an already-dirty file yielded an empty delta,
    while a file it newly created was reported).

    Untracked paths are included because the accident this detector exists
    for -- an agent writing to a path it was not given -- often creates a
    file rather than editing one, and `--untracked-files=no` is blind to
    exactly that. They are asked for one file at a time
    (`--untracked-files=all`) rather than in git's default form: the default
    collapses an untracked directory to the directory's name, so a file
    created inside a directory that was already untracked would be invisible
    here too. Naming each file also lets a caller subtract one exact path --
    which is how a cell keeps its own report out of the result when the
    report was written somewhere git can see. The gitignored records tree,
    where reports ordinarily go, stays invisible either way.
    """
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        raise WriteDetectorUnavailable(completed.stderr.strip() or "no detail")
    return {
        (name, path_content_fingerprint(REPO_ROOT / name))
        for name in (line[3:] for line in completed.stdout.splitlines())
        if name
    }


def repo_relative_name(path) -> str:
    """git's name for a path inside this repository; "" for anything else.

    Anything else is: no path at all (a cell that failed before it resolved
    one), and a path outside the repository, which git never names and so
    never needs subtracting.
    """
    if path is None:
        return ""
    try:
        return str(pathlib.Path(path).resolve().relative_to(REPO_ROOT))
    except ValueError:
        return ""


def stray_writes_since(baseline: set, own_report_path=None) -> list[str]:
    """Paths that changed during the run -- the DELTA, not the tree's state.

    Without a baseline this reported every already-dirty path as the
    reviewer's doing. md-review's ordinary subject is a draft that has not
    landed, so the ordinary run starts dirty and all eight cells would
    accuse the reviewer of changes it never made. A detector that cries wolf
    on the common case is one its readers learn to skip.

    The cell's own report is subtracted, because writing it is the one write
    the reviewer was asked for. It ordinarily needs no subtracting -- reports
    go under the gitignored records tree, which git never names -- but the
    grid's failure note tells the operator to rerun a failed cell singly with
    the cell launchers, and an operator who then points --report somewhere
    git can see was told to revert the review he had just asked for
    (nedschorus#167).
    """
    changed = {name for name, _fingerprint in working_tree_state() - baseline}
    changed.discard(repo_relative_name(own_report_path))
    return sorted(changed)


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
    baseline,
) -> int:
    """Try each model in turn until one produces a report; then stamp it.

    This loop is shared deliberately. It is the whole of what a cell does
    around its model, and the two runtimes' only real difference is
    `build_invocation`, which returns the argv to run and the text to feed
    on stdin (None when the runtime takes the prompt as an argument).

    THE MACHINE, stated once so the code below can be checked against it.
    The report path is the only state variable. Every attempt begins with it
    empty (the unlink at the top of the loop), so a non-empty file at that
    path was written by the attempt now being judged and by no other. An
    attempt ends in exactly one of three states: it produced a report, which
    is the accepting state and leaves the loop; it produced none, whether by
    exiting non-zero, by exiting 0 having written nothing, or by never
    starting at all; or it raised, which the OSError handler turns into the
    second. All three non-accepting cases are the same event -- no review was
    produced -- so the chain advances. Before the report became a file, "exited
    0 having written nothing" was indistinguishable from success, so a model
    that died quietly ended the chain with a clean-looking stamp.
    """
    failed_attempts: list[str] = []
    produced_by = ""
    for model in chain:
        # THE STATE RESET, and the reason this loop is safe to read. The report
        # path is this chain's only state variable, and `verify_report` below
        # asks one question of it: does a non-empty file exist here? That
        # question is answerable only if the file can have been written by THIS
        # attempt and no other. A model that writes its report and then exits
        # non-zero -- a post-turn error, a rate limit surfacing after the tool
        # call, an operator Ctrl-C -- would otherwise leave its text for the
        # next model to be credited with, and the stamp would name a model that
        # did not write what sits under it. Clearing here rather than on the
        # failure paths covers every way an attempt can end, including ones
        # nobody enumerated. It cannot destroy a good report: a successful
        # attempt breaks out of the loop before another begins.
        report.unlink(missing_ok=True)
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
        # stdout is CAPTURED, not discarded, and re-emitted when an attempt
        # fails. The grid decides whether to tell the user his CLI is logged out
        # by searching this cell's stderr log for the runtime's own words, so
        # sending them to DEVNULL leaves that guard reading a channel that can
        # never carry what it tests for. Measured 2026-08-23: when Fable ran out
        # of credits the whole log was 54 bytes -- "claude-fable-5 failed (exit
        # 1)" -- and the runtime's explanation was nowhere in it.
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=sys.stderr,
                cwd=REPO_ROOT,
                text=True,
                check=False,
                **stdin_arguments,
            )
        except OSError as error:
            # Most often the runtime binary is not on PATH. Left uncaught this
            # is a traceback exiting 1, which is the code this program
            # documents as "every model in the chain failed" -- a refusal that
            # names its own cause is worth more than that collision.
            failed_attempts.append(f"{model}({type(error).__name__})")
            print(f"{program}: {model} could not be run: {error}", file=sys.stderr)
            continue
        if completed.returncode != 0:
            failed_attempts.append(f"{model}(exit{completed.returncode})")
            if completed.stdout:
                print(completed.stdout, file=sys.stderr)
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
        report_stray_writes(program, baseline, report)
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
    report_stray_writes(program, baseline, report)
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

    # The baseline is taken BEFORE anything runs, so what the detector reports
    # afterwards is what this run changed rather than what the tree already
    # held. A snapshot that cannot be taken yields None, which every reader
    # below treats as "not checked" rather than as "nothing found".
    try:
        baseline = working_tree_state()
    except WriteDetectorUnavailable as error:
        baseline = None
        print(f"{program}: could not snapshot the working tree ({error}); "
              "stray writes will not be checked for this run.", file=sys.stderr)

    # None until resolve_report_path returns one: a refusal raised before that
    # point still reports stray writes, and there is no report path to
    # subtract from them yet.
    report = None
    try:
        target = resolve_target(args.target)
        report = resolve_report_path(args.report)
        prompt = compose_prompt(args.cell, target, report)
    except CellRefusal as refusal:
        print(f"{program}: {refusal}", file=sys.stderr)
        report_stray_writes(program, baseline, report)
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
        target_argument=args.target, baseline=baseline,
    )


def report_stray_writes(program: str, baseline, own_report_path=None) -> None:
    """Print what the run changed outside its report. Never raises.

    Called on every exit path, not only the successful one: a reviewer that
    edits the document under review instead of writing findings about it
    fails its cell, and the edit is then the one thing that needs cleaning
    up. Detection, never blocking, per the ruling in this module's docstring.

    `baseline` is None when the pre-run snapshot itself failed, which is
    reported as what it is rather than passed off as a clean result.
    """
    if baseline is None:
        print(f"{program}: no pre-run snapshot, so stray writes were not "
              "checked for this run.", file=sys.stderr)
        return
    try:
        stray = stray_writes_since(baseline, own_report_path)
    except WriteDetectorUnavailable as error:
        print(f"{program}: could not check for stray writes — git status "
              f"failed ({error}). This is a failure to look, not a clean "
              "result.", file=sys.stderr)
        return
    if stray:
        print(
            f"{program}: the reviewer changed files outside its report, which "
            f"it should not have — {', '.join(stray)}. Inspect and revert "
            "these before triage; any report still stands on its own.",
            file=sys.stderr,
        )
