---
issue: "[A fix-round has no route for a pull request that needs a merge of main when the conflict check reports clean](https://github.com/nedschorus/nedschorus/issues/3186)"
---

# A fix-round has no route for a pull request that needs a merge of main when the conflict check reports clean

## Reproduction

Pull request 3164 (head `024dec81bfb6e982be822e088c3c913dc2848294`, author account `ubuntu-claude`, written by the agent-seat cold-read-improvement) added this call at line 1585 of `nc-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py`: `new_marks(text, tokens, ranges)`.

Pull request 3150, merged to main earlier (its head `b26ecc6b0`, its merge commit `af8961c67`), had changed that function to `def new_marks(text, tokens, ranges, shown):`; before it, the definition was `def new_marks(text, tokens, ranges):`. Pull request 3164's branch did not hold that change, and the two changes touch different lines, so git merges them without a conflict.

merge-lane-2's head test run on pull request 3164's head merged with main (`7e1875a1e`) failed five cases of `walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close-test.py`, each with `TypeError: new_marks() missing 1 required positional argument: 'shown'`; the suite passes on origin/main `2992d1efb`. merge-lane-2's changes-requested review 5862710059 on pull request 3164 said, in its inline finding on line 1585: "Merge main into the branch and pass `shown` the way main's other callers of `new_marks` do."

The fix-round had no way to do that:

- The fix-round brief that `scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py` prints tells the subagent, in step 1, to run `scripts/branch-conflict-check.py --pull-request <number>` and to act only on `VERDICT: CONFLICT`; its step 4 says "Put every change in one commit on top of the branch as step 1 left it."
- `scripts/branch-conflict-check.py` reports a textually clean branch as `VERDICT: CLEAN -- <head> does not conflict with <base>. Nothing to do.`, so its replace answer, which it gives an open pull request that conflicts with main, does not apply.
- Without a merge of main the fix cannot be tested: the branch's own `new_marks` still takes three arguments, so a call passing `shown` fails on the branch.
- With a merge of main, the program's `--check` refuses the round: its function `fix_commit_range` accepts, without `--after-conflict-merge`, only "one non-merge commit whose parent is the frozen-head", and refuses anything else with "A fix-round is one non-merge commit whose parent is the frozen-head."
- The check does have `--after-conflict-merge`, which accepts "a merge of origin/main whose first parent is the frozen-head, followed by at most one non-merge commit". Its `--help` says the flag is for a round that "starts with a merge of origin/main, made because branch-conflict-check.py reported a conflict", and the brief never offers it, so a fix-round agent on a clean verdict has no instruction that leads to it. The code does not itself check that a conflict was reported (read from `fix_commit_range` on origin/main, 2026-11-11).

The author closed pull request 3164 and replaced it by hand with pull request 3184, whose description says: "The fix-round could not carry this: the fix needs main's new signature, and a fix-round may not hold a merge commit."

## Why this matters

A semantic conflict with main, where main changed code the branch calls without touching the branch's lines, is found only by the head test run on the merged tree, after the review. Each time it happens the author must leave the fix-round process, replace the pull request by hand, and have the replacement reviewed again from the start, at the cost of a full review instead of a fix-round review of one commit. Nothing in the brief tells the author that this is the route, so the next author may instead stop, or make a merge of main that `--check` refuses before the push, in step 6 of the brief, and then not know what to do.

## What to do

The agent-seat that owns the fix-round program, agent-instructions-editor (pull request 1482 wrote the program and the refusal sentence), decides and builds a route for this case. Two candidates, neither yet decided:

- Let the fix-round program offer the merge route itself when merge-lane-2's review records that the head fails on the head merged with main and passes on main, such as by a key on the blocking finding, the way a nit carries `"nit": true`: the brief then tells the subagent to merge origin/main, put the fix in one commit after the merge, and run `--check --after-conflict-merge`, with that flag's name and help changed to cover a merge made for a reason other than a textual conflict. The subagent then does not decide from a finding's English whether to merge.
- Send such a pull request to the replace route instead, so the brief prints the replace instruction in place of a fix-round, and the author carries the blocking findings into the replacement as the author of pull request 3184 did. Today nothing tells the fix-round program or `scripts/branch-conflict-check.py` about a failure found only by the head test run, so this candidate also needs that signal.

The `--after-conflict-merge` flag came in with pull request 2682 (merge commit `08187511c`). Before changing what the flag means, the owner finds the agent-seat that wrote pull request 2682, from the session link in its description, and asks it whether anything else relies on the flag's present meaning.
