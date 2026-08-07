# Running named agents on the Ubuntu box, reachable from iTerm2 by name

Pair document for [nedschorus#45](https://github.com/nedschorus/nedschorus/issues/45). The issue carries state; this document carries the design, the walk's order, and the rulings as they land.

## What the user asked for (2026-08-07)

Type `launch-claude <name>` in iTerm2 and get that named agent. The agents themselves run on the Ubuntu box over SSH. If the agent is already running — because the iTerm2 window was closed — the same command reconnects to it rather than starting a second one.

## The mechanism

SSH alone cannot reconnect to a running process: a process's terminal belongs to whoever started it, and a second SSH connection cannot adopt it. A terminal multiplexer on the remote box is what provides attach-or-create, and tmux states it directly:

    ssh -t <box> tmux new-session -A -s <name> -c <worktree> '<supervisor command>'

`new-session -A` attaches to the session named `<name>` when it exists and creates it when it does not, which is the requested behavior exactly. Closing the iTerm2 window detaches; the agent keeps working; the same command reattaches.

This also settles the open question recorded against the seat move in `docs/cross-project/fast-handoff-design.md`: inside tmux the supervisor is the pane's own process, so every successor it launches inherits the pane's terminal and is visible on reattach. The detached-supervisor stdio problem does not arise in this topology.

## Walk order (opened 2026-08-07, new-vp session 5b66b6d0)

1. Purpose and the bar these decisions are judged by
   *processed 2026-08-07 → accepted (purpose item; no capture)*
2. What must exist on the Ubuntu box before any agent runs there
   *processed 2026-08-07 → accepted. Probed live: the box answers as `ned` (10.0.1.39, user nedlern) on the existing SSH key with 895GB free; `claude` 2.1.220 is installed against the Mac's 2.1.223; `python3` and `git` are present; `tmux` is NOT installed; there is no nedschorus checkout; `~/.claude/tasks` does not exist yet. Blocking on the user: authentication is expired there ("OAuth session expired and could not be refreshed"), which needs an interactive login only he can perform. The version gap means both pre-seed canaries must be re-run on the box — they have only ever run on the Mac, and task carry-over rides undocumented harness state. Item split noted (user): this inventory bundled four facts needing no ruling with one decision, which became item 6.*
3. Whether SSH from the user's Mac is the server role that fires the hardening precondition ([nedschorus#40](https://github.com/nedschorus/nedschorus/issues/40))
4. What `launch-claude` must know — the agent roster and its home
5. How the migration sequences against the seat move
6. The box's machine-global CLAUDE.md, which defines a different agent's role
