---
issue: "[What NC preserves, where it goes, how that is codified, and how it is kept from drifting — design pair (destination: wiki page with subpages)](https://github.com/nedschorus/nedschorus/issues/32)"
---

# What NC preserves, where it goes, how that is codified, and how it is kept from drifting — design pair (destination: wiki page with subpages)

## What this captures

The preservation-and-placement design pair — what NC preserves, where each class goes, how the rules become code and skills, and how the parts are kept from drifting apart. Substance: [docs/issues/32-preservation-and-placement.md](https://github.com/nedschorus/nedschorus/blob/main/docs/issues/32-preservation-and-placement.md), walked and ruled by the boss 2026-07-27/28. **Destination form (boss-set): graduates into a wiki page with subpages when matured.**

The four parts, one line each (the MD carries the full substance):

1. **Inventory** — four classes: git-preserved (free), vendor-preserved (the vendor's job; archive the legacy repository, never delete it), machine-local (the only class taking real decisions; shrinks by placement, not by backup), deliberately-unpreserved-or-regenerable (recorded so absence reads as intent). Governing economics: losing ~5% of work beats hoarding material that taxes search and context.
2. **Placement** — durable state belongs in the repository, moved at natural boundaries; machine-local is for live state; the global scope holds nothing.
3. **Codification** — no new machinery: duties assign to the gatekeeper (GHI [main-gatekeeper — the single check-in gate (design: nc-systems/main-gatekeeper/main-gatekeeper-design.md)](https://github.com/nedschorus/nedschorus/issues/3)), the handoff build (GHI [Build fast-handoff (renames to handoff at entry) — script, skill, dogfood, per docs/cross-project/fast-handoff-design.md](https://github.com/nedschorus/nedschorus/issues/2)), and the writing skills (GHI [Build ghi-write (step-1 founding skill): trigger on creating or revising a GHI; enforce edit-don't-comment-or-duplicate](https://github.com/nedschorus/nedschorus/issues/13)); the graduated wiki page owns the recorded inventory.
4. **Maintenance** — three anti-drift disciplines, plus detection as the guarantee: a scheduled watermarked sweep PROGRAM (not an agent) that enumerates new artifacts per store, classifies by rule, archives (never deletes; 30-day TTL on archives), and hands only the unclassifiable residue to an agent.

## Open questions

1. Memory placement: do memories become a tracked repository directory? (Costs and benefits in the MD § Open questions.)
2. Log extracts at boundaries — owned by the bridge specification's open section; tracked here as a placement consumer only.
3. Shared-store writes by temporary workers: ban, or allow-and-sweep-by-dead-session?

## Close condition

Closes when the pair graduates to its wiki page with the open questions resolved, or is superseded.

—
Session: 3b576242-213e-43a2-bd16-80a1a36f67e7 (new-vp)
