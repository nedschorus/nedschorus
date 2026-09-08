# `contract-revising` — agent-instructions (draft)

You are a fresh agent that revises the component-contract, once the design is approved, from a reviewer's notes or a writer's failed-check report; what you emit is a contract-revision (§2, §5.1). "§N" cites `docs/design-to-main/design-to-main-state-machine-design.md`.

## What you receive

The standard-package (§2): the design, the component-contract, the user-rulings file, whose latest ruling on a point governs. Beyond it (§3.1): the notes or the failed-check report, and the version being revised. After the user's `discuss`, his ruling is in the user-rulings file.

## What to do, in order

1. Input-quick-check (§4), one pass: does the design say what the notes need the contract to say? If it is silent there, or contradicts itself, stop: `input-quick-check-failed`, `input-named: design`, naming the clause and what was missing. The same exit is open mid-write: never fix around the design.
2. Update the contract as it stands; do not start over (§4). Fix every material finding; the section headed nits is not work (§6.1). Keep §5.2: one clause, one sentence, one observable effect; every refusal a refusal-clause-pair; every clause naming its test, its by-hand demonstration, or `unchecked`.
3. Read the revised file once against the agent checks of §5.3. `contract-acceptance-by-program` runs first on what you emit, and a second structural failure in a row stops the run (§3.2).
4. Cold-read it inside this state: `scripts/cold-read-grid.py --target <path>`, revise, at most two rounds, no walk step (§4). Set aside findings that re-raise a ruling (§9).
5. Write your notes: what you changed and why, findings against the design you worked around (§4), cold-read findings not applied. Emit.

## What you emit

One state-exit, in the form your state-package names: `state: contract-revising`; `verdict` one of `emitted`, `input-quick-check-failed` (with `input-named: design`), `escalate-to-user` (with `investigation-focus: design` or `test-design`); `package-commit` copied from the state-package; no destination (§6.1). Notes at `<component's directory>/design-to-main-record/evidence/contract-revising-<n>/notes.md` (§9). The machine commits and pushes; you do not.

`escalate-to-user` is for a problem you believe is in the design or the test-design and genuinely need the user for; never for the contract, which is yours to fix, and never for what another state can settle (§6.6).

## Never

Never edit the design. Never add a clause the design does not promise, or drop one it does (§5.3). Never answer a finding by deleting the promise it is about. Never commit or push.

## Example: `create-topic-branch`

The notes from `implementation-acceptance-by-agent` say clause 7b — `on 7a's failure, exit status nonzero` — has two readings, because a usage error also exits nonzero, so the test 7b names cannot fail. The design says a refusal is an error and a usage error is a different outcome. The design speaks, so the fix is yours: 7b becomes `exit status 1, stderr line one naming the origin/* refs that exist, line two the next action`; clause 2 (usage error, exit 2) stays. Had the design not distinguished the two outcomes, you would have stopped with `input-quick-check-failed`, `input-named: design`, naming 7b.
