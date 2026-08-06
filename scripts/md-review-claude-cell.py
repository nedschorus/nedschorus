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
stays on stderr. Exit codes: 0 cell ran, 2 bad invocation, else claude's code.

The cell runs with this repository as its working directory, so its
instruction floor (the checkout's CLAUDE.md / AGENTS.md, when present) is
identical to the Codex cells' — never the invoking session's project.
"""

import argparse
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PROMPTS_DIR = REPO_ROOT / ".claude" / "skills" / "md-review" / "prompts"

# Tier -> Claude model id. One place to update as models change. User-picked
# (good = Opus-class, floor = Sonnet-class, 2026-08-04); exact ids verified
# against live subagent transcripts 2026-08-04.
TIER_TO_CLAUDE_MODEL = {
    "good": "claude-opus-5",
    "floor": "claude-sonnet-5",
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

    model = args.model or TIER_TO_CLAUDE_MODEL[args.tier]
    effort = TIER_TO_REASONING_EFFORT[args.tier]
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
    if completed.returncode != 0:
        if completed.stdout:
            print(completed.stdout, file=sys.stderr)
        print(
            f"md-review-claude-cell: claude -p failed (exit {completed.returncode})"
            + (" — if the error above says the CLI is not logged in, ask the user to run: claude login"
               if "auth" in (completed.stdout or "").lower() or "login" in (completed.stdout or "").lower()
               else ""),
            file=sys.stderr,
        )
        return completed.returncode

    # Provenance header for the review record: the which-cells-earn-their-keep
    # analysis needs every cell output pinned to its exact model and effort
    # (tier names drift across model eras; pins do not).
    print(
        f"<!-- provenance: runtime=claude model={model} "
        f"effort={effort} cell={args.cell} "
        f"tier={args.tier} target={args.target} -->\n"
    )
    print(completed.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
