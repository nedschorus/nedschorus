---
issue: "[Two test cases that fail on a busy machine and pass on rerun: a stop while the last cell saves its report, and a stop while a relaunch is prepared](https://github.com/nedschorus/nedschorus/issues/1112)"
---

# Two test cases that fail on a busy machine and pass on rerun: a stop while the last cell saves its report, and a stop while a relaunch is prepared

Two test cases have each failed in the test run of a pull request's head commit on ned-box and then passed when run again with no code change. A test run of a head commit that fails for no reason in the code holds up the merge of an unrelated pull request until someone reruns it. Fix each case so that it either gets a deadline that holds on a busy machine or waits for the event it is checking instead of a timer.

The user approved filing this GHI on 2026-10-09 (about 05:09Z, "both y") as item 4 of merge-lane-2's open-items approval-walk; the minutes are at `nedlern@ned-box:/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-open-items-walk-2026-10-05-minutes.md`.

A third case, in `scripts/watch-agent-dialog-alerts-test.py`, the several-target watcher exiting when its output closes, was this GHI's case 1 until PR [Delete the retired alert watcher and the dialog watcher; keep project_directory_for_seat in its own module](https://github.com/nedschorus/nedschorus/pull/1262) deleted it together with the watcher, merged as `a2c99fc7` on 2026-10-13.

## Case 1: a stop that lands while the last cell saves its report

`scripts/sanity-check-attacks-test.py`, case 55, the check that opens "a stop that lands while the last cell saves its report ends the run with its STOPPED line, and the report is kept" (line 3017 on main when this was written).

Failure: in the first test run of the head commit of PR [GHI-MD edit for issue 956: Part two: the messages of the git hooks that run at commit and push](https://github.com/nedschorus/nedschorus/pull/1075) at about 2026-10-05 16:10Z; it then passed 3 of 3 reruns.

The timers:
- `wait_until(...)` (line 2368) polls every 0.05 s for up to 30 s, first for the `report-check-hold.held` marker, which says the driver is holding the last cell before its report check, and then, after the test sends SIGTERM, for the `stop-walk-done` marker.
- `process.communicate(timeout=30)` then waits up to 30 s for the run to end.
Both waits already wait for events, so a 30 s limit running out is less likely than with a fixed timer. Which part of the check failed is not known: the failure's detail line (held, walked, record, stdout, stderr) is not in merge-lane-2's report of the failure, which is where this GHI's account of it comes from.

Next action for case 1: find the detail line of the failing run, in the log of the test run of that pull request's head commit, which merge-lane-2 writes under its scratchpad in `/tmp/claude-1000/-home-nedlern-agents-merge-lane-2/` and which may since have been cleaned, or reproduce by running the suite many times under load through `python3 scripts/run-suite-in-signal-sandbox.py scripts/sanity-check-attacks-test.py`. Then fix the condition that failed: a limit that is too short, an event the case does not actually wait for, or another of the check's conditions, such as the STOPPED line or the shipped record.

## Case 2: a stop that lands while a relaunch is prepared

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

Next action for case 2: reproduce by running the suite many times under load through `python3 scripts/run-suite-in-signal-sandbox.py scripts/sanity-check-attacks-test.py`, and record when the driver writes `stop-walk-done` relative to the SIGTERM and to the end of the hold. If the file comes late but before the hold ends, the 10 s limit is too short for a busy machine, and the fix is the one this GHI asks for; if the file comes only after the hold ends, or never, the stop handler waits on the relaunch, and that defect in `scripts/sanity-check-attacks.py` is fixed instead.

## Done when

Each case either waits for its event with only a long ceiling against a hung test, or has a deadline measured to hold on ned-box under a full parallel test run, and the suite passes 20 runs in a row through `python3 scripts/run-suite-in-signal-sandbox.py` while `python3 scripts/run-all-test-suites.py` runs every suite in another checkout.
