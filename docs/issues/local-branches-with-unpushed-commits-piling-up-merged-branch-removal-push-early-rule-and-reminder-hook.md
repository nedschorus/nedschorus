# Stop local branches with commits on no remote from piling up: clean up branches whose pull request merged, push branches early, and remind the agent to push

## Problem

On 2026-10-13 an inventory of both machines found 116 local branches holding commits that are on no remote: 31 on ned-box and 85 on the Mac. The tables, one row per branch with the evidence for each, are `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/cold-read-improvement/ned-box-unpushed-commits-classification-2026-10-13.md` and `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/cold-read-improvement/mac-unpushed-commits-classification-2026-10-13.md`. A commit "on no remote" is one that `git rev-list <branch> --not --remotes` lists.

| What the branch held | Branches |
|---|---|
| work already on main, the branch left behind | 86 |
| work in progress, never pushed | 12 |
| work held local on purpose: parked by the user, local-only work in progress, or waiting for another branch or an approval-walk | 6 |
| work dropped by a decision | 5 |

The work already on main reached main in several ways, and `scripts/clean-worktrees.py`, the daily job that removes finished worktrees and branches, recognises none of them:

- Squash merges. Main squash-merged its pull requests until PR #182 on 2026-08-28; 22 commits on main's first-parent history are squash merges. A squash merge puts the branch's content on main under a new commit, so `git log origin/main..<branch>` stays non-empty for ever. Since then merge-lane-2 merges with a merge commit (`gh pr merge --merge --delete-branch`, the command `scripts/merge-gate.sh` prints), which keeps a merged pull request's head commit on main.
- Local merges of origin/main on top of a merged head commit. 17 of the Mac's branches carried only merges of origin/main, made from 2026-08-14 to 2026-09-14, on top of a pull request's head commit that later merged. Those merge commits are on no remote, so the branch never counts as merged.
- The same change merged from another branch: rebased or copied commits, a subagent's worktree branch whose work its parent pushed under another name, or a GHI-MD the GHI write tool (`scripts/ghi-issue-write.py`) merged from its own branch.

The work that was not on main shows the other half of the problem: 12 branches of work in progress existed on one machine only, and the owner of 5 of them had stopped working on them 8 to 11 days earlier. Work that exists only on one machine is lost when the worktree is removed or the machine fails, and no other agent-seat can see or take over work it cannot fetch.

The branches found on 2026-10-13 are being cleared by hand: the user approved deleting the ones whose work is on main or was dropped, and having their owners push the ones in progress (approval-walk open-decisions-unpushed-branches-memory-claude-md-root-cause-and-cold-read-2026-10-14, items 1.2 and 2; walk-minutes `nedlern@ned-box:/home/nedlern/agents/cold-read-improvement/docs/walk/open-decisions-unpushed-branches-memory-claude-md-root-cause-and-cold-read-2026-10-14-minutes.md`, which move to the log-store's `walk/` directory when the approval-walk closes). This GHI keeps them from piling up again. The user approved its three changes in the same approval-walk, item 5.

## Change 1: `scripts/clean-worktrees.py` removes a branch whose pull request merged

### What the script does today

The script runs daily with `--remove` on both machines, from the reference clone, and with `--only-done` at every agent-seat launch. It acts on two things:

- A worktree under `<clone>/.claude/worktrees/`. Such a worktree is removable, which the script calls done, when `git log origin/main..HEAD` is empty, no process has its working directory inside it, and, for a subagent's `agent-<id>` worktree, nothing wrote to it for an hour. A done worktree is removed with `git worktree remove --force` whatever files it holds: the script lists its modified, staged, untracked and ignored files (`.DS_Store` and `__pycache__` left out), names them before the removal and again after it, and the files are deleted. Its branch is then deleted with `git branch -d`, which git refuses for a branch it does not see as merged. Worktrees outside `.claude/worktrees/`, such as an agent-seat's `/home/nedlern/agents/<seat>-<topic>` worktrees, are never touched.
- A local branch no worktree has checked out. `--remove` deletes it with `git branch -d` only when `git for-each-ref --merged origin/main` lists it.

Both tests ask whether the branch's commits are ancestors of origin/main, which is false after a squash merge and false when the branch has commits on top of its merged head commit. 75 of the 90 branches the inventory marked for deletion had no worktree, so the second path matters most.

### The change

Both paths gain one more way to count a branch as merged, read from GitHub. A branch whose tip is commit T counts as merged through a pull request when GitHub lists a pull request of `nedschorus/nedschorus` that is merged, whose base branch is main, and whose head commit H relates to T in one of three ways:

1. T is H.
2. T is an ancestor of H: someone pushed further commits to the pull request from elsewhere, and all of T's commits are in H.
3. H is an ancestor of T, and every commit reachable from T but not from H or origin/main is a merge commit whose tree equals git's own automatic merge of its parents (`git merge-tree --write-tree <first parent> <second parent>`). Such a merge only brought main in and changed nothing by hand.

The base-branch condition matters because a stacked pull request merged into another pull request's branch does not put its content on main. The relation between T and H matters because a branch with commits of its own after its pull request merged holds work that is on no remote.

The script reads the merged pull requests once per invocation, not once per branch: for example `gh api --paginate 'repos/nedschorus/nedschorus/pulls?state=closed&per_page=100'`, keeping the ones with a `merged_at` and a base of main, and mapping each head commit to its pull request number. It reads them only when some branch fails the ancestry test, so an invocation with nothing to decide makes no network call. A head commit H that is not in the local clone cannot be compared with T except for equality; relations 2 and 3 then do not hold, and the branch is kept.

What the script then does with a branch that counts as merged through a pull request:

- A worktree under `.claude/worktrees/` on that branch must still pass the vacancy test and, for a subagent's worktree, the hour of quiet. It is removed only when it holds no modified, staged, untracked or ignored file, `.DS_Store` and `__pycache__` aside: the same set the script lists today. A worktree that holds any such file is kept, and its line says so and names the files, for example: `agent-a1b2c3: kept — its pull request #1234 merged, but it holds 2 uncommitted, untracked or ignored file(s): notes.md, docs/walk/x.md; commit, move or delete them, and the next invocation removes it`. Ignored files count because the ignored directories include `docs/walk/` and `cold-read-records/`, which hold approval-walk files and cold-read-records that may not yet be in the log-store.
- After the worktree is removed, and for a branch no worktree has checked out, the branch is deleted with `git branch -D`. The script uses `-d` today so that git's own merged test backs up the script's; for this class git's test always refuses, and the pull-request test above takes its place. The script names the pull request in the line it prints: `branch <name>: deleted (its pull request #1234 merged at this branch's tip)`.
- `--only-done` and the plain report name the same branches and worktrees, with the pull request number, without deleting anything.

The worktrees outside `.claude/worktrees/` stay outside the script's reach, as today; 4 of the 90 branches marked for deletion were in such a worktree.

### When GitHub cannot be read

When the read of merged pull requests fails, because `gh` is missing, exits nonzero, times out, or returns output that cannot be parsed, the script:

- prints one line naming what failed, with `gh`'s own error, and saying that no branch was counted as merged through a pull request in this invocation, so branches whose pull request merged are kept until GitHub can be read;
- still applies the ancestry test, so it removes what it removes today;
- exits 1, the status it already uses when a removal fails; the docstring's list of exit codes adds this cause.

On ned-box the daily cron job reaches GitHub through `gh`'s login in `/home/nedlern/.config/gh/hosts.yml` (account ubuntu-claude, checked 2026-10-13 with `GH_TOKEN` unset). Whether the Mac's launchd job can read `gh`'s token from the Mac's keychain has not been checked; the first daily invocation on the Mac shows it, through the failure line above if it cannot.

### What the change does not catch

A branch whose work reached main from a different branch, with no merged pull request whose head commit relates to the branch's tip as above, is still kept. On ned-box, change 1 would have caught 2 of the 8 branches whose work the inventory found on main; on the Mac, about 40 of the 78 branches marked for deletion had no merged pull request of their own, most of them with their work on main and the rest dropped work. Deciding that such a branch's work is on main takes a judgment about its content, which is the question under "Questions for the user" below.

### Tests

New tests in `scripts/clean-worktrees-test.py`, with `gh` replaced by a fake that returns a fixed list of merged pull requests, cover: each of the three relations, counted as merged; a branch with a commit of its own after the merged head commit, kept; a merge commit on top whose tree differs from git's automatic merge, kept; a pull request merged into a base other than main, not counted; a squash-merged worktree holding an untracked file and one holding an ignored file, each kept and its files named; a branch no worktree has checked out, deleted with `-D`; `gh` exiting nonzero and `gh` returning text that is not JSON, each printing the failure line, removing nothing it would not remove today, and exiting 1.

## Change 2: CLAUDE.md says to push a branch whenever it has commits

### Pushing a branch commissions nothing

merge-lane-2 works from the queue of open pull requests: its seat-brief (`/home/nedlern/agents/merge-lane-2/CLAUDE.local.md`, lines 8 and 16) says it holds the open pull-request queue and, for each pull request, picks the review tier and commissions the reviewers. `scripts/merge-gate.sh` takes a pull request number. The repository has no `.github/workflows/` directory, and the user switched off the automatic Codex reviews on 2026-08-28. So a pushed branch with no pull request is reviewed by nobody and merged by nobody; checked 2026-10-13.

### The text

In the bullet "How a change reaches main", insert after "Never extend an existing pull request with a second topic.":

> Push a topic branch whenever it has commits, so that no work exists on one machine only, unless the user has told you to keep that branch local; open its pull request only when the work is ready for review.

In the same bullet, replace:

> A head commit becomes a frozen-head the moment it is pushed, because that is when its review is commissioned.

with:

> A pull request's head commit becomes a frozen-head when merge-lane-2 commissions its review, which can happen as soon as the pull request is open; so once a branch has an open pull request, never amend, rebase or force-push it. Until then the branch is not frozen: when it falls behind main or conflicts with it, rebase it onto origin/main and push it with `git push --force-with-lease`.

The bullet "Before pushing, run only the test suites your change can affect" stays as it is, so the test suites run before every push, including the early ones.

`scripts/git-client-side-hooks/pre-push` refuses a push of a branch that conflicts with main. For a branch with no pull request the new sentence gives the remedy, a rebase; `scripts/force-push-with-open-pull-request-guard-hook.py` refuses a force push to a branch that has an open pull request, so the rebase cannot move a head commit under review.

### What the new rule breaks, and changes in the same pull request

Several files say a head commit is frozen once pushed. The pull request that changes CLAUDE.md changes them too, so that the rule and the programs agree:

- `docs/nedschorus-wiki/nedschorus-glossary.md`, the entry frozen-head ("a pull request's head commit once pushed"); `docs/nedschorus-wiki/nedschorus-sdlc-terms.md`, the entry head commit ("once pushed it is the frozen-head"); and the `head` row of `docs/nedschorus-wiki/nedschorus-style-guide.md` ("the pushed head commit must not be amended").
- `scripts/checkout-freshness-catch-up.py`, the Stop hook that rebases a never-pushed branch onto main and never moves a pushed one. Its `head_state` docstring says the frozen-head rule freezes a head commit the moment it is pushed and that it does not ask GitHub whether a pull request is open, to avoid a network call at every turn's end. Under the new rule most working branches are pushed, so the hook would stop rebasing them; its messages for a pushed branch would also forbid a rebase the new rule allows. How the hook should behave is the first question below.
- `scripts/obsolete-file-edit-warning-hook.py`: `PUSHED_ADVICE` says "This branch is pushed, so its review may be running: do not rebase or amend it", and `NEVER_PUSHED_ADVICE` ties the rebase to a never-pushed branch.
- `nc-systems/handoff/handoff-supervisor.py`: `BRANCH_STATE_INSTRUCTION` tells a new agent-session to rebase a never-pushed branch and to leave a pushed one as it is.
- `docs/agents/seat-first-prompt.md`, line 28: "Commit to your own branch and push it; never push to `main` yourself. Open a pull request", which reads as push and open a pull request together.

GHI [One design of record for the project's git checkouts, worktrees and branch rules](https://github.com/nedschorus/nedschorus/issues/1121) lists, among its disagreements, that "frozen" means "has an open pull request" to the force-push guard and "pushed" to the freshness hook. This change settles that disagreement in favour of the open pull request; the design of record GHI 1121 produces records it.

## Change 3: a hook reminds the agent when its branch has commits on no remote

### What the hook does

A new PostToolUse hook, `nc-systems/general-tools/claude-code-after-bash-current-branch-unpushed-commits-push-reminder-hook.py`, runs after every Bash call; commits are made with git through Bash. When the command contains no `git` word, the hook exits at once. Otherwise it looks at each checkout the call may have committed in: the checkout holding the call's working directory, and the checkout of each directory the command passes to `git -C` or `cd`, read with `nc-systems/general-tools/shell-command-tree-sitter-bash-reader-common.py`, the shell reader the force-push guard uses. For each checkout on a branch other than main, it counts `git rev-list --count HEAD --not --remotes`. A count above zero produces the reminder.

A commit already pushed under another branch name, such as a branch cut at a pull request's pushed head commit, is on a remote and is not counted. The hook makes no network call: the remote-tracking refs are as fresh as the last fetch or push, and a push updates them.

### How it avoids noise

- It reminds once per agent-session, checkout and tip commit: it records the tip it reminded about in a file in the checkout's own git directory, keyed by the agent-session's id, as `scripts/obsolete-file-edit-warning-hook.py` records the warnings it gave. The reminder comes again only after a new commit.
- It says nothing on a detached HEAD, on main, or when the count is zero.
- It says nothing about a checkout the call did not touch, so one agent-seat is not told about another agent-seat's branches in a shared clone.

### What the message says

The message, through `additionalContext`, says what was found, then one instruction per line with its condition:

> Branch `<branch>` in `<checkout>` has `<n>` commit(s) that are on no remote, so they exist only on this machine.
> Run `python3 scripts/run-all-test-suites.py --only-suites-whose-recorded-inputs-changed-since origin/main`, then push with `git push -u origin <branch>`.
> If the push is refused because the branch conflicts with main and the branch has no open pull request, rebase it onto origin/main, run the test suites again and push with `git push --force-with-lease`.
> If the user told you to keep this branch local, leave it; this reminder comes again only after the branch's next commit.
> If this branch's pull request has already merged, do not push it: its work is on main, and `scripts/clean-worktrees.py --remove` deletes the branch.

When git fails while the hook checks a checkout, the message says that the hook could not check the branch, with git's error; the hook always exits 0, since the tool call has already happened.

### Why a separate hook after a tool call

`scripts/checkout-freshness-catch-up.py` already works out at every turn's end whether a branch is pushed. The user's decision was a reminder after a tool call, which comes right after the commit, while the agent is still at that step; a Stop hook speaks only when the turn ends, often after the agent has moved on. The new hook is small and shares nothing with the freshness hook but one git command.

### Tests

`nc-systems/general-tools/tests/claude-code-after-bash-current-branch-unpushed-commits-push-reminder-hook-test.py`, against a test fixture repository with a bare remote: a commit on a never-pushed branch, reminded; the same tip after a second Bash call in the same agent-session, not reminded; a second commit, reminded again; a pushed branch, silent; a branch cut at the pushed head commit of another branch, silent; a detached HEAD and main, silent; a commit made with `git -C <other checkout>`, reminded about that checkout; a command with no `git` word, silent with no git call; git failing, the failure message and exit 0. The hook is registered in `.claude/settings.json` under PostToolUse with the matcher `Bash`.

## Questions for the user

1. **How the freshness Stop hook treats a pushed branch with no pull request.** Under the new rule the hook would stop rebasing most working branches, because they are pushed. Option A, recommended: the hook still rebases only a never-pushed branch and never moves a pushed one, so it needs no network; its messages and `PUSHED_ADVICE` change to say that a pushed branch with no open pull request may be rebased and pushed with `--force-with-lease`, and the force-push guard refuses that when a pull request is open. Option B: the hook asks GitHub at every turn's end whether the branch has an open pull request, and rebases and force-pushes a branch that has none; this keeps branches current without the agent's help, at the cost of a network call at every turn's end and a force push made by a program.
2. **A test of content instead of, or beside, the test of pull request state.** A branch whose content is all on main could be found without GitHub: when `git merge-tree --write-tree origin/main <branch>` gives exactly origin/main's tree, merging the branch would change nothing, so deleting it loses nothing. Such a test catches every way the inventory found work reaching main, including the branches change 1 does not catch, and needs no network, so it has no GitHub failure to report. It keeps a branch when main later changed the same lines, which errs toward keeping. Recommended: use the content test in place of the pull-request test, and keep the pull-request number only as a label in the report where GitHub can supply it.
3. **A worktree whose branch is merged by ancestry and which holds uncommitted files.** Change 1 keeps a worktree whose pull request merged when the worktree holds uncommitted files, while the script goes on removing, with its files, a worktree whose branch is an ancestor of origin/main. A worktree just created from origin/main, holding edits not yet committed and briefly vacant, is such a worktree. Recommended: keep any worktree holding such files, whichever test found its branch merged.
4. **Remote branches.** Pushing early leaves more branches on GitHub: a branch whose work is dropped, or merged from another branch, stays there, because merge-lane-2 deletes a branch only when it merges that branch's pull request, and the repository's `delete_branch_on_merge` setting is off. On 2026-10-13 origin held 92 branches and 28 open pull requests. Should a follow-up GHI cover deleting remote branches whose work is on main?

## Related GHIs

- [One design of record for the project's git checkouts, worktrees and branch rules](https://github.com/nedschorus/nedschorus/issues/1121): the frozen-head disagreement above, and the worktrees outside `.claude/worktrees/` that nothing removes.
- [Topic-branch base enforcement: a branch-creation script and a `gh pr create` check that refuses an undeclared carry of another PR's commits](https://github.com/nedschorus/nedschorus/issues/238): how a branch is created; not changed here.
- [Four small skills the user named on the vocabulary page: /save, /push, /save-MD, /save-MD-as-draft (name open)](https://github.com/nedschorus/nedschorus/issues/256): a `/push` skill, which the reminder's push instruction could later name.

## Next action

The user answers the four questions above. Then an agent-seat builds the three changes as three pull requests: change 1 with its tests; change 2 with the files it breaks; change 3 with its tests and its entry in `.claude/settings.json`. Change 3 follows change 2, because the reminder's instructions assume the new rule.
