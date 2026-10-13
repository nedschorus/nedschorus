# Catch a guarded file changed without the user's approval, ask him, and keep every version

## What is wanted

One hook, registered under PostToolUse and PostToolUseFailure so that it runs after every tool call, that notices when a guarded file has changed without the user's approval, by any route, a shell command included. It copies the new version into a backup directory and tells the agent to ask the user. The change stays in place while he is asked. The hook reminds the agent after every tool call until the change is settled: the user approved it, or the agent put the approved version back. Every version a run sees is kept in a backup directory on ned-box, with the approved versions of each file named there. The routes it does not catch are listed under "Known gaps". Nothing is built yet; the next action is the build.

A **guarded file** here is a file that `.claude/hooks/instruction-file-guard.py` protects: `CLAUDE.md` and `CLAUDE.local.md`, everything under a `.claude/` directory apart from `worktrees/`, `jobs/` and `handoffs/`, a `-prompt.md` or `-instructions.md` file, and a reviewed document (a `.md` file under `docs/agents/`, `docs/nedschorus-wiki/` or `nc-systems/skills/`, or a `-design.md` file), with the exceptions that guard makes; plus `~/.claude/CLAUDE.md` and `~/.claude/settings.json` (term approved by the user, 2026-10-12).

## Why

The instruction-file guard is a PreToolUse hook on Edit, Write and NotebookEdit. A write to a guarded file goes through only once the agent has written the user's approval words into a one-use marker file, `.walk-approved`; a write into a Claude Code memory directory is always refused. The guard does not see a shell command, and the files a shell command will write cannot, in general, be known before it runs. Two records:

- On 2026-08-24, about 60 lines of credential reference material built up in an agent-seat's `CLAUDE.local.md`, written by shell commands, before the user noticed (GHI [Review-system design requirements learned from the legacy gate — dormant until a class of work first requires review](https://github.com/nedschorus/nedschorus/issues/31), item 2 of its list "Guards").
- On 2026-09-13 the guard was fed two payloads naming the same `CLAUDE.md`: the Edit payload was refused, the Bash heredoc payload allowed (GHI [wiki-write skill, and the detect-set-aside-ask hook that enforces it — checking the file, not the tool call](https://github.com/nedschorus/nedschorus/issues/343)).

On 2026-10-03 the user designed the last layer of defence: "If we track SHAs - then we can easily add a backup directory to it when SHAs are updated." On 2026-10-12 he simplified it, in the approval-walk `unapproved-guarded-file-changes-set-aside-and-restore-the-approved-version-2026-10-11-2`: the hook does not put anything back by itself; it asks. "Why do we need more than one gate - if we check every post tool that's enough checking." The agents' failures are accidents between cooperative agents, so a reminder that does not stop until the change is settled is enough.

## This GHI takes over three plans

- **Item 2 of the list "Guards" in GHI 31** ("In-session tamper revert"). The rest of GHI 31 stays as it is, dormant.
- **Part 2 of GHI 343**, the hook that sets an unapproved change aside and asks. Part 1 of GHI 343, the `wiki-write` skill, stays there.
- **The third follow-up of the GHI-MD of GHI [Every refusal and warning a program hands an agent says why and what to do instead](https://github.com/nedschorus/nedschorus/issues/956)**: "a check that reports, and reverts, a guarded file changed without the user's approval by any means, a shell command included: approved writes record the file's hash and keep a copy, and a quotation of the user in a marker is checked against the transcript". This GHI drops "reverts": the user is asked instead.

The user approved merging them on 2026-10-11, as item 2 of the approval-walk `codex-simplification-trawl-survivors-2026-10-10`, and decided the design in that item's follow-up questions and in the approval-walk named above (walk-minutes in `docs/walk/` of the cold-read-improvement checkout on ned-box until each approval-walk closes, then in the log-store under `walk/`).

## The design

### When it runs, and how fast

It is a hook for every tool, registered under PostToolUse and PostToolUseFailure, since PostToolUse runs only after a tool call that succeeds. It does not run at Stop (user-ruled 2026-10-11). When nothing has changed it takes under 100 ms per tool call on ned-box (user-ruled 2026-10-11): it compares the stat data it stored at its previous run (change time, modification time, size, inode) and hashes only a file whose stat data differs, as git hashes it (`git hash-object --path`). A throwaway prototype took about 40 ms per run on ned-box on 2026-10-11.


### Which files it checks

- **In the checkout of the tool call's working directory:** every guarded file in it, tracked, untracked or ignored, decided with the guard's own functions, `is_protected`, `is_reusable_prompt` and `is_reviewed_document`, imported from `.claude/hooks/instruction-file-guard.py`, so the two hooks cannot disagree. Ignored files are listed with `git ls-files --others --ignored --exclude-standard` restricted to the paths the guard can protect (`CLAUDE.local.md` at any depth, and under `.claude/`, `.claude/settings.local.json` included), so the large ignored trees, such as `__pycache__/`, are never read.
- **Outside every checkout:** `~/.claude/CLAUDE.md` and `~/.claude/settings.json`.

A write a session makes into another checkout is noticed by the next session that runs in that checkout, not by the writer.

Memory files are not checked: the guard refuses every Edit and Write into a memory directory, and on ned-box 731 memory directories held 3 files on 2026-10-12.

### The approved set

For each checked path, the hook keeps in the backup directory the set of content hashes approved for that path. A file is **settled** when its current content's hash is in its path's approved set; otherwise it is waiting for the user. Nothing else records that a question is open: the reminder is derived from the content, so it survives a handoff, a crash and the removal of a worktree. A hash enters the set in four ways:

1. **Git's own work.** When a run sees HEAD moved by a branch switch, a reset, a merge, a pull, a rebase, a cherry-pick or a revert since its previous run in this checkout, the versions HEAD then holds are added. A `git commit`, `--amend` and a squash merge included, adds nothing: it commits the agent's own content. The hook finds what happened from the reflog entries newer than the newest entry it saw at its previous run, identified by that entry's commit and time, not by the reflog's length, which expiry can keep constant. A commit that finishes a merge, cherry-pick or revert that a previous run saw stopped on a conflict counts as git's own work, so a hand-merge is not asked about. Because the set is kept, a version added once stays approved: a `git stash apply` that brings back an approved version is settled.
2. **A successful Edit, Write or NotebookEdit,** while the instruction-file guard refuses every such call that has no approval marker (user-ruled 2026-10-12): the version the call wrote is added by the hook run after it.
3. **The user's yes,** recorded by the hook's approve command (below), which adds the one hash the user was shown.
4. **Stocking:** the first run on a machine adds the current version of each file outside every checkout and of each `CLAUDE.local.md` (user-ruled 2026-10-12); the first run in a checkout adds the current version of each checked file there.

While a rebase, merge, cherry-pick or revert is in progress, the hook still copies every new version, so no intermediate resolution is lost, but asks nothing, using the check the function `git_operation_in_progress` in `.claude/hooks/session-location-write-guard.py` already makes. A rename that leaves the content unchanged is settled (user-ruled 2026-10-12): when one run sees a path disappear and a new path appear with the same content, it adds that hash to the new path's approved set. A deleted file's content is recorded as the reserved hash `deleted`, which the approve and restore commands accept like any other. A deletion git's own work made is settled; any other deletion of a guarded file is a change to ask about. When a conflicted operation is aborted, the files return to versions already approved, so they are settled, and the copies made during the conflict stay in the backup directory.

### What it does when a file changes

At every run, for each checked file whose content differs from its content at the previous run:

1. It copies the new version into the backup directory, whether or not the version is approved, so that every version a run sees is kept, approved uncommitted Edits included.
2. If the new version's hash is not in the path's approved set, it tells the agent, through `additionalContext`, in one message for all the files one tool call changed, which file changed and that the user has not approved it, and, each on its own line with its condition:
   - show the user the change (the hook gives the diff against the newest approved version, at most 40 lines and 4,000 characters, and the version's short hash) and ask him;
   - if he approves, write his words into the marker file `.walk-approved` at the top of the session's checkout, as the instruction-file guard's marker is written, and run `python3 .claude/hooks/guarded-file-change-without-approval-backup-and-ask-hook.py --approve <path> <hash>` for each file he approved, which spends the marker and adds that hash to the approved set; it refuses when the file's content is no longer that hash, so a version he was not shown is never approved, and refuses when it cannot write to the backup directory;
   - if he declines, run the same program with `--restore <path> <hash>`, which first copies the file's current content into the backup directory, refuses unless that content is still the hash he declined, and then puts back the newest approved version from the backup directory; and, if the declined version is in a commit, the agent adds a commit on top that holds the approved version, with the command the message gives;
   - a subagent reports the change to the agent that dispatched it instead of asking the user.
3. The session whose run first saw the version is named in the backup directory's log as the one to ask. After every later tool call in that session, while the file is not settled, the hook repeats a one-line reminder naming the file. Any other session that checks the file gets the reminder once. A successor after a handoff is a new session in the same checkout; when the log's asking session has ended, the first session to see the unsettled file is logged as the new asking session, asks, and is reminded after every tool call from then on.

The user's own edit in an editor is handled the same way (user-ruled 2026-10-11): the hook cannot tell his editor from an agent's `sed`; since nothing is put back without his no, his edit is not lost.

`~/.claude/settings.json` is written by Claude Code itself when the user picks a model with `/model` or changes a setting with `/config`, outside any tool call. Proposed, for the user to decide: the hook compares only its keys that change what hooks and tools may do, `hooks`, `disableAllHooks`, `permissions` and `env`, so a model choice is not asked about; the whole file is still copied.

### The backup directory

One directory on ned-box, `/home/nedlern/guarded-file-backups/` (user-ruled 2026-10-12: "we use ned-box as the backup drive"). It mirrors each file's full path, since every `CLAUDE.local.md` has the same name; a path the Mac reaches through its mount `/Volumes/nedhome/` is keyed by its ned-box path, `/home/nedlern/...`, so both machines name one file the same way, and a Mac path not on the mount goes under `mac/`. Under each path's directory:

- one copy of each version, named by its content hash, written to a temporary file with a unique name and moved into place only if no copy of that name exists; copies are never changed or deleted by the hook, and how long they are kept is decided in the build (user-ruled 2026-10-11);
- `approved`, the path's approved set, one hash per line, appended to and never rewritten;
- `log`, one appended line per version seen: the time, the machine, the session, the hash, and how it entered the approved set, if it did;
Nothing in the directory is ever rewritten, only added to, so no run needs a lock: a copy is created only when no copy of its name exists, and a line is appended to `approved` or `log` in one write with `O_APPEND`. Whether one appended line stays whole when the Mac appends through its SMB mount while ned-box appends locally is tested in the build.

The directory is outside every checkout and outside `~/.claude/`, where the guard would protect its files. A checkout's own stored stat data and reflog position are kept in that checkout's git directory (`git rev-parse --git-dir`), and the stat data of the files outside every checkout in `~/.cache/guarded-file-change-without-approval-backup-and-ask-hook/` on each machine.

### When something fails

If the hook cannot write a copy, read the backup directory or run git, it exits 0 and tells the agent through `additionalContext` what failed and that the change is not backed up; `--restore` refuses while the current version cannot be copied. When the Mac cannot reach ned-box, the message says so, with the remedy, and the agent tells the user, as `CLAUDE.md` asks for an unreachable ned-box.

### How this sits beside the existing backups

The fleet already keeps histories that `scripts/find-deleted-path-across-backups.py` searches: git, including the work-snapshot refs, Timeshift snapshots of ned-box (hourly, daily, weekly and monthly, per `/etc/timeshift/timeshift.json`), and Time Machine on the Mac. A work-snapshot (`nc-systems/handoff/uncommitted-work-snapshots.py`, written after every Edit, Write, NotebookEdit and Bash call by `scripts/uncommitted-work-snapshot-hook.py`) is a git commit under `refs/work-snapshots/<owner>/<worktree>` holding the latest uncommitted changes of one worktree for one `claude` process, so that they outlive a crash.

None of them can be the backup directory:

- Timeshift and Time Machine copy on a timer, so a version that lived for ten minutes may be in neither; they record no approval; and agents may not write backup state (`.claude/hooks/backup-and-snapshot-write-guard.py`).
- A work-snapshot keeps only the latest uncommitted state per process and worktree, leaves out files git ignores, `CLAUDE.local.md` among them, and covers no file outside a checkout.

The backup directory is the same idea at a finer grain: a copy at each change of a guarded file, with the approved versions named. Timeshift backs the directory itself up on ned-box. `scripts/find-deleted-path-across-backups.py` should search it as one more history; that is part of the build.

### Does this replace the existing file protection?

Three PreToolUse hooks guard Edit, Write and NotebookEdit calls today:

- `.claude/hooks/session-location-write-guard.py` refuses writes from a session whose checkout is on a detached HEAD and writes into the machine's shared reference checkout, each unless its own one-use marker `.location-write-approved` exists. It protects where work happens, not the user's approval, and stays.
- `.claude/hooks/backup-and-snapshot-write-guard.py` refuses writes to Timeshift and Time Machine state. It stays.
- `.claude/hooks/instruction-file-guard.py` refuses an Edit or Write of a guarded file unless a marker file holding some text exists; today it accepts any text in the marker, and checking that the text quotes the user is the work described below. This is the gate the user's one-gate principle bears on.

Built first, the new hook works beside the instruction-file guard, and the approved set's way 2 relies on the guard. Afterwards the guard's approval gate could go: an Edit would land, the hook would ask, and `--approve` would record the user's yes, one gate for Edit and the shell alike; way 2 would go with it. What would be lost:

- **Blocking before the write lands.** `.claude/settings.json` configures hooks, this hook included; a change that switches the hook off takes effect before anyone answers. The guard stops such an Edit before it lands; the new hook cannot.
- **The memory-directory refusal,** which no marker overrides. It has nothing to do with approval and would stay as a small hook of its own.
- **The teaching moment.** The guard's refusal tells the agent how to get approval before it writes; the new hook's message tells it after.

Whether to remove the guard's approval gate once the new hook works is the user's decision, and is not part of this build.

### Checking a quotation of the user

The guard is to check a quotation of the user in a marker file against the transcripts, and refuse a marker whose quoted words the user never typed (user-ruled 2026-10-03). The check applies to the text in double quotation marks. A marker that begins "Obvious fix under CLAUDE.md's standing approval:" is not checked, as `CLAUDE.md` allows. It reads the user's words with the functions `typed_by_user` and `queued_by_user` of `scripts/search-user-messages-in-transcripts.py`, in the session's own transcript and, for a subagent, its parent's; for a marker naming another session, in that session's transcript in the log-store's `transcripts/` copy, letting the write through with a warning when that copy ends before the quotation. The same check applies to the hook's `--approve`. The check shows that the user typed the words, not that he meant them for this change.

## Tests the build must include

Run in a throwaway repository unless stated:

- a shell command that edits `CLAUDE.md` is caught: the new version is copied, the agent is told, and the file is left as it is;
- the reminder repeats in the asking session after the next tool call, appears once in another session, and stops once `--approve` or `--restore` has run;
- `--approve` refuses when the file no longer holds the hash given, and refuses without a marker; `--restore` refuses when the file changed after the user was shown it, and keeps the current version before it restores;
- an approved Edit, still uncommitted, then a shell edit, then a decline: the approved Edit's version is put back;
- a shell command that edits `CLAUDE.md` and commits it, then rebases onto main, in the same command is caught, and is still unsettled at the next run;
- the files a rebase, a merge, a pull, a cherry-pick, a revert and a branch switch change are not asked about, nor a merge, revert or cherry-pick finished after a conflict a run saw; every resolution version seen during the conflict is copied;
- `git stash` and `git stash apply` of an approved edit are not asked about;
- an edit of `CLAUDE.local.md` in two checkouts is kept under two different paths; the same file seen from the Mac through `/Volumes/nedhome` and on ned-box is kept under one path;
- two runs copying the same version at the same moment leave one copy and two log lines;
- a `/model` change to `~/.claude/settings.json` is copied and not asked about; a change to its `hooks` key is asked about;
- the first run on a machine stocks `~/.claude/CLAUDE.md`, `~/.claude/settings.json` and each `CLAUDE.local.md`;
- when the backup directory cannot be written, the agent is told and nothing else changes;
- with nothing changed, a run on a copy of main takes under 100 ms on ned-box; on the Mac the test prints a SKIP line.

The quotation check's tests: a marker quoting words the user typed passes; one quoting words he never typed is refused; a queued "y" passes; an obvious-fix marker passes; a quotation from a session whose log-store copy is behind passes with the warning.

## Known gaps

- **A background write after the last tool call** is not noticed until the next tool call that checks the file.
- **Versions overwritten within one tool call:** only the last version is copied.
- **An unapproved change in effect while the user is asked:** an agent follows a changed skill or `CLAUDE.local.md` until the user answers; a change to `.claude/settings.json` made by a shell command can switch hooks off, this one included.
- **An unrelated change staged during a conflicted merge** is committed with the resolution and approved as git's own work.
- **A conflict resolved inside one shell command** leaves no stopped state for a run to see, so its merge commit is asked about.
- **An unapproved commit rebased over a main that changed the same file** can come out as a version that git's own work then approves.
- **A new worktree created from a branch holding an unapproved commit** stocks that commit's versions as approved.
- **A write into another checkout** is noticed only when a session runs there.
- **A Codex session** runs no Claude Code hooks; its write is noticed at the next tool call of a Claude Code session that checks the file.
- **A push before the user answers** sends the unapproved version to other machines and merge-lane-2 as git's own work.
- **User-level files under `~/.claude/`** other than the two listed are not checked.
- **The hook's own file:** a shell command that deletes or breaks the hook stops it.

## Open questions

- Whether to remove the instruction-file guard's approval gate once this hook works ("Does this replace the existing file protection?" above).
- Whether `~/.claude/settings.json` is compared only in `hooks`, `disableAllHooks`, `permissions` and `env`, as proposed above, so that `/model` and `/config` choices are not asked about.
- Whether to check quotations of the user in commit messages as well as in marker files (the agent-seat MD-skills' task #152, closed when this GHI took it over).
- The term the user approved on 2026-10-12, guarded-file-unapproved-change-set-aside-for-user-decision, names a saved-aside change that this design no longer has. A file waiting for the user is simply a file that is not settled; if the build needs a term, a name goes to the user.

## Next action

Build the hook on one topic branch, with the tests above, as `.claude/hooks/guarded-file-change-without-approval-backup-and-ask-hook.py` (name to be checked against the naming page in the build), and add the backup directory to `scripts/find-deleted-path-across-backups.py`. Confirm with a failing Bash command that writes `CLAUDE.md` that the PostToolUseFailure registration catches it. Build the quotation check on its own topic branch: it changes the instruction-file guard and works without the hook.

## Search receipt

`scripts/ghi-info-ask.py "Is there an issue, open or closed, about a check that catches an instruction file or other guarded file (CLAUDE.md, a skill, a prompt file, a wiki page, a memory file) changed without the user's approval by a shell command or any route the instruction-file guard does not see, by comparing file hashes after a tool call or at Stop, and reverting or setting the change aside?"` on 2026-10-11 named GHI 343 (open) as the nearest; GHI [Sanity-check write detector never inspects the worktree after claude agents, and one wrote a file during a live run](https://github.com/nedschorus/nedschorus/issues/161) and GHI [cold-read grid: FELL BACK and STRAY WRITE markers fire on text that is not the cell's — two false positives measured 2026-09-02](https://github.com/nedschorus/nedschorus/issues/244), both closed, about write detectors in the sanity-check and cold-read runners; and GHI [Move mechanical agent chores into programs and hooks](https://github.com/nedschorus/nedschorus/issues/1036), open. None covers this check apart from GHI 343, whose part 2 this GHI takes over.
