# Subtraction-reviewer prompt lessons — from the S1–S9 walk corrections

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
