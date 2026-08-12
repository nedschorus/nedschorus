<!-- provenance: runtime=claude model=claude-fable-5 cell=sanity-checker (settled prompt, post-calibration acceptance) run=second-document target=docs/cross-project/fast-handoff-design.md (live revision, snapshotted in this directory); context: .claude/skills/handoff/SKILL.md, docs/drafts/handoff-skill-draft.md -->

I have read all three documents in the set. Before the findings, the linked material I could not read (per the review request's instruction not to search for it): the superseded design at `git show e178e67:docs/cross-project/fast-handoff-design.md`; GitHub issues nedschorus#40, #27, and the "#32 Q1 ruling"; the trial dialogs `essayist-dialog-000N.md`; and all six scripts and their test suites (`handoff-write-and-check-supervisor.py`, `handoff-supervisor.py`, `handoff-extract-conversation.py`, `handoff-statusline-context-relay.py`, `handoff-context-threshold-hook.py`, and tests). Where a finding depends on what a script actually does, I say so.

---

# Sanity-check report: fast-handoff-design.md

## Findings (deepest rung first)

### Finding 1 — Delete the statusline relay; the design already contains two normative, mutually contradictory auto-trigger mechanisms, and its own verified facts say one suffices everywhere

**WHAT** — Collapse the auto-trigger to a single data source: the Stop hook computes context used from the transcript tail. Delete the statusline relay (`scripts/handoff-statusline-context-relay.py`), the side file, and the one-line statusline modification; merge the two "Auto-trigger" sections into one.

**WHY** — The document currently states two different mechanisms as the mechanism, and they disagree about what the Stop hook reads:

- "Auto-trigger — read cost": "The transcript is read only by the Stop hook, once per turn boundary, and only from the end — the newest assistant record is all that matters, so the hook reads a 256KB tail and doubles the window until it finds that record."
- "Auto-trigger": "The statusline script receives `.context_window.remaining_percentage` on stdin at every refresh; one added line writes it to a side file. The Stop hook reads that file."

These cannot both be the trigger's data source. The document's own verified facts resolve which one can actually cover the fleet: "A headless (`claude -p`) session NEVER runs the status line, so the relay file is never written and a statusline-only auto-trigger cannot fire there" — yet the live trial was headless (`claude -p`) and "three auto-triggered recycles happened with no human input," so the relay cannot be what fired. And: "Every assistant transcript record carries `message.usage` … context used is therefore computable from the transcript alone, in any session." One source works everywhere; the other works only in interactive panes. Two mechanisms where one suffices is a duplicated normative home in both the document and the running system, and the measured cost of the surviving path is already recorded as negligible ("Measured on a 5.8MB transcript: 0.3ms"). I could not read the hook script, so I cannot say whether the relay is already dead code or a live second path — either way the cut and the section merge stand; if it is dead code the cut is even cheaper.

**LOST** — The harness-authoritative `remaining_percentage`. Computing "context used" from `message.usage` requires knowing each model's window size — the document already carries that table ("Context windows: Fable 5, Opus 5, Sonnet 5, and the Opus 4.x line are 1M; Haiku 4.5 is 200K") — and that mapping must be maintained as models ship, with a defined loud behavior on an unknown model id. Paid for by priority 1 (one mechanism that fires in every session type, headless included) and priority 3 (one script, one suite, no side file).

**CONSEQUENCES** — The "Auto-trigger" section (relay description) is deleted or rewritten; the "Auto-trigger — read cost" section merges into it. Build-status row "Auto-trigger | BUILT — `scripts/handoff-statusline-context-relay.py` + `scripts/handoff-context-threshold-hook.py`, 14-case suite" loses its first script and part of its suite. Components item 3, "The statusline relay + Stop hook — the auto-trigger," loses the relay. Verified-fact rows "Statusline stdin carries…" and "A headless (`claude -p`) session NEVER runs the status line…" remain true but become historical rather than load-bearing; the context-window row becomes load-bearing and needs a maintenance note. The trigger test "threshold crossing fires the skill exactly once" survives unchanged.

### Finding 2 — Delete the threshold hook's supervisor-liveness gate; it now suppresses the self-healing path that self-registration created

**WHAT** — Remove the rule that "the threshold hook stays silent when nothing is watching." The hook fires at the threshold unconditionally; the skill and writer already handle the no-supervisor case.

**WHY** — The gate's stated purpose — "so it cannot ask for a handoff nobody will act on" — was true before self-registration and is false after it. The same document, same date, says: "the agent starts it when its handoff script finds none watching (user-asked 2026-08-06)," and the skill's step 3 (text of record) says: "When it found a supervisor watching, or started one, stop working and wait." So a hook-fired handoff with no supervisor watching IS acted on: the writer starts an adopting supervisor and the recycle proceeds. With the gate in place, the one failure the whole system exists to prevent becomes permanent: supervisor dies mid-session, hook goes silent, the session never recycles and context grows until a human notices — exactly the unattended-fleet failure. Even in the genuine could-not-start environment, an ungated firing produces the designed outcome, not waste: "keep working, and tell the user that the handoff is written but nothing is watching for it" — a written handoff plus an informed user, strictly better than silence. This is a guard whose remaining benefit is preventing a report the design elsewhere wants made.

**Ruling collision, flagged:** the liveness detection is recorded as "Detectable since 2026-08-06 (user-asked)," and the sentence naming the hook as a consumer sits inside that ruled passage. I read the ruling as asking for detectability of a dead supervisor; whether hook-silence was itself ruled or was an implementation choice riding the ruling is for triage — I flag it rather than assume.

**LOST** — In an environment where a supervisor genuinely cannot start, the agent spends one skill run per threshold crossing writing a handoff nobody consumes (bounded by the existing "fires the skill exactly once" behavior). Paid for by priority 1: a dead supervisor becomes a self-healed glitch instead of a silent permanent stall. Note the `--check` machinery itself keeps its other consumer ("the skill checks before it stops working") and is not touched.

**CONSEQUENCES** — In "Known holes," the sentence "the threshold hook stays silent when nothing is watching, so it cannot ask for a handoff nobody will act on" is deleted, and "Both consumers use it" becomes one consumer. Any case in the 14-case trigger suite asserting hook silence on dead supervisor (I could not read the suite) inverts.

### Finding 3 — The queue-status line has no named reader in the detached case: name its consumer, route it to one, or cut it

**WHAT** — Decide who reads "one automated queue-status line — each queue's depth and oldest item." Either route it where its reader demonstrably is (the ignition prompt, so the successor sees it; or a user-facing surface), or state the reader in the design, or cut the step.

**WHY** — The line is printed by the supervisor. But the same document says a self-started supervisor "is detached, with its output going to `<agent>-supervisor.log`, so the successor it launches inherits that rather than the terminal the person is watching." The ignition prompt's contents are enumerated — "the exact handoff path to read; the elapsed-time line…; confirm N tasks visible…; then take the next step" — and the queue-status line is not among them. So for headless agents and any adoption-launched successor, the "rot-visibility duty" is discharged into a log file with no stated reader: a detector whose output feeds no machinery. The forcing-function test finds no one forced to decide anything by its existence. Routing it into the ignition prompt would give it a consumer at the same zero agent cost; cutting it is also honest if panes-run-supervisors (the open question's recommendation) makes the human the reader in the only case that matters.

**Ruling collision, flagged:** the line discharges "the artifact-lifecycle rot-visibility duty" under "the #32 Q1 ruling," which I could not read ("memory maintenance is the boss's drain"). If the ruled reader is the boss at a console, the finding reduces to: the design should say so, and say what happens to visibility for headless agents. I flag; I do not re-litigate #32.

**LOST** — If cut: rot visibility riding recycles disappears — a named blind spot, and a ruled duty loses its rider, so cutting needs the #32 context. If routed to the ignition prompt: nothing is lost and the successor gains a fact it can act on or relay. Paid for by priority 1 either way (output that reaches an actor, or machinery removed).

**CONSEQUENCES** — Recycle-cycle step 5 and Components item 4 ("queue-status line") change; if routed, the ignition-prompt template (Components item 5, "path, elapsed-time line, task count, next step") and its test ("ignition prompt contains path + elapsed-time line + task count") gain a clause; the parenthetical citing #32 moves with the duty.

### Finding 4 — Encode the per-upgrade canary duty; "re-run both canaries after every Claude Code upgrade" is a remembered human step that the system could carry itself

**WHAT** — Replace the bolded remembered duty with mechanism: the supervisor records the Claude Code version against which the canaries last passed; on launch (or first recycle) under a different version, it re-runs the canaries automatically or refuses loudly with the instruction. Alternatively, delete the duty and let the existing containment carry it.

**WHY** — The design says: "**re-run both canaries after every Claude Code upgrade**" and lists in Tests "task pre-seed as executable canaries (re-run per upgrade)." That is a manual check that must be remembered forever — "Operator cost is not builder cost." The canaries are already executable, so the trigger is the only unmechanized part, and the trigger is a version comparison — pure code. Moreover the design has already built containment for exactly this failure: "bounded by the ignition count-check and the per-upgrade canaries; the queues are the backstop," and the trial proved the containment works unassisted: "A successor challenges inconsistent state rather than proceeding… reported the discrepancy unprompted." With detection-at-first-recycle and a backstop both in place, the remembered duty is a second check on a contained failure; mechanize it cheaply or drop it with eyes open.

**LOST** — If mechanized: a small new supervisor feature (version stamp + compare) — priority 1 pays, zero remembered human steps. If instead deleted: pre-upgrade assurance is given up; the first post-upgrade recycle becomes the detection event, bounded by the count-check and the queues — that blind interval is the declared loss.

**CONSEQUENCES** — The bolded sentence in recycle-cycle step 4; the Known-holes line "bounded by the ignition count-check and the per-upgrade canaries"; the Tests clause "(re-run per upgrade)". If mechanized, the supervisor's test list gains the version-mismatch case.

### Finding 5 — The Tests section and Components item 1 predate the 2026-08-06 boundary ruling: the live recycling boundary is untested-as-specified while the demoted override is listed first

**WHAT** — Update Components item 1 and the extractor's test list to match the ruled design: the word-floor tail is the recycling mode; `--boundary-quote` is a manual override; the test list should name the word-floor behavior. Add the two supervisor branches the trial proved critical to the supervisor's test list.

**WHY** — The ruling is quoted in the field list: "The extractor carries the tail of the conversation that clears a **2500-word floor** … extended back to the nearest user prompt … `--boundary-quote` survives in the extractor as a manual override only." But Components item 1 still says "boundary-quote mode (recycling) and line-count mode (dead-session recovery)" — naming the demoted override as the recycling mode and not mentioning the word floor at all. And the extractor test list — "boundary-quote start, line-count mode, cross-directory ID search, empty/unparseable refusal" — contains no word-floor case: the one boundary every real recycle now uses is the one absent from the listed suite, while the manual override keeps its test. Separately, the trial section records two branches as load-bearing — "Before the fix (`wait_for_handoff` returning None on exit before checking the file) the trial would have stopped at the first handoff" and "The clean-stop branch works" — yet the supervisor's test list ("semaphore init and consumed-marker…, `dont-restart` y/n paths, kill → extract → launch ordering…") names neither exit-as-handoff nor clean-stop. The suites may already cover these (23 and 24 cases; I could not read them); the Tests section is the document's normative statement of what must be tested, and it is stale either way.

**LOST** — Nothing; this is reconciling the document with its own rulings and trial evidence. Priority 2 pays (a reader stepping through the design meets one boundary story, not two), with a priority-1 edge if the word-floor case is genuinely untested.

**CONSEQUENCES** — Components item 1's mode list; the Tests section's extractor and supervisor lines. No other sentence depends on boundary-quote being the recycling mode.

### Finding 6 — One home per component: merge "Build status" and "Components (the build)", which currently disagree with each other and with the frontmatter

**WHAT** — Merge the two component inventories into one section — each component once, with its script name, state, and spec detail — and make the status story single-homed.

**WHY** — The same inventory lives twice and has already drifted. The build section opens "Four of the five components are built… the fifth is the skill text, which is instruction-class and lands after its walk," immediately above a table of six rows all BUILT and the closing "Every component is now built, tested, and walked" — the preamble is contradicted twice within its own section. The Components list names the extractor "`extract_convo.py`" while the table names it "`scripts/handoff-extract-conversation.py`" — a grep for either name finds half the document. The frontmatter still reads "status: specification" against the header's "**Implementation status:** BUILT, walked, and trial-passed." This is the duplicated-normative-home class applied to the document's own status: three tellings, each stale in a different way. The walk record's own lesson (item 8) names the mechanism: "which is what a second copy of a procedure does."

**LOST** — The current separation of "what it is" (Components) from "where it stands" (table) — recoverable as columns of one table. Priority 2 pays.

**CONSEQUENCES** — The "Build status (2026-08-06)" section and "Components (the build)" section merge; the sentences "Four of the five components are built…" and the duplicate name `extract_convo.py` disappear; the frontmatter status field changes; Finding 5's corrections land in the merged home.

### Finding 7 — "Known holes" holds three closed holes; move closed rulings to the sections that own the mechanisms

**WHAT** — Keep "Known holes" for holes. The three entries marked closed — the boundary-judgment hole ("closed 2026-08-06: the boundary is mechanical"), the terminal-less `dont-restart` hole ("Closed 2026-08-06: the supervisor takes the non-relaunch branch"), and the crash-restart hole ("Closed 2026-08-06: a fresh start always mints a new id") — move, with their ruled tags intact, into the sections describing the mechanisms they now simply are (extractor boundary, supervisor `dont-restart`, supervisor restart). The residual live risk in the first entry ("a session whose live thread runs longer than 2500 words hands over a partial thread") stays in Known holes, because that part is still a hole.

**WHY** — A reader auditing the design's known weaknesses must currently parse six entries to find that only three are weaknesses; the closed ones are design facts wearing a hole's heading. The project records rulings inline — this move preserves every ruling annotation verbatim; only the heading under which it sits changes. This is reorganization, not history-deletion: "git is the long-term record" holds the full narrative regardless.

**LOST** — The at-a-glance record of what used to be broken, in one place — recoverable from git and from the ruled tags at their new homes. Priority 2 pays.

**CONSEQUENCES** — The "Known holes" section shrinks to three entries (pre-seed fragility, very-long-session material, supervisor-death — the last also touched by Finding 2); the supervisor and extractor descriptions each gain a ruled sentence they currently lack.

---

## Hunt: prompts-to-code

Every place the design relies on an LLM following English instructions, and the disposition:

1. **Writing `next-step`** — genuinely interpretive; the design has already stripped it to the single piece only the model can supply ("The agent supplies only `next-step`; the writer fills every field a machine can compute"). Correctly delegated residue. No finding.
2. **The skill's step 3, "Do what it reports"** — model routed by script output, constrained to two branches (stop-and-wait / keep-working-and-tell-the-user). Already constrained. No finding.
3. **The ignition count-check ("confirm N tasks visible")** — a model performing verification, but legitimately: the failure it guards ("a record with an integer id is dropped by TaskList while still counting toward the next allocated id — so a schema-wrong pre-seed looks half-successful") is visible only from inside the session's task tools, not on disk. I considered a supervisor-side schema validation at copy time and refuted it: production records are harness-written and schema-correct by construction; the integer-id hazard arose in canary authoring. No finding.
4. **`--agent <your name>`** — the one remaining agent-typed fact. The walk record already flags it: "One input remains unscriptable until NC has an agent-naming convention." Respecting the roadmap: a question for the report, not a finding — when the naming convention lands, encode this argument too.
5. **The per-upgrade canary re-run** — a remembered human instruction where a version comparison is pure code: Finding 4.
6. **The threshold-hook message** — already reduced to the exact string "Run the handoff skill now" with an exact-match test. Lean.

## Hunt: a better way

Stepping back: the architecture — agent authors one interpretive line; scripts write, watch, kill, extract, seed, relaunch; git and the queues are the durable stores and the restore path — is the right shape, and it already embodies the containment move this review hunts for (a broken pre-seed is a challenged discrepancy plus a queue backstop, not a disaster; a lost session is a git-restorable glitch). The two places the design falls short of its own shape are Findings 1 and 2: it carries two trigger mechanisms where its own probes prove one covers every session type, and it gates the trigger on a liveness check that self-registration made self-healing to ignore. The candidate unknown-unknown I examined and dismissed: an interactive pane killed at threshold while the user is mid-exchange — the word-floor tail carries the exchange to the successor, "over-capture is nearly free" covers it, and consultation machinery for it would be complexity for a theoretical annoyance (`dont-restart` already exists for the consulted case).

## Leanness certification

I examined the following and certify them lean, each against the replacement test (the simplest existing thing that could deliver the same result):

- **The skill text** (`handoff-SKILL.md`): a description and three steps, one command, one interpretive input. Replacement test: the hook cannot invoke the writer directly because `next-step` needs the model — the skill is exactly the model-shaped remainder. The walk record shows two whole sections already deleted; nothing further to cut.
- **The writer's mechanisms**: file-not-argument ("a shell mangles backticks and quotes"), whitespace collapse (the silent newline truncation), counter derived from the max of file and consumed values (the stale-file refire), refuse-empty-next-step, and the single-command-with-liveness-report ruling ("an agent that runs only the first half of a two-step procedure would stop anyway"). Each mechanism maps to a named, observed failure. No cheaper substitute exists for any of them.
- **The extractor's parser tolerances**: partial tail, malformed-line skip-and-count, per-line size bound, ID-keyed lookup with UUID fallback and latest-by-mtime rejected ("a second session in the same worktree makes it a race"). Each guards a real hazard class of JSONL-in-motion; none is a check on another check.
- **Self-registration with the lock file**: the lock prevents a concrete double-kill/double-launch failure ("two would each kill the session and each launch a successor"); the two dissolved questions (which sessions, subagents) are dissolved structurally, not by added rules.
- **Retention (current + predecessor), the founding boot (one committed file, no standing machinery), and the `dont-restart` gate with its EOFError-safe branch**: each is already the minimal form; the boot's replacement test (reuse the recycle machinery for the first boot) fails because there is no predecessor session to extract from.
- **The consumed-marker counter protocol**: replacement test — bare mtime-watching cannot distinguish consumed from unconsumed across a supervisor restart; the counter pair is the minimal state that can. The parenthetical "(or file mtime)" in step 1 is implementation detail, not a second mechanism.

The rest of the document outside Findings 1–7 is already lean.
