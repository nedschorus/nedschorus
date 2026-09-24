---
issue: "[Candidate skill: write-test-plan — consequence-ranked test plan with observable oracles and traceability (likely FIRST build)](https://github.com/nedschorus/nedschorus/issues/18)"
---

# Candidate skill: write-test-plan — consequence-ranked test plan with observable oracles and traceability (likely FIRST build)

Before building: rank requirements by consequence (1-10 criticality); per requirement specify level, setup, stimulus, observable oracle, expected failure caught, exact command, automated-vs-human, justified exclusions; requirement->test traceability. Evidence: no adoptable end-to-end source exists; import the criticality scale and oracle framing from Anthropic pr-test-analyzer, the traceability method from Waza spec-verify. cops: highest-value missing packaged capability; leading dogfood candidate for the git-gatekeeper build, whose trial correctly returned needs-design-clarification rather than inventing commands. Flagged as the likely first actual build, manual evaluation.

## Pair document

The substance is in [write-test-plan: the riders, and the rules on what counts as test evidence](https://github.com/nedschorus/nedschorus/blob/main/docs/issues/18-write-test-plan-riders-and-test-evidence-rules.md): the four riders drained from the queue on 2026-09-02, the worked example that triggered the build, the user's rules on what evidence a change needs before it merges, and the evidence of record. It moved out of this body on 2026-09-16, when the next ruling would have taken the body past its 1000-word cap. This body keeps the summary, the disposition and the next action.

## Disposition: BUILD TRIGGERED 2026-09-02

The 2026-07-24 ruling recorded below said candidates are recorded and none is built now, and that "a build triggers only when a real task exposes the missing decision". That condition is met. On 2026-08-31 three defects shipped in `scripts/find-deleted-path-across-backups.py` and were fixed across two pull requests, both cited in the pair document. The user asked how to prevent the class, three prevention rules were drafted and walked, and the walk established that the rules being derived are instances of the riders already specified for this skill. The skill is the answer rather than three new `CLAUDE.md` bullets.

Prior disposition, superseded: candidate-on-GHI, not built, user-ruled 2026-07-24 on the outer walk (session ad0a3708) as one of nine candidates recorded together, with the build trigger quoted above. Full text in this body's edit history.

## Next action

One question comes before the build: whether write-test-plan is a skill at all.

The user ruled on 2026-09-06, on the reboot-test seat's walk, that a capability belonging to a design-to-main node is that node's agent-instructions rather than a skill. Planning a test suite is what design-to-main's `test-design-writing` node does, and a draft of that node's agent-instructions already exists at `docs/agents/queue/design-to-main-test-design-writing-agent-instructions.md`.

So settle that first, because the answer decides what the build produces: a `SKILL.md` under `.claude/skills/`, or agent-instructions under `docs/agents/`. Either way the riders in the pair document are the content.
