---
issue: "[The worktree cleaner's test suite fails 83 test cases and then crashes when lsof is not installed, instead of skipping them](https://github.com/nedschorus/nedschorus/issues/3294)"
---

# The worktree cleaner's test suite fails 83 test cases and then crashes when lsof is not installed, instead of skipping them

## Reproduction

mac-claude reproduced this while reviewing pull request [#3281](https://github.com/nedschorus/nedschorus/pull/3281), in its review 5869686930, at head 8e341577f1d11765fb0d97a94b2eb102c5a7609a and at its merge base 96ef56fa75d404e4243d5ecaa799571a8f8d2ea2 (the failure is the same at both, so main has it). Run `python3 scripts/clean-worktrees-test.py` from the top of a checkout with a `PATH` that holds no `lsof` (mac-claude put `lsof` and `pgrep` out of a symlinked `PATH`). Result: exit 1, 102 cases pass and 83 fail, the first failing case being "a clean, landed, vacant worktree reports done" with the detail "kept ... lsof is not installed", and then the suite crashes with a `FileNotFoundError` on `.git/refs/work-snapshots`. With `lsof` on `PATH` the same suite exits 0 with 284 cases passing.

## What is wrong

`scripts/clean-worktrees-test.py` knows `lsof` can be missing: it prints `SKIP  [this machine cannot run it] occupied cases: lsof is not installed on this machine` and skips only the occupant it would start (the line `if shutil.which("lsof")`). The classification cases that follow run against the machine's real `lsof`, which the suite's docstring says; with none installed, the cleaner under test keeps every worktree as "the vacancy check (lsof) could not be run", so each case that expects a worktree to be done fails. The crash follows the failures. The suite therefore neither skips the cases `lsof` is needed for nor reports that a prerequisite is missing, and it exits with a pile of failures that point away from the cause.

## Why it matters little today

Both machines, ned-box and the Mac, have `lsof`, so no test run hits this. It is a latent defect: a third machine, a stripped container, or a sandbox without `lsof` would show 83 failures for one missing tool. GHI [#1055](https://github.com/nedschorus/nedschorus/issues/1055) covers checking a program's prerequisites before it runs; GHI [#1121](https://github.com/nedschorus/nedschorus/issues/1121) is the design of record for the project's worktrees and owns `scripts/clean-worktrees.py`.

## What to do

Make the suite check for `lsof` once at its start. When `lsof` is missing, skip every case that needs the real `lsof` (the cases the stub-`lsof` runner `run_clean_with_stub_lsof` serves can still run) with the skip line that opens `SKIP  [this machine cannot run it]`, and exit 0, or fail with one line naming the missing tool; either way the 83 failures and the crash must not appear. Add a case that runs the suite with `lsof` left out of `PATH` and checks that result, so the behaviour is tested, not assumed. The skip line's format is the one GHI [#1206](https://github.com/nedschorus/nedschorus/issues/1206) fixes.

## Search receipts

`scripts/ghi-guide-agent-ask.py` on 2026-11-11, open issues: no issue names `scripts/clean-worktrees-test.py` or `lsof`; #1055 and #1121 are the nearest.
