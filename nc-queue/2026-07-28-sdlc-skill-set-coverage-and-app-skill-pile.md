# SDLC skill-set coverage check, and the app-skill pile question

Boss-requested (2026-07-28, shared-conversation-discussion session). Sources: the cops research record `nedlern-sonnet/cops/tasks/sessions/cops-nedschorus-reproducible-engineering-skills-research-2026-07-22.md` (read in full); the boss's 2026-07-05 claude.ai conversation proposing ten test-infrastructure skills from CockroachDB/LLVM/Hypothesis; the live repo state (boot-set rule of 2026-07-24, candidate GHIs #15–#23, founding plan step 7).

## 1. What is already settled (no action; recorded so the gaps below are read against it)

The "full set of SDLC skills, when and how" mostly exists and is ratified:

- **The list**: five founding skills (d-review, walk-me-through, handoff, ghi-write, md-write) + nine candidates, one GHI each ([#15](https://github.com/nedschorus/nedschorus/issues/15)–[#23](https://github.com/nedschorus/nedschorus/issues/23)): define-work, plan-rewrite-slice, design-change, write-test-plan, attack-artifact (packaging vs d-review unresolved), implement-with-evidence, diagnose-failure, review-change, eval-agent-change.
- **The when**: the routing table in the cops record ("missing decision → candidate") — a skill is pulled when a real task exposes the decision it encodes, never built ahead (boot-set rule, resolved 2026-07-24). First expected pull: write-test-plan ([#18](https://github.com/nedschorus/nedschorus/issues/18)) at the step-7 git-gatekeeper task.
- **The how**: one SKILL.md per decision, manual evaluation per the frozen protocol in the cops record (two positives on different branches, one near-miss negative, one clean control, one withheld case; no-skill baseline first; no framework).

## 2. Gap — nothing owns removal/retirement

The cops record's own objective names "obsolete guards, compatibility paths, and incident fixes accumulating until further development becomes difficult" as a NedLern failure class; its survey question 11 asks every project how mechanisms are retired; its cross-project finding 6 says mature processes have explicit ways to undo work. **No candidate skill owns deletion/retirement.** The nine candidates are all forward-motion decisions. Proposed disposition: add a named-deferred candidate (working name `retire-mechanism`) to the candidate set — same status as release-transition and learn-from-failure: on the map, gated on a real task (the first time an obsolete guard, compat path, or dead skill needs removing). Costs one GHI now; prevents the map from silently claiming coverage it lacks.

> **processed 2026-07-29 → REJECTED as retire-mechanism; REVISED into three potential improvements** (walk item 2, new-vp session b6241858; discussed in parallel with the Mac-app agent's thread, which converged; boss-directed write-up). Governing frame — the four-way zero-usage taxonomy: (a) lucky, the guarded case has not occurred yet → keep and exercise synthetically; (b) superseded by other changes → remove; (c) flawed premise now visible → redesign, not remove; (d) flawed premise still invisible — the dangerous one. Remedy (remove vs refactor vs design-cascade) is judgment applied to data; usage data only finds candidates.
>
> **Potential improvement 1 — usage-expectation tags + usage sensing, one set (stronger together, especially where full test coverage is impractical).** New mechanisms and code paths declare an expected firing class at birth (HOT / NORMAL / RARE / EMERGENCY-ONLY; decorator or comment convention). Existing instruments grade the declaration against reality: coverage.py at test time (branch coverage + per-test dynamic contexts; `sys.monitoring` core on Python ≥3.12), event counters and py-spy sampling in production. Instrument honesty: sampling is biased toward hot code and cannot distinguish cold from dead — existence questions need event/coverage data; sampling answers only how hot. Expectations differ by class and phase: EMERGENCY-ONLY should be synthetically exercised in tests yet ~never fire in production; HOT should show in both — so tag-vs-reality mismatch can surface **already in testing**. Both mismatch directions are findings; expected-rare-but-firing-often is an incident detector, not hygiene. Vetted precedent: FoundationDB `CODE_PROBE`. diff-cover ("changed lines must be exercised") is the cheap gatekeeper-side entry point. Landing: deferred evaluation task, triggered by NC's first real Python surface (the step-7 git-gatekeeper); a CDX-delegatable graded tool survey may run earlier on request.
>
> **Potential improvement 2 — design-change obsolescence sweep.** A design change is the one moment the superseded category is cheaply identifiable: the design-change skill's contract gains the obligation "what does this change orphan?" Landing: rider on the design-change candidate GHI.
>
> **Potential improvement 3 — patch-cycle tripwire at three, escalating to design AND goal.** Three review-fail-patch cycles on one change → stop patching; mandatory reconsideration of the design or of the goal itself (edge-case explosion; intractable or NP-complete as specified). The threshold exists twice in the ratified record (decision 23; diagnose-failure's three-failed-fixes rule); the additions are the goal-level escalation and making the cycle count visible in the attempt record so the tripwire can trip. Landing: rider on the diagnose-failure candidate GHI.
>
> Status: potential improvements — direction ruled, not yet a plan. Boss's standing design hope, recorded: with better modularity and more careful design, almost everything should be testable; hard-to-test is itself a design smell, feeding improvement 3.

## 3. Gap — test-suite operations have no named-deferred class

The nine candidates are decision skills. The boss's 2026-07-05 ten (property-harness, stateful-model-tester, datadriven-migrator, golden-check-writer, repro-reducer, deflaker, skip-warden, suite-tiering, test-diff-reviewer, test-ghostwriter) are mostly **suite operations** — what to do when a real suite rots, flakes, or slows. Overlaps: test-diff-reviewer ≈ review-change's test half; test-ghostwriter is subsumed by write-test-plan + implement-with-evidence. The rest (deflaker, repro-reducer, suite-tiering, skip-warden, golden/datadriven/property harness writers) have no owner and no deferred entry. Proposed disposition: record one named-deferred class (working name `suite-health`) rather than seven skills; trigger: the first sustained suite whose signal degrades. Skip-warden's expiry-on-skips idea also feeds §2's retirement candidate.

## 4. Note — the anti-tautology device already exists in the write-test-plan contract

The boss's standing complaint: agent-written tests are ~95% useless because agents write tests from the implementation, producing tautologies. The write-test-plan contract's mechanical check — **every planned check states its expected red witness** (the exact reason it fails before the fix or against a deliberately bad implementation) — is the structural counter: a tautological test cannot state one. Two riders for the walk:

- Enforcement idea: hand test-writing (the implement-with-evidence half) to a zero-context one-shot agent given the contract/design and error catalog but **not** the implementation. An agent that never saw the implementation cannot mirror it. This uses the existing kleenex instrument; no new machinery.
- The cops dogfood run of the contract against the git-gatekeeper spec returned `needs-design-clarification` with nine concrete missing interface bindings rather than inventing tests — evidence the contract refuses correctly. Those nine bindings are on the critical path of the step-7 task.

## 5. Question for the boss — the app-skill pile and routing dilution

The Claude Code app sessions currently carry ~60+ skills from installed marketplace plugins (engineering, design, productivity, anthropic-skills, cowork-plugin-management bundles from claude-plugins-official) plus app built-ins. None are NC skills; the NC repo has zero built skills yet. The skill-creation deep-dive (§5, archived 2026-07-22) established that every added skill dilutes every other skill's claim on routing attention, and the description budget shortens under pressure. When NC's own five founding skills boot, they will compete with that pile for triggering. Proposed ruling candidate: NC project sessions run lean — disable or not-install non-essential plugins in the NC project scope (keep what is actually used: e.g. code-review, skill-creator as reference), so NC skill routing is measured against a quiet field, not a noisy one. Needs a boss decision on which app skills, if any, earn a place in NC sessions.

## 6. Proposed dispositions (for the walk)

1. §2 retire-mechanism: one new candidate GHI, named-deferred.
   *processed 2026-07-29 → rejected as proposed; revised into three potential improvements — see the §2 processed mark.*
2. §3 suite-health: one line in the candidate set or founding plan naming the deferred class; no GHI until triggered.
3. §4 riders: attach to [#18](https://github.com/nedschorus/nedschorus/issues/18) (red-witness enforcement note, kleenex test-writer idea) and to the step-7 task record (nine missing bindings).
4. §5: boss ruling on app-skill policy for NC sessions; if ruled, it lands as a line in the founding plan's environment step (step 6).

---

## Walk order (ledger, opened 2026-07-28, new-vp session b6241858)

This walk also covers pair [nedschorus#32](https://github.com/nedschorus/nedschorus/issues/32)'s three open questions; those resolutions are additionally marked in `docs/issues/32-preservation-and-placement.md` as they land. Recovery anchor after any interruption: the first unmarked item below.

1. Purpose and map of the walk
2. §2 — retire-mechanism candidate (note §6.1)
3. §3 — suite-health named-deferred class (note §6.2)
4. §4 — riders to #18 and the step-7 record (note §6.3)
5. §5 — app-skill policy for NC sessions (note §6.4)
6. Pair #32 Q1 — memory placement
7. Pair #32 Q2 — log extracts at boundaries (owned by the bridge specification; only the placement-consumer stance is decidable here)
8. Pair #32 Q3 — shared-store writes by temporary workers
