---
issue: "[adjudicate skill: how a fresh agent resolves a conflict between agents, and when it calls the user (the glossary defines the agent-arbitrator)](https://github.com/nedschorus/nedschorus/issues/265)"
---

# adjudicate skill: how a fresh agent resolves a conflict between agents, and when it calls the user (the glossary defines the agent-arbitrator)

## Why

The nedschorus glossary (`docs/nedschorus-wiki/nedschorus-glossary.md`, the user's own text) defines "**agent-arbitrator** — a fresh-agent, used to resolve conflicts between agents." The user decided the entry on 2026-09-06, in the cold-read triage walk of the glossary, under the headword "adjudicator"; on 2026-09-07 he decided "Keep arbitrator - scrub out adjudicator" (item 4 of the minutes `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/state-machine-design-third-cold-read-decisions-minutes.md`), and the headword is agent-arbitrator today. When this issue was filed, no procedure for one existed anywhere in the tree: nothing said who spawns an agent-arbitrator, what it reads, what it produces, or when it stops. The six-cell cold read of the glossary asked for that procedure four times; the user ruled it off the page ("The rest is implementation detail") and asked for issues on the missing skills the page implies.

## What the skill does

A `SKILL.md` under `.claude/skills/adjudicate/` (name to settle before the build; glob `.claude/skills/adjudic*` finds nothing) that an agent loads when two agents' work conflicts and neither can settle it: a hard merge, a disagreement over whether the code or the test is wrong, or another problem that may need the user. The user's words on how it works, 2026-09-06: "Id assume that the adjudicator usually can resolve disputes without me-say complex merges. They only call for help when they can't (or they run out of chances." So the skill says: how the agent-arbitrator is spawned as a fresh agent that had no part in the conflict, what it is given to read (all the documents relevant to the conflict, from both sides), that it resolves the conflict itself when it can, how many chances it has, and that it calls on the user only when it cannot or when the chances run out. It records its resolution where the conflict was.

## What exists

Two agent-arbitrators now have their procedure written as agent-instructions, and neither is a skill: design-to-main's arbitrator, whose agent-instructions are queued at `docs/agents/queue/design-to-main-test-suite-arbitrating-agent-instructions.md`, and the agent-arbitrator that merge-lane-2 commissions when a pull request's fix-round leaves blocking findings unfixed, whose brief is in merge-lane-2's seat-brief, `nedlern@ned-box:/home/nedlern/agents/merge-lane-2/CLAUDE.local.md`, line 75. Search receipt, 2026-11-12: `grep -rln -i arbitrator docs/agents nc-systems .claude` in the repository, and `grep -n -i arbitrat` on merge-lane-2's seat-brief; `.claude/skills/` holds no directory whose name contains "arbitrat" or "adjudic".

Skills on main: cold-read, ghi-write, handoff, walk-me-through; issues for the others the glossary names: GHI [Four small skills the user named on the vocabulary page: /save, /push, /save-MD, /save-MD-as-draft (name open)](https://github.com/nedschorus/nedschorus/issues/256) (save, push, save-MD), GHI [update-glossary skill: the editor rules for the nedschorus glossary, taken off the page (user-asked 2026-09-06)](https://github.com/nedschorus/nedschorus/issues/262) (update-glossary), GHI [sanity-check skill: wrap the sanity-checker instrument so any agent can run it on a design (the glossary lists it; user-asked 2026-09-06)](https://github.com/nedschorus/nedschorus/issues/263) (sanity-check). Search receipt: `gh issue list --repo nedschorus/nedschorus --state all --limit 100 --search "adjudicator"`, 2026-09-06: no issue; the same search for "arbitrator", 2026-11-12: no issue. Issue bodies here are links only, so these searches match titles.

## Next action

The MD-skills seat writes the skill on its own topic branch, cold-read before it lands, one PR to merge-lane. Settle the name and the number of chances with the user first.
