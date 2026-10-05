# Work snapshots of uncommitted changes, for recovery after a crash: design

Status: proposed, for the user's approval. Nothing here is built yet.

## The problem

An agent's committed work is safe: the branch keeps it, and the worktree cleaner keeps any worktree whose branch has commits that are not on main. Work an agent has not yet committed lives only in the worktree's files. Two things can take it away:

- **A crash.** An agent-session, or a forked subagent (a fork, below) working in its own worktree, dies with edits on disk and no commit. A fork runs inside its parent agent-session's `claude` process, so when that process dies, all its forks die with it.
- **The cleaner, after a crash.** `scripts/clean-worktrees.py --remove` runs on each machine every day at 06:30 and at every session-handoff. Among the worktrees it manages, under `.claude/worktrees/` in each machine's clone, it removes one whose branch has no commits beyond `origin/main` and in which nothing is running, together with any uncommitted files it holds. It names up to ten of those files in its output. A branch with no commits of its own passes that test. So a worktree whose agent died before its first commit is removed with its edits.

This happened on ned-box. On 2026-10-04 at 21:14:56 a test sent SIGTERM to every process of the `nedlern` account, killing every agent-session and fork on the machine. One fork had edited two files for a change to `scripts/resupervise-seat-test.py` and committed nothing. At 06:30 on 2026-10-05 the cleaner removed that fork's worktree and both files; ned-box's `/home/nedlern/.claude/daily-clean-worktrees.log` records the removal. The work was rebuilt only because the fork's transcript recorded every edit. Other dead forks' worktrees survived because each had made at least one commit.

The cleaner's rule is right for its job. What was missing is a copy of the uncommitted work that outlives both the crash and the cleanup, and a way for the agent-seat's next agent-session to find that copy and restore it.

## What this design does

It keeps a copy of a worktree's uncommitted changes, called a work snapshot here, as a git commit in the clone's shared object store, under a ref that no branch points to. While its agent works, the work snapshot follows the worktree and is deleted once nothing is left uncommitted. When the `claude` process that wrote a work snapshot is gone, the work snapshot is a leftover: the agent-seat's next agent-session is told about it and restores what is worth keeping.

The design is one shared module, `nc-systems/handoff/uncommitted-work-snapshots.py`, and three callers:

1. A hook, `scripts/uncommitted-work-snapshot-hook.py`, that writes, refreshes and deletes work snapshots while agents work.
2. `nc-systems/handoff/handoff-supervisor.py`, which lists leftover work snapshots, with restore steps, in the first prompt of every agent-session it starts.
3. `scripts/clean-worktrees.py`, which deletes leftover work snapshots nobody restored within 30 days.

## 1. The hook: writing, refreshing and deleting work snapshots

The hook is a Claude Code PostToolUse hook. It runs after every Edit, Write and NotebookEdit call, and after every Bash call.

**Which worktrees it handles.**
- After Edit, Write and NotebookEdit: the git worktree that contains the edited file, found with `git -C <the file's directory> rev-parse --show-toplevel`.
- After Bash: the git worktree that contains the `cwd` field of the hook's input, and every other worktree that still exists and already has a work snapshot owned by this `claude` process. A Bash command can change files in a worktree other than the one it starts in (`cd`, `git -C`, an absolute path); the second set keeps such a worktree's work snapshot current once it has one.
- Only worktrees of this project's clone: the hook skips a worktree whose `git rev-parse --git-common-dir` is not the clone's own, so other repositories on the machine are never touched.

**Who owns a work snapshot.** The `claude` process the hook was started by: the hook follows its chain of parent processes to the first one whose command is `claude`, and records its process id and start time in whole seconds since 1970: on Linux, field 22 of `/proc/<pid>/stat` divided by the clock-tick rate (`os.sysconf('SC_CLK_TCK')`) plus the boot time from the `btime` line of `/proc/stat`; on macOS, the date `ps -o lstart= -p <pid>` prints, converted. A process id with a different start time is a different process, so a reused process id is not mistaken for the owner. Forks run inside their parent's `claude` process, so a fork's work snapshots are owned by that process.

**The ref.** `refs/work-snapshots/<owner process id>-<owner start time in seconds>/<SHA-1 of the worktree's absolute path with symlinks resolved, all 40 hex digits>`. The ref contains only digits, hex and one hyphen, so any worktree path gives a legal ref name. Each owner process has its own refs, so a later agent-session working in the same worktree never overwrites or deletes a dead process's leftover. Within one owner, each new work snapshot replaces that worktree's previous one.

**What a work snapshot holds.** Every change `git add -A` would stage: modified and deleted tracked files, and new files that git's ignore rules (`.gitignore` files, `.git/info/exclude` and the user's global excludes file) do not exclude. Ignored files, such as cold-read-records, are not held. The hook builds it without changing the worktree's index, branch or files, running every git command with `git -C <worktree>`:
1. `git --no-optional-locks status --porcelain --untracked-files=all` checks whether anything is uncommitted. `--no-optional-locks` keeps git from rewriting the index, and `--untracked-files=all` overrides any setting that hides new files.
2. If something is, the hook copies the worktree's index (`git rev-parse --git-path index`) to a temporary file, runs `git add -A` with `GIT_INDEX_FILE` set to the copy, writes the tree with `git write-tree`, makes a commit with `git commit-tree`, whose parent is the worktree's HEAD, and deletes the temporary index. No git hooks run, and no branch moves.
3. It sets the ref with `git update-ref <ref> <new commit> <old value>`, where the old value is what the ref held when the hook read it, or 40 zeros when it did not exist. That succeeds only if no overlapping hook run changed the ref in between; on that conflict it builds the work snapshot again once.

**The work snapshot's message** is a summary line and git trailers, which the module reads with `git interpret-trailers --parse`:
- `Work-snapshot-worktree:` the worktree's absolute path.
- `Work-snapshot-branch:` its branch, or `detached`.
- `Work-snapshot-agent-seat:` the agent-seat, from `GIT_AUTHOR_NAME`, which `scripts/launch-claude-ubuntu`, `scripts/launch-claude-mac` and `scripts/recover-crashed-seats.py` set to the agent-seat's name; `unknown` when it is unset.
- `Work-snapshot-transcript:` the `transcript_path` field of the hook's input.
- `Work-snapshot-operation:` `merge`, `rebase`, `cherry-pick`, `revert` or `am` when git shows that operation in progress (`MERGE_HEAD`, a `rebase-merge` or `rebase-apply` directory, `CHERRY_PICK_HEAD`, `REVERT_HEAD`); absent otherwise.

The commit's author date is the work snapshot's time.

**When nothing is uncommitted**, the hook deletes that worktree's ref for this owner, if there is one. The hook runs after the Bash call that makes a commit, so a work snapshot of now-committed work is deleted when that call returns.

**What it cannot protect.** Changes made by a tool call that is killed before it returns, and changes a Bash command makes in a worktree that has no work snapshot yet and is not the command's `cwd`, have no work snapshot until the hook next runs for that worktree. Ignored files and files outside a git worktree are never held.

**Failure.** If the hook cannot read the worktree's state, write a work snapshot or delete a ref, it reports what failed to the agent through the PostToolUse output field `additionalContext`, so the agent knows that worktree's work is not protected, and exits 0, since the tool call has already happened.

The hook's wiring in `.claude/settings.json` changes only with the user's approval of the exact text.

## 2. Leftover work snapshots in the next agent-session's first prompt

Every time `nc-systems/handoff/handoff-supervisor.py` starts an agent-session, whatever the reason (a crash resume, a session-handoff, a first start, or recovery by `scripts/recover-crashed-seats.py`), it adds to the first prompt the agent-seat's leftover work snapshots: those whose `Work-snapshot-agent-seat` trailer names this agent-seat and whose owner process is gone. A worktree's existence does not matter: a dead owner's work snapshot is listed whether its worktree survives or the cleaner removed it.

- Each entry gives the ref, the worktree path and whether it exists, the branch, the time, the transcript path and whether that file exists, the operation if any, and up to ten changed files with a count of the rest.
- At most 20 entries are listed, newest first, then a count of the rest and the command that lists them all: `python3 nc-systems/handoff/uncommitted-work-snapshots.py list --agent-seat <name>`.
- When there are none, the prompt says nothing about work snapshots.
- When the list cannot be built, the prompt says so, with the reason and that same command, so the failure is not mistaken for "none".

## 3. The restore steps, printed with the list

The restore steps come before the agent's other work. They are written as instructions, with no history.

For each listed work snapshot:

1. **See what it holds:** `git diff --stat <ref>^ <ref>`, then `git diff <ref>^ <ref>`.
2. **Decide what to keep.** If you keep nothing, skip step 3. Read the end of the transcript the entry names, to learn what the dead agent was doing; if the transcript is gone, decide from the diff alone, and ask the user when unsure. Drop any mutant: a deliberate small break in code that mutation testing makes, by a program or by an agent's own edit, to check that the tests notice. A crash during mutation testing leaves the mutant in the work snapshot. If one file holds both wanted work and a mutant, keep the file and remove the mutant from it by editing it before you commit in step 3.
3. **Restore what you keep, as a commit.**
   - If the worktree still exists, and `python3 nc-systems/handoff/uncommitted-work-snapshots.py matches <ref>` prints `yes` (the worktree's HEAD is still `<ref>^`, and a work snapshot built from the worktree now has the same tree as `<ref>`), the changes are still in it. In that worktree, commit the files you keep with `git add -- <files>` and `git commit -m "Restore work from <ref>"`, and undo the rest: `git restore --source=HEAD --staged --worktree -- <dropped tracked files>`, and delete the dropped new files. If the worktree no longer matches, leave it alone and restore into a new worktree as below.
   - If the worktree is gone, make one from the work snapshot's parent, so the changes apply without conflict. With `<name>` standing for `restored-` and the ref's last two parts joined by a hyphen, which no other work snapshot shares: `git worktree add -b <name> <clone>/.claude/worktrees/<name> <ref>^`, where `<clone>` is the clone's main checkout, the directory containing the path `git rev-parse --path-format=absolute --git-common-dir` prints. In the new worktree, run `git diff --binary <ref>^ <ref> -- <files to keep> | git apply --index`, then `git commit -m "Restore work from <ref>"`. The restored branch is ordinary work in progress: carry it on, or tell the user it is there; the cleaner keeps its worktree while the branch has a commit not on main, and removes it once the branch is merged.
   - If the entry names an operation, the files are from the middle of that merge, rebase or similar, and git's record of the operation is not in the work snapshot, so it cannot be resumed. Do not restore such a work snapshot by yourself: tell the user what it holds, and restore only what the user decides.
   - If a command here fails, stop, leave the ref in place, and tell the user what failed.
4. **Delete the ref:** `git update-ref -d <ref>`, whether the work was kept or dropped.
5. **Tell the user**, in the next message to the user, each work snapshot handled, what was kept and where, and what was dropped and why. Finishing the dead agent's task is a separate decision, made after the restore.

## 4. The cleaner: removing what nobody restored

`scripts/clean-worktrees.py --remove`, at its daily run and at every session-handoff, also handles work snapshots, after its worktree removals:
- It deletes a work snapshot whose owner process is gone and whose author date is more than 30 days old, writing its ref, worktree path and changed files in its output, which the daily run appends to `~/.claude/daily-clean-worktrees.log` on that machine.
- It reports every other work snapshot whose owner process is gone, with its age, including those whose agent-seat is `unknown`, which no agent-session's list shows.
- Run without `--remove`, it only reports, and deletes nothing.
- It never deletes a work snapshot whose owner process is alive.
- If it cannot list or delete work snapshots, it says so in its output and exits nonzero.

A replaced work snapshot's commit is no longer referenced by any ref; git's automatic `git gc --auto`, which ordinary git commands start when loose objects pile up, removes such objects once they are older than `gc.pruneExpire`, two weeks by default. A work snapshot stores only the changed files, so these objects are small.

## Machines

Each machine has its own clone and its own work snapshots: on ned-box the clone at `/home/nedlern/Projects/nedschorus`, on the Mac the clone at `/Users/el/Projects/nedschorus`. All of a clone's worktrees share its refs, so an agent-session can see work snapshots from any worktree of that clone. Work snapshots are refs on disk, so they survive a reboot. An ordinary `git push` sends branches and tags, not `refs/work-snapshots/`, so work snapshots stay on the machine, apart from the machine's own disk backups, which copy the whole clone.

## What this design does not do

- It does not change which worktrees the cleaner removes.
- It does not hold ignored files, or files outside a git worktree.
- It does not restore anything without an agent deciding what to keep.

## How it will be tested

- A worktree with a modified tracked file, a deleted tracked file, a new file, and files excluded by `.gitignore`, `.git/info/exclude` and a global excludes file gets a work snapshot holding the first three only; its index file, branch and HEAD are unchanged.
- Two worktrees whose directories have the same name get different refs; a path with a space gives a legal ref.
- The hook run after a Bash call that commits everything deletes the ref; one after a Bash call whose `cwd` is a fork's worktree handles that worktree.
- Two overlapping hook runs leave the ref pointing at a work snapshot of the final state.
- During a merge with conflicts, the work snapshot's operation trailer is `merge`.
- A hook that cannot write reports it through `additionalContext` and exits 0.
- An owner process still running keeps its work snapshots off the list; a dead one's are listed, whether or not the worktree exists; a reused process id with a different start time counts as dead.
- The list caps at 20 entries and ten files each, and a failure to build it is stated in the prompt.
- Restoring a chosen subset of files, both in a surviving worktree and into a new worktree from `<ref>^`, gives a commit with exactly those modifications, new files and deletions.
- The cleaner deletes a dead owner's work snapshot older than 30 days, naming it in its output, and keeps a younger one and a live owner's one.
- The 2026-10-05 loss replayed: a worktree on a branch with no commits of its own, two uncommitted files, the owner process killed, the cleaner run, which removes the worktree; the next agent-session's first prompt lists the work snapshot, and following the restore steps brings both files back as a commit.

## Decisions for the user

1. The hook wiring in `.claude/settings.json`: after Edit, Write and NotebookEdit, and after Bash.
2. The 30 days after which the cleaner deletes a work snapshot nobody restored.
