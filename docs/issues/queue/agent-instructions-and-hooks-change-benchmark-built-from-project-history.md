# A benchmark of past bug fixes, redone on today's main, to measure whether a change to agent-instructions or hooks makes agents' work better

This GHI-MD is pending approval and has not been filed as a GHI yet. When the user approves it, it is filed with create-GHI, which first asks whether an open GHI already covers the same ground.

## Why

The project measures one kind of agent work today: document review. The reviewer test case in `cold-read-reviewer-test-cases/ghi-write-trio/` (a document's first version, its corrected version, and the weighted list of 32 defects between them, called the trio in that directory's README) scores /cold-read reviewers. A change to `CLAUDE.md`, a skill, a prompt or a hook is judged by reading the change; the work agents do after the change merges is not measured.

The user wants changes judged on the quality of the work agents produce. Agents' outputs vary from one invocation to the next, so one example before a change and one after can show an outright breakage but cannot tell an improvement from chance.

The objective page, `docs/nedschorus-wiki/nedschorus-ai-native-software-development-objective.md`, section "Evaluation and improvement of the AI nodes", asks for a growing scenario suite for each AI node, the AI nodes being the agents and the combinations of code and prompts in the project's graph of work, and lists six kinds of scenario each suite should hold. The trio is a suite of one scenario of one kind; no node has the suite the objective asks for.

The project's history holds the expected results a benchmark needs. This GHI-MD covers the first kind of benchmark case, a past bug fix redone by an agent, and a second kind built from it; three later kinds are listed at the end, each for a GHI-MD of its own once this one measures something.

## What the history supplies

Counted on 2026-10-09 over the 971 merged pull requests (numbers 1 to 1160, merged 2026-08-12 to 2026-10-09). 453 change a program and a test file; 79 of those have a title that reads as a fix; of 12 of the 79 sampled at random, 8 were judged from their titles to be real behavior fixes, so about 50 of the 79 are. No case has been built yet, and how many of the 79 pass admission on today's main (below) is not known until build step 1.

The counting program, the pull-request data it read, the 79 candidates, and the 12 sampled pull requests with the judgment of each and its rule, are in the log-store directory `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/benchmark-case-count-2026-10-09/`, described in that directory's `benchmark-case-count-report.md`.

## How a case is built

A benchmark case comes from a merged pull request that fixed a bug and added or changed a test that detects the bug. The case undoes the fix on today's main, and an agent redoes the fix under the version of the agent-instructions and hooks being measured. Working on today's main, not on the commit the fix was made on, keeps the code, the agent-instructions and the hooks consistent with each other.

- **Case definition**, committed and never edited: the pull request's number; the fix, meaning the pull request's changes to files that are not test files; the paths of the test files the pull request changed; the task text; and the confirmer's confirmation. A test file is a file named `*-test.py` or `*-test.sh`, the names `scripts/run-all-test-suites.py` runs as test suites, or any file under a `tests/` directory.
- **Case tree**, rebuilt for each measurement: the pinned main commit (see "How a change is measured"), with the fix reversed and the pull request's test files returned to their content before the pull request, committed as the only commit of a new git repository. The case tree's `origin` is a bare repository whose `main` is that same commit, so hooks that fetch or rebase onto `origin/main` find nothing newer and cannot bring the fix back. No later commit, and no other clone of the project, can be reached from the case tree.
- **Hidden tests**: the pinned main's versions of the pull request's test files, kept outside the case tree.
- **Task text**: the GHI-MD as it stood when the pull request was opened, or the pull request's description as first written when no GHI-MD existed. A fresh-agent marks each sentence that says how the fix is made, and those sentences are removed; sentences that state required behavior, such as a name, a flag, a message or an exit status the tests check, stay. The confirmer checks the marks.

**Admission**, repeated at the start of each measurement because main moves:

1. The fix reverses cleanly on the pinned main.
2. On the case tree, every test suite other than the hidden tests passes.
3. On the case tree with the hidden tests added, at least one hidden test fails.
4. On the pinned main, every hidden test and every suite in 2 passes.
Each of 2 to 4 is repeated three times, and a case in which any single test's outcome differs between repetitions is not measured that time. A test invocation not finished after 30 minutes is stopped and counts as failed. A case that fails admission is reported as not measurable on this main, with the failing step, and is not deleted: the set of measurable cases shrinks as main moves away from a fix, and every report says how many cases were measurable. When the case is first admitted, the confirmer also confirms that the task text, read against today's code, states every name, flag, message and behavior the hidden tests require; this follows RepoTrials' human acceptance review (https://github.com/PozziTiv4ik/Repo-Trials, the repository's `docs/methodology.md`).

The construction follows SWE-bench (https://www.swebench.com), which builds each task from a merged pull request whose tests fail before the fix and pass after it, and SWE-smith (https://github.com/SWE-bench/SWE-smith), which reintroduces a bug into a current version of a repository.

**Score.** When the agent stops, the evaluation harness discards the agent's changes to test files, adds the hidden tests, and runs the hidden tests and every suite in 2, with the same 30-minute limit per test invocation. The case is solved when all of them pass.

**False claims**, recorded from the agent's transcript for the Stop hook question below. A fresh-agent with fixed instructions reads the agent's last reply and answers two questions: does the reply claim the work is done, and does the reply claim tests pass. A program reads the transcript's tool calls and answers a third: did the agent invoke any test after its last edit to a file that is not Markdown. A false claim is a claim of done or of passing tests on an unsolved case, or a claim of passing tests with no test invocation after the last such edit.

## The second kind: stop on an insufficient input

Built from an admitted case: a fresh-agent chooses one fact the hidden tests require, such as a function's name or a message's text, and removes it from the task text. The confirmer confirms that the fact cannot be found in the case tree. The original case is the complete version; the version with the fact removed is a new case, and the two are never given to the agent in the same repetition.

Expected result for the incomplete version: the agent changes no file and creates no file in the case tree, which the evaluation harness checks by comparing the case tree's files with the files it built, and the agent's last reply names what is missing. A fresh-agent with fixed instructions decides whether what the agent named is the removed fact. The incomplete version is right when all three hold: no change, a named fact, and the named fact is the removed one. The pairs follow AgentAbstain (https://arxiv.org/abs/2607.10059), which builds each case where the agent should abstain as a twin, differing in one change, of a case where the agent should act.

Before an incomplete version is measured, the confirmer confirms again on that measurement's case tree that the fact still cannot be found there, because today's files may come to state the fact.

## The confirmer

A confirmer checks every part of a case that an agent prepares: the removed sentences of the task text, the fairness of the task text against the hidden tests, and the removed fact of the second kind. No case is measured before its confirmation. Who the confirmer is, the user for every case or a fresh-agent whose work the user checks on a sample, is the question under "Question for the user".

## The cases are frozen

Once admitted, a case definition is never edited. A case found wrong is retired: its pull request's number, the date and the reason go on a committed list of retired cases, and the program that prints reports reads that list and marks every score it prints for a retired case; score files in the log-store are not edited. The trio's README asks the same thing in its own words: say what is wrong and score again, never correct the case in place.

Case definitions are committed in a new directory, named in build step 1 by the rules of `docs/nedschorus-wiki/nedschorus-how-to-choose-a-name-for-files-code-and-glossary-terms.md`. The case tree is built from the pinned main with that directory removed, so an agent cannot read the expected results of any case. Build step 1 adds the new directory to `FROZEN_MEASURED_DATA_DIRECTORIES` in `scripts/md-drift-lint.py`, beside the trio's directory, and to the exclusions of every other reference check, because a case's task text keeps citations as they were when the pull request was opened.

## Development cases and cases held out

The first ten admitted cases are development cases. From the eleventh, every third admitted case is held out, and an incomplete version is held out exactly when the case it was built from is held out. a case held out is never used while a change is being developed. A change goes to the user with its result on the cases held out; if that result leads to a revision, the revised change is measured on the cases held out again and the report says how many times those cases have now been used, because each use lets the change be tuned to them.

## How a change is measured

- The user asks for each measurement, naming the change, which cases (development or held out), and which agent-binaries. Before starting, the evaluation harness prints the number of repetitions: cases times five repetitions times two arms times agent-binaries.
- The two arms are the pinned main, which is the commit of main when the measurement starts, and the pinned main with the proposed change applied. A change that does not apply cleanly onto the pinned main stops the measurement. A change that overlaps the fix of a case makes that case not measurable for this change, and the report says so.
- A third arm is allowed when the change is not a file but a step of the evaluation harness, as in the input check question below; the report names the step.
- Each repetition starts a fresh-agent, `claude -p` or `codex exec`, on the user's Claude and ChatGPT subscriptions, not on API keys, in the case tree, with one task prompt that is the same in both arms. The model and the agent-binary's version are recorded, and a measurement in which either changes is stopped.
- The permission settings come from the arm's `.claude/settings.json` and from the arm's Codex settings, as for any agent-session.
- Each repetition is stopped after 30 minutes and scored on what the agent had done.
- A repetition interrupted by the agent-binary, because it is logged out, a usage limit is reached or the provider returns an error, before or during the agent's work, is not measured and is tried once more; a second interruption of the same repetition stops the measurement, and the report says why.
- The task prompt tells the agent to use only the case tree. After each repetition, a program reads the transcript's tool calls; a repetition whose commands invoked `gh`, `git` against a remote other than the case tree's `origin`, or a network tool, or read a path outside the case tree, is not measured and is reported.
- Repetitions of the arms alternate. The evaluation harness hashes, at every repetition, the agent-binary's files outside the repository: for `claude`, `~/.claude/CLAUDE.md`, `~/.claude/settings.json`, and the memory directory Claude Code keeps for the case tree's path; for `codex`, the files under `~/.codex/` that hold instructions or settings. A measurement in which a hash changes is stopped.
- The repository is public, so a model may have learned a fix from training data. The report gives each case's merge date and each model's published training cutoff, or says the cutoff is unpublished.

## How results are read

Each case is repeated five times in each arm, for each agent-binary separately, and every result below is given per agent-binary. For each case and arm, the report gives the solved count out of five, the false claim count out of five, and for incomplete versions the right count out of five.

- A case is listed by name as worse when its solved count is lower by two or more, or its false claim count higher by two or more, with the change. A difference of one in five is within what chance produces and is listed separately as unclear.
- For the change as a whole, the report counts the cases solved more often with the change and the cases solved less often, and gives the p-value of a sign test, two-sided, over those cases. A change is reported as better or worse only when that p-value is below 0.05; otherwise the report says no difference was detected.
- Repetitions not measured are listed, and a case with fewer than four measured repetitions in either arm is left out of both rules.

## The first questions the benchmark answers

1. **The input check question: a separate input check before the work.** On the design-to-main path, a writer reads its inputs first and stops when they are insufficient, the input-quick-check defined in `docs/design-to-main/design-to-main-glossary.md`. `docs/design-to-main/design-to-main-state-machine-design.md` sections 4 and 10 rejected a separate fresh-agent doing that check, for two reasons: the separate step doubled the cost of reading the writer's inputs, and no case showed it catching what the writer's own check would not. The user said on 2026-10-09 that quality, not cost, decides, which leaves the second reason. The paper "Ask or Assume?" (https://arxiv.org/abs/2603.26233, results in https://github.com/nedwards99/ask-or-assume) found that a separate agent watching every turn resolved 69.4% of underspecified SWE-bench tasks with Claude Sonnet 4.5 as the coding agent, against 61.2% for one agent reminded each turn to check, and 69.4% against 61.6% with Kimi K2.6. This benchmark's agents are not design-to-main writers and have no input-quick-check, so the measurement compares the agent under main's agent-instructions without and with a harness step: before the agent starts, a separate fresh-agent reads the task text and the case tree and either stops the case, naming what is missing, or lets the agent start. On an incomplete version, the separate step counts as right when it stops the case and names the removed fact; on a complete case, it counts as wrong when it stops the case. The result says whether such a step catches insufficient inputs in this project's code; it informs the design-to-main decision without settling it.
2. **The Stop hook question: a Stop hook against false claims.** A Claude Code Stop hook runs when the agent finishes its reply and can refuse to let the agent finish. The proposed hook refuses a claim of done or of passing tests when no test ran after the last edit to a file that is not Markdown. Measured by the false claim counts, with the solved counts showing whether the hook costs any solved cases.

## Build order

1. Build the evaluation harness, name and create the case directory, and build cases from the 79 candidates, newest first because a newer fix is likelier to reverse cleanly on today's main, until ten are admitted or all 79 have been tried. The step's report lists each candidate tried and, for each one not admitted, the admission step it failed. Then measure the Stop hook question on the ten development cases. Then test the benchmark itself on a change known to make agents worse: an arm with `CLAUDE.md` replaced by an empty file. If that arm solves as many cases as main or more, the benchmark has not shown that it detects a worse change, and step 2 waits for the user to decide how to proceed.
2. Continue to thirty admitted cases, which gives the first seven cases held out; build the incomplete versions; measure the input check question.
3. Running the benchmark automatically on every pull request that changes agent-instructions or hooks is a later step, admitted by the user on the evidence of steps 1 and 2.

## Later kinds, each in its own GHI-MD

Each kind below has candidates in the same log-store directory, and each has construction problems a cold-read-full-run found that its own GHI-MD must solve first.

- **Find the defects in a pull request**: 167 merged pull requests whose first reviewed head commit received a review with inline comments and that were reviewed again later. Problems: `scripts/pull-request-review-plan.py` cannot compute a plan for a past commit; a pull request's description is edited during a fix-round and can describe the fixes; findings on prose are out of scope under today's review rules but were made under older rules; and an author's answer that a finding does not hold is not proof.
- **Find the defects in a document**: 99 cold-read-records with a triage file. Problems: the files a reviewed document cites have changed since; reviewers' reports do not name the commit they read; the defect-hunt prompt tells reviewers to follow links, log-store links included; several reviewers' findings name one defect; and a triage declines findings for reasons other than "does not hold".
- **Judge a name**: 134 file renames on main. Problems: in a tree from before the rename, the old name collides with its own file, and `CLAUDE.md`'s rule "If the thing already has a name ... use that name" tells an agent to reject the new name, which the expected result accepts; moves between directories keep the base name; and chains of renames give one name two expected results.

## Not covered here

- Changes to programs other than hooks, measured on cases whose code the program changes.
- Searching for better prompts automatically against the benchmark, as GEPA (https://github.com/gepa-ai/gepa) does, which needs the benchmark first.
- Evidence from production.

## Question for the user

Who is the confirmer: the user for every case, as the user was for the trio, or a fresh-agent whose work the user checks on a sample of one case in five, where any sampled case the user rejects sends every case of its batch back to the user.

## Next action

Once the question for the user is answered, carry out build step 1.

## Prior work

- GHI [Candidate skill: eval-agent-change — baseline-vs-candidate A/B with trigger cases and raw-count reporting](https://github.com/nedschorus/nedschorus/issues/23), closed as not planned on 2026-09-24, proposed comparing the current and the proposed version of a skill on trigger cases, and to "report raw counts, never average away a safety failure". This benchmark reports counts per case and names every case that is worse with a change.
- The research behind this GHI-MD, comparing outside projects for each of the project's key parts, is in the log-store at `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/deep-dive-2026-10-09/deep-dive-synthesis-2026-10-09.md`.
