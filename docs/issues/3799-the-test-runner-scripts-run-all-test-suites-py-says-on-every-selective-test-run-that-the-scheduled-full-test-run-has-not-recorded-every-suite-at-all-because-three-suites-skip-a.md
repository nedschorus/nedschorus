---
issue: "[The test runner `scripts/run-all-test-suites.py` says on every selective test run that the scheduled full test run has not recorded every suite at all, because three suites skip a case without the mark and so never get a list of the files only strace saw](https://github.com/nedschorus/nedschorus/issues/3799)"
---

# The test runner `scripts/run-all-test-suites.py` says on every selective test run that the scheduled full test run has not recorded every suite at all, because three suites skip a case without the mark and so never get a list of the files only strace saw

## Reproduction

Run on ned-box on 2026-11-16, in a detached worktree of origin/main at e43c12cf02d1bcd731cebae13407fbe5585e74a1. The script below imports `scripts/run-all-test-suites.py`, loads each suite's list of the files only strace saw from the default directory, `~/.cache/nedschorus-test-suite-recorded-inputs/c8652c93ef1c27e3/`, and calls the function that prints the notice, `suites_with_missing_or_stale_files_only_strace_saw_list_notice_or_none`, as a selective test run does:

```python
import datetime, importlib.util, pathlib, sys
top = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("rats", top / "scripts/run-all-test-suites.py")
rats = importlib.util.module_from_spec(spec); spec.loader.exec_module(rats)
directory = pathlib.Path.home() / ".cache/nedschorus-test-suite-recorded-inputs/c8652c93ef1c27e3"
suites = rats.suites_listed_by_git(top)
kept = {s: rats.load_files_only_strace_saw(directory, s) for s in suites}
python_suites = [s for s in suites if not rats.is_shell_test_suite(s)]
print("Python suites:", len(python_suites))
for s in python_suites:
    if kept[s] is None:
        print("no list:", s)
now = datetime.datetime.now(datetime.timezone.utc)
print(rats.suites_with_missing_or_stale_files_only_strace_saw_list_notice_or_none(suites, kept, directory, now))
```

Its output, with the script saved as `repro.py` and run as `python3 repro.py <worktree>`:

```
Python suites: 250
no list: nc-systems/cold-read/tests/cold-read-agy-cell-test.py
no list: nc-systems/general-tools/tests/agent-seat-task-list-task-file-rewrite-common-test.py
no list: nc-systems/general-tools/tests/install-scheduled-jobs-on-this-machine-after-reference-checkout-merge-and-report-install-failure-as-task-for-installer-owner-agent-seat-test.py
no list: nc-systems/handoff/tests/handoff-write-and-check-supervisor-test.py
no list: scripts/claude-code-session-transcript-records-read-backward-common-test.py
no list: scripts/design-ghi-md-approval-walk-minutes-and-cold-read-records-user-turns-with-file-and-line-extract-test.py
scripts/run-all-test-suites.py: 6 of 250 suites have no list of the files only strace saw them read from the last 36 hours in /home/nedlern/.cache/nedschorus-test-suite-recorded-inputs/c8652c93ef1c27e3, so this selective run does not select such a suite when the change edits a file the suite reads only through git or a shell script. scripts/scheduled-full-test-run-of-main.py makes those lists once a day on ned-box, so it has not recorded every suite at all. The verdicts of the suites this run ran stand; carry on with your work.
If you have not yet told the user in this agent-session that the scheduled full test run's lists are stale: tell him "The scheduled full test run on ned-box has not recorded every suite at all, so selective test runs there can miss a suite whose git or shell reads changed. The scheduled run's records are in nedlern@ned-box:/home/nedlern/nedschorus-logs/scheduled-full-test-runs-of-main/ned-box/." A subagent passes that sentence to the agent that dispatched it instead.
```

Three of the six suites reached main after the scheduled full test run of 2026-11-15, which ran origin/main at 5eb94cd939e4a554e2584d16c2ee86ed920869cc and started at 2026-11-15T08:00:02Z: none of the commits that added them, f2bf2b7c7, bc9bbf20d and 25e39bf2f, is an ancestor of 5eb94cd93. The next scheduled run records them, as designed; until it does, any suite newly added to main is named by the notice, which is the notice working as meant.

The other three were in that run, and each skipped a case with a reason that does not carry the mark `[this machine cannot run it]`. Lines 5 to 7 of `nedlern@ned-box:/home/nedlern/nedschorus-logs/scheduled-full-test-runs-of-main/ned-box/2026-11-15.txt`:

```
nc-systems/cold-read/tests/cold-read-agy-cell-test.py: SKIP  the credential-file cases: they need the real sandbox program, which cannot start in the nc-test-sandbox; nc-systems/cold-read/tests/cold-read-agy-cell-real-sandbox-test.py runs them
nc-systems/handoff/tests/handoff-write-and-check-supervisor-test.py: SKIP  a running Claude Code session sets CLAUDE_CODE_SESSION_ID: this run is not inside a Claude Code session
scripts/claude-code-session-transcript-records-read-backward-common-test.py: SKIP  no real transcripts under ~/.claude/projects/ to compare
```

## Why the notice fires on every selective test run

`save_files_only_strace_saw` in `scripts/run-all-test-suites.py` keeps a suite's list only when `recorded_run_passed_and_skipped_only_cases_this_machine_cannot_run` holds: the run passed and every case it skipped carried the mark. These three suites skip an unmarked case in every scheduled full test run, so they never get a list, and the notice names them on every selective test run on ned-box.

The notice also overstates the gap. It writes "at all" when none of the suites lacking a fresh list has ever had one, however many other suites have one, so here it says the scheduled run "has not recorded every suite at all" when 244 of 250 suites have a list.

## Harm

The notice has become noise. Reviewers relayed it on pull requests 3792, 3793 and 3795 (reported by merge-lane-2; unverified here), and a notice that fires on every run will not be read when it reports a real gap, such as a scheduled run that stopped recording.

## Whether selective test runs actually miss these three suites

From reading `selection_reason` in `scripts/run-all-test-suites.py` and the recordings on ned-box on 2026-11-16, the answer differs between the three suites:

- `selection_reason` selects a suite whenever its own recording, the one the last run on that recorded-inputs directory saved, skipped an unmarked case. The recordings of `nc-systems/cold-read/tests/cold-read-agy-cell-test.py` and `scripts/claude-code-session-transcript-records-read-backward-common-test.py`, in both `~/.cache/nedschorus-test-suite-recorded-inputs/c8652c93ef1c27e3/` and merge-lane-2's head test run directory `/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/hr/store/c8652c93ef1c27e3/`, each record one skipped case and no marked one, so every selective test run selects them, and the missing list costs nothing for them today.
- `nc-systems/handoff/tests/handoff-write-and-check-supervisor-test.py` skips its case only outside a Claude Code session. Its recordings in both directories were made inside one and record no skipped case, so a selective test run can leave it unselected, and with no list it is not selected when a file it reads only through git or a shell script changes. For this suite the notice reports a real gap (unverified whether the suite reads any file only that way).

## What to do

The owner, reboot-test, which wrote this code in pull request 2607 (commits 10e0ca11c, 337adc6e4 and 8d41c96d7), decides the fix. Three parts:

1. Make the three suites get a list, or stop the notice counting a suite that a selective test run selects every time anyway. The mark `[this machine cannot run it]` does not fit these skips: the runner's docstring, section on skipped cases, reserves it for a skip "whose cause is the machine itself, its platform or what is installed on it", and none of the three skips has that cause; GHI [The daily full test runs tell the user about failures and about test cases that run nowhere or lack a tool, and every test suite prints a skipped test case in one format](https://github.com/nedschorus/nedschorus/issues/1206) lists the handoff suite's skip as "a test case skipped on both machines", which the daily full test runs never run. Options include: leaving out of the notice's count each suite whose recording skipped an unmarked case, since `selection_reason` already selects such a suite every time, so the notice counts only suites a selective test run can really miss; running the skipped cases in the scheduled full test run where that can be arranged; or keeping a list from a run whose unmarked skips are declared, in code with a test, to read nothing the other cases do not.
2. Make the notice's "at all", in both its sentence to the agent and its sentence for the user, say how many suites lack a list when other suites have one, instead of saying the scheduled run has recorded no suite.
3. Settle whether `nc-systems/handoff/tests/handoff-write-and-check-supervisor-test.py` reads any file only through git or a shell script, for example by running it under the test runner with `--record-inputs-with-strace` inside a Claude Code session and reading the list it saves; if it does, its missing list is a real selection gap today.
