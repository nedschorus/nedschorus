# Part two: the messages of the git hooks that run at commit and push

This document is part two of GHI [Every refusal and warning a program hands an agent says why and what to do instead](https://github.com/nedschorus/nedschorus/issues/956). The GHI's GHI-MD, `docs/issues/956-every-refusal-and-warning-a-program-hands-an.md`, is part one, and its section "Later parts" lists the five parts after it, this one first. This part covers the messages of the git hooks that run when an agent commits or pushes. It shows each message that leaves the agent a question open, as the agent sees the message, and proposes the exact words to replace it, with the code changes the new words need. The user approved every proposed text and code change below in the approval-walk 956-part-two-the-git-hooks-messages-2026-10-04, whose minutes are in the log-store. The next action is one pull request, cut from main, that builds them with their test cases.

## What a reader needs first

**Where the hooks run from.** Each machine's clone sets `core.hooksPath` to `scripts/git-client-side-hooks/` inside the clone's main checkout: `/Users/el/Projects/nedschorus` on the Mac and `/home/nedlern/Projects/nedschorus` on ned-box. That checkout stays on main, so every agent-seat's worktree on the machine runs main's copy of the hooks. The agent's own worktree has its own copy of every script, at the same relative paths, from whatever commit the worktree has checked out.

**The hooks.** The directory holds four hooks:

- `pre-commit` refuses a commit made inside an agent-session when the commit's author or committer email address is one of the user's three addresses or the `unconfigured-agent` address. A commit made outside an agent-session is not checked. Git runs `pre-commit` for `git commit`, including `--amend`; `git rebase` and `git cherry-pick` run neither; `--no-verify` skips both.
- `pre-merge-commit` runs `pre-commit`'s check for a merge commit made by `git merge`, and prints the same refusal.
- `prepare-commit-msg` adds a trailer naming the agent-session that made the commit: `Claude-Session: https://claude.ai/code/<id>` when the agent-session has a claude.ai link, otherwise `Claude-Session-Id: <id>`. It adds nothing outside an agent-session, and leaves a message that holds only comment lines untouched. Git runs it for every commit, including each commit a rebase, a cherry-pick or a merge makes.
- `pre-push` runs `scripts/git-client-side-hooks-pre-push-conflict-check.py`, called the pre-push conflict check below. That program runs `scripts/branch-conflict-check.py` on each branch the push sends to the remote named origin, except main and except a deletion, and refuses the push when a branch conflicts with origin/main. A push of main, of a tag, of a deletion, or to another remote is never checked, and `git push --no-verify` skips the hook.

A git hook's message is what the hook prints to stderr. An agent that runs `git commit` or `git push` through Bash sees the message in the command's output, among git's own lines.

**Failing open.** A pre-push hook that exits nonzero stops the push, and a prepare-commit-msg hook that exits nonzero stops the commit. Both hooks run for every agent-seat on the machine, so both are written to exit 0 when their own work fails, as long as the hook itself starts: a failure in a hook must not stop every agent's work. CLAUDE.md's rule for a failure is that the program "prints what failed and exits nonzero"; these two hooks keep the first half and deliberately break the second, so the message is the only place the failure shows. Each message in this part reports such a failure: a conflict check that did not happen, or a trailer that may not have been added.

**The four questions.** As in part one, a message is complete when the message says:

1. What was refused or found, naming the file or the command.
2. Why: the rule being enforced, or what goes wrong if the agent goes ahead.
3. What to do instead, as an instruction.
4. Under which condition each instruction applies, when the message gives more than one.

**Where the list comes from.** Part one's audit put these four questions to 139 messages printed by this repository's programs; its report is `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/MD-skills/refusal-and-warning-message-audit-2026-10-01.md`. For the git hooks it found that seven pre-push messages give no instruction and that the trailer message gives no reason. A message the audit did not flag, the one for a check that gave no answer, is added here because the new texts would otherwise disagree with it in one push's output. Every message below was read again from main at the commit [Merge pull request #1025 from nedschorus/skill-start-new-agent-seat-on-ned-box](https://github.com/nedschorus/nedschorus/commit/1a23e5ef), and the line numbers are main's at that commit.

## What every unchecked push should tell the agent

Seven of the messages below end "the push goes ahead unchecked". From that the agent cannot tell which branches went unchecked, whether to do anything, or whether to tell anyone. Three facts decide what each message should say:

- A branch that was not checked may still conflict with main, and the agent can check the branch by running, from the agent's own worktree, `python3 scripts/branch-conflict-check.py --head <commit>`. That program prints a VERDICT line and says what to do: for a conflict, CLAUDE.md's procedure applies, which starts by seeing what the conflict is with.
- In a push of several branches, one branch's check can go unrun while another branch conflicts. The conflict then refuses the whole push. So a message must say which branches were not checked, not that the push went ahead. When no branch conflicts, git goes on with the push, and git's own output says whether the push reached origin.
- When the hook's own machinery fails, rather than a check merely running out of time, the next push on the same machine may fail the same way. The user is the one who can repair the machine or have the hook fixed, so the agent tells the user what the message says.

So each proposed text names the branches that were not checked and the reason, gives one command per branch to run by hand, and, when the hook's machinery failed, tells the agent to tell the user the whole message. Where a reason is printed by git or by Python just above the hook's line, the text says so.

## Code the new texts need

The texts below name each unchecked branch and its commit. Two programs print them, and only one knows the branches today:

- `scripts/git-client-side-hooks/pre-push`, the shell part, prints messages 2 and 3 without reading what git hands the hook: the remote's name, and one line per ref the push sends. The proposal has it read those lines first, keep the branches the pre-push conflict check would check (remote origin, a ref under `refs/heads/` other than main, not a deletion), print nothing when there are none, and then pass the same lines on to the pre-push conflict check: it reads them once into a shell variable and writes the variable to the check's standard input. The shell part stays POSIX sh, because a hook whose interpreter is missing stops every push. The two programs' rules for which branches count must agree, so `scripts/git-client-side-hooks-pre-push-test.py` gains cases that push main, a tag, a deletion, and to another remote, and asserts that both programs ignore each.
- `scripts/git-client-side-hooks-pre-push-conflict-check.py` already knows each branch and commit in messages 4, 5, 6 and 9. For message 7 it names the branches when it had read them before the error, and otherwise says so: the variable holding the pushed lines starts empty, and the error handler checks whether it was filled.
- `scripts/git-client-side-hooks/prepare-commit-msg` fills `{trailer}` in message 8 from the trailer it already builds.

## The messages, one at a time

In the proposed texts, `{branches}` is the unchecked branches, each with its commit, separated by commas, such as `fix-layout (1a23e5ef), docs-move (9c0d2b11)`; `{unchecked_lines}` is one line for each of those branches:

```
Check {branch} by hand from your worktree: python3 scripts/branch-conflict-check.py --head {commit}
```

and `{tell_user_line}` is:

```
Tell the user this whole message, including any error printed just above it: the next push on this machine may go unchecked the same way.
```

### 1. python3 is not on PATH: removed

`scripts/git-client-side-hooks/pre-push:30-34` checks for python3 and prints its own message when python3 is missing. python3 is on PATH on both machines, also in a bare `sh` with no environment (`/usr/bin/python3`). The proposal removes that check and its message. If python3 is ever missing, the next line, `python3 "$conflict_check"`, fails with exit status 127, the shell prints "python3: not found", and message 3 reports the failure.

### 2. The pre-push conflict check is missing

**When an agent sees this.** The main checkout that `core.hooksPath` points into has no `scripts/git-client-side-hooks-pre-push-conflict-check.py`, for example because the checkout was switched off main.

**What the agent is told today** (`scripts/git-client-side-hooks/pre-push:36`; the hook fills in the path):

```
pre-push: the conflict check did not run (/Users/el/Projects/nedschorus/scripts/git-client-side-hooks/../git-client-side-hooks-pre-push-conflict-check.py is missing); the push goes ahead unchecked.
```

**What the agent cannot tell from the text.** Which branches went unchecked, what to do, and whether to tell anyone.

**Proposed text** (`{path}` is the missing file):

```
pre-push: the pre-push conflict check did not run, because {path} is missing, so no branch in this push was checked for conflicts with origin/main: {branches}.
{unchecked_lines}
{tell_user_line}
```

### 3. The pre-push conflict check exited with an unexpected status

**When an agent sees this.** The pre-push conflict check exits with a status other than 0, which lets the push through, and 10, which refuses the push. Python prints its own error just above the hook's line.

**What the agent is told today** (`scripts/git-client-side-hooks/pre-push:47`):

```
pre-push: the conflict check failed (exit 1); the push goes ahead unchecked.
```

**What the agent cannot tell from the text.** Which branches went unchecked, what to do, and whether to tell anyone.

**Proposed text** (`{status}` is the exit status):

```
pre-push: the pre-push conflict check exited with status {status}, so no branch in this push was checked for conflicts with origin/main: {branches}.
{unchecked_lines}
{tell_user_line}
```

### 4. branch-conflict-check.py is missing from the main checkout

**When an agent sees this.** The pre-push conflict check runs, but `scripts/branch-conflict-check.py` is not beside it in the main checkout.

**What the agent is told today** (`scripts/git-client-side-hooks-pre-push-conflict-check.py:151`):

```
pre-push: the conflict check did not run (/Users/el/Projects/nedschorus/scripts/branch-conflict-check.py is missing); the push goes ahead unchecked.
```

**What the agent cannot tell from the text.** Which branches went unchecked, what to do, and whether to tell anyone. The agent's own worktree has its own copy of the file, so the agent can still run the check by hand.

**Proposed text** (`{path}` is the missing file):

```
pre-push: the pre-push conflict check did not run, because {path} is missing, so no branch in this push was checked for conflicts with origin/main: {branches}.
{unchecked_lines}
{tell_user_line}
```

### 5. The time budget ran out before a branch's turn

**When an agent sees this.** One push carries several branches, and the checks of the earlier branches used up the hook's time budget before this branch's turn. The budget is 60 seconds, or the number of seconds in `NEDSCHORUS_PRE_PUSH_CONFLICT_CHECK_SECONDS` when that is a positive number.

**What the agent is told today** (`scripts/git-client-side-hooks-pre-push-conflict-check.py:161`):

```
pre-push: the conflict check did not run for branch fix-layout (the 60-second budget was spent); the push goes ahead unchecked.
```

**What the agent cannot tell from the text.** What to do. The earlier branch's own message says why that branch took the time, so this message does not tell the agent to tell the user.

**Proposed text** (`{budget}` is the budget in seconds):

```
pre-push: branch {branch} was not checked for conflicts with origin/main, because the earlier branches in this push used up the {budget}-second time budget.
Check {branch} by hand from your worktree: python3 scripts/branch-conflict-check.py --head {commit}
```

### 6. The check gave no verdict

**When an agent sees this.** `scripts/branch-conflict-check.py` ended without a result the pre-push conflict check can read. The pre-push conflict check builds one of five reasons: the program could not be started; it had not finished when the time budget ran out, and was stopped; it was killed by a signal; it exited 1, its status for a conflict, without a `VERDICT: CONFLICT` line; or it exited with another status.

**What the agent is told today** (`scripts/git-client-side-hooks-pre-push-conflict-check.py:176`):

```
pre-push: the conflict check gave no verdict for branch fix-layout (it had not finished when the 60-second budget ran out, and was stopped); the push goes ahead unchecked.
```

**What the agent cannot tell from the text.** What to do, and whether to tell anyone.

**Proposed text, when the time budget ran out:**

```
pre-push: branch {branch} was not checked for conflicts with origin/main, because scripts/branch-conflict-check.py had not finished when the {budget}-second time budget ran out, and was stopped.
Check {branch} by hand from your worktree: python3 scripts/branch-conflict-check.py --head {commit}
If that run also prints no VERDICT line, tell the user this whole message and what that run printed.
```

**Proposed text, for the other four reasons** (`{reason}` is the reason, as today):

```
pre-push: branch {branch} was not checked for conflicts with origin/main, because scripts/branch-conflict-check.py gave no verdict: {reason}.
Check {branch} by hand from your worktree: python3 scripts/branch-conflict-check.py --head {commit}
{tell_user_line}
```

### 7. The pre-push conflict check raised an error

**When an agent sees this.** The pre-push conflict check raises a Python `Exception`, which the program catches so that the push is not stopped.

**What the agent is told today** (`scripts/git-client-side-hooks-pre-push-conflict-check.py:196`; the hook fills in the exception's type and text):

```
pre-push: the conflict check failed (<exception type>: <exception text>); the push goes ahead unchecked.
```

**What the agent cannot tell from the text.** Which branches went unchecked, what to do, and whether to tell anyone.

**Proposed text, when the program had read the pushed branches** (`{error}` is the exception's type and text, as today):

```
pre-push: the pre-push conflict check failed with {error}, so no branch in this push was checked for conflicts with origin/main: {branches}.
{unchecked_lines}
{tell_user_line}
```

**Proposed text, when the error came before the program had read them:**

```
pre-push: the pre-push conflict check failed with {error} before reading which branches this push sends, so no branch in this push was checked for conflicts with origin/main.
For each branch this push sends to origin, other than main, run from your worktree: python3 scripts/branch-conflict-check.py --head <branch name>
{tell_user_line}
```

### 8. The session trailer may not have been added

**When an agent sees this.** In an agent-session, `git interpret-trailers` fails while `prepare-commit-msg` adds the session trailer, and git prints the tool's error just above the hook's line. The commit goes on. The message can print during `git commit`, and once for each commit a rebase, a cherry-pick or a merge makes.

**What the agent is told today** (`scripts/git-client-side-hooks/prepare-commit-msg:74`):

```
prepare-commit-msg: could not add the session trailer; add it by hand
```

**What the agent cannot tell from the text.** Why the trailer matters, what the trailer is, how to add the trailer, which commit to add it to, and what to do when adding it fails again. `git commit --amend` changes whatever commit `HEAD` is, and without `--only` it also commits whatever is staged. A pushed commit must not be amended, because amending it needs a force push.

**Proposed text** (`{trailer}` is the trailer the hook meant to add, such as `Claude-Session: https://claude.ai/code/session_01ABC`):

```
prepare-commit-msg: git interpret-trailers failed, so the trailer "{trailer}" may be missing from this commit's message; the trailer is how a reviewer finds the agent-session that made a commit. git's error is just above this line.
If this commit was made by a rebase, merge or cherry-pick, leave the commits as they are, and tell the user this message once the operation is done.
Otherwise, if git log -1 shows the commit you just made, that commit is not pushed, and its message lacks the trailer, add it with: git commit --amend --only --no-edit --trailer "{trailer}"
If that amend fails, or the commit is already pushed, leave the commit as it is and tell the user this whole message.
```

The amend runs `prepare-commit-msg` again; the hook adds the trailer only when the message does not already carry it, so the trailer is not doubled. `--only` with no paths amends the message alone: tried in a scratch repository under git 2.56, a file staged before the amend stayed staged and stayed out of the commit.

### 9. The check gave no answer

**When an agent sees this.** `scripts/branch-conflict-check.py` exits 2, its status for a run that could not decide, and prints one of its own reports, UNFETCHED, UNMATCHED, UNRESOLVED or UNANSWERED, each with its own instructions. The audit found this message complete; it is changed here so that its command matches the other texts and so that it says when to tell the user.

**What the agent is told today** (`scripts/git-client-side-hooks-pre-push-conflict-check.py:169-174`; the report's own lines sit between the first line and the last):

```
pre-push: the conflict check gave no answer for branch fix-layout; the push goes ahead unchecked.
<the report's lines>
To get an answer, run scripts/branch-conflict-check.py --head <commit> from this checkout.
```

**Proposed text.**

```
pre-push: branch {branch} was not checked for conflicts with origin/main, because scripts/branch-conflict-check.py could not decide; its report follows.
<the report's lines>
Follow the report, then check {branch} again by hand from your worktree: python3 scripts/branch-conflict-check.py --head {commit}
If that run also prints no VERDICT line, tell the user this whole message and what that run printed.
```

### 10. A commit under the user's address

**When an agent sees this.** In an agent-session, an agent runs `git commit`, or `git merge` makes a merge commit, and the commit's author or committer email address is `junk@lerner1.com`, `ned@lerner1.com`, `nedlerner@yahoo.com` or `unconfigured-agent@nedschorus.invalid`. The commit is refused.

**What the agent is told today** (`scripts/git-client-side-hooks/pre-commit:125-131`; the hook fills in the refused identity):

```
Commit under this seat's own name, not as Ned Lerner <junk@lerner1.com>.
If this session is a seat, relaunch it with launch-claude-mac or launch-claude-ubuntu, then commit again.
If you cannot relaunch, set the identity in the same command as the commit: GIT_AUTHOR_NAME=<seat> GIT_AUTHOR_EMAIL=<seat>@nedschorus.invalid GIT_COMMITTER_NAME=<seat> GIT_COMMITTER_EMAIL=<seat>@nedschorus.invalid git commit ...
If you are amending a commit made under the user's address by mistake, add --reset-author to that same command.
If you are amending a commit the user wrote, leave it and make a new commit on top instead.
Do not change user.name or user.email in git config.
If the user is committing by hand, commit from a terminal outside the Claude session, adding -c user.name=<name> -c user.email=<address> after git if the clone's identity is unconfigured-agent.
```

**What the agent cannot tell from the text.** That the commit was refused and by which hook, and why: why an agent's commit must not carry these addresses, and why the git config must not be changed. The audit counted this message complete; the fast read of this part found the reasons missing.

**Proposed text** (`{identity}` is the refused identity, as today). The first line is new, and the sixth line gains its reason; the other lines are unchanged:

```
pre-commit: this commit is refused, because its author or committer is {identity}: an agent's commit must not carry the user's own address, which a pushed commit publishes, or the unconfigured-agent address, which marks an agent-session started without its launcher.
Commit under this seat's own name, not as {identity}.
If this session is a seat, relaunch it with launch-claude-mac or launch-claude-ubuntu, then commit again.
If you cannot relaunch, set the identity in the same command as the commit: GIT_AUTHOR_NAME=<seat> GIT_AUTHOR_EMAIL=<seat>@nedschorus.invalid GIT_COMMITTER_NAME=<seat> GIT_COMMITTER_EMAIL=<seat>@nedschorus.invalid git commit ...
If you are amending a commit made under the user's address by mistake, add --reset-author to that same command.
If you are amending a commit the user wrote, leave it and make a new commit on top instead.
Do not change user.name or user.email in git config: every worktree of the clone shares that config, so the change would rename every agent-seat's commits.
If the user is committing by hand, commit from a terminal outside the Claude session, adding -c user.name=<name> -c user.email=<address> after git if the clone's identity is unconfigured-agent.
```

### 11. The conflict refusal

**When an agent sees this.** A pushed branch conflicts with origin/main, and main has not deleted any file the branch changes. `scripts/branch-conflict-check.py` handles the deleted-file case with a refusal of its own, which tells the agent to close the pull request and carry the work forward.

**What the agent is told today** (`scripts/branch-conflict-check.py`, the plain conflict verdict):

```
VERDICT: CONFLICT -- <commit> conflicts with origin/main.
Merge origin/main into the branch by hand, with the frozen head as first parent.
Resolve the conflict and change nothing else in the merge.
Before pushing, rerun the test suites for what the merge touched.
```

**What the agent cannot tell from the text.** CLAUDE.md's first step: see what the conflict is with. When main has replaced the branch's work without deleting the file, for example by rewriting the same function another way, a hand-merge is the wrong action.

**Proposed text.** One line is added after the verdict line, before the merge line; the other lines are unchanged:

```
First see what the conflict is with: if main has already replaced this branch's work, do not merge; close the pull request and carry what main still lacks on a new topic branch cut from current main.
```

## Messages left as they are

- The pre-push conflict check's closing line after a conflict, "Once the merge is committed, push again.", follows the conflict report and applies to the hand-merge case.

## Tests

`scripts/git-client-side-hooks-pre-push-test.py` asserts parts of today's messages 1, 2, 3, 4, 6 and 9; the case for message 1 is removed with the message, and `scripts/git-client-side-hooks-prepare-commit-msg-test.py` asserts message 8, `scripts/git-client-side-hooks-pre-commit-test.py` asserts message 10, and `scripts/branch-conflict-check-test.py` asserts message 11. The pull request changes those cases with the texts, and adds cases for what no case covers today: message 5, message 7 in both forms, the branch and commit each message names, the trailer message 8 names, and the shell part's branch filter, as "Code the new texts need" says.
