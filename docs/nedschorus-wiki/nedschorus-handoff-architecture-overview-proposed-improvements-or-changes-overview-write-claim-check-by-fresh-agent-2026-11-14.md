# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-14)

Assertions of the overview that the claim check against commit 3585a4a99eb79b679deaf345b491a9cdc0e5bc81 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/13e8611e65b3ef14bc42990d6259a113716ae345-2026-11-14T01-08-07-949987Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: `worktree-owner.json`, the owner file: written through the owner-file module (for agent-made worktrees by `agent-seat-worktree-create-with-owner-file.py`, for others by the post-checkout hook, for subagent worktrees by the snapshot hook or clean-worktrees, by restore, by the backfill and the `write` command); read by clean-worktrees and through it the first-prompt list; deleted with the worktree.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> The list misses the path by which Claude Code now makes subagent worktrees, and misses readers. nc-systems/general-tools/agent-seat-worktree-create-with-owner-file-claude-code-worktree-create-hook.py:2-7 `"""Claude Code's WorktreeCreate hook: make the worktree with scripts/agent-seat-worktree-create-with-owner-file.py, so it has an owner file from its first second` … `Claude Code runs this hook in place of its own git worktree add whenever it makes a worktree: for a subagent started with isolation "worktree"`, :19 `A worktree it made carries no Claude Code lock`; registered at .claude/settings.json:17-22. So a subagent's worktree gets its owner file from that hook, not only from the snapshot hook or clean-worktrees. Missing readers: scripts/uncommitted-work-snapshot-hook.py:133 `if owner_file.worktree_owner_file_read(worktree) is not None:` and uncommitted-work-snapshots.py:876 `written = owners.worktree_owner_file_read(worktree)`.
State: open

## E2 — possible problem: an assertion of the overview is contradicted

Claim: The task list under `~/.claude/tasks/`: written by Claude Code and, on ned-box, the crash watcher; completed tasks removed by the writer after comparing with the log-store copy that `transcript-mirror-to-log-store.py` writes.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> The writer list is incomplete. nc-systems/handoff/uncommitted-work-snapshots.py:907-912 `task_list = Path.home() / ".claude" / "tasks" / environment[TASK_LIST_ENVIRONMENT_VARIABLE]` … `task_id = agent_seat_task_list.agent_seat_task_list_new_pending_task_write(` (`restore` opens a task); scripts/clean-worktrees.py:231-240 `Last, it closes the tasks that uncommitted-work-snapshots.py restore opens, in every task list on the machine` … `marks the task completed, adding a line at the end of its description`. The rest is supported: handoff-agent-crash-watcher.py:49-51; writer :826-857; transcript-mirror-to-log-store.py:191.
State: open

## E3 — possible problem: an assertion of the overview is contradicted

Claim: Entry points: the install scripts by a person; the `list` command of `uncommitted-work-snapshots.py` by a person or an agent its initial-agent-instructions send there; the `write` and `show` commands of the owner-file module by a person or a program that makes a worktree.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> The install scripts and the owner-file module's commands are supported (worktree-owner-file-read-and-write.py:29-31, :47-53). The row is incomplete for `uncommitted-work-snapshots.py`: the first prompt also sends the agent to its `restore` and `discard` commands. uncommitted-work-snapshots.py:648 `3. Run the entry's command. To keep one file or more, run restore, ... To keep nothing, run python3 {module} discard <ref>.`, and :1098-1108 `if arguments[:1] == ["restore"]:` … `if arguments[:1] == ["discard"]:`.
State: open
