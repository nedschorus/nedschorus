---
issue: "[Test suites that run without a sandbox leave per-change test runs and run apart, when their own files change or in a quiet gap](https://github.com/nedschorus/nedschorus/issues/2381)"
kind: design
---

# Test suites that run without a sandbox leave per-change test runs and run apart, when their own files change or in a quiet gap

## What is wrong

On ned-box, Linux with bwrap, `scripts/run-all-test-suites.py` runs every test suite in its own nc-test-sandbox, except the ten listed in `SUITES_RUN_WITHOUT_ANY_SANDBOX` on 2026-11-03, eight when this GHI was filed, which start bwrap themselves or run the real ssh and so cannot run inside one. Those suites share one machine-wide lock, the file named by `SUITES_RUN_WITHOUT_ANY_SANDBOX_LOCK_FILE_NAME`, and only one of them runs at a time on the whole machine. A test run that selected one of them starts its other suites, but that suite waits until no other run is running one. The ten are `nc-systems/cold-read/tests/cold-read-agy-cell-test.py`, `nc-systems/cold-read/tests/cold-read-fast-read-test.py`, `nc-systems/cold-read/tests/cold-read-grid-test.py`, `nc-systems/general-tools/tests/agy-print-prompt-run-in-empty-home-sandbox-test.py`, `nc-systems/skills/explain/tests/explain-reply-cold-read-fast-read-test.py`, `nc-systems/skills/walk-me-through/tests/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close-test.py`, `scripts/run-all-test-suites-cleanup-after-killed-runs-real-process-test.py`, `scripts/run-all-test-suites-test-sandbox-escape-test.py`, `scripts/run-all-test-suites-overlapping-runs-real-process-test.py` and `scripts/mac-request-from-ned-box-forced-command-test.py`.

Two independent analyses of the agent-sessions' transcripts and the runners' reports for 2026-10-31T00:00Z to 2026-11-02T00:00Z were made, one by Opus and one by Codex. The Opus analysis found:

- In the 226 author test runs that finished, the waits of each run's longest-waiting suite add up to 79.7 of the runs' 84.0 hours; in merge-lane-2's 139 head test runs, to 51.1 of 53.8 hours.
- 76% of the runners' once-a-minute "waits to start" lines in author runs, and 74% in head test runs, name this lock. It was held for 20.6 of the 29.6 hours that test runs covered.
- Each of these suites takes about a minute, but most selections include them.
- Taking them off per-change runs would save an estimated 49 to 88 pull-request hours and 105 to 210 agent-hours a week (Opus report, section 6, proposal 2).

The reports: `nedlern@ned-box:/home/nedlern/nedschorus-logs/analysis/fleet-time-and-token-costs-2026-10-31-to-2026-11-02/opus/report.md` (section 2, "Top time costs", its paragraph "Why test runs are slow", and section 6, proposal 2) and `nedlern@ned-box:/home/nedlern/nedschorus-logs/analysis/fleet-time-and-token-costs-2026-10-31-to-2026-11-02/codex/report.md`.

GHI [Each test suite on ned-box runs in its own throwaway test environment, and suites start by free CPU and memory instead of waiting for a machine-wide lock](https://github.com/nedschorus/nedschorus/issues/1374) replaced the old machine-wide lock with a sandbox and CPU admission for every other suite, and created this lock for the suites that cannot run in the sandbox, and pull request [Test runner admits a suite while machine CPU is under 90%, and every suite runs in one low-CPU-weight slice](https://github.com/nedschorus/nedschorus/pull/2350) raised the CPU limit for starting a suite and did not change this lock.

A third look, at the pre-push selective test runs of 2026-11-02 and 2026-11-03 (`nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/reboot-test/task-316-pre-push-time-budget-root-cause-2026-11-03/findings.md`), found 111 runs stopped at the hook's 480-second budget, 71 on the first day and 40 on the second. In 67 of them the only suites left were no-sandbox ones, each waiting with the runner's line "another run is running a suite that has no sandbox, and that run holds the lock all such suites share". In the hours the findings file measured, 00:00 to 12:00 local time on 2026-11-02 and 00:00 to 05:00 and 09:00 to 12:00 on 2026-11-03, these suites held the lock for 2,300 to 3,300 of most hours' 3,600 seconds, and the longest single wait of any suite in any run on those days was 17,363 seconds.

A fourth look, ned-box-helper's test-time survey of 2026-11-03 and its verification (`nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/ned-box-helper/test-time-survey-2026-11-03/report.md` and `verification.md` beside it), counted 4,379 test runs from 2026-10-27 to 2026-11-03. In 563 of the 686 runs that selected a no-sandbox suite, that suite finished last, which made those runs end about 50 run-hours a day later than their sandboxed suites alone would have. On 2026-11-03, a run of 203 suites finished its 194 sandboxed suites in 7 minutes, and its nine no-sandbox suites added 1.6 hours. Ten more pre-push runs stopped at 480 seconds waiting on the lock between 20:49Z and 21:42Z that day.

A related failure is outside this GHI: mutation testing's quick passes were stopped at 605 seconds on 2026-11-03 because the wait for CPU admission counts against each mutant's time limit, as the survey's verification records.

## What the user decided

On 2026-11-02 at about 00:55Z, in agent-instructions-editor's agent-session on ned-box, the user ruled, in his words: "We should really be careful about anything that locks the testing cycle for everybody. ... Obviously running the same tests is stupid unless there's a reason to run a test. But lock stuff really needs to be attacked. ... I would make all these changes, and I'd make them in the order of efficiency. I think you just said what I said, which is just run the eight lock holding suites completely separately. Or when their files change. Yes, and if that's not enough, maybe we run them four times a day or something. Or when we see we run them nightly, when we're almost positive there'll be a gap, or maybe we wait until things are really quiet and then run them during that gap. ... at some point there aren't anything queued up behind them ... if it did happen, we could stick one in." The user-ruling is recorded at line 35 of `/home/nedlern/agents/agent-instructions-editor/docs/walk/merge-lane-2-seat-brief-rewrite-without-history-2026-11-02-minutes.md` on ned-box. Another change he ordered at the same time, that each round's test suites run once, is GHI [Each round of a pull request runs its test suites once, and a push reuses a passing test run of the same tree](https://github.com/nedschorus/nedschorus/issues/2384).

So:

1. Author test runs, the pre-push selective test run and merge-lane-2's head test run no longer run these suites as part of a run for one change.
2. They run in a test run of their own, apart from those runs, when their own files change.
3. They also run when ned-box is quiet, at a moment when no test run is waiting behind them.
4. If they have not run that day, they run at a fixed time; the design picks four times a day or nightly.

## Design

The user-ruling names eight suites; `SUITES_RUN_WITHOUT_ANY_SANDBOX` lists ten on 2026-11-03, and the design applies to whatever that list holds. This design calls them the no-sandbox suites. Everything below applies where the runner runs the other suites in nc-test-sandboxes, which is Linux with bwrap, ned-box's case, and where the no-sandbox suites' lock exists. Elsewhere, on the Mac and on Linux without bwrap, the whole run takes the machine's lock and nothing changes.

Steps that need judgment: none in the new code. Two steps keep an agent's judgment: an author deciding whether to run a left-out suite by hand before the merge, and merge-lane-2 deciding, from a failure notice, which merged pull request's author to ask about it.

### 1. Per-change test runs leave the no-sandbox suites out

`scripts/run-all-test-suites.py` changes its selective run, a run given `--only-suites-whose-recorded-inputs-changed-since COMMIT` without `--only-suites-named`. Such a run leaves every no-sandbox suite out, whatever changed, the suite's own file included. The runner does this by default, so the pre-push selective test run, an author's test run and merge-lane-2's head test run all leave the suites out with no change to those callers, and no selective caller can bring the lock back by forgetting a flag.

For each no-sandbox suite the selection would have picked, the runner prints, in place of its `SELECTED` line, one line opening `LEFT OUT `, followed by the suite's path, the selection reason, and the command that runs it by hand: `python3 scripts/run-all-test-suites.py --only-suites-named <the suite's path>`. The `SUMMARY:` line adds a count of suites left out. A suite left out is never counted as failed or not run, so a selective run's exit 0 now means every suite it ran passed, and the `LEFT OUT ` lines say which suites it did not run. The readers that pick `FAIL ` and `NOT RUN ` lines apart, `scripts/daily-full-test-run-of-main.py` and `scripts/mutation-testing-changed-lines-quick-or-full-pass-survivors.py`, need no change.

Unchanged: a run with no selection option, such as the daily full test run of main, runs every suite; a run given `--only-suites-named` runs the named suites, narrowed by the selection option when that is given too; so mutation testing still runs a no-sandbox suite when the suite reads a mutated file.

So a change to any file a no-sandbox suite reads, its own file included, is tested by the suites' own run, part 2, after the change reaches main. An author who wants a suite's verdict before the merge, such as for a change to the suite itself or to `scripts/run-all-test-suites.py`, runs the command the `LEFT OUT ` line prints. Per-change runs no longer take the no-sandbox suites' lock; the runs that still take it are part 2's own run, the daily full test run of main, mutation testing that runs a no-sandbox suite, and those hand runs.

### 2. The no-sandbox suites' own run, on main, in a quiet gap

A new program, `scripts/no-sandbox-test-suites-run-on-main-in-a-quiet-gap.py`, runs on ned-box under cron every 10 minutes, from a new entry in `nc-systems/general-tools/scheduled-jobs-on-each-machine.json` with a `ned-box` key only and the output file `.claude/no-sandbox-test-suites-run-on-main-in-a-quiet-gap.log`. It keeps a state file, `~/.local/state/nedschorus/no-sandbox-test-suites-run-on-main-in-a-quiet-gap.json`, which holds two things: the passing commit, the last commit of main at which a run of the program passed; and the last run, with its commit, start and end times, result (passed, failed or stopped), and, for a failure, each failing suite with the log-store copy of its log. The program writes the file whole, to a temporary file renamed into place.

Each run of the program does this, in order:

1. Takes its own lock, the state file's path with `.lock` added, without waiting. When another run of the program holds it, it exits 0.
2. Reads the state file. A file that is missing or cannot be read counts as having no passing commit and no last run.
3. Runs `git fetch origin` and resolves `origin/main` to its full commit hash.
4. Exits 0 when no run is due. A run is due when there is no last run, when the last run was at another commit, when the last run stopped, or when it failed more than an hour ago. So a failure is tried again once an hour at most, which clears a failure that was a passing fault.
5. Checks that ned-box is quiet, in the user-ruling's sense that nothing is waiting behind the no-sandbox suites' lock. It takes that lock, the file the runner names `SUITES_RUN_WITHOUT_ANY_SANDBOX_LOCK_FILE_NAME` in its admission directory, `~/.claude/.run-all-test-suites.lock.test-suite-admission/`, without waiting, and releases it at once; when the lock is held, it exits 0. This sees only whether a suite holds the lock at that moment, not whether another run's suite is between two tries for it. That is close enough: after part 1, few runs take the lock at all.
6. Makes a detached worktree at that commit, under the system temp directory in a directory named for the program, removing first, with `git worktree remove --force` and `git worktree prune`, a worktree a killed run left there. It runs the worktree's runner once, with `--log-dir` set to a directory beside the worktree, with `--only-suites-named` and the no-sandbox suites listed in that worktree's `scripts/run-all-test-suites.py`, plus `--only-suites-whose-recorded-inputs-changed-since <the passing commit>` when there is one. The runner then runs each no-sandbox suite whose recorded inputs changed since the passing commit. The runner has a 60-minute time limit, about six times the ten suites' combined run time.
7. Removes the worktree, then writes its record and the state file. The result is passed when the runner exited 0, and the commit becomes the passing commit; failed when it exited 1, with the suites its `FAIL ` lines name, each suite's log copied into the record's directory; and stopped otherwise, with the reason.

A run that cannot finish, because the fetch, the worktree or a write failed, records that as stopped in the state file where it can, prints the reason, and exits nonzero, so cron's output file keeps it.

Each run that reaches step 6 writes one record to the log-store, at `nedlern@ned-box:/home/nedlern/nedschorus-logs/no-sandbox-test-suites-runs/<YYYY-MM-DD>/<HHMMSS>Z.txt`, with the failing suites' logs beside it. A record holds the commit tested, the passing commit it was compared with, when the run started and ended, each suite run with its result, and the run's result.

### 3. The fixed-time run is the daily full test run of main

`scripts/daily-full-test-run-of-main.py` already starts every day at 03:30 ned-box time, America/Los_Angeles, and runs every suite on main, the no-sandbox suites included. That covers point 4: the suites run every day at a fixed time, whether or not they ran in a quiet gap that day. So the design adds no second fixed-time job. The daily run can still end late on a busy ned-box, or test nothing on a day its fetch fails, as that day's record says. It leaves part 2's state file alone.

### 4. Where a failure goes

A failure in part 2's run is a failure on main, caught after the change merged. `scripts/merge-gate.sh` reads part 2's state file at every run and prints a notice on stderr, without changing its exit code, in three cases: the last run failed, naming each failing suite, the log-store copy of its log, the commit range from the passing commit to the commit tested, and the pull requests merged in that range, read from the merge commits on main's first-parent line, or, when there is no passing commit yet, that there is no range; the last run stopped, naming the reason and, when the run reached step 6, its record; or the state file exists but cannot be read. A missing state file, as before part 2's first run or on a machine without it, prints nothing. The gate's header comment, which says the gate only gates, is amended to allow this notice. A refusal would stop every agent-seat's merges for one suite's failure, which is the lock on the testing cycle the user-ruling attacks.

merge-lane-2 runs the gate before every merge, so it sees a standing failure within one merge. The notice's last line tells it what to do: for a failure with a range, judge from the failing suites' logs and the merged pull requests which change most likely broke the suite, and send that pull request's author a follow-up request, as it does for a non-blocking finding; for a failure it cannot place, a failure with no range, a stopped run or an unreadable state file, send the follow-up to reboot-test, which owns the runner. After sending, it runs part 2's program with `--record-follow-up-sent`, which writes the time into the state file's last run; from then on the gate prints that failure as one line naming the follow-up's time, so a later agent-session of merge-lane-2 does not send it again. A failure that part 2's hourly retry clears before the next merge is never shown; it stays in that run's record.

The user is not told of these failures directly today. The daily full test run's record reaches merge-lane-2 at each session start, and GHI [The daily full test runs tell the user about failures and about test cases that run nowhere or lack a tool, and every test suite prints a skipped test case in one format](https://github.com/nedschorus/nedschorus/issues/1206), not yet built, is the planned path to the user.

### Tests

- The runner: a selective run leaves out a no-sandbox suite, its own file changed or not, and prints the `LEFT OUT ` line with its command; `--only-suites-named` and a full run are unchanged; the exit code ignores a left-out suite.
- Part 2's program, each with a fake runner, a fake lock and a scratch repository: it exits 0 when its own lock or the no-sandbox lock is held; it exits 0 when no run is due, and runs again after a stop, after an hour past a failure, and when main moves; a pass moves the passing commit and a failure does not; a missing or unreadable state file counts as empty; a failed fetch exits nonzero and records a stop; the time limit stops the runner and records a stop.
- `scripts/merge-gate.sh`: the notice appears for a failure, a stop and an unreadable state file, and not for a missing one; it shrinks to one line after `--record-follow-up-sent`; the exit code is unchanged; the notice is gone after a passing run.

## Deferred-decisions

- How part 2 stops the runner and its suites at the time limit, and how a later run avoids removing a worktree that a runner left by a killed run of the program still uses, to be set when the program is built and tested against the runner's process groups.
- The time limit on `git fetch origin` and on the gate's git reads, to be set from their measured durations on ned-box.

## Question for the user

The Opus report names a different fix: stub the agy cell's bwrap in the tests, or allow nested user namespaces, so that these suites run inside the nc-test-sandbox. That would help the six suites that start the agy cell's or the agy program's own bwrap; `scripts/mac-request-from-ned-box-forced-command-test.py` and the three runner suites that start bwrap themselves would each need another fix. It would shrink the need for the lock, instead of moving the suites off per-change runs, so it would change the user-ruling above, and it is the user's to decide.

Recommendation: build this design now, without waiting for the answer, and leave the sandbox alternative out. Thirty days after the build merges, a date reboot-test puts on its task list when it merges, reboot-test counts from part 2's records how often a no-sandbox suite failed on main, and brings the user that count beside the lock's measured waits from before the change, so he can decide then.

## Why it matters

The lock makes a test run that selected a no-sandbox suite wait for whichever run holds it, and most selections include one, so it lies on the critical path of most pull requests. In the analyses' window, 130 pre-push selective test runs stopped at their 480-second budget with no verdict, and the push went ahead without one; on 2026-11-02 and 2026-11-03, after that window, another 111 did.

## Next action

The agent-seat reboot-test builds parts 1, 2 and 4 and their tests in one pull request: the runner change, the new program and its scheduled-jobs entry, and the gate's notice. The pull request description names the user-ruling of 2026-11-02. After it merges, reboot-test runs `python3 nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py --install --job no-sandbox-test-suites-run-on-main-in-a-quiet-gap` on ned-box, then the same program with `--check` in place of `--install`, which must exit 0. Part 3 needs no code.
