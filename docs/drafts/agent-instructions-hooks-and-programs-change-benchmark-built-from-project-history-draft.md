# A benchmark built from the project's own history, to measure whether a change to agent-instructions, hooks or programs makes agents' work better

## Why

A change to `CLAUDE.md`, a skill, a prompt, a hook or a program that directs agents is judged today by reading the change. Nobody measures whether agents do better work after the change merges. The user wants changes judged on the quality of the work agents produce, and agents' outputs vary from one invocation to the next, so one example before and one after tells nothing.

The project has one measured instrument: the reviewer test case in `cold-read-reviewer-test-cases/ghi-write-trio/`, which scores document reviewers against 32 weighted defects in one first version of one document. The objective page, `docs/nedschorus-wiki/nedschorus-ai-native-software-development-objective.md`, section "Evaluation and improvement of the AI nodes", asks for a scenario suite for every node, a node being one agent step of the work, and lists six kinds of scenario each suite should hold. No such suite exists for any node.

The project's history already holds the right answers a benchmark needs: bugs that were fixed with a regression test, reviews whose findings were fixed, cold-read findings that were triaged, and names that were replaced. The work this GHI-MD proposes builds a benchmark from that history, and uses the benchmark to compare the project as it is on main with main plus a proposed change.

## What the history supplies

Counted on 2026-10-09 over the 971 merged pull requests (numbers 1 to 1160, merged 2026-08-12 to 2026-10-09) and over git history on main. The counts are upper bounds on candidates; no benchmark case has been built.

| Kind of benchmark case | Candidates | How counted |
|---|---|---|
| Redo a fix | about 55 strong, up to 453 | merged pull requests that change a program and a test file: 453; of those, 79 have a title that reads as a fix, and 9 of 12 sampled were real behavior fixes |
| Find the defects in a pull request | 153 | merged pull requests reviewed with inline comments at two or more head commits |
| Find the defects in a document | 99 | cold-read records in the log-store with a triage file |
| Judge a name | 134 | file renames in git history |

The counting program, its data and the sample are in the log-store directory `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/benchmark-case-count-2026-10-09/`. The candidate pull requests for each kind are listed in that directory's `benchmark-candidate-case-pull-request-numbers-by-kind.json`.

## The benchmark cases

Each benchmark case gives an agent the inputs a real agent had, hides the answer, and scores the agent's output against the answer. A program does the scoring. Where an output is English and must be matched against an answer, a fresh-agent first places each item of the output on one answer row, or on none, and the program counts the placements; the trio is scored the same way today.

Each kind of case has one prompt that starts the agent. The prompt says what the agent receives and what it must produce, gives no part of the answer, and is committed with the cases. The prompt is part of the measured system: a change to a prompt is a proposed change, and is measured like any other.

1. **Redo a fix.** Source: a merged pull request that changed a program and its test. Input: the repository at the pull request's merge base, with git history after that commit removed so the fix cannot be read, and the GHI-MD or pull-request description with each sentence that states the fix removed. A fresh-agent marks the sentences that state the fix, and the person who confirms answers (see "Questions for the user") confirms the marks. Hidden: the test files the pull request changed. A benchmark case is admitted only after four admission tests pass when the case is built: the test suites the pull request did not change pass at the merge base; the hidden tests fail at the merge base; the hidden tests pass at the merge commit; and an empty change scores as unsolved. Each of the four is run three times, and a case whose result differs between repetitions is dropped as flaky. A test invocation that has not finished after 30 minutes is stopped, and the case is dropped with that reason. Score: solved when the hidden tests pass and every suite that passed at the merge base still passes. The construction is SWE-bench's, with the four admission tests taken from RepoTrials (https://github.com/PozziTiv4ik/Repo-Trials, `docs/methodology.md`).
2. **Find the defects in a pull request.** Source: a pull request reviewed, then changed in a fix-round. Input: the first reviewed head commit and the review plan that `scripts/pull-request-review-plan.py` computes for that commit. Answer: the findings that a later commit fixed, one answer row each. Findings that the pull request's author answered as not holding become traps: a finding placed on a trap is counted as a false finding. Score: three counts, reported separately and never combined into one number: answer rows found, false findings, and minutes taken.
3. **Find the defects in a document.** Source: a cold-read record whose triage marks which findings held. Input: the document as reviewed. Answer: a defect list in the trio's format, one row for each finding the triage marks as held, each row weighted 1 until the user decides how rows are weighted (see "Questions for the user"). Score: `nc-systems/cold-read/cold-read-reviewer-score.py`, unchanged, which reads the weights from the defect list.
4. **Judge a name.** Source: a rename whose commit message says why the old name was wrong. Each rename gives two cases, run separately so that neither reveals the other: the old name, and the new name, each with one sentence saying what the name names. The agent answers accept or reject. Answer: the old name is rejected and the new name is accepted. Score: the program compares the two answers; the agent's stated reason is kept for a person to read and is not scored.
5. **Stop on an insufficient input.** Not from history alone. Built from a case of kind 1 by removing one fact the fix needs from the input, so the case has two versions: one complete, which the agent should complete, and one missing a fact, from which the agent should stop without changing any file and name what is missing. Score: the complete version scores as kind 1 does; for the incomplete version, a program confirms that no file changed, and a fresh-agent decides whether what the agent named is the removed fact; both versions must be right. The pairs follow AgentAbstain (arXiv 2607.10059).

## The answers are frozen

A benchmark case is measured data. Once admitted, a case is never edited to improve it; a case found wrong is retired with the reason and replaced, and every score taken against the retired case says so. The rule is the one `cold-read-reviewer-test-cases/README.md` states for the trio. Case definitions are committed to the repository, in a directory beside `cold-read-reviewer-test-cases/`, because they are the instrument. Agent outputs and scores are byproducts and go to the log-store.

Once a kind has at least six admitted cases, a third of them, rounded down, is held out: never used while a change is being developed, and run only to confirm a result before the change goes to the user. A change tuned against the held-out cases would be measured against its own training data. Which cases are held out is chosen at random once and recorded with the cases.

## How a change is measured

- Two arms: main, and main with the proposed change. Everything else is the same in both arms: the cases, the model, the agent-binary and its version.
- Each benchmark case runs three times in each arm, for each agent-binary the change affects, `claude` and `codex`.
- Each repetition runs headless, through `claude -p` or `codex exec`, on the subscription, in its own throwaway worktree, from a fresh-agent.
- A measurement starts only when the user asks for one, until build step 3 says otherwise, so a measurement never consumes usage limits the user did not choose to spend.
- The report lists raw counts per benchmark case, not only totals. Every case that passed on main and failed with the proposed change is listed by name, because an average can hide a regression.
- The first evaluation harness is a Python script in this repository. promptfoo (https://github.com/promptfoo/promptfoo) and Inspect AI (https://github.com/UKGovernmentBEIS/inspect_ai) are considered only when the script shows a need either one meets.

## The first questions the benchmark answers

1. Whether a separate fresh-agent that checks a writer's inputs catches more insufficient inputs than the writer's own check. `docs/design-to-main/design-to-main-state-machine-design.md` section 10 rejected a separate checker because no case showed a gain. The paper "Ask or Assume?" (arXiv 2603.26233) measured a gain in a different setting: a separate checker resolved 69.4% of underspecified SWE-bench tasks against 61.2% for one agent reminded to check. In the paper the single agent checks while it codes, with its context filling with its own work; a design-to-main writer checks first, from an empty context. Cases of kind 5 measure the difference in this project's setting.
2. Whether a Claude Code Stop hook, a hook that runs when the agent finishes its reply and can refuse to let it finish, reduces false claims of "done" or "tests pass" by refusing such a claim when no test ran after the last edit. Measured on cases of kind 1.
3. Whether a change to the cold-read reviewers' instructions finds more of the defects in documents, on cases of kind 3.

## Build order

1. Build ten cases of kind 1 by hand with a script's help, choosing further candidates until ten are admitted or the candidates run out, and measure one real proposed change in both arms. The step shows whether the cases tell a better change from a worse one before more cases are built. Ten cases are too few to hold any out.
2. Extend the script to build cases of all five kinds, and choose the held-out cases.
3. Running the benchmark automatically on every pull request that changes agent-instructions is a later step, admitted by the user on evidence from steps 1 and 2.

## Not covered here

- Searching for better prompts automatically against the benchmark, as GEPA (https://github.com/gepa-ai/gepa) does. That search needs the benchmark first, and goes in its own GHI.
- Evidence from production.

## Questions for the user

1. Who confirms the answers and the removed sentences for each case: a fresh-agent proposes them and the user confirms a sample, or the user confirms every case, as the user did for the trio.
2. How the rows of a defect list built from a triage are weighted: 1 each, or by consequence on the trio's scale of 1 to 10, set by an agent and confirmed by the user.

## Next action

Build step 1: from the candidates for kind 1 in `benchmark-candidate-case-pull-request-numbers-by-kind.json`, build cases and run the four admission tests three times each until ten cases are admitted, and report each case admitted and the reason each other candidate was dropped.

## Prior work

- GHI [Candidate skill: eval-agent-change — baseline-vs-candidate A/B with trigger cases and raw-count reporting](https://github.com/nedschorus/nedschorus/issues/23), closed as not planned on 2026-09-24, proposed comparing the current and the proposed version of a skill on trigger cases. The work proposed here keeps that GHI's rules of raw counts per case and no regression hidden in an average, and adds cases taken from history.
- The research behind this GHI-MD, comparing outside projects for each of the project's key parts, is in the log-store at `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/deep-dive-2026-10-09/deep-dive-synthesis-2026-10-09.md`.
