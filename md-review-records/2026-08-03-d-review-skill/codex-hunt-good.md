1. **HIGH — self-contradiction / incompatible readings.** “**Review never creates:** a finding names what is wrong and points the direction of a fix in one line; the fix itself belongs to the author.” Literally, review may create nothing, including the required findings and mitigations; narrowly, “creates” may mean only “authors the replacement design.”  
   Mitigation: Define precisely what kinds of creation are prohibited.

2. **HIGH — conflict.** “Use when a document is about to be built from or landed, or when the boss says ‘d-review this’.” Conflicting sentence: “Routine re-review of long-shipped doctrine — that is a deliberate consistency sweep, not a per-change gate.” If “the boss” requests d-review of long-shipped doctrine, the reader is simultaneously told to use and not use the skill.  
   Mitigation: State which scope rule takes precedence.

3. **HIGH — impossible when obeyed literally.** “**Write out your exact understanding of each mechanism, rule, and load-bearing claim — subtleties fully elucidated — before hunting defects:** edge behavior, boundary conditions, what is not covered, what it does to adjacent state.” An ambiguous or incomplete document cannot yield an “exact” understanding with “subtleties fully elucidated” without the reviewer inventing missing intent.  
   Mitigation: Distinguish documented understanding from assumptions and unresolved gaps.

4. **HIGH — wrong literal rule / false dichotomy.** “A divergence between your written understanding and the document's words is a finding — either the document permitted your misreading, or your correct model contradicts it.” A reviewer can simply misunderstand clear text; then neither offered explanation holds, yet the sentence requires a false finding.  
   Mitigation: Require the reviewer to rule out reviewer error before reporting divergence.

5. **HIGH — overbroad factual claim.** “A live specimen of the cost of skipping this: a review once passed the confidently false sentence ‘uncommitted work has no copy outside the conversation’ — a written-out model of the boundary would have collided with it immediately, since files on disk survive session restarts.” Files can be deleted by cleanup hooks, reside on ephemeral storage, fail to persist, or disappear with a container; relying literally on this claim can lose work. The referenced review is also unidentified.  
   Mitigation: Scope the persistence claim to a named runtime and link the specimen.

6. **HIGH — unexecutable absolute.** “**Verify every falsifiable claim against ground truth.**” Some claims concern unavailable external systems, historical measurements, future behavior, authorial intent, or inaccessible credentials; “every” makes the review impossible to complete.  
   Mitigation: Define acceptable evidence and how to report claims that cannot be verified.

7. **HIGH — wrong and unexecutable literal procedure.** “Any claim about what exists, what a tool does, what a schema holds, what a commit landed — check it (`git`, `gh`, `grep`, `test -f`).” Those commands do not establish every listed fact: `grep` does not prove schema semantics, `test -f` does not prove tool behavior, and `gh` may be unavailable or unauthorized.  
   Mitigation: Map claim classes to sufficient evidence and provide an unavailable-tool path.

8. **HIGH — overbroad absolute.** “**Re-review after revision covers the delta:** the changed sections plus verification of each prior finding's fix — never a full re-run of the matrix.” A small textual change can alter global invariants, and a full rewrite plainly warrants a full review; following “never” can miss regressions outside the textual delta.  
   Mitigation: Name observable triggers for a full rerun.

9. **HIGH — invalid inference.** “**And repetition migrates out:** a check that repeats identically across reviews is the certain-and-cheaply-checkable kind and belongs in a script or the mechanical check battery; a defect class that recurs across documents belongs upstream in the authoring skill that keeps producing it.” A recurring check can still require judgment, and recurring defects can come from humans or multiple authoring paths rather than one authoring skill.  
   Mitigation: Separate recurrence from demonstrated mechanizability and demonstrated provenance.

10. **HIGH — false dichotomy and wrong discriminator.** “A stated rule either names an enforcement point — a gate, a check, a tool boundary — or it is discipline dressed as enforcement. The discriminator is whether the rule's correct form is already known.” Rules may be advisory, descriptive, aspirational, externally enforced, or intentionally unenforced; knowing their form also does not determine whether enforcement is safe, affordable, or authorized.  
   Mitigation: Define the rule categories and all criteria for mechanization.

11. **HIGH — logically invalid definition.** “Conversely, do not manufacture a probe for a fact that is true by construction — one whose falsity would make the mechanism itself pointless.” A fact can be load-bearing without being true by construction: if filesystem atomicity fails, a mechanism may become pointless, but that does not make atomicity logically guaranteed.  
   Mitigation: Define “true by construction” using an actual invariant rather than the cost of falsity.

12. **HIGH — overbroad “only” and judgment condition.** “Side two: a rule still discovering its own right form legitimately starts as discipline (coding it early freezes a guess and enforces it with machine reliability); there, verify the document names the upgrade trigger — the concrete failure condition that converts it to code — and flag it only when the trigger is missing, or when a single failure of the written rule would be disastrous.” A trigger may exist but be ambiguous, unobservable, dangerously late, or impossible to implement; “only” forbids reporting those defects, while “right form” and “disastrous” are judgment calls.  
   Mitigation: Permit findings on trigger quality and define observable risk criteria.

13. **HIGH — impossible exhaustive requirement.** “For each mechanism, walk the state space systematically: every actor state (busy, idle, mid-turn, dead), every dependency failure (the file it reads, the tool it runs, the channel it writes), every concurrency case (two sessions, re-entry, repeated firing) — and require the document to name or explicitly discard each cell.” The listed states are not exhaustive, “every” state can be unbounded, and “each cell” does not say whether it means a Cartesian product; literal compliance is impossible.  
   Mitigation: Define a bounded state model and the required combinations.

14. **HIGH — wrong absolute.** “An omission is a finding even when the happy path is flawless; the highest-value finds are usually cells the design's own narrative never visits.” An omitted state may be provably unreachable, irrelevant, or already governed by a stated invariant; the sentence still requires a finding.  
   Mitigation: Limit findings to omissions that are relevant and not otherwise covered.

15. **HIGH — internal conflict.** “Name the cut and what replaces it.” Conflicting sentence: “A reviewer who wants to propose an alternative design has left review — that is a create-design task, owned separately.” Naming a replacement can require proposing the prohibited alternative design.  
   Mitigation: Clarify whether reviewers identify an existing replacement or design a new one.

16. **HIGH — unexecutable external dependency.** “The document contradicting itself, its own stated principles, or the project's recent rulings.” A zero-context reader is given neither the rulings nor a location or time boundary for “recent,” so this lens cannot be executed.  
   Mitigation: Supply a canonical rulings source and define the relevant interval.

17. **HIGH — false dichotomy and internal conflict.** “For each load-bearing mechanism: measured (probe, canary, field observation) or merely believed? A believed load-bearing mechanism is a named risk until measured.” A mechanism may be formally proven, guaranteed by construction, or specified by an authoritative interface without being measured. This also conflicts with “do not manufacture a probe for a fact that is true by construction.”  
   Mitigation: Add non-empirical evidence categories and reconcile the probe exception.

18. **HIGH — overbroad requirement plus missing project knowledge.** “Data the design accumulates needs a bound — retention, archival, or the project's artifact-lifecycle rule (no stateless piles) — and a stated expectation of volume.” Naturally finite data or data bounded by an external invariant need not acquire another retention policy, while “the project's artifact-lifecycle rule” and “no stateless piles” are not defined or located.  
   Mitigation: Scope the rule to potentially unbounded data and link the lifecycle doctrine.

19. **HIGH — false absolute.** “A test plan that maps the design's own cells is necessary but only exercises what the design thought of.” Property tests, fuzzing, model checking, and randomized fault injection can discover cases not enumerated by the design; “only” dismisses valid coverage.  
   Mitigation: Distinguish enumerated tests from generative or exploratory tests.

20. **HIGH — impossible or irrelevant literal requirement.** “Require a second, adversarial layer — load, scale, ‘what did we not anticipate’ — that does not assume the design is right.” A reviewer cannot enumerate what nobody anticipated, and load or scale may be irrelevant to a static doctrine or naming proposal.  
   Mitigation: Define applicable adversarial techniques and when each is required.

21. **HIGH — overbroad naming absolutes and internal inconsistency.** “Every name the document introduces — files, scripts, functions, terms, headings, test labels — must be self-documenting and greppable: full words a search matches verbatim, one shared token across a family of related names, no cryptic abbreviations, no bare sequence labels, and no bare numeric references in prose (an issue number always rides with a descriptive handle).” Conventional names such as `API`, `CLI`, `SHA-256`, `README`, or mathematical `x` can be clearer than expanded alternatives; unrelated names need no shared token. The file itself introduces `d-review` and `NC`.  
   Mitigation: State context-sensitive naming tests and explicit exceptions.

22. **HIGH — empirically false generalization.** “Expect almost every truly self-documenting name to run two to five words (boss calibration 2026-08-03): a one-word name is almost never self-documenting, so the reviewer treats it as a finding candidate by default; a longer precise name beats a short ambiguous one, and ease of typing is not a constraint.” Names such as `timeout`, `shutdown`, `parser`, and `README` are self-documenting; typing cost matters for frequently used commands and APIs. Literal obedience creates spurious findings and cumbersome names.  
   Mitigation: Replace word-count presumptions with audience, collision, and usage-frequency criteria.

23. **HIGH — self-contradiction.** “Two pass types, and **they run in SEPARATE agents — never one agent doing both**: whichever task runs first primes the second (a defect-hunt frame makes the restatement adversarial; a restatement frame makes the hunt post-hoc).” Truly separate fresh agents do not prime one another; if the second receives the first task's framing or output, the promised isolation is absent.  
   Mitigation: Identify who is being primed and what context is isolated.

24. **HIGH — impossible absolute and internal conflict.** “Prompt it only to paraphrase: *‘Restate, in your own words, exactly what each sentence's words say. Do not repair it, fill gaps, or infer intent.’*” The agent must also receive the target path or document contents. Later, the file explicitly requires “substituting the target path,” contradicting “only.”  
   Mitigation: Define the complete allowed prompt envelope.

25. **HIGH — missing required input.** “The finding is not the paraphrase — it is the **divergence** between the paraphrase and the intended meaning.” The skill accepts a document path but no statement of intended meaning; a zero-context reviewer cannot compute this divergence.  
   Mitigation: Make authoritative intent or author comparison an explicit input or handoff.

26. **HIGH — impossible output schema.** “Each flag quotes the sentence, gives both readings or the conflict, and a case where obeying the words does the wrong thing.” A merely undefined term or a factually false single-reading sentence may have neither two readings nor a conflicting sentence, yet the schema requires one.  
   Mitigation: Make readings, conflict, and counterexample alternative evidence forms.

27. **HIGH — false absolute / incompatible readings.** “The templates in [`prompts/`](prompts/) are the single prompt source for BOTH runtimes' cells — a Claude cell is prompted with the same template text, substituting the target path — so the two legs cannot drift apart.” Shared template text can prevent template drift, but different system prompts, tools, wrappers, model behavior, and substitution code can still make the runtime legs drift.  
   Mitigation: Scope “cannot drift” to the exact artifact actually shared.

28. **HIGH — unsupported absolute.** “The tier-to-model mapping and per-tier reasoning effort sit at the top of the script, one place to update as models change (currently `gpt-5.6-sol` at high effort for good, `gpt-5.6-terra` at medium for floor — boss-picked ids, live-verified 2026-08-03; effort is pinned in the script so a cell never inherits the machine-local Codex config's default).” Pinning may be ignored, overridden, or broken by CLI precedence or future changes; “never” cannot be established from this file. The “boss-picked” and “live-verified” provenance is also absent.  
   Mitigation: State the verified precedence contract and link its evidence.

29. **HIGH — inconsistent cardinality and unavailable-case failure.** “**The matrix:** {restate, defect-hunt} × {good, floor} × {each available runtime} — with both runtimes available, eight cells total.” Also: “Scale to the change: a full new file or full rewrite earns all eight cells; a one-line tweak may need a single good defect-hunt.” “Each available runtime” permits one or more than two runtimes, producing four or more than eight cells; “all eight” is impossible when only one runtime is available.  
   Mitigation: Define the runtime set and derive cell count from detected availability.

30. **HIGH — unexecutable role dependency and overbroad rationale.** “The **author** compares restatements against intent — a comparator without the intended meaning watches a faithful paraphrase of broken text agree with it and misses the defect.” The procedure does not identify or contact the author, and a non-author comparator can sometimes detect ambiguity or contradiction without knowing intent.  
   Mitigation: Define author availability as a prerequisite and provide a fallback result when unavailable.

31. **MED — non-self-documenting introduced name / internal inconsistency.** “name: d-review” The single letter `d` is unexplained and conflicts with the file's own ban on cryptic abbreviations and presumption against one-word names; one reader may infer “design,” another “document” or “doctrine.”  
   Mitigation: Expand or explicitly define the abbreviation.

32. **MED — judgment-call condition.** “The document must exist and be complete enough to judge — reviewing is judging the written artifact, never co-writing it.” “Complete enough” has no observable threshold, so competent reviewers can disagree about whether to proceed.  
   Mitigation: List minimum required document elements.

33. **MED — judgment-call mode selection.** “Pick the mode by the document's nature: a proposal not yet built gets the soundness checklist; a doctrine or instruction file gets the clarity review; a spec that is both — doctrine carrying designed mechanisms — gets both, in separate passes.” “Nature,” “doctrine,” “instruction,” and “both” lack decision criteria; a normative architecture spec can plausibly receive either one mode or both.  
   Mitigation: Supply observable classification tests and a mixed-document rule.

34. **MED — judgment-dependent introduced term.** “Identify the load-bearing claims: the statements the design depends on being true. Those get the hardest scrutiny.” Whether a claim is “load-bearing,” and what counts as “hardest,” depends on an unstated causal model and review budget.  
   Mitigation: Define load-bearing status and the additional scrutiny it triggers.

35. **MED — overbroad absolute / unclear referent.** “Known limit: if the document and the reviewer are wrong the same way, no restatement detects it; that is what step 4 and the independent passes are for.” “The reviewer” may mean the initial reviewer or every independent reviewer; another restater can reject the shared error, so “no restatement” is broader than the ordinary case supports.  
   Mitigation: Name the specific reviewer and scope the detection limit.

36. **MED — unsupported guarantee.** “Dispatch fresh-context subagents against the same document; they hold no investment in the design.” A subagent may inherit history, prior framing, organizational preferences, or generated context; freshness and lack of investment are not observable from the instruction.  
   Mitigation: Define the actual context-isolation mechanism.

37. **MED — undefined conditional and introduced term.** “Add the companion runtime's read once it is admitted.” Neither “companion runtime” nor “admitted” has a definition or observable admission test.  
   Mitigation: Name the runtime and the admission signal.

38. **MED — incompatible readings.** “**Running it:** the lenses fan out — one focused agent per lens or lens-group, each handed the document and its single question; the invoker synthesizes.” “Per lens” implies eleven agents, while “per lens-group” allows an unspecified smaller number; a grouped agent also receives multiple lens questions despite “its single question.”  
   Mitigation: Define the grouping and assignment rule.

39. **MED — overbroad prohibition.** “No single reviewer walks all eleven inside one context.” A constrained environment may offer no subagents, while one reviewer can still execute a checklist systematically; literal obedience makes review impossible there.  
   Mitigation: State the required fallback when delegation is unavailable.

40. **MED — undefined term and overbroad absolute.** “The review board is expected to shrink this way; only genuine judgment should stay manual.” “Review board” is introduced without definition, “genuine judgment” is subjective, and mechanical checks may remain manual because automation is too costly or lacks access.  
   Mitigation: Define the board and include feasibility in migration decisions.

41. **MED — judgment-call conditional.** “A load-bearing claim resting on first-principles reasoning about how the runtime behaves — what loads when, hook ordering, what a session can and cannot see — needs an empirical probe, not assumption.” “Load-bearing” and “resting on first-principles reasoning” are judgment calls; authoritative documentation or formal semantics can also be sufficient without an empirical probe.  
   Mitigation: Define evidence tiers and observable probe triggers.

42. **MED — unexecutable judgment predicates and undefined terms.** “Side one: a rule that is precisely specifiable now, cheaply checkable, and false-positive-free by construction, found sitting at the discipline rung, is a finding — it belongs in the mechanical check battery from day one, and the review asks why it is not there.” “Precisely,” “cheaply,” “false-positive-free,” “discipline rung,” “mechanical check battery,” and “day one” have no tests or definitions.  
   Mitigation: Define each predicate, the battery location, and the relevant start date.

43. **MED — judgment-call condition.** “Machinery whose value does not justify its cost.” Reviewers lack a value model, cost categories, or threshold, so two competent readers can classify the same mechanism differently.  
   Mitigation: Supply the dimensions used for the value-versus-cost comparison.

44. **MED — overbroad causal claim.** “Internal inconsistency is a reliable tell of an unexamined call.” An inconsistency can result from a typo, stale merge, or incomplete edit rather than an unexamined decision.  
   Mitigation: Present inconsistency as evidence to investigate, not a reliable diagnosis.

45. **MED — judgment-only criteria.** “Does the order remove the highest live risk first? Is the highest-value piece scheduled sensibly or buried behind lower-value work?” “Highest risk,” “highest value,” “sensibly,” and “buried” lack a ranking method, producing divergent reviews.  
   Mitigation: Define risk, value, and scheduling criteria.

46. **MED — ambiguous referent and overbroad instruction.** “Unbounded growth plus correctness-only thinking is a default blind spot; flag its absence even when the ceiling looks far off.” “Its absence” can mean absence of a bound, volume estimate, lifecycle rule, or blind-spot discussion; “ceiling looks far off” supplies no threshold.  
   Mitigation: Name the missing artifact to flag and the applicability test.

47. **MED — unstable and judgment-defined tier names.** “*Good* = the top model at high effort — best at cross-rule contradictions. *Floor* = the mid tier a framework auto-assigns to subagents — the lowest tier that actually reads the file, not the lowest tier that exists (a below-floor model flags its own capability gaps, not the document's defects).” “Top,” “best,” “mid tier,” “a framework,” and “actually reads” are undefined or mutable; a below-floor model can still find real defects.  
   Mitigation: Define tiers by explicit model IDs, evaluation evidence, and the named framework.

48. **MED — unsupported and unfindable evidence.** “The same document yields wildly different results by wording alone — measured: seventeen findings under an adversarial-literal prompt against two under a charitable one that silently resolved the very defects being hunted.” The target document, prompts, models, controls, and run artifact are absent, so “wording alone” cannot be checked.  
   Mitigation: Link the experiment and identify the controlled variables.

49. **MED — undefined introduced name and missing evidence.** “Dedupe across cells — expect heavy overlap (first NC run, 2026-08-03: five cells over a ~120-line skill returned 109 raw flags that consolidated to ~35 distinct defects).” `NC` is unexplained and hard to locate beyond this sentence, and the run has no artifact reference.  
   Mitigation: Expand `NC` and link the recorded run.

50. **MED — wrong causal inference.** “An innocent paraphrase exposes ambiguity by misreading it.” A misreading can be agent error rather than textual ambiguity, while an ambiguous sentence may happen to receive the intended reading and expose nothing.  
   Mitigation: Require multiple supported readings or textual evidence before inferring ambiguity.

51. **MED — overbroad claim.** “Include a fair ‘what's solid’ section — a review that only attacks gets discounted.” A strict red-team gate or findings-only request can deliberately exclude praise and still be accepted; following this sentence can violate the requested output.  
   Mitigation: Make the positive section conditional on the review contract.

52. **MED — unsupported superlative.** “Anything labeled as existing that is only designed or proposed (or the reverse) — the single biggest source of design confusion.” No scope or evidence supports “the single biggest,” and ordinary projects may be dominated by missing requirements or contradictory interfaces instead.  
   Mitigation: Remove or substantiate the ranking.

53. **LOW — uncertain; undefined introduced term.** “Adversarially review a WRITTEN design, specification, or doctrine document before anything is built from it or it lands — a design pair doc, an architecture spec, a skill file, a CLAUDE.md or rule change.” “Design pair doc” is not explained or linked; uncertainty: it may be established local vocabulary, but a zero-context reader cannot know that.  
   Mitigation: Define or link the document type.

54. **LOW — uncertain; undefined external task name.** “A reviewer who wants to propose an alternative design has left review — that is a create-design task, owned separately.” `create-design task` may be a named workflow or merely descriptive prose, and “owned separately” does not identify an owner.  
   Mitigation: Link the workflow or describe it generically and name the owner.

55. **LOW — uncertain; judgment-call timing.** “Review a written document before its content gets expensive: a finished design before anything is built from it, doctrine before it binds readers.” “Gets expensive,” “finished,” and “binds readers” have no observable transition; uncertainty: they may be motivational rather than procedural.  
   Mitigation: State the concrete lifecycle point at which review is expected.

56. **LOW — uncertain; unsupported effectiveness claim.** “The fixed checklists below keep the review consistent instead of mood-dependent.” Checklists reduce variation but cannot ensure consistency across reviewers; uncertainty: “keep” may be intended loosely.  
   Mitigation: Qualify the claimed effect.

57. **LOW — uncertain; overgeneralization.** “A self-review of one's own text has blind spots — the author has already rationalized the weak parts.” An author may not have noticed, considered, or rationalized a newly introduced defect; uncertainty: the sentence may be rhetorical motivation.  
   Mitigation: Phrase this as a risk rather than a universal author state.

58. **LOW — uncertain; subjective output rule.** “Every finding names the specific location, the weakness, a severity (HIGH / MED / LOW), and a concrete mitigation — never a vague concern.” “Concrete” and “vague” have no operational test; uncertainty: examples elsewhere may establish a local convention not included here.  
   Mitigation: Give one acceptable and one unacceptable finding example.

59. **LOW — uncertain; wrong cost absolute.** “A bad name in a design propagates into code, tests, and doctrine — flag it here, where the rename is still free.” Renaming can already carry discussion, link, migration, or coordination cost; uncertainty: “free” may be deliberate hyperbole.  
   Mitigation: Replace “free” with a scoped comparative cost claim.

60. **LOW — uncertain; undefined routing reference.** “Code correctness, or an implementation reviewed against its design — that is a code-review skill's job, not this one's.” No code-review skill name or location is supplied; uncertainty: the sentence still suffices to reject the task even if it cannot route it.  
   Mitigation: Name or link the intended skill.

clean sections: none
