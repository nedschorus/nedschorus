---
issue: "[Wake idle agent-seats that have unfinished work, after a usage limit resets and after a change request goes unanswered](https://github.com/nedschorus/nedschorus/issues/1152)"
---

# Wake idle agent-seats that have unfinished work, after a usage limit resets and after a change request goes unanswered

Some pull requests take a day or more to merge because the agent-seat that must act next has gone idle and nothing wakes it. Two wake-ups would cover two of the three causes of stalls found so far: (a) after a usage limit resets, send each idle agent-seat that has unfinished work a short wake-up message; (b) when a pull request has had changes requested and no new commit for several hours, send its author a nudge.

The user approved filing this GHI on 2026-10-09 (about 17:20Z, "y") as item 7 of merge-lane-2's approval-walk merge-lane-2-waiting-on-user-walk-2026-10-07. The walk-document is `nedlern@ned-box:/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-waiting-on-user-walk-2026-10-07.md` and its minutes are `nedlern@ned-box:/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-waiting-on-user-walk-2026-10-07-minutes.md`; both are untracked files in merge-lane-2's checkout.

## Why

Most pull requests merge fast: of the 306 merged from 2026-09-29 to 2026-10-07, 184 were open for under half an hour, and the median was 20 minutes (`gh pr list --state merged --search "merged:2026-09-29..2026-10-07"`, measured 2026-10-09). A pull request whose author sits idle waits as long as the idleness lasts, and the user does not watch pull requests, so nobody notices. An agent-seat acts only when a message reaches it: a prompt from the user, a message from another agent-seat, or the end of a watch or a background command the agent-seat started. When none comes, the agent-seat waits without limit.

## Evidence

merge-lane-2 read the authors' transcripts of the three slowest recent pull requests on 2026-10-08 (minutes, entry "Item 3 follow-up"). The commit and review times below are from GitHub.

- [A cold-read-record shipment prints shipped: only when the store holds its own files](https://github.com/nedschorus/nedschorus/pull/912), open 21 hours (2026-10-02T00:11Z to 21:33Z). The author agent-seat hit its usage limit overnight and stayed idle after the limit reset until the user typed to it. Fix (a) covers this stall.
- [The sanity-check runner's stop lets agent-binaries end, and a stop that ends no cell ends the run as finished](https://github.com/nedschorus/nedschorus/pull/928), open 40 hours (2026-10-02T04:32Z to 2026-10-03T20:35Z), with two stalls:
  - First, the author agent-seat hit its usage limit overnight and stayed idle after the reset until the user typed to it. Fix (a) covers this stall.
  - Second, the longest gap, 24.5 hours: changes were requested at 2026-10-02T19:30Z and the next commit came at 2026-10-03T20:03Z. A subagent fixing the findings was waiting on a test result with a watch; the watch had expired, and the test result sat unread. Fix (b) would have caught this stall; the background wait described under "A watch that does not expire" below removes this particular cause for an agent-seat or subagent that adopts that wait, and (b) remains the catch for an author that stalls for any reason.
- [The walk and seat shippers judge a shipment by what the store holds](https://github.com/nedschorus/nedschorus/pull/918), open 41 hours (2026-10-02T03:10Z to 2026-10-03T20:01Z). Its 20-hour gap, from changes requested at 2026-10-02T23:49Z to approval at 2026-10-03T20:01Z, was a wait on the user: the author asked him to approve a `--help` paragraph in cold-read-research's window alone, while merge-lane-2's list of open pull requests showed the pull request as waiting on its author. The change request stood (GitHub shows it not dismissed), so (b) would have nudged the author; but the author was waiting on the user, not idle, and the cause, a question to the user asked in one window only, is not what either fix addresses. This entry is here so that a reader does not count the walk and seat shippers' pull request as evidence for either fix.

Logouts of `claude` cost these pull requests about 3 minutes in all.

## What exists today

- **Knowing when a usage limit resets.** Claude Code passes the status line a `rate_limits` object whose windows carry `resets_at`; `scripts/session-statusline-command.py` reads it to show a countdown. Nothing else in the repository reads the reset time (search: `grep -rliE 'usage.limit|rate.limit|limit reset|resets at' --include=*.py nc-systems scripts`, 2026-10-09; besides the status line and its test, the hits mention GitHub's API rate limit or, in `scripts/sanity-check-attacks.py`, detect that a run hit a usage limit, without reading when the limit resets).
- **Knowing what an agent-seat has left to do.** `scripts/seat-task-list-read.py --seats` prints each agent-seat's open task count.
- **Watching pull requests.** `scripts/watch-open-pull-requests.py` polls open pull requests and prints an event when one opens or gets a new head commit. It does not report how long a change request has gone without a commit.
- **Sending a message to an agent-seat.** Agent-seats message each other by name with Claude Code's cross-session messaging. GHI [Cross-session messages between agent-seats reach stale offline Remote Control entries instead of the live agent-session](https://github.com/nedschorus/nedschorus/issues/1115) records that such a message can go to an old offline entry and never be read; a wake-up sender must reach the live agent-session, or the wake-up is lost the same way.
- **A watch that does not expire.** On 2026-10-09 merge-lane-2 replaced its 30-minute Monitor watch of open pull requests with a background wait that has no time limit and ends only on an event. Any agent-seat or subagent that waits this way, instead of with a watch that has a time limit, cannot lose a result to an expired watch, the cause of the 24.5-hour stall of the sanity-check runner's pull request above. This prevents that one cause; (b) still catches an author that stalls for any other reason.

## Related GHIs

- GHI [Relaunch stopped agent-seats with open tasks daily](https://github.com/nedschorus/nedschorus/issues/936) relaunches an agent-seat that is not running. The GHI this file describes wakes an agent-seat that is running but idle, at the moment its work can resume, not once a day.
- GHI [Console text-insertion + stuck/waiting-state detection (operator tooling; captured from the comms backlog)](https://github.com/nedschorus/nedschorus/issues/27) covers detecting a stuck agent-session as a tool for the user, not an automatic trigger.
- GHI [Tasks raise themselves when their due time passes or their prerequisite is met](https://github.com/nedschorus/nedschorus/issues/940) raises a task when its time comes; the reset of a usage limit is one such time.

## What is not decided

1. **Who sends the wake-up.** The handoff-supervisor runs beside every agent-session and could send (a) itself; a scheduled job, or merge-lane-2, which already follows every open pull request, could send (b).
2. **What counts as idle with unfinished work** for (a): open tasks on the agent-seat's task list, an open pull request the agent-seat authored, or both; and how long after the reset to wait.
3. **How many hours** without a commit after a change request before (b) fires, and whether (b) repeats or tells the user after a second nudge goes unanswered.
4. **How the wake-up reaches a running agent-session.** Cross-session messaging is one way, subject to the stale-entry defect recorded under GHI [Cross-session messages between agent-seats reach stale offline Remote Control entries instead of the live agent-session](https://github.com/nedschorus/nedschorus/issues/1115); typing into the agent-session's tmux pane is another, and `scripts/synthetic-keystroke-guard-hook.py` decides which keystroke injections an agent may run. Recommended in the approval-walk on this GHI-MD, to be confirmed with the user before building: the agent-seat's own handoff-supervisor types the wake-up into the pane it owns, so no lookup by name can reach the wrong agent-session; if the typed wake-up does not take, the handoff-supervisor restarts the agent resuming its conversation, with the wake-up as its first prompt.
5. **How the sender learns that the limit has reset.** All agent-seats share one Claude account, so the sender tests it: every 30 minutes or so it makes one minimal call with a small, fast model. Success means the limit has probably reset, and an agent-seat quiet at its prompt since the limit was hit is woken. A wake-up that comes too soon does no harm: the agent-seat stops at the limit again, and the sender tries again on its next test. A connection failure means no connectivity, reported as such and not treated as a limit.
6. **An author waiting on the user.** When the author of a stalled pull request is waiting on a question it put to the user, (b) both nudges the author and brings that question to the user directly, quoting it and naming the pull request and the agent-seat that asked. How the question reaches the user, for example a message in the window of the agent-seat he is working with, or a window opened on his Mac, is for the builder to propose.
7. **What the message says.** One short line naming the reason, such as the usage limit having reset or the pull request and its change request, and asking the agent-seat to continue its work.

## Next action

Put points 1 to 7 to the user. Then build (a) and (b) with a test that starts an idle agent-session, sends the wake-up by the way point 4 chooses, and checks that the agent-session's transcript shows the message arrived.
