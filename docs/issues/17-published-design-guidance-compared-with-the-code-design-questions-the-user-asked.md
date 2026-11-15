---
issue: "[Candidate skill: design-change — read-only evidence-grounded design with one recommendation and honest exits](https://github.com/nedschorus/nedschorus/issues/17)"
---

# Published design guidance compared with the code-design questions the user asked

This file is step 2 of the next action in GHI [Candidate skill: design-change — read-only evidence-grounded design with one recommendation and honest exits](https://github.com/nedschorus/nedschorus/issues/17), whose GHI-MD is `docs/issues/17-candidate-skill-design-change-read-only-evidence-grounded.md`. Step 1 listed, in `docs/issues/17-code-design-questions-the-user-asked-of-past-designs.md`, the 26 questions the user asked about, or decided, more than once in past designs; this file calls them Q1 to Q26 by their number there. It compares that list with the Anthropic code-architect agent and four other published sources of design guidance, and says, for each source, what it adds that the list lacks, and then what the list has that no source covers. Step 3 decides which additions the design skill takes up.

## The sources, and how each was read

1. **Anthropic's code-architect agent and the feature-dev command that runs it**, in the plugin feature-dev of the repository anthropics/claude-plugins-official, at commit 4ca561fb8532594e7a5faef945e85096fcec0616: https://github.com/anthropics/claude-plugins-official/blob/4ca561fb8532594e7a5faef945e85096fcec0616/plugins/feature-dev/agents/code-architect.md and https://github.com/anthropics/claude-plugins-official/blob/4ca561fb8532594e7a5faef945e85096fcec0616/plugins/feature-dev/commands/feature-dev.md. Both files were read whole, as raw text through the GitHub API, on 2026-11-15; quotations below are copied from them. The copies once in anthropics/claude-code under `plugins/feature-dev/` were deleted there, and the README of that repository's plugins directory now points to claude-plugins-official.
2. **Design docs at Google**, by Malte Ubl, published 2020-07-06, https://www.industrialempathy.com/posts/design-docs-at-google/. One engineer's account of Google's practice, not a document Google publishes as policy. Read on 2026-11-15 through a fetch tool that returned a summary, not the page's text, so what it says is given below in paraphrase, without quotation marks.
3. **Architecture decision records**: Michael Nygard's post "Documenting Architecture Decisions" of 2011-11-15, https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions, read through the same summarizing fetch tool, so paraphrased; and the MADR template, https://github.com/adr/madr/blob/8135ed2e01503be852769402ec3eeb585bfe75a2/template/adr-template.md, read whole as raw text, so quoted. The two are counted as one source.
4. **The Rust RFC template**, https://github.com/rust-lang/rfcs/blob/f17e8623ee2e2854570dcdb936a9f4ab08c0fcd4/0000-template.md, read whole as raw text and quoted.
5. **OpenAI's ExecPlans**, "Using PLANS.md for multi-hour problem solving", https://developers.openai.com/cookbook/articles/codex_exec_plans, read through the summarizing fetch tool, so paraphrased. The candidate in GHI 17 was first built from source 1 with two parts of this one, as `nc-queue/archived/2026-07-22-candidate-skill-source-evidence.md` records under its item 4.

## Which question each source touches

A cell names the part of the source that bears on the question; an empty cell means the source says nothing on it. "Partly" means the source raises the subject but not the point the user made.

| Question of step 1 | code-architect and feature-dev | Design docs at Google | ADR and MADR | Rust RFC template | ExecPlans |
|---|---|---|---|---|---|
| Q1 simpler design, smaller scope | the "minimal changes" architect; "Simple and elegant" | non-goals; when not to write a design doc | Considered Options | Drawbacks; "What is the impact of not doing this?" | |
| Q2 already exists, here or outside | "Find similar features"; patterns with file:line | alternatives considered | Considered Options | Prior art; "could this be done in a library" | |
| Q3 judgment steps, code-prompt-code | | | | | |
| Q4 review each part gets | Phase 6, three code-reviewer agents | the review process, light and heavy | | | |
| Q5 evidence of need, measured limits | | a prototype as evidence | More Information, evidence for the outcome | Motivation, concrete use cases | Surprises and Discoveries, with evidence |
| Q6 single source of truth, design and code drift | | | partly: superseded, not deleted | | partly: a living document |
| Q7 what the user sees when it fails | | partly: observability | | partly: sample error messages | |
| Q8 who reads each text, plain words | | | | guide-level explanation | the reader knows only the plan and the working tree |
| Q9 what needs the user's approval | partly: wait for approval before building | | decision-makers, consulted, informed | | |
| Q10 failure behaviour | "Critical Details: Error handling" | | | | Idempotence and Recovery |
| Q11 timing, cost, usage limits | partly: performance | partly: cross-cutting concerns | | | |
| Q12 enforced by code, not instructions | | | Confirmation: "automated or manual fitness function" | | |
| Q13 has the failure happened, is the guard worth it | | | | partly: Drawbacks | |
| Q14 kept current over time | | | partly: status, superseded | | partly: a living document |
| Q15 terms defined once | | | | partly: new named concepts introduced | every term of art explained or not used |
| Q16 every case covered | partly: edge cases among the clarifying questions | | | corner cases "dissected by example" | |
| Q17 where each file is kept | Implementation Map, every file to create or modify | | | | full paths from the repository root |
| Q18 root cause | | | | | |
| Q19 outside limits, confirmed | | degree of constraint | Decision Drivers | | Interfaces and Dependencies |
| Q20 decisions recorded durably | "Key decisions made" in the summary | | the record is the decision | Unresolved questions | Decision Log |
| Q21 names | | | | | |
| Q22 owner of each piece of work | Component Design: responsibilities | | | | |
| Q23 work starts without waiting on the user | | | | | |
| Q24 how each part is tested | "Design for testability"; testing among Critical Details | | Confirmation | | Validation and Acceptance |
| Q25 which model judges, and how well | | | | | |
| Q26 how review findings are graded | partly: "fix now, fix later, or proceed as-is" | | | | |

## What each source adds that the list from step 1 lacks

### Anthropic code-architect and feature-dev

- **Evidence from the code, cited by line.** The blueprint opens with "Patterns & Conventions Found: Existing patterns with file:line references, similar features, key abstractions". Q2 asks whether something exists; this asks the designer to show what exists, by line, before designing.
- **One decision, committed to.** "Make decisive choices - pick one approach and commit" and "Make confident architectural choices rather than presenting multiple options." The list has no question on how many options a design presents.
- **An implementation map and a build order.** "Implementation Map: Specific files to create/modify with detailed change descriptions" and "Build Sequence: Phased implementation steps as a checklist". Q17 asks where files are kept; no question asks for the list of files the build touches, or the order of the build.
- **Data flow end to end.** "Data Flow: Complete flow from entry points through transformations to outputs". No question asks for it.
- **Questions to the user before the design, by category.** feature-dev's Phase 3 lists what to ask about: "edge cases, error handling, integration points, scope boundaries, design preferences, backward compatibility, performance needs", and says "DO NOT SKIP". Backward compatibility, and integration points, appear in no question of the list.
- **Security.** "Critical Details: Error handling, state management, testing, performance, and security considerations." The list has no question on security; the project's rules say hardening against deliberate attackers is not needed, so this addition may be dropped by rule rather than by oversight.
- **A contradiction step 3 must settle.** The agent says to pick one approach, but the command that runs it launches "2-3 code-architect agents in parallel with different focuses: minimal changes (smallest change, maximum reuse), clean architecture (maintainability, elegant abstractions), or pragmatic balance (speed + quality)", and then tells the main agent to present them with "your recommendation with reasoning" and "Ask user which approach they prefer". GHI 17's opening asks for one recommendation only after the evidence supports one, with honest exits otherwise; feature-dev's way of reaching one recommendation is to generate the alternatives first and then recommend among them.

### Design docs at Google

- **Goals and non-goals.** Non-goals are things that could reasonably be goals and are chosen not to be. Q1 asks whether scope can shrink; no question asks the design to say what it will not do.
- **Alternatives considered, as a required part.** The article counts this among the most important sections: other reasonable designs, their trade-offs, and why the chosen one is better for the goals. Q1 and Q2 ask about simpler or existing designs; no question asks the design to record the alternatives it rejected.
- **When not to write a design doc.** When the solution is not ambiguous, or the document would only be an implementation manual with no trade-offs, it is not worth writing; a mini design doc of one to three pages fits incremental work. The list has no question on whether a design is needed at all, or on its length.
- **Cross-cutting concerns as a standard list.** Security, privacy and observability, each with how the design affects it; the article suggests a team standardize the list. Q7 and Q11 touch observability and cost; the idea of a fixed list the project keeps is new.
- **A system-context diagram** that places the system among the others it touches.

### ADR and MADR

- **One decision per record, never deleted.** Nygard: each record holds one significant decision; a reversed decision stays, marked superseded, with a pointer to its replacement. Q20 asks that decisions be recorded; this says how a later decision replaces an earlier one without erasing it.
- **Consequences, good and bad.** MADR: "Good, because …" and "Bad, because …"; Nygard lists every consequence, positive, negative and neutral. No question asks the design to state what gets worse.
- **Decision drivers.** MADR: "{decision driver 1, for instance, a desired software quality, faced concern, constraint or force}". The forces the choice answers to, named before the options.
- **Confirmation.** MADR: "Describe how the implementation / compliance of the ADR can/will be confirmed. Is there any automated or manual fitness function?" Q12 asks whether a rule is enforced by code; this asks it of the design's own decision: how a later reader confirms the code still follows it.

### Rust RFC template

- **Drawbacks.** "Why should we *not* do this?" A section of its own, before the rationale. The list asks for a simpler design (Q1) and whether a guard is worth its cost (Q13); it never asks the design to argue against itself as a whole.
- **The cost of doing nothing.** "What is the impact of not doing this?"
- **A guide-level explanation.** The design explained as if it already existed, to someone who will use it, through examples. Q8 asks who reads each text; this asks the design to show the user's or caller's view before the internals.
- **Corner cases by example.** The reference-level explanation must make "Corner cases are dissected by example", and "should return to the examples given in the previous section". Q16 asks whether the cases cover everything; this says how to show it.
- **Open questions sorted by when they are settled.** "What parts of the design do you expect to resolve through the RFC process before this gets merged?", "… through the implementation of this feature before stabilization?", and the related problems out of scope. The project's deferred-decisions section, with `#not_in_this_run`, `#rejected` and `Decided elsewhere`, already sorts them; the RFC adds no case the project lacks, but confirms the practice.
- **Future possibilities**, kept apart so that they do not argue for the design: "having something written down in the future-possibilities section is not a reason to accept the current or a future RFC".

### ExecPlans

- **Acceptance as observed behaviour.** Acceptance criteria are behaviour a person can check, with specific inputs and expected outputs, not facts about the code's internals. Q24 asks how each part is tested; this asks the design to name the command and the output that shows the built thing works.
- **Safe to repeat, and recovery.** Steps should be safe to run again; a risky step needs a retry or rollback path, and a destructive one a backup. Q10 asks what happens on failure; this adds what happens when a step is run twice.
- **Milestones each checked on their own, and prototypes labelled.** A prototype milestone says so, and says what would promote or discard it. The list has no question on how the build is cut into steps that can each be shown to work.
- **Surprises and Discoveries.** Unexpected behaviour found during the work, with short evidence. Close to the first working rule GHI 17 carries, that each result goes into its file when produced.
- **Full repository paths, and the working directory for each command.**

## What the list from step 1 has that no source covers

- **Q3, which steps need judgment, with every other step in code.** No source separates the work a model does from the work code does; this is CLAUDE.md's code-prompt-code rule, and the design skill must carry it from the project.
- **Q25, which model judges each judgment step, and how its quality is measured on real cases.** No source designs systems whose parts are model calls.
- **Q13, whether the failure a guard handles has happened, and whether the guard is worth its cost.** The sources ask for failure handling (code-architect, ExecPlans); none asks that a guard be justified by a failure seen or foreseeable, as CLAUDE.md does.
- **Q18, the root cause.** No source asks whether the design fixes the cause or one case of it.
- **Q21, names.** No source asks that names say what they name or be checked for collisions.
- **Q23, work that does not wait on the user.** feature-dev asks the opposite: "Wait for answers before proceeding". The user asked that agents keep working rather than block on him.
- **Q9, minimizing what reaches the user for approval, and Q7, showing the user only what he must act on, on the device he is using.** MADR names who decides and who is informed; no source asks how to keep the decider's load small.
- **Q6, which copy is the master, and how a design and its code are kept from drifting.** ADRs keep superseded records and ExecPlans revise the plan as the work goes, but neither says which of design and code governs, or when.
- **Q14, keeping what the design produces current: staleness, maintenance, leftovers.** The sources keep the document current, not the files, records and state the built system produces.
- **Q11 in the project's sense: the user's hours and the usage limits of the agent accounts.** Google's cross-cutting concerns and code-architect's performance touch cost; none treats model usage as a budget.
- **Q12 beyond one decision: delivering each instruction to the agent where and when it acts, by hook or check, instead of by written instruction.** MADR's Confirmation is the nearest, and covers only the design's own decision.
- **Q4 and Q26, which review each text gets and how review findings are graded and routed.** Google describes design review and feature-dev runs code reviewers with a three-way choice for the user; none grades findings by whether they block a merge.
- **Q15, a term defined once in a glossary.** ExecPlans asks for plain words in each plan; none keeps one definition across documents.
- **Q22 among agents: which agent-seat or component owns each piece of state so that no two do the same job.** code-architect gives each component its responsibilities, inside one feature, not across agents.

## Decisions settled by the agent

Drafting the skill raised 13 questions, called D1 to D13 here so as not to be confused with Q1 to Q26. Under item 4.1 of approval-walk prime-intellect-open-decisions-for-the-user-2026-10-28, approved 2026-10-28 (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/prime-intellect-open-decisions-for-the-user-2026-10-28-minutes.md` lines 87 to 93), the user does not approve GHIs and only cold-reads them, so an agent settles each question below and none goes to him. The skill's final SKILL.md text still needs his approval, because `.claude/skills/` holds files the instruction-file guard protects.

- **D1, the skill's name and scope.** Settled by two rulings that agree. Item 29 of approval-walk ned-box-helper-all-open-items-2026-10-15, which the user approved with "a" at 2026-10-21T05:01Z (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ned-box-helper-all-open-items-2026-10-15-minutes.md` line 192; his words in `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/ned-box/projects/-home-nedlern-agents-ned-box-helper/a489de60-8192-410a-9cc3-5635fb6c680c.jsonl`), makes three design skills, one each for a tool, a test and a system. His direction of 2026-10-29, sent at 2026-10-30T00:23Z (`nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/ned-box/projects/-home-nedlern-agents-reboot-test/222a1661-826e-4213-834e-439b45884194.jsonl`), ends with a sentence the GHI-MD's quotation leaves out: "Anyway, we're just following a GHI, I would think, for creating a code design skill, I suppose, or a tool design." So the skill is `tool-design-write`, for in-house tools as the fifteenth job of GHI 1058 defines them. Neither ruling says where module design goes; item 27 of the same approval-walk, accepted with "27 a" (minutes line 178), leaves modules, files of functions that other files import, off the tool-design page. The agent's choice: a module is designed inside the design of the tool or system that loads it, and has no design skill of its own. The GHI-MD's words "programs, tools and modules" are narrowed to match by an edit-GHI.
- **D2, the ten required sections.** Kept as the checker's `REQUIRED_SECTION_HEADINGS` lists them. GHI 1080's definition of a design will own the list once written (its GHI-MD's bullet Designs); see Deferred-decisions.
- **D3, `Defects fixed` and `Decided elsewhere` as required sections.** Not required. A pull request's description already carries a `#root_cause` or `#no_defect_fixed` line for each defect, as CLAUDE.md requires, and a decision made elsewhere goes in Deferred-decisions, as the glossary's entry for that section allows.
- **D4, a tool whose every step is code.** Its section The judgment steps holds the one item "None: every step is code". The draft says so, and the checker's test shows the checker accepts it. Basis: CLAUDE.md's code-prompt-code rule, under which an all-code tool is the preferred case, which a rule demanding a judgment step would punish.
- **D5, an honest exit.** A design that takes one needs only Problem, What exists today, Deferred-decisions and a section Honest exit that names the exit in backticks. The checker implements this as `HONEST_EXIT_REQUIRED_SECTION_HEADINGS`, with tests. Basis: GHI 17's opening, which asks for honest exits instead of prompt-induced certainty; a design with no chosen design has no Files or Tests to give.
- **D6, which of the 26 questions a design answers.** Only those that apply to it, as the draft says. Some, such as Q26 on how review findings are graded, concern the project's process, not one tool.
- **D7, one recommendation or several options.** One recommendation, with the rejected options under Alternatives considered. Basis: GHI 17's opening and code-architect's "pick one approach and commit". The user's question of 2026-10-28 whether a design skill should "ask for two versions" of a design, one with some prompting and one with more code (`nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/mac/projects/-Users-el-agents-cold-read-research/87e00ba1-357a-4f2b-ac40-d652a90d0185.jsonl`, 2026-10-28T21:18Z), was a question, not a ruling; it is taken up by requiring Alternatives considered to give the version that does in code each step the design leaves to a model.
- **D8, which published additions the skill requires.** Non-goals (Goals and non-goals), alternatives (Alternatives considered), acceptance as a command and its output (Tests), and evidence cited by path and line (What exists today). Not security, because CLAUDE.md says hardening against deliberate attackers is not needed. Not MADR's Confirmation as a section of its own: for a tool design, the Tests section's command and output is that confirmation.
- **D9, the hashtag `#file_not_yet_existing_that_this_design_creates`.** Kept; the checker and the draft use it.
- **D10, `scripts/md-drift-lint.py` skipping paths on a line that carries that hashtag.** Not built now. The lint reaches a design only through `scripts/dangling-path-citation-check.py`, which a push reminder hook runs; a false "path does not exist" there costs no work, so CLAUDE.md's rule on guards and workarounds does not admit the change until such a finding costs work. If it does, the change goes in a pull request of its own, since it changes the lint's tests.
- **D11, the `-tool-design` file-name ending and the line naming the skill that wrote the design.** Waits on GHI 1080, which item 29 gave both; see Deferred-decisions.
- **D12, a program for the skill's order.** Built: `nc-systems/skills/tool-design-write/tool-design-write-design-document-next-step-print.py`, with its test, prints the next step from the design file and the form check: write the design, fix the check's findings, or hand the design to the walk-me-through and cold-read skills. The draft no longer lists steps in order. Basis: CLAUDE.md's code-prompt-code rule.
- **D13, the tool-design standard page of task #107.** Not on main (no file under `docs/nedschorus-wiki/` or `.claude/` names tool-design at origin/main de14ef960, 2026-11-15); see Deferred-decisions.

## Deferred-decisions

- When GHI 1080's definition of a design lands, the checker's `REQUIRED_SECTION_HEADINGS` and the draft's list of sections point to it as their one definition, and change to match it (D2).
- When GHI 1080 settles the file-name endings `-tool-design`, `-test-design` and `-system-design` and the line naming the skill that wrote a design, the draft says to give each design both, and the checker checks both (D11).
- When the tool-design standard page of task #107 merges, the draft's section The design points to it, and the checker checks what of it can be checked by code (D13).
