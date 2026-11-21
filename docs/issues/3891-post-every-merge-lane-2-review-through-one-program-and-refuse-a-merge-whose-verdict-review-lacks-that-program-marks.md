---
issue: "[Post every merge-lane-2 review through one program, and refuse a merge whose verdict review lacks that program's marks](https://github.com/nedschorus/nedschorus/issues/3891)"
---

# Post every merge-lane-2 review through one program, and refuse a merge whose verdict review lacks that program's marks

merge-lane-2 posts each review it writes, as the GitHub account `ned-review-merge`, in one of two ways: through `scripts/merge-lane-pull-request-reviewer-review-post-and-read-back.py`, the posting program, or by hand with `gh pr review`. Only the posting program writes the marks that other programs read findings by. This GHI asks for two changes, so that every merge-lane-2 review goes through the posting program and a verdict posted any other way is caught before the merge.

## Why

The posting program, run with `--github-account ned-review-merge`, writes these marks into a review, as its docstring says:

- each inline comment opens with a mark for its finding category: `**Blocks** ` for a must-fix-now finding, `**fix-in-maintenance, nit** ` for a nit, and the category in bold, such as `**fix-next** `, for any other;
- the body opens with the verdict line, `APPROVE` or `REQUEST_CHANGES`, and, when N comments are must-fix-now, the line `**Blocking: N**` after it and a blank line.

The fix-round program, `scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py`, finds blocking findings by these marks, with its `BLOCKING_MARKER_PATTERN` and `BLOCKING_COUNT_PATTERN`; `scripts/pull-request-follow-up-request-after-merge-finding-answers-and-next-step.py` finds non-blocking findings by the category marks. A review posted by hand carries none of them. When such a review requests changes, the fix-round program refuses, saying that none of the review's inline comments starts with the blocking mark, and tells the author to ask merge-lane-2 which findings block. merge-lane-2 then has to post its blocking findings a second time.

This has happened twice:

- On [PR 3881](https://github.com/nedschorus/nedschorus/pull/3881), merge-lane-2's hand-typed review [5949985134](https://github.com/nedschorus/nedschorus/pull/3881#pullrequestreview-5949985134) requested changes with no marked inline comment, and its review [5949991380](https://github.com/nedschorus/nedschorus/pull/3881#pullrequestreview-5949991380), less than a minute later, reposted the blocking finding as a comment opening with `**Blocks**`.
- On [PR 3602](https://github.com/nedschorus/nedschorus/pull/3602), the hand-typed review [5945142106](https://github.com/nedschorus/nedschorus/pull/3602#pullrequestreview-5945142106) was followed by [5945151474](https://github.com/nedschorus/nedschorus/pull/3602#pullrequestreview-5945151474), which reposted its blocking finding the same way.

Since 2026-11-04, merge-lane-2 has posted 505 reviews with a hand-typed `gh pr review`, 13 of them requesting changes, and 25 with the posting program, by the count recorded in item 91.2 of the approval-walk `nedlern@ned-box:/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-pr-2760-pr-2695-and-emergency-stop-merges-approval-walk-2026-11-08.md`, a file in merge-lane-2's agent-home that git does not track (unverified).

On 2026-11-19 the user approved, as item 91.2 of that approval-walk, that merge-lane-2 posts every review with a verdict, approve or request changes, through the posting program, and a review with no verdict with a hand-typed `gh pr review --comment`. That rule leaves merge-lane-2 to choose the method by hand for each review, and nothing reports a wrong choice before the author's fix-round refuses. As item 93 of the same approval-walk, the user approved filing this GHI, which asks for both changes below.

## What to build

1. **A check after the act.** `scripts/merge-gate.sh` refuses to merge when `ned-review-merge`'s latest review whose state is `APPROVED` or `CHANGES_REQUESTED` lacks the marks the posting program writes, whichever way it was posted: `gh pr review`, `gh api`, or any other. The check goes in the gate rather than in the merge program, `scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py`, because the merge program runs the gate and the gate is also run alone. The refusal names the review and says to post it again through the posting program. Because the check reads the review GitHub holds, it catches every way of posting, which a guard on one command's spelling would not.
   - The marks are those the posting program writes for the review's verdict: for `CHANGES_REQUESTED`, a body opening with `REQUEST_CHANGES`, a blank line and `**Blocking: N**`, and N inline comments, or comments moved into the body, opening with `**Blocks**`; for `APPROVED`, a body opening with `APPROVE`. The check reads them with the fix-round program's constants, `BLOCKING_MARKER_PATTERN` and `BLOCKING_COUNT_PATTERN`, not with a second copy of them.
   - A hand-typed approval whose body happens to open with `APPROVE` passes this check. When the builder judges that worth catching, the posting program can also write a fixed signature into every body it posts, and the check can require it.
   - When `ned-review-merge` has no review in either state, such as on a pull request it opened, the check passes.
   - In practice the check catches a hand-posted approval, whose non-blocking findings `scripts/pull-request-follow-up-request-after-merge-finding-answers-and-next-step.py` would then miss. A hand-posted request for changes is the latest verdict review only while the pull request cannot merge anyway, and the fix-round program's refusal already reports it, as on PRs 3881 and 3602; change 2 is what keeps it from being posted by hand.
2. **One command for every merge-lane-2 review.** The posting program also posts a review with no verdict, a `COMMENT` review, and finds for itself when one is needed, so merge-lane-2 runs the same command for every review it posts. There are two such cases:
   - merge-lane-2's review of a pull request that `ned-review-merge` opened. GitHub refuses an approving review, and a review requesting changes, from a pull request's author, and today the posting program, run as `ned-review-merge`, always posts with the verdict as its event, so that post fails. The program already reads the pull request's author when it chooses the event for the `mac-claude` account, and can choose `COMMENT` the same way here, keeping the verdict line and every mark in the body. The fix-round program reads only a `CHANGES_REQUESTED` review as asking for a fix-round, so on such a pull request it must also read a `COMMENT` review by `ned-review-merge` whose body opens with `REQUEST_CHANGES` as one.
   - the review `scripts/merge-gate.sh` asks for when the pull request has activity after merge-lane-2's latest review: its refusal says to "post a review as the merge account saying what you read" and to pass that review's `submitted_at` to the gate. The review file for this case carries no verdict, only the body merge-lane-2 writes, saying what it read. The program finds the case by running the gate's own test for activity after `ned-review-merge`'s latest review, and refuses a review file without a verdict when that test finds none.
Each change carries its tests: the merge gate refusing a verdict review without the marks and passing one the posting program wrote; the posting program choosing `COMMENT` in each of the two cases above, and refusing a review file without a verdict when the gate's test finds no activity; and the fix-round program briefing a round from a `COMMENT` review that opens with `REQUEST_CHANGES` on a pull request `ned-review-merge` opened.

## Related

- GHI [Programs for sixteen merge-lane-2 seat-brief steps that need no judgment](https://github.com/nedschorus/nedschorus/issues/2608), whose item 1 asks for a program that posts merge-lane-2's review and writes its fixed closing sentences. The posting program now exists; this GHI covers making it the only way merge-lane-2 posts, and the gate's check that it was.

## Next action

The agent-seat reboot-test, which wrote the posting program, builds both changes, in one pull request or two. Until they land, merge-lane-2 follows the rule of item 91.2.
