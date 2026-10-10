---
issue: "[Move mechanical agent chores into programs and hooks](https://github.com/nedschorus/nedschorus/issues/1036)"
---

# Move mechanical agent chores into programs and hooks

Agents in this project are told, in skills and standing instructions, to do by hand chores that a program, a hook or a scheduled job could do. Each chore costs every agent that does it some attention, and an agent that forgets one leaves the work undone, with nothing to report the gap. A survey found eleven such chores. Four are still to build; the other seven are settled, as the last section lists.

## Why

The user asked, in agent-seat reboot-test's agent-session of 2026-10-02 on the Mac, at 21:45:56Z: "why run by hand when they can just be scheduled? Why give agents extra burden? Are there other things that can be shifted from agents to automation?" A survey of the standing instructions on main that day found the eleven chores. The user approved filing this GHI at 21:59:30Z the same day, noting that agents handle special cases smoothly and a script might have to pass back to the agent anything it stumbles on.

## The rules every chore follows

1. **The program does only the normal case.** Anything else stops and goes back to the agent with a plain message saying what failed: the program prints what failed and exits nonzero, or puts the failure in the text the agent reads next. The program never handles the special cases an agent handles; it only recognises that a case is not the normal one. Each build's tests check that the normal case works and that each unexpected case is reported, not handled.
2. **Prevent first.** Where an agent must still act, the program or hook tells the agent the rule at the moment the agent is about to act, so the agent gets it right the first time.
3. **Check right after the write.** A check runs as soon after the agent's edit as it can, in the same turn, so a mistake is fixed before it reaches a commit, a pull request or another document.
4. **Scale.** A check handles 50 changed files with 100 findings in seconds, and groups its findings rather than printing a wall of text.
5. **Parse accurately, or not at all.** A check that parses text uses the language's own parser where one exists, and reports what it finds rather than fixing it. A check that cannot be sure says so; it never guesses.

The user accepted rule 1 on 2026-10-02 and set rules 2 to 5 on 2026-10-06, when he paused the first approval-walk on this GHI: checks must be "as preventive as possible", must "run as quickly as possible to the write/edit", must "handle say 50 files with 100 things to check or correct", and "if parsing is required, it better be super accurate or we'll introduce errors".

## The four chores to build

Checked against main on 2026-10-10. The rulings are from two approval-walks, whose minutes are in the log-store: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/move-mechanical-agent-chores-into-programs-and-hooks-2026-10-04-minutes.md` and `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/move-mechanical-agent-chores-rework-decisions-2026-10-09-minutes.md`. Build them in this order, smallest first, each on its own topic branch and pull request, with tests for the normal case and for each unexpected case being reported. Test each chore in use once it is built.

### 1. The handoff's next-step text goes in on standard input (chore 3)

Today step 1 of `.claude/skills/handoff/SKILL.md` has the agent run a shell expression to get the next-step file's path, write the text there, and pass the path to `nc-systems/handoff/handoff-write-and-check-supervisor.py --next-step-file`.

To build: `handoff-write-and-check-supervisor.py` reads the next-step text on standard input, and the agent pipes the text in with a quoted heredoc, `handoff-write-and-check-supervisor.py <<'EOF'`, the text, then `EOF`, so that no quoting or escaping of the text is needed. No separate next-step file is written: the program already copies the whole text into the handoff file's verbatim block. Empty input, or standard input that is a terminal, is refused with a message saying so. A failed write exits 3, distinct from 1 ("written, but no supervisor is watching") and 2 (a refusal), and the skill's step that reads the exit status treats 3 as a stop. A crash loses nothing: the agent still holds the text and pipes it in again. `--next-step-file` and the skill's step 1 expression go.

### 2. Cold-read triage and walk-minutes ship on every write (chore 4)

Today an agent runs `nc-systems/cold-read/cold-read-record-ship.py` after writing a cold-read-record's `triage.md`, and `scripts/walk-files-ship.py` at an approval-walk's close.

To build: a `PostToolUse` hook on the Write and Edit tools, registered in `.claude/settings.json` beside the project's other `PostToolUse` hooks, which takes the written file's path from the tool call's `file_path`. The hook never blocks the write: it exits 0 and reports through the additional context that the agent reads next, as the project's other `PostToolUse` hooks do. Each write ships the file as it then is, so when writes follow one another quickly the last shipment holds the last text.
- When the file written is a cold-read-record's `triage.md`, the hook runs `cold-read-record-ship.py` on that record. The shipper already replaces a stored `triage.md` and leaves the record's unchanged files alone.
- When the file written is an approval-walk's walk-minutes, the hook ships that file alone. `walk-files-ship.py` gains a flag that ships the walk-minutes alone, given the walk-minutes file's path, because a shipment of the whole approval-walk refuses a walk-document that changed during the approval-walk, as a re-planned approval-walk's does. The shipper already replaces stored walk-minutes.
- The approval-walk's other files still ship at its close, by the step the /walk-me-through skill already has.
- When ned-box cannot be reached, the hook prints that and the shipper's remedy, and the next write tries again. A connection attempt has a short time limit, so an edit is not held up for long while ned-box is down.
- Step 9 of `.claude/skills/cold-read/SKILL.md` drops its hand-shipping instruction for `triage.md`.

Out of scope: a file written through Bash, which the hook does not see, so an agent that writes one of these files through Bash runs the shipper itself; and a sanity-check-record's `finding-dispositions.md`, which `.claude/skills/sanity-check/SKILL.md` step 7 still ships by hand once it is finished, because the store refuses a changed copy of that file.

### 3. Pull request states go into the successor's initial-agent-instructions (chore 2)

Today `BRANCH_STATE_INSTRUCTION` in `nc-systems/handoff/handoff-supervisor.py` tells each successor to rebase a never-pushed branch, rerun the tests, and check its pull requests with `gh`.

To build: the handoff-supervisor runs no tests at handoff. It finds the agent-seat's open pull requests by their commits' git author: `scripts/launch-claude-ubuntu`, `scripts/launch-claude-mac` and `scripts/recover-crashed-seats.py` already set `GIT_AUTHOR_NAME` to the agent-seat's name in every agent-session, so an open pull request with a commit whose author is the agent-seat belongs to it. It writes each such pull request into the successor's initial-agent-instructions: its state, its newest review, and whether it conflicts with main, with a time limit on the `gh` calls; when a call fails or times out, the initial-agent-instructions say so plainly. Each pull request gets one state line. Two states add an instruction to their line: a review with findings adds the fix by a forked subagent that CLAUDE.md describes, and a conflict with main adds the hand-merge `scripts/branch-conflict-check.py` describes. Every other state, such as a pull request awaiting review, gets its state line and no instruction. The initial-agent-instructions already carry the supervisor's branch-sync report; when that report says the checkout was not brought up to date with main, they add the instruction to rebase a never-pushed branch before any other work, because the supervisor only fast-forwards and the Stop hook `scripts/checkout-freshness-catch-up.py` skips a checkout with uncommitted changes or a conflict. The unconditional instructions to rebase, rerun the tests and check pull requests go.

### 4. create-GHI deletes the author's input file (chore 5)

To build, with the next change to `scripts/ghi-issue-write.py`: create-GHI deletes the author's input file once the pull request is open, only when that file is not the copy under `docs/issues/` itself, which a resumed filing can be given, and keeps it, saying so, when the pull request could not be opened. The program's last line, which today names the input file as the path to rerun on after the merge, names the copy under `docs/issues/` instead.

The rerun after a merge waits on GHI [An issue has one GHI-MD and many supporting documents, and the GHI write tool cannot tell them apart](https://github.com/nedschorus/nedschorus/issues/783). Its design has merge-lane-2 rebuild the issue bodies after each merge it makes, and makes the ghi-write skill's rerun a fallback for a merge the rebuild did not cover. Until that is built, agents rerun by hand.

## The seven chores settled

- **Chore 1, the tests before a push: dropped.** merge-lane-2 runs the same selection of test suites on each pull request's head commit merged onto main before merging, and every suite runs on main each night. A pre-push hook would add minutes to every push, including the GHI write tool's. CLAUDE.md's "Before pushing" line stays.
- **Chore 6, a name-collision helper script: dropped.** After each edit, `scripts/new-shared-names-reminder-hook.py` lists the new shared names the branch adds and tells the agent to send them to the fresh agent `.claude/agents/new-name-propose-and-check-fresh-agent.md`, which runs the searches against the naming page. The hook reminds; the agent still dispatches the check.
- **Chore 7, citing by a bare number: built.** `scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py` reports, and never fixes, each bare reference in Markdown just written and in the agent's previous reply. Two exceptions to the rules above: it finds references with regular expressions, not a Markdown parser, and it checks a reply at the user's next message, not in the same turn.
- **Chore 8, the daily reminder's `started` mark: moved** to GHI [Daily maintenance in one daily step](https://github.com/nedschorus/nedschorus/issues/1058).
- **Chore 9, an agent-seat's first checks: dropped.** The launcher already prints its failure when it cannot make the agent-home a worktree; that fallback has not been seen to fire, and the root cause of the broken worktrees found, worktrees kept under `/tmp` on the Mac, is gone now that they live under `~/agents/`.
- **Chore 10, announcing pull requests to merge-lane-2: built.** merge-lane-2 runs `scripts/watch-open-pull-requests.py`, and the standing instructions no longer ask for announcements (PR [Standing instructions no longer ask agents to announce a pull request or a push](https://github.com/nedschorus/nedschorus/pull/1082)).
- **Chore 11, citing sanity-check-records: dropped, already built.** `scripts/sanity-check-attacks.py` ships its record when an invocation of it ends and prints the `record:` line, which is the citation.

## Related GHIs

GHI [Three mechanical checks agents keep forgetting to run: file-overlap before work starts, exit status through a pipe, and the settled-decision list](https://github.com/nedschorus/nedschorus/issues/216) has the same aim but holds three different checks. GHI [Four places where agent instructions should be Python: supervisor merge advice, appended-prompt editor notes, cold-read full-run rule, walk bare references](https://github.com/nedschorus/nedschorus/issues/418), closed, is the earlier survey of this kind.

## Next action

Build the handoff's next-step text on standard input (chore 3), then the other three in the order above.
