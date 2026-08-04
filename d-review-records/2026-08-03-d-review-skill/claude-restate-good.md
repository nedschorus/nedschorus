# Restatement of /Users/el/Projects/nedschorus/.claude/skills/d-review/SKILL.md

## YAML frontmatter

1. The skill's name field gives its name as `d-review`.
2. The description field opens by saying: review a written design document, specification, or doctrine document in an adversarial manner, and do it before anything gets built from that document or before the document lands; the kinds of documents named are a design pair doc, an architecture spec, a skill file, a CLAUDE.md, or a rule change.
3. The document has to exist already; the skill's job is to judge the document, and the skill never participates in writing it.
4. There are two modes: one is a design-soundness checklist meant for proposals, and the parenthetical lists what that checklist covers — assumptions that have not been validated, confusing what is designed with what is built, discipline that has been dressed up as enforcement, failure modes that got dropped, excessive complexity, growth without bound, risk in the ordering of the build, and naming; the other mode is a clarity review conducted at the level of individual sentences, meant for doctrine and instruction files, and its parenthetical says it consists of restatement done in isolation plus adversarial-literal passes run across different capability tiers and different runtimes.
5. The skill is not for checking whether code is correct, and it is not for reviewing an implementation by comparing it against its design.
6. Use the skill when a document is on the verge of being built from or landed, or when the boss says "d-review this".

## Design review (d-review) — opening section

1. Review a written document before the content in it becomes expensive: review a finished design before anything is built from it, and review doctrine before it starts binding the people who read it.
2. The document must exist and be far enough along to be judged — because reviewing means passing judgment on the written artifact, and never means co-writing it.
3. Review never creates: a finding states what is wrong and indicates the direction of a fix in a single line; producing the fix itself is the author's job, not the reviewer's.
4. If a reviewer wants to put forward an alternative design, that reviewer is no longer doing review — proposing an alternative design is a create-design task, and that task is owned by someone else, separately.
5. A design can read as coherent and still be resting on an assumption nobody validated, still be conflating what is designed with what is built, still be leaning a load-bearing guarantee on agent discipline, or still be quietly dropping a failure mode — and these defects are much cheaper to correct while they are still in the document than after the build.
6. An instruction file that has already shipped fails in a different way: a single sentence that is ambiguous, contradicts itself, or is literally wrong, and a sympathetic reader quietly patches over it in their own head and never reports it.
7. The checklists below are fixed so that the review comes out consistent rather than varying with the reviewer's mood.

## Input and mode choice

1. The input is the path to the document — examples given are a pair doc at `docs/issues/<n>-<slug>.md`, a spec under `docs/cross-project/`, a skill file, CLAUDE.md, or a rule page.
2. If nobody supplies a target, ask which document is to be reviewed.
3. Choose the mode according to what kind of document it is: a proposal that has not been built yet gets the soundness checklist; a doctrine or instruction file gets the clarity review; a spec that is both things at once — doctrine that carries designed mechanisms inside it — gets both modes, run as separate passes.

## Steps

1. Read the entire document, all the way through, rather than skimming it.
2. Work out which claims are load-bearing: the statements that the design depends on being true.
3. Those load-bearing claims get the most rigorous scrutiny.
4. Before starting to hunt for defects, write out your precise understanding of every mechanism, every rule, and every load-bearing claim, with the subtleties spelled out in full — covering how it behaves at the edges, its boundary conditions, what it does not cover, and what effect it has on state next to it.
5. If your written-out understanding diverges from what the document's words say, that divergence is itself a finding — either the document allowed you to misread it, or your model is right and the document contradicts it.
6. A concrete example of what skipping this costs: a review once let through the sentence "uncommitted work has no copy outside the conversation," which was stated confidently and was false — writing out a model of that boundary would have run straight into the contradiction right away, because files sitting on disk continue to exist across session restarts.
7. A stated limitation: when the document and the reviewer share the same error, no amount of restatement will catch it; step 4 and the independent passes exist to cover that case.
8. Run the checklist belonging to whichever mode was chosen.
9. Each finding must state the specific location, what the weakness is, a severity level of HIGH, MED, or LOW, and a specific mitigation — a vague expression of concern does not qualify.
10. Prefer coverage to self-censorship: if you are unsure about a finding, report it anyway, marked LOW and with your uncertainty stated, instead of holding it back; deciding what to filter out is the reader's job, not the job of the person reporting.
11. Check every claim that can be falsified against ground truth.
12. Any claim about what exists, about what a tool does, about what a schema contains, or about what a commit landed must be checked, using tools such as `git`, `gh`, `grep`, and `test -f`.
13. Never accept the document's own statements about what exists on trust; existence labels are precisely the place where designs deceive themselves.
14. Obtain independent passes.
15. Reviewing one's own text leaves blind spots, because the author has already talked themselves into accepting the weak parts.
16. Send fresh-context subagents at the same document; they have no stake in the design.
17. Once the companion runtime is admitted, add its read as well.
18. When the document is a doctrine file, the clarity-review matrix described further down is what constitutes this step.
19. Write up the findings: tagged with severity, ordered with the most consequential first, and each one accompanied by its mitigation.
20. Include a section covering what is solid, written fairly — a review consisting only of attacks gets discounted.
21. Finish with a single line giving one of: sound, sound-with-named-risks, or not-ready-because-X.

## Mode 1 — the design-soundness checklist

1. On running it: the lenses are fanned out, with one focused agent assigned per lens or per group of lenses, each agent given the document and the one question belonging to its lens; the person who invoked the review then synthesizes the results.
2. No single reviewer goes through all eleven lenses inside one context.
3. When re-reviewing after a revision, cover only the delta: the sections that changed, plus a check that each earlier finding's fix actually happened — do not re-run the whole matrix.
4. Repetition is also to be migrated out of the review: a check that comes out identical review after review is the kind that is certain and cheap to check, so it belongs in a script or in the mechanical check battery; and a class of defect that keeps appearing across different documents belongs upstream, in the authoring skill that keeps generating it.
5. The expectation is that the review board shrinks by this process; only checks that require genuine judgment should remain manual.
6. Lens 1 is titled "Unvalidated runtime-boundary claims."
7. When a load-bearing claim rests on reasoning from first principles about how the runtime behaves — such as what gets loaded at what time, the order hooks fire in, or what a session is and is not able to see — it needs an empirical probe rather than an assumption.
8. Going the other way, do not invent a probe for something that is true by construction — meaning a fact whose being false would render the mechanism itself pointless.
9. Insist on probes for the unknowns that are genuine.
10. Lens 2 is titled "EXISTS-vs-NEW honesty."
11. Anything that is labeled as already existing when it is in fact only designed or proposed — or labeled the other way around — is called out here as the largest single source of confusion in designs.
12. Check each such label against ground truth (as described in step 4) and flag every instance of the two being conflated.
13. Lens 3 is titled "Enforcement vs discipline — a two-sided lens," and is noted as having been sharpened by the boss's questioning on 2026-08-03.
14. A rule as stated either identifies an enforcement point — a gate, a check, or a tool boundary — or else it is discipline that has been dressed up to look like enforcement.
15. What distinguishes the two cases is whether the correct form of the rule is already known.
16. First side: if a rule can be specified precisely right now, is cheap to check, and by its construction produces no false positives, and yet it is sitting at the discipline rung, that is a finding — such a rule belongs in the mechanical check battery from the first day, and the review is to ask why it is not already there.
17. Second side: a rule that is still working out what its own correct form should be legitimately begins life as discipline, because writing it into code too early freezes a guess and then enforces that guess with machine-level reliability; for such a rule, check that the document states the upgrade trigger — the specific failure condition that would convert the rule into code — and flag it only if that trigger is absent, or if one single failure of the written rule would be disastrous.
18. Lens 4 is titled "Gaps and silently-dropped cases — enumerate, don't recall."
19. For every mechanism, systematically walk the state space: every state an actor can be in (busy, idle, in the middle of a turn, dead), every way a dependency can fail (the file it reads, the tool it runs, the channel it writes to), and every concurrency situation (two sessions at once, re-entry, the same thing firing repeatedly) — and require that the document either address each cell or explicitly discard it.
20. Leaving something out is a finding even if the happy path is perfect; the finds with the most value tend to be exactly those cells that the design's own narrative never goes to.
21. Lens 5 is titled "Over-complexity — what can be cut."
22. This lens targets machinery whose value is not worth what it costs.
23. Two smells are given names: unnecessary tracked state, meaning state the design keeps that a state-agnostic mechanism would make unnecessary; and a compensating mechanism, meaning machinery that papers over a gap which a simpler primitive would remove entirely.
24. State which cut to make and what takes the place of what was cut.
25. Lens 6 is titled "Internal consistency."
26. This covers the document contradicting itself, contradicting the principles it itself states, or contradicting rulings the project made recently.
27. Internal inconsistency is a dependable indicator that some decision went unexamined.
28. Lens 7 is titled "Reliability grounding."
29. For each load-bearing mechanism, ask whether it has been measured — by a probe, a canary, or observation in the field — or is merely believed.
30. A load-bearing mechanism that is only believed counts as a named risk until it has been measured.
31. Lens 8 is titled "Build-order sanity."
32. Ask whether the ordering eliminates the highest live risk first.
33. Ask whether the highest-value piece is scheduled at a sensible point or is buried behind work of lower value.
34. Lens 9 is titled "Scale and growth."
35. Any data the design accumulates requires a bound — through retention, through archival, or through the project's artifact-lifecycle rule, described as "no stateless piles" — and it also requires a stated expectation of how much volume there will be.
36. Growth without bound combined with thinking only about correctness is described as a blind spot by default; flag the absence of a bound even when the ceiling appears to be a long way off.
37. Lens 10 is titled "Test-plan completeness — cooperative AND adversarial."
38. A test plan that maps onto the design's own cells is necessary, but it only exercises the things the design already thought about.
39. Require a second layer that is adversarial — covering load, scale, and "what did we not anticipate" — a layer that does not start from the premise that the design is correct.
40. Lens 11 is titled "Naming."
41. Every name the document introduces — files, scripts, functions, terms, headings, test labels — has to be self-documenting and greppable: made of full words that a search will match exactly, sharing one common token across a family of related names, with no cryptic abbreviations, no bare sequence labels, and no bare numeric references in running prose (an issue number is always accompanied by a descriptive handle).
42. Expect that nearly every genuinely self-documenting name will be two to five words long — attributed to a boss calibration on 2026-08-03: a name of one word is almost never self-documenting, so by default the reviewer treats a one-word name as a candidate finding; a longer name that is precise is better than a short one that is ambiguous, and how easy the name is to type does not count as a constraint.
43. A bad name inside a design spreads outward into code, tests, and doctrine — so flag it at the design stage, while renaming still costs nothing.

## Mode 2 — the clarity review (doctrine and instruction files)

1. The failure mode being looked for here occurs at the level of the sentence: a reader who cannot get through a sentence without guessing, or two readers who each follow the sentence and end up behaving differently.
2. There are two types of pass, and they run in SEPARATE agents — one agent must never do both — because whichever of the two tasks is performed first primes the second one (being framed for a defect hunt makes the restatement adversarial; being framed for restatement makes the hunt come after the fact).
3. Pass type 1 is the restatement pass, characterized as innocent and zero-charity.
4. The agent doing it must NOT be aware that it is part of a review.
5. Prompt that agent to do nothing but paraphrase, using wording such as: "Restate, in your own words, exactly what each sentence's words say. Do not repair it, fill gaps, or infer intent."
6. The finding is not the paraphrase itself — the finding is the divergence between the paraphrase and the meaning that was intended.
7. A paraphrase produced innocently reveals ambiguity by misreading it.
8. Pass type 2 is the defect-hunt pass, characterized as adversarial-literal.
9. It is done by a separate agent, told to locate defects and prohibited from resolving them: it flags every sentence that contradicts itself, that conflicts with some other sentence, that supports two readings which are incompatible, that is wrong if obeyed literally, or that a reader with zero context cannot execute; and additionally it flags absolutes stated more broadly than they can actually hold (supplying the everyday counterexample) and conditionals whose condition requires a judgment call instead of being an observable predicate.
10. Every flag quotes the sentence, supplies either both readings or the conflict, and supplies a case in which obeying the words as written produces the wrong outcome.
11. On running the cells: cells on the Claude runtime are fresh subagents.
12. Cells on the Codex runtime are run through `scripts/d-review-codex-cell.py`, with one invocation for each cell, taking arguments `--cell restate|defect-hunt --tier good|floor --target <path>`, running `codex exec` headlessly in a read-only sandbox, and emitting that cell's final message on stdout.
13. The templates in `prompts/` are the one and only source of prompts for the cells on BOTH runtimes — a Claude cell gets prompted with the identical template text, with the target path substituted in — which is what prevents the two legs from drifting apart from each other.
14. The mapping from tier to model lives at the top of the script, giving a single place to update as models change; currently that mapping is `gpt-5.6-sol` for good and `gpt-5.6-terra` for floor, described as picked by the boss and verified live on 2026-08-03.
15. The matrix is the cross product {restate, defect-hunt} × {good, floor} × {each available runtime} — which, when both runtimes are available, comes to eight cells in total.
16. "Good" means the top model run at high effort, and is described as best at catching contradictions that span rules.
17. "Floor" means the middle tier that a framework assigns to subagents automatically — defined as the lowest tier that actually reads the file, not the lowest tier that exists at all, since a model below the floor ends up flagging its own gaps in capability rather than the document's defects.
18. Add the companion runtime's cells once that runtime has been admitted.
19. Scale the number of cells to the size of the change: an entirely new file or a full rewrite warrants all eight cells, whereas a one-line tweak may only require a single good-tier defect-hunt.
20. The prompt is the lever: the same document produces wildly different results purely as a function of how the prompt is worded — with a measured instance of seventeen findings under an adversarial-literal prompt versus two findings under a charitable prompt that quietly resolved the very defects the review was hunting for.
21. Force reading to be literal; forbid charity; and give the restatement pass no framing at all that indicates a review.
22. On synthesizing: deduplicate across the cells, and expect a lot of overlap — the first NC run, on 2026-08-03, had five cells over a skill file of roughly 120 lines return 109 raw flags, which consolidated down to about 35 distinct defects.
23. It is the author who compares the restatements against the intent, because a comparator who does not hold the intended meaning will watch a faithful paraphrase of broken text agree with that text and will miss the defect.
24. After that, produce findings the same way step 6 describes: severity, mitigation, what is solid, and the net verdict.

## When NOT to use

1. Do not use it for code correctness, or for reviewing an implementation against its design — that work belongs to a code-review skill rather than this one.
2. Do not use it for routine re-review of doctrine that shipped long ago — that is a deliberate consistency sweep, not a gate applied per change.

---

Total paraphrases: 106
