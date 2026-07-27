---
processed: 2026-07-24
walk-item: outer item 11 (skill-creator review)
dispositions: [docs/wiki/queue/skill-authoring-checklist.md (distillation), founding-plan step-1 pointer, pointers on nedschorus#15-#23]
dropped-by: new-vp (archived 2026-07-27 by the queue audit; outputs verified before the move)
---

# Skill creation and improvement for NC — extraction proposal from the skill-creator read

Queued for the walk (slots into the outer backlog walk as its own item, after the nine candidate skills). Sources: the full read of Anthropic's `skill-creator` plugin (21 files, 5,464 lines, fetched 2026-07-22; local copies in the session scratchpad), pair #9's shortlist and principles, pair #10's candidate rules, and today's boss rulings (boss-facing vs agent-facing split; iterate-in-use for supervised behavior).

## 1. The decision frame

NC builds five founding skills at step 1 (d-review, walk-me-through, handoff, ghi-write, md-write) and will choose a boot subset of pair #9's nine candidates. The question this note answers: what does NC take from skill-creator — the only substantial official artifact about making skills — and in what form. The frame rules out wholesale adoption immediately: skill-creator is ~5,500 lines centered on a human-in-browser iteration loop (localhost review UIs, feedback.json round-trips, benchmark runs of 2 configurations x 3 runs per test case, a description optimizer that spawns ~300 headless `claude -p` runs per optimization). That is machinery the earned-complexity ladder has not admitted, and its trigger measurement is a command-file proxy, not real skill loading — its numbers are approximations, not truth.

## 2. Extract A — creation-time doctrine (the walkable core, ~150 lines of prose in the source)

Proposed disposition: these become the step-1 skill-build checklist, replacing the thinner "interface contract" extraction previously withdrawn during the walk.

- **The intent-capture interview, four questions asked before writing anything:** what should the skill enable; when should it trigger (what user phrases and contexts); what output format is expected; are test cases worth it — "skills with objectively verifiable outputs benefit from test cases; skills with subjective outputs often don't." That last question IS the boss's boss-facing/agent-facing split, discovered independently by Anthropic.
- **Description and trigger heuristics:** the description is the primary triggering mechanism; ALL when-to-use information goes in the description, not the body; imperative form ("Use this skill for...") over declarative; describe the user's intent, not the implementation; 100–200 words; and deliberately "pushy," because Claude currently undertriggers skills. Descriptions compete with every other skill for attention.
- **Structure — progressive disclosure, three levels:** metadata always in context (~100 words); body loads on invocation (keep under 500 lines; approaching the limit means add hierarchy, not compression); bundled references/scripts unlimited (large reference files get a table of contents).
- **Writing style:** explain why things matter instead of stacking MUSTs; all-caps ALWAYS/NEVER is a yellow flag — reframe with reasoning. NOTE, flagged for the boss: this conflicts with the old system's NOT/DO doctrine at exactly one point. NOT/DO earned its place for instructions that override a training default (measured drift without it); explain-why is better everywhere else. Proposed resolution: NC skills use explain-why as the default register and reserve NOT/DO for the training-override cases that doctrine was built for.

## 3. Extract B — test doctrine for agent-facing skills

Proposed disposition: the test-design rules below govern any NC skill (or skill half) whose failures are silent — per today's ruling, that is most of them; boss-supervised interaction halves iterate in live use instead.

- Assertions are objectively verifiable statements with descriptive names; subjective qualities are evaluated by a human, never forced into assertions.
- Burden of proof is on the expectation; no partial credit; evidence must show genuine task completion, not surface compliance.
- **The discriminating-assertion concept** — an assertion that passes for both a good and a bad output is worse than useless (false confidence); the grader's second job is critiquing the evals themselves.
- Negative trigger tests must be near-misses (share keywords with the skill but need something else); easy negatives prove nothing.
- Checkable assertions get checked by script, not eyeballed.
- Pair #9's principle-6 classes (false trigger, missing context, conflicting instructions, partial failure, letter-vs-intent) remain the scenario taxonomy; the rules above are how each scenario's pass/fail is judged. The handoff spec's T1–T10 already conform.

## 4. Extract C — two standalone utilities (defer)

`quick_validate.py` (102 lines, frontmatter validator) and `package_skill.py` (136 lines) are cleanly separable, but NC's frontmatter conventions differ (field-with-a-named-consumer, ruled 2026-07-22) and NC has no packaging need. Disposition: no import now; candidates through the entry checkpoint at first real need.

## 5. Skill-count mechanics (answers a standing boss question)

Confirmed from current docs: descriptions load at session start, bodies lazy-load on invocation; the combined description text is capped at 1,536 characters per skill; the listing budget scales at 1% of the context window, and on overflow Claude Code shortens descriptions starting with the least-used skills. Implication: NC can carry many skills cheaply, but the real constraint is description-budget discipline and trigger distinctiveness — every added skill dilutes every other skill's claim on attention. "A lot of skills" is fine; "a lot of vague skills" degrades routing.

## 6. The proposal in one paragraph

Skill-creator is read-for-ideas-only: no adoption, no dependency, no import of its loop. Its creation doctrine (section 2) becomes the step-1 build checklist; its test doctrine (section 3) governs agent-facing skills, with boss-facing halves iterating live per the walk-me precedent; its utilities wait for real need; its eval loop is the ladder rung NC revisits only if an NC skill's failures prove silent and frequent enough that live iteration demonstrably misses them.

## 7. Open sub-questions for the walk

1. The NOT/DO vs explain-why register resolution (section 2, last bullet) — confirm or re-rule.
2. Whether section 2's checklist folds into the founding plan's step 1 text now, or lives only in the skill files as they are built.
3. Whether the description-tuning idea (the one genuinely novel mechanized piece) ever earns a rung, and what evidence would justify it.
