---
name: cold-read
description: Give a document of lasting value — a skill, a wiki page, a completed design — a cold read before it lands on main: zero-context reviewers report what each sentence made them think it meant, and what defects they found. Typically the final step before pushing; drafts still in progress are not ready for one.
---

# cold-read

## When Used

When a document of lasting value is finished, so future agents can clearly understand it (wiki files), use it properly (skills), or encode it (designs). A cold read is typically the final step before pushing such a document to main. Drafts in progress, and plans under development, are not ready for one.

## What to do

1. Run `scripts/cold-read-grid.py --target <path>` as a background task, and arm a Monitor on its output that emits an event per `saved:`, `FAILED`, `STRAY WRITE:`, `FELL BACK:`, `RECOVERED:` and `TARGET CHANGED DURING RUN:` line. Each line is addressed to you: `saved:` means a finished review has landed and can be read now; `FAILED` means a cell produced no review, surfacing immediately instead of being discovered at the end; `STRAY WRITE:` means a reviewer changed a file that was not its own report, which is ordinary cleanup for you rather than something to escalate; `FELL BACK:` means a cell's first-choice model did not produce a report and names the model that actually wrote the one you are about to read; `RECOVERED:` means the model wrote its report to a path one character from the one it was given and the cell moved it into place — the review is intact, and the line is there so a model that mistyped the directory it was given is not invisible to you; `TARGET CHANGED DURING RUN:` means the document was edited while the reviewers read it, so every report in the set describes text that no longer exists — the grid marks each report and exits 3, and the right response is to settle the document and run the grid again rather than to triage a set that reviews the wrong file. It launches eight reviewers and saves their reviews to the `cold-read-records/` directory — machine-local working material, gitignored and never committed (user-ruled 2026-08-14). The reviews exist to be triaged; what survives is the change they produce in the reviewed document and the rulings recorded in its governing document. Delete the record directory when the work it served lands, the same disposal the founding plan gives every evidence archive. The script output tells you what to do next.
2. Read each report as it arrives. Triage as you go, but keep your judgments provisional until all eight reviews are in, as the later reviews may offer more insight than the earlier ones.
3. When you have processed all reviews and formulated a draft response, use the walk-me-through skill to walk through what problems were detected, and what you propose to do about them. Order the walk from items of most importance to least.
