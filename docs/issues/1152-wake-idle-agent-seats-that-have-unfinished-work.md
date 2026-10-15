---
issue: "[Wake an agent-seat when its 5-hour session limit resets](https://github.com/nedschorus/nedschorus/issues/1152)"
---

# Wake an agent-seat when its 5-hour session limit resets

An agent-seat that hits Claude's 5-hour session limit stops mid-work and stays idle after the limit resets, until someone types to it. This GHI builds a waker: the agent-seat's own handoff-supervisor, which runs outside Claude Code in the agent-seat's tmux session, sees the session-limit message in the agent-seat's transcript, waits until the reset time the message gives, and types "." and Enter into that agent-seat's prompt so that it continues. The handoff-supervisor already checks the agent-seat every 2 seconds in a loop beside the running Claude Code process, so it can read the transcript in that loop, and it can address its own pane through the `TMUX` and `TMUX_PANE` variables it runs with. The waker types whatever is already in the prompt's line: an agent-seat at its limit is frozen, and a wake-up that waits for an empty line could wait for hours. ned-box's agent-seats come first; the Mac's follow in a second step of this GHI, since both machines need it. It sends nothing when the agent-seat has written anything to its transcript since the limit message, because then someone has already woken it or it is working; and nothing when the agent-seat is no longer running. A reset time that has already passed when the waker reads the message, such as after the waker restarts, is acted on at once.

The user approved filing this GHI on 2026-10-09 (about 17:20Z, "y") as item 7 of merge-lane-2's approval-walk merge-lane-2-waiting-on-user-walk-2026-10-07; the walk-document is `nedlern@ned-box:/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-waiting-on-user-walk-2026-10-07.md` and its minutes `nedlern@ned-box:/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-waiting-on-user-walk-2026-10-07-minutes.md`, both untracked files in merge-lane-2's checkout. On 2026-10-12 the user narrowed it to the 5-hour limit, in prime-intellect's agent-session bafa2657-92ad-439d-ac19-89fdad69d71e: "Agents have 3 limits - context, which we have a solution for, a 5 hour window, which the 'waker' just needs to watch or see that "You've hit your session limit · resets 1am (America/Los_Angeles)' which I guess is visible in the jsonl, and then send that agent a "." to wake them at the appropriate time. ... But if the agent hits the weekly limit, that is a different problem, one that needs its own GHI." The user then ruled on the open points (same agent-session, 2026-10-12), numbered as below under "Decided", with 5 being the split under "Split out": "1 - y, 2 - these agents are frozen. It they need a . and enter to push the . If there is other stuff in the line buffer I don't care - as long as we send (that is push enter) something. Don't wait or we'll be waiting for hours. 3 - we need both fixed, but you can do just one machine first. 4 - 4 - Y, 5 - 5 - separate issue."

## Why

An agent-seat acts only when a message reaches it: a prompt from the user, a message from another agent-seat, or the end of a watch or a background command the agent-seat started. An agent-seat stopped by the session limit has nothing running that could end, so it waits without limit, and the user does not watch every window. Most pull requests merge fast: of the 306 merged from 2026-09-29 to 2026-10-07, 184 were open for under half an hour, and the median was 20 minutes (`gh pr list --state merged --search "merged:2026-09-29..2026-10-07"`, measured 2026-10-09). A pull request whose author sleeps through a reset waits until the user notices.

## Evidence

merge-lane-2 read the authors' transcripts of the slowest recent pull requests on 2026-10-08 (minutes, entry "Item 3 follow-up"). The times below are from GitHub.

- [A cold-read-record shipment prints shipped: only when the store holds its own files](https://github.com/nedschorus/nedschorus/pull/912), open 21 hours (2026-10-02T00:11Z to 21:33Z). The author agent-seat hit its usage limit overnight and stayed idle after the limit reset until the user typed to it.
- [The sanity-check runner's stop lets agent-binaries end, and a stop that ends no cell ends the run as finished](https://github.com/nedschorus/nedschorus/pull/928), open 40 hours (2026-10-02T04:32Z to 2026-10-03T20:35Z). Its first stall: the author agent-seat hit its usage limit overnight and stayed idle after the reset until the user typed to it.

On ned-box, transcripts hold 21 session-limit messages from 2026-09-21 to 2026-10-12, the latest merge-lane-2's at 2026-10-12T04:21Z; notes in `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/wake-after-session-limit-facts-2026-10-12.md`.

## What exists today

- **The session-limit message.** Claude Code writes it into the agent-session's transcript, `~/.claude/projects/<project directory>/<session id>.jsonl`, as a record with `"type": "assistant"`, `"isApiErrorMessage": true` and the text `You've hit your session limit · resets 1am (America/Los_Angeles)`; the reset is a clock time, sometimes with minutes (`resets 12:10am`), without a date, in the zone the message names, America/Los_Angeles, while the record's `timestamp` is in UTC; the reset is the next such time in that zone after the timestamp. The weekly limit writes a different text, `You've hit your weekly limit · resets Oct 13, 9pm (America/Los_Angeles)`, which this GHI does not act on.
- **The exact reset time.** Claude Code passes the status line `rate_limits.five_hour.resets_at`; `scripts/session-statusline-command.py` shows it as a countdown and saves nothing to disk, unless `NEDSCHORUS_STATUSLINE_PAYLOAD_CAPTURE` is set, which nothing sets. The transcript's clock time is enough to wake an agent-seat within a minute.
- **Where each agent-seat runs.** On ned-box each agent-seat runs Claude Code in a tmux session on a tmux server of its own, named for the agent-seat (`tmux -L <agent-seat> list-sessions`). On 2026-10-12 every one had a client attached: the user's terminal.
- **Typing into an agent-seat.** `scripts/synthetic-keystroke-guard-hook.py`, a hook on agents' shell commands, refuses an agent's `tmux send-keys` into a session with an attached client, because keystrokes would interleave with the typing of whoever is attached. The hook does not bind a program that is not an agent, such as the waker; the user accepted the interleaving its reason warns of, because a frozen agent-seat needs the Enter whatever is in its line. `scripts/launch-claude-ubuntu` creates each agent-seat's tmux session, and inside it runs the handoff-supervisor (`nc-systems/handoff/handoff-supervisor.py`), which launches Claude Code.

## Related GHIs

- The weekly limit: GHI [Switch the agent-seats to another Claude account when the current account reaches its weekly usage limit](https://github.com/nedschorus/nedschorus/issues/1201).
- GHI [Relaunch stopped agent-seats with open tasks daily](https://github.com/nedschorus/nedschorus/issues/936) relaunches an agent-seat that is not running. This GHI wakes one that is running but stopped at its limit.
- GHI [Cross-session messages between agent-seats reach stale offline Remote Control entries instead of the live agent-session](https://github.com/nedschorus/nedschorus/issues/1115) is why the wake-up is not sent as a cross-session message.
- GHI [Console text-insertion + stuck/waiting-state detection (operator tooling; captured from the comms backlog)](https://github.com/nedschorus/nedschorus/issues/27) covers detecting a stuck agent-session as a tool for the user, not an automatic trigger.

## Split out

Before the user narrowed it, this GHI also proposed nudging the author of a pull request whose change request has gone several hours without a new commit. That is now GHI [Nudge the author of a pull request whose review findings have gone unanswered for hours](https://github.com/nedschorus/nedschorus/issues/1203). An agent-seat with no work left is woken too: it answers the "." and stops, which costs little.

## Decided

1. **Who sends the "."**: the agent-seat's own handoff-supervisor, which runs inside the agent-seat's tmux session, so no lookup by name can reach the wrong agent-session.
2. **What is already in the prompt's line** does not stop the waker: it types "." and Enter at the reset time without checking or waiting.
3. **Both machines**: ned-box first, then the Mac's agent-seats as a second step of this GHI.
4. **When a "." does not take**, because nothing new appears in the transcript within 5 minutes, the waker types it once more and then tells the user. A new session-limit message after the "." is not a failure: the waker waits for that message's reset time instead.

## Deferred-decisions

- How the waker tells the user that a second "." did not take; GHI [Agents put each question for the user on a page that pops up on his Mac, and hold the dialog with him there](https://github.com/nedschorus/nedschorus/issues/1186) is one candidate.

## Next action

Build the waker on ned-box with a test that feeds it a transcript record carrying the session-limit message and checks that it sends "." and Enter to the right tmux pane at the reset time, one that checks it sends nothing when the transcript has moved on, one that checks it ignores the weekly-limit message, one that checks a reset time already past is acted on at once, and one that checks a second "." after 5 minutes without new transcript activity. Then the Mac's agent-seats.
