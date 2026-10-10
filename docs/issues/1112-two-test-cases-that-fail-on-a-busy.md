---
issue: "[Three test cases that fail on a busy machine and pass on rerun: the several-target watcher exiting when its output closes, a stop while the last cell saves its report, and a stop while a relaunch is prepared](https://github.com/nedschorus/nedschorus/issues/1112)"
---

# Three test cases that fail on a busy machine and pass on rerun: the several-target watcher exiting when its output closes, a stop while the last cell saves its report, and a stop while a relaunch is prepared

Three test cases have each failed in the test run of a pull request's head commit on ned-box and then passed when run again with no code change. A test run of a head commit that fails for no reason in the code holds up the merge of an unrelated pull request until someone reruns it. Fix each case so that it either gets a deadline that holds on a busy machine or waits for the event it is checking instead of a timer.

The user approved filing this GHI on 2026-10-09 (about 05:09Z, "both y") as item 4 of merge-lane-2's open-items approval-walk; the minutes are at `nedlern@ned-box:/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-open-items-walk-2026-10-05-minutes.md`.

## Case 1: the several-target watcher exits when its output closes

`scripts/watch-agent-dialog-alerts-test.py`, the check that opens "when its output closes, the several-target watcher exits and takes both child watchers with it" (line 1273 on main when this was written).

Failures: in the test run of the head commit of PR [instruction-file-guard: each refusal says to create .walk-approved with the Write tool](https://github.com/nedschorus/nedschorus/pull/1032) on 2026-10-04, and of PR [A reminder to run the locator replaces CLAUDE.md's locate-first line](https://github.com/nedschorus/nedschorus/pull/1071) at about 2026-10-05 06:45Z. Each passed on rerun.

The timers, in the order the case runs:
- It waits up to 20 s (`deadline = time.monotonic() + 20.0`) for both child watchers to print their `: started` lines.
- It closes the watcher's output, then waits up to 15 s (`process.wait(timeout=15)`) for the watcher to exit. On timeout it records "still running 15 s after its output closed".
- The exit itself depends on a child watcher writing a line after the output closed: the fake Mac stream ends after 1.5 s (`hold_seconds: 1.5`), so its child writes once more and finds the pipe closed. On a busy machine, the child's write, the watcher's notice of the broken pipe, and the teardown of both children all queue behind other work.

What it could wait on instead: the event the case checks is that the watcher exits and both child watchers are gone. The case could wait for the two `: started` lines and for the watcher process's exit with no fixed short limit, keeping only a long ceiling, such as 120 s, to stop a hung test: neither the 20 s nor the 15 s figure asserts anything about the code.

## Case 2: a stop that lands while the last cell saves its report

`scripts/sanity-check-attacks-test.py`, case 55, the check that opens "a stop that lands while the last cell saves its report ends the run with its STOPPED line, and the report is kept" (line 3017 on main when this was written).

Failure: in the first test run of the head commit of PR [GHI-MD edit for issue 956: Part two: the messages of the git hooks that run at commit and push](https://github.com/nedschorus/nedschorus/pull/1075) at about 2026-10-05 16:10Z; it then passed 3 of 3 reruns.

The timers:
- `wait_until(...)` (line 2368) polls every 0.05 s for up to 30 s, first for the `report-check-hold.held` marker, which says the driver is holding the last cell before its report check, and then, after the test sends SIGTERM, for the `stop-walk-done` marker.
- `process.communicate(timeout=30)` then waits up to 30 s for the run to end.
Both waits already wait for events, so a 30 s limit running out is less likely than in case 1. Which part of the check failed is not known: the failure's detail line (held, walked, record, stdout, stderr) is not in merge-lane-2's report of the failure, which is where this GHI's account of it comes from.

Next action for case 2: find the detail line of the failing run, in the log of the test run of that pull request's head commit, which merge-lane-2 writes under its scratchpad in `/tmp/claude-1000/-home-nedlern-agents-merge-lane-2/` and which may since have been cleaned, or reproduce by running the suite many times under load through `python3 scripts/run-suite-in-signal-sandbox.py scripts/sanity-check-attacks-test.py`. Then fix the condition that failed: a limit that is too short, an event the case does not actually wait for, or another of the check's conditions, such as the STOPPED line or the shipped record.

## Case 3: a stop that lands while a relaunch is prepared

`scripts/sanity-check-attacks-test.py`, case 49, the two checks that open "a stop that lands while a relaunch is prepared: the first launch had failed and the relaunch was under way when the signal came" and "and no agent-binary starts after the signal, and the run ends by it with its copy removed" (the case starts at line 2659 on main when this was written).

Failure: in the first test run of the head commit of PR [Launchers: the window title starts with the machine, [box] or [mac]](https://github.com/nedschorus/nedschorus/pull/1150), on merged tree `4c927cce`, at about 2026-10-10 03:33Z; the same suite on the same tree then passed 3 of 3 reruns, and a full rerun passed. The machine was busy: two reviewers' mutation testing runs were waiting on the test lock. The record of the test run is `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/hr/pr1150/log-store/pull-request-head-test-runs/ned-box/4c927cce312d058ef699a6663941ee246881399b.txt`; the failing lines are in the suite's log that the record names, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/hr/pr1150/tmp/nedschorus-pull-request-head-test-run/4c927cce312d058ef699a6663941ee246881399b-20261010T033301Z-513882/logs/scripts__sanity-check-attacks-test.py.log`, lines 244 and 245:

```
FAIL  a stop that lands while a relaunch is prepared: the first launch had failed and the relaunch was under way when the signal came: held True, walked False, stdout 'ERROR: Selected model is at capacity. Please try a different model.\nRETRYING: cut-codex — exit-1 — ERROR: Selected model is at capacity. Please try a different model.\n'
FAIL  and no agent-binary starts after the signal, and the run ends by it with its copy removed: ended by itself False, started [(755, 756)], exit -9, copies root ['stopped-while-a-relaunch-is-prepared-8yqzg1yn'], stdout 'ERROR: Selected model is at capacity. Please try a different model.\nRETRYING: cut-codex — exit-1 — ERROR: Selected model is at capacity. Please try a different model.\n', stderr ''
```

The timers, in the order the case runs:
- `wait_until(...)` polls every 0.05 s for up to 30 s for the `relaunch-hold.held` file, which says the driver is holding the codex cell's second launch while its profile is built. This wait succeeded (`held True`).
- After the test sends SIGTERM, `wait_until(walk_done.exists, 10.0)` waits up to 10 s for the `stop-walk-done` file, which the driver writes once the stop handler has stopped the processes it found. This wait ran out (`walked False`).
- The test then writes the `relaunch-hold` file, which ends the driver's hold, whether or not the handler finished, so the relaunch went ahead: an agent-binary started after the signal (`started [(755, 756)]`).
- `process.communicate(timeout=30)` then waited 30 s for the runner to end, ran out (`ended by itself False`), and the test killed the runner (`exit -9`), leaving its review copy.

The 10 s wait for the stop handler is the shortest limit and the first to fail; the later failures follow from the test letting the hold go after it. Whether the handler was only slow, or was stuck until the hold was let go, is not known from the log.

Next action for case 3: reproduce by running the suite many times under load through `python3 scripts/run-suite-in-signal-sandbox.py scripts/sanity-check-attacks-test.py`, and record when the driver writes `stop-walk-done` relative to the SIGTERM and to the end of the hold. If the file comes late but before the hold ends, the 10 s limit is too short for a busy machine, and the fix is the one this GHI asks for; if the file comes only after the hold ends, or never, the stop handler waits on the relaunch, and that defect in `scripts/sanity-check-attacks.py` is fixed instead.

## Done when

Each case either waits for its event with only a long ceiling against a hung test, or has a deadline measured to hold on ned-box under a full parallel test run, and the suite passes 20 runs in a row through `python3 scripts/run-suite-in-signal-sandbox.py` while `python3 scripts/run-all-test-suites.py` runs every suite in another checkout.
