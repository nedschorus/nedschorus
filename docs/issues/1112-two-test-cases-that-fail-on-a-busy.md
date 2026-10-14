---
issue: "[Two test cases that fail on a busy machine and pass on rerun: a stop while the last cell saves its report, and a stop while a relaunch is prepared](https://github.com/nedschorus/nedschorus/issues/1112)"
---

# Two test cases that fail on a busy machine and pass on rerun: a stop while the last cell saves its report, and a stop while a relaunch is prepared

Two test cases have each failed in the test run of a pull request's head commit on ned-box and then passed when run again with no code change. A test run of a head commit that fails for no reason in the code holds up the merge of an unrelated pull request until someone reruns it. The evidence points at the runner, `scripts/sanity-check-attacks.py`, rather than at the tests' timers. Case 1's failing line, quoted in merge-lane-2's transcript `nedlern@ned-box:/home/nedlern/nedschorus-logs/transcripts/ned-box/projects/-home-nedlern-agents-merge-lane-2/4dff1cbc-468c-49ba-b869-969b5b147e19.jsonl` at line 911, shows `walked False` and `sanity-check complete`. Read against the runner's code at commit `6782ea5a` (`main`, line 1766, and `run_cells_in_review_copy`, line 1908), those two show that the runner's stop handler did not start in the 30 s that the test held the cell. In case 2 the stop handler was held off for at least 10 s: a relaunch started after the signal, and the runner lets a relaunch start only until its stop handler sets RUN_STOPPED (the section on case 2 below gives the code). The shared suspect is the runner's stop handler starting late, not when the signal comes, while a cell is held. A fix would have to make the runner start its stop handler soon after a stop signal, whatever the cells' threads are doing. The first place to look is the main thread's wait for the cells in `concurrent.futures.as_completed` (line 1896), because Python runs a signal's handler only in the main thread. If reproduction shows instead that the stop handler does start while the hold lasts, only late, the fix is in the tests: each case gets a deadline that holds on a busy machine, or waits for the event it is checking instead of a timer.

The user approved filing this GHI on 2026-10-09 (about 05:09Z, "both y") as item 4 of merge-lane-2's open-items approval-walk; the minutes are at `nedlern@ned-box:/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-open-items-walk-2026-10-05-minutes.md`.

A third case, in `scripts/watch-agent-dialog-alerts-test.py`, the several-target watcher exiting when its output closes, was this GHI's case 1 until PR [Delete the retired alert watcher and the dialog watcher; keep project_directory_for_seat in its own module](https://github.com/nedschorus/nedschorus/pull/1262) deleted it together with the watcher, merged as `a2c99fc7` on 2026-10-13.

Every line number below is a line of `scripts/sanity-check-attacks-test.py` or `scripts/sanity-check-attacks.py` at commit `6782ea5a` on main. If the lines have moved, search for the quoted check names.

## Case 1: a stop that lands while the last cell saves its report

`scripts/sanity-check-attacks-test.py`, case 55 (its comment starts at line 3014), the check that opens "a stop that lands while the last cell saves its report ends the run with its STOPPED line, and the report is kept" (line 3045).

Failure: in the first test run of the head commit of PR [GHI-MD edit for issue 956: Part two: the messages of the git hooks that run at commit and push](https://github.com/nedschorus/nedschorus/pull/1075) at about 2026-10-05 16:10Z; it then passed 3 of 3 reruns. The suite's log from that test run was under merge-lane-2's scratchpad in `/tmp/claude-1000/` and is gone, but merge-lane-2's transcript quotes the failing line: `nedlern@ned-box:/home/nedlern/nedschorus-logs/transcripts/ned-box/projects/-home-nedlern-agents-merge-lane-2/4dff1cbc-468c-49ba-b869-969b5b147e19.jsonl`, line 911, at 2026-10-05T16:13:22Z. The line, with the long paths and the last line of stdout cut where `…` stands:

```
FAIL  a stop that lands while the last cell saves its report ends the run with its STOPPED line, and the report is kept: held True, walked False, record /tmp/tmp8cl4dm7s/repo/sanity-check-records/2026-10-05-stopped-while-a-report-is-saved, stdout 'saved: …/cut-claude.md\nsaved: …/cut-codex.md\nrecord: shipped: 2026-10-05-stopped-while-a-report-is-saved — 3 file(s) added; …\nsanity-check complete: reports in … ', stderr ''
```

The transcript names this as the run's one failing check, so case 55's second check, "and that run still ends by the signal, its copy removed" (line 3054), passed: the run ended by SIGTERM, with its review copy removed.

The timers, in the order the case runs:
- `wait_until(condition, seconds=30.0)` (defined at line 2396) polls every 0.05 s, for up to 30 s unless the call gives another limit. At line 3034 it waits for the `report-check-hold.held` marker, which says the driver is holding the last cell before its report check. This wait succeeded (`held True`).
- After the test sends SIGTERM, the call at line 3036 waits up to 30 s for the `stop-walk-done` marker, which the driver writes once the stop handler has stopped the processes it found. This wait ran out (`walked False`).
- The test then writes the `report-check-hold` file (line 3037), which ends the driver's hold.
- `process.communicate(timeout=30)` (line 3039) then waits up to 30 s for the run to end. The run ended within that limit, since the second check passed.

What the failure shows: three of the check's conditions failed. The wait for `stop-walk-done` ran out; the run printed no STOPPED line; and the run printed `sanity-check complete`, the line of a finished run. A stopped run prints a finished run's lines only when every cell had finished before the stop handler started (`main`, line 1766, and `run_cells_in_review_copy`, line 1908, of `scripts/sanity-check-attacks.py`), and the held cell could finish only after the test ended the hold. So the stop handler had not started in the 30 s between the SIGTERM and the end of the hold, and started after the hold ended. The missing STOPPED line and the `sanity-check complete` line follow from that late start; they are not separate failures. A longer limit on the wait for `stop-walk-done` fixes this case only if the stop handler starts while the hold lasts, and this failure does not show whether the stop handler would.

## Case 2: a stop that lands while a relaunch is prepared

`scripts/sanity-check-attacks-test.py`, case 49 (its comment starts at line 2687), the two checks that open "a stop that lands while a relaunch is prepared: the first launch had failed and the relaunch was under way when the signal came" (line 2723) and "and no agent-binary starts after the signal, and the run ends by it with its copy removed" (line 2727). In the second check's name, "ends by it" means the run ends by the signal.

Failure: in the first test run of the head commit of PR [Launchers: the window title starts with the machine, [box] or [mac]](https://github.com/nedschorus/nedschorus/pull/1150), on merged tree `4c927cce`, at about 2026-10-10 03:33Z; the same suite on the same tree then passed 3 of 3 reruns, and a full rerun passed. The machine was busy: two reviewers' mutation testing runs were waiting on the test lock. The record of the test run is `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/hr/pr1150/log-store/pull-request-head-test-runs/ned-box/4c927cce312d058ef699a6663941ee246881399b.txt`; the failing lines are in the suite's log that the record names, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/hr/pr1150/tmp/nedschorus-pull-request-head-test-run/4c927cce312d058ef699a6663941ee246881399b-20261010T033301Z-513882/logs/scripts__sanity-check-attacks-test.py.log`, lines 244 and 245:

```
FAIL  a stop that lands while a relaunch is prepared: the first launch had failed and the relaunch was under way when the signal came: held True, walked False, stdout 'ERROR: Selected model is at capacity. Please try a different model.\nRETRYING: cut-codex — exit-1 — ERROR: Selected model is at capacity. Please try a different model.\n'
FAIL  and no agent-binary starts after the signal, and the run ends by it with its copy removed: ended by itself False, started [(755, 756)], exit -9, copies root ['stopped-while-a-relaunch-is-prepared-8yqzg1yn'], stdout 'ERROR: Selected model is at capacity. Please try a different model.\nRETRYING: cut-codex — exit-1 — ERROR: Selected model is at capacity. Please try a different model.\n', stderr ''
```

`started` lists one pair for each launch of the stand-in `codex` program that got as far as waiting: the stand-in's own process id, then the process id of the `sleep 300` that the stand-in starts (`recorded_process_ids`, line 2380, and the stand-in's source, line 2238). In this case the first launch fails on purpose and records no pair, so the one pair `(755, 756)` is the relaunch.

The timers, in the order the case runs:
- `wait_until(...)` (line 2711) polls every 0.05 s for up to 30 s for the `relaunch-hold.held` file, which says the driver is holding the codex cell's second launch while its profile is built. This wait succeeded (`held True`).
- After the test sends SIGTERM, `wait_until(walk_done.exists, 10.0)` (line 2713) waits up to 10 s for the `stop-walk-done` file, which the driver writes once the stop handler has stopped the processes it found. This wait ran out (`walked False`).
- The test then writes the `relaunch-hold` file (line 2714), which ends the driver's hold whether or not the stop handler finished, so the relaunch went ahead: an agent-binary started after the signal (`started [(755, 756)]`).
- `process.communicate(timeout=30)` (line 2716) then waited 30 s for the runner to end, ran out (`ended by itself False`), and the test killed the runner (`exit -9`), leaving its review copy.

What the failure shows: the relaunch starts only when RUN_STOPPED is unset at the moment the relaunch takes AGENT_BINARY_LAUNCH_LOCK (`run_agent_binary_unless_run_stopped`, line 648), and the stop handler's first act after taking that lock is to set RUN_STOPPED (`stop_run_on_signal`, line 1311). The hold sits in the building of the codex profile, which `run_codex` does before it takes that lock (line 710, against line 743), so the hold does not keep the stop handler from the lock. So the stop handler had not set RUN_STOPPED in the 10 s between the SIGTERM and the end of the hold. The run then printed no STOPPED line in the next 30 s, so the stop handler had not finished 40 s after the signal.

## What both failures show

In both failures the stop handler did not run while the test held a cell, although nothing in the hold blocks the stop handler: for at least 30 s in case 1 and at least 10 s in case 2. Python runs a signal's handler only in the main thread, and while the cells run, the main thread waits in `concurrent.futures.as_completed` (line 1896 of `scripts/sanity-check-attacks.py`). Why the stop handler did not run during the hold is not known.

## Next action

Reproduce both cases under load, with the hold kept long enough to see when the stop handler starts:
1. In a local copy of the test that is not committed, lengthen the wait for `stop-walk-done` in both cases (lines 2713 and 3036) to 55 s; the driver's `held_until` (line 2332) ends every hold after 60 s on its own. Have the driver record the time the stop handler starts, by wrapping `stop_run_on_signal` as the driver already wraps `stop_processes_this_run_started` to write `stop-walk-done`.
2. Make a second checkout to load the machine: `git worktree add --detach <scratch directory>/load-checkout origin/main`. In that checkout, run `python3 scripts/run-all-test-suites.py --checkout <scratch directory>/load-checkout --lock-file <scratch directory>/load.lock` over and over. The load run needs a lock file of its own because both programs take `~/.claude/.run-all-test-suites.lock` by default, and a run that finds the lock held exits 3 without running anything. The load run's own results do not count.
3. While the load runs, run `python3 scripts/run-suite-in-signal-sandbox.py scripts/sanity-check-attacks-test.py` in the checkout with the changed test until each case has failed once, or 20 times with neither case failing.
4. Read what the runs recorded:
   - If the stop handler starts while the hold lasts, only late, the limit was too short for a busy machine: give the wait a limit measured to hold, or wait for the event, as this GHI's opening paragraph asks.
   - If the stop handler starts only after the hold ends, the defect is in `scripts/sanity-check-attacks.py`, which does not run its stop handler while a cell is held: find why and fix it there.
   - If neither case fails in 20 runs, stop reproducing. Fix from the two recorded failures and the code, and say in the pull request that the failure did not reproduce in 20 runs under load.
5. Remove the load checkout: `git worktree remove --force <scratch directory>/load-checkout`.

## Done when

- Each case either waits for its event with only a long ceiling against a hung test, or has a deadline measured to hold on ned-box under load.
- If the cause is in `scripts/sanity-check-attacks.py`, the fix is there, and comes with a test case that fails on the code before the fix and passes with the fix.
- In either case, `python3 scripts/run-suite-in-signal-sandbox.py scripts/sanity-check-attacks-test.py` passes 20 runs in a row, with the test as committed, while the load run of step 2 of the next action runs over and over until the 20th run ends.

## Provisional additions (not yet vetted by the user)

- ned-box-helper, 2026-10-14: ask the user about the "Next action for case 3" paragraph of this GHI-MD, which ned-box-helper could not settle alone.
