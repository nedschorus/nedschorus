---
issue: "[Hierarchical, cross-linked wiki, and a wiki-agent to build it and keep it current](https://github.com/nedsnodes/nedsnodes/issues/2709)"
---

# Hierarchical, cross-linked wiki, and a wiki-agent to build it and keep it current

The project wiki, `docs/nedsnodes-wiki/`, is one flat folder of pages with few links between them. The user wants it hierarchical and cross-linked, like any other wiki, and expects an agent-seat he calls the wiki-agent to do that work and keep the wiki reasonably up to date. This GHI records the problem, his direction, his rulings, and the open questions he has not yet ruled on. It does not design the wiki-agent: GHI 3950, listed under Related issues, does. GHI 3950's GHI-MD is in [PR 3951](https://github.com/nedsnodes/nedsnodes/pull/3951) until that pull request merges.

## The user's direction

The user, 2026-10-16T16:07:44Z, in agent-instructions-editor's agent-session `fd3dde6d-34c5-4198-9aa4-1209e4d8b1a6` on ned-box: "the wiki shouldn't be flat. It should be hierarchical, and with appropriate cross links, like any other wiki. Pretty sure we'll need a wiki-agent to do all that and keep it reasonably up to date. Maybe a GHI for the wiki-agent and other wiki improvements."

The name wiki-agent follows his ruling, 2026-10-24T01:37:28Z in the same agent-session, that agents be named with the suffix "-agent": "Agents should be labeled – agent".

On 2026-11-06, as item 11 of agent-instructions-editor's approval-walk agent-instructions-editor-backlog-decisions-2026-11-05, the user added: "I think links to code will make the wiki more useful" and "Use links when needed. Must link sounds too strong, so it might be done more than what is ideal". A wiki page links to the code, designs and GHIs it describes where a reader needs the link, not at every mention.

## The user's rulings of 2026-11-20

The user ruled on items 2, 3 and 4 of agent-seat overall-cleanup's approval-walk overall-cleanup-wiki-structure-and-wiki-agent-questions-2026-11-20. Its walk-document is `nedlern@ned-box:/home/nedlern/nedsnodes-logs/walk/overall-cleanup-wiki-structure-and-wiki-agent-questions-2026-11-20.md` and its walk-minutes are `nedlern@ned-box:/home/nedlern/nedsnodes-logs/walk/overall-cleanup-wiki-structure-and-wiki-agent-questions-2026-11-20-minutes.md`.

The wiki's new structure, item 2, "Put the pages in folders by subject, with shorter names and a home page". Line 18 of the walk-minutes records his answer to item 2.2, at 2026-11-20 06:05Z, as approved, tagged `#approved_obvious`, in his words: "ao - the reason against is that is it work. Extra one time work should be included in the no reason against group." He approved item 2.2's recommendation: "make item 2.1's five folders, the shorter names and the home page in one pull request, once PR 3885 merges". [PR 3885, Rename pull request 3 of 3](https://github.com/nedsnodes/nedsnodes/pull/3885), which moved the wiki to its `nedsnodes-` names, merged on 2026-11-20. So one pull request does three things: it moves the pages into five folders inside `docs/nedsnodes-wiki/`, which are `project/`, `systems/`, `how-agents-work/`, `writing-and-naming/` and `machines-and-accounts/`, as item 2.1 lists them with the pages each holds; it drops the project prefix from the page names, as in `writing-and-naming/style-guide.md`; and it adds a home page at the top of the wiki that links every folder and page. The same pull request rewrites, by script, every file that names a wiki path. Item 6, the approval-walk's summary, which the user answered "A" at 23:46Z (walk-minutes line 43), says this pull request starts after the wiki fixes of [PR 3974](https://github.com/nedsnodes/nedsnodes/pull/3974) merge, since both change the same pages. This answers open question 2: the wiki is organized by subject.

The order, item 3, "Do this now, and leave the one documentation tree for later". The approval-walk settled item 3 without asking the user, by his earlier ruling "If the agents recommend now versus later, I'm always for now." (walk-minutes line 23). The wiki is restructured now, and GHI 1066 waits until he takes it up. This answers open question 1.

The wiki-agent, item 4, "The wiki-agent: an interactive agent-seat that owns the wiki". Line 29 of the walk-minutes records his answer, at 2026-11-20 18:46Z, as approved, in his words: "a". He approved three parts: the wiki-agent runs the daily wiki check that GHI [Regular maintenance: the list of maintenance jobs, how often each runs, and how each reaches the user](https://github.com/nedsnodes/nedsnodes/issues/1058) plans and also acts on requests from him or another agent-seat; it changes pages only through its own pull requests, which merge-lane-2 reviews like any other; and it fixes without asking a sentence that contradicts reality, while deleting, merging or reorganizing pages comes to him. Until the wiki-agent exists, overall-cleanup fixes pages under that rule. GHI [Wiki-agent: an interactive agent-seat that keeps the project wiki, `docs/nedsnodes-wiki/`, current](https://github.com/nedsnodes/nedsnodes/issues/3950) is the wiki-agent's design, written from these three parts.

## Why

A reader of a flat wiki finds a page only by knowing its file name or by searching, and a page that links to no related page leaves the reader to guess what else bears on the subject. Pages also drift out of date when no one owns keeping them current; the user expects an agent-seat to own that.

## What is there today

Measured on `origin/main` on 2026-10-27:

- `docs/nedsnodes-wiki/` holds 19 Markdown pages and one subdirectory, `queue/`, with no other subdirectories (`git ls-tree --name-only origin/main docs/nedsnodes-wiki/`).
- Only 2 of the 19 pages contain a Markdown link to another wiki page, 3 such links in all: `nedsnodes-enforcement-ladder.md` links once and `nedsnodes-fleet-git-worktree-working-model.md` twice (`git grep -noE '\]\([^)]*nedschorus-[a-z0-9-]+\.md[^)]*\)' origin/main -- 'docs/nedsnodes-wiki/*.md'`, less one hit that points outside the wiki, to `docs/cross-project/`). Other pages name wiki pages as backticked paths, which do not open as links.
- The systems have their own directories under `nn-systems/`: `cold-read/`, `general-tools/`, `handoff/`, `main-gatekeeper/`, `skills/explain/` and `skills/walk-me-through/` (`git ls-tree -d --name-only origin/main nn-systems/ nn-systems/skills/`). One system has wiki pages named after it, the handoff system's `nedsnodes-handoff-architecture-overview.md` and a page of proposed changes to it; no other system has one, and the wiki's folders do not follow the layout of `nn-systems/`.
- No agent-seat owns the wiki.

## Related issues

- GHI [Wiki-agent: an interactive agent-seat that keeps the project wiki, `docs/nedsnodes-wiki/`, current](https://github.com/nedsnodes/nedsnodes/issues/3950) is the wiki-agent's design, written from the three parts the user approved on 2026-11-20 in item 4 of agent-seat overall-cleanup's approval-walk overall-cleanup-wiki-structure-and-wiki-agent-questions-2026-11-20. Its three parts answer part of open questions 4 and 5 below. It does not design the wiki's new structure, which the section "The user's rulings of 2026-11-20" records.
- GHI [One documentation tree in place of the wiki and the rest of docs, with Obsidian opened on it](https://github.com/nedschorus/nedschorus/issues/1066), open and waiting for the user's decision, proposes merging the wiki and the rest of `docs/` into one tree. It decides where the tree lives, not how pages inside it are arranged or linked, and it has no agent to maintain them.
- GHI [wiki-write skill, and the detect-set-aside-ask hook that enforces it — checking the file, not the tool call](https://github.com/nedschorus/nedschorus/issues/343) is the procedure for writing a wiki page, which a wiki-agent would follow.
- GHI [overview-write skill: how an overview of a system is written and checked before it lands](https://github.com/nedschorus/nedschorus/issues/168) is how a page describing one system is written.
- GHI [refresh-design: when a system's code lands, bring its design, build-slice plan and overview into line — removing, never revising](https://github.com/nedschorus/nedschorus/issues/670) keeps a system's design documents in line with its code, the nearest existing case of keeping documents current.
- GHI [Reference-integrity checker: links resolve and cited revision-paths exist — pure-code review check (and the home for what-else-can-code-check)](https://github.com/nedschorus/nedschorus/issues/42) checks that links resolve, which cross-links would need.
- GHI [Rationalize the repository layout: group components by owning system under nn-systems/, and a hook dispatcher](https://github.com/nedschorus/nedschorus/issues/224) groups the code by system under `nn-systems/`, one possible model for the wiki's hierarchy.
- GHI [Dynamic agent-team model: sparring pairs, on-tap domain experts, spy-triaged oversight (design capture; research pending)](https://github.com/nedschorus/nedschorus/issues/26) has the idea of one agent accountable for keeping each system's overview current.

## Open questions for the user

1. Whether this work is done together with GHI 1066's one documentation tree, before it, or after it. Doing them separately moves the wiki's pages twice, and each move changes every path that names them. Answered by item 3: before it, now.
2. What the hierarchy is organized by: by system, mirroring `nn-systems/`; by subject, such as the agent-seat model, the review process and naming; or some other way. Answered by item 2: by subject, in five folders.
3. What counts as an appropriate cross-link: which kinds of page must link to which.
4. What the wiki-agent does beyond the first restructuring: what makes it act, such as a merged pull request that changes a system or a schedule, and how it learns that a page is out of date. Partly answered by item 4: GHI 1058's daily wiki check and requests make it act. What the three parts leave open, such as how it learns of a change that has no commit on main, is now open in GHI 3950, not here.
5. Whether the wiki-agent changes wiki pages through its own pull requests, which merge-lane-2 reviews like any other, and whether its changes need the user's approval only where `docs/nedsnodes-wiki/nedsnodes-which-changes-need-the-users-approval.md` says any agent's changes do. Partly answered by item 4: through its own pull requests, and a sentence that contradicts reality is fixed without asking, while deleting, merging or reorganizing pages needs his approval. How that rule fits the instruction-file guard and `CLAUDE.md`'s obvious-error-fix rule is now open in GHI 3950, not here.
6. Which other wiki improvements, beyond hierarchy and cross-links, belong to this GHI.

## Next action

Open questions 3 and 6 remain here; the wiki-agent's remaining questions are GHI 3950's. Once PR 3974 merges, make the restructure that item 2 approved, in one pull request. Who makes it is open in GHI 3950. overall-cleanup, the agent-seat that cleans up the wiki, puts open questions 3 and 6 to the user in an approval-walk, and records his rulings here; if GHI 3950 has not settled who makes the restructure by then, the same approval-walk asks him. Close this GHI as completed when the restructure has merged, questions 3 and 6 are ruled on and carried out, and the wiki-agent has been started under GHI 3950.
