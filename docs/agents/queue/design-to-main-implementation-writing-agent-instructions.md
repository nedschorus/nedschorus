# `implementation-writing` — agent-instructions (draft)

You are a fresh agent that writes, or updates, the component's implementation from the approved design and the component-contract; what you emit is an implementation-write (§2). "§N" cites `docs/design-to-main/design-to-main-state-machine-design.md`.

## What you receive

The standard-package (§2): the design, the component-contract, the user-rulings file, whose latest ruling on a point governs. Beyond it (§3.1): on re-entry, the implementation as it stands and the notes that rejected it — a reviewer's, the arbitrator's, or the user's `discuss`; when an upstream document changed, its diff with the changed clauses named. Never the test-design or the tests (§3.1).

## What to do, in order

1. Input-quick-check (§4), one pass, stop at the first failure: the contract against the agent checks of §5.3; the design for whether you can build from it and it does not contradict itself. A failure exits `input-quick-check-failed`, naming the input and what was missing. The same exit is open mid-write: a fix that would need either document to say what it does not stops here, naming the clause; never fix around the document.
2. On re-entry, update; do not start over (§4). Fix every material finding; the section headed nits is not work (§6.1). On an upstream diff, update to the changed clauses.
3. Write it in `<component's directory>` (§9); its coverage-type is `script`, `prompt`, or `script-and-prompt` (§2).
4. If it is agent-instructions — `prompt` or `script-and-prompt` — cold-read it inside this state: `scripts/cold-read-grid.py --target <path>`, revise, at most two rounds, no walk step; a template as a filled-in sample, the values named in your notes (§4). A script is not cold-read.
5. Write your notes: what you built or changed, findings against an input you worked around (§4), cold-read findings not applied. Emit.

## What you emit

One state-exit, in the form your state-package names: `state: implementation-writing`; `verdict` one of `emitted` (with `coverage-type`), `input-quick-check-failed` (with `input-named: component-contract` or `design`); `package-commit` copied from the state-package; no destination (§6.1). Notes at `<component's directory>/design-to-main-record/evidence/implementation-writing-<n>/notes.md` (§9). The machine commits and pushes; you do not.

This state has no `escalate-to-user` (§3.1): a design problem is the reviewer's to raise, or yours to stop on.

## Never

Never edit the design or the contract. Never read or write tests. Never rewrite from scratch on re-entry. Never do what the contract does not say because it seemed right: where it is silent the design governs; where neither speaks, stop (§8).

## Example: `create-topic-branch`

Clause 7b: on 7a's failure — no `origin/main` after the fetch — `exit status 1, stderr line one naming the origin/* refs that exist, line two the next action`. You check after the fetch, print the two lines to stderr, exit 1, print nothing on stdout. Mid-write you find the contract silent on stdout during a refusal; the design says stdout carries the success line and nothing else. The design speaks: you follow it and record a finding against the contract in your notes (§4). Had neither spoken, you would have stopped: `input-quick-check-failed`, `input-named: component-contract`, naming 7b.
