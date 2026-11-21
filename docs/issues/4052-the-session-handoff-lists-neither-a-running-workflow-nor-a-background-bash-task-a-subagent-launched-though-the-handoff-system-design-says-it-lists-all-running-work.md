---
issue: "[The session-handoff lists neither a running workflow nor a background Bash task a subagent launched, though the handoff-system design says it lists all running work](https://github.com/nedsnodes/nedsnodes/issues/4052)"
---

# The session-handoff lists neither a running workflow nor a background Bash task a subagent launched, though the handoff-system design says it lists all running work

## What is wrong

`nn-systems/handoff/handoff.system.design.md` says, in the User-rulings entry "A reincarnate-seat waits for the agent-session's running subagents, up to a ceiling", that work started during a handoff-deferral, "if still running at the session-handoff ... is stopped and listed for the successor", where the work named is "the subagents, workflows and background Bash tasks"; and section "The handoff-deferral fields" says "the spawned-subagent-roster and the background-task fields already list every subagent and background Bash task still running".

The writer, `nn-systems/handoff/handoff-write-and-check-supervisor.py`, lists less than that:

- No field carries a run of Claude Code's Workflow tool. The spawned-subagent-roster is read from the transcript's Agent-tool spawns, and the background-task fields from the agent-session's own Bash launches.
- A background Bash task that a subagent launched is recorded only in the subagent's own transcript, `<session-dir>/subagents/agent-<id>.jsonl`, and the background-task fields read only the agent-session's transcript (`background_task_launches_still_running_in_transcript` in the writer takes its tasks from the agent-session's transcript alone, on main at 55626cb48). Claude Code's `background_tasks` list, which the threshold-hook reads, does include such a task.

So a workflow, or a subagent's own background Bash task, still running at the session-handoff is stopped, and the successor is not told it existed.

The findings come from the cold-read-full-run `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/handoff.system.design-2026-11-20-6`; its `cold-read-triage.md`, in that directory beside the reports named here, gives each of these findings the link of the GHI filed from this file: `agy-hunt-gemini-4-argon-high.md` 11 and 14; `claude-hunt-deep.md` 18 and 25; `codex-hunt-deep.md` 13 and 15.

## Why it matters

An agent that starts a workflow, or whose subagent starts a long test run, relies on the design's word that the successor will be told; the successor is not, and the work is lost without a trace in the session-handoff.

## Next action

The agent-seat that takes up this GHI decides, with the user where the ruling's wording is at stake, whether the writer lists these two kinds of running work or the design's sentences are narrowed to what the writer lists; covering also a workflow or background task started inside a subagent or a workflow, and saying what the successor is given to restart each, such as its command or description; then lands that in one pull request, with a test that puts each kind in a transcript and checks the session-handoff, and the design's change, which gets the cold-read-full-run the /cold-read skill gives a design.
