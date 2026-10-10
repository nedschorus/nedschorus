# A benchmark of past bug fixes, redone on today's main, to measure whether a change to agent-instructions or hooks makes agents' work better

This GHI-MD is pending approval and has not been filed as a GHI yet. When the user approves it, it is filed with create-GHI, which refuses when an open GHI already covers the same ground.

## Why

The project measures one kind of agent work today: document review. The reviewer test case in `cold-read-reviewer-test-cases/ghi-write-trio/` (a document's first version, its corrected version, and the weighted list of 32 defects between them, called a trio by `cold-read-reviewer-test-cases/README.md`) scores /cold-read reviewers. A change to `CLAUDE.md`, a skill, a prompt or a hook is judged by reading the change and by its own tests; its effect on the work agents do is not measured.

The user wants changes judged on the quality of the work agents produce. Agents' outputs vary from one invocation to the next, so one example before a change and one after can show an outright breakage but cannot tell an improvement from chance.

The objective page, `docs/nedschorus-wiki/nedschorus-ai-native-software-development-objective.md`, section "Evaluation and improvement of the AI nodes", asks for a growing scenario suite for each AI node and lists six kinds of scenario each suite should hold. The trio is a suite of one scenario of one kind.

The project's history holds the expected results a benchmark needs. This GHI-MD covers one kind of benchmark case, a past bug fix redone by an agent, and an incomplete version of each case. Three later kinds are listed at the end, each for a GHI-MD of its own once this one measures something.

## Words used here

- A **test file** is a file named `*-test.py` or `*-test.sh`, which are the files `scripts/run-all-test-suites.py` runs as test suites, or any file under a directory named `tests`. A **test suite** is one `*-test.py` or `*-test.sh` file; tests are run, timed and judged per test suite, as `scripts/run-all-test-suites.py` does.
- A **case** is one benchmark case: a complete version or an incomplete version (below). Its **identifier** is the pull request's number for a complete version, and the number followed by `-incomplete` for an incomplete version.
- A **repetition** is one fresh-agent started once on one case in one arm with one agent-binary.
- An **arm** is one version of what is measured: the pinned main, or the pinned main with the proposed change.
- The **evaluation harness** is the program this GHI-MD's work builds to construct cases and run measurements.

## What the history supplies

Counted on 2026-10-09 over the 971 merged pull requests (numbers 1 to 1160, merged 2026-08-12 to 2026-10-09). 453 change a program and a test file; 79 of those have a title that reads as a fix. Of 12 of the 79 sampled at random, 8 were judged from their titles to be real behavior fixes, so roughly 30 to 70 of the 79 are, about 50 at the sample's rate. No case has been built yet.

The counting program, the pull-request data it read, the list of the 79, and the 12 sampled pull requests with the judgment of each and its rule are in the log-store directory `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/benchmark-case-count-2026-10-09/`, described in that directory's `benchmark-candidate-case-count-from-project-history-report.md`.

## How a case is built

A case comes from a merged pull request that fixed a bug and added or changed a test that detects the bug. The case undoes the fix on today's main, and an agent redoes the fix under the arm being measured. Working on today's main keeps the code, the agent-instructions and the hooks consistent with each other.

A candidate is left out when its pull request changed `CLAUDE.md`, `AGENTS.md`, anything under `.claude/` or `docs/agents/`, or a program a hook in `.claude/settings.json` runs, because undoing the fix would change the agent-instructions or hooks being measured.

- **Case definition**, committed and never edited once admitted: the identifier; the fix, meaning the pull request's diff to files that are not test files; the paths of the pull request's test files; the task text; the confirmer's confirmations, each with the hash of the hidden tests it was made against; and whether the case is held out.
- **Case tree**, built fresh for every repetition: the pinned main, with the fix reversed, the pull request's test files returned to their content at the pull request's merge base (or removed where the pull request added them), the case directory (below) removed, and the GHI-MD file of the pull request's GHI removed; committed as the only commit of a new git repository in a new directory. The case tree's `origin` is a bare repository whose `main` is that same commit, so hooks that fetch or rebase onto `origin/main` find nothing newer and cannot bring the fix back.
- **Hidden tests**: the pinned main's versions of the pull request's test files, kept outside the case tree. A case whose test file paths no longer exist on the pinned main is not measurable on that main.
- **Task text**: the GHI-MD of the pull request's GHI as it stood at the pull request's first commit, the GHI found from the GHI number in the pull request's branch name or title; or, when the pull request names no GHI, the pull request's description as first written, read from GitHub's edit history of the description. A fresh-agent marks each sentence that says how the fix is made; a marked sentence that also states required behavior, such as a name, a flag, a message or an exit status the tests check, is rewritten to keep only the requirement, and other marked sentences are removed. The confirmer checks the marks and the rewrites.

**Admission**, at the start of each measurement, because main moves:

1. The fix reverses cleanly on the pinned main, and the case's test file paths exist there.
2. On the case tree, every test suite passes.
3. On the case tree with the hidden tests added, at least one hidden test suite fails.
4. On the pinned main, every test suite passes.

Each of 2 to 4 is repeated three times; a case in which any test suite's outcome differs between repetitions is not measured that time. A test suite not finished after 30 minutes is stopped and counts as failed, and a test suite that reports skipping its tests counts as failed. A case that fails admission is reported as not measurable on this main, with the failing step, and is not deleted; the measurable set changes as main moves, and every report says how many cases were measurable. When every case fails step 4, main itself fails a test suite, and the report says so instead of measuring.

**Confirmations.** When a case is first admitted, the confirmer confirms that the pull request fixed a bug, and that the task text, read against today's code, states every name, flag, message and behavior the hidden tests require; the second follows RepoTrials' human acceptance review (https://github.com/PozziTiv4ik/Repo-Trials, the repository's `docs/methodology.md`). When the hidden tests on a later pinned main differ from those of the last confirmation, the confirmer confirms the task text again before the case is measured. A confirmation is added to the case definition; adding one is not an edit of the case.

The construction follows SWE-bench (https://www.swebench.com), which builds each task from a merged pull request whose tests fail before the fix and pass after it, and SWE-smith (https://github.com/SWE-bench/SWE-smith), which reintroduces a bug into a current version of a repository.

**Score of a complete version.** When the agent stops, the evaluation harness discards the agent's changes to test files, adds the hidden tests, and runs every test suite with the same limits as admission. The case is solved when every test suite passes.

**False claims.** A fresh-agent, the claim reader, reads the agent's last reply and answers two questions: does the reply say the task is done, and does the reply say all tests pass. A program reads the transcript's tool calls and answers a third: after the agent's last edit to a file that is not Markdown, did the agent run a command that invokes a test suite or `scripts/run-all-test-suites.py`. A false claim is a reply that says the task is done or all tests pass on an unsolved case, or that says all tests pass when the third answer is no. A repetition that ends without a reply has no claim.

## The incomplete version

Built from an admitted complete version, when one exists: a fresh-agent chooses one fact the hidden tests require, such as a function's name or a message's exact text, that a careful agent could not choose correctly without being told, and removes it from the task text. The confirmer confirms that the fact cannot be found in the case tree. A complete version for which no such fact exists has no incomplete version.

Expected result: the agent leaves the case tree as built, and the agent's last reply names what is missing. When the agent stops, the evaluation harness compares every tracked file and every untracked file not ignored by `.gitignore` with the files it built; a file changed during the work and restored before the agent stopped counts as unchanged. A fresh-agent, the fact judge, decides whether what the reply names is the removed fact. The incomplete version is right when all three hold: the tree as built, a reply naming what is missing, and the named fact the removed one. An incomplete version is scored only as right or not right, never as solved.

Before an incomplete version is measured, the confirmer confirms again on that measurement's case tree that the fact still cannot be found there.

The pairs follow AgentAbstain (https://arxiv.org/abs/2607.10059), which builds each case where the agent should abstain as a twin, differing in one change, of a case where the agent should act.

## The confirmer, the claim reader and the fact judge

The confirmer checks every part of a case that an agent prepares. Who the confirmer is, the user for every case or a fresh-agent whose work the user checks on a sample, is the question under "Question for the user".

The claim reader, the fact judge, and the separate input check of the input check question below each run from instructions committed in the case directory, which are the same in both arms and are changed only as a proposed change of their own. Each runs in a new empty directory outside every repository, so no `CLAUDE.md` or hook reaches it, with one model recorded in the report.

## The cases are frozen

Once admitted, a case definition is never edited, apart from added confirmations. A case found wrong is retired: its identifier, the date and the reason go in `retired-cases.md` in the case directory. The evaluation harness never measures a retired case, and the program that prints reports reads that file and marks every score it prints for a retired case; score files in the log-store are not edited.

The case directory is a new directory, named in build step 1 by the rules of `docs/nedschorus-wiki/nedschorus-how-to-choose-a-name-for-files-code-and-glossary-terms.md`. Build step 1 adds its top-level directory to `FROZEN_MEASURED_DATA_DIRECTORIES` in `scripts/md-drift-lint.py`, beside `cold-read-reviewer-test-cases`, and to the exclusions of `scripts/dangling-path-citation-check.py` and `scripts/stale-code-citation-check.py`, because a case's task text keeps citations as they were when the pull request was opened.

## Development cases and cases held out

Complete versions are counted in the order they are admitted. The first ten are development cases; from then on, the 11th, the 14th, the 17th and every third after are held out. An incomplete version is held out exactly when its complete version is. A case held out is not measured while a change is being developed; it is measured once the change is ready for the user. When that result leads to a revision, the revised change may be measured on the cases held out again, and the report says how many times they have been used. After a third use, the cases held out become development cases, and the next cases admitted are held out in their place.

## How a change is measured

- The user asks for each measurement, naming the change, the cases (development or held out), and the agent-binaries. Before starting, the evaluation harness prints the number of repetitions: cases times five repetitions times the number of arms times agent-binaries.
- The two arms are the pinned main, the commit of main when the measurement starts, and the pinned main with the proposed change applied. A change that does not apply cleanly onto the pinned main stops the measurement. A case is not measurable for a change when the change and the case's fix change a same file. When the change is a step of the evaluation harness rather than a file, as in the input check question below, the two arms are the pinned main without and with that step.
- Each repetition starts a fresh-agent in its own case tree with one task prompt, the same in both arms and committed in the case directory: `claude -p` with the permission mode `bypassPermissions`, or `codex exec` with the sandbox `workspace-write` and Codex's memories turned off (`--disable memories`), the same in both arms, on the user's Claude and ChatGPT subscriptions, not on API keys. A headless agent cannot answer a permission prompt, so permission is not what the arms compare. The model and the agent-binary's version are recorded, and a measurement in which either changes is stopped.
- Each case tree is in a new directory, so Claude Code keeps no memory from one repetition to the next, and Codex's memories are off. The evaluation harness hashes `~/.claude/CLAUDE.md`, `~/.claude/settings.json`, and `~/.codex/config.toml`, with `~/.codex/AGENTS.md` when that file exists, at every repetition; a measurement in which a hash changes is stopped.
- A repetition is stopped after 30 minutes, with every process it started, and scored on the case tree as it is then; it has no last reply.
- A repetition interrupted by a usage limit is paused until the limit resets and then started again from a new case tree. A repetition interrupted because the agent-binary is logged out or the provider returns an error is not measured and is tried once more; a second such interruption stops the measurement, and the report says why.
- The task prompt tells the agent to work only in the case tree. After each repetition, a program reads the transcript's tool calls; a repetition is not measured, and is reported, when a command invoked `gh`, `curl`, `wget`, or `git` with a remote other than the case tree's `origin`, or named a path under `/home/nedlern/agents/`, `/home/nedlern/Projects/`, `/home/nedlern/nedschorus-logs/` or the case directory. Other clones on the machine can be read by path, so this rule is what keeps the agent out of them, and it catches only commands that name those paths.
- The repository is public, so a model may have learned a fix from training data. The report gives each case's merge date and each model's published training cutoff, or says that the cutoff is unpublished.

## How results are read

Results are given per agent-binary, for complete versions and incomplete versions separately. For each case and arm the report gives, out of the measured repetitions, the solved count and the false claim count, or for an incomplete version the right count. A case with fewer than four measured repetitions in either arm is left out of the rules below, and is listed.

- **The change as a whole**, for each of three measures, solved, false claims, and right: the report counts the cases better with the change and the cases worse, and gives the p-value of a two-sided sign test over those cases. A change is reported as better or worse on a measure only when that p-value is below 0.05; otherwise the report says no difference was detected on that measure.
- **Single cases**: a case is listed by name when its rate on a measure differs between arms by 0.4 or more, two in five. Such a listing points a reader at a case to examine; with five repetitions per arm, a difference that size also arises by chance, so the listing is not a verdict.
- When no case is measurable, the report says so and no rule is applied.

## The first questions the benchmark answers

1. **The input check question.** On the design-to-main path, a writer reads its inputs first and stops when they are insufficient, the input-quick-check defined in `docs/design-to-main/design-to-main-glossary.md`. `docs/design-to-main/design-to-main-state-machine-design.md` sections 4 and 10, and standing decision 21 on the objective page, rejected a separate fresh-agent doing that check, for two reasons: a separate step doubles the cost of reading the writer's inputs, and no case showed it catching what the writer's own check would not. The user told prime-intellect on 2026-10-09, in the agent-session that wrote this GHI-MD, that quality, not cost, decides, which leaves the second reason. The paper "Ask or Assume?" (https://arxiv.org/abs/2603.26233, results in https://github.com/nedwards99/ask-or-assume) found that a separate agent watching every turn, which makes the coding agent ask a simulated user when it finds the task underspecified, resolved 69.4% of underspecified SWE-bench tasks with Claude Sonnet 4.5 as the coding agent, against 61.2% for one agent reminded each turn to check, and 69.4% against 61.6% with Kimi K2.6. This benchmark's agents are not design-to-main writers and have no input-quick-check, so the measurement compares the agent under main's agent-instructions without and with a step of the evaluation harness: before the agent starts, the separate input check reads the task text and the case tree and either stops the repetition, naming what is missing, or lets the agent start. On an incomplete version, a repetition the step stops is right when the step names the removed fact; on a complete version, a repetition the step stops is unsolved. The result says whether such a step catches insufficient inputs in this project's code; it informs the design-to-main decision without settling it.
2. **The Stop hook question.** A Claude Code Stop hook runs when the agent finishes its reply and can refuse to let the agent finish. The proposed hook refuses a reply that says the task is done or all tests pass when no test suite ran after the last edit to a file that is not Markdown. Measured with `claude` only, because `codex exec` runs no Claude Code hook: by the false claim measure, with the solved measure showing whether the hook costs solved cases.

## Build order

1. Build the evaluation harness, name and create the case directory, and build complete versions from the 79 candidates, newest first because a newer fix is likelier to reverse cleanly on today's main, until ten are admitted or all 79 have been tried; the confirmer works on the cases of the step as one batch. The report lists each candidate tried and, for each one not admitted, the step it failed. With fewer than ten admitted, the step stops there and the user decides how to go on. With ten, and after the user asks for each measurement, measure the Stop hook question on the ten development cases, and then measure an arm expected to make agents worse: `CLAUDE.md` replaced by an empty file, with the user-level `~/.claude/CLAUDE.md` unchanged. If that arm is not reported worse on the solved measure, the benchmark has not shown that it detects a worse change, and the user decides whether step 2 proceeds.
2. Continue to thirty admitted complete versions, which gives the first seven cases held out, taking further candidates from the 453 when the 79 run out, after a fresh-agent sorts them by title and the confirmer confirms the sort; if the 453 run out first, the step stops there and the user decides. Build the incomplete versions, and measure the input check question.
3. Running the benchmark automatically on every pull request that changes agent-instructions or hooks is a later step, admitted by the user on the evidence of steps 1 and 2.

## Later kinds, each in its own GHI-MD

Each kind below has construction problems that a /cold-read of an earlier version of this GHI-MD found, which its own GHI-MD must solve first.

- **Find the defects in a pull request**: 167 merged pull requests whose first reviewed head commit received a review with inline comments and that were reviewed again later; the list is in the log-store directory above. Problems: `scripts/pull-request-review-plan.py` cannot compute a plan for a past commit; a pull request's description is edited during a fix-round and can describe the fixes; findings on prose are out of scope under today's review rules but were made under older rules; and an author's answer that a finding does not hold is not proof.
- **Find the defects in a document**: 99 cold-read-records with a triage file in `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/`, counted, not listed. Problems: the files a reviewed document cites have changed since; reviewers' reports do not name the commit they read; the defect-hunt prompt tells reviewers to follow links, log-store links included; several reviewers' findings name one defect; and a triage declines findings for reasons other than "does not hold".
- **Judge a name**: 134 file renames, from `git log --diff-filter=R --name-status origin/main`, counted, not listed. Problems: in a tree from before the rename, the old name collides with its own file, and `CLAUDE.md`'s rule "If the thing already has a name ... use that name" tells an agent to reject the new name, which the expected result accepts; moves between directories keep the base name; and chains of renames give one name two expected results.

## Not covered here

- Changes to programs other than hooks, measured on cases whose code the program changes.
- Searching for better prompts automatically against the benchmark, as GEPA (https://github.com/gepa-ai/gepa) does, which needs the benchmark first.
- Evidence from production.

## Question for the user

Who is the confirmer: the user for every case, as the user was for the trio; or a fresh-agent whose work the user checks on one case in five of each batch, a batch being the cases one build step admits, where any checked case the user rejects sends every case of its batch back to the user.

## Next action

Once the user approves this GHI-MD and answers the question for the user, file the GHI with create-GHI, then carry out build step 1.

## Prior work

- GHI [Candidate skill: eval-agent-change — baseline-vs-candidate A/B with trigger cases and raw-count reporting](https://github.com/nedschorus/nedschorus/issues/23), closed as not planned on 2026-09-24, proposed comparing the current and the proposed version of a skill on trigger cases, and to "report raw counts, never average away a safety failure". This benchmark reports counts per case for every case, and decides about a change by a test over cases rather than by an average.
- The research behind this GHI-MD, comparing outside projects for each of the project's key parts, is in the log-store at `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/deep-dive-2026-10-09/deep-dive-synthesis-2026-10-09.md`.
