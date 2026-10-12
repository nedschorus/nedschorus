# A pilot of three past bug fixes, redone by agents on the code as it stood before each fix, to learn whether a benchmark of agent-instructions and hooks can be built from the project's history

This GHI-MD is pending approval and has not been filed as a GHI yet. When the user has approved it, it is filed with create-GHI, which refuses when an open GHI already covers the same ground.

## Why

A change to `CLAUDE.md`, a skill, a prompt or a hook is judged today by reading the change and by its own tests; its effect on the work agents do is not measured. The user wants changes judged on the quality of the work agents produce. Agents' outputs vary from one invocation to the next, so measuring that needs many tasks with known right answers, run repeatedly. The project's merged bug fixes, each with a test that catches its bug, are such tasks.

Whether such tasks can be built from this project's history, and whether agents' runs on them can be read and scored, is not known. A full benchmark design went through five cold-read-full-runs and one sanity-check, and each round found about fifty gaps in rules for a program nobody had built. This GHI-MD builds three tasks and runs them, so that the next design rests on what happened.

## Words used here

- A **case** is one task built from one merged pull request that fixed a bug and added or changed a test that detects it.
- The **pre-fix tree** of a case is the files of the first parent of the pull request's merge commit: main as it stood just before the fix merged.
- The **hidden tests** of a case are the pull request's test files as they stand at its merge commit. A test file is a file named `*-test.py` or `*-test.sh`, or any file under a directory named `tests`.
- An **arm** is one version of the agent-instructions and hooks the agent works under.
- An arm's **instruction package** is a directory holding `CLAUDE.md`, `AGENTS.md`, `.claude/`, `docs/agents/`, every program a hook in that `.claude/settings.json` runs, and every project file those programs load.
- The **evaluation harness** is the program this GHI-MD's work builds to construct cases, run the pilot and print its report.

## What the history supplies

A count made on 2026-10-09 covered the 971 merged pull requests numbered 1 to 1160: 79 change a program and a test file and have a title that reads as a fix, and 37 of those merged after `scripts/run-all-test-suites.py` first merged, on 2026-09-21. The count, its program and the list are in `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/benchmark-case-count-2026-10-09/`.

Building a case by undoing the fix on today's main was tried and rejected: on main of 2026-10-10 the reversal applied cleanly for only 11 or 12 of the 79, and main takes 20 to 65 merges a day. On the pre-fix tree of 8 sampled pull requests (72, 102, 200, 307, 416, 584, 822 and 1160), the merged test failed before the fix and passed after it in all 8. Both trials are in `fresh-eyes-claude.md` of the sanity-check-record `nedlern@ned-box:/home/nedlern/nedschorus-logs/sanity-check-records/2026-10-10-agent-instructions-and-hooks-change-benchmark-built-from-project-history/`.

## Step 1: the sandbox probe

Each invocation of the agent happens inside one bubblewrap sandbox that the evaluation harness starts. The sandbox shows the case's tree, read and write; the arm's instruction package, read only; a private home directory holding copies of `~/.claude/CLAUDE.md`, `~/.claude/settings.json`, the programs that settings file runs, and the login files `claude` needs; and temporary directories. Every other checkout, the log-store, other agent-sessions' transcripts and GitHub's credentials are absent. Network access stays open, because the model needs it.

On ned-box a second bubblewrap cannot start inside a first (`kernel.apparmor_restrict_unprivileged_userns = 1`), and `scripts/run-all-test-suites.py` runs each suite in a bubblewrap of its own. So the sandbox sets `RUN_ALL_TEST_SUITES_INSIDE_SIGNAL_SANDBOX`, under which the runner runs its suites without starting another, and Claude Code's own sandbox stays off. Run that way inside one bubblewrap, the runner passed 15 suites on 2026-10-10: `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/benchmark-sandbox-nesting-probe-2026-10-10.md`.

The probe starts `claude -p` inside such a sandbox and checks three things: `claude` logs in, a hook runs, and `scripts/run-all-test-suites.py` runs its suites inside the sandbox. It spends usage, so it waits for the user's go. If any of the three fails, the user decides how to go on.

## Step 2: three cases

The evaluation harness takes the 37 candidates newest first and builds cases until three pass admission. A candidate is left out when its pull request changed a file that either arm's instruction package holds, because the arm replaces those files and would bring the fix back; the harness computes that set from both arms' `.claude/settings.json`, following each hook program to the project files it loads.

- **Case tree**, built fresh for every invocation of the agent: the files of the pre-fix tree, committed as the only commit of a new git repository in a new directory, with the commit's author and committer dates set to the date of the merge commit's first parent, so that `git log` shows nothing later. When the pre-fix tree has no `scripts/run-all-test-suites.py`, the copy from main when the pilot starts is added before that commit. The case tree's `origin` is a bare repository whose `main` is that same commit, so hooks that fetch or rebase onto `origin/main` find nothing newer.
- **The arm laid over the case tree**: the harness replaces the case tree's `CLAUDE.md`, `AGENTS.md`, `.claude/` and `docs/agents/` with the arm's copies, and rewrites every hook command in `.claude/settings.json` to an absolute path into the arm's instruction package. The case tree's own `scripts/` and `nc-systems/` are not touched: they hold the code the agent fixes.
- **Hidden tests**: kept outside the case tree. Before any test run of the harness, they are copied in and staged with `git add -f`, because the runner runs tracked suites only and `-f` stages a path the tree's `.gitignore` would skip.
- **Bug report**: written by a fresh-agent who sees the hidden tests and the output of running them on the pre-fix tree, and never the fix or the pull request's description. The report says what goes wrong and what should happen instead, and states every name, flag, message and exit status the hidden tests check. One of SWE-smith's strategies for writing a task's text (arXiv 2504.21798, the appendix on issue generation) works the same way, from a failing test's source and its execution logs without the patch.

**Admission**, each of its two tests run three times; a case in which any test suite's outcome differs between test runs is not admitted:

1. On the case tree with the hidden tests, at least one hidden test suite exits with a failure, and every test suite that is not a hidden test passes.
2. On the merge commit's files with the hidden tests, every test suite passes.

The user then reads each of the three bug reports beside its hidden tests and confirms that it states what the tests require and nothing that reveals the fix. A case he rejects is replaced by the next candidate.

## Step 3: two arms, one invocation each

The two arms are an instruction package cut from main when the pilot starts, and the same package with `CLAUDE.md` empty. The second is expected to make agents worse; it is the cheapest change that exercises the overlay, and a pilot that cannot tell it apart from the first says something about the benchmark.

Each case runs once in each arm, one invocation of the agent at a time on the machine: `claude -p` with the permission mode `bypassPermissions`, on the user's Claude subscription, inside the sandbox, with a task prompt that gives the bug report, tells the agent to work only in the case tree, to finish by saying what it did or what is missing, and not to push. The agent's work is stopped after 30 minutes.

**Scoring.** The harness puts back the case tree's own `CLAUDE.md`, `AGENTS.md`, `.claude/` and `docs/agents/`, discards the agent's changes to those paths and to test files, adds and stages the hidden tests, and runs the `scripts/run-all-test-suites.py` of main when the pilot started, with `--checkout <case tree>`. The case is solved when the runner exits 0.

## Step 4: the pilot report, and a stop

The report shows, for each case and arm:

- the bug report the agent got;
- what the agent did: the commands it ran and the files it changed;
- its last reply;
- the hidden tests' verdict;
- anything that broke: a guard refusing the agent's edits, a hook writing outside the case tree, a hidden test that a correct fix fails because it checks an exact message, a sandbox path the agent needed and lacked.

The user or prime-intellect reads every transcript. The user then decides from the report whether a second GHI-MD, for the full benchmark, is written.

## Decided by the user; to be specified from the pilot's evidence

The user decided each of these in the approval-walks on this GHI-MD's sanity-check, `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/agent-instructions-and-hooks-change-benchmark-sanity-check-triage-2026-10-10-minutes.md` and `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/benchmark-walk-items-10-and-11-and-cold-read-triage-sentence-2026-10-10-minutes.md`. The full benchmark's GHI-MD specifies them, with what the pilot shows.

- Each measurement request names its deciding measure, its repetitions and the drop in solved cases that counts as no cost; an unclear result is measured once more, and the second result decides.
- Results per case and overall by a two-sided sign test, with the statement of what ten cases can detect.
- The measure of false claims: the last change found from the files as well as the edit tools, and a test run counted only when its suites ran to the end.
- The Stop hook question, measured by the count of false claims, with the hook using the same rules.
- The input check question, under standing decisions 21 and 26 on the objective page.
- Incomplete versions, built after the first ten cases: the missing fact picked from a list code makes, checked absent with `git grep -F`.
- Judging agents answer in fixed formats that code checks.
- Admitted cases frozen: a hash guard, a retire command, and the case directory in `FROZEN_MEASURED_DATA_DIRECTORIES`.
- Candidates listed from GitHub by the harness.
- No held-out cases until the benchmark runs on every pull request.
- `claude` only; Codex later.

## Known limits

- A bug report written from a test is more exact than most real bug reports.
- The pre-fix tree holds the old version of a changed test file beside the code; the agent may read it.
- The repository is public, so a model may have learned a fix from training data.
- The pilot's agents have no GitHub, no other checkouts and no long conversation, unlike real agent-seats.

## Later kinds and not covered

- Find the defects in a pull request, find the defects in a document, and judge a name: each needs its own GHI-MD once the benchmark measures something; the counts are in the log-store directory named under "What the history supplies".
- Changes to programs other than hooks; searching for better prompts automatically, as GEPA (https://github.com/gepa-ai/gepa) does; evidence from production.

## Next action

Once the user approves this GHI-MD, file the GHI with create-GHI, then ask the user for his go on the sandbox probe.

## Prior work

- GHI [Candidate skill: eval-agent-change — baseline-vs-candidate A/B with trigger cases and raw-count reporting](https://github.com/nedschorus/nedschorus/issues/23), closed as not planned on 2026-09-24, proposed comparing the current and the proposed version of a skill on trigger cases.
- The research behind this GHI-MD is `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/deep-dive-2026-10-09/deep-dive-synthesis-2026-10-09.md`. The sanity-check of the full design, and what the user decided on each finding, are in the sanity-check-record named under "What the history supplies", in `finding-dispositions.md`.
