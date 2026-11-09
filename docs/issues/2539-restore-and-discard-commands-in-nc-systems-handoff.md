---
issue: "[Restore and discard commands in `nc-systems/handoff/uncommitted-work-snapshots.py` replace the restore steps an agent runs by hand](https://github.com/nedschorus/nedschorus/issues/2539)"
---

# Restore and discard commands in `nc-systems/handoff/uncommitted-work-snapshots.py` replace the restore steps an agent runs by hand

## What is wrong

When an agent-seat's earlier agent-session died with uncommitted work, the handoff-supervisor lists each leftover work-snapshot in the first prompt of the next agent-session, followed by the restore steps, the constant `RESTORE_STEPS` in `nc-systems/handoff/uncommitted-work-snapshots.py` (line 571 on main at 78716fd58). Most of those steps need no judgment, yet the agent carries them out by hand, one shell command at a time:

- it works out a branch name from the ref (`restored-` and the ref's last two parts joined by a hyphen) and the clone's directory from `git rev-parse --path-format=absolute --git-common-dir`;
- it runs `git worktree add -b <name> <clone>/.claude/worktrees/<name> <ref>^`, then `git diff --binary <ref>^ <ref> -- <files to keep> | git apply --index` and `git commit -m "Restore work from <ref>"` in the new worktree;
- it applies the rule that a work-snapshot taken during a merge, rebase, cherry-pick, revert or am is never restored, only deleted;
- it deletes the ref with `git update-ref -d <ref>`, whether the work was kept or dropped, and leaves the ref in place when a command fails.

The program's command line today has one command, `list` (`main()` in the same file). The design, `nc-systems/handoff/handoff-uncommitted-work-snapshots-across-crashes-design.md` § 3, "The restore steps, printed with the list", writes these steps as instructions to the agent.

## Why it matters

The project builds code-prompt-code: a step that needs no judgment, such as sequencing, state, validation or a retry, goes in code, because code can be tested and runs the same way each time, while an agent following steps can run them differently each time. Here a wrong branch name, a diff applied to the wrong parent, a merge-time work-snapshot restored, or a ref deleted after a failed apply each loses or damages the dead agent-session's work, and no test can cover how an agent carries out prose steps.

## What to build

Two commands on `nc-systems/handoff/uncommitted-work-snapshots.py`:

- `restore <ref> --keep <file> [<file> ...]` makes the branch and worktree the restore steps name today (`restored-` and the ref's last two parts joined by a hyphen, under `<clone>/.claude/worktrees/`) from the work-snapshot's parent, applies the diff of the kept files, commits it with the message "Restore work from <ref>", deletes the ref, prints the branch and worktree it made, and opens a task on the agent-seat's task list naming the restored branch, which code closes when the branch's pull request merges or the branch is deleted. Paths are relative to the clone's root, as the list entry prints them. Before it changes anything, it refuses when a kept path is not among the work-snapshot's changed files, when the branch or the worktree directory already exists, or when the work-snapshot was taken during a merge, rebase, cherry-pick, revert or am, in which case it tells the agent to run `discard` and tell the user which operation was discarded. When a step before the commit fails, it removes the branch and worktree it made, leaves the ref in place, and prints what failed; when only the ref's deletion fails, it keeps the restored branch and prints the `git update-ref -d <ref>` to run.
- `discard <ref>` deletes the ref and prints its list entry, which names the files it held and, for a work-snapshot taken during an operation, the operation.

Each list entry the handoff-supervisor prints then ends with the command to run: `discard <ref>` for a work-snapshot taken during an operation, and otherwise `restore <ref> --keep` followed by every changed file, so the agent's only edit is to delete the files it drops.

`RESTORE_STEPS` then keeps only what needs judgment: reading the diff and the end of the dead agent-session's transcript to decide which files to keep, removing any mutant left by nc-mutation-testing from a kept file, in a commit of its own after `restore`, before the branch is pushed, choosing between `restore` and `discard`, and telling the user what was kept and what was dropped.

Tests for both commands go in `nc-systems/handoff/tests/uncommitted-work-snapshots-test.py`, with each failure injected: a kept path not in the work-snapshot, a branch that already exists, an apply that conflicts, a commit that fails, a ref deletion that fails, a merge-time work-snapshot, and, for both commands, a ref that no longer exists.

## User-rulings

The user approved this GHI-MD's plan on 2026-11-07, as item 2 of the approval-walk `relaunch-stopped-agent-seats-decisions-memory-refusal-subagent-sentence-and-work-snapshot-restore-command-approval-walk-2026-11-07`, whose walk-minutes are `nedlern@ned-box:/home/nedlern/agents/fleet-restart-at-login/docs/walk/relaunch-stopped-agent-seats-decisions-memory-refusal-subagent-sentence-and-work-snapshot-restore-command-approval-walk-2026-11-07-minutes.md`, in his words, "they" being the two commands: "They approve, and there's something about a restore opens one more task on the agent's list. Well, that's fine as long as we remember to, as long as it's automatically closed." Decided:

- Build `restore <ref> --keep <files>` and `discard <ref>` as What to build says.
- `restore` also opens a task on the agent-seat's task list naming the restored branch, and code closes that task when the branch's pull request merges or the branch is deleted.
- The new text of the design's § 3 comes to the user, its old and new text side by side, as an approval-walk item of its own, before the build.

The user approved the new text of the design's § 3 on 2026-11-07, as item 1 of the approval-walk `handoff-uncommitted-work-snapshots-design-section-3-restore-and-discard-commands-approval-walk-2026-11-07`, whose walk-minutes are `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/handoff-uncommitted-work-snapshots-design-section-3-restore-and-discard-commands-approval-walk-2026-11-07-minutes.md`, answering "A". The approved text is the file the walk presented, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/fleet-restart-at-login/ghi-2539-design-section-3-draft-2026-11-08.md`; the date in its name is the drafter's. Decided:

- The design's § 3 is replaced with the approved text, and the build follows it; where What to build above and the approved text differ, the approved text holds.
- `scripts/clean-worktrees.py` is the code that closes the task `restore` opens, at its runs with `--remove`.
- The task follows the commit `restore` made, not the branch's name: after `git fetch --prune origin`, the cleaner marks the task completed when that commit is reachable from `origin/main`, or when no ref holds it. The 2026-11-08 ruling below replaces this rule.
- `restore` writes the new worktree's owner file, naming the agent-seat, so that `scripts/clean-worktrees.py` and the agent-seat's list of worktrees handle the restored worktree.

The user approved a change to the rule that closes the task on 2026-11-08, as item 3.2 of the approval-walk `memory-refusal-only-the-callers-lines-and-restored-branch-task-rebase-gap-approval-walk-2026-11-08`, whose walk-minutes are `nedlern@ned-box:/home/nedlern/agents/fleet-restart-at-login/docs/walk/memory-refusal-only-the-callers-lines-and-restored-branch-task-rebase-gap-approval-walk-2026-11-08-minutes.md`, answering "A". The item, with the exact design sentences he approved, is under the heading "Item 3.2 of 4: The design's new sentences" in `nedlern@ned-box:/home/nedlern/agents/fleet-restart-at-login/docs/walk/memory-refusal-only-the-callers-lines-and-restored-branch-task-rebase-gap-approval-walk-2026-11-08.md`. The defect it fixes: a rebase copies the restore commit under a new id, so no ref holds the commit the task's `Restore commit: ` line names, and the cleaner marks the task completed while the work is still unmerged. Decided:

- `restore` gives the commit it makes the trailer `Restored-from-work-snapshot: <the work-snapshot's ref>`, whose key is the constant `RESTORED_FROM_WORK_SNAPSHOT_TRAILER_KEY` in `nc-systems/handoff/uncommitted-work-snapshots.py`, and writes the same line in the task's description, whose instructions add "Keep this trailer in the commit message."; the task's `Restore commit: ` line stays, for the reader only.
- After `git fetch --prune origin`, `scripts/clean-worktrees.py` reads each commit's trailers in `git log --all` and marks the task completed when a commit with the task's `Restored-from-work-snapshot: ` line is reachable from `origin/main`, or when no commit with that line is on any ref. A rebase copies the commit message, so a rebased or renamed branch keeps the task open until its work is on main or deleted.
- A task with no `Restored-from-work-snapshot: ` line, opened before `restore` wrote one, is judged by its `Restore commit: ` line, as before.
- This is built in a follow-up pull request after PR 2790 merges, not on PR 2790's branch; that pull request also puts the approved sentences into the design's § 3.

## Next action

[PR 2790](https://github.com/nedschorus/nedschorus/pull/2790), open on 2026-11-08, builds what the 2026-11-07 rulings decided: the two commands, the task `restore` opens and the code that closes it, their tests, the shortened `RESTORE_STEPS`, and the design's § 3. It merges with the rule the 2026-11-07 rulings set, under which a rebase still closes the task early, and is not changed for the 2026-11-08 ruling. After it merges, an agent-seat builds the 2026-11-08 ruling in a pull request of its own: the trailer in `restore`'s commit and in the task's description, the new rule in `scripts/clean-worktrees.py`, its tests, one of which rebases a restored branch and checks that the task stays open, and the approved sentences in the design's § 3.

## Where this came from

Item 2 of Question 4, "What should be code", in the cold-read-fast-read of the handoff-system's nc-architecture-overview draft on 2026-11-03: `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/nedschorus-handoff-architecture-overview-draft-2026-11-03/cold-read-fast-read.md`. Checked against main at 78716fd58 on 2026-11-03. ghi-guide-agent, asked with `--include-closed`, named no issue, open or closed, that covers it.
