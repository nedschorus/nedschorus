# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-11)

Assertions of the overview that the claim check against commit 84a92dd16d5d3d180f2214e2f3a7c2541fb62562 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/2849acdfa8c72239374f9f407c895e6404784896-2026-11-11T23-05-48-837391Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: The leftovers-saving back-on-main program saves the leftovers to a branch it pushes, "and only then puts the checkout back on main".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - nc-systems/handoff/handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:27-29 `runs git switch --no-overwrite-ignore -C main origin/main ... whether or not every push succeeded, because every agent-seat's git hooks and the cron jobs run from this checkout`
> - The checkout goes back on main even when the push failed; unpushed leftovers stay only on a local branch (:17-18, :23).
> - The overview also never says that the handoff-supervisor runs this program's `put_reference_checkout_back_on_main` itself (handoff-supervisor.py:2382-2388; this program's docstring :7-11).
State: open

## E2 — possible problem: an assertion of the overview is contradicted

Claim: When the restart cannot happen, the successor's notice names the back-on-main program whenever the supervisor runs from the reference-checkout and the replacement itself did not fail, and the restart program otherwise.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - handoff-supervisor.py:2382-2394: the back-on-main program is named only when the supervisor's own run of `put_reference_checkout_back_on_main` failed.
> - :2398-2400 `report = launch_time_git_sync_of_own_checkout_first_line_if_not_on_main()` / `if report: return handoff_supervisor_not_restarted_notice_and_console_line(report, settings.agent)`: when that run succeeded but the checkout is still not at main, the notice names the restart program (:2325-2328).
> - The overview also omits that the supervisor runs the back-on-main step itself before giving up.
State: open

## E3 — possible problem: an assertion of the overview is unsupported

Claim: The owner file's writers are the post-checkout hook, the snapshot hook, clean-worktrees, the backfill script and the module's `write` command.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - Files read: uncommitted-work-snapshots.py, worktree-owner-file-read-and-write.py.
> - The list is incomplete: the `restore` command of uncommitted-work-snapshots.py also writes owner files through the module's function (uncommitted-work-snapshots.py:910-914 `owners.worktree_owner_file_write(worktree, owners.OWNER_AGENT_SEAT, agent_seat)`).
State: open

## E4 — possible problem: an assertion of the overview is unsupported

Claim: The agent-seat's task list is written by Claude Code, and completed tasks are removed by the writer script.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - Files read: handoff-agent-crash-watcher.py, uncommitted-work-snapshots.py, clean-worktrees.py.
> - Programs in this system also write the task list, and the overview leaves them out:
>   - handoff-agent-crash-watcher.py:1101-1104 `task_list = task_lists_directory / f"nedschorus-{agent_seat}-tasks"` writes new tasks.
>   - uncommitted-work-snapshots.py:949-952: `restore` opens a task.
>   - clean-worktrees.py:221 `Last, it closes the tasks that uncommitted-work-snapshots.py restore opens`.
State: open

## E5 — possible problem: an assertion of the overview is unsupported

Claim: Entry points: the install scripts (a person); the `list` command of uncommitted-work-snapshots.py (a person or an agent); the `write` and `show` commands of the owner-file module.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - Files read: uncommitted-work-snapshots.py.
> - The module also has `restore` and `discard` commands (uncommitted-work-snapshots.py:29-39, :1138-1148).
> - The first prompt sends agents to these commands: :605-612 `return f"{program} restore {snapshot['ref']} --keep {files}"`, :633 `parts.append(f"handle it with: `{entry_command_text(repo, snapshot)}`")`.
> - These entry points are missing from Entry points and from Components.
State: open
