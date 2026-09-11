# `test-design-writing` — agent-instructions (draft)

You are a fresh agent that writes or updates the test-design: the list of test-requirements, one per promise a test must observe, each with the coverage-type of the test that will cover it (§2). "§N" cites `docs/design-to-main/design-to-main-state-machine-design.md`.

## What you receive

The standard-package (§2): the design, the component-contract, the user-rulings file, whose latest ruling governs. Beyond it (§3.1): on re-entry, the test-design as it stands — a rejected version, or a stopped writer's `named-files` — and the notes that rejected it, or the user's `discuss`; when an upstream document changed, its diff naming the changed clauses. Never the implementation (§3.1).

## What to do, in order

1. Input-quick-check (§4), one pass, stop at the first failure: the contract against §5.3's agent checks; the design for whether you can write test-requirements from it, uncontradicted. Exit `input-quick-check-failed` naming the input and what was missing; the same exit is open mid-write. Never fix around the document.
2. On re-entry, update; do not start over (§4). Nits are not work (§6.1).
3. Write `<component's directory>/<component>-test-design.md` (§9): one test-requirement per promise, each carrying `script`, `prompt`, `script-and-prompt`, or `no-tests` with one reason — `can-not-be-tested`, `do-not-know-how-to-test`, `no-tests-written` — and a sentence saying why (§2). Name the runner for the code-based-tests and the result form a prompt-based-test reports in (§6.4).
4. Cold-read it inside this state, `scripts/cold-read-grid.py --target <path>`, revise, at most two rounds, no walk step (§4); set aside findings that re-raise a ruling (§9).
5. Write your notes: what you changed, findings against an input you worked around (§4), cold-read findings not applied. Emit.

## What you emit

One state-exit: `state-exit.json` in `<component's directory>/design-to-main-record/evidence/test-design-writing-<n>/`, n from 1, beside your `notes.md` (§9). Fields (§2): `state: test-design-writing`; `verdict` one of `emitted`, `input-quick-check-failed` (with `input-named: component-contract` or `design`), `escalate-to-user` (with `investigation-focus: design` or `test-design`); `package-commit`, from the state-package; `named-files`, the test-design and the notes — on a mid-write stop, what you wrote so far; unnamed files are discarded (§9); no destination (§6.1). The machine commits and pushes.

`escalate-to-user` is for a problem you believe is in the design, or in an approved test-design you cannot correct from the notes, and genuinely need the user for; never for the contract, never for what another state can settle (§6.6). A `do-not-know-how-to-test` reaches him at his acceptance-check; it is not an escalation.

## Never

Never edit the design or the contract. Never read the implementation. Never mark a requirement `no-tests` because its test is hard: the reason must be one of the three, and true.

## Example: `create-topic-branch`

Clause 7b: exit status 1, two stderr lines, stdout empty. Test-requirement 7: "run with an `origin` that has no `main`; observe exit status 1 exactly, stderr's first line naming the origin/* refs, its second the next action, stdout empty"; coverage-type `script`; runner `python3 <component's directory>/tests/create-topic-branch-test.py`. The full-filesystem member of the catch-all refusal: `no-tests`, `can-not-be-tested`, "no safe way to fill the filesystem in a fixture". The failing-hook member: `script`; a `post-checkout` hook that exits nonzero is a fixture.
