<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=restate tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/issues/queue/45-session-seat-and-isolation-riders.md -->

# Session seat and isolation riders

1. This document is queued under GitHub issue `nedschorus#45`, which concerns named agents, launching them, and reconnecting to them.

2. The document was created during a conversation on 2026-08-13 about why several sessions on “the box” were difficult to distinguish and why one session had ended up in another session’s checkout.

3. Every item below was intentionally discussed but left undone; none is currently being worked on.

## 1. A guard that enforces one live session per directory

1. The required invariant is that no two live sessions may use the same working directory.

2. Forking is a common way to violate this rule because a fork inherits both its parent’s working directory and its conversation. A background job started from a session also inherits that session’s current working directory, and this inheritance caused several jobs to appear to be duplicate sessions in `~/agents/choirmaster`.

3. The proposed implementation is a `PreToolUse` hook for `Edit` and `Write` that refuses the operation if another live Claude process is using the same working directory as the current session. Its refusal should explain the remedy: another session is already active there, so the user should call `EnterWorktree` first.

4. Read and search operations should remain permitted because they do not create the same kind of collision.

5. Determining how to detect the other session is unresolved, and the most obvious detection approach has already proved unusable.

6. The first proposed approach was to scan `/proc` and compare the current working directory of each Claude process. That approach was tested on 2026-08-13 and found unreliable: for an attached background session, the process reports the directory from which the `claude attach` command was entered, rather than the directory where the session actually works. Consequently, genuine duplicate-directory sessions can go undetected, while terminal windows merely viewing sessions can be incorrectly treated as sessions themselves.

7. A reliable detector must obtain the working directory from the session’s own perspective, either from its transcript or by asking the session directly, rather than relying on the operating-system process table.

8. This detection problem must be solved before implementing the hook because a guard that detects incorrectly could be more harmful than having no guard: it could give the user an incorrect explanation and recommend the wrong fix at the wrong time.

9. `EnterWorktree` already knows how to move a running session to the correct worktree, so the missing capability is not relocation; what is missing is a condition that triggers that relocation or otherwise prompts it.

10. A `SessionStart` warning was considered inferior because it merely gives advice, whereas the `PreToolUse` version prevents the conflicting operation.

11. The project already uses this same kind of hook pattern in `.claude/hooks/instruction-file-guard.py`.

12. Implementing this requires adding an entry to `.claude/settings.json`. Because this is instruction-class configuration, that change is delivered through the user’s walk.

13. A `PreToolUse` hook runs for every session on the machine, so any defect in the hook affects all sessions on that machine.

## 2. A `--directory` flag for the launchers

1. `scripts/launch-claude-ubuntu` and `scripts/launch-claude-mac` conventionally put each agent in `<agents-root>/<name>` and do not accept a directory argument. Therefore, a seat cannot use an already-existing worktree. This makes it unnecessarily difficult to turn a background thread into a visible tmux seat. The estimated implementation size is about ten lines in each launcher.

2. The case for this feature became weaker, though it was not eliminated, because it was discovered that `claude attach <job-id>` can already open a background session in a terminal. Thus, creating a seat is not the only way to make that session visible.

## 3. A CLAUDE.md rule: background jobs push their own branch

1. Multiple sessions pushed to one shared agent branch. That produced merge commits such as `Merge remote-tracking branch 'origin/choirmaster' into choirmaster` in the branch history, and it also caused a non-fast-forward rejection that required a rebase during a task.

2. Giving each session its own branch eliminates this category of problem. Git already prevents the same branch from being checked out in two worktrees, so the remaining rule only needs to specify which branch each session is allowed or expected to push.

3. This belongs to instruction-class text, so it is delivered through the user’s walk.

## 4. md-review the fleet paths reference

1. `docs/cross-project/fleet-machine-paths-and-checkouts.md` was written on 2026-08-13 and is intended to remain as a long-term reference, which matches the stated target of the `md-review` skill.

2. The document has not yet been reviewed.

## 5. Migrating `choirmaster` to a machine-suffixed name

1. Migrating the name was considered and postponed.

2. Because the two machines do not share agent state, an agent named `choirmaster` on one machine and an agent with the same name on the other machine are unrelated agents, not conflicting copies. Adding a machine suffix would only make the names easier to distinguish in a listing that combines both machines; it would provide no other benefit.

3. Renaming the live seat would require moving its Git worktree with `git worktree move`, renaming its handoff files, and restarting it. Those actions would interrupt an agent that is currently working, and the benefit would be merely cosmetic.

4. The naming question should be reconsidered only if cross-machine agent listings become something people routinely inspect.

## Session-management facts worth keeping (verified 2026-08-13, Claude Code 2.1.231)

1. These facts are not proposed riders; they were learned through difficulty and could easily be forgotten.

2. A job ID and a session ID are different identifiers.

3. `claude attach <id>` expects the eight-character job ID, which corresponds to directory names under `~/.claude/jobs/`, rather than the session UUID. If the session UUID is supplied instead, attachment fails with `No job matching`.

4. Running `claude agents` opens the agent-management view. It lists every session grouped by state; `Space` previews a session without attaching to it; `Ctrl+R` renames it; `Ctrl+T` pins it so it is protected from the approximately one-hour idle cleanup; and `Ctrl+X` stops it. `Ctrl+S` groups sessions by directory, making the shared-directory hazard visible.

5. `claude agents` must be run on the machine whose sessions are being inspected. Running it on the Mac lists the Mac’s jobs; to inspect the box, the command must be run there through `ssh nedlern@ned-box -t 'claude agents'`.

6. The harness provides no side-by-side session view. To view multiple sessions at the same time, each session must occupy its own terminal or tmux window.

7. A process’s total uptime does not tell you how long it has been idle.

8. A session with an elapsed process time of 23 hours may still have been active only a minute ago.

9. The reliable way to determine whether a session is stale is to inspect the modification time of its transcript at `~/.claude/projects/<project>/<session-id>.jsonl`.
