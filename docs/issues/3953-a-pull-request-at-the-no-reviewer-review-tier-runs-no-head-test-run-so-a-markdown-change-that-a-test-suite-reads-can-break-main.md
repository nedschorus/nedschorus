---
issue: "[A pull request at the no-reviewer review tier runs no head test run, so a Markdown change that a test suite reads can break main](https://github.com/nedsnodes/nedsnodes/issues/3953)"
---

# A pull request at the no-reviewer review tier runs no head test run, so a Markdown change that a test suite reads can break main

Filed by merge-lane-2, which owns this issue. Every line number below is in the file as it is on main at `1647b697b`.

## Reproduction

1. PR [Walk-me-through skill: an item that only rewords an approved change or only makes text clearer is not shown](https://github.com/nedsnodes/nedsnodes/pull/3899) changed one file, `.claude/skills/walk-me-through/SKILL.md`, a standing instruction file. Its last sentence on line 42 gained the date `2026-11-17`. `scripts/pull-request-review-plan.py` gave the pull request `no-reviewer-tier`, and merge-lane-2's posted review says "Review tier: no-reviewer-tier, because the pull request changes only prose in .claude/skills/walk-me-through/SKILL.md. No reviewer ran, and the tier called for none." Its review file is `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-helpers/merge-lane-2-review-3899r1.json`.
2. No head test run ran on it. Receipts: `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-helpers/hr/pr3899` does not exist, while `hr/`, the directory where `scripts/merge-lane-pull-request-head-test-run-on-merged-worktree.py` files each pull request's head test run records, holds directories for other pull requests, such as `hr/pr1143`; and the after-merge test run selected suites "by inputs changed since e2467fb716b2", the pull request's own head commit, which is what the merge program falls back to, and says it falls back to, when no passing head test run record exists.
3. `scripts/standing-instructions-carry-no-citations-test.py` fails when a standing instruction file carries a date. The pull request merged on 2026-11-20 at 17:18Z as `b46d47c2bdbe`. The after-merge test run of that merge commit selected the suite, and the suite failed: `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-helpers/pr3899-after-merge-test-run-logs-b46d47c2bdbe/test-run-report.txt` shows `FAIL scripts/standing-instructions-carry-no-citations-test.py exit 1` and the SUMMARY line `56 passed, 1 failed, 1 not run`; the suite's log, `scripts__standing-instructions-carry-no-citations-test.py.log` in the same directory, names `.claude/skills/walk-me-through/SKILL.md:42`.
4. Main went on failing that suite. The after-merge test run of the merge commit of PR [GHI-MD for issue 3902: The Gemini task launcher's read-only `~/.gemini` stops agy from saving its refreshed Google login](https://github.com/nedsnodes/nedsnodes/pull/3903), `1c64cdc25be8`, failed it again: `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-helpers/pr3903-after-merge-test-run-logs-1c64cdc25be8/scripts__standing-instructions-carry-no-citations-test.py.log`. Why nobody acted on the first failure is not established here (unverified).
5. PR [Standing-instructions citation test: except the walk-me-through skill's clarity-only ruling citation](https://github.com/nedsnodes/nedsnodes/pull/3944), open when this issue was filed, adds a test exception for that line. It makes main pass again, but leaves the cause below in place.

## Cause

A Markdown file that a test suite reads, such as a standing instruction file, can change in a pull request whose review tier runs no test suite before the merge.

What the code does:

- In `scripts/pull-request-review-plan.py`, `classify_changed_file_into_class_tier_and_reason` gives a `.md` file whose diff touches no line inside a fenced code block the class `prose` and the tier `no-reviewer-tier` (lines 509-520), and gives the same to any other file under `docs/` or `nn-queue/` without a code extension (lines 521-523). Nothing in the function asks whether a test suite reads the file. The module docstring states the rule: "Markdown prose anywhere is no-reviewer-tier because prose outside code is outside the review scope." (lines 121-122). A pull request takes the strictest tier of its files (`review_tier_and_deciding_reason`, lines 578-584), so a pull request that changes only such files gets `no-reviewer-tier`.
- The tier names say which tiers include a head test run: `codex-review-and-head-tests-tier` and `claude-and-codex-review-and-head-tests-tier` do, and `no-reviewer-tier` does not (line 216).
- `test_files_to_run_for_changed_files` (lines 837-854) maps only a changed `-test.py` file or a changed `.py` program to test files, so a changed Markdown file yields none. Only the plan's printed output (lines 1240 and 1265) and its own test, `scripts/pull-request-review-plan-test.py`, read that list: `git grep -n test_files_to_run origin/main -- scripts nn-systems` finds no other reader. The head test run does not use the list: `scripts/pull-request-head-test-run.py` selects suites by their recorded inputs, passing `--only-suites-whose-recorded-inputs-changed-since` to the runner (line 352), the same way the after-merge test run selected the failing suite in step 3.
- The skip of the head test run is in merge-lane-2's seat-brief, not in code. The seat-brief runs `scripts/merge-lane-pull-request-worktrees-reviewer-brief-codex-review-and-head-tests-run-without-merge.py`, the program that holds the head test run step, only "at any tier but no-reviewer-tier". That program checks the tier only to skip the Claude reviewer step (line 422).
- `scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py` tests main only after the merge. When no head test run record passed, it selects suites changed since the head commit (lines 459-468); when that run fails, it prints `STOP: merged, but the test run of main ... so main may be broken` and exits 3 (lines 562-568). By then the change is on main.

## Options

No option is chosen here. The options seen so far:

- Run the head test run at every tier, `no-reviewer-tier` included, so that a prose-only pull request still runs, before it merges, the suites whose recorded inputs it changes.
- Give a Markdown file that some suite's recorded inputs include a tier with a head test run, and keep `no-reviewer-tier` for files no suite reads. The two tiers that have a head test run today also have a Codex or Claude reviewer, so this option either sends such prose to a code reviewer or adds a new tier with tests and no reviewer.
- Make `test_files_to_run_for_changed_files` list the suites whose recorded inputs include a changed Markdown file, and have a program, not merge-lane-2's memory, run those suites at `no-reviewer-tier` and record that they passed.
- Have the merge program refuse a merge that has no passing head test run record, whatever its tier. This option needs the first option, or every prose-only pull request would be refused; with it, the rule that a head test run happens moves from the seat-brief into code.
- Separately from the tier gap: have the merge program refuse the next merge while the latest after-merge test run of main failed, until it passes or the user overrides it, so that a failure such as step 3's cannot stay unnoticed across later merges, as it did until step 4.
- Fold the fix into the review-tier work of GHI [3889](https://github.com/nedsnodes/nedsnodes/issues/3889), or into GHI [3891](https://github.com/nedsnodes/nedsnodes/issues/3891), which posts every merge-lane-2 review through one program, as ghi-guide-agent suggested. Both concern the same review tiers, but neither covers this gap.

## Next action

merge-lane-2 chooses an option, bringing it to the user first when it changes what merge-lane-2's seat-brief tells it to do, and opens the pull request that carries it, with a test that reproduces a prose-only pull request changing a file that a suite reads.
