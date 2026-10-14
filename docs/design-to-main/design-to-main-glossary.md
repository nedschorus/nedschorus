# design-to-main glossary

Terms that belong to the design-to-main workflow alone, for agents working on the files in this directory. Terms used beyond design-to-main, such as design-contract and test-design, are in the project glossary, `docs/nedschorus-wiki/nedschorus-glossary.md`, and are used here as defined there. Only hyphenated phrases are defined; no common software-engineering word is redefined.

The state names of the machine are in the design, `docs/design-to-main/design-to-main-state-machine-design.md`, §3.1, and are not repeated here.

- **acceptance-check** — a check of one finished artifact against its acceptance criteria, which passes or fails, made by a program, an agent or the user.
- **can-not-be-tested** — a `no-tests` reason: no machine or safe way to exercise the requirement here.
- **code-based-test**, **prompt-based-test**, **CPC-based-test**, **user-based-test** — a test named in prose by what it is based on: coverage-type `script`, `prompt` (agent-instructions run by a single-purpose agent that reports pass or fail), `script-and-prompt`, and a clause's by-hand demonstration.
- **component-consumer** — anything that invokes a component or reads what it leaves. A script's component-consumers are whoever runs it and whatever reads the files, branches or output it leaves behind.
- **component-consumer-receives** — the design-contract group holding the postconditions on what a component-consumer gets back, per case, and how each outcome is observed.
- **component-consumer-supplies** — the design-contract group holding the preconditions on what a component-consumer passes in, each with what makes it invalid and what the component does then.
- **contract-revision** — a re-write of the design-contract in `contract-revising` after a rejection or a failed check against it, once the design is approved.
- **could-not-run** — the test suite's third outcome, beside pass and fail: the runner or a launched test agent produced no result at all.
- **coverage-type** — the word on an implementation or a test saying what kind of thing it is: `script`, `prompt` (agent-instructions; for a test, a prompt-based-test), or `script-and-prompt`. A test-requirement in the test-design carries the same field for the test that will cover it and may instead be `no-tests`.
- **do-not-know-how-to-test** — a `no-tests` reason: an open question, which reaches the user.
- **escalate-to-user** — the state-exit an agent takes for a problem it believes is in the design or the test-design, when it needs the user; it opens an investigation.
- **flaky-test** — the arbitrator's verdict that a test gives different results on the same inputs while the implementation does not; routes to `test-writing`. The standard term.
- **gate-rejection** — the gate's review finding what the machine's reviewers missed: a code defect with a failure scenario, or the test suite failing on current `main`. Never a wording finding. Opens an investigation with the user.
- **gatekeeper-refusal** — the main-gatekeeper program declining a request, naming its error and its fix.
- **implementation-work-stream** — the states that carry the implementation from the approved design to the test suite: `implementation-writing` and `implementation-reviewing`.
- **implementation-write** — one finished writing of the implementation in `implementation-writing`; the machine counts them per design version.
- **initiate-design-to-main** — the skill the user invokes to start a run, naming the component, and the run's first state.
- **initiator** — the fresh agent `design-writing` launches to hold its side of the design conversation with the user, until the code and the tests both exist.
- **input-quick-check** — the check at the start of every writing state that what it received is enough to do its task: the writer reads its inputs once against an enumerated list and stops if it cannot proceed. A quick check, not a validation.
- **input-quick-check-failed** — the state-exit a writing state takes when its input-quick-check fails, naming the input and what was missing. Not a write; counts against the input it names.
- **investigate-workflow** — the user's dialog with the initiator while it lives, or with the arbitrator once the code and the tests exist, that pauses a run, and the skill that opens one. Exits: stop, submit-to-PR-gate, resume.
- **investigation-focus** — the field on an investigation report naming which document is under suspicion: `design`, `contract`, `test-design`, or `unknown` when none is.
- **no-tests** — the coverage-type of a test-requirement that has no test, always with one of three reasons and a sentence saying why: can-not-be-tested, do-not-know-how-to-test, no-tests-written. A value of the test-design only; an implementation is never `no-tests`.
- **no-tests-written** — a `no-tests` reason: a test could be written and was not, the sentence saying whether the code is trivial or the fixture, tool or environment does not exist yet.
- **per-run-text** — what one agent writes during a run for another agent: a reviewer's notes, an input-quick-check-failed report, a contract-revision. The user does not review it, except a contract-revision at `contract-acceptance-by-user`.
- **ready-for-test-suite** — the position a work-stream holds at when its last reviewing state has advanced and the other work-stream has not yet; recorded per work-stream in the run-state file.
- **redesign-ordered-by-user-after-contract-failed-twice** — the user's verdict at `contract-acceptance-by-user`, after the design-contract has failed review twice, that the trouble lies in the design itself: it opens a redesign through an investigation, counted against redesigns.
- **refusal-clause-pair** — how a refusal is written in a design-contract: one `world-requires` clause and one `component-consumer-receives` clause sharing a number, with suffixes `a` and `b`.
- **standard-package** — the files every agent after the design receives in every state-package: the design, the design-contract, the component's user-rulings file, and on a re-entry the notes or failed-check report that caused it and the version being corrected.
- **standing-agent-instructions** — agent-instructions that will be followed again and again: a skill, the instructions a state launches its agent with, an implementation or a test that is agent-instructions.
- **state-exit** — the one structured record a state's work emits and the machine routes on: a verdict, a destination, and the commit of the state-package it was built from.
- **state-package** — the set of files the machine assembles for one launched agent and tells it to read; the agent works in a worktree of the topic branch holding the state-package and what it needs to run.
- **submit-to-PR-gate** — the state that hands the accepted implementation and tests to the gate, and the exit by which the user overrides an investigation to do the same.
- **test-design-correction** — a re-write of the test-design in `test-design-writing` after a rejection or a failed check against it, once the test-design is approved.
- **test-work-stream** — the states that carry the test-design and the tests from the approved design to the test suite: `test-design-writing`, `test-design-reviewing`, `test-writing`, `test-reviewing`.
- **test-write** — one finished writing of the tests in `test-writing`; the machine counts them like implementation-writes.
- **tests-begun** — the per-design-version flag set when the first implementation-write is accepted, after which the test-work-stream runs.
- **world-changes** — the design-contract group holding the postconditions on what is different in the world after a run, per case.
- **world-requires** — the design-contract group holding the preconditions on what must already be true in the world, each naming its refusal or declared `unchecked`. The world is everything outside the component and its component-consumers that the component does not itself create: the repository and its settings, the file system, GitHub, the network, the tools the component runs.
- **world-unchanged** — the design-contract group holding the invariant: what in the world is the same after a run, and which runs it covers.
- **zero-all-run-counters-including-redesigns** — a user-ruling, given in any dialog with him, that sets every counter to zero, the redesigns counter included, and is recorded in the user-rulings file.
