#!/usr/bin/env python3
"""Run a sanity-check: three stance attacks x two runtimes over one document.

The sanity-check is this project's second review instrument, separate from
md-review and never one of its grid cells (user-ruled 2026-08-17, on the
attack-split validation experiment's scorecard; experiment records at
`git show db917b5:md-review-records/2026-08-12-attack-split-experiment/`).
Operating rules, all user-ruled:

- Three attacks, each in its own fresh context: **cut** (what should be
  deleted), **mechanization** (what English instruction should become code),
  **fresh-eyes** (an independent design built from the problem statement —
  the cell is instructed never to read the design, its implementation, or
  its records, and may otherwise read the repository and the internet; the
  leak scan below is the check; triage diffs its sketch against the real
  one). Prompts: `docs/agents/sanity-checker-<attack>-attack-prompt.md`.
- Both runtimes on every attack: claude-fable-5 and gpt-5.6-sol, at xhigh.
  (Tier probe 2026-08-17: max found no missed ground-truth cut on either
  runtime and covered less on codex — xhigh stands.)
- Manual call, after md-review (the check reads the post-review text, so its
  findings go to the design, not to prose md-review fixes more cheaply), on
  actionable (work-directing) MDs only — designs, specs, skills, plans; never
  on records. "md-review passed" is the natural moment to ask whether a
  document deserves its check.
- Never automatic, never repeated on revisions: a re-check is a deliberate
  call. At most, a PR carrying an actionable MD that has never been
  sanity-checked may have a check suggested — a note, never a gate; a
  one-line walked edit to a never-checked file is not taxed with a full
  review.
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
that attack works from the problem statement alone. A fresh-eyes run also
prints `LEAK-WARNING: ...` lines — the design's coined names found in the
problem statement, in instruction files the cell CLIs inject on their own,
or in a fresh-eyes report. Information for triage, never a gate (user-ruled
2026-08-17). Exit 0 when every launched cell saved, 1 otherwise.
"""

import argparse
import concurrent.futures
import datetime
import pathlib
import re
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


# Hyphenations that are ordinary English or repo-wide convention, not names a
# design coined — the coined-name scan skips them. Anything else that hits is
# printed; triage judges false positives (the scan reports, never gates).
GENERIC_HYPHENATED_WORDS = {
    "read-only", "zero-context", "one-line", "built-in", "fine-grained",
    "high-level", "low-level", "long-running", "machine-readable",
    "human-readable", "re-run", "so-called", "non-empty", "well-designed",
    "open-ended", "side-effect", "side-effects", "trade-off", "trade-offs",
    "one-off", "end-to-end", "up-to-date", "auto-filled", "auto-posted",
    "hand-made", "judgment-written", "long-lived", "near-perfect",
    "per-commit", "what-and-why", "work-in-progress",
}


def prompt_body(attack: str) -> str:
    """The prompt below the file's status rule (skipping any YAML frontmatter,
    whose own `---` pair would otherwise be mistaken for the rule)."""
    path = ATTACK_PROMPT_FILES[attack]
    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        close = text.find("\n---\n", 4)
        if close == -1:
            raise SystemExit(f"unterminated frontmatter: {path}")
        text = text[close + len("\n---\n"):]
    marker = "\n---\n"
    if marker not in text:
        raise SystemExit(f"attack prompt has no status rule: {path}")
    return text.split(marker, 1)[1].strip()


def coined_names(target_path: pathlib.Path) -> set:
    """The design's coined names: backticked spans plus multi-part invented
    names (hyphenated tokens), minus ordinary-English hyphenations."""
    text = target_path.read_text(encoding="utf-8")
    names = set()
    for span in re.findall(r"`([^`\n]+)`", text):
        span = span.strip()
        # A plain lowercase word is vocabulary, not coinage: the project's
        # naming rule makes invented names multi-part, so single words
        # (`main`, `none`, `status`) only produce scan noise.
        if (len(span) >= 3 and " " not in span and not span.isdigit()
                and not (span.isalpha() and span.islower())):
            names.add(span)
    for token in re.findall(r"[A-Za-z]\w*(?:-\w+)+", text):
        if token.lower() not in GENERIC_HYPHENATED_WORDS:
            names.add(token)
    return names


def leak_scan(design_names: set, text: str, where: str) -> None:
    """Print a LEAK-WARNING per design name found in text. Report, never gate:
    a leaked name means the sketch can no longer independently confirm that
    part of the design — the requester weighs it at triage."""
    for name in sorted(design_names):
        if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text, re.IGNORECASE):
            print(f"LEAK-WARNING: design name `{name}` appears in {where}", flush=True)


def injected_instruction_files() -> list:
    """Instruction files the cell CLIs load on their own — the leak channel a
    2026-08-17 canary exposed (a cell disclosed that the injected project
    CLAUDE.md carried the design's thesis). Conventional paths, not a verified
    enumeration; the report scan is the catch-all behind this."""
    home = pathlib.Path.home()
    candidates = [
        REPO_ROOT / "CLAUDE.md",
        REPO_ROOT / "CLAUDE.local.md",
        REPO_ROOT / "AGENTS.md",
        home / ".claude" / "CLAUDE.md",
        home / ".claude" / "CLAUDE.local.md",
        home / ".codex" / "AGENTS.md",
    ]
    return [path for path in candidates if path.is_file()]


def assemble_prompt(attack: str, target: str, context: list, problem_statement: pathlib.Path) -> str:
    # Data only below the rule: every instruction lives in the prompt MDs,
    # which are md-reviewed; nothing reviewable hides here (user-ruled
    # 2026-08-17).
    if attack == "fresh-eyes":
        problem = problem_statement.read_text(encoding="utf-8")
        return prompt_body(attack) + "\n\n---\n\n" + problem
    request_lines = [f"Document under review: `{target}`"]
    if context:
        request_lines.append("Context documents:")
        request_lines.extend(f"- {path}" for path in context)
    return prompt_body(attack) + "\n\n---\n\n" + "\n".join(request_lines)


def run_claude(prompt: str, fresh_eyes: bool) -> tuple:
    # Fresh-eyes isolation is instructed and checked, not enforced (user-ruled
    # 2026-08-17): the prompt forbids reading the design, the leak scan
    # checks, and the cell may otherwise consult the repository and the
    # internet — so it gets the web tools its siblings have no use for.
    tools = "Read,Grep,Glob,WebSearch,WebFetch" if fresh_eyes else "Read,Grep"
    command = [
        "claude", "-p",
        "--model", CLAUDE_MODEL,
        "--effort", REASONING_EFFORT,
        "--output-format", "text",
        "--allowedTools", tools,
    ]
    completed = subprocess.run(
        command, input=prompt, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        cwd=REPO_ROOT, text=True, check=False, timeout=CELL_TIMEOUT_SECONDS,
    )
    return completed.returncode, completed.stdout


def run_codex(prompt: str, fresh_eyes: bool) -> tuple:
    # fresh_eyes changes nothing here: isolation is instructed in the prompt,
    # and the read-only sandbox has no network, so the codex cell cannot reach
    # the internet the prompt offers — a known, accepted asymmetry with the
    # claude cell.
    del fresh_eyes
    last_message_path = pathlib.Path(tempfile.mkstemp(suffix=".md", prefix="attack-cell-")[1])
    command = [
        "codex", "exec",
        "--sandbox", "read-only",
        "-C", str(REPO_ROOT),
        "--output-last-message", str(last_message_path),
        "-m", CODEX_MODEL,
        "-c", f"model_reasoning_effort={REASONING_EFFORT}",
        prompt,
    ]
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
             problem_statement: pathlib.Path, out_dir: pathlib.Path,
             design_names: set) -> tuple:
    """Run one cell; returns (cell_name, ok)."""
    cell = f"{attack}-{runtime}"
    prompt = assemble_prompt(attack, target, context, problem_statement)
    fresh_eyes = attack == "fresh-eyes"
    runner = run_claude if runtime == "claude" else run_codex
    try:
        code, output = runner(prompt, fresh_eyes)
    except subprocess.TimeoutExpired:
        print(f"FAILED: {cell} (timeout after {CELL_TIMEOUT_SECONDS}s)", flush=True)
        return cell, False
    if code != 0:
        print(f"FAILED: {cell} exit {code}", flush=True)
        return cell, False
    if fresh_eyes:
        leak_scan(design_names, output, f"the {cell} report")
    model = CLAUDE_MODEL if runtime == "claude" else CODEX_MODEL
    out_path = out_dir / f"{cell}.md"
    out_path.write_text(
        f"<!-- provenance: runtime={runtime} model={model} effort={REASONING_EFFORT} "
        f"attack={attack} target={target} "
        f"isolation={'instructed-not-enforced' if fresh_eyes else 'repository-read-only'} -->\n\n"
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
    missing_context = [path for path in args.context if not (REPO_ROOT / path).is_file()]
    if missing_context:
        print(f"context not found: {', '.join(missing_context)}", file=sys.stderr)
        return 2
    if args.problem_statement and not args.problem_statement.is_file():
        print(f"problem statement not found: {args.problem_statement}", file=sys.stderr)
        return 2

    design_names = coined_names(target_path)
    if args.problem_statement:
        leak_scan(design_names, args.problem_statement.read_text(encoding="utf-8"),
                  f"the problem statement ({args.problem_statement})")
        for path in injected_instruction_files():
            leak_scan(design_names, path.read_text(encoding="utf-8"),
                      f"an injected instruction file ({path})")

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
                        args.problem_statement, out_dir, design_names)
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
