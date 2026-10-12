# A benchmark of past bug fixes, redone on the code as it stood before each fix, to measure whether a change to agent-instructions or hooks makes agents' work better

This GHI-MD is pending approval and has not been filed as a GHI yet. When the user has approved it and answered the question at its end, it is filed with create-GHI, which refuses when an open GHI already covers the same ground.

## Why

The project measures one kind of agent work today: document review. The reviewer test case in `cold-read-reviewer-test-cases/ghi-write-trio/` (a document's first version, its corrected version, and the weighted list of 32 defects between them, called a trio by `cold-read-reviewer-test-cases/README.md`) scores /cold-read reviewers. A change to `CLAUDE.md`, a skill, a prompt or a hook is judged by reading the change and by its own tests; its effect on the work agents do is not measured.

The user wants changes judged on the quality of the work agents produce. Agents' outputs vary from one invocation to the next, so one example before a change and one after can show an outright breakage but cannot tell an improvement from chance.

The objective page, `docs/nedschorus-wiki/nedschorus-ai-native-software-development-objective.md`, section "Evaluation and improvement of the AI nodes", asks for a growing scenario suite for each AI node and lists six kinds of scenario each suite should hold. The trio is a suite of one scenario of one kind.

The project's history holds the expected results a benchmark needs. This GHI-MD covers one kind of benchmark case, a past bug fix redone by an agent, and, where one can be built, an incomplete version of a case. Three later kinds are listed at the end, each for a GHI-MD of its own once this one measures something.

## Words used here

- A **test file** is a file named `*-test.py` or `*-test.sh`, which are the files `scripts/run-all-test-suites.py` runs as test suites, or any file under a directory named `tests`. A **test suite** is one `*-test.py` or `*-test.sh` file. Every test run in this GHI-MD goes through `scripts/run-all-test-suites.py`, which judges each suite by its exit code alone; a skipped test case does not change a verdict and is listed beside it.
- A **case** is one benchmark case: a complete version or an incomplete version (below). Its **identifier** is the pull request's number for a complete version, and the number followed by `-incomplete` for an incomplete version.
- The **pre-fix tree** of a case is the files of the first parent of the pull request's merge commit: main as it stood just before the fix merged. It never changes, so a case built on it stays valid however main moves.
- The **pinned main** is the commit of main when a measurement starts. The two arms' instruction packages (below) are cut from it.
- An **arm** is one version of what is measured: the agent-instructions and hooks of the pinned main, or those of the pinned main with the proposed change applied.
- An arm's **instruction package** is a directory the evaluation harness cuts from the arm's commit, holding `CLAUDE.md`, `AGENTS.md`, `.claude/`, `docs/agents/`, every program a hook in that `.claude/settings.json` runs, and every project file those programs load.
- A **repetition** is one fresh-agent started once on one case in one arm; a repetition started again after an interruption is the same repetition.
- The **evaluation harness** is the program this GHI-MD's work builds to construct cases, run measurements and print reports.
- A case is **admitted** when it passes admission and its confirmation, once, when it is built.

## What the history supplies

Counted on 2026-10-09 over the 971 merged pull requests (numbers 1 to 1160, merged 2026-08-12 to 2026-10-09). 453 change a program and a test file; 79 of those have a title that reads as a fix. Of 12 of the 79 sampled at random, 8 were judged from their titles to be real behavior fixes. A review of the 79 during this GHI-MD's sanity-check estimates 24 to 52 usable cases: 11 only add code, 20 touch instruction or hook files, and 22 change more than three files. 37 of the 79 merged after `scripts/run-all-test-suites.py` merged on 2026-09-21; on an older pre-fix tree, today's `CLAUDE.md` tells the agent to run a program that is not there. No case has been built yet.

Building on today's main was tried and rejected. Undoing each of the 79 fixes on main of 2026-10-10 applied cleanly for only 11 or 12 of them, all merged in the preceding two weeks, and main takes 20 to 65 merges a day. On the pre-fix tree of 8 sampled pull requests (72, 102, 200, 307, 416, 584, 822 and 1160), the merged test failed before the fix and passed after it in all 8.

The counting program, the pull-request data it read, the list of the 79 and the 12 sampled pull requests are in the log-store directory `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/benchmark-case-count-2026-10-09/`, described in that directory's `benchmark-candidate-case-count-from-project-history-report.md`. The reversal and pre-fix trials are in `fresh-eyes-claude.md` of the sanity-check-record `nedlern@ned-box:/home/nedlern/nedschorus-logs/sanity-check-records/2026-10-10-agent-instructions-and-hooks-change-benchmark-built-from-project-history/`.

## How a case is built

A case comes from a merged pull request that fixed a bug and added or changed a test that detects the bug. An agent gets the pre-fix tree and a bug report, and redoes the fix under the arm being measured; the pull request's own tests, hidden from the agent, say whether it succeeded.

A candidate is left out when its pull request changed a file that any arm's instruction package holds, because the arms replace those files and would bring the fix back. The evaluation harness computes that set from the pinned main's `.claude/settings.json`, following each hook program to the project files it loads; six of the twenty hook programs on main of 2026-10-10 load another file.

- **Case definition**, committed in the case directory: the identifier; the pull request's number and merge commit; the paths of the pull request's test files; the bug report; and the confirmer's confirmation, with the commit it was made against.
- **Case tree**, built fresh for every repetition: the files of the pre-fix tree, committed as the only commit of a new git repository in a new directory, so `git log` shows nothing after the fix's date. The case tree's `origin` is a bare repository whose `main` is that same commit, so hooks that fetch or rebase onto `origin/main` find nothing newer.
- **The arm laid over the case tree**: in the case tree, the harness replaces `CLAUDE.md`, `AGENTS.md`, `.claude/` and `docs/agents/` with the arm's copies, and rewrites every hook command in `.claude/settings.json` to an absolute path into the arm's instruction package, which is mounted read-only beside the case tree. The case tree's own `scripts/` and `nc-systems/` are not touched: they hold the code the agent fixes and the programs `CLAUDE.md` tells it to run.
- **Hidden tests**: the pull request's test files as they stand at its merge commit, kept outside the case tree.
- **Bug report**: written by a fresh-agent, the bug-report writer, who sees the hidden tests and the output of running them on the pre-fix tree, and never the fix or the pull request's description. The report says what goes wrong and what should happen instead, as a user reporting a bug would, and states every name, flag, message and exit status the hidden tests check. One of SWE-smith's strategies for writing a task's text (https://github.com/SWE-bench/SWE-smith; arXiv 2504.21798, the appendix on issue generation) writes a task the same way, from a failing test's source and its execution logs without the patch.

**Admission**, once, when the case is built:

1. On the case tree with the hidden tests added, at least one hidden test suite exits with a failure, and every other test suite passes.
2. On the merge commit's files with the hidden tests, every test suite passes.

Each is run three times; a case in which any test suite's outcome differs between test runs is not admitted. A case that fails admission is listed in the build report with the admission test it failed.

**Confirmation.** When a case is admitted, the confirmer confirms that the pull request fixed a bug, and that the bug report states every name, flag, message and behavior the hidden tests require and nothing that reveals how the fix is made; the second follows RepoTrials' human acceptance review (https://github.com/PozziTiv4ik/Repo-Trials, the repository's `docs/methodology.md`). The construction follows SWE-bench (https://www.swebench.com), which builds each task from a merged pull request whose tests fail before the fix and pass after it.

**Score of a complete version.** When the agent stops, the evaluation harness puts back the case tree's own `CLAUDE.md`, `AGENTS.md`, `.claude/` and `docs/agents/`, discards the agent's changes to those paths and to test files, adds the hidden tests and stages them with `git add`, because the runner runs tracked suites only, and runs the pinned main's `scripts/run-all-test-suites.py --checkout <case tree>`. The case is solved when the runner exits 0.

**False claims.** A fresh-agent, the claim reader, reads the agent's last reply and answers two questions: does the reply say the task is done, and does the reply say all tests pass. The evaluation harness answers a third: did a test run end after the agent's last change. The last change is the later of the agent's last Edit or Write tool call and the newest change to a file in the case tree whose content differs from the tree as built; files git ignores, such as `__pycache__`, do not count. A test run counts when its suites ran to their end, pass or fail: `scripts/run-all-test-suites.py` printed its `SUMMARY:` line, or a test suite run directly exited on its own; an invocation of the runner that the machine lock refused is not a test run. "All tests pass" means a statement that the tests the agent ran passed, without a stated exception. A false claim is a reply that says the task is done or all tests pass on an unsolved case, or that says all tests pass when the third answer is no. False claims are counted on complete versions only. A repetition that ends without a reply has no claim.

## The incomplete version

Built in build step 2 only, from an admitted complete version. The evaluation harness lists the names and quoted strings that appear both in the bug report and in the hidden tests. A fresh-agent picks one of them that a careful agent could not choose correctly without being told, and the harness removes it from the bug report. The case definition stores the removed literal and the complete version's identifier. When the case is built, `git grep -i` on the case tree must find the literal nowhere; a hit means the agent could find it, and the pick is refused. A complete version with no candidate that passes has no incomplete version.

Expected result: the agent leaves the case tree as built, and its last reply names what is missing. When the agent stops, the evaluation harness compares every tracked file and every untracked file not ignored by `.gitignore` with the files it built; a file changed and restored before the agent stopped counts as unchanged. A fresh-agent, the fact judge, given the removed literal, decides whether the reply names the removed fact, meaning that the reply says which fact is missing, such as "the message the refusal must print", without needing to supply its value; a reply that also names other things still counts. The incomplete version is right when both hold: the tree is as built, and the fact judge says yes. An incomplete version is scored only as right or not right.

The pairs follow AgentAbstain (https://arxiv.org/abs/2607.10059), which builds each case where the agent should abstain as a twin, differing in one change, of a case where the agent should act.

## The confirmer and the judging agents

The confirmer checks every case an agent prepares. Who the confirmer is, the user for every case or a fresh-agent whose work the user checks on a sample, is the question under "Question for the user".

The bug-report writer, the claim reader, the fact judge, and the separate input check of the input check question below each run from instructions committed in the case directory, which are the same in both arms. A change to those instructions is made by the user's decision, not measured by this benchmark, because the instructions score the measurement; every report names the hash of each instruction file. Each runs as `claude -p` with `--setting-sources user` in a new empty directory outside every repository, so no project `CLAUDE.md` or project hook reaches it. Each answers in a fixed format that code checks, yes or no for the claim reader and the fact judge, start or stop with the missing fact for the input check; an answer not in that format is asked for once more, and a second such answer leaves the repetition unscored and listed in the report.

## The cases are frozen

Once admitted, a case definition is not edited apart from its confirmation. The case directory's test suite compares each admitted definition with the git hash recorded when it was admitted and fails on a difference. A case found wrong is retired with the evaluation harness's retire command, which checks the identifier exists and records it, the date and the reason in `benchmark-retired-cases.md` in the case directory; a case that can be repaired is retired and its repaired form admitted as a new case, with an identifier followed by `-2`. The evaluation harness never measures a retired case, and marks every earlier score of a retired case when it prints a report; score files in the log-store are not edited.

The case directory is a new top-level directory, named in build step 1 by the rules of `docs/nedschorus-wiki/nedschorus-how-to-choose-a-name-for-files-code-and-glossary-terms.md`. Build step 1 adds it to `FROZEN_MEASURED_DATA_DIRECTORIES` in `scripts/md-drift-lint.py`, beside `cold-read-reviewer-test-cases`, which excludes the whole directory from that lint and from `scripts/dangling-path-citation-check.py` and `scripts/stale-code-citation-check.py`, because a bug report names files as they were on its pre-fix tree.

The evaluation harness builds each of these mechanisms when the pilot or the first ten cases first need it.

## How a change is measured

- The user asks for each measurement, naming the change as a branch or a pull request, the cases, the one measure that decides the question, the number of repetitions, how large a drop in solved cases still counts as no cost, and what result counts as unclear. The evaluation harness records the change's commit and prints the number of repetitions before starting: cases times repetitions times two arms.
- The two arms' instruction packages are cut from the pinned main and from the pinned main with the change applied. A change that does not apply cleanly stops the measurement. The harness compares the two packages and refuses to measure when any file differs outside the paths the change touches. A case is not measurable for a measurement when either package contains one of the names or quoted strings of its hidden tests that its pre-fix tree does not, because a newer instruction could give the fix away.
- Each repetition runs `claude -p` with the permission mode `bypassPermissions`, on the user's Claude subscription, not an API key, with one task prompt committed in the case directory and the same in both arms. The model and the agent-binary's version are recorded, and a measurement in which either changes stops, and the report says why.
- Each repetition runs inside one bubblewrap sandbox the evaluation harness starts. The sandbox shows the case tree, read and write; the arm's instruction package, read only; a private home directory holding copies of `~/.claude/CLAUDE.md`, `~/.claude/settings.json`, the programs that settings file runs, and the login files `claude` needs; and temporary directories. Every other checkout, the log-store, other agent-sessions' transcripts and GitHub's credentials are absent. The sandbox has a process namespace of its own, so stopping it stops every process the repetition started, and it sets `RUN_ALL_TEST_SUITES_INSIDE_SIGNAL_SANDBOX` so that the test runner, which cannot start a second bubblewrap inside the first on ned-box (`kernel.apparmor_restrict_unprivileged_userns = 1`), runs its suites inside the repetition's sandbox; Claude Code's own sandbox stays off for the same reason. Network access stays open, because the model needs it. The probe behind this is `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/benchmark-sandbox-nesting-probe-2026-10-10.md`.
- The harness hashes the files copied into the private home directory at every repetition; a measurement in which a hash changes stops, and the report says why. Each repetition starts with an empty `~/.claude/projects/`, so Claude Code keeps no memory from one repetition to the next.
- Repetitions run one at a time on the machine, so an agent's own test run never meets another holding the runner's lock; scoring runs take the runner's default lock too, and a scoring run's 30-minute limit counts from when the runner holds the lock. On each case the two arms run back to back, and which arm goes first alternates from one repetition to the next.
- A repetition is stopped after 30 minutes and scored on the case tree as it is then; it has no last reply. A repetition interrupted by a usage limit is paused until the limit resets and then started again from a new case tree; a measurement paused for more than 24 hours stops, and the report says why. A repetition interrupted because `claude` is logged out or the provider returns an error is started once more; if that one is interrupted too, the measurement stops, and the report says why.
- The task prompt gives the agent the bug report, tells it to work only in the case tree, to finish by saying in its last reply what it did, or what is missing when it cannot do the task, and not to push or open a pull request. After each repetition, the evaluation harness reads the transcript; a repetition is not measured, and is reported, when a command invoked `curl`, `wget` or `gh`. A download by another program, such as a Python script, is not seen.
- The repository is public, so a model may have learned a fix from training data. The report gives each case's merge date and the model's published training cutoff, or says that the cutoff is unpublished.

## How results are read

The report gives, for complete versions and incomplete versions separately, for each case and arm, out of the measured repetitions, the solved count and the false claim count, or for an incomplete version the right count. A case with fewer than four measured repetitions in either arm is left out of the rules below, and is listed.

- **The change as a whole**: on a measure, a case is better with the change when its rate is higher with the change for solved and right, or lower for false claims, and worse in the opposite case; a case with equal rates is neither. The report counts the cases better and the cases worse, and gives the p-value of a two-sided sign test over those cases. Only the measure the request named decides: the change is reported better or worse on it when that p-value is below 0.05, and no difference is detected otherwise; the other measures are reported as information. With ten cases a sign test reaches 0.05 only when at least six cases differ and all six differ the same way, so build step 1 can detect only a large effect, and "no difference was detected" there is not evidence that a change does nothing. When the result is what the request named as unclear, the measurement is run once more with new repetitions, and that second result decides.
- **Single cases**: a case is listed by identifier when its rate on a measure differs between arms by 0.4 or more, such as two in five. Such a listing points a reader at a case to examine; with five repetitions per arm, a difference that size also arises by chance, so the listing is not a verdict.
- When fewer than six cases are measurable, the report says that the sign test cannot reach 0.05 and gives the counts only.

## The first questions the benchmark answers

1. **The input check question.** On the design-to-main path, a writer reads its inputs first and stops when they are insufficient, the input-quick-check defined in `docs/design-to-main/design-to-main-glossary.md`. `docs/design-to-main/design-to-main-state-machine-design.md` sections 4 and 10, and standing decision 21 on the objective page, rejected a separate fresh-agent doing that check, because it would double the cost of reading the writer's inputs "without a demonstrated gain". Standing decision 26 on the same page, "Evidence first; cost is a bound", makes the gain the question. The paper "Ask or Assume?" (https://arxiv.org/abs/2603.26233, results in https://github.com/nedwards99/ask-or-assume) found that a separate agent watching every turn, which makes the coding agent ask a simulated user when it finds the task underspecified, resolved 69.4% of underspecified SWE-bench tasks with Claude Sonnet 4.5 as the coding agent, against 61.2% for one agent reminded each turn to check, and 69.4% against 61.6% with Kimi K2.6. This benchmark's agents are not design-to-main writers, so the measurement compares the agent under the pinned main's agent-instructions without and with a step of the evaluation harness: before the agent starts, the separate input check reads the bug report and the case tree and either stops the repetition, naming what is missing, or lets the agent start. On an incomplete version, a repetition the step stops is right when the step names the removed fact; on a complete version, a repetition the step stops is unsolved. The result informs the design-to-main decision without settling it.
2. **The Stop hook question.** A Claude Code Stop hook runs when the agent finishes its reply and can refuse to let the agent finish. The proposed hook refuses a reply that says the task is done or all tests pass when no test run ended after the last change, by the same rule the false claim measure uses, so the hook and the scoring agree. Measured by the false claim measure, with the solved measure showing whether the hook costs solved cases. The report also counts the hook's refusals, and the turns Claude Code ended because the hook refused eight times in a row.

## Build order

1. **Probe, pilot, then ten cases.**
   - First, with the user's go because it spends usage: start `claude -p` inside the evaluation harness's sandbox with a private home directory, and check that it logs in, runs a hook, and that `scripts/run-all-test-suites.py` runs its suites inside it. If it does not, the user decides how to go on.
   - Then a pilot: build three cases from the candidates, run each once in each arm of the Stop hook question, and read every transcript and every claim reader's answer. The pilot report shows, for each case: the bug report the agent got, what the agent did, its last reply and the claim reader's answers, the hidden tests' verdict, and the Stop hook's refusals. What the pilot finds is written into this GHI-MD before more cases are built. If the pilot shows the benchmark costs more work than it can repay, the report says so.
   - Then build complete versions, newest first, from the candidates the evaluation harness lists from GitHub with this GHI-MD's test-file rule (79 on 2026-10-09), starting with those merged after 2026-09-21, until ten are admitted or the candidates run out; the confirmer works on the cases of the step as one batch. The report lists each candidate tried and, for each one not admitted, why. With fewer than ten admitted, the user decides how to go on. With ten, and after the user asks for each measurement, measure the Stop hook question, and then an arm expected to make agents worse: an instruction package whose `CLAUDE.md` is empty, with the user-level `~/.claude/CLAUDE.md` unchanged. The arm runs because scoring puts back the case tree's own `CLAUDE.md`. If that arm is not reported worse on the solved measure, the benchmark has not shown that it detects a worse change, and the user decides whether step 2 proceeds.
2. Continue to thirty admitted complete versions, taking further candidates from the 453 when the 79 run out, after a fresh-agent judges from each title whether the pull request fixes a bug, by the rule recorded with the 12-title sample, and the confirmer confirms the judgments; if the 453 run out first, the step stops there and the user decides. Build the incomplete versions, and measure the input check question.
3. Running the benchmark automatically on every pull request that changes agent-instructions or hooks is a later step, approved by the user on the evidence of steps 1 and 2. That step's GHI-MD adds a set of cases held out from development, which repeated tuning against the same cases then needs.

## Known limits

- A bug report is written after the fact, from a test; it is more exact than most real bug reports, so the benchmark measures fixing bugs whose reports are exact.
- The pre-fix tree holds the old version of a changed test file beside the code, which often names the behavior; both arms see it.
- Several pull requests can fix one underlying failure. The report groups cases from one pull-request chain, and an overall result resting on one group says so.
- Real agent-seats have GitHub, other checkouts and long conversations; these agents have none of them.

## Later kinds, each in its own GHI-MD

Each kind below has construction problems that a /cold-read of an earlier version of this GHI-MD found, which its own GHI-MD must solve first.

- **Find the defects in a pull request**: 167 merged pull requests whose first reviewed head commit received a review with inline comments and that were reviewed again later; the list is in the log-store directory above. Problems: `scripts/pull-request-review-plan.py` cannot compute a plan for a past commit; a pull request's description is edited during a fix-round and can describe the fixes; findings on prose are out of scope under today's review rules but were made under older rules; and an author's answer that a finding does not hold is not proof.
- **Find the defects in a document**: 99 cold-read-records with a triage file in `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/`, counted, not listed. Problems: the files a reviewed document cites have changed since; reviewers' reports do not name the commit they read; the defect-hunt prompt, `.claude/skills/cold-read/prompts/defect-hunt.md`, tells reviewers to follow links, log-store links included; several reviewers' findings name one defect; and a triage declines findings for reasons other than "does not hold".
- **Judge a name**: 134 file renames, from `git log --diff-filter=R --name-status origin/main`, counted, not listed. Problems: in a tree from before the rename, the old name collides with its own file, and `CLAUDE.md`'s rule "If the thing already has a name ... use that name" tells an agent to reject the new name, which the expected result accepts; moves between directories keep the base name; and chains of renames give one name two expected results.

## Not covered here

- Codex. This GHI-MD measures `claude` only. Codex has hooks of its own, with a Stop event, so a Codex version of the Stop hook can be measured once a probe shows `codex exec` runs them; Codex's own sandbox must then stay off inside the evaluation harness's.
- Changes to programs other than hooks, measured on cases whose code the program changes.
- Searching for better prompts automatically against the benchmark, as GEPA (https://github.com/gepa-ai/gepa) does, which needs the benchmark first.
- Evidence from production.

## Question for the user

Who is the confirmer: the user for every case, as the user was for the trio; or a fresh-agent whose work the user checks on one case in five of each batch, and on at least one case of a batch smaller than five, a batch being the cases one build step admits, where any checked case the user rejects sends every case of its batch back to the user. Under the second, the evaluation harness draws the sample with a recorded seed, records the user's verdicts, and refuses to measure a case of a batch sent back until the user has confirmed it.

## Next action

Once the user approves this GHI-MD and answers the question for the user, file the GHI with create-GHI, then carry out build step 1, asking the user before the probe.

## Prior work

- GHI [Candidate skill: eval-agent-change — baseline-vs-candidate A/B with trigger cases and raw-count reporting](https://github.com/nedschorus/nedschorus/issues/23), closed as not planned on 2026-09-24, proposed comparing the current and the proposed version of a skill on trigger cases, and to "report raw counts, never average away a safety failure". This benchmark reports counts per case for every case, and decides about a change by a test over cases rather than by an average.
- The research behind this GHI-MD, comparing outside projects for each of the project's key parts, is in the log-store at `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/deep-dive-2026-10-09/deep-dive-synthesis-2026-10-09.md`. Its sanity-check, and what the user decided on each finding, are in the sanity-check-record named under "What the history supplies", in `finding-dispositions.md`.
