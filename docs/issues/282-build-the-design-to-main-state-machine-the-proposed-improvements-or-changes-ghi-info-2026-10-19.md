# Proposed improvements or changes from ghi-info, 2026-10-19

ghi-info reviewed the GHI-MD beside this file when scripts/ghi-issue-write.py edited it. Once this file is on main, the agent that ran the tool dispatches a forked subagent to settle each entry by rules 3 to 7 of § The design in docs/issues/1132-concerns-about-a-ghi-are-handled-by-agents.md.

## E1 — possible problem: the GHI-MD's proposal may go against a user-ruling held in GHI [refresh-design: when a system's code lands, bring its design, build-slice plan and overview into line — removing, never revising](https://github.com/nedschorus/nedschorus/issues/670)
ghi-info's question: The refresh-design rule that a landed design is brought into line by removing, never revising, against this edit's item 10 ruling of 2026-09-16 that design-to-main's design prose and its code both stay hand-edited — section 3.2 the source for what a transition is, the code for what it does, bound together by tests rather than one generated from the other — with slices 1 through 1d (and later) already landed on main, does #670 bind design-to-main's design, or does the earlier item 10 ruling stand?
Goes wrong when: the proposal is carried out while that user-ruling still applies.
State: open
