---
issue: "[A wiki page on when a step given to an agent should become code and when it should stay with the model, with before-and-after examples of code-prompt-code from this project](https://github.com/nedschorus/nedschorus/issues/2127)"
---

# A wiki page on when a step given to an agent should become code and when it should stay with the model, with before-and-after examples of code-prompt-code from this project

## What is wanted

A new wiki page that tells an agent, when it writes or reviews a text that gives steps to a model or a person, which of those steps belong in code and which stay with the model, the split that code-prompt-code (CPC) programs are built on. The page shows before-and-after examples taken from this project, says plainly when code is the wrong answer, and is the one place the project explains the subject: other texts link to the page instead of repeating it.

The page goes where `docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md` puts a wiki page: `docs/nedschorus-wiki/queue/` while it awaits the user's approval, and `docs/nedschorus-wiki/` once he approves it. A suggested name, which a fresh subagent read correctly from the name alone, is `nedschorus-code-prompt-code-when-an-agent-step-becomes-code-or-stays-with-the-model.md`; the page's author may choose another by `docs/nedschorus-wiki/nedschorus-how-to-choose-a-name-for-files-code-and-glossary-terms.md`.

## Why

The user often has to ask an agent whether what it just showed him could be code-prompt-code. cold-read-research's study of the transcripts, cited below, found 107 confirmed requests from July to October 2026, 79 of them in October, in 23 agent-seats: since 2026-10-15, about 1 in every 36 assistant turns the user answered (64 of 2,278) drew a request.

No text on main says when to use code-prompt-code. The glossary entry, line 33 of `docs/nedschorus-wiki/nedschorus-glossary.md`, says what code-prompt-code is: "a program built from both code and prompts". The paragraph at line 17 of `docs/nedschorus-wiki/nedschorus-ai-native-software-development-objective.md` says why the project builds that way: code gives reliability, testability and speed, prompts give flexibility, and "proven prompts can be replaced with code". Neither says how to tell, for one step in one text, which kind the step should be, and neither shows an example.

The user approved this GHI as item 2.2.1.2 of cold-read-research's approval-walk cold-read-research-carried-items-2026-10-28, on 2026-10-29 by cold-read-research's account. The walk-document is on the Mac, at `/Users/el/agents/cold-read-research/docs/walk/cold-read-research-carried-items-2026-10-28.md`; its walk-minutes go to `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/` when the approval-walk closes, and were not there on 2026-10-28. In his words: "I approve this new GHI, but I think this is something we should do sooner rather than later, so I would also make it a task." Earlier in the same approval-walk he said the page should be "a well-written page on code prompt code and when it should be used", and: "we have a month of examples now, so that should be a pretty damn good page."

## The earlier attempt

GHI [code-prompt-code (CPC) design philosophy wiki page: systems as state machines whose nodes are code or prompts](https://github.com/nedschorus/nedschorus/issues/237) asked for a page on the design idea: systems as state machines whose nodes are code or prompts. It was closed as not planned on 2026-09-21, because the objective page and the glossary already carried that idea; its outcome says "Re-file if a dedicated page is later wanted." This GHI is that re-filing, with a narrower subject: not the idea, which the objective page keeps, but the decision for each step, taught from examples the project did not have in September.

GHI [Move mechanical agent chores into programs and hooks](https://github.com/nedschorus/nedschorus/issues/1036) is related and separate: it lists eleven chores to move into programs, and states the principle that a program does only the normal case and hands every other case back to the agent with a message saying what failed. The new page links to that principle rather than restating it, and may use those chores as examples.

## What the page draws from

### cold-read-research's two research reports

Both are in the log-store:

- The trigger research, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/cold-read-research/cpc-trigger-research-2026-10-28/cpc-trigger-research.md`, which collected the 107 requests and tested whether a program could predict them from the text the user saw.
- The question measurement, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/cold-read-research/cpc-trigger-research-2026-10-28/cpc-question-measurement-2026-10-29.md`, which tested a question an agent can ask of any text, "what should be code", on 65 texts from the transcripts, and traced where each request's text was when the user asked.

What the page takes from them:

1. **Where the requests come from.** Most requests answer a text that adds or changes standing instructions for an agent, such as a CLAUDE.md line, a skill step, an `-instructions.md` file or the prompt a program gives a subagent: a pattern for such texts catches 45 of the 64 requests since 2026-10-15. 84 of the 107 answer an approval-walk item. The page's examples come mostly from these texts.
2. **The decision is a judgment.** No pattern that code can test on a text, such as its length, its numbered steps or its verbs, predicts a request in more than about 7% of the texts the pattern matches, apart from one pattern that matched only 13 texts. So the page teaches the judgment, with examples, instead of relying on a hook to say when to think of code.
3. **The split between code and the model.** The question measurement gave each of its 65 texts the question from `docs/agents/sanity-checker-mechanization-adversarial-prompt.md`. The question named steps that code could do in every text, 5 to 7 on average, and in a hand check of 5 texts, each of the 5 named a step code could really do. The page uses that prompt's split, the model for what needs interpretation and code for validation, parsing, sequencing, state, retries and checks, and cites the prompt rather than copying it.
4. **When not to.** The same measurement shows that the question alone suggests code for nearly everything, so the page needs a limit. Sources for the limit: the prompt's sentence "A step that works reliably today, costs little, and fails loudly is not a finding"; CLAUDE.md's rule that a guard or a validation is added only for a failure that has happened or is foreseeable and would lose work, stop work or go unnoticed; and the 16 of 20 texts in the trigger research's hand-judged sample that were summaries, definitions, judgment calls or already code, as examples where code was not the answer.
5. **Before texts.** The trigger research's section "Five example cases" quotes five requests, each with the log-store file and line of the transcript, such as a guard's refusal message that told the agent to make a branch by hand, and a subagent's prompt that told it to delete worktrees and branches one by one. Each is a candidate "before". Where code was later built for a case, the "after" is that code and the shorter text that calls it. Where nothing was built, the page either shows what code could take over, saying that it is not built, or leaves the case out.
6. **Program messages are instructions too.** Text a program prints to an agent, such as a hook's refusal or a script's error, also gives an agent steps. In the 11 days from 2026-10-18 to 2026-10-28, 68 merged pull requests added such text to a `.py` or `.sh` file. The page covers this kind of text alongside Markdown.

### The follow-up request example

The main before-and-after example is the prompt a subagent follows to answer a pull request's non-blocking findings after the merge. Before, the prompt listed five steps for the subagent to carry out in order, with loops over topics and findings. After, the prompt is one line: run the program's next-step command, do what it prints, and run it again until it prints "Done". The program tracks which findings are answered and prints only the step that comes next. What moved into code: the order of the steps, the loop over topics, the record of answered findings, the fetch and the defaults. What stayed with the model: judging whether a finding still holds, grouping findings by topic, and writing the change and its pull request description. The user approved the after text on 2026-10-28, as item 2.1 of the same approval-walk, after asking "could this be more code prompt codey?". The page shows both prompts and at least one step the program prints, so that a reader sees what the one-line prompt relies on.

Both prompts, and examples of what next-step prints, are saved at `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/cpc-page-follow-up-brief-before-and-after-from-cold-read-research-2026-10-29.md`. The program, `scripts/pull-request-follow-up-request-findings-open-pull-requests-or-record-leave-out-reasons-and-clean-up.py`, is not yet on main: on 2026-10-28 it was an unpushed build in cold-read-research's worktree on the Mac. The page's author takes the final text of the example from cold-read-research. If the program is on main when the page is written, the page cites it by path; if not, the page cites the log-store file above instead, and does not wait for the program.

## Texts that link to the page instead of repeating it

The pull request that adds the page also changes these two texts, so that each keeps its one line on the subject and links to the page for the rest:

- the glossary entry for code-prompt-code, line 33 of `docs/nedschorus-wiki/nedschorus-glossary.md`;
- the paragraph on code-prompt-code, line 17 of `docs/nedschorus-wiki/nedschorus-ai-native-software-development-objective.md`.

The page itself links to `docs/nedschorus-wiki/nedschorus-enforcement-ladder.md`, whose rung 6 says a do-or-not-do rule stays as text only until a program enforces it, rather than repeating that rung.

After the page merges, cold-read-research adds further links to the page: from the new "Question 4: What should be code" of the cold-read-fast-read, from the copy of that question in the cold-read-full-run, from a line in CLAUDE.md, and from a new glossary entry that cold-read-research chooses. Those changes are cold-read-research's, not part of this GHI's pull request.

## Search for an existing GHI

On 2026-10-28, `scripts/ghi-info-ask.py --include-closed`, asked for any GHI, open or closed, or GHI-MD, about a page on when to use code-prompt-code, or about deciding which agent steps should be code, returned GHI 237 (closed, cited above) and GHI 1036 (open, a different subject, cited above), and found no GHI on a "what should be code" question in the cold-read-fast-read.

## Next action

The user wants this done soon, so the agent-seat that takes it on puts it on its own task list as well.

1. Read the two research reports and the before-and-after file above, and ask cold-read-research for the final text of the follow-up request example.
2. Write the page on a topic branch from origin/main. In the same pull request, change the glossary entry and the objective page's paragraph to link to the page, as the section above says.
3. Give the page its /cold-read, which for a wiki page includes a cold-read-full-run, then open the pull request; merge-lane-2 reviews and merges it.
4. When the pull request merges, tell the agent-seat cold-read-research, with Claude Code's SendMessage tool, the page's path, so that cold-read-research adds its links.
