# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-06)

Assertions of the overview that the claim check against commit e0f608a0a433a189da0c362861753d098c48a959 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/260741fa9320708ce9cb7822f6e8e78798963c5e-2026-11-06T15-22-52-331480Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: Shared state: the reference-checkout `~/Projects/nedschorus`. The overview lists its writers as the launchers, every handoff-supervisor that runs from it at a session-handoff, and the restart program.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The list leaves out the Stop hook checkout-freshness-catch-up.py, which fast-forwards it at every turn boundary.
> - scripts/checkout-freshness-catch-up.py:11 `Wired as a Stop hook, so it runs at every turn boundary. Each run:`
> - same file:61-63 `6. The machine's reference checkout — the main worktree of the same repository, parked on main — gets a fast-forward-only pull on the same rhythm, under its own stamp.`
> - The list is incomplete, but no agent would open the wrong file on it.
State: open
