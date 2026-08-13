<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=restate tier=good target=/Users/el/Projects/nedschorus/.claude/worktrees/linters-tool-usage-f8b0a0/.claude/skills/ghi-write/SKILL.md -->

## Frontmatter

1. Use this skill before performing any write operation that affects a GitHub issue in this project. Such operations include creating an issue, changing an issue’s body, adding a comment, and turning material from a queue into an issue.

2. The skill also applies before creating or revising any project artifact that could properly belong in a GitHub issue, even if no issue operation has yet been chosen. This is because deciding whether the material belongs in an issue, a queue, or another artifact is itself part of the skill’s job.

3. The skill does not apply when the only action is reading an issue or referring to an issue as a source.

## When Used

1. Invoke this skill before creating an issue, changing an issue’s body, commenting on an issue, or writing project material when it has not yet been decided whether that material belongs in an issue, a queue, or a Markdown document.

## What to do

1. Before creating an issue, first investigate whether an appropriate issue or related artifact already exists.

2. Submit the proposed subject as a question to the `ghi-info` system by running `scripts/ghi-info-ask.py`; include `--include-closed` when the question concerns prior examples or whether something is absent. Then read both the issues returned by the script and the paired documents referenced by those issues.

3. If an existing artifact already addresses the subject, update that artifact instead of creating another one. The normal choice is to revise the existing issue, just as the separate `md-write` process normally chooses its `REVISE` disposition.

4. Failure of the `ghi-info` inquiry must not prevent the write. If it fails, search the local issue mirror with `grep`, then search through `gh`, and continue applying the rest of these rules.

5. Choose the artifact’s destination according to the state represented by the material.

6. Every artifact must be in one of two conditions: either it is final and located at its proper permanent destination, or it is provisional material placed in an explicitly named queue that has a defined process for moving queued material onward.

7. If nobody has yet decided what should ultimately happen to the material, place it in the queue associated with its expected destination. Use `docs/wiki/queue/` for doctrine expected to become wiki content, `docs/issues/queue/` for Markdown documents expected to be paired with issues, and the `draft` label for issues that are still queued. Do not create a GitHub issue merely for the queued material in the first two cases.

8. Material that represents something unresolved or still requiring action must have a GitHub issue. Examples include a desired feature or component, an unanswered question, and a promise to do something. Use only an issue when its body can remain below 500 words; use both a Markdown document and a paired GitHub issue when substantial working detail must accompany it.

9. Put the overview in the issue body and the detailed substance in the paired Markdown document. Create the Markdown document first, make it part of the repository’s landed content—the precise landing mechanism is not specified here—and only then link to it from the issue.

10. Reference material that is complete and has no unresolved question, promised work, or other pending state should exist as an unpaired Markdown document in its permanent location.

11. The deciding distinction is that a GitHub issue records unresolved state, a Markdown document contains substantive material, and a queue stores material whose final disposition has not been decided.

12. If the correct routing remains genuinely uncertain, create an issue with the `draft` label and continue. Routing uncertainty must not stop the write.

13. Revise an existing issue by changing its body rather than recording the revision elsewhere.

14. If the change clarifies the issue, corrects it, alters its scope, or repairs a reference already present there, make that change directly in the issue body.

15. Add a comment only when recording a genuinely new event. The two permitted kinds of event are the outcome of a particular instance or occurrence, and a challenge to an earlier ruling or decision.

16. Do not record completion as a comment. Instead, edit the body to record the result and then close the issue while specifying why it is being closed.

17. Never create a second issue when editing the first issue would adequately handle the new material.

18. This body-editing rule supersedes the usual tendency to accumulate comments or create additional records, because the issue’s edit history already preserves the earlier and later versions.

19. Write the issue so that it can be understood by someone who has no knowledge of the conversation or circumstances that produced it.

20. Before submitting, verify three things: the issue alone clearly identifies its subject; it explains why the subject matters or why the issue exists; and it gives a next action that an uninvolved reader can actually carry out.

21. Ensure that every reference can be opened by the intended reader and that every factual claim has been verified.

22. A file reference must work from the reader’s environment, not merely from the writer’s. Use complete URLs for material outside this repository, and cite an in-repository path only after confirming that the path exists on the `main` branch.

23. Perform inexpensive checks before filing. If a claim can be resolved with one `grep` search or one `gh` command, run that check immediately so the issue states the current fact rather than an unverified possibility.

24. Any assertion that something does not exist must include evidence of the search: record both the query that was used and the scope within which it returned no results.

## How to do it

1. To perform the initial inquiry, run `scripts/ghi-info-ask.py "<question>"`, replacing `<question>` with the actual question. Add `--include-closed` when investigating precedent or claiming that something is absent.

2. If that inquiry fails, use the fallback methods in this exact order: search `ghi-mirror/` in the current checkout while recognizing that it is stale unless recently regenerated; search all issue states in `nedschorus/nedschorus` with `gh issue list --repo nedschorus/nedschorus --state all --search "<terms>"`; and search the repository for paired documents concerning the subject.

3. To create an issue, run `gh issue create --repo nedschorus/nedschorus --title "<title>" --body-file <file>`, substituting the actual title and the file containing the issue body.

4. To replace an issue’s body, run `gh issue edit <number> --repo nedschorus/nedschorus --body-file <file>`, substituting the issue number and body-file path.

5. To close an issue, first edit its body to record the outcome, then run `gh issue close <number> --repo nedschorus/nedschorus --reason "completed"` when the work was completed, or use `"not planned"` when that is the applicable closing reason.

6. For either of the two permitted comment-event categories, submit the comment through the comment operation provided by `scripts/ghi-issue-write.py` and identify which event category it represents. Do not use `gh issue comment` directly, because the project’s issue-writing controls reject that route.

7. Draft issue bodies in files and supply them through `--body-file`.

8. Do not pass content containing backticks through an inline `--body` argument, because the shell alters such content without reporting the alteration.

9. To queue material, either create the queue file inside the directory corresponding to its intended destination or add the `draft` label to the queued issue. The process that drains or advances queued material is defined in [nedschorus issue 24](https://github.com/nedschorus/nedschorus/issues/24).
