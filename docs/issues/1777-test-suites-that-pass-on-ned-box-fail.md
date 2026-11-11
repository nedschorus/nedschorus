---
issue: "[Test suites that pass on ned-box fail on the Mac when they compare a path that macOS reaches through a link](https://github.com/nedschorus/nedschorus/issues/1777)"
---

# Test suites that pass on ned-box fail on the Mac when they compare a path that macOS reaches through a link

## What happens

Python's `tempfile` puts scratch files under `$TMPDIR`. On the Mac that is `/var/folders/…`, and `/var` is a link to `/private/var`; `/tmp` is also a link there, to `/private/tmp`. On ned-box, `tempfile` uses `/tmp`, which is not a link. A program that resolves a path, as `Path.resolve()` does, reports a Mac scratch path as `/private/var/folders/…`. A test suite that builds the path it expects from the unresolved `tempfile` path then fails on the Mac and passes on ned-box. This issue calls that failure the link-path failure. Because merge-lane-2's review runs the suites on ned-box, such a suite passes review.

This happened twice on 2026-10-20, both times in suites added that day:

- PR [Cold-read programs report a failed git, ssh or judge cell instead of reading it as an answer](https://github.com/nedschorus/nedschorus/pull/1752) added two cold-read-grid test cases whose stand-in git never fired on the Mac. PR [cold-read-grid test: the failing-git stub matches the directory resolved, so it fires on the Mac](https://github.com/nedschorus/nedschorus/pull/1760), now merged, fixed that one stub.
- Three more suites failed the same way: `scripts/dangling-path-citation-check-test.py`, `scripts/stale-code-citation-check-test.py` and `scripts/ghi-issue-write-test.py`. PR [Three Mac-failing suites build their scratch paths under the resolved temporary directory](https://github.com/nedschorus/nedschorus/pull/1775), open when this issue was filed, fixes those three.

Each time, the Mac's pre-push test run refused every Mac push whose selection included a failing suite. The first blocked the filing of a GHI until PR 1760 merged; the second blocks a documentation pull request until PR 1775 merges.

## Why it is found late

- No pull request has its tests run on the Mac before it merges: `nedlern@ned-box:/home/nedlern/nedschorus-logs/pull-request-head-test-runs/mac/` holds two records, both from 2026-10-01.
- The Mac's nightly full test run of main would show the failure the next morning, but no program tells anyone what that run found. GHI [The daily full test runs tell the user about failures and about test cases that run nowhere or lack a tool, and every test suite prints a skipped test case in one format](https://github.com/nedschorus/nedschorus/issues/1206) covers that.
- The suites are right on the machine they were written on, so neither their author nor a reviewer has a reason to look.

## Options

Option 1 hides the difference; option 2 fixes a failing suite; option 3 finds the failure before the merge.

1. `scripts/run-all-test-suites.py` gives every suite it runs a `TMPDIR` that is already resolved. The pre-push run, the nightly run and the head test runs would then never meet the link. But the programs under test would then never meet the link in a test either, although on the Mac they meet it in real use, so a program's own link-path failure would pass every test. A suite run by hand on the Mac still meets the link, and a suite that uses `/tmp` directly is not covered.
2. A shared test helper resolves the temporary directory, and every suite that makes scratch paths uses it. A failing suite is then fixed with one line, as PR 1775 does by hand, but a new suite must remember to use the helper.
3. merge-lane-2's head test run on ned-box sets `TMPDIR` to a directory reached through a link. The link-path failure, in a suite or in a program, would then fail on ned-box before the merge, and its author fixes it, with option 2's helper when the suite is at fault.

Recommendation: options 3 and 2 together. Option 3 moves the finding before the merge on the machine that already runs the review, and keeps the tests as close to real Mac use as they are today; option 2 makes each fix it finds one line. Option 1 is not recommended, because it hides a real Mac failure in a program along with the false ones in the suites.

## Next action

Reproduce the link-path failure on ned-box: check out commit 5477dc2e, before PR 1775, make a directory and a link to it, and run `scripts/dangling-path-citation-check-test.py` with `TMPDIR` set to the link; four cases should fail. Then put the options and the recommendation to the user, and build what he chooses. Its test makes its own directory and link, so it runs on either machine, and fails without the change.
