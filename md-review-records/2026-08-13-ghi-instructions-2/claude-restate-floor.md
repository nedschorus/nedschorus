<!-- provenance: runtime=claude model=claude-sonnet-5 effort=high cell=restate tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/ghi-instructions.md -->

**Frontmatter:** None present — the file begins directly with the H1 heading; no YAML block precedes it.

## Title / preamble (before the first `##` heading)

1. "Read [the seat model](agent-seat-model.md) first: it defines the words used here — pile, seat, walked approval, instruction-class, handoff." — An instruction to read the file agent-seat-model.md before anything else in this document; that file supplies the definitions for the specific terms used here: "pile," "seat," "walked approval," "instruction-class," and "handoff."

2. "Your pile is **GitHub-issue knowledge and the tooling around it**." — The area of responsibility ("pile") assigned to the reader is knowledge about GitHub issues plus the tools/software built to work with them.

3. "GHI" is this project's shorthand for a GitHub issue." — Within this project, "GHI" is used as an abbreviation meaning "GitHub issue."

4. "The pieces belong together because they share one doctrine — how the project decides what becomes an issue, what goes in a pair document, and what waits in a queue — and one set of design documents." — The various components making up this pile are grouped under one seat because they are all governed by a single shared body of policy covering three decisions (what qualifies as an issue, what content belongs in a paired companion document, and what remains undecided in a queue), and because they share one common set of design documents.

5. "**Your work is done when** ghi-info has a built first slice or a written reason it should wait, its two companion tools are designed or ruled out, and each issue below carries the current state." — Completion is defined by three conditions all holding at once: (1) ghi-info has either had an initial minimal working version built, or there is a written explanation for why building it should be deferred; (2) its two related tools have each either been designed or been decided against; and (3) every issue listed later in this document reflects its up-to-date status.

6. "Then write a handoff and stop." — Once those conditions are satisfied, the reader should produce a handoff document and then end the work session.

## The main build: ghi-info

1. "[nedschorus#46](...), designed and awaiting build." — This names GitHub issue #46 in the nedschorus repository and states its status: it has already been designed and is currently waiting to be implemented.

2. "**Read `docs/issues/46-ghi-info-agent-design.md` first** — it landed 2026-08-11 after an md-review, with the walk scaffolding deliberately stripped so it stands alone." — An instruction to read that specific design file before anything else related to this build; the file was added/merged on 2026-08-11 after going through the md-review process; it had certain structural content referred to as "walk scaffolding" intentionally removed, with the effect that the document can be understood fully on its own without needing that scaffolding.

3. "What it is: a dedicated agent that answers "which issues bear on this file, or this edit?"" — This describes ghi-info as an agent whose specific purpose is to answer which GitHub issues are relevant to a given file or a given edit/change.

4. "It lives on the box at `~/agents/ghi-info`, is resumed headlessly for each question, and answers on exit." — ghi-info is installed on the Ubuntu machine at the path ~/agents/ghi-info; for each question it is asked, an existing agent session is restarted/continued without an interactive interface ("resumed headlessly"); the agent delivers its answer at the point its process terminates ("on exit").

5. "Mac-side callers reach it over SSH." — Processes running on the Mac that want to query ghi-info do so by connecting to the box via SSH.

6. "Its answers come from a local mirror of issue state rather than live GitHub calls — a rule stated by its purpose (it should be cheap and fast to ask) rather than by prohibition." — ghi-info answers using a locally stored copy of issue state rather than querying GitHub's API in real time; this behavior follows from ghi-info's goal of being inexpensive and quick to query, rather than from an explicit rule forbidding live calls.

7. "Two rulings to know before touching it:" — An introductory line signaling that two prior decisions are about to be listed, which the reader should know before beginning work on ghi-info.

8. "**The direction was settled against a gate.**" — A decision has already been finalized against pursuing an approach that involves a "gate" (an approval/access-control checkpoint).

9. "An earlier plan proposed gating issue reads and writes; the user rejected it in favour of a knowledge agent." — A previous plan had proposed placing a gate/checkpoint around both reading and writing issues; the user rejected that plan and instead chose to build a knowledge-providing agent (what became ghi-info).

10. "That plan survives marked SUPERSEDED as the record of the rejected direction — read it before proposing anything gate-shaped, so you do not re-derive a decision already made." — The document for that earlier, rejected plan still exists but is labeled "SUPERSEDED," kept as a historical record of the rejected approach; the reader should read it before suggesting anything resembling a gate, so as not to waste effort independently arriving at a conclusion already settled.

11. "**Write refusals are soft.**" — When a write action is refused, that refusal is not an absolute, hard block — it is characterized as "soft," implying it can potentially be overridden.

12. "A refusal's job is to make an agent look twice." — The purpose of issuing a refusal is to prompt the receiving agent to reconsider its action, not necessarily to permanently prevent it.

13. "An agent still convinced after reconsidering passes exactly one resubmit by writing its reasoning into a marker file." — If, after reconsidering, the agent still believes it should proceed, it is allowed to attempt the write one more time, and does so by recording its justification into a designated "marker file."

14. "There is no user-approval branch and no forced escalation." — This process contains no path where a human user is asked to approve the action, and no mechanism forcing escalation to a higher authority.

15. "The `ghi-write` skill (`.claude/skills/ghi-write/`) is live and governs every issue write — filing, editing a body, commenting, promoting queue material." — There is an active skill named "ghi-write," located at .claude/skills/ghi-write/, that applies to every kind of write to a GitHub issue: creating a new issue, editing an existing issue's body, commenting on an issue, and promoting queued material into an issue.

16. "You will use it constantly; read it before your first issue write." — The reader will invoke this skill frequently and repeatedly, and must read it before performing their first issue-write action.

17. "Note that it tells callers to ask ghi-info first and falls back when the ask fails: that fallback is the current state of the world, because the ask tool does not exist yet." — The reader's attention is drawn to the fact that the skill instructs callers to query ghi-info first and has a fallback behavior for when that query cannot succeed; this fallback is presently how things actually operate, because the tool needed to perform that query does not yet exist.

18. "Building it is your pile." — Building that query tool falls within the reader's area of responsibility.

## The companions

1. "[#41](...) **run-agent** — one command to invoke a Claude or Codex agent headlessly from any caller, shell or Python, either runtime." — This names issue #41, "run-agent," described as a single command for invoking either a Claude or a Codex agent without an interactive interface, usable from any caller — whether a shell script or a Python program — regardless of which of the two runtimes is being invoked.

2. "ghi-info is defined as headlessly invokable, so this may need to exist first; deciding that ordering is part of your first action." — Because ghi-info's design requires it to be callable headlessly, run-agent may need to be built before ghi-info can be; determining whether that ordering is actually necessary is itself part of the reader's very first action.

3. "[#42](...) **reference-integrity checker** — verifying that links resolve and that cited revision-paths exist." — This names issue #42, "reference-integrity checker," described as verifying that hyperlinks resolve successfully and that referenced revision-paths cited in documents actually exist.

4. "A pure-code check, and the designated home for the broader question of what else code can check instead of an LLM." — This checker is implemented purely through code logic rather than requiring an AI model; issue #42 is also designated as the place where the broader question of what other checks can be handled by code instead of a language model is to be tracked.

5. "It serves the project's axis directly: deterministic checks beat asking a model to look." — This checker directly advances a core guiding principle of the project: that deterministic, code-based checks are preferable to having a model visually/contextually inspect something.

6. "[#39](...) **memory instrumentation** — echoing every memory read and write to the console; hooks that remind rather than block, with no context injection." — This names issue #39, "memory instrumentation," described as a feature that outputs every memory read/write event to the console, implemented via hooks whose function is to remind rather than block, and which do not inject any additional context into the agent's prompt.

## The doctrine you work inside

1. "Issues carry state; pair documents (`docs/issues/<n>-<slug>.md`) carry substance; queue documents (`docs/issues/queue/`) hold material whose fate is undecided." — GitHub issues track the current status of a piece of work; pair documents, following the naming pattern docs/issues/<number>-<short-name>.md and each paired with a specific issue, hold the substantive detailed content; queue documents, stored under docs/issues/queue/, hold material for which it has not yet been decided what it will become.

2. "Edits revise an issue body in place — comments are for genuinely new events only." — Changes to an issue's description should be made by directly editing the existing issue body text; comments should be used only to report events that are genuinely new since the last update, not as a substitute for editing the body.

3. "A to-do is a task rather than a memory (user-ruled 2026-08-12)." — An item representing something still to be done should be tracked as a task rather than stored as a memory entry; the user made this determination on 2026-08-12.

4. "The routing rules live in `docs/cross-project/nedschorus-founding-plan.md` § Project organization." — The specific rules governing how material is routed (among issue, pair document, and queue document) can be found in the "Project organization" section of docs/cross-project/nedschorus-founding-plan.md.

## Boundaries

1. "The launcher and supervisor belong to `fleet`; if run-agent needs changes there, tell the user rather than editing those scripts, since seats cannot hand work to each other directly." — Two components called "the launcher" and "the supervisor" are the responsibility of a different seat named "fleet," not the ghi seat; if building run-agent requires changes to those components, the reader should inform the user rather than edit those scripts themselves, because seats have no mechanism to directly transfer work to one another.

2. "Skill *builds* belong to `skill-builder` — but `ghi-write` is yours, because it is issue machinery rather than a general skill." — Building skills in general is the responsibility of a different seat named "skill-builder"; however, the ghi-write skill specifically belongs to the reader's responsibility, because it is considered specialized machinery for handling GitHub issues rather than a general-purpose skill.

## First action

1. "Read the ghi-info design and the `ghi-write` skill." — An instruction to read both the ghi-info design document and the contents of the ghi-write skill.

2. "Then report to the user what ghi-info's first build slice should be, and specifically whether run-agent ([#41](...)) must come first — ghi-info is defined as headlessly invokable, so the answer decides the order of your whole pile." — After reading, the reader should tell the user their assessment of what the first incremental buildable portion of ghi-info should be, specifically addressing whether run-agent (issue #41) must be built first; this matters because ghi-info's requirement of headless invocability means the answer determines the build order for the reader's entire area of responsibility.

3. "Propose; do not start building until he rules." — The reader should present this as a proposal only and should not begin actual implementation until the user makes a decision.

