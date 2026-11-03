---
name: handoff
description: 'Use when a system message says the reincarnation threshold is reached or says to run the handoff skill now, or when the user asks for a handoff or to restart this agent-session; not when a message says the handoff is deferred. Writes the session-handoff your successor starts from, and the handoff-system supplies the rest; you write its first action and anything open it cannot see.'
---

# handoff

## What to do

If the user asked for this handoff while a subagent you commissioned is still working, tell the user what it is doing and how long it has been running, and ask whether to wait for it or hand off now: the handoff stops it. If a system message started the handoff, do not ask; hand off.

1. Bring your task list up to date: each piece of open work is one task whose description holds what a successor needs to do it: its files, branch, pull request, the user-rulings it rests on, and what it waits for. A question for the user that no approval-walk holds yet is a task too.
2. Write the next step into `~/.claude/handoffs/$(basename "$PWD")-next-step-$(date +%Y%m%d-%H%M%S).md` — run that expression to get the path; do not compose the name yourself. Write only these: the first action, which is what the user is waiting on, or, when he waits on nothing, the task to start first, naming an approval-walk by its name or a task by its id; the line 'Then start each ready task on your task list: a task another agent-seat owns goes to that agent-seat, any other to a background subagent or Codex.'; what must be restarted now, with its command; and what a successor needs that no task, walk-minutes, committed file or CLAUDE.md holds, with a path, or a repository and number, for each reference.
3. Run `nc-systems/handoff/handoff-write-and-check-supervisor.py --next-step-file <that file>`. Pass no `--agent` unless a refusal tells you to: it defaults to the name your supervisor watches — a session name is not it. Add `--dont-restart` if the user does not want an automatic relaunch.
4. If it reports a supervisor watching, stop working and wait — it takes over within seconds. If it reports nothing is watching, keep working and relay its printed instructions to the user. If it refuses, fix what it names and rerun.
