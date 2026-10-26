---
name: handoff
description: 'Use when a system message says the reincarnation threshold is reached, or when the user asks for a handoff or to restart this agent-session. Writes the session-handoff your successor starts from: the handoff-system supplies the rest, and you write its first action and anything open it cannot see.'
---

# handoff

## What to do

If the user asked for this handoff while a subagent you commissioned is still working, tell the user what it is doing and how long it has been running, and ask whether to wait for it or hand off now: the handoff stops it. If a system message started the handoff, do not ask; hand off.

1. Write the first action your successor should take into `~/.claude/handoffs/$(basename "$PWD")-next-step-$(date +%Y%m%d-%H%M%S).md` — run that expression to get the path; do not compose the name yourself. Make the first action whatever the user is waiting on; when that includes items of open approval-walks, write in the next step that your successor carries every item the user has not answered, deferred items included, first, into one new approval-walk, naming each item and linking the walk-document and walk-minutes it came from; then tell your successor to start each ready task on its task list, as the project glossary defines ready: a task another agent-seat owns goes to that agent-seat, and any other to a background subagent or Codex. When the user is waiting on nothing, starting the ready tasks is the first action. Also list any open approval-walks or open items. List anything that needs immediate restarting. If the prompt references files, include the path. If it references GitHub issues, include the repository and number.
2. Run `nc-systems/handoff/handoff-write-and-check-supervisor.py --next-step-file <that file>`. Pass no `--agent` unless a refusal tells you to: it defaults to the name your supervisor watches — a session name is not it. Add `--dont-restart` if the user does not want an automatic relaunch.
3. If it reports a supervisor watching, stop working and wait — it takes over within seconds. If it reports nothing is watching, keep working and relay its printed instructions to the user. If it refuses, fix what it names and rerun.
