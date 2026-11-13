---
status: reference
verified-as-of: 2026-08-13
---

# Fleet machine paths and checkouts

Where every working copy, agent-home, and handoff file lives on each machine of the nedschorus fleet, and which commands run where. Written because the fleet spans two machines that carry the same relative paths over different clones: on 2026-08-12 a `git pull` intended for the Ubuntu checkout ran on the Mac instead, leaving the box stale for hours while everyone believed it current. Naming the machine is not pedantry here; it is the difference between a command working and silently working somewhere else.

The user-level instruction file on the box (`/home/nedlern/.claude/CLAUDE.md`) carries the short form of this page's rule, that every command names the machine it runs on, for every session on ned-box; this document is the full map behind it.

## The two machines

The user works at a **Mac**. Most agent-sessions run on **`ned-box`**, an Ubuntu machine on the same LAN, reached as `ssh nedlern@ned-box`. Each machine has its own clone of nedschorus, its own Claude credentials, and its own agent state. Between the two clones only git branches cross, and only when pushed; worktrees, handoff files, locks, and credentials are per-machine. The Mac reaches files on ned-box only through the mount that § What the system needs in order to run describes.

The box is the default machine for agent work: more memory, CPU and bandwidth, and it does not compete with the machine the user is sitting at. The Mac runs agents only when the work needs to be where the user is — its browser session, its keychain, its GUI, or files that exist only there. Merges to `main` happen on ned-box, at the agent-seat merge-lane-2, which merges as `ned-review-merge`; branch protection lets only `ned-review-merge` and `nedlern` push to `main`.

## Three kinds of checkout, one repository

All checkouts of a machine's clone are git worktrees sharing one object store, each on its own branch or, for an agent-home, on a detached HEAD. **Git allows a branch to be checked out in only one worktree at a time**, unless `--force` overrides it, which is what keeps two agents in two worktrees from editing one branch's files: git refuses before they get the chance.

1. **The main checkout** — the machine's reference-checkout, parked on `main`, in which no agent works. The git client-side hooks of every checkout of the clone run from its `scripts/git-client-side-hooks/`, so a stale main checkout means stale git hooks; a session reads Claude Code's `.claude/` hooks and settings from its own checkout.
2. **Agent-homes** — one permanent directory per agent-seat, a worktree that holds no work and rests on a detached HEAD at `origin/main`. The launchers create it and make it a checkout with `git worktree add --detach` before the agent-seat's first agent-session starts.
3. **Task worktrees** — disposable, one per piece of work that edits files, each on its own branch: the topic-worktree an agent-session makes for its nc-topic-branch, or the worktree Claude Code makes when a subagent isolates itself. Their value leaves as pushed commits; `scripts/clean-worktrees.py` removes a worktree whose work is done, at each session-handoff and once a day.

## Ubuntu — `ned-box`, user `nedlern`

Verified 2026-09-14, every row checked on the box itself.

| What | Full path | Branch |
|---|---|---|
| Main checkout | `/home/nedlern/Projects/nedschorus` | `main` |
| Agent-homes | `/home/nedlern/agents/<name>` | detached at `origin/main` |
| Task worktrees | `/home/nedlern/Projects/nedschorus/.claude/worktrees/<name>` | per job |
| Handoff files | `/home/nedlern/.claude/handoffs/<agent>-handoff.md` | — |
| User-level instructions | `/home/nedlern/.claude/CLAUDE.md` | — |
| Auto-memory | `/home/nedlern/.claude/projects/-home-nedlern-Projects-nedschorus/memory/` | — |
| Legacy reference system | `/home/nedlern/Projects/nedlern` | **absent on this box** |

The legacy checkout's absence is expected and safe: the main-gatekeeper's `--import` machinery refuses `import-invalid` ("not a readable git repository") until one exists, which is a named refusal rather than a failure. Clone it only when an import is actually needed.

## Mac — user `el`

Verified 2026-09-14.

| What | Full path |
|---|---|
| Main checkout | `/Users/el/Projects/nedschorus` |
| Agent-homes | `/Users/el/agents/<name>` |
| Task worktrees | `/Users/el/Projects/nedschorus/.claude/worktrees/<name>` |
| Handoff files | `/Users/el/.claude/handoffs/<agent>-handoff.md` |
| User-level instructions | `/Users/el/.claude/CLAUDE.md` |
| Auto-memory | `/Users/el/.claude/projects/-Users-el-Projects-nedschorus/memory/` |
| Legacy reference system | `/Users/el/Projects/nedlern` |

Two naming notes that hold on both machines. A handoff file is `<agent>-handoff.md` for the current one and `<agent>-handoff-<NNNN>.md` for numbered earlier ones, with `<agent>-dialog-<NNNN>.md` beside them; the `<session-uuid>-handoff-asked` and `-handoff-deferred` files in the same directory are markers, not handoffs. A task worktree an agent-session makes is named for its nc-topic-branch, and one Claude Code makes for a subagent is named `agent-<id>` or `worktree-agent-<id>`.

## Commands, and the machine each runs on

| Goal | Type it on | Command |
|---|---|---|
| Reach a named agent on the box | Mac | `/Users/el/Projects/nedschorus/scripts/launch-claude-ubuntu <name>` |
| Run a named agent on the Mac | Mac | `/Users/el/Projects/nedschorus/scripts/launch-claude-mac <name>` |
| List agents running on a machine | Mac | run `/Users/el/Projects/nedschorus/scripts/launch-claude-ubuntu` (ned-box's agent-seats) or `/Users/el/Projects/nedschorus/scripts/launch-claude-mac` (the Mac's) with no name |
| See every checkout of this machine's clone and its branch | either | `git -C ~/Projects/nedschorus worktree list` |
| Update the box's main checkout | Mac | `ssh nedlern@ned-box 'git -C ~/Projects/nedschorus pull'` |
| Clear stale worktree registrations | either | `git -C ~/Projects/nedschorus worktree prune` |

Both launchers are attach-or-create: running a name that is already up attaches to that agent rather than starting a second copy. Within one machine, duplicate agents are prevented three ways — the launcher asks the agent-seat's own tmux socket and the default socket for a session of that name before creating one, the supervisor holds an exclusive per-agent `flock` on its lock file for its whole life (the kernel releases the lock when the supervisor dies, so the next supervisor claims the lock at once), and an agent's home directory is derived from its name rather than chosen. The first of those changed on 2026-08-21, when each agent-seat moved to its OWN tmux server (`tmux -L <name>`, one socket per agent-seat, after a single server's crash killed three Mac agent-seats at once). A session name is therefore no longer unique across the machine, only within one agent-seat's socket, so the launcher asks the agent-seat's own socket, and its no-name listing walks the whole socket directory rather than asking one server. Across machines no launcher state or lock is shared, so nothing stops the same name on both. But the name is also the agent-seat's address for cross-session messages and its directory in the log-store (`seats/<seat>/`), so two agent-seats with one name confuse a sender and overwrite each other's shared files. One name means one agent-seat across both machines (see `nedschorus-agent-seat-model.md`), and nothing enforces that across machines.

## What crosses between machines, and what does not

**Crosses:** git branches, once pushed, and through them every committed file. That is also a cross-machine collision surface — two clones pushing the same branch name fight over one remote ref, whatever the agent-seats are called; the other is one agent-seat name used on both machines, as § Commands, and the machine each runs on says.

**Does not cross:** worktrees and their directories, agent-homes, handoff files, supervisor locks, tmux sessions, Claude credentials (each machine authenticates separately), and uncommitted work in a checkout. A pull on one machine tells the other nothing.

**A consequence worth remembering:** pulling the main checkout does not update agent-homes or task worktrees, because each has its own HEAD: a task worktree sits on its own branch, and an agent-home on a detached HEAD. After a merge to `main`, the main checkout is fast-forwarded on its own: by each launcher at launch, and by `scripts/checkout-freshness-catch-up.py` at the turn boundaries of the machine's agent-sessions. `main` is never merged into an open pull request's branch: a pull request that conflicts with `main` is replaced by a new one cut from current `main`. For a conflicting branch with no open pull request, `scripts/branch-conflict-check.py` says how to clear the conflict; it answers rebase only when no remote branch holds any of the branch's commits, because this repository refuses every force-push; otherwise it answers a merge of `main` into the branch, or, when a remote branch holding those commits has an open pull request, that pull request's replacement. An agent sees the change because the handoff-supervisor fast-forwards a clean agent-home at launch and `scripts/checkout-freshness-catch-up.py` fast-forwards it at each turn boundary, `scripts/checkout-freshness-catch-up.py` rebases a never-pushed branch onto `origin/main` at a turn boundary when its tree is clean and the rebase meets no conflict, and new work starts on an nc-topic-branch cut from current `main`.

## What the system needs in order to run

Three things must hold. When one of them fails, an agent tells the user what failed, with the remedy the failing program gave if it gave one. Until the failure is fixed, the agent goes on with the work that does not need the failed part, and leaves the rest waiting; it does not find a way around the failure.

- **ned-box is up and reachable from the Mac as `ssh nedlern@ned-box`.** Most agent-seats run on ned-box, merge-lane-2 merges every pull request there, and the log-store, `/home/nedlern/nedschorus-logs/`, lives there. A Mac agent that cannot reach ned-box can still edit and commit on the Mac, but it cannot have work reviewed or merged, and it cannot write to the log-store or read from it.
- **`claude` on ned-box is logged in.** Every agent-seat on ned-box, and every program that starts a Claude agent there, such as a cold-read or ghi-guide-agent, runs as that login. When it is logged out, nothing on ned-box can start a Claude agent, and only the user can log it back in.
- **The Mac has ned-box's home directory mounted at `/Volumes/nedhome`.** The mount is how the user opens a file on ned-box from the Mac, through a `file:///Volumes/nedhome/...` link an agent gives him. The Mac's copy of `.claude/guard-hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook.py` also writes its backups into the log-store through it. Without the mount, those links do not open and the Mac's backups are not written; the hook says so when it runs. To link a ned-box file for the user, replace `/home/nedlern/` with `file:///Volumes/nedhome/` in a markdown link; if he reports the file cannot be found, have him click `smb://ned-box.local/nedhome`, the share's root, to remount it.

What each machine does is in § The two machines, above.
