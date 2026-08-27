# draft-md: writing, review, reconciliation, and approval ([nedschorus#142](https://github.com/nedschorus/nedschorus/issues/142))

Specification for how a durable Markdown document gets written in this project, from the moment a session decides to write one to the moment the user approves it. It is the pair document for issue 142, which commissions the `draft-md` skill; the skill does not exist yet and is drafted from this document. Status: specification, walked with the user on 2026-08-26 and 2026-08-27, then cold-read by eight reviewers and reconciled; the walk's dispositions are in the last section. As a pair document it carries rulings and dates by design; the scrub rule discussed below applies to the documents this process produces, not to this one.

Vocabulary used throughout. A **session** is one running agent conversation. A **seat** is a session with a standing role and its own worktree; this document was written at the prof seat. A **fork** is a subagent that starts with a copy of the session's whole conversation up to the moment it is spawned. A **cell** is one reviewer run of the review skill; a **fresh** cell is one that starts with no conversation at all. **Both runtimes** means Claude Code and Codex, which the review skill already runs its cells on. **The grid** is the review skill's runner, `scripts/md-review-grid.py`, which spawns the cells and collects their reports.

Four stages, kept separate:

- **Writing** — the `draft-md` skill: one write pass, run by a fork of the session.
- **Review** — the existing review skill, `md-review` in this checkout, which the user is renaming `cold-read` in a revision not yet on main. Its fresh cells (`restate`, `defect-hunt`) are its own; this document does not change them. This document adds one **warm cell**: a fork of the session that knows the design and has not seen the draft being written, hunting conflation. Every cell reports; none edits the draft.
- **Reconciliation** — a write pass by another fork: it reads every report from the round, decides each finding from the design and the draft, applies what holds, and records every disposition. Then review runs again, up to a stated limit.
- **Approval** — the user, who enters when the loop has stopped, not before.

What this document depends on that is not yet on main: the `draft-md` design notes at `docs/issues/142-draft-md-skill-design-notes.md` (PR #160, another seat's); the `cold-read` rename and the `defect-hunt` revision that adds an "other complaints" pass and a class (j) for sentence-level omission (the user's in-progress revision of `md-review`, with another agent); and a document term list written by `restate` (proposed to that revision, accepted tentatively at this walk's item 3). Where this document names those, it names what it expects, not what the checkout has.

## The problem

A writing agent holds the whole conversation in its context window and writes as if the reader held it too. The reader — another agent or a human with the repository and the document and nothing else — gets a document with defects at two poles.

**Ellipsis: two things too far apart.** The bridge between them is left out because it was obvious to the writer: a label coined in the conversation used as established vocabulary; "it" or "the restriction" whose referent is three paragraphs back; a step without its precondition or its result; two adjacent claims whose relation is unstated; the case a rule excludes, never mentioned. The reader has to guess, or cannot cross.

**Conflation: two things squeezed into one.** One term for a request's identifier and for the content hash it was computed from; "every check-in" when one kind of check-in behaves differently; several claims packed into one sentence, which is conflation at sentence scale. Its mirror image, one thing under two names in two sections, is found by the same detector and is treated with it. The reader does not guess. The reader restates the sentence confidently and wrongly, because the text is fluent and self-consistent while being wrong about the system, and the error surfaces when someone builds or tests from the document.

The two poles organize the new work in this document; they are not the only defects. The write pass below is the general zero-context prompt, and most of its rules serve both poles. `defect-hunt` already hunts classes neither pole names: contradiction within the file, instructions wrong when obeyed literally, instructions with no stopping point, over-broad absolutes, conflict with CLAUDE.md, names hard to find by search. Nothing here says the list is complete.

The two poles need different detectors. The requirements-engineering literature makes the split: Berry, Kamsties and Krieger's *Ambiguity Handbook* (2003) separates "language ambiguities", which "can be spotted by any reader who has an ear for language", from "software engineering ambiguities", which "can be spotted only by readers that have sufficient domain knowledge". A fresh reader asked for a careful, complete restatement makes ellipsis visible: the gaps are where the restatement stumbles. A fresh reader finds conflation rarely, and only when two passages give the merged thing incompatible properties; a merge that stays consistent reads fine. The reader who can find it is one who knows the design — and that reader must not have watched the sentences form, because an author reviewing their own draft reads what they meant. The warm cell is that reader.

## The mechanism: the write pass, the warm cell, and the reconciliation pass are forks from one snapshot

At the point in a session where the document would be written, the session does not write. It spawns a fork with the write-pass prompt; the fork writes the document to the given path and reports back one line, the path. The session's context has grown by that one line and by nothing of the writing. Every later fork — the warm cell, each reconciliation pass — is spawned from the session at that point, so each holds the design and none has seen the text being formed. The invariant is not that the forks' contexts are identical (each is later by a few one-line reports) but that no fork ever sees drafting. Nothing reviews its own writing. Chain-of-Verification (Dhuliawala et al., ACL Findings 2024) measured the same effect: hallucination fell only when the verification questions were answered "independently so the answers are not biased by other responses".

The reachable failure: a fork that returns more than its one line — an error, a question, a refusal — puts that text into the session's context, and every later fork inherits it. The seat records that it happened in the round's disposition file and continues; the contamination is words about the process, not the draft's text, and the loop's fresh cells are unaffected.

In Claude Code the fork is the Agent tool's `fork` subagent type. On Codex the nearest mechanism is `codex exec resume <session id>`, which continues the session rather than branching it; whether Codex sessions can host this process is open and is not needed for the first build, which runs the forks on Claude Code and only the cold cells on both runtimes.

Cold cells are fresh agents, as the review skill's already are: no conversation, no fork; what the runtime loaded (the checkout's CLAUDE.md), the document, and what the document cites by explicit path.

## The sequence

1. **Write.** A fork writes the draft under the write-pass prompt and reports the path.
2. **Review round.** The grid runs the cold cells (`restate` and `defect-hunt`, both runtimes); the seat spawns the warm conflation cell. All write reports; none edits the draft. The conflation cell also writes the **design term list**: one line per thing the design has, from the design, not from the draft. `restate` writes the **document term list**: one line per thing the draft names, as a reader with no design knowledge takes it. Every report and list path carries the round number, so no round overwrites another.
3. **Term-list diff.** One agent call, given both lists, matches entries by name and by description and writes a diff file: a document entry that matches two design entries (a conflation); a design entry with no document match (an omission, or a deliberate exclusion the draft's opening should name); a document entry with no design match (an invention, a synonym, or a real thing the design missed). Each diff line is a finding for reconciliation; none goes to the user directly.
4. **Reconciliation.** A fork runs the reconciliation prompt, given the draft, the round's reports, the diff, the design term list, and the previous rounds' disposition files. It applies what holds and records every disposition: `applied`, `rejected`, or `open`.
5. **Review again, or stop.** If the reconciliation applied nothing, the loop stops. If it applied something and this was the third reconciliation, the loop stops and the third round's edits reach the user unreviewed, which the seat says at approval. Otherwise the round runs again from step 2.
6. **Approval.** The seat walks the near-final document and what the rounds found, choosing what to present and how; the reports and disposition files stay on disk. A change the user makes starts one more round (steps 2 to 4) and then returns to the user.

**Order inside reconciliation.** Findings are applied in two groups: first, findings that add text or correct text in place; last, findings that split one term into two. A finding that needs both is applied with the splits. The reason is which residue the next round can catch: an addition can create a conflation (the missing definition of a merged term, written as one fused definition), and a split can create an ellipsis (a new name that needs introducing). Ellipsis left by a split is what `restate` finds next round; conflation left by an addition is what the warm cell and the diff find, less reliably. So splits go last, and the fork coins their new names itself in the same pass.

The rules come first and the passes later (user-ruled 2026-08-26): each stage gets the best rules that can be written, and how to split them into passes is decided afterwards. One fact to weigh then: a 2026 benchmark (Purpura et al., arXiv 2601.18554) found instruction compliance reliable at one to six constraints, unpredictable at seven to fifteen, and dropping past fifteen.

## The prompts

Angle-bracket slots such as `<path to the draft>` are filled by the seat before the fork sees the prompt; the fork never fills one. (The convention is the one the ghi-info design uses, [nedschorus#46](https://github.com/nedschorus/nedschorus/issues/46) § "Every prompt".) Each prompt was cold-read once by a fresh Sonnet reader given only the prompt and the checkout's CLAUDE.md, and revised after. The whole document was then cold-read by the grid and reconciled (2026-08-27).

### Write pass (fork)

> You are writing a document to <path>. What it is for, and which system it describes: <one sentence>. Its reader has the repository and this document, full command of English and of standard software vocabulary, and no memory of any conversation. You hold the design; the reader holds none of it. Everything the reader needs that the repository does not already say goes on the page.
>
> 1. **Opening.** The first paragraph states, in the document's own words: which system the document is about, what the document is for, what it covers, and what it leaves out. When the document describes a process, it also states the state the system is in when the process begins.
> 2. **Names.** Use the repository's existing name for a thing. When you must introduce a new name, search the repository for it first — grep for names in files, glob for path names — and if it is already used for something else, choose another. Use one name per thing; when a thing has two names in the repository (an old and a new, a symbol and a label), say so once and use one thereafter. Explain each term the repository or this document defines in the sentence where it first appears, and keep the term.
> 3. **Sentences.** One claim per sentence, and under 25 words when the claim allows; split a long sentence rather than drop its qualifiers. When a sentence describes an action, the actor is the subject and its action is the verb. A condition comes before the action it governs.
> 4. **Steps and cases.** Every step the document prescribes states its result, including when it changes nothing. When a rule has a case it does not cover, name it.
> 5. **Nothing compressed.** Keep articles and the small words that mark relations: that, which, then, because, unless. In the body, state how a thing works before summarizing it or comparing it to something else. Document length is not a defect; a missing step is.
>
> Report back one line: the path.

### Conflation cell (warm; fork; reports only, and writes the design term list)

> A draft is at <path to the draft>. The draft's purpose: <one sentence>. A sibling fork of the session that dispatched you wrote the draft. You inherit that session's context, so you know the design of the part of the system the draft is about; you were not present for the drafting. Find where the draft treats two things as one, or one thing as two. Work from the design, not from the draft.
>
> First write the design term list to <path for the design term list>. A thing is something the design gives an identity to: a component, an artifact, a role, an actor, a state, an event. Each line has three parts: the thing's name; what it is, stated by how it comes to exist and how it is used, rather than by its format; and its purpose. When the design uses one word for two things that have separate identities — created by different events, with separate lifetimes — list them as two things. A thing with several purposes, or several ways of being created, that is still one thing stays on one line.
>
> Then run three checks, each over the whole draft, in this order. A term is a name the draft uses for a thing in the design; ordinary words, paths, and actors outside the design are not terms.
>
> 1. **Terms.** Map every term in the draft onto the list. A draft term that maps onto two list entries is a finding. A draft term that maps onto none is a finding. A list entry that a claim or step in the draft depends on, and that the draft never names, is a finding.
> 2. **Names.** Two draft terms mapping onto one list entry is a finding, unless the draft says they are the same thing.
> 3. **States.** When the draft describes a state machine, make a table of states against events. A cell the draft leaves unaccounted for — no transition, no `no-op`, no error, and not marked impossible by the design — is a finding.
>
> Do not edit the draft. Write your findings to <report path> as a numbered list in the order the findings' passages appear in the draft. Each entry quotes the passage — both passages, when two things are established in different sentences; for an omission, the passage that depends on the missing thing — names the two things merged or the thing missing, says how the design shows it, and gives your confidence: sure, or unsure and why. Do not propose fixes. The file's last line is the number of findings alone, `0` if none. Report back one line: the report path, the design term list path, and that number.

### Reconciliation pass (fork)

> A draft is at <path to the draft>. What it is for: <one sentence>. You know the design it describes and you have not seen it being written. This is reconciliation round <N>. The reviews of the draft are the files at <report paths>; some reviewers knew the design and some did not, and their findings disagree with each other. The term-list diff is at <diff path> and the design term list at <design term list path>; each diff line is a finding. The disposition files of earlier rounds, if any, are at <earlier disposition paths>; every finding marked `open` in them is a finding for this round. Reconcile all of it and revise the draft.
>
> 1. **Every finding gets a disposition.** For each finding: `applied`, `rejected` with the reason, or `open` when neither the design nor the draft settles it. Identify a finding by its file's path and its number; if a file's findings are not numbered, number them in order and record the numbering in the disposition file. A reviewer who never saw the design may misjudge how the design works; a reviewer who knows the design may misjudge what a reader with no such knowledge needs explained. Decide from what the design specifies and what the draft says, not from how certain a reviewer sounds.
> 2. **Additions first, splits last.** Apply findings that add text or correct text in place before findings that split one term into two. A finding that needs both is applied with the splits. When a split calls for new names, you coin them in this pass.
> 3. **New and changed text obeys the write pass.** Every sentence you add or change follows the write-pass prompt, all five rules. Those rules bind the draft, not the disposition file.
> 4. **Edit what a finding needs, and no more.** A finding's edit includes the consistency changes it forces — the other occurrences of a renamed term, a cross-reference, a table row. Text no finding reaches stays as it is, however it reads. If you suspect untouched text has a problem no reviewer flagged, do not edit it: add a finding of your own, labelled `reconciliation-self`, numbered in its own sequence, with disposition `open`.
> 5. **Record.** Write the dispositions to <disposition path>: one line per finding — its file's path or `reconciliation-self`, its number, `applied` / `rejected` / `open`, and the reason. End with three numbers: applied, rejected, open. Write a zero as `0`.
>
> Report back one line: the draft path, the disposition path, and the three numbers.

## What makes a claim checkable, and the provenance scrub

The design notes (§ "Scrub what is not instruction", user-ruled 2026-08-23) remove provenance from durable MDs: commit ids, issue numbers, dates, who decided and when. The write pass's rule 4 and the reconciliation fork's "decide from the design" both push toward factual claims a reader can check. These are two different things. **Decision history** — who ruled, when, in which walk — leaves the document. **What makes a factual claim checkable** — the file path, the test name, the command whose output shows it — stays, because a claim about the system with nothing named to check it against cannot be checked from the document by any reader (Zave and Jackson, "Four Dark Corners of Requirements Engineering", 1997: an assertion "might be true or false and should be validated"; a definition "cannot be false"). The referring-phrase specimen in the design notes — "proven, not merely configured", with nothing naming what proved it — is that failure. The one-sentence addition to the design notes was accepted at this walk (item 12) and is filed as [a comment on PR #160](https://github.com/nedschorus/nedschorus/pull/160#issuecomment-5441523792): "A factual claim about the system names what makes it checkable — the path, the test, or the command. The history of who decided it, and when, does not belong here."

The research behind the prompts — the defect catalog, what covers each defect after the rulings, and the published evidence per rule — is in `docs/issues/142-draft-md-prompt-research-report.md`.

## The experiment (a sketch, specified when it runs)

The research found nothing that measures whether a writer-side prompt makes a document more usable by a zero-context reader, so the skill's acceptance test is new, and it runs after the skill's first draft. Its shape: a handful of existing documents whose sources (the issue, the code, the notes) still exist, chosen when the experiment is specified; two conditions per document, **A**, a session writing in-line under the CLAUDE.md rules followed by the cold cells, and **B**, the sequence above through its first reconciliation; on two documents a third condition **C** with the two reconciliation groups applied in the reverse order. Three measures: `restate` stumbles (an entry that gives two readings or says it cannot tell); the diff's conflation lines; and, for documents that describe a state machine, a derivation test in which a fresh agent derives the state table from the document, marks each row sure or unsure, and the seat checks the sure rows against the design. Identical prompts, models, and source material across conditions. Cost is roughly one working day of agent time against several hundred future uses; the exact counts belong to the specification written when it runs.

## Where this lands

Once this document is on main, the prof seat drafts the `draft-md` skill from it (user-directed 2026-08-26), following the skill-authoring checklist at `docs/wiki/queue/skill-authoring-checklist.md`; the draft gets its own cold-read and walk. The write-pass and reconciliation prompts belong to that skill. The conflation cell's prompt and the grid change that spawns it as a fork belong to the review skill, which the user is revising with another agent; they are proposed there, not made here. The two files this document commits with are this specification and `docs/issues/142-draft-md-prompt-research-report.md`; they go to main under the interim lane (one topic, a fresh branch from main, a PR for the merge-lane seat) while the gatekeeper is dormant.

## Walk order

Walked with the user 2026-08-26 and 2026-08-27; dispositions are marked at each item.

Re-planned 2026-08-26 at the user's direction: the walk follows the process from start to end. The first plan, below the new one, is superseded; its marks stand as history.

1. The starting point: a seat decides to write an MD; why the seat does not write; the snapshot and the fork. — processed 2026-08-26 → accepted.
2. The write pass: the fork and its prompt. — processed 2026-08-26 → accepted as it stands; a proposed rule 6 (contrastive examples per behavior) rejected — clear, correct examples cannot be produced at that early stage; the "what the prompt omits" material (personas, readability targets, caveman) struck as extraneous — no prompt asks for those and no agent volunteers them; per-prompt Sonnet cold reads continued through the walk because they helped the user follow; the whole document then got one cold-read.
3. Cold review: what the review skill's cells produce, and whether one of them produces the document term list. — processed 2026-08-26 → revised: the step is "run cold-read", nothing more. — re-presented 2026-08-27 as a pair with item 6 → accepted tentatively ("worth a try"): `restate` also writes the document term list, one line per thing the draft names as a stranger takes it; proposed to the review skill's revision, not changed here.
4. Warm review, the ellipsis cell: its prompt. — processed 2026-08-26 → rejected: questions 1–3 duplicate cold-read, question 4 was incoherent, question 5 moved to `defect-hunt` as class (j) by the user; ellipsis is cold-read's job and the cell is removed.
5. Warm review, the conflation cell: its prompt and the design term list. — processed 2026-08-27 → revised: checks 1 (terms), 2 (names), and 5 (states) kept; check 3 (universals) cut as covered by `defect-hunt` class (f); check 4 (causes) cut as unworkable. The prompt now has three checks.
6. The term-list diff. — processed 2026-08-27 → accepted tentatively with item 3: one agent call diffs the stranger's list against the design list; every diff line is a finding for reconciliation (changed at the cold-read: the "the human decides" clause put the user mid-loop, against item 9's ruling, so unmatched entries are now `open` findings).
7. Reconciliation: the fork, its prompt, and the order inside it (additions first, splits last). — processed 2026-08-27 → accepted: the prompt as written, the additions-first-splits-last order, and the touch-only-what-a-finding-touches rule. (Cold-read changes: slots for the diff, the design term list, and earlier rounds' dispositions; round-numbered paths; the `self` label became `reconciliation-self`; a finding's edit includes the consistency changes it forces.)
8. The loop: review again, and when it stops. — processed 2026-08-27 → accepted: any change re-runs the round; stop on a round that applies nothing, or after three rounds. (Cold-read change: the rule is now stated once, in terms of `applied`; the third round's edits reach the user unreviewed and the seat says so; a user change runs one more round.)
9. Approval: the user's walk. — processed 2026-08-27 → revised: not the pile; the seat presents its findings in a walk and decides how; reports and dispositions stay on disk — opening the draft on the Mac is manual and not specified.
10. The defect catalog all the prompts derive from. — a first mark of 2026-08-27 misread the user (his "manual, needs no spec" was about opening the draft on the Mac, item 9); the section was restored and the item re-presented. — processed 2026-08-27 → accepted: the catalog moves out of the specification into the research report, for whoever revises a rule later.
11. What the evidence supports, and what it does not. — processed 2026-08-27 → accepted: both sections and the catalog moved to `docs/issues/142-draft-md-prompt-research-report.md`; this specification cites it in one line.
12. The tension: checkable source versus provenance scrub. — processed 2026-08-27 → accepted: the one-sentence addition to the design notes' scrub section is proposed as a comment on PR #160 (another seat's PR).
13. The experiment. — processed 2026-08-27 → accepted as the skill's acceptance test, to run after the skill's first draft. (Cold-read change: reduced to a sketch with its measures defined; the counts, which did not follow from the design, are removed until it is specified.)
14. Where this lands, and the commit. — processed 2026-08-27 → accepted: cold-read of this specification first, then one commit of both files on the prof branch, a fresh branch from main with the commit cherry-picked, and a PR for the merge lane; then the prof seat drafts the `draft-md` skill.

Superseded first plan (2026-08-26; its item 1 was revised four times before the re-plan, and items 9, 13, and 14 carry marks made while it was current):

1. Purpose and the bar: the human is the final approver; both poles; reviewers fresh or warm, never the writer; one write pass, one reconciliation pass, both forks. — revised 2026-08-26 → the intro over-focused on the two poles: it must name the write pass as the general zero-context prompt and must not imply the existing cells are complete except for the poles. — revised again 2026-08-26 → the intro ran writing and reviewing together and skipped reconciliation; four separate stages now. — revised a third time 2026-08-26 → draft-md is a single pass and cannot hunt itself: the ellipsis and conflation hunts became warm review cells that report and do not edit; reconciliation is the only other write pass; `md-review` is being renamed `cold-read`. — revised a fourth time 2026-08-26 → no five-rule cap: write the best rules, group them into passes later.
2. The defect catalog: two poles, eleven classes and a catch-all, one writer rule and one reader question each.
3. The fork-from-snapshot mechanism: write pass, warm cells, reconciliation pass.
4. The order inside reconciliation: ellipsis findings first, conflation findings last, and the residue rule that fixes it.
5. The write-pass prompt.
6. The ellipsis cell prompt.
7. The conflation cell prompt and the design term list.
8. The document term list and the term-list diff — which cold cell produces the document term list.
9. The catch-all. — processed 2026-08-26 → absorbed into the user's `defect-hunt` revision as the "other complaints" pass; nothing separate remains here.
10. The reconciliation-pass prompt, the loop, and the human's entry point.
11. The tension: checkable source versus provenance scrub.
12. What the evidence does not support.
13. The experiment.
14. Where this lands, and the commit.
