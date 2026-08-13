<!-- provenance: runtime=codex model=gpt-5.6-terra effort=xhigh cell=restate tier=floor target=/Users/el/Projects/nedschorus/.claude/worktrees/linters-tool-usage-f8b0a0/.claude/skills/ghi-write/SKILL.md -->

## Frontmatter

1. Apply this skill before making any change that affects a GitHub issue in this project, including creating an issue, changing an issue’s main body text, adding an issue comment, or turning material from a queue into an issue.

2. Creating or updating any project artifact that could properly belong in an issue also requires this skill, because deciding where that material belongs is part of the skill’s required routing work.

3. This skill does not apply when the only action is reading an issue or citing it as a reference.

## When Used

1. Use this skill before creating an issue, changing an issue’s body, commenting on an issue, or writing project material when it has not yet been decided whether that material belongs in an issue, a queue, or a Markdown document.

## What to do

1. Ask before creating a new issue.

2. Send the subject to `ghi-info` by running `scripts/ghi-info-ask.py` with a question; when the question concerns precedent or whether something is absent, include `--include-closed`; then read both the issues returned by that command and the paired documents those issues cite.

3. If an existing artifact already addresses the subject, update that artifact instead of creating another one; ordinarily, the correct outcome is to revise the existing issue, matching the `md-write` convention that prefers revision over creating a new record.

4. Failure of the ask operation must not prevent the write: search the local mirror with `grep`, then search with `gh`, and continue while following the remaining rules.

5. Choose the destination based on the artifact’s state.

6. Every artifact must either be final in its proper destination or be placed in a specifically named queue that has a defined process for moving its contents onward.

7. Put material whose final disposition has not been decided into its appropriate destination queue—`docs/wiki/queue/` for doctrine intended for the wiki, `docs/issues/queue/` for Markdown documents intended to be paired with issues, or the `draft` label for issues being queued—and do not create a GitHub issue for that material at this stage.

8. Anything that represents unfinished or pending state—such as a desired feature or component, an unresolved question, or a promise to take action—must have a GitHub issue: use only an issue when its body will remain below 500 words, and use an issue-plus-Markdown pair when substantial working material accompanies it.

9. Put the summary in the issue body and the detailed substance in the paired Markdown document; when making such a pair, create the Markdown document first, get it landed in the project, and only then cite it from the issue.

10. Final reference material that is not awaiting any further decision or action belongs as an unpaired Markdown document in its final location.

11. The decision rule is that a GitHub issue records state, a Markdown document contains substantive material, and a queue holds material whose destination is still undecided.

12. If routing is truly unclear, create an issue labeled `draft` and continue; uncertainty about routing must never stop the write.

13. Make revisions by changing the issue body.

14. Put clarifications, corrections, and changes of scope into the issue body, including corrections to references that already appear there.

15. Use a comment only for a genuinely new event, specifically an outcome from an instance or a challenge to a prior ruling.

16. Do not treat completion as a comment: record the completed outcome in the issue body and then close the issue with the applicable reason.

17. Never create a second issue when editing the first issue would serve the purpose.

18. This rule deliberately rejects the usual practice of accumulating comments and new records, because the issue’s edit history is intended to preserve the before-and-after record.

19. Write so that someone with no prior context can understand the issue.

20. Before submitting, verify three things: the issue by itself identifies what it concerns, it explains why it exists, and a reader who was not part of this conversation can carry out the stated next action.

21. Ensure every reference can be opened and every claim has been checked.

22. A file reference must be usable from the reader’s own context: use complete URLs for material outside this repository, and cite in-repository paths only after verifying that they exist on `main`.

23. Perform inexpensive verification before filing: if one `grep` or one `gh` command can answer a question, run it now, so the issue body states confirmed facts rather than possibilities.

24. Any claim that something is absent must include a search receipt stating both the query used and the scope searched that produced no results.

## How to do it

1. To ask, run `scripts/ghi-info-ask.py "<question>"`; add `--include-closed` for questions about precedent or absence. If that ask fails, fall back in this order: search `ghi-mirror/` in the checkout, recognizing that it is stale unless it was regenerated recently; then run `gh issue list --repo nedschorus/nedschorus --state all --search "<terms>"`; then search the repository for paired documents about the subject.

2. To create an issue, run `gh issue create --repo nedschorus/nedschorus --title "<title>" --body-file <file>`.

3. To edit an issue, run `gh issue edit <number> --repo nedschorus/nedschorus --body-file <file>`.

4. To close an issue, first edit its body to record the outcome, then run `gh issue close <number> --repo nedschorus/nedschorus --reason "completed"` or use `"not planned"` as the reason.

5. For the only two permitted comment-event types, submit the comment through the comment verb of `scripts/ghi-issue-write.py` and name the event kind; the normal `gh issue comment` command is rejected by this project’s write path.

6. Draft issue bodies in a file and provide that file with `--body-file`; using inline `--body` text containing backticks causes the shell to alter that text without reporting the alteration.

7. For queue routing, create the queue file in its destination directory or apply the `draft` label to the issue; the process that drains queued material is defined by [nedschorus#24](https://github.com/nedschorus/nedschorus/issues/24).
