---
status: built
rulings-as-of: 2026-08-27
---

# Session recycling — the handoff system

**What this document is.** The handoff system is built, tested, and trial-passed; the scripts and their test suites are the normative description of what it does. This document carries only what code cannot: the rulings and their reasons, the verified harness facts the design rests on, the live holes, and the pointer below. It was gutted to that charter on 2026-08-12 (user-ruled: there is no utility in prose that documents what is better understood by reading the code — mechanism prose drifts). The full pre-gut text, mechanism descriptions included, is snapshotted at `git show db917b5:md-review-records/2026-08-12-fast-handoff-sanity-check/reviewed-fast-handoff-design.md` and in git history; the superseded 2026-07-22/24 design is at `git show e178e67:docs/cross-project/fast-handoff-design.md`.

## The problem

A fleet of interactive agents running with little attention. Recycle a session before its context gets heavy — the work is mostly sequential, so old turns are disposable — without the human typing into each pane. **Compaction is rejected** for this: it summarizes uniformly when value is non-uniform, and it is slow. **`--continue`/`--resume` are rejected**: they restore the context being shed. Every relaunch is a fresh session — new id, empty window, CLAUDE.md and hooks reloaded from disk.

## The components

Each script's module docstring says what it does and why it is shaped that way; each has a `…-test.py` suite beside it stating what must keep passing.

- `scripts/handoff-context-threshold-hook.py` — the auto-trigger: a Stop hook that reads context used from the session's own transcript and tells the agent to run the skill at the threshold — or, while one of the session's subagents is still in flight and context is below the ceiling, that the handoff is deferred until it finishes (next section).
- `.claude/skills/handoff/SKILL.md` — the skill: the agent writes `next-step`, runs the writer, does what it reports. Walked and landed 2026-08-06 (dispositions in `docs/drafts/handoff-skill-draft.md`).
- `scripts/handoff-write-and-check-supervisor.py` — the writer: fills every field a machine can compute, writes the handoff file, reports supervisor liveness.
- `scripts/handoff-supervisor.py` — the supervisor: watch, kill, extract, pre-seed tasks, launch the successor with the ignition prompt; one per agent, self-registered, lock-guarded.
- `scripts/handoff-extract-conversation.py` — the extractor: carries the word-floor tail of the dialog verbatim to the successor.

## What a recycle kills, and how work survives it

A recycle kills the session, and the session's in-process subagents die with it: a subagent runs inside the process the supervisor terminates, and no field of the handoff can carry a running one across. On 2026-08-27 a seat dispatched a builder subagent at 20:38; the threshold hook fired at 50% at 20:43, the handoff ran, the supervisor killed the session, and the subagent died four minutes into its job.

**The deferral makes that rare, and it is the one exception to record-not-wait (user-ruled 2026-08-27).** The threshold hook holds the recycle while any Agent-tool subagent is in flight, up to `--ceiling-used-percentage`; past the ceiling it fires whatever is running, because a session waiting on a subagent that does not finish runs out of context instead of recycling, which loses more. The 2026-08-23 ruling that a recycle records its subagents rather than waiting for them ([nedschorus#153](https://github.com/nedschorus/nedschorus/pull/153)) governs everything else. The deferral postpones the kill; it does not retire it. A subagent still dies at the ceiling, on a crash, and on any exit the hook is not there to see.

**So a brief for a job longer than one step says how the work survives a kill.** The subagent reads only the brief it was given, so both requirements go in the brief: commit after each step, and keep a report file rewritten after each step rather than composed at the end. A kill then costs the step in progress and nothing behind it, and whoever picks the job up reads the commits and the report instead of reconstructing intent from an absence.

**Subagents, forks included, are the default way to dispatch work.** They report back on their own, the roster records them, the deferral protects them, and their output reaches the commissioning session without anyone watching a pane.

**A detached headless session is the explicit exception**, for an unattended job measured in hours rather than one that fits in a session's remaining context. It buys freedom from the recycle and pays in tracking, so a brief that chooses it names that cost where its reader will meet it:

- **No completion notification.** Nothing wakes the commissioning session when the job ends; someone goes and looks.
- **Its own permission mode**, fixed at launch rather than inherited from the session that dispatched it.
- **Nobody watches it wedge.** Stuck-state detection is the open gap in [nedschorus#27](https://github.com/nedschorus/nedschorus/issues/27), so a headless job that stalls stalls quietly.
- **It is invisible to the spawned-subagent roster** ([nedschorus#153](https://github.com/nedschorus/nedschorus/pull/153), open at the time of writing), which reads the session transcript for spawns the Agent tool recorded there. A detached session leaves no such record, so the successor is not told it exists unless the brief or the next step says so.

## The handoff file format

**Status: the block form below is QUEUED, not built** (R20 in
`fleet-git-worktree-working-model.md`; the document's `status: built`
frontmatter covers the rest of the system, not this). Today the writer
collapses every whitespace run in the next step to a single space, and the
supervisor parses one `key: value` line at a time with no block parser — so a
multi-line next step reaches the successor as a dense chain. This section
specifies what both ends will do, because a reader-only change cannot restore
line breaks a writer has already destroyed.

The handoff file is a short list of `key: value` lines, written whole — the
writer renders it to a `.partial` file and renames, so no reader ever sees it
half-written. The supervisor reads those lines into fields and the first
occurrence of a key wins.

### The shape

The `next-step` field does not change. It stays the collapsed single line it is
today, and every reader — including a supervisor that predates this format —
keeps reading it exactly as it does now. When the agent's next step spans
several lines, the writer adds a second field carrying the text verbatim, and
writes it LAST:

    written-at: 2026-08-19T17:04:11Z
    next-step: FIRST ACTION: run the suite. THEN: fix only the locale case.
    restart-counter: 7
    written-in: /Users/el/agents/git-infra
    next-step-verbatim: <<END-OF-NEXT-STEP
    FIRST ACTION: run the suite and read the three failures.
    THEN: fix only the locale case; leave the other two for the
    design walk on docs/issues/45-remote-named-agent-launch-and-reattach.md@3406ac3.
    END-OF-NEXT-STEP

The opening marker is `<<END-OF-NEXT-STEP`, on the `next-step-verbatim:` line.
The terminator is `END-OF-NEXT-STEP` alone, with no `<<`, on a line by itself.
The lines between them are the value.

**The terminator is matched as an exact line**, on both ends: no leading or
trailing whitespace is tolerated, and the writer refuses on the same exact
comparison the reader ends a block on. This is what makes an indented
lookalike — a terminator inside a fenced code block, say — ordinary content
rather than a truncation: the writer writes it and the reader keeps it, and
the two ends cannot disagree about where a block ends. The cost is that a
hand-written terminator carrying trailing whitespace does not terminate; that
lands in the unterminated case below, which falls back to the collapsed line
and says so, rather than silently dropping content.

Writing the block last, after every computed field, is what makes it safe: a
content line that happens to look like `key: value` cannot shadow a real field,
because the real fields precede it and the first occurrence of a key wins.

### Rules the two ends must both honour

- **The writer adds `next-step-verbatim` only when the text contains a line
  break**, and always writes `next-step` as it does today. A single-line next
  step produces a file byte-identical to today's.
- **Content between the markers is verbatim** — no indentation added or
  stripped, no whitespace collapsed, and no trailing whitespace removed from
  the last line. A trailing double space is a markdown hard break, so the
  reader must hand the block over exactly as parsed; emptiness may be tested
  on a stripped copy, but the value passed on is never the stripped one. The one exception, stated so it cannot be
  read two ways: blank lines that fall between the first and last non-blank
  lines are preserved; blank lines before the first and after the last are not
  written at all.
- **The empty-next-step refusal is applied to the collapsed `next-step` value**,
  before any block is considered. A next step that is only whitespace is
  therefore refused, rather than written as an empty block.
- **The writer refuses** a next step containing a line equal to the terminator,
  naming the offending line. The same discipline as its refusal of an empty next
  step: a writer that cannot represent what it was given says so, rather than
  writing a file that reads back as something else.
- **The reader prefers `next-step-verbatim` when it is present and terminated**,
  and uses `next-step` otherwise. An unterminated block is a damaged handoff:
  the reader falls back to `next-step` — which is always present and correct —
  and says in the ignition prompt that the verbatim block was unterminated, so
  the successor knows it received the collapsed form.
- **Only `next-step-verbatim` takes the block form.** A `<<` in any other value,
  `next-step` included, is ordinary text.

### Compatibility, in both directions

The direction that matters is a new writer's file reaching an old reader, not
the reverse. Supervisors are long-running per-agent processes, so one started
before an upgrade will read files written after it.

- **Old supervisor, new file:** it reads `next-step` exactly as it does today,
  and ignores `next-step-verbatim` as an unknown key. The block's content lines
  can only add junk fields that nothing reads, since the real fields precede
  them. The successor gets today's behavior — a collapsed instruction — which is
  a degradation, not a failure.
- **New supervisor, old file:** no `next-step-verbatim` is present, so it uses
  `next-step`. Nothing needs migrating.
- **A hand-written file** with neither field well-formed is unchanged in
  treatment: `next-step` is whatever its line says.

This is why the marker does not go on the `next-step:` line. Putting it there
would make an old supervisor boot its successor with the marker string as its
entire instruction — silently, which is the failure this whole change exists to
remove.

### Relationship to the whitespace collapse

The writer's whitespace collapse is one of the mechanisms recorded in the
2026-08-06 writer ruling under Rulings below. It exists because a multi-line
value would otherwise be truncated at its first line by the reader. It keeps
that job here and is not weakened: `next-step` is still collapsed, which is
exactly what makes it safe for every reader. What changes is that the collapsed
line is no longer the only copy — the verbatim text travels beside it.

### The spawned-subagent roster — BUILT 2026-08-23

Unlike the block form above, this field is built and in use. A retiring
session records every subagent it spawned as one numbered field each:

    spawned-subagent-1: a309071aa3681d280 "Fix ignored-path write blind spot" spawned at 2026-08-23T19:55:24Z, last event completed at 2026-08-23T20:52:59Z
    spawned-subagent-2: abb92c2626197a6f5 "Fix output-path directory traceback" spawned at 2026-08-23T20:12:30Z, last event completed at 2026-08-23T20:47:50Z

Both lines are real output, derived from session `40a16b9c` of 2026-08-23.
Every one of that session's nine subagents completed, so no line of it shows
`spawned` as a last event; a subagent whose notification never arrives is
exercised by the test fixture instead, which is constructed for exactly the
cases the record does not happen to contain.

One field per subagent, numbered from 1 in spawn order, carrying the agent
id, the task description, the spawn time and the last event recorded for that
subagent. Numbered rather than repeated, because the reader takes the first
occurrence of a key and a repeated `spawned-subagent:` would lose every
subagent but the first. Written with the computed fields, before any verbatim
block. A session that spawned nothing writes no field at all, so its handoff
is byte-identical to what it would have been.

Compatibility runs the same way as the block form's. A reader that predates
the field sees unknown keys and ignores them; a reader that has the field
meets a handoff without it, derives an empty roster, and says nothing about
subagents. Nothing migrates.

**`last event` is stated, never interpreted.** It is whatever the transcript
last recorded — `spawned`, `resumed`, `completed`, `killed` — and the ignition
prompt tells the successor plainly that `completed` means the subagent
stopped, not that its work is finished. Deciding which entries still own work
is the successor's judgement, and the writer does not pretend to compute it.

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
- **Record the subagents, do not wait for them (user-ruled 2026-08-23).** Subagents die with the session that spawned them, and that stays the policy: killing and restarting them is cheaper than draining them before a recycle. What was missing is that nothing told the successor they had existed. On 2026-08-23 the merge-lane seat commissioned a subagent that built pull request #150. Read off session `40a16b9c` rather than remembered: it was spawned at 21:20:43Z and **completed at 21:31:18Z**, then sat idle and resumable; #150 opened at 21:32:07Z and drew review findings; the session was killed at 22:08:12Z. So the subagent did not die mid-task — it died stopped, still the owner of unfinished work on #150, which is the harder case and the one a liveness check would have missed. Its work survived — worktree and branch on disk at exactly the reviewed head — but its ownership did not: nothing computed by the handoff said #150 had a fixer. The successor found the orphan only because the retiring agent happened to write a sentence of prose about it — accurately, as it turns out: *"#150 — a fixer this seat commissioned; resume it by name from the transcript, or re-commission."* It re-commissioned, spawning a fresh fixer at 22:25:28Z. Prose is the faculty least to be relied on at recycle time, and it is what this field replaces. Hence the roster field above, and a supervisor that names it in the ignition prompt. Two shapes the field deliberately does NOT take, each of which loses the case it exists for: a roster of *running* subagents (the #150 fixer had stopped and was sitting idle, still owning the fix), and liveness inferred from unmatched tool_use/tool_result pairs (see the harness facts below — the spawn's result arrives at spawn time, so every spawn is a matched pair whatever becomes of the subagent).
- **A recycle waits for the session's running subagents, up to a ceiling (user-ruled 2026-08-27).** Bought by a loss: a builder subagent dispatched at 20:38 on 2026-08-27 died at 20:43 when the hook fired at 50%. The threshold hook now defers while any Agent-tool subagent is in flight and writes no fired marker, so every turn boundary re-decides — and since a completion notification is itself a turn, the boundary after the last subagent finishes is the one that fires. `--ceiling-used-percentage` (default 65) bounds the wait. This is the single exception to the 2026-08-23 record-not-wait ruling; what a recycle kills, and what a brief owes a job that outlives one step, is the section above.
- **No scheduled canary re-runs (user-ruled 2026-08-12).** Task pre-seed rides undocumented harness state, and the user does not care about the risk of a Claude Code upgrade breaking it. Detection is the successor's ignition count-check (trial-proven to fire unprompted) with the queues as backstop; the `--canary` cases in the supervisor suite are the diagnosis when it fires.

## Verified facts (2026-07-21 – 2026-08-23, Claude Code v2.1.220, and v2.1.238 for the 2026-08-23 rows)

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
| A subagent spawn writes a transcript record whose `toolUseResult` carries `status: async_launched` with an `agentId`, the task `description` and the commissioning prompt — and that result arrives at SPAWN time, so a matched tool_use/tool_result pair says nothing about whether the subagent is still running | 2026-08-23 transcripts |
| A subagent's completion arrives later and separately, as a `<task-notification>` record carrying a `<status>` and ONE OR MORE `<task-id>` elements — several ids under one status is how the harness reports agents from a previous session with no completion record, so a reader that takes only the first id leaves the rest holding a stale event; one notification reaches the transcript ONE TO THREE times, never four, in one of four combinations of queue enqueue, delivered user turn, attachment copy and queue remove | three session transcripts, 2026-08-21 to 2026-08-24, grouped on identical notification body; per-combination counts in `task_notification_text`. Multi-id specimen: session `3f4965a7`, 2026-08-21T19:31:05Z, naming two subagents that session spawned under `<status>stopped</status>`; five multi-id bodies across `~/.claude/projects` |
| The enqueue-only combination — a notification nothing ever delivered — occurs in every session measured, and all ten specimens carry `killed` at the session's death: eight background tasks, two subagents. A subagent whose COMPLETION was enqueued and never delivered has no specimen in the three, so the derivation reads every combination to make undelivered notifications visible at all, not on the strength of that variant having been seen | same three transcripts, re-measured 2026-08-28 |
| Background monitors notify through that same channel but launch differently: a monitor's `toolUseResult` carries `taskId`/`persistent` and never an `agentId`, which is how the two are told apart — not by the shape of their ids | session `40a16b9c` of 2026-08-23: 9 subagents, 8 monitors. Eight by two independent countings (`Monitor` tool-use blocks; results carrying `persistent: true`). Counting `taskId`-without-`agentId` gives 15, because backgrounded `Bash` tasks carry a `taskId` too |

## The live recycle trial — PASSED 2026-08-06

Four generations of a headless essay-writing agent; three auto-triggered recycles with no human input; every pass criterion met (full account in the snapshotted pre-gut text). What it proved that no unit test could: exit-as-handoff is the headless norm and the supervisor reads it correctly; the clean-stop branch works; a raised threshold mid-run does not disturb the cycle; and a successor challenges inconsistent state unprompted — the behavior the ignition count-check exists to produce, and now the declared detection for pre-seed breakage.

## Known holes

- Pre-seed rides undocumented harness state; detection is the ignition count-check, the queues are the backstop, the `--canary` cases are the diagnosis (accepted risk, user-ruled 2026-08-12).
- Very-long-session material can predate the word-floor window and every durable store; bounded by commit-as-you-go and the full-JSONL pointer in every extract. A live thread longer than the floor hands over a partial thread, bounded by the header's left-behind count.
- A supervisor is a per-agent process; if it dies, nothing watches until the next threshold crossing, when the hook-fired skill run starts an adopting supervisor (self-healing since 2026-08-12; `handoff-supervisor.py --check --agent <name>` reports liveness on demand).

## Open question — attached to the seat move

**Where the successor's output goes in an interactive pane.** A self-started supervisor is detached, its output going to `<agent>-supervisor.log`, so the successor it launches inherits that rather than the terminal the person is watching — correct headless, wrong for a console pane. Recommendation: panes run their supervisor directly (the supervisor as parent), leaving adoption as the bootstrap and recovery path. Settle before the seat move.
