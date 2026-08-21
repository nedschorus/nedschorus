#!/usr/bin/env python3
"""Run a sanity-check: independent review checks, each on both runtimes, over one document.

The sanity-check is this project's second review instrument, separate from
md-review (`scripts/md-review-grid.py`, the prose-and-clarity review) and
never part of it. Three checks, each in its own
fresh context:

- **cut** — what here should be deleted.
- **mechanization** — what English instruction here should become code.
- **fresh-eyes** — an independent, competitive design built from a problem
  statement alone. The agent is instructed not to read the existing design,
  its implementation, or its records, but may research the best approach
  independently — this repository, the internet, reputable repositories on
  GitHub. Isolation is instructed, not enforced, and checked two ways: the
  agent's report lists everything it consulted and discloses anything
  off-limits it strayed into, and the runner scans what the requester sends
  (the problem statement, and the instruction files the CLIs inject on their
  own) for the design's coined names, printing a LEAK-WARNING per hit. The
  agent returns a five-section report — sketch, hard parts, late
  discoveries, assumptions, what it consulted — and triage compares the
  original and the fresh design on their merits: differences become
  questions, absent worries become findings, the stronger parts of either
  feed a best-of-both proposal, and every adoption is walked to the user.

Prompts: `docs/agents/sanity-checker-<check>-attack-prompt.md`. Each file is
split at its `<!-- SANITY-CHECK-PROMPT-BODY -->` line: above it a header for
maintainers that no review agent ever sees, below it the prompt itself. The
runner refuses to start unless every prompt it will use carries exactly one
such line with `## Your assignment` directly below it, so a broken boundary
fails before any model cost is spent.

Operating rules:

- Both runtimes on every check — claude-fable-5 (the claude CLI) and
  gpt-5.6-sol (the codex CLI), at xhigh reasoning effort. Each check
  therefore runs as two review agents, one per runtime, named
  `<check>-<runtime>` in this runner's output.
- The check runs only when a person or agent deliberately decides to run it:
  never automatically, and a revision of an already-checked document earns no
  automatic re-check. Run it after md-review has passed, not before. It
  applies only to actionable (work-directing) MDs — designs, specs, skills,
  plans — never records (documents that only report what happened).
  "md-review passed" is the natural moment to ask
  whether a document deserves its check; a PR carrying a never-checked
  actionable MD may have a check suggested — a note, never a gate.
- The requesting agent triages: follows up the warnings described below,
  settles hedged claims about code by reading the code, merges the runtimes' reports, and
  walks the survivors with the user (walk-me-through). Findings are design
  changes; none is applied without his ruling.
- Reports land in `sanity-check-records/<date>-<target-stem>/` (suffixed -2,
  -3, ... when that name is taken, so a same-day second pass never overwrites
  earlier reports) — machine-local working material, gitignored, deleted when
  the work it served lands; git history is the archive.

Usage:

  scripts/sanity-check-attacks.py --target <path> [--context <path> ...]
      [--problem-statement <path>] [--attack <name> ...] [--print <surface>]

`--context` names companion documents the reading checks receive alongside
the target. `--attack` (repeatable; default all three) runs a subset — the fresh-eyes
second pass is `--attack fresh-eyes --problem-statement <variant>`, and a
failed check reruns without repeating the others.

`--print` writes a review surface to stdout instead of running: `cut`,
`mechanization`, or `fresh-eyes` prints that check's assembled prompt — body plus the review request: for
the reading checks the request names the target and context paths, for
fresh-eyes it is the problem-statement file; `requester` prints the requesting agent's manual —
this docstring followed by the fresh-eyes requester section — and needs no
other arguments.

Running a check, and reading its output:

- Run it as a background task and arm a Monitor (the harness's watch tool)
  on its output; it prints a status line per review agent as each finishes —
  `saved: <path>`, `FAILED: <check>-<runtime> exit <code>`, or `SKIPPED:` —
  plus the warning lines described below. Exit 0 when every launched agent saved; 1 when any launched agent
  failed (a skipped agent is not launched); 2 when the invocation itself is
  unusable — a missing file, a broken prompt boundary, a bad flag.
- Without `--problem-statement` the fresh-eyes agents print `SKIPPED`, loudly,
  never silently — that check works from the problem statement alone.
- Cut and mechanization reports get a quote scan: every quoted span of four
  or more words is searched for across the tracked files, and a span found in
  none prints `WARNING: <check>-<runtime> quote found in no tracked file: ...` — triage
  information, never a gate; a quote may legitimately come from git history
  or the web.
- Fresh-eyes runs print `LEAK-WARNING` lines — the requester-input scan
  described above. Expect hits on every run: the off-limits list must name
  the design's paths to forbid them, and those paths are coined names.
- Every review agent may reach the internet to check facts: claude agents
  carry web tools and no write tools; codex agents run workspace-write with
  network on, writes forbidden by prompt — a codex agent that modifies the
  worktree is reported as `WARNING: <check>-<runtime> modified the worktree:
  <paths>`. While the agents run, make no changes in this worktree yourself —
  the write detector cannot tell your edits from a review agent's; work
  elsewhere until the run
  completes.
- Each saved report opens with a provenance line: runtime, model, effort,
  check, target, and the commit and worktree state at review time, so quotes
  can be verified against the text the agent actually read even after the
  document moves.
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

# The prompt files' header/body boundary, and the heading the body must open
# with — checked at startup, so a broken boundary fails before any model cost.
PROMPT_BODY_MARKER = "<!-- SANITY-CHECK-PROMPT-BODY -->"
PROMPT_BODY_FIRST_LINE = "## Your assignment"

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
    """The prompt below the file's body marker.

    The marker is a line no ordinary edit produces. The boundary was the first
    `---` line until 2026-08-19, and `---` is ordinary markdown punctuation: a
    horizontal rule added to the header, or one written inside a code fence,
    silently moved the split and shipped header text to the cells in place of
    their instructions. It also forced a YAML-frontmatter special case, since
    frontmatter is delimited by `---` too. A marker that collides with nothing
    needs neither the special case nor an editor's memory (user-ruled
    2026-08-19, on the first live check of the cut prompt, where five of six
    cells raised the old boundary independently).
    """
    path = ATTACK_PROMPT_FILES[attack]
    lines = path.read_text(encoding="utf-8").splitlines()
    # A line that IS the marker, not a line mentioning it: the header names the
    # marker when it explains the split, and that mention must not be mistaken
    # for the boundary itself.
    marker_lines = [i for i, line in enumerate(lines)
                    if line.strip() == PROMPT_BODY_MARKER]
    if len(marker_lines) != 1:
        raise SystemExit(
            f"attack prompt needs exactly one {PROMPT_BODY_MARKER} line, "
            f"found {len(marker_lines)}: {path}"
        )
    body = "\n".join(lines[marker_lines[0] + 1:]).strip()
    first_line = body.split("\n", 1)[0].strip()
    if first_line != PROMPT_BODY_FIRST_LINE:
        raise SystemExit(
            f"attack prompt body must open with {PROMPT_BODY_FIRST_LINE!r}, "
            f"found {first_line!r}: {path}"
        )
    return body


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
        # Bare punctuation (`---`) is markdown, not a coinage.
        if (len(span) >= 3 and " " not in span and not span.isdigit()
                and any(ch.isalnum() for ch in span)
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
    """Path -> (index/worktree status, content fingerprint) for every file git
    sees as dirty or untracked. Both halves are needed, because each catches
    what the other misses. A file already modified before the run keeps its
    ` M` line when a cell rewrites it, so a label alone misses that write
    (Codex finding on PR #98); staging a file changes its status without
    changing its bytes, so a fingerprint alone misses `git add` (found by
    `codex exec review` on PR #102, where the fingerprint-only version was a
    regression against the label comparison it replaced).

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
        snapshot[path] = (status, hashed)
    return snapshot


QUOTE_MINIMUM_WORDS = 4


def normalized_for_quote_match(text: str) -> str:
    """Whitespace and markdown emphasis vary freely between a quote and its
    source; both sides are compared with them normalized away (the same rule
    as scripts/md-drift-lint.py)."""
    return re.sub(r"\s+", " ", re.sub(r"[*_`]", "", text)).strip()


def tracked_files_corpus() -> tuple:
    """Every tracked text file's content, normalized, one entry per file.
    Built once per run, before the cells launch."""
    listed = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT,
        stdout=subprocess.PIPE, text=True, check=False,
    )
    pieces = []
    for name in listed.stdout.splitlines():
        path = REPO_ROOT / name
        try:
            pieces.append(normalized_for_quote_match(path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue
    # One entry per file, never concatenated: a joined corpus would let a quote
    # match across a file boundary (md-review finding, verified by construction).
    return tuple(pieces)


def quote_scan(corpus: tuple, report: str, cell: str) -> None:
    """Print a WARNING per quoted span in a report that appears in no tracked
    file. A quote is a search string: found anywhere, it is verbatim; found
    nowhere, it is the one failure that matters — words that exist in no file.
    No attribution convention is asked of the cells (user-ruled 2026-08-19).
    Information for triage, never a gate: a quote may legitimately come from
    git history or the web, and the warning says where it was not found."""
    for match in re.finditer(r'"([^"\n]+)"|\u201c([^\u201d\n]+)\u201d', report):
        quote = match.group(1) or match.group(2)
        for fragment in re.split(r"\.\.\.|\u2026", quote):
            fragment = fragment.strip().rstrip("?.!,;:")
            if len(fragment.split()) < QUOTE_MINIMUM_WORDS:
                continue
            normalized = normalized_for_quote_match(fragment)
            if not any(normalized in file_text for file_text in corpus):
                print(f'WARNING: {cell} quote found in no tracked file: '
                      f'"{fragment[:60]}"', flush=True)


def reviewed_revision(baseline: dict) -> str:
    """The revision each report describes, for its provenance line.

    Cells read the working tree, not a commit, so the commit alone identifies
    the text reviewed only when the tree is clean; `worktree=dirty(N)` says N
    paths differed from it and the commit will not reproduce what the cell saw.
    Recorded by the runner rather than asked of the reviewer: the machine holds
    this fact exactly, and a document moves under a walk — every quote in the
    first live check's reports pointed at a version that no longer existed
    before the walk on them finished (user-ruled 2026-08-19).
    """
    completed = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False,
    )
    commit = completed.stdout.strip() or "unknown"
    worktree = "clean" if not baseline else f"dirty({len(baseline)})"
    return f"commit={commit} worktree={worktree}"


def stray_paths(baseline: dict, now: dict) -> list:
    """Paths whose status or fingerprint changed while the cells ran — a codex
    cell writing to the worktree, which its prompt forbids. Compared over the
    union of both snapshots, so a file that appears, changes, or disappears
    all count (Codex finding on PR #98)."""
    return sorted(path for path in set(now) | set(baseline)
                  if now.get(path) != baseline.get(path))


def fresh_record_dir(target_stem: str) -> pathlib.Path:
    """A record directory this run owns alone: the date-stem name, suffixed
    -2, -3, ... when that name is taken — a same-day second pass or re-run
    never overwrites earlier reports (Codex finding on PR #98).

    The directory is claimed by creating it, not by testing first and creating
    after: two runs starting together on the same target and date both pass a
    look-then-create test and return the same path, and the second overwrites
    the first (found by `codex exec review` on PR #102)."""
    base = RECORDS_ROOT / f"{datetime.date.today().isoformat()}-{target_stem}"
    counter = 1
    while True:
        out_dir = base if counter == 1 else pathlib.Path(f"{base}-{counter}")
        try:
            out_dir.mkdir(parents=True)
            return out_dir
        except FileExistsError:
            counter += 1


def run_cell(attack: str, runtime: str, target: str, context: list,
             problem_statement: pathlib.Path, out_dir: pathlib.Path,
             baseline_status: set, corpus: str) -> tuple:
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
    if not fresh_eyes:
        quote_scan(corpus, output, cell)
    if runtime == "codex":
        stray = stray_paths(baseline_status, worktree_snapshot())
        if stray:
            print(f"WARNING: {cell} modified the worktree: {', '.join(stray)}", flush=True)
    model = CLAUDE_MODEL if runtime == "claude" else CODEX_MODEL
    revision = reviewed_revision(baseline_status)
    out_path = out_dir / f"{cell}.md"
    out_path.write_text(
        f"<!-- provenance: runtime={runtime} model={model} effort={REASONING_EFFORT} "
        f"attack={attack} target={target} "
        f"isolation={'instructed-not-enforced' if fresh_eyes else 'repository-read-only'} "
        f"{revision} -->\n\n"
        + output,
        encoding="utf-8",
    )
    print(f"saved: {out_path}", flush=True)
    return cell, True


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--target", default=None,
                        help="repo-relative path of the document under review "
                             "(required except with --print requester)")
    parser.add_argument("--context", action="append", default=[],
                        help="repo-relative context document (repeatable)")
    parser.add_argument("--problem-statement", type=pathlib.Path, default=None,
                        help="review-request file for the fresh-eyes attack; "
                             "without it the fresh-eyes cells are SKIPPED, loudly")
    parser.add_argument("--attack", action="append", choices=list(ATTACKS), default=None,
                        help="run only this attack (repeatable); default: all three")
    parser.add_argument("--print", dest="print_surface",
                        choices=list(ATTACKS) + ["requester"], default=None,
                        help="print a review surface to stdout instead of running: "
                             "an attack's assembled cell prompt, or the requester manual")
    args = parser.parse_args()

    if args.print_surface == "requester":
        fresh_eyes_text = ATTACK_PROMPT_FILES["fresh-eyes"].read_text(encoding="utf-8")
        heading = "## Writing the problem statement"
        start = fresh_eyes_text.find(heading)
        # The marker as its own line, not the header sentence that names it.
        end = fresh_eyes_text.find("\n" + PROMPT_BODY_MARKER + "\n")
        if start == -1 or end == -1 or start >= end:
            print("requester section not found in the fresh-eyes prompt", file=sys.stderr)
            return 2
        section = fresh_eyes_text[start:end].strip()
        # The section's closing sentence points at the marker and body below
        # it, which this surface deliberately omits — printed here it would
        # dangle (md-review finding).
        tail_start = section.rfind("\n\nEverything below the marker")
        if tail_start != -1:
            section = section[:tail_start].rstrip()
        print("# The requesting agent's manual\n")
        print("## The runner's operating rules (its docstring)\n")
        print(__doc__.strip())
        print()
        print(section)
        return 0

    if args.target is None:
        parser.error("--target is required except with --print requester")

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

    if args.print_surface:
        if args.print_surface == "fresh-eyes" and args.problem_statement is None:
            print("--print fresh-eyes needs --problem-statement", file=sys.stderr)
            return 2
        print(assemble_prompt(args.print_surface, args.target, args.context,
                              args.problem_statement))
        return 0

    design_names = coined_names(target_path)

    out_dir = fresh_record_dir(target_path.stem)
    baseline_status = worktree_snapshot()
    corpus = tracked_files_corpus()

    attacks = tuple(dict.fromkeys(args.attack)) if args.attack else ATTACKS
    cells = []
    for attack in attacks:
        if attack == "fresh-eyes" and args.problem_statement is None:
            for runtime in RUNTIMES:
                print(f"SKIPPED: {attack}-{runtime} (no --problem-statement)", flush=True)
            continue
        for runtime in RUNTIMES:
            cells.append((attack, runtime))

    if args.problem_statement and any(a == "fresh-eyes" for a, _ in cells):
        leak_scan(design_names, args.problem_statement.read_text(encoding="utf-8"),
                  f"the problem statement ({args.problem_statement})")
        for path in injected_instruction_files():
            leak_scan(design_names, path.read_text(encoding="utf-8"),
                      f"an injected instruction file ({path})")

    # Validate every prompt this run will use before any cell launches, so a
    # broken boundary fails before model cost — as documented; until 2026-08-21
    # validation ran lazily inside each cell (md-review finding, verified).
    for attack in dict.fromkeys(cell_attack for cell_attack, _ in cells):
        prompt_body(attack)

    ok = True
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(cells) or 1) as pool:
        futures = [
            pool.submit(run_cell, attack, runtime, args.target, args.context,
                        args.problem_statement, out_dir, baseline_status, corpus)
            for attack, runtime in cells
        ]
        for future in concurrent.futures.as_completed(futures):
            _, cell_ok = future.result()
            ok = ok and cell_ok

    print(
        f"sanity-check complete: reports in {out_dir}. Triage each report "
        "(follow up the warnings above, settle hedged claims about code by "
        "reading the code, merge the "
        "runtimes), then walk the survivors with the user (walk-me-through). "
        "Delete the record directory when the work it served lands.",
        flush=True,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
