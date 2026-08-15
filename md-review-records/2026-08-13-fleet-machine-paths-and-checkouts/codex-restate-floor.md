<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=restate tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/cross-project/fleet-machine-paths-and-checkouts.md -->

## Fleet machine paths and checkouts

1. This document maps where each working copy, agent home, and handoff file is located on every nedschorus fleet machine, and specifies which commands belong on which machine.

2. It exists because the fleet uses two machines with separate clones that expose the same relative paths; on August 12, 2026, a `git pull` meant for Ubuntu was accidentally run on the Mac, leaving the box outdated for hours while people thought it was current.

3. Identifying the machine is operationally essential, because otherwise a command may run successfully on the wrong machine without making the mistake obvious.

4. The user-level instruction file at `/home/nedlern/.claude/CLAUDE.md` gives every session the abbreviated version of this machine-identification rule.

5. This document provides the complete directory and command map underlying that abbreviated rule.

## The two machines

1. The user works on a Mac.

2. Agent sessions run on an Ubuntu machine named `ned-box`, which is on the same local network and can be reached with `ssh nedlern@ned-box`.

3. Each machine has its own nedschorus clone, Claude authentication credentials, and agent-related state.

4. The only thing that crosses from one machine to the other is git branch information, and even that crosses only after it has been pushed.

5. `ned-box` is the normal place for agent work because it has more memory, processing power, and network bandwidth, and its work does not compete with the computer the user is actively using.

6. Agents run on the Mac only when the task depends on resources local to the Mac, such as its browser session, keychain, graphical interface, or files that are not present elsewhere.

7. The Mac is also the place where changes are reviewed and merged because branch protection allows only `NedLern` to perform merges into `main`.

## Three kinds of checkout, one repository

1. On any one machine, all working copies belong to the same repository but represent different branches, and git worktrees let them share one underlying object store.

2. Git prevents a branch from being checked out in more than one worktree at once, so parallel agents cannot edit files from the same branch simultaneously; git rejects the second checkout before editing can begin.

3. The main checkout is the machine’s primary working directory, and it remains checked out on `main`.

4. `git pull` updates the main checkout, and sessions use that checkout to read the currently available `.claude/` components such as hooks and settings.

5. If the main checkout is outdated, its hooks are outdated too; this caused the instruction-file guard’s worktree-related bug to remain unfixed in practice for an additional day even though a fix existed elsewhere.

6. Agent homes are permanent directories assigned one per named, long-lived agent, with each home associated with that agent’s own branch.

7. The launchers create agent homes initially as ordinary directories, and when an agent needs to work on the repository, the directory is intentionally turned into a checkout with `git worktree add`.

8. Task worktrees are temporary worktrees, one for each background job that edits files; each uses its own branch, is created by the harness when a session needs isolation, and is deleted when the job finishes.

9. The lasting output of a task worktree is its pushed commits; once the job ends, the remaining directory is treated as disposable clutter.

## Ubuntu — `ned-box`, user `nedlern`

1. The Ubuntu machine’s main nedschorus checkout is `/home/nedlern/Projects/nedschorus`, and it is on the `main` branch.

2. The founding agent’s permanent home is `/home/nedlern/agents/choirmaster`, and it is on the `choirmaster` branch.

3. General agent homes are located at `/home/nedlern/agents/<name>`, with the branch determined separately for each agent.

4. Task worktrees are located at `/home/nedlern/Projects/nedschorus/.claude/worktrees/<name>`, with the branch determined separately for each job.

5. An agent’s handoff file is `/home/nedlern/.claude/handoffs/<agent>-handoff.md`; the table does not associate it with a branch.

6. The user-level instruction file is `/home/nedlern/.claude/CLAUDE.md`; the table does not associate it with a branch.

7. Automatically saved memory is stored under `/home/nedlern/.claude/projects/-home-nedlern-Projects-nedschorus/memory/`; the table does not associate it with a branch.

8. The legacy reference checkout would be `/home/nedlern/Projects/nedlern`, but that checkout is not present on `ned-box`.

9. The missing legacy checkout is intentional and harmless: the git-gatekeeper’s `--import` mechanism responds to an attempted import with `import-invalid` and the message “not a readable git repository” until that checkout exists, and this response is classified as an explicit refusal rather than a system failure.

10. The legacy checkout should be cloned only if an import operation actually requires it.

## Mac — user `el`

1. The repository’s tests, specifically `scripts/handoff-extract-conversation-test.py`, establish the Mac checkout path; the other Mac paths in the table are inferred from the same conventions and have not been checked directly from the Ubuntu machine.

2. The Mac’s main checkout is `/Users/el/Projects/nedschorus`.

3. Mac agent homes are located at `/Users/el/agents/<name>`.

4. Mac task worktrees are located at `/Users/el/Projects/nedschorus/.claude/worktrees/<name>`.

5. Mac handoff files are located at `/Users/el/.claude/handoffs/<agent>-handoff.md`.

## Commands, and the machine each runs on

1. To reach a named agent running on `ned-box`, type `/Users/el/Projects/nedschorus/scripts/launch-claude-ubuntu <name>` on the Mac.

2. To start or reach a named agent running on the Mac, type `/Users/el/Projects/nedschorus/scripts/launch-claude-mac <name>` on the Mac.

3. To list agents running on a machine, run that machine’s corresponding launcher without providing an agent name.

4. To display every checkout and the branch checked out in each one, run `git -C ~/Projects/nedschorus worktree list` on either machine.

5. To update the Ubuntu machine’s main checkout from the Mac, run `ssh nedlern@ned-box 'git -C ~/Projects/nedschorus pull'` on the Mac.

6. To remove obsolete git worktree registrations, run `git -C ~/Projects/nedschorus worktree prune` on either machine.

7. Both launchers either attach to an already running agent or create one; invoking a name that is already active connects to that existing agent instead of launching a duplicate.

8. On a single machine, three independent mechanisms prevent duplicate agents: tmux reuses the session identified by the agent name, the supervisor maintains an exclusive lock for that agent and can reclaim it if its owner has died, and the agent’s home directory is generated from the name instead of being freely chosen.

9. Because the two machines do not share runtime state, the same agent name can run on both machines as two unrelated agents; this is not a conflict, although a combined listing of both machines cannot distinguish them by name alone.

10. Adding suffixes such as `-mac` or `-ubuntu` makes agents from the two machines visually distinguishable in listings.

11. Such suffixes are optional; no system rule requires them.

## What crosses between machines, and what does not

1. The items that cross machines are git branches after they are pushed, and every committed file crosses as part of the commits those branches point to.

2. This branch exchange is the only meaningful cross-machine collision point: if two clones push the same branch name, they contend for the same remote reference regardless of the agents’ names.

3. The things that do not cross machines are worktrees and their directories, agent homes, handoff files, supervisor locks, tmux sessions, Claude credentials, and uncommitted changes.

4. Each machine authenticates to Claude separately, so credentials remain local to that machine.

5. Pulling on one machine gives the other machine no information and does not change its state.

6. Pulling the main checkout does not update agent homes or task worktrees because those directories are checked out on their own branches.

7. After `main` is merged, the main checkout must separately pull the updated branch, and each long-lived agent branch must separately merge `main` before that agent can see the merged changes.
