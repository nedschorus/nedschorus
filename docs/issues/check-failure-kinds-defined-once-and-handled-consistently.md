# One shared list of the kinds of check failure, used by reviewers, authors and test writers, and a daily check that each kind is handled the same way

Status: draft, not filed. The user asked for it on 2026-10-18, in the approval-walk `md-skills-seat-open-decisions-2026-10-15` (item 19), after two independent searches found that a failing check can mean several different things and that agents handle each one differently.

## The problem

The project's checks are its test suites, the pull request reviewers, the merge gate, merge-lane-2's head test run, the guard hooks, the git client-side hooks, the cold-read grid, `scripts/branch-conflict-check.py`, the canary tests, and the prerequisite checks that GHI [Check every prerequisite of the fleet's programs before an agent-session starts](https://github.com/nedschorus/nedschorus/issues/1055) plans. Their outcomes are not just pass or fail. Between them they produce about ten kinds of non-pass outcome, listed below. No glossary entry, wiki page or CLAUDE.md line defines these kinds as a set. Each check uses its own words and its own exit codes for them, and agents handle the same kind in different ways.

The evidence is in four reports, two by Codex and two by Claude subagents, which searched independently, and in their combined summary, all in `nedlern@ned-box:/home/nedlern/nedsnodes-logs/analysis/canary-cases-and-failure-kinds-2026-10-18/` (`summary.md`, `failure-kinds-codex.md`, `failure-kinds-claude.md`, `canary-trawl-codex.md`, `canary-trawl-claude.md`). The cases below come from them.

**The same kind handled differently.**
- A test already failing on main was ignored, merged over, rerun, filed as a GHI or fixed at the root, depending on the agent. On 2026-10-14 the test `scripts/run-codex-task-from-brief-test.py` got three of those handlings from three agent-seats; merge-lane-2 then filed GHI [The Codex task runner's deadline test case fails on a busy machine, because a scan of the whole home directory runs before the deadline starts](https://github.com/nedschorus/nedschorus/issues/1323).
- A Mac test case noted as "also fails on main" was pushed over in four pull requests, starting with PR [Claude Code Bash hook: remind the agent to run both citation checks when a git push sends a branch that changes a Markdown file](https://github.com/nedschorus/nedschorus/pull/1354), and fixed only in PR [Bash guards replay: a checkout named through a symlink is removed by git, not deleted as unregistered](https://github.com/nedschorus/nedschorus/pull/1452).
- A failure called "a flake" in PR [handoff dialog: each subagent's task and report as a third voice; ned-box keeps every session's complete dialog current in the log-store](https://github.com/nedschorus/nedschorus/pull/1188) was a deterministic defect, GHI [The signal sandbox test's fake bwrap fails when its status descriptor number is 10 or more, so the test fails at random](https://github.com/nedschorus/nedschorus/issues/1233), which had held six unrelated pull requests.
- Non-blocking findings sometimes got a follow-up pull request or a written decline, as in PR [Fast-read reminder: the marked-as-read note and stderr line say only what is true, mutant M6 is killed, and every registered hook's constants are scanned for citations](https://github.com/nedschorus/nedschorus/pull/1593), and sometimes nothing visible, as in PR [run-all-test-suites.py: kill a suite past a time limit sized from its recorded duration](https://github.com/nedschorus/nedschorus/pull/1560).
- Two reviewers gave the same finding different merge consequences in PR [The cold-read-cells read the frozen copy, which is what freezing meant](https://github.com/nedschorus/nedschorus/pull/636).

**The same kind called by different words.**
- A finding that need not be fixed before the merge is called "advice", "does not block", "non-blocking finding", "follow-up" and "findings that do not block".
- `scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py` treats a review comment as blocking only when it begins with `**Blocks.**` (its constant `BLOCKING_MARKER`). No file on main tells a reviewer to write that marker: `git grep '\*\*Blocks\.\*\*' origin/main` finds it only in that script and its test.
- "Could not run" and "failed" are kept apart by `scripts/run-all-test-suites.py` (exit 2 against exit 1) and by the cold-read grid ("a run that produced no report is not a review that found nothing"), but `nn-systems/handoff/uncommitted-work-snapshot-hook-scheduled-check-that-real-claude-session-is-recorded-as-owner.py` reports a lapsed login or a network outage as `VERDICT: FAILED`.
- `docs/nedsnodes-wiki/nedsnodes-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md` requires a program that fails open to say the act was not checked; several guard hooks fail open silently on bad input.
- One test suite prints `SKIP:`, which the test runner's pattern `^SKIP\s` does not count.

**Why it matters.** When the kinds are not defined, an agent decides each case alone, from its own reading. A real defect labelled "flaky" stays unfixed and holds other pull requests; a "could not run" read as a pass merges unchecked work; a non-blocking finding with no follow-up is lost. The user cannot see from the records which of these happened.

## The proposed list of kinds

The kind names below are plain prose; only the three under Proposed terms are proposed as project-terms. "Decides" names who sets the kind for a given case.

| # | Kind | Definition | Leads to | Decides |
|---|---|---|---|---|
| 1 | Blocks | The check ran and found a defect that this change introduces. | A fix before the merge. | The reviewer or the check reports it; merge-lane-2 holds the merge. |
| 2 | Already failing on main | The same test fails on main without this change. | Never merged over; cleared by a separate pull request that fixes, deletes or skips the test, with a GHI tracking it. | merge-lane-2, from the head test run compared with the same day's daily full test run of main: failing on main too is kind 2; passing on main and passing on a rerun of the head is kind 3. |
| 3 | Fails at random | The check fails, then passes on the same commit. | The failing log is cited in a pull request comment; the pull request may merge on the passing rerun; a GHI at the second sighting. Never put down to machine load without evidence: two failures so labelled were real defects. | Whoever sees the second sighting, found in `test-case-failure-history.jsonl`, which `scripts/run-all-test-suites.py` appends each failing case to, files the GHI. |
| 4 | Could not run | The check reached no answer: it crashed, timed out, lacked a program or login, or its tool was down. | Never a pass; the cause named; a cause the user can clear, such as a lapsed login or a usage limit, told to the user. | Open question 1. |
| 5 | Let through unchecked | The check could not run and let the act go ahead. | The program says so where the agent will see it. | The program's author, at build time; what the agent then does is open question 6. |
| 6 | Skipped | A test case chose not to run, for example because it applies only to the other machine. | Printed in one format that the test runner counts, as GHI [The daily full test runs tell the user about failures and about test cases that run nowhere or lack a tool, and every test suite prints a skipped test case in one format](https://github.com/nedschorus/nedschorus/issues/1206) plans. | The test writer. |
| 7 | Advice | A real finding that need not be fixed before the merge. | A follow-up pull request, or a written decline: a reply on the finding's review comment saying why it is not followed up. CLAUDE.md already requires one of the two. | The reviewer labels it; merge-lane-2 may relabel it in its review, saying so; the author follows it up. |
| 8 | Question | A matter for a decision, not a defect. | Answered before the merge. | Open question 3. |
| 9 | False alarm | The finding does not hold. | The author says why in a reply on the finding; when the check is a program, its cause is fixed so it does not recur. | The author answers; merge-lane-2 accepts or rejects the answer. |
| 10 | Outside program changed | A program the project calls but does not write behaved differently from what the code assumes, now or after an upgrade. | A fix whose description has a `Root cause:` line naming the outside program, and a canary test where the canary design asks for one. | Open question 7. |

The canary design, `docs/drafts/canary-tests-when-required-who-runs-them-and-where-they-live-design-draft.md` on branch `canary-tests-when-required-who-runs-them-and-where-they-live-design-topic-branch`, splits kinds 4 and 10 further for canary tests (wrong only on the other machine, wrong only after an upgrade or at a reboot, a false pass from probing the wrong command), using this list's names.

## Where the definitions live

One wiki page holds the table above with one real example of each kind. Its proposed name, `docs/nedsnodes-wiki/nedsnodes-kinds-of-check-failure.md`, is still to be checked against `docs/nedsnodes-wiki/nedsnodes-how-to-choose-a-name-for-files-code-and-glossary-terms.md`. The project glossary gets one entry, check-failure-kind if the user approves that term, pointing to the page.

## Which files must use them

- `docs/agents/pr-reviewer-instructions.md`, to which CLAUDE.md's review bullet points: a reviewer labels each finding with its kind.
- `.claude/skills/pull-request-review-write/SKILL.md`: how the label is written in a review comment, so that a program can read it.
- `scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py`, which today reads only the `**Blocks.**` marker (open question 4).
- `scripts/run-all-test-suites.py`, `scripts/scheduled-full-test-run-of-main.py` and `nn-systems/handoff/uncommitted-work-snapshot-hook-scheduled-check-that-real-claude-session-is-recorded-as-owner.py`: their exit codes and summary lines map to kinds 1, 4 and 6, and the owner check reports a lapsed login as kind 4, not as a failure. Kind 3 cannot be seen in one run; the consistency check finds it across runs.
- The guard hooks that fail open silently: they say so (kind 5). GHI [Every refusal and warning a program hands an agent says why and what to do instead](https://github.com/nedschorus/nedschorus/issues/956) covers the wording; this GHI covers only which kind each outcome is.
- merge-lane-2's seat-brief, which is outside the repository: merge-lane-2 is told of the list and updates it itself.

## The consistency check

A daily job in the daily maintenance step of GHI [Daily maintenance in one daily step, starting with a daily check of every wiki page](https://github.com/nedschorus/nedschorus/issues/1058). It reads the pull requests merged since its last run (descriptions, reviews, comments), the head test run records and daily full test run records in the log-store, and `test-case-failure-history.jsonl`. It reports to the user, and to merge-lane-2, each case where:
- a test failing on a pull request's head also failed on main that day, and the pull request merged without a GHI or a separate pull request for it (kind 2);
- the same test failed on two pull requests' heads, or failed and then passed on one commit, with no GHI after the second sighting (kind 3);
- a finding labelled advice has, after the grace period of open question 5, no later pull request citing it and no written decline (kind 7);
- a "Not checked", "not run" or "Codex review not run" line in a pull request is not named in merge-lane-2's approving review (kind 4);
- a test suite printed a skip the runner did not count (kind 6);
- an instruction file uses a word for a kind that the wiki page does not list.

It would have caught the already-failing-on-main, fails-at-random and advice cases above. It cannot judge false alarms or outside-program changes; for those it checks only that a finding left unfixed has a reply, or a `False alarm:` or `Outside program changed:` line in the description, and merge-lane-2 judges the content.

## Next action

The user rules on the open questions and the proposed terms. Then this GHI-MD gets its /cold-read, is filed, and the work is built in this order: the wiki page and glossary entry; the instruction files and the fix-round script; the exit codes and summary lines; the consistency check.

## Proposed terms

Each stays plain prose until the user approves it; approved, it takes the hyphenated form.
- check failure kind: one of the ten kinds of non-pass outcome listed in this GHI, each with a defined consequence.
- already failing on main: a failure that also happens on main without the change under test.
- could not run: a check that reached no answer, which is never a pass and never a failure of the change.

## Open questions for the user

1. When a check could not run before a merge, may the pull request merge with the gap named, or must the check run first? Today both happen. Recommendation: the check runs first, unless the user is told and agrees.
2. Your ruling of 2026-08-23 added an `external` value that never routes to a fix now; your ruling of 2026-10-13 says an unrelated failure is cleared by a passing rerun, not merged over. This draft reads a passing rerun as kind 3 and requires a separate pull request for kind 2. Do both rulings stand, and does `external` mean kind 2 or kind 10? Recommendation: `external` is kind 10, and a failure that also fails on main is never cleared by a rerun.
3. A question a reviewer raises: does it go into the review for the author, as `.claude/skills/pull-request-review-write/SKILL.md` says, or to you, as CLAUDE.md says? And does merge-lane-2 hold the merge until it is answered? Recommendation: a question about the code goes to the author in the review, a question about what the project wants goes to you, and the merge waits for the answer in both cases.
4. Reviewers' labels against the fix-round script's `**Blocks.**` marker: should the review-write skill teach the marker, or the script read the new kind labels? Recommendation: the script reads the kind labels, so there is one vocabulary.
5. How long may an advice finding go without a follow-up pull request or a written decline before the consistency check reports it? Recommendation: 7 days after the merge.
6. When a program says it let an act through unchecked (kind 5), what does the agent do? Recommendation: it runs the check by hand before relying on the act, or tells you why it cannot.
7. Kind 10: who decides that an outside program changed, the author alone or merge-lane-2 on the author's evidence? Recommendation: merge-lane-2, as for kind 9, because the label excuses a defect.
8. Your ruling that a needless guarded-file alarm is cleared with `--restore` without asking you is recorded only in `/home/nedlern/.claude/projects/-home-nedlern-Projects-nedsnodes/memory/guard-false-alarm-act-without-asking.md` on ned-box, so agent-seats on the Mac do not have it. Should it go into the false-alarm row of the wiki page? Recommendation: yes.
