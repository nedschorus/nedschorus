# Walk: the third cold read of the state-machine design — what was fixed, and seven decisions

The design-to-main state machine turns an approved design into code and tests and submits them to the gate that guards main. Its design had a third cold read today; this walk reports what was fixed and asks the seven decisions that are yours. 8 items.

[The design](file:///Users/el/agents/reboot-test/docs/design-to-main/design-to-main-state-machine-design.md) — [its glossary](file:///Users/el/agents/reboot-test/docs/design-to-main/design-to-main-glossary.md) — [the dispositions of every finding](file:///Users/el/agents/reboot-test/cold-read-records/2026-09-06-design-to-main-state-machine-design/dispositions.md), machine-local.

---

## Item 1 of 8: What the read found, and what I fixed without asking

Six reviewer agents read the design: four hunting defects, two checking terms. About 500 findings came back; after removing the same defect seen six ways, about 60 distinct ones. Most were contradictions I wrote today while applying your rulings, and I fixed those in a second commit. The commonest:

- **Who does what per state.** My sentence "every other state launches a fresh agent" put the terminal state, your invocation, and the investigation in the wrong bucket. Now each state's work is listed plainly.
- **The test-design was never defined.** It is now: the list of test-requirements, one per promise a test must observe, each with the coverage-type of the test that covers it. That also settles where `no-tests` lives: on a test-requirement in the test-design, not on a test.
- **The write ceiling fired when the third implementation was emitted**, before it was reviewed. Your ruling is the third *failed* write. Fixed, and the counters now appear as guards on the reject exits rather than as rows of their own.
- **The redesigns counter was charged twice** per redesign, and nothing reset the per-version counters on a redesign. Fixed.
- **Your contract check had no way to say yes.** It now has advance, discuss, or open an investigation, and its moment is fixed: item 5.
- **The first component-contract's form check raced the design review.** Now the script runs first, at once, then the design review reads both files and may reject either.
- **Packages "not a checkout" versus a reviewer that must run code.** Every launched agent now works in a worktree of the topic branch, with the other work-stream's files absent.

Sixteen findings were not applied because you had ruled the thing they flagged today or earlier; the dispositions file cites each ruling. Everything else in this walk needs your word.

No decision. Say next.

---

## Item 2 of 8: Your glossary rule applied to the document's own words

You ruled today that no common software-engineering word is redefined and only hyphenated phrases are defined. The document broke that in its own vocabulary section: "exit", "package", "write", "revision", "correction", "nit", "line" and "focus" were all given senses of their own as bare words. Both terminology reviewers flagged every one.

I applied your rule, building each phrase from the word already there so a search still finds it:

| Was | Now |
| --- | --- |
| exit | `state-exit`: the record a state's work emits, a verdict and a destination |
| package | `state-package`: the files one launched agent is told to read |
| standard delivery | `standard-package`: the files every agent below the design gets |
| revision | `contract-revision` |
| correction | `test-design-correction` |
| nit | `unobservable-defect`: a real defect no component-consumer can observe |
| line | `implementation-work-stream`, `test-work-stream` |
| focus | `investigation-focus` |

Not taken: the reviewers' longer inventions, such as `completed-artifact-authoring-attempt` for a write. Your rule is three or four parts only when a shorter name collides or is ambiguous, and none of these do.

Recommendation: confirm the table. Y, N, or D.

---

## Item 3 of 8: The short words a state emits

A state's work ends with one word the machine routes on: `advance`, `emitted`, `discuss`, `stop`, `resume`, `green`, `red`. One reviewer flagged them as too short to search for: a search for `red` or `stop` finds everything.

They are always written beside the state's name. In a commit on the topic branch the trailer reads `State: implementation-reviewing` on one line and `Exit: advance` on the next, so a search for the pair finds exactly the event, and the words stay readable in a table. Lengthening them, to `state-artifact-emitted` for `emitted`, say, would make every row of the transition table longer for a search that already works.

Recommendation: keep the short words. Y to keep, N to lengthen, or D.

---

## Item 4 of 8: Two words that were not yours, and one that is

- **`unreliable-test`** was my name for a test that gives different results on the same inputs. The standard word is **flaky test**, and CLAUDE.md says to use standard terms. Applied: `flaky-test`.
- **`over-its-head`** was my name for the arbitrator's verdict that neither the component-contract nor the design settles a question. It names the arbitrator's inadequacy, not where the work goes. Applied: `escalate-to-user`.
- **`arbitrator`** is yours: on 2026-09-05 you said "if a judge is an arbitrator, call them that consistently." But the fleet glossary already has **adjudicator**, "a fresh agent, used to resolve conflicts between agents," which is the same role, and CLAUDE.md's rule is to use the existing name. Two words for one job across two documents is what a later agent will "fix" in one place and not the other.

Recommendation: keep `arbitrator` in the design, since you chose it with the whole role in view, and change the fleet glossary's entry to `arbitrator` with `adjudicator` noted as the older word. Y, N to adopt `adjudicator` instead, or D.

---

## Item 5 of 8: Your contract check, settled

Your ruling was that a contract reaches you when it has "failed review twice," and you "see both versions before a third is written." The document said that three different ways, and reviewers found they gave three different moments and no way for you to accept.

Settled reading, as applied. `create-topic-branch` again. The contract you discussed says exit 0 on refusal; the reviewer rejects it. A fresh agent writes contract-revision one. The reviewer rejects that too. That is the second failure. The counter is at its ceiling, and the machine does not start a second contract-revision. It shows you the original and contract-revision one, with both reviewers' notes, and waits. You may:

- **advance** contract-revision one as it stands, overruling the reviewer;
- **discuss**, and your ruling goes to a fresh agent that writes the next version from it;
- open an **investigation**, focus `contract`.

No third version is written without you. Y, N, or D.

---

## Item 6 of 8: A consequence of your standing-versus-per-run rule

You ruled today that you review standing agent-instructions, the instructions any agent will follow again, and not per-run text. A test of coverage-type `prompt` is agent-instructions run by a single-purpose agent every time the suite runs. By your rule it is standing, so it reaches you.

Three reviewers found the gap: the implementation side had `implementation-acceptance-by-user` for agent-instructions and the test side had nothing. Applied for symmetry: `test-acceptance-by-user`, only for tests that are agent-instructions, after the agent's check advances them. Script tests never reach you.

Recommendation: keep it, since it follows your rule. N if you would rather not read test prompts. Y, N, or D.

---

## Item 7 of 8: Where the run's files live on the branch

The design's branch layout put `design.md`, `contract.md`, `src/` and `tests/` at the root of the topic branch. Four reviewers found the same three problems: the branch is a branch of this repository, which has no `src/`; every component would use the same nine paths, so two components in flight collide; and nothing mapped `src/` to where the design actually wants the script.

Applied:

- The implementation and the tests live at the paths the design names for them: a script under `scripts/`, a skill under `.claude/skills/`, tests where the project keeps them.
- The run's record lives in one directory of its own: `design-to-main-runs/<component>/` holding the design, the component-contract, the test-design, evidence, reports, the user-rulings file, and the run-state file.

Whether that record directory lands on main with the component, or only the artifacts do, stays the open gate-payload question merge-lane is routing.

One thing this does not settle. The design and the test-design are durable prose by your rulings, meant to be read where people read. After the gate accepts the component, where do they go: stay in the record directory, or move under `docs/`, and where? That is yours; it is in the design's §11 until you say.

Recommendation: adopt the layout, and answer the landing question when you choose. Y, N, or D, and the landing place if you have one.

---

## Item 8 of 8: What this walk settled, and the next step

- Your glossary rule applied to the document's own words: eight hyphenated phrases (item 2).
- The short exit words kept (item 3).
- `flaky-test`, `escalate-to-user`; `arbitrator` kept and the fleet glossary aligned (item 4).
- The contract check's moment and its three exits (item 5).
- Prompt tests reach you, script tests do not (item 6).
- Artifacts at the paths the design names; the run's record under one directory; where durable prose lands after acceptance is yours (item 7).

Next: the pull request, as you ruled in the round-2 walk's item 8. It carries the design at its new path, the workflow's glossary, the fleet glossary's three pointer entries, and the walk files of four walks. Merge-lane reviews it. The record directories stay on this machine.

No decision. Say next to close.
