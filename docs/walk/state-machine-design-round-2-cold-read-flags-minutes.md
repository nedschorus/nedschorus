# Minutes: the state-machine design's second cold read — flags for the user

Walk document: docs/walk/state-machine-design-round-2-cold-read-flags.md
8 items. Opened 2026-09-05.

What this walk is about, for someone who has not read it: the design-to-main state machine
was rewritten from scratch on 2026-09-05 after its first draft failed a cold read (236
findings). The rewrite was cold-read again: 347 findings across four cells, no clean
sections, about 150 unique. The seat applied roughly 125 of them and committed the result as
14d8446 on branch design-to-main-state-machine-rewrite, naming the record directory
cold-read-records/2026-09-05-design-to-main-state-machine-design/ (machine-local). Twelve of
the applied changes follow from the user's earlier rulings but restate them in ways he has
not seen; three findings are questions only he can answer. This walk presents those.

Preceding walk, whose rulings this one cites as "item N":
docs/walk/state-machine-design-cold-read-triage-minutes.md (closed 2026-09-05, all 8 ruled).

Two facts the seat owes the user before item 1 and states there: (1) the seat told him the
cells would receive his rulings as a settled set; they did not, because scripts/cold-read-grid.py
takes only --target; (2) the round-2 count went UP 47% from round 1, and the seat's reading of
why is in item 1.

## Item 1 — 347 findings, and what the cells could not see

presented 2026-09-05 → next. No decision asked.

RIDER, user-raised: "are those flaws so big that they invalidated the cold-read - thinking we
should change cold-read to do a fast-read with gemini (30 seconds) first, then after the
author with context (you) responds to that, do the full cold-read." Seat's answer: not
invalidated — about a dozen of ~150 unique findings were absent-file citations and almost
none depended on the rulings; the deep defects needed max-effort reading. The proposal is
right by the machine's own tests-after-first-build logic: ~60% of round 2 was shallow, and a
fast pass clearing it lets the full read spend itself on what only it finds. Caveats given:
the fast pass is a lint, not a review (terra-low 0.11 recall on a design, per
cold-read-research; gemini unmeasured); the responding author must be the writer; the
response fixes contradictions and does not reword. User: "send them." SENT to md-skills-6c,
which owns the cold-read skill, with his words and the data. Not a ruling until walked.

## Item 2 — loop-in pauses the run; every design rejection is a conversation

presented 2026-09-05; REVISED by the user before ruling, three points:
1. "we could define a loop-in node to be the one where I dialog with the right agent (I
   think the arbitrator)." LOOP-IN IS A DIALOG BETWEEN THE USER AND THE ARBITRATOR. Merges
   the seat's separate "arbitrator status mode" into loop-in: every user–machine dialog is
   through the arbitrator holding the branch history. "loop-in is unusual because it is not
   a naive agent - it is with the current arbitrator." Seat's reading, put to him: the
   arbitrator instance spun up for that loop-in, fresh per loop-in, persisting across the
   conversation's turns, git as memory.
2. "If a judge is an arbitrator, call them that consistently." The class word "judge" is
   dropped; the document names reviewers and the arbitrator.
3. The initial state: "maybe I initiate the design-to-main skill? so initiate-design-to-main?"
   Fixes c1#15/c4#10 (the design node's package was circular): the user's invocation is
   the start state and the design conversation's package.
4. Second revision, user: "I'll need a loop-in skill to initiate the loop-in state. Once
   I'm looped I can [do] almost anything but at some point I'll want to stop that particular
   design-to-main, or say submit-to-gate, or update the design, or update the test-design,
   or update the contract, and then say restart? ... I guess we'll need a test-design-review
   and design-review and a contract-review that I can use (skills) or if I forget (and those
   change) that is started automatically as needed?" Seat's reading, accepted into the
   recommendation: loop-in exits are stop / submit-to-gate (his override; the gate still
   reviews) / resume; on resume the machine diffs the branch and resumes at the earliest
   state downstream of what changed (the item-6 invalidation rule applied to his edits); any
   edited document is re-read (cold read; the contract's checks) before anything builds from
   it, automatically — his own review of a document he just edited is skipped, the cold
   read is not; skills (loop-in, design-review, test-design-review, contract-review) are how
   he emits exits and are MD-skills' to write.
5. Third revision, user: "a suite that cannot run - what am I supposed to do about that."
   Struck as a loop-in trigger. Seat's replacement, in the recommendation: could-not-run →
   retry once → the ARBITRATOR, which routes to tests (bad fixture/import) or implementation
   (will not start); only an environment fault goes over-its-head, with the report naming
   what is broken. The user also listed "test-design rejection, or a contract-rejection" as
   triggers; the prior ruling (item 6.2) was the contract's SECOND correction, and a rejected
   test-design's redo reaches him at test-design-user-review anyway. Seat ASKED whether the
   list was a summary or a change. User: "I think I confused you. I was only asking about
   this - a suite that cannot run." The list was a summary; the seat read a ruling into it.
   Prior ruling stands unchanged. Only change: could-not-run → arbitrator, not the user.
6. Fourth revision, user, RENAMES: "loop in is not precise enough. let's call it
   investigate-workflow - does that work. submit-to-PR-gate". Seat: both work —
   investigate-workflow names what he does there in both the user-opened and the
   machine-opened case; submit-to-PR-gate names the shape the ruled gate (PR, 2026-08-29)
   and the interim lane share. Collision check run. The skill becomes investigate-workflow.
   The focus field values (design / contract / test-design / unknown) are unchanged.

RULED Y 2026-09-05 on the four-times-revised text. The ruled item, whole:
- The run starts at `initiate-design-to-main`: the user invokes the skill; that invocation
  is the design conversation's package.
- `investigate-workflow` is a dialog between the user and the arbitrator, which holds the
  branch history and writes the report. It pauses the run. The user may open one at any
  time with the investigate-workflow skill; the machine opens one on a design rejection, an
  arbitrator's over-its-head, a counter ceiling, or a gate rejection. A suite that cannot
  run goes to the arbitrator after one retry and reaches the user only if the arbitrator
  finds the environment at fault.
- Exits: stop / submit-to-PR-gate (user override; the gate still reviews) / resume. On
  resume the machine diffs the branch and resumes at the earliest state downstream of what
  changed; the user may name a destination instead.
- Any document edited during an investigation is re-read before anything builds from it —
  its writer's cold read, and the contract's checks — automatically; the user's own review
  of a document he just edited is skipped. design-review, test-design-review and
  contract-review skills run the same on demand. All four skills are MD-skills' to write.
- Every rejection of the design is an investigation; re-entering design-node from it is a
  redesign; the third redesign is where the machine stops.
- Two terminal states: submit-to-PR-gate and stopped.
- "Judge" is dropped; the document names reviewers and the arbitrator.
CONSEQUENCE for items 3–8 as drafted: they say "loop-in" and "submit-to-gate"; read them
with the new names. The design document is updated after the walk, in one commit.

## Item 3 — build ceiling opens an investigation; a rebuild after a correction is a build

presented 2026-09-05; the user asked for it walked ("/walk-me-through this"). Expanded into
two sub-steps at docs/walk/state-machine-design-round-2-cold-read-flags-item3-rewrite.md,
each traced through one concrete run; fast-clarify found three stumbles and one gap, all
fixed before presentation (the "unclosed" quote glossed; investigate-workflow defined at
first use; the correction arithmetic corrected to "two corrections force builds 2 and 3";
two ceilings in one moment open one investigation whose report names both).

- 3.1 the build ceiling — presented 2026-09-05, REVISED by the user: "don't say unclosed say
  that failed review" (applied); and "the ceiling beats the arbitrator - what? so the third
  failed build goes to the arbitrator - who goes to me." His sentence is the rule, and it
  replaced the seat's two-part framing: THE THIRD FAILED BUILD GOES TO THE ARBITRATOR, WHO
  OPENS THE INVESTIGATION WITH THE USER, whether the build failed review or failed the suite;
  a ruling the arbitrator would have made rides in the report instead of being acted on. No
  decision in 3.1 → next ("y").
  INTERRUPTION during 3.1: catch-up merged PR #257, git-gatekeeper renamed main-gatekeeper
  (user-ruled 2026-09-05). The design cites the old name once; queued for the post-walk
  commit with the walk's rulings. Nothing on this branch was changed by the merge.
- 3.2 presented 2026-09-05; user REJECTED THE WORDING: "You use nonsensical statements of
  course a correction is not a build. what do you mean build ... a build is when you build a
  thing - a process, not a noun." Applied: the counter counts HOW MANY TIMES THE IMPLEMENTOR
  WRITES THE CODE; "build" as a count noun is struck from the walk and will be struck from
  the design. He also said "I thought I was in the loop for designs, test designs and
  contracts. And that we tell reviewers to ignore findings about those." Seat restated the
  prior rulings: designs and test-designs he reviews every time; contracts not routinely
  (6.2, "I'd rather not"), brought in at the second rewrite; reviewers report no WORDING
  findings on prose parents but may reject one for a defect with a failure scenario. Asked
  whether he now wants every contract rewrite to reach him. User then: "up to 3 times, not
  three times" (applied) and "why does the reviewer not complain about the contract - it has
  to see that to know if the code matches the spec." Seat: it does — rejecting the contract
  is exactly what the run shows; only WORDING findings are suppressed. User then: "what do you mean
  it does not complain about the contract - why not? ... still confused. Try again, go slower
  and more carefully. /walk-me-through the process you are complaining about. Throw out this
  subwalk, and give me a real walk." The seat's sentence "reviewers do not report wording
  findings about a ... contract" read as "reviewers do not complain about contracts"; they
  do — it is one of their four verdicts. SUB-WALK THROWN OUT. Item 3 of this walk is now
  answered by a separate full walk built around one script:
  docs/walk/implementation-review-verdicts-and-code-write-counting.md (6 items). Its item 4
  carries 3.2's decision; its item 5 carries the contract-gate question. This walk resumes
  at item 4 when that one closes.
  CLOSED 2026-09-06: the inner walk ruled all six items. 3.2's decision: a code rewrite
  forced by a contract change COUNTS as a code write (fresh implementor, from scratch).
  Contract gate: unchanged — second failure. Also ruled there, and changing this design:
  the contract is a second file written by the DESIGN'S AUTHOR in the design conversation
  (contract-writer-node survives only as the corrector after the fan-out); NEW
  design-reviewer-node and test-design-reviewer-node between each writer and the user's
  review; skills only for user-invoked instructions, node instructions are node prompts
  (sent to md-skills-12). Item 3 of this walk is answered. Resumed at item 4.

## Item 4 — three missing routes: gate rejection, suite could-not-run, illegal destination

presented 2026-09-06 with the item-2 names; the could-not-run route restated as already
ruled (arbitrator after one retry). User asked what "terminal" meant and whether "rejected"
should be "fails": seat — terminal is the machine's last state, the draft had nowhere for
the gate's answer to go; "rejected" kept because the component lives on (fix in the
investigation, resume, resubmit), "fails" would say it is finished. User asked what causes
a reject. Seat's answer, TO BE WRITTEN INTO THE DESIGN: a REJECTION is the gate's review
finding what this machine's reviewers missed — a code defect with a failure scenario, or
the suite red on current main; never prose. A REFUSAL is the gatekeeper program declining
a malformed or unappliable request (bad path, stale base, conflict, main-moving-too-fast,
network-down), each naming its fix, resubmit safe: the machine's to handle — retry for
weather; a machine error (which opens an investigation) if the submit state built a bad
request. RULED Y 2026-09-06 on the gate-rejection and illegal-destination routes.

## Item 5 — two dropped rulings restored: test-design user review, -node names

presented 2026-09-06, with a note that test-design-reviewer-node now precedes
test-design-user-review. RULED Y: both restorations confirmed.

## Item 6 — contract correction invalidates both lines; arbitrator status mode; nit-repair departure

presented 2026-09-06, rewritten: 6.1 already ruled (inner walk item 4); 6.2 the separate
"status mode" is superseded by item 2 — an investigation the user opens with the
investigate-workflow skill, arbitrator as the agent; 6.3 the only decision. User asked
"what are you saying about nits"; seat explained: a nit is a real defect with no
observable consequence, recorded in the reviewer's notes, never routed and never repaired
by the reviewer, which departs from standing decision 4's "a safe nit may be repaired,
verified, and recorded locally"; §10 now names the departure. RULED Y.

## Item 7 — three open questions: prompt implementations, excluded, bounding the contract

presented 2026-09-06, with the third question restated against the user's words earlier
today (the contract is the design with more detail). User: "/walk-me-through these".
EXPANDED into a separate walk, docs/walk/state-machine-design-section-11-open-questions.md
(4 items; minutes beside it). This walk resumes at item 8 when that one closes.
CLOSED 2026-09-06, all three ruled: agent-instructions implementations cold-read in-state
and user-checked; `excluded` → `no-tests` with three reasons, tests only; the contract
bound to what the design promises its component-consumers plus what a tester needs.
SIDE RULINGS there: all states renamed by artifact-phase (table in those minutes), "caller"
→ "component-consumer". Resumed at item 8.

## Item 8 — not applied, and the next step

presented 2026-09-06, rewritten to list everything the one commit now carries. RIDER, a
long terminology exchange before the ruling, user-driven, all RULED by "Y, or
corrections" → "quick check is fine" (2026-09-06):
- The workflow gets its OWN DIRECTORY, docs/design-to-main/, holding the design (moved
  from docs/cross-project/) and docs/design-to-main/design-to-main-glossary.md, read by
  agents working there; the fleet glossary keeps pointers only. User: "most of these are
  specific to the design-to-main workflow, which most agents will run, but not be aware
  of."
- GLOSSARY RULE, user: never redefine a common SDLC word; define only carefully
  hyphenated phrases. So no entries for state, contract, rejection, refusal, check.
- The user found "user ruling" / "user-ruled" already in the glossary = settled rulings;
  "settled-rulings" STRUCK, the design says user rulings and the package carries the
  component's user-rulings file.
- "code-write" too generic → `implementation-write`, `test-write` (match the states).
- "could-not" bad; "sufficient" overclaims; "sanity-check" collides with the /sanity-check
  skill entry → `input-quick-check` (a writing state's check that what it received is
  enough to do its task) and its exit `input-quick-check-failed`.
- "check" needs a word → `acceptance-check` (umbrella). "design-agent-check" and then
  "design-agent-acceptance-check" both AMBIGUOUS ("design-agent" reads as the design
  agent, its input vs its output) → `<artifact>-acceptance-by-program` / `-by-agent` /
  `-by-user`: the actor behind "by" cannot bind to the artifact. Replaces the 2026-09-04
  tier names <artifact>-program-check etc.
- User's model, confirmed: a state is not an agent; a writing state starts with the
  input-quick-check; a reviewing state checks the previous state's output for issues that
  must be addressed.
- THE RULED PHRASE LIST for design-to-main-glossary.md: acceptance-check,
  input-quick-check, input-quick-check-failed, component-consumer, component-contract,
  component-consumer-supplies, component-consumer-receives, coverage-type, no-tests,
  can-not-be-tested, do-not-know-how-to-test, no-tests-written, implementation-write,
  test-write, gate-rejection, gatekeeper-refusal, standing-agent-instructions,
  per-run-text, investigate-workflow, initiate-design-to-main, submit-to-PR-gate. Fleet
  glossary pointers: component-consumer, coverage-type group. Existing terms used as-is:
  agent-instructions, user ruling / user-ruled, fresh agent, GHI-MD, PR process, cold-read
  run. STRUCK: node, node prompt, judge, caller, could-not, settled rulings, build (noun),
  excluded, the -node suffix, the -check tier names. All new phrases collision-checked
  2026-09-06. The state table with acceptance-by- sub-states is in this seat's fix queue.
Item 8's own recommendation (one commit, then the third cold-read run, then the PR):
RULED Y 2026-09-06. WALK CLOSED 2026-09-06, all 8 items ruled. The commit carries the
design (moved to docs/design-to-main/), the new glossary, the fleet-glossary pointers, and
the walk files of all three walks; then the third cold-read run; then the PR.
