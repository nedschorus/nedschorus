<!-- provenance: runtime=claude model=claude-opus-5 effort=session-inherited (Agent tool has no per-cell effort control; model id read from subagent transcript) cell=defect-hunt tier=good target=.claude/skills/d-review/SKILL.md session=4cf7d488 date=2026-08-04 -->

I have the full context the prompt defines: the target file, the checkout root (which has **no CLAUDE.md and no AGENTS.md**), and everything the file references by explicit path — `scripts/d-review-codex-cell.py`, `prompts/restate.md`, `prompts/defect-hunt.md`, `d-review-records/`, `docs/issues/`, `docs/cross-project/`. Findings follow in document order.

---

**1.** `name: d-review` (frontmatter), echoed as the invocation phrase `"d-review this"` and the heading `# Design review (d-review)`.

Defect class: conflict with another sentence in the same file (b) — specifically with the file's own lens 11.

Lens 11 defines an in-scope name as "an identifier that anything outside the document will use to find or invoke the thing … skill names" and requires: "Every in-scope name must be self-documenting and greppable: full words a search matches verbatim … no cryptic abbreviations". `d-review` is a skill name — the exact category lens 11 names — and `d` is a cryptic single-letter abbreviation for "design", expanded nowhere except the section heading. The same lens adds "a one-word name is a finding candidate by default when the word is generic"; `d-review` is worse than one generic word, since the disambiguating half is a letter. Harm: a reader searching the codebase for "design review" tooling matches nothing; the abbreviation propagates into `d-review-records/` and `scripts/d-review-codex-cell.py`, so the whole name family inherits it, which is the propagation cost lens 11 itself warns about ("A bad name in a design propagates into code, tests, and doctrine"). Confidence: sure the sentence-level conflict exists; I cannot judge whether the name predates the lens or was deliberately grandfathered, because the file says nothing about exempting itself.

**2.** "Use when a document is about to be built from or landed, or when the boss says "d-review this" — his ask wins over the exclusions." (frontmatter description)

Defect class: wrong/impossible when obeyed literally (d), and conflict with the mode-choice rule.

The exclusions are stated in the same description ("Not for code correctness, and not for reviewing an implementation against its design") and in "When NOT to use". If the boss points this skill at a source file, the override says the skill applies. But every executable path in the file assumes a written document: line 14 says "Pick the mode by what the document IS", and offers exactly three branches — a design not yet built from, a doctrine/instruction file, or both. A Python file is none of the three; mode 1's lenses ask about assumptions, EXISTS-vs-NEW labels and build order, and mode 2's cells hunt sentence defects in prose. Harm: an agent obeying the override literally has an in-scope invocation with no applicable mode and no instruction for what to do instead — it will improvise a code review the file explicitly disclaims competence for, or stall. Confidence: sure that the override creates a state the rest of the file does not cover; unsure whether the author intends the override to be scope-only (still apply the closest mode) or full (do whatever the boss asked), because the sentence supports both.

**3.** "when the boss says "d-review this" — his ask wins over the exclusions." (frontmatter); recurring as "boss-ruled 2026-08-04", "the boss picks the models", "boss calibration 2026-08-03", "boss-required 2026-08-04".

Defect class: unexecutable by a zero-context reader (e).

"The boss" is never defined in this file, and this checkout has no CLAUDE.md and no AGENTS.md — I verified: `/Users/el/Projects/nedschorus/CLAUDE.md` and `/Users/el/Projects/nedschorus/AGENTS.md` do not exist. So the defined instruction floor for a reader of this file is empty, and "the boss" resolves to nothing. Harm: two behaviors depend on identifying this person — the exclusion override in finding 2, and "the boss picks the models" in line 50, which forbids the agent from choosing a model itself and gives no way to obtain the pick. An agent that cannot resolve "the boss" cannot tell an authorized override from an ordinary user request, and cannot tell whether a "boss-ruled" line is binding doctrine or a historical note. Confidence: sure the term is undefined in the reader's guaranteed context; the term is presumably obvious inside the project, which is exactly the assumption mode 2 says the file must not make.

**4.** "The document must exist and be complete enough to judge — reviewing is judging the written artifact, never co-writing it."

Defect class: conditional whose condition is a judgment call rather than an observable predicate.

"Complete enough to judge" is a gate on whether the review proceeds at all, but the file supplies no test for it: no required sections, no minimum, no observable signal. Two reviewers will draw the line differently, and a reviewer motivated to decline can always find the document incomplete. Harm: the one gate that can refuse work is unfalsifiable, so refusals and acceptances are both unreviewable; and there is no stated action for the failed case — the file never says what to do when a document is judged not complete enough (return it? ask? review partially?). Confidence: sure.

**5.** "**Review never creates — a finding explains, it does not prescribe (boss-ruled 2026-08-04):** … Designing the fix belongs to the author, and a reviewer who wants to propose an alternative design has left review — that is a create-design task, owned separately."

Defect class: conflict with another sentence in the same file (b).

Lens 5 says: "The finding names the simpler mechanism that suffices — not as a proposal, but as the evidence that the machinery is over-complex." Naming the simpler mechanism that suffices *is* proposing an alternative design; the "not as a proposal, but as evidence" clause relabels the output without changing a word of it. The same collision appears in lens 1 ("needs an empirical probe … Demand probes for genuine unknowns"), lens 9 ("needs a stated bound — retention, archival, or …"), and lens 10 ("require a second, adversarial layer — load, scale …"), each of which instructs the reviewer to specify a remedy. Harm: a reviewer running lens 5 must either violate the no-prescribe rule or emit a finding lens 5 declares insufficient ("the evidence that the machinery is over-complex" is precisely the named alternative). Since the no-prescribe rule is stamped as a ruling, the two are not resolvable by reading order. Confidence: sure for lens 5; the lens 1/9/10 cases are weaker, because "needs a bound" states a required property rather than a chosen design, but the file draws no such distinction anywhere, so a literal reader has no basis to treat them differently.

**6.** "Review a written document before its content gets expensive: a finished design before anything is built from it, and doctrine before it binds readers."

Defect class: conflict with another sentence in the same file (b).

"When NOT to use" says: "Routine re-review of long-shipped doctrine — run a deliberate consistency sweep instead; this skill gates changes, not the archive." Gating *changes* to shipped doctrine means reviewing text that already binds readers, which the opening sentence excludes by its own words ("before it binds readers"). Line 29 confirms re-reviews are in scope ("A re-review always reads the whole document"), and line 54 cites "a legacy doctrine-file review" as a run that happened. Harm: an agent asked to review a one-line edit to a doctrine file that has been live for months gets contradictory answers — out of scope by the opening sentence, in scope by "this skill gates changes". Confidence: sure the two sentences disagree; unsure how the author partitions "change to shipped doctrine" from "routine re-review of long-shipped doctrine", since no observable difference is given (see finding 45).

**7.** "Input: the path to the document — a pair doc (`docs/issues/<n>-<slug>.md`, an issue's companion document), a spec (`docs/cross-project/`), a skill file, CLAUDE.md, a rule page (paths relative to the repo root)."

Defect class: unexecutable by a zero-context reader (e).

Two of the five input kinds cannot be resolved. "A rule page" is an undefined term with no path, no directory, and no example — the file uses it again nowhere, so a reader cannot recognize one or find one. "CLAUDE.md" is offered as an input type, but this checkout contains no CLAUDE.md at any level (verified), so the example names a file the reader cannot locate; a reader may reasonably conclude the input list describes a different repository than the one they are in. Harm: this is the sentence that tells the agent what it is allowed to accept as a target; two of its five categories are unusable, so a target that is neither a `docs/issues/` pair doc, a `docs/cross-project/` spec, nor a skill file cannot be classified as in-scope or out-of-scope. Confidence: sure for "a rule page"; sure that CLAUDE.md is absent from this checkout, unsure whether the author intends the input list to describe this repository or the family of repositories the skill may be copied into.

**8.** "Pick the mode by what the document IS, not by the state of the system around it: a design nothing has been built from yet gets the soundness checklist; a doctrine or instruction file gets the clarity review; a document that is both — doctrine carrying designed mechanisms — gets both, in separate passes."

Defect class: self-contradictory (a).

The rule forbids using the surrounding system's state, then the first branch is defined entirely by the surrounding system's state: "a design nothing has been built from yet" is a fact about the build, not about the document. Nothing in the document itself changes when the first line of implementation lands. Harm: the reader is given a discriminator and, in the same sentence, an instance that violates it, so they cannot tell which of the two the author meant to bind — a reader who follows the stated principle classifies purely by document type and ignores build state; a reader who follows the example checks the repository first. These produce different modes for the same file. Confidence: sure.

**9.** "a design nothing has been built from yet gets the soundness checklist; a doctrine or instruction file gets the clarity review; a document that is both — doctrine carrying designed mechanisms — gets both, in separate passes."

Defect class: unexecutable — the branch set does not cover a reachable case (e).

A design document that *has* been partly built from matches no branch: it is not "a design nothing has been built from yet", it is not a doctrine or instruction file, and it is not "doctrine carrying designed mechanisms". This case is reachable and common — a design revised mid-build, which line 29 explicitly contemplates ("a light revision may earn a single good-tier pass … a heavy revision earns the full grid"). The description's exclusion "not for reviewing an implementation against its design" does not cover it either, since reviewing the revised design is not comparing it to an implementation. Harm: for the exact document most likely to be re-reviewed, the mode-choice rule is silent, and the agent must guess. Confidence: sure the case is uncovered; unsure whether the author considers a partly-built design to still be "a design" for branch-one purposes, in which case the qualifier "nothing has been built from yet" is doing harm it was not meant to do.

**10.** "Steps 1–4 and 6 apply in both modes; step 5 is discharged by the clarity matrix in mode 2." — and the step list that follows.

Defect class: unexecutable because the procedure assumes missing context (e); supports two incompatible readings (c).

No step names its performer. In mode 1, line 29 says "the lenses fan out — one focused agent per lens … each handed the document and its question; the invoker synthesizes", so at least two distinct actors exist, but the numbered steps never say which of them does step 1 ("Read the whole document, in full"), step 2 (write out your understanding), or step 4 (spot-check). Reading A: every step is the invoker's, and the lens agents only execute step 3's checklist. Reading B: each dispatched agent performs steps 1–4 on its own, and the invoker performs step 6. These differ in cost by roughly the agent count and in output shape entirely — under reading B, eleven lens agents each produce a full step-2 restatement. Harm: the file's central procedure has an unassigned actor at every step, and the only actor-clarifying text is a parenthetical two paragraphs earlier ("This step is invoker-side preparation") that covers step 2 alone. Confidence: sure that the performer is unstated; the step-2 parenthetical shows the author knows the ambiguity exists for one step and did not resolve it for the others.

**11.** "**Write out your understanding of each mechanism, rule, and load-bearing claim — subtleties elucidated — before hunting defects:** edge behavior, boundary conditions, what is not covered, what it does to adjacent state; as exact as the document permits, with unresolved gaps listed as gaps rather than filled by guessing."

Defect class: demands work an agent cannot reasonably complete — enumeration over an open set with no stop rule (f).

"What is not covered", written out for *each* mechanism, rule, and load-bearing claim, is the complement of a specification: the set of situations a document does not address is unbounded and cannot be enumerated. Lens 4 solves the same problem correctly by fixing the axes ("actor states … dependency failures … concurrency") and then explicitly capping the obligation ("The enumeration prompts the reviewer; it does not bind the document to a transcript of every cell"); step 2 has neither the axes nor the cap. Harm: the step is the mandatory precondition for defect-hunting ("before hunting defects"), so an agent that takes the stop rule seriously never reaches the hunt, and one that does not take it seriously silently decides how much is enough — which is the mood-dependence the file says the fixed checklists exist to remove. Confidence: sure.

**12.** "A divergence between your written understanding and the document's words is a finding — after ruling out that you simply misread clear text: either the document permitted your misreading, or your correct model contradicts it."

Defect class: conflict with another sentence in the same file (b); condition is a judgment call.

Line 48 rules the opposite for the same observable event: "**A confusion flag is never dismissed as the reviewer's ignorance (boss-ruled 2026-08-04):** the reviewer's guaranteed context is the instruction floor plus the document, so a concept that confused them was missing from both". Step 2 instructs the reader to first rule out that they "simply misread clear text" — i.e. to dismiss the divergence as their own error — which line 48 forbids. The parenthetical "(This step is invoker-side preparation — in mode 2, the delegated restate cells do their paraphrasing separately and innocently)" scopes step 2 to the invoker, but line 48's rule is stated about "a confusion flag" without restricting it to cell-produced flags, and the invoker's misreadings are evidence of the same defect for the same stated reason. Additionally, "ruling out that you simply misread clear text" cannot be executed from inside: the reviewer's judgment that the text was clear is the very judgment the restatement exercise exists to distrust. Harm: divergences the method is designed to surface get suppressed at the moment of discovery by the reader best placed to report them. Confidence: sure the two sentences instruct opposite actions; unsure whether the author considers the invoker-side scoping sufficient to separate them, since the file never says the two rules address different populations.

**13.** "**Write out your understanding … — before hunting defects**" (step 2) versus "Two pass types, and **they run in SEPARATE agents — never one agent doing both**: a single agent doing one task first is primed for the second (a defect-hunt frame makes its restatement adversarial; a restatement frame makes its hunt post-hoc)."

Defect class: conflict with another sentence in the same file (b).

Step 2 mandates precisely the sequence line 45 declares invalid — restate first, then hunt — performed by one agent, the invoker. Line 45's stated mechanism for why this fails ("a restatement frame makes its hunt post-hoc") is a property of doing both tasks in one context, and the invoker's context is not exempt from it. Step 2's parenthetical says the delegated cells paraphrase separately, which explains why the *cells* are safe but leaves the invoker doing both. Harm: whichever rule the reader honors, they violate the other — skipping step 2 to protect the invoker's hunt, or performing step 2 and accepting a post-hoc hunt the file says is compromised. In mode 2 specifically, both rules apply to the same agent at the same time. Confidence: sure.

**14.** "Every finding names the specific location and explains the defect to fix-ready depth — what is wrong, when it does harm, why — never a vague concern, never a proposed fix, and **never a severity or importance rating** (boss-ruled 2026-08-04)".

Defect class: conflict with another sentence in the same file (b).

Step 6 says: "The invoker — the one agent holding full context — assigns each finding's severity here, and only here: HIGH = … MED = … LOW = …". Step 3 says "Every finding" never carries a severity rating; step 6 says every finding gets one. The intended resolution is presumably by role (cells never rate; the invoker rates), but step 3 does not say "a cell's finding" — it says "Every finding", and step 3 is declared to apply "in both modes", including mode 1 where the invoker also produces findings. Harm: a reader following step 3 literally strips severity from the final deliverable, defeating step 6's ordering rule ("Order by severity, consequence breaking ties"); a reader following step 6 literally attaches severity to every finding, violating a stamped ruling. Confidence: sure the literal texts conflict; the role-based reading is available but is not stated in step 3.

**15.** "Coverage over self-censorship: report what you are unsure of, with the uncertainty stated; filtering is the synthesis's job."

Defect class: unexecutable — names a job no described role performs (e); conflict (b).

The synthesis is fully specified in line 56 and contains no filtering step. The merge agent is defined as "independent, one job, zero judgment" and explicitly forbidden to filter: "nothing dropped or filtered, uncertainty wording preserved verbatim". The author's described jobs are reading the merged file, assigning severity, comparing restatements against intent, planning the second pass, and rewriting — none of which is filtering, and step 6's output rule ("An unconfirmed high-consequence finding is HIGH (unconfirmed), never buried") pushes against dropping findings. Harm: cells are told to over-report on the promise that a later stage will filter, and no later stage does, so the promised safeguard against noise does not exist — the measured 191-raw/110-distinct volume in line 56 lands on the author unfiltered. Confidence: sure that no described role filters; unsure whether the author counts severity assignment as filtering, which would make LOW the discard bucket — but the file never says so.

**16.** "A cell states only its own confidence — sure, or unsure and why." (step 3, declared to apply in both modes)

Defect class: unexecutable term (e); term collision that supports two incompatible readings (c).

"Cell" is used here for the first time and is never defined anywhere in the file; the closest thing to a definition is line 52's "{restate, defect-hunt} × {good, floor} × {each available runtime} … eight cells", which is mode-2-only and appears three sections later. Worse, "cell" carries a second, unrelated meaning in mode 1: lens 4's "require the document to name or explicitly discard the reachable, consequential cells" and "the best catches live in cells the design's own story never visits" mean state-space cells, and lens 10's "A plan that maps the design's own cells" means the same. So in step 3 — a both-modes step — "a cell" reads as a review agent under mode 2 and has no referent at all under mode 1, where the units are lenses and lens agents. Harm: a mode-1 reader cannot tell whether "A cell states only its own confidence" binds their lens agents; and the collision defeats search, since grepping `cell` across the project returns two unrelated concepts, which is exactly the greppability failure lens 11 exists to prevent. Confidence: sure both meanings are present; sure "cell" is undefined at first use.

**17.** "When a load-bearing claim can be settled by one command or one file-read — a cited file exists, a quoted line matches, a commit landed — check it … When checking would be hard, laborious, or impossible, do not attempt it — mark the claim *unverified*".

Defect class: the two branches are not exhaustive (e); the second condition is a judgment call.

A claim settleable by three commands is neither "one command or one file-read" nor "hard, laborious, or impossible", so the rule gives no instruction for it — and most real verification (does this script exist, is it wired into the hook config, did it ever run) is two to four commands. "Hard" and "laborious" are unmeasurable: no time budget, no command count, no file count. Harm: the discriminator that decides how much verification a review performs — the thing the boss ruling was issued to bound — has an unruled middle that covers the common case, so reviewers will diverge widely and the ruling's intent ("verifying everything is overreach") is not actually operationalized. Confidence: sure.

**18.** "Exhaustive mechanical checking belongs to code when it is worth doing at all, never to a reviewer's afternoon." versus lens 2's "Verify each label against ground truth (step 4)."

Defect class: absolute claim broader than can hold, with a counterexample inside the same file (b).

Lens 2 requires verifying *each* EXISTS/NEW label; step 4 restricts verification to "load-bearing claims only" and forbids exhaustive checking. A design that labels forty components as existing presents forty cheap, one-command checks: lens 2 demands all forty, step 4 calls exactly that pattern overreach, and the "(step 4)" pointer in lens 2 asserts the two are consistent when they are not. Harm: the pointer is the misleading part — a reader following lens 2 to step 4 finds a rule that contradicts the instruction that sent them there, and there is no stated tiebreak. Under the step-4 reading, the label lens becomes selective and the "biggest source of design confusion we have observed" is sampled rather than checked; under the lens-2 reading, the boss's overreach ruling is voided. Confidence: sure.

**19.** "Dispatch fresh subagents against the same document, spawned with nothing but the task (no session context rides along), on each available runtime."

Defect class: wrong/impossible when obeyed literally (d); conflict (b).

Two problems. First, "nothing but the task" is not achievable for a subagent on either runtime: a Claude subagent inherits a system prompt, a tool set and working directory, and the Codex path in `scripts/d-review-codex-cell.py` runs `codex exec -C <repo root>` with a read-only sandbox, so the agent has the whole repository available. Second, it conflicts with line 48, which *defines the required context* for the defect-hunt reader as "the checkout's instruction file (CLAUDE.md / AGENTS.md), the document itself, and the files the document explicitly references by path" — three things, not "nothing but the task". Harm: an invoker obeying line 24 literally would withhold the instruction file that line 48 makes load-bearing for judging whether a concept is undefined; the whole "a confusion flag is never dismissed" ruling rests on the reviewer having had that floor. Confidence: sure the two sentences specify different context sets; the "no session context rides along" parenthetical shows the intent is "no *conversation* context", but the words say more than that.

**20.** "Dispatch fresh subagents … on each available runtime." and "**The matrix:** {restate, defect-hunt} × {good, floor} × {each available runtime} — with both runtimes available, as today, eight cells."

Defect class: conditional whose condition is a judgment call rather than an observable predicate (also (e)).

"Available" is never given a test. Is a runtime available if `codex` is on PATH? If the CLI authenticates? If the pinned model ids still resolve? The cell count — and therefore the entire matrix — is a function of this untested predicate, and "as today" pins the answer to an unstated date-of-writing rather than to a check the reader can run. Harm: an agent whose `codex exec` fails must decide whether it just observed "runtime unavailable" (proceed with four cells, a legitimate matrix) or "the run is broken" (stop), and the file supports both; the script does distinguish exit codes (2 for bad invocation, otherwise codex's own), but nothing in the file maps those to availability. Confidence: sure.

**21.** "**Get independent passes.** … Dispatch fresh subagents against the same document … For a doctrine file, the clarity-review matrix below IS this step." versus "**Running it:** the lenses fan out — one focused agent per lens or per related group … the invoker synthesizes."

Defect class: supports two incompatible readings (c).

The file states explicitly that mode 2's matrix *is* step 5, and states nothing equivalent for mode 1. Reading A: the lens fan-out is mode 1's step 5, by symmetry. Reading B: the lens fan-out discharges step 3 (it is introduced under Mode 1's "Running it", and step 3 is "Run the chosen mode's checklist"), and step 5 additionally requires a separate set of fresh whole-document subagents on *each available runtime* — a cross-runtime requirement that appears nowhere in Mode 1's own procedure. Harm: the two readings differ by an entire second wave of agents and by whether mode 1 has a Codex leg at all; line 29's degraded-mode sentence ("with no subagent facility, one reviewer working the lenses serially is the accepted degraded mode") suggests the lenses are the delegation story, which would leave mode 1 with no independent-pass requirement despite step 5 applying to it. Confidence: sure the file resolves this for mode 2 and leaves it open for mode 1.

**22.** "The invoker — the one agent holding full context — assigns each finding's severity here, and only here" versus "Then the **author** reads that one file with full context … assigns all severity at step 6" and "the author never reviews their own text — that is step 5's warning".

Defect class: self-contradictory across the role vocabulary (a)/(b); unexecutable in the ordinary case.

Both "the invoker" and "the author" are described as the agent holding full context and as the assigner of severity, so either they are the same agent or the file has two "the one agent holding full context". If they are the same agent — the normal case, since an author reviewing their own draft is who reaches for a review skill, and the repository's own `d-review-records/2026-08-04-d-review-skill-self-review/` shows this skill being run on itself — then "the author never reviews their own text" is violated by the author performing steps 1–4 and 6. If they are different agents, then line 56's "no one else holds the intended meaning" says the invoker cannot perform the restatement comparison, and the file never says how the author and invoker divide steps 1–6. A third role name, "the context-holder", appears in line 54 ("the context-holder rules on each") without definition and may be a fourth name for the same agent. Harm: the file's central safety property — separation of author from reviewer — has no consistent assignment of who does what, and the most common invocation pattern violates it on its face. Confidence: sure the role names collide; unsure which collapse the author intends.

**23.** "End with one line: sound · sound-with-named-risks · not-ready-because-X, where X is the single blocking reason."

Defect class: wrong when obeyed literally (d).

A document can have two or more independent blocking reasons. The format admits exactly one, and the instruction says "the single blocking reason", presupposing uniqueness rather than instructing the reviewer to pick the worst. Harm: obeying the words on a document with three blockers forces the reviewer to name one and silently drop two from the one line that most readers will read; a reader who sees the named blocker fixed will reasonably believe the document is now ready. Confidence: sure. (Secondary, unsure: the three verdicts are phrased for designs — "sound" is an awkward verdict for a mode-2 clarity review of doctrine, and the file gives no mode-2 alternative even though step 6 applies in both modes.)

**24.** "Order by severity, consequence breaking ties, each explained to fix-ready depth." versus "ordered by **document position — never by any cell's opinion or rating**: report order pollutes the author's judgment as their context fills, and document order is the one ordering that carries nobody's".

Defect class: supports two incompatible readings (c).

Step 6 mandates severity ordering; line 56 mandates document ordering and states a general reason — that ordering by any rating pollutes the reader's judgment — which applies equally to the invoker's severities in step 6. The two rules can be reconciled by scoping (merged cell file: document order; final findings: severity order), but neither sentence carries that scope, and line 56 ends with "Then findings as in step 6", placing them in one pipeline. Harm: if the preserved record is the step-6 output, the "never by any cell's opinion or rating" guarantee is lost in the artifact that survives; if it is the merged file, the author's severity work is not preserved. Confidence: unsure — the scoped reading is plausible, but the absolute "never" and the generality of the stated rationale make the conflict readable as real.

**25.** "**A re-review always reads the whole document (boss-ruled 2026-08-04)** — design defects are global, and an edit collides with unedited text as often as with itself (measured: several of the first full-grid run's catches were changed-versus-unchanged conflicts)."

Defect class: absolute/quantitative claim broader than the cited evidence can hold (with the file's own lens as the counterexample standard).

"As often as" is a frequency claim — equal rates for two collision classes — and the parenthetical labels it "measured" while supplying only "several … catches" from one run, with no denominator and no count of the comparison class. Lens 7 requires exactly this distinction: "Each load-bearing mechanism is measured (probe, canary, field observation), guaranteed …, or merely believed. Believed plus load-bearing is a named risk until measured." Harm: the sentence is the stated justification for a boss ruling that fixes the cost of every re-review at whole-document scope; presenting a believed rate as measured makes the ruling look empirically settled and discourages the measurement that would confirm or refute it. Confidence: sure the evidence given does not support "as often as"; unsure whether fuller measurements exist in `d-review-records/` that the sentence is summarizing.

**26.** "What scales with revision size is the reviewer count, never the text scope: a light revision may earn a single good-tier pass over the full document plus verification of each prior finding's fix; a heavy revision earns the full grid." versus "The full grid runs every time, and every cell reads the whole document."

Defect class: direct conflict between two sentences in the same file (b).

Line 29 says a light revision may run one good-tier pass; line 52 says the full grid runs every time. Both use "the full grid" for the same eight-cell matrix, so this is not a mode-1/mode-2 scoping difference — line 29 is describing the clarity grid while sitting in the Mode 1 section, which compounds the problem. Harm: the rule that decides how many agents a re-review costs has two contradictory answers, one of which ("every time") is stated as an invariant that the pruning discussion immediately after depends on ("Pruning cells is a data question … over tens of preserved reviews"). If light revisions actually run one cell, the accumulating record is not a full-grid corpus and the future pruning analysis is comparing unlike runs. Confidence: sure.

**27.** "a light revision may earn a single good-tier pass over the full document plus verification of each prior finding's fix; a heavy revision earns the full grid."

Defect class: conditional whose condition is a judgment call rather than an observable predicate.

"Light" and "heavy" revision are undefined — no line count, no diff size, no section count, no "touches a load-bearing claim" test. The file elsewhere shows it can write observable predicates (line 23's "one command or one file-read"), so the omission is visible. Harm: the choice between one agent and eight is made by an unmeasured adjective, and the reviewer choosing it is often the author, who has an incentive to call their revision light. Confidence: sure.

**28.** "The reviewable unit is the whole file — and doctrine and design files stay small and atomic partly so that whole-file review stays practical."

Defect class: unexecutable dependence on an unstated, unverifiable world-fact (e).

The sentence asserts as background fact that the corpus consists of small atomic files, and makes the practicality of the whole-file rule depend on it — but nothing in this file or in the reader's guaranteed context establishes or enforces that property, and no size threshold is given. The reachable counterexample is in the input list: `docs/issues/<n>-<slug>.md` pair docs, of which this checkout holds several in the 26–38 KB range, and this SKILL.md is itself 21 KB. Harm: an agent handed a large pair doc is bound by "every cell reads the whole document" and "A re-review always reads the whole document" with no stated fallback, while the sentence that justified those rules assumes a condition the target violates. Confidence: unsure — the claim may be true of the specific documents the author has in mind, but the reader has no way to check it and no rule to fall back on when it fails.

**29.** "A load-bearing claim resting on first-principles reasoning about how the runtime behaves — what loads when, hook ordering, what a session can and cannot see — needs an empirical probe … Conversely, do not manufacture a probe for a fact true by construction — one that follows from the artifact's own definition, so its falsity would make the mechanism itself pointless."

Defect class: self-contradictory (a) — the exemption's test admits the class the rule targets.

The exemption's stated test is "its falsity would make the mechanism itself pointless". That test is satisfied by many genuine runtime-boundary claims: "the hook fires before the tool call" is pointless-if-false *and* is precisely the "hook ordering" example the first half names as requiring a probe. The two halves therefore classify the same claim oppositely — the first sentence demands a probe, the second forbids manufacturing one. The intended test for "true by construction" is presumably "follows deductively from the artifact's definition", which is the first clause; the second clause ("so its falsity would make the mechanism pointless") does not follow from it and is not equivalent to it. Harm: the highest-value lens in mode 1 can be talked out of every probe it should demand, using the lens's own exemption, and the stakes-based tiebreak is explicitly removed ("stake level is not the discriminator"). Confidence: sure.

**30.** "needs an empirical probe (or an authoritative contract that specifies the behavior), not assumption."

Defect class: unexecutable — undefined term (e).

"An authoritative contract" is never defined and no example is given. A reader cannot tell whether vendor documentation, a tool's JSON schema, a source comment, another project doctrine file, or a previous d-review record qualifies. Lens 7 makes the term load-bearing a second time ("guaranteed (by definition or an authoritative contract — lens 1's by-construction class)"), so the same undefined term decides whether a mechanism is classified as guaranteed or merely believed. Harm: the accept/reject decision on a probe demand — and the measured-vs-believed classification that feeds the final severity — turns on a word the reader must define for themselves. Confidence: sure.

**31.** "Every load-bearing rule in a design is backed by something: an enforcement point (a gate, a check, a tool boundary) or a written instruction agents follow."

Defect class: absolute claim broader than can hold (d).

The ordinary counterexample is a rule backed by nothing: stated only in a design document that no agent reads at runtime, with no gate and no instruction placed anywhere an agent encounters it. That is a real and common defect, and it is arguably the most severe one this lens should catch — but the sentence declares the two-way split exhaustive, so a reviewer classifying such a rule must force it into "a written instruction agents follow", which is false, or find the lens has no verdict. The lens then defines its only finding type as "discipline presented as enforcement", which does not cover "nothing presented as discipline". Harm: rules that are backed by nothing are misclassified as discipline-backed and pass the lens. Confidence: sure.

**32.** "Re-evaluating that split — "this prompt rule should be code," or the reverse — is a different problem set, out of this review's scope … — unless the code-versus-prompts choice is itself the subject of the document or section under review, in which case it is reviewed like any other design decision."

Defect class: conditional whose condition is a judgment call, and nearly circular (c).

Whether the code-versus-prompts choice "is itself the subject" of a section is a judgment with no test, and it is close to always true in the direction that reopens the exclusion: any design section that specifies a mechanism has chosen between code and prompt, so a reviewer inclined to raise the issue can declare that the section's subject. Harm: an exclusion stamped as a boss ruling, with a named owner elsewhere, can be reopened at the reviewer's discretion on every mechanism section — which returns the review to the exact debate the ruling was made to route away. Confidence: sure the condition is unmeasurable; unsure how wide the author intends "the subject of … [a] section" to be.

**33.** "For each mechanism, walk the state space systematically: actor states (busy, idle, mid-turn, dead), dependency failures (the file it reads, the tool it runs, the channel it writes), concurrency (two sessions, re-entry, repeated firing) — and require the document to name or explicitly discard the reachable, consequential cells."

Defect class: (noted only for the term collision, see finding 16); otherwise this lens is correctly bounded by the following sentence.

The specific issue is the word "cells", which here means state-space cells and in mode 2 means review agents. Because step 3 applies to both modes and uses "cell" in the mode-2 sense, a mode-1 reader who has just read lens 4 will read step 3's "A cell states only its own confidence" as a statement about state-space cells, which is meaningless. Harm and confidence as in finding 16.

**34.** "The document contradicting itself, its own stated principles, or the project's recorded rulings — the governing plan documents and issue bodies, which the lens agent is given alongside the document."

Defect class: unexecutable — undefined reference (e); conflict (b).

"The governing plan documents" and "issue bodies" are named with no paths, no titles, and no way to identify them; this checkout has `docs/cross-project/nedschorus-founding-plan.md`, `docs/cross-project/git-gatekeeper-design.md` and seven others, plus `docs/issues/` files and, separately, GitHub issues (the file links `https://github.com/nedschorus/nedschorus/issues/42`), and nothing says which set is meant or where "recorded rulings" live. The clause also conflicts with line 29, which says each lens agent is handed "the document and its question" — lens 6 asserts it is additionally given a corpus that line 29 does not mention and that the invoker is never told to assemble. Harm: lens 6 cannot be dispatched as described; the invoker must invent the input set, and different invokers will supply different ones, so the "recorded rulings" check is only as good as an unspecified guess. Confidence: sure.

**35.** "Internal inconsistency is strong evidence of an unexamined call; confirm the exception is not deliberate before flagging."

Defect class: demands work an agent cannot reasonably complete — knowledge of another party's internal state (f); conflict (b).

Confirming that an inconsistency is not deliberate requires the author's intent, which line 56 says the reviewer does not have: "no one else holds the intended meaning". It also runs against line 48's ruling that a reviewer's confusion is never dismissed as their own ignorance. There is no stated channel for the confirmation either — the reviewer is a fresh subagent with no session context (line 24) and cannot ask the author. Harm: the gate is unsatisfiable, so a literal reader suppresses every internal-inconsistency finding — the class this lens exists to produce, and the class this very review is composed of. Confidence: sure.

**36.** "Potentially unbounded data the design accumulates needs a stated bound — retention, archival, or the project's artifact-lifecycle rule that every accumulating store has a named home and a drain — plus a rough volume expectation."

Defect class: unexecutable — undefined reference (e).

"The project's artifact-lifecycle rule" is cited as an existing rule of this project, but it exists in no file the reader is guaranteed: there is no CLAUDE.md or AGENTS.md in this checkout, and the sentence gives no path. The reader is told they may satisfy the lens by invoking a rule they cannot read. Harm: a reviewer cannot tell whether a design that says "records go in `d-review-records/`" has satisfied the artifact-lifecycle rule or not, because the rule's actual requirements are unavailable; the parenthetical gloss ("a named home and a drain") may or may not be the whole rule. Confidence: sure the reference is unresolvable from the guaranteed context.

**37.** "Potentially unbounded data the design accumulates needs a stated bound … plus a rough volume expectation." versus "**Every review preserves its record** — the merged cell-attributed findings, the triage dispositions, and every cell's output … as a dated directory under `d-review-records/`".

Defect class: conflict between a rule and this file's own designed mechanism (b) / wrong when obeyed literally (d).

`d-review-records/` is an accumulating store created by this document: one dated directory per review, holding eight cell outputs plus merged findings and dispositions, growing without limit. The file states no retention, no archival, no drain, and no volume expectation for it — and lens 9 says to "flag the missing bound even when the ceiling looks far off". Compounding it, line 52 makes the store permanently load-bearing ("Pruning cells is a data question … over tens of preserved reviews"), so the design explicitly requires the store to keep growing before any analysis can run. Harm: the file fails its own lens on the only store it creates, which both undermines the lens's authority for readers who notice and leaves the store genuinely unbounded. Confidence: sure.

**38.** "Where the designed thing has an executable surface, require a second, adversarial layer — load, scale, "what did we not anticipate" — that does not assume the design is right."

Defect class: labor with no stop rule (f).

"What did we not anticipate" as a required test layer has no completion condition; it is the same open-set enumeration as finding 11, and unlike lens 4 it is not accompanied by a limiting sentence. The reviewer must judge whether a test plan contains enough of an unbounded category to pass. Harm: the lens can neither be satisfied nor be shown unsatisfied, so it produces either a permanent finding on every design with an executable surface or an arbitrary pass. Confidence: unsure — the phrase may be intended as a category name for generative/adversarial testing (fuzzing and property tests are named in the preceding sentence) rather than as a literal deliverable, but the words place it in a list of required layers.

**39.** "A name, for this lens, is an identifier that anything outside the document will use to find or invoke the thing (boss-scoped 2026-08-04): file and directory names; script, function, and command names; skill names; issue and test labels; defined terms other documents will cite. Ordinary prose vocabulary, one-off words, and local labels defined where they are used (a tier scheme, a severity scale) are not names and are out of this lens's scope."

Defect class: self-contradictory (a).

The definition and the exemption classify the same items oppositely. The tier scheme is `good` and `floor` — and those exact strings are command-line argument values consumed outside the document by `scripts/d-review-codex-cell.py` (`--tier good|floor`, verified in the script's `choices=["good", "floor"]` and its `TIER_TO_CODEX_MODEL` / `TIER_TO_REASONING_EFFORT` keys). By the definition, they are names: identifiers something outside the document uses to invoke the thing. By the exemption, "a tier scheme" is explicitly not a name. They are also exactly the kind the lens flags on sight — one generic word each, with "good" colliding with ordinary prose usage throughout the file ("a single good-tier pass", "*Good* is best at cross-rule contradictions"). Harm: the reader cannot determine the lens's scope for any identifier that is both a local label and an external interface, which is the common case for enum values, mode names, and severity levels that appear in scripts or filenames. Confidence: sure.

**40.** "Every in-scope name must be self-documenting and greppable: full words a search matches verbatim, one shared token across a family of related names, no cryptic abbreviations, no bare sequence labels, and no bare numeric issue references in prose (the number must ride with a descriptive handle)."

Defect class: absolute rule the file itself cannot satisfy (d), plus an ambiguous exemption boundary (c).

"No bare sequence labels" is violated throughout this document by its own cross-reference vocabulary: "Steps 1–4 and 6 apply in both modes", "step 5 is discharged by the clarity matrix in mode 2", "lens 1's by-construction class", "let that label feed lens 7's measured-or-believed judgment", "Mode 1", "Mode 2". These are identifiers other documents and review records will cite ("d-review lens 7"), which the lens's own definition puts in scope; the exemption for "local labels defined where they are used" arguably covers them, and the file gives no way to decide which applies. Harm: a reviewer applying this lens to any numbered document cannot tell whether numbered steps and lenses are findings; and if they are not, the rule loses most of its bite, while if they are, this file is a mass violation. The same ambiguity determines whether finding 39's tier names are in scope. Confidence: sure the tension exists; unsure which side the author intends, which is the defect.

**41.** "The cell's prompt carries no review framing — only the paraphrase template and the target path, nothing else."

Defect class: wrong when checked against the file it names (d).

I read the referenced template, `prompts/restate.md`. It contains: "Do not repair anything, do not fill gaps, and do not substitute what the author probably intended for what the words say" and "many sentences use ambiguous words with several meanings, or jargon, or coined expressions that are hard to interpret out of their normal context." Both prime the reader to expect defective text and to withhold charity — which is review framing by the file's own account, since line 54 identifies charity-suppression as the active ingredient of the adversarial prompt ("Force literal reading; forbid charity; keep the restate template free of review framing"). So the claim "carries no review framing" is false about the artifact it describes, and the last clause of line 54 restates the requirement the template does not meet. Additionally, "nothing else" cannot hold for a Claude cell, which necessarily receives a system prompt and tool set (see finding 19). Harm: the restatement pass's claimed innocence — the property that makes a divergence meaningful evidence — is asserted rather than held, and a reader auditing the template against this sentence will not know whether to fix the template or the sentence. Confidence: sure about the template's contents; unsure only in that "review framing" is not defined, so a narrow reading (no mention of finding defects, which the template indeed avoids) could be defended.

**42.** "a reader with no project history whose entire context is the checkout's instruction file (CLAUDE.md / AGENTS.md), the document itself, and the files the document explicitly references by path" — together with "the remedy is one of three, chosen at triage: define it in the file, add the explicit path reference, or promote the definition to the instruction floor when many files share the concept."

Defect class: wrong/impossible when obeyed literally in this checkout (d).

There is no CLAUDE.md and no AGENTS.md anywhere in `/Users/el/Projects/nedschorus/` (verified). The defined instruction floor is empty, so: the cell's context is document-plus-referenced-files only; and the third remedy — "promote the definition to the instruction floor" — names a destination file that does not exist, with no instruction to create one. Harm: this is the load-bearing premise of the ruling in the next sentence ("the reviewer's guaranteed context is the instruction floor plus the document, so a concept that confused them was missing from both"). With no floor, every project-specific term in every reviewed document is automatically a finding — "the boss", "the governing plan documents", "the project's artifact-lifecycle rule", "postal", and so on — and the triage has only two of its three remedies available. Confidence: sure about the absence; unsure whether the author knows the floor is missing and intends this skill to be portable to repositories that do have one.

**43.** "the reviewer's guaranteed context is the instruction floor plus the document, so a concept that confused them was missing from both"

Defect class: conflicts with the sentence immediately preceding it (b).

The preceding sentence defines the reader's context as three things — instruction file, document, and "the files the document explicitly references by path". This sentence drops the third and reasons from two. The inference is therefore invalid on its own terms: a concept defined in an explicitly referenced file (for example, the tier-to-model mapping documented at the top of `scripts/d-review-codex-cell.py`, which line 50 points to and calls authoritative) is *not* missing from the reviewer's context, yet a reviewer who skipped that file would produce a confusion flag that this rule forbids anyone from dismissing. Harm: the ruling's absolute protection is derived from a premise narrower than the context the file actually grants, so it protects flags that are genuinely the reviewer's failure to read a referenced file — and it does so with a ruling stamp that discourages challenge. Confidence: sure.

**44.** "**A confusion flag is never dismissed as the reviewer's ignorance (boss-ruled 2026-08-04)**"

Defect class: absolute word making a claim broader than can hold, with a counterexample inside this file.

Lens 11 states that "domain-standard tokens (`README`, `checksum`, `SHA-256`) pass". A cell that flags `SHA-256` or `checksum` as an undefined concept is exhibiting ignorance of standard vocabulary, and under this rule that flag cannot be dismissed as such — the three prescribed remedies would force the document to define standard terms or add path references for them, or to promote them to the instruction floor. Harm: the two rules give opposite dispositions for the same flag, and because this one is boss-stamped and absolute, a triager following it inflates documents with definitions of common terms. Confidence: sure the two sentences conflict; unsure whether the author regards "domain-standard token" as an implicit exception, which the file does not state.

**45.** "the remedy is one of three, chosen at triage: define it in the file, add the explicit path reference, or promote the definition to the instruction floor when many files share the concept."

Defect class: closed enumeration that omits an ordinary case (d).

A fourth remedy is routine and often correct: remove or reword the sentence so the confusing concept is not used at all — which is the right disposition when the concept was incidental, or when the flag reveals the sentence should not have been written. A fifth is that the flag reveals a genuine defect elsewhere rather than a missing definition. Harm: "one of three" is stated as exhaustive, so a triager confronted with a confusing sentence that should simply be deleted must instead define a term the document does not need, adding text to fix a problem better solved by removing text. Confidence: sure the enumeration is closed by its wording; unsure how strictly the author intends "one of three" to bind.

**46.** "Every tier-to-model assignment is an operator-set pinned value — the boss picks the models; agents apply the pinned picks and never substitute their own sense of the model landscape, which is months stale by construction (boss-ruled 2026-08-04). Claude-runtime cells are fresh subagents — good = the pinned top model at high effort, floor = the pinned floor model (Sonnet-class today), set per launch."

Defect class: self-contradictory (a) and demands knowledge the agent cannot have (f).

Three problems compound. First, "an operator-set pinned value" and "set per launch" are opposites: a pinned value is fixed in a location and read; a per-launch value is chosen at invocation time. Second, for the Codex leg the pin has a stated location ("The tier-to-model mapping and per-tier reasoning effort sit at the top of the script (authoritative)" — verified: `TIER_TO_CODEX_MODEL` and `TIER_TO_REASONING_EFFORT` in `scripts/d-review-codex-cell.py`), but for the Claude leg no pin location is given anywhere in the file or its referenced paths. Third, the agent is told to use "the pinned top model" while being forbidden to use its own knowledge of the model landscape — so it can neither read the pin nor derive it, and the only hint given, "Sonnet-class today", is prose the same paragraph declares non-authoritative ("any ids quoted in prose are a snapshot"). Harm: the Claude half of an eight-cell matrix cannot be launched as specified; an agent must either guess a model (violating the ruling) or stop. Confidence: sure the Claude pin has no stated location; sure "pinned" and "set per launch" conflict.

**47.** "good = the pinned top model at high effort"

Defect class: wrong/impossible when obeyed literally (d).

Reasoning effort is not a per-launch parameter of the subagent-dispatch interface available to an invoking agent: an agent type's model, reasoning effort and tools come from its definition, and a dispatch call carries a model override, not an effort override. The Codex leg handles this explicitly by passing `-c model_reasoning_effort=…` from the script, and the file notes the pin exists "so a cell does not depend on the machine-local Codex config" — no equivalent mechanism is named for the Claude leg. Harm: the good/floor distinction on the Claude side reduces to the model choice alone, so a provenance stamp claiming an effort level for a Claude cell (required by line 56) records a value nobody set. Confidence: unsure — I am reasoning from the dispatch interface described in my own tooling rather than from a document this file references, and a project-specific launcher I cannot see could expose an effort setting.

**48.** "The templates in [`prompts/`](prompts/) are the single prompt source for BOTH runtimes' cells — one place to improve wording for both legs."

Defect class: conflict between a claimed guarantee and the mechanism described (b) — an instance of the file's own lens 3.

For Codex cells the claim is enforced: the script reads `PROMPTS_DIR / f"{args.cell}.md"` and fails with exit 2 if it is missing. For Claude cells, nothing in this file instructs the invoker to read `prompts/<cell>.md`, use it verbatim, or substitute `{TARGET_PATH}`; the Claude sentence specifies only the tier-to-model mapping. So "single prompt source" is backed by enforcement on one leg and by nothing at all on the other — which is exactly what lens 3 calls "discipline presented as enforcement — a false claim about how the rule is backed", and what the same paragraph promises ("so the two legs cannot drift apart", in the script's docstring). Harm: the Claude leg can silently drift to a paraphrased prompt, and since line 54 says the prompt is the highest-leverage text in the process ("seventeen findings … against two"), drift there invalidates cross-runtime comparison, which is the entire purpose of running both legs. Confidence: sure the Claude-side instruction is absent from the file.

**49.** "*Floor* is defined by capability — the lowest tier that actually reads the file, not the lowest tier that exists (a below-floor model flags mostly its own capability gaps); the framework's subagent default is the current instance."

Defect class: demands work an agent cannot reasonably complete (f); conflict (b); supports two incompatible readings (c).

Identifying "the lowest tier that actually reads the file" requires testing candidate models downward until one fails, with no stop rule, no candidate list, and current-world model knowledge that the preceding paragraph forbids the agent from supplying. The final clause then contradicts the definition it was appended to: if "the framework's subagent default" determines the floor cell's model, the floor is set by a framework default, not by an operator pin ("Every tier-to-model assignment is an operator-set pinned value") and not by the capability search just described; and it conflicts with "floor = the pinned floor model (Sonnet-class today)", since a framework default that equals "the current instance" would run the floor cell on whatever model the invoker is, which is typically the top model, not the floor one. The clause also has at least two readings: (i) the subagent default model is the same model as the currently running agent, so a floor cell launched without an explicit model override is not a floor cell at all; (ii) the framework's default happens to sit at the floor tier, so no override is needed. These prescribe opposite launch behavior. Harm: the floor cell — half the matrix — may silently run at the top tier, and the resulting record would be stamped `tier=floor` with a top-tier model, poisoning the future which-cells-earn-their-keep analysis that line 52 says the records exist to support. Confidence: sure the clause is ambiguous and conflicts with line 50.

**50.** "Pruning cells is a data question — which cells' findings survive context-aware triage, over tens of preserved reviews — decided by analysis of the records below, never by doctrine (boss-ruled 2026-08-04)."

Defect class: unexplained reference (e); plus a self-referential absolute.

"The records below" has no referent: no section below is titled or introduced as records. The nearest candidate is the record-preservation requirement inside the Synthesize paragraph, which points at `d-review-records/`, but "below" pointing at a clause two paragraphs later inside an unrelated heading is not a resolvable reference for a first-time reader, and "the records" is not the store's name. Separately, "never by doctrine" is asserted in a doctrine file, by a doctrine sentence, as the doctrine governing how pruning decisions are made — so obeyed literally it disqualifies itself. Harm: the reader cannot locate the data set the rule depends on; and the self-referential absolute gives no way to distinguish "doctrine may not decide which cells to prune" (presumably intended) from "no doctrinal statement about pruning is binding" (what the words allow). Confidence: sure about the dangling "below"; the self-reference point is minor and I am less sure it does practical harm.

**51.** "(The clarity cells run on today's runtimes; a Codex *wrapper of this skill* — the runtime-parity question — is separate and arrives at companion admission.)"

Defect class: unexecutable — undefined jargon (e).

"Arrives at companion admission" is not decodable from anything in the reader's guaranteed context: "companion admission" is defined nowhere in this file, appears in no referenced file, and is not standard vocabulary. It could mean a future event (when a companion agent or runtime is admitted to the fleet), a document class, or a process gate. "Today's runtimes" has the same problem in miniature — "today" is undated in a file whose other date references are explicit. Harm: the parenthetical is the file's only statement about runtime parity, and a reader cannot tell whether it defers work, forbids work, or names a precondition; an agent asked to build a Codex wrapper cannot tell whether the precondition is met. Confidence: sure.

**52.** "land changes deliberately (the context-holder rules on each, ideally micro-tested), never as silent drift (boss-ruled 2026-08-04)."

Defect class: unexecutable — undefined term (e); role-vocabulary collision.

"The context-holder" appears once, is never defined, and is a fourth role name alongside "the invoker", "the author", and "the merge agent" — with line 25 and line 56 both already claiming the "holds full context" description for two different names (see finding 22). A reader cannot tell whether the context-holder is the invoker, the author, or a third party, and therefore cannot tell who is authorized to approve a template change. "Ideally micro-tested" also states no threshold: "ideally" makes the test optional, so the rule's only verification step is discretionary. Harm: the file declares the templates "the most leveraged text in the whole process" and then leaves their change-control owner unnamed. Confidence: sure the term is undefined.

**53.** "First a **merge agent** — independent, one job, zero judgment — folds all cell reports into ONE file: hunt findings deduped (the same sentence flagged with the same complaint is one entry, all catching cells listed; the same sentence with different complaints stays adjacent entries), nothing dropped or filtered, uncertainty wording preserved verbatim".

Defect class: self-contradictory (a).

Three incompatibilities in one sentence. First, "zero judgment" versus deduplication: deciding whether two cells flagged "the same complaint" or "different complaints" about the same sentence is a semantic judgment — two cells will describe one ambiguity in different words, and the file gives no matching rule. Second, "nothing dropped" versus "deduped": deduplication drops entries by construction; the parenthetical partly rescues this ("all catching cells listed"), but the words "nothing dropped" and "deduped" still stand in direct opposition, and the file later repeats the instruction as "Dedupe across cells" with measured drop rates (109 raw to ~35 distinct; 191 raw to 110 distinct — that is 81 and 81 entries not present in the merged file). Third, "uncertainty wording preserved verbatim" is unsatisfiable for a deduped entry: when three cells each state their own confidence in their own words and become "one entry", the sentence does not say whether all three wordings are carried or one is chosen — and choosing is judgment. Harm: the merge role is defined as mechanical precisely so its output can be trusted as unfiltered, and every one of its three stated obligations requires the judgment it is denied; an agent given this role will either apply hidden judgment or refuse to dedupe. Confidence: sure.

**54.** "cells report observations, never importance (measured on the first full-grid run: the raw stream arrived pre-labeled "47 HIGH" by its cells, and the labels, not the content, framed the first triage)"

Defect class: absolute contradicted by the evidence attached to it (d).

The clause states as fact that cells never report importance, and its own parenthetical documents cells reporting importance on the only full-grid run cited. The intended meaning is presumably normative — cells *must not* report importance — but the sentence is written descriptively and is used to justify the merge agent's ordering rule, so a reader may conclude the pre-labeling problem is solved when the measurement says it is not. Harm: the file's guard against cell-assigned severity is the prompt template's instruction, and the measured run shows that instruction being violated; presenting the violation and the "never" together obscures that the guard is unreliable and that the merge agent may need to strip labels — which the merge agent's "nothing dropped or filtered, uncertainty wording preserved verbatim" rule forbids it from doing. Confidence: sure.

**55.** "as a dated directory under `d-review-records/`"

Defect class: unexecutable — incomplete specification (e).

The path is unanchored: `d-review-records/` is given with no root, and the file's only anchoring statement — "(paths relative to the repo root)" — sits in the input-path sentence in a different section and is scoped there to review targets. A reader could place it relative to the current working directory or the skill directory. (In this checkout it exists at the repository root, but that is not derivable from the file.) The directory-name format is also underspecified: "a dated directory" gives no date format and no naming convention beyond the date, while the existing entries follow `YYYY-MM-DD-<subject>` (`2026-08-03-d-review-skill`, `2026-08-04-d-review-skill-self-review`). Harm: records from different reviews land in different places or under inconsistent names, which directly damages the future cross-review analysis the store exists for; and lens 11's "one shared token across a family of related names" cannot be satisfied by a convention the file does not state. Confidence: sure the anchoring and the naming format are unstated.

**56.** "each file stamped with its provenance: runtime, exact model id, effort level, cell, tier … the Codex cell script stamps its own, Claude cell files are stamped when saved"

Defect class: demands work an agent cannot reasonably complete (f); actor unnamed.

"Exact model id" is available on the Codex side (the script prints `model={model or 'config-default'}` from its pinned table, verified) but not on the Claude side: the invoker selects a subagent model by alias, not by exact id, so the invoker cannot stamp an exact id, and the cell's self-report of its own id is not something the invoker can verify. "Effort level" has the same problem (finding 47). "Claude cell files are stamped when saved" names no actor and no format — passive voice where the Codex counterpart has an executable mechanism. Harm: the stamp exists specifically because "tier names drift across model eras; pins do not", so an unstampable or self-reported Claude id defeats the stated purpose for half the matrix, and the future analysis cannot distinguish model eras on the Claude leg. Confidence: unsure on the exact-id point for the same reason as finding 47 — I am reasoning from the dispatch interface I can see rather than from a referenced document; sure that no actor or format is specified for the Claude stamping.

**57.** "The **author** compares restatements against intent — no one else holds the intended meaning, and a comparator without it watches a faithful paraphrase of broken text agree with the text and misses the defect." together with "The two roles never mix: the cells generate the findings (the author never reviews their own text — that is step 5's warning)".

Defect class: self-contradictory (a); unexecutable in a case the file itself cites (d).

Comparing restatements against intent and deciding which divergences are findings *is* reviewing one's own text — the file assigns the author a finding-producing role in one clause and forbids the author any reviewing role in the next. Separately, "no one else holds the intended meaning" makes the comparison unexecutable for any document whose author is unavailable — an inherited doctrine file, a document written by a departed agent, or the "legacy doctrine-file review" line 54 cites as a run that already happened. In that case the restatement pass still runs (line 52: "The full grid runs every time"), producing four restatement reports with no one able to compare them. Harm: half the matrix produces output that cannot be consumed, and the file gives no fallback comparator and no instruction to skip the restatement cells. Confidence: sure on both points.

**58.** "A bad rewrite is caught by the next review round, not by restricting the author."

Defect class: wrong when obeyed literally (d) — the stated safety net is not mandated anywhere.

The sentence is the sole justification for letting the author rewrite unsupervised, and it asserts a next review round as a given. No rule in the file requires one: line 29 describes how a re-review *would* be scoped ("a light revision may earn a single good-tier pass … a heavy revision earns the full grid") but never says a re-review must occur, and step 6 ends the procedure with a one-line verdict. "When NOT to use" then discourages re-review of long-shipped doctrine. Harm: an author's rewrite can land with no second pass, and the safety property the file relies on to justify unrestricted rewriting silently does not hold; the very first rewrite after a review is the one most likely to introduce new defects, since it touches every flagged passage at once. Confidence: sure that no sentence in the file mandates the next round.

**59.** "Dedupe across cells — expect heavy overlap (first NedsChorus run, 2026-08-03: an under-scaled five-cell pass over a ~120-line skill returned 109 raw flags, ~35 distinct; the first full grid returned 191 raw, 110 distinct)."

Defect class: name that is hard to find by search.

The project appears here as `NedsChorus` and elsewhere in the same file as `nedschorus` (`https://github.com/nedschorus/nedschorus/issues/42`), and the checkout directory is `nedschorus`. Lens 11 requires "full words a search matches verbatim" and "one shared token across a family of related names"; a case-sensitive search for either spelling misses the other. Harm: small, but this is the project's own name in its own doctrine, and the file's naming lens is the standard being applied — a reader cannot tell which casing is canonical when creating new artifacts, so the split propagates. Confidence: sure the two spellings appear; unsure whether the author considers `NedsChorus` a legitimate prose rendering distinct from the repository identifier, which the file does not say.

**60.** "Code correctness, or an implementation reviewed against its design — a code-review skill's lane (the review-change candidate owns it when built), not this one's."

Defect class: unexecutable — undefined reference (e); a name that is not self-documenting.

"The review-change candidate" is an identifier for a thing outside this document — a proposed skill — and is therefore in scope for lens 11, but it is not self-documenting: "review-change" parses as "review a change" or "a change to reviews", and "candidate" is unexplained project jargon for a proposed-but-unbuilt item. It appears nowhere else in this file, has no path, no issue link, and no definition, and "when built" confirms it does not exist. Harm: the exclusion tells the reader to route code review elsewhere and names a destination they cannot find or verify, so the routing instruction is inert; a reader also cannot tell whether the skill exists yet, which determines whether the exclusion is currently actionable. Confidence: sure.

**61.** "Routine re-review of long-shipped doctrine — run a deliberate consistency sweep instead; this skill gates changes, not the archive."

Defect class: unexecutable — undefined procedure (e); conditional whose condition is a judgment call.

"A deliberate consistency sweep" is presented as the alternative action, in the imperative ("run"), but it is not defined, not named as a skill, not given a path, and not described anywhere in this file. A reader following the instruction has nothing to run. "Routine" is likewise unmeasured: the reader must decide whether a given re-review is routine, and the file offers no test, while line 6's opening scope and line 29's re-review rule both push the other way (findings 6 and 26). Harm: the only exclusion with a prescribed substitute prescribes a substitute that does not exist, so the practical effect is either doing nothing or doing the excluded review anyway. Confidence: sure.

---

clean sections: none — every section (YAML frontmatter, the opening "Design review (d-review)" prose, "Input and mode choice", "Steps", "Mode 1 — the design-soundness checklist", "Mode 2 — the clarity review (doctrine and instruction files)", and "When NOT to use") carries at least one finding above.
