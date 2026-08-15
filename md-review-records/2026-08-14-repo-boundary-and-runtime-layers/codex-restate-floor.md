<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=restate tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/cross-project/repo-boundary-and-runtime-layers.md -->

## Repository boundary and runtime layers

1. The document explains where a new file should be placed and why.
2. The user established this rule on 2026-08-14 during a walkthrough that also strengthened the box’s backup protections.
3. This document should be read before creating a script, skill, hook, or enduring document, and before suggesting that an existing item be moved between repositories.
4. It addresses which repository and which machine should contain something, considering three execution environments rather than only one.

## The problem this exists to settle

1. The `nedschorus` repository contains two fundamentally different categories of material.
2. One category is specific to `nedschorus`: its issues, wiki, seat briefs, and founding decisions. “Seat briefs” is not defined here; I take it to mean briefs describing the project’s agent seats or roles.
3. The other category is general-purpose machinery that is not inherently about `nedschorus`, including a handoff supervisor, agent launchers, a Markdown review grid, a status line, and skills.
4. There is already another project on the same machine, `~/nedsmessenger`, and that project has accumulated its own agent transcripts, so the need for machinery shared between projects is now an actual situation rather than a hypothetical one.
5. The repository boundary was hinted at but never made into an explicit decision or rule.
6. The existence of `docs/cross-project/` is that hint, but the project-specific file `docs/cross-project/nedschorus-founding-plan.md` is stored inside the supposedly shared directory.
7. That misplaced file demonstrates the problem: the boundary had a label but no enforceable rule.
8. Because there was no rule, nobody could test a file’s placement against a defined standard.

## What is not the problem

1. The problem is not the physical disk layout itself.
2. Moving a file between directories is inexpensive and reversible, and an incorrectly placed file can be corrected with `git mv`.
3. The problem is not untidiness or an aesthetically mixed repository.
4. A single repository containing both project-specific material and shared machinery works adequately when one person uses two machines.
5. If that limited situation were the entire situation, the correct choice would be to leave the repository as it is.
6. The actual problem is delivery: getting the shared machinery to the execution environment that needs to use it.
7. That delivery concern makes the repository boundary operationally important—“load-bearing” means that practical use depends on getting the boundary right—and therefore the decision should be based on runtime requirements rather than personal preference.

## The three runtimes

1. In this document, a “runtime” means a place where an actual Claude Code session executes.
2. There are three such places, and each has a different view of the filesystem.
3. The box runtime is `ned-box`, an Ubuntu machine on the local network.
4. The box runtime can access that machine’s filesystem, including `~/.claude`, seat worktrees, and `/mnt/backup`.
5. The Mac runtime is the user’s Mac, where the user physically works.
6. The Mac runtime can access the Mac’s filesystem, including that Mac’s own `~/.claude` directory and its Time Machine backups.
7. The cloud runtime runs on Anthropic’s infrastructure.
8. The cloud runtime can access neither the box’s nor the Mac’s filesystem; it clones a git repository and works within that cloned repository.
9. The cloud runtime is the limiting case that determines the rules that follow.
10. A cloud session has no `~/.claude`, cannot read files that exist only on either machine, and has no route to either machine.
11. A cloud session can access exactly the files contained in the git repository it cloned, and cannot access anything outside that repository.
12. The document says that two additional facts about cloud sessions were obtained by reading the Claude Code 2.1.232 binary rather than inferred, and that the detailed record is in `docs/issues/queue/45-session-seat-and-isolation-riders.md`.
13. `claude --teleport` can transfer a session from the cloud to a local CLI and can also transfer one from a local CLI to the cloud.
14. Teleporting requires the local working directory to be clean and requires the command to be run from a checkout of the same repository that the cloud session used.
15. Cloud sessions synchronize files subject to strict limits, and when a repository contains more files than can be tracked during a per-turn synchronization, the session stops instead of quietly operating with incomplete synchronization.
16. Repository size therefore limits what the cloud runtime can functionally handle, not merely how fast it handles it.

## The three layers

1. Every component must be assigned to exactly one of the three layers.
2. The deciding criterion is where the component must physically exist at the moment it is used.

### Layer 1 — Runtime: must be present in every session

1. The status line, skills, hooks, and global `CLAUDE.md` are runtime components that must be available in every session.
2. Claude Code reads these items from `~/.claude/` and from the working directory’s `.claude/` directory when the session starts.
3. Actions performed by an agent after the session has started cannot cause these startup-loaded items to be loaded later.
4. These components should be installed into `~/.claude/` on every machine rather than copied into every project repository.
5. This per-machine installation is not being presented as an improvised workaround; it is the location supported by the harness, and the user already depends on it.
6. On the box, `~/.claude/CLAUDE.md` is loaded automatically into every session, without requiring an agent to remember or deliberately recall it.
7. The unavoidable cost of installing a copy is that the installed copy can quietly become older than the source copy.
8. The user has already decided, in another context, that this exact stale-installation risk must be handled by making the git-gatekeeper version-aware and able to upgrade itself automatically.
9. The quoted concern means that an AI may repeatedly try to fix a problem in source files while failing to recognize that the fix must also be deployed, creating an endless cycle of attempted repairs.
10. Every installation mechanism for this layer must therefore include, from its first version, a version stamp and a check that detects when the installed copy is stale.

### Layer 2 — Tools: invoked by path when needed

1. The handoff supervisor, launchers, Markdown-review grid, drift lint, git-gatekeeper, and backup health check are tools in this layer.
2. These tools are invoked by name when needed, so they must exist somewhere on disk where they can be found—such as a checkout included on `PATH`—but they do not need to be loaded when a session starts.
3. This layer is the strongest candidate for its own repository because a second project could clone that repository and obtain the machinery it needs.

### Layer 3 — Project content: belongs to one project

1. Issues, the wiki, seat briefs, drafts, design documents about this project, and founding decisions are project-specific content.
2. The simplest classification test is whether another project would want the file exactly as it is, without changing it.
3. If answering that question requires saying “it depends,” the file should be treated as project content rather than as shared machinery.

## The manifest

1. The manifest classifies every component that was in the repository on 2026-08-14.
2. Because there are many Layer 3 files with the same classification, the manifest lists those files by directory instead of listing every file individually.
3. The table’s “Cloud can reach it?” column asks whether a cloud session can access the component under the cloud-repository rules described earlier.
4. `scripts/session-statusline-command.py` is a Layer 1 runtime component, and a cloud session can access it only when it is included in the repository that the cloud session cloned.
5. `.claude/hooks/instruction-file-guard.py` is also a Layer 1 runtime component, with the same conditional cloud access.
6. `.claude/hooks/backup-and-snapshot-write-guard.py`, which is pending PR #58, is classified as Layer 1, but cloud reachability is irrelevant because this hook protects paths that exist only on a machine.
7. `scripts/handoff-context-threshold-hook.py` is a Layer 1 runtime component, and a cloud session can access it only if the cloned repository contains it.
8. `.claude/skills/walk-me-through/` is a Layer 1 runtime component, conditionally available to the cloud when present in the cloned repository.
9. `.claude/skills/md-review/` is a Layer 1 runtime component, conditionally available to the cloud when present in the cloned repository.
10. `.claude/skills/handoff/` is a Layer 1 runtime component, conditionally available to the cloud when present in the cloned repository.
11. `.claude/skills/ghi-write/` is a Layer 1 runtime component, conditionally available to the cloud when present in the cloned repository.
12. `scripts/handoff-supervisor.py` is a Layer 2 tool, and a cloud session cannot reach it because it manages sessions that are local to a machine.
13. `scripts/handoff-write-and-check-supervisor.py` is a Layer 2 tool, and a cloud session cannot reach it for the same machine-local reason.
14. `scripts/handoff-extract-conversation.py` is a Layer 2 tool, and a cloud session cannot reach it because it reads transcripts stored on a machine.
15. `scripts/launch-claude-ubuntu` and `scripts/launch-claude-mac` are Layer 2 tools, and a cloud session cannot reach them because they interact with particular physical machines.
16. `scripts/md-review-grid.py` and its two cell runners are Layer 2 tools, and a cloud session can reach them if the runtimes that those tools invoke through subprocesses also exist in the cloud environment.
17. `scripts/md-drift-lint.py` is a Layer 2 tool that a cloud session can reach.
18. `scripts/git-gatekeeper.py` is a Layer 2 tool that a cloud session can reach.
19. `scripts/backup-health-check.py`, pending PR #58, is a Layer 2 tool, but a cloud session cannot reach it because it reads backup state stored on a machine.
20. `docs/cross-project/git-gatekeeper-design.md` is the design document for a Layer 2 tool, and a cloud session can reach it.
21. `docs/cross-project/fast-handoff-design.md` is the design document for a Layer 2 tool, and a cloud session can reach it.
22. `docs/cross-project/fleet-machine-paths-and-checkouts.md` is a Layer 2 tool design document, and a cloud session can reach it.
23. `docs/cross-project/nc-python-toolchain-plan.md` is provisionally classified as Layer 2 based on its filename and location, has not been verified by reading it, and is reachable by a cloud session because it is in the repository.
24. `docs/cross-project/nc-python-toolchain-target-architecture.md` has the same provisional Layer 2 classification and the same cloud reachability.
25. `docs/cross-project/comms-bridge-spec.md` has the same provisional Layer 2 classification and the same cloud reachability.
26. `docs/cross-project/seed-claude-md-draft.md` has the same provisional Layer 2 classification and the same cloud reachability.
27. `docs/cross-project/nedschorus-founding-plan.md` is Layer 3 project content in the wrong location, and it is reachable by a cloud session because it is currently in the repository.
28. `docs/agents/`, containing the seat model and briefs, is Layer 3 project content and is reachable by a cloud session.
29. `docs/issues/`, `docs/wiki/`, `docs/drafts/`, and `docs/founding/` are Layer 3 project-content directories and are reachable by a cloud session.
30. `md-review-records/` is Layer 3 project content and is reachable by a cloud session.
31. Four entries are marked unverified because their classifications were inferred from their filenames and their location in `docs/cross-project/`, not established by reading their contents.
32. The next person who works on any of those four entries should verify the classification and change the manifest row if necessary, rather than accepting the existing guess.
33. One entry is both misplaced and already assigned a destination: `docs/cross-project/nedschorus-founding-plan.md` should move to `docs/nedschorus-plan.md` and should be renamed.
34. The file’s current heading already says “nedschorus Boot-Up Plan,” so the filename has contradicted the document’s own heading for a substantial period of time.
35. The move was decided on 2026-08-14 but intentionally not performed then because fourteen files refer to the old path, including `.claude/skills/ghi-write/SKILL.md`.
36. Because `.claude/skills/ghi-write/SKILL.md` contains instructions, it requires its own approval through a walkthrough; “walked approval” is not formally defined here, so I read it as a separate, guided review rather than automatic coverage by the earlier move decision.
37. Two other references are being rewritten in a branch that has not yet been merged.
38. The move is therefore deferred until that branch has landed.

## The boundary: what was decided, and what is still open

1. The three-layer model has been decided, and the manifest is the operational half of that decision.
2. A table describing layers without classifying individual files would not determine where particular files belong.
3. A file classification without the reasoning behind it would not provide a basis for classifying future files consistently.
4. The layer model and the manifest remain in one document so that both the classifications and their reasoning stay together.
5. It has also been decided not to split the repository yet.
6. The argument for splitting is genuine and became stronger during the walkthrough that produced this document because a second project now exists and cloud sessions can receive only what their cloned repository contains.
7. The argument against splitting is concrete but has not been resolved.
8. Before splitting, an installation mechanism with a version check must be built.
9. Without that mechanism, splitting would recreate the predicted gatekeeper failure in which fixes are made in source but never deployed, causing repeated attempts to fix the same underlying problem.
10. A cloud session is tied to one repository.
11. If the shared machinery is removed from `nedschorus`, a cloud session that cloned `nedschorus` will no longer be able to see that machinery, and teleporting the session will place it in the checkout of the project repository rather than in a separate machinery repository.
12. The cloud runtime therefore supports having a shared repository, while also limiting any attempt to split the repository that a cloud session is using.
13. A cloud session receives whichever repository it cloned; it does not automatically receive machinery from another repository.
14. Two repositories would create two separate review-and-merge workflows.
15. The project’s existing change-control design is described metaphorically as “one door to main”; I read that as one controlled path through which changes enter the main branch.
16. Splitting the repositories would double the account and authentication work, which is already the blocking issue for the git-gatekeeper.
17. The manifest makes a future split inexpensive because the boundary has already been drawn and every file has been assigned a classification.
18. With those classifications in place, splitting can be performed mechanically from the manifest rather than reconstructed through an archaeology-like investigation of the repository’s history and contents.
19. The point is to decide the classifications while doing so is easy, before a future split makes the work more difficult.

### The unresolved ownership question

1. The remaining open question is which account should own which repository, and the user must answer it.
2. The user operates under two identities: `ned@lerner1.com` for nonprofit work and `junk@lerner1.com` for personal work.
3. A cloud session authenticated as one identity might not be able to read a repository owned by the other identity.
4. `nedschorus` currently belongs to the `nedschorus` GitHub organization, and merges are performed as `NedLern`.
5. Until repository ownership is decided, splitting could create a repository that some of the user’s own sessions cannot clone.
6. The ownership question must be answered before the split begins, not while the split is already being performed.

## Filing rule

1. For a new file, the rules are applied in the stated order.
2. First ask whether a different project would want the file unchanged; if the answer is no, classify it as Layer 3 and keep it in this repository under `docs/` or under whatever directory is appropriate for that kind of project content.
3. Next ask whether the file must be loaded when a session starts in order to work; if yes, classify it as Layer 1.
4. A Layer 1 file remains in the repository for now, but if the repositories are later split it becomes something installed into the runtime, and that installation must have the previously required version stamp and staleness check.
5. If neither of those rules applies, classify the file as Layer 2: put the tool in `scripts/` and put its design document in `docs/cross-project/`.
6. If the correct layer is genuinely uncertain, record that uncertainty in the manifest row instead of silently choosing a classification.
7. An explicitly uncertain classification is more useful than a confidently stated classification that nobody can verify.
