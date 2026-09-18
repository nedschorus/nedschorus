---
status: rulings record and working material for issue [Sweep the project's bare generic words to project terms, under the 2026-09-15 three-form rule](https://github.com/nedschorus/nedschorus/issues/386)
as-of: 2026-09-17
---

# The project-term sweep: what the user ruled, and the work it leaves

The pair document of issue [Sweep the project's bare generic words to project terms, under the 2026-09-15 three-form rule](https://github.com/nedschorus/nedschorus/issues/386). The issue body carries the summary and the next action; this file carries the substance: the five rulings from the MD-skills seat's walk of 2026-09-15 with the user's own words, the rename list ruled at the cold-read-research seat the same day, the terms the MD-skills seat proposes, and the cold-read skill change that makes the sweep self-sustaining. The walk file and its minutes are Mac-local files at the MD-skills seat's checkout, under `docs/walk/`, a gitignored directory that does not exist on main, so this is the durable copy.

## The rule

Landed in PR [Glossary: project terms are hyphenated phrases, abbreviations or slash names; the seat model's words become headwords; CLAUDE.md says so](https://github.com/nedschorus/nedschorus/pull/384), merged 2026-09-15 17:25Z, as the last three sentences of `CLAUDE.md`'s naming bullet:

> A word used in a project-specific sense is a project term, and a project term takes one of three forms: an abbreviation such as GHI, a skill's slash name such as /handoff, or a hyphenated phrase such as agent-seat, never a bare generic word. Every project term is in the glossary; a term the glossary does not list is not a project term. If you need a new one, propose it to the user.

Two rulings behind it, his words: "There's either stuff in the glossary or not", and, on how a new term arrives, "I think a walk is overkill for something as simple as this". A new term is proposed to him in one message, not walked.

Earlier the same day he ruled the renames themselves ("rename.") and how they happen: "I think as we find problematic names we should fix them. And so we'll have to update the skill. However maybe I should approve these global name changes, just in case."

### Changed on 2026-09-16

The rule above is no longer in `CLAUDE.md`, and the rulings below were made under it. Read them against the rule as it now stands:

- **The three sentences are gone.** PR [CLAUDE.md: the glossary line says to propose a coined term; the project-term sentences go](https://github.com/nedschorus/nedschorus/pull/422), merged 2026-09-16 20:12Z, removed them. His words: "it's not true because we have not auditted the project and the project keeps changing", and "remove 3 trms". What `CLAUDE.md` keeps is one sentence in its glossary bullet: "If you need to coin a new term, a word with a meaning specific to this project, propose it to the user."
- **A bare word no longer needs a hyphen.** The three term forms now live only in the glossary's preamble. PR [Glossary preamble: a word needs a defined term only when its project meaning is unexpected or hard to guess](https://github.com/nedschorus/nedschorus/pull/428), merged 21:06Z, dropped "never a bare generic word such as seat" there and added his test: "A word needs a defined term only where this project does something unexpected with it or gives it a meaning that would be hard to guess; otherwise it stays ordinary prose." His words behind it: "Just because a term means something to this project, doesn't mean it needs a defined term. It needs a defined term if this project is doing something unexpected or imputing a specific mean to a term that would be hard to guess."
- **"runtime" becomes `agent-cli`.** At item 10 of the MD-skills seat's walk of the issue [cold-read grid: retry a failed cold-read-cell once, report its cause, and name a runtime that is down](https://github.com/nedschorus/nedschorus/issues/413) design's cold read, he asked "how about agent-cli - is that better" and answered "y" to the scope put to him. The glossary gets the entry, the files that say "runtime" move to `agent-cli` through this sweep, and the provenance stamp field `runtime=` stays. That replaces "runtime stays a bare word" under "Terms the MD-skills seat proposes" below.

## The five rulings of the 2026-09-15 walk

The walk put five questions the rule does not settle. Item 1 blocked the others, because a sweep with no boundary cannot start.

### 1. How far the sweep reaches

The seat put him counts of one word. "Record" here means a folder holding one document review: 12 uses in operative prose (`CLAUDE.md` and `.claude/skills/`), 917 in `scripts/`, 820 in `docs/`, 7,104 in `cold-read-records/`. The seat recommended sweeping instructions, wiki pages and script comments, and leaving git history, walk minutes, saved review reports, the frozen test set (`cold-read-reviewer-test-cases/`, the labelled documents reviewer models are scored against) and closed issues untouched.

His words: "agreed - we don't want to change logs and records, we want to make stuff that is being used or will be used easier to read"

The test he gave is broader than the file list and governs: a file is in the sweep if it is being used or will be used, not because of the directory it sits in. Logs and records are out because nothing reads them to decide what to do. So operative prose, wiki pages, script comments and designs still to be implemented are in. Git history, walk minutes, saved review reports, the frozen test set and closed issues are out. A file whose status is unclear is judged by his test, not by its path, and if the sweeping agent cannot tell, it asks him rather than guessing. This supersedes the earlier sizing of "36 files of operative prose".

### 2. The word "walk"

At the cold-read-research seat he approved renaming the bare word "walk" to `approval-walk` on `docs/nedschorus-wiki/agent-seat-model.md`. The rule says every project term is in the glossary, and the glossary had `walk-minutes` and `walked-approval` but no entry for the walk itself. So the rename as approved produced a word the rule denies is a term.

Ruled "y" to adding the term. The alternative offered and declined was to use `walked-approval` on the page instead.

Commitment: add to `docs/nedschorus-wiki/nedschorus-glossary.md` the headword `approval-walk`, defined as presenting material to the user one item at a time for a decision, conducted by the skill `/walk-me-through`.

### 3. "fresh reader or fresh agent"

The glossary's entry `fresh reader or fresh agent` was the one headword PR [Glossary: project terms are hyphenated phrases, abbreviations or slash names; the seat model's words become headwords; CLAUDE.md says so](https://github.com/nedschorus/nedschorus/pull/384) left non-conforming. The rename to `fresh-agent` he had approved earlier in the day would have deleted "fresh reader" from five sentences of live instruction text: twice in `.claude/skills/cold-read/SKILL.md`, twice in `.claude/skills/cold-read/prompts/fast-clarify.md`, once in `.claude/skills/ghi-write/SKILL.md`.

His words: "My guess is that fresh-reader is more specific than fresh-agent, so we probably should keep both, but if so, make sure we use the right one in the right places"

So the entry becomes two hyphenated headwords, `fresh-reader` and `fresh-agent`, each defined.

At the walk the seat disagreed on which is more specific, reading `fresh-agent` as the narrower (a running minimal-context process) and `fresh-reader` as the broader (whoever reads later, human or agent). A grep of `CLAUDE.md`, `.claude/skills/` and the glossary after the walk settled it his way: besides the five "fresh reader" sentences there are two uses of "fresh agent" that are not readers at all, "a fresh agent's commit" in `CLAUDE.md`'s merge bullet and "a fresh agent" in the glossary's `agent-arbitrator` entry. So `fresh-agent` is the broad term, any minimal-context agent in any role, and `fresh-reader` is the narrow one.

Put to him 2026-09-15, awaiting his word: the five "fresh reader" sentences keep their word and gain the hyphen; the two non-reader uses become `fresh-agent`, the `CLAUDE.md` one only if he confirms it is the project sense; and the glossary entry splits into

    - **fresh-agent** — a minimal-context agent: one that has read only its agent-instructions, the documents selected for it to read, and (recursively) the documents linked from the selected documents.
    - **fresh-reader** — a fresh-agent, or a person, reading a document with no context beyond the document and what it links. This project's durable documents, wiki pages, skills and designs, the documents of lasting value, are written for fresh-readers rather than for the user, to enable parallelism and increase reliability.

No file changes until he answers.

### 4. The project's own name

The glossary entry `- **NedsChorus (aka NC)** — this project.` did not take one of the three forms. The seat proposed a fourth permitted form, "a proper name such as NedsChorus", in both the glossary preamble and `CLAUDE.md`.

His words: "dont like - opens the slipperly slope about proper names - what are they. Let's just include NC as an abbreviation, and define it as this project NedsChorus or something like that."

Ruled instead: the headword becomes the abbreviation, already a permitted form, so no rule changes at all.

    OLD: - **NedsChorus (aka NC)** — this project.
    NEW: - **NC** — this project, NedsChorus.

"NedsChorus" stops being a project term and becomes an ordinary name used in prose. No change to the glossary preamble and none to `CLAUDE.md`.

### 5. File names already on main

The older half of the naming bullet already asks for multi-part file names; the new rule is about words in prose. The question was whether together they mean existing files get renamed. The argument put to him: a renamed file breaks every document citing its path, this project cites paths constantly, nothing finds and fixes those citations automatically, and a file name is used by being found, not by being read.

Ruled "y": the naming rule binds new file names only. An existing file is renamed only when someone is already editing it for another reason. No full rename of existing files.

## Ruled at the cold-read-research seat, superseded 2026-09-17

Renames for `docs/nedschorus-wiki/agent-seat-model.md` were ruled at that seat on 2026-09-15. The list as it was ruled that day, kept because a record that drops a superseded ruling leaves the next reader no way to tell which version he is looking at:

seat → agent-seat; handoff → session-handoff; supervisor → handoff-supervisor; session → agent-session; brief → seat-brief; slice → build-slice; walk → approval-walk (the skill name `/walk-me-through` stays); "a seat's work" → "the agent-seat's subject area". Dropped as not a term: "series" ("how is task series different from tasks"), spelled out as "a series of related tasks". That seat's branch left the page's words alone so the rename could happen in one pass.

**Do not apply that list.** On 2026-09-17 the user overruled it, under the test the glossary preamble now carries (`docs/nedschorus-wiki/nedschorus-glossary.md`): a word needs a defined term only where this project does something unexpected with it or gives it a meaning that would be hard to guess. What he ruled in its place, for the seat model page and, on `docs/nedschorus-wiki/fleet-git-worktree-working-model.md`, for its Reader's key and for the per-seat briefs named in its scope note:

- Three words take their glossary terms, everywhere they appear: seat → agent-seat, supervisor → handoff-supervisor, reincarnate → reincarnate-seat.
- Session, handoff, brief, slice and walk stay plain words, and so do the branch words, "seat branch" and "topic branch".
- "A seat's work" is not renamed at all. Its definition leaves the page's list of words and becomes body prose: an agent-seat's work is the body of related work it owns, a subject area with shared context rather than an ordered queue, its tasks named by its brief.

## Still open: the new name for `dispositions.md`

The triage record both review instruments write beside their reports is named with one part, and the name does not say dispositions of what. On 2026-09-15, at item 3 of the `/sanity-check` skill triage walk at the cold-read-research seat (that seat's walk minutes, Mac-local), the user ruled that the name stays for now and handed the rename to this sweep. So the rename is the sweep's to make, as the one exception to ruling 5 he made himself; what is open is the name, which the MD-skills seat proposes to him in the same message as the cold-read terms below. It is written by `.claude/skills/cold-read/SKILL.md` step 7, read by `scripts/cold-read-record-ship.py`, and present in every shipped record, so the rename touches skill prose, a script and the shipper's expectations together.

## Terms the MD-skills seat proposes

Not yet put to him. Under his ruling these go as one message from the MD-skills seat, not a walk, and nothing in operative prose or scripts is swept to them before he answers. All instrument-first, matching the sanity-check seat's `sanity-check-cell` and `sanity-check-record`; "runtime" stays a bare word in both instruments, naming the command-line tool that ran the model.

- `cold-read-cell`: one reviewer model reading one target under one prompt. Already 41 uses in the tree.
- `cold-read-record`: the directory holding one run's reports, its frozen target and its dispositions. 24 uses.
- `cold-read-grid`: the program that launches the six cold-read-cells, `scripts/cold-read-grid.py`.
- `cold-read-tier`: which model a cold-read-cell runs, and at what effort. 5 uses.
- `cold-read-fast-read`: the one-reviewer pass that precedes the full run, matching `scripts/cold-read-fast-read.py`.
- `cold-read-full-run`: the six-cold-read-cell run.
- `cold-read-target`: the document under review, frozen at launch.

`cold-read-fast-read` and `cold-read-full-run` were `fast-cold-read` and `full-cold-read` until 2026-09-15, when he renamed the sanity-check seat's `review-request` to `sanity-check-request`, "instrument first like the rest".

## The cold-read skill change that makes this self-sustaining

`.claude/skills/cold-read/SKILL.md` has no route for a terminology finding whose fix is a rename beyond the document under review, so such findings get rejected as out of scope. On 2026-09-14 fifteen rename proposals were rejected in `cold-read-records/2026-09-14-nedschorus-file-naming-and-location-standards-3/dispositions.md` (shipped to `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/`) as "the project's settled words", none reached the user, and his ruling the next day went the other way, although step 7 already says to ask before rejecting a criticism.

Proposed addition to step 7, making four ask-the-user cases five: "...and when the fix is renaming a term this document does not own. A term this document does not own is one other files use, so renaming it is a change across the project and his to approve: put him the reviewer's proposed name, and on his approval make the rename its own task and its own change rather than folding it into this one. Record in `dispositions.md` that the rename was approved and where it went, or that he declined it." A declined rename leaves the document's word as it is and the finding recorded as declined; the document is not held for it.

No change is needed to `.claude/skills/cold-read/prompts/terminology.md`: it already asks each reviewer for the exact words of a fix, and its option (c) is a constructed name following `CLAUDE.md`'s naming rule, so the conforming name arrives in the report. Skill text is operative prose, so this change takes a cold read and the user's walk before a pull request, and the edit needs a `.walk-approved` marker quoting his words.
