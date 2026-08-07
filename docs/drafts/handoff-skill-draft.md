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
   *processed 2026-08-06 → REVISED then approved. The user ruled that the script fills every scriptable field; the design had never said so — it assigned all four fields to the agent and listed no writer among its five components. `scripts/handoff-write-and-check-supervisor.py` now stamps the timestamp, derives the counter, writes the file, and reports supervisor liveness; the skill's steps 2 and 3 collapse to one command plus following what it reports. This also closed a silent defect: the supervisor parses `key: value` lines, so a next-step containing a newline was truncated at its first line with no error, and the newly approved "clear and complete" wording made that more likely. The writer collapses whitespace to one line (user-ruled), takes the prompt as a file so a shell cannot mangle backticks, and derives the counter from the higher of the previous file's value and the supervisor's consumed value so a stale file cannot produce a counter the supervisor ignores. 27 cases green.*
6. What to do, step 3 — the supervisor liveness check
   *processed 2026-08-06 → REVISED then approved. The two-command procedure collapsed into one: the script reports, the agent obeys. The user then asked why the script does not simply start a supervisor when none is watching, which closed the bootstrap hole — a session started by hand could never recycle, because a supervisor could only terminate a process it had launched itself. The script now starts an adopting supervisor, so step 3's branches are found-or-started (stop and wait) versus could-not-start (keep working and tell the user). Self-registration, not discovery: the session identifies itself from its own environment, so nothing scans for supervisable sessions, and subagents — which never run the skill and raise SubagentStop rather than Stop — are excluded structurally. One input remains unscriptable until NC has an agent-naming convention: the agent's own name.*
7. How to do it — path, counter, the never-summarize rule
   *processed 2026-08-06 → DELETED entirely, with one sentence folded into step 1. The path and --handoff-dir paragraph became the script's business once the agent stopped writing the file. The never-paste/never-summarize paragraph carried two absolutes against floor line 6, and its last clause restated approved step 1 more weakly. What survived is the live risk — "clear and complete" licenses a longer prompt, so an agent could write a session summary instead of an instruction — restated positively as what the output IS, per the authoring checklist's finding that a positive recipe beats a prohibition. The skill is now a description and three numbered steps, with no trailing prose.*
8. Ratification: the threshold-hook instruction deletion landed this session
   *processed 2026-08-06 → REVISED then approved. The fired message is now exactly "Run the handoff skill now." The user cut the whole remainder: the used-percentage and threshold report (informational, changes nothing the agent does), the procedure clause, and the reassurance sentence. The procedure clause had gone stale twice in one day — once when boundary judgment was removed, once when the writer took over the fields — which is what a second copy of a procedure does. Its test case, which asserted the percentage appeared, was replaced by an exact-match assertion so re-adding any procedure text fails the suite.*

Everything below the line is the proposed skill file, verbatim.

---

```
---
name: handoff
description: Hand this session over to a fresh one. A program gives your successor everything except one piece — what their first action should be to continue your work from this exact point — and writing that piece is your job. Use when a system message says the recycle threshold is reached, or when the user asks for a handoff or a restart.
---

# handoff

## What to do

1. Write a clear and complete prompt telling your successor what their first action should be. It is an instruction to act on, not a summary of this session. Your successor will read the last few thousand words of this conversation before acting on your prompt, so it will have that context. If your prompt references a file, include its path and commit SHA. If it references a GitHub issue, include the repository and number.
2. Run `scripts/handoff-write-and-check-supervisor.py --agent <your name> --next-step-file <the file holding your prompt>`. It stamps the time, sets the restart counter, writes the handoff file, and reports whether a supervisor is watching. Add `--dont-restart` only when the user asked to be consulted before a relaunch.
3. Do what it reports. When it found a supervisor watching, or started one, stop working and wait — it takes over within seconds. When it reports it could not start one, do not stop: keep working, and tell the user that the handoff is written but nothing is watching for it.
```
