---
issue: "[What a successor does with a background task stopped at a session-handoff: rerun, restart if needed, or neither](https://github.com/nedsnodes/nedsnodes/issues/4048)"
---

# What a successor does with a background task stopped at a session-handoff: rerun, restart if needed, or neither

## What is wrong

`nn-systems/handoff/handoff.system.design.md` gives a successor two instructions about background Bash tasks that the session-handoff stopped, and they do not fit together or end:

- For a task that passed its wait-limit, section "What a reincarnate-seat kills, and how work survives it" says: "The next agent-session reruns the task, then looks first for a way to make it faster, such as removing repeated work or running its steps in parallel, and raises its kind's limit in the table only when it finds none."
- For every background task still running at the session-handoff, the successor is told, as section "The background-task fields" quotes: "Restart any you still need."

A task past its wait-limit is still running when the session-handoff is written, so the handoff-supervisor, `nn-systems/handoff/handoff-supervisor.py`, gives its successor both sentences in the initial-agent-instructions: run it again, and restart it only if still needed. Beyond that conflict:

- Nothing says when the search for a faster way ends, so a successor can spend a minute or an afternoon and obey either way.
- A rerun that hangs again has no outcome, and the wait-limit governs only the handoff-deferral, not how long the rerun may take; a task that cannot finish within the ceiling can be killed and rerun at every session-handoff.
- A command that no kind's pattern matches gets the default of 75 minutes, `BACKGROUND_TASK_WAIT_LIMIT_MINUTES_WHEN_NO_KIND_MATCHES` in `scripts/handoff-context-threshold-hook.py`, which is not a row of the table, so "raises its kind's limit in the table" names nothing to raise; raising the default changes every unmatched command.
- Neither instruction says whether the command is safe to repeat. A background command can create remote state, such as a pull request or a pushed branch, before it is stopped; rerunning it can do that twice. CLAUDE.md allows a retry only "on an operation safe to repeat".

The findings come from the cold-read-full-run `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/handoff.system.design-2026-11-20-6`; its `cold-read-triage.md`, in that directory beside the reports named here, gives each of these findings the link of the GHI filed from this file: `claude-hunt-deep.md` 11; `claude-hunt-second-strongest-model.md` 11 and 12; `codex-hunt-deep.md` 3, 4, 5 and 6; `codex-hunt-second-strongest-model.md` 3 and 7.

## Why it matters

The successor acts on these instructions at its first turn, with no context but the session-handoff. Conflicting or open-ended instructions there either waste the successor's work on a rerun it did not need, or repeat a side effect the stopped task already had.

## Next action

The agent-seat agent-instructions-editor proposes one rule for every background task the session-handoff stops, waiting-tasks included, covering the past-wait-limit case, a command with no kind, a rerun that hangs, and a command not safe to repeat, and brings it to the user in an approval-walk, because the instructions are user-ruled. The parts that need no judgment go in code, as Question 4 of this GHI-MD's cold-read-fast-read, `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/handoff-past-wait-limit-task-rerun-instruction-2026-11-20/cold-read-fast-read.md`, proposes: each task gets one sentence rather than two, the writer counts how many session-handoffs in a row stopped the same command so the sentence can change after the first, and a command no kind matches gets its own sentence. Once he rules, one pull request changes the design, the handoff-supervisor's sentences and the code, with tests, and the design's change gets the cold-read-full-run the /cold-read skill gives a design.
