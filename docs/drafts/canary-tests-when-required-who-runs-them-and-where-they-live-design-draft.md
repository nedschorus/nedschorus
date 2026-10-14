# Design: canary tests, when one is required, who runs it, and where it lives

Status: draft for a cold read, then the user's approval-walk. Not yet decided where it says "Open question".

## What a canary test is

A canary test runs a real outside program, such as Codex, Claude Code, git, cron or launchd, with throwaway inputs, to check one behaviour of that program that the project's code relies on and that the project's own tests replace with a fake. The project's tests show that our code does what we meant when the outside program behaves as we assume; a canary test shows that the outside program does behave so, at the version installed on the machine that day.

Example: PR [Cold-read cells: the Codex reviewer can write a report outside its checkout, and a missing report says why](https://github.com/nedschorus/nedschorus/pull/1200) relies on Codex's `--add-dir` making one more directory writable without lifting the permission profile's deny rules on credential files. The cell's test runs a fake Codex, which cannot show that. The canary planted a random string in `probe.token` and `.env` in a new temporary directory, and in `inside-added-dir.token` in a second one, ran `codex exec` twice with `--add-dir` pointing at the second, once under the credential-denying profile and once under `--sandbox workspace-write` as a control, and passed when the profile run never showed the string, could still write into the added directory, and the control run did show it.

The project has run canary tests by hand for months, for Claude Code's launch prompt, Codex's permission profile, cron on the Mac, and launchd at login; each was written, run and thrown away by the agent that needed it, and nothing records where they are or when one is owed. This design settles that.

## When a canary test is required

A change needs a canary test when both hold:

- the change is correct only if an outside program behaves in a particular way, such as honouring a flag, denying a read, firing a hook, or running a scheduled job; and
- no test in the repository runs that outside program for real, because the tests replace it with a fake or do not reach it.

The author runs the canary test before asking for the merge, and a pull request reviewer who finds such a dependence untested asks for one, as a finding that blocks the merge. A change whose dependence an existing permanent canary test already checks needs none; a change that relies on an existing call whose behaviour no canary test checks needs one, like any other.

## The two kinds

**A permanent canary test** checks a behaviour of the project's own setup that must keep holding, so that a silent upgrade of the outside program that breaks it is found the next morning. Example: Codex's credential-denying permission profile, which every Codex cell relies on and which a Codex upgrade could change. A permanent canary test is a test suite in the repository, beside the code it protects, and the daily full test run, `scripts/daily-full-test-run-of-main.py`, runs it on each machine.

**A one-shot canary test** answers one question about an outside program at one version, for one change, such as PR 1200's `--add-dir` question. It is not kept in the repository. Its program, its transcript and its result are kept in the log-store for 30 days, and then deleted.

When the question a one-shot canary test answered must keep holding for the change to stay correct, the change's author turns it into a permanent canary test in the same pull request. A one-shot canary test stays one-shot when the change does not come to rely on the behaviour: the canary test showed the program does not behave so and the change took another route, or the change runs once, such as a migration.

## Who runs it, and how

Every canary test, of either kind, is a program, one Python file that ends by printing `RESULT: PASS` or `RESULT: FAIL` as its last line, and runs through one repository script, the canary runner, given the program's path and a time limit. The canary runner is not built yet; its file name is chosen when it is. The canary runner:

1. makes a throwaway home directory in a new temporary directory, and plants fake credentials in it: a random string in a file at each credential path that the project's deny rules name, such as `.ssh/id_canary` and `.config/nedschorus/canary.token`, and in `.env`; the canary test's program finds those strings by reading the planted files, which hold nothing real;
2. runs the canary test's program with `HOME` set to the throwaway home directory, while Codex and Claude Code can still reach their own login in the way open question 4 settles;
3. writes the whole run, every command and its output, to a transcript, and reads the program's last line; a program that ends without a `RESULT:` line, or is stopped at its time limit, has no verdict;
4. writes the record to the log-store on ned-box, over ssh when it runs on the Mac: for a one-shot canary test, the program, the transcript and a result file into the canary test's directory (below); for a permanent canary test, as open question 7 settles;
5. deletes the throwaway home directory and every temporary directory the run made, except that when the record could not be written it keeps the transcript and prints its path; and exits 0 on PASS, 1 on FAIL, and 2 when the run could not be made, gave no verdict, or its record could not be written, saying which.

A canary test never reads or lists a real credential file or directory. The canary runner's throwaway home directory is how that is kept: the canary test's program receives only the throwaway paths.

A Codex agent runs the canary runner outside Codex's own sandbox, because that sandbox would otherwise wrap the outside program under test and change what the canary test sees; a canary test of a sandbox, for instance, must start its program with the sandbox settings the test chooses. The user allows the canary runner, and nothing else, to run outside Codex's sandbox by one permission rule on each machine; no such rule exists yet on either machine, and its form is open question 3. A Claude Code agent-session runs the canary runner directly. Neither runs a canary test any other way.

## Where canary tests live, and their names

**Permanent:** one file in the repository, the canary test's program, in the same directory as the code it protects, named `<the code it protects>-canary-test.py`; the first, for example, would be `nc-systems/cold-read/cold-read-codex-cell-credential-deny-canary-test.py`, which does not exist yet. How the test runner starts it through the canary runner is open question 2.

**One-shot:** a directory in the log-store, `nedlern@ned-box:/home/nedlern/nedschorus-logs/canaries/canary-temp-<YYYY-MM-DD>-<subject>/`, where the date is the day the canary test ran, in the local time of the machine that ran it, and the subject names the outside program and the behaviour, such as `canary-temp-2026-10-12-codex-add-dir/`; a second run with the same date and subject adds `-2`, then `-3`. The directory holds the canary test's program, its transcript and its result. The date in the name is the only record of its age: no database table, and no index file.

## How a result is reported

**One-shot:** the author posts the result on the pull request that needed it, as a comment that says PASS or FAIL, the machine, the outside program's version, what was run and what was seen, in a table when there is a control run, and cites the transcript in the log-store. PR 1200's comment is the model.

**Permanent:** the daily full test run's record, `nedlern@ned-box:/home/nedlern/nedschorus-logs/daily-full-test-runs/<machine>/<YYYY-MM-DD>.txt`, like any other test suite. A FAIL there means the outside program changed under the project; whoever reads the daily record tells the user, with the outside program's version before and after when the transcript shows it.

## How a canary test is removed

A one-shot canary test's directory is deleted 30 days after the date in its name, by the mechanism open question 1 settles. A permanent canary test is removed like any test suite, in a pull request that says why the behaviour no longer matters.

## Open questions

1. **What deletes the one-shot directories.** Recommendation: a scheduled job on ned-box, listed in `nc-systems/general-tools/scheduled-jobs-on-each-machine.json`, that deletes each `canaries/canary-temp-<date>-*` directory more than 30 days old and prints what it deleted, because deleting by a date in a name needs no agent. The alternative is a job of the daily maintenance step of GHI [Daily maintenance in one daily step, starting with a daily check of every wiki page](https://github.com/nedschorus/nedschorus/issues/1058), which an agent-session runs.
2. **How the permanent canary tests fit the test runner.** A canary test needs the real outside program, its login and, for Codex and Claude Code, a share of the day's model limit. `scripts/run-all-test-suites.py --only-suites-whose-recorded-inputs-changed-since` would run one before every push that touches its inputs. Recommendation: the runner runs a suite named `-canary-test.py` only in the daily full test run and when asked for it by name, and skips it, saying so, in a selective run.
3. **The one permission rule.** Codex's rules file can allow a command prefix; which form lets the canary runner, and only the canary runner, start its program outside the sandbox has not been measured. Recommendation: measure it once, before the canary runner is built, with a canary test run by hand outside Codex's sandbox at the user's word for that one run, the way PR 1200's canary test was run.
4. **The real login under a throwaway home directory.** Codex and Claude Code read their login from under the home directory unless told otherwise. Recommendation: point Codex's and Claude Code's own configuration-directory variables at the real login, and plant fake credentials only under the throwaway home directory; check by a canary test that the outside program still runs and that the sandboxed commands still cannot read the real login.
5. **The weekly real Claude session check.** `nc-systems/handoff/uncommitted-work-snapshot-hook-real-claude-session-weekly-owner-check.py` is a permanent canary test in all but name, run weekly as its own scheduled job. Recommendation: leave it as it is until the canary runner exists, then decide whether it moves into the daily full test run.
6. **The first permanent canary test.** Recommendation: Codex's credential-denying permission profile, with PR 1200's `--add-dir` case and the profile placement after `review` that GHI [The Codex review cell's commands run writable and without credential denials, because `codex exec review` drops the cell's permission profile](https://github.com/nedschorus/nedschorus/issues/804) measured, because every Codex cell relies on it and Codex upgrades itself.
7. **Where a permanent canary test's transcript is kept.** The daily full test run's record says PASS or FAIL, but comparing an outside program's version before and after a FAIL needs earlier transcripts. Recommendation: the canary runner writes each run's transcript to `nedlern@ned-box:/home/nedlern/nedschorus-logs/canaries/permanent/<machine>/<YYYY-MM-DD>-<suite>.txt`, deleted after 30 days by the same mechanism as the one-shot directories.
8. **Canary tests of cron and launchd.** The canary runner runs one program and waits for it; cron and launchd run a job later, outside that program. Recommendation: such a canary test installs a throwaway job that writes a file, waits for the file within its time limit, and removes the job whatever happens.
