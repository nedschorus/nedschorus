---
issue: "[The pull request head test run takes its suite sandbox lists from main instead of the merged tree it tests](https://github.com/nedschorus/nedschorus/issues/1660)"
---

# The pull request head test run takes its suite sandbox lists from main instead of the merged tree it tests

## Reproduction: pull request 1577

[Pull request 1577](https://github.com/nedschorus/nedschorus/pull/1577), "Rename the Mac's forced command for ned-box to mac-request-from-ned-box-forced-command.py", renamed the suite `scripts/mac-window-opened-for-ned-box-forced-command-test.py` to `scripts/mac-request-from-ned-box-forced-command-test.py`. That suite is listed in `SUITES_RUN_WITHOUT_ANY_SANDBOX` in `scripts/run-all-test-suites.py`, because it runs the real ssh, which refuses its root-owned config files inside the test sandbox's user namespace. The pull request renamed the suite's entry in that list too.

merge-lane-2's head test run on the merged tree passed 158 of 159 suites. The one failure was the renamed suite, with "Bad owner or permissions on /etc/ssh/ssh_config.d/…". The same merged tree, run with its own `scripts/run-all-test-suites.py`, passed 159 of 159, and that run's report says the renamed suite ran "without any sandbox". merge-lane-2 recorded both runs in its review of pull request 1577. The output of the run with the tree's own runner is kept at `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/pr1577-merged-tree-run-with-its-own-runner-2026-10-17.txt`.

The renamed suite ran inside the sandbox because the head test run's runner was main's, and main's `SUITES_RUN_WITHOUT_ANY_SANDBOX` still named the old path.

## Why it happens

The runner comes from main on purpose, in two places:

- `scripts/merge-lane-pull-request-head-test-run-on-merged-worktree.py` runs `scripts/pull-request-head-test-run.py` from the worktree at main that its option `--review-tools-worktree-at-main` names, "so a pull request cannot pass by changing its runner". It runs it on the merged worktree `wt/pr<n>-merged` under merge-lane-2's worktrees directory.
- `scripts/pull-request-head-test-run.py` runs the `scripts/run-all-test-suites.py` beside itself (`PULL_REQUEST_HEAD_TEST_RUN_RUNNER_BESIDE_THIS_FILE`), with the comment "so a pull request cannot pass itself by modifying its runner", and passes the merged tree as `--checkout`.

`scripts/run-all-test-suites.py` has three suite sandbox lists: `SUITES_RUN_WITHOUT_ANY_SANDBOX`, `SUITES_GIVEN_A_COPY_ON_WRITE_OVERLAY_OF_THE_REPOSITORY_GIT_DIRECTORY` and `SUITES_WHOSE_TEST_SANDBOX_SHARES_THE_MACHINE_NETWORK`. Each is a Python dict that maps a suite's path to the reason that suite runs with less of the sandbox. The root cause is that the runner reads these three dicts from its own file, not from the checkout it tests. They name suites by path, so they describe the checkout's suites, and are wrong whenever the runner's copy and the checkout's copy differ. Any pull request that renames, adds or removes a suite in one of them fails merge-lane-2's head test run the same way, until the change reaches main.

## Why the whole runner must stay main's

The runner decides the verdict: which suites run, how a result is counted, what the SUMMARY line says. If the head test run used the merged tree's runner, a pull request could change that logic and pass itself. So the fix must not take the runner from the merged tree.

## The fix: read only the suite sandbox lists from the checkout under test

On every run, with or without `--checkout`, the runner reads the three dicts from the `scripts/run-all-test-suites.py` of the checkout it tests; without `--checkout` that is the runner's own checkout, so nothing changes there. It parses that file with Python's `ast` module and evaluates only the three top-level assignments with `ast.literal_eval`. It never imports or runs the file, so no code from the pull request runs inside main's runner, and the verdict logic stays main's.

- When the checkout has no `scripts/run-all-test-suites.py`, as in the scratch checkouts tests build, the runner uses its own three dicts.
- The runner refuses to run, with exit 2 and a message naming the file and what it could not read, in each of these cases: the file cannot be read; it is not valid Python; or any one of the three names is missing, is not assigned a literal, or is assigned a literal that is not a dict.
- The run's report, `test-run-report.txt`, has a line beside its sandbox line, `which sandbox each suite runs in, from the lists in <file>`, so the head test run's record shows where the dicts came from. When they are the runner's own, the line adds that the checkout has no `scripts/run-all-test-suites.py`.

The trade-off this accepts: a pull request can now add a suite to `SUITES_RUN_WITHOUT_ANY_SANDBOX` and have merge-lane-2's head test run run it unconfined. That exposure is not new in kind. A pull request can already rewrite the body of a suite main lists as unconfined, and merge-lane-2's run will run the new body unconfined. Both changes are in the diff merge-lane-2 reviews. The project does not harden against deliberate attackers (`CLAUDE.md`), and nothing here weakens the verdict: moving a suite out of the sandbox changes where it runs, not whether its failure counts.

## Not affected

`scripts/run-suite-in-signal-sandbox.py` and `scripts/pull-request-mutation-testing-survivors.py` also read `SUITES_RUN_WITHOUT_ANY_SANDBOX`. Neither has this defect in merge-lane-2's work, because none of merge-lane-2's steps runs them from main on a merged tree. Those steps are the four in `STEPS` of `scripts/merge-lane-pull-request-worktrees-reviewer-brief-codex-review-and-head-tests-run-without-merge.py`. Each of the two programs reads the list from the runner in its own checkout.

## Next action

prime-intellect opens a pull request that changes `scripts/run-all-test-suites.py` as the fix section says. Its tests, in `scripts/run-all-test-suites-signal-sandbox-test.py`, reproduce pull request 1577: a scratch checkout's own `scripts/run-all-test-suites.py` lists a suite under a path the runner's list lacks, and the runner must run that suite without the sandbox. They also cover the fallback when the file is absent and each refusal. merge-lane-2 reviews the pull request. Once it merges, a head test run on a pull request that renames a listed suite reports that suite as run without any sandbox.
