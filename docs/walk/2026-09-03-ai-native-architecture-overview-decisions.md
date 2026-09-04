# Walk: the decisions the AI-native architecture document leaves open

The subject: the decisions that [NedsChorus: AI-Native Software Development with Natural-Language Human Oversight](https://github.com/nedschorus/nedschorus/blob/main/docs/cross-project/nedschorus-ai-native-software-development.md), merged to main on 2026-09-03, leaves open, ruled here so its mission can govern every agent. Eight items after the re-plan at item 2 (eleven before it). This is a decisions walk, not a section walk: the document is your own thinking and stays as written unless an item changes it. Until the items are ruled, nothing in the document governs an agent beyond the rulings already in force.

Items 1 and 2 are ruled; their text is in the minutes. In short: the cold read runs after this walk, on the edited text; the document is the project's mission, not a plan; CLAUDE.md carries the mission (the central rule, sections 19, 20 and 21) plus a paragraph naming the notes file and the channel for questions; everything else becomes a not-prescriptive, not-vetted notes file; a dedicated objective seat fields complaints.

---

## Item 3 of 8: Reopen the "no master" ruling of 2026-08-13 and adopt the master as designed.

The seat model, [docs/agents/agent-seat-model.md, section Why there is no master agent](https://github.com/nedschorus/nedschorus/blob/main/docs/agents/agent-seat-model.md), ruled on 2026-08-13: "A coordinating seat has nothing to do while the user chooses which seats run, and the evidence is choirmaster itself: created to direct, it drifted into being an ordinary topic thread. Revisit if seats ever need to hand work to each other without the user in the loop — which today they cannot."

The mission's standing decision 7 says: "The master is logically persistent, not process-immortal. Nodes communicate through the master; the master communicates with the human." That sentence goes into CLAUDE.md under item 2, so the conflict is real and cannot be left to the notes. The notes' section 10 describes the master as a router and supervisor that tracks work items, builds input packages, starts and restarts node executions, and carries the one human conversation; "not the smartest agent", restarting from durable state rather than living as one immortal session.

The two rulings do not contradict each other. The 2026-08-13 ruling named its own revisit condition, seats handing work to each other without you in the loop, and that condition is exactly what the master does for routine transitions. It is also the channel you named at item 2: the single agent through which every agent you are not directing reaches you. What has changed is the design, not today's fleet, which still has no such channel.

**Recommendation: reopen and adopt the master as standing decision 7 states it, and record the reason in the seat model in one paragraph: the revisit condition named on 2026-08-13 is now the mission's core, the master is a router and the user's channel, not a smarter agent.** Y to approve, N to disapprove, D to defer.

---

## Item 4 of 8: The one reference the guard held back: the ghi-write skill, line 36.

Pull request #248 repointed seventeen files from the retired founding plan to the architecture document. The eighteenth reference is in an operative skill, [.claude/skills/ghi-write/SKILL.md](https://github.com/nedschorus/nedschorus/blob/main/.claude/skills/ghi-write/SKILL.md), line 36, and the instruction-file guard, the hook that refuses edits to instruction files unless your approval words sit in a `.walk-approved` marker at the checkout root, refused my edit, as it should. This item is that walk.

The line is the skill's note on where its machinery and its doctrine are specified. Only the path changes, and after item 2 the target is CLAUDE.md, where section 20 now lives.

Old: the routing doctrine (queues, homes, the drain) is `docs/cross-project/nedschorus-founding-plan.md` § Project organization.

New: the routing doctrine (queues, homes, the drain) is `CLAUDE.md` § Project organization.

**Recommendation: approve the path change. It lands inside the split pull request from item 2, with your Y quoted into the marker for that one edit.** Y to approve, N to disapprove, D to defer.

---

## Item 5 of 8: Four rules the architecture document dropped. Still rules, and where do they live?

The project vocabulary page, [docs/wiki/queue/213-project-vocabulary.md](https://github.com/nedschorus/nedschorus/blob/main/docs/wiki/queue/213-project-vocabulary.md), a queue page you have not drained, named the founding plan's Standing decisions as the home of four rules. Section 19 of the architecture document does not state them. Pull request #248 gave each the git-history pointer rather than inventing a home.

1. **The `draft` label.** Issues labeled draft are your review queue in the issue world. Section 20 names the queues but not this label, and item 2 just made the label the channel for every agent you are not directing.
2. **The entry checkpoint.** Every import from the legacy system writes a `Gatekeeper-import` trailer in the importing commit. The gatekeeper design already specifies the mechanism.
3. **The handoff scrub.** The queue-depth report at handoff. The vocabulary page itself records this as retired by the gatekeeper design and moved onto the ignition prompt by the fast-handoff design.
4. **The check-in terminology ruling.** "Check-in" replaces the retired "land" and "landing".

**Recommendation, one disposition for the four:** the label and the check-in terminology are still rules and gain one sentence each in the mission's standing decisions in CLAUDE.md; the entry checkpoint's home is the gatekeeper design, so its vocabulary entry points there; the scrub is retired, its entry says so, and the conflict note closes. Y to approve the four together, or name the ones to handle differently and each becomes its own item at the end of this walk, or D to defer.

---

## Item 6 of 8: The seventeen standing decisions, confirmed as written before they enter CLAUDE.md.

[Section 19](https://github.com/nedschorus/nedschorus/blob/main/docs/cross-project/nedschorus-ai-native-software-development.md#19-standing-decisions) lists seventeen standing decisions, and item 2 moves them verbatim into CLAUDE.md, where every agent reads them on every launch. Twelve restate rulings already in force in this project: one gate to main, complexity earned, behavior in code where it can be, durable artifacts for an independent reader, the legacy rewrite policy, public sources judged by usefulness, the human directs and works in natural language, bounded executions, a simple workflow, optimistic parallel work, and creation alternating with review.

Five are new relative to any ruling on record:

- **4.** Every node examines its inputs before producing output; a material upstream defect stops promotion; a safe nit is repaired and recorded locally.
- **6.** Diagnosis may look broadly but may change narrowly.
- **7.** The master is logically persistent, not process-immortal.
- **10.** Production returns evidence to the graph.
- **11.** Observability is part of design and testing.

Items 3 and 5 of this walk add or change sentences here. Beyond those, the question is whether the seventeen stand as written, because once in CLAUDE.md a sentence that reads two ways is read two ways by every agent.

**Recommendation: confirm the seventeen as written, plus whatever items 3 and 5 add, or name one to change.** Y to approve, N to disapprove, D to defer.

---

## Item 7 of 8: Build step 1, promoted from the notes into the cycle as an issue.

The notes' [section 18](https://github.com/nedschorus/nedschorus/blob/main/docs/cross-project/nedschorus-ai-native-software-development.md#18-recommended-build-order) lists twelve build steps. Step 3, resolve the two policy conflicts, is item 3 of this walk and the ladder question now held under issue #21. Step 4 is issue #41, the run-agent runner, which has an issue and no build yet. Steps 1 and 2 have neither: the vocabulary, provenance fields and result schema, and the policy-manifest resolution that delivers instructions mechanically.

Step 1 is where the notes say to begin, and it is documentation with a small amount of code: define work item, node execution, artifact version, attestation, the outcome dimensions and the decision packet, adapting the gatekeeper's existing response shape rather than inventing a new one. Nothing else in the plan can be built against an undefined schema.

This is exactly the promotion you called dangerous at item 2: a note moving into the built, in-process, planned cycle. It is safe only because you rule it here, and it enters as planned, the cycle's own word. Who owns it is your call, not mine; the merge lane stays on merges, and an unowned issue is visible on the issue list and in the next fleet handoff.

**Recommendation: file step 1 as a GitHub issue with a pair document, through the ghi-write skill, now, and assign an owner when you choose one.** Y to approve, N to disapprove, D to defer.

---

## Item 8 of 8: Where each ruling lands.

The captures this walk produces, so nothing lives only in the conversation:

- **Item 1:** after this walk and the split, a cold-read grid run on CLAUDE.md's mission section and the notes file, reports under `cold-read-records/`, then a triage walk.
- **Item 2:** the split pull request from this seat, opened as ned-review-merge: the mission into CLAUDE.md with the channel paragraph, the notes file with its front matter, the old file deleted, the twenty citations repointed; plus two tasks, the objective seat's brief and the communication SOP.
- **Item 3:** one paragraph in the seat model, in the same pull request.
- **Item 4:** the skill line, in the same pull request, with your approval words in the guard's marker.
- **Item 5:** two sentences in the mission's standing decisions and two vocabulary entries, in the same pull request.
- **Item 6:** any changed standing decision, in the same pull request.
- **Item 7:** a GitHub issue and pair document for build step 1.
- **The parked code/design walk:** resumes after this one, re-planned under standing decisions 4 and 5.

Anything deferred stays open in this walk's minutes and as a task on this seat's task list, titled as the question; a deferred item is revisited when you next take this walk up, and closes when you rule it or declare it moot.

**Recommendation: confirm this capture list.** Y to approve, N to disapprove, D to defer.
