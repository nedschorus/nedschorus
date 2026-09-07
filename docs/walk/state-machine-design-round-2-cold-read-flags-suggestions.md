<!-- provenance: runtime=codex model=gpt-5.6-terra effort=low cell=fast-clarify tier=floor duration_s=74 tokens=33481 target=docs/walk/state-machine-design-round-2-cold-read-flags-draft.md -->

# Cold read: state-machine design, round 2 flags

## 1. What it says

### Opening and links

The revised state-machine design received 347 cold-read findings, most of which were applied; twelve resulting changes and three unresolved questions are presented for the user's decisions. The linked design is the subject under discussion, while the not-applied record is machine-local.

### Item 1 of 8: 347 findings, up from 236 — and what the reviewers could not see

Finding counts rose in every review cell, largely because the rewrite added substantive machinery that reviewers could assess, with about 150 findings remaining after deduplication. Reviewers did not receive the user's settled rulings and could not access two pages on unpushed branches, so they re-raised decisions and reported those pages missing; neither requires a decision here.

### Item 2 of 8: A loop-in pauses the run; every design rejection is a conversation with you

A loop-in pauses, rather than ends, a component run and lets the user decide where it resumes or whether it stops. Design rejection enters a design-focused loop-in and a return to the design node is a redesign; after the third redesign the component is stopped, and the two terminal states are submit-to-gate and stopped.

### Item 3 of 8: The build ceiling loops you in, and a rebuild after a corrected contract is a build

The build ceiling must loop the user in rather than route to the arbitrator, including when an arbitrator's ruling would otherwise send an at-ceiling writer back to work. Rewriting a contract does not itself use build budget, but an implementation rebuild caused by it does; prose-only contract exchanges remain free and two contract corrections can cause at most two such builds before the user sees the problem.

### Item 4 of 8: Three routes the machine lacked — a rejected submission, a suite that cannot run, an illegal destination

A rejected gate submission now loops the user in with the gate findings, because it shows that the workflow's review missed something. A suite that cannot run retries once and then loops in, while a destination outside the transition table is a machine error that also loops in.

### Item 5 of 8: Two rulings I dropped, restored

The test-design now receives a user-review state, matching the design's review, because the user reviews both kinds of final prose. State names now retain the user-supplied `-node` suffix.

### Item 6 of 8: A corrected contract invalidates both lines; the arbitrator has a status mode; nit repair is a departure

Re-emitting a corrected contract resets both implementation and test progress, requiring an implementation rebuild and, once testing has started, a newly derived test design. An arbitrator invoked by the user pauses the run, receives branch history only, provides an answer or status report without routing, records any ruling, and then permits resumption; local nit repair is explicitly a departure from an earlier decision.

### Item 7 of 8: Three questions that are yours, held open in the design

The design leaves open whether prompt implementations require cold reads, what an excluded implementation is and how it is handled, and how to bound the contract's observable behavior. The recommendation is to keep all three open in section 11 unless the user chooses to rule on them now.

### Item 8 of 8: What was not applied, and the next step

Sixteen findings were deliberately not applied for recorded reasons, including deferrals, open questions, inaccessible citations, and ruled names. After the user rules on items 2 through 7, the design should receive a third cold read and then be paired with build step 1's issue; until the cold-read instrument accepts rulings, it will keep re-raising that class of finding.

## 2. Where you stumbled

1. [question] "Say next." What response or action does this request require?

2. [question] "Your ruling in item 6.2 of the last walk" Which last walk and ruling is this referring to?

3. [question] "The arbitrator's one trigger is a red suite (your 6.3)" What source defines "your 6.3" and the arbitrator's trigger?

4. [question] "decision 4's second half" Which decision is this, and what is its second half?

5. [question] "§11" Which document's section 11 contains the three questions to remain open?

6. [question] "the cells still cannot see your rulings" What are the cells and how are they used in the proposed third cold read?

## 3. What it does not cover

1. [no-rule] "Recommendation: adopt that as stated. Y, N, or D." What happens to the design when the answer is N or D?

2. [no-rule] "Recommendation: adopt all three. Y, N, or D." How should the user respond when they accept some, but not all, of the three routes?

3. [no-rule] "Recommendation: confirm both restorations. Y, N, or D." How should the user respond when they confirm one restoration but not the other?

4. [no-rule] "Recommendation: adopt all three. Y, N, or D." How should the user respond when they adopt only some of the three changes in this item?

5. [rule-conflict] "A prompt implementation is both. Which wins is yours." Which rule governs a prompt-typed implementation when the cold-read rule and the implementation-review rule both apply?

6. [no-rule] "Recommendation: rule items 2–7, then a third cold read. Y, N, or D." What is the next step if the user answers N or D to this recommendation?
