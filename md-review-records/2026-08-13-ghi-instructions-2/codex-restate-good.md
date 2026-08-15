<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=restate tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/ghi-instructions.md -->

# `ghi` — seat instructions

1. Before using this brief, read the linked agent-seat-model document because it supplies the intended definitions of “pile,” “seat,” “walked approval,” “instruction-class,” and “handoff.”

2. The body of related work assigned to the `ghi` seat is knowledge about GitHub issues and the tools that provide, manage, or use that knowledge.

3. In this project, “GHI” is an abbreviation for “GitHub issue.”

4. These tasks are grouped under one seat because they use the same rules for deciding whether material belongs in a GitHub issue, in the detailed document paired with an issue, or in a queue of undecided material, and because they rely on the same collection of design documents.

5. The seat reaches its completion condition when ghi-info’s first independently deliverable build increment has either been implemented or explicitly deferred with a written explanation, when its two companion tools have each either received a design or been explicitly rejected, and when every issue mentioned later in the brief reflects its current status. I take “the two companion tools” to mean run-agent and the reference-integrity checker, but the later “companions” section also lists memory instrumentation, so the wording does not make that count completely unambiguous.

6. After satisfying that completion condition, the agent must write a handoff for the next session and end the current session.

## The main build: ghi-info

1. GitHub issue nedschorus#46 represents the ghi-info work; its design has already been completed, but implementation is still waiting to begin.

2. Before doing other work on ghi-info, read `docs/issues/46-ghi-info-agent-design.md`; that document was incorporated into the project on 2026-08-11 after an `md-review`, and material belonging specifically to the item-by-item approval walk was intentionally removed so the design can be understood as a self-contained document.

3. Ghi-info is a specialized agent whose function is to identify which GitHub issues are relevant to, constrain, inform, or otherwise affect a specified file or proposed edit.

4. Its persistent seat or working installation is located on the Ubuntu machine under `~/agents/ghi-info`; for each query it is started or continued without an interactive user interface, and its answer is emitted when that invocation terminates.

5. Programs or agents running on the user’s Mac communicate with ghi-info by connecting to the Ubuntu machine through SSH.

6. Ghi-info must answer from a locally maintained copy of GitHub issue state instead of querying GitHub live for every question; this requirement follows from the goal that queries be inexpensive and quick, even though the document apparently does not express it as an explicit prohibition against live calls.

7. The first of two decisions that must be understood before changing ghi-info is that the project has already decided not to make it an enforcement gate.

8. A previous plan would have placed a mechanism in front of GitHub issue reads and writes that could control or condition those operations, but the user rejected that approach and chose an informational agent instead.

9. The rejected plan remains available and is labelled `SUPERSEDED` so it preserves the history of the rejected approach; it must be read before suggesting anything resembling an issue-access gate, to avoid independently proposing an option the project has already considered and rejected.

10. The second prior decision is that a write refusal from the issue machinery is advisory or interruptive rather than an absolute block.

11. Such a refusal is intended to make the acting agent stop and reconsider the proposed write.

12. If the agent reconsiders and remains persuaded that the write is correct, it may make exactly one renewed submission, provided it records its reasoning in a designated marker file.

13. That renewed submission does not require a separate path for obtaining user approval, and the system does not compel the agent to escalate the matter to anyone else.

14. The `ghi-write` skill at `.claude/skills/ghi-write/` is already operational and controls every operation that writes to an issue, including creating an issue, changing its body, posting a comment, and moving queued material into an issue.

15. Because this seat will perform issue writes frequently, its occupant must read that skill before performing the first such write.

16. The skill currently instructs callers to query ghi-info first and defines fallback behavior for occasions when that query fails; in present practice the fallback is necessarily used because the tool for making the ghi-info query has not yet been built.

17. Building “it” is assigned to this seat; I take “it” to mean the missing ghi-info query capability, including the agent/tool necessary to provide it.

## The companions

1. Issue #41 concerns run-agent: a single command or interface intended to invoke either a Claude agent or a Codex agent non-interactively, from either shell code or Python code, and for either supported agent runtime. “Either runtime” appears to refer to Claude and Codex, although the sentence’s compressed grammar leaves open whether it denotes some other runtime distinction.

2. Because ghi-info is required to support non-interactive invocation, run-agent might be a prerequisite for it; determining whether that dependency exists, and therefore which one must be built first, is part of the seat’s initial assignment.

3. Issue #42 concerns a reference-integrity checker that verifies both that links reach valid targets and that revision-paths cited by documents exist. I take “revision-path” to mean the project’s established form of a reference combining or relating a revision and a filesystem path; this brief does not define its exact syntax.

4. This checker is to be implemented entirely as ordinary deterministic code rather than as an LLM judgment, and its issue or design document is also the designated place to consider which other validations can be performed by code instead of by a language model.

5. It directly advances a central project preference: when a reliable deterministic check is possible, the project prefers that check over asking a model to inspect and judge the same thing.

6. Issue #39 concerns memory instrumentation that prints every memory read and write to the console, uses hooks as reminders rather than as blocking enforcement, and does not insert memory content into the agent’s context. This brief does not further identify the memory system or the exact hooks involved.

## The doctrine you work inside

1. GitHub issues hold the current state of work; documents named `docs/issues/<n>-<slug>.md` hold the detailed substance associated with an issue; and documents under `docs/issues/queue/` hold material for which the project has not yet decided the final destination or outcome.

2. When existing issue information changes, the canonical issue body should be edited in place; comments should be added only for events that are genuinely new, rather than being used as a running substitute for maintaining the body.

3. Under the user’s ruling of 2026-08-12, a to-do belongs in the project’s task-handling system and must not be treated merely as information to remember.

4. The authoritative rules for routing material among those destinations are in the “Project organization” section of `docs/cross-project/nedschorus-founding-plan.md`.

## Boundaries

1. The launcher and supervisor are owned by the `fleet` seat; if implementing run-agent would require changing those components, the `ghi` seat must inform the user instead of editing the relevant scripts, because the seat model does not permit one seat to transfer work directly to another seat and therefore requires the user to mediate.

2. Building skills normally belongs to the `skill-builder` seat, but `ghi-write` is assigned to the `ghi` seat as an exception because it is specifically part of the machinery for handling GitHub issues rather than a generally applicable skill.

## First action

1. First read both the ghi-info design document and the `ghi-write` skill.

2. After reading them, present the user with a proposal identifying ghi-info’s first build increment and explicitly deciding whether run-agent, issue #41, must be implemented before that increment; because ghi-info must support headless invocation, this dependency decision determines the order in which the seat’s overall body of work should proceed.

3. At this stage, offer only the proposal and do not begin implementation until the user has made the ruling.
