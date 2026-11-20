---
issue: "[Review the archived task list of the agent-seat cold-read-improvement](https://github.com/nedschorus/nedschorus/issues/3838)"
---

# Review the archived task list of the agent-seat cold-read-improvement

On 2026-11-17 the user asked every agent-seat to archive its task list before a major restructure, and to file a GitHub issue for reviewing each archive later. He said, in merge-lane-2's agent-session: "You can have all the agents archive their tasks, and make GHIs to review those archives at some point. Then we can start the restructure." This issue is that review for the agent-seat cold-read-improvement. It asks for no work now: the user will schedule the review.

## What was archived

The archive is `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/cold-read-improvement/task-list-archive-2026-11-17/`. It holds all 50 tasks of the agent-seat's task list as they stood, each task's JSON file copied whole, and `task-list-archive.md`, which gives each task's id, status, subject, blocking tasks, metadata and description. The live task list now holds one task, which points to the archive and lists what was in flight: an open approval-walk, open pull requests, and the branches and worktrees that archived tasks hold.

## Why a review is needed

Many of the archived tasks may be deferred for a long time or changed by the restructure. Archiving loses none of the user's rulings, because those are in the walk-minutes and the GHI-MDs, but some archived tasks carry commitments to him, questions waiting on him, or work started on a branch, and those must not be dropped unseen.

## What the review does

When the user schedules it, an agent-session reads `task-list-archive.md` in the archive folder and sorts each task by the criteria of the sixteenth job of GHI [Regular maintenance: the list of maintenance jobs, how often each runs, and how each reaches the user](https://github.com/nedschorus/nedschorus/issues/1058): a task whose work is done is marked done; a stale task is dropped with a reason; a task that is a question waiting on the user, a commitment to him, or a ruling of his not yet carried out goes to him as an item of an approval-walk. A task that belongs in an open GitHub issue goes to that issue, by the criteria of that GHI's eighth job, applied by hand, since the eighth job's program reads only live task lists and never this archive. The agent-session writes its decision for each task, with the reason, to a new review file in the archive folder, and changes none of the archived files.

Each task kept is put back, with its description and metadata whole, on the task list of the agent-seat that owns its work after the restructure; when the restructure does not settle which agent-seat that is, the task goes to the user as an approval-walk item.

The review also decides, for each branch and worktree that an archived task holds, and for each pull request and approval-walk the live task lists as in flight, whether to keep, finish or delete it. A branch or worktree with commits not on main, or with uncommitted changes, is deleted only after the user approves it in the approval-walk.

The review is done when every archived task has a decision in that review file; the agent-session then marks the live task that points to the archive completed and closes this issue.
