# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-12)

Assertions of the overview that the claim check against commit 96ef56fa75d404e4243d5ecaa799571a8f8d2ea2 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/7c17c266f4c6ec2951c4e0d0da3a1336c1f1547d-2026-11-12T05-01-04-583568Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: The reference-checkout leftovers-saving back-on-main program is "run by an agent-seat on its own machine when the reference-checkout will not fast-forward to main".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> The handoff-supervisor also runs it, in-process, at a session-handoff. The component sentence leaves that caller out.
> - nc-systems/handoff/handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:9 `neither, the handoff-supervisor runs this program's put_reference_checkout_back_on_main itself and,`
> - nc-systems/handoff/handoff-supervisor.py:2387 `reference_checkout_back_on_main.put_reference_checkout_back_on_main(`
State: open

## E2 — possible problem: an assertion of the overview is contradicted

Claim: When the restart fails, the notice names "the reference-checkout leftovers-saving back-on-main program when the handoff-supervisor runs from the reference-checkout and the replacement itself did not fail ..., and the restart program otherwise".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> In the code, the handoff-supervisor first runs the back-on-main program itself. It names that program only when its own run failed. When that run succeeded but the checkout is still not on main, it names the restart program.
> - nc-systems/handoff/handoff-supervisor.py:2382 `if report and REPOSITORY_ROOT == REFERENCE_CHECKOUT:`
> - nc-systems/handoff/handoff-supervisor.py:2389-2394 (only on `StepFailed` is `back_on_main_program_failure_output` passed)
> - nc-systems/handoff/handoff-supervisor.py:2398-2400 `report = launch_time_git_sync_of_own_checkout_first_line_if_not_on_main()` / `return handoff_supervisor_not_restarted_notice_and_console_line(report, settings.agent)` (this notice names the restart program, :2325-2328)
State: open

## E3 — possible problem: an assertion of the overview is contradicted

Claim: The list of writers of `worktree-owner.json`.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> The list leaves out `uncommitted-work-snapshots.py restore`, which writes an owner file into the worktree it makes.
> - nc-systems/handoff/uncommitted-work-snapshots.py:872 `owners.worktree_owner_file_write(worktree, owners.OWNER_AGENT_SEAT, agent_seat)`
> - nc-systems/handoff/uncommitted-work-snapshots.py:32-33 `... given an owner file naming the agent-seat GIT_AUTHOR_NAME names;`
State: open

## E4 — possible problem: an assertion of the overview is contradicted

Claim: The readers of transcripts under `~/.claude/projects/` are "the extractor, the threshold hook, the post-compaction hook, the writer script, `agent-seat-transcript-worth-resuming-common.py`, the agent-crash-watcher and the Remote Control reconnect watcher".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> The restart program also reads a seat's transcripts, in its step 7.
> - nc-systems/handoff/handoff-supervisor-restart-onto-main-code-by-relaunch-from-reference-checkout.py:43-44 `- step 7: waits up to 5 minutes from step 6's start for a new transcript in the agent-seat's project folder under ~/.claude/projects to hold a reply from the successor.`
State: open

## E5 — possible problem: an assertion of the overview is contradicted

Claim: The task list under `~/.claude/tasks/` is "written by Claude Code, and on ned-box by the agent-crash-watcher; completed tasks removed by the writer script".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> Two more programs write it: `uncommitted-work-snapshots.py restore` opens a task, and `clean-worktrees.py --remove` marks restore tasks completed.
> - nc-systems/handoff/uncommitted-work-snapshots.py:911 `task_id = agent_seat_task_list.agent_seat_task_list_new_pending_task_write(`
> - scripts/clean-worktrees.py:221-230 `Last, it closes the tasks that uncommitted-work-snapshots.py restore opens, in every task list on the machine ... marks the task completed`
State: open

## E6 — possible problem: an assertion of the overview is contradicted

Claim: The reference-checkout is "fast-forwarded to main by launch-claude-ubuntu ..., by launch-claude-mac ..., by every handoff-supervisor that runs from it, and by the restart program".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> The `checkout-freshness-catch-up.py` Stop hook fast-forwards it mid-session too, and this row leaves it out.
> - scripts/launch-claude-mac:283-286 `Launch-time freshness: fast-forward the machine's reference checkout to origin/main ... The mid-session half runs as a Stop hook (scripts/checkout-freshness-catch-up.py)`
> - .claude/settings.json:83
State: open

## E7 — possible problem: an assertion of the overview is contradicted

Claim: Entry point: the back-on-main program is started by "an agent-seat whose initial-agent-instructions name it, because its handoff-supervisor did not restart itself on main's code".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> The handoff-supervisor is also a caller: it runs the program's `put_reference_checkout_back_on_main` itself at a session-handoff, before any notice names the program.
> - nc-systems/handoff/handoff-supervisor.py:2386-2388 `reference_checkout_back_on_main.put_reference_checkout_back_on_main(REFERENCE_CHECKOUT, datetime.now().date())`
> - nc-systems/handoff/handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:9
State: open

## E8 — possible problem: an assertion of the overview is contradicted

Claim: Entry point: the install scripts are run by a person; the `list` command of `uncommitted-work-snapshots.py` by a person or an agent its initial-agent-instructions send there; the owner-file `write` and `show` commands by a person or a program that makes a worktree.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> The initial-agent-instructions mainly send agents to the module's `restore` and `discard` commands, and Entry points does not list them. Every listed work-snapshot entry ends with one of them.
> - nc-systems/handoff/uncommitted-work-snapshots.py:636 ``parts.append(f"handle it with: `{entry_command_text(repo, snapshot)}`")``
> - nc-systems/handoff/uncommitted-work-snapshots.py:613-615 (`discard` / `restore ... --keep`)
> - nc-systems/handoff/uncommitted-work-snapshots.py:1098-1108 (the restore and discard commands in main)
State: open
