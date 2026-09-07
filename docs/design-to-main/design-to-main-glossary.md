# design-to-main glossary

Terms that belong to the design-to-main workflow alone, for agents working on the files in this directory. Fleet-wide terms — `agent-instructions`, `fresh agent`, `user ruling` and `user-ruled`, `GHI-MD`, `PR process`, `cold-read run` — are in the fleet glossary, `docs/wiki/nedschorus-glossary.md`, and are used here as defined there. Only hyphenated phrases are defined; no common software-engineering word is redefined. Every phrase was collision-checked against `docs/`, `scripts/` and `.claude/` on 2026-09-06, the day the user ruled them.

The state names of the machine are in the design, `docs/design-to-main/design-to-main-state-machine-design.md`, §3.1, and are not repeated here.

- **acceptance-check** — a pass-or-fail check of one artifact against its acceptance criteria. Three tiers, by who performs it: by program, a script the machine runs; by agent, a fresh agent reading the artifact; by user. A reviewing state's sub-states are its artifact's acceptance-checks in that order, named `<artifact>-acceptance-by-program`, `-by-agent`, `-by-user`. An acceptance-check examines the previous state's output; it is not an input-quick-check.
- **can-not-be-tested** — a `no-tests` reason: no machine or safe way to exercise the requirement here.
- **component-consumer** — anything that invokes a component or reads what it leaves. A script's component-consumers are whoever runs it and whatever reads the files, branches or output it leaves behind. Replaces "caller".
- **component-consumer-receives** — the component-contract group holding the postconditions on what a component-consumer gets back, per case, and how each outcome is observed.
- **component-consumer-supplies** — the component-contract group holding the preconditions on what a component-consumer passes in, each with what makes it invalid.
- **component-contract** — the file beside a design listing what the component promises its component-consumers, one testable clause per observable, plus the details a tester needs to observe those promises and nothing else. Written by the design's author in the design conversation; revised after the design's approval only by a fresh agent from a reviewer's notes.
- **coverage-type** — the word on an implementation or a test saying what kind of thing it is: `script`, `prompt` (agent-instructions; for a test, a test run by a single-purpose agent), or `script-and-prompt`. A test may also be `no-tests`.
- **do-not-know-how-to-test** — a `no-tests` reason: an open question, which reaches the user.
- **gate-rejection** — the gate's review finding what the machine's reviewers missed: a code defect with a failure scenario, or the test suite red on current `main`. Never a wording finding. Opens an investigation with the user.
- **gatekeeper-refusal** — the main-gatekeeper program declining a request it cannot apply, naming its error and its fix; resubmission is safe. Handled by the machine, not the user.
- **implementation-write** — one finished writing of the implementation by a fresh agent in `implementation-writing`. What the machine counts, up to three per design version. Replaces "build" as a noun.
- **initiate-design-to-main** — the skill the user invokes to start a run, and the run's first state.
- **input-quick-check** — the check at the start of every writing state that what it received is enough to do its task: the writer reads its inputs once against an enumerated list and stops if it cannot proceed. A quick check, not a validation.
- **input-quick-check-failed** — the exit a writing state takes when its input-quick-check fails, naming the input and what was missing. Not a write; charged to the input it was against. Replaces "could-not".
- **investigate-workflow** — the user's dialog with the arbitrator that pauses a run, and the skill that opens one. Exits: stop, submit-to-PR-gate, resume.
- **no-tests** — the coverage-type of a test-requirement that has no test, always with one of three reasons and a sentence saying why: can-not-be-tested, do-not-know-how-to-test, no-tests-written. A test-side value only; an implementation is never `no-tests`. Replaces `excluded` and its four reasons (user-ruled 2026-09-06).
- **no-tests-written** — a `no-tests` reason: a test could be written and was not, the sentence saying whether the code is trivial or the fixture, tool or environment does not exist yet.
- **per-run-text** — what one agent writes during a run for another agent: a reviewer's notes, an input-quick-check-failed report, a revised component-contract. The user does not review it.
- **standing-agent-instructions** — agent-instructions any agent will follow: a skill, or the instructions a state launches its agent with. Final prose; the user reviews them after their cold read.
- **submit-to-PR-gate** — the state that hands the accepted implementation and tests to the gate, and the exit by which the user overrides an investigation to do the same.
- **test-write** — one finished writing of the tests by a fresh agent in `test-writing`. Counted like an implementation-write.
