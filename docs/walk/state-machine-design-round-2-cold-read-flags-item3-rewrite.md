# Item 3 expanded: two counting rules, each followed through one run

Item 3 of the round-2 walk bundles two counting rules the cold read found wrong. This expands it into two sub-steps, each traced through a concrete run. 2 sub-steps, one decision at the end.

[The parent walk](file:///Users/el/agents/reboot-test/docs/walk/state-machine-design-round-2-cold-read-flags.md) — [the design](file:///Users/el/agents/reboot-test/docs/design-to-main/design-to-main-state-machine-design.md), §7 "Counting".

Background, for anyone picking this up cold. The machine keeps counters per component so that no loop runs forever. **Builds** counts successful implementation writes, three per version of the design, nine in all. **Corrections** counts re-writes of the contract after it is rejected, two before the user is brought in. The user is brought in through `investigate-workflow`, the state in which he and the arbitrator talk; the arbitrator is the one agent that reads the whole branch history. The arbitrator is otherwise reached only when the test suite fails.

---

## Item 3.1 of 2: The third failed build goes to the arbitrator, who opens the investigation with you

Take a component whose design has been approved. The implementor writes build 1; the reviewer rejects it. Build 2; rejected. Build 3; rejected again. The build counter is at its ceiling of three for this version of the design.

The design as committed said the third build that failed review goes to the arbitrator, not to the user. Follow that. The arbitrator reads the branch and rules "the implementation is wrong" — its only ruling that fits — and routes to the implementor. That is build 4. Nothing in the document says what happens at build 4, or at build 10. The ceiling had no consequence. Two cells found it.

The fix is one rule. **When the third build fails, the arbitrator opens the investigation with you.** The machine hands the arbitrator the branch history; it writes the report — three builds, what failed each time — and you rule: redesign, correct the contract, or stop. It does not matter whether the third build failed review or failed the suite. If it failed the suite and the arbitrator would have ruled "back to the implementor," that ruling goes in the report instead of being acted on, because the budget is spent. If two budgets run out in the same moment, one investigation opens and the report names both.

No decision yet; the decision is in 3.2. Say next.

---

## Item 3.2 of 2: A correction is free; the rebuild it forces is not

You ruled in item 6.8 of the previous walk that a cheap prose ping-pong must never burn the build budget. The cells found that the design's own transition graph broke that rule.

Take the same component. The contract writer emits contract v1: "on refusal, exit 0." The implementor builds to it — build 1. The reviewer reads the design, which says a refusal is an error, and rejects the contract. A fresh contract writer emits v2: "on refusal, exit 1." That is correction 1. Now the only edge out of the contract writer goes to the implementor, and the implementor's write is counted. Build 2 is spent because the contract changed. A second correction forces build 3. Two corrections have forced two rebuilds — builds 2 and 3 — so the epoch's three builds are gone, and one line of code has been written three times. That is the loop you were guarding against, produced by topology.

The honest statement, and what the design now says:

**A correction is not a build.** Contract-writer ping-pong with no code written costs nothing from the build budget. Concretely: the implementor reads contract v1, cannot build from it, and stops with `could-not` — no build; a fresh contract writer emits v2 — a correction; the implementor builds from v2 — build 1. One build, one correction.

**A rebuild forced by a corrected contract is a build.** In the first run above, build 2 was real work — the code changed — and it is counted. Hiding it would make the budget a fiction.

**The bound holds anyway.** The contract opens an investigation at its second correction. So the most a defective contract can cost before you see it is two builds, and you see it with both contract versions in front of you.

Recommendation: adopt both 3.1 and 3.2 as stated. Y, N, or D.
