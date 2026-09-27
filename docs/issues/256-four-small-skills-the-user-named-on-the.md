---
issue: "[Four small skills the user named on the vocabulary page: /save, /push, /save-MD, /save-MD-as-draft (name open)](https://github.com/nedschorus/nedschorus/issues/256)"
---

# Four small skills the user named on the vocabulary page: /save, /push, /save-MD, /save-MD-as-draft (name open)

## Why

On 2026-09-05, while rewriting the project vocabulary page by hand (GHI [Project vocabulary wiki page: define this project's own terms so a zero-context reader can resolve them](https://github.com/nedschorus/nedschorus/issues/213), `docs/wiki/queue/213-project-vocabulary.md`), the user named four skills that do not exist and asked, in the MD-skills seat's session, for one issue to create them: "make a GHI to create the skills I suggest. They should be pretty simple." He also ruled that none of them is listed on the vocabulary page until it exists.

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
- GHI [Queue drain procedure — the review process that empties wiki/queue, the pair queue, and the draft-label issue queue](https://github.com/nedschorus/nedschorus/issues/24), the queue drain procedure, is the review that the **/save-MD-as-draft** destination feeds.
- GHI [Build draft-md: the drafting-stage skill run before md-review (user-ruled 2026-08-22)](https://github.com/nedschorus/nedschorus/issues/142), draft-md, is about drafting an MD's text, not moving it.

Search receipt: `gh issue list --repo nedschorus/nedschorus --state all --limit 100 --search "<terms>"` for "save skill", "push skill", "skill move MD", "draft-md", "check-in skill", 2026-09-05: no issue names any of the four.

## Open questions for the user, to settle before the build

1. **/save-MD-as-draft's destination.** The project has three review queues: `docs/wiki/queue/`, `docs/issues/queue/`, and the `draft` issue label; `docs/drafts/` holds in-progress documents that are not queued for review. Which directory does the skill move a file into, or does it choose by the file's kind?
2. **/save-MD's rules.** "The right place" for an MD is what GHI [MD-placement guidance as symmetric pre-tool remind hooks on both runtimes (boss-directed design, build deferred)](https://github.com/nedschorus/nedschorus/issues/11) was to define. Does /save-MD wait for GHI [MD-placement guidance as symmetric pre-tool remind hooks on both runtimes (boss-directed design, build deferred)](https://github.com/nedschorus/nedschorus/issues/11), or carry a short table of its own (wiki page, GHI-MD, design, walk file, draft)?
3. **/save's scope.** Commit everything in the working tree, or only the files named? Push to the seat's own branch on origin, never to main.

## Next action

The MD-skills seat builds them, simplest first: **/save**, then **/save-MD-as-draft** and **/save-MD** once questions 1 and 2 are answered, then **/push** as a thin entry to GHI [pull-request skill: how a change reaches main — durable-file disposition, the description, and topic-branch creation](https://github.com/nedschorus/nedschorus/issues/236)'s skill when that lands. Each skill is a `SKILL.md` under `.claude/skills/<name>/`, on its own topic branch, cold-read before it lands, one PR each to merge-lane.
