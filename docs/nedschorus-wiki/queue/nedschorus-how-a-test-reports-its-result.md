# How a test reports its result

This page says how a test suite in this repository tells the program that runs it whether it passed. Read it before you write a test suite, or a program that reads a suite's result. `scripts/run-all-test-suites.py` holds the full rules in its built-in help, printed by `python3 scripts/run-all-test-suites.py --help`; this page is the short version.

## What counts as a test suite

A test suite is a file that git tracks whose name ends `-test.py` or `-test.sh`, anywhere in the repository. `scripts/run-all-test-suites.py` runs every such file, and no other. A file git does not track is not run, so commit a new suite, or `git add` it, before you expect it to run. Most suites are plain scripts; a few use Python's `unittest` or `pytest`. Either way the runner treats them the same, by the rules below.

## Pass or fail: the exit code alone

A suite passes when its process exits with code 0. It fails when it exits with any other code, when a signal kills it, or when it runs past its time limit, which the runner's help describes. The runner prints `PASS <path> (<seconds>s)` or `FAIL <path> exit <code> (<seconds>s)` for each suite, and a last line that opens `SUMMARY:` with the counts.

What a suite prints never decides whether it passed. Suites print success in several different wordings, such as "all cases passed" or "OK", so the runner reads no text to decide. A suite that finds a failure must exit nonzero; printing "FAIL" and exiting 0 reports a pass.

## Skipped test cases: a `SKIP` line

A suite sometimes cannot run one of its test cases, for example because a tool the case needs is not installed. It then prints one line for that case that begins with `SKIP`, followed by a space and a sentence saying which case it skipped and why, and goes on with the other cases. Example: `SKIP  occupied cases: lsof is not installed`.

The runner counts every output line that matches the regular expression `^SKIP\s`, adds `, <n> skipped` to the suite's `PASS` or `FAIL` line, and repeats each `SKIP` line, with its suite, at the end of its output. A skip never changes whether the suite passed. A line that begins `SKIP:`, with a colon straight after the word, does not match and is not counted.

Not every suite reports its skips this way yet. GHI [The daily full test runs tell the user about failures and about test cases that run nowhere or lack a tool, and every test suite prints a skipped test case in one format](https://github.com/nedschorus/nedschorus/issues/1206) would make every suite use the `SKIP` line.

## Where the results are kept

A test run started by hand prints its report and also writes it to `test-run-report.txt` in the run's log directory, which the runner's first output line names.

`scripts/daily-full-test-run-of-main.py` runs every suite on main once a day on each machine, ned-box and the Mac, and writes one record per machine and day to `nedlern@ned-box:/home/nedlern/nedschorus-logs/daily-full-test-runs/<machine>/<YYYY-MM-DD>.txt`. The record holds every `FAIL` line and every skipped test case.

## Measurements are not covered

No suite reports a measurement, such as how long an operation took or a quality score, as its result. The runner prints how long each suite ran, but no rule here says how a suite would report a number or what would count as a bad one. When a test needs to report a measurement, this page needs a section for it first.

## Canary tests: an approved addition, not yet built

A canary test runs a real outside program the project does not write, such as `codex` or `gh`, to check that it still behaves the way our code relies on. The rules below are approved but no canary test or program that runs one exists yet.

A canary test follows the exit-code rule above and adds one rule: its last line of standard output is exactly `#canary_pass`, with exit code 0, or exactly `#canary_fail`, with exit code 1. Any other ending, such as no such line, other text on the last line, or an exit code that does not match the line, gives the result `#canary_no_answer`.

The reason for the extra line: a canary test can fail to run at all, for example because the outside program is logged out. An exit code alone would report that as a fail, as if the outside program had behaved wrongly. The last line tells "the outside program failed the check" apart from "the test could not give an answer".
