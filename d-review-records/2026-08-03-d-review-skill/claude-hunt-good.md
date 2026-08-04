# Adversarial-literal defect hunt — `.claude/skills/d-review/SKILL.md`

Target read in full (57 lines, including YAML frontmatter). Mode: analysis only; no edits made.
Two ground-truth checks were run (allowed inspection, no modification):
`scripts/d-review-codex-cell.py` exists; `.claude/skills/d-review/prompts/` exists and contains `restate.md` and `defect-hunt.md`; the script defines `TIER_TO_CODEX_MODEL` at its line 29 with `good -> gpt-5.6-sol`, `floor -> gpt-5.6-terra`. Those two link citations are therefore NOT dangling; findings below that touch them concern wording, not existence.

Findings are numbered, most severe first.

---

## HIGH

### 1. The by-construction probe exemption is defined by a test that selects the highest-stakes claims for exemption
- **Quote (Mode 1, lens 1):** "Conversely, do not manufacture a probe for a fact that is true by construction — one whose falsity would make the mechanism itself pointless."
- **Defect class:** (a) self-contradictory; (d) wrong when obeyed literally.
- **The problem:** the sentence supplies a test for "true by construction" — *falsity would make the mechanism pointless* — and that test is satisfied by exactly the claims the same lens's first sentence demands a probe for. Counterexample-case: a design says "the hook fires before the tool call, so the guard can block it." If that ordering claim is false the guard mechanism is pointless, so the literal rule says do NOT probe it — yet it is a load-bearing runtime-boundary claim resting on first-principles reasoning, which the lens's first sentence says "needs an empirical probe, not assumption." A reader obeying the words skips the single most important probe in the review. (Also in tension with lens 7: "A believed load-bearing mechanism is a named risk until measured.")
- **Severity:** HIGH.
- **Mitigation:** replace the falsity test with one that actually identifies by-construction facts (the claim is true by definition of the artifact, e.g. "the file the script writes is the file the script reads"), and state explicitly that stake level is not the discriminator.

### 2. Step 2 orders the reviewer to restate before hunting; Mode 2 forbids one agent doing both
- **Quote (Steps, 2):** "**Write out your exact understanding of each mechanism, rule, and load-bearing claim — subtleties fully elucidated — before hunting defects:** edge behavior, boundary conditions, what is not covered, what it does to adjacent state."
- **Conflicting sentence (Mode 2 preamble):** "Two pass types, and **they run in SEPARATE agents — never one agent doing both**: whichever task runs first primes the second (a defect-hunt frame makes the restatement adversarial; a restatement frame makes the hunt post-hoc)."
- **Defect class:** (b) conflict with another sentence in the same file.
- **The problem:** Steps 1–6 are presented as the procedure for both modes ("Run the chosen mode's checklist" is step 3, inside the same list). Step 2 is a restatement done by the same reader who then hunts defects — the precise sequence Mode 2 says is never to happen, for the stated reason that it poisons both passes. A reader reviewing a doctrine file cannot obey both. Step 5's "For a doctrine file, the clarity-review matrix below IS this step" scopes *step 5* to the matrix but says nothing about step 2.
- **Severity:** HIGH.
- **Mitigation:** state whether step 2 is Mode-1-only, or that in Mode 2 step 2 is discharged by the delegated restate cells rather than by the invoker.

### 3. "Review never creates" is contradicted by three later mandatory outputs
- **Quote (intro):** "**Review never creates:** a finding names what is wrong and points the direction of a fix in one line; the fix itself belongs to the author."
- **Conflicting sentences:** Steps 3 — "Every finding names the specific location, the weakness, a severity (HIGH / MED / LOW), and a concrete mitigation — never a vague concern." Lens 5 — "Name the cut and what replaces it." Intro — "A reviewer who wants to propose an alternative design has left review — that is a create-design task, owned separately."
- **Defect class:** (b) internal conflict; (c) two incompatible readings.
- **The problem:** "what replaces it" is an alternative design for that component, and "a concrete mitigation" is stronger than "points the direction of a fix." Reading A: produce concrete replacement designs per lens 5. Reading B: refuse, because proposing an alternative "has left review." Counterexample-case: an over-complex retry ladder — under lens 5 the reviewer must name the simpler primitive that replaces it; under the intro that same act ends the review.
- **Severity:** HIGH.
- **Mitigation:** define the boundary in observable terms (one-line direction naming a known-existing primitive = allowed; new mechanism specification = out of scope) in the intro, and make lens 5 and step 3 use that same wording.

### 4. The defect-hunt cell is forbidden to resolve findings, but every finding must carry a concrete mitigation
- **Quote (Mode 2, pass 2):** "A separate agent, told to find defects and forbidden to resolve them: flag every sentence that is self-contradictory, conflicts with another sentence, supports two incompatible readings, is wrong when obeyed literally, or is unexecutable by a zero-context reader; plus absolutes broader than can hold (with the ordinary counterexample) and conditionals whose condition is a judgment call rather than an observable predicate."
- **Conflicting sentence (Steps, 3):** "Every finding names the specific location, the weakness, a severity (HIGH / MED / LOW), and a concrete mitigation — never a vague concern."
- **Defect class:** (b) internal conflict; (c) two readings.
- **The problem:** pass 2's own enumeration of what a flag must contain — "Each flag quotes the sentence, gives both readings or the conflict, and a case where obeying the words does the wrong thing" — omits both severity and mitigation, the two things step 3 says *every* finding has. A cell operator cannot tell whether to emit severities and mitigations (step 3) or to emit neither because resolving is forbidden (pass 2). Counterexample-case: the cell finds a contradiction, writes the one-line fix, and has now "resolved" it in violation of its own instruction.
- **Severity:** HIGH.
- **Mitigation:** say explicitly that cell output is severity-tagged but mitigation-free, and that mitigations are added only at the synthesis step.

### 5. Lens 3's opening dichotomy makes every honestly-stated discipline rule an automatic finding
- **Quote (lens 3):** "A stated rule either names an enforcement point — a gate, a check, a tool boundary — or it is discipline dressed as enforcement."
- **Conflicting sentence (same lens, side two):** "a rule still discovering its own right form legitimately starts as discipline (coding it early freezes a guess and enforces it with machine reliability)".
- **Defect class:** (a) self-contradictory within the lens; (d) wrong when obeyed literally.
- **The problem:** the binary has no cell for *honest, correctly-labeled discipline* — a rule that claims no enforcement and pretends to none. Counterexample-case: "prefer full words in names, ease of typing is not a constraint" names no gate, so by the literal first sentence it *is* "discipline dressed as enforcement" and gets flagged — while side two says that same rule is legitimate. Two competent reviewers produce opposite verdicts on the same rule from the same lens.
- **Severity:** HIGH.
- **Mitigation:** add the missing third category to the opening sentence (enforcement point named / discipline honestly labeled / discipline dressed as enforcement) so only the third is a finding by default.

### 6. The restatement pass's finding can only be computed by the author, but the skill is defined as not-the-author
- **Quote (Mode 2, pass 1):** "The finding is not the paraphrase — it is the **divergence** between the paraphrase and the intended meaning."
- **Supporting quote (Synthesize):** "The **author** compares restatements against intent — a comparator without the intended meaning watches a faithful paraphrase of broken text agree with it and misses the defect."
- **Conflicting sentences (frontmatter and intro):** "The document must already exist; this skill judges it, never co-writes it." / "the fix itself belongs to the author."
- **Defect class:** (e) unexecutable — depends on knowledge the file says the executor does not have; (b) conflict.
- **The problem:** the file positions the d-review runner as a third party distinct from the author, then makes a required pass produce findings only the author can extract. A reviewer running d-review on someone else's document literally cannot complete pass 1. Counterexample-case: an agent d-reviews a CLAUDE.md written months earlier by a different agent — it holds paraphrases and no intent, so per the Synthesize sentence it will "miss the defect," and the file gives no fallback.
- **Severity:** HIGH.
- **Mitigation:** state who runs which step (author-in-the-loop for restatement comparison), or define a substitute comparator for the no-author case and say what it can and cannot catch.

### 7. Half the matrix has no model assignment: "good" and "floor" are mapped for Codex only
- **Quote (Running the cells):** "The tier-to-model mapping sits at the top of the script, one place to update as models change (currently `gpt-5.6-sol` good / `gpt-5.6-terra` floor, boss-picked and live-verified 2026-08-03)."
- **Conflicting/incomplete sentence (Running the cells):** "Claude-runtime cells are fresh subagents."
- **Defect class:** (e) unexecutable for a zero-context reader.
- **The problem:** the matrix is "{restate, defect-hunt} × {good, floor} × {each available runtime}", so the Claude leg needs a good model and a floor model. The only stated mapping lives in a Codex-specific script (verified: `TIER_TO_CODEX_MODEL`, `scripts/d-review-codex-cell.py:29`) and covers Codex model ids only. A reader dispatching Claude cells has no way to know which model is "good" and which is "floor" — and the file's own definition of floor ("the mid tier a framework auto-assigns to subagents") describes a default, not a name a reader can pass. Counterexample-case: the invoker dispatches four Claude cells all at the same model, and the tier axis silently collapses.
- **Severity:** HIGH.
- **Mitigation:** state the Claude-runtime tier-to-model mapping in the same place, or point at the single artifact that holds both runtimes' mappings.

### 8. Lens 6 requires knowledge the lens's own dispatch model withholds
- **Quote (lens 6):** "The document contradicting itself, its own stated principles, or the project's recent rulings."
- **Conflicting sentence (Mode 1, Running it):** "the lenses fan out — one focused agent per lens or lens-group, each handed the document and its single question; the invoker synthesizes."
- **Defect class:** (e) unexecutable — depends on context the file does not supply; (b) conflict.
- **The problem:** an agent "handed the document and its single question" has no access to "the project's recent rulings" — an undefined, unlocated, undated body of decisions. The file never says where rulings live, how recent counts, or that this lens's agent gets extra inputs. Counterexample-case: the lens-6 agent reports "no conflict with recent rulings" having never seen one, and the invoker reads that as a cleared check.
- **Severity:** HIGH.
- **Mitigation:** name the location and recency window for "recent rulings," and state that the lens-6 agent is handed them alongside the document.

---

## MED

### 9. "the mechanical check battery" is a named destination the file never locates
- **Quote (lens 3):** "it belongs in the mechanical check battery from day one, and the review asks why it is not there."
- **Also (Mode 1, Running it):** "belongs in a script or the mechanical check battery".
- **Defect class:** (e) undefined term used as if known; naming.
- **The problem:** a definite article ("the") asserts a specific existing artifact. A zero-context reader cannot check whether a rule "is not there," which is the literal action lens 3 requires. It is also unclear whether "a script" and "the mechanical check battery" are two destinations or one.
- **Severity:** MED.
- **Mitigation:** give the battery's path on first use and say whether it is distinct from "a script."

### 10. "all eleven" is a hard-coded count in a section that says the count will change
- **Quote (Mode 1, Running it):** "No single reviewer walks all eleven inside one context."
- **Conflicting sentence (same paragraph):** "The review board is expected to shrink this way; only genuine judgment should stay manual."
- **Defect class:** (b) conflict; (d) becomes literally wrong on the file's own predicted trajectory.
- **The problem:** the number is correct today (lenses 1–11) but the same paragraph plans for lenses to migrate out. After one migration the sentence is false, and a reader who counts ten lenses cannot tell whether one was removed or one is missing from the file.
- **Severity:** MED.
- **Mitigation:** write "all of them" / "the full lens set" instead of a literal count.

### 11. "the matrix" names two different things in two sections
- **Quote (Mode 1, Running it):** "**Re-review after revision covers the delta:** the changed sections plus verification of each prior finding's fix — never a full re-run of the matrix."
- **Conflicting definition (Mode 2):** "**The matrix:** {restate, defect-hunt} × {good, floor} × {each available runtime} — with both runtimes available, eight cells total."
- **Defect class:** (c) two readings; naming collision.
- **The problem:** in Mode 1 "the matrix" can only mean the eleven-lens set (the matrix term is never defined there); in Mode 2 it is formally defined as the cell grid. One term, two referents, and the Mode 1 use precedes the definition.
- **Severity:** MED.
- **Mitigation:** call the Mode 1 object "the lens set" and reserve "matrix" for the Mode 2 cell grid.

### 12. "never a full re-run" conflicts with "a full rewrite earns all eight cells"
- **Quote (Mode 1, Running it):** "never a full re-run of the matrix."
- **Conflicting sentence (Mode 2, The matrix):** "Scale to the change: a full new file or full rewrite earns all eight cells; a one-line tweak may need a single good defect-hunt."
- **Defect class:** (b) conflict.
- **The problem:** a full rewrite submitted after a first review is simultaneously a "re-review after revision" (never a full re-run) and a "full rewrite" (all eight cells). Counterexample-case: the author rewrites the document wholesale in response to findings; the reviewer, obeying the first sentence, reviews only "the delta" — which is the entire document — while believing a full re-run is forbidden.
- **Severity:** MED.
- **Mitigation:** scope the "never a full re-run" rule to targeted revisions and say a rewrite resets to a full pass.

### 13. "a check that repeats identically across reviews" is asserted to be mechanizable; it need not be
- **Quote (Mode 1, Running it):** "a check that repeats identically across reviews is the certain-and-cheaply-checkable kind and belongs in a script or the mechanical check battery".
- **Defect class:** (d) wrong when obeyed literally; overbroad claim.
- **The problem:** repetition and mechanizability are independent. Counterexample from this same file: lens 6 ("Internal consistency") and lens 5 ("what can be cut") repeat identically in every single review and are pure judgment — the sentence's literal instruction is to move them into a script.
- **Severity:** MED.
- **Mitigation:** add the missing conjunct — repeats identically **and** has a mechanically decidable predicate.

### 14. The companion runtime is described as both not-yet-admitted and already operational
- **Quote (Steps, 5):** "Add the companion runtime's read once it is admitted."
- **Quote (Mode 2, The matrix):** "Add the companion runtime's cells once it is admitted."
- **Conflicting sentence (Running the cells):** "Codex-runtime cells run through [`scripts/d-review-codex-cell.py`](../../../scripts/d-review-codex-cell.py) — one invocation per cell (`--cell restate|defect-hunt --tier good|floor --target <path>`), headless `codex exec`, read-only sandbox, the cell's final message on stdout."
- **Defect class:** (b) conflict; (e) undefined term ("admitted," "companion runtime").
- **The problem:** the operational paragraph describes a working, live-verified second runtime (script confirmed present on disk), while two other sentences defer it to a future admission event that is never defined — no admitter, no criterion, no place to check. A reader cannot tell whether to run four cells or eight today.
- **Severity:** MED.
- **Mitigation:** state the current admission status once, and either define "admitted" (who decides, recorded where) or drop the conditional.

### 15. "each available runtime" and "once it is admitted" are two different inclusion predicates
- **Quote (Mode 2, The matrix):** "{restate, defect-hunt} × {good, floor} × {each available runtime} — with both runtimes available, eight cells total."
- **Defect class:** (c) two readings.
- **The problem:** "available" (the runtime can be invoked) and "admitted" (someone approved it) are not the same test, and the file uses both for the same axis. Counterexample-case: Codex is invocable but nobody has "admitted" it — reading A gives eight cells, reading B gives four.
- **Severity:** MED.
- **Mitigation:** pick one predicate and use it in all three places.

### 16. The cited empirical run does not fit the matrix it is cited under
- **Quote (Synthesize):** "Dedupe across cells — expect heavy overlap (first NC run, 2026-08-03: five cells over a ~120-line skill returned 109 raw flags that consolidated to ~35 distinct defects)."
- **Defect class:** (e) unexplained reference; (b) numeric tension with the matrix.
- **The problem:** two separate gaps. First, "NC" is an unexpanded abbreviation appearing exactly once — a zero-context reader cannot decode it and cannot grep for it usefully. Second, the matrix admits 4 cells (one runtime) or 8 (both); five is neither, and the file never says which five, so the overlap statistic cannot be interpreted or reproduced.
- **Severity:** MED.
- **Mitigation:** expand the abbreviation on first use and name the five cells (or state that the run predates the current matrix).

### 17. "one place to update" is false as written — the mapping is stated in two places
- **Quote (Running the cells):** "The tier-to-model mapping sits at the top of the script, one place to update as models change (currently `gpt-5.6-sol` good / `gpt-5.6-terra` floor, boss-picked and live-verified 2026-08-03)."
- **Defect class:** (a) self-contradictory within the sentence.
- **The problem:** the parenthetical duplicates into prose the exact mapping the clause just called single-sourced. Verified: `TIER_TO_CODEX_MODEL` at `scripts/d-review-codex-cell.py:29` holds the same two pairs. When models change, a reader who updates only the script leaves this sentence stating stale model ids with a "live-verified" stamp attached.
- **Severity:** MED.
- **Mitigation:** drop the model ids from the prose, or mark them explicitly as a non-authoritative snapshot with the script as SSOT.

### 18. "Floor" carries two definitions that need not select the same model
- **Quote (Mode 2, The matrix):** "*Floor* = the mid tier a framework auto-assigns to subagents — the lowest tier that actually reads the file, not the lowest tier that exists (a below-floor model flags its own capability gaps, not the document's defects)."
- **Defect class:** (c) two incompatible readings; (e) undefined referent ("a framework").
- **The problem:** definition A is operational and external ("what a framework auto-assigns"); definition B is a capability threshold ("the lowest tier that actually reads the file"). Nothing guarantees they coincide, and if a framework's default drops below the reading threshold the two definitions select different models. "A framework" is also indefinite — which one? The reader cannot look up the default.
- **Severity:** MED.
- **Mitigation:** pick the capability threshold as the definition and cite the auto-assigned default only as the current instance, naming the framework.

### 19. The tier names "good" and "floor" violate the file's own naming lens
- **Quote (lens 11):** "Every name the document introduces — files, scripts, functions, terms, headings, test labels — must be self-documenting and greppable: full words a search matches verbatim, one shared token across a family of related names, no cryptic abbreviations, no bare sequence labels, and no bare numeric references in prose".
- **Defect class:** (b) the file conflicts with its own rule; naming.
- **The problem:** "good" is one of the least greppable words in English (it matches prose everywhere), "floor" reads as a building or a numeric operation, and the two share no family token — while the rule demands "one shared token across a family of related names." The same objection applies to the skill's own name, `d-review`: "d" is a cryptic single-letter abbreviation the file never expands beyond the heading "Design review (d-review)". A reviewer applying lens 11 to this file must flag its own vocabulary.
- **Severity:** MED.
- **Mitigation:** either rename the tiers to a shared-token family (e.g. `tier-top` / `tier-floor`) or add an explicit note that these names are grandfathered and why.

### 20. "a one-word name is almost never self-documenting" is broader than it can hold
- **Quote (lens 11):** "Expect almost every truly self-documenting name to run two to five words (boss calibration 2026-08-03): a one-word name is almost never self-documenting, so the reviewer treats it as a finding candidate by default".
- **Defect class:** overbroad absolute (hedged, but operationalized as an unhedged default).
- **The problem:** ordinary counterexamples: `timestamp`, `latitude`, `checksum`, `retries` are one word and fully self-documenting. The hedge "almost never" is immediately converted into a hard behavior ("a finding candidate by default"), so the hedge does no work at the point of action, and the reviewer generates noise flags on correct names.
- **Severity:** MED.
- **Mitigation:** state the actual discriminator (a one-word name is a finding when the word is generic or overloaded in context), not the word count.

### 21. "so the two legs cannot drift apart" claims enforcement the file provides no mechanism for
- **Quote (Running the cells):** "The templates in [`prompts/`](prompts/) are the single prompt source for BOTH runtimes' cells — a Claude cell is prompted with the same template text, substituting the target path — so the two legs cannot drift apart."
- **Defect class:** overbroad "cannot"; (b) the file's own lens 3 classifies this pattern as a defect.
- **The problem:** the Codex leg reads the template mechanically (via the script); the Claude leg is prompted by whoever dispatches the subagent, with no gate that checks the text matches. Ordinary counterexample: the dispatcher paraphrases the template from memory, or edits it inline for one run — the legs drift immediately. By lens 3's own test this is "discipline dressed as enforcement," stated with an absolute ("cannot").
- **Severity:** MED.
- **Mitigation:** downgrade to "are intended to keep the two legs aligned," or name the mechanism that actually enforces it on the Claude leg.

### 22. Pass 1 says an innocent paraphrase exposes ambiguity; Synthesize says it can hide it
- **Quote (pass 1):** "An innocent paraphrase exposes ambiguity by misreading it."
- **Conflicting sentence (Synthesize):** "a comparator without the intended meaning watches a faithful paraphrase of broken text agree with it and misses the defect."
- **Defect class:** (b) conflict; overbroad claim.
- **The problem:** the second sentence names the exact case the first excludes — a paraphrase that is faithful rather than misreading, over text that is broken. Ordinary counterexample: the paraphraser copies the ambiguous phrase through verbatim, producing a paraphrase that neither misreads nor exposes anything.
- **Severity:** MED.
- **Mitigation:** soften pass 1 to "an innocent paraphrase often exposes ambiguity by misreading it, but a verbatim-carried ambiguity survives paraphrase — hence the comparator requirement."

### 23. Uncertain findings are forced to LOW regardless of consequence
- **Quote (Steps, 3):** "Coverage over self-censorship: report a finding you are unsure about, tagged LOW with the uncertainty stated, rather than suppressing it; filtering is the reader's job, not the reporter's."
- **Defect class:** (d) wrong when obeyed literally.
- **The problem:** severity is being used for two orthogonal things — consequence and confidence. Counterexample-case: the reviewer suspects but cannot confirm that a documented command deletes an unbackedup directory. Literal obedience files it LOW, next to typo-grade items, and the reader's filter drops it.
- **Severity:** MED.
- **Mitigation:** keep severity for consequence and add a separate confidence marker (e.g. `HIGH (unconfirmed)`).

### 24. The severity scale is required everywhere and defined nowhere
- **Quote (Steps, 3):** "Every finding names the specific location, the weakness, a severity (HIGH / MED / LOW), and a concrete mitigation — never a vague concern."
- **Defect class:** (e) unexecutable by a zero-context reader.
- **The problem:** HIGH, MED, and LOW are used in step 3, step 6, and the Synthesize step, and the file never states what distinguishes them. Two competent reviewers will draw the HIGH/MED line differently, which makes the "most consequential first" ordering and any cross-cell dedupe incomparable.
- **Severity:** MED.
- **Mitigation:** define the three levels in one line each where the scale is first introduced.

### 25. "Include a fair 'what's solid' section" is mandatory even when nothing is solid
- **Quote (Steps, 6):** "Include a fair \"what's solid\" section — a review that only attacks gets discounted."
- **Defect class:** (d) wrong when obeyed literally.
- **The problem:** the requirement is unconditional and its stated rationale is reception ("gets discounted"), not accuracy. Counterexample-case: a document whose central mechanism is unsound end to end — the reviewer must still produce a fairness section, and the only way to comply is to inflate something. The instruction creates pressure to manufacture praise, and the verdict option "not-ready-because-X" shows the file anticipates wholly-unsound documents.
- **Severity:** MED.
- **Mitigation:** make it conditional — "name what is solid where anything is; if nothing is, say so explicitly."

### 26. "Verify every falsifiable claim" is unbounded and includes claims the reviewer cannot check
- **Quote (Steps, 4):** "**Verify every falsifiable claim against ground truth.** Any claim about what exists, what a tool does, what a schema holds, what a commit landed — check it (`git`, `gh`, `grep`, `test -f`)."
- **Defect class:** overbroad absolute; (d) impossible when obeyed literally.
- **The problem:** the first sentence says *every falsifiable claim*; the second narrows to existence-class claims checkable with four local tools. Ordinary counterexamples: "this reduces review time by half," "the vendor's API rate-limits at 60/min," "the model behaves better at high effort" — all falsifiable, none checkable with `git`/`gh`/`grep`/`test -f`. A literal reader either stalls or silently substitutes the narrower second sentence.
- **Severity:** MED.
- **Mitigation:** restrict the headline to "every claim about what exists or what a tool does," and say what to do with falsifiable-but-uncheckable claims (flag as unverified).

### 27. Step 5's rationale assumes the reviewer wrote the document, which the intro forbids
- **Quote (Steps, 5):** "**Get independent passes.** A self-review of one's own text has blind spots — the author has already rationalized the weak parts."
- **Conflicting sentence (frontmatter):** "The document must already exist; this skill judges it, never co-writes it."
- **Defect class:** (b) conflict; (c) two readings.
- **The problem:** if the reviewer is never the author, the stated justification for independent passes does not apply to this skill's runs at all — leaving a reader unable to tell whether step 5 is mandatory for third-party reviews or only when the author self-reviews. Counterexample-case: an agent reviewing a peer's spec concludes "I am not the author, so there is nothing to de-bias" and skips the fan-out.
- **Severity:** MED.
- **Mitigation:** give the independence rationale that survives third-party review (a single reader's blind spots and single-context anchoring), not the self-review one.

### 28. Lens 4 demands exhaustive coverage of a cross-product no document can enumerate
- **Quote (lens 4):** "For each mechanism, walk the state space systematically: every actor state (busy, idle, mid-turn, dead), every dependency failure (the file it reads, the tool it runs, the channel it writes), every concurrency case (two sessions, re-entry, repeated firing) — and require the document to name or explicitly discard each cell."
- **Defect class:** (d) impossible when obeyed literally; (e) undefined term ("actor").
- **The problem:** the requirement is a full cross-product per mechanism (4 actor states × N dependencies × 3 concurrency cases), and the document must address *each cell* explicitly. For a design with five mechanisms and three dependencies each, that is hundreds of mandated statements — every absent one a finding, by the next sentence ("An omission is a finding even when the happy path is flawless"). Separately, "actor" is never defined, and the listed states presuppose agent-like actors; a design for a file format or a naming convention has no actors, leaving the lens inapplicable with no stated escape.
- **Severity:** MED.
- **Mitigation:** require coverage of cells that are *reachable and consequential*, and say the enumeration is a prompt for the reviewer rather than a checklist the document must transcribe.

### 29. Lens 10 requires an adversarial test layer from documents that have no test plan
- **Quote (lens 10):** "Require a second, adversarial layer — load, scale, \"what did we not anticipate\" — that does not assume the design is right."
- **Defect class:** (d) wrong when obeyed literally.
- **The problem:** Mode 1 targets include specs and rule pages, and the "Input and mode choice" section says a spec that is both gets both modes. Counterexample-case: a doctrine document establishing a naming convention has no executable surface — demanding a load-and-scale adversarial test layer produces a mandatory finding against a document that correctly has none.
- **Severity:** MED.
- **Mitigation:** condition the lens on the design having an executable surface, and say what substitutes for it when it does not.

### 30. Lens 9 leans on an external rule the file neither locates nor explains
- **Quote (lens 9):** "Data the design accumulates needs a bound — retention, archival, or the project's artifact-lifecycle rule (no stateless piles) — and a stated expectation of volume."
- **Defect class:** (e) undefined reference; naming.
- **The problem:** "the project's artifact-lifecycle rule" is cited with a definite article and no path, and its parenthetical gloss "no stateless piles" is jargon that does not decode on its own — a "stateless pile" is not a term the file or ordinary usage defines. A reviewer cannot check a document against a rule it cannot find, and cannot grep for it either.
- **Severity:** MED.
- **Mitigation:** cite the rule's path, and replace or expand the "stateless piles" gloss with a plain statement of what it prohibits.

### 31. "complete enough to judge" is a judgment-call gate on whether the skill may run at all
- **Quote (intro):** "The document must exist and be complete enough to judge — reviewing is judging the written artifact, never co-writing it."
- **Defect class:** conditional whose condition is a judgment call, not an observable predicate.
- **The problem:** this is the entry gate for the whole skill, and two reviewers will place it differently on the same draft — one begins the review, the other refuses it as too incomplete. There is no stated test (has a stated mechanism per section? no TODO markers? author declares it ready?).
- **Severity:** MED.
- **Mitigation:** give one observable test for readiness, or name who declares it.

### 32. The mode-choice trichotomy has no branch for a design of something already built
- **Quote (Input and mode choice):** "Pick the mode by the document's nature: a proposal not yet built gets the soundness checklist; a doctrine or instruction file gets the clarity review; a spec that is both — doctrine carrying designed mechanisms — gets both, in separate passes."
- **Defect class:** (e) incomplete procedure; conditional resting on a judgment call ("the document's nature").
- **The problem:** branch one is gated on "not yet built." A design document for a system that is already partly built is neither a proposal-not-yet-built nor a doctrine file, so the literal trichotomy assigns it no mode — while the "When NOT to use" section excludes only "an implementation reviewed against its design," which is a different activity. Counterexample-case: a spec revised mid-build arrives and the reviewer has no branch to take.
- **Severity:** MED.
- **Mitigation:** re-gate branch one on document *type* (proposal/design) rather than build status, and say what happens to partially-built designs.

### 33. "unexecutable by a zero-context reader" flags essentially every project-specific sentence
- **Quote (pass 2):** "flag every sentence that ... is unexecutable by a zero-context reader".
- **Defect class:** overbroad absolute; (e) "zero-context" itself undefined.
- **The problem:** the file never says zero context *about what*. Under the widest reading, every sentence naming a repo path, a tool, or a project convention is unexecutable to a reader with zero project context — which is most sentences in any doctrine file, including this one's own `docs/issues/<n>-<slug>.md`. Counterexample-case: a cell returns 60 flags, one per project-specific noun, and the real defects are buried.
- **Severity:** MED.
- **Mitigation:** define the reader (no project history, but access to the repo and the linked files) so the predicate becomes decidable.

### 34. Pass 2's required flag contents cannot be produced for two of the defect classes it mandates
- **Quote (pass 2):** "Each flag quotes the sentence, gives both readings or the conflict, and a case where obeying the words does the wrong thing."
- **Defect class:** (d) impossible for some in-scope findings; (c) "both readings" presumes exactly two.
- **The problem:** a sentence that is *unexecutable* cannot be obeyed at all, so no "case where obeying the words does the wrong thing" exists; a three-way ambiguity has more than "both" readings; and a judgment-call conditional has no misobedience case either — it has divergent-outcome cases. A literal cell either suppresses those findings or fabricates a misobedience story.
- **Severity:** MED.
- **Mitigation:** make the third element per-class ("the misobedience case, the divergence, or the missing knowledge, whichever applies") and say "the readings" rather than "both."

### 35. The second "When NOT to use" bullet does not actually say not to use it
- **Quote (When NOT to use):** "Routine re-review of long-shipped doctrine — that is a deliberate consistency sweep, not a per-change gate."
- **Defect class:** (c) two readings; judgment-call condition.
- **The problem:** reading A: do not run d-review on long-shipped doctrine. Reading B: you may run it, but call it a consistency sweep rather than a gate — the sentence renames the activity rather than excluding it, and the file elsewhere invites re-review ("Re-review after revision covers the delta"). "Long-shipped" is also unmeasured — a week? a quarter?
- **Severity:** MED.
- **Mitigation:** state the exclusion as an action ("do not run this skill for X; run it only when Y") and replace "long-shipped" with an observable trigger.

### 36. "the boss" is an undefined authority appearing in an invocation trigger
- **Quote (frontmatter description):** "Use when a document is about to be built from or landed, or when the boss says \"d-review this\"."
- **Also:** "(sharpened by boss questioning 2026-08-03)", "(boss calibration 2026-08-03)", "boss-picked and live-verified 2026-08-03".
- **Defect class:** (e) undefined term used in an executable trigger.
- **The problem:** one of the two stated invocation conditions turns on recognizing an unnamed role. A zero-context reader cannot tell whether "the boss" is a specific human, any requester, or a role defined elsewhere — and the same term is used to carry authority for three calibration decisions.
- **Severity:** MED.
- **Mitigation:** define the role once on first use (or link the role map), since it gates invocation.

### 37. "a pair doc" is introduced as an input type without definition
- **Quote (Input and mode choice):** "The path to the document — a pair doc (`docs/issues/<n>-<slug>.md`), a spec (`docs/cross-project/`), a skill file, CLAUDE.md, a rule page."
- **Defect class:** (e) undefined term; also relative paths with an unstated root.
- **The problem:** "pair doc" is a project term with no gloss; the path pattern alone does not explain what makes a document a *pair* doc (pair of what?). The two directory paths are given relative to a root the file never names, so a reader in a different working directory cannot resolve them. The sentence is also verbless, so whether this is a required input or an illustrative list is left to inference.
- **Severity:** MED.
- **Mitigation:** gloss "pair doc" in three words on first use and state the path root.

---

## LOW

### 38. Step 1's definition of load-bearing does not cover doctrine files
- **Quote (Steps, 1):** "Identify the load-bearing claims: the statements the design depends on being true."
- **Defect class:** (e) definition does not apply to one of the two modes.
- **The problem:** in Mode 2 the target is a doctrine or instruction file with no "design" to depend on anything. A reader applying step 1 to CLAUDE.md has no defined object to identify. Recoverable by analogy (statements other rules depend on), hence LOW.
- **Severity:** LOW.
- **Mitigation:** add the doctrine-file form of the definition in the same sentence.

### 39. The divergence comparator in step 2 differs from the one in Mode 2
- **Quote (Steps, 2):** "A divergence between your written understanding and the document's words is a finding — either the document permitted your misreading, or your correct model contradicts it."
- **Conflicting sentence (pass 1):** "it is the **divergence** between the paraphrase and the intended meaning."
- **Defect class:** (b) conflict in what is compared against what.
- **The problem:** step 2 compares understanding against *the words*; pass 1 compares paraphrase against *the intent*. These are different tests and catch different defects. Flagged LOW rather than higher because finding 6 already carries the load-bearing version of this conflict.
- **Severity:** LOW.
- **Mitigation:** use one comparator vocabulary across both sections.

### 40. The specimen anecdote overstates what restatement would have caught, next to a clause conceding it might not
- **Quote (Steps, 2):** "a written-out model of the boundary would have collided with it immediately, since files on disk survive session restarts. Known limit: if the document and the reviewer are wrong the same way, no restatement detects it".
- **Defect class:** internal tension; unfalsifiable counterfactual.
- **The problem:** "would have collided with it immediately" is asserted about a review that did not happen, and the very next sentence names the case where it would not have. Low impact — the reader still performs step 2 either way.
- **Severity:** LOW.
- **Mitigation:** soften to "a written-out model of the boundary is the kind of check that collides with this class of sentence."

### 41. "The fixed checklists below" describes a checklist set the file plans to change
- **Quote (intro):** "The fixed checklists below keep the review consistent instead of mood-dependent."
- **Conflicting sentences:** "The review board is expected to shrink this way" and "Scale to the change: a full new file or full rewrite earns all eight cells; a one-line tweak may need a single good defect-hunt."
- **Defect class:** (b) mild conflict.
- **The problem:** "fixed" is doing rhetorical work (not mood-dependent) but reads as literal immutability, which two later passages contradict. Most readers recover the intent, hence LOW.
- **Severity:** LOW.
- **Mitigation:** say "the checklists below" or "a stable checklist" rather than "fixed."

### 42. "the single biggest source of design confusion" is an unverifiable superlative
- **Quote (lens 2):** "Anything labeled as existing that is only designed or proposed (or the reverse) — the single biggest source of design confusion."
- **Defect class:** overbroad absolute.
- **The problem:** no measurement is cited, and the file elsewhere does cite measurements (the 17-vs-2 prompt result, the 109-flags run), so the unsourced superlative reads inconsistently. It changes no behavior — lens 2 is run either way.
- **Severity:** LOW.
- **Mitigation:** attribute it ("in our reviews so far, the most common source") or drop the ranking.

### 43. "the discipline rung" introduces an undefined ladder metaphor
- **Quote (lens 3):** "found sitting at the discipline rung, is a finding".
- **Defect class:** (e) undefined term; naming (metaphor, not greppable as a concept).
- **The problem:** "rung" implies an ordered ladder of enforcement levels that the file never lays out. The intent is inferable from the surrounding two-sided framing, hence LOW.
- **Severity:** LOW.
- **Mitigation:** name the levels once, or say "stated only as discipline."

### 44. Lens 3 side two's flag condition ends in a judgment call
- **Quote (lens 3):** "flag it only when the trigger is missing, or when a single failure of the written rule would be disastrous."
- **Defect class:** conditional on a judgment call ("disastrous"); "only when" interacts confusingly with side one's separate flag condition.
- **The problem:** "disastrous" has no threshold, and "only when" is scoped to side two while side one supplies a third independent flag case — a reader skimming may take "only when" as governing the whole lens.
- **Severity:** LOW.
- **Mitigation:** give "disastrous" a concrete floor (irreversible, or silent data loss) and scope the "only" explicitly to side-two rules.

### 45. "Internal inconsistency is a reliable tell of an unexamined call" is broader than it holds
- **Quote (lens 6):** "Internal inconsistency is a reliable tell of an unexamined call."
- **Defect class:** overbroad claim.
- **The problem:** ordinary counterexample: a deliberate, documented exception to a general rule reads as an inconsistency but is the most examined call in the document. Low impact — lens 6 still flags it for confirmation.
- **Severity:** LOW.
- **Mitigation:** "often a tell" plus "confirm whether the exception is deliberate and stated."

### 46. Lens 7 and lens 1 give different verdicts on by-construction mechanisms
- **Quote (lens 7):** "A believed load-bearing mechanism is a named risk until measured."
- **Conflicting sentence (lens 1):** "do not manufacture a probe for a fact that is true by construction".
- **Defect class:** (b) conflict.
- **The problem:** lens 7 admits no by-construction exemption, so the same mechanism is exempt under lens 1 and a named risk under lens 7. Since the lenses run in separate agents and the invoker synthesizes, this surfaces as a dedupe conflict rather than a wrong action — hence LOW, though it becomes MED if finding 1 is fixed without touching lens 7.
- **Severity:** LOW (uncertainty stated: severity depends on how finding 1 is resolved).
- **Mitigation:** cross-reference the by-construction exemption from lens 7.

### 47. Lens 8 rests on two undefined judgment terms
- **Quote (lens 8):** "Does the order remove the highest live risk first? Is the highest-value piece scheduled sensibly or buried behind lower-value work?"
- **Defect class:** conditionals on judgment calls ("live risk," "value," "sensibly").
- **The problem:** none of the three is an observable predicate, and the lens gives no ranking method — two reviewers will nominate different "highest live risks." This is arguably irreducible judgment (the section says "only genuine judgment should stay manual"), so LOW.
- **Severity:** LOW.
- **Mitigation:** name the ranking axis (probability × cost of late discovery) so two reviewers rank the same way.

### 48. The restate agent is told it must not know it is a review, while its invocation is named for the review
- **Quote (pass 1):** "The agent must NOT know it is a review."
- **Related quote (Running the cells):** "Codex-runtime cells run through [`scripts/d-review-codex-cell.py`](../../../scripts/d-review-codex-cell.py) — one invocation per cell (`--cell restate|defect-hunt --tier good|floor --target <path>`)".
- **Defect class:** possible (b) conflict — stated with uncertainty.
- **The problem:** the script name and the `--cell restate|defect-hunt` flag both encode the review framing. Whether the cell sees them depends on how the script constructs the model's input, which SKILL.md does not state — I did not read the script's prompt-assembly code, so I cannot say the leak is real. Flagged per the coverage-over-suppression rule.
- **Severity:** LOW (uncertain — depends on script internals not described in the file).
- **Mitigation:** state in SKILL.md that the cell receives only the template text and the target path, nothing naming the invocation.

### 49. "a code-review skill's job" points at an unnamed artifact
- **Quote (When NOT to use):** "Code correctness, or an implementation reviewed against its design — that is a code-review skill's job, not this one's."
- **Defect class:** (e) unresolvable pointer.
- **The problem:** the indefinite article means the reader is told where *not* to go without being told where to go. Recoverable (the reader can list skills), hence LOW.
- **Severity:** LOW.
- **Mitigation:** name the skill.

### 50. Verdict and ordering vocabulary are lightly underspecified
- **Quotes (Steps, 6):** "Write the findings: severity-tagged, most consequential first, each with its mitigation." / "End with one line: sound · sound-with-named-risks · not-ready-because-X."
- **Defect class:** (c) minor two-readings; placeholder.
- **The problem:** "most consequential first" and severity-tagging are two orderings that can disagree (a MED finding on the core mechanism vs a HIGH on a peripheral one), and "X" is an unfilled placeholder whose expected content (the blocking reason, presumably) is never stated. Both are recovered by any competent reader.
- **Severity:** LOW.
- **Mitigation:** say "ordered by severity, ties broken by consequence," and gloss X as "the single blocking reason."

### 51. "designs lie to themselves" personifies the artifact in an otherwise literal instruction
- **Quote (Steps, 4):** "Never take the document's word for its own existence labels; that is exactly where designs lie to themselves."
- **Defect class:** figurative phrasing in an instruction; the "never" is fine as written.
- **The problem:** a document cannot lie; the intended meaning (authors' aspirational labels survive into the text) has to be reconstructed. No behavioral divergence expected.
- **Severity:** LOW.
- **Mitigation:** state the mechanism plainly — "authors label intended state as existing state."

### 52. "before anything is built from it or it lands" admits two parses
- **Quote (frontmatter description):** "Adversarially review a WRITTEN design, specification, or doctrine document before anything is built from it or it lands".
- **Defect class:** (c) two readings.
- **The problem:** parse A: "before (anything is built from it) or (it lands)" — two triggers. Parse B: "before anything is built from (it or it lands)" — ungrammatical but reachable on a fast read. Parse A is almost certainly intended and recovered immediately.
- **Severity:** LOW.
- **Mitigation:** "before anything is built from it, and before it lands."

---

**Findings by severity:** HIGH 8, MED 29, LOW 15 — 52 total.

clean sections: "The prompt is the lever." (line 50) — its two sentences state a measured result and three imperatives, with no contradiction, no absolute beyond what the cited measurement supports, and no undefined term; the section headings themselves ("Steps", "When NOT to use", "Mode 1", "Mode 2") carry no defects independent of the findings above.
