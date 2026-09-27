---
issue: "[Queue drain procedure — the review process that empties the wiki queue, the pair queue, nc-queue, docs/drafts and the draft-label issue queue](https://github.com/nedschorus/nedschorus/issues/24)"
---

# Queue drain procedure — the review process that empties the wiki queue, the pair queue, nc-queue, docs/drafts and the draft-label issue queue

## Why this exists (boss-directed, 2026-07-24)

The artifact-lifecycle design gives every non-final artifact a named queue (`docs/nedschorus-wiki/queue/` for doctrine candidates, `docs/issues/queue/` for pair candidates, the `draft`-labeled issue queue). The boss's ruling at capture, near-verbatim: the missing piece is the maintenance/draining procedure — that is what turns these nice docs into something that is part of the system, not just notes. A queue without a drain is a pile with extra steps; this GHI tracks the drain until it is built into the system.

## The drain (boss-approved 2026-07-24 with the parent ruling)

- The boss walks a queue when he chooses; nothing blocks on it.
- Every item gets exactly one of four outcomes, each leaving a durable record:
  - **promote** — `git mv` to the destination; the move commit is the record.
  - **edit** — revise in place; stays queued.
  - **demote** — down to evidence/transient, attached to its pair or session.
  - **drop** — deleted, with the reason in the commit message; explicit, never silent rot.
- **Starvation visibility is the system half:** the handoff scrub step reports every queue's depth and oldest-item age (it already does this for the `draft` issue queue), so an unwalked queue surfaces at every handoff without anyone remembering to look.

## Build surfaces (when NC builds them)

1. The NC handoff skill's scrub step: add per-queue depth + oldest-age reporting (one grep per queue directory + one label query).
2. Possibly a `drain-queue` walk variant later — only if live drains with walk-me-through prove insufficient; do not build ahead of friction.

## Status and dependency

The parent queue-system ruling was boss-approved 2026-07-24 and executed (commit 4b20892: queues created at `docs/nedschorus-wiki/queue/` and `docs/issues/queue/`, `boss-review` label renamed to `draft`, rule of record in founding plan § Project organization). This GHI remains open for the build half: the NC handoff skill's scrub step reporting every queue's depth and oldest-item age. Until that is built, the drain runs as discipline.



## Drain scheduling — superseded (see the 2026-09-22 ruling below)

The first drain is DEFERRED until the step-2 CLAUDE.md lands (GHI [Step 2: the CLAUDE.md build — NC's instruction floor (founding plan step 2)](https://github.com/nedschorus/nedschorus/issues/43)) — it then runs as a natural next sitting. Queue state at ruling: nc-queue 4 notes (oldest 2026-07-28; TTL 90 days — no pressure), docs/issues/queue 5 pair-bound MDs, docs/nedschorus-wiki/queue 3 docs, draft-labeled issues zero, legacy-feature-queue empty. Nothing is blocked on the drain.

## The drain runs now (user-ruled 2026-09-22)

**"Let do it as soon as this walk completes."** Ruled at item 8 of the walk `open-questions-concerns-and-recommendations-2026-09-21`, which closed the same day. This supersedes the 2026-08-06 deferral above: that one waited on GHI [Step 2: the CLAUDE.md build — NC's instruction floor (founding plan step 2)](https://github.com/nedschorus/nedschorus/issues/43), which closed 2026-08-06, and nothing ran in the seven weeks after. The replacement deferral was bounded by a named event rather than left open.

### `docs/drafts/` is in scope

The user named drafts on 2026-09-19 — "at some point we need to clean out the queue and drafts" — and again in ruling the drain. It is a fourth location this procedure now covers.

Recorded because it looked like settled doctrine and is not: GHI [Four small skills the user named on the vocabulary page: /save, /push, /save-MD, /save-MD-as-draft (name open)](https://github.com/nedschorus/nedschorus/issues/256) contains the sentence "`docs/drafts/` holds in-progress documents that are not queued for review". That sentence sits **inside an open question being put to the user**, not a ruling, and nothing else in the repository says it: `grep -rn 'not queued for review' --include='*.md'` over the tree returns nothing. So drafts had no settled status either way, and the user's words give them one.

### Queue state at the ruling

Measured against main at `5f0fd4c` on 2026-09-22 — **58 items**:

| location | items |
|---|---|
| `docs/issues/queue/` | 22 |
| `docs/nedschorus-wiki/queue/` | 8 |
| `docs/drafts/` | 9 |
| `nc-queue/`, live | 4 |
| issues labelled `draft` | 3 |
| `docs/agents/queue/` | 12 |

`nc-queue/archived/` holds 6 more, already disposed of and not counted.

**`docs/agents/queue/` is in scope**, corrected the same day. An earlier count put it out of scope as the skill-builder seat's working drafts; the glossary's own definition of queue-drain names it as one of the four queue directories, and the user ruled to go through all of them: "I want to clean up stuff that needs cleaning up, and log or remove stuff that does not. I don't know what's in these queues. So why not go through all of them - unless they are obviously junk." Its 12 files are the design-to-main agent-instructions, added 2026-09-08 and last touched 2026-09-16 to -18, so they are a recent coherent set rather than accumulated drift — which may make them one decision rather than twelve.

### Two questions already answered by measurement — not to be reopened at the sitting

- **Nothing has to move.** Relocating all four directories would rewrite 138 citations across 91 files (`nc-queue/` 21 in 16, `docs/issues/queue/` 44 in 34, the wiki queue 26 in 19, `docs/drafts/` 47 in 22). Each sits beside what it feeds, and no agent is recorded as failing to find one.
- **The drafts are pre-walk drafts, not GHI-MDs** — a GHI-MD lives in `docs/issues/` named by its number. Of the 9, four are named by an issue and five by none; two are for work that has since landed.
