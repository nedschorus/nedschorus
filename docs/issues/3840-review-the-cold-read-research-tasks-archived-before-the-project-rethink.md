---
issue: "[Review the cold-read-research tasks archived before the project rethink](https://github.com/nedschorus/nedschorus/issues/3840)"
---

# Review the cold-read-research tasks archived before the project rethink

On 2026-11-17 the user asked agent-seat cold-read-research to set aside its older tasks: "I think you should archive most of your tasks, the ones that preceded my desire to rethink this project, which maybe was a week ago. When you do archive them, make a GHI to review them some time in the future." His rethink of the project began about 2026-11-13, when he started writing the NedsNodes overview that is now `README.md`.

85 tasks were archived: every task on cold-read-research's task list numbered below 390. Each was marked completed, and a note at the start of its description says it was archived and where the copy is. Tasks 390 to 398, created after the rethink began, stay open on the list.

The archive is in the log-store:

- the index, one line per archived task with its number, its status before archiving and its subject: `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/cold-read-research/task-archive-2026-11-17/archived-tasks-index-2026-11-17.md`
- every task's full record as it stood before archiving, one JSON file per task: `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/cold-read-research/task-archive-2026-11-17/task-files/`. That directory also holds copies of tasks 390 to 398, for reference only; they are not part of this review.

Why a review is needed: the archived tasks were set aside, not judged. Some may still matter after the rethink, some will be obsolete, and some name pull requests, worktrees, branches or other agent-seats that are still waiting on them. Before the review, nobody has checked which is which.

When: the user set no date. Do the review when he asks for it, or bring it to him once the project rename from nedschorus to nedsnodes has finished, since the rename changes the paths and names many of these tasks cite. The rename's own task, task 398 on cold-read-research's task list, ends by bringing this issue to the user. A review done before the rename reads each cited path under its old name.

Next action: first list, for each archived task, the pull requests, branches, worktrees and agent-seats it cites, with each one's current state: open, merged or closed for a pull request, present or gone for a branch or worktree. That listing is lookup work, best done by a short program over the JSON files. Then group the tasks by subject, so the user rules on a group at a time rather than 85 single items, and give each task one of these outcomes in an approval-walk with the user:

- drop it, because the rethink or later work made it obsolete
- revive it: when cold-read-research should still do it, create it again on cold-read-research's task list from its JSON file, without the archive note
- hand it to another agent-seat, by a message carrying its subject, description and citations, when that agent-seat should own it now
- turn it into a GHI of its own, when the work needs a document beyond a task line, such as a design

For each task with a live pull request, branch or worktree, the walk also rules what happens to it, and the reviewer then carries that out: kept for the new owner, closed or deleted. An agent-seat that a dropped task left waiting is told it was dropped.
