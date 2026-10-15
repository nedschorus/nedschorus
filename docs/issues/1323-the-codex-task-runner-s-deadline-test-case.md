---
issue: "[The Codex task runner's deadline test case fails on a busy machine, because a scan of the whole home directory runs before the deadline starts](https://github.com/nedschorus/nedschorus/issues/1323)"
---

# The Codex task runner's deadline test case fails on a busy machine, because a scan of the whole home directory runs before the deadline starts

## Reproduction

The case "the deadline stops Codex, exits 1 and says so" in `scripts/run-codex-task-from-brief-test.py` (lines 194 to 206 on main at `85ad6555`) runs `scripts/run-codex-task-from-brief.py` with `--deadline-minutes 0.05`, a 3-second deadline, against a fake `codex` in the mode `sleep`, which sleeps for 600 seconds and dies on SIGTERM. The case passes only when the whole invocation of the program, measured by the test from start to exit, takes less than 30 seconds (`elapsed < 30`, line 205).

The program spends most of that time before the deadline starts. Before it starts Codex, the program builds Codex's command line with `codex_command`, which calls `codex_credential_denying_permission_profile_arguments` in `nc-systems/cold-read/cold-read-cell-common.py`. On Linux, that function calls `credential_files_found_now` (line 94), which runs `find` over the whole home directory and the repository (`CREDENTIAL_FILE_SCAN_ROOTS`, line 91; the `find` command, line 106) to list every file named `*.token` or `.env`. Only after `find` returns does the program call `subprocess.Popen` (line 162 of the program) and start the deadline with `process.wait(timeout=deadline_seconds)` (line 166).

Measured on ned-box on 2026-10-14 between about 04:55Z and 05:05Z UTC, at main `85ad6555`, in a scratch copy of the two files whose program printed the time since its own start at each step, and whose test printed each invocation's elapsed time:

| Load added during the test | Time before `Popen` | Deadline passed | Program stopped Codex | Test's elapsed time |
|---|---|---|---|---|
| none (load average about 11 on 16 cores) | 2.86 s | 5.86 s | 5.86 s | 5.89 s |
| 24 Python busy loops | 5.61 s | 8.61 s | 8.61 s | 8.74 s |
| 16 Python busy loops and 8 loops of the same `find` | 19.02 s | 22.02 s | 22.04 s | 22.15 s |

In every measurement, stopping Codex after the deadline took at most 0.02 seconds: the SIGTERM path in `stop_process_group` is not where the time goes. The `find` alone, timed by hand with no added load, took 2.84 seconds (1.10 s user, 1.73 s system) and visits 827,219 entries; the home directory, the log-store `/home/nedlern/nedschorus-logs/` and `~/.claude/projects` are on one file system, so `-xdev` excludes none of them. One `find` timed while 16 others ran took 4.62 seconds.

So the case's real limit is: the scan, plus the 3-second deadline, must finish within 30 seconds. The measurements reached 22 seconds, not 30; that the scan accounts for the whole 30 seconds in the recorded failures below is inferred, not measured. The inference rests on the other case that failed with it: in three of the four recorded failures, the case "Codex's stdin is closed even when the caller's stdin is an open pipe" (line 230) failed too, with `completed None`, meaning its own 30-second `subprocess.run` timeout expired. That case has no deadline and no stop path: its fake `codex` reads stdin to the end and exits. It can take 30 seconds only if the program's start, before `Popen`, does.

## Where it failed

Four agent-seats on ned-box saw the case fail on 2026-10-14 UTC, each in `scripts/run-all-test-suites.py` before opening a pull request that changes neither `scripts/run-codex-task-from-brief.py`, `scripts/run-codex-task-from-brief-test.py` nor `nc-systems/cold-read/cold-read-cell-common.py`; each pull request's description reports the failure (`gh pr view <number> --repo nedschorus/nedschorus --json body`). In each, the exit code (1) and the deadline message were right; only the time failed:

- 01:31Z, 33.1 s, pull request [#1317](https://github.com/nedschorus/nedschorus/pull/1317): `nedlern@ned-box:/home/nedlern/nedschorus-logs/transcripts/ned-box/projects/-home-nedlern-agents-agent-instructions-editor/acc8171b-7215-4bb7-8adc-6b4bb55f9a8d/subagents/agent-ae7d5a16624dc525c.jsonl`. The stdin case passed.
- 01:38Z, 36.4 s, pull request [#1318](https://github.com/nedschorus/nedschorus/pull/1318): `nedlern@ned-box:/home/nedlern/nedschorus-logs/transcripts/ned-box/projects/-home-nedlern-agents-reboot-test/13be3b1b-2966-4c0d-83ad-3d3738bc2df2/subagents/agent-aebf11e91d23cca23.jsonl`. The stdin case failed.
- 01:44Z, 35.7 s, pull request [#1319](https://github.com/nedschorus/nedschorus/pull/1319): `nedlern@ned-box:/home/nedlern/nedschorus-logs/transcripts/ned-box/projects/-home-nedlern-agents-cold-read-improvement/d20a97c0-cfe8-4fb4-8863-e75f07c3484f/subagents/agent-a811be0fbe09f92ce.jsonl`. The stdin case failed.
- 01:52Z, 32.9 s, pull request [#1320](https://github.com/nedschorus/nedschorus/pull/1320): `nedlern@ned-box:/home/nedlern/nedschorus-logs/transcripts/ned-box/projects/-home-nedlern-agents-fleet-restart-at-login/c1b8aa3a-c1aa-4e9f-bddc-28d39a7c20ba/subagents/agent-a0b8f531d254ed275.jsonl`. The stdin case failed.

In each transcript, the failure is the line that begins `FAIL  the deadline stops Codex`. One failure spreads to the next agent-seat: `scripts/run-all-test-suites.py --only-suites-whose-recorded-inputs-changed-since origin/main` selects a suite again when "its last recorded run did not pass" (line 1799 on main), so once one agent-seat's test run fails the suite, the next agent-seat's test run on ned-box selects it too, whatever that agent-seat changed.

Search receipt: on 2026-10-14 at about 05:00Z UTC, `grep -rlE` for the failing lines of the two cases above and of "the deadline also kills a process Codex started that ignores SIGTERM", over `/home/nedlern/nedschorus-logs/`, found the four transcripts above, and three others that do not report this failure: two transcripts of merge-lane-2's review of pull request [#1246](https://github.com/nedschorus/nedschorus/pull/1246) that ran the test against deliberately broken copies of the program, and one Mac transcript that ran the test against an older version of the program on purpose. None of the six logs of this suite under `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/hr/*/tmp/*/logs/` holds a `FAIL` line, so no head test run has failed on the case so far.

## Why it matters

The case fails on a busy ned-box for a reason unrelated to the deadline it tests, so each agent-seat that runs the affected suites before opening a pull request gets a failure it must investigate, rerun and explain in its pull request; four did so within 21 minutes. A head test run on a busy ned-box runs suites in parallel under the same conditions, and a failing head test run blocks a merge.

The scan also slows every real use of the program: every invocation of `scripts/run-codex-task-from-brief.py` walks the whole home directory before Codex starts, as do the other callers of `codex_credential_denying_permission_profile_arguments` or `credential_files_found_now` on main: `scripts/code-review-codex-cell.py`, `scripts/sanity-check-attacks.py`, `nc-systems/cold-read/cold-read-codex-cell.py` and `nc-systems/cold-read/cold-read-agy-cell.py`. Within the test itself, each of the 11 invocations of the program that reach `codex_command` scans the home directory again: about 3 seconds each with no added load, about 31 of the suite's 39 seconds in one measured test run.

## Next action

The program and its test came from pull request [#1246](https://github.com/nedschorus/nedschorus/pull/1246), written by the Mac agent-seat cold-read-research. That agent-seat, or the agent-seat merge-lane-2 assigns, changes the two test cases so that the duration of the credential file scan cannot fail them. For the deadline case, one way is to measure only the time from the deadline to the program's exit, for example from the moment the program's stderr says the deadline passed, instead of the whole invocation. The stdin case's 30-second limit only stops a program that waits on stdin forever; a larger limit would still fail under a slower scan, so the same approach fits it: measure from a point after the scan, or make the limit count only the time after Codex starts.

Whether the scan itself should cost less is a separate decision, because the scan runs in every real use too and a change to `credential_files_found_now` reaches the other callers named above. Ways to make the scan cheaper include skipping the log-store and other directories that hold no credentials, or keeping the scan's result between invocations. The agent-seat that fixes the test cases says in its pull request whether it changed the scan or filed that question as its own GHI.

## Done when

`scripts/run-codex-task-from-brief-test.py` holds a new test case that runs the deadline case's invocation and the stdin case's invocation with a fake `find` first on the PATH the test passes to the program, only for those two invocations: the fake sleeps 31 seconds and then runs the real `find` with the same arguments. The new case passes, which shows that the scan's duration no longer counts against either case's time limit; the same fake makes the two cases fail as they are written on main at `85ad6555`. The scan runs only on Linux, so on the Mac the new case may print SKIP. `python3 scripts/run-codex-task-from-brief-test.py` passes on ned-box.

## Outcome

Done. PR [run-codex-task-from-brief test: deadline and stdin cases time from Codex's start, so the credential-file scan counts against neither limit](https://github.com/nedschorus/nedschorus/pull/1362) merged on 2026-10-14 as `5bb66448`. Its commit `84d5b6fa` times the deadline and stdin cases from Codex's start. It also runs each of them a second time with a fake `find` that sleeps 31 seconds and then runs the real `find`, on Linux only, and prints SKIP elsewhere: `scripts/run-codex-task-from-brief-test.py` lines 94 to 100 and 322 to 329 on main at `fbcfbde5`. Commit `f1b23e45`, merged in PR [run-codex-task-from-brief test: cases for the start-line wait limit and the timeout cleanup; the cleanup now kills both process groups](https://github.com/nedschorus/nedschorus/pull/1364), adds cases for the start-line bound and for cleanup after a timeout. Agent-seat reboot-test reported to merge-lane-2 on 2026-10-15 that the test file passed 20 of 20 runs on ned-box under the load this GHI describes, on main at `f7038068`.

## Related

GHI [#1112](https://github.com/nedschorus/nedschorus/issues/1112) collects test cases that fail on a busy machine because a time limit runs out. This case is one of that kind, but its cause is named: the time goes to a scan the program runs on every invocation, not to the behaviour the case tests, so a longer limit alone would hide a cost real use also pays. GHI [#1233](https://github.com/nedschorus/nedschorus/issues/1233) is a different intermittent test failure, in the signal sandbox test.
