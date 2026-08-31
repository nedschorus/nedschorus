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
gitignored and therefore invisible to `git status`. Before the model runs
and again afterwards the cell records what every path `git status` names
holds, and reports the DIFFERENCE -- so a dirty tree the run did not cause
is not blamed on the reviewer, while a path the reviewer created, or edited
though it was already dirty, is named. It reports on
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
import hashlib
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


# A cell's own refusals, kept off every code its runtime produces so that a
# code coming out of a cell stays readable as whose it is. sysexits.h's
# EX_USAGE. The collision it avoids was measured on the Codex leg
# (nedschorus#162): `codex exec` itself exits 2 when it rejects a command
# line, and 2 was what a cell returned for a caller's typo, so one number
# meant both "the caller invoked this cell wrongly" and "this cell invoked its
# runtime wrongly". The measurements behind the choice of 64 are written once,
# in scripts/code-review-codex-cell.py's docstring under the heading
# EXIT CODES
#
# Both cells use it, though only the Codex leg had the collision -- the
# `claude` CLI was probed the same day and exits 1, not 2, on an unrecognized
# option. One contract for both legs is worth more than a code that differs
# per runtime for a reason nobody reading a grid's output can see, and this
# module exists precisely so the two legs cannot differ in anything but the
# invocation.
EXIT_BAD_INVOCATION = 64


class CellRefusal(Exception):
    """A refusal that names its own fix. Carries the exit code to return."""

    def __init__(self, message: str, exit_code: int = EXIT_BAD_INVOCATION):
        super().__init__(message)
        self.exit_code = exit_code


class BadInvocationArgumentParser(argparse.ArgumentParser):
    """argparse's own command-line errors join EXIT_BAD_INVOCATION.

    argparse exits 2 on a missing or unknown option, and 2 is also what
    `codex exec` returns when IT rejects a command line -- so leaving the
    default in place would keep the two layers indistinguishable for the
    commonest bad invocation there is, a mistyped flag. Usage text and
    message are argparse's, unchanged; only the exit code moves.
    """

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(EXIT_BAD_INVOCATION, f"{self.prog}: error: {message}\n")


def build_argument_parser(description: str, model_help: str) -> argparse.ArgumentParser:
    """The argument surface both cells present. Identical by construction.

    The parser is the subclass above, so a mistyped flag leaves through the
    same door as the cell's own refusals rather than through argparse's
    default 2.
    """
    parser = BadInvocationArgumentParser(
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


# The phrase both "the check did not run" messages below carry, and the
# phrase scripts/cold-read-grid.py greps a cell's stderr log for. The grid
# deletes that log on the success path, so a message it does not lift there
# is a message nobody ever reads -- and these two are the ones that say the
# run was never checked, which is the outcome likeliest to be mistaken for a
# clean one. This is a contract with that file, not a sentence to reword in
# passing: change it here and in the grid together, and
# scripts/cold-read-grid-test.py fails if only one of the two moves.
STRAY_WRITE_CHECK_SKIPPED_PHRASE = "stray writes were not checked for this run"


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
    the comparison. A cold read's ordinary subject is a draft that has not
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
    reviewer's doing. A cold read's ordinary subject is a draft that has not
    landed, so the ordinary run starts dirty and every cell of a grid would
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
        # THE LAST ATTEMPT'S REPORT, cleared here because there is no next
        # attempt to clear it. The unlink at the top of the loop empties the
        # path for the attempt about to run; a model that writes its report
        # and then exits non-zero -- the credit exhaustion this fleet hit
        # 2026-08-23, a rate limit surfacing after the tool call, an operator
        # Ctrl-C -- therefore leaves its file behind when it is the last model
        # in the chain. This program then says no report was produced while an
        # unstamped one sits in the record directory, the grid tells the
        # reviewing agent that failed reviews are absent from the record, and
        # the skill sends that agent to read every report there. The orphan is
        # read as a review, and it is the one file in the directory carrying no
        # stamp naming the model that wrote it (nedschorus#167). A report
        # exists if and only if the run succeeded: this line is where that
        # invariant is kept on the failing path.
        report.unlink(missing_ok=True)
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
        duration_s=int(time.time() - cell_started_at),
        fallback_from="+".join(failed_attempts),
        tokens=produced_tokens,
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
        cell_started_at=cell_started_at,
    )


def report_stray_writes(program: str, baseline, own_report_path=None) -> None:
    """Print what the run changed outside its report. Never raises.

    Called on every exit path, not only the successful one: a reviewer that
    edits the document under review instead of writing findings about it
    fails its cell, and the edit is then the one thing that needs cleaning
    up. Detection, never blocking, per the ruling in this module's docstring.

    `baseline` is None when the pre-run snapshot itself failed, which is
    reported as what it is rather than passed off as a clean result. Both
    ways the check can fail to run carry STRAY_WRITE_CHECK_SKIPPED_PHRASE,
    because the grid lifts those lines out of this log before deleting it.

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
        print(f"{program}: {STRAY_WRITE_CHECK_SKIPPED_PHRASE} — no pre-run "
              "snapshot of the working tree was taken. This is a failure to "
              "look, not a clean result.", file=sys.stderr)
        return
    try:
        stray = stray_writes_since(baseline, own_report_path)
    except WriteDetectorUnavailable as error:
        print(f"{program}: {STRAY_WRITE_CHECK_SKIPPED_PHRASE} — git status "
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
