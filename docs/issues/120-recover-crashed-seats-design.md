---
status: overview of the tool as built; six changes ruled 2026-09-02, none built — listed in § What this document proposes
design-as-of: 2026-09-02
---

# Crash recovery for seats — `recover-crashed-seats.py` (overview)

What [`scripts/recover-crashed-seats.py`](../../scripts/recover-crashed-seats.py)
does today, end to end, and the changes ruled for it. Pair document for
[nedschorus#120](https://github.com/nedschorus/nedschorus/issues/120), which
carries the issue's own history and close condition.

A **seat** is a durable named identity — `MD-skills`, `merge-lane` — a directory
under `~/agents/` and a tmux session of the same name, into which sessions are
minted one after another; the seat outlives any one session. A **supervisor**
watches it: it launches each session, recycles it on each handoff, and exits when
the agent stops without handing off. A **handoff** is the file a session writes
when it passes its work to a successor; it carries a **restart-counter**, which
the supervisor compares with the last counter it consumed to tell a new handoff
from one already acted on. **Boot-ignition** is the supervisor's first-launch
path that starts a session from a handoff found waiting. A **dialog extract** is
the condensed dialog
[`scripts/handoff-extract-conversation.py`](../../scripts/handoff-extract-conversation.py)
produces from a transcript.

This tool covers one case: a seat whose session died **with no handoff acted
on** — a crash, a killed tmux server, a machine reboot. That case is what
[`scripts/resupervise-seat.py`](../../scripts/resupervise-seat.py) cannot serve,
because its precondition is a handoff genuinely waiting to be acted on. A crash
normally leaves none; one that strikes after the agent writes a handoff and
before the supervisor consumes it does leave one, and that is the
waiting-handoff branch below.

## What this document proposes

Six changes, all ruled 2026-09-02, none built. Each is specified in the section
named.

1. **Judge the supervisor by its process, confirmed by command line**, not by the
   age of its heartbeat — § Two defects that test found.
2. **Record how the agent exited**, treat a recorded clean exit as not a crash,
   relax the tmux check, make the launch collision report failure, and make the
   occupancy check ignore only an idle shell — § Ruled: record how the agent
   exited.
3. **A durable parking marker** that automatic paths consult and a requested
   resume clears — § Ruled: parking is on the user's word.
4. **Verify a resumed seat actually came up, and offer the degraded restart when
   it did not** — § Ruled: what happens when a restart fails.
5. **A by-hand launch resumes a crashed seat** instead of minting an empty
   session — the same section.
6. **Recover into a window**, `--open-iterm-window-per-seat` — § Proposed
   change: recover into a window.

## Why it exists

On 2026-08-21 the Mac's single tmux server died and took all three Mac seats with
it in the same second, mid-flight, with no handoff written. Relaunching plainly
made things worse: the supervisors fell through to their first-prompt path and
minted three near-empty successor sessions while the real pre-crash transcripts,
1.0–2.1 MB each, sat intact on disk. Recovery was done by hand — dig each session
id out of `~/.claude/projects/` by modification time, then `claude --resume` in
the seat's directory. It worked, and every step was improvised.

## What it does, per seat

**First it tries to establish the seat is dead.** These are checks, not proof —
each one can only report what it can see, and none covers the moment between
the last check and the launch:

1. No seat directory → refuse.
2. A tmux session holding the seat's name, on the seat's own socket or the shared
   default one → refuse: *this tool recovers crashes, it never touches live
   work.* If that cannot be determined, it refuses rather than guessing.
3. A supervisor lock file held by a live process → refuse; a supervisor is
   starting or already running.
4. A supervisor heartbeat that is still fresh → refuse.
5. A live process whose working directory is the seat's directory, found with
   `lsof` → refuse.

**Then it decides what kind of recovery is needed:**

- **A handoff is waiting and unconsumed** → it does nothing itself and says so.
  A plain relaunch is correct there, because the supervisor's own boot-ignition
  consumes the handoff.
- **A handoff exists but its restart-counter is missing or unreadable** → refuse,
  and tell the operator both ways out: if the file is real, fix its
  restart-counter and relaunch plain; if it is scrap, delete it and rerun the
  recovery. The supervisor's boot-ignition skips such a file, so resuming past it
  would silently discard whatever it says.
- **Otherwise, resume.** It takes the newest transcript for that seat by file
  modification time, skipping the shape of a failed successor — a small session
  whose first turn this machinery itself composed **and** that holds fewer than
  two substantive assistant turns. Both conditions, so a prior successful
  recovery, which carries the composed opener and then real work, is not skipped
  on a second crash. That is a heuristic, not a proof: a large failed successor,
  or a transcript whose timestamps were disturbed, can still win.
- **No usable transcript** → ignite: launch fresh, with a first prompt pointing
  at the newest dialog extract.

**Then it launches.** On the Mac it runs
[`launch-claude-mac`](../../scripts/launch-claude-mac) `<seat> --no-attach`,
passing the chosen session id to the supervisor through the environment variable
`LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS`, along with the handoff directory and
agents root the assessment actually used. On a non-macOS machine there is no such
launcher, so it composes the supervisor's tmux launch directly — carrying the
seat environment the launcher would otherwise have set, including the task-list
binding, the variable that pins the seat's task list to the seat's name.

Every non-dry run appends its decision to
`~/.claude/handoffs/recover-crashed-seats-log.txt`.

## The command line

```
recover-crashed-seats.py <seat-name>... [--dry-run] [--ignite-fallback]
recover-crashed-seats.py --all [--dry-run] [--ignite-fallback]
```

`--dry-run` reports every decision and launches nothing. `--ignite-fallback`
skips the resume and starts fresh from a dialog extract — for a transcript too
large to be worth replaying. `--agents-root`, `--handoff-dir` and
`--projects-root` override the locations.

**`--all` is narrower than it sounds.** It assesses only directories where
something has actually run — a supervisor state file, a handoff, or a transcript
directory. An empty leftover from a mistyped launch is not a seat. A never-run
directory can still be recovered by naming it explicitly.

**Two properties worth knowing before relying on it.** `--all` selects by *seat
home* — a directory under the agents root — not by what was running: on 2026-09-02 it would have resumed `mac-prof`, a
seat finished with five days earlier, as a paid session. And the exit code is
non-zero only when *every* named seat failed — a partial recovery, where some
seats came back and others did not, exits zero.

## Proven, 2026-09-02, on both machines

The one link that had never run live — the script's own automated resume launch,
as opposed to the by-hand `claude --resume` form proven 2026-08-21 — ran for the
first time after the Mac's reboot. Three seats (`MD-skills`, `merge-lane`,
`reboot-test`) were recovered in one command, each resuming its own pre-reboot
transcript under a fresh supervisor, in its own directory. Verified afterwards:
each transcript carries the script's crash-recovery opening turn and has advanced
past the relaunch.

That is [nedschorus#120](https://github.com/nedschorus/nedschorus/issues/120)'s
stated close condition.

**The box's own branch was then proven by a deliberate crash the same day.** The
non-macOS launch path is different code — it composes the supervisor's tmux
launch directly rather than calling a launcher — and had never run live. A
throwaway seat, `reboot-test-box`, was launched on ned-box with a real first task
so its transcript held actual work; its tmux server was then killed outright, the
2026-08-21 shape: no handoff, no warning. Recovery resumed session
`66a66097-1ff1-4140-950c-687273a8ec4a` under a fresh supervisor, the transcript
grew from 25 KB to 33 KB, and the supervisor stamped its heartbeat 10 seconds
later. The test seat, its worktree, branch, task store and handoff files were
then removed. The box's recovery log keeps its line for that run, correctly, as
append-only history.

## Two defects that test found

**A crashed seat is refused for the first 60 seconds.** The deadness check asks
`supervisor_liveness()`, which judges a heartbeat stale only after
`HEARTBEAT_STALE_SECONDS = 60.0`. A supervisor that died three seconds ago still
looks alive, so recovery refuses with *"a supervisor is watching this seat."*
Measured on the box: refused at 8, 24, 39 and 54 seconds after the kill, and
accepted at 60. `restart-live-seats-at-login` runs shortly after the machine comes
up, so whether it lands inside this window depends on how fast the machine boots
— and inside it, it recovers nothing and reports a screen of refusals claiming
the seats are alive.

**Ruled 2026-09-02: judge the supervisor by its process, not by the age of its
stamp.** The recorded process id is already in the same state file as the
timestamp. Probe that instead, and fall back to the 60-second rule only when no
process id is recorded.

With one condition that is not optional: **existence of the process id is not
enough.** Process ids are reused, and most readily across exactly the event this
tool serves — a reboot. A number recorded before the restart can belong to an
unrelated process afterwards, and then a dead seat reads as alive again, which is
the defect this ruling exists to remove. The check must confirm the process *is*
that supervisor, by its command line, not merely that something holds the number.

**A surviving after-exit shell blocks recovery until it is killed by hand.** When
only the agent and its supervisor die — an accidental exit, a supervisor crash —
under a seat that was launched attached, the tmux session does not die with
them: the launcher's pane command falls through to an interactive shell in the
seat's directory, by design, so the seat can be relaunched in place. (A seat
launched detached has its pane command fixed at creation, and its session closes
with the supervisor.) Recovery sees that tmux session and refuses: *"this tool
recovers crashes, it never touches live seats."* This tool cannot recover the
seat until someone kills that session by hand. `prof` on ned-box is in exactly
this state right now, and `mac-prof` was on the Mac. The refusal is protecting
an empty bash shell.

This does not affect recovery after a reboot or a killed tmux server, which
leave no session standing. It affects every crash that leaves a same-name tmux
session behind, and it is the reason the answer to "close a seat now and reopen
it later" is unsatisfying today (below).

**One check refuses today, and two more problems wait behind it.** The checks
short-circuit at the first refusal, so fixing the tmux check alone does not clear
the case:

1. `tmux_session_alive_anywhere()` reports the surviving session and the seat is
   called not-dead.
2. `seat_directory_occupied()` runs `lsof` for any process whose working
   directory is the seat's directory — and the after-exit shell's working
   directory *is* the seat's directory, because the launcher puts it there on
   purpose so the seat can be relaunched in place. So the shell is read as
   someone still working in the seat.
3. Past both, not a check but a collision. The launcher's detached path runs
   `tmux new-session -d -s <name>`, which fails when a session of that name
   already exists — and it swallows that failure into an `|| echo …` message,
   so the launcher still exits zero. Recovery checks only the exit code, so it
   would report `relaunched resuming <session>` having launched nothing. **A
   false success, at the one moment the report is all anyone has.**

### Ruled 2026-09-02: record how the agent exited, and stop inferring it

The refusal above is wrong in its reasoning and right in its outcome, and that is
why it must not simply be removed. The user exits seats deliberately — *"I do
that to get back some memory or clean up my screen"* — and the surviving shell is
what accidentally stops those seats being resumed against his intent. Teaching
recovery to reach past it, which this document first proposed, would have made
the tool worse.

**The distinction already exists in behavior; it is only unwritten.** When the
user exits, the supervisor watches the agent go and exits cleanly, printing
"session ended without a handoff; supervisor stopping"
([`handoff-supervisor.py`](../../scripts/handoff-supervisor.py), its no-handoff
return). When the machine or the tmux server dies, the supervisor is killed and
never reaches that line. A supervisor that outlived its agent saw an intended
ending; one that did not, did not.

So: **the supervisor records the agent's exit code and the time in its state file
immediately before stopping**, and recovery asks that instead of guessing.

- **A recorded exit with code zero** — deliberate. Not a crash. Do not resume
  automatically; offer restart, park, or finished.
- **No such record** — the supervisor died mid-flight. A crash. Resume.

With intent recorded, the tmux check can be relaxed safely, because it is no
longer the only thing standing between a deliberately closed seat and an
automatic resume.

Two failure directions, both accepted. If the supervisor is killed before it can
write the record, a deliberate exit reads as a crash and the seat returns — the
error falls toward restoring, which the user undoes by exiting again. And a seat
whose agent crashed while its supervisor kept watching produces a record too, so
it lands in "offer" rather than "resume"; that is wanted, since the supervisor
was present and the case is worth showing rather than deciding.

This ruling reaches into the supervisor, not only this tool: the state file it
writes is the same one carrying `last_poll_at`.

**Independent of the above, two fixes stand on their own.** The launch collision
must stop reporting a success it did not achieve. And the occupancy check must
ignore only a shell with nothing running under it — never one the user is working
in, or the tool breaks its own promise never to touch live work. Retiring a stale
tmux session before launching is the remaining piece, the step
`resupervise-seat.py` already performs for its own case.

## Closing a seat deliberately, and reopening it later

The mechanism exists: a handoff may carry an optional `dont-restart` field, and
any value makes the supervisor ask before relaunching — `restart? y/n` — or, with
no terminal to ask on, stop without relaunching. So a seat can be told to hand
off and stand down.

Reopening it later with its context is where this frays. Answering `n` consumes
the handoff, so a later plain relaunch finds nothing waiting and starts a fresh
empty session. The context is still on disk, and recovery would resume it — but
the supervisor's exit leaves the after-exit shell holding the tmux session, and
recovery refuses a seat whose tmux session is alive. The two defects above
combine into a gap: **there is no clean supported way to park a seat and bring it
back with its context.**

### Ruled 2026-09-02: parking is on the user's word, in both directions

The user's requirement: *"let me not resume now but resume when I ask."* A parked
seat must stay down until he asks for it, and must then come back carrying its
context.

That has a consequence for everything automatic. A parked seat must be invisible
to `--all` and to the login-time restarter, or the next reboot undoes the parking
— and the seat the user deliberately stood down returns as a paid session, which
is the same fault this project already rejected `--all` for.

`dont-restart` cannot carry that state. It lives in a handoff, and the handoff is
consumed the moment the question is answered, so it marks one relaunch decision
rather than a standing one. Parking needs a durable marker of its own that
survives the supervisor's exit, that automatic paths consult before selecting a
seat, and that resuming on request clears.

Not built. Of the changes listed at the top, it is the one that is a new
capability rather than a correction.

## Ruled 2026-09-02: what happens when a restart fails

A failed resume must not silently become something else. The user's ruling: the
tool reports that the restart failed and **asks** whether to recreate the seat
the degraded way — the fresh session that reads a dialog extract and needs no
handoff — rather than falling back on its own.

Today it does neither. A failed launch returns `LAUNCH FAILED — the seat is still
down` and stops; `--ignite-fallback` is a flag the operator must pass in advance.
And the exit code checked is the launcher's, which only starts tmux: if the
resume fails *inside* the session, the launch still exits zero and recovery
reports success. Both halves — verify the seat actually came up, then offer the
degraded restart — are proposed work, not built.

**Ruled 2026-09-02: the ask has an answer when nobody is at the terminal, and a
by-hand launch is one way to answer it.** `restart-live-seats-at-login` calls
this tool with no one watching. A seat it cannot bring back stays down, is
recorded as parked with the reason and date, and is asked about in the restart's
own window on the Mac, where whatever goes unanswered stays parked. The full
ruling is in the fleet-restart design
([116-fleet-survives-machine-restart-design.md](116-fleet-survives-machine-restart-design.md)).
The part that lands beside this tool: **a by-hand launch — `launch-claude-mac
<seat>` or `launch-claude-ubuntu <seat>` — of a seat with no waiting handoff and
no recorded clean exit tries again to resume its last transcript, and clears the
parked mark.** Measured 2026-09-02: today the supervisor's first launch takes a
waiting handoff, or a `--resume-session-id` that only this tool passes, or else
mints an empty session with the prompt "No handoff exists yet; ask what to work
on" — so launching a crashed seat by hand discards its context, on both
machines. A recorded clean exit still gives that fresh session; the exit record
ruled above is what tells the supervisor which to do. A resume that fails again
under a by-hand launch is reported in the terminal, where the degraded restart
can be offered as ruled. This is a further change to the supervisor's
first-launch path, and the launchers inherit it without change of their own.

## Proposed change, not built: recover into a window

**The problem.** The tool leaves a recovered seat headless. The launcher is
called with a hardcoded `--no-attach`, so the seat lives in tmux with no window
on it. It is still supervised and still recycles — the supervisor runs inside the
tmux session — but nothing is visible.

The user's requirement, 2026-09-02: a restarted session must be interactive and
visible in iTerm2, while still wrapped in its supervisor.

`--no-attach` costs one further thing. A seat born detached has its pane command
fixed at creation, so when its supervisor exits the tmux session closes. A seat
born attached instead drops to an interactive shell in the seat's directory,
where the launcher prints how to relaunch it.

**The change.** A new opt-in flag, `--open-iterm-window-per-seat`, which opens an
iTerm window through `scripts/open-iterm-window-running-command` and runs the
launcher attached inside it.

**The trap in it.** The resume argument reaches the launcher today through the
process environment. That does not survive the move into iTerm: the new session
is a child of iTerm, not of this script, so it inherits iTerm's environment.
Written naively, each window would start a **fresh** seat with no
`--resume-session-id` while looking like a successful recovery, silently
abandoning the crashed transcript. The argument must therefore be encoded into
the command text — `/usr/bin/env 'NAME=value' <absolute launcher path> <seat>` —
which works because iTerm parses its command shell-style and keeps a quoted
`NAME=value` as one word.

**Scope and constraints.**

- macOS only. On any other platform the flag is refused with the reason, not
  silently downgraded to detached. The Ubuntu box is headless and has no iTerm2.
- The launcher must be named by absolute path; iTerm gives a custom command a
  bare PATH.
- Rides on [nedschorus#235](https://github.com/nedschorus/nedschorus/pull/235),
  merged 2026-09-02: its login-shell wrapper is what stops the window dying at
  the launcher's own `command -v tmux` check with nothing printed.
- `--dry-run` prints the command and opens no window. `--ignite-fallback`
  combines with the flag: the window opens either way, and `--ignite-fallback`
  decides whether the seat inside it resumes the transcript or starts fresh from
  the dialog extract.

**What it does not change:** seat selection, the deadness checks, the transcript
choice, or the resume decision.

**Open question:** whether the flag should become the default on the Mac once
proven. Recommended not yet — a default change reaches every existing caller,
including the non-macOS branch.

## Relations

[#116](https://github.com/nedschorus/nedschorus/issues/116) is the fleet-restart
design that consumes this tool at boot; the proposed change above is its build
step 2. [#45](https://github.com/nedschorus/nedschorus/issues/45) owns seat
supervision and the launchers.
[#62](https://github.com/nedschorus/nedschorus/issues/62) owns the blast radius
of one tmux server per machine — this tool makes that blast recoverable rather
than smaller.
