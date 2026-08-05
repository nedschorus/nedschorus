# Defect-hunt (adversarial-literal) pass — /Users/el/Projects/nedschorus/.claude/skills/d-review/SKILL.md

Mode: analysis-only. Findings below, most severe first, then a "clean sections" line.

---

## HIGH

### H1. Step 2 requires one agent to restate-then-hunt; Mode 2 forbids exactly that
- **Location:** `## Steps`, item 2, vs `## Mode 2`, opening paragraph.
- **Quote A (Step 2):** "Write out your exact understanding of each mechanism, rule, and load-bearing claim — subtleties fully elucidated — before hunting defects:"
- **Quote B (Mode 2):** "Two pass types, and **they run in SEPARATE agents — never one agent doing both**: whichever task runs first primes the second (a defect-hunt frame makes the restatement adversarial; a restatement frame makes the hunt post-hoc)."
- **Defect class:** (b) conflicts with another sentence in the same file.
- **Reading collision:** Step 2, read literally, instructs a reviewer to write a restatement/understanding first and hunt defects second, in that order, within what the surrounding six-step procedure presents as one continuous review process. Mode 2 explicitly bans that sequence for doctrine/instruction files — its whole rationale is that whichever pass runs first primes (contaminates) the second, so the two passes must be different agents. Steps 1–6 are the general procedure that precedes mode selection and are never marked "Mode-1-only," so a reader applying Step 2 to a doctrine file (this file's own Mode 2 target class) does precisely what Mode 2 forbids.
- **Mitigation:** Mark Step 2 as applying to Mode 1 only, or add "except under Mode 2, where restatement and defect-hunt are separate agents per Mode 2" to Step 2 itself.

### H2. Step 5 bars author self-review; Mode 2's Synthesize step hands judgment back to the author
- **Location:** `## Steps`, item 5, vs `## Mode 2`, "Synthesize." paragraph.
- **Quote A (Step 5):** "A self-review of one's own text has blind spots — the author has already rationalized the weak parts. Dispatch fresh-context subagents against the same document; they hold no investment in the design."
- **Quote B (Synthesize):** "The **author** compares restatements against intent — a comparator without the intended meaning watches a faithful paraphrase of broken text agree with it and misses the defect."
- **Defect class:** (b) conflicts with another sentence in the same file; (d) wrong when obeyed literally.
- **Reading collision:** Step 5 states the document's author is disqualified from judging their own text because they have already rationalized its weak parts, and prescribes fresh subagents instead. The Synthesize step then assigns the one step that decides whether a restatement's divergence is a real defect — arguably the most judgment-laden step in the whole clarity review — specifically to "the author," on the stated grounds that only the author knows the intended meaning. Obeyed literally, the procedure re-introduces, at the exact chokepoint that determines which findings survive, the same rationalization bias Step 5 was written to eliminate.
- **Mitigation:** Either rename the Step-5 prohibition to scope it to the hunting/restating passes (not the final comparison), or replace "the author" in Synthesize with a role that is not the document's own writer (e.g., a second fresh agent briefed on stated intent by the author, but not empowered to waive findings alone).

### H3. Same paragraph asserts both runtimes are available now and that the companion runtime awaits future admission
- **Location:** `## Mode 2`, "The matrix:" paragraph.
- **Quote A:** "**The matrix:** {restate, defect-hunt} × {good, floor} × {each available runtime} — with both runtimes available, eight cells total."
- **Quote B (same paragraph, two sentences later):** "Add the companion runtime's cells once it is admitted."
- **Defect class:** (a) self-contradictory within one paragraph; (b) conflicts with the preceding sentence.
- **Reading collision:** "with both runtimes available, eight cells total" is a present-tense factual claim that two runtimes are currently usable, yielding 8 cells now. "Add the companion runtime's cells once it is admitted" is a conditional/future claim that a second runtime is NOT yet usable, implying only 4 cells (one runtime) are currently obtainable. A reader cannot obey both: doing 8 cells now satisfies the first sentence and violates the second (the companion isn't "admitted" yet); doing 4 cells now (Claude only) satisfies the second and contradicts the first ("both runtimes available"). The same conditional recurs identically at Step 5 ("Add the companion runtime's read once it is admitted"), and yet the intervening "Running the cells" section describes the Codex-runtime path (`scripts/d-review-codex-cell.py`, a live tier-to-model mapping "boss-picked and live-verified 2026-08-03") as fully operational, not speculative — which reads as evidence the companion runtime already IS admitted, deepening the contradiction rather than resolving it.
- **Mitigation:** State plainly, in one place, whether the companion (Codex) runtime is currently admitted; if it is, delete both "once it is admitted" clauses; if not, change "with both runtimes available, eight cells total" to "currently four cells (Claude only); eight once the companion runtime is admitted."

### H4. No mapping exists from Claude-runtime cells to a "good" vs "floor" model/config
- **Location:** `## Mode 2`, "Running the cells." and "The matrix:" paragraphs.
- **Quote A:** "Claude-runtime cells are fresh subagents."
- **Quote B:** "*Floor* = the mid tier a framework auto-assigns to subagents — the lowest tier that actually reads the file, not the lowest tier that exists..."
- **Defect class:** (e) unexecutable by a zero-context reader — depends on missing information.
- **Reading collision:** The matrix requires four Claude-runtime cells (restate × {good, floor} and defect-hunt × {good, floor}), but the only sentence describing how Claude-runtime cells are produced ("fresh subagents") never says how to make one a "good"-tier cell versus a "floor"-tier cell — no model name, no effort setting, no dispatch instruction, unlike the Codex side, which gets an explicit tier-to-model table (`gpt-5.6-sol` / `gpt-5.6-terra`) in the same section. "The mid tier a framework auto-assigns to subagents" additionally names an unidentified "framework" with no pointer to which one or where its tier assignment is documented. A reader with no context beyond this file cannot construct a Claude "floor" cell versus a Claude "good" cell — they can only guess, and the guess is unfalsifiable from the file's own text. (This defect-hunt cell is itself evidence: nothing in this file told its invoker which Claude configuration constitutes "floor.")
- **Mitigation:** Add a Claude-runtime tier-to-model line parallel to the Codex one (e.g., "Claude good = <model>, Claude floor = <model/effort>"), and name the "framework" that auto-assigns tiers.

---

## MED

### M1. "A stated rule either names an enforcement point... or it is discipline dressed as enforcement" contradicts the immediately following "Side two"
- **Location:** Mode 1 checklist, item 3 (Enforcement vs discipline).
- **Quote A:** "A stated rule either names an enforcement point — a gate, a check, a tool boundary — or it is discipline dressed as enforcement."
- **Quote B:** "Side two: a rule still discovering its own right form legitimately starts as discipline (coding it early freezes a guess and enforces it with machine reliability); there, verify the document names the upgrade trigger... and flag it only when the trigger is missing, or when a single failure of the written rule would be disastrous."
- **Defect class:** (a)/(c) — supports two incompatible readings.
- **Conflict:** Read literally, the opening sentence classifies every non-enforcement-point rule as "discipline dressed as enforcement" (a phrase that connotes illegitimate masquerading, i.e., a defect by default). Side two then describes a category of discipline-rung rule that is explicitly legitimate ("legitimately starts as discipline") and is flagged only under narrow conditions (trigger missing, or failure would be disastrous) — not simply for existing at the discipline rung. A reader who stops at the opening sentence would flag every undiscovered-form rule as a violation; a reader who continues to Side two would not. Severity kept at MED rather than HIGH because the clarifying Side one/Side two text appears within the same numbered item, three sentences later, giving a careful reader a real chance to reconcile before acting.
- **Mitigation:** Reword the opening sentence to something like "...or it sits at the discipline rung, which is not itself a defect (see Side two)."

### M2. "Side two" flags a rule "when a single failure... would be disastrous" — a judgment call, not an observable predicate
- **Location:** Mode 1 checklist, item 3.
- **Quote:** "...and flag it only when the trigger is missing, or when a single failure of the written rule would be disastrous."
- **Defect class:** conditional whose condition is a judgment call.
- **Issue:** "Disastrous" has no defined threshold (data loss? one bad commit? reputational?). Two reviewers applying this item to the same rule can reach opposite flag/no-flag decisions with no way to adjudicate from the text alone.
- **Mitigation:** Give a concrete anchor for "disastrous" (e.g., "irreversible outside git, or affects prod / a shared credential") or explicitly delegate the call to reviewer discretion.

### M3. "true by construction... whose falsity would make the mechanism itself pointless" is a judgment call, not an observable predicate
- **Location:** Mode 1 checklist, item 1.
- **Quote:** "Conversely, do not manufacture a probe for a fact that is true by construction — one whose falsity would make the mechanism itself pointless."
- **Defect class:** conditional whose condition is a judgment call.
- **Issue:** Whether a given claim is "true by construction" (needing no probe) or a genuine unvalidated runtime-boundary claim (needing one) is exactly the kind of first-principles reasoning item 1's opening sentence says is untrustworthy. The item gives no test for telling the two apart beyond the reviewer's own judgment of what would make "the mechanism itself pointless."
- **Mitigation:** Give one worked example of a true-by-construction fact next to one worked example of a genuine unknown, so the boundary has an anchor.

### M4. "Pick the mode by the document's nature" relies on an unspecified, self-referentially ambiguous classification
- **Location:** `## Input and mode choice`.
- **Quote:** "Pick the mode by the document's nature: a proposal not yet built gets the soundness checklist; a doctrine or instruction file gets the clarity review; a spec that is both — doctrine carrying designed mechanisms — gets both, in separate passes."
- **Defect class:** conditional whose condition is a judgment call; (e) partially unexecutable.
- **Issue:** No test is given for classifying an arbitrary document into "proposal not yet built" vs. "doctrine or instruction file" vs. "both." Applied to this very file (a skill file that is simultaneously an operative instruction file AND a document under active, dated revision — "sharpened by boss questioning 2026-08-03," "boss calibration 2026-08-03" — i.e., still being designed), a reader cannot tell from the text whether it is Mode 2 only or "both, in separate passes." (This file's own frontmatter lists "a skill file" as an example target without stating which bucket skill files fall into.)
- **Mitigation:** Add an explicit rule for the skill-file case, since it is named in the frontmatter as an in-scope document type but not resolved by the three-way split.

### M5. "Scale to the change" leaves the boundary between "one-line tweak" and "full rewrite" undefined
- **Location:** Mode 2, "The matrix:" paragraph.
- **Quote:** "Scale to the change: a full new file or full rewrite earns all eight cells; a one-line tweak may need a single good defect-hunt."
- **Defect class:** conditional whose condition is a judgment call.
- **Issue:** Only the two extremes are anchored. A three-paragraph addition, a section rewrite, or a dozen scattered wording edits fall in an unaddressed middle with no stated scaling rule, so two reviewers could reasonably run 1 cell or 8 cells for the identical diff.
- **Mitigation:** Give at least one intermediate anchor (e.g., "a single section rewrite: both tiers, one runtime, restate + defect-hunt = 4 cells").

### M6. "Never take the document's word for its own existence labels... check it (`git`, `gh`, `grep`, `test -f`)" overclaims what the listed tools can verify
- **Location:** `## Steps`, item 4.
- **Quote:** "Any claim about what exists, what a tool does, what a schema holds, what a commit landed — check it (`git`, `gh`, `grep`, `test -f`). Never take the document's word for its own existence labels..."
- **Defect class:** absolute ("Never"/"Any claim") broader than the stated means can support.
- **Counterexample:** A falsifiable claim about something outside the repository — e.g., this very file's "gpt-5.6-sol" / "gpt-5.6-terra" being real, currently-served model identifiers, or a claim about an external API's rate limit — is not checkable with `git`, `gh`, `grep`, or `test -f`. The sentence states an absolute ("any claim... check it") but supplies only repo-local tooling, so the literal instruction is unsatisfiable for a non-repo-local falsifiable claim.
- **Mitigation:** Scope the sentence to "claims about this repository's contents" or add a fallback method for external claims (web fetch, direct query to the relevant system).

### M7. Undefined project artifacts referenced with no name or location a zero-context reader could resolve
- **Location:** Mode 1 checklist, "Running it" intro and items 3, 6, 9; `## When NOT to use`.
- **Quotes:**
  - "...belongs in a script or the mechanical check battery..." (Running it) and "...it belongs in the mechanical check battery from day one..." (item 3) — "the mechanical check battery" is never named as a specific file, script, or directory.
  - "...a defect class that recurs across documents belongs upstream in the authoring skill that keeps producing it." — "the authoring skill" is not identified.
  - "...its own stated principles, or the project's recent rulings." (item 6) — "the project's recent rulings" has no pointer to where rulings are recorded.
  - "...or the project's artifact-lifecycle rule (no stateless piles)..." (item 9) — no pointer to where this rule is documented.
  - "...that is a code-review skill's job, not this one's." / "...that is a deliberate consistency sweep, not a per-change gate." (When NOT to use) — neither the code-review skill nor the consistency-sweep process is named.
- **Defect class:** (e) unexecutable by a zero-context reader — each phrase assumes the reader already knows where these live.
- **Mitigation:** Attach a path or skill name to each (the file already does this correctly elsewhere, e.g. `scripts/d-review-codex-cell.py` and `prompts/` are both linked).

### M8. "first NC run" — unexplained two-letter abbreviation
- **Location:** Mode 2, "Synthesize." paragraph.
- **Quote:** "Dedupe across cells — expect heavy overlap (first NC run, 2026-08-03: five cells over a ~120-line skill returned 109 raw flags that consolidated to ~35 distinct defects)."
- **Defect class:** (e) unexecutable/undefined term; also fails the file's own naming bar (item 11: no cryptic abbreviations).
- **Issue:** "NC" is never expanded anywhere in the file and is too short and generic to grep for meaningfully. It is also unclear whether "a ~120-line skill" refers to this file (currently 58 lines) or a different document used as the illustrative example.
- **Mitigation:** Spell out "NC" on first use, and name which document the ~120-line/109-flag example is about.

### M9. "Review board," "cells," "good," "floor," "mechanical check battery" are dictionary-word terms used as specific technical vocabulary, hard to grep
- **Location:** Mode 1 "Running it" ("The review board is expected to shrink this way"); Mode 2 throughout ("cells," "good," "floor").
- **Defect class:** introduced term not self-documenting / hard to find by grep — matches the file's own naming bar in item 11 ("no cryptic abbreviations... a longer precise name beats a short ambiguous one").
- **Issue:** "floor," "good," and "cells" are common English words; grepping a codebase for any of them returns overwhelming noise, unlike the file's own well-formed examples (`d-review-codex-cell.py`, `restate|defect-hunt`). "The review board" is also not self-evidently defined — it could plausibly be misread as a literal panel of people rather than the numbered lens list it appears to mean.
- **Mitigation:** Prefix the generic terms with a distinguishing token (e.g., "review-tier: good/floor," "review-cell") consistent with the file's own naming rule.

### M10. Unclear whether Step 4 (verify falsifiable claims against ground truth) applies inside a Mode 2 cell
- **Location:** `## Steps` item 4 vs `## Mode 2` (entire section).
- **Issue:** Step 4 is stated as an unconditional step in the general procedure ("Verify every falsifiable claim against ground truth"), but the Mode 2 section — which folds Step 5 into "the clarity-review matrix" explicitly — never mentions verification, and the restate/defect-hunt cell descriptions in Mode 2 give no instruction to check claims like model names or script existence against `git`/`gh`/`test -f`. A reader cannot tell whether a Mode 2 defect-hunt cell is also expected to perform Step 4's ground-truth verification, or whether Mode 2 silently supersedes it the way it explicitly supersedes Step 5.
- **Defect class:** (e) unexecutable — procedure assumes context (which steps survive into Mode 2) that the file does not state.
- **Mitigation:** State explicitly whether Steps 1, 2, and 4 still apply, in addition to the matrix, when running Mode 2.

---

## LOW

### L1. "The path to the document — a pair doc (...), a spec (...), a skill file, CLAUDE.md, a rule page." is a sentence fragment (no verb)
- **Location:** `## Input and mode choice`, opening line.
- **Defect class:** (e)/grammatical — reads as a label, not an instruction; likely recovered as "[Input:] the path to the document," but literally has no predicate.

### L2. "Anything labeled as existing that is only designed or proposed (or the reverse) — the single biggest source of design confusion." is a sentence fragment (no verb)
- **Location:** Mode 1 checklist, item 2.
- **Defect class:** grammatical fragment; meaning is recoverable from the following sentence ("Verify each label against ground truth... and flag every conflation"), so low practical risk.

### L3. "so the two legs cannot drift apart" is an absolute stronger than the described mechanism strictly guarantees
- **Location:** Mode 2, "Running the cells."
- **Quote:** "The templates in `prompts/` are the single prompt source for BOTH runtimes' cells — a Claude cell is prompted with the same template text, substituting the target path — so the two legs cannot drift apart."
- **Defect class:** absolute ("cannot") broader than can hold.
- **Counterexample:** A single-source template only guarantees the two runtimes start from identical text; it does not prevent someone from hand-editing a prompt inline for one runtime without touching the shared file, nor does it prevent the two models from *interpreting* the identical prompt differently. "Cannot drift apart" is true only for the prompt-text dimension, and only as long as no one bypasses the shared file — a possibility the sentence doesn't acknowledge.

### L4. "d-review" itself is a short, partly-abbreviated name that the file's own naming rule (item 11) would flag as a finding candidate
- **Location:** Skill name (frontmatter `name: d-review`) vs Mode 1 checklist item 11.
- **Quote (item 11):** "...no cryptic abbreviations, no bare sequence labels... Expect almost every truly self-documenting name to run two to five words... a one-word name is almost never self-documenting, so the reviewer treats it as a finding candidate by default."
- **Defect class:** self-referential tension, flagged with uncertainty (LOW) since it's borderline whether a hyphenated compound like "d-review" counts as "one word" under item 11's own rule, and the "d" is not expanded anywhere in the file (design-review is implied but never spelled out).

### L5. "the boss" is used without definition
- **Location:** frontmatter description ("...or when the boss says 'd-review this'"); item 3 ("sharpened by boss questioning 2026-08-03"); item 11 ("boss calibration 2026-08-03"); Mode 2 ("boss-picked and live-verified 2026-08-03").
- **Defect class:** (e) unexplained reference — no definition of who/what "the boss" is given anywhere in this file. Likely recoverable (common convention for "the human operator" in this class of agent repo), hence LOW rather than higher.

### L6. "a code-review skill" and "a deliberate consistency sweep" are named without an identifier
- **Location:** `## When NOT to use`.
- **Quote:** "Code correctness, or an implementation reviewed against its design — that is a code-review skill's job, not this one's." / "Routine re-review of long-shipped doctrine — that is a deliberate consistency sweep, not a per-change gate."
- **Defect class:** (e) unexplained reference — neither the code-review skill nor the "deliberate consistency sweep" process is given a name or path a zero-context reader could locate. Kept LOW because both phrases are plausible/guessable generic descriptions rather than load-bearing procedural steps.

### L7. "an issue number always rides with a descriptive handle" — absolute phrased as an observed fact rather than a stated rule
- **Location:** Mode 1 checklist, item 11.
- **Quote:** "...and no bare numeric references in prose (an issue number always rides with a descriptive handle)."
- **Defect class:** absolute ("always") — read literally as a factual claim about all prose everywhere, which is false in general (bare issue numbers are extremely common outside this document's own rule). In context it is clearly meant prescriptively ("must always"), so this is flagged LOW/uncertain rather than higher.

---

## Findings you should treat with the most caution (explicitly uncertain)
- L4 (d-review naming) and M9 (dictionary-word technical terms) both hinge on how strictly "self-documenting" is meant to be read against the file's own vocabulary; a defensible counter-reading is that item 11 is scoped to names the *reviewer* introduces in their findings, not the skill's own pre-existing vocabulary.
- M10 (Step 4 applicability to Mode 2) is an inference from silence, not a stated conflict; the author may intend Step 4 to obviously carry over and consider it not worth restating.

---

clean sections: `## Mode 1 — the design-soundness checklist` items 4 (Gaps and silently-dropped cases), 5 (Over-complexity), 7 (Reliability grounding), 8 (Build-order sanity), 10 (Test-plan completeness); the frontmatter `description:` line taken alone (defects it shares are counted where the same wording recurs in the body).
