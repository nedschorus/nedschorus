---
issue: "[Four small skills the user named on the vocabulary page: /save, /push, /save-MD, /save-MD-as-draft (name open)](https://github.com/nedschorus/nedschorus/issues/256)"
---

# Four small skills the user named on the vocabulary page: /save, /push, /save-MD, /save-MD-as-draft (name open)

## Why

On 2026-09-05, while rewriting the project vocabulary page by hand (GHI [Project vocabulary wiki page: define this project's own terms so a zero-context reader can resolve them](https://github.com/nedschorus/nedschorus/issues/213), then `docs/wiki/queue/213-project-vocabulary.md`, which became the glossary, `docs/nedschorus-wiki/nedschorus-glossary.md`), the user named four skills that do not exist and asked, in the MD-skills seat's session, for one issue to create them: "make a GHI to create the skills I suggest. They should be pretty simple." He also ruled that none of them is listed on the vocabulary page until it exists.

## The four skills, in the user's words from the page

- **/save** — "a missing skill used to push files to git, but no further, not to main, just to save this version, no reviews required."
- **/push** — "a missing skill used to initiate the design to main workflow."
- **/save-MD** — "If we need a skill to help move MD files to the right place."
- **/save-MD-as-draft** — "a skill used to move an MD file into the directory of files that need to be reviewed by the user." With his note on the name: "we can't reserve the word draft - it's too common and will generate too many conflicts." So this skill's final name is open.

## What exists today

Skills on main: `.claude/skills/cold-read`, `ghi-write`, `handoff`, `walk-me-through`. None of the four.

Related issues, none the same matter:

- GHI [pull-request skill: how a change reaches main — durable-file disposition, the description, and topic-branch creation](https://github.com/nedschorus/nedschorus/issues/236), the pull-request skill (how a change reaches main), is the workflow **/push** starts. GHI [pull-request skill: how a change reaches main — durable-file disposition, the description, and topic-branch creation](https://github.com/nedschorus/nedschorus/issues/236) stays the design home; this issue only records the user's name for the entry point.
- GHI [MD-placement guidance as symmetric pre-tool remind hooks on both runtimes (boss-directed design, build deferred)](https://github.com/nedschorus/nedschorus/issues/11), MD-placement guidance as pre-tool remind hooks, holds the placement rules **/save-MD** would apply.
- GHI [Queue drain procedure — the review process that empties the wiki queue, the pair queue, nc-queue, the drafts directory and the queue-drain-candidate-label issue queue](https://github.com/nedschorus/nedschorus/issues/24), the queue drain procedure, is the review that the **/save-MD-as-draft** destination feeds.
- GHI [Build draft-md: the drafting-stage skill run before md-review (user-ruled 2026-08-22)](https://github.com/nedschorus/nedschorus/issues/142), draft-md, is about drafting an MD's text, not moving it.

Search receipt: `gh issue list --repo nedschorus/nedschorus --state all --limit 100 --search "<terms>"` for "save skill", "push skill", "skill move MD", "draft-md", "check-in skill", 2026-09-05: no issue names any of the four.

## Skills, not agent-instructions

All four stay skills. On 2026-09-06 the user decided that instructions are a skill only when they are used outside the state machine, and that the instructions a state of the state machine launches its agent with are that state's agent-instructions, not a skill; GHI [Candidate skill: write-test-plan — consequence-ranked test plan with observable oracles and traceability (likely FIRST build)](https://github.com/nedschorus/nedschorus/issues/18) quotes those 2026-09-06 words in its section "2026-10-30: write-test-plan is a skill", where that issue applies the rule, and `docs/design-to-main/design-to-main-state-machine-design.md` applies the rule in its paragraph "Skills and agent-instructions": "A skill is agent-instructions a person invokes." The state machine is design-to-main's. The user named each of the four as a command a person types, and none is the text a state of design-to-main launches its agent with: **/save**, **/save-MD** and **/save-MD-as-draft** save or move files outside any run of the machine, and **/push** is what a person types to start the design-to-main workflow, so it too is invoked from outside the machine.

## Open questions for the user, to settle before the build

1. **/save-MD-as-draft's destination.** The project has three review queues: `docs/nedschorus-wiki/queue/`, `docs/issues/queue/`, and the `queue-drain-candidate` issue label; `docs/drafts/` holds in-progress documents that are not queued for review. Which directory does the skill move a file into, or does it choose by the file's kind?
2. **/save-MD's rules.** "The right place" for an MD is what GHI [MD-placement guidance as symmetric pre-tool remind hooks on both runtimes (boss-directed design, build deferred)](https://github.com/nedschorus/nedschorus/issues/11) was to define. Does /save-MD wait for GHI [MD-placement guidance as symmetric pre-tool remind hooks on both runtimes (boss-directed design, build deferred)](https://github.com/nedschorus/nedschorus/issues/11), or carry a short table of its own (wiki page, GHI-MD, design, walk file, draft)?
3. **/save's scope.** Commit everything in the working tree, or only the files named? Push to the seat's own branch on origin, never to main.
4. **/push's workflow.** The user's words say /push starts the design-to-main workflow, whose design, `docs/design-to-main/design-to-main-state-machine-design.md`, names an entry skill that the user invokes, `initiate-design-to-main`; this issue's other text ties /push to GHI [pull-request skill: how a change reaches main — durable-file disposition, the description, and topic-branch creation](https://github.com/nedschorus/nedschorus/issues/236)'s pull-request skill. Which of the two /push starts, and whether /push is another name for `initiate-design-to-main`, the user has not decided.

## Next action

The MD-skills seat builds them, simplest first: **/save**, then **/save-MD-as-draft** and **/save-MD** once questions 1 and 2 are answered, then **/push** as a thin entry to GHI [pull-request skill: how a change reaches main — durable-file disposition, the description, and topic-branch creation](https://github.com/nedschorus/nedschorus/issues/236)'s skill when that lands. Each skill is a `SKILL.md` under `.claude/skills/<name>/`, on its own topic branch, cold-read before it lands, one PR each to merge-lane.
