# The explain skill — GHI-MD for issue [Build the explain skill: re-say a message for a reader who does not carry the session's context — the draft exists, and the hold's reason expired](https://github.com/nedschorus/nedschorus/issues/603)

This document carries the substance the issue summarises: the draft recovered from the
log-store, the seven defects its review raised with a proposed resolution for each, the
design evidence observed, and the revised skill text those resolutions produce.

The issue carries the state — why the skill exists, why its 2026-08-22 hold expired, and
what happens next. Read it first.

## Why the draft had to be recovered rather than read

`docs/drafts/explain-skill-draft.md` was written 2026-09-15 and never reached main, so no
branch of this repository holds it. It survives only because a cold-read-fast-read was run
against it that day and the run froze its cold-read-target into the cold-read-record, the
behaviour user-ruled 2026-09-07. The record is at
`nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/2026-09-15-explain-skill-draft/`,
holding the frozen draft at
`nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/2026-09-15-explain-skill-draft/target/docs/drafts/explain-skill-draft.md`
and its review at
`nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/2026-09-15-explain-skill-draft/explain-skill-draft-fast-read.md`.

Worth recording as a property of the review machinery rather than an accident: a document
that was never committed was recoverable a week later because reviewing it copied it. The
freeze was ruled for a different purpose — so a reader of an old cold-read-record has the
text the reviewers read — and this is a second benefit of it.

## The draft as written, 2026-09-15

Reproduced verbatim so this document is readable without reaching the log-store. Its
defects are addressed in the next section; do not build from this copy.

> ---
> name: explain
> description: Re-say what you just told the user, for a reader who does not carry this session's context. Use when the user types /explain, or says he does not understand, is confused, or asks what a term or a number refers to.
> ---
>
> # Explain
>
> The user reads your messages cold. He works in other seats' terminals and arrives
> at yours without the context you have been accumulating all session. When he
> cannot follow something you said, the cause is almost never sentence length. It
> is one of two things:
>
> - **a project term used as though already defined** — slice, cell, seat, drain,
>   gate, head;
> - **a bare identifier cited as though he would recognise it** — #379, 40b5ee7,
>   task #191.
>
> Both are invisible to you while you write, because you know what they refer to.
>
> ## What to do
>
> Take your previous message. Do not defend it, do not apologise for it, and do not
> add to it.
>
> 1. **Answer the words first.** Name every project term and every identifier that
>    carried weight in what you said, and say plainly what each one is, one clause
>    each: "#379 is a pull request. A slice is one numbered chunk of a build."
>    Do this for all of them, not only the ones he asked about — he asked about the
>    ones he noticed.
> 2. **Then retell the point as one concrete story.** A particular thing happening
>    to a particular file, run, or branch: what happens, in order, and what goes
>    wrong or right at the end. Not a definition, not a summary, not a list of
>    properties.
> 3. **Stop there.** Same content, different footing.
>
> ## What not to do
>
> - **Do not add information.** If you are introducing something the original
>   message did not contain, you have answered a question he did not ask. The
>   definitions step 1 calls for are the only exception.
> - **Do not define a project term with other project terms.** If the definition
>   needs a second term he may not know, define that one too, or choose different
>   words.
> - **Do not restate at the same altitude, only longer.** Repetition is not
>   explanation.
> - **Do not give the mechanism before the purpose.** Say what the thing does and
>   why anyone wants it, then how it works.
>
> ## When he aims it
>
> `/explain <term>` narrows it to that one thing. Answer it directly, and retell
> the surrounding point only if the term cannot be understood without it.
>
> ## When you cannot tell what was unclear
>
> Guess, and say you are guessing. Name the one or two things you think were
> opaque, explain those, and offer the rest. Do not ask him which part confused him
> and then wait: he is usually reading between seats, and a question costs him a
> round trip that a guess does not.

## The seven defects, and how each is resolved

The cold-read-fast-read of 2026-09-15 raised seven. Each is quoted from that report, then
answered. Five are text fixes; two are design decisions that change what the skill does.

### 1. The purpose-before-mechanism rule has nowhere to live — DESIGN

> This instruction conflicts directly with step 1, which limits definitions to "one clause
> each", and step 2, which strictly requires a chronological narrative of an event and
> forbids definitions, summaries, or property lists, leaving an executing agent with no
> valid structural place to explain purpose and mechanism without violating either step 1
> or step 2.

Correct, and the fix is not to find it a third home. Purpose-before-mechanism is not a
separate obligation; it is a property a story already has when it is told properly. A story
about a particular run begins with what someone was trying to do, which is the purpose, and
only then what the machinery did. The rule belongs inside step 2 as a constraint on how the
story opens, not in a list of prohibitions where it competes with the steps.

**Resolution:** delete the prohibition; fold it into step 2 as the sentence that starts the
story.

### 2. The draft uses `seat` undefined while forbidding exactly that — DESIGN

> The document relies on "seat" as a critical operational concept without defining it,
> despite explicitly listing "seat" in `[s8]` as a prime example of a confusing project
> term used as though already defined.

The observation is right and the inference is not. The draft's rule governs what the agent
writes **to the user**; the draft itself is written **to an agent**, which has the project
glossary and for which `agent-seat` is a defined project-term. The fault is that the draft
never says which direction the rule points, so a reader applies it to the skill's own prose
and finds a contradiction.

**Resolution:** state the scope in the opening line — the rule governs the message the agent
sends, not this document — and use the glossary's `agent-seat` rather than the bare `seat`.

### 3. "Carried weight" is subjective and clashes with "all of them" — DESIGN

> The qualifying phrase "carried weight" is subjective and undefined, requiring the agent to
> guess which terms are important enough to define, which clashes directly with `[s16]`'s
> absolute command to "Do this for all of them".

The draft asks for a judgement and then forbids judgement in the next sentence. Since the
whole failure this skill addresses is an agent misjudging what the reader knows, asking it
to judge again is the wrong instrument.

**Resolution:** make the set mechanical and checkable. Define every project-term — the
glossary at `docs/nedschorus-wiki/nedschorus-glossary.md` is the authority on what is one —
and every identifier, meaning anything of the form `#N`, a commit hash, a session id, a
branch name or a path, that appears in the message being re-said. No weighing.

### 4. "Answer it directly" has an ambiguous referent — TEXT

> The pronoun "it" shifts ambiguously between the explanation scope, the user's inquiry, and
> the targeted term itself.

**Resolution:** name the referent. "`/explain <term>` narrows step 1 to that term. Define
it, then retell the surrounding point only if the term cannot be understood without it."

### 5. "Offer the rest" reads as asking a question the draft forbids — TEXT

> "Offer the rest" can be interpreted as asking the user whether they would like the
> remaining terms explained, which would directly violate `[s32]`'s strict prohibition
> against asking the user a question and waiting.

**Resolution:** replace with an offer that costs no round trip — list the others in one line
so he can aim a follow-up if he wants one, and carry on without waiting.

### 6. "Same content, different footing" is an undefined metaphor — TEXT

> The phrase "different footing" is an undefined colloquial metaphor, leaving the agent to
> guess whether the rewrite requires a different level of abstraction, an altered persona,
> or a narrative rather than analytical structure.

**Resolution:** delete it. Step 3 is "Stop." The sentence was decoration and the skill's own
rule against restating at the same altitude already carries the meaning.

### 7. A quotation spans a sentence boundary unclosed — TEXT

**Resolution:** move the example out of the sentence and into a display block.

## The open question the seven do not cover

Whether a skill needs a cold-read-full-run or whether a cold-read-fast-read plus the user's
own reading is enough was raised twice during the identifier-presentation work and never
answered. `.claude/skills/cold-read/SKILL.md` says a skill gets the full run, and
`scripts/cold-read-fast-read.py` warns on stderr and in its report when its target belongs to
a class the full run covers — a skill among them. Absent a ruling to the contrary the full
run applies, and this document recommends taking it: the skill is operative prose that every
session will read.

## Design evidence, observed 2026-09-21

The 2026-08-22 hold asked for failed one-shot explanations as the skill's design evidence.
Two were produced at the merge-lane-backlog seat during its triage walk, with no output
style active anywhere in the fleet:

1. Presented with a one-shot explanation of a closed task, the user replied "confused.
   explain 2". The retelling succeeded — and it succeeded by doing step 2 of this draft,
   one concrete story told from the failure the task guarded against, while skipping step 1
   entirely: it never defined the terms or the identifiers first. The draft predicts that
   omission and forbids it, which is evidence the draft is addressing the real failure.
2. Earlier in the same walk, after a recommendation had been stated plainly, the user asked
   "what do you want to do and why?" — the same class of miss, a message that did not land
   as written.

Both are recorded in that walk's minutes, shipped to the log-store as
`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/merge-lane-backlog-triage-result-minutes.md`.

## The revised skill text

What the resolutions above produce, for `.claude/skills/explain/SKILL.md`. This is the
proposal the cold read should read and the user should walk; it is not installed.

```markdown
---
name: explain
description: Re-say what you just told the user, for a reader who does not carry this session's context. Use when the user types /explain, or says he does not understand, is confused, or asks what a term or a number refers to.
---

# Explain

The user reads your messages cold. He works in other agent-seats' terminals and arrives at
yours without the context you have been accumulating all session. When he cannot follow
something you said, the cause is almost never sentence length. It is one of two things:

- **a project-term used as though already defined** — slice, cell, drain, gate, head;
- **an identifier cited as though he would recognise it** — a pull request number, a commit
  hash, a session id.

Both are invisible to you while you write, because you know what they refer to.

Everything below governs the message you send him. It does not govern this document.

## What to do

Take your previous message. Do not defend it, do not apologise for it, and do not add to it.

1. **Answer the words first.** Define two sets, with no weighing of which mattered: every
   project-term in that message, as listed in `docs/nedschorus-wiki/nedschorus-glossary.md`,
   and every identifier in it — a number, a hash, a session id, a branch, a path. One clause
   each:

       A slice is one numbered chunk of a build, built and merged on its own.
       That number is a pull request: "exit nonzero when any seat was not recovered".

   Define all of them, not only the ones he asked about. He asked about the ones he noticed.

2. **Then retell the point as one concrete story.** Open with what someone was trying to do,
   because purpose before mechanism is how a story reads; then a particular thing happening
   to a particular file, run or branch, in order, ending in what went wrong or right. Not a
   definition, not a summary, not a list of properties.

3. **Stop.**

## What not to do

- **Do not add information.** If you are introducing something the original message did not
  contain, you have answered a question he did not ask. The definitions in step 1 are the
  only exception.
- **Do not define a project-term with other project-terms.** If the definition needs a
  second term he may not know, define that one too, or choose different words.
- **Do not restate at the same altitude, only longer.** Repetition is not explanation.

## When he aims it

`/explain <term>` narrows step 1 to that term. Define it, then retell the surrounding point
only if the term cannot be understood without it.

## When you cannot tell what was unclear

Guess, and say you are guessing. Name the one or two things you think were opaque and
explain those. List the others in one line so he can aim a follow-up, then carry on. Do not
ask him which part confused him and wait: he is usually reading between agent-seats, and a
question costs him a round trip that a guess does not.
```

## Next action

Cold-read this document's revised skill text, walk it with the user, then install it at
`.claude/skills/explain/SKILL.md`. The skill is operative prose, so it reaches main through
the user's walk rather than through a reviewer's judgement.
