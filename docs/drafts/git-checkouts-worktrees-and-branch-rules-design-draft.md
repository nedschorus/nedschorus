# Design of record: the project's git checkouts, worktrees and branch rules

Status: decided by the user in the approval-walk git-checkouts-worktrees-and-branch-rules-design-draft-2026-10-09-2 (walk-minutes: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/git-checkouts-worktrees-and-branch-rules-design-draft-2026-10-09-2-minutes.md`); its second cold-read-full-run is pending. The section "Build" lists the work that makes main match this design; until that work lands, the programs this design names behave as their code on main does, and the design states the decided behaviour.

This design states how the project keeps each git checkout current with main, what an agent may do to a branch on its way to main, and how a change reaches main. It cites code by file and function or constant name. A description elsewhere that this design shows to be false is listed under "Corrections".

## What a reader needs first

**Checkout, worktree, HEAD.** A git checkout is a directory holding a copy of the repository's files at one commit; git calls each such directory of a clone a worktree. The clone's first worktree is its main worktree; the others are linked worktrees made with `git worktree add`. HEAD is what a checkout stands on: a branch, such as `main`, or, when HEAD is detached, a bare commit. This design says "checkout" for the directory and "check out" only for the git action.

**Behind and ahead.** A checkout is behind main by the number of commits on `origin/main` that its HEAD lacks, and ahead by the number of commits its HEAD has that `origin/main` lacks. "Own commits" below always means commits that are not on `origin/main`; a branch's commits beyond its remote branch, `origin/<branch>`, are called "local commits".

**Moving a checkout forward.** Three git operations bring a checkout up to date, and they differ in what they risk:

- a fast-forward (`git merge --ff-only origin/main`) moves HEAD to main's newest commit when HEAD has no own commits, and rewrites no commit; it overwrites every tracked file main changed, but git refuses rather than overwrite an uncommitted change to a tracked file, or an untracked file at a path main adds;
- a rebase (`git rebase origin/main`) replays a branch's own commits on top of main, giving them new commit hashes;
- a merge (`git merge origin/main`) adds a merge commit joining the branch and main.

**Frozen-head and fix-round.** Both are project-terms the glossary defines. Under this design, a frozen-head is a pull request's head commit while the pull request is open: it is never amended, rebased or force-pushed, because merge-lane-2 commissions its review against that commit. A fix-round answers review findings with one commit on top of the frozen-head, pushed once.

**The two machines.** The Mac and ned-box each have their own clone of the repository. Git branches pass between them only through GitHub.

**Scratchpad.** Claude Code gives each agent-session a temporary directory of its own, its scratchpad: under `/private/tmp/claude-501/` on the Mac and `/tmp/claude-1000/` on ned-box. The operating system can empty these directories.

**The freshness hook and the launch-time sync.** The freshness hook is `scripts/checkout-freshness-catch-up.py`, run at the end of each turn of an agent-session, on the checkout that holds the agent-session's working directory. The launch-time sync is `sync_working_branch_with_main` in `nc-systems/handoff/handoff-supervisor.py`, run by the handoff-supervisor just before it starts an agent-session, both when the agent-seat starts and after each session-handoff.

## The kinds of checkout

| Kind | Where | HEAD | What keeps it current | What removes it |
|---|---|---|---|---|
| Reference checkout | the clone's main worktree: `/Users/el/Projects/nedschorus` on the Mac, `/home/nedlern/Projects/nedschorus` on ned-box | `main` | a fast-forward each time `scripts/launch-claude-mac` or `scripts/launch-claude-ubuntu` starts an agent-seat (through `checkout-freshness-catch-up.py --reference-pull`), and `fast_forward_reference_checkout` in the freshness hook at the end of each turn of an agent-session in any checkout of the clone | never removed |
| Agent-home | `~/agents/<agent-seat>`, made by `git worktree add --detach <agent-home> origin/main` in the two launchers | detached at main's newest commit; it holds no topic work, and the write guard refuses edits in it | the launch-time sync, and the freshness hook while an agent-session works in it | never removed |
| Topic worktree | `<reference>/.claude/worktrees/<topic>`, made with `git worktree add -b <topic> ~/Projects/nedschorus/.claude/worktrees/<topic> origin/main` right after a successful `git fetch` | the topic branch | nothing moves a topic branch; the pre-push hook and merge-lane-2's merged-onto-main test catch what falling behind costs (step 2 below) | `scripts/clean-worktrees.py` (step 10 below) |
| Subagent worktree | `<reference>/.claude/worktrees/agent-<id>`, made by the Agent tool for a subagent | a branch | nothing | `scripts/clean-worktrees.py`, after an hour's quiet (step 10 below) |
| Scratchpad worktree | an agent-session's scratchpad | detached or a branch | nothing | its author, by hand; when the operating system empties the scratchpad, the directory goes and a dead registration stays, which the cleaner reports |
| merge-lane-2's review worktrees | on ned-box, in merge-lane-2's scratchpad: `wt/pr<N>-head`, detached at a pull request's head commit, and `wt/pr<N>-merged`, the head merged onto `origin/main` | detached | rebuilt by merge-lane-2 when main moves | merge-lane-2, by hand; a scheduled remover that asks GitHub whether pull request N is merged or closed is planned in GHI [Before a seat is retired, report what still cites the paths the retirement removes](https://github.com/nedschorus/nedschorus/issues/226) |
| A program's own worktree or clone | worktrees made by `scripts/daily-full-test-run-of-main.py`, `scripts/ghi-issue-write.py` and `scripts/pull-request-mutation-testing-survivors.py`; a separate local clone made by `scripts/sanity-check-attacks.py` | detached | — | the program that made it, in a `finally` block; one left by a killed program has no remover |
| ghi-info's checkout | `~/agents/ghi-info` on ned-box | the branch `ghi-info` | `fast_forward_seat_checkout` in `scripts/ghi-info-ask.py`, run by the ask that holds the lock | never removed |

Seat-branches, branches named after agent-seats, are retired: no checkout rests on one, and nothing creates one. ghi-info's checkout is the one named-branch exception, and task 168's sweep decides whether it stays.

Every checkout of the Mac's clone and of ned-box's clone runs the git hooks from the reference checkout's `scripts/git-client-side-hooks/`, because each clone's local git configuration sets `core.hooksPath` there. A separate clone, such as the one `scripts/sanity-check-attacks.py` makes, does not inherit that setting.

## What a checkout's HEAD can be, and what each program does

The freshness hook acts on the checkout that holds the agent-session's working directory, which is normally the agent-home; it sees a topic worktree only when an agent-session moves its working directory there, as Claude Code's EnterWorktree does. It fetches from GitHub at most every 300 seconds (`DEFAULT_FETCH_INTERVAL_SECONDS`) and does nothing unless the checkout is behind `origin/main` (`drift_facts`). It sorts a checkout with `head_state`, except that a checkout on `main` is handled as a reference checkout and a detached one by `move_detached_checkout_forward`. It tells the agent through `additionalContext` and the user through `systemMessage`. A note to the agent about a checkout it left alone is told once per update of main and once per reason: the `last_told` record keys on the branch, main's newest commit and the reason, so a changed reason is told at once. The hook moves no branch: it fast-forwards only the reference checkout and a detached checkout. Its `timeout` in `.claude/settings.json` is set above the sum of its slowest steps.

| State | Example | Freshness hook | Launch-time sync |
|---|---|---|---|
| on `main` | the reference checkout | fast-forwarded when it has no own commits, no uncommitted tracked change and no git operation in progress; otherwise left, and the user told once per reason | fast-forwarded when strictly behind with no own commits, no uncommitted tracked change and no git operation in progress; otherwise left, with the reason in its `branch sync:` line |
| detached, no own commits, no uncommitted tracked change, no operation in progress | an agent-home at an old main commit | fast-forwarded, and the agent told what changed and to reread CLAUDE.md and any listed skill; when git refuses, the agent told why, and a refusal that does not name an untracked file is also reported to the user once | as for `main` |
| detached, with own commits, an uncommitted tracked change, or an operation in progress | an agent-home where an agent committed by mistake | left; the agent told why, and told to carry the work to a topic worktree | as for `main` |
| never pushed (`unpushed`) | a topic branch with two local commits, no copy on GitHub | left; the agent may rebase the branch, and need not | reported, never moved |
| pushed history under a new name (`pushed-history`) | a branch cut at a pull request's pushed head commit to make a fix-round | left; the agent told that, if the pull request is open, those commits are frozen | as for `main` |
| pushed, and HEAD equals its remote branch (`pushed`) | a pull request's branch under review | left; the agent told that, if this branch has an open pull request, its head is frozen | as for `main` |
| pushed, with local commits on top (`pushed-with-local-commits`) | a fix-round commit not yet pushed | left; the agent told that, if this branch has an open pull request, the commits `origin/<branch>` holds are frozen, and that the newer local commits may be amended, or rebased with `git rebase -i origin/<branch>` | as for `main` |
| behind its remote branch (`behind-remote`) | another agent pushed a fix-round commit to this branch | left; the agent told to run `git merge --ff-only origin/<branch>` | as for `main` |
| diverged from its remote branch (`diverged-from-remote`) | the branch was amended after it was pushed; or a local commit was made while another agent pushed one | left; see the paragraph after this table | as for `main` |
| `unknown` | git did not run, or could not say whether the branch's commits are on a remote branch | left; the agent told to check `git status` (`UNKNOWN_ADVICE`) | as for `main` |

The routine messages say "if this branch has an open pull request" rather than asking GitHub, so the hook makes no network call at a turn's end beyond its fetch. The hook reaches `behind-remote` only when the branch is also behind `origin/main`; git's own refusal of a non-fast-forward push covers the cases the hook does not see.

At every turn's end, before anything else, the freshness hook also checks for two things an agent must not do, and reports each to the user:

- **A merge from main into a working branch** whose two parents re-merge without a conflict (`merges_from_main`). A merge whose parents conflict when re-merged is not reported; that covers the allowed hand-merge, and also a merge over a file main deleted, which step 8 below forbids and which nothing reports. A hand-merge that GitHub demanded although git can merge the parents cleanly is reported as forbidden; when that report reaches the user, the author explains that GitHub demanded the hand-merge, and the hook is fixed then.
- **A rewritten frozen-head** (`head_state`'s `diverged-from-remote`). Before reporting, the hook tests whether the previous value of `origin/<branch>` (`origin/<branch>@{1}`) is an ancestor of HEAD. If it is, nothing pushed was rewritten: the remote advanced under local commits, and the agent is told to rebase its local commits onto `origin/<branch>`. If it is not, the hook asks GitHub (`gh pr list --state open --head <branch>`) and reports to the user only when the branch has an open pull request, since a rewrite before a pull request opens is allowed.

Other programs that act on a checkout's state:

- `scripts/obsolete-file-edit-warning-hook.py` is the only other program that calls `head_state`; after each Edit or Write it warns when the edited file is older than main's copy, with advice by state. Its advice gives no rebase instruction and points an agent in an agent-home to a topic worktree.
- `.claude/hooks/session-location-write-guard.py`, registered for Edit, Write and NotebookEdit, uses its own `head_state_of`. It refuses a write into the agent-session's own checkout while HEAD is detached, unless a rebase, merge, cherry-pick or revert is in progress or git ignores the file, and refuses a write into the reference checkout; either refusal lets one write through when `.location-write-approved` holds the user's approval. Its refusal in an agent-home names the command that makes a topic worktree, `git worktree add -b <topic> ~/Projects/nedschorus/.claude/worktrees/<topic> origin/main`, and so does `docs/agents/seat-first-prompt.md`.
- `scripts/force-push-with-open-pull-request-guard-hook.py`, registered for Bash, refuses `git push --force` or `--force-with-lease` to a branch that GitHub says has an open pull request (`open_pull_request_for_branch`). When GitHub cannot be asked within its 20-second budget, it lets the push through with a note. Its refusal says that if merge-lane-2 asked for the force-push, the agent may run the command again prefixed with `CLAUDE_MERGE_LANE_ASKED_FOR_THIS_REWRITE=1` (`ESCAPE_HATCH_VARIABLE`); the agent sets the variable itself, and the guard does not check that merge-lane-2 asked.
- No program checks a subagent's checkout: the freshness hook is registered for Stop only, not for SubagentStop. A subagent's task is short, its branch is cut from current main or is a pushed fix-round branch, and the agent that dispatched it receives the hook's notes at its own turn's end.

## Who may move what

| Action | Allowed when | Enforced by |
|---|---|---|
| Fast-forward a checkout | it has no own commits, no uncommitted tracked change and no git operation in progress | the freshness hook and the launch-time sync, which do it themselves for the reference checkout and detached checkouts; an agent does it with `git merge --ff-only` |
| Rebase a branch | the branch has no open pull request and no other branch is built on it; or the rebase is `git rebase -i origin/<branch>`, which touches only local commits. A rebase onto `origin/main` rewrites every own commit of the branch, pushed ones included | nothing stops it; the freshness hook reports a rewrite of a branch with an open pull request to the user |
| Amend a commit | the branch has no open pull request, or HEAD is ahead of `origin/<branch>`, so the amended commit is local | nothing stops it; the freshness hook reports the rewrite of a frozen-head as above, and misses an amend of commits pushed under another branch name |
| Merge main into a working branch | only the hand-merge `scripts/branch-conflict-check.py` asks for, or one GitHub asks for when it reports a conflict that git does not | the freshness hook reports a merge whose parents re-merge cleanly |
| Push | after the suites the change can affect pass, when the push does not conflict with main, and once per fix-round | the pre-push hook refuses a push that conflicts with main; nothing runs the tests or counts the pushes |
| Force-push | never to a branch with an open pull request; closing the pull request without merging releases the freeze | the force-push guard |
| Merge to main | merge-lane-2 after review, pinned to the reviewed head commit, or an agent-seat the user deputizes in that agent-seat's own session (working model R13) | `scripts/merge-gate.sh` prints the pinned merge command; GitHub's branch protection admits two accounts, `nedlern` and `ned-review-merge`, and requires one approving review (working model R12) |

## How a change reaches main

1. **Make a topic worktree from `origin/main`.** One feature or one bugfix per topic branch, which may take several commits. After a successful `git fetch`, `git worktree add -b <topic> ~/Projects/nedschorus/.claude/worktrees/<topic> origin/main` makes the branch and its worktree together, from any checkout. The agent-home holds no topic work. Nothing enforces the base: GHI [Topic-branch base enforcement: a branch-creation script and a gh pr create check that refuses an undeclared carry of another PR's commits](https://github.com/nedschorus/nedschorus/issues/238) proposes a script and a check, unbuilt.
2. **Work.** Nothing moves the topic branch. An agent may rebase a never-pushed branch onto `origin/main`, and need not: a conflict with main is refused at the push (step 4), and a clean merge that breaks the code is caught by merge-lane-2's merged-onto-main test (step 6).
3. **Run the selective test run before pushing:** `git fetch`, then `python3 scripts/run-all-test-suites.py --only-suites-whose-recorded-inputs-changed-since origin/main`. CLAUDE.md asks for this; no program runs it or checks it. The author's own run finds a failure one review round sooner than merge-lane-2's run, which is worth asking for but not worth a hook that slows every push.
4. **Push.** The pre-push hook runs `scripts/branch-conflict-check.py` against main and refuses a push that conflicts (`scripts/git-client-side-hooks-pre-push-conflict-check.py`). When the check itself cannot run, the push goes through. Until a pull request is open, the agent may still rewrite and force-push the branch.
5. **Open the pull request.** The head commit is now a frozen-head, and the force-push guard protects the branch.
6. **merge-lane-2 tests and reviews.** On ned-box, for every pull request that changes code, merge-lane-2 runs a program in the repository that builds `wt/pr<N>-merged` at `origin/main` with `git merge --no-ff <head commit>`, never pushed, and runs `scripts/pull-request-head-test-run.py --checkout` on it; merge-lane-2's seat-brief names that program. A conflict with main stops that merge before any review is commissioned. merge-lane-2 then commissions the reviews the head commit needs and decides which findings block. When main moves with a code change before the merge, it rebuilds the merged worktree on the new main and reruns the tests; after each merge it runs every suite on main. A pull request that changes only prose gets no test run.
7. **Fix-round.** A review with findings starts a fix-round, one commit on top of the frozen-head, pushed once, written by a forked subagent. When the fix is made on a branch cut at the pushed head commit under another name, the `pushed-history` state, the commit reaches the pull request with `git push origin HEAD:<the pull request's branch>`.
8. **Conflict.** When `scripts/branch-conflict-check.py` reports `VERDICT: CONFLICT`, or GitHub reports a conflict that git does not: if main deleted or replaced what the branch changes, the pull request is closed and what main still lacks is carried on a new topic branch; otherwise the author hand-merges main into the branch, with the frozen-head as first parent, plus at most one ordinary commit for an edit the resolution forces. When the branch conflicts at the moment a fix-round commit is pushed, the pre-push hook refuses the push until the hand-merge is made. When a pull request comes to conflict with main after its review, merge-lane-2's merge onto main fails, the author clears the conflict with a hand-merge in a fix-round, and merge-lane-2 runs the tests and the review again.
9. **Merge.** `scripts/merge-gate.sh` checks that an approving review covers the head commit, that GitHub's merge state allows the merge, and that no review or comment arrived since merge-lane-2 last read them, then prints the merge command pinned to the head commit with `--match-head-commit`. merge-lane-2 runs it, as a merge commit, never a squash. The gate does not check that the merged-onto-main test ran or passed; that is a known gap.
10. **Clean up.** `scripts/clean-worktrees.py` runs daily at 06:30 on both machines, and at each session-handoff, over the worktrees under `<reference>/.claude/worktrees/`. It asks nothing of GitHub.
    - A topic worktree with no uncommitted, untracked or ignored file (disposable files such as `__pycache__` aside) and no commit outside `origin/main` is removed at the next run, if no process has its working directory inside it (`worktree_vacancy_keep_reason`).
    - Any other topic worktree is removed once nothing in it has changed for 30 days, whatever it holds, if no process has its working directory inside it. The change time is the newest of: the modification time of each file a removal would discard, the worktree's `.git` file, and its newest commit. Its branch is deleted with it, merged or not; before deleting an unmerged branch, the cleaner writes each commit's hash and subject to its log, so `git cherry-pick <hash>` brings a commit back until git's garbage collection prunes it (two weeks by git's default), and the clone's backups hold it after that.
    - A branch that no worktree has checked out is deleted when it is fully merged into `origin/main` (`branch_refs_with_no_worktree_fully_on_main`), or when its newest commit is more than 30 days old, writing its commits to the log as above.
    - A subagent worktree, named `agent-<id>`, is removed when it has no commit outside `origin/main`, is vacant, and is quiet (`agent_worktree_quiet_keep_reason`: neither the subagent's transcript nor the worktree's `.git` file written for an hour), whatever it holds.
    - Removal is `git worktree remove --force`, and the report names each file a removal discards. Uncommitted changes to tracked files and new files survive in the work-snapshot the work-snapshot hook kept, listed in the owning agent-seat's next first prompt; files git ignores, such as walk files, survive only in the machines' backups, which `scripts/find-deleted-path-across-backups.py` searches.

## Corrections

Each of these describes something shown to be otherwise; each goes by the route named.

**Fixed in the pull request that lands this design, as obvious errors under CLAUDE.md's standing approval:**

1. `docs/nedschorus-wiki/nedschorus-fleet-git-worktree-working-model.md`, R15, says the freshness hook can force an agent turn and merges; the hook never forces a turn and never merges (the code shows it: no `decision` field is emitted).
2. `docs/nedschorus-wiki/nedschorus-fleet-machine-paths-and-checkouts.md` places every task worktree under the reference checkout; many sit under agent-homes or beside them (`git worktree list` on the Mac, 2026-10-09). The working model's R21 describes every session worktree as removed, which holds only for worktrees under `<reference>/.claude/worktrees/` (`classify` in `scripts/clean-worktrees.py`).

**In the freshness hook's pull request (task 166):** the hook's docstring cites a walk-document moved to the log-store, cites a measurement "recorded in" `scripts/branch-conflict-check.py`'s docstring that the docstring no longer holds, and says a hand-merge "announces the new head", which CLAUDE.md no longer asks.

**edit-GHI (task 170):** `docs/issues/324-checkout-freshness-catch-up-reports-instead-of-merging.md` lists the obsolete-file warning as not built, and it is built as `scripts/obsolete-file-edit-warning-hook.py`; `docs/issues/226-run-fleet-maintenance-on-a-schedule-weekly-worktree.md` says the cleaner removes only a worktree with no uncommitted, untracked or ignored files, and it will describe step 10's rule.

**In task 168's sweep:** `docs/agents/seat-first-prompt.md`, the glossary's agent-home and seat-branch entries, and the other files listed in `docs/drafts/git-checkouts-worktrees-and-branch-rules-agent-home-detached-follow-on-changes.md` still place an agent-home on its seat-branch.

**In the combined CLAUDE.md approval-walk:** CLAUDE.md says a head commit "becomes a frozen-head the moment it is pushed"; under this design it becomes one when its pull request is open. The sentence goes to the combined CLAUDE.md approval-walk, not to this design's pull requests.

## Decisions

Each line is one item of the approval-walk git-checkouts-worktrees-and-branch-rules-design-draft-2026-10-09-2; walk-minutes: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/git-checkouts-worktrees-and-branch-rules-design-draft-2026-10-09-2-minutes.md`.

1. An agent-home rests detached at main and holds no topic work; every topic gets its own worktree under `<reference>/.claude/worktrees/`; seat-branches are retired; every file that assumes a seat-branch is swept.
2. merge-lane-2's merged-onto-main test moves into the repository as a program, and merge-lane-2's seat-brief names it.
3. No agent and no program rebases a never-pushed branch as a rule; a topic worktree is made right after a successful fetch; the freshness hook's rebase step and the rebase instructions in `BRANCH_STATE_INSTRUCTION` and the obsolete-file warning go.
4. A head commit is frozen once its pull request is open, not once it is pushed. The rule is written where it applies: the glossary's frozen-head entry, the freshness hook's conditional message, and this design; the CLAUDE.md sentence goes to the combined CLAUDE.md approval-walk. The worktree command is named in the write guard's refusal and in `docs/agents/seat-first-prompt.md`. The hook's rewrite report asks GitHub first and reports only for an open pull request; closing a pull request unmerged releases the freeze; "unless another branch is built on it" stays an instruction with no check.
5. The cleaner removes a clean, merged topic worktree at its next run, and any other topic worktree with its branch after 30 days with no change, writing deleted commits to its log; old branches with no worktree go the same way; no GitHub query. A wiki page on backup procedures is added as a task to GHI [Backup strategy for state outside git (Time Machine covers today; inventory + restore drill when the boss teaches it)](https://github.com/nedschorus/nedschorus/issues/7).
6. No freshness hook for subagents.
7. The `behind-remote` message names `git merge --ff-only origin/<branch>`; no new hook code.
8. The `last_told` record keys on the reason too; the shared-checkout case needs nothing, because an agent-home holds no work; the hook gets an explicit timeout.
9. No hook runs the test suites before a push.
10. A commit not yet on GitHub may be amended, or rebased with `git rebase -i origin/<branch>`; the rewrite report tells a remote that advanced under local commits from a rewrite.
11. This design states the deputized merge, GitHub-only conflicts, one push per fix-round and the merge gate's gap; the corrections above go by their routes.
12. Step 8 states what happens when a pull request conflicts with main after its review; the freshness hook's false report of a hand-merge GitHub demanded is recorded, not fixed, until it happens.
13. A git and GitHub architecture overview is written for the wiki after the build (13a); the overview-refresh reminder is extended to every overview in the wiki and every component each lists (13b, GHI [refresh-design: when a system's code lands, bring its design, build-slice plan and overview into line — removing, never revising](https://github.com/nedschorus/nedschorus/issues/670)); the daily maintenance build writes a maintenance overview (13c, GHI [Daily maintenance in one daily step, starting with a daily check of every wiki page](https://github.com/nedschorus/nedschorus/issues/1058)); the repository-layout plan gets system directories for git and GitHub and for backup and recovery (13d, GHI [Rationalize the repository layout: group components by owning system under nc-systems/, and a hook dispatcher](https://github.com/nedschorus/nedschorus/issues/224)); a GHI is filed for a wiki page on the two machines and their network (13e).

## Build

Each item is a task on the MD-skills agent-seat's task list, and each code change goes in its own topic branch and pull request.

- **Task 166, the freshness hook:** decisions 3, 4, 7, 8 and 10 in `scripts/checkout-freshness-catch-up.py`, its test, `BRANCH_STATE_INSTRUCTION` in `nc-systems/handoff/handoff-supervisor.py`, the obsolete-file warning's advice, the `timeout` in `.claude/settings.json`, and the stale docstring above.
- **Task 167, the cleaner:** step 10's rules in `scripts/clean-worktrees.py` and its test. Worktrees that today sit under agent-homes or beside them, outside the managed area, are moved or removed by their owners once.
- **Task 168, the agent-home sweep:** decision 1 and decision 4's write-guard and first-prompt text, across the files listed in `docs/drafts/git-checkouts-worktrees-and-branch-rules-agent-home-detached-follow-on-changes.md`: the launchers, `sync_working_branch_with_main`, the write guard, the obsolete-file warning, `scripts/ghi-info-ask.py`, `scripts/design-to-main/design-to-main-git-record.py`, their tests, `docs/agents/seat-first-prompt.md`, the start-new-agent-seat skill, the glossary, the wiki pages and the GHI-MDs; several pull requests.
- **Task 169, merge-lane-2's test program:** decision 2, built with merge-lane-2.
- **Task 170, GHI edits:** the edit-GHI corrections above, the tasks decisions 5 and 13 add to GHIs, the GHI decision 13e files, and the link from GHI [One design of record for the project's git checkouts, worktrees and branch rules](https://github.com/nedschorus/nedschorus/issues/1121) to this design.
- **Task 171, the overview:** decision 13a, after tasks 166 to 169 land.

## How this design changes, and what it does not cover

The design is updated in the same pull request as any change to a rule it states. It does not cover the main-gatekeeper of GHI [main-gatekeeper — the single check-in gate](https://github.com/nedschorus/nedschorus/issues/3), which is not in use, or the design-to-main state machine, which has its own design. On landing, it moves to `docs/issues/1121-git-checkouts-worktrees-and-branch-rules-design.md`, beside the GHI-MD of GHI [One design of record for the project's git checkouts, worktrees and branch rules](https://github.com/nedschorus/nedschorus/issues/1121).

Checked against main at 1ed6d45a on 2026-10-11.
