<!-- provenance: runtime=codex model=gpt-5.6-terra effort=xhigh cell=defect-hunt tier=floor target=/Users/el/Projects/nedschorus/.claude/worktrees/linters-tool-usage-f8b0a0/.claude/skills/ghi-write/SKILL.md -->

1. `description: “Creating or revising any project artifact that might belong in an issue also triggers it…”` versus `“writing project material whose home (issue, queue, or MD) is not yet decided.”`  
   These give incompatible trigger boundaries: “might belong” can mean any artifact topically related to an issue, while the body limits the trigger to material with an undecided home. An agent cannot tell whether revising a known paired MD invokes this skill. Confidence: sure.

2. `“Put the subject to ghi-info by running scripts/ghi-info-ask.py…”`  
   `ghi-info` is not defined, and the referenced helper does not exist in this checkout. The mandatory ask therefore cannot be run, and the file supplies neither its input contract nor its result format. Confidence: sure.

3. `“When an existing artifact covers the subject, edit that artifact…”`  
   “Covers the subject” has no test. An old issue about the same component but with a completed, different decision can reasonably be treated as either covering or not covering a new request; the choice changes whether the agent edits or files. Confidence: sure.

4. `“the same way md-write defaults to REVISE.”`  
   `md-write` and `REVISE` are unexplained cross-skill terms with no path to their definition. The claimed supporting policy cannot be found or applied from the permitted context. Confidence: sure.

5. `“A failed ask never blocks the write…”`  
   This absolute is false. For example, if the ask helper, local mirror, and authenticated GitHub search are unavailable, an agent cannot determine whether an existing issue must be revised while also satisfying the requirement to check claims. Filing itself is also blocked if GitHub authentication is unavailable. Confidence: sure.

6. `“Every artifact is either final at its home or in a named queue with a drain:”`  
   “Every artifact” is broader than the routing scheme can hold. A temporary local investigation note or generated diagnostic artifact may be deliberately discarded rather than final or queued. The frontmatter’s equally broad “any project artifact” makes that literal reading reachable. Confidence: sure.

7. `“Material whose disposition is not yet decided goes to its destination queue … with no GHI.”` versus `“When the routing is genuinely ambiguous, file a draft-labeled issue…”`  
   Routing ambiguity is an ordinary form of an undecided disposition, but these instructions select different destinations: a queue without a GHI versus a draft issue. The file does not distinguish the two predicates. Confidence: unsure — “disposition” may have a specialized intended meaning, but none is provided.

8. `“gets a GHI … an MD-GHI pair…”` and `“the GHI carries state, the MD carries substance…”`  
   `GHI`, `MD`, and the pair relationship are never defined. `GHI` is not a standard SDLC term and is difficult to interpret reliably from the acronym alone; these are the concepts that control whether an issue and/or companion file must be created. Confidence: sure.

9. `“issue-only when the body stays under 500 words, an MD-GHI pair when substantial working material rides with it.”`  
   The conditions are neither mutually exclusive nor exhaustive. A 500-word issue with no substantial working material matches neither branch; a 300-word issue with a substantial appendix matches both. The routing mechanism gives no precedence or boundary. Confidence: sure.

10. `“write the MD, land it, then cite it from the issue”` versus `“in-repo paths verified present on main before citing.”`  
    “Land it” is undefined here and does not say that the MD is merged to `main`. If it means commit or publish on a branch, the prescribed citation violates the later main-presence rule. Confidence: unsure — “land” may be intended to mean merge to main, but the file does not establish that.

11. `“ambiguity never blocks the write.”`  
    This absolute has ordinary counterexamples. If ambiguity is whether material can safely be published in a GitHub issue at all—for example, a potential security disclosure—creating a draft issue can itself be the harmful action. Confidence: sure.

12. `“A second issue is never filed where an edit to the first serves.”`  
    This forbids a normal separate-lifecycle case: a recurring incident can be related enough that editing the old issue preserves context, yet still require a new owner, milestone, closure reason, and audit trail. “Serves” has no criterion that resolves this. Confidence: sure.

13. `“Make every reference openable and every claim checked:”`  
    “Every claim checked” is too broad for the skill’s own pending-state issues. A commitment to act or an open question can truthfully state current intent or uncertainty, but cannot be checked as a present fact by grep or GitHub search. Confidence: sure.

14. `“Run the cheap verifications before filing…”`  
    The skill also governs edits and comments, but this is the only stated timing for the required claim checks. A permitted new-event comment can therefore be read as either requiring pre-submission verification or not requiring it at all. Confidence: sure.

15. `“grep ghi-mirror/ in the checkout (stale unless freshly regenerated)”`  
    `ghi-mirror/` does not exist in this checkout. The fallback also supplies neither a grep query nor a regeneration procedure, despite warning that its results may be stale. When the mandatory ask fails, the first fallback is therefore not executable or interpretable. Confidence: sure.

16. `gh issue list --repo nedschorus/nedschorus --state all --search "<terms>"`  
    This search has no result limit. The installed `gh` help states that `issue list` defaults to 30 results, so a subject matching more than 30 issues can omit the existing artifact the skill requires the agent to find and read. Confidence: sure.

17. `“resubmit through the write tool scripts/ghi-issue-write.py’s comment verb naming the event kind”`  
    The referenced write tool is absent from this checkout. Independently, the file gives semantic examples of the two events but no literal event-kind values or command syntax, so an agent cannot execute the only permitted comment path. Confidence: sure.

18. `“plain gh issue comment is denied by the write path.”`  
    A direct `gh issue comment` invocation does not pass through the named Python tool. No wrapper, hook, permission rule, or other enforcement mechanism is defined that could deny it, so this claim is impossible as written. Confidence: sure.

19. `“an inline --body with backticks is silently mangled by the shell.”`  
    This is an overbroad literal claim. For example, a POSIX shell preserves backticks in a single-quoted argument such as `--body 'Use \`name\`.'`; unquoted backticks are a different case and are not necessarily silent. Confidence: sure.

clean sections: none
