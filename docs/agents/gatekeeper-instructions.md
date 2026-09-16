# `gatekeeper` — seat instructions

Your work — the body of related work this seat owns — is **taking the main-gatekeeper from built-but-dormant to live.** Every task here shares one specification, one program, and one threat model (the specification's § The credential and enforcement is where that threat model is written down), so each makes the next cheaper. Read [the seat model](../nedschorus-wiki/agent-seat-model.md) first: it defines the words used here — seat, walked approval, slice, the C-numbers — and this file assumes them.

## Where things stand

`scripts/main-gatekeeper.py` is **built through slice 5** — every slice of the original five-slice plan — and merged to main (PR #49, 2026-08-12), with a test suite in `scripts/main-gatekeeper-test.py` (169 cases as of 2026-08-13; the count moves as slices land, so run it rather than quoting it). A **sixth slice**, the review-evidence check that would have enforced a walked-approval evidence format, was added by ruling on 2026-08-10 and ruled not to be built on 2026-08-17 (the specification's § Resolved; the full reasoning is `docs/issues/3-slice-6-review-evidence-not-built.md`); it keeps its number, so the slices that remain start at 7. The gate is **dormant**, but not for want of a main-capable credential: the Mac's `gh` credential, `nedlern`, is on main's push allow-list (the specification's Implementation status). What stops it is its last step: since 2026-08-20 main's protection has required one approving review, with no account exempt and `enforce_admins` on, so the program as built, which pushes its candidate straight to main, would be refused there (§ The credential and enforcement, the Branch protection bullet). One live end-to-end check-in has gone through it, commit `b24e376` on 2026-08-18, user-authorized at the merge-lane seat before the review requirement existed; nothing routes through it in ordinary use. Agents currently reach main the interim way — commit to a working branch, push, and the user's Mac-side agent reviews and merges (that agent runs on his Mac and is outside the seat model; you reach it by telling the user, not by addressing it directly).

**Read first:** `docs/cross-project/main-gatekeeper-design.md` (the canonical specification, design-as-of 2026-08-12) and `docs/issues/3-main-gatekeeper-build-slice-plan.md` (the build order, its ruled design points, and the program follow-ups). Issue: [nedschorus#3](https://github.com/nedschorus/nedschorus/issues/3), whose body is current as of 2026-08-12.

The review history — two cold-read runs and a subtraction review, with the rulings they produced and the reasoning behind each — is in `git show db917b5:md-review-records/2026-08-09-git-gatekeeper-design/`, chiefly `dispositions.md` and `codex-dispositions.md` (roughly forty decisions, each dated with its grounds). Rulings also live in two other places, so that directory is not the whole record: the slice plan carries the design points it settles, and issue #3's body carries the state.

**A settled question may be reopened — by the user, not by you.** If one now looks wrong, read its disposition first, then put it to him with what changed; do not re-derive it silently and do not act against it. Re-deriving decisions he already made is the specific waste this record exists to prevent.

## The road, in order

What remains before activation is four slices, listed in the slice plan's § The slices that remain before activation, to which the specification's Implementation status points.

1. **Slice 7 — the gate opens a pull request instead of pushing to main** (user-ruled 2026-08-29; the specification's § The credential and enforcement, the Branch protection bullet). Today `attempt_push` pushes `main-gatekeeper-candidate:main` directly. What the pull request carries is ruled too, shape A (user-ruled 2026-09-15): the single candidate commit the gate composes, which the merge-lane reviews, approves and merges as a merge commit pinned to the approved commit (the specification's Implementation status; the record is the slice plan's § What the gate's pull request carries and how it merges — ruled 2026-09-15). Under shape 1 (user-ruled 2026-09-14) the merge-lane keeps reviewing and approving the gate's pull requests at activation, which is how the 2026-08-17 prerequisite that the gate be able to review what passes through it is met; a reviewer attached to the gate itself is deferred, not rejected (Implementation status; the slice plan's § Activation shape ruled 2026-09-14).
2. **Slice 8 — the per-file staleness report** (user-ruled 2026-08-31): for every declared path, whether main has changed it since the base commit, how many commits, and the latest pull request — a report, never a refusal. The specification names it only through its Implementation status's pointer to the slice plan, whose § The per-file staleness report — slice 8's requirement holds it in full.
3. **Slice 9 — the check battery**, the mechanical checks that run at check-in. Its owner has been unruled since 2026-08-14: whether this build owns it or the toolchain plan's Phase 1 binding is corrected is the user's ruling. The specification names it only through the same pointer; the question is the slice plan's § Open item 3.
4. **Slice 10 — the C2 move**: the gate runs from the dedicated Unix user, on a **root-owned copy of the program outside every checkout** that updates itself from main, pushing on the `ned-git-gatekeeper` token rather than on its caller's credential. The design is the specification's § The credential and enforcement, the Unix-user boundary bullet — read there before proposing anything, including what happens when the self-update cannot reach main, and the 2026-08-18 ruling that on the box, where every agent holds passwordless sudo, C2 is discipline rather than a hard boundary. The GitHub half of the credential work is done: the dedicated account (C1/C3), `ned-git-gatekeeper`, was created on 2026-08-29 as a collaborator with write on both of the organization's repositories and a member, never an owner, and a fine-grained token for it has existed since the same day. Branch protection's push restriction does not move onto it: under the 2026-08-29 ruling the gate opens a pull request, so the account needs no allow-list entry (§ The credential and enforcement, the layout-amendment bullet).

Cross-machine callers (C8) stay open and are not a slice: the specification's § Open, decided when a Mac-side agent first needs direct check-in.

Slice 9 waits on the user's ruling of its owner.

PR #55 (`gatekeeper audit: account names compared case-insensitively; PR #49 review rulings folded into the slice plan`) **merged 2026-08-13**, so its rulings are in the slice plan you are about to read. Nothing of this seat's work is outstanding in review as of that date — verify with `gh pr list --repo nedschorus/nedschorus --state open` rather than trusting this sentence, since PR state goes stale within hours.

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

Read the specification and the slice plan, check PR #55's state, and confirm the test suite runs green. Then report to the user where the road stands, and propose which slice to start with, and why. Slice 9 is not available to you until he rules its owner.
