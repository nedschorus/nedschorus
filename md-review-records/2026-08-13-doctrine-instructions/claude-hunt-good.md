<!-- provenance: runtime=claude model=claude-opus-5 effort=high cell=defect-hunt tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/doctrine-instructions.md -->

I read the file, the checkout's `CLAUDE.md`, and the one document the file references by path for its vocabulary (`docs/agents/agent-seat-model.md`). The file has no YAML frontmatter. Analysis only — nothing edited.

## Findings

**1. Line 3 / 22 / 40–42 — three different "first" instructions.**
> "Read [the seat model](agent-seat-model.md) first" … "Most items here amend or extend it, so read it first" … "## First action — Read the founding plan and [#32]"

Three separate sentences each claim priority, and the section actually titled **First action** names neither the seat model nor the ordering of the other two. An agent that treats the "First action" section as authoritative — the natural reading of a section with that title — skips the seat model entirely and therefore never learns the definitions of pile, seat, walked approval, instruction-class and handoff that line 3 says are required to read this file. Harm lands on the very first session in the seat: the terms in lines 5, 7 and 24 are then unresolved. Confidence: sure the three statements conflict; unsure only which one the author intends to win.

**2. Line 5 vs line 22 — "each" versus "most".**
> "they belong together because each one amends the same foundation" … "Most items here amend or extend it"

Direct contradiction about the same set of pile items. It matters because line 22 turns it into an obligation — "be explicit about which standing decision a proposal touches." Under line 5 that obligation is unconditional; under line 22 there is a class of items that touch no standing decision and the file never says which items those are or what to do instead. An agent working #35 or #28/#29 (research threads) cannot tell whether it has failed the requirement or is exempt. Confidence: sure.

**3. Line 5 vs line 38 — review ownership is claimed twice.**
> "Your pile is **how the project should work**: what it preserves, how instructions reach agents, **what gets reviewed and when**." … "review methodology to `sanity-checker`"

"What gets reviewed and when" and "review methodology" are not separated anywhere in the file, and #31 (**Review-system requirements**) sits in this seat's pile while a whole other seat owns review. Two readings survive: this seat rules on review policy and `sanity-checker` implements it, or review questions belong to `sanity-checker` and #31 is misfiled here. Harm: duplicated or abandoned work on #31 — the same failure mode line 13 warns about for `gatekeeper`, but for a different seat and with no warning attached. Confidence: sure the boundary is undrawn.

**4. Line 7 — "a governing document" and "an issue body" as durable homes.**
> "has a written ruling in its durable home — an issue body, a governing document, or a CLAUDE.md line walked with him"

"A governing document" is a category with at least three members in scope (`nedschorus-founding-plan.md`, `agent-seat-model.md`, `git-gatekeeper-design.md`) and the file never says which one a given ruling belongs in, nor who decides. "An issue body" names a destination but no procedure — the file never says how an issue body is edited, and issue tooling is another seat's territory per the seat model. An agent completing work has no test for whether it has satisfied the criterion, which is exactly the field the criterion is supposed to be checkable against. Confidence: sure the list is underspecified; unsure whether the author considers the choice obvious per item.

**5. Line 7 — completion conditioned on an act only the user can perform.**
> "**Your work is done when** the item the user chose has a written ruling in its durable home — … or a CLAUDE.md line walked with him"

For any item that ends in CLAUDE.md, "done" requires a walk that has actually happened, i.e. an event the agent cannot cause. If the user is unavailable, defers, or declines, the seat has no defined ending: the file offers no alternative terminal state such as "drafted and queued for a walk." This is the precise failure the referenced seat model warns about ("a seat whose completion is defined as 'the outcome happened' can never finish, and an agent with no completion criterion either invents adjacent work or stalls"), so the brief contradicts the background it tells you to read first. Confidence: sure.

**6. Line 7 vs lines 16–18 — "a written ruling" does not fit research items.**
> "the item the user chose has a written ruling in its durable home"

Four of the eight pile entries are explicitly not ruling-shaped: #35 is "an open research thread," #28/#29 are "research bundles," #26 is "Design capture; research pending." If the user chooses one of those, the stated completion criterion cannot be met as written, and the file gives no substitute (a research note, a findings summary, a decision that no ruling is due). An agent will either manufacture a premature ruling on an open question or run without a stopping point. Confidence: sure.

**7. Line 7 — "the others are left where the next session can find them."**
> "and the others are left where the next session can find them"

This is stated as a completion condition but names no location, no artifact and no action. The pile items are GitHub issues that already exist, so the condition may be vacuous; or it may mean partial thinking must be written into the handoff, or into each issue. An agent cannot tell whether it must do anything at all to satisfy it, and cannot verify it before stopping. Confidence: sure it is unverifiable as written; unsure which meaning was intended.

**8. Line 11 — the wiki is not a durable home and has no location.**
> "Destined for a wiki page with subpages."

Two problems. First, it conflicts with line 7: the durable-home list is "an issue body, a governing document, or a CLAUDE.md line," and a wiki page is none of those — so work on the largest, most central item cannot be completed into the destination this line names. Second, "a wiki page" is unresolvable from this context: the file never says which wiki, where it lives, whether it exists yet, or how an agent writes to it. Harm: the agent working #32 either stalls at the point of writing the result or silently substitutes a different destination. Confidence: sure.

**9. Line 13 — "the legacy gate."**
> "**Review-system requirements** learned from the legacy gate."

Undefined term. `CLAUDE.md` names "the legacy system at `~/Projects/nedlern`" but nothing in either file defines a "legacy gate," so an agent cannot tell whether this means a review gate inside that legacy system, a former git gate, or something else, nor where to read about it. The phrase carries the entire provenance of the requirements the item is about. Confidence: sure it is undefined in the available context.

**10. Line 13 — "Dormant by ruling."**
> "Dormant by ruling until some class of work first required review"

The ruling is neither quoted, dated, nor located. An agent cannot read it to learn what was actually decided, what "some class of work" was meant to cover, or whether the dormancy had other conditions attached. It matters immediately, because the next clause claims the ruling's condition is now satisfied — a claim that cannot be checked against a ruling nobody can find. Confidence: sure.

**11. Line 13 — "that condition has now arrived" is an unverifiable state assertion.**
> "and that condition has now arrived: the git-gatekeeper's slice 6 needs a walked-approval evidence format"

"Now" is the moment the brief was written, not the moment it is read. A seat is explicitly resumable weeks later, and the `gatekeeper` seat may by then have designed the format, or slice 6 may have moved. The file states the world's current state instead of telling the agent how to check it (e.g. what to read to see whether the format exists). Harm: a future session opens work already finished elsewhere, or asks the user a routing question that was answered a month ago. Confidence: sure.

**12. Line 13 vs line 38 — "Coordinate with `gatekeeper`" against "seats cannot hand work to each other."**
> "**Coordinate with `gatekeeper` before designing it**, since that seat's brief also points here" … "Where a ruling lands in their territory, write it down and tell the user, who routes it — seats cannot hand work to each other."

Line 13 issues an imperative that line 38 declares impossible, and the referenced seat model agrees with line 38 ("a seat's only channel to another seat is through him"). No mechanism for coordinating is given: not a file, not a message, not the user. Taken literally, the instruction cannot be obeyed; taken as "raise it with the user," it duplicates line 42 without saying so. An agent will either invent a channel (writing into another seat's brief or handoff) or block on a step it cannot perform. Confidence: sure.

**13. Line 14 — "the entry checkpoint" and "the gatekeeper's import check."**
> "reconciling the entry checkpoint, the rewrite policy, and the gatekeeper's import check"

Three named things, of which only "the rewrite policy" is locatable from this context (line 22 attributes it to the founding plan). "The entry checkpoint" appears nowhere else in this file, in `CLAUDE.md`, or in the seat model, and no path is given. "The gatekeeper's import check" is presumably in `git-gatekeeper-design.md`, but this file does not say so and does not give the path. The item's whole task is to reconcile these three, so an agent that cannot find two of them cannot start. Confidence: sure for "entry checkpoint"; sure that "import check" is unpathed here even if guessable.

**14. Line 14 — "building a team rather than a museum."**
> "with the goal of building a team rather than a museum"

This metaphor is the stated decision criterion for the reconciliation, and it is never explained. Nothing in this file, `CLAUDE.md`, or the seat model says what "museum" behaviour would look like in import tracking or what makes an outcome "team"-shaped. Two agents could reach opposite conclusions and both claim the goal. Harm: the ruling produced is unreviewable against the criterion it claims to satisfy. Confidence: sure it is unexplained; unsure whether the source issue supplies it (the brief must stand alone).

**15. Line 15 — #25 is written as an answer, not as an open item.**
> "**Check-in timing** — infrequently-updated files committed immediately after update; append-type logs at logical breakpoints."

Every other pile entry describes a subject to think about; this one states a rule in the indicative. It supports two readings: this is the settled policy (in which case why is it in a pile of unsettled work, and where is it recorded?), or this is the proposal under consideration (in which case the phrasing hides that it is unsettled). Additionally "append-type logs" and "logical breakpoints" are undefined — which files count as append-type, and what makes a breakpoint logical, are exactly the questions the item exists to answer. Confidence: sure the reading is ambiguous.

**16. Line 16 — "Usage versus expectation."**
> "**Usage versus expectation** — an open research thread treating obsolescence as a design problem rather than a function of age."

The title names two things being contrasted and the gloss never connects either to obsolescence: whose usage, expectation of what, and how the pair bears on obsolescence are all missing. An agent asked to think about this item cannot state the question it is answering without opening the issue, which defeats the purpose of the pile summary. Confidence: sure the phrase is opaque in this context.

**17. Line 17 — which bundle belongs to which issue.**
> "[#28] and [#29] — two **research bundles**: agent introspection (…) and runtime behaviour (…)"

The mapping is implied only by parallel ordering. If the ordering is wrong or is later edited, an agent citing "#28, agent introspection" writes a false reference into a durable artifact, and nothing in the sentence would reveal the error. Confidence: unsure — positional pairing is a common convention and may be intended as sufficient; I flag it because the consequence is a wrong issue number in a ruling.

**18. Line 18 — "spy-triaged oversight" and "Design capture; research pending."**
> "sparring pairs, on-tap domain experts, spy-triaged oversight. Design capture; research pending."

"Spy-triaged oversight" is defined nowhere in this file or its referenced context, and it is not self-documenting: nothing about the word "spy" indicates what is being triaged, by what, or what oversight results. It is also a poor search key — a grep for "spy" in this project will not obviously lead anywhere. "Design capture; research pending" is telegraphic to the point of ambiguity: it may mean the design is already captured and research is the remaining work, or that this item's job is to capture design while research waits. Confidence: sure both are unresolvable here.

**19. Lines 22 and 24 — two authorities, no precedence rule.**
> "`docs/cross-project/nedschorus-founding-plan.md` is the project's constitution — its standing decisions…" … "`CLAUDE.md` at the repository root carries the operative rules agents actually read."

The file establishes two rule-bearing documents and never says which governs when they disagree — a reachable case, since line 24 says "much of this pile ends in a CLAUDE.md line" while line 22 says most items amend the founding plan, so a single ruling can touch both. It also leaves unstated whether a founding-plan amendment must be mirrored into CLAUDE.md, or vice versa, to take effect. An agent producing a ruling has no rule for where authority lives or how the two are kept consistent. Confidence: sure the case is reachable and unaddressed.

**20. Line 24 — "a quoted marker."**
> "enforced by `.claude/hooks/instruction-file-guard.py` and a quoted marker"

Undefined and unsearchable. The referenced seat model describes the actual mechanism as quoting the user's words into `.walk-approved` at the repository root, which the hook consumes for a single write — but "quoted marker" is not that name, so an agent reading this file cannot grep for it, cannot tell what file it lives in, and cannot tell what "quoted" refers to (the user's words? a delimiter?). Since the whole path for landing this pile's output runs through this mechanism, the agent is blocked at the point of actually writing a CLAUDE.md line. Confidence: sure.

**21. Line 24 — "changes land only through the user's walked approval."**
> "It is instruction-class: changes land only through the user's walked approval, enforced by `.claude/hooks/instruction-file-guard.py`"

The absolute "only" is broader than the named enforcement supports. The hook is a machine-local write-time guard in this checkout; ordinary counterexamples are a change to `CLAUDE.md` made in the Mac's separate clone, or a branch merged to `main` by the Mac-side agent, neither of which passes through this box's hook. The sentence presents a mechanical guarantee where the mechanism covers one path, so an agent may treat CLAUDE.md as unable to change without a walk and not check whether it in fact did. Confidence: unsure — this depends on where the guard runs, which the file does not state; the ambiguity is itself the point.

**22. Line 24 — "expect walks rather than commits."**
> "Much of this pile ends in a CLAUDE.md line, so expect walks rather than commits."

Taken literally this is wrong: a walked CLAUDE.md line still has to be committed, and per the checkout's `CLAUDE.md` it reaches `main` only through the interim lane — "commit to the working branch, push it, and the user's Mac-side agent reviews and merges." A walk replaces *unilateral* commits, not commits. Compounding it, the completion criterion at line 7 mentions writing the ruling but never mentions committing or pushing, so an agent obeying both sentences can declare an item done with the ruling sitting uncommitted in a worktree, invisible to `main` and lost if the seat is later retired. Confidence: sure.

**23. Line 30 — "This project's axis" is singular but three follow.**
> "**State the axis.** … This project's axis: simple-to-operate over simple-to-build; mechanical guarantees over trained habit; deterministic code over LLM prompts wherever the choice exists."

The instruction is a requirement ("state the axis") whose satisfaction test is unclear: must a proposal name one of these three, all three, or a proposal-specific axis of its own? "The axis" in the singular, followed by three distinct preference orderings, supports all three readings. Harm is mild but real — proposals "come back" for ignoring these criteria, per line 28, and this one cannot be checked. Confidence: unsure; the intent may be that the three jointly *are* the axis, which would still leave the instruction's test unstated.

**24. Line 34 — "as much as to what you review."**
> "that applies to what you write as much as to what you review"

This brief assigns the seat no reviewing duty anywhere — the pile is thinking and rulings, and line 38 puts review methodology in another seat. An agent cannot tell what it is expected to review, so the clause either refers to a role the file never grants or is loose phrasing for "proposals you assess." See also finding 3. Confidence: unsure — it may be idiomatic, but combined with finding 3 it deepens a real ambiguity about this seat's relation to review.

**25. Line 38 — the boundary list omits two of the seven seats.**
> "The gatekeeper's specification belongs to `gatekeeper`, review methodology to `sanity-checker`, session machinery to `fleet`, skills to `skill-builder`. Where a ruling lands in their territory…"

Four seats are enumerated; the seat model defines seven. `ghi` — which owns GitHub-issue knowledge and tooling — is absent, even though this pile is entirely issue-based and line 7 makes "an issue body" a durable home; `sidebar` is absent too. "Their territory" has only the four named seats as antecedent, so a ruling landing in issue tooling falls outside the stated routing rule with nothing said about it. An agent will either implement it itself (violating "You produce rulings; other seats implement them") or drop it. Confidence: sure the enumeration is incomplete; unsure whether the omission was deliberate.

**26. Line 42 — the ordering of the two questions contradicts itself.**
> "Then ask the user which item he wants thought about, and put one question to him first: whether [#31]'s walked-approval evidence format should be designed here or in `gatekeeper`."

The sentence introduces the question that must come "first" *after* the question it is supposed to precede, and "first" has no stated referent — first before the item choice, or first among a set of questions asked once the item is chosen. Both readings survive. The distinction is material: if the user picks #31 as his item and only afterwards is asked whether #31 belongs in this seat at all, the seat may begin work it is then told to hand over. Confidence: unsure the reading is genuinely blocking; sure the ordering is stated ambiguously.

clean sections: none — every section (preamble, "The pile", "The ground you stand on", "How the user judges a proposal", "Boundaries", "First action") carries at least one finding.

