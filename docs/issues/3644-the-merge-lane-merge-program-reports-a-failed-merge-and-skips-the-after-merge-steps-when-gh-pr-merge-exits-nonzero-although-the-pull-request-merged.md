---
issue: "[The merge-lane merge program reports a failed merge and skips the after-merge steps when `gh pr merge` exits nonzero although the pull request merged](https://github.com/nedschorus/nedschorus/issues/3644)"
---

# The merge-lane merge program reports a failed merge and skips the after-merge steps when `gh pr merge` exits nonzero although the pull request merged

Filed by a subagent of merge-lane-2 on 2026-11-15, under merge-lane-2's seat-brief section "Findings that outlive a pull request": the defect is reproduced and makes the code behave wrongly when it runs. The reproduction comes first; the cause and the expected behaviour follow it.

## Reproduction

The program is `scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py`, as it was on main when merge-lane-2 merged pull request [3360](https://github.com/nedschorus/nedschorus/pull/3360) on 2026-11-15 at about 02:48Z. Its output is in the log `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/merge-3360.log`, whose first lines are:

```
try 1: mergeStateStatus is UNKNOWN
non-200 OK status code: 502 Bad Gateway body: "<html>\r\n<head><title>502 Bad Gateway</title></head>...nginx..."
gate passed (#3360): approved commit e2e79567d8a18ff5fb410f63090e9ffa78915793 by ned-review-merge at 2026-11-15T02:07:49Z, APPROVED, CLEAN, no new channel activity since 2026-11-15T02:07:49Z
MERGE WITH THIS EXACT COMMAND:
  gh pr merge 3360 --repo nedschorus/nedschorus --merge --delete-branch --match-head-commit e2e79567d8a18ff5fb410f63090e9ffa78915793
...
no open pull request is based on mutation-testing-script-tests-kill-surviving-mutants-of-2026-11-12-topic-branch
merge exit 1
{"mc":"c565bbbc5918514ff216d3dd88ab6d6c83cadfa3","mergedAt":"2026-11-15T02:47:56Z","state":"MERGED"}
```

1. `gh pr merge` exited 1. The only error text in the log is GitHub's `502 Bad Gateway` page, and `gh pr merge` printed it: every other `gh` call in the program, and `merge-gate.sh`, run with their output captured, so `gh pr merge`, which runs with the program's own stdout and stderr, is the only command that can write to the log directly. Its unbuffered stderr reached the log before the program's earlier stdout lines, which is why the 502 line comes second.
2. The program's own read of the pull request, on the next line, shows the pull request had merged: state `MERGED`, merge commit `c565bbbc5918514ff216d3dd88ab6d6c83cadfa3`. That commit is on main as "Merge pull request #3360".
3. The program then exited 1, which its docstring documents as "the gate refused, printed a merge command other than the expected one, or the merge failed", and printed no message saying which. It did not remove the review worktrees `pr3360-head` and `pr3360-merged`, and did not run the after-merge test run on main at the merge commit.
4. A subagent of merge-lane-2 did those steps by hand. The log's lines after the state line (`removed the review worktree ...`, `removal exit 0`, the after-merge test run's `SUMMARY: 38 passed, 0 failed`, `after-merge test exit 0`) are the subagent's runs, appended to the same log, not the program's output. merge-lane-2 reports that the subagent also deleted the branch by hand; the branch `mutation-testing-script-tests-kill-surviving-mutants-of-2026-11-12-topic-branch` no longer exists on GitHub (`gh api repos/nedschorus/nedschorus/branches/<branch>` returns 404).

A caller that trusts the exit code believes a merged pull request is unmerged, and may try to merge it again or report it as failed, while main goes untested at the merge commit.

## Cause

In `main()` of the program, the merge step decides by `gh pr merge`'s exit code alone, although it reads the pull request's state on the very next lines:

```python
    merge = subprocess.run(expected.split(), env=environment, stdin=subprocess.DEVNULL)
    print(f"merge exit {merge.returncode}", flush=True)
    state = run(["gh", "pr", "view", arguments.pull_request, "--repo", REPOSITORY,
                 "--json", "state,mergedAt,mergeCommit",
                 "-q", "{state,mergedAt,mc:.mergeCommit.oid}"], environment)
    print(...)
    if merge.returncode != 0:
        return EXIT_REFUSED
```

The lines up to the `print` came from pull request [1161](https://github.com/nedschorus/nedschorus/pull/1161), commit `4adc5941e`, which ended with `return EXIT_MERGED if merge.returncode == 0 else EXIT_REFUSED`; pull request [2014](https://github.com/nedschorus/nedschorus/pull/2014), commit `b27504ffa`, turned that into the `if merge.returncode != 0: return EXIT_REFUSED` that now skips the review-worktree removal and the after-merge test run. Both were written by the agent-seat ned-box-helper.

`gh pr merge`'s exit code says whether the command saw success, not whether the pull request merged: a GitHub error after the merge was done, such as a 502 on the response, makes it exit nonzero over a merged pull request.

## Expected behaviour

After the merge command, the program decides from the pull request's state it reads, not from the command's exit code, and reports what the step changed. It captures the merge command's stderr, so that it can print that error under the step's name in each case below:

- State `MERGED`: the merge happened, whatever the command's exit code. When the command exited nonzero, the program prints its exit code and error and that the pull request merged anyway. It then checks that the pull request's branch is gone from GitHub, because the command's `--delete-branch` part may not have run, and deletes it when it is still there; a deletion that fails is a step after the merge not done, which the docstring's exit 3 already covers. Then it continues with the review-worktree removal and the after-merge test run as for any merge. When GitHub reports `MERGED` with no merge commit, the after-merge test run already reports that it could not read the merge commit, with exit 3.
- Any other state, `OPEN` or `CLOSED`: the merge did not happen; the program prints so, with the command's exit code and error, and exits 1, as today.
- The state cannot be read: the program prints that the merge's outcome is unknown, with the command's exit code and error and the read's error, and exits with a new exit code, 4, which the docstring adds as "the merge command ran, and whether the pull request merged is unknown". The caller then reads the pull request's state itself before doing anything else.

A test causes each case: the merge command exiting nonzero over a merged pull request, over an open one, and with the state read failing.

## Next action

The agent-seat ned-box-helper, which wrote these lines, changes the merge step in `scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py` and its docstring's exit codes as above, with the tests, in one pull request that merge-lane-2 reviews.
