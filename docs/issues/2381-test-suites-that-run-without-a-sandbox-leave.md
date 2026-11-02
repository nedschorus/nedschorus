---
issue: "[Test suites that run without a sandbox leave per-change test runs and run apart, when their own files change or in a quiet gap](https://github.com/nedschorus/nedschorus/issues/2381)"
---

# Test suites that run without a sandbox leave per-change test runs and run apart, when their own files change or in a quiet gap

## What is wrong

`scripts/run-all-test-suites.py` runs every test suite in its own bwrap sandbox, except the eight listed in `SUITES_RUN_WITHOUT_ANY_SANDBOX`, which start bwrap themselves or run the real ssh and so cannot run inside one. Those eight share one machine-wide lock, the file named by `SUITES_RUN_WITHOUT_ANY_SANDBOX_LOCK_FILE_NAME`, so while any test run on ned-box runs one of them, every other test run that selected one of them waits to start. The eight are `nc-systems/cold-read/tests/cold-read-agy-cell-test.py`, `nc-systems/cold-read/tests/cold-read-fast-read-test.py`, `nc-systems/skills/explain/tests/explain-reply-cold-read-fast-read-test.py`, `nc-systems/skills/walk-me-through/tests/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close-test.py`, `scripts/run-all-test-suites-cleanup-after-killed-runs-real-process-test.py`, `scripts/run-all-test-suites-test-sandbox-escape-test.py`, `scripts/run-all-test-suites-overlapping-runs-real-process-test.py` and `scripts/mac-request-from-ned-box-forced-command-test.py`.

Two independent analyses of the fleet's transcripts and the runners' reports for 2026-10-31T00:00Z to 2026-11-02T00:00Z, one by Opus and one by Codex, found:

- In the 226 author test runs that finished, the longest-waiting suite waited 79.7 of the runs' 84.0 hours; in merge-lane-2's 139 head test runs, 51.1 of 53.8 hours.
- 76% of the runners' once-a-minute "waits to start" lines in author runs, and 74% in head test runs, name this lock. It was held for 20.6 of the 29.6 hours that test runs covered.
- Each of the eight takes about a minute, but most selections include them.
- Taking them off per-change runs would save an estimated 49 to 88 pull-request hours and 105 to 210 agent-hours a week (Opus report, section 6, proposal 2).

The reports: `nedlern@ned-box:/home/nedlern/nedschorus-logs/analysis/fleet-time-and-token-costs-2026-10-31-to-2026-11-02/opus/report.md` (section 2, "Top time costs", its paragraph "Why test runs are slow", and section 6, proposal 2) and `nedlern@ned-box:/home/nedlern/nedschorus-logs/analysis/fleet-time-and-token-costs-2026-10-31-to-2026-11-02/codex/report.md`.

GHI [Each test suite on ned-box runs in its own throwaway test environment, and suites start by free CPU and memory instead of waiting for a machine-wide lock](https://github.com/nedschorus/nedschorus/issues/1374) replaced the old machine-wide lock with a sandbox and CPU admission for every other suite, and pull request [Test runner admits a suite while machine CPU is under 90%, and every suite runs in one low-CPU-weight slice](https://github.com/nedschorus/nedschorus/pull/2350) raised the CPU gate; neither touches this lock.

## What the user decided

On 2026-11-02 at about 00:55Z, in agent-instructions-editor's agent-session on ned-box, the user ruled, in his words: "We should really be careful about anything that locks the testing cycle for everybody. ... Obviously running the same tests is stupid unless there's a reason to run a test. But lock stuff really needs to be attacked. ... I would make all these changes, and I'd make them in the order of efficiency. I think you just said what I said, which is just run the eight lock holding suites completely separately. Or when their files change. Yes, and if that's not enough, maybe we run them four times a day or something. Or when we see we run them nightly, when we're almost positive there'll be a gap, or maybe we wait until things are really quiet and then run them during that gap. ... at some point there aren't anything queued up behind them ... if it did happen, we could stick one in." His ruling is recorded at line 35 of `/home/nedlern/agents/agent-instructions-editor/docs/walk/merge-lane-2-seat-brief-rewrite-without-history-2026-11-02-minutes.md` on ned-box. This change is first in the order he set, by hours saved; the second, that each round's test suites run once, has a GHI of its own, filed with this one, whose GHI-MD's first heading begins "Each round of a pull request runs its test suites once".

So:

1. Author test runs, the pre-push selective test run and merge-lane-2's head test run no longer run the eight suites as part of a run for one change.
2. The eight run in a test run of their own, apart from those runs, when their own files change.
3. They also run when ned-box is quiet, at a moment when no test run is waiting behind them.
4. If they have not run that day, they run at a fixed time; the design picks four times a day or nightly.

## Open questions for the design

- "When their own files change": today the runner's recorded-inputs selection already picks a suite only when one of its recorded inputs changed, yet the eight are picked in most runs, because their inputs include widely edited files such as `scripts/run-all-test-suites.py` and the cold-read programs. The design says which files count as their own, and whether a run for those files still takes the shared lock.
- Whether a pull request that changes one of the eight's own files must pass them before it merges.
- Whether a change to one suite's files runs that suite alone or all eight.
- Where a failure goes when a change breaks one of the eight and the change is caught after it merged, not before: who is told, and how. Code does this, so the failure cannot go unnoticed.
- What happens when an author's or merge-lane-2's test run arrives while the eight are running in a quiet moment, so that the lock does not come back onto the critical path.
- Whether `scripts/daily-full-test-run-of-main.py`, which runs every suite on main at 03:30 on ned-box, already is the nightly run of point 4.
- Whether the change also applies to test runs on the Mac.
- That the runner leaves the eight out of its selective runs by default, rather than through a flag every caller must pass, so a caller that forgets the flag does not bring the lock back.
- What "quiet" means in code: no test run waiting for admission on ned-box, read from the runner's own state.
- The Opus report also names a different fix, letting the eight run in a sandbox (stubbing the agy cell's bwrap in the tests, or allowing nested user namespaces), which would remove the lock instead of moving the suites. The design weighs it against the user's ruling above.

## Why it matters

The lock makes every agent-seat's test run wait for whichever run holds it, so it lies on the critical path of nearly every pull request; 130 pre-push selective test runs in the window stopped at their 480-second budget with no verdict, using CPU, and often the lock, that other runs were waiting for.

## Next action

The agent-seat reboot-test, which owns the runner's CPU admission work, writes the design for the four points above and the open questions as an edit to this GHI-MD, and gives it a /cold-read.
