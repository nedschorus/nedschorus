---
issue: "[One documentation tree in place of the wiki and the rest of docs, with Obsidian opened on it](https://github.com/nedschorus/nedschorus/issues/1066)"
---

# One documentation tree in place of the wiki and the rest of docs, with Obsidian opened on it

The repository keeps its documentation in two areas: the wiki, `docs/nedschorus-wiki/`, and the rest of `docs/`. The user does not want two documentation areas. This GHI records his proposal, which is not yet decided, to make them one tree, and to have Obsidian on the Mac open that tree in the ned-box clone. It is not urgent: it is taken on when the user decides it is needed.

## Why

Agents read single files by path, never the whole wiki, so setting the wiki apart from the rest of `docs/` does not change what an agent reads. Almost everything in `docs/` is markdown already, and the user reads and edits markdown in Obsidian. The user, 2026-10-05: "I don't really want two docs areas, wiki and non wiki. And agetns don't have to read the whole wiki, just what they need. So maybe a separate docs and wiki is stupid".

## What is there today

Measured on main on 2026-10-05 with `git ls-tree -r --name-only origin/main docs/`:

- `docs/` holds 146 files, 144 of them markdown: `docs/issues/` 107, `docs/agents/` 18, `docs/nedschorus-wiki/` 12, and the rest in `docs/cross-project/`, `docs/design-to-main/`, `docs/drafts/` and `docs/founding/`.
- 75 files on main name `docs/nedschorus-wiki` (`git grep -l nedschorus-wiki origin/main`), 32 of them in `CLAUDE.md`, `.claude/`, `scripts/` and `nc-systems/`.
- The instruction-file guard lists the wiki among the directories the user reviews: `REVIEWED_HOME_DIRECTORY_PREFIXES` in `.claude/hooks/instruction-file-guard.py`.
- The Obsidian vault is on the Mac, over `docs/nedschorus-wiki/` in the Mac's own clone, `/Users/el/Projects/nedschorus`, as GHI [Host the project's Obsidian wiki vault — waits for the user's word](https://github.com/nedschorus/nedschorus/issues/482) records. The ned-box clone has no `.obsidian` directory.
- ned-box became the project's server after the vault was set up, and the Mac mounts ned-box's home directory over SMB as `/Volumes/nedhome/`, so Obsidian on the Mac can open a directory of the ned-box clone directly.

## The proposal

One documentation tree, with Obsidian, running on the Mac, opened on all of it. Opening it in the ned-box clone through the SMB mount is the user's suggestion; which clone is open question 3 below. A change would touch every path that names `docs/nedschorus-wiki/`, the file-naming and location standards page `docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md`, the guard's list of reviewed directories, and the glossary `docs/nedschorus-wiki/nedschorus-glossary.md`, if "wiki" stops being a project word.

## Open questions for the user

1. Where the tree's root is: `docs/` itself, or a renamed directory.
2. Whether "wiki" stays a word, for example for the durable background pages, or goes.
3. Which clone Obsidian edits: the ned-box clone through `/Volumes/nedhome/`, or the Mac's own clone. The two are separate copies, so editing both lets them diverge. Either way, an edit made in Obsidian still reaches main only through a topic branch and a pull request, so the answer also says which worktree Obsidian opens and who commits what the user writes there.
4. Which directories the instruction-file guard treats as ones the user reviews, once the wiki is no longer its own directory: all of the tree would also cover the GHI-MDs and drafts, and none would drop the pages he reviews today.
5. Whether Obsidian's `.obsidian` settings directory is committed or ignored.

## Next action

Wait until the user decides to take this on. Then put the five questions to him in an approval-walk, and plan the move from his answers as one pull request that changes every path at once, landed when no open pull request changes a file under `docs/nedschorus-wiki/`.
