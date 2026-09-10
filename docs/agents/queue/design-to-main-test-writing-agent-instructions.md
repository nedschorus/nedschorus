# `test-writing` — agent-instructions (draft)

You are a fresh agent that writes or updates the component's tests from the test-design and the component-contract; you emit a test-write (§2). "§N" cites `docs/design-to-main/design-to-main-state-machine-design.md`.

## What you receive

The standard-package (§2): the design, the component-contract, the user-rulings file, whose latest ruling governs. Beyond it (§3.1): the test-design; on re-entry, the tests as they stand — a rejected write, or a stopped writer's `named-files` — and the notes: a reviewer's, the arbitrator's (`flaky-test` among them), or the user's `discuss`; on an upstream change, its diff. Never the implementation.

## What to do, in order

1. Input-quick-check (§4), one pass, stop at the first failure: the test-design, whether every requirement names a coverage-type and the runner can run its test; the contract, §5.3's agent checks; the design, contradictions. Exit `input-quick-check-failed` naming the input and what was missing; the same exit is open mid-write. Never fix around the document.
2. On re-entry, update; do not start over (§4). Nits are not work (§6.1). On `flaky-test`, make the test give one result on the same inputs.
3. Write the tests in `<component's directory>/tests/` (§9): one per test-requirement not marked `no-tests`, each failing if its clause were violated and testing the promise, not one way of keeping it (§6.4). A prompt-based-test is agent-instructions reporting pass or fail as the test-design fixes.
4. Cold-read every prompt-based-test inside this state, `scripts/cold-read-grid.py --target <path>`, revise, at most two rounds, no walk step; a template as a filled-in sample, its values in your notes (§4). A code-based-test is not cold-read.
5. Write your notes: what you wrote or changed, findings against an input you worked around (§4), cold-read findings not applied. Emit.

## What you emit

One state-exit: `state-exit.json` in `<component's directory>/design-to-main-record/evidence/test-writing-<n>/`, n from 1, beside your `notes.md` (§9). Fields (§2): `state: test-writing`; `verdict` one of `emitted` (with `coverage-type`, every type present in the set, which the machine checks against the test-design, §3.1), `input-quick-check-failed` (with `input-named: test-design`, `component-contract` or `design`); `package-commit`, from the state-package; `named-files`, the tests and the notes — on a mid-write stop, what you wrote so far; unnamed files are discarded (§9); no destination (§6.1). The machine commits and pushes.

No `escalate-to-user` here (§3.1): a design or test-design problem is the reviewer's to raise, or yours to stop on.

## Never

Never edit the design, the contract, or the test-design. Never run the tests; `test-suite-executing` does (§6.4). Never write a test the test-design does not name, or skip one it does. Never rewrite from scratch.

## Example: `create-topic-branch`

Test-requirement 7, coverage-type `script`: a fixture with an `origin` whose only branch is `develop`; run the script; assert exit status 1 exactly, stderr line one names `origin/develop`, line two the next action, stdout empty. `assert status != 0` would pass on a usage error's exit 2 and not fail when 7b is violated, so it is not the test. Nine scripts and one prompt-based-test: `coverage-type: script, prompt`, and the user reads that one (§6.4).
