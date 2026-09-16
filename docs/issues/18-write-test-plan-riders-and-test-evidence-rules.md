---
status: working material for nedschorus#18
as-of: 2026-09-16
---

# write-test-plan: the riders, and the rules on what counts as test evidence

The pair document of [nedschorus#18](https://github.com/nedschorus/nedschorus/issues/18), the candidate skill write-test-plan. The issue body keeps the summary, the disposition and the next action. This file carries the substance: the four riders drained into the issue on 2026-09-02, the worked example that triggered the build, and the user's rules on what evidence a change needs before it merges. Every section down to "Evidence of record" moved here verbatim from the issue body on 2026-09-16, when adding the newest ruling would have passed the body's 1000-word cap. The section on code that runs only against a stand-in is new.

## Riders, drained from the queue 2026-09-02

Source: `docs/issues/queue/18-write-test-plan-agent-native-riders.md`, from the agent-native testing walk of 2026-07-29/30. Queued for drain since then; drained here.

1. **Oracle-and-red-condition rule (the skill's core).** Every planned check, of any test kind, states its oracle (what is measured or compared) and its red condition (the reading that means fail) before implementation. A check whose red condition cannot occur proves nothing. This is the structural counter to implementation-mirroring tests (the user's ~95%-useless observation): a test copied from the implementation cannot state a failure it would detect.

2. **Reach-posit obligation.** Each planned test declares which design-significant paths it reaches; the declared set is diffed against measured execution (coverage.py dynamic contexts) — red on posited-but-unreached (false-green detector) or reached-but-forbidden. Escalation layers, per-claim rather than standing: trace assertions for ordering claims; scripted-debugger interior-state assertions for claims with no test-visible seam.

3. **Test-kind taxonomy (selection menu).** The skill selects kinds per claim across five axes (scope, oracle, input production, environment/workload, suite adequacy) rather than defaulting to example-based functional tests. Reference by pointer, not import: `/Users/el/Projects/nedlern-sonnet/cops/tasks/sessions/cops-nedschorus-automated-testing-kinds-survey-2026-07-29.md` (COPS, 2026-07-29; routine / trigger-reserved / reject buckets, 24-kind menu, 11 planner questions). Binding framing rulings: evidence value for good, maintainable code first — cost (CPU/tokens/storage) is a bound, not a ranking key; standard terminology only.

4. **Skip-expiry convention.** Every skipped or disabled test carries an owner and an expiry date from day one. Belongs in this skill's text or implement-with-evidence's, whichever first writes a test.

## Worked example for rider 1, and what it cost to learn twice

The 2026-08-31 defect is rider 1 in one incident. `find-deleted-path-across-backups.py` mounts an APFS snapshot and needs the mount point. The code assumed `/tmp`. The fixture, written by the same author in the same sitting, also said `/tmp`. The test asserted the code's answer matched the fixture's, matched, and passed. Nothing in that loop asked the operating system; `mount | grep` would have answered it without privilege and was never run. The test was green, and green read as checked.

Rider 1 predicted this five weeks before it happened — "a test copied from the implementation cannot state a failure it would detect" — and the rule was sitting undrained in a queue file while the defect shipped.

A research pass on 2026-09-02 examined eight techniques against this defect: code-clone detection, mutation testing, checked coverage, property-based testing, metamorphic testing, golden/snapshot/approval testing, VCR-style record-and-replay, and consumer-driven contract testing. One would have caught it — running the real query independently and comparing against the program's answer. **Mutation testing would have praised the bad test**, because killing a mutant proves a test is sensitive to change, not that its baseline is true; snapshot testing preserves a decision without establishing it was right. The report lands with the build as `docs/research/authoring-rule-wording-and-fixture-independence-research.md`; it is not on main yet.

Two rules the 2026-09-02 walk adopted, to be carried into the skill as concrete instances of riders 1 and 2 rather than as separate rules:

- When adding or changing a test fixture that represents the output of an external system, run the real command first and generate the fixture from what it printed. If the command is unsafe to run directly, capture it in a sandbox and say so in the capture note — the fixture then proves what the sandbox does, not what the real system does. Never type, copy or infer those values from the code under test. Record the capture command and the machine it ran on beside the fixture. Without that capture, the test is not finished.
- Do not merge a code path that neither the author nor a reviewer can execute. If nobody can run it, get an environment that can, or leave the path out.

A third rule — at least one test per script that asks the real system on every run, rather than replaying a recording — was drafted four times and never reached wording the user accepted. It is the live-check half of rider 1 and is unresolved; the skill build is where it gets settled. The project's existing idiom for its absent-system case is the visible SKIP line, as in `scripts/clean-worktrees-test.py`.

## 2026-09-16: code that runs only against a stand-in

The second 2026-09-02 rule above covers a code path that nobody can execute at all. It left open a neighbouring case: a path that can only ever be exercised against a stand-in, never the real system, because triggering the real thing means crashing a machine or hitting a rate limit deliberately. That case waited as an open question from 2026-09-02 until the MD-skills seat's open-items walk put it to the user on 2026-09-16 (item 5; the minutes are Mac-local at that seat, `docs/walk/md-skills-seat-open-items-rulings-minutes.md`, a gitignored directory).

His ruling, in his words:

> We test as best we can, then we ship. If production has a problem, we file the issue and fix.

Asked the same day how that fits the 2026-09-02 rule, he confirmed both stand, each for its own case:

- **Code that nobody can run in any form does not merge.** Get an environment that runs it, or leave the path out. (2026-09-02)
- **Code that runs, but only against a stand-in, ships on that evidence.** If production then shows a problem, it becomes a GitHub issue and gets fixed. (2026-09-16)

Running a path against a stand-in counts as executing it. A stand-in is whatever takes the real system's place for the run: a sandbox, a fake service, or a recorded response. It must still meet rider 1 and the fixture rule above: a stand-in whose answers were typed, copied or inferred from the code under test proves nothing, because it agrees with the code by construction. The stricter reading, that the 2026-09-16 ruling replaces the 2026-09-02 rule and lets code no one has run ship whenever testing it is hard, was put to him and declined.

This fits the 2026-09-02 fixture rule rather than loosening it. A fixture captured from a sandbox must still say so, because it proves what the sandbox does, not what the real system does. The new ruling says that evidence is enough to ship; it does not let anyone present it as evidence about the real system.

## Evidence of record

- Six-agent source read: `nc-queue/archived/2026-07-22-candidate-skill-source-evidence.md` (this skill's section)
- cops delta packet: `nc-queue/archived/2026-07-23-cops-candidate-skill-delta-packet.md` (this skill's section)
- Shortlist origin: `docs/issues/9-neds-notes.md` § Working skill shortlist
- The 2026-09-02 walk that triggered the build: `docs/walk/prevention-rules-from-the-2026-08-31-fix-rounds-minutes.md` (lands with the build)
- The defects: https://github.com/nedschorus/nedschorus/pull/222 and https://github.com/nedschorus/nedschorus/pull/223
