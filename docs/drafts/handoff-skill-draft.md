# handoff skill — draft for the user's walk

Proposed text for `.claude/skills/handoff/SKILL.md`. Written bare, per the skill-authoring checklist's Register rules: three questions answered — when to use it, what to do, how to do it — instructions only, no evidence or examples. The mechanics live in the code (`scripts/handoff-supervisor.py`, `scripts/handoff-extract-conversation.py`), so this text does not restate what the supervisor prints at run time.

## Walk order (opened 2026-08-06, new-vp session 5b66b6d0)

1. Purpose and the bar the text is judged by
   *processed 2026-08-06 → accepted (purpose item; no capture)*
2. The description — the trigger
   *processed 2026-08-06 → REVISED then approved. Replaced with the user's "everything except one piece" framing; the trigger is now an observable system message rather than a self-assessed context level (an agent cannot see its own context percentage, so the old phrasing was a judgment call dressed as a condition); file mechanics dropped from the description so the always-in-context text cannot compete with the body; the near-miss negative clause declined — both triggers are observable events, so an agent working on the handoff system receives neither, and speculative rules are not added.*
3. When Used
   *processed 2026-08-06 → DELETED entirely (user): agents are not expected to self-trigger, so a body section restating the trigger has no reader. Its other two facts were already carried where they act — step 3 says stop working and wait for the supervisor, and How to do it says the dialog is carried for you. A proposed fold about tasks carrying over was withdrawn: nothing in this skill asks the agent to touch its tasks, and mentioning them would invite that. The body now opens on What to do.*
4. What to do, step 1 — writing next-step
   *processed 2026-08-06 → REVISED then approved (user-authored text). "Clear and complete" replaces the draft's bare instruction, bounded by what the successor already has: it reads the last few thousand words of the conversation before acting. Pinning is now two observable cases — a file reference carries path and commit SHA, a GitHub issue reference carries repository and number. Dropped: the don't-restate-a-durable-store rule (the context bound covers it) and the pre-correct-misreadings rule (general good writing, not project-unique). "GHI" expanded to "GitHub issue" per floor line 4's standard-SDLC-terms rule, though a cold probe confirmed agents understand the shorthand.*
5. What to do, step 2 — the handoff file and its fields
   *processed 2026-08-06 → REVISED then approved. The user ruled that the script fills every scriptable field; the design had never said so — it assigned all four fields to the agent and listed no writer among its five components. `scripts/handoff-write-file.py` now stamps the timestamp, derives the counter, and writes the file; the skill's step is one command. This also closed a silent defect: the supervisor parses `key: value` lines, so a next-step containing a newline was truncated at its first line with no error, and the newly approved "clear and complete" wording made that more likely. The writer collapses whitespace to one line (user-ruled), takes the prompt as a file so a shell cannot mangle backticks, and derives the counter from the higher of the previous file's value and the supervisor's consumed value so a stale file cannot produce a counter the supervisor ignores. 23 cases green.*
6. What to do, step 3 — the supervisor liveness check
7. How to do it — path, counter, the never-summarize rule
8. Ratification: the threshold-hook instruction deletion landed this session

Everything below the line is the proposed skill file, verbatim.

---

```
---
name: handoff
description: Hand this session over to a fresh one. A program gives your successor everything except one piece — what their first action should be to continue your work from this exact point — and writing that piece is your job. Use when a system message says the recycle threshold is reached, or when the user asks for a handoff or a restart.
---

# handoff

## What to do

1. Write a clear and complete prompt telling your successor what their first action should be. Your successor will read the last few thousand words of this conversation before acting on your prompt, so it will have that context. If your prompt references a file, include its path and commit SHA. If it references a GitHub issue, include the repository and number.
2. Run `scripts/handoff-write-file.py --agent <your name> --next-step-file <the file holding your prompt>`. It stamps the time, sets the restart counter, and writes the handoff file your supervisor watches. Add `--dont-restart` only when the user asked to be consulted before a relaunch.
3. Check that a supervisor is watching: run `scripts/handoff-supervisor.py --check --agent <your name>`. If it reports one alive, stop working and wait — the supervisor takes over within seconds. If it reports none, do not stop: tell the user that the handoff is written but nothing is watching for it, and keep working until they start a supervisor or tell you otherwise.

## How to do it

The handoff file is `~/.claude/handoffs/<agent>-handoff.md` unless your supervisor was started with a different directory, in which case pass that directory to the writer with `--handoff-dir`.

The dialog is carried for you, and how much of it is not yours to decide — never paste conversation into the handoff file, and never try to summarize the session. Anything the successor needs that is not in the recent dialog and not in a durable store goes in the next step.
```
