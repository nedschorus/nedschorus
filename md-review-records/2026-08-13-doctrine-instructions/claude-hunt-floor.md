<!-- provenance: runtime=claude model=claude-sonnet-5 effort=high cell=defect-hunt tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/doctrine-instructions.md -->

## Findings

**1. `# doctrine — seat instructions` intro, line 3** — *"Read [the seat model](agent-seat-model.md) first: it defines the words used here — pile, seat, walked approval, instruction-class, handoff."*

This list is presented as the set of terms this file borrows from the seat model. But the file also uses other terms defined only in the seat model and not listed here: "brief" (line 13, "that seat's brief also points here"), "slice" (line 13, "the git-gatekeeper's slice 6"), and "session" (line 7, "the next session can find them"). A reader who trusts the enumerated list as complete has no signal that these are technical terms with specific definitions elsewhere (e.g., "Slice" = "one numbered increment of a build plan, built and landed on its own") rather than ordinary English words. Confidence: sure the omission exists; unsure whether the author intended the list to be exhaustive or merely illustrative — the wording ("it defines the words used here") reads as exhaustive to me.

**2. Completion criterion, line 7** — *"the item the user chose has a written ruling in its durable home — an issue body, a governing document, or a CLAUDE.md line walked with him"*

It's ambiguous whether "walked with him" modifies only the last list item ("a CLAUDE.md line") or distributes across all three ("an issue body ... walked with him", "a governing document ... walked with him", "a CLAUDE.md line ... walked with him"). This matters operationally: the seat model ties walked approval specifically to instruction-class files (enforced by a hook), while the founding plan shows walks also used for non-instruction governing documents (e.g. `git-gatekeeper-design.md`: "boss-walked full-process revision 2026-07-24"). So both readings are independently plausible, and the sentence doesn't disambiguate whether an issue-body ruling needs a walk to count as "done." Confidence: sure the ambiguity exists; unsure which reading is intended.

**3. Pile item #31, line 13, vs. Boundaries, line 38** — *"**Coordinate with `gatekeeper` before designing it**, since that seat's brief also points here"* (line 13) contradicts *"Where a ruling lands in their territory, write it down and tell the user, who routes it — seats cannot hand work to each other."* (line 38)

Line 13 instructs direct seat-to-seat coordination with `gatekeeper`. Line 38, later in the same file, states flatly that seats cannot do this — all inter-seat routing must go through the user. Taken literally, "Coordinate with `gatekeeper`" has no legal mechanism under this file's own Boundaries section: doctrine has no channel to gatekeeper except through the user. (The First Action section, line 42, actually does it the Boundaries-compliant way — "put one question to him" — which only sharpens the inconsistency with line 13's phrasing.) Confidence: sure.

**4. Pile item #44, line 14** — *"reconciling the entry checkpoint, the rewrite policy, and the gatekeeper's import check with the goal of building a team rather than a museum"*

"Building a team rather than a museum" is evocative but its intended meaning for import-tracking doctrine is not explained anywhere in this file, in `CLAUDE.md`, in `agent-seat-model.md`, or in `nedschorus-founding-plan.md` (I checked; the phrase appears nowhere else in the referenced material). An agent picking up #44 with only this context has no way to know what distinguishes a "team" outcome from a "museum" outcome for import tracking. Confidence: unsure — the linked GitHub issue #44 may spell this out, but that's outside the context this file promises to be readable within.

**5. Pile item #26, line 18** — *"Dynamic agent-team model — sparring pairs, on-tap domain experts, spy-triaged oversight."*

Same issue as #4: "sparring pairs," "on-tap domain experts," and "spy-triaged oversight" are three distinct undefined concepts, none explained in this file or in the referenced `agent-seat-model.md`/founding plan. "Spy-triaged oversight" in particular is opaque without further context (what is a "spy" here?). Confidence: unsure for the same reason as finding 4 — the issue body may define these, but nothing in the given context does.

**6. "The ground you stand on," line 22** — *"`docs/cross-project/nedschorus-founding-plan.md` is the project's constitution — its standing decisions, the artifact-lifecycle rule, the fix ladder, the rewrite policy."*

I read `nedschorus-founding-plan.md` in full and grepped it for "ladder" and "fix ladder": the only occurrence of "ladder" is an unrelated mention ("git-gatekeeper/ladder/python-first are established practice"), not a definition of anything called "the fix ladder." The term "the fix ladder" is actually defined in `docs/cross-project/git-gatekeeper-design.md` ("the fix ladder (the founding plan's escalation sequence for failed work — retry, stronger model, then the boss)") — but that escalation sequence ("retry, stronger model, then the boss") does not itself appear anywhere in the founding plan either (grepped for "retry," "escalat," "stronger model": no matches). So an agent told by this line to find "the fix ladder" in the founding plan, per the instruction "read it first," will not find it there. Confidence: sure the term is absent from the founding plan as claimed.

**7. Same sentence, line 22** — *"`docs/cross-project/nedschorus-founding-plan.md` is the project's constitution"*

The founding plan document describes itself differently: its own opening line calls it *"the founding pair's workflow document"* ("This file is written for us... This is the founding pair's workflow document"), and its own documents table repeats that label ("This plan | The founding pair's workflow document."). Much of the document is a step-by-step, largely-completed boot narrative ("## The steps," several marked DONE/RESOLVED) rather than standing law. Calling it "the project's constitution" is a stronger and different framing than the document's own self-description, and could lead a reader to treat completed historical steps as still-active governing rules. Confidence: unsure — "constitution" may be intended loosely/metaphorically to mean "authoritative source for standing decisions," which is defensible given the "## Standing decisions" section, but the mismatch with the document's own stated identity is real.

**8. Boundaries, line 38** — *"seats cannot hand work to each other."*

This is stated as an unqualified fact, immediately after this same file cautions (line 34) that "Absolutes in instructions can backfire... that applies to what you write as much as to what you review." The referenced seat model itself does not state this as a fixed impossibility: its "Why there is no master agent" section frames the current state as a choice, not a constraint — "Revisit if seats ever need to hand work to each other without the user in the loop — which today they cannot." That "today" hedge is missing here, so line 38 is broader (an unconditional "cannot") than the source material it depends on actually supports, and than this file's own stated policy on absolutes would counsel. Confidence: sure the wording is unhedged where the referenced material hedges it; the practical harm is that a reader has no signal this is a revisable policy choice rather than a structural impossibility.

**9. Boundaries, line 38** — *"review methodology to `sanity-checker`"* vs. pile item #31, line 13 — *"**Review-system requirements** learned from the legacy gate"*

Both use "review" for what this file treats as different territories: #31 (review-system requirements / walked-approval evidence format) is doctrine's own pile item requiring coordination with `gatekeeper`, while Boundaries assigns "review methodology" to `sanity-checker`. Nothing in this file explains why #31 isn't simply sanity-checker's territory under the "review methodology" rule. (Reading `agent-seat-model.md`'s table resolves this — sanity-checker's remit is specifically the sanity-checker reviewer prompt and its place in the md-review grid, a different thing from check-in evidence format — but that disambiguation lives outside this file.) Confidence: unsure — plausible reading collision within this file alone, resolved only by consulting the seat model's fuller table.

**10. First action, line 42** — *"Then ask the user which item he wants thought about, and put one question to him first: whether [#31](https://github.com/nedschorus/nedschorus/issues/31)'s walked-approval evidence format should be designed here or in `gatekeeper`."*

The sentence names two questions ("which item" and the #31-routing question) but the word "first" attached to the second-named question conflicts with its position (second) in the sentence. Two incompatible executions follow: (a) ask "which item" first, then ask the #31 question as a follow-up; or (b) ask the #31 question before "which item," regardless of what the user ends up choosing. It's also unclear whether the #31 question is conditional on the user choosing #31, or must be asked up front no matter which item is picked. Confidence: sure the ambiguity exists; unsure which order is intended.

---

clean sections: "How the user judges a proposal" (lines 26–34, aside from being the source of the standard applied in finding 8).

