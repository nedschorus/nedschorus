---
issue: "[A wiki page of the project's goals and philosophies: how agents work with the user, and how they build and finish work](https://github.com/nedschorus/nedschorus/issues/2411)"
---

# A wiki page of the project's goals and philosophies: how agents work with the user, and how they build and finish work

## Why

The user wrote, on 2026-10-28 in cold-read-improvement's agent-session on ned-box: "we don't have a good high concept document for this project, and we probably need one that collects maybe 10 of these sort of high level approaches. And that's maybe something that should be a GHI or a task". He approved filing this GHI on 2026-11-01, as item 7 of approval-walk cold-read-improvement-handoff-intake-decisions-2026-10-31. Its walk-minutes are `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-improvement-handoff-intake-decisions-2026-10-31-minutes.md`.

On 2026-11-03 he widened the page from how agents work with him to the project's goals and philosophies, answering item 1.2 of approval-walk walk-me-through-skill-refactor-approval-walk-2026-11-02: "So that's that's probably a bit of philosophy that needs to go into both Claude and our project philosophy page, or whatever the closest equivalent is, which I'm starting to talk about with more and more agents, but I don't know if we have a real spot for project, you know, it's not even project overview. It's like I said, project goals and philosophies, which I think would be useful." The walk-minutes are `nedlern@ned-box:/home/nedlern/agents/cold-read-improvement/docs/walk/walk-me-through-skill-refactor-approval-walk-2026-11-02-minutes.md`, line 36, in cold-read-improvement's agent-home while that approval-walk is open, and in `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/` once it closes; lines 26 and 43 carry the two other principles he gave that day.

The section "Standing decisions" in `docs/nedschorus-wiki/nedschorus-ai-native-software-development-objective.md` lists 26 decisions, most of them about what the system is built from. No page states how agents work with the user, or how they build and finish work. So an agent meets each of these principles only in a single user-ruling that arrived too late, or not at all.

## The principles

The page pending approval, `docs/nedschorus-wiki/queue/nedschorus-goals-and-philosophy-founding-statement-and-agent-working-principles.md`, which reached the wiki queue on main through PR [Wiki queue: the project's goals-and-philosophies page for GHI 2411, pending the user's approval](https://github.com/nedschorus/nedschorus/pull/2513), holds the fourteen principles below and two more drawn from the user's founding statement of 2026-11-03, sixteen in all. The page numbers them differently: the list's principles 1 to 11 are the page's 6 to 16; the list's 13, 12 and 14 are the page's 1, 2 and 3; the page's 4 and 5 are the two from the founding statement. Each principle cites the user-rulings it comes from, which the page's section Sources quotes, gathered from the walk-minutes and his typed messages.

How agents work with the user:

1. Do trusted work without telling him, and ask him only what needs him.
2. Count more work as a win when the result works better.
3. State the case against as it is, even when it is weak; he accepts that about 5% of the decisions he makes on such recommendations will turn out wrong.
4. A case against that says only "this takes work" is not a real case.
5. Search for his earlier user-ruling before asking him.
6. Bring him one thing at a time, in an approval-walk.
7. Give him the essence, and keep the details for agents.
8. Bring in the advisor, the stronger model Claude Code's advisor tool asks, for a hard question, and an agent-arbitrator for a disagreement.
9. Back each promise to him with a hook, a program or a skill.
10. Say how you know a fix works.
11. Do not keep a file only because keeping it is easy.

How agents build and finish work, the three principles he gave on 2026-11-03:

12. Aim for steady improvement, not perfection, in three stages. His words, on item 1.2: "what we're talking about is splitting up things into essentially must fix to get to the next step, fix when can fix next, like fix in the next PR kind of thing, and then fix during maintenance." He ties the stages to nice-but-dirty: "This is a concept we're calling nice but dirty." On item 1.1, line 26: "The goal should be steady improvement, not perfection."
13. Agents are strong at code and weak at prose, so programs hold as much as they can. His words, line 43: "agents are extremely good at debugging and testing state machines and schemas and databases and code, and really have almost no clue of what to do with prose. So the more we can put into a machine, and the fewer, and then specifically isolate the parts that need judgment and therefore LLMs and agents, the better." This principle also carries the earlier principle that agents judge prose poorly.
14. Check a prose claim once; retest code on every change. His words, line 36: "things that have been checked and proven in one round, claim-wise, not code-wise, maybe, probably should not be rechecked, because as you say, there's some lack of reproducibility for prose checks."

## What the page is, and how it avoids drifting

- It is a wiki page named `nedschorus-goals-and-philosophy-founding-statement-and-agent-working-principles.md`, a name a fresh subagent read correctly from the name alone. Each principle is one short paragraph that cites the user-rulings it comes from, quoted in the page's section Sources.
- A principle is a rule for how agents work with the user, or build and finish work, across tasks. A user-ruling on one task's content is not a principle.
- The page's goal section links to the section "What the project is" of the objective page, the user's own statement of the goal, in place of restating it.
- The objective page links to the new page from the section "Standing decisions", and the new page links back to that section.
- No principle is stated on both pages. Where a principle overlaps a Standing decision, the Standing decision stays where it is, and the new page links to it in place of restating it: principle 13 names Standing decision 22, "Prose always precedes code", so that the design stays prose and only the mechanism around it moves into programs; principle 14 names Standing decision 5, so that a changed text still loses its old review, and Standing decision 25, which already keeps a finding on text the user has decided from being reported again.
- Where `CLAUDE.md` already states a rule, the page names it in place of restating it: principle 13's rule for building is `CLAUDE.md`'s bullet that begins "Build code-prompt-code", and principle 12's later stages are the non-blocking finding sent after a merge and the -nbd suffix.

The case against is that a second page of principles can drift away from the Standing decisions. The alternative is to add the principles to the Standing decisions. The user chose a separate page: the Standing decisions say what the system is built from, and this page says how agents work with him and how they build and finish work.

The user also said, on line 36, that the principles of 2026-11-03 belong in `CLAUDE.md`, and on line 43 that every agent-seat should be told of principle 13. These lines are proposed for `CLAUDE.md`, and the other agent-seats are told after he approves them:

- A new bullet, after the bullet that begins "When you review or rewrite anything": "Aim for steady improvement, not perfection. Sort each fix into one of three stages: must fix to reach the next step, done now; fix next, in the next pull request; fix during maintenance. A claim in prose that a review has passed is not reviewed again while its text is unchanged; code is retested on every change."
- A sentence added to the bullet that begins "Build code-prompt-code", after "A model is given only work that needs judgment.": "Agents are strong at code, state machines and schemas and weak at prose, so put as much of the work as possible in programs."

## Related work, not duplicates

- GHI [A wiki page on when a step given to an agent should become code and when it should stay with the model, with before-and-after examples of code-prompt-code from this project](https://github.com/nedschorus/nedschorus/issues/2127) plans the page that tells an agent, step by step, which steps go to code. This page states principle 13 and links to that page; it does not teach the decision.
- GHI [Pull requests, their reviews and approval-walks held as one state machine over one schema and one store, so code tracks their state and agents are handed only the steps that need judgment](https://github.com/nedschorus/nedschorus/issues/2505) applies principle 13 to pull requests, their reviews and approval-walks, and quotes the same words of the user. Its GHI-MD links here for the principle.
- GHI [code-prompt-code (CPC) design philosophy wiki page: systems as state machines whose nodes are code or prompts](https://github.com/nedschorus/nedschorus/issues/237), closed as not planned on 2026-09-21, asked for a page on the code-prompt-code design idea, which the objective page and the glossary carry.
- GHI [Move mechanical agent chores into programs and hooks](https://github.com/nedschorus/nedschorus/issues/1036) lists chores to move into programs, an application of principle 13.
- GHI [Save each lesson where agents meet it at the moment it applies, and decide whether a store that recalls lessons by subject is worth building](https://github.com/nedschorus/nedschorus/issues/1349) is about where single lessons live, not about one collected page.

## Next action

1. Give the wiki page `docs/nedschorus-wiki/queue/nedschorus-goals-and-philosophy-founding-statement-and-agent-working-principles.md` its cold-read-full-run with the /cold-read skill; it has had its cold-read-fast-read only.
2. Put the page to the user in an approval-walk, one principle per item, with the proposed `CLAUDE.md` lines as items of their own. A principle he disapproves is dropped. A principle he revises is rewritten and goes back to him as a new item. The proposed `CLAUDE.md` lines are handled the same way, and do not hold up the page.
3. In one pull request, move the approved page out of the queue to `docs/nedschorus-wiki/` with `git mv`, change its relative links from `../` to the same directory, and add the objective page's link from the section "Standing decisions".
4. After he approves the `CLAUDE.md` lines, add them in their own pull request, and tell each other agent-seat of the principles with SendMessage, naming the page.
