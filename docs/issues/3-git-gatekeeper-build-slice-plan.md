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
| 2 **BUILT 2026-08-08** | The entry checkpoint: `--import` (the `imports` query was built here, then deleted by user ruling 2026-08-10 — `git log --grep` is the view) | T11 (T10 retired) | hand-recorded legacy imports |
| 3 **BUILT 2026-08-09** | Concurrency: loser integrates over newer commits, real conflict refuses, retry cap | T4, T5, T6 | slice 1's `main-moved` refusal |
| 4 | Worker lifecycle: `--no-wait`, detached worker, `status`, `cancel`, crash recovery | T7, T8 | slice 1's `unbuilt-option` refusal |
| 5 | Enforcement surfaces: branch-protection audit, repo git config, CLAUDE.md workflow lines (trailer-absence audit deleted, user-ruled 2026-08-10) | B3c | the founding-window "boss watches every landing" guard |

Not in any of the five, and deliberately so: the review-evidence check for
the instruction-file class
([nedschorus#31](https://github.com/nedschorus/nedschorus/issues/31), guard
1). It needs an approval-evidence format that does not exist yet, and the
in-session tamper guard
([`.claude/hooks/instruction-file-guard.py`](../../.claude/hooks/instruction-file-guard.py))
covers the same surface today. It becomes slice 6 when that format is
designed.

User-ruled 2026-08-10: slice 6 is now a scheduled prerequisite of
activating the privileged lane. The deployed, root-owned gatekeeper copy
(C2 as amended) upgrades itself from main, which is safe only once the
gatekeeper's own source is in the instruction-file class with the evidence
check enforcing walked approval. Sequence: slices 4 and 5, then the
approval-evidence format design, then slice 6, then the credential work.

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
- **The audit is detection, not gating.** It catches the configuration
  residual (protection drifting from the design; an owner credential
  editing protection). Useful, but it protects a lane that does not exist
  until slice 1 ships. (Its former sibling, the trailer-absence history
  scan, was deleted by user ruling 2026-08-10 — see the spec's
  enforcement section.)

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
`status` (4), `cancel` (4), the refusal record B4d (4), the
branch-protection audit (5),
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

First, the classification's one home is the specification's § Relationship
to the legacy design, which performed it at design time in the four-class
vocabulary — this plan inherits those dispositions by pointer rather than
restating them (deduplicated 2026-08-10; a table restating that section
lived here until then, provenance in git history). Slice-landing notes
unique to this plan: the CLAUDE.md workflow rules and the git-config pins
land in slice 5. Second — verified 2026-08-07 — **the legacy checkout does
not exist on this box.** `~/Projects/nedlern` is absent; only
`~/Projects/nedschorus` is present. Slice 1 therefore reads no legacy
material at all, and its classification is inherited, not fresh. No
consider-feature entries, so nothing goes to `legacy-feature-queue/`.

## Program follow-ups from the 2026-08-09 md-review

Rulings from the user's review of the revised spec (records:
`md-review-records/2026-08-09-git-gatekeeper-design/`); program work, not
spec text.

Applied 2026-08-11 (suite 140 cases green, was 146): the `imports`
deletion, the base absorption, and the catalog collapse below — plus one
stray the sweep exposed: the program's `unsafe-path` code, which the spec's
catalog never listed, folded into `malformed-field` under the same
collapse principle. The refusal-text quality pass ran the same day over
the final catalog: every refusal site meets the user's bar (facts name
the offending path/field and embed what the program holds — stderr,
intervening commits, the current tip; next actions are verb-first and
specific); no entry needed a user judgment call. Still pending, slice-4
scope by design: the expiry sweep and the liveness check.

- **Refusal-text quality pass** (user-ruled 2026-08-10). The bar, in the
  user's words: a refused check-in gets "the best, most useful and
  actionable refusal text that can be reliably generated." Sweep every
  error-catalog entry against three questions: (1) does the text say what
  happened, in the caller's terms; (2) does it name the exact next action,
  not a category of action; (3) does it include every fact the program
  already holds that the caller would otherwise have to dig up — the
  offending path, the conflicting commit id, the expected form of a missing
  argument. "Already holds" is the limit: no speculative investigation
  beyond what the check-in computed. Entries whose text needs a judgment
  call go to the user rather than being decided silently. Runs alongside
  slice 4.
- **Refusal-record expiry** (user-ruled 2026-08-10). Every gatekeeper
  invocation first sweeps retained `--no-wait` refusal records older than
  30 days — opportunistic, no daemon. Slice 4 work: it lands with the
  machinery that creates the records.
- **Advisory sees untracked files** (user-ruled 2026-08-11, Codex-leg
  WALK-3): drop `--untracked-files=no` from the advisory's status call so
  a forgotten new file — its likeliest target — is named; ignored files
  stay hidden, and the advisory still never blocks. One test case; apply
  with the Codex-leg fix batch.
- **Parser-layer errors join the JSON contract** (user-ruled 2026-08-11,
  Codex-leg WALK-2): wrap argparse so command-line-form errors — unknown
  flag, missing argument, unknown subcommand — emit the `malformed-field`
  teaching refusal as JSON with exit 1, quoting argparse's complaint in
  facts, instead of usage text with exit 2 (the defect code). Test cases
  for each shape; apply with the Codex-leg fix batch.
- **Refuse symlinked declared paths** (user-ruled 2026-08-11, Codex-leg
  WALK-1): a declared path that is itself a symlink refuses
  `malformed-field` — `Path.is_file()` follows links, so today a
  symlink-to-file passes and its target's bytes (possibly outside the
  repository) would be read as declared content. One lstat check plus one
  test case; apply with the Codex-leg fix batch.
- **Cancel kills the process group and waits** (user-ruled 2026-08-11,
  Codex-leg WALK-4): killing only the recorded worker pid leaves an
  already-spawned `git push` child running, so `cancelled` could be
  answered while the push lands moments later. Slice 4 builds cancel as:
  process-group kill, wait for exit, then the history query. Lands with
  the cancel machinery it corrects.
- **Liveness check before the resubmit sweep** (md-review finding HG31,
  noted 2026-08-11). Concurrent identical submissions share one digest and
  therefore one workspace; before sweeping a leftover workspace, test
  whether its recorded worker is alive — alive answers `in-progress`
  instead of sweeping the ground from under a running twin. Slice 4 work:
  lands with the worker lifecycle it protects.
- **Collapse the refusal catalog in the built program** (user-ruled
  2026-08-10): delete the unreachable `empty-change` branch (dead code —
  the first unchanged path refuses first) and its catalog entry; fold
  `missing-message` into `malformed-field`; merge the four import codes
  into `import-invalid`. Teaching text and facts keep every distinction.
  Matching test-assertion edits across T1/T11. Apply after the review
  walk closes, together with the other program follow-ups.
- **Absorb the base into the program** (user-ruled 2026-08-10): drop the
  `--base` field from the contract; the program computes
  `git merge-base HEAD origin/main`, after a fetch, in the caller's
  checkout. Retire `unknown-base` / `base-not-on-main`. Rework against
  built code: screening resolves the base after `resolve_repository`;
  T1's base cases delete; T3/T4/T5 fixtures set the caller's HEAD instead
  of passing `--base`. Apply after the review walk closes.
- **Delete the `imports` subcommand from the built program** (user-ruled
  2026-08-10): the parser entry, `imports_table`, `parse_import_trailers`,
  the per-call scratch clone, and T10's test cases. The `--import` trailer
  machinery and T11's screening stay. The view is
  `git log origin/main --grep "Gatekeeper-import:"`, documented in the
  spec. Apply after the review walk closes; suite must stay green minus
  the retired cases.

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
