# `fleet` — seat instructions

Your pile: **the machinery that runs agents** — launchers, handoffs, session isolation, and the tooling around keeping several agents straight. Read [the seat model](agent-seat-model.md) first; you own that model's implementation.

## Your open PR

**[PR #57](https://github.com/nedschorus/nedschorus/pull/57)**, branch `launch-claude-machine-named-launchers`, awaiting the Mac-side review seat. It carries: `scripts/launch-claude` renamed to `launch-claude-ubuntu` plus a new `launch-claude-mac` twin (both teach on the no-name case and list running agents); `docs/cross-project/fleet-machine-paths-and-checkouts.md`, the two-machine path reference; the supervisor's branch sync; the session riders; the fleet work inventory; and these seat briefs. **Nothing else should touch those files until it merges.**

## The state of the machinery

- **Launchers** (`scripts/launch-claude-{ubuntu,mac}`): attach-or-create by tmux session name, agent home at `~/agents/<name>`, identity from a `CLAUDE.local.md` there, the handoff supervisor inside. The name typed is the whole configuration — no roster ([nedschorus#45](https://github.com/nedschorus/nedschorus/issues/45)).
- **The supervisor** (`scripts/handoff-supervisor.py`): launches each session, recycles on every handoff, exits when its agent stops without one. Since 2026-08-13 it **syncs the agent's branch with main before each launch** — fetch, then fast-forward only when the tree is clean and strictly behind; otherwise report and change nothing. It never merges (a conflicted merge waiting for an unwoken agent is worse than being behind) and never runs on the adoption path (changing files under a live agent is the one forbidden act).
- **The recycle trigger** (`scripts/handoff-context-threshold-hook.py`): a Stop hook firing at 50% context, wired into project settings 2026-08-12.
- **Guards**: `.claude/hooks/instruction-file-guard.py` blocks edits to CLAUDE.md and `.claude/` machinery without the user's walked approval, consumed through a `.walk-approved` marker.

## Your queue

`docs/issues/queue/45-session-seat-and-isolation-riders.md` holds five ideas discussed and deliberately not built, each with its reasoning. **Read it before proposing any of them** — in particular, rider 1's obvious detection method (a `/proc` scan for two live sessions in one directory) was tried and **proved unreliable**: an attached session's process reports the directory the attach command was typed in, not the directory the session works in. Solve detection before building that guard.

Issues: [#45](https://github.com/nedschorus/nedschorus/issues/45) (named agents), [#50](https://github.com/nedschorus/nedschorus/issues/50) (worktree file hygiene), [#34](https://github.com/nedschorus/nedschorus/issues/34) (successors must state git context), [#33](https://github.com/nedschorus/nedschorus/issues/33) (fast-handoff pickup superseded), [#37](https://github.com/nedschorus/nedschorus/issues/37) (turn/steer equivalents), [#27](https://github.com/nedschorus/nedschorus/issues/27) (console insertion, stuck-state detection), [#36](https://github.com/nedschorus/nedschorus/issues/36) and [#38](https://github.com/nedschorus/nedschorus/issues/38) (mutual oversight, watch-your-back). PR #52 (fast-handoff findings applied) is adjacent — coordinate with `sanity-checker`, which shepherds it.

## Session-management facts, verified 2026-08-13 on Claude Code 2.1.231

Expensive to learn, easy to lose:

- **Job ids are not session ids.** `claude attach <id>` wants the 8-character job id (directory names under `~/.claude/jobs/`), not the session UUID.
- **`claude agents`** opens agent view: `Space` peeks without attaching, `Ctrl+R` renames, `Ctrl+T` pins against the ~1-hour idle reap, `Ctrl+X` stops, `Ctrl+S` groups by directory — which makes the shared-directory hazard visible.
- It lists **only the machine it runs on**; the box needs `ssh nedlern@ned-box -t 'claude agents'`.
- **No side-by-side view exists.** Simultaneous views mean one terminal per session.
- **Process uptime is not idle time.** A session showing 23 hours of `etime` may have been active a minute ago; check its transcript's modification time under `~/.claude/projects/`.
- Non-interactive SSH shells did not see `~/.local/bin` until `~/.bashrc` was fixed on 2026-08-13 to export PATH above its non-interactive early-return.

## Your standing invariant

**Two live sessions must never share a working directory.** Forks inherit the parent's directory along with its conversation; background jobs inherit the launching session's cwd. `EnterWorktree` relocates a running session correctly — the gap is the trigger, not the capability.

## First action

Check whether PR #57 has merged. If it has, verify the renamed launchers work from the Mac and tell the user. If not, report its status and ask which rider he wants next — noting that rider 1 is blocked on solving detection.
