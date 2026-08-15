<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=restate tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/cross-project/repo-boundary-and-runtime-layers.md -->

# Repository boundary and runtime layers

1. This document explains which repository or location should contain a newly created file and the reasons for choosing that location.
2. The user made the decisions recorded here on August 14, 2026, during a guided process called a “walk”; that same process also strengthened the backup protections or backup system of the machine called “the box.”
3. Before creating a script, skill, hook, or document intended to persist, or suggesting that something be transferred from one repository to another, the reader should consult this document.
4. The document determines both which repository and which physical or hosted machine should contain something, and it applies that determination across three distinct execution environments.

## The problem this exists to settle

1. The `nedschorus` repository currently contains two fundamentally different categories of material.
2. One category is specific to the nedschorus project, including its issue records, wiki, agent-seat briefs, and decisions made when the project was founded.
3. The other category consists of generally reusable operational machinery—such as session-handoff supervision, agent launch scripts, a Markdown-review grid, a status-line implementation, and skills—that is not inherently specific to nedschorus.
4. Because another project, `~/nedsmessenger`, already exists on the same machine and has accumulated its own agent-session transcripts, the possibility that multiple projects need the same shared machinery is now concrete rather than theoretical.
5. Previous work had acknowledged that some boundary should separate shared machinery from project-specific material, but it had not established a definite rule for drawing that boundary.
6. The existence of `docs/cross-project/` shows that someone recognized the need for a shared or cross-project category, but the presence of the nedschorus-specific founding plan inside that directory shows that the category was not being applied consistently.
7. That incorrectly filed founding plan demonstrates that the boundary had a label but lacked an enforceable classification rule, leaving no standard against which a file’s placement could be verified.

## What is not the problem

1. The central problem is not the physical arrangement of files and directories on disk.
2. Moving a file between directories is inexpensive and reversible, so an incorrect directory choice can ordinarily be corrected with `git mv`.
3. The central problem is also not aesthetic neatness or organizational tidiness.
4. For one person working across two machines, keeping both project-specific material and shared machinery in one repository is operationally workable.
5. If that simple two-machine, one-person arrangement were the only relevant consideration, the correct choice would be to make no change.
6. The actual problem is delivering the shared machinery to every execution environment that requires it.
7. Delivery requirements make the repository boundary operationally important, and they require the answer to be based on what each runtime can access rather than on subjective organizational preference.

## The three runtimes

1. In this document, a “runtime” is an environment in which a Claude Code session actually executes.
2. There are three such environments, and they have different filesystem access.
3. “The box” means the Ubuntu machine named `ned-box` on the local network; it can access that machine’s files, including its `~/.claude`, agent-seat worktrees, and `/mnt/backup`.
4. “The Mac” means the user’s Mac; it can access the Mac’s own files, including its own `~/.claude` and Time Machine data.
5. “The cloud” means Anthropic’s infrastructure; it cannot directly access either local machine’s filesystem and instead works from a cloned Git repository.
6. The cloud runtime imposes the restrictions that determine the remaining design decisions in this document.
7. A cloud session has no usable machine-local `~/.claude` installation location, cannot read files that exist only on one of the user’s machines, and has no filesystem path through which it can access either machine.
8. For the purposes of this design, a cloud session can access only files contained in the particular Git repository it cloned.
9. The following two cloud-session facts were obtained by examining the Claude Code 2.1.232 executable rather than by making assumptions; the supporting details are recorded in `docs/issues/queue/45-session-seat-and-isolation-riders.md`.
10. Running `claude --teleport` can transfer a session from the cloud to a local Claude Code CLI or from a local CLI to the cloud.
11. Teleporting requires the local working directory to be clean and requires the command to be run from a checkout of the same repository that the cloud session used.
12. Cloud sessions synchronize repository files subject to fixed limits, and when a repository exceeds the number of files that can be synchronized during a turn, the process stops instead of merely continuing more slowly or with silently reduced behavior; the document does not specify whether “stops” means that synchronization alone stops or that the broader operation or session fails.
13. Repository size therefore affects whether the cloud runtime can function at all, rather than affecting only its speed.

## The three layers

1. Every component must be assigned to exactly one of the following three layers, based on where the component must physically exist when it is used.

### Layer 1 — Runtime: must be present in every session

1. The status line, skills, hooks, and global `CLAUDE.md` are examples of components in the runtime layer.
2. Claude Code loads these components from the user-level `~/.claude/` directory and the current working directory’s `.claude/` directory when a session begins.
3. Once the session has started, later actions by an agent cannot cause these startup-loaded components to be loaded into that session.
4. These components should therefore be installed in `~/.claude/` separately on each machine instead of being copied into every project repository.
5. Installing them there is the normal mechanism supplied by the Claude Code harness, not an improvised workaround; the user already depends on this behavior because the box’s `~/.claude/CLAUDE.md` is automatically loaded into every session without requiring an agent to remember to retrieve it.
6. The design must anticipate that an installed copy could become outdated without any visible warning when its source changes.
7. The user previously addressed the same danger for the git-gatekeeper by requiring it to identify its version and upgrade automatically, because otherwise AI agents may repeatedly try to solve a problem in source code without recognizing that the corrected code has not been deployed to the place actually executing it.
8. Consequently, every installation mechanism for these runtime components must include both a version identifier and a check for whether the installed copy is stale, starting with its first version rather than adding those safeguards later.

### Layer 2 — Tools: invoked by path when needed

1. The handoff supervisor, launchers, Markdown-review grid, drift lint, git-gatekeeper, and backup health check are examples of tools in the second layer.
2. These tools are invoked by their command or path only when needed, so they must exist in a discoverable on-disk checkout—such as a checkout exposed through `PATH`—but do not need to be loaded when a session starts.
3. This layer is the strongest candidate for a separate shared repository because another project could clone that repository to obtain working copies of the tools.

### Layer 3 — Project content: belongs to one project

1. Project issues, the wiki, agent-seat briefs, drafts, project-specific design documents, and founding decisions are examples of the third layer.
2. A quick test is to ask whether a different project would want to use the file without changing it.
3. If answering that test requires qualifications such as “it depends,” the file should be treated as project-specific content rather than as reusable shared machinery.

## The manifest

1. The following table classifies every component known to be in the repository as of August 14, 2026.
2. Because the Layer 3 material contains many files that receive the same classification, the table groups those entries by directory rather than listing every individual file.
3. `scripts/session-statusline-command.py` is Layer 1 runtime material; a cloud session can access it only when it is contained in the repository that session cloned.
4. `.claude/hooks/instruction-file-guard.py` is Layer 1 runtime material; a cloud session can access it only when it is contained in the cloned repository.
5. `.claude/hooks/backup-and-snapshot-write-guard.py`, which was pending in PR #58, is Layer 1 runtime material; whether the cloud can access it does not matter to its purpose because it protects paths that exist only on a local machine.
6. `scripts/handoff-context-threshold-hook.py` is Layer 1 runtime material; a cloud session can access it only when it is contained in the cloned repository.
7. `.claude/skills/walk-me-through/` is Layer 1 runtime material; a cloud session can access it only when it is contained in the cloned repository.
8. `.claude/skills/md-review/` is Layer 1 runtime material; a cloud session can access it only when it is contained in the cloned repository.
9. `.claude/skills/handoff/` is Layer 1 runtime material; a cloud session can access it only when it is contained in the cloned repository.
10. `.claude/skills/ghi-write/` is Layer 1 runtime material; a cloud session can access it only when it is contained in the cloned repository.
11. `scripts/handoff-supervisor.py` is a Layer 2 tool; it is not usable by the cloud because it manages sessions that exist locally on a machine.
12. `scripts/handoff-write-and-check-supervisor.py` is a Layer 2 tool and is likewise unavailable or unusable in the cloud because it operates on machine-local sessions.
13. `scripts/handoff-extract-conversation.py` is a Layer 2 tool; the cloud cannot use it because the transcripts it reads exist only on a local machine.
14. `scripts/launch-claude-ubuntu` and `scripts/launch-claude-mac` are Layer 2 tools; the cloud cannot use them because they connect to or operate on particular local machines.
15. `scripts/md-review-grid.py` and its two cell-runner programs are Layer 2 tools; the cloud can use them if the external runtimes or commands they invoke are also available in the cloud environment.
16. `scripts/md-drift-lint.py` is a Layer 2 tool that the cloud can access.
17. `scripts/git-gatekeeper.py` is a Layer 2 tool that the cloud can access.
18. `scripts/backup-health-check.py`, which was pending in PR #58, is a Layer 2 tool; the cloud cannot use it because it examines backup state that exists only on a local machine.
19. `docs/cross-project/git-gatekeeper-design.md` is classified with Layer 2 as the design document for a tool, and the cloud can access it.
20. `docs/cross-project/fast-handoff-design.md` is classified with Layer 2 as the design document for a tool, and the cloud can access it.
21. `docs/cross-project/fleet-machine-paths-and-checkouts.md` is classified with Layer 2 as tool-related design documentation, and the cloud can access it.
22. `docs/cross-project/nc-python-toolchain-plan.md` is provisionally classified as Layer 2, subject to the later verification described below, and the cloud can access it.
23. `docs/cross-project/nc-python-toolchain-target-architecture.md` is provisionally classified as Layer 2, subject to later verification, and the cloud can access it.
24. `docs/cross-project/comms-bridge-spec.md` is provisionally classified as Layer 2, subject to later verification, and the cloud can access it.
25. `docs/cross-project/seed-claude-md-draft.md` is provisionally classified as Layer 2, subject to later verification, and the cloud can access it.
26. `docs/cross-project/nedschorus-founding-plan.md` is Layer 3 project content that has been placed in the wrong directory; the cloud can access it.
27. `docs/agents/`, containing the agent-seat model and briefs, is Layer 3 project content that the cloud can access.
28. `docs/issues/`, `docs/wiki/`, `docs/drafts/`, and `docs/founding/` contain Layer 3 project content that the cloud can access.
29. `md-review-records/` contains Layer 3 project content that the cloud can access.
30. The four rows labeled “unverified” were assigned to Layer 2 solely on the basis of their filenames and their location in `docs/cross-project/`; their contents were not read to determine their classifications.
31. The next person who works on any of those four entries should inspect it and either confirm or correct its manifest row instead of treating the provisional classification as established fact.
32. One file is known to be incorrectly placed, and the user has already decided where it should go.
33. `docs/cross-project/nedschorus-founding-plan.md` is to be moved to `docs/nedschorus-plan.md`, thereby changing its filename or title designation; its existing internal heading already says “nedschorus Boot-Up Plan,” which shows that its filename and its own stated title have been inconsistent.
34. The user decided on that move on August 14, 2026, but intentionally deferred performing it because 14 files refer to the old path, one of those files is the instruction-class `.claude/skills/ghi-write/SKILL.md` and therefore requires approval through a separate guided “walk” process, and two additional referring files appear to be under revision in a branch that has not yet been merged.
35. The move must remain pending until that branch is merged into its destination branch.

## The boundary: what was decided, and what is still open

1. The user has decided to adopt the three-layer model and to treat the manifest’s per-component classifications as the part that puts the abstract model into operation.
2. A table defining layers without classifying actual files produces no concrete placement decisions, while a file classification that records no underlying reasoning gives future maintainers no principled way to classify new files.
3. The conceptual layer model and the concrete manifest are therefore kept together in one document.
4. The user has also decided not to divide the current repository yet.
5. There are genuine and increasingly strong reasons to split it: a second project now exists, and a cloud session receives only the contents carried by its cloned repository.
6. Nevertheless, the reasons against splitting now are specific and remain unresolved.
7. Before a split occurs, an installation mechanism that includes a version check must be implemented.
8. Without that mechanism, source fixes could remain undeployed, recreating the exact failure mode the user anticipated for the gatekeeper and causing agents to pursue the same apparent problem repeatedly.
9. Each cloud session is tied to one repository.
10. If the shared machinery is removed from `nedschorus`, a cloud session that cloned `nedschorus` will be unable to see that machinery, and teleporting that session to a local machine will place it in a checkout of the project repository rather than automatically providing a checkout of the machinery repository.
11. Cloud limitations therefore both support creating a shared repository and oppose removing necessary machinery from the single repository used by a particular cloud session.
12. A cloud session receives the contents of whichever one repository it clones, not an automatic combination of multiple repositories.
13. Dividing the current repository would create two independent paths through review and merging.
14. The project’s change-control system is designed around a single controlled path into the `main` branch, so a split would double the repository credentials or authentication work that is already preventing completion of the git-gatekeeper.
15. The existing manifest will make a future split inexpensive because the boundary has already been drawn and each file has been classified, allowing files to be moved according to a list instead of requiring someone to reconstruct their purposes from repository history and contents.
16. The purpose is to make the classification decisions now, while doing so has little cost and before an actual split makes those decisions operationally urgent; “free” appears to mean low-cost in effort or consequences, not literally without monetary cost.
17. One unresolved decision belongs to the user: which of the user’s accounts should own each repository.
18. The user works through two identities, `ned@lerner1.com` for nonprofit work and `junk@lerner1.com` for personal work, and a cloud session authenticated under one identity may lack permission to read a repository owned by the other.
19. The `nedschorus` repository currently belongs to the `nedschorus` GitHub organization, while merges are performed under the identity or account named `NedLern`.
20. Until repository ownership and account access are resolved, splitting could create a shared repository that some of the user’s own sessions lack permission to clone.
21. The ownership and access question must be answered before the repository is split, rather than being deferred until the split is underway.

## Filing rule

1. The following tests must be applied in the stated order when classifying a new file.
2. First, ask whether another project would want the file with no modifications.
3. If the answer is no, classify the file as Layer 3 project content, keep it in this repository, and place it under `docs/` or the conventional location for that type of project-specific file.
4. If the file passes the first test, ask whether it must be loaded at session startup in order to function.
5. If startup loading is required, classify it as Layer 1 runtime material.
6. For now, that Layer 1 file remains in the current repository; after a future repository split, it should become an installed artifact and must use the previously described version stamp and staleness check.
7. If the file is reusable across projects but does not require startup loading, classify it as a Layer 2 tool, place the tool in `scripts/`, and place its design document in `docs/cross-project/`.
8. If the correct layer truly cannot be determined, explicitly record that uncertainty in the file’s manifest row instead of silently choosing a classification.
9. A manifest row that may be wrong but openly identifies its uncertainty is more useful than a confident-looking classification whose basis cannot be examined or verified.
