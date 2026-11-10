# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-08)

Assertions of the overview that the claim check against commit 31905b3dea48908baf818723090b23b5388cfa49 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/b734eef5ed84f6f5ef61190b13c31f2755202c73-2026-11-08T23-29-10-938461Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: clean-worktrees.py keeps "a worktree with no owner file, or locked ..."
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - scripts/clean-worktrees.py:13-14 "it has no owner file, as agent-homes and worktrees made by hand have, and is not a merge-lane review checkout"
> - scripts/clean-worktrees.py:61-68 "A worktree with no owner file directly inside ~/.cache/merge-lane-review-worktrees ... It is removed when that pull request was merged or closed at least 24 hours ago"
> - scripts/worktree-owner-file-read-and-write.py:38-41 "The cleaner never removes a worktree with no owner file, except a merge-lane review checkout"
> - scripts/clean-worktrees.py:49-52: a Claude Code lock whose process has ended is unlocked by --remove.
> - The overview leaves out both exceptions. The rest of the sentence is supported: :33-47 (rules while the owner runs and after it stops), :85 (records shipped before removal), :108-110 (branches), :192-208 (the log, using `run_on_ned_box_or_here`), :169 (work-snapshots deleted after ten days).
State: open

## E2 — possible problem: an assertion of the overview is contradicted

Claim: The asked and deferred markers. The overview says the second marker is read "by `scripts/agent-seat-idle-sweep-verdicts-print.py`, which spells the suffix itself".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - scripts/agent-seat-idle-sweep-verdicts-print.py:68-70 `deferred_marker_files = _load("handoff_deferred_marker_and_refused_commands_files_common", ...)`
> - scripts/agent-seat-idle-sweep-verdicts-print.py:533 `marker = deferred_marker_files.handoff_deferred_marker_path(`
> - A grep for `handoff-deferred` or `DEFERRED` in that file finds no suffix spelled there. It takes the suffix from the shared module, like the other readers.
> - The rest of the bullet is supported: agent-seat-due-task-raise-hook.py:711-712 reads both markers; the guard hook :47; the writer :463; post-compaction :109-110; handoff-deferred-marker-and-refused-commands-files-common.py:35 `"-handoff-deferred-fired"`; threshold hook :744.
State: open
