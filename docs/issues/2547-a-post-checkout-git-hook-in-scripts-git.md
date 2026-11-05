---
issue: "[A post-checkout git hook in `scripts/git-client-side-hooks/` writes the owner file of each new worktree an agent makes](https://github.com/nedschorus/nedschorus/issues/2547)"
---

# A post-checkout git hook in `scripts/git-client-side-hooks/` writes the owner file of each new worktree an agent makes

## What is wrong

`scripts/clean-worktrees.py` removes a worktree only when the worktree holds an owner file, `worktree-owner.json` in the worktree's own git directory, which says which agent-seat or agent-session owns it; a worktree with no owner file is kept forever. The owner file is written only when the program or agent that makes the worktree remembers to run `scripts/worktree-owner-file-read-and-write.py write`, or, for a subagent's worktree, by `scripts/uncommitted-work-snapshot-hook.py` after the subagent's first Edit, Write, NotebookEdit or Bash call there, so a subagent that makes none of those calls leaves its worktree with none (the docstring of `scripts/worktree-owner-file-read-and-write.py`, on main at 78716fd58).

On ned-box on 2026-11-03, `python3 scripts/clean-worktrees.py`, run without `--remove` in the reference-checkout `~/Projects/nedschorus` at 78716fd58, reported 487 worktrees kept, 468 of them because they have no owner file.

## Why it matters

Each worktree kept forever holds disk space and a branch, and the cleaner's report lists hundreds of worktrees no program will remove, so a person must judge each by hand. Writing the owner file needs no judgment once the worktree's maker is known, and the project builds code-prompt-code: such a step goes in code, never in an instruction an agent must remember.

## What to build

A `post-checkout` hook in `scripts/git-client-side-hooks/`, the directory that `core.hooksPath` names in the clone on ned-box (checked 2026-11-03). Git runs `post-checkout` after `git worktree add` with a previous HEAD of all zeros, which tells a new worktree from an ordinary checkout. For a new worktree with no owner file, the hook runs `python3 scripts/worktree-owner-file-read-and-write.py write` from the clone's reference-checkout, with the owner the maker implies: `--agent-session` for a subagent's worktree that Claude Code makes, and `--agent-seat` with the agent-seat that `GIT_AUTHOR_NAME` names, which `scripts/launch-claude-ubuntu` and `scripts/launch-claude-mac` set, for a worktree an agent-session makes for its own work. How the hook tells the two apart is the first open question; until it can, it writes nothing, because a wrong owner file cannot be corrected later: the write program refuses to write over an existing one. It writes nothing when `GIT_AUTHOR_NAME` names no agent-seat with a directory under `~/agents/`, such as for a worktree a person makes by hand, and nothing for an agent-home under `~/agents/` or a merge-lane review checkout, which `clean-worktrees.py` keeps on purpose because they have no owner file. A failed write prints why on standard error and exits 0, so the checkout is not failed; since nobody may read that output when Claude Code makes the worktree, the cleaner's report of worktrees with no owner file is where a failing hook shows. Tests go beside the other client-side hook tests under `scripts/`.

## Open questions

- How the hook tells a subagent's worktree, which Claude Code makes, from one an agent-session makes for its own work, since a `claude` process is among the parent processes of both; Claude Code's lock reason on a subagent's worktree, "claude agent agent-<id> (pid N start M)", which `CLAUDE_CODE_SUBAGENT_WORKTREE_LOCK_REASON` in `scripts/worktree-owner-file-read-and-write.py` matches, would tell them apart if it is set before `post-checkout` runs, so the builder checks when it is set.
- The builder confirms which kinds of worktree the cleaner keeps on purpose because they have no owner file, as listed in the docstring of `scripts/clean-worktrees.py`, and how the hook tells each of them from a worktree an agent makes, before choosing the exclusions above.
- GHI [One design of record for the project's git checkouts, worktrees and branch rules](https://github.com/nedschorus/nedschorus/issues/1121), `docs/issues/1121-one-design-of-record-for-the-project-s.md`, plans the design of record for worktree rules; the builder reads it, keeps the hook consistent with it, and adds the hook to it if it lists the hooks.

## What this does not cover

The 468 worktrees found on ned-box on 2026-11-03 with no owner file, and those on the Mac. The hook covers only worktrees made after it lands; whether to write owner files for existing worktrees, from what each still shows, such as its path, its lock reason and the author of its newest commit, is a separate decision.

## Next action

An agent-seat that takes up this GHI answers the open questions from the code, then builds the hook in one pull request with its tests.

## Where this came from

Item 6 of Question 4, "What should be code", in the cold-read-fast-read of the handoff-system's nc-architecture-overview draft on 2026-11-03: `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/nedschorus-handoff-architecture-overview-draft-2026-11-03/cold-read-fast-read.md`. Checked against main at 78716fd58 on 2026-11-03: `scripts/git-client-side-hooks/` holds `post-merge`, `pre-commit`, `pre-merge-commit`, `pre-push` and `prepare-commit-msg`, and no `post-checkout`. ghi-guide-agent, asked with `--include-closed`, named no issue that covers it.
