---
issue: "[Tasks raise themselves when their due time passes or their prerequisite is met](https://github.com/nedschorus/nedschorus/issues/940)"
---

# Tasks raise themselves when their due time passes or their prerequisite is met

## Why

An agent often promises to act later: "I'll report when PR 927 merges", "I'll hold until the review is in". A promise backed only by a task on the agent-seat's task list still depends on the agent remembering to look at the list at the right moment, and nothing makes it look. Over 30 days of agent messages to the user, measured for GHI [A project style guide: words to avoid, a mechanical checker, and a check on unbacked promises](https://github.com/nedschorus/nedschorus/issues/14), 592 first-person promises were found and only 47.0% were backed by a task, a reminder or a background job in the same response. A memory is no backing either: nothing forces an agent to read one.

A rule holds when something fires at the moment the rule applies. This issue gives a task that something: a due time or a prerequisite that a program checks, and two checkers that raise the task to its agent-seat when the time passes or the prerequisite is met. To raise a task is to put it in front of its agent with the reason, so the agent acts on it now. The user approved this design on 2026-10-02.

## What to build

1. **Two optional fields in a task's `metadata`.** Every agent-seat's tasks are JSON files `~/.claude/tasks/nedschorus-<seat name>-tasks/<id>.json`, and a task may carry a `metadata` object; 57 of the 1,065 task files on the user's Mac carried one on 2026-10-02. Claude Code's TaskCreate and TaskUpdate tools both take a `metadata` argument, so an agent sets these fields with the task tools, never by editing the files. A task may carry either field, both, or neither:
   - `due_utc`: an ISO 8601 time in UTC from which the task should be started, or looked at again.
   - `waits_on`: a list of conditions a program can check, all of which must hold. The first two kinds are `{"pr_merged": <pull request number>}` and `{"issue_closed": <issue number>}`, both in the repository nedschorus/nedschorus. A prerequisite on another task stays in the task's existing `blockedBy` field.

   A task is raised when its due time has passed, or when its `waits_on` conditions all hold; a task carrying both is raised when both hold, and once at its due time if a condition still does not hold, naming that condition, so its agent can chase it. A task whose `blockedBy` tasks are still open is not raised. A task with neither field is a plain task, reviewed by the periodic approval-walks that put an agent-seat's open items to the user, as now.

2. **The idle check, built first.** A Stop hook runs at the end of each of the agent's turns, reads the agent-seat's own task list, and raises every open task that is due, so the agent acts on the task before it goes idle. Claude Code lets a Stop hook refuse the stop with a reason; the reason names each raised task and why, and the agent's turn continues.
   - Due times are read from the task files, with no network call, so the check costs nothing on most turns.
   - Conditions that need a network call, such as whether a pull request merged, are checked at most once every few minutes, each with a short timeout; between checks, the last answer stands.
   - The hook records what it raised, and when it last made each network check, in a state file of its own for the agent-seat. A task is raised once for its due time and once when its conditions come to hold, so the hook cannot keep the agent from stopping turn after turn; a raised task the agent leaves open is raised again only by its next due time.
   - Every fault is silence: a hook error never stops the agent's turn from ending.

3. **The hourly sweep.** A scheduled job, installed through `nc-systems/general-tools/scheduled-jobs-on-each-machine.json` like the jobs already there, runs on each machine, reads the task lists of the agent-seats on that machine, and checks due times and `waits_on` conditions as the idle check does. Its purpose is the agent-seat that is idle, which the idle check cannot reach because an idle agent ends no turns. Two questions are open: how the job tells that an agent-seat is idle, and how it reaches an idle agent-seat. The handoff-supervisor launches agent-sessions but does not type into a running one, and `scripts/synthetic-keystroke-guard-hook.py` refuses synthetic keystrokes, so no route exists yet.

GHI 14's promise check, its item 3, is narrowed to depend on this issue in an edit of the same day: a promise passes when the same turn created or updated a task with a due time or a checkable prerequisite.

GHI [Relaunch stopped agent-seats with open tasks daily](https://github.com/nedschorus/nedschorus/issues/936) also reads agent-seat task lists on a schedule, to relaunch agent-seats that stopped; the hourly sweep and that issue's job may share one reader of the task files.

## Next action

Build the idle check, item 2, as its own pull request; a subagent of the agent-seat merge-lane-backlog is building it. Then answer the hourly sweep's two open questions, and build the sweep.

## Trigger to close

The idle check runs in every agent-seat, the hourly sweep runs on both machines, and a task carrying a due time or a prerequisite is raised to its agent-seat without anyone remembering it.
