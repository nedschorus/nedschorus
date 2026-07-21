---
status: draft
---

# fast-pr-to-prod — the single-writer throat (for the boss + new-vp markup)

How a change reaches main (= production, until the first long-running process exists) in nedschorus. Re-derived from the actual requirement — one human, one writing agent, one drafting companion — rather than migrated from the quarry's many-writer design (`git-clean-slate-plan.md`, frozen quarry reference). Companion issue: nedschorus#3.

## The architecture: one throat to main

- **One identity can push to main, ever** — enforced by branch protection (its single surviving job: a lock with one keyholder, not a referee among N writers). The quarry's sanctioned-path lesson: a throat enforced by convention gets bypassed; this one is structural.
- **Choirmaster's own change:** edit in the canonical checkout → commit at every coherent change (session id in the message) → push. Three verbs, no branch, no PR, no parking state.
- **The companion's change:** draft freely in its own clone (any paths, never pushes) → promotion request → the promotion job validates against CURRENT main, stamps provenance (whose draft, which session), writes the entry-manifest line if a quarry import, commits, pushes. Best-of-both synthesis is choirmaster merging drafts before promotion.
- **The promotion job is as dumb as possible:** a script for the simple case; a spawn-per-job background subagent (cheap model, dies when done) for multi-step promotions; choirmaster only for rare oddities. No persistent committer.
- **Gates sit upstream, verified at the throat:** for boss-designated gated classes, review happens before promotion and the throat mechanically refuses a promotion whose gate evidence is missing. Quality is an input the throat checks; serialization is what the throat is.

## States (four, none where work ages)

| State | Meaning | Exit |
|---|---|---|
| EDITING | Uncommitted work in a checkout | Commit (as-you-go) |
| COMMITTED | In the single writer's local main | Push |
| PROMOTION-PENDING | A companion draft awaiting its promotion job | The job lands or refuses it |
| LANDED | On origin/main | — (deploy = landed, until the first daemon exists; that gap is designed when it appears) |

## Checks ship with the throat, day one

One path means every check has one place to live and one flow to cover (boss ruling 2026-07-21: "not after, but asap"). In the promotion script from the start: provenance stamp, entry-manifest presence for imports, subsystem-structure hygiene, gate evidence for gated classes, current-main validation. Each is a few lines because it polices one door — the quarry's checks grew huge policing N paths and every bypass spelling.

## From the quarry's git plan: survives / dissolves / defers

- **Survives (task-1 imports, small):** the two-line git config (§2.1, adapted); workflow rules rewritten for the four-state machine; protection as the single-identity lock; enforcement-at-the-remote as principle; stay-near-main as a read-side habit (companion pulls before drafting) + the throat's promotion-time validation as the mechanical backstop.
- **Dissolves (never imported):** three GitHub Apps; credential helper and per-agent tokens; per-agent branches and the PR pipeline for ordinary work; all parking states; the orphaned-ephemeral-author problem; the one-OS-user reviewer-key hole (no reviewer key exists to mis-load).
- **Defers, each with a reopening trigger:** PR flow for a designated artifact class (trigger: the boss wants a review-parked class — may never fire); multi-writer machinery (trigger: a genuine third head or true co-writing); merge-vs-deployed handling (trigger: the first long-running process).

## Task-1 consequence

Choirmaster's first task = git config + the throat script with its built-in checks + the protection lock + the prompt rules. Bounded, testable, code-heavy, first-task-sized.

## Open for the boss

- The throat identity: choirmaster's own credential, or a dedicated committer identity choirmaster wields? (Attribution rides in commit messages either way.)
- Which artifact classes are gated (review-before-promotion) from day one, if any.
