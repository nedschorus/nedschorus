# Skill authoring checklist

Consult this whenever a NedsChorus skill is created or revised. Distilled 2026-07-24 (outer walk item 11, boss-approved) from the read-for-ideas-only extraction of Anthropic's skill-creator; full evidence in `nc-queue/2026-07-22-skill-creation-and-improvement-deep-dive.md` and the cops delta packet §11. Every skill-build GHI points here; the founding plan's step 1 builds against this list.

## Four questions before writing anything

1. What should the skill enable?
2. When should it trigger — the actual user phrases and contexts? And when must it *not*?
3. What output format is expected?
4. Are the outputs objectively verifiable? Verifiable outputs get test cases; subjective outputs get human judgment. (This is the boss-facing/agent-facing split — Anthropic reached the same rule independently.)

## The description is the trigger

The ~100-word description is the only part of a skill the model sees when deciding whether to invoke it; the body is invisible until invocation. So:

- Put every piece of when-to-use information in the description, not the body. Phrase it as user intent, imperative form.
- Front-load a concise positive AND negative scope: use for X; not for Y.
- "Pushy" descriptions are a Claude-specific hypothesis, not doctrine — adopt only with false-trigger tests showing they help. Word-count targets are not portable across runtimes (fields get capped and truncated differently); measure, don't copy.
- Descriptions compete for a capped listing budget. Many skills are fine; many *vague* skills degrade every skill's routing, because each dilutes the others' claim on attention.

## Structure: progressive disclosure

- Description/metadata: always in context. Body: loads on invocation — keep it under 500 lines. Bundled references and scripts: unlimited, behind a table of contents.
- Approaching the body limit means add hierarchy, not compression. Compression must preserve scope conditions and qualifiers verbatim — dropping a qualifier widens the rule's claim; that is a semantic change, not a shortening.

## Register

- Explain why a rule matters instead of stacking MUSTs; all-caps ALWAYS/NEVER is a yellow flag — reframe with the reasoning.
- Reserve NOT/DO pairs for instructions that override a training default; that is the case they were invented for, and they earn nothing elsewhere.

## Testing agent-facing skills

These rules govern any skill (or skill half) whose failures are silent. Boss-supervised interaction halves iterate in live use instead — their final quality judgment is human.

- Assertions are objectively verifiable statements with descriptive names; subjective qualities go to a human, never forced into assertions.
- An assertion that passes for both a good and a bad output is worse than useless — it manufactures false confidence. Discriminating power is the bar, and critiquing the evals themselves is part of the grader's job.
- Negative trigger tests must be near-misses: they share the skill's keywords but lack its essence. Easy negatives prove nothing.
- Burden of proof is on the expectation; no partial credit; evidence must show genuine task completion, not surface compliance.
- Checkable assertions are checked by script, not eyeballed.
- Scenario taxonomy (pair #9, principle 6): false trigger, missing context, conflicting instructions, partial failure, criteria-pass-while-intent-violated.

## Deliberately excluded, with its reopening trigger

skill-creator's iteration machinery — review UIs, benchmark loops, the description optimizer — is not adopted; it is complexity the earned-complexity ladder has not admitted, and its trigger measurement is a proxy. Revisit only if an NC skill's failures prove silent and frequent enough that live iteration demonstrably misses them, and only after false-trigger tests exist for the trigger claims involved.
