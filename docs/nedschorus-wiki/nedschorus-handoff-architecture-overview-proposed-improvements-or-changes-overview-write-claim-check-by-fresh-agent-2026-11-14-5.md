# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-14)

Assertions of the overview that the claim check against commit 8b7af67ce5344461608f1b010f4a1ef2a2845c10 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/79ff41aec0a056755c485ecb8d1cbd4d082ddd85-2026-11-14T11-55-04-444110Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: Invariant: no program but the handoff-supervisor starts or resumes an agent-seat's agent-session, apart from `scripts/ghi-guide-agent-ask.py`, which starts and resumes the ghi-guide-agent's agent-sessions itself.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - docs/nedschorus-wiki/nedschorus-glossary.md:60: "**guide-agent** — ... It is not an agent-seat: a script runs it one question at a time, with no seat-brief and no handoffs". ghi-guide-agent is a guide-agent (glossary:56), so `ghi-guide-agent-ask.py` is not an exception to a rule about agent-seats; the "apart from" clause wrongly implies that ghi-guide-agent is an agent-seat.
> - The rule itself holds. A search for `--resume` in *.py found these callers outside the handoff-system: ghi-guide-agent-ask.py:580, merge-lane-pull-request-claude-reviewer-headless-run-and-review-post.py:394 and run-codex-task-from-brief.py. None of them starts an agent-seat's agent-session.
> - No agent would act wrongly on it: the wording is loose, not wrong.
State: open

## E2 — possible problem: an assertion of the overview is contradicted

Claim: The agent-seat's task list is written by Claude Code, and on ned-box by the agent-crash-watcher; completed tasks are removed by the writer script.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - nc-systems/handoff/uncommitted-work-snapshots.py:34-36: "opens a task naming the branch on the task list ~/.claude/tasks/<CLAUDE_CODE_TASK_LIST_ID>"
> - scripts/clean-worktrees.py:236-245: "it closes the tasks that `uncommitted-work-snapshots.py restore` opens, in every task list on the machine ... marks the task completed, adding a line at the end of its description"
> - Two components of this system also write task files, and the entry leaves them out. Readers are missing too: the first-prompt list (first-prompt list:27-31) and `clean-worktrees.py`'s `-D` check (clean-worktrees.py:158-163).
> - The entry is incomplete rather than misleading on any one action.
State: open
