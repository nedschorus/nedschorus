---
issue: "[Type definitions for the project's kinds of markdown: what each contains, leaves out, and how long it runs](https://github.com/nedschorus/nedschorus/issues/1080)"
---

# Type definitions for the project's kinds of markdown: what each contains, leaves out, and how long it runs

## Why

Agents writing markdown with no definition of the kind they are writing fill it with history, rulings, citations, defence of decisions and detail the code already states, and each later edit adds more. A reader then has to dig the present state of the system out of the story of how it came to be. The overview of a system was the first kind defined from industry best practice: a draft definition, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/cold-read-improvement/overview-definition-research-2026-10-04/overview-definition-draft-2.md`, says what an overview contains, what it leaves out, how long it runs and how it is kept true. The research behind it is in the same directory. Each kind below needs the same treatment.

A survey of the kinds of markdown on main ranks where a definition helps most, by how much agents write of each kind, how much padding it carries, and how many readers it costs: `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/cold-read-improvement/overview-definition-research-2026-10-04/markdown-kinds-needing-type-definitions-survey.md`. Kinds whose guide already says what to leave out (skills, skill prompts, `CLAUDE.md`) carry 3 to 7 dates, rulings and citations per 1,000 words; the durable kinds with no such guide carry 14 to 18.

## Method, for each kind

1. Collect industry best practice for the kind, and real exemplars of it from well-documented projects.
2. Write a draft definition: what the kind contains, what it leaves out, how long it runs, and how it is kept true. Every kind leaves out the research behind an instruction; that research stays with the work that produced it.
3. Give the draft a full cold read, then an approval-walk with the user.
4. Land the definition where agents writing that kind will read it, such as the skill that writes it.

## The kinds

- **GHI-MDs.** Each GHI-MD is one of five kinds, named by a suffix at the end of its file name, `<number>-<name>-<kind>.md`, and by a matching GitHub label: `-design` for a new component; `-change-request` for a change to a baseline; `-bug` for code that does not do what its baseline says; `-chore` for upkeep that changes no behaviour; `-research` for a question to answer, with no code promised. A baseline is a design, its design-contract and its test-design once their code has landed on main; "baseline" and "change request" are SDLC-terms, to be listed in `docs/nedschorus-wiki/nedschorus-sdlc-terms.md`. A bug changes code and tests only; when the fault turns out to be in the baseline, the work is a change request instead. The definition says how a GHI-MD changes kind, and what happens to GHI-MDs filed before the suffixes existed. A change request names the baseline design and design-contract it changes, what should change and why, and whether the change is corrective, adaptive, perfective or preventive. Starting points: bug-report and feature-request practice, IEEE 828 change control, Rust RFC and Python PEP templates.
- **Designs.** What a design contains while its code is built, and what happens to it once the code lands: with its design-contract and test-design it becomes a baseline, changed only through a change request. A `-design` GHI-MD is where a design starts; whether the design stays inside that GHI-MD or moves to a file beside its code is part of this definition. Starting points: Google's design-doc practice, Rust RFC and Python PEP templates.
- **Project glossary entries.** What an entry in `docs/nedschorus-wiki/nedschorus-glossary.md` holds and leaves out. The user has decided the core: an entry defines its term in a sentence and keeps any link to more detail, and holds no history, user-rulings, rationale, design detail or how-to steps; each term has one entry, in the glossary of the widest scope that uses it. The three glossaries were trimmed to this in PR [Glossaries: one entry per term, definitions without padding, unused terms dropped](https://github.com/nedschorus/nedschorus/pull/1145). Starting point: terminology practice for definitions, such as ISO 704.
- **Seat-briefs.** What a seat-brief holds. A seat-brief is now the `CLAUDE.local.md` at the root of an agent-seat's checkout, which git does not track, and it is in context for every agent-session of that agent-seat. Starting point: Anthropic's guidance on writing `CLAUDE.md` and system prompts.
- **Handoff next-step files.** What the next-step file of `.claude/skills/handoff/SKILL.md` holds for a successor that did not see the work. Starting point: shift-handover practice, such as SBAR and on-call handoff notes.
- **Wiki pages other than overviews.** What a page in `docs/nedschorus-wiki/` holds, by the kind of page it is. Starting point: Diátaxis's split of explanation, reference, how-to and tutorial.

## Next action

Define GHI-MDs and designs together, first: whether a design lives inside its GHI-MD or beside it is one question for both definitions.

## Relations

- GHI [overview-write skill: how an overview of a system is written and checked before it lands](https://github.com/nedschorus/nedschorus/issues/168): the overview definition this method comes from.
- GHI [refresh-design: when a system's code lands, bring its design, build-slice plan and overview into line — removing, never revising](https://github.com/nedschorus/nedschorus/issues/670): what happens to a design once its code lands; the designs definition replaces its rule that a refresh of a design "removes and never revises".
- GHI [Candidate skill: design-change — read-only evidence-grounded design with one recommendation and honest exits](https://github.com/nedschorus/nedschorus/issues/17): its name "design-change" means writing a design before code, not a change request.
- GHI [update-glossary skill: the editor rules for the nedschorus glossary, taken off the page (user-asked 2026-09-06)](https://github.com/nedschorus/nedschorus/issues/262): where the glossary-entry definition lands.
- GHI [wiki-write skill, and the detect-set-aside-ask hook that enforces it — checking the file, not the tool call](https://github.com/nedschorus/nedschorus/issues/343): where the wiki-page definitions land.
- GHI [Genre-suffix naming for non-reviewable documents (-log, -report, -capture), and mechanical exclusion from the review instruments](https://github.com/nedschorus/nedschorus/issues/152): file-name suffixes for other kinds of document.
- GHI [One documentation tree in place of the wiki and the rest of docs, with Obsidian opened on it](https://github.com/nedschorus/nedschorus/issues/1066): may move where wiki pages live.
