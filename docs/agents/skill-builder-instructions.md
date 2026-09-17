# `skill-builder` — seat instructions

Read [the seat model](../nedschorus-wiki/agent-seat-model.md) first: it defines the words used here — seat, walked approval.

Your work is **the queue of proposed skills** — seven, each filed as an issue — together with [#24](https://github.com/nedschorus/nedschorus/issues/24), the queue-drain procedure. #24 is not an eighth skill: it is the process by which the project's queues get emptied, so it governs how you work the other seven rather than being one of them.

They belong together because most share a shape and one authoring standard, so the later builds cost far less than the first. Two do not, and knowing which is which saves a wasted session: **#19 (`attack-artifact`) is filed as an open comparison question rather than a settled design** — the work there is to answer whether it should exist and in what form, not to build it — and **#17 (`design-change`) describes a read-only skill**, which changes what "done" looks like but not the build process.

**Reading the issues:** every item is filed as a GitHub issue, reached with `gh issue view <n> --repo nedschorus/nedschorus --comments`. If `gh` cannot read the issue, stop and tell the user rather than working from the summaries below — they are orientation, not specification.

A **skill** here is a Claude Code skill: a directory under `.claude/skills/<name>/` containing a `SKILL.md` whose frontmatter says when the skill applies and whose body tells an agent what to do. The live examples include `walk-me-through`, `cold-read`, `handoff`, and `ghi-write`; reading two of those closely is the cheapest way to learn the house style.

## The queue

An item's **state** — whether it is unstarted, in progress, built, or ruled out — lives in its issue: open or closed, plus whatever the body records. There is no separate tracker, so after any build or ruling, update the issue body through the `ghi-write` skill; otherwise the next session cannot easily tell what you did. Where an issue and its queue document disagree, the issue wins; a queue document is material still waiting for the user's review.

Only #18's build has been triggered. Each of the other six records a 2026-07-24 ruling in its body: the candidate is recorded, not built, until a real task exposes the missing decision and triggers its build.

| Issue | Skill | What it is for, and any material already written |
|---|---|---|
| [#18](https://github.com/nedschorus/nedschorus/issues/18) | `write-test-plan` | consequence-ranked test plans with observable oracles. Build triggered 2026-09-02, not yet built; riders drained into the issue body on 2026-09-02 (§ Riders, drained from the queue) from `docs/issues/queue/18-write-test-plan-agent-native-riders.md` |
| [#20](https://github.com/nedschorus/nedschorus/issues/20) | `implement-with-evidence` | red/green evidence without delete-and-start-over mandates; riders in `docs/issues/queue/20-implement-with-evidence-agent-native-riders.md` |
| [#21](https://github.com/nedschorus/nedschorus/issues/21) | `diagnose-failure` | bounded causal debugging that stops after three failed fixes rather than thrashing; detail in `docs/issues/queue/21-diagnose-failure-test-procedure.md` |
| [#22](https://github.com/nedschorus/nedschorus/issues/22) | `review-change` | defect-first code review at an exact revision, with a five-part gate a finding must pass to be reported |
| [#23](https://github.com/nedschorus/nedschorus/issues/23) | `eval-agent-change` | A/B comparison of a baseline agent against a candidate over trigger cases, reporting raw counts |
| [#19](https://github.com/nedschorus/nedschorus/issues/19) | `attack-artifact` | isolated adversarial review; filed as a comparison question rather than a settled design |
| [#17](https://github.com/nedschorus/nedschorus/issues/17) | `design-change` | read-only, evidence-grounded design producing one recommendation and honest exits |

[#24](https://github.com/nedschorus/nedschorus/issues/24) is the **queue-drain procedure** — how the project empties its wiki queue, its GHI-MD queue, and its `draft`-labelled issue queue. It governs how this seat's work is done, so read it before picking a skill.

## How skills are built here

Three rules have caught previous builds:

1. **A skill's files are agent-instructions files**, so a skill lands only through the user's walked approval, guarded by `.claude/hooks/instruction-file-guard.py` (a soft block on file-tool writes under `.claude/`).
2. **A skill is instructions, not an essay.** Rationale asides get cut; the text tells an agent what to do. Four such asides were removed from `walk-me-through` on 2026-08-06 for exactly this reason.
3. **Fresh-reader readability is the bar**, ruled 2026-08-11: an agent must be able to follow the skill cold. A settled draft gets the `/cold-read` skill's full run before it lands.

Expect the shape of a build (not of #19, which is a question) to be: read the issue and any riders the issue or the table names, draft the skill under `docs/agents/queue/`, where `ghi-write` routes agent-instructions drafts, walk it with the user item by item, give the settled draft the `/cold-read` skill, which ends in its own walk of what the review changed, move it under `.claude/skills/<name>/` with the walked-approval marker, then open a pull request for merge-lane to review and merge, as `CLAUDE.md` describes.

## Boundaries

Changing how the review instruments work — the `/cold-read` and `/sanity-check` skills and their scripts — is not this seat's work; if a skill you are building would change them, say so to the user. Routing work to another seat is his call, except announcing your pull request to merge-lane, once.

Using the review machinery on your own draft is ordinary work, not a boundary crossing. Changing how it behaves is.

## First action

Read [#24](https://github.com/nedschorus/nedschorus/issues/24) (the drain procedure) and [#18](https://github.com/nedschorus/nedschorus/issues/18) with the riders in its body. Then, unless #18's body now records the build begun or done, start the #18 build as [How skills are built here](#how-skills-are-built-here) describes: #18's body records that the 2026-09-02 walk met the build's trigger, so do not ask the user which skill to build first. A skill still takes the user's walked approval before it lands.
