# draft-md: writing, review, and approval ([nedschorus#142](https://github.com/nedschorus/nedschorus/issues/142))

Specification for how a durable Markdown document gets written in this project, from the moment a session decides to write one to the moment the user approves it. It is the pair document for issue 142, which commissions the `draft-md` skill; the skill does not exist yet and is drafted from this document. Status: specification. Walked with the user on 2026-08-26 and 2026-08-27, cold-read by eight reviewers and reconciled, then cut down by the user to what survived: the walk's item dispositions and the earlier, larger design are in this file's history at commit 29e2dc3.

Vocabulary used throughout. A **session** is one running agent conversation. A **seat** is a session with a standing role and its own worktree. A **fork** is a subagent that starts with a copy of the session's whole conversation up to the moment it is spawned. A **cell** is one reviewer run of the review skill; a **fresh** cell starts with no conversation at all. **Both runtimes** means Claude Code and Codex, which the review skill runs its cells on. **The grid** is the review skill's runner, `scripts/md-review-grid.py`.

## The idea

The first draft of a durable document is never written by the interactive session. At the point where the document would be written, the session spawns a fork, and the fork writes. The session's context grows by the fork's one-line report and by nothing of the writing, so when the session reads the draft and its reviews it holds the design and has never seen the text being formed. Reviewers are fresh cells with no conversation at all. The session processes the reviews by itself before the user sees anything; the user enters when the agents have done their best, not before. This applies to every persistent artifact the project writes, code included; this document specifies it for Markdown.

Three stages, kept separate:

- **Writing** — the `draft-md` skill: one write pass, run by a fork of the session, carrying the gotchas list below.
- **Review** — the existing review skill, `md-review` in this checkout, which the user is renaming `cold-read` in a revision not yet on main. Its fresh cells (`restate`, `defect-hunt`) are its own; this document does not change them, and proposes one addition to `defect-hunt`'s criteria (conflation, below). Every cell reports; none edits the draft.
- **Approval** — the user, who enters when the session has processed the reviews and walks them with him.

What this document depends on that is not yet on main: the `draft-md` design notes at `docs/issues/142-draft-md-skill-design-notes.md` (PR #160, another seat's), and the `cold-read` rename with its revised `defect-hunt` criteria (the user's in-progress revision of `md-review`, with another agent). Where this document names those, it names what it expects, not what the checkout has.

## The problem

A writing agent holds the whole conversation in its context window and writes as if the reader held it too. The reader — another agent or a human with the repository and the document and nothing else — gets a document that leans on what was said in the room. The defects this produces are the ones `defect-hunt`'s criteria hunt: contradictions, ambiguity, instructions wrong when obeyed literally, missing prerequisites, tasks with no stopping point, over-broad absolutes, incomplete mechanisms, conflicts with CLAUDE.md, unsearchable names, omitted words and premises — and conflation, which this document adds.

**Conflation** is one word used for two things, or two things treated as one, so that what is true of one is silently applied to the other. The reader does not guess; the reader restates the sentence confidently and wrongly, because the text is fluent and self-consistent while being wrong about the system, and the error surfaces when someone builds or tests from the document. No step-by-step test for it is known, to a fresh reader or to a reviewer who knows the design. What this document does instead is define it plainly, give the signs and examples, and put that in front of both the writer and the reviewer.

## The gotchas: one list, two forms

`defect-hunt`'s criteria are written for a reviewer: each names a target to flag. Writers work harder than readers, so the writer gets the same list in a shorter, positive form — what to do, one or two lines each — as part of the write-pass prompt. Conflation is added to both forms. The reviewer's form of the other criteria lives in `defect-hunt` and is not repeated here.

**The writer's form, all criteria.**

> Things that go wrong in documents like this one, to avoid as you write:
>
> 1. **Missing context.** Everything the reader needs that its training, the internet or the repository does not supply needs to be explained where it first appears. 
> 2. **No stopping point.** Every step or task you set states when it is done.
> 3. **Absolutes.** "Never", "always", "every", "all", "cannot" only when true under all conditions; otherwise name the exception, or use a softer, safer but truer wording. 
> 4. **Incomplete mechanism.** For every mechanism, say what happens in each reachable state, failure, and limit, or say which are out of scope.
> 5. **Names.** Use the repository's existing name for a thing; a new name only after searching, make those self-documenting and easy to grep or glob; see CLAUDE.md for specifics. 
> 6. **Omissions.** Do not leave out a word, a step, or a premise because it is obvious to you; With zero context it may not be obvious to some future reader. If a sentence only works with an unstated premise, state it.
> 7. **Conflation.** Do not condense or squeeze thoughts, ideas, statements or sentences so that two different or potentially different things or concepts are treated as one. 

## The write-pass prompt

Angle-bracket slots such as `<path>` are filled by the seat before the fork sees the prompt; the fork never fills one. (The convention is the one the ghi-info design uses, [nedschorus#46](https://github.com/nedschorus/nedschorus/issues/46) § "Every prompt".)

The fork runs this prompt.

> You are writing a Markdown file to <path>. It covers: <one sentence>. Its readers have access to the repository and this document, are experienced software engineers who prefer standard SDLC terminology, and have none of your context and no memory of any conversation. You hold the design; the reader holds none of it. Everything the reader needs to understand this document, that the repository does not explain, is written in this document.
>
> 1. **Opening.** The first paragraph summarizes the document.
> 2. **Names.** Use the repository's existing names where possible. When you must create a new name, search the repository for it first — grep for names in files, glob for path names — and if it is already used, add a prefix or suffix appropriate to this document, or find a clearer, self-documenting multi-part name like many others in this repository. Use the same name for the same thing. If there is a reason to change from an old name to a new one — the old name was poor, or the thing's use or meaning changed — say so, and use the new one thereafter. Explain each new name in the sentence where it first appears.
> 3. **Gotchas.** The list above, "Things that go wrong in documents like this one", is part of this prompt: read it before you write and against your draft before you report.
>
> Report back one line: the path.

## The sequence

1. **Write.** A fork writes the draft under the write-pass prompt and reports the path.
2. **Cold-read.** The session runs the review skill on the draft: the grid runs the fresh cells (`restate` and `defect-hunt`, both runtimes). All write reports; none edits the draft.
3. **Process the reviews.** The session — not a fork — reads the reports as they land and triages them by itself, as the review skill prescribes; then it walks the findings and what it proposes to do about each with the user, most important first, and revises the draft as the user rules. The reports stay on disk.

A fork that returns more than its one line — an error, a question, a refusal — puts that text into the session's context; it is words about the process, not the draft's text, and the session continues. In Claude Code the fork is the Agent tool's `fork` subagent type; on Codex the nearest mechanism is `codex exec resume <session id>`, which continues a session rather than branching it, so the first build runs the fork on Claude Code and only the cold cells on both runtimes.

## Testing the gotchas

Nothing published measures whether a list like this changes what a writer produces, and the project has the one asset that makes it measurable: transcripts in which the user has already found and named conflations. Two experiments from that labelled set, both judged by the user. Writer side: for each labelled conflation, take the transcript up to just before the passage, regenerate the passage with and without gotcha 7, and judge whether the merge recurs. Reader side: run `defect-hunt` with Criterion J over the documents that contain the labelled conflations, count how many labelled ones it flags, and judge a sample of its other flags. The same reader-side run over the same documents measures the other criteria the same way. The labels are the ground truth; the set grows as the user finds more.

## Where this lands

Once this document is on main, the prof seat drafts the `draft-md` skill from it (user-directed 2026-08-26), following the skill-authoring checklist at `docs/wiki/queue/skill-authoring-checklist.md`; the draft gets its own cold-read and walk. The write-pass prompt and the writer's gotchas list belong to that skill. Criterion J belongs to `defect-hunt`, which the user is revising with another agent; it is proposed there, not made here. The research behind the earlier, larger design — the defect catalog and the published evidence per rule — is in `docs/issues/142-draft-md-prompt-research-report.md`. Both files go to main under the interim lane (one topic, a fresh branch from main, a PR for the merge-lane seat) while the gatekeeper is dormant.
