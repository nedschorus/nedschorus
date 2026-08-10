# git-gatekeeper build — slice plan

Issue: [nedschorus#3](https://github.com/nedschorus/nedschorus/issues/3)

Working material for the build of `scripts/git-gatekeeper.py`, the single
program through which every change reaches `main` in nedschorus. This
document decomposes that build into slices, fixes the boundary of the first
one, and records the design points the specification deliberately leaves to
the builder.

**The specification is canonical, not this document.**
[`docs/cross-project/git-gatekeeper-design.md`](../cross-project/git-gatekeeper-design.md)
(design-as-of 2026-07-24) states the contract; the build bindings in
[`docs/issues/queue/3-gatekeeper-build-bindings.md`](queue/3-gatekeeper-build-bindings.md)
(boss-walked 2026-07-30) supplement it with B1–B6. This plan only says what
gets built in what order, and answers questions those two documents leave
open. Where this plan and the specification appear to disagree, the
specification wins and this plan is wrong.

Author: choirmaster, session 1caf1c51 (first build task).

## Why the order matters

The gatekeeper is not an optimization; it is the project's only check-in
lane. Until it exists, choirmaster is push-less by ruling
([nedschorus#45](https://github.com/nedschorus/nedschorus/issues/45),
2026-08-07): it commits to its own branch and a Mac-side agent merges after
review. The interim was ruled explicitly as "until the git-gatekeeper
provides the check-in lane." So the first slice is chosen for one property
above all others: **it is the shortest path to a change actually reaching
main through the program.** Everything that does not serve that goes later.

## The five slices

| Slice | Delivers | Spec tests | Retires |
|---|---|---|---|
| 1 **BUILT 2026-08-08** | Synchronous check-in end to end: screening → candidate → commit → push | T1, T2, T3, T9 | the manual merge lane, on the happy path |
| 2 **BUILT 2026-08-08** | The entry checkpoint: `--import` and the `imports` query | T10, T11 | hand-recorded legacy imports |
| 3 **BUILT 2026-08-09** | Concurrency: loser integrates over newer commits, real conflict refuses, retry cap | T4, T5, T6 | slice 1's `main-moved` refusal |
| 4 | Worker lifecycle: `--no-wait`, detached worker, `status`, `cancel`, crash recovery | T7, T8 | slice 1's `unbuilt-option` refusal |
| 5 | Enforcement surfaces: trailer-absence audit, branch-protection audit, repo git config, CLAUDE.md workflow lines | T12, B3c | the founding-window "boss watches every landing" guard |

Not in any of the five, and deliberately so: the review-evidence check for
the instruction-file class
([nedschorus#31](https://github.com/nedschorus/nedschorus/issues/31), guard
1). It needs an approval-evidence format that does not exist yet, and the
in-session tamper guard
([`.claude/hooks/instruction-file-guard.py`](../../.claude/hooks/instruction-file-guard.py))
covers the same surface today. It becomes slice 6 when that format is
designed.

### Why the boundaries fall here

- **Import is separable from check-in.** The import triple is three extra
  fields, one extra copy step, and one extra trailer line — none of it on
  the path a non-importing change takes. Splitting it keeps slice 1 from
  carrying the legacy-repository fixture.
- **Concurrency is the hardest logic in the design and is not needed to
  land the first change.** Rebuilding a candidate over a moved main and
  deciding clean-re-application versus real conflict is where the bugs
  live. Slice 1 handles a moved main honestly — it refuses and teaches the
  fix — and slice 3 upgrades that refusal into automatic integration. This
  is the project's manual → script → automation ladder applied inside one
  component.
- **The worker lifecycle serves slow checks, and there are no slow checks
  yet.** `--no-wait`, the detached worker, `status`, and `cancel` all exist
  for a caller who does not want to block. In version 1 the pipeline is
  screening plus construction plus a push; waiting is cheap.
- **The audits are detection, not gating.** They catch the cooperative
  residual (an agent pushing raw, an owner editing protection). Useful, but
  they protect a lane that does not exist until slice 1 ships.

## Slice 1 — synchronous check-in, end to end

*BUILT 2026-08-08. `scripts/git-gatekeeper.py` with
`scripts/git-gatekeeper-test.py`; every item below is in place. The
gate is working but dormant: this box authenticates as `ubuntu-claude`
and branch protection admits only `NedLern`, so nothing checks in to
the real repository until open item 1 is settled.*

**Built:** `scripts/git-gatekeeper.py`, command `check-in`, `--wait` only,
`--import none` only.

In scope:

1. **Instant screening, complete.** Every form refusal in the
   specification's catalog that a non-importing request can reach:
   `malformed-field`, `missing-message`, `unknown-path`, `unchanged-path`,
   `empty-change`, `unknown-base`, `base-not-on-main`, plus B2's
   `unsafe-path`. Each refusal names the error, the specific facts, and the
   exact next action (B5's verb-first phrasing), and touches nothing.
2. **The digest** (specification field 8): SHA-256 over base id, sorted
   path list, each path's new bytes, and the import triple. Screened
   against history at submit, so an identical resubmit answers
   `already-checked-in <commit>` having done no work.
3. **The resolve-once request record** (B4c): every environment-derived
   field — origin above all — is resolved during screening and written into
   the workspace as the request record. Nothing downstream re-derives it.
4. **Candidate construction** in
   `$XDG_STATE_HOME/nedschorus-gatekeeper/<digest>/` (B4a): a clone at the
   declared base with exactly the declared changes applied. Unchanged files
   come from main, never from the caller's worktree.
5. **The commit and the full trailer block**, including B6's
   `Gatekeeper-agent` line.
6. **The push**, happy path.
7. **The advisory** (specification § Constructive guarantees): undeclared
   modifications in the caller's worktree are noted in the reply and never
   block.
8. **B1's reply contract**: one JSON object on stdout; exit 0 success and
   informational, 1 catalog refusal, 2 program defect.
9. **Workspace sweep** on both endings.

Out of scope, each with the slice that takes it: `--import` (2), `imports`
(2), automatic integration over a moved main (3), `conflict` and
`main-moving-too-fast` (3), `--no-wait` and the detached worker (4),
`status` (4), `cancel` (4), the refusal record B4d (4), both audits (5),
repo git config (5), CLAUDE.md workflow lines (5), review evidence (6).

**Tests** — `scripts/git-gatekeeper-test.py`, matching the convention
already in `scripts/`: standard library only, self-running, one PASS/FAIL
line per case, non-zero exit on any failure. Cases: T1 every form refusal,
each asserted to leave no side effect; T2 the happy path's four success
guarantees with the trailer block asserted exactly; T3 the three digest
properties (identical resubmit deduplicates, changed content digests fresh,
metadata-only change does not); T9 the advisory; the `main-moved` refusal;
and B3d's version-floor smoke assertion (Python ≥ 3.12, git ≥ the recorded
floor — this box runs Python 3.14.4 and git 2.53.0).

**The alternative boundary, considered and not chosen:** slice 1 could stop
after screening and the digest — the whole pure core, no git writes, fully
testable, roughly half the code. It was rejected because it delivers no
check-in: the program would exist and the manual merge lane would still be
the only way to main. The smaller slice is the fallback if slice 1 as
scoped proves too large to land in one reviewable change.

## Rewrite-policy classification for this slice

Required by the rewrite policy (founding plan § Standing decisions): every
piece of work that touches legacy material classifies the legacy features
it touches. Two facts bound this slice's table.

First, the specification already performed this classification at design
time (§ Relationship to the legacy design); the table below restates those
dispositions in the four-class vocabulary rather than re-deciding them.
Second — verified 2026-08-07 — **the legacy checkout does not exist on this
box.** `~/Projects/nedlern` is absent; only `~/Projects/nedschorus` is
present. Slice 1 therefore reads no legacy material at all, and its
classification is inherited, not fresh.

| Legacy feature (`git-clean-slate-plan.md`, legacy `docs/working/proposed/`) | Class | Record |
|---|---|---|
| Workflow rules expressed as CLAUDE.md documentation | update-feature | Kept as documentation only, never enforcement — a Python program does not read CLAUDE.md, and different machines carry different copies. Lands in slice 5. |
| Protection-as-lock | update-feature | Reduced from many-writer protection to one credential behind one program. Live since 2026-07-21. |
| Three GitHub Apps | remove-feature | Multi-writer machinery; NC has one writer. |
| Credential helper | remove-feature | Serves per-agent credentials, which NC does not issue. |
| Per-agent branches | remove-feature | Ordinary changes use no branches. |
| PR pipeline for ordinary work | remove-feature | Replaced by the single gate; PRs are not the ordinary path. |
| Parking states | remove-feature | The four-state model has no parking; a stalled request is resubmitted, not parked. |
| Minimal repo git config (`user.name`, `user.email`, `useConfigOnly`) | preserve-feature | Contract preserved, values re-derived and stated in the specification, not imported. Test-pinned in slice 5. |

No consider-feature entries, so nothing goes to `legacy-feature-queue/`.

## Design points this plan settles

The specification leaves these to the builder. Each is a real fork, and
each is recorded here as the answer the build will use.

### D1 — Where the program reads main from

The program clones `origin` into the per-digest workspace and builds the
candidate there, at the declared base. It never uses the caller's worktree
as the source of unchanged content, and it reads the caller's worktree
exactly once, for the declared paths (specification field 1).

Tests need this to point somewhere other than GitHub. Per B3a, pushing
tests target a throwaway local bare repository, fresh per test. The program
therefore takes the remote from an explicit argument that defaults to the
invoking repository's `origin`, so a test can hand it a fixture path
without any special test-only code path in the program.

### D2 — Options not yet built

Slice 1 does not implement `--no-wait`, `--import` with a value, or the
`status`, `cancel`, and `imports` commands. Reaching one of them must not
be an unnamed ending, and it must not exit 2 (B1 reserves exit 2 for
program defects, so an argument-parser rejection would make a loop counter
read a scoping decision as a gatekeeper bug).

New catalog entry, `unbuilt-option`: a normal three-part refusal, exit 1,
naming the option, the slice that builds it, and the available alternative
("resubmit with `--wait`"). It is removed entry by entry as each slice
lands, and is gone after slice 5.

### D3 — The value of the `Gatekeeper-agent` trailer

B6 requires `Gatekeeper-agent: <runtime/model>` on every commit, never
omitted. The environment does not carry it: this box exposes
`CLAUDE_CODE_SESSION_ID` and `AI_AGENT=claude-code_2-1-220_agent`, which
name the runtime and its version but not the model, and the model is the
half the fix ladder needs.

The program therefore takes it as a required declared field, resolved once
at screening like every other environment-derived value. The caller is the
only party that knows which model it is. This is the cooperative class — a
caller can declare wrongly — consistent with the design's honest-singleton
stance: the gatekeeper records what it is told and never guesses.

### D4 — A moved main, before slice 3

Slice 1 pushes once. If the push is rejected because main moved since the
declared base, the reply is a refusal named `main-moved`, carrying the
files, the intervening commits, and the next action: update from main,
rebase the work, resubmit. Nothing is left behind; the workspace is swept.

`main-moved` retires in slice 3, where the same condition splits into
automatic integration (clean re-application, the usual case) and `conflict`
(the new main touched the same content).

## Open — awaiting the user

1. **The push credential.** Slice 1 ships fully tested against local bare
   repositories, but it cannot check anything into
   `nedschorus/nedschorus` from this box: the box is authenticated as
   `ubuntu-claude`, and branch protection restricts pushes to `NedLern`.
   The design's whole premise is that the program holds the project's one
   push-capable credential. So slice 1 lands as a working, dormant gate,
   and a separate decision — install the `NedLern` credential for the
   program's use on this box, or run the program on the Mac, or move
   straight to the dedicated-identity rung the design names — turns it
   live. Not choirmaster's decision to make.
2. **The `write-test-plan` skill.** Founding plan open question 8 names
   [nedschorus#18](https://github.com/nedschorus/nedschorus/issues/18) as
   the first expected candidate-skill pull, triggered by exactly this task.
   Building it first would produce this slice's test plan; not building it
   means the test plan above is hand-written, as it currently is.

## How this plan was ruled

Walked with the user 2026-08-08 and closed at the first item by his direction:
he is not picky about the slice boundaries, he wants progress, and he wants
more than the first slice delivered. So the decomposition, the slice-1
boundary, the classification table, and the four design points D1-D4 stand as
written above — accepted by not being contested — and the build proceeds
through the slices in order without per-item approval.

Two consequences recorded here because they change what gets built:

- The `write-test-plan` skill (open item 2) is NOT built first. Founding plan
  open question 8 anticipated pulling it at this task, but building a skill
  before building the thing it plans is the opposite of progress. The test
  plans in this document are hand-written. The pull stays available the moment
  a slice's test design genuinely stalls.
- The push credential (open item 1) does not block. Slices land tested against
  local bare repositories and go live when the credential question is settled,
  which is the user's to settle.

## Walk order

*The walk closed at item 1; the remaining items were accepted uncontested
rather than presented. Kept for reference.*

1. Purpose: what this walk decides and the bar for slice 1
   *processed 2026-08-08 -> ACCEPTED: the bar is that slice 1 must produce a
   change that actually reaches main through the program*
2. The five-slice decomposition
3. Slice 1's boundary — what is in and what is out
4. The rewrite-policy classification table
5. D1 — where the program reads main from, and the test fixture model
6. D2 — `unbuilt-option`, the refusal for options not yet built
7. D3 — how the program learns the `Gatekeeper-agent` value
8. D4 — `main-moved`, the interim answer to a moved main
9. Open 1 — the push credential and what "slice 1 done" means
10. Open 2 — `write-test-plan` (#18): pull it now, or hand-write the plan
11. Artifacts, naming, and the commit convention for this build
