<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=restate tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/fleet-instructions.md -->

## `fleet` — seat instructions

1. Your assigned area is the machinery used to run agents: launchers, handoffs, isolated sessions, and tools for managing multiple agents without confusing them.
2. Read `agent-seat-model.md` before proceeding; you are responsible for implementing that model.

## Your open PR

1. Your open change is PR #57 on branch `launch-claude-machine-named-launchers`, and it is waiting for review by the Mac-side seat.
2. The PR renames `scripts/launch-claude` to `launch-claude-ubuntu`, adds a corresponding `launch-claude-mac`, makes both explain the no-name case and display running agents, adds the two-machine path reference, adds supervisor branch synchronization, adds the session riders, adds the fleet work inventory, and adds these seat briefs.
3. No other change should modify any of those files before the PR is merged.

## The state of the machinery

1. The Ubuntu and Mac launchers either attach to a tmux session with the requested name or create such a session; the agent’s home is `~/agents/<name>`, its identity comes from the `CLAUDE.local.md` in that directory, and the handoff supervisor runs inside the session. The supplied name determines the entire configuration, because there is no separate roster of agents.
2. The handoff supervisor starts each session, recycles it after every handoff, and exits when its agent stops without another one to launch; I understand “one” to mean a successor or replacement agent, although the sentence does not define that word more precisely.
3. Since 2026-08-13, before launching an agent, the supervisor synchronizes that agent’s branch with `main`: it fetches first, then fast-forwards only if the working tree is clean and the branch is strictly behind `main`; in every other condition it reports the situation and makes no change.
4. The supervisor never performs merges, because a merge conflict left waiting for an agent that has not been awakened is considered worse than leaving the branch behind.
5. The supervisor does not perform this synchronization when adopting an existing session, because changing files underneath a currently live agent is the one explicitly forbidden action.
6. The recycle trigger is `scripts/handoff-context-threshold-hook.py`, a Stop hook that fires when context usage reaches 50%; it was connected to the project settings on 2026-08-12.
7. `.claude/hooks/instruction-file-guard.py` prevents edits to `CLAUDE.md` and the machinery in `.claude/` unless the user has given “walked approval.” I understand that phrase to mean approval granted through the user-guided approval process, and the `.walk-approved` marker is how that approval is recorded and consumed.

## Your queue

1. `docs/issues/queue/45-session-seat-and-isolation-riders.md` contains five ideas that were discussed, intentionally left unimplemented, and documented with the reasoning behind not building them.
2. Read that file before proposing any of those ideas. In particular, rider 1’s seemingly obvious detection method—a `/proc` scan looking for two live sessions in one directory—was attempted and found unreliable because an attached session’s process reports the directory from which the attach command was entered, rather than the directory in which the session is actually working.
3. A reliable detection method must be found before the corresponding guard is implemented.
4. The tracked issues are #45 about named agents, #50 about worktree file hygiene, #34 about requiring successors to state their Git context, #33 about superseded fast-handoff pickup, #37 about equivalents for turning or steering, #27 about console insertion and detecting stuck states, and #36 plus #38 about mutual oversight or “watch-your-back” behavior.
5. PR #52, which applies the fast-handoff findings, is related but separate; coordinate with `sanity-checker`, the seat responsible for shepherding that PR.

## Session-management facts, verified 2026-08-13 on Claude Code 2.1.231

1. These facts are difficult and expensive to discover but easy to forget.
2. A job ID is different from a session ID: `claude attach <id>` requires the eight-character job ID, found in directory names under `~/.claude/jobs/`, rather than the session UUID.
3. Running `claude agents` opens the agent view: `Space` previews an agent without attaching to it, `Ctrl+R` renames it, `Ctrl+T` pins it so the roughly one-hour idle reaper does not remove it, `Ctrl+X` stops it, and `Ctrl+S` groups agents by directory, thereby making the shared-directory danger visible.
4. `claude agents` displays agents only from the machine on which it is run; to inspect `ned-box`, run `ssh nedlern@ned-box -t 'claude agents'`.
5. There is no side-by-side session view, so viewing multiple sessions simultaneously requires one terminal for each session.
6. A process’s uptime is not the same as its idle duration: a session with 23 hours of `etime` might still have been active one minute ago, so its transcript’s modification time under `~/.claude/projects/` must be checked.
7. Non-interactive SSH shells initially did not include `~/.local/bin` in `PATH`; this was fixed on 2026-08-13 by making `.bashrc` export that path before its early return for non-interactive shells.

## Your standing invariant

1. Two simultaneously live sessions must never use the same working directory.
2. Forked sessions inherit both their parent’s directory and its conversation, while background jobs inherit the current working directory of the session that starts them.
3. `EnterWorktree` can correctly move an already-running session to another location; the problem is the interval that triggers the hazard, not an inability of `EnterWorktree` to relocate the session.

## First action

1. Determine whether PR #57 has been merged.
2. If it has merged, verify the renamed launchers from the Mac and report the result to the user.
3. If it has not merged, report its status and ask the user which rider should be handled next, while noting that rider 1 cannot proceed until detection is solved.
