---
status: design of record; build tracked in issue [Fleet survives a machine restart without losing seat context: detect, hand off on notice, relaunch at boot, resume from transcript](https://github.com/nedschorus/nedschorus/issues/116)
design-as-of: 2026-09-11
---

# Fleet survives a machine restart (design)

A machine restart destroys every agent seat on it. A seat is a durable named
identity — `MD-skills`, `merge-lane` — a directory under `~/agents/` and a tmux
session of the same name, into which sessions are minted one after another; the
seat outlives any one session. This designs what brings the seats back: how a pending restart is detected, how live seats are told to hand
off, how `restart-live-seats-at-login` decides **which** seats were running, and what
state each returns in. GHI-MD for
issue [Fleet survives a machine restart without losing seat context: detect, hand off on notice, relaunch at boot, resume from transcript](https://github.com/nedschorus/nedschorus/issues/116); the issue
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
normal reincarnation.

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
issue [Claude auto-update purges the running version under live fleet sessions — updates need a drain-or-retain policy](https://github.com/nedschorus/nedschorus/issues/62)'s subject, not this
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

**Ruled 2026-09-14, after both halves of step 4 landed:** the user does not
reconnect box seats by hand. Asked what happens to box seats opened over ssh
from the Mac, the answer was that the seats survive either reboot but the Mac
windows onto them do not come back on their own, and the by-hand recovery is
`launch-claude-ubuntu <seat>`, which attaches to the existing tmux session.
The user's ruling: *"I do not want to ssh open nedbox agents by hand. That
should be in the claude-ubuntu script or whatever we call it."* So the window
role is the next build, and it has two triggers, not one: a Mac login (the
role as designed above), and a box reboot while the Mac stays up, when the ssh
windows drop and nothing on the Mac notices. The second trigger is built into
`launch-claude-ubuntu` (PR [launch-claude-ubuntu reconnects when the box drops, waits out the box's restart, and does not re-prepare a live seat (#116 window role, part 1)](https://github.com/nedschorus/nedschorus/pull/365), 2026-09-14): the attach is a loop, not an
exec, so the window outlives the box's reboot instead of being reopened after
it. ssh exits 255 for a connection-level failure and nothing else; on 255 the
launcher waits and tries again, doubling to 30 s, one line per attempt naming
the seat and Ctrl-C. Any other exit — a detach, the after-exit shell closing,
the seat's tmux server dying — ends the launcher as before, so a window never
recreates a seat that was deliberately stopped. Two remote-side decisions ride
with it: the attach waits out the box's own seat restart while that unit is
still activating (bounded at 180 s), because sshd answers in the same second
the unit starts and a `new-session -A` arriving first would create a fresh
seat that the box's restart then refuses, the transcript resume lost; and the
prepare step (the Claude update, the trust mark, the checkout) runs only when
the seat does not already exist, so N windows reconnecting after a boot do not
each run `claude update` under live sessions (issue [Claude auto-update purges the running version under live fleet sessions — updates need a drain-or-retain policy](https://github.com/nedschorus/nedschorus/issues/62)). Measured
2026-09-15 with a canary seat: a window attached through the launcher, the
connection's sshd process killed on the box, and a new tmux client attached
four seconds later with the window still open; killing the seat's tmux server
instead ended the launcher and the window, with no seat recreated. Restarting
the box's sshd does not drop existing connections, so that is not a test.

The first trigger is built into `restart-live-seats-at-login.py` (PR [restart-live-seats-at-login opens a window onto each live box seat at a Mac login (#116 window role, part 2)](https://github.com/nedschorus/nedschorus/pull/367),
2026-09-15): on the Mac, after its own seats and whatever their verdicts, a
run asks the box over ssh which seats are alive — every session on every
per-seat tmux server, kept only when a seat home of that name exists, the
listing `launch-claude-ubuntu`'s usage prints — and opens an iTerm window
onto each through `open-iterm-window-running-command`, running
`launch-claude-ubuntu` by absolute path, which attaches. The query uses the
launcher's box alias with BatchMode, since under the LaunchAgent there is no
terminal to answer a prompt. A box that does not answer (ssh exit 255) is
retried every 5 s for 150 s, because both machines may have rebooted, then
its windows are reported missing with the by-hand command; that is not a
failure of the run. A window that cannot be opened fails the run. Duplicate
windows on a by-hand rerun are accepted in this version. The run-log line
gains `box_windows`. Measured 2026-09-15 under a throwaway LaunchAgent with
one canary seat live on the box: ssh reached the box with no prompt, the
window opened and attached, the job exited 0 within three seconds. With both
triggers on main and the product plist installed, a Mac logout and login is
the test of the whole role; it has not been run yet.

Two questions the PR [launch-claude-ubuntu reconnects when the box drops, waits out the box's restart, and does not re-prepare a live seat (#116 window role, part 1)](https://github.com/nedschorus/nedschorus/pull/365) reviews left open, both in the launcher: the
reconnect wait doubles to 30 s and is never reset after a successful attach,
so every later drop in that window's life waits 30 s before its first retry
(a slower reconnect, not a lost seat); and after a box boot a reconnecting
window, once the box's restart has finished, creates via `new-session -A` a
seat that restart decided only to *offer* — what a by-hand relaunch did
before, now automatic on every reconnect. Whether the window should stop at
the offer instead is the user's call. Unmeasured by any review: a real box
reboot under an attached window (the measurements were an sshd-session kill
and a tmux-server kill); the next planned box reboot is the measurement.

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

**Ruled 2026-09-15, replacing the second bullet.** Asked whether a window
reconnecting after a box boot should stop at such an offer rather than create
the seat, the user ruled the offer itself away: *"I'd just restart anything that
looks like it was accidentally shut down at roughly the time of shutdown. It's
easy to shut down an agent that isn't useful."* So the seats within the
20-second window of the newest stamp before boot are restarted however long the
machine sat off; the age bound (one hour) is gone from the selector. The cost
the 2026-09-02 rule guarded against — a seat that had been stopped on purpose
long before the shutdown coming back as the "newest" one — is accepted: a seat
restarted wrongly costs one stop, a seat left down costs its work. The
2026-09-11 amendment stands, because it is about a different thing: once seats
have been brought back by hand before this program ran, the newest remaining
stamp is not the stop at all, and those seats are still only offered.

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
ruled in the issue [Crash recovery for seats that died without a handoff: find the last live transcript, resume it supervised](https://github.com/nedschorus/nedschorus/issues/120) overview covers the case instead: the seat's fresh stamp
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
  *inside* the seat's tmux session, so a seat recovered headless still reincarnates
  normally. Detached does not mean unsupervised.
- **Interactive and visible** — not satisfied. `recover-crashed-seats.py` calls
  the launcher with a hardcoded `--no-attach`
  ([`scripts/recover-crashed-seats.py`](../../scripts/recover-crashed-seats.py),
  in `launch_seat`), so recovered seats live in tmux with no window on them.

**The fix belongs in the existing script, not a new one, as an opt-in flag
rather than a change to its default.** The issue [Crash recovery for seats that died without a handoff: find the last live transcript, resume it supervised](https://github.com/nedschorus/nedschorus/issues/120) overview specifies it:
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
   restart asks before recreating a seat the degraded way (the issue [Crash recovery for seats that died without a handoff: find the last live transcript, resume it supervised](https://github.com/nedschorus/nedschorus/issues/120) overview)
   holds with nobody at the terminal.
2. **It is recorded as parked, with the reason and date** — "resume failed at
   login, 2026-09-02". The record is what keeps the seat findable: at the next
   reboot the heartbeat rule selects only seats stamped near that stop, and a
   seat that never came back is not among them. Parking on the user's word (the
   issue [Crash recovery for seats that died without a handoff: find the last live transcript, resume it supervised](https://github.com/nedschorus/nedschorus/issues/120) overview) and parking on failure share one state and differ in the
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
(PR [open-iterm-window-running-command: run the command under a login shell](https://github.com/nedschorus/nedschorus/pull/235), merged
2026-09-02); `restart-live-seats-at-login` must go through that script rather
than composing its own AppleScript.

**The window opener is the only sanctioned path for opening a window that runs
a command.** Synthesising keystrokes into
iTerm races the user's own typing and corrupted a live window on 2026-08-17;
the project's synthetic-keystroke guard hook blocks that form outright
(issue [Console text-insertion + stuck/waiting-state detection (operator tooling; captured from the comms backlog)](https://github.com/nedschorus/nedschorus/issues/27)).

## The build, in order

1. **Surface a pending reboot** — check `/var/run/reboot-required` where seat
   launch already runs its update and freshness steps. Covers the accepted cost
   of disabling auto-reboot on the box.
2. **Heartbeat selection** — read every
   `~/.claude/handoffs/<seat>-supervisor-state.json`, take the newest
   `last_poll_at` across all of them, validate it against boot time, and select
   the seats stamped within 20 seconds of it, as ruled above. Each run records
   what it selected in the run log ruled below, and a later run in the same
   boot takes the stop from there rather than deriving it again.
3. **Window-opening recovery** — `--open-iterm-window-per-seat` on
   `recover-crashed-seats.py`, specified in the issue [Crash recovery for seats that died without a handoff: find the last live transcript, resume it supervised](https://github.com/nedschorus/nedschorus/issues/120) overview, so a recovered
   seat is born attached in its own iTerm window. Independently useful: it is
   how a seat should be recovered by hand too.
4. **`restart-live-seats-at-login`, wired to login** — a LaunchAgent on the Mac,
   `fleet-tmux.service` or a sibling on the box, running 2 and then 3, and
   handling a seat it cannot bring back as ruled above.

   *Built 2026-09-14, the Mac half:* `restart-live-seats-at-login.py` runs
   `recover-crashed-seats.py <seat> --handoff-dir <dir> --open-iterm-window-per-seat`
   for each seat it decides to restart, one subprocess per seat, records the
   seats that came up in the run log's `launched` field, and exits 1 when a
   decided seat did not come back. Two decisions taken in the build: the
   launch runs before the run-log line is appended, so a run killed
   mid-launch leaves no line and the next run in the boot offers rather than
   restarts (a missed restart is preferred to a double launch); and a seat
   that does not come back is reported and left down, because parking it
   with its reason and asking in a window is issue [recover-crashed-seats.py: the six changes ruled 2026-09-02 — exit record, process-identity liveness, parking marker, verified restart, by-hand resume, window](https://github.com/nedschorus/nedschorus/issues/242) change 3, not
   built. `install-restart-live-seats-at-login-launch-agent.py` writes the
   LaunchAgent plist (`com.nedschorus.restart-live-seats-at-login`, RunAtLoad,
   Aqua sessions only, PATH naming `~/.local/bin` and `/opt/homebrew/bin`,
   output to `~/.claude/handoffs/restart-live-seats-at-login-launchd-output.txt`).
   Writing it does not load it; it loads at the next login. Measured
   2026-09-14 by bootstrapping a throwaway label pointed at a throwaway
   handoff directory holding one canary state file stamped 30 s before
   boot: launchd ran the program, it decided `restart`, the recovery tool
   opened an iTerm window (id 1743) and launched the seat fresh, the
   supervisor came up in 17 s, the run log recorded `launched: ["seat-t"]`,
   the job exited 0. No Automation permission prompt appeared: the
   AppleScript ran under launchd without one.

   *Measured 2026-09-17, the product LaunchAgent itself:* it had never been
   loaded. The plist was written 2026-09-14 15:53, after the current login
   session began, and a new agent loads at the next login, so
   `launchctl print gui/501/com.nedschorus.restart-live-seats-at-login`
   answered "Could not find service". `launchctl bootstrap gui/501 <plist>`
   loaded it and RunAtLoad ran it: exit 0, and the first content ever written
   to `~/.claude/handoffs/restart-live-seats-at-login-launchd-output.txt`. It
   launched nothing, correctly — every live Mac seat read `stamped-since-boot`,
   `reboot-test-2` was offered with its by-hand command, and the box line read
   "no live seats, so no windows to open". The job was left loaded. The user
   ruled the same day against the Mac logout-and-login test ("Logging out and
   logging into another account confuses claude"), so that launchd fires this
   job AT LOGIN rests on the plist's `RunAtLoad` and `LimitLoadToSessionType`
   keys, read rather than exercised. That gap stands and is not planned to close.

   *ned-box, 2026-09-17:* the three supervisor state files left there — `prof`
   (2026-08-28), `gatekeeper` (2026-08-25), `gatekeeper-walk-fork` (2026-08-14),
   none of them running — were set aside on the user's word, each renamed with a
   `.set-aside-2026-09-17` suffix, which the selection skips because a seat with
   no state file is not considered. Dry runs on copies first: as they stood the
   next boot restarted `prof`; without `prof`'s file, `gatekeeper`; without both,
   `gatekeeper-walk-fork`. With no age bound (ruled 2026-09-15) the oldest
   surviving state file is selected whenever nothing newer was running at the
   stop, so setting one aside promotes the next. With all three aside the dry run
   answers "no heartbeat before boot: no supervisor was running when the machine
   stopped", and the next box boot restarts nothing. Renaming a file back undoes
   it.

   *Built 2026-09-14, the box half:* `install-restart-live-seats-at-login-systemd-unit.py`
   writes a systemd **user** unit (`restart-live-seats-at-login.service`,
   `Type=oneshot`, `WantedBy=default.target`, PATH set, output appended
   beside the run log) and enables it; lingering is on for the seat user,
   so the user manager starts at boot and runs it without a login. A user
   unit rather than a system unit beside `fleet-tmux.service`: no root, and
   the seats belong to the seat user. The line that matters is
   `KillMode=process`: a oneshot service kills whatever is left in its
   control group when its main process exits, and the seats the program
   launches are detached tmux servers left behind by it. Measured
   2026-09-14 with a probe unit on the box: with `KillMode=process` the
   tmux server was alive after the unit went inactive; without it, no
   server was running. `RemainAfterExit` was rejected because a later stop
   of the unit would then kill every seat it launched. Measured the same
   day with a throwaway unit started by hand: the program decided
   `restart` for a canary seat, the recovery tool launched it fresh on its
   own tmux server, the supervisor came up, the run log recorded
   `launched: ["systemd-unit-canary"]`, the unit went inactive with
   status 0 and the journal noted the tmux server "remains running after
   unit stopped". The product unit was then installed and enabled, with the
   canary left live in the real handoff directory, so the box's one real
   reboot (allowed 2026-09-11) measures the unit firing at boot and a seat
   live at the stop coming back.

   *The box reboot, 2026-09-14 23:33:22Z, on the user's word.* Boot at
   16:34:12 PDT. The user manager reached `basic.target` and started the
   unit at 16:34:20, the same second the system reached `network.target`
   and five seconds before `network-online.target` (16:34:25) — a user
   unit cannot order itself after the system manager's network targets, so
   the program runs before the network is declared online. It decided
   `restart` for the canary (heartbeat 56 s before boot), the recovery tool
   launched it on its own tmux server, the supervisor's first heartbeat
   landed at 16:34:22, the unit finished with status 0 at 16:34:27 and the
   journal logged the tmux server "remains running after unit stopped".
   The run log line carries `"launched": ["systemd-unit-canary"]`; the seat
   was alive and stamping afterwards. Whether the session's first API call
   waited on the network is not measured; the seat came up. `fleet-anchor`
   came back through `fleet-tmux.service` at 16:34:25 as before. The
   canary and its records were then removed. Left unmeasured on either
   machine: only the Mac's real login after a real reboot.
5. **Notify-and-wait and the resume prompt** stay as designed above: built only
   if the manual path proves insufficient. Open, as noted there: no trigger for
   that judgment is defined.

## Open questions

- **Does the LaunchAgent need to start iTerm2?** It fires at login, when iTerm2
  may not be running. Either `restart-live-seats-at-login` launches iTerm2
  itself and waits for it, or the trigger hangs off iTerm2's own startup
  instead. *Decided 2026-09-14 for the build: it is a LaunchAgent, and it
  relies on the opener's `tell application "iTerm"`, which AppleScript
  answers by launching the application when it is not running.* That cold
  start is not yet measured — the 2026-09-14 kickstart test ran with iTerm2
  already open — so the first real login with iTerm2 quit is the
  measurement, and its record goes here. Note also that a logout and login
  does not change the boot instant (`kern.boottime`), so a login test on a
  machine that has not rebooted restarts nothing: the program sees the
  seats it already brought back as written since boot. What
  is settled (2026-09-02) is the cost of login rather than boot: an unattended
  Mac that boots to the login window restores nothing until someone logs in,
  and the user accepted that — *"I'm OK with it being stuck until I reboot it —
  it rarely crashes or has to be reset."*
- **What does the selector do with a bad state file?** No behavior is defined
  for a state file that is missing, malformed, empty, or future-dated.
  `write_supervisor_state()` is a whole-file write, so a reboot mid-write
  produces exactly that input. *Answered by the user 2026-09-11 for a file that
  cannot be read:* "Resume or continue works perfectly 99% of the time, so I'd
  try that." Resume replays the transcript, not this file; the file only says
  whether the seat was running. So an unreadable file is dated by its last
  write instead, which works because only the supervisor writes it. A file cut
  off at the stop therefore counts as running then, and the seat is restarted.
  One damaged long before the stop is judged like any old seat.

  **A missing file is a different case, settled 2026-09-11: the selector does
  not consider such a seat.** The supervisor writes its state file on its first
  launch and never deletes it, so a seat without one never ran supervised.

  That was the standing proposal, and it was nearly replaced by a worse rule.
  The intermediate proposal — offer the seat when it has transcripts, since
  something evidently ran there — was put to the user and approved, then
  withdrawn when it was measured rather than assumed. Every seat on either
  machine with a seat directory and no state file: the Mac's `seat-t` and
  `seatub`, both with no transcripts at all, and ned-box's `ghi-info`, with
  five. `ghi-info` is the only seat the rule would ever have surfaced, and it
  is precisely the wrong one — `scripts/ghi-info-ask.py` runs it as a one-shot
  `claude -p` over ssh, never under `handoff-supervisor.py` and never in tmux.
  It has a seat directory because it follows the agents-root convention and
  transcripts because `claude -p` writes them. So **having transcripts does not
  mean having been a running seat**, and the rule would have offered to restart
  a tool that was never running. The user's word on the corrected measurement
  (2026-09-11) is the ruling above.

  The failure the rule was meant to cover — a supervised seat that lost its
  state file — appears nowhere in the evidence. The divergence that does occur
  is the reverse, and is already handled: five state files on the Mac
  (`doctrine-queue-drain` with 73 transcripts, `git-infra` 57,
  `mac-ubuntu-bridge` 22, `fixer1` and `repo-hygiene` 1 each) have no seat
  directory at all, and are considered and reported `not-running-at-the-stop`.
- **Amended 2026-09-11, in review: after the first restart, offer.** Once any
  seat has been written since boot, the seats that were running at the stop
  have stamped over their heartbeats from before boot, and the newest one left
  is no longer the stop. A later run in the same boot would anchor on a seat
  that died earlier and restart it. So once any seat has been written since
  boot, the selector offers instead of restarting. The cost: every later login
  in the same boot offers whichever seat holds the newest remaining heartbeat
  from before boot.
- **Ruled 2026-09-11, on that cost: a run log.** The user, reading the
  amendment above: *"sounds like we need a log here ... not a single file."*
  So every run that is not a dry run appends one line to
  `<handoff-dir>/restart-live-seats-at-login-log.txt` — the run, the boot, the
  stop, and the verdict per seat — and a later run in the same boot reads the
  stop back from it instead of deriving it from heartbeats the restarted seats
  have since stamped over. A log rather than one overwritten file, so the runs
  of a boot can be read in order afterwards, as
  `recover-crashed-seats-log.txt` is (ruled 2026-08-22). With the stop read
  back, the degradation above does not apply: the recorded stop is the stop
  whatever has been stamped since, so a seat still sitting at it is one that
  did not come back, and it is restarted rather than merely offered. Boots are
  matched as instants, not as strings, because the box reads its boot time
  from `uptime -s` in local time — and within a few seconds rather than
  exactly, because neither machine *stores* its boot instant: the Mac adjusts
  `kern.boottime` when the clock is corrected, and the box computes `uptime
  -s` as now minus `/proc/uptime` and prints whole seconds, so an NTP step of
  half a second flips it, and a step right after boot is exactly when this
  program runs (measured 2026-09-11, in review). The tolerance is far below
  the shortest interval two real boots can be apart. The first line recorded
  for a boot wins, having seen the least disturbed state. **Each line records
  what was launched as well as what was decided** (the user, 2026-09-11, on
  whether to defer the field: *"If so why wait"*): a verdict is a decision,
  and once step 4 lands a decided restart can still fail to come up, so
  `launched` carries null while this program cannot launch at all and the list
  of seats it launched once it can. A cold reader can then tell a seat that
  was never launched from one whose launch failed. **And the report says what
  actually happened** (found in review, fixed 2026-09-11): a run whose append
  failed no longer announces a record that is not there, and a later run in a
  degraded boot no longer says the first one "left no line in the run log"
  when the log holds exactly that line. The log is what an investigator reads,
  so a false sentence beside a true verdict is worse than no sentence. This
  needs the reader to answer two questions rather than one — the stop, and
  whether there was an earlier run at all — because a degraded run leaves a
  line carrying no stop, which makes "no recorded stop" and "no earlier run"
  different states. A null stop is deliberate and settles the matter; a stop
  that is present but corrupt is a line nobody wrote on purpose, and is
  skipped rather than believed. A line that cannot be read is skipped
  and a log that cannot be written is reported and nothing more: a machine
  that has just booted needs its seats back more than it needs the record.
  **A run that cannot tell where the stop was records none:** when the seats
  brought back earlier in this boot have already stamped over the derived
  anchor — the 2026-09-10 shape, where the user recovered seats by hand before
  this program ever ran — the line carries `stop_at` null and keeps what the
  run worked from in `anchor_at`, visible to an investigator and trusted by no
  later run. Otherwise that degraded anchor would be read back as the stop,
  the degradation would be dropped because a stop had been "recorded", and a
  seat that died before the real stop would be restarted. Built 2026-09-11,
  with `--dry-run` reading the log and never writing it.

## Provenance

Rulings carried from issue [Fleet survives a machine restart without losing seat context: detect, hand off on notice, relaunch at boot, resume from transcript](https://github.com/nedschorus/nedschorus/issues/116):
2026-08-20 (walk with the user, item by item), 2026-08-31 (walk item 5,
`retired-seat-cleanup-and-reboot-open-questions`), and 2026-09-02 (this
session, after the Mac reboot). The 2026-09-02 measurements are recorded in that
issue's instance-outcome comment.

Related: issue [Crash recovery for seats that died without a handoff: find the last live transcript, resume it supervised](https://github.com/nedschorus/nedschorus/issues/120) owns
`recover-crashed-seats.py`; issue [Run named agents on the Ubuntu box, reachable from iTerm2 by name: launch-claude with tmux attach-or-create, and the migration it requires](https://github.com/nedschorus/nedschorus/issues/45)
owns the launchers; issue [Console text-insertion + stuck/waiting-state detection (operator tooling; captured from the comms backlog)](https://github.com/nedschorus/nedschorus/issues/27)
owns the iTerm window opener and the keystroke rule;
issue [Claude auto-update purges the running version under live fleet sessions — updates need a drain-or-retain policy](https://github.com/nedschorus/nedschorus/issues/62) is the Claude
*runtime* updating under a live session, which is a different problem.
