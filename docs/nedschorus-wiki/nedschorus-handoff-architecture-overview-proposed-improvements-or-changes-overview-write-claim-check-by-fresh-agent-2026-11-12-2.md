# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-12)

Assertions of the overview that the claim check against commit 1b6fb19aeab73778f234b7552b2f7dfec1ef2cef found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/c6db3c481b478830a1784c634a6acd8cd1b1e318-2026-11-12T06-25-19-226589Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: Diagram row: agent-crash-watcher (ned-box, every minute) ──> recover-crashed-seats.py ──> launcher or tmux pane.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The agent-crash-watcher runs only on ned-box. There recover-crashed-seats.py never runs a launcher: it always starts the tmux pane itself. So the "launcher or" in this row cannot happen.
> - recover-crashed-seats.py:645-651 `"""Return the durable checkout’s Mac launcher, or None off macOS."""` ... `if sys.platform == "darwin": ... return None`
> - recover-crashed-seats.py:796 `# This branch bypasses the launcher: preserve its task-store migration and binding,`
> - handoff-agent-crash-watcher.py:1215-1218 `if sys.platform != "linux": print(f"{PROGRAM}: refused: this program watches ned-box's agent-seats and runs only on ned-box`
State: open

## E2 — possible problem: an assertion of the overview is contradicted

Claim: `nc-systems/handoff/session-handoff-field-names-common.py` holds the session-handoff's field names, so renaming a field is one edit there.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - Two fields of the session-handoff are named elsewhere: handoff-supervisor.py:380-383 `BACKGROUND_TASK_STARTED_DURING_HANDOFF_DEFERRAL_FIELD_PREFIX = ("background-task-started-during-handoff-deferral-")` and `COLD_READ_FULL_RUN_COMMAND_REFUSED_DURING_HANDOFF_DEFERRAL_FIELD_PREFIX = (...)`.
> - The writer takes them from the supervisor, not from the common module: handoff-write-and-check-supervisor.py:156-159.
> - Renaming them is still one edit, but not in the file this row names.
State: open

## E3 — possible problem: an assertion of the overview is contradicted

Claim: The reference-checkout leftovers-saving back-on-main program saves the leftovers to a branch it pushes, and only then puts the checkout back on main.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - It puts the checkout back on main even when a push failed: handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:27-29 `then runs git switch --no-overwrite-ignore -C main origin/main, ... whether or not every push succeeded`
> - :52-55 `a failed push of a leftovers branch ... still lets the checkout go back on main: the unpushed branch stays in the checkout`
State: open

## E4 — possible problem: an assertion of the overview is contradicted

Claim: The task list is written by Claude Code and on ned-box by the agent-crash-watcher. The writer removes completed tasks after comparing with the log-store copy, which transcript-mirror-to-log-store.py writes.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - Other programs also write task files:
>   - clean-worktrees.py:221-230 `it closes the tasks that uncommitted-work-snapshots.py restore opens, in every task list on the machine ... marks the task completed, adding a line at the end of its description`
>   - uncommitted-work-snapshots.py:34-37 `opens a task naming the branch on the task list ~/.claude/tasks/<CLAUDE_CODE_TASK_LIST_ID>`
> - The writer also writes the log-store copy and the high-water mark itself:
>   - handoff-write-and-check-supervisor.py:52-54 `The writer first copies each completed task it would remove into the log-store`, and :616-632
>   - handoff-write-and-check-supervisor.py:672-690 (writes `.highwatermark`)
State: open

## E5 — possible problem: an assertion of the overview is contradicted

Claim: The reference-checkout is put back on main by the back-on-main program, which pushes any leftovers to a `reference-checkout-leftovers-<date>` branch first.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The switch to main runs even when a push failed: handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:27-29 `whether or not every push succeeded`; :52-55
> - The branch may also be an existing leftovers branch rather than a new dated one: :19-20 `the leftovers branch HEAD is already on, else a new branch reference-checkout-leftovers-<YYYY-MM-DD>`
> - The rest of the row is supported: launch-claude-ubuntu:335, launch-claude-mac:288, handoff-supervisor.py:2381, restart program :19
State: open
