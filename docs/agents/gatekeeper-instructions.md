# `gatekeeper` — seat instructions

Your pile: **taking the git-gatekeeper from built-but-dormant to live.** Every task here shares one specification, one program, and one threat model, so each makes the next cheaper. Read [the seat model](agent-seat-model.md) for how seats work; this file is your brief.

## Where things stand

`scripts/git-gatekeeper.py` is **built through all five slices** and merged to main (PR #49, 2026-08-12), with a 169-case suite in `scripts/git-gatekeeper-test.py`. The gate is **dormant**: no host holds a main-capable credential, so nothing routes through it yet. Agents currently reach main the interim way — commit to a working branch, push, and the user's Mac-side seat reviews and merges.

**Read first:** `docs/cross-project/git-gatekeeper-design.md` (the canonical specification, design-as-of 2026-08-12) and `docs/issues/3-git-gatekeeper-build-slice-plan.md` (the build order, its ruled design points, and the program follow-ups). Issue: [nedschorus#3](https://github.com/nedschorus/nedschorus/issues/3), whose body is current as of 2026-08-12.

The full review history — two md-review grids, a subtraction review, and every ruling with its reasoning — is in `md-review-records/2026-08-09-git-gatekeeper-design/`. Consult `dispositions.md` and `codex-dispositions.md` there **before reopening any settled question**; roughly forty decisions are recorded with dates and grounds, and re-deriving them wastes the user's time.

## The road, in order

1. **Design the walked-approval evidence format.** What does the user's approval of an instruction-class change look like as a checkable artifact? Undesigned today, and everything downstream waits on it. Class definition and guards: [nedschorus#31](https://github.com/nedschorus/nedschorus/issues/31).
2. **Build slice 6** — the review-evidence check, which enforces that format at the gate. Ruled 2026-08-10 as a prerequisite of activation, because the deployed gatekeeper copy self-updates from main and that is only safe once its own source cannot reach main without walked approval.
3. **The credential work** — the dedicated GitHub account (C1/C3: a collaborator with write on this one repository, never an org owner), the dedicated Unix user holding the credential, the sudoers rule pointing at a **root-owned copy outside every checkout** that keeps itself current from main, and moving branch protection's push restriction onto the new account. Requires an org owner to apply; the user does this part.

Also yours: **PR #55** (`gatekeeper audit: account names compared case-insensitively; PR #49 review rulings folded into the slice plan`), open and awaiting review.

## What is settled, and must not be relitigated

The user ruled these; each is recorded with reasoning in the disposition files. Notable: slice 4's async machinery **stays** (slow checks are expected); the deployed copy **self-updates** rather than being hand-deployed (simple-to-operate over simple-to-build); `--issue` **stays** (a mechanical forcing function is never traded for trained habit); the trailer-absence audit is **deleted** (a detector with no consumer is cost without value); the base is **computed, not declared**; C7 is **struck to zero**.

## Boundaries

The handoff and supervisor machinery belongs to `fleet`, review methodology to `sanity-checker`. If your work needs a change there, say so rather than reaching into it — those seats hold the context.

## First action

Read the specification and the slice plan, check whether PR #55 has merged, then report to the user where the road stands and ask which step he wants first. Do not start the evidence-format design without his go-ahead: it is instruction-class work and its shape is his ruling to make.
