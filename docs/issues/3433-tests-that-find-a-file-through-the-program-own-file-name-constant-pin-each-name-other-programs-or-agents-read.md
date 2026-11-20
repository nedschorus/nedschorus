---
issue: "[Tests that find a file through the program's own file name constant: pin each name other programs or agents read](https://github.com/nedschorus/nedschorus/issues/3433)"
---

# Tests that find a file through the program's own file name constant: pin each name other programs or agents read

A test that finds a program's output file through the program's own constant, such as `groups_file.with_name(replay.ADDED_GUARD_REFUSAL_GROUP_RIGHTLY_REFUSED_REVIEW_ANSWER_LINES_FILE_NAME)`, reads the name from the same Python constant the program writes it with. When someone changes the constant's value, the program and the test both use the new value without the test being edited, so the test still passes. When another program, an agent or a document reads that file by its old name, the change breaks that reader and no test fails. This GHI asks for a test that fails whenever a file name constant whose value something outside its program reads is not also checked against its literal value, and for the pins that make that test pass on main.

## Why

- It has happened. In merge-lane-2's follow-up request on PR [Bash guards replay: the refusal right lines file and its constant are named for the rightly refused review answer lines they hold](https://github.com/nedschorus/nedschorus/pull/3311), finding 1 reported that putting `ADDED_GUARD_REFUSAL_GROUP_RIGHTLY_REFUSED_REVIEW_ANSWER_LINES_FILE_NAME` back to its old value `"added-guard-refusal-right-lines.txt"` left all 155 cases of `nc-systems/general-tools/tests/bash-guards-verdict-changes-between-git-refs-on-recorded-commands-check-test.py` passing.
- PR [Bash guards replay test: pin the rightly refused review answer lines file's name](https://github.com/nedschorus/nedschorus/pull/3328) pins that one name: its test checks `lines_file.name == "added-guard-refusal-group-rightly-refused-review-answer-lines.txt"`. Its description's `#root_cause_not_fixed` line leaves the other tests that find a file through their program's constant to this GHI.
- Pinning the cases found today by hand fixes those cases only. A test that keeps checking catches the next one too, which is the root cause the PR 3328 line leaves.

## What exists today

On main at c0e19b69a, `grep -rlE "[a-z_]+\.[A-Z][A-Z_]*_(FILE_NAME|FILENAME|DIRECTORY_NAME)\b" --include='*test*.py' .` lists 34 test files that use such a constant through a module name. The grep is a rough count: it also matches uses that do not find a file, and it misses a constant imported with `from <module> import <NAME>` and constants with other suffixes, such as `_PATH`. The files with the most matching lines are:

| Test file | Matching lines |
|---|---|
| `scripts/scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open-test.py` | 40 |
| `scripts/ghi-guide-agent-ask-test.py` | 23 |
| `scripts/standing-user-rulings-store-add-from-transcripts-and-walk-minutes-then-index-file-and-anchor-list-for-hooks-write-test.py` | 18 |
| `scripts/run-all-test-suites-machine-wide-test-suite-admission-test.py` | 15 |
| `scripts/ghi-mirror-refresh-test.py` | 14 |

Whether any of these tests already checks a name against its literal value elsewhere in the file was not checked.

## What to do

1. Write a test, in the repository's test suites, that reads every program's assignments of a string literal to a constant whose name ends in `_FILE_NAME`, `_FILENAME` or `_DIRECTORY_NAME`, and, for each, runs `git grep -F` on the literal outside the program and outside the program's own test. When that search finds the literal, the test fails unless the program's own test contains the literal too. Its failure message names the constant, the program, the files where the literal was found, and the test file that should check it.
2. Run it on main. For each failure, judge whether the hit is a real reader of the file by that name, such as another program, a hook, or an agent's instructions, or a coincidence, such as a changelog line. For a real reader, add to the program's test a check that the path the test found has that literal name, as PR 3328 does. For a coincidence, add the constant to an exceptions list in the new test, with the reason on its line.
3. Land the new test with the pins and exceptions that make it pass on main, in one pull request whose description carries a `#root_cause` line, or split the pins by test suite when one pull request would be too big for a reader to say in one sentence what it does.

## Deferred-decisions

- Whether the new test also searches the log-store on ned-box for files already written under each name, to be settled once step 2 shows whether any constant's only reader is a file already on disk.
