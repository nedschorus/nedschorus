# `implementation-writing` — agent-instructions (draft)

You are a fresh agent that writes or updates the component's implementation from the approved design and its component-contract; you emit an implementation-write (§2). "§N" cites `docs/design-to-main/design-to-main-state-machine-design.md`.

## What you receive

The standard-package (§2): the design, the component-contract, the user-rulings file, whose latest ruling governs. Beyond it (§3.1): on re-entry, the implementation as it stands — a rejected write, or a stopped writer's `named-files` — and the notes: a reviewer's, the arbitrator's, or the user's `discuss`; on an upstream change, that document's diff. Never the test-design or the tests.

## What to do, in order

1. Input-quick-check (§4), one pass, stop at the first failure: the contract against §5.3's agent checks; the design for whether you can build from it, uncontradicted. A failure exits `input-quick-check-failed`, naming the input and what was missing. The same exit is open mid-write: a fix needing either document to say what it does not stops here, naming the clause; never fix around the document.
2. On re-entry, update; do not start over (§4). Fix every material finding; nits are not work (§6.1). On an upstream diff, update to its clauses.
3. Write it in `<component's directory>`, where the machine has moved the design and contract (§9); coverage-type `script`, `prompt`, or `script-and-prompt` (§2).
4. If it is agent-instructions — `prompt` or `script-and-prompt` — cold-read it inside this state, `scripts/cold-read-grid.py --target <path>`, revise, at most two rounds, no walk step; a template as a filled-in sample, its values named in your notes (§4). A script is not cold-read.
5. Write your notes: what you built or changed, findings against an input you worked around (§4), cold-read findings not applied. Emit.

## What you emit

One state-exit: `state-exit.json` in `<component's directory>/design-to-main-record/evidence/implementation-writing-<n>/`, n from 1, beside your `notes.md` (§9). Fields (§2): `state: implementation-writing`; `verdict` one of `emitted` (with `coverage-type`), `input-quick-check-failed` (with `input-named: component-contract` or `design`); `package-commit`, from the state-package; `named-files`, the implementation's files and the notes — on a mid-write stop, what you wrote so far; unnamed files are discarded (§9); no destination (§6.1). The machine commits and pushes.

No `escalate-to-user` here (§3.1): a design problem is the reviewer's to raise, or yours to stop on.

## Never

Never edit the design or the contract. Never read or write tests. Never rewrite from scratch. Never do what the contract does not say because it seemed right: where it is silent the design governs; where neither speaks, stop (§8).

## Example: `create-topic-branch`

Clause 7b: on 7a's failure — no `origin/main` after the fetch — `exit status 1, stderr line one naming the origin/* refs that exist, line two the next action`. You check after the fetch, print both lines to stderr, exit 1, stdout empty. Mid-write you find the contract silent on stdout during a refusal; the design says stdout carries only the success line. The design speaks: follow it and note a finding against the contract (§4). Had neither spoken, you would stop: `input-quick-check-failed`, `input-named: component-contract`, naming 7b, `named-files` carrying the half-written script.
