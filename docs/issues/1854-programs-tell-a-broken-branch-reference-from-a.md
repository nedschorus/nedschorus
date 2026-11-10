---
issue: "[Programs tell a broken branch reference from a branch with no commits yet](https://github.com/nedschorus/nedschorus/issues/1854)"
kind: design
---

# Programs tell a broken branch reference from a branch with no commits yet

## What is wrong

Four programs ask `git rev-parse -q --verify HEAD` (or `HEAD^{commit}`) whether the checkout has a commit yet, and read exit 1 as "no commits yet". git also exits 1, printing nothing, when the branch HEAD names exists but its reference file holds text that is not an object name, or when HEAD's commit object is missing. A checkout that git cannot read is then treated as a fresh one: a warning is suppressed, or a stamp records the wrong state, and nothing reports that git failed.

Reproduced on ned-box with git 2.53.0, in a scratch repository with one commit whose `.git/refs/heads/main` was overwritten with the word `garbage`: `git rev-parse -q --verify HEAD` and `git rev-parse -q --verify 'HEAD^{commit}'` both exit 1 with no output, the same as in a repository that `git init` made. Codex reproduced the case of a missing commit object, on the pull request for `ghi-issue-write.py` cited below, by pointing `GIT_OBJECT_DIRECTORY` at an empty directory.

## Where

Each site came from one pull request in the 2026-10-20 round of fixes to programs that read a failed command as an answer; reviewers raised each one as a follow-up, detection only.

- `scripts/checkout-freshness-catch-up.py`, the unborn-HEAD check added by [checkout-freshness-catch-up tells a failed git command from git's no](https://github.com/nedschorus/nedschorus/pull/1744), at line 733 of that pull request's head commit.
- `scripts/new-shared-names-reminder-hook.py:294` on main, from [The name-collision and new-shared-names hooks report their own git failures instead of exiting 0 silently](https://github.com/nedschorus/nedschorus/pull/1757).
- `scripts/ghi-issue-write.py`, `head_is_unborn`, at lines 569-576 of the head commit of [ghi-issue-write reports a failed git command instead of reading it as an answer](https://github.com/nedschorus/nedschorus/pull/1759); because that function answers "no commit yet", the merge-base step after it also reads its own failure as "no merge base", so fixing the function fixes both.
- `nc-systems/cold-read/cold-read-cell-common.py`, `checkout_commit_for_provenance_stamp`, from [Cold-read-cell provenance stamp says checkout=no-commits-yet for a checkout with no commits, not a git failure](https://github.com/nedschorus/nedschorus/pull/1769).

## What to do

Write one shared helper that answers "does HEAD have a commit?" with three outcomes: a commit, no commit yet, or git could not tell, the last carrying the git command, its exit code and its stderr, so each caller can build the failure report it already builds for other git failures. Put it beside the project's other shared modules that several programs load by path, such as `nc-systems/general-tools/tmux-target-or-server-does-not-exist-error-pattern-common.py`, and name it by the naming page. Make the four sites use it.

The helper's steps, each checked on ned-box with git 2.53.0 in the scratch repositories above:

1. `git symbolic-ref -q HEAD` prints the branch HEAD names, such as `refs/heads/main`, and exits 0; it exits 1 when HEAD is detached; any other exit means git could not tell. The repository whose branch reference holds `garbage` already stops here: `git symbolic-ref -q HEAD` exits 128, "No such ref: HEAD".
2. On a branch, `git show-ref --exists refs/heads/<branch>` exits 2 when the branch has no commits yet, and any other nonzero exit, such as 1, "failed to look up reference", which it gave for the `garbage` reference, means git could not tell. Pass the branch's full reference name, never `HEAD`: `git show-ref --exists HEAD` exits 0 even in a repository with no commits.
3. When `git show-ref --exists` exits 0, or HEAD is detached, `git rev-parse -q --verify 'HEAD^{commit}'` must print a commit. Exit 1 here can no longer mean "no commit yet", so it means "git could not tell". This step catches a missing commit object: with `GIT_OBJECT_DIRECTORY` pointed at an empty directory, `git show-ref --exists` still exits 0 and this command exits 1.

`git show-ref --exists` needs git 2.43 or later. Before building, the builder asks the Mac's agent-seat, or the user, for the output of `git --version` on the Mac, because the hooks run there too. If the Mac's git is older, step 2 must tell the cases apart another way; the builder finds one and tests it on that version.

Give each site a test that plants a broken reference in a scratch repository and asserts the failure output that site already gives for other git failures: a raised error, a refusal, or the `unknown-git-exited-<code>` stamp value. Check each test by mutation testing.
