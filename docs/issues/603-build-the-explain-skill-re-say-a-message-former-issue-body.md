---
issue: "[Build the explain skill: re-say a message for a reader who does not carry the session's context — the draft exists, and the hold's reason expired](https://github.com/nedschorus/nedschorus/issues/603)"
---

# Build the explain skill: re-say a message for a reader who does not carry the session's context — the draft exists, and the hold's reason expired

## Problem

The user reads agent messages cold. He works in other seats' terminals and arrives at one without the context that session has been accumulating, so an explanation written by an agent that knows what every term and number refers to routinely fails for the one reader it is written for. He has typed some form of "I don't understand", "too much", or "explain assuming zero context" thousands of times.

Nothing on main does this job today. `/walk-me-through` covers multi-part material presented item by item; it does not cover re-saying a single message that did not land. The drafting register for durable MDs is GHI [Build draft-md: the drafting-stage skill run before md-review (user-ruled 2026-08-22)](https://github.com/nedschorus/nedschorus/issues/142), which is about documents, not about live explanation to the user.

## A draft already exists, and it is not in git

`docs/drafts/explain-skill-draft.md` was written 2026-09-15, given a cold-read-fast-read the same day, and revised the same day in answer to it. It never reached main, so `git log --all` and every grep of this repository come up empty — but it is not lost. It is an untracked file in the merge-lane seat's checkout, `/Users/el/agents/merge-lane/docs/drafts/explain-skill-draft.md`, 3,194 bytes.

So are two other documents this work depends on: the identifier table the user ruled on 2026-09-16, and the walk minutes that record those rulings. The walk directory is gitignored and its record was never shipped to the log-store. All three exist in exactly one place, and one `git clean -x` in that checkout destroys them.

A superseded pre-revision copy of the draft does survive in the log-store, frozen into the cold-read-record by that day's fast read, at `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/2026-09-15-explain-skill-draft/`. It is the text the reviewer READ, not the text that answered it; do not build from it.

This issue's GHI-MD reproduces the current draft and the ruled table in full, which puts their content into git for the first time.

The draft's shape, in brief: confusion is almost never caused by sentence length. It is caused by a project-term used as though already defined, or a bare identifier cited as though the reader would recognise it — both invisible to the writer, who knows what they mean. The procedure is three steps: define every term and identifier that carried weight, one clause each; then retell the point as one concrete story about a particular file, run or branch; then stop. It forbids adding information, defining a project-term with other project-terms, restating at the same altitude only longer, and giving mechanism before purpose. When the agent cannot tell what was unclear it guesses and says so rather than asking, because a question costs the user a round trip he is reading between seats to avoid.

## Why it was held, and why that reason no longer exists

Item 7 of the clarity-registers walk, 2026-08-22, ruled the skill HELD, recorded on GHI [Clarity registers: explanations and drafted instruction text land without the user's repeated corrections](https://github.com/nedschorus/nedschorus/issues/138):

> An "explain" skill for one-shot explanations: HELD (user-ruled 2026-08-22) — the output style makes the explaining register standing for every session and the walk skill covers multi-part material, so the skill would add only an invocation name; no observed failure remains post-style. Reopen condition: clarify-corrections still being typed at one-shot explanations in sessions running under the Zero-Context Explanation style — those failed explanations become the skill's design evidence.

Three things have happened to that reasoning, and together they are why this issue exists.

**The mechanism it deferred to lived on main for 28.8 hours.** PR [Zero-Context Explanation output style, activated fleet-wide](https://github.com/nedschorus/nedschorus/pull/156) merged 2026-08-31T18:54:03Z. PR [Remove the Zero-Context Explanation output style](https://github.com/nedschorus/nedschorus/pull/232) merged 2026-09-01T23:41:11Z. The skill was held on 2026-08-22 in favour of a mechanism that had not yet landed and that then survived a little over a day.

**The removal was right, and its reasoning argues for a skill.** A custom output style's text sits in the system prompt, is never repositioned, and so competes with everything newer as a session grows; the built-in styles compensate with a per-turn reminder that a custom style cannot declare, because the frontmatter schema is strict. PR [Remove the Zero-Context Explanation output style](https://github.com/nedschorus/nedschorus/pull/232) concludes that a rule which must survive to turn 200 belongs in a hook or a test, not a style file. A skill is nearer to that than a style: it is invoked, so its text arrives at the point of use instead of decaying in the system prompt. The 2026-08-22 ruling dismissed the skill as adding "only an invocation name" — but an invocation name is precisely the delivery the removal found missing.

**The reopen condition can never fire, and the issue was closed for that reason.** The condition names failures observed "in sessions running under the Zero-Context Explanation style". No such session can exist. GHI [Clarity registers](https://github.com/nedschorus/nedschorus/issues/138) was closed not planned on 2026-09-21 on exactly this reasoning. So the hold has no live exit, and the job has no owner.

## Design evidence, observed

The reopen condition asked for failed one-shot explanations as the skill's design evidence. Two were produced on 2026-09-21 at the merge-lane-backlog seat, during the triage walk, with no style active:

1. The user replied "confused. explain 2" to a one-shot explanation of a closed task. The retelling succeeded, and it succeeded by doing the draft's step 2 — one concrete story, told from the failure it guards against — while skipping step 1 entirely: it never defined the terms and identifiers first. The draft predicts and forbids that omission.
2. Earlier in the same walk the user asked "what do you want to do and why?" after a recommendation had been stated, which is the same class: the message did not land as written.

## What the skill must settle

Its fast read raised seven defects on 2026-09-15 and the revision of that same day answered all seven; the GHI-MD tabulates what each answer was, so nobody re-solves them. What remains unbuilt is different and smaller:

**The identifier table is not in the draft.** The user ruled it row by row at walk items 13.1 to 13.3 on 2026-09-16 — four groups covering what gets a type word, a title and a link, what gets a title but nothing to open, what has no human title, and what should not be shown at all. The draft predates those rulings by a day. Folding the table in is step 3 of the identifier-presentation task and has never been done. The table is reproduced in the GHI-MD.

For the record, the seven the revision already closed:

1. **The purpose-before-mechanism rule has nowhere to live.** It requires saying what a thing does and why anyone wants it before how it works, but step 1 allows one clause per term and step 2 requires a chronological story, so an agent following both has no place to put it.
2. **The draft uses `seat` undefined** while listing `seat` as a prime example of the failure it forbids — the document commits its own defect.
3. **"Every term that carried weight" is subjective**, and clashes with the absolute instruction to define all of them rather than only the ones the user noticed.
4. **"Answer it directly" has an ambiguous referent** in the aimed form `/explain <term>` — the term, the scope, or the user's larger question.
5. **"Offer the rest" reads as asking a question**, which the draft forbids two sentences later.
6. **"Same content, different footing" is an undefined metaphor** — a different altitude, persona, or structure is left to the agent to guess.
7. A quotation spans a sentence boundary unclosed.

Beyond the seven: whether this skill needs a cold-read-full-run or whether a fast read plus the user's reading suffices was asked four times across earlier sessions without an answer, and was then **ruled**. Walk item 12 of 2026-09-16: the user answered "y", no exception. The draft takes the cold-read-full-run once the identifier rulings are folded in.

## Pair document

`docs/issues/603-explain-skill-design.md` carries the substance: the recovered draft
verbatim, the seven defects with a resolution for each, the design evidence, and the revised
skill text those resolutions produce. It is in flight, not yet on main, in
PR [Pair document for the explain skill: the recovered draft, its seven defects resolved, and the revised skill text](https://github.com/nedschorus/nedschorus/pull/604);
this line becomes a plain path citation when that merges.

## Next action

The design work the GHI-MD was to do is done in it — the seven defects are resolved and the
revised skill text is written. What remains, in order: land the pair document; give the
revised skill text a cold-read-full-run, which `.claude/skills/cold-read/SKILL.md` requires
for a skill; walk it with the user; then install it at `.claude/skills/explain/SKILL.md`.
The skill is operative prose, so it reaches main through his walk rather than through a
reviewer's judgement.

## Search receipts

- `scripts/ghi-info-ask.py` with `--include-closed`, asked 2026-09-21 for any issue covering an explain skill for one-shot explanations: returned GHI [Clarity registers](https://github.com/nedschorus/nedschorus/issues/138) (closed not planned), GHI [Build draft-md](https://github.com/nedschorus/nedschorus/issues/142) and GHI [Runtime-behavior research bundle](https://github.com/nedschorus/nedschorus/issues/29), and stated that no issue proposes an explain skill as a live candidate.
- `gh issue list --state all --limit 200`, titles scanned for `explain`, `clarity`, `identifier`: only GHI [Clarity registers](https://github.com/nedschorus/nedschorus/issues/138).
- `git log --all` and `git grep` across every branch for `explain-skill` and `explain skill`: no such file in this repository, on any branch. The draft exists only in the log-store, cited above.
- `ls .claude/skills/` on main: `cold-read`, `ghi-write`, `handoff`, `pull-request-review-write`, `sanity-check`, `walk-me-through`. No `explain`.

## Relations

- GHI [Clarity registers: explanations and drafted instruction text land without the user's repeated corrections](https://github.com/nedschorus/nedschorus/issues/138) — the ancestor; held this skill on 2026-08-22 and closed not planned on 2026-09-21.
- GHI [Build draft-md: the drafting-stage skill run before md-review (user-ruled 2026-08-22)](https://github.com/nedschorus/nedschorus/issues/142) — the sibling register, for drafted MDs rather than live explanation.
- GHI [overview-write skill: how an overview of a system is written and checked before it lands](https://github.com/nedschorus/nedschorus/issues/168) — the third register, for explaining a whole system to a reader who must act on it.
