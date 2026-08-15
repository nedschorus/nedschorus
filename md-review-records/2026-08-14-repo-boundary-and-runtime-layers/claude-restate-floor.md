<!-- provenance: runtime=claude model=claude-sonnet-5 effort=high cell=restate tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/cross-project/repo-boundary-and-runtime-layers.md -->

# Title and lede

1. This document's stated subject, given as a sentence fragment rather than a full sentence, is: where within the project/repository a newly created file should be placed, and the reasoning behind that placement.
2. This document's content was decided/authorized ("ruled") by the user on 2026-08-14, during a collaborative work session referred to as "the walk," and that same session also, as a separate outcome, improved/strengthened ("hardened") the backup system belonging to "the box" (elsewhere identified as the machine ned-box). (Note: "the walk" is used here as if it names a specific, known kind of session — it isn't defined in this document. It could mean simply "the working session," or it could refer specifically to a session run using the "walk-me-through" skill referenced elsewhere in this environment. I can't tell which from this document alone.)

# The problem this exists to settle

1. The git repository named `nedschorus` contains two kinds of content that differ from one another, both held within one repository.
2. One portion of the repository's contents relates specifically to the nedschorus project itself: its issue-tracker items, its wiki, briefs associated with individual "seats" (a role/position term used but not defined in this document — inferred to mean an assigned work slot or position), and documents recording the project's founding decisions.
3. The remaining portion consists of tooling/infrastructure that has no particular connection to this project specifically — examples given are a program supervising handoffs between sessions, programs that launch Claude agent sessions, a tool for reviewing markdown files in a grid layout, a status-line UI element, and "skills" (packaged instruction sets Claude Code can load).
4. A second, separate project already exists on the same machine, located at `~/nedsmessenger`, and it already has its own accumulated set of agent session transcripts; because of this, the concept of "shared machinery" (infrastructure used by more than one project) is now an actual, concrete situation rather than a merely theoretical one.
5. The dividing line between project-specific content and shared machinery was informally hinted at, rather than being explicitly and formally established as a rule.
6. A directory named `docs/cross-project/` exists in the repository, and its existence/name is itself the informal hint referred to above — but a file called `nedschorus-founding-plan.md`, which is specific to nedschorus's own founding rather than being cross-project material, is located inside that directory; i.e., a project-specific document has been placed into a location meant for material shared across projects.
7. This one instance of misplacement is presented as proof of the underlying issue: there existed a label/concept for the boundary (the directory's name implying such a boundary) but no actual defined rule specifying what belongs on each side of it, so there was no way to check any file's placement against a rule, because no such rule existed.

# What is not the problem

1. The issue under discussion is not about the physical/logical layout of files and folders on disk.
2. Moving a file from one directory to another is inexpensive and easily undone, and correcting a file placed in the wrong directory costs only running the `git mv` command.
3. The issue is also not about tidiness or organizational neatness.
4. A single repository holding both kinds of content works adequately when there is one person operating across two machines.
5. If that scenario (one person, two machines) were the entire situation, then the correct response would be to leave the current arrangement unchanged.
6. The real underlying problem is labeled "delivery" — the challenge of getting the shared machinery to whatever runtime environment needs to use it.
7. This delivery problem is what makes the boundary between the two kinds of content structurally important rather than cosmetic ("load-bearing," a construction metaphor for something essential to the whole structure), and it is the reason the correct resolution must be determined by the technical properties of the runtime environments rather than by personal preference or style ("taste").

# The three runtimes

1. In this document, "runtime" is defined specifically as a location/environment where a Claude Code session actually executes.
2. There are exactly three such runtimes, and they differ from each other in what they are able to access.
3. **Table — "The box":** the runtime called "the box" is the machine `ned-box`, running Ubuntu, connected to the local area network; the filesystem it can access is the box's own local filesystem, which includes the `~/.claude` directory, directories called "seat worktrees" (git working copies tied to individual work "seats"), and the `/mnt/backup` mounted backup location.
4. **Table — "The Mac":** the runtime called "the Mac" is the user's own Mac computer, the machine at which he physically works; the filesystem it can access is the Mac's own local filesystem, including its own separate `~/.claude` directory and its Time Machine backup data.
5. **Table — "The cloud":** the runtime called "the cloud" is infrastructure operated by Anthropic; it cannot access either the box's or the Mac's filesystem, and instead works by cloning a git repository and doing its work inside that cloned copy.
6. Of the three, the cloud runtime is specifically the one whose limitations shape/constrain everything discussed in the rest of the document.
7. The cloud runtime has no `~/.claude` directory to install anything into, has no way to read any file stored locally on either machine, and has no access route to either machine at all.
8. A session running in the cloud can access only what is contained inside the specific git repository it cloned, and nothing beyond that.
9. Two additional factual claims about cloud sessions follow; these were determined by inspecting the actual Claude Code binary at version 2.1.232, rather than being assumed, and the supporting detail is recorded in the file `docs/issues/queue/45-session-seat-and-isolation-riders.md`.
10. Running `claude --teleport` transfers an active session between the cloud runtime and a local command-line session, and this works in either direction (cloud-to-local or local-to-cloud).
11. For that teleport operation to work, the local working directory must have no uncommitted changes ("clean"), and the command must be run from within a local checkout of the very same repository the cloud session had used.
12. Cloud sessions synchronize files subject to strict, fixed limits, and when a repository contains more files than the per-conversational-turn sync process can track, the cloud session halts outright rather than continuing to function with silently reduced capability.
13. As a result, the size of a repository (in file count) is an actual functional limitation on what the cloud runtime can do, not merely something that affects how quickly it operates.

# The three layers

1. Each individual component belongs to exactly one of the three layers described below, and which layer it belongs to is determined by where that component must physically be located at the moment it is actually used.

## Layer 1 — Runtime: must be present in every session

1. This layer consists (at least) of: the status line, skills, hooks, and the globally-applicable `CLAUDE.md` file.
2. Claude Code loads these specific component types from two locations — `~/.claude/` and the `.claude/` directory inside the current working directory — and this loading happens only at the moment a session begins; no subsequent action performed by an agent during the session can cause these to be loaded later.
3. The intended approach for these components is to install them into `~/.claude/` separately on each machine, rather than copying/bundling them into every individual project's repository.
4. This installation approach is not an improvised stopgap but the officially supported mechanism the underlying system ("the harness") provides, and the user already depends on this exact mechanism: `~/.claude/CLAUDE.md` is loaded into every session on the box automatically and unconditionally, with no separate step needed to "remember" to load it.
5. There is a cost to this approach that the document says must be actively designed around rather than discovered later by accident: an installed copy of a component can become outdated relative to its original source, without any visible signal that this divergence has occurred.
6. The user has already made a ruling addressing this exact risk in a different context, by requiring that the "git-gatekeeper" tool track its own version and update itself automatically; the quoted reasoning is that AI systems tend to get stuck repeatedly trying to fix a problem without recognizing that a fix also needs to be deployed to take effect.
7. Any process for installing a layer-1 component in this project must carry the same requirement: it must include a version marker and a mechanism to detect staleness, and this must be true starting from the very first version of that install process, not added later.

## Layer 2 — Tools: invoked by path when needed

1. This layer consists (at least) of: the handoff supervisor, the launcher scripts, the md-review grid tool, "the drift lint" (a linting tool checking for documentation inconsistency, inferred from its name), the git-gatekeeper, and the backup health check.
2. These components are run by invoking them by name at whatever moment they're needed, so they must exist somewhere findable on disk — specifically, in a git checkout that is on the system `PATH` — but, unlike layer 1, they do not need to be loaded automatically when a session starts.
3. Of the three layers, layer 2 has the strongest case for living in its own separate repository, because it is exactly the set of components a second, different project would need to clone in order to have this shared machinery working.

## Layer 3 — Project content: belongs to one project

1. This layer consists (at least) of: issues, the wiki, seat briefs, drafts, design documents that are specifically about this project, and the founding decisions.
2. The simplest test for whether something belongs here is: would a different, separate project want to use this exact file unchanged?
3. If answering that question honestly requires qualification (i.e., "it depends") rather than a clean yes or no, the file should be classified as layer-3 project content.

# The manifest

1. This section lists every component present in the repository as of 2026-08-14, together with its assigned classification.
2. Layer-3 entries are listed grouped by containing directory rather than individually by file, because there are many of them and they are similar enough in kind that individual listing wasn't judged necessary.
3. **Table rows (each restated as a claim):**
   - `scripts/session-statusline-command.py` is classified layer 1; a cloud session can reach it only if it happens to be part of the repository it cloned.
   - `.claude/hooks/instruction-file-guard.py` is classified layer 1; reachable by a cloud session only if included in the cloned repository.
   - `.claude/hooks/backup-and-snapshot-write-guard.py` (not yet merged, awaiting pull request #58) is classified layer 1; whether a cloud session can reach it is treated as beside the point ("irrelevant"), because this hook's job is to guard file paths that are local to a specific machine, which the cloud runtime doesn't have anyway.
   - `scripts/handoff-context-threshold-hook.py` is classified layer 1; reachable by a cloud session only if included in the cloned repository.
   - `.claude/skills/walk-me-through/` is classified layer 1; reachable by a cloud session only if included in the cloned repository.
   - `.claude/skills/md-review/` is classified layer 1; reachable by a cloud session only if included in the cloned repository.
   - `.claude/skills/handoff/` is classified layer 1; reachable by a cloud session only if included in the cloned repository.
   - `.claude/skills/ghi-write/` is classified layer 1; reachable by a cloud session only if included in the cloned repository.
   - `scripts/handoff-supervisor.py` is classified layer 2; a cloud session cannot usefully reach it, because it manages sessions local to a specific machine.
   - `scripts/handoff-write-and-check-supervisor.py` is classified layer 2; unreachable by a cloud session for the same reason as the previous entry.
   - `scripts/handoff-extract-conversation.py` is classified layer 2; unreachable by a cloud session because it reads conversation transcripts stored locally on a machine.
   - `scripts/launch-claude-ubuntu` and `scripts/launch-claude-mac` are both classified layer 2; neither is usefully reachable by a cloud session, because each connects to one specific physical machine.
   - `scripts/md-review-grid.py` and its two associated "cell runner" scripts are classified layer 2; a cloud session can reach them, but only conditionally — specifically only if whatever runtime environments this script launches as subprocesses ("shells out to") are themselves present in the cloud environment.
   - `scripts/md-drift-lint.py` is classified layer 2; unconditionally reachable by a cloud session.
   - `scripts/git-gatekeeper.py` is classified layer 2; unconditionally reachable by a cloud session.
   - `scripts/backup-health-check.py` (not yet merged, awaiting pull request #58) is classified layer 2; unreachable by a cloud session because it reads backup state that is local to a machine.
   - `docs/cross-project/git-gatekeeper-design.md` is classified as a layer-2 tool's design document; unconditionally reachable by a cloud session.
   - `docs/cross-project/fast-handoff-design.md` is classified as a layer-2 tool's design document; unconditionally reachable by a cloud session.
   - `docs/cross-project/fleet-machine-paths-and-checkouts.md` is classified as a layer-2 tool's design document; unconditionally reachable by a cloud session.
   - `docs/cross-project/nc-python-toolchain-plan.md` is tentatively classified layer 2, but marked as not yet confirmed by actually reading it ("unverified"), with further explanation appearing later in the document; marked as reachable by a cloud session.
   - `docs/cross-project/nc-python-toolchain-target-architecture.md` is likewise tentatively/unverified-ly classified layer 2, explanation deferred; marked reachable by a cloud session.
   - `docs/cross-project/comms-bridge-spec.md` is likewise tentatively/unverified-ly classified layer 2, explanation deferred; marked reachable by a cloud session.
   - `docs/cross-project/seed-claude-md-draft.md` is likewise tentatively/unverified-ly classified layer 2, explanation deferred; marked reachable by a cloud session.
   - `docs/cross-project/nedschorus-founding-plan.md` is classified layer 3 but explicitly flagged as currently stored in the wrong place ("misfiled"), with explanation appearing later in the document; marked reachable by a cloud session.
   - The directory `docs/agents/`, described as containing the "seat model" and seat briefs, is classified layer 3; unconditionally reachable by a cloud session.
   - The directories `docs/issues/`, `docs/wiki/`, `docs/drafts/`, and `docs/founding/` are each classified layer 3; unconditionally reachable by a cloud session.
   - `md-review-records/` is classified layer 3; unconditionally reachable by a cloud session.
4. The four entries labeled "unverified" were assigned their classification based only on inference from their filenames and their location inside `docs/cross-project/`, not from anyone actually having read their contents.
5. Whoever next works with these four files should confirm the classification is correct, or fix it, rather than simply carrying forward the unverified guess.
6. There is exactly one entry that is both incorrectly located and already has a decided destination for where it should go.
7. The file `docs/cross-project/nedschorus-founding-plan.md` is to be moved to `docs/nedschorus-plan.md` and given a new title; the justification offered is that the file's own internal first-level heading already reads "nedschorus Boot-Up Plan," which differs from its current filename, meaning the filename and the document's self-description have been inconsistent with each other for some time already.
8. This move was decided on 2026-08-14 but deliberately not carried out at that same time, for these stated reasons: 14 files in the repository reference this document by its file path; one of those 14, `.claude/skills/ghi-write/SKILL.md`, is categorized as "instruction-class" (a category implying it needs special handling) and requires its own separate step-by-step reviewed approval (referencing a "walked" review process); and two more of the 14 citing files are currently being rewritten in a git branch that has not yet been merged.
9. The move is being postponed until that unmerged branch is merged into the main branch.

# The boundary: what was decided, and what is still open

1. One decided item is: the three-layer model described earlier, together with the fact that the manifest (per-file classification table) constitutes the functionally active part of that model.
2. A table that only defines the three layers abstractly, without classifying individual files into them, would not actually resolve anything practical; and a per-file classification made without any accompanying reasoning could not be applied to new files in the future.
3. Because of this interdependence, the layer definitions and the manifest are kept together within one single document rather than split apart.
4. Another decided item is: the repository should not be split into multiple repositories at this time (with "yet" implying this could change later).
5. There is a genuine, legitimate case in favor of splitting, and it became stronger during the work session that produced this document, because a second project now exists and because cloud sessions can only access whatever a single cloned repository contains.
6. However, there is also a specific, tangible, and currently unresolved case against splitting, elaborated in the following points.
7. First: splitting requires that an installation mechanism including a version-check capability be built beforehand, not afterward; without this, the split would recreate exactly the failure the user had earlier predicted for the git-gatekeeper — fixes being made to source but never actually deployed, resulting in a repeating, unproductive cycle.
8. Second: a cloud session can only work within one single repository (the one it cloned).
9. If the shared machinery were moved out of the nedschorus repository, a cloud session that had cloned nedschorus would lose access to it, and using `--teleport` to move such a session locally would place it inside a checkout of the project repository (not necessarily one containing the machinery).
10. The properties of the cloud runtime simultaneously argue for keeping everything in one shared repository and act as a constraint against splitting apart whichever single repository a given cloud session is using.
11. A cloud session's access is entirely determined by, and confined to, whichever single repository it clones.
12. Third: having two repositories would require two separate review-and-merge pathways, which conflicts with the project's overall design principle of having exactly one entry point through which changes reach the main branch.
13. Splitting would double the work related to managing authentication credentials, which is already the current obstacle blocking the git-gatekeeper from being fully activated.
14. The existence of the manifest is what will make the eventual split inexpensive when it happens: because the boundary is already defined and every file already classified, performing the split becomes a mechanical process of working through a list rather than requiring investigative research to figure out where things belong.
15. The underlying reason for doing this classification work now is that doing so currently costs little or nothing extra, and taking advantage of that low cost is the whole point. (Note: "while it is free" could mean "at essentially no additional cost right now" or could carry a looser sense of "while there's nothing yet constraining the decision" — I read it as the former, but the latter is a plausible alternate reading.)
16. There remains one open question, which only the user is positioned to answer: which of his accounts should own which repository, in a scenario where the repository gets split.
17. The user operates under two separate identities — `ned@lerner1.com` for non-profit work and `junk@lerner1.com` for personal matters — and a cloud session authenticated under one of these identities may be unable to read a repository owned by the other identity.
18. The nedschorus repository currently belongs to a GitHub organization also named `nedschorus`, and merge operations into it are performed under the GitHub account `NedLern`.
19. Until the ownership question is answered, proceeding with any split risks creating a repository that some of the user's own sessions would be unable to clone.
20. The recommendation is that this question must be answered before beginning a split, not partway through one.

# Filing rule

1. The following is an ordered sequence of questions to apply when deciding where a new file should be placed.
2. First question: would a different project want to use this file exactly as-is, unchanged? If the answer is no, the file is layer 3 — it belongs in this repository, placed under `docs/` or wherever else files of its type are conventionally kept.
3. Second question (asked if the file wasn't classified as layer 3): must this file be loaded automatically at the moment a session starts in order to function? If yes, it is layer 1. Such a file currently lives directly in the repository; once the eventual split happens, it will instead become something installed as a separate artifact, and it will need the version stamp and staleness check described earlier.
4. If the file matches neither of the preceding conditions, it is layer 2 — a tool, placed in `scripts/`, with its design document placed in `docs/cross-project/`.
5. When it is genuinely difficult to determine which layer a file belongs to, the correct action is to record that uncertainty directly in the file's manifest row, rather than silently choosing a classification without indicating any doubt.
6. A manifest row that turns out to be wrong but had explicitly marked itself as uncertain is more valuable than a row that appears confident but that nobody is able to actually verify.

