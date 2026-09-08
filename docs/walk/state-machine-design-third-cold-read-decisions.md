# Walk: the third cold read of the state-machine design — what was fixed, and seven decisions

The design-to-main state machine turns an approved design into code and tests and submits them to the gate that guards main. Its design had a third cold read today; this walk reports what was fixed and asks the seven decisions that are yours. 9 items. [This walk](file:///Users/el/agents/reboot-test/docs/walk/state-machine-design-third-cold-read-decisions.md).

Y approves an item, N declines it, D defers it to the end of the walk.

[The design](file:///Users/el/agents/reboot-test/docs/design-to-main/design-to-main-state-machine-design.md) — [its glossary](file:///Users/el/agents/reboot-test/docs/design-to-main/design-to-main-glossary.md) — [the dispositions of every finding](file:///Users/el/agents/reboot-test/cold-read-records/2026-09-06-design-to-main-state-machine-design/dispositions.md), machine-local.

---

## Item 1 of 9: What the read found, and what I fixed without asking

Six reviewer agents read the design: four hunting defects, two checking terms. About 500 findings came back, about 60 distinct once the same defect seen six ways was merged. Most were contradictions I wrote today while applying your rulings; I fixed those in a second commit. The commonest:

- **Who does what per state.** My sentence "every other state launches a fresh agent" put the terminal state, your invocation, and the investigation in the wrong bucket. Now each state's work is listed plainly.
- **The test-design was never defined.** It is now: the list of test-requirements, one per promise a test must observe, each with the coverage-type of the test that covers it. That settles where `no-tests` lives: on a test-requirement, not on a test.
- **The write ceiling fired when the third implementation was emitted**, before it was reviewed. Your ruling is the third *failed* write. Fixed; the counters are now guards on the reject exits, not rows of their own.
- **The redesigns counter was charged twice** per redesign, and nothing reset the per-version counters on a redesign. Fixed.
- **Your contract check had no way to say yes.** It now has advance, discuss, or open an investigation, and its moment is fixed: item 5.
- **The first component-contract's form check raced the design review.** Now the script runs first, at once, then the design review reads both files and may reject either.
- **Packages "not a checkout" versus a reviewer that must run code.** Every launched agent now works in a worktree of the topic branch, with the other work-stream's files absent.

Sixteen findings were not applied because you had already ruled what they flagged; the dispositions file cites each ruling. Everything else in this walk needs your word.

No decision. Any of these fixes you may overrule; say which. Otherwise say next.

---

## Item 2 of 9: Your glossary rule applied to the document's own words

You ruled today that no common software-engineering word is redefined and only hyphenated phrases are defined. The document broke that in its own vocabulary section: "exit", "package", "write", "revision", "correction", "line" and "focus" were all given senses of their own as bare words; "nit" was renamed too, and you kept it as the standard word. Both terminology reviewers flagged every one.

I applied your rule, forming each phrase from the word already there so a search still finds it:

| Was | Now |
| --- | --- |
| exit | `state-exit`: the record a state's work emits, a verdict and a destination |
| package | `state-package`: the files one launched agent is told to read |
| standard delivery | `standard-package`: the files every agent after the design gets |
| revision | `contract-revision` |
| correction | `test-design-correction` |
| line | `implementation-work-stream`, `test-work-stream` |
| focus | `investigation-focus` |

Not taken: the reviewers' longer inventions, such as `completed-artifact-authoring-attempt` for a write. Your rule is three or four parts only when a shorter name collides or is ambiguous, and none of these do.

Recommendation: confirm the table. Y, N, or D.

---

## Item 3 of 9: The short words a state emits

A state's work ends with one word the machine routes on: `advance`, `emitted`, `discuss`, `stop`, `resume`, `green`, `red`. One reviewer flagged them as too short to search for: a search for `red` or `stop` finds everything.

They are always written beside the state's name. In a commit on the topic branch the trailer reads `State: implementation-reviewing` on one line and `Exit: advance` on the next, so a search for the pair finds exactly the event, and the words stay readable in a table. Lengthening them, to `state-artifact-emitted` for `emitted`, say, would make every row of the transition table longer for a search that already works.

Recommendation: keep the short words. Y to keep, N to lengthen, or D.

---

## Item 4 of 9: Two words that were not yours, and one that is

- **`unreliable-test`** was my name for a test that gives different results on the same inputs. The standard word is **flaky test**, and CLAUDE.md says to use standard terms. Applied: `flaky-test`.
- **`over-its-head`** was my name for the arbitrator's verdict that neither the component-contract nor the design settles a question. It names the arbitrator's inadequacy, not where the work goes. Applied: `escalate-to-user`.
- **`arbitrator`** is yours: on 2026-09-05 you said "if a judge is an arbitrator, call them that consistently." But [the fleet glossary](file:///Users/el/agents/reboot-test/docs/wiki/nedschorus-glossary.md) already has **adjudicator**, "a fresh agent, used to resolve conflicts between agents," which is the same role, and CLAUDE.md's rule is to use the existing name. Two words for one job across two documents is what a later agent will "fix" in one place and not the other. The word `adjudicator` appears in the whole repository twice: that glossary entry, and one queue draft.

Recommendation: keep `arbitrator` in the design, since you chose it with the whole role in view, and change the fleet glossary's entry to `arbitrator` with `adjudicator` noted as the older word. Y, N to adopt `adjudicator` instead, or D.

---

## Item 5 of 9: Your contract check, settled

### Item 5.1 of 9

Your ruling, [item 5 of the write-counting walk](file:///Users/el/agents/reboot-test/docs/walk/implementation-review-verdicts-and-code-write-counting-minutes.md) on 2026-09-06, was that a corrected contract reaches you only when it has "failed review twice," and you "see both versions before a third is written." The document said that three different ways, and reviewers found they gave three different moments and no way for you to accept.

Settled reading, as applied. Take the component-contract for `create-topic-branch` that you read on 2026-09-04. Its clause said the script exits 0 when it refuses to create the branch. The reviewer rejects it, since 0 means success. A fresh agent writes contract-revision one. The reviewer rejects that too. That is the second failure. The counter is at its ceiling, and the machine does not start a second contract-revision. It shows you the original and contract-revision one, with both reviewers' notes, and waits. You may:

- **advance** contract-revision one as it stands, overruling the reviewer;
- **discuss**, and your ruling goes to a fresh agent that writes the next version from it;
- open an **investigation**, focus `contract`.

No third version is written without you. Say next for the two things you added tonight.

### Item 5.2 of 9

You settled the rest by walking the whole run step by step, and the design now says this.

**Who talks to you.** From your invocation until the code and the tests both exist, one agent, the initiator, which holds the design conversation and stays alive across rejections. From then on, only arbitrators, fresh on each entry, reading everyone's notes and the branch history, because code would overwhelm the initiator. 

**Chances.** The initiator revises alone up to twice when the reviewer rejects the design or the contract, comes to you sooner when unsure, and brings you in at the third. Each work-stream's writer gets three writes by review. The arbitrator rules alone twice per design version, and a write it orders does not spend the writer's three. On its third entry it walks you through its report. A rewrite forced by a changed contract, test-design or design spends that document's counter and nobody else's. Your word `reset` zeroes every counter.

**The contract.** At its second failure the initiator, or an arbitrator once code exists, walks you through both versions. You advance one, rule and a fresh reviser writes from it, or order a redesign. Any agent that thinks the contract is wrong tries twice before that; a problem in the design or the test-design may reach you sooner.

**What you read after the design.** The test-design, an implementation that is a prompt, and prompt-based-tests as a set.

**The pull request.** None exists during a run; no agent the machine launches reads one. `submit-to-PR-gate` writes it from the run's record and it says nothing the design, contract and test-design do not.

Y, N, or D for item 5 entire.

---

## Item 6 of 9: Prompt-based-tests reach you

Ruled during item 5, in your words: "I think I should review tests that are prompts. They are usually both short and important." And, on their number: you review them as a set, reading what you choose. Kept as the design had it, renamed. Not presented.

---

## Item 7 of 9: Where the run's files live on the branch

Ruled in your own model, and applied. A topic branch's directories mirror main; there is no directory of the run's own.

- **Before code exists**, the design and the contract are written in `docs/designs/queue/`, by the pattern of the three queues the project has. When code starts they move into the component's directory, before anything outside the run cites them.
- **The component's directory** holds the design, the contract, the test-design, the code, and its tests in a `tests/` subdirectory. Where that directory is follows the repository layout rule of [issue 224](https://github.com/nedschorus/nedschorus/issues/224); the wiki links to the design once it is in use.
- **The run's record**, notes, reports, your rulings and the run state, lives in a subdirectory of the component's directory on the branch and is deleted before the gate. It survives on the retained topic branch, where git keeps every commit.

Ruled Y. Also from this item: a test lives in a subdirectory of the component it tests; cold-read earns a directory of its own; the machine is Python, and step 1 reads PocketFlow before writing it. The first two go to issue 224 on your word.

---

## Item 8 of 9: The sixteen findings not applied, because you had ruled them

Sixteen findings, in eleven groups, each raised by one or more reviewers and each settled by a ruling of yours; the dispositions file cites the reviewer for every one. Nothing here changes unless you overrule yourself. Two parts.

### Item 8.1 of 9

1. **`stopped` as the one terminal state.** Reviewers wanted separate end states for accepted and abandoned. You named `stopped` on 2026-09-06; an outcome field on its state-exit says which.
2. **`initiate-design-to-main`, `investigate-workflow`, `submit-to-PR-gate`** naming both a skill and a state. You kept the names on 2026-09-06.
3. **The `-acceptance-by-program`, `-agent`, `-user` sub-state names**, and artifact-phase state names with four exceptions. Ruled 2026-09-06; the design now states the exceptions.
4. **`arbitrator`.** Your word of 2026-09-05; the fleet glossary conflict is item 4 of this walk.
5. **`coverage-type` and its values, `no-tests` with its three reasons.** Ruled 2026-09-03, renamed 2026-09-06.
6. **The component-contract as a second file by the design's author**, with you not a routine gate on it. Ruled 2026-09-04 and 2026-09-06.

Say next for the second part.

### Item 8.2 of 9

7. **No Kind column** in the state table. Ruled 2026-09-06.
8. **`green` and `red` as the suite's words.** Listed here in error: they were the seat's, not your ruling. You renamed them `pass` and `fail`, and the terminal state `stopped` became `ended` with outcomes `passed`, `failed`, `stopped-by-user`.
9. **The standing-decisions page and the MD-skills minutes are absent from this checkout.** Known: the page is on merge-lane's branch, the minutes on ned-box. The design says so.
10. **Resource limits, the design's and test-design's enumerated checks, provenance fields, the gate payload.** Deferred to step 1 or to merge-lane by earlier rulings; still listed in §11.
11. **Wholesale renames the terminology reviewers proposed**: `state-outcome-record`, `completed-artifact-authoring-attempt`, `request-changes` for discuss, `accept` for advance. Your rule is hyphenated compounds of existing words; the group names and `discuss` and `advance` were ruled.

Ruled Y with group 8 reopened and renamed; the deferred items of group 10 are captured as a build issue for the design-to-main machine, filed with the pull request.

---

## Item 9 of 9: What this walk asked, and the next step

- Your glossary rule applied to the document's own words: eight hyphenated phrases (item 2).
- The short exit words kept (item 3).
- `flaky-test`, `escalate-to-user`; `arbitrator` kept and the fleet glossary aligned (item 4).
- The contract check's moment and its three exits (item 5).
- Prompt tests reach you, script tests do not (item 6).
- Artifacts at the paths the design names; the run's record under one directory; where durable prose lands after acceptance is yours (item 7).

This item is rewritten at the close to carry what you actually ruled.

Next: the pull request, as you ruled in [item 8 of the round-2 walk](file:///Users/el/agents/reboot-test/docs/walk/state-machine-design-round-2-cold-read-flags-minutes.md). It carries the design at its new path, the workflow's glossary, the fleet glossary's three pointer entries, and the walk files of four walks. Merge-lane, the Mac-side agent that reviews and merges every pull request, reviews it. The record directories stay on this machine.

No decision. Say next to close.
