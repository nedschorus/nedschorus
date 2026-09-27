---
issue: "[Box unavailability must always reach the user, and wants one shared health check when the process moves to ned-box](https://github.com/nedschorus/nedschorus/issues/337)"
---

# Box unavailability must always reach the user, and wants one shared health check when the process moves to ned-box

The user's plan, stated 2026-09-11: "I plan to move most for the process to nedbox, so if claude is not logged in on it, or out of subscription or down in any way I'd block and report."

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

**When the move starts, not before.** One shared health check that every box-dependent program calls, so unavailability is detected once and reported the same way instead of each program inventing its own story. It must distinguish the three conditions the user named: not logged in, out of subscription, and unreachable or down.

Precedent for the failure shapes: `ghi-info-ask.py` already separates ssh unreachable, box silent past a timeout, claude exited non-zero, and the authentication case. That separation is the seed of the shared check.

**Do not build the shared check speculatively.** The user said "I plan to" — the move has not started. Build it when it does.

User-approved 2026-09-11 as item 7 of the cold-read-research open-items walk, as an amendment correcting a "no action needed" recommendation.

Search receipt: `gh issue list --state all --search "box unavailable health check"` and `--search "ned-box down report"` returned nothing on this matter (2026-09-11). The ghi-info ask was attempted first per the ghi-write skill and failed with the defect filed as GHI [checkout-freshness catch-up's block decision overwrites the answer of a claude -p subprocess whose output a program reads](https://github.com/nedschorus/nedschorus/issues/334).
