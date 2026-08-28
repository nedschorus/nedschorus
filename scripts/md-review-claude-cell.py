#!/usr/bin/env python3
"""Run one Claude cell of an md-review grid against a document.

One invocation = one cell — the twin of the Codex cell launcher
(scripts/md-review-codex-cell.py). Everything the two do apart from
invoking their model lives in scripts/md-review-cell-common.py and is
imported by both, so the legs cannot drift. Read that file for the report
contract, the write-detection rule, and why the reviewer writes a file
rather than answering in chat.

Usage:
  scripts/md-review-claude-cell.py --cell restate --tier floor \\
      --target docs/drafts/foo.md \\
      --report md-review-records/2026-01-01-foo/claude-restate-floor.md

The reviewer writes its findings to --report. This program prints progress
to stderr and nothing to stdout.

Exit codes: 0 a model produced a report; 1 every model in the tier's chain
failed to produce one; 64 this program refused the invocation and never
launched a model, naming its own fix. 64 rather than the conventional 2 for
the reason written beside EXIT_BAD_INVOCATION in
scripts/md-review-cell-common.py, which both cells share.
"""

import importlib.util
import pathlib
import sys

_common_spec = importlib.util.spec_from_file_location(
    "md_review_cell_common", pathlib.Path(__file__).with_name("md-review-cell-common.py")
)
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)

PROGRAM = "md-review-claude-cell"

# Tier -> the Claude models to try, in order. One place to update as models
# change. User-picked (good = Fable-class, floor = Sonnet-class, re-ruled
# 2026-08-17, replacing the 2026-08-04 Opus-class good tier); exact ids
# verified against live subagent transcripts 2026-08-04.
#
# WHY A CHAIN RATHER THAN ONE ID (user-ruled 2026-08-23). On 2026-08-23 the
# account's Fable credits ran out. The measured blast radius was two cells of
# eight — the Claude good-tier pair; the codex good tier is a different model
# and was untouched. A completed review was still reachable without editing
# any source, by rerunning those two cells singly with the --model override
# below. The grid's failure note does tell the operator to rerun failed cells
# singly with the cell launchers, but it names no flag, so reaching for the
# override took knowing it was there. What the chain buys is that the
# eight-cell run stops degrading into a manual per-cell rerun. Opus-class is
# the named fallback because it was this tier's own pin until 2026-08-17.
#
# The fallback is never silent: the report's provenance stamp names the model
# that actually produced it, and records what was asked for first and why that
# attempt failed. A record naming a model that did not write it would be worse
# than a failed cell, because the failure is visible and the false stamp is not.
TIER_TO_CLAUDE_MODEL_CHAIN = {
    "good": ("claude-fable-5", "claude-opus-5"),
    "floor": ("claude-sonnet-5",),
}

# Tier -> reasoning effort, pinned explicitly so a cell's behavior never
# depends on the machine-local default. Accepted levels today:
# low, medium, high, xhigh, max. "high" for both tiers per the skill's
# good-at-high-effort ruling; recalibrating is the user's call, here.
TIER_TO_REASONING_EFFORT = {
    "good": "high",
    "floor": "high",
}

# The reviewer reads the document and writes one file: its report. Write is
# present because the report is a file now — the common module explains why
# writes are detected rather than blocked.
ALLOWED_TOOLS = "Read,Grep,Glob,Write"


def invocation_builder(effort: str):
    """The one thing that differs between the two cells.

    Returns the callback the shared chain runner uses: given a model and the
    composed prompt, it yields the argv to run and the text to feed on stdin.

    The prompt travels via stdin, not as a positional argument: the CLI's
    variadic options (--allowedTools) swallow a trailing positional
    (measured 2026-08-05: the cell ran with no input at all), and
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
