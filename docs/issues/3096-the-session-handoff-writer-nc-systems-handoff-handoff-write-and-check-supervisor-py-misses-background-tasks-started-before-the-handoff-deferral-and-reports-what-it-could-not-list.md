---
issue: "[The session-handoff writer nc-systems/handoff/handoff-write-and-check-supervisor.py misses background tasks started before the handoff-deferral and reports what it could not list only after writing](https://github.com/nedschorus/nedschorus/issues/3096)"
---

# The session-handoff writer nc-systems/handoff/handoff-write-and-check-supervisor.py misses background tasks started before the handoff-deferral and reports what it could not list only after writing

## What is wrong

When an agent-session hands off, `nc-systems/handoff/handoff-write-and-check-supervisor.py` writes the session-handoff and records in it the work still running, so the successor knows what to start again. The successor needs that record because the session-handoff stops every background Bash task of the agent-session. Two gaps in that script, and one in a script that reads the same transcripts, are checked here against main at 30f0c3312.

### 1. Only background tasks started during the handoff-deferral are listed

`background_tasks_started_during_handoff_deferral_still_running` keeps a background Bash task only when its launch time is at or after the moment the handoff-deferral began, which `handoff_deferral_fields_for_this_session` reads from the handoff-deferred marker file. A task started earlier and still running is stopped at the session-handoff without being listed, so the successor never hears of it. When the session-handoff was not deferred at all, `handoff_deferral_fields_for_this_session` finds no marker file and lists no background task, however many are running.

Example: an agent starts a two-hour test run; the handoff-deferral begins 80 minutes later; at the session-handoff the run is stopped and left out of the session-handoff.

The field that carries the list is `background-task-started-during-handoff-deferral-N`, described in `nc-systems/handoff/handoff-design.md` and read by `nc-systems/handoff/handoff-supervisor.py`. Pull request [#3095](https://github.com/nedschorus/nedschorus/pull/3095) only tells the agent to name such a task by hand in the next step.

Proposed: list every background Bash task still running at the session-handoff, whatever its launch time and whether or not the session-handoff was deferred, and rename the field `background-task-still-running-N` in the design, the writer, the handoff-supervisor and their tests. The task list then no longer needs the handoff-deferred marker file, so an unreadable marker file stops being a reason the tasks are not listed; only an unreadable transcript remains. The same pull request removes the instruction #3095 added that tells the agent to name earlier tasks by hand.

This waits on the user's ruling. It is the approval-walk item "The handoff writer lists every background task still running, not only those started during the deferral", in ned-box-helper's walk-document `nedlern@ned-box:/home/nedlern/agents/ned-box-helper/docs/walk/ned-box-helper-push-program-design-points-2026-11-03.md`, which `.gitignore` keeps out of the repository. The item says no loss of work from this filter has been recorded.

### 2. The writer reports what it could not list only after the session-handoff is written

In `main`, the writer calls `spawned_subagent_roster_for_this_session` and `handoff_deferral_fields_for_this_session` first, then `write_handoff_file`, and prints their reports only after that. When either could not read what it needs, its report says what was left out: the roster's report ends "Name any subagents in the next step by hand.", and the handoff-deferral's report ends "Find the work left out in this session's dialog, and run this script again with a next step that names it." The same output then says, when a handoff-supervisor holds its lock: "Stop working now and wait — if it is watching, it takes over within seconds." The next step is already written by then, so the agent can add the missing work only by rerunning the script, and a watching handoff-supervisor may end the agent-session first. The work left out then never reaches the successor, and the script has exited 0.

Proposed: when either report names work it could not list, the writer prints the report and exits nonzero before `write_handoff_file`, so the agent names the work in the next step and reruns before anything takes over; the exit code follows #2476. This reverses the current design: `nc-systems/handoff/handoff-design.md` says that when the writer cannot read the marker file, the file of refused commands or the transcript, "it writes what it could read and tells the agent to name the rest in the next step", and the docstrings of both functions say they never block a session-handoff. It also needs a way to write the session-handoff anyway once the next step names the work by hand, because a failure that a rerun does not cure, such as `CLAUDE_CODE_SESSION_ID` being unset, would otherwise block every session-handoff. The writer can tell those failures apart itself: it could refuse only on a failure a rerun might cure, such as a transcript line still being written, and write the session-handoff on the rest.

A simpler alternative needs no refusal and keeps the design: the writer writes each failed report into the session-handoff as a field of its own, which the handoff-supervisor puts in the successor's initial-agent-instructions, so the successor learns what was not listed whatever the agent does. Both ways change the design, so this part waits on the user's ruling too.

Evidence on whether this race has lost work: none found. On 2026-11-11, `rg -z` over `/home/nedlern/nedschorus-logs`, which holds copies of the Mac's and ned-box's agent-session transcripts under `agent-session-files-by-machine/`, and over ned-box's `/home/nedlern/.claude/projects`, tallied every printed line starting `handoff-write-and-check-supervisor: handoff-deferral:` or `handoff-write-and-check-supervisor: spawned-subagent roster:`. No handoff-deferral line reports a failure. The roster lines that do, "not derived — CLAUDE_CODE_SESSION_ID is unset", appear only in subagents' transcripts and in research notes under `seats/reboot-test/`, not in the transcript of an agent-session that handed off. `rg` could not read one file, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/rv1289r1-dead-reviewer-2352/shatest/3.json` (permission denied).

### 3. The idle sweep misses Workflow-tool agents' transcripts

In `scripts/agent-seat-idle-sweep-verdicts-print.py`, `verdict_for_seat` reads the agent-session's own transcript and then looks for its subagents' transcripts by globbing `subagents/*.jsonl`, which matches only files directly in that directory. The agents that Claude Code's Workflow tool starts write their transcripts one directory deeper, under `subagents/workflows/<workflow run>/agent-*.jsonl`, as seen in ned-box's `/home/nedlern/.claude/projects` on 2026-11-11. Their token spend is left out of the verdict's `last_activity`. The verdict's `idle` is true when that spend is 5 minutes old and the agent-session's last turn has ended, so an agent-seat whose only work is a running workflow can be judged idle. `session_subagent_transcript_paths` in `scripts/handoff-context-threshold-hook.py`, which the sweep already loads as `threshold_hook`, returns both kinds of transcript.

Proposed: `verdict_for_seat` takes its subagent transcripts from `threshold_hook.session_subagent_transcript_paths`.

## Why it matters

Each gap lets running work be lost at a session-handoff, or an agent-seat be swept as idle while it works, without anyone being told. Parts 1 and 2 decide what the successor learns about the work it inherits.

## Next action

1. The user rules on part 1, the approval-walk item, and on part 2's reversal of the design.
2. Part 1, if the user approves it, is one pull request. Part 2, in whichever way the user approves, goes in the same pull request when both are approved, since both change the writer's handling of the same reports, with a test for each failure the writer reports, checking what reaches the session-handoff and the exit code.
3. Part 3 needs no ruling and can be its own pull request now, with a test that puts a transcript under `subagents/workflows/<run>/` and checks that its spend counts.

Related, read before building: [#2476](https://github.com/nedschorus/nedschorus/issues/2476), the project's design for how a program reports its outcome by exit code, for part 2; [#2257](https://github.com/nedschorus/nedschorus/issues/2257), which reads agent-seats' transcripts, for part 3.
