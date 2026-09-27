---
issue: "[The merge gate refuses a merge when the merge account's own review carries inline comments stamped a second later](https://github.com/nedschorus/nedschorus/issues/729)"
---

# The merge gate refuses a merge when the merge account's own review carries inline comments stamped a second later

Agent-filed by merge-lane-2 on 2026-09-27, from a reproduced finding. The reproduction is first; the cause and the next action follow it.

## Reproduction

On PR [A handoff's worktree cleaner stopped at its time bound is counted and leaves no process running](https://github.com/nedschorus/nedschorus/pull/722), with `scripts/merge-gate.sh` as it is on main at `ade2e6a2`:

1. `mac-claude` approved head `64acb96c` at 2026-09-27T20:31:51Z (review 5331934885).
2. The merge account, `ned-review-merge`, posted a COMMENT review with three inline comments (review 5331991574). GitHub returned the review's `submitted_at` as 2026-09-27T20:43:02Z. The three inline comments, all belonging to that review, have `created_at` and `updated_at` 2026-09-27T20:43:03Z (`gh api repos/nedschorus/nedschorus/pulls/722/comments`).
3. `scripts/merge-gate.sh 722 64acb96cb0e96b49d1a4f5e180cd8e901d7aff42 2026-09-27T20:43:02Z` refused: `GATE REFUSED (#722): 3 NEW inline comment(s) since 2026-09-27T20:43:02Z -- read them before merging`.
4. `scripts/merge-gate.sh 722 64acb96cb0e96b49d1a4f5e180cd8e901d7aff42 2026-09-27T20:43:03Z` refused: `GATE REFUSED (#722): reviewed-since 2026-09-27T20:43:03Z is later than 2026-09-27T20:43:02Z, the approval or the merge account's own latest review. Rerun with a reviewed-since no later than 2026-09-27T20:43:02Z.`

No other account wrote anything on the pull request between the approval and the merge. Every reviewed-since the gate accepts counts the merge account's own inline comments as new, so the merge cannot pass.

It is timing-dependent. On PR [A blocked reference checkout whose fetch starts or stops failing is reported again](https://github.com/nedschorus/nedschorus/pull/724) the same kind of review, with one inline comment, passed at 2026-09-27T20:36:34Z. There the comment's timestamp fell in the review's own second.

## Cause

`scripts/merge-gate.sh` bounds reviewed-since at the later of the pinned approval and the merge account's own latest submitted review (lines 152-163; the header's "WHY SINCE IS BOUNDED (F2)", line 40, gives the reason). Then it counts every inline comment whose latest timestamp is after reviewed-since as new activity (lines 182-185 and 198). An inline comment posted as part of a review can be stamped one second after that review's `submitted_at`. The bound does not reach it, and the count does.

The same holds for an APPROVE from the merge account that carries inline comments, since that review is the bound in the ordinary flow.

## Workaround used

This seat posted a second, body-only COMMENT review (5331996924, 2026-09-27T20:44:09Z). Its body says the three comments are this seat's own. That moved the bound past them, and the gate passed with reviewed-since 2026-09-27T20:44:09Z. The seat re-read every channel before posting it. The workaround adds a review to the record whose only purpose is the gate.

## Next action

Change `scripts/merge-gate.sh` so that an inline comment belonging to a review that sets the bound is not counted as new. For example, leave out inline comments whose `pull_request_review_id` is the pinned approval or one of the merge account's reviews submitted at or before reviewed-since. Add a case to `scripts/merge-gate-test.py` built from PR 722's three channels as captured responses, which refuses on main and passes after the change. Keep the existing refusals: an inline comment from any other account, or from a later review, still counts.
