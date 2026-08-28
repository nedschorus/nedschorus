#!/usr/bin/env python3
"""Run one Codex cell of an md-review grid against a document.

One invocation = one cell — the twin of the Claude cell launcher
(scripts/md-review-claude-cell.py). Everything the two do apart from
invoking their model lives in scripts/md-review-cell-common.py and is
imported by both, so the legs cannot drift. Read that file for the report
contract, the write-detection rule, and why the reviewer writes a file
rather than answering in chat.

Usage:
  scripts/md-review-codex-cell.py --cell restate --tier floor \\
      --target docs/cross-project/foo.md \\
      --report md-review-records/2026-01-01-foo/codex-restate-floor.md

The reviewer writes its findings to --report. This program prints progress
to stderr and nothing to stdout.

Exit codes: 0 a model produced a report, 1 every model in the tier's chain
failed to produce one, 2 bad invocation or a refusal that names its fix.

WHY THE SANDBOX IS NO LONGER READ-ONLY. This cell used to run
`--sandbox read-only` and take the review out through
`--output-last-message`. Both legs captured only the model's final message,
and text written before a tool call is discarded by that capture (measured
2026-08-23), so a reviewer that interleaved reading and writing shipped its
closing line and none of its findings. The reviewer now writes its report
itself, which needs write access. Per the user's ruling the same day, writes
are detected rather than blocked: the report goes under the gitignored
md-review-records/ tree, where `git status` cannot see it, and the shared
module names any other path whose content changed while the reviewer ran. It
compares content rather than the list of paths git calls dirty because an
md-review subject is usually a draft that has not landed: the tree is
already dirty when the run starts, so "dirty afterwards too" says nothing,
while "this file holds something else now" says the reviewer wrote it
(nedschorus#167).

WHY THE CODEX MEMORY STORE IS OFF FOR REVIEW CELLS: written once, in
scripts/code-review-codex-cell.py's docstring, under that heading.
"""

import importlib.util
import pathlib
import sys

_common_spec = importlib.util.spec_from_file_location(
    "md_review_cell_common", pathlib.Path(__file__).with_name("md-review-cell-common.py")
)
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)

PROGRAM = "md-review-codex-cell"

# Tier -> the Codex models to try, in order. Single-entry chains: an
# Anthropic credit exhaustion — the failure that gave the Claude cell its
# fallback — does not touch these models, and no equivalent has been
# observed here. The shape is a chain anyway so both cells run the same
# shared loop; adding a fallback is one entry, not a code change.
# The version-prefixed ids are the accepted form (user's direction
# 2026-08-11, live-verified the same day: the bare names "sol"/"luna" are
# rejected by the CLI).
TIER_TO_CODEX_MODEL_CHAIN = {
    "good": ("gpt-5.6-sol",),
    "floor": ("gpt-5.6-luna",),
}

# Tier -> reasoning effort, pinned explicitly so a cell's behavior never
# depends on the machine-local ~/.codex/config.toml default. xhigh for both
# tiers by user calibration 2026-08-03 ("xhigh is OK for codex").
TIER_TO_REASONING_EFFORT = {
    "good": "xhigh",
    "floor": "xhigh",
}


def invocation_builder(effort: str):
    """The one thing that differs between the two cells.

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


def main() -> int:
    return common.run_cell(
        program=PROGRAM, runtime="codex", description=__doc__,
        model_help="explicit Codex model id; overrides the tier mapping",
        tier_to_model_chain=TIER_TO_CODEX_MODEL_CHAIN,
        tier_to_effort=TIER_TO_REASONING_EFFORT,
        invocation_builder=invocation_builder,
    )


if __name__ == "__main__":
    sys.exit(main())
