## YAML frontmatter

1. The skill is named `d-review`.
2. It is for adversarially evaluating an already-written design, specification, or doctrine document before anyone builds from it or lands it, including design-pair documents, architecture specs, skill files, and changes to CLAUDE.md or rules.
3. The document must already exist; this skill judges it and does not help write it.
4. It has two modes: a proposal checklist for assumptions that lack validation, confusion between designs and built reality, unenforced rules presented as enforcement, missing failure cases, needless complexity, unbounded accumulation, risky build order, and names; and a sentence-by-sentence clarity review for doctrine and instruction files that uses isolated paraphrases and adversarial literal readings across capability levels and runtimes.
5. It is not for checking code correctness or comparing an implementation with its design.
6. Use it when a document is about to be built from or landed, or when the boss says to d-review it.

## Design review (d-review)

1. Review a completed written document before its contents become costly: review a finished design before construction and doctrine before it constrains readers.
2. The document must exist and be sufficiently complete to evaluate; the task is to judge the written artifact, never to co-write it.
3. Review does not create fixes: a finding identifies the problem and gives a one-line direction for a repair, while the author performs the repair itself.
4. A reviewer who begins proposing an alternate design is no longer reviewing and has moved into a separately owned design-creation task.
5. Even a design that seems coherent can rely on an untested assumption, mistake a design for an implemented fact, rest an essential guarantee on agent discipline, or omit a failure case without saying so.
6. An already-shipped instruction file has a different failure pattern: a sentence may be unclear, internally inconsistent, or literally false, while a sympathetic reader silently corrects it and does not report it.
7. The fixed checklists are intended to make reviews consistent rather than dependent on the reviewer’s mood.

## Input and mode choice

1. The input is the path to the document, such as a pair document under `docs/issues/<n>-<slug>.md`, a spec under `docs/cross-project/`, a skill file, CLAUDE.md, or a rules page.
2. If no document target is supplied, ask which document should be reviewed.
3. Select the mode based on what the document is: use the soundness checklist for an unbuilt proposal, the clarity review for doctrine or instructions, and separate passes of both for a spec that combines doctrine with designed mechanisms.

## Steps

1. Read the entire document rather than skimming it.
2. Identify its load-bearing claims: statements that the design requires to be true.
3. Subject those load-bearing claims to the most rigorous scrutiny.
4. Before looking for defects, write down your exact understanding of every mechanism, rule, and load-bearing claim, fully explaining subtleties, edge behavior, boundaries, omissions, and effects on neighboring state.
5. If that written understanding differs from the document’s wording, treat the difference as a finding because either the document allowed the mistaken reading or the correct model conflicts with it.
6. A previous review accepted the false claim that uncommitted work exists only in the conversation; writing out the boundary model would have immediately exposed the conflict because files on disk survive session restarts.
7. If both the document and reviewer share the same error, restatement will not reveal it; step 4 and independent passes address that limitation.
8. Run the checklist for the selected mode.
9. Every finding must identify a specific location, state the weakness, assign HIGH, MED, or LOW severity, and give a concrete mitigation rather than merely expressing a vague worry.
10. Prefer coverage over withholding uncertain concerns: report an uncertain finding as LOW and state the uncertainty instead of suppressing it, because the reader filters findings rather than the reporter.
11. Check every claim that could be disproved against reality.
12. For claims about existing things, tool behavior, schema contents, or landed commits, use checks such as `git`, `gh`, `grep`, or `test -f`.
13. Do not accept the document’s own statements about what exists, because this is where designs can misrepresent themselves.
14. Obtain independent passes.
15. An author reviewing their own writing has blind spots because they have already rationalized its weak points.
16. Send fresh-context subagents to review the same document, since they have no investment in its design.
17. Add the companion runtime’s reading after that runtime is admitted.
18. For doctrine files, the clarity-review matrix below constitutes this independent-pass step.
19. Write findings with severity tags, putting the most consequential first and giving each a mitigation.
20. Include a fair section describing what is solid, because a review that only attacks will be discounted.
21. End with one line classifying the result as sound, sound with named risks, or not ready because of a specified reason.

## Mode 1 — the design-soundness checklist

1. Run the lenses in parallel: assign one focused agent to each lens or lens group, give each the document and one question, and have the invoker combine the results.
2. Do not have a single reviewer apply all eleven lenses in one context.
3. After a revision, re-review only the changed material and verify the repair for every earlier finding rather than rerunning the entire matrix.
4. A check that repeats unchanged across reviews, and is certainly and cheaply machine-checkable, should move into a script or the mechanical-check battery.
5. A defect type that repeatedly appears across documents should move upstream into the authoring skill responsible for producing it.
6. The review board should become smaller in this manner, leaving only work that requires genuine judgment for manual review.
7. For runtime-boundary claims, require an empirical probe when an essential claim relies on first-principles reasoning about runtime behavior, such as loading behavior, hook order, or what a session can see.
8. Do not demand a probe for a fact that is true by construction, where falsity would make the mechanism meaningless.
9. Require probes for actual unknowns.
10. For EXISTS-versus-NEW honesty, treat anything described as existing when it is only proposed or designed, or the reverse, as the largest source of design confusion.
11. Verify each such label against reality as required by step 4, and flag every conflation.
12. For enforcement versus discipline, a stated rule either identifies an enforcement point, such as a gate, check, or tool boundary, or it is discipline presented as enforcement.
13. The test is whether the rule’s correct form is already known.
14. If a rule can already be specified precisely, checked cheaply, and made free of false positives by construction, yet remains merely a discipline rule, report it because it belongs in the mechanical-check battery from the beginning and ask why it is absent.
15. If a rule is still discovering its correct form, it may properly begin as discipline because implementing it too early would freeze a guess and enforce that guess reliably.
16. In that case, verify that the document states the upgrade trigger: the concrete failure condition that changes the rule into code; report a finding only if that trigger is absent or one breach of the written rule would be disastrous.
17. For gaps and silently omitted cases, enumerate rather than rely on memory.
18. For every mechanism, systematically traverse all actor states, dependency failures, and concurrency situations, and require the document to name or explicitly reject every resulting cell.
19. A missing cell is a finding even if the happy path works perfectly, and the most valuable findings are usually cells the document’s own story never visits.
20. The over-complexity lens concerns machinery whose benefit does not justify its cost.
21. Its two named warning signs are tracked state that a state-agnostic mechanism could avoid, and a compensating mechanism that covers a gap a simpler primitive could eliminate.
22. Identify what should be cut and what replaces it.
23. Internal consistency concerns contradictions within the document, with its stated principles, or with the project’s recent decisions.
24. Such inconsistency reliably indicates an unexamined decision.
25. For reliability grounding, classify each load-bearing mechanism as measured through a probe, canary, or field observation, or as merely believed.
26. A load-bearing mechanism that is only believed remains a named risk until it is measured.
27. For build order, ask whether the sequence removes the greatest live risk first.
28. Also ask whether the highest-value component is scheduled sensibly rather than placed behind lower-value work.
29. For scale and growth, accumulated data needs a limit through retention, archival, or the project’s artifact-lifecycle rule against stateless piles, as well as an expected volume.
30. Treat unbounded growth combined with correctness-only thinking as a default blind spot, and flag a missing growth treatment even if the limit appears distant.
31. For test-plan completeness, a plan that covers the design’s own cells is necessary but tests only what the design itself considered.
32. Require a second adversarial layer involving load, scale, and unanticipated cases that does not assume the design is correct.
33. For naming, every introduced name—including files, scripts, functions, terms, headings, and test labels—must explain itself and be searchable: use full words that searches match exactly, one shared token for related name families, no obscure abbreviations or bare sequence labels, and no prose references consisting only of a number.
34. An issue number must always appear with a descriptive handle.
35. Expect nearly every genuinely self-explanatory name to contain two to five words; treat a one-word name as a finding candidate by default, favor a longer precise name over a short unclear one, and do not treat typing convenience as a constraint.
36. Flag poor names in the design because they will spread into code, tests, and doctrine, whereas renaming them at design time is still free.

## Mode 2 — the clarity review (doctrine and instruction files)

1. The relevant failure is at sentence level: a reader must not need to guess to follow a sentence, and two readers must not follow the same sentence into different actions.
2. There are two pass types, and separate agents must perform them because doing one first biases the other: a defect-hunting frame makes restatement adversarial, while a restatement frame makes defect hunting after-the-fact.
3. In the restatement pass, the agent is innocent and gives no charity.
4. The agent must not be told it is conducting a review.
5. Prompt it only to restate what each sentence says in its own words, without repairing it, filling omissions, or inferring intent.
6. The finding is the difference between that paraphrase and the intended meaning, not the paraphrase itself.
7. An innocent paraphrase reveals ambiguity when it reads the words differently.
8. In the defect-hunt pass, use a separate agent that reads adversarially and literally.
9. Tell that agent to locate defects and forbid it from resolving them.
10. It must flag every sentence that contradicts itself, conflicts with another sentence, permits two incompatible readings, becomes wrong when followed literally, or cannot be executed by a reader with no context.
11. It must also flag absolutes that are broader than they can be, with an ordinary counterexample, and conditionals whose conditions require judgment rather than an observable test.
12. Every flag must quote the sentence, state both readings or the conflict, and give a case in which obeying the words produces the wrong result.
13. Claude-runtime matrix cells use fresh subagents.
14. Codex-runtime cells run through `scripts/d-review-codex-cell.py`, once per cell, using `--cell restate|defect-hunt --tier good|floor --target <path>`, headless `codex exec`, a read-only sandbox, and stdout for the cell’s final message.
15. The templates in `prompts/` are the sole prompt source for cells in both runtimes; Claude cells receive the same template text with the target path substituted, preventing the two runtime paths from drifting apart.
16. The script contains the tier-to-model mapping and reasoning effort in one top-level place so model changes require one update.
17. At present, `good` uses boss-selected, live-verified `gpt-5.6-sol` at high effort and `floor` uses boss-selected, live-verified `gpt-5.6-terra` at medium effort; the effort is fixed in the script so cells do not inherit the machine-local Codex configuration’s default.
18. The matrix combines restatement and defect hunting with good and floor tiers and every available runtime; if both runtimes are available, it contains eight cells.
19. The good tier is the highest model at high effort and is best at finding contradictions across rules.
20. The floor tier is the middle tier that a framework automatically assigns to subagents: the lowest tier that truly reads the file, rather than the lowest model that exists, because a model below that floor reports its own capability limits rather than document defects.
21. Add the companion runtime’s cells once that runtime is admitted.
22. Match the matrix to the size of the change: a new file or complete rewrite receives all eight cells, while a one-line change may need only one good defect-hunt cell.
23. Prompt wording is the controlling factor.
24. Identical documents can yield very different results from wording alone: an adversarial-literal prompt produced seventeen findings, while a charitable prompt that silently repaired the targeted defects produced two.
25. Require literal reading, prohibit charity, and give the restatement pass no review framing.
26. Consolidate duplicate findings across cells, because substantial overlap is expected; an initial NC run on an approximately 120-line skill produced 109 raw flags from five cells and reduced them to approximately 35 distinct defects.
27. The author must compare restatements with intent, because a comparator lacking the intended meaning can see a faithful paraphrase of defective text agree with it and fail to notice the defect.
28. Then write findings as required by step 6: severity, mitigation, what is solid, and a net verdict.

## When NOT to use

1. Do not use this skill for code correctness or for reviewing an implementation against its design; those belong to a code-review skill.
2. Do not use it for routine re-review of long-shipped doctrine, because that is a deliberate consistency sweep rather than a gate for each change.
