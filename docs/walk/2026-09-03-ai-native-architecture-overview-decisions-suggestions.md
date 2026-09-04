<!-- provenance: runtime=codex model=gpt-5.6-terra effort=low cell=fast-clarify tier=floor duration_s=72 tokens=33226 target=docs/walk/2026-09-03-ai-native-architecture-overview-decisions-draft.md -->

# Cold-read report: AI-native architecture overview decisions

## 1. What it says

### Title and subject

This is an eleven-item decision walk for rulings left open by the AI-native architecture document that was merged on 2026-09-03. It is organized by decisions rather than the architecture document's sections, and says the underlying document remains unchanged unless a decision changes it.

### Item 1 of 11: Cold-read the document before it governs anything.

The architecture document was merged as unreviewed documentation even though the project normally cold-reads durable documents with four zero-context reviewers. The walk recommends running that grid and a findings-triage walk now, and treating the document as governing only afterwards.

### Item 2 of 11: What agents must read, and where the pointer lives.

Until the unbuilt policy-manifest runner can deliver instructions, the text asks whether the whole architecture document or only section 19 governs, and where agents should be told to read it. It recommends section 19 as governing text, a required-reading line in the seat first prompt, and the rest of the document as reference.

### Item 3 of 11: Reopen the "no master" ruling of 2026-08-13 and adopt the master as designed.

The seat model declined a coordinating agent but explicitly allowed reconsideration when seats could hand work to one another without the user; the architecture's master performs that routine routing and supervision. The walk says the designs do not conflict, because the triggering condition is now the design's core, and recommends adopting the master and recording that reason in the seat model.

### Item 4 of 11: The diagnosis ladder. Two dated texts disagree, and the choice is yours.

The dated agent-loop draft permits up to four fresh machine fix attempts with a broad two-agent diagnosis after three failures, whereas architecture section 8 uses three rounds with only one code fix before cross-artifact diagnosis and then a human decision packet. The walk states their shared safeguards and differing escalation point, makes no recommendation, and offers either retaining the dated ladder or adopting section 8.

### Item 5 of 11: Section 13 replaces "code is master after round 1". Confirm it, and the parked walk re-plans under it.

The prior outline made code authoritative after the first pull-request round, while section 13 makes accepted artifacts immutable versions and routes mismatches through reconciliation rather than correcting design toward code. The walk recommends making section 13 govern and then re-planning the parked code/design walk: closing one item and recasting three others as reconciliation questions.

### Item 6 of 11: Reviewer scope in the interim lane. One sentence to pin.

Architecture section 7 permits reviewers to identify neighboring-artifact causes, but the current pull-request rule excludes prose findings because prior prose review caused repeated churn. The walk recommends routing suspected causes only to the future master and retaining the existing pull-request rule until that master exists.

### Item 7 of 11: The one reference the guard held back: the ghi-write skill, line 36.

Pull request #248 updated seventeen references to the retired founding plan, but an instruction-file guard held back the remaining reference in a skill. The walk says the proposed replacement architecture section contains the same routing material, and recommends approving the one-path change followed by the stated guarded pull-request and review process.

### Item 8 of 11: Four rules the architecture document dropped. Still rules, and where do they live?

Four rules formerly associated with standing decisions are absent from architecture section 19: the draft label, legacy-import trailer, handoff scrub, and check-in terminology. The walk recommends retaining and adding the label and terminology rules, pointing the checkpoint vocabulary to the gatekeeper design, and recording the scrub as retired.

### Item 9 of 11: Section 19 as the governing text. Five of its seventeen decisions are new.

Section 19 has seventeen standing decisions, twelve described as restatements of existing rulings and five described as new: input inspection and promotion stopping, broad diagnosis with narrow changes, a logically persistent master, production evidence returning to the graph, and observability in design and testing. The walk recommends confirming the section as written, subject to changes made by items 3, 4, and 8.

### Item 10 of 11: The build order. Which step starts, and under what issue.

The architecture's twelve-step build order has its third step already represented by items 3 and 4, its fourth as unbuilt issue #41, and its first two without issues. The walk says step 1 must begin because later work needs its vocabulary and schemas, and recommends filing it with a pair document while leaving ownership to the user.

### Item 11 of 11: Where each ruling lands.

The walk assigns the outputs of its decisions to cold-read records and a triage walk, specified instruction or architecture edits and pull requests, revised parked-walk minutes, a guard marker and one-line pull request, and a GitHub issue with pair document. It says deferred matters remain open in minutes and this seat's task list, and recommends confirming the capture list.

## 2. Where you stumbled

1. [question] "the eleven decisions that [NedsChorus: AI-Native Software Development with Natural-Language Human Oversight](https://github.com/nedschorus/nedschorus/blob/main/docs/cross-project/nedschorus-ai-native-software-development.md) ... leaves open" — Where is the referenced architecture document available to a zero-context reader when its stated checkout path is absent?

2. [question] "the cold-read grid" — What is the cold-read grid, including how it is run, who its four reviewers are, and where its records are kept?

3. [question] "line 3 of the doctrine pile's instructions" — Which file is the doctrine pile's instructions, and what exact line is being relied upon?

4. [question] "section 19" — What are the seventeen standing decisions in section 19 for a reader who cannot reach the linked architecture document?

5. [question] "the seat first prompt" — What file is the seat first prompt, and how is the proposed required-reading line delivered to every seat?

6. [question] "the parked walk on the code/design mismatch" — Which walk is this, and where are its items 2, 4, 5, and 7 and task 56 recorded?

7. [question] "the ghi-write skill, line 36" — Where is this skill and its line 36, so the retained reference can be identified?

8. [question] "the guard's marker" — What marker is meant, where is it, and what makes it authorize the later edit?

9. [question] "one pull request from this seat, opened as ned-review-merge" — What does `ned-review-merge` designate, and how does an independent reviewer get selected?

10. [question] "the cold-read records" — Where are cold-read records located and what makes a report part of them?

11. [question] "its minutes" — Which minutes record the parked walk, and where is this seat's task list?

## 3. What it does not cover

1. [no-rule] "treat it as governing only after that" — If item 1 is deferred or disapproved, what text governs agents in the meantime?

2. [rule-conflict] "section 19 is the governing text" / "treat it as governing only after that" — If item 2 is approved before item 1's cold read and triage complete, which instruction controls whether section 19 governs?

3. [no-rule] "until the runner exists" — What changes the required-reading arrangement once the policy-manifest runner exists?

4. [no-rule] "A or B, or D to defer" — What policy governs the diagnosis ladder if the user gives N rather than A, B, or D?

5. [rule-conflict] "section 19 ... as written plus whatever items 3, 4 and 8 add" / "No recommendation" — If item 9 is approved while item 4 is deferred, which diagnosis-ladder decision is part of the governing section?

6. [no-rule] "until the master exists, the pull-request reviewer rule stands unchanged" — Once the master exists, what rule determines whether and how a pull-request reviewer reports a suspected upstream cause?

7. [no-rule] "Y to approve the four together, name any one to handle differently" — If more than one of the four rules needs a different disposition, how is the combined decision recorded?

8. [no-rule] "assign an owner when you choose one" — If step 1 is filed without an owner, what event or process assigns it and prevents it from remaining unowned?

9. [no-rule] "Anything deferred stays open in the minutes and on this seat's task list" — How are deferred items revisited, and what closes or removes them from those two records?
