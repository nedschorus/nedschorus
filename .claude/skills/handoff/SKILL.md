---
name: handoff
description: Hand this session over to a fresh one. A program gives your successor everything except one piece — what their first action should be to continue your work from this exact point — and writing that piece is your job. Use when a system message says the recycle threshold is reached, or when the user asks for a handoff or a restart.
---

# handoff

## What to do

1. Write in `~/.claude/handoffs/<your name>-next-step-<YYYYMMDD-HHMMSS from date>.md` the first action your successor should take. Also list any open walks or open items. List anything that needs immediate restarting. If the prompt references files, include path and commit SHA. If it references GitHub issues, include the repository and number.
2. Run `scripts/handoff-write-and-check-supervisor.py --agent <your name> --next-step-file <that file>`. Add `--dont-restart` if the user does not want an automatic relaunch.
3. If it reports a supervisor watching, stop working and wait — it takes over within seconds. If it reports nothing is watching, keep working and relay its printed instructions to the user. If it refuses, fix what it names and rerun.
