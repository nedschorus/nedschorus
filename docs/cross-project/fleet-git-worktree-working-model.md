---
status: ruled — produced at the close of the git/worktree rules walk
  (2026-08-17/18); every rule disposition below was user-ruled item by
  item (the State-at-close candidates are recorded, not ruled).
  Streamlined 2026-08-20 on the user's ruling: mechanism prose removed in
  favor of script citations; the full original text is this file's git
  history.
scope: fleet-wide — both machines, every seat, and the two agent runtimes,
  Claude Code and Codex
supersedes: the machine-local walk ledgers named under Provenance, which are
  deleted once this document is verified on main
---

# Fleet git and worktree working model

The ruled working model for how this project's agent fleet uses git: which
directory a session works in, whose directories it may touch, how work
reaches main, how landed changes reach running seats, and what makes most
damage recoverable when noticed in time. The dispositions and dates below
are the user's rulings. Where a ruling shipped code, the pull request is
named; where it deliberately built nothing, the reason and the revisit
trigger are stated — an unbuilt rule here is a decision, not an omission.

What this document deliberately does not do: describe how the named
scripts work. A sentence here must stay true when a script is rewritten
tomorrow; how a script satisfies its rule today is readable at the cited
path. This boundary is itself a ruling (2026-08-20), made after three
mechanism descriptions in this document went stale within hours of
passing review.

## Reader's key

- **The user / the boss** — the same person: the project's one human
  operator.
- **The two machines** — the user's Mac (user `el`) and `ned-box` (Ubuntu,
  user `nedlern`), each with its own clone. Path map:
  `docs/cross-project/fleet-machine-paths-and-checkouts.md` (flagged stale
  2026-08-17; verify before relying on specifics).
- **Seat** — a named, long-lived agent identity: home directory, own
  branch, brief. **Session** — one running conversation occupying a seat;
  sessions end and are replaced, the seat persists. **Recycle** — the
  supervisor replacing a session with a fresh one, carrying the handoff
  forward. Definitions of record: `docs/agents/agent-seat-model.md`.
- **The reference checkout** — the machine's checkout that supervisors and
  launchers run from and other agents read expecting main. A standalone
  clone is its own workspace, never "the reference" — where any mechanical
  test disagrees with that definition, the definition governs (pinned
  2026-08-17). The test the guards use lives in the guard scripts.
- **Walked approval** — the user's approval given item by item, not one
  yes to a bundle (`docs/agents/agent-seat-model.md` § The words this
  model uses).
- **The gatekeeper** — `scripts/git-gatekeeper.py`, the permanent single
  door to main; specification `docs/cross-project/git-gatekeeper-design.md`
  (canonical for everything gate-related, including credential ruling C2:
  the credential able to push main belongs to a dedicated system user,
  reached only through a controlled, logged door). Dormant until its
  credential work lands.
- **The interim lane** — until the gate activates: seats commit on their
  own branch, ship each topic as a small atomic PR cherry-picked onto a
  fresh branch from main, and the merge-lane seat reviews and merges every
  PR (deputization, recorded at R13, is the ruled exception). Recorded in
  CLAUDE.md's lane paragraph.
- **The override markers** — `.walk-approved` (instruction-file guard) and
  `.location-write-approved` (session-location guard), both gitignored,
  each by convention holding the user's quoted approval words, consumed by
  the one guarded call it approves (see Marker honesty).
- **The launchers** — `scripts/launch-claude-mac` and
  `scripts/launch-claude-ubuntu`.
- **#N** — nedschorus's GitHub tracker; issue or pull request is labeled
  at first use per row.

## Scope

Rules about git, worktrees, sessions, seats, and machines, plus the
enforcement programs that implement them. Deliberately excluded: workflow
governance content (md-review's cells, ghi-write's routing, walk conduct),
prose-quality rules, and communication conventions. Coverage is bounded by
the sweep that built the inventory — the per-seat briefs
(`docs/agents/*-instructions.md`), `docs/cross-project/fast-handoff-design.md`,
and seat `CLAUDE.local.md` files were not swept.

Reach, so nothing below is assumed to protect more than it does: every
enforcement program in this document is a Claude Code feature, registered
in Claude Code's settings and running only inside Claude Code sessions. A
Codex invocation gets none of that machinery; it is bound only by what it
reads and by GitHub's branch protection, which binds everyone. No work is
planned to extend the guards to Codex. R26 alone is designed for both
runtimes from the start.

## The enforcement ladder

A *rule* is a do-or-not-do instruction expressed as text; an *enforcement
program* is code that enforces one (user-ruled vocabulary, 2026-08-17).
The ladder orders mechanisms by when they act, earliest first — not by
resistance to evasion: a block acts before the deed but can be blind to
some routes; detection acts after and sees routes a block is blind to.

1. **Impossible** — the bad state cannot arise without a deliberate
   override. Even rung 1 is "impossible by default": `git worktree add
   --force` and a second clone both defeat git's one-branch-one-worktree
   refusal.
2. **Default** — the right thing happens without anyone deciding.
3. **Block** — an enforcement program refuses at the moment of action
   (PreToolUse hooks). Known blind spot: a block on file-write tools does
   not see shell writes (R10 carries the ruling on that gap).
4. **Detect and reverse** — the unwanted action is noticed after the
   fact, undone, and the right way taught. Preconditions: an undo must
   exist, and the damage must not be consumed before detection — both
   argue for fast detection, not audits.
5. **Remind** — the program surfaces the rule at the moment it matters
   and proceeds.
6. **Text** — no enforcement; prose only. The waiting room: a do-or-not-do
   rule lives here only until mechanized (user-ruled 2026-08-17);
   governing principles (R17's, R28's) live here permanently by design.

Anchoring ruling, from the gatekeeper design: **CLAUDE.md is
documentation, never enforcement** — no program reads it, and different
machines may carry different copies.

## Standing rulings and principles

These govern every row below.

- **Prose yields to code** (user-ruled 2026-08-19): anything that can move
  from CLAUDE.md — or any instruction prose — into a small program should
  move, and never the other way. A check in code runs; a check in prose
  waits to be remembered.
- **A blocking guard carries an escape** (user-ruled 2026-08-17): a false
  fire must be *self-detecting* — the refusal names the file, the reason,
  and the fix — and *self-repairable*: either the consumed-marker lane
  passes one approved write, or the refusal itself teaches a repair that
  releases the block. A future block that cannot meet this bar is built
  as detect-and-report instead. The backup guard (R11) is the one ruled
  exception: its no-lane form is deliberate, and reading stays free so
  recovery is never blocked by it.
- **Gray-zone deciders**, per guard: the *program* decides mechanically
  (the gatekeeper); the *user* decides with the agent recording (the
  marker lane); or *no one* — the write is not the agent's to make
  (the backup guard). Fourth value, *nobody-now*: defer, valid only where
  a named later gate covers the case; no rule currently uses it.
- **Marker honesty**: a marker mechanism cannot verify whose words the
  marker holds or when approval was given — any non-empty marker passes.
  A guard's claimed strictness above that is carried only by its refusal
  text; the audit value is the visible quote in the marker and transcript.
  A marker lives at the root of the checkout it resolves from, is consumed
  at the guard's hook call, and persists unconsumed until a guarded call
  consumes it.
- **Silent safety is the enemy**: a conservative default must be
  distinguishable from a clean result, and a protection must be verifiable
  as actually in force.
- **Detection is the scarce half of undo**: git plus the snapshot stores
  can reverse most damage if noticed in time. Two carve-outs: content
  never committed that lived shorter than the host's snapshot interval is
  protected by neither store; and reversal restores artifacts, never
  consequences already drawn from them.
- **Rules are delivered at their trigger moment, not held in memory**
  (R28, re-ruled 2026-08-17): refusal text teaches at denial; boot reports
  teach when someone looks; the seat first-prompt teaches at birth.
  CLAUDE.md's rules section shrinking is the health signal — rules leave
  when mechanized; rationale lives in design documents like this one.

## The rules

Status vocabulary: **BUILT** marks code the walk shipped, with its pull
request named. **built-live** marks a mechanism already running before the
walk began.

### Q1 — Which directory am I in?

**R1. Enforcement programs resolve their roots correctly — resolvers FIXED
(PR #86, merged 2026-08-17); registration residue open.** Two questions
hide under "the root": which repository owns the target file, and which
checkout the session is in — the latter from the session's own working
directory, never from `$CLAUDE_PROJECT_DIR`, which names the wrong
checkout in forked sessions. User revision made at approval: override
markers resolve from the *session's own* checkout, not the target's;
target-derived resolution is only the fallback when the session sits in
no checkout. Open residue: the hook and status-line *registration* lines
in `.claude/settings.json` still resolve through `$CLAUDE_PROJECT_DIR` —
benign while all checkouts carry identical copies. A re-registration was
attempted and deliberately reverted (PR #103, 2026-08-19) after three
shell forms in one day, two wrong; the PR records all three forms and
their evidence for whoever settles it.

**R2. A session states and verifies its git context at start — satisfied
by composition (ruled 2026-08-17), nothing built.** The four facts of
issue #34 each have a delivery at least as good as a session-start print:
directory and branch on the status line (R5); the write blocks covering
the demonstrated wrong-place classes (R3, R6); the landing lane in
CLAUDE.md's ruled paragraph, the gatekeeper at activation, and branch
protection at push time. A session-start hook rides the same committed
repository as CLAUDE.md, so the print adds zero reach.

**R3. Detached HEAD or sitting in the reference checkout refuses writes —
BUILT (PR #88, merged 2026-08-17).**
`.claude/hooks/session-location-write-guard.py`, PreToolUse block on
Edit/Write/NotebookEdit; exception lane via `.location-write-approved`.
Scope, corrected 2026-08-19: the detached-HEAD test governs writes into
the session's *own* checkout; a write landing in the reference checkout is
R6+R7's block, which applies to any session however its HEAD is set.
Writes into another seat's home stay unbuilt (R6). The adjacent
*starting-stale* block was ruled **not built**: launch-time sync plus the
catch-up hook (R15) shrink exposure to one turn, and the motivating
incident was a stale *read*, which no write-guard sees. Revisit trigger: a real incident traced to
the one-turn window.

**R4. Stale base — absorbed (ruled 2026-08-17).** The original rule
(block first write on a stale base; warn when main moves mid-task; harden
at push) is superseded by R15's catch-up hook plus the Claude Code
runtime's own refusal to edit files changed since last read. Residues
assigned: starting-stale rides R3's ruling; push-time hardening rides the
gatekeeper permanently.

**R5. Status line shows the branch — ruled kept (2026-08-17, PR #89).**
`scripts/session-statusline-command.py`. Kept because shell git commands
pass no file-write guard — the line is that mistake's only always-on
visibility.

### Q2 — Whose directory is this?

**R6 + R7. No agent writes into the reference checkout — BUILT as a block
(PR #91, merged 2026-08-17).** The session-location guard's second
condition: a write *landing* in the reference checkout from a session
seated elsewhere is refused, same marker lane. Scoped to the demonstrated
class — all four recorded cross-checkout incidents targeted the reference.
The four, so the evidence outlives the walk papers: on 2026-08-14 a
session seated in its own worktree edited twelve documents and staged 235
deletions in the reference checkout; md-review records were later written
into it; a git branch was created in it, twice; and on 2026-08-15 a walk's
working ledger was written into it. Zero incidents targeted another seat's
home or a scratch worktree. Writes into
*another seat's* home are recorded-unbuilt with an incident as the build
trigger; a session's own scratch worktrees are deliberately untouched.
Block outranked detect-and-reverse because the undo is imperfect exactly
where damage is worst: a cross-checkout write over uncommitted work is
unrecoverable by git. R7 (the reference is a reference, never a bench)
rides this mechanism; the merge-lane seat's legitimate conflict edits pass
through the marker lane.

**R8. One live session per directory — waits on detection; build
nothing.** No detector yet meets the bar: it must classify attached
viewers, forked sessions, and background sessions correctly from each
session's own state.

**R9. One name = one seat; a handoff refuses a foreign claim — built-live
(PR #72, merged 2026-08-17).**
`scripts/handoff-write-and-check-supervisor.py`: handoffs stamp
`written-in:`; a writer whose directory differs is refused; `--claim`
overrides deliberately, the typed flag in the transcript being the audit
trail. The accident it kills: two same-name sessions overwrote a handoff
eleven seconds apart, first lost unread. Residuals: pre-#72 handoffs carry
no stamp; directory basenames are not globally unique across machines
(machine-suffixed names deferred — rider 5 in
`docs/issues/queue/45-session-seat-and-isolation-riders.md`). A seat's
*first* handoff is written by its provisioner from elsewhere, the guard
correctly refuses, and `--claim` is the sanctioned path.

**R10. Instruction-class files change only with walked approval —
built-live (root-resolution fixed by PR #86).**
`.claude/hooks/instruction-file-guard.py`: CLAUDE.md, per-seat
`CLAUDE.local.md`, and `.claude/` (minus `worktrees/` and `jobs/`) block
on write; approval quoted into `.walk-approved`. **The shell-write gap is
named and ruled unguarded** (2026-08-17): every recorded bypass was
accidental, not adversarial. Build trigger: an actually observed
shell-route bypass. A periodic drift sweep was rejected: it
false-positives on seats legitimately carrying approved-but-unmerged
changes. Codex has no instruction file in this repository today; if it
gains one, that file is not in this guard's list — a known fact, not a
decision.

**R11. Backup stores are read-only to agents — built-live; lane removed
(user-ruled 2026-08-17).**
`.claude/hooks/backup-and-snapshot-write-guard.py`: the Timeshift store
and configuration and Time Machine state refuse agent tool-writes
*unconditionally* — no marker lane; a real configuration need routes to
the user's keyboard. Rationale: an undo store agents can write is not
one. Reading stays free, so snapshot recovery is untouched. Precedent
(2026-08-18): the user may direct an agent's hands, in that agent's own
session, to paths outside the guarded class; the guarded paths stay
agent-unwritable.

### Q3 — How does work reach main?

**R12. Agents never push to main; one door — partial, hardened
2026-08-20.** Branch protection is live: pushes to main restricted to two
accounts — the user's own (`nedlern`, which authors) and
`ned-review-merge` (the merge seat's identity, which reviews and merges,
added 2026-08-19 so approval comes from a non-author); enforce-admins on;
force-push and deletion blocked; and, since 2026-08-20, **one approving
review is required for every merge** — enabled with the user present and
drilled live on PR #104. This is rung 1 at the account tier only: any
process holding either credential can push, so "agents never push" is
instructed, not impossible, until the gatekeeper's C2 credential design
lands. The restriction was proven live 2026-08-18 by a user-authorized
fence test (a non-allow-listed push refused with GH006 while an
unprotected control accepted the same credential and commit); the same
test established that a refused push leaves NO trace in the activity log
— a quiet log means nothing got through, never that nobody tried. The
gate's own program path was proven end to end 2026-08-18 (commit b24e376;
record at
`docs/cross-project/git-gatekeeper-first-live-check-in-record.md`) while
the gate stays dormant for daily work.

**R13. The interim lane — built-live (process); retired when the gate
activates.** Lives in CLAUDE.md's lane paragraph and
`docs/agents/seat-first-prompt.md` § Reaching main. **Deputization** is
the lane's recorded exception (ruled 2026-08-18, PR #93): the user may
instruct a specific seat, in that seat's own session, to merge a specific
PR; relayed words are hearsay and are refused — exercised before it was
recorded (a relayed instruction refused 2026-08-16; the user then deputized
directly for PR #72's merge).

**R14. One branch, one writer — satisfied by defaults (ruled 2026-08-17);
the old push-time check is retired.** An own-branch-only push check would
refuse the ruled atomic-PR lane. The residual hazard (two writers, one
branch) is covered by defaults with git's non-fast-forward refusal as
backstop; these are defaults, not guarantees — branch protection covers
main only. Push discipline as a whole becomes the gatekeeper's at
activation: a push is a shell operation no file-write hook sees.

### Q4 — How does a change reach a running seat, and what keeps seats alive?

**R15. A landed change reaches every running seat — BUILT (PR #87, merged
2026-08-17; delivery ruling PR #90).**
`scripts/checkout-freshness-catch-up.py` is the delivery; the status
line's `⇣N` shows the lag; the launchers freshen the reference checkout
at boot; the supervisor's launch-time sync remains the floor. Coverage
stated exactly: delivery happens at turn boundaries when the seat is
clean and conflict-free — a
seat that lags says so on its status line rather than silently. **Who
hears it** (ruled 2026-08-17): exactly one state forces an agent turn — a
conflict whose cleanup failed, leaving the tree mid-merge; routine events
stay display-plus-stamp. **Known structural finding, candidate fix
unruled:** the atomic-PR lane reliably produces add/add conflicts on files
a cherry-picked topic *created*. Manual remedy: `git status` to list,
`git checkout --theirs <file>` to take main's canonical version, `git
add`, commit. The candidate launch-reset of fully-merged seat branches
stays unruled (cherry-picks break ancestry, so the predicate needs care).

**R16. Binary updates at launch, never in background — built-live
(accreted, no single PR).** Both launchers update the binary at launch,
warn-and-proceed on failure; their guarantee is that *they* never swap it
under a live session. The box's `DISABLE_AUTOUPDATER=1` flag was
removed 2026-08-17 (dated backup beside it); issue #62's auto-update
theory was retracted. A launch-time version check is queued — State at
close.

**R17. Shared machinery lives in the repository, self-updating at safe
points — principle; two open gaps (recorded 2026-08-19).** The principle:
every deployed copy keeps itself current from its source at safe points
(launch, recycle, invocation), never by swapping under a live consumer.
The two gaps, each owned by named code: `launch-claude-mac` runs the
supervisor from whatever checkout it is invoked in, which need not be the
checkout that was freshened — whether the launcher *should* always
operate on the reference checkout is an open design question routed to
issue #45 (design pair:
`docs/issues/45-remote-named-agent-launch-and-reattach.md`); and a freshening that fails is reported nowhere, on either
launcher — the failure is recorded in a stamp file and nothing reads it
(owned by `checkout-freshness-catch-up.py --reference-pull`, not by the
launchers that call it). How each launcher wires freshening to launch is
the launchers' own business; read the scripts, not this paragraph.

**R18. Seat hosts are provisioned to survive disconnects — checklist
ruled (2026-08-17).** Per host: (1) on systemd hosts, `loginctl
enable-linger <agent-user>`, verified by an actual multi-minute gap, not
by reading the flag (the Mac has no linger equivalent; its seats ride the
desktop session); (2) a restore-one-file snapshot verification (done for
the box 2026-08-17; not yet for the Mac); (3) the host's snapshot cadence
per R19; (4) `lsof` present, for R21's vacancy check. Linger covers
logout-triggered kills; reboots and power loss fall to git and snapshots.
Completed and gap-verified for the box; the Mac has not been walked
through this list.

**R19. Snapshot cadence — ruled and LIVE (2026-08-17/18).** The box:
10-minute Timeshift snapshots via `/etc/cron.d/timeshift-10min`
(installed 2026-08-18, first tick verified), joining the auto-pruned
hourly ring — a ruled trade of ring depth for cadence, raisable at the
user's keyboard. Undo: delete the cron file. Applied by the git-infra
seat on the user's direct in-session instruction — `/etc/cron.d` is
outside R11's guarded class. The Mac stays at OS-default hourly: no
recorded Mac-side loss. What it buys, honestly: minutes-cadence never
reaches the seconds class (R9's guard closed that class).

**R20. The handoff channel preserves structure end to end — BUILT
(PR #108, merged 2026-08-20; fix ruled 2026-08-18).** Both ends: the
writer (`scripts/handoff-write-and-check-supervisor.py`) emits a
delimited multi-line block and the reader
(`scripts/handoff-supervisor.py`) parses it — a reader-only fix could not
have restored newlines already destroyed. The format specification, and
the exact-terminator trade it records, live in
`docs/cross-project/fast-handoff-design.md`, md-reviewed before the build
per design-first.

### Q5 — What piles up, and who sweeps it?

**R21. Session worktrees are reaped when clean, landed, and vacant —
built-live (PR #73); vacancy made provable (PR #100, merged 2026-08-19).**
`scripts/clean-worktrees.py`: anything failing or ambiguous is kept with
its reason; the launcher runs only the safe subset at boot; removal is a
separate deliberate call, never automatic. The posture it set,
reused across this model: mechanical predicates, ambiguity keeps, report
before remove. PR #100 closed the gap where an untrustworthy vacancy
answer read as vacant: vacancy is now proven by a usable answer or the
worktree is kept, with a reason that does not claim a process that was
never seen. `lsof` present at provisioning is R18's checklist line.

**R22. Untracked files classified; junk ignored by pattern — ruled closed
(2026-08-17; issue #50 closed).** The `.gitignore` is the living list —
new patterns as new junk classes are observed, each with its reason
beside it. The periodic cleanup script is not built; build trigger: a
real accumulation surfacing — then its first version reports and never
deletes. Unpromoted work is protected by exactly one net: commit it.

**R23. Agent scratch lives in the scratchpad — satisfied by a Claude Code
runtime default (ruled 2026-08-17).** The runtime names a per-session
scratchpad outside the repository in every system prompt. A remind-tier
hook on scratch-shaped writes stays a recorded candidate sharing R26's
hook-plus-config pattern.

**R24. Branch surveys fetch before they conclude — text, encoded into
R22's cleanup script when built.** Before concluding what exists or is
merged: `git fetch --prune origin` and read remote-tracking refs; a
survey that cannot reach the remote says so. Evidence: a prune list built
from unfetched refs missed four merged branches (2026-08-17).

**R25. Dead worktree registrations get surfaced — ruled (2026-08-18),
build queued.** A worktree registered under a temporary directory
(`/private/tmp` on macOS, `/tmp` on the box) leaves a dead entry when the
temp area clears, and `git worktree prune` is manual. The
`clean-worktrees.py` report gains one line naming dead registrations and
the prune command — report only; the prune stays deliberate.

**R26. New MDs land in approved homes — ruled-unbuilt (issue #11).** A
PreToolUse *remind* hook on MD writes outside the approved homes, symmetric
across both agent runtimes, one shared config — the repository root
`README.md` § "Where things live" becomes the single-source path list at
build time (known gap: it lacks `docs/agents/`). Remind, not block: MD
creation is overwhelmingly legitimate. Build trigger: a note landing
astray despite the queue rule. The hook-plus-config pair serves R23 and
R26 both — build once, configure twice.

**R27. Machine-local records stay out of commits — built-live (accreted
entry by entry).** `.gitignore` carries the walk-ledger, review-record,
marker, and `CLAUDE.local.md` patterns, each with its reason. Limit,
observed live: gitignore protects the repository, not the placement — a
file can still land in the wrong checkout (R6's business).

### Cross-cutting

**R28. Rules are delivered at their trigger moment** — see Standing
rulings; listed here to keep the numbering complete.

## Index

| # | Rule | Rung | Status at close |
|---|---|---|---|
| R1 | Guards resolve roots correctly | — (foundation) | fixed, PR #86; registration residue open (reverted attempt recorded in PR #103) |
| R2 | Session states its git context | — (composition of R3/R5/R6) | satisfied by composition |
| R3 | Detached/reference seat refuses writes | block | built, PR #88 |
| R4 | Stale base | — | absorbed by R15's catch-up |
| R5 | Status line shows branch | default | kept; separators fixed, PR #89 |
| R6+R7 | No writes into the reference | block | built, PR #91 |
| R8 | One live session per directory | — | waits on detection; build nothing |
| R9 | One name = one seat | default + block | built-live, PR #72 |
| R10 | Instruction files need walked approval | block | built-live; shell gap ruled unguarded |
| R11 | Backups read-only to agents | block (no lane) | built-live; lane removed |
| R12 | Agents never push to main | impossible (account tier) + text (agent tier) | partial; required reviews live 2026-08-20; C2 pending |
| R13 | Interim lane + deputization | text (process) | built-live; deputization in CLAUDE.md, PR #93 |
| R14 | One branch, one writer | default | satisfied by defaults; push check retired |
| R15 | Landed changes reach running seats | default + block (attention) | built, PRs #87/#90 |
| R16 | Binary updates at launch only | default | built-live; version check queued |
| R17 | Machinery self-updates at safe points | text (principle) | two open: Mac launcher runs the invoking checkout's supervisor; freshening failures are silent |
| R18 | Hosts survive disconnects | default | checklist ruled; box done |
| R19 | Snapshot cadence | default | live: box 10-min, Mac hourly |
| R20 | Handoff preserves structure | default | built, PR #108 |
| R21 | Worktrees reaped when safe | detect + remind | built-live, PR #73; vacancy proven, PR #100 |
| R22 | Junk ignored by pattern | default | ruled closed; issue #50 closed |
| R23 | Scratch lives in the scratchpad | default | satisfied by runtime default |
| R24 | Surveys fetch before concluding | text | encode into R22's cleanup script when built |
| R25 | Dead registrations surfaced | remind (report) | ruled; build queued |
| R26 | New MDs land in approved homes | remind | ruled-unbuilt, issue #11 |
| R27 | Machine-local stays uncommitted | default | built-live |
| R28 | Rules delivered at trigger | principle | governs all rows |

## State at close — queued work and recorded candidates

Depth convention (2026-08-19, set with the merge seat): each queued item
is a *work order* — what is wrong plus what correct behavior looks like,
built and reviewed directly against that statement — or *design-first*,
for changes that are coupled or fleet-critical: the design lands in the
document that owns the area and is md-reviewed before code. Every queued
PR's body states the intended behavior it should be reviewed against; the
merge seat reviews against that statement and posts its review on the
pull request.

1. **Guard and catch-up review fixes** — LANDED (PR #103, merged
   2026-08-19): fifteen of its sixteen entries, with the review
   discussions permanent on the pull request. The sixteenth — the hook
   re-registration (R1's residue) — was deliberately dropped, and stays
   open with all attempted forms recorded in that PR.
2. **R20** — the handoff both-ends structure fix — LANDED (PR #108,
   merged 2026-08-20; design section md-reviewed in
   `fast-handoff-design.md` first, per design-first).
3. **R25** — the dead-registration report line in `clean-worktrees.py` —
   queued.
4. **Launcher version check** (user-ruled 2026-08-17) — queued; settle
   first via the claude-code-guide agent whether the auto-updater and
   `claude update` respect `autoUpdatesChannel`. That answer decides
   build-or-close.

Recorded candidates, unruled — an incident or a user pick is the trigger:
the supervisor launch-reset of fully-merged seat branches (R15); R24's
logic encoded into R22's future cleanup script; R8's session detector;
machine-suffixed seat names (rider 5); other-seat-home write blocking
(R6's recorded-unbuilt half).

## Provenance

Produced at the close of the git/worktree rules walk (fifteen items,
2026-08-17/18, git-infra seat, the user ruling item by item). The walk
shipped PRs #86–#91 and #93 and closed issue #50. Its working papers —
`walk-ledgers/2026-08-17-git-worktree-rules-inventory.md` and
`walk-ledgers/2026-08-16-agent-worktree-git-coalesce-shape.md` — were
machine-local and gitignored, deleted once this document was verified on
main; everything they decided is restated here. This document depends,
deliberately, on three documents, each canonical for its own subject —
the gatekeeper design, the seat model, and the founding plan
(`docs/cross-project/nedschorus-founding-plan.md`).

Streamlined 2026-08-20 on the user's ruling, after the document's
mechanism prose was three times found stale against the code it
described: mechanism now lives in the cited scripts, and every cut
sentence remains in this file's git history. The rulings, dates, evidence
pointers, and open items above are complete — nothing ruled was dropped
in the cut.
