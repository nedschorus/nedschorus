# `skill-builder` — seat instructions

Your pile: **the candidate-skill queue.** Seven proposed skills, each a build of the same shape, sharing one authoring checklist and one walk process — which is exactly why they belong to one seat: the seventh build should be far cheaper than the first. Read [the seat model](agent-seat-model.md) for how seats work.

## The queue

Each has an issue carrying its state and, in several cases, a queue document carrying detail:

| Issue | Skill | Note |
|---|---|---|
| [#18](https://github.com/nedschorus/nedschorus/issues/18) | `write-test-plan` | consequence-ranked plans with observable oracles; **flagged as the likely first build**. Riders in `docs/issues/queue/18-write-test-plan-agent-native-riders.md` |
| [#20](https://github.com/nedschorus/nedschorus/issues/20) | `implement-with-evidence` | red/green evidence kernel, no delete-and-start-over mandates. Riders in `docs/issues/queue/20-implement-with-evidence-agent-native-riders.md` |
| [#21](https://github.com/nedschorus/nedschorus/issues/21) | `diagnose-failure` | bounded causal debugging with a three-fix escalation stop. Detail in `docs/issues/queue/21-diagnose-failure-test-procedure.md` |
| [#22](https://github.com/nedschorus/nedschorus/issues/22) | `review-change` | exact-revision defect-first review with a five-part finding gate |
| [#23](https://github.com/nedschorus/nedschorus/issues/23) | `eval-agent-change` | baseline-vs-candidate A/B with trigger cases and raw-count reporting |
| [#19](https://github.com/nedschorus/nedschorus/issues/19) | `attack-artifact` | isolated adversarial review; filed as a d-review comparison question |
| [#17](https://github.com/nedschorus/nedschorus/issues/17) | `design-change` | read-only evidence-grounded design, one recommendation, honest exits |

Plus [#24](https://github.com/nedschorus/nedschorus/issues/24), the **queue-drain procedure** — the review process that empties the wiki queue, the pair queue, and the draft-label issue queue. It governs how the rest of this pile is worked, so read it early.

## How skills are built here

Find the **skill-authoring checklist** under `docs/` and follow it; it is the project's own standard and predates you. The existing skills are the worked examples — `.claude/skills/walk-me-through/`, `.claude/skills/md-review/`, `.claude/skills/handoff/`, `.claude/skills/ghi-write/` — and reading two of them closely is the cheapest way to learn the house style.

Three rules that have bitten previous builds:

1. **A skill is instruction-class.** It lands only through the user's walk, and the `instruction-file-guard` hook enforces that mechanically — a `.walk-approved` marker quoting his approval, consumed by the one write it approves.
2. **Skills are instructions, not essays.** Rationale asides get cut; the text tells an agent what to do. Four such asides were cut from `walk-me-through` on 2026-08-06 for exactly this reason.
3. **Zero-context readability is the bar.** The user ruled 2026-08-11 that agents must understand their instructions cold, which is why a settled skill draft gets an md-review before it lands.

## Related work you did not do

The `sanity-checker` seat owns review methodology and may add a reviewer to the md-review grid; PRs #51 and #53 are its business. If a skill you are building would change how reviews are delivered, hand that part over rather than deciding it here.

## First action

Read [#24](https://github.com/nedschorus/nedschorus/issues/24) (the drain procedure) and [#18](https://github.com/nedschorus/nedschorus/issues/18) (the likely first build) with its riders file, then tell the user which skill you propose building first and why. Build nothing until he rules — the order is his call, and a skill is walked before it lands.
