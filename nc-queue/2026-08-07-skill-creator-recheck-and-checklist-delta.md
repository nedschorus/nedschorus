# Anthropic's `skill-creator` re-check — what it carries that our checklist does not (2026-08-07)

Boss-requested. The thread that produced it: asked whether NC has a GHI for a skill-authoring skill (answer: no — the doctrine lives as `docs/wiki/queue/skill-authoring-checklist.md`, a doc consulted by pointer from nedschorus#15–#23, and no GHI tracks a skill), the boss directed a look at Anthropic's skill-authoring skill before any further move on that question. This note records what the source is, what NC already took from it, and the delta between the source as it stands today and our checklist.

## 1. What it is and where it is

`skill-creator` — Anthropic's official skill for creating, improving, and measuring skills. Installed on this machine in two places, and live in this session's skill listing as `anthropic-skills:skill-creator`:

- `~/.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-creator/skills/skill-creator/` — plugin-marketplace clone.
- `~/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/<session>/<id>/skills/skill-creator/` — app-bundled copy, present under two session ids, identical to each other.

**Content of record is the app-bundled copy**, which is the newer content line despite the marketplace clone's later file mtime: it carries a `SendUserFile`/Cowork-remote delivery path and a nested-`SKILL.md` rejection check in `quick_validate.py` that the marketplace clone lacks. The two differ in exactly two files (`SKILL.md` §Package and Present, four lines; `quick_validate.py`); nothing doctrinal turns on the difference.

Size today: 18 files, 5,453 lines, of which 2,368 are Python. `SKILL.md` is 485 lines; the rest is three subagent instruction files (`agents/grader.md`, `agents/comparator.md`, `agents/analyzer.md`), one reference (`references/schemas.md`, 430 lines), nine scripts, and an eval viewer.

## 2. NC has already read this source once

Full read 2026-07-22 (recorded then as 21 files / 5,464 lines), walked 2026-07-24 as outer walk item 11. Record: `nc-queue/archived/2026-07-22-skill-creation-and-improvement-deep-dive.md`. Ruling: **read-for-ideas-only** — no adoption, no dependency, no import of its loop; its creation doctrine became `docs/wiki/queue/skill-authoring-checklist.md`, its test doctrine governs agent-facing skills, its utilities wait for real need, and its eval loop is a ladder rung NC revisits only on evidence that live iteration misses real failures.

Status of the three sub-questions that dive left open:

1. NOT/DO vs explain-why register — **resolved**; the checklist carries the resolution (explain-why as default, NOT/DO reserved for training-default overrides).
2. Whether the checklist folds into founding-plan step 1 — **resolved**; step 1 points at it, as do #15–#23.
3. Whether the description-tuning mechanism ever earns a rung, and on what evidence — **still open**. The delta below feeds this one.

## 3. The delta: current source vs. our checklist

This is a comparison of the source *as it stands today* against the checklist. It is not a claim about what changed in the source since July — the July snapshot lived in that session's scratchpad and was not retained. If the boss wants the source's own change history, the receipt is the public `anthropics/skills` repository's git log; not fetched.

**a. The eval harness exists as a working reference implementation, not just as doctrine.** `scripts/run_eval.py`, `scripts/aggregate_benchmark.py`, `agents/grader.md`, and the review viewer implement: spawn with-skill and baseline runs in the same turn; per-iteration workspace directories; timing captured from the task notification (the source notes this is the only moment that data exists); scripted grading over named assertions; mean ± stddev with the delta; an analyst pass over the aggregate to surface non-discriminating assertions and high-variance evals. nedschorus#23 (`eval-agent-change`) is the same shape — baseline-vs-candidate A/B, positive and near-miss negative triggers, raw counts. #23's recorded sources are the Anthropic evals article, the April-23 postmortem, and Microsoft Waza; the source-evidence note connects it to the deep-dive's test doctrine, but **no NC artifact cites skill-creator's harness as a reference implementation for #23**. The doctrine link is recorded; the runnable comparison is not.

**b. The description optimizer is a real, runnable mechanism** (`scripts/run_loop.py`): 60/40 train/held-out split of a trigger eval set, each query run three times for a trigger rate, Claude proposes description revisions from the failures, up to five iterations, and **the winner is selected on the held-out test score rather than the train score, explicitly to avoid overfitting**. That last property is what makes it more than a tuning loop. This is open sub-question 3 above, still unruled.

**c. A stated triggering mechanic our checklist does not carry, which bears on any NC trigger test.** The source states that Claude consults a skill only for tasks it cannot easily handle directly — simple one-step queries may not trigger a skill *however well the description matches*, so such queries are poor test cases regardless of description quality. Our checklist has the near-miss rule for negatives; it says nothing that would stop an NC trigger test from being built on positives that cannot discriminate. Note this is the source's assertion about runtime behavior, not something NC has measured.

**d. Realism rules for trigger queries.** Concrete and specific over abstract — file paths, column names, company names, a little backstory, some lowercase/typo/casual phrasing, mixed lengths, edge cases over clear-cut ones, ~8–10 each side. Our checklist requires near-miss negatives but says nothing about query realism, and the source's worked bad/good pair makes the difference plain.

**e. A discovery procedure for the checklist's own question 5.** Our newest checklist question asks which steps are machine work — but gives no method for finding the answer. The source gives one: read the run transcripts, and when several independent runs each wrote the same helper script or repeated the same multi-step approach, that is the signal to bundle a script and have the skill call it. That is question 5 answered from evidence rather than from a judgment made at the desk.

**f. Improvement-loop discipline, lightly held in our checklist.** Generalize from feedback rather than patching the specific examples (the examples are a fast proxy; a skill that works only on them is useless); keep the prompt lean and delete what is not pulling its weight; read the transcripts, not only the final outputs, since wasted work is visible only there.

**What our checklist has that the source does not** — so this reads as a delta, not a deficit: skill atomicity with explicit-path references and shared concepts defined once in CLAUDE.md; NOT/DO reserved for training-default overrides; instruction form matched to the failure it fixes, with the wording-test evidence; absolutes get code enforcement or stay reasoned rules; refuse-with-questions as headless can't-ask behavior; the register rule that keeps statistics and incident specimens out of skill bodies.

## 4. The GHI question this note serves

Given that a skill-authoring skill already exists, is installed, and is live in the session listing, the options for NC are:

- **(a) No NC skill.** The checklist stays a doc, consulted by pointer from each skill-build GHI. Cost: it fires only when someone remembers to open it — the same failure mode that justified `ghi-write` (nedschorus#13).
- **(b) Point at `skill-creator` and carry only the NC deltas.** A thin NC skill or CLAUDE.md line that triggers on skill authoring, defers mechanics to the installed skill, and adds only §3's "what our checklist has" list. Cost: a dependency on an app-bundled artifact NC does not control.
- **(c) Build an NC skill-authoring skill** from the checklist, on the `ghi-write`/`md-write` pattern. Cost: the build itself, plus keeping it from drifting against a maintained upstream.

No recommendation is offered here; the boss asked for research first.

**Why a skill can beat a document, boss-stated 2026-08-07:** a skill is triggered automatically at the moment it applies, where a document is followed only when someone opens it; and a skill can carry programs and actions, not prompt text alone. Both properties count against option (a) — the checklist as a doc has neither. This is the same argument that justified `ghi-write` (nedschorus#13), and it connects to §3e: the machine work a skill can absorb has to be identified before it can be written.

## 5. Receipts and gaps

Verified this session: both install paths and their file listings; the two copies diffed (two files differ, as described); `SKILL.md` read in full; `skill-creator` absent from every NC issue body under six phrasings (`write-skill`, `skill-write`, `build-skill`, `author-skill`, `skill-author`, `skill.creator`) across all 45 issues; #23's body and its source-evidence section read for existing prior-art citation.

Not done: the source's own change history since 2026-07-22; the three `agents/*.md` files and `references/schemas.md` were listed and sized but not read line-by-line — §3a's description of the harness comes from `SKILL.md`'s account of what those files do.

## Walk order

Walk opened 2026-08-07, restarted at item 1 the same day for clarity (the first opening asked an unanswerable yes/no about a negatively-stated rule). Dispositions are marked against this list.

1. Purpose — what this walk decides: six differences, then the build question. Nothing is built during the walk. — processed 2026-08-07 → accepted; the boss's why-a-skill-beats-a-document reason recorded at §4.
2. §3a — skill-creator's eval harness as a reference implementation for nedschorus#23. — processed 2026-08-08 → accepted; prior-art bullet added to the eval-agent-change issue body (Evidence of record section), edit visible in that issue's edit history. (The anchor-update commit 05cb2b9 misdates this approval 2026-08-07; the walk resumed past midnight.)
3. §3b — the description optimizer's held-out-test selection; the deep-dive's open sub-question 3. — processed 2026-08-08 → rejected as checklist doctrine, revised from the initial append-a-bullet proposal: description tuning is an activity NC does not do — a heavily-trained concept triggers from a plain description, and for subtle skills the trigger evals are nearly as hard as the skill itself (boss-ruled). Sub-question 3 closes declined-with-condition: any future description-tuning proposal must carry held-out judgment as a precondition, argued fresh on that day's evidence. The checklist is untouched.
4. §3c — the triggering mechanic that makes easy positive trigger cases non-discriminating.
5. §3d — realism rules for trigger queries.
6. §3e — the transcript-reading procedure for the checklist's which-steps-are-machine-work question.
7. §3f — improvement-loop discipline (generalize, keep lean, read transcripts).
8. §4 — the GHI question: no NC skill / point at skill-creator / build one.
