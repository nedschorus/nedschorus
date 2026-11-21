---
issue: "[Tell the author of a pull request to push work held for a fix-round when the pull request merges without one](https://github.com/nedsnodes/nedsnodes/issues/4029)"
---

# Tell the author of a pull request to push work held for a fix-round when the pull request merges without one

An author agent-seat that holds commits unpushed, waiting to push them in a fix-round, loses them from the pull request when merge-lane-2 approves and merges the pull request without asking for that fix-round. Nothing tells the author that the pull request merged and the fix-round it was waiting for will not come, so the held commits either stay unpushed or arrive later in a pull request of their own, after the merged change has run on main without them.

## Why

The held commits are work the author meant to land with the pull request, such as a fix for a defect found after the review was commissioned. CLAUDE.md tells an author not to push small corrections one at a time under a running review, and says "A defect you find yourself goes in the next fix-round, or after the merge in a new pull request." So the author knows what to do once it knows the pull request merged; what is missing is anything that tells it the pull request merged while it held work, and the author, waiting for a fix-round, does not look.

## Evidence

- Pull request [Idle sweep: a sentence whose object is negated is not raised](https://github.com/nedsnodes/nedsnodes/pull/4003) had a review comment at 2026-11-21T02:30:09Z, from the fresh reviewer merge-lane-2 commissions, whose body begins `REQUEST_CHANGES`; merge-lane-2's own account, `ned-review-merge`, then approved it at 2026-11-21T02:32:35Z, and it merged at 2026-11-21T02:33:07Z, with no fix-round. Why merge-lane-2 approved over that comment is not recorded here (unverified); this GHI is about the held work, whatever the reason for the approval.
- The author's judge-prompt fix and GHI 940 rewrite, held for that fix-round, came instead as pull request [Idle-sweep judge raises unbacked holds and promises again; GHI 940 rewrite from its cold-read-full-run](https://github.com/nedsnodes/nedsnodes/pull/4019), opened at 2026-11-21T02:38:14Z. Its description says: "These commits missed PR #4003 because they were held unpushed for a fix-round that never came: the review passed without one, and nothing told the author to push work held for a fix-round once the pull request merged instead."

## What to do next

Design how the author learns, when its pull request merges, that it holds work meant for that pull request. Code can do the part that needs no judgment: when a pull request merges, compare the author's local nc-topic-branch with the merged nc-head-commit, and only when the branch has commits the merged nc-head-commit lacks, send the author a tool-message-to-agent naming those commits and telling it to put them in a new pull request cut from `origin/main`. The design must say how that code finds the author's checkout, and what happens when the author agent-seat is not running. GHI [Pull requests, their reviews and approval-walks held as one state machine over one schema and one store, so code tracks their state and agents are handed only the steps that need judgment](https://github.com/nedsnodes/nedsnodes/issues/2505) holds pull request states in code; read that GHI before building a separate mechanism, since its merged state is a natural place to run this check.
