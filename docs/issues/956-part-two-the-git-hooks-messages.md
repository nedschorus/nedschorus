# Part two: the messages of the git hooks that run at commit and push

This document is part two of GHI [Every refusal and warning a program hands an agent says why and what to do instead](https://github.com/nedschorus/nedschorus/issues/956). The GHI's GHI-MD, `docs/issues/956-every-refusal-and-warning-a-program-hands-an.md`, covers part one and lists all six parts under "Later parts". This part covers the git hooks that run when an agent commits or pushes. It shows each of their messages that leaves a question open, as the agent sees the message, and proposes the exact words to replace it. None of the proposed wording is built. The next action is one approval-walk with the user over the proposed texts, then one pull request, cut from main, that changes the messages and the test cases that assert them.

## What a reader needs first

**The git hooks.** Each clone sets `core.hooksPath` to the directory `scripts/git-client-side-hooks/` in the clone's reference checkout, which stays on main, so every agent-seat's worktree on a machine runs main's copy. Git runs:

- `pre-commit` before each commit; it refuses a commit made under the user's own name. Its refusal answers the four questions below already, so it has no section here.
- `prepare-commit-msg` while git prepares each commit's message; it adds a trailer naming the Claude session that made the commit.
- `pre-push` before each push; it runs `scripts/git-client-side-hooks-pre-push-conflict-check.py`, which runs `scripts/branch-conflict-check.py` on each branch being pushed to origin and refuses the push when the branch conflicts with origin/main.

A git hook's message is what the hook prints to stderr. An agent that runs `git commit` or `git push` through Bash sees that text in the command's output, mixed with git's own.

**Failing open.** A pre-push hook that exits nonzero stops the push, and a prepare-commit-msg hook that exits nonzero stops the commit. Both hooks run for every agent-seat on the machine, so both exit 0 when they themselves fail: a broken hook must not stop every agent's work. The push or the commit goes ahead, and the hook's message is then the only sign that a check did not happen. Every message in this part is of that kind.

**The four questions.** As in part one, a message is complete when the message says:

1. What was refused or found, naming the file or the command.
2. Why: the rule being enforced, or what goes wrong if the agent goes ahead.
3. What to do instead, as an instruction.
4. Under which condition each instruction applies, when the message gives more than one.

**Where the list comes from.** The audit's report, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/MD-skills/refusal-and-warning-message-audit-2026-10-01.md`, found 8 of these hooks' 11 messages missing the third question, and one of them missing the second. Every message below was read again from main at the commit [Merge pull request #1025 from nedschorus/skill-start-new-agent-seat-on-ned-box](https://github.com/nedschorus/nedschorus/commit/1a23e5ef), and the line numbers are main's at that commit. Three messages answer all four questions and are left as they are: the pre-commit refusal, the pre-push refusal for a conflicting branch, and the pre-push message for a check that gave no answer, which names the command to run.

## What every unchecked push should tell the agent

Six of the eight messages say only that the push "goes ahead unchecked". The agent cannot tell from that text whether anything is wrong with the branch, whether to do anything, or whether to tell anyone. Two facts decide what the agent should do:

- The branch may still conflict with main. The check can be run by hand, as the pre-push message for a check that gave no answer already says: `python3 scripts/branch-conflict-check.py --head <commit>`, from the checkout that pushed. A conflict found then is cleared the way `scripts/branch-conflict-check.py` reports, as CLAUDE.md says.
- A hook that cannot run its check is broken on that machine, for every agent-seat there, and only the user can repair the machine. CLAUDE.md requires a failure to be made visible to whoever acts on it.

So each proposed text below says what did not run and why the push went ahead, then gives the hand-run command, then says when to tell the user.

## The messages, one at a time

### 1. python3 is not on PATH

**When an agent sees this.** An agent runs `git push` in a shell whose PATH has no `python3`.

**What the agent is told today** (`scripts/git-client-side-hooks/pre-push:31`):

```
pre-push: the conflict check did not run (no python3 on PATH); the push goes ahead unchecked.
```

**What the agent cannot tell from the text.** What to do. The hand-run check needs python3 too, so the agent cannot run the check either.

**Proposed text.**

```
pre-push: the conflict check did not run, because python3 is not on PATH; the push went ahead without being checked against origin/main.
Tell the user this message: no agent-seat's push on this machine is being checked until python3 is on PATH.
```

### 2. The conflict check's Python file is missing

**When an agent sees this.** The reference checkout that `core.hooksPath` points into has no `scripts/git-client-side-hooks-pre-push-conflict-check.py`, for example because the checkout is on a branch where the file does not exist.

**What the agent is told today** (`scripts/git-client-side-hooks/pre-push:36`; the hook fills in the path):

```
pre-push: the conflict check did not run (/Users/el/Projects/nedschorus/scripts/git-client-side-hooks/../git-client-side-hooks-pre-push-conflict-check.py is missing); the push goes ahead unchecked.
```

**What the agent cannot tell from the text.** What to do.

**Proposed text** (`{path}` is the missing file):

```
pre-push: the conflict check did not run, because {path} is missing; the push went ahead without being checked against origin/main.
Check the branch by hand from this checkout: python3 scripts/branch-conflict-check.py --head <the commit you pushed>
Tell the user this message: no agent-seat's push on this machine is being checked until that file is back.
```

### 3. The conflict check's Python file failed

**When an agent sees this.** `scripts/git-client-side-hooks-pre-push-conflict-check.py` exits with a status other than 0 and 10, for example when Python cannot start the file.

**What the agent is told today** (`scripts/git-client-side-hooks/pre-push:47`):

```
pre-push: the conflict check failed (exit 1); the push goes ahead unchecked.
```

**What the agent cannot tell from the text.** What to do.

**Proposed text** (`{status}` is the exit status):

```
pre-push: the conflict check failed with exit status {status}; the push went ahead without being checked against origin/main. Any error the check printed is above this line.
Check the branch by hand from this checkout: python3 scripts/branch-conflict-check.py --head <the commit you pushed>
Tell the user this message: the pre-push hook is failing on this machine.
```

### 4. branch-conflict-check.py is missing

**When an agent sees this.** The conflict check's Python file runs, but `scripts/branch-conflict-check.py` is not beside it.

**What the agent is told today** (`scripts/git-client-side-hooks-pre-push-conflict-check.py:151`):

```
pre-push: the conflict check did not run (/Users/el/Projects/nedschorus/scripts/branch-conflict-check.py is missing); the push goes ahead unchecked.
```

**What the agent cannot tell from the text.** What to do. The hand-run command is the missing file, so the agent cannot run the check either.

**Proposed text** (`{path}` is the missing file):

```
pre-push: the conflict check did not run, because {path} is missing; the push went ahead without being checked against origin/main.
Tell the user this message: no agent-seat's push on this machine is being checked until that file is back.
```

### 5. The time budget ran out before a branch's turn

**When an agent sees this.** One push carries several branches, and the check of the earlier branches used up the hook's time budget, 60 seconds unless `NEDSCHORUS_PRE_PUSH_CONFLICT_CHECK_SECONDS` sets another, before this branch's turn.

**What the agent is told today** (`scripts/git-client-side-hooks-pre-push-conflict-check.py:161`):

```
pre-push: the conflict check did not run for branch fix-layout (the 60-second budget was spent); the push goes ahead unchecked.
```

**What the agent cannot tell from the text.** What to do. Nothing is broken here, so the user need not hear of it.

**Proposed text** (`{branch}`, `{budget}` and `{commit}` are filled in by the hook):

```
pre-push: the conflict check did not run for branch {branch}, because the earlier branches in this push used up its {budget}-second budget; the push went ahead without checking {branch} against origin/main.
Check the branch by hand from this checkout: python3 scripts/branch-conflict-check.py --head {commit}
```

### 6. The check gave no verdict

**When an agent sees this.** `scripts/branch-conflict-check.py` could not be started, ran past the budget and was stopped, was killed, or exited with a status it never uses.

**What the agent is told today** (`scripts/git-client-side-hooks-pre-push-conflict-check.py:176`; the reason in parentheses is one of five the hook builds):

```
pre-push: the conflict check gave no verdict for branch fix-layout (it had not finished when the 60-second budget ran out, and was stopped); the push goes ahead unchecked.
```

**What the agent cannot tell from the text.** What to do, and whether the reason means the hook is broken. A check that ran past the budget is usually a slow fetch; a check that could not be started, was killed, or exited with a status it never uses is a defect.

**Proposed text** (`{reason}` is the hook's reason, as today):

```
pre-push: the conflict check gave no verdict for branch {branch}, because {reason}; the push went ahead without checking {branch} against origin/main.
Check the branch by hand from this checkout: python3 scripts/branch-conflict-check.py --head {commit}
If the hand-run check also fails to give a verdict, tell the user this message and what the hand-run check printed.
```

### 7. The conflict check raised an error

**When an agent sees this.** `scripts/git-client-side-hooks-pre-push-conflict-check.py` raises a Python exception, which the file catches so that the push is not stopped.

**What the agent is told today** (`scripts/git-client-side-hooks-pre-push-conflict-check.py:196`; the hook fills in the exception's type and text):

```
pre-push: the conflict check failed (<exception type>: <exception text>); the push goes ahead unchecked.
```

**What the agent cannot tell from the text.** What to do. An exception here is a defect in the hook.

**Proposed text** (`{error}` is the exception's type and text, as today):

```
pre-push: the conflict check failed with {error}; the push went ahead without being checked against origin/main.
Check the branch by hand from this checkout: python3 scripts/branch-conflict-check.py --head <the commit you pushed>
Tell the user this message: the pre-push hook has a defect.
```

### 8. The session trailer was not added

**When an agent sees this.** An agent runs `git commit` in a Claude session, and `git interpret-trailers` fails while adding the trailer that names the session. The commit still goes ahead.

**What the agent is told today** (`scripts/git-client-side-hooks/prepare-commit-msg:74`):

```
prepare-commit-msg: could not add the session trailer; add it by hand
```

**What the agent cannot tell from the text.** Why the trailer matters, what the trailer is, and how to add the trailer by hand. A pushed commit is frozen, so the instruction must not have the agent amend a commit that is already pushed.

**Proposed text** (`{trailer}` is the trailer the hook meant to add, such as `Claude-Session: https://claude.ai/code/session_01ABC`):

```
prepare-commit-msg: the session trailer was not added, so this commit does not record which Claude session made it; a reviewer uses the trailer to find the session. git interpret-trailers' error is above this line.
If the commit is not pushed yet, add the trailer with: git commit --amend --no-edit --trailer "{trailer}"
If the commit is pushed, leave it as it is.
```

## Code the pull request changes besides the texts

- `scripts/git-client-side-hooks-pre-push-conflict-check.py` passes the pushed commit, `local_object_id`, into messages 5 and 6, as the no-answer message already does.
- Messages 2, 3 and 7 cannot name the pushed commit: `pre-push` has not read the pushed refs when it prints messages 2 and 3, and message 7 may come from a failure to read them. They say `<the commit you pushed>` instead.
- `scripts/git-client-side-hooks/prepare-commit-msg` fills `{trailer}` from the `session_trailer` it already builds.
- The test cases that assert these texts, in `scripts/git-client-side-hooks-pre-push-test.py` and `scripts/git-client-side-hooks-prepare-commit-msg-test.py`, change with the texts.
