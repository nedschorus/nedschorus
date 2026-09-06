---
status: research recommendations
research-as-of: 2026-09-06
disposition: queued for user review
---

# Anthropic skill-creator: adapt the viewer and evaluation records

**The output viewer is the most concrete reusable external component found in this pass. Treat the benchmark aggregator as a reference requiring adaptation.** This follows the read-for-ideas disposition already recorded in [#23](https://github.com/nedschorus/nedschorus/issues/23).

| Exact upstream location | Useful piece |
| --- | --- |
| [eval-viewer/generate_review.py](https://github.com/anthropics/claude-plugins-official/blob/85cce0381e7860082641b59d961a2b8c368b8b79/plugins/skill-creator/skills/skill-creator/eval-viewer/generate_review.py) — find_runs, build_run, generate_html | Builds an output-review page from run directories; its static-output mode avoids operating a server. |
| [eval-viewer/viewer.html](https://github.com/anthropics/claude-plugins-official/blob/85cce0381e7860082641b59d961a2b8c368b8b79/plugins/skill-creator/skills/skill-creator/eval-viewer/viewer.html) | The viewer template used by generate_html. The Python file alone is insufficient. |
| [references/schemas.md](https://github.com/anthropics/claude-plugins-official/blob/85cce0381e7860082641b59d961a2b8c368b8b79/plugins/skill-creator/skills/skill-creator/references/schemas.md) — grading.json, timing.json, benchmark.json | Concrete file conventions for per-assertion evidence, timing, and comparisons. |
| [scripts/aggregate_benchmark.py](https://github.com/anthropics/claude-plugins-official/blob/85cce0381e7860082641b59d961a2b8c368b8b79/plugins/skill-creator/skills/skill-creator/scripts/aggregate_benchmark.py) — load_run_results, aggregate_results, generate_benchmark | Small, inspectable Python aggregation code; adaptation details below. |
| [agents/comparator.md](https://github.com/anthropics/claude-plugins-official/blob/85cce0381e7860082641b59d961a2b8c368b8b79/plugins/skill-creator/skills/skill-creator/agents/comparator.md) | An A/B output-comparison protocol that hides which skill produced each output. |

The local consumers are [#23](https://github.com/nedschorus/nedschorus/issues/23) and the Cold Read research workflow described in [docs/issues/queue/cold-read-tier-roster-campaign-brief.md](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/docs/issues/queue/cold-read-tier-roster-campaign-brief.md). Current [scripts/cold-read-cell-common.py](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/scripts/cold-read-cell-common.py) already exposes a draft-template override through compose_prompt and records timing/provenance through stamp_provenance. An evaluation adapter can use those production paths rather than inventing different prompt construction for tests.

The smallest trial is a paired comparison of one current template and one candidate on the same frozen inputs, with outputs stored under distinct run identifiers. Keep raw assertion outcomes and evidence, including missing or failed runs. The human reviews the outputs using an existing MD walk first; use the upstream static viewer if repeatedly arranging the same comparison is the costly part. No new model-provider SDK or optimization loop is required for those presentation pieces.

**The aggregator is not suitable unchanged.** A synthetic probe of the pinned source used one graded run in each of two configurations and a second candidate-run directory with no grading file. Each graded record supplied 900 output characters and no token measurement. The result contained two graded runs, recorded three runs per configuration, labeled 900 as tokens, and omitted the ungraded attempt after printing a warning.

These behaviors are visible in load_run_results and generate_benchmark: missing grading files are skipped, output_chars can fill the tokens field, and runs_per_configuration is set to three. NC explicitly treats missing cost data as unknown; its Claude cell does not manufacture a token count. Carry that existing convention forward.

Any adapted aggregation must preserve attempted-run denominators, distinguish an execution failure from a scored failure, derive actual counts, and keep absent token measurements absent. Name baseline and candidate explicitly. [#23](https://github.com/nedschorus/nedschorus/issues/23) also requires raw counts and regression visibility, so an average score cannot be the sole decision.

The comparator's hiding of A/B identity is useful. Its preference for a decisive winner and a rubric generated after reading the outputs does not replace NC's frozen assertions and human decision. Borrow the separation, and retain the NC evaluation contract.

**First proof.** The small fixture described above should produce two scored runs, one ungraded attempt, unknown tokens, and the actual per-configuration counts. Then use a real paired result set to assess whether the viewer saves human effort. If upstream code is copied, retain the source's [Apache-2.0 license](https://github.com/anthropics/claude-plugins-official/blob/85cce0381e7860082641b59d961a2b8c368b8b79/plugins/skill-creator/skills/skill-creator/LICENSE.txt) and make the adaptation traceable.
