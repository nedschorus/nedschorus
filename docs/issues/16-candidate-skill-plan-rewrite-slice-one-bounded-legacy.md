---
issue: "[Candidate skill: plan-rewrite-slice — one bounded legacy slice with four-way behavior classification](https://github.com/nedschorus/nedschorus/issues/16)"
---

# Candidate skill: plan-rewrite-slice — one bounded legacy slice with four-way behavior classification

When cherry-picking from the legacy system: one bounded end-to-end slice; write current legacy behavior vs target design; classify EVERY legacy feature the slice touches per the rewrite policy's four classes — preserve-feature (the feature's contract, probably not its implementation; named + test-pinned) / update-feature (divergence recorded) / remove-feature (reason recorded — "defective" when that is why) / consider-feature (blocks nothing; if it outlives the slice it parks in `legacy-feature-queue/`, never a GHI). Gate = every feature classified, never zero-diffs; unexamined is never preserved. Vocabulary boss-ruled 2026-07-24 (walk item 13), superseding MUST PRESERVE / INTENTIONAL CHANGE / OLD BUG / UNRESOLVED; policy of record: founding plan § Standing decisions (commit d3383f8). Key evidence finding: the OpenAI modernization source actively entrenches old defects (default aligns new code to old behavior) — structure donor and named anti-pattern only. cops: evidence + oracle ownership per classification.

## Disposition: candidate-on-GHI, not built (boss-ruled 2026-07-24)

Captured per the artifact-lifecycle rule (pending state -> GHI, lean -> issue-only). Boss ruling on the outer walk (session ad0a3708): candidates are recorded, none is built now; a build triggers only when a real task exposes the missing decision (cops item-12 delta: select ONE candidate from the first real task). Define-work carried the individual ruling "at best it's worth a GHI in nc"; the remaining eight were approved as a batch off the collapsed-walk summaries.

## Evidence of record

- Six-agent source read: `nc-queue/archived/2026-07-22-candidate-skill-source-evidence.md` (this skill's section)
- cops delta packet: `nc-queue/archived/2026-07-23-cops-candidate-skill-delta-packet.md` (this skill's section)
- Shortlist origin: `docs/issues/9-neds-notes.md` § Working skill shortlist
