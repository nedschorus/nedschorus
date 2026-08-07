---
status: specification
design-as-of: 2026-08-02
---

# Session recycling — the handoff system (specification)

**Implementation status:** BUILT and trial-passed 2026-08-06 (see the build-status table and the live recycle trial below); the `handoff` skill text is the only component still in its walk. This 2026-08-02 revision supersedes the 2026-07-22/24 fast-handoff design after the boss-walked reconciliation with the session-recycling design (boss + app-session agent, 2026-08-01). The superseded machinery — the numbered committed series and its retention rule, the read state table and stamps, the drafting subagent and correction pass, the scrub modes, the committed task export, the privacy-scan stage — is recoverable at `git show e178e67:docs/cross-project/fast-handoff-design.md`; what survives of it is folded below. The file keeps its historical name; the skill is named `handoff`.

## The problem

A fleet of interactive agents running with little attention. Recycle a session before its context gets heavy — the work is mostly sequential, so old turns are disposable — without the human typing into each pane. **Compaction is rejected** for this: it summarizes uniformly when value is non-uniform, and it is slow. **`--continue`/`--resume` are rejected**: they restore the context being shed. Every relaunch is a fresh session — new id, empty window, CLAUDE.md and hooks reloaded from disk.

## Governing principles

- **The conversation is the key context.** File and repo state live in the worktree and on main, fed continuously by commit-as-you-go and the queues — **git is the long-term record and the restore-after-problem source (boss-ruled 2026-08-02)**. Handoffs are operational, machine-local, disposable.
- **The successor is not dumber than the predecessor.** Carry information, not interpretation: dialog goes verbatim; there is no distillation, so no drafting or correction ceremony.
- **Gaps cost more than over-capture.** Dialog is small next to what a session reads and writes; over-capture is nearly free, which is what makes frequent recycling safe.
- **Multi-machine flexibility is deliberately out of scope (boss-ruled 2026-08-02).** A machine migration is a project, not a handoff. Reopening trigger: multi-machine operation becoming an actual goal (the server-role precondition is tracked at [nedschorus#40](https://github.com/nedschorus/nedschorus/issues/40)).

## The recycle cycle

The retiring agent — via the `handoff` skill, boss-invoked or auto-triggered — writes its successor's opening prompt to a file and runs the writer, `scripts/handoff-write-and-check-supervisor.py`, which produces the handoff file. **The agent supplies only `next-step`; the writer fills every field a machine can compute (user-ruled 2026-08-06).** The earlier design had the agent hand-write all four fields, which asked it to find and read the previous handoff purely to do arithmetic, and left a silent failure open: the supervisor parses `key: value` lines, so a `next-step` containing a newline was truncated at its first line with no error. The writer collapses whitespace to one line, so that cannot happen. It also takes the next step as a FILE, not an argument — a shell mangles backticks and quotes inside an inline argument — and derives the counter from the higher of the previous handoff's value and the supervisor's consumed value, so a missing or stale handoff file cannot produce a counter the supervisor ignores.

The fields:

- `written-at:` — UTC timestamp (boss-ruled 2026-08-02; consumed by the ignition prompt's elapsed-time line).
- ~~`read-starting-here:`~~ — **REMOVED 2026-08-06 (user-ruled): the retiring agent exercises no judgment over what its successor receives.** The extractor carries the tail of the conversation that clears a **2500-word floor** — roughly eighteen exchanges, sized against measured sessions — extended back to the nearest user prompt so the extract opens on a clean turn. The header states how many earlier turns were left behind, which makes reading further from the transcript an informed choice rather than a blind one. The 5-topics boundary rule, the "err long" hedge, and the boundary field all died with this ruling; `--boundary-quote` survives in the extractor as a manual override only.
- `next-step:` — the first action the successor takes. Governed by the preserved content rule: never restate what a durable store holds — point at it; and **any pointer to mutable content carries a pin** (a commit SHA with the path, an issue number, a quoted line), so the successor resolves what the writer meant, not whatever the artifact says by read time. Correction-note style where misreading is predictable ("you will likely misread X as Y; actually Z").
- optional `dont-restart:` — the supervisor prompts `restart? y/n` instead of auto-relaunching (`y` launches, `n` exits the supervisor).
- `restart-counter:` — the semaphore the supervisor watches, written by the writer as one above the highest value either the previous handoff file or the supervisor's state records. The supervisor records the last-consumed value in its own state file so it never refires on the same value (the consumed-marker).

The **supervisor** (one per agent, a python program running in a console) then:

1. Notices the counter change (or file mtime).
2. **Kills the session.** Agents cannot exit themselves — `/clear` and `/exit` are unavailable to the agent, and self-SIGTERM trips the safety classifier (verified) — so the supervisor owns termination.
3. **Extracts the dialog** (files-first: written to disk before anything else proceeds). The extractor derives the JSONL path from the session id the supervisor launched with — **ID-keyed lookup only**: the supervisor-known path is primary, a UUID search across the project directories is the recovery fallback, and latest-by-mtime is rejected (a second session in the same worktree makes it a race). It copies verbatim the user prompts and display messages from the boundary to EOF and appends the full-JSONL path as the need-more pointer.
4. **Migrates tasks by pre-seed**: generates the successor UUID, copies `~/.claude/tasks/<old-uuid>/*.json` into `~/.claude/tasks/<new-uuid>/`, then launches `claude --session-id <new-uuid> "<ignition prompt>"`. Canaried 2026-08-02, v2.1.220: seeded tasks are read; new task ids allocate above the seeded max; no clobber. This rides undocumented harness internals — **re-run both canaries after every Claude Code upgrade**; the backstop if an upgrade breaks it is the queues (task-shaped work belongs in GHIs by the artifact rules).
5. **Prints one automated queue-status line** — each queue's depth and oldest item, computed by script: the artifact-lifecycle rot-visibility duty riding every recycle at zero agent cost (full manual scrubs died with the committed tier; memory maintenance is the boss's drain per the #32 Q1 ruling).
6. **Launches the successor with the ignition prompt**: the exact handoff path to read; the elapsed-time line ("this handoff was written N minutes/days ago — the longer the gap, the more will have changed since"); confirm N tasks visible (the pre-seed drift tripwire); then take the next step.
7. **Local retention**: keeps the current and predecessor handoff + extract; deletes older.

## Auto-trigger — read cost

The supervisor's poll never touches the transcript: it stats the handoff file and stamps its heartbeat, nothing more. The transcript is read only by the Stop hook, once per turn boundary, and only from the end — the newest assistant record is all that matters, so the hook reads a 256KB tail and doubles the window until it finds that record. Measured on a 5.8MB transcript: 0.3ms, against 23ms for a whole-file parse, and the gap widens as a session grows because the tail read does not scale with file size.

## Auto-trigger

The statusline script receives `.context_window.remaining_percentage` on stdin at every refresh; one added line writes it to a side file. The Stop hook reads that file — Stop-hook stdin does not carry `context_window` (verified) — and triggers the `handoff` skill at the threshold (config, ~50% used).

## Who starts the supervisor — self-registration, not discovery

A supervisor watches exactly one agent, and **the agent starts it** when its handoff script finds none watching (user-asked 2026-08-06). Nothing scans the machine for sessions to supervise, and nothing needs to: the running session identifies itself from its own environment — `CLAUDE_CODE_SESSION_ID` and `CLAUDE_PID`, both verified present 2026-08-06 — and passes those to the supervisor it starts, which adopts that one process. Two questions dissolve rather than being answered:

- **Which sessions can be handed off?** Only ones carrying the `handoff` skill and this script, because only they ever call it. An agent without them never starts a supervisor, so no supervisor exists for it.
- **What about subagents?** They do not run the skill, and their turn boundaries raise `SubagentStop` rather than `Stop`, so the threshold hook never fires for them.

`AdoptedSession` gives the supervisor the same interface over a process id that `subprocess.Popen` gives over a process it launched — poll, terminate, kill, wait — so everything after the kill is the ordinary cycle, unchanged. A per-agent lock file (`<agent>-supervisor.lock`, holder process id recorded, stale locks reclaimed) refuses a second supervisor: two would each kill the session and each launch a successor.

This also closes the bootstrap hole. Before adoption, a session started by hand could never recycle, because a supervisor could only terminate a process it had launched itself — which meant the founding boot below, and any agent a person started in a console, was permanently unrecyclable.

Verified live 2026-08-06: a supervisor adopted a process it had not launched, killed it on the handoff, extracted the dialog, carried 50 task records, launched the successor with the full ignition prompt, and released its lock on exit.

## The founding boot — the one committed handoff

Choirmaster's first boot has no predecessor session and no supervisor. The founding handoff is written by the founding pair, committed as an ordinary file, and launched with the ruled prompt pattern (`claude "$(cat <path>)"` — the launcher passes the prompt; CLAUDE.md instructions do not wake a session, [nedschorus#27](https://github.com/nedschorus/nedschorus/issues/27)). After that boot, recycling owns everything. No standing committed-handoff machinery exists; a boss-called durable snapshot is an ordinary commit on request.

## Build status (2026-08-06)

Four of the five components are built, tested, and on main; the fifth is the skill text, which is instruction-class and lands after its walk.

| Component | State |
|---|---|
| Extractor | BUILT — `scripts/handoff-extract-conversation.py`, 23-case suite (`…-test.py`), live-validated against a real transcript |
| Supervisor | BUILT — `scripts/handoff-supervisor.py`, 24 offline cases plus both live pre-seed canaries green |
| Auto-trigger | BUILT — `scripts/handoff-statusline-context-relay.py` + `scripts/handoff-context-threshold-hook.py`, 14-case suite |
| Ignition prompt | BUILT — `build_ignition_prompt` in the supervisor: dialog path, elapsed-time line, task count, next step |
| Writer | BUILT — `scripts/handoff-write-and-check-supervisor.py`, 27-case suite (`…-test.py`); added 2026-08-06 when the user ruled that the script does everything best done by script |
| `handoff` skill | BUILT — `.claude/skills/handoff/SKILL.md`, walked and landed 2026-08-06 (eight items, per-item dispositions in `docs/drafts/handoff-skill-draft.md`); executed cold by four trial generations, which handed off correctly from the drafted text |

Not yet done: wiring the Stop hook into NC's own settings file, which belongs to the seat move rather than the code build. Every component is now built, tested, and walked.

## The live recycle trial — PASSED 2026-08-06

A headless Opus agent (`claude -p`, no subagents) seeded with 100 essay topics turned them into 50 tasks and wrote ~1000-word essays one per turn, so context filled from its own output. Four generations ran; three auto-triggered recycles happened with no human input. All four pass criteria met:

| Criterion | Result |
|---|---|
| Sessions recycle without the user typing | 3 recycles: generations 0→1→2→3, each an auto-triggered handoff, kill, extract, task carry, relaunch |
| Each successor reports the expected task count | Generation 1 opened "50 tasks are visible — count confirmed"; every generation confirmed before working |
| The task list drains across generations | 14 essays written by four sessions sharing one carried task store, tasks marked completed in order |
| The dialog files hold the real conversation | `essayist-dialog-000N.md` carry the ignition prompt, the count confirmation, the essay summaries, and the threshold-hook moment |

What the trial proved that no unit test could:

- **Exit-as-handoff is the headless norm, and the supervisor now reads it correctly.** Every one of the three recycles arrived as a process exit, not as a file change observed while running. Before the fix (`wait_for_handoff` returning None on exit before checking the file) the trial would have stopped at the first handoff.
- **A raised threshold mid-run does not disturb the cycle.** The threshold was 5.5% for generations 0–2 and 8% for generation 3; recycling behaved identically, confirming the mechanism is threshold-independent.
- **The clean-stop branch works.** With no pending tasks left, the final session exited without writing a handoff and the supervisor printed "session ended without a handoff; supervisor stopping" and exited 0 — the terminal branch the exit-handling fix also touches.
- **A successor challenges inconsistent state rather than proceeding.** To reach the drain condition without writing 36 more essays, task records were closed directly on disk. The generation-3 agent reported the discrepancy unprompted: 50 tasks read completed while `essays/` held 14 files. The carried dialog gave it enough context to notice, which is the behavior the ignition prompt's count-check exists to produce.

Trial-only scaffolding, not part of the system: a driver Stop hook produced one-essay-per-turn boundaries (an agent told to finish everything in one turn never reaches a Stop boundary, so the threshold hook could never fire), and the sandbox ran outside NC so essay churn stayed out of the repository.

## Components (the build)

1. **`extract_convo.py`** — the extractor: boundary-quote mode (recycling) and line-count mode (dead-session recovery, printed to stdout); two voices verbatim, noise dropped (tool dumps, thinking fragments, scheduled-prompt turns, subagent turns). Parser tolerances, all preserved from the founding spec: a partial last record is skipped, not fatal; a malformed line is skipped and counted, the count named in the output; per-line size is bounded so one oversized record cannot defeat the extraction; ID-keyed JSONL lookup with the UUID-search fallback.
2. **The `handoff` skill** — writes `next-step` per the content rule, runs the writer, waits for the supervisor (boundary judgment removed 2026-08-06; the extractor's word-floor tail decides what carries).
2a. **`handoff-write-and-check-supervisor.py`** — the writer: stamps the timestamp, derives the restart counter, collapses the next step to one line, writes the handoff file atomically, then reports whether a supervisor is watching and what that means for the agent. Refuses an empty next step rather than booting a successor with no instruction. The liveness report lives here rather than in a second command because the two are one decision — a handoff nobody is watching must not stop the agent working, and an agent that runs only the first half of a two-step procedure would stop anyway (user-ruled 2026-08-06: the skill runs one script that does everything best done by script).
3. **The statusline relay + Stop hook** — the auto-trigger.
4. **The supervisor** — watch, kill, extract, pre-seed, queue-status line, launch; consumed-marker state; the `dont-restart` y/n gate.
5. **The ignition prompt template** — path, elapsed-time line, task count, next step.

## Verified facts (2026-07-21 – 2026-08-02, Claude Code v2.1.220)

| Fact | Source |
|------|--------|
| `claude "<prompt>"` fires the prompt as the first interactive turn, in-band (dialog-safe) | canary |
| `--allowedTools` on the launch silently prevents the positional prompt from firing — never combine them in a launcher | canary (2×2) |
| An agent cannot `/clear` or `/exit` itself; self-SIGTERM trips the safety classifier (exit 143) | canary |
| Statusline stdin carries `.context_window.remaining_percentage`; Stop-hook stdin does not | probe |
| A headless (`claude -p`) session NEVER runs the status line, so the relay file is never written and a statusline-only auto-trigger cannot fire there | probe 2026-08-06 |
| Every assistant transcript record carries `message.usage` (input + cache-read + cache-creation tokens = that request's prompt size) and `message.model`; context used is therefore computable from the transcript alone, in any session | probe 2026-08-06 |
| Context windows: Fable 5, Opus 5, Sonnet 5, and the Opus 4.x line are 1M; Haiku 4.5 is 200K (source: the claude-api reference skill, read 2026-08-06 — not inferred) | reference |
| Tasks are `<N>.json` under `~/.claude/tasks/<session-id>/`; the dir is created lazily; `--session-id <uuid>` forces the id; pre-seed canaries 1 and 2 passed | probe/canary |
| A task record's `id` is a STRING, and `blocks`/`blockedBy` arrays are present; a record with an integer id is dropped by TaskList while still counting toward the next allocated id — so a schema-wrong pre-seed looks half-successful | canary 2026-08-06 |
| `--continue` keeps the prior session id | boss-measured 2026-07-21 |
| A context clear mints a new session id; the session id is in the environment | measured |
| A fresh subagent's context floor is CLAUDE.md + prompt | measured |
| JSONL extraction of a closed session yields readable dialog | measured |

## Tests

- **Extractor**: the four tolerance fixtures (partial tail; malformed line skipped and counted; oversized line bounded; subagent turns dropped as deliberate classification), boundary-quote start, line-count mode, cross-directory ID search, empty/unparseable refusal.
- **Supervisor**: semaphore init and consumed-marker (no refire after relaunch), `dont-restart` y/n paths, kill → extract → launch ordering (files-first verified), local retention old+new, task pre-seed as executable canaries (re-run per upgrade), ignition prompt contains path + elapsed-time line + task count.
- **Trigger**: threshold crossing fires the skill exactly once.

## Known holes

- Pre-seed rides undocumented harness state; bounded by the ignition count-check and the per-upgrade canaries; the queues are the backstop.
- Very-long-session material can predate the boundary window and every durable store; bounded by commit-as-you-go and the full-JSONL pointer.
- ~~The 5-topics boundary is the retiring agent's judgment~~ — closed 2026-08-06: the boundary is mechanical (a 2500-word tail), so this hole no longer exists. What remains is the floor's size itself: a session whose live thread runs longer than 2500 words hands over a partial thread, bounded by the header's left-behind count and the transcript pointer.
- The supervisor is a per-agent console process; if it dies, recycling stops until relaunched. Detectable since 2026-08-06 (user-asked): the supervisor stamps `last_poll_at` into its state file every ten seconds while watching, and `handoff-supervisor.py --check --agent <name>` reports liveness (exit 0 alive, 1 not). Both consumers use it — the skill checks before it stops working, so a dead supervisor yields a plain report to the user rather than a session hung forever waiting to be killed; the threshold hook stays silent when nothing is watching, so it cannot ask for a handoff nobody will act on.
