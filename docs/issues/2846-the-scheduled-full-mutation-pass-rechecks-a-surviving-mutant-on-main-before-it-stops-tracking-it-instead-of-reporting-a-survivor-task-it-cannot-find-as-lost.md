---
issue: "[The scheduled full mutation pass rechecks a surviving mutant on main before it stops tracking it, instead of reporting a survivor task it cannot find as lost](https://github.com/nedschorus/nedschorus/issues/2846)"
---

# The scheduled full mutation pass rechecks a surviving mutant on main before it stops tracking it, instead of reporting a survivor task it cannot find as lost

## What is wrong

`scripts/scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.py` runs each night on ned-box. For each line with surviving mutants it opens a survivor task on the task list of the agent-seat that wrote the line, and its state file records which task holds each mutant. Step 4 of each run, as the program's docstring on main describes it, checks that each such task still lists its mutants. When a task no longer holds a mutant, step 4 takes one of three branches:

- Moved: exactly one other open task on the same list names the mutant's diff file; the state now names that task.
- Finished: the task is marked completed and no open task names the diff file; the state stops naming the mutant, and nothing else happens.
- Reported once: every other case, such as a task file that is gone. The run writes the mutant into its record, stops naming it in the state, and exits 7 (`EXIT_OPENED_TASK_NO_LONGER_HOLDS_ITS_SURVIVOR`). It opens no task.

Exit 7 opens no task because the program cannot tell a lost task from a finished one that a session-handoff deleted: the handoff writer deletes completed tasks from the task list, so a survivor task its owner finished and marked completed is, by the next night, a missing file, the same as a task that was lost. If exit 7 opened a task, it would open one after ordinary session-handoffs. The user ruled on 2026-11-08 that exits 5 and 8 open a job failure task and exit 7 does not (item 2 of the approval-walk memory-refusal-only-the-callers-lines-and-restored-branch-task-rebase-gap-approval-walk-2026-11-08, minutes at `docs/walk/memory-refusal-only-the-callers-lines-and-restored-branch-task-rebase-gap-approval-walk-2026-11-08-minutes.md` in agent-seat fleet-restart-at-login's checkout on ned-box); PR [Scheduled mutation pass: an unwritten record or a recheck with no verdicts opens a job failure task](https://github.com/nedschorus/nedschorus/pull/2839) builds that ruling.

Why it matters: a survivor task that is truly lost, or marked completed without a test that kills its mutants, ends with the mutant dropped from the state and only a line in the run's record, which no agent reads. The mutant survives on main and no task asks anyone to kill it.

## The proposed fix

The question step 4 cannot answer, whether the task was finished or lost, need not be asked. What matters is whether the mutant still survives on main, and the program already has a way to ask that: the recheck (step 5) runs `scripts/mutation-testing-changed-lines-quick-or-full-pass-survivors.py --recorded-mutant-killed-check` on each mutant's diff file with `--head origin/main`, and judges each mutant killed, no longer existing, surviving or not judged.

Proposed, from merge-lane-2's cold-read-fast-read note on PR [#2827](https://github.com/nedschorus/nedschorus/pull/2827), whose record is `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/scripts-scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open-2426b6eb0254add0-agent-facing-message-2026-11-08/cold-read-fast-read.md`: in the Finished branch and the Reported-once case, run that check on the mutant before the state stops naming it.

- Killed, or no longer existing: drop it, with no report; the work was done, whoever deleted the task.
- Still surviving: open a survivor task for it again, as for a new survivor, so the work is not lost. When two or more open tasks already name its diff file, the work is not lost, and the build decides which of them the state names instead of opening another.
- Not judged: keep it in the state, so the next run checks it again, and report it.

With that, a mutant is dropped only when main no longer has it, and exit 7 no longer reports a mutant that may still survive.

Questions the build answers:

- How a not-judged mutant is reported, and what task the state names for it while its old task is completed or gone: through exit 7, kept for this case alone, or as step 5 reports a survivor task whose recheck gives no verdicts, which after PR #2839 opens a job failure task (exit 8).
- Who owns a reopened survivor task: the agent-seat the state names for the mutant, or the author `git blame` gives the line on main.
- Whether mutants of the same line found surviving here share one reopened task, as step 7 groups a merge's survivors by line.
- Whether step 5 skips a mutant step 4 has just checked in the same run.
- Whether the two-or-more-tasks check, and the Moved branch's one-task check, look at other agent-seats' task lists as well as the owner's.

A second, separate idea from the same note: a later run that passes could close the job failure task an earlier failed run opened. It is not part of this fix.

Before relying on the check here, read GHI [The recorded mutant killed check in scripts/mutation-testing-changed-lines-quick-or-full-pass-survivors.py can apply a recorded mutant to a second copy of its hunk](https://github.com/nedschorus/nedschorus/issues/2780): a wrong verdict there would make this fix drop a surviving mutant.

## Next action

Recommendation: build the fix above when the scheduled job's maintenance next allows; the user decides when. The build changes step 4 of the program and its docstring, and adds tests for each of the three verdicts in both the Finished branch and the Reported-once case.
