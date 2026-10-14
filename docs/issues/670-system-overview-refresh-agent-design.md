---
issue: "[refresh-design: when a system's code lands, bring its design, build-slice plan and overview into line — removing, never revising](https://github.com/nedschorus/nedschorus/issues/670)"
---

# The refresh agent: each system's overview refreshed after main passes its nightly full test run

Status: design draft, written 2026-10-03 on ned-box for the agent-seat merge-lane-2; the user deferred building it to later maintenance work. Nothing is built; every path below that names a new program or brief is proposed. The design depends on PR [ned-box opens a window on the Mac through one forced command](https://github.com/nedschorus/nedschorus/pull/982), merged 2026-10-03.

Today the handoff-supervisor tells whichever agent-seat restarts first each day that an overview is due, and that agent-seat, busy with its own job, lets the refresh wait and go stale. This design gives the refresh to one agent that exists only while a refresh runs, and deletes the reminder.

## What starts a refresh

- A new scheduled job on ned-box, `system-overview-refresh-nightly-run`, one row in `nc-systems/general-tools/scheduled-jobs-on-each-machine.json`, cron `0 5 * * *` Pacific. The nightly full test run starts at 03:30, took 312 seconds on 2026-10-03, and waits at most an hour for its lock, so 05:00 is after its worst case.
- The job runs `scripts/system-overview-refresh-nightly-run.py`. The program reads the day's record `nedlern@ned-box:/home/nedlern/nedschorus-logs/daily-full-test-runs/ned-box/<YYYY-MM-DD>.txt`, goes on only when the record says `runner exit code: 0`, and takes the record's `origin/main:` commit as the tested commit, which every refresh that night is checked against and pinned to. ned-box's record alone decides: the refresh runs on ned-box, and the Mac's test run waits for the Mac to wake.
- Due systems are found by today's rule, moved unchanged from the handoff-supervisor's `overview_refresh_due_lines`: commits under `nc-systems/<system>/`, `.md` excluded, between the overview page's last `**Pinned to what landed:**` commit and the tested commit. A system with no overview page, or whose page an open pull request already changes, is passed over; the second case includes last night's refresh while its pull request waits to merge.
- With nothing due, the program exits within seconds and starts no `claude`. Nothing stays running between refreshes; an exclusive flock stops a second run from starting while one runs.

## One refresh agent, several systems on one night

- The refresh agent is one role with one brief, `docs/agents/system-overview-refresh-agent-instructions.md`, started fresh for each system as a pull-request reviewer is started fresh for each pull request. The refresh agent is never an agent-seat: no session-handoff, no task list.
- Due systems run one at a time, in name order, each as one `claude -p` run given one system, the range `<pinned commit>..<tested commit>`, a detached worktree at the tested commit, and a run directory outside every checkout. Both sit in the program's temporary directory, outside `.claude/worktrees/`, so the 06:30 `scripts/clean-worktrees.py --remove` job, which removes only worktrees under `.claude/worktrees/`, never removes them while a question waits.
- The refresh agent writes the refreshed page into the run directory as GHI [refresh-design: when a system's code lands, bring its design, build-slice plan and overview into line — removing, never revising](https://github.com/nedschorus/nedschorus/issues/670) defines a refresh, ending with a pinned line naming the tested commit. A range with nothing worth changing still gets the pinned line, so the next range starts there.
- Each system gets its own pull request, so a change rejected in one page holds back no other page.

## Whether the user must see a change, and how he answers

- **Sorting.** Step 9 of `.claude/skills/cold-read/SKILL.md` decides: a change to what a program or agent does, must do or may do, or to what the page decides or plans, goes to the user; a correction of past events, a citation, a reference, spelling or punctuation does not; a change the sorter cannot place goes to him. The refresh agent writes its list; the program then starts a second fresh-agent given only the diff and step 9, which writes its own list without seeing the first; the union goes to the user. A page with an empty union is published at once.
- **Cold read.** The page is a wiki page, so the cold-read skill's step 2 gives a refresh that changes more than one sentence a cold-read-full-run. The refresh agent runs the cold read in the run directory, stopping before step 9's approval-walk; what the cold read would send to the user joins the night's questions. See decision 3.
- **The guard.** `.claude/hooks/instruction-file-guard.py` refuses every Edit or Write under `docs/nedschorus-wiki/` without the user's quoted approval, and cannot tell a correction from a decision. Here the refresh agent writes only in the run directory and the program copies the page into the worktree, so a correction passes the guard's user-block on his ruling that a change that only makes a text right again needs no approval. The two sorters stand in for the guard. See decision 1.
- **Asking.** When any system has questions, the program starts, after the last system, one interactive `claude` session in the tmux session `system-overview-refresh` on ned-box, holding every question of the night, and runs `scripts/open-mac-window-from-ned-box.py tmux attach -t system-overview-refresh`, the helper PR [ned-box opens a window on the Mac through one forced command](https://github.com/nedschorus/nedschorus/pull/982) added, which opens a window on the Mac attached to that session. The session puts the questions to him in one approval-walk with /walk-me-through, applies his rulings to the pages in the run directories, and writes his exact words with their times to a rulings file. The program sees the file, ends the session, because an agent cannot end its own session, and publishes.
- **When the window does not open.** At 05:00 the Mac is often asleep, which is why the Mac's own nightly job waits for its wake. The program tries the window again every 15 minutes until the window opens or the deadline passes. A window closed before the end is reopened from the Mac with `ssh nedlern@ned-box 'tmux attach -t system-overview-refresh'`.
- **No answer.** The waiting session holds about 1 GB of ned-box's memory, so the program ends the session at 04:30 the next morning, before the next run, and publishes nothing for an unanswered system. The page on main is unchanged, so the next night refreshes the page again from a newer tested commit and asks again. See decision 2.

## How the refreshed page reaches main

- The program, not the refresh agent, copies the page into the detached worktree, commits only that file, pushes with `git push origin HEAD:refs/heads/system-overview-refresh-<system>-<YYYY-MM-DD>`, which makes no local branch, and runs `gh pr create`.
- The account is `ubuntu-claude`, the account ned-box's processes act as, token `~/.config/nedschorus/ubuntu-claude.token`; never `ned-review-merge`, which must stay free to approve, nor `nedlern`, the user. The description lists each change, which went to the user, his quoted rulings with their times or that both sorters found only corrections, and the night's record.
- merge-lane-2 handles the pull request like any other agent's. The pull request is prose only, so no reviewer is commissioned: merge-lane-2 checks that only that page changed, checks quoted rulings against the session's transcript, mirrored under `nedlern@ned-box:/home/nedlern/nedschorus-logs/transcripts/ned-box/`, approves as `ned-review-merge` and merges.

## A flaw the refresh agent finds

A flaw in the code, such as code that contradicts its design, goes through the /ghi-write skill's route and is listed in the pull request's description. Sending a flaw to the agent-seat working that system, started on demand, waits on a record of which agent-seat works which system and a way to hand work to a stopped agent-seat; GHI [Relaunch stopped agent-seats with open tasks daily](https://github.com/nedschorus/nedschorus/issues/936) and GHI [Seat mailboxes across machines and runtimes](https://github.com/nedschorus/nedschorus/issues/749) are the nearest designs.

## What the change deletes

The pull request that adds the program also deletes the reminder, so no night runs both.

- In `nc-systems/handoff/handoff-supervisor.py`: `overview_refresh_due_lines`; the constants `SYSTEM_OVERVIEW_PATH_TEMPLATE`, `SYSTEM_OVERVIEW_DRAFT_PATH_TEMPLATE`, `OVERVIEW_REFRESH_CHECK_GIT_TIMEOUT_SECONDS`, `OVERVIEW_REFRESH_CHECK_GH_TIMEOUT_SECONDS`, `OVERVIEW_REFRESH_REMINDER_MARKS_READ_TIMEOUT_SECONDS`, `OVERVIEW_REFRESH_DUE_INSTRUCTION_TEMPLATE`, `DAILY_OVERVIEW_REFRESH_REMINDER_MARK_PATH`; the loads of `daily-overview-refresh-reminder-mark.py` and `scripts/stale-code-citation-check.py`, used only by the overview check; the `overview_refresh_due` parameter of `build_ignition_prompt` and both `compose` methods; the call before launch; the overview sentence of the docstring's step 6.
- `nc-systems/handoff/daily-overview-refresh-reminder-mark.py` and `nc-systems/handoff/tests/daily-overview-refresh-reminder-mark-test.py`.
- The overview cases of `nc-systems/handoff/tests/handoff-supervisor-successor-prompt-test.py`, whose due-rule cases move to the new program's test; the marks override in `nc-systems/handoff/tests/handoff-supervisor-test-fixture.py`; the copies of `daily-overview-refresh-reminder-mark.py` and `stale-code-citation-check.py` in `scripts/resupervise-seat-test.py`; the deleted test's entry in `scripts/python-comments-carry-no-history-markers-test.py`.
- Text the deletion would leave wrong: the handoff overview's bullet on the "overview refresh due" line, with the user's approval; and, through edit-GHI, the trigger and next action in GHI [refresh-design: when a system's code lands, bring its design, build-slice plan and overview into line — removing, never revising](https://github.com/nedschorus/nedschorus/issues/670), the marks named in GHI [A small service on ned-box keeps one record of every agent-seat on both machines](https://github.com/nedschorus/nedschorus/issues/972), and the deleted program's messages quoted in GHI [Every refusal and warning a program hands an agent says why and what to do instead](https://github.com/nedschorus/nedschorus/issues/956).
- After the merge, the log-store directory `daily-overview-refresh-reminder-marks/`.

## How each failure is reported

Every run writes `nedlern@ned-box:/home/nedlern/nedschorus-logs/system-overview-refresh-nightly-runs/<YYYY-MM-DD>.txt`, one line per system: not due, passed over and why, published with the pull request's link, unanswered, or failed with the command and the end of its error output. The program exits nonzero when any system failed, cron appends its output to `/home/nedlern/.claude/system-overview-refresh-nightly-run.log`, and a failure also opens a Mac window running `less` on the record, retried as above.

| What failed | What happens |
|---|---|
| No test-run record for the day, or the test run did not pass | Record says "not run" and why; exit 0. The test run's own record reports the test run, and merge-lane-2 reads that record at session start. |
| `claude` cannot start, is logged out, or exits nonzero | That system failed; the window shows `claude`'s output, remedy included. The next night tries again. |
| No page written, or no new pinned line | That system failed; nothing published. |
| Copy, commit, push or `gh pr create` fails | That system failed, with the command and its output; the run directory is kept until the next run. |
| The window cannot open | The record names the helper's cause: key not admitted, Mac's host key unknown, or Mac unreachable. Retried until the deadline; then the systems are recorded unanswered. |
| An open pull request already changes the page | Not a failure: "passed over", with that pull request's title and link. |

## Names

The agent: `system-overview-refresh-agent`, proposed as a project-term; until the user approves the name, prose writes "the refresh agent". Also the program `scripts/system-overview-refresh-nightly-run.py`, the job `system-overview-refresh-nightly-run`, the brief `docs/agents/system-overview-refresh-agent-instructions.md`, the tmux session `system-overview-refresh` and the log-store directory `system-overview-refresh-nightly-runs/`. On 2026-10-03, after `git fetch`, `git ls-tree -r --name-only origin/main` and `git grep -i` on `origin/main` found none of `system-overview-refresh`, `system_overview_refresh`, `overview-refresh-agent`, `refresh-agent` or `refresh agent`, and neither does this checkout.

## Decisions for the user

1. **A correction reaches a wiki page without him**, past the instruction-file guard's user-block, when both sorters find only corrections. Recommendation: yes; otherwise every refresh goes to him. **RULED Y** by the user, "y", 2026-10-04 about 00:15Z, in merge-lane-2's agent-session on ned-box: corrections merge without him; anything either sorter calls a decision still goes to him.
2. **An unanswered question holds the whole page**: the session ends at 04:30, nothing for that system is published, corrections included, and the next night asks again. The alternative publishes the corrections at once and holds only the questions, at the cost of two pages and two pull requests per system. Recommendation: hold the whole page. **RULED Y** by the user, "y", 2026-10-04 about 16:30Z, in merge-lane-2's agent-session on ned-box: an unanswered question holds the whole page, corrections included.
3. **Which cold read a refresh takes.** The skill as written gives six cold-read-cells whenever more than one sentence changes. Recommendation: the cold-read-fast-read for a refresh, as an exception he rules, because a nightly change to one page does not repay six cold-read-cells. **RULED Y** by the user, 2026-10-05 about 04:25Z, in merge-lane-2's agent-session on ned-box: "for daily maintenance a fast cold read is enough". He added a separate proposal, not part of this design: a monthly cold-read-full-run, staggered across the month, of each important markdown file, wiki pages included, that has never had one or has changed since its last one.

## Not settled

- PR [ned-box opens a window on the Mac through one forced command](https://github.com/nedschorus/nedschorus/pull/982) put the helper on main on 2026-10-03; until its key is installed on the Mac, the refresh agent cannot ask anything.
- When the Mac stays unreachable all day, nobody reads the night's record until a window opens; whether an agent-seat should read the record at session start is open.
- GHI [refresh-design: when a system's code lands, bring its design, build-slice plan and overview into line — removing, never revising](https://github.com/nedschorus/nedschorus/issues/670) covers three documents; the refresh agent covers the overview only.
- Four of the five systems under `nc-systems/`, namely `cold-read`, `general-tools`, `main-gatekeeper` and `skills`, have no overview page. Today's rule passes them over, while the refresh-design GHI in the item above says the first refresh creates a system's overview. Creating a page is more than a correction and would always go to the user; whether the refresh agent creates missing pages is his ruling.
