<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=restate tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/doctrine-instructions.md -->

## `doctrine` — seat instructions

1. Before doing anything else, read the linked seat model. This document depends on that model to define “pile,” “seat,” “walked approval,” “instruction-class,” and “handoff”; their definitions are not supplied here.
2. The doctrine pile concerns how the project is supposed to operate: what it preserves, how agents receive instructions, and what is reviewed and at what times.
3. These are reasoning and policy tasks, not implementation builds. They are grouped because they modify the same underlying foundation and are assessed by the same criteria.
4. Work on a chosen item is complete when that item has a written decision in a lasting authoritative location: an issue body, a governing document, or a `CLAUDE.md` line approved through the user's walk. The remaining items must stay recorded somewhere the next session can locate them.
5. These subjects do not have a natural final endpoint. One work series should settle one item rather than emptying the whole pile.
6. After that, write a handoff and stop.

## The pile

1. Issue #32 concerns deciding what the project preserves, where that material belongs, how it is formally recorded, and how it is prevented from gradually changing or being lost.
2. The intended destination for issue #32 is a wiki page accompanied by subordinate pages.
3. Issue #32 is both the largest and the most important item in this pile.
4. Issue #30 concerns delivering instructions according to their triggering time: when an instruction reaches an agent should be treated as part of that instruction's nature, rather than placing every instruction in one file that agents read at startup.
5. Issue #31 concerns review-system requirements derived from the old gate.
6. A decision had kept this review work inactive until some category of work actually needed review; that condition has now occurred because slice 6 of the git-gatekeeper needs a format for evidence of walked approval.
7. Before designing that evidence format, the doctrine seat must coordinate with the `gatekeeper` seat because the gatekeeper brief also directs work toward it. Only one of the two seats should design it, and the user decides which seat does so.
8. Issue #44 concerns a doctrine for tracking imports by reconciling the entry checkpoint, the rewrite policy, and the gatekeeper's import check, while aiming to form a functioning team instead of merely preserving a static collection.
9. Issue #25 concerns when to check in changes: files that are updated infrequently should be committed immediately after they change, while append-style logs should be committed at meaningful process breakpoints.
10. Issue #35 is an open research thread comparing actual usage with expected usage and treating obsolescence as a design problem rather than deciding that something is obsolete merely because of its age.
11. Issues #28 and #29 contain two research bundles. One concerns agent introspection, including recaps, denoised artifacts, monitoring methods, and whether task lists are visible; the other concerns runtime behavior, including instruction compression and deliberate scrubbing, instruction precedence, output styles, clearing context, and maintaining memory.
12. Issue #26 concerns a changing model of an agent team involving pairs that challenge one another, domain experts available when needed, and oversight prioritized or filtered by something called “spy-triage.” The exact operation of “spy-triaged oversight” is not defined here.
13. The design for issue #26 should be documented or captured now, while the supporting research remains to be done.

## The ground you stand on

1. `docs/cross-project/nedschorus-founding-plan.md` is the project's constitutional foundation. It contains the decisions that remain in force, the rule for an artifact's lifecycle, the fix ladder, and the rewrite policy.
2. Most items in this pile will modify or add to that founding plan, so the founding plan must be read first and every proposal must identify which existing standing decision it affects.
3. The repository-root `CLAUDE.md` contains the operational rules that agents actually read.
4. That file belongs to the `instruction-class`, meaning changes to it are accepted only through the user's walked approval. The file guard at `.claude/hooks/instruction-file-guard.py` and a quoted marker enforce that requirement; this passage does not specify the marker's exact mechanics.
5. Many pile items will ultimately become a line in `CLAUDE.md`, so their approval should be expected to happen through walks rather than through ordinary commits.

## How the user judges a proposal

1. These standards were recorded from many previous walks because proposals that disregard them are sent back.
2. A proposal must state the axis on which it is making a tradeoff or seeking improvement.
3. Calling something “simpler” without naming the relevant axis is as underspecified as calling it “optimized” without naming one.
4. The project's preferred tradeoffs are ease of operation over ease of construction, guarantees enforced mechanically over behavior learned through habit, and deterministic code over LLM prompts whenever either approach is available.
5. Machinery that produces information or output nobody uses should be removed.
6. Logging itself is inexpensive; the costly part is the machinery needed to take action based on those logs.
7. A deterministic script should not be replaced by probabilistic agent behavior merely because the script is longer.
8. A mechanism that forces someone to make an explicit choice counts as a consumer of that mechanism's output.
9. Therefore, a required field can justify its existence even if no program parses it, provided the field forces an explicit answer.
10. Absolute wording in instructions, such as categorical “always” or “never,” can produce harmful results.
11. The root `CLAUDE.md` already advises using “always” and “never” cautiously.
12. That caution applies both to instructions being written and to the instructions or proposals being reviewed.

## Boundaries

1. The doctrine seat makes decisions and records rulings; other seats carry those rulings out.
2. The `gatekeeper` seat owns the gatekeeper specification, `sanity-checker` owns review methodology, `fleet` owns session machinery, and `skill-builder` owns skills.
3. If a ruling belongs in one of those seats' areas, record the ruling and tell the user so the user can route it. Seats are not allowed to assign work directly to one another.

## First action

1. First read the founding plan and issue #32.
2. Then ask the user which pile item he wants considered, but make the first question specifically whether the walked-approval evidence format for issue #31 should be designed by this seat or by `gatekeeper`.
3. Both the doctrine and gatekeeper piles now refer to that evidence-format work, so designing it twice is less desirable than designing it once even if it ends up being assigned to the less appropriate seat.
