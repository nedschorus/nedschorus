---
issue: "[The test runner's history of failing test cases says whether each failure was a caught defect or a flaky failure, keeps a retried attempt's output, and names the pull request](https://github.com/nedschorus/nedschorus/issues/2263)"
---

# The test runner's history of failing test cases says whether each failure was a caught defect or a flaky failure, keeps a retried attempt's output, and names the pull request

## What this GHI asks for

Three additions to the history of failing test cases that the test runner, `scripts/run-all-test-suites.py`, appends to `test-case-failure-history.jsonl` in its `--recorded-inputs-directory`, one JSON line per failing case, written by `append_test_case_failure_history`. Each line today holds the time, the suite, the case, the failure's detail, the exit code, the commit, the branch, the checkout and the log paths. The three additions:

1. Whether the failure was a caught defect, which a later test run passed after a code change, or a flaky failure, which a later test run passed on unchanged code. Telling them apart needs the passes of each case recorded across test runs, since the history records only failures.
2. When a test case is retried, the failed attempt's output is kept. The runner has no retry today, so this part waits on a decision to add one.
3. The pull request number of the test run's change. The history records the branch, not the pull request.

This GHI is a placeholder: no design exists yet. The Outcome section of `docs/issues/1374-each-test-suite-on-ned-box-runs-in.md` says each of the three needs its own decision before it is built. The design answers these questions:

- For the first addition: where passes are recorded, in what format and for how long; how the runner, in code rather than an agent's judgment, labels a failure once a later test run passes, for example by comparing a hash of the suite's recorded inputs at the failure and at the pass; where the label is stored, given that the history file is only appended to; and what label a failure holds while no later test run has passed, or when the test case is removed or its branch is dropped.
- For the second: whether the runner gets a retry at all; and if it does, where each attempt's output is kept, such as a log file per attempt named in the history line, rather than the output itself in the history file.
- For the third: how the runner finds the pull request of a branch, such as with `gh pr list --head <branch>`, and what it records when the branch has no pull request, as in a test run before the first push or a daily full test run of main.

## Why

The user decided all three on 2026-10-14, as part of point 4 of the approval-walk ned-box-head-test-runs-in-isolated-test-environments-2026-10-14, recorded in GHI [Each test suite on ned-box runs in its own throwaway test environment, and suites start by free CPU and memory instead of waiting for a machine-wide lock](https://github.com/nedschorus/nedschorus/issues/1374), whose GHI-MD is `docs/issues/1374-each-test-suite-on-ned-box-runs-in.md`. Point 4 reads: "A history of every failing test case, with its pull request, its commit, and whether a code change fixed it (a caught defect) or it passed on rerun (a flaky failure); a retry keeps the failed attempt's output." The build of that GHI recorded the history without these three, and that GHI closes with this GHI carrying them.

A history that cannot tell a caught defect from a flaky failure cannot show which test cases fail for reasons outside the code, such as the failures on a busy machine that GHI [#1830](https://github.com/nedschorus/nedschorus/issues/1830) describes.

## Related

On 2026-10-30, `scripts/ghi-guide-agent-ask.py --include-closed`, asked for a GHI on these three additions, found none. The nearest are on other matters: GHI [#1206](https://github.com/nedschorus/nedschorus/issues/1206), on what the daily full test runs report to the user; GHI [#1830](https://github.com/nedschorus/nedschorus/issues/1830), on test cases timed against a wall-clock limit that fail on a busy machine; and GHI [#2135](https://github.com/nedschorus/nedschorus/issues/2135), on mutation testing.

## Next action

Write the design in this GHI-MD, answering the questions above for each of the three additions. Put each decision to the user, then add the line `kind: design` to the front matter at the top of this GHI-MD, between its `---` lines, and build what he approves.
