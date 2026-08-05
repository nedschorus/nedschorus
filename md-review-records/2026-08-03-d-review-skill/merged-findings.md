# Merged defect findings — four review cells, deduplicated

Cell keys: CH-good = claude-hunt-good, CH-floor = claude-hunt-floor, CX-good = codex-hunt-good, CX-floor = codex-hunt-floor.
Order: HIGH, then MED, then LOW; within a severity, findings flagged by more cells first. Severity shown is the maximum any cell assigned. Uncertainty tags carried from the originating cell are preserved in parentheses.

---

## HIGH

1. [HIGH] "The document contradicting itself, its own stated principles, or the project's recent rulings." — the lens depends on a body of project rulings the file never locates, dates, or hands to the lens agent, so the check cannot be executed. — cells: {CH-good, CH-floor, CX-good, CX-floor} — mitigation: name the canonical rulings source and the recency window, and state that the lens agent receives it alongside the document.

2. [HIGH] "or the project's artifact-lifecycle rule (no stateless piles)" — a rule cited with a definite article but no path, glossed with jargon ("stateless piles") that does not decode on its own. — cells: {CH-good, CH-floor, CX-good, CX-floor} — mitigation: link the lifecycle doctrine and replace the gloss with a plain statement of what it prohibits.

3. [HIGH] "so the two legs cannot drift apart" — an absolute guarantee the described mechanism does not provide, since only the Codex leg reads the template mechanically and system prompts, wrappers, and inline edits can still diverge. — cells: {CH-good, CH-floor, CX-good, CX-floor} — mitigation: scope the claim to template-source consistency, or name the gate that actually enforces identical prompts on the Claude leg.

4. [HIGH] "A stated rule either names an enforcement point ... or it is discipline dressed as enforcement." — a false dichotomy with no cell for honestly-labeled discipline, advisory rules, or rules enforced outside the document, and it contradicts the same lens's "Side two". — cells: {CH-good, CH-floor, CX-good, CX-floor} — mitigation: add the missing categories to the opening sentence so only masquerading discipline is a finding by default.

5. [HIGH] "check it (`git`, `gh`, `grep`, `test -f`)" — the four listed tools cannot establish the claim classes named (schema semantics, tool behavior, external model ids, API limits), and may themselves be unavailable. — cells: {CH-good, CH-floor, CX-good, CX-floor} — mitigation: map claim classes to sufficient evidence sources and give a path for claims no local tool can check.

6. [HIGH] "the mid tier a framework auto-assigns to subagents" — "a framework" is indefinite and unnamed, so the reader cannot look up the default that defines the floor tier. — cells: {CH-good, CH-floor, CX-good, CX-floor} — mitigation: name the framework and cite where its subagent tier assignment is documented.

7. [HIGH] "**Review never creates:** ... the fix itself belongs to the author." vs "Name the cut and what replaces it." — the file both forbids proposing an alternative design and requires naming the replacement and a concrete mitigation. — cells: {CH-good, CX-good, CX-floor} — mitigation: define the permitted depth of a mitigation in observable terms (naming an existing primitive allowed, specifying new mechanism out of scope) and use that wording in the intro, lens 5, and step 3.

8. [HIGH] "The **author** compares restatements against intent" — the decisive comparison requires intent the skill never takes as an input and an author the procedure never identifies or contacts. — cells: {CH-good, CX-good, CX-floor} — mitigation: make authoritative intent an explicit input, and define a substitute comparator plus its stated limits when the author is unavailable.

9. [HIGH] "Each flag quotes the sentence, gives both readings or the conflict, and a case where obeying the words does the wrong thing." — an output schema that cannot be satisfied for undefined terms, unexecutable sentences, or three-way ambiguities, which have no misobedience case and more than two readings. — cells: {CH-good, CX-good, CX-floor} — mitigation: make the required evidence conditional on defect class and say "the readings" rather than "both".

10. [HIGH] "never a full re-run of the matrix" — an absolute that blocks a full re-review even after a wholesale rewrite or a change to a central invariant, and conflicts with "a full rewrite earns all eight cells". — cells: {CH-good, CX-good, CX-floor} — mitigation: scope the delta rule to targeted revisions and name observable triggers that reset to a full pass.

11. [HIGH] "every actor state ... every dependency failure ... every concurrency case ... name or explicitly discard each cell" — a full cross-product per mechanism is impossible to enumerate or transcribe, and the parenthetical lists are neither exhaustive nor marked as examples. — cells: {CH-good, CX-good, CX-floor} — mitigation: require coverage of reachable, consequential cells only, and state that the enumeration prompts the reviewer rather than binding the document.

12. [HIGH] "flag it only when the trigger is missing, or ... would be disastrous" — "disastrous" has no threshold, so two reviewers reach opposite flag decisions from the same rule. — cells: {CH-good, CH-floor, CX-good} — mitigation: anchor "disastrous" to an observable floor such as irreversible outside git, silent data loss, or shared-credential exposure.

13. [HIGH] "measured (probe, canary, field observation) or merely believed?" and "A believed load-bearing mechanism is a named risk until measured." — a false binary that admits no formally proven, definitionally guaranteed, or contract-specified mechanism, and that contradicts lens 1's by-construction probe exemption. — cells: {CH-good, CX-good, CX-floor} (CH-good flagged its severity as uncertain, contingent on how the by-construction defect is resolved) — mitigation: add non-empirical evidence categories and cross-reference the by-construction exemption from lens 7.

14. [HIGH] "{restate, defect-hunt} × {good, floor} × {each available runtime} ... eight cells total" — cell count is derived from an unfixed runtime set, so "all eight cells" is unachievable when only one runtime is available or admitted, and permits more than eight if a third appears. — cells: {CH-good, CX-good, CX-floor} — mitigation: define the runtime set and express the requirement per detected available runtime rather than as a fixed eight.

15. [HIGH] "Add the companion runtime's read once it is admitted." — "companion runtime" and "admitted" are undefined: no admitter, no criterion, no place to check the current status. — cells: {CH-good, CX-good, CX-floor} — mitigation: name the runtime and the observable admission signal, or drop the conditional.

16. [HIGH] "**Verify every falsifiable claim against ground truth.**" — an unbounded absolute covering claims with no presently accessible ground truth (future behavior, external systems, historical measurements), so it can never be completed. — cells: {CH-good, CX-good, CX-floor} — mitigation: define the accessible-evidence boundary and prescribe reporting falsifiable-but-uncheckable claims as unverified.

17. [HIGH] "a one-word name is almost never self-documenting, so the reviewer treats it as a finding candidate by default" — a hedged claim operationalized as an unhedged default, generating spurious findings against correct names like `timestamp`, `checksum`, `parser`, `README`. — cells: {CH-good, CX-good, CX-floor} — mitigation: state the real discriminator (generic or overloaded in context) and replace the word-count presumption with audience, collision, and usage criteria.

18. [HIGH] "Write out your exact understanding ... before hunting defects" vs "they run in SEPARATE agents — never one agent doing both" — step 2 orders one reviewer to restate then hunt, the exact sequence Mode 2 forbids as mutually priming, and steps 1–6 are not marked Mode-1-only. — cells: {CH-good, CH-floor} — mitigation: mark step 2 as Mode 1 only, or state that in Mode 2 it is discharged by the delegated restate cells.

19. [HIGH] "flag it only when the trigger is missing, or ..." — the "only" forbids reporting real defects in trigger quality (ambiguous, unobservable, dangerously late, or unimplementable triggers). — cells: {CX-good, CX-floor} — mitigation: remove "only" or enumerate the intended exclusive scope so trigger-quality findings remain reportable.

20. [HIGH] "do not manufacture a probe for a fact that is true by construction — one whose falsity would make the mechanism itself pointless" — the offered test identifies load-bearing facts rather than by-construction ones, so it exempts precisely the claims most needing a probe. — cells: {CH-good, CX-good} — mitigation: define "true by construction" by an actual invariant (true by definition of the artifact) and state that stake level is not the discriminator.

21. [HIGH] "Add the companion runtime's cells once it is admitted." vs "with both runtimes available, eight cells total" — the same paragraph says the second runtime awaits a future admission and that both are available now, while the operational section describes it as live and verified. — cells: {CH-good, CH-floor} — mitigation: state the current admission status once and make the cell count follow from it.

22. [HIGH] "Claude-runtime cells are fresh subagents." — the matrix needs a good-tier and floor-tier Claude cell but only the Codex leg gets a tier-to-model mapping, so the tier axis silently collapses on the Claude side. — cells: {CH-good, CH-floor} — mitigation: state the Claude-runtime tier-to-model (and effort) mapping in the same place as the Codex one.

23. [HIGH] "Every name the document introduces ... must be self-documenting and greppable: full words ..." — overbroad: conventional identifiers (`API`, `CLI`, `SHA-256`, `README`, versions, dates) are clearer unexpanded, unrelated names need no shared token, and "bare numeric references" has two possible scopes. — cells: {CX-good, CX-floor} — mitigation: state context-sensitive naming tests, the search context assumed, and explicit exceptions.

24. [HIGH] "a check that repeats identically across reviews is the certain-and-cheaply-checkable kind" — repetition and mechanizability are independent; the file's own judgment lenses repeat every review and would be moved into a script by this rule. — cells: {CH-good, CX-good} — mitigation: add the missing conjunct — repeats identically **and** has a mechanically decidable predicate.

25. [HIGH] "either the document permitted your misreading, or your correct model contradicts it" — a false dichotomy: a reviewer can simply misread unambiguous text, yet the sentence still mandates a finding. — cells: {CX-good, CX-floor} — mitigation: admit reviewer error as a third outcome and require ruling it out before reporting the divergence.

26. [HIGH] "your exact understanding ... subtleties fully elucidated" — "exact" and "fully" give no stopping rule and are unachievable against an ambiguous or incomplete document without inventing intent. — cells: {CX-good, CX-floor} — mitigation: define the required restatement fields and scope, and separate documented understanding from assumptions and unresolved gaps.

27. [HIGH] "Require a second, adversarial layer — load, scale, 'what did we not anticipate'" — inapplicable to documents with no executable surface (doctrine, naming conventions), and nobody can enumerate what was never anticipated, so it manufactures a mandatory finding. — cells: {CH-good, CX-good} — mitigation: condition the lens on an executable surface and define which adversarial techniques are required when.

28. [HIGH] "A test plan that maps the design's own cells ... only exercises what the design thought of." — false absolute: property tests, fuzzing, model checking, and randomized fault injection reach cases the design never enumerated. — cells: {CX-good, CX-floor} — mitigation: limit the claim to plans containing only design-derived cases, and distinguish enumerated from generative tests.

29. [HIGH] "No single reviewer walks all eleven inside one context." — an absolute prohibition that makes Mode 1 impossible in an environment with no subagent facility, where one reviewer could still work the checklist systematically. — cells: {CX-good, CX-floor} — mitigation: state the permitted single-reviewer fallback when delegation is unavailable.

30. [HIGH] "one focused agent per lens or lens-group, each handed the document and its single question" — "per lens" implies eleven agents while "lens-group" allows fewer, and a grouped agent necessarily gets more than one question; "lens-group" and "invoker" are undefined. — cells: {CX-good, CX-floor} — mitigation: define the grouping rule, the question assignment, and the invoker role with its dispatch inputs.

31. [HIGH] "a below-floor model flags its own capability gaps, not the document's defects" — false as stated: a below-floor model can still surface real defects, so the claim overstates the tier boundary. — cells: {CX-good, CX-floor} — mitigation: treat below-floor output as lower-confidence rather than impossible, and cite the evaluation evidence behind the tier line.

32. [HIGH] "The agent must NOT know it is a review." — an unenforceable mental-state constraint: the target path, invocation flags (`--cell restate|defect-hunt`), script name, or surrounding context can reveal the framing. — cells: {CH-good, CX-floor} (CH-good flagged uncertain — depends on the script's prompt assembly, which SKILL.md does not describe) — mitigation: replace the mental-state requirement with controllable prompt constraints and state that the cell receives only template text plus target path.

33. [HIGH] "The discriminator is whether the rule's correct form is already known." — conflicts with the discriminator given one sentence earlier (whether the rule names an enforcement point); a precisely known rule can still lack one, and knowing the form does not establish that mechanizing it is safe, affordable, or authorized. — cells: {CX-good, CX-floor} — mitigation: state one classification test and all criteria for mechanization.

34. [HIGH] "a defect class that recurs across documents belongs upstream in the authoring skill that keeps producing it" — an invalid provenance inference: recurring defects can come from human authors or several authoring paths, not one upstream skill. — cells: {CX-good} — mitigation: require demonstrated provenance before assigning a defect class upstream.

35. [HIGH] "since files on disk survive session restarts" — overbroad persistence claim: files can be removed by cleanup hooks, live on ephemeral storage, or vanish with a container; the cited review is also unidentified. — cells: {CX-good} — mitigation: scope the persistence claim to a named runtime and link the specimen review.

36. [HIGH] "**Review never creates:**" — read literally it forbids creating anything, including the findings and mitigations the skill requires; "creates" is never defined. — cells: {CX-good} — mitigation: define precisely which kinds of creation are prohibited.

37. [HIGH] "when the boss says 'd-review this'" vs "Routine re-review of long-shipped doctrine — ... not a per-change gate." — if the boss asks for a review of long-shipped doctrine the reader is told both to use and not to use the skill. — cells: {CX-good} — mitigation: state which scope rule takes precedence.

38. [HIGH] "An omission is a finding even when the happy path is flawless" — wrong when obeyed literally: an omitted state may be provably unreachable, irrelevant, or already governed by a stated invariant. — cells: {CX-good} — mitigation: limit findings to omissions that are reachable, relevant, and not otherwise covered.

39. [HIGH] "Data the design accumulates needs a bound" — overbroad: naturally finite data, or data bounded by an external invariant, needs no additional retention policy. — cells: {CX-good} — mitigation: scope the requirement to potentially unbounded data.

40. [HIGH] "whichever task runs first primes the second" — the stated rationale is incoherent for genuinely separate fresh agents, which cannot prime one another; if the second does receive the first's framing, the promised isolation is absent. — cells: {CX-good} — mitigation: identify who is being primed and exactly what context is isolated between cells.

41. [HIGH] "Prompt it only to paraphrase: 'Restate, in your own words, exactly what each sentence's words say...'" — the "only" is contradicted by the cell's required inputs, since the file elsewhere mandates "substituting the target path". — cells: {CX-good} — mitigation: define the complete allowed prompt envelope rather than an "only" that the procedure violates.

42. [HIGH] "effort is pinned in the script so a cell never inherits the machine-local Codex config's default" — "never" cannot be established from this file: CLI precedence, overrides, or future changes can defeat pinning, and the boss-picked/live-verified provenance is unlinked. — cells: {CX-good} — mitigation: state the verified precedence contract and link its evidence.

43. [HIGH] "A separate agent, told to find defects and forbidden to resolve them" vs "Every finding names ... a concrete mitigation" — the cell is told both to withhold resolutions and to supply one with every finding, and pass 2's own flag contents omit severity and mitigation entirely. — cells: {CH-good} — mitigation: say explicitly that cell output is severity-tagged but mitigation-free, and that mitigations are added at synthesis.

44. [HIGH] "A self-review of one's own text has blind spots" vs "The **author** compares restatements against intent" — the procedure disqualifies the author for bias, then hands the author the chokepoint that decides which findings survive. — cells: {CH-floor} — mitigation: scope the step-5 prohibition to the hunting and restating passes, or give the comparison to a briefed non-author who cannot waive findings alone.

45. [HIGH] "Dispatch fresh-context subagents against the same document" — unexecutable where no subagent facility exists, and the file offers no fallback. — cells: {CX-floor} — mitigation: specify the fallback when independent agents are unavailable.

46. [HIGH] "they run in SEPARATE agents — never one agent doing both" — a mandatory multi-agent requirement with no fallback for a reader who has only one agent available. — cells: {CX-floor} — mitigation: provide a single-agent fallback or make multi-agent availability an explicit precondition.

47. [HIGH] "Claude-runtime cells are fresh subagents." — "Claude-runtime" and the procedure for producing a fresh subagent are never defined, so the dispatch step is unexecutable from this file alone. — cells: {CX-floor} — mitigation: define the runtime and the dispatch mechanism, or link a self-contained procedure.

---

## MED

48. [MED] "it belongs in the mechanical check battery from day one" — a definite-article artifact with no path, and it is unclear whether "a script" and "the mechanical check battery" are one destination or two; "day one" is also undefined. — cells: {CH-good, CH-floor, CX-good, CX-floor} — mitigation: give the battery's path on first use and say whether it differs from "a script".

49. [MED] "that is a code-review skill's job, not this one's" — an indefinite pointer: the reader is told where not to go but not which skill to use instead. — cells: {CH-good, CH-floor, CX-good, CX-floor} (CX-good flagged uncertain — the sentence still suffices to reject the task even if it cannot route it) — mitigation: name or link the intended code-review skill.

50. [MED] "name: d-review" — a cryptic one-letter abbreviation never expanded, which the file's own naming lens would flag; readers may infer design, document, or doctrine. — cells: {CH-good, CH-floor, CX-good, CX-floor} (CH-floor flagged uncertain — borderline whether a hyphenated compound counts as one word under the file's own rule) — mitigation: expand the abbreviation on first use or rename the skill descriptively.

51. [MED] "first NC run, 2026-08-03" — "NC" is an unexpanded two-letter abbreviation appearing once, ungreppable, with no linked run artifact. — cells: {CH-good, CH-floor, CX-good, CX-floor} — mitigation: expand the abbreviation on first use and link the recorded run.

52. [MED] "a pair doc (`docs/issues/<n>-<slug>.md`), a spec (`docs/cross-project/`) ... a rule page" — "pair doc", "rule page", and the `<n>-<slug>` convention are undefined project vocabulary, and the paths are relative to an unnamed root. — cells: {CH-good, CX-good, CX-floor} (CX-good flagged uncertain — may be established local vocabulary a zero-context reader cannot know) — mitigation: gloss each document category in a few words on first use and state the path root.

53. [MED] "Pick the mode by the document's nature" — no observable classification test, and a document can satisfy several branches at once (a proposed instruction file with designed mechanisms) with no precedence rule. — cells: {CH-floor, CX-good, CX-floor} — mitigation: supply observable classification tests, an ordered decision rule, and an explicit ruling for the skill-file case named in the frontmatter.

54. [MED] "The document must exist and be complete enough to judge" — the entry gate for the whole skill turns on a judgment call with no threshold, so two reviewers accept or refuse the same draft. — cells: {CH-good, CX-good, CX-floor} — mitigation: list the minimum required document elements or name who declares readiness.

55. [MED] "the single biggest source of design confusion" — an unsourced superlative in a file that cites measurements elsewhere; other candidates (missing requirements, contradictory interfaces) may dominate in a given project. — cells: {CH-good, CX-good, CX-floor} — mitigation: attribute the ranking to observed reviews or drop it.

56. [MED] "An innocent paraphrase exposes ambiguity by misreading it." — overstated causal claim, contradicted by the file's own note that a faithful paraphrase of broken text agrees with it and hides the defect; a misreading can also be paraphraser error. — cells: {CH-good, CX-good, CX-floor} (CX-floor flagged uncertain) — mitigation: soften to "often exposes", and require divergent paraphrases or textual evidence before inferring ambiguity.

57. [MED] "Does the order remove the highest live risk first? Is the highest-value piece scheduled sensibly...?" — "highest live risk", "value", "sensibly", and "buried" are judgment terms with no ranking method, so two reviewers rank differently. — cells: {CH-good, CX-good, CX-floor} — mitigation: name the ranking axis (for example probability × cost of late discovery) so rankings are reproducible.

58. [MED] "a rule that is precisely specifiable now, cheaply checkable, and false-positive-free by construction, found sitting at the discipline rung" — "precisely", "cheaply", "false-positive-free", and "the discipline rung" have no tests or definitions, and the rung implies a ladder the file never lays out. — cells: {CH-good, CX-good, CX-floor} — mitigation: define each predicate and name the enforcement levels once, or say "stated only as discipline".

59. [MED] "when the boss says 'd-review this'" — "the boss" is an undefined role carrying an invocation trigger and three calibration decisions. — cells: {CH-good, CH-floor, CX-floor} — mitigation: define the role on first use or link the role map, since it gates invocation.

60. [MED] "The review board is expected to shrink this way; only genuine judgment should stay manual." — "review board" is introduced undefined (readable as a panel of people rather than the lens list) and "genuine judgment" is subjective; cost and access can also keep mechanical checks manual. — cells: {CH-floor, CX-good, CX-floor} — mitigation: define the board and include feasibility in the migration decision.

61. [MED] "Internal inconsistency is a reliable tell of an unexamined call." — overbroad: a documented deliberate exception, a typo, a stale merge, or an incomplete edit all read as inconsistency without an unexamined decision. — cells: {CH-good, CX-good} — mitigation: present inconsistency as evidence to investigate and require confirming whether the exception is deliberate.

62. [MED] "Include a fair \"what's solid\" section — a review that only attacks gets discounted." — unconditional even for a wholly unsound document, creating pressure to manufacture praise, and it can violate an explicit findings-only or red-team contract. — cells: {CH-good, CX-good} — mitigation: make it conditional — name what is solid where anything is, and say so explicitly when nothing is.

63. [MED] "*Good* = the top model at high effort — best at cross-rule contradictions." — "top" and "best" have no source, metric, or update rule for a zero-context reader. — cells: {CX-good, CX-floor} — mitigation: name the selection authority, the evaluation criterion, and the explicit model ids.

64. [MED] "Scale to the change: a full new file or full rewrite earns all eight cells; a one-line tweak may need a single good defect-hunt." — only the two extremes are anchored; section rewrites and scattered edits fall in an unaddressed middle, and "may need" gives no escalation condition. — cells: {CH-floor, CX-floor} — mitigation: give at least one intermediate anchor and state escalation triggers for small changes.

65. [MED] "Routine re-review of long-shipped doctrine — that is a deliberate consistency sweep, not a per-change gate." — renames the activity rather than excluding it, and "routine" and "long-shipped" carry no measurable threshold. — cells: {CH-good, CX-floor} — mitigation: state the exclusion as an action and replace "long-shipped" with an observable trigger.

66. [MED] "Identify the load-bearing claims ... Those get the hardest scrutiny." — "load-bearing" rests on an unstated causal model and "hardest" names no ranking or action, so reviewers prioritize different claims. — cells: {CX-good, CX-floor} — mitigation: define load-bearing status and the specific additional scrutiny it triggers.

67. [MED] "Known limit: if the document and the reviewer are wrong the same way, no restatement detects it" — "the reviewer" may mean the first or every independent reviewer, and another restater can reject the shared error, so "no restatement" is stronger than the mechanism warrants. — cells: {CX-good, CX-floor} (CX-floor flagged uncertain) — mitigation: name the specific reviewer and scope the detection limit as a risk rather than an impossibility.

68. [MED] "A load-bearing claim resting on first-principles reasoning ... needs an empirical probe, not assumption." — the trigger rests on two judgment calls, and an authoritative contract or formal semantics can establish the behavior without a probe. — cells: {CX-good, CX-floor} — mitigation: distinguish empirical, formal, and documented evidence tiers and give observable probe triggers.

69. [MED] "Machinery whose value does not justify its cost." — no value model, cost categories, or threshold, so two competent readers classify the same mechanism differently. — cells: {CX-good, CX-floor} — mitigation: supply the dimensions used for the value-versus-cost comparison.

70. [MED] "flag its absence even when the ceiling looks far off" — "its absence" can mean a missing bound, a missing volume estimate, a missing lifecycle rule, or missing blind-spot discussion, and "ceiling looks far off" supplies no threshold. — cells: {CX-good, CX-floor} — mitigation: name the exact missing artifact to flag and the applicability test.

71. [MED] "seventeen findings under an adversarial-literal prompt against two under a charitable one" — the target document, prompts, models, controls, and run artifact are all absent, so "measured" and "by wording alone" cannot be checked. — cells: {CX-good, CX-floor} — mitigation: link the experiment and identify the controlled variables.

72. [MED] "before its content gets expensive: a finished design before anything is built from it, doctrine before it binds readers" — "gets expensive", "finished", and "binds readers" name no observable transition. — cells: {CX-good, CX-floor} (CX-good flagged uncertain — may be motivational rather than procedural) — mitigation: state the concrete lifecycle point at which review is expected.

73. [MED] "flag it here, where the rename is still free" — renames already carry discussion, link, and coordination cost, a name may be contract-bound before build, and a design-only term may never reach code. — cells: {CX-good, CX-floor} (CX-good flagged uncertain — "free" may be deliberate hyperbole) — mitigation: replace "free" with a scoped comparative cost claim and require checking existing dependencies.

74. [MED] "Write the findings: severity-tagged, most consequential first" — severity order and consequence order can disagree (a MED on the core mechanism against a HIGH on the periphery), and no tiebreak is given. — cells: {CH-good, CX-floor} — mitigation: state the ordering rule, for example severity first with ties broken by consequence.

75. [MED] "End with one line: sound · sound-with-named-risks · not-ready-because-X." — the three verdicts have no decision criteria and "X" is an unglossed placeholder, so the same evidence yields different verdicts. — cells: {CH-good, CX-floor} — mitigation: define each verdict's threshold and gloss X as the single blocking reason.

76. [MED] "belongs upstream in the authoring skill that keeps producing it" — "the authoring skill" and "upstream" are named with no identifier or location a reader could act on. — cells: {CH-floor, CX-floor} — mitigation: name the authoring skill and the destination artifact.

77. [MED] "five cells over a ~120-line skill returned 109 raw flags" — five cells fits neither the four-cell nor eight-cell matrix, and the ~120-line document is unidentified (this file is far shorter), so the statistic cannot be interpreted or reproduced. — cells: {CH-good, CH-floor} — mitigation: name the five cells and the document, or state that the run predates the current matrix.

78. [MED] "a fact that is true by construction — one whose falsity would make the mechanism itself pointless" — "true by construction" and "pointless" are subjective assessments with no test separating them from a genuine unvalidated runtime claim. — cells: {CH-floor, CX-floor} — mitigation: define the qualifying invariants and give one worked example on each side of the boundary.

79. [MED] "*Floor* = the mid tier a framework auto-assigns ... the lowest tier that actually reads the file" — two definitions in one sentence (an external default and a capability threshold) that need not select the same model. — cells: {CH-good} — mitigation: adopt the capability threshold as the definition and cite the auto-assigned default only as the current instance.

80. [MED] Step 4 ("Verify every falsifiable claim") versus the Mode 2 section — the file never says whether steps 1, 2, and 4 still apply inside Mode 2, though it explicitly supersedes step 5. — cells: {CH-floor} (flagged uncertain — inference from silence, not a stated conflict) — mitigation: state explicitly which steps survive into Mode 2 alongside the matrix.

81. [MED] "No single reviewer walks all eleven inside one context." — a hard-coded count in the same paragraph that predicts lenses will migrate out, so it goes false on the file's own trajectory. — cells: {CH-good} — mitigation: write "the full lens set" instead of a literal count.

82. [MED] "never a full re-run of the matrix" (Mode 1) versus "**The matrix:** {restate, defect-hunt} × ..." (Mode 2) — "the matrix" denotes the eleven-lens set in one section and the cell grid in another, with the undefined use coming first. — cells: {CH-good} — mitigation: call the Mode 1 object "the lens set" and reserve "matrix" for the Mode 2 cell grid.

83. [MED] "The tier-to-model mapping sits at the top of the script, one place to update" — the same sentence's parenthetical restates the mapping in prose, so there are two places and the prose goes stale while carrying a "live-verified" stamp. — cells: {CH-good} — mitigation: drop the ids from the prose or mark them a non-authoritative snapshot with the script as the single source.

84. [MED] "report a finding you are unsure about, tagged LOW with the uncertainty stated" — conflates confidence with consequence, forcing a high-consequence unconfirmed finding down next to typo-grade items where the reader's filter drops it. — cells: {CH-good} — mitigation: keep severity for consequence and add a separate confidence marker such as HIGH (unconfirmed).

85. [MED] "a severity (HIGH / MED / LOW)" — the scale is required in three places and defined nowhere, so the ordering rule and cross-cell dedupe are incomparable between reviewers. — cells: {CH-good} — mitigation: define the three levels in one line each where the scale is introduced.

86. [MED] "A self-review of one's own text has blind spots — the author has already rationalized the weak parts." — the stated rationale for independent passes does not apply when the reviewer is never the author, letting a reader conclude the fan-out is unnecessary. — cells: {CH-good} — mitigation: give the independence rationale that survives third-party review (single-reader blind spots, single-context anchoring).

87. [MED] "a proposal not yet built gets the soundness checklist" — the trichotomy is gated on build status, so a design for a partly-built system falls into no branch. — cells: {CH-good} — mitigation: re-gate the branch on document type rather than build status and say what happens to partially-built designs.

88. [MED] "is unexecutable by a zero-context reader" — "zero context" is never scoped, so under the widest reading every project-specific noun becomes a flag and real defects are buried. — cells: {CH-good} — mitigation: define the reader (no project history, but access to the repo and linked files) so the predicate is decidable.

89. [MED] "Restate, in your own words, exactly what each sentence's words say." — "in your own words" requires rephrasing while "exactly what each sentence's words say" can require verbatim repetition. — cells: {CX-floor} — mitigation: distinguish exact meaning from exact wording in the prompt.

90. [MED] "which a sympathetic reader silently repairs and never reports" — a universal claim about reader behavior; a sympathetic reader can report the defect precisely because they had to repair it. — cells: {CX-floor} — mitigation: remove the universal and state it as the common failure mode.

91. [MED] "*unnecessary tracked state* ... a *compensating mechanism* — machinery papering over a gap that a simpler primitive would eliminate outright" — both smells rest on unstated counterfactuals ("would obviate", "would eliminate"). — cells: {CX-floor} — mitigation: require the reviewer to name the proposed simpler mechanism and its demonstrated tradeoff.

92. [MED] "Include a fair \"what's solid\" section — a review that only attacks gets discounted." — "fair" and "gets discounted" depend on an unidentified evaluator and standard. — cells: {CX-floor} — mitigation: state an objective inclusion rule or mark the section as optional guidance.

93. [MED] "Use when a document is about to be built from or landed" — "about to" has no observable threshold, so the invocation trigger cannot be applied consistently. — cells: {CX-floor} — mitigation: define a concrete lifecycle trigger.

94. [MED] "that is a deliberate consistency sweep, not a per-change gate" — the consistency-sweep process is named without a procedure, owner, or location. — cells: {CH-floor} — mitigation: name the sweep process and where it is documented.

95. [MED] "the certain-and-cheaply-checkable kind" and "repeats identically across reviews" — neither the recurrence threshold nor the checkability standard has a test. — cells: {CX-floor} — mitigation: define the recurrence threshold and the checkability criterion.

96. [MED] "Dispatch fresh-context subagents against the same document; they hold no investment in the design." — freshness and absence of investment are asserted, not guaranteed; a subagent can inherit history, framing, or generated context. — cells: {CX-good} — mitigation: define the actual context-isolation mechanism.

97. [MED] "*Good* = the top model at high effort" and "*Floor* = the mid tier..." — the tier names "good", "floor", and "cells" are dictionary words that fail the file's own greppability rule and share no family token. — cells: {CH-good, CH-floor} (CH-floor flagged uncertain — the naming lens may be scoped to names the reviewer introduces, not the skill's own vocabulary) — mitigation: rename to a shared-token family such as `review-tier-top` / `review-tier-floor`, or note explicitly that the names are grandfathered and why.

---

## LOW

98. [LOW] "Identify the load-bearing claims: the statements the design depends on being true." — the definition presumes a design, so it has no object when step 1 is applied to a doctrine file under Mode 2. — cells: {CH-good} — mitigation: add the doctrine-file form of the definition in the same sentence.

99. [LOW] "A divergence between your written understanding and the document's words is a finding" — step 2 compares understanding against the words while pass 1 compares paraphrase against intent; the two tests catch different defects. — cells: {CH-good} — mitigation: use one comparator vocabulary across both sections.

100. [LOW] "a written-out model of the boundary would have collided with it immediately" — an unfalsifiable counterfactual about a review that never happened, sitting next to the concession that shared error defeats restatement. — cells: {CH-good} — mitigation: soften to "is the kind of check that collides with this class of sentence".

101. [LOW] "The fixed checklists below keep the review consistent" — "fixed" reads as literal immutability, contradicted by the planned lens migration and the scale-to-the-change rule. — cells: {CH-good} — mitigation: say "the checklists below" or "a stable checklist".

102. [LOW] "that is exactly where designs lie to themselves" — figurative personification in an otherwise literal instruction; a document cannot lie. — cells: {CH-good} — mitigation: state the mechanism plainly — authors label intended state as existing state.

103. [LOW] "before anything is built from it or it lands" — admits a second parse ("built from (it or it lands)") on a fast read. — cells: {CH-good} — mitigation: write "before anything is built from it, and before it lands".

104. [LOW] "The path to the document — a pair doc ..., a spec ..., a skill file, CLAUDE.md, a rule page." — a verbless fragment, so whether this is a required input or an illustrative list is left to inference. — cells: {CH-floor} — mitigation: add a predicate, for example "Input: the path to the document...".

105. [LOW] "Anything labeled as existing that is only designed or proposed (or the reverse) — the single biggest source..." — a verbless fragment; the instruction is recoverable only from the following sentence. — cells: {CH-floor} — mitigation: rewrite as a complete imperative sentence.

106. [LOW] "an issue number always rides with a descriptive handle" — phrased as a factual absolute about prose in general, which is false; the intent is prescriptive. — cells: {CH-floor} (flagged uncertain — clearly meant prescriptively in context) — mitigation: write it as a rule ("must always ride with").

107. [LOW] "that is a create-design task, owned separately" — "create-design task" may be a named workflow or plain description, and no owner is identified. — cells: {CX-good} (flagged uncertain) — mitigation: link the workflow or describe it generically and name the owner.

108. [LOW] "The fixed checklists below keep the review consistent instead of mood-dependent." — checklists reduce variation but cannot ensure consistency across reviewers, so "keep" overclaims. — cells: {CX-good} (flagged uncertain — "keep" may be intended loosely) — mitigation: qualify the claimed effect.

109. [LOW] "the author has already rationalized the weak parts" — an overgeneralization about author psychology; an author may simply not have noticed a newly introduced defect. — cells: {CX-good} (flagged uncertain — may be rhetorical motivation) — mitigation: phrase it as a risk rather than a universal author state.

110. [LOW] "a concrete mitigation — never a vague concern" — "concrete" and "vague" have no operational test. — cells: {CX-good} (flagged uncertain — examples elsewhere may establish a local convention) — mitigation: give one acceptable and one unacceptable finding example.

---

## Counts

- claude-hunt-good.md: 52 raw findings
- claude-hunt-floor.md: 21 raw findings
- codex-hunt-good.md: 60 raw findings
- codex-hunt-floor.md: 58 raw findings
- Raw total: 191
- Distinct after dedupe: 110 (HIGH 47, MED 50, LOW 13)
