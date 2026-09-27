---
issue: "[nedsmessenger is deferred until nedschorus can build it; where its early context lives](https://github.com/nedschorus/nedschorus/issues/80)"
---

# nedsmessenger is deferred until nedschorus can build it; where its early context lives

nedsmessenger is an early-stage project of the user's, separate from nedschorus. **Ruling (user, 2026-08-17): it is deferred until nedschorus is capable enough to build it.** This issue exists so the deferral and the project's early context are findable in the one place readers look — without it, both live only in a dated inventory snapshot and a conversation.

**What exists today.** Twenty session transcripts on ned-box, from explorations in late July and early August 2026:

- `~/.claude/projects/-home-nedlern-agent-nedsmessenger/` — 18 transcripts; five substantial (0.2–1.4 MB, 2026-08-03/04) titled "Reorganize GitHub repos and GitHub Apps," "Create Samba links for Typora file access," "Review backup alert system improvements," "Merge PR #37 and resolve branch conflicts with main," and a message test; thirteen small 07-28 test runs.
- `~/.claude/projects/-home-nedlern-nedsmessenger-agent-home/` — 2 small transcripts, 07-27, early setup.

Last write 2026-08-04. These directories are project context, not debris: no nedschorus cleanup touches them while this issue is open.

**Next action:** none until the user ends the deferral. When he does: the project gets its own named seat under the fleet model (`docs/agents/agent-seat-model.md`), launched with the machine-named launchers (GHI [Run named agents on the Ubuntu box, reachable from iTerm2 by name: launch-claude with tmux attach-or-create, and the migration it requires](https://github.com/nedschorus/nedschorus/issues/45)), and the builder seat's first orientation is the five substantial transcripts above.

**Close condition:** the project starts (seat launched, work begun) or the user revokes the intention.

Search receipt: `gh issue list --state all --limit 100 --search "nedsmessenger"` returned nothing before this issue was filed; the only prior written trace is one paragraph in `docs/issues/queue/45-ubuntu-fleet-open-work-inventory.md` (2026-08-13 snapshot).


**Correction (2026-08-17, same day):** deferred does not mean fully dormant — the box runs a live component, `nm-adapter.service` ("nedsmessenger adapter, claude bot"), which connects as bot @ubuntu-claude, listens on :8066, and auto-restarts (journal restart counter 9 as of today). The future builder seat inherits this running service as part of the project's existing state; whether it should stay up during the deferral is the boss's call, not decided here.
