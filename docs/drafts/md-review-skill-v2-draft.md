---
name: md-review
description: Review an MD file of lasting value before it lands on main — a skill, CLAUDE.md, AGENTS.md, a wiki page, a completed design — so future agents can clearly understand, use, and build on it. Typically the final step before pushing; drafts still in progress are not ready for it. Use when the boss types "md-review <file>" or when a lasting-value MD you are finishing is ready to land.
---

# md-review

## When to use

Run md-review on MD files so that future agents can clearly understand them (wiki files), use them properly (skills), encode them (designs), or otherwise incorporate them (CLAUDE.md, AGENTS.md). The md-review is typically the final step before pushing MD files of lasting value to main. Drafts in progress, and plans under development, are not ready to be md-reviewed.

## What to do

1. Run the grid script against the file: `scripts/md-review-grid.py --target <path>`. It launches all eight reviews, saves every review artifact to the record directory, and its output tells you what to do next.
2. Read each md-review report as it arrives. Triage as you go, but keep your judgments provisional until all eight reviews are in, as the later reviews may offer more insight than the earlier ones.
3. When you have processed all reviews and formulated a draft response, use the walk-me-through skill to walk through what problems were detected, and what you propose to do about them. Order the walk from items of most importance to least. The walk's rulings are captured in the record's dispositions file.
