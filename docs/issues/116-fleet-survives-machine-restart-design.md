---
status: design of record; build tracked in nedschorus#116
design-as-of: 2026-09-02
---

# Fleet survives a machine restart (design)

A machine restart destroys every agent seat on it. A seat is a durable named
identity — `MD-skills`, `merge-lane` — a directory under `~/agents/` and a tmux
session of the same name, into which sessions are minted one after another; the
seat outlives any one session. This designs what brings the seats back: how a pending restart is detected, how live seats are told to hand
off, how `restart-live-seats-at-login` decides **which** seats were running, and what
state each returns in. Pair document for
[nedschorus#116](https://github.com/nedschorus/nedschorus/issues/116); the issue
carries the summary and the next actions, this carries the substance.

The recovery half already exists and its resume path is proven on both machines
(2026-09-02) —
[`scripts/recover-crashed-seats.py`](../../scripts/recover-crashed-seats.py)
checks that a seat is dead, picks its last real transcript by a heuristic, and
resumes it under a supervisor. What is missing is everything that decides to call it at boot, and
one property of how it calls the launcher.

## Demonstrated twice

**2026-08-20, ned-box.** `unattended-upgrades` installed a kernel package, set
`/var/run/reboot-required`, and scheduled a reboot 19.5 hours out. At 02:00 it
fired and killed the gatekeeper seat mid-conversation: no handoff written,
nothing restarted it, recovery done by hand from the dead transcript.
`fleet-tmux.service`, a systemd unit on the box and not in this repository, runs
at boot but starts only `fleet-anchor`, the session that keeps the box's default
tmux server alive, and recreates no seats.

**2026-09-02, the Mac.** The user rebooted for the first time in months. No seat
came back on its own. Four Mac seats were live at the stop, transcripts all
stamped 09:31 PDT — `MD-skills`, `merge-lane`, `reboot-test`, `reboot-test-2`.
The supervisor heartbeat files the selection rule below reads were present and
stamping; nothing read them at boot, because `restart-live-seats-at-login` does
not exist. (The supervisor's own liveness check reads them today, so their
format is not free to change.) The user relaunched `reboot-test-2` by hand at
09:59; recovery restored the other three in one command, the first live
exercise of `recover-crashed-seats.py`'s automated resume launch — the
`--resume-session-id` it hands the supervisor — where before that date only the
by-hand `claude --resume` form had been proven (2026-08-21).

That reboot also produced the measured constraint in § Constraints the build
must respect, which `restart-live-seats-at-login` would otherwise have hit; the
same section restates one standing rule.

## Ruled 2026-08-20 — the shape of the procedure

**Detection.** `/var/run/reboot-required`, the file Ubuntu creates when a package
update needs a restart. Runtime staleness gets no trigger; it defers to the
normal recycle.

*Ruled 2026-09-02: the second signal is dropped.* The 2026-08-20 form named two
signals, the second being `needrestart` for daemons holding deleted libraries. It
was never scheduled into the build and never explained again, which all four
reviewers of this document noticed — a half-specified signal in a design of
record invites someone to build it later without knowing why it was in doubt. The
substantive reason for dropping it: a daemon holding a deleted library normally
needs **that daemon** restarted, not the machine, so it is not evidence of a
pending reboot and acting on it could restart the fleet when nothing asked for
it. The file check is the reliable indicator and it is the one that caught the
real incident on the box.

**Handoff on notice.** Tell every live seat to hand off with a five-minute
deadline. **Wait on the handoff file, not on the seat's reply** — the file
exists and its restart-counter is newer than the last one the supervisor
consumed. The handoff format carries no session field, so the counter is the
freshness test, not the session name.

*Open: this step is not yet a specification.* It names no delivery mechanism for
the notice, no liveness test at notice time (the heartbeat rule below is
anchored on the stop, not on the notice), and no behavior when the five-minute
deadline expires with a seat still working. It is built only if the manual path
proves insufficient, and no trigger for that judgment is defined either.

**No handoff? Change the prompt, not the artifact.** Run
[`scripts/handoff-extract-conversation.py`](../../scripts/handoff-extract-conversation.py)
over the dead transcript and open the successor telling it to read that and work
out where it left off. This needs a prompt, not machinery. Proven by hand on the
gatekeeper seat, whose extract ended "Step 2 of 5 ... Ready for the next step?".

**Ruled 2026-09-02: a recovered agent continues; it does not stop and wait.** The
2026-08-20 form of this step told the successor to state its inferred position
**and stop** — not act on it. The shipped recovery has always said the opposite:
its resume prompt ends "then continue the work you were doing," and its degraded
prompt says "Continue from where that dialog ends." Two reviewers found the
conflict independently. The user's ruling settles it in favour of what ships: *"I
want agents to continue."*

The reasoning behind stop-and-wait was that an agent recovering from a crash can
misread its own intent. That is weakest where recovery normally lands — a
successor resuming the **full** transcript has its own context, and none of the
recoveries seen so far has needed to guess — and the cost of the alternative is
one interruption per seat on every
reboot, at the moment the user is least able to absorb it. Three seats were
recovered this way on 2026-09-02 and each continued correctly. If a recovery does
go wrong, tighten the degraded prompt first, since that is the path where the
successor has only a summary to reason from.

**One procedure, pluggable trigger.** The box detects automatically; on the Mac
the trigger is the user announcing a reboot.

*This section originally continued "everything after the trigger is identical on
both machines." That is superseded — see the 2026-09-02 ruling below.*

## Ruled 2026-09-02: the program is named `restart-live-seats-at-login`

This design previously used five names for one program — the boot-time consumer,
the boot-time script, the boot-time relaunch, the restarter, and `restart-claude`
— without ever saying they were the same thing. `restart-claude` was also
actively misleading: it reads as restarting the Claude *runtime*, which is
[#62](https://github.com/nedschorus/nedschorus/issues/62)'s subject, not this
one. The single name is `restart-live-seats-at-login`: what it does, and when.
Checked for collisions 2026-09-02 — nothing in `scripts/`, and no occurrence in
the repository outside this walk's own records.

## Ruled 2026-09-02: two roles, not one procedure

The Mac is the user's terminal for **both** machines: a window on the Mac holds
either a Mac seat or an ssh connection into a seat running on the box. So there
are three distinct failures, not one, and they need different repairs.

- **The Mac restarts.** Every window dies and Mac seats die with it. Box seats
  keep running, untouched — only the windows looking at them are gone. The repair
  is two things at once: recover the Mac's own seats, and re-attach windows onto
  the box's seats, which need no recovery at all.
- **The box restarts or crashes.** Box seats die; the Mac is unaffected, but its
  windows onto those seats are dead ends. Recovery runs on the box, and the Mac
  then re-opens windows onto the recovered seats.
- **One agent on the box crashes.** The same box-side recovery, for that seat
  alone.

**"Visible" therefore never means anything on the box itself.** The box has no
display and opens no window. All visibility lives on the Mac, whichever machine
the seat runs on. The restart is two roles rather than one procedure: **each
machine recovers its own seats; the Mac additionally restores windows, for both
machines.**

**The Mac's window role depends on the box being reachable.** A supervisor writes
its heartbeat on the machine it runs on, so the Mac cannot learn which box seats
were alive by reading its own disk — it must ask the box over ssh. When the box
is unreachable, or answers with nothing usable, the Mac still recovers its own
seats and restores the windows onto them, and reports the box's windows as
missing rather than opening nothing quietly.

## Ruled 2026-08-31 — the heartbeat answers "which seats were running"

**The snapshot only covers a planned restart.** The original relaunch step said
to snapshot which seats were live before restarting. That assumes there is a
moment before; a crash gives none, so the snapshot is stale or absent exactly
when it is needed. Selecting by transcript age instead mis-selects in both
directions: an idle seat looks dead and a long-finished one looks alive.

**The mechanism was already built.**
[`scripts/handoff-supervisor.py`](../../scripts/handoff-supervisor.py) has
`stamp_heartbeat()`, and each supervisor keeps a per-seat file at
`~/.claude/handoffs/<seat>-supervisor-state.json` carrying `last_poll_at`. The
stamp is written on its own cadence, `HEARTBEAT_INTERVAL_SECONDS = 10.0`, inside
a loop that polls every `HANDOFF_POLL_SECONDS = 2.0` — the supervisor's comment
says why: "Stamped on an interval rather than every poll to keep the write rate
low." The two numbers are easy to conflate and the difference decides the rule
below. Per-seat files, so heartbeat writes for *different* seats need no locking
between them; the same seat is protected by the supervisor's own per-seat lock,
not by the file layout. Measured 2026-09-01T00:20Z: MD-skills and merge-lane stamped 8 seconds
earlier; mac-prof 3 days; git-infra and doctrine-queue-drain 4 days; fixer1 10
days; repo-hygiene 15 days.

**Freshness is measured against the newest stamp, not against now.** This is the
part that would otherwise fail silently: after a reboot a week later every stamp
is old in absolute terms and the rule selects nothing. The newest stamp across
all seats approximates the moment the machine stopped, and the live set is those
stamped close enough to it.

**Ruled 2026-09-02: "close enough" is 20 seconds — twice
`HEARTBEAT_INTERVAL_SECONDS`.** The original wording, "within one poll interval",
named neither of the supervisor's two intervals, and the choice is not cosmetic:
the two live seats in the measurement above were stamped **8 seconds apart**, so
a 2-second reading rejects one of them and leaves it dead while a 10-second
reading keeps both. Twice the heartbeat interval rather than exactly one, because
supervisors stamp on independent cycles — a genuinely live seat can trail the
newest stamp by a full interval through timing alone, and at exactly one interval
it falls out by a fraction of a second.

The margins are lopsided, which is worth stating rather than glossing: on the
rejection side the nearest non-live seat is three days away, while on the
inclusion side the whole budget is one heartbeat cycle. That is why the threshold
is expressed as a multiple of that constant and not as a round number. The
earlier claim that the rule is "insensitive to the exact threshold" held only on
the rejection side and is withdrawn. It remains true that the rule works whether
the
reboot happens in five minutes or five weeks.

**Ruled 2026-09-02: the anchor is validated against boot time, and an old anchor
asks rather than acts.** The rule above sets no limit on how old the newest stamp
may be, and that is a hole rather than a detail. If nothing was running when the
machine stopped, the rule still anchors on whatever file happens to be newest —
possibly weeks old — and restarts whatever was alive at that far-off moment. On
the 2026-09-01 measurements, a shutdown with nothing running would have anchored
on `mac-prof` at three days and restarted it: a paid session for a seat the user
had finished with, which is the precise fault that disqualified `--all`.

The bound must not be measured against the current time. Doing so reintroduces
exactly the failure this section was written to avoid: a machine that crashed
with seats running and was rebooted weeks later carries stamps weeks old, and a
clock-relative bound would refuse them all. The question is not how old the newest
stamp is, but **whether anything was running when the machine stopped** — and
those differ only when the machine then sat off for a long time.

Boot time is the reference, and it is cheaply available on both machines:
`sysctl -n kern.boottime` on the Mac, `uptime -s` on the box. Previous *shutdown*
time is not — `last -x reboot shutdown` returns nothing on either (measured
2026-09-02). So:

- **Newest stamp within one hour before boot** → seats were running when the
  machine stopped. Select from them by the 20-second rule above and restart them.
  Anchoring on boot rather than on now also means a restarter that runs late is
  unaffected.
- **Newest stamp long before boot** → either nothing was running at the stop, or
  the machine sat off for a long time. Do not start sessions silently, and do not
  discard them either: report what was found and offer the three outcomes —
  restart, park, or finished. `mac-prof`, stamped three days before the stop,
  lands here rather than being resumed.

This also corrects a claim below. "A seat whose supervisor died while the machine
kept running is not restarted" does not follow from the relative rule on its own:
a supervisor that died one second before shutdown falls inside the window, and if
every supervisor had already died, the last one to die becomes the anchor and
selects itself. The absolute bound closes the second case; the first is the known
over-selection recorded next.

**Two consequences, both wanted.** A seat whose supervisor died while the machine
kept running is not restarted — an unsupervised seat should not be silently
revived. And a seat that exited cleanly seconds before a crash would look live
and be restarted. Deleting the state file on a clean exit was proposed as the
cure and is withdrawn: that file also carries the session id and the consumed
handoff counter, so deleting it discards recovery continuity. The exit record
ruled in the #120 overview covers the case instead: the seat's fresh stamp
still selects it, and the recorded clean exit then routes it to the offer —
restart, park, or finished — rather than to an automatic restart.

**This replaces a hardcoded seat list,** considered and rejected the same day: a
list of seat names in the LaunchAgent goes stale the moment a seat is added and
nothing checks it, while the heartbeat answers from what the supervisors
actually wrote.

**It also replaces `--all` as the boot-time selector.** On 2026-09-02
`recover-crashed-seats.py --all --dry-run` reported it would resume `mac-prof`,
whose newest transcript was five days old (its heartbeat, a different artifact,
was three days old at the 2026-09-01 measurement) and which was not running at
the stop — a paid session for a seat the user had finished with. `--all`
assesses every seat home under the agents root where something has ever run;
the heartbeat rule assesses who was alive. `restart-live-seats-at-login` does its own selection and names the seats.

## Ruled 2026-09-02 — a restored seat must be interactive

The user's requirement, in his words: *"I don't need the exact same terminals to
come back. I do need the sessions to be interactive, which I think means they
should be visible in iterm2 (but properly wrapped in our supervisor, so they can
reincarnate)."*

Two halves, and they come apart:

- **Supervised, so it can reincarnate** — already satisfied. The supervisor runs
  *inside* the seat's tmux session, so a seat recovered headless still recycles
  normally. Detached does not mean unsupervised.
- **Interactive and visible** — not satisfied. `recover-crashed-seats.py` calls
  the launcher with a hardcoded `--no-attach`
  ([`scripts/recover-crashed-seats.py`](../../scripts/recover-crashed-seats.py),
  in `launch_seat`), so recovered seats live in tmux with no window on them.

**The fix belongs in the existing script, not a new one, as an opt-in flag
rather than a change to its default.** The #120 overview specifies it:
`--open-iterm-window-per-seat`, macOS only. It opens an iTerm window per seat
through
[`scripts/open-iterm-window-running-command`](../../scripts/open-iterm-window-running-command)
and runs
[`launch-claude-mac`](../../scripts/launch-claude-mac) `<seat>` inside it,
passing the transcript it chose through the launcher's existing
`LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS` hook — the same hook the
`--resume-session-id` recovery already rides.

**The hook does not cross into the window on its own.** It is an environment
variable, and an iTerm custom command is a child of iTerm, not of the recovery
script, so it inherits iTerm's environment. Written naively, each window would
start a fresh seat with no `--resume-session-id` while looking like a successful
recovery. The value must be encoded into the command text —
`/usr/bin/env 'NAME=value' <absolute launcher path> <seat>` — which works
because iTerm parses its command shell-style and keeps a quoted `NAME=value` as
one word.

**Born attached matters beyond visibility.** A seat born `--no-attach` has its
pane command fixed at creation, so when its supervisor exits the tmux session
closes and the window disappears. A seat born attached drops to an interactive
shell in its own directory, which is where the launcher prints how to relaunch
it. Attaching a window to an already-detached session, as was done by hand on
2026-09-02, gets the visibility but keeps the vanishing pane.

**Restoring the windows is not the same as restoring the seats.** iTerm2 3.6.11
does its own session restoration — it ignores macOS window restoration
(`NoSyncIgnoreSystemWindowRestoration = 1`) and keeps its own
`~/Library/Application Support/iTerm2/SavedState/restorable-state.sqlite`. On
2026-09-02 it reopened the windows and printed `Session Contents Restored`,
which restores scrollback **text** only: each window held a fresh login shell in
`/`, with no claude and no tmux. The user ruled this not useful, and it is worse
than neutral — a restored window is hard to tell from a live one at a glance,
which is what made that morning's failure hard to read off the screen. The
restarter should own the windows.

**Turning iTerm2's restoration off was the companion change, and the user did it
the same day.** The controlling preference is `OpenNoWindowsAtStartup`, `0` →
`1`, the "Only Restore Hotkey Window" position of the window-restoration policy
in iTerm2's Startup settings, identified by diffing
`defaults read com.googlecode.iterm2` before and after the click.
`NoSyncIgnoreSystemWindowRestoration` did not change and was not the key. The
macOS-wide "Close windows when quitting an application" setting was left off
deliberately: it is global to every application and disables restoration
outright rather than letting iTerm2 choose.

## Ruled 2026-09-02: a seat the login restart cannot bring back

The seats that were live at the stop come back without asking. The user's
reasoning: *"they are easy to stop if I want to. Easier than starting."* Only a
seat `restart-live-seats-at-login` cannot bring back — a resume that fails — is
asked about, and it is handled in five steps:

1. **The seat stays down.** Nothing is created. The standing rule that a failed
   restart asks before recreating a seat the degraded way (the #120 overview)
   holds with nobody at the terminal.
2. **It is recorded as parked, with the reason and date** — "resume failed at
   login, 2026-09-02". The record is what keeps the seat findable: at the next
   reboot the heartbeat rule selects only seats stamped near that stop, and a
   seat that never came back is not among them. Parking on the user's word (the
   #120 overview) and parking on failure share one state and differ in the
   recorded reason, which every offer must show so the two read differently.
3. **The restart asks in a window of its own on the Mac**, one line per failed
   seat, the box's included: "<seat> could not be resumed. Recreate it from a
   summary, park it, or finish it?" Recreate makes the fresh session from the
   dialog summary; park leaves it down until asked for; finish retires it. This
   is the same channel the old-anchor case above uses. The Mac can ask because
   the restart runs at login, when the user is present, and already opens
   windows; the box cannot, and its failures reach the Mac window through the
   window role above. Whether the LaunchAgent must start iTerm2 itself remains
   the open question below.
4. **Whatever is left unanswered stays parked.** A closed window loses nothing.
   The next restart of any seat offers the parked ones, each with its reason.
5. **Launching by hand is an answer.** `launch-claude-mac <seat>` or
   `launch-claude-ubuntu <seat>`, with no waiting handoff and no recorded clean
   exit, tries again to resume the last transcript and clears the parked mark.
   Measured 2026-09-02: today that command starts an empty session, because the
   supervisor's first launch takes a waiting handoff, or `--resume-session-id`
   (which only `recover-crashed-seats.py` passes), or else the prompt "No
   handoff exists yet; ask what to work on" — so launching a crashed seat by
   hand discards its context on both machines. A recorded clean exit still gives
   a fresh session. A resume that fails again is reported in the terminal and
   the summary offered there. This reaches into the supervisor's first-launch
   path; the launchers inherit it.

## Constraints the build must respect

**iTerm2 gives a custom command a bare PATH.** Measured 2026-09-02 by running a
probe as the session's own process:

```
PATH=/usr/bin:/bin:/usr/sbin:/sbin:/Applications/iTerm.app/Contents/Resources/utilities
tmux:   NOT-FOUND
claude: NOT-FOUND
pwd:    /
```

`launch-claude-mac` opens with `command -v tmux || exit 1`, so a window opened
this way dies before printing a line, and iTerm reports only *"A session ended
very soon after starting."* Any relaunch that opens an iTerm window with a
custom command hits this. Fixed by wrapping the command in a login shell in
`open-iterm-window-running-command`
([nedschorus#235](https://github.com/nedschorus/nedschorus/pull/235), merged
2026-09-02); `restart-live-seats-at-login` must go through that script rather
than composing its own AppleScript.

**The window opener is the only sanctioned path for opening a window that runs
a command.** Synthesising keystrokes into
iTerm races the user's own typing and corrupted a live window on 2026-08-17;
the project's synthetic-keystroke guard hook blocks that form outright
(nedschorus#27).

## The build, in order

1. **Surface a pending reboot** — check `/var/run/reboot-required` where seat
   launch already runs its update and freshness steps. Covers the accepted cost
   of disabling auto-reboot on the box.
2. **Heartbeat selection** — read every
   `~/.claude/handoffs/<seat>-supervisor-state.json`, take the newest
   `last_poll_at` across all of them, validate it against boot time, and select
   the seats stamped within 20 seconds of it, as ruled above.
3. **Window-opening recovery** — `--open-iterm-window-per-seat` on
   `recover-crashed-seats.py`, specified in the #120 overview, so a recovered
   seat is born attached in its own iTerm window. Independently useful: it is
   how a seat should be recovered by hand too.
4. **`restart-live-seats-at-login`, wired to login** — a LaunchAgent on the Mac,
   `fleet-tmux.service` or a sibling on the box, running 2 and then 3, and
   handling a seat it cannot bring back as ruled above.
5. **Notify-and-wait and the resume prompt** stay as designed above: built only
   if the manual path proves insufficient. Open, as noted there: no trigger for
   that judgment is defined.

## Open questions

- **Does the LaunchAgent need to start iTerm2?** It fires at login, when iTerm2
  may not be running. Either `restart-live-seats-at-login` launches iTerm2
  itself and waits for it, or the trigger hangs off iTerm2's own startup
  instead. Unresolved; it decides whether step 4 is a LaunchAgent at all. What
  is settled (2026-09-02) is the cost of login rather than boot: an unattended
  Mac that boots to the login window restores nothing until someone logs in,
  and the user accepted that — *"I'm OK with it being stuck until I reboot it —
  it rarely crashes or has to be reset."*
- **What does the selector do with a bad state file?** No behavior is defined
  for a state file that is missing, malformed, empty, or future-dated.
  `write_supervisor_state()` is a whole-file write, so a reboot mid-write
  produces exactly that input. Undecided.

## Provenance

Rulings carried from [nedschorus#116](https://github.com/nedschorus/nedschorus/issues/116):
2026-08-20 (walk with the user, item by item), 2026-08-31 (walk item 5,
`retired-seat-cleanup-and-reboot-open-questions`), and 2026-09-02 (this
session, after the Mac reboot). The 2026-09-02 measurements are recorded in that
issue's instance-outcome comment.

Related: [#120](https://github.com/nedschorus/nedschorus/issues/120) owns
`recover-crashed-seats.py`; [#45](https://github.com/nedschorus/nedschorus/issues/45)
owns the launchers; [#27](https://github.com/nedschorus/nedschorus/issues/27)
owns the iTerm window opener and the keystroke rule;
[#62](https://github.com/nedschorus/nedschorus/issues/62) is the Claude
*runtime* updating under a live session, which is a different problem.
