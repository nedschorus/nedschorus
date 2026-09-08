# Minutes: the state-machine design's third cold read — what was fixed, and seven decisions

Walk document: docs/walk/state-machine-design-third-cold-read-decisions.md
9 items (8 at opening; item 8 added 2026-09-07, see item 1). Opened 2026-09-06.

What this walk is about, for someone who has not read it: on 2026-09-06 the design-to-main
state-machine design (docs/design-to-main/design-to-main-state-machine-design.md) was
rewritten with the rulings of three walks (commit 2604e5f) and then had its third cold read
(six reviewer agents; about 500 findings, about 60 distinct; the reports and the
dispositions are machine-local in
cold-read-records/2026-09-06-design-to-main-state-machine-design/). The seat applied the
contradictions it had written itself in a second commit (33b300d) and did not apply what
the user had ruled. Seven findings need the user's word; this walk asks them. When it
closes, the pull request is opened, as the user ruled in item 8 of the round-2 walk
(docs/walk/state-machine-design-round-2-cold-read-flags-minutes.md). This is a top-level
walk, not nested.

Item 8 of the walk document is written as "what this walk asked" and is rewritten at the
close to carry the actual rulings. The walk document was clarified from its draft on
2026-09-07 (fast-clarify suggestions applied: D defined in the opening; the twice-failed
ruling, the fleet glossary, and the round-2 item 8 cited by link; item 5's example made
self-contained; item 8 retitled).

## Item 1 — what the read found, and what was fixed without asking

presented 2026-09-07 (session continued from a handoff; the retiring session wrote the
draft). <next> "Continue". RIDER: "let's go over my 16 at the end of this walk" — the
sixteen findings not applied because the user had ruled them (dispositions section B,
eleven groups). RE-PLANNED: they become item 8, in two parts (8.1, 8.2); the summary
becomes item 9; the walk is now 9 items. No fix of item 1 was overruled.

## Item 8 — the sixteen findings not applied (added 2026-09-07 at the user's request)

8.1 presented 2026-09-07 (groups 1–6: stopped; the three skill-and-state names; the
acceptance-by- names; arbitrator; coverage-type; the contract by the design's author) →
<next>, nothing reopened. Between 8.1 and 8.2 merge-lane-e7 asked whether two sentences
of the objective page's node section are in the design ("an explicit input package";
"nothing that matters exists only in a chat message"); answered yes to both with the
design's sentences (§2 state-package; §1 "Between agent instances, only files cross"),
recommending the section go.
8.2 presented 2026-09-08 (groups 7–11). User REOPENED two: "Seems like we should know if a
design-main passed or failed, that stopped isn't enough ... Is that one state with two
possible values, or two states? why green and red - why don't a label that make sense like
accept or reject?" Seat: one terminal state (every ending commits, pushes, keeps the
branch), renamed `ended`, outcomes `passed` (gate accepts), `failed` (a ceiling),
`stopped-by-user`; and CORRECTED ITSELF — green/red were never the user's ruling, the seat
kept them on its own (B8 was misfiled as ruled); renamed to `pass` / `fail`,
`could-not-run` kept. RULED Y ("y - make sure the deferred items are captured as tasks or
in some GHI"). APPLIED: the design (state table, transitions, diagram, §3.4, §6.4, §6.5,
§7, §2) and the glossary; twenty lines, no other file used the words. Groups 7, 9, 10, 11
stand. DEFERRED ITEMS captured: the design's §11 (nine builder items, three owned
elsewhere) drafted as a GHI body, "Build the design-to-main state machine", to be filed
through ghi-write right after the PR is up so its citations open (ghi-info ask failed
tonight, claude exited 1; the ladder search found no existing issue; #237 is philosophy,
not the build). Task #6. <revised> then <accepted>.

## Item 9 — what this walk settled, and the next step

presented 2026-09-08, rewritten to carry the actual rulings → "y". WALK CLOSED 2026-09-08,
all nine items ruled (item 6 ruled during item 5 and not presented). Held as tasks for the
user's word: the docs/agents/queue/ rule relayed by md-skills-9e; carrying the layout
rulings to #224; the cold-read citation form if ruled in md-skills' walk; filing the
build issue right after the PR. Next: merge origin/main into the branch, one commit with
this walk's rulings and its four files, push, PR.

## Item 2 — the user's glossary rule applied to the document's own words

presented 2026-09-07. <revised> then <accepted>: "keep nit. It's standard SDLC. And nits
are easy to observe" — the seat's rename to `unobservable-defect` and its definition ("a
real defect no component-consumer can observe") were wrong: a nit is observable, it is
small and of no consequence to a component-consumer. APPLIED: `nit` restored in the design
(§ vocabulary, reviewer verdicts, notes, the no-local-repair rule) with the sentence "A
nit is the standard word: a small defect of no consequence to any component-consumer.
`exxample` for `example` in a comment is one; the same typo in a CLI flag is a contract
defect, because a component-consumer depends on it." The glossary's `unobservable-defect`
entry deleted; `nit`, a standard word, gets no glossary entry by his hyphenation rule.
"y for the rest": the other seven renames (state-exit, state-package, standard-package,
contract-revision, test-design-correction, implementation-work-stream/test-work-stream,
investigation-focus) RULED Y.

## Item 3 — the short exit words

presented 2026-09-07. RULED Y: the short words (advance, emitted, discuss, stop, resume,
green, red) stay. Rider answered: the reviewer was the Codex hunt cell at the good tier
(report codex-hunt-good, finding on the exit-record schema), citing CLAUDE.md's naming
rule for grepped names.

## Item 4 — flaky-test, escalate-to-user; arbitrator vs the fleet glossary's adjudicator

presented 2026-09-07. RULED: "Keep arbitrator - scrub out adjudicator." `flaky-test` and
`escalate-to-user` stand as applied. APPLIED: the fleet glossary's `adjudicator` entry
replaced by `arbitrator` (same definition, alphabetical place); the one other use, in
docs/wiki/queue/agent-loop-rules-draft.md ("maintained by its adjudicator"), renamed.
No "older word" note kept — he said scrub. The word no longer appears in the repository
outside the machine-local cold-read records and this walk's files.

## Item 5 — the user's contract check, settled

presented 2026-09-07. Reply: "0 is not a good error code" (agrees with the example), then
two riders, no Y yet:
- RULING on escalation: "When things get escalated to me I need to have a dialog with the
  arbitrator agent. It should prepare a report, then run walk-me-through on that report,
  then tell me it needs to walk through the unresolved problem with me. Together we will
  try to determine a course of action, which may change the design, test-design,
  contract, possibly adding user-overrides to any of them." APPLIED to §6.6
  investigate-workflow (report delivered by walk-me-through, then the walk of the
  unresolved problem, course of action may change design/test-design/contract or add a
  user ruling that overrides any of them) and to contract-acceptance-by-user (the two
  versions delivered the same way; the dialog ends in advance/discuss/investigation).
  "user-overrides" mapped to the existing user-rulings file, not a new name.
- QUESTION: is the workflow always integrated with a PR, do agents have access to it, and
  if so the PR must align with the context documents and the design must say so.
  ANSWERED: a PR always exists at the end (PR process today; the gatekeeper opens one once
  active, ruled 2026-08-29); none exists during the run; no launched agent reads a PR; the
  machine writes the PR body from the run's record and says nothing the documents do not;
  gate findings return only as a gate-rejection. APPLIED to §3.4.

Item 5 restated 2026-09-07 after the user lost context; split into 5.1 and 5.2 (340 words).
On 5.1 the user RULED TWO MORE THINGS, correcting the seat's reading as "overly simple":
- ANY AGENT MAY REACH HIM. "The arbitrator can reach out to me whenever they need to.
  Maybe some other reviewers can too? If agents really need to reach out to me, they
  should. I may need to tighten up that prompt if they over use their privilege."
  APPLIED: `escalate-to-user` is no longer the arbitrator's alone. Any launched agent may
  take it, whatever its state; it routes to investigate-workflow, focus `unknown`. Changed:
  §6.1 verdict list, §6.5/§6.6 (a new paragraph in The channel), the §3.1 note under the
  states table, one general row in the §3.2 transitions table, and the glossary entry. The
  control on overuse is the agent-instructions of every launched agent, tightened if
  abused; the machine never refuses an escalation. Standing decision 20 (never a question
  another state could settle) is where the discipline is stated.
- ALWAYS, NOT ONLY. "A correct contract always reaches me when it fails review twice -
  always and only not the same." The seat had written the ceiling as the ONLY path to him.
  It is a GUARANTEE, not a restriction: at the second failure the contract always reaches
  him, and that does not bar an agent from reaching him earlier. APPLIED in §5.3 and §6.6
  ("without fail at the revisions ceiling ... an always, not an only").
The user then NARROWED the roster (2026-09-07): "Since I only want to read prose, I think
the reviewers and arbitrators and non code writer can reach out to me, (if they think the
problem is in the design, test design only. The contract they should try to resolve
(twice)." He asked what had been decided; the seat cited: not a routine gate on the
contract (2026-09-04), the nine-pass loop he found and the second-failure trigger, one
report type per loop-in written by the triggering agent, and round-2 item 2 (the dialog is
with the arbitrator). The seat flagged its own drift: the design now says "the agent that
escalated does the talking," which contradicts round-2 item 2.

STEP-BY-STEP, opened by the user 2026-09-07 ("let's go through every step together"). His
model, in his words: first half he works with THE INITIATOR (the design conversation's
agent, best context), carrying every reviewer's comments — design rejected, contract
writer can't, contract fails twice, any writer or reviewer flags the design; second half
he works with FRESH INITIATORS that read everyone's comments; he wants nothing to do with
code; test-design writers fix the contract without him (invalidating the code); code or
test failures go to the arbitrator, "and they can pull me in if they need to." The seat's
assessment: this SUPERSEDES round-2 item 2 (arbitrator as dialog partner) with the
initiator, coherent because the arbitrator never edits the design and the user only deals
in design/test-design prose; it BENDS the one-instance rule for the first half. Two design
passages written tonight are HELD until the steps land: §6.6 "any launched agent may reach
the user" and "the agent that escalated does the talking." Chances, ruled during the steps (2026-09-07), in the user's words:
- "I'd like to give the arbitrator a lot of autonomy (it get 3 chances). I could give the
  initiator 2 times. but encourage it to work with me if it's not sure. ... And I can
  reset the chances with a word." Seat mapped: the three are the writers' ceiling (ruled
  2026-09-05); the initiator's two is a NEW counter, design revisions before approval,
  ceiling two, reset at approval; "reset" is a user ruling that zeroes the current
  version's counters, recorded in user-rulings.md; the initiator may come to him sooner
  when unsure.
- Seat asked one budget (three writes shared by reviewer and arbitrator; the arbitrator
  gets at most two, possibly zero) or two. User: "I'd give the arbitrator 2 chances.
  Otherwise they might get zero?" RULED TWO BUDGETS. Mechanism to apply: the reviewer's
  three writes per stream per design version as today; at the ceiling the arbitrator RULES
  instead of opening the investigation; a new arbitrator counter per design version,
  ceiling two, incremented on entry; a write the arbitrator orders is bounded by the
  arbitrator's counter, not the writer's; on its third entry the arbitrator brings the
  user in. Worst case rises from six writes per version to eight. "The arbitrator
  increments nothing" is struck; the machine increments its counter.
- THREE BUCKETS, user: "I'd distinguish between code thrown out because it failed
  testing (which the arbitrator would have to decide) or code that was thrown out for some
  other cause (changed design, or contract, or for test code, changed design, contract,
  or test-design). Which I think means the arbitrator gets its own quota of chances."
  Seat's table: failed review → the writer's three; failed the suite → the arbitrator's
  two; upstream document changed → that document's counter only. The seat named that the
  third bucket REVERSES the fourth walk's item 4 (2026-09-06: a forced rewrite counts as a
  code write) and recommended the reversal (a double charge otherwise).
"all approved" (2026-09-07) — RULED Y, all of: step 1 (the initiator revises alone up to
twice before approval, comes to him sooner if unsure, brings him in at the third
rejection; the user's `reset` zeroes the current version's counters); two budgets (the
arbitrator's own counter, ceiling two, rules alone on entries 1–2, brings him in on 3; a
write it orders is bounded by its counter); three buckets (forced rewrites bounded by the
upstream counter alone — the 2026-09-06 item-4 ruling is SUPERSEDED). Not yet applied to
the design; the step-by-step continues at step 2 (the contract writer).
STEP 2 (the contract writer), 2026-09-07: RULED Y — "It makes sense to give the initiator
the initial contract." The initiator writes the first component-contract in the design
conversation (as ruled 2026-09-06); a reviewer's reject of the contract before approval
returns to the live initiator under step 1; the fresh contract writer of his account is
contract-revising, after approval, whose input-quick-check-failed against the design opens
the dialog with an arbitrator.
STEP 3 (the contract fails twice after approval), 2026-09-07: RULED Y — the user works
with a FRESH ARBITRATOR, not the initiator (his later "once I start working with
arbitrators I only work with them" overrides his earlier "I'd want to work with the
initiating agent"); outcomes: advance one version, rule and a fresh reviser writes from
it, or redesign (counted). The separate "open an investigation" exit folds away: the
dialog with the arbitrator IS the investigation.
STEP 4 (what the test-design, code and tests may flag), 2026-09-07: RULED Y — "4 -
approved - though these cycles are limited." Every writer and reviewer below the design
may reject the contract (a fresh reviser, no user; an advanced revision invalidates the
code built on the old one) or the design (the dialog with an arbitrator). The cycles are
bounded by the existing counters: contract-revisions two, test-design-corrections two,
redesigns two, per design version. Below the design the user reads three things: the
test-design, an implementation that is a prompt, and a prompt-based-test.
NAMING, proposed during step 4 and not yet answered: the user's `-based-test` pattern
("Prompt-based-tests I think. Code-based-tests, CPC-based-tests, User-based-tests,
Simulated-user-based-tests, web-scripting-based-tests") — seat proposed: nouns in prose
(code-based-test = coverage-type script, prompt-based-test = prompt, CPC-based-test =
script-and-prompt), the values unchanged; the by-hand demonstration renamed
user-based-test; the other kinds added when a component needs one. Plus the user's check
on prompt-based-tests running on the SET (all delivered with cold-read reports and the
reviewer's notes; he reads what he chooses), after "if we generate massive numbers of
tests that are prompts I can't review all these."
STEP 5 (code or tests fail; the whole shape), 2026-09-07: RULED Y ("y" to a message
carrying the naming question and step 5; taken as covering both, said so to the user).
The whole shape: invocation → approval, one live initiator reading each reviewer's notes;
approval → gate, fresh arbitrators reading everyone's; nothing else talks to him. The
arbitrator on each entry receives the whole branch; on its third entry, or sooner if it
genuinely needs him, it prepares and cold-reads its report and walks him through it.
STEP-BY-STEP CLOSED. The seat now applies all of it to the design in one pass, then
returns to item 5 for its Y. Task #1 (merge-lane's relay that arbitrators write no
verdicts) is answered by tonight's direct rulings: the arbitrator rules alone twice.
CORRECTION on the switch, 2026-09-07, after item 5.2 was presented: "After approval -- I
thought we kept talking to the initiator until we had code and test code? Then we switched
to the arbitrator - because that code will overwhelm the context of the initiator." The
seat had put the switch at the design's approval; it is at the first entry of
test-suite-executing (both work-streams at ready-for-test-suite). APPLIED: §1, §2, §4,
§5.3, §6.6 (contract paragraph, investigate-workflow, the channel), the §3.2 row, the
glossary (initiator, investigate-workflow), walk item 5.2. Step 3's "fresh arbitrator"
at the contract's second failure becomes the initiator while it lives. The round-2 item 2
ruling (dialog with the arbitrator) now holds only after the switch.
Two wording rulings on the restated 5.2: "below is the wrong word. After. You don't have
to say nevers." APPLIED in the walk, the design (§2, §6.6) and the glossary: "after the
design" for "below the design"; the emphasis nevers dropped from item 5 (the design's
rule-nevers, e.g. a reviewer never edits, left; the user told).
ITEM 5 RULED Y, 2026-09-07, entire: the contract check's moment and three outcomes; the
initiator until code and tests exist, arbitrators after; the chances (initiator two,
writers three by review, arbitrator two, upstream changes on their own counters, reset);
what he reads after the design; the pull request written from the record. <accepted>.

INTERRUPTION during item 5, 2026-09-07: merge-lane-75 (the merge-lane seat, recycled from
merge-lane-16) asked for this design's roster of "nodes" for the objective page's node
section, which the user was walking with it at that moment. Answered from the design: the
design has no nodes (the user struck the word 2026-09-06), states are not agents, and the
mapping is by what a state launches. Also answered: the contract's three checks; what a
reviewer emits (state-exit + notes); that a reviewer may reject any upstream artifact,
furthest upstream when several are at fault; and that the unit reviewed is one artifact,
never a pull request. Merge-lane relayed two rulings of the user's, recorded as reported
and NOT applied on a relay (hearsay): the contract counts among the files that land on
main, and the design, contract and test-design live in one directory (§9 already does the
latter; the former is item 7's open gate-payload question).

OPEN QUESTION raised by that exchange, to put to the user: merge-lane reports the user has
ruled that arbitrators do not write verdicts and are not judges. §6.5 of this design gives
the arbitrator seven verdicts in a table. If the ruling is as relayed, §6.5 is wrong and
must change. Not applied on a relay; asked directly.

## Item 6 — prompt tests reach the user (a consequence of the standing-vs-per-run rule)

RULED N ahead of its turn, 2026-09-07, during step 4 of the step-by-step under item 5:
"tests dont reach me - why is tests here". The seat's symmetry inference from the
standing-vs-per-run rule was wrong to make on his behalf. `test-acceptance-by-user` is
removed: no test reaches the user, whatever its coverage-type. Kept, as his own
2026-09-06 ruling (fifth walk, item 1): an implementation that is agent-instructions
reaches him after the agent check. Item 6 dropped from the presentation; the walk goes
from item 5 to item 7.

REVERSED minutes later, same session, once the phrase was unpacked: "tests of prompts is
the ambiguity - I want to review some prompts - but not the tests of those prompts" and
then "I think I should review tests that are prompts. They are usually both short and
important." RULED Y: a test of coverage-type `prompt` — a test that is itself
agent-instructions run by a single-purpose agent — reaches him after the agent check.
Tests that are scripts never do, including script tests of a prompt implementation.
`test-acceptance-by-user` STAYS as the design has it. Item 6 is ruled Y, still dropped
from the presentation. The seat's phrase "a test of coverage-type prompt" was the
ambiguity: it reads as a test OF a prompt; the design's sense is a test that IS one.

## Item 7 — the branch layout, and where durable prose lands after acceptance

presented 2026-09-07. RIDERS before the ruling:
- "I'd think tests would be in a subdirectory of the code it tests. I like carefully
  structured directories ... Think of subdirectories like tags." Seat: the project has no
  rule today (scripts/ is flat, each test a sibling file, twenty-odd pairs); proposed
  scripts/<component>/tests/, then WITHDREW it on finding GHI #224 (2026-08-31, open):
  nc-systems/<system>/ holding everything a system owns; user-ruled there that a system
  earns its directory; pilot on backup-and-recovery not landed. No wiki page on layout
  exists.
- "maybe claude.md needs some guidance on directory structure - I'd think a link to a wiki
  page on our current and planned directory structure. Is there any notes in the ghi or
  queue about this? ... and what is best practice." Seat: #224 is the note; best practice
  listed (group by system not file type; tests beside what they test in tests/; a map per
  directory level; no maturity in names; depth for meaning). CLAUDE.md line deferred until
  the wiki page exists; the seat shows the sentence first. Separate topic, own PR.
RULED Y: the layout as applied; tests in a subdirectory of the component's directory as
the RULE; concrete paths deferred to #224's layout rule. Then, same message: "The systems
will be fairly hierarchical, with matching hierarchical directory structures. I guess this
system is the design-to-main - would the directory be called that? What should be its
subdirectories. Also it seems obvious to me that our state machine should be in python.
This might be useful to look at or borrow before we build our own -
https://the-pocket.github.io/PocketFlow/core_abstraction/node.html So where does that
leave walk-me-through and cold-read. Maybe a user-skills?" — answered: the system is
design-to-main; proposed subdirectories docs/, machine/ (Python, with tests/),
agent-instructions/, skills/, walks/; not design-to-main-runs/ (a run's, on its branch).
Python agreed; PocketFlow read (prep/exec/post, post returns an action string, `node_a -
"rejected" >> node_b`, nested flows) — recommend borrowing the shape, not the dependency;
noted for §11 step 1. walk-me-through is one skill file; cold-read is in four places
(.claude/skills/cold-read/ with prompts/, seven scripts in scripts/, a draft design in
docs/drafts/, cold-read-records/). Neither is this system's; #224 sorts them. RULED
(2026-09-07, for #224, not this walk): "seems like cold-read should have its own
directory." Recorded to carry to #224 as a comment via ghi-write when the user says so;
not filed unasked. Skills stay under .claude/skills/ because the harness reads them
there; a link or one-line skill pointing into the system's directory is #224's answer.
RELAY from md-skills-9e (2026-09-07): agent-instructions draft in docs/agents/queue/ and
land in docs/agents/ when they pass the full cold-read; PR #280 (on main, eb81a5a) put the
queue into the cold-read skill. Recorded as a relay; put to the user, not yet confirmed
in his words here. Consequence if it stands: the machine's per-state agent-instructions
draft there; the proposed agent-instructions/ subdirectory yields to it until #224.
THE TWO OPEN QUESTIONS, RULED 2026-09-07 in the user's own model: "designs before code are
in the design-queue, and once we start writing code and tests in a system or subsystem
directory. the wiki links to the designs once they are in use. Topic branches are fine
for stuff in process - but presumably their directories mirror main." Then, on the run's
record, which must be on the branch for agents on two machines to pass notes: the seat
offered merge-it or gate-deletes-it-and-the-retained-branch-keeps-it; user: "That works"
for the second, and asked whether git preserves it — yes, every commit a kept branch
points to. APPLIED to §2, §9 (table rewritten: docs/designs/queue/ for the design and
contract before code, by the pattern of the three existing queues; the component's
directory once code exists, tests in tests/; the record in
<component>/design-to-main-record/, deleted by submit-to-PR-gate before the gate;
design-to-main-runs/ gone; directories mirror main) and §11 (the landing question closed;
the gate-payload question reduced to commit-vs-branch; a step-1 note: Python, read
PocketFlow, borrow the shape not the dependency). ITEM 7 RULED Y entire. <accepted>.

