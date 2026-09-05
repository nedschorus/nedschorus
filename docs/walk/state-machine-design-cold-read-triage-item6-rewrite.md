# Item 6 expanded: eight holes in the logic

Eight places where the design's rules, as written, produce no answer or the wrong one. Five came from the cold read, three from questions other seats asked afterwards. 8 items.

[The parent walk](file:///Users/el/agents/reboot-test/docs/walk/state-machine-design-cold-read-triage.md) — this expands its item 6. The document under review is [the state-machine design](file:///Users/el/agents/reboot-test/docs/cross-project/design-to-main-state-machine-design.md). Rulings cited below are in [the walk minutes](file:///Users/el/agents/reboot-test/docs/walk/state-machine-design-cold-read-triage-minutes.md).

Three of the eight were already resolved by rulings earlier in this walk. They are presented for the record, with no decision asked, so the rewrite has a checklist.

---

## Item 6.1 of 8: A clean review cannot advance — resolved by item 5

The design says only nits set `advance`. A review that finds nothing at all — no nits, no issues — therefore has no exit. The best possible outcome is trapped.

Item 5's ruling closes this: every node's output carries an explicit exit the machine routes on. A review's exit carries a destination, and "advance" is the destination a reviewer sets when it found no substantial issue, nits or none. Nits stop being the trigger and become an annotation.

No decision. Say next.

---

## Item 6.2 of 8: The arbitrator invents intent

The arbitrator settles a disagreement between the code and the tests. Its table of cases says that when a test asserts something the contract does not promise, the arbitrator names the correct assertion.

If the contract is silent on the point, there is no correct assertion to name. Naming one is deciding what the component should do, and the design forbids every node below the design from deciding that. The arbitrator would be writing contract in the guise of a ruling.

A concrete case. The contract promises the command refuses a branch with stray commits. A test asserts the refusal message contains the branch name. The contract says nothing about the message text. The arbitrator cannot rule the assertion right or wrong; it can only rule that the contract does not settle it.

The fix: when the contract is silent, the arbitrator routes up to the contract rather than ruling. Its exit is "the contract does not decide this," and the contract writer gets the question. If the contract writer cannot decide it from the code-design either, the same rule sends it up again — to the code-design, and at the bound to you. Each step up is a rejection of a prose parent, so it is counted the way item 6.8 counts them.

**Y** to route a silent-contract case to the contract rather than have the arbitrator rule, **N**, or **D**.

---

## Item 6.3 of 8: Arbitration triggers without disagreement

The design says a conflict is two packages arriving at one node. Two packages that agree would still trigger arbitration.

Item 4.6 settled what makes a node an arbitrator: it is the node that takes two packages. So the arrival of two packages is what *routes to* the arbitrator, and whether they conflict is what the arbitrator *determines*. It has three exits: advance, when the packages agree; a ruling with a destination for the fix, when they disagree and the contract decides it; and route-up, when they disagree and the contract is silent, per 6.2.

**Y** to make conflict the arbitrator's finding rather than its trigger, **N**, or **D**.

---

## Item 6.4 of 8: A nit has three definitions

The design defines a nit in three places and they do not match. Item 4.1 established, through your corrections, what the single definition has to satisfy:

- Not-testable is not nit. Rejecting a code-design carries a real failure scenario and no possible test.
- No-failure-scenario is not nit. Preferences, questions, suggestions, prose findings and false positives all lack one, and none is a nit.
- A nit is a real defect that is inconsequential. Your example: "log-in" for "login" in a comment. The same typo in a CLI flag is a contract defect.

So a nit is a genuine defect with no observable consequence, and position decides which it is. Nits are recorded in the reviewer's notes and never routed to a producer as work.

**Y** to adopt that as the one definition, **N**, or **D**.

---

## Item 6.5 of 8: The round-two guard and the reviewer's tests — resolved by item 4.1

The cold read found a contradiction: from the second pass a reviewer demonstrates a code defect with a failing test, while the same document says a reviewer never edits what it judges.

Item 4.1 dissolved it. Reviewers write and run their own tests; those tests are evidence kept with the notes, not edits to the thing under review. Writing a probe is not editing the code. The rewrite says so and the contradiction goes.

No decision. Say next.

---

## Item 6.6 of 8: Line 200 is obsolete — resolved by items 2 and 4.2

Line 200 says a code-design gets no fresh cold read unless the contract changes. It exists to stop a prose loop.

Item 2 put the cold read inside every prose-producing node, so there is no re-read event separable from a re-emission. Item 4.2's rider says the design changes on exactly two triggers: something below it cannot be written from it, or code cannot be written that passes acceptance. My reading of "cannot be written from it" — flagged as mine — is that it covers any producing node below the design, so a contract writer that cannot write a contract from it is the first trigger, not a third. A design is never re-read for drift, only rewritten on failure. Line 200 is deleted.

No decision. Say next.

---

## Item 6.7 of 8: The code-design's validator is asserted and never enumerated

The contract's validator checks are written out in full — every clause numbered, every clause one sentence, and so on. The code-design's validator exists only by the sentence "the scheme generalises: `code-design-program-check`, `tests-agent-check`, and so on."

That validator is the node that catches a code-design which is correct but insufficient — silent on something the coder needs. It is also the reason a code-design that is never re-read is safe: every reader that builds from it is fresh, and the validator asks whether it can be built from before any producer is spent. It should not rest on "and so on."

The fix: enumerate the code-design's program checks and agent checks in the rewrite, in the same form as the contract's.

**Y** to enumerate them, **N**, or **D**.

---

## Item 6.8 of 8: Which number a rejection increments is undefined

Every pass carries a restart count, 0 to 2, and a pass within it, 1 to 3. The design says a restart is a redesign or an arbitration. It does not say what a contract rejection or a test-design rejection is.

The bound holds regardless — a loop not closed at pass 3 goes to the arbitrator, and an arbitration is a restart — so this is an ambiguity, not a runaway. But an implementer cannot tell which counter to increment.

Item 4.2's rider gives the rule: a redesign fires only when the code cannot be written or cannot pass acceptance. So the fix: a rejection that sends work back to the code-design is a restart; any other rejection is a pass within the current restart. Every rejection says which.

**Y** to fix the numbering that way, **N**, or **D**.
