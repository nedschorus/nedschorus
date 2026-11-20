# Proposed improvements or changes: nedsnodes-handoff-architecture-overview.md (overview claim check, 2026-11-18)

Assertions of the overview that the claim check against commit 46844e6f221b7702dfacb176b1ae657fb06e6757 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedsnodes-logs/overview-write-architecture-overview-claim-check-reports/nedsnodes-handoff-architecture-overview/6d6d2eb147cfe6fb0d3c9b2c11b8d55761134401-2026-11-18T07-23-22-284097Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: The cleaner deletes a local branch other than main that no worktree has checked out, "and no other branch", with `-D` only for a finished pull request's head branch.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - clean-worktrees.py:197-201 `A worktree on a branch other than main then has that branch deleted with \`git branch -D\`, even when origin/main lacks some of its commits`
> - clean-worktrees.py:202-206 `--force-delete-branch keeps the branch when it is main, does not exist, is checked out in a worktree, cannot be checked against the pull requests, or is the head branch of an open pull request; otherwise it deletes it with \`git branch -D\``
> - So the program's named-worktree and named-branch commands, which the first-prompt list sends agents to, delete branches with no pull request, which "no other branch" rules out. The sentence holds only for `--remove`.
> - Row 133 names those commands, so no agent would act wrongly; scope "and no other branch" to `--remove`.
State: open
