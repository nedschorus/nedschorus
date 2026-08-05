<!-- provenance: runtime=codex model=gpt-5.6-terra effort=xhigh cell=restate tier=floor target=.claude/skills/d-review/SKILL.md -->

## YAML frontmatter

1. The skill is named `d-review`.

2. This skill performs an adversarial review of an already-written design, specification, or doctrine document before anyone builds from it or incorporates it into the project.

3. Eligible documents include design-pair documents, architecture specifications, skill files, and changes to `CLAUDE.md` or rules.

4. The target document must pre-exist; the skill evaluates that document rather than helping write it.

5. The skill has two modes: a proposal-oriented soundness checklist that looks for the listed design failures, and a doctrine/instruction-oriented, sentence-by-sentence clarity review that uses isolated paraphrases and literal adversarial reading across different capability tiers and runtimes.

6. The skill does not review whether code is correct, nor whether an implementation matches its design.

7. Use the skill when a document will soon be built from or landed, or when “the boss” explicitly requests `d-review`; such an explicit request overrides the stated exclusions.

## Design review (d-review)

1. Review a completed written design before implementation makes its contents costly to change, and review doctrine before it becomes binding on readers.

2. The document being reviewed must already exist and contain enough material to assess; reviewing means evaluating the written artifact, never jointly authoring it.

3. Review does not create anything: a finding explains a defect but does not tell the author what to build or change.

4. A finding must make the defect fully understandable by specifying what is wrong, the circumstances in which it causes harm, and why it causes harm, with enough completeness that the author need not ask the reviewer follow-up questions before fixing it.

5. Choosing or designing the remedy belongs to the author; a reviewer who proposes an alternative design has stopped doing review and started a separately owned create-design task.

6. Even a coherent-seeming design can contain untested assumptions, mistake a planned thing for an existing thing, depend on agent obedience for a guarantee that must bear load, or omit failure cases without saying so; these defects are much cheaper to repair in the document than after implementation.

7. A deployed instruction file instead fails when a sentence is ambiguous, contradictory, or false if obeyed literally, because a sympathetic reader may silently repair the sentence and normally will not report the problem.

8. The fixed checklists are intended to make reviews consistent rather than dependent on the reviewer’s mood.

## Input and mode choice

1. The required input is a repository-relative path to the document, such as a design-pair document under `docs/issues/<n>-<slug>.md`, a cross-project specification under `docs/cross-project/`, a skill file, `CLAUDE.md`, or a rules page.

2. If the requester provides no document target, ask which document is to be reviewed.

3. Select the review mode based on what the document itself is, rather than the surrounding system’s current state: use the soundness checklist for an unimplemented design, the clarity review for doctrine or instructions, and both modes as separate passes when doctrine also describes designed mechanisms.

## Steps

1. Steps 1 through 4 and step 6 apply to both review modes, while mode 2 satisfies step 5 through its clarity matrix.

2. Step 1 requires reading the entire document rather than skimming it.

3. Step 1 requires identifying the claims on which the design depends being true, because those claims receive the most intense scrutiny.

4. Step 2 requires writing down the reviewer’s understanding of every mechanism, rule, and load-bearing claim before looking for defects.

5. That written understanding must spell out edge behavior, boundary conditions, exclusions, and effects on nearby state as precisely as the document allows; genuinely unresolved matters must be recorded as gaps rather than guessed into existence.

6. If the reviewer’s written understanding diverges from the document’s wording, that divergence is a finding after first excluding the possibility that the reviewer merely misunderstood unambiguous text; either the wording allowed the misunderstanding or the reviewer’s correct model conflicts with the document.

7. The cited example says a prior review accepted the false statement that uncommitted work has no copy outside the conversation, whereas an explicit model of the boundary would conflict with that statement because this project’s runtime preserves on-disk files across session restarts.

8. Restatement cannot reliably reveal a defect when both the document and reviewer share the same mistaken belief; step 4 and independent passes are meant to address that limit.

9. In mode 2, this preparation is done on the invoker’s side, while delegated restatement cells independently paraphrase the document without being given that preparation.

10. Step 3 requires running the checklist for the selected mode.

11. Every finding must identify its exact location and explain what is wrong, when it harms something, and why; it must not be vague, propose a remedy, or include a severity or importance rating.

12. A cell may report only its own confidence: either that it is sure, or that it is unsure and why.

13. Report uncertain observations with their uncertainty stated rather than suppressing them; deciding what to filter out belongs to synthesis.

14. Step 4 means cheaply checking only load-bearing claims and labeling the remainder, rather than trying to verify everything.

15. If one command or one file read can settle a load-bearing claim—such as whether a cited file exists, a quotation matches, or a commit landed—the reviewer must check it, because designs often misstate their own existence labels; the backup script believed to run but whose output directory had no commits is the supplied example.

16. If checking a load-bearing claim would be difficult, labor-intensive, or impossible, do not attempt the check; mark the claim as unverified so that lens 7 can distinguish measured knowledge from belief.

17. Exhaustive mechanical verification belongs in code when worthwhile, not in a reviewer’s afternoon.

18. Step 5 requires obtaining independent review passes.

19. A reader fixed in one context can miss what fresh readers see, and authors are especially poor reviewers of their own text because they have already rationalized its weak points.

20. Send fresh subagents the same document and only the task, without session context, on every available runtime.

21. For a doctrine file, the clarity-review matrix below fulfills the independent-pass requirement.

22. Step 6 requires writing the findings.

23. Only the invoker—the agent with the full context—assigns finding severity at this point: HIGH means literal compliance produces a materially costly wrong result; MED means competent readers would behave differently; LOW means friction from which readers will probably recover.

24. A finding that is not confirmed but would have high consequences is labeled HIGH (unconfirmed), rather than being hidden.

25. Order findings by severity and then by consequence, explain each to fix-ready depth, identify sound material when some exists, and state directly when nothing is sound.

26. Finish with exactly one of the stated outcome forms: `sound`, `sound-with-named-risks`, or `not-ready-because-X`, where `X` is the one blocking reason.

## Mode 1 — the design-soundness checklist

1. The lenses are intended to fan out to focused agents, with one agent per lens or related lens group; the invoker chooses any grouping and gives each agent the document and its question.

2. When delegation is available, no one reviewer may cover the entire lens set in a single context; if there is no subagent facility, one reviewer may perform the lenses serially as the accepted degraded mode.

3. Every re-review must reread the entire document because design defects are global and edits often conflict with untouched text; the stated measurement is that several catches in the first full-grid run were changed-versus-unchanged conflicts.

4. Revision size changes the number of reviewers, never the amount of text read: a light revision can receive one good-tier full-document pass plus checks that prior findings were fixed, while a heavy revision receives the whole grid.

5. The whole file is the unit of review, and doctrine and design files should remain small and atomic partly so whole-file review remains feasible.

6. Lens 1 concerns load-bearing claims about runtime boundaries that have not been validated.

7. A load-bearing runtime-behavior claim—such as what loads, hook order, or what a session can see—requires an empirical probe or an authoritative behavioral contract, rather than first-principles assumption.

8. Do not demand a probe for a fact that is true by construction, meaning that it follows from the artifact’s own definition and denying it would make the mechanism pointless.

9. Require probes for real unknowns; the claim’s stake level does not determine whether a probe is required.

10. Lens 2 concerns honest distinction between things that already exist and things that are new or proposed.

11. Flag anything described as existing when it is only designed or proposed, and flag the reverse mislabeling as well.

12. Verify every such existence label against reality through step 4.

13. Lens 3 concerns whether the document truthfully states what backs each rule.

14. Every load-bearing design rule is backed either by an enforcement point, such as a gate, check, or tool boundary, or by a written instruction agents are expected to follow.

15. Check that the document truthfully identifies which kind of backing applies: a purported mechanism must actually exist, as lens 2 checks, and a written instruction must be labeled as a written instruction.

16. The defect to report is a claim that agent discipline is enforcement, because it falsely describes how the rule is backed.

17. A design may freely decide which requirements become code and which remain written instructions; those choices are ordinary design decisions.

18. Deciding that a given prompt rule should instead become code, or the reverse, is outside this review’s scope and belongs to the separately cited what-can-code-check issue.

19. If the code-versus-prompts choice itself is the subject of the reviewed document or section, review that choice like any other design decision.

20. Lens 4 concerns omissions and silently dropped cases, and requires enumeration rather than relying on memory.

21. For each mechanism, systematically consider actor states, dependency failures, and concurrency—including busy, idle, mid-turn, and dead actors; failed files, tools, and channels; and two sessions, re-entry, and repeated firing—and require the document to name or explicitly discard each reachable consequential case.

22. The enumeration is a reviewer aid and does not require the document itself to contain a transcript of every examined case.

23. An omitted reachable and relevant case is a finding even when the happy path is perfect, because important defects often lie outside the design’s own narrative.

24. Lens 5 concerns over-complexity and asks what can be removed.

25. The relevant problem is machinery whose benefit does not justify its cost.

26. Two named over-complexity smells are unnecessary tracked state, which a state-agnostic mechanism could avoid maintaining, and a compensating mechanism, which papers over a gap that a simpler primitive could eliminate.

27. An over-complexity finding identifies the simpler mechanism that is sufficient, not as a recommended redesign but as evidence that the existing machinery is overly complex.

28. Lens 6 concerns internal consistency.

29. It looks for a document contradicting itself, its own principles, or recorded project rulings in governing plan documents and issue bodies supplied to the lens agent.

30. Internal inconsistency strongly suggests an unexamined decision, but the reviewer must confirm that it is not a deliberate exception before reporting it.

31. Lens 7 concerns the grounding for reliability.

32. Every load-bearing mechanism must be classified as measured through a probe, canary, or field observation; guaranteed by definition or authoritative contract; or merely believed.

33. A merely believed load-bearing mechanism is a named risk until it is measured.

34. Lens 8 concerns whether the build order is sensible.

35. Ask whether the implementation order removes the greatest live risk first, where risk is probability multiplied by the cost of discovering it late.

36. Ask whether the highest-value component is scheduled sensibly instead of being placed behind lower-value work.

37. Lens 9 concerns scale and growth.

38. Any potentially unbounded accumulated data needs both a stated bound—retention, archival, or a project artifact-lifecycle rule giving every accumulating store a named home and drain—and a rough expected volume.

39. Flag a missing bound even if the limit appears distant, because treating growth only as a correctness concern is a common blind spot.

40. Lens 10 concerns a test plan that is both cooperative and adversarial.

41. A test plan that covers the design’s own cases is necessary, but unless it includes generative techniques such as fuzzing or property testing, it covers only what the design anticipated.

42. When the design has an executable surface, require another adversarial testing layer—such as load, scale, or unanticipated-case testing—that does not assume the design is correct.

43. Lens 11 concerns names.

44. For this lens, a name is an identifier used outside the document to find or invoke something, including file and directory names, script/function/command names, skill names, issue and test labels, and defined terms other documents cite.

45. Ordinary prose, one-off words, and local labels defined at their point of use, including a tier scheme or severity scale, are not names for this lens and are outside its scope.

46. Every in-scope name must be self-documenting and searchable: it must use full words that a search matches exactly, share a token with related names, avoid cryptic abbreviations and bare sequence labels, and avoid bare numeric issue references in prose by pairing each number with a descriptive handle.

47. Almost every genuinely self-documenting name is expected to be two to five words; a generic or context-colliding one-word name such as `parser`, `data`, or `manager` is presumptively a finding candidate, while domain-standard tokens such as `README`, `checksum`, and `SHA-256` are acceptable.

48. Prefer a longer precise name to a short ambiguous one; ease of typing does not constrain the choice.

49. Flag bad names in the design because they will spread into code, tests, and doctrine, where renaming becomes more expensive.

## Mode 2 — the clarity review (doctrine and instruction files)

1. The relevant failure is at the sentence level: either a reader cannot obey a sentence without guessing, or different readers obey it in different ways.

2. The two pass types must be run by separate agents, never by one agent doing both, because performing one task first primes that agent for the other: defect hunting makes a later restatement adversarial, and restating makes a later hunt post-hoc.

3. The restatement pass is intended to be innocent and give the text no charitable repair.

4. A restatement cell’s prompt contains only the paraphrase template and target path, with no review framing.

5. The paraphrase itself is not the finding; the finding is a divergence between that paraphrase and the intended meaning.

6. An innocent paraphrase can expose ambiguity by reading the sentence differently from its intended meaning.

7. The defect-hunt pass is adversarial and literal.

8. A different agent must be asked to find every sentence that contradicts itself, conflicts with another sentence, permits incompatible readings, causes wrong behavior when literally obeyed, cannot be executed by a zero-context reader, or demands work an agent cannot reasonably finish.

9. Here, a zero-context reader has only the checkout’s instruction file—`CLAUDE.md` or `AGENTS.md`—the reviewed document, and files that document explicitly names by path; it has no project history.

10. Unreasonably completable work includes unbounded verification or enumeration, knowledge of the present world beyond training, control over another agent’s internal state, and labor with no stopping rule.

11. The inability-to-complete category is only a candidate filter rather than conclusive proof, because agents can misjudge other agents’ abilities; the invoker decides which such flags are genuine overreach.

12. A reviewer’s confusion may not be dismissed as mere ignorance: the reviewer is guaranteed only the instruction floor and the document, so a concept that confused it was absent from both.

13. At triage, the response to such a missing concept must be one of three choices: define it in the file, add an explicit path to its definition, or promote the definition to the instruction floor if many files use it.

14. Also flag absolutes broader than their ordinary counterexample permits, and conditionals whose condition requires judgment rather than an observable predicate.

15. Every flag must quote the problematic sentence, state the possible readings or contradiction, and, when that defect type permits it, provide a case in which literal obedience produces the wrong result; it must explain what, when, and why to fix-ready depth, offer no remedy or severity rating, and report only the cell’s own confidence.

## Running the cells

1. Every mapping from tier to model is a pinned value chosen by the operator set: the boss selects the models, and agents apply those choices without replacing them based on their own supposedly current knowledge of models, which is inherently months stale.

2. Claude-runtime cells are fresh subagents: the good tier is the pinned top model at high effort, while the floor tier is the pinned floor model, presently Sonnet-class, and both choices are set for each launch.

3. Codex-runtime cells are run through `scripts/d-review-codex-cell.py`, once per cell, using `--cell restate|defect-hunt --tier good|floor --target <path>`, headless `codex exec`, a read-only sandbox, and the cell’s final message as standard output.

4. The templates under `prompts/` are the sole prompt source for cells on both runtimes, so wording improvements affect both legs in one place.

5. The script’s top section authoritatively defines the tier-to-model mapping and tier reasoning efforts; prose model IDs are only snapshots, and the recorded current mapping is `gpt-5.6-sol` and `gpt-5.6-terra` at `xhigh`, boss-selected and live-verified on 2026-08-03, pinned so a cell does not depend on local Codex configuration.

## The matrix

1. The matrix consists of each combination of restatement versus defect hunt, good versus floor tier, and every available runtime; with the two currently available runtimes, that produces eight cells.

2. The good tier is considered especially capable of finding contradictions between rules.

3. The floor tier is determined by capability: it is the lowest tier that can actually read the file, rather than the lowest tier that exists, because a model below that threshold mostly reports its own limits; the framework’s current instance is the default subagent.

4. Run the complete grid every time, and have every cell read the entire document.

5. Whether any cells can be pruned must be decided from data—specifically, analysis of which cell findings survive context-aware triage over many preserved reviews—not from doctrine.

6. The clarity cells run on the currently available runtimes, while a Codex wrapper for this skill is a separate runtime-parity issue that comes at companion admission.

## The prompt is the lever

1. A legacy doctrine-file review produced seventeen findings with an adversarial-literal prompt and two with a charitable prompt that silently repaired the defects being sought.

2. Require literal reading, prohibit charity, and keep the restatement template free of review framing.

3. The templates are described as the most leveraged text in the process; they may be criticized both within and outside reviews, but changes must be landed deliberately under the context holder’s decision, ideally with micro-tests, rather than drifting silently.

## Synthesize — two roles, strictly split

1. There are two strictly separate synthesis roles.

2. First, an independent merge agent with one task and no judgment combines all cell reports into one file: it deduplicates identical sentence-and-complaint hunt findings while listing every catching cell, keeps different complaints about the same sentence as adjacent entries, drops and filters nothing, preserves uncertainty wording exactly, and orders content by document position rather than a cell’s view or rating, because report order can bias an author as context accumulates whereas document order carries no one’s judgment and groups complaints about each passage.

3. The merge agent places restatement reports alongside the text by section so their divergences are next to the passages from which they diverge.

4. Then the author, who has full context, reads that single merged file, assigns severities only at step 6, and plans the second pass; cells supply observations rather than importance, because the cited first full-grid run’s cell-applied “47 HIGH” labels framed initial triage.

5. Every review must preserve its record in a dated directory under `d-review-records/`: merged findings with cell attribution, triage dispositions, and each cell’s output, with every file stamped with runtime, exact model ID, effort, cell, and tier provenance; this data supports later analysis of which cells are worthwhile, and Codex records its own provenance while Claude files are stamped when saved.

6. Deduplicate across cells because heavy overlap is expected; the supplied observations are that a five-cell pass over about 120 lines yielded 109 raw flags and about 35 distinct flags, while the first full grid yielded 191 raw and 110 distinct flags.

7. Only the author compares restatements with intended meaning, because no other role possesses that intended meaning and a comparator lacking it could see a faithful paraphrase of broken text agree with the text and miss the defect.

8. The roles must never merge: cells create findings and the author does not review their own text, while the author receives the notes and rewrites; this is the stated purpose of review notes.

9. A bad rewrite is to be detected in the next review round, not prevented by limiting the author’s freedom to rewrite.

10. After that process, write findings according to step 6.

## When NOT to use

1. Do not use this skill for code correctness or for comparing an implementation to its design; those belong to a code-review skill, with the review-change candidate owning that work after the implementation exists.

2. Do not use this skill for routine re-review of long-shipped doctrine; perform a deliberate consistency sweep instead, because this skill gates changes rather than maintaining the archive.
