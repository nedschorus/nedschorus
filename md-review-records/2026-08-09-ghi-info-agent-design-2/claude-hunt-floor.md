<!-- provenance: runtime=claude model=claude-sonnet-5 effort=high cell=defect-hunt tier=floor target=/Users/el/Projects/nedschorus/.claude/worktrees/shared-conversation-discussion-eb34e2/docs/drafts/ghi-info-agent-design.md -->

I read the target file in full, then verified every explicit-path reference it makes (the two draft files, `../issues/26-dynamic-agent-team-model.md`, and `~/Projects/nedsmessenger/adapter/adapter.py`) to confirm they exist and check for cross-document conflicts, since those are part of my given context. Here are the findings, in document order.

---

**1. Frontmatter status vs. "Decision trail" paragraph (lines 2, 8)**
Quote: `status: design awaiting the user's walk (md-review first)` vs. `this file's design decisions were ruled 2026-08-07 (walk anchor with per-item dispositions: [ghi-info-agent-plan-draft.md]...)`.
The frontmatter says a walk is still pending; the very next paragraph says the design's decisions were already "ruled" through a walk. A reader with only this file cannot tell whether this document reports settled decisions or a still-open proposal — one plausible reading is that a *different* walk (of the linked plan-draft) already ruled the underlying decisions while *this* synthesis document awaits its own separate walk, but the file never states that distinction. Unsure — resolvable with a careful reading, but the two sentences read as flatly contradictory on a first pass, and the file gives no explicit signal that "the walk" in each sentence refers to a different event.

**2. "domain-knowledge-agent class" terminology (line 14)**
Quote: `The first build of the domain-knowledge-agent class defined in [26-dynamic-agent-team-model.md]`.
The referenced source names this class "Domain-knowledge agents" (space, no compound hyphenation before "agents"), while this file writes "domain-knowledge-agent class" (fully hyphenated, singular). A grep for one form will not find the other. Sure this is a search-ability defect (class i); the underlying identity is otherwise clear from context.

**3. Lifecycle contradicts the class it instantiates (line 34, referencing line 14)**
Quote: `There is no idle state for a headless resume-per-question agent; idle describes a live waiting process (an interactive session, a watcher), which this is not.`
This file explicitly identifies ghi-info as "the first build of the domain-knowledge-agent class defined in [26-dynamic-agent-team-model.md]" (line 14), and that source states the class has "Lifecycle states active / idle / exited." This document then asserts flatly that "there is no idle state" for this agent, without acknowledging it is deviating from the lifecycle model of the class it claims to instantiate. Sure the two statements conflict textually; unsure whether this is a real design decision (a deliberate override) that simply isn't flagged as such, or an oversight — either way a reader relying only on this file plus its cited reference hits an unreconciled contradiction.

**4. Cross-link write exclusivity (line 17 vs. line 44)**
Quote: `Cross-link edits are ghi-info's only write class.` vs. later: `a writer who finds a relation ghi-info missed adds the cross-link while editing, and the next delta refresh teaches the corpus.`
"Cross-link edits are ghi-info's only write class" supports two readings: (a) cross-link edits are the *only kind of write ghi-info itself performs* (compatible with other agents also editing cross-links), or (b) ghi-info is the *exclusive owner* of cross-link edits (no one else may write them). Line 44 explicitly describes a different agent ("a writer") adding a cross-link during its own edit, which only make sense under reading (a) but reads as a direct violation under reading (b). Sure this is a genuine ambiguity — the sentence at line 17, read on its own, favors reading (b).

**5. Undefined routing vocabulary (line 20)**
Quote: `ghi-info never decides routing (queue vs GHI vs pair vs bare MD — \`ghi-write\`'s judgment)`.
"queue," "pair," and "bare MD" are none of them defined anywhere in this file, and the file does not link to wherever `ghi-write`'s routing logic (which owns this judgment) is documented. A reader cannot tell what these four routing destinations mean or how they differ. Sure — none of these terms recur with an explanation elsewhere in the file, and no path is given.

**6. "the length limit" never stated (line 20, elaborated line 51)**
Quote: `issue bodies grown past the length limit while nobody was writing` and `Over the limit, the writer is told immediately`.
The mechanism (a length check the write tool enforces) is defined, but the limit itself — its value, units, or where it is configured — is never given or pointed to. Sure this is a real gap under the "mechanism defined, limit unstated" pattern: an agent trying to reason about "how close am I to the limit" has no way to find out from this file.

**7. "one tiered line per closed issue" (line 26)**
Quote: `issues-closed.md — one tiered line per closed issue`.
"Tiered line" is not defined anywhere in the file — it's unclear what the tiers are, how many there are, or what determines an issue's tier. Unsure whether this is meant to be self-evident jargon from elsewhere in the project, but taken on this file alone it is opaque.

**8. "pair-MD" vs. "pair MD" spelling (lines 17, 28, 51)**
Quote: `every pair MD backlinks its correct GHI(s)` (line 17) and `the linked pair MD` (line 51) vs. `covers pair-MD edits` (line 28).
The same concept is spelled with and without a hyphen in different places. This is a searchability problem (class i): grepping one form misses the other.

**9. "a gitignored conventional path" (line 27)**
Quote: `a gitignored conventional path in any checkout, regenerated by script on any machine`.
No actual path or naming convention is given, nor is there a pointer to where "the convention" is specified. A future agent implementing or debugging the mirror has no way to find out where it actually lives on disk from this file. Unsure whether this is intentionally left to a linked implementation doc not referenced here, or a genuine gap.

**10. "the box convention" / "the launch-claude work" (line 33)**
Quote: `the Ubuntu box (\`~/agents/ghi-info\` per the box convention)... Mac-side callers reach it over SSH, the path the launch-claude work built.`
Both "the box convention" and "the launch-claude work" are referenced as if already known, with no definition and no explicit path given (unlike the two design drafts and the issue file, which are linked). Sure these are unexplained references per this file's own context rules.

**11. "a killed run is a named failure" (line 40)**
Quote: `One overall timeout; a killed run is a named failure.`
It's unclear what "named" adds here — whether it means the failure is logged/classified under a specific label (and if so, which), or something else. It is also not stated whether a killed run counts as "a failed ask" for purposes of the fallback ladder described two sentences later. Unsure — plausibly a minor phrasing issue, but as written it leaves the actual behavior on timeout unspecified.

**12. Long-lived token presented as solved vs. flagged as previously failed (line 40 vs. line 94)**
Quote: `Auth is the box's long-lived token (interactive logins expire with no human to refresh them).` vs. `Whether the box's \`gh\` auth and the long-lived Claude token survive unattended operation (the box's auth has expired before).`
Line 40 presents the long-lived token as the fix for the interactive-login-expiry problem. Line 94, in "Verify at build," flags this exact token's survival as an open, unverified question and notes "the box's auth has expired before." These sit in tension: the earlier passage reads as a settled design justification, while the later passage reveals the chosen solution has a track record of failing at exactly the thing it's meant to guarantee. Unsure whether "the box's auth" in line 94 refers to the same long-lived Claude token or a separate `gh` credential, since the sentence names both together — but under either reading the token's reliability is undercut by information later in the same file.

**13. "cooperative posture" vs. "cooperative threat model" (line 44 vs. line 56)**
Quote: `the missing-pointer residual is accepted under the cooperative posture` vs. `gh api, MCP tools, and creative quoting slip past under the cooperative threat model`.
These appear to name the same underlying assumption (agents are not adversarial) but use two different terms, neither defined. A grep for one will miss the other, and neither occurrence explains what the posture/model actually entails. Sure this is an inconsistency; unsure whether they were meant to be the same concept or are subtly distinct.

**14. Fail-open scope ambiguous (line 50)**
Quote: `Fail-open: ghi-info unreachable means the write proceeds unchecked.`
Immediately preceding this, the same bullet says the tool "runs the mechanical checks (body length; openable references), consults ghi-info with the draft body." It's unclear whether "unchecked" means only the ghi-info similarity adjudication is skipped (mechanical checks still run) or whether the whole tool bypasses all checks when ghi-info is unreachable. Sure this supports two incompatible readings as written.

**15. Length check timing contradicts "before an issue write lands" (line 18 vs. line 50–51)**
Quote: `The write-path tool (below) consults ghi-info with the actual draft body before an issue write lands.` and the ordering in line 50 ("runs the mechanical checks... consults ghi-info... writes via \`gh\` internally") vs. line 51: `no agent counts words — the tool measures the body after the write.`
Line 18 and the sequencing in line 50 both describe checks (including "body length") as happening before the write lands. Line 51 then states plainly that body length is measured *after* the write. These directly conflict on whether an oversized body is caught before or after it is published to GitHub. Sure — this is a literal contradiction between two passages describing the same mechanism.

**16. "the revision convention" undefined (line 52)**
Quote: `a comment cannot be mechanically rewritten into the body edit the revision convention requires` ... `for the genuinely new events the convention permits`.
"The revision convention" is never defined or linked anywhere in this file, yet the entire justification for denying `gh issue comment` rests on it. Sure this is a load-bearing undefined term — a reader cannot evaluate or apply the comment-handling rule without knowing what the convention actually requires.

**17. "fixed catalog" that can "grow" (line 52)**
Quote: `an event kind from the fixed catalog (instance outcome, completion, ruling challenge; growth only by explicit ruling)`.
Calling the catalog "fixed" while also stating it can "grow... by explicit ruling" is a literal tension: a fixed set, by definition, does not grow. Unsure whether "fixed" is meant loosely (closed to ad hoc addition by any agent, but formally amendable) rather than literally immutable — that reading is plausible but not stated, so taken literally the two clauses conflict.

**18. "the instruction-file guard pattern already live on main" (line 55)**
Quote: `the audited one-use override (the instruction-file guard pattern already live on main)`.
No path or link is given for this pattern, and it's not otherwise defined in this file. A reader cannot verify what "the audited one-use override" mechanically consists of. Sure this is an unexplained reference under this file's own context rules.

**19. "The maintenance sweep" undefined and disconnected from named sweeps (line 56)**
Quote: `The maintenance sweep catches what slips — an unchecked write still appears in the delta.`
The division-of-labor table (line 70) names a "supersession sweep" and a "link-integrity scan" as script-run mechanisms, but never a "maintenance sweep" — so it's unclear whether this is a third, unlisted mechanism or a loose reference to one of the two named ones. Separately, the claim that "an unchecked write still appears in the delta" doesn't by itself establish detection: any write (checked or not) appears in the delta refresh per the mirror section — the file never states how a write that slipped past the hook is distinguished from a normal one once it's in the delta. Sure on the naming inconsistency; unsure on whether the detection gap is a real design hole or just terse phrasing.

**20. "never correctness" contradicted by "Known holes, accepted" (line 61 vs. line 56)**
Quote: `a missed trigger costs efficiency (a late duplicate catch, one comment retry), never correctness.` vs. `gh api, MCP tools, and creative quoting slip past under the cooperative threat model.`
"Never correctness" is an absolute claim that the hook+tool layer preserves correctness whenever the skill misses. But the file's own "Known holes, accepted" bullet describes writes that bypass the hook layer entirely (via `gh api`, MCP tools, or creative quoting) — in that case neither the skill nor the hook adjudicates the write, so a duplicate or oversized issue can land unchecked, which is a correctness failure, not merely an efficiency one. Sure the two passages are in tension; the ordinary counterexample is exactly the scenario the file itself names two paragraphs earlier.

---

clean sections: Division of labor; Deliberately not in version 1

