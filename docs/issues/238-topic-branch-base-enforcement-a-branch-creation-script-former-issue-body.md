---
issue: "[Topic-branch base enforcement: a branch-creation script and a gh pr create check that refuses an undeclared carry of another PR's commits](https://github.com/nedschorus/nedschorus/issues/238)"
---

# Topic-branch base enforcement: a branch-creation script and a gh pr create check that refuses an undeclared carry of another PR's commits

## Problem

A seat can silently put one topic's commits inside another topic's pull
request, and nothing reports it.

`git checkout -b <name>` creates the branch at whatever commit the working copy
stands on, and moves the copy onto it. So the command that creates topic one
leaves the copy standing on topic one; the same command typed for topic two
bases topic two on topic one. The second pull request then holds two topics
while its description names one, and if topic one is rejected its code rides
into main inside topic two.

A seat cannot avoid this by standing on main between topics: git allows one
branch in one working copy, and main is held by the machine's main checkout at
`~/Projects/nedschorus`. That is the only reason each seat has a branch named
after it (`scripts/handoff-supervisor.py` docstring). So a seat has nowhere safe
to stand, and correctness rests on naming `origin/main` by hand every time.

**Near-miss, 2026-09-01.** The reboot-test seat created four topic branches in a
row (PRs PR [Launchers: report only the update failure the launcher can actually see](https://github.com/nedschorus/nedschorus/pull/229), PR [launch-claude-mac: update the claude the seat will actually run](https://github.com/nedschorus/nedschorus/pull/230), PR [catch-up hook: a landed merge is an attention state, and stdout is one channel](https://github.com/nedschorus/nedschorus/pull/231), PR [Remove the Zero-Context Explanation output style](https://github.com/nedschorus/nedschorus/pull/232)) and named `origin/main` explicitly on each. The
short form on any one of them would have produced the failure. Four for four is
luck, not discipline.

Searched and NOT FOUND: `gh issue list --state all --limit 100 --search "branch
base commit worktree"` returns only GHI [main-gatekeeper — the single check-in gate (design: nc-systems/main-gatekeeper/main-gatekeeper-design.md)](https://github.com/nedschorus/nedschorus/issues/3), the gatekeeper issue.

## The rule this enforces

Filed with the pull-request skill, which is the rule's home:

> Create every topic branch from the seat's own branch, after fast-forwarding
> that branch to current `origin/main`. Work that depends on an unmerged topic
> is not a new topic: branch it from that topic and say so in its pull request.

A sentence of instruction is not a fix — agents are unreliable readers
(user-ruled 2026-09-02, which is why this is filed separately from the skill).
Three mechanical pieces:

## Piece 1 — the branch-creation script

Performs the sequence, so the correct action is one command whose base commit
cannot be got wrong:

```
git fetch origin
git checkout <seat-branch>
git merge --ff-only origin/main
git checkout -b <topic-name>
```

`--ff-only` is the safety: the seat's branch carries no work of its own, so the
fast-forward normally succeeds, and a refusal means something is on that branch
that should not be — the script stops and says so rather than merging.

Open sub-question for the build: how the script identifies the seat's own
branch. The supervisor knows it; the script should not guess it from the
directory name.

## Piece 2 — the check at `gh pr create`

Detects the actual failure rather than trusting the rule was followed: refuse
when the branch about to be filed carries commits belonging to another open
pull request's branch, **unless the pull request declares that dependency**.

The declaration is what distinguishes the two cases. Stacked work is legitimate
— work that depends on an unmerged topic branches from that topic and
necessarily carries its commits — and a check without the exemption would refuse
exactly the case the rule permits. (Caught by a cold read of the walk item
before this was filed; the first form of the check had that conflict.)

## Piece 3 — the `Claude-Session` trailer, checked before the push

Ruled by the user 2026-09-17, at the merge-lane seat's backlog walk, on being
offered a one-line instruction instead: *"seems like that should be python, not
prompt"*. Commits reach main without the `Claude-Session` trailer the harness
asks every session to add; the merge lane has recorded heads arriving without it
repeatedly, and nothing but a system-prompt reminder produces it.

The check belongs beside pieces 1 and 2, and not at merge time, for one reason:
**a pull request's head is frozen the moment it is pushed** (`CLAUDE.md`), and a
missing trailer can only be repaired by rewriting the commit. A check that fires
at the merge can refuse but can never be satisfied — it would wedge the lane on
work already frozen. So it runs before the push: at branch creation, at
`gh pr create`, or both, which is where these two pieces already are.

**Built 2026-09-18.** PR [Stamp the Claude-Session trailer on commits with a git hook](https://github.com/nedschorus/nedschorus/pull/491), merged as 706356c: `scripts/git-client-side-hooks/prepare-commit-msg`, a git `prepare-commit-msg` hook that stamps the line from `CLAUDE_CODE_BRIDGE_SESSION_ID`, never blocks a commit, and leaves an empty message empty. Wired the same day on both clones, `core.hooksPath` pointing at each reference checkout, and verified by a stamped commit on each machine. Pull request descriptions stay manual.

**2026-09-18: a whole session missed it, and the user's direction.** All six pull requests of the reboot-test seat's 2026-09-17/18 session lacked it, fresh agents' commits too: its briefs dictated the attribution line over their correct reminders. Nothing needs remembering: a session with a claude.ai link carries it as `CLAUDE_CODE_BRIDGE_SESSION_ID`, so it can be stamped rather than checked. The user's direction: the active gatekeeper, GHI [main-gatekeeper — the single check-in gate](https://github.com/nedschorus/nedschorus/issues/3), stamps both the commit and the pull request it composes, beside its `Gatekeeper-origin` trailer — subject to its recorded C2 defect: `sudo` strips the caller's environment. Ruled 2026-09-18, keep this piece: "If the script is a github action, no. If it's a claude thing, yes."

## Value across gatekeeper activation

Both pieces are worth building while the gate is dormant, because today every
change reaches main through an agent-created topic branch.

They keep their value afterward, in a smaller lane. Per
`nc-systems/main-gatekeeper/main-gatekeeper-design.md`, an active gate builds each change
in its own private workspace from main, so ordinary changes need no branch and
where the caller stands is irrelevant. One pull-request lane survives
permanently: the gate refuses check-ins touching its own source
(`gatekeeper-source-refused`), and `nc-systems/main-gatekeeper/main-gatekeeper.py` must still reach
main the reviewed way. These pieces govern that lane.

## Next action

Build piece 1, the script — it is small, it is useful the day it lands, and it
is the node the rule's correctness actually depends on. Pieces 2 and 3 follow;
piece 3 can ride with either, since both run before the push.
