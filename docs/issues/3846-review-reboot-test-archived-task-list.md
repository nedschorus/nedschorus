---
issue: "[Review reboot-test's archived task list](https://github.com/nedschorus/nedschorus/issues/3846)"
---

# Review reboot-test's archived task list

## Why

Before the restructure, the user asked for every agent-seat to archive its task list and for a GHI to review each archive later. merge-lane-2 relayed his words on 2026-11-17 at about 05:45Z: "You can have all the agents archive their tasks, and make GHIs to review those archives at some point. Then we can start the restructure." This GHI is agent-seat reboot-test's; each other agent-seat files its own. No GHI described the restructure on 2026-11-17: `gh issue list --repo nedschorus/nedschorus --state all --search "restructure"` found none. When the review starts, find the restructure's GHI or design first, and ask the user what the restructure changes only when there is none.

## The archive

On 2026-11-17, reboot-test archived its whole task list, 186 tasks (121 pending, 30 in_progress, 35 completed), to `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/reboot-test/task-list-archive-2026-11-17/`. In that directory, `task-list-archive.md` gives each task's id, status, subject and description, and each `<id>.json` file is that task as the task store held it, with its `blocks`, `blockedBy` and `metadata` fields. The user's rulings are kept in walk-minutes and GHI-MDs, so the archive holds no ruling that exists only there.

## In flight when the list was archived

These may have changed since; check each one's current state before deciding it.

- Open pull requests: [3818](https://github.com/nedschorus/nedschorus/pull/3818), [3348](https://github.com/nedschorus/nedschorus/pull/3348), [3320](https://github.com/nedschorus/nedschorus/pull/3320), [3731](https://github.com/nedschorus/nedschorus/pull/3731), and the draft [3426](https://github.com/nedschorus/nedschorus/pull/3426).
- Pushed branches with no pull request, by archived task:
  - 480: `bash-guards-replay-merge-tree-refusals-print-the-exact-rerun-command-topic-branch`
  - 524: `idle-sweep-failures-to-owning-agent-seat-tasks-and-headless-usage-limit-pause-topic-branch`
  - 579: `fix-round-brief-prints-walk-approved-path-stopped-round-next-step-and-answers-file-skeleton-topic-branch`
  - 631: `idle-sweep-object-negated-sentence-not-raised-and-no-escalation-after-tool-call-on-promise-wait-topic-branch`
  - 632: `approval-walk-item-decided-prerequisite-line-printed-for-next-item-topic-branch`
  - 634: `due-task-hook-raises-task-once-when-its-pull-request-closes-without-merging-topic-branch`
- One open approval-walk, agent-seat-git-worktrees-branches-checkout-refresh-and-cleanup-redesign-approval-walk-2026-11-03, waiting on the user's answer to item 49 of 93. Its walk-minutes are `nedlern@ned-box:/home/nedlern/agents/reboot-test/docs/walk/agent-seat-git-worktrees-branches-checkout-refresh-and-cleanup-redesign-approval-walk-2026-11-03-minutes.md`, in reboot-test's agent-home, a directory git does not track, so keep that directory while the walk is open. Several archived tasks wait on items of this walk: each names its item in `metadata.prerequisites`.

## Next action

None until the user schedules the review. When he does, the agent-seat he names, reboot-test unless he says otherwise, goes through the archive and decides each pending or in_progress task in light of the restructure: drop it, re-create it as a task on the task list of the agent-seat that now owns its work, or route it as the /ghi-write skill says, such as into a GHI. When a task is dropped, look again at each task its `blocks` field names. A completed task needs no decision unless its description shows work left over. Record each task's decision in a file beside the archive, so that a session-handoff partway through loses nothing. In the same pass, decide each pull request and branch above, and whether the approval-walk resumes with the user or ends with its open items routed as /ghi-write says. When every task, pull request, branch and the approval-walk is decided, write the outcome into this GHI-MD and close the issue with close-GHI.
