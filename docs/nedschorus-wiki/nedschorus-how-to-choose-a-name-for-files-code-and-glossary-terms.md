# How to choose a name for files, code and glossary terms

This page says how to choose every name this project invents: file and directory names, script names, the names of functions, classes, constants and states used from other files, branch names, and the terms the glossaries define, project-terms and system-terms alike. CLAUDE.md states the naming rule in brief and points here; where the two differ, this page governs.

Two kinds of name are partly decided elsewhere, and this page fills in the rest:

- **Names set outside the project.** `CLAUDE.md`, `SKILL.md`, `AGENTS.md`, a test framework's `test_` prefix, and the flags another program accepts are fixed by the tools that read them. Keep what is fixed; choose the remaining words by this page.
- **Names that follow a pattern in the file naming standards.** `docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md` gives patterns for kinds of file, such as `nedschorus-<subject>.md` for a wiki page or `<what it does>.py` for a hook, and filename suffixes such as `-draft`. Follow the pattern exactly, and use this page to choose the words that fill each slot in it.

## Why names matter so much in this project

Most readers of this project's names are agents that meet a name away from where it is defined. An agent finds a name in a `grep` result, in a list of files, in a hook's refusal, or in a message from another agent-seat, and decides from the name what to open or run next. A name that only makes sense to the agent that coined it costs every later reader a search.

Worse, without naming rules, agents often coin a second name for something that already has one. When that happens, the vocabulary splits: a `grep` for one name misses the places that use the other, and two agents describe one thing in two ways. That is why Step 1 asks you to look for an existing name before you make one, and why the glossaries exist.

## The naming criterion every name must meet

A fresh-reader who meets the name can tell what it names.

A fresh-reader here has the name, the glossaries, and what the glossaries reference, as a cold-read-cell has its document and what the document references; the fresh-reader does not have the file the name is defined in, or the agent-session in which the name was coined. The glossaries are allowed because a project-term or a system-term is meant to be looked up: its hyphens tell the reader it is a term, and its glossary entry says what it means. So `log-store` and `agent-seat` meet the criterion, and so does a longer name built from such a term, such as `cold-read-record-ship.py`, which says it ships a cold-read-record.

"Tell what it names" means the reader can say what kind of thing it is and which one, well enough to pick the right file to open or the right program to run. It does not mean the reader can use the thing without reading its documentation.

### Who judges whether a name meets the criterion

You cannot judge your own name, because you already know what it means. So for a name that will be used beyond the place it is defined, such as a file name, a script name, a function or class used from other files, or a branch name, ask a fresh subagent what it thinks the name means, giving it the name and nothing else. If its answer is wrong, or vague where your meaning is specific, add the words its answer lacked and ask again. A name used only inside one file needs no such check.

For a new project-term or system-term, the user rules on the name, as Step 5 says.

## Step 1: look for an existing name for the thing

If the thing you are naming already has a name in this project, use that name. Do not invent a second one.

Look in three places, in this order:

1. **The glossaries.** The project glossary, `docs/nedschorus-wiki/nedschorus-glossary.md`, lists the project-terms, and lists at its top the system glossaries, each of which lists the system-terms of one system: today `.claude/skills/skills-glossary.md` for every skill, `docs/design-to-main/design-to-main-glossary.md` for design-to-main, and `nc-systems/main-gatekeeper/main-gatekeeper-glossary.md` for the main-gatekeeper.
2. **The SDLC-terms.** When a standard term of software engineering or another computing field fits, such as worktree, pull request or test double, use it with its standard meaning, as an SDLC-term. `docs/nedschorus-wiki/nedschorus-sdlc-terms.md` lists the few this project relies on most; a standard term that is not on that list may still be used as it is.
3. **The code and documents.** Search your checkout and main for words that describe the thing, not only for the name you have in mind, because the thing may already exist under a name you would not guess: run `git grep -i <word> origin/main` for each word, after `git fetch` (see Step 3 for what to do if the fetch fails).

If an existing name fails the naming criterion, reuse it anyway, but tell the user it should be renamed: renaming it is a separate change, and a second name for the same thing is worse than one weak name.

## Step 2: build the name from three questions

A name that meets the naming criterion usually answers three questions by itself. Each answer is one part of the name, and a part may be one word or several: `main-gatekeeper-check-in-request-holder` has three parts and six words.

1. **Which system or skill does it belong to?** For example, `main-gatekeeper`, `cold-read`, `sanity-check`, `handoff`. Use the system's existing name exactly, as Step 1 found it.
2. **What does it act on, or hold?** For example, a `check-in` request, a cold-read-record, a branch.
3. **What does it do, or what is it?** For example, it holds, it starts, it checks, it copies; or, for a name of stored data, what the data is, such as minutes or records.

### Two worked examples

The main-gatekeeper is the program that will be the single route by which a change reaches main; its build plan is `docs/issues/3-main-gatekeeper-build-slice-plan.md`. That plan first named two of the program's processes `request-holder` and `spawner`.

- `request-holder` answers the third question, holds, and only vaguely the second: a request, but which program's request, and what kind? The first question it does not answer at all. The approved name is `main-gatekeeper-check-in-request-holder`: `main-gatekeeper` answers the first question, `check-in-request` the second, and `holder` the third, which is to hold the request and its lock until the work ends.
- `spawner` answers the third question, and leaves the reader asking what it starts, and for which program. The approved name is `main-gatekeeper-worker-spawner`, which adds the system and the thing it starts, the worker.

### Existing names that answer the questions

- `nc-systems/cold-read/cold-read-record-ship.py`: the skill is cold-read; it acts on a cold-read-record; it ships the record, which here means copying it to the log-store.
- `scripts/branch-conflict-check.py`: it acts on a branch and checks it for a merge conflict. It belongs to no single system, and its name says so by naming none (see "Where a rule above does not apply").
- `nc-systems/handoff/handoff-supervisor.py`: the system is the handoff system, and the program supervises it.

A name can also fail the third question by saying something untrue. `.claude/hooks/ghi-issue-write-redirect.py` refuses a write to a GitHub issue typed by hand and tells the agent which command to run instead; it does not redirect the write anywhere. Its name says "redirect", so a reader expects the write to have gone through by another route. Step 4 covers this.

### Order the parts from the system to the role

Put the system or skill first, then what it acts on or holds, then what it does or is: `main-gatekeeper-worker-spawner`, not `worker-spawner-for-the-main-gatekeeper`; `cold-read-record-ship`, not `ship-cold-read-record`. Names that share a system then sort together in a file listing, and a search for the system's name finds them, in every spelling Step 5 allows.

### Use as many words as the naming criterion needs

Three to nine words is normal for a name used beyond the place it is defined. Stop adding words when a fresh-reader can tell what the name names. Do not drop a word because every name around it shares that word: the name will also be met alone, in a search result or a message, where its neighbours are not there.

This page sets no upper limit: some studies favour names of two to four words, and others found that longer, more descriptive names were understood faster. This project's names are mostly read by agents with no context, so this page favours the longer name.

### Generic words are fine inside a longer name

Generic words, such as `manager`, `handler`, `helper`, `common`, `data`, `info`, `record` or `check`, say almost nothing alone. As one word of a longer name whose other words say which one, they are fine: `nc-systems/cold-read/cold-read-cell-common.py` says it holds the code the cold-read-cells share. What fails is the bare word, or a name such as `seat-manager`, which leaves the reader asking what it does to which agent-seat.

### Name a test file after what it tests

A test file takes the name of the program it tests, with `-test` before the extension: `scripts/branch-conflict-check-test.py` tests `scripts/branch-conflict-check.py`. When one program has more than one test file, each adds the fewest words that tell it apart from the others, naming the behaviour it covers rather than every case inside it: `handoff-supervisor-successor-prompt-test.py` and `handoff-supervisor-session-launch-and-seat-lock-test.py` both test `nc-systems/handoff/handoff-supervisor.py`. A test file that lists every case it holds grows a name no one reads; one that covers so much that a few words cannot say what sets it apart is better split.

## Step 3: check the name you built against the names that exist

Step 1 looked for an existing name for the thing. Now check that the name you built is not already used for something else, and does not sit too close to one that is.

1. Search your checkout: `git grep -i -E '<pattern>'`.
2. Run `git fetch`. If it fails, stop this check, tell the user that main could not be checked and why, and do not use the name until the check has run.
3. Search main: `git ls-tree -r --name-only origin/main | grep -i -E '<pattern>'` for paths, and `git grep -i -E '<pattern>' origin/main` for names used inside files.
4. Search the open pull requests, where other agent-seats are naming things at the same time: `gh pr list --repo nedschorus/nedschorus --state open --search '<words>'`, and look at the branch names it lists.

Build `<pattern>` so it matches every spelling of the name and its near neighbours, not only the exact string: write `[-_]?` between words so that `agent-seat`, `agent_seat` and `AgentSeat` all match `agent[-_]?seat`, and search for each word on its own as well when the name is short.

A name is too close to an existing one when a reader or a search could take one for the other: names that differ by one letter (`log-store-reader` beside `log-store-header`), or only by the order of their words (`review-count` beside `count-review`). Choose more words that tell them apart. A plural that names a collection of the singular is not too close: `cold-read-records/` holds cold-read-records, and the pair is clear.

## Step 4: make sure the name tells the truth

A name must not claim something the thing does not do, and must not leave out the main thing it does. A script named `log-store-sync` that also deletes files the user made elsewhere misleads; `log-store-mirror-and-prune-stale-copies` says what it does. A name need not list every side effect, such as logging or taking a lock; it must not hide the effect a caller would be surprised by.

Do not put the history of the thing in its name. Words such as `new-`, `old-`, `-fixed` or `-final` say how a file was edited, not what it is, and become false at the next edit. A number or date that tells one instance from another is not history and is fine: a date in a log's name, such as `2026-10-05-naming-best-practice-research.md`; a generation number, such as the `NNNN` in a conversation-tail's name; an instance number, such as the agent-seat merge-lane-2; or a version that is part of what the thing is, such as a file format that stays version 2 after version 3 exists.

When a change makes a name untrue, rename the thing, and in the same commit update every reference to the old name in the repository: callers, imports, paths in scripts, and mentions in documents. Leave the references outside the repository as they are: git history, the log-store, the frozen copies inside cold-read-records, and text already written on GitHub. A change that leaves the name true, such as a bug fix, needs no rename.

Do not abbreviate, except with abbreviations the glossary lists, such as GHI and PR, or that any programmer reads without decoding, such as `id` and `url`. Write them in lowercase inside a name, as in `ghi-issue-write.py` or `pr-reviewer-instructions.md`. Use the abbreviation or the full words for a thing, not both: once `pull-request-` names one family of files, a new file in it does not start `pr-`.

## Step 5: use the same words everywhere, and coin new terms with the user

A name keeps the same words in the same order in prose, in file names and in code; only the separator and the capitals change, as each language's naming convention requires. The project-term `agent-seat` is written in kebab-case `agent-seat` in prose and in file names, snake_case `agent_seat` for a Python variable or function, `AGENT_SEAT` for a Python constant, and CapWords `AgentSeat` for a Python class. Other languages and formats follow their own convention: `AGENT_SEAT` for a shell environment variable, `--agent-seat` for a command line flag. Search with a pattern that matches every form, as Step 3 says.

A fixed name is written whole in the code, so a search finds it. Do not assemble a fixed name from fragments, as in `"agent" + "-seat"`. A name with a variable part, such as `<seat>-handoff.md` or a dated record directory, is built at run time from a template whose fixed words are written whole, such as `f"{seat_name}-handoff.md"`, so a search for `-handoff.md` finds the template.

### Hyphens in prose mark the project's own terms

In prose, a hyphenated phrase marks a project-term or a system-term, such as agent-seat, log-store or cold-read-cell, so a reader knows to look it up in a glossary. Do not hyphenate an ordinary phrase: write "a name of two words", not "a two-word name", and "nearly identical", not "near-identical". A name of a file, a program or a piece of code, written in backquotes, keeps its own hyphens; the backquotes mark it as a name, not a term.

### New project-terms and system-terms

A new term is coined only when no existing name and no SDLC-term fits, and it is proposed to the user, with a definition of one sentence, before it is used. The glossary entries for project-term and system-term say which is which. An approved project-term goes into the project glossary; an approved system-term goes into the glossary of its system. If the system has no glossary yet, propose one to the user, named `<system-name>-glossary.md` in the system's directory, and list it at the top of the project glossary.

## Where a rule above does not apply, and why

- **A name that belongs to the whole project names no system.** `agent-seat` and `log-store` belong to no single system, and a general tool such as `scripts/branch-conflict-check.py` serves them all. Adding the project's name, as in `nedschorus-agent-seat`, would add a word that every such name shares. The wiki's `nedschorus-` prefix is a pattern set by the file naming standards, and the pattern governs there.
- **An SDLC-term keeps its standard name.** `worktree`, `pull request` and `test double` mean the same thing to every programmer who knows them, and a reader who does not can look them up anywhere. A longer name of this project's own would hide that they are standard.
- **What is set outside the project stays as it is set**, as the opening of this page says.
- **A name used only inside one file** is left to the writer: this page does not govern it. A loop index `i`, an exception `error`, or a constant only its own file reads is found by a reader who already has the file open.

## Checklist

1. Did you look in the glossaries, the SDLC-terms and the code for an existing name for the thing, and reuse it if one exists?
2. Did a fresh subagent, given only the name, say correctly what it names? (Not needed for a name used only inside one file.)
3. Does the name say which system or skill, what it acts on or holds, and what it does or is, in that order, unless a case under "Where a rule above does not apply" covers it?
4. Did the searches of your checkout, main and the open pull requests, with a pattern for every spelling, find no name it could be taken for?
5. Does it tell the truth, with no history in it, and no abbreviation the glossary does not list or a programmer would have to decode?
6. Does it use the same words in prose, file names and code?
7. If it is a new project-term or system-term, has the user approved it, and is it in its glossary?
