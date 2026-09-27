---
issue: "[adjudicate skill: how a fresh agent resolves a conflict between agents, and when it calls the user (the glossary defines the adjudicator; user-asked 2026-09-06)](https://github.com/nedschorus/nedschorus/issues/265)"
---

# adjudicate skill: how a fresh agent resolves a conflict between agents, and when it calls the user (the glossary defines the adjudicator; user-asked 2026-09-06)

## Why

The nedschorus glossary (`docs/wiki/nedschorus-glossary.md`, the user's own text) defines "**adjudicator** — a fresh agent, used to resolve conflicts between agents." (user-ruled 2026-09-06, in the cold-read triage walk of the glossary). No procedure for one exists anywhere in the tree: nothing says who spawns an adjudicator, what it reads, what it produces, or when it stops. The six-cell cold read of the glossary asked for that procedure four times; the user ruled it off the page ("The rest is implementation detail") and asked for issues on the missing skills the page implies.

## What the skill does

A `SKILL.md` under `.claude/skills/adjudicate/` (name to settle before the build; glob `.claude/skills/adjudic*` finds nothing) that an agent loads when two agents' work conflicts and neither can settle it: a hard merge, a disagreement over whether the code or the test is wrong, or another problem that may need the user. The user's words on how it works, 2026-09-06: "Id assume that the adjudicator usually can resolve disputes without me-say complex merges. They only call for help when they can't (or they run out of chances." So the skill says: how the adjudicator is spawned as a fresh agent that had no part in the conflict, what it is given to read (all the documents relevant to the conflict, from both sides), that it resolves the conflict itself when it can, how many chances it has, and that it calls on the user only when it cannot or when the chances run out. It records its resolution where the conflict was.

## What exists

Skills on main: cold-read, ghi-write, handoff, walk-me-through; issues for the others the glossary names: GHI [Four small skills the user named on the vocabulary page: /save, /push, /save-MD, /save-MD-as-draft (name open)](https://github.com/nedschorus/nedschorus/issues/256) (save, push, save-MD), GHI [update-glossary skill: the editor rules for the nedschorus glossary, taken off the page (user-asked 2026-09-06)](https://github.com/nedschorus/nedschorus/issues/262) (update-glossary), GHI [sanity-check skill: wrap the sanity-checker instrument so any agent can run it on a design (the glossary lists it; user-asked 2026-09-06)](https://github.com/nedschorus/nedschorus/issues/263) (sanity-check). Search receipt: `gh issue list --repo nedschorus/nedschorus --state all --limit 100 --search "adjudicator"`, 2026-09-06: no issue.

## Next action

The MD-skills seat writes the skill on its own topic branch, cold-read before it lands, one PR to merge-lane. Settle the name and the number of chances with the user first.
