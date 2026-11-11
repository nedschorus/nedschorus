---
issue: "[Fix the defects a full cold read found in the ghi-write skill, `.claude/skills/ghi-write/SKILL.md`](https://github.com/nedschorus/nedschorus/issues/3127)"
---

# Fix the defects a full cold read found in the ghi-write skill, `.claude/skills/ghi-write/SKILL.md`

## What is wrong

On 2026-11-11 the ghi-write skill, `.claude/skills/ghi-write/SKILL.md`, had a cold-read-full-run, because pull request [3120](https://github.com/nedschorus/nedschorus/pull/3120) adds one sentence to its step 4. Its seven reviewers, and an eighth that answered which steps should be code, also found defects in text that pull request does not change. Those defects are listed below, so that someone can fix them in a later pull request. Each defect quotes the skill as it stood at commit `f9c696542`, and names the reviewer reports that raised it. The reports, and the triage that sorted them, are in the cold-read-record `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/SKILL-ghi-write-2026-11-11-2`. A report is named by its file there: `claude-hunt-deep.md` is "claude-deep", `claude-hunt-second-strongest-model.md` is "claude-second", `codex-hunt-deep.md` is "codex-deep", `codex-hunt-second-strongest-model.md` is "codex-second", `agy-hunt-gemini-4-argon-high.md` is "agy", the two `-terminology-deep.md` files are "claude-term" and "codex-term", and `question-4-what-should-be-code-answer.md` is "Q4". A number after a report's name is the number of the finding in it.

Why it matters: the skill runs every time an agent files, edits or closes a GitHub issue in this project. Where its text contradicts itself, or describes `scripts/ghi-issue-write.py` wrongly, two agents following it will route the same material in different ways, or will wait for a step the program never takes.

Already covered elsewhere, and so not listed here: the skill's account of one GHI-MD against its supporting documents ("its one GHI-MD", "wherever they live", "beside the GHI-MD") is the subject of GHI [An issue has one GHI-MD and many supporting documents, and the GHI write tool cannot tell them apart](https://github.com/nedschorus/nedschorus/issues/783).

## The defects

### Step 1, asking before filing

1. The skill lists promoting queue material into an issue as one of its uses, in its front matter and under When Used, but no step says how to do it: whether the queue file goes to create-GHI where it lies, and what happens to the queue copy. Reports: claude-deep 1, claude-second 1. GHI [Queue drain procedure](https://github.com/nedschorus/nedschorus/issues/24) is the design to point to rather than writing a new procedure; GHI [345](https://github.com/nedschorus/nedschorus/issues/345), closed as not planned, raised a nearby gap.
2. "Ask before filing" does not say whether an agent about to edit, record an outcome on, or close a known issue must also ask ghi-guide-agent. Reports: claude-deep 2, agy 2.
3. "read the issues it returns and the documents they cite" sets no limit on how far the reading goes. Reports: claude-deep 3, agy 3, codex-deep 1.
4. "When an existing issue or GHI-MD covers the subject … edit its GHI-MD" does not say whether a closed issue counts, whether the step-1 ask takes `--include-closed`, or what to do when the covering issue has no GHI-MD, as an issue filed before the migration to GHI-MDs may not. Reports: claude-deep 4, agy 4, codex-deep 2, codex-second 1, claude-second 2.
5. "A failed ask does not block the write: fall down the ladder" conflicts, for an agent on the Mac whose ask failed because ned-box was down, with the root `CLAUDE.md` rule to leave a step that needs ned-box until ned-box is fixed. Reports: claude-deep 6, agy 5, codex-second 2.
6. "the project's issue-knowledge agent" is a second name for ghi-guide-agent, which the glossary already defines. Reports: claude-deep 5, codex-term 4, claude-term 1.

### Step 2, routing

7. The lead sentence lists four destinations — canonical location, queue, task list, commit or pull request — and leaves out a GHI, which the second bullet then gives as a destination. Reports: claude-deep 7, claude-second 3.
8. The step says undecided material "goes to a queue, not to an issue", then that "a candidate issue queues as a `queue-drain-candidate`-labeled issue", and its last bullet sends material whose routing is "genuinely ambiguous" to a labeled issue. A reader cannot tell when undecided material goes in a queue directory and when it becomes a labeled issue. The queues are named for destinations, so material in one has its destination decided, and "The queue", singular, does not say which queue. "and move on" also hides the filing work that follows: the pull request, the merge and the rerun. Reports: claude-deep 8 and 9, agy 6 and 10, codex-deep 3, claude-second 4 and 10, claude-term 7 and 12.
9. Bullet 2 ("too big to explain in one commit message or pull request description") and bullet 3 ("Work that one commit message or pull request description explains") disagree about work that a pull request description can explain but one commit message cannot. Report: claude-deep 10.
10. "records its outcome with the edit that closes it" is literally wrong: no edit closes an issue; step 3 and the Close bullet close it with `gh issue close` after the edit merges. Reports: claude-deep 11, claude-second 9, claude-term 8.
11. "Every GHI is a link-only-GHI: its text is its one GHI-MD, and its body is the links …" defines link-only-GHI again, where the glossary already does, and does not hold for an issue between create-GHI's first run and its rerun, whose body is a placeholder. Reports: codex-deep 4, codex-second 3, codex-term 6, claude-term 9.
12. "a bare MD at its canonical location" uses "bare MD", which no glossary defines, and does not say what makes a wiki page "finished" rather than wiki-bound doctrine for `docs/nedschorus-wiki/queue/`. Reports: claude-deep 13, agy 9, claude-term 6.
13. The `TaskCreate` tool that step 2 names for the task list is not available to a Codex agent, and the skill names no equivalent. Reports: codex-deep 6, codex-second 4.

### Step 3, revising

14. Step 3 makes "a challenge to a ruling it records" an edit to the GHI-MD, while step 2 sends "a question waiting on the user" to the task list, and step 4 files "without asking the user". Nothing says how a challenge is written so the user-ruling stays on record as his. Report: claude-deep 14. "ruling" is also written where the glossary's term is user-ruling, here and in step 4. Reports: codex-term 8, claude-term 13.
15. "No agent writes an issue comment" has no qualifier, though the hook lets comments on other repositories through. Report: claude-deep 15.

### Step 4, writing

16. "The first heading becomes the issue's title" is true for create-GHI; for edit-GHI the How to do it bullet gives an exception, and that exception ("unless other files are named with the issue's number") does not match the program, which also counts a landed design that has no number in its name (`title_follows_heading_in_this_edit` and `ghi_md_paths_for_issue` in `scripts/ghi-issue-write.py`). Reports: claude-deep 18, agy 19, codex-deep 7 and 14.
17. "without abbreviations" does not say whether a project-term that is an abbreviation, such as GHI, counts. The title of GHI [46](https://github.com/nedschorus/nedschorus/issues/46) uses "GHI". Reports: claude-deep 19, agy 13, claude-second 12.
18. The third of the three tests, "the next action is one a reader who was not in this conversation can take", cannot be met by an outcome edit or by a GHI-MD closing as not planned, which have no next action. Its wording, "a reader who was not in this conversation", is also a second, weaker name for fresh-reader. Reports: claude-deep 20, agy 12, claude-second 13, claude-term 15.
19. "Give the GHI-MD its /cold-read before running create-GHI or edit-GHI on it" also covers, read literally, the rerun after the merge. It does not say that the cold read's findings must be applied before filing. Reports: claude-deep 21, claude-second 14, agy 14, codex-second 5.
20. "file it with create-GHI or edit-GHI without asking the user" does not mention that a GHI-MD whose name ends `-design.md` is a file the instruction-file guard protects, so a change to it is refused until `.walk-approved` holds an approval. Reports: claude-deep 22, claude-second 15.
21. "Give him the GHI-MD's `file:///Volumes/nedhome/...` link" does not say what an agent on the Mac links, since its checkout is not under ned-box's home, nor which copy to link when the file it wrote is deleted after filing. Reports: claude-deep 23, claude-second 16.

### Step 5, references and claims

22. "full URLs for anything outside this repository" conflicts with the root `CLAUDE.md` form for a log-store file, `nedlern@ned-box:/home/nedlern/nedschorus-logs/<path>`, which is not a URL. Reports: claude-deep 25, agy 16, claude-second 17.
23. "in-repo paths verified present on main before citing" rules out a design naming the files it will create. "the reader's seat" can be read as agent-seat or as a machine. Reports: claude-deep 26, codex-deep 10, claude-second 18, codex-term 9, claude-term 17 and 18.
24. "a claim you have not checked … ends with "(unverified)"" cannot sensibly apply to a design's statements of what will be built. Report: claude-deep 24.

### How to do it

25. The fallback ladder does not say whether to stop at the first rung that answers; `ghi-mirror/` is normally absent from an agent's own checkout; "freshly regenerated" names no command; and `--limit 100` can cut a broad search short without saying so. Reports: claude-deep 27, agy 17, codex-deep 11, codex-second 7 and 8, claude-second 19.
26. The skill's "File:" bullet does not say where to write the GHI-MD. `scripts/ghi-issue-write.py` refuses a file that is not inside a git checkout. Reports: claude-deep 28, claude-second 20, codex-second 9.
27. "Every refusal says what to do next" is not true of every refusal: `scripts/ghi-issue-write.py` refuses with only "no such file: <path>" or "<path> is empty". "refuses if one does" does not always hold: the program's docstring says its check against open issues fails open. Reports: claude-deep 29, codex-deep 12.
28. "When filing finishes, delete the file you wrote" can be read as after the first run or after the rerun; deleting after a first run that failed before its pull request opened removes the only copy. Reports: claude-deep 30, agy 18, codex-deep 13, claude-second 21.
29. "Both operations open a pull request for the file and stop there" is wrong for edit-GHI, which changes the issue's title before the pull request merges: `edit` calls `sync_title_on_heading_change` after `land_edit` in `scripts/ghi-issue-write.py`. Reports: agy 20, codex-deep 15.
30. "rerun as the run's last line says": when there is an open question about a user-ruling, the run's last lines are the instruction to dispatch a subagent for it, printed by `report_open_ruling_questions` after the rerun line, not the rerun line. Reports: claude-deep 31, codex-deep 17, claude-second 23.
31. Nothing says what to do when the pull request that create-GHI or edit-GHI opened does not merge. Reports: claude-deep 32, codex-deep 16, claude-second 22.
32. "pull main" does not say which checkout, and on edit-GHI the author's checkout may still hold the edit uncommitted. Report: claude-deep 33.
33. "that run finishes the issue" reads as closing the issue; it means the rerun finishes the filing or the edit. Reports: claude-deep 34, codex-term 11, claude-term 19.
34. Close with `--reason "duplicate"` names no issue it duplicates; the hook already allows `--duplicate-of`. Reports: claude-deep 35, claude-second 24.
35. The skill's "Queue routing:" bullet: "its destination directory" can be read as the queue or as the final destination, and nothing says the queue file must reach main through a pull request. "add the `queue-drain-candidate` label to the issue" names no issue. Reports: claude-deep 36, agy 22, codex-second 13, claude-second 25, claude-term 22.
36. The hook bullet's list of refused commands differs from what `.claude/guard-hooks/ghi-issue-write-hand-typed-gh-command-refusal.py` refuses. Reports: agy 21, codex-deep 19, codex-second 12.
37. The routing doctrine the skill cites, `docs/nedschorus-wiki/nedschorus-ai-native-software-development-objective.md` § Project organization, contradicts the skill on comments, on what queues hold, and on which queue directories exist, and the skill does not say which wins. Reports: claude-deep 37, claude-second 26.
38. The skill calls the same program "the ghi-write-tool", "the tool" and "the write tool". Reports: codex-term 12 and 13, claude-term 20.

### Steps that could be code

39. Report Q4 lists eleven steps that a program could do in place of the agent: run the rerun after the merge, check that a /cold-read happened, check cited paths against main, refuse a close while the body is still a placeholder, delete the source file after filing, run the fallback ladder inside the ask program, a `--queue-drain-candidate` flag on create, flag abbreviations in a title, check the `kind: design` front-matter line, merge a draft with `git merge-file`, and print the Mac link. Each needs judging against the root `CLAUDE.md` rule on code-prompt-code. Two more come from the cold read of this GHI-MD: the hook could refuse `gh issue close --reason duplicate` without `--duplicate-of` (item 34), and `scripts/ghi-guide-agent-ask.py`, which knows why an ask failed, could print whether to fall back or to wait for ned-box (item 5). Where the skill restates what a program does (items 16, 27, 29, 30 and 36), the fix may be to point to what the program prints rather than to restate it again.

## What comes next

Whoever takes this issue first judges item 39, because a step that becomes code may replace the prose fix for the item it covers. Then they fix the skill's text, `.claude/skills/ghi-write/SKILL.md`, for the remaining items among 1 to 38 in one pull request, or in several where the items do not share a topic, and gives that change the cold-read-full-run that step 2 of the cold-read skill, `.claude/skills/cold-read/SKILL.md`, requires for a skill. What goes to the user from that run is what that skill's step 9 sends him. Item 39 is judged item by item; each step that should become code gets its own GHI or task.
