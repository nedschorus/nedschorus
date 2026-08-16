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
| 4 **BUILT 2026-08-12** | Worker lifecycle: `--no-wait`, detached worker, `status`, `cancel`, crash recovery, the expiry sweep | T7, T8 | slice 1's `unbuilt-option` refusal |
| 5 **BUILT 2026-08-12** | Enforcement surfaces: branch-protection audit (`audit` subcommand + the session-recycle ride in the fast-handoff writer), repo git config pins, the CLAUDE.md workflow line (user-walked 2026-08-12) (trailer-absence audit deleted, user-ruled 2026-08-10) | B3c | the founding-window "boss watches every landing" guard |

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

## Program follow-ups from the user's reviews

Two batches, each from a review of a different subject: the 2026-08-09
md-review of the revised specification, and the 2026-08-12 code review of
[nedschorus#49](https://github.com/nedschorus/nedschorus/pull/49). Program
work in both cases, not spec text.

### From the 2026-08-09 md-review of the specification

Rulings from the user's review of the revised spec (records:
`md-review-records/2026-08-09-git-gatekeeper-design/`); program work, not
spec text.

Applied 2026-08-11 (suite then 140 cases green, was 146): the `imports`
deletion, the base absorption, and the catalog collapse below.
Applied 2026-08-12 (suite then 150 cases green): the symlink refusal, the
parser-contract wrap, the untracked-files advisory, and the digest
length-prefix reframing. Slice 4 itself BUILT later the same day (suite
162 green): the worker lifecycle landed with all four of its ruled build
notes — the 30-day expiry sweep (plus stale screening scratch and
day-old dead-worker leftovers), the liveness check before the resubmit
sweep, process-group kill-and-wait for cancel, and the worker start-time
recorded beside its pid (Codex FIX-2 — the tag-only framing was
collidable by crafted content; every component is now length-prefixed) — plus one
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
- APPLIED 2026-08-12 with slice 4 — **Refusal-record expiry**
  (user-ruled 2026-08-10). Every gatekeeper
  invocation first sweeps retained `--no-wait` refusal records older than
  30 days — opportunistic, no daemon. Slice 4 work: it lands with the
  machinery that creates the records.
- APPLIED 2026-08-12 — **Advisory sees untracked files** (user-ruled
  2026-08-11, Codex-leg WALK-3): drop `--untracked-files=no` from the advisory's status call so
  a forgotten new file — its likeliest target — is named; ignored files
  stay hidden, and the advisory still never blocks. One test case; apply
  with the Codex-leg fix batch.
- APPLIED 2026-08-12 — **Parser-layer errors join the JSON contract**
  (user-ruled 2026-08-11, Codex-leg WALK-2): wrap argparse so command-line-form errors — unknown
  flag, missing argument, unknown subcommand — emit the `malformed-field`
  teaching refusal as JSON with exit 1, quoting argparse's complaint in
  facts, instead of usage text with exit 2 (the defect code). Test cases
  for each shape; apply with the Codex-leg fix batch.
- APPLIED 2026-08-12 — **Refuse symlinked declared paths** (user-ruled
  2026-08-11, Codex-leg WALK-1): a declared path that is itself a symlink refuses
  `malformed-field` — `Path.is_file()` follows links, so today a
  symlink-to-file passes and its target's bytes (possibly outside the
  repository) would be read as declared content. One lstat check plus one
  test case; apply with the Codex-leg fix batch.
- APPLIED 2026-08-12 with slice 4 — **Cancel kills the process group and
  waits** (user-ruled 2026-08-11, Codex-leg WALK-4): killing only the recorded worker pid leaves an
  already-spawned `git push` child running, so `cancelled` could be
  answered while the push lands moments later. Slice 4 builds cancel as:
  process-group kill, wait for exit, then the history query. Lands with
  the cancel machinery it corrects.
- APPLIED 2026-08-12 with slice 4 — **Liveness check before the resubmit
  sweep** (md-review finding HG31, noted 2026-08-11). Concurrent identical submissions share one digest and
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

### From the PR #49 code review (2026-08-12)

Findings from a code review of `choirmaster` at `3c418863` — the head that
built slice 4 (the worker lifecycle: `--no-wait`, the detached worker,
`status`, `cancel`) — taken while
[nedschorus#49](https://github.com/nedschorus/nedschorus/pull/49) was open
and unmerged. Each finding was reproduced by running the program unless
its entry says otherwise. The rulings were walked with the user item by
item and recorded *before* any code changed, so the fixes had a stated
bar; several were decided against the reviewer's own recommendation, and
those reversals are kept in the entries below because they are the
reasoning, not the decoration.

Seventeen headed entries. The recording commit, `4cadb46`, says sixteen;
so does the handoff that ordered this fold. Nothing records how the two
counts differ, so the entry count below is the file's own headings.
Applied 2026-08-12 across seven commits —
`cb582d6`, `646e82b`, `89bd749`, `3a301a8`, `71d492e`, `cacd3b9`,
`6d356d2` — merged into choirmaster as `6655e92` and reaching main inside
nedschorus#49's merge `9bd1335`. Suite then 202 cases, 200 green on a
stock macOS host; the two failures are environment artifacts, not code
defects (Apple's git 2.39.5 below the 2.40 floor — see the version-floors
entry — and `user.useConfigOnly` unset in the enclosing repository, which
may be a setup step slice 5 assumes rather than performs). The audit's
account-name casefold, the identity guard's one-writer half, the named-phase
seam with its cancel-truthfulness cases, and the accepted reply's host landed
after this batch and took the suite to 214.

These rulings were first recorded in a standalone document,
`docs/issues/3-gatekeeper-review-fix-rulings-2026-08-12.md`, which existed
separately only because the open PR was itself modifying this plan. It is
retired by this fold, as its own closing note directed; its verbatim text
remains in git history at `4cadb46`.

- APPLIED 2026-08-12 (`cb582d6`) — **Caller-supplied digests never build a
  filesystem path.** Defect: `require_digest` accepted any non-empty
  string, and `status`, `cancel` and `run_worker` each built
  `workspace_root() / digest` from it. Joining an absolute path discards
  the root and `..` resolves normally, so a caller-named path outside the
  workspace root was reachable: `cancel <absolute path>` removed a
  directory and its contents and answered `cancelled — the workspace is
  swept; nothing reached main`, exit 0, and `status ../../secret` returned
  a foreign `refusal.json` verbatim as the gatekeeper's own refusal reply
  and then deleted the directory. After C2 the program runs as the
  dedicated gatekeeper user via sudo, so the caller chooses the path and
  the gatekeeper's privileges perform the deletion — including against
  that user's own credential and state directories. Fix: `workspace_for()`
  locates a workspace by enumerating the workspace root and matching an
  entry whose name equals the digest; caller text is never joined onto a
  path. Escape becomes impossible by construction rather than by
  filtering, only entries the program itself created are ever acted on,
  and a string matching nothing answers `unknown-request`. Applied in all
  three places, `worker` included — it is a real, `--help`-listed
  subcommand, so its path build was caller-reachable too. Explicitly not
  done: a `^[0-9a-f]{64}$` format check. Under the enumeration fix it
  changes no outcome — its only effect is a more specific error string —
  and the project cuts machinery whose findings have no consumer, the same
  reasoning that deleted the trailer-absence audit (ruled 2026-08-10). Ten
  test cases across `status` and `cancel`, absolute and climbing
  arguments, each asserting the reply, that the named directory and its
  contents survive, and that no foreign record is returned; all ten fail
  against the pre-fix program.
- APPLIED 2026-08-12 (`646e82b`) — **A process group is killed only when
  the recorded pid leads it.** Defect: `worker.pid` was written above the
  `--no-wait` branch, so in the default waiting mode it recorded the
  caller's own pid — a process not started with `start_new_session`, whose
  group belongs to whatever launched it (the agent's shell, harness or
  pipeline). `cancel` read that pid and called
  `os.killpg(os.getpgid(pid), SIGTERM)`, signalling every process in the
  caller's group: in the demonstration a launcher, an unrelated `sleep`
  and the check-in all died, and the caller never received a reply because
  its harness went first. Reachable without malice — a twin submission of
  identical work returns the first request's digest to the second agent,
  and any agent may cancel (standing ruling, no permission machinery).
  Fix: `signal_worker()` group-kills only when `os.getpgid(pid) == pid`,
  true exactly for the detached worker (spawned `start_new_session=True`)
  and false for a foreground caller. The kernel answers the question; the
  program does not record a "this one was detached" flag and trust its own
  note, because the pid record is precisely the data that goes stale,
  tears, or names a recycled process. Ruled for the other branch: when the
  recorded pid leads no group, `cancel` signals that single process rather
  than refusing — cancel then behaves uniformly in both modes, which is
  simpler to teach and consistent with the standing ruling that any agent
  may cancel. Kept deliberately: `worker.pid` is still written in both
  modes, because twin detection depends on it — a second agent submitting
  identical work discovers the live sibling through that record and is
  answered `in-progress` instead of trampling it. Test: a launcher in its
  own session holds a child whose pid is recorded; cancel must leave the
  launcher alive while stopping the child.
- APPLIED 2026-08-12 (`646e82b`) — **`cancel` confirms the kill and
  re-asks history on every path, and gains a fifth outcome.** Amends the
  specification's "Outcomes, exactly four" to five. Two defects put a
  false `cancelled — the workspace is swept; nothing reached main` in
  front of callers. First, the ruled kill-wait-then-ask-history sequence
  ran only on the branch where a live worker was found; when the worker
  was already gone — it pushed and died, or swept itself — `cancel`
  answered from the history check made *before* the wait. Demonstrated: a
  worker's push landed inside that window, `cancel` answered `cancelled —
  nothing reached main`, exit 0, and `status` on the same digest one
  second later answered `checked-in 7ac9a7e`; where the worker also swept
  itself first, `cancel` instead answered `unknown-request — no trace of
  this digest` for work that had just reached main. Second, nothing
  confirmed the kill: after the SIGTERM and SIGKILL waits control fell
  through to `cancelled` with no liveness re-check, both `killpg` calls
  swallowed every error, and `worker_state` deliberately reads
  permission-denied as *alive* — the normal case once C2 puts the worker
  under the dedicated gatekeeper user. Demonstrated against a process this
  user cannot signal: 15.2 seconds spent, nothing signalled, workspace
  deleted, answer `cancelled — nothing reached main`, while the worker ran
  on free to push. Third, smaller: the post-SIGKILL wait reused the
  already-expired SIGTERM deadline, and both waits used wall-clock time,
  so a forward clock step skipped the second wait entirely. Fix: one exit
  path — whatever killing happened, confirm the process is gone, re-ask
  history, then answer; each wait computes its own deadline from a
  monotonic clock. That produces a state the catalog had no word for (the
  worker outlives SIGKILL, so the gatekeeper neither stopped it nor knows
  the outcome), and a fifth outcome was added rather than forcing a false
  `cancelled`: `cancel-failed`, carrying the pid, what was tried, and the
  instruction to check `status` shortly because the worker may still push.
  Its workspace is left in place rather than swept.
- APPLIED 2026-08-12 (`89bd749`) — **`worker.pid` is written atomically,
  and death requires positive evidence.** Defect: every writer truncated
  `worker.pid` in place, and every reader treated an unreadable or
  unparseable file as proof the worker was dead — the strongest conclusion
  drawn from the weakest evidence. Between those lay a window in which the
  file is empty on disk while the worker is alive. Demonstrated by
  emptying the file under a live worker: `status` answered `abandoned —
  workspace present, worker dead; resubmit safely`; a twin submission took
  the dead path, deleted the live worker's candidate clone and its
  declared snapshot, and spawned a second worker on the same digest; the
  first worker then died reading its own declared bytes with output at
  `/dev/null`, leaving no refusal record and no trace. Mid-push, the clone
  would have been deleted under a running `git`. A related crash path: a
  file torn between the read at the top of `cancel`'s kill block and the
  later escalation left `pid` unbound, and the `NameError` escaped the
  caught exception tuple as a program defect. Fix, two parts.
  `write_atomically()` writes through a temporary sibling and renames, so
  a reader sees either the old contents or the new and never an empty
  file. And `worker_state` gains a fourth value, `unknown`, for an
  unreadable or absent pid file; every caller except the age-gated sweep
  treats it as live — not swept, not trampled, no rival worker spawned —
  and only a confirmed process-not-found means dead. The asymmetry decides
  the default: guessing "alive" wrongly leaves a stale directory the sweep
  collects after a day, while guessing "dead" wrongly destroys work in
  flight and loses its reason silently. Tests: an empty and a garbage
  `worker.pid` must each report `in-progress` and leave the workspace
  intact.
- APPLIED 2026-08-12 (`89bd749`) — **The retained refusal record is
  written before anything is demolished, atomically, and is never swept
  unread.** Defect: `retain_refusal_record` deleted `worker.pid` and
  `request.json` first, then wrote `refusal.json` in place. That record is
  the caller's only route to a detached refusal's reason — the design
  deliberately keeps no other copy — and two windows destroyed it. A
  `status` arriving after the deletions but before the write saw no record
  and no worker, so it answered `abandoned — resubmit safely` for a
  request that had in fact refused with a real reason; a `status` arriving
  mid-write found the file present but empty, failed to parse it,
  fabricated a generic `workspace-io-error — record unreadable`, and then
  deleted the whole workspace anyway, so the real reason was gone
  permanently and the worker's own write failed into an unhandled
  `OSError`. Both reproduced. Separately, two concurrent `status` calls
  each received the full record, though the design states it is returned
  once and then swept. Fix, three parts: write the record before removing
  the candidate clone and pid file — never demolish the old state before
  the new state exists; write it through a temporary name and rename it
  into place; and never sweep a record that could not be read, since an
  unparseable record is unknown, not spent, and is left for a retry. The
  "returned once" property is now enforced by claiming the record with an
  atomic rename, so exactly one concurrent caller wins it — B4d was
  previously enforced by nothing.
- APPLIED 2026-08-12 (`cacd3b9`) — **The workspace is claimed by creating
  it, and a worker without a request leaves a reason.** Defect: `check_in`
  tested whether the workspace was occupied, then created it, then stamped
  it live. A twin submission arriving between the creation and the stamp
  saw a directory with no pid file, concluded the owner was dead, and
  deleted the live sibling's request record and candidate clone — the
  exact case the twin-detection ruling exists to prevent. The damage was
  silent, because the victim's `shutil.move` does not raise: CPython falls
  back to `copytree`, which recreates the missing parent, so the workspace
  reappeared holding only a partial clone. On a `--no-wait` submission the
  caller was answered `accepted <digest>` while the spawned worker found
  no `request.json`, returned the defect exit code with output at
  `/dev/null`, and recorded nothing — the request never ran, never pushed
  and never explained itself, and `status` later reported `abandoned`.
  Most of the window is closed by the entry above (a missing or unreadable
  pid file now means unknown and is treated as alive). Two changes remain
  and are applied here: the claim becomes the creation — the directory is
  created exclusively and a `FileExistsError` *is* the signal that another
  submission owns the digest, which removes the check-then-act gap rather
  than narrowing it — and a worker that cannot find its request now
  retains a refusal record saying so, instead of exiting silently into the
  defect code with no reply channel. Identity is stamped before the
  request record is written, so the observable `unknown` window is one
  rename wide.
- APPLIED 2026-08-12 (`3a301a8`) — **The symlink boundary is enforced
  symmetrically, on both sides and every component.** Widens WALK-1
  (user-ruled 2026-08-11), which was recorded APPLIED covering the read
  side's leaf component only. The specification states the boundary
  plainly — "a link's target can live outside the repository, and the
  security boundary does not follow it" — and neither direction delivered
  it. Reading: the shipped check tested only a declared path's final
  component, so with `esc` a symlink to a directory outside the
  repository, declaring `esc/secret.txt` passed every screen (no `..`, not
  absolute, printable ASCII) because the leaf is a regular file reached
  *through* the link; its bytes were read from outside and checked in to
  main. Reproduced independently by three reviewers. Writing: unchecked
  entirely, and worse — the candidate commit is built by checking out main
  and writing declared bytes over it, so a symlink carried in **main's own
  tree** at a declared path is recreated in the candidate clone and the
  write follows it out of the repository; a file outside every repository
  was overwritten with the caller's content. The caller's worktree is
  innocent in that case, since the link lives in main, so no check on the
  caller's files can catch it. Fix, one rule applied symmetrically:
  `refuse_symlinked_component()` requires a declared path to be a regular
  file or absent on both sides of the comparison — the caller's worktree
  and the base tree — with no component a symlink on either side.
  Rejected as the primary form: resolving the path and asserting
  containment inside the repository. Used instead of the per-component
  check it would silently reverse WALK-1, because a symlink whose target
  sits inside the repository passes containment while the ruling refuses
  it; containment may sit behind the per-component check as a second
  assertion only if it is shown to catch something the first does not. Two
  attachments: a base-tree symlink gets its own catalog code,
  `base-tree-symlink`, rather than the generic `workspace-io-error` whose
  next action reads "Resubmit the same request; this class of failure is
  safe to retry" — the caller did nothing wrong, cannot fix it by
  resubmitting, and each retry repeats the out-of-repository write, so the
  honest reply names the path, states that main carries a link there, and
  points at who can change main; and the scope sentence PR #49 added ("The
  caller's files and main are untouched. Scoped exactly (2026-08-12): …")
  is corrected, since writing bytes outside every repository appeared
  nowhere in its enumeration.
- APPLIED 2026-08-12 (`cacd3b9`) — **`status` and `cancel` answer from the
  request's own remote, and never assert absence after a failed fetch.**
  Two defects let a confident answer rest on nothing. `check_in` recorded
  the request's remote in `request.json` and nothing read it back;
  `status` and `cancel` resolved a repository from `--repo` or the
  caller's current directory instead. The accepted reply teaches
  `git-gatekeeper.py status <digest>` with no `--repo`, so run verbatim
  from a directory that is not a git repository it answered
  `malformed-field — not inside a git repository`, which is not among the
  five outcomes the design lists for `status`; run inside a repository
  with a different origin, checked-in work answered `unknown` and `cancel`
  answered `cancelled` for work already on main. The suite always passed
  `--repo` explicitly, so the taught command was never the tested one.
  And the history fetch ran with failure ignored, so an unreachable remote
  or expired credentials left the search reading a stale local copy:
  `cancel` asserted `nothing reached main` while the commit sat on the
  remote, and `status` answered `unknown — no trace of this digest; submit
  it`. Fix: resolve the repository from the request record when the
  workspace exists; make the taught next action a command that works as
  written; and on fetch failure answer `network-down`, already in the
  catalog and already documented as safely resubmittable, rather than
  asserting absence. Distinction preserved deliberately: swallowing a
  failed fetch remains correct for a check-in's base computation, where
  the specification rules the degradation tolerable and the behind-main
  integration absorbs it — it is not tolerable here, because in `status`
  and `cancel` the fetch decides whether the answer is true.
- APPLIED 2026-08-12 (`71d492e`, `6d356d2`) — **The two exemptions from
  the one-JSON-object contract are written down, and agent-facing text
  stops citing `--help`.** The reply contract states that every invocation
  prints exactly one JSON object on stdout, and reserves exit 2 for a
  program defect; two invocations broke it. `worker` was a real,
  `--help`-listed subcommand whose every path prints nothing — invoked
  without a request it produced zero bytes on stdout, zero on stderr, and
  exit 2, the defect code, for what is a caller's mistake; its docstring
  stated the intent ("Never prints; the reply channel is the workspace")
  but never reconciled it with the contract. `--help` prints usage text
  and exits 0: the parser wrapper added by PR #49 converts argparse
  *errors* into JSON refusals, as WALK-2 ruled, and does not touch the
  help path. Neither is made to emit JSON — help text as JSON serves no
  one, and the worker genuinely has no listener. What was missing is that
  the contract named no exceptions at all. Fix: state both exemptions in
  the specification (`--help` is the human lane; `worker` is an internal
  re-entry the program makes into itself, not a caller-facing
  subcommand); suppress `worker` from `--help` so the caller-facing
  surface matches the caller-facing contract; and remove the `--help`
  citation from the parser refusal's next-action text, which directed a
  JSON-consuming caller to the one command that returns no JSON — it
  cites the specification path instead. The exit code ceases to matter
  here, because a request-less worker now leaves a refusal record under
  the entries above.
- APPLIED 2026-08-12 (`71d492e`) — **The undeclared-changes advisory names
  real files.** Defect: widening the advisory to see untracked files fed
  `??` entries into a parse written for tracked changes. Git collapses a
  wholly-new directory into a single entry, so a check-in declaring
  `newdir/new.txt` was told `advisory: the working copy also differs at
  newdir/; confirm intentional` — the advisory named the caller's own
  declared work and sent an agent to investigate a change it had just made
  deliberately (reproduced). The same collapse defeated the widening's
  stated purpose, since a genuinely forgotten new file inside a new
  directory was never named either. And untracked filenames are arbitrary,
  unlike declared paths, which are screened, so names carrying spaces or
  non-ASCII bytes came back C-quoted and the advisory reported a string
  that was not a path. Fix: `git status --porcelain -z
  --untracked-files=all` — `-z` is NUL-delimited and disables quoting,
  `-uall` names actual files instead of collapsing to the directory, and
  the exact-match filter against declared paths then works. Accepted cost,
  uncapped for now: `-uall` enumerates every untracked file rather than
  stopping at a directory, so a repository carrying a large un-ignored
  untracked tree pays more and produces a longer advisory string; no
  truncation rule is built until a real case appears. Worktree hygiene —
  which files should be ignored rather than reported at all — is tracked
  separately as
  [nedschorus#50](https://github.com/nedschorus/nedschorus/issues/50).
- APPLIED 2026-08-12 (`71d492e`, portable reader) and 2026-08-13 (one
  writer) — **The worker-identity guard works on macOS and Linux alike,
  and has one writer.** The design names a
  residual and its mitigation: a recycled process id could masquerade as a
  live worker, so slice 4 records the worker's start time beside its pid
  and `status` checks both. The code recorded it and three defects stopped
  it working. (1) `process_start_time` read `/proc/<pid>/stat` only, a
  path that does not exist on macOS, so it returned an empty string for
  every process, the reader fell back to the placeholder, and the
  comparison was skipped — the guard was dead code on that half of a fleet
  that runs both macOS and Ubuntu, with nothing announcing which behaviour
  a given host had. The suite could not detect the difference: its only
  pid fixture was a hand-written placeholder, and no case asserted that a
  start time is ever captured or ever effective. (2) The write ordering was
  an unsynchronised race: the worker's loop claimed to yield to the
  spawner's placeholder write, but it waits for `worker.pid` to *exist*
  and the spawner created it before launching, so the loop returns
  immediately and the two writes race, and the placeholder can land last
  and win permanently. (3) A worker that dies before stamping — spawn
  failure, out-of-memory, an early kill — leaves the placeholder in place
  forever, and the reader explicitly skips the comparison when it sees a
  placeholder, so that workspace's guard is off for good and a later
  `cancel` group-kills whatever now owns the recycled pid. Ruled fix: one
  writer, and a portable reader — the spawner writes no placeholder, the
  worker writes the pid file as its first act, and the gap before it does
  is covered by the ruling above that a missing pid file means unknown and
  is treated as alive; start time is read portably (`ps -o lstart= -p
  <pid>` where `/proc` is absent) so the guard behaves identically on both
  platforms. Applied: the portable reader, with `ps`'s output joined into
  one whitespace-free token because `worker.pid` is `<pid> <start>` split
  on whitespace, so `Tue Aug 12 13:45:01 2026` would otherwise record
  `Tue` and never match again — the test asserts a real start time is
  captured on the running platform and carries no whitespace. The
  one-writer half was missed at the time and applied 2026-08-13: `check_in`
  no longer stamps in `--no-wait` mode, so the detached worker is the only
  writer of `worker.pid` and writes it as its first act; the worker's
  yield loop is gone, having waited for a file the spawner had already
  created and so returned at once into the race it was meant to prevent.
  The claim does not depend on the pid file — the exclusive `mkdir` holds
  it (see the workspace-claim entry above) — so the gap before the worker
  stamps reads as unknown, which every caller treats as alive. In waiting
  mode the caller is the worker and still stamps itself, unchanged. Two
  cases, both red against the pre-fix program, which answered `['<pid>',
  '0']` to each: the pid file carries no `0` start field the instant the
  spawner returns, and the worker's own stamp appears within the pause.
  The second reproduced defect (2) directly — the placeholder had won the
  race permanently in that run. Why it was missed, from the applying
  session's record: it proposed the one-writer form itself and had it
  ruled, then at application fixed only the start-time token that `ps` had
  broken, treated the spawner's placeholder as fixed ground while doing
  so, and wrote its identity-guard case to assert that the worker's stamp
  *beats* the placeholder — pinning the happy-path outcome of the very
  race the ruling deleted. It committed that batch noting it was behind
  schedule and reached its context-recycle threshold three items later.
- APPLIED 2026-08-12 (`cb582d6`) — **Version floors are met by upgrading
  hosts, not by lowering the floors.** The suite asserts Python ≥ 3.12 and
  git ≥ 2.40. A stock macOS host meets neither: its system `python3` is
  3.9.6, and the program's type annotations require ≥ 3.10 to import at
  all, while Apple's shipped git is 2.39.5 — the sole failing case in
  every suite run performed during the review, an environment artifact
  rather than a code defect. The floors stand: macOS hosts in the fleet
  take a current Python and a current git (Homebrew or equivalent) rather
  than the program accommodating superseded versions. Applied as the
  ruling directs — nothing in the program changed — with one repair
  alongside: the suite's own git-version parse took the last token of `git
  version 2.39.5 (Apple Git-154)` and crashed the whole run on macOS
  before the floor could report. The ruling was then carried out on the
  Mac host 2026-08-13: `brew install git` put 2.55.0 ahead of Apple's
  2.39.5 on PATH and the git-floor case went green, leaving
  `user.useConfigOnly` as the suite's only failing case there. Python was
  already satisfied by an explicitly-invoked `python3.13`; the system
  `python3` remains 3.9.6, which matters for any caller that runs the
  program as plain `python3` rather than naming the interpreter.
- APPLIED 2026-08-12 (`cb582d6`, `cacd3b9`) and 2026-08-13 (the accepted
  reply, the specification correction) — **`status` and `cancel` are
  host-local, and say so.** The workspace lives under the
  local machine's state directory, keyed by digest, and nothing is shared
  between hosts, while the fleet runs agents on more than one machine — so
  a `--no-wait` submission on one host leaves its worker and its record
  there and nowhere else. From another host the history check still runs
  first, so work that already pushed answers `checked-in` correctly; work
  still in flight has no local workspace and answered `unknown — no trace
  of this digest; submit it, submitting is always safe`. That advice is
  wrong in this case: following it duplicates work running normally
  elsewhere. The duplicate is not dangerous — the atomic push arbitrates
  and the loser integrates — but it is waste produced by a confident wrong
  answer. `cancel` was worse: from another host it answered
  `unknown-request` while the worker ran on, so the standing ruling that
  any agent may cancel turned out to mean any agent on that host. Ruled
  fix, without new infrastructure: record the submitting host in the
  request and name it in the accepted reply and its next action, so the
  digest is handed out together with the machine it belongs to; and change
  the `unknown` next action to state that no trace exists *on this host*
  and that a request submitted elsewhere must be asked about there.
  Rejected: a shared workspace root on a network filesystem — its locking
  and partial-failure modes cost far more than the problem. Applied: the
  request record carries the host, and both absence replies scope
  themselves to this host. The accepted reply followed 2026-08-13: it reads
  `accepted <digest> on <host>`, and its next action names the host to run
  `status` on and why — the workspace, worker and refusal record live there
  and nowhere else. One case pins both fields, red against the pre-fix
  program. The specification correction was recorded as applied with the
  fix batch but had not in fact been made; it is applied now — the states
  section's "discoverable from the digest alone" holds only on the host
  that created it, and the reply contract and procedure both carried the
  hostless `accepted <digest>` form.
- APPLIED 2026-08-12 (the cases, across the seven fix commits) and
  2026-08-13 (the phase seam and the cases needing it) — **The regression
  set, and the phase seam it needs.** The 162-case suite caught
  none of the defects above, for two structural reasons worth recording
  rather than the individual gaps. It tests what the code does rather than
  what was ruled — the clearest case being the process-group kill: WALK-4
  exists because a worker may already have spawned `git push`, so killing
  only the recorded process leaves that child alive to push anyway, and
  the test parked the worker in a pause that runs *before* any git work
  begins, so no child existed at cancel time and replacing the group kill
  with a single-process kill left every cancel case green. And it never
  asserted the absence of damage: every destructive defect found here
  produced a successful-looking reply (`cancel` on an arbitrary path
  answers `cancelled`; a twin trampling a live worker answers `accepted`),
  and a test that checks only the reply passes. The missing half is always
  the second assertion — *and the thing that should not have been touched
  is still there*. Each case states its oracle and red condition in
  advance and must fail against the pre-fix program; written after the
  fix, several would pass vacuously. The eleven groups ruled: path safety;
  kill scope; cancel truthfulness; torn pid file; refusal record; twin
  claim; symlinks in both directions; repository resolution; advisory;
  identity guard; host locality. Roughly 25–30 cases. Ten of the eleven
  groups landed inside the seven fix commits above rather than as one
  batch, taking the suite 162 → 202. The eleventh, cancel truthfulness,
  waited on the named-phase seam, which was the ruled prerequisite and was
  not built at the time; both were built 2026-08-13. The seam
  (`worker_phase`, env `GATEKEEPER_TEST_WORKER_PAUSE_AT`) replaces the
  single pre-git sleep: the worker writes a `.reached-<phase>` file on
  arrival at `before-git`, `before-push` and `after-push`, and blocks at
  the one phase a test names until that test creates `.release-<phase>`.
  It is inert unless the variable is set. A companion variable,
  `GATEKEEPER_TEST_WORKER_IGNORES_TERM`, makes the held worker ignore
  SIGTERM; it stands in for the two ways a real worker outlives its
  cancellation — a `git push` child that survived a single-process kill,
  and a worker the canceller lacks permission to signal — neither of which
  is constructible from inside one test process. The two cases: a worker
  released inside cancel's ten-second SIGTERM wait pushes, and cancel
  answers `too-late` with the commit; and a workspace whose recorded worker
  is alive but unsignalable (pid 1, the case skipping itself where that pid
  *is* signalable, as when running as root) yields `cancel-failed`, exit 1,
  workspace left in place. Red conditions verified by mutation rather than
  against the pre-fix program, since the cancel fixes had already landed:
  removing the every-path history re-check turns the first case's answer
  into `cancelled`, and removing the post-kill liveness confirmation does
  the same to the second — the exact false `cancelled` the ruling exists to
  prevent. Still unwritten: the host-locality case.
- APPLIED 2026-08-12 (the git-version parse and the `finally` reaping) and
  2026-08-13 (the rest) — **The harness synchronises by handshake, fails
  soft, and reaps what it spawns.** Three weaknesses in the test
  harness itself, independent of what it covers. It makes a timing bet:
  the refusal-record and liveness cases must fit a `status` invocation, a
  full second check-in and a rival's git work inside a three-second worker
  pause — measured at roughly 0.6 seconds of work, about five times margin
  on an idle machine, which a cold filesystem cache, a loaded CI host, a
  networked state directory or antivirus scanning git objects consumes;
  when the pause wins, assertions invert quietly (`in-progress` becomes
  `checked-in`). One broken case ends the run: two helpers raise rather
  than recording a failure — the git wrapper on a non-zero exit, and a
  bare JSON decode on empty output — and neither is caught by the case
  recorder, so they unwind the whole harness; this surfaces as a traceback
  and a non-zero exit rather than a false green (observed twice during the
  review, via the git-version floor), but the cases that never ran leave
  no trace, and a traceback arriving after a hundred passes reads as an
  environment hiccup rather than as a third of the suite not executing.
  And nothing reaps what it spawns: no `try`/`finally` kills spawned
  workers, so on such an abort a paused worker outlives the suite with its
  state directory deleted underneath it. Ruled fix: synchronise by
  handshake rather than by sleeping, using the named-phase seam above, so
  the worker signals that it reached a phase and the test waits on that
  signal under a generous timeout — removing the race instead of widening
  it; make the helpers mark their case failed and let the run continue;
  reap spawned workers in a `finally`; and print the number of cases run,
  so a short run is visible on sight. The git-version parse that was
  crashing the run on macOS and the `finally` reaping around the
  worker-spawning cases landed with the fix batch; the rest landed
  2026-08-13 once the seam existed. The three-second and thirty-second
  worker sleeps are gone: a `wait_for` helper watches the seam's phase
  files, and the B4d case now releases the worker only after the rival's
  conflicting commit is on main, so the conflict it asserts is guaranteed
  rather than raced for. The `git` wrapper records a failed case and
  returns instead of raising, and every bare decode of a subprocess reply
  goes through `load_payload`, which answers `UNPARSEABLE` rather than
  raising. The run ends with the number of cases run, printed before the
  failure line. The value of that last part was immediate: building these
  cases collided a fixture digest with an existing one, and the resulting
  `FileExistsError` ended the run a third of the way through — visible on
  sight as a short count, invisible before.
- APPLIED 2026-08-12 (`6d356d2`) — **Document contradictions corrected
  with the fixes.** All introduced or left standing by PR #49, none
  needing a separate decision: the specification stated slice 4 is BUILT
  while its cancel section still read "slice 4, unbuilt today — see
  Implementation status", pointing the reader at the sentence that
  contradicted it; four code comments dated rulings 2026-08-12, the day
  they were applied, while the specification and this plan record
  2026-08-11, the day they were ruled (the parser docstring records it
  correctly, which establishes the convention); `codex-dispositions.md`
  opened "Walk pending: the WALK items and the FIX batch below await the
  user's rulings" while the body added by that PR declared "WALK COMPLETE
  2026-08-12"; the specification named `scripts/launch-claude` the
  "standing bit-holder" for the executable bit while twelve of fifteen
  tracked scripts carry it; and a `too-late` cancel returned before any
  cleanup, alone among cancel's endings, leaving the workspace on disk
  where every other branch sweeps it. The historical finding text quoting
  the old four-outcome wording was left as written: it is a record of what
  was found, not a live claim.
- APPLIED 2026-08-12 — **The fixes land before the merge.** Ruled
  reversing the reviewer's initial recommendation to merge first and fix
  forward. The reviewer's case: merging PR #49 would not put the
  gatekeeper in service — it is dormant, no host holds a main-capable
  credential, and activation waits on slice 6 — and the branch was an
  improvement on main for everything currently reachable, fixing the
  collidable digest framing, narrowing the symlink read escape, and
  carrying 23 verified specification corrections, while the defects it
  added lived entirely in slice 4, which nothing yet invokes. Rejected:
  "nothing invokes it yet" is exactly what allows a known destructive
  defect to sit until something does, and landing a `cancel` that deletes
  arbitrary directories leaves that commit in main's history for any
  future bisect or reader to walk into. The goal is a reliable system, and
  the fixes were being done regardless, so main never carries the defect.
  The corrected branch merges once the fixes and their tests are in;
  staging the destructive set (path, kill-scope, cancel-truthfulness,
  atomicity and claim fixes) ahead of the full regression set remained
  available if something needed main sooner. Enacted as ruled: the seven
  fix commits landed on choirmaster first, and nedschorus#49 merged to
  main afterwards as `9bd1335`.

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
3. **Does this build own the check battery?** Two documents disagree, and
   the disagreement is why nobody noticed the work was skipped.
   [nc-python-toolchain-plan.md](../cross-project/nc-python-toolchain-plan.md)
   § Phase 1 is headed "First pass (built with the gatekeeper, step 7)" and
   specifies `nc-checkin-quality-gate` — gitleaks plus `ruff check`,
   `ruff format --check`, `mypy` and `pytest`, run full-repo on every
   check-in, refusing with the tool's structured output nested in the
   gatekeeper's refusal (boss-ruled 2026-07-31). This plan never mentions
   it. Neither does the specification, nor the build bindings: `git grep -icE
   'ruff|mypy|pytest|gitleaks|nc-checkin-quality-gate|check battery' main --`
   over `docs/issues/3-git-gatekeeper-build-slice-plan.md`,
   `docs/cross-project/git-gatekeeper-design.md` and
   `docs/issues/queue/3-gatekeeper-build-bindings.md` returns zero hits in
   all three; the same query over `scripts/git-gatekeeper.py` also returns
   zero. Only the two toolchain documents name it. All five slices are
   built, so today the gate screens the request, builds the candidate and
   handles the race, and runs no style check, no type check, no test suite
   and no secret scan: a check-in that breaks every test in the repository
   is accepted. The ruling needed is which document governs — whether this
   build owns the battery (this plan gains a slice) or the binding has
   lapsed (the toolchain plan's Phase 1 heading is corrected). A related
   distinction the user raised 2026-08-14, already project doctrine as the
   toolchain plan's "code beats prompts": mechanically decidable checks are
   code and belong to the gate; correctness review is not mechanically
   decidable and belongs to the judgment layer with skills and reviews.
   Whichever way this is ruled, both tiers are currently absent from the
   program. Raised 2026-08-14 by new-vp; not choirmaster's decision to make.

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
