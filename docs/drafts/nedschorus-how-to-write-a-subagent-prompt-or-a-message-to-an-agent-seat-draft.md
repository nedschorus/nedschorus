# How to write a subagent's prompt or a message to an agent-seat

An agent starts a subagent with Claude Code's Agent tool, whose prompt holds the subagent's initial-agent-instructions, and writes to another agent-seat with Claude Code's SendMessage tool. The reader of either text has only that text and what it can look up, so the text must carry everything the reader needs. This page adds what the rules elsewhere leave out, and points to those rules. A forked subagent shares your context, so this page does not cover its prompt; text a program hands an agent, such as a hook's refusal, follows [How to write a tool-message-to-agent](../nedschorus-wiki/nedschorus-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md) instead.

Write both by [the style guide](../nedschorus-wiki/nedschorus-style-guide.md): every row whose "Applies to" names messages to other agents applies, the pronoun rows and the `or` row included.

## A subagent's prompt

- Write what the Agent tool's own description asks for: the goal, what you have already ruled out, the files to read, and a scope stated narrowly.
- Give each subagent a folder of its own for its files, inside the scratchpad directory that Claude Code's system prompt names for your agent-session, and write the folder's absolute path in the prompt, such as `<your scratchpad directory>/pull-request-description-writer/` with the placeholder filled in. Two subagents that write a file of the same name in one folder overwrite each other's work, and neither can tell.

## A message to an agent-seat

- Carry your citations, as the `CLAUDE.md` bullet that begins "Text a program hands an agent" says: the receiving agent-seat must verify claims it did not witness. Cite a log-store file in the form `CLAUDE.md` gives, `nedlern@ned-box:/home/nedlern/nedschorus-logs/<path>`; cite a pull request, a commit or a GHI by its link, or by its number after its ID-type, such as PR 2230.
- Address the agent-seat by its name. When the ListAgents tool lists more than one agent-session under that name, send to the address of the running one, such as `merge-lane-2 [b27c8d]`.
