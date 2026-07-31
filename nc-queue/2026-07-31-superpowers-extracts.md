# obra/superpowers read — extracts and plan updates (2026-07-31)

Boss-commissioned full read of the 14-skill repo (clone in session scratchpad; two skills — test-driven-development, systematic-debugging — were already graded in the 2026-07-22 source-evidence note: adopt kernel, strip absolutism; that verdict re-confirmed for the other twelve). This note records what was taken, where it landed, and what was declined. Register warning applies repo-wide: Iron-Law/HARD-GATE absolutism stripped from every extract per the absolutes audit.

## Validation (no action): independent convergence on the loop machinery

`subagent-driven-development` independently evolved: fresh one-shot implementer per task with constructed context ("never inherit your session's context"), per-task review, capped fix rounds whose cap is called a breaker, adjudication then BLOCKED-to-human, and a ledger outside the conversation because compaction loses places ("controllers that lost their place have re-dispatched entire completed task sequences"). Convergence with the boss-ruled circuit-breaker ladder and one-shot-creator rulings — recorded as supporting evidence on both.

## Extracts executed (this branch)

1. **Baseline-fail-first with a rationalization catalog** (`writing-skills`: "if you didn't watch an agent fail without the skill, you don't know the skill teaches the right thing"; document the exact rationalizations, write the skill against them, close loopholes on re-runs) → appended as a proposed addition to `docs/wiki/queue/skill-authoring-checklist.md` (queued draft, still undrained — the amendment rides the same drain).
2. **Review-reception discipline** (`receiving-code-review`: verify findings against reality before implementing; no performative agreement; all findings understood before any is implemented, since findings interrelate; a finding that conflicts with the plan goes to the human) → new rule 5 in `docs/wiki/queue/agent-loop-rules-draft.md`, where fix-loop rounds begin.
3. **Bidirectional regression witness** (`verification-before-completion`: write → pass → revert fix → must fail → restore → pass; and "agent success" claims require the VCS diff, not the report) → appended to the #20 packet's evidence kernel.

## Supporting evidence filed (no ruling forced)

- `~/.agents/skills` is recognized cross-runtime by Codex, Copilot CLI, and Gemini CLI (superpowers README, which ships to all of them). This is direct supporting evidence for the dormant portability proposal (cops decision 12: root `skills/` + symlinked discovery dirs), which stays unadopted pending its canaries — but its central factual premise is now corroborated by a shipping multi-runtime system.

## Open questions for the boss (asked in-session)

- **Q1 — the ladder is uncapped after the trip.** Superpowers bounds the whole loop (5 rounds total → adjudicate/park/BLOCK). NC's ladder trips at 3 into the fresh-pair reset — and nothing bounds the reset's own rounds. Proposed: the post-trip pair gets a bounded budget (2 rounds), then the change goes to the boss with the attempt history; and the reset runs on a more capable model or higher effort than the looping agent (superpowers' R≥4 rung — escalate the model along with the eyes). Awaiting ruling before the ladder text changes.

## Flank additions (new-vp blind-side read @ 44c9b2d6, 2026-07-31) — triage-list homes, judged this session

- **BASE-recording rule (never HEAD~1 for multi-commit work): declined as subsumed** — the gatekeeper design already requires an explicit full-40-hex `--base` per request; the HEAD~1 failure mode is inexpressible in NC's check-in path.
- **Reviewer-dispatch independence** (a dispatch prompt containing "do not flag X" / "at most Minor" is pre-judging the review): **taken** — extends the ruled isolation invariant (reviewer sees artifact + criteria, never the author's reasoning) with: *nor the dispatcher's expectations*. Rider candidate for d-review/#22's shared finding contract.
- **Minors bypass the fix loop to the ledger; adjudication only at the cap, every adjudication a ledger entry: taken into the ladder amendment** (see Q1 resolution in the walk) — keeps low-stakes findings from burning breaker rounds.
- **Final-fix wave = ONE fixer with the complete findings list + ONE scoped re-review** (donor cost specimen: per-finding fixers cost more than all tasks combined): **taken** as the dispatch-side complement of reception rule 5 (all findings understood before any implemented → all findings *dispatched* as one batch too).
- **Plan-conflict pre-flight as one batched which-governs question: declined for now** — NC has no plan-execution machinery yet; noted for the future executing-plans sibling if one ever exists.

## Declined, with reasons

- **Baseline-fail-first amendment: DROPPED at boss walk (2026-07-31)** — the verbatim failure record already exists automatically in the baseline run's transcript jsonl; skills history lives in git; and NC has no scenarios yet — the amendment was make-work. Checklist amendment reverted (delta to land).
- `brainstorming` / `writing-plans` / `executing-plans` — covered by define-work/design-change plans; the plans-for-a-junior-engineer framing conflicts with NC's zero-context-reader rule only in register, not substance; nothing new to take.
- `using-git-worktrees`, `dispatching-parallel-agents`, `finishing-a-development-branch`, `using-superpowers` — harness mechanics NC re-derives; dispatch hygiene is already superseded by the ruled one-shot/interrogation protocol.
- The verification skill's Iron-Law register and rationalization tables — kernels taken above; the enforcement-by-shouting model is the documented anti-pattern.
