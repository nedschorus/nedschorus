# Walk: the state-machine design's cold read — what four reviewers found

The state-machine design went through the cold-read grid. Four reviewers returned 236 findings and no clean sections. This walk is what they found and what I propose to do.

8 items.

---

## Item 1 of 8: The verdict — rewrite, not patch

The grid ran four reviewers against [the design document](file:///Users/el/agents/reboot-test/docs/cross-project/design-to-main-state-machine-design.md): two at floor tier, two at good tier. Every one of them reported findings in every section. The good-tier Claude cell put it plainly at the end of its report: clean sections, none.

The counts, by cell:

| Cell | Model | Findings |
| --- | --- | --- |
| codex floor | gpt-5.6-luna, xhigh | 58 |
| claude floor | sonnet-5, high | 26 |
| codex good | gpt-5.6-sol, xhigh | 75 |
| claude good | opus-5, high | 77 |

That is not four reviewers each finding a different small thing. They converge. Three of the four independently found the same contradiction between a node that says nothing about its inputs and a node that records a worked-around problem as a nit. Three found the restart counter running 0 to 2 while escalation triggers on a third restart. Three found the code reviewer being told to run tests that are not among its inputs.

My diagnosis, and it is mine rather than theirs: **I wrote a summary of what you ruled, and you asked for a specification.** The rulings are all in there and they are correct. What is missing is everything that turns rulings into a machine. That single gap produces most of the 236.

The rest of this walk takes the findings in order of how much they change.

No decision here.

---

## Item 2 of 8: "The machine" is undefined, and you ruled it does not exist

The deepest finding, from the good-tier Claude cell, is that **"the machine" is the busiest actor in the design and is never defined.**

It appears at eight places. The machine assembles a validator's package before the validator sees it. The machine maps a destination to a next node. The machine detects two packages arriving and calls that arbitration. The machine counts restarts and passes. The machine assembles and delivers the escalation packet, because no node speaks to you directly.

Every one of those is load-bearing. And you ruled, in the other window, that there is no global controller: only the state machine with nodes, and how they connect is undefined.

So the thing every routing sentence depends on has no owner, and I raised it as an open design question.

It is not open. You answered it twice already, in two standing decisions, and neither merge-lane nor I noticed until it went looking. Decision 13 says what belongs in deterministic code: permissions, state transitions, counters, validation, repeatable transforms, and promotion. That is the machine's job list almost word for word. Decision 7 says the state machine is logically persistent rather than process-immortal. Together: the machine is the state machine, and the state machine is a program.

What was missing is a sentence saying so out loud, and a name. Both arrived while this item was on the table. Merge-lane reports you named it: the **design-to-main workflow** is the process, the **design-to-main state machine** is the program that runs it, and the nodes are its states. Decision 7 now reads that the state machine is logically persistent rather than process-immortal, that it is a program, and that it assembles each node's package, routes on the destination a node returns, counts passes and delivers escalations. That answers this item's finding by name rather than by inference from decisions 13 and 7. It reached me through merge-lane rather than from you, so a Y here confirms it as yours.

The consequence is sharper than the naming. **The machine is code, so it holds no judgement.** Anywhere my document has the machine deciding rather than routing is a defect, and I will sweep for those specifically rather than assume the cold read caught them all under other headings.

**And it settles where the cold read lives, which I had as a separate open question.** Your point is that the cold read has to be coupled to the writer, because only the writer knows what they were trying to say, even if they said it badly. Follow that through this item and the placement stops being a preference. If the machine routed a document out to a cold read, the report would come back to a *fresh* agent, because no agent persists across a pass. A fresh agent cannot tell whether the reader understood what was meant — it does not know what was meant either. All it can do is smooth whatever reads badly, which is the prose loop with extra steps. **So the machine cannot own the cold read at all.** Not by preference: routing it destroys the comparison that makes it work. The cold read sits inside the writing node, its report returns to the agent that wrote the draft, and the node emits when that writer is satisfied, one or two iterations in.

That generates a constraint this document does not currently state: **inside a node, the writer persists across its own cold-read iterations.** The no-agent-persists rule bounds passes, not iterations within a single node's execution, and nothing says so. Left unstated, an implementer could hand the cold-read report to a fresh agent and destroy the mechanism while following every written rule.

Recommendation: the rewrite says the machine is the design-to-main state machine and it is a program, points at those two decisions, and every place it currently decides becomes a place a node decides and it routes. It also says the machine does not own the cold read: each prose-producing node contains one, its report returns to that node's writer, and the writer persists across those iterations. Y, N, or D.

---

## Item 3 of 8: There is no state machine in the state-machine design

You asked for states, transitions, file names, numbering, and each role's package. The document has file names, numbering, and packages. It has no state list and no transition table.

Two reviewers found this from opposite ends. One said the state machine cannot be run without knowing which node follows which. The other said the title promises a path to merged code while the node table stops at reviews and rulings, so there is no terminal state that reaches main at all.

They are both right. The document names states it never lists: the code-design review node, the node that reconciles code and tests, and the three contract check states. Each is routed to somewhere in the prose and none appears in the table headed "the nodes." The cold read was a fourth entry on this list until item 2, which took it off: it is not a missing state, it is a sub-node inside every prose-producing node, and it should never get a row.

The missing terminal state turns out not to be a gap. Merge-lane answered it from decision 14: there is one gate to main, the git-gatekeeper is the permanent path, and the interim pull-request lane holds until it is active. This machine is not that gate and must not become one. Its terminal state is one state, submit to the gate, and what happens after belongs to the lane and the gatekeeper design. The defect is that the document stops without saying so, leaving a reader unable to tell whether merging was forgotten or excluded on purpose.

**And you have already given me the first half of that table**, in the flow you sketched: you and an agent write the design, it is cold-read, you read it, and on your approval it fans out to `implementation-validator-node` and `test-design-validation-node` in parallel; passing those, it reaches `implementor-node` or `test-design-node`. That is four named states, one fan-out, and a user-review state, none of which my document has in this form. Two things it settles that the cold read had flagged separately: validators are named per edge rather than being one generic Validator row, and the design node's fan-out to several consumers is real rather than the defect item 4 calls it.

What I propose: the rewrite leads with a state table and a transition table. Every state named anywhere appears in it with its inputs, outputs, and successors, ending at submit to the gate. Your names are used as given rather than renamed. Where a state's composition is genuinely undecided — the reconciling node is the live example, since nothing has said what it receives — it appears with that noted rather than being left out.

Y to lead the rewrite with state and transition tables ending at the gate, N, or D.

---

## Item 4 of 8: The node table is wrong in ways that would stop an implementation

Six concrete defects, all found by more than one cell.

- **The code reviewer runs tests it does not receive.** Its row lists the design, the contract, and the code. The order says the code review runs the tests, and the tests come from a different producer.
- **The test coder must reject documents it never gets.** Its row lists only the test plan, and the text says it may reject the design too.
- **Nodes are routed to and absent from the table**, as item 3 said: the code-design review node, the reconciling node, and the three contract check states.
- **Your row admits only final prose**, while three other paths deliver you something else: the gate on the two designs, and the escalation conversation.

**Two of the original six were not defects, and your rulings retired them rather than my fixing them.**

- **"The code-design node has one output connection and three consumers"** is resolved, and I stated it loosely in item 3. The fan-out is real, but it is not the node's. Your shape rule is that a node has one output connection and one or two inputs. Your flow has the design reaching two validators in parallel. Both hold at once: **the node emits once, and the machine delivers that one output to both consumers.** Fan-out is routing, which is mechanical, which is exactly what item 2 says the machine does and the only kind of thing it may do. So the rule and the flow agree, and what my document lacks is the sentence saying delivery is the machine's rather than the node's.
- **"Non-arbitrator rows list several inputs while the shape rule allows one connection"** dissolves the same way, once two things stop being conflated. The code reviewer's row lists three documents; that is not three connections. The machine assembles a package and delivers it over one connection, so **documents-in-a-package and input-connections are different counts.** One or two inputs means one or two upstream nodes feeding it, not one or two files. My document says the machine assembles the package for the validator and never generalises it, which is what made these look like contradictions.

So: four real defects to fix, and two retired as misreadings of rules you had already given — though both retirements leave a sentence my document is missing rather than nothing at all.

None of what remains is a judgment call. All are mine to fix in the rewrite.

Y to fix the four and adopt the two clarifications as stated, N, or D.

---

## Item 5 of 8: The contract's group names break your own naming rule

The five groups are named I, P, O, E, U. The good-tier codex cell caught what I should have: `CLAUDE.md` says that names likely to be grepped get explicit, clear, precise, multi-part names. Single letters are the opposite of that, cannot be searched, and do not self-document. Worse, I and P both hold preconditions, so the two are not even distinguishable by meaning.

Three more defects in the same section:

- **"The three underneath" has no referent.** Five groups follow it.
- **"Every output clause names an exit status"** assumes every component is a process. The contract form was written for components generally, and a library function has no exit status.
- **The worked example cites "rows 2 through 7"**, which exist in the topic-branch design and not in this document. A dangling reference I carried across without noticing.

And one that cuts deeper: the contract is defined by **observability** and then narrowed by **testability**, and those are not the same set. A clause can be observable and not reachable by any test, which the document elsewhere admits when it lets a reviewer demonstrate a defect by hand.

Recommendation: rename the five groups to multi-part names, drop the exit-status requirement to an example, fix the dangling reference, and state which of observability and testability governs when they disagree.

Y, N, or D.

---

## Item 6 of 8: Five holes in the logic

These are places where the rules as written produce no answer or the wrong one.

- **A perfectly clean review cannot advance.** Only nits set `advance`, so a review with no findings at all has no exit. The best possible outcome is trapped.
- **The arbitrator invents intent.** Its table says that when a test asserts something the contract does not promise, the arbitrator names the correct assertion. If the contract is silent, that is a node below the design deciding an observable, which the document forbids everywhere else.
- **Arbitration triggers without disagreement.** A conflict is defined as two packages arriving. Two packages that agree would still trigger it.
- **A nit has three definitions**, in three places, and they do not match.
- **The round-two guard makes a reviewer write a test**, while the same document says a reviewer never edits what it judges. Demonstrating a defect with a failing test is producing.

Two more, which the cold read did not find. They came out of a question merge-lane put to me about whether a reviewer's right to reject a prose parent reopens the prose-change/code-change loop you raised at 19:21.

- **Line 200 is probably obsolete rather than incomplete.** It says a code-design gets no fresh cold read unless the contract changes, and it exists to stop the prose loop. Under the model you described — the cold read is a sub-node *inside* every prose-producing node, iterated once or twice before the node emits — there is no re-cold-read event inside the machine that is separable from a re-emission. The loop line 200 guards against cannot occur here, and the bound is the internal iteration count instead. A standalone cold read, the kind you trigger by hand on a design, lives outside the state machine. So the rewrite should either delete line 200 or restate it as a fact about standalone cold reads, and this document should not be where a project-wide rule about the cold read lives.

  Two things settled during this exchange and recorded so they are not relitigated: **decision 19 stands as approved**, and **"final" in line 206 is load-bearing and correct as written**. There are two triggers on purpose — the cold read fires on every prose emission, cheap and internal; the user's review fires on prose that is final and about to land. An earlier draft of this item proposed fusing them, which would have delivered him every intermediate emission. That was my error and it is withdrawn.
- **The code-design's validator is asserted and never enumerated.** The contract's checks are written out in full. The code-design's exist only by "the scheme generalises: `code-design-program-check`, `tests-agent-check`, and so on." That validator is the node that catches a code-design which is correct but insufficient, and it is the reason the never-re-read rule above is safe in this machine. It should not rest on an "and so on".
- **Which number a contract rejection increments is undefined.** A restart is "a redesign or an arbitration", and a contract rejection is neither by that wording. The bound still holds, because a loop that has not closed at pass 3 goes to the arbitrator and an arbitration is a restart. So this is a numbering ambiguity rather than a runaway: an implementer cannot tell whether a contract rejection burns a pass or a restart.

Recommendation: fix all seven. `advance` is set by any pass with no substantial issue, nits or none. An arbitrator that would have to decide a silent observable routes up instead. Two inputs makes a node an arbitrator; whether there is a conflict is what it determines. One definition of nit. A reviewer demonstrating by test hands the test to a fresh producer rather than writing it. The no-fresh-cold-read guard covers every prose parent, not just the code-design. And every rejection says which number it increments.

Y, N, or D.

---

## Item 7 of 8: Claims that overstate, and references that go nowhere

Two families, both cheap.

**Absolutes with ordinary counterexamples.** "A node asked to evaluate its inputs will find something." "Every output goes to an independent reviewer." "There always is." "Nobody found that by reading." "The validator exists so the consuming node never has to be thrown away," which the document itself then contradicts by admitting a validated design can still burn a coder. Each is fixed by deleting words, not by adding qualifiers.

**References a reader cannot follow.** The walk minutes, the AI-native architecture, its notes sections, the objective page, standing decision 4, "this fleet", "cell", "red witness", and the topic-branch design are all named without a path or a definition. For a document of lasting value that is a real defect: a future agent cannot check whether a departure was licensed, or reproduce the one worked example.

Recommendation: cut every absolute to what the evidence supports, and give every external reference a path or a definition. Where merge-lane warns a path is about to change, cite the section rather than the file.

Y, N, or D.

---

## Item 8 of 8: What the rewrite becomes, and what it lands into

**What the rewrite becomes.** A specification of the design-to-main state machine: a program that holds no judgement, assembles every package, delivers in both directions, runs the suite, and keeps three counters. It leads with a state table and a transition table, with a diagram checked against the table, and ends at two terminal states — submit to the gate, or loop you in. Your node names as given. The code-design in every package. A contract writer before the fan-out. Every node emits an explicit exit; every non-writer emits notes, a verdict and a destination; the arbitrator never fixes. Reviewers write their own tests and never see the suite. The cold read is inside every prose-producing node, reporting to its writer. One loop-in report type, cold-read, carrying your prior rulings. Count what is expensive. One definition of nit.

**Retired since the document was written:** `contract-user-check` (you are not a routine contract gate); "may approve without reading"; line 200; the code-review-is-where-the-lines-meet sentence.

**Vocabulary from elsewhere, used rather than reinvented:** *implementation* for what a producer builds (Write implementation, Write test implementation); and the coverage type you ruled on 2026-09-03 — **script, prompt, script-and-prompt, excluded** — for what a producer built. **One question:** that field was ruled for tests; does it also apply to what an implementor builds?

**Where it lands.** Into build step 1's GitHub issue as its pair, per merge-lane. Provenance and attestation fields are step 1's own work, and the document says so rather than adding them.

**How it is rewritten.** By the process you wrote into the cold-read skill tonight: fix what the readers found, record every finding not applied with its reason, commit each round naming the record directory, and walk the changes and the rejected findings with you. The second cold read hands the cells today's rulings — not intent — so they do not relitigate them.

**Open, not decided here:** parallel validators disagreeing (merge-lane's walk); the loop-in report's content (placeholder: prepare what you need, then cold-read); the arbitrator's route for an unreliable test (a rewrite detail); whether "pushed to main" means via the gate (your 4.2 rider); the campaign brief in this seat's tree, unrouted.

Recommendation: rewrite against items 2 through 7 as ruled, by that process, then a second cold read, then you.

Y, N, or D.
