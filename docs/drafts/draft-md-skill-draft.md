---
name: draft-md
description: Use when composing durable MD prose — a new document, or new or changed paragraphs in an existing one — before md-review sees it. Not for mechanical edits (a path, a date, a rename), not for code, and not for files whose names end in -log, -report, or -capture.
---

# draft-md

You are about to write prose that an agent or a person will read. They will have no initial context other than this text. This skill governs how that prose should be drafted, not where it lands.

Work in this order: settle what you are governing, draft the answer, clear the bars, move out what does not belong, then get one fresh reader on it before anyone else.

## What this governs

Only the text you are composing: a new document's whole text, or exactly the paragraphs an edit adds or changes. In a file that keeps each paragraph on one line, `git diff` shows that governed text directly. Untouched text is out of bounds no matter how it reads to you — a ruling from the user's item-by-item review (a walk) may be exactly why it reads that way. If an untouched paragraph looks wrong, raise it as a question or route the file to md-review; never improve it silently.

Two kinds of file are outside this skill entirely. Mechanical edits — a path, a date, a rename — need no drafting register. And a document that only reports what happened is not instruction: those carry a genre suffix in their name — `-log` for an account that accumulates entries, `-report` for the output of one run, `-capture` for an artifact saved off a real run — and their history is their content. Do not draft them here.

## How to draft

For example: a two-sentence rule, drafted directly as rule text, took four rounds of rewriting before its reader could accept it — dense, abstraction-first, terms unresolved. The same author, asked a plain question about the same material, answered it clearly in one try; the accepted text was that answer transcribed. Draft the answer, not the rule:

1. Identify the question the text exists to answer. Every durable paragraph answers one — "when do I run this?", "what do I audit here?", "where do reports land?".
2. Answer it as if a colleague asked, with one concrete case first. Use the case at hand. Where the material is new and no case exists yet, write the smallest case that could really occur here and open it with "For example:" — never dress an invented case as something that happened.
3. Keep the sentences you would say. The answer, not the question, becomes the text.

For a whole new document, give it a title line that says what it is, and headings a reader can scan. A reader who opens it should be able to answer "what is this, and when do I need it?" from the first paragraph.

## The bars the draft must clear

- Standard SDLC terminology; do not coin a new term while drafting. Where the project already has a name for something, use that name and give its plain-words meaning at first use.
- Plain, precise, short sentences. Short and dense are not the same: never compress to fit a word count, and never pad to look thorough.
- The three-test check, on the whole draft: the subject is identifiable from the text alone; the why is stated; a reader who was not in the conversation can act on it.
- No hard line wraps inside a paragraph: write each paragraph as one line and let the viewer wrap it. Line breaks belong only where markdown means them — between paragraphs, list items, headings, and inside code fences.
- The two bars below, which need more than a line each: name what a phrase refers to, and make any step you define emit its answer.

## Name what a phrase refers to

For example: a document said a restriction was proven by a controlled experiment rather than merely read from its settings, and named the restriction only as "the restriction" — correct at the time, because the restriction was named in the sentence just above. Later editing inserted several hundred words between the two, and among them a second restriction, which no experiment had ever tested. The sentence did not change, and it began asserting that the untested restriction was the proven one. Nothing in the sentence looked wrong.

So name the referent inside the phrase: "the push restriction", not "the restriction"; "the branch-protection check", not "this check". A phrase that points at its neighbor is true only while that neighbor stays put, and no edit announces that it has moved the neighbor. Naming costs a word or two; the failure produces a confident false claim in a document other people act on, with nothing left in the text for a reader to doubt.

Ordinary connective prose still points — "it" and "this" are what let paragraphs read as paragraphs. The bar applies to sentences carrying a claim someone will act on or check: there, name the referent.

## When the draft defines steps

When the prose you draft defines a step — work handed to a program or an agent, whose result something else consumes — the step must always emit its answer.

Never define a step that answers only on one outcome: only if true, only on failure, only when a particular tag matches, staying silent otherwise. A tag here is a status label the step must choose from, such as PASS, FAIL, or NEEDS-REVIEW.

Every run answers each thing asked: true or false, or one of the named labels the step chooses from. When there was nothing to do, one of the step's own declared answers says so — an in-set no-op, never silence, and never a value invented outside the declared set.

This covers terminal steps too. Where no next step exists, the human reading the output is the consumer.

The reason: an unconditional answer lets the consumer verify the step ran at all. With conditional emission, silence could mean false, nothing-to-do, or never-ran, and no reader can tell which. A step that edits or searches by matching a pattern, and finds nothing, must say so or error — never silently proceed.

## What does not belong in the text

Three things earn a place: the instruction, the explanation an instruction needs to be judged rightly, and a clean example of it. Move the rest out before anyone reads the draft. Only two classes are simply deleted: commentary about the document itself, and hedges that change no action. The others move rather than go — each has a home that holds it better than this document does, and material cut without a home is material lost.

- Provenance — commit ids, issue and pull-request numbers, dates, who decided and when. The commit message and the issue hold that, and so does the pair document, an issue's companion file under `docs/issues/`. A reader following the instruction does not need it, and every citation is one more claim that must be checked and can rot.
- Historical narrative — what the rule replaced, what it used to say, when it changed. An example that teaches the rule and stands on its own is not historical narrative; keep it.
- Commentary about the document itself — "the section above", "note that", "importantly".
- Hedges and caveats that change no action.
- Intentions about later work — what a future version may add, what someone should build next. File the intention as an issue, or move it into the queue directory that will hold it (`docs/issues/queue/` or `docs/wiki/queue/`), naming that path in your commit. Then cut it from the text. Never simply delete it: an intention that lives only in a document nobody treats as a work list is already lost, and cutting it without a home finishes the job.
- Cross-references that make the reader open a second document to understand this one. Say the thing here, or name that document by its path in backticks as the authority and stop.

Keep the reason a rule exists — what it protects against — because that is what lets an agent judge a case the rule never anticipated. What you cut is decision history, not reasons.

## Before anyone else sees it

Run one zero-context read: a fresh subagent with no conversation history, handed only the draft plus the project's CLAUDE.md, asked what the text means and where it stumbles. Fix the stumbles. Where the reader's restatement of a passage is clearer than the draft, revise the draft toward the restatement — the author's sentences do not outrank the reader's. Any stumble you chose not to fix goes in the commit message, so the next reviewer sees what you left and why.

Then the normal pipeline: md-review — the durable prose this skill governs is the same "documents of lasting value" md-review exists for — and the user walks near-final MDs before they land.
