# `fleet` — seat instructions

Read [the seat model](agent-seat-model.md) first: it defines the words used here — pile, seat, session, supervisor, recycle, handoff, walked approval, instruction-class.

Your pile is **the machinery that runs agents**: the launchers, the handoff supervisor and its recycle cycle, seat isolation, and the tooling around keeping several agents straight. You own the *implementation* of that machinery — the scripts and hooks — not the seat model's policy. Which seats exist, how work is grouped, and how a seat is retired are the user's rulings recorded in the model; you build what they require and propose changes rather than making them.

**Your work is done when** the riders below are either built, ruled out, or left with their blocking question written down; the open PRs in your pile are merged or their remaining work is stated; and the user knows what machinery exists and what does not. Then write a handoff and stop.

## The state of the machinery

Accurate as of 2026-08-13. Where something is described as pending, check before relying on it: `git log --oneline -5 origin/main` and `gh pr view <n> --repo nedschorus/nedschorus --json state,mergedAt`.

**On main:**

- **Launchers** — `scripts/launch-claude-ubuntu` (run from the Mac, reaches the box over SSH) and `scripts/launch-claude-mac` (local twin). Attach-or-create by tmux session name; the seat's home is `~/agents/<name>`; the name typed is the whole configuration, with no roster ([nedschorus#45](https://github.com/nedschorus/nedschorus/issues/45)). Both create the seat's home as a checkout on its own branch *before* the session starts, because project settings load from `.claude/` at session start.
- **The supervisor** — `scripts/handoff-supervisor.py`. Launches each session, replaces it when it writes a handoff, exits when its agent stops without one. Before each launch it fetches and fast-forwards the seat's branch when the tree is clean and strictly behind main; on a dirty tree, a diverged branch, or a failed fetch it reports and changes nothing. It never merges automatically, and never runs on the adoption path — changing files under a live agent is the thing this must not do.
- **The recycle trigger** — `scripts/handoff-context-threshold-hook.py`, a `Stop` hook that asks the agent to hand off once context passes 50%.
- **The instruction-file guard** — `.claude/hooks/instruction-file-guard.py`, a `PreToolUse` hook on Edit, Write and NotebookEdit. It blocks changes to `CLAUDE.md`, `CLAUDE.local.md` and `.claude/` unless the user's approval is quoted into `.walk-approved`, which it then consumes. It cannot see writes made through shell commands, so the rule binds regardless of the hook.

**Pending in [PR #58](https://github.com/nedschorus/nedschorus/pull/58):** the seat briefs' md-review corrections, `docs/agents/seat-first-prompt.md`, and the launcher change that creates the home as a checkout. Until it merges, a seat launched from main gets the pre-review versions.

## Your queue

`docs/issues/queue/45-session-seat-and-isolation-riders.md` holds five ideas raised and deliberately not built, each with its reasoning. Read it before proposing any of them.

Rider 1 — a guard enforcing one live session per directory — is **blocked on a question, not on effort**. The obvious detection method (scanning `/proc` for two Claude processes sharing a working directory) was tried on 2026-08-13 and proved unreliable: an attached background session's process reports the directory where `claude attach` was typed, not the directory the session works in, so real collisions hide and viewer windows look like sessions. Before building anything, answer: *what source of truth reports a session's actual working directory?* Candidates worth testing are the session's own transcript, which records it, and asking the session directly. Detection is solved when you can, from outside a session, name its working directory correctly for all three ways a session is created — launched by the supervisor, forked, and started as a background job. Until then the guard should not be built; a guard whose detection is wrong teaches the wrong lesson at the worst moment.

Issues in your pile: [#45](https://github.com/nedschorus/nedschorus/issues/45) (named agents), [#50](https://github.com/nedschorus/nedschorus/issues/50) (worktree file hygiene), [#34](https://github.com/nedschorus/nedschorus/issues/34) (successors must state their git context), [#33](https://github.com/nedschorus/nedschorus/issues/33) (fast-handoff pickup via CLAUDE.md lines is superseded), [#37](https://github.com/nedschorus/nedschorus/issues/37) (injecting a message into an idle session, steering an active one), [#27](https://github.com/nedschorus/nedschorus/issues/27) (console text insertion and stuck-state detection), [#36](https://github.com/nedschorus/nedschorus/issues/36) and [#38](https://github.com/nedschorus/nedschorus/issues/38) (agents watching each other's work).

[PR #52](https://github.com/nedschorus/nedschorus/pull/52) applies fast-handoff findings and touches the design document your machinery implements. The `sanity-checker` seat shepherds it because it came out of that seat's review work; read it before changing the supervisor, so you do not collide.

## The isolation rule, and how far it actually holds

**Two live sessions should never share a working directory.** Forks inherit their parent's directory along with its conversation; background jobs inherit the launching session's. Both are ordinary ways to end up with two agents editing one tree.

Be honest about its status: nothing enforces this today. The detection needed for a guard is the open question above, so the rule is a discipline, not a guarantee, and the *only* mechanical protection is git's refusal to check out one branch in two worktrees — which stops the common case and nothing else.

The remedy when it happens is `EnterWorktree`, a tool available to a running session: it creates a new git worktree on a fresh branch and moves the session into it, conversation intact. The session that should move is the one that arrived second — the fork or the background job — since the original owns the directory. A session that has already edited files there should say so before moving, because those edits stay behind.

## Session-management facts, verified 2026-08-13 on Claude Code 2.1.232

Expensive to learn, easy to lose:

- **Job ids are not session ids.** `claude attach <id>` takes the eight-character job id (the directory names under `~/.claude/jobs/`), not the session UUID.
- **`claude agents`** opens the agent view: `Space` peeks without attaching, `Ctrl+R` renames a session, `Ctrl+T` pins it against the roughly one-hour idle reap, `Ctrl+X` stops it, and `Ctrl+S` groups by directory — which makes the shared-directory hazard visible.
- Both list **only the machine they run on**; the box needs `ssh nedlern@ned-box -t 'claude agents'`.
- **No side-by-side view exists** in the harness. Watching two sessions at once means two terminals.
- **Process uptime is not idle time.** A session showing many hours of `etime` may have been active a minute ago; the honest check is the modification time of its transcript under `~/.claude/projects/<project>/<session-id>.jsonl`.
- Non-interactive SSH shells did not see `~/.local/bin` until `~/.bashrc` was changed on 2026-08-13 to export PATH above its non-interactive early-return. That fix is machine state, not in git, so it will not survive a rebuilt box.

## First action

From the box, where you are: confirm what is on main (`git log --oneline -5 origin/main`), check whether PR #58 has merged, and run the machinery's tests — `python3 scripts/handoff-supervisor-test.py`, `python3 scripts/handoff-write-and-check-supervisor-test.py`, and `python3 .claude/hooks/instruction-file-guard-test.py`. Report what is live, what is pending, and whether the tests pass.

Then ask the user which rider he wants, noting that rider 1 is blocked on its detection question. Do not verify the launchers yourself: they run from the Mac, and you have no shell there — if that needs testing, say so and let him run it.
