<!-- provenance: runtime=claude model=claude-sonnet-5 effort=high cell=restate tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/cross-project/fleet-machine-paths-and-checkouts.md -->

# Frontmatter

Both fields (`status: reference`, `verified-as-of: 2026-08-13`) are data fields (a category value and a date) — skipped per instructions.

# Introduction (untitled lead paragraph)

1. This document describes, for each machine in the nedschorus fleet, the filesystem location of every working copy of the code, every agent's home directory, and every handoff file, and it also specifies which machine each command should be executed on.
2. This document was written because the fleet consists of two machines whose repository clones use identical relative directory paths despite being separate, independent clones; as a result, on August 12, 2026, a `git pull` intended for the Ubuntu checkout was instead run on the Mac's checkout, so the Ubuntu machine ("the box") did not get updated and stayed out of date for hours while everyone believed it was current.
3. Explicitly naming which machine a command applies to is not unnecessary fussiness in this context — omitting it can mean the difference between a command having its intended effect versus executing without error but silently affecting the wrong machine, with no visible indication anything went wrong.

4. The instruction file that applies at the user level on ned-box, located at `/home/nedlern/.claude/CLAUDE.md`, contains an abbreviated version of this machine-naming rule that is in effect for every session; this document is the complete, detailed reference underlying that abbreviated rule.

# The two machines

1. The user performs their work while physically sitting at a Mac computer.
2. Claude agent sessions execute on a separate machine called ned-box, which runs Ubuntu and sits on the same local network as the Mac; it is accessed via the SSH command `ssh nedlern@ned-box`.
3. The Mac and ned-box each maintain their own separate, independent clone of the nedschorus repository, their own separate set of Claude credentials, and their own separate record of agent state.
4. The only thing shared between the two machines is git branches, and only at the moment they're pushed to a shared remote; by contrast, worktrees, handoff files, locks, and credentials each exist independently per machine and are never copied or moved between them.
5. Ned-box is where agent work happens by default, for two reasons: it has more memory, CPU, and bandwidth, and running work there doesn't consume resources on the machine the user is actively using.
6. Agents run on the Mac only when a task specifically needs something that exists only there: its browser session, its keychain (credential store), its GUI, or files present only on that machine.
7. The Mac additionally serves as the review-and-merge location: because branch protection permits merges only from the GitHub account "NedLern," and that account is used from the Mac, merges into `main` happen from the Mac.

# Three kinds of checkout, one repository

1. On any given machine, every working copy is actually a view of the same single underlying git repository at different branches, sharing one git object store (the database of commits, trees, and blobs) through the git worktree mechanism.
2. Git's built-in rule that a branch may be checked out in only one worktree at a time is the mechanism preventing two agents working in parallel from both editing the same branch's files simultaneously — git refuses the second checkout attempt outright, stopping the conflict before it could happen rather than needing to reconcile it afterward.
3. The first kind, "the main checkout," is the machine's primary/default working copy, kept checked out on the `main` branch.
4. `git pull` updates specifically this main checkout, and a running session reads from this main checkout to get the currently active `.claude/` configuration (hooks, settings).
5. When the main checkout is out of date, the hooks it provides are correspondingly out of date; this is how a bug in the "instruction-file guard" related to worktrees continued to affect things for a full day after it had already been fixed, because the fix hadn't yet reached the stale main checkout.
6. The second kind, "agent homes," gives each named long-lived agent one permanent (non-disposable) directory, checked out on a branch belonging specifically to that agent.
7. These directories are first created by the launcher scripts as plain (non-git) directories, and only deliberately converted into an actual git checkout via `git worktree add` once the agent begins working on the repository.
8. The third kind, "task worktrees," are disposable: one is created per background job that needs to edit files, each on its own branch, created by the harness when a session isolates its work, and removed when that job finishes.
9. Whatever value a task worktree produces is preserved by pushing its commits elsewhere; once that's done, the leftover directory itself has no further value and is just clutter.

# Ubuntu — `ned-box`, user `nedlern`

1. The contents of the table that follows were confirmed accurate as of August 13, 2026.
2. (Table rows of paths and branch names are data fields — skipped.)
3. The legacy checkout not existing on this box is expected and not a problem: the git-gatekeeper's `--import` functionality will decline to proceed — returning a specific status called `import-invalid` with the message "not a readable git repository" — until such a checkout exists, and this decline is treated as a deliberate, recognized refusal condition rather than an unexpected failure.
4. A clone of the legacy repository should be created on this machine only at the point an import operation actually needs to happen, not ahead of time.

# Mac — user `el`

1. The specific path used for the Mac's main checkout is fixed by a test within the repository itself (`scripts/handoff-extract-conversation-test.py`, which depends on that path); the other paths in the table below are inferred from following the same naming conventions used elsewhere, but have not actually been verified by checking from the box — i.e., they're assumed correct by convention rather than confirmed.
2. (Table rows of paths are data fields — skipped.)

# Commands, and the machine each runs on

1. To reach/connect to a specific named agent running on ned-box, the command should be typed on the Mac: `launch-claude-ubuntu` followed by the agent's name, at the given path.
2. To start a specific named agent on the Mac itself, the command should be typed on the Mac: `launch-claude-mac` followed by the agent's name, at the given path.
3. To list the agents currently running on a given machine, the command can be typed on either machine, by running that machine's matching launcher script with no agent name supplied.
4. To see every checkout that exists and which branch each is on, the command `git -C ~/Projects/nedschorus worktree list` can be typed on either machine.
5. To bring ned-box's main checkout up to date, the command should be typed on the Mac; it works by using SSH to remotely run `git -C ~/Projects/nedschorus pull` on ned-box.
6. To remove outdated worktree records that git still has registered but that no longer correspond to real worktrees, the command `git -C ~/Projects/nedschorus worktree prune` can be typed on either machine.
7. Both launcher scripts behave the same way — attach-or-create: running one with the name of an agent that's already up connects you to that existing agent rather than starting a duplicate.
8. On a single machine, three independent mechanisms each make duplicate same-named agents impossible: tmux connects to sessions by matching session name (so a duplicate name reattaches rather than creating a new session); a supervising process holds a lock exclusive to each individual agent, which is automatically reclaimed if the process holding it dies; and each agent's home directory path is computed from its name rather than freely chosen, so two same-named agents would necessarily map to the same directory.
9. Because nothing is shared between the two machines, giving an agent the same name on both creates no actual conflict — they are simply two unrelated agents that happen to share a name; the only downside is that a listing combining agents from both machines would not let you visually tell the two apart by name.
10. Adding a suffix like `-mac` or `-ubuntu` to a name is one way to make same-named agents on different machines distinguishable at a glance, but doing so is optional and not enforced by the system.

# What crosses between machines, and what does not

1. What transfers between the Mac and ned-box is git branches — but only once pushed to a shared remote — and, as a result, every file committed to those branches effectively transfers too.
2. This pushing of branches is also the one genuine point of conflict between the machines: if two clones (one per machine) push to a branch with the same name, they contend over the same single remote reference, regardless of what the agents involved are named.
3. The following do not transfer between the machines: git worktrees and their directories, agent home directories, handoff files, the supervisor's locks, tmux sessions, and Claude credentials (each machine must authenticate to Claude independently), plus anything that hasn't been committed to git.
4. Running `git pull` on one machine has no effect on and communicates nothing to the other machine.
5. One consequence worth remembering is that pulling the main checkout does not update the agent-home or task-worktree checkouts, because each of those sits on a different branch than `main`.
6. After a change is merged into `main`, the main checkout must itself be separately updated with its own `git pull`; and for a long-lived agent working on its own persistent branch, `main` must be merged into that branch before that agent can see the merged change.

