# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-05)

Assertions of the overview that the claim check against commit ffda8acb53b803e99d2da40fd114686ee8fc0291 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/a9e58dc888a1fa644d2d69e0f307e6817a3a4746-2026-11-05T04-44-09-006473Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: Diagram: agent-crash-watcher (ned-box, every minute) ──> recover-crashed-seats.py ──> launcher or tmux pane
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - On ned-box, recover-crashed-seats.py never runs a launcher. recover-crashed-seats.py:645-648 `if sys.platform == "darwin":` … `return durable_checkout / LAUNCH_CLAUDE_MAC_WITHIN_A_CHECKOUT` / `return None`
> - With no launcher, launch_seat takes the tmux branch at :855 `completed = run_tmux(`.
> - The watcher refuses to run anywhere but ned-box: handoff-agent-crash-watcher.py:76 `Off ned-box the program refuses: the agent-seats root it reads is ned-box's.`
> - So on this row the only target is the tmux pane. The rest of the overview says recover-crashed-seats.py starts a ned-box tmux server itself, so no agent would act wrongly on it.
State: open

## E2 — possible problem: an assertion of the overview is contradicted

Claim: `<session>-handoff-asked` and `<session>-handoff-deferred`, keyed by session ID, are written by the threshold hook and read by it and by `scripts/agent-seat-due-task-raise-hook.py`. The first is deleted by the post-compaction hook; the second outlasts a compaction and is deleted by the threshold hook when it asks for the handoff.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The writers, the deletions and the due-task hook read are right: handoff-context-threshold-hook.py:565, 585, 597; post-compaction-session-continues-hook.py:110; agent-seat-due-task-raise-hook.py:708-709.
> - But the reader list names one outside reader and leaves out another: scripts/agent-seat-idle-sweep-verdicts-print.py:82 `HANDOFF_DEFERRED_SUFFIX = "-handoff-deferred"` and :531 `marker = paths.handoff_directory / f"{session_id}{HANDOFF_DEFERRED_SUFFIX}"`
> - The idle sweep keeps its own copy of the suffix, so renaming the marker from this list alone would silently break it.
State: open
