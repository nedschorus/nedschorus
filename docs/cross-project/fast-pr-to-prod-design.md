---
status: specification
---

# fast-pr-to-prod — the single-writer throat (specification)

How a change reaches main in nedschorus. Main is production until the first long-running process exists; the deploy gap is designed when that process appears. Actors: choirmaster (the single writer), the companion (drafts in its own clone), the boss.

## The throat

- **Exactly one identity can push to main: choirmaster's credential.** Enforced by branch protection — a lock with one keyholder, not a referee among writers. The companion has no git identity; its attribution rides the provenance stamp the promotion job writes into each commit message (whose draft, which session).
- **Choirmaster's own change:** edit in the canonical checkout → commit at every coherent change, session id in the message → push. Three verbs; no branch, no pull request, no parking state.
- **The companion's change:** draft freely in its own clone (any paths; it never pushes) → promotion request → the promotion job lands it through the throat. Best-of-both synthesis (both heads drafted the same artifact) is choirmaster merging drafts before promotion.
- **The promotion job is as dumb as possible:** a script for the simple case; a spawn-per-job background subagent for multi-step promotions (reading a proposal, placement, collision with moved main); choirmaster itself only for rare oddities. No persistent committer process exists.

## The checks — all at the throat, from day one

One path means every check has one place to live. The promotion script carries, from its first day:

| Check | Refuses when |
|---|---|
| Provenance | The commit message lacks the producing session id (and, for companion drafts, whose draft it is). |
| Entry manifest | The promotion contains quarry-sourced files without a matching `entry-manifest.md` line in the same commit. |
| Subsystem hygiene | A file carries no known subsystem token; two-plus same-token files sit loose in one root; a test lacks the test marker. A NEVER-seen token is routed to the `boss-review` queue ("new subsystem, or synonym drift?"), never blocked. |
| Gate evidence | The artifact belongs to a boss-designated gated class and carries no review evidence. Review happens before promotion; the throat only verifies it happened. |
| Current-main validation | The draft was made against a stale tree and no longer applies cleanly to current main. |

Every refusal is structured and named — what failed, why, next step. No silent failures.

## States (four; none is a place where work ages)

| State | Meaning | Exit |
|---|---|---|
| EDITING | Uncommitted work in a checkout | Commit (as-you-go) |
| COMMITTED | In the single writer's local main | Push |
| PROMOTION-PENDING | A companion draft awaiting its promotion job | The job lands it or refuses it with the named defect |
| LANDED | On origin/main | — |

## Reading discipline

Any checkout other than the canonical one (the companion's clone, a subagent workspace) pulls before drafting. The mechanical backstop is the throat's current-main validation: a stale draft is caught at the one moment it matters.

## Relationship to the quarry's git design

The quarry's `git-clean-slate-plan.md` (read-only reference, `~/Projects/nedlern/docs/working/proposed/`) designed the many-writer version of this problem. From it, nedschorus imports only: the two-line git config, the workflow rules rewritten for the four-state machine, protection as the single-identity lock, and enforcement-at-the-remote as the principle. Never imported: the three GitHub Apps, the credential helper, per-agent branches and the PR pipeline for ordinary work, the parking states. Deferred with reopening triggers: PR flow for a designated artifact class (trigger: the boss wants a review-parked class); multi-writer machinery (trigger: a genuine third head or true co-writing); merge-versus-deployed handling (trigger: the first long-running process).

## Build slice (choirmaster task 1)

Git config + the throat script with its built-in checks + the protection lock + the workflow rules as prompt lines. Bounded, testable, code-heavy.

## Open

- Which artifact classes are gated (review-before-promotion) from day one, if any. The boss designates.
