<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=defect-hunt tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/cross-project/repo-boundary-and-runtime-layers.md -->

1. “Ruled by the user 2026-08-14, in the walk that also hardened the box's backups.” The walk, its subject, and its durable record are unidentified; “box's backups” is also unexplained. A future agent cannot determine which ruling this invokes. “shared drawer” is likewise a metaphor rather than a searchable concept. Confidence: sure.

2. “It answers one question — *which repository, and which machine* — and it answers it for three runtimes rather than one.” The later rules do not identify the machine or checkout for each tool, especially machine-specific launchers and supervisors; Layer 2 only says “a checkout on `PATH`,” while the split is explicitly undecided. Confidence: sure.

3. “Moving files between directories is cheap and reversible, and a wrong directory costs a `git mv`.” Line 96 itself shows that the move also requires updating 14 path references, handling instruction-class approval, and waiting for another branch. A wrong directory therefore has costs beyond `git mv`. Confidence: sure.

4. “A single repository holding both kinds of thing works fine for one person on two machines.” Separate machine-local clones and runtime installations can become stale or diverge even for one person; the fleet reference records that this already caused stale hooks. Confidence: unsure — the sentence may intend to exclude runtime-delivery problems, but that scope is not stated.

5. “There are three, and they differ in what they can reach.” This asserts an exact universal count without limiting it to the currently supported deployment. A fourth Claude session in a container, CI runner, or another host is an ordinary counterexample. Confidence: unsure — “here” may be intended as an unstated scope limitation.

6. “A cloud session can reach exactly what is inside the git repository it cloned, and nothing else.” Literally, a cloud session can also reach its process environment, temporary files, installed tools, and files it creates outside or alongside the checkout. The sentence also conflicts with the later description of teleporting the session to a local CLI. Confidence: sure.

7. “Two further facts about cloud sessions, read from the Claude Code 2.1.232 binary ... with the detail recorded in `docs/issues/queue/45-session-seat-and-isolation-riders.md`.” The cited file records Claude Code 2.1.231 and contains no discussion of `--teleport` or cloud sync budgets. The claimed evidence and version therefore cannot be checked from the supplied context. Confidence: sure.

8. “Cloud sessions sync files under hard budgets and stop rather than degrade quietly when a repository has more files than per-turn sync can track.” “Sync,” “hard budgets,” “per-turn,” the tracked unit, the threshold, and the observable stop behavior are undefined. The cited file does not supply them, so an agent cannot use this as an operational limit. Confidence: sure.

9. “Every component belongs to exactly one of these.” “Component” has no definition, and the manifest mixes individual files, directories, grouped runners, and design documents. Some files also serve both as repository source and installed runtime material, so the stated exclusivity is not executable as written. Confidence: sure.

10. “### Layer 1 — Runtime: must be present in every session.” Cloud sessions have no `~/.claude`, while the table says these entries are reachable only when present in the cloned repository. The document never explains how a machine-installed Layer 1 artifact is present in cloud sessions. Confidence: sure.

11. “Claude Code reads these from `~/.claude/` and from the working directory's `.claude/` at session start. Nothing an agent does later can load them.” The status-line implementation is `scripts/session-statusline-command.py`, merely wired by `.claude/settings.json`; skill content is used on demand, not described as fully loaded at startup. The sentence conflates startup configuration discovery with later loading and is literally too broad. Confidence: sure.

12. “These want to be installed to `~/.claude/` on each machine, not vendored into every project.” This cannot satisfy the document’s own cloud constraint, since cloud sessions cannot see machine-local `~/.claude`. It also conflicts with the project-specific `ghi-write` skill, whose frontmatter says “in this project” and whose commands hard-code `nedschorus/nedschorus`; that file cannot be treated as an unchanged global installation. Confidence: sure.

13. “Any install step here carries the same obligation: a version stamp and a staleness check, from the first version.” No source authority, stamp location or format, comparison rule, stale-state behavior, or update trigger is defined. An agent cannot implement or verify this obligation from the document. Confidence: sure.

14. “### Layer 2 — Tools: invoked by path when needed” versus “These are run by name at the moment they are wanted ... a checkout on `PATH`.” These describe different lookup mechanisms: explicit path resolution versus bare-name `PATH` lookup. The document does not say which applies, and current wiring uses explicit repository paths. Confidence: sure.

15. “Cheapest test: **would a different project want this file unchanged?** ... it is project content.” The manifest classifies `.claude/skills/ghi-write/` as Layer 1 even though its referenced skill is explicitly project-specific and contains nedschorus-specific issue-routing commands. The test and the manifest therefore produce incompatible classifications. Confidence: sure.

16. “Every component in the repository as of 2026-08-14, classified.” Numerous tracked files are absent, including the root `CLAUDE.md`, `README.md`, `entry-manifest.md`, `.claude/settings.json`, test files, and the target document itself. The manifest cannot serve as a complete mechanical split list under this claim. Confidence: sure.

17. “`.claude/hooks/backup-and-snapshot-write-guard.py` *(pending PR #58)*” The file is not in this checkout, yet the manifest is presented as the repository’s current component inventory. “PR #58” is a bare, unopenable reference with no branch, commit, or status evidence. Confidence: sure.

18. The column “Cloud can reach it?” marks `scripts/handoff-supervisor.py`, the launchers, and the backup checker as “No” because they manage machine-local state. The files themselves are inside the cloned repository and are therefore reachable under the document’s own definition; “can reach the file” and “can successfully operate” are being conflated. Confidence: sure.

19. “`scripts/md-review-grid.py` and its two cell runners ... Yes, if the runtimes it shells out to exist there.” The two runners are not named, and “the runtimes” is undefined. A future agent cannot determine which files or runtime-presence condition this row covers. Confidence: sure.

20. “It waits for that branch to land.” Neither the branch name nor the two files being rewritten is given. The move also depends on an unexplained “walked approval” and an undefined instruction-class process, so an agent cannot know what event ends the wait or what work is complete. Confidence: sure.

21. “A layer table with no per-file classification decides nothing.” The preceding manifest explicitly lists Layer 3 entries by directory rather than by file. The document therefore says per-file classification is necessary while declining to provide it. Confidence: sure.

22. “A split needs an install mechanism with a version check, built first.” “Built” has no acceptance condition, test, or stopping point, and the document supplies no mechanism design beyond the undefined obligation at line 48. An agent cannot determine when the split prerequisite is satisfied. Confidence: sure.

23. “A cloud session is bound to one repository ... a `--teleport` lands in the project checkout. ... Whichever repository a cloud session clones is the one it gets.” The same-repository teleport requirement does not establish that the session cannot clone or access another repository, and “the project checkout” is ambiguous among main, agent, and task worktrees. The claim is broader than the stated evidence. Confidence: sure.

24. “Two repositories mean two review-and-merge lanes ... Splitting doubles the credential work.” Multiple repositories can share one review queue, gatekeeper service, or organization-level credential. Neither “mean” nor “doubles” follows literally from having two repositories. Confidence: sure.

25. “the boundary is drawn and every file is classified” repeats the completeness claim despite the omitted files and directory-level Layer 3 rows. The stated mechanical split cannot rely on a list that is neither file-complete nor uniformly granular. Confidence: sure.

26. “1. **Would a different project want this unchanged?** No → layer 3 ... 2. **Must it be loaded at session start to work?** Yes → layer 1.” A file can satisfy both conditions: a project-specific skill or hook can be required at session start. The ordered test gives no precedence for that case and conflicts with the Layer 1 classification of `ghi-write`. Confidence: sure.

27. “Otherwise it is layer 2 — a tool, in `scripts/`, with its design document in `docs/cross-project/`.” A new support file such as a configuration file, schema, fixture, or dependency declaration can be neither Layer 1 nor project content without being a script. The rule therefore does not classify all “new files” it claims to cover. Confidence: unsure — the opening scope may intend only scripts, skills, hooks, and lasting documents, but line 114 broadens it to any new file.

clean sections: none
