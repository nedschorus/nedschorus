# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-14)

Assertions of the overview that the claim check against commit d98d1e81554cdefccf4b16f1d39b50b1bbf65653 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/f57c91037638ae05276ed23fc9fc601e7b88cb4c-2026-11-14T04-26-52-843322Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: Otherwise it starts fresh when an exit is recorded, and else resumes the agent-seat's last transcript worth resuming.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - nc-systems/handoff/handoff-supervisor.py:2557-2560 `if (not settings.resume_session_id and not settings.first_prompt_wins_over_crashed_transcript and ignition_plan is None and agent_exit_record_from_supervisor_state(state) is None):`
> - With `--first-prompt-file-wins-over-crashed-transcript` it also starts fresh, with no exit recorded. recover-crashed-seats.py:237 passes that flag for its fresh start from a conversation-tail.
> - The sentence leaves this exception out. Component 57's sentence ("starting fresh, from its newest conversation-tail") still lets a reader reconcile it.
State: open

## E2 — possible problem: an assertion of the overview is contradicted

Claim: The agent-seat's task list under `~/.claude/tasks/` is written by Claude Code and, on ned-box, by the agent-crash-watcher; completed tasks are removed by the writer script.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - scripts/clean-worktrees.py:2015-2025 rewrites task files as completed: `task = dict(task, status="completed", ...` … `os.replace(partial, task_file)`. Its docstring at :231-232 says "it closes the tasks that `uncommitted-work-snapshots.py restore` opens, in every task list on the machine".
> - nc-systems/handoff/uncommitted-work-snapshots.py:911 `task_id = agent_seat_task_list.agent_seat_task_list_new_pending_task_write(`
> - The bullet's list of writers leaves out these two programs.
State: open
