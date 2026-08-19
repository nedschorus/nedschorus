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
- Reports land in `sanity-check-records/<date>-<target-stem>/` (suffixed -2,
  -3, ... when reports already sit there, so a same-day second pass or re-run
  never overwrites earlier reports) — machine-local working material,
  gitignored, deleted when the work it served lands; git history is the
  archive.

Usage:

  scripts/sanity-check-attacks.py --target <path> [--context <path> ...] \
      [--problem-statement <path>] [--attack <name> ...]

`--attack` (repeatable; default all three) runs a subset — the fresh-eyes
second pass is `--attack fresh-eyes --problem-statement <variant>`, and a
failed cell pair reruns without repeating the others.

Run it as a background task and arm a Monitor on its output: it prints one
line per cell — `saved: <path>` or `FAILED: <cell> exit <code>` — as each
finishes. Without `--problem-statement` the fresh-eyes cells print
`SKIPPED: <cell> (no --problem-statement)` — loudly, never silently — since
that attack works from the problem statement alone. A fresh-eyes run also
prints `LEAK-WARNING: ...` lines — the design's coined names found in the
problem statement, in instruction files the cell CLIs inject on their own,
or in a fresh-eyes report. Information for triage, never a gate (user-ruled
2026-08-17). Every cell may reach the internet to check facts (user-ruled
2026-08-18): claude cells carry web tools and no write tools; codex cells run
workspace-write with network on, writes forbidden by prompt — a codex cell
that modifies the worktree is reported as `WARNING: <cell> modified the
worktree: <paths>`. Exit 0 when every launched cell saved, 1 otherwise.
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


def run_claude(prompt: str) -> tuple:
    # Every cell may check facts on the internet (user-ruled 2026-08-18);
    # isolation and write discipline are instructed in the prompts and
    # checked (leak scan; worktree check), never enforced here. The tool set
    # still omits every write tool, so claude cells cannot write at all.
    command = [
        "claude", "-p",
        "--model", CLAUDE_MODEL,
        "--effort", REASONING_EFFORT,
        "--output-format", "text",
        "--allowedTools", "Read,Grep,Glob,WebSearch,WebFetch",
    ]
    completed = subprocess.run(
        command, input=prompt, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        cwd=REPO_ROOT, text=True, check=False, timeout=CELL_TIMEOUT_SECONDS,
    )
    return completed.returncode, completed.stdout


def run_codex(prompt: str) -> tuple:
    # workspace-write plus network: the cells may reach the internet and
    # GitHub to check facts (user-ruled 2026-08-18; the read-only sandbox
    # blocks even DNS, measured that day). Disk writes become possible and
    # are forbidden by the prompts; run_cell's worktree check detects strays
    # — containment over prevention, the house doctrine.
    last_message_path = pathlib.Path(tempfile.mkstemp(suffix=".md", prefix="attack-cell-")[1])
    command = [
        "codex", "exec",
        "--sandbox", "workspace-write",
        "-c", "sandbox_workspace_write.network_access=true",
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


def worktree_snapshot(repo_root: pathlib.Path = REPO_ROOT) -> dict:
    """Path -> content fingerprint for every file git sees as dirty or
    untracked. Content hashes, not porcelain labels: a file already modified
    before the run keeps its ` M` line when a cell modifies it again, so a
    label comparison would miss the write (Codex finding on PR #98).

    The paths come from `--porcelain -z -uall`, because plain porcelain hides
    writes two ways (both found reviewing PR #102, both silent by
    construction). Without `-z`, git C-quotes a non-ASCII pathname, and the
    unquoted result names no file on disk, so it fingerprints as "absent"
    before and after a cell rewrites it. Without `-uall`, git collapses a
    wholly-untracked directory into one `dir/` entry, so every file a cell
    writes underneath it is invisible.
    """
    completed = subprocess.run(
        ["git", "status", "--porcelain", "-z", "-uall"], cwd=repo_root,
        stdout=subprocess.PIPE, text=True, check=False,
    )
    snapshot = {}
    fields = completed.stdout.split("\0")
    index = 0
    while index < len(fields):
        entry = fields[index]
        index += 1
        if not entry:
            continue
        status, path = entry[:2], entry[3:]
        # Under -z a rename or copy carries its origin path as the following
        # field instead of as ` -> origin` inside this one; skipping it keeps
        # the walk aligned with the entries that follow.
        if status[0] in ("R", "C"):
            index += 1
        file_path = repo_root / path
        if file_path.is_file():
            hashed = subprocess.run(
                ["git", "hash-object", str(file_path)], cwd=repo_root,
                stdout=subprocess.PIPE, text=True, check=False,
            ).stdout.strip()
        else:
            hashed = "absent"
        snapshot[path] = hashed
    return snapshot


def stray_paths(baseline: dict, now: dict) -> list:
    """Paths whose fingerprint changed while the cells ran — a codex cell
    writing to the worktree, which its prompt forbids. Compared over the union
    of both snapshots, so a file that appears, changes, or disappears all
    count (Codex finding on PR #98)."""
    return sorted(path for path in set(now) | set(baseline)
                  if now.get(path) != baseline.get(path))


def fresh_record_dir(target_stem: str) -> pathlib.Path:
    """A record directory this run owns alone: the date-stem name, suffixed
    -2, -3, ... when reports already sit there — a same-day second pass or
    re-run never overwrites earlier reports (Codex finding on PR #98)."""
    base = RECORDS_ROOT / f"{datetime.date.today().isoformat()}-{target_stem}"
    out_dir = base
    counter = 2
    while out_dir.exists() and any(out_dir.iterdir()):
        out_dir = pathlib.Path(f"{base}-{counter}")
        counter += 1
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def run_cell(attack: str, runtime: str, target: str, context: list,
             problem_statement: pathlib.Path, out_dir: pathlib.Path,
             design_names: set, baseline_status: set) -> tuple:
    """Run one cell; returns (cell_name, ok)."""
    cell = f"{attack}-{runtime}"
    prompt = assemble_prompt(attack, target, context, problem_statement)
    fresh_eyes = attack == "fresh-eyes"
    runner = run_claude if runtime == "claude" else run_codex
    try:
        code, output = runner(prompt)
    except subprocess.TimeoutExpired:
        print(f"FAILED: {cell} (timeout after {CELL_TIMEOUT_SECONDS}s)", flush=True)
        return cell, False
    except OSError as exc:
        # A missing or unexecutable CLI fails this cell, never the whole run.
        print(f"FAILED: {cell} (launcher error: {exc})", flush=True)
        return cell, False
    if code != 0:
        print(f"FAILED: {cell} exit {code}", flush=True)
        return cell, False
    if fresh_eyes:
        leak_scan(design_names, output, f"the {cell} report")
    if runtime == "codex":
        stray = stray_paths(baseline_status, worktree_snapshot())
        if stray:
            print(f"WARNING: {cell} modified the worktree: {', '.join(stray)}", flush=True)
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
                        help="review-request file for the fresh-eyes attack; "
                             "without it the fresh-eyes cells are SKIPPED, loudly")
    parser.add_argument("--attack", action="append", choices=list(ATTACKS), default=None,
                        help="run only this attack (repeatable); default: all three")
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

    out_dir = fresh_record_dir(target_path.stem)
    baseline_status = worktree_snapshot()

    attacks = tuple(dict.fromkeys(args.attack)) if args.attack else ATTACKS
    cells = []
    for attack in attacks:
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
                        args.problem_statement, out_dir, design_names, baseline_status)
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
