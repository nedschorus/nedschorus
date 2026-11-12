# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-12)

Assertions of the overview that the claim check against commit e1ed2fbef30bdeca4d5263aea0d0b615ce8fa273 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/f1b38eda0da3b4fe93ef07108c02e3c7472d6d74-2026-11-12T19-14-45-414540Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: Shared state: the agent-seat's task list under `~/.claude/tasks/` is written by Claude Code and, on ned-box, by the agent-crash-watcher; completed tasks are removed by the writer script.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The list of writers is incomplete. nc-systems/handoff/uncommitted-work-snapshots.py:911-912 `task_id = agent_seat_task_list.agent_seat_task_list_new_pending_task_write(task_list, subject, description, metadata)` (restore opens a task on either machine).
> - scripts/clean-worktrees.py:1842-1844 `task = dict(task, status="completed", description=( ... f"\nMarked completed by scripts/clean-worktrees.py at {now}: {reason}."))`
> - Readers are missing too: the first-prompt list reads the list (first-prompt list:27-29).
State: open
