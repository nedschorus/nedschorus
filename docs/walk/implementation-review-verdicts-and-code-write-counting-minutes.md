# Minutes: what the code reviewer can find, where each finding goes, and what gets counted

Walk document: docs/walk/implementation-review-verdicts-and-code-write-counting.md
6 items. Opened 2026-09-05.

What this walk is about, for someone who has not read it: the design-to-main state machine
(docs/cross-project/design-to-main-state-machine-design.md) has a code reviewer that reads
code against a contract and a design, and counters that bound how many times code is
rewritten. The user asked, in item 3 of the round-2 walk
(docs/walk/state-machine-design-round-2-cold-read-flags.md), for that process to be walked
slowly from one concrete example after the seat's two attempts left him confused — the
seat's sentence "reviewers do not report wording findings about a contract" read as
"reviewers do not complain about contracts", which is false: rejecting the contract is one
of the reviewer's four verdicts. This walk follows one script, create-topic-branch, through
the review and the counting. Its item 4 carries the decision that round-2 item 3.2 asked
for; its item 5 carries the question whether the user wants every contract rewrite to reach
him. Round-2 resumes at its item 4 when this walk closes.

Fast-clarify on the draft found eight stumbles and five gaps; applied before presentation:
paths for the previous walk and the round-2 walk; "second rewrite" made precise as "failed
review twice, before a third is written"; a rule for two documents at fault (reject the
highest); code that will not run is rejected as code; a fixed design counts code writes from
zero. Walk mechanics ("what is D") not applied.

## Item 1 — the component and the three documents the reviewer holds

presented 2026-09-05. User: "the code reviewer receives some instructions too, right?"
Yes — the seat's "exactly three things" was wrong. Corrected in the walk: the reviewer
receives its instructions (the reviewer prompt, the same for every component), the three
documents, the user's settled rulings on the component, and on re-review the previous
reviewer's notes; never the suite. → next ("y").

## Item 2 — the four verdicts, and the one thing never reported (wording)

presented 2026-09-05; re-presented 2026-09-06 after a handoff. The user asked whether this
was the code reviewer or the test reviewer, since "the code reviewer should not need to know
about the contract". Seat: the code reviewer (implementation-reviewer-node); both reviewers
hold the contract, at the user's own prompting (first walk item 4, 2026-09-03; triage 4.1,
2026-09-04). The user then asked what exactly is in the contract versus the design, whether
the contract expands the design, and why it is not the test-design's creation. Seat's
answers: the contract is a narrower restatement — only what a caller observes, one clause
per observable, naming its test; the design governs where they disagree, so no new
arbitration node; whether a contract may promise what the design never mentions was open
(§11); a test-side contract leaves the implementor guessing the observables. History stated:
a separate contract file was DEFERRED by the user on 2026-09-03 (first walk, Decision A) and
the contract-writer node was accepted by proceeding on 2026-09-04, not ruled.

RULED 2026-09-06, user: "I think its best if the design and design contract are in one
place." THE CONTRACT IS A SECTION OF THE DESIGN, not a separate artifact. His reasoning: the
precision the contract adds (exit 1 for "an error") is a design decision and must be
cold-read and human-reviewed like any non-nit change to the design; "if agents dont have
good instructions we've got bigger problems." Seat's condition, accepted into the ruling:
the section keeps the checkable form (five groups, one clause one observable, each naming
its test) and the machine's program check runs on it before anything is built from it.
CONSEQUENCES for the design document: contract-writer-node removed; "reject contract"
verdict removed from both reviewers (three verdicts: advance, reject code/tests, reject
design; the test reviewer also rejects the test-design); the contract correction counter
and the second-failure trigger removed; §5 becomes the contract section's form and checks;
the standard delivery is the design and the settled rulings; §11's "bounding the contract"
question dissolves — the section states only what the design decides. The user: the
initiate-design-to-main state "will need to contain multiple skills. Writing a design is
one. Adding the contract section to the design is another." Skills are MD-skills' to write.
CONCERN, user: "the contract section may be larger than the entire design." Seat's answer
and the open counting question are in the dialog after this ruling; see item 4.
CONSEQUENCE for this walk: items 4 and 5 (who pays for a contract rewrite; whether every
contract rewrite reaches the user) dissolve — a change to the contract section is a change
to the design and the user reviews every one. Item 3 stands. Item 6 to be rewritten.

SUPERSEDED 2026-09-06, within the hour, by the user, "thoughts ... still evolving": "I think
the contract can mutate without the design mutating as it will need to bring in
implementation details that are necessary for testing or full implementation. If a long doc
has 2 sections, a stable section and an unstable section i think it would be best to
separate them. My sense is the contract is full of little details that are essentially
arbitrary or irrelevant to the design. So we should separate them.
design->contract->(test design and code). In this case I won't review the contract unless I
have to." THE CONTRACT IS A SEPARATE ARTIFACT AGAIN, derived from the design before the
fan-out, as the design document already has it; the user is not its routine gate; the
seat's counting question (correction vs redesign on one document) is moot. The
consequences listed above for the design document do NOT apply; items 4 and 5 of this walk
are live again. Two things the user added:
1. A NEW NODE that reviews the contract against the design, with its own instructions,
   because "once some agent ... writes the contract" nobody human reads it. Who writes the
   contract is open — his words: "(naive? the one that writes the initial design I think)".
   The seat's answer and recommendations follow in the dialog; rulings recorded below when
   given.
   RESOLVED 2026-09-06: the user withdrew the contract-reviewer idea on the seat's
   explanation that the consumer's input check is the producer's output check (the
   implementor and test-designer each compare the contract to the design before writing,
   with could-not). He then asked for a DESIGN REVIEWER: "we have reviewer node for code,
   for test, I think for test-design, but we don't for design. Sounds like we should."
   Seat corrected the count (none for test-design either) and recommended
   design-reviewer-node and test-design-reviewer-node between each writer and the user's
   review, running the consumers' checks before the user reads; flagged that this un-folds
   the 2026-09-05 validator ruling for the two intent artifacts, on a new argument (the
   user's time). AWAITING Y/N/D.
   WHO WRITES THE CONTRACT — RULED 2026-09-06: THE DESIGN'S AUTHOR, in the design
   conversation. User: "The contract is part of the design - just more detail ... I think
   the author, as that way as we build the design we can discuss the contract section too.
   Its hard for me to believe it's easier to discuss the contract without that impinging on
   the design." Seat's completeness-test argument for a fresh writer conceded: the gaps a
   fresh writer would bounce as could-not are found live, with the user, in the
   conversation.
   RULED 2026-09-06 ("yes to all"), three rulings at once:
   (a) TWO FILES: the design and the contract are separate files, one author, written in
       the one design conversation. Reason: a clause fixed by a fresh agent after the
       fan-out must not edit the design the user approved. Consequences: contract-writer-node
       is no longer a writer — design-node emits the design and the contract together; the
       contract's program check runs on emission; the implementor and test-designer still
       compare it to the design before writing (could-not); corrections after the fan-out
       are written by a FRESH agent from the reviewer's notes (the surviving role of
       contract-writer-node), counted separately, the second failure brings the user in;
       the contract is in the user's design-review package because he discussed it, and he
       reads as much of it as he chooses.
   (b) DESIGN-REVIEWER-NODE and TEST-DESIGN-REVIEWER-NODE: a fresh agent between each
       writer and the user's review, receiving the document and the settled rulings,
       running the consumers' enumerated checks (every path's promise stated, no
       contradiction, buildable), reporting no wording findings, emitting advance (to the
       user's review) or reject (to the writer with notes). A rejection here is a
       correction before approval, not a redesign. Intent stays the user's. Names checked
       for collision 2026-09-06: none. This un-folds the 2026-09-05 validator ruling for the
       two intent artifacts, on the user's time as the new argument.
   (c) the skills rule below goes to MD-skills. SENT to md-skills-12 2026-09-06.
2. SKILLS VERSUS NODE INSTRUCTIONS, user's rule: prose instructions are a skill only if
   used outside the state machine, e.g. at the user's request; instructions that exist
   only for a node are "canned instructions", not skills. "We may have messed that up
   which means we may have to recategorize some proposed skills and agent-instructions."

## Item 3 — verdict two traced: the code is wrong; up to three code writes

presented 2026-09-06 → next ("y"). No decision asked; restates the previous walk's 3.1
and 6.8.

## Item 4 — verdict three traced: the contract is wrong; the forced code rewrite counts

presented 2026-09-06, text adjusted for the item-2 rulings (the contract's mistake is one
the design conversation and the design reviewer missed; a fresh agent, not the user, fixes
the clause). RULED Y: user, "If you reject a precursor you reject everything after it. This
means that if a long code edit has a 2 instead of a 1, that we throw out the whole edit,
because the always naive writer won't see it, but that's not terrible." Matches the
design's rule (§3.2: a corrected contract invalidates everything built from the old one);
the seat confirmed that on a contract correction the fresh implementor receives the design,
the corrected contract and the rulings, NOT the old code — old code and notes are delivered
only when the code itself was rejected. A CODE REWRITE FORCED BY A CONTRACT CHANGE COUNTS AS
A CODE WRITE. This is the decision round-2 item 3.2 asked for.

## Item 5 — when the user is called; contracts at the second failure, or every rewrite?

presented 2026-09-06, text adjusted for the item-2 rulings (the user sees the contract's
first version because it is written in his design conversation). RULED Y: the prior ruling
stands — the user reviews every design and test-design version; a corrected contract reaches
him only when it has failed review twice. The round-2 item-3 question ("I thought I was in
the loop for ... contracts") is answered: he is, at the first version, in the design
conversation; not routinely afterwards.

## Item 6 — what this walk settled

presented 2026-09-06, rewritten to carry the item-2 rulings → next. WALK CLOSED 2026-09-06.
The round-2 walk resumes at its item 4.
