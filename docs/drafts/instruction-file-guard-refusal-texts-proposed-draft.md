# Proposed refusal texts, .claude/hooks/instruction-file-guard.py

## MEMORY_WRITE_DENY_MESSAGE (replaces the whole message)

Current:

Refusing to write {path}: it is in a Claude Code memory directory, where nothing recalls a note at the moment it applies.
If what you meant to save would change how agents work, propose to the user the exact edit, with its wording, to the instruction file, skill or program where an agent would meet it.
If you cannot tell where it belongs, tell the user in one sentence what you meant to remember, and ask him where to save it so that an agent recalls it when it applies.
If it matters only to this conversation, drop it.
If you are a subagent, put this to the agent that dispatched you instead.
No {marker} marker lets a write into a memory directory through, so do not write one for this.

Proposed:

Refusing to write {path}: it is in a Claude Code memory directory. This project blocks memory notes not because saving a lesson is wrong, but because a note is never recalled: nothing puts it in front of an agent at the moment it applies.
If you are a subagent, report what you meant to remember to the agent that dispatched you, and do nothing else with it.
If it matters only to this conversation, drop it; if it is working state for your current task, keep it in your scratchpad or your task list.
Otherwise, read docs/nedschorus-wiki/nedschorus-how-to-save-a-lesson-where-an-agent-meets-it-when-it-applies-instead-of-in-a-memory-note.md, which says where a lesson goes so that an agent meets it when it applies, and only then.
Do not move the lesson into CLAUDE.md instead: CLAUDE.md is always loaded, but its space is scarce and agents easily ignore it, so that wiki page puts CLAUDE.md last.
If that wiki page names a place, propose to the user the exact change, with its wording, at that place.
If no place on that wiki page fits, tell the user in one sentence what you meant to remember and which places you ruled out, and ask him where it should go.
No {marker} marker lets a write into a memory directory through, so do not write one, and do not retry this write.

## DENY_MESSAGE (one sentence added after the first)

Current first sentence:

Before modifying {path}, get the user's approval on your change: instruction files (CLAUDE.md, CLAUDE.local.md identity files, and .claude/ machinery) change only through the user's walk, however clearly the edit would help.

Added after it:

If your change adds a rule for agents, first read docs/nedschorus-wiki/nedschorus-techniques-that-shape-what-agents-do-and-say-with-hooks-prompts-and-code.md: a program, a hook, a skill step or a program's message usually delivers a rule at the moment it applies, where another line of standing text is easily ignored. If one of those fits, propose it to the user instead of this edit.
