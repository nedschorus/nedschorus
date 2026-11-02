---
issue: "[Each round of a pull request runs its test suites once, and a push reuses a passing test run of the same tree](https://github.com/nedschorus/nedschorus/issues/2384)"
---

# Each round of a pull request runs its test suites once, and a push reuses a passing test run of the same tree

## What is wrong

Today one round of a pull request, from the author's push to merge-lane-2's review, runs overlapping selections of the test suites three times:

1. The author's test run, which the CLAUDE.md bullet beginning "Before pushing" asks for: `python3 scripts/run-all-test-suites.py --only-suites-whose-recorded-inputs-changed-since origin/main`.
2. The pre-push selective test run, `scripts/git-client-side-hooks-pre-push-selective-test-run.py`, which runs the same selection again on the same files, within a 480-second budget (`DEFAULT_TIME_BUDGET_SECONDS`).
3. merge-lane-2's head test run, run by `scripts/merge-lane-pull-request-worktrees-reviewer-brief-codex-review-and-head-tests-run-without-merge.py`, which selects since the merge base of main and the pull request's head.

Selecting since `origin/main` picks more suites than selecting since the merge base, because it counts every file main changed since the branch started. Test runs started by authors, by hand or by the pre-push hook, averaged 81 suites, and the pre-push runs stopped at the budget averaged 107, against 64 in head test runs.

Two independent analyses of the fleet's transcripts and the runners' reports for 2026-10-31T00:00Z to 2026-11-02T00:00Z, one by Opus and one by Codex, found:

- Pushes cost 18.0 agent-hours in the window and about 8 minutes of each round's critical path (168 pushes, median 8.1 minutes).
- 130 pre-push selective test runs (102 from authors' pushes, 28 from `scripts/ghi-issue-write.py`) stopped at the 480-second budget with no verdict: 17.2 machine-hours thrown away, and each of those pushes went through untested.
- Running each round's suites once would save about 78 pull-request hours and 63 agent-hours a week, and 60 machine-hours (Opus report, section 6, proposal 3).

The reports: `nedlern@ned-box:/home/nedlern/nedschorus-logs/analysis/fleet-time-and-token-costs-2026-10-31-to-2026-11-02/opus/report.md` (section 2, "Retries and timeouts", and section 6, proposal 3) and `nedlern@ned-box:/home/nedlern/nedschorus-logs/analysis/fleet-time-and-token-costs-2026-10-31-to-2026-11-02/codex/report.md`.

## What the user decided

On 2026-11-02 at about 00:55Z, in agent-instructions-editor's agent-session on ned-box, the user ruled, in his words: "Obviously running the same tests is stupid unless there's a reason to run a test. ... I would make all these changes, and I'd make them in the order of efficiency." His ruling is recorded at line 35 of `/home/nedlern/agents/agent-instructions-editor/docs/walk/merge-lane-2-seat-brief-rewrite-without-history-2026-11-02-minutes.md` on ned-box, whose outcome reads in part "tests run once per change unless there is a reason". This change is second in the order he set, by hours saved, after taking the eight test suites that run without a sandbox off per-change test runs, GHI [Test suites that run without a sandbox leave per-change test runs and run apart, when their own files change or in a quiet gap](https://github.com/nedschorus/nedschorus/issues/2381).

So:

1. A push reuses a passing test run of the same tree instead of running the selection again.
2. The author's test run and the pre-push selective test run select since the merge base, as the head test run does.

## Open questions for the design

- How a push knows a passing run covered what it pushes: the runner would record a hash of what it tested with the run's verdict, and the hook would read that record. Today both the author's run and the hook test the checkout's files, uncommitted changes included, while a push sends only commits, so the design says which of the two the hash names and what happens when they differ.
- Whether the head test run also reuses a passing result for suites whose recorded inputs are identical, which the Opus report proposes. Without it, a round still runs its suites twice: once by the author and once in the head test run.
- What the pre-push hook does when no passing run of the pushed tree is recorded, or the last run failed or was stopped: it could run the selection itself, so a push no longer depends on the author having run the tests first.
- Whether the 480-second budget stays, and whether a push whose run reaches it still goes through untested.
- Where the record is kept and when it stops being valid.
- The CLAUDE.md bullet beginning "Before pushing" names `--only-suites-whose-recorded-inputs-changed-since origin/main`. Its new wording goes to the user for approval before it changes; it is not decided here. One option keeps the base out of the bullet: the runner works out the merge base itself, with `git merge-base origin/main HEAD`, as the head test run's program does, so the bullet names one fixed option and an agent cannot type the wrong base.

## Why it matters

Each repeated selection holds CPU, admission slots and often the lock of the suites that run without a sandbox, so it delays every other agent-seat's test run as well as its own. A pre-push run that is stopped at its budget costs the time and still lets the push through untested.

## Next action

The agent-seat reboot-test, which owns the runner's CPU admission work, writes the design for the two points above and the open questions as an edit to this GHI-MD, after the design for the eight test suites that run without a sandbox, and gives it a /cold-read.
