---
issue: "[update-glossary skill: the editor rules for the nedschorus glossary, taken off the page (user-asked 2026-09-06)](https://github.com/nedschorus/nedschorus/issues/262)"
kind: design
---

# update-glossary skill: the editor rules for the nedschorus glossary, taken off the page (user-asked 2026-09-06)

## Why

The project vocabulary glossary, `docs/nedschorus-wiki/nedschorus-glossary.md` (landed as PR [Land the project vocabulary glossary as the wiki's first page, and point CLAUDE.md at it](https://github.com/nedschorus/nedschorus/pull/258) on 2026-09-06; GHI [Project vocabulary wiki page: define this project's own terms so a zero-context reader can resolve them](https://github.com/nedschorus/nedschorus/issues/213)), is the user's own text and every agent reads it through CLAUDE.md's pointer. Its purpose paragraph carried instructions to whoever edits the page: no links, which terms qualify, which skills to list. In the cold-read triage walk of 2026-09-06 the user ruled those sentences off the page: "they are intended for the writer or editor of vocab, not for the readers of the vocab. So I guess we need a minimal add-vocab skill for these how to add vocab instructions", and then: "sounds like we need a GHI for the update-glossary skill." This issue is that GHI.

## What the skill does

A minimal skill, loaded when an agent is about to add, change or remove an entry on the glossary. It carries the editor rules the page no longer states, all the user's rulings of 2026-09-05 and 2026-09-06 (minutes: `docs/walk/project-vocabulary-page-drain-minutes.md` and `docs/walk/project-vocabulary-glossary-cold-read-triage-minutes.md`, on the MD-skills branch until they land):

1. The user approves every entry; an agent proposes, with the complete old and new sentence, and the user rules.
2. No links on the page: a link forces the reading agent to read the linked document. A file name in plain text is not a link.
3. Include only terms that all or most agents might need; leave out terms that will be rarely needed (the user's example of one that stays off: cold-read-cell, met only by the cold-read agents).
4. Generic SDLC vocabulary is absent; a standard term is listed only if the project attaches a meaning of its own to it.
5. Skills that a fresh agent needs to understand the documents are listed, slash first, skills before terms; a skill is not listed until it exists.
6. Alphabetical order, one line per entry, short.
7. Facts about the environment (machines, repositories, the user) belong in CLAUDE.md, not the glossary.
8. A new coined name follows CLAUDE.md's naming rule and is checked with grep and glob before it is used.
9. An entry gives the minimum context a naive agent needs and no more; for a skill, that is one line, because the skill's own front matter says the rest. His words, 2026-09-06: "Glossary should provide the minimum context a naive agent needs. They can always search/hunt for more."

## A skill, not agent-instructions

update-glossary stays a skill. On 2026-09-06 the user decided that instructions are a skill only when they are used outside the state machine, such as at his request, and that the instructions a state of the state machine launches its agent with are that state's agent-instructions, not a skill; GHI [Candidate skill: write-test-plan — consequence-ranked test plan with observable oracles and traceability (likely FIRST build)](https://github.com/nedschorus/nedschorus/issues/18) quotes those 2026-09-06 words in its section "2026-10-30: write-test-plan is a skill", where that issue applies the rule. The state machine is design-to-main's. These editor rules are used outside it, by whichever agent is about to change the glossary, usually because the user asked for the change. No state of design-to-main changes the glossary: neither `docs/design-to-main/design-to-main-state-machine-design.md` nor any of its queued agent-instructions, `docs/agents/queue/design-to-main-*`, tells an agent to edit it. And the user asked for these rules as a skill, in the words quoted under Why.

## Name

Settled: **update-glossary** (user-ruled 2026-09-06: "update-glossary is good"). Earlier words for it were "add-vocab", "update-vocabulary" and "add-glossary-entry"; none is used. `.claude/skills/update-glossary/` does not exist yet.

## What exists

Skills on main: cold-read, ghi-write, handoff, walk-me-through. Related: GHI [Four small skills the user named on the vocabulary page: /save, /push, /save-MD, /save-MD-as-draft (name open)](https://github.com/nedschorus/nedschorus/issues/256) (four other small skills the user named on the same page), GHI [Project vocabulary wiki page: define this project's own terms so a zero-context reader can resolve them](https://github.com/nedschorus/nedschorus/issues/213) (the page). Search receipt: `gh issue list --repo nedschorus/nedschorus --state all --limit 100 --search "<terms>"` for "vocabulary skill", "glossary skill", "update-glossary", "add-vocab", 2026-09-06: no issue names this skill.

## Next action

The MD-skills seat writes `.claude/skills/update-glossary/SKILL.md` with the nine rules above in the user's words where he gave them, on its own topic branch, cold-read before it lands, one PR to merge-lane. When it lands, the glossary's purpose paragraph may point at it.
