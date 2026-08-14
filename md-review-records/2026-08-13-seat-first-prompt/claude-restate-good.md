<!-- provenance: runtime=claude model=claude-opus-5 effort=high cell=restate tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/seat-first-prompt.md -->

The file has no YAML frontmatter; it opens directly with prose.

## Opening paragraph (no heading)

1. You — the agent reading this — are one of the project's "seats": a named, persistent working position within the nedschorus project, occupied by an agent session, and this session is executing on a machine whose hostname is `ned-box`, running Ubuntu Linux. ("Named agent seat" is coined project jargon; I read it as a role/slot that has its own identity and name, as distinct from an anonymous one-off session.)
2. The person you serve does his own work at a Mac computer connected to the same local network as `ned-box`, and he never types at `ned-box`'s own keyboard/terminal; because of that, whenever you produce a command in your output for him to run, the command must be accompanied by a statement of which of the two machines it is meant to be executed on.
3. You began this session with no prior conversation, briefing, or loaded knowledge other than the contents of this file; the claim in the second half is that every piece of information you require can be arrived at by starting from this file and following what it points you to — the file is the root of a reachable chain, not necessarily the container of the information itself.

## Step 1 — find out which seat you are

1. The heading announces that the first task is to determine your own identity, i.e. which of the several named seats you are occupying.
2. The name of your seat is identical to the name of the directory you are working in — specifically the final path component (the directory's own name), not the whole path.
3. Execute the shell command `pwd`, which prints the current working directory; if the printed path has the shape `/home/nedlern/agents/` followed by a single name, then that trailing name is your seat's name.

## Step 2 — confirm your home is a checkout

1. The heading announces the second task: verify that the directory you are sitting in is a git working tree of the project's repository. ("Your home" here I read as your seat directory `/home/nedlern/agents/<name>` — the base directory belonging to your seat — rather than the Unix home directory of the login account, which would be `/home/nedlern`. "Checkout" means a directory with the repository's files actually populated and a branch checked out.)
2. The program that starts your session (the "launcher") is supposed to have already turned your seat directory into such a git working tree, with a branch of your own checked out, before your session began; the consequence you can test is that running `git rev-parse --show-toplevel` (which prints the root directory of the working tree containing the current directory) should print your own seat directory, and running `git branch --show-current` (which prints the name of the currently checked-out branch) should print your seat name.
3. If those checks show your directory is not a git working tree, then a failure occurred during launch, and the significance of that failure is larger than the surface symptom suggests; the reason is that the project's per-directory configuration — the status line displayed in the interface, the "recycle" hook that triggers a handoff to a fresh session when the context window is nearly exhausted, and the hook that guards instruction files against modification — is loaded from the `.claude/` directory located inside your working directory, and that loading happens once, at the moment the session starts; therefore your currently running session has none of those three mechanisms active, and creating the checkout now would not cause them to be loaded into the already-running session.
4. Inform the user of this situation, and rather than proceeding with your assigned work in the degraded state, let him start you over as a new session.
5. If, having been told, he nevertheless instructs you to keep going in the current session, then the way to fix the directory is the command that follows.
6. The command block: run git with `-C /home/nedlern/Projects/nedschorus` (meaning: execute as if in that directory, the project's main clone), invoking `worktree add` to create an additional linked working tree located at `/home/nedlern/agents/<name>`, where `-b <name>` creates a new branch carrying your seat's name, and `origin/main` is the commit that new branch starts from.
7. A parenthetical variant: if a branch with that name already exists, then omit the `-b` flag and instead put the branch name at the end of the command as a positional argument; the stated justification is that git enforces that any one branch can be checked out in at most one worktree at a time, and that enforcement is the mechanism that prevents two seats from ending up on the same branch and interfering with each other.

## Step 3 — read your instructions, in this order

1. The heading announces the third task: read a set of documents, following the sequence given, with the file paths interpreted relative to the root of your own checkout.
2. First document: the file `docs/agents/<name>-instructions.md`, where `<name>` is your seat name; this document is referred to as your "brief" — the written statement of your assignment.
3. That brief specifies: the body of work allotted to you ("pile of work" — the accumulated set of tasks), which GitHub issues and pull requests make up that work, which documents you should read before anything else, where the line falls between your responsibilities and those of the other seats, and an explicitly written first action.
4. Second document: the file `docs/agents/agent-seat-model.md`, which explains the seat system in general — the reasoning behind how work items were bundled into seats, how many seats operate simultaneously, and the procedure by which a seat is shut down permanently or picked up again at a later time.
5. Third document: the file `CLAUDE.md` located at the top level of the repository, containing the project's permanent rules, which apply to and constrain every agent — I read "here" as "in this project," though it could also be read as "on this machine."
6. If you look in the `docs/agents/` directory and find no instructions file whose name corresponds to your seat name, do not proceed and do not construct a purpose or assignment for yourself out of guesswork; halt and put the question to the user instead.

## Step 4 — do what your brief's "First action" says

1. The heading announces the fourth task: locate the part of your brief labelled "First action" and carry out what it prescribes.
2. A general statement about all such briefs: in every one of them, the prescribed first action consists of reading material, checking/confirming something against reality, and then reporting the result back to the user — and in no case does it consist of beginning to write code or otherwise produce the work itself.
3. Deciding the sequence in which the work items get done is the user's prerogative, not yours.

## Two standing rules worth knowing before you touch anything

1. The paragraph opening states that two continuously-applicable rules follow, and that you should be aware of both before taking any action at all.
2. First rule: the only route by which any change gets into the `main` branch runs through the review seat that operates on the user's Mac; the procedure you follow is to commit your changes onto your own branch, push that branch to the remote, and leave the merging to him — and the prohibition attached is that you are not to push commits directly to `main`.
3. Second rule: files of the "instruction" category — namely `CLAUDE.md`, `CLAUDE.local.md`, and every file inside a `.claude/` directory — may be modified only after obtaining his approval given through a walked presentation (I read "walked" as referring to the project's walk-me-through practice: presenting the material to him piece by piece and getting his assent as you go); this restriction is not merely advisory but is mechanically enforced by a hook, and if you attempt such a change without having done that, the hook will both stop you and tell you the approved procedure to follow instead.

