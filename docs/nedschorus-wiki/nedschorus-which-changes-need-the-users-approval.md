# nedschorus: which changes need the user's approval

A change needs the user's approval only when it is on the list of changes that need approval below and is none of the exceptions after that list. Every other change is a pre-approved-change: make it, and do not report it to the user. If it later breaks something, report the breakage as you would any failure. Each edit is classified on its own. Only an edit on the list waits for the user, together with any edit in the same pull request that depends on it; an unrelated edit goes in its own pull request, as CLAUDE.md's rule that each pull request is atomic already requires. If you cannot tell whether a change is on the list or is an exception, ask the user.

A change is the difference an agent's work makes, from before it starts to after it finishes: in what any file, setting or data, in the repository or outside it, says, and in where it lives; how the commits are arranged is not part of it. The way an agent makes a change, whether by editing a file, writing a file anew, creating a new file and deleting the old one, moving a file or renaming it, is not the change: two ways that give the same before and after make the same change. Every rule on this page applies to the change, never to the way it was made, and is applied before the agent makes it. A change that only moves prose or a Markdown file, with every link and path to it in the repository updated and every program and agent the repository shows reading it still finding it, is a cosmetic-change.

## Changes that need approval

- A change to what agent-instructions, an agent-facing-message or a prompt a program hands to an agent tells an agent to do, such as `CLAUDE.md`, a seat-brief, a skill and its prompts, a subagent definition in `.claude/agents/`, an `-instructions.md` or `-prompt.md` file, a prompt built in Python, or a hook's refusal.
- A change to what a hook or a setting lets an agent do, or stops an agent doing.
- Adding, removing or reordering a step that agent-instructions or a program tell agents to follow.
- A change to what a document on main directs, decides or plans, including one a review finding asks for.
- A change to code or data that makes a program do other than its design or a user-ruling says. A program's design is the design document on main it was built from, such as a GHI-MD that is a design; a program with none has no design for this purpose.
- Choosing which term the project uses for a thing, coining a term, or adding, changing or removing a glossary entry.
- Creating a wiki page: a Markdown file in `docs/nedschorus-wiki/`, whether written there or moved in from elsewhere; moving a file into the wiki is never a cosmetic-change, though moving a page within the wiki can be.
- Rewording a sentence of prose when it is unclear which meaning is intended.
- A change to what a sentence that states a user-ruling says.
- A guard, validation, retry or workaround that `CLAUDE.md` says to raise as a question for the user.
- A change to code or data outside the repository, such as a crontab entry or a LaunchAgent.

## Exceptions: changes that need no approval, even when they fall under the list above

- A user-approved-change.
- An obvious-error-fix, which the project glossary defines; it covers prose only.
- A cosmetic-change; it covers prose only.
- The wording of a message a program prints, such as an error, a refusal or a warning, when the message still tells the agent to do the same thing. Only the message's words change, together with each test or document that quotes the old words, changed to quote the new; the code that fills in the message's placeholders does not change. Before pushing, the agent that changes the wording saves the new wording to a file in its scratchpad, runs a cold-read-fast-read on that file, and applies each finding that holds without changing what the message tells the agent to do.
- In prose: renumbering headings, steps or items; updating a citation; naming the source of a statement; adding an open question to a document without answering it. A number or heading that a program reads is data, and renumbering it is not this exception.
- Renaming a page, a file of any kind or a title to a term the project glossary or a system glossary already lists, with every reference in the repository updated, when nothing outside the repository, such as a crontab entry or a LaunchAgent, names it.
- Rewording a sentence of prose to remove an ambiguity or a contradiction, when the rest of the same document or the latest user-ruling on the subject settles which meaning is intended.
- Carrying out a decision the user already made: merging a clean pull request, deleting what he retired, closing a finished task or GHI, or recording the decision in a GHI's outcome section.

## Terms

### user-approved-change

A specific change the user approved before an agent makes it, approved-by-walk or approved in conversation. A "y" approves only the question it answers, not another proposal in the same message. The user's approval reaches an agent second-hand, through a task prompt or another agent's message, only when that text quotes his exact words for this change, with the agent-session and time he wrote them. A user-approved-change includes:
- a place that a change approved in this agent-session missed, fixed exactly as the change fixed the other places;
- carrying a user-ruling to a place that does not yet say what the user-ruling says, such as a program's message, a prompt, code, a test or another document, changing only what is needed to make the place say what the user-ruling says, with the user-ruling cited in the commit message.

### cosmetic-change

A change to prose that alters only its formatting or its place, never what it says. Only these count:
- formatting: whitespace, Markdown markup, or joining a paragraph, list item or table row broken across lines onto one line, as `CLAUDE.md` asks, with no word changed and no list or block structure changed;
- moving prose or a Markdown file to another place, as the paragraph that begins "A change is the difference an agent's work makes" says.

A spelling, grammar or punctuation fix is an obvious-error-fix, which the project glossary defines, not a cosmetic-change. A change to a part of a file that a program reads as data, such as a GHI-MD's first heading or a row of the word table in `docs/nedschorus-wiki/nedschorus-style-guide.md`, is never a cosmetic-change, however small.

## Prose, code and data

Each change is judged by the kind of text it changes. A file can hold more than one kind, and each part of it is judged by its own kind. A rule on this page that names no kind covers every kind.

Prose is text that people or agents read: Markdown, the commands and code examples inside it included; every comment other than one that says what a piece of code does or why or tells a program what to do; and the English of a message a program prints or a prompt a program hands to an agent, even when it sits inside a program's source.

Code is text that a program runs: source code, a test, a hook, a shell script, and a docstring or comment that says what a piece of code does or why or tells a program what to do. A program includes the operating system, a shell, git and Claude Code.

Data is text that a program reads for its values rather than runs: a settings file such as `.claude/settings.json`, a JSON or YAML file, an environment variable, a crontab entry, and a part of a Markdown file that a program reads, such as a GHI-MD's first heading or a table row a script parses. A part that people read and a program also reads is prose and data at once, and a rule that covers prose only, such as obvious-error-fix or cosmetic-change, does not cover it. `CLAUDE.md`'s rule for reviewing a pull request reviews data as it reviews code; this page treats data as a kind of its own only to decide what needs approval.

obvious-error-fix and cosmetic-change cover prose only, never code or data: a broken path in a script is a bug, fixed as any code change is, not an obvious-error. When it is unclear which kind a text is, ask the user. Logs are kept outside the repository, in the log-store, and this page does not cover them.

## How to ask, and how to make a change

"Ask the user" means: put the change to him and leave it unmade until he answers, going on with other work meanwhile. A subagent puts it to the agent that dispatched it instead, which asks the user.

A change to a file git tracks, or a new file meant for main, reaches main through a pull request, which merge-lane-2 merges, following `CLAUDE.md`'s rules for pull requests. A file meant to stay untracked, such as a seat-brief, is changed in place, with no pull request. The instruction-file guard (`.claude/hooks/instruction-file-guard.py`) refuses every write to a file it protects, seat-briefs included, until the agent writes the `.walk-approved` marker file: for a user-approved-change, with the user's quoted words; for any other change, with `#pre_approved_change` on its first line and, on its second, the exception the change falls under, or the words "on neither list" when the change is neither on the list of changes that need approval nor one of its exceptions; the guard's refusal gives the steps. No marker file lets a write into a Claude Code auto-memory directory, `~/.claude/projects/<project>/memory/`, through.

If you think a kind of change belongs on the list of changes that need approval or on the list of exceptions, add a task proposing it to your task list, and carry the task in your session-handoff if the agent-session ends before the user rules. Meanwhile, judge each change by the lists as they stand, including the change that prompted the proposal. When the work that prompted your first proposal is done, put every proposal you hold to the user in one approval-walk, even if there is only one.
