---
issue: "[Wake an agent-seat when its 5-hour session limit resets](https://github.com/nedschorus/nedschorus/issues/1152)"
---

# Wake an agent-seat when its 5-hour session limit resets

An agent-seat that hits Claude's 5-hour session limit stops mid-work and stays idle after the limit resets, until someone types to it. This GHI makes every agent-seat wake itself every 3 hours, whether or not it hit a limit: a recurring job inside its own Claude Code session, created with the CronCreate tool, hands the agent a short prompt. A job fires only while the session is idle, so a working agent-seat is not interrupted; one with nothing to do answers the prompt and stops, which costs little; one stopped at its limit resumes within 3 hours of the reset. No program outside Claude, no tmux, no transcript parsing and no reset-time arithmetic. ned-box's agent-seats come first; the Mac's follow in a second step of this GHI.

The user approved filing this GHI on 2026-10-09 (about 17:20Z, "y") as item 7 of merge-lane-2's approval-walk merge-lane-2-waiting-on-user-walk-2026-10-07; the walk-document is `nedlern@ned-box:/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-waiting-on-user-walk-2026-10-07.md` and its minutes `nedlern@ned-box:/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-waiting-on-user-walk-2026-10-07-minutes.md`, both untracked files in merge-lane-2's checkout. On 2026-10-12 the user narrowed it to the 5-hour limit, in prime-intellect's agent-session bafa2657-92ad-439d-ac19-89fdad69d71e: "Agents have 3 limits - context, which we have a solution for, a 5 hour window, which the 'waker' just needs to watch or see that "You've hit your session limit · resets 1am (America/Los_Angeles)' which I guess is visible in the jsonl, and then send that agent a "." to wake them at the appropriate time. ... But if the agent hits the weekly limit, that is a different problem, one that needs its own GHI." The user then ruled on the open points (same agent-session, 2026-10-12), numbered 1 to 4 in the earlier version of this GHI-MD, with 5 being the split under "Split out": "1 - y, 2 - these agents are frozen. It they need a . and enter to push the . If there is other stuff in the line buffer I don't care - as long as we send (that is push enter) something. Don't wait or we'll be waiting for hours. 3 - we need both fixed, but you can do just one machine first. 4 - 4 - Y, 5 - 5 - separate issue." On 2026-10-18, in prime-intellect's agent-session 1de807c5-e476-42c9-b4f9-6357a594345f, the user replaced that design: "We could just have a simple wake up every 3 hours. If it's already awake who cares.", and chose a wake inside each agent-seat's session over a timer outside Claude that types into tmux panes: "No the internal timer is simpler and safer".

## Why

An agent-seat acts only when a message reaches it: a prompt from the user, a message from another agent-seat, or the end of a watch or a background command the agent-seat started. An agent-seat stopped by the session limit has nothing running that could end, so it waits without limit, and the user does not watch every window. Most pull requests merge fast: of the 306 merged from 2026-09-29 to 2026-10-07, 184 were open for under half an hour, and the median was 20 minutes (`gh pr list --state merged --search "merged:2026-09-29..2026-10-07"`, measured 2026-10-09). A pull request whose author sleeps through a reset waits until the user notices.

## Evidence

merge-lane-2 read the authors' transcripts of the slowest recent pull requests on 2026-10-08 (minutes, entry "Item 3 follow-up"). The times below are from GitHub.

- [A cold-read-record shipment prints shipped: only when the store holds its own files](https://github.com/nedschorus/nedschorus/pull/912), open 21 hours (2026-10-02T00:11Z to 21:33Z). The author agent-seat hit its usage limit overnight and stayed idle after the limit reset until the user typed to it.
- [The sanity-check runner's stop lets agent-binaries end, and a stop that ends no cell ends the run as finished](https://github.com/nedschorus/nedschorus/pull/928), open 40 hours (2026-10-02T04:32Z to 2026-10-03T20:35Z). Its first stall: the author agent-seat hit its usage limit overnight and stayed idle after the reset until the user typed to it.

On ned-box, transcripts hold 21 session-limit messages from 2026-09-21 to 2026-10-12, the latest merge-lane-2's at 2026-10-12T04:21Z; notes in `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/wake-after-session-limit-facts-2026-10-12.md`. A prompt that arrives after the reset does resume an agent-seat: on 2026-10-16 merge-lane-2 stopped on the session limit at 06:12:58Z ("resets 12:30am (America/Los_Angeles)", 07:30Z); its hourly stall check at 06:46:45Z failed on the limit, leaving the job in place, and the one at 07:46:44Z resumed it (transcript `nedlern@ned-box:/home/nedlern/.claude/projects/-home-nedlern-agents-merge-lane-2/e1716d82-31a8-4c1c-b787-eb1c7a6c5e5a.jsonl`).

## What exists today

- **CronCreate.** A Claude Code tool that schedules a prompt in the agent's own session, recurring on a 5-field cron expression in local time. Its jobs live only in that session, nothing is written to disk, a recurring job expires after 7 days (it fires once more, then is deleted), and a job fires only while the session is idle, which an agent-seat stopped at its limit is. CronList lists the session's jobs with their ids and prompts, and CronDelete deletes one by its id. From the tools' own descriptions, read on 2026-10-18.
- **SessionStart hooks.** `.claude/settings.json` runs one SessionStart hook today, `scripts/post-compaction-session-continues-hook.py`, on the matcher `compact`; a SessionStart hook's output reaches the agent as context at the start of a session.

## Related GHIs

- The weekly limit: GHI [Switch the agent-seats to another Claude account when the current account reaches its weekly usage limit](https://github.com/nedschorus/nedschorus/issues/1201).
- GHI [Relaunch stopped agent-seats with open tasks daily](https://github.com/nedschorus/nedschorus/issues/936) relaunches an agent-seat that is not running. This GHI wakes one that is running but stopped at its limit.
- GHI [Cross-session messages between agent-seats reach stale offline Remote Control entries instead of the live agent-session](https://github.com/nedschorus/nedschorus/issues/1115) is why the wake-up is not sent as a cross-session message.
- GHI [Console text-insertion + stuck/waiting-state detection (operator tooling; captured from the comms backlog)](https://github.com/nedschorus/nedschorus/issues/27) covers detecting a stuck agent-session as a tool for the user, not an automatic trigger.

## Split out

Before the user narrowed it, this GHI also proposed nudging the author of a pull request whose change request has gone several hours without a new commit. That is now GHI [Nudge the author of a pull request whose review findings have gone unanswered for hours](https://github.com/nedschorus/nedschorus/issues/1203). An agent-seat with no work left is woken too: it answers the wake and stops, which costs little.

## Decided

1. **What wakes an agent-seat**: a recurring CronCreate job in its own session, every 3 hours, awake or not (user-ruled 2026-10-18). Its prompt, with the job's own cron expression in place of `<cron>`: "agent-seat 3-hourly wake: delete this job with CronDelete, by the id CronList shows for it, and create it again with CronCreate, cron `<cron>`, recurring, with this same prompt, so it never reaches its 7-day expiry. Then, if you have unfinished work you can do now, continue it; if you are only waiting on someone else, end the turn with no reply." A wake that fires while the account is still at its limit fails on the limit, as merge-lane-2's 06:46:45Z check did, and the next one comes 3 hours later.
2. **Where it is set up, so every agent-seat has it after any restart**: a SessionStart hook in `.claude/settings.json` with no matcher, so it runs at every start of a session (a new session after a handoff or a relaunch, a resumed one, one after `/clear`, and after compaction). It tells the agent to run CronList and, when no job's prompt begins "agent-seat 3-hourly wake", to create it with CronCreate. It gives the cron expression: every third hour, at a minute between 1 and 59, other than 30, derived from the agent-seat's name, so that the agent-seats do not all wake at once.
3. **Both machines**: the hook reaches the Mac's agent-seats when the Mac's checkout has the merged `.claude/settings.json`; the second step of this GHI checks it there.
4. **Considered and not chosen**: a timer outside Claude typing "." and Enter into each agent-seat's tmux pane; the user ruled the internal wake simpler and safer (2026-10-18).

## Deferred-decisions

- #not_in_this_run Telling the user when an agent-seat does not answer its wake. Reason: the next wake comes 3 hours later anyway; the user said "If it's already awake who cares."

## Next action

Build the SessionStart hook on ned-box, with tests that check: its output tells the agent to run CronList and create the job when none is listed; the cron expression fires every third hour at the minute derived from the agent-seat's name, never 0 or 30, and two different agent-seat names can give different minutes; the wake prompt is the one under "Decided", word for word, with that cron expression in it; and `.claude/settings.json` runs it with no matcher. Then the user asks one running agent-seat, in its own window, to run CronList; check the job is there, and record in this GHI-MD the first wake that reaches an idle agent-seat. Then check the same on the Mac.
