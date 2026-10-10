# A benchmark built from the project's own history, to measure whether a change to agent-instructions or hooks makes agents' work better

This GHI-MD is pending approval and has not been filed as a GHI yet; create-GHI files it once the user approves it.

## Why

The project measures one kind of agent work today: document review. The reviewer test case in `cold-read-reviewer-test-cases/ghi-write-trio/` (the "trio": a document's first version, its corrected version, and the weighted list of 32 defects between them) scores /cold-read reviewers, and `cold-read-reviewer-test-cases/README.md` explains the scoring. No other agent work is measured, and a change to `CLAUDE.md`, a skill, a prompt or a hook is judged by reading the change, not by measuring the work agents do after the change merges.

The user wants changes judged on the quality of the work agents produce. Agents' outputs vary from one invocation to the next, so one example before a change and one after can show an outright breakage but cannot tell an improvement from chance.

The objective page, `docs/nedschorus-wiki/nedschorus-ai-native-software-development-objective.md`, section "Evaluation and improvement of the AI nodes", asks for a growing scenario suite for each AI node, the AI nodes being the agents and the combinations of code and prompts in the project's graph of work, and lists six kinds of scenario each suite should hold. The trio is a suite of one scenario of one kind; no node has the suite the objective asks for.

The project's history holds expected results for four of the five kinds of benchmark case below: bugs fixed with a regression test, reviews whose findings were fixed, /cold-read findings that were triaged, and names that were replaced. The fifth kind is built from the first. The work this GHI-MD proposes builds a benchmark from that history and uses the benchmark to compare main with main plus a proposed change.

## What the history supplies

Counted on 2026-10-09 over the 971 merged pull requests (numbers 1 to 1160, merged 2026-08-12 to 2026-10-09) and over git history on main. No benchmark case has been built yet.

| Kind of benchmark case | Candidates | How counted |
|---|---|---|
| 1. Redo a fix | about 60; 453 to sort | 453 merged pull requests change a program and a test file; 79 of them have a title that reads as a fix; of 12 of the 79 sampled, 9 were judged from their titles to be real behavior fixes, and 75% of 79 is about 60 |
| 2. Find the defects in a pull request | 167 | merged pull requests whose first reviewed head commit received a review with inline comments and that were reviewed again at a later commit |
| 3. Find the defects in a document | 99 | cold-read-records in the log-store with a triage file, out of 594 |
| 4. Judge a name | 134 | file renames in git history on main |

Everything behind the table is in the log-store directory `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/benchmark-case-count-2026-10-09/`: the programs that counted (`count-cases.py` and `count-review-cases-first-reviewed-commit-with-inline-comments.py`), the pull-request data they read, the twelve sampled pull requests with their titles (`redo-a-fix-title-sample-of-12-2026-10-09.txt`), the 79 kind 1 candidates (key `bug_fix_candidates` in `benchmark-candidate-case-pull-request-numbers-by-kind.json`) and the 167 kind 2 candidates (`review-case-candidate-pull-request-numbers.json`). Kind 3 candidates are the cold-read-record directories under `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/` that hold a `triage.md`; kind 4 candidates are the output of `git log --diff-filter=R --name-status origin/main`.

## What the benchmark measures

The **measured files** are the files a proposed change alters and an agent reads or runs while it works: `CLAUDE.md`, `AGENTS.md`, everything under `.claude/` (settings, hooks, skills and the subagent definitions), `docs/agents/`, and the programs the hooks in `.claude/settings.json` call. A change to any other program is not measured by this benchmark (see "Not covered here").

An **arm** is one version of the measured files. A measurement compares two arms: main, pinned to one commit when the measurement starts, and that commit plus the proposed change.

A **case tree** is the repository state an agent works in for one repetition of one benchmark case. The evaluation harness builds the case tree in a new directory outside every clone of the repository: the files of the case's historical commit, committed as the only commit of a new git repository with no remote, so no later commit can be read from the case tree. The evaluation harness then copies the arm's measured files over the case tree, so the agent works on the historical code under the arm's agent-instructions and hooks. A candidate whose pull request changed a measured file is not admitted, because the copy would overwrite the files the case is about.

## The benchmark cases

Each benchmark case hides an expected result from the agent under test, and the agent's output is scored against the expected result. Programs do the scoring. Where the output is English and must be matched against expected results, a fresh-agent, the placer, first places each item of the output, and a program counts the placements. The placer's instructions are committed with the cases and are the same in both arms, so a change to the measured files cannot change how outputs are placed.

Each kind of case has one task prompt, committed with the cases and the same in both arms, that says what the agent receives and what it must produce and gives no part of the expected result. The agent reads the arm's measured files as well, and those are what differ between arms.

A **confirmer** checks by hand every part of a case that an agent prepares; who the confirmer is, the user for every case or the user for a sample, is question 1 under "Questions for the user". No case is admitted before its confirmation.

1. **Redo a fix.**
   - Source: a merged pull request that changed a program and a test file and changed no measured file.
   - Case tree: the pull request's merge base, with the pull request's changes to test files withheld; test files that existed at the merge base stay as they were.
   - Task text: the GHI-MD as it stood at the merge base, or the pull request's description when no GHI-MD existed then. A fresh-agent marks each sentence that says how the fix is made, and those sentences are removed; sentences that state required behavior, such as a name, a flag, a message or an exit status the tests check, stay.
   - Admission, run three times each: (a) every test suite the pull request did not change passes at the merge base; (b) with the pull request's test files applied, at least one of its tests fails at the merge base; (c) with the pull request's whole diff applied to the merge base, every test in (a) and (b) passes; (d) with no change, the case scores unsolved. A case in which any single test's outcome differs between the three repetitions is dropped as flaky. A test invocation not finished after 30 minutes is stopped and the case is dropped. Finally, the confirmer confirms the task text: every name, flag, message and behavior the withheld tests require is still stated, and no removed sentence is needed to know what to build.
   - Score: when the agent stops, the evaluation harness discards the agent's changes to test files, applies the pull request's test files, and runs the tests of (a) and (b). The case is solved when all of them pass.
   - Also recorded, from the agent's transcript: whether the agent's last reply claims the work is done or the tests pass, and whether the agent ran a test after its last edit. A **false claim** is a claim of done or passing on an unsolved case, or a claim that tests pass with no test invocation after the last edit.
   - The construction is SWE-bench's; admission tests (a) to (d) follow RepoTrials (https://github.com/PozziTiv4ik/Repo-Trials, `docs/methodology.md`), which also has a person confirm that the task text is fair to the hidden tests.
2. **Find the defects in a pull request.**
   - Source: a merged pull request among the 167 whose first reviewed head commit still exists in the repository.
   - Case tree: the first reviewed head commit. Task text: the pull request's description, and the diff from the merge base to that commit. The agent reviews under the arm's `docs/agents/pr-reviewer-instructions.md`.
   - Expected results: the defects found by the first review that a later commit of the same pull request fixed, one row per defect even when several findings name the same defect, prepared by a fresh-agent from the review and the later commits. A finding about a Markdown file is left out, because the review scope in `CLAUDE.md` gives prose no findings.
   - Negative examples: findings of the first review that the pull request's author answered as not holding, kept only where the confirmer agrees that the finding does not hold.
   - Placement: each finding of the agent goes on one expected row, on one negative example, or is left unmatched. A finding that names two expected defects goes on both rows.
   - Score, reported separately and never combined: expected rows found; false positives, which are findings placed on a negative example; unmatched findings, which are listed for a person to read and counted neither for nor against; and minutes from the agent's start to its exit.
3. **Find the defects in a document.**
   - Source: a cold-read-record whose triage marks which findings held, and whose reviewers' reports name the commit the reviewers read.
   - Case tree: that commit, so every file the document refers to is as the reviewers saw it. Task text: the document as reviewed, from the frozen copy kept in the cold-read-record. The agent reviews under the arm's `.claude/skills/cold-read/prompts/defect-hunt.md`.
   - Expected results: one row per distinct defect the triage marks as held, merged across the record's reviewers by a fresh-agent, each row weighted as question 2 under "Questions for the user" decides. No kind 3 case is admitted before question 2 is answered.
   - Placement and score as in kind 2: rows found, by weight and by count; false positives, which are findings placed on a finding the triage declined; unmatched findings listed. A reviewer output with no findings scores zero rows found. The counting follows `nc-systems/cold-read/cold-read-reviewer-score.py`, extended to accept the placements on a negative example and unmatched findings and an empty output; the trio's own scoring is not changed.
4. **Judge a name.**
   - Source: a file rename on main whose commit message says why the old name was wrong. A rename in a chain is left out: a file renamed again later, or renamed from a name that was itself a replacement.
   - Each rename gives two cases, run in separate repetitions: the old name, and the new name. Case tree: the commit before the rename, so a search for collisions sees the repository as it was that day.
   - Task text: the name and one sentence saying what the named file does, written by a fresh-agent from the file's content in the case tree and never from the rename's commit message, and confirmed by the confirmer not to contain either name.
   - The agent answers accept or reject, with its reason. Expected result: reject for the old name, accept for the new name, the project's own choice on the day of the rename. Score: the program compares each case's answer with its expected result; the reason is kept for a person to read.
5. **Stop on an insufficient input.**
   - Built from an admitted kind 1 case: a fresh-agent chooses one fact the withheld tests require, such as a function's name or a message's text, and removes it from the task text. The confirmer confirms that the fact cannot be recovered from the case tree.
   - The complete version is the kind 1 case itself; the incomplete version is a new case. The two are never given to the agent in the same repetition.
   - Expected result for the incomplete version: the agent stops, `git status` in the case tree shows no change and no new file when the agent exits, and the agent's last reply names what is missing. A fresh-agent with fixed instructions decides whether what the agent named is the removed fact. Score: the incomplete version is right when both hold; the complete version scores as kind 1.
   - The pairs follow AgentAbstain (arXiv 2607.10059).

## The cases are frozen

A benchmark case is measured data. A case definition holds the commit hashes the case tree is built from, the task text, the expected results and negative examples, the confirmer's confirmation, and whether the case is held out; case trees are rebuilt from the hashes and not committed. Case definitions are committed to the repository in a new directory beside `cold-read-reviewer-test-cases/`, named in build step 1 under the naming page, and every reference or drift check, `scripts/md-drift-lint.py` included, skips the new directory as the README requires for the trio's directory.

Once admitted, a case is never edited. A case found wrong is retired: the case's identifier, the date and the reason go on a committed list of retired cases, and the case is replaced by a new one when a candidate remains. Score files in the log-store are not edited; the program that prints a report reads the list of retired cases and marks every score it prints for a retired case. The trio's README asks the same thing in its own words: say what is wrong and score again, never correct the case in place.

## Held-out cases

The first ten admitted cases of each kind are development cases. After the first ten, every third case admitted is held out: never used while a change is being developed, and run only to confirm a result before the change goes to the user, because a change tuned against the cases that confirm the change is measured against its own development cases. Related cases share held-out status: the two cases of one rename, and a kind 5 case and the kind 1 case it was built from. When a held-out confirmation fails and the change is revised, the report to the user says how many times those held-out cases have already been used.

## How a change is measured

- The user asks for each measurement, naming the change, the kinds, and the agent-binaries the change affects. Before starting, the evaluation harness prints the number of repetitions the measurement needs: cases times three repetitions times two arms times agent-binaries.
- Each repetition starts a fresh-agent, `claude -p` or `codex exec`, on the user's Claude and ChatGPT subscriptions, not on API keys, in its own case tree, with the task prompt. Repetitions of the two arms alternate, so a change to machine-local files such as `~/.claude/CLAUDE.md` during a measurement reaches both arms; the evaluation harness records each machine-local file's hash at each repetition.
- A repetition not finished after 30 minutes is stopped and scored on what the agent had done.
- A repetition that fails before the agent works, because the agent-binary is logged out, a usage limit is reached or the provider returns an error, is recorded as not measured and tried once more; a second such failure stops the measurement, and the report says why.
- The task prompt tells the agent not to consult GitHub, the log-store or other checkouts. After each repetition, the agent's transcript is searched for `gh`, the log-store's path and other checkouts' paths, and a repetition that consulted one is voided and reported.
- The repository is public, so a model trained after a fix merged may have seen the fix. The report names each agent-binary's model, and cases merged before that model's training cutoff are reported apart from cases merged after it.
- The report lists every repetition's result per case and arm. A case is listed by name as worse with the change when, for kinds 1, 4 and 5, the proposed arm solved or answered correctly fewer of the three repetitions than main; and, for kinds 2 and 3, when the median of expected rows found is lower or the median of false positives is higher. An average over cases can hide such a case, so the list never relies on an average.
- The first evaluation harness is a Python script in this repository. promptfoo (https://github.com/promptfoo/promptfoo) and Inspect AI (https://github.com/UKGovernmentBEIS/inspect_ai) are considered only when the script shows a need either one meets.

## The first questions the benchmark answers

1. Whether a separate fresh-agent that reads a writer's inputs before the writer starts catches more insufficient inputs than the writer's own input-quick-check. `docs/design-to-main/design-to-main-state-machine-design.md` sections 4 and 10 rejected a separate checker for two reasons: the separate state doubled the cost of reading one state-package, and no case showed the separate state catching what the writer's own input-quick-check would not. The user said on 2026-10-09 that quality, not cost, decides, which leaves the second reason. The paper "Ask or Assume?" (arXiv 2603.26233, code and results at https://github.com/nedwards99/ask-or-assume) measured a gain: a separate Intent Agent watching every turn resolved 69.4% of underspecified SWE-bench tasks, against 61.2% for one agent reminded each turn to check. In the paper both arrangements check during the work. A design-to-main writer checks its inputs first, before writing, and may also stop part way through. The measurement adds a step to the evaluation harness for the proposed arm: before the agent under test starts, a separate fresh-agent reads the task text and the case tree and stops the case when the input is insufficient. Both versions of kind 5 cases are measured: a better checker stops more incomplete versions and no more complete ones. Kind 5 cases are bug fixes, not design-to-main writing states, so the result informs the design-to-main decision without settling it.
2. Whether a Claude Code Stop hook, a hook that runs when the agent finishes its reply and can refuse to let the agent finish, reduces false claims by refusing a claim of done or passing tests when no test ran after the last edit. Measured by the false claims recorded on kind 1 cases, and by the solved count, which the hook must not lower.
3. Whether a change to the /cold-read reviewers' prompts finds more of the defects in documents, on kind 3 cases.

## Build order

1. Build the evaluation harness for kind 1 and ten kind 1 cases, taking candidates newest first, so that today's measured files fit their code best, until ten are admitted or the candidates run out. Then test the cases on a change whose direction is known: removing `CLAUDE.md` and `.claude/` from the proposed arm must not raise the solved count, and should lower it. Then measure question 2. The step's report lists each candidate tried and why each one that was not admitted was dropped.
2. Build kinds 2 to 5, each until it has ten development cases and its first held-out cases, and measure questions 1 and 3.
3. Running the benchmark automatically on every pull request that changes a measured file is a later step, admitted by the user on evidence from steps 1 and 2.

## Not covered here

- Changes to programs other than the ones hooks call, which need case trees that combine a program's new version with historical code; a GHI of their own when steps 1 and 2 show the benchmark works.
- Searching for better prompts automatically against the benchmark, as GEPA (https://github.com/gepa-ai/gepa) does. The search needs the benchmark first, and goes in its own GHI.
- Evidence from production.

## Questions for the user

1. Who is the confirmer: the user for every case, as the user was for the trio, or a fresh-agent with the user confirming a sample of its work.
2. How the rows of kinds 2 and 3 are weighted: 1 each, or by consequence on the scale the trio's defect list uses, set by an agent and confirmed by the confirmer.

## Next action

Once question 1 is answered, carry out build step 1.

## Prior work

- GHI [Candidate skill: eval-agent-change — baseline-vs-candidate A/B with trigger cases and raw-count reporting](https://github.com/nedschorus/nedschorus/issues/23), closed as not planned on 2026-09-24, proposed comparing the current and the proposed version of a skill on trigger cases, and to "report raw counts, never average away a safety failure". The benchmark keeps raw counts per case, and lists every case that is worse with a change by name for the same reason.
- The research behind this GHI-MD, comparing outside projects for each of the project's key parts, is in the log-store at `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/deep-dive-2026-10-09/deep-dive-synthesis-2026-10-09.md`.
