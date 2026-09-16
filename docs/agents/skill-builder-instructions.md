# `skill-builder` — seat instructions

Read [the seat model](../nedschorus-wiki/agent-seat-model.md) first: it defines the words used here — seat, walked approval, handoff.

Your work is **the queue of proposed skills** — seven, each filed as an issue — together with [#24](https://github.com/nedschorus/nedschorus/issues/24), the queue-drain procedure. #24 is not an eighth skill: it is the process by which this queue and the project's others get emptied, so it governs how you work the other seven rather than being one of them.

They belong together because most share a shape and one authoring standard, so the later builds cost far less than the first. Two do not, and knowing which is which saves a wasted session: **#19 (`attack-artifact`) is filed as an open comparison question rather than a settled design** — the work there is to answer whether it should exist and in what form, not to build it — and **#17 (`design-change`) describes a read-only skill**, which changes what "done" looks like but not the build process.

**Reading the issues:** every item is filed as a GitHub issue, reached with `gh issue view <n> --repo nedschorus/nedschorus`. If `gh` is unauthenticated or the network is down, stop and tell the user rather than working from the summaries below — they are orientation, not specification.

A **skill** here is a Claude Code skill: a directory under `.claude/skills/<name>/` containing a `SKILL.md` whose frontmatter says when the skill applies and whose body tells an agent what to do. The live examples are `walk-me-through`, `cold-read`, `handoff`, and `ghi-write`; reading two of those closely is the cheapest way to learn the house style.

## The queue

An item's **state** — whether it is unstarted, in progress, built, or ruled out — lives in its issue: open or closed, plus whatever the body records. There is no separate tracker, so after any build or ruling, update the issue body through the `ghi-write` skill; otherwise the next session cannot tell what you did. Where an issue and its queue document disagree, the issue is authoritative on state and the queue document on substance.

| Issue | Skill | What it is for, and any material already written |
|---|---|---|
| [#18](https://github.com/nedschorus/nedschorus/issues/18) | `write-test-plan` | consequence-ranked test plans with observable oracles. Build triggered 2026-09-02, not yet built; riders in `docs/issues/queue/18-write-test-plan-agent-native-riders.md` |
| [#20](https://github.com/nedschorus/nedschorus/issues/20) | `implement-with-evidence` | red/green evidence without delete-and-start-over mandates; riders in `docs/issues/queue/20-implement-with-evidence-agent-native-riders.md` |
| [#21](https://github.com/nedschorus/nedschorus/issues/21) | `diagnose-failure` | bounded causal debugging that stops after three failed fixes rather than thrashing; detail in `docs/issues/queue/21-diagnose-failure-test-procedure.md` |
| [#22](https://github.com/nedschorus/nedschorus/issues/22) | `review-change` | defect-first code review at an exact revision, with a five-part gate a finding must pass to be reported |
| [#23](https://github.com/nedschorus/nedschorus/issues/23) | `eval-agent-change` | A/B comparison of a baseline agent against a candidate over trigger cases, reporting raw counts |
| [#19](https://github.com/nedschorus/nedschorus/issues/19) | `attack-artifact` | isolated adversarial review; filed as a comparison question rather than a settled design |
| [#17](https://github.com/nedschorus/nedschorus/issues/17) | `design-change` | read-only, evidence-grounded design producing one recommendation and honest exits |

[#24](https://github.com/nedschorus/nedschorus/issues/24) is the **queue-drain procedure** — how the project empties its wiki queue, its GHI-MD queue, and its `draft`-labelled issue queue. It governs how this seat's work is done, so read it before picking a skill.

## How skills are built here

Three rules have caught previous builds:

1. **A skill is an agent-instructions file**, so it lands only through the user's walked approval, enforced by `.claude/hooks/instruction-file-guard.py`.
2. **A skill is instructions, not an essay.** Rationale asides get cut; the text tells an agent what to do. Four such asides were removed from `walk-me-through` on 2026-08-06 for exactly this reason.
3. **Fresh-reader readability is the bar**, ruled 2026-08-11: an agent must be able to follow the skill cold. A settled draft gets the `/cold-read` skill's full run before it lands.

Expect the shape of a build to be: read the issue and its riders, draft the skill, walk it with the user item by item, give the settled draft the `/cold-read` skill, which ends in its own walk of what the review changed, then open a pull request for merge-lane to review and merge, as `CLAUDE.md` describes.

## Boundaries

The `sanity-checker` seat owns review methodology — how reviews are delivered and whether new reviewers join the cold-read run. If a skill you are building would change that, say so to the user rather than deciding it here; seats cannot hand work to each other directly, so routing is his.

Using the review machinery on your own draft is ordinary work, not a boundary crossing. Changing how it behaves is.

## First action

Read [#24](https://github.com/nedschorus/nedschorus/issues/24) (the drain procedure) and [#18](https://github.com/nedschorus/nedschorus/issues/18) with its riders file. Then start the #18 build as [How skills are built here](#how-skills-are-built-here) describes: #18's body records the build as triggered on 2026-09-02, so do not ask the user which skill to build first. A skill is still walked before it lands.
