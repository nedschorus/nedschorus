# Walk: the decisions the AI-native architecture document leaves open

The subject: the eleven decisions that [NedsChorus: AI-Native Software Development with Natural-Language Human Oversight](https://github.com/nedschorus/nedschorus/blob/main/docs/cross-project/nedschorus-ai-native-software-development.md), merged to main on 2026-09-03, leaves open, ruled here so the document can govern every agent. Eleven items. This is a decisions walk, not a section walk: the document is your own thinking and stays as written unless an item changes it. Say so if you want the section-by-section shape instead.

---

## Item 1 of 11: Cold-read the document before it governs anything.

The document is ten thousand words of lasting value, written by Codex from your direction, and it reached main as documentation, which the pull-request lane does not review. The project's own instrument for a document of lasting value is the cold-read grid: four zero-context reviewers report what each sentence made them think it meant and what defects they found. It is normally the last step before such a document lands. This one landed without it.

What skipping costs. Every agent that reads the document as governing text inherits any sentence that reads two ways, and there is no second reader to catch it: the pull-request reviewers said nothing about the prose because the reviewer rule tells them not to. What running costs: one grid run, four reports, and a triage walk of the findings. For comparison, the walk-me-through skill rewrite drew fifteen triage items from four cold reads and was better for it.

**Recommendation: run the cold-read grid on the document now, triage the findings in a walk, and treat it as governing only after that.** Y to approve, N to disapprove, D to defer.

---

## Item 2 of 11: What agents must read, and where the pointer lives.

Today one place tells an agent to read the document: line 3 of the doctrine pile's instructions, which says to read the seat model and then the architecture. The root instruction file does not name it. Every seat reads its own brief at launch, and briefs name their own reading. The document itself says in section 11 that instructions are delivered, not discovered, by a runner that assembles a policy manifest. That runner is not built.

So until the runner exists, two questions. Which part is the governing text: the whole document, or section 19, Standing decisions, on its own? And where does the pointer live?

Section 19 is seventeen numbered sentences, readable in a minute, and the document calls it "the present architectural decisions established by the human direction behind this document". The other twenty-one sections are rationale, research, and plan. Asking every agent to read ten thousand words before acting is the reading load you have ruled against before.

For the pointer, the candidate homes are the root instruction file, which you have called a poor home for rules, and the seat first prompt, which every seat reads at launch and which already tells a seat what to read before its first action.

**Recommendation: section 19 is the governing text; the seat first prompt gains one line naming it as required reading, and the rest of the document is reference. That edit is operative prose, so your Y here is its walk.** Y to approve, N to disapprove, D to defer.

---

## Item 3 of 11: Reopen the "no master" ruling of 2026-08-13 and adopt the master as designed.

The seat model, [section Why there is no master agent](https://github.com/nedschorus/nedschorus/blob/main/docs/agents/agent-seat-model.md), ruled on 2026-08-13: "A coordinating seat has nothing to do while the user chooses which seats run, and the evidence is choirmaster itself: created to direct, it drifted into being an ordinary topic thread. Revisit if seats ever need to hand work to each other without the user in the loop — which today they cannot."

The document, [section 10](https://github.com/nedschorus/nedschorus/blob/main/docs/cross-project/nedschorus-ai-native-software-development.md#10-the-master-and-the-human-conversation), makes nodes communicate through one persistent logical master: a router and supervisor that tracks work items, builds input packages, starts and restarts node executions, and carries the one human conversation. It is "not the smartest agent", and it restarts from durable state rather than living as one immortal session. Section 15 says: reopen explicitly, and record why the earlier decision changed.

The two do not contradict each other. The 2026-08-13 ruling named its own revisit condition, seats handing work to each other without you in the loop, and that condition is exactly what the master does for routine transitions. What has changed is the design, not today's fleet, which still has no such channel.

**Recommendation: reopen and adopt the master as section 10 designs it, and record the reason in the seat model in one paragraph: the revisit condition named on 2026-08-13 is now the design's core, and the master is a router, not a smarter agent.** Y to approve, N to disapprove, D to defer.

---

## Item 4 of 11: The diagnosis ladder. Two dated texts disagree, and the choice is yours.

The agent-loop draft, [rule 1](https://github.com/nedschorus/nedschorus/blob/main/docs/wiki/queue/agent-loop-rules-draft.md), is marked user-ruled 2026-07-31 and says it superseded "the earlier three-round form". Its ladder: at most four machine attempts, each by a fresh fixer, never the writer or the reviewer. Attempt one gets the design, the code, and the failing evidence. Attempts two and three get the earlier notes as well. After three failures a two-agent team diagnoses everything as suspect and directs one final attempt. Then you. The tree is reverted between attempts, and the counter is kept by the quality gate, outside the loop.

The document, [section 8](https://github.com/nedschorus/nedschorus/blob/main/docs/cross-project/nedschorus-ai-native-software-development.md#8-test-failure-policy), recommends three rounds: reproduce and classify; round one, one code fix verified by a regression witness; round two, cross-artifact diagnosis before any further edit; round three, a decision packet to you. It calls this "the simpler and safer default" and asks that the two texts be reconciled before implementation.

Where they agree: the counter lives outside the agent, fixers are fresh, and non-convergence goes to you. Where they differ: the draft allows three code attempts before widening the frame, the document allows one. The document argues from research; the draft is a ruling you made, with a date.

**No recommendation. I will not propose overturning a dated ruling on the document's argument alone. Two options: A, keep the 2026-07-31 ladder and edit section 8 to match it; B, adopt section 8's three rounds and edit the draft.** Answer A or B, or D to defer.

---

## Item 5 of 11: Section 13 replaces "code is master after round 1". Confirm it, and the parked walk re-plans under it.

Your outline of 2026-09-02, recorded in the parked walk on the code/design mismatch: the design is master until the first pull-request round, after that the code is master, and the design is corrected toward the code at maintenance.

The document, [section 13](https://github.com/nedschorus/nedschorus/blob/main/docs/cross-project/nedschorus-ai-native-software-development.md#13-provenance-invalidation-and-parallel-work), says something different. Accepted artifacts are immutable. A correction creates a new version, linked to what it derived from and what it supersedes. Descendants of the old version are marked stale, and a reconciliation node decides whether the code, plans and tests remain valid, need review, or must be recreated. Nothing is corrected toward the code; a mismatch is a defect routed to whichever artifact is wrong, and that artifact gets a new version. Section 15 keeps issue 219's built, in-process, planned map, but as "documentation support, not the runtime workflow engine".

Consequence for the parked walk: its items 2, 4, 5 and 7 rest on the outline, not on section 13. Under section 13, the round-one design-match step stays, because section 6 requires every node to inspect its inputs; the retrofit agent in task 56 becomes the reconciliation node; and "weekly or per merge" becomes the question of when reconciliation runs.

**Recommendation: confirm that section 13 governs. I then re-plan the parked walk under it: item 2 closes as superseded, and items 4, 5 and 7 are rewritten as reconciliation questions.** Y to approve, N to disapprove, D to defer.

---

## Item 6 of 11: Reviewer scope in the interim lane. One sentence to pin.

The document, [section 7](https://github.com/nedschorus/nedschorus/blob/main/docs/cross-project/nedschorus-ai-native-software-development.md#7-review-and-root-cause-routing), lets a reviewer "inspect relevant neighboring artifacts and name an actionable suspected cause", and says "the master routes the recommendation; cross-node ambiguity goes to the human".

The rule every pull-request reviewer obeys today, [docs/agents/pr-reviewer-instructions.md](https://github.com/nedschorus/nedschorus/blob/main/docs/agents/pr-reviewer-instructions.md), ruled 2026-08-30: code blocks; operative prose is not reported on; all other prose is silent. The measured reason: one pull request that deleted one file drew four review rounds over five hours, every blocking finding about prose, and two of the three were errors the previous round's own fix had created.

The tension: a suspected upstream cause posted as a pull-request finding is a prose finding under another name, and it reopens that divergence. Section 7 is right that the cause should be found. It is right only if the finding goes to the master, which does not exist yet.

**Recommendation: add one sentence to section 7. A suspected cause found during review is routed to the master and is never posted as a pull-request finding; until the master exists, the pull-request reviewer rule stands unchanged.** Y to approve, N to disapprove, D to defer.

---

## Item 7 of 11: The one reference the guard held back: the ghi-write skill, line 36.

Pull request #248 repointed seventeen files from the retired founding plan to the architecture document. The eighteenth reference is in an operative skill, and the instruction-file guard refused my edit, as it should: instruction files change only through your walk. This item is that walk.

The line is the skill's note on where its machinery and its doctrine are specified. Only the path changes.

Old: the routing doctrine (queues, homes, the drain) is `docs/cross-project/nedschorus-founding-plan.md` § Project organization.

New: the routing doctrine (queues, homes, the drain) is `docs/cross-project/nedschorus-ai-native-software-development.md` § Project organization.

Section 20 of the architecture document is titled Project organization and carries the queues, the homes and the drain, so the new target holds what the old one held.

**Recommendation: approve the path change. On your Y, I quote your approval into the guard's marker, make the edit on a branch from main, open it as ned-review-merge with a fresh independent reviewer, and merge.** Y to approve, N to disapprove, D to defer.

---

## Item 8 of 11: Four rules the architecture document dropped. Still rules, and where do they live?

The project vocabulary page, [docs/wiki/queue/213-project-vocabulary.md](https://github.com/nedschorus/nedschorus/blob/main/docs/wiki/queue/213-project-vocabulary.md), a queue page you have not drained, named the founding plan's Standing decisions as the home of four rules. Section 19 of the architecture document does not state them. Pull request #248 gave each the git-history pointer rather than inventing a home.

1. **The `draft` label.** Issues labeled draft are your review queue in the issue world. Section 20 names the queues but not this label.
2. **The entry checkpoint.** Every import from the legacy system writes a `Gatekeeper-import` trailer in the importing commit. The gatekeeper design already specifies the mechanism.
3. **The handoff scrub.** The queue-depth report at handoff. The vocabulary page itself records this as retired by the gatekeeper design and moved onto the ignition prompt by the fast-handoff design.
4. **The check-in terminology ruling.** "Check-in" replaces the retired "land" and "landing".

**Recommendation, one disposition for the four:** the label and the check-in terminology are still rules and gain one sentence each in section 19; the entry checkpoint's home is the gatekeeper design, so its vocabulary entry points there; the scrub is retired, its entry says so, and the conflict note closes. Y to approve the four together, name any one to handle differently, or D to defer.

---

## Item 9 of 11: Section 19 as the governing text. Five of its seventeen decisions are new.

[Section 19](https://github.com/nedschorus/nedschorus/blob/main/docs/cross-project/nedschorus-ai-native-software-development.md#19-standing-decisions) lists seventeen standing decisions. Twelve restate rulings already in force in this project: one gate to main, complexity earned, behavior in code where it can be, durable artifacts for an independent reader, the legacy rewrite policy, public sources judged by usefulness, the human directs and works in natural language, bounded executions, a simple workflow, optimistic parallel work, and creation alternating with review.

Five are new relative to any ruling on record, and they are the ones this walk's other items turn on:

- **4.** Every node examines its inputs before producing output; a material upstream defect stops promotion; a safe nit is repaired and recorded locally.
- **6.** Diagnosis may look broadly but may change narrowly.
- **7.** The master is logically persistent, not process-immortal.
- **10.** Production returns evidence to the graph.
- **11.** Observability is part of design and testing.

Items 3, 4 and 8 of this walk may add or change sentences in this section. Beyond those, the question is whether the section stands as written.

**Recommendation: confirm section 19 as the governing standing decisions, as written plus whatever items 3, 4 and 8 add, or name one decision to change.** Y to approve, N to disapprove, D to defer.

---

## Item 10 of 11: The build order. Which step starts, and under what issue.

[Section 18](https://github.com/nedschorus/nedschorus/blob/main/docs/cross-project/nedschorus-ai-native-software-development.md#18-recommended-build-order) lists twelve steps. Step 3, resolve the two policy conflicts, is items 3 and 4 of this walk, so it is already in motion. Step 4 is issue #41, the run-agent runner, which has an issue and no build yet. Steps 1 and 2 have neither: the vocabulary, provenance fields and result schema, and the policy-manifest resolution that delivers instructions mechanically.

Step 1 is where the document says to begin, and it is documentation with a small amount of code: define work item, node execution, artifact version, attestation, the outcome dimensions and the decision packet, adapting the gatekeeper's existing response shape rather than inventing a new one. Nothing else in the plan can be built against an undefined schema.

Who owns it is your call, not mine. The merge lane stays on merges.

**Recommendation: file step 1 as a GitHub issue with a pair document, through the ghi-write skill, now, and assign an owner when you choose one.** Y to approve, N to disapprove, D to defer.

---

## Item 11 of 11: Where each ruling lands.

The captures this walk produces, so nothing lives only in the conversation:

- **Item 1:** a cold-read grid run on the document, its reports under the cold-read records, and a triage walk.
- **Item 2:** one line in the seat first prompt naming section 19 as required reading; operative prose, approved by this walk.
- **Items 3, 4, 6, 8 and 9:** edits to the architecture document and, for item 3, one paragraph in the seat model; one pull request from this seat, opened as ned-review-merge, independently reviewed.
- **Item 5:** the parked code/design walk re-planned under section 13, recorded in its minutes.
- **Item 7:** the guard's marker with your words, then a one-line pull request.
- **Item 10:** a GitHub issue and pair document for build step 1.

Anything deferred stays open in the minutes and on this seat's task list.

**Recommendation: confirm this capture list.** Y to approve, N to disapprove, D to defer.
