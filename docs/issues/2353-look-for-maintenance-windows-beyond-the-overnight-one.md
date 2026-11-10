---
issue: "[Look for maintenance windows beyond the overnight one when CPU, memory and token use are all low](https://github.com/nedschorus/nedschorus/issues/2353)"
---

# Look for maintenance windows beyond the overnight one when CPU, memory and token use are all low

A later idea, not ready to build: besides the overnight maintenance window, open a maintenance window for the maintenance-jobs of GHI 1058 at other times, such as hours of the day when the user is away from his computer, whenever ned-box's CPU use, its memory use and the token use of all agent-seats are all three low enough. This GHI records the idea and the user's words; it decides no design.

## Why

The maintenance-jobs of GHI [Regular maintenance: the list of maintenance jobs, how often each runs, and how each reaches the user](https://github.com/nedschorus/nedschorus/issues/1058) run overnight. The user approved that on 2026-10-30, a change not yet written into GHI 1058's GHI-MD, in items 9.2 and 9.3.1 of approval-walk prime-intellect-handed-over-items-2026-10-29. Item 9.2 moves the nightly full test run of main to 00:00 and starts maintenance when that test run ends. Item 9.3.1 runs one maintenance-job, the refresh of designs and overviews, at one document every 2 hours, only between 00:00 and 08:00 Pacific while the 5-hour usage limit lasts, and around the clock after the limit ends. The reason for night is the 5-hour usage limit: maintenance run while the user works would use up the limit he needs for his own work. Daytime hours when he is away and activity is low are left unused.

The walk-document is `nedlern@ned-box:/home/nedlern/agents/prime-intellect/docs/walk/prime-intellect-handed-over-items-2026-10-29.md` (items 9.2 and 9.3.1), and its walk-minutes are `nedlern@ned-box:/home/nedlern/agents/prime-intellect/docs/walk/prime-intellect-handed-over-items-2026-10-29-minutes.md`, in prime-intellect's checkout until the walk closes and they are shipped to the log-store.

## The user's words

The user, on 2026-10-30 at 20:21 Pacific, added these words to his approval of item 9.3.1, in prime-intellect's agent-session ba7934a0-5582-4108-a133-88383dd60b06, whose transcript is `nedlern@ned-box:/home/nedlern/.claude/projects/-home-nedlern-agents-prime-intellect/ba7934a0-5582-4108-a133-88383dd60b06.jsonl`; the line of those walk-minutes that starts "item 9.3.1 of 24: the user's rider" records them abridged:

"I'm often away from my computer for hours at a time during the day, and it seemed like that would be pretty easy to detect. I don't think we have a away from keyboard detector. And it's not just that, it's usually at some point activity really slows to a trickle, at which point we could do more maintenance stuff like this. But it seems like this is over-engineering, that we should just let it run 24 hours a day, unless we actually do have capacity problems, and we'll fix them later. So maybe that's the right solution. Though we're pretty close. All right, just keep it as it is, as a overnight maintenance thing. And I think it would be okay to add a GHI to say at some point we can look for windows, maintenance windows beyond sleep time based on minimal token burn or memory. I mean, there's CPU, there's memory and token burn, and at some point when they all get safe zone, we could start doing maintenance. So we can make a GHI for that."

His ruling in these words: maintenance stays overnight, as item 9.3.1 approved, and this GHI is filed for windows beyond the night. What "we're pretty close" refers to, he did not say.

## What bears on it

- **Running around the clock may make this unneeded.** The user said that letting maintenance run 24 hours a day may be the simpler answer, unless capacity turns out to be a problem. Item 9.3.1 already moves the design and overview refresh to around the clock once the 5-hour limit ends.
- **The 5-hour limit may go away.** In item 9.2 the user said Anthropic has written that the 5-hour usage limit is going away. If it does, the main reason for keeping maintenance to the night goes with it, and the user may then have this GHI closed as not planned.
- **Pieces that exist on main today.** `scripts/run-all-test-suites.py` already starts a test suite only while ned-box's CPU use, averaged over 5 seconds, is under 55% and available memory is above 10 GB, as GHI [Each test suite on ned-box runs in its own throwaway test environment, and suites start by free CPU and memory instead of waiting for a machine-wide lock](https://github.com/nedschorus/nedschorus/issues/1374) decided; a window opened by CPU and memory would reuse that way of measuring them rather than build another; whether it would also use the same thresholds is left to the design. `scripts/session-statusline-command.py` reads the `five_hour` and `seven_day` entries of the `rate_limits` that Claude Code hands the status line, which is one place token use is already read.
- **No away-from-keyboard detector exists.** Search receipt: `git grep -n -i "away from keyboard\|afk\|user is away\|HIDIdleTime"` over `scripts`, `nc-systems`, `.claude` and `docs/issues` on origin/main, 2026-11-01, found none.
- **Related, not the same.** GHI [Wake an agent-seat when its 5-hour session limit resets](https://github.com/nedschorus/nedschorus/issues/1152) detects an idle agent-seat to wake it, not a quiet machine to run maintenance in. GHI [ned-box runs out of reclaimable memory, so systemd-oomd kills agent-seats and Bash-guard replay readings time out](https://github.com/nedschorus/nedschorus/issues/1834) concerns the opposite condition, a machine under too much load.

## Questions left to the design

Left open on purpose, for the design if the user asks for one:

- What counts as low for each of the three measures, and whether token use is read from the 5-hour limit, the 7-day limit or something else.
- Whether a window needs to know the user is away, or whether low load alone is enough; the user named both his absence and activity slowing "to a trickle".
- How maintenance run in the daytime avoids using up the 5-hour limit the user needs when he comes back.
- What a running maintenance-job does when load rises during a window: stop, finish, or hand back.
- Which maintenance-jobs may run in such a window.

## Next action

None until one of these happens: maintenance capacity becomes a problem, because the overnight window is too short for the maintenance-jobs it holds, such as maintenance-jobs left unfinished by morning; the 5-hour usage limit ends; or the user asks for this. Whichever agent sees one happen brings the user the evidence and asks whether to design load-based maintenance windows. When the 5-hour limit has ended, ask him first whether maintenance should simply run around the clock instead, in which case this GHI closes as not planned.
