---
issue: "[The signal sandbox test's fake bwrap fails when its status descriptor number is 10 or more, so the test fails at random](https://github.com/nedschorus/nedschorus/issues/1233)"
---

# The signal sandbox test's fake bwrap fails when its status descriptor number is 10 or more, so the test fails at random

## Reproduction

On ned-box, `/bin/sh` is dash (`readlink -f /bin/sh` prints `/usr/bin/dash`), and dash refuses a redirection to a descriptor number of two digits:

```
$ sh -c 'eval "echo x >&9" 9>/dev/null; echo "after 9: $?"'
after 9: 0
$ sh -c 'eval "echo x >&12" 12>/dev/null; echo "after 12: $?"'
sh: 1: eval: Syntax error: Bad fd number
$ echo $?
2
```

A syntax error inside `eval` ends dash with exit 2, so the line after it never runs.

The case "with the sandbox on, report.txt says each suite runs in its own PID namespace" in `scripts/run-all-test-suites-signal-sandbox-test.py` (line 324 on main at `c69fcf88`) runs `scripts/run-all-test-suites.py` on a scratch checkout that holds two one-line suites the test writes itself, `a-test.py` and a copy of `scripts/mac-window-opened-for-ned-box-forced-command-test.py`, each printing `ran`, with a fake `bwrap` first on PATH. The runner runs `a-test.py` inside the fake bwrap, and runs the other suite without the signal sandbox. The fake bwrap is a `#!/bin/sh` script, written by the test, that ends with these two lines:

```
[ -n "$status_fd" ] && eval "echo '{\"child-pid\": $$}' >&$status_fd"
exec "$@"
```

`$status_fd` is the number the runner passes with `--json-status-fd`: the write end of an `os.pipe()` that `run_one_suite` in `scripts/run-all-test-suites.py` opens just before it starts the suite. When that number is 10 or more, dash stops at the `eval` with exit 2, the `exec "$@"` that would start the suite never runs, and the runner reports `FAIL a-test.py exit 2 (0.0s)`. The runner then exits 1, and the case fails.

Captured on 2026-10-13 on ned-box, at origin/main `c69fcf88`: the suite was run 20 times through `python3 scripts/run-suite-in-signal-sandbox.py scripts/run-all-test-suites-signal-sandbox-test.py`, with the test changed only to copy its scratch directory aside when the inner run failed. The suite failed once in the 20 runs, and the copied `a-test.py.log` holds one line:

```
/tmp/tmph6v52k7k/bin/bwrap: 1: eval: Syntax error: Bad fd number
```

The same changed test, run directly 40 times outside the signal sandbox, did not fail.

## Why it fails only sometimes

The runner passes the pipe's write end to the fake bwrap at whatever number the operating system gave it, so the number depends on how many descriptors the runner process holds open at that moment. The runner starts suites in parallel threads, each with its own log file and pipe, and under the signal sandbox, and in a head test run (a run of `scripts/pull-request-head-test-run.py` on a pull request's head commit merged onto main), which also records each suite's inputs, it holds more descriptors. On some runs the number reaches 10. Run by hand on 2026-10-13 at about 01:10Z UTC, the suite failed 2 of 9 times on the merged tree of pull request #1226 and 0 of 9 times on main, although the test and runner files were byte-identical in both; the difference is chance, as the descriptor number varies from run to run.

## Where it has failed

The case failed in the head test runs of six pull requests on ned-box, each time with `FAIL a-test.py exit 2 (0.0s)` from the inner run:

- 2026-10-12T02:57Z, pull request [#1188](https://github.com/nedschorus/nedschorus/pull/1188): the record `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/hr/pr1188/log-store/pull-request-head-test-runs/ned-box/7f0ba4686e67aeff91de9f487250fccda524dc2f.txt`, and the suite's log `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/hr/pr1188/tmp/nedschorus-pull-request-head-test-run/7f0ba4686e67aeff91de9f487250fccda524dc2f-20261012T025745Z-1380500/logs/scripts__run-all-test-suites-signal-sandbox-test.py.log`.
- 2026-10-12T19:01Z, pull request [#1200](https://github.com/nedschorus/nedschorus/pull/1200): the record `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/hr/pr1200/log-store/pull-request-head-test-runs/ned-box/9bcece235de3e8fe0a28c7836de3504e3337009d.txt`, and the suite's log `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/hr/pr1200/tmp/nedschorus-pull-request-head-test-run/9bcece235de3e8fe0a28c7836de3504e3337009d-20261012T190115Z-1008389/logs/scripts__run-all-test-suites-signal-sandbox-test.py.log`.
- 2026-10-13T01:09Z, pull request [#1226](https://github.com/nedschorus/nedschorus/pull/1226): the record `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/hr/pr1226/log-store/pull-request-head-test-runs/ned-box/2b3dcf1668f594fea2f68d494f461a06c5d72370.txt`, and the suite's log `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/hr/pr1226/tmp/nedschorus-pull-request-head-test-run/2b3dcf1668f594fea2f68d494f461a06c5d72370-20261013T010903Z-3029873/logs/scripts__run-all-test-suites-signal-sandbox-test.py.log`.
- 2026-10-13T20:06Z, PR [Session dialogs: nice-but-dirty files, the extractor survives a tracker failure, a stale dialog says so](https://github.com/nedschorus/nedschorus/pull/1274), on the merge commit `16c3cc4f` of its head `b9ddba6a` onto main: the record `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/hr/pr1274/log-store/pull-request-head-test-runs/ned-box/16c3cc4f3b036b90f5f113032e0b0e343943f220.txt`, and the suite's log `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/hr/pr1274/tmp/nedschorus-pull-request-head-test-run/16c3cc4f3b036b90f5f113032e0b0e343943f220-20261013T200613Z-1952004/logs/scripts__run-all-test-suites-signal-sandbox-test.py.log`.
- 2026-10-13T20:07Z, PR [Bash guards: one committed script replays recorded real commands at two refs and blocks on a changed verdict](https://github.com/nedschorus/nedschorus/pull/1278), on the merge commit `f95d3eb0` of its head `25169d2e` onto main: the record `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/hr/pr1278/log-store/pull-request-head-test-runs/ned-box/f95d3eb0e318b89ca387277c43a80f863a2083d9.txt`, and the suite's log `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/hr/pr1278/tmp/nedschorus-pull-request-head-test-run/f95d3eb0e318b89ca387277c43a80f863a2083d9-20261013T200754Z-1972553/logs/scripts__run-all-test-suites-signal-sandbox-test.py.log`.
- 2026-10-13T20:16Z, PR [Crash restart watcher: tell the user about a seat recovery refuses or a leftover shell holds](https://github.com/nedschorus/nedschorus/pull/1277), on the merge commit `536ccb41` of its head `0d89cd1f` onto main: the record `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/hr/pr1277/log-store/pull-request-head-test-runs/ned-box/536ccb418b76d0d54e8d326a1e3ebb5caa639171.txt`, and the suite's log `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/hr/pr1277/tmp/nedschorus-pull-request-head-test-run/536ccb418b76d0d54e8d326a1e3ebb5caa639171-20261013T201612Z-2115714/logs/scripts__run-all-test-suites-signal-sandbox-test.py.log`.

Each of the last three records holds a second head test run on the same merge commit, started 7 to 15 minutes after the failing one with no change to the code: at 20:12:55Z for PR 1274, 20:22:50Z for PR 1278 and 20:26:43Z for PR 1277. In each second run `scripts/run-all-test-suites-signal-sandbox-test.py` passed.

The inner runs' own `a-test.py.log` files were in temporary directories that the test deletes, so these six runs' logs do not show dash's message; the captured run above does.

## Why it matters

A failing head test run blocks a merge, so each time this case fails, merge-lane-2 holds an unrelated pull request until the run is repeated and the case passes.

## What is and is not wrong

The defect is in the test's fake bwrap only. The real bwrap is a compiled program and accepts any descriptor number, and the runner's `--json-status-fd` handling is not involved: the fake bwrap fails before the suite starts.

## Next action

Change the fake bwrap in `scripts/run-all-test-suites-signal-sandbox-test.py` so that it writes to a descriptor of any number. Two ways that would do it: make the fake bwrap a `#!/bin/bash` script, since bash accepts descriptor numbers above 9 in a redirection; or keep `#!/bin/sh` and replace the `eval` line with `[ -n "$status_fd" ] && echo "{\"child-pid\": $$}" > "/dev/fd/$status_fd"`, which keeps the check for a missing `--json-status-fd`. `/dev/fd` needs `/proc`, which ned-box has outside the signal sandbox and the signal sandbox mounts with `--proc /proc`; the case runs only on Linux. No other file under `scripts/` redirects to a descriptor held in a variable: `git grep -n '>&\$\|>&"\$' origin/main -- 'scripts/*'` at `c69fcf88` finds only this fake bwrap's line.

## Done when

A new test case in `scripts/run-all-test-suites-signal-sandbox-test.py` runs the fake bwrap directly, not through the runner: it opens a pipe, moves the pipe's write end to descriptor 12 with `os.dup2`, and runs the fake bwrap with `--json-status-fd 12` and a short command such as `sh -c 'echo started'`, passing descriptor 12 to it. The case checks that the pipe receives the `child-pid` line and that the command's output is `started`; it runs the same check with descriptor 9 so the one-digit case stays covered. The case fails against the current fake bwrap and passes against the fixed one.

## Related

GHI [#1112](https://github.com/nedschorus/nedschorus/issues/1112) collects test cases that fail on a busy machine because a deadline runs out. This failure is a different matter: no deadline is involved, and #1112's fix of longer deadlines or waiting for events would not change it.

Search receipt: on 2026-10-13 UTC, `scripts/ghi-info-ask.py --include-closed` found no issue, open or closed, naming this test file, this case, "PID namespace", "a-test.py", "bwrap" or "signal-sandbox" for a failure; and `gh issue list --state all --search` on "signal-sandbox", "PID namespace", "flaky test", "intermittent" and "bwrap" returned no issue about this failure.
