#!/usr/bin/env python3
"""Everything a cold-read cell does except invoke its model.

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
cheap and exact: the report goes in `cold-read-records/`, which is
gitignored and therefore invisible to `git status`. The cell snapshots the
working tree before the model runs and again afterwards, and reports the
DIFFERENCE -- so a dirty tree the run did not cause is not blamed on the
reviewer, and a file the reviewer newly created is not missed. It reports on
every exit path, including failures, because a reviewer that edited the
document instead of reviewing it leaves an edit worth naming whether or not
it also produced a report. This follows the project's rule that a guard names the behavior
it defends against: the behavior here is an ordinary agent writing to the
wrong path by accident, not an attacker. The check is ungated by runtime,
deliberately -- see `report_stray_writes` for the incident that ruling comes
from (nedschorus#161).

A RUN REPORTS WHAT IT ACTUALLY DID (user-ruled 2026-08-25). Three of this
module's habits used to hide the run's own facts from the record it produced.
It declared "the model exited without writing" while a complete review sat one
character away in a directory the model had created itself -- so a cell now
searches the whole `cold-read-records/` tree for a file of its report's own
name before it declares failure (`recover_near_miss_report`). That search is
safe to widen because every file the grid writes into a record directory is
named for the run: `<record directory name>--<runtime>-<pass>-<tier>.md`, so
one file name belongs to one run and cannot be another run's report.
It threw away the runtime's stderr on every successful run, which is the only
channel carrying the Codex CLI's token total -- so stderr is captured and
re-emitted, and the total is parsed out of it (`parse_tokens_used`). And its
provenance stamp recorded what the cell was asked to do but nothing about what
the doing cost -- so `duration_s=`, and `tokens=` where the runtime reports
one, are now stamped alongside the model and the tier.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PROMPTS_DIR = REPO_ROOT / ".claude" / "skills" / "cold-read" / "prompts"

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


def working_tree_state() -> set:
    """Every path git reports as changed, INCLUDING untracked ones.

    Untracked paths are included because the accident this detector exists
    for -- an agent writing to a path it was not given -- most often creates
    a file rather than editing one, and `--untracked-files=no` is blind to
    exactly that. The gitignored records tree stays invisible either way,
    which is what keeps a reviewer's own report out of the result.
    """
    completed = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        raise WriteDetectorUnavailable(completed.stderr.strip() or "no detail")
    return {line[3:] for line in completed.stdout.splitlines() if line[3:]}


def stray_writes_since(baseline: set) -> list[str]:
    """Paths that changed during the run -- the DELTA, not the tree's state.

    Without a baseline this reported every already-dirty path as the
    reviewer's doing. A cold read's ordinary subject is a draft that has not
    landed, so the ordinary run starts dirty and all eight cells would
    accuse the reviewer of changes it never made. A detector that cries wolf
    on the common case is one its readers learn to skip.
    """
    return sorted(working_tree_state() - baseline)


# The phrase the grid greps this cell's stderr log for, so a recovery is
# visible on the grid's own output rather than only in a log the grid deletes
# on success. Kept as a constant because it is a contract with
# scripts/cold-read-grid.py, not a sentence anyone should reword in passing.
NEAR_MISS_RECOVERY_PHRASE = "recovered a near-miss report"


def recover_near_miss_report(
    program: str, report: pathlib.Path, attempt_started_at: float,
) -> bool:
    """Look through the records tree for this attempt's report before failing it.

    WHAT HAPPENED (2026-08-25). A Codex cell was given a report path inside
    `cold-read-records/2026-08-25-ghi-write-SKILL-prewalk-c6fb95f/` and wrote a
    complete 33-finding review into `...-c6fb95c/` -- one character different, a
    directory it created itself. The cell reported "the model exited without
    writing", which was true of the path it watched and false of the work: a
    finished review existed and the run threw it away. Losing a review to a
    typo in a directory name is not a review that did not happen.

    WHY AN EXACT NAME IS ENOUGH TO SEARCH ON, and why this looks through the
    whole tree rather than at neighbouring directories only. Every file the
    grid writes into a record directory carries the run's own name:
    `2026-08-25-ghi-write-SKILL--codex-hunt-floor.md` is written by one run and
    by no other. Before that prefix existed, every run's Codex defect-hunt cell
    on the floor tier wrote `codex-hunt-floor.md`, so two grids running at once
    in one checkout each had a file of that name -- and a cell of the first run
    that wrote nothing could pick up the second run's correctly placed report,
    move it under the first run's stamp, and leave the second run without the
    review it had produced (user-ruled 2026-08-25). With the run in the name,
    a file of the report's exact name is this run's report wherever it sits.

    WHAT IS AND IS NOT ACCEPTED. Exactly one candidate is recovered: a
    non-empty file whose name is exactly the report's own, anywhere under the
    record directory's parent -- the `cold-read-records/` tree, which includes
    a file left loose in the root of it and one inside a directory a model
    invented -- whose mtime is at or after this ATTEMPT's start, and which is
    not the expected path itself. Zero candidates is the ordinary failure and
    stays one. Two or more is refused rather than guessed at, because picking
    one would put a review under a stamp that may not describe it.

    WHY THE ATTEMPT'S START AND NOT THE CELL'S. The ruling says "since the run
    started". Per-attempt is a strict subset of that and is what keeps the
    provenance stamp honest: a chain runs several models against one report
    path, and a stray left by a model that failed would otherwise be recovered
    during a later model's attempt and stamped with the later model's name.
    The stamp must name whoever wrote the text under it.

    Either way this prints what it looked for, so a cell that fails here says
    where it searched rather than only that it found nothing.
    """
    record_dir = report.parent
    records_root = record_dir.parent
    cutoff_text = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(attempt_started_at))
    candidates = []
    for directory, _subdirectories, file_names in os.walk(records_root):
        for file_name in file_names:
            if file_name != report.name:
                continue
            candidate = pathlib.Path(directory) / file_name
            if candidate == report or not candidate.is_file():
                continue
            if candidate.stat().st_mtime < attempt_started_at:
                continue
            if not candidate.read_text(encoding="utf-8").strip():
                continue
            candidates.append(candidate)
    candidates.sort()

    if len(candidates) == 1:
        found = candidates[0]
        # move, not copy: two copies of one review under two names is the
        # ambiguity this recovery exists to remove. The directory the model
        # invented is left standing -- it is evidence of the miss, and `git
        # status` never sees it because the records tree is gitignored.
        shutil.move(str(found), str(report))
        print(
            f"{program}: {NEAR_MISS_RECOVERY_PHRASE} — the model wrote "
            f"{found} instead of {report}, elsewhere under {records_root}. "
            f"The file has been moved into place and stamped; the review "
            f"itself is intact.",
            file=sys.stderr,
        )
        return True

    found_text = (
        "nothing" if not candidates
        else "more than one, which is ambiguous and so refused: "
             + ", ".join(str(candidate) for candidate in candidates)
    )
    print(
        f"{program}: no near-miss report to recover — looked for a file named "
        f"{report.name}, modified at or after {cutoff_text}, anywhere under "
        f"{records_root}, and found {found_text}.",
        file=sys.stderr,
    )
    return False


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


# The Codex CLI ends a run with a line of the form "tokens used: 12,345", on
# stderr, which is the only stream this is ever read from -- stdout is the
# model's own words and a reviewer may write that phrase in its findings.
# The Claude CLI prints no equivalent, so a claude cell simply has no token
# figure and the stamp omits the field rather than guessing at one. The
# pattern lives here rather than in the Codex launcher because that launcher's
# one job is building an invocation -- giving it a second responsibility is
# how the two legs start to drift, which is the defect this module exists to
# prevent. A runtime that starts printing the same line gets the field for
# free.
TOKENS_USED_PATTERN = re.compile(r"tokens used[:\s]+([\d,]+)", re.IGNORECASE)


def parse_tokens_used(runtime_output: str) -> str:
    """The token total a runtime reported, or "" when it reported none.

    The LAST match wins: a CLI that prints a running count and then a total
    ends with the total. Commas are stripped so the stamp carries a number a
    reader can add up. An absent figure returns "" and the caller omits the
    field -- an omitted field reads as "not reported", and a zero would read
    as "this run cost nothing", which is never true.
    """
    matches = TOKENS_USED_PATTERN.findall(runtime_output or "")
    return matches[-1].replace(",", "") if matches else ""


def stamp_provenance(
    report: pathlib.Path, *, runtime: str, model: str, effort: str,
    cell: str, tier: str, target_argument: str, duration_s: int,
    fallback_from: str = "", tokens: str = "",
) -> None:
    """Prepend the provenance line the records convention requires.

    `model=` always names the model that actually produced the text below
    it. `fallback_from=` appears only when an earlier model in a chain
    failed, so a degraded cell is visible in the record rather than only
    in a log.

    WHAT A CELL COST IS PART OF WHAT IT DID (user-ruled 2026-08-25). Until
    that ruling the stamp recorded every input to the run -- runtime, model,
    effort, cell, tier, target -- and nothing about the run itself, so a
    record set answered "what was asked for" and could not answer "what did
    this cost". Measured that day: across six grids the only recoverable token
    figure came from the single cell that FAILED, because failure is the one
    path that kept the runtime's output. `duration_s=` is wall seconds for the
    whole cell including any failed attempts ahead of the one that worked --
    the cell's cost, not the winning model's. `tokens=` is present only when
    the runtime reported a total; see `parse_tokens_used`.

    FIELD ORDER IS DELIBERATE: `target=` stays last because its value is a
    path, and a path with a space in it would swallow whatever followed for
    any reader splitting this line on whitespace. Everything added here goes
    in front of it.
    """
    fallback_note = f"fallback_from={fallback_from} " if fallback_from else ""
    tokens_note = f"tokens={tokens} " if tokens else ""
    stamp = (
        f"<!-- provenance: runtime={runtime} model={model} {fallback_note}"
        f"effort={effort} cell={cell} tier={tier} duration_s={duration_s} "
        f"{tokens_note}target={target_argument} -->\n\n"
    )
    report.write_text(stamp + report.read_text(encoding="utf-8"), encoding="utf-8")


def run_model_chain(
    *, program: str, runtime: str, chain, effort: str, build_invocation,
    prompt: str, report: pathlib.Path, cell: str, tier: str, target_argument: str,
    baseline, cell_started_at: float,
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

    The one thing that can now put a file at that path other than the model
    writing there directly is `recover_near_miss_report`, and it keeps the
    invariant rather than bending it: it accepts only a file of this report's
    exact name -- a name that carries the run, so it belongs to no other run --
    whose mtime falls at or after the moment THIS attempt began, so what it
    moves into place was written during the attempt being judged and the stamp
    still names whoever wrote the text beneath it.
    """
    failed_attempts: list[str] = []
    produced_by = ""
    produced_tokens = ""
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
        # THE ATTEMPT'S OWN CLOCK. `recover_near_miss_report` credits a stray
        # file to this attempt only if it was written after this moment, so
        # the clock is read here -- inside the loop, after the state reset --
        # and not once for the cell. A per-cell clock would let a stray from
        # a failed model be recovered during a later model's attempt and
        # stamped with the later model's name.
        attempt_started_at = time.time()
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
        # BOTH STREAMS ARE CAPTURED, and stderr is re-emitted unconditionally.
        # stdout has been captured since 2026-08-23, when Fable ran out of
        # credits and the whole cell log came to 54 bytes -- "claude-fable-5
        # failed (exit 1)" -- with the runtime's own explanation nowhere in it;
        # the grid decides whether to tell the user his CLI is logged out by
        # searching this cell's log for the runtime's words, so a discarded
        # stream leaves that guard reading a channel that cannot carry what it
        # tests for. stderr joined it 2026-08-25: it had been passed straight
        # through to the log, which the grid DELETES on success, and it is the
        # only channel carrying the Codex CLI's token total -- so across six
        # grids that day the one recoverable token figure came from the one
        # cell that failed. Capturing costs the live stream, which nothing
        # watches: the grid redirects this into a file it reads only after the
        # process exits. Re-emitting happens before any branch below, so every
        # exit path still leaves the runtime's own words in the log.
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
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
        if completed.stderr:
            print(completed.stderr, file=sys.stderr, end="")
        if completed.returncode != 0:
            failed_attempts.append(f"{model}(exit{completed.returncode})")
            if completed.stdout:
                print(completed.stdout, file=sys.stderr)
            print(f"{program}: {model} failed (exit {completed.returncode})", file=sys.stderr)
            continue
        # The near-miss check goes HERE and not on the non-zero-exit path
        # above: the 2026-08-25 incident was a model that exited 0 having
        # written a complete review to a record directory one character from
        # the one it was given. A model that exited non-zero has told us it
        # failed, and its leavings are not a review to go looking for.
        if not report.is_file():
            recover_near_miss_report(program, report, attempt_started_at)
        try:
            verify_report(program, report)
        except CellRefusal as refusal:
            failed_attempts.append(f"{model}(no-report)")
            print(str(refusal), file=sys.stderr)
            continue
        produced_by = model
        # THIS ATTEMPT'S STDERR, and nothing else. Two narrowings, each
        # closing a way the stamp could name a cost that was not this cell's.
        # Per-attempt, because a concatenation across attempts would stamp a
        # failed model's total onto the model that succeeded. stderr only,
        # because stdout is the model's own chat text: a reviewer of a document
        # about model costs can quite reasonably write "tokens used: 12,345"
        # in its commentary, and reading stdout would stamp the reviewer's
        # sentence as the run's price. The Codex CLI prints its total on
        # stderr; a runtime that prints one elsewhere simply has no figure
        # here, which is the honest answer.
        produced_tokens = parse_tokens_used(completed.stderr or "")
        break

    if not produced_by:
        print(
            f"{program}: every model for this cell failed — "
            + ", ".join(failed_attempts)
            + ". No report was produced; the cell failed rather than leaving a "
              "stub that would read as a completed review.",
            file=sys.stderr,
        )
        report_stray_writes(program, baseline)
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
        duration_s=int(time.time() - cell_started_at),
        fallback_from="+".join(failed_attempts),
        tokens=produced_tokens,
    )
    report_stray_writes(program, baseline)
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
    # The cell's clock starts here, before anything else this program does,
    # so `duration_s=` in the stamp is the cost of the whole cell -- every
    # failed attempt in the chain included -- rather than of the attempt that
    # happened to succeed. A reader budgeting a grid wants what the cell cost
    # him, not what its last model cost.
    cell_started_at = time.time()
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

    try:
        target = resolve_target(args.target)
        report = resolve_report_path(args.report)
        prompt = compose_prompt(args.cell, target, report)
    except CellRefusal as refusal:
        print(f"{program}: {refusal}", file=sys.stderr)
        report_stray_writes(program, baseline)
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
        cell_started_at=cell_started_at,
    )


def report_stray_writes(program: str, baseline) -> None:
    """Print what the run changed outside its report. Never raises.

    Called on every exit path, not only the successful one: a reviewer that
    edits the document under review instead of writing findings about it
    fails its cell, and the edit is then the one thing that needs cleaning
    up. Detection, never blocking, per the ruling in this module's docstring.

    `baseline` is None when the pre-run snapshot itself failed, which is
    reported as what it is rather than passed off as a clean result.

    RUNTIME-AGNOSTIC ON PURPOSE, and this is the one thing not to "optimize"
    here (nedschorus#161). The fleet's other review instrument,
    scripts/sanity-check-attacks.py, gates this same comparison on
    `runtime == "codex"`, on the premise that claude cells are launched
    without a write tool and therefore cannot write. On 2026-08-21 a
    fresh-eyes claude agent wrote a 25,170-byte file into the worktree root
    during a live run and nothing reported it -- the agent disclosed the write
    itself, in the last line of its own report, and that was the only notice
    anyone got. A runtime whose compliance is never compared cannot be
    reported non-compliant. Here the call sits on the shared path both
    launchers run, so neither runtime can be skipped without deleting the call
    for both; scripts/cold-read-cell-common-test.py drives a stray write
    through each launcher so a gate cannot be reintroduced quietly.
    """
    if baseline is None:
        print(f"{program}: no pre-run snapshot, so stray writes were not "
              "checked for this run.", file=sys.stderr)
        return
    try:
        stray = stray_writes_since(baseline)
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
