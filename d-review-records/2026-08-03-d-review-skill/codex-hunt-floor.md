1. **HIGH — self-conflict / wrong literal.** “**Review never creates:** a finding names what is wrong and points the direction of a fix in one line; the fix itself belongs to the author.” / “A reviewer who wants to propose an alternative design has left review — that is a create-design task, owned separately.” / “Name the cut and what replaces it.” Conflict: naming both a cut and its replacement is proposing an alternative design, which the first two sentences prohibit. Mitigation: make the permitted depth of a mitigation consistent.

2. **HIGH — wrong literal.** “A divergence between your written understanding and the document's words is a finding — either the document permitted your misreading, or your correct model contradicts it.” Counterexample: a reviewer simply misreads an unambiguous sentence; that is neither document ambiguity nor a correct conflicting model, yet the sentence requires a false finding. Mitigation: allow for reviewer error as a third outcome.

3. **HIGH — unexecutable by a zero-context reader.** “Verify every falsifiable claim against ground truth.” Counterexample: “this service will launch next year” is falsifiable but has no presently accessible ground truth; the universal instruction cannot be completed. Mitigation: define the accessible evidence boundary and treatment of unverifiable claims.

4. **HIGH — unexecutable by a zero-context reader.** “Dispatch fresh-context subagents against the same document; they hold no investment in the design.” Counterexample: a reader with no subagent facility cannot dispatch anyone, and the file gives no fallback. Mitigation: specify a fallback when independent agents are unavailable.

5. **HIGH — undefined reference / unexecutable condition.** “Add the companion runtime's read once it is admitted.” This occurs twice. A zero-context reader cannot identify the companion runtime, who admits it, or the observable admission condition. Mitigation: name the runtime and admission criterion.

6. **HIGH — unexecutable procedure.** “**Running it:** the lenses fan out — one focused agent per lens or lens-group, each handed the document and its single question; the invoker synthesizes.” “Lens-group,” “single question,” and “invoker” are not defined; the checklist supplies no grouping rule or question assignment. Mitigation: define those roles and the dispatch inputs.

7. **HIGH — absolute overreach / unexecutable.** “No single reviewer walks all eleven inside one context.” Counterexample: a review environment with one available reviewer cannot perform Mode 1 at all. Mitigation: state when a single-reviewer fallback is permitted.

8. **HIGH — absolute overreach.** “**Re-review after revision covers the delta:** the changed sections plus verification of each prior finding's fix — never a full re-run of the matrix.” Counterexample: changing a central invariant or replacing the document wholesale can invalidate every prior conclusion. Mitigation: permit a full rerun under stated observable triggers.

9. **HIGH — false dichotomy.** “A stated rule either names an enforcement point — a gate, a check, a tool boundary — or it is discipline dressed as enforcement.” Counterexample: a rule can be explicitly advisory, a policy decision, or enforced outside the document without naming its enforcement point. Mitigation: include the missing categories or limit the claim’s scope.

10. **HIGH — absolute overreach.** “Side two: a rule still discovering its own right form legitimately starts as discipline (coding it early freezes a guess and enforces it with machine reliability); there, verify the document names the upgrade trigger — the concrete failure condition that converts it to code — and flag it only when the trigger is missing, or when a single failure of the written rule would be disastrous.” Counterexample: a rule can have a trigger and non-disastrous individual failures yet still be contradictory, unlawful, or too costly to leave as discipline. Mitigation: remove “only” or enumerate the intended exclusive scope.

11. **HIGH — impossible exhaustive procedure.** “For each mechanism, walk the state space systematically: every actor state (busy, idle, mid-turn, dead), every dependency failure (the file it reads, the tool it runs, the channel it writes), every concurrency case (two sessions, re-entry, repeated firing) — and require the document to name or explicitly discard each cell.” Readings: the parenthetical lists are exhaustive, or merely examples; the first is plainly incomplete and the second leaves an unbounded state space. Mitigation: define a finite enumeration method and explicit scope boundary.

12. **HIGH — undefined external corpus.** “The document contradicting itself, its own stated principles, or the project's recent rulings.” A zero-context reader cannot locate “the project's recent rulings” or determine what counts as recent. Mitigation: name the source and recency boundary.

13. **HIGH — false binary / conflict.** “For each load-bearing mechanism: measured (probe, canary, field observation) or merely believed?” / “A believed load-bearing mechanism is a named risk until measured.” Counterexample: a mechanism can be established by formal proof or a definition, neither measured nor merely believed; this also conflicts with “do not manufacture a probe for a fact that is true by construction.” Mitigation: recognize non-empirical evidence and reconcile it with the probe rule.

14. **HIGH — overbroad naming rule.** “Every name the document introduces — files, scripts, functions, terms, headings, test labels — must be self-documenting and greppable: full words a search matches verbatim, one shared token across a family of related names, no cryptic abbreviations, no bare sequence labels, and no bare numeric references in prose (an issue number always rides with a descriptive handle).” Counterexample: standard identifiers such as `git`, `URL`, API names, versions, dates, and established issue references can be clear but fail one or more literal requirements; “bare numeric references” also has two scopes: all numbers or only issue numbers. Mitigation: define the scope, search context, and exceptions.

15. **HIGH — unexecutable by a single-agent reader.** “Two pass types, and **they run in SEPARATE agents — never one agent doing both**: whichever task runs first primes the second (a defect-hunt frame makes the restatement adversarial; a restatement frame makes the hunt post-hoc).” Counterexample: one available agent cannot run both passes despite the mandatory “never.” Mitigation: provide a single-agent fallback or make multi-agent availability a precondition.

16. **HIGH — impossible knowledge constraint.** “The agent must NOT know it is a review.” Counterexample: the target path, surrounding system context, or document content may reveal that it is a review; the invoker cannot guarantee the agent lacks that knowledge. Mitigation: replace the unknowable mental-state requirement with controllable prompt constraints.

17. **HIGH — incompatible output requirements.** “Each flag quotes the sentence, gives both readings or the conflict, and a case where obeying the words does the wrong thing.” Counterexample: an undefined term can be unexecutable without yielding two readings, a conflicting sentence, or an action that produces a wrong result rather than a halt. Mitigation: make the required evidence conditional on defect class.

18. **HIGH — undefined execution model.** “Claude-runtime cells are fresh subagents.” “Claude-runtime” and the procedure for creating a “fresh subagent” are not defined in the file. Mitigation: define the runtime and dispatch mechanism or link to a self-contained procedure.

19. **HIGH — internal conflict.** “**The matrix:** {restate, defect-hunt} × {good, floor} × {each available runtime} — with both runtimes available, eight cells total.” / “Scale to the change: a full new file or full rewrite earns all eight cells; a one-line tweak may need a single good defect-hunt.” If the companion runtime is not admitted, the matrix has four cells, yet a full rewrite still “earns all eight.” Mitigation: express the requirement per available runtime.

20. **HIGH — undefined capability tier / false absolute.** “*Floor* = the mid tier a framework auto-assigns to subagents — the lowest tier that actually reads the file, not the lowest tier that exists (a below-floor model flags its own capability gaps, not the document's defects).” The framework and its assigned tier are unidentified; a below-floor model can also identify a real defect, so “not the document’s defects” is false. Mitigation: name the framework and treat below-floor output as lower-confidence, not impossible.

21. **HIGH — missing required participant and input.** “The **author** compares restatements against intent — a comparator without the intended meaning watches a faithful paraphrase of broken text agree with it and misses the defect.” Counterexample: when the author is unavailable or intent is undocumented, synthesis cannot be performed and the file gives no alternate authority. Mitigation: define an intent source and fallback owner.

22. **MED — non-self-documenting YAML name / self-conflict.** “name: d-review” The one-letter `d` is unexplained and broad in search results; it also violates the document’s later ban on cryptic abbreviations. Mitigation: use a descriptive, distinctive skill name.

23. **MED — judgment-call condition / undefined authority.** “Use when a document is about to be built from or landed, or when the boss says "d-review this".” “About to” has no observable threshold, and “boss” is not identified. Mitigation: define a concrete trigger and authority.

24. **MED — judgment-call condition.** “Review a written document before its content gets expensive: a finished design before anything is built from it, doctrine before it binds readers.” “Gets expensive” and “binds readers” are not observable predicates; readers can disagree whether the gate has passed. Mitigation: replace them with lifecycle events.

25. **MED — judgment-call condition.** “The document must exist and be complete enough to judge — reviewing is judging the written artifact, never co-writing it.” “Complete enough to judge” has no test, so two reviewers can accept or reject the same draft. Mitigation: state minimum required sections or a readiness test.

26. **MED — absolute claim broader than it can hold.** “A shipped instruction file fails differently: one sentence that is ambiguous, self-contradictory, or literally wrong, which a sympathetic reader silently repairs and never reports.” Counterexample: a sympathetic reader can report the defect precisely because they repaired it mentally. Mitigation: remove the universal claim about reader behavior.

27. **MED — unexplained terms.** “The path to the document — a pair doc (`docs/issues/<n>-<slug>.md`), a spec (`docs/cross-project/`), a skill file, CLAUDE.md, a rule page.” “Pair doc,” “rule page,” and the `<n>-<slug>` convention are not explained to a zero-context reader. Mitigation: define each document category or use generic examples.

28. **MED — incompatible classifications.** “Pick the mode by the document's nature: a proposal not yet built gets the soundness checklist; a doctrine or instruction file gets the clarity review; a spec that is both — doctrine carrying designed mechanisms — gets both, in separate passes.” A proposed instruction file with designed mechanisms fits multiple branches, but the sentence does not say whether it is a proposal, doctrine, or “spec that is both.” Mitigation: give an ordered decision rule.

29. **MED — undefined ranking criterion.** “Those get the hardest scrutiny.” “Hardest” lacks a method or measure, so reviewers can prioritize different claims. Mitigation: state the scrutiny action or ranking criteria.

30. **MED — impossible completeness requirement.** “Write out your exact understanding of each mechanism, rule, and load-bearing claim — subtleties fully elucidated — before hunting defects: edge behavior, boundary conditions, what is not covered, what it does to adjacent state.” “Exact,” “fully,” “each mechanism,” and “adjacent state” provide no finite stopping rule. Mitigation: define the required restatement fields and scope.

31. **MED — unexecutable verification instruction.** “Any claim about what exists, what a tool does, what a schema holds, what a commit landed — check it (`git`, `gh`, `grep`, `test -f`).” Counterexample: a claim about a remote production schema or tool behavior cannot necessarily be checked by any listed command, which may also be unavailable. Mitigation: map claim classes to evidence sources and failure handling.

32. **MED — judgment-based output requirement.** “Write the findings: severity-tagged, most consequential first, each with its mitigation.” “Most consequential” has no severity-to-order rule, so competent reviewers can order the same findings differently. Mitigation: define the ordering rule.

33. **MED — judgment-call requirement.** “Include a fair "what's solid" section — a review that only attacks gets discounted.” “Fair” and “gets discounted” depend on an unidentified evaluator and standard. Mitigation: state an objective inclusion rule or make this optional guidance.

34. **MED — undefined verdict vocabulary.** “End with one line: sound · sound-with-named-risks · not-ready-because-X.” “Sound,” “named risks,” and `X` have no decision criteria, so the same evidence can yield different verdicts. Mitigation: define the verdict thresholds and placeholder format.

35. **MED — undefined migration destination and test.** “**And repetition migrates out:** a check that repeats identically across reviews is the certain-and-cheaply-checkable kind and belongs in a script or the mechanical check battery; a defect class that recurs across documents belongs upstream in the authoring skill that keeps producing it.” “Repeats identically,” “certain-and-cheaply-checkable,” “mechanical check battery,” and “upstream” lack criteria or locations. Mitigation: define the recurrence threshold and destination artifacts.

36. **MED — judgment-call term.** “The review board is expected to shrink this way; only genuine judgment should stay manual.” “Review board” and “genuine judgment” are undefined, so the “only” rule cannot be applied consistently. Mitigation: define the board and a test for automation candidacy.

37. **MED — overbroad evidence rule.** “A load-bearing claim resting on first-principles reasoning about how the runtime behaves — what loads when, hook ordering, what a session can and cannot see — needs an empirical probe, not assumption.” Counterexample: an authoritative formal contract can establish behavior without an empirical probe; “runtime,” “hook,” and “session” are also undefined. Mitigation: distinguish empirical, formal, and documented evidence.

38. **MED — judgment-call exception.** “Conversely, do not manufacture a probe for a fact that is true by construction — one whose falsity would make the mechanism itself pointless.” “True by construction” and “pointless” are subjective assessments; two reviewers can disagree on whether to test. Mitigation: define qualifying invariants and the evidence required.

39. **MED — unsupported superlative.** “Anything labeled as existing that is only designed or proposed (or the reverse) — the single biggest source of design confusion.” Counterexample: incompatible requirements or missing failure handling can be the larger source of confusion in a given design. Mitigation: present this as a common risk rather than a universal ranking.

40. **MED — conflicting discriminator.** “The discriminator is whether the rule's correct form is already known.” This conflicts with the preceding discriminator, which is whether a rule names an enforcement point; a precisely known rule can still lack one. Mitigation: state one classification test and its outcome.

41. **MED — judgment-call condition.** “Side one: a rule that is precisely specifiable now, cheaply checkable, and false-positive-free by construction, found sitting at the discipline rung, is a finding — it belongs in the mechanical check battery from day one, and the review asks why it is not there.” “Precisely,” “cheaply,” “false-positive-free,” “discipline rung,” and “day one” are undefined. Mitigation: define measurable thresholds and the relevant lifecycle point.

42. **MED — judgment-call defect definition.** “Machinery whose value does not justify its cost.” Neither value nor cost is measured, so the definition yields divergent findings. Mitigation: supply evaluation dimensions or examples with boundaries.

43. **MED — counterfactual judgment.** “Two named smells: *unnecessary tracked state* — state the design maintains that a state-agnostic mechanism would obviate; and a *compensating mechanism* — machinery papering over a gap that a simpler primitive would eliminate outright.” “Would obviate” and “would eliminate outright” require unstated counterfactual assumptions. Mitigation: require the proposed simpler mechanism and its demonstrated tradeoff.

44. **MED — judgment-call questions.** “Does the order remove the highest live risk first?” / “Is the highest-value piece scheduled sensibly or buried behind lower-value work?” “Highest,” “live,” “value,” “sensibly,” and “buried” have no measurable meaning. Mitigation: define the risk and value ranking method.

45. **MED — undefined project rule / ambiguous pronoun.** “Data the design accumulates needs a bound — retention, archival, or the project's artifact-lifecycle rule (no stateless piles) — and a stated expectation of volume.” / “Unbounded growth plus correctness-only thinking is a default blind spot; flag its absence even when the ceiling looks far off.” “Artifact-lifecycle rule” and “stateless piles” are unexplained; “its absence” can mean absence of growth, correctness-only thinking, or a stated bound. Mitigation: identify the rule and name the exact missing condition.

46. **MED — absolute claim broader than it can hold.** “A test plan that maps the design's own cells is necessary but only exercises what the design thought of.” Counterexample: such a plan can include fuzzing, randomized inputs, or external regression cases that exercise unanticipated behavior. Mitigation: limit the claim to a plan containing only design-derived cells.

47. **MED — unsupported naming heuristic.** “Expect almost every truly self-documenting name to run two to five words (boss calibration 2026-08-03): a one-word name is almost never self-documenting, so the reviewer treats it as a finding candidate by default; a longer precise name beats a short ambiguous one, and ease of typing is not a constraint.” “Boss calibration” is unexplained; standard names such as `Git` or `Linux` are one word and self-documenting in context, while typing can be a real interface constraint. Mitigation: make this a contextual heuristic with stated exceptions.

48. **MED — overbroad causal claim.** “A bad name in a design propagates into code, tests, and doctrine — flag it here, where the rename is still free.” Counterexample: a design-only term may never reach implementation, and a name can already be public or contract-bound before build work begins. Mitigation: qualify propagation and assess existing dependencies before calling a rename free.

49. **MED — incompatible readings.** “Prompt it only to paraphrase: *"Restate, in your own words, exactly what each sentence's words say. Do not repair it, fill gaps, or infer intent."*” “In your own words” calls for rephrasing, while “exactly what each sentence's words say” can literally require word-for-word restatement. Mitigation: distinguish exact meaning from exact wording.

50. **MED — absolute claim not guaranteed by the mechanism.** “The templates in [`prompts/`](prompts/) are the single prompt source for BOTH runtimes' cells — a Claude cell is prompted with the same template text, substituting the target path — so the two legs cannot drift apart.” Counterexample: system prompts, wrappers, substitutions, or runtime-specific instructions can drift while the template text remains shared. Mitigation: limit the claim to template-source consistency and specify how full prompts are compared.

51. **MED — undefined model-selection rule.** “*Good* = the top model at high effort — best at cross-rule contradictions.” “Top” and “best” have no source, metric, or update rule for a zero-context reader. Mitigation: name the selection authority and evaluation criterion.

52. **MED — judgment-call scaling rule.** “Scale to the change: a full new file or full rewrite earns all eight cells; a one-line tweak may need a single good defect-hunt.” “May need” supplies no observable condition for deciding whether the one-line change needs more cells. Mitigation: specify escalation triggers for small changes.

53. **MED — unverified, non-self-contained measurement.** “The same document yields wildly different results by wording alone — measured: seventeen findings under an adversarial-literal prompt against two under a charitable one that silently resolved the very defects being hunted.” “Measured” provides no target, runtime, prompt text, or evidence; “wording alone” also asserts a causal isolation the sentence does not establish. Mitigation: link the experiment or present it as a non-binding anecdote.

54. **MED — unexplained name.** “Dedupe across cells — expect heavy overlap (first NC run, 2026-08-03: five cells over a ~120-line skill returned 109 raw flags that consolidated to ~35 distinct defects).” “NC” is introduced without expansion and is difficult to locate meaningfully by grep. Mitigation: expand or link the run identifier.

55. **MED — undefined alternative workflow.** “Code correctness, or an implementation reviewed against its design — that is a code-review skill's job, not this one's.” A zero-context reader cannot identify which “code-review skill” to use. Mitigation: name or link the replacement skill.

56. **MED — judgment-call exclusion.** “Routine re-review of long-shipped doctrine — that is a deliberate consistency sweep, not a per-change gate.” “Routine,” “long-shipped,” and “deliberate consistency sweep” lack thresholds and procedure. Mitigation: define the age/change criteria and route for the sweep.

57. **LOW — unsupported absolute, uncertain.** “Known limit: if the document and the reviewer are wrong the same way, no restatement detects it; that is what step 4 and the independent passes are for.” Uncertainty: independent restatements or verification can expose a shared premise, so “no” is stronger than the stated mechanism warrants. Mitigation: describe this as a risk rather than an impossibility.

58. **LOW — unsupported causal claim, uncertain.** “An innocent paraphrase exposes ambiguity by misreading it.” Uncertainty: a paraphrase can choose the intended reading even when another incompatible reading exists, so ambiguity may remain hidden. Mitigation: say that divergent paraphrases can expose ambiguity.

clean sections: none.
