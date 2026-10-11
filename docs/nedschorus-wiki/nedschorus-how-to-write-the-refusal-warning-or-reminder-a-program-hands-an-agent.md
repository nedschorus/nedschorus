# How to write the refusal, warning or reminder a program hands an agent

When a program in this project refuses an agent's act, warns it, reminds it or reports an error to it, the program's message is the agent's only account of what happened and why. The agent did not write the program and may never open its code, so the message decides whether the agent does the right thing next, works around the program, or passes the problem to the user. Write every such message so that an agent who reads only the message acts well, and so that the user hears only what he must decide or know.

## Which messages this page covers

Every text a program in this project hands an agent while the agent works, when the program refuses, warns, reminds or fails:

- a hook's refusal of a tool call, whether a hard-block, a soft-block or a user-block;
- a warning or reminder a hook adds, as `additionalContext`, to what the agent reads next;
- the `reason` field of a Stop hook that keeps the agent's turn open;
- an error, a failing verdict or usage text that a script the agent runs prints, a git hook included; usage text the agent asked for with `--help` is not an error, and this page does not cover it;
- the FAIL line of a test suite that enforces a project rule.

A line a program shows the user directly, with no agent between, says what a fact for the user says under "When the message sends the agent to the user": what stopped, on which machine, and what it costs him. The rest of this page is about messages an agent reads.

Below, "the act" means the tool call or command the program checks.

## What a message says

Every message says points 1 to 3. Point 4 applies when the message gives more than one instruction; point 5 applies when the agent can make the same mistake again.

1. **What was stopped or found.** Name the command, the file, the branch or the pull request, and the value that failed, when the program knows it.
2. **Why.** The rule being enforced, or what goes wrong if the agent goes ahead. A reason lets the agent apply the rule to a case the message did not foresee, instead of only getting past this one case.
3. **What to do instead**, as an instruction the agent can carry out now. Before you write the instruction, follow it yourself in the situation the message fires in, and check that it does not run into another program's refusal, a rebase of a frozen-head for example, and that it does not wait on something that never comes. A soft-block or a user-block names its marker and says exactly what to write into the marker to clear the refusal. A hard-block says what the agent can do instead to reach its goal, or, when the goal itself is not allowed, says so and why.
4. **The condition for each instruction**, when the message gives more than one. Put each instruction on its own line with the condition it applies under. Every "or" between two instructions says when to take each.
5. **What to do from now on**, when the agent can make the same mistake again. The fix for this one case teaches little about the next; one line on the behavior wanted next time does. Leave this point out for a fault the agent did not cause and cannot avoid, such as a network failure.

When the program finds the problem after the act, as a PostToolUse or Stop hook does, point 3 says whether the program already undid the act, and if it did not, how the agent sets the work right: by undoing the act and redoing the work correctly, or by correcting the work in place. When the act cannot be undone, such as a pushed commit, which this project never rewrites, the message says what the agent does instead, such as a fix in a new commit on top. When the program's finding can be wrong, the message says how the agent checks the finding before acting on it.

An example. `scripts/search-file-argument-read-as-option-guard-hook.py` refused `grep -r pattern *.md` in a directory holding a file named `-v.md`, because grep would read that file name as an option. A message that covers only points 1 to 3 tells the agent to add `--` before `*.md` in this command. A message that covers point 5 too adds: "In every grep or rg command whose file names come from a glob, put `--` before them."

## Who acts, and whether anyone needs to

For each case the program detects, the program's author decides who must act, and the message says so. These are choices for the author, not steps for the agent to go through in order. Most problems are the agent's to fix.

- **The agent.** When the agent's own action can help, give the agent its instruction, with a limit: the command to retry or to check, how many times, and only then what comes next. "Run it again once; if it fails the same way, ..." is right. "Stop and tell the user" as the first step, when a retry could fix the problem, is not. Before a retry of an act with side effects, such as filing a GHI or pushing, the message tells the agent how to check whether the first try already did it.
- **Another agent-seat.** When the author knows which agent-seat owns the program or the work, and that agent-seat can fix the problem, the message names that agent-seat and tells the agent to send it a message with Claude Code's SendMessage tool, addressed by the agent-seat's name, holding the failure, its effect, a recommendation and the result wanted. When that agent-seat cannot be reached, or has not answered by the time the agent needs the result, the agent tells the user so.
- **Nobody.** When a case the message covers needs no action, the message says so and says what dropping it means, such as "If the file is not one you edited, drop it: do not fix it and do not mention it to the user."
- **The user**, only for a decision only he can make, such as an edit to agent-instructions other than an obvious error that CLAUDE.md lets an agent fix, a setting only he can change, or a choice between two of his rules; or for a fact he must know, such as merges stopping or a machine whose tests cannot run.

## When the message sends the agent to the user

The user is one person running many agent-seats, and each question costs his attention. A message that sends an agent to the user says what the agent brings:

- **For a decision:** what is asked; the context quoted, such as the current and the proposed wording, or the error line; the agent's recommendation and why; and what the agent will do for each answer. "Show him the change", "walk it with him" and "say what you were trying to do" are not enough.
- **For a fact:** what stopped, on which machine, and what it costs him. The agent adds what it has already done.
- **Never "tell the user this message".** A message written for an agent is full of instructions to someone else, and reaches the user as raw material to sort out. When the user must hear a fact, the message gives the agent the sentence to pass on, written for the user. When the user must decide, the message says what the agent's question must hold, as above, and the agent writes the question.
- **Never raw material as the question.** A program's output, a log line, a list of findings or a list of files is for the agent to assess before it asks anything. Quoted inside a question the agent has framed, such material is context, as above.
- **Once per agent-session for each failure.** A failure that recurs on every push or every tool call sends the agent to the user once per agent-session, and that message says the agent will not be told again. A failure whose effect on the user changes, such as an outage that now stops merges, counts as a new failure. Later occurrences of the same failure go to the agent alone, with no instruction to tell the user. `scripts/absence-claim-locator-reminder-hook.py` is an example of a hook that fires once per agent-session. A git hook or a script, which cannot tell one agent-session from another, says each time that the agent tells the user about this failure only once per agent-session.
- **Agent-sessions no user attends.** In an agent-session no user attends, such as a `claude -p` child that a program starts, a reminder or a question that only the user could act on stays silent. A refusal still refuses and says why, because the agent must still not do the act. `scripts/absence-claim-locator-reminder-hook.py` shows how a hook tells such an agent-session apart.
- **Subagents.** A message that sends an agent to the user always carries one more line, for the case that a subagent reads it: a subagent puts the same question, or passes the same fact, to the agent that dispatched it.

## How each output channel reaches the agent and the user

The Claude Code hooks reference (https://code.claude.com/docs/en/hooks) gives every output channel and exit code for each hook event. This page relies on these:

- A hook's refusal of a tool call arrives as the tool's error result. The agent reads it at once; the user sees it in the terminal, but cannot be counted on to read it.
- A Stop hook's block keeps the agent's turn open, and its `reason` field is the agent's next instruction. The user sees the `reason` field too. A Stop hook must not keep the turn open again on the agent's answer to what the hook said. Claude Code sets the payload's `stop_hook_active` to true during the agent's answer to any Stop hook's block, so a hook that stays silent when `stop_hook_active` is true also stays silent after another Stop hook's block.
- `additionalContext` arrives as text the agent reads next. The user does not see it, except from a Stop hook, whose `additionalContext` Claude Code shows the user as "Stop hook feedback".
- `systemMessage` is shown to the user, not the agent, and only from a synchronous hook on some hook events; the hooks reference says which. Use it only for a fact the user must know when no agent turn follows to pass the fact on. Otherwise send the matter to the agent and let the agent frame what reaches the user. Never tell the agent "do not report this" about something the user has just been shown.
- A git hook or a script the agent runs speaks through its output, which the agent reads as the command's result, and through its exit code; the user cannot be counted on to read that output either.
- Codex runs none of the hooks registered in `.claude/settings.json`, so a rule only a Claude Code hook delivers never reaches an agent running in Codex.

Claude Code labels a hook's exit-2 refusal, and a Stop hook's block, as a hook error, which an agent can take for a malfunction to work around. Open a refusal or a block by saying that the program refused the act on purpose. When hook output runs over 10,000 characters, the agent sees only a 2,000-character preview, so put what was stopped, why and the instruction in the first lines and the details after.

Write instructions as instructions, on every channel. The Claude Code hooks reference (section "Add context for Claude") advises phrasing `additionalContext` as statements of fact, because text framed as system instructions can be taken for prompt injection. This project writes the clearest message it can instead. When a project message is taken for prompt injection, that is a defect of that message: fix that message, and do not make other messages vaguer to avoid it.

## Every claim holds

- **In every situation the message fires in.** A sentence true on the Mac and false on ned-box, or true before a push and false after, misleads in the other situation. Name the machine when an instruction runs on one machine only.
- **About what the agent did.** A reminder about a whole file, or about lines this Edit or Write did not write, asks for unrelated changes and comes back after every edit. Judge the lines the act wrote, and any unchanged line the act made wrong.
- **About whether the act happened.** When a program fails partway, say what may already have happened, how the agent finds out, and how to resume, so the agent neither repeats the act nor leaves it half done.
- **With the underlying cause.** When a program runs another program that fails, pass on the cause and the instruction the failing program gave, such as "ned-box cannot be reached", instead of a bare "failed". When the program below gave no cause, say so and give its exit status.
- **When the program fails open.** When the program detects that it could not run its check, such as a missing dependency or a file it cannot read, and lets the act through, say that the act was not checked and what the agent does about it, since the message is then the only report. A hook that crashes or times out reports nothing, so this covers only failures the program detects itself.

## What stays out

- **History.** Dates, user-rulings, quotations of the user, incidents, review rounds, and GHI or pull request numbers cited as the source of a rule belong in the commit message and the pull request, where `git log` and `git blame` find them. The agent needs the reason and the instruction, not who decided and when. An identifier the agent acts on, such as the pull request a merge refused, stays.
- **A raw exception or usage text as the whole message.** Say what was wrong with this call, then add the details.
- **Words the agent has to guess.** Use the terms of the project glossary, or of the glossary of the system the program belongs to, and name a thing in full the first time.
- **Apology and reassurance.** The agent needs what happened, why, and what to do.

## Before the message merges

- Test the message: assert, in a test that runs the program, that each line the agent must act on is present, so that deleting or rewording the line fails a test. Where you can, also run in a test each command the message tells the agent to run, so that an instruction which stops working fails a test too. `scripts/registered-hook-messages-carry-no-citations-test.py` already fails a hook registered in `.claude/settings.json` whose module-level message constants, those named with an ending such as `_MESSAGE` or `_REASON`, cite a date, a ruling, or an issue or pull request; it also fails a registered hook that declares no such constant.
- A program that hands agents messages carries a comment naming this page by its path, `docs/nedschorus-wiki/nedschorus-how-to-write-the-refusal-warning-or-reminder-a-program-hands-an-agent.md`, so whoever edits a message finds the page.
- Read the message as a fresh-reader would, as the agent will meet it, and check it against this page.
