# How a test suite reports its result

This page says how a test suite in this repository tells the test runner, `scripts/run-all-test-suites.py`, whether it passed, and what the test runner prints. Read it before you write a test suite, or a program that reads the test runner's output. The test runner's module docstring, at the top of the file, holds its complete rules; this page is the short version of the parts a test suite's author needs. The last section, on canary tests, describes rules the user has decided for programs not yet built, which that docstring does not cover.

On this page a test suite is one file, and a test case is one check inside it.

## What counts as a test suite

A test suite is a file that git tracks whose name ends `-test.py` or `-test.sh`, anywhere in the repository. A full test run, which is the test runner started without a selection option, runs every such file and no other. A file git does not track is not run, so commit a new test suite, or `git add` it, before you expect it to run. Run with `--only-suites-whose-recorded-inputs-changed-since <commit>`, as CLAUDE.md asks before every push, the test runner runs only the test suites whose recorded inputs changed, and prints a `NOT SELECTED` line for each of the others.

The test runner runs each test suite as a script, `<python> -u <path>` or `sh <path>`. It does not run pytest or unittest's test discovery. So a test suite that uses Python's `unittest` must itself call `unittest.main()`, and a file that only defines `test_` functions for pytest runs none of them and exits 0, which the test runner reports as a pass. No test suite in the repository uses pytest.

## Pass or fail: the exit code alone

A test suite passes when its process exits with code 0. It fails when it exits with any other code, when a signal kills it, or when it runs past its time limit, which the docstring's PER-SUITE TIMEOUT section sets.

The test runner reads no text a test suite prints to decide whether it passed. Test suites print success in several wordings, such as "all cases passed" or "OK", so no wording can be trusted. A test suite that finds a failure must exit nonzero: printing its own "FAIL" and exiting 0 is reported as a pass.

For each test suite, the test runner prints one line when it finishes, `PASS <path> (<details>)` or `FAIL <path> <why> (<details>)`. `<why>` is `exit <code>`, `killed by <signal>`, `TIMEOUT after <n>s (...)`, or `killed when the run was stopped by <signal>`. `<details>` opens with the seconds the test suite ran, then, when it printed skip lines, `<n> skipped`, then, on Linux, how it was sandboxed and the processor time and memory it used. After every test suite has finished, the test runner prints each failed test suite again with the path of its log file, then every skip line, then a last line that opens `SUMMARY:` and gives the counts of passed, failed and skipped. A test run that was stopped, or could not start a test suite, prints no `SUMMARY:` line: its last line opens `run-all-test-suites: not run to the end`, and it exits 2.

## Skipped test cases: the `SKIP` line

A test suite sometimes cannot run one of its test cases, for example because a tool the test case needs is not installed. It then prints one line for that test case, opening with `SKIP`, then whitespace, then the test case's name and why it was skipped, and goes on with the other test cases. Example: `SKIP  occupied cases: lsof is not installed`.

The test runner counts every line of a test suite's output that matches the regular expression `^SKIP\s`, and shows the count and each line as the section above says. A skip never changes whether the test suite passed. The test runner counts lines, so a line that names several test cases counts as one.

Two kinds of skip are not counted: a line opening `SKIP:`, with a colon straight after the word, as `scripts/locate-user-approval-by-question-subject-test.py` prints, and a skip made through unittest's own `skipTest` or `@unittest.skip`, which unittest reports in its own words.

GHI [The daily full test runs tell the user about failures and about test cases that run nowhere or lack a tool, and every test suite prints a skipped test case in one format](https://github.com/nedschorus/nedschorus/issues/1206) proposes replacing the `SKIP` line with `SKIPPED test case "<name>"; reason: <reason>`, printed by one shared function, and changing the test runner's pattern to match. Until that change is merged, print the `SKIP` line.

## Where the results are kept

Every test run writes its whole report to `test-run-report.txt` in its log directory, which the test runner's first output line names, beside one log file per test suite. Unless `--log-dir` names another directory, the log directory is under the system temp directory and is deleted two days after the test run ends, so copy anything you need to cite before then.

`scripts/daily-full-test-run-of-main.py` starts a full test run of main once a day on each machine, ned-box and the Mac, at 03:30 Pacific time; a Mac run missed while the Mac sleeps starts when it wakes. It writes one record per machine and day to `nedlern@ned-box:/home/nedlern/nedschorus-logs/daily-full-test-runs/<machine>/<YYYY-MM-DD>.txt`, where `<machine>` is `ned-box` or `mac` and the date is the date in America/Los_Angeles when the run started. The record holds every line the test runner printed that opens `FAIL`, and every counted skip line. The full report and the test suites' log files stay on the machine that ran them, and the next day's run replaces them.

## Measurements are not covered

This page has no rule for a test suite that reports a measurement, such as how long an operation took or a quality score, as a number for someone to read. A test suite may measure something and pass or fail on it: `scripts/absence-claim-locator-reminder-hook-test.py` measures a hook's precision and fails when the measured line changes. Its result is still its exit code. Before writing a test suite whose result is a number rather than a pass or a fail, ask the user how it should report.

## Canary tests: decided, not yet built

A canary test runs a real outside program that the project does not write, such as `codex` or `gh`, to check that it still behaves the way our code relies on. It is a kind of contract test; it is not a canary release, the software-engineering sense of "canary". The user decided the rules below in an approval-walk (user-ruled 2026-10-19). No canary test, and no canary runner, the program that will run one, exists yet.

A canary test is one Python file. Its last line of standard output is exactly `#canary_pass`, and it exits 0, when the outside program behaved as relied on; or exactly `#canary_fail`, and it exits 1, when the outside program did not. The canary runner, not the canary test, gives the third result, `#canary_no_answer`, which means the canary test could not tell: when the last line is anything else, when the exit code does not match the line, or when the canary test runs past its time limit and the canary runner kills it. So a canary test that finds it cannot check, for example because the outside program is logged out, prints neither hashtag, and its result is `#canary_no_answer`.

The extra line is what tells "the outside program failed the check" apart from "the canary test could not give an answer": an exit code alone reports both as a fail.

Today's test runner judges a file named `-test.py` by its exit code alone, as above, and in its Linux test sandbox an outside program such as `gh` or `codex` has no network and no login. How the test runner will run canary tests, through the canary runner and outside that sandbox, is not decided yet. The first canary test kept in the repository is to be committed together with that change to the test runner (user-ruled 2026-10-20).
