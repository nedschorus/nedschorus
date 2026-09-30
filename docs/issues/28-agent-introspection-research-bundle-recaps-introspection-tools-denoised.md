---
issue: "[Agent-introspection research bundle: recaps, introspection tools, denoised artifacts, monitoring test method, task-list visibility](https://github.com/nedschorus/nedschorus/issues/28)"
---

# Agent-introspection research bundle: recaps, introspection tools, denoised artifacts, monitoring test method, task-list visibility

## What this captures

The agent-introspection research bundle — task-shaped items dispersed from pair GHI [Working ideas and research backlog — capture pair (Decided / Candidate / Research / Reference)](https://github.com/nedschorus/nedschorus/issues/10)'s status/monitoring backlog (walk item 17 cluster 2, boss-ruled 2026-07-25: task-shaped work gets a GHI, never a doc-only capture — docs are not attention surfaces). Captured, not scheduled; lean bundle rather than five micro-issues.

1. Are session recaps customizable?
2. Evaluate small agent-introspection tools (what exists; smallest useful adoption).
3. Is a denoised introspection artifact easier to back up and use than raw session logs?
4. The controlled-test-project method: tune any future monitoring against a deliberately instrumented toy project before pointing it at real work.
5. Task-list visibility: a method for the boss to SEE and review agents' harness task lists — until this exists the boss is blind to them, which is why nothing may live only there (same ruling).

   **Asked for as a build, 2026-09-21.** The user asked for "a task viewer tool" while working with the reboot-test seat. What made it concrete: that one session created eight tasks in an afternoon — user rulings, a defect deferred to its own topic, three cross-seat announcements owed — and none of them was visible to him without attaching to that seat's terminal. Tasks are where a seat's rulings and owed work survive a session handoff, so the blindness this item names is not cosmetic: it is over the fleet's own working memory.

   What it has to do, as the ask stands: show the task lists of every live seat in one place, per seat, without attaching to each terminal. Whether it also writes — closing or adding a task — is not settled and was not asked for.

   Not scheduled here. This bundle captures; a build gets its own GHI with its own closure, per the close condition below.

## Relations

- The spy/observer design consumes several of these answers: https://github.com/nedschorus/nedschorus/issues/26
- Operator tooling sibling (console insertion, stuck-state detection): https://github.com/nedschorus/nedschorus/issues/27

## Close condition

Closes when the items are individually answered/absorbed by builds, or superseded.

## Outcome

Closed as not planned on 2026-09-29, by the user's "y" to item 1 of the walk eight-deferrals-with-no-trigger-2026-09-29 (minutes: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/eight-deferrals-with-no-trigger-2026-09-29-minutes.md`). Not planned rather than completed, because only item 5 was built.

- Item 5, task-list visibility, was the one item ever asked for as a build, and it is built: the task viewer `scripts/seat-task-list-read.py`, on main since 2026-09-21. PR [Fold every seat, on both machines, into the one task viewer](https://github.com/nedschorus/nedschorus/pull/646), merged 2026-09-22, extended the task viewer to every seat on both machines. The task viewer only reads task lists; nobody asked for it to write.
- Item 3 was not studied as asked. The nearest thing built is `scripts/handoff-extract-conversation.py`, which extracts the two-voice dialog from a session transcript at every handoff.
- Items 1, 2 and 4 had no work after this issue was filed, and nothing waits on any of them.

This bundle only captured its items, and a build gets its own GHI. So whoever wants item 1, 2, 3 or 4 files a new issue for that item alone.

—
Session: 23789ca5-e422-422a-bb1d-f03616746770 (new-vp)
