<!-- provenance: runtime=claude model=claude-opus-5 effort=session-inherited role=merge-agent (zero-judgment merge; model id read from subagent transcript) inputs=eight-cell-grid target=.claude/skills/d-review/SKILL.md session=4cf7d488 date=2026-08-04 -->

# Merged cell findings — d-review SKILL.md self-review, 2026-08-04

Input files merged (eight cell reports, all in this directory):
`claude-restate-good.md`, `claude-restate-floor.md`, `claude-hunt-good.md`, `claude-hunt-floor.md`, `codex-restate-good.md`, `codex-restate-floor.md`, `codex-hunt-good.md`, `codex-hunt-floor.md`.

Raw hunt findings vs. distinct entries: **185 raw** (claude-hunt-good 61, claude-hunt-floor 20, codex-hunt-good 55, codex-hunt-floor 49) → **132 distinct entries** after dedupe, plus **29 restatement-note passages**.

Entries are ordered by the position in `SKILL.md` of the sentence they target, top of file to bottom. Restatement notes for a section follow that section's hunt entries.

---

## Frontmatter

### [Frontmatter] — "`name: d-review`"
- Complaint: `d-review` is a skill name — the exact category lens 11 puts in scope — and `d` is a cryptic single-letter abbreviation for "design", expanded nowhere except the section heading; it could mean design, document, doctrine, defect, or delegated. Lens 11 requires in-scope names to be self-documenting and greppable with "no cryptic abbreviations", and adds that a one-word name is a finding candidate by default. A reader searching for "design review" tooling matches nothing, and the abbreviation propagates into `d-review-records/` and `scripts/d-review-codex-cell.py`, so the whole name family inherits it — the propagation cost lens 11 itself warns about. The document never states that its own name is exempt.
- Cells: claude-hunt-good, claude-hunt-floor, codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure the sentence-level conflict exists; I cannot judge whether the name predates the lens or was deliberately grandfathered, because the file says nothing about exempting itself." · claude-hunt-floor: "unsure — the greppability criterion arguably passes (it is the literal skill directory name), and the lens may implicitly apply only to names *within a reviewed design*, not the reviewing skill's own name — but this exemption is never stated." · codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Frontmatter] — "Use when a document is about to be built from or landed, or when the boss says "d-review this" — his ask wins over the exclusions."
- Complaint: "The boss" is never defined in this file, and the checkout has no CLAUDE.md and no AGENTS.md, so the defined instruction floor for a reader of this file is empty and "the boss" resolves to nothing. A zero-context reader cannot tell whether this means the repository owner, the current user, a manager, or another agent, so cannot determine whose request overrides the stated exclusions; nor can they tell whether a "boss-ruled" line is binding doctrine or a historical note, or obtain the model picks that "the boss picks the models" requires.
- Cells: claude-hunt-good, codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure the term is undefined in the reader's guaranteed context; the term is presumably obvious inside the project, which is exactly the assumption mode 2 says the file must not make." · codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Frontmatter] — "Use when a document is about to be built from or landed, or when the boss says "d-review this" — his ask wins over the exclusions."
- Complaint: Taken literally, the override lets the skill be pointed at code correctness or an implementation-vs-design review — precisely the two things the preceding sentence excludes — but every executable path in the file assumes a written document. "Pick the mode by what the document IS" offers exactly three branches, and a source file is none of the three; mode 1's lenses ask about assumptions, EXISTS-vs-NEW labels and build order, and mode 2's cells hunt sentence defects in prose. An agent obeying the override literally has an in-scope invocation with no applicable mode and no instruction for what to do instead — it will improvise a code review the file explicitly disclaims competence for, or stall.
- Cells: claude-hunt-good, claude-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure that the override creates a state the rest of the file does not cover; unsure whether the author intends the override to be scope-only (still apply the closest mode) or full (do whatever the boss asked), because the sentence supports both." · claude-hunt-floor: "unsure — it's plausible the override was meant only for the archive-exclusion (line 61) rather than the domain-exclusion, but the sentence draws no such distinction and reads as "the exclusions" (plural, unqualified)."

### [Frontmatter] — "his ask wins over the exclusions"
- Complaint: "Wins over the exclusions" can mean overriding only the two immediately preceding exclusions, or overriding every exclusion and prerequisite in the description, including "The document must already exist" and "never co-writes it." Those readings produce different behavior when the named person asks for code review, implementation review, co-writing, or review of a nonexistent draft.
- Cells: codex-hunt-good
- Confidence (verbatim per cell): codex-hunt-good: "sure."

### Restatement notes — Frontmatter
- claude-restate-good: "Two timing conditions are given, both of which are "before" conditions: before any implementation work derived from the document begins, and before the document "lands," which I take to mean before it is merged into the main branch / committed as official."
- claude-restate-good: ""Never co-writes" I read as forbidding the reviewer from contributing text to the document."

---

## Design review (d-review) — opening body

### [Design review (d-review)] — "Review a written document before its content gets expensive: a finished design before anything is built from it, and doctrine before it binds readers."
- Complaint: Conflicts with "When NOT to use": "this skill gates changes, not the archive." Gating *changes* to shipped doctrine means reviewing text that already binds readers, which the opening sentence excludes by its own words. "A re-review always reads the whole document" confirms re-reviews are in scope, and "a legacy doctrine-file review" is cited as a run that happened. An agent asked to review a one-line edit to a doctrine file live for months gets contradictory answers.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure the two sentences disagree; unsure how the author partitions "change to shipped doctrine" from "routine re-review of long-shipped doctrine", since no observable difference is given (see finding 45)."

### [Design review (d-review)] — "The document must exist and be complete enough to judge — reviewing is judging the written artifact, never co-writing it."
- Complaint: "Complete enough to judge" is a gate on whether the review proceeds at all, but the file supplies no test for it: no required sections, no minimum, no observable signal. Two reviewers will draw the line differently, and a reviewer motivated to decline can always find the document incomplete. The one gate that can refuse work is unfalsifiable, and there is no stated action for the failed case — the file never says what to do when a document is judged not complete enough (return it? ask? review partially?).
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure."

### [Design review (d-review)] — "**Review never creates — a finding explains, it does not prescribe (boss-ruled 2026-08-04):** … Designing the fix belongs to the author, and a reviewer who wants to propose an alternative design has left review — that is a create-design task, owned separately."
- Complaint: Conflicts with lens 5, which requires "The finding names the simpler mechanism that suffices — not as a proposal, but as the evidence that the machinery is over-complex." Naming the simpler mechanism that suffices *is* proposing an alternative design; the "not as a proposal, but as evidence" clause relabels the output without changing a word of it, and the absolute "never" leaves no way to reconcile the two. The same collision appears in lens 1 ("needs an empirical probe"), lens 9 ("needs a stated bound"), and lens 10 ("require a second, adversarial layer"), each instructing the reviewer to specify a remedy. A reviewer running lens 5 must either violate the no-prescribe rule or emit a finding lens 5 declares insufficient; since the no-prescribe rule is stamped as a ruling, the two are not resolvable by reading order.
- Cells: claude-hunt-good, codex-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure for lens 5; the lens 1/9/10 cases are weaker, because "needs a bound" states a required property rather than a chosen design, but the file draws no such distinction anywhere, so a literal reader has no basis to treat them differently." · codex-hunt-good: "sure."

### [Design review (d-review)] — "a finding makes the defect fully understood … completely enough that the author can fix it without asking the reviewer anything."
- Complaint: The sentence claims that explanation can always leave the author with no questions; a defect caused by missing product intent or an undocumented external constraint can be completely characterized while still leaving the author needing information from someone else.
- Cells: codex-hunt-good
- Confidence (verbatim per cell): codex-hunt-good: "sure."

### Restatement notes — Design review (d-review)
- claude-restate-good: ""Before its content gets expensive" I read as: before the document's mistakes have been converted into built artifacts or into behavior."
- claude-restate-good: "I read "owned separately" as: that work belongs to a different assignment/role, not to this review."

---

## Input and mode choice

### [Input and mode choice] — "Input: the path to the document — a pair doc (`docs/issues/<n>-<slug>.md`, an issue's companion document), a spec (`docs/cross-project/`), a skill file, CLAUDE.md, a rule page (paths relative to the repo root)."
- Complaint: Two of the five input kinds cannot be resolved. "A rule page" is an undefined term with no path, no directory, and no example — the file uses it nowhere else, so a reader cannot recognize one or find one. "CLAUDE.md" is offered as an input type, but this checkout contains no CLAUDE.md at any level (verified), so the example names a file the reader cannot locate; a reader may reasonably conclude the input list describes a different repository. This is the sentence that tells the agent what it may accept as a target, so a target that is none of the three resolvable categories cannot be classified as in-scope or out-of-scope.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure for "a rule page"; sure that CLAUDE.md is absent from this checkout, unsure whether the author intends the input list to describe this repository or the family of repositories the skill may be copied into."

### [Input and mode choice] — "Pick the mode by what the document IS, not by the state of the system around it: a design nothing has been built from yet gets the soundness checklist; a doctrine or instruction file gets the clarity review; a document that is both — doctrine carrying designed mechanisms — gets both, in separate passes."
- Complaint: The rule forbids using the surrounding system's state, then the first branch is defined entirely by the surrounding system's state: "a design nothing has been built from yet" is a fact about the build, not about the document. Nothing in the document itself changes when the first line of implementation lands. A reader who follows the stated principle classifies purely by document type; a reader who follows the example checks the repository first. These produce different modes for the same file, and the same design document moves between modes before and after partial implementation.
- Cells: claude-hunt-good, claude-hunt-floor, codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure." · claude-hunt-floor: "unsure." · codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Input and mode choice] — "a document that is both — doctrine carrying designed mechanisms — gets both, in separate passes."
- Complaint: "Doctrine carrying designed mechanisms" supplies no observable test for when both passes are required, so two readers can choose different scopes.
- Cells: codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-floor: "sure."

### [Input and mode choice] — "a design nothing has been built from yet gets the soundness checklist; a doctrine or instruction file gets the clarity review; a document that is both — doctrine carrying designed mechanisms — gets both, in separate passes."
- Complaint: A design document that *has* been partly built from matches no branch: it is not "a design nothing has been built from yet", it is not a doctrine or instruction file, and it is not "doctrine carrying designed mechanisms". The case is reachable and common — a design revised mid-build, which the re-review sizing sentence explicitly contemplates — and the description's exclusion for implementation-vs-design review does not cover it. For the exact document most likely to be re-reviewed, the mode-choice rule is silent and the agent must guess.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure the case is uncovered; unsure whether the author considers a partly-built design to still be "a design" for branch-one purposes, in which case the qualifier "nothing has been built from yet" is doing harm it was not meant to do."

### Restatement notes — Input and mode choice
(No restate cell flagged uncertainty, multiple readings, or a divergent reading in this section.)

---

## Steps

### [Steps — preamble] — "Steps 1–4 and 6 apply in both modes; step 5 is discharged by the clarity matrix in mode 2." (and the step list that follows)
- Complaint: No step names its performer. Mode 1's "Running it" establishes at least two distinct actors (lens agents and the invoker), but the numbered steps never say which performs step 1 (read the whole document), step 2 (write out your understanding), or step 4 (spot-check). Reading A: every step is the invoker's, and the lens agents only execute step 3's checklist. Reading B: each dispatched agent performs steps 1–4 on its own, and the invoker performs step 6. These differ in cost by roughly the agent count and in output shape entirely — under reading B, eleven lens agents each produce a full step-2 restatement. The only actor-clarifying text is a parenthetical two paragraphs earlier covering step 2 alone.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure that the performer is unstated; the step-2 parenthetical shows the author knows the ambiguity exists for one step and did not resolve it for the others."

### [Steps — step 2] — "**Write out your understanding of each mechanism, rule, and load-bearing claim — subtleties elucidated — before hunting defects:** edge behavior, boundary conditions, what is not covered, what it does to adjacent state…"
- Complaint: "What is not covered", written out for *each* mechanism, rule, and load-bearing claim, is the complement of a specification: the set of situations a document does not address is unbounded and cannot be enumerated. Lens 4 solves the same problem correctly by fixing the axes and then explicitly capping the obligation; step 2 has neither the axes nor the cap. The step is the mandatory precondition for defect-hunting, so an agent that takes the stop rule seriously never reaches the hunt, and one that does not silently decides how much is enough — the mood-dependence the file says the fixed checklists exist to remove.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure."

### [Steps — step 2] — "**Write out your understanding … before hunting defects**" versus "Two pass types, and **they run in SEPARATE agents — never one agent doing both**: a single agent doing one task first is primed for the second (a defect-hunt frame makes its restatement adversarial; a restatement frame makes its hunt post-hoc)."
- Complaint: Step 2 mandates precisely the sequence Mode 2 declares invalid — restate first, then hunt — performed by one agent, the invoker. The stated mechanism for why this fails ("a restatement frame makes its hunt post-hoc") is a property of doing both tasks in one context, and the invoker's context is not exempt. Step 2's parenthetical explains why the *cells* are safe but leaves the invoker doing both. Whichever rule the reader honors, they violate the other; in mode 2 both rules apply to the same agent at the same time.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure."

### [Steps — step 2] — "A divergence between your written understanding and the document's words is a finding — after ruling out that you simply misread clear text" versus "**A confusion flag is never dismissed as the reviewer's ignorance (boss-ruled 2026-08-04):** the reviewer's guaranteed context is the instruction floor plus the document, so a concept that confused them was missing from both"
- Complaint: The two sentences rule opposite ways on the same observable event. Step 2 instructs the reader to first rule out that they "simply misread clear text" — i.e. to dismiss the divergence as their own error — which the mode-2 ruling forbids, stating flatly and without carve-out that a confusion flag is never dismissed as the reviewer's ignorance. Step 2's invoker-side parenthetical scopes step 2, but the ruling is stated about "a confusion flag" without restricting it to cell-produced flags, and the invoker's misreadings are evidence of the same defect for the same stated reason. "Ruling out that you simply misread clear text" also cannot be executed from inside: the reviewer's judgment that the text was clear is the very judgment the restatement exercise exists to distrust. Divergences the method is designed to surface get suppressed at the moment of discovery by the reader best placed to report them.
- Cells: claude-hunt-good, claude-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure the two sentences instruct opposite actions; unsure whether the author considers the invoker-side scoping sufficient to separate them, since the file never says the two rules address different populations." · claude-hunt-floor: "unsure — the document never states whether these are the same judgment or different ones, so the literal conflict stands unresolved."

### [Steps — step 2] — "A divergence between your written understanding and the document's words is a finding — after ruling out that you simply misread clear text: either the document permitted your misreading, or your correct model contradicts it."
- Complaint: Unexecutable certainty requirement and false dichotomy. "Ruling out" an ordinary reviewer mistake has no observable test here. A third case remains possible: the document is clear, but the reviewer misread it and mistakenly believes the error has been ruled out. The later admission that a document and reviewer can be wrong together does not cover this reviewer-only error. Following the sentence turns an undetected reading mistake into a document finding.
- Cells: codex-hunt-good
- Confidence (verbatim per cell): codex-hunt-good: "sure."

### [Steps — step 2] — "A live specimen of the cost of skipping this: a review once passed the confidently false sentence "uncommitted work has no copy outside the conversation" — … since on this project's runtime, files on disk survive session restarts."
- Complaint: Two unresolvable references in one sentence. "A review once" cites an unnamed, unlocated past review as evidentiary support, with no path, date, or record pointer — unlike other citations in this document that do carry one. And "this project's runtime" is not identified, defined, or referenced by path, and "session restarts" is not tied to a named runtime operation, so a reader cannot determine whether the claim applies to Claude, Codex, another execution environment, every kind of restart, or only a particular launcher. The claimed counterexample therefore cannot reliably govern another review.
- Cells: claude-hunt-floor, codex-hunt-good
- Confidence (verbatim per cell): claude-hunt-floor: "unsure — this functions as illustrative background rather than an operative rule the reader must execute, so the practical cost of not being able to verify it may be low; still, it is offered as the reason a whole doctrine (step 2) exists." · codex-hunt-good: "sure."

### [Steps — step 2] — "(This step is invoker-side preparation — in mode 2, the delegated restate cells do their paraphrasing separately and innocently.)"
- Complaint: Supports two incompatible readings, in tension with "Steps 1–4 and 6 apply in both modes; step 5 is discharged by the clarity matrix in mode 2." Reading A: step 2 still happens in full in mode 2, and the delegated restate cells are a separate, additional activity. Reading B: in mode 2 the invoker's step-2 obligation is satisfied by the delegated cells doing the paraphrasing instead — which would contradict the claim that only step 5 is discharged by the mode-2 matrix. The parenthetical's wording does not clearly rule out Reading B.
- Cells: claude-hunt-floor
- Confidence (verbatim per cell): claude-hunt-floor: "unsure."

### [Steps — step 3] — "Every finding names the specific location and explains the defect to fix-ready depth … never a vague concern, never a proposed fix, and **never a severity or importance rating** (boss-ruled 2026-08-04)"
- Complaint: Conflicts with step 6, "The invoker — the one agent holding full context — assigns each finding's severity here, and only here: HIGH = … MED = … LOW = …". Step 3 says "Every finding" never carries a severity rating; step 6 says every finding gets one. The intended resolution is presumably by role (cells never rate; the invoker rates), but step 3 does not say "a cell's finding" — it says "Every finding", and step 3 is declared to apply in both modes, including mode 1 where the invoker also produces findings; the file never defines a distinct object to which one rule applies but the other does not. A reader following step 3 literally strips severity from the final deliverable, defeating step 6's ordering rule; a reader following step 6 literally violates a stamped ruling.
- Cells: claude-hunt-good, codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure the literal texts conflict; the role-based reading is available but is not stated in step 3." · codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Steps — step 3] — "a reviewer without context cannot rate importance, and an out-of-context rating anchors every later reader."
- Complaint: Overbroad absolutes. "Every later reader" is literally false: a reader who does not see the rating, deliberately ignores it, or reaches an independent judgment is an ordinary counterexample; and a reader can rate an explicitly described consequence.
- Cells: codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Steps — step 3] — "A cell states only its own confidence — sure, or unsure and why."
- Complaint: "Cell" is used here for the first time and is never defined; the closest thing to a definition is the mode-2 matrix three sections later, and mode 1's parallel unit is called a "lens", never equated with "cell". Worse, "cell" carries a second, unrelated meaning in mode 1 — lens 4's "reachable, consequential cells" and lens 10's "the design's own cells" mean state-space cells. So in step 3, a both-modes step, "a cell" reads as a review agent under mode 2 and has no referent at all under mode 1. A mode-1 reader cannot tell whether the rule binds their lens agents, and the collision defeats search, since grepping `cell` returns two unrelated concepts — the greppability failure lens 11 exists to prevent.
- Cells: claude-hunt-good, claude-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure both meanings are present; sure "cell" is undefined at first use." · claude-hunt-floor: "sure the term is used before being defined and is never equated with "lens"; unsure whether they were intended as synonyms."

### [Steps — step 3] — "Coverage over self-censorship: report what you are unsure of, with the uncertainty stated; filtering is the synthesis's job."
- Complaint: The synthesis is fully specified and contains no filtering step. The merge agent is defined as "independent, one job, zero judgment" and explicitly forbidden to filter ("nothing dropped or filtered, uncertainty wording preserved verbatim"). The author's described jobs — reading the merged file, assigning severity, comparing restatements against intent, planning the second pass, rewriting — include no filtering, and step 6's "never buried" pushes against dropping findings. Cells are told to over-report on the promise that a later stage will filter, and no later stage does, so the measured 191-raw/110-distinct volume lands on the author unfiltered.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure that no described role filters; unsure whether the author counts severity assignment as filtering, which would make LOW the discard bucket — but the file never says so."

### [Steps — step 4] — "designs' own existence labels are where they lie to themselves (the standing specimen: a backup script everyone believed ran, whose output directory had zero commits in the repository's history)."
- Complaint: Unexplained reference. "The standing specimen" and "everyone believed" cite a specific incident with no path, date, or record pointer, and "the repository" is unnamed — unlike other citations in this document that do carry a locator. A zero-context reader cannot verify or locate this claimed incident.
- Cells: claude-hunt-floor
- Confidence (verbatim per cell): claude-hunt-floor: "unsure — illustrative rather than operative."

### [Steps — step 4] — "When a load-bearing claim can be settled by one command or one file-read … check it" / "When checking would be hard, laborious, or impossible, do not attempt it"
- Complaint: The two branches are not exhaustive. A claim settleable by three commands is neither "one command or one file-read" nor "hard, laborious, or impossible", so the rule gives no instruction for it — and most real verification (does this script exist, is it wired into the hook config, did it ever run) is two to four commands. The discriminator that decides how much verification a review performs — the thing the boss ruling was issued to bound — has an unruled middle that covers the common case, so the ruling's intent is not actually operationalized.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure."

### [Steps — step 4] — "When checking would be hard, laborious, or impossible, do not attempt it — mark the claim *unverified*, and let that label feed lens 7's measured-or-believed judgment; the label is the deliverable."
- Complaint: A conditional whose condition is a judgment call rather than an observable predicate. "Hard" and "laborious" carry no objective threshold — no time budget, no command count, no file count — and depend on the specific reviewer's tools, time, and skill. Two reviewers facing the identical claim can reach opposite verify/don't-verify decisions while each faithfully following the instruction, producing different work and different evidence labels, and the file supplies no stopping rule or standard for resolving the divergence. The harm occurs precisely on consequential claims near that undefined boundary.
- Cells: claude-hunt-good, claude-hunt-floor, codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure." · claude-hunt-floor: "sure the condition is not objectively observable; unsure whether the vagueness is a genuine defect or deliberately left to reviewer discretion." · codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Steps — step 4] — "…let that label feed lens 7's measured-or-believed judgment…"
- Complaint: Step 4 is declared to apply "in both modes," but "lens 7" is Mode-1-only numbering; Mode 2 has no lenses at all, only two named passes. A reader executing step 4 while running Mode 2 has no "lens 7" to feed the label into — the instruction cannot be carried out literally in that mode.
- Cells: claude-hunt-floor
- Confidence (verbatim per cell): claude-hunt-floor: "sure."

### [Steps — step 4] — "Exhaustive mechanical checking belongs to code when it is worth doing at all, never to a reviewer's afternoon."
- Complaint: Overbroad absolute plus a judgment-based conditional. A small finite document with three links — or one whose only load-bearing claims are a small closed list of file references — is an ordinary counterexample: a reviewer can exhaustively check them manually in less time than building or locating automation. "When it is worth doing" supplies no observable predicate. Literal obedience can prevent a cheap, complete check while offering no executable way to decide whether automation is worthwhile.
- Cells: codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Steps — step 4] — "Exhaustive mechanical checking belongs to code when it is worth doing at all, never to a reviewer's afternoon." versus lens 2's "Verify each label against ground truth (step 4)."
- Complaint: Lens 2 requires verifying *each* EXISTS/NEW label; step 4 restricts verification to load-bearing claims only and forbids exhaustive checking. A design that labels forty components as existing presents forty cheap, one-command checks: lens 2 demands all forty, step 4 calls exactly that pattern overreach, and the "(step 4)" pointer asserts the two are consistent when they are not. Under the step-4 reading the label lens becomes selective and "the biggest source of design confusion we have observed" is sampled rather than checked; under the lens-2 reading the overreach ruling is voided. No tiebreak is stated.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure."

### [Steps — step 5] — "**Get independent passes.** … Dispatch fresh subagents against the same document … For a doctrine file, the clarity-review matrix below IS this step." versus "**Running it:** the lenses fan out — one focused agent per lens or per related group … the invoker synthesizes."
- Complaint: The file states explicitly that mode 2's matrix *is* step 5, and states nothing equivalent for mode 1. Reading A: the lens fan-out is mode 1's step 5, by symmetry. Reading B: the lens fan-out discharges step 3 (it is introduced under Mode 1's "Running it", and step 3 is "Run the chosen mode's checklist"), and step 5 additionally requires a separate set of fresh whole-document subagents on each available runtime — a cross-runtime requirement that appears nowhere in Mode 1's own procedure. The two readings differ by an entire second wave of agents and by whether mode 1 has a Codex leg at all; the degraded-mode sentence suggests the lenses are the delegation story, which would leave mode 1 with no independent-pass requirement despite step 5 applying to it.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure the file resolves this for mode 2 and leaves it open for mode 1."

### [Steps — step 5] — "Dispatch fresh subagents against the same document, spawned with nothing but the task (no session context rides along), on each available runtime."
- Complaint: "Nothing but the task" is not achievable on either runtime: a Claude subagent inherits a system prompt, a tool set and working directory, and the Codex path runs `codex exec -C <repo root>` with a read-only sandbox, so the agent has the whole repository available; the invoker cannot guarantee that system instructions, checkout instructions, runtime defaults, tool descriptions, retained state, or framework-provided context do not ride along, and the instruction cannot be verified as completed. It also conflicts with the mode-2 definition of the required context — "the checkout's instruction file (CLAUDE.md / AGENTS.md), the document itself, and the files the document explicitly references by path" — three things, not "nothing but the task"; an invoker obeying this sentence literally would withhold the instruction file that the "confusion flag is never dismissed" ruling makes load-bearing.
- Cells: claude-hunt-good, codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure the two sentences specify different context sets; the "no session context rides along" parenthetical shows the intent is "no *conversation* context", but the words say more than that." · codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Steps — step 5] — "Dispatch fresh subagents … on each available runtime." and "**The matrix:** {restate, defect-hunt} × {good, floor} × {each available runtime} — with both runtimes available, as today, eight cells."
- Complaint: "Available" is never given a test and has no enumeration procedure. Is a runtime available if `codex` is on PATH? If the CLI authenticates? If the pinned model ids still resolve? The cell count — and therefore the entire matrix — is a function of this untested predicate, and "as today" pins the answer to an unstated date-of-writing rather than to a check the reader can run. An agent whose `codex exec` fails must decide whether it just observed "runtime unavailable" (proceed with four cells, a legitimate matrix) or "the run is broken" (stop), and the file supports both; the script distinguishes exit codes but nothing in the file maps those to availability. Later prose discusses Claude and Codex but does not say whether those exhaust the set.
- Cells: claude-hunt-good, codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure." · codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Steps — step 6] — "The invoker — the one agent holding full context — assigns each finding's severity here, and only here: HIGH = following the words does the wrong thing and the wrongness costs something real; MED = competent readers diverge; LOW = friction, likely recovered."
- Complaint: Conflicts with the earlier prohibition on every severity rating. It also makes severity depend on "costs something real," "competent readers," and "likely recovered," none of which has an observable standard. The later synthesis assigns severity to "the author" with full context, but the file never establishes whether that author is the invoker; if not, two roles are directed to perform the same exclusive act.
- Cells: codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-floor: "sure."

### [Steps — step 6] — "The invoker — the one agent holding full context — assigns each finding's severity here, and only here" versus "Then the **author** reads that one file with full context … assigns all severity at step 6" and "the author never reviews their own text — that is step 5's warning"
- Complaint: Both "the invoker" and "the author" are described as the agent holding full context and as the assigner of severity, so either they are the same agent or the file has two "the one agent holding full context". If they are the same agent — the normal case, since an author reviewing their own draft is who reaches for a review skill, and this repository's own self-review directory shows the skill being run on itself — then "the author never reviews their own text" is violated by the author performing steps 1–4 and 6. If they are different agents, then "no one else holds the intended meaning" says the invoker cannot perform the restatement comparison, and the file never says how the author and invoker divide steps 1–6. A third role name, "the context-holder", appears without definition and may be a fourth name for the same agent. The file's central safety property — separation of author from reviewer — has no consistent assignment of who does what, and the most common invocation pattern violates it on its face.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure the role names collide; unsure which collapse the author intends."

### [Steps — step 6] — "Order by severity, consequence breaking ties, each explained to fix-ready depth." versus "ordered by **document position — never by any cell's opinion or rating**: report order pollutes the author's judgment as their context fills, and document order is the one ordering that carries nobody's"
- Complaint: Step 6 mandates severity ordering; the synthesis paragraph mandates document ordering and states a general reason — that ordering by any rating pollutes the reader's judgment — which applies equally to the invoker's severities in step 6. The two rules can be reconciled by scoping (merged cell file: document order; final findings: severity order), but neither sentence carries that scope, and the synthesis ends with "Then findings as in step 6", placing them in one pipeline. If the preserved record is the step-6 output, the "never by any cell's opinion or rating" guarantee is lost in the artifact that survives; if it is the merged file, the author's severity work is not preserved.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "unsure — the scoped reading is plausible, but the absolute "never" and the generality of the stated rationale make the conflict readable as real."

### [Steps — step 6] — "Name what is solid where anything is — and say plainly when nothing is."
- Complaint: Judgment-based conditional and unbounded negative determination. "Solid" has no observable criterion, while saying that "nothing" is solid requires ruling out every part of the document. Readers can disagree about partial evidence, an unverified claim, or a correct but underspecified mechanism. The sentence can force an unjustified all-clear or all-unsound statement.
- Cells: codex-hunt-good
- Confidence (verbatim per cell): codex-hunt-good: "sure."

### [Steps — step 6] — "End with one line: sound · sound-with-named-risks · not-ready-because-X, where X is the single blocking reason."
- Complaint: Wrong when obeyed literally. A document can have two or more independent blocking reasons — for example an impossible runtime assumption and a contradictory safety rule — where neither subsumes the other. The format admits exactly one, and the instruction presupposes uniqueness rather than instructing the reviewer to pick the worst. Obeying the words forces the reviewer to name one and silently drop the others from the one line most readers will read; a reader who sees the named blocker fixed will reasonably believe the document is now ready.
- Cells: claude-hunt-good, codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure." · codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Steps — step 6] — "End with one line: sound · sound-with-named-risks · not-ready-because-X"
- Complaint: The three verdicts are phrased for designs — "sound" is an awkward verdict for a mode-2 clarity review of doctrine, and the file gives no mode-2 alternative even though step 6 applies in both modes.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "(Secondary, unsure: the three verdicts are phrased for designs — "sound" is an awkward verdict for a mode-2 clarity review of doctrine, and the file gives no mode-2 alternative even though step 6 applies in both modes.)"

### Restatement notes — Steps
- claude-restate-good (on the preamble): ""Discharged" I read as: the obligation created by step 5 is fulfilled by that matrix, so no additional action is owed."
- claude-restate-good (on step 2's live specimen): "The reason writing out your understanding would have caught it: the exercise of explicitly modeling the boundary (I read "the boundary" as the boundary between what persists and what does not — between session state and disk state) forces a conflict with such a sentence…"
- claude-restate-good (on step 5's final sentence): "(I note this sentence says "for a doctrine file," while the earlier scoping line said "in mode 2"; I read both as referring to the same case, since mode 2 is selected for doctrine and instruction files.)"
- claude-restate-good (on step 6's verdict line): "(I read the middle-dot separators as enumerating the three alternatives to choose among, not as a string to be emitted whole.)"

---

## Mode 1 — the design-soundness checklist

### [Mode 1 — Running it] — "No single reviewer walks the full lens set inside one context when delegation is available; with no subagent facility, one reviewer working the lenses serially is the accepted degraded mode."
- Complaint: "Delegation is available" is not an observable predicate: a platform can expose subagents while policy, capacity, target sensitivity, or a user instruction prohibits using them. The absolute prohibition then conflicts with the actual available authority, and no fallback covers that case.
- Cells: codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-floor: "sure."

### [Mode 1 — Running it] — "**A re-review always reads the whole document (boss-ruled 2026-08-04)**"
- Complaint: Overbroad absolute with no exception or stop rule. A generated, corrupted, unexpectedly enormous, or composite document makes whole-file rereading unreasonable — or impossible within an agent's context and time limits — even when a bounded changed section is reviewable, and the skill sets no maximum document size or accessible-text requirement.
- Cells: codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 1 — Running it] — "design defects are global, and an edit collides with unedited text as often as with itself (measured: several of the first full-grid run's catches were changed-versus-unchanged conflicts)."
- Complaint: "As often as" is a frequency claim — equal rates for two collision classes — and the parenthetical labels it "measured" while supplying only "several … catches" from one run, with no denominator and no count of the comparison class. Lens 7 requires exactly this distinction between measured, guaranteed, and merely believed. The sentence is the stated justification for a ruling that fixes the cost of every re-review at whole-document scope; presenting a believed rate as measured makes the ruling look empirically settled and discourages the measurement that would confirm or refute it.
- Cells: claude-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure the evidence given does not support "as often as"; unsure whether fuller measurements exist in `d-review-records/` that the sentence is summarizing." · codex-hunt-floor: "sure."

### [Mode 1 — Running it] — "(measured: several of the first full-grid run's catches were changed-versus-unchanged conflicts)"
- Complaint: Unexplained evidence reference. "The first full-grid run" is not identified by a file or record path in this sentence, so its measurement is difficult for the minimal reader to locate or evaluate.
- Cells: codex-hunt-good
- Confidence (verbatim per cell): codex-hunt-good: "sure."

### [Mode 1 — Running it] — "What scales with revision size is the reviewer count, never the text scope: a light revision may earn a single good-tier pass over the full document plus verification of each prior finding's fix; a heavy revision earns the full grid."
- Complaint: "Light" and "heavy" revision are undefined — no line count, no diff size, no section count, no "touches a load-bearing claim" test — so the prescribed reviewer count is not reproducible and two invokers facing the identical diff could reasonably pick different review scales while each claiming to follow the rule. The file elsewhere shows it can write observable predicates ("one command or one file-read"), so the omission is visible. The choice between one agent and eight is made by an unmeasured adjective, and the reviewer choosing it is often the author, who has an incentive to call their revision light.
- Cells: claude-hunt-good, claude-hunt-floor, codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure." · claude-hunt-floor: "sure the condition is undefined; unsure whether this is a genuine defect versus intentional discretion (the document elsewhere explicitly flags similar discretion, e.g. "grouping is the invoker's call," but does not do so here)." · codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 1 — Running it] — "a light revision may earn a single good-tier pass over the full document…" versus "The full grid runs every time, and every cell reads the whole document."
- Complaint: Direct conflict between two sentences in the same file. One says a light revision may run one good-tier pass; the other says the full grid runs every time. Both use "the full grid" for the same eight-cell matrix, so this is not a mode-1/mode-2 scoping difference — and the first is describing the clarity grid while sitting in the Mode 1 section, which compounds the problem. The rule that decides how many agents a re-review costs has two contradictory answers, one of which is stated as an invariant that the pruning discussion immediately after depends on. If light revisions actually run one cell, the accumulating record is not a full-grid corpus and the future pruning analysis is comparing unlike runs.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure."

### [Mode 1 — Running it] — "What scales with revision size is the reviewer count, never the text scope"
- Complaint: Overbroad absolute and impossible scaling requirement. Reviewer count cannot necessarily scale when the number of available agents is fixed. A large file with a one-line revision is an ordinary case where text scope, not reviewer count, may be the practical variable.
- Cells: codex-hunt-good
- Confidence (verbatim per cell): codex-hunt-good: "sure."

### [Mode 1 — Running it] — "a light revision may earn a single good-tier pass over the full document plus verification of each prior finding's fix"
- Complaint: "Verification of each prior finding's fix" conflicts with step 4's direction not to attempt hard verification and instead mark it unverified. "Good-tier" is also not defined for the design-soundness mode at this point.
- Cells: codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-floor: "sure."

### [Mode 1 — Running it] — "The reviewable unit is the whole file — and doctrine and design files stay small and atomic partly so that whole-file review stays practical."
- Complaint: The sentence asserts as background fact that the corpus consists of small atomic files and makes the practicality of the whole-file rule depend on it, but nothing in this file, in the reader's guaranteed context, or anywhere else constrains doctrine or design files to remain small or atomic, and no size threshold is given. The reachable counterexample is in the input list: `docs/issues/<n>-<slug>.md` pair docs, of which this checkout holds several in the 26–38 KB range, and this SKILL.md is itself 21 KB; a long existing instruction file, a generated specification, or a file combining inherited sections violates the premise while still satisfying the stated input type. An agent handed a large pair doc is bound by "every cell reads the whole document" and "A re-review always reads the whole document" with no stated fallback.
- Cells: claude-hunt-good, codex-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "unsure — the claim may be true of the specific documents the author has in mind, but the reader has no way to check it and no rule to fall back on when it fails." · codex-hunt-good: "sure."

### [Mode 1 — lens 1] — "A load-bearing claim resting on first-principles reasoning about how the runtime behaves … needs an empirical probe … Conversely, do not manufacture a probe for a fact true by construction — one that follows from the artifact's own definition, so its falsity would make the mechanism itself pointless."
- Complaint: Self-contradictory — the exemption's test admits the class the rule targets. "Its falsity would make the mechanism itself pointless" is satisfied by many genuine runtime-boundary claims: "the hook fires before the tool call" is pointless-if-false *and* is precisely the "hook ordering" example the first half names as requiring a probe. The two halves classify the same claim oppositely. The intended test for "true by construction" is presumably "follows deductively from the artifact's definition", which is the first clause; the second clause does not follow from it and is not equivalent to it. The highest-value lens in mode 1 can be talked out of every probe it should demand, using the lens's own exemption, and the stakes-based tiebreak is explicitly removed.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure."

### [Mode 1 — lens 1] — "needs an empirical probe (or an authoritative contract that specifies the behavior), not assumption."
- Complaint: "An authoritative contract" is never defined and no example is given. A reader cannot tell whether vendor documentation, a tool's JSON schema, a source comment, another project doctrine file, or a previous d-review record qualifies. Lens 7 makes the term load-bearing a second time, so the same undefined term decides whether a mechanism is classified as guaranteed or merely believed — and therefore feeds the final severity.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure."

### [Mode 1 — lens 1] — "Demand probes for genuine unknowns; stake level is not the discriminator."
- Complaint: "Genuine unknown" has no observable test and depends on what the reviewer believes, what evidence they happened to find, and how they interpret "by construction." A reviewer must make the very epistemic judgment that the sentence treats as the gate for required work, so two reviewers can demand or omit probes for the same claim without either violating a stated predicate.
- Cells: codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 1 — lens 2] — "Anything labeled as existing that is only designed or proposed (or the reverse) is flagged — the biggest source of design confusion we have observed."
- Complaint: Incompatible classification. "The reverse" can mean either something labeled proposed that already exists, or any existing artifact discussed prospectively. The former is a status-label mismatch; the latter would flag ordinary proposed changes to an existing mechanism. The sentence does not constrain the reversal to the label itself.
- Cells: codex-hunt-good
- Confidence (verbatim per cell): codex-hunt-good: "unsure because "or the reverse" conventionally suggests the narrower symmetric reading, but the literal broader reading remains available."

### [Mode 1 — lens 2] — "Verify each label against ground truth (step 4)."
- Complaint: Conflict. Step 4 explicitly says not to attempt checks that are hard, laborious, or impossible and to mark those claims unverified. "Verify each" requires a settled result for every label; "mark unverified" permits some labels to remain unsettled. A label whose status depends on inaccessible production state cannot satisfy both instructions.
- Cells: codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 1 — lens 3] — "Every load-bearing rule in a design is backed by something: an enforcement point (a gate, a check, a tool boundary) or a written instruction agents follow."
- Complaint: False exhaustive claim / overbroad absolute. The ordinary counterexample is a rule backed by nothing: stated only in a design document that no agent reads at runtime, with no gate and no instruction placed anywhere an agent encounters it. A design can also contain a rule established by a platform guarantee, a human approval process, a legal constraint, or a convention outside the two categories. The unbacked rule is arguably the most severe defect this lens should catch, but the sentence declares the two-way split exhaustive, so a reviewer must force it into "a written instruction agents follow", which is false, or find the lens has no verdict — and the lens's only stated finding type, "discipline presented as enforcement", does not cover "nothing presented as discipline". Rules backed by nothing are misclassified as discipline-backed and pass the lens.
- Cells: claude-hunt-good, codex-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure." · codex-hunt-good: "sure."

### [Mode 1 — lens 3] — "The review checks that the document says which, truthfully: a claimed mechanism must actually exist (lens 2 verifies it), and a written instruction must be labeled as what it is."
- Complaint: Conflict. Lens 2 expressly permits honest `NEW` or proposed mechanisms that do not yet exist. This sentence says any claimed mechanism "must actually exist," which would reject an accurately labeled future mechanism. It also says lens 2 verifies existence despite step 4 allowing an unverified result.
- Cells: codex-hunt-good
- Confidence (verbatim per cell): codex-hunt-good: "sure."

### [Mode 1 — lens 3] — "Re-evaluating that split … is a different problem set, out of this review's scope … — unless the code-versus-prompts choice is itself the subject of the document or section under review, in which case it is reviewed like any other design decision."
- Complaint: A conditional whose condition is a judgment call with no observable test, and nearly circular: any design section that specifies a mechanism has chosen between code and prompt, so a reviewer inclined to raise the issue can declare that the section's subject. A section may discuss enforcement architecture without announcing that its subject is code-versus-prompts; one reader will review the split while another will exclude it. An exclusion stamped as a boss ruling, with a named owner elsewhere, can be reopened at the reviewer's discretion on every mechanism section — returning the review to the exact debate the ruling was made to route away — and the boundary controls whether a potentially central design decision is examined at all.
- Cells: claude-hunt-good, codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure the condition is unmeasurable; unsure how wide the author intends "the subject of … [a] section" to be." · codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 1 — lens 4] — "For each mechanism, walk the state space systematically: actor states (busy, idle, mid-turn, dead), dependency failures (the file it reads, the tool it runs, the channel it writes), concurrency (two sessions, re-entry, repeated firing) — and require the document to name or explicitly discard the reachable, consequential cells."
- Complaint: Unbounded enumeration with judgment-based conditions. "Repeated firing" admits arbitrarily many repetitions, concurrency can produce an open-ended interleaving space, and dependencies can fail in unenumerated combinations; there is no abstraction level or stop rule. "Reachable" and "consequential" have no decision procedure and depend on a system model the zero-context reader may not possess. Saying the enumeration need not appear as a transcript does not bound the reviewer's required private enumeration, so literal completion can require an unlimited state-space analysis.
- Cells: codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 1 — lens 4] — "require the document to name or explicitly discard the reachable, consequential cells" / "the best catches live in cells the design's own story never visits" / (lens 10) "A plan that maps the design's own cells is necessary"
- Complaint: Overloaded term. Here "cell" denotes a state-space or test-matrix scenario; in step 3, step 4 and throughout Mode 2 it denotes one delegated review-agent invocation in the {pass}×{tier}×{runtime} matrix. Because step 3 applies to both modes and uses "cell" in the mode-2 sense, a mode-1 reader who has just read lens 4 will read "A cell states only its own confidence" as a statement about state-space cells, which is meaningless. The same word is used for two unrelated concepts without the overload ever being flagged.
- Cells: claude-hunt-good, claude-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "Harm and confidence as in finding 16." · claude-hunt-floor: "sure both senses are used; unsure whether a real reader would actually be misled given that surrounding context usually disambiguates."

### [Mode 1 — lens 4] — "A reachable, relevant omission is a finding even when the happy path is flawless — the best catches live in cells the design's own story never visits."
- Complaint: Judgment-based condition. "Relevant" has no observable criterion, and "reachable" may depend on undocumented runtime behavior. Two readers can identify the same omitted case but disagree whether this sentence requires a finding. The harm is inconsistent coverage at precisely the omitted boundaries the lens is meant to govern.
- Cells: codex-hunt-good
- Confidence (verbatim per cell): codex-hunt-good: "sure."

### [Mode 1 — lens 5] — "Machinery whose value does not justify its cost."
- Complaint: Unexecutable judgment criterion. No kinds of value, kinds of cost, comparison method, or decision threshold are supplied. The fragment can classify the same mechanism as necessary or over-complex solely from reviewer preference.
- Cells: codex-hunt-good
- Confidence (verbatim per cell): codex-hunt-good: "sure."

### [Mode 1 — lens 5] — "The finding names the simpler mechanism that suffices — not as a proposal, but as the evidence that the machinery is over-complex."
- Complaint: Naming a different mechanism that should replace or obviate the reviewed machinery is an alternative design proposal under the ordinary meaning of "proposal"; declaring that it is "not" one does not change the act, and calling the alternative evidence rather than a proposal does not change what the reviewer must supply. It conflicts with "Review never creates," "a finding … does not prescribe," and "never a proposed fix." Literal obedience requires both proposing and not proposing the same mechanism.
- Cells: codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 1 — lens 6] — "The document contradicting itself, its own stated principles, or the project's recorded rulings — the governing plan documents and issue bodies, which the lens agent is given alongside the document."
- Complaint: Unexecutable, undefined reference. "The governing plan documents" and "issue bodies" are named with no paths, no titles, and no way to identify them; this checkout has `docs/cross-project/nedschorus-founding-plan.md`, `docs/cross-project/git-gatekeeper-design.md` and seven others, plus `docs/issues/` files and, separately, GitHub issues, and nothing says which set is meant, who selects them, where "recorded rulings" live, or how to bound them. The clause also conflicts with "Running it", which says each lens agent is handed "the document and its question" — lens 6 asserts it is additionally given a corpus that is never mentioned there and that the invoker is never told to assemble. Lens 6 cannot be dispatched as described; the invoker must invent the input set, and different invokers will supply different ones.
- Cells: claude-hunt-good, codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure." · codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 1 — lens 6] — "**Internal consistency.** The document contradicting itself, its own stated principles, or the project's recorded rulings…"
- Complaint: Calling external-ruling conflicts "Internal consistency" supports two scopes: consistency internal to the document versus consistency with selected project records.
- Cells: codex-hunt-good
- Confidence (verbatim per cell): codex-hunt-good: "sure."

### [Mode 1 — lens 6] — "Internal inconsistency is strong evidence of an unexamined call; confirm the exception is not deliberate before flagging."
- Complaint: Demands knowledge of another party's internal state. Confirming that an inconsistency is not deliberate requires the author's intent, which the synthesis paragraph says the reviewer does not have ("no one else holds the intended meaning"); silence supports both an accidental contradiction and an intentional but undocumented exception. There is no stated channel, artifact, authority, or stop rule for the confirmation — the reviewer is a fresh subagent with no session context and cannot ask the author — and it runs against the ruling that a reviewer's confusion is never dismissed as their own. The gate is unsatisfiable, so a literal reader suppresses every internal-inconsistency finding: the class this lens exists to produce.
- Cells: claude-hunt-good, codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure." · codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 1 — lens 7] — "Each load-bearing mechanism is measured (probe, canary, field observation), guaranteed (by definition or an authoritative contract — lens 1's by-construction class), or merely believed."
- Complaint: Incompatible/incomplete classification. The `or` can define mutually exclusive statuses or merely list nonexclusive evidence types. A mechanism can be measured in one environment, contractually guaranteed for another boundary, and still believed to work end to end; it can be partially measured; or its basis can be unknown because step 4 marked the claim unverified. Those cases fit neither a single exclusive category nor "merely believed," and the subsequent rule "Believed plus load-bearing" behaves differently depending on which reading holds. The classification determines review output, so different readers must guess how to classify mixed evidence.
- Cells: codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 1 — lens 7] — "Believed plus load-bearing is a named risk until measured."
- Complaint: Wrong when obeyed literally. The preceding sentence recognizes that an authoritative contract or definition can establish a guarantee. A believed claim can therefore cease to be merely believed by obtaining such a guarantee without being measured. "Until measured" falsely excludes that stated path.
- Cells: codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-floor: "sure."

### [Mode 1 — lens 8] — "Does the order remove the highest live risk first — ranked by probability times the cost of late discovery?"
- Complaint: Current-world dependency and judgment-based condition. The file provides neither probabilities nor costs, "live risk" requires current system state that the document may not contain, and multiplying unstated estimates does not produce an observable ranking. Different reviewers can identify different "highest" risks while each follows the sentence, and the lens provides no evidence standard or way to stop when those facts are unavailable.
- Cells: codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 1 — lens 8] — "Is the highest-value piece scheduled sensibly or buried behind lower-value work?"
- Complaint: Judgment-based condition. "Value," "sensibly," "buried," and "lower-value" have no defined measures. The sentence offers no literal criterion for deciding whether a dependency-first schedule is sensible preparation or improper burial.
- Cells: codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 1 — lens 9] — "Potentially unbounded data the design accumulates needs a stated bound — retention, archival, or the project's artifact-lifecycle rule that every accumulating store has a named home and a drain — plus a rough volume expectation."
- Complaint: Undefined reference. "The project's artifact-lifecycle rule" is cited as an existing rule of this project but exists in no file the reader is guaranteed: there is no CLAUDE.md or AGENTS.md in this checkout, and the sentence gives no path or definition. The reader is told they may satisfy the lens by invoking a rule they cannot read, and cannot tell whether a design that says "records go in `d-review-records/`" has satisfied it; the parenthetical gloss ("a named home and a drain") may or may not be the whole rule.
- Cells: claude-hunt-good, codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure the reference is unresolvable from the guaranteed context." · codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 1 — lens 9] — "Potentially unbounded data the design accumulates needs a stated bound … plus a rough volume expectation."
- Complaint: Judgment-based condition. "Potentially unbounded," "named home and a drain," and "rough volume expectation" have no observable thresholds, so a reviewer cannot reliably decide whether the rule applies or what satisfies the requirement.
- Cells: codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 1 — lens 9] — "needs a stated bound — retention, archival, or the project's artifact-lifecycle rule…"
- Complaint: Wrong examples. Retention and archival do not necessarily establish a bound: an archive that never deletes data remains unbounded, and a retention policy without a maximum duration or volume may also remain unbounded. Literal obedience can accept an accumulating archive as the required bound.
- Cells: codex-hunt-good
- Confidence (verbatim per cell): codex-hunt-good: "sure."

### [Mode 1 — lens 9] — "Potentially unbounded data the design accumulates needs a stated bound…" versus "**Every review preserves its record** — the merged cell-attributed findings, the triage dispositions, and every cell's output … as a dated directory under `d-review-records/`"
- Complaint: `d-review-records/` is an accumulating store created by this document: one dated directory per review, holding eight cell outputs plus merged findings and dispositions, growing without limit. The file states no retention, no archival, no drain, and no volume expectation for it — and lens 9 says to flag the missing bound even when the ceiling looks far off. The matrix paragraph makes the store permanently load-bearing ("Pruning cells is a data question … over tens of preserved reviews"), so the design explicitly requires the store to keep growing before any analysis can run. The file fails its own lens on the only store it creates.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure."

### [Mode 1 — lens 9] — "Unbounded growth with correctness-only thinking is a default blind spot; flag the missing bound even when the ceiling looks far off."
- Complaint: Judgment-based conditional. "Looks far off" supplies no measurable horizon, rate, capacity, or time interval. A reviewer cannot tell when this clause applies, and different guesses about future growth produce different findings.
- Cells: codex-hunt-good
- Confidence (verbatim per cell): codex-hunt-good: "sure."

### [Mode 1 — lens 10] — "A plan that maps the design's own cells is necessary but, unless it includes generative techniques (fuzzing, property tests), only exercises what the design thought of."
- Complaint: Overbroad absolute. A manually authored adversarial test, a regression test from an external failure or prior incident, an external contract, a production trace, or a test imported from another implementation can exercise something the design did not anticipate without using fuzzing or property tests. "Only" makes the absence of generative techniques conclusive when it is not, and misclassifies those ordinary cases.
- Cells: codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 1 — lens 10] — "Where the designed thing has an executable surface, require a second, adversarial layer — load, scale, "what did we not anticipate" — that does not assume the design is right."
- Complaint: Labor with no stop rule. "What did we not anticipate" as a required test layer has no completion condition; it is an open set, completing it would require knowing the unknown cases, and unlike lens 4 it is not accompanied by a limiting sentence. The sentence gives no bounded test method, coverage target, or completion criterion, so the reviewer must judge whether a test plan contains enough of an unbounded category to pass, can neither know when the requirement has been met nor distinguish a reasonable test plan from an endlessly expandable one, and the lens produces either a permanent finding on every design with an executable surface or an arbitrary pass.
- Cells: claude-hunt-good, codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "unsure — the phrase may be intended as a category name for generative/adversarial testing (fuzzing and property tests are named in the preceding sentence) rather than as a literal deliverable, but the words place it in a list of required layers." · codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 1 — lens 10] — "Where the designed thing has an executable surface, require a second, adversarial layer — load, scale…"
- Complaint: Overbroad requirement. Load and scale testing are not meaningful for every executable surface — for example a finite one-time schema check — yet the sentence requires the layer whenever any executable surface exists.
- Cells: codex-hunt-good
- Confidence (verbatim per cell): codex-hunt-good: "sure."

### [Mode 1 — lens 11] — "A name, for this lens, is an identifier that anything outside the document will use to find or invoke the thing (boss-scoped 2026-08-04) … Ordinary prose vocabulary, one-off words, and local labels defined where they are used (a tier scheme, a severity scale) are not names and are out of this lens's scope."
- Complaint: Self-contradictory: the definition and the exemption classify the same items oppositely. The tier scheme is `good` and `floor` — and those exact strings are command-line argument values consumed outside the document by `scripts/d-review-codex-cell.py` (`--tier good|floor`, verified in the script's `choices=["good", "floor"]` and its `TIER_TO_CODEX_MODEL` / `TIER_TO_REASONING_EFFORT` keys). By the definition they are names; by the exemption "a tier scheme" is explicitly not a name. They are also exactly the kind the lens flags on sight — one generic word each, with "good" colliding with ordinary prose usage throughout the file. The reader cannot determine the lens's scope for any identifier that is both a local label and an external interface, which is the common case for enum values, mode names, and severity levels that appear in scripts or filenames.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure."

### [Mode 1 — lens 11] — "Every in-scope name must be self-documenting and greppable: full words a search matches verbatim, one shared token across a family of related names, no cryptic abbreviations, no bare sequence labels, and no bare numeric issue references in prose (the number must ride with a descriptive handle)."
- Complaint: An absolute rule the file itself cannot satisfy, plus an ambiguous exemption boundary. "No bare sequence labels" is violated throughout this document by its own cross-reference vocabulary: "Steps 1–4 and 6 apply in both modes", "step 5 is discharged by the clarity matrix in mode 2", "lens 1's by-construction class", "lens 7's measured-or-believed judgment", "Mode 1", "Mode 2". These are identifiers other documents and review records will cite ("d-review lens 7"), which the lens's own definition puts in scope; the exemption for "local labels defined where they are used" arguably covers them, and the file gives no way to decide which applies. A reviewer applying this lens to any numbered document cannot tell whether numbered steps and lenses are findings; if they are not, the rule loses most of its bite, while if they are, this file is a mass violation.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure the tension exists; unsure which side the author intends, which is the defect."

### [Mode 1 — lens 11] — "Every in-scope name must be self-documenting and greppable: full words a search matches verbatim, one shared token across a family of related names, no cryptic abbreviations…"
- Complaint: Overbroad absolute, judgment-based predicates, and conflict. "Self-documenting," "cryptic," and "related" have no observable tests. The next sentence says domain-standard tokens such as `SHA-256` pass, although `SHA` is not a full word, so "full words" is not universally required. A family can also use established ecosystem names that lack one shared token while remaining searchable.
- Cells: codex-hunt-good
- Confidence (verbatim per cell): codex-hunt-good: "sure."

### [Mode 1 — lens 11] — "Every in-scope name must be self-documenting and greppable: full words a search matches verbatim…"
- Complaint: Judgment-call conditional and overbroad absolute. "Self-documenting," "cryptic," and what counts as a related family are not observable predicates. The universal also fails for established externally required identifiers: a design may have to cite a vendor command, protocol token, API name, or compatibility path whose spelling cannot be replaced with full words. The rule does not distinguish names being introduced from names that must be referenced accurately.
- Cells: codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-floor: "sure."

### [Mode 1 — lens 11] — "A one-word name is a finding candidate by default when the word is generic or collides in context (`parser`, `data`, `manager`); domain-standard tokens (`README`, `checksum`, `SHA-256`) pass."
- Complaint: Judgment-based conditional. "Generic," "collides in context," and "domain-standard" have no defined corpus or observable threshold. `parser` may be fully specific in a parser-only package but generic in a compiler suite; the sentence gives no way to settle that boundary.
- Cells: codex-hunt-good
- Confidence (verbatim per cell): codex-hunt-good: "sure."

### [Mode 1 — lens 11] — "A longer precise name beats a short ambiguous one, and ease of typing is not a constraint."
- Complaint: Overbroad claim. Ease of typing is an ordinary constraint for frequently invoked CLI commands, public APIs, accessibility needs, platform path-length limits, or interfaces where users must enter the name manually. Literal obedience forbids considering that real constraint even when it materially affects the designed interface.
- Cells: codex-hunt-good
- Confidence (verbatim per cell): codex-hunt-good: "sure."

### Restatement notes — Mode 1 — the design-soundness checklist
- claude-restate-good (on "What scales with revision size…"): "I read "earn" as "warrant/receive.""
- claude-restate-good (on lens 11's requirement list): "do not use bare sequence labels (I read this as names that are just an ordinal or index, such as "step2" or "v3", carrying no descriptive content)"

---

## Mode 2 — the clarity review (doctrine and instruction files)

### [Mode 2 — opening] — "Two pass types, and **they run in SEPARATE agents — never one agent doing both**: a single agent doing one task first is primed for the second…"
- Complaint: An unqualified absolute with no stated fallback. Mode 1 explicitly provides a degraded mode for the analogous constraint ("with no subagent facility, one reviewer working the lenses serially is the accepted degraded mode"); Mode 2 states its agent-separation rule as "never" with no equivalent fallback anywhere in its text. Taken literally, the rule cannot be obeyed in an environment lacking a subagent-spawning facility, and no alternative path is given, so a single-agent runtime cannot perform the clarity review at all. An isolated runtime may provide only one agent slot while still permitting separate fresh turns or independent processes; the sentence treats that ordinary constrained case as forbidden rather than defining a degraded mode.
- Cells: claude-hunt-floor, codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-floor: "sure no Mode-2 fallback text exists; unsure whether that gap matters (an environment with no subagent facility at all may be considered outside this skill's intended operating envelope)." · codex-hunt-good: "sure." · codex-hunt-floor: "unsure — the intended meaning may be that independently launched cells count as separate agents even when initiated by one coordinator."

### [Mode 2 — opening] — "**they run in SEPARATE agents — never one agent doing both**"
- Complaint: "Never" also excludes isolated fresh sessions of the same agent implementation even when no conversational state carries between them, while the stated reason concerns priming rather than identity.
- Cells: codex-hunt-good
- Confidence (verbatim per cell): codex-hunt-good: "sure."

### [Mode 2 — restatement pass] — "The cell's prompt carries no review framing — only the paraphrase template and the target path, nothing else."
- Complaint: Wrong when checked against the file it names. `prompts/restate.md` contains "Do not repair anything, do not fill gaps, and do not substitute what the author probably intended for what the words say" and "many sentences use ambiguous words with several meanings, or jargon, or coined expressions that are hard to interpret out of their normal context." Both prime the reader to expect defective text and to withhold charity — which is review framing by the file's own account, since it identifies charity-suppression as the active ingredient of the adversarial prompt ("Force literal reading; forbid charity; keep the restate template free of review framing"). Additionally, "nothing else" cannot hold for a Claude cell, which necessarily receives a system prompt and tool set. The restatement pass's claimed innocence — the property that makes a divergence meaningful evidence — is asserted rather than held.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure about the template's contents; unsure only in that "review framing" is not defined, so a narrow reading (no mention of finding defects, which the template indeed avoids) could be defended."

### [Mode 2 — restatement pass] — "The finding is not the paraphrase — it is the **divergence** between the paraphrase and the intended meaning."
- Complaint: Unexecutable by the stated actor. The restatement cell is given only a target path and a paraphrase template, while the intended meaning is not supplied to it. The sentence can mean either that the cell must detect divergence, which is impossible from its input, or that another unspecified actor must do so. Later text assigns comparison to the author, but this sentence does not identify that actor.
- Cells: codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-floor: "sure."

### [Mode 2 — defect-hunt pass] — "a reader with no project history whose entire context is the checkout's instruction file (CLAUDE.md / AGENTS.md), the document itself, and the files the document explicitly references by path" — together with "the remedy is one of three … or promote the definition to the instruction floor when many files share the concept."
- Complaint: Wrong/impossible when obeyed literally in this checkout. There is no CLAUDE.md and no AGENTS.md anywhere in `/Users/el/Projects/nedschorus/` (verified). The defined instruction floor is empty, so the cell's context is document-plus-referenced-files only, and the third remedy names a destination file that does not exist, with no instruction to create one. This is the load-bearing premise of the ruling in the next sentence: with no floor, every project-specific term in every reviewed document is automatically a finding — "the boss", "the governing plan documents", "the project's artifact-lifecycle rule", "postal" — and the triage has only two of its three remedies available.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure about the absence; unsure whether the author knows the floor is missing and intends this skill to be portable to repositories that do have one."

### [Mode 2 — defect-hunt pass] — "**A confusion flag is never dismissed as the reviewer's ignorance (boss-ruled 2026-08-04):** the reviewer's guaranteed context is the instruction floor plus the document, so a concept that confused them was missing from both"
- Complaint: Invalid inference and overbroad absolute. A reviewer can overlook an existing definition, misparse clear text, fail to follow a reference, or lack the capability to understand a correctly defined concept; guaranteed access to context does not guarantee correct use of it. Confusion therefore does not prove the concept was missing, and the rule converts those ordinary reviewer failures into document defects.
- Cells: codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 2 — defect-hunt pass] — "the reviewer's guaranteed context is the instruction floor plus the document, so a concept that confused them was missing from both"
- Complaint: Conflicts with the sentence immediately preceding it, which defines the reader's context as three things — instruction file, document, and "the files the document explicitly references by path". This sentence drops the third and reasons from two, so the inference is invalid on its own terms: a concept defined in an explicitly referenced file (for example the tier-to-model mapping at the top of `scripts/d-review-codex-cell.py`, which the file points to and calls authoritative) is *not* missing from the reviewer's context, yet a reviewer who skipped that file would produce a confusion flag that this rule forbids anyone from dismissing. The ruling's absolute protection is derived from a premise narrower than the context the file actually grants, and it does so with a ruling stamp that discourages challenge.
- Cells: claude-hunt-good, claude-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure." · claude-hunt-floor: "unsure on both points — the dropped third component may be deliberate (referenced files aren't guaranteed to exist for every document), but the term collision with tier-"floor" is a plain textual fact."

### [Mode 2 — defect-hunt pass] — "the reviewer's guaranteed context is the instruction floor plus the document"
- Complaint: "The instruction floor" is a new term introduced here, defined and located nowhere, and it collides with the document's separately and heavily used term "floor" meaning the low-capability model tier ("floor = the pinned floor model"; "*Floor* is defined by capability").
- Cells: claude-hunt-floor, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-floor: "unsure on both points — the dropped third component may be deliberate (referenced files aren't guaranteed to exist for every document), but the term collision with tier-"floor" is a plain textual fact." · codex-hunt-floor: "sure."

### [Mode 2 — defect-hunt pass] — "**A confusion flag is never dismissed as the reviewer's ignorance (boss-ruled 2026-08-04)**"
- Complaint: An absolute making a claim broader than can hold, with a counterexample inside this file. Lens 11 states that "domain-standard tokens (`README`, `checksum`, `SHA-256`) pass". A cell that flags `SHA-256` or `checksum` as an undefined concept is exhibiting ignorance of standard vocabulary, and under this rule that flag cannot be dismissed as such — the three prescribed remedies would force the document to define standard terms, add path references for them, or promote them to the instruction floor. The two rules give opposite dispositions for the same flag, and because this one is boss-stamped and absolute, a triager following it inflates documents with definitions of common terms.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure the two sentences conflict; unsure whether the author regards "domain-standard token" as an implicit exception, which the file does not state."

### [Mode 2 — defect-hunt pass] — "the remedy is one of three, chosen at triage: define it in the file, add the explicit path reference, or promote the definition to the instruction floor when many files share the concept."
- Complaint: A closed enumeration that omits ordinary cases. A fourth remedy is routine and often correct: remove or reword the sentence so the confusing concept is not used at all — the right disposition when the concept was incidental, or when the flag reveals the sentence should not have been written. Others: the flag reveals a genuine defect elsewhere rather than a missing definition; the confusion arises from reviewer error, contradictory wording, or a mistaken name; or the definition is already adequately available. "One of three" is stated as exhaustive, so a triager confronted with a confusing sentence that should simply be deleted must instead define a term the document does not need — adding text to fix a problem better solved by removing text.
- Cells: claude-hunt-good, codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure the enumeration is closed by its wording; unsure how strictly the author intends "one of three" to bind." · codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 2 — defect-hunt pass] — "…promote the definition to the instruction floor when many files share the concept."
- Complaint: "When many files share" has no defined count and no repository boundary, so the condition is not observable.
- Cells: codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 2 — defect-hunt pass] — "Each flag quotes the sentence, gives the readings or the conflict, and where the defect class permits, a case where obeying the words does the wrong thing…"
- Complaint: Judgment-based conditional. "Where the defect class permits" gives no mapping from defect classes to required counterexample cases. Two cells can treat the same ambiguity differently, with one supplying a case and the other deciding the class does not permit one.
- Cells: codex-hunt-good
- Confidence (verbatim per cell): codex-hunt-good: "sure."

### [Mode 2 — Running the cells] — "Every tier-to-model assignment is an operator-set pinned value … Claude-runtime cells are fresh subagents — good = the pinned top model at high effort, floor = the pinned floor model (Sonnet-class today), set per launch."
- Complaint: Three problems compound. "An operator-set pinned value" and "set per launch" are opposites: a pinned value is fixed in a location and read; a per-launch value is chosen at invocation time. For the Codex leg the pin has a stated location (`TIER_TO_CODEX_MODEL` and `TIER_TO_REASONING_EFFORT` in `scripts/d-review-codex-cell.py`, verified), but for the Claude leg no pin location is given anywhere in the file or its referenced paths. And the agent is told to use "the pinned top model" while being forbidden to use its own knowledge of the model landscape — so it can neither read the pin nor derive it, and the only hint given, "Sonnet-class today", is prose the same paragraph declares non-authoritative. The Claude half of an eight-cell matrix cannot be launched as specified; an agent must either guess a model (violating the ruling) or stop.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure the Claude pin has no stated location; sure "pinned" and "set per launch" conflict."

### [Mode 2 — Running the cells] — "Every tier-to-model assignment is an operator-set pinned value — the boss picks the models; agents apply the pinned picks and never substitute their own sense of the model landscape…"
- Complaint: Undefined actor and terminology. "The boss," "operator-set," "pinned," and "model landscape" are not defined as executable concepts and have no executable identification procedure. The Codex script supplies one mapping, but there is no corresponding authority or location for Claude selections; a zero-context reader cannot know who sets an absent or stale pin, nor when a pin is authoritative.
- Cells: codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 2 — Running the cells] — "agents apply the pinned picks and never substitute their own sense of the model landscape"
- Complaint: Conflict with the referenced script. The script exposes `--model`, documented as overriding the tier mapping, without constraining that option to the operator; therefore "never substitute" and the callable interface support different behaviors.
- Cells: codex-hunt-good
- Confidence (verbatim per cell): codex-hunt-good: "sure."

### [Mode 2 — Running the cells] — "…their own sense of the model landscape, which is months stale by construction (boss-ruled 2026-08-04)."
- Complaint: Overbroad claim. "Months stale by construction" is false for an agent with freshly supplied model metadata or live authoritative tooling.
- Cells: codex-hunt-good
- Confidence (verbatim per cell): codex-hunt-good: "sure."

### [Mode 2 — Running the cells] — "Claude-runtime cells are fresh subagents — good = the pinned top model at high effort, floor = the pinned floor model (Sonnet-class today), set per launch."
- Complaint: Missing execution data and current-world dependency. No explicit path contains the Claude model pins, exact model IDs, effort values, or launch procedure — no launcher, configuration file, or executable procedure is identified. "Top model," "floor model," "Sonnet-class," and "today" require current model-landscape knowledge that the file elsewhere says agents must not supply themselves, and `Sonnet-class` is not self-documenting enough to select an exact model. A zero-context invoker cannot construct the required cells from this sentence.
- Cells: codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 2 — Running the cells] — "good = the pinned top model at high effort"
- Complaint: Reasoning effort is not a per-launch parameter of the subagent-dispatch interface available to an invoking agent: an agent type's model, reasoning effort and tools come from its definition, and a dispatch call carries a model override, not an effort override. The Codex leg handles this explicitly by passing `-c model_reasoning_effort=…` from the script; no equivalent mechanism is named for the Claude leg. The good/floor distinction on the Claude side therefore reduces to the model choice alone, so a provenance stamp claiming an effort level for a Claude cell records a value nobody set.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "unsure — I am reasoning from the dispatch interface described in my own tooling rather than from a document this file references, and a project-specific launcher I cannot see could expose an effort setting."

### [Mode 2 — Running the cells] — "The templates in [`prompts/`](prompts/) are the single prompt source for BOTH runtimes' cells — one place to improve wording for both legs."
- Complaint: A claimed guarantee backed by enforcement on one leg and by nothing on the other — an instance of the file's own lens 3. For Codex cells the claim is enforced: the script reads `PROMPTS_DIR / f"{args.cell}.md"` and fails with exit 2 if it is missing. For Claude cells, nothing in this file instructs the invoker to read `prompts/<cell>.md`, use it verbatim, or substitute `{TARGET_PATH}`; the Claude sentence specifies only the tier-to-model mapping, and nothing controls how Claude subagents are launched or proves they receive the same text. The Claude leg can silently drift to a paraphrased prompt, and since the file says the prompt is the highest-leverage text in the process, drift there invalidates the cross-runtime comparison that is the entire purpose of running both legs.
- Cells: claude-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure the Claude-side instruction is absent from the file." · codex-hunt-floor: "sure."

### [Mode 2 — Running the cells] — "The tier-to-model mapping and per-tier reasoning effort sit at the top of the script (authoritative; any ids quoted in prose are a snapshot), currently `gpt-5.6-sol` / `gpt-5.6-terra` at `xhigh`…"
- Complaint: Names. `gpt-5.6-sol` and `gpt-5.6-terra` are command-invoked model identifiers, yet `sol` and `terra` do not describe the models' role or capability. `xhigh` is likewise an externally consumed effort identifier without a self-contained meaning. These identifiers can be found by exact string after a reader knows them, but are not discoverable from the semantic terms "good," "floor," or "high effort."
- Cells: codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-floor: "unsure — the script's exact mapping makes these usable once found, but does not make the identifiers themselves self-documenting."

### [Mode 2 — The matrix] — "**The matrix:** {restate, defect-hunt} × {good, floor} × {each available runtime} — with both runtimes available, as today, eight cells."
- Complaint: Undefined/open set and unstable current-world claim. "Each available runtime" has no enumeration rule and no observation that establishes availability, while "both runtimes" assumes the set consists of exactly Claude and Codex. If a third runtime is callable, or one named runtime is installed but unusable, the first and second clauses yield different matrix sizes. "As today" is time-dependent and becomes stale without changing the file; a reader cannot know whether eight cells are required, whether a newly available runtime expands the matrix, or whether an unavailable one must be retried.
- Cells: codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 2 — The matrix] — "*Good* is best at cross-rule contradictions."
- Complaint: Unsupported and temporally unstable superlative. "Best" has no comparison set, measurement, record reference, or effective date. It can mean better than Floor, better than every model, or the best use of that tier. Model changes can invalidate the claim while the instruction continues to route work by it.
- Cells: codex-hunt-good
- Confidence (verbatim per cell): codex-hunt-good: "sure."

### [Mode 2 — The matrix] — "*Floor* is defined by capability — the lowest tier that actually reads the file, not the lowest tier that exists (a below-floor model flags mostly its own capability gaps); the framework's subagent default is the current instance."
- Complaint: Identifying "the lowest tier that actually reads the file" requires testing candidate models downward with no stop rule, no candidate list, and current-world model knowledge that the preceding paragraph forbids the agent from supplying; determining the lowest existing tier requires knowing and testing an open, changing model set, and "actually reads" is a per-run behavior, not a stable model property. The final clause then contradicts the definition it was appended to: if "the framework's subagent default" determines the floor cell's model, the floor is set by a framework default, not by an operator pin and not by the capability search just described, and it conflicts with "floor = the pinned floor model (Sonnet-class today)" — a framework default that equals "the current instance" would run the floor cell on whatever model the invoker is, typically the top model. The clause has at least two readings: (i) the subagent default model is the same model as the currently running agent, so a floor cell launched without an explicit model override is not a floor cell at all; (ii) the framework's default happens to sit at the floor tier, so no override is needed. These prescribe opposite launch behavior, and the resulting record would be stamped `tier=floor` with a top-tier model, poisoning the future which-cells-earn-their-keep analysis.
- Cells: claude-hunt-good, codex-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure the clause is ambiguous and conflicts with line 50." · codex-hunt-good: "sure."

### [Mode 2 — The matrix] — "*Floor* is defined by capability — the lowest tier that actually reads the file…"
- Complaint: Unexecutable criterion. Whether a model "actually reads" a file is an internal-state claim the coordinator cannot directly verify, and the sentence provides no test or threshold.
- Cells: codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-floor: "sure."

### [Mode 2 — The matrix] — "the framework's subagent default is the current instance"
- Complaint: Unexecutable by a zero-context reader. "The framework" is never named or introduced anywhere in the document (no product name, no path), and "the current instance" is likewise unresolved — instance of what: the invoking model, the invoking session, something else? Neither referent is resolvable from the sanctioned context, so the claimed default cannot be located and the last clause cannot select a model.
- Cells: claude-hunt-floor, codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-floor: "sure neither term is defined in-document; unsure how much this matters practically, since it's a parenthetical aside rather than an operative instruction." · codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 2 — The matrix] — "The full grid runs every time, and every cell reads the whole document."
- Complaint: Overbroad absolutes with unbounded labor. A runtime outage, context-limit failure, process error, unreadable target, unavailable agent, a document too large for a cell's context window, or an explicitly constrained review are ordinary counterexamples; the referenced script expressly permits nonzero execution failure, so the file itself demonstrates that a cell may not run or read the document. The sentence gives no exception, no distinction between attempting every cell and successfully completing every cell, and no valid completion state for those cases.
- Cells: codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 2 — The matrix] — "Pruning cells is a data question — which cells' findings survive context-aware triage, over tens of preserved reviews — decided by analysis of the records below, never by doctrine (boss-ruled 2026-08-04)."
- Complaint: "The records below" has no referent: no section below is titled or introduced as records. The nearest candidate is the record-preservation requirement inside the Synthesize paragraph, which points at `d-review-records/`, but "below" pointing at a clause two paragraphs later inside an unrelated heading is not a resolvable reference for a first-time reader, and "the records" is not the store's name. Separately, "never by doctrine" is asserted in a doctrine file, by a doctrine sentence, as the doctrine governing how pruning decisions are made — so obeyed literally it disqualifies itself, and gives no way to distinguish "doctrine may not decide which cells to prune" from "no doctrinal statement about pruning is binding".
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure about the dangling "below"; the self-reference point is minor and I am less sure it does practical harm."

### [Mode 2 — The matrix] — "Pruning cells is a data question — which cells' findings survive context-aware triage, over tens of preserved reviews — decided by analysis of the records below, never by doctrine…"
- Complaint: Undefined procedure and overbroad absolute. "Context-aware triage," "tens," and the analysis method are undefined; the record directory contains prior outputs, not a decision rule. "Never by doctrine" also fails when a governing policy requires a runtime or independent pass regardless of empirical yield. The sentence leaves no way to determine when pruning is permitted.
- Cells: codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-floor: "sure."

### [Mode 2 — The matrix] — "(The clarity cells run on today's runtimes; a Codex *wrapper of this skill* — the runtime-parity question — is separate and arrives at companion admission.)"
- Complaint: Unexplained, undefined jargon. "Companion admission" is defined nowhere in this file, appears in no referenced file, is not standard vocabulary, and is not linked by path; "arrives" does not identify an actor, artifact, event, or observable completion condition. It could mean a future event, a document class, or a process gate. "Codex wrapper of this skill" and "the runtime-parity question" are likewise introduced as externally meaningful concepts without definition or link, and "today's runtimes" is undated in a file whose other date references are explicit. This is the file's only statement about runtime parity, and a reader cannot tell whether it defers work, forbids work, or names a precondition, nor when the exclusion ends.
- Cells: claude-hunt-good, claude-hunt-floor, codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure." · claude-hunt-floor: "sure this phrase is undefined in the sanctioned context." · codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 2 — The prompt is the lever] — "Measured on a legacy doctrine-file review: seventeen findings under an adversarial-literal prompt against two under a charitably-worded one that silently repaired the defects being hunted."
- Complaint: Unexplained reference. "A legacy doctrine-file review" cites a specific, unnamed measurement (17 vs. 2 findings) as the evidentiary basis for the entire "prompt is the lever" doctrine, with no path, date, or record pointer — unlike the parallel measured claim in the Synthesize paragraph, which does name its source ("first NedsChorus run, 2026-08-03"). A zero-context reader cannot verify or locate this measurement.
- Cells: claude-hunt-floor
- Confidence (verbatim per cell): claude-hunt-floor: "unsure — illustrative, but offered as load-bearing empirical justification for a firm prompting rule."

### [Mode 2 — The prompt is the lever] — "The templates are the most leveraged text in the whole process — criticize them freely, in reviews and out of them; land changes deliberately (the context-holder rules on each, ideally micro-tested), never as silent drift (boss-ruled 2026-08-04)."
- Complaint: Undefined role and undefined procedure. "The context-holder" appears once, is never defined, and is a fourth role name alongside "the invoker", "the author", and "the merge agent" — with step 6 and the Synthesize paragraph both already claiming the "holds full context" description for two different names; the document never states these are synonyms, so a reader cannot tell who is authorized to approve a template change. "Rules on each" can mean approves each change, adjudicates each criticism, or establishes rules for each template. "Micro-tested" has no test definition, procedure, evidence location, or stop condition, and "ideally" makes it optional, so the rule's only verification step is discretionary; "deliberately" and "silent drift" are judgments rather than observable predicates. The file declares the templates "the most leveraged text in the whole process" and then leaves their change-control owner unnamed.
- Cells: claude-hunt-good, claude-hunt-floor, codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure the term is undefined." · claude-hunt-floor: "unsure whether "context-holder" is a plain descriptive phrase or an alternate name for the same defined role as "invoker."" · codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 2 — Synthesize] — "First a **merge agent** — independent, one job, zero judgment — folds all cell reports into ONE file: hunt findings deduped (the same sentence flagged with the same complaint is one entry, all catching cells listed; the same sentence with different complaints stays adjacent entries)…"
- Complaint: "Zero judgment" versus deduplication: deciding whether two cells flagged "the same complaint" or "different complaints" about the same sentence is a semantic judgment — two cells will describe one ambiguity in different words, and the file gives no matching rule. Determining which document position controls a cross-sentence conflict and how restatements align requires the same judgment. An agent given this role will either apply hidden judgment or refuse to dedupe.
- Cells: claude-hunt-good, codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure." · codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 2 — Synthesize] — "hunt findings deduped … nothing dropped or filtered"
- Complaint: "Nothing dropped" versus "deduped": deduplication drops entries by construction. The parenthetical partly rescues this ("all catching cells listed"), but the words stand in direct opposition, and the file later repeats the instruction as "Dedupe across cells" with measured drop rates (109 raw to ~35 distinct; 191 raw to 110 distinct — that is 81 and 81 entries not present in the merged file).
- Cells: claude-hunt-good, codex-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure." · codex-hunt-good: "sure."

### [Mode 2 — Synthesize] — "uncertainty wording preserved verbatim"
- Complaint: Unsatisfiable for a deduped entry: when three cells each state their own confidence in their own words and become "one entry", the sentence does not say whether all three wordings are carried or one is chosen — and choosing is judgment. Listing catching cells does not preserve each duplicate's wording.
- Cells: claude-hunt-good, codex-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure." · codex-hunt-good: "sure."

### [Mode 2 — Synthesize] — "ordered by **document position — never by any cell's opinion or rating**: … document order is the one ordering that carries nobody's"
- Complaint: Wrong claim and overbroad absolute. Document position can carry the author's judgment: an author can front-load favored claims, defer caveats, or order content rhetorically. Document order is therefore not uniquely free of anyone's judgment, and the rationale for the mandatory ordering is factually false in ordinary documents.
- Cells: codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-floor: "sure."

### [Mode 2 — Synthesize] — "The restatement reports merge alongside, aligned per section, so divergences sit next to the text they diverge about."
- Complaint: Unexecutable procedure. The skill accepts instruction files generally, but does not require headings or define a section for frontmatter, headingless prose, or reports whose sentence-level restatements cross a section boundary. "Aligned per section" therefore has no executable mapping for valid target documents without sections.
- Cells: codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-floor: "sure."

### [Mode 2 — Synthesize] — "cells report observations, never importance (measured on the first full-grid run: the raw stream arrived pre-labeled "47 HIGH" by its cells, and the labels, not the content, framed the first triage)"
- Complaint: An absolute contradicted by the evidence attached to it. The clause states as fact that cells never report importance, and its own parenthetical documents cells reporting importance on the only full-grid run cited. The intended meaning is presumably normative, but the sentence is written descriptively and is used to justify the merge agent's ordering rule, so a reader may conclude the pre-labeling problem is solved when the measurement says it is not — obscuring that the guard is unreliable and that the merge agent may need to strip labels, which its own "nothing dropped or filtered, uncertainty wording preserved verbatim" rule forbids it from doing.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure."

### [Mode 2 — Synthesize] — "**Every review preserves its record** — the merged cell-attributed findings, the triage dispositions, and every cell's output, each file stamped with its provenance: runtime, exact model id, effort level, cell, tier…"
- Complaint: Literal impossibility and overbroad absolute. A merged report and a triage-disposition file aggregate multiple cells and therefore do not have one truthful runtime, model ID, effort, cell, or tier, yet "each file" requires all five fields. Failed, timed-out, interrupted, or unavailable cells and reviews are ordinary counterexamples to "Every review preserves" every output; the instruction defines no record for failure and no stopping condition, and demands control over external runtimes the coordinator may not have.
- Cells: codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 2 — Synthesize] — "each file stamped with its provenance: runtime, exact model id, effort level, cell, tier … the Codex cell script stamps its own, Claude cell files are stamped when saved"
- Complaint: Demands work an agent cannot reasonably complete, with the actor unnamed. "Exact model id" is available on the Codex side (the script prints `model={model or 'config-default'}` from its pinned table, verified) but not on the Claude side: the invoker selects a subagent model by alias, not by exact id, so the invoker cannot stamp an exact id, and the cell's self-report is not something the invoker can verify. "Effort level" has the same problem. "Claude cell files are stamped when saved" names no actor and no format — passive voice where the Codex counterpart has an executable mechanism. The stamp exists specifically because "tier names drift across model eras; pins do not", so an unstampable or self-reported Claude id defeats the stated purpose for half the matrix.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "unsure on the exact-id point for the same reason as finding 47 — I am reasoning from the dispatch interface I can see rather than from a referenced document; sure that no actor or format is specified for the Claude stamping."

### [Mode 2 — Synthesize] — "as a dated directory under `d-review-records/`"
- Complaint: Introduced non-self-documenting name. `d-review-records` inherits the unexplained `d-review` abbreviation and is not self-documenting without prior knowledge of that name.
- Cells: codex-hunt-good
- Confidence (verbatim per cell): codex-hunt-good: "sure."

### [Mode 2 — Synthesize] — "as a dated directory under `d-review-records/`"
- Complaint: Incomplete specification. The path is unanchored: `d-review-records/` is given with no root, and the file's only anchoring statement — "(paths relative to the repo root)" — sits in the input-path sentence in a different section and is scoped there to review targets. A reader could place it relative to the current working directory or the skill directory. The directory-name format is also underspecified: "a dated directory" gives no date format and no naming convention beyond the date, while the existing entries follow `YYYY-MM-DD-<subject>`. Records from different reviews land in different places or under inconsistent names, damaging the cross-review analysis the store exists for.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure the anchoring and the naming format are unstated."

### [Mode 2 — Synthesize] — "Dedupe across cells — expect heavy overlap (first NedsChorus run, 2026-08-03: an under-scaled five-cell pass over a ~120-line skill returned 109 raw flags, ~35 distinct; the first full grid returned 191 raw, 110 distinct)."
- Complaint: A name that is hard to find by search. The project appears here as `NedsChorus` and elsewhere in the same file as `nedschorus` (in the GitHub URL), and the checkout directory is `nedschorus`. Lens 11 requires "full words a search matches verbatim" and "one shared token across a family of related names"; a case-sensitive search for either spelling misses the other. This is the project's own name in its own doctrine, and a reader cannot tell which casing is canonical when creating new artifacts, so the split propagates.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure the two spellings appear; unsure whether the author considers `NedsChorus` a legitimate prose rendering distinct from the repository identifier, which the file does not say."

### [Mode 2 — Synthesize] — "The **author** compares restatements against intent — no one else holds the intended meaning, and a comparator without it watches a faithful paraphrase of broken text agree with the text and misses the defect."
- Complaint: Overbroad absolute. Coauthors, decision-makers, recorded requirements, documented acceptance criteria, prior approved documents, an explicitly referenced specification, or an operator who commissioned the text can also hold or record intended meaning. A comparator without private intent can still detect contradictions, impossibilities, undefined terms, and divergence from a cited governing contract. "No one else" and "misses the defect" make claims broader than those ordinary cases permit, and the absolute can block review where the author is unavailable but intent is documented.
- Cells: codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 2 — Synthesize] — "The **author** compares restatements against intent…" together with "The two roles never mix: the cells generate the findings (the author never reviews their own text — that is step 5's warning)"
- Complaint: Self-contradictory, and unexecutable in a case the file itself cites. Comparing restatements against intent and deciding which divergences are findings *is* reviewing one's own text — the file assigns the author a finding-producing role in one clause and forbids the author any reviewing role in the next. Separately, "no one else holds the intended meaning" makes the comparison unexecutable for any document whose author is unavailable — an inherited doctrine file, a document written by a departed agent, or the "legacy doctrine-file review" cited as a run that already happened. In that case the restatement pass still runs ("The full grid runs every time"), producing four restatement reports with no one able to compare them; half the matrix produces output that cannot be consumed, with no fallback comparator and no instruction to skip the restatement cells.
- Cells: claude-hunt-good
- Confidence (verbatim per cell): claude-hunt-good: "sure on both points."

### [Mode 2 — Synthesize] — "The two roles never mix: the cells generate the findings (the author never reviews their own text — that is step 5's warning), and the author, who holds the intent, takes the notes and rewrites — that is what review notes are for."
- Complaint: Internal conflict and overbroad absolutes. The preceding sentence requires the author to compare restatements against intent, and the restatement-pass section says the resulting divergence is a finding; the author therefore participates in determining at least those findings while this sentence says cells generate the findings and the author "never reviews." Step 6 also assigns the context-holding invoker evaluative synthesis work. "Reviews" can mean any evaluative reading — in which case it conflicts with the author's required comparison, severity assignment, and second-pass planning — or only generating defect findings, which is not stated; the broad wording makes the author's required triage look prohibited. The roles cannot remain literally unmixed under the described procedure.
- Cells: codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [Mode 2 — Synthesize] — "Then the **author** reads that one file with full context … assigns all severity at step 6" / "The **author** compares restatements against intent" / "the author, who holds the intent, takes the notes and rewrites"
- Complaint: Conflicts with the document's own earlier, distinct use of "author". In the opening body, "the author" is unambiguously the original document's owner/writer, a role explicitly walled off from the review process; in step 5, the stated reason for delegating to independent fresh agents is precisely that "an author reviewing their own text has the worst of it — the weak parts are already rationalized." But here "the author" reads the full merged file, personally assigns all severities, and rewrites the document — the role elsewhere called "the invoker". Read literally with "author" meaning the document's original owner, this has that author doing hands-on severity triage of findings about their own text and then rewriting it — contradicting step 5's rationale and step 6's assignment of severity-setting to "the invoker". Read with "author" as a second name for "the invoker" in this section, the passage is internally consistent, but the document never states this equivalence.
- Cells: claude-hunt-floor
- Confidence (verbatim per cell): claude-hunt-floor: "sure the word "author" is used with apparently inconsistent referents across the document and the two usages are never reconciled; unsure whether every reader would resolve it the harmless way, since line 24's explicit warning against self-review makes the literal "document-owner" reading a real hazard, not a purely theoretical one."

### [Mode 2 — Synthesize] — "A bad rewrite is caught by the next review round, not by restricting the author."
- Complaint: The stated safety net is not mandated anywhere, and the guarantee is impossible. The sentence is the sole justification for letting the author rewrite unsupervised, and it asserts a next review round as a given, but no rule in the file requires one: the re-review sizing sentence describes how a re-review *would* be scoped but never says one must occur, step 6 ends the procedure with a one-line verdict, and "When NOT to use" then discourages re-review of long-shipped doctrine. Even when a later review happens it can miss the defect, repeat the author's assumption, fail to run, lack the context to recognize the regression, or arrive after the rewrite is deployed — and the file itself acknowledges that a document and reviewer can be wrong in the same way. "Is caught" promises an outcome the process cannot control, and the very first rewrite after a review is the one most likely to introduce new defects, since it touches every flagged passage at once.
- Cells: claude-hunt-good, codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure that no sentence in the file mandates the next round." · codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### Restatement notes — Mode 2 — the clarity review (doctrine and instruction files)
- claude-restate-good (on the two pass types): "an agent that has been in a restatement frame will produce a defect hunt that is "post-hoc," which I read as: it will justify or elaborate the reading it already committed to rather than hunting freshly."
- claude-restate-good (on the confusion-flag ruling): "The reasoning: the context the cell is guaranteed to have consists of the "instruction floor" (which I take to be the baseline instruction file, CLAUDE.md/AGENTS.md, as defined in the zero-context-reader definition above) plus the document itself…"
- claude-restate-good (on "Claude-runtime cells are fresh subagents … set per launch"): ""Set per launch" is ambiguous to me between two readings: (a) these pinned values are established at each launch of the review, so they can differ from run to run; or (b) the tier settings are applied when each cell is launched. I lean toward (a) given the surrounding emphasis on pinning, but the sentence does not settle it."
- codex-restate-good (same sentence): "the `floor` tier is the pinned minimum acceptable model, described as Sonnet-class "today." "Today" is deictic: the sentence does not explicitly say whether it means the file's date, the current run date, or another operational date. The model and tier must be selected separately for every launch."
- codex-restate-floor (same sentence, divergent reading): "Claude-runtime cells are fresh subagents: the good tier is the pinned top model at high effort, while the floor tier is the pinned floor model, presently Sonnet-class, and both choices are set for each launch."
- claude-restate-good (on the pinned Codex ids): "The current values are given as `gpt-5.6-sol` and `gpt-5.6-terra`, both at reasoning effort `xhigh`; the sentence does not say which of the two is "good" and which is "floor.""
- claude-restate-good (on "the framework's subagent default is the current instance"): "The final clause, "the framework's subagent default is the current instance," is ambiguous to me. Two readings I can see: (a) the harness's default model for a spawned subagent is the same model as the currently-running agent (subagents inherit the parent's model), which is offered as a fact one must account for when setting the floor tier; or (b) the model that currently occupies the floor position is the framework's default subagent model. I cannot tell which is meant from the sentence alone."
- claude-restate-floor (same clause): "states that the framework's default model for subagents is "the current instance" — read literally, this appears to assert that when no tier/model is explicitly specified, the subagent framework defaults to whatever model instance is currently running, though the exact intended connection between this clause and the floor definition just given is not fully spelled out, so I am not fully certain whether this is meant as an illustrative current value of "floor" or as a separate cautionary note about default behavior."
- codex-restate-good (same clause): "The additional statement that the framework's subagent default is "the current instance" appears to define the default model source, but the sentence does not fully specify how that default relates to the pinned floor-tier assignment."
- codex-restate-floor (same clause, divergent reading): "the framework's current instance is the default subagent."
- claude-restate-good (on "arrives at companion admission"): "The final clause, "arrives at companion admission," is jargon I cannot resolve with confidence. Readings I can see: (a) that wrapper will come into existence at the point when a Codex "companion" agent is formally admitted to (onboarded into) the project; or (b) the wrapper is itself the artifact that will be admitted, arriving alongside some companion. I cannot tell which from this text."
- claude-restate-floor (same clause): "I cannot determine what "companion admission" refers to; the document supplies no definition of this term elsewhere, so its precise meaning is unclear to me."
- codex-restate-good (same clause): "Creating a Codex-side wrapper for the entire skill is a separate runtime-parity matter, said to arrive at "companion admission"; that expression is not defined here, so I cannot determine the exact event or artifact it denotes."
- codex-restate-good (on the author's post-merge actions): ""Second pass" is not further defined in this sentence."
- claude-restate-good (on the record location): "The record is stored as a directory named by date, located under `d-review-records/` (the sentence does not state what this path is relative to; I read it as the repository root, consistent with the input section's convention, but the sentence itself does not say)."

---

## When NOT to use

### [When NOT to use] — "Code correctness, or an implementation reviewed against its design — a code-review skill's lane (the review-change candidate owns it when built), not this one's."
- Complaint: An unexplained external name that is not self-documenting. "The review-change candidate" is an identifier for a thing outside this document — a proposed skill — and is therefore in scope for lens 11, but "review-change" parses as "review a change" or "a change to reviews", and "candidate" is unexplained project jargon for a proposed-but-unbuilt item; "candidate" does not establish the eventual external name, so the term is hard to find by search. It appears nowhere else in this file and has no path, issue link, invocation name, or definition, and "when built" confirms it does not exist. The exclusion tells the reader to route code review elsewhere and names a destination they cannot find or verify, so the routing instruction is inert; a reader also cannot tell whether the skill exists yet, which determines whether the exclusion is currently actionable.
- Cells: claude-hunt-good, codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure." · codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### [When NOT to use] — "Code correctness, or an implementation reviewed against its design … not this one's."
- Complaint: Incompatible scope reading. This exclusion conflicts with the frontmatter reading in which the boss's request overrides all exclusions.
- Cells: codex-hunt-good
- Confidence (verbatim per cell): codex-hunt-good: "sure."

### [When NOT to use] — "Routine re-review of long-shipped doctrine — run a deliberate consistency sweep instead; this skill gates changes, not the archive."
- Complaint: An undefined procedure prescribed in the imperative, plus judgment-call conditions. "A deliberate consistency sweep" is presented as the alternative action ("run"), but it is not defined, not named as a skill, not given a path, and not described anywhere in this file — a reader following the instruction has nothing to run, so the practical effect is either doing nothing or doing the excluded review anyway. "Routine," "long-shipped," "deliberate," and "the archive" are likewise unmeasured: the reader must decide whether a given re-review is routine, with no test, while the opening scope sentence and the re-review rule both push the other way. A reader cannot determine whether a doctrine re-review is excluded, what procedure replaces this skill, or whether a live defect in an old file should bypass the stated gate; the harm occurs at the boundary between a recent doctrine change and archival maintenance, where different readers will choose different processes.
- Cells: claude-hunt-good, codex-hunt-good, codex-hunt-floor
- Confidence (verbatim per cell): claude-hunt-good: "sure." · codex-hunt-good: "sure." · codex-hunt-floor: "sure."

### Restatement notes — When NOT to use
- claude-restate-good: "The parenthetical says that ownership will fall to "the review-change candidate" — which I read as a proposed but not yet existing skill, referred to by that handle — once it is built. I cannot tell from this text whether "the review-change candidate" is a fixed name for that skill or a description of a candidate item on a list of skills to build."
- claude-restate-floor: "with that domain's ownership attributed (once built) to something called "the review-change candidate" — a term whose precise referent (a specific named candidate skill, versus a generic description of "the candidate that reviews changes") I cannot determine with certainty from this document alone"
- codex-restate-good: "Those tasks belong to a code-review skill; the text says the "review-change candidate" will own that work once it has been built, though it does not further define that candidate here."
- codex-restate-floor (divergent reading of "when built"): "those belong to a code-review skill, with the review-change candidate owning that work after the implementation exists."

---

## Whole-document findings

### [Opening body + When NOT to use] — "Designing the fix belongs to the author, and a reviewer who wants to propose an alternative design has left review — that is a create-design task, owned separately." / "a code-review skill's lane (the review-change candidate owns it when built), not this one's."
- Complaint: Naming — identifiers without a locator. "create-design task" and "review-change candidate" both read as hyphenated, skill-name-shaped labels for sibling work, but unlike the document's other forward-references (for example the what-can-code-check issue with a full URL), neither carries a path, issue number, or any pointer to where that work is tracked. A reader cannot tell whether these are real, findable skills-in-progress or just descriptive ad hoc categories invented on the spot.
- Cells: claude-hunt-floor
- Confidence (verbatim per cell): claude-hunt-floor: "unsure — each phrase is glossed in the same clause it appears in, which may satisfy the "local labels defined where they are used" exemption the document itself states elsewhere (line 41)."
