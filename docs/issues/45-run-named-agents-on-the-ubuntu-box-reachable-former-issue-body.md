---
issue: "[Run named agents on the Ubuntu box, reachable from iTerm2 by name: launch-claude with tmux attach-or-create, and the migration it requires](https://github.com/nedschorus/nedschorus/issues/45)"
---

# Run named agents on the Ubuntu box, reachable from iTerm2 by name: launch-claude with tmux attach-or-create, and the migration it requires

## What is wanted

Type one command and get a named agent running on the Ubuntu box, reachable from the Mac. If that agent is already running — because the terminal window was closed — the same command reconnects rather than starting a second one (user, 2026-08-07).

## What shipped

`scripts/launch-claude-ubuntu <name>`, with a local twin `scripts/launch-claude-mac`. Attach-or-create comes from tmux: closing the window detaches and the agent keeps working; the same command reattaches. The name typed is the whole configuration — there is no roster (ruled 2026-08-07).

The launcher makes the agent's home a **checkout on its own branch before the session starts**, because project settings — status line, recycle hook, instruction-file guard — load from `.claude/` at session start, and an agent booted into a bare directory cannot retrofit them. Git permits a branch in one worktree at a time, which is what stops two agents racing each other's pushes.

## Seat supervision, and recovering a seat that stopped

A seat recycles only while a supervisor watches it: the supervisor waits for the handoff file the agent writes, ends the spent session, and starts its successor. A session started any other way — `claude` or `claude --continue` typed by hand — has no supervisor and can never recycle, and a supervised seat can be orphaned when its supervisor dies mid-run. On 2026-08-18 two Mac seats ran unsupervised for about 25 hours.

Shipped 2026-08-19:

- **`scripts/resupervise-seat.py`** (PR [Unsupervised seats have a recovery procedure, not a hand improvisation (nedschorus#45)](https://github.com/nedschorus/nedschorus/pull/106)) — one command that recovers an unsupervised seat, replacing a hand procedure that left whatever state the operator improvised. It retires the session rather than adopting it: refuses unless the seat's handoff is genuinely waiting, clears the stale tmux session, and relaunches so the supervisor ignites from that handoff. Tests: `scripts/resupervise-seat-test.py`.
- **Both launchers stopped advertising the unsupervised path first** (PR [Launcher after-exit prompt offers the supervised relaunch first, on both twins (nedschorus#45)](https://github.com/nedschorus/nedschorus/pull/107)). The after-exit shell listed `claude --continue` before the supervised relaunch; it now leads with the supervised option and states what the alternative costs.

Live adoption — putting a supervisor onto a still-running session — is built into `scripts/handoff-supervisor.py` (`--adopt-session-id`, `--adopt-process-id`), tested, and reached by nothing. It is deliberately left that way; see the Open section below.

Mechanism, measurements, and the reasoning behind the deferral: `docs/issues/45-remote-named-agent-launch-and-reattach.md` § Seat supervision.

## How work is divided among agents

Ruled 2026-08-14: **group tasks by shared context, not by workload.** Two tasks belong to one seat when doing the first makes the agent smarter about the second. Idle seats are free; confused seats are expensive. Seven seats are defined, two or three run at a time, and a finished seat is resumed by name.

- `docs/agents/agent-seat-model.md` — the model, the seat list, the launch recipe, and how a seat is retired or reused
- `docs/agents/<seat>-instructions.md` — one brief each for the seven seats
- `docs/cross-project/fleet-machine-paths-and-checkouts.md` — full path map for both machines, the three kinds of checkout, and what crosses between them

## Open

- `docs/issues/queue/45-session-seat-and-isolation-riders.md` — five ideas raised and deliberately not built, each with its reasoning. Most notable: a guard enforcing one live session per directory, whose obvious `/proc`-based detection was tried and **proved unreliable** (an attached session's process reports the directory the attach command was typed in). Detection must be solved before that guard is built.
- `docs/issues/queue/45-ubuntu-fleet-open-work-inventory.md` — a 2026-08-14 snapshot of every open thread on the box, its context file, and the seat split. Operational: its PR and issue rows go stale, its thread map does not.
- **The boot report line depends on a manual pull nothing performs.** `scripts/launch-claude-ubuntu` calls `scripts/clean-worktrees.py` by absolute path in the box's main checkout; its update step updates Claude Code only, never that checkout. On 2026-08-16 the box sat two merges behind, so the line errored harmlessly (`|| true`) at every launch until it was pulled by hand to `294fcbf`. Next: decide whether the launcher pulls, or the dependency goes. Related (2026-08-19): `resupervise-seat.py --machine ubuntu` needs itself present in the box checkout and refuses with a message naming that pull, and the launch-time freshening reports success unconditionally, so a failed fetch leaves a stale checkout silently.
Detail, rulings, and the walk record: `docs/issues/45-remote-named-agent-launch-and-reattach.md`



- **`launch-claude-mac` is not symlink-safe** (measured 2026-08-18, merge-lane seat; two Mac seats ran unsupervised ~25 h). The script locates its siblings via `$(dirname "$0")`, so invoking it through a PATH symlink makes that the symlink's directory: the supervisor path dangles (the launched tmux pane dies) and the repository-path uses fail silently behind `|| true`. This is the remaining half of that incident — the prompt-ordering half shipped in PR [Launcher after-exit prompt offers the supervised relaunch first, on both twins (nedschorus#45)](https://github.com/nedschorus/nedschorus/pull/107), and recovery shipped in PR [Unsupervised seats have a recovery procedure, not a hand improvisation (nedschorus#45)](https://github.com/nedschorus/nedschorus/pull/106). Fix queued at the git-infra seat: resolve `$0` through symlinks while keeping the deliberate sibling lookup (macOS `/bin/sh` lacks `readlink -f`, so a resolution loop). Ruled 2026-08-19: no symlink is required for PATH installation, and `git rev-parse --show-toplevel` does not solve it — it answers about the current working directory, which a launcher invoked from anywhere cannot trust. Interim on the Mac: an exec wrapper at `~/.local/bin/launch-claude-mac`, to be deleted once the script is symlink-safe; full analysis machine-local at `~/rca-fleet-supervisor-loss-2026-08-18.md`.

- **Live adoption is built, unreachable, and deliberately left that way** (decided 2026-08-19). Adoption would let a *working* unsupervised agent keep its context and recycle on its own schedule, where `resupervise-seat.py` retires it now — a comfort improvement, not a missing capability. It does not rescue a wedged agent: every supervisor recycles by waiting for a handoff file, so an agent too stuck to write one is equally unrecoverable either way. Two costs blocked it — a hand-started session exposes no session id in its command line, so discovery is an inference from transcript timestamps whose failure is silent (the successor wakes carrying another session's memory); and a successor inherits the supervisor's terminal, so an adopted seat spans two panes until its first recycle, which is the decoy that misread a healthy seat as dead on 2026-08-18. **Build it if unsupervised seats keep occurring after the symlink fix above lands** — that fix and PR [Launcher after-exit prompt offers the supervised relaunch first, on both twins (nedschorus#45)](https://github.com/nedschorus/nedschorus/pull/107) attack the cause. Full reasoning: `docs/issues/45-remote-named-agent-launch-and-reattach.md` § Live adoption.
