#!/usr/bin/env python3
"""Run one cell of the sanity-checker attack-split validation experiment.

The experiment (grid-seat rulings, user-walked 2026-08-12, recorded in
docs/drafts/sanity-checker-prompt-draft.md): three stance attacks x two
runtimes x two ground-truth documents, scored afterward against the recorded
rulings. One invocation = one cell, mirroring the md-review cell launchers.

  scripts/sanity-checker-attack-experiment.py --attack cut --runtime claude --doc gatekeeper

Attacks: cut, mechanization, fresh-eyes. Runtimes: claude (Fable, xhigh),
codex (gpt-5.6-sol, xhigh). Docs: gatekeeper (the archived pre-walk spec),
fast-handoff (the archived pre-gut design).

The cut and mechanization cells read the target and its pinned context set
from the repository, isolated by instruction exactly as the original
calibration runs were. The fresh-eyes cell receives only the problem
statement, inlined, and runs from an empty scratch directory so it cannot
find the design it must stay independent of.

Output lands in md-review-records/2026-08-12-attack-split-experiment/ as
<doc>-<attack>-<runtime>.md with a provenance stamp. Exit codes: 0 cell ran,
2 bad invocation, else the runtime CLI's code.
"""

import argparse
import pathlib
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
EXPERIMENT_DIR = REPO_ROOT / "md-review-records" / "2026-08-12-attack-split-experiment"
INPUTS_DIR = EXPERIMENT_DIR / "inputs"

CLAUDE_MODEL = "claude-fable-5"
CODEX_MODEL = "gpt-5.6-sol"
REASONING_EFFORT = "xhigh"
CELL_TIMEOUT_SECONDS = 3600

ATTACK_PROMPT_FILES = {
    "cut": REPO_ROOT / "docs/drafts/sanity-checker-cut-attack-prompt-draft.md",
    "mechanization": REPO_ROOT / "docs/drafts/sanity-checker-mechanization-attack-prompt-draft.md",
    "fresh-eyes": REPO_ROOT / "docs/drafts/sanity-checker-fresh-eyes-attack-prompt-draft.md",
}

# Target + pinned context per document, matching the original ground-truth
# runs so scores compare like with like.
DOC_SETS = {
    "gatekeeper": {
        "target": "md-review-records/2026-08-12-sanity-checker-calibration/reviewed-spec-at-0890848.md",
        "target_description": "the git-gatekeeper design at its 2026-08-09 revision (archived snapshot)",
        "context": [
            "md-review-records/2026-08-12-attack-split-experiment/inputs/context-build-slice-plan-at-0890848.md",
            "md-review-records/2026-08-12-attack-split-experiment/inputs/context-credential-bindings-at-0890848.md",
            "md-review-records/2026-08-12-attack-split-experiment/inputs/context-fast-handoff-design-at-0890848.md",
        ],
        "problem_statement": INPUTS_DIR / "problem-statement-gatekeeper.md",
    },
    "fast-handoff": {
        "target": "md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md",
        "target_description": "the fast-handoff design at its pre-gut revision (archived snapshot)",
        "context": [
            ".claude/skills/handoff/SKILL.md",
            "docs/drafts/handoff-skill-draft.md",
        ],
        "problem_statement": INPUTS_DIR / "problem-statement-fast-handoff.md",
    },
}


def prompt_body(attack: str) -> str:
    """The prompt below the draft file's status rule."""
    text = ATTACK_PROMPT_FILES[attack].read_text(encoding="utf-8")
    marker = "\n---\n"
    if marker not in text:
        raise SystemExit(f"attack draft has no status rule: {ATTACK_PROMPT_FILES[attack]}")
    return text.split(marker, 1)[1].strip()


def assemble_prompt(attack: str, doc: str) -> str:
    doc_set = DOC_SETS[doc]
    if attack == "fresh-eyes":
        problem = doc_set["problem_statement"].read_text(encoding="utf-8")
        return (
            prompt_body(attack)
            + "\n\n---\n\nThe review request follows: the problem statement is below. "
            "It is your complete input; do not read files or search for anything.\n\n"
            + problem
        )
    context_lines = "\n".join(f"- {path}" for path in doc_set["context"])
    request = (
        f"Review request: the document under review is `{doc_set['target']}` — "
        f"{doc_set['target_description']}. Context documents:\n{context_lines}\n\n"
        "These files are your complete document set: do not search for or read any "
        "other file, including documents they link. Where a finding depends on "
        "something you cannot read, say so plainly rather than chasing it."
    )
    return prompt_body(attack) + "\n\n---\n\n" + request


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
        command, input=prompt, stdout=subprocess.PIPE, stderr=sys.stderr,
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
        command, stdin=subprocess.DEVNULL, stdout=sys.stderr, stderr=sys.stderr,
        text=True, check=False, timeout=CELL_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        return completed.returncode, ""
    output = last_message_path.read_text(encoding="utf-8")
    last_message_path.unlink(missing_ok=True)
    return 0, output


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--attack", required=True, choices=sorted(ATTACK_PROMPT_FILES))
    parser.add_argument("--runtime", required=True, choices=["claude", "codex"])
    parser.add_argument("--doc", required=True, choices=sorted(DOC_SETS))
    args = parser.parse_args()

    prompt = assemble_prompt(args.attack, args.doc)
    isolated = args.attack == "fresh-eyes"
    runner = run_claude if args.runtime == "claude" else run_codex
    code, output = runner(prompt, isolated)
    if code != 0:
        print(
            f"sanity-checker-attack-experiment: {args.runtime} cell failed (exit {code})",
            file=sys.stderr,
        )
        return code

    model = CLAUDE_MODEL if args.runtime == "claude" else CODEX_MODEL
    output_path = EXPERIMENT_DIR / f"{args.doc}-{args.attack}-{args.runtime}.md"
    output_path.write_text(
        f"<!-- provenance: runtime={args.runtime} model={model} effort={REASONING_EFFORT} "
        f"attack={args.attack} doc={args.doc} "
        f"isolation={'empty-scratch-directory' if isolated else 'instruction-pinned document set'} -->\n\n"
        + output,
        encoding="utf-8",
    )
    print(f"cell complete: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
