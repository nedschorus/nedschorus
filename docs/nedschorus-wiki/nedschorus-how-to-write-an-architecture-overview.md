# How to write an architecture overview

An architecture overview tells a reader who must change a system what the system is for, what its components are, and how the components fit together. It describes the system as it is on main at the commit named in its last line. It summarizes and points: it says in a sentence, or for a few in a short paragraph, what each component and each piece of shared state does and where it lives, and leaves the detail to the code and the documents that hold it.

The overview of a system whose code lives in `nc-systems/<system>/` is `docs/nedschorus-wiki/nedschorus-<system>-architecture-overview.md`, where `<system>` is the directory directly under `nc-systems/`. This page is `docs/nedschorus-wiki/nedschorus-how-to-write-an-architecture-overview.md`.

## What an overview contains

The overview has these seven sections, in this order. The words component, shared state and entry point keep their ordinary meanings; each item says what to write in that section.

1. **Purpose.** In one to three sentences, before naming any component, say what the system is for, what goes in and what comes out.
2. **Architectural pattern.** In one short paragraph, name the pattern the components form, such as a pipeline, a control loop, layers, or a supervisor and the process it launches; if the components are independent tools, say so. A diagram, as plain text in a code block with one row per component, may follow the paragraph.
3. **Components.** List the files that make up the system, its programs, prompts and configuration, each by its path in backticks, with one sentence on what it does; give a short paragraph instead to the few a reader must understand first. A directory may stand for the files in it when they serve one job. Include ones that live outside `nc-systems/<system>/`, such as shared scripts in `scripts/`. Do not list tests, the documents the system is run on, or programs from outside the repository, such as `claude` or `git`. Put the entry points first, then the rest in roughly the order a run reaches them; where there is no such order, any order will do. Write a hook as "`<path>`, a `<event>` hook".
4. **Invariants.** State each rule the code keeps across components that no single file states, especially an absence, such as "the launchers never start `claude` themselves; only the handoff-supervisor does", in one to three sentences, with its reason in at most one clause.
5. **Shared state.** For each file, lock, environment variable, git ref or other state that two or more components use, say which components create or write it and which read or wait on it, naming an outside program such as Claude Code or git where it is the writer, and say where it lives, naming the machine when that matters.
6. **Entry points.** For each component where execution starts, say what starts it: a person, a Claude Code hook event, a job in `nc-systems/general-tools/scheduled-jobs-on-each-machine.json`, or another system.
7. **Planned work.** List each open GHI that holds work on the system, one line each, written `GHI [<title>](<url>)`; find them with `scripts/ghi-info-ask.py` and a GitHub search for the system's name and directory. Do not list work recorded only on an agent-seat's task list.

## What an overview leaves out

- **How the system came to be.** No history: no dates of events, no user-rulings, no incidents, no review rounds, no "was replaced by", no pull request or GHI cited as provenance. A past fact stays only when a reader would otherwise misread something present, and then as one clause with no date or citation.
- **Design rationale beyond one clause.** A reason appears only as one clause attached to the component, invariant or shared state it explains. Rejected alternatives are not listed. The overview describes the system; it does not argue for it.
- **Implementation detail.** Flags, exit codes, timeouts, message texts, file formats, retry policies, edge cases, test files. Name the file that holds the detail and stop. What a component is for, such as "restarts the agent-session when the agent-session dies", is not implementation detail and belongs in its sentence.
- **Detail another document holds.** Link the document that is the canonical location; do not restate it. A one-sentence summary of a component is a summary, not a restatement.

## Improvements and problems the writer notices

While reading the code, a writer may notice something worth changing: an improvement, such as something to add, remove, simplify or archive, or a possible problem. None of it goes into the overview, which describes the system as it is, and Planned work does not list it. The writer records it in a proposed-improvements-or-changes-file beside the overview, as GHI [Proposed improvements or changes to a GHI are handled by agents first, and reach the user only when they need him](https://github.com/nedschorus/nedschorus/issues/1132) says for an architecture overview; the line that GHI puts under the overview's first heading stands before the seven sections and is not one of them. Until an agent exists to settle the file's entries, the file waits on main as a reminder.

## Length

Size an overview by its components: about one sentence each, and a short paragraph for the few a reader must understand first. For a system of about ten components that is roughly 300 to 800 words, Planned work aside. Measured architecture overviews of 18 open-source systems, from 500 to 2,000,000 lines of code, had a median of about 1,200 words and barely grew with the code (`nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/cold-read-improvement/overview-definition-research-2026-10-04/overview-length-versus-code-size-codex/report.md`). A section much longer than its components need usually holds something the list above leaves out.

## Terms

Use project-terms, the described system's system-terms where the system has a glossary, and SDLC-terms, without paraphrase.

## Keeping an overview true

The last line of an overview is `**Checked against:** commit [<full commit id>](https://github.com/nedschorus/nedschorus/commit/<full commit id>)`, naming the commit of main that the last check ran against. It is data a program reads, and it is the only commit the overview names.

An overview refresh brings an overview into line with the code on main and with this page. It reads the commits between the commit in the `**Checked against:**` line and main to find what changed; nothing about those commits goes into the overview. It corrects every statement that is no longer true, adds what the code added (a component, an invariant, shared state, an entry point), takes out what the code removed, takes out anything this page leaves out, and updates Planned work to the open GHIs. Then it replaces the `**Checked against:**` line with the commit it checked against. A refresh that finds nothing to change replaces only that line.

A refresh is due when a commit after the one in the `**Checked against:**` line changes a file under `nc-systems/<system>/`, a path the overview lists as a component, the hooks in `.claude/settings.json`, `nc-systems/general-tools/scheduled-jobs-on-each-machine.json`, or this page, or when the open GHIs on the system no longer match Planned work. Who runs a refresh, and when, belongs to the program that runs refreshes; this page says what a refresh does.

An overview already on main without a `**Checked against:**` line was written before this page. It is not edited; it is written anew from the code at the path this page gives for an overview, and the old file is deleted in the same pull request, with every link to it changed to the new path. The writer may read the old page for invariants and reasons, and keeps what still describes the code.

## Checking an overview

A new overview gets a cold-read-full-run of the /cold-read skill; a refresh gets a cold-read-fast-read (both terms are in `.claude/skills/skills-glossary.md`). Then the overview is checked against the code of main at one commit, the one its `**Checked against:**` line will name. A round is the check, the writer's fixes, and a cold-read-fast-read of the whole overview. The overview merges after a round in which the check found nothing to fix and the read changed nothing the check covers. If two rounds pass without that, the writer brings the overview to the user.

The check has two stages, and the second runs only once the first is clean.

1. **The overview checks of `scripts/md-drift-lint.py`** settle what a program can, and prints one `overview-path:line: problem` per finding: every repository path in backticks or in a link exists, paths outside the repository and paths holding a `<placeholder>` excepted; a component written as "`<path>`, a `<event>` hook" is registered under that event in `.claude/settings.json`; every lock name and environment variable in backticks appears in the source of a component named on the same line; every GHI under Planned work is open and its title is the link text. A GitHub query that fails stops the script with an error, not a finding. Separately, as a note and not a finding, it lists the programs under `nc-systems/<system>/`, outside `tests/`, that the overview does not name, for the writer to consider.
2. **A fresh-agent**, never a forked subagent of the writer, is given this page, the overview and the repository at that commit. It splits the overview into single assertions and checks every assertion about the code: each component's sentence, the architectural pattern and any diagram arrow, each invariant, each piece of shared state, each entry point, and the inputs and outputs. For each it looks first for a line that contradicts the statement, then for lines that bear it out, and gives one verdict: supported, with each file, line number and quoted line it rests on, or for an absence, the searches that found nothing, covering every component that could break it; contradicted, with the file, line number and quoted line; or unsupported, with the files it read and the searches it ran. It reports one row per assertion, then the count of each verdict.

The writer corrects or removes each contradicted statement and each script finding. For an unsupported statement, the writer names in it the files that bear it out, or removes it. A writer who believes a verdict is wrong answers it with the quoted line, and the next round's check reads the answer; a verdict still disputed after two rounds goes to the user with the rest. What the system is for and the one-clause reasons are not checked against the code; the writer stands behind them.
