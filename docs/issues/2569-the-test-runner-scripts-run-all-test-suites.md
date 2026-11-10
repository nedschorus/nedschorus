---
issue: "[The test runner `scripts/run-all-test-suites.py` reruns suites whose recorded inputs did not change, because it keeps one recording per suite for every branch and selects every suite that runs a content-reading git command on the checkout](https://github.com/nedschorus/nedschorus/issues/2569)"
---

# The test runner `scripts/run-all-test-suites.py` reruns suites whose recorded inputs did not change, because it keeps one recording per suite for every branch and selects every suite that runs a content-reading git command on the checkout

## What this GHI asks for

A design, then a build, that stops the test runner, `scripts/run-all-test-suites.py`, from running a suite in a selective test run when nothing the suite reads has changed. Two of the runner's selection reasons pick suites that way today, and together they took 39% of the run-seconds of merge-lane-2's head test runs from 2026-11-01 to 2026-11-04.

### Reason 1: one recording per suite, shared by every branch

The runner records the files each suite reads while it runs, with two recorders, a Python audit hook and, on ned-box, strace, and keeps that recording under `--recorded-inputs-directory`, keyed by the repository's root commit, one file per suite, shared by every clone and worktree on the machine (the runner's docstring, section RECORDED INPUTS, and `recordings_directory_for`). Every run replaces the recordings of the suites it ran. So when a run on branch X records a suite, a run on branch Y finds a recording whose file contents are X's. The runner then cannot tell what the suite reads on Y, and selects it with the reason "its recording read another copy of <file> than the checkout holds, so what it reads here is unknown" (`selection_reason`).

Example: merge-lane-2's head test run of one pull request records `nc-systems/skills/explain/tests/explain-reply-cold-read-fast-read-test.py` while that pull request's copy of a cold-read file differs from main. The next head test run, of a pull request that touches nothing that suite reads, selects it anyway. That suite was selected this way 77 times in the three days.

Measured: this reason selected 24% of head-run seconds, up to 119,000 suite-seconds over 2026-11-01 to 2026-11-04.

The change to design: keep several recordings per suite, each a file of its own, check them one by one, and do not select a suite when any one of its recordings matches the checkout in everything it saw (the files it read, the paths it looked for and the directories it listed) and none of that changed since COMMIT, the commit the selective test run compares against (`--only-suites-whose-recorded-inputs-changed-since`).

### Reason 2: a suite that runs a content-reading git command on the checkout is selected by every change

When a suite runs a git command on the checkout that reads file contents, such as `git status`, `git diff` or `git clone` of the checkout, the runner selects it whenever any file differs, because git reads committed content from the object store, where neither recorder sees a working file (`selection_reason`, the reason "it runs git … on the checkout, which reads files no recorder here saw").

Measured: 749 suite-runs and 75,745 suite-seconds, 15% of head-run seconds, over the same three days. Most came from seven suites, among them `nc-systems/general-tools/tests/bash-guards-verdict-changes-between-two-git-refs-on-transcript-recorded-commands-check-test.py`, whose median run is 430 seconds; it ran in all 230 head test runs and used 17.5% of all suite CPU.

The options to weigh in the design, which can be combined:
1. Each such suite runs git on a fixture repository it builds, instead of on the checkout, so it no longer runs git on the checkout and the runner selects it by its recorded files alone. This helps only the suites rewritten, and only where the fixture still holds what the test checks; a suite that needs the real checkout stays selected by every change.
2. The recorder learns which paths a git command can read from its arguments, such as `git show <ref>:<path>` or a pathspec after `--`, and treats a whole-tree command such as `git status` as reading every tracked file, so a suite running `git status` stays selected by every change; it does not help a suite that clones the checkout, such as the bash-guards suite above, which needs option 1.

## Why

The user ruled on 2026-09-30 that a suite is rerun only when a file it reads has changed: test result caching keyed on inputs recorded while the suite runs (approval-walk open-questions-concerns-and-recommendations-2026-09-30, item 5, "y both", quoted in the runner's docstring, section RECORDED INPUTS). Both reasons above rerun suites whose files did not change. On 2026-11-04 the user asked "Build what we need to test faster" (approval-walk reboot-test-worktree-review-direction-2026-11-03, item 4.1). A head test run's suites wait 19 times their own run time to start, because about seven test runs run at once on ned-box and the runner starts a suite only while CPU is under 90%; every needless suite-run adds to that wait.

## What needs judgment and what is code

Code, once the design sets the rules: matching recordings to the checkout, storing several recordings per suite and dropping old ones, and option 2's mapping from git commands to paths. Judgment, in the design: how many recordings to keep and which to drop first, and which options to build. Judgment, per suite: for option 1, whether a fixture repository keeps the suite's assertions meaningful, decided by the agent that rewrites it.

## Proposed design, awaiting the user's ruling

This section proposes a design for the two reasons above. The user has not ruled on it; the build waits for his ruling, which comes to him as an item of an approval-walk of agent-seat reboot-test. Until then, the sections above stand as filed, and the line `kind: design` is not added.

### What changed since filing

Reason 1, measured again: in the latest test run of each of the 21 pull requests merge-lane-2 test-ran from 2026-11-05 to 2026-11-06T07:01Z, leaving out the test runs that ran every nc-test-suite, the reason selected 37% of the run-seconds, against 24% from 2026-11-01 to 2026-11-04.

Reason 2: `nc-systems/general-tools/tests/bash-guards-verdict-changes-between-two-git-refs-on-transcript-recorded-commands-check-test.py` now runs its git commands on a test fixture repository it builds from the checkout's files (`make_test_repository` in that file), and merge-lane-2's test runs of pull requests 2686 and 2687 on 2026-11-06 did not select it. In the same 21 test runs, the reason selected 4.3% of the run-seconds, in the four nc-test-suites of the table under Part 2.

Measured from the PASS and FAIL lines of nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/hr/pr*/stderr, the latest test run of each pull request, leaving out test runs where a file under `EVERY_SUITE_RUNS_WHEN_THESE_CHANGE` differed. Pull request 2544 was replaced by [pull request 2684](https://github.com/nedschorus/nedschorus/pull/2684), which merged on 2026-11-06 as a4cf4060b; it changed `selective_test_run_selection_without_no_sandbox_suites`, which runs after `suites_selected_since` and is untouched by this proposal.

### Part 1: several recordings per nc-test-suite

**Two tests a recording passes or fails.** The design names the two halves of today's `selection_reason`, and keeps each half's rules as the runner's docstring states them today.

- A recording *matches the checkout* when every file it read has the same blob hash in the checkout, every path it looked for is present or absent as recorded, every directory it listed holds the recorded entries, and, when it ran git on the checkout, the checkout's list of files has the recorded fingerprint.
- A recording is *unchanged since COMMIT* when none of the files it read differs between COMMIT and the checkout, no path it looked for was added or deleted, no directory it listed gained or lost an entry, and none of the git rules fires: a file added or deleted while it ran git on the checkout, or any file differing while it ran a content-reading git command on the checkout.

A recording *passed* when its run exited 0 and skipped only cases marked `[this machine cannot run it]`, as `recorded_run_passed_and_skipped_only_cases_this_machine_cannot_run` says today.

**The store.** Each nc-test-suite gets a directory of its own in place of its one file: `<recorded-inputs-directory>/<first 16 hex digits of the root commit>/<the nc-test-suite's path with each / written as __>/`, beside where its file is today. Each recording in the directory is a file named `<key>.json`, where the key is the first 16 hex digits of the SHA-256 of a JSON text, with sorted keys, of the facts the match test compares: the files read with their blob hashes, the paths looked for, the directories listed with their entries, the git commands run on the checkout, and the fingerprint when it ran git on the checkout. Two test runs of one nc-test-suite on the same inputs therefore write the same file name, and the later replaces the earlier. The lists of files only strace saw stay one per nc-test-suite, in `--suite-files-only-strace-saw-lists-directory`, unchanged, and every recording of the nc-test-suite is compared with its list as the single recording is today.

**Selection.** For each nc-test-suite, in this order, after the reasons that select every nc-test-suite or select it because the nc-test-suite file itself differs, which stay as they are:

1. A file on its list of files only strace saw differs: SELECTED, as today.
2. No recording in the current format, which includes a missing or empty directory: SELECTED, "no recording of its inputs on this machine yet".
3. A recording that did not pass matches the checkout: SELECTED, with today's reason for a run that did not pass, even when a passing recording matches too. A run that fails or is killed records only what it read before it stopped, so its recording matches more checkouts than a passing one; it stays the deciding recording until a test run that matches it records a newer outcome, as step 2 of Saving says. After step 2 of Saving, a passing and a failing recording both match one checkout only when two test runs saved at once, and then the failure decides.
4. A recording that passed matches the checkout and is unchanged since COMMIT: NOT SELECTED. The line names that recording's `recorded_at` and commit, beside today's count of files read.
5. Otherwise SELECTED. When a passing recording matches the checkout, the reason is the first failed rule of unchanged since COMMIT of the newest such recording, worded as today. When none matches, the reason is "none of its <N> recordings matches the checkout; the newest: " followed by today's wording of why the newest one does not match.

A recording that does not match the checkout plays no part in the selection: it was made on other inputs, so it says nothing about this checkout.

**Saving.** A test run that records an nc-test-suite, holding the nc-test-suite's lock, which stays the file `<the nc-test-suite's path with each / written as __>.json.lock` beside the nc-test-suite's directory, as today, does three things in this order:

1. Renames its recording into place from a temporary file of its own in the directory, whose name ends in `.tmp`, as `save_recording` does today.
2. Removes every other recording of the nc-test-suite that matches the checkout the test run recorded in, judged with the checkout's list of files the test run took at its start and the blob hashes of the files each recording read, hashed in that checkout when the nc-test-suite ends, as `recording_of` hashes them today. Such a recording was made on the same inputs, so the new one records the newer outcome on them, and a passing recording can never outlive a later failure on the same inputs.
3. When more than 32 recordings remain, removes the ones with the oldest `recorded_at`, the lowest file name first among equal times, until 32 remain; the one just saved is never removed. The test run also removes the nc-test-suite's file in today's format, when one is still there.

A test run that cannot save a recording removes, under the same lock, every recording of the nc-test-suite that matches the checkout and whose file still has the identity the test run read at its start, compared file by file as `remove_recording_if_unchanged` compares the one file today; a recording another test run saved meanwhile has another identity and records that test run's own outcome, so it stays. A removal that fails is reported in the test run's report as today's is. Readers take no lock: a test run lists the directory once at its start and reads each file whose name ends in `.json` once, and a file removed between the listing and the read is skipped. Both selection and the starting order use what the test run read, as today.

**Why 32.** A recording matters only while a checkout with its inputs is still tested. The checkouts tested at once are main and the open pull requests: 9 pull requests were open on 2026-11-06, and merge-lane-2 test-ran up to 78 distinct pull requests in a day (2026-10-31). An nc-test-suite gains a recording only when a test run selects and runs it, so most nc-test-suites hold far fewer than 32. Today's store holds 300 recordings of about 4 KB each on average (`~/.cache/nedschorus-test-suite-recorded-inputs/c8652c93ef1c27e3/`, 2026-11-06), so a full store of 32 per nc-test-suite is under 40 MB. An eviction shows in the selection line as "none of its 32 recordings matches the checkout"; a week after the build merges, the count of those lines over that week's test runs, against all SELECTED lines, is recorded in this GHI-MD, and more than 5% of selections is the evidence for a larger number.

**Other readers of a recording.** The starting order, `suites_longest_recorded_first`, and each nc-test-suite's time limit, `suite_timeout_and_the_recorded_seconds_it_came_from`, use the newest passing recording; with none, both treat the nc-test-suite as they treat one with no passing recording today. `scripts/mutation-testing-changed-lines-quick-or-full-pass-survivors.py` calls `runner.load_recording` in three places: `suites_for_file` chooses an nc-test-suite when any of its passing recordings read the file; `quick_mutation_pass_suites` and `default_mutant_timeout_seconds_from_test_suites_own_time_limits` use the newest passing recording. The runner replaces `load_recording` with a function returning a list of every recording of the nc-test-suite, newest first, empty when there is none, and the build changes those three callers in the same pull request.

**Format.** `RECORDED_INPUTS_FORMAT_VERSION` goes from 5 to 6. A test run finds no recording of the new format for any nc-test-suite at first, so each nc-test-suite is selected once on each store, as after every format change.

**Tests**, in `scripts/run-all-test-suites-test.py`, each on a test fixture repository with two branches whose copies of one file differ:

- A test run on branch X, then one on branch Y, then a selective test run on each branch again: each nc-test-suite reading that file is NOT SELECTED on both branches.
- A passing recording, then a failing test run on the same inputs: the passing recording is gone, and the next selective test run selects the nc-test-suite.
- 33 recordings of one nc-test-suite: the oldest is removed and the new one stays.
- A save that fails removes the matching recordings the test run read at its start, and keeps one another test run saved meanwhile.
- Two test runs saving one nc-test-suite at once leave whole recordings, each named after its own inputs.
- A store in format 5 selects every nc-test-suite once, and the next save removes the format-5 file.
- `scripts/mutation-testing-changed-lines-quick-or-full-pass-survivors-test.py`: an nc-test-suite whose older passing recording, and not its newest, read the file is chosen for that file.

### Part 2: the nc-test-suites that run a content-reading git command on the checkout

The GHI-MD as filed weighed two options, which can be combined: option 1, an nc-test-suite runs git on a test fixture repository it builds instead of on the checkout; option 2, the recorder learns which paths a git command reads from its arguments. The four nc-test-suites still selected this way, from merge-lane-2's `hr/store` recordings and its test-run reports of 2026-11-05 to 2026-11-06:

| nc-test-suite | git call on the checkout | Seconds a test run | What the design does |
|---|---|---|---|
| `.claude/guard-hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook-test.py` | `git clone -q --shared <checkout>`, in its case "with nothing changed, a run does no hashing, copying or store work" | about 50 | Option 1: the case clones a test fixture repository holding the checkout's guarded files, as the hook's own `guarded_blobs_at` lists them, built the way `make_test_repository` in the bash-guards nc-test-suite builds one. |
| `scripts/unvalidated-negative-result-check-test.py` | `git grep -n "scripts/handoff-supervisor.py" 9f8cc38e`, from `scripts/unvalidated-negative-result-check-fixtures/moved-file-checked-by-searching-for-its-old-path.json` | about 2 | Nothing: the call reproduces a real search of the repository's history at a pinned commit, and costs about 2 seconds. |
| `scripts/ghi-issue-write-test.py` | `git ls-remote --heads <a test fixture repository under /tmp> …` | about 1 | `ls-remote` joins `GIT_COMMANDS_THAT_ONLY_LIST`: it lists refs and reads no file's content. The nc-test-suite is then selected only when a file is added or deleted, by the rule for every git call on the checkout. |
| `scripts/branch-leaves-no-citations-of-removed-paths-test.py` | `git diff -z --name-status … <COMMIT>..HEAD` | under 1 | Nothing: the nc-test-suite checks this checkout's own commits, so every change is its input. |

Option 2 is not built. Of the four calls, a clone reads the whole checkout whatever its arguments, the `git diff` covers every file the branch changed, the `git grep` names no path to map, and `ls-remote` reads no file; so mapping arguments to paths would deselect none of them.

### What needs judgment and what is code in this proposal

Code: both tests of a recording, the store, the selection order, saving, superseding, eviction, the readers' choice of recording, and `ls-remote` in `GIT_COMMANDS_THAT_ONLY_LIST`. Judgment, decided in this design: the number of recordings kept, 32, and which is dropped first, the oldest; which option each nc-test-suite of Part 2 gets. The guarded-file hook nc-test-suite's fixture takes its files from the hook's own list of guarded files, so no agent chooses them; the case's assertion is about work done, not time, so a fixture holding every guarded file of the checkout keeps it meaningful. Judgment, after the build: whether the count of evictions calls for a number other than 32.

### How this fits the GHIs near it

[GHI 2259](https://github.com/nedschorus/nedschorus/issues/2259) is a placeholder with no design yet (2026-11-06). Its mapping from each test case to the code it covers belongs in a record of its own; if it is ever joined to these recordings, the join key is a recording's file name, defined under The store. [GHI 2384](https://github.com/nedschorus/nedschorus/issues/2384) reuses a passing test run of a whole tree; this design decides per nc-test-suite. Neither design depends on the other.

### Build, once the user rules

Each in its own pull request, from main, after the user approves this proposal and this GHI-MD records his ruling: (1) Part 1, in `scripts/run-all-test-suites.py`, its test and `scripts/mutation-testing-changed-lines-quick-or-full-pass-survivors.py` with its test, and the runner's docstring sections RECORDED INPUTS and "SELECTION, with --only-suites-whose-recorded-inputs-changed-since COMMIT." rewritten to match; (2) `ls-remote` in `GIT_COMMANDS_THAT_ONLY_LIST`, with a test in `scripts/run-all-test-suites-test.py`; (3) the guarded-file hook nc-test-suite's case on a test fixture repository. After pull request (1) has run for a week, count the "none of its 32 recordings matches the checkout" lines, as Why 32 says, and record the count and the outcome in this GHI-MD.

## Evidence

The measurement, its scripts and the per-reason totals: nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/reboot-test/test-speed-2026-11-04/findings.md and nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/reboot-test/test-speed-2026-11-04/head-run-selection-reasons.txt.

## Related

On 2026-11-04, `scripts/ghi-guide-agent-ask.py --include-closed`, asked for an issue on either reason, found none. Two open GHIs are near: [The test runner `scripts/run-all-test-suites.py` records which code each test case covers, using coverage.py's per-test contexts](https://github.com/nedschorus/nedschorus/issues/2259), a different mechanism, which this design should check before changing the recording format; and [Each round of a pull request runs its test suites once, and a push reuses a passing test run of the same tree](https://github.com/nedschorus/nedschorus/issues/2384), which skips whole runs rather than single suites. Open [pull request 2544](https://github.com/nedschorus/nedschorus/pull/2544) also changes `scripts/run-all-test-suites.py`, taking the ten suites that run without a sandbox out of per-change test runs.

## Next action

Write the design in this GHI-MD: the recording store's new shape, how many recordings it keeps per suite and which it drops first, how runs that save one suite at once stay safe (today a short lock per suite), the matching rule, how it fits the per-test coverage records of GHI 2259 if both land, and which options to build for reason 2. Then add the line `kind: design` to this GHI-MD's front matter, the block between `---` lines at its top that create-GHI writes, and build it in its own pull request after pull request 2544 merges, because both change the runner's selection code.
