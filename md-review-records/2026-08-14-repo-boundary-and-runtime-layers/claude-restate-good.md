<!-- provenance: runtime=claude model=claude-opus-5 effort=high cell=restate tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/cross-project/repo-boundary-and-runtime-layers.md -->

The file has no YAML frontmatter — it begins directly with the `#` heading. Restatements follow.

## Title and opening (before the first section heading)

1. **"# Repository boundary and runtime layers"** — The document's title announces its subject as two related things: the dividing line between what belongs in this repository versus elsewhere ("repository boundary"), and a scheme of "layers" defined in terms of the environments in which code runs ("runtime layers").

2. **"Where a new file belongs, and why."** — A sentence fragment serving as a subtitle: this document tells you which location (repository and directory) a newly created file should be placed in, and gives the reasoning behind that placement rather than just the answer.

3. **"Ruled by the user 2026-08-14, in the walk that also hardened the box's backups."** — The decisions written here were made authoritatively by the human user (not by an agent) on 14 August 2026. "The walk" means a walk-me-through session — a conversation in which material was presented to him item by item for his rulings — and that same session additionally produced changes making the Ubuntu machine's (`ned-box`'s) backup arrangements more robust against failure.

4. **"Read this before creating a script, skill, hook, or lasting document, and before proposing that anything move between repositories."** — An instruction to future readers (agents or the user): consult this document as a precondition for two kinds of action — (a) authoring any new script, Claude Code skill, Claude Code hook, or document intended to persist rather than be throwaway; and (b) suggesting that any existing file be relocated from one repository to another.

5. **"It answers one question — *which repository, and which machine* — and it answers it for three runtimes rather than one."** — The document's scope is deliberately narrow: it resolves the placement question in two dimensions, namely which git repository a thing goes in and which physical/logical machine it must be present on. "For three runtimes rather than one" means the answer is not given for a single assumed execution environment but is worked out against three distinct environments in which a session may run (enumerated later as the box, the Mac, and the cloud).

## The problem this exists to settle

*(Section heading: "The problem this exists to settle" — this section states the specific difficulty that motivated writing the document and that the document's rulings are meant to resolve.)*

1. **"`nedschorus` is one repository holding two different kinds of thing."** — The git repository named `nedschorus` currently contains material of two categorically distinct sorts, even though it is a single repository.

2. **"Some of it is about nedschorus: its issues, its wiki, its seat briefs, its founding decisions."** — One of those two sorts is content specific to the nedschorus project itself, exemplified by: tracked issues, the project's wiki pages, "seat briefs" (documents describing the roles or stations — "seats" — that agents occupy in this project's working arrangement), and records of the foundational decisions that established the project.

3. **"The rest is machinery that has nothing to do with this project in particular — a handoff supervisor, agent launchers, a markdown review grid, a status line, skills."** — The other sort is general-purpose tooling ("machinery") whose function is not tied to nedschorus specifically and which would work equally for other projects; the examples given are the program that oversees handing a session over to a successor session, the scripts that start Claude agents, the "grid" tool that runs markdown reviews (presumably across multiple cells/dimensions), the status-line program, and Claude Code skills.

4. **"A second project already exists on the same machine (`~/nedsmessenger`, with its own accumulated agent transcripts), so "shared machinery" is no longer hypothetical."** — There is now a second, separate project living on the same box at the path `~/nedsmessenger`, and it has already built up its own history of agent session transcripts (i.e. it is genuinely in use, not an empty placeholder); consequently the idea of tooling being shared across projects is a present reality with a concrete second consumer, rather than a speculative future scenario used to justify design work.

5. **"The boundary was gestured at rather than decided."** — Prior to this document, the distinction between project-specific and shared material had been merely hinted at or partially indicated through some existing arrangement, but had never been settled by an explicit, stated rule.

6. **"`docs/cross-project/` exists, which is the gesture — but `docs/cross-project/nedschorus-founding-plan.md` sits inside it, this project's own founding document filed in the shared drawer."** — The existence of a directory named `docs/cross-project/` is precisely the hint referred to in the previous sentence: its name implies "material that spans projects." However, a file named `nedschorus-founding-plan.md` is located inside that directory, and that file is a document about the founding of this one project — so a project-specific document has been placed in the location reserved for cross-project material ("the shared drawer" being a metaphor for that directory).

7. **"That single misfiling is the evidence: there was a name for the boundary but no rule, so nothing could be checked against it."** — That one wrongly-placed file is offered as the proof of the preceding claim; the reasoning is that the project had a label naming the distinction (the directory name) but no articulated criterion for applying it, and without a criterion there was nothing any file's placement could be tested against, so misfilings could occur undetected.

## What is not the problem

*(Section heading: "What is not the problem" — this section rules out two candidate motivations before naming the real one.)*

1. **"**Not disk layout.**"** — A fragment introducing the first ruled-out motivation: the concern here is not about how files are arranged in directories on disk.

2. **"Moving files between directories is cheap and reversible, and a wrong directory costs a `git mv`."** — The justification for ruling that out: relocating a file from one directory to another takes little effort and can be undone, so the total cost of having put a file in the wrong directory amounts to running a single `git mv` command to correct it.

3. **"**Not tidiness.**"** — A fragment introducing the second ruled-out motivation: the concern is also not aesthetic neatness or organizational hygiene for its own sake.

4. **"A single repository holding both kinds of thing works fine for one person on two machines."** — At the current scale of operation — one human user working across two machines — keeping project content and shared machinery together in a single repository functions adequately; nothing is broken by the mixture at that scale.

5. **"If that were the whole picture, the right answer would be to leave it alone."** — Conditional claim: supposing tidiness and disk layout were the only considerations in play, the correct decision would be to make no change at all and keep the current arrangement.

6. **"The problem is **delivery**: getting the machinery to a runtime that needs it."** — The actual motivating problem is delivery in the software-distribution sense — ensuring that the shared tooling is physically present in, and accessible to, whichever execution environment requires it at the time it is required.

7. **"That is what makes the boundary load-bearing, and it is why the answer depends on runtimes rather than on taste."** — Delivery is what gives the project/shared boundary real structural consequences ("load-bearing": other things depend on it and would fail if it were wrong), and delivery is also the reason the correct placement is determined by the technical properties of the execution environments rather than by subjective preference or style.

## The three runtimes

*(Section heading: "The three runtimes" — this section enumerates and characterizes the three execution environments.)*

1. **"A "runtime" here means a place a Claude Code session actually runs."** — A stipulative definition scoped to this document: the word "runtime" is not being used in its usual senses (a language runtime, a runtime library, elapsed time); it means a physical or hosted location where a Claude Code session executes.

2. **"There are three, and they differ in what they can reach."** — The set of such locations has exactly three members, and the distinguishing property that matters for this document is the difference in what files and systems each one has access to.

3. **Table header: "| Runtime | Where it runs | Filesystem it has |"** — The table has three columns: the name of the runtime, a description of its physical location, and a description of which filesystem that runtime can see and use.

4. **Row: "| **The box** | `ned-box`, Ubuntu, on the LAN | The box's, including `~/.claude`, seat worktrees, and `/mnt/backup` |"** — The runtime called "the box" is the Ubuntu machine named `ned-box`, reachable over the local network; a session running there sees that machine's own filesystem, which specifically includes the `~/.claude` configuration directory, the git worktrees created for the various agent "seats," and the backup mount point at `/mnt/backup`.

5. **Row: "| **The Mac** | The user's Mac, where he sits | The Mac's, including its own `~/.claude` and Time Machine |"** — The runtime called "the Mac" is the user's Macintosh computer, the machine he is physically present at; a session running there sees the Mac's filesystem, which includes a `~/.claude` directory belonging to the Mac (distinct from the box's) and the Mac's Time Machine backup system.

6. **Row: "| **The cloud** | Anthropic's infrastructure | Neither machine's — it clones a git repository and works there |"** — The runtime called "the cloud" runs on servers operated by Anthropic; a session there sees neither the box's nor the Mac's filesystem. Instead it obtains its working files by cloning a git repository into its own environment and operating on that clone.

7. **"The cloud runtime is the one that constrains everything below."** — Of the three, the cloud is the environment whose limitations drive all the design conclusions stated in the remainder of the document; the other two are permissive enough not to force decisions.

8. **"It has no `~/.claude` to install into, no way to read a machine-local file, and no path to either machine."** — Three specific limitations of the cloud runtime: (a) there is no persistent per-user `~/.claude` configuration directory there that one could install shared tooling into; (b) it cannot read any file that exists only on one of the two physical machines; (c) it has no network route or access mechanism to reach the box or the Mac at all.

9. **"**A cloud session can reach exactly what is inside the git repository it cloned, and nothing else.**"** — Stated emphatically as the governing constraint: the complete set of material available to a cloud session is the contents of the one git repository it cloned; anything not committed into that repository is unavailable to it.

10. **"Two further facts about cloud sessions, read from the Claude Code 2.1.232 binary rather than assumed, with the detail recorded in `docs/issues/queue/45-session-seat-and-isolation-riders.md`:"** — An introduction to two additional claims about cloud sessions, with a provenance note: these were established by inspecting the actual Claude Code executable at version 2.1.232 (I read "read from the binary" as meaning someone examined the shipped program itself, e.g. its strings or code) rather than being inferred or taken on faith, and the fuller supporting detail is written down in the named queued-issue file.

11. **Bullet 1, first sentence: "**`claude --teleport` moves a session between the cloud and a local CLI**, in both directions."** — The Claude Code command-line invocation `claude --teleport` relocates an in-progress session across the cloud/local divide, and it works both ways: cloud-to-local and local-to-cloud.

12. **Bullet 1, second sentence: "It requires a clean local working directory and requires running **from a checkout of the same repository the cloud session used**."** — Two preconditions for that teleport command to work: the local git working directory must have no uncommitted modifications ("clean"), and the command must be issued from within a local clone/checkout of the identical repository that the cloud session had cloned — not merely a similar repository.

13. **Bullet 2, first sentence: "**Cloud sessions sync files under hard budgets** and stop rather than degrade quietly when a repository has more files than per-turn sync can track."** — File synchronization between a cloud session and its repository operates under fixed, non-negotiable limits ("hard budgets"), and when a repository contains more files than the per-conversational-turn synchronization mechanism is capable of tracking, the behavior is to halt outright rather than to silently continue with partial or degraded synchronization.

14. **Bullet 2, second sentence: "Repository size is therefore a functional limit on the cloud runtime, not merely a speed one."** — The consequence: the number of files in a repository determines whether the cloud runtime works at all, rather than only affecting how fast it works — so size is a correctness/capability constraint, not just a performance concern.

## The three layers

*(Section heading: "The three layers" — this section defines the classification scheme with three categories.)*

1. **"Every component belongs to exactly one of these, decided by *where it must physically be at the moment it is used*."** — The classification is exhaustive and mutually exclusive: each component falls into one and only one of the three layers, and the criterion that determines which is a physical-location question about the instant of use — namely, at the moment the component is actually invoked or consulted, on what filesystem must it already be sitting.

### Layer 1 — Runtime: must be present in every session

1. **Heading: "Layer 1 — Runtime: must be present in every session"** — The first category is named "Runtime," and its defining property is that its members must be available in every single session rather than being fetched on demand. (Note: "Runtime" here is being reused as a layer name, distinct from the earlier defined sense of "runtime" as an execution location; I read the layer name as meaning "things that must be in place for the session's runtime environment itself.")

2. **"The status line, skills, hooks, and the global `CLAUDE.md`."** — A fragment listing the members of layer 1: the status-line program, Claude Code skills, Claude Code hooks, and the machine-wide `CLAUDE.md` instruction file.

3. **"Claude Code reads these from `~/.claude/` and from the working directory's `.claude/` **at session start**."** — The Claude Code harness loads these artifacts from two locations — the user-level `~/.claude/` directory and the `.claude/` directory inside whatever directory the session is working in — and the loading happens once, at the moment the session begins.

4. **"Nothing an agent does later can load them."** — Because loading occurs only at session start, no action taken by an agent during the session — no file write, no command — can cause such an artifact to be picked up mid-session; it will not take effect until a new session starts.

5. **"These want to be **installed to `~/.claude/` on each machine**, not vendored into every project."** — The recommended arrangement for layer-1 artifacts is to install a copy into the `~/.claude/` directory of each physical machine, as opposed to "vendoring" them — i.e. copying them into each individual project's own repository tree so every project carries its own duplicate.

6. **"That is not a workaround — it is the path the harness provides, and the user already relies on it: `~/.claude/CLAUDE.md` loads into every session on the box unconditionally, with no recall step to forget."** — Installing into `~/.claude/` should not be read as an inelegant hack chosen to evade some limitation; it is the mechanism Claude Code itself supplies for this purpose, and the user's existing practice already depends on it, as demonstrated by `~/.claude/CLAUDE.md`, which is loaded into every session on the box automatically and without exception, requiring no separate act of remembering or retrieving it (and therefore offering no opportunity for an agent to forget to retrieve it).

7. **"The cost, which must be designed for rather than discovered: an installed copy can silently go stale against its source."** — The drawback of the install approach, which the design must anticipate in advance instead of learning about through failure in the field: the installed copy in `~/.claude/` can fall behind the canonical source version without any visible signal that it has done so.

8. **"The user has already ruled on this exact hazard in another context, requiring the git-gatekeeper to version itself and upgrade automatically, because *"AI's go in an infinite loop trying to fix problems without realizing they need to deploy those fixes."*"** — The same staleness hazard has previously been decided by the user in a different setting: he mandated that the git-gatekeeper program carry its own version identifier and update itself without manual intervention, and his stated reason (quoted verbatim) is that AI agents will loop endlessly attempting to fix a problem while failing to recognize that the fix they already made has not been deployed to the running copy.

9. **"**Any install step here carries the same obligation: a version stamp and a staleness check, from the first version.**"** — The ruling generalizes: any installation mechanism introduced for layer-1 artifacts must include both a recorded version marker and a mechanism that detects when the installed copy is out of date, and both must be present in the initial release rather than added later.

### Layer 2 — Tools: invoked by path when needed

1. **Heading: "Layer 2 — Tools: invoked by path when needed"** — The second category is named "Tools," defined by being executed on demand by referring to their filesystem location, only at the times they are wanted.

2. **"The handoff supervisor, the launchers, the md-review grid, the drift lint, the git-gatekeeper, the backup health check."** — A fragment listing layer-2 members: the program supervising session handoffs, the agent-launcher scripts, the markdown-review grid tool, the linter that detects documentation drift, the git-gatekeeper program, and the script that checks backup health.

3. **"These are run by name at the moment they are wanted, so they need to exist on disk somewhere findable — a checkout on `PATH` — but not to be loaded at session start."** — Layer-2 components are executed by invoking their name at the moment of need; the resulting requirement is that they be present on some filesystem in a location the shell can locate — the example given being a git checkout whose directory is listed in the `PATH` environment variable — while they carry no requirement to be loaded during session initialization.

4. **"This is the layer that most wants its own repository, because it is what a second project would clone to get working."** — Among the three layers, layer 2 has the strongest case for being extracted into a separate repository of its own, and the reason is that layer 2 is precisely the body of material a different project would need to clone in order to become operational.

### Layer 3 — Project content: belongs to one project

1. **Heading: "Layer 3 — Project content: belongs to one project"** — The third category is named "Project content," defined by being the property of exactly one project.

2. **"Issues, the wiki, seat briefs, drafts, design documents about this project, and the founding decisions."** — A fragment listing layer-3 members: issue records, wiki pages, seat briefs, draft documents, design documents whose subject is this particular project, and the recorded founding decisions.

3. **"Cheapest test: **would a different project want this file unchanged?**"** — The least-effort diagnostic for identifying layer 3 is to ask whether some other, unrelated project would have use for this file exactly as written, without modification.

4. **"If the answer needs a "well, it depends", it is project content."** — Decision rule for the test: the qualifying threshold is a clean yes. If answering the test question requires hedging or conditionalizing, that hesitation itself settles the classification as layer 3.

## The manifest

*(Section heading: "The manifest" — this section is the enumerated inventory applying the scheme to every current component.)*

1. **"Every component in the repository as of 2026-08-14, classified."** — A fragment stating the table's scope and cutoff date: it covers all components present in the repository on 14 August 2026, each assigned a layer.

2. **"Layer 3 entries are listed by directory rather than by file, since they are numerous and uniform."** — For layer-3 material, the table gives one row per directory instead of one row per file, because the files are both too many to list individually and consistent enough within a directory that a per-file listing would add nothing.

3. **Table header: "| Component | Layer | Cloud can reach it? |"** — Three columns: the component's identity (usually a path), its assigned layer, and an answer to whether a cloud session can access it.

4. **Row: "`scripts/session-statusline-command.py` | 1 — runtime | Only if in the cloned repository"** — The status-line script is layer 1; a cloud session can access it if and only if that file is part of the repository the cloud session cloned.

5. **Row: "`.claude/hooks/instruction-file-guard.py` | 1 — runtime | Only if in the cloned repository"** — The hook that guards instruction files is layer 1, with the same conditional cloud reachability.

6. **Row: "`.claude/hooks/backup-and-snapshot-write-guard.py` *(pending PR #58)* | 1 — runtime | Irrelevant: it guards machine-local paths"** — The hook guarding writes to backup and snapshot locations — which is not yet merged and is awaiting pull request #58 — is layer 1; the cloud-reachability question does not apply to it because its entire purpose concerns paths that exist only on a physical machine, so a cloud session would have nothing for it to guard.

7. **Row: "`scripts/handoff-context-threshold-hook.py` | 1 — runtime | Only if in the cloned repository"** — The hook that fires when a session's context reaches the handoff threshold is layer 1, reachable from the cloud only when included in the cloned repository.

8. **Row: "`.claude/skills/walk-me-through/` | 1 — runtime | Only if in the cloned repository"** — The walk-me-through skill directory is layer 1, with the same conditional cloud reachability.

9. **Row: "`.claude/skills/md-review/` | 1 — runtime | Only if in the cloned repository"** — The markdown-review skill directory is layer 1, same condition.

10. **Row: "`.claude/skills/handoff/` | 1 — runtime | Only if in the cloned repository"** — The handoff skill directory is layer 1, same condition.

11. **Row: "`.claude/skills/ghi-write/` | 1 — runtime | Only if in the cloned repository"** — The GitHub-issue-writing skill directory is layer 1, same condition.

12. **Row: "`scripts/handoff-supervisor.py` | 2 — tool | No: it manages machine-local sessions"** — The handoff supervisor is layer 2, and a cloud session cannot usefully reach it because what it operates on is sessions running locally on a machine, which the cloud cannot see.

13. **Row: "`scripts/handoff-write-and-check-supervisor.py` | 2 — tool | No: same"** — The supervisor that writes and then checks handoffs is layer 2, unreachable from the cloud for the identical reason as the preceding row (it manages machine-local sessions).

14. **Row: "`scripts/handoff-extract-conversation.py` | 2 — tool | No: reads machine-local transcripts"** — The script that extracts conversation content for a handoff is layer 2, unreachable-in-practice from the cloud because its input is transcript files stored only on a physical machine.

15. **Row: "`scripts/launch-claude-ubuntu`, `scripts/launch-claude-mac` | 2 — tool | No: they reach specific machines"** — The two launcher scripts (one targeting the Ubuntu box, one targeting the Mac) are both layer 2, and neither is usable from the cloud because each operates by connecting to a named physical machine.

16. **Row: "`scripts/md-review-grid.py` and its two cell runners | 2 — tool | Yes, if the runtimes it shells out to exist there"** — The markdown-review grid script together with the two subordinate programs that execute individual cells of the grid are layer 2; they are usable from the cloud conditionally — specifically, only if the external programs or interpreters the grid invokes as subprocesses are also present in the cloud environment. (I read "the runtimes it shells out to" as the executables/interpreters it launches as child processes.)

17. **Row: "`scripts/md-drift-lint.py` | 2 — tool | Yes"** — The documentation-drift linter is layer 2 and is fully usable from a cloud session, without qualification.

18. **Row: "`scripts/git-gatekeeper.py` | 2 — tool | Yes"** — The git-gatekeeper program is layer 2 and is usable from a cloud session.

19. **Row: "`scripts/backup-health-check.py` *(pending PR #58)* | 2 — tool | No: it reads machine-local backup state"** — The backup health-check script, not yet merged and awaiting pull request #58, is layer 2 and is not usable from the cloud because the data it inspects — the state of backups — exists only on a physical machine.

20. **Row: "`docs/cross-project/git-gatekeeper-design.md` | 2 — tool's design | Yes"** — The git-gatekeeper design document is classified under layer 2 with a sub-qualifier indicating it is the design document belonging to a layer-2 tool rather than the tool itself; it is reachable from the cloud.

21. **Row: "`docs/cross-project/fast-handoff-design.md` | 2 — tool's design | Yes"** — The design document for the fast-handoff mechanism is a layer-2 tool's design document and is cloud-reachable.

22. **Row: "`docs/cross-project/fleet-machine-paths-and-checkouts.md` | 2 — tool's design | Yes"** — The document describing machine paths and git checkouts across the fleet of machines is a layer-2 tool's design document and is cloud-reachable.

23. **Row: "`docs/cross-project/nc-python-toolchain-plan.md` | 2 — unverified, see below | Yes"** — The plan document for the "nc" Python toolchain is provisionally assigned to layer 2, but the assignment is flagged as unverified with a pointer to the explanation following the table; it is cloud-reachable.

24. **Row: "`docs/cross-project/nc-python-toolchain-target-architecture.md` | 2 — unverified, see below | Yes"** — The document describing the target architecture for the "nc" Python toolchain carries the same provisional layer-2 assignment, the same unverified flag, and is cloud-reachable.

25. **Row: "`docs/cross-project/comms-bridge-spec.md` | 2 — unverified, see below | Yes"** — The specification for the communications bridge carries the same provisional, unverified layer-2 assignment and is cloud-reachable.

26. **Row: "`docs/cross-project/seed-claude-md-draft.md` | 2 — unverified, see below | Yes"** — The draft of a seed/starter `CLAUDE.md` file carries the same provisional, unverified layer-2 assignment and is cloud-reachable.

27. **Row: "`docs/cross-project/nedschorus-founding-plan.md` | **3 — misfiled**, see below | Yes"** — The nedschorus founding plan is classified as layer 3 (project content), and its row is marked as a known misfiling because it currently sits in the cross-project directory; the explanation follows the table. It is cloud-reachable.

28. **Row: "`docs/agents/` — seat model and briefs | 3 — project content | Yes"** — The `docs/agents/` directory, which holds the model of agent seats and the briefs for those seats, is layer-3 project content and is cloud-reachable.

29. **Row: "`docs/issues/`, `docs/wiki/`, `docs/drafts/`, `docs/founding/` | 3 — project content | Yes"** — These four directories — issues, wiki, drafts, and founding material — are all layer-3 project content and all cloud-reachable.

30. **Row: "`md-review-records/` | 3 — project content | Yes"** — The directory holding records of past markdown reviews is layer-3 project content and is cloud-reachable.

31. **"**Four entries marked unverified** were classified from their filenames and their placement in `docs/cross-project/`, not from reading them."** — The four rows bearing the "unverified" flag received their layer assignment on the basis of two weak signals only — what the file is named, and the fact that it currently sits in the `docs/cross-project/` directory — because whoever produced the manifest did not open and read the files' contents.

32. **"Whoever next touches them should confirm or correct the row rather than inherit the guess."** — An instruction to the next person or agent who works on any of those four files: actively verify the classification and either affirm it or fix it in the table, instead of silently treating the unverified guess as established fact and carrying it forward.

33. **"**One entry is misfiled and has a ruled destination.**"** — Of all the rows, exactly one describes a file that is currently in the wrong place, and the correct place for it has already been decided by the user.

34. **"`docs/cross-project/nedschorus-founding-plan.md` moves to `docs/nedschorus-plan.md` and is retitled — its heading already reads "nedschorus Boot-Up Plan", so the file has disagreed with its own name for some time."** — The ruled action is to relocate that file to the path `docs/nedschorus-plan.md` (out of the cross-project directory, and with a changed filename) and also to change its title. The supporting observation: the document's internal heading already says "nedschorus Boot-Up Plan" rather than anything about a founding plan, so its filename and its heading have been inconsistent with each other for a considerable period. (I read "is retitled" as ambiguous between changing the in-document heading and changing the filename; given the filename change is stated separately, I take "retitled" to mean the heading text is to be brought into agreement — though the sentence does not say what the new title should be.)

35. **"The move was ruled 2026-08-14 and deliberately **not** executed at the time: 14 files cite it by path, one of them `.claude/skills/ghi-write/SKILL.md`, which is instruction-class and needs its own walked approval, and two more are being rewritten in an unmerged branch."** — The user decided on the move on 14 August 2026, but it was intentionally left unperformed in that same session, for stated reasons: fourteen other files refer to the document by its current path and would all need updating; one of those fourteen is the `ghi-write` skill file, which belongs to the category of files that instruct agents and therefore requires its own separate approval obtained through a walk-me-through before being edited; and two more of the fourteen citing files are currently undergoing rewriting on a branch that has not yet been merged.

36. **"It waits for that branch to land."** — The move is deferred until the unmerged branch mentioned in the previous sentence has been merged into main.

## The boundary: what was decided, and what is still open

*(Section heading: "The boundary: what was decided, and what is still open" — this section separates the settled rulings about the repository boundary from the questions still unanswered.)*

1. **"**Decided: the three-layer model above, and that the manifest is its operative half.**"** — Two things are settled: first, the three-layer classification scheme as described earlier in the document; second, the position that of the document's two components (the abstract model and the per-file table), the manifest is the part that actually does the work — the half with practical force.

2. **"A layer table with no per-file classification decides nothing, and a classification with no reasoning cannot be extended."** — The justification, given as two symmetrical failures: abstract layer definitions unaccompanied by concrete per-file assignments settle no actual question; and per-file assignments unaccompanied by the reasoning behind them cannot be applied to files not already listed.

3. **"They stay in one document for that reason."** — Because each half is deficient without the other, the model and the manifest are kept together in this single file rather than being split into separate documents.

4. **"**Decided: do not split the repository yet.**"** — A second settled ruling: the repository is not to be divided into separate repositories at this time. "Yet" indicates a deferral rather than a permanent rejection.

5. **"The case for splitting is real and got stronger during the walk that produced this document — a second project exists, and cloud sessions can only receive what a repository carries."** — The arguments favoring a split are genuine, not straw men, and they became more compelling over the course of the 14 August walk-through session; the two strengthening facts are that a second consumer project now exists, and that a cloud session's entire available material is limited to what its cloned repository contains.

6. **"But the case against is concrete and unresolved:"** — Nevertheless, the counterarguments are specific and tangible rather than vague, and none of them has been settled; they are enumerated in the list that follows.

7. **Item 1, first sentence: "**A split needs an install mechanism with a version check, built first.**"** — The first counterargument: splitting the repository presupposes that a way to install layer-1 artifacts, including a version-staleness check, already exists — and building that mechanism must precede the split rather than follow it.

8. **Item 1, second sentence: "Without it, the split reproduces exactly the failure the user predicted for the gatekeeper: fixes that are made but never deployed, chased in a loop."** — Absent such an install mechanism, splitting would recreate precisely the failure mode the user identified when ruling on the git-gatekeeper: corrections get written but never reach the copy actually running, and agents then pursue those already-fixed problems repeatedly without progress.

9. **Item 2, first sentence: "**A cloud session is bound to one repository.**"** — The second counterargument: a cloud session's access is tied to exactly one repository, with no ability to reach a second one.

10. **Item 2, second sentence: "If the machinery leaves this repository, a cloud session that cloned `nedschorus` can no longer see it, and a `--teleport` lands in the project checkout."** — Consequence of moving the shared tooling out: a cloud session that had cloned the `nedschorus` repository would lose all access to that tooling, and additionally, a `--teleport` operation from such a cloud session would place the user in a local checkout of the project repository — meaning the machinery would not be present there either. (I read "lands in the project checkout" as describing where the teleported session ends up, which would be the project repository's checkout rather than the machinery repository's.)

11. **Item 2, third sentence: "The cloud runtime is an argument *for* a shared repository and simultaneously a constraint *against* splitting the one a cloud session uses."** — The cloud runtime cuts both ways: it supports the idea of having one repository that carries everything (since only repository contents are reachable), while at the same time it forbids removing material from whichever repository the cloud session clones.

12. **Item 2, fourth sentence: "Whichever repository a cloud session clones is the one it gets."** — Restated as a flat rule: the single repository a cloud session clones fully determines its accessible material — there is no supplementing it with a second one.

13. **Item 3, first sentence: "**Two repositories mean two review-and-merge lanes**, and the project's whole change-control design is one door to main."** — The third counterargument: maintaining two repositories entails maintaining two separate processes for reviewing and merging changes, whereas the project's entire change-control architecture is deliberately built around a single controlled entry point into the main branch.

14. **Item 3, second sentence: "Splitting doubles the credential work that is already the blocking item for the git-gatekeeper."** — Because each repository requires its own credentials to be set up, splitting would double the amount of credential-related work — and that work is already the specific unfinished item preventing the git-gatekeeper from being activated.

15. **"The manifest is what makes the split cheap when it happens: the boundary is drawn and every file is classified, so the split becomes a mechanical operation against a list rather than an archaeology exercise."** — The manifest's value lies in reducing the future cost of a split: since the dividing criterion is written down and each file already has an assigned layer, executing the split later would consist of routinely processing an existing list, instead of having to reconstruct from scratch what each file is and where it belongs — the latter being what "archaeology" figuratively denotes here.

16. **"Deciding the classification while it is free is the point."** — The rationale for doing the classification work now: performing it at a moment when it costs nothing (because no split is underway and nothing is blocked on it) is exactly why it is being done now rather than later.

17. **"**Open, and the user's to answer: which account owns which repository.**"** — One question is explicitly left unresolved, and it is designated as the user's to decide rather than an agent's: the assignment of repository ownership to accounts — which identity should own which repository.

18. **"He works under two identities — `ned@lerner1.com` for the non-profit and `junk@lerner1.com` for personal — and a cloud session authenticated as one may not be able to read a repository owned by the other."** — The user maintains two separate accounts: `ned@lerner1.com` used for his non-profit work and `junk@lerner1.com` used for personal work. The complication is that a cloud session logged in under one of those identities might lack read access to a repository whose owner is the other identity. ("May not be able to" is stated as a possibility, not a confirmed fact.)

19. **"`nedschorus` currently lives under the `nedschorus` GitHub organisation and merges run as `NedLern`."** — Two present facts about the existing setup: the repository is hosted under a GitHub organization also named `nedschorus`, and merge operations are performed under the GitHub username `NedLern`.

20. **"Until this is answered, any split risks producing a repository that some of his own sessions cannot clone."** — So long as the ownership question remains undecided, carrying out a split carries the hazard of creating a repository that a subset of the user's own Claude sessions would be unable to clone because of an account mismatch.

21. **"**Answer it before splitting, not during.**"** — An instruction on sequencing: the ownership question must be resolved as a precondition of the split, rather than being worked out while the split is in progress.

## Filing rule

*(Section heading: "Filing rule" — this section gives the procedure for placing a new file.)*

1. **"For a new file, in order:"** — Introduces a decision procedure whose steps are to be applied in the sequence given, stopping at the first step that yields an answer.

2. **Step 1: "**Would a different project want this unchanged?** No → layer 3, this repository, under `docs/` or wherever its kind lives."** — First ask whether an unrelated project would want this file exactly as written. If the answer is no, the file is layer 3 and belongs in the current (`nedschorus`) repository, placed under `docs/` or, if it is a kind of thing with its own established home directory, in that directory instead.

3. **Step 2: "**Must it be loaded at session start to work?** Yes → layer 1. It lives in the repository today; when the split happens it becomes an installed artifact, and it needs the version stamp described above."** — If step 1 did not classify it, ask whether the file only functions if the harness loads it at session initialization. If yes, it is layer 1. Its present home is this repository, but should the repository split occur in future, it would instead become something installed into `~/.claude/`, and at that point it must carry the version marker and staleness check mandated in the layer-1 section.

4. **Step 3: "**Otherwise it is layer 2** — a tool, in `scripts/`, with its design document in `docs/cross-project/`."** — If neither of the first two tests classified the file, it falls through to layer 2 by default; as a tool it is placed in the `scripts/` directory, and the document describing its design is placed in `docs/cross-project/`.

5. **"When a file's layer is genuinely unclear, record the ambiguity in the manifest row rather than picking silently."** — In cases where the layer truly cannot be determined (as opposed to merely requiring thought), the correct action is to write the uncertainty into that file's row in the manifest table, instead of choosing a layer without disclosing that the choice was uncertain.

6. **"A wrong row that says it is uncertain is worth more than a confident one nobody can check."** — Justification: an entry that assigns the wrong layer but flags itself as uncertain has greater value than an entry stated with confidence whose correctness no subsequent reader has any way to verify — because the flagged one invites and enables correction.

