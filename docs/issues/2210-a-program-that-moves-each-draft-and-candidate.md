---
issue: "[A program that moves each `-draft` and `-candidate` file to the log-store when the work the file served merges or is dropped](https://github.com/nedschorus/nedschorus/issues/2210)"
kind: design
---
# A program that moves each `-draft` and `-candidate` file to the log-store when the work the file served merges or is dropped

## What this GHI asks for

A program, run without any agent-seat having to remember it, that moves each `-draft` and `-candidate` file to the log-store's `seats/<agent-seat name>/` directory once the work the file served has merged or has been dropped. Moving a file to the log-store is what the user calls archiving it. The work a file served is the pull request whose change the file was written for. The file's `serves:` line names that pull request or the nc-topic-branch that will carry it, says the work is pending or dropped, or is absent, in which case the program finds the work as "Which work a file served" says. Every step that needs no judgment is code. The program asks an agent-seat a question only at one of the judgment steps listed under "The judgment steps".

The program's proposed name is `nc-systems/general-tools/draft-and-candidate-file-move-to-log-store-after-its-work-merged-or-dropped.py`, in `nc-systems/general-tools/` because it belongs to no one system, as the "Program, in Python or shell" entry of the file naming and location standards page, `docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md`, says. The next action is one pull request that adds:

- the program, and its test in `nc-systems/general-tools/tests/`;
- the Stop hook, and the row for the hourly job in `nc-systems/general-tools/scheduled-jobs-on-each-machine.json`, from which `nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py` writes the cron entry, both described under "What runs the program";
- the `scripts/clean-worktrees.py` change described there;
- the test described under "Files tracked on main";
- the removal of the two files git tracks today, described there too;
- a change to the `-draft` entry of the file naming and location standards page that names the program, and to the `seats/` entry of the log-store's `README.md` that names it beside `scripts/seat-shared-file-ship.py`; that `README.md` is written from `STORE_README` in `nc-systems/cold-read/cold-read-record-ship.py`, so the change is made there.

## Why

A user-ruling of 2026-10-30, approved-by-walk as item 18 of the approval-walk `agent-instructions-editor-open-decisions-2026-10-26`, set the `-draft` entry of the file naming and location standards page. Since pull request [#2204](https://github.com/nedschorus/nedschorus/pull/2204) merged, the entry on main reads: "A `-draft` or `-candidate` file moves to the log-store's `seats/<agent-seat name>/` when the work it served merges or is dropped. A later candidate of the same subject adds the next number, such as `<subject>-candidate-2.md`." The walk-minutes record the approval at line 279 and the user's remark at line 283: `nedlern@ned-box:/home/nedlern/agents/agent-instructions-editor/docs/walk/agent-instructions-editor-open-decisions-2026-10-26-minutes.md`, which `scripts/walk-files-ship.py` ships to the log-store's `walk/` directory when the approval-walk closes. No program carries the rule out.

The user objected that the rule depends on the agent-seat remembering it, and asked for the step to be automated. His words, with his approval, on 2026-10-30, in agent-instructions-editor's agent-session: "I am concerned about the objection that the agent seat that wrote the file must remember to approve it. It seems like we could code prompt code this or automate this because we could associate, you would think that when something merges or is dropped, it knows what draft it was associated with, or file, or I mean design or candidate. So that would even be better if we could get rid of the objection by automating the removal process, not removal, the archiving process, which is what this really is."

What happens today without a program:

- A `-draft` file can stay on main long after its work merges. `docs/drafts/merge-gate-test-plan-draft.md` was added by commit 980401662, in pull request [#691](https://github.com/nedschorus/nedschorus/pull/691), which brought `scripts/merge-gate.sh` into the repository on 2026-09-23; the file is still on main on 2026-10-30.
- Files leave `docs/drafts/` when an agent remembers to remove them, sometimes in a batch long after the work: commit cb2e8990c, "Drop six drafts whose work has landed", on 2026-09-23. `git log --diff-filter=DR -- docs/drafts/` lists every removal and every move out of the directory.
- `-draft` files that git does not track sit in agent-homes with nothing to move them. On 2026-10-30, `git status --short docs/drafts` in `~/agents/ned-box-helper` on ned-box shows four untracked files, last written between 2026-10-03 and 2026-10-23.
- `scripts/clean-worktrees.py --remove`, which cron runs daily at 06:30 on ned-box, deletes the untracked files of each done worktree with it, a `-draft` file included; its docstring says "Uncommitted, untracked and ignored files do NOT keep a done worktree: they are removed with it". The only things it ships to the log-store first are cold-read-records and sanity-check-records.

## What a reader needs first

- A `-draft` or `-candidate` file, here, is a Markdown file whose name ends `-draft.md`, `-candidate.md` or `-candidate-<number>.md`. A name that only contains the word is not one: `docs/issues/15-candidate-skill-define-work-bounded-work-definition-spec.md` is a GHI-MD. The program leaves alone two kinds of file that other programs ship to the log-store: an approval-walk's `docs/walk/<walk name>-draft.md`, which `scripts/walk-files-ship.py` ships, and anything under a `cold-read-records/`, `md-review-records/` or `sanity-check-records/` directory, such as the frozen-copy a cold read keeps of a document it reviewed.
- The program looks for such files in two places on ned-box: in each agent-seat's own checkouts, which are its agent-home `~/agents/<agent-seat name>/` and every worktree under the agent-home's `.claude/worktrees/` and under `~/Projects/nedschorus/.claude/worktrees/`; and on `origin/main`, for files git tracks there. A file in a checkout whose path and bytes are the same as a file git tracks on `origin/main` is handled only as the file on main, so a file every checkout holds is handled once; a checkout's copy with different bytes is handled as a file of that checkout. A file committed on a branch other than main is handled like an untracked file of its checkout. A directory the program cannot list gets a `FAILED:` line naming it, and the program goes on with the rest.
- An agent-session's scratchpad is not searched: a file meant to outlive the agent-session does not belong there, and on ned-box `nc-systems/general-tools/claude-code-temp-folders-of-exited-agent-sessions-delete.py` deletes the scratchpads of exited agent-sessions, keeping only those its docstring lists, such as the one crash recovery would resume.
- The program never replaces a file in the log-store. `scripts/seat-shared-file-ship.py`, which also writes to `seats/<agent-seat name>/`, replaces a file of the same name, so the program does not use that program. The cold-read-record shipper, `nc-systems/cold-read/cold-read-record-ship.py`, has the step the program needs, `link_staged_files_never_over_existing`, the add-only placing that `scripts/walk-files-ship.py` also uses: it hard-links a staged file into place, never over a name already taken, and the caller judges each file by the sha256 read back. Two runs of this program that move the same name at the same moment therefore cannot replace each other's file; "Out of scope" names what `seat-shared-file-ship.py` can still do.
- A Stop hook reaches the agent through `additionalContext`, the text it returns in a `hookSpecificOutput` JSON object at the end of the agent's turn, which continues the conversation. `scripts/agent-seat-due-task-raise-hook.py` puts a task back in front of an agent-seat that way, and only in the agent-seat's own interactive agent-session, never in a headless `claude -p` child that the agent-seat's programs start. The program's Stop hook follows that hook in both respects.

## Design

### Which work a file served

The `serves:` line is a front matter line, between the `---` lines at the top of the file, with one value:

- `serves: pull-request <number>`;
- `serves: branch <nc-topic-branch name>`;
- `serves: pending`, for work that has no branch yet and has not been dropped;
- `serves: dropped`.

The program finds the work a file served by the first of these that applies:

1. The file has exactly one `serves:` line with one of the values above. A file with two `serves:` lines, or a value of any other form, gets no other rule: the program asks about it, judgment step 1, after the wait rule 3 gives.
2. The file is in a worktree under a `.claude/worktrees/` directory, which has a branch checked out, not a detached HEAD, and whose branch is neither `main` nor the agent-seat's seat-branch, which is named for the agent-seat: that branch is the work. Such a worktree is made for one branch, so the file's place says which. A file in the agent-home itself gets no work from its place, because the agent-home changes branch.
3. Otherwise the program asks the owning agent-seat, judgment step 1, once the file has not been written for a set time, so an agent is not asked about a file it is still writing; "Deferred-decisions" holds the time. For a file tracked on main, the time it was last written is the time of the last commit on `origin/main` that changed it.

Nothing that exists today records the work for a file in an agent-home's own `docs/drafts/` or for a file tracked on main. The commit that added a tracked file is not reliably the work it served: `docs/drafts/merge-gate-test-plan-draft.md` came in with its work, but `docs/drafts/ghi-write-skill-draft.md`, since removed, was added on 2026-08-06 by commit 6a098f42a, and the skill it was a draft of, `.claude/skills/ghi-write/SKILL.md`, by commit c6fb95faf on 2026-08-12. So the `serves:` line is new. It names the work the file is for, not the pull request that adds the file to main. A file whose work spans several pull requests says `pending` until the last of them is open, then names that one.

### Which agent-seat owns a file

The program never guesses an agent-seat, as `seat-shared-file-ship.py` never does: a file stored under the wrong agent-seat's directory is filed where nobody looks for it. The first of these that applies gives the owner:

1. A file tracked on `origin/main`: the agent-seat its front matter line `agent-seat: <agent-seat name>` names.
2. A file in `~/agents/<agent-seat name>/`, or in a worktree under it: that agent-seat.
3. A file in a worktree `~/Projects/nedschorus/.claude/worktrees/agent-<id>/`, which the Agent tool makes for a subagent: the subagent's transcript is `<projects directory>/<directory name>/<session>/subagents/agent-<id>.jsonl`, where the projects directory is the one `clean-worktrees.py` already searches for that transcript. Beside the `subagents/` directory is the parent agent-session's own transcript, `<session>.jsonl`, whose lines record the parent's working directory in their `cwd` field. The owner is the agent-seat whose agent-home is that working directory or holds it. For example, the subagent that wrote this GHI-MD worked in `~/Projects/nedschorus/.claude/worktrees/agent-a3f4fd3acacb45e1c/`, and its parent's transcript records the working directory `/home/nedlern/agents/agent-instructions-editor`, so a file in that worktree belongs to agent-instructions-editor.
4. Otherwise the file has no owner and nobody to ask. The hourly run leaves it, with a `LEFT:` line. The run `clean-worktrees.py` makes on a done worktree moves it to `seats/unknown-seat/`, the directory `scripts/save-uncommitted-scratch-worktrees-before-reboot.py` already uses for a worktree whose agent-seat it cannot name, whatever the state of its work, and prints it as moved, not left, so the worktree can be removed; so that nothing is lost and no agent-seat's directory gets a file that is not its own.

### When the work has ended

The program reads the state of the work from GitHub with `gh`, and from git. For a branch, it lists every pull request of that branch in any state, merged included, with `gh pr list --head <branch> --state all --limit 100`; a list of 100 is a failure, printed as a `FAILED:` line saying the list may be cut short, since it may be. For `serves: pull-request <number>`, the program reads that pull request's state and branch with `gh pr view <number> --json state,headRefName`; a number GitHub does not know is a failure. A branch exists on origin when `git ls-remote --exit-code --heads origin <branch>` exits 0, and not when it exits 2; it exists in the checkout when `git rev-parse --verify --quiet refs/heads/<branch>`, run in the checkout that holds the file, exits 0, and not when it exits 1. For a file tracked on main, only origin counts. The first of these that applies decides:

1. `serves: dropped`: move the file.
2. `serves: pending`: leave the file, and ask again, judgment step 1, once the file has not been written for the set time since the last question, so that a waiting file is not forgotten; the agent leaves `pending` in place when the work still waits.
3. A pull request of the work is open: leave the file.
4. A pull request of the work merged: move the file.
5. The branch exists on origin or in the checkout: leave the file, whether its pull requests were closed without merging or it has none. When the file has not been written for the set time, ask, judgment step 1.
6. The branch has at least one pull request, every one closed without merging, and exists neither on origin nor in the checkout: the work was dropped; move the file.
7. The branch has no pull request and exists neither on origin nor in the checkout: ask, judgment step 2.

In a done worktree, one that passes `clean-worktrees.py`'s landed, vacant and quiet tests, a file whose work is the worktree's own branch, with no pull request, is moved in place of rules 5 and 7: the branch carries nothing beyond `origin/main`. A subagent paused with unfinished work only in that file loses nothing, since the file is in the log-store. A branch the Agent tool makes for a subagent, such as `worktree-agent-a3f4fd3acacb45e1c`, is such a branch while it has no pull request.

When `gh` or `git` fails, times out, exits with a code other than the ones named above, or prints what the program cannot read, the program leaves the file and prints a `FAILED:` line naming the file and what the command said. A failure is never read as an answer.

### Moving one file

1. The stored name is the file's name. The program first looks in `seats/<agent-seat name>/` for a file of the same subject with the same bytes, the subject being the name without its `-draft`, `-candidate` or `-candidate-<number>` ending; when there is one, the file was moved before: the program removes the source as step 4 says, and its citation names that stored file.
2. When the stored name is taken by different bytes: a `-candidate` file takes the number after the highest number any stored candidate of its subject carries, `<subject>-candidate-2.md` when only `<subject>-candidate.md` is stored. A `-draft` file is not numbered, because the user-ruling numbers only candidates: the program leaves it where it is and asks the owning agent-seat, judgment step 3.
3. The program first renames the source to a hidden name beside it, so that an editor saving the file in the meantime writes a new file under the old name rather than into the one being moved. It then stages the hidden file and links it into place with `link_staged_files_never_over_existing`. When another program took the name in between with the same bytes, the file was moved; the program goes to step 4. With different bytes, a `-candidate` file goes back to step 2, at most 5 times in all, after which the program prints `FAILED:` for it; a `-draft` file goes to judgment step 3. A file the program does not move is renamed back, unless a new file now has its name, in which case the program prints `FAILED:` naming both.
4. The program reads the stored file back and removes the hidden file, or under step 1 the source, only when its sha256 matches the stored file's; otherwise it renames the hidden file back and prints `FAILED:`. A file in a checkout is removed from the working tree; when git tracks it on the checkout's branch, the removal shows in `git status` for the agent to commit. A file tracked on main is removed as "Files tracked on main" says.
5. The program prints one line per file moved, the citation `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/<agent-seat name>/<stored name>`, naming the stored file that holds the bytes, one line opening `LEFT:` per file it leaves, with the reason, such as the work still open or a question asked; and one line opening `FAILED:` per file that failed, naming the file, the command that failed and what it printed, with the source left where it is. It exits 0 when no file failed, and 1 when any did; leaving a file, or asking about one, is not a failure.
6. A `--move <path> --agent-seat <name>` option moves one named file by steps 1 to 5 without the rules of "When the work has ended", for a file whose work an agent has settled by hand.

### Files tracked on main

- A test over `git ls-files`, run by `scripts/run-all-test-suites.py` like every other nc-test-suite, fails when a tracked `-draft` or `-candidate` file lacks exactly one valid `serves:` line, or exactly one `agent-seat:` line naming an agent-seat that has an agent-home on ned-box, and says which line to add or correct. The author of the pull request that adds the file writes both lines, which the author knows at that moment. When a file reaches main without them anyway, because the test was not run on its pull request, the daily full test run of main fails until an agent adds them, and until then the program leaves the file, with a `LEFT:` line.
- When the work of a tracked file has ended, the program copies the file to the log-store, and the move finishes when the file leaves main: the program asks the owning agent-seat to remove it from main, judgment step 4. When the file changes on main before the removal merges, the program's next run finds bytes the log-store does not hold, and moves the new version by the same steps. Removing it is a pull request, and an agent, not a program, opens it: repointing a citation of the file can need its sentence rewritten, and the author of a pull request answers its review in a fix-round, which a program cannot. `scripts/branch-leaves-no-citations-of-removed-paths-test.py` fails a pull request that removes a path another file still cites.
- The pull request that builds the program moves the two files tracked today to the log-store with the program's `--move` option, run from its own branch, and removes them in the same pull request, repointing each citation of either path: `docs/drafts/merge-gate-test-plan-draft.md`, whose work was pull request #691, merged, written by the Mac's merge-lane-backlog agent-seat, as the Mac paths it cites show; and `docs/issues/archived/seed-claude-md-draft.md`, whose owner nothing records, which goes to `seats/unknown-seat/`. Neither file then needs the two front matter lines.

### What runs the program

- Runs for one agent-seat take a lock, with `flock` on a file per agent-seat, and `unknown-seat` has a lock file of its own, so that the cron entry, a Stop hook and `clean-worktrees.py` never handle one file at the same time; a run that finds the lock held skips that agent-seat and prints a `LEFT:` line saying so.
- A cron entry on ned-box runs the program every hour over every agent-seat's checkouts and over `origin/main`, after a `git fetch`, and appends its output to `~/.claude/draft-and-candidate-file-move-to-log-store.log`, as the other cron entries do. The cron entry moves every file whose work has ended and that needs no question, and asks nothing, so an agent-seat that is idle or retired still has those files moved. A file that needs a question, and a failure, reach an agent only through the owning agent-seat's Stop hook.
- A Stop hook, registered in `.claude/settings.json` beside `scripts/agent-seat-due-task-raise-hook.py`, runs the program for the agent-session's own agent-seat, named by `CLAUDE_CODE_TASK_LIST_ID` as the due-task hook reads it, and does nothing in an agent-session without one; it runs the program at most once an hour, and hands the agent its questions and its `FAILED:` lines through `additionalContext`. The hook keeps, for each agent-seat, the time it last ran the program and the time it last asked about each file. It asks about a file again only after the set time, so an answer that needs a pull request to merge first is not asked for every hour. When the hook cannot read those times, it runs the program and asks; when it cannot write them, it reports that as a non-blocking hook error, exit 1 with a line on stderr, as the due-task hook does, so that the turn still ends. With each `FAILED:` line it tells the agent to run the program again on that one file, with all its rules, once the cause is fixed, or to tell the user when the agent cannot fix the cause.
- `scripts/clean-worktrees.py --remove` runs the program on one done worktree before removing it, as it ships cold-read-records today, and keeps the worktree when the program prints a `LEFT:` or `FAILED:` line for one of its files, since removing the worktree would delete that file.
- On the Mac, the hook, the cron entry and the `clean-worktrees.py` change do nothing: the program exits 0 at once when the machine is not ned-box, and `clean-worktrees.py` on the Mac behaves as it does today. "Out of scope" says why.

### The judgment steps

Each is a question the Stop hook hands the owning agent-seat; the program decides none of them. Each question names the file and what the program found. The agent answers by changing the file, and the program's next run reads the change; for a file tracked on main, the change is a pull request, and the program reads it once it has merged.

1. The program cannot tell which work a file served, or the work's branch has no open pull request and the file has not been written for the set time. The question lists the nc-topic-branches of the agent-seat's worktrees and their pull requests, and the work the program found, if any. The agent writes or corrects the `serves:` line: a pull request or a branch, `pending` while the work waits, or `dropped`; or leaves a correct line as it is.
2. The served branch is gone with no pull request. The agent sets `serves:` to the pull request that carried the work, to the branch now carrying it, to `pending` while the work waits for a new branch, or to `dropped`.
3. A `-draft` file's name is already taken in the log-store by different bytes. The agent renames the file to a new subject that still ends `-draft.md`, or deletes it when the stored file holds everything worth keeping. For a tracked file, the rename or the deletion is a pull request.
4. A tracked file's work has ended and the file is in the log-store; the question gives the stored file's citation. The agent opens a pull request that removes the file from main and repoints every citation of its path in a file on main at the log-store copy. A citation in a log, in git history or on GitHub stays as it is.

## Out of scope

- The Mac. Its clones have their own agent-homes, and its files would need to reach the log-store on ned-box over ssh; a later GHI decides that, and until then the Mac behaves as it does today.
- An agent-seat that never runs again: files that need its answer, and failures of the cron entry, stay in the cron entry's log until a later GHI says who reads it.
- A later `seat-shared-file-ship.py` shipment of a file with the same name as one this program stored replaces that file, as that program does to any file in `seats/`, and announces it.

## Deferred-decisions

- How long a file goes unwritten, or unanswered, before the program asks about it, to be set from the first weeks of use.
- What the program does when an nc-topic-branch name is reused after an earlier pull request of that name merged, to be set by the pull request that builds the program.
- How much text the Stop hook hands the agent at once when many files need questions, to be set by the pull request that builds the program.
- The Stop hook's time limit, and the order in which a run that reaches the limit takes files, to be set by the pull request that builds the program from the time a run takes.
- The program's command-line options beyond `--move`, such as the ones for one file and for one worktree, where the Stop hook keeps its times, and the names and places of the Stop hook, the lock files and the test, to be set by the pull request that builds the program and checked against the file naming and location standards page.
- How the program's test runs it on the Mac, where the program otherwise exits at once, such as with the `COLD_READ_RECORD_SHIP_DESTINATION` override the shippers' tests use and an override of the machine check, to be set by the pull request that builds the program.
- How the program lists the agent-seats on ned-box and the checkouts each owns, such as a worktree under `~/agents/` made for one nc-topic-branch, to be set by the pull request that builds the program.
- Whether the program strips the `serves:` and `agent-seat:` lines from a copy promoted out of a `-draft` file, or a test fails on them in any file that is not one, to be set by the pull request that builds the program.
