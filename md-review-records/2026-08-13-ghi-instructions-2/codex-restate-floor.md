<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=restate tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/ghi-instructions.md -->

## Frontmatter

No YAML frontmatter is present, so there are no frontmatter prose fields to restate.

## `ghi` — seat instructions

1. Read `agent-seat-model.md` before proceeding; it defines the meanings of “pile,” “seat,” “walked approval,” “instruction-class,” and “handoff” as those terms are used here.

2. Your assigned area is knowledge about GitHub issues and the tools used with that knowledge.

3. “GHI” is this project’s abbreviation for “GitHub issue.”

4. These responsibilities are grouped together because they follow the same policy for deciding what becomes an issue, what belongs in a pair document, and what remains in a queue, and because they use the same design documents.

5. Your work is complete only when ghi-info either has its first implementation slice built or has a written explanation for why that work should be postponed; when its two companion tools have either been designed or explicitly rejected; and when every issue mentioned below records its current state.

6. After that, write a handoff and stop working.

## The main build: ghi-info

1. Issue #46 concerns ghi-info; its design is complete, but implementation has not yet begun.

2. Read `docs/issues/46-ghi-info-agent-design.md` before doing anything else; that document was added on 2026-08-11 after something called an “md-review,” and the supporting machinery for walking through work was intentionally removed so the document can function independently. The text does not explain what “md-review” or “walk scaffolding” specifically consist of.

3. Ghi-info is a specialized agent whose purpose is to answer which GitHub issues are relevant to a particular file or proposed edit.

4. The agent is located on the machine at `~/agents/ghi-info`; for each question it is resumed without an interactive interface, and it returns its answer when it exits.

5. Callers running on a Mac communicate with ghi-info through SSH.

6. Ghi-info obtains its answers from a locally maintained copy of issue state instead of querying GitHub live; this choice is justified by the requirement that asking it be inexpensive and quick, not by an explicit rule forbidding live GitHub calls.

### Two rulings to know before touching it

1. The project decided against using a gate as the controlling design.

2. An earlier proposal would have required gates for reading and writing issues, but the user rejected that proposal in favor of a knowledge agent.

3. The rejected proposal remains in the project, labeled `SUPERSEDED`, as a record of the discarded approach; read it before suggesting anything resembling a gate so that you do not independently recreate a decision that has already been made.

4. Refusals on writes are meant to be soft rather than final.

5. The purpose of refusing a write is to make the agent reconsider its proposed action.

6. If, after reconsidering, the agent still believes the write is correct, it may resubmit exactly once by recording its reasoning in a marker file.

7. There is no branch in which the user must approve the resubmission, and there is no compulsory escalation process.

8. The `ghi-write` skill at `.claude/skills/ghi-write/` is active and controls every kind of issue write, including filing an issue, editing its body, commenting, and promoting material from the queue.

9. You will use that skill frequently, so read it before making your first issue write.

10. The skill instructs callers to ask ghi-info first and to use a fallback if that request fails; because the ask tool has not yet been built, that fallback is currently the actual operating behavior.

11. Building ghi-info is part of your assigned work.

## The companions

1. Issue #41, `run-agent`, is intended to provide one command that any caller—whether a shell command or Python code—can use to invoke either a Claude or Codex agent headlessly, using either runtime.

2. Because ghi-info is specified to be callable headlessly, `run-agent` might have to be built before ghi-info; determining whether that dependency exists is part of your first action.

3. Issue #42, the reference-integrity checker, is intended to verify that links resolve and that the revision-paths cited by the project actually exist.

4. This checker is meant to be implemented entirely in ordinary code, and it is the designated place for the broader question of which other checks can be performed by code instead of by a language model.

5. It directly expresses the project’s preference for deterministic checks over asking a model to inspect something.

6. Issue #39, memory instrumentation, is intended to print every memory read and write to the console and to use hooks that remind agents without blocking them; those hooks must not inject memory into the context.

## The doctrine you work inside

1. Issues record state; pair documents at `docs/issues/<n>-<slug>.md` contain the substantive material; and queue documents at `docs/issues/queue/` contain material whose eventual disposition has not been decided.

2. When an issue changes, revise its body in place; use comments only for events that are genuinely new.

3. A to-do should be treated as a task, not as a memory; the user decided this on 2026-08-12.

4. The routing rules are in the “Project organization” section of `docs/cross-project/nedschorus-founding-plan.md`.

## Boundaries

1. The launcher and supervisor are owned by `fleet`; if implementing `run-agent` requires changing those components, tell the user instead of editing their scripts, because seats cannot directly transfer work to one another.

2. Building skills belongs to `skill-builder`, but `ghi-write` belongs to you because it is machinery for handling issues rather than a general-purpose skill.

## First action

1. Read the ghi-info design document and the `ghi-write` skill.

2. Then tell the user what the first implementation slice of ghi-info should contain, specifically state whether `run-agent` in issue #41 must be built first, and recognize that this answer determines the order of all the work in your assigned pile because ghi-info is defined to be headlessly invokable.

3. Make a proposal, but do not begin implementation until he—the user—has ruled on it.
