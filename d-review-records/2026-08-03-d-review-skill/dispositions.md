# Triage dispositions — d-review skill draft, eight-cell run 2026-08-03/04

Target: `.claude/skills/d-review/SKILL.md` (pre-landing draft). Cells: {restate, defect-hunt} × {good, floor} × {Claude, Codex} — raw counts 52/21/60/58 hunts plus two restatement pairs; merged to 110 distinct (see `merged-findings.md`, cell-attributed).

Author triage with the boss (walked 2026-08-03/04): roughly 45 findings accepted and folded by rewrite; the rest declined as out-of-context severity inflation, false precision demanded of deliberate judgment calls, renames of established vocabulary, or misreads.

Boss rulings issued during the findings walk (each superseding the reviewers' proposed mitigation where they differ):

- A finding explains — what is wrong, when it does harm, why — and never prescribes; "mitigation" removed from the finding format.
- Cells emit no severity or importance: out-of-context ratings anchor later readers; the invoker assigns all severity at synthesis, with context.
- Lens 3 shrunk to the honesty question (how is each rule backed, stated truthfully); evaluating code-versus-prompt choices is out of review scope unless that choice is the document's own subject.
- Step 4 shrunk to spot-check-the-cheap, label-the-rest, load-bearing claims only; blanket verification is overreach.
- No partial reviews: every cell reads the whole file, at every scale; files stay small and atomic so that stays practical.
- No reviewer-count scale rule: the full grid runs until per-cell value analysis (this records directory's purpose) says otherwise.
- Tier-to-model picks are operator-set pinned values; agents never derive them from their own stale model knowledge.

Sibling run, same dates: the walk-me-through skill review (five cells, 109 raw, ~35 distinct, 28 accepted) ran before this records home existed; its raw legs live only in machine-local session transcripts (new-vp session bba1b075) and its outcome summary in that skill's landing commit (nedschorus 1b7bb4c).

new-vp session bba1b075
