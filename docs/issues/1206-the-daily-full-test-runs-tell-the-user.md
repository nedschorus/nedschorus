---
issue: "[The daily full test runs tell the user about failures and about test cases that run nowhere or lack a tool, and every test suite prints a skipped test case in one format](https://github.com/nedschorus/nedschorus/issues/1206)"
---

# The daily full test runs tell the user about failures and about test cases that run nowhere or lack a tool, and every test suite prints a skipped test case in one format

Every night `scripts/daily-full-test-run-of-main.py` runs every test suite on main, once on ned-box and once on the Mac, and writes a record to the log-store. The records list every failure and every skipped test case. No program reads them to the user. This GHI-MD proposes one check that reads both machines' records and tells the user about three things: any failure, any test case skipped because of something the machine lacks, and any test case skipped on both machines. The same check also reads each machine's latest record of the weekly work-snapshot owner check, and tells the user when that check failed or its record is missing. It also proposes one format for the line a test suite prints when it skips a test case, so that the check can tell those kinds of skip apart. The report reaches the user as one more job of the project's daily maintenance, GHI [Daily maintenance in one daily step, starting with a daily check of every wiki page](https://github.com/nedschorus/nedschorus/issues/1058), by the route the user chose on 2026-10-12, below.

## What happens today

- A test suite that cannot run one of its test cases prints a line opening `SKIP` and exits 0. `scripts/run-all-test-suites.py` finds such lines with the pattern `^SKIP\s` and says of them, in its manual: "A skip never changes a verdict; it is reported beside it." On origin/main at 76f289e8, 25 test suites print `SKIP` lines (`git grep -l 'SKIP' origin/main -- '*-test.py' '*-test.sh'`).
- `scripts/daily-full-test-run-of-main.py` writes `nedlern@ned-box:/home/nedlern/nedschorus-logs/daily-full-test-runs/<machine>/<YYYY-MM-DD>.txt`, holding every `FAIL` line and every skipped test case. The only program on main that names that directory besides the writer and its test is `nc-systems/cold-read/cold-read-record-ship.py` (`git grep -l 'daily-full-test-runs' origin/main`); the one design that reads the record, GHI [refresh-design: when a system's code lands, bring its design, build-slice plan and overview into line — removing, never revising](https://github.com/nedschorus/nedschorus/issues/670), reads only its runner exit code, and is not built.
- Every Sunday at 04:30 Pacific, `nc-systems/handoff/uncommitted-work-snapshot-hook-real-claude-session-weekly-owner-check.py` starts a real claude session on each machine and checks that the work-snapshot hook finds that session. The job is in `nc-systems/general-tools/scheduled-jobs-on-each-machine.json`, installed on ned-box by cron and on the Mac by launchd. Each run writes `nedlern@ned-box:/home/nedlern/nedschorus-logs/uncommitted-work-snapshot-hook-real-claude-session-weekly-owner-checks/<machine>/<YYYY-MM-DD>.txt`, which ends with the line `VERDICT: PASSED` or `VERDICT: FAILED`; the run's output is also appended to `~/.claude/weekly-uncommitted-work-snapshot-hook-real-claude-session-owner-check.log` on that machine. No program reads these records to the user either. The first run is due on 2026-10-18, so the directory does not exist yet.
- `CLAUDE.md`'s reporting rule makes a failure visible to whoever acts on a program's output. A skipped test case is not a failure, so nothing makes it visible to the user.

The records of 2026-10-11 show the three kinds of skip this GHI-MD separates. ned-box: "SUMMARY: 124 passed, 0 failed, 124 total; 6 cases skipped in 4 suites"; the Mac: "SUMMARY: 124 passed, 0 failed, 124 total; 15 cases skipped in 10 suites".

- **A test case that cannot apply on this machine**, and runs on the other one. ned-box: "scripts/recover-crashed-seats-test.py: SKIP  CHECKOUT: on the Mac, a recovery run from checkout A launches checkout B's launch-claude-mac: macOS only: launcher_path() is None off macOS". Harmless.
- **A test case that lacks something the machine could have.** ned-box: "nc-systems/handoff/tests/uncommitted-work-snapshots-test.py: SKIP a C program compiled with cc stands in for claude and runs the hook: no cc on PATH". The Mac: "scripts/search-file-argument-read-as-option-guard-hook-test.py: SKIP  rg reproduction: rg is not on PATH here", and "scripts/absence-claim-locator-reminder-hook-test.py: SKIP  labelled-reply precision: /home/nedlern/nedschorus-logs/seats/ned-box-helper/absence-claim-trigger-phrases-2026-10-05/out/precision/labels.csv is not on this machine". The commit that added the `cc` skip, b08e2490, says "ned-box has no cc" in its message, which is the only place it was said.
- **A test case skipped on both machines**, which the daily full test runs never run. Both machines: "nc-systems/handoff/tests/handoff-write-and-check-supervisor-test.py: SKIP  a running Claude Code session sets CLAUDE_CODE_SESSION_ID: this run is not inside a Claude Code session". This test case runs only when an agent runs the suite inside its own agent-session.

## Why

The user asked, on 2026-10-11, on learning of the `cc` skip: "why didn't they tell me? That is a serious question. What instructions let this slip", and, of the missing tool, here `cc`: "If the tool SKIP is missing, that is not just a skip." A test case skipped for a missing tool is a missing prerequisite on that machine, not a test that cannot apply there, and a test case skipped on both machines tests its behavior nowhere. Today both read the same as a harmless skip, in a record no one reads to the user. The same is true of a failure in a daily full test run.

The `SKIP` line also reads badly. In "SKIP a C program compiled with cc stands in for claude and runs the hook: no cc on PATH", nothing marks where the test case's name ends and its reason begins, and a reader can take "SKIP" for the thing that acts on "a C program".

## Proposal

1. **One format for a skipped test case.** Every test suite prints a skipped test case as:

   `SKIPPED test case "<name>"; reason: <reason>`

   and a reason that the test case cannot apply on this machine opens `not on this platform:`, as in `SKIPPED test case "the end-to-end sandbox-exec case"; reason: not on this platform: sandbox-exec exists only on macOS`. One small shared function prints the line, so the 25 test suites call it rather than each writing its own. `scripts/run-all-test-suites.py`'s pattern for a skipped test case (`SKIPPED_CASE_LINE`, `^SKIP\s`) changes to match, and so does `scripts/daily-full-test-run-of-main.py`'s (`RUNNER_SKIPPED_CASE_LINE`, `^(?:\S+: )?SKIP\s`), which copies skip lines into the record; without that second change the records would lose every skip. Their manuals and tests change with them. The runner already prefixes each line with `<suite>: `, so the suite path reaches the record without the shared function printing it.

2. **One check over both machines' records.** After both machines' daily full test runs have written their records for a day, a program reads the two records and reports:
   - every failure, and every step of a daily full test run that failed, such as a failed fetch or a lock never released;
   - every skipped test case whose reason does not open `not on this platform:`, such as a missing tool, a missing file, or a run outside an agent-session;
   - every test case skipped on both machines, whatever its reason, a test case being one suite path and one test case name; a test case that is both is reported once, under this heading.

   The check also reads each machine's latest weekly work-snapshot owner-check record and reports:
   - a record whose verdict is `VERDICT: FAILED`, with the record's `FAIL` lines, the same way it reports a failure of a daily full test run;
   - a machine whose latest weekly record is older than 8 days as a missing weekly record. The 8 days let a Sunday run that did not happen show up before the next Sunday run is due. A machine with no weekly record at all is reported missing from 2026-10-19, the day after the first run is due.

   A test case skipped on one machine as `not on this platform:` is not reported when the other machine's record does not list it as skipped and its suite passed there. A day with a record missing from either machine is reported as that.

3. **The report reaches the user as a daily job of GHI 1058.** When the check finds something to report, it makes the day's nightly-test-run job due, in the per-job, per-day state file that GHI 1058's ruled design keeps. When it finds nothing, it makes no job due, and the user sees nothing. How a due job reaches the user is the next section.

## What the design must settle

- When and where the check runs: the Mac's daily full test run waits for the Mac to wake, so the check must wait for both records or say how long it waits before it reports one missing.
- What starts the check (a scheduled job in `nc-systems/general-tools/scheduled-jobs-on-each-machine.json`, or the hook itself), where it keeps its report so that the hook can show it, and what happens to a due job when a missing record arrives later and clears it, given that only the user's answer completes or defers a job in GHI [Daily maintenance in one daily step, starting with a daily check of every wiki page](https://github.com/nedschorus/nedschorus/issues/1058).
- How a failed step of a daily full test run, such as a failed fetch, shows in the record.
- What happens to a `not on this platform:` skip when the other machine's test suite failed.
- Whether the check reports the record that did arrive when the other machine's record is missing, or waits for both.
- How the skip line handles a quote or a semicolon inside a test case's name.
- Whether a weekly failure or a missing weekly record makes the job due on each day until a newer weekly record clears it, or only on the first day the check finds it.
- The names and places of the shared skip function and of the check, by the rules of `docs/nedschorus-wiki/nedschorus-how-to-choose-a-name-for-files-code-and-glossary-terms.md`, and whether the check keeps its report in the log-store.

## Related GHIs

- GHI [Check every prerequisite of the fleet's programs before an agent-session starts](https://github.com/nedschorus/nedschorus/issues/1055) inventories the tools the fleet's programs need before an agent-session starts. A tool only a test suite needs, such as `cc` above, is outside that inventory; this check reports such a tool when a test case skips for it, and the user decides whether to install it.
- GHI [Every refusal and warning a program hands an agent says why and what to do instead](https://github.com/nedschorus/nedschorus/issues/956) sets the form of messages to agents; the skip line here is read by the user and by the check.
- PR [Work-snapshot test: a fake process tree replaces the four claude stand-ins; a weekly owner check runs the hook in a real claude session](https://github.com/nedschorus/nedschorus/pull/1212) added the weekly work-snapshot owner check that this check also reads. The user ruled on 2026-10-13, as item 21 of ned-box-helper's approval-walk fast-cold-read-of-agent-facing-prose-design-questions-2026-10-10 (minutes: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/fast-cold-read-of-agent-facing-prose-design-questions-2026-10-10-minutes.md`), that this check reads the weekly records rather than a separate program. The weekly check skips no test cases; the check reads its `FAIL` lines and `VERDICT:` line as they are.

Searched for an existing GHI covering the check or the format: ghi-info, asked on 2026-10-11, found none for either; it named GHI 1055 for tool prerequisites, covered above.

## How the report reaches the user (decided)

The user decided the route on 2026-10-12, as item 2 of prime-intellect's approval-walk prime-intellect-open-decisions-for-the-user-2026-10-12 (minutes: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/prime-intellect-open-decisions-for-the-user-2026-10-12-minutes.md` once shipped). He was shown this proposal: a hook runs on his first prompt of the day, in any agent-seat; if a daily job is due, the hook adds it to that agent's context; that agent shows it to him before anything else; the job is then marked shown, so other agent-seats do not repeat it; a night with nothing to report shows nothing. He answered: "Y - that souds like a good way to handle any maintenance issue, I don't know if we have any maintence GHIs or docs, but if we do, that should be added, and if we don't we need at least one."

The general mechanism belongs to GHI 1058, the project's daily-maintenance GHI, not to this one. Its section "How a daily job is handed to the user and tracked (decided)" already rules the state file per daily job per day, with the states due, shown, completed and deferred, and that only the user's answer marks a job completed or deferred. Its open question 1 asks how a due job reaches an agent-session that is already running; this route answers it, for every daily job: the user prompting an agent-session is the moment he is there to see it. GHI 1058's ruled design already moves the daily overview refresh reminder, `nc-systems/handoff/daily-overview-refresh-reminder-mark.py`, onto the same state files, so that reminder takes this route too.

This GHI builds the nightly test-run check and its job; the hook that shows due jobs on the user's first prompt of the day is built under GHI 1058, and this check is its first user if this GHI lands first. The search behind this section is `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/maintenance-items-reaching-the-user-search-2026-10-12.md`.

## Next action

Write the shared skip function and change the 25 test suites, `scripts/run-all-test-suites.py` and `scripts/daily-full-test-run-of-main.py` to the new format in one pull request, as proposal 1 says; then build the check over both machines' daily full test run records and latest weekly work-snapshot owner-check records, which makes the day's job due in GHI 1058's state file, in a second; the hook that shows due jobs on the user's first prompt of the day is built under GHI 1058.
