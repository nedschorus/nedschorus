---
issue: "[Mutation testing before push mutates only failure-handling code without repository-wide checks, and a daily full mutation pass mutates every changed line](https://github.com/nedschorus/nedschorus/issues/2135)"
kind: design
---

# Mutation testing before push mutates only failure-handling code without repository-wide checks, and a daily full mutation pass mutates every changed line

## What is wrong

`scripts/pull-request-mutation-testing-survivors.py` runs mutation testing with cosmic-ray on the lines a pull request changed. For each changed Python file that is not itself a test suite, it makes mutants on the changed lines, and tests each mutant with the suites its function `suites_for_file()` selects: every test suite whose last recorded run, kept by `scripts/run-all-test-suites.py`, exited 0 and read the file, plus the file's sibling `<name>-test.py` or `<name>-test.sh` in the same directory when there is one.

Here a repository-wide check means a test suite that checks one rule across a whole class of the repository's Python files, such as every program under `scripts/` and `nc-systems/`, and so reads every file of that class. Its recording therefore includes nearly every module, and `suites_for_file()` selects it for nearly every mutant of every module. In the measured run below, six were selected for every mutant of both modules:

- `scripts/code-comments-carry-no-history-markers-test.py`
- `scripts/edited-file-path-within-checkout-root-and-git-check-ignore-defined-once-test.py`
- `scripts/every-repository-program-help-option-test.py`
- `scripts/git-redirecting-environment-variables-defined-once-test.py`
- `scripts/python-files-carry-no-try-except-pass-ruff-s110-test.py`
- `scripts/supervisor-file-names-defined-once-test.py`

A seventh suite, `nc-systems/cold-read/tests/cold-read-codex-cell-test.py`, was selected for both modules too, although it checks no rule across files: its recording on ned-box, in `~/.cache/nedschorus-test-suite-recorded-inputs/`, includes all 329 Python files git tracks, and why it reads them was not found. So a recording alone cannot tell a suite that tests a module from a suite that only reads it.

Before every push, the rule in CLAUDE.md on failure-handling code is applied today by running the script, and the script mutates every changed line, not only the failure-handling code the rule names. A new module, or a large change, gives hundreds of mutants; each mutant that no suite kills runs every selected suite.

## Measurements

On 2026-10-27, on ned-box, one invocation of `scripts/pull-request-mutation-testing-survivors.py` mutated two modules, at a load average of 15.7 on 16 cores. The head commit was `5104fd789413d5c3b1461c54943d5c4098428faa`, on the topic branch `user-alerts-reach-user-as-approval-walk-items-first-build-slice-topic-branch` in ned-box's clone, not pushed; the base, the merge base with main, was `28205cb9574bbf604596f53777bd59c375246886`. Each module's suites ran one after another, in the order below, stopping at the first that failed.

- `nc-systems/general-tools/user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py`, the shared module of the user-alerts build-slice, new in that change and not on main on 2026-10-28, where it is in the open pull request [User alerts reach the user as approval-walk items, first build-slice](https://github.com/nedschorus/nedschorus/pull/2084), here called the alerts module: 248 mutants in about 13 minutes, each tested with 11 suites: `cold-read-codex-cell-test.py`, the module's own test, three other suites that read the module, and the six repository-wide checks.
- `nc-systems/handoff/handoff-agent-seat-died-without-session-handoff-restart-watcher.py`: 36 mutants, each tested with 10 suites: `cold-read-codex-cell-test.py`, two other suites that read the module, the module's own test, and the six repository-wide checks.

Each module's own test is in a `tests/` directory beside the module, such as `nc-systems/general-tools/tests/user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common-test.py`, so the sibling rule does not find it; `suites_for_file()` selected it only because its recording read the module.

The data are in the log-store directory `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/fleet-restart-at-login/mutation-testing-suites-per-mutant-measurement-2026-10-27/`: cosmic-ray's result databases (`*.sqlite`), configurations (`*.toml`) and suite chains (`*.test-command.sh`) for both modules, copied from that invocation's scratch directory; the two files of results named below, both in that directory; and the two scripts that produced them, `mutation-testing-cosmic-ray-results-tally-of-killing-suite-per-mutant.py` and `mutation-testing-test-suite-chain-seconds-per-suite-on-unmutated-code-timer.py`, which read that scratch directory under `/tmp/` and so run only while it exists.

Which suite killed each mutant, from the result databases (the log-store directory's `mutation-testing-two-modules-test-suite-chain-killed-and-survived-mutant-counts-per-suite.txt`):

- Alerts module: the module's own test, second in the chain, killed 235 of the 248 mutants. The other 13 survived: all 11 suites passed.
- Watcher module: the module's own test, fourth in the chain, killed all 36 mutants.

So in this invocation no repository-wide check killed a mutant that the other suites let survive. That is a result for these two modules, not a proof for every module: `every-repository-program-help-option-test.py`, for one, could kill a mutant in a program's argument parsing.

Seconds each suite of the alerts module's chain took on the unmutated code, run in the same test sandbox as a mutant, median of three rounds at a load average of 10 to 12 (the log-store directory's `mutation-testing-user-alerts-common-module-test-suite-chain-seconds-per-suite-on-unmutated-code-three-rounds.txt`, where `suite00.sh` to `suite10.sh` are the chain's suites in the order of the list above, with the six repository-wide checks in alphabetical order):

| Suite | Seconds |
|---|---|
| `cold-read-codex-cell-test.py` | 1.34 |
| the module's own test | 0.10 |
| the three other suites that read the module | 0.37, 1.26 and 1.27 |
| `code-comments-carry-no-history-markers-test.py` | 14.60 |
| `edited-file-path-within-checkout-root-and-git-check-ignore-defined-once-test.py` | 0.76 |
| `every-repository-program-help-option-test.py` | 3.32 |
| `git-redirecting-environment-variables-defined-once-test.py` | 2.53 |
| `python-files-carry-no-try-except-pass-ruff-s110-test.py` | 0.18 |
| `supervisor-file-names-defined-once-test.py` | 1.09 |

The whole chain took about 26.8 seconds; the six repository-wide checks took 22.5 of them. Multiplying these times by the mutant counts, a computation rather than a measurement, accounts for about 11.5 of the 13 minutes: 235 killed mutants at about 1.4 seconds each, `cold-read-codex-cell-test.py` and then the module's own test, about 5.6 minutes; and 13 surviving mutants at about 26.8 seconds each, about 5.8 minutes, of which the repository-wide checks took about 4.9. The rest is cosmic-ray's own work per mutant and the higher load during the invocation.

Pull request [Mutation testing survivors: run each mutant's suites through run-all-test-suites, and report a baseline timeout as a timeout](https://github.com/nedschorus/nedschorus/pull/2031), merged on 2026-10-28, builds GHI [Baseline timeout in mutation testing of a module with many dependent test suites is reported as failing suites](https://github.com/nedschorus/nedschorus/issues/2004): each mutant's suites run in parallel through `scripts/run-all-test-suites.py`, under the machine's admission of test suites, stopping at the first failing suite. So the suite time of a surviving mutant is now about that of its slowest suite: 14.6 seconds with the repository-wide checks, 1.34 seconds without them, and 1.27 seconds with `cold-read-codex-cell-test.py` left out too, as item 1 of The change leaves it out. Each mutant also pays the runner's start-up and any wait for admission, which the pull request's description measures and which leaving suites out does not shorten, except that six fewer suites wait for admission on a machine that is often fully loaded.

## Why it matters

CLAUDE.md's rule, as applied before every push, makes an author wait for the whole pass, 13 minutes for the alerts module on a loaded ned-box, while every other agent-seat's test runs share the machine with it. GHI [Mutation testing of a module with many dependent test suites fails before any mutant runs](https://github.com/nedschorus/nedschorus/issues/1939) and GHI [Baseline timeout in mutation testing of a module with many dependent test suites is reported as failing suites](https://github.com/nedschorus/nedschorus/issues/2004) came from the same cost: a module that many suites read.

## The user's approval

On 2026-10-27 the user approved items 1 and 2 of The change below, as they were proposed to him, in these words: "We can certainly run fewer suites per mutant. The repository-wide checks. Maybe that becomes a daily maintenance thing or something like that. Could be a little more frequently if that's useful. And your quick pass, full pass idea that needs a change is a Claude rule, that looks good too."

On 2026-10-28 he ruled on the wording of The change, in approval-walk mutation-testing-two-passes-dangling-path-citation-check-bare-names-and-agent-facing-message-pointer-approval-walk-2026-10-28 (minutes: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/mutation-testing-two-passes-dangling-path-citation-check-bare-names-and-agent-facing-message-pointer-approval-walk-2026-10-28-minutes.md`):

- Item 1's first sentence, which suites test each mutant in the quick mutation pass (the walk's items 2 and 2.1). He answered the sentence first proposed, "Approve. This one's kind of complicated for me, which I guess means that you should probably check it with an advisor. So I guess AA.", where AA means approve after a check by the advisor, a stronger reviewer model the agent-seat can consult. That check found that the sentence kept `cold-read-codex-cell-test.py` in every mutant's suites, against his 2026-10-27 answer dropping the repository-wide checks. He asked: "Why don't you just move the mutants that check, that are effectively repository-wide checks, into the repository-wide checks, instead of creating an exception?", where by "the mutants that check" he meant such suites. He then approved the sentence item 1 now begins with, which also leaves out every suite whose last recorded run read every tracked Python file (2026-10-28 14:24).
- Item 2, one script makes both passes (the walk's item 4): approved at 15:12, in these words: "It seems like one program can handle both passes. That seems reasonable. And if you're saying the name is becoming obsolete, I'm happy to rename it." Item 4 is that rename.
- Item 3, CLAUDE.md's wording (the walk's item 3): approved as obvious at 14:43, the short wording item 3 quotes, which names the program and its quick mutation pass and leaves out the full mutation pass. Of its case against, that an agent reading only CLAUDE.md does not learn of the daily full mutation pass, he said: "The objection or the case against is weak because it's yet another case where a short delay doesn't make any difference typically and can easily be corrected."
- Item 2's task for each surviving mutant, which asks for a test that kills the mutant or a recorded reason why no test can (the walk's item 5): approved at 17:21.
- Next action's sentence that the agent-seat building the change settles the deferred decisions (the walk's item 6): approved at 17:25.
- Next action's measurement of both passes, recorded under Outcome (the walk's item 7): approved as obvious at 17:51.
- No glossary terms for the two passes (the walk's item 8): approved at 18:05. A terminology reviewer had proposed the project-terms mutation-testing-changed-failure-handling-lines-run and mutation-testing-all-changed-lines-run; both are declined, and "quick mutation pass" and "full mutation pass" stay plain words.

## The change

1. In the quick mutation pass of item 2, each mutant is tested with the suites `suites_for_file()` selects today, less the repository-wide checks and any other suite whose last recorded run read every tracked Python file, as `cold-read-codex-cell-test.py`'s does today. The repository-wide checks still run on the unmutated code: in the test run before a push whenever a file they read changed, as `scripts/run-all-test-suites.py --only-suites-whose-recorded-inputs-changed-since origin/main` selects them, and every day in `scripts/daily-full-test-run-of-main.py`, the maintenance-job that runs every suite on main once a day on each machine. The repository-wide checks chosen under the second deferred decision are tested against mutants only in the full mutation pass of item 2.
2. Mutation testing has two passes, both made by `scripts/pull-request-mutation-testing-survivors.py`, which mutates changed Python files only, as it does today:
   - The quick mutation pass, run before every push, mutates only the failure-handling code among the lines changed since the base the script is given, as today, such as an `except` block or an exit-code check, which is what CLAUDE.md's rule names. A surviving mutant there means the failure-handling code lacks a test, as a survivor does today.
   - The full mutation pass mutates every changed line, testing each mutant with the suites the quick mutation pass uses plus the repository-wide checks chosen under the second deferred decision. A maintenance-job runs it at least once a day, and opens a task for each surviving mutant, which asks the agent-seat it is given to, as the fifth deferred decision settles, to add a test that kills the mutant or to record why no test can.
3. The rule in CLAUDE.md, in the bullet that begins "Before pushing", currently says: "Code that handles a failure, such as an `except` block or an exit-code check, gets a test that causes that failure, checked by mutation testing." It names no pass and no program. The new wording keeps that requirement and adds one instruction, to run the program's quick mutation pass before pushing: "Code that handles a failure, such as an `except` block or an exit-code check, gets a test that causes that failure, checked by mutation testing: before pushing, run the quick mutation pass of `scripts/pull-request-mutation-testing-survivors.py`." In CLAUDE.md the sentence names the script by the new name item 4 gives it.
4. The build renames `scripts/pull-request-mutation-testing-survivors.py`, whose name says it works on a pull request, to a name that covers both passes, chosen by `docs/nedschorus-wiki/nedschorus-how-to-choose-a-name-for-files-code-and-glossary-terms.md`, and renames its test `scripts/pull-request-mutation-testing-survivors-test.py` to match. The same pull request updates every caller and every citation of the old names.

## Next action

Build on `scripts/pull-request-mutation-testing-survivors.py` as main has it: pull request [Mutation testing survivors: run each mutant's suites through run-all-test-suites, and report a baseline timeout as a timeout](https://github.com/nedschorus/nedschorus/pull/2031) merged on 2026-10-28, and item 1 changes the list of suites that the script, since that pull request, hands to `scripts/run-all-test-suites.py`.

Build items 1 to 4 in one pull request, since CLAUDE.md's new wording names the renamed script and its quick mutation pass: the quick mutation pass in the script and its tests in the script's test; the full mutation pass's maintenance-job and its tests; the rename of item 4; and the CLAUDE.md change, with the wording item 3 quotes. Settle each deferred decision below in the build, and state how in the pull request's description; put to the user first any that would change what the user sees or must do.

Then, on ned-box, run both passes on the alerts module's change, with `--head 5104fd789413d5c3b1461c54943d5c4098428faa --base 28205cb9574bbf604596f53777bd59c375246886`, or, if that head commit is no longer in ned-box's clone, with the head and base commits of the pull request that merged the alerts module; if no pull request merged it, with those of a merged pull request that adds a new Python module with failure-handling code, named in the Outcome. Record, under a new heading, Outcome, in this GHI's GHI-MD, which is `docs/issues/<this GHI's number>-….md` once create-GHI has filed it, through the edit-GHI operation of `scripts/ghi-issue-write.py`: the full mutation pass's time, mutant count and survivor count, against the 248 mutants, 13 survivors and 13 minutes above; and the quick mutation pass's time and mutant count, the cost a push now pays.

## Deferred-decisions

- How `suites_for_file()` tells a suite that tests the module from a repository-wide check: a list of the repository-wide checks kept in one place, a comment line in each such suite that says it is one, or a threshold on the share of tracked files its recording includes. Item 1, as the user approved it on 2026-10-28, settles part of this: a suite whose last recorded run read every tracked Python file is left out, whichever method tells the rest apart. Whether a repository-wide check tied to one module, such as `git-redirecting-environment-variables-defined-once-test.py`, stays in the quick mutation pass when that module is the one mutated.
- Which repository-wide checks can kill a mutant, and so run in the full mutation pass, and whether that pass runs more often than daily.
- How the quick mutation pass finds failure-handling code among the changed lines: the `except` blocks and the exit-code checks are the cases CLAUDE.md names; what else counts is the builder's to propose in the pull request's description. What the quick mutation pass prints and exits with when the changed lines hold no failure-handling code, and when a changed module has no suite once the repository-wide checks are left out, which the script reports today as `NO SUITE` and exit 1.
- Where the full mutation pass runs: as part of `scripts/daily-full-test-run-of-main.py` or as a maintenance-job of its own in `nc-systems/general-tools/scheduled-jobs-on-each-machine.json`; on ned-box only or on both machines; and where it finds cosmic-ray, which the script needs passed with `--cosmic-ray-venv`. Which changes it mutates: the pull requests merged since its last run, or the open pull requests; and what it does when one day's run is still going when the next starts.
- How the full mutation pass opens a task for each surviving mutant, and on whose task list: the author agent-seat of the pull request that changed the line, or merge-lane-2; where the task goes after the author agent-seat is ended by retire-seat; how a mutant that no test can kill is recorded so that later runs open no second task for it; and how a mutant already given a task is recognised on the next day.
- What the full mutation pass does with a mutant the script reports as ERRORED, an invocation that exits 2, and an invocation that does not finish, and where its own failure is reported so that an agent or the user sees it.
- The names of the quick mutation pass's flag, of the script and its test after item 4's rename, and of any new maintenance-job, chosen by `docs/nedschorus-wiki/nedschorus-how-to-choose-a-name-for-files-code-and-glossary-terms.md`.
