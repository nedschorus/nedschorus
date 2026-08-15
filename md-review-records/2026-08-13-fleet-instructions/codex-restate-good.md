<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=restate tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/fleet-instructions.md -->

# `fleet` — seat instructions

1. The `fleet` role is responsible for the infrastructure used to run and organize multiple agents: starting them, transferring work or context between them, preventing their sessions from interfering with one another, and maintaining the tools that distinguish and manage those agents.

2. Before doing that work, the holder of this role must read `agent-seat-model.md`; “you own that model’s implementation” means this role is responsible for making the conceptual seat model actually work in the repository’s code and tooling.

## Your open PR

1. PR #57 is on the branch `launch-claude-machine-named-launchers` and, at the time these instructions were written, has not merged because it is waiting for the role assigned to review or verify its Mac-specific side; the text does not specify whether that role is occupied by a person, an agent, or either.

2. That PR contains all of the following: the rename of `scripts/launch-claude` to `scripts/launch-claude-ubuntu`; a corresponding new `launch-claude-mac` script; behavior in both scripts that provides guidance when no agent name is supplied and shows currently running agents; `docs/cross-project/fleet-machine-paths-and-checkouts.md`, which records relevant paths and checkouts on two machines; the supervisor feature that synchronizes an agent’s branch; the proposed or documented session-related additions called “riders”; an inventory of fleet work; and the instruction briefs for the different seats or roles.

3. Until PR #57 merges, no other task, branch, PR, or agent should modify the files included in that PR, because concurrent edits would overlap with its pending changes.

## The state of the machinery

1. The Ubuntu and Mac launcher scripts use the supplied agent name as a tmux session name: they attach to the existing session with that name or create one if it does not exist. Each named agent uses `~/agents/<name>` as its home directory, obtains its identity or role instructions from `CLAUDE.local.md` in that directory, and runs under the handoff supervisor within the launched environment.

2. Supplying the name is sufficient to derive the agent’s configuration; there is no separate registry or roster in which valid agents must first be declared, as discussed in issue #45.

3. `scripts/handoff-supervisor.py` starts the agent’s sessions, replaces or restarts the active session whenever a handoff occurs, and terminates itself if the agent stops without requesting or producing a handoff.

4. Beginning on August 13, 2026, the supervisor synchronizes the agent’s current branch with `main` before every launch. It first fetches current repository information, then advances the branch by fast-forward only if the working tree has no changes and the branch is strictly behind `main`, meaning it has no divergent or additional commits preventing a pure forward movement. In every other condition—such as a dirty tree, divergence, or a branch that is not behind—it reports the condition and leaves repository state unchanged.

5. The supervisor never performs a merge that reconciles divergent histories, because a conflict could otherwise be left waiting for an agent that is not currently awake or running. It also does not perform synchronization while adopting an already-running agent or session, because changing files beneath a live agent is categorically prohibited. The term “adoption path” is not otherwise defined here, but I take it to mean the path in which the supervisor assumes management of an existing live agent instead of launching a fresh one.

6. `scripts/handoff-context-threshold-hook.py` is the mechanism that triggers recycling when context usage reaches 50 percent. It is registered as a Claude Code `Stop` hook in project settings and has been connected there since August 12, 2026; the sentence does not further explain precisely when the Stop-hook system evaluates the percentage.

7. `.claude/hooks/instruction-file-guard.py` prevents changes to `CLAUDE.md` and machinery under `.claude/` unless the user has explicitly approved those changes through the process called a “walk.” That approval is represented by a `.walk-approved` marker, which the guard uses as its authorization signal; “consumed” suggests one-time use, although the exact marker lifecycle is not stated here.

## Your queue

1. `docs/issues/queue/45-session-seat-and-isolation-riders.md` documents five ideas that were discussed but intentionally left unimplemented, together with the reasoning for not building each one.

2. Before proposing any of those ideas, the `fleet` role must read that queue document. This warning especially applies to rider 1: its seemingly straightforward detection technique—examining `/proc` for two live sessions that appear to use the same directory—was tested and shown not to work reliably, because the process associated with attaching to a session reports the directory from which the attach command was invoked rather than the directory in which the attached session is actually doing its work.

3. A dependable method for detecting shared-directory sessions must be found before implementing rider 1’s guard.

4. The issues relevant to this role are: #45, concerning named agents; #50, concerning keeping files in worktrees properly separated or clean; #34, requiring successor agents to report their Git context; #33, whose fast-handoff pickup work is described as superseded; #37, concerning equivalents for “turn” and “steer” operations; #27, concerning insertion into the console and detection of stuck states; and #36 and #38, concerning agents supervising one another or “watching each other’s backs.”

5. PR #52, which applies findings from the fast-handoff work, is closely related to this role’s work but is being shepherded by the `sanity-checker` role, so `fleet` must coordinate with that role rather than treating the PR as wholly independent work.

## Session-management facts, verified 2026-08-13 on Claude Code 2.1.231

1. The following facts required substantial effort to discover but are easy for future workers to forget, so they are recorded here as durable operational knowledge.

2. A job ID and a session ID are different identifiers and must not be treated as interchangeable.

3. `claude attach <id>` expects the eight-character job identifier that also appears as a directory name under `~/.claude/jobs/`; it does not accept the session’s UUID in that position.

4. `claude agents` opens the agent-management view. Within it, `Space` temporarily inspects an agent without attaching to its session, `Ctrl+R` renames an agent, `Ctrl+T` pins an agent so it is not automatically reaped after roughly one hour of idleness, `Ctrl+X` stops an agent, and `Ctrl+S` groups agents according to working directory. That last grouping makes it possible to notice when multiple agents appear to share a directory.

5. The agent view shows only agents on the same machine where the command is running. To inspect agents on the host named `ned-box`, the documented command is `ssh nedlern@ned-box -t 'claude agents'`, where `-t` requests the terminal needed for the interactive agent view.

6. Claude Code provides no single view that displays two sessions next to each other simultaneously.

7. To watch multiple sessions at the same time, each session must be opened in a separate terminal.

8. The elapsed lifetime of a process does not measure how long its session has been inactive.

9. For example, a session whose process reports an `etime` of 23 hours may still have performed work one minute ago. To estimate its latest activity, inspect the modification time of its transcript under `~/.claude/projects/` rather than relying on process age.

10. Before `.bashrc` was changed on August 13, 2026, non-interactive SSH shells could not find commands in `~/.local/bin`, because `.bashrc` returned early before adding that directory to `PATH`. The fix was to export the required `PATH` before that early return.

## Your standing invariant

1. Under no circumstances may two simultaneously live agent sessions use the same working directory.

2. Creating a fork copies both the parent session’s conversation and its working directory, while a background job starts with the current working directory of the session that launched it; both behaviors can therefore produce the prohibited directory sharing if they are not handled.

3. `EnterWorktree` can correctly move an already-running session into a separate worktree. The missing piece is a dependable event, rule, or detection mechanism that causes this relocation to happen when required, not the underlying ability to relocate the session.

## First action

1. The first task for the holder of this role is to determine whether PR #57 has merged.

2. If it has merged, the role must test from the Mac that the newly renamed launcher scripts function correctly and then report the result to the user.

3. If it has not merged, the role must report the PR’s current status and ask the user which session rider to work on next, while explicitly noting that rider 1 cannot proceed until a reliable detection method has been found.
