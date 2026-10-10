# A benchmark built from the project's own history, to measure whether a change to the agents' instructions, hooks or programs makes their work better

## Why

A change to `CLAUDE.md`, a skill, a prompt, a hook or a program that directs agents is judged today by reading the change. Nobody measures whether agents do better work after the change merges. The user wants changes judged on the quality of the work agents produce, and agents' outputs vary from one invocation to the next, so one example before and one after tells nothing.

The project has one measured instrument: the reviewer test case in `cold-read-reviewer-test-cases/ghi-write-trio/`, which scores document reviewers against 32 weighted defects in one first draft. The objective page, `docs/nedschorus-wiki/nedschorus-ai-native-software-development-objective.md`, section "Evaluation and improvement of the AI nodes", asks for a scenario suite for every node and lists six kinds of scenario each suite should hold. No such suite exists for any node.

The project's history already holds the right answers a benchmark needs: bugs that were fixed with a regression test, reviews whose findings were fixed, cold-read findings that were triaged, and names that were replaced. This GHI builds a benchmark from that history and uses the benchmark to compare the current system with a proposed change.

## What the history supplies

Counted on 2026-10-09 over the 971 merged pull requests (numbers 1 to 1160, merged 2026-08-12 to 2026-10-09) and over git history on main. The counts are upper bounds on candidates; no benchmark case has been built.

| Kind of benchmark case | Candidates | How counted |
|---|---|---|
| Redo a fix | about 55 strong, up to 453 | merged pull requests that change a program and a test file: 453; of those, 79 have a title that reads as a fix, and 9 of 12 sampled were real behavior fixes |
| Find the defects in a pull request | 153 | merged pull requests reviewed with inline comments at two or more head commits |
| Find the defects in a document | 99 | cold-read records in the log-store with a triage file |
| Judge a name | 134 | file renames in git history |

The counting program, its data and the sample are in the log-store at `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/benchmark-case-count-2026-10-09/`.

## The benchmark cases

Each benchmark case gives an agent the inputs a real agent had, hides the answer, and scores the agent's output against the answer with a program.

1. **Redo a fix.** Source: a merged pull request that changed a program and its test. Input: the repository at the pull request's merge base, with git history after that commit removed so the fix cannot be read, and the GHI-MD or pull-request description with any sentence that states the fix removed. Hidden: the test files the pull request changed. A benchmark case is admitted only after four tests pass when the case is built: the test suites the pull request did not change pass at the merge base; the hidden tests fail at the merge base; the hidden tests pass at the merge commit; and an empty change scores as unsolved. Each of the four is run three times, and a case whose result differs between repetitions is dropped as flaky. Score: the hidden tests pass and every suite that passed at the merge base still passes. This construction is SWE-bench's, with the four admission tests taken from RepoTrials (https://github.com/RepoTrials/Repo-Trials, `docs/methodology.md`).
2. **Find the defects in a pull request.** Source: a pull request reviewed, then changed in a fix-round. Input: the first reviewed head commit and the review plan that `scripts/pull-request-review-plan.py` computes for that commit. Answer: the findings that a later commit fixed. Findings that the author answered as not holding become traps, which a reviewer scores against by reporting them. Score: findings found, traps reported, and the time taken.
3. **Find the defects in a document.** Source: a cold-read record whose triage marks which findings held. Input: the document as reviewed. Answer: the findings that held, as a defect list in the format of the existing trio. Score: `nc-systems/cold-read/cold-read-reviewer-score.py`, unchanged.
4. **Judge a name.** Source: a rename whose commit message says why the old name was wrong. Input: the old name and one sentence saying what the name names. Answer: the old name is rejected for the reason the commit gives, and the new name is accepted. Score: both judgments correct.
5. **Stop on an insufficient input.** Not from history alone. Built from a case of kind 1 by removing one fact the fix needs from the input, so the case has two versions: one complete, which the agent should complete, and one missing a fact, from which the agent should stop and name the missing fact. Score: both versions handled correctly. The pairs follow AgentAbstain (arXiv 2607.10059).

## The answers are frozen

A benchmark case is measured data. Once admitted, a case is never edited to improve it; a case found wrong is retired with the reason and replaced, and every score taken against the retired case says so. The rule is the one `cold-read-reviewer-test-cases/README.md` states for the trio. Case definitions are committed to the repository, in a directory beside `cold-read-reviewer-test-cases/`, because they are the instrument. Agent outputs and scores are byproducts and go to the log-store.

A fixed third of the cases of each kind is held out: never used while a change is being developed, and run only to confirm a result before the change goes to the user. A change tuned against the held-out cases would be measured against its own training data.

## How a change is measured

- Two arms: the current main, and main with the proposed change. Everything else is the same in both arms: the cases, the model, the agent-binary and its version.
- Each benchmark case runs three times in each arm, for each agent-binary the change affects, `claude` and `codex`.
- Each repetition runs headless, through `claude -p` or `codex exec`, on the subscription, in its own throwaway worktree, from a fresh-agent.
- The report lists raw counts per benchmark case, not only totals. Every case that passed in the current arm and failed in the proposed arm is listed by name, because an average can hide a regression.
- The first evaluation harness is a Python script in this repository. promptfoo (https://github.com/promptfoo/promptfoo) and Inspect AI (https://github.com/UKGovernmentBEIS/inspect_ai) are considered only when the script shows a need either one meets.

## The first questions the benchmark answers

1. Whether a separate fresh-agent that checks a writer's inputs catches more insufficient inputs than the writer's own check. `docs/design-to-main/design-to-main-state-machine-design.md` section 10 rejected a separate checker because no case showed a gain. The paper "Ask or Assume?" (arXiv 2603.26233) measured a gain in a different setting: a separate checker resolved 69.4% of underspecified SWE-bench tasks against 61.2% for one agent reminded to check. In the paper the single agent checks while it codes, with its context filling with its own work; a design-to-main writer checks first, from an empty context. Cases of kind 5 measure the difference in this project's setting.
2. Whether a Stop hook that refuses a claim of "done" or "tests pass" with no test run after the last edit reduces false claims, on cases of kind 1.
3. Whether a change to the cold-read reviewers' instructions finds more of the defects in documents, on cases of kind 3.

## Build order

1. Build ten cases of kind 1, redo a fix, by hand with a script's help, run the four admission tests, and measure one real proposed change in both arms. The step shows whether the cases discriminate between a better and a worse change before more are built.
2. Extend the script to build cases of all five kinds, and build the held-out set.
3. Running the benchmark automatically on every pull request that changes agent-instructions is a later step, admitted by the user on evidence from steps 1 and 2.

## Not covered here

- Searching for better prompts automatically against the benchmark, as GEPA (https://github.com/gepa-ai/gepa) does. That search needs the benchmark first, and goes in its own GHI.
- Evidence from production.

## Questions for the user

1. Who confirms the answers for cases of kinds 2 and 4: a fresh-agent labels them and the user confirms a sample, or the user confirms every case, as the user did for the trio.
2. How much of the subscriptions' usage limits one measurement of a change may consume, since a measurement consumes the limits the agent-seats work from.

## Next action

Build step 1: choose ten merged pull requests from the candidates for kind 1 listed in the log-store's `benchmark-candidate-case-pull-request-numbers-by-kind.json`, build each case, run the four admission tests three times, and report which cases were admitted and why each other case was dropped.

## Prior work

- GHI [Candidate skill: eval-agent-change — baseline-vs-candidate A/B with trigger cases and raw-count reporting](https://github.com/nedschorus/nedschorus/issues/23), closed as not planned on 2026-09-24, proposed comparing the current and the proposed version of a skill on trigger cases. This GHI keeps that GHI's rules of raw counts per case and no averaged away regression, and adds cases taken from history.
- The research behind this GHI, comparing outside projects for each of the project's key parts, is in the log-store at `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/deep-dive-2026-10-09/deep-dive-synthesis-2026-10-09.md`.
