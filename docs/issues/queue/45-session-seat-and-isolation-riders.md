# Session seat and isolation riders

Queued for [nedschorus#45](https://github.com/nedschorus/nedschorus/issues/45) (named agents, launch and reattach). Raised in conversation 2026-08-13 while untangling why several sessions on the box were hard to tell apart and one had forked into another's checkout. Each item below was discussed and left undone deliberately — none is in flight.

## 1. A guard that enforces one live session per directory

**The invariant:** two live sessions must never share a working directory. Forks are the common road to breaking it — a fork inherits the parent's directory along with its conversation — and a background job launched from a session inherits the same cwd, which is what made several jobs look like duplicates in `~/agents/choirmaster`.

**The proposal:** a PreToolUse hook on `Edit|Write` that refuses when another live Claude process shares this session's working directory, teaching the fix — "another session is live here; call `EnterWorktree` first". Reads and searches stay unblocked; they never collide. **Detection is the open problem, and the obvious method does not work.** A `/proc` scan comparing each Claude process's `cwd` was the first proposal; it was tried 2026-08-13 and found unreliable — an *attached* background session's process reports the directory the `claude attach` command was typed in, not the directory the session actually works in, so real duplicates hide and viewer windows masquerade as sessions. A working detector needs the session's own view of its working directory (its transcript records it, and the session itself answers correctly when asked), not the process table. Resolve this before building the hook: a guard whose detection is wrong is worse than none, because it teaches the wrong lesson at the wrong moment.

**Why this shape:** `EnterWorktree` already relocates a running session correctly, so capability is not the gap — the trigger is. A SessionStart warning was considered and judged weaker: it advises, where the PreToolUse form blocks. The project already runs this exact pattern in `.claude/hooks/instruction-file-guard.py`.

**Cost/caveat:** needs an entry in `.claude/settings.json` (instruction-class, so it lands through the user's walk), and a PreToolUse hook runs for every session on the machine, so a defect in it is felt everywhere.

## 2. A `--directory` flag for the launchers

`scripts/launch-claude-ubuntu` and `scripts/launch-claude-mac` place every agent in `<agents-root>/<name>` by convention and accept no directory argument, so a seat cannot adopt an existing worktree. That makes "promote this background thread to a visible tmux seat" harder than it needs to be. Roughly ten lines per launcher.

Weakened, though not eliminated, by a fact discovered the same day: `claude attach <job-id>` already opens a background session in a terminal, so a seat is not the only route to visibility.

## 3. A CLAUDE.md rule: background jobs push their own branch

Several sessions pushing to one shared agent branch produced the `Merge remote-tracking branch 'origin/choirmaster' into choirmaster` commits in that branch's history, and a non-fast-forward rejection that cost a rebase mid-task. One branch per session removes the class: git already refuses one branch in two worktrees, so the discipline only has to cover which branch a session pushes.

Instruction-class text, so it lands through the user's walk.

## 4. md-review the fleet paths reference

`docs/cross-project/fleet-machine-paths-and-checkouts.md` was written 2026-08-13 and is a lasting reference, which is the md-review skill's stated target. Not yet reviewed.

## 5. Migrating `choirmaster` to a machine-suffixed name

Considered and deferred. The two machines share no agent state, so the same name on both is two unrelated agents rather than a conflict — the suffix buys legibility in a listing that spans machines, nothing more. Migrating the live seat means `git worktree move`, renaming its handoff files, and a restart, which is disruptive to a working agent for a cosmetic gain. Revisit only if a cross-machine listing becomes a routine view.

## 6. `$CLAUDE_PROJECT_DIR` points at the main checkout in a forked session, so the guards look in the wrong place

Owner: `fleet`. Found 2026-08-14 while wiring the backup-write guard, and confirmed twice.

In a session forked or attached into a worktree under `.claude/worktrees/`, the harness loads `.claude/settings.json` from **the worktree** but expands `$CLAUDE_PROJECT_DIR` to **the main checkout** (`/home/nedlern/Projects/nedschorus`). The two disagree, and both guards are built on the assumption that they agree.

Two consequences, one of them a live hole:

1. **`.claude/hooks/instruction-file-guard.py` reads its `.walk-approved` marker from the wrong root.** Its `project_root()` resolves `$CLAUDE_PROJECT_DIR`, so an approval quoted into the worktree's marker is never seen, while a *stale* marker sitting in the main checkout silently authorises one guarded write in any forked session. One was observed being consumed that way before the cause was understood — the write went through on an approval that had nothing to do with it.
2. **A hook registered by `$CLAUDE_PROJECT_DIR` path fails for any file that exists only on the branch.** Registering the new guard blocked every Edit and Write in the session until it was backed out, because the referenced path resolved into the main checkout where the file does not exist until merge. The interim fix is in `.claude/settings.json`: the registration falls back to `$PWD` when the `$CLAUDE_PROJECT_DIR` path is absent. That is a workaround at the call site, not a fix — the guards themselves still resolve their markers against the wrong root.

The proper fix belongs inside the guards: resolve the repository root from the file being written (walk up to the enclosing `.git`) rather than trusting the environment, which also makes them correct for seats, worktrees, and the main checkout alike without a fallback in the settings file. Verify against a forked session specifically, since a normally-launched session does not reproduce it.

## Session-management facts worth keeping (verified 2026-08-13, Claude Code 2.1.231)

Not riders, but hard-won and easy to lose:

- **Job ids are not session ids.** `claude attach <id>` takes the 8-character job id (the directory names under `~/.claude/jobs/`), not the session UUID. Attaching by session id fails with "No job matching".
- **`claude agents`** opens the agent view: every session grouped by state, `Space` peeks without attaching, `Ctrl+R` renames, `Ctrl+T` pins against the ~1-hour idle reap, `Ctrl+X` stops. `Ctrl+S` groups by *directory*, which makes the shared-directory hazard visible.
- **It must run on the machine whose sessions you want.** Typed on the Mac it lists the Mac's jobs; the box needs `ssh nedlern@ned-box -t 'claude agents'`.
- **No side-by-side view exists** in the harness. Simultaneous views mean one terminal (or tmux window) per session.
- **Process uptime is not idle time.** A session showing 23 hours of `etime` may have been active a minute ago; the honest staleness check is the modification time of its transcript under `~/.claude/projects/<project>/<session-id>.jsonl`.

## Cloud sessions and `claude --teleport` (read from the 2.1.232 binary, 2026-08-14)

A cloud session — one running on Anthropic's infrastructure rather than on the box or the Mac — has no filesystem of either machine: no `~/.claude`, no seat worktree, no `/mnt/backup`. It reaches a project by **cloning a git repository**, which makes git the only channel that can deliver anything to it. That is a design constraint rather than a preference, and it is the strongest argument for the shared machinery living in a real repository rather than only in machine-local installs.

`claude --teleport` moves a session between the cloud and a local CLI, in both directions (`teleportToRemote` exists alongside the resume path). Three constraints are enforced, each visible as its own error:

- **The local git working directory must be clean.** *"Git working directory is not clean. Please commit or stash your changes before using --teleport."* Seats routinely carry uncommitted work, so teleporting into a seat's worktree is not a casual operation.
- **It must run from a checkout of the same repository the cloud session used.** The error is `tengu_teleport_error_repo_mismatch_sessions_api`.
- **It cannot be combined with `--continue`,** nor with another remote backend (a `cc://` connect URL, `claude ssh`, `claude assistant`) — *"both select a remote backend; pick one."*

The second constraint has a consequence for any repository split: **a cloud session is bound to one repository.** If shared machinery and project content live in separate repositories, a cloud session that cloned the project repository cannot see the machinery, and a teleport lands in the project checkout. Whichever repository a cloud session clones is the one it gets.

Cloud sessions also sync files under explicit budgets, and give up rather than degrade silently — the binary carries distinct messages for a directory with more files than per-turn sync can track, a repository too large to track, a starting commit that cannot be read in the local checkout, and an exhausted per-session file budget. A large repository is therefore a functional limit on cloud sessions, not merely a slow one.
