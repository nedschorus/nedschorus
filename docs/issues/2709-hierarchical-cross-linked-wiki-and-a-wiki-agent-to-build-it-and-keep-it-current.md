---
issue: "[Hierarchical, cross-linked wiki, and a wiki-agent to build it and keep it current](https://github.com/nedschorus/nedschorus/issues/2709)"
---

# Hierarchical, cross-linked wiki, and a wiki-agent to build it and keep it current

The project wiki, `docs/nedschorus-wiki/`, is one flat folder of pages with few links between them. The user wants it hierarchical and cross-linked, like any other wiki, and expects an agent-seat he calls the wiki-agent to do that work and keep the wiki reasonably up to date. This GHI records the problem and his direction, and the open questions he has not yet ruled on. It does not design the wiki-agent.

## The user's direction

The user, 2026-10-16T16:07:44Z, in agent-instructions-editor's agent-session `fd3dde6d-34c5-4198-9aa4-1209e4d8b1a6` on ned-box: "the wiki shouldn't be flat. It should be hierarchical, and with appropriate cross links, like any other wiki. Pretty sure we'll need a wiki-agent to do all that and keep it reasonably up to date. Maybe a GHI for the wiki-agent and other wiki improvements."

The name wiki-agent follows his ruling, 2026-10-24T01:37:28Z in the same agent-session, that agents be named with the suffix "-agent": "Agents should be labeled – agent".

On 2026-11-06, as item 11 of agent-instructions-editor's approval-walk agent-instructions-editor-backlog-decisions-2026-11-05, the user added: "I think links to code will make the wiki more useful" and "Use links when needed. Must link sounds too strong, so it might be done more than what is ideal". A wiki page links to the code, designs and GHIs it describes where a reader needs the link, not at every mention.

## Why

A reader of a flat wiki finds a page only by knowing its file name or by searching, and a page that links to no related page leaves the reader to guess what else bears on the subject. Pages also drift out of date when no one owns keeping them current; the user expects an agent-seat to own that.

## What is there today

Measured on `origin/main` on 2026-10-27:

- `docs/nedschorus-wiki/` holds 19 Markdown pages and one subdirectory, `queue/`, with no other subdirectories (`git ls-tree --name-only origin/main docs/nedschorus-wiki/`).
- Only 2 of the 19 pages contain a Markdown link to another wiki page, 3 such links in all: `nedschorus-enforcement-ladder.md` links once and `nedschorus-fleet-git-worktree-working-model.md` twice (`git grep -noE '\]\([^)]*nedschorus-[a-z0-9-]+\.md[^)]*\)' origin/main -- 'docs/nedschorus-wiki/*.md'`, less one hit that points outside the wiki, to `docs/cross-project/`). Other pages name wiki pages as backticked paths, which do not open as links.
- The systems have their own directories under `nc-systems/`: `cold-read/`, `general-tools/`, `handoff/`, `main-gatekeeper/`, `skills/explain/` and `skills/walk-me-through/` (`git ls-tree -d --name-only origin/main nc-systems/ nc-systems/skills/`). One system has wiki pages named after it, the handoff system's `nedschorus-handoff-architecture-overview.md` and a page of proposed changes to it; no other system has one, and the wiki's folders do not follow the layout of `nc-systems/`.
- No agent-seat owns the wiki.

## Related issues

- GHI [One documentation tree in place of the wiki and the rest of docs, with Obsidian opened on it](https://github.com/nedschorus/nedschorus/issues/1066), open and waiting for the user's decision, proposes merging the wiki and the rest of `docs/` into one tree. It decides where the tree lives, not how pages inside it are arranged or linked, and it has no agent to maintain them.
- GHI [wiki-write skill, and the detect-set-aside-ask hook that enforces it — checking the file, not the tool call](https://github.com/nedschorus/nedschorus/issues/343) is the procedure for writing a wiki page, which a wiki-agent would follow.
- GHI [overview-write skill: how an overview of a system is written and checked before it lands](https://github.com/nedschorus/nedschorus/issues/168) is how a page describing one system is written.
- GHI [refresh-design: when a system's code lands, bring its design, build-slice plan and overview into line — removing, never revising](https://github.com/nedschorus/nedschorus/issues/670) keeps a system's design documents in line with its code, the nearest existing case of keeping documents current.
- GHI [Reference-integrity checker: links resolve and cited revision-paths exist — pure-code review check (and the home for what-else-can-code-check)](https://github.com/nedschorus/nedschorus/issues/42) checks that links resolve, which cross-links would need.
- GHI [Rationalize the repository layout: group components by owning system under nc-systems/, and a hook dispatcher](https://github.com/nedschorus/nedschorus/issues/224) groups the code by system under `nc-systems/`, one possible model for the wiki's hierarchy.
- GHI [Dynamic agent-team model: sparring pairs, on-tap domain experts, spy-triaged oversight (design capture; research pending)](https://github.com/nedschorus/nedschorus/issues/26) has the idea of one agent accountable for keeping each system's overview current.

## Open questions for the user

1. Whether this work is done together with GHI 1066's one documentation tree, before it, or after it. Doing them separately moves the wiki's pages twice, and each move changes every path that names them.
2. What the hierarchy is organized by: by system, mirroring `nc-systems/`; by subject, such as the agent-seat model, the review process and naming; or some other way.
3. What counts as an appropriate cross-link: which kinds of page must link to which.
4. What the wiki-agent does beyond the first restructuring: what makes it act, such as a merged pull request that changes a system or a schedule, and how it learns that a page is out of date.
5. Whether the wiki-agent changes wiki pages through its own pull requests, which merge-lane-2 reviews like any other, and whether its changes need the user's approval only where `docs/nedschorus-wiki/nedschorus-which-changes-need-the-users-approval.md` says any agent's changes do.
6. Which other wiki improvements, beyond hierarchy and cross-links, belong to this GHI.

## Next action

Put the six open questions to the user in an approval-walk, with question 1 first: if he rules that this work waits for GHI 1066, record that ruling here and stop until GHI 1066 is decided. If he decides against a wiki-agent or against restructuring the wiki, record his ruling here and close this GHI as not planned. Otherwise, from his answers, write the design of the wiki-agent and of the wiki's new structure as a GHI-MD of its own, and add a link to it in this GHI-MD.
