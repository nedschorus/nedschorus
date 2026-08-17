---
status: reference
verified-as-of: 2026-08-13
---

# Fleet machine paths and checkouts

Where every working copy, agent home, and handoff file lives on each machine of the nedschorus fleet, and which commands run where. Written because the fleet spans two machines that carry the same relative paths over different clones: on 2026-08-12 a `git pull` intended for the Ubuntu checkout ran on the Mac instead, leaving the box stale for hours while everyone believed it current. Naming the machine is not pedantry here; it is the difference between a command working and silently working somewhere else.

The user-level instruction file on the box (`/home/nedlern/.claude/CLAUDE.md`) carries the short form of this rule for every session; this document is the full map behind it.

## The two machines

The user works at a **Mac**. Agent sessions run on **`ned-box`**, an Ubuntu machine on the same LAN, reached as `ssh nedlern@ned-box`. Each machine has its own clone of nedschorus, its own Claude credentials, and its own agent state. Nothing but git branches crosses between them, and only when pushed — worktrees, handoff files, locks, and credentials are per-machine and never travel.

The box is the default home for agent work: more memory, CPU and bandwidth, and it does not compete with the machine the user is sitting at. The Mac runs agents only when the work needs to be where the user is — its browser session, its keychain, its GUI, or files that exist only there. The Mac is also the review-and-merge seat: branch protection admits only `NedLern`, so merges to `main` happen from the Mac.

## Three kinds of checkout, one repository

All working copies on a machine are the same repository viewed at different branches, sharing one object store through git worktrees. **Git allows a branch to be checked out in only one worktree at a time**, which is the mechanism that keeps parallel agents from editing one branch's files: git refuses before they get the chance.

1. **The main checkout** — the machine's primary working copy, parked on `main`. This is what `git pull` updates, and what a session reads for the live `.claude/` machinery (hooks, settings). A stale main checkout means stale hooks, which is how the instruction-file guard's worktree bug outlived its fix by a day.
2. **Agent homes** — one permanent directory per named long-lived agent, each on that agent's own branch. Created by the launchers (as a plain directory) and made a checkout deliberately with `git worktree add` when the agent works on the repository.
3. **Task worktrees** — disposable, one per background job that edits files, each on its own branch, created by the harness when a session isolates itself and removed when the job ends. Their value leaves as pushed commits; the directory afterwards is litter.

## Ubuntu — `ned-box`, user `nedlern`

Verified 2026-08-13.

| What | Full path | Branch |
|---|---|---|
| Main checkout | `/home/nedlern/Projects/nedschorus` | `main` |
| Agent home — the founding seat | `/home/nedlern/agents/choirmaster` | `choirmaster` |
| Agent homes — general | `/home/nedlern/agents/<name>` | per agent |
| Task worktrees | `/home/nedlern/Projects/nedschorus/.claude/worktrees/<name>` | per job |
| Handoff files | `/home/nedlern/.claude/handoffs/<agent>-handoff.md` | — |
| User-level instructions | `/home/nedlern/.claude/CLAUDE.md` | — |
| Auto-memory | `/home/nedlern/.claude/projects/-home-nedlern-Projects-nedschorus/memory/` | — |
| Legacy reference system | `/home/nedlern/Projects/nedlern` | **absent on this box** |

The legacy checkout's absence is expected and safe: the git-gatekeeper's `--import` machinery refuses `import-invalid` ("not a readable git repository") until one exists, which is a named refusal rather than a failure. Clone it only when an import is actually needed.

## Mac — user `el`

The checkout path is pinned by the repository's own tests (`scripts/handoff-extract-conversation-test.py`); the remaining rows follow the same conventions and have not been inspected from the box.

| What | Full path |
|---|---|
| Main checkout | `/Users/el/Projects/nedschorus` |
| Agent homes | `/Users/el/agents/<name>` |
| Task worktrees | `/Users/el/Projects/nedschorus/.claude/worktrees/<name>` |
| Handoff files | `/Users/el/.claude/handoffs/<agent>-handoff.md` |

## Commands, and the machine each runs on

| Goal | Type it on | Command |
|---|---|---|
| Reach a named agent on the box | Mac | `/Users/el/Projects/nedschorus/scripts/launch-claude-ubuntu <name>` |
| Run a named agent on the Mac | Mac | `/Users/el/Projects/nedschorus/scripts/launch-claude-mac <name>` |
| List agents running on a machine | either | run the matching launcher with no name |
| See every checkout and its branch | either | `git -C ~/Projects/nedschorus worktree list` |
| Update the box's main checkout | Mac | `ssh nedlern@ned-box 'git -C ~/Projects/nedschorus pull'` |
| Clear stale worktree registrations | either | `git -C ~/Projects/nedschorus worktree prune` |

Both launchers are attach-or-create: running a name that is already up attaches to that agent rather than starting a second copy. Within one machine, duplicate agents are impossible three ways — tmux attaches by session name, the supervisor holds an exclusive per-agent lock (reclaimed if its holder died), and an agent's home directory is derived from its name rather than chosen. Across machines nothing is shared, so the same name on both is simply two unrelated agents: no conflict, only a label that cannot be told apart in a listing spanning both. Suffix names (`-mac`, `-ubuntu`) if you want them distinguishable at a glance; nothing requires it.

## What crosses between machines, and what does not

**Crosses:** git branches, once pushed, and through them every committed file. That is also the one real cross-machine collision surface — two clones pushing the same branch name fight over one remote ref, whatever the agents are called.

**Does not cross:** worktrees and their directories, agent homes, handoff files, supervisor locks, tmux sessions, Claude credentials (each machine authenticates separately), and anything uncommitted. A pull on one machine tells the other nothing.

**A consequence worth remembering:** pulling the main checkout does not update agent homes or task worktrees, because each sits on its own branch. After a merge to `main`, the main checkout needs its own pull, and any long-lived agent branch needs `main` merged into it before that agent sees the change.
