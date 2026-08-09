# Skill authoring checklist

Consult this whenever a NedsChorus skill is created or revised. Distilled 2026-07-24 (outer walk item 11, user-approved) from the read-for-ideas-only extraction of Anthropic's skill-creator; full evidence in `nc-queue/archived/2026-07-22-skill-creation-and-improvement-deep-dive.md` and the cops delta packet §11. Every skill-build GHI points here; the founding plan's step 1 builds against this list.

## Five questions before writing anything

1. What should the skill enable?
2. When should it trigger — the actual user phrases and contexts? And when must it *not*?
3. What output format is expected?
4. Are the outputs objectively verifiable? Verifiable outputs get test cases; subjective outputs get human judgment. (This is the user-facing/agent-facing split — Anthropic reached the same rule independently.)
5. **Which steps are machine work?** Anything with a determinate answer — a timestamp, a computed value, a file's format, a check whose result is yes or no — belongs in a script the skill runs, leaving the agent only what needs judgment. Ask this *before* reviewing any wording: a wording review presupposes the division of labor and structurally cannot find an error in it. (User-ruled 2026-08-06, from the `handoff` skill's walk, where a step-by-step review of the text validated three steps of agent-performed machine work before the user asked why a script was not doing it; the review had even flagged one of those steps and then declined to act on the flag.) More generally: if a tool or program can replace prompt-driven work with a faster and more reliable solution, that replacement should be examined — at build time and again in use. (User-ruled 2026-08-08.)

## The description is the trigger

The ~100-word description is the only part of a skill the model sees when deciding whether to invoke it; the body is invisible until invocation. So:

- Put every piece of when-to-use information in the description, not the body. Phrase it as user intent, imperative form.
- Front-load a concise positive AND negative scope: use for X; not for Y.
- "Pushy" descriptions are a Claude-specific hypothesis, not doctrine — adopt only with false-trigger tests showing they help. Word-count targets are not portable across runtimes (fields get capped and truncated differently); measure, don't copy.
- Descriptions compete for a capped listing budget. Many skills are fine; many *vague* skills degrade every skill's routing, because each dilutes the others' claim on attention.
- The description states *when* to invoke, never *how* the skill works. A description that summarizes the workflow becomes a competing summary the agent follows instead of the body — the description is always in context while the body loads only on invocation (observed once, human-authored, in the source's tests: a workflow-summarizing description caused one review pass where the body required two). If the description alone is enough to act on, move the how into the body. (Superpowers extract, 2026-07-31.)

## Structure: progressive disclosure

- Description/metadata: always in context. Body: loads on invocation — keep it under 500 lines. Bundled references and scripts: unlimited, behind a table of contents.
- Approaching the body limit means add hierarchy, not compression. Compression must preserve scope conditions and qualifiers verbatim — dropping a qualifier widens the rule's claim; that is a semantic change, not a shortening.

## Register

- A skill answers three questions, worded as simply and plainly as reasonable: when to use it, what to do, how to do it. It contains clear instructions, never information whose point in the file is unclear — no statistics, measured anecdotes, incident specimens, or out-of-context examples; if removing such content leaves a rule unclear, rewrite the rule to carry the clarity. Justifying data lives in the records stores and git history. (User-ruled 2026-08-05; placed here from the step-2 CLAUDE.md admission 2026-08-06 — this checklist, not the floor, governs skill content.)
- Skills stay atomic: a skill references other MD files by explicit path, never by assumed knowledge; shared project concepts a skill relies on are defined in CLAUDE.md, once — not restated per skill. (User-ruled 2026-08-04; placed here 2026-08-06.)
- Explain why a rule matters instead of stacking MUSTs; all-caps ALWAYS/NEVER is a yellow flag — reframe with the reasoning.
- Reserve NOT/DO pairs for instructions that override a training default; that is the case they were invented for, and they earn nothing elsewhere.
- Match an instruction's form to the failure it fixes — or, for preventive guidance, the failure it most plausibly prevents (superpowers extract, 2026-07-31; source: obra/superpowers `writing-skills`; context and decline records: `nc-queue/2026-07-31-superpowers-extracts.md` (moves to `nc-queue/archived/` at dispersal)):
  - Wrong *shape* of output → a positive recipe: state what the output IS. In the source's measured wording tests, prohibition-only guidance produced clearly more of the unwanted content than the recipe form, and was directionally (not decisively) worse than no guidance at all. For load-bearing guidance, micro-test your own wording with a no-guidance control rather than assuming the result transfers.
  - A part omitted from output the agent otherwise produces correctly → a required structural slot (a named section that must exist), not an exhortation to remember.
  - Conditional guidance ("when X, do Y") → write X as an observable predicate the agent can test. A judgment call dressed as a condition does not reliably trigger.
  - Keep a working recipe free of nuance clauses — vague escape hatches like "unless it matters": in the same wording tests, one such clause made a winning recipe's results inconsistent across trials. A genuine exception is its own conditional on an observable predicate (a scope restriction, not a nuance clause).
- A NOT without a paired DO is unreliable — the not-space is infinite (user-ruled 2026-07-31). The wording tests above measured NOT-alone against recipe and no-guidance forms; they are consistent with this rule but did not test pairs.
- The source's remaining machinery — standalone prohibition lists (NOTs with no paired DO) and rationalization tables — addresses agents whose long context holds their own prior work and self-justifications ("just this once"). NC's role separation gives one-shot workers fresh constructed context with no such investment, so for them that machinery is not imported; long-context surfaces (orchestrators, user-facing interactive sessions) remain exposed and are protected by code-enforced gates and reasoned rules, not by imported prohibition machinery (user-ruled 2026-07-31). An absolute that truly must hold gets code enforcement — a gatekeeper check, a lint — when buildable, filed as its own build task rather than built mid-authoring; until then it lives as a reasoned rule, and prompt text alone is not treated as enforcement of an absolute.

## Testing agent-facing skills

These rules govern any skill (or skill half) whose failures are silent. User-supervised interaction halves iterate in live use instead — their final quality judgment is human.

- Assertions are objectively verifiable statements with descriptive names; subjective qualities go to a human, never forced into assertions.
- An assertion that passes for both a good and a bad output is worse than useless — it manufactures false confidence. Discriminating power is the bar, and critiquing the evals themselves is part of the grader's job.
- Trigger tests are written only where triggering is genuinely uncertain — a boundary shared with a sibling skill, an unfamiliar domain. A heavily-trained concept behind a plain description triggers correctly without testing. (User-ruled 2026-08-08.)
- Positive trigger tests must be substantive: a one-step task the model would just do directly consults no skill however apt the description, so an easy positive proves nothing. (skill-creator's stated triggering mechanic, unmeasured by NC; re-check note 2026-08-07.)
- Negative trigger tests are rarely needed — only where false-triggering is a live risk, chiefly a sibling skill that could capture the work. When one is written it must be a near-miss: it shares the skill's keywords but lacks its essence. Easy negatives prove nothing. (Rarity user-ruled 2026-08-08; near-miss rule unchanged from the 2026-07-24 distillation.)
- Burden of proof is on the expectation; no partial credit; evidence must show genuine task completion, not surface compliance.
- Checkable assertions are checked by script, not eyeballed.
- Scenario taxonomy (pair #9, principle 6): false trigger, missing context, conflicting instructions, partial failure, criteria-pass-while-intent-violated.
- Micro-testing a load-bearing wording (referenced by the Register section): run the task with no guidance first — no failure means the guidance isn't needed; then each candidate wording as fresh-context single calls embedded in its realistic surrounding text (the full skill, not the wording alone), on a task that tempts the failure, 5+ repetitions; read every flagged output manually (template echoes fake as compliance); treat variance as a metric — five interpretations across five reps means the wording does not bind. (Superpowers extract, 2026-07-31.)

## Deliberately excluded, with its reopening trigger

skill-creator's iteration machinery — review UIs, benchmark loops, the description optimizer — is not adopted; it is complexity the earned-complexity ladder has not admitted, and its trigger measurement is a proxy. Revisit only if an NC skill's failures prove silent and frequent enough that live iteration demonstrably misses them, and only after false-trigger tests exist for the trigger claims involved.
