---
name: handoff
description: Hand this session over to a fresh one. A program gives your successor everything except one piece — what their first action should be to continue your work from this exact point — and writing that piece is your job. Use when a system message says the recycle threshold is reached, or when the user asks for a handoff or a restart.
---

# handoff

## What to do

1. Tell your successor what their first action should be. List any open walks or open items. List anything that needs immediate restarting. If your prompt references a file, include its path and commit SHA. If it references a GitHub issue, include the repository and number. 
2. Run `scripts/handoff-write-and-check-supervisor.py --agent <your name> --next-step-file <the file holding your prompt>`. It stamps the time of the handoff, sets the restart counter, records the subagents this session spawned so your successor can restart the ones still owing work, writes the handoff file, and reports whether a supervisor is watching. Add `--dont-restart` only when the user asked to be consulted before a relaunch.
3. Do what it reports. When it found a supervisor watching, or started one, stop working and wait — it takes over within seconds. When it reports it could not start one, do not stop: keep working, and tell the user that the handoff is written but nothing is watching for it.
