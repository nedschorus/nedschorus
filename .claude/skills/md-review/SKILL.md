---
name: md-review
description: Review an MD file of lasting value before it lands on main — a skill, a wiki page, a completed design — so future agents can clearly understand, use, and build on it. Typically the final step before pushing; drafts still in progress are not ready for it.
---

# md-review

## When Used

When MD files are finalized so future agents can clearly understand them (wiki files), use them properly (skills), or encode them (designs). The md-review is typically the final step before pushing MD files of lasting value to main. Drafts in progress, and plans under development, are not ready to be md-reviewed.

## What to do

1. Run `scripts/md-review-grid.py --target <path>` as a background task, and arm a Monitor on its output that emits an event per `saved:`, `FAILED`, `STRAY WRITE:` and `WRITE CHECK DID NOT RUN:` line. The first two are progress: each finished review reaches you the moment it lands, and a failed cell surfaces immediately instead of being discovered at the end. The other two say whether the set can be trusted — `STRAY WRITE:` names a file a reviewer changed outside its own report, which is yours to inspect and revert before triage, and `WRITE CHECK DID NOT RUN:` says that check could not run for a cell at all, which is a failure to look rather than a clean result. It launches eight reviewers and saves their reviews to the `md-review-records/` directory — machine-local working material, gitignored and never committed (user-ruled 2026-08-14). The reviews exist to be triaged; what survives is the change they produce in the reviewed document and the rulings recorded in its governing document. Delete the record directory when the work it served lands, the same disposal the founding plan gives every evidence archive. The script output tells you what to do next.
2. Read each md-review report as it arrives. Triage as you go, but keep your judgments provisional until all eight reviews are in, as the later reviews may offer more insight than the earlier ones.
3. When you have processed all reviews and formulated a draft response, use the walk-me-through skill to walk through what problems were detected, and what you propose to do about them. Order the walk from items of most importance to least.
