---
issue: "[Nudge the author of a pull request whose review findings have gone unanswered for hours](https://github.com/nedschorus/nedschorus/issues/1203)"
---

# Nudge the author of a pull request whose review findings have gone unanswered for hours

A pull request whose review asked for changes waits until its author agent-seat pushes a fix, and nothing tells that agent-seat, or the user, when the agent-seat has stopped working on the fix. This GHI builds a nudge: when a pull request has had changes requested and no new commit for several hours, a program sends its author agent-seat a short message naming the pull request and asking the agent-seat to continue. A nudge to an author that is in fact still working costs one message. Whether the nudge also brings the user a question the author is waiting on is an open point below.

This was part (b) of GHI [Wake idle agent-seats that have unfinished work, after a usage limit resets and after a change request goes unanswered](https://github.com/nedschorus/nedschorus/issues/1152), which the user approved filing on 2026-10-09 (about 17:20Z, "y") as item 7 of merge-lane-2's approval-walk merge-lane-2-waiting-on-user-walk-2026-10-07 (minutes `nedlern@ned-box:/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-waiting-on-user-walk-2026-10-07-minutes.md`, an untracked file in merge-lane-2's checkout). On 2026-10-12 the user narrowed that GHI to the 5-hour session limit, under the new title "Wake an agent-seat when its 5-hour session limit resets", and asked for this part to be its own GHI ("5 - separate issue"), in prime-intellect's agent-session bafa2657-92ad-439d-ac19-89fdad69d71e.

## Why

Most pull requests merge fast: of the 306 merged from 2026-09-29 to 2026-10-07, 184 were open for under half an hour, and the median was 20 minutes (`gh pr list --state merged --search "merged:2026-09-29..2026-10-07"`, measured 2026-10-09). A pull request whose author has stopped after a change request waits as long as the author stays stopped, and the user does not watch pull requests, so nobody notices.

## Evidence

merge-lane-2 read the authors' transcripts of the slowest recent pull requests on 2026-10-08 (the minutes above, entry "Item 3 follow-up"). The times are from GitHub.

- [The sanity-check runner's stop lets agent-binaries end, and a stop that ends no cell ends the run as finished](https://github.com/nedschorus/nedschorus/pull/928): changes were requested at 2026-10-02T19:30Z and the next commit came at 2026-10-03T20:03Z, 24.5 hours later. A subagent fixing the findings was waiting on a test result with a watch; the watch had expired, and the test result sat unread.
- [The walk and seat shippers judge a shipment by what the store holds](https://github.com/nedschorus/nedschorus/pull/918): 20 hours from changes requested at 2026-10-02T23:49Z to approval at 2026-10-03T20:01Z, a wait on the user. The author had asked the user to approve a `--help` paragraph in cold-read-research's window alone, while merge-lane-2's list of open pull requests showed the pull request as waiting on its author.

## What exists today

- **Watching pull requests.** `scripts/watch-open-pull-requests.py` polls open pull requests and prints an event when one opens or gets a new head commit. It does not report how long a change request has gone without a commit.
- **A watch that does not expire.** On 2026-10-09 merge-lane-2 replaced its 30-minute watch of open pull requests with Claude Code's Monitor tool with a background wait that has no time limit and ends only on an event. An agent-seat or subagent that waits this way cannot lose a result to an expired watch, the cause of the 24.5-hour stall above; the nudge still catches an author that stops for any other reason.
- **Sending a message to an agent-seat.** Agent-seats message each other by name with Claude Code's cross-session messaging. GHI [Cross-session messages between agent-seats reach stale offline Remote Control entries instead of the live agent-session](https://github.com/nedschorus/nedschorus/issues/1115) records that such a message can go to an old offline entry and never be read.

## Related GHIs

- GHI [Wake idle agent-seats that have unfinished work, after a usage limit resets and after a change request goes unanswered](https://github.com/nedschorus/nedschorus/issues/1152), being narrowed to waking an agent-seat stopped by its 5-hour usage limit, by typing "." and Enter into its tmux window.
- GHI [Agents put each question for the user on a page that pops up on his Mac, and hold the dialog with him there](https://github.com/nedschorus/nedschorus/issues/1186) is one way a question an author waits on could reach the user.

## What is not decided

1. **Who sends the nudge**: merge-lane-2, which already follows every open pull request, or a scheduled job.
2. **Which agent-seat is the author.** Every agent-seat pushes as the same GitHub account, so the pull request's author field does not name the agent-seat; the commits' author name (prime-intellect's commits carry `prime-intellect`) or the branch's checkout may. When no running agent-seat matches, the nudge goes to the user instead.
3. **What counts as changes requested**: a review in the state `CHANGES_REQUESTED`, not dismissed, with no later commit on the pull request.
4. **How many hours** without a commit after a change request before the nudge, and whether a second unanswered nudge goes to the user.
5. **How the nudge reaches the author**: a cross-session message, subject to the stale-entry defect above, or the route GHI 1152 takes, typing into the author agent-seat's tmux window.
6. **An author waiting on the user**: whether the nudge also brings the user a question the author is waiting on, how the program would tell that the author is waiting, and how the question would reach the user.

## Next action

Put the six points to the user. Then build the nudge with a test that feeds it a pull request with a change request older than the threshold and no later commit, and checks that it sends one nudge naming that pull request to its author agent-seat, and none for a pull request that has a newer commit.
