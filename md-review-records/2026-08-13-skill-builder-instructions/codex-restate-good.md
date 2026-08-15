<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=restate tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/skill-builder-instructions.md -->

# `skill-builder` — seat instructions

1. The work assigned to this seat—that is, this agent role or workstream—is the queue of proposed skills that might be built.
2. The queue contains seven proposed skills. Each skill is expected to be built through substantially the same kind of process, using one shared authoring checklist and one shared process called a “walk.” That repetition is the reason all seven are assigned to the same seat: experience and reusable knowledge should make the seventh skill require much less effort than the first. “Cheaper” appears to mean cheaper in time or effort, although the sentence does not explicitly exclude monetary cost.
3. Read the linked seat-model document to learn what “seats” are and how this project expects them to operate.

## The queue

1. Every proposed skill has a GitHub issue that records its current state. Several, but not necessarily all, also have a separate queue document containing more detailed information.
2. Issue #18 concerns the proposed `write-test-plan` skill. That skill would produce plans ranked by the consequences of possible failures and would use outcomes that can actually be observed to determine whether something worked. It is marked as the most likely skill to build first. The named riders file contains additional provisions or requirements, called “riders,” although the exact force of that term is not defined here.
3. Issue #20 concerns `implement-with-evidence`. Its central workflow is based on preserving evidence from a failing state and then a passing state—the likely meaning of “red/green”—and it must not require an agent to delete its work and begin again. “Kernel” means the essential core of the workflow.
4. Issue #21 concerns `diagnose-failure`. It calls for debugging that seeks the cause of a failure while remaining within defined limits, and for stopping and escalating after three fix attempts. The named test-procedure document contains more detail.
5. Issue #22 concerns `review-change`. The review must target one precisely identified revision, focus on defects before other observations, and subject each proposed finding to a five-part acceptance check. This document does not explain the five parts of that “finding gate.”
6. Issue #23 concerns `eval-agent-change`. It would compare a baseline agent behavior with a candidate behavior as an A/B evaluation, include cases designed to trigger the behavior under evaluation, and report unprocessed numerical counts rather than only summaries or derived metrics.
7. Issue #19 concerns `attack-artifact`. It calls for an adversarial review performed in isolation from something not specified here. The issue has been framed as a question comparing that approach with “d-review.” This document does not define `d-review` or state precisely what the comparison asks.
8. Issue #17 concerns `design-change`. It would produce a design without modifying the repository, base that design on gathered evidence, provide one recommended course of action, and include candid ways to stop or decline when proceeding is unsupported. The exact operational meaning of “honest exits” is not defined here.
9. Issue #24 is an additional item: the procedure for draining the queue. It defines a review process intended to empty three collections of pending work—the wiki queue, the pair queue, and the set of issues carrying a draft label. This document does not define those three queues further.
10. Because issue #24 determines how the other assigned items are processed, it should be read near the beginning of the work.

## How skills are built here

1. Locate the project’s skill-authoring checklist somewhere under `docs/` and follow it. That checklist is an established project-specific standard that existed before the current agent or seat began this work.
2. The existing `walk-me-through`, `md-review`, `handoff`, and `ghi-write` skills are completed examples of the expected form. Closely reading any two of them is presented as the lowest-effort way to learn the project’s established writing and structural conventions, called its “house style.”
3. The following three rules are highlighted because earlier skill builds encountered problems when they did not follow them.
4. A skill belongs to a protected category called “instruction-class,” meaning it is treated as an instruction artifact rather than as ordinary repository content. The complete definition of that category is not given here.
5. A skill may be incorporated into the project—“land”—only through the user’s “walk” process. A hook named `instruction-file-guard` mechanically enforces this restriction. Approval is represented by a `.walk-approved` marker that contains a quotation of the user’s approval, and that marker authorizes one particular write and is consumed when that write occurs. The document does not describe the entire walk process or the precise mechanics of consuming the marker.
6. Skill files are supposed to give operational instructions rather than serve as discursive or explanatory essays.
7. Side comments that merely explain the reasons behind instructions are removed; the retained text should directly tell an agent what actions to take.
8. On August 6, 2026, four rationale-only asides were removed from `walk-me-through` specifically because skills are meant to contain instructions rather than essay-like explanation.
9. The required standard is “zero-context readability”: an agent must be able to understand the instructions without relying on unstated background information.
10. On August 11, 2026, the user decided that agents must be able to understand their instructions “cold,” meaning without prior context or preparatory explanation. Consequently, once a skill draft is considered settled or stable, it must undergo the process named `md-review` before it is incorporated into the project. The details of `md-review` are not provided here.

## Related work you did not do

1. The seat named `sanity-checker`, rather than this seat, is responsible for review methodology and may add a reviewer to the collection or matrix called the `md-review` grid. Pull requests #51 and #53 fall within that seat’s assigned responsibility.
2. If building a skill would also alter the way reviews are presented or delivered, transfer that review-delivery portion to the `sanity-checker` seat instead of making the decision within the `skill-builder` seat.

## First action

1. First read issue #24, which defines the queue-draining procedure, and issue #18, which is considered the probable first skill build, together with issue #18’s riders file. After reading them, tell the user which skill you recommend building first and explain the reason for that recommendation.
2. Do not begin building any skill until the user makes a ruling. The user has authority to choose the order, and every skill must go through the process called a “walk” before it may be incorporated into the project. Here, “walked” most likely means reviewed step by step through the user-controlled walk process, but this document does not fully define that process.
