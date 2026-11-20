---
issue: "[Write the wiki page that lists the system's requirements](https://github.com/nedschorus/nedschorus/issues/1908)"
---

# Write the wiki page that lists the system's requirements

## Why

The project cannot work without some parts that are not its own code: the two machines, the network between them, and outside services such as Anthropic's service for Claude Code, GitHub, Codex and Gemini. No page lists them. On 2026-10-23 Gemini's quota ran out and cold-read-fast-reads stopped until the user switched to per-token billing; an agent deciding what to do when such a part is down has no list to check, and neither has someone setting up the project from scratch.

Two earlier user-rulings led to this page:

- On 2026-10-12, at 02:12 UTC, in the approval-walk on the design of record for git checkouts, worktrees and branch rules, the user answered "y y" to items 13d and 13e. The walk-minutes record item 13e as: "Y: file a GHI for a wiki page on the two machines (hardware, disks and backup drives, network and reachability, accounts, where clones and agent-homes live), absorbing nedschorus-fleet-machine-paths-and-checkouts.md; kept current by the daily wiki check" (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/git-checkouts-worktrees-and-branch-rules-design-draft-2026-10-09-2-minutes.md`, line 28; his answer is line 2335 of the agent-seat MD-skills' Mac transcript, `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/mac/projects/-Users-el-agents-MD-skills/6c36247e-cfc3-405a-bd9e-9228046a39b6.jsonl`). No other GHI carries item 13e out: ghi-guide-agent, asked on 2026-11-11 with closed GHIs included, named only this one. The page item 13e names has since been renamed `docs/nedschorus-wiki/nedschorus-mac-and-ned-box-machine-setup.md`. Of the contents item 13e lists, the starting text below covers the machines, their disks and the network; it does not cover backup drives, accounts, or where clones and agent-homes live, and it does not absorb that page. Where the rest goes is a question for the user, listed at the end.
- On 2026-10-22, asked where a note on the machines' reliability belongs, the user said: "I think you could note in, if that is our only thing about our setup, hardware setup, I would note that the hard disks, computers, and networks are sufficiently reliable not to require additional checks. But of course, if they are broken or down and we detect that, we should warn, but not block." Two minutes later he corrected that: "Oh, I don't say anything about never blocking work. Who knows what those failures would do? I would just say reliable enough not to require additional checking." (lines 1268 and 1297 of the agent-seat fleet-restart-at-login's transcript, `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/ned-box/projects/-home-nedlern-agents-fleet-restart-at-login/a03d3ebc-544a-4e0e-b30d-d75c77a68e86.jsonl`; recorded at line 26 of `nedlern@ned-box:/home/nedlern/agents/fleet-restart-at-login/docs/walk/fleet-restart-at-login-agent-seat-open-questions-recommendations-and-concerns-approval-walk-2026-10-21-minutes.md`). The sentence was then meant for `nedschorus-fleet-machine-paths-and-checkouts.md`. It became item 13 of the combined approval-walk; on 2026-10-23 the user called the parts the project cannot work without showstoppers, around which agents should build no workarounds, the agent's proposal to add that one sentence was withdrawn, and item 13 was split into items 13.1 to 13.3 (line 129 of the walk-minutes named below), which the user decided on 2026-10-24.

The user set the page's scope on 2026-10-24, in the approval-walk whose minutes are at `nedlern@ned-box:/home/nedlern/agents/fleet-restart-at-login/docs/walk/fleet-restart-at-login-every-open-question-combined-approval-walk-2026-10-22-minutes.md`, items 13.1 to 13.3:

- The page lists the system's requirements, the parts the system stands on. It also helps someone set up the project from scratch, who may choose other parts than the user's: the user's choice binds no one else. The page will grow as more setup material is added.
- What to do when each part fails goes on a separate page, written after this one, under GHI [Write the wiki page that gives each system requirement's fallback and escalation paths when it fails](https://github.com/nedschorus/nedschorus/issues/1910). His words: "if this is just the system's requirements page, that's pretty different than if it's the fallback and escalation paths page ... we should do them one at a time. I guess we should do it top down, which would mean we do the system requirements page first."

## The starting text

`nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/fleet-restart-at-login/system-requirements-page-draft-2026-10-24.md` holds the page's starting text, pending approval. It has one entry per part, each giving what the project uses the part for and what another setup could use instead. Its eight parts: the network between the Mac and ned-box, ned-box, the Mac, the machines' disks, Claude Code and Anthropic's service, GitHub, Codex, and Gemini, which the cold-read programs call through its command-line program `agy`. The user has decided that the page is written, and first. Of its text, he has decided only the words of the 2026-10-22 sentence on the machines' reliability, quoted under Why, and those for another page; the starting text does not carry that sentence, and whether this page does is a question for him, listed at the end.

## Next action

Write `docs/nedschorus-wiki/nedschorus-system-requirements.md` from the starting text. The name has passed the project's name check. Check the list against what the project's programs actually call, such as the outside services named in `scripts/` and `nc-systems/`. GHI [Check every prerequisite of the fleet's programs before an agent-session starts](https://github.com/nedschorus/nedschorus/issues/1055) proposes a finer inventory of the tools, settings and credentials each machine needs, in a supporting document that GHI will write beside its GHI-MD; that inventory is not written yet. Give the page its /cold-read, put its text and the questions below to the user in an approval-walk, and open its pull request to merge-lane-2. When it merges, record the outcome in this GHI-MD and close the GHI, so that the page on fallback and escalation paths can start.

## Questions for the user

Raised by a cold-read-fast-read of this GHI-MD; the user has not decided them:

- Whether the page waits for that inventory, or lands first and is checked against the inventory once it is written.
- Whether tools such as `python3`, `gh`, `jq` and `tmux`, which that inventory is to list per machine, also belong on this page, or only the machines, the network and the outside services.
- Whether a part the check finds missing from the starting text, or listed there wrongly, is changed on the page and shown to him with its text, or put to him first.
- Whether the page carries the 2026-10-22 sentence that the disks, computers and networks are reliable enough not to require additional checking.
- Where the contents item 13e lists that the starting text leaves out, backup drives, accounts, and where clones and agent-homes live, go: on this page, on `docs/nedschorus-wiki/nedschorus-mac-and-ned-box-machine-setup.md`, or in a GHI of their own.
