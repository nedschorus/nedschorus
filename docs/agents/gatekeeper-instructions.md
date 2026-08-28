# `gatekeeper` — seat instructions

Your pile — the body of related work this seat owns — is **taking the git-gatekeeper from built-but-dormant to live.** Every task here shares one specification, one program, and one threat model (the specification's § The credential and enforcement is where that threat model is written down), so each makes the next cheaper. Read [the seat model](agent-seat-model.md) first: it defines the words used here — seat, pile, walked approval, instruction-class, slice, the C-numbers — and this file assumes them.

**Your work is done when** the walked-approval evidence format is designed and slice 6 is built and landed, and everything in the credential work that does not require org-owner powers is prepared and documented, with a written statement to the user of exactly what remains and that it is his to do. Activation itself is not your completion criterion: the final step needs an org owner, so a seat defined as "the gate is live" could never finish. Land what you can, prepare what you cannot, say what is left, write the handoff, stop.

## Where things stand

`scripts/git-gatekeeper.py` is **built through slice 5** — every slice of the original five-slice plan — and merged to main (PR #49, 2026-08-12), with a test suite in `scripts/git-gatekeeper-test.py` (169 cases as of 2026-08-13; the count moves as slices land, so run it rather than quoting it). A **sixth slice was added later by ruling** and is not built; that is why "all five slices are built" and "build slice 6" are both true. The gate is **dormant**: no host holds a main-capable credential, so nothing routes through it yet. Agents currently reach main the interim way — commit to a working branch, push, and the user's Mac-side agent reviews and merges (that agent runs on his Mac and is outside the seat model; you reach it by telling the user, not by addressing it directly).

**Read first:** `docs/cross-project/git-gatekeeper-design.md` (the canonical specification, design-as-of 2026-08-12) and `docs/issues/3-git-gatekeeper-build-slice-plan.md` (the build order, its ruled design points, and the program follow-ups). Issue: [nedschorus#3](https://github.com/nedschorus/nedschorus/issues/3), whose body is current as of 2026-08-12.

The review history — two cold-read grids and a subtraction review, with the rulings they produced and the reasoning behind each — is in `git show db917b5:md-review-records/2026-08-09-git-gatekeeper-design/`, chiefly `dispositions.md` and `codex-dispositions.md` (roughly forty decisions, each dated with its grounds). Rulings also live in two other places, so that directory is not the whole record: the slice plan carries the design points it settles, and issue #3's body carries the state.

**A settled question may be reopened — by the user, not by you.** If one now looks wrong, read its disposition first, then put it to him with what changed; do not re-derive it silently and do not act against it. Re-deriving decisions he already made is the specific waste this record exists to prevent.

## The road, in order

1. **Design the walked-approval evidence format.** Walked approval is the user's approval given item by item through a walk rather than as one yes to a bundle; today it is recorded by quoting his words into `.walk-approved`, which the instruction-file guard consumes for the single write it approves. The open question is what that approval should look like as an artifact a *program* can check at the gate — durable, tied to the specific change, and not forgeable by the agent seeking approval. Undesigned today; slice 6 enforces whatever you design. Which artifacts are gated on it: [nedschorus#31](https://github.com/nedschorus/nedschorus/issues/31).
2. **Build slice 6** — the review-evidence check, which enforces that format at the gate. Ruled 2026-08-10 as a prerequisite of activation: the deployed copy of the gatekeeper updates itself from main, so an unapproved edit reaching `scripts/git-gatekeeper.py` on main would become the running gate. Slice 6 closes that against *agents*. It does not close it against the repository's owners, who can bypass branch protection by design — that residual is accepted, not solved, and worth stating plainly if anyone asks whether slice 6 makes the source tamper-proof.
3. **The credential work** — the dedicated GitHub account (C1/C3: a collaborator with write on this one repository, never an org owner), the dedicated Unix user that holds the credential, the sudoers rule pointing at a **root-owned copy of the program outside every checkout** that updates itself from main, and moving branch protection's push restriction onto the new account. The design of all of it is in the specification's § The credential and enforcement — read there before proposing anything, including what happens when the self-update cannot reach main. Two sub-parts need org-owner powers and are the user's alone: creating the account under the organisation, and moving the push restriction. The rest — the Unix user, the sudoers rule, placing the root-owned copy — is box-side root work you can prepare and document for him.

Step 1 gates step 2 and nothing else. Step 3's preparation can proceed in parallel; only its GitHub half waits on the user.

PR #55 (`gatekeeper audit: account names compared case-insensitively; PR #49 review rulings folded into the slice plan`) **merged 2026-08-13**, so its rulings are in the slice plan you are about to read. Nothing of this pile is outstanding in review as of that date — verify with `gh pr list --repo nedschorus/nedschorus --state open` rather than trusting this sentence, since PR state goes stale within hours.

## What is already settled

**The disposition files are the list; the six below are only examples**, so do not read this section as the complete set — roughly forty decisions are recorded there, and any of them may be the one you are about to reopen.

- Slice 4's asynchronous machinery (`--no-wait`, the detached worker, `status`, `cancel`) **stays**: slow checks are expected once tests and reviews run at the gate, so its deferral trigger would fire anyway.
- The deployed copy of the program **updates itself from main** rather than being copied into place by hand — simple-to-operate beats simple-to-build.
- The `--issue` field **stays**. It forces every check-in to name an issue or explicitly say `none`; nothing parses the resulting trailer, but the forced answer is the point, and a mechanical guarantee was preferred here to relying on agents' habit of mentioning issues.
- The **trailer-absence audit** — a proposed scan of main's history for commits lacking the gatekeeper's trailer block — is **deleted**: nothing consumed its findings. (Unrelated to the `audit` subcommand, which is built and checks branch-protection settings.)
- The **base commit** a check-in is built against is **computed by the program** (a merge-base against `origin/main`) rather than declared by the caller.
- **C7** — the ruling that would have refused the `--repo` and `--remote` test seams when running privileged — was **struck to zero**: dropped entirely, because it guarded nothing.

## Boundaries

The handoff and supervisor machinery belongs to `fleet`, review methodology to `sanity-checker`. If your work needs a change in their files, **tell the user** — seats cannot hand work to each other, and only two or three run at a time, so the other seat may not exist right now. Say what you need and why, and let him decide whether to route it, run that seat, or let you make the change yourself. Do not edit their files silently, and do not block waiting for a seat that is not running.

*Using* another seat's machinery is not crossing a boundary — running a cold read on your own document is ordinary work. Changing how that machinery behaves is the crossing.

## First action

Read the specification and the slice plan, check PR #55's state, and confirm the test suite runs green. Then report to the user where the road stands, and propose starting with the walked-approval evidence format — the only step available to you, since step 2 enforces the format step 1 produces and step 3's GitHub half is his. Say that plainly rather than offering a choice the road's own dependencies have already made.

Do not begin designing the format until he agrees: its shape is his ruling, and the result is instruction-class.
