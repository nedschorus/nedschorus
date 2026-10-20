# How to save a lesson where an agent meets it when it applies, instead of in a memory note

A lesson, here, is something an agent learned in one agent-session, usually from the user correcting it, that should change what later agents do. This page says where to put each instruction in a lesson so that a later agent meets it as close as possible to the moment it applies. Read it when you want to remember something, and before you ask the user where to save it.

## Why a memory note is refused

The instruction-file guard, `.claude/hooks/instruction-file-guard.py`, refuses with a hard-block every Edit, Write and NotebookEdit call into a Claude Code memory directory: no `.walk-approved` marker file lets one through. Even a saved note would not be recalled when it is needed. Claude Code loads only the index of the memory directory at the start of an agent-session; the note itself is read only if an agent thinks of opening it, and nothing puts it in front of the agent at the moment it applies. CLAUDE.md has the start-of-session problem without the index: Claude Code loads all of it, but its space is scarce, and a rule read at the start is easily forgotten by the time it applies. An instruction works best when it arrives at the moment the agent is about to act, or immediately after, while the agent still has the context to correct course cheaply.

## Where each instruction goes

1. **Split the lesson into its instructions, one per action.** The action is what the instruction changes: following a step of a skill, running a program, a tool call, editing a file, or writing a message. An instruction that applies to two actions counts as two. Drop an instruction that matters only to the current agent-session. If you are a subagent, report the lesson to the agent that dispatched you instead.
2. **Put each instruction in the first of these places that fits.** Where a place uses a technique, [the techniques page](nedschorus-techniques-that-shape-what-agents-do-and-say-with-hooks-prompts-and-code.md) describes it.
   1. **A program.** If a program the agent runs, or one its work passes through, such as a git hook or the merge gate, can do what the instruction asks, or refuse to go on without it, the instruction becomes that program's behaviour. A step simple enough to state in one sentence, and rarely done, does not need a program.
   2. **The step of the skill** the agent follows when it takes the action.
   3. **The sentence that already tells agents to take that action**, wherever it is: a skill, a wiki page, a seat-brief, a bullet of CLAUDE.md, or the user's own `~/.claude/CLAUDE.md` on each machine. Change or extend that sentence, and every copy of it; do not add a new one beside it. An instruction about how to run mutation testing goes into the sentence that tells agents to check their tests by mutation testing.
   4. **The agent-facing-message of the program** the agent has just run, when the instruction is what to do next with that program; or the `description:` line of a skill, which the agent reads when it chooses the skill.
   5. **A row on the page of reusable components**, when the instruction is that a solution already exists, such as a parser or a shared helper. *Planned:* the page, and a hook that names a row after an edit that writes such a solution again, by GHI [Agents reuse what the project has already solved: shared helpers, one page of reusable components, and a reuse check before, during and after the build](https://github.com/nedschorus/nedschorus/issues/1123); until it is built, this place does not fit.
   6. **A new Claude Code hook**, when the action is a tool call, a file edit or a reply that a hook can recognise exactly, none of the places above fits, and CLAUDE.md's rule on when to propose a guard is met: the mistake has happened or soon will, and it would lose or damage work, stop other work, or go unnoticed. Use block-and-inform when a check before the act can tell that the act is wrong; detect-inform-correct when it can see the wrong act only after it happens; a reminder on the act when nothing is wrong yet. Hooks reach Claude Code agents only; an instruction Codex agents also need goes in a program or in text.
   7. **The seat-brief**, when the instruction is about work only one agent-seat does.
   8. **The glossary**, when the instruction is what a word means: the project glossary, or, for a word one system uses, that system's glossary.
   9. **A new bullet in CLAUDE.md**, only when the action comes in every agent's work, agents will otherwise get it wrong, and none of the places above fits.
3. **If no action can be named, or no place fits,** as when, after places 1 to 6, an instruction concerns several agent-seats but not every agent, tell the user in one sentence what you meant to remember and the places you ruled out, and ask him where it should go.

Places 1, 2, 4 and 5 reach the agent at the action itself; place 3 does too when the sentence is in a skill or a page the agent reads for that action, and place 8 does when the agent looks the word up. Place 6 builds a new hook that fires at the action. Places 7 and 9, and a sentence of CLAUDE.md under place 3, are read at the start of an agent-session and are the weakest; use them only when nothing earlier fits.

A proposed change to a guarded-file, such as a skill, CLAUDE.md or a wiki page, gets the cold read the guard's refusal names, then goes to the user with its exact wording before it is made, unless it is an obvious-error-fix. A proposed program or hook goes to the user as a design before it is built. Until the change lands, the agent that learned the lesson follows it for the rest of its agent-session, and records the proposal where it will be picked up: a task on its task list, and, for a design, a GHI through `/ghi-write`.

## A worked example

The user tells an agent: "I can only deal with these one at a time." The lesson: put one question to the user per message, written so he can answer it without other context, and do not list the other questions waiting beside it.

1. **Actions.** One: writing a message to the user that asks him something.
2. **Places, in order.**
   1. A program: no program writes the agent's messages.
   2. A skill step: `/walk-me-through` shows a long or many-item message one item at a time, but an ordinary short question is not a walk, so no step of it covers this action.
   3. The sentence that already tells agents how to ask the user: the user's `~/.claude/CLAUDE.md`, on the Mac and on ned-box, says "Ask in prose instead: state the choice, give your recommendation and why, and let him answer in his own words." This place fits: the instruction extends that sentence, on both machines.
3. **Result.** The proposal: add to that sentence, in both copies, "Ask one question per message, and do not list the other questions you are waiting on beside it." A hook (place 6) would not pass CLAUDE.md's rule on guards: two questions in one message lose no work, and the user sees them at once.

## A store that recalls lessons by subject

A store would hold each instruction with a trigger, such as a tool name and a pattern on the command, the file path or the reply, and one hook would deliver an instruction when its trigger matches. It is not built. Of the eight lessons studied when the store was considered, every instruction but one had a place in text the agent already reads, so a store would add a second place to look and little else. GHI [Save each lesson where agents meet it at the moment it applies, and decide whether a store that recalls lessons by subject is worth building](https://github.com/nedschorus/nedschorus/issues/1349) holds the case for and against, and what would reopen the question.

**Checked against:** commit [ae70c3c430ada1ffb2580590ab10f8b575dfbdbd](https://github.com/nedschorus/nedschorus/commit/ae70c3c430ada1ffb2580590ab10f8b575dfbdbd)
