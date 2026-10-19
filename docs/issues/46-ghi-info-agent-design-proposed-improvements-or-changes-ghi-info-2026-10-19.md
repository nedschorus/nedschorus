# Proposed improvements or changes from ghi-info, 2026-10-19

ghi-info reviewed the GHI-MD beside this file when scripts/ghi-issue-write.py edited it. Once this file is on main, the agent that ran the tool dispatches a forked subagent to settle each entry by rules 3 to 7 of § The design in docs/issues/1132-concerns-about-a-ghi-are-handled-by-agents.md.

## E1 — possible problem: the GHI-MD's proposal may go against a user-ruling held in GHI [Proposed improvements or changes to a GHI are handled by agents first, and reach the user only when they need him](https://github.com/nedschorus/nedschorus/issues/1132)
ghi-info's question: The ruling that proposed improvements or changes to a GHI are handled by agents first and reach the user through its proposed-improvements route, against this design's § What ghi-info is, which has an unresolved ruling doubt land as a new queue-drain-candidate-labeled issue via an `escalate:` reply — and the corpus shows ghi-info's own ruling-conflict flags this session landing instead as `conflicts-with-a-ruling` labels plus a `-proposed-improvements-or-changes-ghi-info-<date>.md` document on the same issue — does #1132's route replace the design's escalation surface, or does the design's stand?
Goes wrong when: the proposal is carried out while that user-ruling still applies.
State: open
