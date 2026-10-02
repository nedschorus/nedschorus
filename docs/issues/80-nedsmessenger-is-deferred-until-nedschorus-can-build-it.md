---
issue: "[nedsmessenger is deferred until nedschorus can build it; where its early context lives](https://github.com/nedschorus/nedschorus/issues/80)"
---

# nedsmessenger is deferred until nedschorus can build it; where its early context lives

nedsmessenger is an early-stage project of the user's, separate from nedschorus. **Ruling (user, 2026-08-17): it is deferred until nedschorus is capable enough to build it.** This issue exists so the deferral and the project's early context are findable in the one place readers look — without it, both live only in a dated inventory snapshot and a conversation.

**What exists today (updated 2026-09-30).** The project's context is its own repository, [nedlern/nedsmessenger](https://github.com/nedlern/nedsmessenger), with a clone on the Mac at `~/Projects/nedsmessenger` (last commit 2026-08-04). The fleet's `mac-claude` GitHub account cannot read the repository, so an agent reads the Mac clone. On ned-box, `/home/nedlern/nedsmessenger/` holds the adapter's code and the compose file. The adapter and the containers are stopped; the end of this file records the stop.

The twenty ned-box session transcripts this file first pointed to are gone. Checked 2026-09-30: on ned-box, `~/.claude/projects/-home-nedlern-agent-nedsmessenger/` holds only a `memory/` folder, and `~/.claude/projects/-home-nedlern-nedsmessenger-agent-home/` no longer exists.

**Kept open 2026-09-30,** in the walk eight-deferrals-with-no-trigger-2026-09-29, item 4 and the summary (minutes: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/eight-deferrals-with-no-trigger-2026-09-29-minutes.md`). The walk recommended closing this issue because the transcripts were gone. The user answered: "I'm still considering building neds messenger. I doubt anything important has been lost as its got its own repo." Asked to confirm, the user said "keep open". At the walk's summary the user answered "B y" to pointing this file at the repository instead of the transcripts, and "A y" to keeping `nm-adapter.service` running on ned-box. The user reversed the "A y" the same day; the end of this file records what was stopped.

**Next action:** none until the user ends the deferral. When he does: the project gets its own named seat under the fleet model (`docs/nedschorus-wiki/nedschorus-agent-seat-model.md`), launched with the machine-named launchers (GHI [Run named agents on the Ubuntu box, reachable from iTerm2 by name: launch-claude with tmux attach-or-create, and the migration it requires](https://github.com/nedschorus/nedschorus/issues/45)), and the builder seat's first orientation is the nedsmessenger repository. Today the fleet can read that repository only through the Mac clone, `~/Projects/nedsmessenger`.

**Close condition:** the project starts (seat launched, work begun) or the user revokes the intention.

Search receipt: `gh issue list --state all --limit 100 --search "nedsmessenger"` returned nothing before this issue was filed; the only prior written trace is one paragraph in `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/cold-read-research/45-ubuntu-fleet-open-work-inventory-retired-from-issues-queue-2026-10-02.md` (2026-08-13 snapshot).


**Correction (2026-08-17, same day; true until the stop on 2026-09-30, recorded below):** deferred does not mean fully dormant — the box runs a live component, `nm-adapter.service` ("nedsmessenger adapter, claude bot"), which connects as bot @ubuntu-claude, listens on :8066, and auto-restarts (journal restart counter 9 as of today). The future builder seat inherits this running service as part of the project's existing state; whether it should stay up during the deferral is the boss's call, not decided here.

**Decided 2026-09-30, then reversed the same day.** The correction above left one question to the user: whether `nm-adapter.service` stays up during the deferral. The summary's "A y" first answered that the service keeps running. Later that day the user said: "let's shut down the extra junk running on ned-box, including the stuff for neds-messenger." The eight-deferrals minutes cited above record both answers in their summary row.

So nedsmessenger is stopped on ned-box. Three things were done on 2026-09-30:

- `nm-adapter.service` was stopped and disabled.
- The nedsmessenger compose project was stopped: the containers `nedsmessenger-mattermost-1` and `nedsmessenger-postgres-1`. The project's six named volumes are kept.
- The nightly backup line in the `nedlern` crontab was commented out. The crontab as it stood before the edit is `nedlern@ned-box:/home/nedlern/nedschorus-logs/crontab-before-nedsmessenger-stop-2026-09-30.txt`.

Checked on ned-box 2026-10-01: `systemctl is-enabled nm-adapter.service` prints `disabled` and `systemctl is-active nm-adapter.service` prints `inactive`; `docker ps` lists no running container and `docker ps -a` shows both containers exited; `docker volume ls` lists six volumes named `nedsmessenger_…`; `crontab -l` shows the backup line commented out.

To start nedsmessenger again: run `docker compose start` in `/home/nedlern/nedsmessenger`, run `sudo systemctl enable --now nm-adapter.service`, and uncomment the backup line with `crontab -e`.
