# Running named agents on the Ubuntu box, reachable from iTerm2 by name

Pair document for [nedschorus#45](https://github.com/nedschorus/nedschorus/issues/45). The issue carries state; this document carries the design, the walk's order, and the rulings as they land.

## What the user asked for (2026-08-07)

Type `launch-claude <name>` in iTerm2 and get that named agent. The agents themselves run on the Ubuntu box over SSH. If the agent is already running — because the iTerm2 window was closed — the same command reconnects to it rather than starting a second one.

## The mechanism

SSH alone cannot reconnect to a running process: a process's terminal belongs to whoever started it, and a second SSH connection cannot adopt it. A terminal multiplexer on the remote box is what provides attach-or-create, and tmux states it directly:

    ssh -t <box> tmux new-session -A -s <name> -c <worktree> '<supervisor command>'

`new-session -A` attaches to the session named `<name>` when it exists and creates it when it does not, which is the requested behavior exactly. Closing the iTerm2 window detaches; the agent keeps working; the same command reattaches.

This also settles the open question recorded against the seat move in `docs/cross-project/fast-handoff-design.md`: inside tmux the supervisor is the pane's own process, so every successor it launches inherits the pane's terminal and is visible on reattach. The detached-supervisor stdio problem does not arise in this topology.

## Where per-agent identity lives (user-ruled 2026-08-07)

An agent's identity — who it is, what it may do, how it reports — is scoped to **one agent**, neither to the machine nor to the repository. Claude Code provides exactly that scope, and the official memory documentation names it: **`CLAUDE.local.md`**, the "Local instructions" scope, personal to one working directory and meant to be gitignored. The documentation states the worktree property directly: *"a gitignored CLAUDE.local.md only exists in the worktree where you created it."* Since each named agent gets its own worktree, each agent gets its own identity file, and no sibling agent sees it.

Verified by probe 2026-08-07: a project `CLAUDE.md` and a `CLAUDE.local.md` beside it both load into a cold session, and a deeper `CLAUDE.md` in the working directory loads on top of the project one — so the effective order is managed policy, then user, then project, then local, each concatenated rather than overriding.

**A superseded claim, recorded so it is not repeated:** this document briefly asserted that agent identity had no CLAUDE.md home and had to ride the launch as a system prompt. That was wrong — it counted only the machine and project scopes and missed the local one — and the user rejected the system-prompt approach on its own merits before the documentation settled the mechanism.

**Reviewability, the one thing the local scope costs.** A gitignored file is outside version control and therefore outside the instruction-class review rule. The fix is that the local file carries no content of its own: it is a single `@` import of a tracked identity file in the repository, so the reviewable text stays committed and walked while the gitignored file supplies only per-worktree scoping.

Consequence for the roster (walk item 4): a roster entry is a name, a worktree, and the tracked identity file its `CLAUDE.local.md` imports.

Consequence for the box's global file (walk item 6): the nm role content belongs at `~/agent/nedsmessenger/CLAUDE.local.md`, gitignored. The nm adapter already runs with its working directory set to that repository, so the agent reads exactly the same text it reads today, no adapter change is needed, the tracked project `CLAUDE.md` is untouched, and the machine-global slot is freed so NC agents are no longer told they are the nm bot.

## Walk order (opened 2026-08-07, new-vp session 5b66b6d0)

1. Purpose and the bar these decisions are judged by
   *processed 2026-08-07 → accepted (purpose item; no capture)*
2. What must exist on the Ubuntu box before any agent runs there
   *processed 2026-08-07 → accepted. Probed live: the box answers as `ned` (10.0.1.39, user nedlern) on the existing SSH key with 895GB free; `claude` 2.1.220 is installed against the Mac's 2.1.223; `python3` and `git` are present; `tmux` is NOT installed; there is no nedschorus checkout; `~/.claude/tasks` does not exist yet. Blocking on the user: authentication is expired there ("OAuth session expired and could not be refreshed"), which needs an interactive login only he can perform. The version gap means both pre-seed canaries must be re-run on the box — they have only ever run on the Mac, and task carry-over rides undocumented harness state. Item split noted (user): this inventory bundled four facts needing no ruling with one decision, which became item 6.*
3. Whether SSH from the user's Mac is the server role that fires the hardening precondition ([nedschorus#40](https://github.com/nedschorus/nedschorus/issues/40))
   *processed 2026-08-07 → accepted: it does NOT fire. SSH already runs and is already how the user reaches the box; agents make outbound API calls and accept nothing inbound; nothing becomes reachable off the LAN. The trigger stands for the case it was written for — an agent reachable from outside the network, or any new listener such as a web interface, a webhook receiver, or the gatekeeper's identity service.*
   *Posture measured read-only the same day, since the user was unsure whether the hardening done so far suffices. ufw is active with default deny incoming and deny routed, and every allow rule is scoped to the LAN (`10.0.1.0/24`) or a container subnet. SSH accepts public keys only — password and keyboard-interactive authentication are off, root login is `prohibit-password`, empty passwords refused. Unattended upgrades are enabled with zero security updates pending. Mattermost listens on `0.0.0.0:8065` with no ufw rule, so the default-deny policy is the only thing keeping it closed — it is closed, but by policy rather than by binding, which is worth knowing before anyone edits firewall rules. fail2ban is not running; under key-only SSH that is not a gap worth closing. The one thing not verifiable from inside the LAN is whether the home router forwards any port to this box — that is the only remaining route to internet exposure, and only the user can check it.*4. What `launch-claude` must know — the agent roster and its home
5. How the migration sequences against the seat move
6. The box's machine-global CLAUDE.md, which defines a different agent's role
   *open 2026-08-07 — the user is reading the file before ruling. Established so far: `~/.claude/CLAUDE.md` on the box is a 49-line role definition in the second person ("You are the nm agent") covering the ubuntu-claude bot's identity, MCP tools, GitHub account, and chat conventions. It is NOT a draft of `~/agent/nedsmessenger/CLAUDE.md`, which exists, is different, and carries that project's doctrine; the nm adapter runs with `cwd` set to the repo, so both files load together on every nm run, and `adapter/adapter.py:384` relies on the global one deliberately. A proposal to append the role content into the repo's file was REJECTED by the user: the content has never been reviewed, and relocating unreviewed instructions just moves the problem. Whatever survives review must land somewhere that does not load for every agent on the machine, since NC agents would otherwise be told they are the nm bot.*
