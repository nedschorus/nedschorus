---
issue: "[Improve the fast cold read: deterministic context rule, clerical restatement work moved into code, a measured shorter mode (from the 2026-09-07 assessment and task #57)](https://github.com/nedschorus/nedschorus/issues/284)"
---

# Improve the fast cold read: deterministic context rule, clerical restatement work moved into code, a measured shorter mode (from the 2026-09-07 assessment and task #57)

## What this is

The fast cold read is one reviewer cell — Gemini 3.8 Flash at medium, about 100 to 150 s per document — run by `scripts/cold-read-fast-read.py` over one document, with the instructions in [.claude/skills/cold-read/prompts/fast-clarify.md](https://github.com/nedschorus/nedschorus/blob/main/.claude/skills/cold-read/prompts/fast-clarify.md) (803 words, the user's own text, PR [cold-read: the fast-clarify prompt as ruled in the user's walk of 2026-09-07](https://github.com/nedschorus/nedschorus/pull/274)) and a derived copy inside the script that the drift test in `scripts/cold-read-fast-read-test.py` holds byte-equal (PR [cold-read-fast-read-test.py: hold the embedded fast-clarify prompt in step with its source file](https://github.com/nedschorus/nedschorus/pull/276)). The cold-read skill runs it on every document, and the walk-me-through skill on every walk draft. Its report has three sections: a sentence-by-sentence restatement with `?nonsense?` and `?gap?` markers, where the reader struggled, and what the document implies but does not cover.

The user wants the improved fast cold read shipped. This issue is the work plan, from an outside assessment relayed by the user on 2026-09-07 ("Astra"), and from what remained of the reviewer-instructions review he put on hold that afternoon (MD-skills task #57).

## The assessment, and what each point is worth

1. **The restatement earns its place, as evidence.** The reviewer read "order conflicting work" as *requesting* conflicting work rather than *sequencing* it, and never flagged the ambiguity — only the restatement exposed the misreading; a defect list would have missed it. But a restatement loses distinctions of its own ("verifies report presence" became "verifies reports"), so it is evidence for the author to examine, never an authoritative correction. Keep the section; say in the skill what it is for.

2. **The context boundary varies between runs.** "Whatever your runtime already loaded" and *permission* to follow explicit-path references mean one run follows the glossary link and the next does not, so their "undefined term" findings differ. The assessment proposes that the report list the instructions and references it actually read. The seat's view, given to the user: listing what was loaded adds nothing (the provenance stamp records the runtime; git records that day's CLAUDE.md) and invites the reviewer to go looking; the real fix is upstream — make the rule an instruction, *follow every explicit-path reference once, one hop, no further* — and extend the report's existing "files examined" list by one line, the references followed. The user's reading: the proposal "seems to ignore the actual problem and simply make the report longer."

3. **"Fast" has a large output cost.** One run produced 6,955 words for a 4,793-word document; the MD-skills seat measured 3,000 to 7,400 words on a 658-word skill and a 1,967-word draft. The assessment's order of work, adopted here: move the clerical part into code first — assign each source sentence an id, attach the original passage to each restated block, check coverage mechanically — so the model spends its output on interpretation rather than copying four-word anchors; then measure whether a shorter mode loses findings before dropping the full restatement.

## Measured 2026-09-08 (cold-read-research, at the user's word, before any build)

Three arms on gemini-3.8-flash medium against the 33-row ghi-write defect list: A the prompt as it stands, B Question 1 at paragraph level, C Question 1 removed. **Single runs cannot separate the arms.** Arm A ran twice, hours apart, same everything: 82% recall (31 findings, 2,826 words, 151 s) and 39% (16 findings, 1,852 words, 106 s). C scored 64%, inside A's range; B gave 24% and 36%. Nothing is to be removed, shortened or kept on this evidence; separating arms needs about five runs each. The 42% figure cited above was measured on prompt 9cc0879 and the fast read now runs 031c59f, which differs substantively in Question 1, so that baseline is superseded.

**The misreading question has an answer, and it bears on step 2's form.** The list holds six rows of the kind only a restatement exposes ("final" read as content-finished; "executable" in the software sense). Two of them, rows 8 and 22, were never reported as findings by any of the five runs; row 8 surfaced only inside a Question 1 restatement, as a committed misreading, in two runs. The longest arm A run echoed the defective word verbatim every time and its 19 gap markers each duplicated one of its own Question 2 and 3 findings, while the runs that paraphrased put the wrong reading on the page where the author could see it. So the restatement earns its keep on exactly the ground the assessment claims — but only when it paraphrases, and the four-word-anchor form suppresses paraphrase. That is a finding about the form, not the length: step 2's sentence ids, which remove the copied anchor, are the change this points at, and step 3's shorter mode is not supported by anything yet.

A candidate 34th defect row for the ghi-write skill turned up on the way (three of five runs): step 1 says to edit the covering artifact but never says what to do when the covering issue is closed. Routed separately.

Record: `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/2026-09-08-shorter-restatement-arms-2/` (23 files, the three exact prompt texts included; the `-2` is the shipper's refuse-on-difference rule at work — the first ship carries a forward pointer).

## Work plan

1. **Context rule** — one sentence in the prompt making reference-following deterministic (one hop, every explicit path), and one clause on the files-examined list naming the references followed. Prompt change, walked with the user; the drift test carries the copy.
2. **Clerical work into code** — the script numbers the target's sentences before launch and hands the model a sentence-id'd copy; the report keeps the id in place of the four-word anchor; a coverage check in the script reports source sentences with no restatement. Prior art: `scripts/cold-read-restater-judge-runner.py` and its cell already score restatements against perfect versions by defect number, and the restatement rule in the prompt ("first four words, exactly as written") is the anchor this replaces.
3. **Measure before shortening** — superseded in part by the 2026-09-08 measurement above: a shorter mode is compared only with five or more runs per arm, after step 2 lands, and against a baseline re-measured on the current prompt; no shortening on the present evidence.
4. **The three placement questions left from task #57** — whether the review class becomes code, what happens to the other three prompts under `.claude/skills/cold-read/prompts/`, and whether `--prompt-file` stays on the cell launcher; and whether the launcher takes a chat-only answer as the report when Gemini answers in chat instead of writing the file (cold-read-research's ad-hoc runner already does).

Each step is its own PR; 1 and 4 are small, 2 is the build, 3 is a measurement.

## What it builds on

- `scripts/cold-read-fast-read.py`, `scripts/cold-read-fast-read-test.py`, `scripts/cold-read-agy-cell.py` (the fast tier pin, user-ruled "medium sounds like the right choice" 2026-09-07).
- The cold-read skill's step 2 and 3, which say what the report is and what the writer does with it.
- GHI [cold-read: one merged report per read — findings grouped by passage, with each cell's wording and the count of cells that raised it](https://github.com/nedschorus/nedschorus/issues/166) is the grid side of the same instinct (mechanical extraction and grouping, judgment left to the agent); this issue is the single-cell side and does not depend on it.

## Next action

Step 1 first: draft the two prompt sentences and walk them with the user, since the prompt is his text. The MD-skills seat holds this after its records walk closes.
