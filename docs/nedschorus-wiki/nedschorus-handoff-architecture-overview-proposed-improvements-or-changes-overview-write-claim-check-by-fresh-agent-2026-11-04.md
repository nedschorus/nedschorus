# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-04)

Assertions of the overview that the claim check against commit 9ecda8345f6d2062befc44c042236d7e6c6ae6fa found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/0e70ae713f204f4060a2c90726caef86c5b80c19-2026-11-04T23-15-57-960804Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: `<session>-handoff-asked` and `<session>-handoff-deferred` are written by handoff-context-threshold-hook.py and read by it and by `scripts/agent-seat-due-task-raise-hook.py`. The first is deleted by the post-compaction hook; the second outlasts a compaction and is deleted by the threshold hook when it tells the agent to run /handoff.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> The writer, deleters and the two named readers are borne out: handoff-context-threshold-hook.py:565, 585, 597; agent-seat-due-task-raise-hook.py:697-698; post-compaction-session-continues-hook.py:109-110. But the reader list leaves out a third reader of the deferred marker, scripts/agent-seat-idle-sweep-verdicts-print.py:79 `HANDOFF_DEFERRED_SUFFIX = "-handoff-deferred"`; an agent renaming the marker would miss it.
State: open
