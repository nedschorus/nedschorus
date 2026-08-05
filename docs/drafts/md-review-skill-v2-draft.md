# DRAFT — md-review skill v2 (not live; lands at `.claude/skills/md-review/SKILL.md`, replacing `.claude/skills/d-review/`)

Draft under boss walk, one section per item. Every disposition feeding this draft: `d-review-records/2026-08-04-d-review-skill-self-review/dispositions.md`. Marks land at each section as the walk rules on it.

## Walk order
1. When to use — *presenting*
2. What to do
3. How to do it
4. Assembly: frontmatter + the whole file verbatim (the instruction-class before/after view)

---

## When to use

Run md-review when an MD file is about to land on main — a new file or a change to an existing one — or when the boss names a file and asks for a review.

Not for code correctness, and not for checking an implementation against its design: that is a future code-review skill's lane, not yet built or filed.

## What to do

1. Launch the review grid against the file. The grid is eight cells: two check types — a restatement pass (the reader says what each sentence means) and a defect-hunt pass (the reader flags clarity and coherence defects) — at two capability tiers, on both runtimes.
2. Read each cell's report as it arrives. Triage as you go, but keep every judgment provisional until all eight cells are in — a later cell often states the same defect more sharply.
3. When all cells are in, assign each finding's severity: HIGH — following the words does the wrong thing and the wrongness costs something real; MED — competent readers diverge; LOW — friction, likely recovered.
4. Walk the dispositions with the boss, one decision at a time. He rules each; an accepted change to an instruction-class file lands only through its class path: verbatim before and after, his approval, then the landing.
5. Save the record: every cell's raw output and the dispositions file, each provenance-stamped, in a dated directory under `md-review-records/`.

## How to do it

- Launch the grid with `scripts/md-review-grid.py --target <path>`. The script creates the dated record directory, runs the reference-integrity pre-pass, launches every cell on both runtimes, and writes each cell's stamped output into the record. *(TO BE BUILT — until it lands, launch cells singly: `scripts/md-review-codex-cell.py` for the Codex leg [EXISTS, pre-rename `d-review-codex-cell.py`]; `scripts/md-review-claude-cell.py` for the Claude leg [TO BE BUILT].)*
- The cell prompts live in the skill's `prompts/` directory — the single prompt source for every cell on both runtimes; the launcher scripts read them and substitute the target path.
- Tier-to-model and reasoning-effort pins sit at the top of the cell launcher scripts. The boss picks them. Never substitute a pick from your own knowledge of models.
- Provenance: the scripts stamp every cell output with runtime, exact model id, effort, cell, and tier.
- The record directory `md-review-records/` accumulates one dated directory per review, deliberately unbounded: it is the dataset for deciding, later and from evidence, which cells earn their keep.

---

*Section dispositions (walk marks):*
