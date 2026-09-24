#!/usr/bin/env python3
"""Run one Claude cold-read-cell against a cold-read-target.

One invocation = one cold-read-cell — the twin of the Codex cold-read-cell
launcher (nc-systems/cold-read/cold-read-codex-cell.py). Everything the two do apart
from invoking their model lives in nc-systems/cold-read/cold-read-cell-common.py and is
imported by both, so the legs cannot drift. Read that file for the report
contract, the write-detection rule, and why the reviewer writes a file rather
than answering in chat.

Usage:
  nc-systems/cold-read/cold-read-claude-cell.py --cell restate --tier second \\
      --target docs/drafts/foo.md \\
      --report cold-read-records/foo-2026-01-01/claude-restate-second.md

The reviewer writes its findings to --report. This program prints progress
to stderr and nothing to stdout.

Exit codes: 0 a model produced a report; 1 every model in the cold-read-tier's
chain failed to produce one; 64 this program refused the invocation and never
launched a model, naming its own fix. 64 rather than the conventional 2 for the
reason written beside EXIT_BAD_INVOCATION in nc-systems/cold-read/cold-read-cell-common.py,
which both cold-read-cells share.

WHY A CLAUDE COLD-READ-CELL'S STAMP CARRIES NO `tokens=` FIELD. Every stamp
records `duration_s=` (user-ruled 2026-08-25), and Codex cold-read-cells also
record `tokens=` because the Codex CLI prints a total. The Claude CLI prints
no equivalent, so there is no figure to record and the field is omitted rather
than filled with a zero -- an omitted field reads as "not reported", a zero
would read as "this cold-read-cell cost nothing". If the CLI starts printing a
"tokens used" line, the shared parser in nc-systems/cold-read/cold-read-cell-common.py picks
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
# as models change. User-picked (`deep` = Opus-class, `second` = Fable-class,
# ruled 2026-09-04; the `deep` cold-read-tier was Opus-class until 2026-08-17,
# Fable-class from then until the 2026-08-25 ruling below, and Opus-class
# since; `second` was Sonnet-class from 2026-08-25 until the 2026-09-04
# ruling); the fable-5-1 id verified by the 2026-09-03 campaign's smoke run and
# the opus-5-5 id by the 2026-09-23 effort sweep's (each provenance stamp
# carried the requested model and effort, no fallback).
#
# WHY THE `second` COLD-READ-TIER IS FABLE, NOT SONNET (user-ruled
# 2026-09-04). This tier was called `floor` until the user renamed it on
# 2026-09-20; the rename's provenance is written once, at TIER_CHOICES in
# nc-systems/cold-read/cold-read-cell-common.py. Sonnet was cut as a reviewer in the
# 2026-08-29 walk-reviewer model trial ("cut as reviewer
# (bottom of every ranking)", METHOD.md of that trial under
# ~/agents/MD-skills/cold-read-records/2026-08-29-walk-reviewer-model-trial/;
# its REPORT.md measured `sonnet defect-hunt` reproducing 0.14 of its own
# previous run's findings). The pin here was never revisited after that
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
# target, so it is the `second` cold-read-tier, not the `deep` one ("THE
# ANSWERS" section 2). "claude-fable-5" is obsolete (user, 2026-09-04: "fable 5 is now
# obsolete. 5.1 is current"); the campaign measured claude-fable-5-1.
#
# When the account's Fable limit is hit (2026-08-23; four cold-read-cells
# on 2026-09-03) the `second` cold-read-cell has no further model to try: it
# fails with the cause model-limit, the cold-read-grid retries it once and,
# when the retry fails too, lists the report as absent in its closing text
# and exits 1 with the set valid and incomplete (user-ruled 2026-09-04: "If
# fable is not available, just note that and continue"; 2026-09-11: no
# cell is special, nedschorus#413). A Sonnet fallback would make the cold-read-cell count
# come out while running a retired reviewer under a `second`-tier stamp, which
# the user ruled worse than a visible failure (2026-08-25: "I just don't
# want it to fail silently").
#
# WHY OPUS LEADS THE `deep` COLD-READ-TIER (user-ruled 2026-08-25: "If opus
# is better, we should switch to that."). Measured that day by running the
# `deep`-tier Claude slot both ways over the same documents: Opus produced 44
# findings against Fable's 24 on one document, and 38 against 21 on the other.
# Whole-run coverage was unchanged — the other seven cold-read-cells found what
# they found either way — so what the swap buys is depth in this one slot, not
# a wider cold-read-cell roster.
#
# WHY OPUS 5.5, NOT OPUS 5 (user-ruled 2026-09-24: "Yes use opus 5.5"). The
# 2026-09-23 effort sweep ran both under the same launchers and prompt, two
# runs on four targets: claude-opus-5-5 at xhigh beat claude-opus-5 at max
# by +10 net unique-and-real findings, positive on three of the four, tied
# it in the four-seat roster union (242 against 244 real findings) and ran
# faster (mean 1032 s against 1103 s). The record is in the log-store at
# nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/2026-09-23-effort-sweep-opus-5-5-gpt-6-sol/REPORT.md
# ("The instrument controls" and "THE ANSWERS").
#
# WHY THE `deep` COLD-READ-TIER HAS NO FALLBACK (user-ruled 2026-09-04: "opus
# falling back to fable is not valid. If opus fails we stop working and wait
# for it to come back"). From 2026-08-23 to 2026-09-04 the `deep`
# cold-read-tier was a chain, Opus then Fable, so the Fable credit exhaustion
# of 2026-08-23 (two cold-read-cells of eight lost) would not degrade a
# cold-read-full-run into a manual per-cell rerun. The 2026-09-04 ruling
# reverses that trade: an Opus outage is a reason to stop the read, not to run
# it on a different model, because a review stamped as the `deep`
# cold-read-tier must be the `deep` cold-read-tier's model. What happens next
# is no longer Opus's own case (user-ruled 2026-09-11, nedschorus#413: "why is
# opus special? I don't think it should be"): the cold-read-grid retries the
# cell once on the same model, reports the report absent like any other, and
# when every Claude cell is absent for one agent-binary-wide cause says once
# that the agent-binary is down (nc-systems/cold-read/cold-read-grid.py).
#
# Every cold-read-tier on both runtimes is therefore a single-entry chain. The
# tuple shape and the shared chain loop in nc-systems/cold-read/cold-read-cell-common.py
# stay: the loop is what clears the report path before an attempt and after
# a failed last one, which is needed with one model as with two, and a second
# entry is one line if a ruling ever wants one. The cold-read-grid's FELL BACK
# line and the stamp's `fallback_from=` field stay for the same reason; no
# pinned chain can produce them today.
TIER_TO_CLAUDE_MODEL_CHAIN = {
    "deep": ("claude-opus-5-5",),
    "second": ("claude-fable-5-1",),
}

# cold-read-tier -> reasoning effort, pinned explicitly so a cold-read-cell's
# behavior never depends on the machine's own default. Accepted levels today:
# low, medium, high, xhigh, max. Recalibrating is the user's call, here.
#
# `deep` is xhigh (user-ruled 2026-09-24, the effort sweep REPORT.md cited
# above, "Within-model effort steps" and "THE ANSWERS"). Over the 2026-09-03
# campaign's six targets, two runs each: claude-opus-5-5 at xhigh beat it at
# high by +58 net unique-and-real findings, positive on all six, and added
# 13 real findings to the four-seat roster union; at max it scored -7
# against xhigh, added nothing to the union, and took 1754 s mean against
# 937 s.
#
# `second` is max (user-ruled 2026-09-04 on the 2026-09-03 tier-roster
# campaign, REPORT.md path above, "Step-rule tally, ALL SIX TARGETS" and
# "THE ANSWERS" section 2): fable at max beat fable at high by +63 net
# unique-and-real findings, positive on every target. Reaffirmed 2026-09-15
# against the union, which is the number that decides a grid: computed from
# the same campaign's cluster tables, fable at max is worth 6 findings of a
# 331-finding union and contributes 14 no other cold-read-cell found. The
# analysis is in the log-store at
# nedlern@ned-box:/home/nedlern/nedschorus-logs/analysis/2026-09-15-cold-read-grid-union-and-effort-analysis.md
# The same campaign put claude-opus-5 at max for `deep` (+70 over high,
# worst-target recall 0.64 -> 0.79; first published as 0.56 -> 0.72, a
# scorer bug the 2026-09-23 sweep found and corrected, its incident 1).
TIER_TO_REASONING_EFFORT = {
    "deep": "xhigh",
    "second": "max",
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


def model_family_name(model: str) -> str:
    """`claude-fable-5-1` -> `Fable`, `claude-opus-5` -> `Opus`: the word the
    `claude` agent-binary's model-limit message uses for the model."""
    parts = model.split("-")
    return parts[1].capitalize() if len(parts) > 1 and parts[1] else model


# THE TEXTS THE `claude` AGENT-BINARY PRINTS WHEN AN ATTEMPT FAILS FOR A REASON
# IT CAN NAME (nedschorus#413, design section 4). None is guessed: each is a
# real line, and the fixture rule (nedschorus#18, user-ruled 2026-09-02)
# wants its source beside it. All three arrive on the agent-binary's standard
# output, which the shared chain runner re-emits into the cold-read-cell's
# log, and each is matched only by how a line starts.
#
#   account-limit  "You've hit your session limit · resets 8:50pm (America/Los_Angeles)"
#       line 2 of nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/2026-09-10-design-to-main-test-writing-agent-instructions/2026-09-10-design-to-main-test-writing-agent-instructions--claude-hunt-good.md.stderr.log,
#       from nc-systems/cold-read/cold-read-grid.py launching this program on the Mac,
#       2026-09-10. Agent-binary-wide: the same limit fails every Claude cell.
#       The detail is the rest of the line, "resets 8:50pm (America/Los_Angeles)".
#   model-limit    "You've reached your Fable limit. Switch to another model, or manage usage credits at claude.ai/settings/usage?from=cc_cli_limit_message, to continue."
#       line 2 of nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/2026-09-11-SKILL-2/2026-09-11-SKILL-2--claude-hunt-floor.md.stderr.log,
#       the same launch on the Mac, 2026-09-11. That model only: on
#       2026-09-11 the Fable cell failed on it while both Opus cells landed.
#       The prefix names the attempt's model family, and the detail is that
#       family name.
#   logged-out     "Not logged in · Please run /login"
#       captured 2026-09-18 on ned-box (Claude Code 2.1.272) from a scratch
#       directory outside any checkout, with an empty configuration
#       directory so the real login was untouched:
#       `CLAUDE_CONFIG_DIR=$(mktemp -d) claude -p "say hi"`, exit 1, that
#       line on stdout, stderr empty. Agent-binary-wide. The detail is the line.
def recognised_failure_texts_for_model(model: str) -> list:
    family = model_family_name(model)
    return [
        common.RecognisedFailureText(
            "account-limit", "You've hit your session limit",
            common.DETAIL_IS_REST_OF_LINE),
        common.RecognisedFailureText(
            "model-limit", f"You've reached your {family} limit", family),
        common.RecognisedFailureText(
            "logged-out", "Not logged in", common.DETAIL_IS_WHOLE_LINE),
    ]


def main() -> int:
    return common.run_cell(
        program=PROGRAM, runtime="claude", description=__doc__,
        model_help="explicit Claude model id; overrides the tier mapping",
        tier_to_model_chain=TIER_TO_CLAUDE_MODEL_CHAIN,
        tier_to_effort=TIER_TO_REASONING_EFFORT,
        invocation_builder=invocation_builder,
        recognised_failure_texts_for_model=recognised_failure_texts_for_model,
    )


if __name__ == "__main__":
    sys.exit(main())
