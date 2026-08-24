#!/usr/bin/env python3
"""Run one Claude cell of an md-review grid against a document.

One invocation = one cell — the twin of the Codex cell launcher
(scripts/md-review-codex-cell.py). The prompt templates in
.claude/skills/md-review/prompts/ are the single prompt source for BOTH
runtimes' cells: both launchers read the same template files, so the two
legs cannot drift apart.

Usage:
  scripts/md-review-claude-cell.py --cell restate --tier floor --target docs/drafts/foo.md
  scripts/md-review-claude-cell.py --cell defect-hunt --tier good --target .claude/skills/x/SKILL.md

The cell's final message prints to stdout after a provenance stamp; progress
stays on stderr. A tier may run more than one model; TIER_TO_CLAUDE_MODEL_CHAIN
in this file's source is the mapping.
Exit codes: 0 a model in the chain ran, 2 bad invocation, otherwise the exit
code of the LAST model attempted — so a 2 from the final attempt is
indistinguishable here from a bad invocation; stderr names every attempt.

The cell runs with this repository as its working directory, so its
instruction floor is the checkout's — never the invoking session's
project. The floor is CLAUDE.md only: Claude Code does not read
AGENTS.md (verified 2026-08-20, tools-disallowed probe), which is why a
rule meant for both runtimes is duplicated into both files rather than
shared through one.
"""

import argparse
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PROMPTS_DIR = REPO_ROOT / ".claude" / "skills" / "md-review" / "prompts"

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

# Read-only tool set: a review cell inspects, never edits. Comma-joined so
# the variadic --allowedTools option parses it as one token.
ALLOWED_TOOLS = "Read,Grep,Glob"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--cell", required=True, choices=["restate", "defect-hunt"])
    parser.add_argument("--tier", required=True, choices=["good", "floor"])
    parser.add_argument(
        "--target", required=True, help="document path, relative to the repo root or absolute"
    )
    parser.add_argument("--model", help="explicit Claude model id; overrides the tier mapping")
    args = parser.parse_args()

    target = pathlib.Path(args.target)
    if not target.is_absolute():
        target = REPO_ROOT / target
    if not target.is_file():
        print(f"md-review-claude-cell: target not found: {target}", file=sys.stderr)
        return 2

    template_path = PROMPTS_DIR / f"{args.cell}.md"
    if not template_path.is_file():
        print(f"md-review-claude-cell: prompt template missing: {template_path}", file=sys.stderr)
        return 2
    prompt = template_path.read_text(encoding="utf-8").replace("{TARGET_PATH}", str(target))

    # An explicit --model is honored exactly, with no fallback: a caller who
    # names a model is answering the question the chain exists to answer, and
    # silently running a different one would defeat the request.
    chain = (args.model,) if args.model else TIER_TO_CLAUDE_MODEL_CHAIN[args.tier]
    effort = TIER_TO_REASONING_EFFORT[args.tier]

    completed = None
    failed_attempts: list[str] = []
    for model in chain:
        command = [
            "claude",
            "-p",
            "--model", model,
            "--effort", effort,
            "--output-format", "text",
            "--allowedTools", ALLOWED_TOOLS,
        ]

        # The prompt travels via stdin, not as a positional argument: the CLI's
        # variadic options (--allowedTools) swallow a trailing positional
        # (measured 2026-08-05: the cell ran with no input at all), and
        # subprocess.run(input=...) writes stdin and closes it, so the
        # inherited-open-stdin deadlock class is avoided by construction.
        completed = subprocess.run(
            command,
            input=prompt,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            cwd=REPO_ROOT,
            text=True,
            check=False,
        )
        if completed.returncode == 0:
            break

        if completed.stdout:
            print(completed.stdout, file=sys.stderr)
        failed_attempts.append(f"{model} (exit {completed.returncode})")
        print(
            f"md-review-claude-cell: {model} failed (exit {completed.returncode})"
            + (" — if the error above says the CLI is not logged in, ask the user to run: claude login"
               if "auth" in (completed.stdout or "").lower() or "login" in (completed.stdout or "").lower()
               else ""),
            file=sys.stderr,
        )

    if completed is None or completed.returncode != 0:
        print(
            "md-review-claude-cell: every model for this cell failed — "
            + ", ".join(failed_attempts)
            + ". No report was produced; the cell failed rather than degrading "
              "to a report nobody asked for.",
            file=sys.stderr,
        )
        return completed.returncode if completed is not None else 2

    if failed_attempts:
        print(
            f"md-review-claude-cell: fell back to {model} after "
            + ", ".join(failed_attempts)
            + ". The report's provenance stamp records this.",
            file=sys.stderr,
        )

    # Provenance header for the review record: the which-cells-earn-their-keep
    # analysis needs every cell output pinned to its exact model and effort
    # (tier names drift across model eras; pins do not). `model=` always names
    # the model that actually produced the text below it; when the tier's first
    # choice failed, `fallback_from=` records what was tried and why, so a
    # degraded cell is visible in the record rather than only in a log.
    fallback_note = (
        f"fallback_from={'+'.join(failed_attempts).replace(' ', '')} "
        if failed_attempts else ""
    )
    print(
        f"<!-- provenance: runtime=claude model={model} "
        f"{fallback_note}"
        f"effort={effort} cell={args.cell} "
        f"tier={args.tier} target={args.target} -->\n"
    )
    print(completed.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
