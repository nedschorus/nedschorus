# Step-2 CLAUDE.md inputs — the consolidated list

Issue: [nedschorus#43](https://github.com/nedschorus/nedschorus/issues/43)

**Consumer:** founding plan step 2 ("Revise CLAUDE.md for them" — [nedschorus-founding-plan.md](../cross-project/nedschorus-founding-plan.md) § The steps). Until this file, the inputs list lived scattered across the new-vp handoff chain and machine-local session transcripts; no committed consolidation existed.

Inputs are numbered in accumulation order — the order the handoff chain recorded them. Verbatim quotes were re-verified against their sources on 2026-08-06 before this file was written.

## The seven inputs

**1. The absolutes warning** (boss-drafted 2026-08-06, superseding the 2026-07-28 shorthand).
Instruction text, boss verbatim: "Using absolute imperatives like 'always' or 'never' can backfire in unforeseen conditions."
Superseded at the step-2 admission (boss-reworded 2026-08-06): "Absolute imperatives like 'always' or 'never' can backfire in unforeseen conditions. Use them cautiously." — the admitted floor wording.
Why this form (boss-ruled 2026-08-06): the earlier shorthand — "absolutes are deadly to agents", applied as a no-bare-always/never rule with a rulings-and-mechanisms exemption — was itself an absolute ban and talked around the instruction. Agents already read imperatives literally and near-unconditionally, so no ban is needed; a plain warning aimed at the writer carries the point, and with no ban the exemption clause has nothing to exempt from.
Provenance: original directive in session 3b576242 (machine-local transcript), committed echo in the legacy worktree at `tasks/sessions/new-vp-walk-ledger-standing-items-2026-07-27.md` (item 3); instruction text drafted by the boss in session 9a618380.
*processed 2026-08-06 → revised: boss redrafted the instruction; this entry carries the ruled text.*

**2. The naming discipline** (boss-ruled 2026-08-06, superseding the one-line rider on [nedschorus#29](https://github.com/nedschorus/nedschorus/issues/29)).
Instruction text, boss-ruled verbatim: "When creating or inventing names, for directories, file names, globals, functions, etc., use explicit, clear and precise multi-part names. Check newly invented names with glob (for path names) or grep (for names in files). If these checks return collisions or ambiguity, choose a more explicit name, with 3 or 4 parts, not 1 or 2. If the thing you are naming already has a name in the project, use the existing name instead of inventing a new one."
What the ruled text adds over the #29 rider ("grep broadly BEFORE inventing a name; on collision or ambiguity choose a more explicit name"): the named surfaces, the tool per surface (glob for paths, grep for in-file names), the quantified escalation (3 or 4 parts, not 1 or 2), and the reuse rule split out with its own verb — match on the job, never on the token alone: a token match (same name, different job) escalates to a more explicit name; a job match (thing already named) reuses the existing name.
Provenance: #29 rider line (verified 2026-08-06); instruction text drafted and ruled in session 9a618380.
*processed 2026-08-06 → revised: boss-ruled instruction text; this entry carries the ruled text.*

**3. Trigger-first delivery, method only** ([nedschorus#30](https://github.com/nedschorus/nedschorus/issues/30)).
What stays always-loaded versus what becomes triggered injection is a step-2 design question. The 348-line legacy enforcement scan was STRUCK by boss ruling 2026-07-27 — its per-row verdicts judge nedlern's content under nedlern's enforcement and do not port. What may port is the METHOD: classify every instruction line against actual enforcement to find what must stay always-loaded — re-derive against NC content, never port verdicts. When step 2 runs, pull the scan from nedlern main at `docs/working/trigger-first-instruction-delivery-scan-first-pass.md` and apply the method to NC's own content.
Provenance: #30 body (verified 2026-08-06).
*processed 2026-08-06 → accepted as recorded (method input; yields step-2 procedure, no instruction text).*

**4. The CLAUDE.md question consumes #29 items 1–2** ([nedschorus#29](https://github.com/nedschorus/nedschorus/issues/29) § Relations: "The step-2 CLAUDE.md rewrite consumes items 1–2 and the naming line").
Item 1 verbatim: "Instruction-compression experiments: try smaller CLAUDE.md, AGENTS.md, and wiki files while measuring whether FRESH-AGENT BEHAVIOR loses essential rules. Fewer words alone is not success — behavior is the measure."
Item 2 verbatim: "The companion method: scrub instruction files deliberately rather than repeatedly squeezing them — repeated compression passes drop qualifiers and scope conditions invisibly (the legacy over-claiming clause in wiki-page-standards.md documents the mechanism: the unqualified sentence is shorter and reads cleaner, so qualifiers go first)."
Provenance: #29 body (verified 2026-08-06).
*processed 2026-08-06 → accepted as recorded (method input; yields step-2 procedure — behavioral acceptance test + single deliberate scrub — no instruction text).*

**5. The quality-over-resources ruling** (boss verbatim, 2026-07-30, received in new-vp session b6241858).
"our goal is not to minimize cpu cycles, storage, memory or tokens. Our goal is to design, write and maintain good code, that is easy to maintain, and not too slow, fat or token heavy."
(The as-received keystrokes had "easy to main" and a doubled space; the form above is the handoff-cleaned version the chain has carried.)
Provenance: session b6241858 (machine-local transcript, timestamp 2026-07-30T00:51:38Z).
Disposition (boss-ruled 2026-08-06): REJECTED as a candidate CLAUDE.md line, on two tests recorded for step 2's line-by-line admission: (1) not actionable at a decision point — it states a goal, and its nearest actionable form ("don't sacrifice clarity to save tokens; optimize only what measures too slow or too fat") is judgment guidance training already covers; (2) suspected collision with the runtimes' own system prompts, which push token economy — precedence between instruction files and system prompts is unprobed ([nedschorus#29](https://github.com/nedschorus/nedschorus/issues/29) item 3), and a true line that silently loses a precedence fight is worse than absent because the author believes it is in force. The ruling itself stays recorded here as the project's priority decision (applied once already: the legacy toolchain plan's "evidence value first, cost as a bound" framing). Nothing instruction-shaped goes to the floor from it unless a concrete decision point demands a line, and any such line first clears the #29 item-3 precedence probe.
*processed 2026-08-06 → rejected as instruction text; retained as the recorded priority ruling.*

**6. The floor-definitions duty** (boss-ruled 2026-08-04 at the d-review findings walk, session 4cf7d488).
CLAUDE.md defines once the shared project concepts every atomic skill assumes — "the boss" first among them. Skills stay atomic and reference other MD files by explicit path, never by assumed knowledge.
Provenance: session 4cf7d488; recorded as the sixth input in the outstanding-items walk ledger.

**7. The skills-are-instructions-only duty** (boss-ruled 2026-08-05 at the md-review self-review walk, session 4cf7d488, both faces).
POSITIVE: a skill answers three questions, worded as simply and plainly as reasonable — when to use it, what to do, how to do it.
NEGATIVE: it contains clear instructions, never information whose point in the file is unclear (the governing test). Common failing cases: statistics, measured anecdotes, incident specimens, out-of-context examples. If removing such content leaves a rule unclear, the rule itself is rewritten to carry the clarity; justifying data lives in the records stores and git history, never in skill text.
Step-2 relevance: CLAUDE.md is the floor that holds this duty for every skill, and the duty's writing standard applies to CLAUDE.md's own text.
Provenance: session 4cf7d488; recorded as the seventh input in the outstanding-items walk ledger; also carried in that session's handoff.

## Adjacent committed material step 2 consumes (already homed — listed so step 2 does not rediscover it)

- **The settled CLAUDE.md lines** ([nedschorus-founding-plan.md](../cross-project/nedschorus-founding-plan.md) § Standing decisions): the handoff pickup line; the transcript-archive pointer; commit-as-you-go with session id in every commit message; the zero-context-reader writing rule for durable artifacts; the check-in timing rule ([nedschorus#25](https://github.com/nedschorus/nedschorus/issues/25)). These are settled content, not queued inputs.
- **The seed draft** ([seed-claude-md-draft.md](../cross-project/seed-claude-md-draft.md)): pre-calibration input to step 2, not the base (founding plan doc table). Step 2's own method line: per sentence — training covers it → cut; training silent → state plainly; training conflicts → NOT/DO override. No rationale, no history, present-tense truth. Line-by-line boss admission.
