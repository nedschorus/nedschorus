# handoff skill — draft for the user's walk

Proposed text for `.claude/skills/handoff/SKILL.md`. Written bare, per the skill-authoring checklist's Register rules: three questions answered — when to use it, what to do, how to do it — instructions only, no evidence or examples. The mechanics live in the code (`scripts/handoff-supervisor.py`, `scripts/handoff-extract-conversation.py`), so this text does not restate what the supervisor prints at run time.

## Walk order (opened 2026-08-06, new-vp session 5b66b6d0)

1. Purpose and the bar the text is judged by
2. The description — the trigger
3. When Used
4. What to do, step 1 — writing next-step
5. What to do, step 2 — the handoff file and its fields
6. What to do, step 3 — the supervisor liveness check
7. How to do it — path, counter, the never-summarize rule
8. Ratification: the threshold-hook instruction deletion landed this session

Everything below the line is the proposed skill file, verbatim.

---

```
---
name: handoff
description: Hand this session over to a fresh one — write the file that tells your successor where the conversation stopped and what to do next. Use when context is running low, when the user asks for a handoff or a restart, or when the auto-trigger asks for one.
---

# handoff

## When Used

When this session should end and a fresh one continue its work: context is running low, the user asks for a handoff or a restart, or the context-threshold hook asks for one. The supervisor watching this session does the rest — it stops this session, extracts the dialog, carries the tasks, and launches the successor.

## What to do

1. Write the next step: the first action the successor takes. Name what a durable store already holds rather than restating it, and pin every pointer to something that will not move — a commit SHA with its path, an issue number, a quoted line. Where the successor is likely to misread something, say so plainly and give the correct reading.
2. Write the handoff file at the path your supervisor watches, with these fields, one per line:
   - `written-at:` the current UTC time, ISO 8601
   - `next-step:` the next step from step 1
   - `restart-counter:` the previous handoff's counter plus one, or 1 if there is no previous handoff
   - `dont-restart:` include this only when the user asks not to be relaunched automatically
3. Check that a supervisor is watching: run `scripts/handoff-supervisor.py --check --agent <your name>`. If it reports one alive, stop working and wait — the supervisor takes over within seconds. If it reports none, do not stop: tell the user that the handoff is written but nothing is watching for it, and keep working until they start a supervisor or tell you otherwise.

## How to do it

The handoff file is `~/.claude/handoffs/<agent>-handoff.md` unless your supervisor was started with a different directory. Read the existing file first to get the counter to increment.

The dialog is carried for you, and how much of it is not yours to decide — never paste conversation into the handoff file, and never try to summarize the session. Anything the successor needs that is not in the recent dialog and not in a durable store goes in the next step.
```
