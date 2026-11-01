# How to write an agent-facing-message

When a program in this project refuses an agent's act, warns it, reminds it or reports an error to it, the program's message is usually the agent's only account of why the program acted and what to do next. The agent often did not write the program and need not open its code, so the message decides whether the agent does the right thing next, works around the program, or passes the problem to the user. Write every such message so that a fresh-agent who reads the message acts well without reading the program's code, and so that the user hears only what he must decide or know.

## Which messages this page covers

This page covers the agent-facing-messages a program in this project hands an agent while the agent works, when the program refuses, warns, reminds or fails:

- a hook's refusal of a tool call, whether a hard-block, a soft-block or a user-block;
- a warning or reminder a hook adds, as `additionalContext`, to what the agent reads next;
- the `reason` field of a Stop hook that keeps the agent's turn open;
- an error, a failing verdict or usage text that a script the agent runs prints, a git hook included; usage text the agent asked for with `--help` is not an error, and this page does not cover it;
- the FAIL line of an nc-test-suite that enforces a project rule.

A line a program shows the user directly, with no agent between, says what a fact for the user says under "When the message sends the agent to the user": what stopped, on which machine, and what it costs him. The rest of this page is about messages an agent reads.

Below, "the act" means what the agent did, or tried to do, that the program answers: the tool call or command a hook or a git hook checks; for a script's error, the command that ran the script; for a Stop hook, the agent's attempt to end its turn; for an nc-test-suite's FAIL line, the change under test.

## What a message says

Every message says points 1 to 3. Point 4 applies when the message gives more than one instruction; point 5 applies when the agent can make the same mistake again.

1. **What was stopped or found.** Name the command, the file, the branch or the pull request, and the value that failed, when the program knows it.
2. **Why.** The rule being enforced, or what goes wrong if the agent goes ahead; for an error, its cause. A reason lets the agent apply the rule to a case the message did not foresee, instead of only getting past this one case.
3. **What to do instead**, as an instruction the agent can carry out now. Give the exact command, value, path or account to use, with every value the program knows filled in. Where a value only the agent knows is needed, write a placeholder such as `<branch name>` and say what goes there. Describe a step in words only when no command can be given. Once you have drafted the instruction, follow it yourself in the situation the message fires in, and check that it does not run into another program's refusal, a rebase of a frozen-head for example, and that it does not wait on something that never comes. A soft-block or a user-block names its marker file and says what to write into the marker file, and in what form, to clear the refusal: for a soft-block, the agent's own reasoning; for a user-block, the user's approval, quoted. A hard-block says what the agent can do instead to reach its goal, or, when the goal itself is not allowed, says so and why.
4. **The condition for each instruction**, when the message gives more than one. Put each instruction on its own line with the condition it applies under. Every "or" between two instructions says when to take each.
5. **What to do from now on**, when the agent can make the same mistake again. The fix for this one case teaches little about the next; one line on the behavior wanted next time does. Leave this point out for a fault the agent did not cause and cannot avoid, such as a network failure.

When the program finds a problem after the agent has acted, as a PostToolUse or Stop hook does under detect-inform-correct, point 3 says what the agent does in each of these cases that applies. When the first case holds together with another, the agent confirms the problem first, and acts on the other case only when the problem is real. When the program cannot tell which case applies, point 3 gives each case with its condition.

- The check can give a false positive, as a check that guesses from a pattern can: point 3 says how the agent confirms the problem, and that the agent leaves the work as it is when the check was wrong.
- The program already undid what the agent did: point 3 says so, and how the agent redoes the work correctly.
- The work is still in place and nobody else has it yet, such as an uncommitted edit: point 3 says how the agent fixes the work in place.
- Someone else already has the work, such as a reply the user has read or a commit pushed for review: point 3 says what new work corrects it, such as a correction in the agent's next message or a new commit on top.

An example. `.claude/guard-hooks/search-file-argument-read-as-option-guard-hook.py` refused `grep -r pattern *.md` in a directory holding a file named `-v.md`, because grep would read that file name as an option. A message that covers only points 1 to 3 tells the agent to add `--` before `*.md` in this command. A message that covers point 5 too adds: "In every grep or rg command whose file names come from a glob, put `--` before them."

## Who acts, and whether anyone needs to

For each case the program detects, the program's author decides who must act, and the message says so. These are choices for the author, not steps for the agent to go through in order. Most problems are the agent's to fix.

- **The agent.** When the agent's own action can help, give the agent its instruction, with a limit: the command to retry or to check, how many times, and only then what comes next. "Run it again once; if it fails the same way, ..." is right. "Stop and tell the user" as the first step, when a retry could fix the problem, is not. Before a retry of an act with side effects, such as filing a GHI or pushing, the message tells the agent how to check whether the first try already did it.
- **Another agent-seat.** When the author knows which agent-seat owns the program or the work, and that agent-seat can fix the problem, the message names that agent-seat and tells the agent to send that agent-seat, with Claude Code's SendMessage tool and addressed by the agent-seat's name, the failure, its effect, a recommendation and the result wanted. When that agent-seat cannot be reached, or has not answered by the time the agent needs the result, the agent tells the user so.
- **Nobody.** When a case the message covers needs no action, the message says so and says what dropping it means, such as "If the file is not one you edited, drop it: do not fix it and do not mention it to the user."
- **The user**, only for a decision only he can make, such as an edit to agent-instructions that needs his approval under `docs/nedschorus-wiki/nedschorus-which-changes-need-the-users-approval.md`, a setting only he can change, or a choice between two of his rules; or for a fact he must know, such as merges stopping or a machine whose tests cannot run.

## When the message sends the agent to the user

The user is one person running many agent-seats, and each question costs his attention. A message that sends an agent to the user says what the agent brings:

- **For a decision:** what is asked; the context quoted, such as the current and the proposed wording, or the error line; the agent's recommendation and why; and what the agent will do for each answer. "Show him the change", "walk it with him" and "say what you were trying to do" are not enough.
- **For a fact:** what stopped, on which machine, and what it costs him. The agent adds what it has already done.
- **Never "tell the user this message".** A message written for an agent is full of instructions to someone else, and reaches the user as raw material to sort out. When the user must hear a fact, the message gives the agent the sentence to pass on, written for the user, and not the whole message. When the user must decide, the message says what the agent's question must hold, as above, and the agent writes the question.
- **Never raw material as the question.** A program's output, a log line, a list of findings or a list of files is for the agent to assess before it asks anything. Quoted inside a question the agent has framed, such material is context, as above.
- **Subagents.** A message that sends an agent to the user always carries one more line, for the case that a subagent reads it: a subagent puts the same question, or passes the same fact, to the agent that dispatched it.

## How each output channel reaches the agent and the user

The Claude Code hooks reference (https://code.claude.com/docs/en/hooks) gives every output channel and exit code for each hook event. This page relies on these:

- A hook's refusal of a tool call arrives as the tool's error result. The agent reads it at once; the user sees it in the terminal, but cannot be counted on to read it.
- A Stop hook's block keeps the agent's turn open, and its `reason` field is the agent's next instruction. The user sees the `reason` field too.
- `additionalContext` arrives as text the agent reads next. The user does not see it, except from a Stop hook, whose `additionalContext` Claude Code shows the user as "Stop hook feedback".
- `systemMessage` from a synchronous hook is shown to the user, not the agent, and only on some hook events; the hooks reference says which. From a hook run with `"async": true`, `systemMessage` goes to the agent on its next turn instead, and the user does not see it. Use `systemMessage` only for a fact the user must know when no agent turn follows to pass the fact on. Otherwise send the matter to the agent and let the agent frame what reaches the user. Never tell the agent "do not report this" about something a `systemMessage` has just shown the user.
- A git hook or a script the agent runs speaks through its output, which the agent reads as the command's result, and through its exit code; the user cannot be counted on to read that output either.
- Codex reads its hooks from a `hooks.json` file in its own configuration folders, such as `~/.codex/`, or from its configuration file, `~/.codex/config.toml`, never from `.claude/settings.json`, and this project has configured no Codex hooks yet, so a rule only a Claude Code hook delivers never reaches an agent running in Codex.

Claude Code labels a hook's refusal by exit code 2, and a Stop hook's block, as a hook error, which an agent can take for a malfunction to work around. Open a refusal or a block by saying that the program refused the act on purpose. When one `additionalContext` or `systemMessage` string, or a hook's plain stdout, runs over 10,000 characters, Claude Code saves the text to a file and the agent sees only the file's path and the first 2,000 characters, so put what was stopped, why and the instruction in the first 2,000 characters and the details after.

Write instructions as instructions, on every channel. The Claude Code hooks reference (section "Add context for Claude") advises phrasing `additionalContext` as statements of fact, because text framed as system instructions can be taken for prompt injection. This project writes the clearest message it can instead. When an agent-facing-message is taken for prompt injection, that is a defect of that agent-facing-message: fix that agent-facing-message, and do not make other agent-facing-messages vaguer to avoid it.

## Every claim holds

- **In every situation the message fires in.** A sentence true on the Mac and false on ned-box, or true before a push and false after, misleads in the other situation. Name the machine when an instruction runs on one machine only.
- **About what the agent did.** A reminder about a whole file, or about lines this Edit or Write did not write, asks for unrelated changes and comes back after every edit. Judge the lines the act wrote, and any unchanged line the act made wrong.
- **About whether the act happened.** When a program fails partway, say what may already have happened, how the agent finds out, and how to resume, so the agent neither repeats the act nor leaves it half done.
- **With the underlying cause.** When a program runs another program that fails, pass on the cause and the instruction the failing program gave, such as "ned-box cannot be reached", instead of a bare "failed". When the failing program gave no cause, say so and give its exit code.
- **When the program fails open.** When the program detects that it could not run its check, such as a missing dependency or a file it cannot read, and lets the act through, say that the act was not checked and what the agent does about it, since the message is then the only report. A hook that crashes or times out hands the agent no message of its own, so this point covers only failures the program detects itself.

## What stays out

- **History.** Dates, user-rulings, quotations of the user, incidents, review rounds, and GHI or pull request numbers, when they are cited as the source of a rule, belong in the commit message, where `git log` and `git blame` find them, and in the pull request. The agent needs the reason and the instruction, not who decided and when. A value the agent acts on, such as the pull request a merge refused or the time a lock expires, stays.
- **A raw exception or usage text as the whole message.** Say what was wrong with the act, then add the details.
- **Words the agent has to guess.** Use the terms of the project glossary, or of the glossary of the system the program belongs to, and name a thing in full the first time.
- **Apology and reassurance.** The agent needs what happened, why, and what to do.

## Before the message merges

- Test the message: assert, in a test that runs the program, that each line the agent must act on is present, so that deleting or rewording the line fails a test. Where you can, also run in a test each command the message tells the agent to run, so that an instruction which stops working fails a test too. `scripts/registered-hook-messages-carry-no-citations-test.py` already fails a hook registered in `.claude/settings.json` whose module-level string constants named in capitals, whatever their names end in, cite a date, a user-ruling, or a GHI or pull request; it also fails a registered hook that declares no constant named with an ending such as `_MESSAGE` or `_REASON`. A constant that needs a date or a number as data, not as a citation, goes in that test's `EXEMPTIONS`, named by hook and constant.
- Put in each program that hands agents messages a comment naming this page by its path, `docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md`, so whoever edits a message finds the page.
- Before the message merges, test it with a fresh-agent, given a short description of the situation the message was written for and, when the message fires inside one skill, that skill. Do not try to give it the context of a particular agent: a message that works for a fresh-agent also works for an agent that knows more. A prompt handed to a fork or a subagent that shares its writer's context needs no such test. Carry out what the fresh-agent writes. Separately, run each command the message names, so that a command, path or flag that does not work fails a test. `python3 scripts/agent-facing-message-ask-two-fresh-agents-next-step-and-check-named-script-flags.py --message-file MESSAGE --situation-file SITUATION` does the fresh-agent part of this: it prints what two fresh-agents say they would do next, and whether each script the message names exists and lists in its `--help` each flag the message gives it, but it carries out nothing and runs none of the commands.
