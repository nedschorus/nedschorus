<!-- provenance: runtime=codex model=gpt-5.6-terra effort=low cell=fast-clarify tier=floor duration_s=77 tokens=39056 target=docs/walk/state-machine-design-cold-read-triage-item6-rewrite.md -->

# Cold-read report: item 6 rewrite

## 1. What it says

The introduction says this document expands item 6 of a parent walk into eight logic failures in the state-machine design. Five came from a cold read and three from later questions; three are already decided and appear only as rewrite checks.

### Item 6.1 of 8: A clean review cannot advance — resolved by item 5

The prior design allowed only a nit to set `advance`, so a review with no findings could not leave. Item 5 resolves that by making every output carry an exit, with a clean review setting `advance` whether it has nits or not; nits are annotations rather than the trigger.

### Item 6.2 of 8: The arbitrator invents intent

An arbitrator cannot name a correct test assertion when the contract is silent, because doing so would decide component behaviour below the design. The proposed rule is to return a “contract does not decide this” exit to the contract writer instead.

### Item 6.3 of 8: Arbitration triggers without disagreement

Defining conflict as two packages arriving would invoke arbitration even when they agree. Under item 4.6, two packages route to an arbitrator, which then determines agreement or disagreement and advances or issues a ruling accordingly.

### Item 6.4 of 8: A nit has three definitions

The design gives incompatible definitions of a nit. The proposed single definition is a real defect with no observable consequence, whose classification can depend on where it occurs; it stays in reviewer notes and is never returned as producer work.

### Item 6.5 of 8: The round-two guard and the reviewer's tests — resolved by item 4.1

The apparent conflict between reviewers writing failing tests and never editing what they judge is resolved by treating reviewers’ self-written tests as evidence kept with notes, rather than changes to the reviewed code. The rewrite is to state that distinction.

### Item 6.6 of 8: Line 200 is obsolete — resolved by items 2 and 4.2

The old no-fresh-cold-read rule is said to be unnecessary because cold reading now occurs within each prose-producing node and a design changes only when code cannot be written from it or cannot pass acceptance. The rewrite deletes line 200 because designs are rewritten for failure rather than reread for drift.

### Item 6.7 of 8: The code-design's validator is asserted and never enumerated

Unlike the contract validator, the code-design validator is only implied by a generalising sentence even though it is meant to establish that a coder has enough information. The proposed rewrite lists its program and agent checks in the same form as the contract’s checks.

### Item 6.8 of 8: Which number a rejection increments is undefined

The existing definitions do not classify contract and test-design rejections as either restart or pass, although the overall bound still prevents an infinite loop. The proposed rule makes a rejection sent back to the code-design a restart, other rejections passes within that restart, and requires each rejection to identify its counter.

## 2. Where you stumbled

1. [question] “**Y** to route a silent-contract case to the contract rather than have the arbitrator rule, **N**, or **D**.” What do `N` and `D` mean, and what happens after either response?

2. [question] “No decision. Say next.” What action does “Say next” require, and who is to perform it?

3. [question] “Its exit is ‘the contract does not decide this,’ and the contract writer gets the question.” What destination or process handles the contract writer’s question when that writer cannot decide it?

4. [question] “A review’s exit is its destination.” Is an exit identical to a destination, or does it contain a destination?

5. [question] “on disagreement, a ruling.” Does every disagreement produce a ruling that resolves it, or can a ruling route the disagreement elsewhere?

6. [question] “from round two a reviewer demonstrates a code defect with a failing test.” Does “round two” mean the second pass within a restart or the second review cycle overall?

## 3. What it does not cover

1. [no-rule] “Its exit on agreement is advance; on disagreement, a ruling.” What exit applies when two incoming packages address different or non-comparable matters, so they neither agree nor disagree?

2. [no-rule] “The design changes on exactly two triggers: the code cannot be written from it, or code cannot be written that passes acceptance.” What happens when a needed change is identified before code is written but is not an inability to write code, such as a contract change that changes the design’s described behaviour?

3. [no-rule] “a rejection that sends work back to the code-design is a restart; any other rejection is a pass within the current restart.” What counter applies to a rejection that routes to neither the code-design nor a producer, such as the silent-contract exit described in item 6.2?

4. [rule-conflict] “every node’s output carries an explicit exit the machine routes on” and “N, or D.” Which rule determines the next action when an item’s response is `N` or `D`, since neither is named as an exit or destination?
