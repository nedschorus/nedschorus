---
issue: "[The checkout-freshness hook treats a new branch cut at a pull request's pushed head as never pushed, and rebases it](https://github.com/nedschorus/nedschorus/issues/913)"
---

# The checkout-freshness hook treats a new branch cut at a pull request's pushed head as never pushed, and rebases it

## The problem

`scripts/checkout-freshness-catch-up.py`, the Stop hook that keeps a checkout current with main, decides whether a branch has been pushed by one test: whether a remote branch of the same name exists. A branch that an agent creates under a new name at a pull request's pushed head fails that test, so the hook calls the branch never pushed, although the branch's commits are the pull request's frozen head. The hook then rebases that branch onto `origin/main` itself, at the end of a main session's turn, whenever the tree is clean. The rebase rewrites every commit of the pull request that main lacks, not only the agent's fix, so the frozen head is moved in the one checkout where the fix commit was being built.

`scripts/obsolete-file-edit-warning-hook.py` reads the same state and tells the agent, after each edit, that the branch "has never been pushed, so nobody else has it" and to run `git rebase origin/main`.

A branch of this kind is ordinary, not exotic. `.claude/hooks/session-location-write-guard.py` refuses an edit from a detached HEAD and tells the agent to "Get onto a branch first (git switch -c <a-branch-name>)". A fix-round subagent checks out a pull request's pushed head detached, because the pull request's own branch is checked out in the agent-seat's worktree and git lets one branch be checked out in one worktree only. Following the guard's instruction creates exactly the branch this hook misclassifies.

Why the frozen head matters: CLAUDE.md freezes a pull request's head the moment it is pushed, because that is when its review is commissioned; a fix is one commit on top of that head. A rebased head can no longer take a fix as one commit on top without being recovered first.

The closed GHI [checkout-freshness catch-up merges main into a branch whose head is frozen under review](https://github.com/nedschorus/nedschorus/issues/324) ruled that the hook never moves a pushed head and introduced the rebase of a never-pushed branch on the premise that it "moves only heads nobody else has". This defect is a case where that premise fails: the head is shared, and only the branch name is new.

## Evidence

- `scripts/checkout-freshness-catch-up.py`, `head_state()`: returns `"unpushed"` when `git rev-parse --verify --quiet origin/<branch>` fails, which is the case for any branch name never pushed, whatever its commits.
- The same file, the never-pushed step (3a) in `main()`: when the state is `"unpushed"`, `rebase_never_pushed_branch()` runs `git rebase origin/main`; a dirty tree only postpones the rebase, which is attempted again at every turn end.
- `scripts/obsolete-file-edit-warning-hook.py`, `head_advice()`: returns `NEVER_PUSHED_ADVICE` for the same `"unpushed"` state, which says "This branch has never been pushed, so nobody else has it: commit or set aside your work and run `git rebase origin/main`".
- `.claude/hooks/session-location-write-guard.py`, the detached-HEAD refusal: "Get onto a branch first (git switch -c <a-branch-name>)".
- Who meets which: the Stop hook runs when a main session's turn ends. `.claude/settings.json` registers no `SubagentStop` hook, so a subagent meets only the edit warning's advice, while a main session that cuts such a branch meets the rebase itself.

## What happened

On 2026-10-01 the MD-skills agent-seat sent two fix-round subagents to build fixes for PR [The instruction-file guard protects the files the user reviews, by where they sit](https://github.com/nedschorus/nedschorus/pull/852), each in a worktree of its own, because the pull request's branch was checked out in the agent-seat's worktree.

- Round one was told to stay on a detached HEAD at the pushed head and not to rebase.
- Round two needed to write files, so it was told to create the branch `instruction-file-guard-protects-reviewed-homes-by-location-fix-round-two` at the pushed head `44ddb6b3`, to leave its edits uncommitted, and to run `git checkout --detach` before finishing, "so the checkout-freshness hook cannot rebase the frozen head". The subagent reported: "`scripts/obsolete-file-edit-warning-hook.py` told me after each Edit to `git rebase origin/main`, because the local branch name hides that 44ddb6b3 is a pushed, frozen head. I ignored the warning."

The agent-seat wrote the detach instruction without checking whether the Stop hook runs for a subagent; by the registration above it does not, so the subagent's real exposure was the edit warning's advice. The frozen head was kept by instructions written around the hooks, not by the hooks. An agent in a main session that follows the guard's instruction without such instructions has its frozen head rebased.

The user approved filing this as a GHI of its own, ahead of the work on the wording of refusal and warning messages, on 2026-10-01 in the MD-skills agent-seat's session, answering "Yes to all" to the recommendation "file this as its own GHI now, ahead of the messages work".

## Directions to choose from

These are the directions visible now, for the user to choose between or combine; none is ruled.

1. Before calling a branch never pushed, check whether any commit in `origin/main..HEAD` is already on a remote branch (for example `git branch -r --contains <commit>` for each such commit, oldest first), and treat the branch as pushed when one is. The agent's own unpushed fix commit is on no remote branch, so the check has to look past HEAD to the commits beneath it.
2. Ask GitHub whether HEAD's commits belong to an open pull request's head. The closed GHI above chose to read head state from git alone, so that a turn end needs no network; this direction reverses that choice, and has to decide what a failed or timed-out query means. Reading a failure as never pushed would keep the defect.
3. Have `head_state()` compare HEAD with the branch's configured upstream (`@{upstream}`) when one is set, instead of with `origin/<local branch name>`, and have the detached-HEAD refusal tell the agent to set the upstream to the pull request's branch when it creates the branch (`git switch -c <name> --track origin/<the pull request's branch>`). Instructions alone cannot do this under today's code: the pull request's own branch name cannot be checked out in a second worktree, and `head_state()` ignores the upstream. This direction also depends on every agent following the refusal's instruction.

## Next action

The user chooses a direction; then one pull request changes `scripts/checkout-freshness-catch-up.py` and `scripts/obsolete-file-edit-warning-hook.py` together, since both read `head_state()`, with test cases in `scripts/checkout-freshness-catch-up-test.py` and `scripts/obsolete-file-edit-warning-hook-test.py` for a branch cut under a new name at a pushed head. That pull request also decides which head state such a branch reports and which remote branch its commit counts are taken against.

## Search receipt

`scripts/ghi-info-ask.py`, asked on 2026-10-01 whether any open issue covers this, and asked again with `--include-closed`: no open issue covers it. The nearest prior art is three closed issues on the same hook, all closed 2026-09-15: GHI [checkout-freshness catch-up merges main into a branch whose head is frozen under review](https://github.com/nedschorus/nedschorus/issues/324), GHI [checkout-freshness catch-up: pin the two git rebase --abort shapes healthy git cannot produce](https://github.com/nedschorus/nedschorus/issues/389), and GHI [checkout-freshness catch-up's block decision overwrites the answer of a claude -p subprocess whose output a program reads](https://github.com/nedschorus/nedschorus/issues/334). None records the misreading of a new branch name as never pushed.
