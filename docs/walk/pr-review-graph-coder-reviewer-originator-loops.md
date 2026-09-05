# Walk: the PR-review graph — the design-to-main state machine

The PR-review graph is the process a code-design goes through to become merged code: who codes it, who reviews it, what each hands to whom, and when each loop ends.

8 items. Each item ends with a recommendation: Y approves it, N disapproves, D pushes it to the end of the walk.

---

## Item 1.1 of 8: The nodes

**No agent persists across a pass.** Every node instance receives files, does one task, and ends. Nothing crosses a pass boundary except files. Four things later in this walk are consequences of that one rule rather than separate decisions: the validator exists so a burned producer is cheap to discard, the dispositions record exists because nothing else carries between passes, the escalation packet exists because no agent holds the history, and the numbering bounds passes rather than agent lifetimes.

The user is the exception, and the only one. He is the same person across every pass. That is why he is a gate rather than a node, and why a cap of three restarts is really a cap on how many times the machine spends his attention, which is the one input it cannot manufacture.

The roles:

- **The code-design node** is a conversation between the user and a fresh agent. It produces the code-design, and it is the only place what it promises can change. On a restart it is a new conversation carrying the accumulated code-design issues, not a waiting owner being woken.
- **The contract writer** writes the contract from the code-design.
- **The coder** builds the component from the code-design and the contract.
- **The test-code-design writer** builds the test-code-design from the code-design and the contract. The user ruled that the test-code-design is its own document and that the coder does not write it.
- **The test coder** builds the tests from the test-code-design.
- **The code reviewer** and **the test reviewer** read a prose parent and the code built from it, and may reject either. Item 4 gives their packages.
- **An arbitrator** is any node with two input connections. Item 6.
- **The user** is a node, not only a gate: he reviews all final prose. A prose document goes cold read, then his review, then it lands.
- **A validator** sits on the edge into an expensive node and asks one question: can the next node complete its task with these inputs. Item 2.4.
- **The merge-lane seat** merges. The graph runs inside the existing lane, not beside it.

Beside the graph, and not walked here: a GHI-knowledge agent that answers for the issue tracker, a wiki-knowledge agent to follow it, and possibly a liaison agent that headless agents use to reach the user. The user ruled it is too soon to codify any of this in `CLAUDE.md`.

The graph's shape, and two words it needs. An edge carries a **package**; a package holds one or more **files**. A pull request is a package, which is why one word for both reads ambiguously.

Every node has exactly one output connection. That is about the connection, not the files: a coder writes many files, a walk writes four, and all of them travel in one package to one destination.

Every node has one input connection, except an arbitrator, which has two. A reviewer reading a code-design and the code is a one-input node, because both arrive in one package. Two input connections means two packages from two producers, and a node with two is an arbitrator by definition (item 6).

A node may be composite. From outside it is one node with one input and one output; inside it may fan out to many parallel sub-nodes and fan back in. The cold read is one of these, running several independent reviewer cells and merging their reports into a single finding set.

Continued in 1.2.

---

## Item 1.2 of 8: The files

The files, named for the component X and the agent that wrote them:

- `X-coder1-code-design-notes.md` — everything the coder found in the design, nits and non-nits alike, each labelled. A non-nit fails the step: the file goes to the design node and the coder stops. Nits alone pass it: the file goes to the design node when the loop closes, as maintenance input.
- `X-reviewer1-notes.md` — the reviewer's findings, on the same rule. Nits and implementation findings go back to the coder; a finding that changes the code-design's promise fails the step and goes to the code-design node.

Running example for the rest of this walk: the topic-branch creation script, `scripts/start-topic-branch.py`, which creates a topic branch at current `origin/main` so a second topic cannot be based on the first. Its [code-design](file:///Users/el/agents/reboot-test/docs/issues/238-topic-branch-creation-script-design.md) was cold-read three times on 2026-09-02, and one of those rounds found the defect item 2 uses. Nothing in it is built yet.

No decision here. This item names the parts the rest connects.

---

## Item 2.1 of 8: The coder's first move — stop or continue

The coder does not review the code-design first. It starts the work. The rule is: **if you cannot complete your task because your inputs or your instructions are defective, report those defects and stop.**

That has no inspection step in it, which is the point. A node asked to evaluate its inputs will find something and then lean on it. A node asked to do its task discovers a defect only by hitting it, and what it reports is what actually blocked it.

The contract is everything about a component that a caller can observe without reading its code. A caller is anything outside the component that invokes it or reads what it leaves: the agent or script that runs it, its tests, the next command in a chain. Anything you would have to read the source to know is implementation, and a defect there is a nit. Item 2.2 gives the form the contract is written in.

The topic-branch script's code-design gave a concrete case, and it is one this rule would have caught the same way it was caught in life. The design said `git merge --ff-only origin/main` would refuse when a seat's branch carried stray commits, and called that the safety net. Nobody found that by reading. It was found by building it in a throwaway repository and measuring: when the branch is strictly ahead of main, the command prints "Already up to date", exits 0, and the stray commit rides into the next topic branch. The safety net was not one. A coder cannot complete a task whose central mechanism does not work, so it writes the defect to `X-coder1-code-design-notes.md`, hands it to the design node, and stops.

A gap blocks the same way. If the code-design is silent on something the caller would observe, an exit code for a case it never mentions, the coder cannot finish without choosing, and choosing is the design node's to do.

Each reported defect carries a failure scenario: which caller does what, and what breaks. That is what makes it a blockage rather than a preference.

Anything the coder worked around and still finished is a nit, recorded in the same file, and the work continues.

Ruled: a node reports defects in its inputs or instructions only when they stop it completing its task, and reports what blocked it.

---

## Item 2.2 of 8: The form a contract is written in

The contract is a numbered list in five groups, so that "does this change the contract" is answered by looking at the list rather than by judgment.

The three groups are Design by Contract's: preconditions, postconditions, invariants. Postconditions are split in two, because a script's exit code and the state it leaves are checked by different assertions.

- **I, inputs.** A precondition on what the caller supplies: arguments, options, environment. One clause each, with what makes it invalid.
- **P, preconditions.** What must already be true and the component does not create. Each is checked, with its refusal, or declared unchecked.
- **O, outputs.** A postcondition on what the caller receives per case: exit status, standard output, standard error.
- **E, effects.** A postcondition on what is different after a successful run.
- **U, unchanged.** The invariant: what is the same after a run, and which runs it covers.

Four rules an agent can follow without judgment:

1. One clause, one sentence, one observable. The sentence count is checkable by a program; the observable count is not, and belongs to the agent check.
2. Every clause names how a test sees it: what the test runs and what it compares.
3. If violating it cannot be caught by a failing test, it is not a contract clause. It belongs in the code-design.
4. A refusal is a P clause and an O clause, numbered together.

The topic-branch script, abbreviated: **I1** exactly one argument, a topic name not beginning with a dash. **P1** the working directory is inside a git checkout; unmet is refusal row 2. **O1** success is exit 0 and one stdout line, `<name> created at <sha> (origin/main)`, the sha unabbreviated, stderr empty. **O2** a refusal is exit 1, stdout empty, stderr's first two lines naming the fact and the next action, git's own message verbatim after them. **E1** on success the branch exists at `origin/main`'s commit and HEAD is on it. **U1** on refusals from rows 2 through 7, HEAD, the working tree, the index, and every ref under `refs/heads/` are unchanged; remote-tracking refs, `FETCH_HEAD`, and the object store are excluded.

This makes the routing mechanical. A contract finding changes the text of a clause or adds one. An implementation finding changes no clause but makes a test for one fail. A nit does neither.

One case needs a rule of its own, because it is common rather than rare: the contract and the code disagree, and either could move. The code-design decides which. If it settles the point, the side that contradicts it changes. If the code-design is silent, it is a contract finding and goes up to the design node, because nobody has decided yet and no agent below may decide for them. The same rule covers a clause that is simply missing.

Continued in 2.3.

---

## Item 2.3 of 8: Accepting a contract

The contract writer does not audit the code-design first, any more than the coder does. It writes the contract, and if it cannot — because the code-design never says what the component promises on some path — it reports what defeated it and stops. A contract only pins down a code-design that is already solid, and the way that is discovered is by trying.

The contract is then checked against a fixed list, written once in the graph's own design and never generated per component. That fixed list is what stops the regress: a contract needs acceptance criteria, and if those were themselves written per component they would need their own, forever.

Each check names its enforcer, and each enforcer is a state the contract passes through.

**`contract-program-check`** — a program checks these, fast and reliably. Every clause is numbered and in one of the five groups. Every clause is one sentence. Every refusal has both a precondition clause and an output clause. Every output clause names an exit status. Every clause names a test.

**`contract-agent-check`** — an agent checks these, slower and less reliably. Each clause states exactly one observable. No clause mentions the component's internals. No two clauses contradict. Every input has a stated invalid case. The invariant clauses say which runs they cover. Every exit status named in the outputs is produced by some stated condition. The test a clause names would fail if that clause were violated, which a program cannot tell: it can confirm a name is present, not that the named test proves anything.

**`contract-user-check`** — only the user can check this: whether this is the right boundary for the component. Whether anything the callers need is missing moved to the validator in item 2.4, because an agent can settle it and the user is a gate.

The contract review has two ways to fail, not one. It can reject the contract, which goes back to the contract writer. It can also reject the code-design the contract rests on, which goes to the design node and reopens everything below it. A reviewer that could only reject the contract would keep rewriting clauses against a code-design that cannot support any of them.

The scheme generalizes: `code-design-program-check`, `tests-agent-check`, and so on.

Failure routes by which check failed, so the classification is the remedy. A program-check failure goes back to the contract's author as a mechanical fix and does not count as a restart. An agent-check failure goes back as a rewrite pass, and it does count. A user-check failure goes to the user immediately, because no agent can rule on boundary or intent. Three passes, then escalate, as everywhere else.

Ruled: the five-group form with the standard names, this fixed acceptance list, the three state names, and both back edges to the code-design — from the contract writer and from the contract review.

---

## Item 2.4 of 8: The validator

A reviewer asks whether the thing in front of it is correct. A validator asks a different question: **can the next node complete its task with this?** Those come apart both ways. A code-design can be correct and insufficient, silent on something the coder needs. It can be sufficient and wrong, as the topic-branch code-design was.

The validator exists so the consuming node never has to look, and so it never has to be thrown away. A coder that hits a defective code-design is burned: when the corrected code-design arrives you want a fresh unbiased agent, so that execution is discarded. The validator absorbs the exposure, so a rejection costs a validator rather than a producer. It is cheaper too, because judging sufficiency is a smaller task than discovering insufficiency halfway through producing.

It runs on the edge into an expensive node and produces one destination: `advance`, or back for another pass.

It is a one-input node, and stays one however its criteria grow. A validator asking whether the coder can work from this contract given this code-design needs both, and gets both in one package, assembled by the machine before the validator sees it. Two input connections means two packages from two producers, which is an arbitrator; several files in one package is not that.

For a contract the question is whether it can be executed, vetted, or validated as written, and item 2.3's checks are its criteria. That also takes half of `contract-user-check` off the user. Whether anything the callers need is missing is the validator's own question. Whether this is the right boundary is judgement and stays with the user. He is a gate, so a state that queues him a question another node could settle costs the machine time it need not spend.

A validator firing consumes no pass number. It is a refusal to start a pass rather than a pass, and only a producer's output consumes a number. The loop is still bounded, on the far side of the edge: a rejection sends the producer to its next pass.

Its yes and its no are not equal. A rejection cites something observed, a clause naming an interface that does not exist, and blocks on its own. An approval predicts that another agent will succeed, which the validator cannot know, so it carries exactly the weight of the criteria it applied, and it names them. That keeps the growth path honest: adding a criterion visibly increases what an approval rules out, and when a coder later fails on a code-design that validated, the named criteria show which check was missing. That is how the criteria set earns its next member.

It does not replace the blockage rule. The fast-forward defect would have passed validation, because the code-design was coherent and sufficient to code against. Only building it revealed it was wrong.

The risk to design against: a validator that judges quality is a second reviewer at doubled cost. The single question is the whole guard.

Ruled: the validator is a node, with asymmetric weight and criteria named in every approval, no pass number of its own, item 2.3's checks as the contract validator's criteria, and `contract-user-check` narrowed to the boundary question.

---

## Item 3 of 8: The two loops and their order

Each loop runs on the stopping rule the user already adopted: a review round ends the loop when it produces no finding that changes a line of code or a line of test. A finding is a report with a failure scenario.

There are two loops. The code-design-and-code loop: coder, code reviewer, fix, review again. The test-plan-and-tests loop: test coder, test reviewer, fix, review again. Everything this walk says of the code reviewer applies to the test reviewer, with one difference: the test path has a second document above it, so the test coder and the test reviewer can fail the test-code-design as well as the component design. A test-design defect goes back to the test-code-designer, who owns that document. Every role in either loop reports a component-design defect to the design node.

The coder and the test coder work from their prose parents alone and never read each other's output. A coder who can see the tests writes to the tests instead of the contract; a test coder who can see the code tests what the code does instead of what the design promises. The code review is where the two lines first meet.

One guard sets the order: from the second round on, the code reviewer proves a finding by a failing test, or by a reproduction by hand where no test can reach it. That needs the tests to exist by the code loop's second round.

So the sequence is:

1. The coder reads the design and makes the stop-or-continue call of item 2. It goes first because a stop invalidates the test loop too: the test cases derive from the contract, and a contract defect means the test-code-design must also change.
2. The test-code-design writer writes the test-code-design; then the test coder and the coder work in parallel from their two prose parents. The test loop runs as soon as the tests exist.
3. The code review loop runs the tests. From round two on, the run is the round: the suite passes and a deliberately broken copy of the code, the red witness, fails it.

For the topic-branch script: the coder finds nothing that fails item 2's test, writes its nits, and starts; the test coder starts at the same time; the tests are there for the first review round.

Recommendation: adopt this order — stop check first, then test code and code in parallel and separated, then a code review that runs the tests. Y, N, or D.

---

## Item 4 of 8: What the reviewer receives

Prose always precedes code. The code-design and the contract are prose, and the code comes from them; the test-code-design is prose, and the tests come from it. So a reviewer's package always holds a prose parent and the code built from it, and the reviewer may reject either.

The code reviewer's package: the design, the contract, and the code. The test reviewer's: the code-design, the contract, the test-code-design, and the tests. Without the contract neither can tell a promise that is wrong from an implementation that breaks a promise, which is the whole sorting. Nothing else is in the package: not the coder's notes, not the other line's files. Only the arbitrator gets everything.

The coder's notes have one reader, the design node, after the loop closes. They are the material for the code-design maintenance item 5.2 assigns: the design catches up from what was decided, and the coder's nits say what was decided at the keyboard.

Why the reviewer does not see them. A reviewer reviews the code against the contract, so a deviation no caller can observe is not a finding and costs no round; the notes would buy nothing there. And a note that says "I chose X because Y" invites the reviewer to accept X. Nobody intends that, which is the point: this fleet's failures are accidents between cooperative agents, and priming a reviewer with the author's reasoning is one.

Example: the code-design says the script checks for a ref-path collision, where a branch `foo` blocks creating `foo/bar`. The coder chose `git for-each-ref refs/heads/` over the code-design's wording and noted why. The reviewer, reading the code cold, either finds the check correct or finds a case it misses. The note would not have helped with either.

Ruled: each reviewer receives its prose parent and its code only; only the arbitrator gets everything; the coder's notes go to the design node when the loop closes.

---

## Item 5.1 of 8: What a review pass produces

A reviewer reads its package — a prose parent and the code built from it — and writes one notes file. It never edits what it is judging. Each entry is a concern with a failure scenario, and it may carry a proposed fix or a mitigation. A fresh agent at the destination reads the proposal and decides.

The pass sets exactly one machine-readable value: **the destination**, meaning where the work goes next. Three kinds of value. `advance`, forward to the next node. The name of an upstream node, back to a fresh agent there. Or `user`.

Everything else is evidence, not state. What the verdict was, where the fault probably sits, whether the work is salvageable: all of it goes in the notes as prose, for the next agent and for the user. None of it is a field, because nothing in the machine switches on it. One representation, and it is the one the machine uses.

Only nits sets `advance`. Any substantial issue sets an upstream node.

Which upstream node is the sorting the rest of item 5 is about. Back to a fresh agent at the same node when the code is wrong. Back to the prose parent — the code-design, the contract, or the test-code-design — when what the code was built from is wrong. The rule when they disagree and either could move: the design decides, and if the design is silent it goes up, because nobody has decided yet and no agent below may decide for them.

`user` is a destination like any other. No node speaks to the user directly; it sets the destination and the machine assembles and delivers the packet. Any node may escalate, and an escalation is a transition rather than a side channel.

Continued in 5.2.

---

## Item 5.2 of 8: Input complaints, nits, and what carries between passes

**A node that proceeds says nothing about its inputs.** Not a finding, not a tag, not a file. A node that finishes its task had no blocking defect, so it reports on its own output only. The reason is not the review loop, which a separate channel would have fixed. It is that an agent asked what is wrong with its inputs will find something, and having found it will lean on it while doing the work it was actually given.

**A node blocked by its inputs reports why, in full.** It produces nothing, so explaining is its whole output: what it could not complete, the evidence, and the destination. There is no divided attention, because there is no other work to divide it from.

So prose about a code-design has exactly two readers who may act on it. The code-design review node, where the prose is the thing under review and finding fault in it is the job. And the arbitrator, which reads everything relevant and is placed to see that an ambiguous sentence is why code and tests diverged. `CLAUDE.md`'s rule that a reviewer reports nothing about `docs/` prose is the same rule seen from the code reviewer's seat.

**A nit** is real, correct, and does not matter to whether the change works: a variable named `tmp` where `candidate_path` reads better. The test: if it were left forever, would any caller, test, or user observe a difference? No means nit. Nits alone set `advance`. The guard that makes this safe: a nit carries no failure scenario, by definition, so a finding that has one cannot be labelled a nit however small the fix. When in doubt, label up. An under-labelled defect costs a green suite and a wrong result, which is what [pull request 223](https://github.com/nedschorus/nedschorus/pull/223) shipped: 143 passing tests and a wrong answer.

**What carries between passes.** Every agent is fresh, so each pass writes a dispositions record in three classes: findings applied, findings rejected with the reason, and findings touching text the user has already ruled, quoted with the ruling and not reportable again. The third class is the one that does the work. Without it a fresh reviewer re-raises what the user decided, and the pass counter climbs for a reason that was never about the code. The MD-skills seat measured this: five cold-read rounds in one day where each round's fixes produced the next round's findings, until it marked the user's rulings as settled.

Recommendation: adopt item 5 as a whole — one destination per pass; a node that finishes says nothing about its inputs and a node blocked by them reports what blocked it; nits alone set `advance`, with the labelling guard; and a three-class dispositions record carries between passes. Y, N, or D.

---

## Item 6 of 8: The arbitrator — when two edges arrive at one node

A conflict is not something an agent declares. It is two packages arriving at one node from two producers, which the machine can see for itself. A node with two input connections is an arbitrator; that is what the shape means, and it needs no judgment to fire. Counted in the graph between nodes, not inside a composite one.

One distinction the shape does not give you: a node that presents disagreement is not arbitrating, a node that resolves it is. The cold read's merge keeps both readings when two cells contradict, each in its own words, and lets the reader see the disagreement. That is aggregation. Arbitration exists to produce one answer where there were two.

Two shapes of it. Code and test results converge on the same node and disagree: the suite fails, and the code, the tests, or the two readings of the contract could each be at fault. Or two changes arrive at the same file with different content.

An arbitrator handles both. What makes it different from the nodes that fed it is its inputs: it reads everything relevant, not only the two packages it was called to settle. The code-design, the contract, the notes from every prior pass, the test results. That wider view is why it can rule where neither party could, and it is closer to what a person does than to what a reviewer does.

It produces the same one field every node produces, a destination, plus its notes. **An arbitrator fixes what its ruling already determines, and hands off work its ruling merely implies.** A merge collision: the ruling is the merged text, so it writes. A test asserting something the contract does not promise: the ruling names the correct assertion, so it fixes. Code that fails a test because the code is wrong: the ruling names the side but does not determine the implementation, so a coder writes it.

The limit is scale, not authority. Whoever judges should not author what it judged, but that buys nothing here, because every output goes to an independent reviewer anyway and an arbitrator's fix is reviewed like any other creation. Forbidding it would only discard the reading that produced the ruling. What an arbitrator genuinely cannot do is production work of unknown size: it is instantiated to answer a question, with a package assembled for judging.

If it cannot rule, the destination is `user`.

For the topic-branch script: the tests expect exit 3 on a stray commit, the code exits 2. The arbitrator reads the code-design, finds it names exit 3, and the destination is the coder. Had the code-design been silent, the destination is the design node, because nobody decided.

Numbering bounds it. Every pass carries a restart count, 0 to 2, and a pass within it, 1 to 3. A loop that has not closed at pass 3 goes to the arbitrator; a third restart sends the component to the user. It arrives as a conversation, not as a report to a reader: the design began in one, and a code-design that has failed downstream resumes in one, with a fresh agent and the accumulated issues.

The pipeline already contains one under another name. The node that reconciles accepted code and tests from separate work items takes two input connections from two producers and resolves a conflict. It fits the definition exactly, so this is a shape already present rather than a new kind of node.

Ruled: arbitration is triggered by two input connections; the arbitrator reads everything relevant; it fixes what its ruling determines and hands off what its ruling merely implies.

---

## Item 7 of 8: The two guards

Two guards keep the sorting from being gamed.

**From round two on, the run is the round — for findings about the code.** After the first round the question is not "is there anything to say about this code," because there always is, but "does the suite pass, and does the red witness turn red." A reviewer who finds a real defect in the code after round one demonstrates it with a failing test, or with a reproduction by hand where no test can reach it.

That standard does not apply to rejecting the prose parent, and cannot. The tests descend from the code-design, so the suite is no oracle for a defect in the code-design that produced it. A reviewer rejecting the code-design, the contract, or the test-code-design carries a failure scenario instead, naming the contract-promise that is wrong or missing, which is item 2.1's standard applied by a reviewer.

**The user reviews all final prose, after the cold read.** A prose document is not finished when its cold read is: it goes cold read, then his review, then it lands. He is a node in that path, not only a gate on it. Operationally the document is opened on his Mac for him to read.

**No fresh cold read of a code-design unless the contract changes.** A contract finding earns one. Nothing else does, however much the text moved. A cold read of a code-design whose behavior is already pinned by tests is the never-ending prose loop restarting under another name.

Ruled: both guards, with the first scoped to findings about the code.

---

## Item 8 of 8: Summary and the next step

What this walk decided:

- **Shape.** An edge carries a package; a package holds files. Every node has one output connection and one input connection, except an arbitrator, which has two. A node may be composite. No agent persists across a pass: every instance receives files, does one task, and ends, and nothing crosses a pass boundary except files. The user is the only continuous participant (item 1).
- **Blockage, not inspection.** A node does not audit its inputs. It does the work, and if it cannot finish because its inputs or instructions are defective, it reports what defeated it and stops. A node that finishes says nothing about its inputs (items 2.1, 5.2).
- **The contract**, written in five numbered groups from Design by Contract, accepted against a fixed list at three states, `contract-program-check`, `contract-agent-check`, and `contract-user-check`, the last narrowed to the boundary question alone (items 2.2, 2.3).
- **The validator**, one input, no pass number, rejection blocks and approval carries the weight of the criteria it names (item 2.4).
- **Two loops**, run separated: the coder and the test coder never read each other's output, and the code review is where the two lines first meet. The test path can also reject the test-code-design (item 3).
- **Packages.** The code reviewer gets design, contract, code. The test reviewer gets design, contract, test-code-design, tests. Either may reject the code or the prose parent (item 4).
- **One field per pass**, the destination. Everything else is evidence in the notes. Nits alone set `advance`. A three-class dispositions record carries between passes, its third class being text the user already ruled (item 5).
- **Arbitration** on two input connections; it fixes what its ruling determines and hands off what its ruling implies (item 6).
- **Two guards**, the first scoped to findings about the code. And the user reviews all final prose after its cold read, as a node in that path (item 7).

The next step is two components. A state-machine design, not in `CLAUDE.md`, defining states, transitions, file names, numbering, and each role's package, cold-read and then reviewed by the user before it lands. Then a Python driver built from it, with its own contract and tests. The topic-branch creation script is the driver's first run.

Two riders: the labelling sentence goes to the reviewer instructions on [issue 210](https://github.com/nedschorus/nedschorus/issues/210), and the design must cite the objective page's sections rather than the current file path, which is being split.

Ruled: write the state-machine design, cold-read it, open it for the user's review, then build the driver from it, run the topic-branch script build through it, and file the labelling rider.
