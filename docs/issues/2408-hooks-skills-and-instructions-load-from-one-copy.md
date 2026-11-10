---
issue: "[Hooks, skills and instructions load from one copy per machine kept at the last known good commit, so a fix reaches every agent-seat once a full test run passes it](https://github.com/nedschorus/nedschorus/issues/2408)"
---

# Hooks, skills and instructions load from one copy per machine kept at the last known good commit, so a fix reaches every agent-seat once a full test run passes it

## The problem

Each agent-seat, and each subagent in its own worktree, runs its hooks and loads its skills and its tracked instructions, such as CLAUDE.md, from its own checkout, on its own branch. The seat-brief, the untracked `CLAUDE.local.md` of each agent-seat, is the seat's own and stays where it is. `scripts/checkout-freshness-catch-up.py` rebases a branch only while it has never been pushed; it also fast-forwards a detached checkout with no work of its own and each machine's reference-checkout. Once a branch is pushed, nothing moves it forward, so its hooks, skills and instructions stay as old as the branch, and a fix merged to main does not reach that agent-seat.

Example: on 2026-11-01, reboot-test's branch was ahead of origin/main by 6 commits and behind it by 323. Its threshold hook was older than commit 2a1e7564b, "Threshold hook counts an interim subagent only while its own transcript shows work" (2026-10-30). The old hook counted 6 finished subagents as still running, kept the handoff-deferral in force, and left reboot-test idle from 2026-10-31 21:37Z until 2026-11-01 16:17Z, about 19 hours, when the user sent it a message. main's hook, run on the same transcript, finds nothing in flight and sends the /handoff instruction. The same branch's `.claude/skills/walk-me-through/SKILL.md` also lacked the rule on rating the case against, so reboot-test rated its approval-walk items differently from other agent-seats. prime-intellect's root-cause analysis, nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/handoff-deferral-stall-root-cause-2026-11-01.md, names the stale hook as the second cause of agent-seats sitting idle. The analysis also notes that many subagent worktrees run hooks different from main's.

## What is decided

- The user approved filing this GHI on 2026-11-01 at 19:51 Pacific time, in item 2 of approval-walk ned-box-helper-agent-seat-stall-fixes-2026-11-01 (walk-minutes `docs/walk/ned-box-helper-agent-seat-stall-fixes-2026-11-01-minutes.md`, shipped to nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ when the walk closes), answering "Aa".
- On each machine, hooks, skills and instructions come from one copy of the code kept at the last known good commit of [GHI 2636](file:///Volumes/nedhome/agents/ned-box-helper/docs/issues/2636-agent-seats-run-on-a-last-known-good.md). Subagent worktrees load from it too. The canary agent-seat loads from its own agent-home, which follows main.
- The user ruled on 2026-11-07 at 18:13 Pacific time, answering "A" to item 20 of approval-walk ned-box-helper-push-program-design-points-2026-11-03, that the copy is kept at the last known good commit instead of tracking main, as approved on 2026-11-01, so that a bad hook merged to main does not reach every agent-seat at once (walk-minutes [docs/walk/ned-box-helper-push-program-design-points-2026-11-03-minutes.md](file:///Volumes/nedhome/agents/ned-box-helper/docs/walk/ned-box-helper-push-program-design-points-2026-11-03-minutes.md), line 184, in ned-box-helper's checkout on ned-box until the walk closes).
- An agent-seat's own pushed branch is never moved. The user ruled this on 2026-09-15 in item 4 of approval-walk keeping-branches-current-telling-and-rebase (nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/keeping-branches-current-telling-and-rebase-minutes.md).
- The design comes back to the user for approval before anything is built.

## Precedent

The reference-checkout is already kept on main, and code already runs from it. `scripts/checkout-freshness-catch-up.py --reference-pull` fast-forwards it to main. The handoff-supervisor of a ned-box agent-seat runs from it, and at each session-handoff that launches a successor without consulting the user, it fast-forwards the reference-checkout to main and restarts itself, as the handoff overview says in `docs/nedschorus-wiki/nedschorus-handoff-architecture-overview.md`. So the reference-checkout, as the project glossary defines it, is the copy this design loads from, unless question 4 below chooses a copy per agent-seat instead; the design builds no new copy, and GHI 2636's design, not this one, moves the reference-checkout from main to the last known good commit.

## Open design questions

1. How Claude Code can load skills and tracked instructions, such as CLAUDE.md, from the reference-checkout while the agent works in its own checkout or in a topic worktree, and how a branch that changes a skill or an instruction tries it before it merges.
2. How a hook run from the reference-checkout still sees the agent-seat's own files. Today hooks use two different anchors. `.claude/settings.json` calls each hook as `python3 "$CLAUDE_PROJECT_DIR"/<path>` (40 commands on main, b1e13e901), so `$CLAUDE_PROJECT_DIR` both picks the hook's code and names the checkout. `.claude/guard-hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook.py --approve` instead looks for `.walk-approved` in the checkout that holds the current directory (`enclosing_repository_root(cwd)` in its `approve()`). The design lists every hook's anchor, and says which one each keeps and which copy a hook's imports of shared modules, such as a `-common.py` file, resolve against. A script can build the list from `.claude/settings.json` and the hook files, and an nc-test-suite can then check that each hook keeps its anchor.
3. Whether hooks alone are a smaller first step. The 19-hour idle came from a hook. Stale skills and instructions caused only inconsistent ratings, so skills and instructions could follow as a second step.
4. Whether the agent-seat's checkout should itself be the copy that hooks, skills and instructions load from, kept at the last known good commit, with all work done in topic worktrees, since a pushed seat branch otherwise ages without end. That copy would be one per agent-seat, not one per machine, so it would not be the reference-checkout and would need a name of its own. GHI [One design of record for the project's git checkouts, worktrees and branch rules](https://github.com/nedschorus/nedschorus/issues/1121) already lists the build "agent-homes detached at main, seat-branches retired" (task #168 of the agent-seat MD-skills). This design either adopts that build as its answer or says why not, and the two GHI-MDs are made to agree.

## Requirements

A branch can still test a change to a hook or a skill from its own checkout before it merges. For example, a pull request that changes `scripts/handoff-context-threshold-hook.py` runs that hook's test from its own checkout today. The design keeps that working. If a branch could not test such a change from its own checkout before it merges, a bad hook is first run only after it merges, by the canary agent-seat, and reaches every other agent-seat if no nc-test-suite catches it before the next promotion.

When the program that keeps the reference-checkout current, such as `scripts/checkout-freshness-catch-up.py --reference-pull`, cannot bring it to the last known good commit, for example over uncommitted changes or a failed fetch, it exits nonzero and says so where the agent-session sees it. Today `--reference-pull` does not do this: it exits 0 whether or not it updated the reference-checkout, and prints the reason it did not on its standard output. The design also says when the copy moves: only at a session-handoff, as the handoff-supervisor does, or between turns, as the checkout-freshness hook does.

## Related

- GHI [One design of record for the project's git checkouts, worktrees and branch rules](https://github.com/nedschorus/nedschorus/issues/1121): branch rules, and the seat checkout's shape (question 4).
- GHI [What instructions each kind of agent needs, and where each kind's instructions live](https://github.com/nedschorus/nedschorus/issues/1127): which instructions each kind of agent loads. This GHI covers only how current the loaded copy is.
- reboot-test's task #391, "skills load from a stale checkout", is closed into this GHI.

## Next action

Write the design. It answers the four questions and keeps the requirement. Then bring it to the user in an approval-walk before any build.
