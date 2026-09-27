---
issue: "[Fleet survives a machine restart without losing seat context: detect, hand off on notice, relaunch at boot, resume from transcript](https://github.com/nedschorus/nedschorus/issues/116)"
---

# Fleet survives a machine restart without losing seat context: detect, hand off on notice, relaunch at boot, resume from transcript

A machine restart destroys every agent seat on it, and nothing today brings those
seats back or preserves what they were doing.

**Design of record:** [`docs/issues/116-fleet-survives-machine-restart-design.md`](https://github.com/nedschorus/nedschorus/blob/main/docs/issues/116-fleet-survives-machine-restart-design.md), the pair document, landed on main 2026-09-03 through PR [Fleet-restart design: pair document for #116, with the 2026-09-02 rulings](https://github.com/nedschorus/nedschorus/pull/240). It carries every ruling in full with its reasoning and measurements; this body carries the summary and the next actions. The ruling text that used to sit here has moved there, corrected by a cold read and a ten-item walk with the user on 2026-09-02.

**Demonstrated three times.** 2026-08-20 on ned-box: `unattended-upgrades` set `/var/run/reboot-required` and rebooted at 02:00, killing the gatekeeper seat mid-conversation with no handoff, and nothing restarted it. 2026-09-02 on the Mac: the first reboot in months, four seats live, none came back on its own; `scripts/recover-crashed-seats.py` restored three in one command, the first live run of its automated resume launch. 2026-09-10 on the Mac: four seats live, none came back for twelve and a half hours. For the two seats whose successors had never replied, the recovery tool would have resumed the retired parent instead; the successors were resumed by hand. Details are in this issue's comment of 2026-09-11.

Distinct from GHI [Claude auto-update purges the running version under live fleet sessions — updates need a drain-or-retain policy](https://github.com/nedschorus/nedschorus/issues/62), the Claude *runtime* updating under live sessions; this is the *machine* restarting. Launchers: GHI [Run named agents on the Ubuntu box, reachable from iTerm2 by name: launch-claude with tmux attach-or-create, and the migration it requires](https://github.com/nedschorus/nedschorus/issues/45). The recovery tool: GHI [Crash recovery for seats that died without a handoff: find the last live transcript, resume it supervised](https://github.com/nedschorus/nedschorus/issues/120), closed completed 2026-09-02, and its successor GHI [recover-crashed-seats.py: the six changes ruled 2026-09-02 — exit record, process-identity liveness, parking marker, verified restart, by-hand resume, window](https://github.com/nedschorus/nedschorus/issues/242), which holds six ruled changes to it that this program depends on.

## What is ruled — summary; the substance is in the design document

- **Detection:** `/var/run/reboot-required` alone. The `needrestart` signal was dropped 2026-09-02: a daemon holding a deleted library needs that daemon restarted, not the machine.
- **The program is `restart-live-seats-at-login`** (ruled 2026-09-02, replacing `restart-claude` and four descriptive aliases). It runs at login, not at boot; the user accepted that an unattended Mac at the login window restores nothing until someone logs in.
- **Two roles, not one procedure.** Each machine recovers its own seats. The Mac additionally restores windows for both machines, asking the box over ssh which seats are alive, and reports the box's windows missing when it cannot.
- **Which seats were running:** the supervisor heartbeat files, `~/.claude/handoffs/<seat>-supervisor-state.json`. Anchor on the newest stamp before boot and restart the seats stamped within 20 seconds of it (twice `HEARTBEAT_INTERVAL_SECONDS`), however long before boot the anchor is (ruled 2026-09-15, replacing the 2026-09-02 one-hour offer rule).
- **A durable run log, not one overwritten file** (ruled 2026-09-11, the user: *"sounds like we need a log here ... not a single file"*): one line per run, so a later run in the same boot reads the stop back rather than re-deriving it from heartbeats the restarted seats have stamped over. A run unsure of the stop records none. Precedent: `recover-crashed-seats-log.txt`, ruled 2026-08-22.
- **A restored seat is interactive:** born attached in its own iTerm window through `scripts/open-iterm-window-running-command` (login-shell wrapper, PR [open-iterm-window-running-command: run the command under a login shell](https://github.com/nedschorus/nedschorus/pull/235), merged). iTerm2's own window restoration was turned off by the user 2026-09-02 (`OpenNoWindowsAtStartup`).
- **A recovered agent continues;** it does not stop and wait for confirmation.
- **Seats live at the stop come back without asking** — the user: "easy to stop if I want to. Easier than starting." A seat the restart cannot bring back stays down, is parked with the reason and date, and is asked about in the restart's own window on the Mac: recreate from a summary, park, or finish. Unanswered stays parked. A by-hand launch, `launch-claude-mac <seat>` or `launch-claude-ubuntu <seat>`, with no waiting handoff and no recorded clean exit resumes the last transcript.
- **Handoff on notice** (five-minute deadline, waiting on the handoff file's restart-counter) is not yet a specification and is built only if the manual path proves insufficient.

## Already done

`52nedlern-full-auto` on ned-box now sets `Automatic-Reboot "false"` (verified by
`apt-config dump`), patching unchanged. Livepatch is enabled, so deferring a
reboot does not expose the kernel. `Automatic-Reboot-WithUsers "false"` would not
have helped: seats run in tmux and do not register in utmp.

## Next actions

1. **Surface a pending reboot** — check `/var/run/reboot-required` where seat
   launch already runs its update and freshness steps. Covers the accepted cost
   of disabling auto-reboot.
2. **Heartbeat selection — built.** Every state file read, the newest stamp
   validated against boot time, seats within 20 seconds selected:
   PR [restart-live-seats-at-login: select the seats running at the stop from supervisor heartbeats](https://github.com/nedschorus/nedschorus/pull/318). An unreadable
   heartbeat is dated by the file's last write (ruled 2026-09-11). The run log:
   PR [restart-live-seats-at-login: a run log, so a later run in the same boot knows where the stop was](https://github.com/nedschorus/nedschorus/pull/320); its truthful
   reporting, PR [restart-live-seats-at-login: the report says what actually happened to the run log](https://github.com/nedschorus/nedschorus/pull/323).
   **Settled 2026-09-11: a seat with no state file is not considered**, on
   measurement — the only stateless seat with transcripts on either machine is
   the box's `ghi-info`, never supervised (a one-shot `claude -p`).
3. **The recovery tool's changes this program needs**, tracked in GHI [recover-crashed-seats.py: the six changes ruled 2026-09-02 — exit record, process-identity liveness, parking marker, verified restart, by-hand resume, window](https://github.com/nedschorus/nedschorus/issues/242): judge the
   supervisor by its process rather than heartbeat age (change 1) and verify a
   resumed seat came up (change 4), without which the login restart recovers
   nothing in the machine's first minute and misreports; recovery into a window
   (change 6, PR [recover-crashed-seats: --open-iterm-window-per-seat launches a recovered seat attached, in its own window](https://github.com/nedschorus/nedschorus/pull/319),
   merged); the exit record, parking marker and by-hand resume (changes 2, 3,
   5) behind the failed-seat handling above.
4. **`restart-live-seats-at-login`, wired to login — both halves built:**
   PR [restart-live-seats-at-login launches the seats it decides on, and a Mac LaunchAgent runs it at login (#116 step 4)](https://github.com/nedschorus/nedschorus/pull/354), the Mac LaunchAgent
   (installed 2026-09-14; real login unmeasured), and
   PR [A systemd user unit runs restart-live-seats-at-login at boot on the box (#116 step 4, box half)](https://github.com/nedschorus/nedschorus/pull/358), the box systemd unit
   (installed; the box reboot measured 2026-09-14). The window role is merged
   (PR [launch-claude-ubuntu reconnects when the box drops, waits out the box's restart, and does not re-prepare a live seat (#116 window role, part 1)](https://github.com/nedschorus/nedschorus/pull/365),
   PR [restart-live-seats-at-login opens a window onto each live box seat at a Mac login (#116 window role, part 2)](https://github.com/nedschorus/nedschorus/pull/367)). Next: the
   failed-seat handling above.
   **Its tests must not reboot the user's Mac** (ruled 2026-09-11): injected
   boot time and clock, `launchctl kickstart`, a throwaway canary seat.
   The one real reboot can be ned-box's (the user, 2026-09-11), at the cost
   of GHI [recover-crashed-seats.py: the six changes ruled 2026-09-02 — exit record, process-identity liveness, parking marker, verified restart, by-hand resume, window](https://github.com/nedschorus/nedschorus/issues/242)'s `prof` specimen.

**The manual path works today and needs none of this:** after any reboot,
`python3 scripts/recover-crashed-seats.py <seat>...` restores the named seats
with their conversations resumed and supervised. `--dry-run` reports every
decision and launches nothing.

Provenance: rulings of 2026-08-20 and 2026-08-31 (walks with the user) and
2026-09-02 (the walk of the design's cold-read findings); the 2026-09-02
measurements are in this issue's comment of that date. Search receipt
(2026-08-20): `gh issue list --state all --search` for "reboot", "restart seats",
"boot", "handoff relaunch", "supervisor restart" returned only GHI [Claude auto-update purges the running version under live fleet sessions — updates need a drain-or-retain policy](https://github.com/nedschorus/nedschorus/issues/62) and GHI [Run named agents on the Ubuntu box, reachable from iTerm2 by name: launch-claude with tmux attach-or-create, and the migration it requires](https://github.com/nedschorus/nedschorus/issues/45).
