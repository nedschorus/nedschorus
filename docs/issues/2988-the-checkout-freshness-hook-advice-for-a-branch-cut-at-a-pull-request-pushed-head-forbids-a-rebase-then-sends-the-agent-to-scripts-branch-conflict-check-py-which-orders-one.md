---
issue: "[The checkout-freshness hook's advice for a branch cut at a pull request's pushed head forbids a rebase, then sends the agent to `scripts/branch-conflict-check.py`, which orders one](https://github.com/nedschorus/nedschorus/issues/2988)"
---

# The checkout-freshness hook's advice for a branch cut at a pull request's pushed head forbids a rebase, then sends the agent to `scripts/branch-conflict-check.py`, which orders one

## Reproduction

On ned-box on 2026-11-10 at 21:44Z, merge-lane-2's Claude reviewer for pull request [2971](https://github.com/nedschorus/nedschorus/pull/2971) ran `scripts/branch-conflict-check.py` as it stood at that pull request's head commit, 5f01a00c55bf, with no arguments. It ran in a throwaway repository with a bare origin, with a fake `gh` on `PATH` that prints `[]`, so every lookup of a pull request finds none. The branch `pr-branch` was pushed; the branch `pr-branch-fix` was cut at its pushed head and was not pushed; main was then changed on the same line and pushed. Run on `pr-branch-fix`, the script printed:

```
VERDICT: CONFLICT -- commit 3e62dabd26a6 ("pr") conflicts with origin/main.
ANSWER: rebase -- branch pr-branch-fix has no open pull request and origin does not have it yet, so it is rebased onto origin/main.
Run git rebase origin/main, resolving each conflict so that both changes work.
```

The command and its output are lines 181 and 186 of the reviewer's transcript, `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/ned-box/projects/-home-nedlern--cache-merge-lane-review-worktrees-pr2971-head/859944f4-3c72-479d-a231-d93b254a253a.jsonl`.

## What is wrong

`PUSHED_HISTORY_ADVICE`, in `scripts/checkout-freshness-catch-up.py` (lines 226 to 232 on main at a1015c357), is the text the checkout-freshness hook hands an agent whose branch's commits are already on GitHub under another branch name. That is the branch a fix-round agent cuts at a pull request's pushed head when the pull request's own branch is checked out in another worktree. `scripts/obsolete-file-edit-warning-hook.py` hands the same text (its line 595). On main the text reads:

> This branch's commits are already on GitHub under another branch name, so the branch is treated as pushed and is not rebased: a pushed head may be under review, and a rebase would rewrite it. Do not rebase or amend those commits. A fix is a new commit on top. If it conflicts with main, do what scripts/branch-conflict-check.py reports.

Run with no arguments, `scripts/branch-conflict-check.py` asks `gh` for the open pull request of the current branch (`clearing_lines`, line 572 onwards on main). The branch cut under a new name has no open pull request, and origin does not have it yet, so the script answers `rebase` (the `ANSWER: rebase` line, line 650 on main). An agent that follows the advice is told to do the rebase the same advice forbids, and the rebase rewrites the commits of a pull request under review. Pull request 2971 only rewords the advice's last sentence, to say the script is run in the branch's checkout; the same defect is on main at that pull request's merge base, 54f04661d, and on main at a1015c357.

## What to do

The agent-seat reboot-test owns the text: it came in with pull request [2682](https://github.com/nedschorus/nedschorus/pull/2682), commit 4e4078c1b. reboot-test fixes the cause, so that the check, run as the advice tells the agent to run it on a branch cut at a pull request's pushed head, gives the answer it gives when run with that pull request's number, and never `rebase`. Two ways are open, and the owner chooses: the advice gives the arguments to run the check with, with the number filled in by the hook, such as `--pull-request <n>` of the pull request whose head the branch was cut at, since a placeholder the agent must fill in leaves the bare command, and its `rebase` answer, one mistake away; or the check, run on such a branch, finds that pull request from the commits that origin already has, the branch's own fix commits on top included. The owner also decides what the advice and the check say when the commits are on GitHub under another branch name that has no open pull request. A test runs the check, as the advice tells the agent to, on a branch cut at the pushed head of a pull request, where main changed the same line, and shows it does not answer `rebase`.
