# Minutes: three questions the state-machine design leaves to the user

Walk document: docs/walk/state-machine-design-section-11-open-questions.md
4 items. Opened 2026-09-06.

What this walk is about, for someone who has not read it: the design-to-main state machine
(docs/cross-project/design-to-main-state-machine-design.md) lists in its §11 three questions
only the user can answer: whether a prompt-typed implementation is cold-read as well as
reviewed; whether `excluded` is a value an implementor can exit with; and how to bound the
contract's "everything a caller can observe". Item 7 of the round-2 walk
(docs/walk/state-machine-design-round-2-cold-read-flags.md) presented the three in one item
and recommended leaving two open; the user asked for them walked ("/walk-me-through these").
This is the third nesting level: the round-2 walk is paused at its item 7, and the inner
walk on reviewer verdicts (docs/walk/implementation-review-verdicts-and-code-write-counting.md)
closed earlier today. The round-2 walk resumes at its item 8 when this one closes.

Sources: the coverage-type vocabulary ruled 2026-09-03 in the MD-skills seat
(/Users/el/agents/MD-skills/docs/walk/cold-read-terminology-pass-rulings-minutes.md, item 1,
not on main); the user's 2026-09-05 confirmation that the field applies to implementations
(docs/walk/state-machine-design-cold-read-triage-minutes.md, "ASKED ONCE AT CLOSE");
today's rulings that skills are only for user-invoked instructions and that the contract is
the design with the details needed for testing or full implementation
(docs/walk/implementation-review-verdicts-and-code-write-counting-minutes.md, item 2).

## Item 1 — a prompt-typed implementation: cold-read as well as reviewed?

1.1 presented 2026-09-06 (what a prompt implementation is; the two rules; the fleet's
practice; today's skill / node-prompt split). RIDER, user: "NOte this. Some prompts are
actually prompt forms with certain sections filled in mechanically, or only certain
sections customized to the reader. The cold read will need to read a sample, filled in
form, not the blank or pre-filled in form." ACCEPTED into 1.2's text and the design's §4
sentence: a prompt that is a template is cold-read as a filled-in sample, the way its
reader will receive it. The fleet's example: the handoff supervisor composes each seat's
launch prompt from a template with the seat's handoff filled in; a reviewer node's prompt
is the same prompt with the component's package filled in.
1.2 presented 2026-09-06. User, on wording: "I think the right word is agent-instructions.
see nedschorus glossary." APPLIED: the glossary (docs/wiki/nedschorus-glossary.md) defines
agent-instructions as "prompts or MD files that instruct agents"; "node prompt" is struck
from this walk, the fix queue and the design; a node's instructions are its
agent-instructions. The coverage-type value `prompt` keeps its ruled name. User then: "what is a
node-prompt - not all nodes are agents, so not all nodes get prompts. agent-instructions is
the word for instructions to agents, and if a node is simply an agent . and only in that
case would it also be a node prompt." APPLIED: "agent node" wherever agent-instructions
are meant; user states and machine states have none; the design's §1 "An agent node is a
prompt" is queued for rewording. User then REJECTED the skill-versus-agent-node split for
his review: "Nope. I'm not going to read review comments, for instance. But I will read
the instructions to the reviewer on how to prepare comments, or the instructions to the
code writer on how generically they should write stuff - for instance/ So it's not that
simple." REVISED: the line is STANDING versus PER-RUN — agent-instructions any agent will
follow (a skill or an agent node's instructions) are final prose and reach him after their
cold read; text one agent writes during a run for another (review notes, a could-not, a
corrected contract) does not. Consequence proposed: a prompt-typed implementation gets a
user-review state after the implementation reviewer advances it. User then: "what is a
prompt-typed or prompt-typed implementation. Use our glossary please." APPLIED: the seat's
coinage struck; the walk says "an implementation that is agent-instructions, coverage type
`prompt`" and, for tests, the ruled phrase "a test run by a single-purpose agent". Queued
for the design: same replacement in §2, §4, §5.2, §11. Awaiting Y/N/D.

SIDE RULING, STATE NAMES, 2026-09-06. The user pasted a critique (another model's, "I
dont agree with all these comments but they do indicate the confusion"): the state table
mixes roles (implementor-node), verbs (initiate-) and waiting conditions (stopped) in one
column; -node adds nothing; states should be named [artifact]-[phase] with the worker as a
parameter. Seat: right on the schema (the design's own "a node is a state"), the suffix
(his 2026-09-04 ruling, his to reverse), contract-writer as a revision phase, and the
symmetry; wrong for this project on UPPER_SNAKE (kebab-case everywhere), "Agent / Human"
workers (implementors and reviewers are always agents; he is a gate on prose), renaming
the arbitrator to a diagnoser and investigate-workflow to an escalation (his own names,
yesterday), "pushes green build". Kept from it: test-suite execution must launch a
single-purpose agent for each `prompt`-type test — the design must say so. User RULED Y on
the seat's kebab-case table with four changes: (1) keep `initiate-design-to-main` (and,
by the same reason, `submit-to-PR-gate`); (2) the user reviews are user+agent and "the
user step is part of the reviewing state. That is we have 2 levels of states - this is
where the acceptance check can go" — each reviewing state is a COMPOSITE state whose
sub-states are the acceptance-check tiers he ruled 2026-09-04 (`<artifact>-program-check`,
`-agent-check`, `-user-check`), the user's check last; (3) most states are code+agent,
not agent; (4) "suite" → "test-suite". Then: "I dont think the kind column is usual
because all the user states (or substates) are named" — KIND COLUMN DROPPED; the name
carries the worker. THE RULED TABLE:
- initiate-design-to-main
- design-writing (in conversation with the user; emits design + contract)
- design-reviewing = design-agent-check → design-user-check
- contract-reviewing = contract-program-check → contract-agent-check → contract-user-check
  (the last only on the contract's second failure)
- contract-revising (replaces contract-writer-node)
- implementation-writing (replaces implementor-node)
- implementation-reviewing = implementation-agent-check → implementation-user-check (the
  last only when the implementation is agent-instructions; item 1.2, pending)
- test-design-writing (replaces test-design-node)
- test-design-reviewing = test-design-agent-check → test-design-user-check
- test-writing (replaces test-implementor-node)
- test-reviewing = test-agent-check
- test-suite-executing (replaces suite-run; launches a single-purpose agent per
  `prompt`-type test)
- test-suite-arbitrating (replaces arbitrator-node)
- investigate-workflow (unchanged)
- submit-to-PR-gate (unchanged)
- stopped (unchanged)
REVERSES triage item 3 (-node suffix) at his word; RENAMES nothing the skills are called.
Every new name is to be collision-checked before the design is edited. "Judge" and
"node" as a word for an agent are struck; a state is a state, an agent is an agent.

ITEM 1 RULED Y 2026-09-06, on 1.2 as last stated with the new names: an implementation
that is agent-instructions (coverage type `prompt`) is cold-read by its writer inside
implementation-writing before emission; a form is cold-read as a filled-in sample; after
implementation-agent-check advances it, it goes to implementation-user-check, because
standing agent-instructions reach the user and per-run text between agents does not; a
script skips both. Same on the test line for a `prompt`-type test (test-writing cold
read; test-agent-check). The design's §4 sentence is replaced as written in the walk file.

## Item 2 — `excluded` on the implementor's exit

presented 2026-09-06. User: "confused. something with nothing doesn't enter the machine?
reasons, is  a value ?" REWRITTEN as a story around branch protection on main (a GitHub
setting, applied by hand 2026-07-21: no file, so nothing to review, test or land; done by
hand, outside the machine). Re-presented. User then RENAMED the test vocabulary: "how about
no-tests: (reasons) can-not-be-tested, do-not-know-how-to-test, no-tests-written." Seat's
mapping against the 2026-09-03 reasons, stated to him: can-not-be-tested = can't-test;
do-not-know-how-to-test = don't-know-how-to-test (still reaches the user); no-tests-written
= no-test-needed AND no-test-available, the sentence saying which. Collision check clean.
RULED Y 2026-09-06: an implementation's coverage type is script / prompt /
script-and-prompt; only a test can be `no-tests`, with one of the three reasons and a
sentence; a design that asks for something that is not a file in the repository is done
by hand and does not enter the machine. SUPERSEDES the `excluded` value and its four
reasons ruled 2026-09-03 in the MD-skills seat — to be SENT to md-skills-12 (owner of the
write-test-plan text) at the user's word; the design's §2, §5.2 rule 3 and §11 change as
written in the walk file, with `no-tests` in place of `excluded`.

## Item 3 — bounding the contract

presented 2026-09-06. User: "what is a caller - the agent that reads the design?" Seat:
no — whatever invokes the component or reads what it leaves (for create-topic-branch: the
agent or the machine running it; git and the gatekeeper reading the branch). User:
"designs can have multiple callers. subroutines have callers, designs can have consumers I
guess" → seat proposed "consumer"; user: "i suggest design-consumer - consumer is too
generic"; seat objected that design-consumer reads as a consumer OF the design (the
writers), the thing consumed is the component, and proposed component-consumer; user:
"component sounds like the right word", then asked whether a design has multiple
design-components and whether CLAUDE.md's naming rule requires the longer name. Seat: the
rule requires the check and lengthens only on collision or ambiguity (component-consumer
is clean); "design-component" would be a new idea — today one design describes one
component and everything is per component — worth its own item if wanted. User: "ok".
RULED Y 2026-09-06: the bound is what the design promises its component-consumers plus
the details a tester needs to observe those promises, and nothing else; a clause belongs
if deleting it leaves a promise unobservable; "caller" → "component-consumer" throughout,
the contract groups become component-consumer-supplies / component-consumer-receives
(renames the 2026-09-04 group names at his word; collision-checked clean); ONE DESIGN,
ONE COMPONENT stands. "component-consumer" goes into the glossary with this meaning.

## Item 4 — what this walk settled

presented 2026-09-06 → next ("y"). WALK CLOSED 2026-09-06. OPEN, awaiting the user's
explicit word (his "y" closed the walk; not read as the word for either): (1) send the
`no-tests` vocabulary to md-skills-12; (2) add "component-consumer" to the glossary. The
round-2 walk resumes at its item 8.
