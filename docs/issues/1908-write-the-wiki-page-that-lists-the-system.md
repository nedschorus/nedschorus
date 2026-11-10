---
issue: "[Write the wiki page that lists the system's requirements](https://github.com/nedschorus/nedschorus/issues/1908)"
---

# Write the wiki page that lists the system's requirements

## Why

The project cannot work without some parts that are not its own code: the two machines, the network between them, and outside services such as Anthropic's service for Claude Code, GitHub, Codex and Gemini. No page lists them. On 2026-10-23 Gemini's quota ran out and cold-read-fast-reads stopped until the user switched to per-token billing; an agent deciding what to do when such a part is down has no list to check, and neither has someone setting up the project from scratch.

The user set the page's scope on 2026-10-24, in the approval-walk whose minutes are at `nedlern@ned-box:/home/nedlern/agents/fleet-restart-at-login/docs/walk/fleet-restart-at-login-every-open-question-combined-approval-walk-2026-10-22-minutes.md`, items 13.1 to 13.3:

- The page lists the system's requirements, the parts the system stands on. It also helps someone set up the project from scratch, who may choose other parts than the user's: the user's choice binds no one else. The page will grow as more setup material is added.
- What to do when each part fails goes on a separate page, written after this one, under GHI [Write the wiki page that gives each system requirement's fallback and escalation paths when it fails](https://github.com/nedschorus/nedschorus/issues/1910). His words: "if this is just the system's requirements page, that's pretty different than if it's the fallback and escalation paths page ... we should do them one at a time. I guess we should do it top down, which would mean we do the system requirements page first."

## The starting text

`nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/fleet-restart-at-login/system-requirements-page-draft-2026-10-24.md` holds the page's starting text, pending approval. It has one entry per part, each giving what the project uses the part for and what another setup could use instead. Its eight parts: the network between the Mac and ned-box, ned-box, the Mac, the machines' disks, Claude Code and Anthropic's service, GitHub, Codex, and Gemini, which the cold-read programs call through its command-line program `agy`. The user has decided only that the page is written, and first; he has not decided on its text.

## Next action

Write `docs/nedschorus-wiki/nedschorus-system-requirements.md` from the starting text. The name has passed the project's name check. Check the list against what the project's programs actually call, such as the outside services named in `scripts/` and `nc-systems/`. GHI [Check every prerequisite of the fleet's programs before an agent-session starts](https://github.com/nedschorus/nedschorus/issues/1055) proposes a finer inventory of the tools, settings and credentials each machine needs, in a supporting document that GHI will write beside its GHI-MD; that inventory is not written yet. Give the page its /cold-read, put its text and the questions below to the user in an approval-walk, and open its pull request to merge-lane-2. When it merges, record the outcome in this GHI-MD and close the GHI, so that the page on fallback and escalation paths can start.

## Questions for the user

Raised by a cold-read-fast-read of this GHI-MD; the user has not decided them:

- Whether the page waits for that inventory, or lands first and is checked against the inventory once it is written.
- Whether tools such as `python3`, `gh`, `jq` and `tmux`, which that inventory is to list per machine, also belong on this page, or only the machines, the network and the outside services.
- Whether a part the check finds missing from the starting text, or listed there wrongly, is changed on the page and shown to him with its text, or put to him first.
