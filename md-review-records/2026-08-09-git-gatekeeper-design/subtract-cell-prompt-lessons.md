# Subtraction-reviewer prompt lessons — from the S1–S9 walk corrections

## Walk order

CLOSED OUT 2026-08-12: the redraft this section anticipated exists at
`docs/drafts/sanity-checker-prompt-draft.md`. It was walked from
scratch and settled 2026-08-11 (18 items; dispositions in that file's
git history) and md-reviewed 2026-08-11/12 (record and dispositions in
`md-review-records/2026-08-11-sanity-checker-prompt-draft/`). This
file remains the requirements record; the calibration protocol in its
final section is the live next step before any grid seat.

WALK CLOSED 2026-08-11 at item 2 (user direction): rather than continue
item-by-item, a fresh context redrafts the reviewer instructions and a
NEW walk starts from scratch over that draft. The user's assessment of
the first merged draft: it has good content but keys the whole document
off the wrong word — "simple" does not appear to be the right concept to
organize around; his ruled candidate name is the **sanity-checker** (refined from
"sanity reviewer" the same day).
The redraft reads everything, including the rejected draft (knowing its
keyword framing is wrong), and this file's body remains the requirements
record. Items 3–10 below were never walked; their content feeds the new
draft and the new walk.

Re-planned 2026-08-11 mid-walk: item 2's discussion produced a complete
merged prompt draft (`docs/drafts/simplification-review-prompt-draft.md`
— the user's axis statement + choirmaster's additions + Codex's
naming/vocabulary notes, per the user's combine-all-three direction), so
items 3–8 become confirmations of that draft's sections, and the user
added an md-review of the settled draft before the calibration run.

1. Purpose: what these rulings produce and the bar they meet
   processed 2026-08-11 → accepted; capture is the walk-order block.
2. The core prompt: axis, concept, method
   open 2026-08-11 — revised twice (TRADE line withdrawn as unhelpful —
   the flawed run's LOST field already declared costs honestly, the
   failure was weighing, which the axis statement fixes; then the user
   directed a full three-source merge, complete not condensed, keeping
   simplicity as the central concept with reliability/testability as
   what it must deliver). First merged draft REJECTED 2026-08-11: it
   tried to overwrite the meaning of "simple" (opening by redefining the
   word away from its everyday sense), which the user ruled against; he
   also judged the drafting session's context anchored by the long
   naming discussion. Retry ruled: rewrite from raw sources in a fresh
   context (post-/clear), no meta-discussion of the word — plain
   language, concrete hunts, results must be better / more reliable /
   more testable. The rejected draft stays in git history; the user's
   verbatim statement is preserved in the appendix below.

## Appendix — the user's axis statement, verbatim (2026-08-11)

The core input for any redraft, exactly as he wrote it (typos included;
clean up spelling when quoting into a prompt, change nothing else):

> look for changes to components, steps, states, dependencies or other
> design changes that would simplify this plan, instruction or proposal.
> Simplification can take several forms. It can mean to take this MD
> file easier to read and understand. It can mean to make the plan or
> design easier to use, that is more reliable, more autonomous, with
> fewer or no user interventions required. The best simplifications
> don't appear simple at first glance. They replace LLM prompts or
> English instructions with code so that the steps, states or algorithm
> is both hundreds of times faster, deterministic, followed exactly, and
> can be tested and tuned exactly. Ten, a hundred or even a thousand
> lines of python in reality is simpler than using invoking an agent and
> short prompt. Simplicity can also mean easier to build or maintain,
> but not at the expense of reliability and test-ability. The goal is a
> highly reliable, understandable, easily maintainable system. Trading
> long and complex for shorter and simpler is a win - in both code and
> prompts, but also trading simple and short prompts, for even simpler,
> but far longer code. Your overall goal is to counter the unfortunately
> tendency of AIs to add complexity and almost never simplify or reject
> dealing with theorectical problems or edge cases that have no pratical
> value to solve. Also if you identify unsolvable problems or open ended
> problems, reject complex near solutions and instead look to solve the
> known and easily identified parts, and then note the insolveable parts
> so that the user or an AI can not fall into the trap of tying to solve
> the whole problem, when it can only partially be solved.

Standing rulings on any redraft (user, 2026-08-11): complete and clear,
never condensed at the cost of comprehension; do not redefine or
overwrite the everyday meaning of "simple" — no meta-discussion of the
word; simplicity stays the central concept (renaming the review
"reliability refactoring" was declined); the result must do the right
things — better, more reliable, more testable — "simplification is the
best way to improve code or prompts, but only if it does the right
things."
3. Confirm draft § Discipline: the roadmap rule (expected-trigger
   machinery is not cuttable)
4. Confirm draft § Discipline: forcing functions count as consumers
5. Confirm draft § Discipline: operator cost is not builder cost
6. Confirm the keeps: refute-your-own-candidates, collision flagging,
   already-lean verdicts; decide whether the six validated cut classes
   get enumerated explicitly or stay implicit in the ladder
7. Confirm draft § Report format: the consequence sweep
8. Confirm draft § Report format: quoted grounds
9. md-review the settled draft (user-directed 2026-08-11: zero-context
   agents must understand their instructions)
10. The calibration protocol — rerun against the archived spec, score
    against S1–S9 as ground truth

Source evidence: the one-off subtraction review `claude-subtract-fable.md`
(Fable, off-grid, user-requested 2026-08-10) and the user's nine rulings on
it, recorded under Group S in `dispositions.md`. Status: the subtract cell
is NOT part of the md-review skill or grid — the user ruled it joins only
after prompt improvement and a calibration test, and that addition is an
instruction-class change walked with him. This file is the input to that
future prompt draft.

Scorecard: 6 of 9 cuts accepted (S3, S4, S5, S7, S8, S9), 3 rejected
(S1, S2, S6). Every rejection shared one shape: the reviewer traded
operational robustness for present textual/code smallness. Every
acceptance removed something with no consumer or a duplicated carrier.
Small sample — nine findings, one document — which is itself the argument
for the calibration protocol below.

## What the prompt lacked (each traced to a correction)

1. **The optimization axis was never stated** — the root cause, in the
   user's own words at S6: "asking to simplify is like asking to optimize
   without context — faster, cheaper, more reliable, simpler to write,
   simpler to maintain, simpler to use?" The prompt must state the
   project's axis explicitly: simple-to-operate beats simple-to-build;
   mechanical guarantees beat trained habit; build cost is acceptable when
   it buys maintenance-free operation. Require every proposed cut to name
   which axis it optimizes and which it sacrifices — the trade visible on
   its face.
2. **No roadmap context** (S1's rejection). The reviewer quoted "there are
   no slow checks yet" as grounds to cut the async machinery, never asking
   whether slow checks were *expected*. They were — tests and reviews are
   planned. Rule for the prompt: provide the forward plan, and a mechanism
   whose deferral trigger is expected to fire is not a valid cut; "build
   the machinery while the system is still simple" is the standing
   preference.
3. **"No consumer" misapplied to forcing functions** (S6's rejection). The
   reviewer argued nothing reads the `Gatekeeper-issue` trailer — true and
   beside the point: the required field's value is the *forced explicit
   answer* (issue number or deliberate `none`), a mechanical guarantee
   that would otherwise degrade to LLM habit. Rule for the prompt: "who is
   forced to decide something because this exists?" counts as a consumer;
   never propose replacing a deterministic mechanism with trained agent
   behavior.
4. **Operator cost vs builder cost conflated** (S2's rejection). Cutting
   the self-updating deployed copy would have reintroduced a remembered
   human step (manual `sudo cp`) — a regression on the stated axis dressed
   as a simplification. Rule: a cut that adds a recurring human obligation
   is not a subtraction; it moves cost from build-time to forever.

## What worked — keep these instructions verbatim in spirit

5. **The validated cut classes** (all six accepted cuts fit one):
   detectors/outputs with no consumer (S3, S5); duplicated normative homes
   (S4); carrier-vs-invariant collapse — derive the fact in one place,
   never drop the fact (S7); guards that guard nothing (S8); dead code and
   distinction-carrying names with no machine consumer (S9). Enumerate
   these as the classes to hunt.
6. **Refute-your-own-candidates before reporting.** The refuted list
   (digest dedup, --base outright, --agent, the advisory, slice-3
   concurrency) was as valuable as the findings — it certified the lean
   core and saved walk time.
7. **Flag collisions with recorded rulings instead of dodging them.** The
   reviewer's "two user rulings get contradicted — surfacing that is the
   point of this review" framing was correct and the user engaged with it.

## New requirements (not discussed in the walk, learned from its aftermath)

8. **Consequence sweep per cut**: enumerate every spec sentence that
   becomes false or stale when the cut lands. S3's application left "the
   raw-push residual is detected at its source" standing — caught only by
   the later Codex leg (its FIX-3). The reviewer proposing a cut holds the
   full blast-radius in view once and should deliver it with the finding.
9. **Grounds must be quoted, not paraphrased**: each WHY that leans on the
   document's own text quotes it, so triage can verify without re-deriving
   (the one-off mostly did this; make it mandatory).

## Calibration protocol before any grid seat

Run the improved prompt against the archived pre-walk spec revision
(commit 0890848's `git-gatekeeper-design.md`) and score against the user's
S1–S9 rulings as ground truth: the six accepted cuts should surface; the
three rejected cuts should either not surface or surface with their
axis-cost stated honestly (a finding that says "this trades operational
reliability for less code — likely against the project's axis" is a pass,
not a miss). Repeat on a second document before proposing the grid
addition, which is walked with the user like any skill change.
