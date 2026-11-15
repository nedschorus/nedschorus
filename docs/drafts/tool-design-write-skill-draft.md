---
name: tool-design-write
description: Use when you are about to write or revise the design of an in-house tool, program, hook or module of this project, before any of its code is written, and when the design-writing state of design-to-main asks for a design. Grounds the design in the code that exists, recommends one design or says honestly why it cannot, names the steps that need judgment, and runs the program that checks the design's required sections and the files it names.
---

# tool-design-write

A design says what will be built, why, and how, before code is written. This skill changes no code: what it produces is the design's own Markdown file, a GHI-MD under `docs/issues/` with the front matter line `kind: design`, and the design is the master until its code is on main. Questions the user asked of past designs, again and again, are listed with citations in `docs/issues/17-code-design-questions-the-user-asked-of-past-designs.md`; a design answers each one that applies to it before the user has to ask.

## Two working rules

1. **Write each result into its MD file when the result is produced.** A design, a decision or a finding goes into the MD file it belongs in at the moment it is produced, not at the end of the agent-session. A result that lives only in a conversation is lost to every later agent: the conversation cannot be read or shared as a record, and only files travel when the user forks an agent-session or hands the work to another agent. That this skill changes no code does not stop you writing the design's own MD files; writing them is what the skill produces.
2. **Find a design's weaknesses before presenting it, and label each claim.** Before you present a design or an experiment, look for the design's weaknesses and confounds yourself and state them up front, and say which of your claims you verified, which a document states, and which are your own inference. A factual claim about a tool is answered from primary sources, such as the installed program, its GitHub issues or its documentation, never from memory alone. A design that holds only until the user's first question reads to him as made up.

## How to write the design

Read the code before you design. Find the programs, helpers and conventions the design will use or resemble, and cite each by path and line, so a reader can check what you found. Look for an existing tool, in this project or outside it, that already does the job; when one does, the design uses it or says why not.

Recommend one design. When the evidence does not support one, say so instead, with one of these honest exits and what would settle it: `needs-feasibility-evidence`, a prototype or measurement must come first; `needs-human-decision`, the choice is the user's; `postponed`; `rejected`; or `unknown`.

Give the design these sections, as headings at any level from `##` down. `nc-systems/skills/tool-design-write/tool-design-write-required-sections-judgment-steps-and-named-files-exist-check.py` holds the list of required headings, and `--help` prints it.

- **Problem**: what is wrong or missing, who meets it, and the evidence from real cases that it needs building; a guard, validation, retry or workaround cites the failure it answers, as CLAUDE.md requires.
- **Goals and non-goals**: what the tool must do, and what it could reasonably do but will not.
- **What exists today**: the code, tools and records the design builds on or replaces, cited by path and line.
- **The design**: each component, the one agent-seat, program or person that owns it, the data it reads and writes and where each record is kept, the flow from the tool's entry point to its outputs, and what the user sees and where.
- **The judgment steps**: a list item for each step a model must do because it needs judgment, saying which model or agent does it and how the quality of its judgments is tested on real cases. Every other step is code, as CLAUDE.md's code-prompt-code rule says.
- **Failure behaviour**: what the tool does when each step, input, dependency or machine fails, stops partway or is run twice, what it prints, its exit code by `docs/nedschorus-wiki/nedschorus-how-a-program-reports-success-failure-and-findings-with-its-exit-code.md`, and who is told.
- **Alternatives considered**: the smaller design, doing nothing, and each other reasonable design, each with why it was not chosen.
- **Tests**: how each part is tested, and the command and output that show the built tool works.
- **Files**: a list item for each file the build creates or changes, in the order the build makes them, each starting with the file's repository path in backticks; an item for a file the build creates carries `#created_by_the_build`. Choose each new name by `docs/nedschorus-wiki/nedschorus-how-to-choose-a-name-for-files-code-and-glossary-terms.md`.
- **Deferred-decisions**: as the project glossary defines the section.

Then run `python3 nc-systems/skills/tool-design-write/tool-design-write-required-sections-judgment-steps-and-named-files-exist-check.py <design path>` and fix each finding it prints, until it exits 0.

## Asking the user

Put the design's open decisions to the user as an approval-walk, through the walk-me-through skill, one decision per item, each with your recommendation. Ask only what the user must decide; settle the rest yourself and record it in the design. Then give the design the review the cold-read skill requires for a design.
