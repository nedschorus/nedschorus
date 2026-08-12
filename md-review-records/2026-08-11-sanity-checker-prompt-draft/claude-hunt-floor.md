<!-- provenance: runtime=claude model=claude-sonnet-5 effort=high cell=defect-hunt tier=floor target=/home/nedlern/agents/choirmaster/docs/drafts/sanity-checker-prompt-draft.md -->

Findings, in document order.

**1. Meta status note, line 3 — undefined terms "review cell" and "grid"**
Quote: *"it becomes a review cell only after the calibration protocol recorded in `md-review-records/2026-08-09-git-gatekeeper-design/subtract-cell-prompt-lessons.md` passes"*
Neither "review cell" nor "grid" (used two sentences later) is defined in this file. I checked the one referenced path with an explicit file path (`subtract-cell-prompt-lessons.md`) and it also only *uses* "grid" (e.g. "before any grid seat") without defining it — the defining document (something like an md-review tooling design) is never named or linked from this file. A future agent deciding whether this draft is eligible to "become a review cell" cannot determine what that status means or how it differs from being "wired into a skill" from the context this file gives access to. Sure.

**2. Lines 9–11 — plural/singular antecedent mismatch ("They" / "It")**
Quote: *"You receive MD files. They could be a design, plan, skill, or instruction document. It in turn may contain links to other documents or even pseudo code or code snippets."*
"MD files" and "They" are plural, but the next sentence switches to singular "It," and "document" (not "documents") is used with the plural "They." A literal reading of "It" could bind to the nearest singular noun, "instruction document," suggesting only instruction documents carry links/pseudocode — a different scope than "any MD file received." Unsure whether this is a real misreading risk or just loose phrasing, but the antecedent is genuinely ambiguous on the page.

**3. Line 11 — undefined term "comprehension fix"**
Quote: *"your findings are design changes — unlike a comprehension fix, a wrong one applied silently makes the design worse under a cleaner surface"*
"Comprehension fix" is never defined here, in the CLAUDE.md/CLAUDE.local.md instructions, or in any file this draft links by explicit path. The sentence's whole argument (why findings must go through triage rather than being applied directly) depends on the contrast with this undefined category. A reader with only this file's context cannot verify or apply the distinction being drawn. Sure.

**4. Line 11 vs. line 92 — "finding" is defined two incompatible ways**
Quote A (line 11): *"your findings are design changes"*
Quote B (line 92): *"Say explicitly which areas are already minimal — 'the rest is already lean' is a finding, and certifying leanness is as valuable as proposing change."*
Line 11 states as a flat equivalence that findings *are* design changes. Line 92 then calls a statement that no design change is warranted ("already lean") a finding too — explicitly contrasted with "proposing change." These are incompatible definitions of the report's core unit: one says every finding is a proposed change, the other says a finding can certify that no change is needed. A reader following line 11 alone would exclude leanness certifications from the report; a reader following line 92 would not know whether such certifications need the WHAT/WHY/LOST/COST/CONSEQUENCES structure defined for design-change findings. Sure.

**5. Lines 13–15 — "simpler, saner, safer" but only "saner" is elaborated**
Quote: *"...that would make this a simpler, saner, safer plan, instruction, or proposal. A saner plan can take several forms: [bullet list]"*
The assignment sentence promises three distinct qualities (simpler, saner, safer), but only "saner" gets a defining bullet list. It's left unclear whether the list is meant to cover all three (i.e. "saner" is being used loosely as a stand-in for the triad) or whether "simpler" and "safer" have their own separate, unstated criteria the reviewer must supply. Unsure whether this is intentional shorthand or a real gap, but it supports both readings as written.

**6. Lines 16/18 vs. 28/30 vs. 76 — the same rules restated in three places (self-violates the file's own "Duplicated normative homes" class)**
Quotes:
- Line 16: *"more reliable, more autonomous, with fewer or no user interventions required"*
- Line 28: *"more reliable, more autonomous, fewer or no user interventions; mechanical guarantees over trained agent habit; zero remembered human steps"*
- Line 18: *"easier to build or maintain — but not at the expense of reliability and testability"*
- Line 30: *"Simpler to build or maintain — welcome, but never at the expense of reliability or testability"*
- Line 76: *"A change that reintroduces a recurring human step — a remembered deploy, a manual check — is not a simplification; it moves cost from build-time to forever."*
The same normative claim (operate-cost beats build-cost; don't trade reliability for build convenience) is stated authoritatively in three separate sections with slightly different wording each time ("fewer or no" vs. "zero"; "and" vs. "or"). This is exactly the pattern the document itself names and warns against at line 66: *"Duplicated normative homes — the same rule stated authoritatively in two places, guaranteed to drift apart."* If one of these three is edited later (e.g. loosened from "zero" to "fewer or no"), the others silently disagree. Sure this is duplication; unsure whether the author would consider it a defect worth collapsing versus intentional layering (informal intro → formal ranking → discipline reminder).

**7. Lines 20, 73, 77 — the theoretical/intractable-problem rule stated three times**
Quotes:
- Line 20: *"looking for attempts to solve NP complete problems, like detecting every way a computer can edit a file... In the case of guarding a file from edits, simply backing up that file, then checking if it has been altered."*
- Line 73: *"Reject theoretical problems. An edge case earns machinery only when it has practical value to solve. Do not propose complexity to handle situations with no realistic path to occurring."*
- Line 77: *"On unsolvable or open-ended problems, reject complex near-solutions. Solve the known, easily identified parts, and note the unsolvable remainder explicitly..."*
Three separate sections independently instruct the reviewer to avoid over-engineering for intractable or low-value edge cases, each with its own framing (NP-complete design problems; low-probability edge cases; unsolvable/open-ended problems generally) and no cross-reference between them. Same self-violation of the "Duplicated normative homes" class as finding 6. Unsure whether these are meant to be three distinct facets or one rule said three times — they are similar enough that later edits to one are unlikely to propagate to the others.

**8. Line 20 — "NP complete problems" is a technically wrong label for the given example**
Quote: *"looking for attempts to solve NP complete problems, like detecting every way a computer can edit a file"*
"NP-complete" is a specific complexity-theory term for decision problems verifiable in polynomial time and reducible to/from other NP-hard problems. "Detecting every way a computer can edit a file" is not a bounded decision problem at all — it's an open-ended, unbounded adversarial-enumeration problem (closer to "undecidable" or simply "not a well-formed problem instance"), not a member of NP. A reader taking the term literally would be misled into thinking a polynomial-time verifiable certificate or approximation algorithm is the relevant frame, when the actual issue is that the problem isn't even well-posed. Unsure whether this is meant as loose shorthand for "very hard" (in which case it's just imprecise) or a load-bearing technical claim, but as written it is wrong when read literally.

**9. Line 66 — "guaranteed to drift apart" is an absolute claim broader than it can hold**
Quote: *"Duplicated normative homes — the same rule stated authoritatively in two places, guaranteed to drift apart."*
"Guaranteed" claims drift is inevitable. Ordinary counterexample: two duplicated statements can be kept in sync indefinitely by disciplined maintenance (e.g., a linter, a shared source-of-truth comment, or simply careful editors) — drift is a high risk, not a certainty. This matters here specifically because findings 6 and 7 show duplicated rules in this very file that have apparently *not* drifted (yet) — so the document's own content is a live counterexample to its "guaranteed" framing. Sure the word is stronger than the claim can support; unsure whether the author intends it as rhetorical emphasis rather than a literal guarantee.

**10. Lines 45 and 52 — the six-question ladder's terminal step assumes a model that may not exist**
Quote (line 45): *"For every component, step, state, or dependency — and for every model-mediated step especially — ask these questions in this order..."*
Quote (line 52): *"Delegate the residue — what remains is the genuinely interpretive part; leave it with the model, explicitly."*
The ladder is scoped to apply to *every* component/step/state/dependency, not only model-mediated ones ("especially" implies a superset, not an exclusive scope). But its final rung assumes there is a model to delegate to. For a component that was never model-mediated to begin with (e.g., a pure data-schema or architecture decision with no LLM in the loop), reaching step 6 has no defined landing point — the instruction to "leave it with the model" doesn't apply, and the file states no alternative outcome for that reachable case. Sure this case is reachable (the "every component... " scope explicitly includes non-model items); unsure whether the intended answer is "no finding" or something else, since the file doesn't say.

**11. Line 54 — "the ladder" is used before being named**
Quote: *"the ladder generates candidates; the priority order decides which are worth building"*
The six-question sequence is introduced under the header "The method: six questions, asked in order" (line 43) and never called "the ladder" anywhere before this point. A reader must infer the referent purely from the numbered-list shape of the preceding section. Unsure how much this actually impedes a reader — it's inferable from proximity — but it is an un-introduced name in a file whose stated audience has zero context beyond what it names.

**12. Lines 56–59 vs. line 90 — conflicting report-structuring instructions**
Quote A (lines 56–59): *"Two hunts deserve their own sections in your report, because they are where the highest-value findings hide: Prompts-to-code... A better way..."*
Quote B (line 90): *"Order findings by depth of simplification, deepest first."*
The first instructs the reviewer to give two specific hunts ("Prompts-to-code" and "A better way") dedicated sections in the report. The second instructs that findings be ordered as a single sequence by depth of simplification. The file never reconciles these: it's unclear whether prompts-to-code and better-way findings sit in their own sections outside the depth-ordered sequence (violating "order findings... deepest first" as a global rule), or whether depth-ordering applies within each of the two special sections separately while other findings form a third, implicit section. Sure these two instructions are not reconciled as written; unsure which reading the author intended.

**13. Line 59 — "a better way" / "unknown unknowns" hunt has no stopping point**
Quote: *"step back from the design as a whole and ask — is there a better way to solve this problem? And are we missing something important, an unknown unknown?"*
Unlike the six-question ladder (which terminates by construction — six questions, report the first that applies) or the cut-classes hunt (a fixed enumerated list), this instruction is open-ended: there is no criterion given for when the reviewer has looked hard enough, tried enough alternative framings, or can conclude nothing is missing. Unsure whether this is intentionally left to reviewer judgment (as "Reject theoretical problems" elsewhere trims scope generally) or an oversight, but as written there is no stated point at which this hunt is satisfied.

clean sections: The highest-value form: prompts to code; Two calibration examples from this project's ruled history.

