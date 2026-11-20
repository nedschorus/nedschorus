---
issue: "[Review the archived task list of agent-seat fleet-restart-at-login](https://github.com/nedschorus/nedschorus/issues/3836)"
---

# Review the archived task list of agent-seat fleet-restart-at-login

On 2026-11-17 the user asked every agent-seat to archive its task list before a major restructure of the project, and to file an issue for reviewing each archive later (his words, relayed by merge-lane-2 at about 05:45Z: "You can have all the agents archive their tasks, and make GHIs to review those archives at some point. Then we can start the restructure."). This issue is that review for the agent-seat fleet-restart-at-login. It asks for no work now; the user schedules the review.

## The archive

The archive is `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/fleet-restart-at-login/task-list-archive-2026-11-17/`. It holds all 182 task files of the agent-seat's task list as they were when archived, 140 of them not completed, and `task-list-archive.md`, which lists each task's id, status, subject, description, metadata and blocking tasks. The user's rulings that these tasks rest on are kept in the walk-minutes and GHI-MDs they cite, so the archive loses none of them.

## What was in flight

- The approval-walk `approval-binding-design-ghi-1268-approval-walk-2026-11-09` was open, waiting on its item 17 of 49; its walk-document and walk-minutes are in `docs/walk/` of the agent-home `/home/nedlern/agents/fleet-restart-at-login` on ned-box. Many archived tasks wait on its items, by the `approval_walk_item_decided` prerequisites in their metadata.
- Nine worktrees and their branches belong to archived open tasks: `empty-search-check-fires-by-itself-after-every-bash-call-topic-branch`, `main-gatekeeper-workspace-files-renamed-to-say-main-gatekeeper-topic-branch`, `approval-walk-item-pages-answered-on-the-page-design-topic-branch`, `handoff-architecture-overview-refreshed-against-b14a66236-topic-branch` (it holds an edit of a guarded overview awaiting the user's approval), `handoff-uncommitted-work-snapshots-restored-branch-task-closes-when-its-restored-from-work-snapshot-trailer-commit-is-merged-or-gone-topic-branch`, `scheduled-full-mutation-pass-job-failure-task-and-survivor-recheck-line-quote-whole-stderr-not-last-line-topic-branch`, `nightly-mutation-pass-first-pass-12-mutants-per-merge-shared-among-files-then-skipped-mutants-second-pass-on-main-topic-branch` and `work-snapshot-restore-runs-git-worktree-add-with-no-hooks-and-writes-the-only-owner-file-topic-branch`, each in a worktree under `/home/nedlern/Projects/nedsnodes/.claude/worktrees/` on ned-box, and the worktree `/home/nedlern/agents/fleet-restart-at-login/.claude/worktrees/ghi-retitle-verdict-check`. The live task "Old tasks archived 2026-11-17 at the user's request" on the agent-seat's task list names each in its `branches` metadata, which keeps the leftover list that opens each new agent-session from offering them for deletion; that task stays open until this review is done.
- The user held all new mutation-testing work on 2026-11-12 until he rules on the walk item "Daytime mutation testing is cut back, with no rate limiter yet", which waits to be shown in the same approval-walk; most of the open archived tasks are mutation-testing tasks under that hold.

## Next action

When the user schedules the review: read `task-list-archive.md` in the archive directory above, and for each open task decide, against the project as restructured, whether to put it back on an agent-seat's task list, fold it into a GHI, or drop it; a task whose walk item or hold is still undecided goes back with its prerequisite. For each worktree above, check whether main already holds its branch's changes, then keep it for a restored task or delete it. Then close the live task "Old tasks archived 2026-11-17 at the user's request" and this issue.
