---
status: ruled — produced at the close of the git/worktree rules walk
  (2026-08-17/18); every rule disposition below was user-ruled item by
  item (the State-at-close candidates are recorded, not ruled)
scope: fleet-wide — both machines, every seat, and the two agent runtimes,
  Claude Code and Codex
supersedes: the machine-local walk ledgers named under Provenance, which are
  deleted once this document is verified on main
---

# Fleet git and worktree working model

This document is the ruled working model for how this project's agent fleet
uses git: which directory a session works in, whose directories it may
touch, how work reaches main, how landed changes reach running seats, and
what makes most damage recoverable when noticed in time (the exact limits
are stated under Standing rulings). It was
produced by a fifteen-item walk — the fifteen were the inventory's open
decisions; rows already built or previously ruled carried their existing
dispositions in — in which the user ruled item by item; the dispositions
and dates below are those rulings. Where a ruling shipped code, the pull request is named; where it
deliberately built nothing, the reason and the revisit trigger are stated —
an unbuilt rule here is a decision, not an omission.

## Reader's key

- **The user / the boss** — the same person: the project's one human
  operator.
- **The two machines** — the user's Mac (user `el`) and `ned-box` (Ubuntu,
  user `nedlern`), each with its own clone. Path map:
  `docs/cross-project/fleet-machine-paths-and-checkouts.md` (flagged stale
  2026-08-17; verify against the live tree before relying on specifics).
- **Seat** — a named, long-lived agent identity: home directory, own
  branch, brief. **Session** — one running conversation occupying a seat;
  sessions end and are replaced, the seat persists. **Recycle** — the
  supervisor replacing a session with a fresh one, carrying the handoff
  forward. Definitions of record: `docs/agents/agent-seat-model.md`.
- **The reference checkout** — the machine's checkout that supervisors
  and launchers run from and other agents read expecting main.
  Mechanically recognizable: it is the checkout whose `.git/worktrees/`
  is non-empty, because it carries the seats as linked worktrees. Three
  honest limits of that test, all recorded: it reads the worktree
  registrations, not the branch; it is dynamic — a standalone clone that
  adds a linked worktree starts classifying as a reference (a queued
  guard fix, State at close); and a reference checkout has an empty
  `.git/worktrees/` before its first seat exists. Where the test and the
  definition disagree, the definition governs: a standalone clone is its
  own workspace, never "the reference" — pinned 2026-08-17.
- **Walked approval** — the user's approval given item by item, not one yes
  to a bundle (`docs/agents/agent-seat-model.md` § The words this model
  uses).
- **The gatekeeper** — `scripts/git-gatekeeper.py`, the permanent single
  door to main; specification `docs/cross-project/git-gatekeeper-design.md`
  (canonical for everything gate-related, including the credential ruling
  it labels C2: the credential able to push main belongs to a dedicated
  system user, and agents reach it only through a controlled, logged door).
  Dormant until its credential work lands.
- **The interim lane** — until the gate activates: seats commit on their
  own branch, ship each topic as a small atomic PR cherry-picked onto a
  fresh branch from main, and the merge-lane seat reviews and merges every
  PR (deputization, recorded at R13, is the ruled exception). Recorded in
  CLAUDE.md's lane paragraph, including deputization.
- **The override markers** — `.walk-approved` (instruction-file guard) and
  `.location-write-approved` (session-location guard), both gitignored,
  each by convention holding the user's quoted approval words — the code
  checks only that the file is non-empty (see Marker honesty below) — and
  consumed by the one guarded call it approves.
- **The launchers** — `scripts/launch-claude-mac` and
  `scripts/launch-claude-ubuntu`.
- **#N** — nedschorus's GitHub tracker; issue or pull request is labeled at
  first use per row.

## Scope

Rules about git, worktrees, sessions, seats, and machines, plus the
enforcement programs that implement them. Deliberately excluded: the
content of workflow governance (md-review's cells, ghi-write's routing, how
a walk is conducted), prose-quality rules, and communication conventions.
Coverage is bounded by the sweep that built the inventory — three corners
were not swept (the per-seat briefs `docs/agents/*-instructions.md`,
`docs/cross-project/fast-handoff-design.md`, and seat `CLAUDE.local.md`
files), so "every rule" means "every rule that sweep found."

A note about reach, so nothing below is assumed to protect more than it
does. This project uses two AI agent programs: Claude Code, which runs
the seated agents, and Codex, which today is invoked only for one-shot
document reviews. Every enforcement program in this document — the hooks
that block writes, the freshness catch-up, the status line, the
launch-time update — is a Claude Code feature: registered in Claude
Code's settings, running only inside Claude Code sessions. A Codex
invocation gets none of that machinery; it is bound only by what it reads
and by GitHub's own branch protection, which applies to everyone because
GitHub enforces it, not the agent program. No work is currently planned
to extend the guards to Codex. The one rule designed for both programs
from the start is R26, whose future reminder hook is specified as one
program with one shared configuration file that both agent programs read.

## The enforcement ladder

A *rule* is a do-or-not-do instruction expressed as text; an *enforcement
program* is code that enforces one (user-ruled vocabulary, 2026-08-17). The
ladder orders mechanisms by when they act, earliest first — not by
resistance to evasion: a block acts before the deed but can be blind to
some routes; detection acts after and sees routes a block is blind to.

1. **Impossible** — the bad state cannot arise without a deliberate
   override. Honest caveat: even rung 1 is "impossible by default" — git
   refuses one branch in two worktrees, but `git worktree add --force` and
   a second clone both defeat it.
2. **Default** — the right thing happens without anyone deciding (agent
   name from the directory; seat branch created at launch).
3. **Block** — an enforcement program refuses at the moment of action
   (PreToolUse hooks). Known blind spot: a block on file-write tools does
   not see writes made through shell commands (see R10 for the ruling on
   that gap).
4. **Detect and reverse** — the unwanted action is noticed after the fact,
   undone, and the right way taught; an exception lane covers unforeseen
   cases. Preconditions: an undo must exist, and the damage must not be
   consumed before detection — both argue for fast detection (next tool
   call, next boot), not audits.
5. **Remind** — the program surfaces the rule at the moment it matters and
   proceeds (boot reports; issue #11's hook shape).
6. **Text** — no enforcement; the rule exists only as prose. The waiting
   room: a do-or-not-do rule lives here only until mechanized (user-ruled
   2026-08-17); governing principles (R17's, R28's) are not queued for
   code and live here permanently by design.

Anchoring ruling, from the gatekeeper design: **CLAUDE.md is documentation,
never enforcement** — a python script does not read it, and different
machines may carry different copies.

## Standing rulings and principles

These govern every row below.

- **A blocking guard carries an escape** (user-ruled 2026-08-17): a false
  fire must be *self-detecting* — the refusal names the file, the reason,
  and the fix, read by the agent at the moment of refusal — and
  *self-repairable*, in either of two forms: the consumed-marker lane
  passes one approved write without code changes, or the refusal itself
  teaches a repair that releases the block (the freshness hook's
  stuck-tree block is this second form — it fires once, and a tree left
  mid-merge takes the display-only path on later turns, verified in
  review). A future block that cannot meet this bar is built as
  detect-and-report instead. The backup guard (R11) is the one ruled
  exception: its no-lane form is deliberate, and reading stays free so
  recovery is never blocked by it.
- **Gray-zone deciders**, per guard: the *program* decides mechanically
  (the gatekeeper); the *user* decides with the agent recording — the
  marker holds the user's quoted approval, self-served by the agent that
  writes it; or **no one** — the write is not the agent's to make, refuse
  unconditionally (the backup guard). Fourth value, *nobody-now*: defer,
  valid only where a named later gate covers the case; no rule currently
  uses it.
- **Marker honesty**: a marker mechanism cannot verify whose words the
  marker holds or when approval was given — any non-empty marker passes.
  A guard's claimed strictness above that is carried only by its refusal
  text; the audit value is the visible quote in the marker and transcript.
  Mechanics, stated exactly: a marker lives at the root of the checkout
  it resolves from; it is consumed at the guard's hook call — one tool
  call, not necessarily one successful write; and an unconsumed marker
  persists until a guarded call consumes it.
- **Silent safety is the enemy**: a conservative default must be
  distinguishable from a clean result, and a protection must be verifiable
  as actually in force. Live sightings that shaped rulings: an unfetched
  ref reporting a false zero-behind; `lsof`-absent making every worktree
  read occupied forever; linger set but protecting nothing started before
  it.
- **Detection is the scarce half of undo**: git plus the snapshot stores
  can reverse most damage if noticed in time. Two carve-outs, stated
  exactly: content never committed that lived shorter than the host's
  snapshot interval (10 minutes on the box, an hour on the Mac) is
  protected by neither store; and reversal restores artifacts, never
  consequences already drawn from them.
- **Rules are delivered at their trigger moment, not held in memory**
  (R28, re-ruled 2026-08-17): refusal text teaches at denial; boot reports
  teach when someone looks; the seat first-prompt teaches at birth.
  CLAUDE.md's rules section shrinking is the health signal — rules leave
  when mechanized; rationale was never CLAUDE.md's to hold (it lives in
  design documents like this one, which refusal messages point at).

## The rules

Status vocabulary, used in every heading below: **BUILT** marks code this
walk shipped, with its pull request named. **built-live** marks a
mechanism that was already running before this walk began — where one
pull request delivered it, that PR is named; where it accreted gradually
with no single PR (launcher scripts, ignore patterns), the row says so.

### Q1 — Which directory am I in?

**R1. Enforcement programs resolve their roots correctly — resolvers
FIXED (PR #86, merged 2026-08-17); tests and registration residue
queued.** Two different questions hide under "the root": *which
repository owns the target file* (walk up from the file to its enclosing
`.git`, handling the worktree case where `.git` is a file) and *which
checkout is this session in* (from the hook payload's working directory,
walked up to the enclosing repo — never from `$CLAUDE_PROJECT_DIR`, which
names the wrong checkout in forked sessions). User revision made at
approval: override markers resolve from the *session's own* checkout, not
the target's — target-derived resolution would let a stale marker in the
reference checkout authorize cross-checkout writes, and would drop marker
litter where other agents read. Target-derived is only the fallback when
the session sits in no checkout. Known residue, queued: hook and statusline
*registration* paths in `.claude/settings.json` still resolve through
`$CLAUDE_PROJECT_DIR` — benign while all checkouts carry identical copies
(the variable only picks which copy of the program starts; the program then
orients itself from the payload), but the retirement is owed.

**R2. A session states and verifies its git context at start — satisfied by
composition (ruled 2026-08-17), nothing built.** The four facts of issue
#34 — a session's directory and branch; that commits land on its branch,
not main; how its work reaches main; that other checkouts are not its to
write — each have a delivery at least as good as the once-proposed
session-start print: directory and branch are on the status line
continuously (R5); the write blocks cover the demonstrated wrong-place
classes exactly — writes from or into the reference checkout (R3, R6) —
with refusals that teach, while a wrong branch in a shell command remains
the status line's to show; the landing lane is CLAUDE.md's ruled
paragraph today, the gatekeeper at activation, and GitHub's branch
protection at push time. The closing argument: a session-start hook rides
the same committed repository as CLAUDE.md — its registration travels in
`.claude/settings.json` in the same clone — so any session that would run
the print already loads the lane text; the print adds zero reach. (This
argument inherits R1's registration residue, noted there.)

**R3. Detached HEAD or sitting in the reference checkout refuses writes —
BUILT (PR #88, merged 2026-08-17).**
`.claude/hooks/session-location-write-guard.py`, PreToolUse block on
Edit/Write/NotebookEdit (including `notebook_path`): a session on detached
HEAD, or seated in the reference checkout, has its writes into repository
checkouts refused with the fix taught in the refusal; exception lane via `.location-write-approved`
holding the user's quoted approval, one write per marker. The adjacent
*starting-stale* block was ruled **not built**: launch-time sync plus the
catch-up hook (R15) shrink exposure to one turn, and the motivating
incident was a stale *read* no write-guard sees. Revisit trigger: a real
incident traced to the one-turn window.

**R4. Stale base — absorbed (ruled 2026-08-17).** The original rule, quoted so
its absorption stays checkable: starting work on a base behind origin/main
blocks the first write; main moving mid-task warns when the new commits
touch files this session edited; push time hardens. The catch-up hook
supersedes it: it merges main into the seat branch when safe and states
why when it cannot; and the Claude Code runtime itself refuses edits to
any file that changed since this session last read it — a runtime
behavior, not project code, and scoped to files this session has read (a
changed file it never read is not covered). Residues assigned: starting-stale rides
R3's ruling; push-time hardening rides the gatekeeper permanently. The
every-turn behind notice stays as built, throttled only if live use
demands it (deliberately left unruled).

**R5. Status line shows the branch — ruled kept (2026-08-17, PR #89).**
`scripts/session-statusline-command.py`. The branch display stays because
shell git commands pass no file-write guard — the line is that mistake's
only always-on visibility even with R3/R6 built. The separator characters became two
plain spaces (PR #89).

### Q2 — Whose directory is this?

**R6 + R7. No agent writes into the reference checkout — BUILT as a block
(PR #91, merged 2026-08-17).** The session-location guard's second
condition: a write *landing* in the reference checkout from a session
seated elsewhere is refused, same marker lane. (The block governs agent
sessions' tool writes; the launchers' fast-forward pull of the reference
at boot is fleet machinery, not an agent write.) Scoped to the demonstrated
class — all four recorded cross-checkout incidents targeted the reference.
The four, so the evidence outlives the walk papers: on 2026-08-14 a
session seated in its own worktree edited twelve documents and staged 235
deletions in the reference checkout; md-review records were later written
into it; a git branch was created in it, twice; and on 2026-08-15 a walk's
working ledger was written into it. Zero incidents targeted another seat's
home or a scratch worktree;
writes into *another seat's* home are recorded-unbuilt with an incident as
the build trigger, and a session's own scratch worktrees are deliberately
untouched (blocking them would false-fire on a pattern the fleet uses
daily). Block outranked the older detect-and-reverse proposal because the
undo is imperfect exactly where damage is worst: a cross-checkout write
that overwrites someone's uncommitted work is unrecoverable by git. R7 (the
reference is a reference, never a bench) rides this mechanism; the
merge-lane seat's legitimate conflict edits pass through the marker lane,
at one marker per write today — the shared-matcher fix in State at close
eases that cost.

**R8. One live session per directory — waits on detection; build
nothing.** No
detector yet meets the bar: it must classify attached viewers, forked
sessions, and background sessions correctly from each session's own state
(the tried `/proc` cwd scan reported an attached session at the directory
the attach was typed in — hiding real duplicates and accusing viewers).

**R9. One name = one seat; a handoff refuses a foreign claim — built-live
(PR #72, merged 2026-08-17).** `scripts/handoff-write-and-check-supervisor.py`:
handoffs stamp `written-in:`; a writer whose directory differs is refused;
`--claim` overrides deliberately — it overwrites whatever handoff stands,
with no approval check; the refusal text is the guard, and the typed flag
in the transcript is the audit trail. The accident it kills: two same-name
sessions overwrote a handoff eleven seconds apart, first lost unread.
Residuals: pre-#72 handoffs carry no stamp; directory basenames are not
globally unique across parents or machines (machine-suffixed names are
deferred — rider 5 in
`docs/issues/queue/45-session-seat-and-isolation-riders.md`). Wrinkle worth
knowing: a seat's *first* handoff is written by whoever provisioned the
seat, from that session's directory — so the writer's directory does not
match the seat the handoff is for, the guard correctly refuses, and
`--claim` is the sanctioned path (docstring line queued).

**R10. Instruction-class files change only with walked approval —
built-live (running since before this walk; its root-resolution defect
was fixed by PR #86).** `.claude/hooks/instruction-file-guard.py`: CLAUDE.md,
per-seat `CLAUDE.local.md`, and `.claude/` (minus `worktrees/` and
`jobs/`, which hold machine-generated working state — fork worktrees, job
records — not instructions) block on write; the agent quotes the user's approval
into `.walk-approved`, consumed by the one call it approves. **The
shell-write gap is named and ruled unguarded** (2026-08-17): a shell
command bypasses every PreToolUse file guard, and no machinery is built for
it — every recorded bypass was accidental, not adversarial, and blocks that
teach the sanctioned path are followed. Build trigger: an actually observed
shell-route bypass. A periodic drift sweep was rejected: in a multi-agent
fleet, "drift from committed state" false-positives on seats legitimately
carrying approved-but-unmerged changes. Codex has no instruction file in
this repository today; if it is ever given one, that file is not in this
guard's protected list — recorded here so the gap is a known fact, not a
surprise, and no decision has been made about it.

**R11. Backup stores are read-only to agents — built-live (running since
before this walk; its root-resolution defect was fixed by PR #86), lane
removed (user-ruled 2026-08-17).**
`.claude/hooks/backup-and-snapshot-write-guard.py`: the Timeshift store and
configuration (`/mnt/backup`, `/etc/timeshift`) and Time Machine state
refuse agent tool-writes *unconditionally* — no marker lane (the shell
route is R10's ruled gap); a real configuration need routes to the user's
keyboard. Reading stays free, so snapshot recovery is untouched.
Rationale: an undo store agents can write is not one; instruction files
are approval-gated writes, backups are not agent-writable at all — two
classes of protection, not two calibrations. What "routes to the user's
keyboard" means was set by precedent (2026-08-18): the *user* decides —
he may direct an agent's hands, in that agent's own session, to paths
outside the guarded class (the snapshot-cadence cron file, R19); the
guarded paths themselves stay agent-unwritable.

### Q3 — How does work reach main?

**R12. Agents never push to main; one door — partial.** Branch protection
is live (pushes to main restricted to one GitHub account, enforce-admins
on, force-push and deletion blocked) — rung 1 at the account tier only: any
process holding that credential can push, so today "agents never push" is
instructed, not impossible. The gatekeeper's C2 credential design is where
it becomes impossible; the gate stays dormant until its credential work
lands and it can review what passes through it (the gatekeeper design is
canonical for activation status). Its `audit` subcommand checks live
protection with three named outcomes, never a silent skip; only the Mac's
credential can read protection settings today, so the box's audit answers
`audit-failed` — honest and blind. The *lane* is exercised daily, and the
*restriction* was proven live on 2026-08-18 by a controlled, user-authorized
fence test at the merge seat: a box agent (write permission, not on the
allow-list) pushed one commit to two throwaway branches cut from main's tip
— one carrying protection identical to main's, one unprotected as control.
The protected branch refused it (GH006, "not authorized to push"); the
control accepted the same credential, commit, and minute, so the refusal is
attributable to the protection itself. The same test established a fact for
anyone reading the repository activity log as evidence: the refused push
left NO trace there — the log records only writes that succeeded, so a
quiet log means nothing got through, never that nobody tried. The gate's
own program path was also proven end to end on 2026-08-18: one
user-authorized smoke check-in landed commit b24e376 on main under the
gate's dedicated git identity with all five commit trailers correct —
while the gate stays dormant for daily work and the pull-request lane
stays in force; the full record is committed at
`docs/cross-project/git-gatekeeper-first-live-check-in-record.md`.

**R13. The interim lane — built-live (process); retired when the gate
activates.** Lives in CLAUDE.md's lane paragraph and
`docs/agents/seat-first-prompt.md` § Reaching main. **Deputization** is the
lane's recorded exception (ruled 2026-08-18, PR #93): the user may instruct
a specific seat, in that seat's own session, to merge a specific PR; the
user's words relayed through another session are hearsay and are refused —
exercised in practice before it was recorded (a relayed instruction refused
2026-08-16; the user then deputized directly for PR #72's merge).

**R14. One branch, one writer — satisfied by defaults (ruled 2026-08-17);
the old push-time check is retired.** The original rule ("each seat pushes
only its own branch") predates the atomic-PR lane, under which seats
legitimately push cherry-picked topic branches daily — an own-branch-only
check would refuse the ruled lane. What remains of the original hazard (two
writers, one branch) is covered by defaults — a seat branch at launch;
in practice one author creates each topic branch, though nothing
allocates names — with git's non-fast-forward refusal as the backstop.
The one recorded collision cost a rebase, not lost work; stated exactly,
these are defaults, not guarantees — branch protection covers main only,
so a force-push to a shared branch remains possible and undefended. Push discipline as a whole becomes the gatekeeper's to enforce at
activation: a push is a shell operation no file-write hook sees, so the
gate is the one real door.

### Q4 — How does a change reach a running seat, and what keeps seats alive?

**R15. A landed change reaches every running seat — BUILT (PR #87, merged
2026-08-17; delivery ruling PR #90).**
`scripts/checkout-freshness-catch-up.py` runs as a Stop hook at every turn
boundary: throttled fetch; merge of `origin/main` into the seat branch only
when behind, clean (no uncommitted changes to tracked files), free of
in-progress state, and conflict-free — else one line stating the reason.
After a successful merge the changed files are named, up to eight, with
the remainder counted; a failed comparison's silent path is a queued fix
(State at close). The status line's `⇣N`
reads the stamp file the hook writes —
`<git-dir>/checkout-freshness-stamp.json` — and never fetches. The launchers fast-forward the reference
checkout at boot; the supervisor's launch-time sync remains the floor.
Coverage stated exactly: delivery happens at turn boundaries when the
seat is clean and conflict-free — an idle session's worktree, or one that
stays dirty, lags and says so on its status line rather than silently.
**Who hears it** (ruled 2026-08-17): exactly one state forces an agent
turn — a conflict whose cleanup failed, leaving the tree mid-merge, emits a
Stop-hook block with repair instructions in hand; routine events stay
display-plus-stamp at zero forced turns. **Known structural finding,
candidate fix unruled:** the atomic-PR lane reliably produces add/add
conflicts on files a cherry-picked topic *created* — the content lands on
main under new commit IDs, so git sees both sides adding the same file.
Manual remedy, executable as written: list the conflicted files with
`git status`; during the catch-up's merge, `git checkout --theirs <file>`
takes main's canonical version; `git add` them and commit to complete the
merge. Candidate: the supervisor's launch sync resets the seat branch to
`origin/main` when the branch carries nothing unmerged — the predicate
still needs careful definition (cherry-picks break ancestry, so an
ancestry test would wrongly call landed work unmerged; part of why this
stays unruled).

**R16. Binary updates at launch, never in background — built-live
(pre-walk; the launchers accreted with no single PR).** Both
launchers run `claude update` with a timeout, warn-and-proceed: launch-time
update is best-effort; the launchers' own guarantee is that *they* never
swap the binary under a live session — whether any background updater now
runs, after the flag removal below, is exactly the queued question in
State at close. Update note (user-ruled 2026-08-17): the box's
`DISABLE_AUTOUPDATER=1` flag is removed from `~/.claude/settings.json` on
the box, a dated backup beside it
(`settings.json.before-autoupdater-enable-2026-08-17`); issue #62's
auto-update theory was retracted. A launch-time version check in the
launchers is queued — see State at close.

**R17. Shared machinery lives in the repository, self-updating at safe
points — violated twice, fixes queued.** The principle: every deployed
copy keeps itself current from its source at safe points (launch,
recycle, invocation), never by swapping under a live consumer. The
current state falls short of it twice:
`launch-claude-ubuntu` invokes the supervisor by absolute path into a
checkout nothing pulls (fix queued on issue #45), and `launch-claude-mac`
runs from whatever checkout invoked it.

**R18. Seat hosts are provisioned to survive disconnects — checklist ruled
(2026-08-17).** The per-host provisioning list: (1) on systemd hosts,
`loginctl enable-linger <agent-user>`, verified by an actual gap — close
every SSH session for several minutes and confirm the seats are still
alive after — because the flag protects only user managers started after
it was set, so reading the flag alone reports a safety not yet in force
(the Mac has no systemd and no linger equivalent; its seats run under the
user's desktop session, which does not end on disconnect); (2) a
restore-one-file snapshot verification — copy one file out of the newest
snapshot and compare checksums (performed for the box 2026-08-17; not yet
performed for the Mac's Time Machine store); (3) the host's snapshot
cadence, recorded per R19; (4) `lsof` present — the worktree reaper's
vacancy check needs it (R21's caveat). Scope honesty: linger covers
logout-triggered kills; reboots and power loss fall to git and to
whichever snapshot store survives the event. Completed and gap-verified
for `nedlern` on the box; the Mac has not been walked through this list.

**R19. Snapshot cadence — ruled and LIVE (2026-08-17/18).** The box's
cron creates a snapshot every 10 minutes (installed 2026-08-18, first
tick verified in the store): `/etc/cron.d/timeshift-10min` fires at
minutes 10–50 with `timeshift --create --tags H --scripted`, joining the
existing auto-pruned 24-slot hourly ring; the shipped hourly `--check`
keeps :00, the daily/weekly/monthly rings, and pruning. Retention config
untouched — the 24-slot ring now holds 4 hours of 10-minute coverage
instead of 24 hours of hourly, a ruled trade, then dailies; raisable at
the user's keyboard if that proves short. Undo: delete the cron file. Ruled on
measured facts: Timeshift runs in rsync-hardlink mode with the agent home
deliberately included; an hourly delta takes ~13 seconds; the whole ladder
is ~50 GB on a 3.6 TB disk; pruning verified live; first 10-minute tick
confirmed in the store. Applied by the git-infra seat on the user's direct
in-session instruction — `/etc/cron.d` is outside R11's guarded class. The
Mac stays at OS-default hourly: no recorded Mac-side loss. Honesty about
what it buys: minutes-cadence never reaches the seconds class (the
11-second handoff overwrite fell inside any cadence; R9's guard closed that
class).

**R20. The handoff channel preserves structure end to end — fix ruled
(2026-08-18), build queued.** The writer
(`scripts/handoff-write-and-check-supervisor.py`) collapses the multi-line
next-step to one line at write time and the supervisor
(`scripts/handoff-supervisor.py`) reads key-value lines, so structured
instructions degrade to a dense chain. The ruled fix touches both ends —
the writer emits a delimited multi-line block *and* the reader parses it (a
reader-only fix cannot restore newlines already destroyed). Until built,
writer discipline is the honest interim: label each part in ALL CAPS
inside the single line — e.g. "FIRST ACTION: read the anchor. THEN:
present item 3. CONTEXT: PRs 86-91 merged." — because capitals survive
the flattening where line breaks do not.

### Q5 — What piles up, and who sweeps it?

**R21. Session worktrees are reaped when clean, landed, and vacant —
built-live (PR #73).** `scripts/clean-worktrees.py`: three mechanical
checks; anything failing or ambiguous is kept with its reason; `--only-done`
runs at launcher launch; `--remove` is a separate deliberate call. The
posture it set, reused across this model: mechanical predicates, ambiguity
keeps, report before remove. Recorded caveat (silent safety): without
`lsof` the vacancy check reads every worktree as occupied — the
launcher-run `--only-done` pass then prints nothing forever,
indistinguishable from tidy, while the full report at least shows the
kept-because-occupied reasons. Not demonstrated live; guarded going
forward by R18's checklist line requiring `lsof` at provisioning.

**R22. Untracked files classified; junk ignored by pattern — ruled closed
(2026-08-17; issue #50 closed).** Measured at ruling: the
untracked-but-not-ignored bucket was empty in both the git-infra seat and
the reference checkout, and every observed junk class already carries a
`.gitignore` pattern — each pattern added since the reasons convention
carries its reason beside it (the first two entries predate the
convention; adding their reasons rides the queued minors PR). The `.gitignore` is the
living list — new patterns as new junk classes are actually observed. The
periodic untracked-file cleanup script is not built (it gets a real,
multi-part name when built); build trigger: a real accumulation surfacing
— then a new issue is filed, the script's first version reports and never
deletes, and it runs as part of session recycling. Unpromoted work — real
work product meant for the repository — is protected by exactly one net,
confirmed: commit it. The not-yet-committed interval is additionally
backstopped by R19's snapshots, above their cadence interval.

**R23. Agent scratch lives in the scratchpad — satisfied by a Claude Code
runtime
default (ruled 2026-08-17).** The Claude Code runtime puts, in every
session's system prompt, the path of its
per-session scratchpad outside the repository and instructs its use —
delivery at the trigger moment, nothing built. A remind-tier hook on
scratch-shaped writes into a worktree stays a recorded candidate sharing
R26's hook-plus-config pattern, configured for scratch-shaped file
patterns rather than only MDs.

**R24. Branch surveys fetch before they conclude — text, encoded into
R22's untracked-file cleanup script when built.** Before concluding what exists or is merged: `git fetch
--prune origin` and read remote-tracking refs; a survey that cannot reach
the remote says so rather than answering from stale refs. Evidence: a prune
list built from unfetched refs missed four merged remote branches
(2026-08-17).

**R25. Dead worktree registrations get surfaced — ruled (2026-08-18), build
queued.** A worktree registered under a temporary directory
(`/private/tmp` on macOS, `/tmp` on the box) leaves a dead entry when the
temp area clears, and `git worktree prune` is manual. The
`clean-worktrees.py` report gains one line naming dead registrations and
the prune command — report
only; the prune stays deliberate. Sighted live at ruling: two
`/private/tmp` scratch registrations in the reference checkout's list.

**R26. New MDs land in approved homes — ruled-unbuilt (issue #11).** A
PreToolUse *remind* hook on MD writes outside the approved homes (the
repository root `README.md` § "Where things live" becomes the
single-source path list at build time — the table must be completed then;
known gap today: it lacks `docs/agents/`, where the seat briefs and the
seat model live), symmetric across the two agent
runtimes (Claude Code and Codex), one shared config. Remind, not block:
MD creation is overwhelmingly legitimate. Build trigger: a note landing
astray despite the queue rule (material whose fate is undecided routes to
the queue directories — `docs/cross-project/nedschorus-founding-plan.md`
§ Project organization). The hook-plus-config pair serves R23
and R26 both — build once, configure twice.

**R27. Machine-local records stay out of commits — built-live (pre-walk;
the ignore patterns accreted entry by entry).**
`.gitignore` carries the walk-ledger, review-record, marker, and
`CLAUDE.local.md` patterns, each with its reason. Default rung: the wrong
state does not assemble through routine git (`git add -f` and
tracked-before-the-pattern are deliberate acts outside the claim). Limit,
observed live: gitignore protects the repository, not the placement — a
file can still land in the wrong checkout (that is R6's business).

### Cross-cutting

**R28. Rules are delivered at their trigger moment** — see Standing rulings
above; listed here to keep the rule numbering complete.

## Index

| # | Rule | Rung | Status at close |
|---|---|---|---|
| R1 | Guards resolve roots correctly | — (foundation) | fixed, PR #86; registration residue queued |
| R2 | Session states its git context | — (composition of R3/R5/R6) | satisfied by composition |
| R3 | Detached/reference seat refuses writes | block | built, PR #88 |
| R4 | Stale base | — | absorbed by R15's catch-up |
| R5 | Status line shows branch | default | kept; separators fixed, PR #89 |
| R6+R7 | No writes into the reference | block | built, PR #91 |
| R8 | One live session per directory | — | waits on detection; build nothing |
| R9 | One name = one seat | default + block | built-live, PR #72 |
| R10 | Instruction files need walked approval | block | built-live; shell gap ruled unguarded |
| R11 | Backups read-only to agents | block (no lane) | built-live; lane removed |
| R12 | Agents never push to main | impossible (account tier) + text (agent tier) | partial; C2 pending |
| R13 | Interim lane + deputization | text (process) | built-live; deputization in CLAUDE.md, PR #93 |
| R14 | One branch, one writer | default | satisfied by defaults; push check retired |
| R15 | Landed changes reach running seats | default + block (attention) | built, PRs #87/#90 |
| R16 | Binary updates at launch only | default | built-live; version check queued |
| R17 | Machinery self-updates at safe points | text (principle) | violated twice; fixes queued (issue #45) |
| R18 | Hosts survive disconnects | default | checklist ruled; box done |
| R19 | Snapshot cadence | default | live: box 10-min, Mac hourly |
| R20 | Handoff preserves structure | text | fix ruled; build queued |
| R21 | Worktrees reaped when safe | detect + remind | built-live, PR #73 |
| R22 | Junk ignored by pattern | default | ruled closed; issue #50 closed |
| R23 | Scratch lives in the scratchpad | default | satisfied by runtime default |
| R24 | Surveys fetch before concluding | text | encode into R22's cleanup script when built |
| R25 | Dead registrations surfaced | remind (report) | ruled; build queued |
| R26 | New MDs land in approved homes | remind | ruled-unbuilt, issue #11 |
| R27 | Machine-local stays uncommitted | default | built-live |
| R28 | Rules delivered at trigger | principle | governs all rows |

## State at close — queued work and recorded candidates

Queued builds, in no ruled order. Items 1–4 are one topic each and ship as
one pull request each — item 1's sub-entries are NOT separate PRs; they are
one PR with a checklist in its description. The full review discussions
behind item 1 are permanent on GitHub, in the merge-lane review threads of
the pull requests named below.

Depth convention (2026-08-19, set with the merge seat): each queued item
is one of two kinds. A *work order* — what is wrong plus what correct
behavior looks like, built and reviewed directly against that statement —
is the default, right for changes smaller than a design document would
be. *Design-first* marks a change that is coupled or touches a path the
whole fleet depends on: its design lands in the document that owns the
area and is md-reviewed before code. Two known design-first items: the
launcher repair recorded on issue #45 (design in that issue's pair
document, `docs/issues/45-remote-named-agent-launch-and-reattach.md`),
and item 2 below — the handoff fix is a two-program protocol change, and
its delimited format gets a short section in
`docs/cross-project/fast-handoff-design.md`, which must record the format
in any case. Every queued PR's body states the intended behavior it
should be reviewed against; the merge seat reviews against that statement
and posts its review on the pull request, making the check part of the
record.

1. **Guard and catch-up review fixes** — each entry: what is wrong today,
   then what it should do instead.
   - From PR #86's review (the guards' root-resolution rework):
     - The test suite never exercises a case where the session's checkout
       and the target file's checkout differ, so a wrong cross-root
       implementation would still pass; add that discriminating test.
     - The two older guards read only the tool input's `file_path`, so a
       NotebookEdit call writing through `notebook_path` bypasses them;
       cover that field there too (the session-location guard already
       does).
     - When the hook payload's working directory names a directory that no
       longer exists, marker resolution falls back to the target file's
       repository and can consume a stale marker sitting there; the
       fallback should refuse instead.
   - From PR #87's review (the catch-up hook):
     - The hook detects its own merge conflicts by finding the word
       "CONFLICT" in git's output, which a non-English locale translates
       (German git prints "KONFLIKT"), so cleanup is skipped and the tree
       stays mid-merge; run git with `LC_ALL=C` so the word is stable.
     - When the behind-count cannot be computed, the seat's own record is
       correctly set to "unknown," but the reference checkout's record and
       the report still show the old stale number; null them the same way.
     - The new code paths need tests that fail against the pre-fix
       implementation; today only the conflict-throttle case does.
   - From PR #88's review (the session-location guard):
     - A repository created by `git init` with no commits yet is
       classified as detached HEAD and told a remedy it cannot complete;
       detect the no-commits state (`git symbolic-ref --short HEAD`
       succeeds there) and say what it actually is.
     - If only the branch-name lookup fails while the repository lookup
       succeeded, a healthy seat is refused with the wrong message and its
       marker is consumed; distinguish the two failure cases.
     - Test gaps to close: relative file paths, a working directory that
       is a subdirectory of the checkout, explicitly symlinked paths,
       marker-survival cases, and the allowed side of NotebookEdit.
   - From PR #91's review (the reference-landing block):
     - Writes into the reference checkout's `.git` directory are allowed —
       the repository lookup fails inside `.git`, so no owner resolves —
       while ordinary file writes there are blocked; `.git/hooks/` is
       executable code, so close that asymmetry.
     - The refusal shown to a session blocked for detached HEAD does not
       say how to create the override file — such a session cannot use the
       normal file-writing tool (that write is itself blocked), so it must
       create the file with a shell command; add that instruction to the
       message (the reference-checkout refusal already carries it).
     - A test should pin that a marker sitting at the target's root stays
       inert and unconsumed for a normally-seated session; today an
       implementation that wrongly honored such a marker would still pass
       the whole suite.
     - Three guards now carry near-identical marker code, and one guarded
       write can need two markers with one wastefully consumed; extract a
       shared marker matcher.
   - From PR #89's review (the status line): the module docstring's
     example line still shows the old │ separators; update it to the
     two-space format.
   - From this document's own md-review (2026-08-18): the first two
     `.gitignore` entries predate the reason-comment convention; add
     their reasons.
   - From R1's residue: the hook and status-line registration lines in
     `.claude/settings.json` still locate their programs through
     `$CLAUDE_PROJECT_DIR`, which names the wrong checkout in forked
     sessions; re-register them to resolve from the session's own checkout,
     which is safe now that every registered script exists on main.
2. **R20** — the handoff both-ends structure fix, plus the
   first-self-handoff `--claim` docstring line.
3. **R25** — the dead-registration report line in `clean-worktrees.py`.
4. **Launcher version check** (user-ruled 2026-08-17, routed via
   merge-lane): the launchers gain a check for a newer Claude Code on the
   release channel each machine is configured for — it may update or just
   announce loudly, and it never blocks a launch. Settle first, via the
   claude-code-guide agent: do the auto-updater and `claude update`
   respect the `autoUpdatesChannel` setting? The user's working premise
   is that auto-update follows the stable channel while the fleet wants
   latest. If the premise is wrong, removing the disable flag (R16)
   already restored working auto-updates and this item closes with no
   launcher change; if it is right, the launcher check gets built. That
   answer decides which, and completes this item's settle-first step.

Recorded candidates, unruled — an incident or a user pick is the trigger:
the supervisor launch-reset of fully-merged seat branches (R15's add/add
finding); R24's logic encoded into R22's future cleanup script; R8's session
detector; machine-suffixed seat names (rider 5); other-seat-home write
blocking (R6's recorded-unbuilt half).

## Provenance

Produced at the close of the git/worktree rules walk (fifteen items,
2026-08-17/18, git-infra seat, the user ruling item by item). The walk
shipped PRs #86–#91 and #93 and closed issue #50. Its working papers —
`walk-ledgers/2026-08-17-git-worktree-rules-inventory.md` (the rules
inventory anchor) and
`walk-ledgers/2026-08-16-agent-worktree-git-coalesce-shape.md` (the shape
ledger) — were machine-local
and gitignored, and are deleted once this document is verified on main; they have no git history to recover from, so this document was
written to stand without them: everything they decided is restated here
in full. It still depends, deliberately, on three documents, each
canonical for its own subject — the gatekeeper design, the seat model,
and the founding plan (`docs/cross-project/nedschorus-founding-plan.md`)
— and it is complete about its own subject, not about theirs.
