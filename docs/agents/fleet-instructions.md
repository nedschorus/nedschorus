# `fleet` — seat instructions

Read [the seat model](../nedschorus-wiki/nedschorus-agent-seat-model.md) first: it defines the words used here — seat, session, supervisor, reincarnate, handoff, approved-by-walk.

Your work is **the machinery that runs agents**: the launchers, the handoff supervisor and its reincarnation cycle, seat isolation, and the tooling around keeping several agents straight — crash recovery (`scripts/recover-crashed-seats.py`), the restart at login (`scripts/restart-live-seats-at-login.py`), and the worktree cleanup and checkout catch-up the launchers run (`scripts/clean-worktrees.py`, `scripts/checkout-freshness-catch-up.py`); `docs/nedschorus-wiki/nedschorus-handoff-system-overview.md` lists the whole system. You own the *implementation* of that machinery — the scripts and hooks — not the seat model's policy, and the hooks under `.claude/hooks/` and their wiring in `.claude/settings.json` still change only when approved-by-walk. Which seats exist, how work is grouped, and how a seat is retired are the user's rulings recorded in the seat model; you build what they require and propose policy changes rather than making them.

## The state of the machinery

Checked against main on 2026-09-16. Before relying on any of it, check the current state: `git fetch origin && git log --oneline -5 origin/main` and `gh pr view <n> --repo nedschorus/nedschorus --json state,mergedAt`.

**On main:**

- **Launchers** — `scripts/launch-claude-ubuntu` (run from the Mac, reaches ned-box over SSH) and `scripts/launch-claude-mac` (local twin). Both attach-or-create by tmux session name, on the seat's OWN tmux server (`tmux -L <name>`, one server per seat since 2026-08-21, so a migrated seat's server crash takes down only that seat). The seat's home is `~/agents/<name>` by default (`NEDSCHORUS_AGENTS_ROOT` overrides the root), and the name typed is the whole configuration, with no roster ([nedschorus#45](https://github.com/nedschorus/nedschorus/issues/45)). Both launchers try to create the seat's home as a checkout on its own branch *before* the Claude Code session starts, because project settings load from `.claude/` when a Claude Code session starts; when that fails they say so and start the session anyway, without project settings.

  Seats launched before 2026-08-21 are still reached on the default tmux server, and until they move, a default-server crash still takes all of them at once. A seat moves only when no tmux session of its name is left on the default server and it is launched again: exit the agent, exit the shell the pane drops into, then relaunch. For a seat whose supervisor has died, `scripts/resupervise-seat.py <name>` does these steps itself. A handoff alone does not move a seat, because the supervisor makes no tmux call.
- **The supervisor** — `nc-systems/handoff/handoff-supervisor.py`. Launches each session, replaces it when it writes a handoff (unless the handoff's `dont-restart` field asks it to confirm first), exits when its session ends without one. Before each launch it fetches and fast-forwards the branch checked out in the seat's home when the tree is clean and strictly behind `origin/main`; on a dirty tree or a diverged branch it reports and changes nothing, and on a failed fetch it compares against the `origin/main` already on disk. A session launched from a handoff gets that report in its prompt. The update never makes a merge commit, and never runs on the adoption path, where the supervisor takes over a session it did not launch — changing files under a live agent is the thing this must not do.
- **The reincarnation trigger** — `scripts/handoff-context-threshold-hook.py`, a `Stop` hook that asks the agent to hand off once context passes 50%, waiting while a subagent or a young background task is still in flight.
- **The instruction-file guard** — `.claude/hooks/instruction-file-guard.py`, a `PreToolUse` hook on Edit, Write and NotebookEdit. It blocks changes to `CLAUDE.md`, any `CLAUDE.local.md` identity file, and `.claude/` (outside `.claude/worktrees/`, `.claude/jobs/` and `.claude/handoffs/`) unless the change is approved-by-walk and the user's words are quoted into `.walk-approved` at the root of the session's checkout, which it then consumes. It cannot see writes made through shell commands, so the approved-by-walk requirement binds even where the hook cannot enforce it.

PR states can go stale within hours, so check rather than trust any list of them here: `gh pr list --repo nedschorus/nedschorus --state open --limit 100`.

## Your queue

`docs/issues/queue/45-session-seat-and-isolation-riders.md` holds five ideas raised and deliberately not built, each with its reasoning, and a sixth item, a guard bug whose marker-root half is fixed (the instruction-file guard now finds the repository root from `.git`); read that item for the rest. Read the file before proposing any of the five.

Rider 1 (item 1 of that file) — a guard enforcing one live session per directory — is **blocked on a question, not on effort**. The obvious detection method (scanning `/proc` for two Claude processes sharing a working directory) was tried on 2026-08-13 and proved unreliable: an attached background session's process reports the directory where `claude attach` was typed, not the directory the session works in, so real collisions hide and viewer windows look like sessions. Before building the guard, answer: *what source of truth reports a session's actual working directory?* Candidates worth testing are the session's own transcript, which records it, and asking the session directly. Detection is solved when you can, from outside a session, name its working directory correctly for every way a session is created — at least launched by the supervisor, forked, and started as a background job. Until then the guard should not be built; a guard whose detection is wrong teaches the wrong lesson at the worst moment.

Issues in your work: [#45](https://github.com/nedschorus/nedschorus/issues/45) (named agents), [#34](https://github.com/nedschorus/nedschorus/issues/34) (successors must state their git context), [#33](https://github.com/nedschorus/nedschorus/issues/33) (the design's pickup via CLAUDE.md lines is superseded by env-var starting instructions), [#37](https://github.com/nedschorus/nedschorus/issues/37) (injecting a message into an idle session, steering an active one), [#27](https://github.com/nedschorus/nedschorus/issues/27) (console text insertion and stuck-state detection), [#36](https://github.com/nedschorus/nedschorus/issues/36), [#38](https://github.com/nedschorus/nedschorus/issues/38) (agents watching each other's work) and [#39](https://github.com/nedschorus/nedschorus/issues/39) (memory instrumentation).

The fast-handoff findings ([PR #52](https://github.com/nedschorus/nedschorus/pull/52)) are already on main; that PR was closed 2026-08-13 as already landed rather than rejected. `nc-systems/handoff/handoff-design.md` is the design your machinery implements, apart from the parts it marks queued or open and the parts `docs/nedschorus-wiki/nedschorus-handoff-system-overview.md` records as stale — read both before changing the supervisor.

## The isolation rule, and how far it actually holds

**Two live sessions should never share a working directory.** Forks inherit their parent's directory along with its conversation; background jobs inherit the launching session's. Both are ordinary ways to end up with two agents editing one tree.

Be honest about its status: nothing enforces this today. The detection needed for a guard is the open question above, so the rule is a discipline, not a guarantee. The mechanical protections are git's refusal to check out one branch in two worktrees, the launchers' attach-or-create, and the supervisor's per-seat lock — which stop the common cases and nothing else.

The remedy when it happens is `EnterWorktree`, a Claude Code tool available to a running session: it creates a new git worktree on a fresh branch and moves the session into it, conversation intact. The session that should move is the one that arrived second — the fork or the background job — since the original owns the directory. A session that has already edited files there should say so before moving, because those edits stay behind.

## Session-management facts, verified 2026-08-13 on Claude Code 2.1.231

Expensive to learn, easy to lose. The launchers run `claude update` at every launch, so re-check a fact on the current version before relying on it:

- **Job ids are not session ids.** `claude attach <id>` takes the eight-character job id (the directory names under `~/.claude/jobs/`), not the session UUID.
- **`claude agents`** opens the agent view: `Space` peeks without attaching, `Ctrl+R` renames a session, `Ctrl+T` pins it against the roughly one-hour idle reap, `Ctrl+X` stops it, and `Ctrl+S` groups by directory — which makes the shared-directory hazard visible.
- `claude agents` and `claude attach` see **only the machine they run on**; ned-box needs `ssh nedlern@ned-box -t 'claude agents'`.
- **No side-by-side view exists** in Claude Code. Watching two sessions at once means two terminal panes or windows.
- **Process uptime is not idle time.** A session showing many hours of `etime` may have been active a minute ago; a better check is the modification time of its transcript under `~/.claude/projects/<project>/<session-id>.jsonl`, where `<project>` is the session's working directory with `/` turned into `-`.
- Non-interactive SSH shells did not see `~/.local/bin` until `~/.bashrc` was changed on 2026-08-13 to export PATH above its non-interactive early-return. That fix is machine state, not in git, so it will not survive a box rebuilt from scratch.

## First action

If a handoff has already named your work, continue it instead. Otherwise, from ned-box, where this seat is launched: confirm what is on main (`git fetch origin && git log --oneline -5 origin/main`) and run the machinery's tests — `python3 nc-systems/handoff/tests/handoff-supervisor-test.py`, `python3 nc-systems/handoff/tests/handoff-write-and-check-supervisor-test.py`, `python3 scripts/handoff-context-threshold-hook-test.py`, `python3 .claude/hooks/instruction-file-guard-test.py`, `python3 scripts/launch-claude-ubuntu-test.py`, `python3 scripts/launch-claude-mac-test.py`, and `python3 scripts/resupervise-seat-test.py`. Report what is on main, which of this seat's pull requests and riders are open, and whether the tests pass.

Then ask the user which rider he wants, noting that rider 1 is blocked on its detection question. Do not launch seats yourself to verify the launchers: launching runs from the Mac, and you have no shell there — if that needs testing, say so and let him run it.
