---
issue: "[run-agent: one CLI to invoke a Claude or Codex agent headlessly from any caller (Python, shell, either runtime)](https://github.com/nedschorus/nedschorus/issues/41)"
---

# run-agent: one CLI to invoke a Claude or Codex agent headlessly from any caller (Python, shell, either runtime)

## Problem

Cross-runtime cross-checking is a standing pattern (d-review's clarity matrix; the sparring pair, GHI [Dynamic agent-team model: sparring pairs, on-tap domain experts, spy-triaged oversight (design capture; research pending)](https://github.com/nedschorus/nedschorus/issues/26)): reviewers from one model family share blind spots, so second reads come from the other family — proven live 2026-08-03, when the Codex cell caught a defect both Claude cells missed and vice versa. The working agent is usually a Claude, which composes Claude subagents natively but has no uniform way to buy a Codex read. The team patterns (a Claude-led team with a Codex reviewer, a Codex-led team with a Claude reviewer, dual-candidate teams with a third team cherry-picking the best of both) need agents of BOTH runtimes invocable from Python orchestration, shell scripts, or either runtime's session.

## The primitive

One CLI — working name `scripts/run-agent.py` — `--runtime claude|codex --tier good|floor --prompt-file <f> --cd <dir> [--context-pack <f>] [--model <id>]`, printing the agent's final message to stdout. That single artifact is callable from all four contexts: shell natively, Python by subprocess, and either agent runtime through its shell verb (the interface both are best trained on).

Headless halves: `codex exec` (MEASURED live 2026-08-03: read-only sandbox, `-C`, `--output-last-message` verified working — see `scripts/d-review-codex-cell.py`, the first special-case caller, which collapses onto this primitive when built) and `claude -p` (UNMEASURED — needs the same smoke test; the boss's measured trap that `--allowedTools` silently discards a positional prompt says every headless-Claude flag combination gets verified, never assumed).

**Correction, 2026-10-01.** Both halves run headless today, and `scripts/d-review-codex-cell.py` is no longer on main: the cells `nc-systems/cold-read/cold-read-claude-cell.py`, `nc-systems/cold-read/cold-read-codex-cell.py` and `nc-systems/cold-read/cold-read-agy-cell.py` run `claude`, `codex` and `agy` headless and share `nc-systems/cold-read/cold-read-cell-common.py`, which `scripts/sanity-check-attacks.py` also calls.

## Design points (boss-ruled 2026-08-03)

1. **Instruction files are the context floor, selected by working directory.** The `--cd` choice decides which CLAUDE.md / AGENTS.md rides along under the prompt. Probe matrix owed at build: which invocation modes load which instruction files, per runtime (currently assumed, not measured).
2. **Questions by stateless retry — and the question contract is load-bearing, not a convenience (boss 2026-08-03).** Output contract: the RESULT, or a block starting `QUESTION:` instead of a partial answer. The invoker reads the question, revises the prompt, and asks a FRESH agent — no threading, no session plumbing; every attempt stays a clean single-shot, and the fixed prefix is machine-branchable from orchestration code. The contract implements the phase-boundary sanity check ruled on GHI [Dynamic agent-team model: sparring pairs, on-tap domain experts, spy-triaged oversight (design capture; research pending)](https://github.com/nedschorus/nedschorus/issues/26) open item 5: the incoming agent's FIRST duty at context load is to challenge an ill-defined or hopeless brief — return the question, never the attempt. The worst observed multi-phase failure class is a later phase inheriting such a task unquestioned; prompt templates for phased work carry this duty explicitly.
3. **Context dial: naive / briefed — with shadowing composing on top.** Naive = instruction floor + task prompt only (right for fresh-eyes review). Briefed = floor + an invoker-curated `--context-pack` file. The former third rung, "mirrored by a generated brief," is superseded (boss 2026-08-03): near-identical context is achieved by **shadowing** — a standing observer continuously reading the working agent's session transcript (JSONL), a mechanism the legacy fleet ran live for weeks (a transcript-follow pipeline, simple and reliable across context resets). Shadowing is an arrangement between two agents, not a spawn mode, so it is out of this CLI's interface and lives in the team patterns (GHI [Dynamic agent-team model: sparring pairs, on-tap domain experts, spy-triaged oversight (design capture; research pending)](https://github.com/nedschorus/nedschorus/issues/26)).
4. **Shared per-role prompt templates remain the no-drift layer** — one prompt source for both runtimes' cells, the `d-review/prompts/` pattern.

## Relations

- First caller: d-review (its Codex-cell script becomes a thin template-selecting wrapper or is absorbed; recorded at that commit).
- Team patterns consuming this: GHI [Dynamic agent-team model: sparring pairs, on-tap domain experts, spy-triaged oversight (design capture; research pending)](https://github.com/nedschorus/nedschorus/issues/26) (sparring pair; N-version competing mode with the third-team cherry-pick).

new-vp session bba1b075
