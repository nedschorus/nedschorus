---
issue: "[Tell the user when ned-box's claude is logged out or ned-box's subscription has run out](https://github.com/nedschorus/nedschorus/issues/337)"
---

# Tell the user when ned-box's claude is logged out or ned-box's subscription has run out

The user's plan, stated 2026-09-11: "I plan to move most for the process to nedbox, so if claude is not logged in on it, or out of subscription or down in any way I'd block and report."

## Narrowed 2026-09-30: lasting failures only

Ruled by the user's "y" to item 7 of the walk eight-deferrals-with-no-trigger-2026-09-29 (minutes: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/eight-deferrals-with-no-trigger-2026-09-29-minutes.md`), after the user said: "I don't care about transient ned-box issues, particularly if I've asked claude to reboot it." The issue stays open.

- **In scope:** the two ned-box failures that do not heal on their own: ned-box's `claude` logged out, and ned-box's subscription run out. Either failure stops every merge until the user acts, because merge-lane-2, the seat that merges pull requests, runs on ned-box.
- **Out of scope:** reboots and brief outages. ned-box rebooted at 13:02 Pacific on 2026-09-29 and came back on its own; the user does not want to hear about that kind of event.
- **The gap found while narrowing.** A program that calls `claude` on ned-box reports a logged-out `claude` — `scripts/ghi-info-ask.py` names the remedy — and the CLAUDE.md sentence recorded below then has the agent tell the user. But when the seat that stops is merge-lane-2 itself, the seat's handoff-supervisor, `nc-systems/handoff/handoff-supervisor.py`, resumes the dead session once; when that resume adds nothing to the transcript, the supervisor prints "not resuming again" on its own console on ned-box and stops. `CONSECUTIVE_RESUMES_WITHOUT_NEW_WORK_BUDGET` sets that budget at 1, and the constant's comment names "a logged-out claude" among the causes. No program then tells the user on the Mac, and no program checks ned-box's `claude` login on its own. A shared check that only box-dependent programs call would not close this gap, because nothing calls a program when merge-lane-2 itself has stopped; whoever designs the check decides what runs it.
- **What the narrowing leaves alone.** The CLAUDE.md reporting sentence recorded below is unchanged: an agent whose program reports that ned-box cannot be reached still tells the user what the program said. The narrowing limits only what the shared check detects and pushes to the user.

## The gap, from a real failure

On 2026-09-11 the `claude` login on ned-box had lapsed. Every `scripts/ghi-info-ask.py` call from the Mac failed. The ghi-write skill's fallback ladder worked as designed — local mirror, GitHub search, grep for paired documents — and the issue edit that needed the lookup went ahead correctly.

**The box being unavailable reached the user only because the agent chose to mention it in a report.** The program told the agent; nothing required the agent to tell the user. That is the gap.

## Two failures that want different answers

**ghi-info unavailable.** One advisory lookup before an issue write. The fallback answers the same question by other means, so the write stays correct. Blocking here trades a correct write for a delay and gains nothing. The ladder's rule — a failed ask never blocks a write — is right and should stay.

**The box down when the box runs the work.** No fallback exists; the work cannot happen. Blocking and reporting is not a policy choice there, it is what failure looks like. This is the case the user is planning for.

The requirement that covers both, and is stronger than either "block" or "fall back quietly": **box unavailability must reach the user every time, whether or not the particular caller had a way around it.**

## Two pieces of work

**Now, cheap.** The rule that an agent reports box unavailability to the user rather than absorbing it. Where that rule lands is a placement question and it is likely operative prose, so it wants a walk rather than a patch. **Walked and ruled 2026-09-18:** one sentence added to `CLAUDE.md`'s bullet introducing ned-box — "When a program reports that ned-box cannot be reached or that its `claude` is logged out, tell the user what it said, remedy included, even when you can work around it" — approved in the user's words, "y". Built in PR [CLAUDE.md: box unavailability reaches the user, even when it can be worked around](https://github.com/nedschorus/nedschorus/pull/486). A retry before reporting was considered and dropped: the only real failure on record is a lapsed login, which a retry cannot fix, and the user ruled that the agents "should just tell me what the problem is."

One half is already done. PR [ghi-info-ask: a failing claude's diagnosis is reported, and a logged-out box names its remedy](https://github.com/nedschorus/nedschorus/pull/316) made `ghi-info-ask.py` report the real cause of a failed ask instead of 500 characters of usage counters, and a logged-out box now names its remedy: `claude auth login` on the box, with the ssh form for running it from the Mac. Before that fix the cause sat about 1100 bytes into the output, past the cut, and the caller misattributed the failure.

**When the move starts, not before.** One shared health check that every box-dependent program calls, so unavailability is detected once and reported the same way instead of each program inventing its own story. It must distinguish the three conditions the user named: not logged in, out of subscription, and unreachable or down. **Narrowed 2026-09-30:** the check covers only the first two, the lasting failures; unreachable or down is out of scope, per the section above.

Precedent for the failure shapes: `ghi-info-ask.py` already separates ssh unreachable, box silent past a timeout, claude exited non-zero, and the authentication case. That separation is the seed of the shared check.

**Do not build the shared check speculatively.** The user said "I plan to" — the move has not started. Build it when it does. **Update 2026-09-30:** the move has started. merge-lane-2 runs on ned-box, so a lasting failure there now stops every merge, and building the narrowed check is no longer speculative. The check waits only for someone to take this issue up.

User-approved 2026-09-11 as item 7 of the cold-read-research open-items walk, as an amendment correcting a "no action needed" recommendation.

Search receipt: `gh issue list --state all --search "box unavailable health check"` and `--search "ned-box down report"` returned nothing on this matter (2026-09-11). The ghi-info ask was attempted first per the ghi-write skill and failed with the defect filed as GHI [checkout-freshness catch-up's block decision overwrites the answer of a claude -p subprocess whose output a program reads](https://github.com/nedschorus/nedschorus/issues/334).
