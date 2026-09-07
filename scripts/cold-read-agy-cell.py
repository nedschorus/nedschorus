#!/usr/bin/env python3
"""Run one Antigravity (`agy`) cell of a cold read against a document.

One invocation = one cell — the third leg beside the Claude cell launcher
(scripts/cold-read-claude-cell.py) and the Codex cell launcher
(scripts/cold-read-codex-cell.py). Everything the three do apart from
invoking their model lives in scripts/cold-read-cell-common.py and is
imported by all of them, so the legs cannot drift. Read that file for the
report contract, the write-detection rule, and why the reviewer writes a
file rather than answering in chat.

Usage:
  scripts/cold-read-agy-cell.py --cell fast-clarify --tier fast \\
      --target docs/walk/foo-draft.md \\
      --report cold-read-records/2026-01-01-foo/foo-fast-read.md

The reviewer writes its findings to --report. This program prints progress
to stderr and nothing to stdout.

Exit codes: 0 a model produced a report; 1 every model in the tier's chain
failed to produce one, including the case where `agy` never started because
the binary is not on PATH (the common module names that on stderr and lets
the chain advance, so a 1 always means "no review was produced"); 64 this
program refused the invocation and never launched agy, naming its own fix.
64 rather than the conventional 2 for the reason written beside
EXIT_BAD_INVOCATION in scripts/cold-read-cell-common.py, which every cell
shares.

WHAT THIS LEG IS FOR (user-ruled 2026-09-07 at the cold-read-research seat,
after measurements, superseding that morning's ruling for low): the fast cold
read runs on Gemini 3.8 Flash at MEDIUM, replacing gpt-5.6-terra at low. The
measurements: about 100-110 s per document (single runs on a 658-word skill
and a 1,967-word walk draft); on the ghi-write candidate defect list, medium
found 42% of the rows against 19% at low, and medium and high hit the same
rows, so medium is the cheapest effort that buys the recall. It is the one
tier this launcher pins. The good and floor tiers stay on the Claude and Codex
launchers, and this launcher refuses them (exit 64 from argparse) rather than
running a Gemini model under a stamp that names a tier the roster never
measured it on.

THE INVOCATION, as measured working in the 2026-09-04 campaign
(cold-read-records/2026-09-03-cold-read-tier-roster-campaign/tools/
run-astra-and-gemini-cells.py on the cold-read-research machine, not
committed): `agy --add-dir <repo> --dangerously-skip-permissions --model <id>
--effort <eff> --print-timeout 30m --output-format text --print <prompt>`.
`--print` takes the prompt as its value. `--add-dir` is required, or the
repository's AGENTS.md does not load. `--dangerously-skip-permissions` is what
lets the Write of the report happen headless. Antigravity's model ids carry the
effort as a suffix (gemini-3.8-flash-{low,medium,high}); `--effort` is passed
as well, exactly as the campaign passed it.

THE CHAT-INSTEAD-OF-FILE QUIRK, and how it is handled. The campaign measured
that gemini-3.8-flash sometimes answers the whole review in chat instead of
writing the file it was told to. Its runner took stdout as the report body
when the file was missing and stdout was long enough to be a review, and
stamped provenance after exit. This launcher does the same through a seam the
common module provides for it: `stdout_is_a_review` below is the rule, applied
only when the model exited 0 and no report exists at the given path or
anywhere the near-miss search looks; the common module writes the text into
place, announces it on stderr under STDOUT_RECOVERY_PHRASE, and stamps it like
any other report. The threshold is the campaign's own, 120 words: a remark
such as "I have written the report to <path>" is a sentence, and a review of
even a short document restates every section and then reports two more
sections, so the two do not overlap in length. A run whose stdout falls under
the threshold with no file written fails, as on the other legs.

WHY THIS LEG'S STAMP CARRIES NO `tokens=` FIELD. The Antigravity CLI prints
no "tokens used" line the way the Codex CLI does, so the field is omitted
rather than filled with a zero; if it starts printing one, the shared parser in
scripts/cold-read-cell-common.py picks it up with no change here.
"""

import importlib.util
import pathlib
import sys

_common_spec = importlib.util.spec_from_file_location(
    "cold_read_cell_common", pathlib.Path(__file__).with_name("cold-read-cell-common.py")
)
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)

PROGRAM = "cold-read-agy-cell"

# Tier -> the Antigravity models to try, in order. One tier, one model
# (user-ruled 2026-09-07, after measurements, superseding the earlier ruling
# for low): the fast cold read is gemini-3.8-flash at medium, and Antigravity's
# id for that is the model name with the effort as its suffix (`agy models`
# lists gemini-3.8-flash-low, -medium, -high). A single-entry chain, like
# every pinned chain on the other two legs: the shared loop still clears the
# report path before the attempt and after a failed one, and a second entry is
# one line if a ruling ever wants one.
TIER_TO_AGY_MODEL_CHAIN = {
    "fast": ("gemini-3.8-flash-medium",),
}

# Tier -> reasoning effort, pinned explicitly so a cell's behavior never
# depends on the machine's own default. The CLI accepts low, medium, high;
# medium is the ruling (2026-09-07: recall 42% at medium against 19% at low
# on the ghi-write candidate defect list, and high hit the same rows as
# medium). Passed alongside the suffixed model id exactly as the 2026-09-04
# campaign passed both.
TIER_TO_REASONING_EFFORT = {
    "fast": "medium",
}

# How long `agy --print` waits for the model before giving up on the turn.
# The campaign's value, kept as measured: a fast read at medium was measured
# at about 100-110 s per document (2026-09-07, single runs on a 658-word skill
# and a 1,967-word walk draft), so a run that reaches this limit has hung, and
# the CLI's non-zero exit then fails the cell the ordinary way. Shortening it
# is a calibration the user makes, here.
AGY_PRINT_TIMEOUT = "30m"

# The fewest words the runtime's stdout must hold to be taken as the review
# when no report file was written -- the campaign's threshold, kept as
# measured. See the docstring: a remark about having written the file is a
# sentence, a review is hundreds of words, and a number between them keeps
# the remark from being stamped as a review.
STDOUT_REVIEW_MINIMUM_WORDS = 120


def stdout_is_a_review(runtime_stdout: str) -> str:
    """The rule the common module applies on the exit-0, no-file path: the
    stdout to keep as the report body, or "" when it is not a review."""
    if len(runtime_stdout.split()) >= STDOUT_REVIEW_MINIMUM_WORDS:
        return runtime_stdout
    return ""


def invocation_builder(effort: str):
    """The one thing that differs between the cells.

    Returns the callback the shared chain runner uses: given a model and the
    composed prompt, it yields the argv to run and the text to feed on stdin.
    agy takes the prompt as the value of --print, so the stdin slot is None —
    which the shared runner turns into an explicitly closed stdin rather than
    an inherited one.
    """
    def build_invocation(model: str, prompt: str):
        command = [
            "agy",
            "--add-dir", str(common.REPO_ROOT),
            "--dangerously-skip-permissions",
            "--model", model,
            "--effort", effort,
            "--print-timeout", AGY_PRINT_TIMEOUT,
            "--output-format", "text",
            "--print", prompt,
        ]
        return command, None
    return build_invocation


def main() -> int:
    return common.run_cell(
        program=PROGRAM, runtime="agy", description=__doc__,
        model_help="explicit Antigravity model id (effort suffix included, "
                   "e.g. gemini-3.8-flash-high); overrides the tier mapping",
        tier_to_model_chain=TIER_TO_AGY_MODEL_CHAIN,
        tier_to_effort=TIER_TO_REASONING_EFFORT,
        invocation_builder=invocation_builder,
        recover_report_from_stdout=stdout_is_a_review,
    )


if __name__ == "__main__":
    sys.exit(main())
