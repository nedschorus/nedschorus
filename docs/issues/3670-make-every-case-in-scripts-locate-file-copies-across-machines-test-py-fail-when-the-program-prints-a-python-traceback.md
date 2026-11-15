---
issue: "[Make every case in scripts/locate-file-copies-across-machines-test.py fail when the program prints a Python traceback](https://github.com/nedschorus/nedschorus/issues/3670)"
---

# Make every case in scripts/locate-file-copies-across-machines-test.py fail when the program prints a Python traceback

## Problem

In [`scripts/locate-file-copies-across-machines-test.py`](https://github.com/nedschorus/nedschorus/blob/main/scripts/locate-file-copies-across-machines-test.py), the shared helper `run()` returns the exit code, stdout and stderr of one run of [`scripts/locate-file-copies-across-machines.py`](https://github.com/nedschorus/nedschorus/blob/main/scripts/locate-file-copies-across-machines.py) and checks none of them; each case checks what it chooses, and many check only the exit code and stdout. The program exits 1 both when it finds nothing and when it crashes with an uncaught exception, so a crash passes every case that expects exit 1 and does not look at stderr.

Example, checked on main at commit 2bd6c94e3 on 2026-11-14: with ` or len(candidate_names) != 1` deleted from the line `if code == 0 or candidate_names is None or len(candidate_names) != 1:` in `main()` of the program, the case "two candidate names do not rerun" (test file lines 1094-1097) runs into `(full_name,) = candidate_names`, which raises `ValueError: too many values to unpack (expected 1, got 2)` and exits 1, and the case still reports `ok`. That mutant is caught only by other cases, where an empty candidate list makes the same line raise.

[Pull request 3666](https://github.com/nedschorus/nedschorus/pull/3666) fixes one case of this class: the case "no rerun when the candidate list was cut" now also requires that stderr holds no `Traceback`. Its [approving review](https://github.com/nedschorus/nedschorus/pull/3666#pullrequestreview-5909571538) graded the suite-wide fix as one that does not block that merge and is done in a follow-up pull request.

## Why it matters

A test that passes while the program crashes does not test the behaviour it names, so a change that breaks that behaviour can merge with every case passing. Fixing the cases one at a time leaves every other case that expects exit 1 open to the same miss.

## Next action

On main at commit 2bd6c94e3 the test file runs the program in four places: `run()`, `run_in_removed_directory()` inside the removed-directory cases, and two direct `subprocess.run` calls in the cases near lines 1717 and 2134. Make all four go through one function that runs the program and, when stderr holds the line `Traceback (most recent call last):`, records a failure through `check()`, naming the query and printing stderr, so the suite goes on to its next case rather than stopping. Then remove the per-case `"Traceback" not in stderr` checks that this makes redundant: the two in the removed-directory cases, and the one pull request 3666 adds if it has merged by then. No case on main expects the program to crash; if one comes to need it, it says so with an argument to that function.

Add a kept case that runs that function on a stand-in program that raises an exception and requires that the function records a failure, because `CLAUDE.md` asks for a test that causes each failure the code handles. Also confirm by hand that with ` or len(candidate_names) != 1` deleted from the program, the case "two candidate names do not rerun" now fails.
