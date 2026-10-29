# Code-prompt-code: when a step given to an agent becomes code, and when it stays with the model

This page is for an agent that writes agent-instructions, such as a `CLAUDE.md` line, a skill step, an `-instructions.md` file or the prompt a program gives a subagent, or that writes an agent-facing-message, such as a hook's refusal or a script's error. A step is one hand-off of one piece of work to one actor, a model or a person; a sentence that makes three hand-offs is three steps. For each step, the page says how to decide whether code should do it, or whether it should stay with the model, meaning the agent that follows the text, or with the person it was given to. That split is what code-prompt-code (CPC) programs are built on. The glossary, `docs/nedschorus-wiki/nedschorus-glossary.md`, says what code-prompt-code is, and `docs/nedschorus-wiki/nedschorus-ai-native-software-development-objective.md` says why the project builds that way.

## Where to look

Look hardest at a text that adds or changes agent-instructions, whether one line of an existing file or a whole new file, and at an approval-walk item that proposes such a text. The agent-seat cold-read-research searched the transcripts from July to October 2026 and found 107 messages in which the user asked or said that what an agent had shown him could be code, a script or code-prompt-code. By its later classification, 84 of the 107 answered an approval-walk item; and since 2026-10-15, 45 of 64 answered a text that said it added or changed an instruction, or that named `CLAUDE.md`, a skill or an `-instructions.md` file. These are pointers to where to look, not a way to decide: of the heuristics it tested on a text's surface, such as its length, its numbered lines or its verbs, none with enough matches to judge was followed by such a request on more than about 7% of the texts it matched. Whether a step should be code is judged step by step. The figures are in two reports: `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/cold-read-research/cpc-trigger-research-2026-10-28/cpc-trigger-research.md` and, for the 84, section 3 of `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/cold-read-research/cpc-trigger-research-2026-10-28/cpc-question-measurement-2026-10-29.md`.

An agent-facing-message gives an agent steps just as a Markdown file does. One put to the user as an approval-walk item gets a cold-read-fast-read, but one written straight into a `.py` or `.sh` file gets none, and a pull request reviewer gives the English of such a message no finding, by `CLAUDE.md`'s review scope. So the agent that writes an agent-facing-message is the one who goes through its steps as this page says. In the 11 days from 2026-10-18 to 2026-10-28, a string match found such text added to `.py` or `.sh` files in 68 merged pull requests, by section 4 of the second report above; 9 of the 10 hits it checked by hand were real agent-facing-messages.

## The split

The mechanization-adversarial-prompt, `docs/agents/sanity-checker-mechanization-adversarial-prompt.md`, draws the line this project uses, in its two bullets beginning "The model handles" and "Code handles". In short: the model keeps what needs interpretation, such as understanding ambiguous intent and drafting open-ended text; code takes work where variability adds nothing, such as validation, parsing, calculation, state transitions, sequencing and formatting contracts. The prompt's bullets have the full lists, and its four questions, Encode, Constrain, Externalize and Verify, are the way to go through a text step by step.

When a step moves into code, the program does the normal case and hands every other case back to the agent with a message saying what failed, as the principle in [Move mechanical agent chores into programs and hooks](https://github.com/nedschorus/nedschorus/issues/1036) says. The program does not try to handle a case an agent would handle; `CLAUDE.md` allows it a retry only for a passing fault, on an operation safe to repeat, with a limit on attempts. What is left in the text for the agent is then two things: the judgment the program cannot make, and what to do with what the program hands back.

When the answer for a step is code and the program does not exist yet, the text keeps the step until the program merges, as rung 6 of `docs/nedschorus-wiki/nedschorus-enforcement-ladder.md` says of a do-or-not-do rule; the ladder keeps a governing principle as text for good.

## When code is the wrong answer

Asked of a text, the mechanization-adversarial-prompt's question nearly always finds something: cold-read-research gave a version of the question to 65 texts of 80 words or more from the transcripts, and every answer named at least two steps that code could do or check. So before you propose code for a step, check it against these four cases; in any of them, the step stays where it is, with the model, the person, or the code that already does it:

- **The step needs judgment.** Deciding whether a review finding still holds, or which findings belong in one pull request, is interpretation. Code can carry the order of such a step and record its answer, but cannot make the call.
- **The step works reliably today, costs little, and fails loudly.** In the mechanization-adversarial-prompt's words, such a step "is not a finding": a mechanism could do it, but would not pay for itself.
- **The code would be a guard, a validation, a retry or a workaround that `CLAUDE.md`'s rule does not allow.** The rule allows one only when "the failure has happened, as a citation from the user, an agent or a machine shows, or concrete evidence shows it is foreseeable within the next 30 days; and it would lose or damage work, stop work beyond the task that failed, or go unnoticed until it does one of those."
- **Nothing in the text is a step code could take.** Of 20 approval-walk items that cold-read-research judged by hand, chosen from items the user did not ask about, 16 were summaries, definitions, judgment calls, or proposals already made in code.

The first case decided this page's own design. The surface heuristics above predicted the user's requests only weakly, at best about twice as often as chance, so this page teaches the judgment with examples, instead of a hook that would tell an agent when to think of code.

## Examples from this project

### The prompt for answering a pull request's non-blocking findings

After merge-lane-2 merges a pull request, it can send the author non-blocking findings to follow up. A program prints the prompt a subagent follows to answer them. Both versions of that prompt below, and what the program prints, are saved at `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/cpc-page-follow-up-brief-before-and-after-from-cold-read-research-2026-10-29.md`, which also gives the program's command; in both versions, "Program:" stands for that command. The program was not on main when this page was written, so its behaviour below is as that file describes it.

The earlier version gave the subagent five numbered items to carry out in order, with a loop over topics; each "topic branch" in it is an nc-topic-branch:

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

The user asked "could this be more code prompt codey?", and on 2026-10-28 approved the following one-line version as item 2.1 of cold-read-research's approval-walk cold-read-research-carried-items-2026-10-28, whose walk-document is on the Mac at `/Users/el/agents/cold-read-research/docs/walk/cold-read-research-carried-items-2026-10-28.md`:

> For the subagent, in your own worktree: Program: next-step. Do what it prints, then run Program: next-step again, until it prints "Done".

`next-step` fetches origin, reads what the program has recorded about which findings each nc-topic-branch took on and which findings have an answer, and prints only the step that comes next, such as:

> Next: topic branch <topic-branch> takes on findings <n> and <n>, which have no pull request yet.
> On that branch, make the change with its tests, and commit, unless you have.

That step ends "Then run: Program: open-pull-request", with no finding numbers to type. Its last output begins "Done:". The prompt can be one line because each step the program prints carries that step's own instructions, such as the step that opens "Next: judge findings <n> and <n>, which have no answer yet".

What moved into code: the order of the steps, the loop over topics, working out from the program's record which findings still need an answer, the fetch, and the finding numbers that `open-pull-request` used to be given. What stayed with the model: judging whether a finding still holds or needs the user's decision, grouping the findings by topic, and writing the change and its pull request description.

### The conflict check before a push

On 2026-09-23, the agent-seat then named merge-lane, on the Mac, put to the user, as item 2.1 of an approval-walk, a new `CLAUDE.md` sentence for every agent to follow:

> Before you push a branch, and whenever you read that its pull request conflicts with main, run `scripts/branch-conflict-check.py --pull-request <n>` from the branch's checkout, leaving out `--pull-request` before the pull request exists, and do what its VERDICT line says: exit 0 is clean, 1 is a conflict to merge by hand, 2 is no answer.

The user answered: "2.1 sounds reasonable, but this looks like it should be a script, not a prompt" (line 278 of `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/mac/projects/-Users-el-agents-merge-lane/7807f5bd-d1ee-4609-aefd-ea669f68ce67.jsonl`). The same day, commit 3a1c60029, "A pre-push hook refuses to push a branch that conflicts with main", made `scripts/git-client-side-hooks/pre-push` run the conflict check, through `scripts/git-client-side-hooks-pre-push-conflict-check.py`, on each branch pushed to origin other than main. Remembering to run the check before a push, and reading its exit code, moved into code. The hook hands back two cases: a refusal when the check reports a conflict, and, when the check cannot give an answer, a line telling the agent to run `scripts/branch-conflict-check.py` by hand. `CLAUDE.md` keeps one sentence: "When `scripts/branch-conflict-check.py` reports `VERDICT: CONFLICT`, do what its report says." What to do about a conflict stays with the agent.

### A hook's refusal message, and the retry left out

On 2026-10-17, the agent-seat agent-instructions-editor put to the user, as item 10 of the approval-walk agent-instructions-editor-every-open-decision-2026-10-15, a new agent-facing-message for `.claude/hooks/session-location-write-guard.py` to print when git failed while the guard checked a write from a detached HEAD. The message told the agent to run `git status` and then tell four cases apart, starting:

> Run git status: it says whether a rebase, merge, cherry-pick or revert is stopped here.
> If git status fails too: tell the user what it printed; until git works in this checkout, this guard refuses every write from a detached HEAD here.
> If an operation is stopped here: try the write again, because this guard checks again on every call. [...]

The user asked "could this be CPC?" (line 5984 of `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/ned-box/projects/-home-nedlern-agents-agent-instructions-editor/fd3dde6d-34c5-4198-9aa4-1209e4d8b1a6.jsonl`). The agent's answer proposed moving the telling apart into the guard: when git failed, the guard would check again by itself and act on the second answer, and only when git failed both times would the agent get the new message, shrunk to three lines. The same answer named the cost, a retry and a test for each outcome, against a failure nobody had yet seen, and recommended leaving the retry out until one was. The user's answer, at lines 6003 to 6039 of the same file, asked for a likely failure, not only a seen one, as the test, and said that "there isn't much reason to guard against quickly and easily corrected failures like the one you just cited, as long as the agent will notice that error." Commit 6d6ad8bb4 wrote that answer into the `CLAUDE.md` rule the third case above quotes. Neither the message nor the retry was built: when git cannot answer, the guard on main lets the write go ahead and tells the agent it could not check it.

## Related pages

- `docs/agents/sanity-checker-mechanization-adversarial-prompt.md`: the split and the four questions, in full.
- `docs/nedschorus-wiki/nedschorus-enforcement-ladder.md`: the ways a rule is enforced, ordered by when each acts, from a bad state that cannot arise without a deliberate override to a rule kept only as text.
- [Move mechanical agent chores into programs and hooks](https://github.com/nedschorus/nedschorus/issues/1036): eleven chores agents do by hand that a program could do, and the principle that the program does only the normal case.
