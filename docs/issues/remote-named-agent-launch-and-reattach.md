# Running named agents on the Ubuntu box, reachable from iTerm2 by name

Pair document for the GitHub issue of the same subject. The issue carries state; this document carries the design, the walk's order, and the rulings as they land.

## What the user asked for (2026-08-07)

Type `launch-claude <name>` in iTerm2 and get that named agent. The agents themselves run on the Ubuntu box over SSH. If the agent is already running — because the iTerm2 window was closed — the same command reconnects to it rather than starting a second one.

## The mechanism

SSH alone cannot reconnect to a running process: a process's terminal belongs to whoever started it, and a second SSH connection cannot adopt it. A terminal multiplexer on the remote box is what provides attach-or-create, and tmux states it directly:

    ssh -t <box> tmux new-session -A -s <name> -c <worktree> '<supervisor command>'

`new-session -A` attaches to the session named `<name>` when it exists and creates it when it does not, which is the requested behavior exactly. Closing the iTerm2 window detaches; the agent keeps working; the same command reattaches.

This also settles the open question recorded against the seat move in `docs/cross-project/fast-handoff-design.md`: inside tmux the supervisor is the pane's own process, so every successor it launches inherits the pane's terminal and is visible on reattach. The detached-supervisor stdio problem does not arise in this topology.

## Walk order (opened 2026-08-07, new-vp session 5b66b6d0)

1. Purpose and the bar these decisions are judged by
2. What must exist on the Ubuntu box before any agent runs there
3. Whether SSH from the user's Mac is the server role that fires the hardening precondition ([nedschorus#40](https://github.com/nedschorus/nedschorus/issues/40))
4. What `launch-claude` must know — the agent roster and its home
5. How the migration sequences against the seat move
