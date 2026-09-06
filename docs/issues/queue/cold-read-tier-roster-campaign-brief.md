# Campaign brief: which reviewer cells make up the full, faster, and fastest cold-read tiers

Status: queued for a long-lived seat to run. Written 2026-09-03 by the reboot-test seat at the user's direction. The instrument, targets, scorer, and prior rulings live in the MD-skills seat's records at `~/agents/MD-skills/cold-read-records/2026-08-29-walk-reviewer-model-trial/` — read its `METHOD.md` in full before running anything; this brief assumes it and does not repeat it.

## The question

Which set of reviewer cells — each a (model, effort) pair — should run a cold read at three tiers, judged on defects caught against ground truth:

| Tier | Criterion (user, 2026-09-03) | Secondary |
| --- | --- | --- |
| Full | ≥ 90% of true defects caught; minimal false positives and false negatives | wall time is secondary |
| Faster | ≥ 75% caught | both accuracy and speed |
| Fastest | ≥ 50% caught | defects per minute is the primary metric |

The user's expectation, on record: the faster tier "may not be that useful". Measure it anyway; the result may be that it collapses into one of its neighbours.

Every cell's processing time is reported beside its findings. Speed and quality are reported separately, never folded into one score.

## What is already known (do not re-measure)

From today's independent deduplication of three cold-read rounds on one design document (reboot-test, `cold-read-records/2026-09-02-238-topic-branch-creation-script-design*/dispositions.md` and the dedup agents' tables recorded in the walk minutes `docs/walk/review-stopping-rule-findings-sorted-by-what-they-change-minutes.md`):

- Unique defects per cell over three rounds: claude-opus-5 high 34; gpt-5.6-sol xhigh 24; gpt-5.6-luna xhigh 21; claude-sonnet-5 high 1; gemini-3.6-flash 1 (trivial). Sonnet is the cold-read run's one dead cell. No two-cell subset held coverage (lost 10–26%); the three non-sonnet cells matched the full cold-read run minus one unsure cluster.
- Gemini 3.6 Flash: 19 findings, all real, 1 new and trivial, strict subset of opus each round, 77–111 s. Consistent with the 2026-08-30 ruling that Gemini stays benched. Do not include it.
- Median durations across all 197 recorded reports on this machine: opus high 706 s; sol xhigh 490 s; luna xhigh 559 s; sonnet high 345 s; terra low (fast-clarify) about 60 s.

From METHOD.md, rulings that bind this campaign:

- Two runs minimum per cell; one run ranks nothing. Concurrency held constant within any compared set; cells-in-flight recorded per cell. A fallback cell (`fallback_from=` in provenance) is a failure to rerun, never a result.
- The fable-vs-opus deep probe (2026-08-30, `cold-read-records/2026-08-30-fable-vs-opus-deep-probe/`) found opus 10-vs-1 on unique-and-real findings against fable-5. Fable-5.1 is the retest the user asked for; the prior is against it. Fable showed one transient API-safeguards failure; the rerun-on-absent-record loop covers it.
- No scorer's rankings are trusted until a hand-count sample matches it. The corrected scorer is `tools/walk-reviewer-model-trial-tables.py` and `tools/criterion-and-overlap.py` in the 08-29 record directory.

## Cells to run

| Cell | Model | Effort | Why it is in |
| --- | --- | --- | --- |
| opus-high | claude-opus-5 | high | the incumbent slow-tier deep seat |
| opus-max | claude-opus-5 | max | the user: "when we are looking for defects we should certainly try max" |
| fable-max | claude-fable-5-1 | max | the user's retest; as a hunter, never as a restater |
| sol-xhigh | gpt-5.6-sol | xhigh | incumbent; found the one mechanism-killing defect alone today |
| sol-max | gpt-5.6-sol | max | max on the codex side, if the CLI accepts it — the cell's `--effort` choices include max; verify on a smoke run first |
| luna-xhigh | gpt-5.6-luna | xhigh | incumbent; erratic (1 to 15 unique per round) but real |
| terra-low | gpt-5.6-terra | low | the ruled fast-tier reviewer, run here on the defect-hunt prompt so the fastest tier has a candidate measured on the same task |

Not run: sonnet (ruled cut, confirmed today), haiku (ruled retired), gemini (ruled benched, confirmed today). Effort levels other than the above are not re-swept; the user ruled that most were tried already.

All cells run the defect-hunt prompt, `.claude/skills/cold-read/prompts/defect-hunt.md`, byte-identical, via the project's cell scripts with `--model` and `--effort` overrides. Two runs each. Cells write files, so a runtime without file tools is not a candidate here.

## Targets

Four, frozen by copy and hash per METHOD.md §2:

1. **pairG** — ghi-write SKILL.md at `c6fb95f` (728 words). Ground truth: the user's 15 labelled one-fix commits to HEAD.
2. **fhspec** — fast-handoff-design.md at `c8652c9` (4,673 words). Ground truth: the final at `8c9b357`; carry its recorded contamination note.
3. **workingmodel** — fleet-git-worktree-working-model.md at `c41eb80` (7,150 words). Ground truth: the final at `8afc20a`, the user's strongest language span.
4. **238-round-1** — the topic-branch script design as first cold-read, at `~/agents/reboot-test`'s scratch copy `design-round1.md` (the seat can supply it; it is also reconstructible from that seat's transcript). Ground truth: the adjudicated cluster list from the round-1 dedup (49 clusters), with truth per cluster settled by measurement where the claim was about git and by the author's fix pass otherwise.

Targets 1–3 are the ruled standard subjects. Target 4 is the one document with a per-finding adjudication already done and a mechanism-class defect known to be present (the `--ff-only` claim), so recall of that specific defect is reported by name.

## Scoring

Per cell, per target, per run:

- **True positives**: findings matching a ground-truth defect. For targets 1–3 a defect is "what the user's hand review changed" — a finding is true if the final's diff addresses it. For target 4 it is a cluster adjudicated true.
- **False positives**: findings that name no defect, or a defect the ground truth contradicts. Adjudicated by a fresh agent with the target and ground truth, never by the reviewing cell, never by the campaign runner from memory.
- **Recall** = TP / ground-truth defects. **Precision** = TP / findings.
- **Wall seconds** per cell at recorded concurrency; **defects per minute** = TP / (seconds/60).
- Union coverage for every pair and triple of cells, as today's dedup did, so the tiers are chosen as sets, not as ranked singles.

Report per METHOD.md §11: updated as results land; fields the runtime does not report are omitted; corrections announced in place.

## What the report must answer

1. For each tier, the smallest cell set meeting its threshold on all four targets, with the per-target recall that set achieves and its wall time. If no set meets a threshold, say so and give the best achievable.
2. Whether opus-max beats opus-high, and whether fable-max beats either — on unique-and-real findings, with the 2x run-noise caveat applied.
3. Whether the faster tier is distinct from its neighbours or collapses.
4. The false-positive rate per cell, since the user's criterion names it.

## How the numbers and the ruling fit together (user, 2026-09-03)

METHOD.md §1 rules that product quality, not review-side metrics, decides a configuration. The user restated it for this campaign: "Product quality is ultimately the goal … the assigned agent should review the results of the top combos, that may be more meaningful than any numbers or percentages." So recall, precision, and defects-per-minute are the SHORTLIST, not the verdict. For each tier, take the two or three cell sets the numbers rank highest and read their combined findings against the target as a reviewer would — do the findings, taken together, tell an author what is actually wrong with the document, and would fixing them make it better? Report that reading in prose beside the tables, and let it break ties or overrule a number when the number is measuring the wrong thing. Where the campaign can afford it, run the author-rewrite loop from METHOD.md §9 on one target for the top set of the full tier and judge the product; if it cannot, say so rather than implying it was done.

## One thing to say to the user before the first cell runs

Budget: 7 cells × 4 targets × 2 runs = 56 cell-runs, plus adjudication agents and the qualitative read. At today's medians and a held concurrency of four, roughly five to eight hours of wall time.
