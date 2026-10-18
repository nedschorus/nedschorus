# One shared list of the kinds of check failure, used by reviewers, authors and test writers, and a daily check that each kind is handled the same way

Status: draft, not filed. The user asked for it on 2026-10-18, in the approval-walk `md-skills-seat-open-decisions-2026-10-15` (item 19), after two independent searches found that a failing check can mean several different things and that agents handle each one differently.

## The problem

The project's checks are its test suites, the pull request reviewers, the merge gate, merge-lane-2's head test run, the guard hooks, the git client-side hooks, the cold-read grid, the prerequisite checks, `scripts/branch-conflict-check.py` and the canary tests. Their outcomes are not just pass or fail. Between them they produce about ten kinds of non-pass outcome, listed below. No glossary entry, wiki page or CLAUDE.md line defines these kinds as a set. Each check uses its own words and its own exit codes for them, and agents handle the same kind in different ways.

The evidence is in four reports, two by Codex and two by Claude subagents, which searched independently, and in their combined summary, all in `nedlern@ned-box:/home/nedlern/nedschorus-logs/analysis/canary-cases-and-failure-kinds-2026-10-18/` (`summary.md`, `failure-kinds-codex.md`, `failure-kinds-claude.md`, `canary-trawl-codex.md`, `canary-trawl-claude.md`). The cases below come from them.

**The same kind handled differently.**
- A test already failing on main was ignored, merged over, rerun, filed as a GHI or fixed at the root, depending on the agent. On 2026-10-14 the test `scripts/run-codex-task-from-brief-test.py` got three of those handlings from three agent-seats; merge-lane-2 then filed GHI [The Codex task runner's deadline test case fails on a busy machine, because a scan of the whole home directory runs before the deadline starts](https://github.com/nedschorus/nedschorus/issues/1323).
- A Mac test case noted as "also fails on main" was pushed over in four pull requests, starting with PR [Claude Code Bash hook: remind the agent to run both citation checks when a git push sends a branch that changes a Markdown file](https://github.com/nedschorus/nedschorus/pull/1354), and fixed only in PR [Bash guards replay: a checkout named through a symlink is removed by git, not deleted as unregistered](https://github.com/nedschorus/nedschorus/pull/1452).
- A failure called "a flake" in PR [handoff dialog: each subagent's task and report as a third voice; ned-box keeps every session's complete dialog current in the log-store](https://github.com/nedschorus/nedschorus/pull/1188) was a deterministic defect, GHI [The signal sandbox test's fake bwrap fails when its status descriptor number is 10 or more, so the test fails at random](https://github.com/nedschorus/nedschorus/issues/1233), which had held six unrelated pull requests.
- Non-blocking findings sometimes got a follow-up pull request or a written decline, as in PR [Fast-read reminder: the marked-as-read note and stderr line say only what is true, mutant M6 is killed, and every registered hook's constants are scanned for citations](https://github.com/nedschorus/nedschorus/pull/1593), and sometimes nothing visible, as in PR [run-all-test-suites.py: kill a suite past a time limit sized from its recorded duration](https://github.com/nedschorus/nedschorus/pull/1560).
- Two reviewers gave the same finding different merge consequences in PR [The cold-read-cells read the frozen copy, which is what freezing meant](https://github.com/nedschorus/nedschorus/pull/636).

**The same kind called by different words.**
- A finding that need not be fixed before the merge is called "advice", "does not block", "non-blocking finding", "follow-up" and "findings that do not block".
- `scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py` treats a review comment as blocking only when it begins with `**Blocks.**` (its constant `BLOCKING_MARKER`). No file on main tells a reviewer to write that marker: `git grep '\*\*Blocks\.\*\*' origin/main` finds it only in that script and its test.
- "Could not run" and "failed" are kept apart by `scripts/run-all-test-suites.py` (exit 2 against exit 1) and by the cold-read grid ("a run that produced no report is not a review that found nothing"), but `nc-systems/handoff/uncommitted-work-snapshot-hook-real-claude-session-weekly-owner-check.py` reports a lapsed login or a network outage as `VERDICT: FAILED`.
- `docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md` requires a program that fails open to say the act was not checked; several guard hooks fail open silently on bad input.
- One test suite prints `SKIP:`, which the test runner's pattern `^SKIP\s` does not count.

**Why it matters.** When the kinds are not defined, an agent decides each case alone, from its own reading. A real defect labelled "flaky" stays unfixed and holds other pull requests; a "could not run" read as a pass merges unchecked work; a non-blocking finding with no follow-up is lost. The user cannot see from the records which of these happened.

## The proposed list of kinds

Each kind has a name, a one-line definition, what it leads to, and who decides. The names are plain prose until the user rules on them (see Proposed terms).

1. **Blocks.** The check ran and found a defect that this change introduces. Leads to: a fix before the merge. Decides: the reviewer or the check reports it; merge-lane-2 holds the merge.
2. **Already failing on main.** The same failure happens on main without this change. Leads to: never merged over; per the user's ruling of 2026-10-13, cleared by a passing rerun, or by a separate pull request that fixes, deletes or skips the test, with a GHI tracking it. Decides: merge-lane-2, by comparing the head test run with the same day's daily full test run of main.
3. **Fails at random.** The check fails, then passes with no change. Leads to: the failure recorded with its log; a GHI at the second sighting; never assumed to be machine load without evidence, because two failures so labelled were real defects. Decides: whoever sees the second sighting files the GHI.
4. **Could not run.** The check reached no answer: it crashed, timed out, lacked a program or login, or its tool was down. Leads to: never treated as a pass; the cause named; a cause the user can clear, such as a lapsed login or a usage limit, told to the user. Decides: open question 1.
5. **Let through unchecked.** The check could not run and let the act go ahead. Leads to: the program says so where the agent will see it. Decides: the program's author, at build time.
6. **Skipped.** A test case chose not to run, for example because it applies only to the other machine. Leads to: printed in one format that the test runner counts, as GHI [The daily full test runs tell the user about failures and about test cases that run nowhere or lack a tool, and every test suite prints a skipped test case in one format](https://github.com/nedschorus/nedschorus/issues/1206) plans. Decides: the test writer.
7. **Advice.** A real finding that need not be fixed before the merge. Leads to: a follow-up pull request or a written decline, as CLAUDE.md already requires. Decides: merge-lane-2 decides a finding is advice; the author follows it up.
8. **Question.** A matter for a decision, not a defect. Leads to: put to the user, or to the reviewer, never left in a review unanswered. Decides: open question 3.
9. **False alarm.** The finding does not hold. Leads to: the author says why, in the pull request; when the check is a program, its cause is fixed so it does not recur. Decides: the author answers; merge-lane-2 accepts or rejects the answer.
10. **Outside program changed.** A program the project calls but does not write behaved differently from what the code assumes, now or after an upgrade. Leads to: a fix with `Root cause:` naming the outside program, and a canary test where the canary design asks for one. Decides: the author.

The canary design, `docs/drafts/canary-tests-when-required-who-runs-them-and-where-they-live-design-draft.md` on its own branch, splits kinds 4 and 10 further for canary tests (wrong only on the other machine, wrong only after an upgrade or at a reboot, a false pass from probing the wrong command). That split belongs to the canary design and uses this list's names.

## Where the definitions live

One wiki page, `docs/nedschorus-wiki/nedschorus-kinds-of-check-failure.md` (name to be checked against the naming page), holds the table above with one real example of each kind. The project glossary gets one entry pointing to it.

## Which files must use them

- `docs/agents/pr-reviewer-instructions.md` and CLAUDE.md's review bullet, which are kept word for word alike by `scripts/pr-reviewer-instructions-copies-test.py`: a reviewer labels each finding with its kind.
- `.claude/skills/pull-request-review-write/SKILL.md`: how the label is written in a review comment, so that the fix-round brief script can read it. Either the skill teaches `**Blocks.**`, or the script reads the new labels.
- The fix-round brief script above.
- The test runner, the daily full test run and the weekly real-Claude check: their exit codes and summary lines map to kinds 1, 3, 4 and 6, and the weekly check reports a lapsed login as could-not-run, not as a failure.
- The guard hooks that fail open silently: they say so (kind 5). GHI [Every refusal and warning a program hands an agent says why and what to do instead](https://github.com/nedschorus/nedschorus/issues/956) covers the wording; this GHI covers only which kind each outcome is.
- merge-lane-2's seat-brief, which is outside the repository: merge-lane-2 is told of the list and updates it itself.

## The consistency check

A daily job in the daily maintenance step of GHI [Daily maintenance in one daily step, starting with a daily check of every wiki page](https://github.com/nedschorus/nedschorus/issues/1058). It reads the pull requests merged since its last run (descriptions, reviews, comments), the head test run records and the daily full test run records in the log-store, and the runner's test case failure history. It reports to the user, and to merge-lane-2, each case where:
- a test failing on a pull request's head also failed on main that day, and the pull request merged without a GHI or a separate pull request for it (kind 2);
- the same test failed in head test runs of two unrelated pull requests, or failed and then passed on one commit, with no GHI after two sightings (kind 3);
- a finding labelled advice in an approving review has no later pull request citing it and no written decline (kind 7);
- a "Not checked", "not run" or "Codex review not run" line before a merge is not named in the merge decision (kind 4);
- a test suite printed a skip the runner did not count (kind 6);
- an instruction file uses a word for a kind that the wiki page does not list.

It would have caught the already-failing-on-main, flaky and advice cases above. It cannot catch false alarms or outside-program changes until pull request descriptions label them, so the check reads a `False alarm:` or `Outside program changed:` line when one is present.

## Next action

The user rules on the open questions and the proposed terms. Then this GHI-MD gets its /cold-read, is filed, and the work is built in this order: the wiki page and glossary entry; the instruction files and the fix-round script; the exit codes and summary lines; the consistency check.

## Proposed terms

- check failure kind: one of the ten kinds of non-pass outcome listed in this GHI, each with a defined consequence.
- already failing on main: a failure that also happens on main without the change under test.
- could not run: a check that reached no answer, which is never a pass and never a failure of the change.

## Open questions for the user

1. When a check could not run before a merge, may the pull request merge with the gap named, or must the check run first? Today both happen (merged with a "Not checked" note, or the check run by hand).
2. Your ruling of 2026-08-23 added an `external` value that never routes to a fix now; your ruling of 2026-10-13 says an unrelated failure is cleared by a passing rerun, not merged over. Do both stand, and does `external` mean kind 2 or kind 10?
3. A question a reviewer raises: does it go into the review for the author, as the review-write skill says, or to you, as CLAUDE.md says?
4. Should every check use one exit-code convention for these kinds (for example 0 pass, 1 blocks, 2 could not run), or only one set of words in its output?
5. Your ruling that a needless guarded-file alarm is cleared without asking you is recorded only in a memory file on ned-box, so agent-seats on the Mac do not have it. Should it go into the false-alarm row of the wiki page?
