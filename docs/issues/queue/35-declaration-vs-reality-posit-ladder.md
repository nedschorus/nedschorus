# Ladder extension for pair #35 (declaration-vs-reality) — the posit system at three granularities

Queued for the boss's drain (promote / edit / demote / drop). Source: `nc-queue/2026-07-28-sdlc-skill-set-coverage-and-app-skill-pile.md` §2 (rewalked) and §6a (boss-walked 2026-07-29/30). Destination: [nedschorus#35](https://github.com/nedschorus/nedschorus/issues/35) — this extends that thread's primitive (declare expectation → observe reality → mismatch is red) down a granularity ladder; it is one system with one home, not a new thread. Status: direction with ruled structure; awaits a real codebase to instrument.

## The ladder (coarse → fine)

1. **System/path-class tags** (#35's existing subject): code tagged with expected firing class; both mismatch directions are alarms — EMERGENCY-ONLY firing weekly is a live incident detector; HOT never firing is a dead path or misroute.
2. **Branch classes (boss-ruled 2026-07-30):** every branch (CFG edge; one line may hold one decision of several conditions) carries a frequency-class posit — HOT / NORMAL / RARE / NEVER-except-emergency. Totality is a lintable exhaustiveness check. Numeric posits (relative to the enclosing function, e.g. "<1% of calls") only where the design states a frequency. Instruments split by question: event-based coverage (coverage.py on `sys.monitoring`, dynamic contexts) verifies existence and the RARE end via synthetic exercise; sampling (py-spy) verifies HOT/NORMAL distribution — sampling alone cannot distinguish cold from dead; tags remove that burden. Precedent: measurement side mature (PGO/gcov branch profiles); the declared-expectation side is novel — nearest is FoundationDB `CODE_PROBE` (binary reach); this is its quantitative generalization.
3. **Test reach posits:** each test declares the design-significant paths it exercises; declared set diffed per-test against measured execution — red on posited-but-unreached or reached-but-forbidden. (Also queued as a #18 rider.)

## Integrity rules (boss-ruled)

- Posits are **predictions**: written from design + code reading before consulting measurement; a posit transcribed from a run has zero information (snapshot-blessing failure mode).
- **Provenance on every posit**: design-claim reference or dated `author-judgment`; basis-less posits are lint-red. Mined invariants (Daikon-style) are hypotheses — measurements never self-promote; each needs a design-traceable reason or a boss stamp.
- **Five-verdict mismatch resolution, no silent blessing**: code wrong / posit wrong (reason about intent, never "measurement said so") / design silent (name the new claim, stamp it) / instrument wrong (the harness lies like any code) / environment wrong (network, race, system bug, misconfiguration, malice). A posit edit without a classification is mechanically refusable.
- **The harness proves it can fail**: periodically plant a deliberately wrong posit and confirm red.
- **Diff harness, counters, joins are code, not prompts** (founding principle 3): agents judge inside the frame; the frame that checks them is code.
- **Pilot-measurement obligation (boss-ruled 2026-07-30)**: the first implementation measures whether every-branch positing stays within the goal framing — "not too token heavy" (write-time posit generation, storage, and check-time cost) — before the practice generalizes beyond the pilot. The every-branch ruling is conditional on that measurement, not assumed.

## Context

The boss's framing (2026-07-29): the hard problem is not removing obsolete code but determining what is used frequently versus never, and why — zero usage has four causes (lucky so far / superseded / flawed premise visible / flawed premise invisible) with four remedies; usage data finds candidates, the why is judgment. Companion improvements ruled in the same walk: design-change obsolescence sweep (pair #17 checklist line); patch-cycle tripwire generalized to a circuit breaker on closed agent loops (draft engineering rules queue).
