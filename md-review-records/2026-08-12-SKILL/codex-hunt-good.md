<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=defect-hunt tier=good target=/Users/el/Projects/nedschorus/.claude/worktrees/linters-tool-usage-f8b0a0/.claude/skills/ghi-write/SKILL.md -->

1. “`name: ghi-write`” — “GHI” is never expanded and is not a standard SDLC term. The two-part opaque name also conflicts with CLAUDE.md’s instruction to use “explicit, clear and precise multi-part names” and, when ambiguous, “3 or 4 parts, not 1 or 2.” A zero-context agent cannot identify the skill’s subject from its name alone. Confidence: sure.

2. “Creating or revising any project artifact that might belong in an issue also triggers it” conflicts with “writing project material whose home (issue, queue, or MD) is not yet decided.” The former can include an artifact with a known home merely because it could conceivably belong in an issue; the latter requires its home to be undecided. This leaves incompatible trigger scopes. Confidence: sure.

3. “Put the subject to ghi-info by running `scripts/ghi-info-ask.py` with the question” — `ghi-info` is undefined, and the specified script does not exist in this checkout. The first required filing step therefore cannot be executed literally. Confidence: sure.

4. “read the issues it returns and the pair documents they cite” — “pair documents” has not been defined, nor does the file state how to recognize one among an issue’s references. This prevents an agent from knowing which cited documents must be read. Confidence: sure.

5. “When an existing artifact covers the subject, edit that artifact — a revision of the existing issue is the default disposition” supports incompatible actions. The existing artifact may be an MD or queue file, in which case “edit that artifact” and “revision of the existing issue” identify different targets. “Covers the subject” also has no stated sufficiency test. Confidence: sure.

6. “the same way md-write defaults to REVISE” — neither `md-write` nor the capitalized disposition `REVISE` is defined or present in the checkout. The comparison therefore supplies no usable context and introduces names that are difficult to resolve by search. Confidence: sure.

7. “A failed ask never blocks the write: fall back to grepping the local mirror, then `gh` search, and proceed under these rules.” The mechanism has no terminal rule when the mirror is missing or stale and `gh` is unavailable, unauthenticated, or also fails. That reachable case conflicts with the later requirements that every claim be checked and every absence claim have a search receipt. The local mirror is in fact absent here. Confidence: sure.

8. “Every artifact is either final at its home or in a named queue with a drain” is both too broad and inconsistent with the later active-GHI route. An ordinary open issue carrying pending state is neither final nor necessarily in the `draft` queue. Ordinary project artifacts such as source files and build outputs also do not fit this binary classification. Confidence: sure.

9. “Material whose disposition is not yet decided goes to its destination queue” is circular under one ordinary reading of “disposition”: selecting the destination is itself the undecided disposition. A raw note whose wiki/issue/MD destination is unknown cannot be assigned to any of the three listed destination queues. Confidence: unsure because “disposition” might be intended to mean something narrower, but no narrower definition is supplied.

10. “the `draft` label for queued issues — with no GHI” conflicts with “When the routing is genuinely ambiguous, file a `draft`-labeled issue.” Under the only contextually apparent expansion of GHI, a draft-labeled GitHub issue is itself a GHI. If GHI means something else, that meaning is absent, leaving the rule equally un-executable. Confidence: sure.

11. “Anything carrying pending state … gets a GHI” is broader than the listed routing purpose can reliably support. An ordinary temporary checklist in an in-progress PR or a local implementation note carries a commitment to act but does not necessarily warrant a separate issue. No boundary excludes already-tracked or transient state. Confidence: unsure because this may be an intentionally exhaustive project policy, but its literal scope includes those ordinary cases.

12. “issue-only when the body stays under 500 words, an MD-GHI pair when substantial working material rides with it” neither partitions nor exhausts the cases. A substantial 400-word body satisfies both routes; a non-substantial body of exactly 500 words satisfies neither stated route; and “substantial” has no test. The routing decision is therefore indeterminate. Confidence: sure.

13. “the pair sequence is write the MD, land it, then cite it from the issue” — “land it” has no executable meaning or stopping test. It could mean commit locally, push a branch, merge to `main`, or merely place the file at its intended path; those states permit different kinds of citation. Confidence: sure.

14. “Final reference content awaiting nothing is a bare MD at its home.” “Bare MD” and “home” are undefined, and the categorical rule excludes ordinary final reference artifacts such as schemas, images, source files, or generated data. The file supplies no home-selection mechanism for final content. Confidence: sure.

15. “The discriminator: the GHI carries state, the MD carries substance, the queue holds the not-yet-decided.” These properties do not discriminate among the routes defined above: the queues expressly contain MDs and doctrine, so they contain substance; issue bodies carry summaries and outcomes, which are also substance; and a queued MD has both “MD” and “queue” properties. Confidence: sure.

16. “A comment is only for a genuinely new event — an instance outcome, or a challenge to a ruling.” This leaves ordinary new events such as newly obtained diagnostic evidence, an upstream dependency change, or a vendor response with no route: they are neither the listed body-edit cases nor either comment event. “Instance outcome” and “ruling” are also undefined project-specific categories. Confidence: sure.

17. “A comment is only for … an instance outcome” conflicts with “Completion is not a comment: record the outcome in the body.” Completion is ordinarily an outcome, so one sentence permits it as a comment while the next forbids it. Nothing defines “instance outcome” narrowly enough to resolve the conflict. Confidence: sure.

18. “A second issue is never filed where an edit to the first serves.” “Serves” has no test, and the absolute can suppress independently assignable work. For example, an umbrella issue can be edited to mention a newly discovered defect, but that does not necessarily provide the separate owner, milestone, or closure state needed to track the defect. Confidence: unsure because the author may intend those tracking needs to mean that an edit does not “serve,” but the text does not say so.

19. “Write for a zero-context reader. Before submitting, check the three tests: the subject is identifiable from the issue alone; the why is stated; the next action is executable by a reader who was not in this conversation.” This duplicates CLAUDE.md’s definition: “Write durable artifacts … for a reader with zero context: the subject identifiable, the why stated, usable without the conversation that produced it.” The duplicate substitutes “next action is executable” for the broader “usable,” so an agent cannot tell whether the three local tests are exhaustive or merely a specialization of the checkout rule. Confidence: sure.

20. “Make every reference openable and every claim checked” is an overbroad absolute. Normative, predictive, and subjective claims—such as “this workflow is confusing” or “this design should reduce retries”—cannot all be checked as existing facts. The instruction provides no category or stopping condition for such claims. Confidence: sure.

21. “full URLs for anything outside this repository” is impossible for ordinary external files that have no URL, such as a local diagnostic log or file in another checkout. It also assumes every reader has access to every URL, despite defining openability from “the reader’s seat” without identifying that reader or their permissions. Confidence: sure.

22. “in-repo paths verified present on main before citing” excludes the ordinary case of an issue discussing a file newly added on a branch or proposing a path that does not yet exist. Such a reference cannot pass the literal check even when that absence is the subject of the issue. Confidence: sure.

23. “a check one grep or one `gh` call answers is run now” is missing the connective needed to identify the subject of “answers.” It can be parsed as “a check that one call answers” or as a malformed sequence of separate checks, leaving the verification boundary unclear. Confidence: sure.

24. “Run the cheap verifications before filing” conflicts in scope with a skill that also governs edits and comments and with the enclosing demand that “every claim” be checked. Elsewhere, “filing” specifically means creating a new issue, so the sentence does not say when equivalent verification occurs for edits and comments. Confidence: sure.

25. “grep `ghi-mirror/` in the checkout” cannot be obeyed literally because `ghi-mirror/` does not exist in this checkout. This makes the first prescribed fallback fail before it can produce evidence. Confidence: sure.

26. “`ghi-mirror/` in the checkout (stale unless freshly regenerated)” defines freshness as significant but gives no regeneration procedure, timestamp, provenance marker, or test for determining whether regeneration was fresh enough. An agent cannot know whether a successful grep is current evidence. Confidence: sure.

27. “Close: … `--reason "completed"` (or `"not planned"`).” The close mechanism omits the reachable duplicate outcome, even though the same workflow searches for existing artifacts and the installed command accepts `duplicate` as a distinct close reason. An already-filed duplicate fits neither stated reason accurately. Confidence: sure.

28. “resubmit through the write tool `scripts/ghi-issue-write.py`’s comment verb naming the event kind” is un-executable: the script does not exist, no command syntax is given, and the accepted event-kind values are not named. The phrase “two catalog events” does not establish machine-usable names. Confidence: sure.

29. “plain `gh issue comment` is denied by the write path” — “write path” is undefined, and the checkout contains no referenced tool through which this denial could be observed. A future agent cannot tell whether this means a hook, wrapper, policy, or GitHub permission failure. Confidence: sure.

30. “an inline `--body` with backticks is silently mangled by the shell” is false as a categorical claim. Backticks inside a correctly single-quoted shell argument remain literal; in other quoting contexts, command substitution can also emit visible errors rather than silently mangling the text. Confidence: sure.

clean sections: none
