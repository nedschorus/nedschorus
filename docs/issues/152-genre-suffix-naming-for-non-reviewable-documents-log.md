---
issue: "[Genre-suffix naming for non-reviewable documents (-log, -report, -capture), and mechanical exclusion from the review instruments](https://github.com/nedschorus/nedschorus/issues/152)"
---

# Genre-suffix naming for non-reviewable documents (-log, -report, -capture), and mechanical exclusion from the review instruments

Documents that only report what happened are not reviewable the way work-directing documents are, and today nothing marks which is which. The sanity-check runner's operating rules already state the exclusion in prose — it applies to actionable MDs (designs, specs, skills, plans) and never to records, defined there as documents that only report what happened — but an agent must judge each file to honor it, and judgment is what this project replaces with mechanism wherever it can.

**The naming rule.** The last token of a filename is the standard genre word, so a glob can find it; the earlier tokens are this project's own subjects and actions, so the name documents itself. Three genre words cover the non-reviewable class:

- `-log` — an account that accumulates entries over time (walk dispositions, decision logs).
- `-report` — the point-in-time output of one run (a review's findings, a scorecard).
- `-capture` — an artifact saved off a real run (the payload of a live check-in).

"Record" is rejected as the umbrella: it carries three meanings already (a database row, records management's authoritative account, an architecture decision record), and the files it would cover are not one kind. "Specimen" is rejected for `-capture` because this project already uses it for an example of a kind of thing shown to a reviewer ("a specimen input is listed read-first and marked not-for-review"); a captured payload is not an example of a kind.

**The mechanism.** The review instruments — `scripts/sanity-check-attacks.py` and md-review — refuse a target whose name ends in a genre suffix, and say which rule fired rather than silently doing nothing. A suffix list can miss a genre nobody anticipated; announcing the skip is what makes that visible instead of silent.

**The rename pass.** Four to six committed files are genuinely in this class, among them `docs/cross-project/git-gatekeeper-first-live-check-in-record.md` (a captured payload) and `docs/issues/3-slice-6-review-evidence-not-built.md` (a decision account). Each rename fixes inbound citations first, so nothing points at a dead path.

**Open, for the user:** whether the two gitignored working directories `sanity-check-records/` and `md-review-records/` rename to match, or keep their name as machine-local material that never enters the review path anyway.

This settles a question left open under GHI [Build draft-md: the drafting-stage skill run before md-review (user-ruled 2026-08-22)](https://github.com/nedschorus/nedschorus/issues/142): documents that record decisions keep their ruling stamps as content, because the genre suffix takes them out of the review path entirely — no exception clause is needed inside the drafting rules.

Search receipt: `gh issue list --state all --search "naming convention suffix"` returned nothing; `--search "md-review exclude records"` returned no issue on this subject (2026-08-23).

— filed from session https://claude.ai/code/session_01F9s9L5vPfehGRgrDHoc4Pk (doctrine-queue-drain seat)
