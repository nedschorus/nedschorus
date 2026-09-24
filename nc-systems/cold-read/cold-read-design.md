# cold-read tooling design — the encode plan

Status: design for everything the cold read encodes as code. The instrument was called `md-review` while this design was written and was renamed `cold-read` on 2026-08-25; the paths below are the current ones, except that a record directory made before the rename keeps the name it was made under. The roster was eight cells while this design was written and is six today, after the restate pass was dropped (commit [cold-read grid: the default roster drops the restate pass (eight cells to four)](https://github.com/nedschorus/nedschorus/commit/89134fd)) and a terminology pass was added on the good tier of both runtimes (commit [cold-read grid: a second pass, terminology, on the good tier of both runtimes](https://github.com/nedschorus/nedschorus/commit/557c1e0)). Every requirement here traces to a user ruling in [the self-review dispositions](../../md-review-records/2026-08-04-d-review-skill-self-review/dispositions.md) — a pre-rename record, and gitignored like every other, so a fresh checkout reads it with `git show db917b5:md-review-records/2026-08-04-d-review-skill-self-review/dispositions.md`. The skill text this tooling serves is live at `.claude/skills/cold-read/SKILL.md`.

## Components

1. **`nc-systems/cold-read/cold-read-claude-cell.py`** — Claude-runtime cell launcher, twin of the Codex one.
   - Headless `claude -p` invocation; per-run exact pinned model id AND reasoning effort (user-confirmed both are settable headless).
   - Reads the shared template from the skill's `prompts/` directory, substitutes the target path.
   - Read-only tool restriction; working directory = the nedschorus checkout, so Claude and Codex cells see the identical instruction floor.
   - Prints the provenance stamp (runtime, exact model id, effort, cell, tier, target) plus the cell's final message on stdout; progress on stderr.
   - Tier-to-model and effort pins at the top of the script, with the user-picked change-control comment, same as the Codex script.
2. **`nc-systems/cold-read/cold-read-codex-cell.py`**.
3. **`nc-systems/cold-read/cold-read-grid.py`** — the orchestrator; `--target <path>`, no mode argument (one review approach).
   - Creates the dated record directory `cold-read-records/<YYYY-MM-DD>-<target-slug>/` —
     gitignored working material kept on this machine only, deleted once the work it served lands
     (user-ruled 2026-08-14).
   - Runs a reference-integrity pre-pass over the target (cited paths exist; quoted commands/files resolve) and writes its result into the record.
   - Launches cells in parallel across both runtimes and both tiers, each cell's stamped output written into the record as `<runtime>-<pass>-<tier>.md` the moment it completes — the reviewing agent reads them as they land.
   - Completion output teaches the next steps (read reports as ready, keep triage provisional until all are in, walk dispositions with the user, dispositions file location) — the skill text does not repeat what this output says.
   - Failure output teaches recovery (a Codex 401 prints "run codex login"; one cell's failure does not stop the others; missing cells are noted in the record).
4. **Templates** (`prompts/`): `defect-hunt.md` gains the coherence checks: gaps in a mechanism the file itself defines; an accumulating store the file defines with no stated bound; a term the file defines that duplicates or conflicts with the checkout's CLAUDE.md/AGENTS.md (the floor-drift guard). Every added check triggers on presence, never demands presence.
   - Micro-tests before any template lands: a planted-conflict file must be reported; a benign MD with no plans or mechanisms must produce zero demanded-section findings.
5. CUT (user-ruled 2026-08-05): no records README — no reader needs it; the store is self-describing.

## Prompts walk

All three prompt sets user-ruled: set one (restate) — two cuts plus the frontmatter rule (prose fields restated, data fields skipped), micro-tested twice; set two (defect-hunt) — user-redrafted stem and classes (a)–(e), evidence-restored (f)–(i) with the trigger-on-presence guard, no-severities and document-order output kept, both micro-tests passed (planted defects all caught; benign file drew zero demanded-section findings); set three (primary-agent instructions) — approved verbatim.

## Future-checks direction (user, 2026-08-06)

Writing rules the project adopts for agent instruction files (the step-2 CLAUDE.md inputs among them) are candidate hunt checks: when we do not want agents instructed in a certain way, the cold read looks for those instructions in the MD files it reviews. Recorded as direction for the records-driven template evolution; no template change commissioned now.

**Pinned to what landed:** commit [daf5fc6](https://github.com/nedschorus/nedschorus/commit/daf5fc62b63b45c73fac70ec4ba785fe2c621076) on 2026-09-22 — the cold read's code as merged by PR [Codex runners: move model pins from GPT-5.6 to GPT-6 Sol and Luna](https://github.com/nedschorus/nedschorus/pull/661), then in `scripts/`; it moved whole into `nc-systems/cold-read/` on 2026-09-23.

**Pinned to what landed:** commit [1b46481](https://github.com/nedschorus/nedschorus/commit/1b464810cde0f6707a730719433e8a2fc4b4f400) on 2026-09-23 — the cold read's code in `nc-systems/cold-read/` after PR [The cold read moves whole into nc-systems/cold-read/](https://github.com/nedschorus/nedschorus/pull/686) and PR [The defect-hunt prompt pins the shape of a finding](https://github.com/nedschorus/nedschorus/pull/685).
