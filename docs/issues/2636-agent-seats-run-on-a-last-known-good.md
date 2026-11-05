---
issue: "[Agent-seats run on a last known good commit of main, while main's newest commit is tested as the release candidate up to four times a day](https://github.com/nedschorus/nedschorus/issues/2636)"
kind: design
---

# Agent-seats run on a last known good commit of main, while main's newest commit is tested as the release candidate up to four times a day

## What the user decided

On 2026-11-04 at 19:38 Pacific the user approved, answering "A" to item 7.2 of approval-walk ned-box-helper-push-program-design-points-2026-11-03, that "A GHI-MD designs the last-known-good and release-candidate commits on your direction above, answering the four questions; you rule on it before anything is built." The walk-document is [docs/walk/ned-box-helper-push-program-design-points-2026-11-03.md](file:///Volumes/nedhome/agents/ned-box-helper/docs/walk/ned-box-helper-push-program-design-points-2026-11-03.md), items 7, 7.1 and 7.2, and its walk-minutes are [the -minutes.md file beside it](file:///Volumes/nedhome/agents/ned-box-helper/docs/walk/ned-box-helper-push-program-design-points-2026-11-03-minutes.md), the lines for item 7, both in ned-box-helper's checkout on ned-box until the walk closes.

His direction, from those walk-minutes, given between 2026-11-05T00:03Z and 03:26Z:

- Using the last known good commit and building the release candidate are separate. When a candidate fails, the next candidate is the failed one plus the fix; nobody's work moves backwards.
- The full test run goes from nightly to about 4 times a day, each started when ned-box is quiet.
- Since a full test run is always coming, some tests can wait for it instead of running on every pull request.
- He can start a full test run of the candidate himself at any time, to promote it, however long it takes.
- One agent-seat, the Mac agent-seat he usually runs, runs on the release candidate as the canary; the others run on the last known good commit.

The case against, as item 7.2 put it to him: every agent and merge-lane-2 change how they sync and test, and a test that waits for the full test run finds a break up to 6 hours later. Under this design that is up to 11 hours on a busy day, as part 3 says.

This GHI-MD answers the item's four questions, in parts 2 to 5. The user rules on it before anything is built.

## The two commits

- **last known good commit**: the newest commit of main on which ned-box's full test run, every nc-test-suite, passed. Hooks, skills and instructions of every agent-seat but the canary run from it.
- **release candidate**: main's newest commit, `origin/main`. Every merge moves it. The next full test run tests it, and when that test run passes, the commit it tested becomes the last known good commit.

This design uses both as standard terms of software engineering, in plain words; open question 1 asks whether either becomes a project-term. Neither is in `docs/nedschorus-wiki/nedschorus-sdlc-terms.md` today. Search receipt: `git grep -l -i "last-known-good\|last known good\|release candidate\|release-candidate"` over `scripts`, `nc-systems`, `.claude` and `docs` on origin/main 45e082bc0, 2026-11-04, found only `docs/cross-project/nedschorus-ai-native-software-development-notes.md`, which uses "release candidate" in its general sense, and ghi-guide-agent, asked 2026-11-04, found no GHI that names either.

The release candidate is not a branch of its own. Main already moves only forward, one tested merge at a time, so "the failed one plus the fix" is main's next commit after the fix merges. Nothing is reverted, and nothing but the promotion in part 1 moves the last known good commit.

## What happens today

- **The full test run.** `scripts/daily-full-test-run-of-main.py` runs every suite on origin/main once a day per machine, from cron on ned-box at 03:30 Los Angeles time (`30 3 * * *` in `nc-systems/general-tools/scheduled-jobs-on-each-machine.json` and in ned-box's crontab on 2026-11-04) and from launchd on the Mac. It blocks no merge; it writes a record to `nedlern@ned-box:/home/nedlern/nedschorus-logs/daily-full-test-runs/<machine>/<YYYY-MM-DD>.txt`, which merge-lane-2 reads at each session start. It holds a lock so that a second run started by hand exits 6. The user approved moving it to 00:00 on 2026-10-30 (items 9.2 and 9.3.1 of approval-walk prime-intellect-handed-over-items-2026-10-29, cited in GHI 2353); the crontab still says 03:30.
- **How long it takes.** ned-box's records for 2026-10-20 to 2026-11-04 show 209 suites on 2026-11-04 and wall-clock times from 283 to 1,501 seconds on most days, 3,141 seconds on 2026-10-27, and 7,945 seconds on 2026-11-02. On 2026-11-04 its suites spent 18,853 seconds in all waiting for admission. The same run's `test-suite-resource-use.tsv` gives 4,842 suite-seconds in all, 1,997 of them in the 11 suites that took over 120 seconds.
- **What a pull request runs.** The pre-push hook's selective test run (`scripts/git-client-side-hooks-pre-push-selective-test-run.py`) runs `scripts/run-all-test-suites.py --only-suites-whose-recorded-inputs-changed-since origin/main` on the pushing checkout. merge-lane-2's head test run (`scripts/merge-lane-pull-request-head-test-run-on-merged-worktree.py`, which runs main's `scripts/pull-request-head-test-run.py`) tests the `pr<n>-merged` worktree, the nc-head-commit merged with main, selecting suites changed since the merge base of the nc-head-commit and `origin/main`. The runner's selection runs every suite when the change touches the runner, `.claude/hooks/`, `.claude/guard-hooks/` or `.claude/settings.json` (its docstring, "SELECTION").
- **The merge.** `scripts/merge-gate.sh` reads the pull request's reviews, its comments, its `mergeStateStatus` and its description's `#root_cause` lines; it reads no test record. It refuses a pull request whose state is `BEHIND`, so a pull request merges only when its branch already holds main's newest commit.
- **Where agents' code runs from.** All 42 hook commands in `.claude/settings.json` run as `python3 "$CLAUDE_PROJECT_DIR"/<path>`, so an agent-session runs the hooks, and loads the skills and CLAUDE.md, of its own checkout. The git client-side hooks of every checkout run from the reference-checkout (`core.hooksPath` is `/home/nedlern/Projects/nedschorus/scripts/git-client-side-hooks` on ned-box), and so do the cron jobs and each ned-box agent-seat's handoff-supervisor.
- **How checkouts follow main.** `launch_time_git_sync` in `nc-systems/handoff/handoff-supervisor.py` runs `git merge --ff-only origin/main` on a strictly behind agent-home before an agent-session starts. `scripts/checkout-freshness-catch-up.py`, a Stop hook, at each turn end: rebases a never-pushed branch onto origin/main (its step 4); tells the agent, and never moves, a pushed branch (step 5; GHI 324, closed, user-ruled 2026-09-14 and 2026-09-15); fast-forwards a detached checkout with no commits of its own (step 5b); and fast-forwards the reference-checkout (step 6).
- **Designs this one meets.** GHI [Hooks, skills and instructions load from one copy per machine that tracks main, so a fix reaches every agent-seat when it merges](https://github.com/nedschorus/nedschorus/issues/2408), open, no design yet, puts every agent-seat's hooks, skills and instructions on one copy per machine, the reference-checkout, kept at main. GHI [Test suites that run without a sandbox leave per-change test runs and run apart, when their own files change or in a quiet gap](https://github.com/nedschorus/nedschorus/issues/2381), a design not yet merged (no `LEFT OUT` line and no quiet-gap program on origin/main 45e082bc0; open [PR 2544](https://github.com/nedschorus/nedschorus/pull/2544), "No-sandbox test suites leave per-change test runs and run on main in a quiet gap", builds it), leaves the ten no-sandbox suites out of every selective test run, runs them in a quiet gap, and has `scripts/merge-gate.sh` print a notice of their failure.

## Design

### 1. The last known good commit, and how it moves

The last known good commit is a branch on origin, `last-known-good`, so that every clone's ordinary `git fetch origin` brings it and every git tool shows it as `origin/last-known-good` (open question 6 gives the alternative). Only one program moves it, by a fast-forward push, and only after a passing full test run on ned-box.

A new program, `scripts/full-test-run-of-main-in-a-quiet-gap-and-last-known-good-promotion.py`, runs on ned-box under cron every 5 minutes. Its entry in `nc-systems/general-tools/scheduled-jobs-on-each-machine.json` replaces ned-box's entry for `scripts/daily-full-test-run-of-main.py`, so cron does not also start the old daily run, and `nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py --install` installs it; the Mac's entry stays. Each invocation, in order:

1. Takes its own lock without waiting; when another invocation holds it, exits 0.
2. Reads its state file, `~/.local/state/nedschorus/full-test-run-of-main-in-a-quiet-gap-and-last-known-good-promotion.json`: the last full test run's commit, start, end and result, how many full test runs in a row failed at that commit, the last time a test suite was seen running on ned-box, the window of the last start, and a passing commit not yet promoted. A missing or unreadable file counts as empty.
3. When the state file holds a passing commit not yet promoted, because an earlier push failed, retries that push as in step 7 and exits, without starting a full test run.
4. Records whether a test suite is running now, as part 3 says.
5. Decides whether a full test run is due and ned-box is quiet, as part 3 says; exits 0 when not.
6. Runs `scripts/daily-full-test-run-of-main.py`, which fetches origin, tests origin/main's newest commit in a detached worktree, and writes its record as today.
7. Writes the full test run's result to the state file. When that program exited 0 and its record names commit C, C is the passing commit not yet promoted, and the program pushes C to `refs/heads/last-known-good` without force: it creates the branch at C when origin has none, and otherwise pushes only when `origin/last-known-good` is an ancestor of C. The push fails, rather than moving the branch backwards, when the branch moved to a later commit in the meantime. After a push that worked, it clears the passing commit not yet promoted from the state file.

Every failure to fetch, push or write the state file prints its reason and exits nonzero, so cron's output file, `~/.claude/full-test-run-of-main-in-a-quiet-gap-and-last-known-good-promotion.log` on ned-box, where the other cron jobs' output files are, keeps it.

**The user's own start.** The same program with `--start-now` skips the window and the quiet test, waits for the full test run's lock instead of exiting, and promotes as in step 7 when the test run passes. Its start counts as the start of the window it falls in, so the scheduled full test run of that window does not also start. He runs it from his Mac as `ssh nedlern@ned-box 'python3 ~/Projects/nedschorus/scripts/full-test-run-of-main-in-a-quiet-gap-and-last-known-good-promotion.py --start-now'`, or tells an agent to.

Only ned-box's full test run promotes. The Mac's daily full test run stays as it is and writes its own record: the Mac sleeps, so a promotion that waited for it could wait for days, and the suites that run only on macOS are few (on 2026-11-04 ned-box skipped 10 cases in 7 suites).

The pre-push hook's conflict check and selective test run look at every pushed branch but main (`branches_to_check` in `scripts/git-client-side-hooks-pre-push-conflict-check.py`, `UNCHECKED_BRANCH_REF = "refs/heads/main"`). The promotion push of `last-known-good` is added to the refs those checks leave alone, because the commit it pushes is already on main and has just passed every suite.

### 2. Which commit agent-seats run on, and which commit they start branches from (question 1)

**Branches start from origin/main, the release candidate, as today.** Work changes the candidate: a fix for a failed candidate must be built on it, since the next candidate is "the failed one plus the fix". `scripts/merge-gate.sh` refuses a pull request that is `BEHIND`, so a branch cut from the last known good commit would have to take in main before it could merge anyway, and the head test run tests it merged with main. The checkout-freshness hook keeps rebasing a never-pushed topic branch onto origin/main.

**What an agent runs comes from the last known good commit.** Three movers change their target from origin/main to origin/last-known-good, for checkouts that hold no work of their own:

- `launch_time_git_sync` fast-forwards a strictly behind agent-home to origin/last-known-good.
- The checkout-freshness hook's step 5b fast-forwards a detached checkout with no commits of its own to origin/last-known-good, and its step 4 does the same for a never-pushed branch with no commits of its own, such as a seat-branch in its agent-home, in place of rebasing it onto main.
- The checkout-freshness hook's step 6 fast-forwards the reference-checkout to origin/last-known-good, so the git client-side hooks, the cron jobs and the handoff-supervisors run the last known good commit's code. The glossary entry for reference-checkout, "which stays on `main`", changes to say the reference-checkout stays at the last known good commit.

A fast-forward never moves a checkout backwards. An agent-home that is at a newer commit of main when this is built, as most will be, stays where it is until the last known good commit passes it. The glossary entry for launch-time-git-sync, which says it fast-forwards to `origin/main`, changes to match.

**GHI 2408's one copy per machine is kept at the last known good commit**, not at main (open question 3). Until GHI 2408 is built, a subagent in a worktree of its own, cut from origin/main, still runs that worktree's hooks through `$CLAUDE_PROJECT_DIR`, so "runs on the last known good commit" holds for agent-homes and the reference-checkout, not yet for such subagents. A branch that changes a hook or a skill still tests it from its own checkout, as GHI 2408's requirement says.

**The canary.** One setting names the agent-seats whose agent-home follows origin/main instead: a file in the repository, `nc-systems/handoff/handoff-canary-agent-seats-whose-agent-home-follows-main.json`, holding a JSON list of agent-seat names, today one, which the three movers read (open question 2 names the agent-seat; open question 7 offers GHI 972's agent-seat record as the place). The canary runs its hooks, skills and instructions from main's newest commit, as every agent-seat does today. Its git client-side hooks still come from the Mac's reference-checkout, at the last known good commit.

When a candidate breaks the canary badly enough that it cannot work, the user takes its name out of the canary file, in a pull request or by asking an agent to. At the canary's next session start, `launch_time_git_sync` then checks out origin/last-known-good, detached, in its agent-home, when the agent-home holds no commits of its own and no uncommitted tracked change; otherwise it leaves the agent-home as it is and says why, as it does today. That moves a checkout back, never anyone's work, which stays on the branches the canary pushed.

### 3. When a full test run starts: "ned-box is quiet" (question 2)

**Windows.** The day has four windows of 6 hours, starting 00:00, 06:00, 12:00 and 18:00 Los Angeles time. Each window gets at most one scheduled full test run. A full test run is due in a window when none has started in it yet, unless the last one tested origin/main's present commit and passed, in which case there is nothing new to test. So a failed full test run is tried once more in the next window even when main has not moved, which clears a transient failure. After two failed full test runs in a row at the same commit, none is due at that commit again; the next one starts once main moves, which it does when the fix merges.

**Quiet.** No test suite has run on ned-box for 20 minutes. Each invocation, every 5 minutes, records whether a suite is running now. A suite is running when any of the 64 admission slot files, in the admission directory beside `~/.claude/.run-all-test-suites.lock`, is held, which the program tests by taking each with a non-blocking flock and releasing it at once, or when a run record in `~/.claude/.run-all-test-suites.lock.runs/` names a runner process that is still alive, its process id and start ticks both matching `/proc`, so a process id the kernel reused for another program does not count. The admission directory is `~/.claude/.run-all-test-suites.lock.test-suite-admission/`. The runner's records name each runner's process id and start ticks but no end time, so the program samples instead of reading an end. The second test catches a test run whose suites all wait for admission and hold no slot. ned-box is quiet when the last time a suite was seen running is 20 minutes or more ago. A suite that ran wholly between two samples is missed; that costs a full test run started beside a short suite, which admission then shares the machine with.

**A busy day with no gap.** When no quiet 20 minutes has come by 5 hours into a window, the program starts the full test run anyway. Its suites then share ned-box through the runner's admission: a suite starts only while CPU use is under 90% and over 10 GB of memory is free, at most 64 at once, every suite at CPU weight 10 against the agent-seats' 100 (the runner's docstring, "ADMISSION"). A pull request's test run that starts beside it waits for admission as its suites already do beside other test runs; on 2026-11-02 a full test run took 7,945 seconds on such a day. So at worst two full test runs are 11 hours apart: one at the start of a window, the next at the 5-hour deadline of the window after.

**Strace.** Only the first full test run of each day, the 00:00 window's, passes `--record-inputs-with-strace`, as the daily one does today; the other three record with the audit hook alone, because strace costs ned-box too much CPU to run more often (the runner's docstring, "RECORDED INPUTS").

GHI 2381's quiet test, that the no-sandbox suites' lock is free, is narrower than this one; under open question 4 its own quiet-gap program is not built, and this part covers it.

### 4. Which suites wait for the full test run, and the fast check of the candidate (question 3)

**Which suites wait.** The suites the runner lists in a new constant, `SUITES_LEFT_OUT_OF_SELECTIVE_TEST_RUNS_UNTIL_THE_FULL_TEST_RUN`, beside `SUITES_RUN_WITHOUT_ANY_SANDBOX`, which takes the place of the separate leave-out PR 2544 builds for the no-sandbox suites, so the runner has one. The first list is two sets, which together make 19 suites:

- the ten no-sandbox suites, as GHI 2381 already decided;
- the suites whose time in the most recent full test run was over 120 seconds. On 2026-11-04 these were 11, two of them no-sandbox suites: `nc-systems/general-tools/tests/bash-guards-verdict-changes-between-two-git-refs-on-transcript-recorded-commands-check-test.py` (416 s), `scripts/run-codex-task-from-brief-test.py` (313 s), `scripts/run-suite-in-signal-sandbox-test.py` (186 s), `nc-systems/skills/walk-me-through/tests/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close-test.py` (146 s), `scripts/checkout-freshness-catch-up-test.py` (144 s), `nc-systems/main-gatekeeper/tests/main-gatekeeper-suite-paired-overlap-test.py` (142 s), `scripts/merge-gate-test.py` (137 s), `scripts/run-all-test-suites-test.py` (133 s), `nc-systems/cold-read/tests/cold-read-grid-test.py` (126 s), `scripts/git-client-side-hooks-pre-push-test.py` (126 s) and `scripts/pull-request-review-plan-test.py` (123 s).

Choosing the list is a judgment, made once by the user's ruling on open question 5, and after that by pull request review of a change to the constant. A suite is kept off the list where a break it would catch reaches agent-seats before a full test run: under this design none does, since every agent-seat but the canary runs on the last known good commit.

**How a pull request's own test run knows to skip them.** The runner leaves a listed suite out of every selective test run, one given `--only-suites-whose-recorded-inputs-changed-since` without `--only-suites-named`, by default, so the pre-push selective test run, an author's own test run and merge-lane-2's head test run all leave it out with no change to those callers. For each listed suite the selection would have picked, the runner prints the `LEFT OUT ` line GHI 2381 designs: the suite, why it would have been selected, and the command that runs it by hand, `python3 scripts/run-all-test-suites.py --only-suites-named <suite>`. A left-out suite is counted neither as failed nor as not run. A full test run, which gives no selection option, and mutation testing, which names its suites with `--only-suites-named`, run listed suites as today.

Each listed suite carries, in the constant, the files whose change still runs it in a selective test run: its own file, and the programs it tests, written out by hand, because a name rule fails here: `scripts/git-client-side-hooks-pre-push-test.py` tests `scripts/git-client-side-hooks-pre-push-selective-test-run.py` and three other programs, and no `git-client-side-hooks-pre-push.py` exists. So an author who changes `scripts/merge-gate.sh` still runs `scripts/merge-gate-test.py` before the merge. GHI 2381 decided the opposite for the no-sandbox suites, which it leaves out even when their own file changes; open question 5 asks which rule both sets follow.

**The fast check of the candidate is the head test run, already there.** `scripts/merge-gate.sh` refuses a pull request that is `BEHIND`, so main's newest commit before the merge is already in the branch, and the head test run's `pr<n>-merged` worktree holds the tree the merge then makes (unverified for GitHub's merge commit; true of git's merge of the same two commits without conflicts). Each merge therefore makes a candidate whose changed suites have just passed on its tree. The canary agent-seat then uses that candidate's hooks and skills. No further check is added: no failure on record shows the head test run missing a break that a quick check of the candidate would have found.

### 5. merge-lane-2's merge test (question 4)

- The head test run keeps testing the `pr<n>-merged` worktree, the next release candidate's tree, with its suites selected since the merge base as today, less the listed suites of part 4.
- A merge moves only main, the release candidate. merge-lane-2 never waits for the last known good commit and never moves it.
- Merges go on while the candidate's last full test run failed: the fix merges as one more pull request, and the next full test run tests the candidate with the fix. Stopping all merges would stop every agent-seat's work for one suite's failure.
- `scripts/merge-gate.sh` keeps its exit codes and reads no test record for its verdict. It gains one notice on stderr, through the channel GHI 2381's part 4 designs, so there is one notice and not two: when the last full test run failed, the notice names each failing suite, its log, the commit range from the last known good commit to the commit tested, and the pull requests merged in that range, read from main's first-parent merge commits, the ones whose changed files a failing suite's recorded inputs hold marked first, since those are the likeliest causes. The notice also says how long ago the last known good commit moved.
- merge-lane-2's review tools, which `scripts/merge-lane-pull-request-worktrees-reviewer-brief-codex-review-and-head-tests-run-without-merge.py` checks out at main's newest commit today, move to the last known good commit (open question 8). Then a merged pull request that breaks a review tool cannot also break the review of its own fix.

### 6. Where a failed full test run goes

The full test run's record is written as today. The promotion program does not move the last known good commit. The merge-gate.sh notice of part 5 shows the failure at merge-lane-2's next merge. merge-lane-2 sends the follow-up to an author, and records that it sent the follow-up, as GHI 2381's part 4 says. That notice takes the place of merge-lane-2's reading of the newest daily record at each session start, so the line of merge-lane-2's seat-brief that says to read it is removed. The record for the window's test run stays in the log-store under `daily-full-test-runs/ned-box/`, one file per test run, named for its date and the window's start hour, in place of one file per day.

### Steps that need judgment

Everything in parts 1 to 6 is code, except:

- Choosing the suites that wait for the full test run: the user's ruling on open question 5, then pull request review of each change to the list.
- merge-lane-2 judging, from a failed full test run's logs and the pull requests merged in its range, which author to send the follow-up to, and the author fixing it.
- The canary agent-seat, or the user using it, noticing that the candidate misbehaves in use and saying so to merge-lane-2 and the author whose pull request it suspects.

### Tests

- The promotion program, with a fake full test run, a fake admission directory and run records, and a scratch repository with a bare origin: it exits 0 when its lock is held; a slot held, or a live runner in a run record, counts as a suite running; it starts nothing until 20 quiet minutes have passed, and starts at 5 hours into a window when they never come; one start per window; no start when the last test run passed on the present commit; it retries in the next window after a failure, and not after a second failure at the same commit; a `--start-now` start counts as its window's start; a failed push is retried at the next invocation without a new full test run; a run record whose process id now belongs to another process does not count as a suite running; a passing test run creates `last-known-good` when origin has none, and otherwise fast-forwards it, and a failing one does not; a branch that moved further meanwhile is not moved back; `--start-now` waits for the lock and promotes; a failed fetch, push or state write exits nonzero.
- The runner: a selective test run leaves a listed suite out with its `LEFT OUT ` line, runs it when its own file or a program the constant lists for it changed, and does not count it in its exit code; a full test run and `--only-suites-named` run it.
- The movers: `launch_time_git_sync` and the checkout-freshness hook's steps 4, 5b and 6 fast-forward to origin/last-known-good, never backwards, and follow origin/main for an agent-seat the canary file names; a name taken out of the file sends that agent-home back to origin/last-known-good at its next session start only when it holds no commits and no change of its own; a topic branch with its own commits still rebases onto origin/main.
- The pre-push hook lets a push of `last-known-good` through without the conflict check or the selective test run.
- `scripts/merge-gate.sh`: the notice appears after a failed full test run, with the range and the age of the last known good commit, and the exit code does not change.

## Deferred-decisions

- The exact first list of suites over 120 seconds, taken from the full test run before the build, since suite times move from day to day.
- Which account the promotion push uses, and whether GitHub's rules on the `last-known-good` branch can refuse a force-push and a push from any other account (unverified).
- The time limits on the promotion program's fetch and push, set from their measured times on ned-box.
- How the Mac's agent-homes and reference-checkout fetch origin/last-known-good when ned-box is unreachable: they fetch from GitHub, which holds the branch, so they need nothing from ned-box (unverified for the Mac's remote setup).

## Open questions for the user

1. The names. Whether "last known good commit" becomes a project-term, which the naming page would spell `nc-last-known-good`, since the project adds its own meaning to a standard term; "release candidate" stays plain words for main's newest commit. The branch `last-known-good`, the program and constant names above, and a new name for `scripts/daily-full-test-run-of-main.py`, which no longer runs once a day on ned-box. Recommendation: keep both as plain words, keep the branch name, and rename the daily program in the same build.
2. Which Mac agent-seat is the canary. Recommendation: name it, and change it by editing the canary file.
3. GHI 2408's one copy per machine is kept at the last known good commit, not at main, which changes what GHI 2408's title says and what you approved on 2026-11-01. Recommendation: yes, and edit GHI 2408's GHI-MD to match when this design is approved.
4. GHI 2381's own quiet-gap program for the no-sandbox suites (its part 2, in open PR 2544) is not merged, because the full test run up to four times a day runs them; its parts 1 and 4 are kept and reused here. The cost: a change to a no-sandbox suite's inputs is tested up to 11 hours after it merges instead of within about an hour. Recommendation: yes, since only the canary runs on a candidate those suites have not yet tested.
5. Which suites wait: the ten no-sandbox suites and those over 120 seconds, and whether a listed suite still runs when the change touches its own file or a program the constant lists for it, for both sets, the opposite of what GHI 2381 decided. Recommendation: both sets, and run a listed suite when its own file or a listed program changed, because an author who changes `scripts/merge-gate.sh` should see `scripts/merge-gate-test.py` pass before the merge.
6. Where the last known good commit lives: a branch on origin, `last-known-good`, which every fetch brings, with the pre-push exemption of part 1; or a ref outside `refs/heads/`, which the pre-push checks already ignore but which every program must fetch by name, and which GitHub may not accept (unverified). Recommendation: the branch.
7. Where the canary setting lives: the file in part 2, or GHI 972's planned agent-seat record on ned-box, once that is built. Recommendation: the file now, since GHI 972 is not built.
8. merge-lane-2's review tools at the last known good commit instead of main. The cost: a fix to a review tool is used by reviews only after the next promotion, up to 11 hours after it merges. Recommendation: the last known good commit, because a review tool broken at main would also break the review of its own fix.

## Related

- GHI [Hooks, skills and instructions load from one copy per machine that tracks main, so a fix reaches every agent-seat when it merges](https://github.com/nedschorus/nedschorus/issues/2408): the copy part 2 keeps at the last known good commit.
- GHI [Test suites that run without a sandbox leave per-change test runs and run apart, when their own files change or in a quiet gap](https://github.com/nedschorus/nedschorus/issues/2381): the `LEFT OUT ` line and the merge-gate.sh notice part 4 and part 5 reuse.
- GHI [Each round of a pull request runs its test suites once, and a push reuses a passing test run of the same tree](https://github.com/nedschorus/nedschorus/issues/2384): the push program whose deferred item 2, a suite that also fails on main, this design narrows, since a failure on main no longer reaches the agent-seats that run on the last known good commit.
- GHI [The handoff-supervisor restarts itself on main's current code at each handoff](https://github.com/nedschorus/nedschorus/issues/2036): restarts from the reference-checkout, which part 2 keeps at the last known good commit.
- GHI [Look for maintenance windows beyond the overnight one when CPU, memory and token use are all low](https://github.com/nedschorus/nedschorus/issues/2353): a related quiet-time idea for maintenance-jobs.
- GHI [The daily full test runs tell the user about failures and about test cases that run nowhere or lack a tool, and every test suite prints a skipped test case in one format](https://github.com/nedschorus/nedschorus/issues/1206): the planned path of a full test run's failure to the user.
- GHI [One design of record for the project's git checkouts, worktrees and branch rules](https://github.com/nedschorus/nedschorus/issues/1121): the branch rules this design changes for agent-homes.
- GHI [checkout-freshness catch-up merges main into a branch whose head is frozen under review](https://github.com/nedschorus/nedschorus/issues/324), closed: a pushed branch is never moved, which this design keeps.

## Next action

ned-box-helper puts this design and its eight open questions to the user in an approval-walk. Nothing is built before he approves it.
