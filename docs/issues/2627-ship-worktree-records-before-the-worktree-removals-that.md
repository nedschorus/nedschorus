---
issue: "[Ship worktree records before the worktree removals that the records-ship-first hook cannot see](https://github.com/nedschorus/nedschorus/issues/2627)"
---

# Ship worktree records before the worktree removals that the records-ship-first hook cannot see

## The problem

Each worktree keeps its cold-read-records and sanity-check records in two gitignored folders, `cold-read-records/` and `sanity-check-records/`. `git worktree remove` deletes them without a word, and the log-store on ned-box is the only other place a record is kept. [PR 2587](https://github.com/nedschorus/nedschorus/pull/2587) adds a PreToolUse hook, `.claude/guard-hooks/git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py`, that ships every worktree's records before a Claude Code Bash command runs `git worktree remove`. Two kinds of removal get past it:

1. Removals the hook never sees. A PreToolUse hook sees only the Bash commands of a Claude Code agent. A removal that a script runs as a program, a Codex agent runs, or a person types in a terminal reaches no hook. `scripts/clean-worktrees.py` ships records before its own removals, so it is not one of these.
2. Removals in another repository. The hook lists worktrees with `git worktree list`, run in the cwd the hook is given. A command such as `git -C /other/repository worktree remove wt`, `git --git-dir /other/.git worktree remove wt`, or `cd /other/repository && git worktree remove wt` removes a worktree of another repository. The hook then ships the records of the repository its cwd is in, and the removed worktree's unshipped records are lost.

The user accepted the first kind on 2026-10-28 at 06:49, approving item 2 of approval-walk prime-intellect-open-decisions-for-the-user-2026-10-28, whose text said a PreToolUse hook misses removals inside scripts, Codex agents and terminals (walk-minutes: nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/prime-intellect-open-decisions-for-the-user-2026-10-28-minutes.md). The second kind was found in the second review round of PR 2587, in the review comments [r4476167874](https://github.com/nedschorus/nedschorus/pull/2587#discussion_r4476167874) and [r4476191166](https://github.com/nedschorus/nedschorus/pull/2587#discussion_r4476191166).

## Why it matters

A record that has not shipped, such as one written or changed after its first shipment, exists only in the removed worktree. Once that worktree is removed, nothing can bring the record back.

## What is not available

git has no client-side hook that runs before `git worktree remove`: `git help hooks` lists none for worktree removal. So the fix cannot be a git hook in `scripts/git-client-side-hooks/`, the way [GHI 2547](https://github.com/nedschorus/nedschorus/issues/2547) uses git's post-checkout hook when a worktree is made.

## Next action

Design how records reach the log-store before every worktree removal, whatever runs it. One option covers both kinds: ship records whenever they are written, so no removal can lose an unshipped one. Another covers only the second kind: have the hook list the worktrees of the repository the command names with `-C`, `--git-dir` or a preceding `cd`, which brings back the reading of shell text that PR 2587 removed. Bring the design to the user, since it changes the design he approved on 2026-10-28. This is part of the subject of [GHI 1121](https://github.com/nedschorus/nedschorus/issues/1121), "One design of record for the project's git checkouts, worktrees and branch rules"; record the outcome there too.
