# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-12)

Assertions of the overview that the claim check against commit 1b6fb19aeab73778f234b7552b2f7dfec1ef2cef found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/fd86d56b9bc675e893af7a8f405bbde8898a40f5-2026-11-12T05-18-38-382372Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: The back-on-main program saves the reference-checkout's leftovers to a branch it pushes, "and only then puts the checkout back on main".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - nc-systems/handoff/handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:27-29 "then runs `git switch --no-overwrite-ignore -C main origin/main`, which puts the local main at origin/main and checks it out, whether or not every push succeeded"
> - nc-systems/handoff/handoff-supervisor.py:2288-2290 "once the checkout is on main, which it can be even after a failed push, so a leftovers branch the program could not push stays only in that checkout"
> - The leftovers are saved on a local branch before the switch, and the switch does not wait for the push to succeed. "Only then" overstates the order.
State: open

## E2 — possible problem: an assertion of the overview is contradicted

Claim: The agent-seat's task list under `~/.claude/tasks/` is "written by Claude Code"; the writer script removes completed tasks; the log-store copy is "written by `transcript-mirror-to-log-store.py`".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - nc-systems/handoff/handoff-agent-crash-watcher.py:1101-1104 `task_list = task_lists_directory / f"nedschorus-{agent_seat}-tasks"` ... `agent_seat_task_list_new_pending_task_write(` (the crash watcher writes tasks to agent-seat task lists).
> - nc-systems/handoff/uncommitted-work-snapshots.py:34 "opens a task naming the branch on the task list ~/.claude/tasks/<CLAUDE_CODE_TASK_LIST_ID>"
> - scripts/clean-worktrees.py:221-230 (marks restore tasks completed in every task list)
> - nc-systems/handoff/handoff-write-and-check-supervisor.py:616-618 "Copy the named task files into the log-store's copy of the list ... The mirror runs on a timer" (the writer also writes the log-store copy)
> - The lists of writers are incomplete. No one would act wrongly on them.
State: open

## E3 — possible problem: an assertion of the overview is contradicted

Claim: The reference-checkout is fast-forwarded by both launchers, by every supervisor running from it at a qualifying session-handoff, and by the restart program. It is "put back on main by the reference-checkout leftovers-saving back-on-main program, which pushes any leftovers in it to a `reference-checkout-leftovers-<date>` branch first".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - Fast-forwarders are supported: launch-claude-ubuntu:335, launch-claude-mac:288, handoff-supervisor.py:2357, restart program:19.
> - nc-systems/handoff/handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:27-29 "...checks it out, whether or not every push succeeded". The leftovers are committed to a local branch first; the push is attempted, not guaranteed, before the switch.
State: open

## E4 — possible problem: an assertion of the overview is contradicted

Claim: Entry points: "The install scripts: a person. The `list` command of `uncommitted-work-snapshots.py`: a person, or an agent its initial-agent-instructions send there. The `write` and `show` commands of `worktree-owner-file-read-and-write.py`: a person or a program that makes a worktree."
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - nc-systems/handoff/uncommitted-work-snapshots.py:15-17 "lists an agent-seat's lost work in the first prompt of every agent-session it starts, each entry ending with the restore or discard command that handles it"
> - nc-systems/handoff/uncommitted-work-snapshots.py:29, 38 (`restore` and `discard`)
> - The `restore` and `discard` commands are entry points that an agent the initial-agent-instructions send there runs. The section omits them, so it is incomplete. What it does say is true.
State: open
