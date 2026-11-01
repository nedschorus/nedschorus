---
issue: "[Wake an agent-seat when its 5-hour session limit resets](https://github.com/nedschorus/nedschorus/issues/1152)"
kind: design
---

# Wake an agent-seat when its 5-hour session limit resets

An agent-seat that hits Claude's 5-hour session limit stops mid-work and stays idle after the limit resets, until someone types to it. The idle sweep of GHI [Tasks raise themselves when their due time passes or their prerequisite is met](https://github.com/nedschorus/nedschorus/issues/940), § The idle sweep, wakes it: a scheduled job on ned-box finds, every minute, the agent-seats that are idle; when an agent-seat's last turn ended on Claude's session-limit message, which names the reset time, a headless agent-session sends it one short cross-session message, with Claude Code's SendMessage tool, a few minutes after that time, and the idle sweep's other steps start over if it is still idle 5 minutes later. Nothing types into a terminal or a tmux window. The idle sweep is built under GHI 940; this GHI records the session-limit case it must handle. ned-box's agent-seats come first; the Mac's need a job running on the Mac.

The user approved filing this GHI on 2026-10-09 (about 17:20Z, "y") as item 7 of merge-lane-2's approval-walk merge-lane-2-waiting-on-user-walk-2026-10-07; the walk-document is `nedlern@ned-box:/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-waiting-on-user-walk-2026-10-07.md` and its minutes `nedlern@ned-box:/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-waiting-on-user-walk-2026-10-07-minutes.md`, both untracked files in merge-lane-2's checkout. On 2026-10-12 the user narrowed it to the 5-hour limit, in prime-intellect's agent-session bafa2657-92ad-439d-ac19-89fdad69d71e: "Agents have 3 limits - context, which we have a solution for, a 5 hour window, which the 'waker' just needs to watch or see that "You've hit your session limit · resets 1am (America/Los_Angeles)' which I guess is visible in the jsonl, and then send that agent a "." to wake them at the appropriate time. ... But if the agent hits the weekly limit, that is a different problem, one that needs its own GHI." The user then ruled on the open points (same agent-session, 2026-10-12), numbered 1 to 4 in the earlier version of this GHI-MD, with 5 being the split under "Split out": "1 - y, 2 - these agents are frozen. It they need a . and enter to push the . If there is other stuff in the line buffer I don't care - as long as we send (that is push enter) something. Don't wait or we'll be waiting for hours. 3 - we need both fixed, but you can do just one machine first. 4 - 4 - Y, 5 - 5 - separate issue." On 2026-10-18, in prime-intellect's agent-session 1de807c5-e476-42c9-b4f9-6357a594345f, the user replaced that design: "We could just have a simple wake up every 3 hours. If it's already awake who cares.", and chose a wake inside each agent-seat's session over a timer outside Claude that types into tmux panes: "No the internal timer is simpler and safer". On 2026-10-30 the user approved item 1 of reboot-test's approval-walk reboot-test-idle-agent-seat-wake-route-2026-10-30 (walk-minutes: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/reboot-test-idle-agent-seat-wake-route-2026-10-30-minutes.md`), which replaced the in-session wake, never built, with GHI 940's idle sweep.

## Why

An agent-seat acts only when a message reaches it: a prompt from the user, a message from another agent-seat, or the end of a watch or a background command the agent-seat started. An agent-seat stopped by the session limit has nothing running that could end, so it waits without limit, and the user does not watch every window. Most pull requests merge fast: of the 306 merged from 2026-09-29 to 2026-10-07, 184 were open for under half an hour, and the median was 20 minutes (`gh pr list --state merged --search "merged:2026-09-29..2026-10-07"`, measured 2026-10-09). A pull request whose author sleeps through a reset waits until the user notices.

## Evidence

merge-lane-2 read the authors' transcripts of the slowest recent pull requests on 2026-10-08 (minutes, entry "Item 3 follow-up"). The times below are from GitHub.

- [A cold-read-record shipment prints shipped: only when the store holds its own files](https://github.com/nedschorus/nedschorus/pull/912), open 21 hours (2026-10-02T00:11Z to 21:33Z). The author agent-seat hit its usage limit overnight and stayed idle after the limit reset until the user typed to it.
- [The sanity-check runner's stop lets agent-binaries end, and a stop that ends no cell ends the run as finished](https://github.com/nedschorus/nedschorus/pull/928), open 40 hours (2026-10-02T04:32Z to 2026-10-03T20:35Z). Its first stall: the author agent-seat hit its usage limit overnight and stayed idle after the reset until the user typed to it.

On ned-box, transcripts hold 21 session-limit messages from 2026-09-21 to 2026-10-12, the latest merge-lane-2's at 2026-10-12T04:21Z; notes in `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/wake-after-session-limit-facts-2026-10-12.md`. A prompt that arrives after the reset does resume an agent-seat: on 2026-10-16 merge-lane-2 stopped on the session limit at 06:12:58Z ("resets 12:30am (America/Los_Angeles)", 07:30Z); its hourly stall check at 06:46:45Z failed on the limit, leaving the job in place, and the one at 07:46:44Z resumed it (transcript `nedlern@ned-box:/home/nedlern/.claude/projects/-home-nedlern-agents-merge-lane-2/e1716d82-31a8-4c1c-b787-eb1c7a6c5e5a.jsonl`).

## Related GHIs

- The weekly limit: GHI [Switch the agent-seats to another Claude account when the current account reaches its weekly usage limit](https://github.com/nedschorus/nedschorus/issues/1201).
- GHI [Relaunch stopped agent-seats with open tasks daily](https://github.com/nedschorus/nedschorus/issues/936) relaunches an agent-seat that is not running. This GHI wakes one that is running but stopped at its limit.
- GHI [Cross-session messages between agent-seats reach stale offline Remote Control entries instead of the live agent-session](https://github.com/nedschorus/nedschorus/issues/1115) records that a cross-session message can reach an old offline Remote Control entry instead of the running agent-session. GHI 940's idle sweep therefore picks the entry ListAgents shows on this machine, by its name and its ref, such as `prime-intellect [2c0a77]`, looks a minute later for the message in the agent-seat's transcript, and tells the user when it is not there.
- GHI [Console text-insertion + stuck/waiting-state detection (operator tooling; captured from the comms backlog)](https://github.com/nedschorus/nedschorus/issues/27) covers detecting a stuck agent-session as a tool for the user, not an automatic trigger.

## Split out

Before the user narrowed it, this GHI also proposed nudging the author of a pull request whose change request has gone several hours without a new commit. That is now GHI [Nudge the author of a pull request whose review findings have gone unanswered for hours](https://github.com/nedschorus/nedschorus/issues/1203). The 3-hourly wake that would have woken every agent-seat, including one with no work left, is not built; GHI 940's idle sweep decides which agent-seats it wakes.

## Decided

1. **What wakes an agent-seat**: the idle sweep of GHI 940, which also wakes an agent-seat stopped at its session limit, just after the reset (user-ruled 2026-10-30). The 3-hourly in-session job of 2026-10-18 is not built.
2. **How the wake is sent after a session limit**: as GHI 940 § The idle sweep says, under "a session limit": a few minutes after the reset time the session-limit message names, the headless agent-session sends one short message, and is asked for no judgment; if the agent-seat is still idle 5 minutes later, the idle sweep's steps start over, which end in telling the user. Nothing is set up inside an agent-seat's session, so a restart needs nothing redone.
3. **Both machines**: cross-session messages stay on one machine, so the Mac's agent-seats need the job running on the Mac, as GHI 940 § How the message reaches the agent-seat says; ned-box comes first.
4. **Considered and not chosen**: a timer outside Claude typing "." and Enter into each agent-seat's tmux pane, which the user ruled less simple and safe than a wake inside the session (2026-10-18); and that wake inside the session, a recurring CronCreate job set up by a SessionStart hook, which the idle sweep replaced (2026-10-30).

## Deferred-decisions

- None of its own: what the idle sweep has still to settle is listed in GHI 940 § Deferred-decisions.

## Next action

Build GHI 940's idle sweep, under GHI 940, with its session-limit case. A prompt from a job inside the session resumed an agent-seat after a reset (§ Evidence), but no cross-session message has yet been tested in that case. When the job is built, test whether a cross-session message sent after a reset resumes an agent-seat stopped at its session limit, as GHI 940 says, and record in this GHI-MD the first such wake, on ned-box and then on the Mac.
