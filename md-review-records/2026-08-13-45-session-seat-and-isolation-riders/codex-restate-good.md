<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=restate tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/issues/queue/45-session-seat-and-isolation-riders.md -->

# Session seat and isolation riders

1. This document records follow-up work for nedschorus issue 45, whose scope includes giving agents names and supporting their initial launch and later reattachment.
2. These follow-up items arose during a conversation on August 13, 2026, while people were investigating why several sessions running on the machine called “the box” were difficult to distinguish and why one session had forked while using another session’s Git checkout.
3. Every item described below was discussed and intentionally postponed; nobody is currently implementing any of them.

## 1. A guard that enforces one live session per directory

1. The required invariant is that no two simultaneously live sessions may use the same filesystem directory as their working directory.
2. Forking is identified as the usual way this invariant gets broken because the new session inherits both the parent session’s conversation and its working directory; separately, a background job started from a session also inherits that session’s current working directory, which caused several jobs associated with `~/agents/choirmaster` to appear to be duplicates of one another.
3. The proposed mechanism is a `PreToolUse` hook that runs before `Edit` or `Write`; if it determines that another live Claude session is using the current session’s working directory, it refuses the operation and instructs the user that another session is already live there and that `EnterWorktree` must be called first.
4. Read-only operations and searches would remain permitted because the author considers them incapable of producing conflicting filesystem changes.
5. Reliably determining whether another session shares the directory is still unsolved, and the most apparent detection technique has already proved unsuitable.
6. The initial idea was to scan Linux’s `/proc` process information and compare the current working directories reported for Claude processes, but testing on August 13, 2026 showed that this information is unreliable: for an attached background session, the relevant process reports the directory from which the user ran `claude attach`, rather than the directory in which the attached session actually performs its work; consequently, true directory-sharing sessions can go undetected, while processes that merely display sessions can be incorrectly identified as independent working sessions.
7. A successful detector therefore needs the working directory as understood and used by the session itself, rather than the operating system process table’s directory; the text says this session-level directory appears in the transcript and is also reported correctly when the session is directly asked.
8. The detection problem must be solved before implementing the hook because an inaccurate guard could either miss genuine collisions or block harmless activity, thereby teaching users an incorrect rule or corrective action precisely when they are trying to work.
9. `EnterWorktree` can already move a running session into an appropriate worktree, so the missing capability is not relocation itself but an automatic mechanism that recognizes when relocation is necessary and prompts or forces it.
10. A warning at `SessionStart` was also considered, but it was judged less effective because it would merely advise the user, whereas a `PreToolUse` hook would prevent the conflicting write.
11. The project already uses this general pattern—a pre-tool guard that blocks an operation and gives corrective instructions—in `.claude/hooks/instruction-file-guard.py`.
12. Implementing the guard would require changing `.claude/settings.json`; the parenthetical description “instruction-class” appears to mean this configuration is treated as user-facing instructional material and therefore propagates through a process called the user’s “walk,” although “walk” is project-specific jargon not defined here. Because the hook would execute for every session on the machine, any bug in it would affect all of those sessions rather than only the session that motivated the change.

## 2. A `--directory` flag for the launchers

1. The `scripts/launch-claude-ubuntu` and `scripts/launch-claude-mac` launchers always assign an agent the conventional directory `<agents-root>/<name>` and provide no option for a caller to choose another directory; therefore, a named visible session—called a “seat” here—cannot be launched directly into a worktree that already exists elsewhere.
2. This limitation makes it unnecessarily difficult to turn an existing background session or thread into a visible session occupying a tmux seat.
3. The author estimates that adding this option would require about ten lines of code in each launcher.
4. A discovery made the same day reduces, but does not completely remove, the need for this feature: `claude attach <job-id>` can already display an existing background session in a terminal, so creating or using a formal seat is not the only way to make that session visible; however, this does not provide every benefit of allowing the launchers to adopt an arbitrary existing worktree.

## 3. A CLAUDE.md rule: background jobs push their own branch

1. When several sessions pushed to the same shared agent branch, their competing histories produced commits named `Merge remote-tracking branch 'origin/choirmaster' into choirmaster`, and they also caused at least one non-fast-forward push rejection that forced someone to interrupt ongoing work and rebase.
2. Giving every session its own Git branch would eliminate this entire category of same-branch conflicts: Git already prevents the same branch from being checked out simultaneously in two separate worktrees, so the additional human or documented rule only needs to ensure that each session pushes its own branch rather than a branch shared with another session.
3. This proposed rule belongs in instructional text and would therefore reach the user through the project-specific propagation process called the user’s “walk.”

## 4. md-review the fleet paths reference

1. `docs/cross-project/fleet-machine-paths-and-checkouts.md` was created on August 13, 2026 and is intended to remain useful as an enduring reference document, which places it within the kind of document that the `md-review` skill explicitly says it should review.
2. That review has not yet happened.

## 5. Migrating `choirmaster` to a machine-suffixed name

1. Renaming `choirmaster` to include a machine-specific suffix was considered but deliberately postponed.
2. Because the two machines do not share agent state, an agent with the same name on each machine represents two independent agents rather than a technical name collision; adding a machine suffix would only make the entries easier to distinguish in a combined listing containing agents from multiple machines.
3. Renaming the currently running seat would require moving its Git worktree with `git worktree move`, renaming the files used to hand work off to or from that agent, and restarting the seat; those steps would interrupt an otherwise functioning agent for a benefit regarded as merely cosmetic.
4. The rename should be reconsidered only if viewing a combined cross-machine listing becomes a normal, recurring workflow.

## Session-management facts worth keeping (verified 2026-08-13, Claude Code 2.1.231)

1. The following points are not additional proposed “riders” or follow-up changes; they are operational facts that required substantial effort to discover and could easily be forgotten.
2. A job ID and a session ID are different identifiers and cannot be substituted for one another.
3. `claude attach <id>` expects the eight-character job identifier corresponding to one of the directory names under `~/.claude/jobs/`; it does not expect the session’s UUID.
4. Supplying a session ID instead of a job ID causes attachment to fail with an error saying that no matching job exists.
5. Running `claude agents` opens an agent-management view in which sessions are grouped by state. Within that view, `Space` temporarily inspects the selected entry without attaching to it, `Ctrl+R` renames it, `Ctrl+T` pins it so that the approximately one-hour idle cleanup does not reap it, and `Ctrl+X` stops it; the exact object of “renames” and “stops” is implicit but appears to be the currently selected session or agent entry.
6. `Ctrl+S` changes the view so that sessions are grouped by working directory, making it possible to notice when multiple sessions share a directory.
7. `claude agents` must be executed on the same physical or virtual machine as the sessions the user wants to inspect.
8. Running the command on the Mac displays jobs belonging to the Mac; to display jobs on the remote machine called “the box,” the user must SSH to `ned-box` as `nedlern`, request a terminal, and run `claude agents` there, as shown by `ssh nedlern@ned-box -t 'claude agents'`.
9. The surrounding Claude Code interface or “harness” does not provide a built-in side-by-side display of multiple sessions.
10. To watch multiple sessions at the same time, the user must put each session in its own terminal or in its own tmux window.
11. The elapsed lifetime of a session’s operating-system process does not reveal how long the session has been inactive.
12. A process whose `etime` reports 23 hours may still have performed work only a minute earlier; the reliable staleness indicator identified here is the modification timestamp of that session’s transcript at `~/.claude/projects/<project>/<session-id>.jsonl`, because that timestamp reflects recent transcript activity.
