<!-- provenance: runtime=claude model=claude-fable-5 effort=xhigh attack=cut doc=fast-handoff isolation=instruction-pinned document set -->

The full document set is read. Here is the cut report.

---

# Cut report — `reviewed-fast-handoff-design.md` (fast-handoff design, pre-gut snapshot)

Findings ordered deepest first. Every candidate below survived my own attempt to defend the design as it stands; the candidates that did not survive are named in the leanness certification.

## Finding 1 — Two data paths both described as *the* auto-trigger; one should not exist

**WHAT** — Cut one of the two context-usage sources feeding the threshold hook. The document describes both the statusline relay (`handoff-statusline-context-relay.py` + side file) and a transcript-tail read as the mechanism, and never states a relationship between them. My recommendation: cut the relay and keep the transcript read.

**WHY** — The "Auto-trigger" section says the trigger value arrives via the relay: "The statusline script receives `.context_window.remaining_percentage` on stdin at every refresh; one added line writes it to a side file. The Stop hook reads that file." But the section directly above it, "Auto-trigger — read cost," says the hook reads the transcript: "The transcript is read only by the Stop hook, once per turn boundary, and only from the end — the newest assistant record is all that matters, so the hook reads a 256KB tail." The only thing the newest assistant record offers a threshold hook is `message.usage`, and the verified-facts table confirms that is its purpose: "context used is therefore computable from the transcript alone, in any session." These are two complete answers to the same question — how does the hook learn context usage — presented as one mechanism. This is the document's own named failure pattern: per the walk record, "The procedure clause had gone stale twice in one day … which is what a second copy of a procedure does."

The evidence for which path is live is decisive: the trial ran headless, and the verified-facts table states in bold that "A headless (`claude -p`) session NEVER runs the status line, so the relay file is never written and a statusline-only auto-trigger cannot fire there." Yet "three auto-triggered recycles happened with no human input" at thresholds of 5.5% and 8%. The path that passed the live trial — the system's only end-to-end validation — is the transcript path. The relay path has never been validated by the trial and serves only sessions the transcript path also serves, at a measured cost of 0.3ms. The relay's phrase "statusline-only auto-trigger" concedes the redundancy: the design already knows a non-statusline path exists.

**LOST** — Real, and it must be said honestly: `remaining_percentage` is harness-authoritative, while the transcript computation requires the per-model window table ("Context windows: Fable 5, Opus 5, Sonnet 5, and the Opus 4.x line are 1M; Haiku 4.5 is 200K") — a table that must be updated when models change, which is a recurring maintenance step (the operator-cost interlock cuts against my recommendation here, partially). Mitigations: `message.model` is in every record, so an unknown model can fail loud rather than silently miscompute, and the threshold is coarse ("config, ~50% used"), so precision differences between "prompt size / window" and the harness's own percentage do not matter. Priority 1 pays: one mechanism that works in every session type, no statusline modification, no side file, no side-file staleness.

**CONSEQUENCES** — If the relay is cut: the "Auto-trigger" section's first two sentences become false; the build-table row "Auto-trigger | BUILT — `scripts/handoff-statusline-context-relay.py` + `scripts/handoff-context-threshold-hook.py`, 14-case suite" names a script that no longer exists; verified-facts rows "Statusline stdin carries `.context_window.remaining_percentage`; Stop-hook stdin does not" and the headless-statusline row lose their consumers. If triage instead cuts the transcript path: the entire "Auto-trigger — read cost" section dies, headless auto-trigger dies with it, the trial's auto-trigger results become non-reproducible by the shipped system, and two verified-facts rows (transcript computability, window sizes) lose their consumers. Either way, the surviving section must state it is the only path. No ruled/RULED marker attaches to either path in my document set.

## Finding 2 — The threshold hook's stay-silent-when-unwatched guard guards nothing, and blocks the fix

**WHAT** — Cut the threshold hook's supervisor-liveness suppression: "the threshold hook stays silent when nothing is watching, so it cannot ask for a handoff nobody will act on." The hook should fire on threshold regardless of supervisor state.

**WHY** — Self-registration made this guard's failure condition unreachable. The document states: "A supervisor watches exactly one agent, and **the agent starts it** when its handoff script finds none watching (user-asked 2026-08-06)," and the skill confirms the fired path handles the unwatched case itself: the writer "reports whether a supervisor is watching," and step 3 covers "When it found a supervisor watching, **or started one**." So "a handoff nobody will act on" can no longer result from firing — firing leads to the writer starting a supervisor and the recycle proceeding. The guard now produces the worst outcome in exactly the case it handles: a session that crosses threshold while unwatched is silently never recycled and runs to context death — the precise failure this whole system exists to prevent — when firing would have self-registered a supervisor. And in the one residual branch where starting genuinely fails, suppression changes nothing downstream: the skill's could-not-start branch already says "do not stop: keep working, and tell the user," which is strictly better than silence because the user learns the seat is unwatched. This is a guard whose failure condition cannot occur and whose firing-anyway cost is one skill run (the tests pin "threshold crossing fires the skill exactly once," so there is no nag).

**Collision flag**: the liveness mechanism itself — the `last_poll_at` heartbeat and `--check` — is marked "(user-asked 2026-08-06)". I am not proposing to touch it; its first consumer (the skill checking before it stops working, "so a dead supervisor yields a plain report to the user rather than a session hung forever waiting to be killed") is real and stays. The cut is only the hook-side consumer. Whether the hook-side behavior was itself part of that user-asked ruling is not visible in my document set — triage should check before accepting.

**LOST** — In an environment where a supervisor truly cannot start, the agent performs one write-and-report cycle it would otherwise have skipped. Nothing else. Priority 1 pays twice: the unwatched-at-threshold session now recycles instead of dying, and the hook decouples entirely from supervisor state (one fewer cross-component read).

**CONSEQUENCES** — In the last known-holes bullet, "Both consumers use it" becomes "the skill checks before it stops working" alone; the clause "the threshold hook stays silent when nothing is watching, so it cannot ask for a handoff nobody will act on" is deleted. The trigger test ("threshold crossing fires the skill exactly once") is unaffected.

## Finding 3 — The `dont-restart` gate: cut the whole mechanism

**WHAT** — Delete the optional `dont-restart:` field, the supervisor's `restart? y/n` branch, the no-terminal closure that patches it, and the skill sentence "Add `--dont-restart` only when the user asked to be consulted before a relaunch."

**WHY** — Three arguments, each from the document's own text.

*It cannot deliver its promise on the normal path.* The field's purpose is consultation: "the supervisor prompts `restart? y/n` instead of auto-relaunching." But the self-started supervisor — the path self-registration makes normal — is detached: "A supervisor the agent starts is detached, with its output going to `<agent>-supervisor.log`." A detached supervisor has no terminal, and the closed hole says what happens then: "the supervisor takes the non-relaunch branch rather than calling `input()`." So the user who asked to be consulted is not consulted; the seat silently dies. A mechanism that fails its stated purpose on the primary path reopens the Delete question, and searching the documents for dependents finds only its own supporting machinery: the fields bullet, the y/n branch in components item 4, the test line "`dont-restart` y/n paths," the EOFError hole closure, and the skill sentence. Nothing else depends on it.

*Its two imaginable uses are already served by simpler existing things (the replacement test).* For "stop this seat": the clean-stop branch, trial-proven — "the final session exited without writing a handoff and the supervisor printed 'session ended without a handoff; supervisor stopping' and exited 0." For "stop with the dialog preserved for later": the extractor's "line-count mode (dead-session recovery)" recovers dialog from any dead session after the fact. And the deferred-relaunch reading does not work at all: the EOFError closure implies the non-relaunch branch records the consumed counter ("would raise EOFError *before the consumed counter was recorded* and leave the next supervisor re-firing"), so a `dont-restart` handoff is consumed, and no future supervisor will ever boot a successor from it — the "saved" handoff is dead on arrival.

*The failure it prevents is contained, by the document's own principles.* An unwanted relaunch is a successor sitting in an interactive pane in front of the very user who asked to be consulted; one typed line stops it, and "git is the long-term record and the restore-after-problem source (boss-ruled 2026-08-02)" bounds anything it does first. This is a glitch cheap to remedy, not a disaster to prevent with a field, a branch, a patched hole, and test paths. I found no ruled/RULED marker on `dont-restart` itself anywhere in my document set; the skill walk's own standard was "speculative rules are not added."

**LOST** — The interactive-pane consult-before-relaunch convenience, in the future state where panes run their supervisor as parent (terminal present). A user who wanted no successor instead gets one that starts on next-step until told to stand by — a few reversible turns of work. Priorities 1 and 2 pay: fewer states, no y/n branch, no terminal-presence conditional, and the EOFError class of holes cannot recur.

**CONSEQUENCES** — The fields bullet "optional `dont-restart:` …" is deleted; components item 4 loses "the `dont-restart` y/n gate"; the supervisor test line "`dont-restart` y/n paths" is deleted; the entire known-holes bullet "A `dont-restart` handoff reaching a supervisor with no terminal cannot be answered. Closed 2026-08-06 …" is deleted; SKILL.md step 2 loses its last sentence.

## Finding 4 — The per-upgrade canary re-run duty: cut the standing human step, keep the canaries as diagnostics

**WHAT** — Delete the duty "**re-run both canaries after every Claude Code upgrade**" (and its echoes in Tests and Known holes). The canary scripts stay, as on-demand diagnostics for when the automatic tripwire trips.

**WHY** — The design already carries two automatic layers protecting the same thing. First, the ignition prompt's count-check — "confirm N tasks visible (the pre-seed drift tripwire)" — which the trial proved works, and works even against half-successful failure: "A successor challenges inconsistent state rather than proceeding … The generation-3 agent reported the discrepancy unprompted." The known integer-id failure mode ("dropped by TaskList while still counting toward the next allocated id — so a schema-wrong pre-seed looks half-successful") lowers the visible count, which is exactly what the count-check catches. Second, the damage is bounded by design: "the backstop if an upgrade breaks it is the queues (task-shaped work belongs in GHIs by the artifact rules)" — the task store is the disposable tier by the project's own artifact rules, and pre-seed *copies* ("copies `~/.claude/tasks/<old-uuid>/*.json`"), so the predecessor's task directory survives intact as the restore source. This is containment: the failure the canaries pre-empt is cheap to remedy after the tripwire fires. A standing remembered step — "after every Claude Code upgrade," when upgrades can arrive by auto-update with nobody watching — is the operator-cost interlock's exact target, and a duty that silently goes unperformed provides imagined protection, which is worse than relying on the tripwire that actually fires.

**LOST** — Pre-emptive detection timing: with the duty cut, breakage is discovered at the first post-upgrade recycle rather than before it. Concretely, the no-clobber failure mode (canary 2's subject) could preserve the count while a successor's new task overwrites a seeded one — the count-check might miss that — but the predecessor's directory still holds the originals, and anything that mattered was in a GHI. Priority 1 pays: zero remembered human steps.

**CONSEQUENCES** — Step 4's bold sentence is deleted; the supervisor test line "task pre-seed as executable canaries (re-run per upgrade)" loses its parenthetical; known-holes bullet 1 becomes "bounded by the ignition count-check; the queues are the backstop." The "artifact rules" this finding leans on live in a document outside my set — I am taking the design's quotation of them at face value.

## Finding 5 — The queue-status line prints where nobody looks (flagged, not cut: a ruling I cannot read depends on it)

**WHAT** — Not a clean cut; a broken-mechanism finding for triage. Step 5's queue-status line either moves to where a reader exists or the duty it discharges is not being discharged.

**WHY** — Step 5: "Prints one automated queue-status line — each queue's depth and oldest item … the artifact-lifecycle rot-visibility duty riding every recycle at zero agent cost." Its only consumer is whoever watches the supervisor's console. But the open question says the self-started supervisor's "output going to `<agent>-supervisor.log`" — an unwatched log file. In that deployment this is a detector whose output no one reads: the rot-visibility duty is cited but not delivered. The mechanism names a dependent — "the #32 Q1 ruling" and "the artifact-lifecycle rot-visibility duty" — both recorded in documents outside my set, so by my own rules repair comes before deletion, and I flag rather than re-litigate: if the ruling requires rot-visibility *to a person*, the line must ride something a person sees (the pane case, or the ignition prompt so the successor sees and can escalate); if the duty can be discharged another way, the line is a cut candidate. Triage should read #32 before deciding.

**LOST** — If cut without a replacement: queue-rot visibility, a named duty. That is why this is a flag, not a cut.

**CONSEQUENCES** — If it moves into the ignition prompt, step 6, components item 5, the build-table ignition row, and the ignition test assertion all change. If cut, step 5 and its test implications go, and the #32 Q1 duty needs a new home.

## Finding 6 — The "Components (the build)" section is a duplicate inventory that has already drifted four ways

**WHAT** — Delete the "Components (the build)" section. The recycle-cycle narrative plus the build-status table already carry everything in it.

**WHY** — Two inventories that differ are cut evidence, and this one differs from the rest of the document in four places. (1) Item 1 names the extractor "`extract_convo.py`"; the build table names it "`scripts/handoff-extract-conversation.py`" — a dead name. (2) Item 1 calls it "boundary-quote mode (recycling)," but the fields section rules the opposite: "the boundary field all died with this ruling; `--boundary-quote` survives in the extractor as a manual override only," with recycling now on the "**2500-word floor**." (3) Item 5 and step 6 say the ignition prompt carries "the exact handoff path to read," while the build table's ignition row says "dialog path" — genuinely different files, and the skill's promise that the successor "will read the last few thousand words of this conversation" is only kept by the dialog path; I cannot verify which the code does, so triage must resolve the discrepancy as part of the cut. (4) Item 2 says the skill "waits for the supervisor," flatly omitting the could-not-start branch the skill's step 3 mandates ("do not stop: keep working"). The section's own numbering — 1, 2, 2a, 3, 4, 5, bolted to preserve the historical "five components" count the walk record mentions — shows it is being maintained by patching rather than as a source of truth. The project has already recorded what second copies do: "The procedure clause had gone stale twice in one day … which is what a second copy of a procedure does."

**LOST** — The parser-tolerance list in item 1 ("a partial last record is skipped, not fatal; a malformed line is skipped and counted …") is the one passage with no other home — it moves into the extractor row of the build table or the Tests section rather than dying. Otherwise nothing: the component-to-script index already exists in the build table.

**CONSEQUENCES** — The Tests section, a third inventory, needs one repair the cut exposes: it tests "boundary-quote start" but names no 2500-word-floor case, though the floor has been the live recycling mechanism since 2026-08-06 — the tests list is testing the manual override and not the mechanism. The "handoff path"/"dialog path" question must be settled in step 6's text when item 5 dies.

## Finding 7 — The design restates the skill's next-step rule while naming the skill as text of record — and the restatement has already drifted against a walked ruling

**WHAT** — In the `next-step:` fields bullet, cut the restated content rule; keep the pointer ("Text of record: `.claude/skills/handoff/SKILL.md`") and nothing that the skill already says.

**WHY** — The bullet declares the skill authoritative and then restates the rule anyway — a duplicated normative home. And it has already drifted in exactly the direction the walk rejected: the design says "**Every pointer carries a pin**" — a general rule — while the walk record rules "Pinning is now two observable cases — a file reference carries path and commit SHA, a GitHub issue reference carries repository and number," and the landed skill states only the two ifs. The design's copy resurrects the pre-walk general form of a rule the user deliberately narrowed to observable cases. This is not hypothetical drift; it is drift against a recorded ruling, which I flag rather than resolve — the resolution is the one the design itself declares: the skill is the text of record.

**LOST** — Nothing. A reader of the design follows the pointer, which the bullet already provides.

**CONSEQUENCES** — The bullet shrinks to the pointer plus any genuinely design-level rationale; components item 2's "writes `next-step` per the content rule" already points at the skill implicitly and is dying with Finding 6 regardless.

## Finding 8 — A stale status sentence contradicted by its own table two lines below

**WHAT** — Delete "Four of the five components are built, tested, and on main; the fifth is the skill text, which is instruction-class and lands after its walk."

**WHY** — The table under it lists six rows, all BUILT, including "`handoff` skill | BUILT — … walked and landed 2026-08-06," and the section closes "Every component is now built, tested, and walked." The sentence and the table cannot both be true; the sentence is the pre-walk state left standing. Status told differently in the same section is the internal-consistency case in its purest form.

**LOST** — Nothing.

**CONSEQUENCES** — None; the closing sentence and the header's "Only the Stop-hook wiring into NC's settings remains" already state the true status, consistently.

## Finding 9 — Smaller cuts

- **Half of "Known holes" is not holes.** Three of six bullets are marked "Closed 2026-08-06," and one says outright "so this hole no longer exists." A heading contradicted by its own body. The closure rationales (the EOFError analysis, the fresh-id-on-restart rule) are load-bearing design rationale worth keeping — but as design text where those mechanisms are specified, not as "known holes." The section should hold only the three open bounds.
- **One verified-fact row has no surviving consumer.** "A fresh subagent's context floor is CLAUDE.md + prompt" supported the drafting subagent, which the header lists among "the superseded machinery." Nothing surviving in the document consumes it — subagent exclusion rests on SubagentStop, not on context floors. Cut the row; it remains recoverable at the header's `git show e178e67` pointer like everything else that died.

---

## Leanness certification

I examined the following and certify them minimal, each against the replacement test:

- **The restart-counter + consumed-marker + max-derivation semaphore.** I attempted this cut (replace the counter with file-write events/mtime) and it failed: mtime breaks across restore-from-backup and same-value rewrites, the consumed-marker needs a durable comparable, and each of the counter's three patches answers an observed failure the document names (newline truncation, stale file, refire). The simplest existing thing that could deliver the same result does not exist.
- **The writer owning every machine-computable field** — user-ruled, and it deleted machinery (agent arithmetic, the boundary field, the silent truncation) rather than adding it.
- **The 2500-word floor with the nearest-user-prompt extension and the left-behind count** — a mechanism replacing judgment; the header count has a real consumer (the successor's informed choice to read further).
- **The extractor's parser tolerances** — all four name real failure modes and all four are tested; nothing simpler survives a torn write.
- **ID-keyed JSONL lookup with UUID fallback, latest-by-mtime rejected** — the rejection is itself a cut already made, with the race named.
- **Self-registration, `AdoptedSession`, and the lock file** — the lock answers a stated two-supervisor failure ("two would each kill the session and each launch a successor"); adoption closed an observed hole (the permanently unrecyclable founding boot). Two design questions dissolve rather than being answered, which is the leanest shape a design gets.
- **Two-generation local retention; the founding boot with "No standing committed-handoff machinery"; the boss-ruled `written-at`/elapsed-time line with its stated consumer** — each already minimal.

The document's superseded-machinery header shows this design has been cut hard once already. What this pass found is mostly the residue of that surgery — second homes that drifted, guards that outlived the mechanism that justified them, and one pair of parallel mechanisms never reconciled — rather than fresh over-building.
