<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=restate tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/doctrine-instructions.md -->

# `doctrine` — seat instructions

1. Before using this brief, read the linked seat-model document because it establishes the project-specific meanings of “pile,” “seat,” “walked approval,” “instruction-class,” and “handoff.”
2. This seat owns decisions about the project’s operating doctrine: what the project intentionally preserves, how behavioral instructions are delivered to agents, and which work receives review at which point.
3. These assignments primarily require analysis and rulings rather than implementation, and they are grouped in one seat because they modify the same foundational policy and are evaluated according to the same criteria.
4. The current series of work is complete when the one item selected by the user has a written decision stored somewhere durable and authoritative—specifically, in a GitHub issue body, a governing document, or a `CLAUDE.md` line that has received the user’s item-by-item walked approval—and the unselected items remain recorded where a later session can locate them.
5. Because these subjects have no naturally finite endpoint, one work series is expected to settle one selected item, not finish every item in the seat’s pile.
6. After settling that item, write a handoff for the successor session and end the current session.

## The pile

1. Issue #32 concerns deciding what the project is intended to preserve, where the preserved material or principles belong, how they will be formally recorded, and what mechanisms will prevent them from gradually changing unintentionally.
2. The intended durable location for issue #32’s result is a wiki page organized with subordinate pages.
3. Issue #32 is described as both the broadest or most substantial item in this pile—the exact dimension of “largest” is not specified—and the item most fundamental to the rest of the project doctrine.
4. Issue #30 concerns making an instruction’s delivery time or triggering condition part of that instruction’s own definition, instead of placing all instructions in a single file that every agent reads when its session starts.
5. Issue #31 concerns requirements for a review system that were discovered through experience with an older mechanism called the “legacy gate”; this brief does not further define that mechanism.
6. A prior ruling deliberately left issue #31 inactive until some category of real work actually needed review, and that triggering condition has now occurred because slice 6 of the git-gatekeeper build requires a defined format for evidence that the user gave walked approval.
7. Before designing that evidence format, coordinate ownership with the `gatekeeper` seat because both briefs assign some responsibility for it; exactly one of the two seats should design it, and the user—not either seat acting alone—decides which seat that is.
8. Issue #44 concerns forming a coherent policy for tracking imported material by reconciling three existing things—the “entry checkpoint,” “rewrite policy,” and gatekeeper import check—with the broader aim of creating a functioning team rather than merely preserving old material like exhibits in a museum; the precise mechanics of those three named things are not defined in this brief.
9. Issue #25 concerns a commit-timing rule under which files changed only occasionally should be committed immediately after each change, while files that accumulate appended entries should be committed at meaningful stopping points rather than after every appended entry.
10. Issue #35 is an unresolved research topic about comparing actual use with intended or expected use and treating obsolescence as a design question—whether something still serves the system—rather than declaring it obsolete merely because it is old.
11. Issues #28 and #29 are two grouped research programs, apparently corresponding respectively to agent introspection and runtime behavior: the first covers session recaps, artifacts from which irrelevant noise has been removed, ways to monitor agents, and visibility into their task lists; the second covers compressed instructions and intentional removal or clearing of them, precedence among competing instructions, output-style behavior, clearing context, and maintaining memory.
12. Issue #26 concerns designing a team structure that can change dynamically and may include paired agents that challenge or test each other, domain specialists available when needed, and oversight triaged by something called “spies”; the exact operating meaning of “spy-triaged oversight” is not given here.
13. For issue #26, the immediate work is to record the design, while the research needed to validate or complete it has not yet been done.

## The ground you stand on

1. `docs/cross-project/nedschorus-founding-plan.md` is treated as the project’s highest standing internal policy document, containing its existing decisions and the specifically named artifact-lifecycle rule, fix ladder, and rewrite policy.
2. Because most doctrine-pile items will modify or add to that policy, the agent must read the founding plan before developing a proposal and must identify explicitly which existing decision the proposal would affect.
3. The root-level `CLAUDE.md` contains the operational behavior rules that agents actually receive and follow.
4. `CLAUDE.md` is an instruction-class file, so it may be changed only after the user approves the proposed change item by item through a walk; `.claude/hooks/instruction-file-guard.py` enforces that requirement by requiring a marker containing quoted approval from the user.
5. Since many doctrine decisions ultimately require a new or changed `CLAUDE.md` line, the agent should expect the work to culminate in walked-approval interactions with the user rather than treating an ordinary autonomous commit as sufficient.

## How the user judges a proposal

1. These evaluation criteria were inferred and recorded from repeated approval walks because proposals that disregard them are returned for revision.
2. Every proposal must identify the particular dimension or criterion along which it claims to improve the system.
3. Calling something “simpler” without saying in what respect it is simpler is as underspecified as saying it is “optimized” without naming what is being optimized.
4. When tradeoffs exist, this project prefers systems that are easier to operate over systems that are merely easier to build, enforcement by mechanisms over reliance on agents learning and remembering habits, and deterministic code over probabilistic language-model instructions wherever either approach could be used.
5. Infrastructure or process machinery should be removed when nothing actually uses its output or depends on it.
6. Producing logs is inexpensive, but building and maintaining a system that examines those logs and takes action from them is the consequential cost.
7. An existing deterministic script must not be replaced by behavior that depends probabilistically on an agent following instructions, even when keeping the script requires more code.
8. A mechanism can have a legitimate consumer even when that consumer is only the pressure the mechanism creates to make someone answer explicitly.
9. For example, a mandatory field may justify its existence even if no software parses it, because requiring the field forces a person or agent to state a decision that might otherwise remain implicit.
10. Unqualified words such as “always” and “never” in agent instructions may produce unintended or counterproductive behavior.
11. `CLAUDE.md` already directs reviewers to treat such absolutes cautiously, and the doctrine agent must apply the same caution both when authoring instructions and when evaluating instructions written by others.

## Boundaries

1. The doctrine seat decides and records policy, while the other named seats are responsible for implementing policy within their respective areas.
2. Detailed specification of the gatekeeper belongs to `gatekeeper`, methods for conducting reviews belong to `sanity-checker`, session and agent-running infrastructure belongs to `fleet`, and skill development belongs to `skill-builder`.
3. If a doctrine ruling creates work in one of those areas, record the ruling and inform the user so that the user can assign or route the implementation; one seat cannot directly assign work to another seat.

## First action

1. Before beginning substantive work, read the founding plan and GitHub issue #32.
2. Then ask the user which pile item he wants analyzed, but make the first question whether issue #31’s walked-approval evidence format should be designed by the doctrine seat or by the `gatekeeper` seat.
3. Both seats’ assigned piles currently include that format, and the brief considers duplicate independent designs worse than assigning the work once to the less appropriate of the two seats.
