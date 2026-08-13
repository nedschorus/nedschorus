# git-gatekeeper — fix rulings from the PR #49 code review (2026-08-12)

Build rulings for nedschorus#3, taken while
https://github.com/nedschorus/nedschorus/pull/49 was open and unmerged. The
findings came from a code review of `choirmaster` at `3c418863` — the head that
built slice 4 (worker lifecycle: `--no-wait`, detached worker, `status`,
`cancel`). Each finding below was reproduced by running the program unless
marked otherwise.

This file exists as a separate document rather than as edits to
`docs/issues/3-git-gatekeeper-build-slice-plan.md` because that plan is modified
by the open PR; these rulings fold into its "Rulings from the user's review"
section once the PR lands, and this file is then retired.

## Ruled

### Caller-supplied digests must never build a filesystem path

**Ruled 2026-08-12. Supersedes the first proposal (format validation), which the
user rejected as machinery without a consumer.**

Defect: `require_digest` accepts any non-empty string, and `status`, `cancel`,
and `run_worker` each build `workspace_root() / digest` from it. Because joining
an absolute path discards the root, and `..` resolves normally, a caller-named
path outside the workspace root is reachable. `cancel` then deletes it
recursively and answers `cancelled — the workspace is swept; nothing reached
main`, exit 0. Demonstrated: `cancel <absolute path>` removed a directory and
its contents; `cancel ../../victim` did the same once the workspace root existed;
`status ../../secret` returned a foreign `refusal.json` verbatim as the
gatekeeper's own refusal reply and then deleted the directory. After C2 the
program runs as the dedicated gatekeeper user via sudo, so the caller chooses the
path and the gatekeeper's privileges perform the deletion — including against
that user's own credential and state directories.

Fix: locate a workspace by enumerating the workspace root and matching an entry
whose name equals the digest. Never join caller-supplied text onto a path. A
string that matches nothing answers `unknown-request`. Escape is then impossible
by construction rather than by filtering, and only entries the program itself
created are ever acted on. Applies in all three places: `status`, `cancel`, and
`run_worker`.

Explicitly not done: a `^[0-9a-f]{64}$` format check. Under the enumeration fix
it changes no outcome — its only effect is a more specific error string — and the
project cuts machinery whose findings have no consumer (the same reasoning that
deleted the trailer-absence audit, ruled 2026-08-10).

Note recorded with the fix: `worker` is a real, `--help`-listed subcommand, so
its path build is caller-reachable too. It only reads there, so the exposure is a
foreign `request.json` rather than a deletion; it takes the same lookup, or it
stops being caller-reachable.

### A process group is killed only when the recorded pid leads it

**Ruled 2026-08-12.**

Defect: `worker.pid` is written above the `--no-wait` branch, so in the default
waiting mode it records the caller's own pid. That process was not started with
`start_new_session`, so its process group belongs to whatever launched it — the
agent's shell, harness, or pipeline. `cancel` reads the pid and calls
`os.killpg(os.getpgid(pid), SIGTERM)`, signalling every process in the caller's
group. Demonstrated: a launcher process started an unrelated `sleep` and a
waiting check-in held open by a stalled push; `cancel <digest>` answered
`cancelled`, exit 0, and killed the launcher, the unrelated sleep, and the
check-in — the caller never received a reply because its harness died first.
Reachable without malice: a twin submission of identical work returns the first
request's digest to the second agent, and any agent may cancel (no permission
machinery, ruled).

Fix: group-kill only when `os.getpgid(pid) == pid` — true exactly for the
detached worker, which is spawned `start_new_session=True` and so leads its own
group, and false for a foreground caller. The kernel answers the question; the
program does not record a "this one was detached" flag and trust its own note,
because the pid record is precisely the data that goes stale, tears, or names a
recycled process.

Behavior ruled for the other branch: when the recorded pid does not lead its own
group — a check-in running in an agent's foreground — `cancel` signals that
single process rather than refusing. Cancel then behaves uniformly in both modes,
which is simpler to teach and consistent with the standing ruling that any agent
may cancel; the wait-then-ask-history sequence still produces a truthful outcome.

Kept deliberately: `worker.pid` is still written in both modes. Twin detection
depends on it — a second agent submitting identical work discovers the live
sibling through that record and is answered `in-progress` instead of trampling
it.

### `cancel` confirms the kill and re-asks history on every path, and gains a fifth outcome

**Ruled 2026-08-12. Amends the design's "Outcomes, exactly four" to five.**

Two defects put a false `cancelled — the workspace is swept; nothing reached
main` in front of callers.

First, the ruled kill-wait-then-ask-history sequence runs only on the branch
where a live worker is found. When the worker is already gone — it pushed and
died, or completed its own sweep — `cancel` answers from the history check made
*before* the wait. Demonstrated: a worker's push landed inside that window;
`cancel` answered `cancelled — nothing reached main`, exit 0, and `status` on the
same digest one second later answered `checked-in 7ac9a7e`. When the worker also
swept itself first, `cancel` instead answers `unknown-request — no trace of this
digest` for work that just reached main.

Second, nothing confirms the kill. After the SIGTERM and SIGKILL waits, control
falls through to `cancelled` with no liveness re-check; both `killpg` calls
swallow every error, and `worker_state` deliberately reads permission-denied as
*alive* — the normal case once C2 puts the worker under the dedicated gatekeeper
user. Demonstrated against a process this user cannot signal: 15.2 seconds spent,
nothing signalled, workspace deleted, answer `cancelled — nothing reached main`,
while the worker ran on free to push.

Third, smaller: the post-SIGKILL wait reuses the already-expired SIGTERM
deadline, and both waits use wall-clock time, so a forward clock step skips the
second wait entirely.

Fix: one exit path for `cancel`. Whatever killing happened, confirm the process
is gone, re-ask history, then answer. Each wait gets its own deadline computed
from a monotonic clock.

That produces a state the catalog had no word for — the worker outlives SIGKILL,
so the gatekeeper neither stopped it nor knows the outcome. A fifth outcome is
added rather than forcing a false `cancelled`:

```json
{"outcome": "cancel-failed",
 "facts": "worker 4123 is still alive after SIGTERM and SIGKILL: permission denied",
 "next_action": "Check status <digest> shortly; the worker may still push. If it persists, the workspace owner must kill it."}
```

The design's cancel section is updated from four outcomes to five.

### `worker.pid` is written atomically, and death requires positive evidence

**Ruled 2026-08-12.**

Defect: every writer truncates `worker.pid` in place, and every reader treats an
unreadable or unparseable file as proof the worker is dead. Between those lies a
window in which the file is empty on disk while the worker is alive.
Demonstrated by emptying the file under a live worker: `status` answered
`abandoned — workspace present, worker dead; resubmit safely`; a twin submission
took the dead path, deleted the live worker's candidate clone and its declared
snapshot, and spawned a second worker on the same digest; the first worker then
died reading its own declared bytes with output at `/dev/null`, leaving no
refusal record and no trace. Mid-push, the clone would have been deleted under a
running `git`. A related crash path: if the file is torn between the read at the
top of `cancel`'s kill block and the later escalation, `pid` is unbound and the
`NameError` escapes the caught exception tuple as a program defect.

Fix, two parts. Write the file to a temporary name and rename it into place, so a
reader sees either the old contents or the new and never an empty file. Then stop
inferring death from silence: an unreadable or unparseable pid file means
*unknown*, and unknown is treated as alive — not swept, not trampled, no rival
worker spawned. Only a confirmed process-not-found means dead.

The asymmetry decides the default. Guessing "alive" wrongly leaves a stale
directory that the age-based sweep collects later. Guessing "dead" wrongly
destroys work in flight and loses its reason silently.

### The retained refusal record is written before anything is demolished, atomically, and is never swept unread

**Ruled 2026-08-12.**

Defect: `retain_refusal_record` deletes `worker.pid` and `request.json` first,
then writes `refusal.json` in place. That record is the caller's only route to a
detached refusal's reason — the design deliberately keeps no other copy — and two
windows destroy it. A `status` arriving after the deletions but before the write
sees no record and no worker, so it answers `abandoned — resubmit safely` for a
request that in fact refused with a real reason. A `status` arriving mid-write
finds the file present but empty, fails to parse it, fabricates a generic
`workspace-io-error — record unreadable`, and then deletes the whole workspace
anyway; the real reason is gone permanently and the worker's own write fails into
an unhandled `OSError`. Both reproduced. Separately, two concurrent `status`
calls each received the full record, though the design states it is returned once
and then swept.

Fix, three parts. Write the record before removing the candidate clone and pid
file — never demolish the old state before the new state exists. Write it to a
temporary name and rename it into place. And never sweep a record that could not
be read: an unparseable record is unknown, not spent, and is left for a retry.
The "returned once" property is enforced by claiming the record with an atomic
rename, so exactly one concurrent caller wins it.

### The workspace is claimed by creating it, and a worker without a request leaves a reason

**Ruled 2026-08-12.**

Defect: `check_in` tests whether the workspace is occupied, then creates it, then
stamps it live. A twin submission arriving between the creation and the stamp
sees a directory with no pid file, concludes the owner is dead, and deletes the
live sibling's request record and candidate clone — the exact case the twin-
detection ruling exists to prevent. The damage is silent: the victim's
`shutil.move` does not raise, because CPython falls back to `copytree`, which
recreates the missing parent, so the workspace reappears holding only a partial
clone. On a `--no-wait` submission the caller is answered `accepted <digest>`
while the spawned worker finds no `request.json`, returns the defect exit code
with output at `/dev/null`, and records nothing. The request never runs, never
pushes, and never explains itself; `status` later reports `abandoned`.

Most of this window is closed by the ruling above — a missing or unreadable pid
file now means unknown and is treated as alive, so a twin no longer tramples.
Two changes remain.

The claim becomes the creation: the workspace directory is created
unconditionally and a failure because it already exists *is* the signal that
another submission owns it. That removes the check-then-act gap rather than
narrowing it.

And a worker that cannot find its request retains a refusal record saying so,
now that records are written safely, instead of exiting silently into the defect
code with no reply channel.

### The symlink boundary is enforced symmetrically, on both sides and every component

**Ruled 2026-08-12. Widens WALK-1 (user-ruled 2026-08-11), which was recorded
APPLIED covering the read side's leaf component only.**

The specification states the boundary plainly — "a link's target can live outside
the repository, and the security boundary does not follow it" — and neither
direction delivers it.

Reading: the shipped check tests only a declared path's final component. With
`esc` a symlink to a directory outside the repository, declaring `esc/secret.txt`
passes every screen (no `..`, not absolute, printable ASCII) because the leaf is a
regular file reached *through* the link; its bytes are read from outside and
checked in to main. Reproduced independently by three reviewers.

Writing: unchecked entirely, and worse. The candidate commit is built by checking
out main and writing declared bytes over it, so a symlink carried in **main's own
tree** at a declared path is recreated in the candidate clone and the write
follows it out of the repository. Demonstrated: a file outside every repository
was overwritten with the caller's content. The caller's worktree is innocent in
this case — the link lives in main — so no check on the caller's files can catch
it.

Fix, one rule applied symmetrically: a declared path must be a regular file or
absent on both sides of the comparison — the caller's worktree and the base tree
— and no component of it may be a symlink on either side.

Rejected as the primary form: resolving the path and asserting containment inside
the repository. Used instead of the per-component check it would silently reverse
WALK-1, because a symlink whose target sits inside the repository passes
containment while the ruling refuses it. Containment may sit behind the
per-component check as a second assertion only if it is shown to catch something
the first does not.

Two attachments. A base-tree symlink gets a named refusal rather than the generic
`workspace-io-error` whose next action reads "Resubmit the same request; this
class of failure is safe to retry" — the caller did nothing wrong, cannot fix it
by resubmitting, and each retry repeats the out-of-repository write; the honest
reply names the path, states that main carries a link there, and points at who
can change main. And the scope sentence this PR adds ("The caller's files and
main are untouched. Scoped exactly (2026-08-12): …") is corrected, since writing
bytes outside every repository appears nowhere in its enumeration.

### `status` and `cancel` answer from the request's own remote, and never assert absence after a failed fetch

**Ruled 2026-08-12.**

Two defects let a confident answer rest on nothing.

`check_in` records the request's remote in `request.json` and nothing reads it
back; `status` and `cancel` resolve a repository from `--repo` or the caller's
current directory instead. The accepted reply teaches `git-gatekeeper.py status
<digest>` with no `--repo`, so run verbatim from a directory that is not a git
repository it answers `malformed-field — not inside a git repository`, which is
not among the five outcomes the design lists for `status`; run inside a
repository with a different origin, checked-in work answers `unknown` and
`cancel` answers `cancelled` for work already on main. The suite always passes
`--repo` explicitly, so the taught command is never the tested one.

And the history fetch runs with failure ignored, so an unreachable remote or
expired credentials leaves the search reading a stale local copy: `cancel`
asserts `nothing reached main` while the commit sits on the remote, and `status`
answers `unknown — no trace of this digest; submit it`.

Fix: resolve the repository from the request record when the workspace exists;
make the taught next action a command that works as written; and on fetch failure
answer `network-down`, already in the catalog and already documented as safely
resubmittable, rather than asserting absence.

Distinction preserved deliberately: swallowing a failed fetch remains correct for
a check-in's base computation, where the specification rules the degradation
tolerable and the behind-main integration absorbs it. It is not tolerable here,
because in `status` and `cancel` the fetch decides whether the answer is true.

### The two exemptions from the one-JSON-object contract are written down, and agent-facing text stops citing `--help`

**Ruled 2026-08-12.**

The reply contract states that every invocation prints exactly one JSON object on
stdout, and reserves exit 2 for a program defect. Two invocations break it.

`worker` is a real, `--help`-listed subcommand whose every path prints nothing;
invoked without a request it produces zero bytes on stdout, zero on stderr, and
exit 2 — the defect code — for what is a caller's mistake. Its docstring states
the intent ("Never prints; the reply channel is the workspace") but never
reconciles it with the contract, and nothing prevents a caller reaching it.
`--help` prints usage text and exits 0: the parser wrapper added by this PR
converts argparse *errors* into JSON refusals, as WALK-2 ruled, and does not
touch the help path.

Neither is made to emit JSON — help text as JSON serves no one, and the worker
genuinely has no listener, its reply channel being the workspace by design. What
was missing is that the contract names no exceptions at all.

Fix: state both exemptions in the specification — `--help` is the human lane, and
`worker` is an internal re-entry the program makes into itself rather than a
caller-facing subcommand. Suppress `worker` from `--help` so the caller-facing
surface matches the caller-facing contract. And remove the `--help` citation from
the parser refusal's next-action text, which currently directs a JSON-consuming
caller to the one command that returns no JSON; it cites the specification path
instead.

The exit code ceases to matter here: a request-less worker now leaves a refusal
record under the ruling above.

### The undeclared-changes advisory names real files

**Ruled 2026-08-12.**

Defect: widening the advisory to see untracked files fed `??` entries into a
parse written for tracked changes. Git collapses a wholly-new directory into a
single entry, so a check-in declaring `newdir/new.txt` is told `advisory: the
working copy also differs at newdir/; confirm intentional` — the advisory names
the caller's own declared work and sends an agent to investigate a change it just
made deliberately (reproduced). The same collapse defeats the widening's stated
purpose, since a genuinely forgotten new file inside a new directory is never
named either. And untracked filenames are arbitrary, unlike declared paths, which
are screened: names carrying spaces or non-ASCII bytes are returned quoted and
escaped, so the advisory reports a string that is not a path.

Fix: `git status --porcelain -z --untracked-files=all`. The `-z` form is
NUL-delimited and disables quoting; `-uall` names actual files instead of
collapsing to the directory. The exact-match filter against declared paths then
works, and the widening delivers what it promised.

Accepted cost, uncapped for now: `-uall` enumerates every untracked file rather
than stopping at a directory, so a repository carrying a large un-ignored
untracked tree pays more and produces a longer advisory string. No truncation
rule is built until a real case appears. Worktree hygiene — which files should be
ignored rather than reported at all — is tracked separately as nedschorus#50.

### The worker-identity guard works on macOS and Linux alike, and has one writer

**Ruled 2026-08-12. The fleet runs agents on both macOS and Ubuntu, so a
host-dependent safety property is not acceptable.**

The design names a residual and its mitigation: a recycled process id could
masquerade as a live worker, so slice 4 records the worker's start time beside its
pid and `status` checks both. The code records it, and three defects stop it
working.

`process_start_time` reads `/proc/<pid>/stat` only. On macOS that path does not
exist, so it returns an empty string for every process, the reader falls back to
the placeholder, and the comparison is skipped — the guard is dead code on that
half of the fleet while working normally on the other half, with nothing
announcing which behaviour a given host has. The suite cannot detect the
difference: its only pid fixture is a hand-written placeholder, and no case
asserts a start time is ever captured or ever effective.

The write ordering is an unsynchronised race. The worker's loop claims to yield to
the spawner's placeholder write, but it waits for `worker.pid` to *exist* and the
spawner created it before launching, so the loop returns immediately and the two
writes race; the placeholder can land last and win permanently.

And a worker that dies before stamping — spawn failure, out-of-memory, an early
kill — leaves the placeholder in place forever. The reader explicitly skips the
comparison when it sees a placeholder, so that workspace's guard is off for good
and a later `cancel` group-kills whatever now owns the recycled pid.

Fix: one writer, and a portable reader. The spawner writes no placeholder; the
worker writes the pid file as its first act, and the gap before it does is covered
by the ruling above that a missing pid file means unknown and is treated as alive.
Start time is read portably — `ps -o lstart= -p <pid>` where `/proc` is absent —
so the guard behaves identically on both platforms.

### Version floors are met by upgrading hosts, not by lowering the floors

**Ruled 2026-08-12.**

The suite asserts Python ≥ 3.12 and git ≥ 2.40. A stock macOS host meets
neither: its system `python3` is 3.9.6, and the program's type annotations
require ≥ 3.10 to import at all, while Apple's shipped git is 2.39.5 — the sole
failing case in every suite run performed during this review, an environment
artifact rather than a code defect.

The floors stand. macOS hosts in the fleet take a current Python and a current
git (Homebrew or equivalent) rather than the program accommodating superseded
versions.

### `status` and `cancel` are host-local, and say so

**Ruled 2026-08-12.**

The workspace lives under the local machine's state directory, keyed by digest,
and nothing is shared between hosts. The fleet runs agents on more than one
machine, so a `--no-wait` submission on one host leaves its worker and its record
there and nowhere else.

From another host the history check still runs first, so work that already
pushed answers `checked-in` correctly. Work still in flight has no local
workspace and answers `unknown — no trace of this digest; submit it, submitting
is always safe`. That advice is wrong in this case: following it duplicates work
running normally elsewhere. The duplicate is not dangerous — the atomic push
arbitrates and the loser integrates — but it is waste produced by a confident
wrong answer. `cancel` is worse: from another host it answers `unknown-request`
while the worker runs on, so the standing ruling that any agent may cancel turns
out to mean any agent on that host.

Fix, without new infrastructure: record the submitting host in the request and
name it in the accepted reply and its next action, so the digest is handed out
together with the machine it belongs to; and change the `unknown` next action to
state that no trace exists *on this host* and that a request submitted elsewhere
must be asked about there.

Rejected: a shared workspace root on a network filesystem. Its locking and
partial-failure modes cost far more than the problem.

Specification correction: the states section describes the workspace as
"discoverable from the digest alone", which holds only on the host that created
it.

### The regression set, and the phase seam it needs

**Ruled 2026-08-12.**

The 162-case suite caught none of the defects above, for two structural reasons
worth recording rather than the individual gaps.

It tests what the code does rather than what was ruled. The clearest case is the
process-group kill: WALK-4 exists because a worker may already have spawned `git
push`, so killing only the recorded process leaves that child alive to push
anyway — and the test parks the worker in a pause that runs *before* any git work
begins, so no child exists at cancel time and replacing the group kill with a
single-process kill leaves every cancel case green.

And it never asserts the absence of damage. Every destructive defect found here
produced a successful-looking reply: `cancel` on an arbitrary path answers
`cancelled`, a twin trampling a live worker answers `accepted`. A test that
checks only the reply passes. The missing half is always the second assertion —
*and the thing that should not have been touched is still there*.

Prerequisite: a test seam that pauses the worker at a **named phase**, rather
than the single pre-git pause that exists today. Several cases below cannot be
written without it.

Each case states its oracle and red condition in advance and must fail against
the pre-fix program; written after the fix, several would pass vacuously.

- **Path safety** — `cancel` and `status` given an absolute path and a `../..`
  path answer `unknown-request`, and the named directory still exists afterwards.
- **Kill scope** — a recorded pid that does not lead its group receives a
  single-process signal, and a sibling in that group survives.
- **Cancel truthfulness** — a worker pushing inside cancel's wait yields
  `too-late`; a worker surviving SIGKILL yields `cancel-failed`. Both need the
  phase seam.
- **Torn pid file** — an empty or garbage `worker.pid` under a live worker
  reports `in-progress`, not `abandoned`, and a twin does not delete the clone.
- **Refusal record** — a `status` racing a half-written record leaves it intact;
  an unparseable record is not swept; two concurrent `status` calls produce
  exactly one delivery.
- **Twin claim** — simultaneous identical submissions give one `accepted` and one
  `in-progress`, both workspaces intact.
- **Symlinks, both directions** — an ancestor symlink refuses on read; a
  base-tree symlink refuses with its named code, and the outside file's bytes are
  unchanged.
- **Repository resolution** — `status` from a repository with a different origin
  does not answer a false `unknown`; an unreachable remote answers `network-down`
  rather than absence.
- **Advisory** — a declared new file in a new directory produces no advisory; a
  forgotten file inside a new directory is named; a filename containing a space
  is reported as a real path.
- **Identity guard** — a real start time is captured on the running platform and
  a mismatched one reads as dead; passes on macOS and Ubuntu alike.
- **Host locality** — a digest recorded against another host is reported as such.

Roughly 25–30 cases.

### The harness synchronises by handshake, fails soft, and reaps what it spawns

**Ruled 2026-08-12.**

Three weaknesses in the test harness itself, independent of what it covers.

It makes a timing bet. The refusal-record and liveness cases must fit a `status`
invocation, a full second check-in, and a rival's git work inside a three-second
worker pause. Measured here at roughly 0.6 seconds of work — about five times
margin on an idle machine — which a cold filesystem cache, a loaded CI host, a
networked state directory, or antivirus scanning git objects consumes. When the
pause wins, assertions invert quietly: `in-progress` becomes `checked-in`.

One broken case ends the run. Two helpers raise rather than recording a failure —
the git wrapper on a non-zero exit, and a bare JSON decode on empty output —
and neither is caught by the case recorder, so they unwind the whole harness.
This surfaces as a traceback and a non-zero exit rather than a false green
(observed twice during this review, via the git-version floor), but the cases
that never ran leave no trace, and a traceback arriving after a hundred passes
reads as an environment hiccup rather than as a third of the suite not
executing.

And nothing reaps what it spawns: there is no `try`/`finally` killing spawned
workers, so on such an abort a paused worker outlives the suite with its state
directory deleted underneath it.

Fix: synchronise by handshake rather than by sleeping — with the named-phase seam
above, the worker signals that it reached a phase and the test waits on that
signal under a generous timeout, removing the race instead of widening it; make
the helpers mark their case failed and let the run continue; reap spawned workers
in a `finally`; and print the number of cases run, so a short run is visible on
sight.

### Document contradictions corrected with the fixes

**Ruled 2026-08-12.** All introduced or left standing by PR #49, none needing a
separate decision:

- The specification states slice 4 is BUILT, while its cancel section still reads
  "slice 4, unbuilt today — see Implementation status", pointing the reader at the
  sentence that contradicts it.
- Four code comments date rulings 2026-08-12, the day they were applied; the
  specification and slice plan record 2026-08-11, the day they were ruled. The
  parser docstring records it correctly, which establishes the convention.
- `codex-dispositions.md` opens "Walk pending: the WALK items and the FIX batch
  below await the user's rulings" while the body added by this PR declares "WALK
  COMPLETE 2026-08-12".
- The specification names `scripts/launch-claude` the "standing bit-holder" for
  the executable bit; twelve of fifteen tracked scripts carry it.
- A `too-late` cancel returns before any cleanup, leaving the workspace on disk
  where every other branch sweeps it.

### The fixes land before the merge

**Ruled 2026-08-12, reversing the reviewer's initial recommendation to merge
first and fix forward.**

Merging PR #49 would not put the gatekeeper in service — it is dormant, no host
holds a main-capable credential, and activation waits on slice 6 — and the branch
is an improvement on main for everything currently reachable: it fixes the
collidable digest framing, narrows the symlink read escape, and carries 23
verified specification corrections. The defects it adds live entirely in slice 4,
which nothing yet invokes.

That reasoning supported merging first, and it was rejected: "nothing invokes it
yet" is exactly what allows a known destructive defect to sit until something
does, and landing a `cancel` that deletes arbitrary directories leaves that
commit in main's history for any future bisect or reader to walk into. The goal
is a reliable system, and the fixes are being done regardless, so main never
carries the defect.

The corrected branch is merged once the fixes and their tests are in. Staging the
destructive set (the path, kill-scope, cancel-truthfulness, atomicity and claim
fixes) ahead of the full regression set remains available if something needs main
sooner.
