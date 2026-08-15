<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=restate tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/skill-builder-instructions.md -->

# `skill-builder` — seat instructions

1. The work assigned to this seat is the set of proposed skills waiting to be built, called the candidate-skill queue.
2. There are seven proposed skills. They all use the same general structure, authoring checklist, and user-guided walk process. Because those methods can be reused, the seventh skill should require substantially less effort than the first; “far cheaper” has no precise measurement here.
3. Read `agent-seat-model.md` to understand what the project means by a “seat” and how seats operate.

## The queue

1. Each proposed skill has an issue that records its current state. Some of them also have a queue document containing further details.
2. Issue #18 is for `write-test-plan`, a skill for plans ordered according to consequence and using observable oracles—concrete, externally checkable results that indicate whether something worked. The issue is marked as the probable first skill to build.
3. Additional material for #18 is in `docs/issues/queue/18-write-test-plan-agent-native-riders.md`; “riders” means supplementary requirements or notes attached to the main queue item.
4. Issue #20 is for `implement-with-evidence`, a skill centered on a red/green evidence kernel. I take that phrase to mean a core method distinguishing unsuccessful or failing evidence from successful or passing evidence, although the exact mechanism is not defined here. The skill must not require deleting the current attempt and starting over.
5. Additional material for #20 is in `docs/issues/queue/20-implement-with-evidence-agent-native-riders.md`.
6. Issue #21 is for `diagnose-failure`, a skill for causal debugging conducted within defined limits. It includes a “three-fix escalation stop,” which I take to mean that after three attempted fixes the process must stop or escalate; the wording does not say exactly which of those happens or how the count is applied.
7. The detailed procedure for #21 is in `docs/issues/queue/21-diagnose-failure-test-procedure.md`.
8. Issue #22 is for `review-change`, a skill that reviews one exact revision, looks for defects as the first priority, and requires a finding to pass five separate conditions before it is accepted. The five conditions are not listed here.
9. Issue #23 is for `eval-agent-change`, a skill that compares a baseline and a candidate in an A/B evaluation, includes cases intended to trigger the relevant behavior, and reports unaggregated numerical counts rather than only summaries or percentages.
10. Issue #19 is for `attack-artifact`, a skill that performs an adversarial review in isolation. It was submitted as a question comparing something called a “d-review” with another approach; neither “d-review” nor the comparison target is defined here.
11. Issue #17 is for `design-change`, a design skill that only reads and reasons from evidence, does not make changes, gives one recommendation rather than several alternatives, and provides candid ways to stop, decline, or acknowledge insufficient evidence. The exact “honest exits” are not specified.
12. In addition to those seven skills, issue #24 defines the queue-drain procedure: a review process intended to empty the wiki queue, the pair queue, and the draft-label issue queue.
13. That procedure controls how the remaining proposed skills are processed, so it should be read near the beginning.

## How skills are built here

1. Locate the project’s skill-authoring checklist under `docs/` and follow it. It is the project’s established standard, and it existed before the current agent.
2. The existing skills—`.claude/skills/walk-me-through/`, `.claude/skills/md-review/`, `.claude/skills/handoff/`, and `.claude/skills/ghi-write/`—are examples of the desired form. Reading two of them carefully is presented as the least costly way to learn the project’s customary writing style.
3. The next three rules address problems that have caused trouble in earlier skill builds; “bitten” is figurative and means those problems led to bad or difficult builds.
4. A skill is “instruction-class,” which I take to mean that its primary nature is an operational instruction artifact rather than an essay or general explanation.
5. A skill becomes part of the project only through the user’s walk process, and the `instruction-file-guard` hook enforces this automatically.
6. The enforcement mechanism uses a `.walk-approved` marker containing a quotation of the user’s approval, and that marker is consumed by exactly the one write operation it authorizes.
7. Skills should be written as instructions for an agent to follow, not as essays.
8. Explanatory asides about rationale are removed, while the remaining text tells the agent what action to take.
9. Four rationale asides were removed from `walk-me-through` on 2026-08-06 because they violated that instruction-focused standard.
10. The required standard is readability without surrounding context.
11. On 2026-08-11, the user decided that agents must be able to understand their instructions without prior conversation or additional explanation. Therefore, a skill draft that has reached a settled state must undergo `md-review` before it becomes part of the project. “Lands” means being incorporated or accepted, though the exact integration mechanism is not stated here.

## Related work you did not do

1. The `sanity-checker` seat is responsible for review methodology and may add another reviewer to the `md-review` grid. PRs #51 and #53 belong to that seat’s work.
2. If building a skill would alter the way reviews are delivered, transfer that portion of the work to the `sanity-checker` seat instead of making the decision within this seat.

## First action

1. Read issue #24 and issue #18, including the riders file associated with #18. Then tell the user which skill you recommend building first and the reason for that recommendation.
2. Do not build anything before the user decides. The user determines the order, and every skill must go through the walk process before it becomes part of the project.
