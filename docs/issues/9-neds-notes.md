Issue: https://github.com/nedschorus/nedschorus/issues/9

## Admission note (new-vp, 2026-07-21)

Authored by cops during the boss's skills-and-methods walkthrough, admitted verbatim below (the draft's not-yet-admitted banner replaced by this note; the tail pointer to cops's local publishing file redirected to pair #4, the admitted home of publishing decisions). Deltas from the continuing walkthrough ride this pair as REVISE dispositions. Not a quarry import — fresh authorship, no entry-manifest line.

# Ned's Notes: NedsChorus Engineering Methods and Sources


## Purpose

NedsChorus is a ground-up successor informed by six months of studying,
building, testing, and observing failures in Nedlern. Nedlern is evidence and a
quarry, not a template. Nothing should transfer merely because it already
exists.

This review is limited to software-engineering lifecycle methods that directly
help NedsChorus: defining work, planning bounded projects, technical design,
test planning, implementation, testing, review of plans/tests/code, debugging,
and necessary maintenance.

## Accepted principles

1. Prefer a few small, precise, modular skills over a comprehensive workflow.
2. A candidate must help make a concrete engineering decision or produce
   checkable evidence. General advice is insufficient.
3. Evaluate exact skills and useful methods, not repositories by reputation.
4. Prefer official sources, then maintained primary projects, then carefully
   verified community work. Prompt extractions and leaked mirrors are never
   runtime contracts or dependencies.
5. Every skill needs a narrow trigger, clear inputs and outputs, stopping and
   failure behavior, safe permissions, and a way to test whether it works.
6. Test finalists against false triggering, missing context, conflicting
   instructions, partial failure, and criteria that can pass while violating
   the intent.
7. Preserve observed lessons from Nedlern, but re-decide the mechanism for
   NedsChorus. Compatibility is not automatically desirable.

## Walk-me-through: accepted behavior

The walkthrough presents one item or subitem at a time, most important first,
and advances only when Ned asks it to continue.

### Three hundred words is a comprehension budget

Three hundred words is the maximum size of one understandable cognitive packet,
not a brevity target. Use as much of that allowance as the item needs to stand
on its own. Shorter is not better when it removes context, evidence, reasoning,
examples, distinctions, or important qualifications.

An overly compressed answer can be harder to understand than a fuller answer.
When uncertain, prefer enough relevant context for Ned to understand the point
without reconstructing unstated premises.

If an item cannot be explained adequately within 300 words, divide it into two
or more separately presented items or labeled subitems. Present only one item
or subitem per turn and pause for Ned between them.

### The document changes as the walkthrough changes the decision

A walkthrough is a working review, not merely a paginated presentation of a
fixed report. After each response, determine whether the item was accepted,
rejected, revised, or remains open. Record an actual decision, correction, or
commitment in the durable working document before advancing.

When a decision invalidates or changes later material, revise, remove, or
reorder the remaining items and tell Ned if the item count or sequence changed.
Preserve the original research as evidence, but keep the working document
aligned with the current conclusion. Questions and reactions that do not change
a decision do not require document churn.

This rule was merged for the quarry's Claude and Codex skills in
[nedlern PR #2158](https://github.com/nedlern/nedlern/pull/2158). It must still
cross the nedschorus entry checkpoint before becoming a NedsChorus skill.

### One behavior contract, with thin runtime wrappers

Claude and Codex should not have independently rewritten definitions of a
walkthrough. Define one canonical behavioral contract covering triggering,
ordering, one independently reactable item per turn, the 300-word comprehension
budget, splitting, user-controlled advancement, decision capture, interruption
recovery, and completion.

Each runtime may have a thin wrapper for its required metadata, invocation
syntax, available tools, and narrowly evidenced runtime-specific cautions.
Require semantic parity rather than byte-for-byte identity.

Test both versions against the same scenarios: an over-compressed explanation,
a complex item requiring subitems, a material walkthrough that should not
re-derive settled rationale, a rejected or revised item, an interruption and
correct resumption, and a response that changes later items.

The NedsChorus skill should preserve this proven interaction pattern and the
decisions recorded here, but its packaging should be rebuilt and reviewed for
NedsChorus rather than copied wholesale from either quarry file.

processed 2026-07-22 → boss-ruled during the founding walk: the quarry's two
walk skills are being updated NOW with two behaviors from this section — the
walked-document-as-ledger rule (each item's disposition marked in place before
advancing; a walk with no document gets a ledger file first) and the re-plan
rule (a ruling that changes later items revises the remaining walk and reports
the changed count or sequence) — quarry PR link to be edited in here when it
opens. The six scenario tests above are deferred to the NC step-1 walk-me
build, judged per the agent-facing test doctrine in
`nc-queue/2026-07-22-skill-creation-and-improvement-deep-dive.md` § 3.
Recorded by edit per the same-day revision convention (revise the artifact,
never stack additive records); nedschorus#12 was opened for this deferral and
closed as consolidated here.

## Working skill shortlist

These are candidates for careful review, not a boot-set decision.

### 1. `define-work`

Use only when work is ambiguous or substantial. Produce the objective,
assumptions, non-goals, scope boundaries, acceptance evidence, open questions,
and stopping condition.

Sources worth adapting:

- OpenAI [`define-goal`](https://github.com/openai/skills/blob/main/skills/.curated/define-goal/SKILL.md): the best compact official starting point for turning an intention into a bounded objective.
- Anthropic [specification interview](https://code.claude.com/docs/en/best-practices#let-claude-interview-you): useful when important requirements are genuinely missing; it should not force interviews for routine work.

### 2. `plan-rewrite-slice`

This is probably the most NedsChorus-specific candidate. Start with one bounded
end-to-end slice, not "rewrite Nedlern." Classify relevant old behavior as
`MUST PRESERVE`, `INTENTIONAL CHANGE`, `OLD BUG`, or `UNRESOLVED`.

Source worth adapting:

- OpenAI [code-modernization workflow](https://developers.openai.com/cookbook/examples/codex/code_modernization): valuable because it separates current behavior, target design, parity/validation, and the executable plan. It needs stricter protection against blindly preserving old defects.

### 3. `design-change`

Read-only technical design grounded in repository evidence. Recommend one
architecture and cover boundaries, interfaces, data flow, failure behavior,
likely files, implementation order, and validation.

Sources worth adapting:

- Anthropic [`code-architect`](https://github.com/anthropics/claude-code/blob/main/plugins/feature-dev/agents/code-architect.md): the strongest direct official design-agent example found.
- OpenAI [ExecPlans](https://developers.openai.com/cookbook/articles/codex_exec_plans): useful for executable, self-contained plans, but its full form is too large for routine work and should not require explaining everything to a complete novice.

### 4. `write-test-plan`

Build this for NedsChorus. No published skill found so far is strong enough to
adopt. Its compact core should trace:

`requirement or risk -> test level -> setup -> stimulus -> observable oracle -> expected failure -> exact command -> automated or human -> justified exclusion`

Source worth studying:

- Anthropic [`pr-test-analyzer`](https://github.com/anthropics/claude-code/blob/main/plugins/pr-review-toolkit/agents/pr-test-analyzer.md): the best official rubric found, but it evaluates tests after a PR rather than designing a test plan beforehand.

### 5. `attack-artifact`

Use a fresh-context reviewer on a design, plan, or test plan. Find
contradictions, ambiguous terms, hidden dependencies, untestable claims,
missing failure modes, and criteria an implementation could satisfy while
violating the intent.

Sources worth adapting:

- Anthropic [adversarial review guidance](https://code.claude.com/docs/en/best-practices#add-an-adversarial-review-step): the best official statement of the fresh-context review pattern.
- Addy Osmani [`doubt-driven-development`](https://github.com/addyosmani/agent-skills/blob/main/skills/doubt-driven-development/SKILL.md): useful questioning discipline from a respected practitioner, but not an authority or a complete review contract.

### 6. `implement-with-evidence`

For a scoped behavior change: observe the new check fail for the intended
reason, make the smallest relevant implementation, then run the appropriate
regression checks.

Source worth extracting from:

- Superpowers [`test-driven-development`](https://github.com/obra/superpowers/blob/main/skills/test-driven-development/SKILL.md): preserves the valuable red/green evidence contract. Do not import its absolutist or potentially destructive instructions, such as deleting already-written code merely because the test was written second.

### 7. `diagnose-failure`

Preserve evidence, reproduce the failure, trace it across boundaries, state one
hypothesis, test one variable, fix the causal fault, and verify. Distinguish an
emergency mitigation from a demonstrated root-cause correction.

Sources worth adapting:

- Anthropic [context and reproduction guidance](https://code.claude.com/docs/en/best-practices#provide-specific-context-in-your-prompts): authoritative high-level direction.
- Superpowers [`systematic-debugging`](https://github.com/obra/superpowers/blob/main/skills/systematic-debugging/SKILL.md): a useful causal loop, provided it has a finite stopping condition and does not turn "root cause" into endless recursion.

### 8. `review-change`

Read-only, independent review of an exact revision. A finding needs a
demonstrable scenario, affected behavior, file/line evidence, and actionable
severity. The reviewer must be allowed to report a clean result.

Sources worth adapting:

- OpenAI [`review-agent`](https://github.com/openai/codex/blob/main/codex-rs/skills/src/assets/samples/review-agent/SKILL.md): the strongest compact official review skill found.
- Google [What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html): a careful, durable engineering rubric from an experienced organization; use it as review criteria, not as an agent workflow.

### 9. `eval-agent-change`

Use for behavioral prompts, skills, routing, guards, and other agent changes.
Test trigger and anti-trigger cases, baseline versus candidate, real runtime
builds, regressions, and capability improvements.

Sources worth adapting or investigating:

- Anthropic [agent-evaluation method](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents): the best official conceptual source found for evaluating agents rather than merely unit-testing code.
- Anthropic [Claude Code quality postmortem](https://www.anthropic.com/engineering/april-23-postmortem): useful evidence that runtime/version coverage and separate regression metrics matter.
- Microsoft [Waza](https://github.com/microsoft/waza): worth testing as a harness because it supports skill/no-skill baselines and trigger/anti-trigger checks. Investigate the smallest useful method before adopting the platform.

## Sources retained for narrow research only

- [Piebald's versioned Claude Code prompt extraction](https://github.com/Piebald-AI/claude-code-system-prompts): the best focused non-official source found for comparing shipped Claude Code prompt and tool-description changes across versions. Use for version archaeology and hypothesis generation, never as a supported contract or executable dependency.
- [Asgeirtj's cross-vendor prompt archive](https://github.com/asgeirtj/system_prompts_leaks): useful for broad historical comparison. Provenance varies by file, so any derived claim needs the model, surface, version/date, extraction method, and confidence recorded.
- [DonutShinobu Claude Code fork](https://github.com/DonutShinobu/claude-code-fork) and [Tanbiralam Claude Code mirror](https://github.com/tanbiralam/claude-code): retained only so the original research trail is not lost. They are duplicate, stale leaked-source archives with provenance and copyright concerns. Do not clone, execute, install, depend on, or cite them in public NedsChorus material.

## Deliberately excluded from the shortlist

- Repository-sized "do everything" development systems.
- Anthropic's full `feature-dev` workflow as a mandatory lifecycle: too many agents and gates, although individual components may be useful.
- Superpowers `brainstorming` and `writing-plans` as universal gates: too ceremonial and too granular for ordinary work.
- Superpowers TDD unchanged: the evidence loop is valuable; the absolutism is not.
- GitHub Awesome Copilot's large breakdown and council playbooks.
- OpenAI Codex's internal all-reviewer orchestration as a default.
- Automatic four-agent simplification passes.
- Numeric quality ratings and arbitrary file-count or line-count thresholds.
- Generic "awesome" lists as recommendations. They are discovery indexes only.

## Still under review

- Which small subset of the nine candidate skills belongs in the initial
  NedsChorus boot set.
- The rewrite policy: which Nedlern behaviors are genuine compatibility
  requirements and which should be abandoned, corrected, or re-decided.
- Whether this note remains an internal working document or becomes public. If
  public, the leaked-source archive should probably be omitted entirely.

## Related working note

Publishing and community decisions are currently recorded separately in
the admitted publishing pair, [nedschorus#4](https://github.com/nedschorus/nedschorus/issues/4) (`docs/issues/4-open-source-publishing-community-strategy.md`).
They should not dilute this engineering-method shortlist.
