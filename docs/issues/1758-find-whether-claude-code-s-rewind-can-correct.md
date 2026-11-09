---
issue: "[Find whether Claude Code's rewind can correct an agent's wrong act, triggered by a program](https://github.com/nedschorus/nedschorus/issues/1758)"
---

# Find whether Claude Code's rewind can correct an agent's wrong act, triggered by a program

## Why

This project controls agents partly by correction: after a check sees a wrong act, a program reverts it, or the agent is told to revert it (detect-inform-correct, in `docs/nedschorus-wiki/nedschorus-glossary.md`). Claude Code has its own undo, rewind, which may be a third way to correct. The user asked on 2026-10-20 for this issue, so that the techniques page on instructing and controlling agents (still a draft when this issue was filed, on branch `agent-control-techniques-and-lesson-placement-wiki-pages-topic-branch` at `docs/drafts/nedschorus-techniques-that-shape-what-agents-do-and-say-with-hooks-prompts-and-code.md`, and bound for `docs/nedschorus-wiki/` under the same name) can link to it from its correction section. He was not sure what rewind does or how a program could trigger it.

## What the documentation says

These points come from Anthropic's documentation, read 2026-10-20.

- A person opens the rewind menu with `/rewind`, or by pressing Esc twice at an empty prompt. The menu restores the code and the conversation, the conversation only, or the code only, to the checkpoint taken before a chosen prompt. The 100 most recent checkpoints are kept. Source: [Checkpointing](https://code.claude.com/docs/en/checkpointing).
- Restoring the code undoes only changes made with Claude Code's file-editing tools (Write and Edit). It does not undo changes made by shell commands; a subagent's changes to files the conversation had not already edited, unless the subagent is a skill with `context: fork` running in the foreground; changes made outside the agent-session; files reached through a link; effects on other systems; or git history. Source: [Checkpointing](https://code.claude.com/docs/en/checkpointing).
- A program can rewind files, but not the conversation, in two ways: the Agent SDK's `rewindFiles()` (in Python, `rewind_files()`) with file checkpointing enabled, and the CLI flag `--rewind-files <user-message-uuid>` together with `--resume <session-id>`. The flag is not listed in `claude --help`, and run from the bare CLI it needs `CLAUDE_CODE_ENABLE_SDK_FILE_CHECKPOINTING=true`. Source: [File checkpointing](https://code.claude.com/docs/en/agent-sdk/file-checkpointing).
- No hook can rewind: the whole [hooks reference](https://code.claude.com/docs/en/hooks) (its Markdown, 269,034 characters, fetched 2026-10-20) contains neither "rewind" nor "checkpoint".
- The documentation does not say whether checkpoints are taken in a headless `claude -p` session, nor whether they are taken without `CLAUDE_CODE_ENABLE_SDK_FILE_CHECKPOINTING` set.

## What is not known

1. Whether a program in this project can rewind a running agent-session's files: whether `--rewind-files` works on a session that is still open, or only on one that is resumed after it ends.
2. Whether anything can rewind a running agent-session's conversation from outside it, so that the agent also forgets the wrong act.
3. Whether checkpoints exist for this project's agent-seats as they are launched today, without that environment variable, including the headless agent-sessions that programs such as the cold-read-cells start.
4. For which of this project's wrong acts a rewind would be the right correction. The wrong acts to weigh are those the techniques page's correction section lists. The guarded-file case already has GHI [Catch a guarded file changed without the user's approval, ask him, and keep every version](https://github.com/nedschorus/nedschorus/issues/1268), and rewind cannot undo the shell edits that case is mostly about.

## Next action

Test questions 1 to 3 on the Mac, in a scratch directory, with two throwaway agent-sessions: one interactive `claude`, and one headless `claude -p`, each started without `CLAUDE_CODE_ENABLE_SDK_FILE_CHECKPOINTING`. In each, have the agent change a file with the Edit tool. Take the session ID and the UUID of the user message before the edit from the session's transcript, `~/.claude/projects/<the directory's encoded path>/<session-id>.jsonl`, where each user message's record carries a `uuid` field. Run `claude --resume <session-id> --rewind-files <uuid>` with that variable set, once while the interactive session is still open and once after it has ended, and once for the headless session. Record, for each run, whether the file was restored and what the command printed. If a run against an open session fails or corrupts the open session, record that as the answer to question 1. Then answer question 4. Then put to the user whether rewind earns a place among the techniques page's correction techniques, and update that page's link to this issue to match his ruling.
