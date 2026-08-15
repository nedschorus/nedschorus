<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=restate tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/cross-project/fleet-machine-paths-and-checkouts.md -->

# Fleet machine paths and checkouts

1. This document identifies where each working checkout, persistent agent directory, and handoff file is located on every computer in the nedschorus group of machines, and it identifies which computer should execute each relevant command.
2. The document exists because the two machines have separate repository clones whose directory structures look alike when expressed as relative paths; on August 12, 2026, someone intended to update the Ubuntu clone with `git pull` but accidentally ran that command in the Mac clone, so the Ubuntu machine remained outdated for several hours while people mistakenly thought it had been updated.
3. Explicitly identifying the target machine is operationally necessary, because an otherwise valid command may succeed against the wrong machine or checkout without making the intended change.
4. The Ubuntu box’s user-wide instruction file, `/home/nedlern/.claude/CLAUDE.md`, gives every session a condensed version of this machine-identification rule; the present document supplies the detailed location map supporting that shorter rule.

## The two machines

1. The human user normally works directly at a Mac.
2. Agent sessions normally execute on an Ubuntu computer named `ned-box`, which is reachable over the local network with the SSH destination `nedlern@ned-box`.
3. The Mac and `ned-box` each have a separate clone of the nedschorus repository, separate Claude authentication credentials, and separate locally stored agent state.
4. The only material transferred between the machines is work represented by Git branches, and even those branches become available across machines only after they are pushed; worktree directories, handoff files, locks, and credentials remain local to the machine on which they were created.
5. `ned-box` is the normal machine for agent work because it has more memory, processing capacity, and network bandwidth, and using it avoids consuming resources on the Mac where the user is working.
6. Agents run on the Mac only when their work depends on Mac-local resources, such as the user’s active browser session, the Mac keychain, graphical applications, or files found only on that machine.
7. The Mac is also where review and merging are performed: branch-protection rules permit only the identity named `NedLern` to perform the relevant protected operation, and consequently merges into `main` are carried out from the Mac.

## Three kinds of checkout, one repository

1. The working directories on any one machine are checkouts of the same repository at different branches, and Git worktrees allow those directories to share that clone’s single object database instead of maintaining independent copies of all repository objects.
2. Within one clone’s worktree arrangement, Git will not allow the same branch to be checked out simultaneously in two worktrees; this prevents parallel agents from obtaining separate worktrees in which they could both edit that one branch, because Git rejects the second checkout first. This restriction is local to a clone’s worktrees, not a prohibition against the same branch existing in the independent clones on both machines.
3. The “main checkout” is the machine’s primary repository working directory, and it is normally left checked out at the `main` branch.
4. A `git pull` directed at this checkout updates it, and sessions use this checkout’s current `.claude/` files—such as hooks and settings—as the active operational machinery.
5. If the main checkout is outdated, the hooks used from it are also outdated; this allowed a worktree-related bug in the instruction-file guard to remain active for another day even though a fix existed elsewhere.
6. An “agent home” is a permanent directory assigned to one named, long-lived agent, with that agent using its own branch.
7. A launcher initially creates an agent home as an ordinary directory; when the agent needs to work on this repository, the directory is intentionally turned into a repository checkout using `git worktree add`.
8. A “task worktree” is a disposable checkout created for one background file-editing job, with each such checkout using its own branch.
9. The harness creates that worktree when a session puts its work into an isolated checkout, and the harness removes it when the job finishes.
10. The durable result of a task worktree is contained in the commits pushed from it; after that, the directory itself has no continuing value and may be treated as disposable residue.

## Ubuntu — `ned-box`, user `nedlern`

1. The information in this section was checked for accuracy on August 13, 2026.
2. The main checkout on `ned-box` is `/home/nedlern/Projects/nedschorus`, and it uses the `main` branch.
3. The specially identified agent home described as “the founding seat” is `/home/nedlern/agents/choirmaster`, and it uses the `choirmaster` branch. The document does not further define what historical or functional significance “founding seat” has.
4. In general, an agent named `<name>` has the home directory `/home/nedlern/agents/<name>` and has a branch assigned per agent; the table does not specify whether every branch must literally have the same text as the agent’s name.
5. Task worktrees are stored at `/home/nedlern/Projects/nedschorus/.claude/worktrees/<name>`, with a separate branch assigned per job.
6. An agent named `<agent>` has its handoff file at `/home/nedlern/.claude/handoffs/<agent>-handoff.md`; the branch column is inapplicable because this row describes a file location rather than a checkout.
7. User-wide instructions are stored at `/home/nedlern/.claude/CLAUDE.md`; no Git branch is assigned to that location in the table.
8. Automatically maintained memory is stored under `/home/nedlern/.claude/projects/-home-nedlern-Projects-nedschorus/memory/`; the document does not further describe the memory format or contents.
9. The legacy reference repository would be located at `/home/nedlern/Projects/nedlern`, but no such checkout currently exists on `ned-box`.
10. The missing legacy checkout is intentional and is not considered unsafe: when the git-gatekeeper’s `--import` function has no readable Git repository at that location, it produces the specifically classified refusal `import-invalid` with the explanation “not a readable git repository,” rather than treating the condition as an unexpected malfunction.
11. The legacy repository should be cloned onto the box only when someone actually needs to perform an import from it.

## Mac — user `el`

1. The repository’s own test file, `scripts/handoff-extract-conversation-test.py`, fixes or encodes the Mac checkout path as an expected path; the other paths in this section are inferred from the same directory conventions and were not directly inspected from `ned-box`.
2. The Mac’s main checkout is `/Users/el/Projects/nedschorus`.
3. A Mac agent named `<name>` has the home directory `/Users/el/agents/<name>`.
4. A Mac task worktree named `<name>` is located at `/Users/el/Projects/nedschorus/.claude/worktrees/<name>`.
5. The handoff file for a Mac agent named `<agent>` is `/Users/el/.claude/handoffs/<agent>-handoff.md`.

## Commands, and the machine each runs on

1. To reach or launch a named agent on `ned-box`, type `/Users/el/Projects/nedschorus/scripts/launch-claude-ubuntu <name>` on the Mac, replacing `<name>` with the agent’s name.
2. To run a named agent locally on the Mac, type `/Users/el/Projects/nedschorus/scripts/launch-claude-mac <name>` on the Mac.
3. To list the agents running on either machine, run the launcher corresponding to that machine without supplying an agent name.
4. To list all worktree checkouts belonging to the local nedschorus clone and show their branches, run `git -C ~/Projects/nedschorus worktree list` on the machine whose checkouts you want to inspect; `~` therefore refers to that machine’s current user home directory.
5. To update `ned-box`’s main checkout while operating from the Mac, run `ssh nedlern@ned-box 'git -C ~/Projects/nedschorus pull'`; the command connects to `ned-box` and executes the pull inside the Ubuntu user’s repository path.
6. To remove obsolete worktree registrations from the local clone’s Git metadata, run `git -C ~/Projects/nedschorus worktree prune` on the affected machine.
7. Both launcher programs follow an “attach-or-create” behavior: if the requested named agent is already running, the launcher connects to that existing agent instead of launching another instance with the same name.
8. Three mechanisms prevent duplicate agents with the same name on one machine: tmux identifies and reuses a session by its name; the supervisor holds a mutually exclusive lock for each agent and can reclaim it when the prior lock holder has died; and the agent’s home path is deterministically constructed from the agent name instead of being independently selected.
9. The two machines do not share this runtime state, so an agent with the same name may run independently on both; the phrase “no conflict” here means no conflict between their local tmux sessions, locks, homes, or runtime identities, while the shared label may make the two agents indistinguishable in a combined listing. It does not negate the later warning that both clones can contend if they push the same remote branch name.
10. If visual distinction is desired, names may be given suffixes such as `-mac` or `-ubuntu`, but the system does not require those suffixes.

## What crosses between machines, and what does not

1. Git branches cross between the machines after being pushed, and those branches carry every file included in their commits; unpushed branch state is not being described as transferred.
2. The meaningful place where work from the two machines can collide is the shared remote Git reference: if both independent clones push a branch with the same name, both pushes target that one remote branch reference regardless of the local agents’ names. “Fight” means the updates contend for that reference; the sentence does not specify exactly which Git rejection, reconciliation, or overwrite behavior will result in every case.
3. Worktree registrations and directories, agent-home directories, handoff files, supervisor locks, tmux sessions, Claude credentials, and all uncommitted changes do not transfer between the machines; each machine also authenticates to Claude independently.
4. Pulling repository changes on one machine does not communicate anything to, or update any checkout on, the other machine.
5. Pulling a machine’s main checkout does not update that machine’s agent homes or task worktrees, because those other checkouts are on separate branches.
6. After changes have been merged into `main`, each machine’s relevant main checkout must be pulled separately, and `main` must also be merged into every long-lived agent branch that needs those changes before the corresponding agent can see them.
