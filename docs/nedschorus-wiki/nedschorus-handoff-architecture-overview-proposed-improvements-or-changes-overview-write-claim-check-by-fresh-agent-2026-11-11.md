# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-11)

Assertions of the overview that the claim check against commit 84a92dd16d5d3d180f2214e2f3a7c2541fb62562 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/38d35b2b5174f76b24a910ba1bd21d16812534dd-2026-11-11T22-22-26-436876Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: Invariant: "When the checkout cannot be brought to main's commit, or the replacement fails, it carries on with its old code, and the successor's initial-agent-instructions ... name the program to run: the reference-checkout leftovers-saving back-on-main program when the handoff-supervisor runs from the reference-checkout and the replacement itself did not fail ... and the restart program otherwise."
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - handoff-supervisor.py:2382-2388 `if report and REPOSITORY_ROOT == REFERENCE_CHECKOUT:` ... `reference_checkout_back_on_main.put_reference_checkout_back_on_main(` (the supervisor runs the leftovers-saving step itself first)
> - :2320-2324 the back-on-main program is named only `if back_on_main_program_failure_output:`, that is, only when the supervisor's own run of it failed.
> - :2398-2400 `report = launch_time_git_sync_of_own_checkout_first_line_if_not_on_main()` / `if report: return handoff_supervisor_not_restarted_notice_and_console_line(report, settings.agent)`: when the program succeeded but the checkout is still not on main, the restart program is named (:2325-2328).
> - handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:8-11 "the handoff-supervisor runs this program's put_reference_checkout_back_on_main itself and, when it succeeds, restarts"
> - The overview never says the supervisor runs this step itself. An agent changing the back-on-main program would not know the supervisor loads it at startup (handoff-supervisor.py:225-233). An agent reading a not-restarted notice that names the back-on-main program would not know it has already been run once.
State: open

## E2 — possible problem: an assertion of the overview is contradicted

Claim: Shared state, the task list under `~/.claude/tasks/`: "written by Claude Code; completed tasks removed by the writer script, which compares each with its copy in the log-store, ... written by `transcript-mirror-to-log-store.py`."
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - uncommitted-work-snapshots.py:34-35 restore "opens a task naming the branch on the task list ~/.claude/tasks/<CLAUDE_CODE_TASK_LIST_ID>"
> - clean-worktrees.py:227-230 "--remove ... marks the task completed, adding a line at the end of its description"
> - handoff-agent-crash-watcher.py:49-51 "A failure an agent can fix becomes a task on an agent-seat's task list, ~/.claude/tasks/nedschorus-<seat>-tasks/"
> - handoff-write-and-check-supervisor.py:611-617 `copy_task_files_to_log_store`: the writer itself rsyncs the log-store copies before comparing.
> - The path agent-session-files-by-machine/<machine>/tasks/ is supported: transcript-mirror-to-log-store.py:33.
State: open

## E3 — possible problem: an assertion of the overview is contradicted

Claim: Shared state, the reference-checkout `~/Projects/nedschorus`: "fast-forwarded to main by launch-claude-ubuntu ..., by launch-claude-mac ..., by every handoff-supervisor that runs from it, and by the restart program; put back on main by the reference-checkout leftovers-saving back-on-main program"
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - scripts/checkout-freshness-catch-up.py:1896-1898 `reference = reference_checkout_of(root)` / `fast_forward_reference_checkout(reference, ...)` in the Stop hook path. :1661-1662 "operator_facing=False is the Stop hook", so every agent-session's turn end also fast-forwards it.
> - handoff-supervisor.py:2386-2388 `reference_checkout_back_on_main.put_reference_checkout_back_on_main(REFERENCE_CHECKOUT, ...)`: the supervisor itself puts it back on main.
> - The listed writers are borne out: launch-claude-ubuntu:335, launch-claude-mac:288, handoff-supervisor.py:2357, restart program :19.
State: open

## E4 — possible problem: an assertion of the overview is contradicted

Claim: Entry point: "The reference-checkout leftovers-saving back-on-main program: an agent-seat whose initial-agent-instructions name it, because its handoff-supervisor did not restart itself on main's code."
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:8-9 "the handoff-supervisor runs this program's put_reference_checkout_back_on_main itself"
> - handoff-supervisor.py:2387 `reference_checkout_back_on_main.put_reference_checkout_back_on_main(`
> - The handoff-supervisor is also a caller, at each session-handoff where it would restart itself and the reference-checkout will not fast-forward.
State: open
