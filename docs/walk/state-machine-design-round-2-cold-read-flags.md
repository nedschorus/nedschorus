# Walk: the state-machine design's second cold read — what changed, and what needs your word

The rewritten design went through the cold-read grid a second time. Four reviewers returned 347 findings. Most are applied; twelve changes follow from your rulings but you have not seen them stated, and three questions are yours. 8 items.

[The design](file:///Users/el/agents/reboot-test/docs/design-to-main/design-to-main-state-machine-design.md) — [the record of findings not applied](file:///Users/el/agents/reboot-test/cold-read-records/2026-09-05-design-to-main-state-machine-design/dispositions-not-applied.md), machine-local — [the previous walk's minutes](file:///Users/el/agents/reboot-test/docs/walk/state-machine-design-cold-read-triage-minutes.md), where every "item N" ruling below is recorded.

Several items bundle related changes. Y takes them all; to take some, name the ones you decline.

---

## Item 1 of 8: 347 findings, up from 236 — and what the reviewers could not see

A cold read runs four reviewer agents — the **cells** — each reading the document with no context from the conversations that produced it. The counts by cell: codex floor 58 → 59; claude floor 26 → 99; codex good 75 → 91; claude good 77 → 98. No clean section in any cell, both rounds.

The count went up 47%. My reading: the first draft had no transitions, no counters, no git layout and no arbitrator table, so there was nothing there to be wrong. The rewrite specified all of them, and a good share of that specification was wrong in ways four independent readers found the same way. Twelve structural defects account for most of the 347; the rest are absolutes, undefined terms, and the same defect seen from four angles. After deduplication there are about 150.

Two things the cells could not see, which explain part of the count:

- **Your rulings.** I told you the cells would be handed today's rulings. They were not — the grid takes one argument, the target file, and has no way to receive a rulings file. So the cells re-raised, as findings, decisions you had made hours earlier. That is a gap in the cold-read instrument, not a defect in the design, and the design now says so where it promises rulings to the cells.
- **Pages not on main.** The objective page with your standing decisions is on merge-lane's unpushed branch; the MD-skills terminology minutes are on that seat's. Every cell reported both as missing. The design now says plainly where each is; the remedy is those seats landing them.

No decision. Say next.

---

## Item 2 of 8: A loop-in pauses the run; every design rejection is a conversation with you

The rewrite made `loop-in` a terminal state — the run ends in conversation — and also made it the cause of every redesign, the appender of the settled rulings, and the channel for a status report. The good-tier Claude cell listed those as four incompatible jobs, and it was right.

Your ruling in item 6.2 of the previous walk settles it: "You are also looped in when a code-design is rejected." So a redesign *is* a conversation with you, not a machine state you are told about at the third one. Followed through:

- A **run** is a component's whole life in the machine. A loop-in **pauses** it and hands you a report; your ruling names where it resumes, or says stop.
- A judge's `reject design` goes to loop-in, focus `design`, and re-entering the design node from there is a redesign.
- The third redesign is not first contact — you were in every one. It is where the machine stops opening a fourth and hands the component back as stopped.
- The two terminal states are `submit-to-gate` and `stopped`.

Recommendation: adopt that as stated. Y, N, or D.

---

## Item 3 of 8: The build ceiling loops you in, and a rebuild after a corrected contract is a build

Two counting rules I wrote were wrong and the cells caught both.

**The build ceiling.** I wrote "the third unclosed build goes to the arbitrator." The arbitrator then routes to a writer — build 4 — and nothing bounds it. The arbitrator's one trigger is a red suite, per your ruling in item 6.3 of the previous walk; the ceiling is the machine's counter. Its consequence is a loop-in, focus `unknown`, with the arbitrator writing the report from the branch history. And when an arbitrator's ruling would send work to a writer already at its ceiling, the ceiling wins and the ruling rides in the report.

**Corrections and builds.** You ruled that a cheap prose ping-pong must never burn the build budget. But the only edge out of a corrected contract goes to the implementor, whose write is a build, so every correction cost a build by topology. The honest statement: a rebuild forced by a corrected contract is expensive and is a build; the correction itself is not. Contract-writer ping-pong with no code written stays free, and because the contract loops you in at its second correction, a defective contract can burn at most two builds before you see it.

Recommendation: adopt both. Y, N, or D.

---

## Item 4 of 8: Three routes the machine lacked — a rejected submission, a suite that cannot run, an illegal destination

Read with the names you ruled in item 2: `investigate-workflow` for what the draft called loop-in, `submit-to-PR-gate` for submit-to-gate.

- **A rejected submission had no path back.** `submit-to-PR-gate` was terminal; under the interim lane merge-lane rejects with changes requested, and nothing received it. Now: the gate's `rejected` opens an investigation with you, focus `unknown`, with the gate's findings as the report — a gate rejection means this machine's own review missed something, which is worth your look rather than another automatic round.
- **A suite that cannot run** — missing interpreter, broken fixture, a runner crash — had no exit; the only outcomes were green or failing tests. Now: `could-not-run`, retried once by the machine, then the arbitrator, which routes it to the tests or the implementation; it reaches you only if the arbitrator finds the environment at fault. You ruled this in item 2; it is here so the three routes are in one place.
- **The machine routed on whatever destination a reviewer or the arbitrator named**, with no check. Now the transition table is the legal-edge list; the machine checks every destination against it, and an illegal one is a machine error that opens an investigation with you.

Recommendation: adopt the first and third; the second is already ruled. Y, N, or D.

---

## Item 5 of 8: Two rulings I dropped, restored

- **You review the test-design.** In item 4.4 of the previous walk you said you are the gate for code-design and test-code-design, and the ruled text was "all final prose after its cold read." My table gave the design a user-review state and the test-design none. It now has `test-design-user-review`, the same shape as the design's. With today's ruling, `test-design-reviewer-node` sits in front of it, as `design-reviewer-node` sits in front of yours on the design.
- **Your node names.** You named them `implementor-node`, `test-design-node`, and so on, and item 3 of the previous walk ruled your names as given. I dropped the suffix. Every state now carries it, and the codex floor cell independently flagged the bare names against the naming rule in `CLAUDE.md`.

Recommendation: confirm both restorations. Y, N, or D.

---

## Item 6 of 8: A corrected contract invalidates both lines; the arbitrator has a status mode; nit repair is a departure

- **A corrected contract invalidates everything built from the old one.** Without this, tests written to the old contract and a stale test-review verdict rode to the suite. The machine marks both lines not-advanced on re-emission; the implementor writes the code again, from scratch, and the test-designer re-derives if tests have begun. This also covers the stale-approval case without provenance fields. You ruled this today in the inner walk's item 4, in your words: reject a precursor and you reject everything after it. It is here only so the three are in one place.
- **The arbitrator on demand.** The draft had a separate "status mode": you invoke the arbitrator, it gets the branch history, pauses the run, answers or reports, and emits no routing exit. Your item 2 ruling replaced that: every dialog between you and the machine is an investigation, with the arbitrator as the agent you talk to, opened by you with the investigate-workflow skill. So the status mode is not a separate thing in the design any more; it is what an investigation you open looks like. Any ruling you give in it goes into the settled rulings and the run resumes.
- **No local nit repair is a departure** from the AI-native architecture's standing decision 4, whose second half reads "A safe nit may be repaired, verified, and recorded locally." The design's departures section did not name it. It does now.

Recommendation: the first two are already ruled; adopt the third. Y, N, or D.

---

## Item 7 of 8: Three questions that are yours, held open in the design's §11

- **Is a `prompt`-typed implementation cold-read?** Your rule: prose emitted to a next node is cold-read. Your other rule: implementations are reviewed against a contract. A prompt implementation is both. The design applies neither until you say which.
- **What is an `excluded` implementation?** I wrote that an implementation "may be a script, a prompt, both, or nothing." Whether an implementor ever exits `excluded`, and what its contract and review are, is not something I can invent.
- **Bounding the contract.** "Everything a caller can observe" is the first walk's definition, and the cells are right that it is unbounded — timing, memory, dependency wording. Today you said the contract is the design with more detail, and that it brings in the implementation details needed for testing or full implementation. That reads as a bound: what the design promises, plus the details a tester needs to observe those promises, and nothing else. If that is what you meant, this question closes with it.

Recommendation: leave the first two open in the design's §11, "Not decided here", and close the third with today's words. Y, or your answers now.

---

## Item 8 of 8: What was not applied, and the next step

Sixteen findings were not applied, each with its reason in the record: five deferred to build step 1 by your rulings, five open questions, four citations of real files a fresh clone cannot see, two ruled names the cells disliked. None is a disagreement with a reviewer on a defect.

The design is 6,465 words, up from 4,860. The growth is the transition table and the branch layout — the two tables the first rewrite was supposed to have and did not.

Next step: items 2 through 7 are ruled, and with them two nested walks' worth of changes: the state rename, the contract written by the design's author, two new agent checks in front of your reviews, the `no-tests` vocabulary, component-consumer, the rejection-versus-refusal split, and the §11 answers. All of it goes into the design in one commit, with the walk files, naming the record directory. Then the cold-read run a third time; the reviewers still cannot see your rulings, so expect the same class of re-raised findings until the cold-read skill gains a rulings input. Then the pull request, and the design lands into build step 1's issue as its GHI-MD. If you say N, the alternative is to open the pull request now and let the third read happen on main's copy.

Recommendation: one commit, then the third cold read, then the pull request. Y, N, or D.
