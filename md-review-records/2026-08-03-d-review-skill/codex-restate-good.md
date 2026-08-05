## YAML frontmatter

1. The skill’s name is `d-review`.
2. It adversarially examines a written design, specification, or doctrine document before anyone builds from it or lands it; examples include a design pair document, architecture specification, skill file, `CLAUDE.md`, or rule change.
3. The document must already exist, and the skill evaluates it rather than helping write it.
4. It has two modes: a proposal-focused design-soundness checklist covering unverified assumptions, confusion between designed and built, discipline presented as enforcement, omitted failure modes, excess complexity, unlimited growth, build-order risk, and naming; and a sentence-level clarity review for doctrine and instruction files using isolated restatement and adversarial-literal passes across capability tiers and runtimes.
5. It does not review code correctness or compare an implementation with its design.
6. Use it when a document is about to be built from or landed, or when the boss requests a `d-review`.

## Design review (d-review)

1. Review a completed design before anything is built from it, or doctrine before readers become bound by it, while changes are still inexpensive.
2. The document must already exist and be complete enough for judgment; review evaluates the written artifact and does not collaborate on writing it.
3. Review produces nothing new: a finding identifies the problem and gives a one-line direction for fixing it, while the author owns the actual fix.
4. A reviewer who proposes a different design is no longer reviewing; creating that design is a separate task with separate ownership.
5. A design can appear coherent while depending on an unverified assumption, treating a design as though it were already built, relying on agent discipline for an essential guarantee, or silently omitting a failure mode; correcting those defects in the document is much cheaper than correcting them after implementation.
6. A deployed instruction file has a different kind of failure: an ambiguous, contradictory, or literally incorrect sentence that a sympathetic reader silently corrects without reporting.
7. The fixed checklists make reviews consistent instead of dependent on the reviewer’s mood.

## Input and mode choice

1. The input is the document’s path, such as a pair document at `docs/issues/<n>-<slug>.md`, a specification under `docs/cross-project/`, a skill file, `CLAUDE.md`, or a rule page.
2. If no target document is supplied, ask which document should be reviewed.
3. Choose according to the document’s type: use the soundness checklist for an unbuilt proposal, the clarity review for doctrine or instructions, and separate passes of both modes for a specification that combines doctrine with designed mechanisms.

## Steps

1. Read the entire document rather than skimming it.
2. Identify the claims on which the design depends, and scrutinize those claims most strongly.
3. Before looking for defects, write down an exact and fully detailed understanding of every mechanism, rule, and load-bearing claim, including edge behavior, boundaries, exclusions, and effects on adjacent state.
4. Any difference between that written understanding and the document’s wording is a finding: either the wording allowed the misreading, or the reviewer’s correct model conflicts with the text.
5. One review demonstrated the cost of skipping this step by accepting the false claim that uncommitted work existed only inside the conversation; explicitly modeling the boundary would have exposed the conflict because files stored on disk survive session restarts.
6. Restatement cannot detect a problem when both the document and reviewer share the same error; step 4 and the independent passes are intended to address that limitation.
7. Apply the checklist for the selected mode.
8. Every finding must identify its exact location, weakness, `HIGH`, `MED`, or `LOW` severity, and a specific mitigation rather than expressing a vague concern.
9. Favor coverage over withholding uncertain findings: report an uncertain concern as `LOW`, state the uncertainty, and leave filtering to the reader.
10. Check every falsifiable statement against ground truth.
11. Verify claims about existing artifacts, tool behavior, schema contents, or landed commits with commands such as `git`, `gh`, `grep`, or `test -f`.
12. Do not trust the document’s own labels about what exists, because designs can misrepresent their own status.
13. Obtain independent review passes.
14. Reviewing one’s own writing leaves blind spots because the author has already rationalized its weak areas.
15. Send fresh-context subagents to examine the same document because they have no investment in the design.
16. Include a reading by the companion runtime after that runtime has been admitted.
17. For doctrine files, the clarity-review matrix performs the independent-pass step.
18. Write findings in descending order of consequence, with a severity and mitigation for each.
19. Include a fair section explaining what is solid, because an exclusively hostile review will be discounted.
20. Finish with exactly one verdict line: `sound`, `sound-with-named-risks`, or `not-ready-because-X`.

## Mode 1 — the design-soundness checklist

1. Run the lenses in parallel, assigning one focused agent to each lens or lens group and giving that agent the document plus one question; the invoking agent combines the results.
2. A single reviewer must not evaluate all eleven lenses in one context.
3. After a revision, re-review only the changed sections and verify the fix for every earlier finding; do not rerun the full matrix.
4. Move repeated checks elsewhere: a check that repeats identically across reviews is certain and cheaply testable, so it belongs in a script or mechanical check battery; a defect category recurring across documents belongs in the upstream authoring skill producing it.
5. The review board should become smaller in this manner, leaving only work that requires genuine judgment.
6. A load-bearing statement derived from first-principles beliefs about runtime behavior—such as loading time, hook order, or session visibility—requires an empirical probe rather than an assumption.
7. Do not invent a probe for a fact guaranteed by construction, meaning a fact whose falsity would make the mechanism itself pointless.
8. Require probes only for actual unknowns.
9. Detect anything described as existing when it is merely designed or proposed, as well as the reverse; this is identified as the greatest source of design confusion.
10. Check every `EXISTS` or `NEW` label against ground truth and report every conflation.
11. Evaluate enforcement versus discipline from both directions, using the version sharpened through boss questioning on 2026-08-03.
12. A rule either identifies an enforcement point such as a gate, check, or tool boundary, or it presents discipline as though it were enforcement.
13. Whether the rule’s correct formulation is already known distinguishes the two sides.
14. If a rule can already be specified precisely, checked cheaply, and made free of false positives by construction, leaving it as discipline is a finding; it should enter the mechanical check battery immediately, and the review asks why it has not.
15. If a rule is still discovering its proper form, it may legitimately begin as discipline because early automation would freeze and reliably enforce a guess; in that case, confirm that the document states the concrete failure condition that will trigger conversion to code, and report the rule only if that trigger is absent or one violation would be disastrous.
16. Find missing and silently discarded cases by enumeration instead of memory.
17. For every mechanism, systematically examine each actor state—busy, idle, mid-turn, and dead—each dependency failure involving the files read, tools run, and channels written, and each concurrency case involving two sessions, re-entry, and repeated firing; require the document to mention or explicitly reject every resulting cell.
18. An omitted cell is a finding even when the happy path is perfect, and the most valuable findings commonly come from cells absent from the design’s own narrative.
19. Look for machinery whose benefit does not justify its cost and identify what can be removed.
20. Two specified warning signs are unnecessary tracked state, meaning state made unnecessary by a state-independent mechanism, and a compensating mechanism, meaning machinery covering a gap that a simpler primitive could remove entirely.
21. State what should be removed and what should replace it.
22. Check whether the document contradicts itself, its declared principles, or recent project rulings.
23. Treat internal inconsistency as a dependable indication of an unexamined decision.
24. For each essential mechanism, determine whether it has been measured through a probe, canary, or field observation, or is only believed to work.
25. Until measured, a merely believed load-bearing mechanism is an explicitly named risk.
26. Check whether the build order addresses the greatest current risk first.
27. Check whether the highest-value component is scheduled appropriately or delayed behind less valuable work.
28. Require accumulated data to have a limit through retention, archival, or the project’s rule against stateless artifact piles, along with an expected volume.
29. Treat the combination of unbounded growth and correctness-only reasoning as a standard blind spot, and report the absence of a bound even when the limit appears distant.
30. A test plan that follows the design’s own cells is required, but it tests only cases the design already anticipated.
31. Require an additional adversarial layer covering load, scale, and unanticipated cases without presuming the design is correct.
32. Every introduced name—including file, script, function, term, heading, and test-label names—must explain itself and be easy to search: it must use full words searchable verbatim, share one token across a related family, avoid cryptic abbreviations and bare sequence labels, and pair every issue number in prose with a descriptive handle.
33. Based on the boss’s 2026-08-03 calibration, expect genuinely self-explanatory names to contain roughly two to five words; treat a one-word name as a likely finding, prefer a longer exact name to a shorter ambiguous one, and do not consider typing convenience a constraint.
34. Report poor design-stage names because they will otherwise spread into code, tests, and doctrine, while renaming remains cost-free at this stage.

## Mode 2 — the clarity review (doctrine and instruction files)

1. This mode targets sentence-level failures: wording that requires guessing or sends different readers toward different behavior.
2. Use two pass types, always in separate agents and never in a single agent, because whichever task runs first biases the second: defect hunting makes a later restatement adversarial, while prior restatement makes later defect hunting retrospective.
3. The restatement pass must be innocent and give the text no charitable interpretation.
4. The restatement agent must not know that it is participating in a review.
5. Tell that agent only to express exactly what each sentence says in different words.
6. Tell it not to correct the text, supply missing information, or infer intention.
7. The finding is not the paraphrase itself but the difference between the paraphrase and the intended meaning.
8. An innocent paraphrase reveals ambiguity when it misreads the text.
9. The defect-hunt pass must be performed by another agent using an adversarial and literal reading.
10. Tell that agent to identify defects without resolving them: it must flag sentences that contradict themselves or other sentences, allow two incompatible interpretations, produce incorrect action when followed literally, or cannot be executed by a reader with no context; it must also flag overly broad absolutes and provide an ordinary counterexample, and flag conditionals whose conditions require judgment instead of an observable test. Every flag must quote the sentence, explain both interpretations or the conflict, and give an example in which literal compliance produces the wrong result.

## Running the cells

1. Claude-runtime cells use fresh subagents.
2. Codex-runtime cells run through `scripts/d-review-codex-cell.py`, with one call for each cell using `--cell restate|defect-hunt --tier good|floor --target <path>`; each call uses headless `codex exec`, a read-only sandbox, and writes the cell’s final response to standard output.
3. The files in `prompts/` are the sole prompt source for both runtimes: Claude cells receive the same template text with the target path substituted, preventing the two runtime paths from diverging.
4. Model mappings and reasoning effort for each tier are defined once at the script’s top so model changes require one update; the current mappings, selected by the boss and live-verified on 2026-08-03, are `gpt-5.6-sol` with high effort for `good` and `gpt-5.6-terra` with medium effort for `floor`, and the script pins effort so cells never inherit the local Codex configuration’s default.

## The matrix

1. The matrix is the product of `{restate, defect-hunt}`, `{good, floor}`, and every available runtime; when both runtimes are available, it contains eight cells.
2. `Good` means the highest model at high reasoning effort, which is best at finding contradictions across rules.
3. `Floor` means the middle tier that a framework assigns automatically to subagents and is the lowest tier that actually reads the file, rather than the lowest model tier in existence; models below that floor reveal their own capability limitations instead of defects in the document.
4. Add the companion runtime’s cells after it is admitted.
5. Adjust the matrix to the size of the change: a wholly new file or complete rewrite merits all eight cells, while a one-line modification may require only one `good` defect-hunt cell.

## The prompt is the lever

1. Prompt wording is the controlling factor.
2. The same document can produce drastically different results solely because of prompt wording; a measurement found seventeen issues with an adversarial-literal prompt and two with a charitable prompt that silently corrected the targeted defects.
3. Require literal interpretation, prohibit charitable correction, and give the restatement pass no indication that it is part of a review.

## Synthesize

1. Remove duplicates across cells, expecting substantial overlap; in the first NC run on 2026-08-03, five cells reviewing a skill of about 120 lines produced 109 raw flags that were consolidated into roughly 35 separate defects.
2. The author must compare the restatements with the intended meaning because someone who does not know that meaning can see a faithful paraphrase agree with defective text and fail to detect the defect.
3. Then present findings according to step 6: give each a severity and mitigation, describe what is solid, and provide the overall verdict.

## When NOT to use

1. Do not use this skill for code correctness or for checking an implementation against its design; those belong to a code-review skill.
2. Do not use it for ordinary re-review of doctrine that has been deployed for a long time; that work is a deliberate consistency sweep rather than a per-change gate.
