# Uncommitted-work snapshots across crashes: design

Status: proposed, for the user's approval. Nothing here is built yet.

## The problem

An agent's work is safe once it is committed: the branch keeps it, and the daily worktree cleaner keeps any worktree whose branch has commits that are not on main. Work that is not yet committed lives only in the worktree's files. Two things can take it away:

- **A crash.** The agent-session, or a forked subagent working in its own worktree, dies with edits on disk and no commit. Nothing records that those edits exist or matter.
- **The cleaner, after a crash.** `scripts/clean-worktrees.py --remove` runs daily at 06:30 and removes a worktree once its branch is merged into main and no running program is working in it, whatever files it still holds, naming each file in `~/.claude/daily-clean-worktrees.log`. A branch with no commits of its own counts as merged. So a worktree whose agent died before its first commit is removed with its edits.

Both happened on 2026-10-04 and 2026-10-05. A fork of ned-box-helper building a change to `scripts/resupervise-seat-test.py` died in the fleet-wide SIGTERM at 21:14:56 with two files edited and nothing committed. At 06:30 the cleaner removed its worktree and both files (`~/.claude/daily-clean-worktrees.log`, lines 198 to 200). The work was rebuilt only because the fork's transcript happened to record every edit. Four other dead forks' worktrees survived because each had made one commit.

The cleaner's rule is right for its job: a merged worktree that nothing is using is cleanup material. What was missing is a copy of the uncommitted work that outlives the crash, and a restart that picks it up before cleanup runs.

## What this design does

It keeps a copy of each worktree's uncommitted changes, called a work snapshot here, outside the worktree, in the clone's shared git object store. In normal work the snapshot is redundant and is deleted as soon as the work is committed. After a crash it is the copy the restarted agent-seat restores from. The design has four parts, built as one shared module, `nc-systems/handoff/uncommitted-work-snapshots.py`, and three callers:

1. A hook, `scripts/uncommitted-work-snapshot-hook.py`, that writes and deletes snapshots while agents work.
2. A list of leftover snapshots in the first prompt of a restarted agent-seat, added by `nc-systems/handoff/handoff-supervisor.py`.
3. A restore procedure for the restarted agent, printed with that list.
4. A backstop in `scripts/clean-worktrees.py` for snapshots nobody restores.

## 1. Writing and deleting snapshots while agents work

The hook runs as a PostToolUse hook after every Edit, Write and NotebookEdit call, and after every Bash call.

- **Which worktree.** For Edit, Write and NotebookEdit, the hook uses the git worktree that contains the edited file, found with `git -C <the file's directory> rev-parse --show-toplevel`. For Bash, it uses the worktree containing the `cwd` field of the hook's input, which is where that Bash call ran. A path outside any git worktree is skipped.
- **The snapshot's name.** One git ref per worktree: `refs/work-snapshots/<worktree directory name>-<first 8 hex digits of the SHA-1 of the worktree's absolute path>`, for example `refs/work-snapshots/agent-a6679693cebd33239-3f9a1c2e`. The hash keeps apart worktrees with the same directory name, such as the review checkouts merge-lane-2 names `main` and `wt` in different scratch directories. Each new snapshot overwrites the ref, so a worktree has at most one snapshot, its latest.
- **What a snapshot holds.** Every change in the worktree that git would commit with `git add -A`: modified and deleted tracked files, and new files that `.gitignore` does not exclude. Ignored files, such as cold-read-records, are left out. The hook builds the snapshot without touching the worktree's index, branch or files: it copies the worktree's index (`git rev-parse --git-path index`) to a temporary file, runs `git add -A` with `GIT_INDEX_FILE` set to that copy, writes the tree with `git write-tree`, and makes a commit whose parent is the worktree's HEAD with `git commit-tree`. No commit hooks run, and the branch does not move.
- **The snapshot's message** is one summary line followed by git trailers, one per fact, which the module reads back with `git interpret-trailers --parse`: `Work-snapshot-worktree:` the worktree's absolute path; `Work-snapshot-branch:` its branch, or `(detached)`; `Work-snapshot-agent-seat:` the agent-seat, from the `GIT_AUTHOR_NAME` the launcher sets; `Work-snapshot-transcript:` the `transcript_path` field of the hook's input, which for a forked subagent is its own transcript; `Work-snapshot-operation:` `rebase`, `merge` or `cherry-pick` when one is in progress, otherwise absent. The commit's date is the snapshot's time.
- **When there is nothing uncommitted**, the hook deletes the worktree's ref if one exists. The hook runs after the Bash call that makes a commit, so the snapshot of now-committed work is deleted at once.
- **During a rebase, merge or cherry-pick**, the hook snapshots as usual and names the operation in the trailer, so a hand-merge's conflict resolution is protected too. A restorer then knows the files came from the middle of that operation.
- **Cost.** The hook first runs `git status --porcelain`; when the worktree is clean and has no ref, it stops there. Building a snapshot takes about a tenth of a second in this repository.
- **Failure.** If the hook cannot write or delete a snapshot, it prints what failed to the agent as a warning and exits without blocking the tool call: the agent's work continues, and the agent knows its work is not protected.

The hook is wired in `.claude/settings.json`, which changes only with the user's approval of the exact wiring.

## 2. Leftover snapshots in the restarted agent-seat's first prompt

When `handoff-supervisor.py` starts an agent-seat's next agent-session, by resuming a crashed transcript or from a session-handoff, it adds to the first prompt a list of the leftover snapshots of this agent-seat. A snapshot is leftover when its `Work-snapshot-agent-seat` trailer names this agent-seat and no live agent is working in its worktree: the worktree no longer exists, or both of the cleaner's checks find it unused, `worktree_vacancy_keep_reason` (no process has its working directory there) and, for a subagent's `agent-<id>` worktree, `agent_worktree_quiet_keep_reason` (neither the subagent's transcript nor the worktree was written in the last hour; a subagent runs inside its parent's process, so the first check alone cannot see it). When there are none, the prompt says nothing about snapshots.

Each line names the full ref, the worktree path and whether it still exists, the branch, the snapshot's time, the transcript path, the operation if any, and the files changed. The list appears after a session-handoff too, because a fork can die while its parent agent-session lives on and ends normally.

## 3. Restoring a snapshot

The list is followed by these steps, which the restarted agent carries out for each listed snapshot before other work:

1. See what the snapshot changes: `git diff --stat <ref>^ <ref>`, then `git diff <ref>^ <ref>`.
2. Read the end of the transcript the snapshot names, to learn what the dead agent was doing. A crash during a hand mutant or a mutation run leaves the mutant in the snapshot: on 2026-10-04 the leftover in a worktree was the mutant that turned off a test's signal recorder. Decide which changed files hold work to keep and which hold a mutant or nothing wanted.
3. To keep work, use the snapshot's worktree if it still exists and is on the snapshot's branch. Otherwise make one: `git worktree add <path> <branch>` when the branch still exists, or `git worktree add -b <new branch name> <path> origin/main` when it does not, with `<path>` under the agent's own scratchpad or `.claude/worktrees/`. From that worktree's root, apply only the files to keep: `git diff --binary <ref>^ <ref> -- <file> <file> ... | git apply --3way`. This carries modifications, new files and deletions alike, and `--3way` reports a conflict instead of failing silently when main has moved under those files. Commit at once, then continue the work or hand it on.
4. Delete the ref, using the full name from the list: `git update-ref -d <ref>`. Do this whether the work was kept or dropped. Dropping needs no other step; the cleaner handles the worktree.
5. In the next message to the user, name each snapshot and say what was kept and what was dropped, and why.

## 4. The daily backstop

The daily cleaner run gains one step, after its worktree removals, for snapshots no restart handled:

- **A snapshot whose worktree still exists** is kept: the worktree still holds the work, and the hook refreshes or deletes the snapshot at the next tool call there.
- **A snapshot whose worktree is gone and whose changes are already on main** is deleted. The test is that the snapshot's changes reverse-apply cleanly to `origin/main`: `git diff --binary <ref>^ <ref> | git apply --check --reverse` run against a checkout of `origin/main`. The cleaner does not fetch, so a stale `origin/main` only keeps more snapshots, never fewer.
- **A snapshot whose worktree is gone and that is older than 30 days** is deleted, with its ref and changed files named in the log.
- Every snapshot kept is reported in the log with its age and the reason it was kept.

Old snapshots that a newer one overwrote are no longer referenced; git's own housekeeping removes them after its `gc.pruneExpire` period, two weeks by default, with no job of ours.

## Machines

Each machine snapshots into its own clone: on ned-box the clone at `/home/nedlern/Projects/nedschorus`, whose worktrees all share its object store and refs; on the Mac the clone at `/Users/el/Projects/nedschorus`. Snapshots are refs on disk, so they survive a reboot. Nothing is copied between machines; an agent-seat restarts on the machine it ran on.

## What this design does not do

- It does not change the cleaner's removal rule.
- It does not protect ignored files, or files outside a git worktree, such as a scratchpad file under `/tmp`.
- It does not push snapshots anywhere; they never leave the machine.
- It does not restore anything without an agent's check, because a snapshot can hold a mutant.

## How it will be tested

- A worktree with a modified tracked file, a deleted tracked file, a new untracked file and an ignored file gets a snapshot holding the first three and not the fourth; its branch, index and HEAD are unchanged.
- Two worktrees with the same directory name in different directories get different refs.
- The hook run after a Bash call that commits everything deletes the ref.
- During a merge with conflicts, the hook writes a snapshot whose operation trailer says `merge`.
- A hook failure prints a warning and does not block.
- A Bash hook input whose `cwd` is a subagent's worktree snapshots that worktree, not the parent's.
- With a worktree removed and its snapshot left, the restart prompt lists it; with a live process rooted in the worktree, or a subagent transcript written in the last hour, it does not.
- The cleaner deletes a snapshot whose changes are on main, deletes one older than 30 days with a log line, keeps a recent one whose worktree is gone, and keeps one whose worktree exists.
- Restoring a chosen subset of a snapshot's files with the documented `git apply` command brings back those modifications, new files and deletions, and leaves the rest out.
- The 2026-10-05 loss replayed: a worktree on a branch with no commits of its own, two uncommitted files, owner process killed, transcript quiet, cleaner run; the snapshot survives, the restart prompt lists it, and restoring it brings both files back.

## Decisions for the user

1. The hook wiring in `.claude/settings.json`: after Edit, Write and NotebookEdit, and after Bash.
2. The 30-day age after which the cleaner deletes an unrestored snapshot whose worktree is gone.
