---
status: specification
---

# fast-pr-to-prod — the single-writer throat (specification)

How a change reaches main in nedschorus. Main is production until the first long-running process exists (no deploy step exists yet; one is designed when such a process appears). Actors: choirmaster (the single writer), the companion (drafts in its own clone), the boss. The name is the family name for the re-derived minimal pipeline; ordinary changes use no pull request.

## The throat

- **Exactly one identity can push to main: choirmaster's credential.** Enforced by branch protection — a lock with one keyholder. Account layout (boss-ruled 2026-07-21): the machine account — the shared agent credential that pushes today — is choirmaster's credential and the lock's sole keyholder; the boss's personal account holds repository admin for settings and issue triage and has **no push path**. The boss never commits directly: a boss-originated change is drafted with an agent and lands through the throat like any other. The lock costs nothing on the issues surface — the repository is public, so opening and commenting on issues needs no repository permission (the triage role adds labeling and closing without code-write). The remote enforces only this lock; the checks live in the landing script below. The companion has no git identity; anything it produces lands under choirmaster's credential with the companion's attribution stamped in the commit message.
- **One landing command for every change.** `scripts/throat.py land` is how ANYTHING reaches main — choirmaster's own work and companion promotions alike. It runs the checks, writes the provenance stamp (producing session id; for companion drafts, whose draft), commits, and pushes. Choirmaster does not raw-push; the kernel instructs landing through the script, and since choirmaster is the only identity that CAN push, a raw push is a deliberate bypass — a cooperative-model residual the boss's reading catches, not a mechanical impossibility.
- **Choirmaster's own change:** edit in the canonical checkout → `throat.py land` at every coherent change. No branch, no pull request, no parking state.
- **The companion's change:** draft freely in its own clone (it never pushes) → append a **promotion request** to its mini-comms log — the draft's path list in its clone, its base commit (the main SHA it drafted against), any declared quarry imports (source SHA + path each) → choirmaster picks the request up at its next turn and either runs `throat.py land` directly (single-file, clean apply) or spawns a background promotion subagent for multi-step work (reading a proposal, deciding placement, reconciling with moved main). The routing is choirmaster's call; the subagent runs inside choirmaster's session and therefore wields its credential. Best-of-both synthesis (both heads drafted the same artifact) is choirmaster merging the drafts, then landing the result like any of its own changes.

## The checks — inside `throat.py land`, from day one

Checks run per landing, against the exact tree being landed (the composed result after any reconciliation, not the earlier working tree); a refusal refuses the whole landing, structured and named — what failed, why, the next step. No silent failures.

| Check | Behavior |
|---|---|
| Provenance | The script WRITES the stamp itself — injected, not remembered — as a fixed parseable trailer schema: base SHA, producing session and runtime, drafts' attribution, task/issue id, declared imports, review evidence, validation result (readable with `git interpret-trailers`; the trailers ARE the machine-readable record). Refuses only if it cannot determine the producing session (missing/empty session-id environment). |
| Declared-vs-actual paths | Refuses when the landing's actual diff touches paths outside the promotion request's declared path list. Binds promotions; choirmaster's own landings declare implicitly (the working diff is the declaration). |
| Replay protection | Refuses a promotion request whose request id already appears in a landed commit's trailers — one request lands at most once. |
| Entry manifest | Refuses when the landing's DECLARED quarry imports (from the promotion request, or named by choirmaster for its own work) lack a matching `entry-manifest.md` line — matched on repo path — in the same landing. An undeclared import is undetectable mechanically; that residual is accepted and caught by the boss's reading. |
| Subsystem hygiene | Refuses when a file's path and name carry no token from the known set (the set = top-level subsystem directory names currently in the repo), or when two-plus same-token files sit directly in one top-level root that should hold a subsystem subdirectory (the lazy-subdirectory rule). A token not in the known set is NOT a refusal: the landing proceeds and the script files a `boss-review` issue ("new subsystem, or synonym drift?"). Test-naming rules are enforced at writing time by the writing skills, not here. |
| Gate evidence | Dormant until the boss designates a gated artifact class; the evidence format is defined at designation. Once designated: refuses a landing of that class carrying no review evidence. (Distinct from the deferred PR flow: gating verifies review happened before landing; PR flow would park the artifact in a GitHub review state — that machinery stays out unless the boss wants it.) |
| Current-main validation | For promotions: refuses only what cannot be reconciled. The job applies the draft onto current main; if files changed on main since the draft's base commit conflict with it, the multi-step job reconciles; when reconciliation would require the companion's intent, the landing is refused with the defect and the companion re-drafts against current main. |

## States

| State | Meaning | Exit |
|---|---|---|
| EDITING | Uncommitted work in a checkout (either agent's) | Choirmaster: `throat.py land`. Companion: promotion request → PROMOTION-PENDING. |
| PROMOTION-PENDING | A companion draft whose request awaits pickup | Choirmaster handles it at its next turn: lands it, or refuses it with the named defect → back to the companion's EDITING for revision. Bound: pickup latency is one choirmaster turn; the request sits in the boss-readable mini-comms log, so a stalled request is visible, never silent. |
| LANDED | On origin/main | — |

(The earlier COMMITTED state collapsed into `land` — the script commits and pushes in one call.)

## Reading discipline

Any checkout other than the canonical one pulls before drafting. The mechanical backstop is current-main validation at landing time.

## Relationship to the quarry's git design

The quarry's `git-clean-slate-plan.md` (read-only reference, `~/Projects/nedlern/docs/working/proposed/`) designed the many-writer version of this problem. nedschorus imports from it only the workflow-rules idea (rewritten for the states above) and the protection-as-lock idea (reduced to one keyholder). The repo's own git config is minimal and stated here, not imported: `user.name` / `user.email` for choirmaster, `useConfigOnly` so no global identity leaks in. Never imported: the three GitHub Apps, the credential helper, per-agent branches, the PR pipeline for ordinary work, the parking states. Deferred with reopening triggers: PR flow for a designated class (trigger: the boss wants a review-parked class); multi-writer machinery (trigger: a genuine third head or true co-writing); deploy handling (trigger: the first long-running process); App-or-CI-identity-as-sole-writer remote enforcement with compare-and-swap landing — the rung that makes the no-raw-push rule mechanical instead of cooperative (trigger: the cooperative residual is observed being hit, or the boss admits the rung on the prior-art evidence in `docs/issues/5-prior-art-cross-check.md`, shortlist item 1).

## Build slice (choirmaster task 1)

The git config above + `throat.py land` with its built-in checks + the protection lock + the workflow rules as kernel lines. Bounded, testable, code-heavy.

## Open

- Which artifact classes are gated from day one, if any. The boss designates (and the evidence format is defined then).
