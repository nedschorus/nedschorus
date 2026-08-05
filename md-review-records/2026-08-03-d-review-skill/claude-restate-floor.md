# Restatement of /Users/el/Projects/nedschorus/.claude/skills/d-review/SKILL.md

## Section A — YAML frontmatter

1. The skill's identifier/name is "d-review".
2. The skill adversarially reviews a written design, specification, or doctrine document before anything gets built from it or before it is finalized/lands — examples given are a design pair document, an architecture spec, a skill file, or a CLAUDE.md or rule change.
3. The document being reviewed must already exist; the skill judges the document rather than helping write it.
4. The skill has two modes: a design-soundness checklist for proposals (checking for unvalidated assumptions, conflation of designed vs. built, discipline dressed up as enforcement, dropped failure modes, over-complexity, unbounded growth, build-order risk, and naming), and a sentence-level clarity review for doctrine and instruction files (consisting of isolated restatement passes plus adversarial-literal passes, run across different capability tiers and runtimes).
5. The skill is not meant for reviewing code correctness, and not meant for reviewing an implementation against its design.
6. The skill should be used when a document is about to be built from or finalized/landed, or when the boss explicitly says "d-review this".

## Section B — Heading and opening paragraph ("# Design review (d-review)")

1. The purpose is to review a written document before its content becomes costly to fix — reviewing a finished design before anything is built from it, or reviewing doctrine before it becomes binding on readers.
2. The document must already exist and be sufficiently complete to be judged — the act of reviewing judges the artifact as written, and does not co-write it.
3. Review is defined as never creating: a finding states what is wrong and indicates the direction of a fix in a single line, while the actual fix is left to the document's author.
4. A reviewer who tries to propose an alternative design has stepped outside the review role — that activity is a separate, distinct task of creating a design, owned separately.
5. A design can appear coherent while still containing problems: it may rest on an unvalidated assumption, blur the line between what is designed and what is actually built, depend on a load-bearing guarantee that relies on agent discipline rather than enforcement, or silently omit a failure mode — and these defects are much cheaper to fix while still in document form than after something has been built from them.
6. A shipped instruction file fails in a different way: a single sentence that is ambiguous, self-contradictory, or literally incorrect gets silently "fixed" in the reader's head by a sympathetic reader, who then never reports the underlying problem.
7. The fixed checklists that follow exist to keep the review consistent from one run to the next, rather than dependent on the reviewer's mood.

## Section C — "## Input and mode choice"

1. The input is the path to the document to review, with examples given: a pair doc at docs/issues/<n>-<slug>.md, a spec under docs/cross-project/, a skill file, CLAUDE.md, or a rule page.
2. If no target document is specified, the reviewer should ask which document to review.
3. The mode to use is chosen based on what kind of document it is: a not-yet-built proposal gets the soundness checklist, a doctrine or instruction file gets the clarity review, and a document that is both — doctrine that also carries designed mechanisms — gets both modes, run as separate passes.

## Section D — "## Steps"

1. Read the entire document in full, not just a skim.
2. Identify the load-bearing claims — the statements the design depends on being true.
3. Those load-bearing claims receive the hardest scrutiny.
4. Before hunting for defects, write out your precise understanding of every mechanism, rule, and load-bearing claim, with subtleties fully spelled out: edge-case behavior, boundary conditions, what is left uncovered, and its effects on adjacent state.
5. A gap between what you wrote and what the document's words actually say counts as a finding — either the document's wording allowed you to misread it, or your correct understanding actually contradicts the document.
6. As an example of the cost of skipping this: a past review let through the confidently stated but false sentence "uncommitted work has no copy outside the conversation" — writing out a model of that boundary would have immediately conflicted with it, since files saved to disk do persist across session restarts.
7. There is a known limitation: if both the document and the reviewer share the same wrong belief, this restatement step will not catch it — that is what step 4 (verification) and the independent passes are for.
8. Run through the checklist belonging to whichever mode was chosen.
9. Every finding must state the specific location, the specific weakness, a severity rating (HIGH, MED, or LOW), and a concrete mitigation — a vague concern is not acceptable.
10. Favor reporting coverage over self-censoring: report even a finding you are not fully sure about, tagging it LOW and stating the uncertainty, rather than holding it back; deciding what to filter out is the reader's job, not the reviewer's.
11. Verify every claim in the document that is capable of being checked, against actual ground truth.
12. Any claim about something existing, about what a tool does, about what a schema contains, or about what a commit actually delivered must be checked using tools such as git, gh, grep, or test -f.
13. Never simply trust the document's own labeling of what already exists — that is precisely the place designs tend to misrepresent themselves.
14. Obtain independent review passes.
15. A person reviewing their own writing has blind spots, because the author has already talked themselves into accepting the weak parts.
16. Send the document to subagents with fresh context who have no stake in the design.
17. Once a companion runtime is available/admitted, include its read as well.
18. For a doctrine file specifically, the clarity-review matrix described later in the document serves as this independent-passes step.
19. Write up the findings: tag each with severity, order them with the most consequential first, and include a mitigation for each.
20. Include a section that fairly lists what is solid in the document — a review that does nothing but attack is given less credit.
21. Conclude with a single summary line using one of three labels: sound, sound-with-named-risks, or not-ready-because-X.

## Section E — "## Mode 1 — the design-soundness checklist"

1. Running this mode works by fanning the checklist's lenses out to separate reviewers — one focused agent assigned to each lens or group of lenses, each given the document plus its one specific question — and the person who invoked the review then synthesizes their outputs.
2. No single reviewer is expected to go through all eleven lenses within one context/session.
3. When a document is re-reviewed after being revised, the re-review only needs to cover the delta: the sections that changed, plus confirming that each previously-reported finding was actually fixed — it should never re-run the entire checklist matrix from scratch.
4. Checks tend to migrate out of manual review over time: a check that comes back identically across multiple reviews is the kind of check that is certain and cheap to automate, and belongs in a script or in the mechanical/automated check battery instead; a class of defect that keeps recurring across different documents belongs further upstream, fixed in the authoring skill that keeps producing that defect.
5. The review board (the set of lenses requiring human/agent judgment) is expected to shrink over time as a result of this migration — only checks that genuinely require judgment should remain manual.
6. The first lens is named: Unvalidated runtime-boundary claims.
7. A load-bearing claim that rests on reasoning from first principles about how the runtime behaves — things like what loads when, the order hooks fire in, or what a session can or cannot see — requires an empirical probe to validate it; assumption alone is not sufficient.
8. Conversely, don't create a probe for something that is true by construction — i.e., a fact whose falsity would make the underlying mechanism itself meaningless.
9. Probes should be required only for claims that are genuinely unknown.
10. The second lens is named: EXISTS-vs-NEW honesty.
11. This lens targets anything the document labels as already existing when it is really only designed or proposed (or the reverse case) — described as the single largest source of confusion in designs.
12. Each such label should be checked against ground truth (per step 4) and every instance of this conflation should be flagged.
13. The third lens is named: Enforcement vs discipline — described as a two-sided lens, sharpened following boss questioning on 2026-08-03.
14. Any stated rule either identifies a concrete enforcement point — a gate, a check, or a tool-level boundary — or else it is discipline that is merely dressed up to look like enforcement.
15. The distinguishing factor is whether the correct form of the rule is already known.
16. Side one: if a rule can already be precisely specified, is cheap to check, and is free of false positives by construction, but is nevertheless still sitting at the "discipline" level rather than being enforced mechanically, that itself is a finding — such a rule belongs in the mechanical check battery starting immediately, and the review should ask why it isn't already there.
17. Side two: a rule that is still in the process of discovering its correct form is legitimately allowed to start out as discipline (since coding it too early would lock in a guess and enforce that guess with machine-level rigidity); for such rules, the reviewer should verify that the document specifies the upgrade trigger — the concrete failure condition that would cause it to be converted into code — and should flag it only if that trigger is missing, or if a single failure of the rule as merely-written would be disastrous.
18. The fourth lens is named: Gaps and silently-dropped cases — enumerate, don't recall.
19. For each mechanism, the reviewer should systematically walk through the state space: every state the relevant actor could be in (busy, idle, mid-turn, dead), every way a dependency could fail (the file it reads, the tool it runs, the channel it writes to), and every concurrency scenario (two sessions at once, re-entry, repeated firing) — and the document is required to either address or explicitly rule out each of these combinations/cells.
20. Leaving out any of these is a finding even if the main/happy path works flawlessly; the most valuable findings tend to be the cells that the document's own narrative never even mentions.
21. The fifth lens is named: Over-complexity — what can be cut.
22. This targets machinery whose value doesn't justify what it costs.
23. Two specific smells are named: "unnecessary tracked state" (state the design keeps track of that a state-agnostic approach would make unnecessary) and a "compensating mechanism" (machinery that papers over a gap that a simpler underlying primitive would eliminate entirely).
24. The finding should name what should be cut and what would replace it.
25. The sixth lens is named: Internal consistency.
26. This covers cases where the document contradicts itself, contradicts its own stated principles, or contradicts the project's recent decisions/rulings.
27. Internal inconsistency reliably indicates that some call in the document was never actually examined/thought through.
28. The seventh lens is named: Reliability grounding.
29. For each load-bearing mechanism, the question is whether it has actually been measured (via a probe, a canary, or field observation) or is merely believed to work.
30. A load-bearing mechanism that is merely believed (not measured) counts as a named risk until it is measured.
31. The eighth lens is named: Build-order sanity.
32. The question is whether the planned build order addresses/removes the highest live risk first.
33. The question is also whether the highest-value piece of work is scheduled sensibly, or whether it's buried behind lower-value work.
34. The ninth lens is named: Scale and growth.
35. Any data that the design accumulates over time needs a defined bound — through retention policy, archival, or the project's artifact-lifecycle rule against stateless piles — and the design should state an expected volume.
36. Unbounded growth combined with thinking that only considers correctness is called out as a default blind spot; its absence should be flagged even when the ceiling on growth appears to be far off.
37. The tenth lens is named: Test-plan completeness — cooperative AND adversarial.
38. A test plan that only covers the cells the design itself identified is necessary, but it only exercises what the design's authors already thought of.
39. A second, adversarial layer of testing is required — covering load, scale, and "what did we fail to anticipate" — one that does not simply assume the design is correct.
40. The eleventh lens is named: Naming.
41. Every name the document introduces — for files, scripts, functions, terms, headings, or test labels — must be self-documenting and easy to search for: made of full words that a text search would match verbatim, sharing a common token across a family of related names, with no cryptic abbreviations, no bare sequence labels, and no bare numeric references appearing in prose (an issue number must always be accompanied by a descriptive handle).
42. Per a boss calibration from 2026-08-03, the expectation is that almost every name that is genuinely self-documenting will run two to five words long: a single-word name is almost never self-documenting, so by default the reviewer should treat a single-word name as a candidate finding; a longer, precise name is preferred over a short, ambiguous one, and how easy the name is to type is not a valid constraint.
43. A poorly chosen name in a design tends to propagate into the code, tests, and doctrine that follow from it, so it should be flagged here, at the design stage, while renaming it is still free/costless.

## Section F — "## Mode 2 — the clarity review (doctrine and instruction files)"

1. The failure mode this mode targets operates at the level of individual sentences: a reader who cannot follow a given sentence without having to guess at its meaning, or two different readers who each follow the same sentence into different resulting behavior.
2. There are two types of passes, and they must be run in separate agents — never combined into one agent doing both — because whichever pass runs first will bias/prime the second one: running the defect-hunt pass first makes the subsequent restatement pass adversarial in framing, while running the restatement pass first makes the subsequent defect-hunt feel after-the-fact/post-hoc.
3. The first pass is named: Restatement pass — described as innocent and zero-charity.
4. The agent performing this pass must not be told that it is participating in a review.
5. It should be prompted only to paraphrase, using an instruction along these lines: "Restate, in your own words, exactly what each sentence's words say. Do not repair it, fill gaps, or infer intent."
6. The actual finding is not the paraphrase itself, but rather the divergence between the paraphrase produced and the meaning that was actually intended.
7. An innocent paraphrase reveals ambiguity in the original text by misreading it.
8. The second pass is named: Defect-hunt pass — described as adversarial-literal.
9. This uses a separate agent that is told to find defects but is forbidden from resolving them; it should flag every sentence that is self-contradictory, that conflicts with another sentence, that supports two incompatible readings, that is wrong if obeyed literally, or that a reader with zero context could not execute; it should also flag absolute statements that are broader than they can actually hold (supplying the ordinary counterexample) and flag conditionals whose triggering condition is a subjective judgment call rather than something objectively observable.
10. Each flag raised must quote the sentence in question, present either the two possible readings or describe the conflict, and give a concrete case where following the words literally produces the wrong outcome.
11. Cells run against the Claude runtime use fresh subagents.
12. Cells run against the Codex runtime go through the script scripts/d-review-codex-cell.py, with one invocation per cell (using the flags --cell restate|defect-hunt --tier good|floor --target <path>), running as a headless `codex exec` process in a read-only sandbox, with the cell's final message emitted on stdout.
13. The prompt templates located in the prompts/ directory are the single source of the prompt text used for cells in both runtimes — a Claude cell is given the identical template text with only the target path substituted in — so that the two runtimes' review legs cannot drift apart from each other over time.
14. The mapping from tier name to actual model sits at the top of the script, as the single place to update when models change; as of now, that mapping is gpt-5.6-sol for "good" and gpt-5.6-terra for "floor," a pairing chosen by the boss and confirmed live on 2026-08-03.
15. The full matrix is the cross product of {restate, defect-hunt} pass types, {good, floor} tiers, and each available runtime — meaning that with both runtimes available, there are eight cells total.
16. "Good" refers to the top model run at high reasoning effort, and is described as being the best at catching cross-rule contradictions.
17. "Floor" refers to the mid tier that a framework automatically assigns to subagents — defined as the lowest tier that actually reads the file, not simply the lowest tier that exists at all, because a model below that floor would flag its own capability limitations rather than actual defects in the document.
18. Once a companion runtime becomes available/admitted, its cells should be added to the matrix.
19. The number of cells run should scale with the size of the change: a brand-new file or a full rewrite warrants running all eight cells, while a one-line tweak may only need a single "good" defect-hunt cell.
20. The exact same document can produce dramatically different review results purely based on how the prompt is worded — as measured, an adversarial-literal prompt produced seventeen findings, while a charitable prompt on the same document produced only two, because the charitable prompt silently resolved the very defects the review was supposed to be hunting for.
21. The instruction is: force literal reading, forbid charitable interpretation, and give the restatement pass no framing that it is part of a review at all.
22. Findings should be deduplicated across all the cells, with heavy overlap expected — as an example, the first run against the NC system reviewed a roughly 120-line skill using five cells, which produced 109 raw flags that were consolidated down to about 35 distinct defects.
23. The author of the document is the one who compares the restatements against the document's actual intended meaning, because a comparator who does not know the intended meaning could see a faithful paraphrase of broken text agree with that broken text and thereby miss the defect.
24. After that, the findings should be written up as described in step 6: with severity ratings, mitigations, a "what's solid" section, and a net overall verdict.

## Section G — "## When NOT to use"

1. This skill should not be used for reviewing code correctness, nor for reviewing an implementation against its design — that work belongs to a separate code-review skill, not this one.
2. This skill should not be used for routine re-review of doctrine that has already been shipped for a long time — that kind of review is a deliberate consistency sweep, not something that gates every change.
