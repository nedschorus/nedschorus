# How a test suite reports its result

This page says how a test suite in this repository tells the test runner, `scripts/run-all-test-suites.py`, whether it passed, and what the test runner prints. Read it before you write a test suite, or a program that reads the test runner's output. The test runner's module docstring, at the top of the file, holds its complete rules; this page is the short version of the parts a test suite's author needs. The last section, on canary tests, describes rules the user has decided for programs not yet built, which that docstring does not cover.

On this page a test suite is one file, and a test case is one check inside it.

## What counts as a test suite

A test suite is a file that git tracks whose name ends `-test.py` or `-test.sh`, anywhere in the repository. A full test run, which is the test runner started without a selection option, runs every such file and no other. A file git does not track is not run, so commit a new test suite, or `git add` it, before you expect it to run. Run with `--only-suites-whose-recorded-inputs-changed-since <commit>`, as CLAUDE.md asks before every push, the test runner runs only the test suites whose recorded inputs changed, and prints a `NOT SELECTED` line for each of the others.

The test runner runs each test suite as a script, `<python> -u <path>` or `sh <path>`. It does not run pytest or unittest's test discovery. So a test suite that uses Python's `unittest` must itself call `unittest.main()`, or, with `exit=False`, exit nonzero itself when a test case fails, and a file that only defines `test_` functions for pytest runs none of them and exits 0, which the test runner reports as a pass. No test suite in the repository uses pytest.

## Pass or fail: the exit code alone

A test suite passes when its process exits with code 0. It fails when it exits with any other code, when a signal kills it, or when it runs past its time limit, which the docstring's PER-SUITE TIMEOUT section sets.

The test runner reads no text a test suite prints to decide whether it passed. The test runner reads test case lines such as `PASS`, `FAIL` or `ok` only to time and record each test case. Test suites print success in several wordings, such as "all cases passed" or "OK", so no wording can be trusted. A test suite that finds a failure must exit nonzero: printing its own "FAIL" and exiting 0 is reported as a pass.

The test runner prints a line opening `PASS` or `FAIL` as each test suite finishes, then each failure again with its log file, then every skip line, and ends with a line opening `SUMMARY:`; a test run that ends early prints no `SUMMARY:` line and exits 2. The docstring of `scripts/run-all-test-suites.py` gives every line's exact form.

## Skipped test cases: the `SKIP` line

A test suite sometimes cannot run one of its test cases, for example because a tool the test case needs is not installed. It then prints one line for that test case and goes on with the other test cases. Print `SKIP`, a space, the test case and the reason. Any other form, such as `SKIP:` or unittest's own skip, is not counted, and `scripts/test-suites-source-scan-for-skipped-case-prints-run-all-test-suites-cannot-count-test.py` fails on it. When the machine itself is the cause, put `[this machine cannot run it]` before the test case; the test runner's docstring says what the mark changes. Example: `SKIP  occupied cases: lsof is not installed`.

The test runner counts every line of a test suite's output that matches the regular expression `^SKIP\s`, and shows the count and each line as the section above says. A skip never changes whether the test suite passed: a test suite that skips every test case and exits 0 is reported as a pass. The test runner counts lines, so a line that names several test cases counts as one.

GHI [The daily full test runs tell the user about failures and about test cases that run nowhere or lack a tool, and every test suite prints a skipped test case in one format](https://github.com/nedschorus/nedschorus/issues/1206) proposes replacing the `SKIP` line with `SKIPPED test case "<name>"; reason: <reason>`, printed by one shared function, and changing the test runner's pattern to match. Until that change is merged, print the `SKIP` line.

## Where the results are kept

Every test run writes its whole report to `test-run-report.txt` in its log directory, which the test runner's first output line names, beside one log file per test suite. Unless `--log-dir` names another directory, the log directory is under the system temp directory and is deleted two days after the test run ends, so copy anything you need to cite before then.

`scripts/daily-full-test-run-of-main.py` starts a full test run of main once a day on each machine, ned-box and the Mac, at 03:30 Pacific time; a Mac run missed while the Mac sleeps starts when it wakes. It writes one record per machine and day to `nedlern@ned-box:/home/nedlern/nedschorus-logs/daily-full-test-runs/<machine>/<YYYY-MM-DD>.txt`, where `<machine>` is `ned-box` or `mac` and the date is the date in America/Los_Angeles when the run started. The record holds the run's failures and counted skips; the docstring of `scripts/daily-full-test-run-of-main.py` lists all it holds. The full report and the test suites' log files stay on the machine that ran them, in `<system temp directory>/nedschorus-daily-full-test-run-of-main/logs`, which the record names and the next day's run replaces.

## A test suite that measures something

A test suite that measures something, such as a duration or how often a hook's reminder is right, prints the number and the threshold, and passes or fails against the threshold, which its author may set by judgement, saying why in a comment beside it. Work whose result is a number with no pass or fail is not a test suite; it is a check, and reports as reboot-test's exit-code wiki page says.

## Canary tests: decided, not yet built

A canary test runs a real outside program that the project does not write, such as `codex` or `gh`, to check that it still behaves the way our code relies on. It is a kind of contract test; it is not a canary release, the software-engineering sense of "canary". The user decided the rules below in an approval-walk (user-ruled 2026-10-19). No canary test, and no canary runner, the program that will run one, exists yet.

A canary test is one Python file. Its last line of standard output is exactly `#canary_pass`, and it exits 0, when the outside program behaved as relied on; or exactly `#canary_fail`, and it exits 1, when the outside program did not. The canary runner, not the canary test, gives the third result, `#canary_no_answer`, which means the canary test could not tell: when the last line is anything else, when the exit code does not match the line, or when the canary test runs past its time limit and the canary runner kills it. So a canary test that finds it cannot check, for example because the outside program is logged out, prints neither hashtag, whatever its exit code, and its result is `#canary_no_answer`. The canary runner logs standard output and standard error together, so a canary test prints nothing to standard error after its hashtag line.

The extra line is what tells "the outside program failed the check" apart from "the canary test could not give an answer": an exit code alone reports both as a fail.

Today's test runner judges a file named `-test.py` by its exit code alone, as above, and in its Linux test sandbox an outside program such as `gh` or `codex` has no network and no login. How the test runner will run canary tests, through the canary runner and outside that sandbox, is not decided yet. The first canary test kept in the repository is to be committed together with that change to the test runner (user-ruled 2026-10-20).
