---
status: specification
design-as-of: 2026-08-02
---

# Session recycling — the handoff system (specification)

**Implementation status:** DESIGNED, NOT YET BUILT. This 2026-08-02 revision supersedes the 2026-07-22/24 fast-handoff design after the boss-walked reconciliation with the session-recycling design (boss + app-session agent, 2026-08-01). The superseded machinery — the numbered committed series and its retention rule, the read state table and stamps, the drafting subagent and correction pass, the scrub modes, the committed task export, the privacy-scan stage — is recoverable at `git show e178e67:docs/cross-project/fast-handoff-design.md`; what survives of it is folded below. The file keeps its historical name; the skill is named `handoff`.

## The problem

A fleet of interactive agents running with little attention. Recycle a session before its context gets heavy — the work is mostly sequential, so old turns are disposable — without the human typing into each pane. **Compaction is rejected** for this: it summarizes uniformly when value is non-uniform, and it is slow. **`--continue`/`--resume` are rejected**: they restore the context being shed. Every relaunch is a fresh session — new id, empty window, CLAUDE.md and hooks reloaded from disk.

## Governing principles

- **The conversation is the key context.** File and repo state live in the worktree and on main, fed continuously by commit-as-you-go and the queues — **git is the long-term record and the restore-after-problem source (boss-ruled 2026-08-02)**. Handoffs are operational, machine-local, disposable.
- **The successor is not dumber than the predecessor.** Carry information, not interpretation: dialog goes verbatim; there is no distillation, so no drafting or correction ceremony.
- **Gaps cost more than over-capture.** Dialog is small next to what a session reads and writes; over-capture is nearly free, which is what makes frequent recycling safe.
- **Multi-machine flexibility is deliberately out of scope (boss-ruled 2026-08-02).** A machine migration is a project, not a handoff. Reopening trigger: multi-machine operation becoming an actual goal (the server-role precondition is tracked at [nedschorus#40](https://github.com/nedschorus/nedschorus/issues/40)).

## The recycle cycle

The retiring agent — via the `handoff` skill, boss-invoked or auto-triggered — writes the handoff file:

- `written-at:` — UTC timestamp (boss-ruled 2026-08-02; consumed by the ignition prompt's elapsed-time line).
- `read-starting-here:` — the quoted first line of the user prompt that opened the current topic (a topic = a series of related turns), or the session's first prompt, whichever is nearer. A too-tight pick is harmless: the extractor widens the selection backwards to earlier user prompts until it clears a **2500-word floor** (boss-ruled 2026-08-06, sized against measured sessions at roughly eighteen exchanges), and the extract's header states how many earlier turns it left behind so a successor whose work reaches further back knows to read the transcript. The judgment call is therefore only where a topic starts, not how much to carry.
- `next-step:` — the first action the successor takes. Governed by the preserved content rule: never restate what a durable store holds — point at it; and **any pointer to mutable content carries a pin** (a commit SHA with the path, an issue number, a quoted line), so the successor resolves what the writer meant, not whatever the artifact says by read time. Correction-note style where misreading is predictable ("you will likely misread X as Y; actually Z").
- optional `dont-restart:` — the supervisor prompts `restart? y/n` instead of auto-relaunching (`y` launches, `n` exits the supervisor).
- `restart-counter:` — the predecessor's counter + 1: the semaphore the supervisor watches. Init 0 when no predecessor file exists; the supervisor records the last-consumed value in its own state file so it never refires on the same value (the consumed-marker).

The **supervisor** (one per agent, a python program running in a console) then:

1. Notices the counter change (or file mtime).
2. **Kills the session.** Agents cannot exit themselves — `/clear` and `/exit` are unavailable to the agent, and self-SIGTERM trips the safety classifier (verified) — so the supervisor owns termination.
3. **Extracts the dialog** (files-first: written to disk before anything else proceeds). The extractor derives the JSONL path from the session id the supervisor launched with — **ID-keyed lookup only**: the supervisor-known path is primary, a UUID search across the project directories is the recovery fallback, and latest-by-mtime is rejected (a second session in the same worktree makes it a race). It copies verbatim the user prompts and display messages from the boundary to EOF and appends the full-JSONL path as the need-more pointer.
4. **Migrates tasks by pre-seed**: generates the successor UUID, copies `~/.claude/tasks/<old-uuid>/*.json` into `~/.claude/tasks/<new-uuid>/`, then launches `claude --session-id <new-uuid> "<ignition prompt>"`. Canaried 2026-08-02, v2.1.220: seeded tasks are read; new task ids allocate above the seeded max; no clobber. This rides undocumented harness internals — **re-run both canaries after every Claude Code upgrade**; the backstop if an upgrade breaks it is the queues (task-shaped work belongs in GHIs by the artifact rules).
5. **Prints one automated queue-status line** — each queue's depth and oldest item, computed by script: the artifact-lifecycle rot-visibility duty riding every recycle at zero agent cost (full manual scrubs died with the committed tier; memory maintenance is the boss's drain per the #32 Q1 ruling).
6. **Launches the successor with the ignition prompt**: the exact handoff path to read; the elapsed-time line ("this handoff was written N minutes/days ago — the longer the gap, the more will have changed since"); confirm N tasks visible (the pre-seed drift tripwire); then take the next step.
7. **Local retention**: keeps the current and predecessor handoff + extract; deletes older.

## Auto-trigger

The statusline script receives `.context_window.remaining_percentage` on stdin at every refresh; one added line writes it to a side file. The Stop hook reads that file — Stop-hook stdin does not carry `context_window` (verified) — and triggers the `handoff` skill at the threshold (config, ~50% used).

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
| `handoff` skill | DRAFTED — `docs/drafts/handoff-skill-draft.md`, awaiting the user's walk |

Not yet done: wiring the status line and Stop hook into a settings file, and the first live recycle. Both belong to the user's walk-and-trial sitting, not to the code build.

## Components (the build)

1. **`extract_convo.py`** — the extractor: boundary-quote mode (recycling) and line-count mode (dead-session recovery, printed to stdout); two voices verbatim, noise dropped (tool dumps, thinking fragments, scheduled-prompt turns, subagent turns). Parser tolerances, all preserved from the founding spec: a partial last record is skipped, not fatal; a malformed line is skipped and counted, the count named in the output; per-line size is bounded so one oversized record cannot defeat the extraction; ID-keyed JSONL lookup with the UUID-search fallback.
2. **The `handoff` skill** — picks the boundary, writes `next-step` per the content rule, writes the file, waits for the supervisor.
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
- The 5-topics boundary is the retiring agent's judgment; over-capture is cheap, so the instructed error is long.
- The supervisor is a per-agent console process; if it dies, recycling stops until relaunched — visible in its console, and the agent keeps working meanwhile.
