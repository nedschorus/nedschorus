---
issue: "[Implementing the project's goals and philosophy: every finding sorted into four categories, checked claims kept with their evidence, and one standard in every agent's instructions](https://github.com/nedschorus/nedschorus/issues/2522)"
---

# Implementing the project's goals and philosophy: every finding sorted into four categories, checked claims kept with their evidence, and one standard in every agent's instructions

**Priority: prioritized.** The user asked that this work be a prioritized GHI and task, because it will change approval-walks, reviews, testing, maintenance and design-to-main.

## Why

On 2026-11-03, about 21:20Z, the user gave merge-lane-2 a statement of the project's philosophy, which is the founding statement of the page `docs/nedschorus-wiki/queue/nedschorus-goals-and-philosophy-founding-statement-and-agent-working-principles.md`, planned by GHI [A wiki page of the project's goals and philosophies: how agents work with the user, and how they build and finish work](https://github.com/nedschorus/nedschorus/issues/2411). merge-lane-2 recorded his words whole in the bullet dated 2026-11-03 ~21:20Z of its walk-minutes `nedlern@ned-box:/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-open-rulings-2026-10-30-minutes.md`, which are in merge-lane-2's agent-home while that approval-walk is open and go to `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/` when it closes. The statement ends: "These principles should live in a maintained Project Goals and Philosophy document, with concise operational guidance in CLAUDE.md and equivalent instructions for other agents. All named, long lived agents should work from the same standards for evidence, progression, and deferred work. Implementing this philosophy should be a prioritized issue and task because it will shape walkthroughs, reviews, testing, maintenance, and the broader design-to-main lifecycle."

That GHI is the page that states the philosophy. This GHI is the work that makes the project follow it. ghi-guide-agent, asked on 2026-11-03 which GHI should carry that work, recommended a new GHI: the page's GHI is a wiki page, and GHI [Pull requests, their reviews and approval-walks held as one state machine over one schema and one store, so code tracks their state and agents are handed only the steps that need judgment](https://github.com/nedschorus/nedschorus/issues/2505) covers pull requests, reviews and approval-walks only.

## What is wanted

1. **Four categories for every finding.** Every place that produces findings, such as a pull request review, a cold-read triage, an overview claim check, a sanity-check triage or an approval-walk, puts each finding in one of the four categories the statement lists: must fix before proceeding; fix in the next appropriate pull request or approval-walk; fix during regular maintenance; or defer, filed as a task for smaller or shorter work or as a GHI for larger or longer work, with a reason for deferral, a follow-up, its precursors and what it enables. Only the first category holds the work back. No finding is left without a category, so an accepted imperfection is never forgotten.
2. **Checked claims kept.** Once a claim has been checked and supported, its conclusion, its evidence and the conditions under which it stays valid are kept, and the claim is reopened only when relevant inputs change, an assumption fails or contradictory evidence appears. Code is still retested on every change.
3. **One standard in every agent's instructions.** `CLAUDE.md` gets the concise operational guidance, which the user approves in the approval-walk that puts the page to him, and the seat-briefs and every `-instructions.md` file under `docs/agents/`, its `queue/` included, get the equivalent, so every named, long-lived agent works from the same standards for evidence, progression and deferred work. No seat-brief or `docs/agents/` file is changed before that guidance is approved.
4. **Encoded where it can be.** Where a rule of the above can be expressed reliably in code, a schema, a state machine or a test, it is, as the statement and `CLAUDE.md`'s bullet that begins "Build code-prompt-code" say. The design of GHI [Pull requests, their reviews and approval-walks held as one state machine over one schema and one store, so code tracks their state and agents are handed only the steps that need judgment](https://github.com/nedschorus/nedschorus/issues/2505) is the enforcement path for pull requests, reviews and approval-walks: its schema gives each finding its category and records which claims each round checked, and its state machine files each deferred finding as a task. The other places that produce findings, such as the cold-read triage, the overview claim check and the sanity-check triage, write their findings through the same record, so one schema holds the category and the deferral fields everywhere.

## Where the project already encodes stages of findings

Surveyed on 2026-11-03 against origin/main `add3a7bbf`. "Agrees" means the place already does what the statement asks; "partly agrees" and "diverges" name the gap.

### The objective page and fleet-restart-at-login's proposed standing decisions

- Standing decisions 27 and 28 are not on `docs/nedschorus-wiki/nedschorus-ai-native-software-development-objective.md`. They were texts proposed in item 18.3.2 of fleet-restart-at-login's approval-walk ghi-972-agent-seat-database-service-design-mac-task-lists-fallback-decision-and-cold-read-findings-approval-walk-2026-10-29, never approved, and overtaken by the user's statement; fleet-restart-at-login's walk-minutes for that item say they go to the page instead (`nedlern@ned-box:/home/nedlern/agents/fleet-restart-at-login/docs/walk/ghi-972-agent-seat-database-service-design-mac-task-lists-fallback-decision-and-cold-read-findings-approval-walk-2026-10-29-minutes.md`, the lines for item 18.3.2). fleet-restart-at-login adds nothing to the objective page.
- Proposed decision 27, a claim not checked again unless its text changes: partly agrees. It reopens a claim only when its text changes; the statement also reopens it when an assumption fails or contradictory evidence appears, and keeps the evidence and conditions with the conclusion.
- Proposed decision 28, three deadlines: partly agrees. It has the first three categories and says only the first holds the work back; it lacks the fourth, deferral filed with a reason, a follow-up, precursors and what it enables.
- Standing decision 5, "A changed output invalidates the old review": agrees; a changed input reopens a claim.
- Standing decision 25, a finding on text the user has already decided is not reported again: agrees, for text he has decided.

### The GHI on pull requests, reviews and approval-walks as one state machine

Agrees in direction: it moves review and approval-walk state into one schema and state machine. Partly agrees in content: its schema marks each finding "blocking or not", two values where the statement has four categories, and it does not yet keep checked claims with their evidence.

### merge-lane-2's approval-walk items 7.1.4.2 to 7.1.4.4

All three are in `nedlern@ned-box:/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-open-rulings-2026-10-30.md` and wait for the user's answer.

- Item 7.1.4.2, three review rounds and a fourth only when one blocking finding is left: partly agrees. It bounds the rounds, so must fix does not run without end, but it does not sort what is left.
- Item 7.1.4.3.2, at the round limit merge-lane-2 merges with follow-ups the author may not decline and keeps a task for each, or asks for the close: agrees; the findings left become the next pull request's, and each stays visible as a task.
- Item 7.1.4.4, a fresh model's read of a message a pull request adds holds the merge only on a misreading: agrees; a misreading is must fix, and a struggle goes to the author as a follow-up.

### Elsewhere in the repository

- `CLAUDE.md`'s -nbd bullet: partly agrees. Its four kinds of blocking finding are the category must fix before proceeding; every other finding "is advice, and does not block", with no category, follow-up or record.
- `CLAUDE.md`'s non-blocking findings and the `#follow_up_request` flow, run by `scripts/pull-request-follow-up-request-after-merge-finding-answers-and-next-step.py`: agrees for fix in the next pull request. Partly agrees for deferral: a finding the author leaves out records a reason, but no task or GHI, follow-up, precursors or what it enables.
- `#root_cause_not_fixed` with its `#follow_up` link, read by `scripts/pull-request-description-defect-line-root-cause-status-and-follow-up-link-reader.py` for `scripts/merge-gate.sh`: agrees; a cause left unfixed names the GHI or pull request that follows it up.
- The overview claim check's ranks must fix, fix later and nit, in PR [overview-write: the claim check ranks flagged claims, and the merge gate blocks only on claims ranked must fix](https://github.com/nedschorus/nedschorus/pull/2506), open, under GHI [overview-write skill: how an overview of a system is written and checked before it lands](https://github.com/nedschorus/nedschorus/issues/168): partly agrees. Must fix blocks, fix later goes to a proposed-improvements-or-changes-file for a follow-up pull request and then to maintenance, but nits are listed in the report only, and there is no deferral category. Its reports, keyed to the overview's exact text, already keep a checked claim's conclusion while that text is unchanged.
- The /cold-read skill's triage, steps 7 to 9 of `.claude/skills/cold-read/SKILL.md`: partly agrees. Findings are applied, deferred, declined or decided by the user; a deferred finding is a line in the design's deferred-decisions, which stays visible, but a declined finding is recorded with its reason and neither scheduled nor filed. GHI [Rebuild the /cold-read skill so its programs do the mechanical steps and print each instruction when the agent needs it](https://github.com/nedschorus/nedschorus/issues/2158) is where its triage would take the categories.
- design-to-main's reviewers, in `docs/design-to-main/design-to-main-state-machine-design.md` and `docs/agents/queue/design-to-main-*-instructions.md`: diverges. A material defect is must fix, but nits are "recorded and never routed", so no nit reaches maintenance.
- The /walk-me-through skill: partly agrees. Its not-asked kinds spare the user some items, but every other item is shown in the same approval-walk whether it blocks work or not. GHI [Approve obvious approval-walk items automatically, by criteria drawn from the user's tracked obvious approvals, after the advisor checks each one](https://github.com/nedschorus/nedschorus/issues/1809) overlaps.
- The glossary's loose-end and maintenance-job: agree. A loose-end is what no task, GHI or pull request holds, which the deferral category forbids; GHI [Regular maintenance: the list of maintenance jobs, how often each runs, and how each reaches the user](https://github.com/nedschorus/nedschorus/issues/1058) plans regular maintenance.

cold-read-improvement's survey `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/cold-read-improvement/staged-completion-survey-2026-11-03.md` ranks these places by how much the change would cut waiting or the user's reading.

## Related work

- GHI [A wiki page of the project's goals and philosophies: how agents work with the user, and how they build and finish work](https://github.com/nedschorus/nedschorus/issues/2411) states the philosophy; this GHI implements it.
- GHI [Pull requests, their reviews and approval-walks held as one state machine over one schema and one store, so code tracks their state and agents are handed only the steps that need judgment](https://github.com/nedschorus/nedschorus/issues/2505) is the enforcement path for pull requests, reviews and approval-walks.
- GHI [overview-write skill: how an overview of a system is written and checked before it lands](https://github.com/nedschorus/nedschorus/issues/168), GHI [Rebuild the /cold-read skill so its programs do the mechanical steps and print each instruction when the agent needs it](https://github.com/nedschorus/nedschorus/issues/2158) and GHI [Approve obvious approval-walk items automatically, by criteria drawn from the user's tracked obvious approvals, after the advisor checks each one](https://github.com/nedschorus/nedschorus/issues/1809) each carry one of the places above.
- GHI [What instructions each kind of agent needs, and where each kind's instructions live](https://github.com/nedschorus/nedschorus/issues/1127) is the design that point 3 builds on.

## Deferred-decisions

- Where a finding in the category fix during regular maintenance is held until maintenance reaches it, settled with the maintenance jobs of GHI [Regular maintenance: the list of maintenance jobs, how often each runs, and how each reaches the user](https://github.com/nedschorus/nedschorus/issues/1058).
- The criteria that separate the categories fix in the next pull request or approval-walk, fix during regular maintenance, and defer, settled from the first findings sorted.
- How a failed assumption or contradictory evidence reopens a kept claim; a changed input can be detected by a hash of the claim's inputs, as the overview claim check keys its reports to the overview's exact text.

## Next action

1. Start on point 4 of "What is wanted" and on the places that partly agree, in programs and skills: the four categories and the conditions for reopening a claim are the user's own words, so they need not wait for the page's approval. The `CLAUDE.md` guidance, and point 3's changes to the seat-briefs and `docs/agents/` files, wait for his approval of the page.
2. For each place above that partly agrees or diverges, file a task, or edit the GHI that already carries the place, to adopt the four categories, in the order of the survey's ranking and then the places it does not rank; a place in a seat-brief or a `docs/agents/` file waits for step 3.
3. After the `CLAUDE.md` guidance merges, bring the seat-briefs and the `-instructions.md` files under `docs/agents/` to the same standards, each change approved as `docs/nedschorus-wiki/nedschorus-which-changes-need-the-users-approval.md` says.
4. Refresh the GHI-MD of the page's GHI to the founding statement: its list of fourteen principles and its proposed `CLAUDE.md` lines are superseded by the page and the guidance its pull request carries.
