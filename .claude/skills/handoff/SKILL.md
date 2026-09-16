---
name: handoff
description: Hand this session over to a fresh one. A program gives your successor everything except one piece — what their first action should be to continue your work from this exact point — and writing that piece is your job. Use when a system message says the reincarnation threshold is reached, or when the user asks for a handoff or a restart.
---

# handoff

## What to do

1. Write the first action your successor should take into `~/.claude/handoffs/$(basename "$PWD")-next-step-$(date +%Y%m%d-%H%M%S).md` — run that expression to get the path; do not compose the name yourself. Also list any open walks or open items. List anything that needs immediate restarting. If the prompt references files, include the path. If it references GitHub issues, include the repository and number.
2. Run `scripts/handoff-write-and-check-supervisor.py --next-step-file <that file>`. Pass no `--agent` unless a refusal tells you to: it defaults to your working directory's name, which is the seat name your supervisor watches — a session name is not it. Add `--dont-restart` if the user does not want an automatic relaunch.
3. If it reports a supervisor watching, stop working and wait — it takes over within seconds. If it reports nothing is watching, keep working and relay its printed instructions to the user. If it refuses, fix what it names and rerun.
