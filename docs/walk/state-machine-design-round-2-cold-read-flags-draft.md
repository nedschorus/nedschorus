# Walk: the state-machine design's second cold read — what changed, and what needs your word

The rewritten design went through the cold-read grid a second time. Four reviewers returned 347 findings. Most are applied; twelve changes follow from your rulings but you have not seen them stated, and three questions are yours. 8 items.

[The design](file:///Users/el/agents/reboot-test/docs/cross-project/design-to-main-state-machine-design.md) — [the not-applied record](file:///Users/el/agents/reboot-test/cold-read-records/2026-09-05-design-to-main-state-machine-design/dispositions-not-applied.md), machine-local.

---

## Item 1 of 8: 347 findings, up from 236 — and what the reviewers could not see

The counts by cell: codex floor 58 → 59; claude floor 26 → 99; codex good 75 → 91; claude good 77 → 98. No clean section in any cell, both rounds.

The count went up 47%. My reading: the first draft had no transitions, no counters, no git layout and no arbitrator table, so there was nothing there to be wrong. The rewrite specified all of them, and a good share of that specification was wrong in ways four independent readers found the same way. Twelve structural defects account for most of the 347; the rest are absolutes, undefined terms, and the same defect seen from four angles. After deduplication there are about 150.

Two things the reviewers could not see, which explain part of the count:

- **Your rulings.** I told you the cells would be handed today's rulings as a settled set. They were not — the grid takes one argument, the target file, and has no way to receive a rulings file. So the cells re-raised, as findings, decisions you had made hours earlier. That is an instrument gap in the cold-read skill, not a defect in the design, and the design now says so where it promises rulings to the cells.
- **Pages not on main.** The objective page with your standing decisions is on merge-lane's unpushed branch; the MD-skills terminology minutes are on that seat's. Every cell reported both as missing. The design now says plainly where each is; the remedy is those seats landing them.

No decision. Say next.

---

## Item 2 of 8: A loop-in pauses the run; every design rejection is a conversation with you

The rewrite made `loop-in` a terminal state — the run ends in conversation — and also made it the cause of every redesign, the appender of the settled rulings, and the channel for a status report. The good-tier Claude cell listed those as four incompatible jobs, and it was right.

Your ruling in item 6.2 of the last walk settles it: "You are also looped in when a code-design is rejected." So a redesign *is* a conversation with you, not a machine state you are told about at the third one. Followed through:

- A **run** is a component's whole life in the machine. A loop-in **pauses** it and hands you a report; your ruling names where it resumes, or says stop.
- A judge's `reject design` goes to loop-in, focus `design`, and re-entering the design node from there is a redesign.
- The third redesign is not first contact — you were in every one. It is where the machine stops opening a fourth and hands the component back as stopped.
- The two terminal states are `submit-to-gate` and `stopped`.

Recommendation: adopt that as stated. Y, N, or D.

---

## Item 3 of 8: The build ceiling loops you in, and a rebuild after a corrected contract is a build

Two counting rules I wrote were wrong and the cells caught both.

**The build ceiling.** I wrote "the third unclosed build goes to the arbitrator." The arbitrator then routes to a writer — build 4 — and nothing bounds it. The arbitrator's one trigger is a red suite (your 6.3); the ceiling is the machine's counter. Its consequence is a loop-in, focus `unknown`, with the arbitrator writing the report from the branch history. And when an arbitrator's ruling would send work to a writer already at its ceiling, the ceiling wins and the ruling rides in the report.

**Corrections and builds.** You ruled that a cheap prose ping-pong must never burn the build budget. But the only edge out of a corrected contract goes to the implementor, whose write is a build, so every correction cost a build by topology. The honest statement: a rebuild forced by a corrected contract is expensive and is a build; the correction itself is not. Contract-writer ping-pong with no code written stays free, and because the contract loops you in at its second correction, a defective contract can burn at most two builds before you see it.

Recommendation: adopt both. Y, N, or D.

---

## Item 4 of 8: Three routes the machine lacked — a rejected submission, a suite that cannot run, an illegal destination

- **A rejected submission had no path back.** `submit-to-gate` was terminal; under the interim lane merge-lane rejects with changes requested, and nothing received it. Now: the gate's `rejected` is a loop-in, focus `unknown`, with the gate's findings as the report — a gate rejection means this machine's own review missed something, which is worth your look rather than another automatic round.
- **A suite that cannot run** — missing interpreter, broken fixture, a runner crash — had no exit; the only outcomes were green or failing tests. Now: `could-not-run`, retried once by the machine, then a loop-in, focus `unknown`.
- **The machine routed on whatever destination a judge named**, with no check. Now the transition table is the legal-edge list; the machine checks every destination against it, and an illegal one is a machine error routed to loop-in.

Recommendation: adopt all three. Y, N, or D.

---

## Item 5 of 8: Two rulings I dropped, restored

- **You review the test-design.** In item 4.4 you said you are the gate for code-design and test-code-design, and the ruled text was "all final prose after its cold read." My table gave the design a user-review state and the test-design none. It now has `test-design-user-review`, the same shape as the design's.
- **Your node names.** You named them `implementor-node`, `test-design-node`, and so on, and item 3 ruled your names as given. I dropped the suffix. Every state now carries it, and the codex floor cell independently flagged the bare names against the naming rule in `CLAUDE.md`.

Recommendation: confirm both restorations. Y, N, or D.

---

## Item 6 of 8: A corrected contract invalidates both lines; the arbitrator has a status mode; nit repair is a departure

- **A corrected contract invalidates everything built from the old one.** Without this, tests written to the old contract and a stale test-review verdict rode to the suite. The machine marks both lines not-advanced on re-emission; the implementor rebuilds, and the test-designer re-derives if tests have begun. This also covers the stale-approval case without provenance fields.
- **The arbitrator on demand is a status mode.** You ruled you can invoke it at any point. A routed arbitrator has two packages and a red suite; an on-demand one has one package — the branch history — pauses the run, answers or writes a status report, and emits no routing exit. Any ruling you give it goes into the settled rulings and the run resumes.
- **No local nit repair** is a departure from decision 4's second half ("a safe nit may be repaired ... locally"), which the departures section did not name. It does now.

Recommendation: adopt all three. Y, N, or D.

---

## Item 7 of 8: Three questions that are yours, held open in the design

- **Is a `prompt`-typed implementation cold-read?** Your rule: prose emitted to a next node is cold-read. Your other rule: implementations are reviewed against a contract. A prompt implementation is both. Which wins is yours.
- **What is an `excluded` implementation?** I wrote that an implementation "may be a script, a prompt, both, or nothing." Whether an implementor ever exits `excluded`, and what its contract and review are, is not something I can invent.
- **Bounding the contract.** "Everything a caller can observe" is the first walk's definition, and the cells are right that it is unbounded — timing, memory, dependency wording. Bounding it to what the design promises is a change to a ruled definition.

Recommendation: leave all three open in §11 and answer them when you choose; or rule any of them now. Y to leave open, or your answers.

---

## Item 8 of 8: What was not applied, and the next step

Sixteen findings were not applied, each with its reason in the record: five deferred to build step 1 by your rulings, five open questions, four citations of real files a fresh clone cannot see, two ruled names the cells disliked. None is a disagreement with a reviewer on a defect.

The design is 6,465 words, up from 4,860. The growth is the transition table and the branch layout — the two tables the first rewrite was supposed to have and did not.

Next step: your rulings on items 2 through 7 change the document, so a third cold read waits for them. Then the grid runs again; the cells still cannot see your rulings, so expect the same class of re-raised findings until the cold-read skill gains a rulings input. Then the design lands into build step 1's issue as its pair.

Recommendation: rule items 2–7, then a third cold read. Y, N, or D.
