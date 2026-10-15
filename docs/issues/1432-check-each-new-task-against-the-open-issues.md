---
issue: "[Check each new task against the open issues when it is filed, and add a match to that issue's GHI-MD](https://github.com/nedschorus/nedschorus/issues/1432)"
---

# Check each new task against the open issues when it is filed, and add a match to that issue's GHI-MD

## Why

A task on an agent-seat's task list is a file only that agent-seat reads, `~/.claude/tasks/nedschorus-<agent-seat>-tasks/<id>.json` (described at `scripts/agent-seat-due-task-raise-hook.py:6-13`). Other agents never see it, so a task that belongs to an open issue is lost to that issue's builder. In a sweep on 2026-10-14, 63 of the 269 open tasks of 8 agent-seats belonged in an open issue's GHI-MD. The user then ruled on 2026-10-15, in the approval-walk cold-read-research-open-questions-and-skill-reviews-2026-10-14 of agent-seat cold-read-research: "I realized that as tasks are filed we should check them for overlap with GHIs, then daily maint can cover the odd case where the task came before teh GHI." He approved filing this issue on 2026-10-15, with "Y", in the same approval-walk.

## What to build

When an agent files a task with `TaskCreate`, a PostToolUse hook on the matcher `TaskCreate` starts, in the background, `scripts/ghi-info-ask.py` (without `--include-closed`, so only open issues are named) with a question carrying the task's subject and description, and returns at once, because in the sweep a ghi-info question went silent for about 280 seconds and was killed for 6 of the 8 agent-seats.

The background question queues its answer, and the answer reaches the agent with the first prompt or tool call after it arrives, as `scripts/checkout-freshness-catch-up.py --deliver-pending-agent-notes` already delivers its queued notes at the next prompt (`scripts/checkout-freshness-catch-up.py:574`, registered at `.claude/settings.json:36`).

For each open issue the answer names, the agent reads its GHI-MD. If the GHI-MD covers the same matter, not merely the same area, as the ghi-write skill uses the words, and does not already record the task, the agent adds one line for the task with edit-GHI under the heading "Provisional additions (not yet vetted by the user)", adding the heading at the end when it is missing, naming the agent-seat and the date; then, with `TaskUpdate`, it changes the task's subject to "Work on GHI <title> (<url>): <the old subject>". When the answer names no issue, or ghi-info says the question is not about issues, the task stays as it is. When ghi-info returns a question about one of the user's rulings, the agent puts that question to the user.

When the question fails or times out, the background question records the task's agent-seat and id, so that the eighth job of GHI [Daily maintenance in one daily step, starting with a daily check of every wiki page](https://github.com/nedschorus/nedschorus/issues/1058), being added to that GHI-MD now, checks it; that job also checks a task filed before the issue it belongs to existed.

## What exists today

No hook on main reads a `TaskCreate` call: `git grep -n -i taskcreate origin/main -- '*.py' '.claude/*.json'` finds none. ghi-info found no open issue for this check; the nearest is GHI [Move mechanical agent chores into programs and hooks](https://github.com/nedschorus/nedschorus/issues/1036), whose eleven chores do not include it. In the sweep, `scripts/ghi-issue-write.py edit` replaced whole GHI-MDs with editors' older copies and deleted 4 lines other agent-seats had added; agent-seat reboot-test is building the tool's refusal of such an edit. This hook makes such edits frequent, so it waits for that fix.

## Deferred-decisions

1. The cost: one ghi-info question per new task, at the agent-seats' rate of filing tasks, against the day's model limit.
2. Whether a task too vague to match, such as "check with the user", is skipped without a question.
3. Where a failed question is recorded for the daily job to find, and how an entry is cleared once checked.

## Next action

Settle the three open questions with the user; after reboot-test's fix to `scripts/ghi-issue-write.py` merges, build both hooks with their tests and register them in `.claude/settings.json`.
