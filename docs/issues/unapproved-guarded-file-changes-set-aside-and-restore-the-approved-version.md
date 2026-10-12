# Unapproved guarded file changes: set aside and restore the approved version, by any route

## What is wanted

A hook that runs after every tool call and catches a guarded file changed without the user's approval, by any route, a shell command included. It saves the changed version, puts the approved version back, and tells the agent, which shows the user the change; if the user approves it, the agent writes it back through the instruction-file guard. For the few guarded files that Claude Code or the user write themselves, the hook saves and reports the change and restores nothing. Nothing is built yet; the next action is the build.

A **guarded file** here is a file that `.claude/hooks/instruction-file-guard.py` protects: `CLAUDE.md` and `CLAUDE.local.md`, everything under a `.claude/` directory apart from `worktrees/`, `jobs/` and `handoffs/`, a `-prompt.md` or `-instructions.md` file, and a reviewed document (a `.md` file under `docs/agents/`, `docs/nedschorus-wiki/` or `nc-systems/skills/`, or a `-design.md` file), with the exceptions that guard makes; plus the files in a Claude Code memory directory, which the guard refuses to write at all. `~/.claude/CLAUDE.md` and `~/.claude/settings.json` are guarded files by the same rules.

## Why

The instruction-file guard is a PreToolUse hook on Edit, Write and NotebookEdit. It refuses a write to a guarded file unless the agent has written the user's approval words into a one-use marker file, `.walk-approved`. It does not see a shell command, and a shell command cannot be predicted before it runs: redirection, `sed -i`, `tee`, a Python heredoc, or a program three layers down. Two records:

- On 2026-08-24, about 60 lines of credential reference material built up in an agent-seat's `CLAUDE.local.md`, written by shell commands, before the user noticed (GHI [Review-system design requirements learned from the legacy gate — dormant until a class of work first requires review](https://github.com/nedschorus/nedschorus/issues/31), guard 2).
- On 2026-09-13 the guard was fed two payloads naming the same `CLAUDE.md`: the Edit payload was refused with exit 2, the Bash heredoc payload allowed with exit 0 (GHI [wiki-write skill, and the detect-set-aside-ask hook that enforces it — checking the file, not the tool call](https://github.com/nedschorus/nedschorus/issues/343)).

On 2026-10-03 the user set out the layers, in the MD-skills agent-seat's agent-session 17346de4 on the Mac: the guard's refusal tells agents not to go around it; a simpler shell parser, which other agent-seats are building, catches more as it happens; and "for the last round of defense we could rat out changes". At 22:19:38 UTC he designed this hook: "If we track SHAs - then we can easily add a backup directory to it when SHAs are updated. Then if they are updated by cheating we can just revert and tell the agent in a post tool hook." This hook is that last layer. It adds to the PreToolUse guard and does not replace it: the guard refuses before the write and tells the agent how to get approval.

## This GHI takes over three plans

- **Guard 2 of GHI 31** ("In-session tamper revert"). The rest of GHI 31 stays as it is, dormant.
- **Part 2 of GHI 343**, the Stop hook that sets an unapproved change aside. Part 1 of GHI 343, the `wiki-write` skill, stays there. GHI 343's open question, whether the check replaces the PreToolUse guard, is answered: it adds to it.
- **The third follow-up of the GHI-MD of GHI [Every refusal and warning a program hands an agent says why and what to do instead](https://github.com/nedschorus/nedschorus/issues/956)**: "a check that reports, and reverts, a guarded file changed without the user's approval by any means, a shell command included: approved writes record the file's hash and keep a copy, and a quotation of the user in a marker is checked against the transcript". That follow-up is the record of the user's 2026-10-03 design.

The user approved merging them into this GHI on 2026-10-11, as item 2 of the approval-walk `codex-simplification-trawl-survivors-2026-10-10`, and decided the design questions below in that item's follow-up questions on 2026-10-11 and 2026-10-12. The walk-minutes are `docs/walk/codex-simplification-trawl-survivors-2026-10-10-minutes.md` in the cold-read-improvement agent-seat's checkout on ned-box, and are shipped to the log-store when the approval-walk closes.

## The design

### When it runs, and how fast

It runs after every tool call, whatever the tool, and not at Stop. A command started in the background that writes after its tool call returns is caught at the next tool call.

When nothing has changed, it takes under 100 ms on ned-box per tool call, and a test measures that. For each guarded file it compares the change time (ctime), the modification time, the size and the inode with a stored record, and hashes only a file whose record differs. The change time is compared because no program can set it back, as `touch -d` can set the modification time back. The list of guarded files is cached and recomputed only when the output of `git ls-files --cached --others --exclude-standard` changes. A prototype measured on 2026-10-11 took about 40 ms per run on ned-box, most of it Python's start-up and that one git call.

### Which files each agent-session checks

An agent-session checks the guarded files of its own checkout and the guarded files outside every checkout: `~/.claude/CLAUDE.md`, `~/.claude/settings.json` and the memory directories. It does not check another agent-session's checkout; otherwise one agent-session could restore another's approved edit in the moment before that agent-session's own check records it. Inside a checkout, a file git ignores is not guarded, such as the compiled Python files Python writes under `.claude/hooks/__pycache__/`, with one exception: `CLAUDE.local.md`, which git ignores and which is guarded.

### Which version is approved

A guarded file's content is approved when it equals one of these:

1. **The version in the current commit (HEAD), unless a `git commit` in the same tool call put it there.** git's record of where HEAD has moved, the reflog, tells the two apart. A checkout, a reset, a merge, a pull, a rebase, a cherry-pick or a revert is git's own work; a `git commit`, including `--amend`, is the agent's. A shell command that edits `CLAUDE.md` and commits it in the same command is caught.
2. **A version written by an Edit, Write or NotebookEdit call that spent an approval marker file.** The guard deletes the marker before the write, so the guard also leaves a short note naming the file, the agent-session and the time, and the hook approves the version that write produced.
3. **For a guarded file git does not track** (`CLAUDE.local.md`, `~/.claude/CLAUDE.md`, `~/.claude/settings.json`, a memory file): the copy saved the first time the hook runs on that machine, or at the file's last approved write. Each machine keeps one copy per file path, shared by all its agent-sessions. After that first run, a new guarded file git does not track has no approved version.

Also:

- **A rename that leaves the content unchanged is approved:** a guarded file at a new path whose content equals the approved version of the file that left the old path. The old path is not restored. A file that must carry a set name, such as `SKILL.md`, is not renamed in practice, so no rule covers it.
- **A deletion is approved when git's own work removed the file,** such as switching to a branch that does not have it. Any other deletion is restored like a change.
- **A version the hook has set aside is never approved later, by any rule.** Otherwise a later `git reset --hard` or `git stash` would bring the commit holding it back as git's own work. The hook's message tells the agent to amend that commit before pushing.
- **While a rebase, merge or cherry-pick is in progress, the hook restores nothing and leaves its record as it is,** so that a conflict an agent is resolving is not wiped out. An operation is in progress when `rebase-merge`, `rebase-apply`, `MERGE_HEAD`, `CHERRY_PICK_HEAD` or `REVERT_HEAD` exists in the worktree's git directory, the test the user approved for GHI 956's location guard. The first check after the operation ends sees every file it changed, because their timestamps differ from the record.

### What it does with an unapproved change

- **A tracked guarded file, `CLAUDE.local.md` or `~/.claude/CLAUDE.md`:** it saves the changed version, puts the approved version back, and tells the agent what it restored, where the changed version is saved, and that the user's approval is needed to write it back.
- **`~/.claude/settings.json` and memory files:** it saves the changed version and tells the agent, and restores nothing. Claude Code writes `~/.claude/settings.json` when the user changes a setting with `/config` or `/model` or installs a plugin, and the hook cannot tell that from an agent's `sed`; restoring would undo the user's own choices. The guard lets no write into a memory directory through, with or without a marker, so no agent could write a set-aside memory file back. The agent tells the user, who says whether the change stays. Each changed version is reported once, not after every tool call.
- **A new guarded file with no approved version,** such as a wiki page written by a shell command: it moves the file into the save directory, and nothing takes its place.
- **The user's own edit, in an editor:** the hook cannot tell the user's editor from an agent's `sed`, so it handles the edit as any other. The agent shows the user the saved version; on his yes, the agent writes his words into the marker file and writes his version back with Edit.

The message says what was changed and restored, and why; then, each on its own line with its condition, what the agent does next: show the user the saved version and ask; if he approves, write his words into the marker file and write the version back with Edit or Write; if the change is in a commit, amend the commit before pushing.

### The save directory

One directory per machine, `~/guarded-file-approved-versions-and-set-aside-changes/`, outside every checkout and outside `~/.claude/`; under `~/.claude/` the guard would protect the directory's own files, and the hook would set aside its own writes. It holds:

- approved versions of guarded files git does not track, and versions approved by rule 2 that are not yet committed, each kept under its hash; approved versions of tracked files are not copied, because git already holds them;
- every changed version the hook set aside, with the agent-session, the time and the file's path.

Rules that keep agent-sessions from damaging each other's records:

- The directory is only ever added to. Each copy is written whole to a temporary file and moved into place with `os.replace`, as `nc-systems/handoff/uncommitted-work-snapshots.py` does.
- A set-aside entry is created with `O_EXCL`, so only the agent-session that creates it reports the change.
- The record of timestamps is kept per worktree, in that worktree's git directory (`git rev-parse --git-dir`), so it goes when the worktree goes and no two agent-sessions write the same record.
- A set-aside entry that nobody has answered is reported again by the next check in that checkout, so the change is not lost when the agent-session that found it ends.
- How long set-aside copies are kept is decided in the build.

### When something fails

The hook never restores a file before its set-aside copy is written. If anything fails, it restores nothing, exits 0, and tells the agent through `additionalContext` what failed, as `scripts/uncommitted-work-snapshot-hook.py` does.

### Checking a quotation of the user

The guard also checks the words an agent writes into a marker file against the user's transcript, and refuses a marker whose words the user never typed. The search reads the user's queued inputs too: a message he types while the agent is working is stored as a `queue-operation` record and a `queued_command` attachment, not as a `"type":"user"` record. On 2026-09-21 two agents missed a queued "y" that way and retracted a real approval for 49 minutes. When the transcript copy is behind, the guard says so rather than refusing.

## Tests the build must include

Each of these is a test case, run in a throwaway repository:

- a shell command that edits `CLAUDE.md` and commits it in the same command is caught, set aside and restored;
- a rebase, a merge that is not a fast-forward, a pull, a cherry-pick and a revert are not restored;
- `scripts/merge-lane-pull-request-head-and-merged-worktrees-rebuild.py`, which fetches a pull request and makes a merge commit in one call, is not restored;
- an approved Edit is not restored, including by another agent-session's tool call made at the same moment;
- the user's own edit is caught, saved, and written back by Edit after his approval;
- a memory file is reported once and never restored;
- a rename with unchanged content is approved; a rename with changed content is caught;
- a deletion made by switching branches is approved; any other deletion is restored;
- with a rebase stopped on a conflict, nothing is restored;
- when the save directory cannot be written, nothing is restored and the agent is told;
- with nothing changed, a run takes under 100 ms on ned-box.

## Known gaps

- **A pushed unapproved version.** Once an unapproved version has been pushed, the other machine and merge-lane-2 receive it as git's own work and approve it. Only the amend that the hook's message asks for closes that gap.
- **A hook switched off in `~/.claude/settings.json`** stays off until the user answers, because that file is reported, not restored. The project's own `.claude/settings.json`, which wires the project's hooks, is tracked by git and is restored.
- **A shell edit stashed in the same command** is never seen, and a shell edit made while resolving a rebase conflict is approved when the rebase continues. Both are rare.

## Open question

MD-skills recorded, on 2026-10-03, a wish to check quotations of the user in commit messages against the transcript as well as those in marker files. The user has not decided it; it goes to him when the build starts.

## Next action

Build the hook, the guard's note and the quotation check on one topic branch, with the tests above. The hook goes in `.claude/hooks/` as `guarded-file-unapproved-change-set-aside-and-restore-hook.py`.

## Search receipt

`scripts/ghi-info-ask.py "Is there an issue, open or closed, about a check that catches an instruction file or other guarded file … changed without the user's approval by a shell command or any route the instruction-file guard does not see …"` on 2026-10-11 named GHI 343 (open) as the nearest, GHI 161 and GHI 244 (closed; write detectors in the sanity-check and cold-read runners), and GHI 1036 (open; mechanical agent chores in programs and hooks); none covers this check apart from GHI 343, whose part 2 this GHI takes over.
