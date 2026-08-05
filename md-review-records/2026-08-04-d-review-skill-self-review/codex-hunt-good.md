<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=defect-hunt tier=good target=.claude/skills/d-review/SKILL.md -->

1. > `name: d-review`

   Defect class: introduced NAME that is not self-documenting. `d` could mean design, document, doctrine, defect, or delegated; the rest of the name does not resolve which meaning applies. External invocations must already know the name rather than being able to infer it. It is greppable once known, but not self-explanatory. Confidence: sure.

2. > Use when a document is about to be built from or landed, or when the boss says "d-review this" — his ask wins over the exclusions.

   Defect classes: undefined reference, judgment-based conditional, and incompatible readings. The file never identifies “the boss” or explains how a zero-context agent recognizes that person. “Wins over the exclusions” can mean overriding only the two immediately preceding exclusions, or overriding every exclusion and prerequisite in the description, including “The document must already exist” and “never co-writes it.” Those readings produce different behavior when the named person asks for code review, implementation review, co-writing, or review of a nonexistent draft. Confidence: sure.

3. > **Review never creates — a finding explains, it does not prescribe (boss-ruled 2026-08-04):** a finding makes the defect fully understood — exactly what is wrong, under what conditions it does harm, and why — completely enough that the author can fix it without asking the reviewer anything.

   Defect classes: conflict and overbroad absolute. Lens 5 later requires, “The finding names the simpler mechanism that suffices,” which introduces an alternative mechanism and therefore prescribes design content under the ordinary meaning of “prescribe.” The absolute “never” leaves no way to reconcile those instructions. The sentence also claims that explanation can always leave the author with no questions; a defect caused by missing product intent or an undocumented external constraint can be completely characterized while still leaving the author needing information from someone else. Confidence: sure.

4. > Pick the mode by what the document IS, not by the state of the system around it: a design nothing has been built from yet gets the soundness checklist; a doctrine or instruction file gets the clarity review; a document that is both — doctrine carrying designed mechanisms — gets both, in separate passes.

   Defect class: self-contradiction. The sentence forbids choosing by system state, then defines the design case using exactly such a state: whether anything has been built from the document. The two literal procedures disagree when the same design document is reviewed before and after partial implementation. Confidence: sure.

5. > A divergence between your written understanding and the document's words is a finding — after ruling out that you simply misread clear text: either the document permitted your misreading, or your correct model contradicts it.

   Defect classes: unexecutable certainty requirement and false dichotomy. “Ruling out” an ordinary reviewer mistake has no observable test here. A third case remains possible: the document is clear, but the reviewer misread it and mistakenly believes the error has been ruled out. The later admission that a document and reviewer can be wrong together does not cover this reviewer-only error. Following the sentence turns an undetected reading mistake into a document finding. Confidence: sure.

6. > A live specimen of the cost of skipping this: a review once passed the confidently false sentence "uncommitted work has no copy outside the conversation" — a written-out model of the boundary collides with that class of sentence, since on this project's runtime, files on disk survive session restarts.

   Defect class: zero-context dependency. “This project’s runtime” is not identified, defined, or referenced by path, and “session restarts” is not tied to a named runtime operation. A reader cannot determine whether the claim applies to Claude, Codex, another execution environment, every kind of restart, or only a particular launcher. The claimed counterexample therefore cannot reliably govern another review. Confidence: sure.

7. > Every finding names the specific location and explains the defect to fix-ready depth — what is wrong, when it does harm, why — never a vague concern, never a proposed fix, and **never a severity or importance rating** (boss-ruled 2026-08-04): a reviewer without context cannot rate importance, and an out-of-context rating anchors every later reader.

   Defect classes: internal conflict and overbroad absolutes. Step 6 later says the invoker “assigns each finding’s severity,” orders findings by severity, and labels findings HIGH, MED, or LOW. “Every finding” and “never a severity” can mean either raw cell findings only or all findings including the synthesized report; the sentence does not make that distinction. “Every later reader” is also literally false: a reader who does not see the rating, deliberately ignores it, or reaches an independent judgment is an ordinary counterexample. Confidence: sure.

8. > When checking would be hard, laborious, or impossible, do not attempt it — mark the claim *unverified*, and let that label feed lens 7's measured-or-believed judgment; the label is the deliverable.

   Defect class: judgment-based conditional. “Hard” and “laborious” have no observable threshold, time budget, command budget, or resource limit. Two readers can classify the same ten-minute check differently and consequently either verify it or stop. The harm occurs precisely on consequential claims near that undefined boundary. Confidence: sure.

9. > Exhaustive mechanical checking belongs to code when it is worth doing at all, never to a reviewer's afternoon.

   Defect classes: overbroad absolute and judgment-based conditional. A small finite document with three links is an ordinary counterexample: a reviewer can exhaustively check all three manually in less time than building or locating automation. “When it is worth doing” supplies no observable predicate. Literal obedience can prevent a cheap, complete check while offering no executable way to decide whether automation is worthwhile. Confidence: sure.

10. > Dispatch fresh subagents against the same document, spawned with nothing but the task (no session context rides along), on each available runtime.

    Defect classes: impossible control over another agent’s internal state, undefined scope, and open-set enumeration. The invoker can choose a task payload but cannot guarantee that system instructions, checkout instructions, runtime defaults, tool descriptions, retained state, or framework-provided context do not “ride along.” “Available runtime” is not defined here and has no enumeration procedure; later prose discusses Claude and Codex but does not say whether those exhaust the set. The instruction therefore cannot be verified as completed. Confidence: sure.

11. > Name what is solid where anything is — and say plainly when nothing is.

    Defect classes: judgment-based conditional and unbounded negative determination. “Solid” has no observable criterion, while saying that “nothing” is solid requires ruling out every part of the document. Readers can disagree about partial evidence, an unverified claim, or a correct but underspecified mechanism. The sentence can force an unjustified all-clear or all-unsound statement. Confidence: sure.

12. > End with one line: sound · sound-with-named-risks · not-ready-because-X, where X is the single blocking reason.

    Defect class: wrong when obeyed literally. A document can have two independent blocking reasons—for example, an impossible runtime assumption and a contradictory safety rule. Requiring “the single” reason forces one blocker out of the conclusion even though neither subsumes the other. Confidence: sure.

13. > **A re-review always reads the whole document (boss-ruled 2026-08-04)** — design defects are global, and an edit collides with unedited text as often as with itself (measured: several of the first full-grid run's catches were changed-versus-unchanged conflicts).

    Defect classes: overbroad absolute and unexplained evidence reference. A generated, corrupted, unexpectedly enormous, or composite document makes whole-file rereading unreasonable even when a bounded changed section is reviewable. “Always” provides no exception or stop rule. “The first full-grid run” is not identified by a file or record path in this sentence, so its measurement is difficult for the minimal reader to locate or evaluate. Confidence: sure.

14. > What scales with revision size is the reviewer count, never the text scope: a light revision may earn a single good-tier pass over the full document plus verification of each prior finding's fix; a heavy revision earns the full grid.

    Defect classes: overbroad absolute, impossible scaling requirement, and judgment-based conditionals. Reviewer count cannot necessarily scale when the number of available agents is fixed. A large file with a one-line revision is an ordinary case where text scope, not reviewer count, may be the practical variable. “Light” and “heavy” have no observable thresholds, so the choice between one pass and the full grid can vary by reader. Confidence: sure.

15. > The reviewable unit is the whole file — and doctrine and design files stay small and atomic partly so that whole-file review stays practical.

    Defect class: unsupported universal assumption. Nothing in the file constrains doctrine or design files to remain small or atomic. A long existing instruction file, a generated specification, or a file combining inherited sections violates the premise while still satisfying the stated input type. Literal reliance on this assertion leaves no procedure for such a target. Confidence: sure.

16. > Demand probes for genuine unknowns; stake level is not the discriminator.

    Defect class: judgment-based condition. “Genuine unknown” has no observable test and depends on what the reviewer believes, what evidence they happened to find, and how they interpret “by construction.” Two reviewers can demand different probes from the same claim without either violating a stated predicate. Confidence: sure.

17. > Anything labeled as existing that is only designed or proposed (or the reverse) is flagged — the biggest source of design confusion we have observed.

    Defect class: incompatible classification. “The reverse” can mean either something labeled proposed that already exists, or any existing artifact discussed prospectively. The former is a status-label mismatch; the latter would flag ordinary proposed changes to an existing mechanism. The sentence does not constrain the reversal to the label itself. Confidence: unsure because “or the reverse” conventionally suggests the narrower symmetric reading, but the literal broader reading remains available.

18. > Verify each label against ground truth (step 4).

    Defect class: conflict. Step 4 explicitly says not to attempt checks that are hard, laborious, or impossible and to mark those claims unverified. “Verify each” requires a settled result for every label; “mark unverified” permits some labels to remain unsettled. A label whose status depends on inaccessible production state cannot satisfy both instructions. Confidence: sure.

19. > Every load-bearing rule in a design is backed by something: an enforcement point (a gate, a check, a tool boundary) or a written instruction agents follow.

    Defect classes: false exhaustive claim and overbroad absolute. A design can contain an aspirational rule backed by nothing, a rule established by a platform guarantee, a human approval process, a legal constraint, or a convention outside those two categories. An unbacked rule is especially relevant to this lens, yet the sentence asserts that case cannot exist. Literal classification can hide the very absence of backing that review ought to expose. Confidence: sure.

20. > The review checks that the document says which, truthfully: a claimed mechanism must actually exist (lens 2 verifies it), and a written instruction must be labeled as what it is.

    Defect class: conflict. Lens 2 expressly permits honest `NEW` or proposed mechanisms that do not yet exist. This sentence says any claimed mechanism “must actually exist,” which would reject an accurately labeled future mechanism. It also says lens 2 verifies existence despite step 4 allowing an unverified result. Confidence: sure.

21. > Re-evaluating that split — "this prompt rule should be code," or the reverse — is a different problem set, out of this review's scope (boss-ruled 2026-08-04; the question lives per-candidate on [the what-can-code-check issue, nedschorus#42](https://github.com/nedschorus/nedschorus/issues/42)) — unless the code-versus-prompts choice is itself the subject of the document or section under review, in which case it is reviewed like any other design decision.

    Defect class: judgment-based conditional. Whether the choice is “itself the subject” is not an observable predicate. A section may discuss enforcement architecture without explicitly announcing that its subject is code-versus-prompts; one reader will review the split while another will exclude it. The boundary controls whether a potentially central design decision is examined. Confidence: sure.

22. > For each mechanism, walk the state space systematically: actor states (busy, idle, mid-turn, dead), dependency failures (the file it reads, the tool it runs, the channel it writes), concurrency (two sessions, re-entry, repeated firing) — and require the document to name or explicitly discard the reachable, consequential cells.

    Defect classes: unbounded enumeration and judgment-based conditions. “Repeated firing” admits arbitrarily many repetitions, concurrency can produce an open-ended interleaving space, and dependencies can fail in unenumerated combinations. There is no abstraction level or stop rule. “Reachable” and “consequential” also depend on a system model the zero-context reader may not possess. Literal completion can require an unlimited state-space analysis. Confidence: sure.

23. > A reachable, relevant omission is a finding even when the happy path is flawless — the best catches live in cells the design's own story never visits.

    Defect class: judgment-based condition. “Relevant” has no observable criterion, and “reachable” may depend on undocumented runtime behavior. Two readers can identify the same omitted case but disagree whether this sentence requires a finding. The harm is inconsistent coverage at precisely the omitted boundaries the lens is meant to govern. Confidence: sure.

24. > Machinery whose value does not justify its cost.

    Defect class: unexecutable judgment criterion. No kinds of value, kinds of cost, comparison method, or decision threshold are supplied. The fragment can classify the same mechanism as necessary or over-complex solely from reviewer preference. Confidence: sure.

25. > The finding names the simpler mechanism that suffices — not as a proposal, but as the evidence that the machinery is over-complex.

    Defect classes: self-contradiction and conflict. Naming a different mechanism that should replace or obviate the reviewed machinery is an alternative design proposal under the ordinary meaning of “proposal”; declaring that it is “not” one does not change the act. It conflicts with “Review never creates,” “a finding … does not prescribe,” and “never a proposed fix.” Literal obedience requires both proposing and not proposing the same mechanism. Confidence: sure.

26. > The document contradicting itself, its own stated principles, or the project's recorded rulings — the governing plan documents and issue bodies, which the lens agent is given alongside the document.

    Defect classes: zero-context dependency and unbounded external set. The file does not identify the governing plan documents or issue bodies, provide their paths, define who selects them, or bound “the project’s recorded rulings.” A reader given only this file and the target cannot know whether the supplied set is complete. Calling external-ruling conflicts “Internal consistency” also supports two scopes: consistency internal to the document versus consistency with selected project records. Confidence: sure.

27. > Internal inconsistency is strong evidence of an unexamined call; confirm the exception is not deliberate before flagging.

    Defect classes: impossible knowledge requirement and judgment-based condition. An agent cannot confirm the absence of deliberate author intent from text that does not record that intent. Silence supports both an accidental contradiction and an intentional but undocumented exception. Literal obedience can suppress every such finding unless the agent obtains access to the author’s internal state. Confidence: sure.

28. > Each load-bearing mechanism is measured (probe, canary, field observation), guaranteed (by definition or an authoritative contract — lens 1's by-construction class), or merely believed.

    Defect class: incompatible readings. The `or` can define mutually exclusive statuses or merely list nonexclusive evidence types. A mechanism can be measured in one environment, contractually guaranteed for another boundary, and still believed to work end to end; it can also be partially measured. The subsequent rule “Believed plus load-bearing” behaves differently depending on whether “believed” is an exclusive lowest status or a belief that can coexist with evidence. Confidence: sure.

29. > Does the order remove the highest live risk first — ranked by probability times the cost of late discovery?

    Defect classes: current-world dependency and judgment-based condition. The file provides neither probabilities nor costs, and “live risk” requires current system state. Multiplying unstated estimates does not produce an observable ranking. Different reviewers can identify different “highest” risks while each follows the sentence. Confidence: sure.

30. > Is the highest-value piece scheduled sensibly or buried behind lower-value work?

    Defect class: judgment-based condition. “Value,” “sensibly,” “buried,” and “lower-value” have no defined measures. The sentence offers no literal criterion for deciding whether a dependency-first schedule is sensible preparation or improper burial. Confidence: sure.

31. > Potentially unbounded data the design accumulates needs a stated bound — retention, archival, or the project's artifact-lifecycle rule that every accumulating store has a named home and a drain — plus a rough volume expectation.

    Defect classes: undefined reference, judgment-based condition, and wrong examples. “The project’s artifact-lifecycle rule” has no explicit path or definition in the permitted context. “Potentially unbounded” has no threshold. Retention and archival do not necessarily establish a bound: an archive that never deletes data remains unbounded, and a retention policy without a maximum duration or volume may also remain unbounded. Literal obedience can accept an accumulating archive as the required bound. Confidence: sure.

32. > Unbounded growth with correctness-only thinking is a default blind spot; flag the missing bound even when the ceiling looks far off.

    Defect class: judgment-based conditional. “Looks far off” supplies no measurable horizon, rate, capacity, or time interval. A reviewer cannot tell when this clause applies, and different guesses about future growth produce different findings. Confidence: sure.

33. > A plan that maps the design's own cells is necessary but, unless it includes generative techniques (fuzzing, property tests), only exercises what the design thought of.

    Defect class: overbroad absolute. A manually authored adversarial test, a regression test from an external failure, or a test imported from another implementation can exercise something the design did not anticipate without using fuzzing or property tests. “Only” makes the absence of generative techniques conclusive when it is not. Confidence: sure.

34. > Where the designed thing has an executable surface, require a second, adversarial layer — load, scale, "what did we not anticipate" — that does not assume the design is right.

    Defect classes: unbounded work and overbroad requirement. “What did we not anticipate” describes an open set with no stopping condition; completing it would require knowing the unknown cases. Load and scale testing are not meaningful for every executable surface—for example, a finite one-time schema check—yet the sentence requires the layer whenever any executable surface exists. Confidence: sure.

35. > Every in-scope name must be self-documenting and greppable: full words a search matches verbatim, one shared token across a family of related names, no cryptic abbreviations, no bare sequence labels, and no bare numeric issue references in prose (the number must ride with a descriptive handle).

    Defect classes: overbroad absolute, judgment-based predicates, and conflict. “Self-documenting,” “cryptic,” and “related” have no observable tests. The next sentence says domain-standard tokens such as `SHA-256` pass, although `SHA` is not a full word, so “full words” is not universally required. A family can also use established ecosystem names that lack one shared token while remaining searchable. Confidence: sure.

36. > A one-word name is a finding candidate by default when the word is generic or collides in context (`parser`, `data`, `manager`); domain-standard tokens (`README`, `checksum`, `SHA-256`) pass.

    Defect class: judgment-based conditional. “Generic,” “collides in context,” and “domain-standard” have no defined corpus or observable threshold. `parser` may be fully specific in a parser-only package but generic in a compiler suite; the sentence gives no way to settle that boundary. Confidence: sure.

37. > A longer precise name beats a short ambiguous one, and ease of typing is not a constraint.

    Defect class: overbroad claim. Ease of typing is an ordinary constraint for frequently invoked CLI commands, public APIs, accessibility needs, platform path-length limits, or interfaces where users must enter the name manually. Literal obedience forbids considering that real constraint even when it materially affects the designed interface. Confidence: sure.

38. > Two pass types, and **they run in SEPARATE agents — never one agent doing both**: a single agent doing one task first is primed for the second (a defect-hunt frame makes its restatement adversarial; a restatement frame makes its hunt post-hoc).

    Defect classes: overbroad absolute and unexecutable procedure. Unlike Mode 1, Mode 2 supplies no degraded behavior when subagents are unavailable. A single-agent runtime therefore cannot perform the clarity review at all. “Never” also excludes isolated fresh sessions of the same agent implementation even when no conversational state carries between them, while the stated reason concerns priming rather than identity. Confidence: sure.

39. > **A confusion flag is never dismissed as the reviewer's ignorance (boss-ruled 2026-08-04):** the reviewer's guaranteed context is the instruction floor plus the document, so a concept that confused them was missing from both — the remedy is one of three, chosen at triage: define it in the file, add the explicit path reference, or promote the definition to the instruction floor when many files share the concept.

    Defect classes: invalid inference, overbroad absolute, false exhaustive list, and judgment-based condition. A reviewer can overlook an existing definition, misparse clear text, fail to follow a reference, or lack the capability to understand a correctly defined concept; guaranteed access to context does not guarantee correct use of it. Thus confusion does not prove the concept was missing. The three remedies are not exhaustive because the confusion may arise from reviewer error, contradictory wording, a mistaken name, or an unnecessary concept. “When many files share” also has no defined count. Confidence: sure.

40. > Each flag quotes the sentence, gives the readings or the conflict, and where the defect class permits, a case where obeying the words does the wrong thing — the what, when, and why of the defect, explained to fix-ready depth, with no proposed fix and no severity rating; the cell states only its own confidence.

    Defect class: judgment-based conditional. “Where the defect class permits” gives no mapping from defect classes to required counterexample cases. Two cells can treat the same ambiguity differently, with one supplying a case and the other deciding the class does not permit one. Confidence: sure.

41. > Every tier-to-model assignment is an operator-set pinned value — the boss picks the models; agents apply the pinned picks and never substitute their own sense of the model landscape, which is months stale by construction (boss-ruled 2026-08-04).

    Defect classes: undefined actor, conflict with the referenced script, and overbroad claim. “The boss” and “operator-set” have no executable identification procedure. The referenced script exposes `--model`, documented as overriding the tier mapping, without constraining that option to the operator; therefore “never substitute” and the callable interface support different behaviors. “Months stale by construction” is false for an agent with freshly supplied model metadata or live authoritative tooling. Confidence: sure.

42. > Claude-runtime cells are fresh subagents — good = the pinned top model at high effort, floor = the pinned floor model (Sonnet-class today), set per launch.

    Defect classes: missing execution data and current-world dependency. No explicit path contains the Claude model pins, exact model IDs, effort values, or launch procedure. “Top model,” “floor model,” “Sonnet-class,” and “today” require current model-landscape knowledge that the file elsewhere says agents must not supply themselves. A zero-context invoker cannot construct the required cells from this sentence. Confidence: sure.

43. > **The matrix:** {restate, defect-hunt} × {good, floor} × {each available runtime} — with both runtimes available, as today, eight cells.

    Defect classes: undefined/open set and unstable current-world claim. “Each available runtime” has no enumeration rule, while “both runtimes” assumes the set consists of exactly Claude and Codex. If a third runtime is callable, or one named runtime is installed but unusable, the first and second clauses yield different matrix sizes. “As today” also becomes stale without changing the file. Confidence: sure.

44. > *Good* is best at cross-rule contradictions.

    Defect class: unsupported and temporally unstable superlative. “Best” has no comparison set, measurement, record reference, or effective date. It can mean better than Floor, better than every model, or the best use of that tier. Model changes can invalidate the claim while the instruction continues to route work by it. Confidence: sure.

45. > *Floor* is defined by capability — the lowest tier that actually reads the file, not the lowest tier that exists (a below-floor model flags mostly its own capability gaps); the framework's subagent default is the current instance.

    Defect classes: unbounded current-world comparison, incompatible definition, and undefined references. Determining the lowest existing tier requires knowing and testing an open, changing model set. “Actually reads” is a per-run behavior, not a stable model property. It conflicts with the earlier operator-pinned Floor and “Sonnet-class today.” “The framework” and “current instance” are also not identified, so the last clause cannot select a model. Confidence: sure.

46. > The full grid runs every time, and every cell reads the whole document.

    Defect class: overbroad absolutes. A runtime outage, context-limit failure, process error, unreadable target, or unavailable agent is an ordinary counterexample. The referenced script expressly permits nonzero execution failure, so the file itself demonstrates that a cell may not run or read the document. The sentence gives no distinction between attempting every cell and successfully completing every cell. Confidence: sure.

47. > (The clarity cells run on today's runtimes; a Codex *wrapper of this skill* — the runtime-parity question — is separate and arrives at companion admission.)

    Defect classes: unexplained reference and unstable future claim. “Companion admission” is neither defined nor linked by path, and “arrives” does not identify an actor, artifact, event, or observable completion condition. A reader cannot know what work is excluded now or when that exclusion ends. Confidence: sure.

48. > The templates are the most leveraged text in the whole process — criticize them freely, in reviews and out of them; land changes deliberately (the context-holder rules on each, ideally micro-tested), never as silent drift (boss-ruled 2026-08-04).

    Defect classes: undefined role and undefined procedure. “The context-holder” is not explicitly identified with the invoker, author, operator, or boss. “Rules on each” can mean approves each change, adjudicates each criticism, or establishes rules for each template. “Micro-tested” has no test definition, procedure, evidence location, or stop condition, while “deliberately” is a judgment rather than an observable predicate. Confidence: sure.

49. > First a **merge agent** — independent, one job, zero judgment — folds all cell reports into ONE file: hunt findings deduped (the same sentence flagged with the same complaint is one entry, all catching cells listed; the same sentence with different complaints stays adjacent entries), nothing dropped or filtered, uncertainty wording preserved verbatim, ordered by **document position — never by any cell's opinion or rating**: report order pollutes the author's judgment as their context fills, and document order is the one ordering that carries nobody's; it also puts every complaint about a passage in one place.

    Defect classes: self-contradictory capability demand and incompatible requirements. Determining whether complaints are “the same,” whether they are different, which document position controls a cross-sentence conflict, and how restatements align requires semantic judgment. That contradicts “zero judgment.” Deduplication necessarily removes duplicate report instances, while “nothing dropped” and “uncertainty wording preserved verbatim” require retaining them; listing catching cells does not preserve each duplicate’s wording. Confidence: sure.

50. > **Every review preserves its record** — the merged cell-attributed findings, the triage dispositions, and every cell's output, each file stamped with its provenance: runtime, exact model id, effort level, cell, tier (boss-required 2026-08-04 — tier names drift across model eras; pins do not; the Codex cell script stamps its own, Claude cell files are stamped when saved) — as a dated directory under `d-review-records/`, the data for the future which-cells-earn-their-keep analysis.

    Defect classes: literal impossibility, overbroad absolute, and introduced non-self-documenting NAME. A merged report and triage-disposition file aggregate multiple cells and therefore do not have one truthful runtime, model ID, effort, cell, or tier, yet “each file” requires all five fields. Failed or interrupted reviews are ordinary counterexamples to “Every review preserves” every output. `d-review-records` inherits the unexplained `d-review` abbreviation and is not self-documenting without prior knowledge of that name. Confidence: sure.

51. > The **author** compares restatements against intent — no one else holds the intended meaning, and a comparator without it watches a faithful paraphrase of broken text agree with the text and misses the defect.

    Defect class: overbroad absolute. Coauthors, decision-makers, recorded requirements, prior approved documents, or an operator who commissioned the text can also hold intended meaning. A comparator without private intent can still detect contradictions, impossibilities, undefined terms, and divergence from a cited governing contract. “No one else” and “misses the defect” make claims broader than those ordinary cases permit. Confidence: sure.

52. > The two roles never mix: the cells generate the findings (the author never reviews their own text — that is step 5's warning), and the author, who holds the intent, takes the notes and rewrites — that is what review notes are for.

    Defect classes: internal conflict and overbroad absolutes. The preceding sentence requires the author to compare restatements against intent; the restatement-pass section says that the resulting divergence is a finding. The author therefore participates in determining at least those findings while this sentence says cells generate the findings and the author “never reviews.” Step 6 also assigns the context-holding invoker evaluative synthesis work. The roles cannot remain literally unmixed under the described procedure. Confidence: sure.

53. > A bad rewrite is caught by the next review round, not by restricting the author.

    Defect class: impossible guarantee. A later review can miss a defect, repeat the author’s assumption, fail to run, or lack the context needed to recognize the regression. The file itself acknowledges that a document and reviewer can be wrong in the same way. “Is caught” promises an outcome the process cannot control. Confidence: sure.

54. > Code correctness, or an implementation reviewed against its design — a code-review skill's lane (the review-change candidate owns it when built), not this one's.

    Defect classes: unexplained external NAME and incompatible scope reading. “The review-change candidate” appears to name a future skill or artifact, but no path, invocation name, issue, or definition identifies it. It is difficult to find by search because “candidate” does not establish the eventual external name. This exclusion also conflicts with the frontmatter reading in which the boss’s request overrides all exclusions. Confidence: sure.

55. > Routine re-review of long-shipped doctrine — run a deliberate consistency sweep instead; this skill gates changes, not the archive.

    Defect classes: judgment-based conditions and undefined procedure. “Routine,” “long-shipped,” and “deliberate” have no observable thresholds. “Consistency sweep” is neither defined nor referenced by path, so the excluded reader is told to invoke a procedure they cannot locate or execute. The harm occurs at the boundary between a recent doctrine change and archival maintenance, where different readers will choose different processes. Confidence: sure.

clean sections: none
