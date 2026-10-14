---
issue: "[One design of record for the project's git checkouts, worktrees and branch rules](https://github.com/nedschorus/nedschorus/issues/1121)"
---

# One design of record for the project's git checkouts, worktrees and branch rules

## Problem

How this project keeps its git checkouts current with main, and what an agent may and may not do to a branch on its way to main, is decided in many places and described whole in none:

- `CLAUDE.md` holds the rules on topic branches, atomic pull requests, frozen heads, commits on top and hand-merges.
- `scripts/checkout-freshness-catch-up.py`, a Stop hook, rebases a never-pushed branch, moves a detached checkout with no work of its own forward, fast-forwards the machine's reference checkout (the clone's main worktree, kept on the main branch, such as `/Users/el/Projects/nedschorus` on the Mac), and tells the agent what changed; its rules live in its docstring.
- `sync_working_branch_with_main` in `nc-systems/handoff/handoff-supervisor.py` fast-forwards a seat's checkout at launch; no document describes it.
- The git hooks, `scripts/branch-conflict-check.py`, `scripts/force-push-with-open-pull-request-guard-hook.py`, `scripts/obsolete-file-edit-warning-hook.py`, `.claude/hooks/session-location-write-guard.py`, `scripts/clean-worktrees.py` and `scripts/merge-gate.sh` each enforce one piece.
- Closed GHIs record past rulings: [checkout-freshness catch-up merges main into a branch whose head is frozen under review](https://github.com/nedschorus/nedschorus/issues/324) and [The checkout-freshness hook treats a new branch cut at a pull request's pushed head as never pushed, and rebases it](https://github.com/nedschorus/nedschorus/issues/913).

Because nothing states the whole, the pieces disagree, and agents act on the disagreement. On 2026-10-08 the Mac's MD-skills seat checkout sat 86 commits behind main on a detached HEAD, a shape `docs/agents/seat-first-prompt.md` says should never occur, and the agent ran a skill whose text predated a rule the user had approved. A reading of every place on 2026-10-09 found sixteen further disagreements, which the design lists in full; among them:

- the documents place every agent-home on its own seat-branch, while live seat checkouts sit detached and nothing creates or describes that shape;
- `CLAUDE.md` says merge-lane-2 tests a pull request's head commit merged onto main, while merge-lane-2 tests the head as it stands;
- the first prompt the supervisor builds for a seat (`BRANCH_STATE_INSTRUCTION` in `nc-systems/handoff/handoff-supervisor.py`) tells an agent to rebase a never-pushed branch, which the Stop hook already does;
- "frozen" means "has an open pull request" to `scripts/force-push-with-open-pull-request-guard-hook.py` and "pushed" to the freshness hook;
- worktrees under agent-homes and in scratchpads are never removed, while `docs/nedschorus-wiki/nedschorus-fleet-git-worktree-working-model.md` (R21) and `docs/nedschorus-wiki/nedschorus-fleet-machine-paths-and-checkouts.md` describe every session worktree as removed once merged;
- a subagent's worktree gets no freshness check, because no hook runs when a subagent stops;
- several documents describe behaviour the code no longer has.

## What this GHI produces

One design of record, in `docs/issues/` beside this GHI-MD and named with this issue's number followed by `-git-checkouts-worktrees-and-branch-rules-design.md`, that states:

- each kind of checkout the project has, on the Mac and on ned-box, and which program keeps each current;
- each state a checkout's HEAD can be in, and what each program does and tells the agent in that state;
- who may move, rebase, merge or push what, and when;
- how a change goes from a topic branch to main;
- each disagreement found, either corrected to what the code does, or put to the user as a question with a recommendation.

The design gets a fast read and a full cold read, then an approval-walk with the user. The changes the user approves are built as their own pull requests, each linked from this GHI.

## Related GHIs

- [pull-request skill: how a change reaches main — durable-file disposition, the description, and topic-branch creation](https://github.com/nedschorus/nedschorus/issues/236) defines how an agent creates a topic branch from its seat-branch. The design adopts that procedure, or puts any conflict with it to the user; the skill itself stays with that GHI.
- [Topic-branch base enforcement: a branch-creation script and a gh pr create check that refuses an undeclared carry of another PR's commits](https://github.com/nedschorus/nedschorus/issues/238) keeps its unbuilt script and check; the design cites them.
- [Move mechanical agent chores into programs and hooks](https://github.com/nedschorus/nedschorus/issues/1036): its rows 1 (the pre-push test run), 2 (the supervisor's rebase instruction), 9 (the first prompt's branch checks) and 10 (announcing a push) concern these rules; this design takes them over, and that GHI-MD is edited to point here.
- [Every refusal and warning a program hands an agent says why and what to do instead](https://github.com/nedschorus/nedschorus/issues/956): any message the design changes follows its rules for messages.

## Next action

The design's first draft, written from the 2026-10-09 reading of every place these rules live, has had its fast read. Next: add it beside this GHI-MD, give it a full cold read, and walk its questions with the user.
