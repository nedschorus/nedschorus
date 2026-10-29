# Code-prompt-code: when a step given to an agent becomes code, and when it stays with the model

This page is for an agent that writes or reviews a text giving steps to a model or a person: a `CLAUDE.md` line, a skill step, an `-instructions.md` file, the prompt a program gives a subagent, or a message a program prints to an agent, such as a hook's refusal or a script's error. For each step in that text, it says whether the step should be done by code or stay with the model, the split that code-prompt-code (CPC) programs are built on. The glossary, `docs/nedschorus-wiki/nedschorus-glossary.md`, says what code-prompt-code is, and `docs/nedschorus-wiki/nedschorus-ai-native-software-development-objective.md` says why the project builds that way; this page says how to decide, one step at a time.

## Where to look

Look hardest at a text that adds or changes standing instructions for an agent, and at an approval-walk item that proposes one. Of the 107 times from July to October 2026 that the user asked an agent whether what it had just shown him could be code-prompt-code, 84 answered an approval-walk item, and since 2026-10-15, 45 of 64 answered a text that said it added or changed an instruction, or that named `CLAUDE.md`, a skill or an `-instructions.md` file. No test that code can run on a text, such as its length, its numbered steps or its verbs, picked out those texts in more than about 7% of the texts it matched, so no hook tells you when to look: you judge. The figures are from cold-read-research's study, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/cold-read-research/cpc-trigger-research-2026-10-28/cpc-trigger-research.md`.

A message a program prints to an agent gives the agent steps just as a Markdown file does, and no cold-read-fast-read reads it. In the 11 days from 2026-10-18 to 2026-10-28, 68 merged pull requests added such a message to a `.py` or `.sh` file, by cold-read-research's count in `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/cold-read-research/cpc-trigger-research-2026-10-28/cpc-question-measurement-2026-10-29.md`. Treat each one as you would a prompt.

## The split

A step is one hand-off of one piece of work to one actor; a sentence that makes three hand-offs is three steps. For each step, `docs/agents/sanity-checker-mechanization-adversarial-prompt.md` draws the line this project uses, in its two bullets beginning "The model handles" and "Code handles": the model keeps what needs interpretation, such as understanding ambiguous intent, classifying material whose meaning matters, and drafting open-ended text; code takes validation, parsing, calculation, state, sequencing, retries, filtering and formats. That prompt's four questions, Encode, Constrain, Externalize and Verify, are the way to go through a text step by step.

When a step moves into code, the program does only the normal case and hands every other case back to the agent with a message saying what failed, as the principle in [Move mechanical agent chores into programs and hooks](https://github.com/nedschorus/nedschorus/issues/1036) says. What is left in the text for the agent is then two things: the judgment the program cannot make, and what to do with what the program hands back.

## When code is the wrong answer

Asked of any text, "what here could be code?" finds something: cold-read-research gave that question to 65 texts from the transcripts, and every answer named at least two steps. So a step that code could do still stays with the model, or stays as it is, in any of these four cases:

- **The step needs judgment.** Deciding whether a review finding still holds, or which findings belong in one pull request, is interpretation; code can carry the step's order and record its answer, but not make the call.
- **The step already works.** "A step that works reliably today, costs little, and fails loudly is not a finding", in the words of the mechanization prompt.
- **The code would be a guard, a validation or a retry against a failure nobody has seen.** `CLAUDE.md` allows one only when the failure has happened, or is foreseeable within 30 days, and would lose or damage work, stop other work, or go unnoticed.
- **The text gives no steps.** Of 20 approval-walk items that cold-read-research judged by hand, 16 were summaries, definitions, judgment calls, or proposals already made in code.

The first case decided this page's own design: no pattern in a text predicts that the user will ask for code-prompt-code, so this page teaches the judgment with examples, instead of a hook that would tell an agent when to think of code. The third case is the second example below.

A rule that stays as text waits there only until a program enforces it, as rung 6 of `docs/nedschorus-wiki/nedschorus-enforcement-ladder.md` says.

## Examples from this project

### The prompt for answering a pull request's non-blocking findings

After merge-lane-2 merges a pull request, it can send the author non-blocking findings to follow up. A program prints the prompt a subagent follows to answer them. In both versions below, "Program:" stands for that program's command, which the cited file defines. Both versions, and what the program prints, are saved at `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/cpc-page-follow-up-brief-before-and-after-from-cold-read-research-2026-10-29.md`; the program was not on main when this page was written.

Before, the subagent was told to carry out five steps in order, with a loop over topics:

> For the subagent, in your own worktree:
> 1. Check each finding against origin/main; leave out any that no longer holds, and any that would change a design or decision of the user's, ending your report with a question to him on each of these.
> 2. Group the findings you take on by topic: one pull request per topic.
> 3. For each topic, Program: start-topic-branch <topic-branch>
>    Make the change with its tests, and commit.
>    Write follow-up-pull-request-title-and-description.md at your worktree's root: the title, a blank line, then the description. Do not commit it.
>    Program: open-pull-request --handled-finding-numbers <n>[,<n>...]
> 4. For each finding you leave out, Program: record-finding-leave-out-reason <n> --reason "<why>"
> 5. Program: finish-follow-up-request-and-print-merge-lane-2-message
>    Send the message it prints to merge-lane-2 with SendMessage.

The user asked "could this be more code prompt codey?", and on 2026-10-28 approved this after, as item 2.1 of cold-read-research's approval-walk cold-read-research-carried-items-2026-10-28:

> For the subagent, in your own worktree: Program: next-step. Do what it prints, then run Program: next-step again, until it prints "Done".

`next-step` fetches origin, reads what the program has recorded about which findings each topic branch took on and which findings have an answer, and prints only the step that comes next, such as:

> Next: topic branch <topic-branch> takes on findings <n> and <n>, which have no pull request yet.
> On that branch, make the change with its tests, and commit, unless you have.

What moved into code: the order of the steps, the loop over topics, the record of which findings are answered, the fetch, and the default for `--handled-finding-numbers`. What stayed with the model: judging whether a finding still holds or needs the user's decision, grouping the findings by topic, and writing the change and its pull request description.

### The conflict check before a push

On 2026-09-23, merge-lane put to the user, as item 2.1 of an approval-walk, a new `CLAUDE.md` sentence for every agent to follow:

> Before you push a branch, and whenever you read that its pull request conflicts with main, run `scripts/branch-conflict-check.py --pull-request <n>` from the branch's checkout, leaving out `--pull-request` before the pull request exists, and do what its VERDICT line says: exit 0 is clean, 1 is a conflict to merge by hand, 2 is no answer.

The user answered: "2.1 sounds reasonable, but this looks like it should be a script, not a prompt" (line 278 of `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/mac/projects/-Users-el-agents-merge-lane/7807f5bd-d1ee-4609-aefd-ea669f68ce67.jsonl`). The same day, commit 3a1c60029, "A pre-push hook refuses to push a branch that conflicts with main", made `scripts/git-client-side-hooks/pre-push` run the conflict check on every push, through `scripts/git-client-side-hooks-pre-push-conflict-check.py`. Remembering to run the check, and reading its exit code, moved into code. `CLAUDE.md` keeps one sentence, for the case the program hands back: "When `scripts/branch-conflict-check.py` reports `VERDICT: CONFLICT`, do what its report says." What to do about a conflict stays with the agent.

### A hook's refusal message, and the retry left out

On 2026-10-17, agent-instructions-editor put to the user, as item 10 of an approval-walk, a new message for `.claude/hooks/session-location-write-guard.py` to print when git failed while the guard checked a write from a detached HEAD. The message told the agent to run `git status` and then tell four cases apart, starting:

> Run git status: it says whether a rebase, merge, cherry-pick or revert is stopped here.
> If git status fails too: tell the user what it printed; until git works in this checkout, this guard refuses every write from a detached HEAD here.
> If an operation is stopped here: try the write again, because this guard checks again on every call. [...]

The user asked "could this be CPC?" (line 5984 of `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/ned-box/projects/-home-nedlern-agents-agent-instructions-editor/fd3dde6d-34c5-4198-9aa4-1209e4d8b1a6.jsonl`). The agent's answer moved telling the cases apart into the guard: when git fails, the guard checks again by itself, and only when git fails both times does the agent get a message, which shrank to three lines. The same answer named the cost, a retry and a test for each outcome, against a failure nobody had yet seen, and recommended leaving the retry out until one was. The user's answer, at lines 6003 to 6039 of the same file, led to the rule in `CLAUDE.md` that the third case above quotes, added the same day in commit 6d6ad8bb4: a guard is worth building against a failure foreseeable within the next 30 days, and "there isn't much reason to guard against quickly and easily corrected failures like the one you just cited, as long as the agent will notice that error." The guard on main, `.claude/hooks/session-location-write-guard.py`, has no retry.

## Related pages

- `docs/agents/sanity-checker-mechanization-adversarial-prompt.md`: the split and the four questions, in full.
- `docs/nedschorus-wiki/nedschorus-enforcement-ladder.md`: the rungs from a rule that cannot be broken down to a rule kept only as text.
- [Move mechanical agent chores into programs and hooks](https://github.com/nedschorus/nedschorus/issues/1036): eleven chores agents do by hand that a program could do, and the principle that the program does only the normal case.
