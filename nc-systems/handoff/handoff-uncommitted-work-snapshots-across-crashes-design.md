# Work-snapshots of uncommitted changes, for recovery after a crash: design

Status: approved by the user in the approval-walk uncommitted-work-snapshots-across-crashes-design-2026-10-05-2 (minutes: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/uncommitted-work-snapshots-across-crashes-design-2026-10-05-2-minutes.md`); built by the pull request that moved it here.

## The problem

An agent's committed work keeps its worktree until the work reaches main or its pull request is closed: the worktree cleaner removes a worktree only once nothing the worktree holds still waits, and a worktree whose branch has commits not on main waits until the branch's pull request has merged or been closed, or, with no pull request, until the worktree's owner has stopped; after that the branch keeps the commits. Work an agent has not yet committed lives only in the worktree's files. Two things can take it away:

- **A crash.** An agent-session, or a forked subagent (a fork, below) working in its own worktree, dies with edits on disk and no commit. A fork runs inside its parent agent-session's `claude` process, so when that process dies, all its forks die with it.
- **The cleaner, after a crash.** `scripts/clean-worktrees.py --remove` runs on each machine every day at 06:30 and at every session-handoff. It judges a worktree by its owner file, which names the agent-seat or agent-session that owns it; an agent-seat counts as running while its handoff-supervisor runs, and an agent-session while its process runs. A worktree with no owner file is removed only once nothing in it has changed for 2 days and it holds no uncommitted or untracked file. Agent-homes and the reference-checkout are never removed, nor is any worktree locked with `git worktree lock`. The exception is a lock in the form Claude Code writes, "claude agent agent-<id> (pid N start T)", once no process N that started at T runs: the cleaner unlocks the worktree, gives a worktree with no owner file one naming that ended agent-session and the agent-seat whose Claude Code transcripts name subagent agent-<id>, and judges it like any other; when no transcript names it, the cleaner keeps it and lists it to the user. While its owner runs, a worktree is removed once its branch's pull request has merged or closed and it holds no uncommitted or untracked file. Once its owner has stopped, an open pull request keeps it; otherwise its uncommitted and untracked files go to a work-snapshot, and it is removed.

This happened on ned-box. On 2026-10-04 at 21:14:56 a test sent SIGTERM to every process of the `nedlern` account, killing every agent-session and fork on the machine. One fork had edited two files for a change to `scripts/resupervise-seat-test.py` and committed nothing. At 06:30 on 2026-10-05 the cleaner removed that fork's worktree and both files; ned-box's `/home/nedlern/.claude/daily-clean-worktrees.log`, the cleaner's log under the job's name at the time, records the removal. The work was rebuilt only because the fork's transcript recorded every edit. Other dead forks' worktrees survived because each had made at least one commit.

The cleaner's rule is right for its job. What was missing is a copy of the uncommitted work that outlives both the crash and the cleanup, and a way for the agent-seat's next agent-session to find that copy and restore it.

## What this design does

It keeps a copy of a worktree's uncommitted changes, a work-snapshot, as a git commit in the clone's shared object store, under a ref that no branch points to. While its agent works, the work-snapshot follows the worktree and is deleted once nothing is left uncommitted. When the `claude` process that wrote a work-snapshot is gone, the work-snapshot is a leftover: the agent-seat's next agent-session is told about it and restores what is worth keeping.

The design is one shared module, `nc-systems/handoff/uncommitted-work-snapshots.py`, and three callers:

1. A hook, `scripts/uncommitted-work-snapshot-hook.py`, that writes, refreshes and deletes work-snapshots while agents work.
2. `nc-systems/handoff/handoff-supervisor.py`, which lists leftover work-snapshots whose worktree is gone or no longer holds their changes, each entry ending with the `restore` or `discard` command that handles it, followed by the restore steps, in the first prompt of every agent-session it starts.
3. `scripts/clean-worktrees.py`, which deletes a leftover work-snapshot nobody restored within 10 days of its first listing in an agent-session's first prompt, and closes the task a `restore` opened once its restore commit is on main or no ref holds it.

## 1. The hook: writing, refreshing and deleting work-snapshots

The hook is a Claude Code PostToolUse hook. It runs after every Edit, Write and NotebookEdit call, and after every Bash call.

**Which worktrees it handles.**
- After Edit, Write and NotebookEdit: the git worktree that contains the edited file, found with `git -C <the file's directory> rev-parse --show-toplevel`.
- After Bash: the git worktree that contains the `cwd` field of the hook's input, and every other worktree that still exists and already has a work-snapshot owned by this `claude` process. A Bash command can change files in a worktree other than the one it starts in (`cd`, `git -C`, an absolute path); the second set keeps such a worktree's work-snapshot current once it has one.
- Only worktrees of this project's clone: the hook skips a worktree whose `git rev-parse --git-common-dir` is not the clone's own, so other repositories on the machine are never touched.

**Who owns a work-snapshot.** The `claude` process the hook was started by: the hook follows its chain of parent processes to the first one whose command is `claude`, and records an owner key that names that process alone. On Linux the owner key is `<boot id>-<process id>-<start ticks>`: the boot id from `/proc/sys/kernel/random/boot_id` with its hyphens removed, and the start ticks from field 22 of `/proc/<pid>/stat`. The start ticks count from boot and never change while the process runs; a start time converted to seconds since 1970 through the `btime` line of `/proc/stat` would move whenever the system clock is stepped, and a live owner would then look dead. The boot id tells one boot's start ticks from another's. On macOS the owner key is `<process id>-<start seconds>`, the date `ps -o lstart= -p <pid>` prints, converted; macOS keeps that date with the process, so a later clock change does not alter it. A process id with a different start is a different process, so a reused process id is not mistaken for the owner. Forks run inside their parent's `claude` process, so a fork's work-snapshots are owned by that process. When no `claude` process is in the chain, the hook writes no work-snapshot and tells the agent its uncommitted work is not protected and why, so a launch whose process is named differently is seen on its first edit.

**The ref.** `refs/work-snapshots/<owner key>/<SHA-1 of the worktree's absolute path with symlinks resolved, all 40 hex digits>`. The ref contains only digits, hex and hyphens, so any worktree path gives a legal ref name. Each owner process has its own refs, so a later agent-session working in the same worktree never overwrites or deletes a dead process's leftover. Within one owner, each new work-snapshot replaces that worktree's previous one.

**What a work-snapshot holds.** Every change `git add -A` would stage: modified and deleted tracked files, and new files that git's ignore rules (`.gitignore` files, `.git/info/exclude` and the user's global excludes file) do not exclude. Ignored files, such as cold-read-records, are not held. The hook builds it without changing the worktree's index, branch or files, running every git command with `git -C <worktree>`:
1. `git --no-optional-locks status --porcelain --untracked-files=all` checks whether anything is uncommitted. `--no-optional-locks` keeps git from rewriting the index, and `--untracked-files=all` overrides any setting that hides new files.
2. If something is, the hook copies the worktree's index (`git rev-parse --git-path index`) to a temporary file, runs `git add -A` with `GIT_INDEX_FILE` set to the copy, writes the tree with `git write-tree`, and deletes the temporary index. When the work-snapshot the ref holds already has that tree, the worktree's HEAD as its parent and the message below, the hook stops there and leaves the ref as it is, so a run on an unchanged worktree writes no object; otherwise it makes a commit with `git commit-tree`, whose parent is the worktree's HEAD. No git hooks run, and no branch moves.
3. It sets the ref with `git update-ref <ref> <new commit> <old value>`, where the old value is what the ref held when the hook read it, or 40 zeros when it did not exist. That succeeds only if no overlapping hook run changed the ref in between; on that conflict it builds the work-snapshot again once.

**The work-snapshot's message** is a summary line and git trailers, which the module reads with `git interpret-trailers --parse`:
- `Work-snapshot-worktree:` the worktree's absolute path.
- `Work-snapshot-branch:` its branch, or `detached`.
- `Work-snapshot-agent-seat:` the agent-seat, from `GIT_AUTHOR_NAME`, which `scripts/launch-claude-ubuntu`, `scripts/launch-claude-mac` and `scripts/recover-crashed-seats.py` set to the agent-seat's name; `unknown` when it is unset.
- `Work-snapshot-transcript:` the `transcript_path` field of the hook's input.
- `Work-snapshot-operation:` `merge`, `rebase`, `cherry-pick`, `revert` or `am` when git shows that operation in progress (`MERGE_HEAD`, a `rebase-merge` or `rebase-apply` directory, `CHERRY_PICK_HEAD`, `REVERT_HEAD`); absent otherwise.

The commit's author date is the work-snapshot's time: when the hook first saw the worktree in the state it holds.

**When nothing is uncommitted**, the hook deletes that worktree's ref for this owner, if there is one. The hook runs after the Bash call that makes a commit, so a work-snapshot of work that has since been committed is deleted when that call returns.

**What it cannot protect.** Changes made by a tool call that is killed before it returns, and changes a Bash command makes in a worktree that has no work-snapshot yet and is not the command's `cwd`, have no work-snapshot until the hook next runs for that worktree. Ignored files and files outside a git worktree are never held.

**Failure.** If the hook cannot read the worktree's state, write a work-snapshot or delete a ref, it reports what failed to the agent through the PostToolUse output field `additionalContext`, so the agent knows that worktree's work is not protected, and exits 0, since the tool call has already happened.

The hook's wiring in `.claude/settings.json` changes only with the user's approval of the exact text.

## 2. Leftover work-snapshots in the next agent-session's first prompt

Every time `nc-systems/handoff/handoff-supervisor.py` starts an agent-session, whatever the reason (a crash resume, a session-handoff, a first start, or recovery by `scripts/recover-crashed-seats.py`), it adds to the first prompt the agent-seat's lost work: each leftover work-snapshot, one whose `Work-snapshot-agent-seat` trailer names this agent-seat and whose owner process is gone, whose changes may exist nowhere else. An owner process ends at every session-handoff, and a `claude` process that runs out of quota or is logged out may be ended and restarted too, while its files stay in its worktree; agent-seat checkouts also keep drafts uncommitted on purpose. So whether the owner is alive decides only whether the cleaner may ever delete a work-snapshot, and each leftover falls in one of two states:

- **Lost:** the worktree is gone, or still exists but no longer holds the work-snapshot's changes (its HEAD is not the work-snapshot's parent, or a work-snapshot built from it now would have another tree). Listed. This includes changes a later agent committed or discarded: whether a change still exists somewhere else is not judged, because every way of judging it that was tried could delete the only copy. A committed draft's leftover is therefore listed too; the restore steps' diff shows the agent the work is already committed, and the agent deletes the work-snapshot. That is an accepted cost. A directory without a `.git` entry where the worktree was, which an interrupted removal can leave, counts as gone, since git there answers for the checkout around it. A leftover whose worktree cannot be read is listed too, with the reason, since its changes may exist nowhere else.
- **In place:** the worktree still holds exactly its changes, as after a session-handoff. Not listed, and kept, so that if the worktree is removed later, by the cleaner or anyone else, the work-snapshot is still there and is then listed as lost.

**Duplicates.** Each session-handoff of an agent-seat that keeps uncommitted drafts leaves another leftover of the same files, written by the next owner. A leftover is a duplicate when a newer leftover of the same agent-seat and the same worktree has the same parent commit and the same tree, compared by git object id, so the newer one holds every byte it holds. A duplicate is not listed, the newer one standing for it, and the cleaner deletes it. Only leftovers count: never a live owner's work-snapshot, which its own hook may delete, and never the worktree or its HEAD.

- The first time the handoff-supervisor lists a work-snapshot, it records the time in `~/.claude/handoffs/<seat>-work-snapshots-first-listed.json` on that machine, ref to time; the cleaner reads that file. A failure to write it is said in the first prompt, and that work-snapshot then counts as never listed.
- Each entry gives the ref, the worktree path and whether it exists, the branch, the time, the transcript path and whether that file exists, the operation if any, and up to ten changed files with a count of the rest, and ends with the command that handles it (section 3).
- At most 20 entries are listed, newest first, then a count of the rest and the command that lists them all: `python3 nc-systems/handoff/uncommitted-work-snapshots.py list --agent-seat <name>`.
- When there are none, the prompt says nothing about work-snapshots.
- When the list cannot be built, the prompt says so, with the reason and that same command, so the failure is not mistaken for "none".

## 3. Restoring or discarding a leftover: the `restore` and `discard` commands, and the task a restore opens

Each entry the handoff-supervisor lists in the initial-agent-instructions ends with the command that handles that work-snapshot: `python3 nc-systems/handoff/uncommitted-work-snapshots.py discard <ref>` for a work-snapshot taken during a merge, rebase, cherry-pick, revert or am, and otherwise `python3 nc-systems/handoff/uncommitted-work-snapshots.py restore <ref> --keep` followed by every changed file, each path quoted for the shell, so the agent's only edit to the command is to delete the files it drops. After the list come the restore steps, the constant `RESTORE_STEPS`, which hold only the steps that need the agent's judgment; the two commands do every other step.

### The steps that need the agent's judgment

The restore steps come before the agent's other work. They are written as instructions, with no history. For each listed work-snapshot:

1. **See what it holds:** `git diff --stat <ref>^ <ref>`, then `git diff <ref>^ <ref>`.
2. **Decide what to keep.** Read the end of the transcript the entry names, to learn what the dead agent was doing; if the transcript is gone, decide from the diff alone, and ask the user when unsure. Drop any mutant: a deliberate small break in code that nc-mutation-testing makes, by a program or by an agent's own edit, to check that the tests notice. A crash during nc-mutation-testing leaves the mutant in the work-snapshot. Leave a file that holds only a mutant off `--keep`; keep a file that holds both wanted work and a mutant, and after `restore` remove the mutant from it in a commit of its own on the restored branch, before the branch is pushed.
3. **Run the entry's command.** To keep one file or more, run `restore`, after deleting from `--keep` the files you drop. To keep nothing, run `discard`. For a work-snapshot taken during an operation, run `discard`, as its entry says. When the command refuses or fails, do what it prints, and tell the user what failed.

Whether to finish the dead agent's task is a separate decision, made after the restore; the task `restore` opens keeps the restored branch on the agent-seat's task list until that decision is carried out.

### `restore <ref> --keep <file> [<file> ...]`

`--keep` takes one file or more; the paths are relative to the clone's root, as the list entry prints them. The branch is named `restored-` followed by the ref's last two parts joined by a hyphen, which no other work-snapshot shares; the worktree is `<clone>/.claude/worktrees/<branch name>`, where `<clone>` is the clone's main checkout, the directory containing the path `git rev-parse --path-format=absolute --git-common-dir` prints.

Before it changes anything, `restore` refuses, saying why, when:

- the ref does not exist;
- `--keep` names no file, which would restore every file; the refusal says that keeping nothing is `discard`;
- a kept path is not among the work-snapshot's changed files;
- the work-snapshot was taken during a merge, rebase, cherry-pick, revert or am; the refusal names the work-snapshot's worktree and operation, and tells the agent to run `discard` and to tell the user which worktree and which operation were discarded. Git's record of the operation is not in the work-snapshot, so the operation cannot be resumed; its commits are still on the branches, so only the conflict resolution done before the crash is lost, with any uncommitted edits to files the operation does not touch, which is accepted because agents commit before merging and crashes are rare;
- the branch or the worktree directory already exists; when the branch's newest commit is `Restore work from <ref>`, the work is already restored and only the ref's deletion failed earlier, so the refusal says so and prints the `git update-ref -d <ref>` to run;
- `CLAUDE_CODE_TASK_LIST_ID` or `GIT_AUTHOR_NAME` is unset; the launchers set both for every agent-seat.

Otherwise it does, in order:

1. `git worktree add -b <branch name> <worktree> <ref>^`, from the work-snapshot's parent, so the changes apply without conflict. The entry's own worktree, if it still exists, no longer holds these changes and is left alone.
2. Writes the new worktree's owner file, naming the agent-seat `GIT_AUTHOR_NAME` names, with `scripts/worktree-owner-file-read-and-write.py`, so that `scripts/clean-worktrees.py` judges the worktree as it judges the agent-seat's other worktrees, and the agent-seat's list of worktrees in the initial-agent-instructions names it.
3. In the new worktree, `git diff --binary <ref>^ <ref> -- <kept files> | git apply --index`, then `git commit -m "Restore work from <ref>"`.
4. Opens the restored branch's task, below, on the task list in `~/.claude/tasks/<CLAUDE_CODE_TASK_LIST_ID>`, making that directory when it does not yet exist.
5. Deletes the ref with `git update-ref -d <ref>`.
6. Prints the branch, the worktree and the task's id, then a summary line: the ref, the kept files, the dropped files, the branch and the worktree.

When a step fails, `restore` prints what failed and exits nonzero:

- a failure in steps 1 to 3 removes the worktree and the branch `restore` made, and leaves the ref in place; a worktree or branch that cannot be removed is named, with the command that removes it;
- a failure to open the task keeps the branch and the worktree and still deletes the ref, since the branch now holds the work, and prints the task's exact subject and description for the agent to create with Claude Code's TaskCreate tool; the cleaner closes a task with that subject as it closes one `restore` opened;
- a failure of only the ref's deletion keeps the branch and the task, and prints the `git update-ref -d <ref>` to run.

### `discard <ref>`

`discard` deletes the ref and prints its list entry, which names the files it held and, for a work-snapshot taken during an operation, the worktree and the operation, as its summary line. It refuses when the ref does not exist. It opens no task.

### The task `restore` opens, and how the task closes itself

The task's subject is `Restored branch <branch name>: open its pull request or delete it`. Its first words, `Restored branch `, are the constant `RESTORED_BRANCH_TASK_SUBJECT_PREFIX` in `nc-systems/handoff/uncommitted-work-snapshots.py`, and the branch name is the text between them and the first colon; a git branch name cannot hold a colon. Its description names the work-snapshot's ref, the worktree and transcript the entry named, the kept files and the restored worktree, and the commit `restore` made, by its SHA, on a line of its own that opens `Restore commit: `. It tells the agent: carry the branch on to a pull request, or delete it; and leave the task open, because `scripts/clean-worktrees.py` marks it completed once that commit is on main or no branch holds it any more. The task is a Claude Code task file, written as `scripts/scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.py` writes a survivor task: its id is one more than the highest of the list's task ids and its `.highwatermark`, and the file is linked into place only where no file of that name exists, so a task Claude Code creates at the same moment is not overwritten.

`scripts/clean-worktrees.py` closes these tasks with `--remove`, at its daily run and at every session-handoff, after its worktree and branch removals. So a task closes at the cleaner's next such run, not at the moment of the merge or the deletion. The cleaner reads every task list on its machine, `~/.claude/tasks/nedschorus-*-tasks`. Each task not marked completed whose subject starts with `RESTORED_BRANCH_TASK_SUBJECT_PREFIX` is marked completed, with a line at the end of its description saying why, when, after `git fetch --prune origin`, the commit its `Restore commit: ` line names is either:

- reachable from `origin/main`, because the branch's pull request merged, whatever the branch is called by then; or
- held by no ref at all, `git for-each-ref --contains <sha>` printing nothing, because the branch was deleted, in the clone and on origin, by whatever command.

The rule follows the commit, not the branch's name, so a renamed branch or one deleted with `git branch -D` is judged correctly, and a branch an agent pushed and then deleted locally stays open while origin still has it.

Any other task with that subject stays open. A pull request closed without merging leaves the task open while a branch still holds the commit, since that branch holds work main lacks. Each machine's cleaner closes the tasks of its own clone's restored branches, because `restore` writes the task list of the machine it runs on. When `git fetch` fails, a task has no `Restore commit: ` line, or a task file cannot be read or written, the cleaner leaves that task as it was, says so in a line opening `FAILED: `, and exits 1. Run without `--remove`, the cleaner names each task it would close and changes none.

## 4. The cleaner: removing what nobody restored

`scripts/clean-worktrees.py --remove`, at its daily run and at every session-handoff, also handles work-snapshots, after its worktree removals:
- It deletes a work-snapshot whose owner process is gone, which is still lost, and which was first listed in an agent-session's first prompt more than 10 days ago, writing its ref, worktree path and changed files in its output, which the scheduled run appends to `~/.claude/clean-worktrees.log` on that machine.
- It deletes a duplicate, a leftover that a newer leftover of the same agent-seat and worktree duplicates (section 2), and says so. Without this, each session-handoff of an agent-seat that keeps uncommitted drafts would leave one more work-snapshot of the same files.
- It reports every other work-snapshot whose owner process is gone, with its age, whether it was listed, and, for one in place, that its changes are still in its worktree, including those whose agent-seat is `unknown`, which no agent-session's list shows.
- A leftover whose worktree cannot be read is kept, and counted as a failure.
- Run without `--remove`, it only reports, and deletes nothing.
- It never deletes a work-snapshot whose owner process is alive.
- If it cannot list or delete work-snapshots, it says so in its output and exits nonzero.
- After its worktree and branch removals, it closes the tasks `restore` opens whose restore commit is on `origin/main` or held by no ref, as section 3 says.

A replaced work-snapshot's commit is no longer referenced by any ref; git's automatic `git gc --auto`, which ordinary git commands start when loose objects pile up, removes such objects once they are older than `gc.pruneExpire`, two weeks by default. A work-snapshot stores only the changed files, so these objects are small.

## Machines

Each machine has its own clone and its own work-snapshots: on ned-box the clone at `/home/nedlern/Projects/nedschorus`, on the Mac the clone at `/Users/el/Projects/nedschorus`. All of a clone's worktrees share its refs, so an agent-session can see work-snapshots from any worktree of that clone. Work-snapshots are refs on disk, so they survive a reboot. An ordinary `git push` sends branches and tags, not `refs/work-snapshots/`, so work-snapshots stay on the machine, apart from the machine's own disk backups, which copy the whole clone.

## What this design does not do

- It does not change which worktrees the cleaner removes.
- It does not hold ignored files, or files outside a git worktree.
- It does not restore anything without an agent deciding what to keep.

## How it will be tested

- A worktree with a modified tracked file, a deleted tracked file, a new file, and files excluded by `.gitignore`, `.git/info/exclude` and a global excludes file gets a work-snapshot holding the first three only; its index file, branch and HEAD are unchanged.
- Two worktrees whose directories have the same name get different refs; a path with a space gives a legal ref.
- The hook run after a Bash call that commits everything deletes the ref; one after a Bash call whose `cwd` is a fork's worktree handles that worktree.
- Two overlapping hook runs leave the ref pointing at a work-snapshot of the final state.
- During a merge with conflicts, the work-snapshot's operation trailer is `merge`.
- A hook that cannot write reports it through `additionalContext` and exits 0.
- An owner process still running keeps its work-snapshots off the list; a dead one's is not listed while its worktree still holds its changes, and is listed once the worktree is removed or changed, or its changes are committed or discarded; of two leftovers with the same parent and tree only the newer is listed, and two that differ in either are both listed; a leftover whose worktree cannot be read is listed with the reason; a reused process id with a different start counts as dead; a live owner still counts as alive after the system clock is stepped.
- The list caps at 20 entries and ten files each, and a failure to build it is stated in the prompt.
- `restore` of a chosen subset of files into a new worktree from `<ref>^`, both when the original worktree is gone and when it survives changed, gives a commit with exactly those modifications, new files and deletions, leaves a surviving original alone, writes the worktree's owner file, opens the task naming the restore commit, deletes the ref and prints the summary line. Each list entry ends with its command, `discard` for a work-snapshot taken during an operation and otherwise `restore` keeping every changed file, each path quoted, and the restore steps name no git step the commands carry out.
- `restore` refuses, changing nothing, a ref that does not exist, an empty `--keep`, a kept path the work-snapshot did not change, a work-snapshot taken during a merge, an existing branch or worktree directory, a branch that already holds this restore, and an unset `CLAUDE_CODE_TASK_LIST_ID` or `GIT_AUTHOR_NAME`. A `git worktree add`, an owner file, an apply and a commit that fail each remove the worktree and branch it made and keep the ref, as does an owner file that the post-checkout hook, installed through `core.hooksPath`, wrote during `git worktree add` naming another agent-seat; one naming `GIT_AUTHOR_NAME`'s agent-seat is kept and the restore goes on; and a worktree or branch it cannot remove is named with its command; a task that cannot be opened keeps the branch, deletes the ref and prints the task for TaskCreate; a ref deletion that fails keeps the branch and the task and prints the command. `discard` deletes the ref and prints its entry, refuses a ref that does not exist, reports a deletion that fails, and opens no task.
- The cleaner, after `git fetch --prune origin`, marks completed the task of a branch whose restore commit reached `origin/main` and of one deleted with `git branch -D`, and keeps open a renamed branch's and one deleted locally while origin still has it, closing that one once origin's copy is deleted; without `--remove` it names what it would close and changes nothing; a failed fetch, a task with no `Restore commit: ` line, a commit git cannot judge, a task file that cannot be read and one that cannot be rewritten are each left as they were and reported.
- The cleaner deletes a dead owner's work-snapshot first listed more than 10 days ago, naming it in its output, and keeps one listed more recently, one never listed, and a live owner's one. It keeps an in-place work-snapshot, even one first listed more than 10 days ago; deletes the older of two leftovers of the same agent-seat with the same parent and tree, and keeps both when the tree, the parent or the agent-seat differs, and keeps a leftover that only a live owner's work-snapshot duplicates; lists and keeps one where an empty directory without `.git` is left; and keeps one whose worktree cannot be read, counting a failure. A HEAD that cannot be read, including a branch whose ref names a missing object, is reported, not taken for a mismatch; a work-snapshot taken on an unborn HEAD stays in place while that HEAD is still unborn. `list` exits 1 when a work-snapshot could not be compared with its worktree.
- The 2026-10-05 loss replayed: a worktree on a branch with no commits of its own, two uncommitted files, the owner process killed, the cleaner run, which removes the worktree; the next agent-session's first prompt lists the work-snapshot, and `restore` brings both files back as a commit, whose task the cleaner closes once the restored branch is deleted.

## Decisions for the user

1. The hook wiring in `.claude/settings.json`: after Edit, Write and NotebookEdit, and after Bash.
2. The 10 days after its first listing at which the cleaner deletes a work-snapshot nobody restored. A work-snapshot never listed, because its agent-seat has not started an agent-session since or its agent-seat is `unknown`, is kept and reported, so a paused agent-seat's work waits until the agent-seat runs again.
