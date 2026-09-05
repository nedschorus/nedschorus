# Minutes: the state-machine design's cold read — triage

Walk document: docs/walk/state-machine-design-cold-read-triage.md
8 items. Opened 2026-09-04.

What this walk is about, for someone who has not read it: a design document for the
design-to-main state machine was written, then put through this project's cold-read grid.
Four zero-context reviewers returned 236 findings and reported no clean sections. This walk
presents what they found, grouped by how much it changes, and what the seat proposes to do.
The seat's own diagnosis is that it wrote a summary of the user's rulings where a
specification was asked for.

Cells and counts: codex floor (gpt-5.6-luna, xhigh) 58; claude floor (sonnet-5, high) 26;
codex good (gpt-5.6-sol, xhigh) 75; claude good (opus-5, high) 77. Records in
cold-read-records/2026-09-04-design-to-main-state-machine-design/ — machine-local, kept.

Before item 1 was presented, merge-lane answered the two structural findings from standing
decisions that already exist, which lightened items 2 and 3:

- THE UNDEFINED MACHINE is answered by decision 13 (what belongs in deterministic code:
  permissions, state transitions, counters, validation, repeatable transforms, promotion)
  plus decision 7 (the state machine is logically persistent, not process-immortal). The
  machine is the state machine and the state machine is a program. Merge-lane has put a
  clarifying sentence to the user for decision 7. Consequence the seat adopted: the machine
  is code, so it holds NO JUDGEMENT, and anywhere the document has it deciding rather than
  routing is a defect to sweep for specifically.
- THE MISSING TERMINAL STATE is correct behaviour, not a gap: decision 14 says there is one
  gate to main and this machine is not it. Its terminal state is one state, submit to the
  gate. The defect is stopping without saying so.

## Item 1 — the verdict: rewrite, not patch

presented 2026-09-04 → next ("go"). No decision was asked. Four cells, 236 findings, no
clean sections in any cell; three of four converged on the same three contradictions. Seat's
diagnosis accepted implicitly: it wrote a summary of rulings where a specification was asked
for.

RIDER, user-set: "remember the reviewers are telling the truth for their point of view,
which is close to what future agents reading this doc will have, ignore them at your peril.
I think we need to add a line something like this to the cold-read skill." Seat proposed the
exact wording for step 2 of .claude/skills/cold-read/SKILL.md, beside the existing
keep-judgments-provisional instruction:

  "A reviewer is telling the truth from where it stands, and where it stands is close to
  where every future agent reading this document will stand. A finding you dismiss because
  you know what you meant is a finding that will be rediscovered by someone who does not."

RETIRED 2026-09-04: the user wrote the paragraph himself in the MD-skills seat, and it is
now step 2 of .claude/skills/cold-read/SKILL.md on that seat's branch, PR to follow. It
carries both halves — reviewers' truth is the operative truth, and the cold read is coupled
to the writer. No branch from this seat. The same paragraph sets the process that binds this
walk's rewrite: rewrite to fix what the readers found; ask him before rejecting a criticism
or when a fix would add or expand a section; record every finding NOT applied, with its
reason; commit each round naming the record directory; then walk the changes and the
rejected findings with him.

## Item 2 — "the machine" is undefined

presented 2026-09-04, twice restated at the user's instruction, RULED Y.

What Y approves, in three parts:

1. THE NAMING, now confirmed by the user directly rather than by relay. The DESIGN-TO-MAIN
   WORKFLOW is the process; the DESIGN-TO-MAIN STATE MACHINE is the program that runs it;
   the nodes are its states. Decision 7 carries it: the state machine is logically persistent
   rather than process-immortal, it is a program, and it assembles each node's package,
   routes on the destination a node returns, counts passes, and delivers escalations.
2. THE MACHINE HOLDS NO JUDGEMENT, because it is code. Every place the document has the
   machine deciding rather than routing is a defect, to be swept for specifically rather than
   assumed caught by the cold read under other headings.
3. THE MACHINE DOES NOT OWN THE COLD READ. Each prose-producing node contains one; its
   report returns to that node's own writer; the writer persists across those iterations.

The reasoning for (3) is the user's and it is the load-bearing insight of the walk so far,
in his words: "Cold read has to be coupled to the writer - because only the writer knows
what they are trying or need to say, even if they are incompetant at saying it in a way that
a cold reader can understand." Worked through this item: if the machine routed a document
out to a cold read, the report would return to a FRESH agent, since no agent persists across
a pass. A fresh agent cannot tell whether the reader understood what was MEANT, because it
does not know what was meant either — it can only smooth what reads badly, which is the
prose loop with extra steps. So the coupling is structural, not stylistic, and it generates
a constraint the design document does not state: inside a node, the writer persists across
its own cold-read iterations. Unstated, an implementer could hand the report to a fresh
agent and destroy the mechanism while obeying every written rule.

EVIDENCE, from cold-read-research-74 after the ruling, in
/Users/el/agents/cold-read-research/cold-read-records/2026-09-03-cold-read-tier-roster-campaign/REPORT.md
(machine-local, gitignored; sections "Author-rewrite loop (METHOD §9)" finding 3, and
"THE ANSWERS" question 4; the judges' calibration paragraph precedes the loop table and is
what makes the figure trustworthy): on 238-round-2, a fresh author given
the reports resolved 14 to 17 of 50 known defects whichever reviewer set drove it; the
writer's own fix pass, judged blind by the same calibrated judges, resolved 42.7. And cells
unanimously report "sure" findings that are false (a true clause the reviewers told the
author to delete), which a fresh author follows and the writer does not. The cells
themselves stay cold — intent as a cell input would make the read warm — but standing
rulings are a legitimate cell input for instruction prose, because they are prior decisions
rather than intent.

ALIGNMENT 2026-09-04, at the user's request, with the three other live seats: merge-lane-16
holds decisions 7, 13, 14, 19, 20 and will send his exact words on the parallel-validator
disagreement from its own walk; MD-skills-6c holds every file under .claude/skills/, the
test taxonomy ruled 2026-09-03 (coverage type: script / prompt / script-and-prompt /
excluded), and the walk-me-through changes from this seat's self-review, all pending his
word; cold-read-research-74 holds the instrument's evidence. This seat holds the node table
and the state and transition tables. docs/issues/queue/cold-read-tier-roster-campaign-brief.md,
untracked here, is THIS SEAT'S — a predecessor wrote it — and is not yet routed; open item.

## Item 3 — there is no state machine in the state-machine design

presented 2026-09-04, RULED Y, with a rider.

The rewrite leads with a STATE TABLE and a TRANSITION TABLE. Every state named anywhere
appears with its inputs, outputs and successors, ending at SUBMIT TO THE GATE — one terminal
state, per decision 14, because this machine is not the gate to main and must not become one.
The user's own node names are used as given rather than renamed: `implementation-validator-node`,
`test-design-validation-node`, `implementor-node`, `test-design-node`. Where a state's
composition is genuinely undecided, it appears with that noted rather than being left out;
the reconciling node is the live example.

RIDER, user-set: "when we do the md we can have a graphic too." A diagram accompanies the
tables in the markdown. Seat's reading, open to correction: a mermaid state diagram, since
the project's documents are markdown in git and GitHub renders mermaid natively, so the
diagram stays in the same file under the same review as the prose. One constraint the seat
is adopting unasked because two representations of one machine diverge silently: THE TABLE
IS NORMATIVE and the diagram is checked against it, so a disagreement between them is a
defect in the diagram rather than an open question.

Before presentation, item 2's Y had already removed the cold read from this item's list of
states named but never listed: it is not a missing state, it is a sub-node inside every
prose-producing node, and it never gets a row.

## Item 4 — the node table is wrong in six ways

presented 2026-09-04 as a block; the user ruled it non-trivial and asked for it to be walked.
Expanded into six sub-items at
docs/walk/state-machine-design-cold-read-triage-item4-rewrite.md, following the pattern this
project used for earlier walks (-item2-rewrite, -item3-rewrite). Suggestions from the
fast-clarify cell are alongside it. Three defects the clarity read found in the draft were
fixed before presentation: an inconsistent count of the paths that reach the user, a switch
between two different consumer sets mid-item, and two rulings cited without saying where they
are recorded.

Sub-item outcomes:

- 4.1 code reviewer receives no tests — presented 2026-09-04, RULED Y after six revisions,
  every one of them a correction from the user. The ruled text: the code reviewer receives
  the code-design, the contract for the scope under review, and the code to be reviewed. It
  writes and runs its own tests to its own completion bar and keeps them with its notes as
  evidence. It does not receive our suite or its result. The machine runs the suite; the
  result routes, and reaches the arbitrator when code and tests conflict.

  What the discussion settled, beyond the text:
  - The design had a real oversight: code reviewers write, run and review their own tests
    unprompted, and the design pretended otherwise. The user's words: "our test path is
    either an optional or secondary set of tests." Seat disagreed on "secondary" — primary
    in discovery is not primary in authority; the formal suite is the durable one — and the
    user did not press it.
  - The reason the reviewer's tests and the suite stay apart is PROVENANCE, not context
    poisoning: a test derived from the code encodes the code's behaviour and so cannot judge
    it. The design's own fast-forward example makes it concrete: a probe test asserting the
    observed "Already up to date" would certify the bug.
  - The reviewer receives neither the suite nor its pass/fail result. User's reason,
    accepted: a reviewer handed our tests tries less hard on its own, and confuses what we
    thought important with what it decides to test; a score does the same in a smaller
    size. Running the suite is mechanical, so the machine does it (decision 13); the result
    is a routing fact, and reaches the arbitrator on conflict.
  - CONSEQUENCE for the rewrite: the design's sentence that the code review is where the
    code and test lines first meet is no longer true. They meet when the machine runs the
    suite, and their disagreements go to the arbitrator.
  - "never enter our suite" was struck: "the word never is dangerous." How reviewer tests
    might be reused or promoted is UNKNOWN and deliberately left out of the design.
  - "code" became "code to be reviewed": the reviewer is invoked on a PR or set of files
    with the contract for that scope, and the design should say so rather than leave the
    invocation "a bit magical."
  - NITS: the seat twice proposed a definition inside 4.1 and was wrong twice. Withdrawn;
    item 6 owns it. Boundary facts established for item 6 to start from: not-testable is
    not nit (prose-parent rejections, by-hand demonstrations carry failure scenarios with no
    possible test); no-failure-scenario is not nit (that set includes preferences,
    questions, suggestions, prose findings and false positives); a nit is a REAL defect
    that is inconsequential — the user's example, "log-in" for "login" in a comment — and
    the same string in a CLI flag is a contract defect, so position decides. Nits are
    recorded in the notes and never routed to a producer as work; that part was not
    contested.
- 4.2 test coder may reject the code-design it never receives — presented 2026-09-04,
  RULED Y, generalised during discussion at the user's prompting: THE CODE-DESIGN IS IN
  EVERY NODE'S PACKAGE, and rows list only what a node receives beyond it. His reason for
  the test path, which is the general one: without the code-design as a direct input, the
  test-design would have to restate it, and a restatement drifts.

  Two RIDERS, user-set with the Y:
  - The code-design is NOT the single source of truth once code exists; the code is far
    more detailed and changes as it is written. The design changes on exactly two triggers:
    the code cannot be written from it, or later, code cannot be written that passes the
    acceptance tests. Seat's reading: this is the definition of when a redesign (a restart)
    fires, and it belongs in the transition table; it also confirms line 200 is obsolete,
    since the design is never re-read for drift, only rewritten on failure.
  - The machine has TWO terminal states, not one: accepted, and the work goes to main; or
    failed, and the work goes back to the human. Item 3 named only the success terminal
    (submit to the gate, decision 14). Seat's reading, put to the user for confirmation:
    success terminal is submit-to-the-gate and the GATE pushes to main, per decision 14;
    failure terminal is the escalation to the human. If "pushed to main" means the machine
    itself pushes, that contradicts decision 14 and merge-lane must hear it.
- 4.3 nodes routed to with no row — presented 2026-09-04 → next. No decision asked; covered
  by item 3's Y. Four rows to add: code-design review node, the reconciling node,
  contract-program-check, contract-agent-check. contract-user-check retired into the general
  prose gate. The terminal-state confirmation from 4.2's rider was not answered at this
  turn and stays OPEN.
- 4.4 the user's row admits only final prose — presented 2026-09-04, RULED Y on the revised
  text: the user's row lists THREE paths — all final prose after its cold read (designs,
  wiki pages, CLAUDE.md, skills, whatever the document is); the escalation conversation at
  the third restart; and the discussion when a document fails his review. Not code, not
  tests, not traffic between nodes.

  Settled in discussion: the gate is MEDIUM-BASED, per decision 19, not a list of document
  types. The user's list (code-design, test-code-design, wiki pages, CLAUDE.md, "maybe other
  stuff") is instances of the rule, and "other stuff" is answered by the rule. The seat's
  draft had the two designs reaching him "before either is final" as a fourth path; wrong —
  he reads a design after its cold read and before it fans out, which is when it is final,
  so the designs ARE the final-prose path. Four paths became three. Decisions 19 and 20
  (node vs gate) are merge-lane-16's walk item, not reopened here.
- 4.5 fan-out belongs to the machine (retirement) — presented 2026-09-04, RULED Y. A node
  emits once over one output connection; the machine delivers that output to each consumer.
  Fan-out is routing, which is the machine's. Retired as a defect; the rewrite adds the
  sentence saying delivery is the machine's in both directions.
- 4.6 documents in a package are not input connections (retirement) — presented 2026-09-04,
  RULED Y. The machine assembles every node's package, not only the validator's; a node has
  one input connection (its package), an arbitrator has two, and the count of documents
  inside a package is unrelated to either. Retired as a defect.

ITEM 4 COMPLETE, all six sub-items ruled 2026-09-04. Net for the rewrite: the code-design is
in every package; the code reviewer receives the contract for its scope and the code to be
reviewed, writes its own tests, and never sees the suite or its result; the machine runs the
suite and delivers every package in both directions; four rows are added; the user's row
lists three paths. Two findings retired as misreadings. The sentence that the code review is
where the two lines first meet is struck.

OPEN, raised by the fast-clarify cell and not answered: when the code-design fans out to
`implementation-validator-node` and `test-design-validation-node` in parallel, where does each
validator's result route, and what happens when the two disagree — one passes and one fails.
Nothing in the design or in any ruling covers a split verdict from parallel validators. Not a
node-table defect, so it is not being folded into item 4; it belongs to the transition table
that item 3's Y commits to.

## Item 5 — the contract's group names break the project's naming rule

presented 2026-09-04, RULED Y on the revised recommendation, which grew in discussion:

1. Rename the five contract groups (I, P, O, E, U) to explicit multi-part names, per the
   CLAUDE.md naming rule; I and P both held preconditions and were indistinguishable.
2. EVERY OUTPUT CLAUSE SAYS HOW SUCCESS AND FAILURE ARE OBSERVED. Exit status is the script
   case (0 success, nonzero failure), and scripts keep it as a requirement; a function's is
   its return value, a prompt's the verdict in its report. Replaces "every output clause
   names an exit status," which assumed every component is a process. The user pressed
   twice — "doesn't 0 usually mean success?" and "don't we need to know if they exited
   successfully?" — and the seat's first fix (demote to an example) was worse than the one
   his pressing produced (keep it universal, name the thing).
3. EVERY NODE'S OUTPUT CARRIES AN EXPLICIT EXIT THE MACHINE ROUTES ON. User-set: "why don't
   we give each node an explicit exit process. For me that's an approval." The design had
   exits for checking nodes (destination, yes/no, ruling) and none for producing nodes,
   whose rows end at "the component" or "the contract"; decision 7 has the machine routing
   on a returned destination, so a producing node with no exit is unroutable — which is
   item 6's "clean review cannot advance" seen from the other side. Producing nodes exit
   done or could-not with what defeated them; the user exits approval or rejection. Feeds
   item 3's transition table as each state's exits.
4. Fix the dangling "rows 2 through 7" reference and "the three underneath."
5. State which of observability and testability governs a contract clause when they
   disagree.

## Item 6 — holes in the logic, now eight rather than five

Expanded 2026-09-04 into eight sub-items at
docs/walk/state-machine-design-cold-read-triage-item6-rewrite.md, the same pattern as item 4,
before presentation. The fast-clarify cell found four real ambiguities in the draft, fixed:
exit vs destination (an exit CARRIES a destination); the arbitrator's exits enumerated as
three (advance / ruling with fix destination / route-up); the silent-contract route
continues up the prose chain and is counted as prose-parent rejections; "round two" became
"the second pass." One gap it found is answered by the seat's reading of the 4.2 rider,
flagged as the seat's: "cannot be written from it" covers any producing node below the
design, so a contract writer defeated by the design is trigger one, not a third trigger.

Sub-item outcomes:

- 6.1 clean review cannot advance — resolved by item 5, presented 2026-09-04 → next ("y").
- 6.2 arbitrator invents intent — presented 2026-09-04, RULED Y after eight revisions, on
  this text: Where the contract speaks, it governs; contradicting tests or code go back to
  their producer. Where it is challenged or silent, the arbitrator checks the code-design;
  if that settles it, a fresh contract writer corrects the contract from the arbitrator's
  notes; if not, the user is looped in. The user is also looped in when a code-design is
  rejected, and when a contract fails its second pass. Every loop-in is ONE REPORT TYPE —
  focus design, contract, test-design, or unknown — written and cold-read by the node that
  triggers it, carrying the evidence and the user's prior rulings on the component. The
  arbitrator never edits the contract or the design.

  Settled on the way, in order:
  - THE CONTRACT WRITER NODE exists, from the code-design, before the fan-out. The user's
    flow sketch lacked it and merge-lane-16 had flagged "contract missing from the
    pipeline" independently. Not the test-designer (collapses the two loops' independence);
    not from the PR (a promise derived from code describes the code). Accepted by the user
    proceeding on it.
  - A defective contract is fixed by a FRESH CONTRACT WRITER from the arbitrator's notes,
    never by the arbitrator. User's assumption, confirmed. The seat's "arbitrator adds a
    ruling to the settled set" mechanism was retired as unnecessary.
  - Two distinct arbitration cases, user's correction: the contract SPEAKS and a test or
    code contradicts it (the contradicting artifact is wrong, back to its producer); or the
    contract is CHALLENGED or SILENT (the code-design governs). The seat's "a test asserts
    something the contract does not promise" conflated them — "tests don't assert stuff
    like that. maybe agents do."
  - THE USER IS NOT A ROUTINE GATE ON CONTRACTS. His words: "i'd rather not." The contract
    has its own validators and is checked from below; the design is gated because it is
    intent, the contract because it is derived and derivation is checkable. NARROWS
    DECISION 19 by one category — the contract is pipeline prose, not a landing document.
    Sent to merge-lane-16 in his words.
  - THE LOOP THE USER FOUND: hidden contract defect → nine passes → escalation packet of
    notes → he fixes the design he gates → counter resets → fresh writer repeats the
    mistake → nine more. Nothing ever put the contract in front of him as the suspect.
    Bounded only by his patience. Real; the seat had not seen it.
  - FIX: he is looped in when a contract fails its SECOND pass (his trigger, replacing the
    seat's "count escalations per component"), with the report focused on the contract.
  - ONE REPORT TYPE for every loop-in, focus field design/contract/test-design/unknown,
    produced by the triggering node (the machine cannot write prose), cold-read inside
    that node because the user is the reader with least context, carrying his prior
    rulings on the component so a second report never asks him to re-decide.
  - PLACEHOLDER, user-set: guidance on what the report must contain is DEFERRED. Until it
    exists: "prepare the info I need and then cold-read, so I can actually read it. Stuff I
    have to read I want cold-read first." OPEN item for the rewrite's scope, not invented.
- 6.3 arbitration triggers without disagreement — presented 2026-09-04, RULED Y. Two
  packages arriving is what routes to the arbitrator; whether they conflict is what it
  determines. EVERY NON-WRITER — validator, reviewer, arbitrator — emits the same three
  things: NOTES, A VERDICT, A DESTINATION. The table's "any fix its ruling determines" is
  struck: the arbitrator emits no fix. The user asked for the whole of it in one place;
  the arbitrator's table, as ruled:
    agree → advance → next node;
    disagree, contract speaks → contradicting artifact is wrong → its producer, fresh;
    disagree, contract challenged/silent, code-design settles it → contract defective →
      fresh contract writer, as a pass;
    disagree, neither settles it → over its head → the user, with the report.
  It never edits code, tests, contract, or design.
- 6.4 one definition of nit — presented 2026-09-04, RULED Y. A NIT IS A REAL DEFECT WITH
  NO OBSERVABLE CONSEQUENCE; position decides ("log-in" in a comment is a nit, in a CLI
  flag a contract defect). Nits are recorded in the reviewer's notes and never routed to a
  producer as work. Replaces three inconsistent definitions.
  RIDER, user-set: "non testable might equate to no-failure-scenario." Seat agrees in
  principle and corrects its earlier boundary fact: a failure scenario is an observable
  wrong outcome, hence testable by SOME test; the cases the seat had called not-testable
  (a bad code-design, a by-hand demonstration) are not testable BY THE SUITE THAT DESCENDS
  FROM THE DEFECTIVE DOCUMENT, which is a fact about which tests, not about testability.
  So has-a-failure-scenario and testable-in-principle are one set.
- 6.5 round-two guard vs reviewer's tests — resolved by 4.1, presented 2026-09-04 → next.
- 6.6 line 200 obsolete — resolved by 2 and 4.2, presented 2026-09-04 → next, after a
  plain-language restatement at the user's request. What it says: the design is rewritten
  ONLY when something downstream fails on it — the design validator, the contract writer,
  the coder or test-designer, the arbitrator, or the user via a loop-in report — all of
  which are "cannot be built from it," plus "code cannot pass acceptance." Nobody re-reads
  the design for drift; a rewrite carries its own cold read inside the node. Line 200, a
  rule about re-reading, is deleted.
- 6.7 code-design validator not enumerated — presented 2026-09-04, RULED Y. The rewrite
  enumerates the code-design's program checks and agent checks in the same form as the
  contract's, replacing "the scheme generalises ... and so on."
- 6.8 which number a rejection increments — presented 2026-09-04, RULED Y on a rewritten
  recommendation. THREE COUNTERS, held by the machine:
    1. Redesigns (the restart counter): three, then the user.
    2. Code writes: three per redesign, nine total. THE ROUND COUNTER INCREMENTS WHEN A
       CODE WRITE FINISHES (user-set: the expensive event, mechanically detectable). A code
       write includes its one suite run. Test writes are counted the same way and BEGIN
       AFTER CODE WRITE 1 (user-set: the first code write is the real proof the design is
       buildable; do not spend the test budget before it). The test package never contains
       the code — sequencing changes when, not what; the provenance rule from 4.1 holds.
    3. Prose corrections to the contract or test-design: two each, then the user (6.2's
       contract rule, extended to test-design). A prose rejection is charged here ONLY.
  Principle, seat's, accepted: COUNT WHAT IS EXPENSIVE. A cheap prose ping-pong must not
  burn the code-write budget. User's constraint: "I certainly don't want more than 9 code
  writes." Nine stays as the ceiling; lowering it is a one-number change, his call.
  Consequence: the first suite run is after test round 1, so round 1's code review is the
  reviewer's own tests only.

ITEM 6 COMPLETE, all eight sub-items ruled 2026-09-04. Grew during items 1–2 from a question merge-lane put to the seat about
whether a reviewer's right to reject a prose parent reopens the prose-change/code-change
loop the user raised at 19:21. Added: the code-design's validator is asserted but never
enumerated (the contract's checks are written out, the code-design's exist only as "the
scheme generalises ... and so on"); which number a contract rejection increments is
undefined (bounded anyway, since a loop not closed at pass 3 goes to the arbitrator, so a
numbering ambiguity rather than a runaway); and line 200 is probably obsolete rather than
incomplete, since under the internal-cold-read model there is no re-cold-read event
separable from a re-emission.

SETTLED DURING THAT EXCHANGE, not to be relitigated: decision 19 stands as the user approved
it, and "final" in the design's line 206 is load-bearing and correct as written. There are
TWO TRIGGERS on purpose — the cold read fires on every prose emission, cheap and internal;
the user's review fires on prose that is final and about to land. The seat proposed fusing
them, merge-lane accepted, and both withdrew it on reading the user's own words: fusing
would have delivered him every intermediate emission, which is precisely the loop he feared.
The seat's error, recorded because the reasoning that produced it looked sound.

SURVIVING FROM THAT EXCHANGE, and worth keeping whatever the trigger turns out to be: a rule
about re-reading is safe where every reader that builds from the document is fresh; where a
reader accumulates context across passes, drift accumulates unseen. Stated as a condition
rather than a carve-out, because a condition is checked at the point of use and fails loudly,
where an enumerated carve-out is only as good as what could be imagined when it was written.

## Item 7 — claims that overstate, references that go nowhere

presented 2026-09-04, RULED Y. Cut every absolute to what the evidence supports, by
deleting words rather than adding qualifiers. Give every external reference a path or a
definition; where a path is about to change, cite the section rather than the file.

## Item 8 — what the rewrite becomes, and what it lands into

presented 2026-09-04, RULED Y 2026-09-05 ("yes to all") on the recommendation — rewrite
against items 2 through 7 as ruled, by the process in the cold-read skill, then a second
cold read with today's rulings handed to the cells, then the user — together with FIVE
user-raised changes that amend earlier items, and one rider:

1. THE VALIDATOR FOLDS INTO THE WRITER. User's reasoning: a writer told "if your
   instructions are missing information, ask first" validates its own inputs; a separate
   node doubles token cost for no utility, and no test case shows separation earns it. The
   seat had none to offer: the review and tests are already the second reader, and a
   writer that asks before writing has burned nothing, which was the validator's original
   reason to exist. Kept from the validator: 6.7's enumerated checks become the writer's
   pre-write checklist; a could-not exit names what was missing, so the learning loop
   survives. AMENDS item 3 (implementation-validator-node and test-design-validation-node
   leave the table) and 4.5 (the fan-out at the design is gone; the flow is sequential:
   design → contract → implementor → after code write 1, test-designer).
2. ONLY SUCCESSFUL WRITES INCREMENT THE BUILD COUNT. A could-not exit is not charged; it is
   bounded by the other counters (could-not against the design is a redesign, against the
   contract a prose correction). AMENDS 6.8.
3. GIT IS THE RECORD. Same filenames every pass, one commit per pass, pass number in the
   commit message; the branch history replaces the numbered files and IS the escalation
   packet. The gate merges with a merge commit so main's first-parent log stays one entry
   per component. Seat does not see why this changes the gatekeeper's job, but decision 14
   and the gatekeeper design are merge-lane's; question sent there rather than ruled here.
   User's worry recorded: it "may force us to change how the git-gatekeeper works, maybe it
   becomes the PR-gatekeeper." AMENDS 6.8 (file naming) and the escalation section.
   CORRECTED by merge-lane-16 from the gatekeeper's code: `git-gatekeeper.py check-in` does
   NOT merge. It makes a fresh clone of main, writes the submitted content as ONE candidate
   commit carrying a trailer, and pushes it fast-forward. No merge commit, no first-parent
   structure; main gets one commit per check-in whatever the branch holds. So pass commits
   never reach main (answers the clutter worry) and the gate's job is unchanged (answers the
   PR-gatekeeper worry). The founded part: pass history survives ONLY on the topic branch,
   so the design must say TOPIC BRANCHES CARRYING PASS HISTORY ARE PUSHED TO ORIGIN AND
   RETAINED AFTER LANDING, or the arbitrator's record dies with the branch. A rule for this
   machine's git step; decision 14 needs no edit.
   CITATIONS for the rewrite, from merge-lane-16: the objective page is
   docs/wiki/queue/nedschorus-ai-native-software-development-objective.md on its unpushed
   branch, moving to docs/wiki/ after its own triage — cite the queue path and expect one
   repoint; decisions are cited as "Standing decisions, decision N" (one heading, numbered
   list, no per-decision anchors). Do NOT cite decisions 4 or 21 until merge-lane sends his
   words: the validator fold reverses both and merge-lane is re-presenting them. Build step
   1 is the AI-native architecture's §18 step 1 ("Adopt the vocabulary, provenance fields,
   and result schema"); its GitHub issue is NOT filed (merge-lane task #106) — cite as
   pending.
4. THE ARBITRATOR IS THE OVERVIEW NODE. Its package includes the branch history. It decides
   and routes per 6.3; it reaches out to the user when necessary — over its head, or at its
   discretion; the user can invoke it on demand, fresh, for a status report or a
   conversation. It never fixes. No mandatory notification ("I may let the arbitrator just
   do its thing"). The seat first proposed a separate status node and withdrew it: with git
   as the memory, a fresh arbitrator has the overview, and a separate node would be the
   duplication just removed in (1). AMENDS 6.2/6.3.
5. THE WORKFLOW IS ONE CPC MEGA-NODE. The state machine is its code (git, packages, exit
   checks, counters, routing); the nodes are its prompts; its one output goes to the gate.
   Item 2 at the implementation level. The transition table is the specification for that
   Python, and it is what build step 1 builds.

RIDER on (4), user-set: the arbitrator must be able to TALK TO THE USER DIRECTLY, and be
interactable whenever he wants — "it can pop itself up on my mac using tmux, or I can do
the same." The design's "no node speaks to you directly" is struck. The machine opens the
channel (a tmux launch is mechanical); the arbitrator talks. This is the fleet's existing
seat mechanism.

ASKED ONCE AT CLOSE, both ANSWERED 2026-09-05 ("that is correct. i goofed"): (a) the
coverage-type field (script / prompt / script-and-prompt / excluded) applies to what an
implementor builds, not only to tests; (b) "accepted and pushed to main" means via the gate,
per decision 14 — the user's "pushed to main" was a slip.
Also open, not the user's to answer now: parallel-validator disagreement is MOOT after (1)
— there are no parallel validators; the loop-in report's content guidance (placeholder
stands); the arbitrator's route for an unreliable test (rewrite detail); the campaign brief
in this seat's tree, unrouted.

WALK COMPLETE 2026-09-05. All eight items ruled. Next step: the rewrite.
