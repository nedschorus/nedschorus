# Proposed wording: the `!` prefix sentence in the user's personal CLAUDE.md

The user sits at a Mac; Claude agent-sessions run on ned-box, an Ubuntu machine. The user can type `!` before a command in an agent-session's prompt to run that command himself inside that agent-session. This sentence goes in the user's personal instructions file, `~/.claude/CLAUDE.md` on ned-box, which every agent-session on ned-box reads, in the section that tells agents how to hand the user a command.

Current sentence:

> The `!` prefix runs inside the session on ned-box — and inherits the session's sandbox and worktree isolation, so commands that must escape those need a separate terminal.

Proposed sentence:

> A command the user types with the `!` prefix runs inside the agent-session's sandbox. If the user must run a command himself, such as an interactive login, and the command must run outside the sandbox, ask him to run it in a separate terminal. A command that needs nothing from him, the agent runs itself, inside or outside the sandbox.
