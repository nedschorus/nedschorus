---
issue: "[Build draft-md: the drafting-stage skill run before md-review (user-ruled 2026-08-22)](https://github.com/nedschorus/nedschorus/issues/142)"
---

# Build draft-md: the drafting-stage skill run before md-review (user-ruled 2026-08-22)

Build the `draft-md` skill: the drafting stage for durable MDs, run before md-review. User-ruled 2026-08-22.

The name is ruled, not open: the user prefers `draft-md` because "md-write sounds like a final product"; the stages stay deliberately separate — draft-md produces the draft, md-review checks it, and the user walks near-final MDs before they land. (draft-md plus md-review together are what "writing an MD" means here.)

Scope boundary against the founding plan's `md-write` commission (step 1, five skills — ghi-write's still-unbuilt sibling): md-write keeps the disposition machinery — search existing pairs, NEW/REVISE/REPLACE/REMOVE, ambiguity to the draft queue — deciding where an MD lands. draft-md owns how the draft is written. One migration to settle at build: the commission embedded the zero-context-reader rule in md-write; under this split that rule belongs to draft-md's stage.

What draft-md carries, from the rulings under GHI [Clarity registers: explanations and drafted instruction text land without the user's repeated corrections](https://github.com/nedschorus/nedschorus/issues/138): the CLAUDE.md drafting bullet operationalized at write time (identify the question the text exists to answer; answer as if a colleague asked, one concrete case first; the answer becomes the text), the zero-context read with the revise-toward-the-restatement rule, and the project's writing bars (standard SDLC terms, no invented vocabulary, no compression to fit a word count).

Timing, user-ruled: built at the end of the clarity-registers walk or soon after.

Search receipt: `grep -rn "draft-md" docs/ scripts/ .claude/ CLAUDE.md` returned no collision (2026-08-22); the founding plan names only `md-write`.

— filed from session https://claude.ai/code/session_01F9s9L5vPfehGRgrDHoc4Pk (doctrine-queue-drain seat)



## Added 2026-09-10: draft-md preserves the first write

**User ruling, verbatim:** "Nothing goes into the queue until it's already been scrubbed a few times. The best place to catch raw or 1st pass MDs is the write-MD or draft-MD skill."

This settles where a cold-read test case's raw half comes from, and it is a requirement on this skill rather than a separate build.

**Why it belongs here and nowhere else.** A cold-read test case is a trio: the raw first write, the perfected version, and the list of defects between them. The perfected version can be read off main whenever it is wanted. **The first write is perishable** — once a document is revised in place it survives only if someone kept a copy, and nothing captures one today. Every raw in the research test set exists because a person or an agent happened to save it at the time. The queue is too late, per the ruling above: a queued document has already been scrubbed several times, so the raw is long gone by then.

**What this asks of the skill.** When draft-md produces a draft, the draft as first written is preserved somewhere durable, with enough provenance to pair it later with whatever lands on main — the document's destination path, the date, and the commit or session it was written in. Where it is preserved is a build decision, not settled here; the log-store's per-seat area (`nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/<seat>/`, `scripts/seat-shared-file-ship.py`) is one obvious candidate, since it is off-repository, reachable from both machines and already add-or-replace.

**What makes a captured raw worth having**, measured 2026-09-10 and recorded at `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/2026-09-10-trio-candidate-screen/RESULT.md`: a raw-and-landed pair yields defect rows only where the landed version REVISED the raw. Of the six pairs already held, only ghi-write has that shape — 73 % of its raw sentences survive into the landed version, which grew 1.39x, and it is the one trio that produced a usable 33-row defect list. Two pairs kept none of their raw at all, having been rewritten; one kept 98 % but nearly tripled in size, so its diff is almost entirely additions rather than fixes. So capture is cheap and worth doing broadly, but not every captured raw will earn a defect list, and the screen for that is two numbers.

**Not asked for here:** any change to what draft-md writes or how. This adds only that the first draft is kept.


### The captured draft's name, user-ruled 2026-09-10

**His words:** "Maybe it should name those initial draft xxx-first-draft so they are easy to find."

Adopted. It fixes something measured: the seven first drafts already held in the research test set carry **seven different name shapes** for one kind of thing — `ghi-write-first-6a098f4.md`, `crash-recovery-design-first-raw-write-18-41Z.md`, `d-review-raw-first-write-2026-08-04T0341Z.md`, `walk-me-through-raw-first-write-…`, `topic-branch-design-first-round1.md`, and two more. None of them globs with the others. `<document>-first-draft` globs as `*-first-draft*` and reads as itself. `grep -rn "first-draft" docs/ scripts/ .claude/ CLAUDE.md` returns no collision (2026-09-10); the only hits anywhere are three nedlern-project tool files under a gitignored records directory, which are not MD captures.

Two consequences the build has to settle. Both follow from the name rather than being separate topics.

**1. A frozen first draft must be out of the review path, and the exclusion mechanism keys on the last token.** GHI [Genre-suffix naming for non-reviewable documents (-log, -report, -capture), and mechanical exclusion from the review instruments](https://github.com/nedschorus/nedschorus/issues/152) rules that a non-reviewable document's LAST filename token is a standard genre word — `-log`, `-report`, `-capture` — so the review instruments can refuse it mechanically and say which rule fired. A captured first draft is squarely that class: it is "an artifact saved off a real run", GHI [Genre-suffix naming for non-reviewable documents (-log, -report, -capture), and mechanical exclusion from the review instruments](https://github.com/nedschorus/nedschorus/issues/152)'s own definition of `-capture`, and its whole value is that nobody fixed it. Left inside the review path, some agent eventually improves it, and the evidence is gone. But under `<document>-first-draft` the last token is `draft`, which is not one of the three genre words. So either GHI [Genre-suffix naming for non-reviewable documents (-log, -report, -capture), and mechanical exclusion from the review instruments](https://github.com/nedschorus/nedschorus/issues/152) gains a fourth genre word or this class takes one of the three. **The distinction to preserve, whichever way it goes:** the live draft being worked on IS reviewable — that is what md-review is for — while the frozen copy kept as evidence is not. Same bytes, different role, and the name is what separates them.

**2. A first draft is immutable, and the obvious storage location is not.** The log-store's per-seat area now REPLACES a file of the same name (user-ruled 2026-09-09, `scripts/seat-shared-file-ship.py`), so the last write wins. For a file called "first draft" that is backwards: if two sessions ship one, the earlier draft is the one worth keeping. The store's other kinds are add-only, where the first write wins, which is the correct semantics here. So a first-draft capture should go to an add-only kind rather than to the seat's working area, or draft-md must refuse to overwrite one. This does not reopen the 2026-09-09 ruling, which was about a seat's evolving working files; a captured first draft is not one of those.
