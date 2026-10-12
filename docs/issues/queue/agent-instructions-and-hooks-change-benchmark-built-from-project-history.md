# A pilot of three past bug fixes, redone by agents on the code as it stood before each fix, to learn whether a benchmark of agent-instructions and hooks can be built from the project's history

This GHI-MD is pending approval and has not been filed as a GHI yet. When the user has approved it, it is filed with create-GHI.

## Why

A change to `CLAUDE.md`, a skill, a prompt or a hook is judged today by reading the change and by its own tests; its effect on the work agents do is not measured. The user wants changes judged on the quality of the work agents produce. Agents' outputs vary from one invocation to the next, so measuring that needs many tasks with known right answers, run repeatedly. Those of the project's merged bug fixes that came with a regression test are such tasks.

Whether such tasks can be built from this project's history, and whether agents' invocations on them can be read and scored, is not known. This GHI-MD's earlier design of the full benchmark went through five cold-read-full-runs and one /sanity-check run, and each reviewer hunting defects found about fifty gaps in rules for a program nobody had built. This GHI-MD builds three tasks and runs them, so that the second GHI-MD, for the full benchmark, rests on what happened.

## Words used here

- A **case** is one task built from one merged pull request that fixed a bug and added or changed a regression test for it; a single test inside a test suite is a test case.
- The **pre-fix tree** of a case is the files of the first parent of the pull request's merge commit: main as it stood just before the fix merged.
- A **test file** is a file named `*-test.py` or `*-test.sh`, or any file under a directory named `tests`. A **test suite** is a test file that `scripts/run-all-test-suites.py`, the test runner, runs: one named `*-test.py` or `*-test.sh`.
- The **hidden tests** of a case are the test files the pull request added or changed, as they stand at its merge commit.
- An **arm** is one version of the agent-instructions and hooks the agent works under.
- An arm's **instruction package** is a directory holding `CLAUDE.md`, `AGENTS.md`, `.claude/`, `docs/agents/`, every program a hook in that `.claude/settings.json` runs, and every project file those programs import or open.
- The **evaluation harness** is the program this GHI-MD's work builds to construct cases, run the pilot and print the pilot report.
- cold-read-full-run and sanity-check-record are defined in `.claude/skills/skills-glossary.md`.

## What the history supplies

A count made on 2026-10-09 covered the 971 merged pull requests numbered 1 to 1160: 79 change a program and a test file and have a title that reads as a fix. The count, its program and the list of 79 are in `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/benchmark-case-count-2026-10-09/`. 37 of the 79 merged after PR [Every test suite runs from one committed program, judged by its exit code](https://github.com/nedschorus/nedschorus/pull/618) added the test runner, at 2026-09-22T01:43Z: 628, 656, 688, 691, 695, 699, 701, 702, 708, 714, 728, 762, 771, 776, 800, 803, 822, 838, 881, 943, 960, 969, 971, 978, 985, 992, 1007, 1021, 1023, 1031, 1032, 1068, 1087, 1096, 1109, 1120 and 1160. Each merge commit has two parents, and none deleted or renamed a test file.

Building a case by reverting the fix on today's main was tried and rejected: on main of 2026-10-10 the revert applied cleanly for only 11 or 12 of the 79, and main takes 20 to 65 merges a day. On the pre-fix tree of 8 sampled pull requests (72, 102, 200, 307, 416, 584, 822 and 1160), the merged regression test failed before the fix and passed after it in all 8. Both trials are in `fresh-eyes-claude.md` of the sanity-check-record `nedlern@ned-box:/home/nedlern/nedschorus-logs/sanity-check-records/2026-10-10-agent-instructions-and-hooks-change-benchmark-built-from-project-history/`.

## Step 1: the sandbox probe

Each invocation of the agent and of the bug report writer happens inside one bubblewrap sandbox, with its own process namespace, that the evaluation harness starts. The sandbox shows only:

- the case tree and its bare `origin` repository, read and write;
- the arm's instruction package, read only;
- the system's programs and libraries, `claude` among them, read only;
- a private home directory, made new for each invocation, holding copies of `~/.claude/CLAUDE.md`, `~/.claude/settings.json` with Remote Control and cross-session messages turned off, the programs that settings file runs, and `~/.claude/.credentials.json`, the login file `claude` needs;
- a private temporary directory.

Other checkouts, the log-store, other agent-sessions' transcripts and GitHub's credentials are absent. Network access stays open, because the model needs it.

On ned-box a second bubblewrap sandbox cannot start inside a first (`kernel.apparmor_restrict_unprivileged_userns = 1`), and the test runner runs each test suite in a bubblewrap sandbox of its own. So the sandbox sets `RUN_ALL_TEST_SUITES_INSIDE_SIGNAL_SANDBOX`, under which the test runner runs its suites without starting another, and Claude Code's own sandbox stays off. Run that way inside one bubblewrap sandbox, the test runner passed the 15 suites that `--only-suites-whose-recorded-inputs-changed-since HEAD~1` selected, on 2026-10-10: `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/benchmark-sandbox-nesting-probe-2026-10-10.md`. The four suites that the test runner's `SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX` names fail inside the sandbox: three start a bubblewrap sandbox themselves, and the fourth runs the real `ssh`, which refuses its configuration files when they show as owned by nobody.

The probe starts `claude -p` inside such a sandbox, on main's files with the first arm laid over them, both taken from main when the user gives his go on the probe, the pilot's start, and checks three things: `claude` logs in, a hook runs, and the test runner passes every test suite but those four inside the sandbox. It spends usage, so it waits for the user's go. If any of the three fails, the user decides how to go on.

## Step 2: three cases

The evaluation harness takes the 37 candidate pull requests newest first, by merge time, and builds cases until three are admitted and confirmed. A candidate is left out when its pull request changed a file that either arm's instruction package holds, because the fixed version would then be in the case tree or in the instruction package, which the agent can read and the hooks run. The evaluation harness computes that set from both arms' `.claude/settings.json`, following each hook program to the project files it imports or opens, by a scan that is approximate and says so.

- **Case tree**, built fresh for every invocation of the agent and every test run: the files of the pre-fix tree, with the arm laid over them when an agent works in the tree, committed on branch `main` as the only commit of a new git repository in a new directory, with the commit's author and committer dates set to the date of the merge commit's first parent, so that `git log` shows nothing later. The case tree's `origin` is a bare repository whose `main` is that same commit, so hooks that fetch or rebase onto `origin/main` find nothing newer.
- **The arm laid over the case tree**: before that commit, the evaluation harness replaces the pre-fix tree's `CLAUDE.md`, `AGENTS.md`, `.claude/` and `docs/agents/` with the arm's copies, and rewrites every hook command in `.claude/settings.json` to an absolute path into the arm's instruction package, so git shows no trace of the pre-fix instruction files. The case tree's own `scripts/` and `nc-systems/` are not touched: they hold the code the agent fixes.
- **Hidden tests**: kept outside the case tree. Before any test run of the evaluation harness, they are copied in and staged with `git add -f`, because the test runner runs tracked suites only and `-f` stages a path the tree's `.gitignore` would skip.

**Admission.** Each test below runs three times, on a case tree without an arm, with the test runner of main at the pilot's start and `--checkout <tree>`, outside the sandbox. Every test run of admission and scoring takes the test runner's default lock and has one time limit, counted from then; a stopped admission test run rejects the candidate, a stopped scoring test run is unsolved.

1. On the case tree with the hidden tests, at least one hidden test suite exits with a failure, and every test suite that is not a hidden test passes.
2. On a tree built the same way from the merge commit's files, with the hidden tests, every test suite passes.

A candidate is not admitted when a test suite passes in one of a test's three test runs and fails in another.

**Bug report**, written for each admitted case by a `claude -p` agent inside the sandbox, which sees the hidden tests, the output of admission test 1 and the pre-fix tree, and never the fix or the pull request's description. The bug report says what goes wrong and what should happen instead, and states every name, flag, message and exit status the hidden tests check. It reveals the fix if it says how the code should change; naming the behavior a test checks does not.

The user then reads each of the three bug reports beside its hidden tests and the fix's diff, and confirms that it states what the tests require and does not reveal the fix. A bug report he rejects is written once more with his reason; a second rejection replaces the case with the next candidate. If the 37 candidates run out before three cases are admitted and confirmed, the user decides how to go on.

## Step 3: two arms, each case once in each

The two arms are an instruction package cut from main at the pilot's start, and the same package with `CLAUDE.md` empty. The second is expected to make agents worse; it is the cheapest change that exercises laying an arm over the case tree. With one invocation per case and arm, the pilot cannot measure an arm's effect; it shows whether the evaluation harness works and what an invocation in each arm looks like.

Each case runs once in each arm, one invocation of the agent at a time on the machine: `claude -p --permission-mode bypassPermissions`, on the user's Claude subscription, inside the sandbox, with initial-agent-instructions that give the bug report, tell the agent to work only in the case tree, to finish by saying what it did or what is missing, and not to push. After 30 minutes the evaluation harness ends the sandbox, and the case is scored as it stands.

**Scoring.** The evaluation harness puts back the pre-fix tree's own `CLAUDE.md`, `AGENTS.md`, `.claude/` and `docs/agents/`, discards the agent's changes to those paths and to test files, copies in and stages the hidden tests, and runs the test runner of main at the pilot's start, with `--checkout <case tree>`, outside the agent's sandbox, so the test runner uses its own. The case is solved when the test runner exits 0.

## Step 4: the pilot report, and a stop

The evaluation harness keeps each invocation's private home, which holds its Claude Code transcript, in the log-store. The pilot report shows, for each case and arm:

- the bug report the agent got;
- what the agent did: the commands it ran and the files it changed;
- its last reply;
- the scoring verdict, solved or unsolved, and which test suites failed;
- anything that broke: a hook that fails because it runs in the sandbox, a hook writing outside the case tree, the private home and the private temporary directory, a sandbox path the agent needed and lacked.

A guard refusing what it exists to refuse has not broken. The reader of the transcript decides what broke; an invocation in which something broke is reported as broken and is not counted as solved or unsolved. Every transcript is read, by the user or by the agent-seat prime-intellect. The user then decides from the pilot report whether the second GHI-MD, for the full benchmark, is written.

## Decided by the user; to be specified from the pilot's evidence

The user decided these in the approval-walks on the /sanity-check run of the earlier design, `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/agent-instructions-and-hooks-change-benchmark-sanity-check-triage-2026-10-10-minutes.md` and `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/benchmark-walk-items-10-and-11-and-cold-read-triage-sentence-2026-10-10-minutes.md`, except where a line says otherwise. If the user decides to write the second GHI-MD, for the full benchmark, it specifies them, with what the pilot shows; the full benchmark starts with ten cases.

- Each measurement request names its primary metric, its repetitions and its noninferiority margin, the drop in solved cases still accepted as no harm, and says which result counts as unclear; an unclear result is measured once more, with new repetitions, and the second result decides.
- Results per case and overall by a two-sided sign test, with the minimum detectable effect for ten cases; from the earlier design, not an approval-walk item.
- The measure of false claims, claims of done or of passing tests with no complete test run after the last change: the last change found from the files as well as the edit tools.
- Whether a Claude Code Stop hook that refuses a claim of done or passing tests, when no test ran after the last change, reduces false claims without costing solved cases.
- Whether a separate agent that checks a task's inputs before the agent starts catches insufficient inputs better than the agent does, the demonstrated gain that standing decision 21 of `docs/nedschorus-wiki/nedschorus-ai-native-software-development-objective.md` requires; from the user's statement of 2026-10-09, not an approval-walk item.
- Underspecified variants, cases whose bug report lacks one fact the hidden tests need, built after the first ten cases: the missing fact picked from a list code makes, checked absent from the pre-fix tree with `git grep -F`.
- LLM judges answer in fixed formats that code checks.
- Admitted cases frozen: a comparison of their git hashes with the recorded ones, a command that retires a case, and the directory holding them listed in `FROZEN_MEASURED_DATA_DIRECTORIES` of `scripts/md-drift-lint.py`.
- Candidates listed from GitHub by the evaluation harness.
- No held-out cases until the benchmark runs on every pull request.
- `claude` only; Codex later.
- A transcript check for network commands, such as `curl` and `wget`, and reads of the project on GitHub (item 2 of `finding-dispositions.md`).
- The test runs' time limit, and what follows the test runner's exit 3 (lock held) or exit 2 (could not start).
- The probe running each hook alone and recording the files it opens; hooks that find their repository from their own location, as `scripts/uncommitted-work-snapshot-hook.py` does.
- Test files outside the naming pattern, such as the captured responses under `scripts/merge-gate-test-captured-github-responses/` that PR [The merge gate enters the repository, with a test for every refusal](https://github.com/nedschorus/nedschorus/pull/691) changed.
- A usage limit or a logged-out `claude` during an invocation.
- The pilot report's further fields: skipped test cases, model, effort level and `claude` version, the 30-minute end, who read each transcript.
- The user confirming that each candidate fixed a bug.

## Known limits

- A bug report written from a test is more exact than most real bug reports; SWE-smith (arXiv 2504.21798) found that task text showing a failing test leaks what the tests check.
- The pre-fix tree holds the old version of a changed test file beside the code; the agent may read it.
- The repository is public: a model may have learned a fix in training, and an agent can read it on GitHub.
- The pilot's agents have no GitHub credentials, no other checkouts and no long conversation, unlike real agent-seats.
- A login refresh inside the sandbox reaches only the copy of the login file.
- Main's `CLAUDE.md` may name programs or flags an older pre-fix tree lacks.

## Other agent work to measure later, and what is not covered

- Find the defects in a pull request, find the defects in a document, and judge a name: each needs its own GHI-MD once the benchmark measures something; the counts are in the log-store directory named under "What the history supplies".
- Measuring changes to programs other than hooks; searching for better prompts automatically, as GEPA (https://github.com/gepa-ai/gepa) does; evidence from production.

## Next action

Once the user approves this GHI-MD, file the GHI with create-GHI, then ask the user for his go on the sandbox probe.

## Prior work

- GHI [Candidate skill: eval-agent-change — baseline-vs-candidate A/B with trigger cases and raw-count reporting](https://github.com/nedschorus/nedschorus/issues/23), closed as not planned on 2026-09-24, proposed comparing the current and the proposed version of a skill on trigger cases.
- The research behind this GHI-MD is `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/deep-dive-2026-10-09/deep-dive-synthesis-2026-10-09.md`. The /sanity-check run of the earlier design, and what the user decided on each finding, are in the sanity-check-record named under "What the history supplies", in `finding-dispositions.md`.
