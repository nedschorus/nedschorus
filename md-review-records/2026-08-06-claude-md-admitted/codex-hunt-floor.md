<!-- provenance: runtime=codex model=gpt-5.6-terra effort=xhigh cell=defect-hunt tier=floor target=/Users/el/Projects/nedschorus/docs/drafts/claude-md-admitted.md -->

1. “This repository is `~/Projects/nedschorus`” fixes the repository’s identity to one user-home path. A second clone, CI checkout, or linked worktree makes the statement literally false and may direct work to a different checkout. Confidence: sure.

2. “(NC)” introduces a two-letter name that is not search-distinct or self-explanatory outside this sentence. “NC” is likely to collide with ordinary prose and unrelated identifiers, so later references cannot be reliably located or attributed. Confidence: sure.

3. “read anything there freely” is an unjustifiably absolute permission. Ordinary counterexamples include unreadable files, secrets requiring handling restrictions, huge files with material cost, and special files whose reads block or have effects. It also gives no boundary for what “freely” permits. Confidence: sure.

4. “NOT: write, commit, or run anything there” supports incompatible readings with the preceding permission: `cat`, `rg`, and `git show` are executable programs commonly run with the legacy checkout as their working directory, yet are how an agent reads it. One reading bans those methods; the other bans only executing legacy code or tests. The document does not choose. Confidence: sure.

5. “Use standard SDLC terms.” is not executable from the supplied context because it identifies no vocabulary or authority. Common terms such as “release,” “rollback,” and “baseline” have incompatible meanings across projects, so an agent cannot determine which wording complies. Confidence: sure.

6. “Write durable artifacts for a reader with zero context: the subject identifiable, the why stated, actionable without the conversation that produced it.” does not define “durable,” “zero context,” or the point at which an artifact is sufficiently actionable. Taken literally, it is impossible for artifacts whose use depends on live state, credentials, approval, or an external system; naming a subject and reason does not make those prerequisites available. It therefore lacks an executable completion condition. Confidence: sure.

7. “Use them cautiously.” supplies no criterion for deciding when an absolute imperative is cautious enough to use. A future agent cannot distinguish a permitted absolute from a prohibited one using this file alone. Confidence: unsure — “cautiously” may be intended as discretionary editorial judgment rather than a procedure.

8. “use explicit, clear and precise multi-part names” leaves both its scope and test undefined. “Etc.” makes it unclear which kinds of names are covered; “part” could mean words, path segments, or identifier components; and “explicit,” “clear,” and “precise” provide no decision rule. This also leaves unclear whether the newly introduced `NC` shorthand is governed by the same instruction. Confidence: sure.

9. “Check newly invented names with glob (for path names) or grep (for names in files).” does not specify an executable checking procedure. “glob” is not identified as a command or syntax, and neither the search scope nor the pattern and match rules are stated. A textual hit in a comment, fixture, generated file, or unrelated string is not necessarily a naming collision; names outside files are also reachable under the earlier “etc.” scope with no stated treatment. Confidence: sure.

10. “If these checks return collisions or ambiguity, choose a more explicit name, with 3 or 4 parts, not 1 or 2.” leaves the collision path unfinished. It does not say how to classify “ambiguity,” whether the replacement is rechecked, or what happens when a three- or four-part replacement still collides, when a required external name has two parts, or when disambiguation requires more than four. The earlier “multi-part” wording also permits a plausible reading in which two parts suffice, while this sentence rejects two parts on the failure path. Confidence: sure.

11. “If the thing you are naming already has a name in the project, use the existing name instead of inventing a new one.” leaves “thing,” “has a name,” and “in the project” undefined. A renamed API with a compatibility alias, a concept represented differently in code and documentation, or multiple existing labels all satisfy the premise but yield different names; the instruction gives no way to select one. It also does not state what governs when the existing name is ambiguous under the preceding collision check. Confidence: sure.

clean sections: none
