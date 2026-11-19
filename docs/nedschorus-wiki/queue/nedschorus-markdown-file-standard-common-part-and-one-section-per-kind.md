# Markdown file standard: a common part and one section per kind

This page is the standard for the project's Markdown files: a common part that every Markdown file follows, then one section for each of six kinds of file, saying what a file of that kind contains, what it leaves out and its length in words. Do not read the whole page before you write or edit a file. Run `nc-systems/general-tools/markdown-file-standard-rules-for-the-markdown-file-kind-at-a-path-print.py <path of the file>`, giving the path the file will have once it is in place, such as `CLAUDE.local.md` for a seat-brief drafted in a scratchpad. It prints the common part and the one section for that file's kind, or the common part alone when no section covers the path; read another section only where the printed one points to it. The program picks the kind by the path, and, for a GHI-MD that already exists, also by its front matter, as the GHI-MDs section says. It reads this page's level-2 headings as data, and holds this page's path: a heading is renamed, or the page moved, only together with the program's constant that holds it.

## Common part

- **Write for a fresh-reader.** The reader has the file and what it links to, not the conversation that produced it. Every reference opens from the reader's machine: a path from the repository root, a log-store citation, or a full URL.
- **State what is, not how it came to be.** Leave out the dates of events, retellings of approval-walks and user-rulings, review rounds, incidents, "was replaced by", "previously", "no longer", and pull requests or GHIs cited as provenance; git history, pull requests and walk-minutes hold them. A decision is written as what holds now. A past fact stays only where a reader would otherwise misread the present, as one clause with no date.
- **One canonical location for each fact.** Link to the document or file that holds a fact instead of restating it. Leave to the code what the code states, such as flags, exit codes, message texts and file formats: name the file and stop.
- **A reason is one clause**, attached to the statement it explains, and only where it helps the reader act. Do not defend a decision or list rejected alternatives, unless the kind's section asks for them.
- **Headings.** Where a kind's section lists headings, the file has each one that section does not make optional or conditional, and keeps that section's order. A heading or line that a program reads, such as `## Provisional additions (not yet vetted by the user)` or a front matter line, keeps its exact text.
- **Length.** Where a kind's section gives a length, it is a cap in words as `wc -w` counts them, not a target. A file or entry over its cap usually holds something its section leaves out: cut that first.
- **Kept true.** When the thing a file describes changes, change the sentence that describes it. Do not append a dated note, an "Update:" paragraph or an "as of" line beside the old sentence.
- **Exemptions and precedence.** A file whose job is to record what happened, such as a log, walk-minutes, a report, a commit message or a pull request description, is exempt from the rules State what is and Kept true, and a word-for-word copy, such as a frozen-copy, follows none of this standard. Where a kind's section asks for something a common-part rule tells writers to leave out, such as the exact command in a bug's `## Reproduction`, the kind's section wins.

## GHI-MDs

This section covers each GHI-MD in `docs/issues/`, and each MD in `docs/issues/queue/` on its way to becoming one. `.claude/skills/ghi-write/SKILL.md` says how it is routed, titled, filed and edited; this section says what it holds. A GHI-MD that is a design, whose front matter carries `kind: design`, follows the Designs section instead. The program prints the Designs section for it only once the file exists with that line; for a new design GHI-MD, it prints this section, so read the Designs section on this page and follow it instead.

A GHI-MD that is not a design is one of four kinds: a bug, code that does not do what its design, design-contract or documentation says; a change request, a change to what a design or design-contract promises once its code has merged; a chore, upkeep that changes no behaviour; and research, a question to answer, with no code promised. A bug whose fault turns out to be in the design is a change request.

It contains, in this order:

1. The first heading, the GHI's title, by the rules of `/ghi-write` step 4.
2. For a bug, `## Reproduction`: the command or steps, what happened, and what should have happened, naming the file that promises it. For a change request, `## Change`: the design it changes, and its design-contract where it has one, what should change, and which of four of the maintenance types that ISO/IEC/IEEE 14764:2022 (https://www.iso.org/standard/80710.html) defines the change is: corrective, adaptive, perfective or preventive. For a chore, `## Work`: the upkeep to do, the files or programs it touches, and why it is due now. For research, `## Question`: the question, and what each likely answer would lead to.
3. `## Why`: who or what the problem or gap costs, and how often.
4. `## Next action`: one action a fresh-reader can take.
5. `## Done when`: the condition that closes the GHI.
6. `## Relations`: each related GHI by title and link, with one clause on how it relates. Leave the section out when there are none.
7. `## Outcome`, added when the work is done: what was done, by pull request link, in one paragraph. When Outcome is added, `## Next action` is deleted, because it is then no longer true.
8. `## Provisional additions (not yet vetted by the user)`, always last, when the GHI-MD holds provisional-additions.

A GHI-MD leaves out:

- A dated account of events, such as a "Status on" section, a list of where a failure was seen beyond the one example that reproduces it, or the rounds of a review. A new event changes the section it affects, such as Why or Next action.
- A record of how a decision was reached. A user-ruling the work rests on is stated as what is decided, in the section it governs, followed by its walk-minutes citation in parentheses, because an agent must verify it before it acts against it.
- Data, measurements and working notes: they go in supporting-documents that the GHI links, as `/ghi-write` step 2 says.

Length: at most 600 words; Outcome and Provisional additions aside. A GHI-MD over 1,000 words usually holds a design, which goes in a GHI-MD of its own that carries `kind: design`, or material for a supporting-document.

## Designs

A design decides how something will be built. It is a GHI-MD whose front matter carries `kind: design`, as `/ghi-write` step 4 says, or a file whose name ends `-design.md`, such as a design moved to its code's `docs/` directory. No section of this page covers a test-design or a design-contract, and the program prints the common part alone for either. `docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md` says where it lives and how it is named at each stage.

A design has these seven level-2 headings, in this order. A design that does not need one of the seven keeps its heading, and the section's whole body is one line, `Not needed:` followed by the reason.

1. `## Problem`: what is wrong or missing, who it costs, and what the design must achieve, measurable where it can be.
2. `## Goals and non-goals`: what the design delivers, and what it deliberately does not, one line each.
3. `## Design`: the components, the data each holds or passes, and how they work together, at the level a builder needs; subsections as the design needs them.
4. `## Steps that need judgment`: each step given to a model, and why code cannot do it. Every step not listed here is code.
5. `## Failure handling`: each failure the design handles, how the program reports it, and, for a guard, validation, retry or workaround, the failure that `CLAUDE.md`'s two conditions require.
6. `## Testing`: how each design-requirement is tested, or the test-design that says so.
7. `## Alternatives considered`: each alternative rejected, in one or two sentences with its reason.

These headings follow the seven when the design has them, and are left out when it does not: `## Deferred-decisions`, one line for each case the design leaves open, and `## Decided elsewhere`, one line for each decision another component, document or agent-seat makes, naming that owner, each line in the form the paragraph headed `initiate-design-to-main` in `docs/design-to-main/design-to-main-state-machine-design.md` gives, such as a deferred line marked `#not_in_this_run` with its reason; `## Defects fixed`, a `#root_cause` or `#root_cause_not_fixed` line for each defect the design's code fixes, or the line `#no_defect_fixed`, as `CLAUDE.md` gives them for a pull request description and `scripts/merge-gate.sh` checks them; `## Relations`; and, for a design that is a GHI-MD, the GHI-MDs section's `## Next action`, `## Done when`, `## Outcome` and `## Provisional additions (not yet vetted by the user)`, as that section describes them. A design that is a GHI-MD also opens with the front matter `/ghi-write` step 4 gives it, then the GHI's title heading.

A design leaves out:

- Its own revision history, such as "this revision folds in", and the dates its decisions were made. The `**Pinned to what landed:**` lines that `docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md` asks for after each merge stay, because `scripts/stale-code-citation-check.py` reads them. A user-ruling the design rests on is stated as what is decided, followed by its walk-minutes citation in parentheses.
- Detail the design-contract or the test-design holds.
- Once its code has merged, any detail the code now states. From then on, a change to what the design promises goes through a GHI-MD that is a change request.

Length: at most 3,000 words for a system, at most 1,200 for a single program. A design over 4,000 words usually holds two designs, or detail that belongs in the design-contract, the test-design or the code.

## The project glossary

The project glossary is `docs/nedschorus-wiki/nedschorus-glossary.md`. Its opening paragraphs say what qualifies as a project-term, which glossary holds a term, the order of entries and when an entry carries the labels #prose, #code and #data; this section says what an entry holds.

Every entry follows one template, on one line, in which `[…]` marks an optional part:

```
- **<term>** — <definition>[, such as <one example>].[ <one sentence naming the document or program that holds the detail, such as "The program is `<path>`.">][ <labels>]
```

- The definition is one sentence. It starts with the kind of thing the term names, such as "a skill", "the program" or "a filename suffix", then says what sets it apart from others of that kind. It does not use the term itself.
- The example is a real one from this repository, given only where the definition alone leaves a reader unsure what counts.
- The sentence naming the detail's canonical location, such as the program that implements the term, is given where one exists.

An entry leaves out history, user-rulings, quotations of the user, the reasons for the term or the thing it names, how-to steps, design detail, a list of the term's cases, and anything the linked document says.

Length: at most 50 words an entry. An entry over 60 words holds detail that belongs in the linked document.

## Seat-briefs

A seat-brief is in context for the whole of every agent-session of its agent-seat, so each word costs every agent-session. `.claude/skills/start-agent-seat/SKILL.md` step 2 says how a new one is written and approved; this section says what it holds, for a new seat-brief and for each edit of one.

It contains, in this order:

1. A level-1 heading naming the agent-seat.
2. What the agent-seat owns, in one paragraph.
3. Its first job, or the standing work it does when no task is open.
4. Where its work goes: nc-topic-branches and pull requests, the log-store directory, and which agent-seat it reports to, if any.
5. Rules for this agent-seat alone that no `CLAUDE.md`, skill, wiki page or program holds, each in one to three sentences. The user's words go in quotation marks where a paraphrase would lose his meaning, with no date or attribution.

A seat-brief leaves out:

- Anything `CLAUDE.md`, a skill, a wiki page or a program already says, and procedures of more than a few steps: a procedure goes into a skill or a program, and the seat-brief names it.
- How the agent-seat was started, who asked for it, and the incidents behind its rules.
- Facts about another agent-seat or a machine that change on their own, such as which agent-seat merges pull requests; the seat-brief names the document that holds them.

Length: at most 800 words. A seat-brief over 1,000 words holds procedures that belong in a skill or a program. When a skill or a program takes over a rule, the rule leaves the seat-brief in the same change.

## Handoff next step files

A next step file is the file `/handoff` step 2 writes in `~/.claude/handoffs/`; `nc-systems/handoff/handoff-write-and-check-supervisor.py` copies its text into the session-handoff, which the successor agent-session, which did not see the work, starts from. `.claude/skills/handoff/SKILL.md` step 2 says what goes in it and what stays out; this section adds the order, the form and the length.

It contains, in this order:

1. The first action, in one paragraph starting `First action:`: what the user is waiting on, or, when he waits on nothing, the task to start first, naming an approval-walk by its name or a task by its id, and the exact command or message to send first where it is already decided.
2. Running work that must be restarted now and that no record shows, as `/handoff` step 2 says, one line each, with its command.
3. What the successor needs that no task, walk-minutes, committed file or `CLAUDE.md` holds, one line each, with a path, or a repository and number, for each reference.

A next step file leaves out what this agent-session did, the text of an approval-walk item or a task, which their files hold, the times and wording of the user's replies unless the successor acts on them, and the reasons behind the first action unless the successor would otherwise act differently.

Length: at most 400 words. A next step file over 500 words holds work that belongs in tasks.

## Wiki pages

A wiki page is a page in `docs/nedschorus-wiki/`, or one in `docs/nedschorus-wiki/queue/` pending approval, other than the project glossary and each proposed-improvements-or-changes-file beside an nc-architecture-overview. An nc-architecture-overview also follows `docs/nedschorus-wiki/nedschorus-how-to-write-an-architecture-overview.md`, which wins where the two differ.

Each page is one of three kinds, and keeps to its kind: a reference page lists rules or facts a reader looks up, such as `docs/nedschorus-wiki/nedschorus-style-guide.md`; a how-to page gives the steps of one job, such as `docs/nedschorus-wiki/nedschorus-how-to-choose-a-name-for-files-code-and-glossary-terms.md`; an explanation page says how part of the project works and why, such as `docs/nedschorus-wiki/nedschorus-agent-seat-model.md`. When a page grows material of another kind, move that material to a page of its own and link to it.

A page contains, in this order:

1. A level-1 heading naming its subject.
2. A first paragraph saying what the page covers and when a reader needs it, so a reader can tell from that paragraph alone whether to read on. A page whose content a program reads as data names that program here, as the rule for prose a program reads in `docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md` says.
3. The body: for a reference page, one rule or fact to an item, ordered for lookup; for a how-to page, numbered steps, each an action; for an explanation page, the parts and how they fit together, with a reason where it helps.

A wiki page leaves out front matter or opening lines that say which approval-walk or user-ruling produced the page, status lines such as "status: ruled" or "streamlined on", the approval-walk or user-ruling behind each rule, and examples taken from past events when a current file or command would serve.

Length: a reference page as long as its content, one line or row for each rule; a how-to or explanation page at most 2,000 words. A page over 3,000 words usually holds two pages.
