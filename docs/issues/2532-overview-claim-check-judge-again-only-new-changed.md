---
issue: "[Overview claim check: judge again only new, changed or flagged claims, and keep a supported claim's verdict while its wording and cited files are unchanged](https://github.com/nedschorus/nedschorus/issues/2532)"
kind: design
---

# Overview claim check: judge again only new, changed or flagged claims, and keep a supported claim's verdict while its wording and cited files are unchanged

## Why

The overview claim check, `nc-systems/skills/overview-write/overview-write-architecture-overview-claim-check-by-fresh-agent.py`, checks an nc-architecture-overview against the code by handing the whole overview to a fresh-agent each round. That fresh-agent gives different verdicts on the same claim from run to run. A claim it supported on one run can be flagged on the next with no change to its wording or to the code it cites: 12 of the 18 claims flagged after the handoff overview's first run were like that. So each round can bring new findings that no fix caused, and a long overview may never come out clean in the three rounds the section "Checking an overview" of `docs/nedschorus-wiki/nedschorus-how-to-write-an-architecture-overview.md` allows.

The user approved this change on 2026-11-03, as item 1.2 of the approval-walk walk-me-through-skill-refactor-approval-walk-2026-11-02 (walk-minutes `nedlern@ned-box:/home/nedlern/agents/cold-read-improvement/docs/walk/walk-me-through-skill-refactor-approval-walk-2026-11-02-minutes.md`, the line "item 1.2 of 16: approved; every text the change adds has had a fast read. <accepted>"), to be built after item 1.1. Item 1.1, the ranks must fix, fix later and nit, merged in pull request [overview-write: the claim check ranks flagged claims, and the merge gate blocks only on claims ranked must fix](https://github.com/nedschorus/nedschorus/pull/2506). His words with that answer: "things that have been checked and proven in one round, claim-wise, not code-wise, maybe, probably should not be rechecked, because as you say, there's some lack of reproducibility for prose checks."

This is the overview claim check's case of point 2 of GHI [Implementing the project's goals and philosophy: every finding sorted into four categories, checked claims kept with their evidence, and one standard in every agent's instructions](https://github.com/nedschorus/nedschorus/issues/2522): a supported claim is kept with its evidence and reopened only when its inputs change. The overview-write skill's own GHI is [overview-write skill: how an overview of a system is written and checked before it lands](https://github.com/nedschorus/nedschorus/issues/168).

## Design

1. **Code splits the overview into claims.** The program, not the model, splits the overview's text into claims, one per sentence, headings left out, and gives each claim a key: a hash of its whitespace-normalized text. Today the fresh-agent splits the overview itself and numbers the claims by their place in that run's list, as in `VERDICT 3 supported: ...`, so no claim can be matched from run to run.
2. **The record of each claim.** The report keeps, for every claim, its key, its verdict, its rank, its evidence, and the files it rests on, each with its git blob hash at the commit the overview's `**Checked against:**` line names. The files it rests on are the repository paths the claim names in backticks and the files its verdict's evidence names; a supported verdict already lists "each file, line number and quoted line it rests on".
3. **The last run.** The program reads the newest report in the overview's report directory, `<report directory>/<overview file name without .md>/`, whatever overview blob it names. With no report there, every claim is judged.
4. **Which claims go to the model again.** A claim is judged again when any of these holds: its key is not in the last report; the last report did not give it the verdict supported; the writer disputes its verdict with `--writer-answers`; one of the files it rests on has a different blob hash at this run's commit; it rests on no file. Every other claim keeps its last verdict and evidence, and the report says which report it was kept from.
5. **The model judges only those claims.** The fresh-agent is given the whole overview for context and the claims to judge, numbered 1 to n. Code maps each number back to its key and rejects a report whose verdicts do not cover exactly those numbers, as the parser already checks the numbering and the COUNTS line today. The one-claim recheck of a claim ranked must fix stays as it is.
6. **The merge gate is unchanged.** The report's result line stays as it is, so `scripts/pull-request-review-plan.py`, which reads it through `find_newest_architecture_overview_claim_check_report_path_and_result_for_overview_git_blob()`, needs no change.
7. **Code is still retested on every change.** This applies to prose claims about code, not to the code: tests run as they do today.

What this does not handle: a claim made false by a change to a file it does not rest on keeps its verdict. The approval-walk named this risk (`#case_against medium`), and the user approved the change with it; taking the files from the verdict's evidence, not only from the claim's wording, keeps the risk small. A claim ranked fix later or nit goes to the model again each round, as the approved item says, and can come back with a different rank.

## Next action

Build steps 1 to 7 in `nc-systems/skills/overview-write/overview-write-architecture-overview-claim-check-by-fresh-agent.py` and its test. Change its prompts and stage 2 of the section "Checking an overview" in `docs/nedschorus-wiki/nedschorus-how-to-write-an-architecture-overview.md` to match: its sentence "It splits the overview into single assertions and checks every assertion about the code" changes so that the fresh-agent checks the assertions it is given. Then put the new prompt wording to the user before the merge, as he approves every prompt a pull request hands an agent. Owner: cold-read-improvement.
