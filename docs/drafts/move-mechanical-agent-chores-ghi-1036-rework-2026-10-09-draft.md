---
issue: "[Move mechanical agent chores into programs and hooks](https://github.com/nedschorus/nedschorus/issues/1036)"
---

# Move mechanical agent chores into programs and hooks

Agents in this project are told, in agent-instructions, to do by hand chores that a program, a hook or a scheduled job could do. When the survey below was made, each chore cost every agent that did it some attention, and an agent that forgot one left the work undone, with nothing to report the gap. The survey found eleven such chores. Programs for four of them are still to be built; the other seven are settled, as the section "The seven chores settled" lists.

## Why

The user asked, in agent-seat reboot-test's agent-session of 2026-10-02 on the Mac, at 21:45:56Z: "why run by hand when they can just be scheduled? Why give agents extra burden? Are there other things that can be shifted from agents to automation?" A survey of the agent-instructions on main that day, the prompt texts inside programs included, found the eleven chores. The user approved filing this GHI at 21:59:30Z the same day, noting that agents handle special cases smoothly and a script might have to pass back to the agent anything it stumbles on.

## The rules for the programs

1. **The program does only the normal case.** Every other case stops and goes back to the agent with a plain message saying what failed: the program prints what failed and exits nonzero, or puts the failure in the text the agent reads next. The program never handles a case an agent handles; it only recognises that a case is not the normal one. Each build-slice's tests check that the normal case works and that each failure case its section below names is reported, not handled.
2. **Prevent first.** Where an agent must still act, the program or hook tells the agent the rule at the moment the agent is about to act, so the agent gets it right the first time.

Rules 3 to 5 bind a check: a program or hook that inspects what an agent has just written and reports what it finds.

3. **Check right after the write.** A check runs as soon after the agent's Write or Edit call as it can, in the same turn, so a mistake is fixed before it reaches a commit, a pull request or another document.
4. **Scale.** A check handles 50 changed files with 100 findings in seconds, and groups its findings rather than printing a wall of text.
5. **Parse accurately, or not at all.** A check that parses text uses a real parser for the language where one exists. A check that cannot be sure says so; it never guesses.

The user accepted rule 1 on 2026-10-02. On 2026-10-06, when he paused the first approval-walk on this GHI, he said that checks must be "as preventive as possible", must "run as quickly as possible to the write/edit", must "handle say 50 files with 100 things to check or correct", and "if parsing is required, it better be super accurate or we'll introduce errors"; rules 2 to 5 restate those words.

## The five programs to build

Checked against main at commit 01b413b5 on 2026-10-10 (UTC). The user-rulings are from two approval-walks, whose walk-minutes are in the log-store: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/move-mechanical-agent-chores-into-programs-and-hooks-2026-10-04-minutes.md` and `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/move-mechanical-agent-chores-rework-decisions-2026-10-09-minutes.md`. Build the five in the order of the headings below, each as a build-slice on its own topic branch and pull request. Once each build-slice is merged, run an acceptance test of it: use it in the agents' real work, confirm it does what its section says, and tell the user the result.

### Chore 3: the session-handoff's next-step text goes in on standard input

Today step 1 of `.claude/skills/handoff/SKILL.md` has the agent run a shell expression to get a next-step file's path and write the text there, and step 2 has the agent pass that path to `nc-systems/handoff/handoff-write-and-check-supervisor.py --next-step-file`.

To build:
- `handoff-write-and-check-supervisor.py` reads the next-step text on standard input. The skill's steps 1 and 2 become one step: the agent runs `nc-systems/handoff/handoff-write-and-check-supervisor.py <<'END-OF-NEXT-STEP'`, then the text, then a line `END-OF-NEXT-STEP`. The quoted delimiter means the text needs no quoting or escaping, and the program already refuses a text containing a line `END-OF-NEXT-STEP`, so the delimiter cannot end the text early.
- No next-step file is written: the program already copies the text into the session-handoff file, which was the next-step file's only use. `--next-step-file` goes.
- Empty input, and standard input that is a terminal, are refused with a message saying so.
- Any failure to write the session-handoff file, an unexpected error in the program included, exits 3: the program catches every error in its main function, so exit 1 keeps meaning only "written, but no supervisor is watching" and exit 2 a refusal. Step 3 of the skill gains the case: when the program exits 3, the session-handoff was not written; tell the user what the program printed, and run the step again once the cause is cleared. The agent still holds the text, so nothing is lost when the program fails.

### Chore 4: a cold-read-record's `triage.md` and an approval-walk's walk-minutes ship on every write

Today an agent runs `nc-systems/cold-read/cold-read-record-ship.py` once triage of a cold-read-record is finished, as step 9 of `.claude/skills/cold-read/SKILL.md` says, and `scripts/walk-files-ship.py` at an approval-walk's close, as the /walk-me-through skill says. A record or walk-minutes not yet shipped lives on one machine only, and is lost with that machine's checkout.

To build:
- A `PostToolUse` hook on the Write and Edit tools, registered in `.claude/settings.json` beside the project's other `PostToolUse` hooks with a timeout of 30 seconds, which takes the written file's path from the tool call's `file_path`.
- When the path is a cold-read-record's own `triage.md`, at the top of a directory under `cold-read-records/` and not under its `target/`, the hook ships that one file. `cold-read-record-ship.py` gains a flag that ships only the record's `triage.md`, which the log-store already replaces with each new copy. The hook never ships the rest of the record, because a cold-read-cell may still be writing its report, and a report shipped half-written would make every later shipment of the record refuse.
- When the path is an approval-walk's walk-minutes, recognised as `scripts/walk-files-ship.py` recognises an approval-walk's files, the hook ships that one file. `walk-files-ship.py` gains a flag that ships only the walk-minutes, which the log-store already replaces with each new copy. Without the flag, a re-planned approval-walk's changed walk-document is refused on every shipment, with a REFUSED line and exit 2 each time.
- The hook never blocks the write. It exits 0 and passes to the agent, through the additional context the agent reads next, the shipper's one-line result and any remedy the shipper prints, but not the shipper's notice of the copy it replaced. When ned-box cannot be reached, the result says so, and the next write of the same file tries again.
- The shipping steps already in the skills stay: step 9 of the cold-read skill ships the whole cold-read-record once triage is finished, and the approval-walk's close ships the whole approval-walk. The hook keeps the work safe while it is being written; those steps remain the ones that ship the final text, including after a last write whose shipment failed, and they cover a file written through Bash, which the hook does not see. A sanity-check-record's `finding-dispositions.md` is not shipped by the hook: step 7 of the sanity-check skill still ships it once it is finished, because the log-store refuses a changed copy of that file.

### Chore 2: the agent-seat's open pull requests go into the successor's initial-agent-instructions

Today `BRANCH_STATE_INSTRUCTION` in `nc-systems/handoff/handoff-supervisor.py` tells each successor: "If this seat has open pull requests, check their state with `gh`".

To build:
- The handoff-supervisor finds the agent-seat's open pull requests: those whose head commit's git author is the agent-seat. `scripts/launch-claude-ubuntu`, `scripts/launch-claude-mac` and `scripts/recover-crashed-seats.py` set `GIT_AUTHOR_NAME` to the agent-seat's name in each agent-session they start. The head commit is the one the agent-seat pushed last, so a pull request whose branch also carries another agent-seat's earlier commits still belongs to one agent-seat.
- For each one, it writes one line into the successor's initial-agent-instructions, with only what GitHub reports: the pull request's title and link; its head commit; whether a review of that head commit exists, with a link to each one; and whether GitHub reports the pull request as mergeable, conflicting, or not yet known.
- When GitHub reports a conflict, the line adds: run `scripts/branch-conflict-check.py`, whose report says whether to hand-merge or to close the pull request.
- Whether a review carries findings stays the successor's judgment: no program can read that from a review's prose, and CLAUDE.md says what to do with findings.
- The `gh` calls have a time limit of 30 seconds in all; when a call fails or the time runs out, the line says so plainly, in place of the pull requests.
- Two sentences of `BRANCH_STATE_INSTRUCTION` go: "If this seat has open pull requests, check their state with `gh`", which the lines replace, and the sentence on clearing a conflict with a hand-merge, which the conflict line replaces. The rest stays: rebasing a never-pushed branch and rerunning its tests, leaving a pushed branch as it is, and the fix-round by a forked subagent when a review has findings.
- Tests: a hung or failing `gh` still lets the successor start, with a line saying what failed; the lines never claim a review or a state GitHub did not report; a review of an older head commit is not shown as a review of the current one.

### Chore 5: create-GHI deletes the author's input file

To build, on its own topic branch: when create-GHI has opened its pull request, it deletes the author's input file if that file is not tracked by git, and says so. A tracked input file is left alone, and the program says so: when main tracks it, filing moves it and the merge removes the original; when only the author's branch tracks it, the author removes it on that branch. When the pull request could not be opened, the input file is kept, and the program says so. If the pull request is later closed without a merge, the text is still on the pull request's branch, which the program names in its output.

The rerun of create-GHI after the merge, which links the GHI's body to the merged file, stays the author's step, as the /ghi-write skill says. GHI [An issue has one GHI-MD and many supporting documents, and the GHI write tool cannot tell them apart](https://github.com/nedschorus/nedschorus/issues/783) has merge-lane-2 rebuild GHI bodies after each merge it makes; its design keeps the author's rerun as the fallback for a merge the rebuild did not cover.

### Chore 12: a reply that promises later work creates a task in the same turn

When an agent tells the user that something will happen soon, later or next, or that it goes on the list, the agent creates a task for it in the same turn, so the promise is not forgotten when the agent-session ends or is compacted.

To build, on its own topic branch: a Stop hook and a SubagentStop hook, modelled on `scripts/absence-claim-locator-reminder-hook.py`, that reads the agent's last reply. When the reply promises later work in those words and the turn made no TaskCreate call, the hook reminds the agent to create the task now and to tell the user the task exists. The hook never blocks. The task lists themselves are already copied to the log-store by the transcript mirror (PR [transcript mirror: also copy task lists, seat-briefs and ~/.claude/CLAUDE.md to the log-store](https://github.com/nedschorus/nedschorus/pull/1182)). The user approved this chore on 2026-10-11, in agent-seat cold-read-research's approval-walk daily-memory-review-2026-10-09, item 7.

## The seven chores settled

- **Chore 1, the tests before a push: dropped.** merge-lane-2 runs the same selection of test suites on each pull request's head commit merged onto main before merging, and `scripts/daily-full-test-run-of-main.py` is scheduled to run every suite on main each night. A pre-push hook could add minutes to any push that changes a suite's recorded inputs, the ghi-write-tool's pushes included. CLAUDE.md's "Before pushing" line stays.
- **Chore 6, a name-collision helper script: dropped.** After each Write, Edit or Bash call, `scripts/new-shared-names-reminder-hook.py` lists the new shared names the branch adds, each name once and at most 30 at a time, and tells the agent to send them to the fresh-agent `.claude/agents/new-name-propose-and-check-fresh-agent.md`, which checks them against the naming page `docs/nedschorus-wiki/nedschorus-how-to-choose-a-name-for-files-code-and-glossary-terms.md`. The hook reminds; the agent still dispatches the fresh-agent.
- **Chore 7, citing by a bare number: built.** `scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py` reports, and never fixes, a pull request, GHI or task cited by a bare number in Markdown just written and in the agent's previous reply. It does not scan files git ignores, such as walk-documents and `triage.md`, and lists at most 10 hits at a time. It departs from rules 3 and 5: it finds the numbers with regular expressions, not a Markdown parser, and it checks a reply at the user's next message, not in the same turn.
- **Chore 8, the daily reminder's `started` mark: moved** to GHI [Daily maintenance in one daily step, starting with a daily check of every wiki page](https://github.com/nedschorus/nedschorus/issues/1058). The chore was the agent running `nc-systems/handoff/daily-memory-review-mark.py started` when the daily memory-review reminder reached it.
- **Chore 9, an agent-seat's first checks: dropped.** The chore was the agent running `pwd`, `git rev-parse --show-toplevel` and `git branch --show-current` at the start of an agent-seat's first agent-session. When `scripts/launch-claude-ubuntu` or `scripts/launch-claude-mac` cannot make the agent-home a worktree, the launcher prints the failure and starts the agent without project settings; that has not been seen to happen. The broken worktrees that prompted the chore had a root cause that is now gone: they were kept under `/tmp` on the Mac, which macOS cleans, and agent worktrees are now kept under `~/agents/`.
- **Chore 10, announcing pull requests to merge-lane-2: built.** merge-lane-2 runs `scripts/watch-open-pull-requests.py`, and the standing instructions no longer ask for announcements (PR [Standing instructions no longer ask agents to announce a pull request or a push](https://github.com/nedschorus/nedschorus/pull/1082)).
- **Chore 11, citing sanity-check-records: built.** `scripts/sanity-check-attacks.py` ships its sanity-check-record when an invocation of it ends and prints a `record:` line; when the shipment succeeded, that line ends with the citation, and step 8 of the sanity-check skill has the agent copy it into the pull request's description.

## Related GHIs

GHI [Three mechanical checks agents keep forgetting to run: file-overlap before work starts, exit status through a pipe, and the settled-decision list](https://github.com/nedschorus/nedschorus/issues/216) has the same aim but holds three different checks. GHI [Four places where agent instructions should be Python: supervisor merge advice, appended-prompt editor notes, cold-read full-run rule, walk bare references](https://github.com/nedschorus/nedschorus/issues/418), closed, is the earlier survey of this kind.

## Next action

Build chore 3, then chores 4, 2, 5 and 12, in the order of the headings above.
