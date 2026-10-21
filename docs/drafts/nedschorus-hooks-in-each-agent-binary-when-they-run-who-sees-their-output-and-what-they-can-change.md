# Hooks in each agent-binary: when they run, who sees their output, and what they can change

A draft companion to [Techniques that shape what agents do and say, with hooks, prompts and code](nedschorus-techniques-that-shape-what-agents-do-and-say-with-hooks-prompts-and-code.md). It lists, for each agent-binary the project runs, the moments at which a hook or a program can act, what a hook's output and its failure reach, and what a program can rewrite or undo. These facts were checked against each agent-binary's documentation on 2026-10-21; they change between releases, so check the current documentation before a design depends on one.

## Claude Code

**The moments a hook can act.**

- SessionStart, when an agent-session starts or resumes; SubagentStart, which can add context to a subagent.
- UserPromptSubmit, when the user's prompt arrives.
- PreToolUse, just before a tool runs, which can allow, ask, deny or rewrite the call.
- PostToolUse and PostToolUseFailure, just after a tool runs or fails.
- Stop and SubagentStop, at turn end, after the reply is shown; a Stop hook can send the agent back, but cannot unshow the reply.
- TaskCreated and TaskCompleted, which can refuse with a message.
- FileChanged, when a watched file changes by any means; it can neither block nor tell the agent.
- MessageDisplay, which changes what the user sees, never what the agent knows.
- InstructionsLoaded, which can only observe standing text loading.

**What reaches the agent.**

- A hook that exits 0 with JSON: its decision and its added context reach the agent.
- A hook that exits 2: its stderr reaches the agent, and blocks where the event can block.
- A hook that exits 1, or with any other code: the user sees a hook-error notice, and the agent sees nothing. A check that must tell the agent it could not run exits 0 with added context, or 2.
- A PreToolUse hook that crashes or times out lets the call proceed, unless the hook sets `onFailure` to `block`. A deny rule in the settings holds whatever a hook returns.

**At turn end.** A Stop hook reads the reply from the `last_assistant_message` field, because the transcript file may not hold it yet. Stop does not run when the user interrupts. A turn that ends in an API error fires StopFailure instead, whose output is ignored.

**What a program can rewrite.** A PreToolUse hook can replace a tool call's input before it runs, with `updatedInput`, and a PostToolUse hook can replace what the agent sees of the result, with `updatedToolOutput`. A prompt hook or an agent hook hands the hook's input to a model, which decides. The project uses none of these yet.

**What a program can undo.** No hook can trigger a rewind. A program outside the agent-session can, through the Agent SDK's `rewind_files()` or `claude -p --resume <session> --rewind-files <checkpoint>`, when the agent-session had file checkpointing enabled. A rewind restores only changes made with the Write, Edit and NotebookEdit tools, not a shell command's. Whether an ordinary interactive agent-session can have checkpointing enabled is untried: GHI [Find whether Claude Code's rewind can correct an agent's wrong act, triggered by a program](https://github.com/nedschorus/nedschorus/issues/1758).

## Git

The git hooks, pre-commit, pre-merge-commit, prepare-commit-msg and pre-push, run for every agent-binary that commits or pushes in a checkout that has them, however the command was typed. They do not run for a command that skips hooks, in a clone without them, or for a change made on GitHub itself; those need a constraint on GitHub.

## Codex

What reaches a Codex agent today: `AGENTS.md`, which sends it to `CLAUDE.md`; the git hooks; the reviewer instructions; and the limits `scripts/run-codex-task-from-brief.py` starts it with. No Claude Code hook reaches it. Codex has hooks of its own, read from `.codex/hooks.json` or `config.toml` once the project's layer is trusted, including a PreToolUse hook that can deny or rewrite a call and a Stop hook that can continue the turn. The project registers none.

## Antigravity, for Gemini

The project runs Gemini only through `nc-systems/cold-read/cold-read-agy-cell.py`, inside the operating system's sandbox. Antigravity has hooks of its own, read from `.agents/hooks.json`: PreToolUse, which can allow, deny, ask or overwrite a call; PostToolUse; hooks before and after each model call; and Stop. The project registers none.
