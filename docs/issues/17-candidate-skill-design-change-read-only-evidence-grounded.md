---
issue: "[Candidate skill: design-change — read-only evidence-grounded design with one recommendation and honest exits](https://github.com/nedschorus/nedschorus/issues/17)"
---

# Candidate skill: design-change — read-only evidence-grounded design with one recommendation and honest exits

Read-only design before code: analyze existing repo patterns, produce a blueprint (boundaries, interfaces, data flow, failure behavior, likely files, order, validation commands), recommend ONE architecture. Spine: Anthropic code-architect nearly one-to-one + two ExecPlans grafts (behavioral validation commands, full path discipline). cops caveat is load-bearing: one-recommendation only after evidence supports one — needs honest exits (needs-feasibility-evidence, needs-human-decision, postponed, rejected, unknown) instead of prompt-induced certainty.

## Disposition: candidate-on-GHI, not built (boss-ruled 2026-07-24)

Captured per the three-state artifact rule (pending state -> GHI, lean -> issue-only). Boss ruling on the outer walk (session ad0a3708): candidates are recorded, none is built now; a build triggers only when a real task exposes the missing decision (cops item-12 delta: select ONE candidate from the first real task). Define-work carried the individual ruling "at best it's worth a GHI in nc"; the remaining eight were approved as a batch off the collapsed-walk summaries.

## Evidence of record

- Six-agent source read: `nc-queue/archived/2026-07-22-candidate-skill-source-evidence.md` (this skill's section)
- cops delta packet: `nc-queue/archived/2026-07-23-cops-candidate-skill-delta-packet.md` (this skill's section)
- Shortlist origin: `docs/issues/9-neds-notes.md` § Working skill shortlist

## The user's direction of 2026-10-29: build it as a code-design skill

The user, in agent-seat reboot-test's session on 2026-10-29: "I'm thinking that we have some sort of design skill, which helps us create designs. We can probably learn a lot from the many designs we've created over the last month. And there's all sorts of logs. There are probably some Anthropic skills like this or other extremely reputable sources. These are code design of code things, not just design things. They're tool design and module design kind of stuff. And usually they have a sort of a question and answer stuff, which we kind of do, but not officially, because the walks kind of end up doing that a little bit. Maybe the designs are organized in a walk."

This lifts the 2026-07-24 disposition above: the skill is now wanted, for the design of programs, tools and modules, not documents in general. Three sources feed it:

- The project's own designs: 62 GHI-MDs under `docs/issues/` carry `kind: design` (`grep -l '^kind: design' docs/issues/*.md`, 2026-10-29), with the approval-walk minutes in `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/` and the cold-read-records in `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/` that show what the user asked about, corrected or ruled on each.
- Published design practice from Anthropic and other reputable sources, starting from the Anthropic code-architect agent this candidate was first built on.
- The project's rules a design must meet: CLAUDE.md's code-prompt-code bullet, which asks each design to name the steps that need judgment, and the tool-design standard checked by the fifteenth job of GHI [Regular maintenance: the list of maintenance jobs, how often each runs, and how each reaches the user](https://github.com/nedschorus/nedschorus/issues/1058).

The skill asks the user its design questions as an approval-walk, one question at a time, through the walk-me-through skill, in place of the informal questions walks carry today.

## Two working rules the skill must teach (user-approved 2026-10-05)

The skill must teach these two rules to every agent that writes a design with it:

1. **Write each result into its MD file when the result is produced.** A design, a decision or a finding goes into the MD file it belongs in at the moment it is produced, not at the end of the agent-session. A result that lives only in a conversation is lost to every later agent: the conversation cannot be read or shared as a record, and only files travel when the user forks an agent-session or hands the work to another agent. "Read-only" in this GHI-MD's opening means the skill changes no code; writing the design's own MD files is what the skill produces, so this rule does not conflict with it.
2. **Find a design's weaknesses before presenting it, and label each claim.** Before an agent presents a design or an experiment, it looks for the design's weaknesses and confounds itself and states them up front, and it says which of its claims it verified, which a document states, and which are its own inference. A factual claim about a tool is answered from primary sources, such as the installed program, its GitHub issues or its documentation, never from memory alone. A design that holds only until the user's first question reads to him as made up.

The rules come from the Mac's memory entry `nedschorus-working-conventions.md`, which recorded them as user-rulings of 2026-07-31 and 2026-08-01; its mirrored copy is `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/mac/projects/-Users-el-Projects-nedschorus/memory/nedschorus-working-conventions.md`. The user approved carrying them here, as content this skill must teach, with "y" to item 6 of the approval-walk reconcile-machine-local-claude-files-2026-10-05, whose walk-minutes are at `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/reconcile-machine-local-claude-files-2026-10-05-minutes.md`. He judged that a line in `CLAUDE.md` would not make the rules work and that a skill loaded for design work might, and he asked that they be written out clearly and completely, not condensed. The third rule of that item, that a test states its oracle and its red condition before it is written, belongs to GHI [Candidate skill: write-test-plan — consequence-ranked test plan with observable oracles and traceability (likely FIRST build)](https://github.com/nedschorus/nedschorus/issues/18). Item 5 of the same approval-walk deletes that Mac memory entry once this section is on main; that deletion is not a step of this GHI's next action, and the agent-seat agent-instructions-editor tracks it with the other items of that approval-walk.

The `design-writing` state of GHI [Build the design-to-main state machine: the Python machine, its per-state agent-instructions, and the nine items the design defers to the build](https://github.com/nedschorus/nedschorus/issues/282) takes its agent-instructions from this candidate and from GHI [Candidate skill: define-work — bounded work-definition spec before ambiguous or substantial work](https://github.com/nedschorus/nedschorus/issues/15); the skill is written once and that state uses it, not a second copy.

## Next action

1. Read the 62 designs and their walk-minutes and cold-read-records, and list the questions the user asked or ruled on more than once, with a citation for each; save the list beside this GHI-MD as `docs/issues/17-code-design-questions-the-user-asked-of-past-designs.md`. A script finds the designs (the grep above, rerun, not the count), their walk-minutes and cold-read-records, and the user's turns in them; an agent judges which turns are questions or rulings about the design.
2. Read the Anthropic code-architect agent and other published design guidance, and note what each adds that the list from step 1 lacks.
3. Draft the skill under `.claude/skills/`, its questions to the user run as an approval-walk, and give it the cold-read the cold-read skill requires. Under CLAUDE.md's code-prompt-code rule, code checks the form of each design the skill writes: its required sections are present, its list of the steps that need judgment is not empty, and each file it names exists or is marked new.
4. Point the `design-writing` state of GHI 282 at the skill.
