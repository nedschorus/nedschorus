<!-- provenance: runtime=codex model=gpt-5.6-terra effort=low cell=fast-clarify tier=floor duration_s=54 tokens=21227 target=docs/walk/topic-branch-parent-problem-and-the-lane-rule-fix-draft.md -->

# 1. What it says

## Item 1 of 3: The near-miss, in the exact commands

After the first of four pull requests, the seat remained on its first topic branch. Creating the next branch with an explicit `origin/main` parent avoided inheriting the first topic; using the short form would have silently included both topics, potentially merging rejected or reworked code. This repeated correct command use was the only protection, and the item makes no decision.

## Item 2 of 3: Why a seat is more exposed to this than an ordinary checkout

An ordinary checkout can return to main before starting its next branch, making the short branch-creation command safe. A seat cannot check out main because the reference copy already has it checked out, which is why it has a personal branch rather than because anyone intended a long-lived personal branch. Thus, after finishing a topic, a seat has no safe between-topic branch and the short command silently starts from the wrong parent; this item also makes no decision.

## Item 3 of 3: The fix — give the seat somewhere safe to stand

The existing rule requires a topic to start from current main but does not say what branch the seat must occupy, leaving correctness dependent on explicitly naming `origin/main`. The proposed rule returns the seat to its own branch, fast-forwarded to main, when a topic pull request opens, so that branch becomes the safe parent for every topic. This makes the short command safe, relies on the handoff supervisor’s existing clean-tree fast-forwarding, prevents the cleanup script from reporting the seat branch as removable, adds no topic limit or worktrees, leaves merged-topic deletion to existing launch-time tooling, and requires approval before editing `CLAUDE.md`.

# 2. Where you stumbled

1. [question] "the handoff supervisor states it plainly in its own source" — Where is that source, so a zero-context reader can verify the stated reason for the seat branch?

2. [question] "return the seat's home to the seat's own branch, fast-forwarded to main" — Which branch is the seat's own branch, and what action returns the home to it when it is currently on a topic branch?

3. [question] "Pull request 233 landed tooling" — Where is the referenced pull request or the command it is said to provide?

4. [question] "the machine's reference copy" — Which checkout is the machine's reference copy for a reader whose environment does not use the stated home-directory path?

# 3. What it does not cover

1. [no-rule] "When a topic's pull request is opened, return the seat's home to the seat's own branch, fast-forwarded to main; cut every topic from there." — What should the seat do when its home cannot be fast-forwarded because it has local changes or commits not in main?

2. [rule-conflict] "a topic starts on a branch cut from current main" / "fast-forwarded to main; cut every topic from there" — Which rule governs when main advances after the seat branch is fast-forwarded but before the next topic is cut?

3. [no-rule] "When a topic's pull request is opened" — What should the seat do if it needs to begin another topic while the preceding topic has not yet reached the pull-request-opened state?

4. [no-rule] "deleting merged topic branches needs no rule" — What should a reader do when a merged topic branch is not reported by the launch-time tooling or its removal command fails?
