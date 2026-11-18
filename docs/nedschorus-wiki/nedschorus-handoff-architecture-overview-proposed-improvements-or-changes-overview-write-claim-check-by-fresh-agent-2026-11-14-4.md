# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-14)

Assertions of the overview that the claim check against commit 679d9a2a881f3bbe08cdb0db0b96532e1f347ef3 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/7ffa7a73a4c9377f84501627c7a50ad9bae58f89-2026-11-14T11-05-28-042311Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: At its first launch the handoff-supervisor carries out a waiting session-handoff (or, with `--resume-session-id`, marks it consumed and resumes); otherwise it starts fresh when an exit is recorded, "and else resumes the agent-seat's last transcript worth resuming", stopping when it cannot read the transcript folder.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> The "else resumes" branch has two exceptions the sentence leaves out, so an agent cannot predict a fresh start from it:
> - nc-systems/handoff/handoff-supervisor.py:2583 `and not settings.first_prompt_wins_over_crashed_transcript` — `--first-prompt-file-wins-over-crashed-transcript` skips the resume.
> - handoff-supervisor.py:2610-2612 `else: print("handoff-supervisor: no waiting handoff and no recorded exit, and " f"nothing worth resuming ({by_hand_detail}); starting fresh")` — with no transcript worth resuming it starts fresh.
> The rest is borne out: :2527-2537 (marks a waiting handoff consumed under --resume-session-id), :2540-2578 (carries out a waiting handoff), :2589-2597 (stops when the folder cannot be read).
State: open

## E2 — possible problem: an assertion of the overview is contradicted

Claim: The reference-checkout leftovers program saves the checkout's leftovers to a branch it pushes, "and only then puts the checkout back on main".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> The checkout goes back on main whether or not the push succeeded:
> - handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:27-29: `then runs git switch --no-overwrite-ignore -C main origin/main ... whether or not every push succeeded, because every agent-seat's git hooks and the cron jobs run from this checkout`.
> - Same file, :52-54: `a failed push of a leftovers branch ... still lets the checkout go back on main: the unpushed branch stays in the checkout`.
> A reader of "only then" would take a checkout back on main as proof that the leftovers reached origin.
State: open

## E3 — possible problem: an assertion of the overview is contradicted

Claim: The agent-seat's task list under `~/.claude/tasks/` is "written by Claude Code, and on ned-box by the agent-crash-watcher"; completed tasks are removed by the writer script.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> Two more programs write it:
> - nc-systems/handoff/uncommitted-work-snapshots.py:911-912: `task_id = agent_seat_task_list.agent_seat_task_list_new_pending_task_write(task_list, subject, description, metadata)` — restore opens a task.
> - scripts/clean-worktrees.py:236-245: `Last, it closes the tasks that uncommitted-work-snapshots.py restore opens, in every task list on the machine ... marks the task completed, adding a line at the end of its description`.
State: open

## E4 — possible problem: an assertion of the overview is contradicted

Claim: The reference-checkout `~/Projects/nedschorus` is fast-forwarded by the launchers, by every supervisor running from it at each non-consulting session-handoff, and by the restart program. It is put back on main by the leftovers program, "which pushes any leftovers in it to a reference-checkout-leftovers-<date> branch first".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> Two problems:
> - The writer list leaves out the Stop hook, which fast-forwards the reference-checkout during every agent-session. scripts/checkout-freshness-catch-up.py:11 `Wired as a Stop hook, so it runs at every turn boundary.` and :63-65 `The machine's reference checkout — the main worktree of the same repository, parked on main — gets a fast-forward-only pull on the same rhythm`.
> - "Pushes ... first" is contradicted, as in assertion 57. handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:27-29 `... whether or not every push succeeded` and :19-20 (the branch can be the leftovers branch HEAD is already on).
> The other writers are borne out: launch-claude-ubuntu:335, launch-claude-mac:288, handoff-supervisor.py:2431-2432, restart program:19.
State: open
