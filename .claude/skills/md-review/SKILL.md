---
name: md-review
description: Review an MD file of lasting value before it lands on main — a skill, a wiki page, a completed design — so future agents can clearly understand, use, and build on it. Typically the final step before pushing. Not for drafts still in progress, and not for CLAUDE.md or AGENTS.md — those are validated behaviorally, not by review.
---

# md-review

## When Used

When MD files are finalized so future agents can clearly understand them (wiki files), use them properly (skills), or encode them (designs). The md-review is typically the final step before pushing MD files of lasting value to main. Drafts in progress, and plans under development, are not ready to be md-reviewed. CLAUDE.md and AGENTS.md are never md-review targets: they are extensions of the system prompts, validated behaviorally (canaries, boot tests), not by review.

## What to do

1. Run `scripts/md-review-grid.py --target <path>`. It launches eight reviewers and saves their reviews to the `md-review-records/` directory. The script output tells you what to do next.
2. Read each md-review report as it arrives. Triage as you go, but keep your judgments provisional until all eight reviews are in, as the later reviews may offer more insight than the earlier ones.
3. When you have processed all reviews and formulated a draft response, use the walk-me-through skill to walk through what problems were detected, and what you propose to do about them. Order the walk from items of most importance to least.
