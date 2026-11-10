---
issue: "[The handoff-supervisor writes the memory review's started mark when it puts the memory-review reminder into the initial-agent-instructions](https://github.com/nedschorus/nedschorus/issues/2545)"
---

# The handoff-supervisor writes the memory review's started mark when it puts the memory-review reminder into the initial-agent-instructions

## What is wrong

When the daily review of both memory stores is due, the handoff-supervisor on the Mac adds the memory-review reminder to the successor's initial-agent-instructions (`memory_review_due_lines()` in `nc-systems/handoff/handoff-supervisor.py`, on main at 78716fd58). The reminder's text, `MEMORY_REVIEW_DUE_INSTRUCTION_TEMPLATE` in the same file, begins with "Before anything else, run `python3 {mark_script} started`", so the started mark, which keeps every other agent-seat from being reminded the same day, depends on the agent obeying that line. Writing the mark needs no judgment: `nc-systems/handoff/handoff-user-review-of-agent-memory-stores-mark.py` writes it with its function `write_daily_memory_review_mark()`, and the handoff-supervisor already loads that program as a module.

## Why it matters

Until the agent writes the started mark, each agent-seat that starts on the Mac that day is told to do the same review, so the user can be walked through the same memory-store entries by two agent-seats. The project builds code-prompt-code: a step that needs no judgment goes in code, which runs the same way each time.

## What to build

When `memory_review_due_lines()` returns a reminder, the handoff-supervisor writes the started mark, as `handoff-user-review-of-agent-memory-stores-mark.py started` writes it, and drops the "Before anything else" line from the reminder. When the write fails, the reminder still goes into the initial-agent-instructions, with one line saying the mark could not be written and why, and with the "Before anything else" line kept, so the agent writes the mark itself; the handoff-supervisor also prints that line on its console. The done mark stays with the agent, because only the agent knows when the user has ruled on every entry. Tests go in `nc-systems/handoff/tests/handoff-supervisor-successor-prompt-test.py`, where the memory-review reminder's tests are, with the failed write injected.

## Open question

The design the user ruled on 2026-09-30, in GHI [Memory: a daily review of both memory stores with the user](https://github.com/nedschorus/nedschorus/issues/39) (`docs/issues/39-memory-drain-at-reincarnation.md`, "What the user ruled, 2026-09-30", item 3), says the instruction tells the agent to mark the review started first. A mark the handoff-supervisor writes changes one case: when the successor never starts, or dies before it starts the review, the mark keeps every agent-seat on the Mac, that agent-seat's own next successor included, from being reminded until the next noon in Pacific time, where today the next agent-seat started would be reminded. Writing the mark only after the successor has started narrows that case but does not remove it. The builder brings the user that change before building.

## What this does not cover

The nc-architecture-overview refresh reminder's mark, written by `nc-systems/handoff/handoff-architecture-overview-refresh-user-shown-mark.py`, stays with the agent. Its docstring says to write it only after the user has been shown the refresh, so that an agent-seat closed before showing it leaves the next agent-seat able to remind him; a mark written when the reminder goes into the initial-agent-instructions would defeat that.

## Next action

An agent-seat that takes up this GHI brings the user the open question; once he approves, it builds the change in one pull request with its tests.

## Where this came from

Item 5 of Question 4, "What should be code", in the cold-read-fast-read of the handoff-system's nc-architecture-overview draft on 2026-11-03: `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/nedschorus-handoff-architecture-overview-draft-2026-11-03/cold-read-fast-read.md`. That item also proposed that the handoff-supervisor write the nc-architecture-overview refresh's shown mark; that half was dropped, for the reason under "What this does not cover". Checked against main at 78716fd58 on 2026-11-03. ghi-guide-agent, asked with `--include-closed`, named no issue that covers it.
