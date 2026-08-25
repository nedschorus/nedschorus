# cold-read tooling design — the encode plan (draft, under active work)

Status: design for everything the cold read encodes as code; feeds the build; itself a draft in progress (not yet ready for a cold read). The instrument was called `md-review` while this design was written and was renamed `cold-read` on 2026-08-25; the paths below are the current ones. Every requirement here traces to a boss ruling in [the self-review dispositions](../../cold-read-records/2026-08-04-d-review-skill-self-review/dispositions.md). The skill text this tooling serves is live at `.claude/skills/cold-read/SKILL.md` (landed 2026-08-05; the draft file was deleted at landing, recoverable from git); this file is the plan that built it.

## Components

1. **`scripts/cold-read-claude-cell.py`** — Claude-runtime cell launcher, twin of the Codex one.
   - Headless `claude -p` invocation; per-run exact pinned model id AND reasoning effort (boss-confirmed both are settable headless; smoke-test both in background execution mode before relying on them).
   - Reads the shared template from the skill's `prompts/` directory, substitutes the target path.
   - Read-only tool restriction; working directory = the nedschorus checkout, so Claude and Codex cells see the identical instruction floor.
   - Prints the provenance stamp (runtime, exact model id, effort, cell, tier, target) plus the cell's final message on stdout; progress on stderr.
   - Tier-to-model and effort pins at the top of the script, with the boss-picked change-control comment, same as the Codex script.
2. **`scripts/cold-read-codex-cell.py`** — rename of `scripts/d-review-codex-cell.py`; content otherwise unchanged.
3. **`scripts/cold-read-grid.py`** — the orchestrator; `--target <path>`, no mode argument (one review approach).
   - Creates the dated record directory `cold-read-records/<YYYY-MM-DD>-<target-slug>/` —
     gitignored machine-local working material, deleted once the work it served lands
     (user-ruled 2026-08-14).
   - Runs a reference-integrity pre-pass over the target (cited paths exist; quoted commands/files resolve) and writes its result into the record; grows into the nedschorus#42 checker when that is built.
   - Launches all eight cells in parallel across both runtimes and both tiers, each cell's stamped output written into the record as `<runtime>-<pass>-<tier>.md` the moment it completes — the reviewing agent reads them as they land.
   - Completion output teaches the next steps (read reports as ready, keep triage provisional until all are in, walk dispositions with the boss, dispositions file location) — the skill text does not repeat what this output says.
   - Failure output teaches recovery (a Codex 401 prints "run codex login"; one cell's failure does not stop the others; missing cells are noted in the record).
4. **Templates** (`prompts/`): `restate.md` unchanged. `defect-hunt.md` gains the coherence checks: gaps in a mechanism the file itself defines; an accumulating store the file defines with no stated bound; a term the file defines that duplicates or conflicts with the checkout's CLAUDE.md/AGENTS.md (the floor-drift guard). Every added check triggers on presence, never demands presence.
   - OPEN: coherence folded into the hunt template (grid stays eight cells — recommended) versus a separate coherence template (twelve cells); the records data decides a split later.
   - Micro-tests before any template lands: a planted-conflict file must be reported; a benign MD with no plans or mechanisms must produce zero demanded-section findings.
5. CUT (boss-ruled 2026-08-05): no records README — no reader needs it; the store is self-describing.
6. **Renames, one commit:** `.claude/skills/d-review/` → `.claude/skills/md-review/` (text replaced by v2 at landing); `d-review-records/` → `md-review-records/`. (Both were renamed a second time on 2026-08-25, when the instrument became `cold-read`: `.claude/skills/cold-read/` and `cold-read-records/`.)

## Build order

1. `cold-read-claude-cell.py` (smoke-test headless model + effort settings first).
2. `cold-read-grid.py`.
3. Rename sweep.
4. Template edits + micro-tests (template wording walked with the boss — instruction class).
5. ~~Records README~~ (CUT — no reader needs it).
6. Skill v2 landing (the bare file, walked — instruction class).

## Prompts walk (complete 2026-08-05)

All three prompt sets boss-ruled and landed: set one (restate) — two cuts plus the frontmatter rule (prose fields restated, data fields skipped), micro-tested twice; set two (defect-hunt) — boss-redrafted stem and classes (a)–(e), evidence-restored (f)–(i) with the trigger-on-presence guard, no-severities and document-order output kept, both micro-tests passed (planted defects all caught; benign file drew zero demanded-section findings); set three (primary-agent instructions) — approved verbatim, lives in this design until the grid script encodes it (the script is its home; class (h)'s micro-test deferred to the CLAUDE.md consolidation landing).

Approved set-three text the grid script must print — at launch: "Launched eight reviewers against <target>. Reports appear in <record-directory> as each completes — read each as it arrives." Per report: "saved: <record-directory>/<runtime>-<pass>-<tier>.md". At completion: "All eight reviews are complete, in <record-directory>, one file per reviewer. / Read every report in full. The restate reports show what a reader took each sentence to mean — compare them against what you intended; a confident misreading is a defect in the file, not in the reader. The defect-hunt reports flag defects with each reviewer's own confidence; expect heavy overlap — the same defect found independently by several reviewers is one defect. / Keep your judgments provisional until you have read all eight, as later reports may offer more insight than earlier ones. Then formulate your draft response: which problems are real, and what you propose to do about each. Walk that with the boss using the walk-me-through skill, ordered from most important to least. The walk's anchor is <record-directory>/dispositions.md."

## Future-checks direction (boss, 2026-08-06)

Writing rules the project adopts for agent instruction files (the step-2 CLAUDE.md inputs among them) are candidate hunt checks: when we do not want agents instructed in a certain way, the cold read looks for those instructions in the MD files it reviews. Recorded as direction for the records-driven template evolution; no template change commissioned now.

## Walk state for the skill draft

WALK COMPLETE 2026-08-05: all four items processed; the bare skill file APPROVED verbatim by the boss (nedschorus 74ad5b9). LANDED 2026-08-05, boss-ordered ("make it so"): both cell launchers and the grid orchestrator built; rename sweep executed (records directory, Codex launcher, skill directory); the approved text is live at `.claude/skills/cold-read/SKILL.md`. Remaining from this design: NONE. Class (h)'s deferred micro-test RAN 2026-08-06 at the CLAUDE.md landing and PASSED — a planted file contradicting two floor definitions (durable artifacts; legacy-system permissions) drew class-(h) findings quoting the checkout's CLAUDE.md verbatim against both, at "sure" confidence, with the write- and execute-conflicts separated. The records README was CUT at the boss's challenge — no reader needs it. This design is fully built.
