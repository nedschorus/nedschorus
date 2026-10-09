# Design of record: the project's git checkouts, worktrees and branch rules

This design states how the project keeps each git checkout current with main, what an agent may do to a branch on its way to main, and how a change reaches main. It describes the code on main at commit 7e2c0228, 2026-10-09, cited by file and line. Where two places disagree, it says so: a description the code shows to be stale is listed under "Corrections", and a disagreement only the user can settle is a "Question for the user" with a recommendation. Nothing here is built yet beyond what main already does.

## What a reader needs first

**Checkout, worktree, HEAD.** A git checkout is a directory holding a copy of the repository's files at one commit. One clone can have several checkouts, called worktrees, each at its own commit; the first is the clone's main worktree, and the others are linked worktrees made with `git worktree add`. HEAD is what a checkout stands on: a branch, such as `main` or `ghi-956-part-four-rule-enforcing-test-suite-messages`, or, when HEAD is detached, a bare commit.

**Behind and ahead.** A checkout is behind main by the number of commits on `origin/main` that its HEAD does not have, and ahead by the number of its own commits that `origin/main` does not have. "Own commits" below always means commits that are not on `origin/main`.

**Moving a checkout forward.** Three git operations bring a checkout up to date, and they differ in what they risk:

- a fast-forward (`git merge --ff-only origin/main`) moves HEAD to main's newest commit when HEAD has no own commits; it rewrites nothing, and git refuses it rather than overwrite a file;
- a rebase (`git rebase origin/main`) replays a branch's own commits on top of main, giving them new commit hashes;
- a merge (`git merge origin/main`) adds a merge commit joining the branch and main.

**Frozen head.** CLAUDE.md: "A head commit becomes a frozen-head the moment it is pushed, because that is when its review is commissioned." A frozen head is never amended or rebased; a fix is a new commit on top, pushed once.

**The two machines.** The Mac and ned-box each have their own clone of the repository. Only pushed branches pass between them, through GitHub.

## The kinds of checkout

| Kind | Where | HEAD | What keeps it current today |
|---|---|---|---|
| Reference checkout | the clone's main worktree: `/Users/el/Projects/nedschorus` on the Mac, `/home/nedlern/Projects/nedschorus` on ned-box | `main` | a fast-forward at each launch (`scripts/launch-claude-mac:342`, `scripts/launch-claude-ubuntu:399`, through `checkout-freshness-catch-up.py --reference-pull`) and at the end of every agent turn in any checkout of the clone (`scripts/checkout-freshness-catch-up.py:1097-1108`) |
| Agent-home, the seat checkout | `~/agents/<seat>`, made by `git worktree add -b <seat> origin/main` (`scripts/launch-claude-mac:326`, `scripts/launch-claude-ubuntu:385`) | designed to be the seat-branch named after the seat; in practice often detached, or a topic branch | the supervisor's launch-time sync (`nc-systems/handoff/handoff-supervisor.py:780-825`) and the turn-end freshness hook |
| Managed task worktree | `<reference>/.claude/worktrees/<name>` | a topic branch | removed by `scripts/clean-worktrees.py` once merged and vacant |
| Worktree under an agent-home, or beside it | `~/agents/<seat>/.claude/worktrees/<name>`, or a sibling directory such as `/Users/el/agents/wt-<topic>` | a topic branch | nothing removes it |
| Scratchpad worktree | the session's scratchpad directory | detached or a branch | nothing removes it |
| merge-lane-2's review worktree | on ned-box, in merge-lane-2's scratchpad, made with `git worktree add --detach` at a pull request's head | detached | nothing removes it yet; planned in GHI [Before a seat is retired, report what still cites the paths the retirement removes](https://github.com/nedschorus/nedschorus/issues/226) |
| A program's own worktree | made by `scripts/daily-full-test-run-of-main.py:400`, `scripts/ghi-issue-write.py:1166` and `:1881`, `scripts/pull-request-mutation-testing-survivors.py:397`, `scripts/sanity-check-attacks.py:1163` | detached | each program removes its own |
| ghi-info's checkout | `~/agents/ghi-info` on ned-box | the branch `ghi-info` | `fast_forward_seat_checkout()` in `scripts/ghi-info-ask.py:622`, before each question |

Every checkout of a clone runs the git hooks from the reference checkout's copy, because both clones set `core.hooksPath` to the reference checkout's hook directory.

## What a checkout's HEAD can be, and what each program does

`head_state()` in `scripts/checkout-freshness-catch-up.py:459-531` sorts a checkout into one of the states below; `main()` treats a checkout on `main` as a reference checkout. The freshness hook runs at the end of each turn of an agent-session, on the checkout that holds the session's working directory, and fetches from GitHub at most once every 300 seconds.

| State | Example | Turn-end freshness hook | Launch-time sync |
|---|---|---|---|
| on `main` | the reference checkout | fast-forwarded when it has no own commits, no uncommitted tracked change and no git operation in progress; otherwise left, and the user told once | — |
| detached, no work of its own | a seat checkout parked at an old main commit | fast-forwarded, and the agent told what changed and to reread CLAUDE.md and any listed skill | fast-forwarded |
| detached, with work, or an operation in progress | a seat checkout with an uncommitted edit, or mid-rebase | left; the agent told why and what to do; a fast-forward git refuses for a reason other than an untracked file is reported to the user once | left, with the reason in the launch report |
| never pushed (`unpushed`) | a topic branch with two local commits, no copy on GitHub | rebased onto `origin/main`, unless it has an uncommitted tracked change or an operation in progress; a conflict is aborted and the agent told the files | fast-forwarded only when strictly behind with no own commits; otherwise reported as ahead, or ahead and behind |
| pushed history under a new name (`pushed-history`) | a branch cut at a pull request's pushed head to make a fix | left; the agent told not to rebase or amend those commits | as for `unpushed` |
| pushed, and HEAD equals the copy on GitHub (`pushed`) | a pull request's branch under review | left; the agent told not to rebase or amend, and to cut its next topic from `origin/main` | as for `unpushed` |
| pushed, with local commits on top (`pushed-with-local-commits`) | a fix commit not yet pushed | left; told as for `pushed` | as for `unpushed` |
| behind its own copy on GitHub (`behind-remote`) | another agent pushed a fix to this branch | left; told as for `pushed` | as for `unpushed` |
| diverged from its copy on GitHub (`diverged-from-remote`) | the branch was amended after it was pushed | left; the user told the pushed head was rewritten | as for `unpushed` |

At every turn's end, before anything else, the freshness hook also checks for two things an agent must not do, and reports each to the user: a merge from main into a working branch that git could have merged without help, and a pushed head that was rewritten (`scripts/checkout-freshness-catch-up.py:808-830`). A merge that resolved a real conflict is the allowed hand-merge, and is not reported.

Three other programs read the same states:

- `scripts/obsolete-file-edit-warning-hook.py`, after each Edit or Write, warns when the edited file is older than main's copy, with advice by state (`:106-140`).
- `.claude/hooks/session-location-write-guard.py` refuses an Edit or Write into the session's own checkout while its HEAD is detached, unless a git operation is in progress or the file is ignored by git (`:197-240`), and refuses any write into the reference checkout.
- `scripts/force-push-with-open-pull-request-guard-hook.py` refuses `git push --force` or `--force-with-lease` to a branch with an open pull request, which it asks GitHub about (`:65-81`).

## Who may move what

| Action | Allowed when | Enforced by |
|---|---|---|
| Fast-forward a checkout | it has no own commits, no uncommitted tracked change and no git operation in progress | the freshness hook and the launch-time sync, which do it themselves |
| Rebase a branch | it has never been pushed, and none of its commits is on GitHub under another name | the freshness hook, which does it itself; the force-push guard, for a branch with an open pull request |
| Amend a commit | it has never been pushed | the freshness hook reports a rewritten pushed head to the user |
| Merge main into a working branch | only to resolve a conflict git cannot resolve, as `scripts/branch-conflict-check.py` describes | the freshness hook reports any other such merge to the user |
| Push | after the suites the change can affect pass, and when the push does not conflict with main | the pre-push hook refuses a push that conflicts with main; nothing runs the tests |
| Force-push | never to a branch with an open pull request, except when merge-lane-2 asks, through `CLAUDE_MERGE_LANE_ASKED_FOR_THIS_REWRITE=1` | the force-push guard |
| Merge to main | only merge-lane-2, after review, pinned to the reviewed head commit | `scripts/merge-gate.sh` and GitHub |

## How a change reaches main

1. **Cut a topic branch from `origin/main`.** One feature or one bugfix per branch, which may take several commits. A change outside the topic goes on its own branch. Nothing enforces the base: GHI [Topic-branch base enforcement: a branch-creation script and a gh pr create check that refuses an undeclared carry of another PR's commits](https://github.com/nedschorus/nedschorus/issues/238) proposes a script and a check, unbuilt, and GHI [pull-request skill: how a change reaches main — durable-file disposition, the description, and topic-branch creation](https://github.com/nedschorus/nedschorus/issues/236) proposes cutting it from the seat-branch after fast-forwarding that branch.
2. **Work, and keep the branch current.** While the branch has never been pushed, the freshness hook rebases it onto main at each turn's end.
3. **Run the selective test run before pushing:** `python3 scripts/run-all-test-suites.py --only-suites-whose-recorded-inputs-changed-since origin/main`. CLAUDE.md asks for this; no program runs it.
4. **Push.** The pre-push hook runs `scripts/branch-conflict-check.py` against main and refuses a push that conflicts (`scripts/git-client-side-hooks-pre-push-conflict-check.py:98-162`). When the check itself cannot run, the push goes through, and the conflict is caught again at merge.
5. **Open the pull request.** From this moment the head commit is frozen.
6. **merge-lane-2 reviews and tests.** On ned-box, merge-lane-2 commissions the reviews the head commit needs, runs `scripts/pull-request-head-test-run.py` in a worktree detached at the head, and decides which findings block.
7. **Fix round.** A review with findings goes back to the author, who fixes it as one commit on top of the frozen head, pushed once, through a forked subagent.
8. **Conflict.** When `scripts/branch-conflict-check.py` reports `VERDICT: CONFLICT`: if main deleted or replaced what the branch changes, the pull request is closed and what main still lacks is carried on a new branch; otherwise the author hand-merges main into the branch, with the frozen head as first parent, plus at most one ordinary commit.
9. **Merge.** `scripts/merge-gate.sh` checks that an approving review covers the head commit and that no review or comment arrived since merge-lane-2 last read them, then prints the merge command pinned to that head commit with `--match-head-commit`. merge-lane-2 runs it.
10. **Clean up.** `scripts/clean-worktrees.py` removes a managed task worktree once its branch is merged and no program is working inside it, and deletes branches fully merged into main: daily at 06:30 on both machines, and at each handoff.

## Corrections

Each of these describes something the code shows to be otherwise. They are fixed in the pull request that lands this design, each as CLAUDE.md's obvious-fix rule allows, naming this design as the source.

1. `docs/agents/seat-first-prompt.md:28` says to "commit to your own branch and push it" and that a Mac-side agent merges, as an interim process. Changes reach main through topic branches and merge-lane-2.
2. `docs/nedschorus-wiki/nedschorus-fleet-git-worktree-working-model.md`, R15 (`:336-351`), says the freshness hook can force an agent turn and merges; the hook never forces a turn and never merges. R3, R4, R14 and R15 cite the launch-time sync, which no document describes; this design now does.
3. `docs/issues/324-checkout-freshness-catch-up-reports-instead-of-merging.md:189-221` lists the obsolete-file warning as not built; it is built as `scripts/obsolete-file-edit-warning-hook.py`.
4. `scripts/checkout-freshness-catch-up.py`'s docstring cites a walk file moved to the log-store (`:35-36`), a measurement no longer in `scripts/branch-conflict-check.py`'s docstring (`:100-102`, `:628-630`), and says a hand-merge "announces the new head" (`:674`), which CLAUDE.md no longer asks. These are comments in code, so they go in a pull request of their own.
5. `docs/nedschorus-wiki/nedschorus-fleet-machine-paths-and-checkouts.md:34` and `:50` place every task worktree under the reference checkout; many sit under agent-homes or beside them.

## Questions for the user

**Question A: does a seat checkout sit on its seat-branch, or detached?** The documents say an agent-home is "a checkout on your own branch" (`docs/agents/seat-first-prompt.md:7-14`, which tells the agent to stop if HEAD is detached), and the write guard refuses edits into a detached seat checkout. In practice the Mac's MD-skills and cold-read-research checkouts are detached, put there by their own agents' `git checkout origin/main`, and MD-skills has no seat-branch at all. Recommendation: the seat-branch, as designed. The launch-time sync recreates a missing seat-branch at `origin/main` and checks it out when the checkout is detached with no work of its own, and the freshness hook's detached message tells the agent to `git switch` back to the seat-branch. An agent then has one place to stand between topics, and GHI 236's procedure for cutting a topic branch works.

**Question B: what merge-lane-2 tests before merging.** CLAUDE.md says merge-lane-2 "runs the same selection on the head commit merged onto main before merging". merge-lane-2 runs `scripts/pull-request-head-test-run.py` in a worktree detached at the head commit itself, choosing suites from the merge base (`scripts/pull-request-head-test-run.py:226-238`); nothing tests the head merged onto main. A pull request whose head passes can still break main when main has moved since its branch was cut. Recommendation: change the program, not the sentence: test the head commit merged onto current main, so that the claim becomes true.

**Question C: who rebases a never-pushed branch.** The freshness hook rebases it at each turn's end. The supervisor's first prompt also tells the agent, "If this branch has never been pushed, rebase it onto origin/main before your first substantive action" (`nc-systems/handoff/handoff-supervisor.py:201-202`), and the obsolete-file warning tells it to run `git rebase origin/main`. Recommendation: the hook alone; the first prompt and the warning say the hook does it, and tell the agent only what to do when the hook could not.

**Question D: what "frozen" means.** CLAUDE.md freezes a head the moment it is pushed. The freshness hook agrees. The force-push guard refuses a rewrite only while the branch has an open pull request. Recommendation: pushed, everywhere; the force-push guard refuses a force-push to any branch that exists on GitHub, keeping merge-lane-2's escape, so that a branch pushed before its pull request is opened is protected too.

**Question E: which worktrees are removed.** `scripts/clean-worktrees.py` removes only managed task worktrees (`:308-310`). On the Mac on 2026-10-09, 24 worktrees under merge-lane-backlog's agent-home and five scratchpad worktrees had no remover. Recommendation: the cleaner covers every linked worktree of the clone, by the same three tests (merged, vacant, quiet), except agent-homes and the reference checkout.

**Question F: subagents.** No hook runs when a subagent stops, so a subagent working in its own worktree is never told that main moved, and its never-pushed branch is never rebased. Recommendation: register the freshness hook for the SubagentStop event too, with the agent channel only.

**Question G: a branch behind its own copy on GitHub.** The hook's state text for `behind-remote` says "fast-forward to it before working here", but the advice it gives is to leave the branch alone, and nothing fast-forwards it. Recommendation: the hook fast-forwards such a branch to its copy on GitHub when it has no own commits and no uncommitted tracked change, as it does a detached checkout, since no rewrite is involved.

**Question H: three questions merge-lane-2's review left open on PR [A detached checkout with no work of its own is moved forward to main, at launch and at each turn's end](https://github.com/nedschorus/nedschorus/pull/1110).**

- A refusal to move a detached checkout is told once per update of main, so it is not repeated until main moves again. Recommendation: leave as is; repeating it at every turn's end would be noise, and the reason does not change until the agent acts.
- Two sessions of the same seat can share one checkout, and a fast-forward run by one moves files under the other. Recommendation: the freshness hook and the launch-time sync do not move a checkout that another running session has as its working directory, using the same vacancy test as the cleaner.
- `.claude/settings.json` gives the freshness hook no timeout. Recommendation: give it one, longer than its slowest git command.

**Question I: the pre-push test run.** CLAUDE.md asks every agent to run the selective test run before pushing; no program runs it, and GHI [Move mechanical agent chores into programs and hooks](https://github.com/nedschorus/nedschorus/issues/1036) row 1 proposes the pre-push hook run it. Recommendation: keep the instruction and leave it unenforced. merge-lane-2's test run (Question B), which every pull request passes before merge, is the protection; the author's own run only finds a failure one review round sooner, which is worth asking for but not worth a hook that slows every push.

## How this design changes, and what it does not cover

The design is updated in the same pull request as any change to the programs it describes. It does not cover the main-gatekeeper of GHI [main-gatekeeper — the single check-in gate](https://github.com/nedschorus/nedschorus/issues/3), which is not in use, or the design-to-main state machine, which has its own design.
