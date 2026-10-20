# How to save a lesson where an agent meets it when it applies, instead of in a memory note

A lesson, here, is something an agent learned in one agent-session, usually from the user correcting it, that should change what later agents do. This page says where to put a lesson so that a later agent meets it at the moment it applies, and only then. Read it when you want to remember something, and before you ask the user where to save it.

## Why a memory note is refused

The instruction-file guard, `.claude/hooks/instruction-file-guard.py`, refuses every write into a Claude Code memory directory, and no marker lets one through. Saving is not the problem; recall is. A memory note is saved, but nothing puts it in front of an agent at the moment it applies: the agent has to think of opening it, and seldom does. CLAUDE.md fails the other way: it is always loaded, but its space is scarce, and an agent reading a long list of rules at the start of its work ignores most of them by the time one applies. A lesson works when it arrives at the moment the agent is about to act, or immediately after, while the agent still has the context to correct course cheaply.

## Where a lesson goes

1. **Split the lesson into its instructions, one per moment.** A moment is a step of a skill, a program the agent runs, a tool call, a file it edits, or a message it writes. An instruction that applies at two moments counts as two. Drop an instruction that matters only to the current conversation.
2. **Put each instruction in the first of these places that fits.** Each is a technique on [the techniques page](nedschorus-techniques-that-shape-what-agents-do-and-say-with-hooks-prompts-and-code.md), which says what fires it and who corrects a miss.
   1. **Code.** If a program can do the step, or refuse to go on without it, the lesson becomes that program's behaviour, and no agent has to remember it: code-prompt-code, or a gate in code.
   2. **The step of the skill** the agent follows at that moment.
   3. **The sentence that already tells agents to take that action**, wherever it is: a skill, a wiki page, a seat-brief, a bullet of CLAUDE.md. Change or extend that sentence; do not add a new one beside it. A lesson about how to test a test goes into the sentence that tells agents to test their tests.
   4. **The agent-facing-message of the program** the agent has just run, when the lesson is what to do next with that program; or the `description:` line of a skill, which the agent reads when it chooses the skill.
   5. **A row on the page of reusable components**, when the lesson is that a solution already exists, such as a parser or a shared helper. *Planned:* the page and the reminder hook that names a row when an agent starts on its problem, by GHI [Agents reuse what the project has already solved: shared helpers, one page of reusable components, and a reuse check before, during and after the build](https://github.com/nedschorus/nedschorus/issues/1123); until then, this place does not exist.
   6. **A new hook**, when the moment is a tool call, a file edit or a reply that a hook can recognise, and none of the places above exists. Hooks reach Claude Code agents only; this project configures none for Codex. Use block-and-inform when a check before the act can tell reliably that the act is wrong; otherwise detect-inform-correct, which tells the agent just after the act and has it redo the work. Keep the hook quiet except in the case it sees exactly.
   7. **The seat-brief**, when the lesson is about a job only one agent-seat does.
   8. **The glossary**, when the lesson is what a word means.
   9. **A new bullet in CLAUDE.md**, only when the moment comes in every kind of work, agents will otherwise get it wrong, and none of the places above exists.
3. **If no moment can be named, or no place fits,** as when a lesson concerns several agent-seats but not every kind of work, tell the user in one sentence what you meant to remember, and the places you ruled out; ask him where it should go.

Places 1 to 5 put the lesson in code or in text the agent is reading at that moment. Place 6 builds a new trigger for the moment. Places 7 to 9 are text the agent reads at the start of its work, which it is likely to have forgotten when the moment comes; use them only when nothing earlier fits. A change to a guarded-file, such as a skill, CLAUDE.md or a wiki page, goes to the user with its exact wording before it is made.

## A worked example

The user tells an agent: "I can only deal with these one at a time." The lesson: put one question to the user per message, written so he can answer it without other context, and do not list the other questions waiting beside it.

1. **Moments.** One: whenever the agent writes a message to the user that asks him something.
2. **Places, in order.**
   - Code: no program writes the agent's messages.
   - A skill step: `/walk-me-through` already shows one item per message, but only during an approval-walk; the lesson applies to every message.
   - An instruction about that action: no standing instruction tells agents how to ask the user a question.
   - A program's message, a skill description, a reusable component: none applies.
   - A new hook: a Stop hook, which runs when the agent finishes its reply, can read the reply and see when it asks the user more than one question. A check before the reply is impossible, so the hook is detect-inform-correct: the user has already seen the questions, so the hook tells the agent to take his answer to the first, and to ask each remaining question in a message of its own.
3. **Result.** The lesson becomes a proposed Stop hook, put to the user with the exact wording of the message it prints, and a task for whoever builds it. Until the hook is built, the agent that learned the lesson follows it for the rest of its agent-session.

## A store that recalls lessons by subject

A store would hold each lesson with a trigger, such as a tool name and a pattern on the command, the file path or the reply, and one hook would deliver a lesson when its trigger matches. It is not built. The lessons placed so far each found a place in text the agent already reads, so a store would add a second place to look and little else. GHI [Save each lesson where agents meet it at the moment it applies, and decide whether a store that recalls lessons by subject is worth building](https://github.com/nedschorus/nedschorus/issues/1349) holds the case for and against, and what would reopen the question.

**Checked against:** commit [ae70c3c430ada1ffb2580590ab10f8b575dfbdbd](https://github.com/nedschorus/nedschorus/commit/ae70c3c430ada1ffb2580590ab10f8b575dfbdbd)
