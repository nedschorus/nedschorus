# Task brief for COPS — automated test-kind taxonomy (precursor to write-test-plan)

**From:** the boss, via the shared-conversation-discussion session (Claude runtime), 2026-07-29. Outbound brief; a relay agent delivers it. COPS cannot reply to the drafting session — deliver results as a file (see Deliverable) and the boss walks them.

**Requested by:** the boss, during the 2026-07-28 queue-note walk, as a named precursor to the `write-test-plan` candidate skill ([nedschorus#18](https://github.com/nedschorus/nedschorus/issues/18)).

## The named design question

What kinds of automated tests exist, and which of them are useful to a NedsChorus-scale project — so that a test plan can *select* kinds deliberately instead of defaulting to example-based functional tests?

Motivation: the draft `write-test-plan` contract (your file `cops-nedschorus-reproducible-engineering-skills-research-2026-07-22.md`, "Initial write-test-plan contract") says "choose the least expensive test level that still reaches the real mechanism," but offers no menu of kinds to choose from. The taxonomy is that menu. This satisfies your own stopping rule (decision 10): new research must answer a named design or evaluation question.

## Framing rulings (boss, 2026-07-29 — binding on this research)

1. **Evidence value first, cost as a bound.** "Our goal is not to minimize CPU cycles, storage, memory or tokens. Our goal is to design, write and maintain good code, that is easy to maintain, and not too slow, fat or token heavy." Rank kinds by what they prove about code quality and maintainability; cost disqualifies only when disproportionate. Do not rank by cheapness. The same correction applies to the contract's "least expensive test level" wording when #18 is built.
2. **Every kind must state its oracle and red condition in advance** — what is measured, and what reading means fail. A kind whose checks cannot go red proves nothing. (This generalizes the contract's "expected red witness" beyond functional tests.)
3. **Standard terminology only.** Map each kind to its accepted industry name(s); no coined terms. The boss's working names below must be translated, not adopted.

## Seed taxonomy (boss's examples, 2026-07-29, with candidate standard names — verify/correct)

- "XY test" (do x, get y) → example-based functional test
- read-a-missing-file-yields-error → negative / error-path test
- "X-not-Y" (do x, y must not happen) → invariant or postcondition check; the run-1000-times-no-leak case → leak / soak test
- exercised-line tests (this call should / should not reach this code) → coverage assertion (cf. FoundationDB `CODE_PROBE`, already graded in your survey)
- timing bounds (1000 runs takes >0.01s and <0.1s) → performance / benchmark test with thresholds
- resource usage (memory, system resources) → resource-consumption test

Known kinds to place additionally (from your own survey evidence where possible): property-based, fuzz, stress, concurrency/race, golden/snapshot, metamorphic (Pebble), fault-injection (SQLite), mutation testing (test-the-tests), regression, integration/end-to-end, smoke, conformance. Add kinds this list misses; the boss expects there are others.

## Required output, per kind

1. Standard name and common aliases.
2. What it proves — and what it cannot prove.
3. Oracle form and red condition (ruling 2 above).
4. Mature Python tooling, if any (pip-install grade preferred; name specific tools).
5. Cost profile: write / run / maintain, qualitatively.
6. When it earns its place in a NedsChorus-scale project (small Python system, one human + few agents, single writer to main) — including "rarely or never, because…" as a valid answer.
7. Evidence source per your hierarchy — implemented practice in your already-surveyed projects outranks advice; open new sources only where a kind lacks evidence in the existing survey.

Close with a short synthesis: the subset of kinds a NedsChorus test plan should routinely consider, the subset reserved for specific triggers, and the subset rejected at this scale — with one line of reasoning each.

## Scope guard

Not an encyclopedia and not organization-scale CI design. Reuse your existing survey (SQLite, FoundationDB, TigerBeetle, Pebble, PostgreSQL, Git, LLVM, Hypothesis-adjacent material) rather than re-opening it. Target length: the menu, not a book.

## Deliverable

One Markdown file in your session-artifacts convention (`cops/tasks/sessions/`), keyed to [nedschorus#18](https://github.com/nedschorus/nedschorus/issues/18), written for a zero-context reader. The boss will walk it; its accepted content feeds the `write-test-plan` skill when that skill is built.
