---
issue: "[Trigger-first instruction delivery (moved from nedlern#1972): delivery timing as a property of every instruction — step-2 CLAUDE.md design input + carried design and scan](https://github.com/nedschorus/nedschorus/issues/30)"
---

# Trigger-first instruction delivery (moved from nedlern#1972): delivery timing as a property of every instruction — step-2 CLAUDE.md design input + carried design and scan

## What this captures

The trigger-first instruction-delivery program, moved here from the legacy tracker ([nedlern/nedlern#1972](https://github.com/nedlern/nedlern/issues/1972), now closed onto this issue) on the boss's direction 2026-07-27: nedlern is being decommissioned, so the legacy issue is no longer a durable home. This issue is the MD-GHI pair's state; the substance is in the two carried documents below.

## The idea (boss, 2026-07-18 legacy walk, marked important)

Delivery timing becomes a property of every instruction, not a placement. Rules that are infrequently needed AND detectable just-in-time (a tool about to run, a file type being touched, a phrase from the user or the agent, a watcher) move out of always-loaded CLAUDE.md to triggered injection — the instruction re-arrives fresh at the moment of need, which also defeats retention decay under token spend. Session-start delivery becomes one trigger among many.

Boss working assumptions recorded with the idea: agents retain most content for roughly 100k tokens; space re-injection of the same rule to roughly 50k–100k tokens since its last delivery; moderate over-firing is tolerable ("it's just instructions") — the guard is aggregate context spend.

## Carried documents (the pair's substance)

- [docs/issues/30-trigger-first-instruction-delivery-design.md](https://github.com/nedschorus/nedschorus/blob/main/docs/issues/30-trigger-first-instruction-delivery-design.md) — the wave-0 design of record (revision 3, d-review complete, verdict READY): the generic injector mechanism + declarative trigger map, injection-only boundaries, spacing guard, audit loop.
- The 348-line CLAUDE.md enforcement scan — **STRUCK by boss ruling 2026-07-27** (it had crossed on agent judgment beyond his named scope; its per-row verdicts judge nedlern's content under nedlern's enforcement and do not port to NC). What may port is the METHOD — classify every instruction line against actual enforcement to find what must stay always-loaded — whose consumer is the step-2 CLAUDE.md design. When step 2 runs, pull the scan from nedlern main at `docs/working/trigger-first-instruction-delivery-scan-first-pass.md` and apply the method to NC's own content.

Not carried (boss-ruled notes/speculative for a pruned mechanism): the thoughts, cold-review, and hook-spam-audit files. They remain in nedlern git history until decommissioning.

Also preserved here because its only other home is the decommissioning repository — **the boss's 2026-07-19 orphaned-MD adoption** (provenance: [nedlern/nedlern#1972 comment 5086000371](https://github.com/nedlern/nedlern/issues/1972#issuecomment-5086000371)): (1) a work-bearing draft names its tracking issue on a `Tracked-by: <issue>` line inside the draft itself; (2) `Record-only: no pending work` is the opt-out marking a genuine findings log, so the absence of an issue reads as deliberate; (3) mandatory MD-per-GHI was DECLINED (it multiplies the orphan/rot surface; the underlying need is bidirectional linkage, with any repo-native index generated, never hand-authored). NC-relevant because the same linkage question arrives with ghi-write/md-write (GHI [Build ghi-write (step-1 founding skill): trigger on creating or revising a GHI; enforce edit-don't-comment-or-duplicate](https://github.com/nedschorus/nedschorus/issues/13)).

## Relations

- The step-2 CLAUDE.md rewrite is the natural consumer: what stays always-loaded vs what becomes triggered is a step-2 design question (founding plan step 2).
- The runtime-behavior research bundle measures the other half of the same problem — what a fresh agent retains from always-loaded files: https://github.com/nedschorus/nedschorus/issues/29
- Evidence available from the legacy side while it lasts: the trigger-injection mechanism is LIVE on nedlern main (it survived the wave-0 prune), a working reference implementation.

## Close condition

Closes when NC's instruction-delivery design either adopts trigger-first delivery (in step 2 or a successor design) or explicitly rejects it with the reason recorded.

—
Session: 3b576242-213e-43a2-bd16-80a1a36f67e7 (new-vp). Body revised 2026-07-27 (same session): from forward-idea-only to full carry, per the boss's decommissioning direction.
