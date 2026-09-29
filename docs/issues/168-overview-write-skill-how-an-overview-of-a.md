---
issue: "[overview-write skill: how an overview of a system is written and checked before it lands](https://github.com/nedschorus/nedschorus/issues/168)"
---

# overview-write skill: how an overview of a system is written and checked before it lands

## Problem

The project has no overview of any of its systems. An overview — a system or subsystem explained for a reader who must act on it — is the document type the user has asked for most often and received least: `docs/wiki/` on main holds only `queue/`; one page ever landed there and survives only in git history; a wiki page requested on 2026-08-24 produced no file; GHI [Write the sanity-checker-overview wiki page: the system map for future editors (user-wanted 2026-08-22)](https://github.com/nedschorus/nedschorus/issues/130) commissions one overview (of the sanity-checker) and it is unwritten. A survey of all 88 tracked markdown files on 2026-08-25 found six that function as overviews (`docs/agents/agent-seat-model.md`, `docs/cross-project/fleet-git-worktree-working-model.md`, `docs/cross-project/fleet-machine-paths-and-checkouts.md`, the top-level `README.md`, `nc-queue/README.md`, and a code-review write-up under `docs/drafts/`); whether any is good is unjudged.

The user's rulings on 2026-08-25, in his words: "My intent with readme is that it is an explainer of a system or subsystem, so it will need its own careful process." "It may need parts of sanity check." "It helps to do several passes on several divergent examples before we attempt to codify them." On the name: overviews, not explainers or readmes — GHI [Write the sanity-checker-overview wiki page: the system map for future editors (user-wanted 2026-08-22)](https://github.com/nedschorus/nedschorus/issues/130) had already ruled "readme" generic where "overview" says what it is. On the skill: "make a GHI to turn our overview notes into an overview-write skill." On order: "walk and discuss and build bottom up, from the most fundamental to the highest level. Overview is literally that."

## What is known about the type

1. Its reader is someone who has to understand a system before acting on it — an agent starting a seat, a person deciding whether to change something. It is consulted, not followed step by step; that separates it from a skill or a seat brief.
2. Its characteristic defect is being wrong about the system, not being unclear. A measurement on 2026-08-25 compared the two review instruments on one document: the clarity review (cold-read) had already raised something about every passage the mechanization audit raised, but everything the audit added was a claim about the world outside the document — whether the corpus obeys a rule the sentence states, whether any program does what a sentence says, whether a term the document uses exists anywhere else. An overview's review therefore needs that half of the sanity-check: an agent that opens the code and scripts the overview describes and checks each claim against them. The cold read alone cannot see an overview that is confidently wrong.
3. Its currency is a standing duty, not a one-time write. GHI [Dynamic agent-team model: sparring pairs, on-tap domain experts, spy-triaged oversight (design capture; research pending)](https://github.com/nedschorus/nedschorus/issues/26)'s design notes name it: one system, one accountable steward keeping that system's overview current. The skill writes the first version; something else keeps it true.

   The steward was replaced on 2026-09-22. At item 9 of the walk what-a-design-becomes-when-its-code-lands-2026-09-22 the user ruled, as its minutes record it, "no owner, because it is idempotent", having asked "how do you know who 'owns' the code or design. And why does that matter - why not just refresh" (minutes `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/what-a-design-becomes-when-its-code-lands-2026-09-22-minutes.md`, lines 46 and 246). So any seat keeps an overview true, through the refresh defined by GHI [refresh-design: when a system's code lands, bring its design, build-slice plan and overview into line — removing, never revising](https://github.com/nedschorus/nedschorus/issues/670); since PR [A reincarnated seat is told when a system's overview has fallen behind its code](https://github.com/nedschorus/nedschorus/pull/764) merged on 2026-09-29, the handoff-supervisor tells a seat's new session when an overview's refresh is due. This issue was kept open on 2026-09-29, by the user's "y" at item 13 of the walk open-items-this-seat-holds-2026-09-24, because that refresh relies on it for how an overview is written and checked.

4. Nothing discovers it by its frontmatter. Neither Claude Code nor Codex indexes the frontmatter of ordinary markdown (measured 2026-08-25 from the documentation and the Codex source); an overview is found by its name and place. The name should say what it overviews and end in `-overview`, the naming rule GHI [Write the sanity-checker-overview wiki page: the system map for future editors (user-wanted 2026-08-22)](https://github.com/nedschorus/nedschorus/issues/130) applied.
5. The rules for how its prose is written are draft-md's (direct and clear, for a naive reader, terms defined before use, one paragraph per line) — this skill does not restate them; it says what an overview must contain and how its claims are checked.

## What the skill must settle

- What an overview contains: the parts of the system and how they fit; what each part reads and writes; where the system's rules live; what a reader must do before touching it; what is not yet built. Which of these are required and which depend on the system.
- The check: how each claim about code or scripts is verified against them before the overview lands — the sanity-check's mechanization half, or a cold-read cell licensed to run commands, or a new pass; keyed so that only overviews pay for it.
- The examples-first method: which systems get the first overviews, written by different agents given nothing but "explain this to someone who has to act on it," so the skill is codified from what the user prefers rather than from theory. Candidates named 2026-08-25: the cold read, the sanity-check (which makes GHI [Write the sanity-checker-overview wiki page: the system map for future editors (user-wanted 2026-08-22)](https://github.com/nedschorus/nedschorus/issues/130)'s page the first deliverable), the PR-to-main lane.
- Where overviews live (`docs/wiki/` is the commissioned home) and how the steward duty attaches.

## Next action

Write the skill's design as a pair document, in the bottom-up order the user set: first the overview type itself, then the check, then the skill text. The design gets a cold read; the skill gets the examples-first test before it is installed. This issue is the home for the rulings as they land.

## Relations

- GHI [Write the sanity-checker-overview wiki page: the system map for future editors (user-wanted 2026-08-22)](https://github.com/nedschorus/nedschorus/issues/130) — the first overview commissioned; becomes this skill's first output.
- GHI [Dynamic agent-team model: sparring pairs, on-tap domain experts, spy-triaged oversight (design capture; research pending)](https://github.com/nedschorus/nedschorus/issues/26) — the steward duty that keeps an overview current.
- GHI [Build draft-md: the drafting-stage skill run before md-review (user-ruled 2026-08-22)](https://github.com/nedschorus/nedschorus/issues/142) — draft-md, whose prose rules this skill cites rather than restates.
- GHI [cold-read: one merged report per read — findings grouped by passage, with each cell's wording and the count of cells that raised it](https://github.com/nedschorus/nedschorus/issues/166) — the merged cold-read report; the check this skill needs may be a cold-read cell rather than a sanity-check audit.
