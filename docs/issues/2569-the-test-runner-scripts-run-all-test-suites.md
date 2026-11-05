---
issue: "[The test runner `scripts/run-all-test-suites.py` reruns suites whose recorded inputs did not change, because it keeps one recording per suite for every branch and selects every suite that runs a content-reading git command on the checkout](https://github.com/nedschorus/nedschorus/issues/2569)"
---

# The test runner `scripts/run-all-test-suites.py` reruns suites whose recorded inputs did not change, because it keeps one recording per suite for every branch and selects every suite that runs a content-reading git command on the checkout

## What this GHI asks for

A design, then a build, that stops the test runner, `scripts/run-all-test-suites.py`, from running a suite in a selective test run when nothing the suite reads has changed. Two of the runner's selection reasons pick suites that way today, and together they took 39% of the run-seconds of merge-lane-2's head test runs from 2026-11-01 to 2026-11-04.

### Reason 1: one recording per suite, shared by every branch

The runner records the files each suite reads while it runs, with two recorders, a Python audit hook and, on ned-box, strace, and keeps that recording under `--recorded-inputs-directory`, keyed by the repository's root commit, one file per suite, shared by every clone and worktree on the machine (the runner's docstring, section RECORDED INPUTS, and `recordings_directory_for`). Every run replaces the recordings of the suites it ran. So when a run on branch X records a suite, a run on branch Y finds a recording whose file contents are X's. The runner then cannot tell what the suite reads on Y, and selects it with the reason "its recording read another copy of <file> than the checkout holds, so what it reads here is unknown" (`selection_reason`).

Example: merge-lane-2's head test run of one pull request records `nc-systems/skills/explain/tests/explain-reply-cold-read-fast-read-test.py` while that pull request's copy of a cold-read file differs from main. The next head test run, of a pull request that touches nothing that suite reads, selects it anyway. That suite was selected this way 77 times in the three days.

Measured: this reason selected 24% of head-run seconds, up to 119,000 suite-seconds over 2026-11-01 to 2026-11-04.

The change to design: keep several recordings per suite, each a file of its own, check them one by one, and do not select a suite when any one of its recordings matches the checkout in everything it saw (the files it read, the paths it looked for and the directories it listed) and none of that changed since COMMIT, the commit the selective test run compares against (`--only-suites-whose-recorded-inputs-changed-since`).

### Reason 2: a suite that runs a content-reading git command on the checkout is selected by every change

When a suite runs a git command on the checkout that reads file contents, such as `git status`, `git diff` or `git clone` of the checkout, the runner selects it whenever any file differs, because git reads committed content from the object store, where neither recorder sees a working file (`selection_reason`, the reason "it runs git … on the checkout, which reads files no recorder here saw").

Measured: 749 suite-runs and 75,745 suite-seconds, 15% of head-run seconds, over the same three days. Most came from seven suites, among them `nc-systems/general-tools/tests/bash-guards-verdict-changes-between-two-git-refs-on-transcript-recorded-commands-check-test.py`, whose median run is 430 seconds; it ran in all 230 head test runs and used 17.5% of all suite CPU.

The options to weigh in the design, which can be combined:
1. Each such suite runs git on a fixture repository it builds, instead of on the checkout, so it no longer runs git on the checkout and the runner selects it by its recorded files alone. This helps only the suites rewritten, and only where the fixture still holds what the test checks; a suite that needs the real checkout stays selected by every change.
2. The recorder learns which paths a git command can read from its arguments, such as `git show <ref>:<path>` or a pathspec after `--`, and treats a whole-tree command such as `git status` as reading every tracked file, so a suite running `git status` stays selected by every change; it does not help a suite that clones the checkout, such as the bash-guards suite above, which needs option 1.

## Why

The user ruled on 2026-09-30 that a suite is rerun only when a file it reads has changed: test result caching keyed on inputs recorded while the suite runs (approval-walk open-questions-concerns-and-recommendations-2026-09-30, item 5, "y both", quoted in the runner's docstring, section RECORDED INPUTS). Both reasons above rerun suites whose files did not change. On 2026-11-04 the user asked "Build what we need to test faster" (approval-walk reboot-test-worktree-review-direction-2026-11-03, item 4.1). A head test run's suites wait 19 times their own run time to start, because about seven test runs run at once on ned-box and the runner starts a suite only while CPU is under 90%; every needless suite-run adds to that wait.

## What needs judgment and what is code

Code, once the design sets the rules: matching recordings to the checkout, storing several recordings per suite and dropping old ones, and option 2's mapping from git commands to paths. Judgment, in the design: how many recordings to keep and which to drop first, and which options to build. Judgment, per suite: for option 1, whether a fixture repository keeps the suite's assertions meaningful, decided by the agent that rewrites it.

## Evidence

The measurement, its scripts and the per-reason totals: nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/reboot-test/test-speed-2026-11-04/findings.md and nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/reboot-test/test-speed-2026-11-04/head-run-selection-reasons.txt.

## Related

On 2026-11-04, `scripts/ghi-guide-agent-ask.py --include-closed`, asked for an issue on either reason, found none. Two open GHIs are near: [The test runner `scripts/run-all-test-suites.py` records which code each test case covers, using coverage.py's per-test contexts](https://github.com/nedschorus/nedschorus/issues/2259), a different mechanism, which this design should check before changing the recording format; and [Each round of a pull request runs its test suites once, and a push reuses a passing test run of the same tree](https://github.com/nedschorus/nedschorus/issues/2384), which skips whole runs rather than single suites. Open [pull request 2544](https://github.com/nedschorus/nedschorus/pull/2544) also changes `scripts/run-all-test-suites.py`, taking the ten suites that run without a sandbox out of per-change test runs.

## Next action

Write the design in this GHI-MD: the recording store's new shape, how many recordings it keeps per suite and which it drops first, how runs that save one suite at once stay safe (today a short lock per suite), the matching rule, how it fits the per-test coverage records of GHI 2259 if both land, and which options to build for reason 2. Then add the line `kind: design` to this GHI-MD's front matter, the block between `---` lines at its top that create-GHI writes, and build it in its own pull request after pull request 2544 merges, because both change the runner's selection code.
