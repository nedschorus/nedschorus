---
issue: "[cold-read: one merged report per read — findings grouped by passage, with each cell's wording and the count of cells that raised it](https://github.com/nedschorus/nedschorus/issues/166)"
---

# cold-read: one merged report per read — findings grouped by passage, with each cell's wording and the count of cells that raised it

## Problem

A cold read (the review instrument formerly named md-review, renamed 2026-08-25) runs eight reviewer cells over one document — four defect-hunt cells and four restate cells, two model families at two tiers each — and leaves eight report files in the record directory. The agent that commissioned the read then reads all eight itself, works out which findings are the same defect in different words, sorts them into fixes and questions, and walks them with the user.

That merge is the largest step of the instrument that is still done by hand, and it is expensive. On 2026-08-25 the MD-skills seat had seven comparisons made between pairs of eight-report sets; each comparer spent 10–20 minutes and 130,000–230,000 tokens, most of it on exactly this step: extracting every numbered finding with its quoted passage, grouping findings that quote the same passage, and deciding whether two findings about one passage describe one defect or two. Only the last decision needs judgment. The rest is mechanical, and today no program does it.

The user's words (2026-08-25): "we can present to the agent that commissioned the cold read that they can get back a single MD file with all the notes from the 8 reads, then I'm not sure what prompt we give them at that point, but it seems to be ok, and they seem to present the material to me well." And: "if a bunch of agents complain that is not 100% truth, but it is data."

## What is wanted

One merged report file per cold read, produced by the grid after its eight cells finish, alongside the eight originals (which stay — the merge is a view, not a replacement).

1. **Extraction is mechanical.** Every defect-hunt report is a numbered list; each finding quotes a passage of the target. A script pulls every finding with its quote and its cell of origin.
2. **Grouping by passage is mechanical.** Findings whose quotes overlap in the target are one group. Groups are ordered by position in the document, the order the eight reports already use.
3. **Sameness is judgment, and stays with an agent.** Within a group, whether two findings are the same defect or two defects about one passage is decided by the commissioning agent, not the script. The merged file presents the group with each cell's wording, so that decision is made from the evidence in one place rather than from eight files.
4. **Agreement is carried as a count, never as a verdict.** Each entry says how many cells raised it and which. The user ruled that this is data, not truth: a finding raised by one cell is presented the same way as one raised by four, with its count. No entry is dropped, ranked, or pre-sorted by tally.
5. **Restate disagreements are a separate section.** The four restate reports find ambiguity by disagreeing with each other about a sentence's meaning, not by listing findings; a measurement on 2026-08-25 found that only 35% of those disagreements are ever explicitly flagged by a restater, so they cannot be extracted as findings. What the merged file can do mechanically is align the four restatements sentence by sentence so the agent sees them side by side.
6. **Nothing is decided for the user.** The sort into fixes and walk items, and the walk itself, stay with the commissioning agent and the user, exactly as today. The user's ruling of 2026-08-25 (walk item 5c): every change is discussed with him; the easy fixes are batched as one step of the walk, not applied silently.

What the commissioning agent is told to do with the merged file — the prompt or skill text at that point — is left open by this issue. The user's words: the current behaviour "seems to be ok, and they seem to present the material to me well." That is the baseline the design must not make worse.

## What it builds on

- The grid script (`scripts/cold-read-grid.py` on branch `MD-skills`; on main it is still `scripts/md-review-grid.py` until the 2026-08-25 rename lands) already knows when all eight cells are done and where the reports are; the merge is a final step there.
- The report contract in `scripts/cold-read-cell-common.py` (branch `MD-skills`; created by the report-to-file fix that closes GHI [md-review-grid reports eight reviews saved when eight cells produced nothing](https://github.com/nedschorus/nedschorus/issues/164), not yet on main) fixes the shape the merge can rely on: numbered findings, quoted passages, a closing "clean sections:" line, one provenance stamp per report.
- Three record sets from 2026-08-24 with their hand-made comparisons, and twelve older sets with the user's dispositions, are test material: a merge script can be checked against what a comparer produced by hand.

## Next action

Design first, then build: the merged file's format, the passage-overlap rule, and what the agent is told. The design goes through a cold read before the build. Filed as a follow-on to GHI [md-review-grid reports eight reviews saved when eight cells produced nothing](https://github.com/nedschorus/nedschorus/issues/164), which hardened the grid's per-cell reporting; this is the step after that reporting.

## Relations

- GHI [md-review-grid reports eight reviews saved when eight cells produced nothing](https://github.com/nedschorus/nedschorus/issues/164) — the grid's per-cell success and failure reporting; this issue starts where that one ends.
- GHI [Adversarial whole-package review — two runtimes, blind first passes, threaded Q&A (doc: docs/issues/8-adversarial-package-review.md)](https://github.com/nedschorus/nedschorus/issues/8) — the one-off two-reviewer synthesis of the founding review, the nearest precedent on record.
- GHI [use-codex skill: one place that says how this project invokes Codex headlessly](https://github.com/nedschorus/nedschorus/issues/165) — the use-codex skill; the Codex cells this merge reads are launched the way that skill will describe.
