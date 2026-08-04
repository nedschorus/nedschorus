<!-- provenance: runtime=codex model=gpt-5.6-terra effort=xhigh cell=defect-hunt tier=floor target=.claude/skills/d-review/SKILL.md -->

1. Quote: `name: d-review`

   Defect class: name.

   `d-review` is an externally invoked skill name, but `d` is an unexplained abbreviation. A reader looking for “design review” cannot infer this invocation name from the identifier itself. This harms discovery before the reader has already found this file.

   Confidence: sure.

2. Quote: “Use when a document is about to be built from or landed, or when the boss says "d-review this" — his ask wins over the exclusions.”

   Defect class: undefined authority.

   “The boss” and “his” are not defined in the file, the checkout has no instruction file defining them, and no explicit path resolves them. A zero-context reader cannot tell whether this means the repository owner, the current user, a manager, or another agent, so cannot determine whose request overrides the stated exclusions.

   Confidence: sure.

3. Quote: “Pick the mode by what the document IS, not by the state of the system around it: a design nothing has been built from yet gets the soundness checklist; a doctrine or instruction file gets the clarity review; a document that is both — doctrine carrying designed mechanisms — gets both, in separate passes.”

   Defect class: self-contradiction; judgment-call conditional.

   It says mode must not depend on system state, then defines the design case by whether “nothing has been built from yet,” which is system state. A document with unchanged text moves between modes when implementation begins. “Doctrine carrying designed mechanisms” also supplies no observable test for when both passes are required, so two readers can choose different scopes.

   Confidence: sure.

4. Quote: “Every finding names the specific location and explains the defect to fix-ready depth — what is wrong, when it does harm, why — never a vague concern, never a proposed fix, and **never a severity or importance rating** (boss-ruled 2026-08-04): a reviewer without context cannot rate importance, and an out-of-context rating anchors every later reader.”

   Defect class: conflict with another sentence; overbroad absolute.

   This conflicts with step 6: “The invoker … assigns each finding's severity here.” Both address findings, and the file never defines a distinct object to which one rule applies but the other does not. The explanatory claims are also too broad: a reader can rate an explicitly described consequence, and a later reader can disregard a rating. The conflict can make an executor either omit the mandated severity or violate the prohibition.

   Confidence: sure.

5. Quote: “When checking would be hard, laborious, or impossible, do not attempt it — mark the claim *unverified*, and let that label feed lens 7's measured-or-believed judgment; the label is the deliverable.”

   Defect class: judgment-call conditional.

   “Hard” and “laborious” have no observable threshold. The same verification can be treated as a short task by one reviewer and laborious by another, producing different work and different evidence labels. The file supplies no stopping rule or standard for resolving that divergence.

   Confidence: sure.

6. Quote: “Exhaustive mechanical checking belongs to code when it is worth doing at all, never to a reviewer's afternoon.”

   Defect class: overbroad absolute.

   A finite document whose only load-bearing claims are, for example, a small closed list of file references can be exhaustively checked quickly by a reviewer; it need not “belong to code.” The word “never” therefore directs the wrong behavior for ordinary finite verification cases.

   Confidence: sure.

7. Quote: “Dispatch fresh subagents against the same document, spawned with nothing but the task (no session context rides along), on each available runtime.”

   Defect class: unexecutable procedure; undefined term.

   The file neither identifies the available runtimes nor supplies a way to enumerate them. It also requires control over another agent’s inherited context, which the invoking agent may not control. A reader cannot know when every runtime has been covered or verify the “nothing but the task” condition.

   Confidence: sure.

8. Quote: “The invoker — the one agent holding full context — assigns each finding's severity here, and only here: HIGH = following the words does the wrong thing and the wrongness costs something real; MED = competent readers diverge; LOW = friction, likely recovered.”

   Defect class: conflict with another sentence; judgment-call conditional.

   It conflicts with the earlier prohibition on every severity rating. It also makes severity depend on “costs something real,” “competent readers,” and “likely recovered,” none of which has an observable standard. The later synthesis assigns severity to “the author” with full context, but the file never establishes whether that author is the invoker; if not, two roles are directed to perform the same exclusive act.

   Confidence: sure.

9. Quote: “End with one line: sound · sound-with-named-risks · not-ready-because-X, where X is the single blocking reason.”

   Defect class: wrong when obeyed literally.

   A review can have two independent blocking defects. Requiring a single `X` forces the reviewer either to omit a blocker or falsely imply that resolving one makes the document ready. The sentence provides no rule for a multi-blocker result.

   Confidence: sure.

10. Quote: “No single reviewer walks the full lens set inside one context when delegation is available; with no subagent facility, one reviewer working the lenses serially is the accepted degraded mode.”

   Defect class: undefined conditional; overbroad absolute.

   “Delegation is available” is not an observable predicate: a platform can expose subagents while policy, capacity, target sensitivity, or a user instruction prohibits using them. The absolute prohibition then conflicts with the actual available authority, and no fallback covers that case.

   Confidence: sure.

11. Quote: “**A re-review always reads the whole document (boss-ruled 2026-08-04)** — design defects are global, and an edit collides with unedited text as often as with itself…”

   Defect class: unbounded labor; overbroad absolute.

   The skill sets no maximum document size or accessible-text requirement. A very large design document makes a whole-document reread potentially unreasonable or impossible within an agent’s context and time limits. The claim that collisions occur “as often” is also unsupported by the cited observation and cannot justify the universal “always.”

   Confidence: sure.

12. Quote: “What scales with revision size is the reviewer count, never the text scope: a light revision may earn a single good-tier pass over the full document plus verification of each prior finding's fix; a heavy revision earns the full grid.”

   Defect class: judgment-call conditional; conflict with another sentence.

   “Light” and “heavy” revisions are undefined, so the prescribed reviewer count is not reproducible. “Verification of each prior finding's fix” conflicts with step 4’s direction not to attempt hard verification and instead mark it unverified. “Good-tier” is not defined for the design-soundness mode at this point, either.

   Confidence: sure.

13. Quote: “Demand probes for genuine unknowns; stake level is not the discriminator.”

   Defect class: judgment-call conditional.

   The file gives no observable test for a “genuine unknown.” A reviewer must make the very epistemic judgment that the sentence treats as the gate for required work, so different reviewers can demand or omit probes for the same claim.

   Confidence: sure.

14. Quote: “Verify each label against ground truth (step 4).”

   Defect class: conflict with another sentence.

   This requires verification of every EXISTS/NEW label, while step 4 says not to attempt checking that is hard, laborious, or impossible. A hard-to-check label cannot both be verified and left unattempted with an `unverified` label.

   Confidence: sure.

15. Quote: “Re-evaluating that split — "this prompt rule should be code," or the reverse — is a different problem set, out of this review's scope … unless the code-versus-prompts choice is itself the subject of the document or section under review, in which case it is reviewed like any other design decision.”

   Defect class: judgment-call conditional.

   The file does not define what makes a choice “the subject” of a document or section. A document can mention the choice, depend on it, or frame it as background; readers can reasonably reach different scope decisions in those cases.

   Confidence: sure.

16. Quote: “For each mechanism, walk the state space systematically: actor states … dependency failures … concurrency … and require the document to name or explicitly discard the reachable, consequential cells.”

   Defect class: unbounded enumeration; judgment-call conditional.

   Mechanism state spaces can be open-ended, especially when dependency failures, retries, inputs, and concurrent sessions combine. “Reachable” and “consequential” have no decision procedure. Saying the enumeration need not appear as a transcript does not bound the reviewer’s required private enumeration, so the task has no stop rule.

   Confidence: sure.

17. Quote: “The finding names the simpler mechanism that suffices — not as a proposal, but as the evidence that the machinery is over-complex.”

   Defect class: conflict with another sentence.

   It directs the reviewer to identify a replacement mechanism that “suffices.” That is a proposed alternative design in substance, despite the file’s earlier rule: “Review never creates” and “Designing the fix belongs to the author.” Calling the alternative evidence rather than a proposal does not change what the reviewer must supply.

   Confidence: sure.

18. Quote: “The document contradicting itself, its own stated principles, or the project's recorded rulings — the governing plan documents and issue bodies, which the lens agent is given alongside the document.”

   Defect class: unexplained reference; unexecutable procedure.

   No governing plan documents or issue bodies are named or linked. The stated minimal context does not include them, and no procedure says who supplies them or how to identify the governing subset. A zero-context lens agent cannot perform this comparison.

   Confidence: sure.

19. Quote: “Internal inconsistency is strong evidence of an unexamined call; confirm the exception is not deliberate before flagging.”

   Defect class: demands inaccessible knowledge.

   Whether an apparent exception is deliberate can depend on an author’s unrecorded intent. The file gives no artifact, authority, or stop rule for confirmation. Literal compliance therefore requires access to another person’s internal state or blocks reporting an otherwise visible contradiction.

   Confidence: sure.

20. Quote: “Each load-bearing mechanism is measured (probe, canary, field observation), guaranteed (by definition or an authoritative contract — lens 1's by-construction class), or merely believed.”

   Defect class: incomplete and incompatible classification.

   A mechanism can be partly measured and partly contract-guaranteed, or its basis can be unknown because step 4 marked the claim unverified. Those cases fit neither a single exclusive category nor “merely believed.” The classification is used to determine review output, so different readers must guess how to classify mixed evidence.

   Confidence: sure.

21. Quote: “Believed plus load-bearing is a named risk until measured.”

   Defect class: wrong when obeyed literally.

   The preceding sentence recognizes that an authoritative contract or definition can establish a guarantee. A believed claim can therefore cease to be merely believed by obtaining such a guarantee without being measured. “Until measured” falsely excludes that stated path.

   Confidence: sure.

22. Quote: “Does the order remove the highest live risk first — ranked by probability times the cost of late discovery? Is the highest-value piece scheduled sensibly or buried behind lower-value work?”

   Defect class: judgment-call conditional; required current-world knowledge.

   “Live risk,” probability, cost, value, and “sensibly” are not defined or sourced. Ranking requires present project facts the document may not contain, yet the lens provides no evidence standard or way to stop when those facts are unavailable.

   Confidence: sure.

23. Quote: “Potentially unbounded data the design accumulates needs a stated bound — retention, archival, or the project's artifact-lifecycle rule that every accumulating store has a named home and a drain — plus a rough volume expectation.”

   Defect class: unexplained reference; judgment-call conditional.

   The “project's artifact-lifecycle rule” has no path or definition, despite being a possible compliance route. “Potentially unbounded,” “named home and a drain,” and “rough volume expectation” have no observable thresholds. A reviewer cannot reliably decide whether the rule applies or what satisfies the requirement.

   Confidence: sure.

24. Quote: “A plan that maps the design's own cells is necessary but, unless it includes generative techniques (fuzzing, property tests), only exercises what the design thought of.”

   Defect class: wrong when obeyed literally.

   Non-generative tests can exercise behavior not anticipated by the design: regression tests can come from prior incidents, external contracts, production traces, or adversarial examples. The sentence’s “only” makes generative techniques the sole exception and misclassifies those ordinary cases.

   Confidence: sure.

25. Quote: “Where the designed thing has an executable surface, require a second, adversarial layer — load, scale, "what did we not anticipate" — that does not assume the design is right.”

   Defect class: unbounded labor.

   “What did we not anticipate” is an open set, and the sentence gives no bounded test method, coverage target, or completion criterion for the adversarial layer. A reviewer can neither know when this requirement has been met nor distinguish a reasonable test plan from an endlessly expandable one.

   Confidence: sure.

26. Quote: “Every in-scope name must be self-documenting and greppable: full words a search matches verbatim, one shared token across a family of related names, no cryptic abbreviations, no bare sequence labels…”

   Defect class: judgment-call conditional; overbroad absolute.

   “Self-documenting,” “cryptic,” and what counts as a related family are not observable predicates. The universal also fails for established externally required identifiers: a design may have to cite a vendor command, protocol token, API name, or compatibility path whose spelling cannot be replaced with full words. The rule does not distinguish names being introduced from names that must be referenced accurately.

   Confidence: sure.

27. Quote: “Two pass types, and **they run in SEPARATE agents — never one agent doing both**…”

   Defect class: overbroad absolute.

   An isolated runtime may provide only one agent slot while still permit separate fresh turns or independent processes. The sentence treats that ordinary constrained case as forbidden rather than defining a degraded mode, even though Mode 1 explicitly provides one for absent delegation.

   Confidence: unsure — the intended meaning may be that independently launched cells count as separate agents even when initiated by one coordinator.

28. Quote: “The finding is not the paraphrase — it is the **divergence** between the paraphrase and the intended meaning.”

   Defect class: unexecutable by the stated actor.

   The restatement cell is given only a target path and a paraphrase template, while the intended meaning is not supplied to it. The sentence can mean either that the cell must detect divergence, which is impossible from its input, or that another unspecified actor must do so. Later text assigns comparison to the author, but this sentence does not identify that actor.

   Confidence: sure.

29. Quote: “**A confusion flag is never dismissed as the reviewer's ignorance …:** the reviewer's guaranteed context is the instruction floor plus the document, so a concept that confused them was missing from both…”

   Defect class: wrong when obeyed literally; undefined term.

   “Instruction floor” is not defined or located. More importantly, confusion does not prove absence: a reviewer can overlook, misread, or lack the capability to understand a definition that is present in the file or an explicitly referenced file. The rule converts those ordinary reviewer failures into document defects.

   Confidence: sure.

30. Quote: “the remedy is one of three, chosen at triage: define it in the file, add the explicit path reference, or promote the definition to the instruction floor when many files share the concept.”

   Defect class: false exhaustive choice; judgment-call conditional.

   The listed actions exclude ordinary outcomes such as removing an unnecessary concept, replacing it with ordinary language, or preserving a definition already adequately available. Determining whether “many files” share a concept also has no repository boundary or count, so the condition is not observable.

   Confidence: sure.

31. Quote: “Every tier-to-model assignment is an operator-set pinned value — the boss picks the models; agents apply the pinned picks and never substitute their own sense of the model landscape…”

   Defect class: undefined authority and terminology.

   “Operator-set,” “pinned,” “the boss,” and “model landscape” are not defined as executable concepts. The Codex script supplies one mapping, but there is no corresponding authority or location for Claude selections. A zero-context reader cannot know who sets an absent or stale pin, nor when a pin is authoritative.

   Confidence: sure.

32. Quote: “Claude-runtime cells are fresh subagents — good = the pinned top model at high effort, floor = the pinned floor model (Sonnet-class today), set per launch.”

   Defect class: unexplained reference; name.

   “Claude-runtime,” “fresh subagents,” “pinned top model,” “Sonnet-class,” and “set per launch” do not identify a launcher, a configuration file, or an executable procedure. `Sonnet-class` is an externally meaningful model identifier/class but is not self-documenting enough to select an exact model. The date-relative “today” also requires current-world knowledge that the file does not provide.

   Confidence: sure.

33. Quote: “The templates in [`prompts/`](prompts/) are the single prompt source for BOTH runtimes' cells — one place to improve wording for both legs.”

   Defect class: unsupported guarantee.

   The referenced Codex wrapper reads these templates, but nothing in the file or wrapper controls how Claude subagents are launched or proves they receive the same text. Literal reliance on this sentence can therefore produce divergent prompts while the reviewer assumes a common source.

   Confidence: sure.

34. Quote: “The tier-to-model mapping and per-tier reasoning effort sit at the top of the script (authoritative; any ids quoted in prose are a snapshot), currently `gpt-5.6-sol` / `gpt-5.6-terra` at `xhigh`…”

   Defect class: names.

   `gpt-5.6-sol` and `gpt-5.6-terra` are command-invoked model identifiers, yet `sol` and `terra` do not describe the models’ role or capability. `xhigh` is likewise an externally consumed effort identifier without a self-contained meaning. These identifiers can be found by exact string after a reader knows them, but are not discoverable from the semantic terms “good,” “floor,” or “high effort.”

   Confidence: unsure — the script’s exact mapping makes these usable once found, but does not make the identifiers themselves self-documenting.

35. Quote: “**The matrix:** {restate, defect-hunt} × {good, floor} × {each available runtime} — with both runtimes available, as today, eight cells.”

   Defect class: required current-world knowledge; undefined conditional.

   The file does not define the set of available runtimes or an observation that establishes availability. “As today” is time-dependent. A reader cannot know whether eight cells are required, whether a newly available runtime expands the matrix, or whether an unavailable one must be retried.

   Confidence: sure.

36. Quote: “*Floor* is defined by capability — the lowest tier that actually reads the file, not the lowest tier that exists…”

   Defect class: unexecutable criterion; unexplained reference.

   Whether a model “actually reads” a file is an internal-state claim the coordinator cannot directly verify. The sentence provides no test or threshold. It also says “the framework's subagent default is the current instance,” but never names the framework or defines “current instance,” so the claimed default cannot be located.

   Confidence: sure.

37. Quote: “The full grid runs every time, and every cell reads the whole document.”

   Defect class: unbounded labor; overbroad absolute.

   The rule has no exception for a document too large for a cell’s context window, unavailable runtimes, failed cells, or an explicitly constrained review. It therefore demands work an agent may not reasonably be able to complete and gives no valid completion state for those cases.

   Confidence: sure.

38. Quote: “Pruning cells is a data question — which cells' findings survive context-aware triage, over tens of preserved reviews — decided by analysis of the records below, never by doctrine…”

   Defect class: undefined procedure; overbroad absolute.

   “Context-aware triage,” “tens,” and the analysis method are undefined; the record directory contains prior outputs, not a decision rule. “Never by doctrine” also fails when a governing policy requires a runtime or independent pass regardless of empirical yield. The sentence leaves no way to determine when pruning is permitted.

   Confidence: sure.

39. Quote: “The clarity cells run on today's runtimes; a Codex *wrapper of this skill* — the runtime-parity question — is separate and arrives at companion admission.”

   Defect class: undefined terms; names.

   “Codex wrapper of this skill,” “runtime-parity question,” and “companion admission” are introduced as externally meaningful concepts but are neither defined nor linked. A reader cannot find the companion process or know what event “arrives at companion admission” describes.

   Confidence: sure.

40. Quote: “The templates are the most leveraged text in the whole process — criticize them freely, in reviews and out of them; land changes deliberately (the context-holder rules on each, ideally micro-tested), never as silent drift…”

   Defect class: undefined terms; judgment-call conditional.

   “Context-holder,” “micro-tested,” “deliberately,” and “silent drift” are not operationally defined. The sentence directs changes but supplies no identifiable authority, required test, or criterion separating deliberate change from drift.

   Confidence: sure.

41. Quote: “First a **merge agent** — independent, one job, zero judgment — folds all cell reports into ONE file: hunt findings deduped…”

   Defect class: self-contradiction.

   Deduplicating requires judgment about whether reports identify the same sentence and make the same complaint; distinguishing “same” from “different complaints” is explicitly required in the following parenthetical. An agent cannot both make those classifications and exercise “zero judgment.”

   Confidence: sure.

42. Quote: “...ordered by **document position — never by any cell's opinion or rating**: report order pollutes the author's judgment as their context fills, and document order is the one ordering that carries nobody's…”

   Defect class: wrong claim; overbroad absolute.

   Document position can carry the author’s judgment: an author can front-load favored claims, defer caveats, or order content rhetorically. Thus document order is not uniquely free of anyone’s judgment. The rationale for the mandatory ordering is factually false in ordinary documents.

   Confidence: sure.

43. Quote: “The restatement reports merge alongside, aligned per section, so divergences sit next to the text they diverge about.”

   Defect class: unexecutable procedure.

   The skill accepts instruction files generally, but does not require headings or define a section for frontmatter, headingless prose, or reports whose sentence-level restatements cross a section boundary. “Aligned per section” therefore has no executable mapping for valid target documents without sections.

   Confidence: sure.

44. Quote: “**Every review preserves its record** — the merged cell-attributed findings, the triage dispositions, and every cell's output, each file stamped with its provenance…”

   Defect class: impossible requirement; overbroad absolute.

   A failed, timed-out, or unavailable cell can have no output to preserve. The instruction nevertheless requires every review to preserve every cell’s output, without defining a record for failure or a stopping condition. It demands control over external runtimes that the coordinator may not have.

   Confidence: sure.

45. Quote: “The **author** compares restatements against intent — no one else holds the intended meaning…”

   Defect class: wrong claim.

   Another coauthor, a documented acceptance criterion, or an explicitly referenced specification can hold or record intended meaning. The absolute claim improperly makes author access the only valid source and can block review where the author is unavailable but intent is documented.

   Confidence: sure.

46. Quote: “The two roles never mix: the cells generate the findings (the author never reviews their own text — that is step 5's warning), and the author, who holds the intent, takes the notes and rewrites…”

   Defect class: incompatible readings.

   “Reviews” can mean any evaluative reading, in which case it conflicts with the author’s required comparison of restatements, severity assignment, and second-pass planning. Or it can mean only generating defect findings, which is not stated. The broad wording makes the author’s required triage look prohibited.

   Confidence: sure.

47. Quote: “A bad rewrite is caught by the next review round, not by restricting the author.”

   Defect class: wrong claim.

   There may be no next round, the next review may not detect the defect, or the rewrite may be deployed before rereview. The sentence guarantees detection without any mechanism that guarantees another review or its effectiveness.

   Confidence: sure.

48. Quote: “Code correctness, or an implementation reviewed against its design — a code-review skill's lane (the review-change candidate owns it when built), not this one's.”

   Defect class: unexplained reference; name.

   “Code-review skill” and “review-change candidate” name an external workflow and owner but no identifiable skill, path, command, or definition. A reader excluded from this skill’s lane cannot locate the asserted destination for the work.

   Confidence: sure.

49. Quote: “Routine re-review of long-shipped doctrine — run a deliberate consistency sweep instead; this skill gates changes, not the archive.”

   Defect class: judgment-call conditional; unexplained procedure.

   “Routine,” “long-shipped,” “deliberate consistency sweep,” and “the archive” are undefined. A reader cannot determine whether a doctrine rereview is excluded, what procedure replaces this skill, or whether a live defect in an old file should bypass the stated gate.

   Confidence: sure.

clean sections: none


