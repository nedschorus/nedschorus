# The nedschorus project: architecture overview

This page sits above the nc-architecture-overview of each system. It names each nc-system and links the system's overview where one exists, and it names the critical components: the parts outside the project whose failure stops work, and that only someone outside the project, usually the user, can fix.

## Systems

Each nc-system has its own directory under `nc-systems/`, or files still to move there; the glossary entry for nc-system says what counts as one. A system without an Overview link below has no nc-architecture-overview yet.

- **cold-read**, `nc-systems/cold-read/`: the programs /cold-read runs, which have reviewer models read a document as a fresh reader would and report what is unclear.
- **design-to-main**, whose files are still in `docs/design-to-main/`: the workflow that takes an approved design to code, tests and a pull request.
- **handoff-system**, `nc-systems/handoff/`: replaces an agent-session with a fresh one that continues from the session-handoff the old one wrote, and restarts agent-seats that crash. Overview: [the handoff-system's nc-architecture-overview](nedschorus-handoff-architecture-overview.md).
- **main-gatekeeper**, `nc-systems/main-gatekeeper/`: the program that will be the only way a change reaches main; until it runs, changes reach main by pull request through merge-lane-2.
- **nc-shared-database**, `nc-systems/nc-shared-database/`: the project's shared database on ned-box and the one service that reads and writes it.
- **skills**, `nc-systems/skills/`: the programs of the skills that have code of their own; each skill's `SKILL.md` stays under `.claude/skills/`.

`nc-systems/general-tools/` is not an nc-system: it holds code shared by several nc-systems or owned by none.

## Critical components

A critical component is a part the project does not own and whose failure stops work that has no other way to go on.

- **ned-box, its disk included.** Most agent-seats run there, merge-lane-2 reviews and merges every pull request there, and the log-store is kept there.
- **The user's Mac, its disk included.** The user reads and answers from it, and its own agent-seats run there.
- **The network between the Mac and ned-box.** The Mac reaches ned-box, and the log-store through the `/Volumes/nedhome` mount, only over it.
- **git.** Every change reaches main as a commit on an nc-topic-branch.
- **GitHub.** Every change merges as a pull request, and every GHI is kept there.
- **The Claude account and its usage limit.** Every agent-seat on both machines runs Claude Code under the account; when the usage limit is reached, those agent-seats stop until it resets.
- **Codex.** `scripts/pull-request-review-plan.py` gives every pull request that changes code a review tier that includes the Codex reviewer, so such a pull request does not merge without Codex.

Gemini is not a critical component: the cold-read programs fall back to another model when Gemini gives no report, and no other step of the project's work needs Gemini. What each machine must have in order to run is in [§ What the system needs in order to run](nedschorus-mac-and-ned-box-machine-setup.md#what-the-system-needs-in-order-to-run) of the machine setup page. GHI [Write the wiki page that lists the system's requirements](https://github.com/nedschorus/nedschorus/issues/1908) holds the full list of parts the project stands on, for someone setting the project up.

## When a critical component fails

A failure of a critical component is a showstopper, and the agent follows this rule. The agent tells the user what the failing command said, with its remedy if it gave one. The agent builds no workaround, fallback or second source, such as another machine or service set up to do the same job. The agent leaves each step that needs the component until the component is fixed or the user says otherwise, and meanwhile carries on with work that does not need the component, or waits when no such work is left. A retry of a passing fault, such as one dropped connection, on an operation safe to repeat and with a limit on attempts, stays allowed, as `CLAUDE.md`'s bullet on guards and workarounds says; a failure that outlasts the retry is reported.

A failure of a critical component is the component itself being unavailable: GitHub not answering, ned-box unreachable, the Claude account logged out or over its usage limit, the Mac's disk full, or git killed by a signal. A command that reaches the component and gets its answer is not a failure of the component, even when the command exits nonzero: a git merge that stops on a merge conflict, a push GitHub refuses, or a script that ssh starts on ned-box and that exits nonzero. The agent handles such an exit as part of its work, and the rule in the paragraph above does not apply.

Code does not handle a critical component's failure beyond reporting it: the code prints what failed and exits nonzero, or raises an error to a caller that does. So a test or a mutant that exists only for such a failure, such as git killed by a signal or GitHub unreachable in the middle of a command, is not needed. A limited retry the code makes for a passing fault keeps its test, and so does the code that handles an exit the agent handles as part of its work, such as a merge conflict.

What stops when each critical component fails and what happens next, including how an agent reports a failure of its own path to the user, such as the network, and how a waiting agent learns that a component is fixed, are for GHI [Write the wiki page that gives each system requirement's fallback and escalation paths when it fails](https://github.com/nedschorus/nedschorus/issues/1910).

**Checked against:** commit [17e72b316c06ddfc587780842dc8a6f426225928](https://github.com/nedschorus/nedschorus/commit/17e72b316c06ddfc587780842dc8a6f426225928)
