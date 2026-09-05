<!-- provenance: runtime=codex model=gpt-5.6-terra effort=low cell=fast-clarify tier=floor duration_s=62 tokens=23548 target=docs/walk/topic-branch-parent-problem-and-the-lane-rule-fix-item3-rewrite.md -->

# 1. What it says

## Proposed addition to the lane rule

Every independent topic branch must be created from the seat’s branch after that branch has been fast-forwarded to the current remote main branch. Work that relies on an unmerged topic belongs on a branch from that topic and must identify that dependency in its pull request.

## The seat's home and commands

This working copy is the seat’s home and its branch is `reboot-test`; the listed commands fetch the remote, select that branch, fast-forward it to `origin/main`, and create a topic branch from it.

## Why the existing rule is insufficient

The existing requirement to start a topic from current main does not specify the checked-out branch at creation time. Since `git checkout -b` uses the current checkout as its base, complying requires manually naming `origin/main` each time.

## Why fast-forward-only is safe

Fast-forward-only protects the seat branch because it should contain no work and therefore normally advances without incident; a refusal means it contains unexpected work and should halt progress. Open pull requests do not alter the seat branch because topic commits remain on their respective topic branches.

## Scope of the rule

While the gatekeeper is dormant, every change reaches main through this branch-and-pull-request process. After the gatekeeper operates, it handles ordinary changes in private workspaces without branches, while changes to its own source must continue through the pull-request lane.

## Enforcement

The proposed lane rule describes the intended process but does not mechanically enforce it. A script for the command sequence and a pull-request-creation check for commits belonging to another open pull request are deferred to a separate topic.

## Approval

Approval of this proposal authorizes the author to edit `CLAUDE.md`.

# 2. Where you stumbled

1. [question] "the seat's own branch" — What defines a seat and identifies its own branch outside this particular `reboot-test` example?

2. [question] "a new topic" — What distinguishes a topic from other changes or determines whether a change depends on an unmerged topic?

3. [question] "say so in its pull request" — What exact information must the dependent pull request contain, and where must it appear?

4. [question] "ordinary changes" — Which changes are ordinary rather than part of the surviving pull-request lane?

5. [question] "Approving here lets me" — Who is “me,” what is “here,” and whose approval is required?

# 3. What it does not cover

1. [rule-conflict] "branch it from that topic" and "a check at `gh pr create` that refuses a branch carrying another open pull request's commits" — How can a dependent branch from an unmerged topic pass the proposed check when it necessarily carries that topic’s open-pull-request commits?

2. [no-rule] "Work that depends on an unmerged topic is not a new topic: branch it from that topic" — How should work that depends on two or more unmerged topics be branched?

3. [no-rule] "if it refuses, something is on that branch that should not be, and that is worth stopping for" — What is the required next action after `git merge --ff-only origin/main` refuses?

4. [no-rule] "Create every topic branch from the seat's own branch" — What should a reader do when switching to the seat’s branch is blocked by uncommitted changes in the current checkout?
