---
issue: "[Write the wiki page that gives each system requirement's fallback and escalation paths when it fails](https://github.com/nedschorus/nedschorus/issues/1910)"
---

# Write the wiki page that gives each system requirement's fallback and escalation paths when it fails

## Why

Each part the project stands on but does not own, such as ned-box, the network, Anthropic's service for Claude Code, GitHub, Codex or Gemini, can fail. No page says, for each part, what stops when it fails and what happens next. Without one, agents build workarounds around failures that only the user can fix, and the user said on 2026-10-23 that such workarounds waste his time: when a part he calls a showstopper fails, the failure must be passed up to him, because "sometimes like if it's a network issue ... I'm the only one to fix it". On 2026-10-23 Gemini's quota ran out, and agents passed Gemini's error messages to him; he fixed the account and the blocked work carried on.

## Terms

The user set these on 2026-10-24, and asked that the words be standard and explicit:

- A fallback is inside our system: a way the system keeps working without the failed part. A part with a fallback is a soft dependency.
- An escalation is outside it: the failure goes up an escalation path to someone outside the system who can fix it, usually a human, though not always. A part with no fallback is a hard dependency, a single point of failure.

A fallback and an escalation are different things, and the page keeps them apart.

## Order and source

This page is written after the page listing the parts, under GHI [Write the wiki page that lists the system's requirements](https://github.com/nedschorus/nedschorus/issues/1908). Start this one only when that GHI is closed, and take the list of parts from the merged page.

The user decided this on 2026-10-24, in the approval-walk whose minutes are at `nedlern@ned-box:/home/nedlern/agents/fleet-restart-at-login/docs/walk/fleet-restart-at-login-every-open-question-combined-approval-walk-2026-10-22-minutes.md`, items 13.1 to 13.3. His words: "if this is just the system's requirements page, that's pretty different than if it's the fallback and escalation paths page ... we should do them one at a time. I guess we should do it top down, which would mean we do the system requirements page first. Now this project's going to take a little longer than I thought, so my sense is we should simply defer both of these, not in the walk, but move them both into GHIs. And they should refer to each other".

## The starting text

`nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/fleet-restart-at-login/system-requirement-failures-page-draft-2026-10-24.md` holds the page's starting text, pending approval. It covers the eight parts the starting text of the requirements page lists: the network between the Mac and ned-box, ned-box, the Mac, the machines' disks, Claude Code and Anthropic's service, GitHub, Codex, and Gemini. For each it says what stops when the part fails and whether the project has a fallback; today it records none, so every part is a hard dependency. The user has not decided on its text.

## Two CLAUDE.md changes that go with the page

Both point at this page, so they travel with it. The user has not decided on either; each needs his approval before it is made. Their full text as last put to him, with the case against each, is at `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/fleet-restart-at-login/items-13.1-13.3-at-removal-2026-10-24.md`, items 13.2 and 13.3. Both proposals name the page by an earlier, longer name, `nedschorus-system-requirements-setup-and-fallback-or-escalation-when-one-fails.md`; the quotes below keep it, because they are the proposals as he saw them. When either is put to him again, and in what lands in `CLAUDE.md`, the name is `nedschorus-system-requirement-failures-fallback-and-escalation-paths.md`.

### Widen the ned-box rule to every hard dependency

`CLAUDE.md`'s bullet on the two machines now says:

"When ned-box cannot be reached, or a program reports that ned-box's `claude` is logged out, tell the user what the failing command or program said, with its remedy if it gave one. Do not find another way to do a step that needs ned-box: leave that step until ned-box is fixed or the user says otherwise, and meanwhile carry on with work that does not need ned-box."

Proposed in place of those two sentences:

"When a hard dependency listed on `nedschorus-system-requirements-setup-and-fallback-or-escalation-when-one-fails.md` fails, such as ned-box not answering or a program reporting that a machine's `claude` is logged out, tell the user what the failing command or program said, with its remedy if it gave one. Do not find another way to do a step that needs that part: leave that step until the part is fixed or the user says otherwise, and meanwhile carry on with work that does not need it."

How the message reaches the user is the subject of GHI [Tell the user when ned-box's claude is logged out or ned-box's subscription has run out](https://github.com/nedschorus/nedschorus/issues/337).

### A hard dependency earns no workaround

`CLAUDE.md`'s bullet on guards and workarounds now says:

"Only a cause outside our control, such as an outside service, the operating system, the program the agent runs inside or the user's environment, earns a workaround; a retry is only for a passing fault, on an operation safe to repeat, with a limit on attempts."

Proposed:

"Only a cause outside our control, such as an outside service, the operating system, the program the agent runs inside or the user's environment, earns a workaround, and a hard dependency listed on `nedschorus-system-requirements-setup-and-fallback-or-escalation-when-one-fails.md` never does; a retry is only for a passing fault, on an operation safe to repeat, with a limit on attempts."

A retry stays allowed for a passing fault such as one dropped connection. Restarting an agent-session that died is recovery of the project's own program, not a workaround, and stays. This change reverses part of a rule the user approved.

## Questions the page must answer

Raised by cold-read-fast-reads of the walk's earlier text and of this GHI-MD, and not yet put to the user:

- How an agent that left a step waiting learns that the failed part is fixed, so that it can do the step.
- What an agent does when the failed part is its own path to the user, such as the network between the Mac and ned-box.
- What the page does with a part the merged requirements page lists that the starting text lacks, or the other way round.
- Whether the page lands when the user rejects one or both CLAUDE.md changes.

## Next action

After GHI [Write the wiki page that lists the system's requirements](https://github.com/nedschorus/nedschorus/issues/1908) closes, write `docs/nedschorus-wiki/nedschorus-system-requirement-failures-fallback-and-escalation-paths.md` from the starting text and the merged requirements page. The name has passed the project's name check. Give the page its /cold-read, and put its text and the two CLAUDE.md changes above to the user for his approval. Then open one pull request to merge-lane-2 with the page and whichever of the two changes he approved. When it merges, record the outcome in this GHI-MD and close the GHI.
