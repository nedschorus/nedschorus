#!/usr/bin/env python3
"""Run one Claude cold-read-cell against a cold-read-target.

One invocation = one cold-read-cell — the twin of the Codex cold-read-cell
launcher (scripts/cold-read-codex-cell.py). Everything the two do apart
from invoking their model lives in scripts/cold-read-cell-common.py and is
imported by both, so the legs cannot drift. Read that file for the report
contract, the write-detection rule, and why the reviewer writes a file rather
than answering in chat.

Usage:
  scripts/cold-read-claude-cell.py --cell restate --tier floor \\
      --target docs/drafts/foo.md \\
      --report cold-read-records/foo-2026-01-01/claude-restate-floor.md

The reviewer writes its findings to --report. This program prints progress
to stderr and nothing to stdout.

Exit codes: 0 a model produced a report; 1 every model in the cold-read-tier's
chain failed to produce one; 64 this program refused the invocation and never
launched a model, naming its own fix. 64 rather than the conventional 2 for the
reason written beside EXIT_BAD_INVOCATION in scripts/cold-read-cell-common.py,
which both cold-read-cells share.

WHY A CLAUDE COLD-READ-CELL'S STAMP CARRIES NO `tokens=` FIELD. Every stamp
records `duration_s=` (user-ruled 2026-08-25), and Codex cold-read-cells also
record `tokens=` because the Codex CLI prints a total. The Claude CLI prints
no equivalent, so there is no figure to record and the field is omitted rather
than filled with a zero -- an omitted field reads as "not reported", a zero
would read as "this cold-read-cell cost nothing". If the CLI starts printing a
"tokens used" line, the shared parser in scripts/cold-read-cell-common.py picks
it up with no change here.
"""

import importlib.util
import json
import pathlib
import sys

_common_spec = importlib.util.spec_from_file_location(
    "cold_read_cell_common", pathlib.Path(__file__).with_name("cold-read-cell-common.py")
)
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)

PROGRAM = "cold-read-claude-cell"

# cold-read-tier -> the Claude models to try, in order. One place to update
# as models change. User-picked (good = Opus-class, floor = Fable-class,
# ruled 2026-09-04; the good cold-read-tier was Opus-class until 2026-08-17,
# Fable-class from then until the 2026-08-25 ruling below, and Opus-class
# since; the floor was Sonnet-class from 2026-08-25 until the 2026-09-04
# ruling); the opus id verified against live subagent transcripts 2026-08-04,
# the fable-5-1 id by the 2026-09-03 campaign's smoke run (its provenance stamp
# carried the requested model and effort, no fallback).
#
# WHY THE FLOOR IS FABLE, NOT SONNET (user-ruled 2026-09-04). Sonnet was cut
# as a reviewer in the 2026-08-29 walk-reviewer model trial ("cut as reviewer
# (bottom of every ranking)", METHOD.md of that trial under
# ~/agents/MD-skills/cold-read-records/2026-08-29-walk-reviewer-model-trial/;
# its REPORT.md measured `sonnet defect-hunt` reproducing 0.14 of its own
# previous run's findings). The floor pin here was never revisited after that
# cut, so the cold-read-grid kept launching a cold-read-cell the trial
# had retired. The 2026-09-03 tier-roster campaign (REPORT.md under
# ~/agents/cold-read-research/cold-read-records/2026-09-03-cold-read-tier-roster-campaign/,
# on that machine only and not committed, which is why the numbers are inline
# here) ran no Sonnet cold-read-cell at all, on the user's ruling that dead
# cold-read-cells are not retried. Its measured second Claude cold-read-cell is
# claude-fable-5-1 at max: added to opus-max + sol-max it lifts pairG 0.83 ->
# 0.89 (the other five targets unchanged) at no wall-clock cost (mean 1009 s,
# under sol-max's 1339 s), and beats fable at high by +63 net unique-and-real
# findings, positive on all six targets ("Step-rule tally, ALL SIX TARGETS";
# "Aggregate over all six targets"). Fable does not beat opus-max on any
# target, so it is the floor, not the good cold-read-tier ("THE ANSWERS"
# section 2). "claude-fable-5" is obsolete (user, 2026-09-04: "fable 5 is now
# obsolete. 5.1 is current"); the campaign measured claude-fable-5-1.
#
# When the account's Fable limit is hit (2026-08-23; four cold-read-cells
# on 2026-09-03) the floor cold-read-cell has no further model to try: it
# fails, the cold-read-grid prints its FAILED line, tells the reviewing
# agent to note the absence and continue with the five reports that landed,
# and exits 1 (user-ruled 2026-09-04: "If fable is not available, just note
# that and continue"). A Sonnet fallback would make the cold-read-cell count
# come out while running a retired reviewer under a floor-tier stamp, which
# the user ruled worse than a visible failure (2026-08-25: "I just don't
# want it to fail silently").
#
# WHY OPUS LEADS THE GOOD COLD-READ-TIER (user-ruled 2026-08-25: "If opus
# is better, we should switch to that."). Measured that day by running the
# good-tier Claude slot both ways over the same documents: Opus produced 44
# findings against Fable's 24 on one document, and 38 against 21 on the other.
# Whole-run coverage was unchanged — the other seven cold-read-cells found what
# they found either way — so what the swap buys is depth in this one slot, not
# a wider cold-read-cell roster.
#
# WHY THE GOOD COLD-READ-TIER HAS NO FALLBACK (user-ruled 2026-09-04: "opus
# falling back to fable is not valid. If opus fails we stop working and wait
# for it to come back"). From 2026-08-23 to 2026-09-04 the good cold-read-tier
# was a chain, Opus then Fable, so the Fable credit exhaustion of 2026-08-23
# (two cold-read-cells of eight lost) would not degrade a cold-read-full-run
# into a manual per-cell rerun. The 2026-09-04 ruling reverses that trade:
# an Opus outage is a reason to stop the read, not to run it on a different
# model, because a review stamped as the good cold-read-tier must be the
# good cold-read-tier's model. The cold-read-grid's closing text says to wait
# for Opus and run the cold-read-grid again (scripts/cold-read-grid.py, the
# closing block of main()).
#
# Every cold-read-tier on both runtimes is therefore a single-entry chain. The
# tuple shape and the shared chain loop in scripts/cold-read-cell-common.py
# stay: the loop is what clears the report path before an attempt and after
# a failed last one, which is needed with one model as with two, and a second
# entry is one line if a ruling ever wants one. The cold-read-grid's FELL BACK
# line and the stamp's `fallback_from=` field stay for the same reason; no
# pinned chain can produce them today.
TIER_TO_CLAUDE_MODEL_CHAIN = {
    "good": ("claude-opus-5",),
    "floor": ("claude-fable-5-1",),
}

# cold-read-tier -> reasoning effort, pinned explicitly so a cold-read-cell's
# behavior never depends on the machine's own default. Accepted levels today:
# low, medium, high, xhigh, max. "max" for both cold-read-tiers (user-ruled
# 2026-09-04 on the 2026-09-03 tier-roster campaign, REPORT.md path above,
# "Step-rule tally, ALL SIX TARGETS" and "THE ANSWERS" section 2): opus at max
# beat opus at high by +70 net unique-and-real findings over two runs and six
# targets, positive on every target, with the cold-read-cell's worst-target
# recall rising 0.56 -> 0.72 and no precision cost (0.18 against 0.20 pooled);
# fable at max beat fable at high by +63, positive on every target. Time
# roughly doubles (opus mean 757 -> 1047 s) and stays under the Codex good
# cold-read-cell's. Recalibrating is the user's call, here.
#
# REAFFIRMED 2026-09-15 against the union, which is the number that decides a
# grid: those figures measure a cold-read-cell alone, and what matters is
# what a cold-read-cell adds to what the others already found. Computed
# from the same campaign's cluster tables over its six targets, opus
# at max is worth 20 findings of a 331-finding union and 14 points of
# worst-target recall against opus at high, and it contributes 34 findings
# no other cold-read-cell in the grid found, more than twice any other
# cold-read-cell. Fable at max is worth 6, and contributes 14. Both stay
# at max. The Codex good cold-read-tier went the other way on the same
# analysis; its own comment says why. The analysis is in the log-store at
# nedlern@ned-box:/home/nedlern/nedschorus-logs/analysis/2026-09-15-cold-read-grid-union-and-effort-analysis.md
TIER_TO_REASONING_EFFORT = {
    "good": "max",
    "floor": "max",
}

# The reviewer reads the cold-read-target and writes one file: its report.
# Write is present because the report is a file now — the common module
# explains why writes are detected rather than blocked.
ALLOWED_TOOLS = "Read,Grep,Glob,Write"

# Bash is DENIED, which is not the same as leaving it out of ALLOWED_TOOLS
# above (measured 2026-09-14). A cold-read-cell inherits the machine's
# permission mode, and under "auto" every tool is already approved,
# so --allowedTools adds rather than restricts: in the 2026-09-14
# cold-read-full-run all three Claude cold-read-cells used Bash for every
# one of their 5 to 22 tool calls and the Read, Grep and Glob they were given
# exactly zero times. That matters because the mode also carries an instruction
# to read files with cat rather than the Read tool, and a whole-script cat
# overflows the tool result: the fable cold-read-cell spilled six results
# to disk and spent about five minutes reading them back in 300-line slices.
# Denying Bash returns the cold-read-cell to the four tools this program
# chose for it; smoke-checked 2026-09-15, the cold-read-cell answers from
# the Read tool instead.
DISALLOWED_TOOLS = "Bash"

# Every hook is switched off for the reviewer's session, and only for it: the
# seat that started the cold read keeps its own. A reviewer runs inside this
# repository, so without this it runs the project's hooks, and two misfired
# inside reviewers on 2026-09-16. The session-location write guard refused a
# reviewer's report because the checkout was on a detached HEAD, and the
# checkout-freshness Stop hook rebased the author's unpushed branch while the
# other reviewers were still reading. The same Stop hook's note displaced two
# sanity-check reviews on 2026-09-15, in the issue "A Stop hook's report
# inside a claude -p review cell displaces the cell's report"
# (https://github.com/nedschorus/nedschorus/issues/397).
#
# Hooks only, not --setting-sources user (user-ruled 2026-09-18): CLAUDE.md
# still loads, because the reviewer stands in for an agent of this project,
# and those agents read it; it is also where they learn the glossary's path.
# The write guards this drops are covered by the common module's check for
# files changed outside the report, the same check the Codex cells rely on.
# Measured 2026-09-18 in a detached checkout of main: without this setting
# the write guard blocked a reviewer's Write; with it the Write went through,
# and the reviewer still gave the glossary path CLAUDE.md names.
SETTINGS = json.dumps({"disableAllHooks": True})


def invocation_builder(effort: str):
    """The one thing that differs between the two cold-read-cells.

    Returns the callback the shared chain runner uses: given a model and the
    composed prompt, it yields the argv to run and the text to feed on stdin.

    The prompt travels via stdin, not as a positional argument: the CLI's
    variadic options (--allowedTools) swallow a trailing positional
    (measured 2026-08-05: the cold-read-cell ran with no input at all), and
    subprocess.run(input=...) writes stdin and closes it, so the
    inherited-open-stdin deadlock class is avoided by construction.
    """
    def build_invocation(model: str, prompt: str):
        command = [
            "claude", "-p",
            "--model", model,
            "--effort", effort,
            "--output-format", "text",
            "--allowedTools", ALLOWED_TOOLS,
            "--disallowedTools", DISALLOWED_TOOLS,
            "--settings", SETTINGS,
        ]
        return command, prompt
    return build_invocation


def main() -> int:
    return common.run_cell(
        program=PROGRAM, runtime="claude", description=__doc__,
        model_help="explicit Claude model id; overrides the tier mapping",
        tier_to_model_chain=TIER_TO_CLAUDE_MODEL_CHAIN,
        tier_to_effort=TIER_TO_REASONING_EFFORT,
        invocation_builder=invocation_builder,
    )


if __name__ == "__main__":
    sys.exit(main())
