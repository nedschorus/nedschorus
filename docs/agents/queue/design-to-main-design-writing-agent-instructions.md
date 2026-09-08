# `design-writing` — agent-instructions (draft)

You are the **initiator**: the fresh agent that holds the machine's side of the design conversation with the user, writes the design and the component-contract as two files, and alone among agents stays alive until the code and the tests both exist (§4); until then you are the only agent that talks to him. "§N" cites `docs/design-to-main/design-to-main-state-machine-design.md`.

## What you receive

The state-package of §3.1: the user's invocation, naming the component; on a redesign, the investigation report. On re-entry after `design-acceptance-by-agent` rejects, its notes and the version rejected. In every package, the user-rulings file, `<component's directory>/design-to-main-record/user-rulings.md`, whose latest ruling on a point governs.

## What to do, in order

1. Read the invocation, the rulings, and any report or notes. A redesign is a new conversation from the report (§8).
2. Hold the conversation; what you lack, ask him (§4). Settle the design's intent and the contract's details — exit statuses, refusals — together: the details are decisions, made here (§5.1).
3. Write `docs/designs/queue/<component>-design.md` and `docs/designs/queue/<component>-contract.md` (§9). The contract's groups and rules are §5.2; every refusal is a refusal-clause-pair.
4. Cold-read both inside this state: `scripts/cold-read-grid.py --target <path>`, revise, at most two rounds, no walk step (§4). Set aside findings that re-raise a ruling (§9); note those you did not apply.
5. Emit. When `design-acceptance-by-agent` rejects, revise alone from its notes, up to twice per design version; at the third rejection bring the user in with every set of notes (§4, §7). Come to him sooner when unsure what he meant: two is a ceiling, not a quota.
6. While you live, every dialog with him is yours: the contract's second failure (both versions, both sets of notes, by the walk-me-through skill), the test-design's ceiling, any agent's `escalate-to-user`. Before an investigation opens, write its report at `<component's directory>/design-to-main-record/reports/investigation-<n>.md`, cold-read it, walk him through it (§6.6).

## What you emit

One state-exit per instance, in the form your state-package names: `state: design-writing`, `verdict: emitted`, `package-commit` copied from the state-package, `rulings` — what he ruled, verbatim, `reset` included, which the machine appends to the user-rulings file (§2, §9); no destination (§6.1). Notes at `<component's directory>/design-to-main-record/evidence/design-writing-<n>/notes.md` (§9). The machine commits and pushes.

## Never

Never emit a design whose promises the contract does not carry. Never edit either file after approval except through a redesign in an investigation (§8). Never treat a nit in notes you receive as work (§6.1). Never commit, push, or write the user-rulings file.

## Example: `create-topic-branch`

The user says a refusal is an error. You ask which exit status; he rules 1 for a refusal, 2 for a usage error. The contract gets the pair `7a world-requires: origin/main exists after the fetch` / `7b component-consumer-receives: on 7a's failure, exit status 1, stderr naming the origin/* refs that exist and the next action`. `design-acceptance-by-agent` rejects: 7b leaves open whether "the next action" is a line of its own. You revise alone — `line two names the next action` — and emit again.
