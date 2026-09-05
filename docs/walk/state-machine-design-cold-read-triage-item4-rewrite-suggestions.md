<!-- provenance: runtime=codex model=gpt-5.6-terra effort=low cell=fast-clarify tier=floor duration_s=80 tokens=34434 target=docs/walk/state-machine-design-cold-read-triage-item4-rewrite.md -->

# Cold-read report: Item 4 expanded

## 1. What it says

The introduction says that the node table describes each workflow node's inputs and outputs, that four cold readers found six defects in it, and that an incorrect row deprives a fresh node agent of information that later stages cannot restore.

### Item 4.1 of 6: The code reviewer is asked to run tests it never receives

The code reviewer must run tests to detect implementation defects, including the worked fast-forward case, but its table row does not receive the tests. The proposed decision is to add tests to its inputs; this is presented as compatible with separating the coder and test coder because review is where their output lines meet.

### Item 4.2 of 6: The test coder may reject a document it is never given

The test coder is allowed to reject the code-design as well as the test-code-design, but receives only the latter and therefore cannot tell whether a proposed test represents a promised requirement. The proposed decision is to give it the code-design, while retaining the separation of the code and test outputs.

### Item 4.3 of 6: Nodes the design routes to that have no row — no decision needed

The design routes work to a code-design reviewer, a reconciliation node, and three contract checks that have no node-table rows, so their routing rules lack defined destinations. A prior commitment is said to require rows for every named state; `contract-user-check` is already retired, leaving four rows to add and no new decision requested.

### Item 4.4 of 6: Your row admits only final prose, and three other paths reach you

The User row permits only final prose, although the two designs reach the user before they are final, escalations bring a conversation and numbered history, and a failed user review leads to a discussion. The proposed decision is to list the user’s non-final-prose inputs as well as final prose.

### Item 4.5 of 6: One output, many consumers — the fan-out belongs to the machine

The claimed conflict between one output connection and multiple code-design consumers is resolved by treating the state machine as the actor that routes one emitted output to multiple validators. The proposed decision is to state that delivery belongs to the machine and retire this as a defect.

### Item 4.6 of 6: Documents in a package are not input connections

Several documents delivered together are one package and therefore one input connection, rather than several input connections; only an arbitrator normally has two packages. The proposed decision is to state that the machine assembles every node’s package, not merely a validator’s.

## 2. Where you stumbled

1. [question] “Item 3's Y commits the rewrite to a state table” — Where is the accepted Item 3 decision that makes this commitment binding?

2. [question] “One of the five is already retired by a separate ruling” — What is the separate ruling that retires `contract-user-check`?

3. [two-readings] “Three other paths in the design deliver you something that is not final prose.” — The following first path contains two designs, so it is unclear whether “three” counts categories or distinct deliveries; that changes the inputs the User row must list.

4. [question] “The fix is to list all of them: final prose for review, the two designs at the gate, and the escalation conversation.” — How is the preceding discussion path included in this list of all paths?

5. [question] “the code-design node has one output connection and three consumers: the contract writer, the coder, and the test-code-design writer” — How do these three consumers relate to the later statement that the machine delivers the output to both validators?

## 3. What it does not cover

1. [no-rule] “**Y** to add the tests to the code reviewer's inputs, **N**, or **D**.” — What does the document prescribe after an N or D response to each requested decision?

2. [no-rule] “four rows to add, not five.” — What inputs, outputs, and successors must the four missing rows define for the code-design review node, reconciliation node, `contract-program-check`, and `contract-agent-check`?

3. [no-rule] “The machine then delivers that one output to both validators.” — Once either validator has received the code-design, where does its result route, including the case where the validators differ?

