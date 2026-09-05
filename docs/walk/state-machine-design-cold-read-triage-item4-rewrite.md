# Item 4 expanded: the node table's six findings

The design-to-main state machine's node table says what each node receives and produces. Four cold readers found six defects in it. 6 items.

[The parent walk](file:///Users/el/agents/reboot-test/docs/walk/state-machine-design-cold-read-triage.md) — this expands its item 4. The document under review is [the state-machine design](file:///Users/el/agents/reboot-test/docs/cross-project/design-to-main-state-machine-design.md).

Background, for anyone picking this up cold. The design describes a pipeline that takes a component from a design document through to code that is ready to submit for merging. Each step is a node. A node is run by a fresh agent that keeps no memory of previous runs, so everything a node needs must arrive in its inputs. The node table is the list of those nodes with two columns: what each one receives, and what it produces. If a row is wrong, an agent built from it is missing something it needs, and nothing later can recover that.

---

## Item 4.1 of 6: The code reviewer is asked to run tests it never receives

The code reviewer reads a package, judges the code against what was promised, and writes a notes file plus a destination saying where the work goes next. Its table row says it receives three things: the code-design, the contract, and the code.

The design also says the code review is where the code and the tests first meet, and that the review runs the tests. The tests are produced by a different node, the test coder. They are not in the code reviewer's row.

A concrete case, and it is the design's own worked example. A code-design promised that `git merge --ff-only origin/main` would refuse a branch carrying stray commits. The real behaviour is that when the branch is strictly ahead, the command prints "Already up to date", exits 0, and the stray commit rides forward. The design says plainly that nobody found this by reading — it was found by running the command.

That is exactly the class of defect the code reviewer exists to catch, and with three documents and no tests it cannot run anything. An implementer building this node from the table would ship a reviewer that can only read.

The fix I first proposed was to add the tests to the reviewer's inputs. The discussion reversed that: reviewers write and run their own tests, and handing them ours makes them try less hard and inherit our priorities. RULED Y on this text instead:

The code reviewer receives the code-design, the contract for the scope under review, and the code to be reviewed. It writes and runs its own tests to its own completion bar and keeps them with its notes as evidence. It does not receive our suite or its result. The machine runs the suite; the result routes, and reaches the arbitrator when code and tests conflict.

---

## Item 4.2 of 6: The test coder may reject a document it is never given

The test coder receives the test-code-design and produces the tests. That is its whole row.

Elsewhere the design says the test path has a second prose parent above it, and that the test coder and test reviewer may reject the code-design as well as the test-code-design. So the test coder holds a right of rejection over a document that is not among its inputs.

A concrete case. The test-code-design says to assert that a command refuses a bad branch. The test coder reads it and needs to know whether refusing was ever promised. If the code-design never required a refusal, the test-code-design has invented a requirement, and the test coder should reject upward rather than write a test that pins behaviour nobody asked for. To do that it has to have read the code-design. It has not.

The alternative reading is that the right of rejection is the error and should be removed. I think that is wrong: the right came from a ruling, and the two-prose-parents structure is deliberate. What is missing is the input that makes the right exercisable.

The fix is to add the code-design to the test coder's inputs. This does not weaken the separation between the two loops, which is about the coder and test coder never seeing each other's *output* — the code and the tests. Prose parents are shared by design; the outputs are not.

**Y** to add the code-design to the test coder's inputs, **N**, or **D**.

---

## Item 4.3 of 6: Nodes the design routes to that have no row — no decision needed

The table has ten rows. The prose routes work to several nodes that are not among them: the code-design review node, the node that reconciles code and tests, and the three contract checks — `contract-program-check`, `contract-agent-check`, and `contract-user-check`.

The contract checks show the cost. The design says failure routes by which check failed, so the classification is the remedy: a program-check failure is a mechanical fix and consumes no pass, an agent-check failure is a rewrite and does. That is a real routing rule with three destinations, and none of the three destinations is listed as a node. A reader can follow the rule and still not know what it points at.

I am flagging this rather than asking, because you already ruled it. Item 3's Y commits the rewrite to a state table where every state named anywhere appears with its inputs, outputs, and successors — that ruling is recorded in [the walk minutes](file:///Users/el/agents/reboot-test/docs/walk/state-machine-design-cold-read-triage-minutes.md). That covers these. What this item adds is only the specific list to check the rewrite against, so none of them is missed a second time.

One of the five is already retired by a separate ruling, recorded in the same minutes: `contract-user-check` collapsed into your general prose gate when you ruled that you review all final prose after its cold read. The contract is seen because it is prose, not because the contract has a special rule. So four rows to add, not five, and each must state its inputs, its outputs, and where it routes on success and on failure.

No decision. Say next.

---

## Item 4.4 of 6: Your row admits only final prose, and three other paths reach you

Your row says you receive any final prose after its cold read, and produce a ruling.

Other things reach you that are not final prose.

**The code-design and the test-code-design, at the gate.** You are a gate on both, and both reach you before either is final.

**The escalation.** When a component hits its third restart it comes to you, and the design is specific about the form: every agent is fresh, so only the numbered files hold the history. The escalation carries all of them in pass order with a covering page naming what conflicts, and it arrives as a conversation rather than a report. A stack of numbered notes files and a conversation is not final prose.

**The discussion when a document does not pass.** Your own flow adds this one: you read the design after its cold read, and if it does not pass, you and the agent discuss. The table has no path for that.

The consequence is not cosmetic. Your row is what an implementer reads to decide what may be sent to you, and as written it would refuse an escalation.

RULED Y on this text, after the discussion collapsed the designs into the final-prose path: your row lists three paths — all final prose after its cold read (designs, wiki pages, CLAUDE.md, skills, whatever the document is); the escalation conversation at the third restart; and the discussion when a document fails your review. Not code, not tests, not traffic between nodes.

---

## Item 4.5 of 6: One output, many consumers — the fan-out belongs to the machine

Two cold readers reported that the code-design node has one output connection and three consumers: the contract writer, the coder, and the test-code-design writer. I carried it as a defect. It is not one, and your last two rulings are what resolve it.

Your shape rule is that a node has one output connection and one or two inputs. Read as node-to-node wiring, one output cannot reach three consumers, which is why it looked like a defect.

It agrees once delivery is the machine's job. The code-design node emits one thing, once. The machine then delivers that one output to each consumer. Fan-out is routing, and item 2 settled that routing is exactly what the machine does and the only kind of thing it may do, because it is code and holds no judgement about who should get what.

Your own flow is the same shape with different consumers: the design you approve reaches `implementation-validator-node` and `test-design-validation-node` in parallel. Whether the count is two or three does not matter to the rule. One emission, several deliveries, and the deliveries are the machine's.

So the node genuinely has one output connection, and the several consumers are on the far side of the machine rather than the far side of the node.

What my document lacks is the sentence saying so. It describes the machine assembling a package for the validator and never generalises that to delivery in both directions, which is what made a correct rule look like a contradiction.

**Y** to state that delivery is the machine's and retire this as a defect, **N**, or **D**.

---

## Item 4.6 of 6: Documents in a package are not input connections

This is the input-side mirror of 4.5, and one sentence fixes both.

Two readers reported that most rows list several inputs while the shape rule allows one connection. The code reviewer's row lists the code-design, the contract and the code to be reviewed. Three documents. Your rule allows one or two inputs.

These are different counts. The machine assembles a package and hands it over as one delivery, so the code reviewer has **one** input connection carrying three documents. The design already says this for the validator: a validator asking whether the coder can work from this contract given this code-design gets both in one package, assembled by the machine before it sees them. It never says it for anything else.

Generalised, your one-or-two rule reads cleanly. Every node takes one package. The arbitrator takes two, which is what makes it an arbitrator — the table's arbitrator row already says it receives two packages. So one input is the normal case, two is the arbitration case, and the count of documents inside a package is unrelated to either.

The fix is the same sentence as 4.5, said for the other direction: the machine assembles every node's package, not only the validator's.

**Y** to generalise package assembly to every node and retire this as a defect, **N**, or **D**.
