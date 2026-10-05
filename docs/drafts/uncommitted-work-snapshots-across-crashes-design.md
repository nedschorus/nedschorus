# Uncommitted-work snapshots across crashes: design

Status: proposed, for the user's approval. Nothing here is built yet.

## The problem

An agent's work is safe once it is committed: the branch keeps it, and the daily worktree cleaner keeps any worktree whose branch has commits that are not on main. Work that is not yet committed lives only in the worktree's files. Two things can take it away:

- **A crash.** The agent-session, or a forked subagent working in its own worktree, dies with edits on disk and no commit. Nothing records that those edits exist or matter.
- **The cleaner, after a crash.** `scripts/clean-worktrees.py --remove` runs daily at 06:30 and removes a worktree once its branch is merged into main and no running program is working in it, whatever files it still holds, naming each file in `~/.claude/daily-clean-worktrees.log`. A branch with no commits of its own counts as merged. So a worktree whose agent died before its first commit is removed with its edits.

Both happened on 2026-10-04 and 2026-10-05. A fork of ned-box-helper building a change to `scripts/resupervise-seat-test.py` died in the fleet-wide SIGTERM at 21:14:56 with two files edited and nothing committed. At 06:30 the cleaner removed its worktree and both files (`~/.claude/daily-clean-worktrees.log`, lines 198 to 200). The work was rebuilt only because the fork's transcript happened to record every edit. Four other dead forks' worktrees survived because each had made one commit.

The cleaner's rule is right for its job: a merged worktree that nothing is using is cleanup material. What was missing is a copy of the uncommitted work that outlives the crash, and a restart that picks it up before cleanup runs.

## What this design does

It keeps a copy of each worktree's uncommitted changes, called a work snapshot here, outside the worktree, in the clone's shared git object store. In normal work the snapshot is redundant and is deleted as soon as the work is committed. After a crash it is the copy the restarted agent-seat restores from. The design has four parts:

1. A hook that writes and deletes snapshots while agents work.
2. A list of leftover snapshots in the first prompt of a restarted agent-seat.
3. A restore procedure for the restarted agent.
4. A backstop in the daily cleaner for snapshots nobody restores.

## 1. Writing and deleting snapshots while agents work

A PostToolUse hook runs after every Edit, Write and NotebookEdit call, and after every Bash call.

- **Which worktree.** For Edit, Write and NotebookEdit the hook uses the git worktree that contains the edited file, found with `git -C <file's directory> rev-parse --show-toplevel`; for Bash it uses the session's working directory. A file outside any git worktree is skipped.
- **The snapshot's name.** One git ref per worktree: `refs/work-snapshots/<worktree directory name>`, for example `refs/work-snapshots/agent-a6679693cebd33239`. The directory name is unique on a machine. Each new snapshot overwrites the ref, so a worktree has at most one snapshot, its latest.
- **What a snapshot holds.** Every change in the worktree that git would commit with `git add -A`: modified and deleted tracked files, and new files that `.gitignore` does not exclude. Ignored files, such as cold-read-records, are left out. The hook builds the snapshot without touching the worktree's index, branch or files: it copies the index to a temporary file, runs `git add -A` against that copy (`GIT_INDEX_FILE`), writes the tree, and makes a commit whose parent is the worktree's HEAD with `git commit-tree`. No commit hooks run, and the branch does not move.
- **The snapshot's message** records what a restorer needs: the worktree's path, its branch, the agent-seat from the launcher's `GIT_AUTHOR_NAME`, the agent-session id, and the time.
- **When there is nothing uncommitted**, the hook deletes the worktree's ref if one exists. So after an agent commits its work, the next tool call removes the now-redundant snapshot.
- **When a rebase, merge or cherry-pick is in progress** in the worktree, the hook does nothing, so it never records or acts on a half-finished operation.
- **Cost.** After a Bash call, the hook first checks `git status --porcelain` and, when the worktree is clean and has no ref, stops there. Building a snapshot takes about a tenth of a second in this repository.
- **Failure.** If the hook cannot write or delete a snapshot, it prints what failed to the agent as a warning and exits without blocking the tool call: the agent's work continues, and the agent knows its work is not protected.

The hook is wired in `.claude/settings.json`, which changes only with the user's approval of the exact wiring.

## 2. Leftover snapshots in the restarted agent-seat's first prompt

When `handoff-supervisor.py` starts an agent-seat's next agent-session, by resuming a crashed transcript or from a session-handoff, its first prompt gains a list of snapshots whose agent-seat is this agent-seat and that no live agent is working on: either the snapshot's worktree no longer exists, or the cleaner's vacancy proof, `worktree_vacancy_keep_reason` in `scripts/clean-worktrees.py`, finds no running program in it. Each line names the ref, the worktree path, the branch, the time and the files changed. When there are none, the prompt says nothing about snapshots.

The list appears after a session-handoff too, because a fork can die while its parent agent-session lives on and ends normally.

## 3. Restoring a snapshot

The restarted agent handles each listed snapshot before other work:

1. Show what the snapshot changes: `git diff <snapshot>^ <snapshot>`.
2. Check the diff against the dead agent's transcript, which names what it was doing. A crash during a hand mutant or a mutation run leaves the mutant in the snapshot; on 2026-10-04 the leftover was the mutant that turned off a test's signal recorder. A change the transcript shows as a mutant is not restored.
3. To keep the work, restore it into a worktree on the snapshot's branch, or a new branch cut from main when the branch is gone, with `git checkout <snapshot> -- .` from the worktree's root, commit it at once, and continue or hand it on.
4. Delete the ref with `git update-ref -d refs/work-snapshots/<name>`, whether the work was kept or dropped, and say which in the reply.

## 4. The daily backstop

The daily cleaner run gains one step for snapshots no restart handled:

- It deletes a snapshot whose worktree is gone and whose changes are already on main, compared with `git diff --quiet origin/main <snapshot>` over the snapshot's changed files.
- It deletes any snapshot older than 30 days whose worktree is gone, naming the ref and its changed files in its log.
- It deletes nothing else, and reports each snapshot it keeps with its age.

Old snapshots that a newer one overwrote are no longer referenced; git's own housekeeping removes them after its `gc.pruneExpire` period, two weeks by default, with no job of ours.

## Machines

Each machine snapshots into its own clone: ned-box into the object store of `/home/nedlern/Projects/nedschorus`, the Mac into the Mac's. Snapshots are refs on disk, so they survive a reboot. Nothing is copied between machines; an agent-seat restarts on the machine it ran on.

## What this design does not do

- It does not change the cleaner's removal rule.
- It does not protect ignored files, or files outside a git worktree, such as a scratchpad under `/tmp`.
- It does not push snapshots anywhere; they never leave the machine.
- It does not restore anything without an agent's check, because a snapshot can hold a mutant.

## How it will be tested

- A worktree with a modified tracked file and a new untracked file gets a snapshot holding both and not an ignored file; its branch, index and HEAD are unchanged.
- After a commit leaves nothing uncommitted, the next hook run deletes the ref.
- During a rebase in progress, the hook neither writes nor deletes.
- A hook failure prints a warning and does not block.
- With a worktree removed and its snapshot left, the restart prompt lists it; with the worktree in use by a live process, it does not.
- The cleaner deletes a snapshot whose changes are on main, deletes one older than 30 days with a log line, and keeps a recent unmerged one.
- The 2026-10-05 loss replayed: a worktree on a branch with no commits of its own, two uncommitted files, owner process killed, cleaner run; the snapshot survives and restoring it brings both files back.

## Decisions for the user

1. The hook wiring in `.claude/settings.json`: after Edit, Write and NotebookEdit, and after Bash.
2. The 30-day age after which the cleaner deletes an unrestored snapshot.
