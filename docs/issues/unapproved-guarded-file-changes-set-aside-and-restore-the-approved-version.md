# Unapproved guarded file changes: set aside and restore the approved version

## What is wanted

A PostToolUse hook, run after every tool call, that catches a guarded file changed without the user's approval by a route the instruction-file guard does not see, a shell command above all. It saves the changed version, puts the approved version back, and tells the agent, which shows the user the change; if the user approves it, the agent writes it back through the instruction-file guard. For `~/.claude/settings.json` and the files in Claude Code memory directories, which Claude Code itself writes, the hook saves and reports the change and puts nothing back. The routes it does not catch are listed under "Known gaps". Nothing is built yet; the next action is the build.

A **guarded file** here is a file that `.claude/hooks/instruction-file-guard.py` protects: `CLAUDE.md` and `CLAUDE.local.md`, everything under a `.claude/` directory apart from `worktrees/`, `jobs/` and `handoffs/`, a `-prompt.md` or `-instructions.md` file, and a reviewed document (a `.md` file under `docs/agents/`, `docs/nedschorus-wiki/` or `nc-systems/skills/`, or a `-design.md` file), with the exceptions that guard makes. The hook checks only some of them; "Which files the hook checks" says which.

An **approved version** of a file is a version the hook accepts, by the rules under "Which version is approved": the user's approval vouches for some, git's own work for others.

## Why

The instruction-file guard is a PreToolUse hook on Edit, Write and NotebookEdit. A write to a guarded file meets a user-block: it goes through only once the agent has written the user's approval words into a one-use marker file, `.walk-approved`. A write into a Claude Code memory directory meets a hard-block. The guard does not see a shell command, and the files a shell command will write cannot, in general, be known before it runs: redirection, `sed -i`, `tee`, a Python heredoc, or a program three layers down. Two records:

- On 2026-08-24, about 60 lines of credential reference material built up in an agent-seat's `CLAUDE.local.md`, written by shell commands, before the user noticed (GHI [Review-system design requirements learned from the legacy gate — dormant until a class of work first requires review](https://github.com/nedschorus/nedschorus/issues/31), item 2 of its list "Guards").
- On 2026-09-13 the guard was fed two payloads naming the same `CLAUDE.md`: the Edit payload was refused with exit 2, the Bash heredoc payload allowed with exit 0 (GHI [wiki-write skill, and the detect-set-aside-ask hook that enforces it — checking the file, not the tool call](https://github.com/nedschorus/nedschorus/issues/343)).

On 2026-10-03, in session 17346de4 of the agent-seat MD-skills on the Mac, the user set out the layers: the guard's refusal tells agents not to go around it; a simpler shell parser catches more as it happens (the replacement of the Bash guards' shell parser that the agent-seat cold-read-research plans, named in the GHI-MD of GHI [Every refusal and warning a program hands an agent says why and what to do instead](https://github.com/nedschorus/nedschorus/issues/956)); and "for the last round of defense we could rat out changes". At 22:19:38 UTC he designed this hook: "If we track SHAs - then we can easily add a backup directory to it when SHAs are updated. Then if they are updated by cheating we can just revert and tell the agent in a post tool hook." This hook is that last layer. It adds to the instruction-file guard and does not replace it: the guard refuses before the write and tells the agent how to get approval.

## This GHI takes over three plans

- **Item 2 of the list "Guards" in GHI 31** ("In-session tamper revert"). The rest of GHI 31 stays as it is, dormant.
- **Part 2 of GHI 343**, the Stop hook that sets an unapproved change aside. Part 1 of GHI 343, the `wiki-write` skill, stays there. GHI 343's open question, whether the check replaces "the PreToolUse guard", the instruction-file guard, is answered: it adds to it.
- **The third follow-up of the GHI-MD of GHI 956**: "a check that reports, and reverts, a guarded file changed without the user's approval by any means, a shell command included: approved writes record the file's hash and keep a copy, and a quotation of the user in a marker is checked against the transcript". That follow-up is the record of the user's 2026-10-03 design.

The user approved merging them into this GHI on 2026-10-11, as item 2 of the approval-walk `codex-simplification-trawl-survivors-2026-10-10`, and decided the design questions below in that item's follow-up questions on 2026-10-11 and 2026-10-12 (UTC). The walk-minutes are at `nedlern@ned-box:/home/nedlern/agents/cold-read-improvement/docs/walk/codex-simplification-trawl-survivors-2026-10-10-minutes.md` until the approval-walk closes, and then in the log-store under `walk/`.

## The design

### When it runs, and how fast

It is a hook for every tool, registered under PostToolUse and PostToolUseFailure, and does not run at Stop (user-ruled 2026-10-11): PostToolUse runs only after a tool call that succeeds, and Claude Code's hooks reference says to register the same hook under PostToolUseFailure for calls that fail. A command started in the background that writes after its tool call returns is caught at the next tool call that checks that file, and not before.

When nothing has changed, it takes under 100 ms per tool call on ned-box (user-ruled 2026-10-11). For each file it checks it compares the stat data it stored at its previous run (the change time, the modification time, the size and the inode) and hashes only a file whose stat data differs, as git hashes it (`git hash-object --path`), so a line-ending conversion is not a change. The change time is compared because an agent's `touch -d` can set the modification time back but not the change time. The list of guarded files inside the checkout is cached, and recomputed only when the output of `git ls-files --cached --others --exclude-standard` changes: that one git call, about 6 ms, is cheaper than applying the guard's rules to every file, about 60 ms. A throwaway prototype measured on 2026-10-11 took about 40 ms per run on ned-box, most of it Python's start-up and that one git call.

### Which files the hook checks

The hook checks two sets:

- **In the checkout of the tool call's working directory** (the payload's `cwd`): the guarded files git tracks, and those git does not ignore, plus `CLAUDE.local.md`, which git ignores. Other files git ignores, such as the compiled Python files under `.claude/hooks/__pycache__/`, are not checked. The hook decides which files are guarded with the guard's own functions, `is_protected`, `is_reusable_prompt` and `is_reviewed_document`, imported from `.claude/hooks/instruction-file-guard.py`, so the two hooks cannot disagree. A subagent working in another worktree has that worktree checked.
- **Outside every checkout:** `~/.claude/CLAUDE.md`, `~/.claude/settings.json`, and the files in every Claude Code memory directory (`~/.claude/projects/*/memory/`), listed at each run, since new memory directories appear.

It does not check another checkout; otherwise one session could undo another's approved edit in the moment before that session's own check records it.

### Which version is approved

A checked file's content is approved when it equals one of these (user-ruled 2026-10-11):

1. **The version in the current commit (HEAD), unless a `git commit` run since the hook's previous run in this checkout put it there.** The hook stores the length of HEAD's reflog at each run, and reads the entries added since. A branch switch, a reset, a merge, a pull, a rebase, a cherry-pick or a revert is git's own work: it builds HEAD from commits that already exist. A `git commit`, including `--amend`, commits the agent's own content and is not: a version that a `git commit` entry since the previous run put into a commit is unapproved, whatever reflog entries follow it, so an edit committed and then rebased or merged in the same command is caught too. One exception: the commit that finishes a merge, cherry-pick or revert that stopped on a conflict counts as git's own work, so the hand-merge `CLAUDE.md` prescribes is not undone. The reflog does not always mark that commit: a revert finished with `git revert --continue` logs a plain `commit:` entry. A shell command that edits `CLAUDE.md` and commits it in the same command is caught.
2. **A version written by an Edit, Write or NotebookEdit call that spent an approval marker file.** The guard deletes the marker before the write, so when it spends a marker it also writes a note naming the file, the session and the tool call's id (`tool_use_id`, which both hook events receive). For a file in a checkout, the note goes in that checkout's git directory; for a file outside every checkout, in the save directory. The hook run after that tool call approves the version the write produced and deletes the note. A note from another tool call approves nothing, with one exception: when the hook's run after the approved write failed, the next run accepts that note and says so.
3. **For a checked file git does not track** (`CLAUDE.local.md`, `~/.claude/CLAUDE.md`, `~/.claude/settings.json`, a memory file, an uncommitted new guarded file): the copy saved the first time the hook checks that path, or at the file's last approved write. After the first time the hook checks a checkout, a new guarded file that appears in it has no approved version unless rule 2 gives it one.

What the hook puts back is the version the file held at the hook's previous run, which these rules approved then.

Also:

- **A rename that leaves the content unchanged is approved** (user-ruled 2026-10-12): a guarded file at a new path whose content equals the approved version of the file that left the old path. The old path is not restored.
- **A deletion is approved when git's own work removed the file:** the path is gone from HEAD, and the reflog entries since the previous run show git's own work. Any other deletion is undone, a `git rm` followed by a `git commit` included, except for `~/.claude/settings.json` and memory files, which are reported.
- **A version the hook has set aside is never approved by rule 1 later.** Otherwise a later `git reset --hard` or `git stash` would bring the commit holding it back as git's own work. When the user approves it, the agent's write through the guard approves it by rule 2.
- **While a rebase, merge, cherry-pick or revert is in progress, the hook puts nothing back and leaves its stored stat data as it is,** so that a conflict an agent is resolving is not wiped out. It uses the check the function `git_operation_in_progress` in `.claude/hooks/session-location-write-guard.py` already makes, which the user approved as question 7 under "Questions the approval-walks settled" in the GHI-MD of GHI 956. The first run after the operation ends sees every file it changed, because their stat data differ.

### What it does with an unapproved change

- **Every checked file apart from the next two kinds:** it saves the changed version, puts the approved version back, and tells the agent.
- **`~/.claude/settings.json` and memory files** (user-ruled 2026-10-12): it saves the changed version, a new or deleted file included, and tells the agent, and puts nothing back. Claude Code writes `~/.claude/settings.json` when the user changes a setting with `/config` or `/model` or installs a plugin, and the hook cannot tell that from an agent's `sed`; putting it back would undo the user's own choices. The agent tells the user. If he keeps the change, the agent runs the hook's close command with `--keep`, which records the changed version as approved. If he does not, the agent copies the saved approved version back with the shell command the message gives, since the guard refuses Edit and Write in a memory directory, and runs the close command.
- **A new guarded file with no approved version,** such as a wiki page written by a shell command: it moves the file into the save directory, and nothing takes its place.
- **The user's own edit, in an editor:** the hook cannot tell the user's editor from an agent's `sed`, so it handles the edit as any other (user-ruled 2026-10-11). The agent shows the user the saved version; on his yes, the agent writes his words into the marker file and writes his version back with Edit.

The hook tells the agent through `additionalContext`, one message for all the files one tool call changed. The message says what was changed and put back, and why; then, each on its own line with its condition, what the agent does next:

- show the user the saved version and ask; a subagent reports to the agent that dispatched it instead;
- if the user approves it, write his words into the marker file and write the version back with Edit or Write;
- if he declines it, close the entry with the hook's close command (the hook run with `--close <entry>`);
- if the change is in a commit that is not pushed, amend that commit so it holds the approved version;
- if the change is in a pushed commit, add a commit on top that holds the approved version, and tell the user the unapproved version is in the pushed history.

### The save directory

One directory per machine, `~/guarded-file-approved-versions-and-set-aside-changes/`, the backup directory of the user's design (user-ruled 2026-10-11), outside every checkout and outside `~/.claude/`; under `~/.claude/` the guard would protect the directory's own files. It holds:

- approved versions git does not hold: those of checked files git does not track, and those approved by rule 2 and not yet committed, each kept under its hash, with an index from path to hash;
- an entry for each changed version the hook set aside: the copy, the session, the time, the file's path, and whether the entry is open or closed;
- the notes for files outside every checkout, and the stored stat data for those files.

Rules that keep sessions from damaging each other's records:

- The hook never changes or deletes a saved copy. Each copy is written whole to a temporary file with a unique name and moved into place with `os.replace`. How long copies are kept is decided in the build (user-ruled 2026-10-11).
- Every read-and-update of stored stat data, of the index or of an entry's state takes an exclusive lock on that file (`flock`), so two sessions' runs do not lose each other's updates. A checkout's stored stat data is kept in that checkout's git directory (`git rev-parse --git-dir`), so it goes when the checkout is removed.
- An entry is named by the hash of the file's path, the hash of the changed version and the time. While an entry for that path and version is open, a second finding of the same change is put back without a second report. After the entry is closed, the same change is reported again.
- An entry is closed when the user's version is written back, which the hook records, or when the agent runs the close command. An open entry is reported again once to each new session that checks it: a session in that checkout, or, for a file outside every checkout, any session on the machine.

### When something fails

The hook never puts a file back before its saved copy is written. It puts a file back by writing the approved version to a temporary file beside it and moving that into place with `os.replace`, keeping the file's permission bits, so a failed restore leaves the changed version where it was. Just before the move it hashes the file again; if the file changed after its copy was saved, it puts nothing back in this run and handles the newer version at the next one, so a write that lands between the save and the restore is not overwritten unsaved. If anything fails, it puts nothing more back, exits 0, and tells the agent through `additionalContext` what failed and which files are left changed, as `scripts/uncommitted-work-snapshot-hook.py` reports its failures.

### Checking a quotation of the user

The guard also checks a quotation of the user in a marker file against the transcripts, and refuses a marker whose quoted words the user never typed (user-ruled 2026-10-03). The check applies to the text in double quotation marks; the agent's own framing around it is not checked. A marker that begins "Obvious fix under CLAUDE.md's standing approval:" is not checked, as `CLAUDE.md` allows. The check searches the session's own transcript and, for a subagent, its parent's; when the marker names another session, as the guard's refusal text asks for an approval quoted from elsewhere, it searches that session's transcript in the log-store's `transcripts/` copy. It reads the user's words with the functions `typed_by_user` and `queued_by_user` of `scripts/search-user-messages-in-transcripts.py`, which already count a message the user typed while the agent was working; on 2026-09-21 two agents missed such a queued "y" and retracted a real approval for 49 minutes (`nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/MD-skills/approval-problems-transcript-trawl-2026-10-03/answer.md`). When the log-store copy of the named session's transcript ends before the quotation's time, the guard lets the write through and says the quotation could not be checked. The check shows that the user typed the words, not that they approve this change; that the words fit the change stays the agent's responsibility.

## Tests the build must include

Run in a throwaway repository unless stated:

- a shell command that edits `CLAUDE.md` and commits it in the same command is caught, set aside and put back;
- a shell command that edits `CLAUDE.md`, commits it and then rebases onto main, or merges with `--no-ff`, in the same command is caught;
- the files a rebase, a merge that is not a fast-forward, a pull, a cherry-pick and a revert change are not put back, nor those of a merge finished with `git commit` after a conflict, a revert finished with `git revert --continue` or `git commit` after a conflict, or a cherry-pick finished after a conflict;
- an approved Edit is not put back, including by another session's tool call made at the same moment, for a file in a checkout and for `~/.claude/CLAUDE.md`;
- a note left by an Edit that another hook then refused approves nothing;
- the user's own edit is caught, saved, and written back by Edit after his approval, and the written-back version is not set aside again;
- a memory file is reported once and never put back; `--keep` and the shell copy-back both close its entry;
- a rename with unchanged content is approved; a rename with changed content is caught;
- a deletion made by switching branches is approved; a deletion by `rm` is undone;
- with a rebase stopped on a conflict, nothing is put back;
- the same unapproved change made again after its entry was closed is reported again;
- when the save directory cannot be written, nothing is put back and the agent is told;
- with nothing changed, a run on a copy of main takes under 100 ms on ned-box; on the Mac the test prints a SKIP line.

The quotation check's tests: a marker quoting words the user typed passes; a marker quoting words he never typed is refused; a queued "y" passes; an obvious-fix marker passes; a quotation from a session whose log-store copy is behind passes with the warning.

## Known gaps

- **A background write after the last tool call** is not caught until a tool call that checks the file runs. Claude Code's FileChanged event fires for such a write, but its hook cannot tell the agent anything.
- **Versions overwritten within one tool call:** a command that writes a guarded file twice leaves only the last version for the hook to save.
- **An unapproved commit rebased over a main that changed the same file** can come out as a version no `git commit` entry made, which rule 1 approves.
- **A Codex session** runs no Claude Code hooks; its write to a guarded file is caught at the next tool call of a Claude Code session that checks the file.
- **A checkout whose branch predates the hook** runs without it until the branch takes in main.
- **A pushed unapproved version.** Once an unapproved version has been pushed, the other machine and the agent-seat merge-lane-2 receive it as git's own work and approve it. The commit on top that the hook's message asks for corrects the file; the unapproved version stays in the pushed history.
- **A change committed in a checkout no session checks,** such as a scratch worktree, arrives in a checked checkout as git's own work and is approved.
- **A shell edit made while a rebase, merge, cherry-pick or revert is stopped** is approved when the operation finishes.
- **A shell command that returns a file to a version rule 2 approved earlier** is approved, because rule 2's approvals stay in the index; this is also what lets `git stash` and `git stash pop` of an approved, uncommitted edit through, when the pop restores it unchanged.
- **A `git stash pop` that merges an approved edit with a newer commit** makes a version no rule approves, and the hook sets it aside.
- **A write that lands in the moment between the hook's last hash and its restore** is overwritten without a saved copy.
- **A change made by the first tool call in a checkout the hook has never checked** becomes that checkout's first approved copy for files git does not track.
- **A hook switched off in `~/.claude/settings.json`** stays off until the user answers, because that file is reported, not put back; and if no session with the hook runs after the change, nobody reports it. The project's own `.claude/settings.json` is tracked and is put back.
- **`.claude/settings.local.json`** is ignored by git in the ned-box clone (`.git/info/exclude`), so the hook does not check it, although it can switch hooks off.
- **User-level files under `~/.claude/`** other than the three listed, such as `~/.claude/skills/`, are not checked.
- **The hook's own file:** a shell command that deletes or breaks the hook stops it from running at all.

## Open question

The agent-seat MD-skills recorded, on 2026-10-03, a wish to check quotations of the user in commit messages against the transcripts as well as those in marker files, as its task #152, closed when this GHI took it over. The user has not decided it; it goes to him when the build starts.

## Next action

Build the hook and the guard's note on one topic branch, with the tests above; the hook goes in `.claude/hooks/` as `guarded-file-unapproved-change-set-aside-and-restore-hook.py`. Confirm with a failing Bash command that writes `CLAUDE.md` that the PostToolUseFailure registration catches it. Build the quotation check on its own topic branch: it changes the instruction-file guard and works without the hook.

## Search receipt

`scripts/ghi-info-ask.py "Is there an issue, open or closed, about a check that catches an instruction file or other guarded file (CLAUDE.md, a skill, a prompt file, a wiki page, a memory file) changed without the user's approval by a shell command or any route the instruction-file guard does not see, by comparing file hashes after a tool call or at Stop, and reverting or setting the change aside?"` on 2026-10-11 named GHI 343 (open) as the nearest; GHI [Sanity-check write detector never inspects the worktree after claude agents, and one wrote a file during a live run](https://github.com/nedschorus/nedschorus/issues/161) and GHI [cold-read grid: FELL BACK and STRAY WRITE markers fire on text that is not the cell's — two false positives measured 2026-09-02](https://github.com/nedschorus/nedschorus/issues/244), both closed, about write detectors in the sanity-check and cold-read runners; and GHI [Move mechanical agent chores into programs and hooks](https://github.com/nedschorus/nedschorus/issues/1036), open. None covers this check apart from GHI 343, whose part 2 this GHI takes over.
