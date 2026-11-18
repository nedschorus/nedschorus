# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-15)

Assertions of the overview that the claim check against commit bc19cd32d263123a0dd057b1b97c5508db5650e6 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedsnodes-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/e70fbebefd630555cf9348a1bf6fd2bda21c0ea6-2026-11-15T19-52-50-377663Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: The name `<session>-handoff-deferred` is spelled only in `handoff-deferred-marker-and-refused-commands-files-common.py`, which each reader loads.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The code constant is only in the common module (`handoff-deferred-marker-and-refused-commands-files-common.py:34 HANDOFF_DEFERRED_MARKER_SUFFIX = "-handoff-deferred"`), but the threshold hook's docstring spells it too: scripts/handoff-context-threshold-hook.py:7 `<session>-handoff-deferred in ~/.claude/handoffs/, while Claude Code's background_tasks list`, and :13 `while <session>-handoff-deferred`.
> - "Defined only in" would be accurate. A rename would leave that docstring stale, but no program would break.
State: open
