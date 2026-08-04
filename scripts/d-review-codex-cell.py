#!/usr/bin/env python3
"""Run one Codex cell of a d-review clarity matrix against a document.

One invocation = one cell. The prompt templates in
.claude/skills/d-review/prompts/ are the single prompt source for BOTH
runtimes' cells: Claude subagent cells are prompted with the same template
text, so the two legs cannot drift apart.

Usage:
  scripts/d-review-codex-cell.py --cell restate --tier floor --target docs/cross-project/foo.md
  scripts/d-review-codex-cell.py --cell defect-hunt --tier good --target .claude/skills/x/SKILL.md

The cell's final message prints to stdout; codex progress output stays on
stderr. Exit codes: 0 cell ran, 2 bad invocation, else codex exec's code.
"""

import argparse
import pathlib
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PROMPTS_DIR = REPO_ROOT / ".claude" / "skills" / "d-review" / "prompts"

# Tier -> Codex model id. One place to update as models change. Both ids
# boss-picked and live-verified 2026-08-03 (the bare names "sol"/"terra" are
# rejected by the CLI; the version-prefixed ids are the accepted form).
TIER_TO_CODEX_MODEL = {
    "good": "gpt-5.6-sol",
    "floor": "gpt-5.6-terra",
}

# Tier -> reasoning effort, pinned explicitly so a cell's behavior never
# depends on the machine-local ~/.codex/config.toml default. xhigh for both
# tiers by boss calibration 2026-08-03 ("xhigh is OK for codex").
TIER_TO_REASONING_EFFORT = {
    "good": "xhigh",
    "floor": "xhigh",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--cell", required=True, choices=["restate", "defect-hunt"])
    parser.add_argument("--tier", required=True, choices=["good", "floor"])
    parser.add_argument(
        "--target", required=True, help="document path, relative to the repo root or absolute"
    )
    parser.add_argument("--model", help="explicit Codex model id; overrides the tier mapping")
    args = parser.parse_args()

    target = pathlib.Path(args.target)
    if not target.is_absolute():
        target = REPO_ROOT / target
    if not target.is_file():
        print(f"d-review-codex-cell: target not found: {target}", file=sys.stderr)
        return 2

    template_path = PROMPTS_DIR / f"{args.cell}.md"
    if not template_path.is_file():
        print(f"d-review-codex-cell: prompt template missing: {template_path}", file=sys.stderr)
        return 2
    prompt = template_path.read_text(encoding="utf-8").replace("{TARGET_PATH}", str(target))

    model = args.model or TIER_TO_CODEX_MODEL[args.tier]
    last_message_path = pathlib.Path(tempfile.mkstemp(suffix=".md", prefix="d-review-cell-")[1])
    command = [
        "codex", "exec",
        "--sandbox", "read-only",
        "-C", str(REPO_ROOT),
        "--output-last-message", str(last_message_path),
    ]
    if model:
        command += ["-m", model]
    command += ["-c", f"model_reasoning_effort={TIER_TO_REASONING_EFFORT[args.tier]}"]
    command.append(prompt)

    # stdin MUST be closed explicitly: `codex exec` treats a piped-open stdin
    # as content to append and reads it to EOF before starting the turn, so an
    # inherited never-closing descriptor deadlocks the cell (measured
    # 2026-08-03: four cells frozen 24 minutes in background execution).
    completed = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=sys.stderr,
        stderr=sys.stderr,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        print(
            f"d-review-codex-cell: codex exec failed (exit {completed.returncode})",
            file=sys.stderr,
        )
        return completed.returncode

    # Provenance header for the review record: the which-cells-earn-their-keep
    # analysis needs every cell output pinned to its exact model and effort
    # (tier names drift across model eras; pins do not). Boss-required 2026-08-04.
    print(
        f"<!-- provenance: runtime=codex model={model or 'config-default'} "
        f"effort={TIER_TO_REASONING_EFFORT[args.tier]} cell={args.cell} "
        f"tier={args.tier} target={args.target} -->\n"
    )
    print(last_message_path.read_text(encoding="utf-8"))
    last_message_path.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
