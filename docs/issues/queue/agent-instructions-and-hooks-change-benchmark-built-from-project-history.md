# A pilot of three past bug fixes, redone by agents on the code as it stood before each fix, to learn whether a benchmark of agent-instructions and hooks can be built from the project's history

This GHI-MD is pending approval and has not been filed as a GHI yet. When the user has approved it, it is filed with create-GHI.

## Why

A change to `CLAUDE.md`, a skill, a prompt or a hook is judged today by reading the change and by its own tests; its effect on the work agents do is not measured. The user wants changes judged on the quality of the work agents produce. Agents' outputs vary from one invocation to the next, so measuring that needs many tasks with known right answers, run repeatedly. Those of the project's merged bug fixes that came with a regression test are such tasks.

Whether such tasks can be built from this project's history, and whether agents' invocations on them can be read and scored, is not known. The earlier design of the full benchmark, in this GHI-MD's previous text, went through five cold-read-full-runs and one /sanity-check run; in each cold-read-full-run, each reviewer that hunted defects reported about fifty, nearly all gaps in rules for a program nobody had built. This GHI-MD builds three tasks and runs them, so that the second GHI-MD, for the full benchmark, rests on what happened.

## Words used here

- A **case** is one task built from one merged pull request that fixed a bug and added or changed a regression test for it. A single test inside a test suite is a **test case**, the test runner's word, never a case.
- The **pre-fix tree** of a case is the files of the first parent of the pull request's merge commit: main as it stood just before the fix merged.
- A **test file** is a file named `*-test.py`, `*-test.sh` or `*-test-fixture.py`, or any file under a directory named `tests` or whose name contains `-test-`. A **test suite** is a test file that `scripts/run-all-test-suites.py`, the test runner, runs: one named `*-test.py` or `*-test.sh`.
- The **hidden tests** of a case are the test files the pull request added or changed, as they stand at its merge commit.
- An **arm** is one version of the agent-instructions and hooks the agent works under.
- An arm's **instruction package** is a directory holding `CLAUDE.md`, `AGENTS.md`, `.claude/`, `docs/agents/`, every program a hook in that `.claude/settings.json` runs, and every project file those programs read when they run.
- The **evaluation harness** is the program this GHI-MD's work builds to construct cases, run the pilot and print the pilot report.
- cold-read-full-run and sanity-check-record are defined in `.claude/skills/skills-glossary.md`.

## What the history supplies

A count made on 2026-10-09 covered the 971 merged pull requests numbered 1 to 1160: 79 change a program and a test file and have a title that reads as a fix. The count, its program and the list of 79 are in `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/benchmark-case-count-2026-10-09/`. 37 of the 79 merged after PR [Every test suite runs from one committed program, judged by its exit code](https://github.com/nedschorus/nedschorus/pull/618) added the test runner, at 2026-09-22T01:43Z, by the `mergedAt` times in that directory's `merged-pull-requests.json`: 628, 656, 688, 691, 695, 699, 701, 702, 708, 714, 728, 762, 771, 776, 800, 803, 822, 838, 881, 943, 960, 969, 971, 978, 985, 992, 1007, 1021, 1023, 1031, 1032, 1068, 1087, 1096, 1109, 1120 and 1160. The pilot takes only these, because an agent that follows `CLAUDE.md` runs the test runner, which an older tree lacks. Checked on 2026-10-12: each of the 37 merge commits has two parents, so its first parent is main just before the fix, and none of the 37 deleted or renamed a test file.

Building a case by reverting the fix on today's main was tried and rejected: on main of 2026-10-10 the revert applied cleanly for only 11 or 12 of the 79, and main takes 20 to 65 merges a day. On the pre-fix tree of 8 sampled pull requests (72, 102, 200, 307, 416, 584, 822 and 1160), the merged regression test failed before the fix and passed after it in all 8. Both trials are in `fresh-eyes-claude.md` of the sanity-check-record `nedlern@ned-box:/home/nedlern/nedschorus-logs/sanity-check-records/2026-10-10-agent-instructions-and-hooks-change-benchmark-built-from-project-history/`.

## When the pilot starts

The pilot starts when the user gives his go on the sandbox probe. At that moment the evaluation harness cuts the first arm's instruction package from main, and takes the test runner it uses for admission and scoring from the same commit; both stay fixed until the pilot report.

## Step 1: the sandbox probe

Each invocation of the agent, and of the bug report writer in Step 2, happens inside one bubblewrap sandbox that the evaluation harness starts with its own process namespace, so that ending the sandbox ends every process inside it. The sandbox shows only what this list names; everything else on ned-box, every other checkout, the log-store, other agent-sessions' transcripts and GitHub's credentials among it, is absent:

- the case tree and its bare `origin` repository, read and write;
- the arm's instruction package, read only;
- the system's programs and libraries, `claude` among them, read only;
- a private home directory, made new for each invocation and kept by the evaluation harness afterward, holding: `~/.claude/CLAUDE.md`; the user's `~/.claude/settings.json` with Remote Control and cross-session messages turned off, so that the agent can reach no other agent-session; the programs that settings file runs; and `~/.claude.json`. The login file `~/.claude/.credentials.json` is the real one, shown read and write, so that a login refresh inside the sandbox reaches the file every other `claude` on ned-box uses;
- a private temporary directory.

Network access stays open, because the model needs it. The repository is public, so an agent can read the merged fix on GitHub without credentials; Step 4 reports every such read.

On ned-box a second bubblewrap sandbox cannot start inside a first (`kernel.apparmor_restrict_unprivileged_userns = 1`), and the test runner runs each test suite in a bubblewrap sandbox of its own. So the sandbox sets `RUN_ALL_TEST_SUITES_INSIDE_SIGNAL_SANDBOX`, under which the test runner runs its suites without starting another, and Claude Code's own sandbox stays off. Run that way inside one bubblewrap sandbox, the test runner passed the 15 suites that `--only-suites-whose-recorded-inputs-changed-since HEAD~1` selected, on 2026-10-10: `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/benchmark-sandbox-nesting-probe-2026-10-10.md`. The test runner gained its own bubblewrap sandbox and that variable in the same commit, cf2b3cae of 2026-10-05, so a pre-fix tree's test runner either starts no bubblewrap sandbox or honours the variable. Four suites start a bubblewrap sandbox themselves, the ones the test runner's `SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX` names, and fail inside the sandbox wherever a tree holds them.

The probe uses main's files at the pilot's start as the case tree and the first arm, and checks four things:

1. `claude -p` logs in inside the sandbox and answers.
2. Claude Code runs a hook: the transcript shows the output of the arm's SessionStart hook.
3. Every hook command in the arm's `.claude/settings.json` exits without error when the evaluation harness hands it a sample event inside the sandbox. The evaluation harness runs each one under `strace` and adds every project file the hook opened to the instruction package. A hook that fails is listed with its error. A hook program that finds its repository from its own location, as `scripts/uncommitted-work-snapshot-hook.py` does, acts on the instruction package and not on the case tree, and is listed too.
4. The test runner, run inside the sandbox, passes every test suite but the four above.

The probe spends usage, so it waits for the user's go. The user reads its results, including the instruction package's file list and the hooks listed in check 3, and decides whether the pilot goes on, and whether both arms drop any listed hook.

## Step 2: three cases

The evaluation harness takes the 37 candidate pull requests newest first, by merge time, and builds cases until three are admitted and confirmed. A candidate is left out when its pull request changed a file that either arm's instruction package holds: the arm either replaces that file in the case tree or runs its own copy of it as a hook, and the agent can read the instruction package, so the fixed version would be in front of the agent.

- **Case tree**, built fresh for every invocation and every test run: the files of the pre-fix tree, with the arm laid over them when an agent works in the tree, committed on branch `main` as the only commit of a new git repository in a new directory, with the commit's author and committer dates set to the date of the merge commit's first parent, so that `git log` shows nothing later. The case tree's `origin` is a bare repository whose `main` is that same commit, so hooks that fetch or rebase onto `origin/main` find nothing newer.
- **The arm laid over the case tree**: before that commit, the evaluation harness replaces the pre-fix tree's `CLAUDE.md`, `AGENTS.md`, `.claude/` and `docs/agents/` with the arm's copies, and rewrites every hook command in `.claude/settings.json` to an absolute path into the arm's instruction package. Because the arm is in the commit, `git status` shows a clean tree and `git diff` shows nothing of the pre-fix instruction files. The case tree's own `scripts/` and `nc-systems/` are not touched: they hold the code the agent fixes.
- **Hidden tests**: kept outside the case tree. Before any test run of the evaluation harness, they are copied in and staged with `git add -f`, because the test runner runs tracked suites only and `-f` stages a path the tree's `.gitignore` would skip.

**Admission.** The evaluation harness runs each of the two tests below three times, each time on a freshly built tree with the tree's own instruction files and no arm, with the test runner of the pilot's start and `--checkout <tree>`, outside the sandbox, so that the test runner uses its own:

1. On the case tree with the hidden tests, at least one hidden test suite exits with a failure, and every test suite that is not a hidden test passes.
2. On a tree built the same way from the merge commit's files, with the hidden tests, every test suite passes.

A candidate is not admitted when a test suite passes in one of the three test runs of a test and fails in another, a flaky test suite. Every test run takes the test runner's default lock. When the test runner exits 3, because another test run on ned-box holds the lock, the evaluation harness waits a minute and starts the test run again. A test run still going 30 minutes after it started is stopped, and its candidate is not admitted; a full test run of main took about two minutes on 2026-10-12. When the test runner exits 2, it could not start: the evaluation harness stops and prints what the test runner printed.

**Bug report**, written for each admitted case by a `claude -p` agent in the sandbox, with the case tree, the hidden tests and the output of admission test 1 copied in, and never the fix or the pull request's description. Its prompt tells it not to look the case up on GitHub; the pilot report lists any network read it made. The bug report says what goes wrong and what should happen instead, and states every name, flag, message and exit status the hidden tests check. It reveals the fix if it says how the code should change: which function or line, or the approach of the fix's diff. Naming the behavior a hidden test checks does not reveal the fix.

**Confirmation.** The user reads each bug report beside its hidden tests and the fix's diff, and confirms three things: the pull request fixed a bug, the bug report states what the hidden tests require, and it does not reveal the fix. A bug report he rejects is written once more with his reason; a second rejection replaces the case with the next candidate. If the 37 candidates run out before three cases are admitted and confirmed, the user decides how to go on.

## Step 3: two arms, each case once in each

The two arms are the instruction package cut from main when the pilot starts, and the same package with `CLAUDE.md` empty. The second is expected to make agents worse. It is the cheapest change that exercises laying an arm over the case tree. With one invocation per case and arm, the pilot cannot measure an arm's effect: it shows whether the evaluation harness works and what an invocation in each arm looks like.

Each case runs once in each arm, six invocations in all, one at a time on the machine: `claude -p --permission-mode bypassPermissions`, on the user's Claude subscription, inside the sandbox, with initial-agent-instructions that give the bug report, tell the agent to work only in the case tree, to finish by saying what it did or what is missing, and not to push. After 30 minutes the evaluation harness ends the sandbox and the case is scored as it stands.

**Scoring.** The evaluation harness builds a fresh case tree with the tree's own instruction files and no arm, copies into it the files the agent changed or added in its case tree, and deletes the files the agent deleted, leaving out `CLAUDE.md`, `AGENTS.md`, `.claude/`, `docs/agents/` and test files. It then copies in and stages the hidden tests and runs the test runner of the pilot's start, with `--checkout <that tree>`, outside the sandbox, under the same lock and 30-minute rules as admission. The case is solved when the test runner exits 0. A scoring test run stopped at 30 minutes is unsolved.

## Step 4: the pilot report, and a stop

The evaluation harness keeps, in a directory of the log-store that the pilot report names, each case's hidden tests and bug report, each invocation's private home with its Claude Code transcript, the agent's changed files, and each scoring test run's report. The pilot report shows, for each case and arm:

- the bug report the agent got;
- what the agent did: the commands it ran and the files it changed, from the transcript and the case tree;
- its last reply, or that the evaluation harness ended the sandbox at 30 minutes;
- the scoring verdict, solved or unsolved, and the verdict of every test suite, hidden and not, with the test cases each suite skipped;
- every command or tool call in the transcript that reached the network other than through the model, such as `curl`, `wget`, `git clone`, `gh`, WebFetch or WebSearch;
- the model, the effort level and the version of `claude` the invocation ran with;
- any fault of the evaluation setup: a hook that fails or refuses because it runs in the sandbox, not a guard refusing what it exists to refuse; a hook writing outside the case tree, the private home and the private temporary directory; a sandbox path the agent needed and lacked; a usage limit or a logged-out `claude` that ended the invocation; and a read of the project's pull requests, GHIs or repository on GitHub.

The evaluation harness lists what it can find of these; the reader of the transcript decides. An invocation with a fault of the evaluation setup is reported as invalid and is not counted as solved or unsolved. When a usage limit or a logged-out `claude` ends an invocation, the evaluation harness stops and tells the user what `claude` printed.

Every transcript is read, by the user or by the agent-seat prime-intellect, which wrote this GHI-MD, and the pilot report says who read each one. The user then decides from the pilot report whether the second GHI-MD, for the full benchmark, is written.

## Decided by the user; to be specified from the pilot's evidence

The user decided these in the approval-walks on the /sanity-check run of the earlier design, `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/agent-instructions-and-hooks-change-benchmark-sanity-check-triage-2026-10-10-minutes.md` and `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/benchmark-walk-items-10-and-11-and-cold-read-triage-sentence-2026-10-10-minutes.md`, except where a line says otherwise. If the user decides to write the second GHI-MD, for the full benchmark, it specifies them, with what the pilot shows; the full benchmark starts with ten cases.

- Each measurement request names its primary metric, its repetitions and its noninferiority margin, the drop in solved cases still accepted as no harm, and says which result counts as unclear; an unclear result is measured once more, with new repetitions, and the second result decides.
- Results per case and overall by a two-sided sign test, with the minimum detectable effect for ten cases. This line comes from the earlier design, not from an approval-walk item.
- The measure of false claims, claims of done or of passing tests that no complete test run after the agent's last change supports: the time of the last change taken from the files as well as from Claude Code's edit tools, and a test run counted only when its suites ran to the end.
- Whether a Claude Code Stop hook that refuses a claim of done or passing tests, when no test ran after the last change, reduces false claims without costing solved cases.
- Whether a separate agent that checks a task's inputs before the agent starts catches insufficient inputs better than the agent does: the demonstrated gain that standing decision 21 of `docs/nedschorus-wiki/nedschorus-ai-native-software-development-objective.md` asks for before an input check is split off, measured under decision 26, "Evidence first; cost is a bound". This line rests on the user's statement of 2026-10-09, not on an approval-walk item.
- Underspecified variants, cases whose bug report lacks one fact the hidden tests need, built after the first ten cases: the missing fact picked from a list code makes, checked absent from the pre-fix tree with `git grep -F`.
- LLM judges answer in fixed formats that code checks.
- Admitted cases frozen: a comparison of their git hashes with the recorded ones, a command that retires a case, and the directory holding them listed in `FROZEN_MEASURED_DATA_DIRECTORIES` of `scripts/md-drift-lint.py`.
- Candidates listed from GitHub by the evaluation harness.
- No held-out cases until the benchmark runs on every pull request.
- `claude` only; Codex later.

## Known limits

- A bug report written from a test is more exact than most real bug reports.
- The pre-fix tree holds the old version of a changed test file beside the code; the agent may read it.
- The repository is public, so a model may have learned a fix from training data, and an agent can read the fix on GitHub; the pilot report lists such reads.
- The pilot's agents have no GitHub credentials, no other checkouts and no long conversation, unlike real agent-seats.
- The agent reads main's `CLAUDE.md` beside the pre-fix tree's wiki pages and programs. An instruction that names something an older tree lacks fails there, such as the test runner's `--only-suites-whose-recorded-inputs-changed-since` flag before 2026-09-30. In the arm with `CLAUDE.md` empty, `scripts/pr-reviewer-instructions-copies-test.py` fails in the agent's own test runs on a tree that holds it, because that test compares `CLAUDE.md` with `docs/agents/pr-reviewer-instructions.md`; scoring restores the tree's own `CLAUDE.md`, so scoring is not affected.
- A hook program that reads its files through `CLAUDE_PROJECT_DIR` or its working directory, rather than its own location, reads the case tree's pre-fix versions.

## Other agent work to measure later, and what is not covered

- Find the defects in a pull request, find the defects in a document, and judge a name: each needs its own GHI-MD once the benchmark measures something; the counts are in the log-store directory named under "What the history supplies".
- Measuring changes to programs other than hooks; searching for better prompts automatically, as GEPA (https://github.com/gepa-ai/gepa) does; evidence from production.

## Next action

Once the user approves this GHI-MD, file the GHI with create-GHI, then ask the user for his go on the sandbox probe.

## Prior work

- GHI [Candidate skill: eval-agent-change — baseline-vs-candidate A/B with trigger cases and raw-count reporting](https://github.com/nedschorus/nedschorus/issues/23), closed as not planned on 2026-09-24, proposed comparing the current and the proposed version of a skill on trigger cases.
- The research behind this GHI-MD is `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/deep-dive-2026-10-09/deep-dive-synthesis-2026-10-09.md`. The /sanity-check run of the earlier design, and what the user decided on each finding, are in the sanity-check-record named under "What the history supplies", in `finding-dispositions.md`.
