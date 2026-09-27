---
issue: "[Open research thread: usage-vs-expectation observation — obsolescence is a design problem, not an age problem](https://github.com/nedschorus/nedschorus/issues/35)"
---

# Open research thread: usage-vs-expectation observation — obsolescence is a design problem, not an age problem

Open research thread from the 2026-07-29 boss walk of the SDLC skills note (`nc-queue/2026-07-28-sdlc-skill-set-coverage-and-app-skill-pile.md` § 2 processed marks; walked by new-vp, nedlern session b6241858, in parallel with the boss's Mac-app agent thread — both converged). Status: **direction ruled, not yet a plan.** This issue is the durable home; the queue note archives per the standing pattern.

## The thesis (boss, near-verbatim)

Code doesn't rot. Time doesn't age code the way it ages animals; **bad designs, or design changes, rot out-of-date or insufficiently modular code.** Obsolete code is usually a product of bad design, not age — and patching is the mechanism by which bad design surfaces as "obsolete" code: the patch pile is the symptom, the misfit design is the disease.

Corollary reframe: removal is a cheap ruling once usage evidence exists; the scarce capability is determining **what is used frequently versus never**. Adding is easy; subtracting demands proving something is not needed now or in the future — non-existence, unfalsifiable — so every workable practice converts it into decidable questions: declare expectations, observe usage, reverse cheaply (git is the undo; the only irreversible loss is the knowledge of why a thing existed, which the record preserves).

## The four-way zero-usage taxonomy (governs investigation of any never-used mechanism)

(a) **lucky** — the guarded case hasn't occurred yet → keep, exercise synthetically; (b) **superseded** — other changes made it irrelevant → remove; (c) **flawed premise, now visible** → redesign, not remove; (d) **flawed premise, still invisible** — the dangerous one. Remedy (remove vs refactor vs design-cascade) is judgment applied to data; usage data only finds candidates.

**Armed-backstop decision rule:** frequency is not value. Never-fires AND fails synthetic exercise = dead. Never-fires but passes synthetic exercise = armed backstop — keep. (SQLite's practice: prove the guard still catches the deliberately injected defect.)

## The actionable candidate: usage-expectation tags + usage sensing (one set)

Declare an expected firing class at birth (HOT / NORMAL / RARE / EMERGENCY-ONLY; decorator or comment convention); grade declarations against reality with existing instruments. The tags change what sensing can prove: sampling verifies the HOT end fast (even during testing); synthetic exercise plus event coverage verifies the RARE end; nothing needs full coverage to be informative. Both mismatch directions are findings — **expected-rare-but-firing-often is an incident detector, not hygiene** (the system is living in its fallback: category (d) surfacing early).

Instruments, graded: coverage.py (branch coverage + per-test dynamic contexts; `sys.monitoring` core on Python ≥3.12) for existence questions at test time; event counters in production; py-spy sampling for hotspot questions only — **sampling is biased toward hot code and cannot distinguish cold from dead**; diff-cover ("changed lines must be exercised") as the cheap gatekeeper-side entry. Vetted precedent for the tags: FoundationDB `CODE_PROBE`. Mutation testing (mutmut) is the adjacent test-the-tests instrument, used selectively.

**Trigger:** NC's first real Python surface (the step-7 git-gatekeeper). A CDX-delegatable graded tool survey may run earlier on request.

## Observability by rule-kind (a "rule" spans prompts, scripts, skills, repeated processes, external mechanisms)

- **Hooks/checks/scripts:** stable per-clause IDs logged in the refusal or error message — the session JSONL then accumulates a usage ledger for free. The git-gatekeeper's still-undefined structured refusal schema is the natural first carrier (check IDs in the schema).
- **Skills:** countable from transcripts but NOT worth tracking — lazy-loaded, no accumulation, no meaningful cost (negative ruling, recorded so it is not re-proposed).
- **Prose rules (CLAUDE.md lines, doctrine):** effects surface indirectly; an LLM asked for root cause can point back at the otherwise-invisible instruction — cheap first probe; ablation only as confirmation.
- **External signals (GitHub Actions, human reviewers, user complaints):** monitored, not ignored — possibly the most important channel, the system's contact with reality; needs only a collector.
- **Production app code:** in the taxonomy, with the boss's aside that a coherent, actively maintained system's code should not rot the way guards and patches do. Standing design hope: with better modularity and more careful design, almost everything should be testable — hard-to-test is itself a design smell.

## Related landings from the same walk

- Design-change obsolescence sweep ("what does this change orphan?"): rider on GHI [Candidate skill: design-change — read-only evidence-grounded design with one recommendation and honest exits](https://github.com/nedschorus/nedschorus/issues/17).
- Patch-cycle tripwire at three with goal-level escalation and a visible cycle count: rider on GHI [Candidate skill: diagnose-failure — bounded causal debugging with a three-fix escalation stop](https://github.com/nedschorus/nedschorus/issues/21). Its across-time instrument is git churn — fix-commit frequency per file, a well-studied defect predictor (hotspot analysis, Tornhill / code-maat); hard-to-test and repeatedly-patched tend to be the same code.

## Reference (retained; its derived proposals were withdrawn in the walk)

Industry removal practice is observation plus cheap reversal, never proof: Kubernetes deprecation warnings with usage counters and a policy window; Rust's crater compiling the actual ecosystem; Linux staging removal on staleness facts; the scream-test/tombstone pattern with windows sized to trigger frequency; the admission-side inversion (decision 28 generalized: a mechanism records at birth the failure it exists to prevent, making later retirement mechanical). Rejected in the walk: `retire-mechanism` as a candidate skill (both proposal generations withdrawn).
