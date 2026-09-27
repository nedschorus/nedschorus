---
issue: "[Reconcile the restater judge's binary critical mark with the defect list's severity weights, at the judge prompt's walk](https://github.com/nedschorus/nedschorus/issues/339)"
---

# Reconcile the restater judge's binary critical mark with the defect list's severity weights, at the judge prompt's walk

The restater judge scores what a restating reviewer caught. A walk ruling of 2026-09-08 (item 8, "fast cold read from start to end") gives it a binary **critical-or-not** mark on each catch, to be validated once against the user's own ghi-write scrub before it affects any score.

Severity weights were adopted the same day, and they overlap it.

## The conflict, precisely

`cold-read-reviewer-test-cases/ghi-write-trio/ghi-write-defect-list-2026-09-07.md` now carries a per-row weight of 1 to 8 in its "Severity weights" section, and `scripts/cold-read-reviewer-score.py` reads those weights out of the list rather than holding a copy.

- **Where a catch maps to a defect-list row,** the row's weight already states how serious it is. The judge's binary mark is redundant, and worse, it is a second severity signal that can disagree with the first.
- **Where a catch maps to no row,** the mark is the only severity signal there is. Dropping it loses information.

So the mark is neither simply redundant nor simply needed, which is why this wants a ruling rather than a default.

## Why nothing has been built

The judge prompt is drafted and **is not on main**. Its home is `.claude/skills/cold-read/prompts/restater-judge.md`, alongside the four prompts that are there (`defect-hunt.md`, `fast-clarify.md`, `restate.md`, `terminology.md`). That directory is operative prose, so the prompt lands only after its own cold read and the user's review.

The reconciliation therefore belongs to the user's walk of that prompt. **Do not edit the prompt ahead of it.**

Two related facts a builder needs:

- The judge runner, `scripts/cold-read-restater-judge-runner.py`, is inert on purpose: `--prompt-file` is required and the prompt is not on main.
- No restater run may use the merged 80/20 composite, which the 2026-09-08 item 8 ruling superseded.

## What ruling would settle it

Either the weight governs wherever a row exists and the mark survives only for unmatched catches, or the mark is dropped entirely and unmatched catches carry no severity, or the two are reconciled into one scale. Each is defensible; the choice is the user's, at the prompt's walk.

Carried as a task on the cold-read-research seat since 2026-09-08 and moved here 2026-09-11, because a task list does not outlive its worktree.

Search receipt: `gh issue list --state all --search "restater judge prompt critical"` returned nothing (2026-09-11).
