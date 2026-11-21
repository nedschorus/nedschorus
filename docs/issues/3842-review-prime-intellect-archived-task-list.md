---
issue: "[Review prime-intellect's archived task list](https://github.com/nedsnodes/nedsnodes/issues/3842)"
---

# Review prime-intellect's archived task list

At 2026-11-17T05:46:07Z the user said to merge-lane-2 (transcript `nedlern@ned-box:/home/nedlern/.claude/projects/-home-nedlern-agents-merge-lane-2/281b4ed9-a47c-42c9-9f34-83ab38636f1b.jsonl`): "You can have all the agents archive their tasks, and make GHIs to review those archives at some point. Then we can start the restructure." That day prime-intellect's task list was copied whole into `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/prime-intellect/task-list-archive-2026-11-17/`, and the archived task files were then removed from the live task store, so that the restructure starts without them. The archive holds 32 task files, one JSON file per task, named by task id. The file `task-list-archive.md` in the same folder lists each task's id, status, subject and description in numeric order. Task 226 of prime-intellect's live task list points to this archive and names the work that was in flight when the list was archived: an open approval-walk, unpushed branches and worktrees, and open pull requests.

## Why

The archived tasks held work in progress, commitments, and questions waiting on the user. Some of that may still be wanted after the restructure; no live task carries it any more (task 226 only points to the archive), so without a review it would be forgotten.

## What to do, and when

Nothing now. The user will schedule this review himself, by telling an agent-seat to start it; until he does, do not start it, and do not resume any work from an archived task.

When he does, read each archived task's JSON file, which holds the whole task including its metadata; `task-list-archive.md` is only an index. Sort each task into one of three groups, by the rules of the sixteenth job of GHI [Regular maintenance: the list of maintenance jobs, how often each runs, and how each reaches the user](https://github.com/nedsnodes/nedsnodes/issues/1058), the job in which an agent-seat reviews its own task list:

- Done, or no longer wanted: dropped, with a one-line reason.
- Still wanted: put on the task list of the agent-seat that owns that work after the restructure, or, when it belongs in an issue, routed through the /ghi-write skill, which also finds an open issue that already covers it.
- A question waiting on the user, a commitment to him, a ruling of his not yet carried out, or a still-wanted task that no agent-seat clearly owns after the restructure: taken to him in one approval-walk, through the /walk-me-through skill.

The work task 226 names as in flight, the open approval-walk, the unpushed branches and worktrees and the open pull requests, is reviewed the same way, and task 226 is marked completed when the review ends. Whoever runs the review decides then whether a program should record which task ids are sorted, so that a review spread over several agent-sessions skips none. Record the outcome in this GHI-MD: the count in each group, each dropped task's id and reason, and where each kept task went. Then close the issue with close-GHI, `python3 scripts/ghi-issue-write.py close <path of this GHI-MD> --reason completed`, as the /ghi-write skill describes. The archive stays in the log-store after the review.
