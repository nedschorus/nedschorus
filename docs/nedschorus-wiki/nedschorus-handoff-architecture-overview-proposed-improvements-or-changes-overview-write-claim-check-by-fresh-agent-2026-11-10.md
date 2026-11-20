# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-10)

Assertions of the overview that the claim check against commit a17081fe3b0d0c6092273fa1e910bd22528cdd78 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/0e7a172e5aebd6f427e7c0427be6fbb3f2208892-2026-11-10T22-36-22-994931Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: `scripts/clean-worktrees.py` keeps a worktree with no owner file, or a locked one, as Claude Code locks a subagent's worktree while the subagent runs.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - Contradicted for worktrees with no owner file. scripts/clean-worktrees.py:63-65 `MERGE-LANE REVIEW CHECKOUTS. A worktree with no owner file directly inside ~/.cache/merge-lane-review-worktrees ... is a merge-lane review checkout` and :70 `It is removed when that pull request was merged or closed at least 24 hours ago`.
> - scripts/worktree-owner-file-read-and-write.py:38-41 `The cleaner never removes a worktree with no owner file, except a merge-lane review checkout`.
> - The locked case matches the overview's qualifier "while the subagent runs": clean-worktrees.py:49-53 unlocks an ended Claude Code lock.
> - The other clauses are supported: :33-36 (owner running), :38-47 (owner stopped: branch for detached commits, work-snapshot) and :5-6 (other than the reference-checkout).
> - Rank: the exception is missing, but an agent relying on the claim would at worst expect a review checkout to be kept; no agent opens the wrong file or loses work.
State: open

## E2 — possible problem: an assertion of the overview is contradicted

Claim: `worktree-owner.json` is written, for each worktree `git worktree add` makes, by the git post-checkout hook. Other writers are the snapshot hook, clean-worktrees.py, the backfill script and the `write` command; it is read by clean-worktrees.py (and through it the first-prompt list) and deleted with the worktree.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - Contradicted on "for each worktree git worktree add makes". scripts/git-client-side-hooks-post-checkout-new-worktree-owner-file-write.py:23-30 `It writes no owner file, and prints nothing: when GIT_AUTHOR_NAME names no agent-seat ...; for the agent-home of the agent-seat ...; for a merge-lane review checkout ...; for the clone's main checkout; when the worktree already has an owner file.`
> - The other writers, readers and the deletion are supported: post-checkout:19; uncommitted-work-snapshot-hook.py:133; clean-worktrees.py:52-53; worktree-owner-file-one-time-backfill...py:238; first-prompt list :102-104; worktree-owner-file-read-and-write.py:8-9.
> - Rank: loose; an agent would not open a wrong file, and the cleaner bullet already says worktrees without owner files exist.
State: open
