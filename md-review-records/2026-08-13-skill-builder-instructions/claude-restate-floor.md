<!-- provenance: runtime=claude model=claude-sonnet-5 effort=high cell=restate tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/skill-builder-instructions.md -->

# Title

1. This is the title of the document, identifying it as the set of instructions belonging to a role or agent-assignment called "skill-builder."

# Preamble (before "## The queue")

1. The body of work assigned to this seat (role) is described as a "pile," specifically the queue of skills that have been proposed as candidates but not yet built/accepted.
2. There are seven proposed skills; each one follows the same general kind of build process ("the same shape"); they all share a single common checklist for authoring and a single common review process (the "walk"); this shared structure is precisely the reason these seven items were grouped together under one seat; and the practical implication is that, due to accumulated experience/process reuse, building the seventh skill should require substantially less effort than building the first one did.
3. The reader is directed to read a separate linked document called "the seat model" (at the path agent-seat-model.md) in order to understand how seats (role assignments for agents) function in general.

# ## The queue

1. Every one of the seven skills listed in the table below has a corresponding GitHub issue that tracks its current status, and for several of them there is also a separate "queue document" containing more detailed information.
2. Issue #18 is for a skill named "write-test-plan," which produces test plans whose priorities are ranked according to the consequences/impact of failure and which rely on "observable oracles" (verifiable, checkable criteria for determining pass or fail); this issue is flagged as probably the first skill that should be built; additional supplementary material ("riders") for it is located in the specified file path.
3. Issue #20 is for a skill named "implement-with-evidence," whose core method ("kernel") is based on red/green evidence — likely referring to a failing-then-passing (red-then-green) test-driven evidence pattern; this skill does not impose requirements to delete existing work and restart from scratch; its supplementary "riders" material is located in the specified file path.
4. Issue #21 is for a skill named "diagnose-failure," which performs debugging aimed at identifying the causal root of a failure within some deliberately limited scope, and which includes a rule that after three attempted fixes have failed, the process escalates or halts rather than continuing indefinitely; further detail is documented in the specified file.
5. Issue #22 is for a skill named "review-change," which reviews a change tied to one exact, specific version of the code (not something that shifts), prioritizes finding defects above other concerns, and requires findings to pass through a gate made up of five distinct parts/criteria before being accepted.
6. Issue #23 is for a skill named "eval-agent-change," which evaluates an agent's change by comparing a baseline version against a candidate version in an A/B-test-style comparison, using specifically designed "trigger cases" (test cases meant to provoke particular behavior), and reporting results as raw, unprocessed counts rather than derived statistics like percentages.
7. Issue #19 is for a skill named "attack-artifact," which performs an adversarial review (actively probing for flaws) conducted in isolation from other review processes; this issue was filed/framed as a question about comparison within some process referred to as "d-review."
8. Issue #17 is for a skill named "design-change," which produces design output that does not alter anything (it only reads/observes — "read-only"), is grounded in verified evidence rather than speculation, results in a single recommendation rather than multiple options, and includes "honest exits" — meaning it should truthfully report when it cannot proceed or reach a conclusion rather than fabricating an answer.
9. In addition to the seven skills, issue #24 is called the "queue-drain procedure," referring to the review process responsible for emptying out three separate queues: a "wiki queue," a "pair queue," and a "draft-label issue queue" (issues tagged with a "draft" label).
10. This queue-drain procedure (#24) sets the rules for how the rest of this seat's assigned work is carried out, and because of that governing role, the reader should read it before the other items — i.e., early in their work.

# ## How skills are built here

1. The reader should locate a document called the "skill-authoring checklist" somewhere within the docs/ directory and use it as the procedure to follow.
2. This checklist is a standard that belongs to and was created by this project itself, and it existed before the current reader began working on this task — it is pre-existing, established convention, not something to be reinvented.
3. The skills that already exist in the repository — located at the four given paths (walk-me-through, md-review, handoff, and ghi-write) — serve as concrete worked examples, and carefully reading at least two of them is presented as the most efficient way to learn the project's particular stylistic conventions ("house style").
4. The following three rules are ones that caused problems in previous attempts at building skills (they "bit" those previous efforts), implying they are cautionary lessons drawn from past mistakes.
5. A skill document belongs to a category of artifact called "instruction-class," meaning it is treated with the formality and seriousness of a set of instructions, distinct from other kinds of files such as ordinary documentation or code.
6. A skill only becomes finalized and committed into the project ("lands") by going through a process called "the user's walk" — a review process led by the user — implying there is no other route by which a skill can be finalized.
7. This requirement is enforced not just by convention but automatically/programmatically, through a mechanism called the "instruction-file-guard" hook (an automated script triggered at some point in the process); specifically, this works via a file called ".walk-approved," which contains a quotation of the user's explicit approval, and this marker file is used up ("consumed") by the single write operation it authorizes — implying it functions as a single-use authorization token tied to one specific approved write.
8. Skill documents should be written as directives telling the reader what to do, not as explanatory prose or discursive writing that argues or provides background (an "essay").
9. Side comments or digressions that explain the reasoning or justification behind an instruction ("rationale asides") are removed during authoring.
10. The purpose of the text within a skill is to tell an agent (an AI assistant) what actions to take — the content should be actionable directives rather than explanation.
11. As a concrete precedent, on August 6, 2026, four such reasoning-explaining digressions were removed from the "walk-me-through" skill specifically for this reason (because skills should be instructions, not essays).
12. The standard that skill text must meet ("the bar") is that it be understandable without any additional context beyond what is written — a reader with no prior background should be able to fully understand it.
13. On August 11, 2026, the user made an authoritative decision establishing that agents reading skill instructions must be able to understand them immediately and completely on their own, without needing extra explanation or outside context ("cold").
14. Because of this requirement, before a skill draft that has reached a stable, finished state ("settled") is allowed to be finalized and committed ("lands"), it must first go through a process called "md-review" to confirm it meets this readability standard.

# ## Related work you did not do

1. There is a separate seat (role assignment) called "sanity-checker" which is responsible for the methodology used in reviews, and this seat has the authority to add a new reviewer to something called the "md-review grid" (presumably a matrix or panel structure used in the md-review process).
2. Two specific pull requests, numbered 51 and 53, are the responsibility of the sanity-checker seat, not of the reader (the skill-builder seat).
3. If, while building a skill within this seat's assigned queue, the reader finds that the skill would change the way reviews are conducted or delivered, the reader should not decide that matter themselves as part of this seat's work, but should instead transfer that particular aspect to the appropriate owner (the sanity-checker seat).

# ## First action

1. The first thing the reader must do is read two issues — issue #24 (referred to here as "the drain procedure," i.e., the queue-drain procedure described earlier) and issue #18 (referred to as "the likely first build," i.e., the write-test-plan skill flagged earlier as probably the first to be built) — and, for issue #18 specifically, also read its associated supplementary "riders" file.
2. After completing that reading, the reader should tell the user which of the seven candidate skills they recommend building first, along with the reasoning behind that recommendation.
3. The reader must not begin actually building/implementing any skill until the user makes his decision (rules on the matter).
4. The decision about the order in which the skills are built belongs to the user — it is his choice to make, not the agent's.
5. This restates the earlier point that a skill must go through the "walk" process (the user's step-by-step review) before it is finalized and committed into the project.

