---
status: built
rulings-as-of: 2026-08-12
---

# Session recycling — the handoff system

**What this document is.** The handoff system is built, tested, and trial-passed; the scripts and their test suites are the normative description of what it does. This document carries only what code cannot: the rulings and their reasons, the verified harness facts the design rests on, the live holes, and the pointer below. It was gutted to that charter on 2026-08-12 (user-ruled: there is no utility in prose that documents what is better understood by reading the code — mechanism prose drifts). The full pre-gut text, mechanism descriptions included, is snapshotted at `md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md` and in git history; the superseded 2026-07-22/24 design is at `git show e178e67:docs/cross-project/fast-handoff-design.md`.

## The problem

A fleet of interactive agents running with little attention. Recycle a session before its context gets heavy — the work is mostly sequential, so old turns are disposable — without the human typing into each pane. **Compaction is rejected** for this: it summarizes uniformly when value is non-uniform, and it is slow. **`--continue`/`--resume` are rejected**: they restore the context being shed. Every relaunch is a fresh session — new id, empty window, CLAUDE.md and hooks reloaded from disk.

## The components

Each script's module docstring says what it does and why it is shaped that way; each has a `…-test.py` suite beside it stating what must keep passing.

- `scripts/handoff-context-threshold-hook.py` — the auto-trigger: a Stop hook that reads context used from the session's own transcript and tells the agent to run the skill at the threshold.
- `.claude/skills/handoff/SKILL.md` — the skill: the agent writes `next-step`, runs the writer, does what it reports. Walked and landed 2026-08-06 (dispositions in `docs/drafts/handoff-skill-draft.md`).
- `scripts/handoff-write-and-check-supervisor.py` — the writer: fills every field a machine can compute, writes the handoff file, reports supervisor liveness.
- `scripts/handoff-supervisor.py` — the supervisor: watch, kill, extract, pre-seed tasks, launch the successor with the ignition prompt; one per agent, self-registered, lock-guarded.
- `scripts/handoff-extract-conversation.py` — the extractor: carries the word-floor tail of the dialog verbatim to the successor.

## Rulings

Dated decisions and their reasons — the part of the design a reader cannot recover from code.

- **Git is the long-term record and the restore-after-problem source (boss-ruled 2026-08-02).** Handoffs are operational, machine-local, disposable. File and repo state travel by commit-as-you-go and the queues, not by handoff.
- **The successor is not dumber than the predecessor.** Carry information, not interpretation: dialog goes verbatim; no distillation, drafting, or correction ceremony.
- **Gaps cost more than over-capture.** Dialog is small next to what a session reads and writes, which is what makes frequent recycling safe.
- **Multi-machine flexibility is out of scope (boss-ruled 2026-08-02).** A machine migration is a project, not a handoff. Reopening trigger: multi-machine operation becoming an actual goal ([nedschorus#40](https://github.com/nedschorus/nedschorus/issues/40)).
- **The agent supplies only `next-step`; the writer fills every field a machine can compute (user-ruled 2026-08-06).** Hand-written fields asked the agent to do arithmetic and left silent-truncation failures open; the writer's mechanisms (file-not-argument, whitespace collapse, counter from the max of file and consumed values, refuse-empty) each answer a named observed failure, recorded in its docstring.
- **The retiring agent exercises no judgment over what its successor receives (user-ruled 2026-08-06).** The extractor's word-floor tail is the recycling boundary — the floor value and its sizing rationale live in the extractor — extended back to the nearest user prompt; `--boundary-quote` survives as a manual override only. The 5-topics rule, the "err long" hedge, and the boundary field died with this ruling.
- **`next-step` is an instruction to act on, not a summary, and every pointer carries a pin** (path + commit SHA, repository + issue number) so the successor resolves what the writer meant. Text of record: the skill (2026-08-06).
- **The skill runs one script that does everything best done by script (user-ruled 2026-08-06).** The writer and the liveness report are one command because they are one decision: a handoff nobody is watching must not stop the agent working, and an agent that runs only half of a two-step procedure would stop anyway.
- **Self-registration, not discovery (user-asked 2026-08-06).** The agent starts its own supervisor when its handoff script finds none watching; nothing scans the machine. Two questions dissolve structurally: only sessions carrying the skill ever get a supervisor, and subagents raise `SubagentStop`, not `Stop`, so the hook never fires for them. A per-agent lock refuses a second supervisor (two would double-kill and double-launch). Adoption also closed the bootstrap hole: a hand-started session can be picked up and recycled.
- **The founding boot is one committed file, no standing machinery.** Launched with the ruled prompt pattern (`claude "$(cat <path>)"` — a launcher passes the prompt; CLAUDE.md instructions do not wake a session, [nedschorus#27](https://github.com/nedschorus/nedschorus/issues/27)). A boss-called durable snapshot is an ordinary commit on request.
- **The auto-trigger reads the transcript, and only the transcript (user-ruled 2026-08-12).** The statusline relay — a second data source riding the interactive-only statusline — was cut: its sole remaining trigger was a session whose first turn had not completed, a moment the threshold cannot be crossed. The statusline renderer survives as `scripts/session-statusline-command.py`, outside this system.
- **The hook fires at the threshold unconditionally (user-ruled 2026-08-12).** Its supervisor-liveness gate was cut: self-registration made an unwatched firing self-healing (the writer starts an adopting supervisor), so silence could only turn a dead supervisor into a permanently un-recycled session. Per-agent wiring of the hook, if ever wanted, waits on an agent-naming convention and gates on being a named agent, not on liveness.
- **The queue-status line rides the ignition prompt (user-ruled 2026-08-12).** The #32 rot-visibility duty (queue depth and oldest item, visible to the boss) discharged into a log file under detached and headless supervisors; every successor now receives the line with the instruction to surface anything rotting. The console print stays for a watched pane.
- **No scheduled canary re-runs (user-ruled 2026-08-12).** Task pre-seed rides undocumented harness state, and the user does not care about the risk of a Claude Code upgrade breaking it. Detection is the successor's ignition count-check (trial-proven to fire unprompted) with the queues as backstop; the `--canary` cases in the supervisor suite are the diagnosis when it fires.

## Verified facts (2026-07-21 – 2026-08-06, Claude Code v2.1.220)

| Fact | Source |
|------|--------|
| `claude "<prompt>"` fires the prompt as the first interactive turn, in-band (dialog-safe) | canary |
| `--allowedTools` on the launch silently prevents the positional prompt from firing — never combine them in a launcher | canary (2×2) |
| An agent cannot `/clear` or `/exit` itself; self-SIGTERM trips the safety classifier (exit 143) | canary |
| Every assistant transcript record carries `message.usage` (input + cache-read + cache-creation tokens = that request's prompt size) and `message.model`; context used is therefore computable from the transcript alone, in any session | probe 2026-08-06 |
| A headless (`claude -p`) session NEVER runs the status line; statusline stdin carries `.context_window.remaining_percentage`, Stop-hook stdin does not (why the trigger reads the transcript) | probe |
| The model→context-window table lives in the threshold hook and must be re-checked when a new model ships; an unknown model id takes the 200K default, which over-fires on larger windows — the safe direction | hook source |
| Tasks are `<N>.json` under `~/.claude/tasks/<session-id>/`; the dir is created lazily; `--session-id <uuid>` forces the id; pre-seed canaries 1 and 2 passed | probe/canary |
| A task record's `id` is a STRING, and `blocks`/`blockedBy` arrays are present; a record with an integer id is dropped by TaskList while still counting toward the next allocated id — so a schema-wrong pre-seed looks half-successful | canary 2026-08-06 |
| `--continue` keeps the prior session id; a context clear mints a new id; the session id is in the environment | measured |
| A fresh subagent's context floor is CLAUDE.md + prompt | measured |

## The live recycle trial — PASSED 2026-08-06

Four generations of a headless essay-writing agent; three auto-triggered recycles with no human input; every pass criterion met (full account in the snapshotted pre-gut text). What it proved that no unit test could: exit-as-handoff is the headless norm and the supervisor reads it correctly; the clean-stop branch works; a raised threshold mid-run does not disturb the cycle; and a successor challenges inconsistent state unprompted — the behavior the ignition count-check exists to produce, and now the declared detection for pre-seed breakage.

## Known holes

- Pre-seed rides undocumented harness state; detection is the ignition count-check, the queues are the backstop, the `--canary` cases are the diagnosis (accepted risk, user-ruled 2026-08-12).
- Very-long-session material can predate the word-floor window and every durable store; bounded by commit-as-you-go and the full-JSONL pointer in every extract. A live thread longer than the floor hands over a partial thread, bounded by the header's left-behind count.
- A supervisor is a per-agent process; if it dies, nothing watches until the next threshold crossing, when the hook-fired skill run starts an adopting supervisor (self-healing since 2026-08-12; `handoff-supervisor.py --check --agent <name>` reports liveness on demand).

## Open question — attached to the seat move

**Where the successor's output goes in an interactive pane.** A self-started supervisor is detached, its output going to `<agent>-supervisor.log`, so the successor it launches inherits that rather than the terminal the person is watching — correct headless, wrong for a console pane. Recommendation: panes run their supervisor directly (the supervisor as parent), leaving adoption as the bootstrap and recovery path. Settle before the seat move.
