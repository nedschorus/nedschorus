# Markdown file standard: a common part and one section per kind

This page is the standard for the project's Markdown files: a common part that every Markdown file follows, then one section for each of six kinds of file, saying what a file of that kind contains, what it leaves out and how long it runs. Do not read the whole page before you write a file. Run `nc-systems/general-tools/markdown-file-standard-rules-for-the-markdown-file-kind-at-a-path-print.py <path of the file>`, which prints the common part and the one section for that file's kind, picked by its path, or the common part alone when no section covers the path. That program reads this page's level-2 headings as data: a heading is renamed only together with the program's constant that holds it.

## Common part

- **Write for a fresh-reader.** The reader has the file and what it links to, not the conversation that produced it. Every reference opens from the reader's machine: a path from the repository root, a log-store citation, or a full URL.
- **State what is, not how it came to be.** Leave out dates of events, approval-walks and user-rulings retold, review rounds, incidents, "was replaced by", "previously", "no longer", and pull requests or GHIs cited as provenance; git history, pull requests and walk-minutes hold them. A decision is written as what holds now. A past fact stays only where a reader would otherwise misread the present, as one clause with no date. A file whose job is to record what happened, such as a log, walk-minutes, a report, a commit message or a pull request description, is exempt from this rule.
- **One canonical location for each fact.** Link to the document or file that holds a fact instead of restating it. Leave to the code what the code states, such as flags, exit codes, message texts and file formats: name the file and stop.
- **A reason is one clause**, attached to the statement it explains, and only where it helps the reader act. Do not defend a decision or list rejected alternatives, unless the kind's section asks for them.
- **Headings are the kind's sections, in its order.** A heading or line that a program reads, such as `## Provisional additions (not yet vetted by the user)` or a front matter line, keeps its exact text.
- **Length.** Each section gives a range, in words as `wc -w` counts them. A file over its range usually holds something its section leaves out: cut that first.
- **Kept true.** When the thing a file describes changes, change the sentence that describes it. Do not append a dated note, an "Update:" paragraph or an "as of" line beside the old sentence.

## GHI-MDs

A GHI-MD is the file under `docs/issues/` that holds a GHI's text, or one in `docs/issues/queue/` on its way there. `.claude/skills/ghi-write/SKILL.md` says how it is routed, titled, filed and edited; this section says what it holds. A GHI-MD that is a design follows the Designs section instead.

A GHI-MD is one of four kinds: a bug, code that does not do what its design, design-contract or documentation says; a change request, a change to what a design or design-contract promises once its code has merged; a chore, upkeep that changes no behaviour; and research, a question to answer, with no code promised. A bug whose fault turns out to be in the design is a change request.

It contains, in this order:

1. The first heading, the GHI's title, by the rules of `/ghi-write` step 4.
2. For a bug, `## Reproduction`: the command or steps, what happened, and what should have happened, naming the file that promises it. For a change request, `## Change`: the design and design-contract it changes, what should change, and whether the change is corrective, adaptive, perfective or preventive. For a chore, `## Work`. For research, `## Question`: the question, and what each likely answer would lead to.
3. `## Why`: who or what the problem or gap costs, and how often.
4. `## Next action`: one action a fresh-reader can take.
5. `## Done when`: the condition that closes the GHI.
6. `## Relations`: each related GHI by title and link, with one clause on how it relates. Leave the section out when there are none.
7. `## Outcome`, added when the work is done: what was done, by pull request link, in one paragraph.
8. `## Provisional additions (not yet vetted by the user)`, when an agent has added lines that wait for the user.

A GHI-MD leaves out:

- A dated account of events, such as a "Status on" section, a list of where a failure was seen beyond the one example that reproduces it, or the rounds of a review. A new event changes the section it affects, such as Why or Next action.
- A record of how a decision was reached. A user-ruling the work rests on is stated as what is decided, in the section it governs, followed by its walk-minutes citation in parentheses, because an agent must verify it before it acts against it.
- Data, measurements and working notes: they go in supporting documents that the GHI links, as `/ghi-write` step 2 says.

Length: 150 to 600 words; Outcome and Provisional additions aside. A GHI-MD over 1,000 words usually holds a design, which goes in a `-design.md` file, or material for a supporting document.

## Designs

A design is a file whose name ends `-design.md`, other than a test-design: a GHI-MD that decides how something will be built, or such a file in its code's `docs/` directory. `docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md` says where it lives and how it is named at each stage.

A design has these level-2 headings, in this order. A section the design does not need keeps its heading, and its whole body is one line, `Not needed:` followed by the reason.

1. `## Problem`: what is wrong or missing, who it costs, and what the design must achieve, measurable where it can be.
2. `## Goals and non-goals`: what the design delivers, and what it deliberately does not, one line each.
3. `## Design`: the components, the data each holds or passes, and how they work together, at the level a builder needs; subsections as the design needs them.
4. `## Steps that need judgment`: each step given to a model, and why code cannot do it. Every step not listed here is code.
5. `## Failure handling`: each failure the design handles, how the program reports it, and, for a guard, validation, retry or workaround, the failure that `CLAUDE.md`'s two conditions require.
6. `## Testing`: how each observable promise is tested, or the test-design that says so.
7. `## Alternatives considered`: each alternative rejected, in one or two sentences with its reason.
8. `## Deferred-decisions`: each case the design leaves open, one line each, or `Not needed:` with the reason.

These headings follow them when the design has them: `## Decided elsewhere`, `## Defects fixed`, `## Next action` while the design's GHI is open, and `## Relations`.

A design leaves out:

- Its own revision history, such as "this revision folds in", and the dates its decisions were made. A user-ruling the design rests on is stated as what is decided, followed by its walk-minutes citation in parentheses.
- Detail the design-contract or the test-design holds.
- Once its code has merged, detail the code now states. The design then changes only through a change-request GHI-MD.

Length: 800 to 3,000 words for a system, 300 to 1,200 for a single program. A design over 4,000 words usually holds two designs, or detail that belongs in the design-contract, the test-design or the code.

## The project glossary

The project glossary is `docs/nedschorus-wiki/nedschorus-glossary.md`. Its opening paragraphs say what qualifies as a project-term, which glossary holds a term, the order of entries and when an entry carries the labels #prose, #code and #data; this section says what an entry holds.

Every entry has one pattern, on one line:

`- **<term>** — <definition>[, such as <one example>][. <path of the document or program that holds the detail>.][ <labels>]`

- The definition is one sentence. It starts with the kind of thing the term names, such as "a skill", "the program" or "a filename suffix", then says what sets it apart from others of that kind. It does not use the term itself.
- The example is one real case from this repository, given only where the definition alone leaves a reader unsure what counts.
- The path is the canonical location of the detail, such as the program that implements the term, given where one exists.

An entry leaves out history, user-rulings, quotations of the user, the reasons for the term or the thing it names, how-to steps, design detail, a list of the term's cases, and anything the linked document says.

Length: 15 to 50 words an entry. An entry over 60 words holds detail that belongs in the linked document.

## Seat-briefs

A seat-brief is the `CLAUDE.local.md` at the root of an agent-seat's agent-home. It is in context for the whole of every agent-session of that agent-seat, so each word costs every agent-session. `.claude/skills/start-agent-seat/SKILL.md` step 2 says how a new one is written and approved; this section says what it holds, for a new seat-brief and for each edit of one.

It contains, in this order:

1. A heading naming the agent-seat.
2. What the agent-seat owns, in one paragraph.
3. Its first job, or the standing work it does when no task is open.
4. Where its work goes: topic branches and pull requests, the log-store directory, and which agent-seat it reports to, if any.
5. Rules for this agent-seat alone that no `CLAUDE.md`, skill, wiki page or program holds, each in one to three sentences. The user's words go in quotation marks where a paraphrase would lose his meaning, with no date or attribution.

A seat-brief leaves out:

- Anything `CLAUDE.md`, a skill, a wiki page or a program already says, and procedures of more than a few steps: a procedure goes into a skill or a program, and the seat-brief names it.
- How the agent-seat was started, who asked for it, and the incidents behind its rules.
- Facts about another agent-seat or a machine that change on their own, such as which agent-seat merges pull requests; the seat-brief names the document that holds them.

Length: 150 to 800 words. A seat-brief over 1,000 words holds procedures that belong in a skill or a program. When a skill or a program takes over a rule, the rule leaves the seat-brief in the same change.

## Handoff next-step files

A next-step file is the file `/handoff` step 2 writes in `~/.claude/handoffs/`, read once, by the successor agent-session, when that agent-session's context is empty. `.claude/skills/handoff/SKILL.md` step 2 says what goes in it and what stays out; this section adds the order, the form and the length.

It contains, in this order:

1. The first action, in one paragraph starting `First action:`: what the user is waiting on, or, when he waits on nothing, the task to start first, naming an approval-walk by its name or a task by its id, and the exact command or message to send first where it is fixed.
2. Running work to restart, one line each, with its command.
3. What the successor needs that no task, walk-minutes, committed file or `CLAUDE.md` holds, one line each, with a path, or a repository and number, for each reference.

A next-step file leaves out what this agent-session did, the text of an approval-walk item or a task, which their files hold, the times and wording of the user's replies unless the successor acts on them, and the reasons behind the first action unless the successor would otherwise act differently.

Length: 100 to 400 words. A next-step file over 500 words holds work that belongs in tasks.

## Wiki pages

A wiki page is a page in `docs/nedschorus-wiki/`, or one in `docs/nedschorus-wiki/queue/` pending approval, other than the project glossary. An nc-architecture-overview also follows `docs/nedschorus-wiki/nedschorus-how-to-write-an-architecture-overview.md`, which wins where the two differ.

Each page is one of three kinds, and keeps to its kind: a reference page lists rules or facts a reader looks up, such as `docs/nedschorus-wiki/nedschorus-style-guide.md`; a how-to page gives the steps of one job, such as `docs/nedschorus-wiki/nedschorus-how-to-choose-a-name-for-files-code-and-glossary-terms.md`; an explanation page says how part of the project works and why, such as `docs/nedschorus-wiki/nedschorus-agent-seat-model.md`. When a page grows material of another kind, move that material to a page of its own and link to it.

A page contains, in this order:

1. A heading naming its subject.
2. A first paragraph saying what the page covers and when a reader needs it, so a reader can tell from that paragraph alone whether to read on. A page whose content a program reads as data names that program here, as the file naming page's rule for prose a program reads says.
3. The body: for a reference page, one rule or fact to an item, ordered for lookup; for a how-to page, numbered steps, each an action; for an explanation page, the parts and how they fit together, with a reason where it helps.

A wiki page leaves out front matter or opening lines that say which approval-walk or user-ruling produced the page, status lines such as "status: ruled" or "streamlined on", the approval-walk or user-ruling behind each rule, and examples taken from past events when a current file or command would serve.

Length: a reference page as long as its content, one line or row for each rule; a how-to or explanation page 300 to 2,000 words. A page over 3,000 words usually holds two pages.
