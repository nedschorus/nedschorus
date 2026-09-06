# Minutes: the PR-review graph — coder, reviewer, and originator loops

Walk document: docs/walk/pr-review-graph-coder-reviewer-originator-loops.md
8 items after re-planning at item 3 (items 1 and 5 in two sub-steps each). Opened 2026-09-03.

What this walk is about, for someone who has not read it: the user set the
process a component design goes through to become merged code. A coder given
a design either stops and returns a design-issues file to the design's owner
(the originator), or notes minor issues in a design-nits file and continues; a
reviewer then reads design and code, and its findings drive a design-code loop;
the test design and test code form a second loop of the same shape. The user
called this the PR-review graph and asked to be walked through it. The walk
supersedes docs/walk/review-stopping-rule-findings-sorted-by-what-they-change.md,
whose rulings it carries: the stopping rule (a review round ends the loop when
it produces no finding that changes a line of code or test) was accepted
2026-09-02; a contract finding reopens both designs, uncontested; the cold
read's composition is delegated to the cold-read-research campaign.

## Item 1 — the nodes and the artifacts

presented 2026-09-03 → revised. No decision was asked; the user set four
rulings on the roles and files, all applied to the walk document:

- A test-designer role is added: an agent type that builds the test design
  from the component design. The test coder then builds tests from it.
- Beside the graph, not walked: a GHI-knowledge agent, a wiki-knowledge agent
  to follow, and possibly a liaison agent that headless agents use to reach the
  user. Ruled too soon to codify any of this in CLAUDE.md; item 7's design
  document is where it goes.
- ONE notes file per agent, not separate issues and nits files:
  X-coder1-design-notes.md holds nits and non-nits together, each labelled.
  A non-nit fails the step (file to the originator, coder stops); nits alone
  pass it (file travels forward with the code). The reviewer's file follows
  the same rule. The user said the earlier two-file sketch was unclear.

Item 1 was split into 1.1 (nodes) and 1.2 (artifacts) for length. The user
advanced with "y".

## Item 2 — the coder's first move: stop or continue

presented 2026-09-03 → accepted ("good enough for now. y"). The coder reads
the design before coding and stops only on a contract defect or gap that
carries a failure scenario, written as a non-nit in X-coder1-design-notes.md
and handed to the originator; everything else is a nit in the same file and
the coder continues.

Discussion: the user asked whether contract equals design (no: the contract
is the caller-observable part of the design; the rest is implementation, and
a defect there is a nit) and whether the project has a full definition of
contract (it did not — the word was used by example in the 238 design and by
a list of kinds in the walks). Definition adopted, "good enough for now", and
added to the walk document at item 2: the contract is everything about a
component a caller can observe without reading its code — inputs and required
prior state, exit status per case, stdout and stderr, state left behind, and
refusals with condition and message; the unobservable is implementation; a
test can only check the contract because a test is a caller; timing and exact
wording are contract only when the design promises them. The definition
carries into the design document item 8 commissions.

Item 2 SPLIT 2026-09-04 into 2.1 (the stop test, as ruled above) and 2.2 (the
form a contract is written in — new, open). The user's rulings that drove it:
contracts also carry invariants (things that must be true before, and things
that must still be true or unchanged after; irrelevant in most components,
noted where not), and the explication of contracts must be "AI functional,
clear, pragmatic, actionable by dumb AIs" rather than prose. Proposed form:
five numbered groups — I inputs, P preconditions, O outputs, E effects,
U unchanged (the invariant, naming which runs it covers) — with four
mechanical rules (one clause one observable; each names how a test sees it;
if a violation cannot fail a test it is design prose not contract; a refusal
is a P clause plus an O clause numbered together). Routing becomes
mechanical: contract finding changes a clause's text or adds one;
implementation finding changes no clause but fails a test for one; a nit
does neither.

Item 2.2 and 2.3 ruled 2026-09-04 ("y"). Adopted: the five-group contract
form, relabelled with Design by Contract's standard terms (preconditions,
postconditions, invariants; postconditions split into what the caller
receives and what changed, because different assertions check them); a FIXED
acceptance list, written once in the graph's design and never per component
— this fixed list is the base case that stops the contract-for-a-contract
regress the user identified; and three enforcement STATES per artifact.

The user's framing that produced this: rules divide into input rules
(creation instructions, i.e. a specification) and output rules (acceptance
criteria), and each is enforceable by code (fast, reliable), by an AI
(slower, less reliable), or only by a human (scarce, high judgement, low
precision, not parallelisable). The seat noted the first two are standard
under other names and the third axis is the useful addition.

STATE NAMES, user asked whether these need proper greppable names and
proposed Code-check / AI-check / Human-check or Contract-code-check. The seat
agreed on the principle, disagreed on two words with reasons, and the user
ruled "y" for the seat's: `contract-program-check`, `contract-agent-check`,
`contract-user-check`, generalising to `<artifact>-program-check` etc.
Reasons recorded: `code` is already an artifact class in CLAUDE.md so the
code artifact's tier would read code-code-check; `AI` is ambiguous when every
agent is AI, and `agent` is the project's word; `user` is the project's word
for the human. All six candidate spellings were grepped and none collide.

Failure routing by tier, adopted: a program-check failure is a mechanical fix
that does NOT count as a restart; an agent-check failure is a rewrite pass
that does; a user-check failure escalates to the user immediately, because no
agent can rule on boundary or intent. Three passes then escalate, as
elsewhere.

Two more back edges, user-ruled 2026-09-04 and applied: a contract only works
if the design under it is solid, so (a) the contract writer may reject the
DESIGN rather than write a contract against it — the same stop-or-continue
call the coder makes in item 2.1, one level up — and (b) the contract review
may reject either the contract (back to the contract writer) or the design
beneath it (to the originator, reopening everything below). Without (b) a
reviewer would keep rewriting clauses against a design that cannot support
any of them.

The user directed this seat to put the contract node to the merge-lane seat.
Sent 2026-09-04 to merge-lane-64: the node, the five-group form, the three
check states, and the user's back-edge ruling, with three questions — would a
contract in this form have changed a review round it has actually run (cite a
PR); is the contract-versus-implementation split mechanical enough to survive
a real reviewer; and what failure mode does it expect (this seat's guess:
clauses that restate the design, so the list grows without pinning anything
down). Its answer, 2026-09-04, summarised with what was done about each point:

- EVIDENCE, accepted. PR #162 ("The codex cells' own error code is
  distinguishable from codex's") wrote a prose exit-code contract, and its
  independent reviewer produced two findings, both about the contract's
  accuracy rather than the code: an unlaunchable codex exits 1 against a
  clause saying every code but 0 and 64 is codex's own, and "passed through
  unchanged" fails for a signal death (caller sees 247, not 128+N). Two
  readings follow: a real reviewer sorted contract from implementation with
  no routing rule in front of it, and that contract was written by the author
  in the same pass as the code, which is the shape the separate contract
  writer exists to prevent.
- THE SPLIT IS NOT MECHANICAL when contract and code disagree, because either
  could move; both #162 findings had that shape. Merge-lane's rule, ADOPTED
  and written into item 2.2: the design decides which side moves; if the
  design is silent it is a contract finding and goes up. The same rule covers
  a missing clause, which answers merge-lane's "contract-silent" third route
  (a live example is open on PR #246: stderr re-emitted with no trailing
  newline, no clause requiring one). No sixth outcome was added — adding a
  clause was already a contract finding — but the design-decides rule is what
  makes that routable rather than a judgement call.
- ITS EXPECTED FAILURE, accepted, and better than this seat's guess: the
  program check can confirm that a clause names a test, not that the named
  test would fail if the clause were violated, so a contract accumulates
  clauses pointing at tests that pass for unrelated reasons and reads as
  coverage while proving nothing. It cited two instances of that shape in its
  own record. Applied: the program check now only requires a name; the agent
  check carries "the test a clause names would fail if that clause were
  violated."
- "ONE OBSERVABLE PER CLAUSE" is the load-bearing property and was in no
  tier; only the checkable "one sentence" was. Applied: moved into the agent
  check.
- ON THE REJECT-THE-DESIGN EDGE it agreed, citing standing decision 4 of the
  AI-native objective (every node examines its inputs; a material upstream
  defect stops promotion and is reported with a recommended route). It named
  a hazard: two reject edges into the originator from adjacent states could
  arrive in one pass saying different things. This seat DISAGREED and told
  it so: the two edges are sequential, not concurrent — if the contract
  writer rejects the design no contract exists, so there is nothing for the
  contract review to review. They cannot both fire in one pass.
  MERGE-LANE WITHDREW this point on being told, saying it could not construct
  the concurrent case and did not believe one exists; the arbitrator stays on
  code against tests only.

Merge-lane's residue, raised as a question and adopted into item 6 as a
proposal for the user to rule on: since every agent is fresh, no agent holds
the history of prior rejections, so an oscillation is possible across passes
(0.1's review rejects the design for reason A, the originator fixes it, 0.2's
fresh writer rejects the revision for reason B that undoes A). The restart
number bounds it, but nothing said what the user RECEIVES at the bound.
Written into item 6: the escalation carries every numbered notes file in pass
order, which the numbering already totals, and the agent that triggers it
writes a covering page naming what conflicts. Three rejections as three
independent complaints are much harder to act on than the same three in
order with the oscillation named.

## Item 3 — the two loops and their order

presented 2026-09-03 → accepted ("I think so"), with three additions the
discussion produced, all applied to the walk document:

- Separation (user-set): the coder and the test coder work from the design
  alone and never read each other's output, because each would pollute the
  other; the code review is where the two lines first meet.
- A contract change invalidates code, test design, and tests together (user
  confirmed this is the reading).
- The test path is not identical to the code path: it has a second document
  above it, so the test coder and test reviewer can fail the test design as
  well as the component design; a test-design defect goes to the test
  designer. Every role reports a component-design defect to the originator.

RE-PLANNED here, 7 → 8 items. The user added the node the walk lacked: when
the code review's test run fails substantially, a fresh evaluator agent reads
code, tests, and results and routes to originator (redesign, always
available), test designer, test coder, coder, or both; capped at three
passes. The user ruled code-against-tests is the only two-agent conflict the
design can produce, so the evaluator is the one arbitrator and the earlier
originator-arbitrates rule (coder vs reviewer on contract-vs-implementation)
is dropped: the reviewer routes its own finding and a mis-route costs one
hop. New item 6 = the evaluator and the caps (seat's addition, pending: a
three-round cap on each loop too, escalating to the evaluator; "substantial"
defined by item 2's contract test). Guards become item 7; summary item 8.

## Item 4 — what the reviewer receives

presented 2026-09-03 → REJECTED as recommended, revised. The seat had
recommended the reviewer receive the coder's notes. The user objected: nits
do not matter to a reviewer, and the notes let the coder steer ("fool") the
reviewer. The seat conceded: a reviewer reviews code against the contract, so
an unobservable deviation is not a finding and the notes buy nothing, while
priming is a real accident between cooperative agents. Ruled: each reviewer
receives its design and its code only; the coder's notes go to the originator
when the loop closes, as the material for design maintenance (item 5.2).
User added: only the arbitrators get everything — every role but the
arbitrator sees only its own line's design and artifact.

While item 4 was on the table the user ruled two points on the caps of item
6, applied to the walk document:

- "Substantial" is not defined; "nit" is. What reaches the evaluator is a
  test failure that is not a nit, by item 5.2's test (left forever, a caller,
  test, or user would observe a difference).
- Caps are by NUMBERING, not a counter: every pass carries its number in the
  agent's name and file (coder1..3, test coders, evaluators, design
  revisions alike); three is the last number. A redesign restarts the coders
  at 1 but the design's own number climbs. Arbitrations that do not go back
  to the human are limited to 3; the theoretical ceiling is nine code passes,
  which the user judged unlikely given how many exits to the human precede it.
- The arbitrator (the user's term; "evaluator" dropped) reads design, test
  design, code, tests, results, and all notes; fixes nothing; writes one
  notes file with, per failing test, which side is wrong and the contract
  clause, then a routing with notes to originator (redesign), test designer,
  coder, test coder, or a combination. Numbering is two-part, user-set:
  restart count 0..2 then pass 1..3, e.g. coder-0.1, tests-1.2,
  arbitrator-2. Seat's refinement, applied: the first number counts restarts
  of any kind (a coder-stop redesign as well as an arbitration), so the
  bound holds on every path.
- Direction (user, mid-turn): the state machine is complex enough that it
  moves to Python. Applied to item 8's next step: a design document that
  defines the machine exactly enough to code, cold-read; then a Python driver
  with its own contract and tests; the 238 build is the driver's first run.

## Item 5 — what a review pass produces (5.1) and input complaints, nits, dispositions (5.2)

ACCEPTED 2026-09-04 ("Yes"). One destination per pass; a node that finishes
says nothing about its inputs and a node blocked by them reports what blocked
it; nits alone set `advance`, with the labelling guard (anything carrying a
failure scenario cannot be called a nit, however small the fix); and a
three-class dispositions record carries between passes — applied, rejected
with reason, and touching text the user already ruled, quoted and not
reportable again.

Earlier history of this item, kept:

Before 5.1 was ruled the user raised four corrections, all accepted and
applied: (1) a review pass has FIVE outcomes, not four — approved with
nothing found, approved with nits only, implementation finding, contract
finding, prose — and the driver switches on those; (2) reviewers return
concerns with optional PROPOSED fixes or mitigations and never edit code or
tests, or the reviewer becomes a second coder; (3) the term is
contract-promise, and a contract runs in both directions, inbound
(what the caller must supply) and outbound (what the component guarantees);
(4) "no caller can tell" means: anything outside the component that invokes
it or reads what it leaves — the running agent or script, the tests, the next
command in a chain — not the component's insides. The test: name an input for
which two implementations differ in exit status, output, or state. Refinement
recorded: a contract finding says the promise is wrong; an implementation
finding says the promise is right and the code breaks it.

5.1 presented 2026-09-03 → next (user confirmed the implementation example:
the reviewer records the non-nit finding and the next coder fixes it; neither
design moves). 5.2 presented; its decision on the four edges is OPEN.

Two side rulings while 5.2 was on the table:

- DECISION A, ruled → deferred ("y"). The seat proposed pulling the contract
  out of the design into its own numbered file, X-contract.md, so that
  "does this change a promise" becomes a diff the Python driver can check.
  The user's objection: this is a too-good-to-be-true pattern — when a step
  does not know what to do, it asks the step before it to have known
  everything — and doubted it would work. The seat conceded the completeness
  half (the topic-branch script's contract defect was found by building and
  measuring, not by writing a better contract up front) and kept only the
  bookkeeping claim. Ruled: DEFER the separate contract file until the
  topic-branch creation script has run through the graph once; decide from
  what that run measures — how often the loop bounces to the originator and
  on what.
- The contract is the component's boundary with the whole system (user's
  framing, confirmed): what it takes in, gives back, refuses, and leaves
  behind. The design is the inside: how the boundary is honored and why. They
  change for different reasons, and the contract can be written first because
  it is written from the callers' side.
- Naming: the user asked whether the running example should be called
  something like "git-script" instead of "238". The seat disagreed with that
  specific name (two parts, ambiguous among many git scripts, against
  CLAUDE.md's naming rule) and used the existing name throughout the walk
  document: the topic-branch creation script,
  scripts/start-topic-branch.py.

## Item 6 — the arbitrator: when two edges arrive at one node

presented and ACCEPTED 2026-09-04 ("y"). Arbitration is triggered by two
nodes routing to the same destination, which the machine detects without
judgement; the arbitrator reads everything relevant, not only the two
artifacts it was called to settle; it produces the same one field every node
produces, a destination, plus notes; it rules and routes rather than writing
the merged artifact or editing either side, because whoever judges must not
author what is judged; if it cannot rule the destination is `user`. Numbering
bounds it: restart 0-2, pass 1-3; a loop unclosed at pass 3 goes to the
arbitrator, a third restart goes to the user.

The seat flagged, and the user accepted with the item, that this differs from
the governing document, which has Integrate produce the merged artifact and a
separate root-cause node diagnose. Consequence still open in practice: the
merge itself is written by a fresh agent at the destination, not by the
arbitrator.

## Item 7 — the two guards

ACCEPTED 2026-09-04 ("y"), with the first guard scoped during the walk.

1. From round two on, the run is the round, FOR FINDINGS ABOUT THE CODE: a
   reviewer finding a real code defect after round one demonstrates it with a
   failing test, or by hand where no test can reach it. The scoping, found by
   this seat when the user generalised the reviewer's reject edges: this
   standard cannot apply to rejecting a prose parent, because the tests
   descend from the design and are no oracle for a defect in the design that
   produced them. A reviewer rejecting the design, contract or test plan
   carries a failure scenario instead — item 2.1's standard applied by a
   reviewer.
2. No fresh cold read of a design unless the contract changes. A contract
   finding earns one; nothing else does, however much the text moved. A cold
   read of a design whose behaviour is already pinned by tests is the
   never-ending prose loop under another name.

## Item 8 — summary and the next step

ACCEPTED 2026-09-04 ("y"). Next step ruled: write the state-machine design,
not in CLAUDE.md, defining states, transitions, file names, numbering and
each role's package; cold-read it; open it for the user's review; then build
the Python driver from it, with its own contract and tests; the topic-branch
creation script is the driver's first run. Riders: the labelling sentence
goes to the reviewer instructions on nedschorus#210, and the design cites the
objective page's SECTIONS rather than the current file path, which is being
split.


## 2026-09-04 — the walk collides with an existing design

The user said "That is incorrect" and pointed at the MD-skills seat and the
code-to-main pipeline design. That design is
docs/cross-project/nedschorus-ai-native-software-development.md, on main. Its
sections 5 (the universal node contract), 6 (the artifact pipeline step by
step), 7 (review and root-cause routing), 8 (test-failure policy) and 19
(standing decisions) already specify what this walk has been deriving.

WHAT THIS SEAT GOT WRONG, in the claim the user called incorrect: it told
merge-lane that every agent is fresh so no agent holds the history of prior
rejections and only the numbered files carry it. Standing decision 7 says the
master is logically persistent, not process-immortal, and that durable events,
artifacts, questions and decisions let any process restart. Standing decision
3 says an execution receives a package (task, pinned revision, governing
artifacts, instructions, evidence) and does not depend on a predecessor's
private conversation. CORRECTION, from merge-lane the same day: that reading is backwards.
"Logically persistent, not process-immortal" means precisely that NO process
holds the thread; the durable records do, and any process can be replaced by
reading them. So decision 7 supports this seat's original claim rather than
refuting it, and the reason given to merge-lane was wrong. The conclusion
still holds on its other reason alone: sections 7 and 8 already specify the
root-cause report's contents and already end at a human decision packet. The escalation packet
merge-lane and this seat treated as a gap is also already specified: section
8's round 3 is a "human decision packet", and section 7 lists the required
contents of a root-cause report.

OTHER CONFLICTS between this walk and the existing design:

- NAMES. The design names its nodes: Define work, Create design, Review
  design, Write code, Review code, Write test plan, Review test plan, Write
  tests, Review tests, Integrate, Build and test, Deploy, Production triage.
  This walk invented originator, coder, test designer, test coder, arbitrator.
  CLAUDE.md's naming rule says use the existing name. Also "test plan", not
  "test design".
- THE FIVE OUTCOMES contradict the design directly. Section 5's "Do not force
  all meaning into one state field" says pass, fail, nit and report-to-human
  are not mutually exclusive states, and prescribes four orthogonal
  dimensions: verdict, suspected location, disposition, artifact eligibility,
  with named convenience outcomes over them (PASS, PASS_SELF_HEALED,
  REVISE_LOCAL, BLOCKED_UPSTREAM, NEEDS_DECISION, RETRY_OPERATIONAL,
  FAILED_SYSTEM).
- THE ARBITRATOR is the design's root-cause node, already specified in
  section 7 with its authority limits and report contents. Section 8's rounds
  differ from this walk's: round 1 a code hypothesis with a regression
  witness, round 2 cross-artifact diagnosis, round 3 the human packet.
- THE CONTRACT is not a separate node there: section 6 says the design states
  the behavioral contract, and Create design's point of view includes
  interfaces and invariants.
- REVIEW DEPTH is proportional to consequence in section 7's risk table, not
  uniform.

WHAT THIS WALK PRODUCED THAT THE DESIGN DOES NOT HAVE: the five-group
contract form with its mechanical rules, the three enforcement states
(contract-program-check / -agent-check / -user-check) and the tier-based
failure routing, the restart.pass numbering, and merge-lane's design-decides
rule for when contract and code disagree.

Open for the user: whether the walk stops being a design and becomes a
reconciliation against the existing document.


## 2026-09-04 — provenance of the governing document, and its status

The user doubted the document was current and doubted it was on main. Both
checked, and both doubts were unfounded:

- It is on main. Commit 34c6598, "docs: add AI-native software development
  architecture", authored by Edward Lerner 2026-09-03 10:18 -0700, reached
  main through the merge of pull request #247. `git merge-base --is-ancestor`
  confirms it.
- It is current. Front matter says `design-as-of: 2026-09-03`, and no branch
  or seat holds a newer version: every seat's copy is byte-identical to
  main's (md5 0ecc97929b57dbf556e8c6ed1136daa0) and every worktree reports it
  clean.

The MD-skills seat reported that no design of that shape exists. Its grep
searched for this walk's invented vocabulary (originator, contract writer,
arbitrator, restart.pass), which the document does not use; it was told where
the file is.

STATUS IS MOVING, reported by merge-lane, which is walking the document with
the user right now:

- The user has ruled the document is the project's OBJECTIVE, not a plan, and
  that it splits into two pages: an objective page (central rule, standing
  decisions, project organization, accepted residuals, at high level) and a
  notes page carrying the detail, with front matter marking it possible
  implementation details, not prescriptive, not vetted, not maintained to
  match reality. Sections 5, 7 and 8 land in the notes half, so the material
  this walk would reconcile against is about to be explicitly
  non-prescriptive, and the path will change. Cite sections, not the path.
- The user is removing the controller/master from standing decision 7, in his
  words to merge-lane: there is no global controller, only the global state
  machine with nodes, and how nodes connect is undefined and irrelevant to
  the state machine. A replacement decision 7 is in front of him, unruled.

MD-skills' rulings from the user today, recorded because they bear on this
walk's open items:

- For the write-test-plan skill, in the user's words: a test returns nits or
  substantial issues; only nits is a pass, any substantial issue fails.
  Minutes at docs/walk/cold-read-terminology-pass-rulings-minutes.md item 1.
- A test case may add a HUMAN REVIEWER node, with a prompt saying what to
  look for and what responses are expected — the human inside the state
  machine, not only at escalation.
- The dispositions record that carries history between fresh rounds must mark
  which findings were the USER'S OWN rulings and therefore settled, or fresh
  reviewers re-raise what he already decided. MD-skills had to hand its
  triage agent the walk minutes to stop exactly that.
- Caution on the contract form: the user's consistent correction that day was
  that a qualifier or rationale clause in an instruction is dead weight, and
  a test that cannot be applied to one item on its own is not a test. Each
  contract clause must be checkable against the code alone.

MD-skills' own corrections after reading the document (it had searched for
this walk's role names, not the concept):

- Its nits ruling is narrower than first stated and does NOT conflict with
  section 5. "Only nits is a pass" is a convenience outcome over section 5's
  verdict dimension, not a fifth state; section 5's warning against
  collapsing four questions into one field is the more careful statement.
  This bears directly on this walk's five-outcome scheme, which is the same
  collapse.
- What its ruling adds that section 6 has no node for: a HUMAN REVIEWER
  inside a test case, with a prompt naming what to look for and the
  responses expected. Distinct from section 8's round-3 escalation packet.
- Concrete proposal against section 8, offered to this walk: a dispositions
  file per review round in three classes — findings applied, findings
  rejected with the reason, and findings touching text the user already
  ruled, quoted with the ruling and NOT reportable again. The third class is
  the load-bearing one. Its evidence: the terminology prompt went through
  five four-cell cold reads in one day, each round's fixes creating the next
  round's findings, until it marked the user's rulings as settled — the same
  failure mode CLAUDE.md's 2026-08-31 rule was measured on. Consequence for
  whatever counter section 8 lands on: it needs the settled set beside it or
  it counts rounds that were never about the artifact.


## 2026-09-04 — one field, and arbitration by convergence

Rulings from the user, applied to items 5.1 and 6:

- THE HUMAN IS AN ESCALATION, not a node inside a test. Any node may escalate,
  but never directly: the escalation goes through the state machine. So `user`
  is a destination like any other; the node sets it and the machine assembles
  and delivers the packet. MD-skills' human-reviewer-inside-a-test is not a
  separate mechanism under this ruling — it is a test case whose destination
  is `user`, with the notes saying what to look for and what answers are
  expected.
- THE CONVENIENCE LAYER IS REJECTED: "sounds like a mess waiting to bite us."
  Two representations of one fact drift, and then the machine and the notes
  disagree about what happened. This kills the seat's earlier recommendation
  to keep five named outcomes over section 5's four dimensions, and it also
  applies to that document, which defines four dimensions and then names
  outcomes over them.
- ONE FIELD, adopted ("close enough"): a review pass sets exactly one
  machine-readable value, the DESTINATION — `advance`, the name of an
  upstream node, or `user`. Verdict, suspected location and artifact
  eligibility become evidence in the notes, in prose, because nothing in the
  machine switches on them. One representation, and it is the one the machine
  uses. The user's nits rule maps onto it: only nits sets `advance`.
- ARBITRATION IS TRIGGERED BY CONVERGENCE, user-set: a conflict is two nodes
  routing to the same destination, which the machine detects without
  judgement. Two shapes named by the user: code and test results disagreeing,
  and two changes arriving at one file with different content. An arbitrator
  reads EVERYTHING relevant, not only the two artifacts it was called to
  settle, which is why it can rule where neither party could — "more like a
  human". If it cannot rule, it escalates.

Seat's addition inside that ruling, in item 6 and open for the user: the
arbitrator rules and routes but does NOT write the merged artifact, for the
reason a reviewer does not edit — whoever judges must not author what is
judged. A fresh agent at the destination does the work. This differs from the
governing document, which has Integrate produce the merged artifact and a
separate root-cause node diagnose; the user's model is one role triggered by
the graph.


## 2026-09-04 — the input-complaint channel

The user asked whether prose findings should be reported but ignored by the
state machine, with explicit tags (design-prose-issue,
test-design-prose-issue, contract-prose-issue), or not reported at all, and
whether reporting would encourage writers and reviewers to blame the design,
test plan, or contract prose.

The seat first recommended report-but-unreachable: a separate prose file per
artifact, outside every coder's package, readable only by the originator in
maintenance and by the arbitrator. The user rejected the reasoning: it stops
the feedback loop but not blame-shifting, because asking an agent what is
wrong with its inputs pollutes its context whether or not the complaint is
acted on. He noted he has no hard data and has seen no reputable test report.

The seat WITHDREW its recommendation and agreed: a separate file is still a
channel, a channel must be named in the prompt, and naming it is the priming.

RULED, with the user's completing correction, then sharpened again by him:
the seat's "one binary test" was still an inspection step and was wrong. The
rule in the user's words is "if you can not complete your task because your
inputs or instructions are defective, report those defects." There is NO
up-front examination. The node does the work; a defect surfaces as a
blockage, discovered rather than sought, and what it reports is what actually
blocked it. Note "instructions" as well as artifacts. A node that FINISHES
says nothing about its inputs — no finding, no tag, no file. A node that REJECTS its inputs reports why in full: it
produces no artifact, so the reason, the evidence and the destination are its
whole output, and there is no divided attention because there is no other
work. This matches the governing document's non-producing node, which returns
evidence and a route.

Consequence: prose about a design has two readers who may act on it — the
design review node, where the prose is the artifact, and the arbitrator,
which reads everything relevant.

Recorded as untested: which error is cheaper is a judgement, not a
measurement. The seat proposed an experiment the fleet's cold-read instrument
could run — same target, two coder prompts, one with an input-criticism
channel and one without, measuring defects found in the code rather than
complaints made about the design. Queued as worth doing, not worth blocking
on.

Consequence applied to item 2.1: the coder no longer reviews the design
before starting. It starts the work and stops only when blocked. This matches
how the one real example was found — the fast-forward defect came from
building in a throwaway repository and measuring, not from reading and
judging. A gap blocks the same way: if the design is silent the coder cannot
finish without choosing, and choosing belongs to the originator. Anything
worked around and still finished is a nit.

Difference from the governing document, flagged not hidden: its standing
decision 4 says every node examines its inputs before producing output. The
user's rule has no examination step. His word governs; the document's
sections are in any case being reclassified as non-prescriptive notes.


## 2026-09-04 — the validator (item 2.4, new sub-step; walk stays at 8 items)

The user proposed a new node type: a validator that asks one question about a
package — can the next node complete its task using these inputs? It answers
with reasons and never produces the artifact. For a contract: can this
contract be fully vetted, executed, or validated as written? His stated
motives: it does not pollute the next agent, it screens serious problems
faster, and its criteria can grow to things the previous agent cannot handle.
He said it is conceptually and initially simple.

Seat's additions, in the item:

- Item 2.3's contract-program-check and contract-agent-check ARE a
  validator's criteria, so the acceptance list is not a separate mechanism.
- ASYMMETRIC WEIGHT: a validator cannot do the next node's job, so its
  approval is a guess about another agent's capability and counts as no
  evidence; its rejection is direct evidence and blocks. Otherwise it
  manufactures the green-signal-with-nothing-behind-it that merge-lane warned
  of.
- It does NOT replace the blockage rule. The fast-forward defect would have
  passed validation: the design was coherent and sufficient to code against,
  and only building it revealed it was wrong.

Merge-lane's contributions, relayed at the user's direction and all adopted:

- A BETTER JUSTIFICATION than the seat's: a coder that hits a defective design
  is burned, because when the corrected design arrives you want a fresh
  unbiased agent and must discard that execution. The validator absorbs the
  exposure, so a rejection costs a validator instead of a producer, and
  freshness survives the round trip. It is also cheaper, since judging
  sufficiency is smaller than discovering insufficiency mid-production.
- SPLIT contract-user-check. It was two questions. "Is anything the callers
  need missing" is the validator's own question and needs no user. "Is this
  the right boundary" is judgement and stays. This is constrained by a user
  ruling in merge-lane's session an hour earlier: he is a gate on the design
  and the test design, he may approve without reading, and states must
  minimise how long agents wait on him — his words, "ask one decision at a
  time... never queue him a question another node could settle."
- NUMBERING: a validator firing consumes no pass number; it is a refusal to
  start a pass rather than a pass. Only a producer's output consumes a
  number. The loop stays bounded on the other side of the edge, because a
  rejection sends the input's producer to its next pass.
- RISK: a validator that judges quality rather than sufficiency is a second
  reviewer at doubled cost. The single question is the whole guard. The user
  said the same.

ACCEPTED by the user ("y"), including the narrowing of contract-user-check,
which amends already-ruled item 2.3.

Process note: the seat told the user item 2.4 had been written to the walk
document before it actually had. It had only been presented in the message.
Corrected the same turn and stated plainly to the user.

AMENDED after the ruling, on merge-lane's correction, and reported to the
user. The seat had written that a validator's approval "counts as no
evidence". Merge-lane: the asymmetry holds but the magnitude overshoots. An
approval is evidence that none of the insufficiencies this validator checks
for are present — bounded evidence, not zero, and the bound is the criteria
set. Its argument for why this matters rather than being a quibble: the user
described the validator as growing, "eventually with specific criteria that
the previous agent can't handle", and if approval carries literally nothing
there is no reason ever to add a criterion, because a stronger validator
produces an equally worthless yes. Under the bounded reading, adding a
criterion visibly increases what an approval rules out. Adopted wording: an
approval carries exactly the weight of the criteria applied and NAMES them; a
rejection blocks on its own. Consequence adopted with it: when a coder later
fails on a design that validated, the named criteria show which check was
missing, which is how the criteria set earns its next member.

## 2026-09-04 — the graph's shape (applied to item 1.1)

Ruled by the user alongside item 5:

- Every node has exactly ONE output connection to the next node, which is the
  destination field of item 5.1.
- A node has ONE OR TWO inputs.
- A composite node may contain many more: "inside big nodes, little nodes can
  have many more, like we use in cold-read (8 I think)". From outside it is
  one node with one output; inside it fans out to parallel sub-nodes and fans
  back in. The cold read is the fleet's existing example. Factual note: the
  rounds on the topic-branch design ran five hunt cells plus a reference
  check, and the campaign brief runs seven; the fan-out point is unaffected.

Seat's distinction (two inputs is ordinary for a reviewer) was REJECTED by
the user: "I would not say that... only arbitrators handle two input nodes."
Ruled instead:

- ONLY ARBITRATORS have two input connections. A node with two inputs is an
  arbitrator by definition; that is what the shape means. A reviewer reading
  a design and the code is a ONE-input node.
- The single output is about the CONNECTION, not the file count: "Nodes can
  emit all sorts of files, coder many, walker 4, etc."
- The user named an ambiguity this exposes: "is a PR an Artifact or a
  collection of artifacts - ambiguous." Two words adopted to settle it, and
  written into item 1.1: an EDGE carries a PACKAGE; a package holds one or
  more FILES. A pull request is a package. Two input connections means two
  packages from two producers.

Item 6 amended to match: the arbitration trigger is two packages arriving at
one node from two producers, not two edges routing to a destination.

## 2026-09-04 — vocabulary, and a reviewer's two reject edges

- "ARTIFACT" IS BANNED, user: "I hate artifact - too broad and ambiguous."
  Removed throughout the walk document. Things are named specifically —
  design, contract, test plan, code, tests, notes — and where a general word
  is unavoidable it is a node's OUTPUT or the PACKAGE an edge carries.
- PROSE ALWAYS PRECEDES CODE in the design-to-main workflow (user). Design
  and contract are prose and the code comes from them; the test plan is prose
  and the tests come from it. So a reviewer's package always holds a prose
  parent and the code built from it.
- A REVIEWER MAY REJECT THE CODE OR THE PROSE PARENT. The user raised this as
  something he thought had been settled with some agent; a search of the 30
  most recent transcripts found only his own message to this seat about the
  contract writer and contract review rejecting the design, so the
  generalisation is new here. The walk had it only weakly, in item 5.1's
  "destination can be an upstream node".
- REVIEWER PACKAGES, with the contract added at the user's prompting: the
  code reviewer gets design, contract, code; the test reviewer gets design,
  contract, test plan, tests. Without the contract neither can tell a promise
  that is wrong from an implementation that breaks a promise.
- ITEM 7'S FIRST GUARD SCOPED as a consequence, seat's finding: "from round
  two on, the run is the round" applies to findings about the CODE only. It
  cannot apply to rejecting a prose parent, because the tests descend from
  the design and are therefore no oracle for a defect in the design that
  produced them. A reviewer rejecting the design, contract or test plan
  carries a failure scenario instead — item 2.1's standard applied by a
  reviewer.

Sync message sent to merge-lane at the user's direction, listing every ruling
above plus the graph shape and node behaviour, and asking for anything ruled
in its session that contradicts them, and where the objective-versus-notes
split leaves the sections this walk cites.

## 2026-09-04 — sync with merge-lane, which is drafting the standing decisions

Merge-lane is writing standing decisions 4, 6, 19 and 20 for the objective
page; this seat is building the concrete machine they will govern. Three
findings:

1. FIXED HERE, no conflict: item 2.3 said the contract writer "reads the
   design and makes the same call the coder makes", which is a producer
   auditing its inputs and contradicts the user's own later blockage ruling
   as well as draft decision 4. Rewritten: the contract writer writes the
   contract, and if it cannot — because the design never says what the
   component promises on some path — it reports what defeated it and stops.
   The pre-screen is a validator firing on the edge into it, not the writer
   auditing.

2. NEEDS THE USER: draft decision 6 says an arbitrator "may fix rather than
   only report; its fix is recorded, never silent." The user ruled the
   OPPOSITE in this session at item 6 ("y"): the arbitrator "does not write
   the merged output and does not edit either side... It rules, and a fresh
   agent at the destination does the work." Direct contradiction between two
   rulings made hours apart in different windows. Seat's proposed synthesis,
   offered but not adopted: for a merge collision the ruling IS the merged
   content and there is nothing left for another agent to do, so the
   arbitrator writing it loses nothing; for a code-versus-tests collision the
   ruling is "this side is wrong" and a fresh agent must write the fix.

3. NEEDS THE USER: merge-lane reports he ruled that a non-producing node
   reports to the node that CALLED it, not to the producer of the bad input,
   because routing is the state machine's job. Item 5.1 currently says the
   one field may be "the name of an upstream node", which assumes the node
   knows the graph. These reconcile if the field is the node's OUTCOME and
   the machine maps outcome to destination — one field either way, but the
   node needs no graph knowledge. Not applied without his word, since he
   ruled the destination wording here.

## 2026-09-04 — merge-lane's crossed reply

- WHERE THE SECTIONS LAND, the seat's actual question, answered: the user
  ruled the objective/notes split axis is ALTITUDE, not topic. Both pages
  carry every subject in the same order; the objective states each at a level
  a reader can follow end to end, the notes carry the detail. Section 5's
  node contract (four orthogonal dimensions included) and sections 7 and 8
  land in the notes with a high-level paragraph above each in the objective.
  Sections 19, 20 and 21 are carried WHOLE in the objective, being operative
  rules cited by path in twenty files. Consequence: a design departing from a
  NOTES section is not blocked but should say why; a design contradicting the
  OBJECTIVE is blocked, and the standing decisions are in the objective.
  Cite sections, not the file path, which goes away.
- The "artifact" ban collides with the standing decisions themselves, which
  use the word in at least five places (decisions 3, 5, 15 and the two
  drafted). Merge-lane has put a wording pass to the user in its own walk
  rather than acting on this seat's report, correctly treating a relayed
  ruling as hearsay.
- INDEPENDENT CONVERGENCE: the user arrived at the same blockage rule in both
  windows within the hour — "a node does not inspect its inputs; if it cannot
  complete its task because its inputs or instructions are defective, it
  reports those defects" is the substance of draft decision 4. Neither seat
  fed the other.
- Merge-lane proposes elevating two of this walk's rulings to objective-level
  standing decisions: PROSE ALWAYS PRECEDES CODE, and AN ARBITRATOR IS
  STRUCTURALLY A NODE WITH TWO INPUT CONNECTIONS. Both are the user's own
  words from this session rather than the seat's inventions, so elevation is
  appropriate; the seat raised no objection.
- VALIDATOR ARITY, merge-lane's question, answered in item 2.4: a validator
  is a one-input node and stays one however its criteria grow. One asking
  whether the coder can work from this contract given this design gets both
  in ONE package, assembled by the machine before the validator sees it. Two
  input connections means two packages from two producers; several files in
  one package is not that.

## 2026-09-04 — the arbitrator settlement, with merge-lane

Merge-lane dropped its own position, adopted this seat's collision-type
synthesis, and then stated the principle underneath it, which neither seat
had: AN ARBITRATOR WRITES ONLY WHEN ITS RULING AND THE OUTPUT ARE THE SAME
THING. In a merge collision, deciding how two sides combine IS the merged
text, and expressing that ruling any other way makes a fresh agent re-derive
what the arbitrator just did. In a code-versus-tests collision the ruling only
names the wrong side, and a producer writes the fix. One rule instead of two
cases, and it extends to collisions nobody has thought of.

It also preserves the reason this seat wrote the stricter version: the judge
does not author what it judged. In a merge collision the arbitrator judged two
inputs and authors a third thing, not either of the things it judged.

NOT APPLIED to item 6 yet. The user ruled the stricter version here ("y"), so
this is a reversal rather than a refinement, and merge-lane already has the
question in front of him in its own walk. This seat deliberately did NOT ask
him a second time, on his own gate rule that a question should not be queued
to him twice.

Also from merge-lane, on the routing field: his words in that window were
"How nodes connect is not defined... how they connect is irrelevant to the
state machine or nodes." That is transport rather than topology so it does
not settle the question outright, but it leans toward this seat's
reconciliation — a node that must name an upstream node carries a map of the
graph in its prompt, which is hidden state of the kind he keeps removing.
Likely an application of a decision already made rather than a new one.

Candidate objective-level decisions merge-lane has taken from this walk:
prose precedes code; one-in-one-out with the arbitrator exception; the
artifact ban; a reviewer may reject the code or the prose parent; and a
finding touching text the user has already ruled is quoted with the ruling
and not reportable again — which already exists for the PR process in CLAUDE.md and
would become general. The package vocabulary goes to a separate vocabulary
walk he ruled today.

## 2026-09-04 — aggregation is not arbitration (item 6, refinement)

Merge-lane answered the composite edge two ways, both adopted into item 6:

1. The two-input rule is counted in the graph BETWEEN nodes, not inside a
   composite one. A composite presents one input and one output to the graph;
   what it does inside is its own business, and that is what makes it
   composite rather than a subgraph. Merge-lane is adding the same clause to
   the standing decision.
2. Even if the rule reached inside, the cold read's merge would not be an
   arbitrator. It produces one merged report with findings grouped by
   passage, each cell's wording preserved and a count of how many cells
   raised it. It never rules between disagreeing cells: two that contradict
   both survive with their own words and the reader sees the disagreement.

The distinction, added to item 6 because the machine will meet it again: a
node that PRESENTS disagreement is not arbitrating; a node that RESOLVES it
is. Aggregation preserves both readings, arbitration produces one answer
where there were two.

## 2026-09-04 — freshness stated, and the design's true origin (item 1.1, item 6)

User-ruled and applied ("y"):

- A COLD READ IS NOT THE START OF THE DESIGN PROCESS. A design originates in
  a conversation between the user and an agent. So when a design fails
  downstream, the restart begins there — the user and a FRESH agent, with the
  design issues in hand. The design cycles; the originating design agent does
  not. Item 1.1's "originator" was rewritten as the DESIGN NODE: a
  conversation between the user and a fresh agent, and on a restart a new
  conversation carrying the accumulated issues, not a waiting owner being
  woken.
- ALL AGENTS ARE ONE-SHOT OR REFRESHED, which the user noted the walk had
  never clearly captured. It appeared once as a background remark in item 1.1
  while four separate things leaned on it. Now stated as its own load-bearing
  rule: no agent persists across a pass; every node instance receives files,
  does one task, and ends; nothing crosses a pass boundary except files. The
  four dependants are named in place — the validator (a burned producer is
  cheap to discard), the dispositions record (nothing else carries between
  passes), the escalation packet (no agent holds the history), and the
  numbering (it bounds passes, not agent lifetimes).
- THE USER IS THE ONLY CONTINUOUS PARTICIPANT, seat's observation inside that
  ruling and accepted with it. He is the same person across every pass, which
  is why he is a gate rather than a node, and why a cap of three restarts is
  really a cap on how many times the machine spends his attention — the one
  input it cannot manufacture.
- Item 6's escalation now says the packet arrives as a CONVERSATION, not as a
  report to a reader, because the design began in one and a failed design
  resumes in one.
- Unchanged, deliberately: the cold read reviews a design and never
  originates one, so item 7's second guard is about when to re-review and is
  a different question.

The roles list in item 1.1 was brought up to date at the same time: design
node, contract writer, coder, test plan writer, test coder, code reviewer,
test reviewer, validator, arbitrator, merge-lane. "Test design" renamed to
TEST PLAN throughout, the governing document's existing name.

The user directed this seat to coordinate the update with merge-lane.

## 2026-09-04 — the arbitrator settlement, RULED by the user via merge-lane

The user ruled the decision-6 conflict in merge-lane's window and told it to
coordinate the update here. The settlement SUPERSEDES both prior rulings,
including the stricter one he gave this seat at item 6.

THE RULE: an arbitrator fixes what its ruling already determines, and hands
off work its ruling merely implies.

Worked cases agreed in that exchange: a merge collision — the ruling is the
merged text, so it writes. A test asserting something the contract does not
promise — the ruling names the correct assertion, so it fixes. Code that
fails a test because the code is wrong — the ruling names the side but does
not determine the implementation, so a coder writes it.

Why this seat's objection fell rather than being traded away: both seats held
that a judge must not author what it judged, and it buys nothing here,
because every output goes to an independent reviewer anyway, so an
arbitrator's fix is reviewed like any other creation. Forbidding it only
discards the reading that produced the ruling. The real limit is SCALE, not
authority: an arbitrator is instantiated to answer a question with a package
assembled for judging, and is not equipped for production work of unknown
size.

Three more from the same exchange, applied or recorded:

- Designer to design-validator is LINEAR, so a validator rejection is not a
  conflict and needs no arbitrator. Sharpening the user accepted: a designer
  holding context they never wrote down is a DEFECT SIGNAL, not a resource —
  if the design cannot be worked from without that memory it is incomplete,
  and that is what the validator catches. Someone will eventually propose
  reaching into the designer's transcript as an optimisation; the answer is
  no, because it undoes minimum hidden context.
- The arbitrator's structural definition carries the composite clause: two
  input connections counted in the graph between nodes, not inside a
  composite one.
- The pipeline ALREADY CONTAINS an arbitrator under another name: the node
  that reconciles accepted code and tests from separate work items has two
  input connections from two producers and a conflict to resolve. Written
  into item 6 — a shape already present rather than a new kind of node.

Still open, merge-lane carrying it: whether the contract is inside "design"
for the decision 19 human gate.

Walk document renamed in its title to "the design-to-main state machine",
since "originator" is gone as a role name; all references now read "the
design node". File paths unchanged.

## 2026-09-04 — where this walk's rulings landed in the objective

Merge-lane's answer to the coordination question, so nothing is queued to the
user twice:

- "No agent persists across a pass" is ALREADY an objective decision, weakly:
  decision 3 says agent executions are bounded and replaceable, an execution
  receives a task, pinned revision, governing files, instructions and
  evidence, and does not depend on a predecessor's private conversation.
  That states it as what an execution RECEIVES; this walk's form states it as
  what nothing may CARRY, which is the testable form. Merge-lane has put it
  to the user as a strengthening of decision 3, not as a new decision, so
  this seat is not to raise it separately.
- "The user is the only participant with memory across passes" is going into
  decision 19 as its REASON. That decision said the gate exists and that
  waits must be short; it did not say why.
- The test plan rename corrects merge-lane's text too: decision 19 had said
  "the design and the test design", while the governing document has always
  said test plan. It now reads test plan.
- Nothing else conflicts. The design-node ruling and merge-lane's
  designer-context sharpening are the same rule from two sides, and it landed
  as a rule about where a design resumes rather than as a rule about
  transcripts.

Still carried by merge-lane: whether the contract is inside "design" for the
decision 19 gate.

## 2026-09-04 — the final rename, and the user as a prose node

- RENAMED, user-confirmed here after merge-lane relayed it (this seat
  declined to act on the relay, on merge-lane's own precedent that a ruling
  through a third party is hearsay). His words: "I think we should be more
  specific code-design and test-code-design." Applied throughout the walk
  document. Both are prose, both name the code that descends from them, which
  "test plan" never conveyed. This supersedes the test-plan rename made an
  hour earlier, and merge-lane retracted its report that test plan was the
  governing name — it was, and he has replaced it.
- THE USER IS A NODE, not only a gate: "I'm a node too I review all final
  prose." A prose document goes COLD READ, then HIS REVIEW, then it lands.
  Added to item 1.1's roles, to item 7 as its own paragraph, and to item 8's
  summary and next step. Operationally the document is opened on his Mac for
  him to read (plain `open`, per the standing convention).

Held, not applied: merge-lane's reading that the gate is exactly code-design
and test-code-design, with the contract riding inside the code-design rather
than being a third thing he is asked about. If confirmed it removes item
2.3's contract question from his queue entirely. Merge-lane has put it to him
and has not sent it as a ruling.