# Handoff-system steps that agents do by hand and code could do: eight proposals awaiting a decision

Each section below is one proposal, not yet decided, from Question 4, "What should be code", of the cold-read-full-run of `nn-systems/handoff/handoff.system.design.md` on 2026-11-20: `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/handoff.system.design-2026-11-20-6/question-4-what-should-be-code-answer.md`, whose item number each section gives. That cold-read-record's `cold-read-triage.md` gives each item the path of this file. The queue-drain decides each section on its own: a section it promotes becomes a GHI of its own; one it declines is removed from this file with the reason in the commit message. Each section names the GHI ghi-guide-agent found nearest on 2026-11-20; none of them covers the proposal.

Item 2 of the same answer, that a program run the nc-architecture-overview refresh, is not here: GHI [refresh-design: when a system's code lands, bring its design, build-slice plan and overview into line — removing, never revising](https://github.com/nedschorus/nedschorus/issues/670) already designs that program. Item 5 and item 11 went to GHI [The session-handoff writer nn-systems/handoff/handoff-write-and-check-supervisor.py misses background tasks started before the handoff-deferral and reports what it could not list only after writing](https://github.com/nedschorus/nedschorus/issues/3096), and item 7 to GHI [The agent-crash-watcher puts a handoff-supervisor back on an unsupervised agent-seat whose session-handoff is waiting](https://github.com/nedschorus/nedschorus/issues/2541).

## Item 1: record each detached headless job in a file the session-handoff writer reads

The design tells the agent that starts a detached headless agent-session to name the job, its session id, where its output goes and its costs in the next step of its next session-handoff, because otherwise the successor is not told the job exists. A launcher for such jobs could append the job, session id and output path to a file kept for each agent-seat, and the writer, `nn-systems/handoff/handoff-write-and-check-supervisor.py`, could copy that file into numbered fields, as it does for `background-task-N`. Nearest: GHI [run-agent: one CLI to invoke a Claude or Codex agent headlessly from any caller (Python, shell, either runtime)](https://github.com/nedschorus/nedschorus/issues/41), the launcher such a record would extend.

## Item 3: tell the successor how long ago its session-handoff was written

The successor is asked to work out how long ago its session-handoff was written from its `written-at` date. A hook at the successor's start could compute the gap and say "this session-handoff was written N minutes ago", leaving the model only how wary to be. Nearest: GHI [The handoff-supervisor writes the memory review's started mark when it puts the memory-review reminder into the initial-agent-instructions](https://github.com/nedschorus/nedschorus/issues/2545), the same channel into the initial-agent-instructions.

## Item 4: the threshold-hook tells the user itself when its input has no `background_tasks` list

When the threshold-hook's input carries no `background_tasks` list, it hands off at the threshold and tells the agent to tell the user, and to tell him once on the second sighting. The hook could count the sightings in its own state file and write a user-alert itself. Nearest: GHI [Hooks that tell the agent something on stderr with exit 1 are read only by the user, because Claude Code never gives that stderr to the model](https://github.com/nedschorus/nedschorus/issues/1796).

## Item 6: fill a task's `branches` field by code, and flag tasks whose branches are gone

A task records the branches and worktrees it holds in a `branches` field of its metadata, filled by the agent following a reminder, and an abandoned open task keeps its entries off the first-prompt list until someone closes it. A `TaskCreate` hook could fill the field with the current worktree and branch, and `nn-systems/handoff/agent-seat-worktrees-and-branches-with-no-pull-request-first-prompt-list.py` could flag a task whose listed branches are all merged or deleted, or whose worktrees are gone. Nearest: GHI [One design of record for the project's git checkouts, worktrees and branch rules](https://github.com/nedschorus/nedschorus/issues/1121).

## Item 8: detect an agent-session stuck at a Claude Code dialog after a resume or launch

The design's Known holes say a resume can stop at a Claude Code dialog and the agent-seat then sits there until someone looks. After a resume or launch, the handoff-supervisor could check whether the transcript gained a substantive turn within a few minutes, or match known dialog text in `tmux capture-pane`, and raise a task or a user-alert. Nearest: GHI [Console text-insertion + stuck/waiting-state detection (operator tooling; captured from the comms backlog)](https://github.com/nedschorus/nedschorus/issues/27), whose document `27-wedged-session-never-recycles.md` holds the stuck-state design.

## Item 9: check the waiting approval-walk item's page at launch, and the successor's closing line

The successor is told to publish the waiting item's page again when the page is gone, and to end its first message with the item's closing line. The handoff-supervisor could check at launch whether the `#item_page` link answers and tell the successor which case applies, and a Stop hook on the successor's first turn could check that the message ends with the closing line. Nearest: GHI [Make the due-task raise hook decide an approval-walk item as the walk-me-through answer program does](https://github.com/nedschorus/nedschorus/issues/3659).

## Item 10: the writer refuses a next step whose references carry no path or number

The design says every pointer in the next step carries a path, or a repository and GHI number, and leaves that to the agent. The writer could check the next step before writing it, so that every path resolves and every mention of a pull request or GHI carries a number, and refuse naming the reference, as it already refuses an empty next step. Nearest: GHI [Reference-integrity checker: links resolve and cited revision-paths exist — pure-code review check (and the home for what-else-can-code-check)](https://github.com/nedschorus/nedschorus/issues/42), the place ghi-guide-agent names for such checks.

## Item 12: compare the task ids the transcript created with the task-list folder at each session-handoff

The design accepts the risk that Claude Code ignores `CLAUDE_CODE_TASK_LIST_ID` while the folder stays, so a successor sees an empty task list (user-ruled 2026-08-12, which rejected scheduled canary tests). A cheap check at each session-handoff could compare the task ids that `TaskCreate` results in the transcript record with the `<N>.json` files in the task-list folder, and report a mismatch. Because it reverses part of an accepted risk, the user decides it. No GHI covers it: ghi-guide-agent named none closer than GHI 29, whose GHI-MD does not mention the task store or `CLAUDE_CODE_TASK_LIST_ID` (searched 2026-11-20).
