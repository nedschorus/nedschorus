# `skill-builder` — seat instructions

Read [the seat model](agent-seat-model.md) first: it defines the words used here — pile, seat, walked approval, instruction-class, handoff.

Your pile is **the queue of proposed skills**: seven of them, each filed as an issue, plus the procedure that drains the project's queues. They belong together because every build has the same shape and shares one authoring standard, so the seventh should cost far less than the first.

A **skill** here is a Claude Code skill: a directory under `.claude/skills/<name>/` containing a `SKILL.md` whose frontmatter says when the skill applies and whose body tells an agent what to do. The live examples are `walk-me-through`, `md-review`, `handoff`, and `ghi-write`; reading two of those closely is the cheapest way to learn the house style.

**Your work is done when** each issue below is either built and landed, ruled out with the reason recorded in the issue, or left with a stated blocker. You will not finish all seven in one series — build one, hand off, and let the next session take the next. Then write a handoff and stop.

## The queue

| Issue | Skill | What it is for, and any material already written |
|---|---|---|
| [#18](https://github.com/nedschorus/nedschorus/issues/18) | `write-test-plan` | consequence-ranked test plans with observable oracles. Flagged as the likely first build; riders in `docs/issues/queue/18-write-test-plan-agent-native-riders.md` |
| [#20](https://github.com/nedschorus/nedschorus/issues/20) | `implement-with-evidence` | red/green evidence without delete-and-start-over mandates; riders in `docs/issues/queue/20-implement-with-evidence-agent-native-riders.md` |
| [#21](https://github.com/nedschorus/nedschorus/issues/21) | `diagnose-failure` | bounded causal debugging that stops after three failed fixes rather than thrashing; detail in `docs/issues/queue/21-diagnose-failure-test-procedure.md` |
| [#22](https://github.com/nedschorus/nedschorus/issues/22) | `review-change` | defect-first code review at an exact revision, with a five-part gate a finding must pass to be reported |
| [#23](https://github.com/nedschorus/nedschorus/issues/23) | `eval-agent-change` | A/B comparison of a baseline agent against a candidate over trigger cases, reporting raw counts |
| [#19](https://github.com/nedschorus/nedschorus/issues/19) | `attack-artifact` | isolated adversarial review; filed as a comparison question rather than a settled design |
| [#17](https://github.com/nedschorus/nedschorus/issues/17) | `design-change` | read-only, evidence-grounded design producing one recommendation and honest exits |

[#24](https://github.com/nedschorus/nedschorus/issues/24) is the **queue-drain procedure** — how the project empties its wiki queue, its pair queue, and its `draft`-labelled issue queue. It governs how this pile is worked, so read it before picking a skill.

## How skills are built here

Find the project's **skill-authoring checklist** under `docs/` and follow it — it predates you and is the standard your work will be judged against. Three rules have caught previous builds:

1. **A skill is instruction-class**, so it lands only through the user's walked approval, enforced by `.claude/hooks/instruction-file-guard.py`.
2. **A skill is instructions, not an essay.** Rationale asides get cut; the text tells an agent what to do. Four such asides were removed from `walk-me-through` on 2026-08-06 for exactly this reason.
3. **Zero-context readability is the bar**, ruled 2026-08-11: an agent must be able to follow the skill cold. A settled draft gets an md-review before it lands, which is `scripts/md-review-grid.py`.

Expect the shape of a build to be: read the issue and its riders, draft the skill, walk it with the user item by item, md-review the settled draft, apply what the review finds, then commit and push for his Mac-side agent to merge.

## Boundaries

The `sanity-checker` seat owns review methodology — how reviews are delivered and whether new reviewers join the md-review grid. If a skill you are building would change that, say so to the user rather than deciding it here; seats cannot hand work to each other directly, so routing is his.

Using the review machinery on your own draft is ordinary work, not a boundary crossing. Changing how it behaves is.

## First action

Read [#24](https://github.com/nedschorus/nedschorus/issues/24) (the drain procedure) and [#18](https://github.com/nedschorus/nedschorus/issues/18) with its riders file. Then tell the user which skill you propose building first and why, and wait for his ruling — the order is his, and a skill is walked before it lands.
