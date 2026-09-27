---
issue: "[Check-in timing: infrequently-updated files immediately after update; append-type logs at logical breakpoints](https://github.com/nedschorus/nedschorus/issues/25)"
---

# Check-in timing: infrequently-updated files immediately after update; append-type logs at logical breakpoints

## Ruling (boss, 2026-07-24)

Check-in through the git-gatekeeper is fast, safe, and reversible, so nothing waits without a reason. Two file classes, two timings:

- **Infrequently-updated files** — specs, docs, code, and the handoff files and read stamps (written once per session, not appended): check in **immediately after update**.
- **Append-type log files** — currently only the future mini-comms logs (companion era): check in at a **logical breakpoint** — session end or next session start — never per append, so log traffic never churns main's head.

## Where this is applied

- https://github.com/nedschorus/nedschorus/blob/main/docs/cross-project/fast-handoff-design.md — handoff files and read stamps submit through `git-gatekeeper.py check-in` immediately when written; the files reach disk first, so a failed submission never blocks a session boundary, and resubmission is always safe (a gatekeeper guarantee).
- https://github.com/nedschorus/nedschorus/blob/main/docs/cross-project/comms-bridge-spec.md — log rotation happens when a handoff is written.

## Destination and close condition

A CLAUDE.md line was the destination until the step-2 admission (2026-08-06) declined it — the floor keeps only lines unique to the project or the boss's preferred working methods, and this rule's delivery moves to code: the git-gatekeeper can enforce the timing and stamp session ids mechanically when built. This issue closes when that enforcement lands, or if the rule is superseded.

Placement note: briefly recorded in founding plan § Standing decisions, then re-homed here same day (boss: Standing decisions cover the boot-up phase only; post-boot needs are GHIs — short ones issue-only, long ones MD-GHI pairs).

—
Session: 23789ca5-e422-422a-bb1d-f03616746770 (new-vp)
