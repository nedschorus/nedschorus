#!/usr/bin/env python3
"""Run one Codex cold-read-cell against a cold-read-target.

One invocation = one cold-read-cell — the twin of the Claude cold-read-cell
launcher (scripts/cold-read-claude-cell.py). Everything the two do apart
from invoking their model lives in scripts/cold-read-cell-common.py and is
imported by both, so the legs cannot drift. Read that file for the report
contract, the write-detection rule, and why the reviewer writes a file rather
than answering in chat.

Usage:
  scripts/cold-read-codex-cell.py --cell restate --tier second \\
      --target docs/cross-project/foo.md \\
      --report cold-read-records/foo-2026-01-01/codex-restate-second.md

The reviewer writes its findings to --report. This program prints progress
to stderr and nothing to stdout.

Exit codes: 0 a model produced a report; 1 every model in the cold-read-tier's
chain failed to produce one -- which covers every way `codex exec` itself can
fail, AND the case where codex never started at all because the binary is not
on PATH. That last one is worth naming rather than leaving implied: an
unlaunchable codex raises OSError, and left uncaught that would be a
traceback exiting 1 as well, so the same number would mean both "the chain
was tried and nothing produced a review" and "this program crashed". The
common module catches it, names the model and the error on stderr, and lets
the chain advance, so a 1 from here always means the first thing and the
stderr line says which models failed how;
64 this program refused the invocation and never launched codex (a target
that is not a file, a report path that is not a file, a missing prompt
template, or a command-line error argparse caught). 64 rather than the
conventional 2 because `codex exec` ITSELF exits 2 when it rejects a command
line, so a 2 out of this program would not say which layer refused.

CODEX'S OWN EXIT CODE IS NO LONGER PASSED THROUGH, and that changed with the
move to a report file. A failed model is now a model the chain falls back
from, so what the caller needs from the exit code is whether any model
produced a review, not which one failed how. The code codex returned, and
codex's own words, go to this program's stderr -- which the cold-read-grid keeps
whenever a cold-read-cell fails, and which is where a defect in the command this
program composes is diagnosed. The measurements behind the choice of 64, and
what an exit 0 from `codex exec` does and does not promise, are written once
in scripts/code-review-codex-cell.py's docstring under the heading
EXIT CODES

WHY THE SANDBOX IS NO LONGER READ-ONLY. This cold-read-cell used to run
`--sandbox read-only` and take the review out through
`--output-last-message`. Both legs captured only the model's final message,
and text written before a tool call is discarded by that capture (measured
2026-08-23), so a reviewer that interleaved reading and writing shipped its
closing line and none of its findings. The reviewer now writes its report
itself, which needs write access. Per the user's ruling the same day, writes
are detected rather than blocked: the report goes under the gitignored
cold-read-records/ tree, where `git status` cannot see it, and the shared
module names any other path whose content changed while the reviewer ran. It
compares content rather than the list of paths git calls dirty because a
cold-read-target is usually a draft that has not landed: the tree is
already dirty when the run starts, so "dirty afterwards too" says nothing,
while "this file holds something else now" says the reviewer wrote it
(nedschorus#167).

WHY THE CODEX MEMORY STORE IS OFF FOR REVIEW CELLS: written once, in
scripts/code-review-codex-cell.py's docstring, under that heading.

WHAT THE CODEX CLI TELLS US ABOUT COST, and where it goes (user-ruled
2026-08-25). This CLI ends a run with a line of the form "tokens used:
12,345" on stderr, and it is the only place a cold-read-cell's token cost is
stated by anyone. The shared module captures stderr, parses that line, and
stamps `tokens=` into the report's provenance line -- see `parse_tokens_used`
in scripts/cold-read-cell-common.py, which is where the pattern lives so
this launcher keeps its single job of building an invocation. If a future
CLI version reworks or drops that line, the field simply goes absent from
the stamps: an absent field reads as "not reported", which is the truth, and
nothing else in the cold-read-cell depends on it.
"""

import importlib.util
import pathlib
import sys

_common_spec = importlib.util.spec_from_file_location(
    "cold_read_cell_common", pathlib.Path(__file__).with_name("cold-read-cell-common.py")
)
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)

PROGRAM = "cold-read-codex-cell"

# cold-read-tier -> the Codex models to try, in order. Single-entry chains: an
# Anthropic credit exhaustion — the failure that gave the Claude cold-read-cell
# its fallback — does not touch these models, and no equivalent has been
# observed here. The shape is a chain anyway so both cold-read-cells
# run the same shared loop; adding a fallback is one entry, not a code
# change. The version-prefixed ids are the accepted form (user's direction
# 2026-08-11, live-verified the same day: the bare names "sol"/"luna" are
# rejected by the CLI).
#
# Both pins were re-measured by the 2026-09-03 tier-roster campaign
# (REPORT.md under
# ~/agents/cold-read-research/cold-read-records/2026-09-03-cold-read-tier-roster-campaign/,
# on that machine only and not committed, which is why the numbers are inline here; sections "Step-rule
# tally, ALL SIX TARGETS", "Aggregate over all six targets" and "Addendum
# 2026-09-04"). Sol keeps the `deep` cold-read-tier: it is in every top
# cold-read-cell set, and gpt-6-astra at max did not beat it (net -19
# unique-and-real over two designs and two runs). Luna keeps `second`:
# added to opus at max plus sol at max it lifts 238-round-1 0.89 -> 0.94 and
# 120-design 0.94 -> 0.97 at no wall-clock cost (mean 665 s, under sol's).
TIER_TO_CODEX_MODEL_CHAIN = {
    "deep": ("gpt-5.6-sol",),
    "second": ("gpt-5.6-luna",),
}

# cold-read-tier -> reasoning effort, pinned explicitly so a cold-read-cell's
# behavior never depends on the machine's own ~/.codex/config.toml default.
# xhigh for both cold-read-tiers by user calibration 2026-08-03 ("xhigh is
# OK for codex"). The `deep` cold-read-tier was raised to max on the
# 2026-09-03 campaign and PUT BACK TO XHIGH 2026-09-15 (user-ruled, "approved"), because
# the campaign measured each cold-read-cell alone and the grid is a union.
#
# What max bought, measured per cold-read-cell: sol at max beat sol at
# xhigh by +46 net unique-and-real findings. What it buys the GRID, computed
# 2026-09-15 from the same campaign's cluster tables over its six targets:
# ten findings of a 331-finding union, and three points of worst-target
# recall, 0.86 to 0.83. What it costs: this is the slowest cold-read-cell
# of the four and so sets the whole read's wall clock, mean 1339 s at max
# against 1082 s at xhigh. Every cheaper roster on the measured frontier
# gives up eighteen findings or more, so this is the one trade that sells
# little fidelity for real time. The analysis is in the log-store at
# nedlern@ned-box:/home/nedlern/nedschorus-logs/analysis/2026-09-15-cold-read-grid-union-and-effort-analysis.md
#
# The `second` cold-read-tier stays at xhigh because luna is the one model
# the step does not help: max was +8 net alone, positive on only three of six
# targets, and in the union it is worth -1. Opus and fable stay at max, where
# the union says the effort is worth 20 and 6 findings; see the claude
# cold-read-cell.
TIER_TO_REASONING_EFFORT = {
    "deep": "xhigh",
    "second": "xhigh",
}


def invocation_builder(effort: str):
    """The one thing that differs between the two cold-read-cells.

    Returns the callback the shared chain runner uses: given a model and the
    composed prompt, it yields the argv to run and the text to feed on stdin.
    Codex takes the prompt as a positional argument, so the stdin slot is
    None — which the shared runner turns into an explicitly closed stdin
    rather than an inherited one.
    """
    def build_invocation(model: str, prompt: str):
        command = [
            "codex", "exec",
            "--sandbox", "workspace-write",
            "--disable", "memories",
            "-C", str(common.REPO_ROOT),
        ]
        if model:
            command += ["-m", model]
        command += ["-c", f"model_reasoning_effort={effort}"]
        command.append(prompt)
        return command, None
    return build_invocation


# THE ONE TEXT THE `codex` AGENT-BINARY PRINTS WHEN AN ATTEMPT FAILS FOR A
# REASON IT CAN NAME (nedschorus#413, design section 4). It is not guessed:
# it is a real line, and the fixture rule (nedschorus#18, user-ruled
# 2026-09-02) wants its source beside it. It arrives on the agent-binary's
# standard error, which the shared chain runner re-emits into the
# cold-read-cell's log.
#
#   logged-out     "ERROR codex_api::endpoint::responses_websocket: failed to connect to websocket: HTTP error: 401 Unauthorized"
#       captured 2026-09-18 on ned-box (codex-cli 0.153.4) from a scratch
#       directory outside any checkout, with an empty CODEX_HOME so the real
#       login was untouched:
#       `CODEX_HOME=$(mktemp -d) codex exec --sandbox read-only --skip-git-repo-check "say hi"`,
#       exit 1, with lines of this form on stderr:
#       `2026-09-18T19:37:41.140816Z ERROR codex_api::endpoint::responses_websocket: failed to connect to websocket: HTTP error: 401 Unauthorized, url: wss://api.openai.com/v1/responses`.
#       The Codex CLI's tracing logger puts that timestamp at the head of
#       every line it logs, so the shared classifier skips an optional
#       leading timestamp and then matches by how the line starts, the one
#       exception to column-0 matching the user ruled on 2026-09-18 (walk
#       skill-sentences-and-shipper-questions-2026-09-18, item 4). The
#       prefix ends at "401 Unauthorized", before the url, which is the
#       part that may vary. Agent-binary-wide. The detail is the line after
#       its timestamp, as the Claude launcher's logged-out text is the line.
#
# No quota text has been captured from a Codex run, so a Codex quota failure
# still lands as exit-N, whose detail is the agent-binary's last stderr line,
# until a real one is captured and added here.
def recognised_failure_texts_for_model(model: str) -> list:
    del model
    return [
        common.RecognisedFailureText(
            "logged-out",
            "ERROR codex_api::endpoint::responses_websocket: failed to connect to "
            "websocket: HTTP error: 401 Unauthorized",
            common.DETAIL_IS_WHOLE_LINE),
    ]


def main() -> int:
    return common.run_cell(
        program=PROGRAM, runtime="codex", description=__doc__,
        model_help="explicit Codex model id; overrides the tier mapping",
        tier_to_model_chain=TIER_TO_CODEX_MODEL_CHAIN,
        tier_to_effort=TIER_TO_REASONING_EFFORT,
        invocation_builder=invocation_builder,
        recognised_failure_texts_for_model=recognised_failure_texts_for_model,
    )


if __name__ == "__main__":
    sys.exit(main())
