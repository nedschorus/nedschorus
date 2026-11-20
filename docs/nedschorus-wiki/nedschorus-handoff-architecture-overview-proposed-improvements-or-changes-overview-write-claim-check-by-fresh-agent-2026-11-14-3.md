# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-14)

Assertions of the overview that the claim check against commit 56961de1b02f8a441103351cb9fbe8babb42f747 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/bbb03c74963a8d4e24b5995e60af59e18694977b-2026-11-14T09-19-30-985666Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: At its first launch the handoff-supervisor carries out a waiting session-handoff, unless started with `--resume-session-id`. Otherwise it starts fresh when an exit is recorded, and else resumes the agent-seat's last transcript worth resuming. It stops when it cannot read the transcript folder.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - nc-systems/handoff/handoff-supervisor.py:2582-2585 "if (not settings.resume_session_id and not settings.first_prompt_wins_over_crashed_transcript and ignition_plan is None and agent_exit_record_from_supervisor_state(state) is None):"
> - The handoff-supervisor also starts fresh, with no exit recorded, when it is given `--first-prompt-file-wins-over-crashed-transcript` (help text at 2829-2834). `recover-crashed-seats.py` passes that flag (scripts/recover-crashed-seats.py:237). The "else resumes" rule leaves this case out.
State: open

## E2 — possible problem: an assertion of the overview is contradicted

Claim: The back-on-main program saves the reference-checkout's leftovers to a branch it pushes, and only then puts the checkout back on main.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - nc-systems/handoff/handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:27-29 "then runs `git switch --no-overwrite-ignore -C main origin/main` ... whether or not every push succeeded"
> - same file:52-54 "a failed push of a leftovers branch ... still lets the checkout go back on main: the unpushed branch stays in the checkout"
> - "Only then" wrongly implies the push has succeeded before the switch. A local branch holds the leftovers, but the push may have failed.
State: open

## E3 — possible problem: an assertion of the overview is contradicted

Claim: The task list's completed tasks are removed by the writer script, which compares each with its log-store copy, written by `transcript-mirror-to-log-store.py`.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - nc-systems/handoff/handoff-write-and-check-supervisor.py:52-54 "The writer first copies each completed task it would remove into the log-store, and removes it only when the log-store's copy then has the same bytes"
> - same file:834 "copy_task_files_to_log_store(host, list_directory, store_list_directory, candidate_names)"
> - The writer script is also a writer of the log-store copy it compares against; the overview names only the mirror.
State: open
