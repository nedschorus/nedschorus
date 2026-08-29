---
name: handoff
description: Hand this session over to a fresh one. A program gives your successor everything except one piece — what their first action should be to continue your work from this exact point — and writing that piece is your job. Use when a system message says the recycle threshold is reached, or when the user asks for a handoff or a restart.
---

# handoff

## What to do

1. Write a clear and complete prompt telling your successor what their first action should be. It is an instruction to act on, not a summary of this session. Your successor will read the last few thousand words of this conversation before acting on your prompt, so it will have that context. If your prompt references a file, include its path and commit SHA. If it references a GitHub issue, include the repository and number. If you stamp the current time, take it from `date`.
2. Run `scripts/handoff-write-and-check-supervisor.py --agent <your name> --next-step-file <the file holding your prompt>`. It stamps the time, sets the restart counter, records the subagents this session spawned so your successor can restart the ones still owing work, writes the handoff file, and reports whether a supervisor is watching. Add `--dont-restart` only when the user asked to be consulted before a relaunch.
3. Do what it reports. When it found a supervisor watching, or started one, stop working and wait — it takes over within seconds. When it reports it could not start one, do not stop: keep working, and tell the user that the handoff is written but nothing is watching for it.
