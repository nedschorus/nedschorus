#!/usr/bin/env python3
"""Run a sanity-check: three stance attacks x two runtimes over one document.

The sanity-check is this project's second review instrument, separate from
md-review and never one of its grid cells (user-ruled 2026-08-17, on the
attack-split validation experiment's scorecard; experiment records at
`git show db917b5:md-review-records/2026-08-12-attack-split-experiment/`).
Operating rules, all user-ruled:

- Three attacks, each in its own fresh context: **cut** (what should be
  deleted), **mechanization** (what English instruction should become code),
  **fresh-eyes** (an independent design built from the problem statement
  alone — it never sees the design; triage diffs its sketch against the real
  one). Prompts: `docs/agents/sanity-checker-<attack>-attack-prompt.md`.
- Both runtimes on every attack: claude-fable-5 and gpt-5.6-sol, at xhigh.
  (Tier probe 2026-08-17: max found no missed ground-truth cut on either
  runtime and covered less on codex — xhigh stands.)
- Manual call, after md-review, on actionable (work-directing) MDs only —
  designs, specs, skills, plans; never on records.
- The requesting agent triages: verifies quotes, resolves code hedges by
  targeted reads, merges the runtimes' reports, and walks the survivors with
  the user (walk-me-through). Findings are design changes; none is applied
  without his ruling.
- Reports land in `sanity-check-records/<date>-<target-stem>/` — machine-local
  working material, gitignored, deleted when the work it served lands; git
  history is the archive.

Usage:

  scripts/sanity-check-attacks.py --target <path> [--context <path> ...] \
      [--problem-statement <path>]

Run it as a background task and arm a Monitor on its output: it prints one
line per cell — `saved: <path>` or `FAILED: <cell> exit <code>` — as each
finishes. Without `--problem-statement` the fresh-eyes cells print
`SKIPPED: <cell> (no --problem-statement)` — loudly, never silently — since
that attack works from the problem statement alone. Exit 0 when every
launched cell saved, 1 otherwise.
"""

import argparse
import concurrent.futures
import datetime
import pathlib
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
RECORDS_ROOT = REPO_ROOT / "sanity-check-records"

CLAUDE_MODEL = "claude-fable-5"
CODEX_MODEL = "gpt-5.6-sol"
# xhigh for both runtimes: user calibration 2026-08-03 for codex, confirmed
# for both by the 2026-08-17 tier probe (max earned neither slot).
REASONING_EFFORT = "xhigh"
CELL_TIMEOUT_SECONDS = 3600

ATTACKS = ("cut", "mechanization", "fresh-eyes")
RUNTIMES = ("claude", "codex")

ATTACK_PROMPT_FILES = {
    "cut": REPO_ROOT / "docs/agents/sanity-checker-cut-attack-prompt.md",
    "mechanization": REPO_ROOT / "docs/agents/sanity-checker-mechanization-attack-prompt.md",
    "fresh-eyes": REPO_ROOT / "docs/agents/sanity-checker-fresh-eyes-attack-prompt.md",
}


def prompt_body(attack: str) -> str:
    """The prompt below the file's status rule."""
    text = ATTACK_PROMPT_FILES[attack].read_text(encoding="utf-8")
    marker = "\n---\n"
    if marker not in text:
        raise SystemExit(f"attack prompt has no status rule: {ATTACK_PROMPT_FILES[attack]}")
    return text.split(marker, 1)[1].strip()


def assemble_prompt(attack: str, target: str, context: list, problem_statement: pathlib.Path) -> str:
    if attack == "fresh-eyes":
        problem = problem_statement.read_text(encoding="utf-8")
        return (
            prompt_body(attack)
            + "\n\n---\n\nThe review request follows: the problem statement is below. "
            "It is your complete input; do not read files or search for anything.\n\n"
            + problem
        )
    request_lines = [f"Review request: the document under review is `{target}`."]
    if context:
        request_lines.append("Context documents:")
        request_lines.extend(f"- {path}" for path in context)
    request_lines.append(
        "Read the documents named above and the documents they link. Where a "
        "finding depends on something you cannot read, say so plainly rather "
        "than chasing it."
    )
    return prompt_body(attack) + "\n\n---\n\n" + "\n".join(request_lines)


def run_claude(prompt: str, isolated: bool) -> tuple:
    command = [
        "claude", "-p",
        "--model", CLAUDE_MODEL,
        "--effort", REASONING_EFFORT,
        "--output-format", "text",
        "--allowedTools", "Read,Grep",
    ]
    cwd = REPO_ROOT
    if isolated:
        cwd = pathlib.Path(tempfile.mkdtemp(prefix="fresh-eyes-cell-"))
    completed = subprocess.run(
        command, input=prompt, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        cwd=cwd, text=True, check=False, timeout=CELL_TIMEOUT_SECONDS,
    )
    return completed.returncode, completed.stdout


def run_codex(prompt: str, isolated: bool) -> tuple:
    last_message_path = pathlib.Path(tempfile.mkstemp(suffix=".md", prefix="attack-cell-")[1])
    cwd = REPO_ROOT
    if isolated:
        cwd = pathlib.Path(tempfile.mkdtemp(prefix="fresh-eyes-cell-"))
    command = [
        "codex", "exec",
        "--sandbox", "read-only",
        "-C", str(cwd),
        "--output-last-message", str(last_message_path),
        "-m", CODEX_MODEL,
        "-c", f"model_reasoning_effort={REASONING_EFFORT}",
    ]
    if isolated:
        # The scratch directory is deliberately not a git repository; codex
        # refuses untrusted non-repo directories without this flag.
        command.append("--skip-git-repo-check")
    command.append(prompt)
    completed = subprocess.run(
        command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, text=True, check=False,
        timeout=CELL_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        return completed.returncode, ""
    output = last_message_path.read_text(encoding="utf-8")
    last_message_path.unlink(missing_ok=True)
    return 0, output


def run_cell(attack: str, runtime: str, target: str, context: list,
             problem_statement: pathlib.Path, out_dir: pathlib.Path) -> tuple:
    """Run one cell; returns (cell_name, ok)."""
    cell = f"{attack}-{runtime}"
    prompt = assemble_prompt(attack, target, context, problem_statement)
    isolated = attack == "fresh-eyes"
    runner = run_claude if runtime == "claude" else run_codex
    code, output = runner(prompt, isolated)
    if code != 0:
        print(f"FAILED: {cell} exit {code}", flush=True)
        return cell, False
    model = CLAUDE_MODEL if runtime == "claude" else CODEX_MODEL
    out_path = out_dir / f"{cell}.md"
    out_path.write_text(
        f"<!-- provenance: runtime={runtime} model={model} effort={REASONING_EFFORT} "
        f"attack={attack} target={target} "
        f"isolation={'empty-scratch-directory' if isolated else 'repository-read-only'} -->\n\n"
        + output,
        encoding="utf-8",
    )
    print(f"saved: {out_path}", flush=True)
    return cell, True


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--target", required=True,
                        help="repo-relative path of the document under review")
    parser.add_argument("--context", action="append", default=[],
                        help="repo-relative context document (repeatable)")
    parser.add_argument("--problem-statement", type=pathlib.Path, default=None,
                        help="problem-statement file for the fresh-eyes attack; "
                             "without it the fresh-eyes cells are SKIPPED, loudly")
    args = parser.parse_args()

    target_path = REPO_ROOT / args.target
    if not target_path.is_file():
        print(f"target not found: {args.target}", file=sys.stderr)
        return 2
    if args.problem_statement and not args.problem_statement.is_file():
        print(f"problem statement not found: {args.problem_statement}", file=sys.stderr)
        return 2

    out_dir = RECORDS_ROOT / f"{datetime.date.today().isoformat()}-{target_path.stem}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cells = []
    for attack in ATTACKS:
        if attack == "fresh-eyes" and args.problem_statement is None:
            for runtime in RUNTIMES:
                print(f"SKIPPED: {attack}-{runtime} (no --problem-statement)", flush=True)
            continue
        for runtime in RUNTIMES:
            cells.append((attack, runtime))

    ok = True
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(cells) or 1) as pool:
        futures = [
            pool.submit(run_cell, attack, runtime, args.target, args.context,
                        args.problem_statement, out_dir)
            for attack, runtime in cells
        ]
        for future in concurrent.futures.as_completed(futures):
            _, cell_ok = future.result()
            ok = ok and cell_ok

    print(
        f"sanity-check complete: reports in {out_dir}. Triage each report "
        "(verify quotes, resolve code hedges by targeted reads, merge the "
        "runtimes), then walk the survivors with the user (walk-me-through). "
        "Delete the record directory when the work it served lands.",
        flush=True,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
