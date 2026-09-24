---
issue: "[Host the project's Obsidian wiki vault — waits for the user's word](https://github.com/nedschorus/nedschorus/issues/482)"
---

# Host the project's Obsidian wiki vault — waits for the user's word

The project's Obsidian vault is stood up on the Mac, over `docs/nedschorus-wiki/` in the reference checkout at `/Users/el/Projects/nedschorus` — piece 1 of GHI [Stand up the Obsidian vault over docs/wiki, and rule which documents are standing knowledge that belongs in it](https://github.com/nedschorus/nedschorus/issues/338), now closed. It is not hosted anywhere. This issue carries the one piece of that work that was deferred.

## Why it is wanted

The user, 2026-09-11: "I guess on the mac for now, though I think I've paid for the plan that lets them host it, which we'll need to do at some point." The plan he means is Obsidian Publish.

## Why it waits for the user

Publishing is outward-facing, and the vault holds the project's own doctrine — the seat model, the glossary, the git and worktree working model, the machine-paths map. Whether any of it is published, to whom, and when is his call, and nothing here should be built or configured before he makes it.

## Next action

The user decides whether and when to host the vault, and what it may expose. Until then nothing is built. Queued as `draft` for the drain.

## Search receipt

`scripts/ghi-info-ask.py` asked 2026-09-18 with `--include-closed` whether any issue covers publishing or hosting the vault: none does. The only other publishing issue, GHI [Open-source publishing and community strategy](https://github.com/nedschorus/nedschorus/issues/4), is about the project's public site and syndication and predates the vault.
